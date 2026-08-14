"""Writes batched inserts into transactions and embeddings tables

Write ordering within each batch:
  1. Insert all transactions (idempotent)
  2. Embed the failure subset in one batched model call
  3. Insert embeddings (foreign key is satisfied)

Failed writes rolls back both (no orphaned embeddings)
"""

from datetime import datetime, timezone

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from consumer.config import POSTGRES_DSN

_INSERT_TX_SQL = """
    INSERT INTO transactions
        (transaction_id, event_timestamp, merchant, method, amount,
         status, gateway, error_text, card_bin, ingested_at)
    VALUES
        (%(transaction_id)s, %(event_timestamp)s, %(merchant)s, %(method)s,
         %(amount)s, %(status)s, %(gateway)s, %(error_text)s, %(card_bin)s,
         %(ingested_at)s)
    ON CONFLICT (transaction_id) DO NOTHING
"""

_INSERT_EMB_SQL = """
    INSERT INTO embeddings (transaction_id, embedded_text, embedding, created_at)
    VALUES (%(transaction_id)s, %(embedded_text)s, %(embedding)s, %(created_at)s)
    ON CONFLICT (transaction_id) DO NOTHING
"""


def build_embedding_text(event: dict) -> str:
    """Enrich an error message for better embedding"""
    method = event.get("method", "unknown")
    gateway = event.get("gateway", "unknown")
    error_text = event.get("error_text", "")
    return f"{method} payment via {gateway} failed: {error_text}"


def connect() -> psycopg.Connection:
    """Initialize psycopg connection with vector type"""
    conn = psycopg.connect(POSTGRES_DSN, row_factory=dict_row)
    register_vector(conn)
    return conn


def write_batch(conn: psycopg.Connection, events: list[dict], embedder=None) -> int:
    """Insert a batch of events. Embeds failure events if embedder is provided

    Returns the number of events in the batch (not necessarily rows inserted)
    """
    now = datetime.now(timezone.utc).isoformat()
    for event in events:
        event["ingested_at"] = now

    failure_events = [e for e in events if e.get("error_text")]

    with conn.transaction():
        cur = conn.cursor()

        # Transactions first (foreign key must exist before its embedding row)
        cur.executemany(_INSERT_TX_SQL, events)

        # Embed failures and insert
        if embedder is not None and failure_events:
            texts = [build_embedding_text(e) for e in failure_events]
            vectors = embedder.embed(texts)
            emb_rows = [
                {
                    "transaction_id": e["transaction_id"],
                    "embedded_text": text,
                    "embedding": np.array(vec),
                    "created_at": now,
                }
                for e, text, vec in zip(failure_events, texts, vectors)
            ]
            cur.executemany(_INSERT_EMB_SQL, emb_rows)

    return len(events)
