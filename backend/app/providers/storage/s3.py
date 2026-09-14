import asyncio
from functools import partial

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


class S3StorageProvider:
    """Works against real S3 and against MinIO (dev) — same API, different
    endpoint_url. See architecture.md §7."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        # Separate client purely for presigned-URL generation — signs against
        # the address the *browser* can reach, not the internal docker
        # hostname the backend itself uses. Never used for actual I/O.
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_public_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )

    async def _run(self, fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    def ensure_bucket(self) -> None:
        """Sync, called once at startup — see app/main.py lifespan."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except (ClientError, BotoCoreError):
            self._client.create_bucket(Bucket=self._bucket)

    async def put_object(self, key: str, data: bytes, *, content_type: str) -> None:
        await self._run(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get_object(self, key: str) -> bytes:
        response = await self._run(self._client.get_object, Bucket=self._bucket, Key=key)
        return response["Body"].read()  # type: ignore[no-any-return]

    async def delete_object(self, key: str) -> None:
        # S3's delete_object is a no-op (not an error) for a missing key —
        # exactly the "tolerate already-gone" behavior callers want.
        await self._run(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def get_presigned_url(self, key: str, *, expires_in: int = 3600) -> str:
        return await self._run(  # type: ignore[no-any-return]
            self._presign_client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def get_presigned_put_url(
        self, key: str, *, content_type: str, expires_in: int = 3600
    ) -> str:
        return await self._run(  # type: ignore[no-any-return]
            self._presign_client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    async def health(self) -> bool:
        try:
            await self._run(self._client.head_bucket, Bucket=self._bucket)
            return True
        except (ClientError, BotoCoreError):
            return False
