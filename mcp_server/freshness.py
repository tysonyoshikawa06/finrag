"""Ingest-lag freshness for the MCP system_freshness tool
allowing the LLM to verify citaton recency
"""

from consumer.freshness import query_freshness
from mcp_server import validation

_MAX_WINDOW_MINUTES = 60


def system_freshness(window_minutes: int = 5) -> dict:
    """Report ingest-lag percentiles over the last window_minutes

    Calls consumer.freshness.query_freshness() with window_minutes translated
    to an interval string and reshapes its result
    """
    notes: list[str] = []
    window_minutes, note = validation.clamp_positive_int(
        "window_minutes", window_minutes, default=5, max_value=_MAX_WINDOW_MINUTES
    )
    if note:
        notes.append(note)

    stats = query_freshness(window=f"{window_minutes} minutes")

    if stats is None:
        return {
            "window_minutes": window_minutes,
            "event_count": 0,
            "p50_seconds": None,
            "p95_seconds": None,
            "p99_seconds": None,
            "max_seconds": None,
            "human_readable": (
                f"No events in the last {window_minutes} minutes — "
                "freshness cannot be computed."
            ),
            "notes": notes,
        }

    p50 = round(stats["p50"], 1)
    p95 = round(stats["p95"], 1)
    p99 = round(stats["p99"], 1)
    max_seconds = round(stats["max"], 1)
    event_count = stats["event_count"]

    return {
        "window_minutes": window_minutes,
        "event_count": event_count,
        "p50_seconds": p50,
        "p95_seconds": p95,
        "p99_seconds": p99,
        "max_seconds": max_seconds,
        "human_readable": (
            f"Data is current as of ~{p50}s (p50) over the last "
            f"{window_minutes} minutes ({event_count:,} events)."
        ),
        "notes": notes,
    }
