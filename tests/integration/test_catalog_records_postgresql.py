from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.links import SqlAlchemyCatalogLinkRepository
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.adapters.persistence.repository import SqlAlchemyCatalogRepository
from cmp.modules.catalog.application.configurable import (
    ConfigurableCatalogService,
    CreateAttribute,
    CreateTable,
)
from cmp.modules.catalog.application.links import (
    BindDomainRevision,
    CatalogLinkService,
    CreateLinkType,
    CreateRecordLink,
    DomainBindingKind,
    ReviseRecordLink,
)
from cmp.modules.catalog.application.records import (
    CatalogRecordService,
    CreateFolder,
    CreateRecord,
    ReviseFolder,
    ReviseRecord,
)
from cmp.modules.catalog.application.service import CatalogService, CreateMaterial
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogTableContent,
    ConfigurableCatalogConflict,
)
from cmp.modules.catalog.domain.links import LinkCardinality, LinkTypeContent, RecordLinkContent
from cmp.modules.catalog.domain.model import MaterialClass, MaterialContent
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    DiscreteFilter,
    NumberRangeFilter,
)
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
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

NOW = datetime(2026, 7, 18, 9, 0, tzinfo=UTC)
ORG = UUID("db000000-0000-4000-8000-000000000001")
PROJECT = UUID("db000000-0000-4000-8000-000000000002")
ACTOR = UUID("db000000-0000-4000-8000-000000000003")
TRACE = "00-000000000000000000000000000000db-00000000000000db-01"


@dataclass(frozen=True, slots=True)
class Harness:
    admin_engine: Engine
    schemas: ConfigurableCatalogService
    records: CatalogRecordService
    links: CatalogLinkService
    catalog: CatalogService


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
    database_name = f"cmp_t50_{uuid4().hex}"
    app_role = f"cmp_t50_app_{uuid4().hex}"
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
        with admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO identity.principal "
                    "(id, principal_type, display_name, active, created_at, updated_at) "
                    "VALUES (:id, 'user', 'T50 Catalog User', true, :now, :now)"
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
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA catalog, access_control, revisioning "
                f'TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        schema_repository = SqlAlchemyConfigurableCatalogRepository(
            session_factory=sessions, rls_context=rls
        )
        record_repository = SqlAlchemyCatalogRecordRepository(
            session_factory=sessions, rls_context=rls
        )
        yield Harness(
            admin_engine=admin_engine,
            schemas=ConfigurableCatalogService(schema_repository),
            records=CatalogRecordService(record_repository, schema_repository),
            links=CatalogLinkService(
                SqlAlchemyCatalogLinkRepository(session_factory=sessions, rls_context=rls),
                schema_repository,
                record_repository,
            ),
            catalog=CatalogService(
                repository=SqlAlchemyCatalogRepository(session_factory=sessions, rls_context=rls)
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


def _context() -> SecurityContext:
    request_id = uuid4()
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog User", True),
        organization_id=ORG,
        project_id=PROJECT,
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
        project_id=PROJECT,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def test_record_round_trip_search_facet_compare_and_folder_cycle(postgres: Harness) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("engineering_materials", "Engineering Materials"),
            "create T50 materials table",
        ),
    )
    modulus = postgres.schemas.create_attribute(
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
            "add modulus",
        ),
    )
    family = postgres.schemas.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "material_family",
                "Material family",
                AttributeDataType.DISCRETE,
                allowed_values=("Steel", "Aluminum"),
            ),
            "add family facet",
        ),
    )
    maker = postgres.schemas.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "manufacturer",
                "Manufacturer",
                AttributeDataType.TEXT,
            ),
            "add manufacturer",
        ),
    )
    root = postgres.records.create_folder(
        context,
        write,
        CreateFolder(
            DataClassification.INTERNAL,
            CatalogFolderContent(table.id, table.current.record.revision_id, "Metals"),
            "create root folder",
        ),
    )
    child = postgres.records.create_folder(
        context,
        write,
        CreateFolder(
            DataClassification.INTERNAL,
            CatalogFolderContent(
                table.id,
                table.current.record.revision_id,
                "Steels",
                parent_folder_id=root.id,
                parent_folder_revision_id=root.current.record.revision_id,
            ),
            "create child folder",
        ),
    )
    with pytest.raises(ConfigurableCatalogConflict, match="cycle"):
        postgres.records.revise_folder(
            context,
            write,
            root.id,
            ReviseFolder(
                root.current.record.revision_id,
                CatalogFolderContent(
                    table.id,
                    table.current.record.revision_id,
                    "Metals",
                    parent_folder_id=child.id,
                    parent_folder_revision_id=child.current.record.revision_id,
                ),
                "attempt cycle",
            ),
        )

    def content(name: str, e_pa: str, category: str, manufacturer: str) -> CatalogRecordContent:
        return CatalogRecordContent(
            table.id,
            table.current.record.revision_id,
            name,
            external_key=name.lower().replace(" ", "-"),
            folder_id=child.id,
            folder_revision_id=child.current.record.revision_id,
            values=(
                CatalogRecordValue(
                    modulus.id,
                    modulus.current.record.revision_id,
                    AttributeDataType.NUMBER,
                    original_value=Decimal(e_pa) / Decimal("1000000"),
                    original_unit_string="MPa",
                    normalized_value=Decimal(e_pa),
                    normalized_unit="Pa",
                    quantity_semantics="modulus.elastic.young",
                ),
                CatalogRecordValue(
                    family.id,
                    family.current.record.revision_id,
                    AttributeDataType.DISCRETE,
                    value=category,
                ),
                CatalogRecordValue(
                    maker.id,
                    maker.current.record.revision_id,
                    AttributeDataType.TEXT,
                    value=manufacturer,
                ),
            ),
        )

    steel = postgres.records.create_record(
        context,
        write,
        CreateRecord(
            DataClassification.INTERNAL,
            content("DP600 Sheet", "210000000000", "Steel", "CMP Demo Mill"),
            "create steel record",
        ),
    )
    postgres.records.create_record(
        context,
        write,
        CreateRecord(
            DataClassification.INTERNAL,
            content("AA6061-T6", "69000000000", "Aluminum", "Reference Metals"),
            "create aluminum record",
        ),
    )

    result = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(
            table.id,
            text="demo mill",
            discrete_filters=(DiscreteFilter(family.id, ("Steel",)),),
            number_filters=(NumberRangeFilter(modulus.id, minimum=Decimal("200000000000")),),
            facet_attribute_ids=(family.id,),
        ),
    )
    assert result.total_count == 1
    assert result.items[0].id == steel.id
    assert result.facets[0].value == "Steel"
    assert result.facets[0].count == 1

    revised = postgres.records.revise_record(
        context,
        write,
        steel.id,
        ReviseRecord(
            steel.current.record.revision_id,
            content("DP600 Sheet", "205000000000", "Steel", "CMP Demo Mill"),
            "revise normalized modulus",
        ),
    )
    comparison = postgres.records.compare_record_revisions(
        context,
        read,
        steel.id,
        steel.current.record.revision_id,
        revised.current.record.revision_id,
    )
    modulus_diff = next(
        item for item in comparison.value_differences if item.attribute_definition_id == modulus.id
    )
    assert modulus_diff.status == "changed"
    assert modulus_diff.before is not None
    assert modulus_diff.before.normalized_value == Decimal("210000000000")
    assert modulus_diff.after is not None
    assert modulus_diff.after.normalized_value == Decimal("205000000000")
    assert len(postgres.records.list_record_revisions(context, read, steel.id)) == 2

    with postgres.admin_engine.connect() as connection:
        version = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
        assert version == "20260917_082_t76_current_binding"
        validator = connection.execute(
            sa.text(
                "SELECT p.prosecdef, p.proconfig, "
                "has_function_privilege('public', p.oid, 'execute') AS public_execute "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='catalog' AND p.proname='validate_domain_record_binding'"
            )
        ).one()
        assert validator.prosecdef is True
        assert validator.proconfig == ["search_path=pg_catalog"]
        assert validator.public_execute is False


def test_dual_explorer_exact_links_reverse_query_cardinality_and_deactivation(
    postgres: Harness,
) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    material_table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("workflow_materials", "Workflow Materials"),
            "create workflow material table",
        ),
    )
    test_table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("workflow_tests", "Workflow Tests"),
            "create workflow test table",
        ),
    )
    folder = postgres.records.create_folder(
        context,
        write,
        CreateFolder(
            DataClassification.INTERNAL,
            CatalogFolderContent(
                material_table.id,
                material_table.current.record.revision_id,
                "Metals",
            ),
            "create workflow folder",
        ),
    )
    material = postgres.records.create_record(
        context,
        write,
        CreateRecord(
            DataClassification.INTERNAL,
            CatalogRecordContent(
                material_table.id,
                material_table.current.record.revision_id,
                "DP780",
                folder_id=folder.id,
                folder_revision_id=folder.current.record.revision_id,
            ),
            "create workflow material",
        ),
    )
    tensile = postgres.records.create_record(
        context,
        write,
        CreateRecord(
            DataClassification.INTERNAL,
            CatalogRecordContent(
                test_table.id,
                test_table.current.record.revision_id,
                "DP780 tensile run 1",
            ),
            "create tensile record",
        ),
    )
    second_test = postgres.records.create_record(
        context,
        write,
        CreateRecord(
            DataClassification.INTERNAL,
            CatalogRecordContent(
                test_table.id,
                test_table.current.record.revision_id,
                "DP780 tensile run 2",
            ),
            "create second tensile record",
        ),
    )
    link_type = postgres.links.create_link_type(
        context,
        write,
        CreateLinkType(
            DataClassification.INTERNAL,
            LinkTypeContent(
                "material_test_evidence",
                "Material test evidence",
                material_table.id,
                material_table.current.record.revision_id,
                test_table.id,
                test_table.current.record.revision_id,
                "has test evidence",
                "is test evidence for",
                LinkCardinality.ONE,
                LinkCardinality.MANY,
            ),
            "define material to test link",
        ),
    )
    content = RecordLinkContent(
        link_type.id,
        link_type.current.record.revision_id,
        material.id,
        material.current.record.revision_id,
        tensile.id,
        tensile.current.record.revision_id,
        note="exact test evidence",
    )
    link = postgres.links.create_record_link(
        context,
        write,
        CreateRecordLink(DataClassification.INTERNAL, content, "link exact test evidence"),
    )
    governed_material = postgres.catalog.create_material(
        context,
        write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("DP780 governed", material_class=MaterialClass.METAL),
            "create governed Material for exact workflow binding",
        ),
    )
    binding = postgres.links.bind_domain_revision(
        context,
        write,
        material.id,
        material.current.record.revision_id,
        BindDomainRevision(
            DomainBindingKind.MATERIAL,
            governed_material.id,
            governed_material.current.record.revision_id,
        ),
    )
    assert binding.workbench_path == (
        f"/materials/{governed_material.id}?revision_id={governed_material.current.record.revision_id}"
    )
    resolved_binding = postgres.links.resolve_domain_binding(
        context,
        read,
        DomainBindingKind.MATERIAL,
        governed_material.id,
        governed_material.current.record.revision_id,
    )
    assert resolved_binding == binding
    assert (
        postgres.links.resolve_domain_binding(
            context,
            read,
            DomainBindingKind.MATERIAL,
            governed_material.id,
            uuid4(),
        )
        is None
    )
    forward = postgres.links.list_record_links(
        context,
        read,
        material.id,
        record_revision_id=material.current.record.revision_id,
    )
    reverse = postgres.links.list_record_links(
        context,
        read,
        tensile.id,
        record_revision_id=tensile.current.record.revision_id,
    )
    assert forward[0].link.id == link.id
    assert reverse[0].link.id == link.id
    assert reverse[0].link_type.content.reverse_label == "is test evidence for"
    graph = postgres.links.workflow_graph(
        context,
        read,
        material.id,
        material.current.record.revision_id,
        depth=8,
    )
    assert {node.name for node in graph.nodes} == {"DP780", "DP780 tensile run 1"}
    assert graph.root.domain_binding == binding
    with pytest.raises(sa.exc.IntegrityError, match="exact revision in the same scope"):
        postgres.links.bind_domain_revision(
            context,
            write,
            tensile.id,
            tensile.current.record.revision_id,
            BindDomainRevision(DomainBindingKind.MATERIAL, uuid4(), uuid4()),
        )
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE catalog.domain_record_binding SET domain_revision_id=:revision "
                    "WHERE id=:binding"
                ),
                {"revision": uuid4(), "binding": binding.id},
            )
    children = postgres.links.explorer_children(context, read, material_table.id, folder.id)
    assert children.records[0].id == material.id

    with pytest.raises(ConfigurableCatalogConflict, match="cardinality"):
        postgres.links.create_record_link(
            context,
            write,
            CreateRecordLink(
                DataClassification.INTERNAL,
                RecordLinkContent(
                    link_type.id,
                    link_type.current.record.revision_id,
                    material.id,
                    material.current.record.revision_id,
                    second_test.id,
                    second_test.current.record.revision_id,
                ),
                "exceed one outgoing target",
            ),
        )

    revised_material = postgres.records.revise_record(
        context,
        write,
        material.id,
        ReviseRecord(
            material.current.record.revision_id,
            CatalogRecordContent(
                material_table.id,
                material_table.current.record.revision_id,
                "DP780 reviewed",
                folder_id=folder.id,
                folder_revision_id=folder.current.record.revision_id,
            ),
            "revise material without moving link",
        ),
    )
    assert not postgres.links.list_record_links(
        context,
        read,
        material.id,
        record_revision_id=revised_material.current.record.revision_id,
    )
    assert postgres.links.list_record_links(
        context,
        read,
        material.id,
        record_revision_id=material.current.record.revision_id,
    )
    revised_binding = postgres.links.bind_domain_revision(
        context,
        write,
        material.id,
        revised_material.current.record.revision_id,
        BindDomainRevision(
            DomainBindingKind.MATERIAL,
            governed_material.id,
            governed_material.current.record.revision_id,
        ),
    )
    assert revised_binding.record_revision_id == revised_material.current.record.revision_id
    assert (
        postgres.links.get_domain_binding(
            context,
            read,
            material.id,
            material.current.record.revision_id,
        )
        == binding
    )
    assert (
        postgres.links.resolve_domain_binding(
            context,
            read,
            DomainBindingKind.MATERIAL,
            governed_material.id,
            governed_material.current.record.revision_id,
        )
        == revised_binding
    )
    with pytest.raises(sa.exc.IntegrityError):
        postgres.links.bind_domain_revision(
            context,
            write,
            tensile.id,
            tensile.current.record.revision_id,
            BindDomainRevision(
                DomainBindingKind.MATERIAL,
                governed_material.id,
                governed_material.current.record.revision_id,
            ),
        )
    advanced_link = postgres.links.revise_record_link(
        context,
        write,
        link.id,
        ReviseRecordLink(
            link.current.record.revision_id,
            RecordLinkContent(
                content.link_type_id,
                content.link_type_revision_id,
                content.source_record_id,
                revised_material.current.record.revision_id,
                content.target_record_id,
                content.target_record_revision_id,
                active=True,
                note="advance the stable relationship to the reviewed Material revision",
            ),
            "advance exact source revision without changing the stable relationship",
        ),
    )
    assert (
        postgres.links.list_record_links(
            context,
            read,
            material.id,
            record_revision_id=revised_material.current.record.revision_id,
        )[0].link.current.record.revision_id
        == advanced_link.current.record.revision_id
    )

    deactivated = postgres.links.revise_record_link(
        context,
        write,
        link.id,
        ReviseRecordLink(
            advanced_link.current.record.revision_id,
            RecordLinkContent(
                content.link_type_id,
                content.link_type_revision_id,
                content.source_record_id,
                revised_material.current.record.revision_id,
                content.target_record_id,
                content.target_record_revision_id,
                active=False,
                note="superseded evidence relation",
            ),
            "deactivate without deleting history",
        ),
    )
    assert deactivated.current.record.revision_no == 3
    assert not postgres.links.list_record_links(context, read, tensile.id)
    historical = postgres.links.list_record_links(context, read, tensile.id, include_inactive=True)
    assert historical[0].link.current.content.active is False


def test_ten_thousand_record_search_is_counted_and_page_bounded(postgres: Harness) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("performance_materials", "Performance Materials"),
            "create bounded-search fixture table",
        ),
    )
    now = datetime.now(UTC)
    identities: list[dict[str, object]] = []
    revisions: list[dict[str, object]] = []
    for index in range(10_000):
        record_id = uuid5(NAMESPACE_URL, f"cmp-t50-record-{index}")
        revision_id = uuid5(NAMESPACE_URL, f"cmp-t50-record-revision-{index}")
        identities.append(
            {
                "id": record_id,
                "org": ORG,
                "project": PROJECT,
                "revision": revision_id,
                "now": now,
                "actor": ACTOR,
                "table": table.id,
            }
        )
        revisions.append(
            {
                "id": revision_id,
                "aggregate": record_id,
                "org": ORG,
                "project": PROJECT,
                "hash": f"{index:064x}",
                "now": now,
                "actor": ACTOR,
                "request": uuid5(NAMESPACE_URL, f"cmp-t50-request-{index}"),
                "table": table.id,
                "table_revision": table.current.record.revision_id,
                "name": f"Synthetic Material {index:05d}",
                "key": f"synthetic-{index:05d}",
            }
        )
    with postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO catalog.catalog_record "
                "(id, organization_id, project_id, classification, current_revision_id, "
                "created_at, created_by, updated_at, table_id) VALUES "
                "(:id, :org, :project, 'internal', :revision, :now, :actor, :now, :table)"
            ),
            identities,
        )
        connection.execute(
            sa.text(
                "INSERT INTO catalog.catalog_record_revision "
                "(id, aggregate_id, organization_id, project_id, classification, revision_no, "
                "based_on_revision_id, schema_id, schema_version, content_hash, created_at, "
                "created_by, change_reason, request_id, trace_id, table_id, table_revision_id, "
                "name, external_key, description, folder_id, folder_revision_id) VALUES "
                "(:id, :aggregate, :org, :project, 'internal', 1, NULL, "
                "'urn:cmp:catalog:record:1.0.0', '1.0.0', :hash, :now, :actor, "
                "'10,000-record bounded query fixture', :request, 't50-performance', :table, "
                ":table_revision, :name, :key, NULL, NULL, NULL)"
            ),
            revisions,
        )

    page = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(table.id, text="Synthetic Material", limit=100),
    )
    assert page.total_count == 10_000
    assert len(page.items) == 100
    exact = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(table.id, text="Synthetic Material 09999", limit=10),
    )
    assert exact.total_count == 1
    assert exact.items[0].current.content.external_key == "synthetic-09999"
