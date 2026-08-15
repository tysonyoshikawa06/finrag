"""Embed example error strings and print the cosine-similarity matrix

Run with: make embed-demo"""

import numpy as np

from consumer.embedder import LocalEmbedder

EXAMPLES = [
    "insufficient_funds",
    "NSF",
    "not sufficient funds available",
    "Gateway timeout after 30000ms upstream=stripe-proxy-7",
    "card expired",
]


def main() -> None:
    print("Loading all-MiniLM-L6-v2 (downloads ~80 MB on first run, then cached)...\n")
    embedder = LocalEmbedder()

    vecs = np.array(embedder.embed(EXAMPLES))
    # vectors are L2-normalised, so dot product == cosine similarity.
    sim: np.ndarray = vecs @ vecs.T

    n = len(EXAMPLES)

    print("Cosine-similarity matrix (1.0 = same meaning, 0.0 = unrelated):\n")

    print("    " + "".join(f"  [{j}]" for j in range(n)))

    for i in range(n):
        row = "".join(f"  {sim[i, j]:.2f}" for j in range(n))
        print(f"[{i}]{row}")

    print()
    for i, label in enumerate(EXAMPLES):
        print(f"[{i}] {label}")

    print("\nExpected: [0]<->[2] >= 0.70 (same concept); [1]=NSF scores lower (ambiguous alone)")
    print("Cross-group [0-2] vs [3,4] < 0.25  |  enrichment (Step 9B) fixes NSF's low score")


if __name__ == "__main__":
    main()
