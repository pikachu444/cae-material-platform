"""HTTP workflow for tensile reduction and typed tabulated-plasticity IR revisions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from cmp.modules.artifacts.domain.content import ArtifactError, ArtifactNotFound
from cmp.modules.datasets.domain.reference_tensile import DatasetError, DatasetNotFound
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.tabulated_plasticity import (
    CreateReferenceTabulatedPlasticityModel,
    PromoteProcessingOutputToTabulatedPlasticity,
    TabulatedPlasticityModelService,
    TabulatedPlasticityModelSnapshot,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningCurvePoint,
    ReferenceIsotropicTabulatedPlasticityContent,
    TabulatedPlasticityConflict,
    TabulatedPlasticityError,
    TabulatedPlasticityNotFound,
    reference_isotropic_tabulated_plasticity_ir,
)
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    ReferenceProcessedTabulatedPlasticityContent,
    reference_processed_tabulated_plasticity_ir,
)
from cmp.modules.modeling.domain.reference_voce_tabulated_plasticity import (
    ReferenceVoceTabulatedPlasticityContent,
    reference_voce_tabulated_plasticity_ir,
)
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError
from cmp.shared.contracts.revisions import RevisionETag, RevisionMetadataResponse
from cmp.shared.domain.revisions import AggregateNotFound, RevisionKernelError, RevisionRecord

type Dependency = Callable[..., object]


class TabulatedPlasticityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_set_revision_id: UUID
    dataset_revision_id: UUID
    extension_max_true_plastic_strain: Annotated[float, Field(gt=0.0)]
    acknowledge_post_necking_approximation: bool
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ProcessingOutputPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_state_id: UUID
    property_set_revision_id: UUID
    processing_output_revision_id: UUID
    acknowledge_bounded_extrapolation: bool
    change_reason: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class HardeningCurveReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    sha256: str
    schema_ref: str
    point_count: int
    independent_quantity: str = "true_plastic_strain"
    independent_unit: str = "1"
    dependent_quantity: str = "true_yield_stress"
    dependent_unit: str = "Pa"


class TabulatedPlasticityApplicabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_min_k: float | None
    temperature_max_k: float | None
    strain_rate_min_per_s: float | None
    strain_rate_max_per_s: float | None
    note: str | None


class TabulatedPlasticityContentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_family_id: str
    model_schema_version: str
    model_schema_digest: str
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    property_set_id: UUID
    property_set_revision_id: UUID
    source_dataset_id: UUID | None
    source_dataset_revision_id: UUID | None
    density_kg_per_m3: float
    youngs_modulus_pa: float
    poisson_ratio: float
    initial_yield_stress_pa: float
    hardening_curve: HardeningCurveReferenceResponse
    source_point_count: int | None
    pre_yield_excluded_point_count: int | None
    post_necking_excluded_point_count: int | None
    necking_source_point_index: int | None
    transformation_profile_id: str
    transformation_profile_version: str
    transformation_profile_digest: str
    necking_engineering_strain: float | None
    characterized_max_true_plastic_strain: float
    extension_max_true_plastic_strain: float
    post_necking_extension_policy: str
    post_necking_approximation_acknowledged: bool
    applicability: TabulatedPlasticityApplicabilityResponse
    reference_temperature_k: float
    calibration_projection: dict[str, Any] | None
    processing_projection: dict[str, Any] | None
    non_production: bool

    @classmethod
    def from_domain(
        cls,
        value: ReferenceIsotropicTabulatedPlasticityContent
        | ReferenceVoceTabulatedPlasticityContent
        | ReferenceProcessedTabulatedPlasticityContent,
    ) -> TabulatedPlasticityContentResponse:
        return cls(
            model_family_id=value.model_family_id,
            model_schema_version=value.model_schema_version,
            model_schema_digest=value.model_schema_digest,
            material_id=value.material_id,
            material_revision_id=value.material_revision_id,
            material_state_id=value.material_state_id,
            material_state_revision_id=value.material_state_revision_id,
            property_set_id=value.property_set_id,
            property_set_revision_id=value.property_set_revision_id,
            source_dataset_id=getattr(value, "source_dataset_id", None),
            source_dataset_revision_id=getattr(value, "source_dataset_revision_id", None),
            density_kg_per_m3=value.density_kg_per_m3,
            youngs_modulus_pa=value.youngs_modulus_pa,
            poisson_ratio=value.poisson_ratio,
            initial_yield_stress_pa=value.initial_yield_stress_pa,
            hardening_curve=HardeningCurveReferenceResponse(
                artifact_id=value.hardening_curve_artifact_id,
                sha256=value.hardening_curve_sha256,
                schema_ref=value.hardening_curve_schema_ref,
                point_count=value.hardening_curve_point_count,
            ),
            source_point_count=getattr(value, "source_point_count", None),
            pre_yield_excluded_point_count=getattr(value, "pre_yield_excluded_point_count", None),
            post_necking_excluded_point_count=getattr(
                value, "post_necking_excluded_point_count", None
            ),
            necking_source_point_index=getattr(value, "necking_source_point_index", None),
            transformation_profile_id=value.transformation_profile_id,
            transformation_profile_version=value.transformation_profile_version,
            transformation_profile_digest=value.transformation_profile_digest,
            necking_engineering_strain=getattr(value, "necking_engineering_strain", None),
            characterized_max_true_plastic_strain=(value.characterized_max_true_plastic_strain),
            extension_max_true_plastic_strain=value.extension_max_true_plastic_strain,
            post_necking_extension_policy=value.post_necking_extension_policy,
            post_necking_approximation_acknowledged=(value.post_necking_approximation_acknowledged),
            applicability=TabulatedPlasticityApplicabilityResponse(
                temperature_min_k=value.applicable_temperature_min_k,
                temperature_max_k=value.applicable_temperature_max_k,
                strain_rate_min_per_s=value.applicable_strain_rate_min_per_s,
                strain_rate_max_per_s=value.applicable_strain_rate_max_per_s,
                note=value.applicability_note,
            ),
            reference_temperature_k=value.reference_temperature_k,
            calibration_projection=(
                {
                    "input_scope_id": value.calibration_input_scope_id,
                    "input_scope_revision_id": value.calibration_input_scope_revision_id,
                    "plan_id": value.voce_calibration_plan_id,
                    "plan_revision_id": value.voce_calibration_plan_revision_id,
                    "run_id": value.voce_calibration_run_id,
                    "candidate_id": value.voce_calibration_candidate_id,
                    "candidate_sha256": f"sha256:{value.voce_calibration_candidate_sha256}",
                    "selection_id": value.voce_candidate_selection_id,
                    "selection_revision_id": value.voce_candidate_selection_revision_id,
                    "sigma_0_pa": value.initial_yield_stress_pa,
                    "q_pa": value.q_pa,
                    "b": value.b,
                    "sampling_point_count": value.sampling_point_count,
                }
                if isinstance(value, ReferenceVoceTabulatedPlasticityContent)
                else None
            ),
            processing_projection=(
                {
                    "output_id": value.processing_output_id,
                    "output_revision_id": value.processing_output_revision_id,
                    "output_sha256": f"sha256:{value.processing_output_sha256}",
                    "source_test_data_id": value.source_test_data_id,
                    "source_test_data_revision_id": value.source_test_data_revision_id,
                    "mapping_profile_id": value.mapping_profile_id,
                    "mapping_profile_revision_id": value.mapping_profile_revision_id,
                    "candidate_families": value.candidate_families,
                    "primary_family": value.primary_family,
                    "secondary_family": value.secondary_family,
                    "primary_weight": value.primary_weight,
                    "fit_minimum_true_plastic_strain": (value.fit_minimum_true_plastic_strain),
                    "recipe_batch": (
                        {
                            "processing_recipe": {
                                "id": value.recipe_batch.recipe_id,
                                "revision_id": value.recipe_batch.recipe_revision_id,
                                "sha256": f"sha256:{value.recipe_batch.recipe_sha256}",
                            },
                            "processing_batch_id": value.recipe_batch.batch_id,
                            "batch_member_id": value.recipe_batch.batch_member_id,
                            "batch_attempt_id": value.recipe_batch.batch_attempt_id,
                            "batch_attempt_no": value.recipe_batch.batch_attempt_no,
                        }
                        if value.recipe_batch is not None
                        else None
                    ),
                }
                if isinstance(value, ReferenceProcessedTabulatedPlasticityContent)
                else None
            ),
            non_production=value.non_production,
        )


class TabulatedPlasticityProvenanceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    reference_type: str
    revision_id: UUID
    content_sha256: str
    based_on_revision_id: UUID | None
    source_property_set_revision_id: UUID
    source_dataset_revision_id: UUID | None
    source_voce_selection_revision_id: UUID | None
    source_processing_output_revision_id: UUID | None
    hardening_curve_artifact_id: UUID
    hardening_curve_sha256: str
    transformation_profile_digest: str
    recorded_at: datetime
    recorded_by: UUID

    @classmethod
    def from_record(
        cls,
        record: RevisionRecord,
        content: ReferenceIsotropicTabulatedPlasticityContent
        | ReferenceVoceTabulatedPlasticityContent
        | ReferenceProcessedTabulatedPlasticityContent,
    ) -> TabulatedPlasticityProvenanceSummary:
        reference_type = "modeling.material_model.revision"
        return cls(
            entity_type=reference_type,
            reference_type=reference_type,
            revision_id=record.revision_id,
            content_sha256=record.content_hash,
            based_on_revision_id=record.based_on_revision_id,
            source_property_set_revision_id=content.property_set_revision_id,
            source_dataset_revision_id=getattr(content, "source_dataset_revision_id", None),
            source_voce_selection_revision_id=getattr(
                content, "voce_candidate_selection_revision_id", None
            ),
            source_processing_output_revision_id=getattr(
                content, "processing_output_revision_id", None
            ),
            hardening_curve_artifact_id=content.hardening_curve_artifact_id,
            hardening_curve_sha256=content.hardening_curve_sha256,
            transformation_profile_digest=content.transformation_profile_digest,
            recorded_at=record.created_at,
            recorded_by=record.created_by,
        )


class TabulatedPlasticityRevisionResponse(RevisionMetadataResponse):
    content: TabulatedPlasticityContentResponse
    ir: dict[str, Any]
    provenance: TabulatedPlasticityProvenanceSummary

    @classmethod
    def from_snapshot(
        cls,
        material_model_id: UUID,
        snapshot: Any,
    ) -> TabulatedPlasticityRevisionResponse:
        metadata = RevisionMetadataResponse.from_record(snapshot.record, "draft")
        return cls(
            **metadata.model_dump(),
            content=TabulatedPlasticityContentResponse.from_domain(snapshot.content),
            ir=(
                reference_processed_tabulated_plasticity_ir(
                    material_model_id=material_model_id,
                    material_model_revision_id=snapshot.record.revision_id,
                    content=snapshot.content,
                )
                if isinstance(snapshot.content, ReferenceProcessedTabulatedPlasticityContent)
                else reference_voce_tabulated_plasticity_ir(
                    material_model_id=material_model_id,
                    material_model_revision_id=snapshot.record.revision_id,
                    content=snapshot.content,
                )
                if isinstance(snapshot.content, ReferenceVoceTabulatedPlasticityContent)
                else reference_isotropic_tabulated_plasticity_ir(
                    material_model_id=material_model_id,
                    material_model_revision_id=snapshot.record.revision_id,
                    content=snapshot.content,
                )
            ),
            provenance=TabulatedPlasticityProvenanceSummary.from_record(
                snapshot.record, snapshot.content
            ),
        )


class TabulatedPlasticityModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_state_id: UUID
    current_revision: TabulatedPlasticityRevisionResponse
    links: dict[str, str]

    @classmethod
    def from_snapshot(
        cls, value: TabulatedPlasticityModelSnapshot
    ) -> TabulatedPlasticityModelResponse:
        root = f"/api/v1/tabulated-plasticity-models/{value.id}"
        return cls(
            material_model_id=value.id,
            material_state_id=value.material_state_id,
            current_revision=TabulatedPlasticityRevisionResponse.from_snapshot(
                value.id, value.current
            ),
            links={
                "self": root,
                "hardening_curve": f"{root}/hardening-curve",
                "mapping_preflight": f"{root}/mapping-preflight",
                "solver_cards": f"{root}/solver-cards",
            },
        )


class TabulatedPlasticityModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TabulatedPlasticityModelResponse, ...]


class HardeningCurvePointResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    true_plastic_strain: float
    true_yield_stress_pa: float
    origin: str

    @classmethod
    def from_domain(cls, value: HardeningCurvePoint) -> HardeningCurvePointResponse:
        return cls(
            true_plastic_strain=value.true_plastic_strain,
            true_yield_stress_pa=value.true_yield_stress_pa,
            origin=value.origin.value,
        )


class HardeningCurveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_model_id: UUID
    material_model_revision_id: UUID
    artifact_id: UUID
    artifact_sha256: str
    points: tuple[HardeningCurvePointResponse, ...]


class TabulatedPlasticityProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    code: Annotated[str, StringConstraints(pattern=r"^CMP-MODELING-[0-9]{4}$")]
    trace_id: str


class TabulatedPlasticityHttpError(Exception):
    def __init__(
        self,
        *,
        context: SecurityContext,
        status_code: int,
        title: str,
        detail: str,
        code: str,
    ) -> None:
        self.context = context
        self.problem = TabulatedPlasticityProblem(
            type="urn:cmp:problem:modeling:tabulated-plasticity",
            title=title,
            status=status_code,
            detail=detail,
            code=code,
            trace_id=context.trace_id,
        )
        super().__init__(title)


def _scope(request: Request) -> tuple[SecurityContext, AuthorizationDecision]:
    context = getattr(request.state, "security_context", None)
    decision = getattr(request.state, "authorization_decision", None)
    if not isinstance(context, SecurityContext) or not isinstance(decision, AuthorizationDecision):
        raise RuntimeError("tabulated-plasticity dependencies did not initialize request scope")
    return context, decision


def _unavailable(context: SecurityContext) -> TabulatedPlasticityHttpError:
    return TabulatedPlasticityHttpError(
        context=context,
        status_code=503,
        title="Tabulated-plasticity service unavailable",
        detail="The authoritative Modeling and Artifact stores are not configured.",
        code="CMP-MODELING-0015",
    )


def _translate(context: SecurityContext, error: Exception) -> TabulatedPlasticityHttpError:
    if isinstance(
        error,
        (TabulatedPlasticityNotFound, DatasetNotFound, ArtifactNotFound, AggregateNotFound),
    ):
        return TabulatedPlasticityHttpError(
            context=context,
            status_code=404,
            title="Tabulated-plasticity resource not found",
            detail="No requested concrete model, property, Dataset, or Artifact is visible.",
            code="CMP-MODELING-0011",
        )
    if isinstance(
        error,
        (
            TabulatedPlasticityConflict,
            CommonPipelineError,
            DatasetError,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
        ),
    ):
        return TabulatedPlasticityHttpError(
            context=context,
            status_code=409,
            title="Tabulated-plasticity source conflict",
            detail="Pinned source scope, classification, revision, or Artifact evidence conflicts.",
            code="CMP-MODELING-0013",
        )
    return TabulatedPlasticityHttpError(
        context=context,
        status_code=422,
        title="Invalid tabulated-plasticity request",
        detail=(
            "Use a monotone normalized/processed tensile Dataset, typed yield stress, and an "
            "explicit post-necking extension acknowledgement."
        ),
        code="CMP-MODELING-0012",
    )


def _etag(response: Response, record: RevisionRecord) -> None:
    response.headers["ETag"] = str(RevisionETag.from_ref(record.ref))
    response.headers["Cache-Control"] = "no-store"


def install_tabulated_plasticity_api(
    application: FastAPI,
    *,
    service: TabulatedPlasticityModelService | None,
    security_dependency: Dependency,
    read_dependency: Dependency,
    write_dependency: Dependency,
) -> None:
    @application.exception_handler(TabulatedPlasticityHttpError)
    async def tabulated_plasticity_error_handler(
        request: Request, error: TabulatedPlasticityHttpError
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.problem.status,
            content=error.problem.model_dump(mode="json"),
            media_type="application/problem+json",
            headers={"Cache-Control": "no-store", "X-Request-ID": str(error.context.request_id)},
        )

    errors: dict[int | str, dict[str, Any]] = {
        401: {"description": "Authentication required."},
        403: {"description": "Modeling permission is not authorized."},
        404: {"model": TabulatedPlasticityProblem},
        409: {"model": TabulatedPlasticityProblem},
        422: {"model": TabulatedPlasticityProblem},
        503: {"model": TabulatedPlasticityProblem},
    }

    @application.post(
        "/api/v1/material-states/{material_state_id}/tabulated-plasticity-models",
        operation_id="createReferenceTabulatedPlasticityModel",
        response_model=TabulatedPlasticityModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
        summary="Reduce one tensile Dataset into a non-production tabulated-plasticity IR.",
    )
    async def create_model(
        request: Request,
        response: Response,
        material_state_id: UUID,
        body: TabulatedPlasticityCreateRequest,
    ) -> TabulatedPlasticityModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.create_model(
                context,
                decision,
                CreateReferenceTabulatedPlasticityModel(
                    material_state_id=material_state_id,
                    property_set_revision_id=body.property_set_revision_id,
                    dataset_revision_id=body.dataset_revision_id,
                    extension_max_true_plastic_strain=(body.extension_max_true_plastic_strain),
                    acknowledge_post_necking_approximation=(
                        body.acknowledge_post_necking_approximation
                    ),
                    change_reason=body.change_reason,
                ),
            )
        except (
            TabulatedPlasticityError,
            DatasetError,
            ArtifactError,
            RevisionKernelError,
            IntegrityError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return TabulatedPlasticityModelResponse.from_snapshot(value)

    @application.post(
        "/api/v1/processing-outputs/{processing_output_id}/tabulated-plasticity-models",
        operation_id="promoteProcessingOutputToTabulatedPlasticityModel",
        response_model=TabulatedPlasticityModelResponse,
        status_code=status.HTTP_201_CREATED,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(write_dependency)],
        tags=["modeling"],
        summary="Promote one exact fitted metal Processing Output into IR 1.2.",
    )
    async def promote_processing_output(
        request: Request,
        response: Response,
        processing_output_id: UUID,
        body: ProcessingOutputPromotionRequest,
    ) -> TabulatedPlasticityModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = await service.promote_processing_output(
                context,
                decision,
                PromoteProcessingOutputToTabulatedPlasticity(
                    material_state_id=body.material_state_id,
                    property_set_revision_id=body.property_set_revision_id,
                    processing_output_id=processing_output_id,
                    processing_output_revision_id=body.processing_output_revision_id,
                    acknowledge_bounded_extrapolation=(body.acknowledge_bounded_extrapolation),
                    change_reason=body.change_reason,
                ),
            )
        except (
            TabulatedPlasticityError,
            DatasetError,
            ArtifactError,
            CommonPipelineError,
            RevisionKernelError,
            IntegrityError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return TabulatedPlasticityModelResponse.from_snapshot(value)

    @application.get(
        "/api/v1/material-states/{material_state_id}/tabulated-plasticity-models",
        operation_id="listReferenceTabulatedPlasticityModels",
        response_model=TabulatedPlasticityModelListResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def list_models(
        request: Request, material_state_id: UUID
    ) -> TabulatedPlasticityModelListResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            values = service.list_models_for_state(context, decision, material_state_id)
        except (
            TabulatedPlasticityError,
            DatasetError,
            ArtifactError,
            RevisionKernelError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        return TabulatedPlasticityModelListResponse(
            items=tuple(TabulatedPlasticityModelResponse.from_snapshot(value) for value in values)
        )

    @application.get(
        "/api/v1/tabulated-plasticity-models/{material_model_id}",
        operation_id="getReferenceTabulatedPlasticityModel",
        response_model=TabulatedPlasticityModelResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    def get_model(
        request: Request, response: Response, material_model_id: UUID
    ) -> TabulatedPlasticityModelResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            value = service.get_model(context, decision, material_model_id)
        except (
            TabulatedPlasticityError,
            DatasetError,
            ArtifactError,
            RevisionKernelError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        _etag(response, value.current.record)
        return TabulatedPlasticityModelResponse.from_snapshot(value)

    @application.get(
        "/api/v1/tabulated-plasticity-models/{material_model_id}/hardening-curve",
        operation_id="getReferenceTabulatedPlasticityHardeningCurve",
        response_model=HardeningCurveResponse,
        responses=errors,
        dependencies=[Depends(security_dependency), Depends(read_dependency)],
        tags=["modeling"],
    )
    async def get_hardening_curve(
        request: Request, material_model_id: UUID
    ) -> HardeningCurveResponse:
        context, decision = _scope(request)
        if service is None:
            raise _unavailable(context)
        try:
            model = service.get_model(context, decision, material_model_id)
            points = await service.read_hardening_curve_for_export(
                context, decision, model.current.content
            )
        except (
            TabulatedPlasticityError,
            DatasetError,
            ArtifactError,
            RevisionKernelError,
            ValueError,
        ) as error:
            raise _translate(context, error) from error
        content = model.current.content
        return HardeningCurveResponse(
            material_model_id=model.id,
            material_model_revision_id=model.current.record.revision_id,
            artifact_id=content.hardening_curve_artifact_id,
            artifact_sha256=content.hardening_curve_sha256,
            points=tuple(HardeningCurvePointResponse.from_domain(point) for point in points),
        )
