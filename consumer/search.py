"""Vector similarity over embeddings + structured SQL filters

Run with: make search-demo "<query>"
"""

import numpy as np

from consumer.db import connect
from consumer.embedder import Embedder, LocalEmbedder

# HNSW search above this threshold, as benefits over exact scan appear
EXACT_SCAN_THRESHOLD = 50_000

_COUNT_SQL = """
    SELECT count(*)
    FROM embeddings e
    JOIN transactions t ON t.transaction_id = e.transaction_id
    WHERE t.event_timestamp >= now() - %(window)s::interval
      AND (%(status)s::text IS NULL OR t.status = %(status)s)
      AND (%(gateway)s::text IS NULL OR t.gateway = %(gateway)s)
"""

_SEARCH_SQL = """
    SELECT
        t.transaction_id,
        e.embedded_text,
        t.event_timestamp,
        t.gateway,
        t.method,
        t.status,
        t.amount::float8 AS amount,
        e.embedding <=> %(query_vec)s AS distance
    FROM embeddings e
    JOIN transactions t ON t.transaction_id = e.transaction_id
    WHERE t.event_timestamp >= now() - %(window)s::interval
      AND (%(status)s::text IS NULL OR t.status = %(status)s)
      AND (%(gateway)s::text IS NULL OR t.gateway = %(gateway)s)
    ORDER BY e.embedding <=> %(query_vec)s
    LIMIT %(k)s
"""


def _count_candidates(conn, window: str, status: str | None, gateway: str | None) -> int:
    cur = conn.cursor()
    cur.execute(_COUNT_SQL, {"window": window, "status": status, "gateway": gateway})
    return cur.fetchone()["count"]


def search(
    conn,
    embedder: Embedder,
    query: str,
    window: str = "1 hour",
    k: int = 5,
    status: str | None = None,
    gateway: str | None = None,
    exact_scan_threshold: int = EXACT_SCAN_THRESHOLD,
) -> tuple[list[dict], str]:
    """Embed query and return the k nearest failure embeddings within window

    Returns (rows, path) where path is "exact" or "hnsw". path is chosen by
    query count after filters are applied
    """
    query_vec = np.array(embedder.embed([query])[0])
    params = {
        "query_vec": query_vec,
        "window": window,
        "status": status,
        "gateway": gateway,
        "k": k,
    }

    candidate_count = _count_candidates(conn, window, status, gateway)
    path = "exact" if candidate_count <= exact_scan_threshold else "hnsw"

    cur = conn.cursor()
    with conn.transaction():
        if path == "exact":
            # SET LOCAL only lasts for per transaction (HNSW stays available for later)
            cur.execute("SET LOCAL enable_indexscan = off")
            cur.execute("SET LOCAL enable_bitmapscan = off")
        cur.execute(_SEARCH_SQL, params)
        rows = cur.fetchall()

    return rows, path


def _format_result(rank: int, row: dict) -> str:
    ts = str(row["event_timestamp"])[:19]
    return (
        f"  [{rank}] distance={row['distance']:.3f}  {ts}  "
        f"{row['transaction_id']}\n"
        f"       {row['embedded_text']}"
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Hybrid semantic + structured search demo")
    parser.add_argument("query", help="Natural-language query, e.g. 'connection timed out'")
    parser.add_argument("--window", default="1 hour", help="e.g. '1 hour', '10 minutes'")
    parser.add_argument("--k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--status", default=None, help="Filter to a status, e.g. 'failure'")
    parser.add_argument("--gateway", default=None, help="Filter to a gateway")
    args = parser.parse_args()

    print("Loading model...")
    embedder = LocalEmbedder()

    conn = connect()
    try:
        rows, path = search(
            conn,
            embedder,
            args.query,
            window=args.window,
            k=args.k,
            status=args.status,
            gateway=args.gateway,
        )
    finally:
        conn.close()

    print(f'\nQuery: "{args.query}"  (window={args.window}, k={args.k}, path={path})\n')
    if not rows:
        print("  No matches in window.")
    else:
        for i, row in enumerate(rows, start=1):
            print(_format_result(i, row))


if __name__ == "__main__":
    main()
