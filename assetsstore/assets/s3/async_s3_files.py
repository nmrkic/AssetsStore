from assetsstore.assets import FileAssets
import os
import sys
import logging
import asyncio
import threading
from pathlib import Path

import aioboto3

logger = logging.getLogger(__name__)


class ProgressPercentage:
    """Async-compatible thread-safe progress callback for S3 transfers.

    Uses threading.Lock since callbacks are executed in background threads
    by boto3's transfer manager, not in the main async event loop.
    """

    def __init__(self, filename: str, size: float):
        self._filename = filename
        self._size = size if size else 1.0
        self._seen_so_far = 0
        # Use threading.Lock because callbacks run in boto3's background threads
        # This is safe because the callback doesn't await anything
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # This method runs in boto3's background threads, not the async event loop
        # So threading.Lock is appropriate here, not asyncio.Lock
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = round((self._seen_so_far / self._size) * 100, 2)

            # Use thread-safe logging (logger is thread-safe)
            logger.info(
                "%s → %s / %s  (%.2f%%)",
                self._filename,
                self._seen_so_far,
                self._size,
                percentage,
            )
            # sys.stdout.flush() is also thread-safe
            sys.stdout.flush()


class AsyncS3Files(FileAssets):
    """Asynchronous S3 helper that mirrors the old FileAssets interface."""

    def __init__(
        self,
        access_key: str | None = os.getenv("ASSET_ACCESS_KEY"),
        secret_key: str | None = os.getenv("ASSET_SECRET_ACCESS_KEY"),
        bucket_name: str | None = os.getenv("ASSET_LOCATION"),
        bucket_region: str | None = os.getenv("ASSET_REGION"),
        local_store: str | None = os.getenv("LOCAL_STORE"),
        endpoint_url: str | None = os.getenv("ASSET_ENDPOINT_URL"),
    ):
        self.aws_access_key_id = access_key
        self.aws_secret_access_key = secret_key
        self.s3_bucket_name = bucket_name
        self.region_name = bucket_region
        self.local_store = local_store or "./"

        # Build kwargs for aioboto3.Session, omit None to leverage default AWS
        session_kwargs = {}
        if self.aws_access_key_id and self.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = self.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = self.aws_secret_access_key
        # Allow region to be optional; if None, AWS SDK will infer from env/IMDS
        if self.region_name:
            session_kwargs["region_name"] = self.region_name

        self._session = aioboto3.Session(**session_kwargs)
        self._endpoint_url = (
            endpoint_url or f"https://s3.{self.region_name}.amazonaws.com"
        )

    async def _client(self):
        """Context-manager helper to obtain an S3 client."""
        return self._session.client("s3", endpoint_url=self._endpoint_url)

    async def check_if_exists(self, path: str) -> bool:
        """Return True if an object exists at *path*."""
        try:
            async with await self._client() as c:
                await c.head_object(Bucket=self.s3_bucket_name, Key=path)
            return True
        except Exception as exc:
            logger.warning(f"Cannot access bucket object {path}: {exc}")
            return False

    async def get_size(self, folder: str):
        """Return total size (bytes) of *folder* in S3, STANDARD storage only."""
        size = 0
        try:
            async with await self._client() as c:
                paginator = c.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self.s3_bucket_name, Prefix=folder
                ):
                    for obj in page.get("Contents", []):
                        if obj.get("StorageClass", "") == "STANDARD":
                            size += obj["Size"]
        except Exception as exc:
            logger.exception(f"Cannot get size for {folder}: {exc}")
            return False
        return size

    async def get_access(
        self,
        filename: str,
        seconds: int = 0,
        short: bool = False,
        download_filename: str = "",
    ):
        """Return a presigned GET url for *filename*."""
        try:
            if not download_filename:
                download_filename = filename

            if short:
                # Simple public link (assuming bucket policy allows it)
                return f"https://{self.s3_bucket_name}.s3.amazonaws.com/{filename}"

            async with await self._client() as c:
                return await c.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": self.s3_bucket_name,
                        "Key": filename,
                        "ResponseContentDisposition": f"attachment;filename={download_filename}",
                    },
                    ExpiresIn=seconds,
                )
        except Exception as exc:
            logger.exception(f"Failed to generate GET link for {filename}: {exc}")
            return False

    async def get_upload_access(self, filename: str, seconds: int = 0):
        """Return a presigned PUT url for *filename*."""
        try:
            async with await self._client() as c:
                return await c.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={"Bucket": self.s3_bucket_name, "Key": filename},
                    ExpiresIn=seconds,
                )
        except Exception as exc:
            logger.exception(f"Failed to generate PUT link for {filename}: {exc}")
            return False

    async def get_folder(self, path: str):
        """Download an entire *path* prefix to the local store."""
        try:
            async with await self._client() as c:
                paginator = c.get_paginator("list_objects_v2")
                tasks = []
                async for page in paginator.paginate(
                    Bucket=self.s3_bucket_name, Prefix=path
                ):
                    for obj in page.get("Contents", []):
                        tasks.append(self.get_file(obj["Key"]))
                if tasks:
                    await asyncio.gather(*tasks)
            return True
        except Exception as exc:
            logger.warning(f"Folder download failed for {path}: {exc}")
            return False

    async def del_folder(self, path: str):
        """Delete every object under *path* prefix."""
        try:
            async with await self._client() as c:
                paginator = c.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self.s3_bucket_name, Prefix=path
                ):
                    for obj in page.get("Contents", []):
                        await self.del_file(obj["Key"])
            return True
        except Exception as exc:
            logger.exception(f"Folder delete failed for {path}: {exc}")
            return False

    async def get_file(self, filename: str):
        """Download *filename* to the local store if it is not already present."""
        try:
            local_path = Path(os.path.realpath(f"{self.local_store}{filename}"))
            if local_path.is_file():
                logger.info("File already exists: %s", local_path)
                return True

            local_path.parent.mkdir(parents=True, exist_ok=True)

            async with await self._client() as c:
                head = await c.head_object(Bucket=self.s3_bucket_name, Key=filename)
                size = head.get("ContentLength", 1)
                progress = ProgressPercentage(filename, size)
                await c.download_file(
                    self.s3_bucket_name,
                    filename,
                    str(local_path),
                    Callback=progress,
                )
            return True
        except Exception as exc:
            logger.exception(f"File download failed for {filename}: {exc}")
            return False

    async def put_file(self, filename: str):
        """Upload *filename* from the local store to S3."""
        try:
            local_path = Path(os.path.realpath(f"{self.local_store}{filename}"))
            size = local_path.stat().st_size
            progress = ProgressPercentage(str(local_path), size)

            async with await self._client() as c:
                await c.upload_file(
                    str(local_path),
                    self.s3_bucket_name,
                    filename,
                    Callback=progress,
                )
            return True
        except Exception as exc:
            logger.exception(f"File upload failed for {filename}: {exc}")
            return False

    async def del_file(self, filename: str, archive: bool = False):
        """Delete or Glacier-archive *filename* in S3."""
        try:
            async with await self._client() as c:
                if archive:
                    await c.copy(
                        {"Bucket": self.s3_bucket_name, "Key": filename},
                        self.s3_bucket_name,
                        filename,
                        ExtraArgs={
                            "StorageClass": "GLACIER",
                            "MetadataDirective": "COPY",
                        },
                    )
                else:
                    await c.delete_object(Bucket=self.s3_bucket_name, Key=filename)
            return True
        except Exception as exc:
            logger.exception(f"File delete failed for {filename}: {exc}")
            return False
