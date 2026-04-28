"""
db package
==========
Domain-split database repositories.
Import from here instead of the old monolithic database.py.
"""

# Re-export everything so existing callers can migrate gradually
from app.db.connection import init_db, close_db, _get_pool, _now_iraq, IRAQ_TZ
from app.db.rates import (
    insert_rate,
    get_latest_rate,
    get_rate_24h_ago,
    get_last_stored_average,
    get_last_message_id,
    get_rate_history,
    get_rates_count,
)
from app.db.messages import (
    insert_raw_message,
    get_unprocessed_messages,
    mark_as_processed,
    get_raw_messages_count,
    cleanup_old_raw_messages,
)
from app.db.users import (
    get_or_create_user,
    create_api_key_for_user,
    validate_api_key,
    list_user_keys,
    revoke_api_key,
)

__all__ = [
    # connection
    "init_db", "close_db", "_get_pool", "_now_iraq", "IRAQ_TZ",
    # rates
    "insert_rate", "get_latest_rate", "get_rate_24h_ago",
    "get_last_stored_average", "get_last_message_id",
    "get_rate_history", "get_rates_count",
    # messages
    "insert_raw_message", "get_unprocessed_messages",
    "mark_as_processed", "get_raw_messages_count", "cleanup_old_raw_messages",
    # users / keys
    "get_or_create_user", "create_api_key_for_user",
    "validate_api_key", "list_user_keys", "revoke_api_key",
]
