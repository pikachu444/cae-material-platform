"""T-13 atomic provenance write orchestration and lineage query service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.provenance.domain.model import (
    ActivityCommitResult,
    ActivityInput,
    ActivityOutput,
    AgentReference,
    CommitActivityProvenance,
    ImmutableEntityReference,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceConflict,
    ProvenanceEntity,
    ProvenanceRecord,
    ResolvedAgentReference,
    ResolvedEntityReference,
)
from cmp.shared.domain.revisions import content_sha256


class ProvenanceReferenceResolver(Protocol):
    """Owner-module boundary that rejects mutable or nonexistent references."""

    def resolve_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: ImmutableEntityReference,
    ) -> ResolvedEntityReference: ...

    def resolve_agent(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: AgentReference,
    ) -> ResolvedAgentReference: ...


@dataclass(frozen=True, slots=True)
class ResolvedActivityCommit:
    activity: ProvenanceActivity
    command: CommitActivityProvenance
    entities: tuple[ProvenanceEntity, ...]
    agents: tuple[ProvenanceAgent, ...]


class ProvenanceRepository(Protocol):
    def commit_activity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        commit: ResolvedActivityCommit,
    ) -> ActivityCommitResult: ...

    def get_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        entity_id: UUID,
    ) -> ProvenanceRecord: ...

    def find_entity_by_reference(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference_type: str,
        reference_id: UUID,
    ) -> ProvenanceRecord: ...

def _reference_document(reference: ImmutableEntityReference) -> dict[str, str]:
    return {
        "kind": reference.kind.value,
        "type": reference.reference_type,
        "id": str(reference.reference_id),
        "sha256": reference.content_sha256,
    }


def _input_document(value: ActivityInput) -> dict[str, object]:
    return {
        "entity": _reference_document(value.entity),
        "role": value.role,
        "ordinal": value.ordinal,
    }


def _output_document(value: ActivityOutput) -> dict[str, object]:
    return {
        "entity": _reference_document(value.entity),
        "role": value.role,
        "derivations": [
            {"entity": _reference_document(item.entity), "kind": item.kind}
            for item in value.derivations
        ],
    }


class ProvenanceService:
    """Validate owner attestations, commit typed relations, and query lineage."""

    def __init__(
        self,
        *,
        repository: ProvenanceRepository,
        resolver: ProvenanceReferenceResolver | None = None,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._resolver = resolver
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _assert_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        if (
            context.principal.id != decision.principal_id
            or context.organization_id != decision.organization_id
            or context.project_id != decision.project_id
            or context.request_id != decision.request_id
            or context.trace_id != decision.trace_id
        ):
            raise ProvenanceConflict("security and authorization contexts differ")

    def commit_activity(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CommitActivityProvenance,
    ) -> ActivityCommitResult:
        """Commit one terminal run graph; this method is never exposed as public graph write."""

        self._assert_scope(context, decision)
        if "provenance.write" not in decision.database_permissions:
            raise ProvenanceConflict("command authorization lacks provenance.write")
        if not decision.allows(
            command.scope.organization_id,
            command.scope.project_id,
            command.scope.classification,
        ):
            raise ProvenanceConflict("provenance command is outside the authorized scope")
        if self._resolver is None:
            raise ProvenanceConflict("immutable reference resolution is not configured")

        references: dict[ImmutableEntityReference, ResolvedEntityReference] = {}
        ordered_references = [
            *(item.entity for item in command.inputs),
            *(item.entity for item in command.outputs),
        ]
        for reference in ordered_references:
            if reference in references:
                continue
            resolved = self._resolver.resolve_entity(
                context=context,
                decision=decision,
                reference=reference,
            )
            if resolved.reference != reference or resolved.scope != command.scope:
                raise ProvenanceConflict(
                    "entity owner attestation differs from the requested immutable reference"
                )
            references[reference] = resolved

        agent_references: dict[AgentReference, ResolvedAgentReference] = {}
        for association in command.agents:
            agent_reference = association.agent
            if agent_reference in agent_references:
                continue
            resolved_agent = self._resolver.resolve_agent(
                context=context,
                decision=decision,
                reference=agent_reference,
            )
            if (
                resolved_agent.reference != agent_reference
                or resolved_agent.scope != command.scope
            ):
                raise ProvenanceConflict(
                    "agent owner attestation differs from the activity scope"
                )
            agent_references[agent_reference] = resolved_agent

        recorded_at = self._clock()
        submission_digest = content_sha256(
            {
                "activity_type": command.activity_type,
                "domain_run_type": command.domain_run_type,
                "domain_run_id": str(command.domain_run_id),
                "status": command.status.value,
                "started_at": command.started_at.isoformat(),
                "ended_at": command.ended_at.isoformat(),
                "scope": {
                    "organization_id": str(command.scope.organization_id),
                    "project_id": str(command.scope.project_id),
                    "classification": command.scope.classification.value,
                },
                "inputs": [_input_document(item) for item in command.inputs],
                "outputs": [_output_document(item) for item in command.outputs],
                "agents": [
                    {
                        "type": item.agent.agent_type.value,
                        "id": str(item.agent.reference_id),
                        "role": item.role,
                        "plan": (
                            _reference_document(item.plan_entity)
                            if item.plan_entity is not None
                            else None
                        ),
                    }
                    for item in command.agents
                ],
            }
        )
        activity = ProvenanceActivity(
            id=self._id_factory(),
            scope=command.scope,
            activity_type=command.activity_type,
            domain_run_type=command.domain_run_type,
            domain_run_id=command.domain_run_id,
            status=command.status,
            started_at=command.started_at,
            ended_at=command.ended_at,
            submission_digest=submission_digest,
            recorded_at=recorded_at,
            recorded_by=context.principal.id,
        )
        entities = tuple(
            ProvenanceEntity(
                id=self._id_factory(),
                scope=resolved.scope,
                entity_type=resolved.entity_type,
                reference=resolved.reference,
                generation_requirement=resolved.generation_requirement,
                created_at=resolved.created_at,
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
            )
            for resolved in references.values()
        )
        agents = tuple(
            ProvenanceAgent(
                id=self._id_factory(),
                scope=resolved.scope,
                reference=resolved.reference,
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
            )
            for resolved in agent_references.values()
        )
        return self._repository.commit_activity(
            context=context,
            decision=decision,
            commit=ResolvedActivityCommit(
                activity=activity,
                command=command,
                entities=entities,
                agents=agents,
            ),
        )

    def get_entity(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        entity_id: UUID,
    ) -> ProvenanceRecord:
        self._assert_scope(context, decision)
        if decision.permission is not Permission.PROVENANCE_READ:
            raise ProvenanceConflict("entity lookup requires provenance.read")
        return self._repository.get_entity(
            context=context,
            decision=decision,
            entity_id=entity_id,
        )

    def find_entity_by_reference(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        reference_type: str,
        reference_id: UUID,
    ) -> ProvenanceRecord:
        self._assert_scope(context, decision)
        if decision.permission is not Permission.PROVENANCE_READ:
            raise ProvenanceConflict("entity lookup requires provenance.read")
        return self._repository.find_entity_by_reference(
            context=context,
            decision=decision,
            reference_type=reference_type,
            reference_id=reference_id,
        )
