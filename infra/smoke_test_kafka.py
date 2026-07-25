"""Produces 5 JSON messages to mock Kafka topic, consumes them back, and verifies round-trip

Run with: uv run python infra/smoke_test_kafka.py
Requires: Kafka running on localhost:29092 (start with 'make up')
"""

import json
import sys
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

BOOTSTRAP_SERVERS = "localhost:29092"
REAL_TOPIC = "transactions" # the app's real topic
SMOKE_TOPIC = "smoke-test" # disposable topic for testing


def wait_for_kafka(timeout=30):
    """Block until Kafka is reachable or timeout expires"""
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            metadata = admin.list_topics(timeout=5)
            if metadata.topics is not None:
                return True
        except Exception:
            time.sleep(1)
    return False


def real_topic_exists():
    """Confirm the app's real topic was created by kafka-init"""
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    metadata = admin.list_topics(timeout=5)
    return REAL_TOPIC in metadata.topics


def ensure_smoke_topic():
    """Create the dedicated smoke-test topic if it doesn't already exist (idempotent)"""
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    future = admin.create_topics([NewTopic(SMOKE_TOPIC, num_partitions=1, replication_factor=1)])[SMOKE_TOPIC]
    try:
        future.result()
    except KafkaException as e:
        if e.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise

def cleanup_smoke_topic():
    """Purge every message from the smoke-test topic so the next run starts clean

    Truncates via delete_records instead of deleting/recreating the topic, so there's
    no create-after-delete race with a future run.
    """
    tp = TopicPartition(SMOKE_TOPIC, 0)
    consumer = Consumer({"bootstrap.servers": BOOTSTRAP_SERVERS, "group.id": f"smoke-test-cleanup-{uuid.uuid4()}"})
    try:
        _low, high = consumer.get_watermark_offsets(tp, timeout=5, cached=False)
    finally:
        consumer.close()

    if high <= 0:
        return # nothing produced yet

    admin = AdminClient({"bootstrap.servers": BOOTSTRAP_SERVERS})
    tp.offset = high
    admin.delete_records([tp])[tp].result()


def make_messages(n=5):
    """Generate n sample transaction messages"""
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "transaction_id": str(uuid.uuid4()),
            "event_timestamp": now,
            "merchant": "smoke_test_merchant",
            "method": "card",
            "amount": round(10.0 + i * 25.50, 2),
            "status": "success",
            "gateway": "stripe-proxy",
            "error_text": None,
            "card_bin": "411111",
        }
        for i in range(n)
    ]


def produce(messages):
    """Send each message as JSON to the smoke-test topic

    producer.produce() is async. producer.flush() blocks until all queued
    messages are delivered (or the timeout expires). The return value is the
    number of messages still in the queue (0 means everything was delivered)
    """
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    for msg in messages:
        producer.produce(
            topic=SMOKE_TOPIC,
            value=json.dumps(msg).encode("utf-8"),
        )

    remaining = producer.flush(timeout=10)
    if remaining > 0:
        print(f"FAIL: {remaining} messages were not delivered")
        sys.exit(1)

    print(f"Produced {len(messages)} messages to '{SMOKE_TOPIC}'")


def consume(expected_ids, timeout=15):
    """Read from the smoke-test topic until every expected transaction_id is seen

    Key settings:
    - group.id: each consumer group tracks its own offsets. We use a random ID
      so this test always reads from scratch (no leftover offset state)
    - auto.offset.reset: "earliest" means start from the first message in the
      topic, not just new ones arriving after we subscribe
    """
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": f"smoke-test-{uuid.uuid4()}",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([SMOKE_TOPIC])

    received = {}
    deadline = time.time() + timeout
    while len(received) < len(expected_ids) and time.time() < deadline:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        event = json.loads(msg.value().decode("utf-8"))
        if event.get("transaction_id") in expected_ids:
            received[event["transaction_id"]] = event

    consumer.close()
    return list(received.values())


def main():
    print(f"Connecting to Kafka at {BOOTSTRAP_SERVERS}...")
    if not wait_for_kafka():
        print("FAIL: Kafka not reachable within 30s")
        sys.exit(1)
    print("Kafka is ready.\n")

    if not real_topic_exists():
        print(f"FAIL: '{REAL_TOPIC}' topic not found (kafka-init may not have run)")
        sys.exit(1)
    print(f"'{REAL_TOPIC}' topic exists.\n")

    ensure_smoke_topic()
    try:
        # Produce
        messages = make_messages(5)
        sent_ids = {m["transaction_id"] for m in messages}
        produce(messages)

        # Consume
        print("Consuming messages...")
        received = consume(expected_ids=sent_ids)
        print(f"Received {len(received)} messages\n")

        recv_ids = {m["transaction_id"] for m in received}

        if sent_ids == recv_ids:
            print("PASS - all 5 messages round-tripped successfully:")
            for msg in received:
                print(f"  {msg['transaction_id'][:8]}... {msg['merchant']:>12}  ${msg['amount']:.2f}")
        else:
            missing = sent_ids - recv_ids
            print("FAIL - message mismatch:")
            print(f"  Not received: {missing}")
            sys.exit(1)
    finally:
        # Cleanup
        cleanup_smoke_topic()


if __name__ == "__main__":
    main()
