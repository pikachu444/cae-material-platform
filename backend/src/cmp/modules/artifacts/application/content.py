"""T-10 content-addressed finalization, transfer, and reconciliation use cases."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactAccessDenied,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactRecord,
    ArtifactStateError,
    ArtifactTransferExpired,
    IntegrityCheckKind,
    IntegrityObservation,
    IntegrityStatus,
    InvalidArtifact,
    PendingArtifact,
    PendingArtifactState,
    ReconciliationIssue,
    ReconciliationIssueType,
    StoredObject,
    content_object_key,
    parse_content_object_key,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError, RawAsset
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import canonical_json_bytes, content_sha256

_IDEMPOTENCY_KEY = re.compile(r"^[\x21-\x7e]{1,255}$")
@dataclass(frozen=True, slots=True)
class ArtifactPolicy:
    transfer_ttl: timedelta = timedelta(minutes=5)
    max_transfer_ttl: timedelta = timedelta(minutes=15)
    default_reconciliation_limit: int = 1000

    def __post_init__(self) -> None:
        if not timedelta(seconds=1) <= self.transfer_ttl <= self.max_transfer_ttl:
            raise ValueError("Artifact transfer TTL policy is inconsistent")
        if not timedelta(seconds=1) <= self.max_transfer_ttl <= timedelta(hours=1):
            raise ValueError("maximum Artifact transfer TTL must be at most one hour")
        if not 1 <= self.default_reconciliation_limit <= 10_000:
            raise ValueError("default reconciliation limit is invalid")


@dataclass(frozen=True, slots=True)
class PrepareArtifact:
    classification: DataClassification
    artifact_kind: ArtifactKind
    artifact_role: str
    schema_ref: str | None
    media_type: str
    expected_size_bytes: int
    expected_sha256: str
    staging_object_key: str
    idempotency_key: str
    encryption_profile: str = "deployment-default"
    source_raw_asset_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class FinalizedArtifact:
    pending: PendingArtifact
    record: ArtifactRecord
    replayed: bool


# A bounded consumer may add its own immutable revision rows while the Artifact
# finalization transaction is still open.  The application layer intentionally
# treats the transaction object as opaque; SQL adapters provide the concrete
# session type.
ArtifactCommitHook = Callable[[Any, FinalizedArtifact], None]


@dataclass(frozen=True, slots=True)
class ArtifactDownloadGrant:
    artifact_id: UUID
    token: str
    expires_at: datetime
    transfer_path: str
    sha256: str
    size_bytes: int
    media_type: str


@dataclass(frozen=True, slots=True)
class ArtifactDownload:
    record: ArtifactRecord
    chunks: AsyncIterable[bytes]


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    artifacts_checked: int
    verified: int
    missing: int
    corrupt: int
    pending_recovered: int
    issues_recorded: int
    orphan_objects: int


class ContentObjectStore(Protocol):
    async def stage_bytes(
        self,
        *,
        object_key: str,
        value: bytes,
        media_type: str,
    ) -> StoredObject: ...

    async def stage_stream(
        self,
        *,
        object_key: str,
        chunks: AsyncIterable[bytes],
        media_type: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject: ...

    async def inspect(self, object_key: str) -> StoredObject | None: ...

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject: ...

    async def discard(self, object_key: str) -> None: ...

    async def list_objects(self, prefix: str) -> tuple[StoredObject, ...]: ...

    def stream(self, object_key: str) -> AsyncIterable[bytes]: ...


class ArtifactRepository(Protocol):
    def prepare(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending: PendingArtifact,
    ) -> tuple[PendingArtifact, bool]: ...

    def begin_promotion(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        now: datetime,
    ) -> PendingArtifact: ...

    def mark_retryable(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> PendingArtifact: ...

    def reject(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        failure_code: str,
        now: datetime,
    ) -> PendingArtifact: ...

    def commit_available(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending_id: UUID,
        stored: StoredObject,
        observation_id: UUID,
        now: datetime,
        commit_hook: ArtifactCommitHook | None = None,
    ) -> FinalizedArtifact: ...

    def get_artifact(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactRecord: ...

    def record_integrity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        observation: IntegrityObservation,
    ) -> ArtifactRecord: ...

    def list_artifacts(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ArtifactRecord, ...]: ...

    def list_unfinished(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[PendingArtifact, ...]: ...

    def known_final_keys(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> frozenset[str]: ...

    def record_issue(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        issue: ReconciliationIssue,
    ) -> ReconciliationIssue: ...


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    if not value or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError("transfer segment is not URL-safe Base64")
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if _b64(decoded) != value:
        raise ValueError("transfer segment is not canonical Base64")
    return decoded


class ArtifactTransferCodec:
    """Canonical HMAC transfer capability bound to actor, tenant, content, and expiry."""

    def __init__(
        self,
        secret: bytes,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(secret) < 32:
            raise ValueError("Artifact transfer secret must contain at least 32 bytes")
        self._secret = bytes(secret)
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(
        self,
        record: ArtifactRecord,
        context: SecurityContext,
        expires_at: datetime,
    ) -> str:
        artifact = record.artifact
        payload = canonical_json_bytes(
            {
                "v": 1,
                "artifact_id": str(artifact.id),
                "organization_id": str(artifact.organization_id),
                "project_id": str(artifact.project_id),
                "actor_id": str(context.principal.id),
                "sha256": artifact.sha256,
                "expires_at": int(expires_at.timestamp()),
            }
        )
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return f"{_b64(payload)}.{_b64(signature)}"

    def verify(
        self,
        token: str,
        record: ArtifactRecord,
        context: SecurityContext,
    ) -> None:
        if len(token) > 4096 or token.count(".") != 1:
            raise ArtifactAccessDenied("Artifact transfer capability is invalid")
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        try:
            payload = _unb64(encoded_payload)
            signature = _unb64(encoded_signature)
            document = json.loads(payload)
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactAccessDenied("Artifact transfer capability is invalid") from error
        expected_signature = hmac.new(
            self._secret, payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected_signature) or not isinstance(
            document, dict
        ):
            raise ArtifactAccessDenied("Artifact transfer capability is invalid")
        artifact = record.artifact
        claims = cast(dict[str, Any], document)
        expected_claims = {
            "v": 1,
            "artifact_id": str(artifact.id),
            "organization_id": str(artifact.organization_id),
            "project_id": str(artifact.project_id),
            "actor_id": str(context.principal.id),
            "sha256": artifact.sha256,
            "expires_at": claims.get("expires_at"),
        }
        if claims != expected_claims or (
            context.organization_id != artifact.organization_id
            or context.project_id != artifact.project_id
        ):
            raise ArtifactAccessDenied(
                "Artifact transfer capability scope does not match this request"
            )
        expires_at = claims.get("expires_at")
        if not isinstance(expires_at, int):
            raise ArtifactAccessDenied("Artifact transfer expiry is invalid")
        if self._clock().timestamp() >= expires_at:
            raise ArtifactTransferExpired("Artifact transfer capability expired")


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
        raise ValueError("authorization decision does not match Artifact context")


def _require_database_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    """Permit a bounded command to consume an explicitly granted Artifact dependency."""

    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise ArtifactAccessDenied("authorization decision lacks the required Artifact capability")


def _matches(value: StoredObject, sha256: str, size_bytes: int) -> bool:
    return value.sha256 == sha256 and value.size_bytes == size_bytes


class ArtifactService:
    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        object_store: ContentObjectStore,
        transfers: ArtifactTransferCodec,
        policy: ArtifactPolicy | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._store = object_store
        self._transfers = transfers
        self._policy = policy or ArtifactPolicy()
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("Artifact id_factory returned a zero UUID")
        return value

    async def finalize_raw_asset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        raw_asset: RawAsset,
    ) -> UUID:
        if (
            raw_asset.organization_id != context.organization_id
            or raw_asset.project_id != context.project_id
        ):
            raise ArtifactAccessDenied("Raw Asset tenant differs from finalization context")
        result = await self.finalize_staged(
            context,
            decision,
            PrepareArtifact(
                classification=raw_asset.classification,
                artifact_kind=ArtifactKind.RAW,
                artifact_role="raw.source",
                schema_ref=None,
                media_type=raw_asset.media_type,
                expected_size_bytes=raw_asset.size_bytes,
                expected_sha256=raw_asset.sha256,
                staging_object_key=raw_asset.staging_object_key,
                idempotency_key=f"raw:{raw_asset.id}",
                source_raw_asset_id=raw_asset.id,
            ),
        )
        return result.record.artifact.id

    @staticmethod
    def _derived_staging_key(
        context: SecurityContext,
        classification: DataClassification,
        idempotency_key: str,
    ) -> str:
        """Return a deterministic non-authoritative key for one derived-byte command."""

        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        return (
            f"staging/derived/{context.organization_id}/{context.project_id}/"
            f"{classification.value}/{digest}"
        )

    async def finalize_derived_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        value: bytes,
        idempotency_key: str,
        commit_hook: ArtifactCommitHook | None = None,
    ) -> ArtifactRecord:
        """Persist one small derived payload through the immutable Artifact lifecycle.

        This is intentionally an internal application service, not a generic upload endpoint.
        A bounded domain (the reference Dataset importer) supplies fully validated bytes and an
        explicit schema/role.  The bytes first receive a deterministic staging key, then use the
        same content-addressed promotion, integrity observation, outbox, and RLS path as other
        Artifacts.
        """

        _require_database_capability(context, decision, Permission.ARTIFACT_WRITE)
        if not value:
            raise InvalidArtifact("derived Artifact bytes must not be empty")
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise InvalidArtifact("Artifact idempotency key must contain visible ASCII")
        sha256 = hashlib.sha256(value).hexdigest()
        staging_key = self._derived_staging_key(context, classification, idempotency_key)
        stored = await self._store.stage_bytes(
            object_key=staging_key,
            value=value,
            media_type=media_type,
        )
        if stored.sha256 != sha256 or stored.size_bytes != len(value):
            raise ArtifactIntegrityError("derived staging object differs from supplied bytes")
        result = await self.finalize_staged(
            context,
            decision,
            PrepareArtifact(
                classification=classification,
                artifact_kind=ArtifactKind.DERIVED,
                artifact_role=artifact_role,
                schema_ref=schema_ref,
                media_type=media_type,
                expected_size_bytes=len(value),
                expected_sha256=sha256,
                staging_object_key=staging_key,
                idempotency_key=idempotency_key,
            ),
            commit_hook=commit_hook,
        )
        if result.replayed:
            try:
                await self._store.discard(staging_key)
            except ObjectStoreError:
                pass
        return result.record

    async def finalize_derived_stream(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        chunks: AsyncIterable[bytes],
        expected_sha256: str,
        expected_size_bytes: int,
        idempotency_key: str,
    ) -> ArtifactRecord:
        """Finalize a validated large derived stream without materializing it in API memory."""

        _require_database_capability(context, decision, Permission.ARTIFACT_WRITE)
        if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
            raise InvalidArtifact("derived Artifact SHA-256 is invalid")
        if expected_size_bytes < 1:
            raise InvalidArtifact("derived Artifact size must be positive")
        if _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise InvalidArtifact("Artifact idempotency key must contain visible ASCII")
        staging_key = self._derived_staging_key(context, classification, idempotency_key)
        stored = await self._store.stage_stream(
            object_key=staging_key,
            chunks=chunks,
            media_type=media_type,
            expected_sha256=expected_sha256,
            expected_size_bytes=expected_size_bytes,
        )
        if not _matches(stored, expected_sha256, expected_size_bytes):
            raise ArtifactIntegrityError("derived staging stream differs from supplied evidence")
        result = await self.finalize_staged(
            context,
            decision,
            PrepareArtifact(
                classification=classification,
                artifact_kind=ArtifactKind.DERIVED,
                artifact_role=artifact_role,
                schema_ref=schema_ref,
                media_type=media_type,
                expected_size_bytes=expected_size_bytes,
                expected_sha256=expected_sha256,
                staging_object_key=staging_key,
                idempotency_key=idempotency_key,
            ),
        )
        if result.replayed:
            try:
                await self._store.discard(staging_key)
            except ObjectStoreError:
                pass
        return result.record

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        """Read a bounded immutable Artifact for an in-process typed importer.

        Public callers keep using short-lived streaming transfer capabilities.  This method is
        deliberately scoped to a server-side application command that already holds
        ``artifact.read`` and rechecks the authoritative digest before parsing.
        """

        # Keep the long-standing bounded reader contract.  Registration package limits
        # must not widen the global immutable Artifact read cap.
        if not 1 <= maximum_bytes <= 64 * 1024 * 1024:
            raise InvalidArtifact("maximum Artifact read size is outside the supported range")
        _require_database_capability(context, decision, Permission.ARTIFACT_READ)
        if artifact_id.int == 0:
            raise InvalidArtifact("artifact_id must be non-zero")
        record = self._repository.get_artifact(
            context=context,
            decision=decision,
            artifact_id=artifact_id,
        )
        if record.integrity_status is not IntegrityStatus.VERIFIED:
            raise ArtifactIntegrityError("Artifact is not currently verified")
        chunks: list[bytes] = []
        observed = 0
        async for chunk in self._store.stream(record.artifact.storage_key):
            observed += len(chunk)
            if observed > maximum_bytes:
                raise InvalidArtifact("Artifact exceeds the importer byte limit")
            chunks.append(chunk)
        value = b"".join(chunks)
        if (
            len(value) != record.artifact.size_bytes
            or hashlib.sha256(value).hexdigest() != record.artifact.sha256
        ):
            raise ArtifactIntegrityError("Artifact bytes no longer match the immutable manifest")
        return record, value

    async def stream_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, AsyncIterable[bytes]]:
        """Open a capability-scoped, integrity-checked stream for worker materialization.

        Unlike ``read_verified_bytes``, this boundary does not collect the immutable object in
        API memory.  The returned iterator verifies the object-store stream before it yields its
        final item; callers must consume it to completion and must not expose the iterator to a
        plugin or an untrusted caller.
        """

        if not 1 <= maximum_bytes <= 512 * 1024 * 1024:
            raise InvalidArtifact("maximum Artifact stream size is outside the supported range")
        _require_database_capability(context, decision, Permission.ARTIFACT_READ)
        if artifact_id.int == 0:
            raise InvalidArtifact("artifact_id must be non-zero")
        record = self._repository.get_artifact(
            context=context,
            decision=decision,
            artifact_id=artifact_id,
        )
        if record.integrity_status is not IntegrityStatus.VERIFIED:
            raise ArtifactIntegrityError("Artifact is not currently verified")
        if record.artifact.size_bytes > maximum_bytes:
            raise InvalidArtifact("Artifact exceeds the worker stream byte limit")

        async def verified_chunks() -> AsyncIterator[bytes]:
            digest = hashlib.sha256()
            observed = 0
            async for chunk in self._store.stream(record.artifact.storage_key):
                if not isinstance(chunk, bytes):
                    raise ArtifactIntegrityError("Artifact stream yielded a non-byte chunk")
                observed += len(chunk)
                if observed > maximum_bytes:
                    raise InvalidArtifact("Artifact exceeds the worker stream byte limit")
                digest.update(chunk)
                yield chunk
            if (
                observed != record.artifact.size_bytes
                or digest.hexdigest() != record.artifact.sha256
            ):
                raise ArtifactIntegrityError(
                    "Artifact bytes no longer match the immutable manifest"
                )

        return record, verified_chunks()

    async def finalize_staged(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PrepareArtifact,
        *,
        commit_hook: ArtifactCommitHook | None = None,
    ) -> FinalizedArtifact:
        _require_database_capability(context, decision, Permission.ARTIFACT_WRITE)
        if not decision.allows(
            context.organization_id, context.project_id, command.classification
        ):
            raise ArtifactAccessDenied(
                "Artifact classification exceeds the authorized clearance"
            )
        if _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key) is None:
            raise InvalidArtifact("Artifact idempotency key must contain visible ASCII")
        now = self._clock()
        final_key = content_object_key(
            context.organization_id,
            context.project_id,
            command.classification,
            command.expected_sha256,
        )
        submission_digest = content_sha256(
            {
                "classification": command.classification.value,
                "artifact_kind": command.artifact_kind.value,
                "artifact_role": command.artifact_role,
                "schema_ref": command.schema_ref,
                "media_type": command.media_type,
                "expected_size_bytes": command.expected_size_bytes,
                "expected_sha256": command.expected_sha256,
                "staging_object_key": command.staging_object_key,
                "final_object_key": final_key,
                "encryption_profile": command.encryption_profile,
                "source_raw_asset_id": (
                    str(command.source_raw_asset_id)
                    if command.source_raw_asset_id is not None
                    else None
                ),
            }
        )
        try:
            pending = PendingArtifact(
                id=self._id(),
                organization_id=context.organization_id,
                project_id=context.project_id,
                classification=command.classification,
                state=PendingArtifactState.PENDING,
                artifact_kind=command.artifact_kind,
                artifact_role=command.artifact_role,
                schema_ref=command.schema_ref,
                media_type=command.media_type,
                expected_size_bytes=command.expected_size_bytes,
                expected_sha256=command.expected_sha256,
                staging_object_key=command.staging_object_key,
                final_object_key=final_key,
                encryption_profile=command.encryption_profile,
                source_raw_asset_id=command.source_raw_asset_id,
                idempotency_key=command.idempotency_key,
                submission_digest=submission_digest,
                reserved_artifact_id=self._id(),
                available_artifact_id=None,
                attempt_count=0,
                failure_code=None,
                created_at=now,
                created_by=context.principal.id,
                request_id=context.request_id,
                trace_id=context.trace_id,
                updated_at=now,
                terminal_at=None,
            )
        except ValueError as error:
            raise InvalidArtifact("Artifact manifest is invalid") from error
        persisted, replayed = self._repository.prepare(
            context=context,
            decision=decision,
            pending=pending,
        )
        return await self._finalize_pending(
            context, decision, persisted, replayed=replayed, commit_hook=commit_hook
        )

    async def _finalize_pending(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pending: PendingArtifact,
        *,
        replayed: bool,
        commit_hook: ArtifactCommitHook | None = None,
    ) -> FinalizedArtifact:
        if pending.state is PendingArtifactState.AVAILABLE:
            if pending.available_artifact_id is None:
                raise RuntimeError("available pending Artifact lost its identity")
            return FinalizedArtifact(
                pending,
                self._repository.get_artifact(
                    context=context,
                    decision=decision,
                    artifact_id=pending.available_artifact_id,
                ),
                True,
            )
        if pending.state is PendingArtifactState.REJECTED:
            raise ArtifactStateError("rejected Artifact finalization cannot be replayed")
        promoting = self._repository.begin_promotion(
            context=context,
            decision=decision,
            pending_id=pending.id,
            now=self._clock(),
        )
        if promoting.state is PendingArtifactState.AVAILABLE:
            if promoting.available_artifact_id is None:
                raise RuntimeError("available pending Artifact lost its identity")
            return FinalizedArtifact(
                promoting,
                self._repository.get_artifact(
                    context=context,
                    decision=decision,
                    artifact_id=promoting.available_artifact_id,
                ),
                True,
            )
        if promoting.state is PendingArtifactState.REJECTED:
            raise ArtifactStateError("pending Artifact was rejected concurrently")
        if promoting.state is not PendingArtifactState.PROMOTING:
            raise ArtifactStateError("pending Artifact did not enter promotion")
        try:
            stored = await self._store.promote(
                source_key=promoting.staging_object_key,
                target_key=promoting.final_object_key,
                expected_sha256=promoting.expected_sha256,
                expected_size_bytes=promoting.expected_size_bytes,
            )
        except ArtifactIntegrityError:
            self._repository.reject(
                context=context,
                decision=decision,
                pending_id=promoting.id,
                failure_code="content_mismatch",
                now=self._clock(),
            )
            raise
        except ObjectStoreError:
            self._repository.mark_retryable(
                context=context,
                decision=decision,
                pending_id=promoting.id,
                failure_code="object_store_unavailable",
                now=self._clock(),
            )
            raise
        if stored.object_key != promoting.final_object_key or not _matches(
            stored, promoting.expected_sha256, promoting.expected_size_bytes
        ):
            self._repository.reject(
                context=context,
                decision=decision,
                pending_id=promoting.id,
                failure_code="content_mismatch",
                now=self._clock(),
            )
            raise ArtifactIntegrityError("promoted object differs from its manifest")
        commit_kwargs: dict[str, Any] = {
            "context": context,
            "decision": decision,
            "pending_id": promoting.id,
            "stored": stored,
            "observation_id": self._id(),
            "now": self._clock(),
        }
        if commit_hook is not None:
            commit_kwargs["commit_hook"] = commit_hook
        committed = self._repository.commit_available(**commit_kwargs)
        try:
            if promoting.staging_object_key != promoting.final_object_key:
                await self._store.discard(promoting.staging_object_key)
        except ObjectStoreError:
            # The authoritative final object and DB record are already available. T-16
            # retention cleanup can remove this non-authoritative staging orphan.
            pass
        return FinalizedArtifact(committed.pending, committed.record, replayed)

    def get_artifact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactRecord:
        _require_decision(context, decision, Permission.ARTIFACT_READ)
        if artifact_id.int == 0:
            raise InvalidArtifact("artifact_id must be non-zero")
        return self._repository.get_artifact(
            context=context,
            decision=decision,
            artifact_id=artifact_id,
        )

    def get_artifact_with_capability(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactRecord:
        """Read one exact Artifact from an owning command's DB capability closure."""

        _require_database_capability(context, decision, Permission.ARTIFACT_READ)
        if artifact_id.int == 0:
            raise InvalidArtifact("artifact_id must be non-zero")
        return self._repository.get_artifact(
            context=context,
            decision=decision,
            artifact_id=artifact_id,
        )

    async def issue_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        ttl: timedelta | None = None,
    ) -> ArtifactDownloadGrant:
        _require_decision(context, decision, Permission.ARTIFACT_READ)
        return await self._issue_download(context, decision, artifact_id, ttl=ttl)

    async def issue_download_with_capability(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        ttl: timedelta | None = None,
    ) -> ArtifactDownloadGrant:
        """Issue a transfer from an owning command's Artifact read dependency."""

        _require_database_capability(context, decision, Permission.ARTIFACT_READ)
        return await self._issue_download(context, decision, artifact_id, ttl=ttl)

    async def _issue_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        ttl: timedelta | None,
    ) -> ArtifactDownloadGrant:
        if artifact_id.int == 0:
            raise InvalidArtifact("artifact_id must be non-zero")
        record = self._repository.get_artifact(
            context=context,
            decision=decision,
            artifact_id=artifact_id,
        )
        if record.integrity_status is not IntegrityStatus.VERIFIED:
            raise ArtifactIntegrityError("Artifact is not currently verified")
        stored = await self._store.inspect(record.artifact.storage_key)
        if stored is None or not _matches(
            stored, record.artifact.sha256, record.artifact.size_bytes
        ):
            raise ArtifactIntegrityError("Artifact object is missing or corrupt")
        selected_ttl = ttl or self._policy.transfer_ttl
        if not timedelta(seconds=1) <= selected_ttl <= self._policy.max_transfer_ttl:
            raise InvalidArtifact("Artifact transfer TTL exceeds platform policy")
        expires_at = datetime.fromtimestamp(
            int((self._clock() + selected_ttl).timestamp()), tz=UTC
        )
        return ArtifactDownloadGrant(
            artifact_id=artifact_id,
            token=self._transfers.issue(record, context, expires_at),
            expires_at=expires_at,
            transfer_path=f"/api/v1/artifacts/{artifact_id}/content",
            sha256=record.artifact.sha256,
            size_bytes=record.artifact.size_bytes,
            media_type=record.artifact.media_type,
        )

    async def open_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        token: str,
    ) -> ArtifactDownload:
        record = self.get_artifact(context, decision, artifact_id)
        self._transfers.verify(token, record, context)
        if record.integrity_status is not IntegrityStatus.VERIFIED:
            raise ArtifactIntegrityError("Artifact is not currently verified")
        stored = await self._store.inspect(record.artifact.storage_key)
        if stored is None or not _matches(
            stored, record.artifact.sha256, record.artifact.size_bytes
        ):
            raise ArtifactIntegrityError("Artifact object is missing or corrupt")
        return ArtifactDownload(record, self._store.stream(record.artifact.storage_key))

    def _observation(
        self,
        context: SecurityContext,
        artifact: Artifact,
        stored: StoredObject | None,
        kind: IntegrityCheckKind,
    ) -> IntegrityObservation:
        if stored is None:
            status = IntegrityStatus.MISSING
        elif _matches(stored, artifact.sha256, artifact.size_bytes):
            status = IntegrityStatus.VERIFIED
        else:
            status = IntegrityStatus.CORRUPT
        return IntegrityObservation(
            id=self._id(),
            organization_id=artifact.organization_id,
            project_id=artifact.project_id,
            classification=artifact.classification,
            artifact_id=artifact.id,
            check_kind=kind,
            status=status,
            expected_sha256=artifact.sha256,
            expected_size_bytes=artifact.size_bytes,
            observed_sha256=stored.sha256 if stored is not None else None,
            observed_size_bytes=stored.size_bytes if stored is not None else None,
            object_version_id=stored.version_id if stored is not None else None,
            checked_at=self._clock(),
            checked_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )

    def _issue(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        issue_type: ReconciliationIssueType,
        object_key: str,
        pending: PendingArtifact | None = None,
        stored: StoredObject | None = None,
    ) -> ReconciliationIssue:
        issue = ReconciliationIssue(
            id=self._id(),
            organization_id=context.organization_id,
            project_id=context.project_id,
            classification=classification,
            issue_type=issue_type,
            artifact_id=None,
            pending_artifact_id=pending.id if pending is not None else None,
            object_key=object_key,
            expected_sha256=pending.expected_sha256 if pending is not None else None,
            expected_size_bytes=(
                pending.expected_size_bytes if pending is not None else None
            ),
            observed_sha256=stored.sha256 if stored is not None else None,
            observed_size_bytes=stored.size_bytes if stored is not None else None,
            detected_at=self._clock(),
            detected_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        return self._repository.record_issue(
            context=context, decision=decision, issue=issue
        )

    async def reconcile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int | None = None,
    ) -> ReconciliationResult:
        _require_decision(context, decision, Permission.ARTIFACT_WRITE)
        selected_limit = limit or self._policy.default_reconciliation_limit
        if not 1 <= selected_limit <= 10_000:
            raise InvalidArtifact("reconciliation limit must be between 1 and 10000")
        records = self._repository.list_artifacts(
            context=context, decision=decision, limit=selected_limit
        )
        verified = missing = corrupt = 0
        for record in records:
            stored = await self._store.inspect(record.artifact.storage_key)
            observation = self._observation(
                context,
                record.artifact,
                stored,
                IntegrityCheckKind.RECONCILIATION,
            )
            self._repository.record_integrity(
                context=context,
                decision=decision,
                observation=observation,
            )
            if observation.status is IntegrityStatus.VERIFIED:
                verified += 1
            elif observation.status is IntegrityStatus.MISSING:
                missing += 1
            else:
                corrupt += 1

        recovered = issues = 0
        pending_records = self._repository.list_unfinished(
            context=context, decision=decision, limit=selected_limit
        )
        for pending in pending_records:
            final = await self._store.inspect(pending.final_object_key)
            if final is not None:
                if _matches(
                    final, pending.expected_sha256, pending.expected_size_bytes
                ):
                    await self._finalize_pending(
                        context, decision, pending, replayed=True
                    )
                    recovered += 1
                else:
                    self._repository.reject(
                        context=context,
                        decision=decision,
                        pending_id=pending.id,
                        failure_code="final_object_corrupt",
                        now=self._clock(),
                    )
                    self._issue(
                        context,
                        decision,
                        classification=pending.classification,
                        issue_type=ReconciliationIssueType.PENDING_FINAL_CORRUPT,
                        object_key=pending.final_object_key,
                        pending=pending,
                        stored=final,
                    )
                    issues += 1
                continue
            staged = await self._store.inspect(pending.staging_object_key)
            if staged is None:
                self._issue(
                    context,
                    decision,
                    classification=pending.classification,
                    issue_type=ReconciliationIssueType.PENDING_MISSING_STAGING,
                    object_key=pending.staging_object_key,
                    pending=pending,
                )
                issues += 1
            elif not _matches(
                staged, pending.expected_sha256, pending.expected_size_bytes
            ):
                self._repository.reject(
                    context=context,
                    decision=decision,
                    pending_id=pending.id,
                    failure_code="staging_object_corrupt",
                    now=self._clock(),
                )
                self._issue(
                    context,
                    decision,
                    classification=pending.classification,
                    issue_type=ReconciliationIssueType.PENDING_STAGING_CORRUPT,
                    object_key=pending.staging_object_key,
                    pending=pending,
                    stored=staged,
                )
                issues += 1
            else:
                await self._finalize_pending(context, decision, pending, replayed=True)
                recovered += 1

        known = self._repository.known_final_keys(
            context=context, decision=decision
        )
        prefix = f"final/{context.organization_id}/{context.project_id}/"
        orphans = 0
        for stored in await self._store.list_objects(prefix):
            if stored.object_key in known:
                continue
            try:
                organization_id, project_id, classification, _ = (
                    parse_content_object_key(stored.object_key)
                )
            except InvalidArtifact:
                continue
            if (
                organization_id != context.organization_id
                or project_id != context.project_id
                or not decision.allows(
                    organization_id, project_id, classification
                )
            ):
                continue
            self._issue(
                context,
                decision,
                classification=classification,
                issue_type=ReconciliationIssueType.ORPHAN_OBJECT,
                object_key=stored.object_key,
                stored=stored,
            )
            issues += 1
            orphans += 1
        return ReconciliationResult(
            artifacts_checked=len(records),
            verified=verified,
            missing=missing,
            corrupt=corrupt,
            pending_recovered=recovered,
            issues_recorded=issues,
            orphan_objects=orphans,
        )
