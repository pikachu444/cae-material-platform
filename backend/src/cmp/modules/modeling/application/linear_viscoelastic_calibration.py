"""Stable application facade for governed linear-viscoelastic calibration.

Command responsibilities live in plan, run, and selection application components.  This facade
keeps the established service/import surface while composing those cohesive components around one
explicit dependency set.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationAcceptedResultConflict,
    CalibrationApplicationState,
    CalibrationErrorCode,
    CalibrationJobReference,
    CalibrationJobTerminalConflict,
    CalibrationPlanSnapshot,
    CalibrationRunProjection,
    CalibrationSelectionSnapshot,
    CreateGovernedLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationPlan,
    CreateLinearViscoelasticCalibrationSelection,
    CreateProcessedLinearViscoelasticCalibrationPlan,
    ExecutionLedgerEntry,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
    LinearViscoelasticCalibrationRepository,
    PromoteLinearViscoelasticCalibrationSelection,
    QueueLinearViscoelasticCalibrationRun,
)
from cmp.modules.modeling.application.linear_viscoelastic_memory_repository import (
    InMemoryLinearViscoelasticCalibrationRepository,
)
from cmp.modules.modeling.application.linear_viscoelastic_plan_application import (
    LinearViscoelasticPlanApplication,
)
from cmp.modules.modeling.application.linear_viscoelastic_run_application import (
    LinearViscoelasticRunApplication,
    failure_code_for_execution,
)
from cmp.modules.modeling.application.linear_viscoelastic_selection_application import (
    LinearViscoelasticSelectionApplication,
)

if TYPE_CHECKING:
    from cmp.modules.artifacts.application.content import ArtifactService
    from cmp.modules.jobs.application.jobs import JobService
    from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
        GovernedLinearViscoelasticInputResolver,
    )
    from cmp.modules.modeling.application.linear_viscoelasticity import (
        LinearViscoelasticModelService,
    )
    from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
        CanonicalViscoelasticInput,
    )
    from cmp.modules.plugins.application.registry import PluginRegistryService


class LinearViscoelasticCalibrationService(
    LinearViscoelasticPlanApplication,
    LinearViscoelasticRunApplication,
    LinearViscoelasticSelectionApplication,
):
    """Compose the bounded plan, run, and selection application components."""

    def __init__(
        self,
        *,
        repository: LinearViscoelasticCalibrationRepository,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
        job_service: JobService | None = None,
        artifact_service: ArtifactService | None = None,
        plugin_registry: PluginRegistryService | None = None,
        authorization: AuthorizationService | None = None,
        input_resolver: GovernedLinearViscoelasticInputResolver | None = None,
        linear_viscoelastic_models: LinearViscoelasticModelService | None = None,
        allow_reference_execution: bool = False,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))
        self._inputs: dict[UUID, CanonicalViscoelasticInput] = {}
        self._job_service = job_service
        self._artifact_service = artifact_service
        self._plugin_registry = plugin_registry
        self._authorization = authorization
        self._input_resolver = input_resolver
        self._linear_viscoelastic_models = linear_viscoelastic_models
        self._allow_reference_execution = allow_reference_execution

    def _new_id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("calibration id_factory returned a zero UUID")
        return value


__all__ = (
    "CalibrationAcceptedResultConflict",
    "CalibrationApplicationState",
    "CalibrationErrorCode",
    "CalibrationJobReference",
    "CalibrationJobTerminalConflict",
    "CalibrationPlanSnapshot",
    "CalibrationRunProjection",
    "CalibrationSelectionSnapshot",
    "CreateGovernedLinearViscoelasticCalibrationPlan",
    "CreateLinearViscoelasticCalibrationPlan",
    "CreateLinearViscoelasticCalibrationSelection",
    "CreateProcessedLinearViscoelasticCalibrationPlan",
    "ExecutionLedgerEntry",
    "InMemoryLinearViscoelasticCalibrationRepository",
    "LinearViscoelasticCalibrationConflict",
    "LinearViscoelasticCalibrationNotFound",
    "LinearViscoelasticCalibrationRepository",
    "LinearViscoelasticCalibrationService",
    "LinearViscoelasticPlanApplication",
    "LinearViscoelasticRunApplication",
    "LinearViscoelasticSelectionApplication",
    "PromoteLinearViscoelasticCalibrationSelection",
    "QueueLinearViscoelasticCalibrationRun",
    "failure_code_for_execution",
)
