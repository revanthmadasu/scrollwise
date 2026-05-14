"""Pluggable image generation client.

The default is a stub that returns a deterministic placeholder URL based on a
hash of the prompt. When you wire in a real image backend (a local SDXL or
FLUX server, the Replicate API, an OpenAI image endpoint, etc.), implement
the same interface and swap it in via `get_image_client()`.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol


class ImageClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Return a URL (or local path) for the generated image."""
        ...


class StubImageClient:
    """Returns a deterministic placeholder URL.

    Useful for end-to-end testing the pipeline without spending GPU time.
    Replace with a real client when ready.
    """

    def generate(self, prompt: str) -> str:
        h = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        # picsum gives stable images keyed on the seed; you'll replace this
        return f"https://picsum.photos/seed/{h}/1024/1024"


class LocalSDXLClient:
    """Skeleton for a local SDXL/FLUX HTTP server.

    Most self-hosted image servers expose a simple POST endpoint. Fill in the
    request shape your server expects. This is intentionally not implemented
    so you don't accidentally hit a placeholder endpoint in production.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        raise NotImplementedError(
            "Wire this up to your self-hosted image server. "
            "POST to a generation endpoint, save the bytes to your object "
            "store (MinIO/S3), and return the public URL."
        )


def get_image_client() -> ImageClient:
    backend = os.environ.get("IMAGE_BACKEND", "stub")
    if backend == "stub":
        return StubImageClient()
    elif backend == "local_sdxl":
        base_url = os.environ["IMAGE_BASE_URL"]
        return LocalSDXLClient(base_url=base_url)
    else:
        raise ValueError(f"Unknown IMAGE_BACKEND: {backend}")
