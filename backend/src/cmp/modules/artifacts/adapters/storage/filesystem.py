"""Streaming non-production filesystem implementation of the multipart object-store port."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
from collections.abc import AsyncIterable
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from cmp.modules.artifacts.domain.content import ArtifactIntegrityError, StoredObject
from cmp.modules.artifacts.domain.uploads import (
    CompletedObject,
    InvalidUpload,
    ObjectStoreError,
    StoredPart,
)


def _hash_file(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ObjectStoreError("stored object is not a regular file")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


class FilesystemMultipartObjectStore:
    """Exercise real streaming/file semantics without claiming S3 production equivalence."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError("filesystem object-store root cannot be a symlink")
        self._root = root.resolve(strict=True)
        self._multipart = self._root / "multipart"
        self._objects = self._root / "objects"
        self._multipart.mkdir(exist_ok=True)
        self._objects.mkdir(exist_ok=True)

    @staticmethod
    def _safe_key(value: str) -> PurePosixPath:
        if "\\" in value or "\x00" in value:
            raise ObjectStoreError("object key contains a forbidden separator")
        key = PurePosixPath(value)
        if key.is_absolute() or not key.parts or any(
            part in {"", ".", ".."} for part in key.parts
        ):
            raise ObjectStoreError("object key is unsafe")
        return key

    def _inside(self, root: Path, candidate: Path) -> Path:
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root.resolve(strict=True))
        except ValueError as error:
            raise ObjectStoreError("object-store path escapes its configured root") from error
        return resolved

    def _upload_root(self, upload_id: str) -> Path:
        try:
            parsed = UUID(upload_id)
        except ValueError as error:
            raise ObjectStoreError("multipart upload identity is invalid") from error
        if parsed.int == 0:
            raise ObjectStoreError("multipart upload identity is invalid")
        return self._inside(self._multipart, self._multipart / str(parsed))

    def _object_path(self, object_key: str) -> Path:
        key = self._safe_key(object_key)
        return self._inside(
            self._objects,
            self._objects.joinpath(*key.parts).with_suffix(".blob"),
        )

    async def initiate(self, object_key: str, media_type: str) -> str:
        self._safe_key(object_key)
        if not media_type or len(media_type) > 255:
            raise ObjectStoreError("object media type is invalid")
        upload_id = str(uuid4())
        upload_root = self._upload_root(upload_id)
        try:
            upload_root.mkdir(parents=False, exist_ok=False)
        except OSError as error:
            raise ObjectStoreError("failed to initialize multipart object") from error
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
        self._safe_key(object_key)
        if not 1 <= part_number <= 100_000 or expected_size <= 0:
            raise ObjectStoreError("multipart part policy is invalid")
        upload_root = self._upload_root(upload_id)
        if not upload_root.is_dir() or upload_root.is_symlink():
            raise ObjectStoreError("multipart upload is unavailable")
        target = self._inside(upload_root, upload_root / f"{part_number:06d}.part")
        temporary = self._inside(
            upload_root, upload_root / f".{part_number:06d}.{uuid4()}.tmp"
        )
        digest = hashlib.sha256()
        observed = 0
        try:
            with temporary.open("xb") as stream:
                async for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise ObjectStoreError("upload stream yielded non-byte content")
                    if not chunk:
                        continue
                    observed += len(chunk)
                    if observed > expected_size:
                        raise InvalidUpload("upload part exceeds its immutable size")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if observed != expected_size:
                raise InvalidUpload(
                    "upload part size differs from its immutable manifest"
                )
            part_digest = digest.hexdigest()
            try:
                os.link(temporary, target)
            except FileExistsError:
                existing_digest, existing_size = _hash_file(target)
                if existing_digest != part_digest or existing_size != observed:
                    raise ObjectStoreError(
                        "multipart part number is already bound to different bytes"
                    ) from None
            return StoredPart(part_number, observed, part_digest, part_digest)
        except ObjectStoreError:
            raise
        except OSError as error:
            raise ObjectStoreError("failed to store multipart part") from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    async def complete(
        self,
        *,
        object_key: str,
        upload_id: str,
        parts: tuple[StoredPart, ...],
    ) -> CompletedObject:
        if not parts or tuple(item.part_number for item in parts) != tuple(
            range(1, len(parts) + 1)
        ):
            raise ObjectStoreError("multipart completion requires contiguous ordered parts")
        target = self._object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing_digest, existing_size = _hash_file(target)
            return CompletedObject(
                object_key, existing_size, existing_digest, existing_digest
            )
        upload_root = self._upload_root(upload_id)
        if not upload_root.is_dir() or upload_root.is_symlink():
            raise ObjectStoreError("multipart upload is unavailable")
        temporary = self._inside(
            target.parent, target.parent / f".{target.name}.{uuid4()}.tmp"
        )
        digest = hashlib.sha256()
        observed = 0
        try:
            with temporary.open("xb") as destination:
                for part in parts:
                    source = self._inside(
                        upload_root, upload_root / f"{part.part_number:06d}.part"
                    )
                    source_digest, source_size = _hash_file(source)
                    if source_digest != part.sha256 or source_size != part.size_bytes:
                        raise ObjectStoreError("multipart part bytes changed before completion")
                    with source.open("rb") as stream:
                        while chunk := stream.read(1024 * 1024):
                            digest.update(chunk)
                            observed += len(chunk)
                            destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            object_digest = digest.hexdigest()
            try:
                os.link(temporary, target)
            except FileExistsError:
                existing_digest, existing_size = _hash_file(target)
                if existing_digest != object_digest or existing_size != observed:
                    raise ObjectStoreError(
                        "immutable object key already has different bytes"
                    ) from None
            self._remove_tree(upload_root)
            return CompletedObject(object_key, observed, object_digest, object_digest)
        except ObjectStoreError:
            raise
        except OSError as error:
            raise ObjectStoreError("failed to complete multipart object") from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def _remove_tree(self, path: Path) -> None:
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self._root)
        except ValueError as error:
            raise ObjectStoreError("refusing to remove path outside object-store root") from error
        if resolved in {self._root, self._multipart, self._objects}:
            raise ObjectStoreError("refusing to remove object-store root")
        if resolved.exists():
            shutil.rmtree(resolved)

    async def abort(self, *, object_key: str, upload_id: str) -> None:
        self._safe_key(object_key)
        self._remove_tree(self._upload_root(upload_id))

    async def stage_bytes(
        self,
        *,
        object_key: str,
        value: bytes,
        media_type: str,
    ) -> StoredObject:
        """Write one non-authoritative derived object without exposing an overwrite path."""

        key = self._safe_key(object_key)
        if key.parts[:2] != ("staging", "derived"):
            raise ObjectStoreError("derived bytes must use the dedicated staging namespace")
        if not value or not media_type or len(media_type) > 255:
            raise ObjectStoreError("derived object payload or media type is invalid")
        target = self._object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(value).hexdigest()
        try:
            with target.open("xb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            existing_digest, existing_size = _hash_file(target)
            if existing_digest != digest or existing_size != len(value):
                raise ObjectStoreError(
                    "derived staging key is already bound to different bytes"
                ) from None
        except OSError as error:
            raise ObjectStoreError("failed to stage derived object bytes") from error
        result = await self.inspect(object_key)
        if result is None:
            raise RuntimeError("derived staging object disappeared after write")
        return result

    async def discard(self, object_key: str) -> None:
        key = self._safe_key(object_key)
        if key.parts[0] != "staging":
            raise ObjectStoreError("only non-authoritative staging objects may be discarded")
        target = self._object_path(object_key)
        try:
            if target.is_symlink():
                raise ObjectStoreError("refusing to discard linked object")
            target.unlink(missing_ok=True)
        except OSError as error:
            raise ObjectStoreError("failed to discard staged object") from error

    async def inspect(self, object_key: str) -> StoredObject | None:
        target = self._object_path(object_key)
        if not target.exists():
            return None
        digest, size = _hash_file(target)
        return StoredObject(object_key, size, digest, digest, digest)

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject:
        if source_key == target_key:
            existing = await self.inspect(target_key)
            if existing is None:
                raise ObjectStoreError("content-addressed object is unavailable")
            if (
                existing.sha256 != expected_sha256
                or existing.size_bytes != expected_size_bytes
            ):
                raise ArtifactIntegrityError(
                    "content-addressed object differs from its immutable manifest"
                )
            return existing
        target = await self.inspect(target_key)
        if target is not None:
            if (
                target.sha256 != expected_sha256
                or target.size_bytes != expected_size_bytes
            ):
                raise ArtifactIntegrityError(
                    "content-addressed key already contains different bytes"
                )
            return target
        source = await self.inspect(source_key)
        if source is None:
            raise ObjectStoreError("staging object is unavailable")
        if (
            source.sha256 != expected_sha256
            or source.size_bytes != expected_size_bytes
        ):
            raise ArtifactIntegrityError(
                "staging object differs from its immutable manifest"
            )
        source_path = self._object_path(source_key)
        target_path = self._object_path(target_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._inside(
            target_path.parent,
            target_path.parent / f".{target_path.name}.{uuid4()}.tmp",
        )
        digest = hashlib.sha256()
        observed = 0
        try:
            with source_path.open("rb") as source_stream, temporary.open(
                "xb"
            ) as destination:
                while chunk := source_stream.read(1024 * 1024):
                    digest.update(chunk)
                    observed += len(chunk)
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            promoted_digest = digest.hexdigest()
            if (
                promoted_digest != expected_sha256
                or observed != expected_size_bytes
            ):
                raise ArtifactIntegrityError(
                    "staging object changed during content-addressed promotion"
                )
            try:
                os.link(temporary, target_path)
            except FileExistsError:
                concurrent_digest, concurrent_size = _hash_file(target_path)
                if (
                    concurrent_digest != expected_sha256
                    or concurrent_size != expected_size_bytes
                ):
                    raise ArtifactIntegrityError(
                        "content-addressed key was concurrently replaced"
                    ) from None
            return StoredObject(
                target_key,
                observed,
                promoted_digest,
                promoted_digest,
                promoted_digest,
            )
        except (ArtifactIntegrityError, ObjectStoreError):
            raise
        except OSError as error:
            raise ObjectStoreError(
                "failed to promote content-addressed object"
            ) from error
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    async def list_objects(self, prefix: str) -> tuple[StoredObject, ...]:
        if not prefix.endswith("/"):
            raise ObjectStoreError("object listing prefix must end with a separator")
        self._safe_key(prefix.removesuffix("/"))
        values: list[StoredObject] = []
        try:
            for path in self._objects.rglob("*.blob"):
                if path.is_symlink() or not path.is_file():
                    raise ObjectStoreError("object listing encountered a non-regular file")
                relative = path.relative_to(self._objects).as_posix()
                object_key = relative.removesuffix(".blob")
                if not object_key.startswith(prefix):
                    continue
                digest, size = _hash_file(path)
                values.append(StoredObject(object_key, size, digest, digest, digest))
        except ObjectStoreError:
            raise
        except OSError as error:
            raise ObjectStoreError("failed to list object-store content") from error
        return tuple(sorted(values, key=lambda item: item.object_key))

    async def stream(self, object_key: str) -> AsyncIterable[bytes]:
        target = self._object_path(object_key)
        if target.is_symlink() or not target.is_file():
            raise ObjectStoreError("download object is unavailable")
        try:
            with target.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    yield chunk
                    await asyncio.sleep(0)
        except OSError as error:
            raise ObjectStoreError("failed to stream immutable object") from error

    async def write_for_testing(self, object_key: str, value: bytes) -> StoredObject:
        """Seed one no-overwrite object for integration fault fixtures."""

        target = self._object_path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("xb") as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise ObjectStoreError("failed to seed test object") from error
        result = await self.inspect(object_key)
        if result is None:
            raise RuntimeError("test object disappeared after write")
        return result

    def corrupt_for_testing(self, object_key: str, value: bytes) -> None:
        """Simulate out-of-band storage damage; production code has no overwrite path."""

        target = self._object_path(object_key)
        if target.is_symlink() or not target.is_file():
            raise FileNotFoundError(object_key)
        with target.open("wb") as stream:
            stream.write(value)

    def remove_for_testing(self, object_key: str) -> None:
        """Simulate an out-of-band missing-object fault."""

        self._object_path(object_key).unlink()

    def read_for_testing(self, object_key: str) -> bytes:
        """Test-only visibility; public APIs never expose the internal object key."""

        return self._object_path(object_key).read_bytes()
