"""Owner-only bootstrap for the non-owner CMP application database role."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.engine import Connection

APPLICATION_ROLE = "cmp_app"
APPLICATION_SCHEMAS = (
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
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def ensure_application_role(connection: Connection, password: str) -> None:
    """Create or harden the application role and rotate its supplied password."""

    if not password:
        raise ValueError("application database password must be non-empty")
    exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = :name"),
        {"name": APPLICATION_ROLE},
    ).scalar_one_or_none()
    if exists is None:
        connection.exec_driver_sql(
            "CREATE ROLE cmp_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )
    connection.exec_driver_sql(
        "ALTER ROLE cmp_app NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
    )
    quoted = connection.execute(
        sa.text("SELECT quote_literal(:password)"), {"password": password}
    ).scalar_one()
    connection.exec_driver_sql(f"ALTER ROLE {APPLICATION_ROLE} PASSWORD {quoted}")


def grant_application_privileges(connection: Connection) -> None:
    """Grant the existing least-privilege runtime surface after migrations."""

    database = connection.execute(sa.text("SELECT current_database()")).scalar_one()
    schema_names = ", ".join(_identifier(name) for name in APPLICATION_SCHEMAS)
    connection.exec_driver_sql(
        f"GRANT CONNECT ON DATABASE {_identifier(database)} TO {APPLICATION_ROLE}"
    )
    connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema_names} TO {APPLICATION_ROLE}")
    connection.exec_driver_sql(
        "GRANT SELECT, INSERT, UPDATE ON identity.principal, identity.external_identity, "
        "identity.role_binding, identity.product_access_assignment TO cmp_app"
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
    for schema in APPLICATION_SCHEMAS:
        connection.exec_driver_sql(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {_identifier(schema)} TO cmp_app"
        )
    for schema in ("access_control", "revisioning", "plugin", "artifact", "provenance", "audit"):
        connection.exec_driver_sql(
            f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {_identifier(schema)} TO cmp_app"
        )
