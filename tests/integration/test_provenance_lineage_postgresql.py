from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

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
    activity_table,
    agent_table,
    association_table,
    derivation_table,
    entity_table,
    generation_table,
    usage_table,
)
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.domain.lineage import (
    CompletenessReportState,
    LineageDirection,
)
from cmp.modules.provenance.domain.model import ProvenanceNotFound
from sqlalchemy.engine import URL, Engine, make_url
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

NOW = datetime(2026, 7, 13, 14, 0, tzinfo=UTC)
ORG = UUID("93000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("93000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("93000000-0000-4000-8000-000000000003")
ACTOR = UUID("93000000-0000-4000-8000-000000000004")
AGENT = UUID("93000000-0000-4000-8000-000000000005")
SOURCE = UUID("93000000-0000-4000-8000-000000000010")
LEFT = UUID("93000000-0000-4000-8000-000000000020")
RIGHT = UUID("93000000-0000-4000-8000-000000000030")
ROOT = UUID("93000000-0000-4000-8000-000000000040")
ACTIVITY_LEFT = UUID("93000000-0000-4000-8000-000000000050")
ACTIVITY_RIGHT = UUID("93000000-0000-4000-8000-000000000060")
ACTIVITY_ROOT = UUID("93000000-0000-4000-8000-000000000070")
OTHER_PROJECT_ENTITY = UUID("93000000-0000-4000-8000-000000000080")
RESTRICTED_ENTITY = UUID("93000000-0000-4000-8000-000000000085")
ORPHAN = UUID("93000000-0000-4000-8000-000000000090")
BAD_SOURCE = UUID("93000000-0000-4000-8000-0000000000a0")
BAD_ROOT = UUID("93000000-0000-4000-8000-0000000000b0")
BAD_ACTIVITY = UUID("93000000-0000-4000-8000-0000000000c0")
CYCLE_A = UUID("93000000-0000-4000-8000-0000000000d0")
CYCLE_B = UUID("93000000-0000-4000-8000-0000000000e0")
CYCLE_ACTIVITY_A = UUID("93000000-0000-4000-8000-0000000000f0")
CYCLE_ACTIVITY_B = UUID("93000000-0000-4000-8000-000000000100")
STAR_SOURCE = UUID("93000000-0000-4000-8000-000000000110")
CHAIN_SOURCE = UUID("93000000-0000-4000-8000-000000000120")
REQUEST = UUID("93000000-0000-4000-8000-000000000130")
TRACE = "00-00000000000000000000000000000093-0000000000000093-01"


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
        principal=Principal(ACTOR, PrincipalType.USER, "T14 Lineage Reader", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST,
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    *,
    maximum: DataClassification = DataClassification.RESTRICTED,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=context.project_id,
        permission=Permission.PROVENANCE_READ,
        roles=(Role.AUDITOR,),
        database_permissions=database_permissions_for(Permission.PROVENANCE_READ),
        max_classification=maximum,
        allow_export_controlled=False,
        request_id=REQUEST,
        trace_id=TRACE,
        decided_at=NOW,
    )


def _scope(project_id: UUID = PROJECT_A) -> dict[str, object]:
    return {
        "organization_id": ORG,
        "project_id": project_id,
        "classification": "internal",
    }


def _entity(
    entity_id: UUID,
    *,
    source: bool = False,
    project_id: UUID = PROJECT_A,
) -> dict[str, object]:
    reference_type = "artifact.raw_asset" if source else "synthetic.dataset_revision"
    return {
        **_scope(project_id),
        "id": entity_id,
        "entity_type": reference_type,
        "reference_kind": "raw_asset" if source else "revision",
        "reference_type": reference_type,
        "reference_id": uuid5(NAMESPACE_URL, f"reference:{entity_id}"),
        "content_sha256": hashlib.sha256(entity_id.bytes).hexdigest(),
        "generation_requirement": "none" if source else "primary",
        "created_at": NOW,
        "recorded_at": NOW,
        "recorded_by": ACTOR,
        "request_id": REQUEST,
        "trace_id": TRACE,
    }


def _activity(activity_id: UUID) -> dict[str, object]:
    return {
        **_scope(),
        "id": activity_id,
        "activity_type": "synthetic.transform_run",
        "domain_run_type": "synthetic.transform_run",
        "domain_run_id": activity_id,
        "status": "succeeded",
        "input_required": True,
        "output_required": True,
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=1),
        "submission_digest": hashlib.sha256(activity_id.bytes).hexdigest(),
        "recorded_at": NOW,
        "recorded_by": ACTOR,
        "request_id": REQUEST,
        "trace_id": TRACE,
    }


def _relation() -> dict[str, object]:
    return {**_scope(), "recorded_at": NOW, "recorded_by": ACTOR}


def _seed_complete_diamond(connection: sa.Connection) -> None:
    restricted = _entity(RESTRICTED_ENTITY, source=True)
    restricted["classification"] = "restricted"
    connection.execute(
        sa.insert(entity_table),
        [
            _entity(SOURCE, source=True),
            _entity(LEFT),
            _entity(RIGHT),
            _entity(ROOT),
            _entity(OTHER_PROJECT_ENTITY, source=True, project_id=PROJECT_B),
            restricted,
        ],
    )
    connection.execute(
        sa.insert(agent_table).values(
            **_scope(),
            id=AGENT,
            agent_type="user",
            reference_id=ACTOR,
            recorded_at=NOW,
            recorded_by=ACTOR,
            request_id=REQUEST,
            trace_id=TRACE,
        )
    )
    connection.execute(
        sa.insert(activity_table),
        [_activity(ACTIVITY_LEFT), _activity(ACTIVITY_RIGHT), _activity(ACTIVITY_ROOT)],
    )
    connection.execute(
        sa.insert(usage_table),
        [
            {
                **_relation(),
                "activity_id": ACTIVITY_LEFT,
                "entity_id": SOURCE,
                "role": "source",
                "ordinal": 0,
            },
            {
                **_relation(),
                "activity_id": ACTIVITY_RIGHT,
                "entity_id": SOURCE,
                "role": "source",
                "ordinal": 0,
            },
            {
                **_relation(),
                "activity_id": ACTIVITY_ROOT,
                "entity_id": LEFT,
                "role": "source",
                "ordinal": 0,
            },
            {
                **_relation(),
                "activity_id": ACTIVITY_ROOT,
                "entity_id": RIGHT,
                "role": "source",
                "ordinal": 1,
            },
        ],
    )
    connection.execute(
        sa.insert(generation_table),
        [
            {
                **_relation(),
                "entity_id": LEFT,
                "activity_id": ACTIVITY_LEFT,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
            {
                **_relation(),
                "entity_id": RIGHT,
                "activity_id": ACTIVITY_RIGHT,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
            {
                **_relation(),
                "entity_id": ROOT,
                "activity_id": ACTIVITY_ROOT,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
        ],
    )
    connection.execute(
        sa.insert(association_table),
        [
            {
                **_relation(),
                "activity_id": activity_id,
                "agent_id": AGENT,
                "role": "operator",
                "plan_entity_id": None,
            }
            for activity_id in (ACTIVITY_LEFT, ACTIVITY_RIGHT, ACTIVITY_ROOT)
        ],
    )
    connection.execute(
        sa.insert(derivation_table),
        [
            {
                **_relation(),
                "generated_entity_id": LEFT,
                "used_entity_id": SOURCE,
                "activity_id": ACTIVITY_LEFT,
                "derivation_kind": "transform",
            },
            {
                **_relation(),
                "generated_entity_id": RIGHT,
                "used_entity_id": SOURCE,
                "activity_id": ACTIVITY_RIGHT,
                "derivation_kind": "transform",
            },
            {
                **_relation(),
                "generated_entity_id": ROOT,
                "used_entity_id": LEFT,
                "activity_id": ACTIVITY_ROOT,
                "derivation_kind": "transform",
            },
            {
                **_relation(),
                "generated_entity_id": ROOT,
                "used_entity_id": RIGHT,
                "activity_id": ACTIVITY_ROOT,
                "derivation_kind": "transform",
            },
        ],
    )


def _seed_corrupt_fixtures(connection: sa.Connection) -> None:
    connection.execute(
        sa.insert(entity_table),
        [
            _entity(ORPHAN),
            _entity(BAD_SOURCE, source=True),
            _entity(BAD_ROOT),
            _entity(CYCLE_A),
            _entity(CYCLE_B),
        ],
    )
    connection.execute(
        sa.insert(activity_table),
        [_activity(BAD_ACTIVITY), _activity(CYCLE_ACTIVITY_A), _activity(CYCLE_ACTIVITY_B)],
    )
    connection.execute(
        sa.insert(generation_table),
        [
            {
                **_relation(),
                "entity_id": BAD_ROOT,
                "activity_id": BAD_ACTIVITY,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
            {
                **_relation(),
                "entity_id": CYCLE_A,
                "activity_id": CYCLE_ACTIVITY_A,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
            {
                **_relation(),
                "entity_id": CYCLE_B,
                "activity_id": CYCLE_ACTIVITY_B,
                "role": "primary",
                "generated_at": NOW + timedelta(seconds=1),
            },
        ],
    )
    connection.execute(
        sa.insert(usage_table),
        [
            {
                **_relation(),
                "activity_id": CYCLE_ACTIVITY_A,
                "entity_id": CYCLE_B,
                "role": "source",
                "ordinal": 0,
            },
            {
                **_relation(),
                "activity_id": CYCLE_ACTIVITY_B,
                "entity_id": CYCLE_A,
                "role": "source",
                "ordinal": 0,
            },
        ],
    )
    connection.execute(
        sa.insert(association_table),
        [
            {
                **_relation(),
                "activity_id": activity_id,
                "agent_id": AGENT,
                "role": "operator",
                "plan_entity_id": None,
            }
            for activity_id in (CYCLE_ACTIVITY_A, CYCLE_ACTIVITY_B)
        ],
    )
    connection.execute(
        sa.insert(derivation_table),
        [
            {
                **_relation(),
                "generated_entity_id": BAD_ROOT,
                "used_entity_id": BAD_SOURCE,
                "activity_id": None,
                "derivation_kind": "transform",
            },
            {
                **_relation(),
                "generated_entity_id": CYCLE_A,
                "used_entity_id": CYCLE_B,
                "activity_id": CYCLE_ACTIVITY_A,
                "derivation_kind": "transform",
            },
            {
                **_relation(),
                "generated_entity_id": CYCLE_B,
                "used_entity_id": CYCLE_A,
                "activity_id": CYCLE_ACTIVITY_B,
                "derivation_kind": "transform",
            },
        ],
    )


def _seed_scale_fixtures(connection: sa.Connection) -> UUID:
    connection.execute(sa.insert(entity_table).values(**_entity(STAR_SOURCE, source=True)))
    connection.execute(
        sa.text(
            "INSERT INTO provenance.entity ("
            "organization_id, project_id, classification, id, entity_type, reference_kind, "
            "reference_type, reference_id, content_sha256, generation_requirement, created_at, "
            "recorded_at, recorded_by, request_id, trace_id) "
            "SELECT :organization_id, :project_id, 'internal', "
            "md5('t14-star-node-' || value::text)::uuid, 'synthetic.dataset_revision', "
            "'revision', 'synthetic.dataset_revision', "
            "md5('t14-star-ref-' || value::text)::uuid, "
            "md5('t14-star-digest-a-' || value::text) || "
            "md5('t14-star-digest-b-' || value::text), 'primary', :now, :now, "
            ":actor, :request_id, :trace_id FROM generate_series(1, 10000) AS value"
        ),
        {
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "now": NOW,
            "actor": ACTOR,
            "request_id": REQUEST,
            "trace_id": TRACE,
        },
    )
    connection.execute(
        sa.text(
            "INSERT INTO provenance.derivation ("
            "organization_id, project_id, classification, generated_entity_id, "
            "used_entity_id, activity_id, derivation_kind, recorded_at, recorded_by) "
            "SELECT :organization_id, :project_id, 'internal', "
            "md5('t14-star-node-' || value::text)::uuid, :source_id, NULL, "
            "'impact', :now, :actor FROM generate_series(1, 10000) AS value"
        ),
        {
            "organization_id": ORG,
            "project_id": PROJECT_A,
            "source_id": STAR_SOURCE,
            "now": NOW,
            "actor": ACTOR,
        },
    )

    chain_ids = [uuid5(NAMESPACE_URL, f"t14-chain:{index}") for index in range(10)]
    connection.execute(sa.insert(entity_table).values(**_entity(CHAIN_SOURCE, source=True)))
    connection.execute(sa.insert(entity_table), [_entity(value) for value in chain_ids])
    parent = CHAIN_SOURCE
    edges: list[dict[str, object]] = []
    for child in chain_ids:
        edges.append(
            {
                **_relation(),
                "generated_entity_id": child,
                "used_entity_id": parent,
                "activity_id": None,
                "derivation_kind": "chain",
            }
        )
        parent = child
    connection.execute(sa.insert(derivation_table), edges)
    return chain_ids[-1]


@dataclass(frozen=True, slots=True)
class PostgresHarness:
    service: ProvenanceLineageService
    chain_root: UUID


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresHarness]:
    assert POSTGRES_DSN is not None
    admin_url = _psycopg_url(POSTGRES_DSN)
    database_name = f"cmp_t14_{uuid4().hex}"
    app_role = f"cmp_t14_app_{uuid4().hex}"
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
                    "VALUES (:id, 'user', 'T14 Lineage Reader', true, :now, :now)"
                ),
                {"id": ACTOR, "now": NOW - timedelta(days=1)},
            )
            connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
            _seed_complete_diamond(connection)
            _seed_corrupt_fixtures(connection)
            chain_root = _seed_scale_fixtures(connection)
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA revisioning, access_control, provenance TO "{app_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT SELECT ON ALL TABLES IN SCHEMA provenance TO "{app_role}"'
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
        yield PostgresHarness(ProvenanceLineageService(repository=repository), chain_root)
    finally:
        if app_engine is not None:
            app_engine.dispose()
        admin_engine.dispose()
        with cluster_engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
            connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{app_role}"')
        cluster_engine.dispose()


def test_known_dag_is_unique_paginated_bidirectional_and_complete(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context)
    first = postgres.service.query(
        context,
        decision,
        ROOT,
        direction=LineageDirection.UPSTREAM,
        limit=2,
    )
    second = postgres.service.query(
        context,
        decision,
        ROOT,
        direction=LineageDirection.UPSTREAM,
        limit=2,
        cursor=first.next_cursor,
    )
    impact = postgres.service.impact(
        context,
        decision,
        SOURCE,
        target_entity_type="synthetic.dataset_revision",
    )
    report = postgres.service.completeness(context, decision, ROOT)

    identifiers = [node.record.entity.id for node in (*first.nodes, *second.nodes)]
    assert identifiers == [ROOT, LEFT, RIGHT, SOURCE]
    assert len(identifiers) == len(set(identifiers))
    assert second.nodes[-1].path == (ROOT, LEFT, SOURCE)
    assert {node.record.entity.id for node in impact.nodes} == {LEFT, RIGHT, ROOT}
    assert report.state is CompletenessReportState.COMPLETE
    assert report.eligible


def test_depth_limit_cursor_binding_and_project_rls_fail_closed(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context)
    shallow = postgres.service.query(
        context,
        decision,
        ROOT,
        direction=LineageDirection.UPSTREAM,
        max_depth=1,
    )
    assert shallow.graph_truncated
    assert {node.record.entity.id for node in shallow.nodes} == {ROOT, LEFT, RIGHT}

    with pytest.raises(ProvenanceNotFound):
        postgres.service.query(
            context,
            decision,
            OTHER_PROJECT_ENTITY,
            direction=LineageDirection.UPSTREAM,
        )
    with pytest.raises(ProvenanceNotFound):
        postgres.service.query(
            context,
            _decision(context, maximum=DataClassification.INTERNAL),
            RESTRICTED_ENTITY,
            direction=LineageDirection.UPSTREAM,
        )


def test_completeness_reports_orphan_incomplete_activity_and_cycle(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context)
    orphan = postgres.service.completeness(context, decision, ORPHAN)
    bad_activity = postgres.service.completeness(context, decision, BAD_ROOT)
    cycle = postgres.service.completeness(context, decision, CYCLE_A)

    assert orphan.state is CompletenessReportState.INCOMPLETE
    assert {issue.code.value for issue in orphan.issues} >= {
        "missing_primary_generation",
        "missing_source_path",
    }
    assert {issue.code.value for issue in bad_activity.issues} >= {
        "missing_activity_input",
        "missing_activity_agent",
    }
    assert {issue.code.value for issue in cycle.issues} >= {
        "dependency_cycle",
        "missing_source_path",
    }


def test_ten_hop_and_ten_thousand_edge_fixtures_are_bounded(
    postgres: PostgresHarness,
) -> None:
    context = _context()
    decision = _decision(context)
    chain = postgres.service.query(
        context,
        decision,
        postgres.chain_root,
        direction=LineageDirection.UPSTREAM,
        max_depth=10,
        limit=1000,
    )
    assert len(chain.nodes) == 11
    assert max(node.depth for node in chain.nodes) == 10
    assert not chain.graph_truncated

    started = perf_counter()
    impact = postgres.service.impact(
        context,
        decision,
        STAR_SOURCE,
        max_depth=1,
        limit=1000,
    )
    elapsed = perf_counter() - started

    assert impact.graph_truncated
    assert impact.total_discovered == 10_000
    assert len(impact.nodes) == 1000
    assert impact.next_cursor is not None
    assert elapsed < 2.0
