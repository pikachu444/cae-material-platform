"""Read-only projection of the exact processed values used by polymer calibration."""

from __future__ import annotations

from uuid import UUID

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationApplicationState,
    LinearViscoelasticCalibrationConflict,
    _require,
    _run_awaitable,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    ProcessedViscoelasticFitInput,
    ReadProcessedViscoelasticFitInput,
)


class LinearViscoelasticFitInputApplication:
    """Expose validated Fit values without leaking Artifact or digest metadata."""

    def get_processed_fit_input(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        processing_output_id: UUID,
        processing_output_revision_id: UUID,
    ) -> ProcessedViscoelasticFitInput:
        _require(context, decision, Permission.MODELING_READ)
        if self._input_resolver is None:
            raise LinearViscoelasticCalibrationConflict(
                "processed calibration input resolution is unavailable"
            )
        return _run_awaitable(
            self._input_resolver.read_processing_output_fit_input(
                context,
                decision,
                ReadProcessedViscoelasticFitInput(
                    processing_output_id=processing_output_id,
                    processing_output_revision_id=processing_output_revision_id,
                ),
            )
        )


__all__ = ("LinearViscoelasticFitInputApplication",)
