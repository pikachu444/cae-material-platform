"""Application orchestration for exact-revision multi-test Ogden calibration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.domain.governed_tabular import (
    GovernedDatasetRepresentation,
    QuantityKind,
    TabularDataSchema,
    normalized_rows_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.application.scientific_profile import ScientificProfileService
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_ogden_calibration import (
    REFERENCE_OGDEN_CALIBRATION_DIAGNOSTICS_SCHEMA,
    REFERENCE_OGDEN_CALIBRATION_ENVIRONMENT_DIGEST,
    REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_ID,
    REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_VERSION,
    OgdenCalibrationCandidate,
    OgdenCalibrationCurve,
    OgdenDiagnosticPoint,
    OgdenTestMode,
    ReferenceOgdenCalibrationPlanContent,
    calibrate_reference_ogden,
    ogden_diagnostics_from_parquet,
    ogden_diagnostics_parquet_bytes,
)
from cmp.modules.modeling.domain.scientific_profile import ScientificProfileFamily
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.modules.testing.application.service import TestingService
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE = "modeling.ogden_calibration_plan"


class OgdenCalibrationConflict(Exception):
    pass


class OgdenCalibrationNotFound(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OgdenCalibrationPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceOgdenCalibrationPlanContent]


@dataclass(frozen=True, slots=True)
class PersistedOgdenCandidate:
    id: UUID
    attempt_id: UUID
    calibration_run_id: UUID
    value: OgdenCalibrationCandidate
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    diagnostics_point_count: int
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class OgdenCalibrationRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    scientific_profile_id: UUID
    scientific_profile_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    status: ProcessingRunStatus
    environment_digest: str
    calibration_curve_count: int
    holdout_curve_count: int
    test_mode_count: int
    attempt_count: int
    candidate_count: int
    failure_code: str | None
    change_reason: str
    started_at: datetime
    ended_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str
    candidates: tuple[PersistedOgdenCandidate, ...]


@dataclass(frozen=True, slots=True)
class CreateReferenceOgdenCalibrationPlan:
    classification: DataClassification
    content: ReferenceOgdenCalibrationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ExecuteReferenceOgdenCalibration:
    plan_id: UUID
    plan_revision_id: UUID
    change_reason: str


class OgdenCalibrationRepository(Protocol):
    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceOgdenCalibrationPlanContent]: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenCalibrationPlanContent]: ...

    def save_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: OgdenCalibrationRun,
    ) -> OgdenCalibrationRun: ...

    def get_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> OgdenCalibrationRun: ...

    def get_candidate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> PersistedOgdenCandidate: ...


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
        raise OgdenCalibrationConflict(
            "authorization decision does not match Ogden calibration request"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


def _schema_for_mode(mode: OgdenTestMode) -> TabularDataSchema:
    return {
        OgdenTestMode.UNIAXIAL_TENSION: TabularDataSchema.MONOTONIC_TENSION,
        OgdenTestMode.PLANAR_TENSION: TabularDataSchema.PLANAR_TENSION,
        OgdenTestMode.BIAXIAL_TENSION: TabularDataSchema.BIAXIAL_TENSION,
    }[mode]


class ReferenceOgdenCalibrationService:
    def __init__(
        self,
        *,
        repository: OgdenCalibrationRepository,
        profiles: ScientificProfileService,
        catalog: CatalogService,
        datasets: GovernedImportService,
        testing: TestingService,
        models: OgdenPronyModelService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._profiles = profiles
        self._catalog = catalog
        self._datasets = datasets
        self._testing = testing
        self._models = models
        self._artifacts = artifacts
        self._id = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceOgdenCalibrationPlan,
    ) -> OgdenCalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        content = command.content
        profile = self._profiles.get_revision_for_calibration(
            context,
            decision,
            content.scientific_profile_id,
            content.scientific_profile_revision_id,
        )
        state = self._catalog.get_material_state_revision_for_calibration(
            context,
            decision,
            content.material_state_id,
            content.material_state_revision_id,
        )
        baseline = self._models.get_model_revision_for_calibration(
            context,
            decision,
            content.baseline_model_id,
            content.baseline_model_revision_id,
        )
        if profile.content.family is not ScientificProfileFamily.ELASTOMER_OGDEN_PRONY:
            raise OgdenCalibrationConflict("Ogden calibration requires an elastomer profile")
        if (
            profile.record.scope != state.record.scope
            or profile.record.scope != baseline.record.scope
            or profile.record.scope.classification != command.classification.value
            or baseline.content.material_state_id != content.material_state_id
            or baseline.content.material_state_revision_id != content.material_state_revision_id
        ):
            raise OgdenCalibrationConflict(
                "profile, State, baseline IR, and Plan classification must share exact scope"
            )
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=OGDEN_CALIBRATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_OGDEN_CALIBRATION_PLAN_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return OgdenCalibrationPlanSnapshot(plan_id, RevisionSnapshot(record, content))

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteReferenceOgdenCalibration,
    ) -> OgdenCalibrationRun:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        profile = self._profiles.get_revision_for_calibration(
            context,
            decision,
            plan.content.scientific_profile_id,
            plan.content.scientific_profile_revision_id,
        )
        baseline = self._models.get_model_revision_for_calibration(
            context,
            decision,
            plan.content.baseline_model_id,
            plan.content.baseline_model_revision_id,
        )
        if profile.record.scope != plan.record.scope or baseline.record.scope != plan.record.scope:
            raise OgdenCalibrationConflict("Plan inputs no longer resolve in the exact scope")
        parameters = profile.content.ogden
        if parameters is None:
            raise OgdenCalibrationConflict("pinned scientific profile has no Ogden parameters")

        curves: list[OgdenCalibrationCurve] = []
        for member in plan.content.members:
            dataset = self._datasets.get_dataset_revision_for_calibration(
                context,
                decision,
                member.dataset_id,
                member.dataset_revision_id,
            )
            test_run = self._testing.get_test_run_revision_for_processing(
                context,
                decision,
                dataset.content.test_run_id,
                dataset.content.test_run_revision_id,
            )
            specimen_classification, specimen = (
                self._testing.get_specimen_revision_for_processing(
                    context,
                    decision,
                    test_run.content.specimen_id,
                    test_run.content.specimen_revision_id,
                )
            )
            if (
                dataset.record.scope != plan.record.scope
                or test_run.record.scope != plan.record.scope
                or specimen_classification.value != plan.record.scope.classification
                or specimen.material_state_id != plan.content.material_state_id
                or specimen.material_state_revision_id
                != plan.content.material_state_revision_id
                or dataset.content.representation
                is not GovernedDatasetRepresentation.NORMALIZED
                or dataset.content.data_schema is not _schema_for_mode(member.test_mode)
                or dataset.content.test_run_id != test_run.record.aggregate_id
            ):
                raise OgdenCalibrationConflict(
                    "Dataset, Test Run, Specimen, mode, and Material State evidence conflict"
                )
            artifact_record, value = await self._artifacts.read_verified_bytes(
                context,
                decision,
                dataset.content.data_artifact_id,
                maximum_bytes=16 * 1024 * 1024,
            )
            if artifact_record.artifact.sha256 != dataset.content.data_sha256:
                raise OgdenCalibrationConflict("normalized Dataset Artifact digest conflicts")
            normalized = normalized_rows_from_parquet(value, dataset.content)
            if normalized.columns != (
                QuantityKind.ENGINEERING_STRAIN,
                QuantityKind.ENGINEERING_STRESS,
            ):
                raise OgdenCalibrationConflict(
                    "Ogden adapters require normalized engineering strain and nominal stress"
                )
            curves.append(
                OgdenCalibrationCurve(
                    member,
                    tuple(row[0] for row in normalized.rows),
                    tuple(row[1] for row in normalized.rows),
                )
            )

        candidates = calibrate_reference_ogden(
            parameters=parameters,
            multistart_count=profile.content.multistart_count,
            seed=profile.content.seed,
            maximum_function_evaluations=plan.content.maximum_function_evaluations,
            curves=tuple(curves),
        )
        run_id = self._id()
        started_at = self._clock()
        persisted: list[PersistedOgdenCandidate] = []
        for candidate in candidates:
            artifact = await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=DataClassification(plan.record.scope.classification),
                artifact_role="modeling.reference_ogden_candidate_diagnostics",
                schema_ref=REFERENCE_OGDEN_CALIBRATION_DIAGNOSTICS_SCHEMA,
                media_type="application/vnd.apache.parquet",
                value=ogden_diagnostics_parquet_bytes(candidate),
                idempotency_key=(
                    f"ogden-calibration:{run_id}:attempt:{candidate.attempt_ordinal}"
                ),
            )
            persisted.append(
                PersistedOgdenCandidate(
                    id=self._id(),
                    attempt_id=self._id(),
                    calibration_run_id=run_id,
                    value=candidate,
                    diagnostics_artifact_id=artifact.artifact.id,
                    diagnostics_sha256=artifact.artifact.sha256,
                    diagnostics_point_count=len(candidate.diagnostics),
                    created_at=self._clock(),
                    created_by=context.principal.id,
                )
            )
        run = OgdenCalibrationRun(
            id=run_id,
            classification=DataClassification(plan.record.scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            scientific_profile_id=plan.content.scientific_profile_id,
            scientific_profile_revision_id=plan.content.scientific_profile_revision_id,
            material_state_id=plan.content.material_state_id,
            material_state_revision_id=plan.content.material_state_revision_id,
            baseline_model_id=plan.content.baseline_model_id,
            baseline_model_revision_id=plan.content.baseline_model_revision_id,
            status=ProcessingRunStatus.SUCCEEDED,
            environment_digest=REFERENCE_OGDEN_CALIBRATION_ENVIRONMENT_DIGEST,
            calibration_curve_count=sum(
                curve.member.role.value == "calibration" for curve in curves
            ),
            holdout_curve_count=sum(curve.member.role.value == "holdout" for curve in curves),
            test_mode_count=len({curve.member.test_mode for curve in curves}),
            attempt_count=len(candidates),
            candidate_count=len(candidates),
            failure_code=None,
            change_reason=reason,
            started_at=started_at,
            ended_at=self._clock(),
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            candidates=tuple(persisted),
        )
        return self._repository.save_run(context=context, decision=decision, run=run)

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> OgdenCalibrationRun:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_run(context=context, decision=decision, run_id=run_id)

    async def candidate_diagnostics(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        candidate_id: UUID,
    ) -> tuple[OgdenDiagnosticPoint, ...]:
        _require(context, decision, Permission.MODELING_READ)
        candidate = self._repository.get_candidate(
            context=context,
            decision=decision,
            candidate_id=candidate_id,
        )
        _, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            candidate.diagnostics_artifact_id,
            maximum_bytes=16 * 1024 * 1024,
        )
        points = ogden_diagnostics_from_parquet(value)
        if len(points) != candidate.diagnostics_point_count:
            raise OgdenCalibrationConflict(
                "candidate diagnostics point count differs from immutable Artifact"
            )
        return points
