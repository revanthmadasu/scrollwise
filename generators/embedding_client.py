"""Embedding client for similarity dedup.

The default is a deterministic hash-based pseudo-embedding (fine for getting
the pipeline running). When you're ready for real semantic dedup, swap in
Voyage, Cohere, or a self-hosted bge / nomic-embed model.

Dimension is 1024 to match what the feed service's pgvector column will expect.
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from typing import Protocol

EMBEDDING_DIM = 1024


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class HashEmbeddingClient:
    """Deterministic pseudo-embedding from SHA-256.

    Not semantically meaningful, but stable: identical text -> identical
    vector. Useful for testing the pipeline. Cosine similarity between
    different texts will be near zero, which is fine for dev.
    """

    def embed(self, text: str) -> list[float]:
        # Expand the hash to fill EMBEDDING_DIM floats in [-1, 1]
        floats: list[float] = []
        counter = 0
        while len(floats) < EMBEDDING_DIM:
            h = hashlib.sha256(f"{text}:{counter}".encode()).digest()
            # 32 bytes -> 8 floats
            for i in range(0, 32, 4):
                u32 = struct.unpack("<I", h[i:i + 4])[0]
                floats.append((u32 / 0xFFFFFFFF) * 2 - 1)
                if len(floats) >= EMBEDDING_DIM:
                    break
            counter += 1
        # L2 normalize for cosine similarity
        norm = math.sqrt(sum(f * f for f in floats))
        return [f / norm for f in floats] if norm > 0 else floats


class VoyageEmbeddingClient:
    """Real semantic embeddings via Voyage AI."""

    def __init__(self, model: str = "voyage-3"):
        try:
            import voyageai
        except ImportError as e:
            raise RuntimeError("voyageai not installed. pip install voyageai") from e
        self.client = voyageai.Client()
        self.model = model

    def embed(self, text: str) -> list[float]:
        result = self.client.embed([text], model=self.model)
        return result.embeddings[0]


def get_embedding_client() -> EmbeddingClient:
    backend = os.environ.get("EMBEDDING_BACKEND", "hash")
    if backend == "hash":
        return HashEmbeddingClient()
    elif backend == "voyage":
        return VoyageEmbeddingClient(
            model=os.environ.get("EMBEDDING_MODEL", "voyage-3")
        )
    else:
        raise ValueError(f"Unknown EMBEDDING_BACKEND: {backend}")
