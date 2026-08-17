"""Semantic (vector) search over failure text for "meaning" questions

Takes an existing psycopg connection and returns a plain
JSON-serializable dict so tests can insert transactions
without disrupting the real data

SQL params are always valided/clamped before being passed in
"""

from consumer.embedder import Embedder
from consumer.search import search
from mcp_server import validation

_MAX_WINDOW_MINUTES = 1440  # 24 hours
_MAX_K = 50
_MAX_QUERY_LEN = 2000


def semantic_search(
    conn,
    embedder: Embedder,
    query: str,
    window_minutes: int = 30,
    gateway: str | None = None,
    k: int = 10,
    exact_scan_threshold: int | None = None,
) -> dict:
    """Find failure-event transactions whose embedded text is closest in meaning to query

    - Finds k nearest embeddings
    - Narrowed down to a single gateway (optional)
    - exact_scan_threshold is to only be used for forcing an exact scan; defaults
      to search.py's settings when None
    """
    notes: list[str] = []

    query, note = validation.check_query_text(query, _MAX_QUERY_LEN)
    if note:
        notes.append(note)

    window_minutes, note = validation.clamp_positive_int(
        "window_minutes", window_minutes, default=30, max_value=_MAX_WINDOW_MINUTES
    )
    if note:
        notes.append(note)

    k, note = validation.clamp_positive_int("k", k, default=10, max_value=_MAX_K)
    if note:
        notes.append(note)

    search_kwargs = dict(
        window=f"{window_minutes} minutes",
        k=k,
        status=None,
        gateway=gateway,
    )
    if exact_scan_threshold is not None:
        search_kwargs["exact_scan_threshold"] = exact_scan_threshold

    rows, path = search(conn, embedder, query, **search_kwargs)

    matches = [
        {
            "transaction_id": str(row["transaction_id"]),
            "similarity": round(1 - row["distance"], 4),
            "embedded_text": row["embedded_text"],
            "event_timestamp": row["event_timestamp"].isoformat(),
            "gateway": row["gateway"],
            "method": row["method"],
            "amount": row["amount"],
            "status": row["status"],
        }
        for row in rows
    ]

    return {
        "query": query,
        "window_minutes": window_minutes,
        "gateway": gateway,
        "k": k,
        "count": len(matches),
        "path": path,
        "matches": matches,
        "notes": notes,
    }
