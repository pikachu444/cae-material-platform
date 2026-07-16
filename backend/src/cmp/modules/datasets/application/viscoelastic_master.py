"""Immutable viscoelastic Selections and derived Dataset revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from cmp.modules.artifacts.domain.content import ArtifactKind, ArtifactRecord, IntegrityStatus
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.datasets.domain.viscoelastic_master import (
    VISCOELASTIC_DATASET_SCHEMA_VERSION,
    VISCOELASTIC_DERIVED_DATASET_SCHEMA_ID,
    VISCOELASTIC_SELECTION_SCHEMA_ID,
    InvalidViscoelasticDataset,
    ViscoelasticDerivedDatasetContent,
    ViscoelasticDerivedRepresentation,
    ViscoelasticSelectionContent,
    ViscoelasticSelectionMember,
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
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionRecord, TenantScope

VISCOELASTIC_SELECTION_AGGREGATE_TYPE = "datasets.viscoelastic_selection"
VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE = "datasets.viscoelastic_derived_dataset"


class ViscoelasticDatasetNotFound(Exception):
    """A tenant-scoped Selection or derived Dataset is not visible."""


class ViscoelasticDatasetConflict(Exception):
    """Pinned Dataset evidence conflicts with the requested operation."""


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ViscoelasticSelectionSnapshot:
    id: UUID
    current: RevisionSnapshot[ViscoelasticSelectionContent]


@dataclass(frozen=True, slots=True)
class ViscoelasticDerivedDatasetSnapshot:
    id: UUID
    current: RevisionSnapshot[ViscoelasticDerivedDatasetContent]


@dataclass(frozen=True, slots=True)
class ViscoelasticSelectionMemberRef:
    dataset_id: UUID
    dataset_revision_id: UUID


@dataclass(frozen=True, slots=True)
class CreateViscoelasticSelection:
    classification: DataClassification
    selection_label: str
    members: tuple[ViscoelasticSelectionMemberRef, ...]
    change_reason: str


@dataclass(frozen=True, slots=True)
class RegisterViscoelasticDerivedDataset:
    selection: ViscoelasticSelectionSnapshot
    processing_plan_id: UUID
    processing_plan_revision_id: UUID
    processing_run_id: UUID
    representation: ViscoelasticDerivedRepresentation
    artifact: ArtifactRecord
    row_count: int
    reference_temperature_k: float
    schema_ref: str
    change_reason: str


class ViscoelasticDatasetRepository(Protocol):
    def selection_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ViscoelasticSelectionContent]: ...

    def derived_dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ViscoelasticDerivedDatasetContent]: ...

    def get_selection(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ViscoelasticSelectionSnapshot: ...

    def get_selection_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ViscoelasticSelectionContent]: ...

    def list_selections(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ViscoelasticSelectionSnapshot, ...]: ...

    def get_derived_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> ViscoelasticDerivedDatasetSnapshot: ...


def _require_capability(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise ViscoelasticDatasetConflict("authorization capability does not match request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise InvalidViscoelasticDataset(
            "change_reason must be trimmed and contain 1..2000 characters"
        )
    return value


class ViscoelasticDatasetService:
    def __init__(
        self,
        *,
        repository: ViscoelasticDatasetRepository,
        shear_datasets: ShearRelaxationDatasetService,
        testing: TestingService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._shear_datasets = shear_datasets
        self._testing = testing
        self._id_factory = id_factory

    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateViscoelasticSelection,
    ) -> ViscoelasticSelectionSnapshot:
        _require_capability(context, decision, Permission.DATASET_WRITE)
        reason = _reason(command.change_reason)
        if not 2 <= len(command.members) <= 50:
            raise InvalidViscoelasticDataset("Selection requires between 2 and 50 members")
        resolved: list[ViscoelasticSelectionMember] = []
        material_state_id: UUID | None = None
        material_state_revision_id: UUID | None = None
        scope: TenantScope | None = None
        for ordinal, member in enumerate(command.members):
            dataset = self._shear_datasets.get_revision_for_processing(
                context,
                decision,
                member.dataset_id,
                member.dataset_revision_id,
            )
            if dataset.content.representation not in {"normalized", "processed"}:
                raise ViscoelasticDatasetConflict(
                    "Selection members must be normalized or processed shear-relaxation revisions"
                )
            test_run = self._testing.get_test_run_revision_for_processing(
                context,
                decision,
                dataset.content.test_run_id,
                dataset.content.test_run_revision_id,
            )
            temperature_k = test_run.content.test_temperature_k
            if temperature_k is None:
                raise ViscoelasticDatasetConflict(
                    "every selected Test Run requires an exact temperature condition"
                )
            if scope is None:
                scope = dataset.record.scope
                material_state_id = dataset.content.material_state_id
                material_state_revision_id = dataset.content.material_state_revision_id
            elif (
                dataset.record.scope != scope
                or dataset.content.material_state_id != material_state_id
                or dataset.content.material_state_revision_id != material_state_revision_id
            ):
                raise ViscoelasticDatasetConflict(
                    "Selection members must share scope and exact Material State revision"
                )
            resolved.append(
                ViscoelasticSelectionMember(
                    ordinal=ordinal,
                    dataset_id=member.dataset_id,
                    dataset_revision_id=member.dataset_revision_id,
                    test_run_id=dataset.content.test_run_id,
                    test_run_revision_id=dataset.content.test_run_revision_id,
                    temperature_k=temperature_k,
                )
            )
        if scope is None or material_state_id is None or material_state_revision_id is None:
            raise InvalidViscoelasticDataset("Selection has no members")
        if scope.classification != command.classification.value:
            raise ViscoelasticDatasetConflict("Selection classification must match its members")
        content = ViscoelasticSelectionContent(
            selection_label=command.selection_label,
            material_state_id=material_state_id,
            material_state_revision_id=material_state_revision_id,
            members=tuple(resolved),
        )
        selection_id = self._id_factory()
        record = RevisionService(
            aggregate_type=VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
            store=self._repository.selection_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=selection_id,
                scope=scope,
                schema_id=VISCOELASTIC_SELECTION_SCHEMA_ID,
                schema_version=VISCOELASTIC_DATASET_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ViscoelasticSelectionSnapshot(selection_id, RevisionSnapshot(record, content))

    def get_selection_revision_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> RevisionSnapshot[ViscoelasticSelectionContent]:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_selection_revision(
            context=context,
            decision=decision,
            selection_id=selection_id,
            selection_revision_id=selection_revision_id,
        )
    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ViscoelasticSelectionSnapshot:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_selection(
            context=context, decision=decision, selection_id=selection_id
        )

    def list_selections(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ViscoelasticSelectionSnapshot, ...]:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.list_selections(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def register_derived(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterViscoelasticDerivedDataset,
    ) -> ViscoelasticDerivedDatasetSnapshot:
        _require_capability(context, decision, Permission.DATASET_WRITE)
        reason = _reason(command.change_reason)
        artifact = command.artifact
        expected_role = {
            ViscoelasticDerivedRepresentation.ALIGNED: "dataset.viscoelastic_aligned",
            ViscoelasticDerivedRepresentation.STATISTICS: "dataset.viscoelastic_statistics",
            ViscoelasticDerivedRepresentation.MASTER_CURVE: "dataset.viscoelastic_master_curve",
        }[command.representation]
        scope = command.selection.current.record.scope
        if (
            artifact.integrity_status is not IntegrityStatus.VERIFIED
            or artifact.artifact.artifact_kind is not ArtifactKind.DERIVED
            or artifact.artifact.artifact_role != expected_role
            or artifact.artifact.schema_ref != command.schema_ref
            or artifact.artifact.media_type != "application/vnd.apache.parquet"
            or artifact.artifact.organization_id != context.organization_id
            or artifact.artifact.project_id != context.project_id
            or artifact.artifact.classification.value != scope.classification
        ):
            raise ViscoelasticDatasetConflict(
                "derived Dataset requires a matching verified typed Parquet Artifact"
            )
        content = ViscoelasticDerivedDatasetContent(
            material_state_id=command.selection.current.content.material_state_id,
            material_state_revision_id=(
                command.selection.current.content.material_state_revision_id
            ),
            selection_id=command.selection.id,
            selection_revision_id=command.selection.current.record.revision_id,
            processing_plan_id=command.processing_plan_id,
            processing_plan_revision_id=command.processing_plan_revision_id,
            processing_run_id=command.processing_run_id,
            representation=command.representation,
            data_artifact_id=artifact.artifact.id,
            data_sha256=artifact.artifact.sha256,
            row_count=command.row_count,
            source_curve_count=len(command.selection.current.content.members),
            reference_temperature_k=command.reference_temperature_k,
            schema_ref=command.schema_ref,
        )
        dataset_id = uuid5(
            NAMESPACE_URL,
            "cmp:viscoelastic-derived-dataset:"
            f"{context.organization_id}:{context.project_id}:{command.processing_run_id}:"
            f"{command.representation.value}",
        )
        try:
            record = RevisionService(
                aggregate_type=VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE,
                store=self._repository.derived_dataset_store(context, decision),
            ).create(
                CreateRevisionedAggregate(
                    aggregate_id=dataset_id,
                    scope=scope,
                    schema_id=VISCOELASTIC_DERIVED_DATASET_SCHEMA_ID,
                    schema_version=VISCOELASTIC_DATASET_SCHEMA_VERSION,
                    content=content,
                    created_by=context.principal.id,
                    change_reason=reason,
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                )
            )
        except AggregateAlreadyExists as error:
            existing = self._repository.get_derived_dataset(
                context=context, decision=decision, dataset_id=dataset_id
            )
            if existing.current.content != content:
                raise ViscoelasticDatasetConflict(
                    "derived Dataset identity is already bound to different evidence"
                ) from error
            return existing
        return ViscoelasticDerivedDatasetSnapshot(
            dataset_id, RevisionSnapshot(record, content)
        )

    def get_derived_dataset_for_processing(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> ViscoelasticDerivedDatasetSnapshot:
        _require_capability(context, decision, Permission.DATASET_READ)
        return self._repository.get_derived_dataset(
            context=context, decision=decision, dataset_id=dataset_id
        )
