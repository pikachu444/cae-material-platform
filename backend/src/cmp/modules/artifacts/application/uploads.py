"""T-09 authorized multipart upload orchestration and object-store ports."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from cmp.modules.artifacts.domain.uploads import (
    CompletedObject,
    DigestMismatch,
    IngestionEvent,
    InvalidUpload,
    ObjectStoreError,
    RawAsset,
    StoredPart,
    UploadAccessDenied,
    UploadExpired,
    UploadSession,
    UploadState,
    UploadStateError,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,255}$")


@dataclass(frozen=True, slots=True)
class UploadPolicy:
    max_object_bytes: int = 2 * 1024 * 1024 * 1024
    default_part_bytes: int = 8 * 1024 * 1024
    min_part_bytes: int = 64 * 1024
    max_part_bytes: int = 512 * 1024 * 1024
    max_parts: int = 10_000
    session_ttl: timedelta = timedelta(hours=24)

    def __post_init__(self) -> None:
        if not 1 <= self.max_object_bytes <= 9_223_372_036_854_775_807:
            raise ValueError("max_object_bytes must be a positive bigint")
        if not 1 <= self.min_part_bytes <= self.default_part_bytes <= self.max_part_bytes:
            raise ValueError("upload part-size policy is inconsistent")
        if not 1 <= self.max_parts <= 100_000:
            raise ValueError("max_parts must be between 1 and 100000")
        if not timedelta(minutes=1) <= self.session_ttl <= timedelta(days=7):
            raise ValueError("session_ttl must be between one minute and seven days")

    def part_size(self, expected_size: int, requested: int | None) -> int:
        if not 1 <= expected_size <= self.max_object_bytes:
            raise InvalidUpload("expected upload size exceeds platform policy")
        if requested is not None and not 1 <= requested <= self.max_part_bytes:
            raise InvalidUpload("requested multipart size exceeds platform policy")
        selected = requested or min(self.default_part_bytes, expected_size)
        if expected_size > selected and not self.min_part_bytes <= selected <= self.max_part_bytes:
            raise InvalidUpload("requested multipart size exceeds platform policy")
        selected = min(selected, expected_size)
        count = math.ceil(expected_size / selected)
        if count > self.max_parts:
            raise InvalidUpload("upload requires too many parts")
        return selected


@dataclass(frozen=True, slots=True)
class CreateUpload:
    classification: DataClassification
    original_filename: str
    media_type: str
    expected_size_bytes: int
    expected_sha256: str
    idempotency_key: str
    part_size_bytes: int | None = None
    test_run_revision_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class RecordUploadPart:
    upload_id: UUID
    part_number: int
    capability: str


@dataclass(frozen=True, slots=True)
class CompleteUpload:
    upload_id: UUID
    capability: str


@dataclass(frozen=True, slots=True)
class CancelUpload:
    upload_id: UUID
    capability: str


@dataclass(frozen=True, slots=True)
class CreateUploadResult:
    session: UploadSession
    capability: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class RawAssetCompletion:
    session: UploadSession
    raw_asset: RawAsset
    ingestion_event: IngestionEvent
    duplicate_content: bool


class MultipartObjectStore(Protocol):
    async def initiate(self, object_key: str, media_type: str) -> str: ...

    async def upload_part(
        self,
        *,
        object_key: str,
        upload_id: str,
        part_number: int,
        chunks: AsyncIterable[bytes],
        expected_size: int,
    ) -> StoredPart: ...

    async def complete(
        self,
        *,
        object_key: str,
        upload_id: str,
        parts: tuple[StoredPart, ...],
    ) -> CompletedObject: ...

    async def abort(self, *, object_key: str, upload_id: str) -> None: ...

    async def discard(self, object_key: str) -> None: ...


class UploadRepository(Protocol):
    def create(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        session: UploadSession,
    ) -> tuple[UploadSession, bool]: ...

    def get_upload(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
    ) -> UploadSession: ...

    def record_part(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        part: StoredPart,
        now: datetime,
    ) -> UploadSession: ...

    def begin_completion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        now: datetime,
    ) -> UploadSession: ...

    def complete(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        completed: CompletedObject,
        raw_asset_id: UUID,
        ingestion_event_id: UUID,
        now: datetime,
    ) -> RawAssetCompletion: ...

    def fail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> UploadSession: ...

    def cancel(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
        now: datetime,
    ) -> UploadSession: ...

    def get_raw_asset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        raw_asset_id: UUID,
    ) -> RawAsset: ...

    def get_completion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
    ) -> RawAssetCompletion: ...


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("capability segment is not URL-safe Base64")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64(decoded) != value:
        raise ValueError("capability segment is not canonical Base64")
    return decoded


class UploadCapabilityCodec:
    """Deterministic short-lived HMAC capability; the secret is never persisted or logged."""

    def __init__(
        self,
        secret: bytes,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("upload capability secret must contain at least 32 bytes")
        self._secret = bytes(secret)
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(self, session: UploadSession) -> str:
        payload = canonical_json_bytes(
            {
                "v": 1,
                "upload_id": str(session.id),
                "organization_id": str(session.organization_id),
                "project_id": str(session.project_id),
                "actor_id": str(session.created_by),
                "expires_at": int(session.expires_at.timestamp()),
            }
        )
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return f"{_b64(payload)}.{_b64(signature)}"

    def verify(self, token: str, session: UploadSession, context: SecurityContext) -> None:
        if len(token) > 4096 or token.count(".") != 1:
            raise UploadAccessDenied("upload capability is invalid")
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        try:
            payload = _unb64(encoded_payload)
            signature = _unb64(encoded_signature)
            document = json.loads(payload)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise UploadAccessDenied("upload capability is invalid") from error
        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected) or not isinstance(document, dict):
            raise UploadAccessDenied("upload capability is invalid")
        claims = cast(dict[str, Any], document)
        expected_claims = {
            "v": 1,
            "upload_id": str(session.id),
            "organization_id": str(session.organization_id),
            "project_id": str(session.project_id),
            "actor_id": str(session.created_by),
            "expires_at": int(session.expires_at.timestamp()),
        }
        if claims != expected_claims or (
            context.organization_id != session.organization_id
            or context.project_id != session.project_id
            or context.principal.id != session.created_by
        ):
            raise UploadAccessDenied("upload capability scope does not match this request")
        if self._clock() >= session.expires_at:
            raise UploadExpired("upload capability expired")


def _require_decision(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or decision.permission is not permission
    ):
        raise ValueError("authorization decision does not match upload context")


class UploadService:
    def __init__(
        self,
        *,
        repository: UploadRepository,
        object_store: MultipartObjectStore,
        capabilities: UploadCapabilityCodec,
        policy: UploadPolicy | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._store = object_store
        self._capabilities = capabilities
        self._policy = policy or UploadPolicy()
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("upload id_factory returned a zero UUID")
        return value

    async def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateUpload,
    ) -> CreateUploadResult:
        _require_decision(context, decision, Permission.ARTIFACT_WRITE)
        if not decision.allows(
            context.organization_id, context.project_id, command.classification
        ):
            raise UploadAccessDenied(
                "upload classification exceeds the authorized clearance"
            )
        if _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key) is None:
            raise InvalidUpload("idempotency_key must contain visible ASCII")
        if (
            not command.original_filename
            or command.original_filename != command.original_filename.strip()
            or len(command.original_filename) > 255
            or "\x00" in command.original_filename
            or any(item in command.original_filename for item in ("/", "\\"))
        ):
            raise InvalidUpload("original_filename must be a safe basename")
        if (
            not command.media_type
            or command.media_type != command.media_type.strip()
            or len(command.media_type) > 255
            or "\x00" in command.media_type
        ):
            raise InvalidUpload("media_type is invalid")
        if re.fullmatch(r"[0-9a-f]{64}", command.expected_sha256) is None:
            raise InvalidUpload("expected_sha256 must be lowercase SHA-256")
        if command.test_run_revision_id is not None and command.test_run_revision_id.int == 0:
            raise InvalidUpload("test_run_revision_id must be non-zero")
        part_size = self._policy.part_size(
            command.expected_size_bytes, command.part_size_bytes
        )
        now = self._clock()
        session_id = self._id()
        staging_key = (
            f"staging/{context.organization_id}/{context.project_id}/{session_id}.raw"
        )
        try:
            object_upload_id = await self._store.initiate(
                staging_key, command.media_type
            )
        except Exception as error:
            if isinstance(error, ObjectStoreError):
                raise
            raise ObjectStoreError("object store failed to initiate multipart upload") from error
        submission_digest = content_sha256(
            {
                "classification": command.classification.value,
                "original_filename": command.original_filename,
                "media_type": command.media_type,
                "expected_size_bytes": command.expected_size_bytes,
                "expected_sha256": command.expected_sha256,
                "part_size_bytes": part_size,
                "test_run_revision_id": (
                    str(command.test_run_revision_id)
                    if command.test_run_revision_id is not None
                    else None
                ),
            }
        )
        session = UploadSession(
            id=session_id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=command.classification,
            state=UploadState.OPEN,
            original_filename=command.original_filename,
            media_type=command.media_type,
            expected_size_bytes=command.expected_size_bytes,
            expected_sha256=command.expected_sha256,
            part_size_bytes=part_size,
            expected_part_count=math.ceil(command.expected_size_bytes / part_size),
            test_run_revision_id=command.test_run_revision_id,
            staging_object_key=staging_key,
            object_upload_id=object_upload_id,
            idempotency_key=command.idempotency_key,
            submission_digest=submission_digest,
            created_at=now,
            expires_at=now + self._policy.session_ttl,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            updated_at=now,
            terminal_at=None,
            raw_asset_id=None,
            failure_code=None,
        )
        try:
            persisted, replayed = self._repository.create(
                context=context,
                decision=decision,
                session=session,
            )
        except Exception:
            await self._store.abort(
                object_key=staging_key, upload_id=object_upload_id
            )
            raise
        if replayed:
            await self._store.abort(
                object_key=staging_key, upload_id=object_upload_id
            )
        return CreateUploadResult(
            persisted,
            self._capabilities.issue(persisted),
            replayed,
        )

    def get_upload(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        upload_id: UUID,
    ) -> UploadSession:
        _require_decision(context, decision, Permission.ARTIFACT_READ)
        if upload_id.int == 0:
            raise InvalidUpload("upload_id must be non-zero")
        return self._repository.get_upload(
            context=context, decision=decision, upload_id=upload_id
        )

    async def record_part(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecordUploadPart,
        chunks: AsyncIterable[bytes],
    ) -> UploadSession:
        _require_decision(context, decision, Permission.ARTIFACT_WRITE)
        session = self._repository.get_upload(
            context=context, decision=decision, upload_id=command.upload_id
        )
        self._capabilities.verify(command.capability, session, context)
        if session.state is not UploadState.OPEN:
            raise UploadStateError("upload parts are accepted only while the session is open")
        expected_size = session.expected_part_size(command.part_number)
        part = await self._store.upload_part(
            object_key=session.staging_object_key,
            upload_id=session.object_upload_id,
            part_number=command.part_number,
            chunks=chunks,
            expected_size=expected_size,
        )
        if part.size_bytes != expected_size:
            raise InvalidUpload("uploaded part size differs from the immutable manifest")
        return self._repository.record_part(
            context=context,
            decision=decision,
            upload_id=session.id,
            part=part,
            now=self._clock(),
        )

    async def complete(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CompleteUpload,
    ) -> RawAssetCompletion:
        _require_decision(context, decision, Permission.ARTIFACT_WRITE)
        current = self._repository.get_upload(
            context=context, decision=decision, upload_id=command.upload_id
        )
        self._capabilities.verify(command.capability, current, context)
        if current.state is UploadState.COMPLETED:
            return self._repository.get_completion(
                context=context,
                decision=decision,
                upload_id=current.id,
            )
        expected_numbers = tuple(range(1, current.expected_part_count + 1))
        actual_numbers = tuple(item.part_number for item in current.parts)
        if actual_numbers != expected_numbers or any(
            item.size_bytes != current.expected_part_size(item.part_number)
            for item in current.parts
        ):
            raise InvalidUpload("upload part manifest is incomplete")
        session = self._repository.begin_completion(
            context=context,
            decision=decision,
            upload_id=command.upload_id,
            now=self._clock(),
        )
        completed = await self._store.complete(
            object_key=session.staging_object_key,
            upload_id=session.object_upload_id,
            parts=tuple(item.stored() for item in session.parts),
        )
        if (
            completed.object_key != session.staging_object_key
            or completed.size_bytes != session.expected_size_bytes
            or completed.sha256 != session.expected_sha256
        ):
            self._repository.fail(
                context=context,
                decision=decision,
                upload_id=session.id,
                failure_code="digest_mismatch",
                now=self._clock(),
            )
            await self._store.discard(session.staging_object_key)
            raise DigestMismatch("completed object digest or size does not match")
        result = self._repository.complete(
            context=context,
            decision=decision,
            upload_id=session.id,
            completed=completed,
            raw_asset_id=self._id(),
            ingestion_event_id=self._id(),
            now=self._clock(),
        )
        if result.duplicate_content:
            await self._store.discard(session.staging_object_key)
        return result

    async def cancel(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CancelUpload,
    ) -> UploadSession:
        _require_decision(context, decision, Permission.ARTIFACT_WRITE)
        current = self._repository.get_upload(
            context=context, decision=decision, upload_id=command.upload_id
        )
        self._capabilities.verify(command.capability, current, context)
        cancelled = self._repository.cancel(
            context=context,
            decision=decision,
            upload_id=current.id,
            now=self._clock(),
        )
        await self._store.abort(
            object_key=current.staging_object_key,
            upload_id=current.object_upload_id,
        )
        await self._store.discard(current.staging_object_key)
        return cancelled

    def get_raw_asset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        raw_asset_id: UUID,
    ) -> RawAsset:
        _require_decision(context, decision, Permission.ARTIFACT_READ)
        if raw_asset_id.int == 0:
            raise InvalidUpload("raw_asset_id must be non-zero")
        return self._repository.get_raw_asset(
            context=context,
            decision=decision,
            raw_asset_id=raw_asset_id,
        )
