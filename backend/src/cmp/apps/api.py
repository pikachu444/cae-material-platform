"""FastAPI composition root for identity, immutable data, provenance, and audit."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from cmp import __version__
from cmp.bootstrap.artifacts import build_artifact_services
from cmp.bootstrap.audit import build_audit_service
from cmp.bootstrap.catalog import build_catalog_service
from cmp.bootstrap.jobs import build_job_service
from cmp.bootstrap.modeling import build_material_model_service
from cmp.bootstrap.plugins import build_plugin_registry_service
from cmp.bootstrap.provenance import build_provenance_services
from cmp.bootstrap.security import IdentityServices, build_identity_services
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.api.content import install_content_artifact_api
from cmp.modules.artifacts.adapters.api.uploads import install_upload_api
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.application.uploads import UploadService
from cmp.modules.audit.adapters.api.audit import install_audit_api
from cmp.modules.audit.application.service import AuditService
from cmp.modules.catalog.adapters.api.catalog import install_catalog_api
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.identity_access.adapters.api.authorization import (
    RequestAuthorizationDependency,
)
from cmp.modules.identity_access.adapters.api.security import install_identity_api
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import Permission
from cmp.modules.jobs.adapters.api.jobs import install_jobs_api
from cmp.modules.jobs.application.jobs import JobService
from cmp.modules.modeling.adapters.api.material_models import install_material_model_api
from cmp.modules.modeling.application.service import MaterialModelService
from cmp.modules.plugins.adapters.api.registry import install_plugin_registry_api
from cmp.modules.plugins.application.registry import PluginRegistryService
from cmp.modules.provenance.adapters.api.provenance import install_provenance_api
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.application.service import ProvenanceService
from cmp.shared.contracts.revisions import revision_openapi_components


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
    material_model_service: MaterialModelService | None = None,
) -> FastAPI:
    """Create the API without importing any business or plugin implementation."""

    resolved = settings or Settings.from_environment()
    application = FastAPI(
        title="CAE Material Platform API",
        summary="Material data management, immutable traceability, and CAE workflow platform.",
        version=__version__,
        openapi_version="3.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs" if resolved.environment != "production" else None,
        redoc_url=None,
    )

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
        else build_identity_services(resolved)
    )
    resolved_security = services.security
    security_dependency = install_identity_api(application, resolved_security)
    resolved_jobs = job_service or build_job_service(services)
    install_jobs_api(
        application,
        service=resolved_jobs,
        security_dependency=security_dependency,
        read_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.JOB_READ
        ),
        submit_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.JOB_SUBMIT
        ),
        control_dependency=RequestAuthorizationDependency(
            services.authorization, Permission.JOB_CONTROL
        ),
    )
    resolved_plugins = plugin_registry_service or build_plugin_registry_service(
        services
    )
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
    application.state.authorization_service = services.authorization
    application.state.rls_context = services.rls_context
    application.state.identity_engine = services.engine
    application.state.catalog_service = resolved_catalog
    application.state.material_model_service = resolved_material_models
    if services.engine is not None:
        application.router.add_event_handler("shutdown", services.engine.dispose)

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

    return application


app = create_app()


def main() -> None:
    """Run the API with the documented environment settings."""

    import uvicorn

    settings = Settings.from_environment()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()

