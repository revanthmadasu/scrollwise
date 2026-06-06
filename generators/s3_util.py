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


def is_s3_url(url: str) -> bool:
    """True if the URL points at an AWS S3 object (not e.g. a picsum stub URL)."""
    try:
        _parse_s3_url(url)
        return True
    except ValueError:
        return False


def delete_objects(
    urls: list[str], *, s3_client=None, region: str | None = None
) -> int:
    """Delete the S3 objects referenced by the given URLs. Returns count deleted.

    Non-S3 URLs (e.g. stub placeholder URLs) are silently skipped. Keys are
    grouped per bucket and batched (S3 allows up to 1000 per delete call).
    """
    from collections import defaultdict

    by_bucket: dict[str, list[str]] = defaultdict(list)
    for url in urls:
        try:
            bucket, key = _parse_s3_url(url)
        except ValueError:
            continue  # skip non-S3 URLs (stub placeholders, etc.)
        by_bucket[bucket].append(key)

    if not by_bucket:
        return 0

    s3 = s3_client or get_s3_client(region)
    deleted = 0
    for bucket, keys in by_bucket.items():
        for i in range(0, len(keys), 1000):
            chunk = keys[i:i + 1000]
            resp = s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
            )
            deleted += len(chunk) - len(resp.get("Errors", []))
    return deleted


def _parse_s3_url(url: str) -> tuple[str, str]:
    """Parse an AWS S3 URL into (bucket, key). Raises ValueError if not S3."""
    parsed = urlparse(url)
    host = parsed.netloc
    key = parsed.path.lstrip("/")
    if "amazonaws.com" not in host:
        raise ValueError(f"Not an S3 URL: {url}")
    if ".s3" in host:
        # Virtual-hosted: <bucket>.s3.amazonaws.com or <bucket>.s3.<region>.amazonaws.com
        bucket = host.split(".s3")[0]
    elif host.startswith("s3.") or host.startswith("s3-"):
        # Path-style: s3.amazonaws.com/<bucket>/<key>
        bucket, _, key = key.partition("/")
    else:
        raise ValueError(f"Unrecognized S3 URL form: {url}")
    if not bucket or not key:
        raise ValueError(f"Could not parse bucket/key from S3 URL: {url}")
    return bucket, key
