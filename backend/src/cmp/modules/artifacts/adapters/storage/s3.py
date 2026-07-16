"""Governed S3-compatible object storage with KMS, versioning, and Object Lock."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
from collections.abc import AsyncIterable, AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any

from cmp.modules.artifacts.domain.content import ArtifactIntegrityError, StoredObject
from cmp.modules.artifacts.domain.uploads import (
    CompletedObject,
    InvalidUpload,
    ObjectStoreError,
    StoredPart,
)

_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_OWNER = re.compile(r"^[0-9]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class S3GovernancePolicy:
    bucket: str
    kms_key_id: str
    retention_days: int
    retention_mode: str = "COMPLIANCE"
    prefix: str = "cmp"
    expected_bucket_owner: str | None = None
    part_size_bytes: int = 8 * 1024 * 1024

    def __post_init__(self) -> None:
        if _BUCKET.fullmatch(self.bucket) is None:
            raise ValueError("S3 bucket name is invalid")
        if not self.kms_key_id or self.kms_key_id != self.kms_key_id.strip():
            raise ValueError("S3 KMS key identity is required")
        if not 1 <= self.retention_days <= 36_500:
            raise ValueError("S3 retention must be between 1 and 36500 days")
        if self.retention_mode not in {"COMPLIANCE", "GOVERNANCE"}:
            raise ValueError("S3 retention mode must be COMPLIANCE or GOVERNANCE")
        safe = self._safe_path(self.prefix)
        if safe.as_posix() != self.prefix:
            raise ValueError("S3 object prefix is not canonical")
        if (
            self.expected_bucket_owner is not None
            and _OWNER.fullmatch(self.expected_bucket_owner) is None
        ):
            raise ValueError("S3 expected bucket owner must be a 12-digit account ID")
        if not 5 * 1024 * 1024 <= self.part_size_bytes <= 5 * 1024 * 1024 * 1024:
            raise ValueError("S3 multipart part size is outside the supported range")

    @staticmethod
    def _safe_path(value: str) -> PurePosixPath:
        if "\\" in value or "\x00" in value:
            raise ValueError("S3 path contains a forbidden separator")
        path = PurePosixPath(value.strip("/"))
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("S3 path is unsafe")
        return path


class S3GovernedObjectStore:
    """Implement Artifact ports without exposing SDK types to domain/application code."""

    def __init__(
        self,
        client: Any,
        policy: S3GovernancePolicy,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._policy = policy
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _safe_key(value: str) -> PurePosixPath:
        try:
            return S3GovernancePolicy._safe_path(value)
        except ValueError as error:
            raise ObjectStoreError("object key is unsafe") from error

    def _remote_key(self, logical_key: str) -> str:
        key = self._safe_key(logical_key)
        return f"{self._policy.prefix}/{key.as_posix()}"

    def _owner(self) -> dict[str, str]:
        return (
            {"ExpectedBucketOwner": self._policy.expected_bucket_owner}
            if self._policy.expected_bucket_owner is not None
            else {}
        )

    def _encryption(self) -> dict[str, Any]:
        return {
            "BucketKeyEnabled": True,
            "SSEKMSKeyId": self._policy.kms_key_id,
            "ServerSideEncryption": "aws:kms",
        }

    def _retention(self) -> dict[str, Any]:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ObjectStoreError("S3 retention clock must be timezone-aware")
        return {
            "ObjectLockMode": self._policy.retention_mode,
            "ObjectLockRetainUntilDate": now + timedelta(days=self._policy.retention_days),
        }

    @staticmethod
    def _etag(response: Mapping[str, Any]) -> str:
        value = response.get("ETag")
        if not isinstance(value, str) or not value.strip('"'):
            raise ObjectStoreError("S3 response omitted object ETag")
        return value.strip('"')

    @staticmethod
    def _version(response: Mapping[str, Any]) -> str:
        value = response.get("VersionId")
        if not isinstance(value, str) or not value:
            raise ObjectStoreError("S3 response omitted required object version ID")
        return value

    @staticmethod
    def _error_code(error: Exception) -> str | None:
        response = getattr(error, "response", None)
        if not isinstance(response, dict):
            return None
        detail = response.get("Error")
        code = detail.get("Code") if isinstance(detail, dict) else None
        return str(code) if code is not None else None

    @classmethod
    def _missing(cls, error: Exception) -> bool:
        return cls._error_code(error) in {"404", "NoSuchKey", "NotFound", "NoSuchVersion"}

    def validate_bucket_governance(self) -> dict[str, Any]:
        """Fail closed unless versioning, Object Lock, and default SSE-KMS are active."""

        try:
            versioning = self._client.get_bucket_versioning(
                Bucket=self._policy.bucket, **self._owner()
            )
            lock = self._client.get_object_lock_configuration(
                Bucket=self._policy.bucket, **self._owner()
            )
            encryption = self._client.get_bucket_encryption(
                Bucket=self._policy.bucket, **self._owner()
            )
        except Exception as error:
            raise ObjectStoreError("S3 bucket governance inspection failed") from error
        if versioning.get("Status") != "Enabled":
            raise ObjectStoreError("S3 bucket versioning must be enabled")
        lock_configuration = lock.get("ObjectLockConfiguration")
        if (
            not isinstance(lock_configuration, dict)
            or lock_configuration.get("ObjectLockEnabled") != "Enabled"
        ):
            raise ObjectStoreError("S3 Object Lock must be enabled")
        configuration = encryption.get("ServerSideEncryptionConfiguration")
        rules = configuration.get("Rules") if isinstance(configuration, dict) else None
        matched = False
        if isinstance(rules, list):
            for rule in rules:
                default = (
                    rule.get("ApplyServerSideEncryptionByDefault")
                    if isinstance(rule, dict)
                    else None
                )
                if (
                    isinstance(default, dict)
                    and default.get("SSEAlgorithm") == "aws:kms"
                    and default.get("KMSMasterKeyID") == self._policy.kms_key_id
                ):
                    matched = True
        if not matched:
            raise ObjectStoreError("S3 bucket default encryption must use the configured KMS key")
        return {
            "bucket_sha256": hashlib.sha256(self._policy.bucket.encode()).hexdigest(),
            "kms_key_id_sha256": hashlib.sha256(self._policy.kms_key_id.encode()).hexdigest(),
            "object_lock_enabled": True,
            "retention_days": self._policy.retention_days,
            "retention_mode": self._policy.retention_mode,
            "versioning": "Enabled",
        }

    async def initiate(self, object_key: str, media_type: str) -> str:
        remote = self._remote_key(object_key)
        if not media_type or len(media_type) > 255:
            raise ObjectStoreError("object media type is invalid")
        try:
            response = await asyncio.to_thread(
                self._client.create_multipart_upload,
                Bucket=self._policy.bucket,
                Key=remote,
                ContentType=media_type,
                ChecksumAlgorithm="SHA256",
                **self._encryption(),
                **self._owner(),
            )
        except Exception as error:
            raise ObjectStoreError("S3 failed to initiate multipart upload") from error
        upload_id = response.get("UploadId")
        if not isinstance(upload_id, str) or not upload_id:
            raise ObjectStoreError("S3 multipart initiation omitted upload identity")
        return upload_id

    async def upload_part(
        self,
        *,
        object_key: str,
        upload_id: str,
        part_number: int,
        chunks: AsyncIterable[bytes],
        expected_size: int,
    ) -> StoredPart:
        remote = self._remote_key(object_key)
        if not upload_id or not 1 <= part_number <= 10_000 or expected_size <= 0:
            raise ObjectStoreError("S3 multipart part policy is invalid")
        body = bytearray()
        digest = hashlib.sha256()
        async for chunk in chunks:
            if not isinstance(chunk, bytes):
                raise ObjectStoreError("upload stream yielded non-byte content")
            body.extend(chunk)
            digest.update(chunk)
            if len(body) > expected_size:
                raise InvalidUpload("multipart part size differs from its manifest")
        if len(body) != expected_size:
            raise InvalidUpload("multipart part size differs from its manifest")
        sha256 = digest.hexdigest()
        try:
            response = await asyncio.to_thread(
                self._client.upload_part,
                Bucket=self._policy.bucket,
                Key=remote,
                UploadId=upload_id,
                PartNumber=part_number,
                Body=bytes(body),
                ChecksumSHA256=base64.b64encode(bytes.fromhex(sha256)).decode("ascii"),
                **self._owner(),
            )
        except Exception as error:
            raise ObjectStoreError("S3 failed to upload multipart part") from error
        return StoredPart(part_number, expected_size, sha256, self._etag(response))

    async def complete(
        self,
        *,
        object_key: str,
        upload_id: str,
        parts: tuple[StoredPart, ...],
    ) -> CompletedObject:
        remote = self._remote_key(object_key)
        if not parts or tuple(part.part_number for part in parts) != tuple(
            range(1, len(parts) + 1)
        ):
            raise ObjectStoreError("S3 multipart completion requires ordered contiguous parts")
        request_parts = [
            {
                "ChecksumSHA256": base64.b64encode(bytes.fromhex(part.sha256)).decode("ascii"),
                "ETag": part.etag,
                "PartNumber": part.part_number,
            }
            for part in parts
        ]
        try:
            response = await asyncio.to_thread(
                self._client.complete_multipart_upload,
                Bucket=self._policy.bucket,
                Key=remote,
                UploadId=upload_id,
                MultipartUpload={"Parts": request_parts},
                **self._owner(),
            )
            sha256, size = await asyncio.to_thread(self._digest_remote, remote)
        except Exception as error:
            if isinstance(error, ObjectStoreError):
                raise
            raise ObjectStoreError("S3 failed to complete multipart upload") from error
        expected_size = sum(part.size_bytes for part in parts)
        if size != expected_size:
            raise ObjectStoreError("S3 multipart object size differs from its manifest")
        return CompletedObject(object_key, size, sha256, self._etag(response))

    async def abort(self, *, object_key: str, upload_id: str) -> None:
        remote = self._remote_key(object_key)
        try:
            await asyncio.to_thread(
                self._client.abort_multipart_upload,
                Bucket=self._policy.bucket,
                Key=remote,
                UploadId=upload_id,
                **self._owner(),
            )
        except Exception as error:
            if self._error_code(error) == "NoSuchUpload":
                return
            raise ObjectStoreError("S3 failed to abort multipart upload") from error

    async def stage_bytes(
        self,
        *,
        object_key: str,
        value: bytes,
        media_type: str,
    ) -> StoredObject:
        if not object_key.startswith("staging/") or not value or not media_type:
            raise ObjectStoreError("derived bytes require a non-empty staging object")
        digest = hashlib.sha256(value).hexdigest()
        existing = await self.inspect(object_key)
        if existing is not None:
            if existing.sha256 != digest or existing.size_bytes != len(value):
                raise ObjectStoreError("staging object already contains different bytes")
            return existing
        remote = self._remote_key(object_key)
        try:
            response = await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._policy.bucket,
                Key=remote,
                Body=value,
                ContentType=media_type,
                ChecksumAlgorithm="SHA256",
                Metadata={"cmp-sha256": digest},
                IfNoneMatch="*",
                **self._encryption(),
                **self._owner(),
            )
        except Exception as error:
            replay = await self.inspect(object_key)
            if replay is not None and replay.sha256 == digest and replay.size_bytes == len(value):
                return replay
            raise ObjectStoreError("S3 failed to stage derived object") from error
        return StoredObject(
            object_key,
            len(value),
            digest,
            self._etag(response),
            self._version(response),
        )

    async def stage_stream(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
        media_type: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject:
        if (
            not object_key.startswith("staging/")
            or _SHA256.fullmatch(expected_sha256) is None
            or expected_size_bytes <= 0
        ):
            raise ObjectStoreError("derived stream evidence is invalid")
        existing = await self.inspect(object_key)
        if existing is not None:
            if existing.sha256 != expected_sha256 or existing.size_bytes != expected_size_bytes:
                raise ObjectStoreError("staging object already contains different bytes")
            return existing
        upload_id = await self.initiate(object_key, media_type)
        buffer = bytearray()
        digest = hashlib.sha256()
        observed = 0
        parts: list[StoredPart] = []

        async def value_chunks(value: bytes) -> AsyncIterator[bytes]:
            yield value

        try:
            async for chunk in chunks:
                if not isinstance(chunk, bytes) or not chunk:
                    raise ObjectStoreError("derived stream chunks must be non-empty bytes")
                digest.update(chunk)
                observed += len(chunk)
                if observed > expected_size_bytes:
                    raise ObjectStoreError("derived stream exceeds its declared size")
                remaining = memoryview(chunk)
                while remaining:
                    capacity = self._policy.part_size_bytes - len(buffer)
                    consumed = min(capacity, len(remaining))
                    buffer.extend(remaining[:consumed])
                    remaining = remaining[consumed:]
                    if len(buffer) == self._policy.part_size_bytes:
                        part_value = bytes(buffer)
                        buffer.clear()
                        parts.append(
                            await self.upload_part(
                                object_key=object_key,
                                upload_id=upload_id,
                                part_number=len(parts) + 1,
                                chunks=value_chunks(part_value),
                                expected_size=len(part_value),
                            )
                        )
            if buffer:
                part_value = bytes(buffer)
                parts.append(
                    await self.upload_part(
                        object_key=object_key,
                        upload_id=upload_id,
                        part_number=len(parts) + 1,
                        chunks=value_chunks(part_value),
                        expected_size=len(part_value),
                    )
                )
            if observed != expected_size_bytes or digest.hexdigest() != expected_sha256:
                raise ObjectStoreError("derived stream differs from its declared digest or size")
            completed = await self.complete(
                object_key=object_key, upload_id=upload_id, parts=tuple(parts)
            )
        except Exception as error:
            try:
                await self.abort(object_key=object_key, upload_id=upload_id)
            except ObjectStoreError as abort_error:
                error.add_note(f"multipart cleanup also failed: {abort_error}")
            raise
        inspected = await self.inspect(object_key)
        if inspected is None or (
            inspected.sha256 != completed.sha256 or inspected.size_bytes != completed.size_bytes
        ):
            raise ObjectStoreError("S3 staged stream inspection failed")
        return inspected

    async def inspect(self, object_key: str) -> StoredObject | None:
        remote = self._remote_key(object_key)
        try:
            head = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._policy.bucket,
                Key=remote,
                ChecksumMode="ENABLED",
                **self._owner(),
            )
        except Exception as error:
            if self._missing(error):
                return None
            raise ObjectStoreError("S3 failed to inspect object") from error
        metadata = head.get("Metadata")
        digest = metadata.get("cmp-sha256") if isinstance(metadata, dict) else None
        size = head.get("ContentLength")
        if not isinstance(size, int) or size < 0:
            raise ObjectStoreError("S3 object size evidence is missing")
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            digest, observed_size = await asyncio.to_thread(self._digest_remote, remote)
            if observed_size != size:
                raise ObjectStoreError("S3 object size changed during inspection")
        if not isinstance(digest, str):
            raise ObjectStoreError("S3 object digest evidence is missing")
        if object_key.startswith("final/"):
            self._validate_final_head(head)
        return StoredObject(
            object_key,
            size,
            digest,
            self._etag(head),
            self._version(head),
        )

    def _validate_final_head(self, head: Mapping[str, Any]) -> None:
        if (
            head.get("ServerSideEncryption") != "aws:kms"
            or head.get("SSEKMSKeyId") != self._policy.kms_key_id
        ):
            raise ObjectStoreError("final S3 object is not encrypted by the configured KMS key")
        if head.get("ObjectLockMode") != self._policy.retention_mode:
            raise ObjectStoreError("final S3 object retention mode is missing or incorrect")
        retain_until = head.get("ObjectLockRetainUntilDate")
        if not isinstance(retain_until, datetime) or retain_until <= self._clock():
            raise ObjectStoreError("final S3 object retention date is missing or expired")

    async def governance_evidence(self, object_key: str) -> dict[str, Any]:
        """Return non-secret evidence for one validated final object."""

        if not object_key.startswith("final/"):
            raise ObjectStoreError("governance evidence requires a final object")
        remote = self._remote_key(object_key)
        try:
            head = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._policy.bucket,
                Key=remote,
                ChecksumMode="ENABLED",
                **self._owner(),
            )
        except Exception as error:
            raise ObjectStoreError("S3 failed to inspect governance evidence") from error
        self._validate_final_head(head)
        retained_until = head["ObjectLockRetainUntilDate"]
        if not isinstance(retained_until, datetime):
            raise ObjectStoreError("final S3 object retention date is unavailable")
        version_id = self._version(head)
        return {
            "bucket_sha256": hashlib.sha256(self._policy.bucket.encode()).hexdigest(),
            "kms_key_id_sha256": hashlib.sha256(self._policy.kms_key_id.encode()).hexdigest(),
            "object_lock_mode": head["ObjectLockMode"],
            "retained_until": retained_until.isoformat(),
            "server_side_encryption": head["ServerSideEncryption"],
            "version_id_sha256": hashlib.sha256(version_id.encode()).hexdigest(),
        }

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject:
        if not source_key.startswith("staging/") or not target_key.startswith("final/"):
            raise ObjectStoreError("S3 promotion requires staging-to-final keys")
        existing = await self.inspect(target_key)
        if existing is not None:
            if existing.sha256 != expected_sha256 or existing.size_bytes != expected_size_bytes:
                raise ArtifactIntegrityError("final object contains different bytes")
            return existing
        source = await self.inspect(source_key)
        if source is None:
            raise ObjectStoreError("S3 promotion source is unavailable")
        if source.sha256 != expected_sha256 or source.size_bytes != expected_size_bytes:
            raise ArtifactIntegrityError("staging object contains different bytes")
        if expected_size_bytes > 5_000_000_000:
            raise ObjectStoreError("governed S3 promotion currently supports objects up to 5 GB")
        remote_source = self._remote_key(source_key)
        remote_target = self._remote_key(target_key)

        def promote_once() -> None:
            response = self._client.get_object(
                Bucket=self._policy.bucket,
                Key=remote_source,
                VersionId=source.version_id,
                ChecksumMode="ENABLED",
                **self._owner(),
            )
            body = response.get("Body")
            if body is None or not callable(getattr(body, "read", None)):
                raise ObjectStoreError("S3 promotion source stream is unavailable")
            try:
                self._client.put_object(
                    Bucket=self._policy.bucket,
                    Key=remote_target,
                    Body=body,
                    ContentLength=expected_size_bytes,
                    ContentType="application/octet-stream",
                    ChecksumAlgorithm="SHA256",
                    ChecksumSHA256=base64.b64encode(bytes.fromhex(expected_sha256)).decode("ascii"),
                    Metadata={"cmp-sha256": expected_sha256},
                    IfNoneMatch="*",
                    **self._encryption(),
                    **self._retention(),
                    **self._owner(),
                )
            finally:
                close = getattr(body, "close", None)
                if callable(close):
                    close()

        try:
            await asyncio.to_thread(promote_once)
        except Exception as error:
            replay = await self.inspect(target_key)
            if replay is not None:
                if replay.sha256 == expected_sha256 and replay.size_bytes == expected_size_bytes:
                    await self.discard(source_key)
                    return replay
                raise ArtifactIntegrityError("final object contains different bytes") from error
            if isinstance(error, ObjectStoreError):
                raise
            raise ObjectStoreError("S3 failed to promote governed object") from error
        promoted = await self.inspect(target_key)
        if promoted is None or (
            promoted.sha256 != expected_sha256 or promoted.size_bytes != expected_size_bytes
        ):
            raise ArtifactIntegrityError("promoted S3 object differs from its manifest")
        await self.discard(source_key)
        return promoted

    async def discard(self, object_key: str) -> None:
        if not object_key.startswith("staging/"):
            raise ObjectStoreError("only non-authoritative staging objects may be discarded")
        existing = await self.inspect(object_key)
        if existing is None:
            return
        remote = self._remote_key(object_key)
        try:
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._policy.bucket,
                Key=remote,
                VersionId=existing.version_id,
                **self._owner(),
            )
        except Exception as error:
            raise ObjectStoreError("S3 failed to discard staging object version") from error

    async def list_objects(self, prefix: str) -> tuple[StoredObject, ...]:
        if not prefix.endswith("/"):
            raise ObjectStoreError("object listing prefix must end with a separator")
        remote_prefix = self._remote_key(prefix.rstrip("/")) + "/"
        keys: list[str] = []
        token: str | None = None
        while True:
            arguments: dict[str, Any] = {
                "Bucket": self._policy.bucket,
                "Prefix": remote_prefix,
                **self._owner(),
            }
            if token is not None:
                arguments["ContinuationToken"] = token
            try:
                response = await asyncio.to_thread(self._client.list_objects_v2, **arguments)
            except Exception as error:
                raise ObjectStoreError("S3 failed to list objects") from error
            contents = response.get("Contents", [])
            if not isinstance(contents, list):
                raise ObjectStoreError("S3 object listing is malformed")
            for item in contents:
                remote = item.get("Key") if isinstance(item, dict) else None
                if not isinstance(remote, str) or not remote.startswith(f"{self._policy.prefix}/"):
                    raise ObjectStoreError("S3 object listing returned an unsafe key")
                keys.append(remote[len(self._policy.prefix) + 1 :])
            if not response.get("IsTruncated"):
                break
            token_value = response.get("NextContinuationToken")
            if not isinstance(token_value, str) or not token_value:
                raise ObjectStoreError("S3 paginated listing omitted continuation token")
            token = token_value
        observed: list[StoredObject] = []
        for key in sorted(keys):
            stored = await self.inspect(key)
            if stored is not None:
                observed.append(stored)
        return tuple(observed)

    def stream(self, object_key: str) -> AsyncIterable[bytes]:
        remote = self._remote_key(object_key)

        async def values() -> AsyncIterator[bytes]:
            try:
                response = await asyncio.to_thread(
                    self._client.get_object,
                    Bucket=self._policy.bucket,
                    Key=remote,
                    ChecksumMode="ENABLED",
                    **self._owner(),
                )
                body = response.get("Body")
                if body is None or not callable(getattr(body, "read", None)):
                    raise ObjectStoreError("S3 object stream is unavailable")
                while True:
                    chunk = await asyncio.to_thread(body.read, 1024 * 1024)
                    if not chunk:
                        break
                    if not isinstance(chunk, bytes):
                        raise ObjectStoreError("S3 object stream returned non-byte content")
                    yield chunk
            except ObjectStoreError:
                raise
            except Exception as error:
                raise ObjectStoreError("S3 failed to stream immutable object") from error

        return values()

    def _digest_remote(self, remote_key: str) -> tuple[str, int]:
        try:
            response = self._client.get_object(
                Bucket=self._policy.bucket,
                Key=remote_key,
                ChecksumMode="ENABLED",
                **self._owner(),
            )
            body = response.get("Body")
            if body is None or not callable(getattr(body, "read", None)):
                raise ObjectStoreError("S3 object stream is unavailable")
            digest = hashlib.sha256()
            size = 0
            while chunk := body.read(1024 * 1024):
                if not isinstance(chunk, bytes):
                    raise ObjectStoreError("S3 object stream returned non-byte content")
                digest.update(chunk)
                size += len(chunk)
            return digest.hexdigest(), size
        except ObjectStoreError:
            raise
        except Exception as error:
            raise ObjectStoreError("S3 failed to verify immutable object bytes") from error
