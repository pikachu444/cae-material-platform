"""T-14 bounded lineage and provenance completeness result types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cmp.modules.provenance.domain.model import (
    InvalidProvenance,
    ProvenanceRecord,
)


class LineageDirection(StrEnum):
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"


class LineageRelation(StrEnum):
    USAGE_GENERATION = "usage_generation"
    DERIVATION = "derivation"
    REVISION = "revision"


class CompletenessReportState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    INDETERMINATE = "indeterminate"


class CompletenessIssueCode(StrEnum):
    MISSING_PRIMARY_GENERATION = "missing_primary_generation"
    MISSING_ACTIVITY_INPUT = "missing_activity_input"
    MISSING_ACTIVITY_AGENT = "missing_activity_agent"
    MISSING_ACTIVITY_OUTPUT = "missing_activity_output"
    MISSING_SOURCE_PATH = "missing_source_path"
    DEPENDENCY_CYCLE = "dependency_cycle"
    GRAPH_LIMIT_EXCEEDED = "graph_limit_exceeded"


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    child_entity_id: UUID
    parent_entity_id: UUID
    relation: LineageRelation
    activity_id: UUID | None

    def __post_init__(self) -> None:
        if self.child_entity_id.int == 0 or self.parent_entity_id.int == 0:
            raise InvalidProvenance("dependency edge Entity IDs must be non-zero")
        if self.child_entity_id == self.parent_entity_id:
            raise InvalidProvenance("dependency edge cannot be a self-loop")
        if self.activity_id is not None and self.activity_id.int == 0:
            raise InvalidProvenance("dependency edge Activity ID must be non-zero")


@dataclass(frozen=True, slots=True)
class LineageVertex:
    record: ProvenanceRecord
    depth: int

    def __post_init__(self) -> None:
        if not 0 <= self.depth <= 100:
            raise InvalidProvenance("lineage vertex depth is invalid")


@dataclass(frozen=True, slots=True)
class LineageGraph:
    root_entity_id: UUID
    direction: LineageDirection
    vertices: tuple[LineageVertex, ...]
    edges: tuple[DependencyEdge, ...]
    truncated: bool

    def __post_init__(self) -> None:
        if self.root_entity_id.int == 0:
            raise InvalidProvenance("lineage root must be non-zero")
        identifiers = [item.record.entity.id for item in self.vertices]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise InvalidProvenance("lineage graph vertices must be non-empty and unique")
        root = next(
            (item for item in self.vertices if item.record.entity.id == self.root_entity_id),
            None,
        )
        if root is None or root.depth != 0:
            raise InvalidProvenance("lineage graph must contain its depth-zero root")
        known = set(identifiers)
        if any(
            edge.child_entity_id not in known or edge.parent_entity_id not in known
            for edge in self.edges
        ):
            raise InvalidProvenance("lineage edges must connect returned vertices")


@dataclass(frozen=True, slots=True)
class LineageNode:
    record: ProvenanceRecord
    depth: int
    path: tuple[UUID, ...]
    via_relation: LineageRelation | None

    def __post_init__(self) -> None:
        if not 0 <= self.depth <= 100:
            raise InvalidProvenance("lineage node depth is invalid")
        if len(self.path) != self.depth + 1:
            raise InvalidProvenance("lineage path length must equal depth plus root")
        if self.path[-1] != self.record.entity.id or len(set(self.path)) != len(self.path):
            raise InvalidProvenance("lineage path must be acyclic and end at the Entity")
        if (self.depth == 0) != (self.via_relation is None):
            raise InvalidProvenance("only the root omits via_relation")


@dataclass(frozen=True, slots=True)
class LineagePage:
    root_entity_id: UUID
    direction: LineageDirection
    max_depth: int
    limit: int
    target_entity_type: str | None
    nodes: tuple[LineageNode, ...]
    next_cursor: str | None
    graph_truncated: bool
    total_discovered: int


@dataclass(frozen=True, slots=True)
class CompletenessIssue:
    code: CompletenessIssueCode
    entity_id: UUID | None = None
    activity_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.entity_id is not None and self.entity_id.int == 0:
            raise InvalidProvenance("completeness issue Entity ID must be non-zero")
        if self.activity_id is not None and self.activity_id.int == 0:
            raise InvalidProvenance("completeness issue Activity ID must be non-zero")


@dataclass(frozen=True, slots=True)
class ProvenanceCompletenessReport:
    root_entity_id: UUID
    state: CompletenessReportState
    eligible: bool
    nodes_evaluated: int
    edges_evaluated: int
    max_depth_reached: int
    issues: tuple[CompletenessIssue, ...]

    def __post_init__(self) -> None:
        if self.root_entity_id.int == 0:
            raise InvalidProvenance("completeness root must be non-zero")
        if self.nodes_evaluated < 1 or self.edges_evaluated < 0:
            raise InvalidProvenance("completeness counts are invalid")
        if not 0 <= self.max_depth_reached <= 100:
            raise InvalidProvenance("completeness depth is invalid")
        if self.eligible != (self.state is CompletenessReportState.COMPLETE):
            raise InvalidProvenance("only a complete report may be eligible")
        if self.state is CompletenessReportState.COMPLETE and self.issues:
            raise InvalidProvenance("complete report cannot contain issues")
        if self.state is not CompletenessReportState.COMPLETE and not self.issues:
            raise InvalidProvenance("non-complete report requires issues")
