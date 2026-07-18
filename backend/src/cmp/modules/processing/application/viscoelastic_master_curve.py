"""Committed T-42 viscoelastic replicate statistics and master-curve workflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.datasets.application.viscoelastic_master import (
    RegisterViscoelasticDerivedDataset,
    ViscoelasticDatasetService,
    ViscoelasticDerivedDatasetSnapshot,
    ViscoelasticSelectionSnapshot,
)
from cmp.modules.datasets.application.viscoelastic_master import (
    RevisionSnapshot as DatasetRevisionSnapshot,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    shear_relaxation_points_from_parquet,
)
from cmp.modules.datasets.domain.viscoelastic_master import (
    ViscoelasticDerivedRepresentation,
    ViscoelasticSelectionContent,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingConflict,
    ProcessingRunStatus,
)
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    VISCOELASTIC_ALIGNED_PARQUET_SCHEMA,
    VISCOELASTIC_MASTER_PARQUET_SCHEMA,
    VISCOELASTIC_MASTER_PLAN_SCHEMA_ID,
    VISCOELASTIC_MASTER_SCHEMA_VERSION,
    VISCOELASTIC_STATISTICS_PARQUET_SCHEMA,
    AlignedCurve,
    MasterCurvePoint,
    ReplicateCurve,
    ShiftFactorEvidence,
    TemperatureStatistics,
    ViscoelasticMasterPlanContent,
    ViscoelasticMasterResult,
    aligned_replicates_from_parquet,
    aligned_replicates_parquet_bytes,
    compute_viscoelastic_master_curve,
    master_curve_from_parquet,
    master_curve_parquet_bytes,
    temperature_statistics_from_parquet,
    temperature_statistics_parquet_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE = "processing.viscoelastic_master_plan"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot:
    record: RevisionRecord
    content: ViscoelasticMasterPlanContent


@dataclass(frozen=True, slots=True)
class ViscoelasticMasterPlanSnapshot:
    id: UUID
    current: RevisionSnapshot


@dataclass(frozen=True, slots=True)
class ViscoelasticMasterRun:
    id: UUID
    scope: TenantScope
    plan_id: UUID
    plan_revision_id: UUID
    selection_id: UUID
    selection_revision_id: UUID
    status: ProcessingRunStatus
    source_curve_count: int
    temperature_count: int
    aligned_row_count: int | None
    statistics_row_count: int | None
    master_row_count: int | None
    aligned_dataset_id: UUID | None
    aligned_dataset_revision_id: UUID | None
    statistics_dataset_id: UUID | None
    statistics_dataset_revision_id: UUID | None
    master_dataset_id: UUID | None
    master_dataset_revision_id: UUID | None
    wlf_c1: float | None
    wlf_c2_k: float | None
    arrhenius_activation_energy_j_per_mol: float | None
    shift_factors: tuple[ShiftFactorEvidence, ...]
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str


@dataclass(frozen=True, slots=True)
class ViscoelasticMasterPreview:
    run: ViscoelasticMasterRun
    selection: DatasetRevisionSnapshot[ViscoelasticSelectionContent]
    aligned_curves: tuple[AlignedCurve, ...]
    temperature_statistics: tuple[TemperatureStatistics, ...]
    master_curve: tuple[MasterCurvePoint, ...]


@dataclass(frozen=True, slots=True)
class CreateViscoelasticMasterPlan:
    classification: DataClassification
    content: ViscoelasticMasterPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteViscoelasticMasterPlan:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class ViscoelasticMasterRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ViscoelasticMasterPlanContent]: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ViscoelasticMasterRun,
    ) -> ViscoelasticMasterRun: ...

    def succeed_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        result: ViscoelasticMasterResult,
        aligned: ViscoelasticDerivedDatasetSnapshot,
        statistics: ViscoelasticDerivedDatasetSnapshot,
        master: ViscoelasticDerivedDatasetSnapshot,
    ) -> ViscoelasticMasterRun: ...

    def fail_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        failure_code: str,
    ) -> ViscoelasticMasterRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ViscoelasticMasterRun: ...


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
        raise ProcessingConflict("authorization capability does not match Processing request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class ViscoelasticMasterService:
    def __init__(
        self,
        *,
        repository: ViscoelasticMasterRepository,
        datasets: ViscoelasticDatasetService,
        shear_datasets: ShearRelaxationDatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._shear_datasets = shear_datasets
        self._artifacts = artifacts
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateViscoelasticMasterPlan,
    ) -> ViscoelasticMasterPlanSnapshot:
        _require_capability(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        selection = self._datasets.get_selection_revision_for_processing(
            context,
            decision,
            command.content.selection_id,
            command.content.selection_revision_id,
        )
        if selection.record.scope.classification != command.classification.value:
            raise ProcessingConflict("Plan classification must match the pinned Selection")
        plan_id = self._id_factory()
        record = RevisionService(
            aggregate_type=VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=selection.record.scope,
                schema_id=VISCOELASTIC_MASTER_PLAN_SCHEMA_ID,
                schema_version=VISCOELASTIC_MASTER_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ViscoelasticMasterPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteViscoelasticMasterPlan,
    ) -> ViscoelasticMasterRun:
        _require_capability(context, decision, Permission.PROCESSING_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        selection_revision = self._datasets.get_selection_revision_for_processing(
            context,
            decision,
            plan.content.selection_id,
            plan.content.selection_revision_id,
        )
        if plan.record.scope != selection_revision.record.scope:
            raise ProcessingConflict("Plan and Selection revisions must share exact scope")
        selection = ViscoelasticSelectionSnapshot(
            plan.content.selection_id, selection_revision
        )
        curves: list[ReplicateCurve] = []
        for member in selection_revision.content.members:
            dataset = self._shear_datasets.get_revision_for_processing(
                context,
                decision,
                member.dataset_id,
                member.dataset_revision_id,
            )
            if (
                dataset.content.test_run_id != member.test_run_id
                or dataset.content.test_run_revision_id != member.test_run_revision_id
                or dataset.record.scope != plan.record.scope
            ):
                raise ProcessingConflict("Selection member evidence no longer resolves exactly")
            _, value = await self._artifacts.read_verified_bytes(
                context,
                decision,
                dataset.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            points = shear_relaxation_points_from_parquet(value)
            if len(points) != dataset.content.point_count:
                raise ProcessingConflict("Dataset point count differs from its Artifact")
            curves.append(
                ReplicateCurve(
                    member_ordinal=member.ordinal,
                    dataset_revision_id=member.dataset_revision_id,
                    test_run_revision_id=member.test_run_revision_id,
                    temperature_k=member.temperature_k,
                    points=points,
                )
            )
        run = ViscoelasticMasterRun(
            id=self._id_factory(),
            scope=plan.record.scope,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            selection_id=selection.id,
            selection_revision_id=selection_revision.record.revision_id,
            status=ProcessingRunStatus.EXECUTING,
            source_curve_count=len(curves),
            temperature_count=len({curve.temperature_k for curve in curves}),
            aligned_row_count=None,
            statistics_row_count=None,
            master_row_count=None,
            aligned_dataset_id=None,
            aligned_dataset_revision_id=None,
            statistics_dataset_id=None,
            statistics_dataset_revision_id=None,
            master_dataset_id=None,
            master_dataset_revision_id=None,
            wlf_c1=None,
            wlf_c2_k=None,
            arrhenius_activation_energy_j_per_mol=None,
            shift_factors=(),
            failure_code=None,
            change_reason=reason,
            started_at=self._clock(),
            ended_at=None,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        created = self._repository.create_run(
            context=context, decision=decision, run=run
        )
        try:
            result = compute_viscoelastic_master_curve(tuple(curves), plan.content)
            output_specs = (
                (
                    ViscoelasticDerivedRepresentation.ALIGNED,
                    "dataset.viscoelastic_aligned",
                    VISCOELASTIC_ALIGNED_PARQUET_SCHEMA,
                    aligned_replicates_parquet_bytes(result),
                    sum(len(curve.points) for curve in result.aligned_curves),
                ),
                (
                    ViscoelasticDerivedRepresentation.STATISTICS,
                    "dataset.viscoelastic_statistics",
                    VISCOELASTIC_STATISTICS_PARQUET_SCHEMA,
                    temperature_statistics_parquet_bytes(result),
                    sum(len(item.points) for item in result.temperature_statistics),
                ),
                (
                    ViscoelasticDerivedRepresentation.MASTER_CURVE,
                    "dataset.viscoelastic_master_curve",
                    VISCOELASTIC_MASTER_PARQUET_SCHEMA,
                    master_curve_parquet_bytes(result),
                    len(result.master_curve),
                ),
            )
            outputs: dict[
                ViscoelasticDerivedRepresentation, ViscoelasticDerivedDatasetSnapshot
            ] = {}
            for representation, role, schema_ref, value, row_count in output_specs:
                artifact = await self._artifacts.finalize_derived_bytes(
                    context,
                    decision,
                    classification=DataClassification(plan.record.scope.classification),
                    artifact_role=role,
                    schema_ref=schema_ref,
                    media_type="application/vnd.apache.parquet",
                    value=value,
                    idempotency_key=f"processing:{created.id}:{representation.value}",
                )
                outputs[representation] = self._datasets.register_derived(
                    context,
                    decision,
                    RegisterViscoelasticDerivedDataset(
                        selection=selection,
                        processing_plan_id=command.plan_id,
                        processing_plan_revision_id=command.plan_revision_id,
                        processing_run_id=created.id,
                        representation=representation,
                        artifact=artifact,
                        row_count=row_count,
                        reference_temperature_k=plan.content.reference_temperature_k,
                        schema_ref=schema_ref,
                        change_reason=reason,
                    ),
                )
            return self._repository.succeed_run(
                context=context,
                decision=decision,
                run_id=created.id,
                result=result,
                aligned=outputs[ViscoelasticDerivedRepresentation.ALIGNED],
                statistics=outputs[ViscoelasticDerivedRepresentation.STATISTICS],
                master=outputs[ViscoelasticDerivedRepresentation.MASTER_CURVE],
            )
        except Exception:
            try:
                self._repository.fail_run(
                    context=context,
                    decision=decision,
                    run_id=created.id,
                    failure_code="viscoelastic_master_processing_failed",
                )
            except Exception:
                pass
            raise

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ViscoelasticMasterRun:
        _require_capability(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_run(
            context=context, decision=decision, run_id=run_id
        )

    async def preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ViscoelasticMasterPreview:
        _require_capability(context, decision, Permission.PROCESSING_READ)
        run = self._repository.get_run(
            context=context, decision=decision, run_id=run_id
        )
        if run.status is not ProcessingRunStatus.SUCCEEDED:
            raise ProcessingConflict("only a succeeded master-curve Run can be previewed")
        selection = self._datasets.get_selection_revision_for_processing(
            context,
            decision,
            run.selection_id,
            run.selection_revision_id,
        )
        aligned_id = run.aligned_dataset_id
        statistics_id = run.statistics_dataset_id
        master_id = run.master_dataset_id
        if aligned_id is None or statistics_id is None or master_id is None:
            raise ProcessingConflict("succeeded Run output Dataset links are incomplete")
        aligned_dataset = self._datasets.get_derived_dataset_for_processing(
            context, decision, aligned_id
        )
        statistics_dataset = self._datasets.get_derived_dataset_for_processing(
            context, decision, statistics_id
        )
        master_dataset = self._datasets.get_derived_dataset_for_processing(
            context, decision, master_id
        )
        values: list[bytes] = []
        for dataset in (aligned_dataset, statistics_dataset, master_dataset):
            _, value = await self._artifacts.read_verified_bytes(
                context,
                decision,
                dataset.current.content.data_artifact_id,
                maximum_bytes=32 * 1024 * 1024,
            )
            values.append(value)
        evidence = {
            item.ordinal: (item.dataset_revision_id, item.test_run_revision_id)
            for item in selection.content.members
        }
        return ViscoelasticMasterPreview(
            run=run,
            selection=selection,
            aligned_curves=aligned_replicates_from_parquet(values[0], evidence),
            temperature_statistics=temperature_statistics_from_parquet(values[1]),
            master_curve=master_curve_from_parquet(values[2]),
        )
