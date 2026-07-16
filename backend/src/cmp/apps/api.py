"""FastAPI composition root for identity, immutable data, provenance, and audit."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from cmp import __version__
from cmp.bootstrap.artifacts import build_artifact_services
from cmp.bootstrap.audit import build_audit_service
from cmp.bootstrap.catalog import build_catalog_service
from cmp.bootstrap.datasets import (
    build_dataset_service,
    build_governed_import_service,
    build_shear_relaxation_dataset_service,
    build_viscoelastic_dataset_service,
)
from cmp.bootstrap.demo_identity import DemoIdentity, install_demo_identity_api
from cmp.bootstrap.exporting import (
    build_bulk_export_service,
    build_elastoplastic_solver_card_service,
    build_linear_viscoelastic_solver_card_service,
    build_ogden_prony_solver_card_service,
    build_solver_card_service,
)
from cmp.bootstrap.jobs import build_job_service
from cmp.bootstrap.modeling import (
    build_candidate_selection_service,
    build_linear_viscoelastic_model_service,
    build_material_model_service,
    build_ogden_candidate_promotion_service,
    build_ogden_prony_model_service,
    build_prony_candidate_promotion_service,
    build_reference_calibration_service,
    build_reference_ogden_calibration_service,
    build_reference_prony_calibration_service,
    build_reference_voce_calibration_service,
    build_scientific_profile_service,
    build_tabulated_plasticity_model_service,
    build_voce_candidate_projection_service,
)
from cmp.bootstrap.plugins import build_plugin_registry_service
from cmp.bootstrap.processing import (
    build_processing_service,
    build_shear_relaxation_processing_service,
    build_viscoelastic_master_service,
)
from cmp.bootstrap.provenance import build_provenance_services
from cmp.bootstrap.release import build_release_service
from cmp.bootstrap.review_release import build_review_service
from cmp.bootstrap.security import (
    IdentityServices,
    build_demo_identity_services,
    build_identity_services,
)
from cmp.bootstrap.settings import Settings
from cmp.bootstrap.statistics import (
    build_replicate_outlier_service,
    build_replicate_statistics_service,
    build_statistics_service,
)
from cmp.bootstrap.testing import build_test_context_service, build_testing_service
from cmp.bootstrap.validation import build_reference_validation_service
from cmp.bootstrap.voce_holdout import build_reference_voce_holdout_service
from cmp.modules.artifacts.adapters.api.content import install_content_artifact_api
from cmp.modules.artifacts.adapters.api.uploads import install_upload_api
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.application.uploads import UploadService
from cmp.modules.audit.adapters.api.audit import install_audit_api
from cmp.modules.audit.application.service import AuditService
from cmp.modules.catalog.adapters.api.catalog import install_catalog_api
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.adapters.api.datasets import install_dataset_api
from cmp.modules.datasets.adapters.api.governed_import import install_governed_import_api
from cmp.modules.datasets.adapters.api.shear_relaxation import (
    install_shear_relaxation_dataset_api,
)
from cmp.modules.datasets.adapters.api.viscoelastic_master import (
    install_viscoelastic_selection_api,
)
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.datasets.application.viscoelastic_master import ViscoelasticDatasetService
from cmp.modules.exporting.adapters.api.bulk_export import install_bulk_export_api
from cmp.modules.exporting.adapters.api.elastoplastic_solver_cards import (
    install_elastoplastic_solver_card_api,
)
from cmp.modules.exporting.adapters.api.linear_viscoelastic_solver_cards import (
    install_linear_viscoelastic_solver_card_api,
)
from cmp.modules.exporting.adapters.api.ogden_prony_solver_cards import (
    install_ogden_prony_solver_card_api,
)
from cmp.modules.exporting.adapters.api.solver_cards import install_solver_card_api
from cmp.modules.exporting.application.bulk_export import BulkExportService
from cmp.modules.exporting.application.elastoplastic_service import (
    ElastoplasticSolverCardService,
)
from cmp.modules.exporting.application.linear_viscoelastic_service import (
    LinearViscoelasticSolverCardService,
)
from cmp.modules.exporting.application.ogden_prony_service import OgdenPronySolverCardService
from cmp.modules.exporting.application.service import SolverCardService
from cmp.modules.identity_access.adapters.api.authorization import (
    RequestAuthorizationDependency,
)
from cmp.modules.identity_access.adapters.api.security import install_identity_api
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import Permission
from cmp.modules.jobs.adapters.api.jobs import install_jobs_api
from cmp.modules.jobs.application.jobs import JobService
from cmp.modules.modeling.adapters.api.calibration import install_calibration_api
from cmp.modules.modeling.adapters.api.candidate_selection import install_candidate_selection_api
from cmp.modules.modeling.adapters.api.linear_viscoelasticity import (
    install_linear_viscoelastic_api,
)
from cmp.modules.modeling.adapters.api.material_models import install_material_model_api
from cmp.modules.modeling.adapters.api.ogden_calibration import (
    install_ogden_calibration_api,
)
from cmp.modules.modeling.adapters.api.ogden_candidate_promotion import (
    install_ogden_candidate_promotion_api,
)
from cmp.modules.modeling.adapters.api.ogden_prony import install_ogden_prony_api
from cmp.modules.modeling.adapters.api.prony_calibration import install_prony_calibration_api
from cmp.modules.modeling.adapters.api.prony_candidate_promotion import (
    install_prony_candidate_promotion_api,
)
from cmp.modules.modeling.adapters.api.scientific_profile import install_scientific_profile_api
from cmp.modules.modeling.adapters.api.tabulated_plasticity import (
    install_tabulated_plasticity_api,
)
from cmp.modules.modeling.adapters.api.voce_calibration import (
    install_voce_calibration_api,
)
from cmp.modules.modeling.adapters.api.voce_candidate_projection import (
    install_voce_candidate_projection_api,
)
from cmp.modules.modeling.application.calibration import ReferenceCalibrationService
from cmp.modules.modeling.application.candidate_selection import CandidateSelectionService
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.ogden_calibration import (
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_candidate_promotion import (
    OgdenCandidatePromotionService,
)
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.application.prony_calibration import (
    ReferencePronyCalibrationService,
)
from cmp.modules.modeling.application.prony_candidate_promotion import (
    PronyCandidatePromotionService,
)
from cmp.modules.modeling.application.scientific_profile import ScientificProfileService
from cmp.modules.modeling.application.service import MaterialModelService
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.modeling.application.voce_calibration import (
    ReferenceVoceCalibrationService,
)
from cmp.modules.modeling.application.voce_candidate_projection import (
    VoceCandidateProjectionService,
)
from cmp.modules.plugins.adapters.api.registry import install_plugin_registry_api
from cmp.modules.plugins.application.registry import PluginRegistryService
from cmp.modules.processing.adapters.api.processing import install_processing_api
from cmp.modules.processing.adapters.api.shear_relaxation import (
    install_shear_relaxation_processing_api,
)
from cmp.modules.processing.adapters.api.viscoelastic_master_curve import (
    install_viscoelastic_master_api,
)
from cmp.modules.processing.application.service import ProcessingService
from cmp.modules.processing.application.shear_relaxation import (
    ShearRelaxationProcessingService,
)
from cmp.modules.processing.application.viscoelastic_master_curve import (
    ViscoelasticMasterService,
)
from cmp.modules.provenance.adapters.api.provenance import install_provenance_api
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.application.service import ProvenanceService
from cmp.modules.review_release.adapters.api.release import install_release_api
from cmp.modules.review_release.adapters.api.review import install_review_api
from cmp.modules.review_release.application.release_service import ReleaseService
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.statistics.adapters.api.replicate_outliers import (
    install_replicate_outlier_api,
)
from cmp.modules.statistics.adapters.api.replicate_statistics import (
    install_replicate_statistics_api,
)
from cmp.modules.statistics.adapters.api.statistics import install_statistics_api
from cmp.modules.statistics.application.replicate_outlier_service import (
    ReplicateOutlierService,
)
from cmp.modules.statistics.application.replicate_service import ReplicateStatisticsService
from cmp.modules.statistics.application.service import StatisticsService
from cmp.modules.testing.adapters.api.test_context import install_test_context_api
from cmp.modules.testing.adapters.api.testing import install_testing_api
from cmp.modules.testing.application.service import TestingService
from cmp.modules.testing.application.test_context import TestContextService
from cmp.modules.validation.adapters.api.validation import install_validation_api
from cmp.modules.validation.adapters.api.voce_holdout import install_voce_holdout_api
from cmp.modules.validation.application.service import ReferenceValidationService
from cmp.modules.validation.application.voce_holdout import ReferenceVoceHoldoutService
from cmp.shared.contracts.revisions import revision_openapi_components
from cmp.shared.observability import (
    HttpObservabilityMiddleware,
    OperationalMetrics,
    build_telemetry_runtime,
    configure_structured_logging,
)
from cmp.shared.observability.api import install_operations_api


class HealthResponse(BaseModel):
    """Stable health response defined by the OpenAPI baseline."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str
    version: str


def create_app(
    settings: Settings | None = None,
    security_service: SecurityContextService | None = None,
    authorization_service: AuthorizationService | None = None,
    job_service: JobService | None = None,
    plugin_registry_service: PluginRegistryService | None = None,
    upload_service: UploadService | None = None,
    artifact_service: ArtifactService | None = None,
    provenance_service: ProvenanceService | None = None,
    provenance_lineage_service: ProvenanceLineageService | None = None,
    audit_service: AuditService | None = None,
    catalog_service: CatalogService | None = None,
    testing_service: TestingService | None = None,
    test_context_service: TestContextService | None = None,
    dataset_service: DatasetService | None = None,
    governed_import_service: GovernedImportService | None = None,
    shear_relaxation_dataset_service: ShearRelaxationDatasetService | None = None,
    viscoelastic_dataset_service: ViscoelasticDatasetService | None = None,
    processing_service: ProcessingService | None = None,
    shear_relaxation_processing_service: ShearRelaxationProcessingService | None = None,
    viscoelastic_master_service: ViscoelasticMasterService | None = None,
    statistics_service: StatisticsService | None = None,
    replicate_statistics_service: ReplicateStatisticsService | None = None,
    replicate_outlier_service: ReplicateOutlierService | None = None,
    material_model_service: MaterialModelService | None = None,
    linear_viscoelastic_model_service: LinearViscoelasticModelService | None = None,
    ogden_prony_model_service: OgdenPronyModelService | None = None,
    scientific_profile_service: ScientificProfileService | None = None,
    ogden_calibration_service: ReferenceOgdenCalibrationService | None = None,
    ogden_candidate_promotion_service: OgdenCandidatePromotionService | None = None,
    tabulated_plasticity_model_service: TabulatedPlasticityModelService | None = None,
    calibration_service: ReferenceCalibrationService | None = None,
    voce_calibration_service: ReferenceVoceCalibrationService | None = None,
    prony_calibration_service: ReferencePronyCalibrationService | None = None,
    prony_candidate_promotion_service: PronyCandidatePromotionService | None = None,
    voce_candidate_projection_service: VoceCandidateProjectionService | None = None,
    candidate_selection_service: CandidateSelectionService | None = None,
    solver_card_service: SolverCardService | None = None,
    elastoplastic_solver_card_service: ElastoplasticSolverCardService | None = None,
    linear_viscoelastic_solver_card_service: LinearViscoelasticSolverCardService | None = None,
    ogden_prony_solver_card_service: OgdenPronySolverCardService | None = None,
    bulk_export_service: BulkExportService | None = None,
    validation_service: ReferenceValidationService | None = None,
    voce_holdout_service: ReferenceVoceHoldoutService | None = None,
    review_service: ReviewService | None = None,
    release_service: ReleaseService | None = None,
) -> FastAPI:
    """Create the API without importing any business or plugin implementation."""

    resolved = settings or Settings.from_environment()
    demo_identity = DemoIdentity.from_settings(resolved)
    application = FastAPI(
        title="CAE Material Platform API",
        summary="Material data management, immutable traceability, and CAE workflow platform.",
        version=__version__,
        openapi_version="3.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs" if resolved.environment != "production" else None,
        redoc_url=None,
    )
    operational_metrics = OperationalMetrics()
    telemetry = build_telemetry_runtime(
        service_name="cmp-api",
        environment=resolved.environment,
        endpoint=resolved.otel_exporter_otlp_endpoint,
        export_interval_ms=resolved.otel_metric_export_interval_ms,
    )
    application.add_middleware(HttpObservabilityMiddleware, metrics=operational_metrics)

    @application.get(
        "/api/v1/health",
        operation_id="getHealth",
        response_model=HealthResponse,
        tags=["system"],
    )
    def get_health() -> HealthResponse:
        return HealthResponse(status="ok", service="cmp-api", version=__version__)

    services = (
        IdentityServices(security_service, authorization_service, None, None)
        if security_service is not None or authorization_service is not None
        else (
            build_demo_identity_services(resolved, demo_identity.idp)
            if demo_identity is not None
            else build_identity_services(resolved)
        )
    )
    install_demo_identity_api(application, demo_identity)
    resolved_security = services.security
    security_dependency = install_identity_api(application, resolved_security)
    install_operations_api(
        application,
        metrics=operational_metrics,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.AUDIT_READ
        ),
    )
    resolved_jobs = job_service or build_job_service(services)
    install_jobs_api(
        application,
        service=resolved_jobs,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(services.authorization, Permission.JOB_READ),
        submit_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.JOB_SUBMIT
        ),
        control_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.JOB_CONTROL
        ),
    )
    resolved_plugins = plugin_registry_service or build_plugin_registry_service(services)
    install_plugin_registry_api(
        application,
        service=resolved_plugins,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PLUGIN_READ
        ),
        submit_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PLUGIN_SUBMIT
        ),
        activate_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PLUGIN_ACTIVATE
        ),
    )
    artifact_services = build_artifact_services(services, resolved)
    resolved_uploads = upload_service or artifact_services.upload
    install_upload_api(
        application,
        service=resolved_uploads,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.ARTIFACT_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.ARTIFACT_WRITE
        ),
    )
    resolved_artifacts = artifact_service or artifact_services.content
    install_content_artifact_api(
        application,
        service=resolved_artifacts,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.ARTIFACT_READ
        ),
    )
    provenance_services = build_provenance_services(services)
    resolved_provenance = provenance_service or provenance_services.entity
    resolved_lineage = provenance_lineage_service or provenance_services.lineage
    install_provenance_api(
        application,
        service=resolved_provenance,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROVENANCE_READ
        ),
        lineage_service=resolved_lineage,
    )
    resolved_audit = audit_service or build_audit_service(services)
    install_audit_api(
        application,
        service=resolved_audit,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.AUDIT_READ
        ),
    )
    resolved_catalog = catalog_service or build_catalog_service(services)
    install_catalog_api(
        application,
        service=resolved_catalog,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CATALOG_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CATALOG_WRITE
        ),
    )
    resolved_testing = testing_service or build_testing_service(services, resolved_artifacts)
    install_testing_api(
        application,
        service=resolved_testing,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.TESTING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.TESTING_WRITE
        ),
    )
    resolved_test_context = test_context_service or build_test_context_service(services)
    install_test_context_api(
        application,
        service=resolved_test_context,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.TESTING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.TESTING_WRITE
        ),
    )
    resolved_datasets = dataset_service or build_dataset_service(services, resolved_artifacts)
    install_dataset_api(
        application,
        service=resolved_datasets,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_WRITE
        ),
    )
    resolved_governed_import = governed_import_service or build_governed_import_service(
        services, resolved_testing, resolved_artifacts
    )
    install_governed_import_api(
        application,
        service=resolved_governed_import,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_WRITE
        ),
    )
    resolved_shear_relaxation_datasets = (
        shear_relaxation_dataset_service
        or build_shear_relaxation_dataset_service(services, resolved_artifacts)
    )
    install_shear_relaxation_dataset_api(
        application,
        service=resolved_shear_relaxation_datasets,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_WRITE
        ),
    )
    resolved_viscoelastic_datasets = (
        viscoelastic_dataset_service
        or build_viscoelastic_dataset_service(
            services,
            resolved_shear_relaxation_datasets,
            resolved_testing,
        )
    )
    install_viscoelastic_selection_api(
        application,
        service=resolved_viscoelastic_datasets,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.DATASET_WRITE
        ),
    )
    resolved_processing = processing_service or build_processing_service(
        services,
        resolved_datasets,
        resolved_testing,
        resolved_artifacts,
    )
    install_processing_api(
        application,
        service=resolved_processing,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_EXECUTE
        ),
    )
    resolved_shear_relaxation_processing = (
        shear_relaxation_processing_service
        or build_shear_relaxation_processing_service(
            services,
            resolved_shear_relaxation_datasets,
            resolved_artifacts,
        )
    )
    install_shear_relaxation_processing_api(
        application,
        service=resolved_shear_relaxation_processing,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_EXECUTE
        ),
    )
    resolved_viscoelastic_master = (
        viscoelastic_master_service
        or build_viscoelastic_master_service(
            services,
            resolved_viscoelastic_datasets,
            resolved_shear_relaxation_datasets,
            resolved_artifacts,
        )
    )
    install_viscoelastic_master_api(
        application,
        service=resolved_viscoelastic_master,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.PROCESSING_EXECUTE
        ),
    )
    resolved_statistics = statistics_service or build_statistics_service(
        services,
        resolved_datasets,
        resolved_artifacts,
    )
    install_statistics_api(
        application,
        service=resolved_statistics,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_EXECUTE
        ),
    )
    resolved_replicate_statistics = (
        replicate_statistics_service
        or build_replicate_statistics_service(
            services,
            resolved_datasets,
            resolved_artifacts,
        )
    )
    install_replicate_statistics_api(
        application,
        service=resolved_replicate_statistics,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_EXECUTE
        ),
    )
    resolved_replicate_outliers = replicate_outlier_service or build_replicate_outlier_service(
        services,
        resolved_datasets,
        resolved_artifacts,
    )
    install_replicate_outlier_api(
        application,
        service=resolved_replicate_outliers,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.STATISTICS_EXECUTE
        ),
    )
    resolved_material_models = material_model_service or build_material_model_service(services)
    install_material_model_api(
        application,
        service=resolved_material_models,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_linear_viscoelastic = (
        linear_viscoelastic_model_service
        or build_linear_viscoelastic_model_service(services, resolved_material_models)
    )
    install_linear_viscoelastic_api(
        application,
        service=resolved_linear_viscoelastic,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_ogden_prony = ogden_prony_model_service or build_ogden_prony_model_service(
        services, resolved_material_models
    )
    install_ogden_prony_api(
        application,
        service=resolved_ogden_prony,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_scientific_profiles = (
        scientific_profile_service or build_scientific_profile_service(services)
    )
    install_scientific_profile_api(
        application,
        service=resolved_scientific_profiles,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_ogden_calibration = (
        ogden_calibration_service
        or build_reference_ogden_calibration_service(
            services,
            resolved_scientific_profiles,
            resolved_catalog,
            resolved_governed_import,
            resolved_testing,
            resolved_ogden_prony,
            resolved_artifacts,
        )
    )
    install_ogden_calibration_api(
        application,
        service=resolved_ogden_calibration,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CALIBRATION_EXECUTE
        ),
    )
    resolved_ogden_candidate_promotion = (
        ogden_candidate_promotion_service
        or build_ogden_candidate_promotion_service(
            services,
            resolved_ogden_calibration,
            resolved_ogden_prony,
        )
    )
    install_ogden_candidate_promotion_api(
        application,
        service=resolved_ogden_candidate_promotion,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_tabulated_plasticity = (
        tabulated_plasticity_model_service
        or build_tabulated_plasticity_model_service(
            services,
            resolved_datasets,
            resolved_material_models,
            resolved_artifacts,
        )
    )
    install_tabulated_plasticity_api(
        application,
        service=resolved_tabulated_plasticity,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_calibration = calibration_service or build_reference_calibration_service(
        services,
        resolved_datasets,
        resolved_material_models,
        resolved_artifacts,
    )
    install_calibration_api(
        application,
        service=resolved_calibration,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CALIBRATION_EXECUTE
        ),
    )
    resolved_voce_calibration = (
        voce_calibration_service
        or build_reference_voce_calibration_service(
            services,
            resolved_datasets,
            resolved_catalog,
            resolved_replicate_outliers,
            resolved_artifacts,
        )
    )
    install_voce_calibration_api(
        application,
        service=resolved_voce_calibration,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CALIBRATION_EXECUTE
        ),
    )
    resolved_prony_calibration = (
        prony_calibration_service
        or build_reference_prony_calibration_service(
            services,
            resolved_shear_relaxation_datasets,
            resolved_linear_viscoelastic,
            resolved_artifacts,
        )
    )
    install_prony_calibration_api(
        application,
        service=resolved_prony_calibration,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.CALIBRATION_EXECUTE
        ),
    )
    resolved_prony_candidate_promotion = (
        prony_candidate_promotion_service
        or build_prony_candidate_promotion_service(
            services,
            resolved_prony_calibration,
            resolved_linear_viscoelastic,
        )
    )
    install_prony_candidate_promotion_api(
        application,
        service=resolved_prony_candidate_promotion,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_voce_projection = (
        voce_candidate_projection_service
        or build_voce_candidate_projection_service(
            services,
            resolved_voce_calibration,
            resolved_material_models,
            resolved_artifacts,
        )
    )
    install_voce_candidate_projection_api(
        application,
        service=resolved_voce_projection,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_candidate_selections = (
        candidate_selection_service
        or build_candidate_selection_service(
            services,
            resolved_calibration,
            resolved_material_models,
        )
    )
    install_candidate_selection_api(
        application,
        service=resolved_candidate_selections,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_READ
        ),
        write_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.MODELING_WRITE
        ),
    )
    resolved_solver_cards = solver_card_service or build_solver_card_service(services)
    install_solver_card_api(
        application,
        service=resolved_solver_cards,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_EXECUTE
        ),
    )
    resolved_elastoplastic_solver_cards = (
        elastoplastic_solver_card_service
        or build_elastoplastic_solver_card_service(
            services,
            resolved_tabulated_plasticity,
        )
    )
    install_elastoplastic_solver_card_api(
        application,
        service=resolved_elastoplastic_solver_cards,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_EXECUTE
        ),
    )
    resolved_linear_viscoelastic_solver_cards = (
        linear_viscoelastic_solver_card_service
        or build_linear_viscoelastic_solver_card_service(
            services,
            resolved_linear_viscoelastic,
        )
    )
    install_linear_viscoelastic_solver_card_api(
        application,
        service=resolved_linear_viscoelastic_solver_cards,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_EXECUTE
        ),
    )
    resolved_ogden_prony_solver_cards = (
        ogden_prony_solver_card_service
        or build_ogden_prony_solver_card_service(services, resolved_ogden_prony)
    )
    install_ogden_prony_solver_card_api(
        application,
        service=resolved_ogden_prony_solver_cards,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_EXECUTE
        ),
    )
    resolved_bulk_exports = bulk_export_service or build_bulk_export_service(
        services,
        resolved_artifacts,
        resolved,
    )
    install_bulk_export_api(
        application,
        service=resolved_bulk_exports,
        artifacts=resolved_artifacts,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.EXPORT_EXECUTE
        ),
    )
    resolved_validation = validation_service or build_reference_validation_service(
        services,
        resolved_datasets,
        resolved_material_models,
        resolved_solver_cards,
        resolved_artifacts,
    )
    install_validation_api(
        application,
        service=resolved_validation,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.VALIDATION_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.VALIDATION_EXECUTE
        ),
    )
    resolved_voce_holdout = voce_holdout_service or build_reference_voce_holdout_service(
        services,
        resolved_tabulated_plasticity,
        resolved_replicate_outliers,
        resolved_datasets,
        resolved_artifacts,
    )
    install_voce_holdout_api(
        application,
        service=resolved_voce_holdout,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.VALIDATION_READ
        ),
        execute_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.VALIDATION_EXECUTE
        ),
    )
    resolved_review = review_service or build_review_service(services)
    install_review_api(
        application,
        service=resolved_review,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.REVIEW_READ
        ),
        request_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.REVIEW_REQUEST
        ),
        decide_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.REVIEW_DECIDE
        ),
    )
    resolved_release = release_service or build_release_service(services)
    install_release_api(
        application,
        service=resolved_release,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.RELEASE_READ
        ),
        publish_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.RELEASE_PUBLISH
        ),
    )
    application.state.authorization_service = services.authorization
    application.state.operational_metrics = operational_metrics
    application.state.telemetry = telemetry
    application.state.rls_context = services.rls_context
    application.state.identity_engine = services.engine
    application.state.catalog_service = resolved_catalog
    application.state.testing_service = resolved_testing
    application.state.test_context_service = resolved_test_context
    application.state.dataset_service = resolved_datasets
    application.state.governed_import_service = resolved_governed_import
    application.state.shear_relaxation_dataset_service = resolved_shear_relaxation_datasets
    application.state.viscoelastic_dataset_service = resolved_viscoelastic_datasets
    application.state.processing_service = resolved_processing
    application.state.shear_relaxation_processing_service = resolved_shear_relaxation_processing
    application.state.viscoelastic_master_service = resolved_viscoelastic_master
    application.state.statistics_service = resolved_statistics
    application.state.replicate_statistics_service = resolved_replicate_statistics
    application.state.material_model_service = resolved_material_models
    application.state.linear_viscoelastic_model_service = resolved_linear_viscoelastic
    application.state.ogden_prony_model_service = resolved_ogden_prony
    application.state.scientific_profile_service = resolved_scientific_profiles
    application.state.ogden_calibration_service = resolved_ogden_calibration
    application.state.tabulated_plasticity_model_service = resolved_tabulated_plasticity
    application.state.calibration_service = resolved_calibration
    application.state.voce_calibration_service = resolved_voce_calibration
    application.state.prony_calibration_service = resolved_prony_calibration
    application.state.prony_candidate_promotion_service = resolved_prony_candidate_promotion
    application.state.voce_candidate_projection_service = resolved_voce_projection
    application.state.candidate_selection_service = resolved_candidate_selections
    application.state.solver_card_service = resolved_solver_cards
    application.state.elastoplastic_solver_card_service = resolved_elastoplastic_solver_cards
    application.state.linear_viscoelastic_solver_card_service = (
        resolved_linear_viscoelastic_solver_cards
    )
    application.state.ogden_prony_solver_card_service = resolved_ogden_prony_solver_cards
    application.state.validation_service = resolved_validation
    application.state.voce_holdout_service = resolved_voce_holdout
    application.state.review_service = resolved_review
    application.state.release_service = resolved_release
    if services.engine is not None:
        application.router.add_event_handler("shutdown", services.engine.dispose)
    application.router.add_event_handler("shutdown", telemetry.shutdown)

    generated_openapi = application.openapi

    def openapi_with_revision_components() -> dict[str, object]:
        schema = generated_openapi()
        components = schema.setdefault("components", {})
        if not isinstance(components, dict):
            raise RuntimeError("FastAPI generated invalid OpenAPI components")
        for section, entries in revision_openapi_components().items():
            target = components.setdefault(section, {})
            if not isinstance(target, dict):
                raise RuntimeError(f"FastAPI generated invalid OpenAPI {section}")
            target.update(entries)
        return schema

    application.openapi = openapi_with_revision_components  # type: ignore[method-assign]

    telemetry.instrument_fastapi(application)
    return application


app = create_app()


def main() -> None:
    """Run the API with the documented environment settings."""

    import uvicorn

    settings = Settings.from_environment()
    configure_structured_logging("cmp-api")
    # CMP emits one allow-listed structured request event after the route template is
    # resolved. Uvicorn's raw access line would duplicate that event and can expose
    # high-cardinality paths or query strings.
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, access_log=False)


if __name__ == "__main__":
    main()
