"""T-14 bounded lineage, impact pagination, and completeness gate service."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.provenance.domain.lineage import (
    CompletenessIssue,
    CompletenessIssueCode,
    CompletenessReportState,
    LineageDirection,
    LineageGraph,
    LineageNode,
    LineagePage,
    LineageRelation,
    ProvenanceCompletenessReport,
)
from cmp.modules.provenance.domain.model import (
    CompletenessState,
    GenerationRequirement,
    ProvenanceConflict,
)
from cmp.shared.domain.revisions import canonical_json_bytes

_ENTITY_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")


@dataclass(frozen=True, slots=True)
class LineagePolicy:
    default_depth: int = 10
    maximum_depth: int = 20
    default_page_size: int = 100
    maximum_page_size: int = 1000
    maximum_graph_nodes: int = 10_000

    def __post_init__(self) -> None:
        if not 1 <= self.default_depth <= self.maximum_depth <= 100:
            raise ValueError("lineage depth policy is invalid")
        if not 1 <= self.default_page_size <= self.maximum_page_size <= 10_000:
            raise ValueError("lineage page policy is invalid")
        if not self.maximum_page_size <= self.maximum_graph_nodes <= 100_000:
            raise ValueError("lineage graph policy is invalid")


class LineageRepository(Protocol):
    def load_lineage_graph(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
        direction: LineageDirection,
        max_depth: int,
        max_nodes: int,
    ) -> LineageGraph: ...

    def activity_completeness_issues(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        activity_ids: tuple[UUID, ...],
    ) -> tuple[CompletenessIssue, ...]: ...


@dataclass(frozen=True, slots=True)
class _CursorPosition:
    depth: int
    entity_id: UUID


class LineageCursorCodec:
    """Canonical opaque cursor bound to the complete read-only query shape."""

    @staticmethod
    def issue(
        *,
        root_entity_id: UUID,
        direction: LineageDirection,
        max_depth: int,
        target_entity_type: str | None,
        position: _CursorPosition,
    ) -> str:
        payload = canonical_json_bytes(
            {
                "v": 1,
                "root": str(root_entity_id),
                "direction": direction.value,
                "max_depth": max_depth,
                "target_entity_type": target_entity_type,
                "after_depth": position.depth,
                "after_entity_id": str(position.entity_id),
            }
        )
        return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> dict[str, object]:
        if not value or len(value) > 4096 or "=" in value:
            raise ValueError("lineage cursor is not canonical")
        try:
            padded = value + "=" * (-len(value) % 4)
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
            document = json.loads(raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("lineage cursor is invalid") from error
        if not isinstance(document, dict) or canonical_json_bytes(document) != raw:
            raise ValueError("lineage cursor is not canonical")
        return cast(dict[str, object], document)

    @classmethod
    def verify(
        cls,
        value: str,
        *,
        root_entity_id: UUID,
        direction: LineageDirection,
        max_depth: int,
        target_entity_type: str | None,
    ) -> _CursorPosition:
        document = cls._decode(value)
        if set(document) != {
            "v",
            "root",
            "direction",
            "max_depth",
            "target_entity_type",
            "after_depth",
            "after_entity_id",
        }:
            raise ValueError("lineage cursor fields are invalid")
        if (
            document["v"] != 1
            or document["root"] != str(root_entity_id)
            or document["direction"] != direction.value
            or document["max_depth"] != max_depth
            or document["target_entity_type"] != target_entity_type
        ):
            raise ValueError("lineage cursor belongs to another query")
        after_depth = document["after_depth"]
        after_entity_id = document["after_entity_id"]
        if type(after_depth) is not int or not isinstance(after_entity_id, str):
            raise ValueError("lineage cursor position is invalid")
        try:
            entity_id = UUID(after_entity_id)
        except ValueError as error:
            raise ValueError("lineage cursor Entity ID is invalid") from error
        if not 0 <= after_depth <= max_depth or entity_id.int == 0:
            raise ValueError("lineage cursor position is outside the query")
        return _CursorPosition(after_depth, entity_id)


class ProvenanceLineageService:
    def __init__(
        self,
        *,
        repository: LineageRepository,
        policy: LineagePolicy | None = None,
    ) -> None:
        self._repository = repository
        self._policy = policy or LineagePolicy()

    @staticmethod
    def _assert_read_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        if (
            decision.permission is not Permission.PROVENANCE_READ
            or context.principal.id != decision.principal_id
            or context.organization_id != decision.organization_id
            or context.project_id != decision.project_id
            or context.request_id != decision.request_id
            or context.trace_id != decision.trace_id
        ):
            raise ProvenanceConflict("lineage query requires exact provenance.read scope")

    @staticmethod
    def _build_nodes(graph: LineageGraph) -> tuple[LineageNode, ...]:
        vertices = {item.record.entity.id: item for item in graph.vertices}
        paths: dict[UUID, tuple[UUID, ...]] = {graph.root_entity_id: (graph.root_entity_id,)}
        predecessors: dict[UUID, list[tuple[UUID, LineageRelation]]] = {}
        for edge in graph.edges:
            if graph.direction is LineageDirection.UPSTREAM:
                predecessor_id = edge.child_entity_id
                current_id = edge.parent_entity_id
            else:
                predecessor_id = edge.parent_entity_id
                current_id = edge.child_entity_id
            predecessors.setdefault(current_id, []).append((predecessor_id, edge.relation))
        nodes: list[LineageNode] = []
        for vertex in sorted(
            graph.vertices,
            key=lambda item: (item.depth, str(item.record.entity.id)),
        ):
            entity_id = vertex.record.entity.id
            if vertex.depth == 0:
                nodes.append(LineageNode(vertex.record, 0, paths[entity_id], None))
                continue
            candidates: list[tuple[UUID, LineageRelation]] = []
            for predecessor_id, relation in predecessors.get(entity_id, ()):
                predecessor = vertices.get(predecessor_id)
                if predecessor is not None and predecessor.depth == vertex.depth - 1:
                    candidates.append((predecessor_id, relation))
            if not candidates:
                raise ProvenanceConflict("lineage graph lacks a shortest-path predecessor")
            predecessor_id, relation = min(
                candidates, key=lambda item: (str(item[0]), item[1].value)
            )
            predecessor_path = paths.get(predecessor_id)
            if predecessor_path is None:
                raise ProvenanceConflict("lineage graph predecessor ordering is invalid")
            path = (*predecessor_path, entity_id)
            paths[entity_id] = path
            nodes.append(LineageNode(vertex.record, vertex.depth, path, relation))
        return tuple(nodes)

    def query(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
        *,
        direction: LineageDirection,
        max_depth: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        target_entity_type: str | None = None,
    ) -> LineagePage:
        self._assert_read_scope(context, decision)
        depth = max_depth or self._policy.default_depth
        page_size = limit or self._policy.default_page_size
        if not 1 <= depth <= self._policy.maximum_depth:
            raise ValueError(f"max_depth must be between 1 and {self._policy.maximum_depth}")
        if not 1 <= page_size <= self._policy.maximum_page_size:
            raise ValueError(f"limit must be between 1 and {self._policy.maximum_page_size}")
        if target_entity_type is not None and _ENTITY_TYPE.fullmatch(target_entity_type) is None:
            raise ValueError("target_entity_type must be a namespaced stable token")
        position = (
            LineageCursorCodec.verify(
                cursor,
                root_entity_id=root_entity_id,
                direction=direction,
                max_depth=depth,
                target_entity_type=target_entity_type,
            )
            if cursor is not None
            else None
        )
        graph = self._repository.load_lineage_graph(
            context=context,
            decision=decision,
            root_entity_id=root_entity_id,
            direction=direction,
            max_depth=depth,
            max_nodes=self._policy.maximum_graph_nodes,
        )
        nodes = self._build_nodes(graph)
        filtered = tuple(
            node
            for node in nodes
            if target_entity_type is None or node.record.entity.entity_type == target_entity_type
        )
        total_discovered = len(filtered)
        if position is not None:
            filtered = tuple(
                node
                for node in filtered
                if (node.depth, str(node.record.entity.id))
                > (position.depth, str(position.entity_id))
            )
        page_nodes = filtered[:page_size]
        has_more = len(filtered) > page_size
        next_cursor = None
        if has_more and page_nodes:
            last = page_nodes[-1]
            next_cursor = LineageCursorCodec.issue(
                root_entity_id=root_entity_id,
                direction=direction,
                max_depth=depth,
                target_entity_type=target_entity_type,
                position=_CursorPosition(last.depth, last.record.entity.id),
            )
        return LineagePage(
            root_entity_id=root_entity_id,
            direction=direction,
            max_depth=depth,
            limit=page_size,
            target_entity_type=target_entity_type,
            nodes=page_nodes,
            next_cursor=next_cursor,
            graph_truncated=graph.truncated,
            total_discovered=total_discovered,
        )

    def impact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
        *,
        max_depth: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        target_entity_type: str | None = None,
    ) -> LineagePage:
        return self.query(
            context,
            decision,
            root_entity_id,
            direction=LineageDirection.DOWNSTREAM,
            max_depth=max_depth,
            limit=limit,
            cursor=cursor,
            target_entity_type=target_entity_type,
        )

    @staticmethod
    def _has_cycle(graph: LineageGraph) -> bool:
        adjacency: dict[UUID, set[UUID]] = {}
        indegree: dict[UUID, int] = {vertex.record.entity.id: 0 for vertex in graph.vertices}
        for edge in graph.edges:
            targets = adjacency.setdefault(edge.child_entity_id, set())
            if edge.parent_entity_id not in targets:
                targets.add(edge.parent_entity_id)
                indegree[edge.parent_entity_id] += 1
        ready = [entity_id for entity_id, count in indegree.items() if count == 0]
        visited_count = 0
        while ready:
            entity_id = ready.pop()
            visited_count += 1
            for parent_id in adjacency.get(entity_id, ()):
                indegree[parent_id] -= 1
                if indegree[parent_id] == 0:
                    ready.append(parent_id)
        return visited_count != len(indegree)

    def completeness(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
    ) -> ProvenanceCompletenessReport:
        self._assert_read_scope(context, decision)
        graph = self._repository.load_lineage_graph(
            context=context,
            decision=decision,
            root_entity_id=root_entity_id,
            direction=LineageDirection.UPSTREAM,
            max_depth=self._policy.maximum_depth,
            max_nodes=self._policy.maximum_graph_nodes,
        )
        issues: list[CompletenessIssue] = []
        for vertex in graph.vertices:
            if vertex.record.completeness.state is CompletenessState.INCOMPLETE:
                issues.append(
                    CompletenessIssue(
                        CompletenessIssueCode.MISSING_PRIMARY_GENERATION,
                        entity_id=vertex.record.entity.id,
                    )
                )
        activity_ids = {
            *(edge.activity_id for edge in graph.edges if edge.activity_id is not None),
            *(
                vertex.record.generation_activity_id
                for vertex in graph.vertices
                if vertex.record.generation_activity_id is not None
            ),
        }
        issues.extend(
            self._repository.activity_completeness_issues(
                context=context,
                decision=decision,
                activity_ids=tuple(sorted(activity_ids, key=str)),
            )
        )
        if self._has_cycle(graph):
            issues.append(
                CompletenessIssue(
                    CompletenessIssueCode.DEPENDENCY_CYCLE,
                    entity_id=root_entity_id,
                )
            )
        has_source = any(
            vertex.record.entity.generation_requirement is GenerationRequirement.NONE
            for vertex in graph.vertices
        )
        if not has_source and not graph.truncated:
            issues.append(
                CompletenessIssue(
                    CompletenessIssueCode.MISSING_SOURCE_PATH,
                    entity_id=root_entity_id,
                )
            )
        if graph.truncated:
            issues.append(CompletenessIssue(CompletenessIssueCode.GRAPH_LIMIT_EXCEEDED))
        unique = tuple(
            sorted(
                set(issues),
                key=lambda issue: (
                    issue.code.value,
                    str(issue.entity_id or ""),
                    str(issue.activity_id or ""),
                ),
            )
        )
        substantive = tuple(
            issue
            for issue in unique
            if issue.code is not CompletenessIssueCode.GRAPH_LIMIT_EXCEEDED
        )
        if substantive:
            state = CompletenessReportState.INCOMPLETE
        elif graph.truncated:
            state = CompletenessReportState.INDETERMINATE
        else:
            state = CompletenessReportState.COMPLETE
        return ProvenanceCompletenessReport(
            root_entity_id=root_entity_id,
            state=state,
            eligible=state is CompletenessReportState.COMPLETE,
            nodes_evaluated=len(graph.vertices),
            edges_evaluated=len(graph.edges),
            max_depth_reached=max(item.depth for item in graph.vertices),
            issues=unique,
        )
