"""RLS-bound PostgreSQL repository and T-06 hook for typed provenance."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.provenance.application.service import ResolvedActivityCommit
from cmp.modules.provenance.domain.lineage import (
    CompletenessIssue,
    CompletenessIssueCode,
    DependencyEdge,
    LineageDirection,
    LineageGraph,
    LineageRelation,
    LineageVertex,
)
from cmp.modules.provenance.domain.model import (
    ActivityCommitResult,
    ActivityStatus,
    AgentReference,
    AgentType,
    CompletenessState,
    EntityCompleteness,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceConflict,
    ProvenanceEntity,
    ProvenanceNotFound,
    ProvenanceRecord,
    ProvenanceScope,
)
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, content_sha256

metadata = sa.MetaData()
uuid_type = postgresql.UUID(as_uuid=True)


def _scope_columns() -> list[sa.Column[Any]]:
    return [
        sa.Column("organization_id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
    ]


entity_table = sa.Table(
    "entity",
    metadata,
    *_scope_columns(),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("entity_type", sa.String(100), nullable=False),
    sa.Column("reference_kind", sa.String(32), nullable=False),
    sa.Column("reference_type", sa.String(100), nullable=False),
    sa.Column("reference_id", uuid_type, nullable=False),
    sa.Column("content_sha256", sa.CHAR(64), nullable=False),
    sa.Column("generation_requirement", sa.String(16), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="provenance",
)

activity_table = sa.Table(
    "activity",
    metadata,
    *_scope_columns(),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("activity_type", sa.String(100), nullable=False),
    sa.Column("domain_run_type", sa.String(100), nullable=False),
    sa.Column("domain_run_id", uuid_type, nullable=False),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("input_required", sa.Boolean(), nullable=False),
    sa.Column("output_required", sa.Boolean(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submission_digest", sa.CHAR(64), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="provenance",
)

agent_table = sa.Table(
    "agent",
    metadata,
    *_scope_columns(),
    sa.Column("id", uuid_type, nullable=False),
    sa.Column("agent_type", sa.String(32), nullable=False),
    sa.Column("reference_id", uuid_type, nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_by", uuid_type, nullable=False),
    sa.Column("request_id", uuid_type, nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="provenance",
)


def _relation_table(name: str, *columns: sa.Column[Any]) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        *_scope_columns(),
        *columns,
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", uuid_type, nullable=False),
        schema="provenance",
    )


usage_table = _relation_table(
    "usage",
    sa.Column("activity_id", uuid_type, nullable=False),
    sa.Column("entity_id", uuid_type, nullable=False),
    sa.Column("role", sa.String(100), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
)
generation_table = _relation_table(
    "generation",
    sa.Column("entity_id", uuid_type, nullable=False),
    sa.Column("activity_id", uuid_type, nullable=False),
    sa.Column("role", sa.String(100), nullable=False),
    sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
)
derivation_table = _relation_table(
    "derivation",
    sa.Column("generated_entity_id", uuid_type, nullable=False),
    sa.Column("used_entity_id", uuid_type, nullable=False),
    sa.Column("activity_id", uuid_type, nullable=True),
    sa.Column("derivation_kind", sa.String(100), nullable=False),
)
association_table = _relation_table(
    "association",
    sa.Column("activity_id", uuid_type, nullable=False),
    sa.Column("agent_id", uuid_type, nullable=False),
    sa.Column("role", sa.String(100), nullable=False),
    sa.Column("plan_entity_id", uuid_type, nullable=True),
)
revision_table = _relation_table(
    "revision",
    sa.Column("newer_entity_id", uuid_type, nullable=False),
    sa.Column("prior_entity_id", uuid_type, nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
)
attribution_table = _relation_table(
    "attribution",
    sa.Column("entity_id", uuid_type, nullable=False),
    sa.Column("agent_id", uuid_type, nullable=False),
    sa.Column("role", sa.String(100), nullable=False),
)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _scope_values(scope: ProvenanceScope) -> dict[str, object]:
    return {
        "organization_id": scope.organization_id,
        "project_id": scope.project_id,
        "classification": scope.classification.value,
    }


def _entity(row: RowMapping) -> ProvenanceEntity:
    scope = ProvenanceScope(
        organization_id=cast(UUID, row["organization_id"]),
        project_id=cast(UUID, row["project_id"]),
        classification=DataClassification(str(row["classification"])),
    )
    reference = ImmutableEntityReference(
        kind=EntityReferenceKind(str(row["reference_kind"])),
        reference_type=str(row["reference_type"]),
        reference_id=cast(UUID, row["reference_id"]),
        content_sha256=str(row["content_sha256"]),
    )
    return ProvenanceEntity(
        id=cast(UUID, row["id"]),
        scope=scope,
        entity_type=str(row["entity_type"]),
        reference=reference,
        generation_requirement=GenerationRequirement(str(row["generation_requirement"])),
        created_at=row["created_at"],
        recorded_at=row["recorded_at"],
        recorded_by=cast(UUID, row["recorded_by"]),
    )


def _activity(row: RowMapping) -> ProvenanceActivity:
    return ProvenanceActivity(
        id=cast(UUID, row["id"]),
        scope=ProvenanceScope(
            organization_id=cast(UUID, row["organization_id"]),
            project_id=cast(UUID, row["project_id"]),
            classification=DataClassification(str(row["classification"])),
        ),
        activity_type=str(row["activity_type"]),
        domain_run_type=str(row["domain_run_type"]),
        domain_run_id=cast(UUID, row["domain_run_id"]),
        status=ActivityStatus(str(row["status"])),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        submission_digest=str(row["submission_digest"]),
        recorded_at=row["recorded_at"],
        recorded_by=cast(UUID, row["recorded_by"]),
    )


def _entity_values(
    entity: ProvenanceEntity,
    *,
    request_id: UUID,
    trace_id: str,
) -> dict[str, object]:
    return {
        **_scope_values(entity.scope),
        "id": entity.id,
        "entity_type": entity.entity_type,
        "reference_kind": entity.reference.kind.value,
        "reference_type": entity.reference.reference_type,
        "reference_id": entity.reference.reference_id,
        "content_sha256": entity.reference.content_sha256,
        "generation_requirement": entity.generation_requirement.value,
        "created_at": entity.created_at,
        "recorded_at": entity.recorded_at,
        "recorded_by": entity.recorded_by,
        "request_id": request_id,
        "trace_id": trace_id,
    }


def _agent_values(
    agent: ProvenanceAgent,
    *,
    request_id: UUID,
    trace_id: str,
) -> dict[str, object]:
    return {
        **_scope_values(agent.scope),
        "id": agent.id,
        "agent_type": agent.reference.agent_type.value,
        "reference_id": agent.reference.reference_id,
        "recorded_at": agent.recorded_at,
        "recorded_by": agent.recorded_by,
        "request_id": request_id,
        "trace_id": trace_id,
    }


def _relation_values(
    scope: ProvenanceScope,
    *,
    recorded_at: datetime,
    recorded_by: UUID,
) -> dict[str, object]:
    return {
        **_scope_values(scope),
        "recorded_at": recorded_at,
        "recorded_by": recorded_by,
    }


class SqlAlchemyProvenanceRepository:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context

    def _bind(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @staticmethod
    def _find_entity(
        session: Session,
        scope: ProvenanceScope,
        reference: ImmutableEntityReference,
    ) -> ProvenanceEntity | None:
        row = (
            session.execute(
                sa.select(entity_table).where(
                    entity_table.c.organization_id == scope.organization_id,
                    entity_table.c.project_id == scope.project_id,
                    entity_table.c.reference_kind == reference.kind.value,
                    entity_table.c.reference_type == reference.reference_type,
                    entity_table.c.reference_id == reference.reference_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        return _entity(row) if row is not None else None

    @staticmethod
    def _ensure_entity(
        session: Session,
        candidate: ProvenanceEntity,
        *,
        request_id: UUID,
        trace_id: str,
    ) -> ProvenanceEntity:
        existing = SqlAlchemyProvenanceRepository._find_entity(
            session, candidate.scope, candidate.reference
        )
        if existing is not None:
            if (
                existing.entity_type != candidate.entity_type
                or existing.reference.content_sha256 != candidate.reference.content_sha256
                or existing.generation_requirement is not candidate.generation_requirement
                or existing.scope != candidate.scope
            ):
                raise ProvenanceConflict(
                    "immutable Entity reference was already registered with different facts"
                )
            return existing
        session.execute(
            sa.insert(entity_table).values(
                _entity_values(candidate, request_id=request_id, trace_id=trace_id)
            )
        )
        return candidate

    @staticmethod
    def _ensure_agent(
        session: Session,
        candidate: ProvenanceAgent,
        *,
        request_id: UUID,
        trace_id: str,
    ) -> ProvenanceAgent:
        row = (
            session.execute(
                sa.select(agent_table).where(
                    agent_table.c.organization_id == candidate.scope.organization_id,
                    agent_table.c.project_id == candidate.scope.project_id,
                    agent_table.c.classification == candidate.scope.classification.value,
                    agent_table.c.agent_type == candidate.reference.agent_type.value,
                    agent_table.c.reference_id == candidate.reference.reference_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return ProvenanceAgent(
                id=cast(UUID, row["id"]),
                scope=candidate.scope,
                reference=candidate.reference,
                recorded_at=row["recorded_at"],
                recorded_by=cast(UUID, row["recorded_by"]),
            )
        session.execute(
            sa.insert(agent_table).values(
                _agent_values(candidate, request_id=request_id, trace_id=trace_id)
            )
        )
        return candidate

    @staticmethod
    def _replayed_result(session: Session, activity: ProvenanceActivity) -> ActivityCommitResult:
        input_ids = tuple(
            cast(UUID, value)
            for value in session.scalars(
                sa.select(usage_table.c.entity_id)
                .where(
                    usage_table.c.organization_id == activity.scope.organization_id,
                    usage_table.c.project_id == activity.scope.project_id,
                    usage_table.c.activity_id == activity.id,
                )
                .order_by(usage_table.c.ordinal, usage_table.c.entity_id)
            )
        )
        output_ids = tuple(
            cast(UUID, value)
            for value in session.scalars(
                sa.select(generation_table.c.entity_id)
                .where(
                    generation_table.c.organization_id == activity.scope.organization_id,
                    generation_table.c.project_id == activity.scope.project_id,
                    generation_table.c.activity_id == activity.id,
                )
                .order_by(generation_table.c.entity_id)
            )
        )
        agent_ids = tuple(
            cast(UUID, value)
            for value in session.scalars(
                sa.select(association_table.c.agent_id)
                .where(
                    association_table.c.organization_id == activity.scope.organization_id,
                    association_table.c.project_id == activity.scope.project_id,
                    association_table.c.activity_id == activity.id,
                )
                .order_by(association_table.c.agent_id)
            )
        )
        return ActivityCommitResult(activity, input_ids, output_ids, agent_ids, True)

    def commit_activity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        commit: ResolvedActivityCommit,
    ) -> ActivityCommitResult:
        try:
            with self._sessions() as session, session.begin():
                self._bind(session, context, decision)
                activity = commit.activity
                existing_row = (
                    session.execute(
                        sa.select(activity_table).where(
                            activity_table.c.organization_id == activity.scope.organization_id,
                            activity_table.c.project_id == activity.scope.project_id,
                            activity_table.c.domain_run_type == activity.domain_run_type,
                            activity_table.c.domain_run_id == activity.domain_run_id,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing_row is not None:
                    existing = _activity(existing_row)
                    if existing.submission_digest != activity.submission_digest:
                        raise ProvenanceConflict(
                            "domain run identity was already committed with another graph"
                        )
                    return self._replayed_result(session, existing)

                entity_by_reference = {
                    item.reference: self._ensure_entity(
                        session,
                        item,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                    )
                    for item in commit.entities
                }
                agent_by_reference = {
                    item.reference: self._ensure_agent(
                        session,
                        item,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                    )
                    for item in commit.agents
                }
                session.execute(
                    sa.insert(activity_table).values(
                        **_scope_values(activity.scope),
                        id=activity.id,
                        activity_type=activity.activity_type,
                        domain_run_type=activity.domain_run_type,
                        domain_run_id=activity.domain_run_id,
                        status=activity.status.value,
                        input_required=True,
                        output_required=activity.status is ActivityStatus.SUCCEEDED,
                        started_at=activity.started_at,
                        ended_at=activity.ended_at,
                        submission_digest=activity.submission_digest,
                        recorded_at=activity.recorded_at,
                        recorded_by=activity.recorded_by,
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                    )
                )
                relation_base = _relation_values(
                    activity.scope,
                    recorded_at=activity.recorded_at,
                    recorded_by=activity.recorded_by,
                )
                for item in commit.command.inputs:
                    session.execute(
                        sa.insert(usage_table).values(
                            **relation_base,
                            activity_id=activity.id,
                            entity_id=entity_by_reference[item.entity].id,
                            role=item.role,
                            ordinal=item.ordinal,
                        )
                    )
                for association in commit.command.agents:
                    plan_id = (
                        entity_by_reference[association.plan_entity].id
                        if association.plan_entity is not None
                        else None
                    )
                    session.execute(
                        sa.insert(association_table).values(
                            **relation_base,
                            activity_id=activity.id,
                            agent_id=agent_by_reference[association.agent].id,
                            role=association.role,
                            plan_entity_id=plan_id,
                        )
                    )
                for output in commit.command.outputs:
                    output_id = entity_by_reference[output.entity].id
                    session.execute(
                        sa.insert(generation_table).values(
                            **relation_base,
                            entity_id=output_id,
                            activity_id=activity.id,
                            role=output.role,
                            generated_at=activity.ended_at,
                        )
                    )
                    for derivation in output.derivations:
                        session.execute(
                            sa.insert(derivation_table).values(
                                **relation_base,
                                generated_entity_id=output_id,
                                used_entity_id=entity_by_reference[derivation.entity].id,
                                activity_id=activity.id,
                                derivation_kind=derivation.kind,
                            )
                        )
                return ActivityCommitResult(
                    activity=activity,
                    input_entity_ids=tuple(
                        entity_by_reference[item.entity].id for item in commit.command.inputs
                    ),
                    output_entity_ids=tuple(
                        entity_by_reference[item.entity].id for item in commit.command.outputs
                    ),
                    agent_ids=tuple(
                        agent_by_reference[item.agent].id for item in commit.command.agents
                    ),
                    replayed=False,
                )
        except ProvenanceConflict:
            raise
        except (IntegrityError, DBAPIError) as error:
            raise ProvenanceConflict("database rejected the provenance graph") from error

    def get_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        entity_id: UUID,
    ) -> ProvenanceRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(
                        entity_table,
                        generation_table.c.activity_id.label("generation_activity_id"),
                    )
                    .outerjoin(
                        generation_table,
                        sa.and_(
                            generation_table.c.organization_id == entity_table.c.organization_id,
                            generation_table.c.project_id == entity_table.c.project_id,
                            generation_table.c.entity_id == entity_table.c.id,
                        ),
                    )
                    .where(entity_table.c.id == entity_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProvenanceNotFound(str(entity_id))
            entity = _entity(row)
            generation_id = cast(UUID | None, row["generation_activity_id"])
            issues = (
                ("missing_primary_generation",)
                if entity.generation_requirement is GenerationRequirement.PRIMARY
                and generation_id is None
                else ()
            )
            completeness = EntityCompleteness(
                state=(CompletenessState.INCOMPLETE if issues else CompletenessState.COMPLETE),
                issues=issues,
            )
            return ProvenanceRecord(entity, generation_id, completeness)

    def find_entity_by_reference(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference_type: str,
        reference_id: UUID,
    ) -> ProvenanceRecord:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            row = (
                session.execute(
                    sa.select(
                        entity_table,
                        generation_table.c.activity_id.label("generation_activity_id"),
                    )
                    .outerjoin(
                        generation_table,
                        sa.and_(
                            generation_table.c.organization_id == entity_table.c.organization_id,
                            generation_table.c.project_id == entity_table.c.project_id,
                            generation_table.c.entity_id == entity_table.c.id,
                        ),
                    )
                    .where(
                        entity_table.c.reference_type == reference_type,
                        entity_table.c.reference_id == reference_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProvenanceNotFound(f"{reference_type}:{reference_id}")
            entity = _entity(row)
            generation_id = cast(UUID | None, row["generation_activity_id"])
            issues = (
                ("missing_primary_generation",)
                if entity.generation_requirement is GenerationRequirement.PRIMARY
                and generation_id is None
                else ()
            )
            completeness = EntityCompleteness(
                state=(CompletenessState.INCOMPLETE if issues else CompletenessState.COMPLETE),
                issues=issues,
            )
            return ProvenanceRecord(entity, generation_id, completeness)

    def load_lineage_graph(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
        direction: LineageDirection,
        max_depth: int,
        max_nodes: int,
    ) -> LineageGraph:
        if direction is LineageDirection.UPSTREAM:
            frontier_column = "edge.child_entity_id"
            next_id = "edge.parent_entity_id"
        else:
            frontier_column = "edge.parent_entity_id"
            next_id = "edge.child_entity_id"
        query = sa.text(
            f"""
            WITH RECURSIVE levels(
              depth, frontier, visited, node_truncated
            ) AS (
              SELECT
                0,
                ARRAY[CAST(:root_entity_id AS uuid)],
                ARRAY[CAST(:root_entity_id AS uuid)],
                false
              UNION ALL
              SELECT
                levels.depth + 1,
                expansion.frontier,
                levels.visited || expansion.frontier,
                expansion.node_truncated
              FROM levels
              CROSS JOIN LATERAL (
                SELECT
                  COALESCE(
                    (array_agg(candidate.entity_id ORDER BY candidate.entity_id))[
                      1:GREATEST(:max_nodes - cardinality(levels.visited), 0)
                    ],
                    ARRAY[]::uuid[]
                  ) AS frontier,
                  count(*) > GREATEST(
                    :max_nodes - cardinality(levels.visited), 0
                  ) AS node_truncated
                FROM (
                  SELECT DISTINCT {next_id} AS entity_id
                  FROM provenance.dependency_edge AS edge
                  WHERE edge.organization_id = :organization_id
                    AND edge.project_id = :project_id
                    AND {frontier_column} = ANY(levels.frontier)
                    AND NOT ({next_id} = ANY(levels.visited))
                  ORDER BY entity_id
                  LIMIT GREATEST(
                    :max_nodes - cardinality(levels.visited) + 1, 1
                  )
                ) AS candidate
              ) AS expansion
              WHERE levels.depth < :max_depth
                AND cardinality(levels.frontier) > 0
                AND NOT levels.node_truncated
            ), ranked AS (
              SELECT entity_id, levels.depth
              FROM levels
              CROSS JOIN LATERAL unnest(levels.frontier) AS entity_id
            )
            SELECT
              ranked.entity_id,
              ranked.depth,
              EXISTS (
                SELECT 1 FROM levels WHERE levels.node_truncated
              ) AS node_truncated
            FROM ranked
            ORDER BY ranked.depth, ranked.entity_id
            """
        )
        entity_query = sa.text(
            """
            SELECT
              entity.*,
              generation.activity_id AS generation_activity_id,
              (
                entity.generation_requirement = 'none'
                OR generation.activity_id IS NOT NULL
              ) AS generation_complete
            FROM provenance.entity AS entity
            LEFT JOIN provenance.generation AS generation
              ON generation.organization_id = entity.organization_id
             AND generation.project_id = entity.project_id
             AND generation.classification = entity.classification
             AND generation.entity_id = entity.id
            WHERE entity.organization_id = :organization_id
              AND entity.project_id = :project_id
              AND entity.id = ANY(CAST(:entity_ids AS uuid[]))
            ORDER BY entity.id
            """
        )
        try:
            with self._sessions() as session, session.begin():
                self._bind(session, context, decision)
                rows = (
                    session.execute(
                        query,
                        {
                            "root_entity_id": root_entity_id,
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "max_depth": max_depth,
                            "max_nodes": max_nodes,
                        },
                    )
                    .mappings()
                    .all()
                )
                if not rows:
                    raise ProvenanceNotFound(str(root_entity_id))
                depths = {cast(UUID, row["entity_id"]): int(row["depth"]) for row in rows}
                identifiers = list(depths)
                entity_rows = (
                    session.execute(
                        entity_query,
                        {
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "entity_ids": identifiers,
                        },
                    )
                    .mappings()
                    .all()
                )
                vertices: list[LineageVertex] = []
                for row in entity_rows:
                    entity = _entity(row)
                    generation_id = cast(UUID | None, row["generation_activity_id"])
                    complete = bool(row["generation_complete"])
                    vertices.append(
                        LineageVertex(
                            ProvenanceRecord(
                                entity,
                                generation_id,
                                EntityCompleteness(
                                    CompletenessState.COMPLETE
                                    if complete
                                    else CompletenessState.INCOMPLETE,
                                    () if complete else ("missing_primary_generation",),
                                ),
                            ),
                            depths[entity.id],
                        )
                    )
                vertices.sort(key=lambda vertex: (vertex.depth, str(vertex.record.entity.id)))
                if not vertices or vertices[0].record.entity.id != root_entity_id:
                    raise ProvenanceNotFound(str(root_entity_id))
                edge_query = sa.text(
                    """
                    SELECT DISTINCT
                      child_entity_id, parent_entity_id, relation, activity_id
                    FROM provenance.dependency_edge
                    WHERE organization_id = :organization_id
                      AND project_id = :project_id
                      AND child_entity_id = ANY(CAST(:entity_ids AS uuid[]))
                      AND parent_entity_id = ANY(CAST(:entity_ids AS uuid[]))
                    ORDER BY child_entity_id, parent_entity_id, relation
                    """
                )
                edge_rows = (
                    session.execute(
                        edge_query,
                        {
                            "organization_id": context.organization_id,
                            "project_id": context.project_id,
                            "entity_ids": identifiers,
                        },
                    )
                    .mappings()
                    .all()
                )
                edges = tuple(
                    DependencyEdge(
                        child_entity_id=cast(UUID, row["child_entity_id"]),
                        parent_entity_id=cast(UUID, row["parent_entity_id"]),
                        relation=LineageRelation(str(row["relation"])),
                        activity_id=cast(UUID | None, row["activity_id"]),
                    )
                    for row in edge_rows
                )
                node_truncated = bool(rows[0]["node_truncated"])
                depth_truncated = False
                boundary_ids = [
                    vertex.record.entity.id for vertex in vertices if vertex.depth == max_depth
                ]
                if not node_truncated and boundary_ids:
                    if direction is LineageDirection.UPSTREAM:
                        boundary_column = "child_entity_id"
                        unseen_column = "parent_entity_id"
                    else:
                        boundary_column = "parent_entity_id"
                        unseen_column = "child_entity_id"
                    boundary_query = sa.text(
                        f"""
                        SELECT EXISTS (
                          SELECT 1
                          FROM provenance.dependency_edge
                          WHERE organization_id = :organization_id
                            AND project_id = :project_id
                            AND {boundary_column} = ANY(
                              CAST(:boundary_ids AS uuid[])
                            )
                            AND NOT ({unseen_column} = ANY(
                              CAST(:known_ids AS uuid[])
                            ))
                        )
                        """
                    )
                    depth_truncated = bool(
                        session.scalar(
                            boundary_query,
                            {
                                "organization_id": context.organization_id,
                                "project_id": context.project_id,
                                "boundary_ids": boundary_ids,
                                "known_ids": identifiers,
                            },
                        )
                    )
                return LineageGraph(
                    root_entity_id=root_entity_id,
                    direction=direction,
                    vertices=tuple(vertices),
                    edges=edges,
                    truncated=node_truncated or depth_truncated,
                )
        except ProvenanceNotFound:
            raise
        except DBAPIError as error:
            raise ProvenanceConflict("database rejected the bounded lineage query") from error

    def activity_completeness_issues(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        activity_ids: tuple[UUID, ...],
    ) -> tuple[CompletenessIssue, ...]:
        if not activity_ids:
            return ()
        query = sa.text(
            """
            SELECT activity_id, input_complete, agent_complete, output_complete
            FROM provenance.activity_completeness
            WHERE organization_id = :organization_id
              AND project_id = :project_id
              AND activity_id = ANY(CAST(:activity_ids AS uuid[]))
            ORDER BY activity_id
            """
        )
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            rows = (
                session.execute(
                    query,
                    {
                        "organization_id": context.organization_id,
                        "project_id": context.project_id,
                        "activity_ids": list(activity_ids),
                    },
                )
                .mappings()
                .all()
            )
            issues: list[CompletenessIssue] = []
            for row in rows:
                activity_id = cast(UUID, row["activity_id"])
                if not bool(row["input_complete"]):
                    issues.append(
                        CompletenessIssue(
                            CompletenessIssueCode.MISSING_ACTIVITY_INPUT,
                            activity_id=activity_id,
                        )
                    )
                if not bool(row["agent_complete"]):
                    issues.append(
                        CompletenessIssue(
                            CompletenessIssueCode.MISSING_ACTIVITY_AGENT,
                            activity_id=activity_id,
                        )
                    )
                if not bool(row["output_complete"]):
                    issues.append(
                        CompletenessIssue(
                            CompletenessIssueCode.MISSING_ACTIVITY_OUTPUT,
                            activity_id=activity_id,
                        )
                    )
            return tuple(issues)


class SqlAlchemySchemaBundleProvenanceWriter:
    """Attach exact bundle Artifact lineage inside a caller-owned transaction."""

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    @staticmethod
    def _actor_type(session: Session) -> AgentType:
        principal_type = session.scalar(
            sa.text("SELECT current_setting('cmp.principal_type', true)")
        )
        if principal_type not in {"user", "service"}:
            raise ProvenanceConflict("Schema Bundle apply actor type is unavailable")
        return AgentType(str(principal_type))

    def ensure_source(
        self,
        session: Session,
        *,
        context: SecurityContext,
        classification: DataClassification,
        artifact_id: UUID,
        artifact_sha256: str,
        artifact_created_at: datetime,
        recorded_at: datetime,
    ) -> UUID:
        scope = ProvenanceScope(
            context.organization_id,
            context.project_id,
            classification,
        )
        existing = session.scalar(
            sa.select(entity_table.c.id).where(
                entity_table.c.organization_id == context.organization_id,
                entity_table.c.project_id == context.project_id,
                entity_table.c.classification == classification.value,
                entity_table.c.reference_kind == EntityReferenceKind.ARTIFACT.value,
                entity_table.c.reference_type == "artifact.artifact",
                entity_table.c.reference_id == artifact_id,
                entity_table.c.content_sha256 == artifact_sha256,
            )
        )
        if existing is not None:
            return cast(UUID, existing)

        agent = SqlAlchemyProvenanceRepository._ensure_agent(
            session,
            ProvenanceAgent(
                id=self._id_factory(),
                scope=scope,
                reference=AgentReference(self._actor_type(session), context.principal.id),
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        entity = SqlAlchemyProvenanceRepository._ensure_entity(
            session,
            ProvenanceEntity(
                id=self._id_factory(),
                scope=scope,
                entity_type="catalog.schema_definition_bundle_source",
                reference=ImmutableEntityReference(
                    EntityReferenceKind.ARTIFACT,
                    "artifact.artifact",
                    artifact_id,
                    artifact_sha256,
                ),
                generation_requirement=GenerationRequirement.PRIMARY,
                created_at=artifact_created_at,
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        activity_id = self._id_factory()
        relation_values = _relation_values(
            scope,
            recorded_at=recorded_at,
            recorded_by=context.principal.id,
        )
        session.execute(
            sa.insert(activity_table).values(
                **_scope_values(scope),
                id=activity_id,
                activity_type="catalog.schema_bundle_source_registration",
                domain_run_type="catalog.schema_bundle_source_registration",
                domain_run_id=artifact_id,
                status=ActivityStatus.SUCCEEDED.value,
                input_required=False,
                output_required=True,
                started_at=recorded_at,
                ended_at=recorded_at,
                submission_digest=content_sha256(
                    {
                        "artifact_id": str(artifact_id),
                        "artifact_sha256": artifact_sha256,
                    }
                ),
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        session.execute(
            sa.insert(association_table).values(
                **relation_values,
                activity_id=activity_id,
                agent_id=agent.id,
                role="registrar",
                plan_entity_id=None,
            )
        )
        session.execute(
            sa.insert(generation_table).values(
                **relation_values,
                entity_id=entity.id,
                activity_id=activity_id,
                role="primary",
                generated_at=recorded_at,
            )
        )
        session.execute(
            sa.insert(attribution_table).values(
                **relation_values,
                entity_id=entity.id,
                agent_id=agent.id,
                role="registrar",
            )
        )
        return entity.id

    @staticmethod
    def attach_source(
        session: Session,
        *,
        source_entity_id: UUID,
        revision: RevisionRecord,
    ) -> None:
        generated_entity_id = session.scalar(
            sa.select(entity_table.c.id).where(
                entity_table.c.organization_id == revision.scope.organization_id,
                entity_table.c.project_id == revision.scope.project_id,
                entity_table.c.classification == revision.scope.classification,
                entity_table.c.reference_kind == EntityReferenceKind.REVISION.value,
                entity_table.c.reference_type == f"{revision.aggregate_type}.revision",
                entity_table.c.reference_id == revision.revision_id,
            )
        )
        if generated_entity_id is None:
            raise ProvenanceConflict("generated Catalog revision provenance Entity is missing")
        activity_id = session.scalar(
            sa.select(generation_table.c.activity_id).where(
                generation_table.c.organization_id == revision.scope.organization_id,
                generation_table.c.project_id == revision.scope.project_id,
                generation_table.c.classification == revision.scope.classification,
                generation_table.c.entity_id == generated_entity_id,
            )
        )
        if activity_id is None:
            raise ProvenanceConflict("generated Catalog revision provenance Activity is missing")
        values = {
            "organization_id": revision.scope.organization_id,
            "project_id": revision.scope.project_id,
            "classification": revision.scope.classification,
            "recorded_at": revision.created_at,
            "recorded_by": revision.created_by,
        }
        session.execute(
            sa.insert(usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=source_entity_id,
                role="schema_definition_bundle",
                ordinal=1 if revision.based_on_revision_id is not None else 0,
            )
        )
        session.execute(
            sa.insert(derivation_table).values(
                **values,
                generated_entity_id=generated_entity_id,
                used_entity_id=source_entity_id,
                activity_id=activity_id,
                derivation_kind="schema_definition_bundle_projection",
            )
        )


class SqlAlchemyRevisionProvenanceHook:
    """T-06 hook that writes revision provenance in the caller's transaction.

    The owning revision repository must bind ``provenance.read``/``provenance.write`` and
    principal RLS context on the supplied session before this hook runs.
    """

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        scope = ProvenanceScope(
            revision.scope.organization_id,
            revision.scope.project_id,
            DataClassification(revision.scope.classification),
        )
        reference_type = f"{revision.aggregate_type}.revision"
        recorded_at = revision.created_at
        relation_base = _relation_values(
            scope, recorded_at=recorded_at, recorded_by=revision.created_by
        )
        principal_type = session.scalar(
            sa.text("SELECT principal_type FROM identity.principal WHERE id = :principal_id"),
            {"principal_id": revision.created_by},
        )
        if principal_type not in {"user", "service"}:
            raise ProvenanceConflict("revision creator is not an active provenance Agent")

        agent_candidate = ProvenanceAgent(
            id=self._id_factory(),
            scope=scope,
            reference=AgentReference(AgentType(str(principal_type)), revision.created_by),
            recorded_at=recorded_at,
            recorded_by=revision.created_by,
        )
        agent = SqlAlchemyProvenanceRepository._ensure_agent(
            session,
            agent_candidate,
            request_id=revision.request_id,
            trace_id=revision.trace_id,
        )
        entity_candidate = ProvenanceEntity(
            id=self._id_factory(),
            scope=scope,
            entity_type=reference_type,
            reference=ImmutableEntityReference(
                EntityReferenceKind.REVISION,
                reference_type,
                revision.revision_id,
                revision.content_hash,
            ),
            generation_requirement=GenerationRequirement.PRIMARY,
            created_at=recorded_at,
            recorded_at=recorded_at,
            recorded_by=revision.created_by,
        )
        entity = SqlAlchemyProvenanceRepository._ensure_entity(
            session,
            entity_candidate,
            request_id=revision.request_id,
            trace_id=revision.trace_id,
        )
        prior_entity: ProvenanceEntity | None = None
        if revision.based_on_revision_id is not None:
            prior_row = (
                session.execute(
                    sa.select(entity_table).where(
                        entity_table.c.organization_id == scope.organization_id,
                        entity_table.c.project_id == scope.project_id,
                        entity_table.c.reference_kind == EntityReferenceKind.REVISION.value,
                        entity_table.c.reference_type == reference_type,
                        entity_table.c.reference_id == revision.based_on_revision_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if prior_row is None:
                raise ProvenanceConflict("prior immutable revision is missing from provenance")
            prior_entity = _entity(prior_row)

        submission_digest = content_sha256(
            {
                "hook": "t13.revision",
                "revision_id": str(revision.revision_id),
                "prior_revision_id": (
                    str(revision.based_on_revision_id)
                    if revision.based_on_revision_id is not None
                    else None
                ),
                "content_sha256": revision.content_hash,
                "change_reason": revision.change_reason,
            }
        )
        activity_id = self._id_factory()
        session.execute(
            sa.insert(activity_table).values(
                **_scope_values(scope),
                id=activity_id,
                activity_type="core.revision_commit",
                domain_run_type="core.revision_commit",
                domain_run_id=revision.revision_id,
                status=ActivityStatus.SUCCEEDED.value,
                input_required=prior_entity is not None,
                output_required=True,
                started_at=recorded_at,
                ended_at=recorded_at,
                submission_digest=submission_digest,
                recorded_at=recorded_at,
                recorded_by=revision.created_by,
                request_id=revision.request_id,
                trace_id=revision.trace_id,
            )
        )
        if prior_entity is not None:
            session.execute(
                sa.insert(usage_table).values(
                    **relation_base,
                    activity_id=activity_id,
                    entity_id=prior_entity.id,
                    role="prior_revision",
                    ordinal=0,
                )
            )
        session.execute(
            sa.insert(association_table).values(
                **relation_base,
                activity_id=activity_id,
                agent_id=agent.id,
                role="author",
                plan_entity_id=None,
            )
        )
        session.execute(
            sa.insert(generation_table).values(
                **relation_base,
                entity_id=entity.id,
                activity_id=activity_id,
                role="primary",
                generated_at=recorded_at,
            )
        )
        session.execute(
            sa.insert(attribution_table).values(
                **relation_base,
                entity_id=entity.id,
                agent_id=agent.id,
                role="author",
            )
        )
        if prior_entity is not None:
            session.execute(
                sa.insert(revision_table).values(
                    **relation_base,
                    newer_entity_id=entity.id,
                    prior_entity_id=prior_entity.id,
                    change_reason=revision.change_reason,
                )
            )
