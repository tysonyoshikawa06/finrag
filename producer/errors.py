"""Error families for the failure-text layer

Each family represents one logical failure reason with multiple textual
variants"""

import itertools
import random

INSUFFICIENT_FUNDS = [
    "insufficient_funds",
    "NSF",
    "ERR_51 insufficient funds",
    "Declined - insufficient funds available",
    "51: INSUFFICIENT FUNDS",
]

DO_NOT_HONOR = [
    "do_not_honor",
    "ERR_05 DO NOT HONOR",
    "05: Do Not Honor",
    "Declined - do not honor",
]

EXPIRED_CARD = [
    "card_expired",
    "ERR_54 expired card",
    "Declined: card expired",
    "54: CARD EXPIRED",
]

INVALID_CVV = [
    "cvv_mismatch",
    "ERR_82 invalid CVC",
    "security code incorrect",
    "CVV2 verification failed",
]

GATEWAY_TIMEOUT = [
    "Gateway timeout after 30000ms upstream={gateway}-7",
    "504 upstream timeout ({gateway})",
    "{gateway}: connection timed out",
    "ETIMEDOUT connecting to {gateway}.internal:443",
    "upstream {gateway} did not respond within 30s",
]

NETWORK_ERROR = [
    "ECONNRESET",
    "upstream connect error, reset before headers. {gateway}:443",
    "network unreachable ({gateway})",
    "TLS handshake failed: {gateway}.internal:443",
]

FRAUD_SUSPECTED = [
    "fraud_suspected",
    "ERR_59 suspected fraud",
    "blocked by risk engine",
    "transaction flagged: high risk score",
]

# List of non-novel error families
ALL_FAMILIES = [
    INSUFFICIENT_FUNDS,
    DO_NOT_HONOR,
    EXPIRED_CARD,
    INVALID_CVV,
    GATEWAY_TIMEOUT,
    NETWORK_ERROR,
    FRAUD_SUSPECTED,
]

# (family, weight) - weights reflect real-world decline frequency.
# Contains error families applicable to all methods
_FAMILY_WEIGHTS_ALL = [
    (INSUFFICIENT_FUNDS, 30),
    (DO_NOT_HONOR, 20),
    (GATEWAY_TIMEOUT, 10),
    (NETWORK_ERROR, 8),
    (FRAUD_SUSPECTED, 7),
]

# Card-only error families
_FAMILY_WEIGHTS_CARD = _FAMILY_WEIGHTS_ALL + [
    (EXPIRED_CARD, 15),
    (INVALID_CVV, 10),
]

_CARD_FAMILIES, _CARD_WEIGHTS = zip(*_FAMILY_WEIGHTS_CARD)
_CARD_CUM_WEIGHTS = list(itertools.accumulate(_CARD_WEIGHTS))

_ALL_FAMILIES, _ALL_WEIGHTS = zip(*_FAMILY_WEIGHTS_ALL)
_ALL_CUM_WEIGHTS = list(itertools.accumulate(_ALL_WEIGHTS))


def generate_error_text(method: str, gateway: str) -> str:
    """Pick a random error family and variant, filling in gateway if templated"""
    if method == "card":
        families, cum_weights = _CARD_FAMILIES, _CARD_CUM_WEIGHTS
    else:
        families, cum_weights = _ALL_FAMILIES, _ALL_CUM_WEIGHTS

    family = random.choices(families, cum_weights=cum_weights, k=1)[0]
    template = random.choice(family)
    return template.format(gateway=gateway)
