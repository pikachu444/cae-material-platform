from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.artifacts.adapters.persistence.content import SqlAlchemyArtifactRepository
from cmp.modules.artifacts.adapters.storage.filesystem import FilesystemMultipartObjectStore
from cmp.modules.artifacts.application.content import ArtifactService, ArtifactTransferCodec
from cmp.modules.catalog.adapters.api.configurable import install_configurable_catalog_api
from cmp.modules.catalog.adapters.api.records import install_catalog_record_api
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
    PublishRevision,
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
    RECORD_AGGREGATE_TYPE,
    CatalogRecordService,
    CreateFolder,
    CreateRecord,
    RegistrationSourceEvidence,
    ReviseFolder,
    ReviseRecord,
)
from cmp.modules.catalog.application.service import (
    CatalogService,
    CreateMaterial,
    CreateMaterialState,
)
from cmp.modules.catalog.domain.configurable import (
    AttributeDataType,
    AttributeDefinitionContent,
    CatalogDataCategory,
    CatalogTableContent,
    ConfigurableCatalogConflict,
)
from cmp.modules.catalog.domain.links import LinkCardinality, LinkTypeContent, RecordLinkContent
from cmp.modules.catalog.domain.model import MaterialClass, MaterialContent, MaterialStateContent
from cmp.modules.catalog.domain.records import (
    CatalogFolderContent,
    CatalogRecordContent,
    CatalogRecordQuery,
    CatalogRecordValue,
    DiscreteFilter,
    NumberRangeFilter,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1,
    CurvePoint,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
    processed_parquet_bytes,
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
from fastapi import FastAPI, Request
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
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
    artifacts: ArtifactService


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
def postgres(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Harness]:
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
                f'GRANT USAGE ON SCHEMA artifact, catalog, governance, access_control, '
                f'revisioning, datasets, modeling, exporting, processing, statistics, '
                f'testing TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA catalog "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT ON ALL TABLES IN SCHEMA governance, datasets, modeling, "
                "exporting, processing, statistics, testing "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA artifact TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA artifact, catalog, "
                "access_control, revisioning "
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
        artifacts = ArtifactService(
            repository=SqlAlchemyArtifactRepository(
                session_factory=sessions,
                rls_context=rls,
            ),
            object_store=FilesystemMultipartObjectStore(
                Path(tmp_path_factory.mktemp("t50-curve-artifacts"))
            ),
            transfers=ArtifactTransferCodec(
                b"t50-curve-transfer-secret-32-bytes-minimum",
                clock=lambda: NOW,
            ),
            clock=lambda: NOW,
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
            artifacts=artifacts,
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


def _context(
    *,
    organization_id: UUID = ORG,
    project_id: UUID = PROJECT,
) -> SecurityContext:
    request_id = uuid4()
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog User", True),
        organization_id=organization_id,
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


def _decision(
    context: SecurityContext,
    permission: Permission,
    *,
    max_classification: DataClassification = DataClassification.INTERNAL,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=max_classification,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _curve_api(
    postgres: Harness,
    context: SecurityContext,
    *,
    max_classification: DataClassification = DataClassification.INTERNAL,
) -> FastAPI:
    application = FastAPI()

    async def security(request: Request) -> SecurityContext:
        request.state.security_context = context
        return context

    async def read(request: Request) -> AuthorizationDecision:
        decision = _decision(
            context,
            Permission.CATALOG_READ,
            max_classification=max_classification,
        )
        request.state.authorization_decision = decision
        return decision

    async def write(request: Request) -> AuthorizationDecision:
        decision = _decision(
            context,
            Permission.CATALOG_WRITE,
            max_classification=max_classification,
        )
        request.state.authorization_decision = decision
        return decision

    install_configurable_catalog_api(
        application,
        service=None,
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
        schema_configuration_dependency=security,
    )
    install_catalog_record_api(
        application,
        service=postgres.records,
        artifact_service=postgres.artifacts,
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return application


async def _api_request(
    application: FastAPI,
    method: str,
    path: str,
    **kwargs: Any,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://test",
    ) as client:
        return await client.request(method, path, **kwargs)


def test_curve_artifact_revision_round_trip_legacy_compatibility_and_rls(
    postgres: Harness,
) -> None:
    async def exercise() -> None:
        context = _context()
        artifact_write = _decision(
            context,
            Permission.ARTIFACT_WRITE,
            max_classification=DataClassification.CONFIDENTIAL,
        )
        catalog_write = _decision(
            context,
            Permission.CATALOG_WRITE,
            max_classification=DataClassification.CONFIDENTIAL,
        )
        points = (
            CurvePoint(0.0, 0.0),
            CurvePoint(0.01, 100_000_000.0),
            CurvePoint(0.02, 125_000_000.0),
        )
        mapping = ReferenceTensileMapping("strain_pct", "stress_mpa", "%", "MPa")
        legacy_bytes = processed_parquet_bytes(
            points,
            mapping,
            schema_ref=REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1,
        )
        declared_bytes = normalized_parquet_bytes(points, mapping)
        legacy_artifact = await postgres.artifacts.finalize_derived_bytes(
            context,
            artifact_write,
            classification=DataClassification.CONFIDENTIAL,
            artifact_role="catalog.curve.synthetic-legacy",
            schema_ref=REFERENCE_TENSILE_PROCESSED_PARQUET_SCHEMA_V1,
            media_type="application/vnd.apache.parquet",
            value=legacy_bytes,
            idempotency_key="issue206:postgres:legacy",
        )
        declared_artifact = await postgres.artifacts.finalize_derived_bytes(
            context,
            artifact_write,
            classification=DataClassification.CONFIDENTIAL,
            artifact_role="catalog.curve.synthetic-declared",
            schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=declared_bytes,
            idempotency_key="issue206:postgres:declared",
        )
        table = postgres.schemas.create_table(
            context,
            catalog_write,
            CreateTable(
                DataClassification.CONFIDENTIAL,
                CatalogTableContent("issue206_curves", "Issue 206 synthetic curves"),
                "create issue 206 curve table",
            ),
        )
        curve_attribute = postgres.schemas.create_attribute(
            context,
            catalog_write,
            CreateAttribute(
                AttributeDefinitionContent(
                    table.id,
                    table.current.record.revision_id,
                    "observed_curve",
                    "Observed curve",
                    AttributeDataType.CURVE,
                    required=True,
                ),
                "add exact curve pointer",
            ),
        )
        application = _curve_api(
            postgres,
            context,
            max_classification=DataClassification.CONFIDENTIAL,
        )

        def body(artifact_id: UUID, sha256: str) -> dict[str, object]:
            return {
                "content": {
                    "table_revision_id": str(table.current.record.revision_id),
                    "name": "Synthetic legacy-to-declared curve",
                    "external_key": "issue206-curve",
                    "description": "Synthetic non-production PostgreSQL fixture",
                    "values": [
                        {
                            "data_type": "curve",
                            "attribute_definition_id": str(curve_attribute.id),
                            "attribute_definition_revision_id": str(
                                curve_attribute.current.record.revision_id
                            ),
                            "artifact_id": str(artifact_id),
                            "artifact_sha256": sha256,
                        }
                    ],
                },
                "change_reason": "exercise exact immutable curve revision",
            }

        created_body = body(
            legacy_artifact.artifact.id,
            legacy_artifact.artifact.sha256,
        )
        created_body["classification"] = "confidential"
        created = await _api_request(
            application,
            "POST",
            f"/api/v1/catalog/tables/{table.id}/records",
            json=created_body,
        )
        assert created.status_code == 201, created.text
        record_id = UUID(created.json()["record_id"])
        legacy_revision_id = UUID(created.json()["current_revision"]["id"])

        revised = await _api_request(
            application,
            "POST",
            f"/api/v1/catalog/records/{record_id}/revisions",
            headers={"If-Match": created.headers["etag"]},
            json=body(
                declared_artifact.artifact.id,
                declared_artifact.artifact.sha256,
            ),
        )
        assert revised.status_code == 201, revised.text
        declared_revision_id = UUID(revised.json()["current_revision"]["id"])
        preview_path = (
            f"/api/v1/catalog/records/{record_id}/revisions/"
            f"{{revision_id}}/curve-values/{curve_attribute.id}/preview?maximum_points=2"
        )

        canonical_artifact = await postgres.artifacts.finalize_derived_bytes(
            context,
            artifact_write,
            classification=DataClassification.CONFIDENTIAL,
            artifact_role="test-data.canonical-json.synthetic",
            schema_ref="urn:cmp:test-data:canonical-json:1.0.0",
            media_type="application/json",
            value=b'{"synthetic":true}',
            idempotency_key="issue206:postgres:canonical-owner",
        )
        document_id = uuid4()
        document_revision_id = uuid4()
        with postgres.admin_engine.begin() as connection:
            connection.execute(sa.text("SET CONSTRAINTS ALL DEFERRED"))
            connection.execute(
                sa.text(
                    "INSERT INTO datasets.test_data_document "
                    "(id, organization_id, project_id, classification, document_key, "
                    "current_revision_id, created_at, created_by, updated_at) VALUES "
                    "(:id, :organization_id, :project_id, 'confidential', :document_key, "
                    ":revision_id, :now, :actor, :now)"
                ),
                {
                    "id": document_id,
                    "organization_id": ORG,
                    "project_id": PROJECT,
                    "document_key": f"issue206-{document_id}",
                    "revision_id": document_revision_id,
                    "now": NOW,
                    "actor": ACTOR,
                },
            )
            connection.execute(
                sa.text(
                    "INSERT INTO datasets.test_data_document_revision "
                    "(id, aggregate_id, organization_id, project_id, classification, "
                    "revision_no, based_on_revision_id, schema_id, schema_version, "
                    "content_hash, created_at, created_by, change_reason, request_id, "
                    "trace_id, document_key, maker, grade, lot_batch, test_date, "
                    "operator_name, laboratory, test_method, equipment_maker, "
                    "equipment_model, specimen_key, specimen_description, source_file_name, "
                    "source_media_type, source_sha256, canonical_artifact_id, "
                    "canonical_sha256, normalized_artifact_id, normalized_sha256, "
                    "point_count, governed_source) VALUES "
                    "(:revision_id, :id, :organization_id, :project_id, 'confidential', "
                    "1, NULL, 'urn:cmp:test-data:document:1.0.0', '1.0.0', :content_hash, "
                    ":now, :actor, 'Create synthetic exact owner', :request_id, :trace_id, "
                    ":document_key, 'CMP Synthetic', 'Issue 206', NULL, '2026-07-18', "
                    "'Test operator', 'Test laboratory', 'synthetic tension', NULL, NULL, "
                    "'S-1', NULL, 'issue206.json', 'application/json', :source_sha256, "
                    ":canonical_artifact_id, :canonical_sha256, :normalized_artifact_id, "
                    ":normalized_sha256, 3, NULL)"
                ),
                {
                    "revision_id": document_revision_id,
                    "id": document_id,
                    "organization_id": ORG,
                    "project_id": PROJECT,
                    "content_hash": "c" * 64,
                    "now": NOW,
                    "actor": ACTOR,
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                    "document_key": f"issue206-{document_id}",
                    "source_sha256": "d" * 64,
                    "canonical_artifact_id": canonical_artifact.artifact.id,
                    "canonical_sha256": canonical_artifact.artifact.sha256,
                    "normalized_artifact_id": declared_artifact.artifact.id,
                    "normalized_sha256": declared_artifact.artifact.sha256,
                },
            )
        source_record = postgres.records.create_record(
            context,
            catalog_write,
            CreateRecord(
                DataClassification.CONFIDENTIAL,
                CatalogRecordContent(
                    table.id,
                    table.current.record.revision_id,
                    "Exact Test Data source",
                    external_key=f"issue206-source-{document_id}",
                    values=(
                        CatalogRecordValue(
                            curve_attribute.id,
                            curve_attribute.current.record.revision_id,
                            AttributeDataType.CURVE,
                            artifact_id=declared_artifact.artifact.id,
                            artifact_sha256=declared_artifact.artifact.sha256,
                        ),
                    ),
                ),
                "Create a separate exact Test Data Catalog source",
            ),
        )
        source_binding = postgres.links.bind_domain_revision(
            context,
            catalog_write,
            source_record.id,
            source_record.current.record.revision_id,
            BindDomainRevision(
                DomainBindingKind.TEST_DATA,
                document_id,
                document_revision_id,
            ),
        )

        with postgres.admin_engine.connect() as connection:
            before = connection.execute(
                sa.text(
                    "SELECT "
                    "(SELECT count(*) FROM catalog.catalog_record_revision), "
                    "(SELECT count(*) FROM artifact.artifact), "
                    "(SELECT count(*) FROM provenance.entity), "
                    "(SELECT count(*) FROM provenance.revision)"
                )
            ).one()

        legacy_preview = await _api_request(
            application,
            "GET",
            preview_path.format(revision_id=legacy_revision_id),
        )
        assert legacy_preview.status_code == 200, legacy_preview.text
        legacy_payload = legacy_preview.json()
        assert legacy_payload["curve_metadata"]["metadata_state"] == "legacy_compatible"
        assert legacy_payload["curve_metadata"]["artifact"]["sha256"] == (
            legacy_artifact.artifact.sha256
        )
        assert legacy_payload["curve_metadata"]["provenance"] == []
        assert legacy_payload["modeling_use"] == "view_only"
        assert legacy_payload["modeling_source"] is None
        assert legacy_payload["curve_series"]["channels"][1]["values"] == [0.0, 125000000.0]

        declared_preview = await _api_request(
            application,
            "GET",
            preview_path.format(revision_id=declared_revision_id),
        )
        assert declared_preview.status_code == 200, declared_preview.text
        declared_payload = declared_preview.json()
        assert declared_payload["curve_metadata"]["metadata_state"] == "declared"
        assert declared_payload["curve_metadata"]["artifact"]["sha256"] == (
            declared_artifact.artifact.sha256
        )
        assert declared_payload["curve_metadata"]["owning_revision"] == {
            "entity_type": "test_data_document",
            "entity_id": str(document_id),
            "revision_id": str(document_revision_id),
        }
        assert declared_payload["modeling_use"] == "fit_input"
        assert declared_payload["modeling_source"] == {
            "binding_id": str(source_binding.id),
            "record_id": str(source_record.id),
            "record_revision_id": str(source_record.current.record.revision_id),
            "kind": "test_data",
            "object_id": str(document_id),
            "revision_id": str(document_revision_id),
            "workbench_path": source_binding.workbench_path,
        }
        assert declared_payload["curve_metadata"]["definition"]["channels"][0][
            "original_units"
        ] == [{"unit": "%", "scale_to_normalized": "0.01", "offset_to_normalized": "0"}]

        with postgres.admin_engine.connect() as connection:
            after = connection.execute(
                sa.text(
                    "SELECT "
                    "(SELECT count(*) FROM catalog.catalog_record_revision), "
                    "(SELECT count(*) FROM artifact.artifact), "
                    "(SELECT count(*) FROM provenance.entity), "
                    "(SELECT count(*) FROM provenance.revision)"
                )
            ).one()
            pinned = connection.execute(
                sa.text(
                    "SELECT artifact_id, artifact_sha256 FROM catalog.record_curve_value "
                    "WHERE record_revision_id IN (:legacy_revision_id, :declared_revision_id) "
                    "ORDER BY record_revision_id"
                ),
                {
                    "legacy_revision_id": legacy_revision_id,
                    "declared_revision_id": declared_revision_id,
                },
            ).all()
        assert before == after
        assert {row.artifact_id for row in pinned} == {
            legacy_artifact.artifact.id,
            declared_artifact.artifact.id,
        }

        denied_contexts = (
            (_context(organization_id=uuid4()), DataClassification.CONFIDENTIAL),
            (_context(project_id=uuid4()), DataClassification.CONFIDENTIAL),
            (_context(), DataClassification.INTERNAL),
        )
        for denied_context, maximum in denied_contexts:
            denied = await _api_request(
                _curve_api(
                    postgres,
                    denied_context,
                    max_classification=maximum,
                ),
                "GET",
                preview_path.format(revision_id=declared_revision_id),
            )
            assert denied.status_code == 404, denied.text

    asyncio.run(exercise())


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
    provider = postgres.schemas.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "provider",
                "Provider",
                AttributeDataType.TEXT,
            ),
            "add provider",
        ),
    )
    evidence_source = postgres.schemas.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "evidence_source",
                "Evidence source",
                AttributeDataType.TEXT,
            ),
            "add evidence source",
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

    def content(
        name: str,
        e_pa: str,
        category: str,
        manufacturer: str,
        provider_name: str = "CMP Demo Provider",
        source_name: str = "Synthetic tensile reference",
    ) -> CatalogRecordContent:
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
                    # The service must derive this from the original value and unit.
                    normalized_value=Decimal("0"),
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
                CatalogRecordValue(
                    provider.id,
                    provider.current.record.revision_id,
                    AttributeDataType.TEXT,
                    value=provider_name,
                ),
                CatalogRecordValue(
                    evidence_source.id,
                    evidence_source.current.record.revision_id,
                    AttributeDataType.TEXT,
                    value=source_name,
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
            content(
                "AA6061-T6",
                "69000000000",
                "Aluminum",
                "Reference Metals",
                "Reference Provider",
                "Reference dataset",
            ),
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
            facet_attribute_ids=(family.id, provider.id, evidence_source.id),
        ),
    )
    assert result.total_count == 1
    assert result.items[0].id == steel.id
    family_facet = next(item for item in result.facets if item.attribute_definition_id == family.id)
    provider_facet = next(
        item for item in result.facets if item.attribute_definition_id == provider.id
    )
    source_facet = next(
        item for item in result.facets if item.attribute_definition_id == evidence_source.id
    )
    assert (family_facet.value, family_facet.count) == ("Steel", 1)
    assert (provider_facet.value, provider_facet.count) == ("CMP Demo Provider", 1)
    assert (source_facet.value, source_facet.count) == ("Synthetic tensile reference", 1)

    scoped = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(
            table.id,
            discrete_filters=(
                DiscreteFilter(provider.id, ("CMP Demo Provider",)),
                DiscreteFilter(evidence_source.id, ("Synthetic tensile reference",)),
            ),
            facet_attribute_ids=(provider.id, evidence_source.id),
        ),
    )
    assert scoped.total_count == 1
    assert [item.id for item in scoped.items] == [steel.id]
    assert {(item.value, item.count) for item in scoped.facets} == {
        ("CMP Demo Provider", 1),
        ("Synthetic tensile reference", 1),
    }

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
        assert version == "20261006_105_dma_tts"
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
            CatalogTableContent(
                "workflow_materials",
                "Workflow Materials",
                data_category=CatalogDataCategory.TECHNICAL_DATA,
            ),
            "create workflow material table",
        ),
    )
    test_table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent(
                "workflow_tests",
                "Workflow Tests",
                data_category=CatalogDataCategory.TEST_DATA,
            ),
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
    governed_state = postgres.catalog.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                governed_material.id,
                governed_material.current.record.revision_id,
                "As received",
            ),
            "create governed Material State for multi-binding graph readback",
        ),
    )
    state_binding = postgres.links.bind_domain_revision(
        context,
        write,
        material.id,
        material.current.record.revision_id,
        BindDomainRevision(
            DomainBindingKind.MATERIAL_STATE,
            governed_state.id,
            governed_state.current.record.revision_id,
        ),
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
    assert graph.root.data_category is CatalogDataCategory.TECHNICAL_DATA
    assert next(node for node in graph.nodes if node.record_id == tensile.id).data_category is (
        CatalogDataCategory.TEST_DATA
    )
    assert graph.root.domain_binding == binding
    assert graph.root.domain_bindings == tuple(
        sorted((binding, state_binding), key=lambda item: (item.kind.value, str(item.id)))
    )
    assert postgres.links.get_domain_binding(
        context, read, material.id, material.current.record.revision_id
    ) == graph.root.domain_binding
    assert postgres.links.list_domain_bindings(
        context, read, material.id, material.current.record.revision_id
    ) == graph.root.domain_bindings
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


def test_registration_preview_maps_original_columns_units_and_publishes_atomically(
    postgres: Harness,
) -> None:
    context = _context()
    write = _decision(context, Permission.CATALOG_WRITE)
    read = _decision(context, Permission.CATALOG_READ)
    table = postgres.schemas.create_table(
        context,
        write,
        CreateTable(
            DataClassification.INTERNAL,
            CatalogTableContent("registration_materials", "Registration Materials"),
            "create registration table",
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
            "add required modulus",
        ),
    )
    material_code = postgres.schemas.create_attribute(
        context,
        write,
        CreateAttribute(
            AttributeDefinitionContent(
                table.id,
                table.current.record.revision_id,
                "material_code",
                "Material code",
                AttributeDataType.TEXT,
                required=True,
            ),
            "add required material code",
        ),
    )
    source = RegistrationSourceEvidence(
        uuid4(),
        "a" * 64,
        "csv",
        encoding="utf-8",
        delimiter=";",
        decimal_separator=",",
    )
    mapping = {
        "Material name": "name",
        "Record code": "code",
        "Source material": "existing_material_code",
        "Source state": "existing_state_name",
        "Elastic modulus": {"attribute": "youngs_modulus", "unit": "GPa"},
    }
    material = postgres.catalog.create_material(
        context,
        write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("Registration source material", "REG-SOURCE", "steel"),
            "create material for exact registration binding",
        ),
    )
    state = postgres.catalog.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "As received",
            ),
            "create state for exact registration binding",
        ),
    )
    second_material = postgres.catalog.create_material(
        context,
        write,
        CreateMaterial(
            DataClassification.INTERNAL,
            MaterialContent("Second registration source", "REG-SOURCE-2", "steel"),
            "create second material for row binding",
        ),
    )
    second_state = postgres.catalog.create_material_state(
        context,
        write,
        CreateMaterialState(
            MaterialStateContent(
                second_material.id,
                second_material.current.record.revision_id,
                "Annealed",
            ),
            "create second state for row binding",
        ),
    )
    rejected = postgres.records.preview_registration(
        context,
        write,
        table_id=table.id,
        table_revision_id=table.current.record.revision_id,
        rows=(
            {
                "Material name": "Steel A",
                "Record code": "A",
                "Source material": "REG-SOURCE",
                "Source state": "As received",
                "Elastic modulus": "210,5",
            },
            {
                "Material name": "Steel B",
                "Record code": "a",
                "Source material": "REG-SOURCE-2",
                "Source state": "Annealed",
                "Elastic modulus": "205,0",
            },
        ),
        mapping=mapping,
        source=source,
    )
    assert not rejected.valid
    assert [(error.row, error.column) for error in rejected.errors] == [(2, "Record code")]
    with postgres.admin_engine.connect() as connection:
        assert (
            connection.scalar(
                sa.text(
                    "SELECT count(*) FROM catalog.catalog_record "
                    "WHERE organization_id = :organization_id AND project_id = :project_id "
                    "AND table_id = :table_id"
                ),
                {"organization_id": ORG, "project_id": PROJECT, "table_id": table.id},
            )
            == 0
        )

    checked = postgres.records.preview_registration(
        context,
        write,
        table_id=table.id,
        table_revision_id=table.current.record.revision_id,
        rows=(
            {
                "Material name": "Steel A",
                "Record code": "A",
                "Source material": "REG-SOURCE",
                "Source state": "As received",
                "Elastic modulus": "210,5",
            },
            {
                "Material name": "Steel B",
                "Record code": "B",
                "Source material": "REG-SOURCE-2",
                "Source state": "Annealed",
                "Elastic modulus": "205,0",
            },
        ),
        mapping=mapping,
        source=source,
    )
    assert checked.valid
    assert [row["material_state"] for row in checked.rows] == ["As received", "Annealed"]
    published = postgres.records.publish_registration(
        context,
        write,
        token=checked.token,
        table_id=table.id,
        table_revision_id=table.current.record.revision_id,
        change_reason="register checked material property rows",
    )
    assert [record.current.content.name for record in published.records] == ["Steel A", "Steel B"]
    values = [
        next(
            value
            for value in record.current.content.values
            if value.attribute_definition_id == modulus.id
        )
        for record in published.records
    ]
    assert [value.original_unit_string for value in values] == ["GPa", "GPa"]
    assert [value.normalized_value for value in values] == [
        Decimal("210500000000.0"),
        Decimal("205000000000.0"),
    ]
    material_codes = [
        next(
            value.value
            for value in record.current.content.values
            if value.attribute_definition_id == material_code.id
        )
        for record in published.records
    ]
    assert material_codes == ["REG-SOURCE", "REG-SOURCE-2"]
    assert (
        postgres.records.search_records(
            context,
            read,
            CatalogRecordQuery(table.id, published_only=True),
        ).total_count
        == 0
    )
    for record in published.records:
        validation = postgres.schemas.validate_publication(
            context,
            write,
            PublishRevision(
                RECORD_AGGREGATE_TYPE,
                record.id,
                record.current.record.revision_id,
            ),
        )
        assert validation.valid
        postgres.schemas.publish_revision(
            context,
            write,
            PublishRevision(
                RECORD_AGGREGATE_TYPE,
                record.id,
                record.current.record.revision_id,
            ),
        )
    searchable = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(table.id, published_only=True),
    )
    assert searchable.total_count == 2
    assert {record.id for record in searchable.items} == {record.id for record in published.records}
    first = published.records[0]
    draft_content = first.current.content
    postgres.records.revise_record(
        context,
        write,
        first.id,
        ReviseRecord(
            first.current.record.revision_id,
            CatalogRecordContent(
                draft_content.table_id,
                draft_content.table_revision_id,
                "Steel A draft",
                draft_content.external_key,
                draft_content.description,
                draft_content.folder_id,
                draft_content.folder_revision_id,
                draft_content.values,
            ),
            "create a later unpublished draft",
        ),
    )
    after_draft = postgres.records.search_records(
        context,
        read,
        CatalogRecordQuery(table.id, published_only=True),
    )
    published_first = next(record for record in after_draft.items if record.id == first.id)
    assert published_first.current.record.revision_id == first.current.record.revision_id
    assert published_first.current.content.name == "Steel A"
    with postgres.admin_engine.connect() as connection:
        evidence = (
            connection.execute(
                sa.text(
                    "SELECT source_artifact_id, source_digest, source_format, delimiter, "
                    "decimal_separator, unit_mapping_evidence, consumed_at "
                    "FROM catalog.record_registration_preview "
                    "WHERE token_digest = encode(sha256(convert_to(:token, 'UTF8')), 'hex')"
                ),
                {"token": checked.token},
            )
            .mappings()
            .one()
        )
    assert evidence["source_artifact_id"] == source.artifact_id
    assert evidence["source_digest"] == source.sha256
    assert evidence["source_format"] == "csv"
    assert evidence["delimiter"] == ";"
    assert evidence["decimal_separator"] == ","
    assert evidence["unit_mapping_evidence"] == [
        {
            "source_column": "Elastic modulus",
            "library_version": "cmp-registration-units/1",
            "source_unit": "GPa",
            "target_unit": "Pa",
            "factor": "1000000000",
            "offset": "0",
            "rule": "linear_scale",
        }
    ]
    assert evidence["consumed_at"] is not None
    conflicting = postgres.records.preview_registration(
        context,
        write,
        table_id=table.id,
        table_revision_id=table.current.record.revision_id,
        rows=(
            {
                "Material name": "Conflicting state row",
                "Material code": "C",
                "Source material": "REG-SOURCE",
                "Source state": "As received",
                "Elastic modulus": "200,0",
            },
        ),
        mapping=mapping,
        source=source,
    )
    assert not conflicting.valid
    assert [(error.row, error.column) for error in conflicting.errors] == [(1, "Source state")]
    assert "이미 데이터가 등록" in conflicting.errors[0].message
    with postgres.admin_engine.connect() as connection:
        assert (
            connection.scalar(
                sa.text("SELECT count(*) FROM catalog.catalog_record WHERE table_id = :table_id"),
                {"table_id": table.id},
            )
            == 2
        )
        assert (
            connection.scalar(
                sa.text(
                    "SELECT consumed_at FROM catalog.record_registration_preview "
                    "WHERE token_digest = encode(sha256(convert_to(:token, 'UTF8')), 'hex')"
                ),
                {"token": conflicting.token},
            )
            is None
        )
    with postgres.admin_engine.connect() as connection:
        bindings = (
            connection.execute(
                sa.text(
                    "SELECT record_id, domain_kind, domain_object_id, domain_revision_id "
                    "FROM catalog.domain_record_binding WHERE record_id = ANY(:record_ids)"
                ),
                {"record_ids": [record.id for record in published.records]},
            )
            .mappings()
            .all()
        )
    assert len(bindings) == 2
    assert {
        (row["record_id"], row["domain_kind"], row["domain_object_id"], row["domain_revision_id"])
        for row in bindings
    } == {
        (
            published.records[0].id,
            "material_state",
            state.id,
            state.current.record.revision_id,
        ),
        (
            published.records[1].id,
            "material_state",
            second_state.id,
            second_state.current.record.revision_id,
        ),
    }
    with pytest.raises(ConfigurableCatalogConflict, match="stale"):
        postgres.records.publish_registration(
            context,
            write,
            token=checked.token,
            table_id=table.id,
            table_revision_id=table.current.record.revision_id,
            change_reason="reject token replay",
        )


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
                # The search contract under test is cardinality, count, and bounded
                # page materialization. Keep one code for the exact-row assertion;
                # populating 10,000 unrelated codes exercises the separate
                # duplicate-code trigger quadratically and obscures this query gate.
                "key": f"synthetic-{index:05d}" if index == 9_999 else None,
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
