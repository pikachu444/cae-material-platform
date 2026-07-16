"""Application service for typed Bulk Export Selection, Job, and Bundle resources."""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportArchiveEvidence,
    BulkExportConflict,
    BulkExportJobState,
    BulkExportLimitExceeded,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSelectionOmission,
    ExportSourceRef,
    InvalidBulkExport,
    ResolvedBundleFile,
    build_bundle_control_files,
    build_deterministic_bundle,
    deterministic_zip_info,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import RevisionRecord


@dataclass(frozen=True, slots=True)
class BulkExportPolicy:
    maximum_components: int = 1000
    maximum_bytes: int = 5 * 1024 * 1024 * 1024
    inline_assembly_maximum_bytes: int = 64 * 1024 * 1024
    external_member_maximum_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_components <= 1000:
            raise ValueError("maximum_components must be between 1 and 1000")
        if self.maximum_bytes < 1:
            raise ValueError("maximum_bytes must be positive")
        if not 1 <= self.inline_assembly_maximum_bytes <= self.maximum_bytes:
            raise ValueError("inline assembly limit must fit the bundle limit")
        if not 1 <= self.external_member_maximum_bytes <= self.maximum_bytes:
            raise ValueError("external member limit must fit the bundle limit")


@dataclass(frozen=True, slots=True)
class ExportCandidate:
    source: ExportSourceRef
    classification: DataClassification
    source_sha256: str
    source_size_bytes: int
    media_type: str
    default_archive_path: str
    label: str

    def member(self, ordinal: int, archive_path: str | None = None) -> ExportSelectionMember:
        return ExportSelectionMember(
            ordinal,
            self.source,
            archive_path or self.default_archive_path,
            self.source_sha256,
            self.source_size_bytes,
            self.media_type,
            self.classification,
            self.label,
        )


@dataclass(frozen=True, slots=True)
class RequestedExportMember:
    ordinal: int
    source: ExportSourceRef
    required: bool = True
    archive_path: str | None = None


@dataclass(frozen=True, slots=True)
class CreateExportSelection:
    classification: DataClassification
    selection_label: str
    members: tuple[RequestedExportMember, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExportSelectionSnapshot:
    id: UUID
    current: RevisionRecord
    content: ExportSelectionContent


@dataclass(frozen=True, slots=True)
class BulkExportJob:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    selection_id: UUID
    selection_revision_id: UUID
    state: BulkExportJobState
    attempt_count: int
    bundle_id: UUID | None
    failure_code: str | None
    failure_detail: str | None
    submitted_at: datetime
    submitted_by: UUID
    started_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class BulkExportBundle:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    selection_id: UUID
    selection_revision_id: UUID
    archive_artifact_id: UUID
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    component_count: int
    omission_count: int
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class CommittedBulkExportOutput:
    id: UUID
    organization_id: UUID
    project_id: UUID
    classification: DataClassification
    job_id: UUID
    selection_revision_id: UUID
    archive_artifact_id: UUID
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    committed_at: datetime
    committed_by: UUID

    @property
    def evidence(self) -> BulkExportArchiveEvidence:
        return BulkExportArchiveEvidence(
            self.archive_sha256,
            self.archive_size_bytes,
            self.manifest_sha256,
        )


class BulkExportSourceResolver(Protocol):
    async def discover(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[ExportCandidate, ...]: ...

    async def inspect(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source: ExportSourceRef,
    ) -> ExportCandidate: ...

    async def resolve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        member: ExportSelectionMember,
        *,
        maximum_bytes: int,
    ) -> ResolvedBundleFile: ...


class BulkExportRepository(Protocol):
    def create_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        revision_id: UUID,
        content: ExportSelectionContent,
        schema_id: str,
        schema_version: str,
        change_reason: str,
        now: datetime,
    ) -> ExportSelectionSnapshot: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ExportSelectionSnapshot: ...

    def create_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        selection: ExportSelectionSnapshot,
        now: datetime,
    ) -> BulkExportJob: ...

    def mark_job_running(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        now: datetime,
    ) -> BulkExportJob: ...

    def claim_next_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        now: datetime,
    ) -> BulkExportJob | None: ...

    def record_output_commit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        job_id: UUID,
        archive_artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
        now: datetime,
    ) -> CommittedBulkExportOutput: ...

    def get_output_commit(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> CommittedBulkExportOutput | None: ...

    def complete_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        bundle_id: UUID,
        archive_artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
        content: ExportSelectionContent,
        now: datetime,
    ) -> tuple[BulkExportJob, BulkExportBundle]: ...

    def fail_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        failure_code: str,
        failure_detail: str,
        now: datetime,
    ) -> BulkExportJob: ...

    def require_output_reconciliation(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
        failure_detail: str,
        now: datetime,
    ) -> BulkExportJob: ...

    def get_job(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> BulkExportJob: ...

    def list_jobs(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportJob, ...]: ...

    def get_bundle(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_id: UUID,
    ) -> BulkExportBundle: ...

    def list_bundles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportBundle, ...]: ...


def _require(
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
        or permission.value not in decision.database_permissions
    ):
        raise InvalidBulkExport("authorization decision does not match request scope")


class BulkExportService:
    SCHEMA_ID = "urn:cmp:exporting:bulk-export-selection:1.0.0"
    SCHEMA_VERSION = "1.0.0"

    def __init__(
        self,
        *,
        repository: BulkExportRepository,
        sources: BulkExportSourceResolver,
        artifacts: ArtifactService,
        policy: BulkExportPolicy | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._sources = sources
        self._artifacts = artifacts
        self._policy = policy or BulkExportPolicy()
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    async def discover(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_id: UUID,
    ) -> tuple[ExportCandidate, ...]:
        _require(context, decision, Permission.EXPORT_READ)
        if material_id.int == 0:
            raise InvalidBulkExport("material_id must be non-zero")
        return await self._sources.discover(context, decision, material_id)

    async def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateExportSelection,
    ) -> ExportSelectionSnapshot:
        _require(context, decision, Permission.EXPORT_EXECUTE)
        if not command.change_reason or len(command.change_reason) > 2000:
            raise InvalidBulkExport("change_reason must contain 1..2000 characters")
        if not command.members or len(command.members) > self._policy.maximum_components:
            raise BulkExportLimitExceeded("selection component count exceeds policy")
        included: list[ExportSelectionMember] = []
        omissions: list[ExportSelectionOmission] = []
        for requested in command.members:
            try:
                candidate = await self._sources.inspect(context, decision, requested.source)
            except Exception as error:
                if requested.required:
                    raise BulkExportConflict(
                        f"required component {requested.ordinal} is unavailable"
                    ) from error
                omissions.append(
                    ExportSelectionOmission(
                        requested.ordinal,
                        requested.source,
                        "optional_unavailable",
                        "The optional exact source was unavailable during preflight.",
                    )
                )
                continue
            included.append(candidate.member(requested.ordinal, requested.archive_path))
        content = ExportSelectionContent(command.selection_label, tuple(included), tuple(omissions))
        if content.classification != command.classification:
            raise InvalidBulkExport(
                "selection classification must equal the most restrictive included component"
            )
        if content.expected_size_bytes > self._policy.maximum_bytes:
            raise BulkExportLimitExceeded("selection expected byte size exceeds policy")
        return self._repository.create_selection(
            context=context,
            decision=decision,
            selection_id=self._id_factory(),
            revision_id=self._id_factory(),
            content=content,
            schema_id=self.SCHEMA_ID,
            schema_version=self.SCHEMA_VERSION,
            change_reason=command.change_reason,
            now=self._clock(),
        )

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ExportSelectionSnapshot:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    async def create_job(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> tuple[BulkExportJob, BulkExportBundle | None]:
        _require(context, decision, Permission.EXPORT_EXECUTE)
        selection = self._repository.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )
        job = self._repository.create_job(
            context=context,
            decision=decision,
            job_id=self._id_factory(),
            selection=selection,
            now=self._clock(),
        )
        if selection.content.expected_size_bytes > self._policy.inline_assembly_maximum_bytes:
            return job, None
        running = self._repository.mark_job_running(
            context=context, decision=decision, job_id=job.id, now=self._clock()
        )
        return await self._assemble_inline(context, decision, selection, running)

    def _record_output(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job: BulkExportJob,
        artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
    ) -> CommittedBulkExportOutput:
        return self._repository.record_output_commit(
            context=context,
            decision=decision,
            output_id=self._id_factory(),
            job_id=job.id,
            archive_artifact_id=artifact_id,
            evidence=evidence,
            now=self._clock(),
        )

    def _complete_output(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job: BulkExportJob,
        selection: ExportSelectionSnapshot,
        output: CommittedBulkExportOutput,
    ) -> tuple[BulkExportJob, BulkExportBundle]:
        return self._repository.complete_job(
            context=context,
            decision=decision,
            job_id=job.id,
            bundle_id=self._id_factory(),
            archive_artifact_id=output.archive_artifact_id,
            evidence=output.evidence,
            content=selection.content,
            now=self._clock(),
        )

    def _record_failure(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job: BulkExportJob,
        error: Exception,
        output: CommittedBulkExportOutput | None,
    ) -> None:
        detail = str(error)[:1000] or type(error).__name__
        if output is not None:
            self._repository.require_output_reconciliation(
                context=context,
                decision=decision,
                job_id=job.id,
                failure_detail=detail,
                now=self._clock(),
            )
            return
        self._repository.fail_job(
            context=context,
            decision=decision,
            job_id=job.id,
            failure_code="assembly_failed",
            failure_detail=detail,
            now=self._clock(),
        )

    async def _assemble_inline(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection: ExportSelectionSnapshot,
        job: BulkExportJob,
    ) -> tuple[BulkExportJob, BulkExportBundle]:
        output: CommittedBulkExportOutput | None = None
        try:
            files = tuple(
                [
                    await self._sources.resolve(
                        context,
                        decision,
                        member,
                        maximum_bytes=self._policy.inline_assembly_maximum_bytes,
                    )
                    for member in selection.content.members
                ]
            )
            built = build_deterministic_bundle(
                selection_id=selection.id,
                selection_revision_id=selection.current.revision_id,
                content=selection.content,
                files=files,
            )
            record = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=selection.content.classification,
                artifact_role="export.bulk_bundle",
                schema_ref="urn:cmp:exporting:bulk-bundle-zip:1.0.0",
                media_type="application/zip",
                value=built.archive,
                idempotency_key=(
                    f"bulk-export:{selection.current.revision_id}:{built.archive_sha256}"
                ),
            )
            output = self._record_output(
                context, decision, job, record.artifact.id, built.evidence
            )
            return self._complete_output(context, decision, job, selection, output)
        except Exception as error:
            self._record_failure(context, decision, job, error, output)
            raise

    async def _assemble_external(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection: ExportSelectionSnapshot,
        job: BulkExportJob,
    ) -> tuple[BulkExportJob, BulkExportBundle]:
        output_commit: CommittedBulkExportOutput | None = None
        try:
            control = build_bundle_control_files(
                selection_id=selection.id,
                selection_revision_id=selection.current.revision_id,
                content=selection.content,
            )
            members = {member.archive_path: member for member in selection.content.members}
            control_entries = control.archive_entries()
            archive_paths = sorted((*members, *control_entries))
            with tempfile.TemporaryFile(mode="w+b") as archive:
                with zipfile.ZipFile(
                    archive,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                ) as bundle:
                    for path in archive_paths:
                        value = control_entries.get(path)
                        if value is None:
                            resolved = await self._sources.resolve(
                                context,
                                decision,
                                members[path],
                                maximum_bytes=self._policy.external_member_maximum_bytes,
                            )
                            value = resolved.value
                        bundle.writestr(deterministic_zip_info(path), value)
                archive.flush()
                archive.seek(0, 2)
                size_bytes = archive.tell()
                archive.seek(0)
                digest = hashlib.sha256()
                while chunk := archive.read(1024 * 1024):
                    digest.update(chunk)
                evidence = BulkExportArchiveEvidence(
                    digest.hexdigest(), size_bytes, control.manifest_sha256
                )

                async def chunks() -> AsyncIterator[bytes]:
                    archive.seek(0)
                    while chunk := archive.read(1024 * 1024):
                        yield chunk

                record = await self._artifacts.finalize_derived_stream(
                    context,
                    decision,
                    classification=selection.content.classification,
                    artifact_role="export.bulk_bundle",
                    schema_ref="urn:cmp:exporting:bulk-bundle-zip:1.0.0",
                    media_type="application/zip",
                    chunks=chunks(),
                    expected_sha256=evidence.archive_sha256,
                    expected_size_bytes=evidence.archive_size_bytes,
                    idempotency_key=(
                        f"bulk-export:{selection.current.revision_id}:{evidence.archive_sha256}"
                    ),
                )
            output_commit = self._record_output(
                context, decision, job, record.artifact.id, evidence
            )
            return self._complete_output(context, decision, job, selection, output_commit)
        except Exception as error:
            self._record_failure(context, decision, job, error, output_commit)
            raise

    async def execute_next_external(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportJob, BulkExportBundle] | None:
        """Claim one queued/reconcilable Bundle job for an out-of-process worker."""

        _require(context, decision, Permission.EXPORT_EXECUTE)
        job = self._repository.claim_next_job(
            context=context, decision=decision, now=self._clock()
        )
        if job is None:
            return None
        selection = self._repository.get_selection(
            context=context, decision=decision, selection_id=job.selection_id
        )
        output = self._repository.get_output_commit(
            context=context, decision=decision, job_id=job.id
        )
        if output is not None:
            try:
                return self._complete_output(context, decision, job, selection, output)
            except Exception as error:
                self._record_failure(context, decision, job, error, output)
                raise
        return await self._assemble_external(context, decision, selection, job)

    def get_job(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> BulkExportJob:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.get_job(context=context, decision=decision, job_id=job_id)

    def list_jobs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportJob, ...]:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.list_jobs(context=context, decision=decision)

    def get_output_commit(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        job_id: UUID,
    ) -> CommittedBulkExportOutput | None:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.get_output_commit(
            context=context, decision=decision, job_id=job_id
        )

    def get_bundle(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        bundle_id: UUID,
    ) -> BulkExportBundle:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.get_bundle(context=context, decision=decision, bundle_id=bundle_id)

    def list_bundles(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[BulkExportBundle, ...]:
        _require(context, decision, Permission.EXPORT_READ)
        return self._repository.list_bundles(context=context, decision=decision)
