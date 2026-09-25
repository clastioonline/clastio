"""Object storage abstraction: local filesystem (dev) or any S3-compatible bucket (prod)."""

from __future__ import annotations

import asyncio
import mimetypes
import time
from pathlib import Path
from urllib.parse import quote, urlencode

from app.core.config import get_settings
from app.core.security import sign_value


class Storage:
    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    async def get(self, key: str) -> bytes:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError

    def signed_url(self, key: str, filename: str | None = None, ttl: int | None = None) -> str:
        raise NotImplementedError

    async def download_to(self, key: str, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(await self.get(key))
        return path


class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("invalid storage key")
        return p

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_bytes, data)
        return key

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def local_path(self, key: str) -> Path:
        return self._path(key)

    def signed_url(self, key: str, filename: str | None = None, ttl: int | None = None) -> str:
        settings = get_settings()
        exp = int(time.time()) + (ttl or settings.signed_url_ttl_seconds)
        query = {"exp": exp, "sig": sign_value(key, exp)}
        if filename:
            query["fn"] = filename
        return f"/api/v1/files/{quote(key)}?{urlencode(query)}"


class S3Storage(Storage):
    def __init__(self):
        import boto3

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=s.s3_region,
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key_id,
            aws_secret_access_key=s.s3_secret_access_key,
        )

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        ct = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        await asyncio.to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=ct,
            ServerSideEncryption="AES256",
        )
        return key

    async def get(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    async def exists(self, key: str) -> bool:
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    def signed_url(self, key: str, filename: str | None = None, ttl: int | None = None) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=ttl or get_settings().signed_url_ttl_seconds
        )


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage() if s.storage_backend == "s3" else LocalStorage(Path(s.storage_local_dir))
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
