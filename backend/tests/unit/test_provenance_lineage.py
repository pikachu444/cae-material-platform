from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
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
from cmp.modules.provenance.application.lineage import (
    LineagePolicy,
    ProvenanceLineageService,
)
from cmp.modules.provenance.domain.lineage import (
    CompletenessIssue,
    CompletenessReportState,
    DependencyEdge,
    LineageDirection,
    LineageGraph,
    LineageRelation,
    LineageVertex,
)
from cmp.modules.provenance.domain.model import (
    CompletenessState,
    EntityCompleteness,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceEntity,
    ProvenanceRecord,
    ProvenanceScope,
)

NOW = datetime(2026, 7, 13, 13, 0, tzinfo=UTC)
ORG = UUID("92000000-0000-4000-8000-000000000001")
PROJECT = UUID("92000000-0000-4000-8000-000000000002")
ACTOR = UUID("92000000-0000-4000-8000-000000000003")
ROOT = UUID("92000000-0000-4000-8000-000000000004")
LEFT = UUID("92000000-0000-4000-8000-000000000010")
RIGHT = UUID("92000000-0000-4000-8000-000000000020")
SOURCE = UUID("92000000-0000-4000-8000-000000000030")
TRACE = "00-00000000000000000000000000000092-0000000000000092-01"
SCOPE = ProvenanceScope(ORG, PROJECT, DataClassification.INTERNAL)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Lineage Reader", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=UUID("92000000-0000-4000-8000-000000000040"),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(context: SecurityContext) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.PROVENANCE_READ,
        roles=(Role.AUDITOR,),
        database_permissions=database_permissions_for(Permission.PROVENANCE_READ),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


def _record(
    entity_id: UUID,
    *,
    source: bool = False,
    complete: bool = True,
    entity_type: str = "synthetic.dataset_revision",
) -> ProvenanceRecord:
    reference_kind = EntityReferenceKind.RAW_ASSET if source else EntityReferenceKind.REVISION
    reference_type = "artifact.raw_asset" if source else entity_type
    generation_requirement = GenerationRequirement.NONE if source else GenerationRequirement.PRIMARY
    entity = ProvenanceEntity(
        id=entity_id,
        scope=SCOPE,
        entity_type=reference_type,
        reference=ImmutableEntityReference(
            reference_kind,
            reference_type,
            uuid4(),
            hashlib.sha256(entity_id.bytes).hexdigest(),
        ),
        generation_requirement=generation_requirement,
        created_at=NOW,
        recorded_at=NOW,
        recorded_by=ACTOR,
    )
    return ProvenanceRecord(
        entity,
        None if source or not complete else uuid4(),
        EntityCompleteness(
            CompletenessState.COMPLETE if complete else CompletenessState.INCOMPLETE,
            () if complete else ("missing_primary_generation",),
        ),
    )


def _diamond(direction: LineageDirection = LineageDirection.UPSTREAM) -> LineageGraph:
    activity = uuid4()
    return LineageGraph(
        root_entity_id=ROOT,
        direction=direction,
        vertices=(
            LineageVertex(_record(ROOT), 0),
            LineageVertex(_record(LEFT), 1),
            LineageVertex(_record(RIGHT), 1),
            LineageVertex(_record(SOURCE, source=True), 2),
        ),
        edges=(
            DependencyEdge(ROOT, LEFT, LineageRelation.USAGE_GENERATION, activity),
            DependencyEdge(ROOT, RIGHT, LineageRelation.DERIVATION, activity),
            DependencyEdge(LEFT, SOURCE, LineageRelation.DERIVATION, activity),
            DependencyEdge(RIGHT, SOURCE, LineageRelation.DERIVATION, activity),
        ),
        truncated=False,
    )


def _downstream_diamond() -> LineageGraph:
    upstream = _diamond()
    return LineageGraph(
        root_entity_id=SOURCE,
        direction=LineageDirection.DOWNSTREAM,
        vertices=(
            LineageVertex(_record(SOURCE, source=True), 0),
            LineageVertex(_record(LEFT), 1),
            LineageVertex(_record(RIGHT), 1),
            LineageVertex(_record(ROOT), 2),
        ),
        edges=upstream.edges,
        truncated=False,
    )


class _Repository:
    def __init__(
        self,
        graph: LineageGraph,
        issues: tuple[CompletenessIssue, ...] = (),
    ) -> None:
        self.graph = graph
        self.issues = issues

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
        del context, decision, max_depth, max_nodes
        assert root_entity_id == self.graph.root_entity_id
        return LineageGraph(
            root_entity_id=self.graph.root_entity_id,
            direction=direction,
            vertices=self.graph.vertices,
            edges=self.graph.edges,
            truncated=self.graph.truncated,
        )

    def activity_completeness_issues(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        activity_ids: tuple[UUID, ...],
    ) -> tuple[CompletenessIssue, ...]:
        del context, decision, activity_ids
        return self.issues


def test_diamond_paths_are_unique_deterministic_and_cursor_paginated() -> None:
    context = _context()
    service = ProvenanceLineageService(repository=_Repository(_diamond()))
    decision = _decision(context)

    first = service.query(
        context,
        decision,
        ROOT,
        direction=LineageDirection.UPSTREAM,
        limit=2,
    )
    assert [node.record.entity.id for node in first.nodes] == [ROOT, LEFT]
    assert first.next_cursor is not None
    assert first.total_discovered == 4

    second = service.query(
        context,
        decision,
        ROOT,
        direction=LineageDirection.UPSTREAM,
        limit=2,
        cursor=first.next_cursor,
    )
    assert [node.record.entity.id for node in second.nodes] == [RIGHT, SOURCE]
    assert second.nodes[-1].path == (ROOT, LEFT, SOURCE)
    assert second.next_cursor is None
    assert second.total_discovered == 4

    with pytest.raises(ValueError, match="another query"):
        service.query(
            context,
            decision,
            ROOT,
            direction=LineageDirection.DOWNSTREAM,
            cursor=first.next_cursor,
        )


def test_target_type_filter_and_impact_use_bounded_downstream_query() -> None:
    context = _context()
    graph = _downstream_diamond()
    service = ProvenanceLineageService(repository=_Repository(graph))

    page = service.impact(
        context,
        _decision(context),
        SOURCE,
        target_entity_type="synthetic.dataset_revision",
    )

    assert page.direction is LineageDirection.DOWNSTREAM
    assert all(
        node.record.entity.entity_type == "synthetic.dataset_revision" for node in page.nodes
    )


def test_completeness_gate_reports_complete_cycle_missing_generation_and_limit() -> None:
    context = _context()
    decision = _decision(context)
    complete = ProvenanceLineageService(repository=_Repository(_diamond())).completeness(
        context, decision, ROOT
    )
    assert complete.state is CompletenessReportState.COMPLETE
    assert complete.eligible

    cycle_graph = LineageGraph(
        root_entity_id=ROOT,
        direction=LineageDirection.UPSTREAM,
        vertices=(
            LineageVertex(_record(ROOT), 0),
            LineageVertex(_record(LEFT), 1),
        ),
        edges=(
            DependencyEdge(ROOT, LEFT, LineageRelation.DERIVATION, None),
            DependencyEdge(LEFT, ROOT, LineageRelation.DERIVATION, None),
        ),
        truncated=False,
    )
    cycle = ProvenanceLineageService(repository=_Repository(cycle_graph)).completeness(
        context, decision, ROOT
    )
    assert cycle.state is CompletenessReportState.INCOMPLETE
    assert {issue.code.value for issue in cycle.issues} >= {
        "dependency_cycle",
        "missing_source_path",
    }

    missing_graph = LineageGraph(
        ROOT,
        LineageDirection.UPSTREAM,
        (LineageVertex(_record(ROOT, complete=False), 0),),
        (),
        False,
    )
    missing = ProvenanceLineageService(repository=_Repository(missing_graph)).completeness(
        context, decision, ROOT
    )
    assert missing.state is CompletenessReportState.INCOMPLETE
    assert "missing_primary_generation" in {issue.code.value for issue in missing.issues}

    truncated_graph = LineageGraph(
        ROOT,
        LineageDirection.UPSTREAM,
        (LineageVertex(_record(ROOT), 0),),
        (),
        True,
    )
    truncated = ProvenanceLineageService(repository=_Repository(truncated_graph)).completeness(
        context, decision, ROOT
    )
    assert truncated.state is CompletenessReportState.INDETERMINATE
    assert [issue.code.value for issue in truncated.issues] == ["graph_limit_exceeded"]


def test_policy_rejects_unbounded_depth_page_and_graph_limits() -> None:
    with pytest.raises(ValueError):
        LineagePolicy(maximum_depth=0)
    with pytest.raises(ValueError):
        LineagePolicy(default_page_size=1001, maximum_page_size=1000)
    with pytest.raises(ValueError):
        LineagePolicy(maximum_page_size=1000, maximum_graph_nodes=999)
