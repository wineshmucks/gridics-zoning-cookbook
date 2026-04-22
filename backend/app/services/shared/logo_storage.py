"""Jurisdiction-scoped asset storage helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AssetBlob:
    content: bytes
    content_type: str


def _normalized_bucket_name() -> str | None:
    bucket_name = settings.assets_bucket.strip() if settings.assets_bucket else ""
    return bucket_name or None


def _normalized_prefix() -> str:
    prefix = settings.assets_prefix.strip() if settings.assets_prefix else ""
    return prefix.strip("/")


def _s3_client():
    return boto3.client("s3", region_name=settings.aws_region or None)


def is_asset_storage_enabled() -> bool:
    return _normalized_bucket_name() is not None


def _normalized_segment(value: str, *, label: str) -> str:
    candidate = PurePosixPath(value.strip()).name
    if not candidate:
        raise ValueError(f"{label} is required.")
    return candidate


def _asset_object_key(namespace: str, asset_type: str, filename: str) -> str:
    namespace_segment = _normalized_segment(namespace, label="Asset namespace")
    asset_type_segment = _normalized_segment(asset_type, label="Asset type")
    filename_segment = _normalized_segment(filename, label="Asset filename")
    prefix = _normalized_prefix()
    suffix = f"{namespace_segment}/{asset_type_segment}/{filename_segment}"
    return f"{prefix}/{suffix}" if prefix else suffix


def upload_asset(namespace: str, asset_type: str, filename: str, content: bytes, content_type: str) -> bool:
    bucket_name = _normalized_bucket_name()
    if not bucket_name:
        return False

    key = _asset_object_key(namespace, asset_type, filename)
    try:
        _s3_client().put_object(
            Bucket=bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
        return True
    except (BotoCoreError, ClientError):
        logger.exception("Unable to upload asset %s to S3.", key)
        return False


def download_asset(namespace: str, asset_type: str, filename: str) -> AssetBlob | None:
    bucket_name = _normalized_bucket_name()
    if not bucket_name:
        return None

    key = _asset_object_key(namespace, asset_type, filename)
    try:
        response = _s3_client().get_object(Bucket=bucket_name, Key=key)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code") or "")
        if error_code in {"NoSuchKey", "404", "NotFound"}:
            return None
        logger.exception("Unable to download asset %s from S3.", key)
        return None
    except BotoCoreError:
        logger.exception("Unable to download asset %s from S3.", key)
        return None

    body = response.get("Body")
    if body is None:
        return None

    content = body.read()
    content_type = response.get("ContentType") or guess_type(filename)[0] or "application/octet-stream"
    return AssetBlob(content=content, content_type=content_type)


def delete_asset(namespace: str, asset_type: str, filename: str) -> bool:
    bucket_name = _normalized_bucket_name()
    if not bucket_name:
        return False

    key = _asset_object_key(namespace, asset_type, filename)
    try:
        _s3_client().delete_object(Bucket=bucket_name, Key=key)
        return True
    except (BotoCoreError, ClientError):
        logger.exception("Unable to delete asset %s from S3.", key)
        return False


def delete_asset_namespace(namespace: str) -> bool:
    bucket_name = _normalized_bucket_name()
    if not bucket_name:
        return False

    namespace_segment = _normalized_segment(namespace, label="Asset namespace")
    prefix = _normalized_prefix()
    namespace_prefix = f"{prefix}/{namespace_segment}" if prefix else namespace_segment

    deleted_any = False
    continuation_token: str | None = None

    while True:
        list_kwargs: dict[str, str] = {
            "Bucket": bucket_name,
            "Prefix": namespace_prefix,
        }
        if continuation_token:
            list_kwargs["ContinuationToken"] = continuation_token
        try:
            response = _s3_client().list_objects_v2(**list_kwargs)
        except (BotoCoreError, ClientError):
            logger.exception("Unable to list asset namespace %s in S3.", namespace_prefix)
            return deleted_any

        objects = response.get("Contents") or []
        keys = [item.get("Key") for item in objects if isinstance(item, dict) and isinstance(item.get("Key"), str)]
        if keys:
            try:
                _s3_client().delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": [{"Key": key} for key in keys], "Quiet": True},
                )
                deleted_any = True
            except (BotoCoreError, ClientError):
                logger.exception("Unable to delete asset namespace %s in S3.", namespace_prefix)
                return deleted_any

        if not response.get("IsTruncated"):
            return deleted_any

        continuation_token = response.get("NextContinuationToken")
