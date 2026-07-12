from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
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
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
    SqlAlchemyRevisionProvenanceHook,
    activity_table,
    derivation_table,
    entity_table,
)
from cmp.modules.provenance.application.service import (
    ProvenanceReferenceResolver,
    ProvenanceService,
)
from cmp.modules.provenance.domain.model import (
    ActivityAgent,
    ActivityInput,
    ActivityOutput,
    ActivityStatus,
    AgentReference,
    AgentType,
    CommitActivityProvenance,
    DerivationInput,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceConflict,
    ProvenanceNotFound,
    ProvenanceScope,
    ResolvedAgentReference,
    ResolvedEntityReference,
)
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).parents[2]
POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="set CMP_TEST_POSTGRES_DSN to an isolated PostgreSQL admin URL",
    ),
]

NOW = datetime(2026, 7, 13, 11, 0, tzinfo=UTC)
ORG = UUID("8f000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("8f000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("8f000000-0000-4000-8000-000000000003")
ACTOR = UUID("8f000000-0000-4000-8000-000000000004")
RAW_ID = UUID("8f000000-0000-4000-8000-000000000005")
UPLOAD_ID = UUID("8f000000-0000-4000-8000-000000000006")
TRACE = "00-0000000000000000000000000000008f-000000000000008f-01"
RAW_BYTES = b"t13-synthetic-raw"
RAW_DIGEST = hashlib.sha256(RAW_BYTES).hexdigest()
SCOPE = ProvenanceScope(ORG, PROJECT_A, DataClassification.INTERNAL)
RAW_REFERENCE = ImmutableEntityReference(
    EntityReferenceKind.RAW_ASSET,
    "artifact.raw_asset",
    RAW_ID,
    RAW_DIGEST,
)


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


def _context(*, project_id: UUID = PROJECT_A) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "T13 Provenance User", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
) -> AuthorizationDecision:
    role = Role.DATA_STEWARD if permission is Permission.ARTIFACT_WRITE else Role.AUDITOR
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


class _Resolver(ProvenanceReferenceResolver):
    def resolve_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: ImmutableEntityReference,
    ) -> ResolvedEntityReference:
        del context, decision
        if reference.kind is EntityReferenceKind.RAW_ASSET:
            if reference != RAW_REFERENCE:
                raise ProvenanceNotFound("Raw Asset not found")
            entity_type = "artifact.raw_asset"
            requirement = GenerationRequirement.NONE
        elif reference.kind is EntityReferenceKind.REVISION:
            if reference.reference_type != "synthetic.dataset_revision":
                raise ProvenanceNotFound("revision type not owned by synthetic resolver")
            entity_type = reference.reference_type
            requirement = GenerationRequirement.PRIMARY
        else:
            raise ProvenanceNotFound("Artifact fixture is not configured")
        return ResolvedEntityReference(
            reference,
            entity_type,
            SCOPE,
            NOW,
            requirement,
        )

    def resolve_agent(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: AgentReference,
    ) -> ResolvedAgentReference:
        del context, decision
        if reference != AgentReference(AgentType.USER, ACTOR):
            raise ProvenanceNotFound("Agent not found")
        return ResolvedAgentReference(reference, SCOPE)


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    admin_engine: Engine
    sessions: sessionmaker[Session]
    rls: SqlAlchemyRlsContext
    service: ProvenanceService


def _insert_raw_asset(connection: sa.Connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO artifact.upload_session ("
            "organization_id, project_id, id, classification, state, original_filename, "
            "media_type, expected_size_bytes, expected_sha256, part_size_bytes, "
            "expected_part_count, test_run_revision_id, staging_object_key, "
            "object_upload_id, idempotency_key, submission_digest, created_at, "
            "expires_at, created_by, request_id, trace_id, updated_at, terminal_at, "
            "raw_asset_id, failure_code) VALUES ("
            ":organization_id, :project_id, :id, 'internal', 'completing', "
            "'synthetic.raw', 'application/octet-stream', :size_bytes, :sha256, "
            ":size_bytes, 1, NULL, :staging_key, :object_upload_id, :idempotency_key, "
            ":submission_digest, :created_at, :expires_at, :created_by, :request_id, "
            ":trace_id, :created_at, NULL, NULL, NULL)"
        ),
        {
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "id": UPLOAD_ID,
            "size_bytes": len(RAW_BYTES),
            "sha256": RAW_DIGEST,
            "staging_key": f"staging/{ORG}/{PROJECT_A}/{UPLOAD_ID}",
            "object_upload_id": f"upload-{UPLOAD_ID}",
            "idempotency_key": "t13-raw-fixture",
            "submission_digest": hashlib.sha256(b"submission").hexdigest(),
            "created_at": NOW - timedelta(minutes=1),
            "expires_at": NOW + timedelta(days=1),
            "created_by": ACTOR,
            "request_id": uuid4(),
            "trace_id": TRACE,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO artifact.raw_asset ("
            "organization_id, project_id, id, classification, sha256, size_bytes, "
            "media_type, original_filename, storage_state, staging_object_key, "
            "created_at, created_by) VALUES ("
            ":organization_id, :project_id, :id, 'internal', :sha256, :size_bytes, "
            "'application/octet-stream', 'synthetic.raw', 'staged_verified', "
            ":staging_key, :created_at, :created_by)"
        ),
        {
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "id": RAW_ID,
            "sha256": RAW_DIGEST,
            "size_bytes": len(RAW_BYTES),
            "staging_key": f"staging/{ORG}/{PROJECT_A}/{UPLOAD_ID}",
            "created_at": NOW,
            "created_by": ACTOR,
        },
    )


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t13_{uuid4().hex}"
    app_role = f"cmp_t13_app_{uuid4().hex}"
    cluster_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with cluster_engine.connect() as connection:
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
                    "VALUES (:id, 'user', 'T13 Provenance User', true, :now, :now)"
                ),
                {"id": ACTOR, "now": NOW - timedelta(days=1)},
            )
            _insert_raw_asset(connection)
            connection.exec_driver_sql(
                "GRANT USAGE ON SCHEMA identity, revisioning, access_control, "
                f'artifact, plugin, provenance TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT ON identity.principal, artifact.raw_asset, "
                f'artifact.artifact, plugin.package TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA provenance "
                f'TO "{app_role}"'
            )
            connection.exec_driver_sql(
                "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA access_control, revisioning, "
                f'provenance TO "{app_role}"'
            )
        app_engine = sa.create_engine(
            database_url.set(username=app_role, password=None), pool_pre_ping=True
        )
        sessions = sessionmaker(app_engine, class_=Session, expire_on_commit=False)
        rls = SqlAlchemyRlsContext()
        with sessions() as session, session.begin():
            rls.assert_application_role(session)
        repository = SqlAlchemyProvenanceRepository(
            session_factory=sessions,
            rls_context=rls,
        )
        yield PostgresHarness(
            admin_engine=admin_engine,
            sessions=sessions,
            rls=rls,
            service=ProvenanceService(repository=repository, resolver=_Resolver()),
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{app_role}"')
        cluster_engine.dispose()


def _revision_reference(reference_id: UUID, marker: bytes) -> ImmutableEntityReference:
    return ImmutableEntityReference(
        EntityReferenceKind.REVISION,
        "synthetic.dataset_revision",
        reference_id,
        hashlib.sha256(marker).hexdigest(),
    )


def _command(
    *,
    run_id: UUID,
    output: ImmutableEntityReference,
    source: ImmutableEntityReference = RAW_REFERENCE,
) -> CommitActivityProvenance:
    return CommitActivityProvenance(
        scope=SCOPE,
        activity_type="synthetic.normalization_run",
        domain_run_type="synthetic.dataset_run",
        domain_run_id=run_id,
        status=ActivityStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        inputs=(ActivityInput(source, "source", 0),),
        outputs=(
            ActivityOutput(
                output,
                "primary",
                (DerivationInput(source, "normalization"),),
            ),
        ),
        agents=(ActivityAgent(AgentReference(AgentType.USER, ACTOR), "operator"),),
    )


def test_raw_to_revision_is_complete_idempotent_and_has_typed_relations(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.ARTIFACT_WRITE)
    output = _revision_reference(uuid4(), b"raw-to-dataset")
    command_value = _command(run_id=uuid4(), output=output)

    committed = postgres.service.commit_activity(context, write, command_value)
    replayed = postgres.service.commit_activity(context, write, command_value)
    with pytest.raises(ProvenanceConflict, match="another graph"):
        postgres.service.commit_activity(
            context,
            write,
            _command(
                run_id=command_value.domain_run_id,
                output=_revision_reference(uuid4(), b"substituted-output"),
            ),
        )
    read = _decision(context, Permission.PROVENANCE_READ)
    record = postgres.service.get_entity(
        context, read, committed.output_entity_ids[0]
    )
    with postgres.admin_engine.connect() as connection:
        relation_counts = connection.execute(
            sa.text(
                "SELECT "
                "(SELECT count(*) FROM provenance.usage WHERE activity_id = :activity_id), "
                "(SELECT count(*) FROM provenance.generation WHERE activity_id = :activity_id), "
                "(SELECT count(*) FROM provenance.derivation WHERE activity_id = :activity_id), "
                "(SELECT count(*) FROM provenance.association WHERE activity_id = :activity_id)"
            ),
            {"activity_id": committed.activity.id},
        ).one()

    assert not committed.replayed
    assert replayed.replayed
    assert replayed.activity.id == committed.activity.id
    assert record.completeness.state.value == "complete"
    assert record.generation_activity_id == committed.activity.id
    assert relation_counts == (1, 1, 1, 1)


def test_duplicate_generation_reverse_cycle_and_orphan_are_rejected(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.ARTIFACT_WRITE)
    first = _revision_reference(uuid4(), b"cycle-first")
    second = _revision_reference(uuid4(), b"cycle-second")
    first_result = postgres.service.commit_activity(
        context, write, _command(run_id=uuid4(), output=first)
    )
    second_result = postgres.service.commit_activity(
        context,
        write,
        _command(run_id=uuid4(), source=first, output=second),
    )

    with pytest.raises(ProvenanceConflict, match="database rejected"):
        postgres.service.commit_activity(
            context, write, _command(run_id=uuid4(), output=first)
        )

    with pytest.raises(DBAPIError, match="cycle"):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            session.execute(
                sa.insert(derivation_table).values(
                    organization_id=ORG,
                    project_id=PROJECT_A,
                    classification="internal",
                    generated_entity_id=first_result.output_entity_ids[0],
                    used_entity_id=second_result.output_entity_ids[0],
                    activity_id=None,
                    derivation_kind="reverse",
                    recorded_at=NOW + timedelta(seconds=2),
                    recorded_by=ACTOR,
                )
            )

    with pytest.raises(DBAPIError, match="primary generation"):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            orphan_id = uuid4()
            session.execute(
                sa.insert(entity_table).values(
                    organization_id=ORG,
                    project_id=PROJECT_A,
                    classification="internal",
                    id=uuid4(),
                    entity_type="synthetic.dataset_revision",
                    reference_kind="revision",
                    reference_type="synthetic.dataset_revision",
                    reference_id=orphan_id,
                    content_sha256=hashlib.sha256(orphan_id.bytes).hexdigest(),
                    generation_requirement="primary",
                    created_at=NOW,
                    recorded_at=NOW,
                    recorded_by=ACTOR,
                    request_id=context.request_id,
                    trace_id=TRACE,
                )
            )


def test_rls_hides_cross_project_and_immutable_rows_reject_admin_mutation(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    output = _revision_reference(uuid4(), b"rls")
    result = postgres.service.commit_activity(
        context,
        _decision(context, Permission.ARTIFACT_WRITE),
        _command(run_id=uuid4(), output=output),
    )
    other_context = _context(project_id=PROJECT_B)

    with pytest.raises(ProvenanceNotFound):
        postgres.service.get_entity(
            other_context,
            _decision(other_context, Permission.PROVENANCE_READ),
            result.output_entity_ids[0],
        )
    with pytest.raises(DBAPIError, match="immutable"):
        with postgres.admin_engine.begin() as connection:
            connection.execute(
                sa.update(entity_table)
                .where(entity_table.c.id == result.output_entity_ids[0])
                .values(content_sha256=hashlib.sha256(b"changed").hexdigest())
            )


def test_t06_revision_hook_writes_generation_revision_and_agent_in_same_session(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.ARTIFACT_WRITE)
    hook = SqlAlchemyRevisionProvenanceHook()
    aggregate_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    tenant = TenantScope(ORG, PROJECT_A, "internal")

    def record(
        revision_id: UUID,
        revision_no: int,
        based_on: UUID | None,
        digest: str,
    ) -> RevisionRecord:
        return RevisionRecord(
            revision_id=revision_id,
            aggregate_type="synthetic.fixture",
            aggregate_id=aggregate_id,
            scope=tenant,
            revision_no=revision_no,
            based_on_revision_id=based_on,
            schema_id="synthetic.fixture",
            schema_version="1.0.0",
            content_hash=digest,
            created_at=NOW + timedelta(seconds=revision_no),
            created_by=ACTOR,
            change_reason=f"revision {revision_no}",
            request_id=context.request_id,
            trace_id=TRACE,
        )

    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(session, context, write)
        hook(
            session,
            RevisionCreated(record(first_id, 1, None, hashlib.sha256(b"one").hexdigest()), "draft"),
        )
    with postgres.sessions() as session, session.begin():
        postgres.rls.bind_authorization(session, context, write)
        hook(
            session,
            RevisionCreated(
                record(second_id, 2, first_id, hashlib.sha256(b"two").hexdigest()),
                "draft",
            ),
        )

    with postgres.admin_engine.connect() as connection:
        counts = connection.execute(
            sa.text(
                "SELECT "
                "(SELECT count(*) FROM provenance.entity "
                " WHERE reference_type = 'synthetic.fixture.revision'), "
                "(SELECT count(*) FROM provenance.revision)"
            )
        ).one()
    assert counts == (2, 1)


def test_incomplete_activity_without_usage_agent_or_output_is_rejected(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    write = _decision(context, Permission.ARTIFACT_WRITE)
    with pytest.raises(DBAPIError, match="immutable input usage"):
        with postgres.sessions() as session, session.begin():
            postgres.rls.bind_authorization(session, context, write)
            session.execute(
                sa.insert(activity_table).values(
                    organization_id=ORG,
                    project_id=PROJECT_A,
                    classification="internal",
                    id=uuid4(),
                    activity_type="synthetic.incomplete_run",
                    domain_run_type="synthetic.incomplete_run",
                    domain_run_id=uuid4(),
                    status="succeeded",
                    input_required=True,
                    output_required=True,
                    started_at=NOW,
                    ended_at=NOW,
                    submission_digest=hashlib.sha256(b"incomplete").hexdigest(),
                    recorded_at=NOW,
                    recorded_by=ACTOR,
                    request_id=context.request_id,
                    trace_id=TRACE,
                )
            )
