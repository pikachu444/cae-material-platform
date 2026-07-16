"""Application service for approved reusable profiles and governed tabular Import Runs."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind
from cmp.modules.datasets.domain.governed_tabular import (
    GOVERNED_DATASET_SCHEMA_ID,
    GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
    GOVERNED_PARQUET_SCHEMA,
    GovernedDatasetContent,
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    GovernedImportError,
    GovernedImportProfileContent,
    ImportRunStatus,
    InvalidGovernedImport,
    TabularFileFormat,
    TabularPreview,
    inspect_tabular_source,
    normalized_parquet_bytes,
    parse_governed_source,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.application.service import TestingService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

IMPORT_PROFILE_AGGREGATE_TYPE = "datasets.import_profile"
GOVERNED_DATASET_AGGREGATE_TYPE = "datasets.governed_tabular_dataset"
SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ImportProfileSnapshot:
    id: UUID
    current: RevisionSnapshot[GovernedImportProfileContent]


@dataclass(frozen=True, slots=True)
class ImportProfileRevisionSnapshot:
    profile_id: UUID
    revision: RevisionSnapshot[GovernedImportProfileContent]


@dataclass(frozen=True, slots=True)
class GovernedDatasetSnapshot:
    id: UUID
    current: RevisionSnapshot[GovernedDatasetContent]


@dataclass(frozen=True, slots=True)
class ImportRun:
    id: UUID
    scope: TenantScope
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_profile_id: UUID
    import_profile_revision_id: UUID
    profile_sha256: str
    status: ImportRunStatus
    started_at: datetime
    finished_at: datetime | None
    started_by: UUID
    request_id: UUID
    trace_id: str
    raw_dataset_id: UUID | None = None
    raw_dataset_revision_id: UUID | None = None
    normalized_dataset_id: UUID | None = None
    normalized_dataset_revision_id: UUID | None = None
    row_count: int | None = None
    failure_code: str | None = None
    failure_detail: str | None = None


@dataclass(frozen=True, slots=True)
class CreateImportProfile:
    classification: DataClassification
    content: GovernedImportProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseImportProfile:
    expected_current_revision_id: UUID
    content: GovernedImportProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class PreviewTabularSource:
    raw_asset_id: UUID
    raw_artifact_id: UUID
    file_format: TabularFileFormat
    sheet_name: str | None
    header_row: int
    encoding: str
    delimiter: str | None
    decimal_separator: str


@dataclass(frozen=True, slots=True)
class ExecuteGovernedImport:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    import_profile_id: UUID
    import_profile_revision_id: UUID
    change_reason: str


class GovernedImportRepository(Protocol):
    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[GovernedImportProfileContent]: ...

    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[GovernedDatasetContent]: ...

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> ImportProfileSnapshot: ...

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> ImportProfileRevisionSnapshot: ...

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ImportProfileSnapshot, ...]: ...

    def save_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        preview_id: UUID,
        classification: DataClassification,
        preview: TabularPreview,
        created_at: datetime,
    ) -> None: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ImportRun,
    ) -> ImportRun: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        finished_at: datetime,
        raw_dataset: GovernedDatasetSnapshot,
        normalized_dataset: GovernedDatasetSnapshot,
        row_count: int,
    ) -> ImportRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        finished_at: datetime,
        failure_code: str,
        failure_detail: str,
        row_number: int | None,
    ) -> ImportRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ImportRun: ...

    def get_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> GovernedDatasetSnapshot: ...

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
        dataset_revision_id: UUID,
    ) -> RevisionSnapshot[GovernedDatasetContent]: ...

    def list_datasets_for_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> tuple[GovernedDatasetSnapshot, ...]: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise GovernedImportConflict("authorization decision does not match Dataset request")


def _require_capability(
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
        raise GovernedImportConflict("authorization decision lacks Dataset read capability")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise InvalidGovernedImport("change_reason must contain 1..2000 trimmed characters")
    return value


class GovernedImportService:
    def __init__(
        self,
        *,
        repository: GovernedImportRepository,
        testing: TestingService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._testing = testing
        self._artifacts = artifacts
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("governed import id_factory returned zero")
        return value

    def create_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateImportProfile,
    ) -> ImportProfileSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        profile_id = self._id()
        record = RevisionService(
            aggregate_type=IMPORT_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=profile_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ImportProfileSnapshot(profile_id, RevisionSnapshot(record, command.content))

    def revise_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseImportProfile,
    ) -> ImportProfileSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        current = self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )
        if current.current.content.profile_label != command.content.profile_label:
            raise GovernedImportConflict("Import Profile stable label cannot change")
        record = RevisionService(
            aggregate_type=IMPORT_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=profile_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_reason(command.change_reason),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ImportProfileSnapshot(profile_id, RevisionSnapshot(record, command.content))

    def list_profiles(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ImportProfileSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_profiles(context=context, decision=decision)

    def get_profile(
        self, context: SecurityContext, decision: AuthorizationDecision, profile_id: UUID
    ) -> ImportProfileSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    async def preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PreviewTabularSource,
    ) -> tuple[UUID, DataClassification, TabularPreview]:
        _require(context, decision, Permission.DATASET_WRITE)
        artifact_record, raw = await self._artifacts.read_verified_bytes(
            context, decision, command.raw_artifact_id, maximum_bytes=16 * 1024 * 1024
        )
        artifact = artifact_record.artifact
        if (
            artifact.artifact_kind is not ArtifactKind.RAW
            or artifact.source_raw_asset_id != command.raw_asset_id
        ):
            raise GovernedImportConflict("preview requires the named immutable Raw Asset Artifact")
        self._validate_media_type(command.file_format, artifact.media_type)
        preview = inspect_tabular_source(
            raw,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            raw_sha256=artifact.sha256,
            file_format=command.file_format,
            sheet_name=command.sheet_name,
            header_row=command.header_row,
            encoding=command.encoding,
            delimiter=command.delimiter,
            decimal_separator=command.decimal_separator,
        )
        preview_id = self._id()
        self._repository.save_preview(
            context=context,
            decision=decision,
            preview_id=preview_id,
            classification=artifact.classification,
            preview=preview,
            created_at=self._clock(),
        )
        return preview_id, artifact.classification, preview

    @staticmethod
    def _validate_media_type(file_format: TabularFileFormat, media_type: str) -> None:
        allowed = {
            TabularFileFormat.CSV: {"text/csv", "application/csv"},
            TabularFileFormat.TSV: {"text/tab-separated-values", "text/tsv"},
            TabularFileFormat.XLSX: {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
        }
        if media_type not in allowed[file_format]:
            raise GovernedImportConflict(
                f"Raw Artifact media type does not match declared {file_format.value} format"
            )

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteGovernedImport,
    ) -> ImportRun:
        _require(context, decision, Permission.DATASET_WRITE)
        _reason(command.change_reason)
        profile = self._repository.get_profile_revision(
            context=context,
            decision=decision,
            profile_id=command.import_profile_id,
            revision_id=command.import_profile_revision_id,
        )
        test_run = self._testing.get_test_run_revision_for_processing(
            context,
            decision,
            command.test_run_id,
            command.test_run_revision_id,
        )
        if profile.revision.record.scope != test_run.record.scope:
            raise GovernedImportConflict("Import Profile and Test Run must share an exact scope")
        now = self._clock()
        run = ImportRun(
            id=self._id(),
            scope=profile.revision.record.scope,
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            import_profile_id=command.import_profile_id,
            import_profile_revision_id=command.import_profile_revision_id,
            profile_sha256=profile.revision.record.content_hash,
            status=ImportRunStatus.EXECUTING,
            started_at=now,
            finished_at=None,
            started_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        self._repository.create_run(context=context, decision=decision, run=run)
        try:
            artifact_record, raw = await self._artifacts.read_verified_bytes(
                context, decision, command.raw_artifact_id, maximum_bytes=16 * 1024 * 1024
            )
            artifact = artifact_record.artifact
            if (
                artifact.artifact_kind is not ArtifactKind.RAW
                or artifact.source_raw_asset_id != command.raw_asset_id
                or artifact.organization_id != context.organization_id
                or artifact.project_id != context.project_id
                or artifact.classification.value != run.scope.classification
            ):
                raise GovernedImportConflict("Raw Asset does not match the pinned Import Run scope")
            self._validate_media_type(profile.revision.content.file_format, artifact.media_type)
            parsed = parse_governed_source(raw, profile.revision.content)
            raw_dataset = self._create_dataset(
                context,
                decision,
                dataset_id=self._id(),
                scope=run.scope,
                content=GovernedDatasetContent(
                    test_run_id=run.test_run_id,
                    test_run_revision_id=run.test_run_revision_id,
                    raw_asset_id=run.raw_asset_id,
                    raw_artifact_id=run.raw_artifact_id,
                    import_profile_id=run.import_profile_id,
                    import_profile_revision_id=run.import_profile_revision_id,
                    representation=GovernedDatasetRepresentation.RAW,
                    data_schema=profile.revision.content.data_schema,
                    data_artifact_id=run.raw_artifact_id,
                    data_sha256=artifact.sha256,
                    source_dataset_revision_id=None,
                    row_count=len(parsed.rows),
                    channels=profile.revision.content.channels,
                ),
                change_reason=f"{command.change_reason} (raw source)",
            )
            parquet = normalized_parquet_bytes(parsed)
            normalized_artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=artifact.classification,
                artifact_role="dataset.normalized.tabular",
                schema_ref=GOVERNED_PARQUET_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=parquet,
                idempotency_key=f"governed-import:{run.id}:normalized",
            )
            normalized_dataset = self._create_dataset(
                context,
                decision,
                dataset_id=self._id(),
                scope=run.scope,
                content=GovernedDatasetContent(
                    test_run_id=run.test_run_id,
                    test_run_revision_id=run.test_run_revision_id,
                    raw_asset_id=run.raw_asset_id,
                    raw_artifact_id=run.raw_artifact_id,
                    import_profile_id=run.import_profile_id,
                    import_profile_revision_id=run.import_profile_revision_id,
                    representation=GovernedDatasetRepresentation.NORMALIZED,
                    data_schema=profile.revision.content.data_schema,
                    data_artifact_id=normalized_artifact.artifact.id,
                    data_sha256=normalized_artifact.artifact.sha256,
                    source_dataset_revision_id=raw_dataset.current.record.revision_id,
                    row_count=len(parsed.rows),
                    channels=profile.revision.content.channels,
                ),
                change_reason=f"{command.change_reason} (normalized SI)",
            )
            return self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=run.id,
                finished_at=self._clock(),
                raw_dataset=raw_dataset,
                normalized_dataset=normalized_dataset,
                row_count=len(parsed.rows),
            )
        except Exception as error:
            detail = str(error)[:1000] or error.__class__.__name__
            row_match = re.search(r"\brow (\d+):", detail)
            failed = self._repository.fail_run(
                context=context,
                decision=decision,
                run_id=run.id,
                finished_at=self._clock(),
                failure_code=(
                    "invalid_tabular_data"
                    if isinstance(error, (InvalidGovernedImport, GovernedImportError))
                    else "import_execution_failed"
                ),
                failure_detail=detail,
                row_number=int(row_match.group(1)) if row_match else None,
            )
            return failed

    def _create_dataset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        dataset_id: UUID,
        scope: TenantScope,
        content: GovernedDatasetContent,
        change_reason: str,
    ) -> GovernedDatasetSnapshot:
        record = RevisionService(
            aggregate_type=GOVERNED_DATASET_AGGREGATE_TYPE,
            store=self._repository.dataset_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=dataset_id,
                scope=scope,
                schema_id=GOVERNED_DATASET_SCHEMA_ID,
                schema_version=SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return GovernedDatasetSnapshot(dataset_id, RevisionSnapshot(record, content))

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ImportRun:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_dataset(
        self, context: SecurityContext, decision: AuthorizationDecision, dataset_id: UUID
    ) -> GovernedDatasetSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset(
            context=context, decision=decision, dataset_id=dataset_id
        )

    def list_datasets_for_test_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> tuple[GovernedDatasetSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_datasets_for_test_run(
            context=context,
            decision=decision,
            test_run_id=test_run_id,
        )

    def get_dataset_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
        dataset_revision_id: UUID,
    ) -> RevisionSnapshot[GovernedDatasetContent]:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_id=dataset_id,
            dataset_revision_id=dataset_revision_id,
        )
