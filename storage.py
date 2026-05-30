"""S3-compatible object storage (Railway bucket) for archives, OG images and
submission uploads.

No-op when S3 credentials are absent (local dev / CI), so callers don't need to
guard every use.
"""
from __future__ import annotations

import os

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

_client = None


def enabled() -> bool:
    return bool(S3_ENDPOINT and S3_BUCKET and S3_ACCESS_KEY and S3_SECRET_KEY)


def _s3():
    global _client
    if not enabled():
        return None
    if _client is None:
        import boto3  # lazy import
        _client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
        )
    return _client


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
    """Upload raw bytes. Returns True on success, False if storage is disabled."""
    c = _s3()
    if c is None:
        return False
    c.put_object(Bucket=S3_BUCKET, Key=key, Body=data, ContentType=content_type)
    return True


def put_file(key: str, path: str, content_type: str = "application/octet-stream") -> bool:
    with open(path, "rb") as f:
        return put_bytes(key, f.read(), content_type)
