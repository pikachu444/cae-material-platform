"""Owner-only bootstrap for the intentionally local Docker Compose demo.

This command is not part of runtime application composition.  It creates the
non-owner application database role and appends fixed group role bindings for
the synthetic demo tenant after Alembic has applied the normal migrations.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from uuid import UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from cmp.bootstrap.demo_identity import (
    DEMO_GROUP,
    DEMO_ORGANIZATION_ID,
    DEMO_PROJECT_ID,
    DemoIdentity,
)
from cmp.bootstrap.settings import Settings

_APPLICATION_ROLE = "cmp_app"
_BOOTSTRAP_PRINCIPAL_ID = UUID("d0000000-0000-4000-8000-000000000003")
_BINDING_NAMESPACE = UUID("d0000000-0000-4000-8000-000000000004")
_DEMO_ROLES = (
    "test_engineer",
    "data_steward",
    "statistical_analyst",
    "material_modeler",
    "cae_analyst",
    "auditor",
)
_SCHEMAS = (
    "identity",
    "revisioning",
    "access_control",
    "governance",
    "jobs",
    "plugin",
    "artifact",
    "provenance",
    "events",
    "audit",
    "catalog",
    "testing",
    "datasets",
    "processing",
    "statistics",
    "modeling",
    "exporting",
    "validation",
)


def _identifier(value: str) -> str:
    return f'"{value.replace('"', '""')}"'


def _required_environment(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise ValueError(f"{name} is required for the Docker Compose demo bootstrap")
    return value


def _set_application_password(connection: Connection, password: str) -> None:
    quoted = connection.execute(
        sa.text("SELECT quote_literal(:password)"), {"password": password}
    ).scalar_one()
    connection.exec_driver_sql(f"ALTER ROLE {_APPLICATION_ROLE} PASSWORD {quoted}")


def _ensure_application_role(connection: Connection, password: str) -> None:
    exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": _APPLICATION_ROLE},
    ).scalar_one_or_none()
    if exists is None:
        connection.exec_driver_sql(
            "CREATE ROLE cmp_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    connection.exec_driver_sql(
        "ALTER ROLE cmp_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
    )
    _set_application_password(connection, password)


def _grant_runtime_privileges(connection: Connection) -> None:
    database = connection.execute(sa.text("SELECT current_database()")).scalar_one()
    schema_names = ", ".join(_identifier(name) for name in _SCHEMAS)
    connection.exec_driver_sql(
        f"GRANT CONNECT ON DATABASE {_identifier(database)} TO {_APPLICATION_ROLE}"
    )
    connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema_names} TO {_APPLICATION_ROLE}")
    connection.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE ON identity.principal, identity.external_identity, "
        "identity.role_binding TO cmp_app"
    )
    for schema in (
        "governance",
        "jobs",
        "plugin",
        "artifact",
        "events",
        "catalog",
        "testing",
        "datasets",
        "processing",
        "statistics",
        "modeling",
        "exporting",
        "validation",
    ):
        connection.exec_driver_sql(
            f"GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {_identifier(schema)} TO cmp_app"
        )
    for schema in ("provenance", "audit"):
        connection.exec_driver_sql(
            f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA {_identifier(schema)} TO cmp_app"
        )
    connection.exec_driver_sql(
        "GRANT UPDATE ON provenance.activity, provenance.association TO cmp_app"
    )
    for schema in _SCHEMAS:
        connection.exec_driver_sql(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {_identifier(schema)} TO cmp_app"
        )
    for schema in ("access_control", "revisioning", "plugin", "artifact", "provenance", "audit"):
        connection.exec_driver_sql(
            f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {_identifier(schema)} TO cmp_app"
        )


def _seed_demo_role_bindings(connection: Connection, issuer: str) -> None:
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.principal (
              id, principal_type, display_name, active, created_at, updated_at
            ) VALUES (
              :id, 'service', 'CMP local demo bootstrap', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": _BOOTSTRAP_PRINCIPAL_ID},
    )
    for role in _DEMO_ROLES:
        connection.execute(
            sa.text(
                """
                INSERT INTO identity.role_binding (
                  id, organization_id, project_id, classification, subject_type,
                  principal_id, group_issuer, group_name, role, max_classification,
                  allow_export_controlled, valid_from, created_at, created_by, grant_reason,
                  revoked_at, revoked_by, revocation_reason
                ) VALUES (
                  :id, :organization_id, :project_id, 'restricted', 'group',
                  NULL, :issuer, :group_name, :role, 'restricted',
                  false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :created_by,
                  'Grant the explicit local demo group the minimum vertical-slice roles.',
                  NULL, NULL, NULL
                ) ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": uuid5(_BINDING_NAMESPACE, role),
                "organization_id": DEMO_ORGANIZATION_ID,
                "project_id": DEMO_PROJECT_ID,
                "issuer": issuer,
                "group_name": DEMO_GROUP,
                "role": role,
                "created_by": _BOOTSTRAP_PRINCIPAL_ID,
            },
        )


def bootstrap_demo_database(settings: Settings, *, application_password: str) -> None:
    """Apply local-demo role/grant/role-binding state through the owner connection."""

    identity = DemoIdentity.from_settings(settings)
    if identity is None:
        raise ValueError("CMP_DEMO_IDENTITY=true is required for the Docker Compose demo bootstrap")
    if not settings.database_url:
        raise ValueError("CMP_DATABASE_URL is required for the Docker Compose demo bootstrap")
    engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            _ensure_application_role(connection, application_password)
            _grant_runtime_privileges(connection)
            _seed_demo_role_bindings(connection, identity.issuer)
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap the explicit local CMP Docker Compose demo."
    )
    parser.add_argument(
        "--application-password-env",
        default="CMP_DEMO_APP_DATABASE_PASSWORD",
        help="Environment variable containing the non-owner cmp_app password.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    bootstrap_demo_database(
        Settings.from_environment(),
        application_password=_required_environment(args.application_password_env),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
