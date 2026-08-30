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

from cmp.bootstrap.database import ensure_application_role, grant_application_privileges
from cmp.bootstrap.demo_identity import (
    DEMO_GROUP,
    DEMO_ORGANIZATION_ID,
    DEMO_PROJECT_ID,
    DEMO_REVIEWER_GROUP,
    DEMO_USER_GROUP,
    DEMO_WORKER_CLIENT_ID,
    DEMO_WORKER_RUNNER_ID,
    DemoIdentity,
)
from cmp.bootstrap.settings import Settings

_ensure_application_role = ensure_application_role
_grant_runtime_privileges = grant_application_privileges

_BOOTSTRAP_PRINCIPAL_ID = UUID("d0000000-0000-4000-8000-000000000003")
_BINDING_NAMESPACE = UUID("d0000000-0000-4000-8000-000000000004")
_DEMO_ROLES = (
    "org_admin",
    "test_engineer",
    "data_steward",
    "statistical_analyst",
    "material_modeler",
    "cae_analyst",
    "auditor",
    "plugin_maintainer",
)


def _required_environment(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise ValueError(f"{name} is required for the Docker Compose demo bootstrap")
    return value


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
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.external_identity (
              id, principal_id, issuer, subject, created_at, last_seen_at
            ) VALUES (
              :id, :principal_id, :issuer, :subject, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) ON CONFLICT (issuer, subject) DO NOTHING
            """
        ),
        {
            "id": uuid5(_BINDING_NAMESPACE, "external-worker"),
            "principal_id": _BOOTSTRAP_PRINCIPAL_ID,
            "issuer": issuer,
            "subject": DEMO_WORKER_CLIENT_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.role_binding (
              id, organization_id, project_id, classification, subject_type,
              principal_id, group_issuer, group_name, role, max_classification,
              allow_export_controlled, valid_from, created_at, created_by, grant_reason,
              revoked_at, revoked_by, revocation_reason
            ) VALUES (
              :id, :organization_id, :project_id, 'restricted', 'principal',
              :principal_id, NULL, NULL, 'job_runner', 'restricted',
              false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :created_by,
              'Grant the explicit local demo worker only the operational Job Runner role.',
              NULL, NULL, NULL
            ) ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": uuid5(_BINDING_NAMESPACE, "worker-job-runner"),
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "principal_id": _BOOTSTRAP_PRINCIPAL_ID,
            "created_by": _BOOTSTRAP_PRINCIPAL_ID,
        },
    )
    # T-15 runner rows are operator-provisioned.  The worker may claim only a
    # pre-registered, tenant-scoped runner; it must never create an arbitrary
    # runner while processing a claim.  Keep both rows deterministic and safe to
    # replay when the demo bootstrap is run more than once.
    connection.execute(
        sa.text(
            """
            INSERT INTO jobs.runner (
              organization_id, project_id, id, classification, name, status,
              max_concurrency, cpu_capacity_millis, memory_capacity_mb, gpu_capacity,
              registered_at, created_by
            ) VALUES (
              :organization_id, :project_id, :id, 'restricted', 'cmp-demo-worker', 'active',
              1, 2000, 4096, 0, CURRENT_TIMESTAMP, :created_by
            ) ON CONFLICT (organization_id, project_id, id) DO NOTHING
            """
        ),
        {
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "id": DEMO_WORKER_RUNNER_ID,
            "created_by": _BOOTSTRAP_PRINCIPAL_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO jobs.runner_job_type (
              organization_id, project_id, classification, runner_id, job_type,
              created_at, created_by
            ) VALUES (
              :organization_id, :project_id, 'restricted', :runner_id, 'plugin.run',
              CURRENT_TIMESTAMP, :created_by
            ) ON CONFLICT (organization_id, project_id, runner_id, job_type) DO NOTHING
            """
        ),
        {
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "runner_id": DEMO_WORKER_RUNNER_ID,
            "created_by": _BOOTSTRAP_PRINCIPAL_ID,
        },
    )
    for role in _DEMO_ROLES:
        # Organization administrators are valid only at organization scope.  Plugin
        # maintenance and the remaining vertical-slice roles stay project-scoped.
        project_id = None if role == "org_admin" else DEMO_PROJECT_ID
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
                "project_id": project_id,
                "issuer": issuer,
                "group_name": DEMO_GROUP,
                "role": role,
                "created_by": _BOOTSTRAP_PRINCIPAL_ID,
            },
        )
    # Keep a separate reviewer group/persona for the end-to-end review journey.
    # Administrator deliberately has no MODEL_APPROVAL grant; the reviewer rows
    # below are the only demo bindings that can decide and publish a request.
    for role in ("domain_reviewer", "release_approver"):
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
                  'Grant the explicit local demo reviewer the minimum decision roles.',
                  NULL, NULL, NULL
                ) ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": uuid5(_BINDING_NAMESPACE, f"reviewer-{role}"),
                "organization_id": DEMO_ORGANIZATION_ID,
                "project_id": DEMO_PROJECT_ID,
                "issuer": issuer,
                "group_name": DEMO_REVIEWER_GROUP,
                "role": role,
                "created_by": _BOOTSTRAP_PRINCIPAL_ID,
            },
        )
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.product_access_assignment (
              id, organization_id, project_id, classification, subject_type,
              principal_id, group_issuer, group_name, product_role,
              schema_configuration, catalog_edit, processing_calibration,
              model_approval, solver_card_export, max_classification,
              allow_export_controlled, valid_from, created_at, created_by, grant_reason,
              revoked_at, revoked_by, revocation_reason
            ) VALUES (
              :id, :organization_id, :project_id, 'restricted', 'group',
              NULL, :issuer, :group_name, 'user',
              false, false, true, false, true, 'restricted',
              false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :created_by,
              'Grant the local demo User assignment for the review-request journey.',
              NULL, NULL, NULL
            ) ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": uuid5(_BINDING_NAMESPACE, "product-access-user"),
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "issuer": issuer,
            "group_name": DEMO_USER_GROUP,
            "created_by": _BOOTSTRAP_PRINCIPAL_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.product_access_assignment (
              id, organization_id, project_id, classification, subject_type,
              principal_id, group_issuer, group_name, product_role,
              schema_configuration, catalog_edit, processing_calibration,
              model_approval, solver_card_export, max_classification,
              allow_export_controlled, valid_from, created_at, created_by, grant_reason,
              revoked_at, revoked_by, revocation_reason
            ) VALUES (
              :id, :organization_id, :project_id, 'restricted', 'group',
              NULL, :issuer, :group_name, 'administrator',
              true, true, true, false, true, 'restricted',
              false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :created_by,
              'Grant the local demo group the product-facing Administrator assignment.',
              NULL, NULL, NULL
            ) ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": uuid5(_BINDING_NAMESPACE, "product-access-administrator"),
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "issuer": issuer,
            "group_name": DEMO_GROUP,
            "created_by": _BOOTSTRAP_PRINCIPAL_ID,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO identity.product_access_assignment (
              id, organization_id, project_id, classification, subject_type,
              principal_id, group_issuer, group_name, product_role,
              schema_configuration, catalog_edit, processing_calibration,
              model_approval, solver_card_export, max_classification,
              allow_export_controlled, valid_from, created_at, created_by, grant_reason,
              revoked_at, revoked_by, revocation_reason
            ) VALUES (
              :id, :organization_id, :project_id, 'restricted', 'group',
              NULL, :issuer, :group_name, 'reviewer',
              false, false, true, true, true, 'restricted',
              false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :created_by,
              'Grant the local demo Reviewer assignment for the review/publication journey.',
              NULL, NULL, NULL
            ) ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": uuid5(_BINDING_NAMESPACE, "product-access-reviewer"),
            "organization_id": DEMO_ORGANIZATION_ID,
            "project_id": DEMO_PROJECT_ID,
            "issuer": issuer,
            "group_name": DEMO_REVIEWER_GROUP,
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
            ensure_application_role(connection, application_password)
            grant_application_privileges(connection)
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
