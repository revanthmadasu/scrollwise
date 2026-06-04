"""Pluggable image generation client.

Backends:
  stub        — placeholder URL (dev, no GPU needed)
  bedrock     — Stability AI SDXL on Amazon Bedrock (current POC)
  local_sdxl  — self-hosted SDXL/FLUX server on a separate EC2 (future)

Set IMAGE_BACKEND env var to switch. Images are saved to S3 when using
bedrock or local_sdxl; set IMAGE_S3_BUCKET to your bucket name.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from typing import Protocol


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


class BedrockSDXLClient:
    """Stability AI SDXL via Amazon Bedrock.

    Uses the same IAM role as the LLM client — no separate API key needed.
    Generated images are uploaded to S3 and the public URL is returned.

    Required env vars:
        IMAGE_S3_BUCKET   — S3 bucket to store generated images
        AWS_REGION        — defaults to us-east-1

    Optional env vars:
        IMAGE_SDXL_MODEL  — Bedrock model ID (defaults to stability.stable-diffusion-xl-v1)
    """

    def __init__(
        self,
        bucket: str,
        model: str = "stability.stable-diffusion-xl-v1",
        region: str | None = None,
    ):
        try:
            import boto3
        except ImportError as e:
            raise RuntimeError("boto3 not installed. pip install boto3") from e

        region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.model = model
        self.bucket = bucket
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.s3 = boto3.client("s3", region_name=region)

    def generate(self, prompt: str) -> str:
        # Call Bedrock SDXL
        body = json.dumps({
            "text_prompts": [{"text": prompt, "weight": 1.0}],
            "cfg_scale": 7,
            "steps": 30,
            "width": 1024,
            "height": 1024,
            "samples": 1,
        })
        response = self.bedrock.invoke_model(
            modelId=self.model,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        image_bytes = base64.b64decode(result["artifacts"][0]["base64"])

        # Upload to S3
        key = f"generated-images/{uuid.uuid4().hex}.png"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"


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
            import boto3
            import requests
        except ImportError as e:
            raise RuntimeError("pip install boto3 requests") from e

        self.base_url = base_url.rstrip("/")
        self.bucket = bucket
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._requests = requests
        self._boto3 = boto3

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
        s3 = self._boto3.client("s3", region_name=self.region)
        key = f"generated-images/{uuid.uuid4().hex}.png"
        s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
        )
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"


def get_image_client() -> ImageClient:
    """Factory. Reads IMAGE_BACKEND env var.

    IMAGE_BACKEND=stub         → StubImageClient (default)
    IMAGE_BACKEND=bedrock      → BedrockSDXLClient (needs IMAGE_S3_BUCKET)
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
            "IMAGE_SDXL_MODEL", "stability.stable-diffusion-xl-v1"
        )
        return BedrockSDXLClient(bucket=bucket, model=model)

    elif backend == "local_sdxl":
        base_url = os.environ["IMAGE_BASE_URL"]
        bucket = os.environ.get("IMAGE_S3_BUCKET")
        if not bucket:
            raise RuntimeError("IMAGE_S3_BUCKET env var required for local_sdxl image backend")
        return LocalSDXLClient(base_url=base_url, bucket=bucket)

    else:
        raise ValueError(f"Unknown IMAGE_BACKEND: {backend}")
