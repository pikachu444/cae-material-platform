"""FastAPI composition root for identity, revision contracts, and durable jobs."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from cmp import __version__
from cmp.bootstrap.jobs import build_job_service
from cmp.bootstrap.security import IdentityServices, build_identity_services
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.api.authorization import (
    RequestAuthorizationDependency,
)
from cmp.modules.identity_access.adapters.api.security import install_identity_api
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import Permission
from cmp.modules.jobs.adapters.api.jobs import install_jobs_api
from cmp.modules.jobs.application.jobs import JobService
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
) -> FastAPI:
    """Create the API without importing any business or plugin implementation."""

    resolved = settings or Settings.from_environment()
    application = FastAPI(
        title="CAE Material Platform API",
        summary="Identity, authorization, revision, and durable job foundation.",
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
    application.state.authorization_service = services.authorization
    application.state.rls_context = services.rls_context
    application.state.identity_engine = services.engine
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

