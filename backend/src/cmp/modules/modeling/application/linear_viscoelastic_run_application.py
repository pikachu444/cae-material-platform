"""Run submission, isolated-result reconciliation, and execution failure orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.artifacts.domain.content import IntegrityStatus
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.jobs.application.jobs import SubmitJob
from cmp.modules.jobs.application.linear_viscoelastic_calibration import (
    build_linear_viscoelastic_job_spec,
    linear_viscoelastic_deadline,
    map_worker_failure,
)
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationAcceptedResultConflict,
    CalibrationApplicationState,
    CalibrationErrorCode,
    CalibrationJobReference,
    CalibrationRunProjection,
    ExecutionLedgerEntry,
    LinearViscoelasticCalibrationConflict,
    QueueLinearViscoelasticCalibrationRun,
    _reason,
    _require,
    _run_awaitable,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
    RunStatus,
)
from cmp.shared.domain.revisions import canonical_json_bytes

_DURABLE_JOB_TYPE = "plugin.run"
_PLAN_ARTIFACT_ROLE = "calibration.plan"
_PLAN_ARTIFACT_IDEMPOTENCY_PREFIX = "linear-viscoelastic-calibration:plan"
_JOB_IDEMPOTENCY_PREFIX = "linear-viscoelastic-calibration:job"


def _append_execution_entry(
    run: CalibrationRunProjection, entry: ExecutionLedgerEntry
) -> tuple[tuple[ExecutionLedgerEntry, ...], bool]:
    """Append one immutable attempt, or prove that it is an exact replay."""

    for existing in run.execution_ledger:
        if existing.attempt_id == entry.attempt_id:
            if existing != entry:
                raise LinearViscoelasticCalibrationConflict(
                    "execution attempt replay differs from the immutable ledger"
                )
            return run.execution_ledger, False
        if existing.job_attempt_no == entry.job_attempt_no:
            raise LinearViscoelasticCalibrationConflict(
                "execution attempt number already belongs to another immutable attempt"
            )
    return (*run.execution_ledger, entry), True


def _artifact_pin_tuple(
    values: tuple[UUID, ...], single: UUID | None, name: str
) -> tuple[UUID, ...]:
    result = tuple((*values, single) if single is not None else values)
    if len(set(result)) != len(result):
        raise LinearViscoelasticCalibrationConflict(f"{name} Artifact pins are duplicated")
    if any(item.int == 0 for item in result):
        raise LinearViscoelasticCalibrationConflict(f"{name} Artifact pin is zero")
    return result


class LinearViscoelasticRunApplication:
    """Application component for Jobs, Run attempts, and host-validated results."""

    @staticmethod
    def _append_execution_entry(
        run: CalibrationRunProjection, entry: ExecutionLedgerEntry
    ) -> tuple[tuple[ExecutionLedgerEntry, ...], bool]:
        return _append_execution_entry(run, entry)

    @staticmethod
    def _artifact_pin_tuple(
        values: tuple[UUID, ...], single: UUID | None, name: str
    ) -> tuple[UUID, ...]:
        return _artifact_pin_tuple(values, single, name)

    def import_validated_result(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        run_id: UUID,
        job_id: UUID,
        attempt_id: UUID,
        job_attempt_no: int,
        package_sha256: str,
        result: CalibrationRunResult | object,
        result_digest: str | None = None,
        result_sha256: str | None = None,
        result_manifest_artifact_id: UUID | None = None,
        result_manifest_sha256: str | None = None,
        response_residual_artifact_ids: tuple[UUID, ...] = (),
        objective_history_artifact_ids: tuple[UUID, ...] = (),
        response_residual_artifact_id: UUID | None = None,
        objective_history_artifact_id: UUID | None = None,
        submitted_at: datetime | None = None,
        deadline_at: datetime | None = None,
    ) -> CalibrationRunProjection:
        """Import one host-validated plugin result into the immutable Run projection."""

        _require(context, decision, Permission.JOB_EXECUTE)
        from cmp.modules.modeling.application.linear_viscoelastic_result_import import (
            document_sha256,
            parse_calibration_run_result,
            validate_result_digest,
        )

        original_result = result
        typed = (
            result
            if isinstance(result, CalibrationRunResult)
            else parse_calibration_run_result(result)
        )
        if not isinstance(typed, CalibrationRunResult):
            raise LinearViscoelasticCalibrationConflict("validated result did not form a typed Run")
        if result_sha256 is not None:
            if isinstance(original_result, CalibrationRunResult):
                raise LinearViscoelasticCalibrationConflict(
                    "run-result document bytes are required when result_sha256 is supplied"
                )
            if len(result_sha256) != 64 or any(
                char not in "0123456789abcdef" for char in result_sha256
            ):
                raise LinearViscoelasticCalibrationConflict("run-result document digest is invalid")
            if document_sha256(original_result) != result_sha256:
                raise LinearViscoelasticCalibrationConflict(
                    "run-result document digest differs from its immutable bytes"
                )
        if result_digest is not None:
            validate_result_digest(typed, result_digest)
        if len(package_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in package_sha256
        ):
            raise LinearViscoelasticCalibrationConflict("package SHA-256 is invalid")
        if result_manifest_artifact_id is not None and result_manifest_artifact_id.int == 0:
            raise LinearViscoelasticCalibrationConflict("result manifest Artifact pin is zero")
        if (result_manifest_artifact_id is None) != (result_manifest_sha256 is None):
            raise LinearViscoelasticCalibrationConflict(
                "result manifest Artifact identity and digest must be supplied together"
            )
        if result_manifest_sha256 is not None and (
            len(result_manifest_sha256) != 64
            or any(char not in "0123456789abcdef" for char in result_manifest_sha256)
        ):
            raise LinearViscoelasticCalibrationConflict("result manifest SHA-256 is invalid")
        if job_attempt_no < 1 or attempt_id.int == 0 or job_id.int == 0:
            raise LinearViscoelasticCalibrationConflict("Job and attempt identities are invalid")
        run = self._repository.get_run(run_id, context=context, decision=decision)
        if (
            run.id != typed.run_id
            or run.job_id != job_id
            or run.plan_revision_id != typed.plan_revision_id
        ):
            raise LinearViscoelasticCalibrationConflict(
                "validated result does not pin the exact Run, Job, or Plan revision"
            )
        residual_ids = _artifact_pin_tuple(
            response_residual_artifact_ids,
            response_residual_artifact_id,
            "response residual",
        )
        history_ids = _artifact_pin_tuple(
            objective_history_artifact_ids,
            objective_history_artifact_id,
            "objective history",
        )
        if not residual_ids:
            residual_ids = typed.response_residual_artifact_ids
        if not history_ids:
            history_ids = typed.objective_history_artifact_ids
        incoming = replace(
            typed,
            response_residual_artifact_ids=residual_ids,
            objective_history_artifact_ids=history_ids,
            execution_ledger_sha256=None,
        )
        entry_state = "succeeded" if incoming.status is RunStatus.SUCCEEDED else "failed"
        entry = ExecutionLedgerEntry(
            attempt_id=attempt_id,
            job_id=job_id,
            job_attempt_no=job_attempt_no,
            state=entry_state,
            package_sha256=package_sha256,
            submitted_at=submitted_at or self._clock(),
            deadline_at=deadline_at or self._clock(),
            result_manifest_artifact_id=result_manifest_artifact_id,
            result_manifest_sha256=result_manifest_sha256,
        )
        entries, appended = _append_execution_entry(run, entry)
        if run.result is not None and run.status in {
            RunStatus.SUCCEEDED.value,
            RunStatus.FAILED.value,
        }:
            if run.result.digest != incoming.digest:
                raise CalibrationAcceptedResultConflict(
                    "accepted_result_conflict: terminal Run has a different result digest"
                )
            if not appended:
                return run
            accepted = run.result
            status = run.status
        else:
            accepted = incoming
            status = incoming.status.value
        with_ledger = replace(run, execution_ledger=entries)
        accepted = replace(accepted, execution_ledger_sha256=with_ledger.execution_ledger_sha256)
        finished = replace(
            run,
            status=status,
            result=accepted,
            execution_ledger=entries,
            failure_code=accepted.failure_code,
            failure_detail=accepted.failure_detail,
            recovery_hint=accepted.recovery_hint,
        )
        return self._repository.save_run(finished, context=context, decision=decision)

    def record_execution_failure(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        run_id: UUID,
        job_id: UUID,
        attempt_id: UUID,
        job_attempt_no: int,
        outcome: str,
        diagnostic_code: str | None = None,
        detail: str | None = None,
        package_sha256: str | None = None,
        submitted_at: datetime | None = None,
        deadline_at: datetime | None = None,
        retry_scheduled: bool = False,
    ) -> CalibrationRunProjection:
        """Reconcile cancellation/timeout/infrastructure failure without faking success."""

        _require(context, decision, Permission.JOB_EXECUTE)
        if outcome not in {"failed", "cancelled", "timed_out"}:
            raise LinearViscoelasticCalibrationConflict("execution failure outcome is invalid")
        if job_id.int == 0 or attempt_id.int == 0 or job_attempt_no < 1:
            raise LinearViscoelasticCalibrationConflict("Job and attempt identities are invalid")
        if package_sha256 is not None and (
            len(package_sha256) != 64
            or any(char not in "0123456789abcdef" for char in package_sha256)
        ):
            raise LinearViscoelasticCalibrationConflict("package SHA-256 is invalid")
        run = self._repository.get_run(run_id, context=context, decision=decision)
        if run.job_id != job_id:
            raise LinearViscoelasticCalibrationConflict("failure does not pin the exact Job")
        code = map_worker_failure(outcome=outcome, diagnostic_code=diagnostic_code)
        recovery = (
            "The generic Job retry was scheduled; wait for its next immutable attempt."
            if retry_scheduled
            else "Create a new immutable calibration Run after reviewing the execution failure."
        )
        message = detail or {
            "cancelled": "The isolated calibration execution was cancelled.",
            "timed_out": "The isolated calibration execution exceeded its deadline.",
            "failed": (
                "The isolated calibration execution failed before a trusted result was committed."
            ),
        }.get(outcome, "The isolated calibration execution did not complete.")
        entry = ExecutionLedgerEntry(
            attempt_id=attempt_id,
            job_id=job_id,
            job_attempt_no=job_attempt_no,
            state=outcome if outcome in {"cancelled", "timed_out"} else "failed",
            failure_code=code,
            failure_detail=message,
            recovery_hint=recovery,
            package_sha256=package_sha256 or "0" * 64,
            submitted_at=submitted_at or self._clock(),
            deadline_at=deadline_at or self._clock(),
        )
        entries, appended = _append_execution_entry(run, entry)
        if not appended:
            return run
        if retry_scheduled:
            retrying = replace(
                run,
                status=RunStatus.RETRYING.value,
                execution_ledger=entries,
                failure_code=code,
                failure_detail=message,
                recovery_hint=recovery,
            )
            return self._repository.save_run(retrying, context=context, decision=decision)
        result = CalibrationRunResult(
            run_id=run.id,
            plan_revision_id=run.plan_revision_id,
            status=RunStatus.FAILED,
            attempts=(),
            candidates=(),
            recommendation=None,
            failure_code=code,
            failure_detail=message,
            recovery_hint=recovery,
        )
        with_ledger = replace(run, execution_ledger=entries)
        result = replace(result, execution_ledger_sha256=with_ledger.execution_ledger_sha256)
        failed = replace(
            run,
            status=RunStatus.FAILED.value,
            result=result,
            execution_ledger=entries,
            failure_code=code,
            failure_detail=message,
            recovery_hint=recovery,
        )
        return self._repository.save_run(failed, context=context, decision=decision)

    def queue_run(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: QueueLinearViscoelasticCalibrationRun,
    ) -> CalibrationJobReference:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        reason = _reason(command.change_reason)
        plan = self._repository.get_plan(command.plan_id, context=context, decision=decision)
        if plan.current.plan_revision_id != command.plan_revision_id:
            raise LinearViscoelasticCalibrationConflict("stale Plan revision")
        request_sha = (
            command.request_sha256
            or hashlib.sha256(
                canonical_json_bytes(
                    {
                        "plan_id": str(command.plan_id),
                        "plan_revision_id": str(command.plan_revision_id),
                        "reason": reason,
                    }
                )
            ).hexdigest()
        )
        existing = self._repository.find_run_by_idempotency(
            command.idempotency_key, context=context, decision=decision
        )
        if existing is not None:
            if existing.request_sha256 != request_sha:
                raise LinearViscoelasticCalibrationConflict(
                    "Run idempotency key was reused with different content"
                )
            return CalibrationJobReference(
                existing.id,
                existing.job_id,
                f"/api/v1/linear-viscoelastic-calibration-runs/{existing.id}",
                f"/api/v1/jobs/{existing.job_id}",
                existing.status,
            )
        if self._job_service is None:
            # The in-memory repository remains a small unit-test fixture. A service with a
            # configured durable dependency must never silently manufacture a Job reference.
            if any(
                dependency is not None
                for dependency in (
                    self._artifact_service,
                    self._plugin_registry,
                    self._authorization,
                )
            ):
                raise LinearViscoelasticCalibrationConflict(
                    "durable calibration Job service is unavailable"
                )
            run_id = self._new_id()
            job_id = self._new_id()
            value = CalibrationRunProjection(
                id=run_id,
                plan_id=command.plan_id,
                plan_revision_id=command.plan_revision_id,
                plan_sha256=plan.content_hash,
                classification=plan.classification,
                job_id=job_id,
                status="queued",
                result=None,
                execution_ledger=(),
                idempotency_key=command.idempotency_key,
                request_sha256=request_sha,
                created_at=self._clock(),
                created_by=context.principal.id,
                organization_id=context.organization_id,
                project_id=context.project_id,
            )
            self._repository.save_run(value, context=context, decision=decision)
            return CalibrationJobReference(
                run_id,
                job_id,
                f"/api/v1/linear-viscoelastic-calibration-runs/{run_id}",
                f"/api/v1/jobs/{job_id}",
            )
        if (
            self._artifact_service is None
            or self._plugin_registry is None
            or self._authorization is None
        ):
            raise LinearViscoelasticCalibrationConflict(
                "durable calibration dependencies are unavailable"
            )

        # Stable IDs make the generic Job idempotency record converge even when two API
        # workers receive the same calibration idempotency key concurrently.
        identity_seed = (
            f"{context.organization_id}:{context.project_id}:{command.plan_id}:"
            f"{command.plan_revision_id}:{request_sha}"
        )
        run_id = uuid5(NAMESPACE_URL, f"cmp:lve:run:{identity_seed}")
        job_id = uuid5(NAMESPACE_URL, f"cmp:lve:job:{identity_seed}")
        attempt_id = uuid5(NAMESPACE_URL, f"cmp:lve:attempt:{identity_seed}:1")
        plan_artifact = _run_awaitable(
            self._artifact_service.finalize_derived_bytes(
                context,
                decision,
                classification=plan.classification,
                artifact_role=_PLAN_ARTIFACT_ROLE,
                schema_ref=plan.current.schema_id,
                media_type="application/json",
                value=canonical_json_bytes(plan.current.canonical()),
                idempotency_key=(
                    f"{_PLAN_ARTIFACT_IDEMPOTENCY_PREFIX}:{plan.current.plan_revision_id}"
                ),
            )
        )
        if (
            plan_artifact.artifact.sha256 != plan.content_hash
            or plan_artifact.artifact.media_type != "application/json"
            or plan_artifact.integrity_status is not IntegrityStatus.VERIFIED
        ):
            raise LinearViscoelasticCalibrationConflict(
                "server-created Plan Artifact does not match the immutable Plan revision"
            )
        for name, pin, expected_media_type in (
            (
                "canonical Test Data",
                plan.current.canonical_artifact,
                "application/vnd.cmp.test-data+json",
            ),
            (
                "normalized Test Data",
                plan.current.normalized_artifact,
                "application/vnd.apache.parquet",
            ),
        ):
            assert pin is not None
            record = self._artifact_service.get_artifact_with_capability(
                context, decision, pin.artifact_id
            )
            artifact = record.artifact
            if (
                artifact.organization_id != context.organization_id
                or artifact.project_id != context.project_id
                or record.integrity_status is not IntegrityStatus.VERIFIED
                or artifact.sha256 != pin.sha256
                or artifact.media_type != expected_media_type
                or (pin.media_type is not None and artifact.media_type != pin.media_type)
            ):
                raise LinearViscoelasticCalibrationConflict(
                    f"exact {name} Artifact does not match the immutable Plan pin"
                )
        processing_output = plan.current.processing_output
        processing_metadata = plan.current.processing_metadata_artifact
        processing_result = plan.current.processing_result_artifact
        for name, pin, expected_media_type, expected_role in (
            (
                "Processing Output metadata",
                processing_metadata,
                "application/vnd.cmp.processing-output+json",
                "processing.common-output-json",
            ),
            (
                "Processing Output result",
                processing_result,
                "application/vnd.apache.parquet",
                "processing.dma-result-parquet",
            ),
        ):
            if pin is None:
                if processing_output is not None:
                    raise LinearViscoelasticCalibrationConflict(
                        "processed Plan input evidence is incomplete"
                    )
                continue
            record = self._artifact_service.get_artifact_with_capability(
                context, decision, pin.artifact_id
            )
            artifact = record.artifact
            if (
                processing_output is None
                or artifact.organization_id != context.organization_id
                or artifact.project_id != context.project_id
                or record.integrity_status is not IntegrityStatus.VERIFIED
                or artifact.sha256 != pin.sha256
                or artifact.media_type != expected_media_type
                or artifact.artifact_role != expected_role
            ):
                raise LinearViscoelasticCalibrationConflict(
                    f"exact {name} Artifact does not match the immutable Plan pin"
                )
        plugin_read = self._authorization.authorize(context, Permission.PLUGIN_READ)
        package = self._plugin_registry.get_active_for_plugin(
            context,
            plugin_read,
            plugin_id="cmp.linear_viscoelastic.calibrator",
            plugin_version="1.0.0",
        )
        if not package.active or package.classification is not plan.classification:
            raise LinearViscoelasticCalibrationConflict(
                "active calibration package is not available at the Plan classification"
            )
        submitted_at = self._clock()
        test_data = plan.current.test_data
        canonical_artifact = plan.current.canonical_artifact
        normalized_artifact = plan.current.normalized_artifact
        if test_data is None or canonical_artifact is None or normalized_artifact is None:
            raise LinearViscoelasticCalibrationConflict(
                "immutable Plan input evidence is incomplete"
            )
        spec, resource_policy = build_linear_viscoelastic_job_spec(
            job_id=job_id,
            attempt_id=attempt_id,
            run_id=run_id,
            plan_revision_id=plan.current.plan_revision_id,
            plan_sha256=plan_artifact.artifact.sha256,
            plan_artifact_id=plan_artifact.artifact.id,
            canonical_test_data_revision_id=test_data.revision_id,
            canonical_test_data_artifact_id=canonical_artifact.artifact_id,
            canonical_test_data_sha256=canonical_artifact.sha256,
            normalized_test_data_revision_id=test_data.revision_id,
            normalized_test_data_artifact_id=normalized_artifact.artifact_id,
            normalized_test_data_sha256=normalized_artifact.sha256,
            package_sha256=package.manifest.package_digest,
            recommendation_policy=plan.current.recommendation_policy,
            deadline=linear_viscoelastic_deadline(submitted_at),
            traceparent=context.trace_id,
            processing_output_revision_id=(
                processing_output.revision_id if processing_output else None
            ),
            processing_metadata_artifact_id=(
                processing_metadata.artifact_id if processing_metadata else None
            ),
            processing_metadata_sha256=(
                processing_metadata.sha256 if processing_metadata else None
            ),
            processing_result_artifact_id=(
                processing_result.artifact_id if processing_result else None
            ),
            processing_result_sha256=(processing_result.sha256 if processing_result else None),
        )
        submitted = self._job_service.submit(
            context,
            self._authorization.authorize(context, Permission.JOB_SUBMIT),
            SubmitJob(
                job_type=_DURABLE_JOB_TYPE,
                classification=plan.classification,
                job_spec=spec.document(),
                resource_policy=resource_policy,
                priority=0,
                idempotency_key=f"{_JOB_IDEMPOTENCY_PREFIX}:{request_sha}",
            ),
        )
        if submitted.details.job.id != job_id:
            raise LinearViscoelasticCalibrationConflict(
                "generic Job idempotency replay returned a different immutable Job identity"
            )
        value = CalibrationRunProjection(
            id=run_id,
            plan_id=command.plan_id,
            plan_revision_id=command.plan_revision_id,
            plan_sha256=plan.content_hash,
            classification=plan.classification,
            job_id=submitted.details.job.id,
            status=submitted.details.job.state.value,
            result=None,
            execution_ledger=(),
            idempotency_key=command.idempotency_key,
            request_sha256=request_sha,
            created_at=submitted.details.job.submitted_at,
            created_by=context.principal.id,
            organization_id=context.organization_id,
            project_id=context.project_id,
        )
        self._repository.save_run(value, context=context, decision=decision)
        return CalibrationJobReference(
            value.id,
            value.job_id,
            f"/api/v1/linear-viscoelastic-calibration-runs/{value.id}",
            f"/api/v1/jobs/{value.job_id}",
            value.status,
        )

    def execute_run(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        run_id: UUID,
        job_attempt_no: int = 1,
        package_sha256: str | None = None,
        submitted_at: datetime | None = None,
        deadline_at: datetime | None = None,
    ) -> CalibrationRunProjection:
        """Reject the removed in-process production execution path."""

        del context, decision, run_id, job_attempt_no, package_sha256, submitted_at, deadline_at
        raise LinearViscoelasticCalibrationConflict(
            "in-process calibration is disabled; import a validated plugin result"
        )

    def execute_reference_run(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        run_id: UUID,
        job_attempt_no: int = 1,
        package_sha256: str | None = None,
        submitted_at: datetime | None = None,
        deadline_at: datetime | None = None,
    ) -> CalibrationRunProjection:
        """Execute the deterministic reference kernel only in an explicitly test-only service."""

        if not self._allow_reference_execution:
            raise LinearViscoelasticCalibrationConflict(
                "reference calibration execution is disabled for production services"
            )
        from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
            calibrate_linear_viscoelastic,
        )

        _require(context, decision, Permission.JOB_EXECUTE)
        run = self._repository.get_run(run_id, context=context, decision=decision)
        value = self._inputs.get(run.plan_id)
        if value is None:
            raise LinearViscoelasticCalibrationConflict(
                "exact normalized source input is not staged"
            )
        now = self._clock()
        entry = ExecutionLedgerEntry(
            attempt_id=self._new_id(),
            job_id=run.job_id,
            job_attempt_no=job_attempt_no,
            state="running",
            package_sha256=package_sha256,
            submitted_at=submitted_at or now,
            deadline_at=deadline_at or now,
        )
        running = replace(run, status="running", execution_ledger=(*run.execution_ledger, entry))
        self._repository.save_run(running, context=context, decision=decision)
        result = calibrate_linear_viscoelastic(
            self._repository.get_plan(run.plan_id, context=context, decision=decision).current,
            value,
            run_id=run_id,
            now=now,
        )
        terminal = replace(
            result,
            execution_ledger_sha256=replace(
                running,
                execution_ledger=(
                    *running.execution_ledger,
                    replace(
                        entry,
                        state="succeeded" if result.status.value == "succeeded" else "failed",
                    ),
                ),
            ).execution_ledger_sha256,
        )
        finished = replace(
            running,
            status=result.status.value,
            result=terminal,
            execution_ledger=(
                *running.execution_ledger,
                replace(
                    entry, state="succeeded" if result.status.value == "succeeded" else "failed"
                ),
            ),
            failure_code=result.failure_code,
            failure_detail=result.failure_detail,
            recovery_hint=result.recovery_hint,
        )
        self._repository.save_run(finished, context=context, decision=decision)
        return finished

    def get_run(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRunProjection:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_run(run_id, context=context, decision=decision)

    def list_candidates(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> tuple[CalibrationCandidate, ...]:
        result = self.get_run(context, decision, run_id).result
        return result.candidates if result is not None else ()

    def get_recommendation(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationRecommendation | None:
        result = self.get_run(context, decision, run_id).result
        return result.recommendation if result else None

    def retry_terminal_run(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> None:
        _require(context, decision, Permission.CALIBRATION_EXECUTE)
        run = self._repository.get_run(run_id, context=context, decision=decision)
        if run.status in {"succeeded", "failed"}:
            from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
                CalibrationJobTerminalConflict,
            )

            raise CalibrationJobTerminalConflict(
                CalibrationErrorCode.TERMINAL_CALIBRATION_REQUIRES_NEW_RUN.value
            )


def failure_code_for_execution(
    *,
    cancelled: bool = False,
    timed_out: bool = False,
    isolation_unavailable: bool = False,
    package_integrity_failed: bool = False,
    request_invalid: bool = False,
    result_invalid: bool = False,
    plugin_domain_failed: bool = False,
) -> str:
    """Stable mapping from worker outcome to the governed calibration failure taxonomy."""

    if cancelled:
        return "CALCULATION_CANCELLED"
    if timed_out:
        return "CALCULATION_TIMED_OUT"
    if isolation_unavailable:
        return "EXECUTION_ISOLATION_UNAVAILABLE"
    if package_integrity_failed:
        return "EXECUTION_PACKAGE_INTEGRITY_FAILED"
    if request_invalid:
        return "EXECUTION_REQUEST_INVALID"
    if result_invalid:
        return "EXECUTION_RESULT_INVALID"
    if plugin_domain_failed:
        return "CALCULATION_FAILED"
    return "EXECUTION_INTERNAL_ERROR"
