"""Plan creation and governed-input orchestration for linear-viscoelastic calibration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationApplicationState,
    CalibrationPlanSnapshot,
    CreateGovernedLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationPlan,
    CreateProcessedLinearViscoelasticCalibrationPlan,
    LinearViscoelasticCalibrationConflict,
    _reason,
    _require,
    _run_awaitable,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ResolveGovernedViscoelasticInput,
    ResolveProcessedViscoelasticInput,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_governance import (
    PlanGovernanceError,
    canonical_diff,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CanonicalViscoelasticInput,
    ExactRevisionPin,
    LinearViscoelasticCalibrationPlan,
    ParameterBound,
    automatic_candidate_term_counts,
)


def _governance_requested(command: object) -> bool:
    return any(
        getattr(command, field, None) is not None
        for field in (
            "setup_name",
            "material",
            "material_state",
            "input_mode",
            "based_on_plan_id",
            "based_on_plan_revision_id",
            "override_reason",
        )
    )


def _assert_plan_author(
    context: SecurityContext,
    decision: AuthorizationDecision,
    *,
    governed: bool,
) -> None:
    if governed and Role.DOMAIN_REVIEWER not in decision.roles:
        raise PlanGovernanceError(
            "linear-viscoelastic Plan authoring requires DOMAIN_REVIEWER",
            code="PLAN_AUTHOR_UNAUTHORIZED",
            recovery_hint="Use CALIBRATION_EXECUTE with the distinct domain-reviewer role.",
        )


def _assert_hint(
    name: str,
    hint: ExactRevisionPin | None,
    resolved: ExactRevisionPin | None,
) -> None:
    if hint is None:
        return
    if (
        resolved is None
        or hint.aggregate_id != resolved.aggregate_id
        or hint.revision_id != resolved.revision_id
    ):
        raise PlanGovernanceError(
            f"client {name} hint does not match the exact server-resolved source",
            code="PLAN_SOURCE_INCOMPATIBLE",
            recovery_hint="Use the Material and Material State pins returned by the exact source.",
        )


def _governance_fields(
    command: object,
    resolved: object,
) -> dict[str, object]:
    requested = _governance_requested(command)
    if not requested:
        return {}
    material = getattr(resolved, "material", None)
    material_state = getattr(resolved, "material_state", None)
    if material is None or material_state is None:
        raise PlanGovernanceError(
            "the exact source has no Material and Material State identity pins",
            code="PLAN_SOURCE_INCOMPATIBLE",
            recovery_hint="Use governed Test Data with verified Material lineage.",
        )
    _assert_hint("Material", getattr(command, "material", None), material)
    _assert_hint("Material State", getattr(command, "material_state", None), material_state)
    input_mode = getattr(command, "input_mode", None)
    if input_mode is not None and input_mode != resolved.semantics.mode:
        raise PlanGovernanceError(
            "input_mode must equal the server-resolved source mode",
            code="PLAN_SOURCE_INCOMPATIBLE",
            recovery_hint="Use the exact mode returned by the governed source resolver.",
        )
    input_mode = resolved.semantics.mode
    based_on_plan_id = getattr(command, "based_on_plan_id", None)
    based_on_plan_revision_id = getattr(command, "based_on_plan_revision_id", None)
    if (based_on_plan_id is None) != (based_on_plan_revision_id is None):
        raise PlanGovernanceError(
            "Advanced clone base Plan identity and revision must be paired",
            code="PLAN_SOURCE_INCOMPATIBLE",
            recovery_hint="Provide both exact base Plan identity and revision, or neither.",
        )
    override_reason = getattr(command, "override_reason", None)
    if based_on_plan_id is None and override_reason is not None:
        raise PlanGovernanceError(
            "override_reason requires an exact approved base Plan",
            code="PLAN_OVERRIDE_REASON_INVALID",
            recovery_hint="Provide an exact approved base Plan when submitting an override.",
        )
    if based_on_plan_id is not None and (
        not isinstance(override_reason, str)
        or not override_reason.strip()
        or override_reason != override_reason.strip()
    ):
        raise PlanGovernanceError(
            "Advanced clone requires a trimmed override_reason",
            code="PLAN_OVERRIDE_REASON_REQUIRED",
            recovery_hint="Explain the controlled change from the approved base Plan.",
        )
    return {
        "setup_name": getattr(command, "setup_name", None),
        "material": material,
        "material_state": material_state,
        "input_mode": input_mode,
        "based_on_plan_id": based_on_plan_id,
        "based_on_plan_revision_id": based_on_plan_revision_id,
        "override_reason": override_reason,
    }


def _candidate_scope(
    command: object,
    resolved: object,
) -> tuple[
    str | None,
    tuple[int, ...],
    Mapping[int, tuple[ParameterBound, ...]],
    Mapping[int, tuple[tuple[Decimal | float, ...], ...]],
]:
    """Resolve manual transport or derive the complete automatic scope after source resolution."""

    mode = getattr(command, "candidate_scope_mode", None)
    if mode in (None, "manual"):
        return (
            None,
            tuple(getattr(command, "term_counts")),
            dict(getattr(command, "parameter_bounds")),
            dict(getattr(command, "start_vectors")),
        )
    if mode != "automatic":
        raise PlanGovernanceError(
            "candidate_scope_mode must be automatic or manual",
            code="PLAN_CANDIDATE_SCOPE_INVALID",
            recovery_hint="Choose automatic or provide an exact feasible manual term subset.",
        )
    term_counts = tuple(getattr(command, "term_counts"))
    parameter_bounds = dict(getattr(command, "parameter_bounds"))
    start_vectors = dict(getattr(command, "start_vectors"))
    expected_terms = automatic_candidate_term_counts(resolved.semantics)
    if term_counts != expected_terms:
        raise PlanGovernanceError(
            "automatic candidate scope must contain every feasible term count in order",
            code="PLAN_CANDIDATE_SCOPE_INVALID",
            recovery_hint="Use the complete feasible range returned for this exact input.",
        )
    return "automatic", term_counts, parameter_bounds, start_vectors


class LinearViscoelasticPlanApplication:
    """Application component for immutable Plans and exact governed source pins."""

    def create_governed_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateGovernedLinearViscoelasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        """Resolve source-controlled pins and create one immutable production Plan."""

        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        governed = _governance_requested(command)
        _assert_plan_author(context, decision, governed=governed)
        if self._input_resolver is None:
            raise LinearViscoelasticCalibrationConflict(
                "governed calibration input resolution is unavailable"
            )
        resolved = _run_awaitable(
            self._input_resolver.resolve(
                context,
                decision,
                ResolveGovernedViscoelasticInput(
                    test_data_id=command.test_data_id,
                    test_data_revision_id=command.test_data_revision_id,
                    selected_temperature_k=command.selected_temperature_k,
                    point_dispositions=command.point_dispositions,
                    availability=command.availability,
                ),
            )
        )
        if command.idempotency_key is None:
            plan_id = self._new_id()
            plan_revision_id = self._new_id()
        else:
            identity_scope = (
                f"{context.organization_id}:{context.project_id}:{command.idempotency_key}"
            )
            plan_id = uuid5(
                NAMESPACE_URL,
                f"urn:cmp:modeling:linear-viscoelastic-calibration-plan:{identity_scope}",
            )
            plan_revision_id = uuid5(
                NAMESPACE_URL,
                f"urn:cmp:modeling:linear-viscoelastic-calibration-plan-revision:{identity_scope}",
            )
        governance = _governance_fields(command, resolved)
        candidate_governance = {
            key: value
            for key, value in governance.items()
            if key not in {"based_on_plan_id", "based_on_plan_revision_id", "override_reason"}
        }
        candidate_scope_mode, term_counts, parameter_bounds, start_vectors = _candidate_scope(
            command, resolved
        )
        plan = LinearViscoelasticCalibrationPlan(
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            test_data=resolved.test_data,
            canonical_artifact=resolved.canonical_artifact,
            normalized_artifact=resolved.normalized_artifact,
            raw_source_sha256=resolved.raw_source_sha256,
            import_profile=resolved.import_profile,
            profile_sha256=resolved.profile_sha256,
            input_semantics=resolved.semantics,
            term_counts=term_counts,
            parameter_bounds=parameter_bounds,
            start_vectors=start_vectors,
            weights=command.weights,
            recommendation_policy=command.recommendation_policy,
            ftol=command.ftol,
            xtol=command.xtol,
            gtol=command.gtol,
            max_nfev=command.max_nfev,
            statuses=command.availability,
            candidate_scope_mode=candidate_scope_mode,
            **candidate_governance,
        )
        plan = self._attach_server_derived_diff(
            context,
            decision,
            plan,
            based_on_plan_id=governance.get("based_on_plan_id"),
            based_on_plan_revision_id=governance.get("based_on_plan_revision_id"),
            override_reason=governance.get("override_reason"),
        )
        return self.create_plan(
            context,
            decision,
            CreateLinearViscoelasticCalibrationPlan(
                plan=plan,
                classification=resolved.classification,
                change_reason=command.change_reason,
                idempotency_key=command.idempotency_key,
            ),
        )

    def create_processed_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateProcessedLinearViscoelasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        """Create a Plan from one exact confirmed Processing Output revision."""

        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        governed = _governance_requested(command)
        _assert_plan_author(context, decision, governed=governed)
        if self._input_resolver is None:
            raise LinearViscoelasticCalibrationConflict(
                "processed calibration input resolution is unavailable"
            )
        resolved = _run_awaitable(
            self._input_resolver.resolve_processing_output(
                context,
                decision,
                ResolveProcessedViscoelasticInput(
                    processing_output_id=command.processing_output_id,
                    processing_output_revision_id=command.processing_output_revision_id,
                    availability=command.availability,
                ),
            )
        )
        if command.idempotency_key is None:
            plan_id = self._new_id()
            plan_revision_id = self._new_id()
        else:
            identity_scope = (
                f"{context.organization_id}:{context.project_id}:{command.idempotency_key}"
            )
            plan_id = uuid5(
                NAMESPACE_URL,
                f"urn:cmp:modeling:linear-viscoelastic-calibration-plan:{identity_scope}",
            )
            plan_revision_id = uuid5(
                NAMESPACE_URL,
                f"urn:cmp:modeling:linear-viscoelastic-calibration-plan-revision:{identity_scope}",
            )
        governance = _governance_fields(command, resolved)
        candidate_governance = {
            key: value
            for key, value in governance.items()
            if key not in {"based_on_plan_id", "based_on_plan_revision_id", "override_reason"}
        }
        candidate_scope_mode, term_counts, parameter_bounds, start_vectors = _candidate_scope(
            command, resolved
        )
        plan = LinearViscoelasticCalibrationPlan(
            plan_id=plan_id,
            plan_revision_id=plan_revision_id,
            test_data=resolved.test_data,
            canonical_artifact=resolved.canonical_artifact,
            normalized_artifact=resolved.normalized_artifact,
            raw_source_sha256=resolved.raw_source_sha256,
            import_profile=resolved.import_profile,
            profile_sha256=resolved.profile_sha256,
            processing_output=resolved.processing_output,
            processing_metadata_artifact=resolved.processing_metadata_artifact,
            processing_result_artifact=resolved.processing_result_artifact,
            input_semantics=resolved.semantics,
            term_counts=term_counts,
            parameter_bounds=parameter_bounds,
            start_vectors=start_vectors,
            weights=command.weights,
            recommendation_policy=command.recommendation_policy,
            ftol=command.ftol,
            xtol=command.xtol,
            gtol=command.gtol,
            max_nfev=command.max_nfev,
            statuses=command.availability,
            candidate_scope_mode=candidate_scope_mode,
            **candidate_governance,
        )
        plan = self._attach_server_derived_diff(
            context,
            decision,
            plan,
            based_on_plan_id=governance.get("based_on_plan_id"),
            based_on_plan_revision_id=governance.get("based_on_plan_revision_id"),
            override_reason=governance.get("override_reason"),
        )
        return self.create_plan(
            context,
            decision,
            CreateLinearViscoelasticCalibrationPlan(
                plan=plan,
                classification=resolved.classification,
                change_reason=command.change_reason,
                idempotency_key=command.idempotency_key,
            ),
        )

    def create_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateLinearViscoelasticCalibrationPlan,
    ) -> CalibrationPlanSnapshot:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        _assert_plan_author(context, decision, governed=command.plan.is_governed)
        reason = _reason(command.change_reason)
        content_hash = command.plan.digest
        value = CalibrationPlanSnapshot(
            id=command.plan.plan_id,
            current=command.plan,
            content_hash=content_hash,
            classification=command.classification,
            created_at=self._clock(),
            created_by=context.principal.id,
            change_reason=reason,
            organization_id=context.organization_id,
            project_id=context.project_id,
        )
        return self._repository.save_plan(
            value,
            idempotency_key=command.idempotency_key,
            context=context,
            decision=decision,
        )

    def _attach_server_derived_diff(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan: LinearViscoelasticCalibrationPlan,
        *,
        based_on_plan_id: object,
        based_on_plan_revision_id: object,
        override_reason: object,
    ) -> LinearViscoelasticCalibrationPlan:
        if based_on_plan_id is None and based_on_plan_revision_id is None:
            return plan
        if not isinstance(based_on_plan_id, UUID) or not isinstance(
            based_on_plan_revision_id, UUID
        ):
            raise PlanGovernanceError(
                "Advanced clone requires exact base Plan identity and revision",
                code="PLAN_SOURCE_INCOMPATIBLE",
                recovery_hint="Provide the exact approved base Plan revision.",
            )
        if not isinstance(override_reason, str) or not override_reason.strip():
            raise PlanGovernanceError(
                "Advanced clone requires a trimmed override_reason",
                code="PLAN_OVERRIDE_REASON_REQUIRED",
                recovery_hint="Explain the controlled change from the approved base Plan.",
            )
        base = self._repository.get_plan(
            based_on_plan_id,
            context=context,
            decision=decision,
        )
        if base.current.plan_revision_id != based_on_plan_revision_id:
            raise PlanGovernanceError(
                "Advanced clone base Plan revision is stale",
                code="PLAN_SOURCE_STALE",
                recovery_hint="Read the exact current base Plan revision and retry.",
            )
        if not base.current.is_governed or self._plan_governance is None:
            raise PlanGovernanceError(
                "Advanced clone requires an active approved base Plan",
                code="PLAN_BASE_APPROVAL_REQUIRED",
                recovery_hint="Choose an active approved Plan as the Advanced base.",
            )
        self._plan_governance.assert_executable(
            context=context,
            decision=decision,
            plan=base.current,
            classification=base.classification,
        )
        return replace(
            plan,
            based_on_plan_id=based_on_plan_id,
            based_on_plan_revision_id=based_on_plan_revision_id,
            override_reason=override_reason,
            base_diff=canonical_diff(base.current, plan),
        )

    def bind_input(
        self: CalibrationApplicationState, plan_id: UUID, value: CanonicalViscoelasticInput
    ) -> None:
        """Bind exact staged source data for a worker/test harness; bytes remain Artifacts."""

        self._inputs[plan_id] = value

    def get_plan(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> CalibrationPlanSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_plan(plan_id, context=context, decision=decision)
