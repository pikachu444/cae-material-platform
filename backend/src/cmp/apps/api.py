"""FastAPI composition root for the foundation health endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from cmp import __version__
from cmp.bootstrap.settings import Settings


class HealthResponse(BaseModel):
    """Stable health response defined by the OpenAPI baseline."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str
    version: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the API without importing any business or plugin implementation."""

    resolved = settings or Settings.from_environment()
    application = FastAPI(
        title="CAE Material Platform API",
        summary="Foundation API; no material-domain resources are implemented yet.",
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

    return application


app = create_app()


def main() -> None:
    """Run the API with the documented environment settings."""

    import uvicorn

    settings = Settings.from_environment()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()

