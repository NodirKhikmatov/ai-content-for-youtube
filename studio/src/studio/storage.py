"""Cloudflare R2 client (S3-compatible). See blueprint.md Section 5.2.

Requires a bucket created by hand in the Cloudflare dashboard first — this
module has no permission to provision cloud infrastructure on its own.
"""

import logging
from pathlib import Path

import boto3
from botocore.client import BaseClient

from studio.config import settings

log = logging.getLogger(__name__)

_r2_client: BaseClient | None = None


def get_r2_client() -> BaseClient:
    global _r2_client
    if _r2_client is not None:
        return _r2_client
    if not (settings.r2_account_id and settings.r2_access_key_id and settings.r2_secret_access_key):
        raise RuntimeError(
            "R2 credentials missing. Create a bucket + API token in the Cloudflare "
            "dashboard, then fill R2_* in .env (see .env.example)."
        )
    _r2_client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )
    return _r2_client


def upload_file(local_path: str, key: str) -> str:
    client = get_r2_client()
    client.upload_file(local_path, settings.r2_bucket_name, key)
    return key


def best_effort_upload(local_path: Path, r2_key: str) -> bool:
    """Every media agent (Voice Synthesis, Video Assembly, Subtitle) treats
    R2 as best-effort persistence, not a gate — local disk is what state/DB
    actually track during a run (see graph.py's module docstring on why
    resume doesn't extend past script_writer). A failed or unconfigured
    upload is logged and skipped, never raised."""
    try:
        upload_file(str(local_path), r2_key)
        return True
    except Exception as exc:
        log.warning("R2 upload skipped for %s: %s", r2_key, exc)
        return False
