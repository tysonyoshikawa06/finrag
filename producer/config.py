"""Value pools and distribution constants for the baseline event generator"""

MERCHANTS = [
    "24 Hour Fitness",
    "Anthropic",
    "Fortnite",
    "Cornell University",
    "Foodland Hawaii",
    "Walmart",
    "Sam's Club",
    "Valorant",
    "Costco",
    "LeetCode Premium",
    "LinkedIn Premium",
    "Spotify Premium",
    "Safeway",
    "7-Eleven",
    "United Airlines",
    "Oishii Bowl",
    "2Hollis LLC",
    "Andrea & Co.",
]

GATEWAYS = [
    "stripe-proxy",
    "adyen-gw",
    "braintree-edge",
    "checkout-io",
]

# Realistic 6-digit Visa (4xxxxx) and Mastercard (5xxxxx) BINs
CARD_BINS = [
    "411111",
    "424242",
    "453201",
    "471500",
    "510510",
    "522233",
    "540012",
    "556677",
]

# (method, weight) - card dominates real-world payment mix
METHOD_WEIGHTS = {
    "card": 0.70,
    "ach": 0.20,
    "wallet": 0.10,
}

# Amount ranges per method: (min, max) with log-uniform sampling
AMOUNT_RANGES = {
    "wallet": (1.00, 100.00),
    "card": (5.00, 500.00),
    "ach": (100.00, 10_000.00),
}

FAILURE_RATE = 0.04

KAFKA_BOOTSTRAP = "localhost:29092"
KAFKA_TOPIC = "transactions"