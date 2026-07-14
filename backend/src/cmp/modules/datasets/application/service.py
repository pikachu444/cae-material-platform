"""Create raw/normalized immutable Dataset revisions from a user-confirmed CSV mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactKind, ArtifactRecord, IntegrityStatus
from cmp.modules.datasets.domain.reference_tensile import (
    MAX_REFERENCE_TENSILE_POINTS,
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    REFERENCE_TENSILE_SCHEMA_VERSION,
    CurvePoint,
    DatasetConflict,
    DatasetContent,
    DatasetRepresentation,
    InvalidDatasetData,
    ParsedReferenceTensile,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
    normalized_points_from_parquet,
    parse_reference_tensile_csv,
    preview_points,
)
from cmp.modules.datasets.domain.selection import (
    REFERENCE_DATASET_SELECTION_SCHEMA_VERSION,
    REFERENCE_TENSILE_REPLICATE_SELECTION_SCHEMA_VERSION,
    ReferenceDatasetSelectionContent,
    ReferenceTensileReplicateSelectionContent,
    ReferenceTensileReplicateSelectionMember,
    validate_selection_label,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import REFERENCE_TENSILE_METHOD_CODE
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    RevisionConflict,
    RevisionRecord,
    TenantScope,
)

DATASET_AGGREGATE_TYPE = "datasets.dataset"
DATASET_SCHEMA_ID = "urn:cmp:datasets:reference-uniaxial-tensile:1.0.0"
DATASET_SELECTION_AGGREGATE_TYPE = "datasets.selection"
DATASET_SELECTION_SCHEMA_ID = "urn:cmp:datasets:reference-selection:1.0.0"
TENSILE_REPLICATE_SELECTION_SCHEMA_ID = (
    "urn:cmp:datasets:reference-tensile-replicate-selection:1.0.0"
)


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    id: UUID
    test_run_id: UUID
    current: RevisionSnapshot[DatasetContent]


@dataclass(frozen=True, slots=True)
class DatasetRevisionSnapshot:
    dataset_id: UUID
    revision: RevisionSnapshot[DatasetContent]


@dataclass(frozen=True, slots=True)
class CalibrationDatasetSource:
    """Pinned Dataset revision plus the Material State reached through its Test Run specimen."""

    dataset: DatasetRevisionSnapshot
    material_state_id: UUID


@dataclass(frozen=True, slots=True)
class DatasetSelectionSnapshot:
    id: UUID
    selection_label: str
    current: RevisionSnapshot[ReferenceDatasetSelectionContent]


@dataclass(frozen=True, slots=True)
class DatasetSelectionRevisionSnapshot:
    selection_id: UUID
    selection_label: str
    revision: RevisionSnapshot[ReferenceDatasetSelectionContent]


@dataclass(frozen=True, slots=True)
class TensileReplicateSelectionSnapshot:
    id: UUID
    selection_label: str
    current: RevisionSnapshot[ReferenceTensileReplicateSelectionContent]


@dataclass(frozen=True, slots=True)
class TensileReplicateSelectionRevisionSnapshot:
    selection_id: UUID
    selection_label: str
    revision: RevisionSnapshot[ReferenceTensileReplicateSelectionContent]


@dataclass(frozen=True, slots=True)
class ReferenceTestRunSource:
    classification: DataClassification
    test_method_code: str


@dataclass(frozen=True, slots=True)
class ImportReferenceTensileCsv:
    test_run_id: UUID
    test_run_revision_id: UUID
    raw_asset_id: UUID
    raw_artifact_id: UUID
    mapping: ReferenceTensileMapping
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceDatasetSelection:
    classification: DataClassification
    selection_label: str
    dataset_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceDatasetSelection:
    expected_current_revision_id: UUID
    dataset_revision_id: UUID
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileReplicateSelection:
    classification: DataClassification
    selection_label: str
    dataset_revision_ids: tuple[UUID, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceTensileReplicateSelection:
    expected_current_revision_id: UUID
    dataset_revision_ids: tuple[UUID, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class RegisterProcessedReferenceTensileDataset:
    """Public Dataset ownership port used only by a committed Processing Run.

    The Processing module supplies an already verified immutable Artifact record.  The Dataset
    module still validates its type, schema, scope, and source before writing its own tables.
    """

    source_dataset_revision_id: UUID
    processing_run_id: UUID
    artifact: ArtifactRecord
    point_count: int
    change_reason: str


@dataclass(frozen=True, slots=True)
class CurvePreview:
    dataset_id: UUID
    dataset_revision_id: UUID
    representation: DatasetRepresentation
    point_count: int
    returned_point_count: int
    sampled: bool
    strain_unit: str
    stress_unit: str
    points: tuple[CurvePoint, ...]


class DatasetRepository(Protocol):
    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[DatasetContent]: ...

    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceDatasetSelectionContent]: ...

    def replicate_selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceTensileReplicateSelectionContent]: ...

    def load_reference_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ReferenceTestRunSource: ...

    def get_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot: ...

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot: ...

    def get_calibration_dataset_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource: ...

    def list_dataset_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]: ...

    def list_datasets_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]: ...

    def get_dataset_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> DatasetSelectionSnapshot: ...

    def list_dataset_selections_for_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> tuple[DatasetSelectionSnapshot, ...]: ...

    def get_dataset_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot: ...

    def get_tensile_replicate_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> TensileReplicateSelectionSnapshot: ...

    def get_tensile_replicate_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> TensileReplicateSelectionRevisionSnapshot: ...

    def list_tensile_replicate_selections_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TensileReplicateSelectionSnapshot, ...]: ...


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
        raise DatasetConflict("authorization decision does not match Dataset request")


def _require_capability(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    """Allow an already authorized bounded command to use a Dataset dependency.

    A bounded command such as Processing or Statistics is authorized at the HTTP edge under its
    own permission. Its explicitly expanded transaction capabilities may include Dataset
    read/write, so the Dataset owner can safely provide immutable inputs or register a derived
    Dataset without pretending the caller used a public Dataset endpoint.
    """

    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise DatasetConflict("authorization decision lacks the required Dataset capability")


class DatasetService:
    """Reference-only importer that preserves raw bytes and creates a Parquet normalization."""

    def __init__(
        self,
        *,
        repository: DatasetRepository,
        artifacts: ArtifactService,
    ) -> None:
        self._repository = repository
        self._artifacts = artifacts

    @staticmethod
    def _dataset_id(
        context: SecurityContext,
        command: ImportReferenceTensileCsv,
    ) -> UUID:
        return uuid5(
            NAMESPACE_URL,
            "cmp:reference-tensile-dataset:"
            f"{context.organization_id}:{context.project_id}:{command.test_run_revision_id}:"
            f"{command.raw_artifact_id}:{command.mapping.digest}",
        )

    @staticmethod
    def _matches_source(existing: DatasetContent, expected: DatasetContent) -> bool:
        """Return whether an existing deterministic Dataset identity has the same source."""

        return (
            existing.test_run_id == expected.test_run_id
            and existing.test_run_revision_id == expected.test_run_revision_id
            and existing.raw_asset_id == expected.raw_asset_id
            and existing.raw_artifact_id == expected.raw_artifact_id
            and existing.mapping == expected.mapping
            and existing.point_count == expected.point_count
        )

    @classmethod
    def _matches_raw_input(cls, existing: DatasetContent, expected: DatasetContent) -> bool:
        return (
            existing.representation is DatasetRepresentation.RAW
            and cls._matches_source(existing, expected)
            and existing.data_artifact_id == expected.data_artifact_id
            and existing.data_sha256 == expected.data_sha256
        )

    @staticmethod
    def _matches_normalized_result(
        existing: DatasetContent,
        expected: DatasetContent,
    ) -> bool:
        return (
            existing.representation is DatasetRepresentation.NORMALIZED
            and existing.test_run_id == expected.test_run_id
            and existing.test_run_revision_id == expected.test_run_revision_id
            and existing.raw_asset_id == expected.raw_asset_id
            and existing.raw_artifact_id == expected.raw_artifact_id
            and existing.data_artifact_id == expected.data_artifact_id
            and existing.data_sha256 == expected.data_sha256
            and existing.source_dataset_revision_id == expected.source_dataset_revision_id
            and existing.mapping == expected.mapping
            and existing.point_count == expected.point_count
        )

    @staticmethod
    def _processed_dataset_id(context: SecurityContext, processing_run_id: UUID) -> UUID:
        """Bind one immutable processed Dataset identity to one immutable Processing Run."""

        return uuid5(
            NAMESPACE_URL,
            "cmp:processed-reference-tensile-dataset:"
            f"{context.organization_id}:{context.project_id}:{processing_run_id}",
        )

    @staticmethod
    def _matches_processed_result(existing: DatasetContent, expected: DatasetContent) -> bool:
        return (
            existing.representation is DatasetRepresentation.PROCESSED
            and existing.test_run_id == expected.test_run_id
            and existing.test_run_revision_id == expected.test_run_revision_id
            and existing.raw_asset_id == expected.raw_asset_id
            and existing.raw_artifact_id == expected.raw_artifact_id
            and existing.data_artifact_id == expected.data_artifact_id
            and existing.data_sha256 == expected.data_sha256
            and existing.source_dataset_revision_id == expected.source_dataset_revision_id
            and existing.processing_run_id == expected.processing_run_id
            and existing.mapping == expected.mapping
            and existing.point_count == expected.point_count
        )

    def create_reference_dataset_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceDatasetSelection,
    ) -> DatasetSelectionSnapshot:
        """Create a stable Selection and first immutable one-member revision.

        The narrow one-member shape is intentional for the reference vertical slice.  It records
        one concrete normalized or processed revision rather than a moving Dataset head and can
        be revised later with another concrete input.
        """

        _require(context, decision, Permission.DATASET_WRITE)
        label = validate_selection_label(command.selection_label)
        source = self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=command.dataset_revision_id,
        )
        if source.revision.content.representation not in (
            DatasetRepresentation.NORMALIZED,
            DatasetRepresentation.PROCESSED,
        ):
            raise DatasetConflict(
                "reference Dataset Selection requires a normalized or processed Dataset revision"
            )
        if source.revision.record.scope.classification != command.classification.value:
            raise DatasetConflict("Selection classification must match its Dataset revision")
        content = ReferenceDatasetSelectionContent(
            selection_label=label,
            dataset_id=source.dataset_id,
            dataset_revision_id=source.revision.record.revision_id,
        )
        aggregate_id = uuid5(
            NAMESPACE_URL,
            "cmp:reference-dataset-selection:"
            f"{context.organization_id}:{context.project_id}:{command.classification.value}:{label}",
        )
        record = RevisionService(
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            store=self._repository.selection_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=DATASET_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_DATASET_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return DatasetSelectionSnapshot(aggregate_id, label, RevisionSnapshot(record, content))

    def revise_reference_dataset_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: ReviseReferenceDatasetSelection,
    ) -> DatasetSelectionSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        existing = self._repository.get_dataset_selection(
            context=context,
            decision=decision,
            selection_id=selection_id,
        )
        source = self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=command.dataset_revision_id,
        )
        if source.revision.content.representation not in (
            DatasetRepresentation.NORMALIZED,
            DatasetRepresentation.PROCESSED,
        ):
            raise DatasetConflict(
                "reference Dataset Selection requires a normalized or processed Dataset revision"
            )
        if source.revision.record.scope != existing.current.record.scope:
            raise DatasetConflict(
                "Selection Dataset revision is outside the Selection tenant scope"
            )
        content = ReferenceDatasetSelectionContent(
            selection_label=existing.selection_label,
            dataset_id=source.dataset_id,
            dataset_revision_id=source.revision.record.revision_id,
        )
        record = RevisionService(
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            store=self._repository.selection_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=selection_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=DATASET_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_DATASET_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return DatasetSelectionSnapshot(
            selection_id,
            existing.selection_label,
            RevisionSnapshot(record, content),
        )

    def _replicate_selection_content(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_label: str,
        dataset_revision_ids: tuple[UUID, ...],
        expected_scope: TenantScope,
    ) -> ReferenceTensileReplicateSelectionContent:
        if len(set(dataset_revision_ids)) != len(dataset_revision_ids):
            raise InvalidDatasetData("replicate Selection Dataset revisions must be distinct")
        members: list[ReferenceTensileReplicateSelectionMember] = []
        material_state_id: UUID | None = None
        test_run_revision_ids: set[UUID] = set()
        for ordinal, dataset_revision_id in enumerate(dataset_revision_ids):
            source = self._repository.get_calibration_dataset_source(
                context=context,
                decision=decision,
                dataset_revision_id=dataset_revision_id,
            )
            revision = source.dataset.revision
            if revision.record.scope != expected_scope:
                raise DatasetConflict(
                    "replicate Selection members must share its tenant and classification scope"
                )
            if revision.content.representation not in (
                DatasetRepresentation.NORMALIZED,
                DatasetRepresentation.PROCESSED,
            ):
                raise DatasetConflict(
                    "replicate Selection requires normalized or processed Dataset revisions"
                )
            if material_state_id is None:
                material_state_id = source.material_state_id
            elif source.material_state_id != material_state_id:
                raise DatasetConflict(
                    "replicate Selection members must belong to one Material State"
                )
            if revision.content.test_run_revision_id in test_run_revision_ids:
                raise DatasetConflict(
                    "replicate Selection members must come from distinct Test Run revisions"
                )
            test_run_revision_ids.add(revision.content.test_run_revision_id)
            members.append(
                ReferenceTensileReplicateSelectionMember(
                    ordinal=ordinal,
                    dataset_id=source.dataset.dataset_id,
                    dataset_revision_id=revision.record.revision_id,
                    test_run_id=revision.content.test_run_id,
                    test_run_revision_id=revision.content.test_run_revision_id,
                )
            )
        return ReferenceTensileReplicateSelectionContent(
            selection_label=selection_label,
            members=tuple(members),
        )

    def create_reference_tensile_replicate_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileReplicateSelection,
    ) -> TensileReplicateSelectionSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        label = validate_selection_label(command.selection_label)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        content = self._replicate_selection_content(
            context=context,
            decision=decision,
            selection_label=label,
            dataset_revision_ids=command.dataset_revision_ids,
            expected_scope=scope,
        )
        aggregate_id = uuid5(
            NAMESPACE_URL,
            "cmp:reference-tensile-replicate-selection:"
            f"{context.organization_id}:{context.project_id}:"
            f"{command.classification.value}:{label}",
        )
        record = RevisionService(
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            store=self._repository.replicate_selection_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=scope,
                schema_id=TENSILE_REPLICATE_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_REPLICATE_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TensileReplicateSelectionSnapshot(
            aggregate_id,
            label,
            RevisionSnapshot(record, content),
        )

    def revise_reference_tensile_replicate_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: ReviseReferenceTensileReplicateSelection,
    ) -> TensileReplicateSelectionSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        existing = self._repository.get_tensile_replicate_selection(
            context=context,
            decision=decision,
            selection_id=selection_id,
        )
        content = self._replicate_selection_content(
            context=context,
            decision=decision,
            selection_label=existing.selection_label,
            dataset_revision_ids=command.dataset_revision_ids,
            expected_scope=existing.current.record.scope,
        )
        record = RevisionService(
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            store=self._repository.replicate_selection_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=selection_id,
                scope=existing.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=TENSILE_REPLICATE_SELECTION_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_REPLICATE_SELECTION_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TensileReplicateSelectionSnapshot(
            selection_id,
            existing.selection_label,
            RevisionSnapshot(record, content),
        )

    def get_reference_tensile_replicate_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> TensileReplicateSelectionSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_tensile_replicate_selection(
            context=context,
            decision=decision,
            selection_id=selection_id,
        )

    def list_reference_tensile_replicate_selections(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TensileReplicateSelectionSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_tensile_replicate_selections_for_material_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def get_reference_dataset_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> DatasetSelectionSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def get_reference_dataset_selection_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> DatasetSelectionSnapshot:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def get_reference_dataset_selection_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )

    def get_reference_dataset_selection_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        """Resolve a concrete Selection input for an authorized Statistics command."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )

    def get_reference_dataset_selection_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        """Resolve one immutable Selection input for an authorized calibration command."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )

    def get_reference_dataset_selection_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> DatasetSelectionRevisionSnapshot:
        """Resolve one immutable Selection input for an authorized Validation command."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )

    def list_reference_dataset_selections_for_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> tuple[DatasetSelectionSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_dataset_selections_for_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_dataset_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_dataset_revision_for_statistics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        """Resolve a concrete Dataset input for an authorized Statistics command."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_dataset_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        """Resolve immutable normalized/processed curve metadata for Calibration."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_dataset_revision_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        """Resolve one immutable normalized/processed Dataset input for Validation.

        Validation receives the typed snapshot through the Dataset application boundary rather
        than reaching into Dataset persistence for an Artifact pointer.
        """

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_calibration_dataset_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource:
        """Resolve Dataset-to-Material-State lineage for Calibration without table leakage."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_calibration_dataset_source(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def get_dataset_source_for_validation(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource:
        """Resolve Dataset-to-Material-State lineage without exposing persistence to Validation."""

        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_calibration_dataset_source(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )

    def register_processed_reference_tensile_dataset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterProcessedReferenceTensileDataset,
    ) -> DatasetSnapshot:
        """Create the processed Dataset identity owned by the Dataset bounded module.

        A committed Processing Run is a semantic derivation, not an edit of its normalized input,
        so this always creates revision 1 of a separate stable Dataset identity.
        """

        _require_capability(context, decision, Permission.DATASET_WRITE)
        source = self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=command.source_dataset_revision_id,
        )
        source_content = source.revision.content
        if source_content.representation is not DatasetRepresentation.NORMALIZED:
            raise DatasetConflict(
                "processed reference Dataset must derive from a normalized Dataset revision"
            )
        artifact = command.artifact
        if (
            artifact.integrity_status is not IntegrityStatus.VERIFIED
            or artifact.artifact.artifact_kind is not ArtifactKind.DERIVED
            or artifact.artifact.schema_ref != REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA
            or artifact.artifact.media_type != "application/vnd.apache.parquet"
            or artifact.artifact.organization_id != context.organization_id
            or artifact.artifact.project_id != context.project_id
            or artifact.artifact.classification.value != source.revision.record.scope.classification
        ):
            raise DatasetConflict(
                "processed Dataset requires a verified derived reference Parquet Artifact"
            )
        if not 2 <= command.point_count <= MAX_REFERENCE_TENSILE_POINTS:
            raise InvalidDatasetData("processed reference Dataset must contain 2..100000 points")
        dataset_id = self._processed_dataset_id(context, command.processing_run_id)
        content = DatasetContent(
            test_run_id=source_content.test_run_id,
            test_run_revision_id=source_content.test_run_revision_id,
            raw_asset_id=source_content.raw_asset_id,
            raw_artifact_id=source_content.raw_artifact_id,
            data_artifact_id=artifact.artifact.id,
            data_sha256=artifact.artifact.sha256,
            representation=DatasetRepresentation.PROCESSED,
            source_dataset_revision_id=source.revision.record.revision_id,
            point_count=command.point_count,
            mapping=source_content.mapping,
            processing_run_id=command.processing_run_id,
        )
        scope = source.revision.record.scope
        service = RevisionService(
            aggregate_type=DATASET_AGGREGATE_TYPE,
            store=self._repository.dataset_store(context, decision),
        )
        try:
            record = service.create(
                CreateRevisionedAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    schema_id=DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                    content=content,
                    created_by=context.principal.id,
                    change_reason=command.change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if not self._matches_processed_result(existing.current.content, content):
                raise DatasetConflict(
                    "processed Dataset identity is already bound to different immutable output"
                ) from error
            return existing
        return DatasetSnapshot(
            dataset_id,
            content.test_run_id,
            RevisionSnapshot(record, content),
        )

    async def import_reference_tensile_csv(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        _require(context, decision, Permission.DATASET_WRITE)
        return await self._import_reference_tensile_csv(context, decision, command)

    async def import_reference_tensile_csv_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        """Let an authorized Processing Import Run register the same immutable Dataset output.

        This remains a public Dataset application port rather than a cross-module table write.
        The caller must carry the explicitly expanded `dataset.write` database capability granted
        by its top-level Processing command.
        """

        _require_capability(context, decision, Permission.DATASET_WRITE)
        return await self._import_reference_tensile_csv(context, decision, command)

    async def _import_reference_tensile_csv(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        run = self._repository.load_reference_test_run(
            context=context,
            decision=decision,
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
        )
        if run.test_method_code != REFERENCE_TENSILE_METHOD_CODE:
            raise DatasetConflict("reference CSV import requires the reference tensile Test Run")
        raw_record, raw_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            command.raw_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        artifact = raw_record.artifact
        if (
            artifact.artifact_kind is not ArtifactKind.RAW
            or artifact.source_raw_asset_id != command.raw_asset_id
            or artifact.media_type != "text/csv"
        ):
            raise DatasetConflict(
                "reference CSV import requires the completed text/csv Artifact "
                "for the named Raw Asset"
            )
        if (
            artifact.organization_id != context.organization_id
            or artifact.project_id != context.project_id
            or artifact.classification is not run.classification
        ):
            raise DatasetConflict("Raw Asset classification or tenant differs from the Test Run")
        parsed = parse_reference_tensile_csv(raw_bytes, command.mapping)
        dataset_id = self._dataset_id(context, command)
        scope = TenantScope(context.organization_id, context.project_id, run.classification.value)
        raw_content = DatasetContent(
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            data_artifact_id=command.raw_artifact_id,
            data_sha256=artifact.sha256,
            representation=DatasetRepresentation.RAW,
            source_dataset_revision_id=None,
            point_count=len(parsed.raw_points),
            mapping=command.mapping,
        )
        service = RevisionService(
            aggregate_type=DATASET_AGGREGATE_TYPE,
            store=self._repository.dataset_store(context, decision),
        )
        try:
            raw_record_revision = service.create(
                CreateRevisionedAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    schema_id=DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                    content=raw_content,
                    created_by=context.principal.id,
                    change_reason=command.change_reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if existing.current.content.representation is DatasetRepresentation.NORMALIZED:
                # The immutable pair was already completed by an equivalent request.
                if not self._matches_source(existing.current.content, raw_content):
                    raise DatasetConflict(
                        "deterministic Dataset identity is already bound to a different source"
                    ) from error
                return existing
            if not self._matches_raw_input(existing.current.content, raw_content):
                raise DatasetConflict(
                    "deterministic Dataset identity is already bound to a different raw source"
                ) from error
            raw_record_revision = existing.current.record
        normalized_bytes = normalized_parquet_bytes(parsed.normalized_points)
        derived = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=run.classification,
            artifact_role="dataset.normalized_curve",
            schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=normalized_bytes,
            idempotency_key=(
                f"dataset:{command.test_run_revision_id}:{command.raw_artifact_id}:"
                f"{command.mapping.digest}"
            ),
        )
        normalized_content = DatasetContent(
            test_run_id=command.test_run_id,
            test_run_revision_id=command.test_run_revision_id,
            raw_asset_id=command.raw_asset_id,
            raw_artifact_id=command.raw_artifact_id,
            data_artifact_id=derived.artifact.id,
            data_sha256=derived.artifact.sha256,
            representation=DatasetRepresentation.NORMALIZED,
            source_dataset_revision_id=raw_record_revision.revision_id,
            point_count=len(parsed.normalized_points),
            mapping=command.mapping,
        )
        try:
            normalized_record = service.revise(
                ReviseAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    expected_current_revision_id=raw_record_revision.revision_id,
                    based_on_revision_id=raw_record_revision.revision_id,
                    schema_id=DATASET_SCHEMA_ID,
                    schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                    content=normalized_content,
                    created_by=context.principal.id,
                    change_reason="normalize reference tensile CSV",
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except RevisionConflict as error:
            existing = self._repository.get_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if self._matches_normalized_result(existing.current.content, normalized_content):
                return existing
            raise DatasetConflict("Dataset normalization head changed concurrently") from error
        return DatasetSnapshot(
            dataset_id,
            command.test_run_id,
            RevisionSnapshot(normalized_record, normalized_content),
        )

    def get_dataset(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.get_dataset(
            context=context, decision=decision, dataset_id=dataset_id
        )

    def list_dataset_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_dataset_revisions(
            context=context, decision=decision, dataset_id=dataset_id
        )

    def list_datasets_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]:
        _require(context, decision, Permission.DATASET_READ)
        return self._repository.list_datasets_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    async def preview_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
        *,
        maximum_points: int,
    ) -> CurvePreview:
        _require(context, decision, Permission.DATASET_READ)
        snapshot = self._repository.get_dataset_revision(
            context=context,
            decision=decision,
            dataset_revision_id=dataset_revision_id,
        )
        content = snapshot.revision.content
        _, data = await self._artifacts.read_verified_bytes(
            context,
            decision,
            content.data_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        if content.representation is DatasetRepresentation.RAW:
            parsed: ParsedReferenceTensile = parse_reference_tensile_csv(data, content.mapping)
            points = parsed.raw_points
            strain_unit = content.mapping.strain_unit
            stress_unit = content.mapping.stress_unit
        else:
            points = normalized_points_from_parquet(data)
            strain_unit = "1"
            stress_unit = "Pa"
        if len(points) != content.point_count:
            raise InvalidDatasetData("Dataset Artifact point count differs from immutable revision")
        preview = preview_points(points, maximum_points)
        return CurvePreview(
            dataset_id=snapshot.dataset_id,
            dataset_revision_id=snapshot.revision.record.revision_id,
            representation=content.representation,
            point_count=len(points),
            returned_point_count=len(preview),
            sampled=len(preview) != len(points),
            strain_unit=strain_unit,
            stress_unit=stress_unit,
            points=preview,
        )
