from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import sqlalchemy as sa
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.persistence.linear_viscoelastic_calibration_tables import (
    linear_viscoelastic_calibration_plan_revision_table,
)
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationPlanSnapshot,
    CreateGovernedLinearViscoelasticCalibrationPlan,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    InMemoryLinearViscoelasticCalibrationRepository,
    LinearViscoelasticCalibrationService,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ResolvedGovernedViscoelasticInput,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    InMemoryLinearViscoelasticPlanApproval,
    PlanApprovalState,
    PlanContextQuery,
    PlanGovernanceError,
    assert_distinct_plan_approver,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
    ArtifactPin,
    CalibrationWeights,
    ChannelAvailability,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
    InputChannelSemantics,
    LinearViscoelasticCalibrationPlan,
    ParameterBound,
    PointDisposition,
    PointPartition,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)
ORG = UUID(int=10)
PROJECT = UUID(int=11)
CREATOR = UUID(int=12)
REVIEWER = UUID(int=13)
MANAGER = UUID(int=14)
USER = UUID(int=15)
SHA = "a" * 64
MATERIAL = ExactRevisionPin(UUID(int=20), UUID(int=21))
MATERIAL_STATE = ExactRevisionPin(UUID(int=22), UUID(int=23))
TEST_DATA = ExactRevisionPin(UUID(int=24), UUID(int=25), SHA)
CANONICAL = ArtifactPin(UUID(int=26), SHA, "application/vnd.cmp.test-data+json")
NORMALIZED = ArtifactPin(UUID(int=27), SHA, "application/vnd.apache.parquet")
PROFILE = ExactRevisionPin(UUID(int=28), UUID(int=29), SHA)

SEMANTICS = GovernedViscoelasticInputSemantics(
    mode="relaxation",
    deformation_mode="shear",
    channels=(
        InputChannelSemantics("time", "time.elapsed", "independent", "s", "s"),
        InputChannelSemantics(
            "shear_modulus",
            "mechanics.modulus.shear.relaxation",
            "dependent",
            "Pa",
            "Pa",
        ),
    ),
    point_dispositions=(
        PointDisposition(0, PointPartition.EXCLUDED, "instantaneous limit"),
        PointDisposition(1, PointPartition.CALIBRATION),
        PointDisposition(2, PointPartition.CALIBRATION),
        PointDisposition(3, PointPartition.CALIBRATION),
        PointDisposition(4, PointPartition.HOLDOUT),
    ),
    selected_temperature_k=298.15,
    temperature_source="condition",
)


def test_plan_creator_cannot_approve_the_same_plan() -> None:
    with pytest.raises(PlanGovernanceError) as denied:
        assert_distinct_plan_approver(
            plan_created_by=CREATOR,
            approved_by=CREATOR,
        )

    assert denied.value.code == "PLAN_APPROVER_UNAUTHORIZED"
    assert "different domain reviewer" in denied.value.recovery_hint

    assert_distinct_plan_approver(
        plan_created_by=CREATOR,
        approved_by=REVIEWER,
    )


def test_optional_advanced_diff_persists_none_as_sql_null() -> None:
    column_type = linear_viscoelastic_calibration_plan_revision_table.c.base_diff.type

    assert isinstance(column_type, sa.JSON)
    assert column_type.none_as_null is True


def _context(principal_id: UUID, request_id: int) -> SecurityContext:
    return SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, f"User {principal_id.int}", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject=str(principal_id),
        token_id=f"token-{request_id}",
        groups=(),
        scopes=(),
        request_id=UUID(int=request_id),
        trace_id=f"trace-{request_id}",
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
    roles: tuple[Role, ...],
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=roles,
        database_permissions=(permission.value,),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _plan(
    *,
    plan_id: UUID,
    revision_id: UUID,
    setup_name: str | None = "Relaxation setup",
    ftol: float = 1e-8,
) -> LinearViscoelasticCalibrationPlan:
    return LinearViscoelasticCalibrationPlan.for_terms(
        (1,),
        bounds={
            1: (
                ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
                ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
                ParameterBound("tau_1_s", 0.01, 0.1, 1, "s"),
            )
        },
        start_vectors={1: ((4.0, 2.0, 0.1),)},
        test_data=TEST_DATA,
        canonical_artifact=CANONICAL,
        normalized_artifact=NORMALIZED,
        raw_source_sha256=SHA,
        import_profile=PROFILE,
        profile_sha256=SHA,
        input_semantics=SEMANTICS,
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        weights=CalibrationWeights(relaxation_scale_pa=Decimal(1)),
        ftol=ftol,
        plan_id=plan_id,
        plan_revision_id=revision_id,
        setup_name=setup_name,
        material=MATERIAL if setup_name is not None else None,
        material_state=MATERIAL_STATE if setup_name is not None else None,
        input_mode="relaxation" if setup_name is not None else None,
    )


def _snapshot(
    plan: LinearViscoelasticCalibrationPlan,
    created_by: UUID = CREATOR,
) -> CalibrationPlanSnapshot:
    return CalibrationPlanSnapshot(
        id=plan.plan_id,
        current=plan,
        content_hash=plan.digest,
        classification=DataClassification.INTERNAL,
        created_at=NOW,
        created_by=created_by,
        change_reason="Create exact governed Plan",
        organization_id=ORG,
        project_id=PROJECT,
    )


def _command(
    *,
    idempotency_key: str,
    setup_name: str | None = "Relaxation setup",
    material: ExactRevisionPin | None = MATERIAL,
    material_state: ExactRevisionPin | None = MATERIAL_STATE,
    input_mode: str | None = "relaxation",
    based_on_plan_id: UUID | None = None,
    based_on_plan_revision_id: UUID | None = None,
    override_reason: str | None = None,
    ftol: float = 1e-8,
) -> CreateGovernedLinearViscoelasticCalibrationPlan:
    return CreateGovernedLinearViscoelasticCalibrationPlan(
        test_data_id=TEST_DATA.aggregate_id,
        test_data_revision_id=TEST_DATA.revision_id,
        selected_temperature_k=298.15,
        point_dispositions=SEMANTICS.point_dispositions,
        availability=ChannelAvailability(),
        term_counts=(1,),
        parameter_bounds={
            1: (
                ParameterBound("G_inf_pa", 1, 4, 20, "Pa"),
                ParameterBound("G_1_pa", 1, 2, 10, "Pa"),
                ParameterBound("tau_1_s", 0.01, 0.1, 1, "s"),
            )
        },
        start_vectors={1: ((4.0, 2.0, 0.1),)},
        weights=CalibrationWeights(relaxation_scale_pa=Decimal(1)),
        recommendation_policy=LINEAR_VISCOELASTIC_RECOMMENDATION_POLICY,
        ftol=ftol,
        xtol=1e-8,
        gtol=1e-8,
        max_nfev=1000,
        change_reason="Create exact governed Plan",
        idempotency_key=idempotency_key,
        setup_name=setup_name,
        material=material,
        material_state=material_state,
        input_mode=input_mode,
        based_on_plan_id=based_on_plan_id,
        based_on_plan_revision_id=based_on_plan_revision_id,
        override_reason=override_reason,
    )


class _Resolver:
    async def resolve(self, *args: object) -> ResolvedGovernedViscoelasticInput:
        del args
        return ResolvedGovernedViscoelasticInput(
            classification=DataClassification.INTERNAL,
            test_data=TEST_DATA,
            canonical_artifact=CANONICAL,
            normalized_artifact=NORMALIZED,
            raw_source_sha256=SHA,
            import_profile=PROFILE,
            profile_sha256=SHA,
            semantics=SEMANTICS,
            material=MATERIAL,
            material_state=MATERIAL_STATE,
        )


def test_governed_authoring_requires_reviewer_and_server_derives_advanced_diff() -> None:
    author_context = _context(CREATOR, 30)
    reviewer_author_decision = _decision(
        author_context, Permission.CALIBRATION_EXECUTE, (Role.DOMAIN_REVIEWER,)
    )
    unauthorized_decision = _decision(
        author_context, Permission.CALIBRATION_EXECUTE, (Role.MATERIAL_MODELER,)
    )
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    approvals = InMemoryLinearViscoelasticPlanApproval()
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        input_resolver=_Resolver(),  # type: ignore[arg-type]
        plan_governance=approvals,
        clock=lambda: NOW,
    )

    with pytest.raises(PlanGovernanceError) as denied:
        service.create_governed_plan(
            author_context,
            unauthorized_decision,
            _command(idempotency_key="unauthorized"),
        )
    assert denied.value.code == "PLAN_AUTHOR_UNAUTHORIZED"

    base = service.create_governed_plan(
        author_context,
        reviewer_author_decision,
        _command(idempotency_key="base"),
    )
    approval = approvals.seed_approved_fixture(
        base,
        context=author_context,
        review_request_id=UUID(int=31),
        review_decision_id=UUID(int=32),
        evidence_sha256="b" * 64,
        approved_by=REVIEWER,
        plan_created_by=CREATOR,
        approved_at=NOW,
    )
    assert approval.state is PlanApprovalState.ACTIVE
    assert base.current.material == MATERIAL
    assert base.current.material_state == MATERIAL_STATE
    assert base.current.input_mode == "relaxation"

    clone = service.create_governed_plan(
        author_context,
        reviewer_author_decision,
        _command(
            idempotency_key="advanced-clone",
            setup_name="Advanced relaxation setup",
            based_on_plan_id=base.id,
            based_on_plan_revision_id=base.current.plan_revision_id,
            override_reason="Use a tighter optimizer tolerance for this approved comparison.",
            ftol=2e-8,
        ),
    )

    assert clone.id != base.id
    assert clone.current.plan_revision_id != base.current.plan_revision_id
    assert clone.current.based_on_plan_id == base.id
    assert clone.current.based_on_plan_revision_id == base.current.plan_revision_id
    assert clone.current.base_diff is not None
    assert clone.current.base_diff["optimizer"] == {
        "before": base.current.canonical()["optimizer"],
        "after": clone.current.canonical()["optimizer"],
    }

    with pytest.raises(PlanGovernanceError) as mismatched:
        service.create_governed_plan(
            author_context,
            reviewer_author_decision,
            _command(
                idempotency_key="wrong-material-hint",
                material=ExactRevisionPin(UUID(int=33), UUID(int=34)),
            ),
        )
    assert mismatched.value.code == "PLAN_SOURCE_INCOMPATIBLE"


def test_exact_context_returns_all_matches_and_append_only_usability_states() -> None:
    author_context = _context(CREATOR, 40)
    manager_context = _context(MANAGER, 41)
    manager_decision = _decision(manager_context, Permission.REVIEW_DECIDE, (Role.DOMAIN_REVIEWER,))
    approvals = InMemoryLinearViscoelasticPlanApproval()
    first = _snapshot(_plan(plan_id=UUID(int=42), revision_id=UUID(int=43), setup_name="Setup A"))
    second = _snapshot(_plan(plan_id=UUID(int=44), revision_id=UUID(int=45), setup_name="Setup B"))
    approvals.seed_approved_fixture(
        first,
        context=author_context,
        review_request_id=UUID(int=46),
        review_decision_id=UUID(int=47),
        approved_by=REVIEWER,
        plan_created_by=CREATOR,
        approved_at=NOW,
    )
    approvals.seed_approved_fixture(
        second,
        context=author_context,
        review_request_id=UUID(int=48),
        review_decision_id=UUID(int=49),
        approved_by=REVIEWER,
        plan_created_by=CREATOR,
        approved_at=NOW,
    )
    query = PlanContextQuery(MATERIAL, MATERIAL_STATE, TEST_DATA, None, "relaxation")

    resolved = approvals.resolve_exact_context(
        context=manager_context,
        decision=_decision(manager_context, Permission.MODELING_READ, (Role.MATERIAL_MODELER,)),
        query=query,
    )
    assert [item.setup_name for item in resolved.matches] == ["Setup A", "Setup B"]
    assert resolved.selection_required is True
    assert "2 active approved linear-viscoelastic setups" in resolved.summary
    assert {item.review_request_id for item in resolved.matches} == {UUID(int=46), UUID(int=48)}

    wrong_context = replace(query, material_state=ExactRevisionPin(UUID(int=22), UUID(int=99)))
    assert (
        approvals.resolve_exact_context(
            context=manager_context,
            decision=_decision(manager_context, Permission.MODELING_READ, (Role.MATERIAL_MODELER,)),
            query=wrong_context,
        ).matches
        == ()
    )

    successor = _snapshot(
        _plan(plan_id=UUID(int=50), revision_id=UUID(int=51), setup_name="Setup successor")
    )
    approvals.seed_approved_fixture(
        successor,
        context=author_context,
        review_request_id=UUID(int=52),
        review_decision_id=UUID(int=53),
        approved_by=REVIEWER,
        plan_created_by=CREATOR,
        approved_at=NOW,
    )
    superseded = approvals.supersede(
        context=manager_context,
        decision=manager_decision,
        plan_id=first.id,
        plan_revision_id=first.current.plan_revision_id,
        successor_plan=successor,
        reason="Replace the active setup with its approved successor.",
    )
    assert superseded.state is PlanApprovalState.SUPERSEDED
    assert superseded.successor_plan_id == successor.id
    assert (
        approvals.get_approval(
            context=manager_context,
            decision=manager_decision,
            plan_id=first.id,
            plan_revision_id=first.current.plan_revision_id,
        ).state
        is PlanApprovalState.SUPERSEDED
    )

    withdrawn = approvals.withdraw(
        context=manager_context,
        decision=manager_decision,
        plan_id=successor.id,
        plan_revision_id=successor.current.plan_revision_id,
        plan_created_by=CREATOR,
        reason="Withdraw the successor after the controlled comparison.",
    )
    assert withdrawn.state is PlanApprovalState.WITHDRAWN
    assert withdrawn.successor_plan_id is None
    remaining = approvals.resolve_exact_context(
        context=manager_context,
        decision=_decision(manager_context, Permission.MODELING_READ, (Role.MATERIAL_MODELER,)),
        query=query,
    )
    assert tuple(item.plan_id for item in remaining.matches) == (second.id,)

    with pytest.raises(PlanGovernanceError) as creator_denied:
        approvals.withdraw(
            context=author_context,
            decision=_decision(author_context, Permission.REVIEW_DECIDE, (Role.DOMAIN_REVIEWER,)),
            plan_id=second.id,
            plan_revision_id=second.current.plan_revision_id,
            plan_created_by=UUID(int=999),
            reason="The creator must not manage this setup.",
        )
    assert creator_denied.value.code == "PLAN_MANAGER_UNAUTHORIZED"


def test_queue_requires_active_approval_and_persists_immutable_execution_evidence() -> None:
    author_context = _context(CREATOR, 60)
    user_context = _context(USER, 61)
    manager_context = _context(MANAGER, 62)
    plan = _snapshot(_plan(plan_id=UUID(int=63), revision_id=UUID(int=64)))
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    repository.save_plan(plan, idempotency_key=None)
    approvals = InMemoryLinearViscoelasticPlanApproval()
    approvals.seed_approved_fixture(
        plan,
        context=author_context,
        review_request_id=UUID(int=65),
        review_decision_id=UUID(int=66),
        evidence_sha256="c" * 64,
        approved_by=REVIEWER,
        plan_created_by=CREATOR,
        approved_at=NOW,
    )
    ids = iter((UUID(int=67), UUID(int=68)))
    service = LinearViscoelasticCalibrationService(
        repository=repository,
        plan_governance=approvals,
        id_factory=lambda: next(ids),
        clock=lambda: NOW,
    )
    execute_decision = _decision(user_context, Permission.CALIBRATION_EXECUTE, (Role.CAE_ANALYST,))

    accepted = service.queue_run(
        user_context,
        execute_decision,
        QueueLinearViscoelasticCalibrationRun(
            plan_id=plan.id,
            plan_revision_id=plan.current.plan_revision_id,
            change_reason="Run the selected active approved setup.",
            idempotency_key="run-approved-plan",
        ),
    )
    run = repository.get_run(accepted.run_id)
    assert run.approval_request_id == UUID(int=65)
    assert run.approval_decision_id == UUID(int=66)
    assert run.approval_evidence_sha256 == "c" * 64
    assert run.approval_state == PlanApprovalState.ACTIVE.value
    assert run.approval_approved_by == REVIEWER
    assert run.execution_material == MATERIAL
    assert run.execution_material_state == MATERIAL_STATE
    assert run.execution_test_data == TEST_DATA
    assert run.execution_input_mode == "relaxation"

    manager_decision = _decision(manager_context, Permission.REVIEW_DECIDE, (Role.DOMAIN_REVIEWER,))
    approvals.withdraw(
        context=manager_context,
        decision=manager_decision,
        plan_id=plan.id,
        plan_revision_id=plan.current.plan_revision_id,
        plan_created_by=CREATOR,
        reason="Withdraw the setup from future queue submissions.",
    )
    with pytest.raises(PlanGovernanceError) as inactive:
        service.queue_run(
            user_context,
            execute_decision,
            QueueLinearViscoelasticCalibrationRun(
                plan_id=plan.id,
                plan_revision_id=plan.current.plan_revision_id,
                change_reason="Attempt a new run after withdrawal.",
                idempotency_key="run-withdrawn-plan",
            ),
        )
    assert inactive.value.code == "PLAN_APPROVAL_WITHDRAWN"
