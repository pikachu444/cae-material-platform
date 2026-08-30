"""Application service for approved reusable profiles and governed tabular Import Runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind
from cmp.modules.datasets.domain.governed_tabular import (
    GOVERNED_IMPORT_PROFILE_SCHEMA_ID,
    GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_2,
    GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_3,
    GOVERNED_PARQUET_SCHEMA,
    GovernedDatasetContent,
    GovernedDatasetRepresentation,
    GovernedImportConflict,
    GovernedImportError,
    GovernedImportProfileContent,
    ImportDiagnostic,
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
from cmp.shared.domain.revisions import RevisionRecord, TenantScope, content_sha256

IMPORT_PROFILE_AGGREGATE_TYPE = "datasets.import_profile"
GOVERNED_DATASET_AGGREGATE_TYPE = "datasets.governed_tabular_dataset"
SCHEMA_VERSION = "1.1.0"


def _profile_schema(content: GovernedImportProfileContent) -> tuple[str, str]:
    """Select the schema identity from the explicit content version.

    The default remains the historical 1.1 contract so old callers produce byte-for-byte
    identical revisions.  A 1.2 profile is the only revision that serializes the new
    deformation-mode field.
    """

    if content.schema_version == "1.2.0":
        return GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_2, "1.2.0"
    if content.schema_version == "1.3.0":
        return GOVERNED_IMPORT_PROFILE_SCHEMA_ID_1_3, "1.3.0"
    return GOVERNED_IMPORT_PROFILE_SCHEMA_ID, content.schema_version


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
    idempotency_key: str
    request_sha256: str
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
    diagnostics: tuple[ImportDiagnostic, ...] = ()


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
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CommitGovernedImportSuccess:
    """Persist both governed Dataset revisions and the successful Run atomically."""

    run_id: UUID
    finished_at: datetime
    scope: TenantScope
    raw_dataset_id: UUID
    raw_content: GovernedDatasetContent
    raw_change_reason: str
    normalized_dataset_id: UUID
    normalized_artifact_id: UUID
    normalized_artifact_sha256: str
    normalized_change_reason: str


class GovernedImportRepository(Protocol):
    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[GovernedImportProfileContent]: ...

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

    def commit_success(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitGovernedImportSuccess,
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
        diagnostics: tuple[ImportDiagnostic, ...],
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
                schema_id=_profile_schema(command.content)[0],
                schema_version=_profile_schema(command.content)[1],
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
                schema_id=_profile_schema(command.content)[0],
                schema_version=_profile_schema(command.content)[1],
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
        if not 1 <= len(command.idempotency_key) <= 255 or any(
            ord(character) < 0x21 or ord(character) > 0x7E for character in command.idempotency_key
        ):
            raise InvalidGovernedImport(
                "idempotency_key must contain 1..255 visible ASCII characters"
            )
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
        request_sha256 = content_sha256(
            {
                "test_run_id": str(command.test_run_id),
                "test_run_revision_id": str(command.test_run_revision_id),
                "raw_asset_id": str(command.raw_asset_id),
                "raw_artifact_id": str(command.raw_artifact_id),
                "import_profile_id": str(command.import_profile_id),
                "import_profile_revision_id": str(command.import_profile_revision_id),
                "change_reason": command.change_reason,
            }
        )
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
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha256,
            status=ImportRunStatus.EXECUTING,
            started_at=now,
            finished_at=None,
            started_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        stored_run = self._repository.create_run(context=context, decision=decision, run=run)
        if stored_run.id != run.id:
            return stored_run
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
            raw_content = GovernedDatasetContent(
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
            )
            return self._repository.commit_success(
                context=context,
                decision=decision,
                command=CommitGovernedImportSuccess(
                    run_id=run.id,
                    finished_at=self._clock(),
                    scope=run.scope,
                    raw_dataset_id=self._id(),
                    raw_content=raw_content,
                    raw_change_reason=f"{command.change_reason} (raw source)",
                    normalized_dataset_id=self._id(),
                    normalized_artifact_id=normalized_artifact.artifact.id,
                    normalized_artifact_sha256=normalized_artifact.artifact.sha256,
                    normalized_change_reason=f"{command.change_reason} (normalized SI)",
                ),
            )
        except Exception as error:
            detail = str(error)[:1000] or error.__class__.__name__
            diagnostics = (
                error.diagnostics
                if isinstance(error, InvalidGovernedImport) and error.diagnostics
                else (
                    ImportDiagnostic(
                        ordinal=0,
                        row_number=None,
                        column_name=None,
                        channel_key=None,
                        error_code=(
                            "invalid_tabular_data"
                            if isinstance(error, (InvalidGovernedImport, GovernedImportError))
                            else "import_execution_failed"
                        ),
                        error_detail=detail,
                        recovery_hint=(
                            "Correct the governed source or pinned evidence, then retry "
                            "with a new key."
                        ),
                    ),
                )
            )
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
                diagnostics=diagnostics,
            )
            return failed

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ImportRun:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_run_for_test_data_source(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ImportRun:
        """Read one exact run while a Dataset-write decision links canonical Test Data."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    def get_dataset_revision_for_test_data_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
        dataset_revision_id: UUID,
    ) -> RevisionSnapshot[GovernedDatasetContent]:
        """Read a pinned governed Dataset revision for canonical source verification."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_id=dataset_id,
            dataset_revision_id=dataset_revision_id,
        )

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

    def get_profile_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> ImportProfileRevisionSnapshot:
        """Read an exact profile through a calibration decision's Dataset capability."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_profile_revision(
            context=context,
            decision=decision,
            profile_id=profile_id,
            revision_id=profile_revision_id,
        )
