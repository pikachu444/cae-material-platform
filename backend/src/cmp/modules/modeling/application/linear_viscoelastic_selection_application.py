"""Selection acknowledgement and model-promotion orchestration for calibration results."""

from __future__ import annotations

from uuid import UUID

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationApplicationState,
    CalibrationSelectionSnapshot,
    CreateLinearViscoelasticCalibrationSelection,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
    PromoteLinearViscoelasticCalibrationSelection,
    _reason,
    _require,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelSnapshot,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    PromoteLinearViscoelasticCalibrationSelection as PromoteSelectionToModel,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    LinearViscoelasticInputError,
    LinearViscoelasticSelection,
    LinearViscoelasticSelectionError,
    RunStatus,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ModelingError
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    InvalidLinearViscoelasticModel,
    LinearViscoelasticConflict,
)


class LinearViscoelasticSelectionApplication:
    """Application component for engineer acknowledgement and exact IR promotion."""

    def create_selection(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateLinearViscoelasticCalibrationSelection,
    ) -> CalibrationSelectionSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        reason = _reason(command.reason)
        run = self._repository.get_run(command.run_id, context=context, decision=decision)
        if (
            run.plan_revision_id != command.plan_revision_id
            or run.result is None
            or run.result.status.value != "succeeded"
        ):
            raise LinearViscoelasticCalibrationConflict(
                "Selection requires the exact successful Run"
            )
        candidate = next(
            (item for item in run.result.candidates if item.candidate_id == command.candidate_id),
            None,
        )
        if candidate is None:
            raise LinearViscoelasticCalibrationNotFound("candidate is not visible")
        if candidate.digest != command.candidate_sha256:
            raise LinearViscoelasticCalibrationConflict(
                "candidate digest does not match server result"
            )
        for acknowledgement in command.warning_acknowledgements:
            if str(acknowledgement.get("candidate_id")) != str(command.candidate_id) or str(
                acknowledgement.get("run_id")
            ) != str(command.run_id):
                raise LinearViscoelasticSelectionError(
                    "warning acknowledgement references a different candidate/run"
                )
        selection = LinearViscoelasticSelection(
            selection_id=self._new_id(),
            selection_revision_id=self._new_id(),
            plan_revision_id=command.plan_revision_id,
            run_id=command.run_id,
            candidate_id=command.candidate_id,
            candidate_digest=candidate.digest,
            reason=reason,
            warning_acknowledgements=command.warning_acknowledgements,
            actor=context.principal.id,
            created_at=self._clock(),
        )
        return self._repository.save_selection(
            CalibrationSelectionSnapshot(
                selection,
                run.classification,
                organization_id=context.organization_id,
                project_id=context.project_id,
            ),
            idempotency_key=command.idempotency_key,
            context=context,
            decision=decision,
        )

    def get_selection(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> CalibrationSelectionSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_selection(selection_id, context=context, decision=decision)

    def promote_selection(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteLinearViscoelasticCalibrationSelection,
    ) -> LinearViscoelasticModelSnapshot:
        """Promote one exact Selection while retaining Recommendation as separate evidence."""

        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        if self._linear_viscoelastic_models is None or self._authorization is None:
            raise LinearViscoelasticCalibrationConflict(
                "linear-viscoelastic IR promotion is unavailable"
            )
        selection_snapshot = self._repository.get_selection(
            command.selection_id,
            context=context,
            decision=decision,
        )
        selection = selection_snapshot.value
        run = self._repository.get_run(
            selection.run_id,
            context=context,
            decision=decision,
        )
        plan_snapshot = self._repository.get_plan(
            run.plan_id,
            context=context,
            decision=decision,
        )
        result = run.result
        if (
            result is None
            or result.status is not RunStatus.SUCCEEDED
            or result.recommendation is None
            or selection.plan_revision_id != plan_snapshot.current.plan_revision_id
            or selection.run_id != run.id
        ):
            raise LinearViscoelasticCalibrationConflict(
                "promotion requires the exact successful Plan, Run, Recommendation, and Selection"
            )
        candidate = next(
            (value for value in result.candidates if value.candidate_id == selection.candidate_id),
            None,
        )
        if candidate is None or candidate.digest != selection.candidate_digest:
            raise LinearViscoelasticCalibrationConflict(
                "immutable Selection Candidate is missing or has a different digest"
            )
        plan = plan_snapshot.current
        if plan.test_data is None or plan.import_profile is None:
            raise LinearViscoelasticCalibrationConflict(
                "promotion Plan lacks exact governed upstream revisions"
            )
        if self._input_resolver is not None:
            try:
                self._input_resolver.assert_current_revisions(
                    context,
                    decision,
                    test_data=plan.test_data,
                    import_profile=plan.import_profile,
                    processing_output=plan.processing_output,
                )
            except LinearViscoelasticInputError as error:
                raise LinearViscoelasticCalibrationConflict(
                    f"{error}; {error.recovery_hint}"
                ) from error
        modeling_write = self._authorization.authorize(
            context,
            Permission.MODELING_WRITE,
        )
        try:
            return self._linear_viscoelastic_models.promote_calibration_selection(
                context,
                modeling_write,
                PromoteSelectionToModel(
                    material_id=command.material_id,
                    material_revision_id=command.material_revision_id,
                    material_state_id=command.material_state_id,
                    material_state_revision_id=command.material_state_revision_id,
                    property_set_id=command.property_set_id,
                    property_set_revision_id=command.property_set_revision_id,
                    classification=plan_snapshot.classification,
                    plan=plan,
                    run=result,
                    candidate=candidate,
                    recommendation=result.recommendation,
                    selection=selection,
                    change_reason=command.change_reason,
                ),
            )
        except LinearViscoelasticConflict as error:
            raise LinearViscoelasticCalibrationConflict(str(error)) from error
        except InvalidLinearViscoelasticModel as error:
            raise LinearViscoelasticSelectionError(str(error)) from error
        except ModelingError as error:
            raise LinearViscoelasticCalibrationConflict(str(error)) from error
