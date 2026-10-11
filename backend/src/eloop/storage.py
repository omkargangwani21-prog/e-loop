"""Image storage: S3 presigned POST in AWS mode, a directory on disk in local mode."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
BEDROCK_FORMATS = {"jpg": "jpeg", "png": "png", "webp": "webp"}
_KEY_RE = re.compile(r"^uploads/\d{4}/\d{2}/[0-9a-f]{32}\.(jpg|png|webp)$")


def is_valid_key(key: str) -> bool:
    """Only keys we minted ourselves are accepted; blocks traversal and arbitrary-object access."""
    return bool(_KEY_RE.fullmatch(key))


def image_format(key: str) -> str:
    return BEDROCK_FORMATS[key.rsplit(".", 1)[-1]]


def new_key(content_type: str, now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return f"uploads/{moment:%Y}/{moment:%m}/{uuid.uuid4().hex}.{EXTENSIONS[content_type]}"


@dataclass(frozen=True, slots=True)
class UploadTicket:
    url: str
    fields: dict[str, str]
    key: str


class Storage(Protocol):
    def create_upload(self, content_type: str) -> UploadTicket: ...
    def exists(self, key: str) -> bool: ...
    def read(self, key: str) -> bytes: ...


class S3Storage:
    """Browser uploads directly to S3 with a size- and type-constrained presigned POST."""

    def __init__(self, client: Any, bucket: str, max_bytes: int, expires_s: int = 300) -> None:
        self._client = client
        self._bucket = bucket
        self._max_bytes = max_bytes
        self._expires_s = expires_s

    def create_upload(self, content_type: str) -> UploadTicket:
        key = new_key(content_type)
        post = self._client.generate_presigned_post(
            Bucket=self._bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                ["content-length-range", 1, self._max_bytes],
                {"Content-Type": content_type},
            ],
            ExpiresIn=self._expires_s,
        )
        return UploadTicket(url=post["url"], fields=post["fields"], key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def read(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()


class LocalStorage:
    """Development stand-in. The dev server receives the upload at `/local-uploads`."""

    def __init__(self, directory: str | Path, max_bytes: int) -> None:
        self._root = Path(directory).resolve()
        self._max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def create_upload(self, content_type: str) -> UploadTicket:
        key = new_key(content_type)
        return UploadTicket(url="/api/local-uploads", fields={"key": key}, key=key)

    def _path(self, key: str) -> Path:
        if not is_valid_key(key):
            raise ValueError("invalid storage key")
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError("invalid storage key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()
