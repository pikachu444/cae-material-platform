from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.application.configurable import (
    ConfigurableCatalogService,
    CreateAttribute,
    CreateDatabase,
    CreateLayout,
    CreateProfile,
    CreateSubset,
    CreateTable,
    PublishRevision,
    ReviseLayout,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDatabaseContent,
    CatalogProfileContent,
    CatalogTableContent,
    LayoutContent,
    LayoutItem,
    SubsetContent,
)
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
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
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

NOW = datetime(2026, 7, 17, 15, 0, tzinfo=UTC)
ORG = UUID("da000000-0000-4000-8000-000000000001")
PROJECT = UUID("da000000-0000-4000-8000-000000000002")
ACTOR = UUID("da000000-0000-4000-8000-000000000003")
TRACE = "00-000000000000000000000000000000da-00000000000000da-01"


@dataclass(frozen=True, slots=True)
class Harness:
    admin_engine: Engine
    service: ConfigurableCatalogService


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
    database_name = f"cmp_t49_{uuid4().hex}"
    app_role = f"cmp_t49_app_{uuid4().hex}"
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
    try:
        command.upgrade(_alembic_config(database_url), "head")
        command.downgrade(_alembic_config(database_url), "20260922_091_uxc07_evidence")
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO identity.principal "
                    "(id, principal_type, display_name, active, created_at, updated_at) "
                    "VALUES (:id, 'user', 'T49 Catalog Administrator', true, :now, :now)"
                ),
                {"id": ACTOR, "now": NOW},
            )
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA catalog, access_control, revisioning TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalog "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning "
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        yield Harness(
            admin_engine=admin_engine,
            service=ConfigurableCatalogService(
                SqlAlchemyConfigurableCatalogRepository(
                    session_factory=sessions,
                    rls_context=rls,
                )
            ),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster.connect() as connection:
            connection.exec_driver_sql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{database_name}' AND pid <> pg_backend_pid()"
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


def test_configurable_schema_round_trip_revision_and_typed_guards(
    postgres: Harness,
) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    database = postgres.service.create_database(
        context,
        write,
        CreateDatabase(
            DataClassification.INTERNAL,
            CatalogDatabaseContent("engineering", "Engineering database"),
            "create configurable database",
        ),
    )
    profile = postgres.service.create_profile(
        context,
        write,
        CreateProfile(
            DataClassification.INTERNAL,
            CatalogProfileContent(
                database.id,
                database.current.record.revision_id,
                "materials",
                "Materials profile",
            ),
            "create configurable profile",
        ),
    )
    table = postgres.service.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("materials", "Materials"),
            "create configurable materials table",
            profile.id,
            profile.current.record.revision_id,
        ),
    )
    with postgres.admin_engine.connect() as connection:
        placement = (
            connection.execute(
                sa.text(
                    "SELECT profile_id, profile_revision_id FROM catalog.table_profile_placement "
                    "WHERE table_id = :table_id AND table_revision_id = :table_revision_id"
                ),
                {"table_id": table.id, "table_revision_id": table.current.record.revision_id},
            )
            .mappings()
            .one()
        )
    assert placement["profile_id"] == profile.id
    assert placement["profile_revision_id"] == profile.current.record.revision_id
    validation = postgres.service.publish_revision(
        context,
        write,
        PublishRevision("catalog.configurable_table", table.id, table.current.record.revision_id),
    )
    assert validation.valid
    other_context = _context(uuid4())
    assert (
        postgres.service.list_tables(
            other_context,
            _decision(other_context, Permission.CATALOG_READ),
        )
        == ()
    )
    with postgres.admin_engine.begin() as connection:
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                sa.text(
                    "UPDATE catalog.publication_marker SET published_at = now() "
                    "WHERE aggregate_id = :table_id"
                ),
                {"table_id": table.id},
            )
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                sa.text("DELETE FROM catalog.table_profile_placement WHERE table_id = :table_id"),
                {"table_id": table.id},
            )
    attribute = postgres.service.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "youngs_modulus",
                "Young's modulus",
                AttributeDataType.NUMBER,
                required=True,
                quantity_semantics="modulus.elastic.young",
                normalized_unit="Pa",
                minimum_number=0,
            ),
            "add governed modulus attribute",
        ),
    )
    layout = postgres.service.create_layout(
        context,
        write,
        CreateLayout(
            LayoutContent(
                table.id,
                table.current.record.revision_id,
                "Engineering datasheet",
                items=(
                    LayoutItem(
                        attribute.id,
                        attribute.current.record.revision_id,
                        "Mechanical",
                        0,
                    ),
                ),
            ),
            "create layout revision one",
        ),
    )
    revised = postgres.service.revise_layout(
        context,
        write,
        layout.id,
        ReviseLayout(
            layout.current.record.revision_id,
            LayoutContent(
                table.id,
                table.current.record.revision_id,
                "Engineering datasheet",
                "Revision two",
                layout.current.content.items,
            ),
            "document datasheet layout",
        ),
    )
    subset = postgres.service.create_subset(
        context,
        write,
        CreateSubset(
            SubsetContent(
                table.id,
                table.current.record.revision_id,
                "All records",
                filter_definition={},
            ),
            "create saved subset",
        ),
    )

    assert revised.current.record.revision_no == 2
    assert len(postgres.service.list_attributes(context, read, table.id)) == 1
    assert postgres.service.list_layouts(context, read, table.id)[0].current.content.items == (
        layout.current.content.items[0],
    )
    assert postgres.service.list_subsets(context, read, table.id)[0].id == subset.id

    record_id = uuid4()
    record_revision_id = uuid4()
    base_values = {
        "organization_id": ORG,
        "project_id": PROJECT,
        "classification": "internal",
    }
    with postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO catalog.catalog_record "
                "(id, organization_id, project_id, classification, current_revision_id, "
                "created_at, created_by, updated_at, table_id) VALUES "
                "(:record_id, :organization_id, :project_id, :classification, :revision_id, "
                ":now, :actor, :now, :table_id)"
            ),
            {
                **base_values,
                "record_id": record_id,
                "revision_id": record_revision_id,
                "now": NOW,
                "actor": ACTOR,
                "table_id": table.id,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO catalog.catalog_record_revision "
                "(id, aggregate_id, organization_id, project_id, classification, revision_no, "
                "based_on_revision_id, schema_id, schema_version, content_hash, created_at, "
                "created_by, change_reason, request_id, trace_id, table_id, table_revision_id, "
                "name, external_key, description) VALUES "
                "(:revision_id, :record_id, :organization_id, :project_id, :classification, 1, "
                "NULL, 'urn:cmp:catalog:record:1.0.0', '1.0.0', :hash, :now, :actor, "
                "'typed guard fixture', :request_id, :trace_id, :table_id, :table_revision_id, "
                "'DP780', NULL, NULL)"
            ),
            {
                **base_values,
                "record_id": record_id,
                "revision_id": record_revision_id,
                "hash": "e" * 64,
                "now": NOW,
                "actor": ACTOR,
                "request_id": uuid4(),
                "trace_id": TRACE,
                "table_id": table.id,
                "table_revision_id": table.current.record.revision_id,
            },
        )
        value_parameters = {
            **base_values,
            "record_id": record_id,
            "record_revision_id": record_revision_id,
            "attribute_id": attribute.id,
            "attribute_revision_id": attribute.current.record.revision_id,
            "original_value": 210,
            "original_unit": "GPa",
            "normalized_value": 210_000_000_000,
            "quantity": "modulus.elastic.young",
        }
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(
                sa.text(
                    "INSERT INTO catalog.record_number_value "
                    "(organization_id, project_id, classification, record_id, "
                    "record_revision_id, attribute_definition_id, "
                    "attribute_definition_revision_id, original_value, original_unit_string, "
                    "normalized_value, normalized_unit, quantity_semantics) VALUES "
                    "(:organization_id, :project_id, :classification, :record_id, "
                    ":record_revision_id, :attribute_id, :attribute_revision_id, "
                    ":original_value, :original_unit, :normalized_value, 'MPa', :quantity)"
                ),
                value_parameters,
            )
        connection.execute(
            sa.text(
                "INSERT INTO catalog.record_number_value "
                "(organization_id, project_id, classification, record_id, record_revision_id, "
                "attribute_definition_id, attribute_definition_revision_id, original_value, "
                "original_unit_string, normalized_value, normalized_unit, quantity_semantics) "
                "VALUES (:organization_id, :project_id, :classification, :record_id, "
                ":record_revision_id, :attribute_id, :attribute_revision_id, :original_value, "
                ":original_unit, :normalized_value, 'Pa', :quantity)"
            ),
            value_parameters,
        )

    with postgres.admin_engine.connect() as connection:
        assert (
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM catalog.layout_revision WHERE aggregate_id = :layout_id"
                ),
                {"layout_id": layout.id},
            )
            == 2
        )
        assert connection.scalar(sa.text("SELECT count(*) FROM catalog.record_number_value")) == 1
