"""
FastAPI Security Dependencies
=============================
Two dependency functions protect all routes:

  get_authorized_user()   — validates developer API keys + rate limits
  get_clerk_user()        — validates Clerk RS256 JWTs for admin dashboard

Security contract for get_clerk_user():
  - Fetches Clerk's JWKS and verifies the RS256 signature on every request
  - JWKS is cached in Redis for 1 hour to avoid latency
  - If a key ID (kid) is not found, the cache is force-refreshed once
  - Refuses all requests if CLERK_FRONTEND_API_URL is not configured
  - Any signature failure returns 401 — never falls through silently
"""

import json
import logging

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

from app import db, rate_limit, cache
from app.config import settings

logger = logging.getLogger(__name__)

# ── API Key Header Schemes ────────────────────────────────────────────

api_key_header_scheme  = APIKeyHeader(name="X-API-Key", auto_error=False)
auth_header_scheme     = APIKeyHeader(name="Authorization", auto_error=False)
bearer_scheme          = HTTPBearer()


# ── Clerk JWKS Verifier ───────────────────────────────────────────────

class ClerkJWTVerifier:
    """
    Verifies Clerk-issued RS256 JWTs.

    JWKS flow:
      1. Check Redis cache (key: clerk:jwks, TTL: 1 hour)
      2. On cache miss → fetch from Clerk's JWKS endpoint
      3. Match the JWT's kid header to a key in the JWKS set
      4. If kid not found → force-refresh JWKS once (key rotation)
      5. Verify signature + expiry with PyJWT
    """

    _CACHE_KEY = "clerk:jwks"

    async def _fetch_from_clerk(self) -> dict:
        """Fetch fresh JWKS directly from Clerk."""
        url = f"{settings.CLERK_FRONTEND_API_URL}/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def _get_jwks(self) -> dict:
        """Return JWKS from Redis cache, or fetch and cache from Clerk."""
        redis_client = cache._get_redis()

        if redis_client:
            try:
                cached = await redis_client.get(self._CACHE_KEY)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"JWKS cache read failed: {e}")

        jwks = await self._fetch_from_clerk()

        if redis_client:
            try:
                await redis_client.set(
                    self._CACHE_KEY,
                    json.dumps(jwks),
                    ex=settings.CLERK_JWKS_CACHE_TTL,
                )
            except Exception as e:
                logger.warning(f"JWKS cache write failed: {e}")

        return jwks

    async def _invalidate_cache(self) -> None:
        """Force-delete the JWKS cache (called when kid not found)."""
        redis_client = cache._get_redis()
        if redis_client:
            try:
                await redis_client.delete(self._CACHE_KEY)
            except Exception:
                pass

    def _extract_public_key(self, jwks: dict, kid: str):
        """Find and construct the RSA public key matching the given kid."""
        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                return RSAAlgorithm.from_jwk(key_data)
        return None

    async def verify(self, token: str) -> dict:
        """
        Fully verify a Clerk JWT.

        Returns the decoded payload dict on success.
        Raises jwt.InvalidTokenError subclasses on any failure — callers
        must handle these and return 401.
        """
        # Read header without verifying — needed to get kid
        try:
            header = jwt.get_unverified_header(token)
        except jwt.DecodeError as e:
            raise jwt.InvalidTokenError(f"Malformed JWT header: {e}")

        kid = header.get("kid")
        if not kid:
            raise jwt.InvalidTokenError("JWT header missing 'kid' field")

        alg = header.get("alg", "")
        if alg != "RS256":
            raise jwt.InvalidTokenError(
                f"Unexpected algorithm '{alg}'. Only RS256 is accepted."
            )

        # Attempt key lookup from (possibly cached) JWKS
        jwks = await self._get_jwks()
        public_key = self._extract_public_key(jwks, kid)

        if public_key is None:
            # kid not in cache — Clerk may have rotated keys
            logger.info(f"kid={kid} not in cached JWKS — forcing refresh")
            await self._invalidate_cache()
            jwks = await self._fetch_from_clerk()
            public_key = self._extract_public_key(jwks, kid)

            if public_key is None:
                raise jwt.InvalidKeyError(
                    f"No matching public key found for kid={kid}"
                )

        # Verify signature + expiry
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_aud": False,  # Clerk does not always include aud
                "verify_exp": True,   # Always enforce token expiry
            },
        )

        return payload


# Module-level singleton — one verifier shared across all requests
_clerk_verifier = ClerkJWTVerifier()


# ── Dependency: API Key Auth (Developer Requests) ─────────────────────

async def get_authorized_user(
    request: Request,
    x_api_key: str = Security(api_key_header_scheme),
    auth_header: str = Security(auth_header_scheme),
) -> dict:
    """
    Validate a developer API key and enforce rate limits.
    Returns the user dict if valid. Falls back to a guest profile if no key.
    """
    # Extract key from X-API-Key or Authorization: Bearer <key>
    api_key = x_api_key
    if not api_key and auth_header:
        api_key = (
            auth_header.removeprefix("Bearer ").strip()
            if auth_header.startswith("Bearer ")
            else auth_header.strip()
        )

    # Enforce max key length to prevent CPU-exhaustion via huge headers
    if api_key and len(api_key) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key format.",
        )

    if not api_key:
        # GUEST MODE — IP-based speed limit only, no token consumption
        client_ip = request.client.host if request.client else "unknown_ip"
        guest_key = f"guest_{client_ip}"

        speed_ok = await rate_limit.check_speed_limit(guest_key)
        if not speed_ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Public rate limit exceeded. Generate a free API key for more access.",
            )

        return {
            "id": "guest",
            "tier": "guest",
            "api_key": guest_key,
            "email": "guest@public",
            "bypass_tokens": True,
        }

    # ── Layer 0: Brute force block (fastest path — Redis GET, no DB) ──
    # Check BEFORE speed limit and DB to immediately short-circuit known bad IPs.
    client_ip = request.client.host if request.client else "unknown"
    if await rate_limit.is_ip_blocked(client_ip):
        logger.warning(f"Auth blocked: {client_ip} exceeded failure threshold")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Too many failed authentication attempts from this IP. "
                f"Try again in {rate_limit.AUTH_FAIL_WINDOW // 60} minutes."
            ),
        )

    # Layer 1: Speed limit check (fastest path — Redis INCR, no DB)
    speed_ok = await rate_limit.check_speed_limit(api_key)
    if not speed_ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Speed limit exceeded. Maximum 60 requests per minute allowed.",
        )

    # Layer 2: Key validation — try auth cache first, then DB
    user_data = None
    redis_client = cache._get_redis()

    if redis_client:
        try:
            cached = await redis_client.get(f"auth:{api_key}")
            if cached:
                user_data = json.loads(cached)
        except Exception:
            pass

    if not user_data:
        user_data = await db.validate_api_key(api_key)
        if not user_data:
            # Track this failure against the requester's IP
            failure_count = await rate_limit.track_auth_failure(client_ip)
            remaining = max(0, rate_limit.AUTH_FAIL_LIMIT - failure_count)
            logger.warning(
                f"Invalid API key from {client_ip} — "
                f"failure {failure_count}/{rate_limit.AUTH_FAIL_LIMIT} "
                f"({remaining} attempts remaining before block)"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key.",
            )
        # Cache valid key for 5 minutes
        if redis_client:
            try:
                await redis_client.set(
                    f"auth:{api_key}",
                    json.dumps(user_data, default=str),
                    ex=300,
                )
            except Exception as e:
                logger.warning(f"Failed to cache auth data: {e}")

    user_data["api_key"] = api_key
    return user_data


# ── Dependency: Clerk JWT Auth (Admin Dashboard) ──────────────────────

async def get_clerk_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> dict:
    """
    Authenticate requests to /api/admin/* using Clerk RS256 JWTs.

    Security guarantees:
      - Signature verified against Clerk's JWKS (RS256)
      - Token expiry enforced
      - Only RS256 algorithm accepted
      - Refuses all requests if CLERK_FRONTEND_API_URL is not set
    """
    if not settings.CLERK_FRONTEND_API_URL:
        logger.error(
            "CLERK_FRONTEND_API_URL is not configured. "
            "JWT signature verification cannot proceed. "
            "Set this variable in .env immediately."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured.",
        )

    token = credentials.credentials

    try:
        payload = await _clerk_verifier.verify(token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please sign in again.",
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT verification failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch Clerk JWKS: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )
    except Exception as e:
        logger.error(f"Unexpected JWT verification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim.",
        )

    # Clerk puts the email in the payload when using JWT templates
    # Fall back to a stable placeholder based on the permanent Clerk sub ID
    email = payload.get("email", f"{clerk_user_id}@clerk.local")

    # Sync user with PostgreSQL (upsert — safe to call every time)
    user_id = await db.get_or_create_user(
        clerk_user_id=clerk_user_id,
        email=email,
    )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync user profile with database.",
        )

    return {
        "id": user_id,
        "clerk_user_id": clerk_user_id,
        "email": email,
    }
