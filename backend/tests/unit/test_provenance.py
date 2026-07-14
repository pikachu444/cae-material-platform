from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
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
from cmp.modules.provenance.application.service import (
    ProvenanceReferenceResolver,
    ProvenanceService,
    ResolvedActivityCommit,
)
from cmp.modules.provenance.domain.model import (
    ActivityAgent,
    ActivityCommitResult,
    ActivityInput,
    ActivityOutput,
    ActivityStatus,
    AgentReference,
    AgentType,
    CommitActivityProvenance,
    CompletenessState,
    DerivationInput,
    EntityCompleteness,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    InvalidProvenance,
    MutableEntityReference,
    ProvenanceConflict,
    ProvenanceRecord,
    ProvenanceScope,
    ResolvedAgentReference,
    ResolvedEntityReference,
)

NOW = datetime(2026, 7, 13, 9, 0, tzinfo=UTC)
ORG = UUID("8d000000-0000-4000-8000-000000000001")
PROJECT = UUID("8d000000-0000-4000-8000-000000000002")
ACTOR = UUID("8d000000-0000-4000-8000-000000000003")
RAW_ID = UUID("8d000000-0000-4000-8000-000000000004")
OUTPUT_ID = UUID("8d000000-0000-4000-8000-000000000005")
RUN_ID = UUID("8d000000-0000-4000-8000-000000000006")
TRACE = "00-0000000000000000000000000000008d-000000000000008d-01"
RAW_DIGEST = hashlib.sha256(b"raw").hexdigest()
OUTPUT_DIGEST = hashlib.sha256(b"normalized").hexdigest()
SCOPE = ProvenanceScope(ORG, PROJECT, DataClassification.INTERNAL)
RAW = ImmutableEntityReference(
    EntityReferenceKind.RAW_ASSET, "artifact.raw_asset", RAW_ID, RAW_DIGEST
)
OUTPUT = ImmutableEntityReference(
    EntityReferenceKind.REVISION,
    "synthetic.dataset_revision",
    OUTPUT_ID,
    OUTPUT_DIGEST,
)


def _context(*, project_id: UUID = PROJECT) -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Provenance User", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=UUID("8d000000-0000-4000-8000-000000000007"),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext, permission: Permission = Permission.ARTIFACT_WRITE
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


def _command() -> CommitActivityProvenance:
    return CommitActivityProvenance(
        scope=SCOPE,
        activity_type="synthetic.normalization_run",
        domain_run_type="synthetic.dataset_run",
        domain_run_id=RUN_ID,
        status=ActivityStatus.SUCCEEDED,
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        inputs=(ActivityInput(RAW, "source", 0),),
        outputs=(
            ActivityOutput(
                OUTPUT,
                "primary",
                (DerivationInput(RAW, "normalization"),),
            ),
        ),
        agents=(ActivityAgent(AgentReference(AgentType.USER, ACTOR), "operator"),),
    )


class _Resolver(ProvenanceReferenceResolver):
    def __init__(self, *, scope: ProvenanceScope = SCOPE) -> None:
        self.scope = scope

    def resolve_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: ImmutableEntityReference,
    ) -> ResolvedEntityReference:
        del context, decision
        return ResolvedEntityReference(
            reference=reference,
            entity_type=(
                "artifact.raw_asset"
                if reference.kind is EntityReferenceKind.RAW_ASSET
                else "synthetic.dataset_revision"
            ),
            scope=self.scope,
            created_at=NOW,
            generation_requirement=(
                GenerationRequirement.NONE
                if reference.kind is EntityReferenceKind.RAW_ASSET
                else GenerationRequirement.PRIMARY
            ),
        )

    def resolve_agent(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference: AgentReference,
    ) -> ResolvedAgentReference:
        del context, decision
        return ResolvedAgentReference(reference, self.scope)


class _Repository:
    def __init__(self) -> None:
        self.commit: ResolvedActivityCommit | None = None
        self.record: ProvenanceRecord | None = None

    def commit_activity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        commit: ResolvedActivityCommit,
    ) -> ActivityCommitResult:
        del context, decision
        self.commit = commit
        entities = {item.reference: item for item in commit.entities}
        agents = {item.reference: item for item in commit.agents}
        return ActivityCommitResult(
            activity=commit.activity,
            input_entity_ids=tuple(
                entities[item.entity].id for item in commit.command.inputs
            ),
            output_entity_ids=tuple(
                entities[item.entity].id for item in commit.command.outputs
            ),
            agent_ids=tuple(agents[item.agent].id for item in commit.command.agents),
            replayed=False,
        )

    def get_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        entity_id: UUID,
    ) -> ProvenanceRecord:
        del context, decision, entity_id
        assert self.record is not None
        return self.record

    def find_entity_by_reference(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference_type: str,
        reference_id: UUID,
    ) -> ProvenanceRecord:
        del context, decision, reference_type, reference_id
        assert self.record is not None
        return self.record

def test_moving_head_reference_is_rejected_before_persistence() -> None:
    with pytest.raises(MutableEntityReference):
        ImmutableEntityReference(
            EntityReferenceKind.REVISION,
            "aggregate.head",
            uuid4(),
            OUTPUT_DIGEST,
        )


def test_run_command_requires_inputs_agents_outputs_and_declared_derivations() -> None:
    base = _command()
    with pytest.raises(InvalidProvenance, match="input usage"):
        CommitActivityProvenance(
            base.scope,
            base.activity_type,
            base.domain_run_type,
            base.domain_run_id,
            base.status,
            base.started_at,
            base.ended_at,
            (),
            base.outputs,
            base.agents,
        )
    with pytest.raises(InvalidProvenance, match=r"responsible|agent"):
        CommitActivityProvenance(
            base.scope,
            base.activity_type,
            base.domain_run_type,
            base.domain_run_id,
            base.status,
            base.started_at,
            base.ended_at,
            base.inputs,
            base.outputs,
            (),
        )
    with pytest.raises(InvalidProvenance, match="generated output"):
        CommitActivityProvenance(
            base.scope,
            base.activity_type,
            base.domain_run_type,
            base.domain_run_id,
            base.status,
            base.started_at,
            base.ended_at,
            base.inputs,
            (),
            base.agents,
        )


def test_service_resolves_immutable_references_and_stages_typed_graph() -> None:
    context = _context()
    repository = _Repository()
    service = ProvenanceService(
        repository=repository,
        resolver=_Resolver(),
        clock=lambda: NOW + timedelta(seconds=2),
    )

    result = service.commit_activity(context, _decision(context), _command())

    assert not result.replayed
    assert len(result.input_entity_ids) == 1
    assert len(result.output_entity_ids) == 1
    assert repository.commit is not None
    assert repository.commit.activity.submission_digest
    output_entity = next(
        item for item in repository.commit.entities if item.reference == OUTPUT
    )
    assert output_entity.generation_requirement is GenerationRequirement.PRIMARY


def test_service_rejects_owner_attestation_outside_exact_scope() -> None:
    context = _context()
    service = ProvenanceService(
        repository=_Repository(),
        resolver=_Resolver(
            scope=ProvenanceScope(ORG, uuid4(), DataClassification.INTERNAL)
        ),
    )

    with pytest.raises(ProvenanceConflict, match="owner attestation"):
        service.commit_activity(context, _decision(context), _command())


def test_completeness_state_cannot_claim_complete_with_issues() -> None:
    with pytest.raises(InvalidProvenance):
        EntityCompleteness(
            CompletenessState.COMPLETE, ("missing_primary_generation",)
        )
