"""Row-level lookup over transactions for LLM citations

  Two read modes:
  - ID mode: fetch exact rows for a caller-supplied list of transaction_ids
  - Filter mode: fetch a bounded, newest-first sample of rows matching
    optional status/gateway/method filters within a recent window
"""

import psycopg
from psycopg.rows import dict_row

from mcp_server import validation

_MAX_IDS = 100  # reject (never clamp) over this; dropping requested IDs invalidates citations
_MAX_WINDOW_MINUTES = 1440  # 24 hours
_MAX_LIMIT = 100

_ROW_COLUMNS = """
    transaction_id, event_timestamp, merchant, method, amount::float8 AS amount,
    status, gateway, error_text, card_bin, ingested_at
"""

_IDS_SQL = f"""
    SELECT {_ROW_COLUMNS}
    FROM transactions
    WHERE transaction_id = ANY(%(ids)s::uuid[])
"""

_FILTER_SQL = f"""
    SELECT {_ROW_COLUMNS}
    FROM transactions
    WHERE event_timestamp >= now() - make_interval(mins => %(window_minutes)s)
      AND (%(status)s::text IS NULL OR status = %(status)s)
      AND (%(gateway)s::text IS NULL OR gateway = %(gateway)s)
      AND (%(method)s::text IS NULL OR method = %(method)s)
    ORDER BY event_timestamp DESC
    LIMIT %(limit)s
"""


def _reshape_row(row: dict) -> dict:
    return {
        "transaction_id": str(row["transaction_id"]),
        "event_timestamp": row["event_timestamp"].isoformat(),
        "merchant": row["merchant"],
        "method": row["method"],
        "amount": row["amount"],
        "status": row["status"],
        "gateway": row["gateway"],
        "error_text": row["error_text"],
        "card_bin": row["card_bin"],
        "ingested_at": row["ingested_at"].isoformat(),
    }


def get_transactions(
    conn: psycopg.Connection,
    transaction_ids: list[str] | None = None,
    window_minutes: int | None = None,
    status: str | None = None,
    gateway: str | None = None,
    method: str | None = None,
    limit: int = 10,
) -> dict:
    """Fetch full transaction rows, either by ID or by a bounded filter

    Mode is chosen by whether transaction_ids is a non-empty list
      - transaction_ids is not None: returns exactly those rows
        (order not guaranteed to match input) Requested IDs with no matching
        row are reported in missing_ids rather than raising
      - transaction_ids is None: returns up to limit from the 
        last window_minutes (default 30) matching any given
        status/gateway/method (newest first)

    The two modes are mutually exclusive; provide EITHER transaction_ids or filter params
    """
    have_ids = bool(transaction_ids)
    notes: list[str] = []

    filters_given = (
        window_minutes is not None
        or status is not None
        or gateway is not None
        or method is not None
    )
    if have_ids and filters_given:
        raise ValueError(
            "get_transactions accepts either transaction_ids OR filter "
            "params (window_minutes/status/gateway/method), not both. Pass "
            "IDs to look up specific rows, or filters to search."
        )

    # limit is validated/clamped the same way in both modes
    limit, note = validation.clamp_positive_int(
        "limit", limit, default=10, max_value=_MAX_LIMIT
    )
    if note:
        notes.append(note)

    if have_ids:
        if len(transaction_ids) > _MAX_IDS:
            # reject if too many requested IDs
            raise ValueError(
                f"transaction_ids exceeds the cap of {_MAX_IDS} items "
                f"(got {len(transaction_ids)}); rejected rather than "
                f"truncated because dropping requested IDs would break "
                f"grounding; pass at most {_MAX_IDS} IDs per call."
            )
        invalid_ids = validation.find_invalid_uuids(transaction_ids)
        if invalid_ids:
            raise ValueError(
                f"transaction_ids must be valid UUIDs; malformed entries: {invalid_ids}"
            )

        # id mode
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(_IDS_SQL, {"ids": transaction_ids})
        rows = cur.fetchall()
        found_ids = {str(row["transaction_id"]) for row in rows}
        missing_ids = [tid for tid in transaction_ids if tid not in found_ids]
        return {
            "mode": "ids",
            "transaction_ids": transaction_ids,
            "window_minutes": None,
            "status": None,
            "gateway": None,
            "method": None,
            "limit": limit,
            "count": len(rows),
            "rows": [_reshape_row(row) for row in rows],
            "missing_ids": missing_ids,
            "notes": notes,
        }

    if status is not None:
        validation.check_enum("status", status, validation.ALLOWED_STATUS)
    if method is not None:
        validation.check_enum("method", method, validation.ALLOWED_METHOD)

    window_minutes, note = validation.clamp_positive_int(
        "window_minutes", window_minutes, default=30, max_value=_MAX_WINDOW_MINUTES
    )
    if note:
        notes.append(note)

    # filter mode
    cur = conn.cursor(row_factory=dict_row)
    cur.execute(
        _FILTER_SQL,
        {
            "window_minutes": window_minutes,
            "status": status,
            "gateway": gateway,
            "method": method,
            "limit": limit,
        },
    )
    rows = cur.fetchall()
    return {
        "mode": "filter",
        "transaction_ids": None,
        "window_minutes": window_minutes,
        "status": status,
        "gateway": gateway,
        "method": method,
        "limit": limit,
        "count": len(rows),
        "rows": [_reshape_row(row) for row in rows],
        "missing_ids": [],
        "notes": notes,
    }
