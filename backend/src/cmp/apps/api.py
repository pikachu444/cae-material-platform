"""FastAPI composition root for health and shared revision contract components."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from cmp import __version__
from cmp.bootstrap.security import build_security_service
from cmp.bootstrap.settings import Settings
from cmp.modules.identity_access.adapters.api.security import install_identity_api
from cmp.modules.identity_access.application.security import SecurityContextService
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
) -> FastAPI:
    """Create the API without importing any business or plugin implementation."""

    resolved = settings or Settings.from_environment()
    application = FastAPI(
        title="CAE Material Platform API",
        summary="Identity and revision-kernel API foundation; no material resources yet.",
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

    resolved_security = security_service or build_security_service(resolved)
    install_identity_api(application, resolved_security)

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

