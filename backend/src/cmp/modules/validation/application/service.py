"""T-27 versioned validation template, Plan, and reference runner orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.datasets.application.service import (
    CalibrationDatasetSource,
    DatasetSelectionRevisionSnapshot,
    DatasetService,
)
from cmp.modules.exporting.application.service import (
    RevisionSnapshot as SolverCardRevisionSnapshot,
)
from cmp.modules.exporting.application.service import (
    SolverCardService,
)
from cmp.modules.exporting.domain.openradioss_elast import ReferenceOpenRadiossCardContent
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MaterialModelService,
)
from cmp.modules.modeling.application.service import (
    RevisionSnapshot as MaterialModelRevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceLinearElasticContent
from cmp.modules.validation.domain.reference_virtual_specimen import (
    REFERENCE_DECK_SCHEMA_ID,
    REFERENCE_NATIVE_RESULT_SCHEMA_ID,
    REFERENCE_PLAN_SCHEMA_ID,
    REFERENCE_SCHEMA_VERSION,
    REFERENCE_STDERR_SCHEMA_ID,
    REFERENCE_STDOUT_SCHEMA_ID,
    REFERENCE_TEMPLATE_SCHEMA_ID,
    InvalidNativeResult,
    InvalidValidationPlan,
    InvalidValidationTemplate,
    ReferenceRunnerOutcome,
    ReferenceValidationPlanContent,
    ReferenceVirtualSpecimenTemplateContent,
    SolverTerminationStatus,
    ValidationArtifactReference,
    ValidationConflict,
    ValidationExecutionMode,
    ValidationRunResultManifestContent,
    ValidationRunStatus,
    map_reference_runner_outcome,
    reference_mock_native_result_bytes,
    reference_runner_stderr,
    reference_runner_stdout,
    render_reference_deck,
    result_manifest_bytes,
    result_manifest_sha256,
    validate_external_job_reference,
    validate_reference_native_result_bytes,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

VALIDATION_TEMPLATE_AGGREGATE_TYPE = "validation.validation_template"
VALIDATION_PLAN_AGGREGATE_TYPE = "validation.validation_plan"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class ValidationTemplateSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent]


@dataclass(frozen=True, slots=True)
class ValidationPlanSnapshot:
    id: UUID
    current: RevisionSnapshot[ReferenceValidationPlanContent]


@dataclass(frozen=True, slots=True)
class ValidationRun:
    id: UUID
    classification: DataClassification
    plan_id: UUID
    plan_revision_id: UUID
    template_id: UUID
    template_revision_id: UUID
    material_model_id: UUID
    material_model_revision_id: UUID
    solver_card_id: UUID
    solver_card_revision_id: UUID
    experimental_selection_id: UUID
    experimental_selection_revision_id: UUID
    execution_mode: ValidationExecutionMode
    runner_id: str
    runner_version: str
    runner_digest: str
    status: ValidationRunStatus
    deck: ValidationArtifactReference
    external_job_reference: str | None
    failure_code: str | None
    submitted_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    created_by: UUID
    request_id: UUID
    trace_id: str
    change_reason: str


@dataclass(frozen=True, slots=True)
class ValidationRunResultManifest:
    id: UUID
    content: ValidationRunResultManifestContent
    manifest_artifact: ValidationArtifactReference
    manifest_sha256: str
    created_at: datetime
    created_by: UUID


@dataclass(frozen=True, slots=True)
class ValidationRunDetail:
    run: ValidationRun
    result_manifest: ValidationRunResultManifest | None


@dataclass(frozen=True, slots=True)
class CreateReferenceValidationTemplate:
    classification: DataClassification
    content: ReferenceVirtualSpecimenTemplateContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceValidationTemplate:
    expected_current_revision_id: UUID
    content: ReferenceVirtualSpecimenTemplateContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceValidationPlan:
    classification: DataClassification
    content: ReferenceValidationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseReferenceValidationPlan:
    expected_current_revision_id: UUID
    content: ReferenceValidationPlanContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class SubmitValidationRun:
    plan_id: UUID
    plan_revision_id: UUID
    execution_mode: ValidationExecutionMode
    external_job_reference: str | None
    change_reason: str


@dataclass(frozen=True, slots=True)
class AttachManualValidationResult:
    stdout_text: str
    stderr_text: str
    native_result_text: str
    change_reason: str


class ValidationRepository(Protocol):
    def template_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceVirtualSpecimenTemplateContent]: ...

    def plan_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceValidationPlanContent]: ...

    def get_template(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
    ) -> ValidationTemplateSnapshot: ...

    def get_template_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
        template_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent]: ...

    def list_templates(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ValidationTemplateSnapshot, ...]: ...

    def get_plan(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ValidationPlanSnapshot: ...

    def get_plan_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        plan_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceValidationPlanContent]: ...

    def list_plans(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
    ) -> tuple[ValidationPlanSnapshot, ...]: ...

    def create_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ValidationRun,
    ) -> ValidationRun: ...

    def get_run_detail(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ValidationRunDetail: ...

    def start_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ValidationRun: ...

    def cancel_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        reason: str,
    ) -> ValidationRun: ...

    def record_result_manifest(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        manifest: ValidationRunResultManifest,
        terminal_status: ValidationRunStatus,
        failure_code: str | None,
        change_reason: str,
    ) -> ValidationRunDetail: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise ValidationConflict("authorization decision does not match Validation request")


def _reason(value: str) -> str:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValidationConflict("change_reason must be trimmed and contain 1..2000 characters")
    return value


def _reference(record: ArtifactRecord) -> ValidationArtifactReference:
    return ValidationArtifactReference(record.artifact.id, record.artifact.sha256)


class ReferenceValidationService:
    """Build immutable T-27 template/Plan/run facts without an actual solver process."""

    def __init__(
        self,
        *,
        repository: ValidationRepository,
        datasets: DatasetService,
        material_models: MaterialModelService,
        solver_cards: SolverCardService,
        artifacts: ArtifactService,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._datasets = datasets
        self._material_models = material_models
        self._solver_cards = solver_cards
        self._artifacts = artifacts
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("validation id_factory returned a zero UUID")
        return value

    def create_template(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceValidationTemplate,
    ) -> ValidationTemplateSnapshot:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        template_id = self._id()
        record = RevisionService(
            aggregate_type=VALIDATION_TEMPLATE_AGGREGATE_TYPE,
            store=self._repository.template_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=template_id,
                scope=scope,
                schema_id=REFERENCE_TEMPLATE_SCHEMA_ID,
                schema_version=REFERENCE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ValidationTemplateSnapshot(template_id, RevisionSnapshot(record, command.content))

    def revise_template(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
        command: ReviseReferenceValidationTemplate,
    ) -> ValidationTemplateSnapshot:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        current = self._repository.get_template(
            context=context, decision=decision, template_id=template_id
        )
        if current.current.content.template_label != command.content.template_label:
            raise ValidationConflict("Validation Template label is a stable identity")
        record = RevisionService(
            aggregate_type=VALIDATION_TEMPLATE_AGGREGATE_TYPE,
            store=self._repository.template_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=template_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_TEMPLATE_SCHEMA_ID,
                schema_version=REFERENCE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ValidationTemplateSnapshot(template_id, RevisionSnapshot(record, command.content))

    def get_template(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        template_id: UUID,
    ) -> ValidationTemplateSnapshot:
        _require(context, decision, Permission.VALIDATION_READ)
        return self._repository.get_template(
            context=context, decision=decision, template_id=template_id
        )

    def list_templates(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[ValidationTemplateSnapshot, ...]:
        _require(context, decision, Permission.VALIDATION_READ)
        if not 1 <= limit <= 200:
            raise InvalidValidationTemplate("limit must be between 1 and 200")
        return self._repository.list_templates(context=context, decision=decision, limit=limit)

    def _plan_inputs(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        content: ReferenceValidationPlanContent,
    ) -> tuple[
        RevisionSnapshot[ReferenceVirtualSpecimenTemplateContent],
        MaterialModelRevisionSnapshot[ReferenceLinearElasticContent],
        SolverCardRevisionSnapshot[ReferenceOpenRadiossCardContent],
        DatasetSelectionRevisionSnapshot,
    ]:
        """Resolve fixed revisions only through owning module application services."""

        template = self._repository.get_template_revision(
            context=context,
            decision=decision,
            template_id=content.template_id,
            template_revision_id=content.template_revision_id,
        )
        model = self._material_models.get_material_model_revision_for_validation(
            context,
            decision,
            content.material_model_id,
            content.material_model_revision_id,
        )
        card = self._solver_cards.get_solver_card_revision_for_validation(
            context,
            decision,
            content.solver_card_id,
            content.solver_card_revision_id,
        )
        selection = self._datasets.get_reference_dataset_selection_revision_for_validation(
            context,
            decision,
            content.experimental_selection_id,
            content.experimental_selection_revision_id,
        )
        scope = template.record.scope
        if (
            model.record.scope != scope
            or card.record.scope != scope
            or selection.revision.record.scope != scope
        ):
            raise ValidationConflict("Validation Plan inputs must share tenant and classification")
        if (
            card.content.material_model_id != content.material_model_id
            or card.content.material_model_revision_id != content.material_model_revision_id
        ):
            raise ValidationConflict("Solver Card must pin the exact Material Model IR in the Plan")
        if (
            card.content.target_solver,
            card.content.target_version,
            card.content.target_unit_system,
        ) != (
            template.content.target_solver,
            template.content.target_version,
            template.content.target_unit_system,
        ):
            raise ValidationConflict("Template target and frozen Solver Card target must match")
        source: CalibrationDatasetSource = self._datasets.get_dataset_source_for_validation(
            context,
            decision,
            selection.revision.content.dataset_revision_id,
        )
        if source.material_state_id != model.content.material_state_id:
            raise ValidationConflict(
                "experimental Selection must belong to the Material State of the pinned IR"
            )
        return template, model, card, selection

    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceValidationPlan,
    ) -> ValidationPlanSnapshot:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        template, _, _, _ = self._plan_inputs(context, decision, command.content)
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            command.classification.value,
        )
        if template.record.scope != scope:
            raise ValidationConflict("Validation Plan classification must match its Template")
        plan_id = self._id()
        record = RevisionService(
            aggregate_type=VALIDATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=plan_id,
                scope=scope,
                schema_id=REFERENCE_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ValidationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def revise_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
        command: ReviseReferenceValidationPlan,
    ) -> ValidationPlanSnapshot:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        current = self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)
        if current.current.content.plan_label != command.content.plan_label:
            raise ValidationConflict("Validation Plan label is a stable identity")
        template, _, _, _ = self._plan_inputs(context, decision, command.content)
        if template.record.scope != current.current.record.scope:
            raise ValidationConflict("Validation Plan cannot move to another tenant scope")
        record = RevisionService(
            aggregate_type=VALIDATION_PLAN_AGGREGATE_TYPE,
            store=self._repository.plan_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=plan_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=REFERENCE_PLAN_SCHEMA_ID,
                schema_version=REFERENCE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ValidationPlanSnapshot(plan_id, RevisionSnapshot(record, command.content))

    def get_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plan_id: UUID,
    ) -> ValidationPlanSnapshot:
        _require(context, decision, Permission.VALIDATION_READ)
        return self._repository.get_plan(context=context, decision=decision, plan_id=plan_id)

    def list_plans(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        limit: int = 100,
    ) -> tuple[ValidationPlanSnapshot, ...]:
        _require(context, decision, Permission.VALIDATION_READ)
        if not 1 <= limit <= 200:
            raise InvalidValidationPlan("limit must be between 1 and 200")
        return self._repository.list_plans(context=context, decision=decision, limit=limit)

    async def submit_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: SubmitValidationRun,
    ) -> ValidationRunDetail:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
        )
        template, _, card, _ = self._plan_inputs(context, decision, plan.content)
        if command.execution_mode is ValidationExecutionMode.MANUAL_ATTACH:
            external_job_reference = validate_external_job_reference(command.external_job_reference)
            if not external_job_reference:
                raise ValidationConflict("manual execution requires an external_job_reference")
        elif command.external_job_reference is not None:
            raise ValidationConflict("reference inline mock execution cannot use an external job")
        else:
            external_job_reference = None
        run_id = self._id()
        deck_bytes = render_reference_deck(
            run_id=run_id,
            template=template.content,
            card_text=card.content.card_text,
            card_sha256=card.content.card_sha256,
        )
        deck = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=DataClassification(plan.record.scope.classification),
                artifact_role="validation.solver_deck",
                schema_ref=REFERENCE_DECK_SCHEMA_ID,
                media_type="text/plain; charset=utf-8",
                value=deck_bytes,
                idempotency_key=f"validation-run:{run_id}:deck",
            )
        )
        run = ValidationRun(
            id=run_id,
            classification=DataClassification(plan.record.scope.classification),
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            template_id=plan.content.template_id,
            template_revision_id=plan.content.template_revision_id,
            material_model_id=plan.content.material_model_id,
            material_model_revision_id=plan.content.material_model_revision_id,
            solver_card_id=plan.content.solver_card_id,
            solver_card_revision_id=plan.content.solver_card_revision_id,
            experimental_selection_id=plan.content.experimental_selection_id,
            experimental_selection_revision_id=plan.content.experimental_selection_revision_id,
            execution_mode=command.execution_mode,
            runner_id=plan.content.runner_id,
            runner_version=plan.content.runner_version,
            runner_digest=plan.content.runner_digest,
            status=(
                ValidationRunStatus.QUEUED
                if command.execution_mode is ValidationExecutionMode.REFERENCE_INLINE_MOCK
                else ValidationRunStatus.WAITING_MANUAL
            ),
            deck=deck,
            external_job_reference=external_job_reference,
            failure_code=None,
            submitted_at=self._clock(),
            started_at=None,
            ended_at=None,
            created_by=context.principal.id,
            request_id=context.request_id,
            trace_id=context.trace_id,
            change_reason=reason,
        )
        created = self._repository.create_run(context=context, decision=decision, run=run)
        return ValidationRunDetail(created, None)

    async def poll_reference_mock_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        *,
        outcome: ReferenceRunnerOutcome = ReferenceRunnerOutcome.SUCCEEDED,
        change_reason: str = "Poll non-production reference mock runner",
    ) -> ValidationRunDetail:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(change_reason)
        detail = self._repository.get_run_detail(context=context, decision=decision, run_id=run_id)
        run = detail.run
        if run.execution_mode is not ValidationExecutionMode.REFERENCE_INLINE_MOCK:
            raise ValidationConflict("manual runs must be completed with the manual attachment API")
        if detail.result_manifest is not None:
            return detail
        if run.status is not ValidationRunStatus.QUEUED:
            raise ValidationConflict("reference mock run is not queued")
        started = self._repository.start_run(context=context, decision=decision, run_id=run_id)
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=started.plan_id,
            plan_revision_id=started.plan_revision_id,
        )
        template, _, card, _ = self._plan_inputs(context, decision, plan.content)
        transition = map_reference_runner_outcome(outcome)
        stdout = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=started.classification,
                artifact_role="validation.runner_stdout",
                schema_ref=REFERENCE_STDOUT_SCHEMA_ID,
                media_type="application/json",
                value=reference_runner_stdout(outcome=outcome),
                idempotency_key=f"validation-run:{run_id}:stdout",
            )
        )
        stderr = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=started.classification,
                artifact_role="validation.runner_stderr",
                schema_ref=REFERENCE_STDERR_SCHEMA_ID,
                media_type="application/json",
                value=reference_runner_stderr(outcome=outcome),
                idempotency_key=f"validation-run:{run_id}:stderr",
            )
        )
        native: ValidationArtifactReference | None = None
        if transition.native_result_available:
            native = _reference(
                await self._artifacts.finalize_derived_bytes(
                    context,
                    decision,
                    classification=started.classification,
                    artifact_role="validation.native_solver_result",
                    schema_ref=REFERENCE_NATIVE_RESULT_SCHEMA_ID,
                    media_type="application/json",
                    value=reference_mock_native_result_bytes(
                        template=template.content,
                        youngs_modulus_pa=card.content.youngs_modulus_pa,
                    ),
                    idempotency_key=f"validation-run:{run_id}:native-result",
                )
            )
        return await self._commit_manifest(
            context,
            decision,
            run=started,
            stdout=stdout,
            stderr=stderr,
            native=native,
            termination=transition.termination,
            terminal_status=transition.status,
            failure_code=transition.failure_code,
            reason=reason,
        )

    async def attach_manual_result(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        command: AttachManualValidationResult,
    ) -> ValidationRunDetail:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        reason = _reason(command.change_reason)
        detail = self._repository.get_run_detail(context=context, decision=decision, run_id=run_id)
        run = detail.run
        if run.execution_mode is not ValidationExecutionMode.MANUAL_ATTACH:
            raise ValidationConflict(
                "only manual validation runs accept external result attachment"
            )
        if detail.result_manifest is not None:
            return detail
        if run.status is not ValidationRunStatus.WAITING_MANUAL:
            raise ValidationConflict("manual validation run is not waiting for an attachment")
        plan = self._repository.get_plan_revision(
            context=context,
            decision=decision,
            plan_id=run.plan_id,
            plan_revision_id=run.plan_revision_id,
        )
        template, _, _, _ = self._plan_inputs(context, decision, plan.content)
        native_bytes = command.native_result_text.encode("utf-8")
        descriptor = validate_reference_native_result_bytes(native_bytes, template=template.content)
        stdout_bytes = _manual_log_bytes(command.stdout_text, "stdout")
        stderr_bytes = _manual_log_bytes(command.stderr_text, "stderr")
        stdout = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=run.classification,
                artifact_role="validation.runner_stdout",
                schema_ref=REFERENCE_STDOUT_SCHEMA_ID,
                media_type="text/plain; charset=utf-8",
                value=stdout_bytes,
                idempotency_key=f"validation-run:{run_id}:stdout",
            )
        )
        stderr = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=run.classification,
                artifact_role="validation.runner_stderr",
                schema_ref=REFERENCE_STDERR_SCHEMA_ID,
                media_type="text/plain; charset=utf-8",
                value=stderr_bytes,
                idempotency_key=f"validation-run:{run_id}:stderr",
            )
        )
        native = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=run.classification,
                artifact_role="validation.native_solver_result",
                schema_ref=REFERENCE_NATIVE_RESULT_SCHEMA_ID,
                media_type="application/json",
                value=native_bytes,
                idempotency_key=f"validation-run:{run_id}:native-result",
            )
        )
        succeeded = descriptor.solver_termination is SolverTerminationStatus.NORMAL
        return await self._commit_manifest(
            context,
            decision,
            run=run,
            stdout=stdout,
            stderr=stderr,
            native=native,
            termination=descriptor.solver_termination,
            terminal_status=(
                ValidationRunStatus.SUCCEEDED if succeeded else ValidationRunStatus.FAILED
            ),
            failure_code=None if succeeded else "solver_failed",
            reason=reason,
        )

    async def _commit_manifest(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        run: ValidationRun,
        stdout: ValidationArtifactReference,
        stderr: ValidationArtifactReference,
        native: ValidationArtifactReference | None,
        termination: SolverTerminationStatus,
        terminal_status: ValidationRunStatus,
        failure_code: str | None,
        reason: str,
    ) -> ValidationRunDetail:
        content = ValidationRunResultManifestContent(
            validation_run_id=run.id,
            execution_mode=run.execution_mode,
            solver_termination=termination,
            external_job_reference=run.external_job_reference,
            deck=run.deck,
            stdout=stdout,
            stderr=stderr,
            native_result=native,
            native_result_state="available" if native else "not_available",
        )
        manifest_bytes = result_manifest_bytes(content)
        manifest_artifact = _reference(
            await self._artifacts.finalize_derived_bytes(
                context,
                decision,
                classification=run.classification,
                artifact_role="validation.run_result_manifest",
                schema_ref="urn:cmp:validation:run-result-manifest:1.0.0",
                media_type="application/json",
                value=manifest_bytes,
                idempotency_key=f"validation-run:{run.id}:result-manifest",
            )
        )
        manifest = ValidationRunResultManifest(
            id=self._id(),
            content=content,
            manifest_artifact=manifest_artifact,
            manifest_sha256=result_manifest_sha256(content),
            created_at=self._clock(),
            created_by=context.principal.id,
        )
        return self._repository.record_result_manifest(
            context=context,
            decision=decision,
            run_id=run.id,
            manifest=manifest,
            terminal_status=terminal_status,
            failure_code=failure_code,
            change_reason=reason,
        )

    def cancel_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
        *,
        reason: str,
    ) -> ValidationRunDetail:
        _require(context, decision, Permission.VALIDATION_EXECUTE)
        cancelled = self._repository.cancel_run(
            context=context,
            decision=decision,
            run_id=run_id,
            reason=_reason(reason),
        )
        return ValidationRunDetail(cancelled, None)

    def get_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> ValidationRunDetail:
        _require(context, decision, Permission.VALIDATION_READ)
        return self._repository.get_run_detail(context=context, decision=decision, run_id=run_id)


def _manual_log_bytes(value: str, stream: str) -> bytes:
    if not value or len(value) > 200_000 or "\x00" in value:
        raise InvalidNativeResult(
            f"manual {stream} log must contain between 1 and 200000 characters"
        )
    return value.encode("utf-8")
