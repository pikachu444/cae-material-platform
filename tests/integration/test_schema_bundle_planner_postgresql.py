from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
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
from cmp.modules.audit.adapters.persistence.repository import (
    SqlAlchemyAuditWriter,
    SqlAlchemyRevisionAuditHook,
)
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.adapters.persistence.schema_bundle_applications import (
    SqlAlchemySchemaBundleApplicationRepository,
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
from cmp.modules.catalog.application.records import CatalogRecordService, CreateRecord
from cmp.modules.catalog.application.schema_bundles import (
    ApplySchemaDefinitionBundle,
    PlanSchemaDefinitionBundle,
    SchemaBundleMigrationRequired,
    SchemaBundlePlannerService,
    SchemaBundleSourceConflict,
    SchemaBundleStalePlan,
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
from cmp.modules.catalog.domain.records import CatalogRecordContent, CatalogRecordValue
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
from cmp.modules.jobs.adapters.persistence.events import SqlAlchemyOutboxWriter
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyRevisionProvenanceHook,
    SqlAlchemySchemaBundleProvenanceWriter,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.shared.domain.revisions import content_sha256
from jsonschema import Draft202012Validator, FormatChecker
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
    records: CatalogRecordService
    artifacts: ArtifactService
    planner: SchemaBundlePlannerService
    applications: SqlAlchemySchemaBundleApplicationRepository
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


@pytest.fixture
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
            schema_repository = SqlAlchemyConfigurableCatalogRepository(
                session_factory=sessions,
                rls_context=rls,
                revision_hooks=hooks,
            )
            catalog = ConfigurableCatalogService(schema_repository)
            records = CatalogRecordService(
                SqlAlchemyCatalogRecordRepository(
                    session_factory=sessions,
                    rls_context=rls,
                    revision_hooks=hooks,
                ),
                schema_repository,
            )
            store = FilesystemMultipartObjectStore(Path(temporary))
            artifact_repository = SqlAlchemyArtifactRepository(
                session_factory=sessions,
                rls_context=rls,
                available_hooks=(SqlArtifactAvailableOutboxHook(),),
            )
            artifacts = ArtifactService(
                repository=artifact_repository,
                object_store=store,
                transfers=ArtifactTransferCodec(TRANSFER_SECRET, clock=lambda: NOW),
                clock=lambda: NOW,
            )
            probe = ReadOnlyTransactionProbe(rls)
            snapshots = SqlAlchemySchemaBundleSnapshotRepository(
                session_factory=sessions,
                rls_context=probe,
            )
            applications = SqlAlchemySchemaBundleApplicationRepository(
                session_factory=sessions,
                rls_context=rls,
                snapshots=snapshots,
                artifacts=artifact_repository,
                provenance=SqlAlchemySchemaBundleProvenanceWriter(),
                audit=SqlAlchemyAuditWriter(),
                outbox=SqlAlchemyOutboxWriter(),
                revision_hooks=hooks,
            )
            planner = SchemaBundlePlannerService(
                artifacts=artifacts,
                snapshots=snapshots,
                applications=applications,
            )
            yield Harness(
                admin_engine,
                catalog,
                records,
                artifacts,
                planner,
                applications,
                probe,
            )
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


def _bump_bundle_version(raw_bytes: bytes, version: str) -> dict[str, Any]:
    changed = cast(dict[str, Any], json.loads(raw_bytes))
    changed["bundle_version"] = version
    for changed_schema in changed["record_schemas"]:
        changed_schema["schema"] = json.loads(
            json.dumps(changed_schema["schema"]).replace(":1.0.0", f":{version}")
        )
        changed_schema["schema_sha256"] = content_sha256(changed_schema["schema"])
    return changed


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


def test_bundle_apply_is_atomic_idempotent_traceable_and_round_trips(
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
            idempotency_key="issue-207-postgresql-apply-source",
        )
    ).artifact
    plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(artifact.id, artifact.sha256),
        )
    )
    assert plan.valid
    command = ApplySchemaDefinitionBundle(
        artifact.id,
        artifact.sha256,
        plan.plan_fingerprint,
        "issue-207-first-apply",
    )
    first = asyncio.run(
        postgres.planner.apply(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            command,
        )
    )
    assert first.mutations_applied
    assert not first.replayed
    assert first.before_snapshot_fingerprint == plan.catalog_snapshot_fingerprint
    assert all(
        result.published
        for result in first.results
        if result.target_type != "profile_table_placement"
    )
    assert not any(result.external_key == "legacy_records" for result in first.results)
    database_result = next(result for result in first.results if result.target_type == "database")
    material_link_result = next(
        result
        for result in first.results
        if result.target_type == "link_type" and result.external_key == "tensile_test_material"
    )
    assert database_result.source_pointer == "/catalog/database"
    assert database_result.source_schema_version == "1.0.0"
    assert material_link_result.source_schema_id == "urn:cmp:catalog-schema:tensile_tests:1.0.0"
    assert material_link_result.source_schema_version == "1.0.0"
    assert material_link_result.source_pointer.endswith("/properties/material_id")

    replay = asyncio.run(
        postgres.planner.apply(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            command,
        )
    )
    assert replay.replayed
    assert replay.application_id == first.application_id

    fresh_plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(artifact.id, artifact.sha256),
        )
    )
    assert fresh_plan.valid
    assert {action.disposition for action in fresh_plan.actions} == {PlanDisposition.NO_OP}
    with postgres.admin_engine.connect() as connection:
        revision_count_before = int(
            connection.scalar(
                sa.text(
                    "SELECT (SELECT count(*) FROM catalog.database_revision) + "
                    "(SELECT count(*) FROM catalog.profile_revision) + "
                    "(SELECT count(*) FROM catalog.schema_table_revision) + "
                    "(SELECT count(*) FROM catalog.attribute_definition_revision) + "
                    "(SELECT count(*) FROM catalog.layout_revision) + "
                    "(SELECT count(*) FROM catalog.link_type_revision)"
                )
            )
            or 0
        )
    second = asyncio.run(
        postgres.planner.apply(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            ApplySchemaDefinitionBundle(
                artifact.id,
                artifact.sha256,
                fresh_plan.plan_fingerprint,
                "issue-207-second-no-op-apply",
            ),
        )
    )
    assert not second.mutations_applied
    with postgres.admin_engine.connect() as connection:
        revision_count_after = int(
            connection.scalar(
                sa.text(
                    "SELECT (SELECT count(*) FROM catalog.database_revision) + "
                    "(SELECT count(*) FROM catalog.profile_revision) + "
                    "(SELECT count(*) FROM catalog.schema_table_revision) + "
                    "(SELECT count(*) FROM catalog.attribute_definition_revision) + "
                    "(SELECT count(*) FROM catalog.layout_revision) + "
                    "(SELECT count(*) FROM catalog.link_type_revision)"
                )
            )
            or 0
        )
    assert revision_count_after == revision_count_before

    exported = asyncio.run(
        postgres.planner.export(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            "synthetic_dependency_chain",
        )
    )
    exported_artifact = asyncio.run(
        postgres.artifacts.finalize_derived_bytes(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            classification=DataClassification.INTERNAL,
            artifact_role="catalog.schema-definition-bundle",
            schema_ref="urn:cmp:catalog-schema-definition-bundle:1.0.0",
            media_type=MEDIA_TYPE,
            value=exported.value,
            idempotency_key="issue-207-round-trip-export",
        )
    ).artifact
    round_trip = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(exported_artifact.id, exported_artifact.sha256),
        )
    )
    assert round_trip.valid
    assert {action.disposition for action in round_trip.actions} == {PlanDisposition.NO_OP}

    with pytest.raises(SchemaBundleStalePlan):
        asyncio.run(
            postgres.planner.apply(
                context,
                _decision(context, Permission.CATALOG_SCHEMA_APPLY),
                ApplySchemaDefinitionBundle(
                    artifact.id,
                    artifact.sha256,
                    plan.plan_fingerprint,
                    "issue-207-stale-plan",
                ),
            )
        )
    with pytest.raises(SchemaBundleSourceConflict):
        asyncio.run(
            postgres.planner.apply(
                context,
                _decision(context, Permission.CATALOG_SCHEMA_APPLY),
                ApplySchemaDefinitionBundle(
                    artifact.id,
                    "0" * 64,
                    fresh_plan.plan_fingerprint,
                    "issue-207-checksum-mismatch",
                ),
            )
        )
    other_context = _context(OTHER_PROJECT)
    with pytest.raises(ArtifactNotFound):
        asyncio.run(
            postgres.planner.apply(
                other_context,
                _decision(other_context, Permission.CATALOG_SCHEMA_APPLY),
                ApplySchemaDefinitionBundle(
                    artifact.id,
                    artifact.sha256,
                    fresh_plan.plan_fingerprint,
                    "issue-207-tenant-mismatch",
                ),
            )
        )

    concurrent_plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(artifact.id, artifact.sha256),
        )
    )

    def concurrent_apply() -> UUID:
        worker_context = _context()
        result = asyncio.run(
            postgres.planner.apply(
                worker_context,
                _decision(worker_context, Permission.CATALOG_SCHEMA_APPLY),
                ApplySchemaDefinitionBundle(
                    artifact.id,
                    artifact.sha256,
                    concurrent_plan.plan_fingerprint,
                    "issue-207-concurrent-apply",
                ),
            )
        )
        return result.application_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent_ids = tuple(executor.map(lambda _: concurrent_apply(), range(2)))
    assert concurrent_ids[0] == concurrent_ids[1]

    changed = _bump_bundle_version(raw_bytes, "1.0.1")
    changed["catalog"]["database"]["description"] = "Rollback probe must never commit."
    changed_bytes = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
    changed_artifact = asyncio.run(
        postgres.artifacts.finalize_derived_bytes(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            classification=DataClassification.INTERNAL,
            artifact_role="catalog.schema-definition-bundle",
            schema_ref="urn:cmp:catalog-schema-definition-bundle:1.0.0",
            media_type=MEDIA_TYPE,
            value=changed_bytes,
            idempotency_key="issue-207-rollback-source",
        )
    ).artifact
    changed_plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(changed_artifact.id, changed_artifact.sha256),
        )
    )
    assert changed_plan.valid, tuple(
        diagnostic.canonical() for diagnostic in changed_plan.diagnostics
    )
    rollback_before = _database_state(postgres.admin_engine)

    def fail_after_second_action(sequence: int) -> None:
        if sequence == 1:
            raise RuntimeError("forced issue-207 rollback probe")

    postgres.applications._failure_injector = fail_after_second_action
    try:
        with pytest.raises(RuntimeError, match="forced issue-207 rollback probe"):
            asyncio.run(
                postgres.planner.apply(
                    context,
                    _decision(context, Permission.CATALOG_SCHEMA_APPLY),
                    ApplySchemaDefinitionBundle(
                        changed_artifact.id,
                        changed_artifact.sha256,
                        changed_plan.plan_fingerprint,
                        "issue-207-forced-rollback",
                    ),
                )
            )
    finally:
        postgres.applications._failure_injector = None
    assert _database_state(postgres.admin_engine) == rollback_before

    with postgres.admin_engine.connect() as connection:
        revision_count_before_change = int(
            connection.scalar(
                sa.text(
                    "SELECT (SELECT count(*) FROM catalog.database_revision) + "
                    "(SELECT count(*) FROM catalog.profile_revision) + "
                    "(SELECT count(*) FROM catalog.schema_table_revision) + "
                    "(SELECT count(*) FROM catalog.attribute_definition_revision) + "
                    "(SELECT count(*) FROM catalog.layout_revision) + "
                    "(SELECT count(*) FROM catalog.link_type_revision)"
                )
            )
            or 0
        )
    changed_application = asyncio.run(
        postgres.planner.apply(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            ApplySchemaDefinitionBundle(
                changed_artifact.id,
                changed_artifact.sha256,
                changed_plan.plan_fingerprint,
                "issue-207-changed-bundle-apply",
            ),
        )
    )
    changed_revisions = {
        (result.target_type, result.external_key)
        for result in changed_application.results
        if result.disposition is PlanDisposition.UPDATE
        and result.target_type != "profile_table_placement"
    }
    changed_placements = {
        result.external_key
        for result in changed_application.results
        if result.disposition is PlanDisposition.UPDATE
        and result.target_type == "profile_table_placement"
    }
    assert changed_placements == {
        "synthetic_materials.curves",
        "synthetic_materials.materials",
        "synthetic_materials.tensile_tests",
    }
    assert changed_revisions == {
        ("database", "synthetic_engineering"),
        ("profile", "synthetic_materials"),
    }
    assert not any(
        result.disposition is PlanDisposition.CREATE
        for result in changed_application.results
    )
    with postgres.admin_engine.connect() as connection:
        revision_count_after_change = int(
            connection.scalar(
                sa.text(
                    "SELECT (SELECT count(*) FROM catalog.database_revision) + "
                    "(SELECT count(*) FROM catalog.profile_revision) + "
                    "(SELECT count(*) FROM catalog.schema_table_revision) + "
                    "(SELECT count(*) FROM catalog.attribute_definition_revision) + "
                    "(SELECT count(*) FROM catalog.layout_revision) + "
                    "(SELECT count(*) FROM catalog.link_type_revision)"
                )
            )
            or 0
        )
    assert revision_count_after_change == revision_count_before_change + 2

    with postgres.admin_engine.connect() as connection:
        lineage_count = int(
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM provenance.derivation derivation "
                    "JOIN provenance.entity source ON source.id = derivation.used_entity_id "
                    "JOIN provenance.entity generated "
                    "ON generated.id = derivation.generated_entity_id "
                    "WHERE source.reference_kind = 'artifact' "
                    "AND source.reference_id = :artifact_id "
                    "AND source.content_sha256 = :sha256 "
                    "AND generated.reference_kind = 'revision' "
                    "AND derivation.derivation_kind = 'schema_definition_bundle_projection'"
                ),
                {"artifact_id": artifact.id, "sha256": artifact.sha256},
            )
            or 0
        )
        application_count = int(
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM catalog.schema_definition_bundle_application "
                    "WHERE idempotency_key = 'issue-207-concurrent-apply'"
                )
            )
            or 0
        )
        outbox_count = int(
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM events.outbox_event "
                    "WHERE event_type = 'io.cmp.catalog.schema-definition-bundle.applied.v1'"
                )
            )
            or 0
        )
        event_row = (
            connection.execute(
                sa.text(
                    "SELECT id, organization_id, project_id, classification, sequence_no, "
                    "source, event_type, subject, data_schema, data, occurred_at "
                    "FROM events.outbox_event WHERE data ->> 'application_id' = :application_id"
                ),
                {"application_id": str(first.application_id)},
            )
            .mappings()
            .one()
        )
    created_revision_count = sum(
        result.disposition in {PlanDisposition.CREATE, PlanDisposition.UPDATE}
        for result in first.results
        if result.target_type != "profile_table_placement"
    )
    assert lineage_count == created_revision_count
    assert application_count == 1
    assert outbox_count == 4
    event_envelope = {
        "specversion": "1.0",
        "id": str(event_row["id"]),
        "source": event_row["source"],
        "type": event_row["event_type"],
        "subject": event_row["subject"],
        "time": event_row["occurred_at"].isoformat().replace("+00:00", "Z"),
        "datacontenttype": "application/json",
        "dataschema": event_row["data_schema"],
        "cmpsequence": event_row["sequence_no"],
        "cmporganizationid": str(event_row["organization_id"]),
        "cmpprojectid": str(event_row["project_id"]),
        "cmpclassification": event_row["classification"],
        "data": event_row["data"],
    }
    event_contract = json.loads(
        (
            PROJECT_ROOT
            / "contracts/events/catalog-schema-definition-bundle-applied.v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        list(
            Draft202012Validator(event_contract, format_checker=FormatChecker()).iter_errors(
                event_envelope
            )
        )
        == []
    )


def test_bundle_apply_blocks_table_revision_when_current_records_need_migration(
    postgres: Harness,
) -> None:
    context = _context()
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
            idempotency_key="issue-207-record-conflict-source",
        )
    ).artifact
    plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(artifact.id, artifact.sha256),
        )
    )
    applied = asyncio.run(
        postgres.planner.apply(
            context,
            _decision(context, Permission.CATALOG_SCHEMA_APPLY),
            ApplySchemaDefinitionBundle(
                artifact.id,
                artifact.sha256,
                plan.plan_fingerprint,
                "issue-207-record-conflict-initial-apply",
            ),
        )
    )
    material_table = next(
        result
        for result in applied.results
        if result.target_type == "table" and result.external_key == "materials"
    )
    record_id_attribute = next(
        result
        for result in applied.results
        if result.target_type == "attribute"
        and result.parent_external_key == "materials"
        and result.external_key == "record_id"
    )
    assert material_table.aggregate_id is not None and material_table.revision_id is not None
    assert (
        record_id_attribute.aggregate_id is not None and record_id_attribute.revision_id is not None
    )
    postgres.records.create_record(
        context,
        _decision(context, Permission.CATALOG_WRITE),
        CreateRecord(
            DataClassification.INTERNAL,
            CatalogRecordContent(
                material_table.aggregate_id,
                material_table.revision_id,
                "Synthetic material that pins schema v1",
                external_key="issue-207-record-conflict",
                values=(
                    CatalogRecordValue(
                        record_id_attribute.aggregate_id,
                        record_id_attribute.revision_id,
                        AttributeDataType.TEXT,
                        value="MAT-207",
                    ),
                ),
            ),
            "Create current Record migration-conflict evidence",
        ),
    )

    changed = _bump_bundle_version(raw_bytes, "1.0.1")
    materials = next(record for record in changed["record_schemas"] if record["key"] == "materials")
    materials["name"] = "Synthetic materials revised"
    changed_bytes = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
    changed_artifact = asyncio.run(
        postgres.artifacts.finalize_derived_bytes(
            context,
            _decision(context, Permission.ARTIFACT_WRITE),
            classification=DataClassification.INTERNAL,
            artifact_role="catalog.schema-definition-bundle",
            schema_ref="urn:cmp:catalog-schema-definition-bundle:1.0.0",
            media_type=MEDIA_TYPE,
            value=changed_bytes,
            idempotency_key="issue-207-record-conflict-revision-source",
        )
    ).artifact
    changed_plan = asyncio.run(
        postgres.planner.plan(
            context,
            _decision(context, Permission.CATALOG_WRITE),
            PlanSchemaDefinitionBundle(changed_artifact.id, changed_artifact.sha256),
        )
    )
    assert not changed_plan.valid
    migration_action = next(
        action
        for action in changed_plan.actions
        if action.target_type == "table" and action.external_key == "materials"
    )
    assert migration_action.disposition is PlanDisposition.ERROR
    assert migration_action.reason_codes == ("record_migration_required",)
    assert any(
        diagnostic.code == "CMP-SCHEMA-BUNDLE-0014"
        and "materials" in diagnostic.message
        and "current Records" in diagnostic.message
        for diagnostic in changed_plan.diagnostics
    )
    before = _database_state(postgres.admin_engine)
    with pytest.raises(SchemaBundleMigrationRequired, match="approved migration"):
        asyncio.run(
            postgres.planner.apply(
                context,
                _decision(context, Permission.CATALOG_SCHEMA_APPLY),
                ApplySchemaDefinitionBundle(
                    changed_artifact.id,
                    changed_artifact.sha256,
                    changed_plan.plan_fingerprint,
                    "issue-207-record-conflict-apply",
                ),
            )
        )
    assert _database_state(postgres.admin_engine) == before
