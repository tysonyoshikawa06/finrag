"""Validation/clamping helpers for the MCP tool params"""

import uuid
from collections.abc import Iterable

# column allowlist for query_stats
ALLOWED_COLUMNS = {"method", "status", "gateway", "merchant"}

# enum allowlists for filter/argument values
ALLOWED_STATUS = {"success", "failure"}
ALLOWED_METHOD = {"card", "ach", "wallet"}
ALLOWED_METRIC = {"count", "failure_rate"}


def require_positive_int(name: str, value: object) -> int:
    """Reject anything that is not a positive int

    Bools are rejected explicitly even though bool is a subclass of int
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")
    return value


def clamp_positive_int(
    name: str, value: int | None, default: int, max_value: int
) -> tuple[int, str | None]:
    """Clamp value to max_value

    Name is the name of the value passed in as to give more information
    to the agent loop
    
    - If value is None, the default is trusted
    - If value is not a positive int, ValueError is propigated
    """
    if value is None:
        return default, None
    value = require_positive_int(name, value)
    if value > max_value:
        return max_value, f"{name} capped at {max_value} (requested {value})"
    return value, None


def check_enum(name: str, value: object, allowed: set[str]) -> None:
    """Raise ValueError if value is not a member of allowed
    
    Name is the name of the value passed in as to give more information
    to the agent loop
    """
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")


def check_allowed_keys(kind: str, keys: Iterable[str], allowed: set[str]) -> None:
    """Raise ValueError if any of keys is not in allowed

    Name is the name of the value passed in as to give more information
    to the agent loop
    """
    bad = sorted(set(keys) - set(allowed))
    if bad:
        raise ValueError(f"{kind} keys must be among {sorted(allowed)}, got {bad}")


def find_invalid_uuids(ids: Iterable[str]) -> list[str]:
    """Return the subset of ids that are not valid UUID strings"""
    invalid = []
    for value in ids:
        try:
            uuid.UUID(value)
        except (ValueError, AttributeError, TypeError):
            invalid.append(value)
    return invalid


def check_query_text(query: str, max_len: int) -> tuple[str, str | None]:
    """Validate free-text query input

    - Empty or whitespace only raises ValueError
    - Strings longer than max_len are truncated and a message is returned
      with the truncated string
    """
    if not query or not query.strip():
        raise ValueError("query must not be empty or whitespace-only")
    if len(query) > max_len:
        note = f"query truncated to {max_len} characters (was {len(query)})"
        return query[:max_len], note
    return query, None
