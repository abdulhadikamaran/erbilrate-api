"""
auth.py
=======
Pure cryptographic utilities for API key lifecycle.
No database calls live here — those are in app/db/users.py.

Responsibilities:
  - Generate random API keys
  - Hash keys with SHA-256 (one-way)
  - Mask keys for UI display
"""

import secrets
import hashlib


def hash_api_key(api_key: str) -> str:
    """Create a secure one-way SHA-256 hash of the API key."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_raw_api_key(prefix: str = "er_live_") -> str:
    """Generate a cryptographically secure random API key."""
    return f"{prefix}{secrets.token_urlsafe(32)}"


def mask_api_key(api_key: str) -> str:
    """Create a masked version for UI display (e.g., er_live_********8F2a)."""
    prefix = api_key[:8]   # 'er_live_'
    suffix = api_key[-4:]
    return f"{prefix}********{suffix}"
