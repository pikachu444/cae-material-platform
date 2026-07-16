from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from cmp.modules.exporting.application.bulk_export import (
    BulkExportBundle,
    BulkExportJob,
    BulkExportPolicy,
    BulkExportService,
    CommittedBulkExportOutput,
    ExportSelectionSnapshot,
)
from cmp.modules.exporting.domain.bulk_bundle import (
    BulkExportArchiveEvidence,
    BulkExportConflict,
    BulkExportJobState,
    ExportMemberKind,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSourceRef,
    ResolvedBundleFile,
    build_deterministic_bundle,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 7, 16, 15, 0, tzinfo=UTC)
ORG = UUID("97000000-0000-4000-8000-000000000001")
PROJECT = UUID("97000000-0000-4000-8000-000000000002")
ACTOR = UUID("97000000-0000-4000-8000-000000000003")
SELECTION = UUID("97000000-0000-4000-8000-000000000004")
REVISION = UUID("97000000-0000-4000-8000-000000000005")
MODEL = UUID("97000000-0000-4000-8000-000000000006")
MODEL_REVISION = UUID("97000000-0000-4000-8000-000000000007")
ARTIFACT = UUID("97000000-0000-4000-8000-000000000008")
TRACE = "00-97000000000000000000000000000000-9700000000000000-01"
VALUE = b"external-worker-bundle-source"


def _context() -> SecurityContext:
    return SecurityContext(
        Principal(ACTOR, PrincipalType.SERVICE, "Bundle worker", True),
        ORG,
        PROJECT,
        "https://issuer.invalid",
        "bundle-worker",
        "token-id",
        (),
        (),
        uuid4(),
        TRACE,
        NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        ACTOR,
        ORG,
        PROJECT,
        Permission.EXPORT_EXECUTE,
        (Role.MATERIAL_MODELER,),
        database_permissions_for(Permission.EXPORT_EXECUTE),
        DataClassification.RESTRICTED,
        False,
        context.request_id,
        TRACE,
        NOW,
    )


def _selection() -> ExportSelectionSnapshot:
    source = ExportSourceRef(
        ExportMemberKind.MODEL_IR_JSON,
        material_model_id=MODEL,
        material_model_revision_id=MODEL_REVISION,
    )
    member = ExportSelectionMember(
        1,
        source,
        "models/reference/ir.json",
        hashlib.sha256(VALUE).hexdigest(),
        len(VALUE),
        "application/json",
        DataClassification.INTERNAL,
        "Reference IR",
    )
    content = ExportSelectionContent("External worker fixture", (member,), ())
    revision = RevisionRecord(
        REVISION,
        "exporting.bulk_export_selection",
        SELECTION,
        TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        1,
        None,
        BulkExportService.SCHEMA_ID,
        BulkExportService.SCHEMA_VERSION,
        content.digest,
        NOW,
        ACTOR,
        "fixture",
        uuid4(),
        TRACE,
    )
    return ExportSelectionSnapshot(SELECTION, revision, content)


class _Sources:
    async def resolve(
        self,
        _context: SecurityContext,
        _decision: AuthorizationDecision,
        member: ExportSelectionMember,
        *,
        maximum_bytes: int,
    ) -> ResolvedBundleFile:
        assert len(VALUE) <= maximum_bytes
        return ResolvedBundleFile(member, VALUE)


class _Artifacts:
    def __init__(self) -> None:
        self.streams: list[bytes] = []

    async def finalize_derived_stream(self, *_args: object, **kwargs: object) -> object:
        chunks = cast(AsyncIterable[bytes], kwargs["chunks"])
        value = b"".join([chunk async for chunk in chunks])
        assert hashlib.sha256(value).hexdigest() == kwargs["expected_sha256"]
        assert len(value) == kwargs["expected_size_bytes"]
        self.streams.append(value)
        return SimpleNamespace(artifact=SimpleNamespace(id=ARTIFACT))


class _Repository:
    def __init__(self, *, fail_complete_once: bool = False) -> None:
        self.selection = _selection()
        self.job: BulkExportJob | None = None
        self.output: CommittedBulkExportOutput | None = None
        self.bundle: BulkExportBundle | None = None
        self.fail_complete_once = fail_complete_once

    def get_selection(self, **_kwargs: object) -> ExportSelectionSnapshot:
        return self.selection

    def create_job(
        self,
        *,
        context: SecurityContext,
        job_id: UUID,
        now: datetime,
        **_kwargs: object,
    ) -> BulkExportJob:
        self.job = BulkExportJob(
            job_id,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            SELECTION,
            REVISION,
            BulkExportJobState.QUEUED,
            1,
            None,
            None,
            None,
            now,
            context.principal.id,
            None,
            None,
        )
        return self.job

    def mark_job_running(self, *, now: datetime, **_kwargs: object) -> BulkExportJob:
        assert self.job is not None
        self.job = replace(self.job, state=BulkExportJobState.RUNNING, started_at=now)
        return self.job

    @staticmethod
    def _assert_lease(job: BulkExportJob, lease_token: UUID | None, now: datetime) -> None:
        if job.lease_token is None:
            if lease_token is not None:
                raise BulkExportConflict("Bulk Export Job lease fencing token is stale")
            return
        if job.lease_token != lease_token or job.lease_expires_at is None:
            raise BulkExportConflict("Bulk Export Job lease was lost or expired")
        if job.lease_expires_at <= now:
            raise BulkExportConflict("Bulk Export Job lease was lost or expired")

    def claim_next_job(
        self,
        *,
        now: datetime,
        lease_token: UUID,
        lease_duration: timedelta,
        **_kwargs: object,
    ) -> BulkExportJob | None:
        if self.job is None:
            return None
        if self.job.state is BulkExportJobState.QUEUED:
            self.job = replace(
                self.job,
                state=BulkExportJobState.RUNNING,
                started_at=now,
                lease_token=lease_token,
                lease_expires_at=now + lease_duration,
                heartbeat_at=now,
            )
            return self.job
        if self.job.state is BulkExportJobState.RECONCILIATION_REQUIRED:
            self.job = replace(
                self.job,
                state=BulkExportJobState.RECONCILING,
                attempt_count=self.job.attempt_count + 1,
                failure_code=None,
                failure_detail=None,
                completed_at=None,
                lease_token=lease_token,
                lease_expires_at=now + lease_duration,
                heartbeat_at=now,
            )
            return self.job
        if (
            self.job.state in (BulkExportJobState.RUNNING, BulkExportJobState.RECONCILING)
            and self.job.lease_expires_at is not None
            and self.job.lease_expires_at <= now
        ):
            self.job = replace(
                self.job,
                attempt_count=self.job.attempt_count + 1,
                lease_token=lease_token,
                lease_expires_at=now + lease_duration,
                heartbeat_at=now,
            )
            return self.job
        return None

    def renew_job_lease(
        self,
        *,
        job_id: UUID,
        lease_token: UUID,
        lease_duration: timedelta,
        now: datetime,
        **_kwargs: object,
    ) -> BulkExportJob:
        assert self.job is not None and self.job.id == job_id
        self._assert_lease(self.job, lease_token, now)
        self.job = replace(
            self.job,
            lease_expires_at=now + lease_duration,
            heartbeat_at=now,
        )
        return self.job

    def record_output_commit(
        self,
        *,
        context: SecurityContext,
        output_id: UUID,
        job_id: UUID,
        archive_artifact_id: UUID,
        evidence: BulkExportArchiveEvidence,
        lease_token: UUID | None,
        now: datetime,
        **_kwargs: object,
    ) -> CommittedBulkExportOutput:
        assert self.job is not None
        self._assert_lease(self.job, lease_token, now)
        if self.output is None:
            self.output = CommittedBulkExportOutput(
                output_id,
                ORG,
                PROJECT,
                DataClassification.INTERNAL,
                job_id,
                REVISION,
                archive_artifact_id,
                evidence.archive_sha256,
                evidence.archive_size_bytes,
                evidence.manifest_sha256,
                now,
                context.principal.id,
            )
        return self.output

    def get_output_commit(self, **_kwargs: object) -> CommittedBulkExportOutput | None:
        return self.output

    def complete_job(
        self,
        *,
        context: SecurityContext,
        bundle_id: UUID,
        evidence: BulkExportArchiveEvidence,
        content: ExportSelectionContent,
        lease_token: UUID | None,
        now: datetime,
        **_kwargs: object,
    ) -> tuple[BulkExportJob, BulkExportBundle]:
        if self.fail_complete_once:
            self.fail_complete_once = False
            raise RuntimeError("simulated later Bundle projection failure")
        assert self.job is not None and self.output is not None
        self._assert_lease(self.job, lease_token, now)
        self.bundle = BulkExportBundle(
            bundle_id,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            SELECTION,
            REVISION,
            ARTIFACT,
            evidence.archive_sha256,
            evidence.archive_size_bytes,
            evidence.manifest_sha256,
            len(content.members),
            len(content.omissions),
            now,
            context.principal.id,
        )
        self.job = replace(
            self.job,
            state=BulkExportJobState.SUCCEEDED,
            bundle_id=bundle_id,
            failure_code=None,
            failure_detail=None,
            completed_at=now,
            lease_token=None,
            lease_expires_at=None,
            heartbeat_at=None,
        )
        return self.job, self.bundle

    def require_output_reconciliation(
        self,
        *,
        failure_detail: str,
        lease_token: UUID | None,
        now: datetime,
        **_kwargs: object,
    ) -> BulkExportJob:
        assert self.job is not None and self.output is not None
        self._assert_lease(self.job, lease_token, now)
        self.job = replace(
            self.job,
            state=BulkExportJobState.RECONCILIATION_REQUIRED,
            failure_code="committed_output_pending",
            failure_detail=failure_detail,
            completed_at=now,
            lease_token=None,
            lease_expires_at=None,
            heartbeat_at=None,
        )
        return self.job

    def fail_job(self, **_kwargs: object) -> BulkExportJob:
        raise AssertionError("the committed-output fixtures must remain reconcilable")


def _service(repository: _Repository, artifacts: _Artifacts) -> BulkExportService:
    return BulkExportService(
        repository=repository,  # type: ignore[arg-type]
        sources=_Sources(),  # type: ignore[arg-type]
        artifacts=artifacts,  # type: ignore[arg-type]
        policy=BulkExportPolicy(
            inline_assembly_maximum_bytes=1,
            external_member_maximum_bytes=1024,
        ),
    )


def test_large_selection_is_queued_then_external_worker_builds_identical_bytes() -> None:
    repository = _Repository()
    artifacts = _Artifacts()
    service = _service(repository, artifacts)
    context = _context()
    decision = _decision(context)

    async def execute() -> tuple[BulkExportJob, BulkExportBundle]:
        submitted, bundle = await service.create_job(context, decision, SELECTION)
        assert submitted.state is BulkExportJobState.QUEUED
        assert bundle is None
        completed = await service.execute_next_external(context, decision)
        assert completed is not None
        return completed

    completed = asyncio.run(execute())
    expected = build_deterministic_bundle(
        selection_id=SELECTION,
        selection_revision_id=REVISION,
        content=repository.selection.content,
        files=(ResolvedBundleFile(repository.selection.content.members[0], VALUE),),
    )
    assert artifacts.streams == [expected.archive]
    assert completed[0].state is BulkExportJobState.SUCCEEDED
    assert completed[1].archive_sha256 == expected.archive_sha256


def test_committed_output_survives_later_failure_and_reconciles_without_reassembly() -> None:
    repository = _Repository(fail_complete_once=True)
    artifacts = _Artifacts()
    service = _service(repository, artifacts)
    context = _context()
    decision = _decision(context)
    async def fail_then_reconcile() -> tuple[BulkExportJob, BulkExportBundle]:
        await service.create_job(context, decision, SELECTION)
        try:
            await service.execute_next_external(context, decision)
        except RuntimeError as error:
            assert "later Bundle projection" in str(error)
        else:
            raise AssertionError("the simulated later projection failure was not raised")

        assert repository.job is not None
        assert repository.job.state is BulkExportJobState.RECONCILIATION_REQUIRED
        assert repository.output is not None
        assert len(artifacts.streams) == 1

        completed = await service.execute_next_external(context, decision)
        assert completed is not None
        return completed

    completed = asyncio.run(fail_then_reconcile())
    assert completed[0].state is BulkExportJobState.SUCCEEDED
    assert completed[0].attempt_count == 2
    assert len(artifacts.streams) == 1


def test_expired_external_job_is_reclaimed_and_stale_worker_is_fenced() -> None:
    repository = _Repository()
    context = _context()
    first_token = UUID("97000000-0000-4000-8000-000000000011")
    second_token = UUID("97000000-0000-4000-8000-000000000012")
    job = repository.create_job(context=context, job_id=uuid4(), now=NOW)

    first_claim = repository.claim_next_job(
        now=NOW,
        lease_token=first_token,
        lease_duration=timedelta(seconds=10),
    )
    assert first_claim is not None
    assert first_claim.lease_token == first_token
    assert first_claim.attempt_count == 1
    assert (
        repository.claim_next_job(
            now=NOW + timedelta(seconds=9),
            lease_token=second_token,
            lease_duration=timedelta(seconds=10),
        )
        is None
    )

    second_claim = repository.claim_next_job(
        now=NOW + timedelta(seconds=11),
        lease_token=second_token,
        lease_duration=timedelta(seconds=10),
    )
    assert second_claim is not None
    assert second_claim.id == job.id
    assert second_claim.lease_token == second_token
    assert second_claim.attempt_count == 2

    evidence = BulkExportArchiveEvidence("a" * 64, 128, "b" * 64)
    try:
        repository.record_output_commit(
            context=context,
            output_id=uuid4(),
            job_id=job.id,
            archive_artifact_id=ARTIFACT,
            evidence=evidence,
            lease_token=first_token,
            now=NOW + timedelta(seconds=12),
        )
    except BulkExportConflict:
        pass
    else:
        raise AssertionError("the expired worker fencing token was accepted")

    output = repository.record_output_commit(
        context=context,
        output_id=uuid4(),
        job_id=job.id,
        archive_artifact_id=ARTIFACT,
        evidence=evidence,
        lease_token=second_token,
        now=NOW + timedelta(seconds=12),
    )
    assert output.job_id == job.id
