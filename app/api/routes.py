"""
API Route Handlers
==================
All REST API endpoints. Thin handlers that validate input,
call the database, apply formulas, and return Pydantic models.
Zero business logic lives here.
"""

from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect, Depends
from app.ws_manager import manager
from app.api.dependencies import get_authorized_user

from app import db
from app import cache
from app import rate_limit
from app.models import (
    RateResponse,
    UsdToIqdResponse,
    IqdToUsdResponse,
    HistoryResponse,
    HealthResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/api")


# ── GET /api/rate/latest ──────────────────────────────────────────────

@router.get(
    "/rate/latest",
    response_model=RateResponse,
    responses={503: {"model": ErrorResponse}},
    summary="Get latest Erbil exchange rate",
    description="Returns the most recently stored USD/IQD exchange rate for Erbil. Cost: 1 Token.",
)
async def get_latest_rate(
    user: dict = Depends(get_authorized_user)
):
    # Consume 1 token
    api_key = user.get("api_key")
    if not user.get("bypass_tokens"):
        token_check = await rate_limit.consume_tokens(api_key, cost=1)
        if not token_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded. Usage: {token_check['usage']}/10000"
            )

    # Try Redis first (fast path — no DB hit)
    rate = await cache.get_latest_rate()
    rate_source = "redis"

    if rate is None:
        # Redis miss or unavailable — fall back to PostgreSQL
        rate = await db.get_latest_rate()
        rate_source = "postgres"

    if rate is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "No exchange rate data available yet.", "code": "NO_DATA"},
        )

    # daily_change: Redis stores it as-is; Postgres row needs calculation
    if rate_source == "postgres":
        rate_24h = await db.get_rate_24h_ago()
        daily_change = rate["erbil_average"] - rate_24h["erbil_average"] if rate_24h else None
    else:
        daily_change = rate.get("daily_change")

    return RateResponse(
        city="Erbil",
        penzi=rate["erbil_penzi"],
        sur=rate["erbil_sur"],
        average=rate["erbil_average"],
        daily_change=daily_change,
        last_updated=rate["created_at"],
    )


# ── WS /api/ws ────────────────────────────────────────────────────────
# Max concurrent WebSocket connections allowed per IP.
# Prevents a single client from exhausting the connection pool.
_WS_MAX_CONNECTIONS_PER_IP = 5
_ws_ip_counts: dict[str, int] = {}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    api_key: str | None = None,  # Optional: ?api_key=er_live_...
):
    """
    Real-time rate broadcast over WebSocket.

    Auth model (mirrors REST endpoints):
      - No key: guest connection, counted per IP, max 5 concurrent per IP
      - Valid key: developer connection, tracked and logged
      - Invalid key: rejected with close code 4003 before connection is accepted

    Public website visitors connect without a key — this is intentional.
    The rate data is public. The controls prevent connection-pool exhaustion.
    """
    client_ip = websocket.client.host if websocket.client else "unknown"

    # ── 1. Validate API key if provided ──────────────────────────────
    user_id = "guest"
    if api_key:
        if len(api_key) > 256:
            await websocket.close(code=4003, reason="Invalid API key format.")
            return

        user_data = await db.validate_api_key(api_key)
        if not user_data:
            await websocket.close(code=4003, reason="Invalid or revoked API key.")
            logger.warning(f"WS: rejected invalid API key from {client_ip}")
            return

        user_id = str(user_data.get("user_id", "unknown"))
        logger.info(f"WS: developer connection accepted (user_id={user_id}, ip={client_ip})")
    else:
        logger.debug(f"WS: guest connection from {client_ip}")

    # ── 2. Enforce per-IP connection limit ────────────────────────────
    current_count = _ws_ip_counts.get(client_ip, 0)
    if current_count >= _WS_MAX_CONNECTIONS_PER_IP:
        await websocket.close(
            code=4029,
            reason=f"Too many connections from this IP (max {_WS_MAX_CONNECTIONS_PER_IP})."
        )
        logger.warning(
            f"WS: rejected connection from {client_ip} — "
            f"already at limit ({current_count}/{_WS_MAX_CONNECTIONS_PER_IP})"
        )
        return

    # ── 3. Accept connection and track it ────────────────────────────
    _ws_ip_counts[client_ip] = current_count + 1
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        # Always decrement counter on disconnect — regardless of error
        manager.disconnect(websocket)
        _ws_ip_counts[client_ip] = max(0, _ws_ip_counts.get(client_ip, 1) - 1)
        if _ws_ip_counts[client_ip] == 0:
            del _ws_ip_counts[client_ip]
        logger.debug(f"WS: {client_ip} disconnected (user_id={user_id})")


# ── GET /api/convert/usd-to-iqd ──────────────────────────────────────

@router.get(
    "/convert/usd-to-iqd",
    response_model=UsdToIqdResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Convert USD to IQD",
    description="Converts a USD amount to IQD using the latest Erbil average rate. Cost: 1 Token.",
)
async def convert_usd_to_iqd(
    amount: float = Query(
        ...,
        gt=0,
        description="Amount in USD to convert (must be positive)",
    ),
    user: dict = Depends(get_authorized_user),
):
    # Consume 1 token
    api_key = user.get("api_key")
    if not user.get("bypass_tokens"):
        token_check = await rate_limit.consume_tokens(api_key, cost=1)
        if not token_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded. Usage: {token_check['usage']}/10000",
            )

    # Cache-first: avoid unnecessary DB hits
    rate = await cache.get_latest_rate()
    if rate is None:
        rate = await db.get_latest_rate()

    if rate is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "No exchange rate data available yet.", "code": "NO_DATA"},
        )

    average = rate.get("erbil_average") or rate.get("average")

    # Guard: a zero average would cause division-by-zero in iqd-to-usd
    # and produce meaningless results here — treat it as missing data.
    if not average or average <= 0:
        raise HTTPException(
            status_code=503,
            detail={"error": "Exchange rate data is unavailable.", "code": "NO_DATA"},
        )

    iqd = amount * (average / 100)
    return UsdToIqdResponse(
        usd=amount,
        iqd=round(iqd, 2),
        rate_per_100=average,
    )


# ── GET /api/convert/iqd-to-usd ──────────────────────────────────────

@router.get(
    "/convert/iqd-to-usd",
    response_model=IqdToUsdResponse,
    responses={
        400: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Convert IQD to USD",
    description="Converts an IQD amount to USD using the latest Erbil average rate. Cost: 1 Token.",
)
async def convert_iqd_to_usd(
    amount: float = Query(
        ...,
        gt=0,
        description="Amount in IQD to convert (must be positive)",
    ),
    user: dict = Depends(get_authorized_user),
):
    # Consume 1 token
    api_key = user.get("api_key")
    if not user.get("bypass_tokens"):
        token_check = await rate_limit.consume_tokens(api_key, cost=1)
        if not token_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded. Usage: {token_check['usage']}/10000",
            )

    # Cache-first: avoid unnecessary DB hits
    rate = await cache.get_latest_rate()
    if rate is None:
        rate = await db.get_latest_rate()

    if rate is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "No exchange rate data available yet.", "code": "NO_DATA"},
        )

    average = rate.get("erbil_average") or rate.get("average")

    # Guard: prevents ZeroDivisionError and serves meaningless results
    if not average or average <= 0:
        raise HTTPException(
            status_code=503,
            detail={"error": "Exchange rate data is unavailable.", "code": "NO_DATA"},
        )

    usd = amount / (average / 100)
    return IqdToUsdResponse(
        iqd=amount,
        usd=round(usd, 2),
        rate_per_100=average,
    )


# ── GET /api/rate/history ─────────────────────────────────────────────

@router.get(
    "/rate/history",
    response_model=HistoryResponse,
    summary="Get historical exchange rates",
    description="Returns exchange rate records from the last N days. Cost: N Tokens.",
)
async def get_rate_history(
    days: int = Query(
        default=7,
        ge=1,
        le=365,
        description="Number of days of history to return (1-365)",
    ),
    user: dict = Depends(get_authorized_user)
):
    # Consume N tokens based on the number of days requested
    api_key = user.get("api_key")
    if not user.get("bypass_tokens"):
        token_check = await rate_limit.consume_tokens(api_key, cost=days)
        if not token_check["allowed"]:
            raise HTTPException(
                status_code=429,
                detail=f"Daily token budget exceeded. Usage: {token_check['usage']}/10000"
            )

    # First try fetching from Redis if they asked for exactly 1, 7, 30, or 90 days
    if days in [1, 7, 30, 90]:
        cache_client = cache._get_redis()
        if cache_client:
            try:
                import json
                cached_history = await cache_client.get(f"history:{days}")
                if cached_history:
                    rates = json.loads(cached_history)
                    return HistoryResponse(
                        city="Erbil",
                        count=len(rates),
                        rates=rates,
                    )
            except Exception:
                pass

    # Fallback: Query Postgres
    history = await db.get_rate_history(days=days)
    rates = [
        RateResponse(
            city="Erbil",
            penzi=r["penzi"],
            sur=r["sur"],
            average=r["average"],
            last_updated=r["last_updated"],
        )
        for r in history
    ]
    return HistoryResponse(
        city="Erbil",
        count=len(rates),
        rates=rates,
    )

# ── GET /api/me ────────────────────────────────────────────────────────

@router.get(
    "/me",
    summary="Get developer token usage",
    description="Returns your current daily token usage and remaining budget.",
)
async def get_me(user: dict = Depends(get_authorized_user)):
    # Guest users have no token budget — prompt them to get a key
    if user.get("tier") == "guest":
        return {
            "tier": "guest",
            "usage": 0,
            "remaining": rate_limit.DAILY_TOKEN_BUDGET,
            "daily_limit": rate_limit.DAILY_TOKEN_BUDGET,
            "note": "Get a free API key at /developers to track your usage.",
        }

    api_key = user.get("api_key")
    # Read current balance without billing (cost=0)
    # Graceful fallback if Redis is temporarily unavailable
    try:
        token_check = await rate_limit.consume_tokens(api_key, cost=0)
        usage = token_check["usage"]
        remaining = token_check["remaining"]
    except Exception:
        usage = 0
        remaining = rate_limit.DAILY_TOKEN_BUDGET

    # NOTE: email intentionally excluded — avoid leaking account details
    # in shared or logged environments. Use the Clerk dashboard to see email.
    return {
        "tier": user.get("tier"),
        "usage": usage,
        "remaining": remaining,
        "daily_limit": rate_limit.DAILY_TOKEN_BUDGET,
    }


# ── GET /api/health ───────────────────────────────────────────────────────

@router.get(
    "/health",
    summary="Public health check",
    description="Returns service status only. Use /api/health/detailed for full metrics (requires API key).",
)
async def health_check():
    """
    Public endpoint — returns only 'ok' or 'degraded'.
    Exposes zero internal infrastructure details to unauthenticated callers.
    """
    rate = await cache.get_latest_rate() or await db.get_latest_rate()
    return {"status": "ok" if rate is not None else "degraded"}


# ── GET /api/health/detailed ───────────────────────────────────────────────

@router.get(
    "/health/detailed",
    response_model=HealthResponse,
    summary="Detailed health metrics (authenticated)",
    description="Full system metrics including Redis, pipeline counts, and last event time. Requires API key.",
)
async def health_check_detailed(user: dict = Depends(get_authorized_user)):
    """
    Authenticated endpoint — returns full internal health data.
    Requires a valid API key. Use this for monitoring dashboards.
    """
    rate = await db.get_latest_rate()
    count = await db.get_rates_count()
    raw_counts = await db.get_raw_messages_count()
    redis_ok = await cache.is_redis_healthy()
    last_event = await cache.get_last_event_time()

    return HealthResponse(
        status="ok" if rate is not None else "degraded",
        last_fetch=rate["created_at"] if rate else None,
        rates_count=count,
        raw_messages_total=raw_counts["total"],
        raw_messages_unprocessed=raw_counts["unprocessed"],
        redis_healthy=redis_ok,
        last_event_received=datetime.fromisoformat(last_event) if last_event else None,
    )
