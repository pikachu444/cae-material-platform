"""Plan creation and governed-input orchestration for linear-viscoelastic calibration."""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
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
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CanonicalViscoelasticInput,
    LinearViscoelasticCalibrationPlan,
)


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
            term_counts=command.term_counts,
            parameter_bounds=command.parameter_bounds,
            start_vectors=command.start_vectors,
            weights=command.weights,
            recommendation_policy=command.recommendation_policy,
            ftol=command.ftol,
            xtol=command.xtol,
            gtol=command.gtol,
            max_nfev=command.max_nfev,
            statuses=command.availability,
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
            term_counts=command.term_counts,
            parameter_bounds=command.parameter_bounds,
            start_vectors=command.start_vectors,
            weights=command.weights,
            recommendation_policy=command.recommendation_policy,
            ftol=command.ftol,
            xtol=command.xtol,
            gtol=command.gtol,
            max_nfev=command.max_nfev,
            statuses=command.availability,
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
