"""Pluggable image generation client.

Backends:
  stub        — placeholder URL (dev, no GPU needed)
  bedrock     — Stability Stable Image Core on Amazon Bedrock (current POC)
  local_sdxl  — self-hosted SDXL/FLUX server on a separate EC2 (future)

Set IMAGE_BACKEND env var to switch. Images are saved to S3 when using
bedrock or local_sdxl; set IMAGE_S3_BUCKET to your bucket name.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Protocol
from generators._logging import get_logger
from generators.s3_util import upload_png
from prompts.templates import (
    IMAGE_BACKGROUND_NEGATIVE_PROMPT,
    IMAGE_BACKGROUND_STYLE,
)

logger = get_logger(__name__)

class ImageClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate an image from a prompt. Returns a public URL."""
        ...


class StubImageClient:
    """Returns a deterministic placeholder URL. No GPU, no API calls.

    Useful for testing the pipeline end-to-end without spending money.
    """

    def generate(self, prompt: str) -> str:
        h = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        return f"https://picsum.photos/seed/{h}/1024/1024"


class BedrockImageClient:
    """Stability Stable Image Core text-to-image via Amazon Bedrock.

    Uses the same IAM role as the LLM client — no separate API key needed.
    Generated images are uploaded to S3 and the public URL is returned.

    The Bedrock region and the S3 region are decoupled on purpose: Stable
    Image Core is only active in some regions (e.g. us-west-2) while your
    bucket / EC2 may live elsewhere (e.g. us-east-1). Invoking Bedrock
    cross-region from us-east-1 is fully supported.

    Required env vars:
        IMAGE_S3_BUCKET     — S3 bucket to store generated images

    Optional env vars:
        IMAGE_BEDROCK_REGION — region to invoke Bedrock in (defaults to us-west-2)
        AWS_REGION           — region of the S3 bucket (defaults to us-east-1)
        IMAGE_BEDROCK_MODEL  — Bedrock model ID (defaults to stability.stable-image-core-v1:1).
                               Ultra (stability.stable-image-ultra-v1:1) and SD3.5
                               (stability.sd3-5-large-v1:0) share this schema.
    """

    def __init__(
        self,
        bucket: str,
        model: str = "stability.stable-image-core-v1:1",
        bedrock_region: str | None = None,
        s3_region: str | None = None,
    ):
        try:
            import boto3
        except ImportError as e:
            raise RuntimeError("boto3 not installed. pip install boto3") from e

        bedrock_region = (
            bedrock_region
            or os.environ.get("IMAGE_BEDROCK_REGION")
            or "us-west-2"
        )
        s3_region = s3_region or os.environ.get("AWS_REGION", "us-east-1")
        logger.info(
            "setting image client",
            extra={
                "bedrock_region": bedrock_region,
                "s3_region": s3_region,
                "model": model,
            },
        )
        self.model = model
        self.bucket = bucket
        self.bedrock = boto3.client("bedrock-runtime", region_name=bedrock_region)
        self.s3 = boto3.client("s3", region_name=s3_region)

    def generate(self, prompt: str) -> str:
        # Steer every image toward a quiet, text-friendly background.
        styled_prompt = f"{prompt}, {IMAGE_BACKGROUND_STYLE}"

        # Call Bedrock (Stability Stable Image Core / Ultra / SD3.5 schema).
        # 4:5 portrait so the background fills the post card without cropping.
        body = json.dumps({
            "prompt": styled_prompt,
            "negative_prompt": IMAGE_BACKGROUND_NEGATIVE_PROMPT,
            "mode": "text-to-image",
            "aspect_ratio": "4:5",
            "output_format": "png",
        })
        response = self.bedrock.invoke_model(
            modelId=self.model,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())

        # Stability returns a per-image finish reason; surface content filtering
        # instead of silently uploading an empty/blank image.
        finish_reasons = result.get("finish_reasons") or [None]
        if finish_reasons[0] is not None:
            raise RuntimeError(
                f"Stable Image Core did not return an image "
                f"(finish_reason={finish_reasons[0]!r}) for prompt: {prompt!r}"
            )

        image_bytes = base64.b64decode(result["images"][0])
        return upload_png(
            image_bytes, self.bucket, key_prefix="generated-images", s3_client=self.s3
        )


class LocalSDXLClient:
    """Self-hosted SDXL/FLUX server on a separate EC2 instance.

    Point IMAGE_BASE_URL at your EC2's HTTP server (e.g. a ComfyUI or
    Automatic1111 instance). Images are uploaded to S3 after generation.

    Expected server contract:
        POST /generate
        Body: {"prompt": "..."}
        Response: {"image_base64": "..."}  OR  {"image_url": "..."}
    """

    def __init__(self, base_url: str, bucket: str, region: str | None = None):
        try:
            import requests
        except ImportError as e:
            raise RuntimeError("pip install boto3 requests") from e

        self.base_url = base_url.rstrip("/")
        self.bucket = bucket
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._requests = requests

    def generate(self, prompt: str) -> str:
        response = self._requests.post(
            f"{self.base_url}/generate",
            json={"prompt": prompt},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        # Support servers that return a URL directly
        if "image_url" in data:
            return data["image_url"]

        # Otherwise expect base64 and upload to S3
        image_bytes = base64.b64decode(data["image_base64"])
        return upload_png(
            image_bytes, self.bucket, key_prefix="generated-images", region=self.region
        )


def get_image_client() -> ImageClient:
    """Factory. Reads IMAGE_BACKEND env var.

    IMAGE_BACKEND=stub         → StubImageClient (default)
    IMAGE_BACKEND=bedrock      → BedrockImageClient (needs IMAGE_S3_BUCKET)
    IMAGE_BACKEND=local_sdxl   → LocalSDXLClient  (needs IMAGE_BASE_URL + IMAGE_S3_BUCKET)
    """
    backend = os.environ.get("IMAGE_BACKEND", "stub")

    if backend == "stub":
        return StubImageClient()

    elif backend == "bedrock":
        bucket = os.environ.get("IMAGE_S3_BUCKET")
        if not bucket:
            raise RuntimeError("IMAGE_S3_BUCKET env var required for bedrock image backend")
        model = os.environ.get(
            "IMAGE_BEDROCK_MODEL", "stability.stable-image-core-v1:1"
        )
        return BedrockImageClient(bucket=bucket, model=model)

    elif backend == "local_sdxl":
        base_url = os.environ["IMAGE_BASE_URL"]
        bucket = os.environ.get("IMAGE_S3_BUCKET")
        if not bucket:
            raise RuntimeError("IMAGE_S3_BUCKET env var required for local_sdxl image backend")
        return LocalSDXLClient(base_url=base_url, bucket=bucket)

    else:
        raise ValueError(f"Unknown IMAGE_BACKEND: {backend}")
