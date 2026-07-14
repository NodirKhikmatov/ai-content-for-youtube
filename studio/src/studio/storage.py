"""Cloudflare R2 client (S3-compatible). See blueprint.md Section 5.2.

Requires a bucket created by hand in the Cloudflare dashboard first — this
module has no permission to provision cloud infrastructure on its own.
"""

import boto3
from botocore.client import BaseClient

from studio.config import settings


def get_r2_client() -> BaseClient:
    if not (settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise RuntimeError(
            "R2 credentials missing. Create a bucket + API token in the Cloudflare "
            "dashboard, then fill R2_* in .env (see .env.example)."
        )
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def upload_file(local_path: str, key: str) -> str:
    client = get_r2_client()
    client.upload_file(local_path, settings.r2_bucket_name, key)
    return key
