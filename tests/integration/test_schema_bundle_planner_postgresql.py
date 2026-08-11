from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.artifacts.adapters.persistence.content import SqlAlchemyArtifactRepository
from cmp.modules.artifacts.adapters.storage.filesystem import FilesystemMultipartObjectStore
from cmp.modules.artifacts.application.content import (
    ArtifactService,
    ArtifactTransferCodec,
)
from cmp.modules.artifacts.domain.content import ArtifactNotFound
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.schema_bundles import (
    SqlAlchemySchemaBundleSnapshotRepository,
)
from cmp.modules.catalog.application.configurable import (
    ConfigurableCatalogService,
    CreateAttribute,
    CreateDatabase,
    CreateLayout,
    CreateProfile,
    CreateTable,
    PublishRevision,
    ReviseDatabase,
)
from cmp.modules.catalog.application.schema_bundles import (
    PlanSchemaDefinitionBundle,
    SchemaBundlePlannerService,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogProfileContent,
    CatalogTableContent,
    LayoutContent,
    LayoutItem,
)
from cmp.modules.catalog.domain.schema_bundles import PlanDisposition
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.adapters.persistence.artifact_events import SqlArtifactAvailableOutboxHook
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyRevisionProvenanceHook,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        POSTGRES_DSN is None,
        reason="CMP_TEST_POSTGRES_DSN is required for PostgreSQL integration",
    ),
]

NOW = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
ORG = UUID("20400000-0000-4000-8000-000000000001")
PROJECT = UUID("20400000-0000-4000-8000-000000000002")
OTHER_PROJECT = UUID("20400000-0000-4000-8000-000000000099")
ACTOR = UUID("20400000-0000-4000-8000-000000000003")
TRACE = "00-00000000000000000000000000000204-0000000000000204-01"
MEDIA_TYPE = "application/vnd.cmp.catalog-schema-definition-bundle+json"
TRANSFER_SECRET = b"issue-204-transfer-secret-at-least-32-bytes"
OBSERVED_SCHEMAS = ("artifact", "audit", "catalog", "events", "governance", "provenance")


@dataclass(frozen=True, slots=True)
class DatabaseState:
    fingerprint: str
    tables: dict[str, dict[str, Any]]


class ReadOnlyTransactionProbe:
    """Delegate RLS binding while recording PostgreSQL's transaction access mode."""

    def __init__(self, delegate: SqlAlchemyRlsContext) -> None:
        self._delegate = delegate
        self.observations: list[str] = []

    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._delegate.bind_authorization(session, context, decision)
        self.observations.append(str(session.scalar(sa.text("SHOW transaction_read_only"))))


@dataclass(frozen=True, slots=True)
class Harness:
    admin_engine: Engine
    catalog: ConfigurableCatalogService
    artifacts: ArtifactService
    planner: SchemaBundlePlannerService
    read_only_probe: ReadOnlyTransactionProbe


def _psycopg_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    if url.drivername != "postgresql+psycopg":
        raise ValueError("CMP_TEST_POSTGRES_DSN must use PostgreSQL with psycopg")
    return url


def _alembic_config(database_url: URL) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    configuration.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    return configuration


@pytest.fixture(scope="module")
def postgres() -> Iterator[Harness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_issue204_{uuid4().hex}"
    app_role = f"cmp_issue204_app_{uuid4().hex}"
    cluster = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        connection.exec_driver_sql(
            f'CREATE ROLE "{app_role}" LOGIN NOSUPERUSER NOCREATEDB '
            "NOCREATEROLE NOINHERIT NOBYPASSRLS"
        )

    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    with tempfile.TemporaryDirectory(prefix="cmp-issue204-object-store-") as temporary:
        try:
            command.upgrade(_alembic_config(database_url), "head")
            with admin_engine.begin() as connection:
                connection.execute(
                    sa.text(
                        "INSERT INTO identity.principal "
                        "(id, principal_type, display_name, active, created_at, updated_at) "
                        "VALUES (:id, 'user', 'Issue 204 Catalog Administrator', true, :now, :now)"
                    ),
                    {"id": ACTOR, "now": NOW},
                )
                connection.exec_driver_sql(
                    "GRANT USAGE ON SCHEMA identity, revisioning, access_control, governance, "
                    f'provenance, audit, catalog, artifact, events, plugin TO "{app_role}"'
                )
                for schema in (
                    "identity",
                    "governance",
                    "provenance",
                    "audit",
                    "catalog",
                    "artifact",
                    "events",
                    "plugin",
                ):
                    connection.exec_driver_sql(
                        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} "
                        f'TO "{app_role}"'
                    )
                connection.exec_driver_sql(
                    "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning, "
                    f'audit, artifact TO "{app_role}"'
                )

            app_engine = sa.create_engine(
                database_url.set(username=app_role, password=None), pool_pre_ping=True
            )
            sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
            rls = SqlAlchemyRlsContext()
            with sessions() as session, session.begin():
                rls.assert_application_role(session)
            hooks = (
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            )
            catalog = ConfigurableCatalogService(
                SqlAlchemyConfigurableCatalogRepository(
                    session_factory=sessions,
                    rls_context=rls,
                    revision_hooks=hooks,
                )
            )
            store = FilesystemMultipartObjectStore(Path(temporary))
            artifacts = ArtifactService(
                repository=SqlAlchemyArtifactRepository(
                    session_factory=sessions,
                    rls_context=rls,
                    available_hooks=(SqlArtifactAvailableOutboxHook(),),
                ),
                object_store=store,
                transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
                clock=lambda: NOW,
            )
            probe = ReadOnlyTransactionProbe(rls)
            planner = SchemaBundlePlannerService(
                artifacts=artifacts,
                snapshots=SqlAlchemySchemaBundleSnapshotRepository(
                    session_factory=sessions,
                    rls_context=probe,
                ),
            )
            yield Harness(admin_engine, catalog, artifacts, planner, probe)
        finally:
            if app_engine is not None:
                app_engine.dispose()
            admin_engine.dispose()
            with cluster.connect() as connection:
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}"')
                connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{app_role}"')
            cluster.dispose()


def _context(project_id: UUID = PROJECT) -> SecurityContext:
    request_id = uuid4()
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog Administrator", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=request_id,
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext, permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _database_state(engine: Engine) -> DatabaseState:
    tables: dict[str, dict[str, Any]] = {}
    with engine.connect() as connection:
        rows = connection.execute(
            sa.text(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' AND table_schema = ANY(:schemas) "
                "ORDER BY table_schema, table_name"
            ),
            {"schemas": list(OBSERVED_SCHEMAS)},
        ).mappings()
        preparer = connection.dialect.identifier_preparer
        for row in rows:
            schema = str(row["table_schema"])
            table = str(row["table_name"])
            qualified = f"{preparer.quote(schema)}.{preparer.quote(table)}"
            state = (
                connection.execute(
                    sa.text(
                        "SELECT count(*) AS row_count, "
                        "coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), "
                        f"'[]'::jsonb)::text AS rows FROM {qualified} AS t"
                    )
                )
                .mappings()
                .one()
            )
            rows_json = str(state["rows"])
            tables[f"{schema}.{table}"] = {
                "row_count": int(state["row_count"]),
                "rows_sha256": hashlib.sha256(rows_json.encode("utf-8")).hexdigest(),
            }
    canonical = json.dumps(tables, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return DatabaseState(hashlib.sha256(canonical.encode("utf-8")).hexdigest(), tables)


def _seed_catalog(service: ConfigurableCatalogService, context: SecurityContext) -> None:
    decision = _decision(context, Permission.CATALOG_WRITE)
    database = service.create_database(
        context,
        decision,
        CreateDatabase(
            DataClassification.INTERNAL,
            CatalogDatabaseContent("legacy_engineering", "Legacy engineering"),
            "seed existing Catalog state before the issue 204 dry-run",
        ),
    )
    profile = service.create_profile(
        context,
        decision,
        CreateProfile(
            DataClassification.INTERNAL,
            CatalogProfileContent(
                database.id,
                database.current.record.revision_id,
                "legacy_materials",
                "Legacy materials",
            ),
            "seed existing Catalog profile before the issue 204 dry-run",
        ),
    )
    table = service.create_table(
        context,
        decision,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("legacy_records", "Legacy records"),
            "seed an object that is absent from the incoming bundle",
            profile.id,
            profile.current.record.revision_id,
        ),
    )
    attribute = service.create_attribute(
        context,
        decision,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "legacy_key",
                "Legacy key",
                AttributeDataType.TEXT,
                required=True,
                maximum_length=64,
            ),
            "seed a current Attribute pointer before the issue 204 dry-run",
        ),
    )
    service.create_layout(
        context,
        decision,
        CreateLayout(
            LayoutContent(
                table.id,
                table.current.record.revision_id,
                "Legacy datasheet",
                items=(
                    LayoutItem(
                        attribute.id,
                        attribute.current.record.revision_id,
                        "Identity",
                        0,
                    ),
                ),
            ),
            "seed a current Layout pointer before the issue 204 dry-run",
        ),
    )
    publication = service.publish_revision(
        context,
        decision,
        PublishRevision(
            "catalog.configurable_table",
            table.id,
            table.current.record.revision_id,
        ),
    )
    assert publication.valid

    bundle_database_content = CatalogDatabaseContent(
        "synthetic_engineering",
        "Synthetic engineering",
        "Non-production schema bundle fixture.",
    )
    bundle_database = service.create_database(
        context,
        decision,
        CreateDatabase(
            DataClassification.INTERNAL,
            bundle_database_content,
            "seed a Bundle-owned Database before the issue 204 dry-run",
        ),
    )
    service.create_profile(
        context,
        decision,
        CreateProfile(
            DataClassification.INTERNAL,
            CatalogProfileContent(
                bundle_database.id,
                bundle_database.current.record.revision_id,
                "synthetic_materials",
                "Synthetic materials",
                "Non-production profile fixture.",
            ),
            "seed a Profile that pins the first exact Database revision",
        ),
    )
    service.revise_database(
        context,
        decision,
        bundle_database.id,
        ReviseDatabase(
            bundle_database.current.record.revision_id,
            bundle_database_content,
            "append semantically identical content to make the Profile dependency pin stale",
        ),
    )


def test_planner_is_repeatable_and_leaves_postgresql_state_byte_equivalent(
    postgres: Harness,
) -> None:
    context = _context()
    _seed_catalog(postgres.catalog, context)
    raw_bytes = (
        PROJECT_ROOT / "contracts" / "examples" / "positive" / "schema-definition-bundle-many.json"
    ).read_bytes()
    artifact = asyncio.run(
        postgres.artifacts.finalize_derived_bytes(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            classification=DataClassification.INTERNAL,
            artifact_role="catalog.schema-definition-bundle",
            schema_ref="urn:cmp:catalog-schema-definition-bundle:1.0.0",
            media_type=MEDIA_TYPE,
            value=raw_bytes,
            idempotency_key="issue-204-postgresql-no-write-bundle",
        )
    ).artifact
    request = PlanSchemaDefinitionBundle(artifact.id, artifact.sha256)
    decision = _decision(context, Permission.CATALOG_WRITE)
    before = _database_state(postgres.admin_engine)

    first = asyncio.run(postgres.planner.plan(context, decision, request))
    middle = _database_state(postgres.admin_engine)
    second = asyncio.run(postgres.planner.plan(context, decision, request))
    after = _database_state(postgres.admin_engine)

    assert first.valid and second.valid
    assert first.source_artifact.artifact_id == artifact.id
    assert first.source_artifact.organization_id == ORG
    assert first.source_artifact.project_id == PROJECT
    assert first.source_artifact.classification is DataClassification.INTERNAL
    assert first.source_artifact.media_type == MEDIA_TYPE
    assert first.source_artifact.size_bytes == len(raw_bytes)
    assert first.source_artifact.sha256 == hashlib.sha256(raw_bytes).hexdigest()
    assert first.plan_fingerprint == second.plan_fingerprint
    assert first.canonical() == second.canonical()
    assert first.canonical()["mutations_applied"] is False
    assert first.canonical()["delete_missing"] is False
    assert first.canonical()["write_set"] == []
    database_action = next(action for action in first.actions if action.target_type == "database")
    profile_action = next(action for action in first.actions if action.target_type == "profile")
    assert database_action.disposition is PlanDisposition.NO_OP
    assert profile_action.disposition is PlanDisposition.UPDATE
    assert profile_action.reason_codes == ("dependency_revision_changes",)
    assert not any(action.external_key == "legacy_records" for action in first.actions)
    assert before == middle == after
    assert postgres.read_only_probe.observations == ["on", "on"]
    assert before.tables["catalog.publication_marker"]["row_count"] == 1
    assert before.tables["artifact.artifact"]["row_count"] == 1
    assert before.tables["events.outbox_event"]["row_count"] == 1
    assert before.tables["audit.event"]["row_count"] > 0
    assert before.tables["provenance.entity"]["row_count"] > 0
    print(
        "ISSUE204_POSTGRES_NO_WRITE="
        + json.dumps(
            {
                "before_fingerprint": before.fingerprint,
                "middle_fingerprint": middle.fingerprint,
                "after_fingerprint": after.fingerprint,
                "observed_table_count": len(before.tables),
                "observed_row_count": sum(
                    int(value["row_count"]) for value in before.tables.values()
                ),
                "transaction_read_only": postgres.read_only_probe.observations,
                "plan_fingerprint": first.plan_fingerprint,
                "artifact_id": str(artifact.id),
                "artifact_sha256": artifact.sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    other_context = _context(OTHER_PROJECT)
    with pytest.raises(ArtifactNotFound):
        asyncio.run(
            postgres.planner.plan(
                other_context,
                _decision(other_context, Permission.CATALOG_WRITE),
                request,
            )
        )
    assert _database_state(postgres.admin_engine) == after
