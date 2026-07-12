"""Environment-backed settings for the API and worker composition roots."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings. Callers must never log values such as ``database_url``."""

    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    worker_poll_interval_seconds: float = 1.0
    database_url: str | None = None
    upload_storage_root: str | None = None
    upload_capability_secret: str | None = None
    upload_max_object_bytes: int = 2 * 1024 * 1024 * 1024
    upload_part_bytes: int = 8 * 1024 * 1024
    upload_session_ttl_seconds: int = 24 * 60 * 60
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: tuple[str, ...] = ("RS256",)
    oidc_clock_skew_seconds: int = 60
    oidc_auto_provision: bool = False
    oidc_allow_loopback_http: bool = False
    oidc_client_id_claim: str = "client_id"
    oidc_organization_claim: str = "organization_id"
    oidc_project_claim: str = "project_id"
    oidc_groups_claim: str = "groups"
    oidc_display_name_claim: str = "preferred_username"
    oidc_service_grant_claim: str = "gty"
    oidc_service_grant_values: tuple[str, ...] = ("client-credentials",)

    @classmethod
    def from_environment(cls) -> Settings:
        """Build settings from the documented CMP_* environment variables."""

        def boolean(name: str, default: bool = False) -> bool:
            value = os.getenv(name)
            if value is None:
                return default
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError(f"{name} must be a boolean")

        def comma_separated(name: str, default: str) -> tuple[str, ...]:
            return tuple(
                item.strip()
                for item in os.getenv(name, default).split(",")
                if item.strip()
            )

        def optional(name: str) -> str | None:
            value = os.getenv(name)
            return value if value else None

        algorithms = comma_separated("CMP_OIDC_ALGORITHMS", "RS256")
        return cls(
            environment=os.getenv("CMP_ENVIRONMENT", "development"),
            api_host=os.getenv("CMP_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("CMP_API_PORT", "8000")),
            worker_poll_interval_seconds=float(
                os.getenv("CMP_WORKER_POLL_INTERVAL_SECONDS", "1.0")
            ),
            database_url=os.getenv("CMP_DATABASE_URL"),
            upload_storage_root=optional("CMP_UPLOAD_STORAGE_ROOT"),
            upload_capability_secret=optional("CMP_UPLOAD_CAPABILITY_SECRET"),
            upload_max_object_bytes=int(
                os.getenv("CMP_UPLOAD_MAX_OBJECT_BYTES", str(2 * 1024 * 1024 * 1024))
            ),
            upload_part_bytes=int(
                os.getenv("CMP_UPLOAD_PART_BYTES", str(8 * 1024 * 1024))
            ),
            upload_session_ttl_seconds=int(
                os.getenv("CMP_UPLOAD_SESSION_TTL_SECONDS", str(24 * 60 * 60))
            ),
            oidc_issuer=os.getenv("CMP_OIDC_ISSUER"),
            oidc_audience=os.getenv("CMP_OIDC_AUDIENCE"),
            oidc_jwks_url=os.getenv("CMP_OIDC_JWKS_URL"),
            oidc_algorithms=algorithms,
            oidc_clock_skew_seconds=int(os.getenv("CMP_OIDC_CLOCK_SKEW_SECONDS", "60")),
            oidc_auto_provision=boolean("CMP_OIDC_AUTO_PROVISION"),
            oidc_allow_loopback_http=boolean("CMP_OIDC_ALLOW_LOOPBACK_HTTP"),
            oidc_client_id_claim=os.getenv("CMP_OIDC_CLIENT_ID_CLAIM", "client_id"),
            oidc_organization_claim=os.getenv(
                "CMP_OIDC_ORGANIZATION_CLAIM", "organization_id"
            ),
            oidc_project_claim=os.getenv("CMP_OIDC_PROJECT_CLAIM", "project_id"),
            oidc_groups_claim=os.getenv("CMP_OIDC_GROUPS_CLAIM", "groups"),
            oidc_display_name_claim=os.getenv(
                "CMP_OIDC_DISPLAY_NAME_CLAIM", "preferred_username"
            ),
            oidc_service_grant_claim=os.getenv(
                "CMP_OIDC_SERVICE_GRANT_CLAIM", "gty"
            ),
            oidc_service_grant_values=comma_separated(
                "CMP_OIDC_SERVICE_GRANT_VALUES", "client-credentials"
            ),
        )

