"""Cross-principal review visibility and separation-of-duties checks on cmp_app/RLS."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.domain.records import CatalogRecordQuery
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.review_release.adapters.persistence.evidence import SqlAlchemyReviewSubjectResolver
from cmp.modules.review_release.adapters.persistence.publication import (
    SqlAlchemyReviewApprovalProjector,
    catalog_publication_marker_table,
    domain_record_binding_table,
    review_publication_projection_table,
)
from cmp.modules.review_release.adapters.persistence.repository import (
    SqlAlchemyReviewRepository,
    lifecycle_event_table,
    lifecycle_projection_table,
    review_request_table,
)
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.review_release.domain.evidence import (
    ReviewEvidenceError,
    ReviewSubjectEvidenceRegistry,
    SourceArtifactState,
)
from cmp.modules.review_release.domain.lifecycle import (
    DecideReviewRequest,
    LifecycleState,
    ReviewDecisionKind,
    ReviewNotFound,
    SubmitReviewRequest,
)
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 8, 9, 8, 0, tzinfo=UTC)
ORG = UUID("76000000-0000-4000-8000-000000000001")
PROJECT = UUID("76000000-0000-4000-8000-000000000002")
AUTHOR = UUID("76000000-0000-4000-8000-000000000003")
REVIEWER = UUID("76000000-0000-4000-8000-000000000004")
OUTSIDER = UUID("76000000-0000-4000-8000-000000000005")
AGGREGATE = UUID("76000000-0000-4000-8000-000000000006")
REVISION = UUID("76000000-0000-4000-8000-000000000007")
EVENT = UUID("76000000-0000-4000-8000-000000000008")
REQUEST = UUID("76000000-0000-4000-8000-000000000009")
DECISION = UUID("76000000-0000-4000-8000-00000000000a")
SCHEMA_TABLE = UUID("76000000-0000-4000-8000-000000000010")
SCHEMA_TABLE_REVISION = UUID("76000000-0000-4000-8000-000000000011")
RECORD = UUID("76000000-0000-4000-8000-000000000012")
RECORD_REVISION = UUID("76000000-0000-4000-8000-000000000013")
BINDING = UUID("76000000-0000-4000-8000-000000000014")
NEXT_REVISION = UUID("76000000-0000-4000-8000-000000000015")
LEGACY_AGGREGATE = UUID("76000000-0000-4000-8000-000000000016")
LEGACY_REVISION = UUID("76000000-0000-4000-8000-000000000017")
LEGACY_EVENT = UUID("76000000-0000-4000-8000-000000000018")
LEGACY_REQUEST = UUID("76000000-0000-4000-8000-000000000019")
LEGACY_DECISION = UUID("76000000-0000-4000-8000-00000000001a")
LEGACY_REQUEST_CONTEXT = UUID("76000000-0000-4000-8000-00000000001b")
CONFIG_REQUEST = UUID("76000000-0000-4000-8000-00000000001c")
CONFIG_DECISION = UUID("76000000-0000-4000-8000-00000000001d")
CONFIG_NEXT_REVISION = UUID("76000000-0000-4000-8000-00000000001e")
CONFIG_NEXT_REQUEST = UUID("76000000-0000-4000-8000-00000000001f")
CONFIG_NEXT_DECISION = UUID("76000000-0000-4000-8000-000000000020")
CONFIG_NEXT_BINDING = UUID("76000000-0000-4000-8000-000000000021")
CONFIG_RECORD_EVENT = UUID("76000000-0000-4000-8000-000000000022")
CONFIG_NEXT_EVENT = UUID("76000000-0000-4000-8000-000000000023")
TEST_DOCUMENT = UUID("76000000-0000-4000-8000-000000000024")
TEST_DOCUMENT_REVISION = UUID("76000000-0000-4000-8000-000000000025")
TEST_BINDING = UUID("76000000-0000-4000-8000-000000000026")
TEST_CANONICAL_PENDING = UUID("76000000-0000-4000-8000-000000000027")
TEST_CANONICAL_ARTIFACT = UUID("76000000-0000-4000-8000-000000000028")
TEST_NORMALIZED_PENDING = UUID("76000000-0000-4000-8000-000000000029")
TEST_NORMALIZED_ARTIFACT = UUID("76000000-0000-4000-8000-00000000002a")
TEST_NO_BINDING_DOCUMENT = UUID("76000000-0000-4000-8000-00000000002b")
TEST_NO_BINDING_REVISION = UUID("76000000-0000-4000-8000-00000000002c")
TEST_DECISION = UUID("76000000-0000-4000-8000-00000000002d")
TEST_REQUEST_AUTH = UUID("76000000-0000-4000-8000-00000000002e")
TEST_EVENT = UUID("76000000-0000-4000-8000-00000000002f")
TEST_REQUEST = UUID("76000000-0000-4000-8000-000000000030")
TEST_GOVERNED_DOCUMENT = UUID("76000000-0000-4000-8000-000000000031")
TEST_GOVERNED_REVISION = UUID("76000000-0000-4000-8000-000000000032")
TEST_GOVERNED_EVENT = UUID("76000000-0000-4000-8000-000000000033")
TEST_GOVERNED_REQUEST = UUID("76000000-0000-4000-8000-000000000034")
TEST_GOVERNED_DECISION = UUID("76000000-0000-4000-8000-000000000035")
DIGEST = "e" * 64
RECORD_DIGEST = "b" * 64


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


def _context(principal_id: UUID, request_id: UUID) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Review integration user", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(principal_id),
        token_id=str(principal_id),
        groups=(),
        scopes=("openid",),
        request_id=request_id,
        trace_id=f"trace-{principal_id}",
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
    role: Role,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[tuple[Engine, Engine]]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_review_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
    database_url = admin_url.set(database=database_name)
    admin_engine = sa.create_engine(database_url, pool_pre_ping=True)
    app_engine: Engine | None = None
    try:
        command.upgrade(_alembic_config(database_url), "head")
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE ROLE cmp_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOBYPASSRLS"
            )
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA governance, revisioning, access_control, catalog, identity, "
                "datasets, modeling, exporting, processing, testing TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA governance, catalog "
                "TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT SELECT ON ALL TABLES IN SCHEMA datasets, modeling, exporting, "
                "processing, testing TO cmp_app"
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA revisioning, access_control TO cmp_app"
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO identity.principal
                      (id, principal_type, display_name, active, created_at, updated_at)
                    VALUES
                      (:author, 'user', 'Review author', true, :now, :now),
                      (:reviewer, 'user', 'Review domain reviewer', true, :now, :now),
                      (:outsider, 'user', 'Review outsider', true, :now, :now)
                    """
                ),
                {"author": AUTHOR, "reviewer": REVIEWER, "outsider": OUTSIDER, "now": NOW},
            )
            # Seed one exact Catalog Material revision and one exact Materials Record revision.
            # The binding is immutable evidence consumed by both the resolver and projector.
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.schema_table
                      (id, organization_id, project_id, classification, current_revision_id,
                       created_at, created_by, updated_at, table_key)
                    VALUES (:id, :org, :project, :classification, :revision,
                            :now, :author, :now, 'review_materials')
                    """
                ),
                {
                    "id": SCHEMA_TABLE,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "revision": SCHEMA_TABLE_REVISION,
                    "now": NOW,
                    "author": AUTHOR,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.schema_table_revision
                      (id, aggregate_id, organization_id, project_id, classification, revision_no,
                       based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                       created_by, change_reason, request_id, trace_id, table_key, name,
                       description)
                    VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
                            'urn:cmp:catalog:schema-table', '1.0.0', :digest, :now, :author,
                            'review fixture schema', :request_id, 'fixture-trace',
                            'review_materials', 'Review Materials', 'Review fixture table')
                    """
                ),
                {
                    "revision": SCHEMA_TABLE_REVISION,
                    "id": SCHEMA_TABLE,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "digest": "a" * 64,
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": REQUEST,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.catalog_record
                      (id, organization_id, project_id, classification, current_revision_id,
                       created_at, created_by, updated_at, table_id)
                    VALUES (:id, :org, :project, :classification, :revision,
                            :now, :author, :now, :table_id)
                    """
                ),
                {
                    "id": RECORD,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "revision": RECORD_REVISION,
                    "now": NOW,
                    "author": AUTHOR,
                    "table_id": SCHEMA_TABLE,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.catalog_record_revision
                      (id, aggregate_id, organization_id, project_id, classification, revision_no,
                       based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                       created_by, change_reason, request_id, trace_id, table_id,
                       table_revision_id, name, external_key, description)
                    VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
                            'urn:cmp:catalog:record', '1.0.0', :digest, :now, :author,
                            'review fixture Record', :request_id, 'fixture-trace',
                            :table_id, :table_revision_id, 'Review Material Record',
                            'review-material-record', 'Review fixture Record revision')
                    """
                ),
                {
                    "revision": RECORD_REVISION,
                    "id": RECORD,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "digest": "b" * 64,
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": REQUEST,
                    "table_id": SCHEMA_TABLE,
                    "table_revision_id": SCHEMA_TABLE_REVISION,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.material
                      (id, organization_id, project_id, classification, current_revision_id,
                       created_at, created_by, updated_at)
                    VALUES (:id, :org, :project, :classification, :revision,
                            :now, :author, :now)
                    """
                ),
                {
                    "id": AGGREGATE,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "revision": REVISION,
                    "now": NOW,
                    "author": AUTHOR,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.material_revision
                      (id, aggregate_id, organization_id, project_id, classification, revision_no,
                       based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                       created_by, change_reason, request_id, trace_id, name, material_code,
                       material_family, description)
                    VALUES (:revision, :id, :org, :project, :classification, 1, NULL,
                            'urn:cmp:catalog:material', '1.0.0', :digest, :now, :author,
                            'review fixture Material', :request_id, 'fixture-trace',
                            'Review Material', 'RM-160', 'synthetic',
                            'Review fixture Material revision')
                    """
                ),
                {
                    "revision": REVISION,
                    "id": AGGREGATE,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "digest": DIGEST,
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": REQUEST,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.domain_record_identity_binding
                      (organization_id, project_id, classification, domain_kind,
                       domain_object_id, domain_revision_id, record_id, created_at,
                       created_by, request_id, trace_id)
                    VALUES (:org, :project, :classification, 'material',
                            :domain_object_id, :domain_revision_id, :record_id,
                            :now, :author, :request_id, 'fixture-trace')
                    """
                ),
                {
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "domain_object_id": AGGREGATE,
                    "domain_revision_id": REVISION,
                    "record_id": RECORD,
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": REQUEST,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO catalog.domain_record_binding
                      (id, organization_id, project_id, classification, record_id,
                       record_revision_id, domain_kind, domain_object_id, domain_revision_id,
                       created_at, created_by, request_id, trace_id)
                    VALUES (:id, :org, :project, :classification, :record_id,
                            :record_revision_id, 'material', :domain_object_id,
                            :domain_revision_id, :now, :author, :request_id, 'fixture-trace')
                    """
                ),
                {
                    "id": BINDING,
                    "org": ORG,
                    "project": PROJECT,
                    "classification": DataClassification.INTERNAL.value,
                    "record_id": RECORD,
                    "record_revision_id": RECORD_REVISION,
                    "domain_object_id": AGGREGATE,
                    "domain_revision_id": REVISION,
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": REQUEST,
                },
            )
            connection.execute(
                sa.insert(lifecycle_event_table).values(
                    id=EVENT,
                    organization_id=ORG,
                    project_id=PROJECT,
                    classification=DataClassification.INTERNAL.value,
                    aggregate_type="catalog.material",
                    aggregate_id=AGGREGATE,
                    revision_id=REVISION,
                    sequence_no=1,
                    from_state=None,
                    to_state=LifecycleState.DRAFT.value,
                    occurred_at=NOW,
                    actor_id=AUTHOR,
                    reason="cross-principal review visibility fixture",
                    request_id=REQUEST,
                    trace_id="fixture-trace",
                )
            )
            connection.execute(
                sa.insert(lifecycle_projection_table).values(
                    organization_id=ORG,
                    project_id=PROJECT,
                    classification=DataClassification.INTERNAL.value,
                    aggregate_type="catalog.material",
                    aggregate_id=AGGREGATE,
                    revision_id=REVISION,
                    lifecycle_state=LifecycleState.DRAFT.value,
                    sequence_no=1,
                    last_event_id=EVENT,
                    updated_at=NOW,
                )
            )
            # Review requests for the configurable Materials Record use the same
            # immutable lifecycle projection as all other review subjects.  Keep
            # this fixture explicit so the cmp_app path exercises the production
            # request transition rather than a pre-seeded review row.
            connection.execute(
                sa.insert(lifecycle_event_table).values(
                    id=CONFIG_RECORD_EVENT,
                    organization_id=ORG,
                    project_id=PROJECT,
                    classification=DataClassification.INTERNAL.value,
                    aggregate_type="catalog.configurable_record",
                    aggregate_id=RECORD,
                    revision_id=RECORD_REVISION,
                    sequence_no=1,
                    from_state=None,
                    to_state=LifecycleState.DRAFT.value,
                    occurred_at=NOW,
                    actor_id=AUTHOR,
                    reason="configurable Record review fixture",
                    request_id=CONFIG_REQUEST,
                    trace_id="fixture-trace",
                )
            )
            connection.execute(
                sa.insert(lifecycle_projection_table).values(
                    organization_id=ORG,
                    project_id=PROJECT,
                    classification=DataClassification.INTERNAL.value,
                    aggregate_type="catalog.configurable_record",
                    aggregate_id=RECORD,
                    revision_id=RECORD_REVISION,
                    lifecycle_state=LifecycleState.DRAFT.value,
                    sequence_no=1,
                    last_event_id=CONFIG_RECORD_EVENT,
                    updated_at=NOW,
                )
            )
        app_engine = sa.create_engine(database_url.set(username="cmp_app", password=None))
        yield admin_engine, app_engine
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
            connection.exec_driver_sql("DROP ROLE IF EXISTS cmp_app")
        cluster_engine.dispose()


def test_cmp_app_cross_principal_review_history_and_sod(postgres: tuple[Engine, Engine]) -> None:
    admin_engine, app_engine = postgres
    sessions = sessionmaker(app_engine)
    rls_context = SqlAlchemyRlsContext()
    catalog_repository = SqlAlchemyCatalogRecordRepository(
        session_factory=sessions,
        rls_context=rls_context,
    )
    evidence_registry = ReviewSubjectEvidenceRegistry(
        (
            SqlAlchemyReviewSubjectResolver(
                subject_type="catalog.material",
                session_factory=sessions,
                rls_context=rls_context,
            ),
        )
    )
    repository = SqlAlchemyReviewRepository(
        session_factory=sessions,
        rls_context=rls_context,
        approval_projector=SqlAlchemyReviewApprovalProjector(),
    )
    service = ReviewService(
        repository=repository,
        id_factory=iter((REQUEST, DECISION)).__next__,
        clock=lambda: NOW,
        evidence_registry=evidence_registry,
    )
    author = _context(AUTHOR, UUID("76000000-0000-4000-8000-00000000000b"))
    reviewer = _context(REVIEWER, UUID("76000000-0000-4000-8000-00000000000c"))
    outsider = _context(OUTSIDER, UUID("76000000-0000-4000-8000-00000000000d"))
    author_request = _decision(author, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER)
    author_read = _decision(author, Permission.REVIEW_READ, Role.MATERIAL_MODELER)
    reviewer_read = _decision(reviewer, Permission.REVIEW_READ, Role.DOMAIN_REVIEWER)
    reviewer_catalog_read = _decision(reviewer, Permission.CATALOG_READ, Role.DOMAIN_REVIEWER)
    reviewer_decide = _decision(reviewer, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER)
    outsider_read = _decision(outsider, Permission.REVIEW_READ, Role.CAE_ANALYST)

    created = service.create_request(
        author,
        author_request,
        SubmitReviewRequest(
            classification=None,
            aggregate_type="catalog.material",
            aggregate_id=AGGREGATE,
            revision_id=REVISION,
            manifest_sha256=None,
            reason="cmp_app cross-principal pending request",
        ),
    )
    assert created.lifecycle_state is LifecycleState.REVIEW
    assert created.evidence is not None
    assert created.evidence.affected_record_id == RECORD
    assert created.evidence.affected_record_revision_id == RECORD_REVISION
    assert created.evidence.affected_table_id is not None
    assert created.evidence.affected_table_revision_id is not None
    assert created.evidence.server_manifest_sha256 == DIGEST
    assert created.requested_by_display_name == "Review integration user"
    with pytest.raises(ReviewEvidenceError, match="revision is not current"):
        evidence_registry.resolve(
            subject_type="catalog.material",
            organization_id=ORG,
            project_id=PROJECT,
            subject_id=AGGREGATE,
            subject_revision_id=UUID("76000000-0000-4000-8000-000000000099"),
            expected_manifest_sha256=None,
            expected_classification=None,
            requested_by=AUTHOR,
            reason="stale evidence probe",
            occurred_at=NOW,
            _context=author,
            _authorization_decision=author_request,
        )
    assert service.list_requests(reviewer, reviewer_read, limit=10)[0].id == REQUEST
    assert service.get_request(reviewer, reviewer_read, REQUEST).id == REQUEST
    assert service.list_requests(author, author_read, limit=10)[0].id == REQUEST
    with pytest.raises(ReviewNotFound):
        service.get_request(outsider, outsider_read, REQUEST)
    assert service.list_requests(outsider, outsider_read, limit=10) == ()

    approved = service.decide(
        reviewer,
        reviewer_decide,
        REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256=DIGEST,
            decision=ReviewDecisionKind.APPROVED,
            reason="cmp_app reviewer decision remains tenant history",
        ),
    )
    assert approved.lifecycle_state is LifecycleState.APPROVED
    assert approved.decision is not None
    assert approved.decision.decided_by == REVIEWER
    with sessions() as session, session.begin():
        rls_context.bind_authorization(session, reviewer, reviewer_decide)
        publication = (
            session.execute(
                sa.select(review_publication_projection_table).where(
                    review_publication_projection_table.c.review_request_id == REQUEST
                )
            )
            .mappings()
            .one()
        )
        marker = (
            session.execute(
                sa.select(catalog_publication_marker_table).where(
                    catalog_publication_marker_table.c.aggregate_id == RECORD,
                    catalog_publication_marker_table.c.revision_id == RECORD_REVISION,
                )
            )
            .mappings()
            .one()
        )
        binding = (
            session.execute(
                sa.select(domain_record_binding_table).where(
                    domain_record_binding_table.c.domain_object_id == AGGREGATE,
                    domain_record_binding_table.c.domain_revision_id == REVISION,
                )
            )
            .mappings()
            .one()
        )
    assert publication["subject_type"] == "catalog.material"
    assert publication["subject_id"] == AGGREGATE
    assert publication["subject_revision_id"] == REVISION
    assert publication["record_id"] == RECORD
    assert publication["record_revision_id"] == RECORD_REVISION
    assert marker["aggregate_type"] == "catalog.configurable_record"
    assert marker["aggregate_id"] == RECORD
    assert marker["revision_id"] == RECORD_REVISION
    assert binding["record_id"] == RECORD
    assert binding["record_revision_id"] == RECORD_REVISION
    published_before = catalog_repository.search_records(
        context=reviewer,
        decision=reviewer_catalog_read,
        query=CatalogRecordQuery(
            table_id=SCHEMA_TABLE,
            record_id=RECORD,
            published_only=True,
        ),
    )
    assert published_before.total_count == 1
    assert published_before.items[0].current.record.revision_id == RECORD_REVISION

    # A new immutable upstream Material head invalidates the governed publication read model.
    # The old review projection, marker, and raw Material revision remain append-only history.
    with admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog.material_revision
                  (id, aggregate_id, organization_id, project_id, classification, revision_no,
                   based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                   created_by, change_reason, request_id, trace_id, name, material_code,
                   material_family, description)
                VALUES (:revision, :id, :org, :project, :classification, 2, :based_on,
                        'urn:cmp:catalog:material', '1.0.0', :digest, :now, :author,
                        'upstream revision invalidates governed publication', :request_id,
                        'fixture-trace', 'Review Material v2', 'RM-160-V2', 'synthetic',
                        'New immutable upstream revision')
                """
            ),
            {
                "revision": NEXT_REVISION,
                "id": AGGREGATE,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "based_on": REVISION,
                "digest": "f" * 64,
                "now": NOW,
                "author": AUTHOR,
                "request_id": REQUEST,
            },
        )
        connection.execute(
            sa.text(
                """
                UPDATE catalog.material
                   SET current_revision_id = :revision, updated_at = :now
                 WHERE organization_id = :org AND project_id = :project AND id = :id
                """
            ),
            {
                "revision": NEXT_REVISION,
                "now": NOW,
                "org": ORG,
                "project": PROJECT,
                "id": AGGREGATE,
            },
        )
    published_after = catalog_repository.search_records(
        context=reviewer,
        decision=reviewer_decide,
        query=CatalogRecordQuery(
            table_id=SCHEMA_TABLE,
            record_id=RECORD,
            published_only=True,
        ),
    )
    assert published_after.total_count == 0
    assert service.get_request(author, author_read, REQUEST).evidence is not None
    assert (
        service.list_requests(reviewer, reviewer_read, limit=10)[0].lifecycle_state
        is LifecycleState.APPROVED
    )
    assert service.get_request(author, author_read, REQUEST).decision is not None
    with pytest.raises(ReviewNotFound):
        service.get_request(outsider, outsider_read, REQUEST)


def test_legacy_validation_result_approval_skips_issue160_projection(
    postgres: tuple[Engine, Engine],
) -> None:
    """The pre-#160 validation-result lifecycle remains approvable without evidence."""

    admin_engine, app_engine = postgres
    with admin_engine.begin() as connection:
        connection.execute(
            sa.insert(lifecycle_event_table).values(
                id=LEGACY_EVENT,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="validation.result",
                aggregate_id=LEGACY_AGGREGATE,
                revision_id=LEGACY_REVISION,
                sequence_no=1,
                from_state=None,
                to_state=LifecycleState.REVIEW.value,
                occurred_at=NOW,
                actor_id=AUTHOR,
                reason="legacy validation result review fixture",
                request_id=LEGACY_REQUEST_CONTEXT,
                trace_id="legacy-fixture-trace",
            )
        )
        connection.execute(
            sa.insert(lifecycle_projection_table).values(
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="validation.result",
                aggregate_id=LEGACY_AGGREGATE,
                revision_id=LEGACY_REVISION,
                lifecycle_state=LifecycleState.REVIEW.value,
                sequence_no=1,
                last_event_id=LEGACY_EVENT,
                updated_at=NOW,
            )
        )
        connection.execute(
            # Keep the fixture at the SQL boundary: this row predates typed #160
            # evidence and therefore has a NULL subject_evidence snapshot.
            sa.insert(review_request_table).values(
                id=LEGACY_REQUEST,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="validation.result",
                aggregate_id=LEGACY_AGGREGATE,
                revision_id=LEGACY_REVISION,
                manifest_sha256=DIGEST,
                required_role="domain_reviewer",
                requested_by=AUTHOR,
                requested_by_display_name="Legacy validation requester",
                requested_at=NOW,
                reason="legacy validation result review fixture",
                subject_evidence=None,
                request_id=LEGACY_REQUEST_CONTEXT,
                trace_id="legacy-fixture-trace",
            )
        )

    sessions = sessionmaker(app_engine)
    repository = SqlAlchemyReviewRepository(
        session_factory=sessions,
        rls_context=SqlAlchemyRlsContext(),
        approval_projector=SqlAlchemyReviewApprovalProjector(),
    )
    reviewer = _context(REVIEWER, UUID("76000000-0000-4000-8000-00000000001c"))
    reviewer_decide = _decision(reviewer, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER)
    service = ReviewService(
        repository=repository,
        id_factory=iter((LEGACY_DECISION,)).__next__,
        clock=lambda: NOW,
    )

    approved = service.decide(
        reviewer,
        reviewer_decide,
        LEGACY_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256=DIGEST,
            decision=ReviewDecisionKind.APPROVED,
            reason="Preserve the legacy validation result approval lifecycle",
        ),
    )

    assert approved.lifecycle_state is LifecycleState.APPROVED
    assert approved.evidence is None
    with sessions() as session, session.begin():
        rls_context = SqlAlchemyRlsContext()
        rls_context.bind_authorization(session, reviewer, reviewer_decide)
        projection = session.execute(
            sa.select(review_publication_projection_table).where(
                review_publication_projection_table.c.review_request_id == LEGACY_REQUEST
            )
        ).first()
    assert projection is None


def test_cmp_app_configurable_record_review_resubmits_after_record_head_advance(
    postgres: tuple[Engine, Engine],
) -> None:
    """A Record subject uses its exact current revision and re-publishes after a new head."""

    admin_engine, app_engine = postgres
    sessions = sessionmaker(app_engine)
    rls_context = SqlAlchemyRlsContext()
    evidence_registry = ReviewSubjectEvidenceRegistry(
        (
            SqlAlchemyReviewSubjectResolver(
                subject_type="catalog.configurable_record",
                session_factory=sessions,
                rls_context=rls_context,
            ),
        )
    )
    repository = SqlAlchemyReviewRepository(
        session_factory=sessions,
        rls_context=rls_context,
        approval_projector=SqlAlchemyReviewApprovalProjector(),
    )
    author = _context(AUTHOR, UUID("76000000-0000-4000-8000-000000000022"))
    reviewer = _context(REVIEWER, UUID("76000000-0000-4000-8000-000000000023"))
    author_request = _decision(author, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER)
    reviewer_catalog_read = _decision(reviewer, Permission.CATALOG_READ, Role.DOMAIN_REVIEWER)
    reviewer_decide = _decision(reviewer, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER)
    service = ReviewService(
        repository=repository,
        id_factory=iter(
            (CONFIG_REQUEST, CONFIG_DECISION, CONFIG_NEXT_REQUEST, CONFIG_NEXT_DECISION)
        ).__next__,
        clock=lambda: NOW,
        evidence_registry=evidence_registry,
    )

    created = service.create_request(
        author,
        author_request,
        SubmitReviewRequest(
            classification=DataClassification.INTERNAL,
            aggregate_type="catalog.configurable_record",
            aggregate_id=RECORD,
            revision_id=RECORD_REVISION,
            manifest_sha256=RECORD_DIGEST,
            reason="review exact configurable Record revision",
        ),
    )
    assert created.evidence is not None
    assert created.evidence.affected_record_id == RECORD
    assert created.evidence.affected_record_revision_id == RECORD_REVISION
    assert created.evidence.server_manifest_sha256 == RECORD_DIGEST

    approved = service.decide(
        reviewer,
        reviewer_decide,
        CONFIG_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256=RECORD_DIGEST,
            decision=ReviewDecisionKind.APPROVED,
            reason="approve the exact Record revision",
        ),
    )
    assert approved.lifecycle_state is LifecycleState.APPROVED
    published = SqlAlchemyCatalogRecordRepository(
        session_factory=sessions,
        rls_context=rls_context,
    ).search_records(
        context=reviewer,
        decision=reviewer_catalog_read,
        query=CatalogRecordQuery(table_id=SCHEMA_TABLE, record_id=RECORD, published_only=True),
    )
    assert published.total_count == 1
    assert published.items[0].current.record.revision_id == RECORD_REVISION

    # Advance the immutable Record head.  The old approved projection remains
    # history but must no longer satisfy the current-head publication predicate.
    with admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog.catalog_record_revision (
                  id, aggregate_id, organization_id, project_id, classification, revision_no,
                  based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                  created_by, change_reason, request_id, trace_id, table_id, table_revision_id,
                  name, external_key, description, folder_id, folder_revision_id
                ) VALUES (
                  :revision, :record, :org, :project, :classification, 2, :based_on,
                  'urn:cmp:catalog:record', '1.0.0', :digest, :now, :author,
                  'advance exact Record head', :request_id, 'fixture-trace', :table_id,
                  :table_revision_id, 'Review Material Record v2', 'review-material-record-v2',
                  'second immutable Record revision', NULL, NULL
                )
                """
            ),
            {
                "revision": CONFIG_NEXT_REVISION,
                "record": RECORD,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "based_on": RECORD_REVISION,
                "digest": "c" * 64,
                "now": NOW,
                "author": AUTHOR,
                "request_id": CONFIG_NEXT_REQUEST,
                "table_id": SCHEMA_TABLE,
                "table_revision_id": SCHEMA_TABLE_REVISION,
            },
        )
        connection.execute(
            sa.text(
                "UPDATE catalog.catalog_record SET current_revision_id=:revision, updated_at=:now "
                "WHERE organization_id=:org AND project_id=:project AND id=:record"
            ),
            {
                "revision": CONFIG_NEXT_REVISION,
                "now": NOW,
                "org": ORG,
                "project": PROJECT,
                "record": RECORD,
            },
        )
        # Preserve the current Material as safe context for the new Record head.
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog.domain_record_binding (
                  id, organization_id, project_id, classification, record_id,
                  record_revision_id, domain_kind, domain_object_id, domain_revision_id,
                  created_at, created_by, request_id, trace_id
                ) VALUES (
                  :id, :org, :project, :classification, :record, :record_revision,
                  'material', :material, :material_revision, :now, :author, :request_id,
                  'fixture-trace'
                )
                """
            ),
            {
                "id": CONFIG_NEXT_BINDING,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "record": RECORD,
                "record_revision": CONFIG_NEXT_REVISION,
                "material": AGGREGATE,
                "material_revision": REVISION,
                "now": NOW,
                "author": AUTHOR,
                "request_id": CONFIG_NEXT_REQUEST,
            },
        )
        connection.execute(
            sa.insert(lifecycle_event_table).values(
                id=CONFIG_NEXT_EVENT,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="catalog.configurable_record",
                aggregate_id=RECORD,
                revision_id=CONFIG_NEXT_REVISION,
                sequence_no=1,
                from_state=None,
                to_state=LifecycleState.DRAFT.value,
                occurred_at=NOW,
                actor_id=AUTHOR,
                reason="configurable Record replacement review fixture",
                request_id=CONFIG_NEXT_REQUEST,
                trace_id="fixture-trace",
            )
        )
        connection.execute(
            sa.insert(lifecycle_projection_table).values(
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="catalog.configurable_record",
                aggregate_id=RECORD,
                revision_id=CONFIG_NEXT_REVISION,
                lifecycle_state=LifecycleState.DRAFT.value,
                sequence_no=1,
                last_event_id=CONFIG_NEXT_EVENT,
                updated_at=NOW,
            )
        )

    assert (
        SqlAlchemyCatalogRecordRepository(
            session_factory=sessions,
            rls_context=rls_context,
        )
        .search_records(
            context=reviewer,
            decision=reviewer_catalog_read,
            query=CatalogRecordQuery(table_id=SCHEMA_TABLE, record_id=RECORD, published_only=True),
        )
        .total_count
        == 0
    )
    with pytest.raises(ReviewEvidenceError, match="revision is not current"):
        service.create_request(
            author,
            author_request,
            SubmitReviewRequest(
                classification=DataClassification.INTERNAL,
                aggregate_type="catalog.configurable_record",
                aggregate_id=RECORD,
                revision_id=RECORD_REVISION,
                manifest_sha256=RECORD_DIGEST,
                reason="stale Record resubmit must fail",
            ),
        )

    created_next = service.create_request(
        author,
        author_request,
        SubmitReviewRequest(
            classification=DataClassification.INTERNAL,
            aggregate_type="catalog.configurable_record",
            aggregate_id=RECORD,
            revision_id=CONFIG_NEXT_REVISION,
            manifest_sha256="c" * 64,
            reason="resubmit the new exact Record revision",
        ),
    )
    assert created_next.evidence is not None
    assert created_next.evidence.affected_record_revision_id == CONFIG_NEXT_REVISION
    approved_next = service.decide(
        reviewer,
        reviewer_decide,
        CONFIG_NEXT_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256="c" * 64,
            decision=ReviewDecisionKind.APPROVED,
            reason="approve the replacement Record revision",
        ),
    )
    assert approved_next.lifecycle_state is LifecycleState.APPROVED
    published_next = SqlAlchemyCatalogRecordRepository(
        session_factory=sessions,
        rls_context=rls_context,
    ).search_records(
        context=reviewer,
        decision=reviewer_catalog_read,
        query=CatalogRecordQuery(table_id=SCHEMA_TABLE, record_id=RECORD, published_only=True),
    )
    assert published_next.total_count == 1
    assert published_next.items[0].current.record.revision_id == CONFIG_NEXT_REVISION


def test_cmp_app_test_data_document_review_requires_binding_digest_and_authorization(
    postgres: tuple[Engine, Engine],
) -> None:
    """Canonical Test Data review resolves source Artifacts and exact Record binding."""

    admin_engine, app_engine = postgres
    with admin_engine.begin() as connection:
        for pending_id, artifact_id, digest, role in (
            (TEST_CANONICAL_PENDING, TEST_CANONICAL_ARTIFACT, "1" * 64, "review.canonical"),
            (TEST_NORMALIZED_PENDING, TEST_NORMALIZED_ARTIFACT, "2" * 64, "review.normalized"),
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO artifact.artifact_pending (
                      organization_id, project_id, id, classification, state, artifact_kind,
                      artifact_role, schema_ref, media_type, expected_size_bytes, expected_sha256,
                      staging_object_key, final_object_key, encryption_profile, source_raw_asset_id,
                      idempotency_key, submission_digest, reserved_artifact_id,
                      available_artifact_id, attempt_count, failure_code, created_at, created_by,
                      request_id, trace_id, updated_at, terminal_at
                    ) VALUES (
                      :org, :project, :pending, :classification, 'pending', 'derived',
                      :role, 'urn:cmp:review:fixture', 'application/json', 2, :digest,
                      :staging,
                      artifact.content_object_key(
                        :org, :project, CAST(:key_classification AS text),
                        CAST(:key_digest AS text)
                      ),
                      'none', NULL, :idempotency, :digest, :artifact, NULL, 0, NULL,
                      :now, :author, :request_id, 'fixture-trace', :now, NULL
                    )
                    """
                ),
                {
                    "org": ORG,
                    "project": PROJECT,
                    "pending": pending_id,
                    "classification": DataClassification.INTERNAL.value,
                    "role": role,
                    "digest": digest,
                    "key_classification": DataClassification.INTERNAL.value,
                    "key_digest": digest,
                    "staging": f"staging/{pending_id}",
                    "artifact": artifact_id,
                    "idempotency": f"review:{pending_id}",
                    "now": NOW,
                    "author": AUTHOR,
                    "request_id": TEST_DOCUMENT_REVISION,
                },
            )
            connection.execute(
                sa.text(
                    """
                    UPDATE artifact.artifact_pending
                       SET state='promoting', attempt_count=1, updated_at=:now
                     WHERE organization_id=:org AND project_id=:project
                       AND id=:pending
                    """
                ),
                {"org": ORG, "project": PROJECT, "pending": pending_id, "now": NOW},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO artifact.artifact (
                      organization_id, project_id, id, classification, artifact_kind,
                      artifact_role, schema_ref, media_type, size_bytes, sha256, storage_key,
                      encryption_profile, source_raw_asset_id, source_pending_id, created_at,
                      created_by
                    ) VALUES (
                      :org, :project, :artifact, :classification, 'derived', :role,
                      'urn:cmp:review:fixture', 'application/json', 2, :digest,
                      artifact.content_object_key(
                        :org, :project, CAST(:key_classification AS text),
                        CAST(:key_digest AS text)
                      ),
                      'none', NULL, :pending, :now, :author
                    )
                    """
                ),
                {
                    "org": ORG,
                    "project": PROJECT,
                    "artifact": artifact_id,
                    "classification": DataClassification.INTERNAL.value,
                    "role": role,
                    "digest": digest,
                    "key_classification": DataClassification.INTERNAL.value,
                    "key_digest": digest,
                    "pending": pending_id,
                    "now": NOW,
                    "author": AUTHOR,
                },
            )
            connection.execute(
                sa.text(
                    """
                    UPDATE artifact.artifact_pending
                       SET state='available', available_artifact_id=:artifact,
                           updated_at=:now, terminal_at=:now
                     WHERE organization_id=:org AND project_id=:project
                       AND id=:pending
                    """
                ),
                {
                    "org": ORG,
                    "project": PROJECT,
                    "pending": pending_id,
                    "artifact": artifact_id,
                    "now": NOW,
                },
            )
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document (
                  id, organization_id, project_id, classification, document_key,
                  current_revision_id, created_at, created_by, updated_at
                ) VALUES (:id, :org, :project, :classification, 'REVIEW-DOC-160',
                          :revision, :now, :author, :now)
                """
            ),
            {
                "id": TEST_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "revision": TEST_DOCUMENT_REVISION,
                "now": NOW,
                "author": AUTHOR,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document_revision (
                  id, aggregate_id, organization_id, project_id, classification, revision_no,
                  based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                  created_by, change_reason, request_id, trace_id, document_key, maker, grade,
                  lot_batch, test_date, operator_name, laboratory, test_method, equipment_maker,
                  equipment_model, specimen_key, specimen_description, source_file_name,
                  source_media_type, source_sha256, canonical_artifact_id, canonical_sha256,
                  normalized_artifact_id, normalized_sha256, point_count
                ) VALUES (
                  :revision, :id, :org, :project, :classification, 1, NULL,
                  'urn:cmp:datasets:test-data-document', '1.0.0', :digest, :now, :author,
                  'review canonical Test Data fixture', :request_id, 'fixture-trace',
                  'REVIEW-DOC-160', 'CMP fixture lab', 'DP780', 'BATCH-160', '2026-08-09',
                  'Fixture operator', 'CMP Lab', 'CMP-TENSILE-REFERENCE', 'CMP', '160',
                  'SPEC-160', 'Synthetic review fixture', 'review-160.json', 'application/json',
                  :source_digest, :canonical_artifact, :canonical_digest,
                  :normalized_artifact, :normalized_digest, 2
                )
                """
            ),
            {
                "revision": TEST_DOCUMENT_REVISION,
                "id": TEST_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "digest": "3" * 64,
                "now": NOW,
                "author": AUTHOR,
                "request_id": TEST_DOCUMENT_REVISION,
                "source_digest": "4" * 64,
                "canonical_artifact": TEST_CANONICAL_ARTIFACT,
                "canonical_digest": "1" * 64,
                "normalized_artifact": TEST_NORMALIZED_ARTIFACT,
                "normalized_digest": "2" * 64,
            },
        )
        connection.execute(
            sa.insert(lifecycle_event_table).values(
                id=TEST_EVENT,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_DOCUMENT,
                revision_id=TEST_DOCUMENT_REVISION,
                sequence_no=1,
                from_state=None,
                to_state=LifecycleState.DRAFT.value,
                occurred_at=NOW,
                actor_id=AUTHOR,
                reason="canonical Test Data review fixture",
                request_id=TEST_REQUEST,
                trace_id="fixture-trace",
            )
        )
        connection.execute(
            sa.insert(lifecycle_projection_table).values(
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_DOCUMENT,
                revision_id=TEST_DOCUMENT_REVISION,
                lifecycle_state=LifecycleState.DRAFT.value,
                sequence_no=1,
                last_event_id=TEST_EVENT,
                updated_at=NOW,
            )
        )
        current_record_revision = connection.execute(
            sa.text(
                "SELECT current_revision_id FROM catalog.catalog_record "
                "WHERE organization_id=:org AND project_id=:project AND id=:record"
            ),
            {"org": ORG, "project": PROJECT, "record": RECORD},
        ).scalar_one()
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog.domain_record_identity_binding (
                  organization_id, project_id, classification, domain_kind,
                  domain_object_id, domain_revision_id, record_id, created_at,
                  created_by, request_id, trace_id
                ) VALUES (
                  :org, :project, :classification, 'test_data', :document,
                  :document_revision, :record, :now, :author, :request_id,
                  'fixture-trace'
                )
                """
            ),
            {
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "document": TEST_DOCUMENT,
                "document_revision": TEST_DOCUMENT_REVISION,
                "record": RECORD,
                "now": NOW,
                "author": AUTHOR,
                "request_id": TEST_DOCUMENT_REVISION,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO catalog.domain_record_binding (
                  id, organization_id, project_id, classification, record_id,
                  record_revision_id, domain_kind, domain_object_id, domain_revision_id,
                  created_at, created_by, request_id, trace_id
                ) VALUES (:id, :org, :project, :classification, :record, :record_revision,
                          'test_data', :document, :document_revision, :now, :author,
                          :request_id, 'fixture-trace')
                """
            ),
            {
                "id": TEST_BINDING,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "record": RECORD,
                "record_revision": current_record_revision,
                "document": TEST_DOCUMENT,
                "document_revision": TEST_DOCUMENT_REVISION,
                "now": NOW,
                "author": AUTHOR,
                "request_id": TEST_DOCUMENT_REVISION,
            },
        )
        # A second immutable document has no Record binding and is used only for
        # the negative resolver assertion below.
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document (
                  id, organization_id, project_id, classification, document_key,
                  current_revision_id, created_at, created_by, updated_at
                ) VALUES (:id, :org, :project, :classification, 'REVIEW-DOC-160-NOBIND',
                          :revision, :now, :author, :now)
                """
            ),
            {
                "id": TEST_NO_BINDING_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "revision": TEST_NO_BINDING_REVISION,
                "now": NOW,
                "author": AUTHOR,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document_revision (
                  id, aggregate_id, organization_id, project_id, classification, revision_no,
                  based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                  created_by, change_reason, request_id, trace_id, document_key, maker, grade,
                  test_date, operator_name, laboratory, test_method, specimen_key,
                  source_file_name, source_media_type, source_sha256, canonical_artifact_id,
                  canonical_sha256, normalized_artifact_id, normalized_sha256, point_count
                ) VALUES (
                  :revision, :id, :org, :project, :classification, 1, NULL,
                  'urn:cmp:datasets:test-data-document', '1.0.0', :digest, :now, :author,
                  'unbound fixture', :request_id, 'fixture-trace', 'REVIEW-DOC-160-NOBIND',
                  'CMP fixture lab', 'DP780', '2026-08-09', 'Fixture operator', 'CMP Lab',
                  'CMP-TENSILE-REFERENCE', 'SPEC-NOBIND', 'review-no-binding.json',
                  'application/json', :source_digest, :canonical_artifact, :canonical_digest,
                  :normalized_artifact, :normalized_digest, 2
                )
                """
            ),
            {
                "revision": TEST_NO_BINDING_REVISION,
                "id": TEST_NO_BINDING_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "digest": "5" * 64,
                "now": NOW,
                "author": AUTHOR,
                "request_id": TEST_NO_BINDING_REVISION,
                "source_digest": "6" * 64,
                "canonical_artifact": TEST_CANONICAL_ARTIFACT,
                "canonical_digest": "1" * 64,
                "normalized_artifact": TEST_NORMALIZED_ARTIFACT,
                "normalized_digest": "2" * 64,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document (
                  id, organization_id, project_id, classification, document_key,
                  current_revision_id, created_at, created_by, updated_at
                ) VALUES (:id, :org, :project, :classification, 'REVIEW-DMA-209',
                          :revision, :now, :author, :now)
                """
            ),
            {
                "id": TEST_GOVERNED_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "revision": TEST_GOVERNED_REVISION,
                "now": NOW,
                "author": AUTHOR,
            },
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO datasets.test_data_document_revision (
                  id, aggregate_id, organization_id, project_id, classification, revision_no,
                  based_on_revision_id, schema_id, schema_version, content_hash, created_at,
                  created_by, change_reason, request_id, trace_id, document_key, maker, grade,
                  test_date, operator_name, laboratory, test_method, specimen_key,
                  source_file_name, source_media_type, source_sha256, canonical_artifact_id,
                  canonical_sha256, normalized_artifact_id, normalized_sha256, point_count,
                  governed_source
                ) VALUES (
                  :revision, :id, :org, :project, :classification, 1, NULL,
                  'urn:cmp:datasets:test-data-document', '1.0.0', :digest, :now, :author,
                  'governed DMA review fixture', :request_id, 'fixture-trace', 'REVIEW-DMA-209',
                  'CMP fixture lab', 'Synthetic DMA', '2026-08-13', 'Fixture operator',
                  'CMP Lab', 'CMP-DMA-SYNTHETIC', 'SPEC-DMA-209', 'review-dma-209.csv',
                  'text/csv', :source_digest, :canonical_artifact, :canonical_digest,
                  :normalized_artifact, :normalized_digest, 2,
                  CAST(:governed_source AS jsonb)
                )
                """
            ),
            {
                "revision": TEST_GOVERNED_REVISION,
                "id": TEST_GOVERNED_DOCUMENT,
                "org": ORG,
                "project": PROJECT,
                "classification": DataClassification.INTERNAL.value,
                "digest": "7" * 64,
                "now": NOW,
                "author": AUTHOR,
                "request_id": TEST_GOVERNED_REVISION,
                "source_digest": "8" * 64,
                "canonical_artifact": TEST_CANONICAL_ARTIFACT,
                "canonical_digest": "1" * 64,
                "normalized_artifact": TEST_NORMALIZED_ARTIFACT,
                "normalized_digest": "2" * 64,
                "governed_source": json.dumps(
                    {
                        "material": {
                            "aggregate_id": str(AGGREGATE),
                            "revision_id": str(REVISION),
                        },
                        "material_state": {
                            "aggregate_id": "76000000-0000-4000-8000-000000000036",
                            "revision_id": "76000000-0000-4000-8000-000000000037",
                        },
                        "test_run": {
                            "aggregate_id": "76000000-0000-4000-8000-000000000038",
                            "revision_id": "76000000-0000-4000-8000-000000000039",
                        },
                        "tabular_import": {
                            "raw_asset_id": "76000000-0000-4000-8000-00000000003a",
                            "raw_artifact_id": "76000000-0000-4000-8000-00000000003b",
                            "import_run_id": "76000000-0000-4000-8000-00000000003c",
                            "import_profile": {
                                "aggregate_id": "76000000-0000-4000-8000-00000000003d",
                                "revision_id": "76000000-0000-4000-8000-00000000003e",
                            },
                            "normalized_dataset": {
                                "aggregate_id": "76000000-0000-4000-8000-00000000003f",
                                "revision_id": "76000000-0000-4000-8000-000000000040",
                            },
                        },
                    }
                ),
            },
        )
        connection.execute(
            sa.insert(lifecycle_event_table).values(
                id=TEST_GOVERNED_EVENT,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_GOVERNED_DOCUMENT,
                revision_id=TEST_GOVERNED_REVISION,
                sequence_no=1,
                from_state=None,
                to_state=LifecycleState.DRAFT.value,
                occurred_at=NOW,
                actor_id=AUTHOR,
                reason="governed DMA review fixture",
                request_id=TEST_GOVERNED_REQUEST,
                trace_id="fixture-trace",
            )
        )
        connection.execute(
            sa.insert(lifecycle_projection_table).values(
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL.value,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_GOVERNED_DOCUMENT,
                revision_id=TEST_GOVERNED_REVISION,
                lifecycle_state=LifecycleState.DRAFT.value,
                sequence_no=1,
                last_event_id=TEST_GOVERNED_EVENT,
                updated_at=NOW,
            )
        )

    sessions = sessionmaker(app_engine)
    rls_context = SqlAlchemyRlsContext()
    evidence_registry = ReviewSubjectEvidenceRegistry(
        (
            SqlAlchemyReviewSubjectResolver(
                subject_type="datasets.test_data_document",
                session_factory=sessions,
                rls_context=rls_context,
            ),
        )
    )
    repository = SqlAlchemyReviewRepository(
        session_factory=sessions,
        rls_context=rls_context,
        approval_projector=SqlAlchemyReviewApprovalProjector(),
    )
    author = _context(AUTHOR, UUID("76000000-0000-4000-8000-00000000002f"))
    reviewer = _context(REVIEWER, UUID("76000000-0000-4000-8000-000000000030"))
    author_request = _decision(author, Permission.REVIEW_REQUEST, Role.MATERIAL_MODELER)
    reviewer_catalog_read = _decision(reviewer, Permission.CATALOG_READ, Role.DOMAIN_REVIEWER)
    reviewer_review_read = _decision(reviewer, Permission.REVIEW_READ, Role.DOMAIN_REVIEWER)
    reviewer_decide = _decision(reviewer, Permission.REVIEW_DECIDE, Role.DOMAIN_REVIEWER)
    service = ReviewService(
        repository=repository,
        id_factory=iter(
            (
                TEST_REQUEST,
                TEST_DECISION,
                TEST_GOVERNED_REQUEST,
                TEST_GOVERNED_DECISION,
            )
        ).__next__,
        clock=lambda: NOW,
        evidence_registry=evidence_registry,
    )

    created = service.create_request(
        author,
        author_request,
        SubmitReviewRequest(
            classification=DataClassification.INTERNAL,
            aggregate_type="datasets.test_data_document",
            aggregate_id=TEST_DOCUMENT,
            revision_id=TEST_DOCUMENT_REVISION,
            manifest_sha256="3" * 64,
            reason="review exact canonical Test Data",
        ),
    )
    assert created.evidence is not None
    assert created.evidence.source_artifact_state is SourceArtifactState.ATTACHED
    assert created.evidence.source_artifact_sha256 == "1" * 64
    assert created.evidence.affected_record_id == RECORD
    approved = service.decide(
        reviewer,
        reviewer_decide,
        TEST_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256="3" * 64,
            decision=ReviewDecisionKind.APPROVED,
            reason="approve exact Test Data source and binding",
        ),
    )
    assert approved.lifecycle_state is LifecycleState.APPROVED
    catalog_repository = SqlAlchemyCatalogRecordRepository(
        session_factory=sessions,
        rls_context=rls_context,
    )
    published = catalog_repository.search_records(
        context=reviewer,
        decision=reviewer_catalog_read,
        query=CatalogRecordQuery(
            table_id=SCHEMA_TABLE,
            record_id=RECORD,
            published_only=True,
            domain_binding_kind="test_data",
            domain_binding_object_id=TEST_DOCUMENT,
            domain_binding_revision_id=TEST_DOCUMENT_REVISION,
        ),
    )
    assert published.total_count == 1
    governed_request = service.create_request(
        author,
        author_request,
        SubmitReviewRequest(
            classification=DataClassification.INTERNAL,
            aggregate_type="datasets.test_data_document",
            aggregate_id=TEST_GOVERNED_DOCUMENT,
            revision_id=TEST_GOVERNED_REVISION,
            manifest_sha256="7" * 64,
            reason="review exact governed DMA Test Data without a Record adapter",
        ),
    )
    assert governed_request.evidence is not None
    assert governed_request.evidence.affected_record_id is None
    assert governed_request.evidence.affected_material_id == AGGREGATE
    assert governed_request.evidence.affected_material_revision_id == REVISION
    assert governed_request.evidence.affected_path == (
        f"/materials/{AGGREGATE}?material_revision_id={REVISION}"
    )
    assert f"material:{AGGREGATE}:{REVISION}" in governed_request.evidence.exact_input_use
    governed_approved = service.decide(
        reviewer,
        reviewer_decide,
        TEST_GOVERNED_REQUEST,
        DecideReviewRequest(
            expected_manifest_sha256="7" * 64,
            decision=ReviewDecisionKind.APPROVED,
            reason="approve the exact governed DMA source and Material pin",
        ),
    )
    assert governed_approved.lifecycle_state is LifecycleState.APPROVED
    activity = service.list_requests(
        reviewer,
        reviewer_review_read,
        limit=10,
        aggregate_type="datasets.test_data_document",
        aggregate_id=TEST_GOVERNED_DOCUMENT,
        revision_id=TEST_GOVERNED_REVISION,
    )
    assert [item.id for item in activity] == [TEST_GOVERNED_REQUEST]
    with sessions() as session, session.begin():
        rls_context.bind_authorization(session, reviewer, reviewer_decide)
        governed_projection = (
            session.execute(
                sa.select(review_publication_projection_table).where(
                    review_publication_projection_table.c.review_request_id == TEST_GOVERNED_REQUEST
                )
            )
            .mappings()
            .one()
        )
    assert governed_projection["material_id"] == AGGREGATE
    assert governed_projection["material_revision_id"] == REVISION
    assert governed_projection["record_id"] is None
    assert governed_projection["record_revision_id"] is None
    with pytest.raises(ReviewEvidenceError, match="manifest hint"):
        service.create_request(
            author,
            author_request,
            SubmitReviewRequest(
                classification=DataClassification.INTERNAL,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_DOCUMENT,
                revision_id=TEST_DOCUMENT_REVISION,
                manifest_sha256="f" * 64,
                reason="wrong source digest must fail",
            ),
        )
    with pytest.raises(ReviewEvidenceError, match="current exact Materials Record binding"):
        service.create_request(
            author,
            author_request,
            SubmitReviewRequest(
                classification=DataClassification.INTERNAL,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_NO_BINDING_DOCUMENT,
                revision_id=TEST_NO_BINDING_REVISION,
                manifest_sha256="5" * 64,
                reason="missing binding must fail",
            ),
        )
    with pytest.raises(Exception, match="authorization decision"):
        service.create_request(
            author,
            _decision(author, Permission.REVIEW_READ, Role.MATERIAL_MODELER),
            SubmitReviewRequest(
                classification=DataClassification.INTERNAL,
                aggregate_type="datasets.test_data_document",
                aggregate_id=TEST_DOCUMENT,
                revision_id=TEST_DOCUMENT_REVISION,
                manifest_sha256="3" * 64,
                reason="wrong authorization permission must fail",
            ),
        )
