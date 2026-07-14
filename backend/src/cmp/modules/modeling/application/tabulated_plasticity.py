"""Build one typed tabulated-plasticity IR from a pinned tensile Dataset revision."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA,
    DatasetRepresentation,
    normalized_points_from_parquet,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    REFERENCE_HARDENING_CURVE_SCHEMA,
    REFERENCE_TABULATED_PLASTICITY_IR_SCHEMA_ID,
    REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
    HardeningCurvePoint,
    ReferenceIsotropicTabulatedPlasticityContent,
    TabulatedPlasticityConflict,
    derive_reference_isotropic_hardening_curve,
    hardening_curve_from_parquet,
    hardening_curve_parquet_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import TenantScope

MAX_REFERENCE_TENSILE_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_REFERENCE_HARDENING_ARTIFACT_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CreateReferenceTabulatedPlasticityModel:
    material_state_id: UUID
    property_set_revision_id: UUID
    dataset_revision_id: UUID
    extension_max_true_plastic_strain: float
    acknowledge_post_necking_approximation: bool
    change_reason: str


@dataclass(frozen=True, slots=True)
class TabulatedPlasticityModelSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[ReferenceIsotropicTabulatedPlasticityContent]


class TabulatedPlasticityRepository(Protocol):
    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceIsotropicTabulatedPlasticityContent]: ...

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> TabulatedPlasticityModelSnapshot: ...

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TabulatedPlasticityModelSnapshot, ...]: ...

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceIsotropicTabulatedPlasticityContent]: ...


def _require_decision(
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
        raise TabulatedPlasticityConflict(
            "authorization decision does not match tabulated-plasticity request"
        )


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
        raise TabulatedPlasticityConflict(
            "authorization decision lacks the tabulated-plasticity capability"
        )


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2_000 or "\x00" in value:
        raise ValueError("change_reason must be trimmed and contain 1..2000 characters")
    return value


class TabulatedPlasticityModelService:
    """Explicit pre-necking reduction; never smooths, repairs, or overwrites source data."""

    def __init__(
        self,
        *,
        repository: TabulatedPlasticityRepository,
        material_models: MaterialModelService,
        datasets: DatasetService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._material_models = material_models
        self._datasets = datasets
        self._artifacts = artifacts
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("material-model id_factory returned a zero UUID")
        return value

    async def create_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTabulatedPlasticityModel,
    ) -> TabulatedPlasticityModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_WRITE)
        reason = _reason(command.change_reason)
        properties = self._material_models.get_reference_property_source_for_tabulated_plasticity(
            context,
            decision,
            material_state_id=command.material_state_id,
            property_set_revision_id=command.property_set_revision_id,
        )
        initial_yield_stress_pa = properties.content.source_yield_stress_pa
        if initial_yield_stress_pa is None:
            raise TabulatedPlasticityConflict(
                "the selected Property Set revision must declare yield_stress_pa"
            )
        dataset_source = self._datasets.get_calibration_dataset_source(
            context,
            decision,
            command.dataset_revision_id,
        )
        dataset = dataset_source.dataset
        if dataset_source.material_state_id != command.material_state_id:
            raise TabulatedPlasticityConflict(
                "the selected Dataset revision belongs to another Material State"
            )
        if dataset.revision.record.scope.classification != properties.classification.value:
            raise TabulatedPlasticityConflict(
                "Property Set and Dataset classifications must match exactly"
            )
        dataset_content = dataset.revision.content
        if dataset_content.representation not in {
            DatasetRepresentation.NORMALIZED,
            DatasetRepresentation.PROCESSED,
        }:
            raise TabulatedPlasticityConflict(
                "tabulated plasticity requires a normalized or processed Dataset revision"
            )
        artifact, source_bytes = await self._artifacts.read_verified_bytes(
            context,
            decision,
            dataset_content.data_artifact_id,
            maximum_bytes=MAX_REFERENCE_TENSILE_ARTIFACT_BYTES,
        )
        expected_schema = (
            REFERENCE_TENSILE_PARQUET_SCHEMA
            if dataset_content.representation is DatasetRepresentation.NORMALIZED
            else REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA
        )
        if (
            artifact.artifact.sha256 != dataset_content.data_sha256
            or artifact.artifact.schema_ref != expected_schema
            or artifact.artifact.media_type != "application/vnd.apache.parquet"
            or artifact.artifact.classification != properties.classification
        ):
            raise TabulatedPlasticityConflict(
                "Dataset Artifact metadata differs from the pinned Dataset revision"
            )
        points = normalized_points_from_parquet(source_bytes)
        if len(points) != dataset_content.point_count:
            raise TabulatedPlasticityConflict(
                "Dataset Artifact point count differs from the pinned Dataset revision"
            )
        outcome = derive_reference_isotropic_hardening_curve(
            points,
            youngs_modulus_pa=properties.content.youngs_modulus_pa,
            initial_yield_stress_pa=initial_yield_stress_pa,
            extension_max_true_plastic_strain=command.extension_max_true_plastic_strain,
            acknowledge_post_necking_approximation=(
                command.acknowledge_post_necking_approximation
            ),
        )
        hardening_bytes = hardening_curve_parquet_bytes(outcome.points)
        derivation_key = hashlib.sha256(
            (
                f"{dataset.revision.record.revision_id}:"
                f"{properties.content.property_set_revision_id}:"
                f"{command.extension_max_true_plastic_strain:.17g}:"
                f"{hashlib.sha256(hardening_bytes).hexdigest()}"
            ).encode("ascii")
        ).hexdigest()
        hardening_artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=properties.classification,
            artifact_role="modeling.hardening_curve",
            schema_ref=REFERENCE_HARDENING_CURVE_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=hardening_bytes,
            idempotency_key=f"modeling-hardening:{derivation_key}",
        )
        source = properties.content
        content = ReferenceIsotropicTabulatedPlasticityContent(
            material_id=source.material_id,
            material_revision_id=source.material_revision_id,
            material_state_id=source.material_state_id,
            material_state_revision_id=source.material_state_revision_id,
            property_set_id=source.property_set_id,
            property_set_revision_id=source.property_set_revision_id,
            source_dataset_id=dataset.dataset_id,
            source_dataset_revision_id=dataset.revision.record.revision_id,
            hardening_curve_artifact_id=hardening_artifact.artifact.id,
            hardening_curve_sha256=hardening_artifact.artifact.sha256,
            hardening_curve_point_count=len(outcome.points),
            source_point_count=outcome.input_point_count,
            pre_yield_excluded_point_count=outcome.pre_yield_excluded_count,
            post_necking_excluded_point_count=outcome.post_necking_excluded_count,
            necking_source_point_index=outcome.necking_source_index,
            density_kg_per_m3=source.density_kg_per_m3,
            youngs_modulus_pa=source.youngs_modulus_pa,
            poisson_ratio=source.poisson_ratio,
            initial_yield_stress_pa=initial_yield_stress_pa,
            necking_engineering_strain=outcome.necking_engineering_strain,
            characterized_max_true_plastic_strain=(
                outcome.characterized_max_true_plastic_strain
            ),
            extension_max_true_plastic_strain=outcome.extension_max_true_plastic_strain,
            post_necking_approximation_acknowledged=(
                command.acknowledge_post_necking_approximation
            ),
            applicable_temperature_min_k=source.applicable_temperature_min_k,
            applicable_temperature_max_k=source.applicable_temperature_max_k,
            applicable_strain_rate_min_per_s=source.applicable_strain_rate_min_per_s,
            applicable_strain_rate_max_per_s=source.applicable_strain_rate_max_per_s,
            applicability_note=source.applicability_note,
            reference_temperature_k=source.reference_temperature_k,
        )
        aggregate_id = self._id()
        record = RevisionService(
            aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
            store=self._repository.material_model_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=aggregate_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    properties.classification.value,
                ),
                schema_id=REFERENCE_TABULATED_PLASTICITY_IR_SCHEMA_ID,
                schema_version=REFERENCE_TABULATED_PLASTICITY_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TabulatedPlasticityModelSnapshot(
            id=aggregate_id,
            material_state_id=content.material_state_id,
            current=RevisionSnapshot(record, content),
        )

    def get_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> TabulatedPlasticityModelSnapshot:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
        )

    def list_models_for_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TabulatedPlasticityModelSnapshot, ...]:
        _require_decision(context, decision, Permission.MODELING_READ)
        return self._repository.list_material_models_for_state(
            context=context,
            decision=decision,
            material_state_id=material_state_id,
        )

    def get_model_revision_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceIsotropicTabulatedPlasticityContent]:
        _require_capability(context, decision, Permission.MODELING_READ)
        return self._repository.get_material_model_revision(
            context=context,
            decision=decision,
            material_model_id=material_model_id,
            material_model_revision_id=material_model_revision_id,
        )

    async def read_hardening_curve_for_export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceIsotropicTabulatedPlasticityContent,
    ) -> tuple[HardeningCurvePoint, ...]:
        """Read and revalidate the exact curve Artifact for an authorized exporter."""

        _require_capability(context, decision, Permission.MODELING_READ)
        record, value = await self._artifacts.read_verified_bytes(
            context,
            decision,
            content.hardening_curve_artifact_id,
            maximum_bytes=MAX_REFERENCE_HARDENING_ARTIFACT_BYTES,
        )
        if (
            record.artifact.sha256 != content.hardening_curve_sha256
            or record.artifact.schema_ref != REFERENCE_HARDENING_CURVE_SCHEMA
            or record.artifact.artifact_role != "modeling.hardening_curve"
            or record.artifact.media_type != "application/vnd.apache.parquet"
        ):
            raise TabulatedPlasticityConflict(
                "hardening-curve Artifact differs from the immutable IR reference"
            )
        points = hardening_curve_from_parquet(value)
        if len(points) != content.hardening_curve_point_count:
            raise TabulatedPlasticityConflict(
                "hardening-curve Artifact point count differs from the immutable IR"
            )
        return points
