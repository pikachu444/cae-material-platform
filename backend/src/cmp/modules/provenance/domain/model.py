"""T-13 typed provenance nodes, relations, and invariant-bearing commands.

The module follows the W3C PROV meanings selected by the repository documents without
introducing RDF, an unrestricted edge table, or a generic domain-content store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import DataClassification

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")
_NAMESPACED_TOKEN = re.compile(
    r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+(?:[._-][a-z0-9]+)*$"
)


class ProvenanceError(Exception):
    """Base error for T-13 provenance operations."""


class InvalidProvenance(ProvenanceError, ValueError):
    """A node, relation, or command violates a provenance invariant."""


class ProvenanceConflict(ProvenanceError):
    """An immutable reference, generation, or domain-run identity conflicts."""


class ProvenanceNotFound(ProvenanceError):
    """A provenance node is absent or hidden by tenant policy."""


class MutableEntityReference(ProvenanceError):
    """A moving aggregate/head alias was supplied instead of immutable content."""


class ProvenanceCycle(ProvenanceConflict):
    """A derivation, revision, or usage-generation relation would create a cycle."""


class EntityReferenceKind(StrEnum):
    RAW_ASSET = "raw_asset"
    ARTIFACT = "artifact"
    REVISION = "revision"


class GenerationRequirement(StrEnum):
    NONE = "none"
    PRIMARY = "primary"


class ActivityStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(StrEnum):
    USER = "user"
    SERVICE = "service"
    PLUGIN_PACKAGE = "plugin_package"
    ORGANIZATION = "organization"


class CompletenessState(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidProvenance(f"{name} must be non-zero")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidProvenance(f"{name} must be timezone-aware")


def _token(name: str, value: str) -> None:
    if _TOKEN.fullmatch(value) is None:
        raise InvalidProvenance(f"{name} must be a stable token")


def _namespaced(name: str, value: str) -> None:
    if _NAMESPACED_TOKEN.fullmatch(value) is None:
        raise InvalidProvenance(f"{name} must be a namespaced stable token")


def _digest(name: str, value: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise InvalidProvenance(f"{name} must be a lowercase SHA-256 digest")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidProvenance(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


@dataclass(frozen=True, slots=True)
class ProvenanceScope:
    organization_id: UUID
    project_id: UUID
    classification: DataClassification

    def __post_init__(self) -> None:
        _nonzero("organization_id", self.organization_id)
        _nonzero("project_id", self.project_id)


@dataclass(frozen=True, slots=True)
class ImmutableEntityReference:
    """Caller-supplied immutable reference and expected content digest."""

    kind: EntityReferenceKind
    reference_type: str
    reference_id: UUID
    content_sha256: str

    def __post_init__(self) -> None:
        _nonzero("reference_id", self.reference_id)
        _namespaced("reference_type", self.reference_type)
        _digest("content_sha256", self.content_sha256)
        if self.kind is EntityReferenceKind.RAW_ASSET:
            if self.reference_type != "artifact.raw_asset":
                raise InvalidProvenance(
                    "Raw Asset references must use artifact.raw_asset"
                )
        elif self.kind is EntityReferenceKind.ARTIFACT:
            if self.reference_type != "artifact.artifact":
                raise InvalidProvenance("Artifact references must use artifact.artifact")
        elif self.reference_type in {"aggregate.head", "aggregate.latest"}:
            raise MutableEntityReference(
                "provenance inputs must identify a concrete immutable revision"
            )


@dataclass(frozen=True, slots=True)
class ResolvedEntityReference:
    """Owner-module attestation for an immutable entity reference."""

    reference: ImmutableEntityReference
    entity_type: str
    scope: ProvenanceScope
    created_at: datetime
    generation_requirement: GenerationRequirement

    def __post_init__(self) -> None:
        _namespaced("entity_type", self.entity_type)
        _aware("created_at", self.created_at)
        expected = (
            GenerationRequirement.NONE
            if self.reference.kind is EntityReferenceKind.RAW_ASSET
            else GenerationRequirement.PRIMARY
        )
        if self.generation_requirement is not expected:
            raise InvalidProvenance(
                "only Raw Assets may enter provenance without primary generation"
            )


@dataclass(frozen=True, slots=True)
class AgentReference:
    agent_type: AgentType
    reference_id: UUID

    def __post_init__(self) -> None:
        _nonzero("agent reference_id", self.reference_id)


@dataclass(frozen=True, slots=True)
class ResolvedAgentReference:
    reference: AgentReference
    scope: ProvenanceScope


@dataclass(frozen=True, slots=True)
class ActivityInput:
    entity: ImmutableEntityReference
    role: str
    ordinal: int

    def __post_init__(self) -> None:
        _token("usage role", self.role)
        if not 0 <= self.ordinal <= 2_147_483_647:
            raise InvalidProvenance("usage ordinal must fit a non-negative integer")


@dataclass(frozen=True, slots=True)
class DerivationInput:
    entity: ImmutableEntityReference
    kind: str

    def __post_init__(self) -> None:
        _token("derivation kind", self.kind)


@dataclass(frozen=True, slots=True)
class ActivityOutput:
    entity: ImmutableEntityReference
    role: str
    derivations: tuple[DerivationInput, ...]

    def __post_init__(self) -> None:
        _token("generation role", self.role)
        identities = [item.entity for item in self.derivations]
        if len(identities) != len(set(identities)):
            raise InvalidProvenance("output derivations must be unique")


@dataclass(frozen=True, slots=True)
class ActivityAgent:
    agent: AgentReference
    role: str
    plan_entity: ImmutableEntityReference | None = None

    def __post_init__(self) -> None:
        _token("association role", self.role)


@dataclass(frozen=True, slots=True)
class CommitActivityProvenance:
    """Atomic terminal run hook expressed without any domain-specific vocabulary."""

    scope: ProvenanceScope
    activity_type: str
    domain_run_type: str
    domain_run_id: UUID
    status: ActivityStatus
    started_at: datetime
    ended_at: datetime
    inputs: tuple[ActivityInput, ...]
    outputs: tuple[ActivityOutput, ...]
    agents: tuple[ActivityAgent, ...]

    def __post_init__(self) -> None:
        _namespaced("activity_type", self.activity_type)
        _namespaced("domain_run_type", self.domain_run_type)
        _nonzero("domain_run_id", self.domain_run_id)
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        if self.ended_at < self.started_at:
            raise InvalidProvenance("activity end cannot precede its start")
        if not self.inputs:
            raise InvalidProvenance("committed run provenance requires an input usage")
        if not self.agents:
            raise InvalidProvenance("committed run provenance requires an agent")
        if self.status is ActivityStatus.SUCCEEDED and not self.outputs:
            raise InvalidProvenance("succeeded activity requires a generated output")

        input_refs = [item.entity for item in self.inputs]
        output_refs = [item.entity for item in self.outputs]
        if len(input_refs) != len(set(input_refs)):
            raise InvalidProvenance("activity input entities must be unique")
        if len(output_refs) != len(set(output_refs)):
            raise InvalidProvenance("activity output entities must be unique")
        if set(input_refs).intersection(output_refs):
            raise InvalidProvenance("one immutable entity cannot be both input and output")
        if len({(item.role, item.ordinal) for item in self.inputs}) != len(self.inputs):
            raise InvalidProvenance("usage role/ordinal positions must be unique")
        if len({(item.agent, item.role) for item in self.agents}) != len(self.agents):
            raise InvalidProvenance("activity agent/role associations must be unique")

        available_inputs = set(input_refs)
        for output in self.outputs:
            if output.entity.kind is EntityReferenceKind.RAW_ASSET:
                raise InvalidProvenance("Raw Assets cannot be generated run outputs")
            for derivation in output.derivations:
                if derivation.entity not in available_inputs:
                    raise InvalidProvenance(
                        "derivation sources must also be declared activity inputs"
                    )
        for association in self.agents:
            if (
                association.plan_entity is not None
                and association.plan_entity not in available_inputs
            ):
                raise InvalidProvenance(
                    "association plan Entity must also be an activity input"
                )


@dataclass(frozen=True, slots=True)
class ProvenanceEntity:
    id: UUID
    scope: ProvenanceScope
    entity_type: str
    reference: ImmutableEntityReference
    generation_requirement: GenerationRequirement
    created_at: datetime
    recorded_at: datetime
    recorded_by: UUID

    def __post_init__(self) -> None:
        _nonzero("entity id", self.id)
        _namespaced("entity_type", self.entity_type)
        _aware("created_at", self.created_at)
        _aware("recorded_at", self.recorded_at)
        _nonzero("recorded_by", self.recorded_by)


@dataclass(frozen=True, slots=True)
class ProvenanceActivity:
    id: UUID
    scope: ProvenanceScope
    activity_type: str
    domain_run_type: str
    domain_run_id: UUID
    status: ActivityStatus
    started_at: datetime
    ended_at: datetime
    submission_digest: str
    recorded_at: datetime
    recorded_by: UUID

    def __post_init__(self) -> None:
        _nonzero("activity id", self.id)
        _namespaced("activity_type", self.activity_type)
        _namespaced("domain_run_type", self.domain_run_type)
        _nonzero("domain_run_id", self.domain_run_id)
        _aware("started_at", self.started_at)
        _aware("ended_at", self.ended_at)
        _digest("submission_digest", self.submission_digest)
        _aware("recorded_at", self.recorded_at)
        _nonzero("recorded_by", self.recorded_by)


@dataclass(frozen=True, slots=True)
class ProvenanceAgent:
    id: UUID
    scope: ProvenanceScope
    reference: AgentReference
    recorded_at: datetime
    recorded_by: UUID


@dataclass(frozen=True, slots=True)
class EntityCompleteness:
    state: CompletenessState
    issues: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.state is CompletenessState.COMPLETE and self.issues:
            raise InvalidProvenance("complete provenance cannot carry issues")
        if self.state is CompletenessState.INCOMPLETE and not self.issues:
            raise InvalidProvenance("incomplete provenance requires at least one issue")
        for issue in self.issues:
            _token("completeness issue", issue)


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    entity: ProvenanceEntity
    generation_activity_id: UUID | None
    completeness: EntityCompleteness

    def __post_init__(self) -> None:
        if self.generation_activity_id is not None:
            _nonzero("generation_activity_id", self.generation_activity_id)


@dataclass(frozen=True, slots=True)
class ActivityCommitResult:
    activity: ProvenanceActivity
    input_entity_ids: tuple[UUID, ...]
    output_entity_ids: tuple[UUID, ...]
    agent_ids: tuple[UUID, ...]
    replayed: bool


def validate_change_reason(value: str) -> None:
    """Validate revision relation reasons for the SQL revision hook."""

    _text("change_reason", value, 2000)
