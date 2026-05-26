"""
File Utilities — save/delete uploaded files, extract audio duration.
Supports local filesystem storage. S3 integration activated via USE_S3=true.
"""

import os
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


# ── Local storage ──────────────────────────────────────────────────────────────

def save_file(file_obj, filename: str, config: dict) -> str:
    """
    Save an uploaded file object to disk (or S3 if configured).
    Returns the stored path / S3 key.
    """
    upload_dir = config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    if config.get("USE_S3"):
        return _save_to_s3(file_obj, filename, config)

    dest = os.path.join(upload_dir, filename)
    file_obj.save(dest)
    logger.info(f"File saved locally: {dest} ({os.path.getsize(dest)} bytes)")
    return dest


def delete_file(file_path: str, config: dict) -> None:
    """Remove a stored file. Skips gracefully if file doesn't exist."""
    if not file_path:
        return

    if config.get("USE_S3"):
        _delete_from_s3(file_path, config)
        return

    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"File deleted: {file_path}")
    else:
        logger.warning(f"File not found for deletion: {file_path}")


def get_file_duration(file_path: str) -> int:
    """
    Use ffprobe to get the duration of an audio/video file in seconds.
    Returns 0 if ffprobe is unavailable or fails.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()))
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        logger.warning(f"Could not determine file duration: {e}")
    return 0


# ── S3 storage (optional) ──────────────────────────────────────────────────────

def _save_to_s3(file_obj, filename: str, config: dict) -> str:
    """Upload file to AWS S3 and return the S3 key."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    s3 = boto3.client(
        "s3",
        aws_access_key_id     = config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = config["AWS_SECRET_KEY"],
        region_name           = config["AWS_REGION"],
    )
    key = f"meetings/{filename}"
    try:
        s3.upload_fileobj(
            file_obj,
            config["AWS_BUCKET_NAME"],
            key,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
        logger.info(f"File uploaded to S3: s3://{config['AWS_BUCKET_NAME']}/{key}")
        return key
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"S3 upload failed: {e}") from e


def _delete_from_s3(key: str, config: dict) -> None:
    import boto3
    s3 = boto3.client(
        "s3",
        aws_access_key_id     = config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = config["AWS_SECRET_KEY"],
        region_name           = config["AWS_REGION"],
    )
    try:
        s3.delete_object(Bucket=config["AWS_BUCKET_NAME"], Key=key)
        logger.info(f"S3 object deleted: {key}")
    except Exception as e:
        logger.warning(f"S3 delete failed: {e}")


def get_s3_presigned_url(key: str, config: dict, expires: int = 3600) -> Optional[str]:
    """Generate a time-limited presigned URL for an S3 object."""
    import boto3
    s3 = boto3.client(
        "s3",
        aws_access_key_id     = config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key = config["AWS_SECRET_KEY"],
        region_name           = config["AWS_REGION"],
    )
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": config["AWS_BUCKET_NAME"], "Key": key},
            ExpiresIn=expires,
        )
    except Exception as e:
        logger.warning(f"Could not generate presigned URL: {e}")
        return None
