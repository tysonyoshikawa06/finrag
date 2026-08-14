"""Embedding interface and local sentence-tansformer

To substitute other embeddings later, add a new subclass and pass it
to write_batch
"""

from abc import ABC, abstractmethod

import numpy as np
from sentence_transformers import SentenceTransformer


class Embedder(ABC):
    """Converts a list of strings into a list of float vectors"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized embedding vector per input text.

        Vectors MUST be L2-normalized so that dot product equals cosine
        similarity (pgvector's <=> operator (cosine distance)
        and the HNSW index both require this)
        """


class LocalEmbedder(Embedder):
    """Wraps all-MiniLM-L6-v2

    Produces 384-dimensional, cosine-normalized vectors. The model file is
    ~80 MB and downloads to the HuggingFace cache (~/.cache/huggingface/) on
    first use; subsequent runs load from disk
    """

    _EXPECTED_DIM = 384

    def __init__(self) -> None:
        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vecs: np.ndarray = self._model.encode(texts, normalize_embeddings=True)
        assert vecs.shape[1] == self._EXPECTED_DIM, (
            f"Model returned {vecs.shape[1]}-dim vectors, expected {self._EXPECTED_DIM}. "
            "Wrong model loaded?"
        )
        return vecs.tolist()
