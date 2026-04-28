"""
Redis Rate Limiter
==================
Implements the 3-Layer Defense System:
Layer 1: Speed Limit (requests per minute)
Layer 2 & 3: Token Budget (daily token quota)
"""

import logging
from app import cache

logger = logging.getLogger(__name__)

import time

# Limits
SPEED_LIMIT_RPM = 300         # 300 requests per minute
DAILY_TOKEN_BUDGET = 10000   # 10,000 tokens per day

# Local Memory Fallback (Circuit Breaker)
_local_fallback_cache = {}

def _check_local_speed_limit(api_key: str) -> bool:
    """Fallback rate limiter if Redis is offline (Strict 20 RPM limit)."""
    now = time.time()
    minute_key = f"{api_key}:{int(now // 60)}"
    
    # Cleanup to prevent memory leak
    if len(_local_fallback_cache) > 10000:
        _local_fallback_cache.clear()
        
    count = _local_fallback_cache.get(minute_key, 0) + 1
    _local_fallback_cache[minute_key] = count
    
    if count > 20: # Stricter limit during degraded state
        return False
    return True

async def check_speed_limit(api_key: str) -> bool:
    """
    Check if the user has exceeded requests in the last minute.
    Returns True if allowed, False if blocked.
    """
    client = cache._get_redis()
    
    if not client:
        # CIRCUIT BREAKER: Redis is down, use local memory
        return _check_local_speed_limit(api_key)
        
    try:
        # Key expires every 60 seconds
        redis_key = f"rate:speed:{api_key}"
        
        # INCR creates the key if it doesn't exist and increments it
        current = await client.incr(redis_key)
        
        # If we just created it, set the TTL to 60 seconds
        if current == 1:
            await client.expire(redis_key, 60)
            
        if current > SPEED_LIMIT_RPM:
            return False
            
        return True
    except Exception as e:
        logger.error(f"Speed limit check failed: {e}")
        return _check_local_speed_limit(api_key)

async def consume_tokens(api_key: str, cost: int) -> dict:
    """
    Consume tokens from the daily budget.
    Returns dict: {"allowed": bool, "remaining": int}
    """
    budget = 500000 if api_key.startswith("guest_") else DAILY_TOKEN_BUDGET
    
    client = cache._get_redis()
    if not client:
        return {"allowed": True, "remaining": budget}
        
    from datetime import datetime, timezone
    
    try:
        # Use UTC date for the daily bucket
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        redis_key = f"rate:budget:{api_key}:{today}"
        
        # Increment by the cost of the endpoint
        current_usage = await client.incrby(redis_key, cost)
        
        # If we just created the bucket, set it to expire in 24 hours (86400s)
        if current_usage == cost:
            await client.expire(redis_key, 86400)
            
        if current_usage > budget:
            return {
                "allowed": False, 
                "remaining": 0,
                "usage": current_usage
            }
            
        return {
            "allowed": True,
            "remaining": budget - current_usage,
            "usage": current_usage
        }
    except Exception as e:
        logger.error(f"Token budget check failed: {e}")
        return {"allowed": True, "remaining": budget}


# ── Brute Force Detection ─────────────────────────────────────────────
# Tracks failed API key attempts per IP address.
# After AUTH_FAIL_LIMIT failures in AUTH_FAIL_WINDOW seconds,
# the IP is blocked from further attempts until the window expires.

AUTH_FAIL_LIMIT  = 10    # Max allowed failures
AUTH_FAIL_WINDOW = 900   # 15-minute sliding window (seconds)


async def track_auth_failure(ip: str) -> int:
    """
    Increment the failure counter for this IP.
    Returns the current failure count after incrementing.
    Call this whenever a key validation fails.
    """
    client = cache._get_redis()
    if not client:
        return 0  # Redis offline — fail open (don't block)

    redis_key = f"auth:fail:{ip}"
    try:
        count = await client.incr(redis_key)
        if count == 1:
            # First failure — set the sliding window TTL
            await client.expire(redis_key, AUTH_FAIL_WINDOW)

        if count >= AUTH_FAIL_LIMIT:
            logger.warning(
                f"Brute force detected: {ip} has {count} failed auth "
                f"attempts in the last {AUTH_FAIL_WINDOW // 60} minutes"
            )
        return count
    except Exception as e:
        logger.error(f"track_auth_failure failed for {ip}: {e}")
        return 0


async def is_ip_blocked(ip: str) -> bool:
    """
    Check if an IP has exceeded the auth failure threshold.
    Returns True if the IP should be blocked, False otherwise.
    Call this BEFORE any DB lookup to fail fast.
    """
    client = cache._get_redis()
    if not client:
        return False  # Redis offline — fail open

    redis_key = f"auth:fail:{ip}"
    try:
        count = await client.get(redis_key)
        if count and int(count) >= AUTH_FAIL_LIMIT:
            return True
        return False
    except Exception as e:
        logger.error(f"is_ip_blocked check failed for {ip}: {e}")
        return False  # Fail open on Redis errors
