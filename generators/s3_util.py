"""Small S3 helpers shared by the image generator and the post-card renderer.

Keeps the bucket URL format and upload/download logic in one place so the
image client and the renderer don't each reinvent it.
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import urlparse


def get_s3_client(region: str | None = None):
    try:
        import boto3
    except ImportError as e:
        raise RuntimeError("boto3 not installed. pip install boto3") from e
    region = region or os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("s3", region_name=region)


def upload_png(
    data: bytes,
    bucket: str,
    *,
    key_prefix: str = "generated-images",
    s3_client=None,
    region: str | None = None,
) -> str:
    """Upload PNG bytes to S3 and return the public-style URL."""
    s3 = s3_client or get_s3_client(region)
    key = f"{key_prefix}/{uuid.uuid4().hex}.png"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/png")
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def download_object(url: str, *, s3_client=None, region: str | None = None) -> bytes:
    """Fetch the bytes of an object given its https://bucket.s3.amazonaws.com/key URL.

    Uses the S3 API (not plain HTTP) so it works on private buckets.
    """
    bucket, key = _parse_s3_url(url)
    s3 = s3_client or get_s3_client(region)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _parse_s3_url(url: str) -> tuple[str, str]:
    """Parse a virtual-hosted-style S3 URL into (bucket, key)."""
    parsed = urlparse(url)
    host = parsed.netloc
    key = parsed.path.lstrip("/")
    # Virtual-hosted: <bucket>.s3.amazonaws.com or <bucket>.s3.<region>.amazonaws.com
    if ".s3" in host:
        bucket = host.split(".s3")[0]
    elif host.startswith("s3.") or host.startswith("s3-"):
        # Path-style: s3.amazonaws.com/<bucket>/<key>
        bucket, _, key = key.partition("/")
    else:
        bucket = host.split(".")[0]
    if not bucket or not key:
        raise ValueError(f"Could not parse bucket/key from S3 URL: {url}")
    return bucket, key
