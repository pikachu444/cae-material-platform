"""SQLAlchemy repository operations for linear-viscoelastic calibration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationPlanSnapshot,
    CalibrationRunProjection,
    CalibrationSelectionSnapshot,
    ExecutionLedgerEntry,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    CalibrationRunResult,
    ExactRevisionPin,
)
from cmp.shared.domain.revisions import (
    RevisionCreated,
    RevisionRecord,
    TenantScope,
    canonical_json_bytes,
)

from .linear_viscoelastic_calibration_serialization import (
    _as_uuid,
    _plan_from_payload,
    _result_from_payload,
    _selection_from_payload,
)
from .linear_viscoelastic_calibration_tables import (
    linear_viscoelastic_calibration_candidate_table,
    linear_viscoelastic_calibration_execution_attempt_table,
    linear_viscoelastic_calibration_numerical_attempt_table,
    linear_viscoelastic_calibration_plan_revision_table,
    linear_viscoelastic_calibration_plan_table,
    linear_viscoelastic_calibration_recommendation_table,
    linear_viscoelastic_calibration_run_table,
    linear_viscoelastic_calibration_selection_revision_table,
    linear_viscoelastic_calibration_selection_table,
)


def _exact_pin(
    aggregate_id: object,
    revision_id: object,
    sha256: object | None = None,
) -> ExactRevisionPin:
    if aggregate_id is None or revision_id is None:
        raise LinearViscoelasticCalibrationConflict("persisted exact pin is incomplete")
    return ExactRevisionPin(
        _as_uuid(aggregate_id),
        _as_uuid(revision_id),
        str(sha256) if sha256 is not None else None,
    )


class SqlAlchemyLinearViscoelasticCalibrationRepository:
    """Durable tenant-scoped SQL repository for the calibration aggregate.

    The repository deliberately has no in-memory fallback.  Every operation opens a fresh
    transaction, binds the request's RLS context, and serializes the immutable domain payload
    alongside typed query columns so a newly constructed service can rehydrate exact records.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: Any | None = None,
        revision_hooks: tuple[Callable[[Session, RevisionCreated], None], ...] = (),
    ) -> None:
        if session_factory is None:
            raise TypeError("session_factory is required for durable calibration persistence")
        self._sessions = session_factory
        self._rls = rls_context
        self._revision_hooks = revision_hooks

    @contextmanager
    def _session(
        self,
        context: SecurityContext | None,
        decision: AuthorizationDecision | None,
    ) -> Any:
        with self._sessions() as session:
            with session.begin():
                if self._rls is not None:
                    if context is None or decision is None:
                        raise LinearViscoelasticCalibrationConflict(
                            "authorization context is required for SQL calibration persistence"
                        )
                    self._rls.bind_authorization(session, context, decision)
                yield session

    @staticmethod
    def _scope(
        value: object,
        context: SecurityContext | None,
    ) -> tuple[UUID, UUID]:
        organization_id = (
            context.organization_id
            if context is not None
            else getattr(value, "organization_id", None)
        )
        project_id = (
            context.project_id if context is not None else getattr(value, "project_id", None)
        )
        if organization_id is None or project_id is None:
            raise LinearViscoelasticCalibrationConflict(
                "organization and project scope are required for SQL calibration persistence"
            )
        if context is not None:
            stored_org = getattr(value, "organization_id", None)
            stored_project = getattr(value, "project_id", None)
            if (stored_org is not None and stored_org != organization_id) or (
                stored_project is not None and stored_project != project_id
            ):
                raise LinearViscoelasticCalibrationConflict("calibration tenant scope mismatch")
        return _as_uuid(organization_id), _as_uuid(project_id)

    @staticmethod
    def _plan_row(session: Session, plan_id: UUID, organization_id: UUID, project_id: UUID) -> Any:
        identity = linear_viscoelastic_calibration_plan_table
        revision = linear_viscoelastic_calibration_plan_revision_table
        return (
            session.execute(
                sa.select(identity, revision)
                .select_from(
                    identity.join(
                        revision,
                        sa.and_(
                            revision.c.id == identity.c.current_revision_id,
                            revision.c.aggregate_id == identity.c.id,
                            revision.c.organization_id == identity.c.organization_id,
                            revision.c.project_id == identity.c.project_id,
                        ),
                    )
                )
                .where(
                    identity.c.id == plan_id,
                    identity.c.organization_id == organization_id,
                    identity.c.project_id == project_id,
                )
            )
            .mappings()
            .one_or_none()
        )

    def save_plan(
        self,
        value: CalibrationPlanSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        organization_id, project_id = self._scope(value, context)
        plan = value.current
        test_data = plan.test_data
        canonical_artifact = plan.canonical_artifact
        normalized_artifact = plan.normalized_artifact
        import_profile = plan.import_profile
        input_semantics = plan.input_semantics
        processing_output = plan.processing_output
        processing_metadata = plan.processing_metadata_artifact
        processing_result = plan.processing_result_artifact
        if (
            test_data is None
            or canonical_artifact is None
            or normalized_artifact is None
            or import_profile is None
            or input_semantics is None
        ):
            raise LinearViscoelasticCalibrationConflict(
                "calibration Plan is missing required immutable input evidence"
            )
        payload = plan.canonical()
        with self._session(context, decision) as session:
            identity = linear_viscoelastic_calibration_plan_table
            revision = linear_viscoelastic_calibration_plan_revision_table
            if idempotency_key is not None:
                existing = (
                    session.execute(
                        sa.select(identity.c.id, identity.c.idempotency_digest).where(
                            identity.c.organization_id == organization_id,
                            identity.c.project_id == project_id,
                            identity.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    if str(existing["idempotency_digest"]) != value.content_hash:
                        raise LinearViscoelasticCalibrationConflict(
                            "Plan idempotency key was reused with different content"
                        )
                    row = self._plan_row(
                        session, _as_uuid(existing["id"]), organization_id, project_id
                    )
                    if row is None:
                        raise LinearViscoelasticCalibrationNotFound("Plan is not visible")
                    return self._plan_snapshot(row)
            existing = self._plan_row(session, plan.plan_id, organization_id, project_id)
            if existing is not None:
                if str(existing["content_hash"]) != value.content_hash:
                    raise LinearViscoelasticCalibrationConflict(
                        "Plan identity maps to different content"
                    )
                return self._plan_snapshot(existing)
            identity_values = {
                "id": plan.plan_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "classification": value.classification.value,
                "current_revision_id": plan.plan_revision_id,
                "created_at": value.created_at,
                "created_by": value.created_by,
                "updated_at": value.created_at,
                "idempotency_key": idempotency_key,
                "idempotency_digest": value.content_hash if idempotency_key else None,
            }
            try:
                with session.begin_nested():
                    session.execute(sa.insert(identity).values(**identity_values))
            except IntegrityError as error:
                replay = self._plan_row(session, plan.plan_id, organization_id, project_id)
                if replay is not None and str(replay["content_hash"]) == value.content_hash:
                    return self._plan_snapshot(replay)
                if idempotency_key is not None:
                    replay_key = (
                        session.execute(
                            sa.select(identity.c.id, identity.c.idempotency_digest).where(
                                identity.c.organization_id == organization_id,
                                identity.c.project_id == project_id,
                                identity.c.idempotency_key == idempotency_key,
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if replay_key is not None:
                        if str(replay_key["idempotency_digest"]) != value.content_hash:
                            raise LinearViscoelasticCalibrationConflict(
                                "Plan idempotency key was reused with different content"
                            ) from error
                        replay = self._plan_row(
                            session,
                            _as_uuid(replay_key["id"]),
                            organization_id,
                            project_id,
                        )
                        if replay is not None:
                            return self._plan_snapshot(replay)
                raise LinearViscoelasticCalibrationConflict(
                    "Plan identity or idempotency key already exists"
                ) from error
            session.execute(
                sa.insert(revision).values(
                    id=plan.plan_revision_id,
                    aggregate_id=plan.plan_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    classification=value.classification.value,
                    revision_no=1,
                    based_on_revision_id=None,
                    schema_id=plan.schema_id,
                    schema_version=plan.schema_version,
                    content_hash=value.content_hash,
                    plan_sha256=value.content_hash,
                    test_data_id=test_data.aggregate_id,
                    test_data_revision_id=test_data.revision_id,
                    test_data_sha256=test_data.sha256,
                    canonical_artifact_id=canonical_artifact.artifact_id,
                    canonical_artifact_sha256=canonical_artifact.sha256,
                    canonical_artifact_media_type=canonical_artifact.media_type,
                    normalized_artifact_id=normalized_artifact.artifact_id,
                    normalized_artifact_sha256=normalized_artifact.sha256,
                    normalized_artifact_media_type=normalized_artifact.media_type,
                    raw_source_sha256=plan.raw_source_sha256,
                    import_profile_id=import_profile.aggregate_id,
                    import_profile_revision_id=import_profile.revision_id,
                    profile_sha256=plan.profile_sha256,
                    processing_output_id=(
                        processing_output.aggregate_id if processing_output else None
                    ),
                    processing_output_revision_id=(
                        processing_output.revision_id if processing_output else None
                    ),
                    processing_output_sha256=(
                        processing_output.sha256 if processing_output else None
                    ),
                    processing_metadata_artifact_id=(
                        processing_metadata.artifact_id if processing_metadata else None
                    ),
                    processing_metadata_artifact_sha256=(
                        processing_metadata.sha256 if processing_metadata else None
                    ),
                    processing_metadata_artifact_media_type=(
                        processing_metadata.media_type if processing_metadata else None
                    ),
                    processing_result_artifact_id=(
                        processing_result.artifact_id if processing_result else None
                    ),
                    processing_result_artifact_sha256=(
                        processing_result.sha256 if processing_result else None
                    ),
                    processing_result_artifact_media_type=(
                        processing_result.media_type if processing_result else None
                    ),
                    input_semantics=input_semantics.canonical(),
                    term_counts=list(plan.term_counts),
                    parameter_bounds={
                        str(term): [bound.canonical() for bound in bounds]
                        for term, bounds in plan.parameter_bounds.items()
                    },
                    start_vectors={
                        str(term): [list(vector) for vector in vectors]
                        for term, vectors in plan.start_vectors.items()
                    },
                    objective_policy=plan.weights.canonical(),
                    optimizer_policy=cast(Mapping[str, object], payload["optimizer"]),
                    statuses=plan.statuses.canonical(),
                    plan_payload=payload,
                    created_at=value.created_at,
                    created_by=value.created_by,
                    change_reason=value.change_reason,
                    request_id=context.request_id if context else UUID(int=1),
                    trace_id=context.trace_id if context else "sql-calibration",
                    setup_name=plan.setup_name,
                    material_id=plan.material.aggregate_id if plan.material else None,
                    material_revision_id=plan.material.revision_id if plan.material else None,
                    material_state_id=(
                        plan.material_state.aggregate_id if plan.material_state else None
                    ),
                    material_state_revision_id=(
                        plan.material_state.revision_id if plan.material_state else None
                    ),
                    input_mode=plan.input_mode,
                    based_on_plan_id=plan.based_on_plan_id,
                    based_on_plan_revision_id=plan.based_on_plan_revision_id,
                    override_reason=plan.override_reason,
                    base_diff=dict(plan.base_diff) if plan.base_diff is not None else None,
                )
            )
            if self._revision_hooks:
                revision_record = RevisionRecord(
                    revision_id=plan.plan_revision_id,
                    aggregate_type="modeling.linear_viscoelastic_calibration_plan",
                    aggregate_id=plan.plan_id,
                    scope=TenantScope(
                        organization_id=organization_id,
                        project_id=project_id,
                        classification=value.classification.value,
                    ),
                    revision_no=1,
                    based_on_revision_id=None,
                    schema_id=plan.schema_id,
                    schema_version=plan.schema_version,
                    content_hash=value.content_hash,
                    created_at=value.created_at,
                    created_by=value.created_by,
                    change_reason=value.change_reason,
                    request_id=context.request_id if context else UUID(int=1),
                    trace_id=context.trace_id if context else "sql-calibration",
                )
                event = RevisionCreated(revision_record, "draft")
                for hook in self._revision_hooks:
                    hook(session, event)
            return value

    @staticmethod
    def _plan_snapshot(row: Any) -> CalibrationPlanSnapshot:
        payload = cast(Mapping[str, object], row.get("plan_payload"))
        plan = _plan_from_payload(payload)
        return CalibrationPlanSnapshot(
            id=_as_uuid(row["id"]),
            current=plan,
            content_hash=str(row["content_hash"]),
            classification=DataClassification(str(row["classification"])),
            created_at=cast(datetime, row["created_at"]),
            created_by=_as_uuid(row["created_by"]),
            change_reason=str(row["change_reason"]),
            organization_id=_as_uuid(row["organization_id"]),
            project_id=_as_uuid(row["project_id"]),
        )

    def get_plan(
        self,
        plan_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        organization_id, project_id = self._context_scope(context)
        with self._session(context, decision) as session:
            row = self._plan_row(session, plan_id, organization_id, project_id)
            if row is None:
                raise LinearViscoelasticCalibrationNotFound("Plan is not visible")
            return self._plan_snapshot(row)

    def get_plan_revision(
        self,
        plan_id: UUID,
        plan_revision_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        """Read one exact immutable Plan revision; never follows a moving alias."""

        organization_id, project_id = self._context_scope(context)
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(linear_viscoelastic_calibration_plan_revision_table).where(
                        linear_viscoelastic_calibration_plan_revision_table.c.aggregate_id
                        == plan_id,
                        linear_viscoelastic_calibration_plan_revision_table.c.id
                        == plan_revision_id,
                        linear_viscoelastic_calibration_plan_revision_table.c.organization_id
                        == organization_id,
                        linear_viscoelastic_calibration_plan_revision_table.c.project_id
                        == project_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise LinearViscoelasticCalibrationNotFound("Plan revision is not visible")
            payload = cast(Mapping[str, object], row["plan_payload"])
            return CalibrationPlanSnapshot(
                id=_as_uuid(row["aggregate_id"]),
                current=_plan_from_payload(payload),
                content_hash=str(row["content_hash"]),
                classification=DataClassification(str(row["classification"])),
                created_at=cast(datetime, row["created_at"]),
                created_by=_as_uuid(row["created_by"]),
                change_reason=str(row["change_reason"]),
                organization_id=organization_id,
                project_id=project_id,
            )

    def find_run_by_idempotency(
        self,
        idempotency_key: str,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection | None:
        organization_id, project_id = self._context_scope(context)
        with self._session(context, decision) as session:
            row = session.execute(
                sa.select(linear_viscoelastic_calibration_run_table.c.id).where(
                    linear_viscoelastic_calibration_run_table.c.organization_id == organization_id,
                    linear_viscoelastic_calibration_run_table.c.project_id == project_id,
                    linear_viscoelastic_calibration_run_table.c.idempotency_key == idempotency_key,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._run_in(session, _as_uuid(row), organization_id, project_id)

    @staticmethod
    def _context_scope(context: SecurityContext | None) -> tuple[UUID, UUID]:
        if context is None:
            raise LinearViscoelasticCalibrationConflict(
                "request security context is required for SQL calibration persistence"
            )
        return context.organization_id, context.project_id

    def save_run(
        self,
        value: CalibrationRunProjection,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection:
        organization_id, project_id = self._scope(value, context)
        result = value.result
        now = value.created_at
        with self._session(context, decision) as session:
            table = linear_viscoelastic_calibration_run_table
            existing = (
                session.execute(
                    sa.select(table).where(
                        table.c.id == value.id,
                        table.c.organization_id == organization_id,
                        table.c.project_id == project_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            by_key = (
                session.execute(
                    sa.select(table).where(
                        table.c.organization_id == organization_id,
                        table.c.project_id == project_id,
                        table.c.idempotency_key == value.idempotency_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if by_key is not None and _as_uuid(by_key["id"]) != value.id:
                if str(by_key["request_sha256"]) != value.request_sha256:
                    raise LinearViscoelasticCalibrationConflict(
                        "Run idempotency key was reused with different content"
                    )
                return self._run_in(session, _as_uuid(by_key["id"]), organization_id, project_id)
            if existing is not None:
                if _as_uuid(existing["job_id"]) != value.job_id:
                    raise LinearViscoelasticCalibrationConflict(
                        "Run identity maps to a different Job"
                    )
                old_payload = existing.get("result_payload")
                if old_payload is not None and result is not None:
                    old_result = _result_from_payload(cast(Mapping[str, object], old_payload))
                    if old_result.digest != result.digest:
                        raise LinearViscoelasticCalibrationConflict("accepted-result conflict")
            else:
                try:
                    with session.begin_nested():
                        session.execute(
                            sa.insert(table).values(
                                id=value.id,
                                organization_id=organization_id,
                                project_id=project_id,
                                classification=value.classification.value,
                                plan_id=value.plan_id,
                                plan_revision_id=value.plan_revision_id,
                                plan_sha256=value.plan_sha256,
                                job_id=value.job_id,
                                status=value.status,
                                terminal_digest=result.digest if result else None,
                                execution_ledger_sha256=value.execution_ledger_sha256
                                if value.execution_ledger
                                else None,
                                failure_code=value.failure_code,
                                failure_detail=value.failure_detail,
                                recovery_hint=value.recovery_hint,
                                recommendation_id=result.recommendation.recommendation_id
                                if result and result.recommendation
                                else None,
                                idempotency_key=value.idempotency_key,
                                request_sha256=value.request_sha256,
                                result_payload=result.canonical() if result else None,
                                started_at=value.created_at,
                                finished_at=(
                                    now
                                    if result and value.status in {"succeeded", "failed"}
                                    else None
                                ),
                                created_at=value.created_at,
                                created_by=value.created_by,
                                request_id=context.request_id if context else UUID(int=1),
                                trace_id=context.trace_id if context else "sql-calibration",
                                approval_request_id=value.approval_request_id,
                                approval_decision_id=value.approval_decision_id,
                                approval_evidence_sha256=value.approval_evidence_sha256,
                                approval_state=value.approval_state,
                                approval_approved_at=value.approval_approved_at,
                                approval_approved_by=value.approval_approved_by,
                                execution_material_id=(
                                    value.execution_material.aggregate_id
                                    if value.execution_material
                                    else None
                                ),
                                execution_material_revision_id=(
                                    value.execution_material.revision_id
                                    if value.execution_material
                                    else None
                                ),
                                execution_material_state_id=(
                                    value.execution_material_state.aggregate_id
                                    if value.execution_material_state
                                    else None
                                ),
                                execution_material_state_revision_id=(
                                    value.execution_material_state.revision_id
                                    if value.execution_material_state
                                    else None
                                ),
                                execution_test_data_id=(
                                    value.execution_test_data.aggregate_id
                                    if value.execution_test_data
                                    else None
                                ),
                                execution_test_data_revision_id=(
                                    value.execution_test_data.revision_id
                                    if value.execution_test_data
                                    else None
                                ),
                                execution_test_data_sha256=(
                                    value.execution_test_data.sha256
                                    if value.execution_test_data
                                    else None
                                ),
                                execution_processing_output_id=(
                                    value.execution_processing_output.aggregate_id
                                    if value.execution_processing_output
                                    else None
                                ),
                                execution_processing_output_revision_id=(
                                    value.execution_processing_output.revision_id
                                    if value.execution_processing_output
                                    else None
                                ),
                                execution_processing_output_sha256=(
                                    value.execution_processing_output.sha256
                                    if value.execution_processing_output
                                    else None
                                ),
                                execution_input_mode=value.execution_input_mode,
                            )
                        )
                except IntegrityError as error:
                    replay = (
                        session.execute(
                            sa.select(table).where(
                                table.c.organization_id == organization_id,
                                table.c.project_id == project_id,
                                table.c.idempotency_key == value.idempotency_key,
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if replay is not None:
                        if str(replay["request_sha256"]) != value.request_sha256:
                            raise LinearViscoelasticCalibrationConflict(
                                "Run idempotency key was reused with different content"
                            ) from error
                        return self._run_in(
                            session, _as_uuid(replay["id"]), organization_id, project_id
                        )
                    raise LinearViscoelasticCalibrationConflict(
                        "Run identity or idempotency key already exists"
                    ) from error
            if existing is not None:
                session.execute(
                    sa.update(table)
                    .where(
                        table.c.id == value.id,
                        table.c.organization_id == organization_id,
                        table.c.project_id == project_id,
                    )
                    .values(
                        status=value.status,
                        terminal_digest=result.digest if result else existing["terminal_digest"],
                        execution_ledger_sha256=value.execution_ledger_sha256
                        if value.execution_ledger
                        else existing["execution_ledger_sha256"],
                        failure_code=value.failure_code,
                        failure_detail=value.failure_detail,
                        recovery_hint=value.recovery_hint,
                        recommendation_id=result.recommendation.recommendation_id
                        if result and result.recommendation
                        else existing["recommendation_id"],
                        result_payload=result.canonical()
                        if result is not None
                        else existing["result_payload"],
                        finished_at=now
                        if result and value.status in {"succeeded", "failed"}
                        else existing["finished_at"],
                    )
                )
            self._save_ledger(session, value, organization_id, project_id, context)
            if result is not None:
                self._save_result_rows(session, value, result, organization_id, project_id, context)
            return value

    def _save_ledger(
        self,
        session: Session,
        value: CalibrationRunProjection,
        organization_id: UUID,
        project_id: UUID,
        context: SecurityContext | None,
    ) -> None:
        table = linear_viscoelastic_calibration_execution_attempt_table
        entries = value.execution_ledger
        if not entries and value.result is not None:
            entries = (
                ExecutionLedgerEntry(
                    attempt_id=uuid5(NAMESPACE_URL, f"{value.id}:execution:1"),
                    job_id=value.job_id,
                    job_attempt_no=1,
                    state="succeeded" if value.status == "succeeded" else "failed",
                    package_sha256="0" * 64,
                    submitted_at=value.created_at,
                    deadline_at=value.created_at,
                ),
            )
        for entry in entries:
            existing = (
                session.execute(
                    sa.select(table).where(
                        table.c.run_id == value.id,
                        table.c.organization_id == organization_id,
                        table.c.project_id == project_id,
                        table.c.job_attempt_no == entry.job_attempt_no,
                    )
                )
                .mappings()
                .one_or_none()
            )
            package_sha256 = entry.package_sha256 or "0" * 64
            values = {
                "id": entry.attempt_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "classification": value.classification.value,
                "run_id": value.id,
                "job_id": entry.job_id,
                "job_attempt_no": entry.job_attempt_no,
                "state": entry.state,
                "failure_code": entry.failure_code,
                "failure_detail": entry.failure_detail,
                "recovery_hint": entry.recovery_hint,
                "package_id": "cmp.linear_viscoelastic.calibrator",
                "package_version": "1.0.0",
                "package_sha256": package_sha256,
                "submitted_at": entry.submitted_at or value.created_at,
                "deadline_at": entry.deadline_at or value.created_at,
                "claimed_at": entry.submitted_at if entry.state != "claimed" else None,
                "finished_at": value.created_at
                if entry.state in {"succeeded", "failed", "cancelled", "timed_out"}
                else None,
                "result_manifest_artifact_id": entry.result_manifest_artifact_id,
                "result_manifest_sha256": entry.result_manifest_sha256,
                "created_at": value.created_at,
                "created_by": value.created_by,
            }
            if existing is None:
                session.execute(sa.insert(table).values(**values))
            elif _as_uuid(existing["id"]) != entry.attempt_id:
                raise LinearViscoelasticCalibrationConflict(
                    "execution attempt number already belongs to another immutable attempt"
                )
            else:
                session.execute(
                    sa.update(table)
                    .where(table.c.id == entry.attempt_id)
                    .values(
                        state=entry.state,
                        failure_code=entry.failure_code,
                        failure_detail=entry.failure_detail,
                        recovery_hint=entry.recovery_hint,
                        claimed_at=values["claimed_at"],
                        finished_at=values["finished_at"],
                        result_manifest_artifact_id=values["result_manifest_artifact_id"],
                        result_manifest_sha256=values["result_manifest_sha256"],
                    )
                )

    def _save_result_rows(
        self,
        session: Session,
        value: CalibrationRunProjection,
        result: CalibrationRunResult,
        organization_id: UUID,
        project_id: UUID,
        context: SecurityContext | None,
    ) -> None:
        execution = (
            session.execute(
                sa.select(linear_viscoelastic_calibration_execution_attempt_table.c.id)
                .where(
                    linear_viscoelastic_calibration_execution_attempt_table.c.run_id == value.id,
                    linear_viscoelastic_calibration_execution_attempt_table.c.organization_id
                    == organization_id,
                    linear_viscoelastic_calibration_execution_attempt_table.c.project_id
                    == project_id,
                )
                .order_by(linear_viscoelastic_calibration_execution_attempt_table.c.job_attempt_no)
            )
            .scalars()
            .first()
        )
        if execution is None:
            raise LinearViscoelasticCalibrationConflict("result requires an execution ledger entry")
        numerical = linear_viscoelastic_calibration_numerical_attempt_table
        residual_artifact_id = (
            result.response_residual_artifact_ids[0]
            if result.response_residual_artifact_ids
            else None
        )
        history_artifact_id = (
            result.objective_history_artifact_ids[0]
            if result.objective_history_artifact_ids
            else None
        )
        for attempt in result.attempts:
            attempt_id = uuid5(NAMESPACE_URL, f"{value.id}:numerical:{attempt.ordinal}")
            exists = session.execute(
                sa.select(numerical.c.id).where(numerical.c.id == attempt_id)
            ).scalar_one_or_none()
            if exists is not None:
                continue
            session.execute(
                sa.insert(numerical).values(
                    id=attempt_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    classification=value.classification.value,
                    run_id=value.id,
                    execution_attempt_id=execution,
                    ordinal=attempt.ordinal,
                    term_count=attempt.term_count,
                    start_vector=list(attempt.start_vector),
                    transformed_start_vector=list(attempt.transformed_start_vector),
                    status=attempt.status,
                    optimizer_message=attempt.message,
                    nfev=attempt.nfev,
                    cost=attempt.cost,
                    optimality=attempt.optimality,
                    active_mask=list(attempt.active_mask),
                    physical_parameters=list(attempt.physical_parameters),
                    transformed_parameters=list(attempt.transformed_parameters),
                    residuals=list(attempt.residuals),
                    residuals_artifact_id=residual_artifact_id,
                    objective_history_artifact_id=history_artifact_id,
                    rank_sigma_max=attempt.rank.sigma_max,
                    rank_threshold=attempt.rank.threshold,
                    rank_status=attempt.rank.status.value,
                    rank_warning_code=attempt.rank.warning_code,
                    objective_history=[item.canonical() for item in attempt.objective_history],
                    rss=attempt.rss,
                    rank=attempt.rank.rank,
                    singular_values=list(attempt.rank.singular_values),
                    warning_codes=list(attempt.warnings),
                    converged=attempt.converged,
                    physical=attempt.physical,
                    created_at=value.created_at,
                    created_by=value.created_by,
                )
            )
        candidate_table = linear_viscoelastic_calibration_candidate_table
        for candidate in result.candidates:
            exists = session.execute(
                sa.select(candidate_table.c.id).where(
                    candidate_table.c.id == candidate.candidate_id
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            numerical_id = uuid5(NAMESPACE_URL, f"{value.id}:numerical:{candidate.attempt_ordinal}")
            calibration_artifact_id = residual_artifact_id or uuid5(
                NAMESPACE_URL, f"{candidate.candidate_id}:calibration-residuals"
            )
            session.execute(
                sa.insert(candidate_table).values(
                    id=candidate.candidate_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    classification=value.classification.value,
                    run_id=value.id,
                    numerical_attempt_id=numerical_id,
                    attempt_ordinal=candidate.attempt_ordinal,
                    term_count=candidate.term_count,
                    candidate_sha256=candidate.digest,
                    physical_parameters=list(candidate.physical_parameters),
                    transformed_parameters=list(candidate.transformed_parameters),
                    rss=candidate.rss,
                    bic=candidate.bic,
                    calibration_residuals_artifact_id=calibration_artifact_id,
                    holdout_residuals_artifact_id=(
                        residual_artifact_id if candidate.holdout_residuals else None
                    ),
                    calibration_residuals=list(candidate.calibration_residuals),
                    holdout_residuals=list(candidate.holdout_residuals),
                    rank=candidate.rank.rank,
                    singular_values=list(candidate.rank.singular_values),
                    rank_sigma_max=candidate.rank.sigma_max,
                    rank_threshold=candidate.rank.threshold,
                    rank_status=candidate.rank.status.value,
                    rank_warning_code=candidate.rank.warning_code,
                    warning_codes=list(candidate.warnings),
                    uncertainty_status=candidate.uncertainty_status.value,
                    created_at=value.created_at,
                    created_by=value.created_by,
                )
            )
        if result.recommendation is not None:
            recommendation = linear_viscoelastic_calibration_recommendation_table
            exists = session.execute(
                sa.select(recommendation.c.id).where(
                    recommendation.c.id == result.recommendation.recommendation_id
                )
            ).scalar_one_or_none()
            if exists is None:
                recommendation_sha256 = hashlib.sha256(
                    canonical_json_bytes(result.recommendation.canonical())
                ).hexdigest()
                session.execute(
                    sa.insert(recommendation).values(
                        id=result.recommendation.recommendation_id,
                        organization_id=organization_id,
                        project_id=project_id,
                        classification=value.classification.value,
                        run_id=value.id,
                        candidate_id=result.recommendation.candidate_id,
                        candidate_sha256=result.recommendation.candidate_digest,
                        recommendation_sha256=recommendation_sha256,
                        rule_version=result.recommendation.rule_version,
                        created_at=value.created_at,
                        created_by=value.created_by,
                    )
                )

    def _run_in(
        self, session: Session, run_id: UUID, organization_id: UUID, project_id: UUID
    ) -> CalibrationRunProjection:
        table = linear_viscoelastic_calibration_run_table
        row = (
            session.execute(
                sa.select(table).where(
                    table.c.id == run_id,
                    table.c.organization_id == organization_id,
                    table.c.project_id == project_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LinearViscoelasticCalibrationNotFound("Run is not visible")
        ledger_rows = (
            session.execute(
                sa.select(linear_viscoelastic_calibration_execution_attempt_table)
                .where(
                    linear_viscoelastic_calibration_execution_attempt_table.c.run_id == run_id,
                    linear_viscoelastic_calibration_execution_attempt_table.c.organization_id
                    == organization_id,
                    linear_viscoelastic_calibration_execution_attempt_table.c.project_id
                    == project_id,
                )
                .order_by(linear_viscoelastic_calibration_execution_attempt_table.c.job_attempt_no)
            )
            .mappings()
            .all()
        )
        ledger = tuple(
            ExecutionLedgerEntry(
                attempt_id=_as_uuid(item["id"]),
                job_id=_as_uuid(item["job_id"]),
                job_attempt_no=int(item["job_attempt_no"]),
                state=str(item["state"]),
                failure_code=str(item["failure_code"]) if item["failure_code"] else None,
                failure_detail=str(item["failure_detail"]) if item["failure_detail"] else None,
                recovery_hint=str(item["recovery_hint"]) if item["recovery_hint"] else None,
                package_sha256=str(item["package_sha256"]),
                submitted_at=cast(datetime, item["submitted_at"]),
                deadline_at=cast(datetime, item["deadline_at"]),
                result_manifest_artifact_id=(
                    _as_uuid(item["result_manifest_artifact_id"])
                    if item["result_manifest_artifact_id"] is not None
                    else None
                ),
                result_manifest_sha256=(
                    str(item["result_manifest_sha256"])
                    if item["result_manifest_sha256"] is not None
                    else None
                ),
            )
            for item in ledger_rows
        )
        payload = row.get("result_payload")
        result = _result_from_payload(cast(Mapping[str, object], payload)) if payload else None
        return CalibrationRunProjection(
            id=_as_uuid(row["id"]),
            plan_id=_as_uuid(row["plan_id"]),
            plan_revision_id=_as_uuid(row["plan_revision_id"]),
            plan_sha256=str(row["plan_sha256"]),
            classification=DataClassification(str(row["classification"])),
            job_id=_as_uuid(row["job_id"]),
            status=str(row["status"]),
            result=result,
            execution_ledger=ledger,
            idempotency_key=str(row["idempotency_key"]),
            request_sha256=str(row["request_sha256"]),
            created_at=cast(datetime, row["created_at"]),
            created_by=_as_uuid(row["created_by"]),
            failure_code=str(row["failure_code"]) if row["failure_code"] else None,
            failure_detail=str(row["failure_detail"]) if row["failure_detail"] else None,
            recovery_hint=str(row["recovery_hint"]) if row["recovery_hint"] else None,
            organization_id=organization_id,
            project_id=project_id,
            approval_request_id=(
                _as_uuid(row["approval_request_id"])
                if row.get("approval_request_id") is not None
                else None
            ),
            approval_decision_id=(
                _as_uuid(row["approval_decision_id"])
                if row.get("approval_decision_id") is not None
                else None
            ),
            approval_evidence_sha256=(
                str(row["approval_evidence_sha256"])
                if row.get("approval_evidence_sha256") is not None
                else None
            ),
            approval_state=(str(row["approval_state"]) if row.get("approval_state") else None),
            approval_approved_at=(
                cast(datetime, row["approval_approved_at"])
                if row.get("approval_approved_at") is not None
                else None
            ),
            approval_approved_by=(
                _as_uuid(row["approval_approved_by"])
                if row.get("approval_approved_by") is not None
                else None
            ),
            execution_material=(
                _exact_pin(
                    row.get("execution_material_id"),
                    row.get("execution_material_revision_id"),
                )
                if row.get("execution_material_id") is not None
                else None
            ),
            execution_material_state=(
                _exact_pin(
                    row.get("execution_material_state_id"),
                    row.get("execution_material_state_revision_id"),
                )
                if row.get("execution_material_state_id") is not None
                else None
            ),
            execution_test_data=(
                _exact_pin(
                    row.get("execution_test_data_id"),
                    row.get("execution_test_data_revision_id"),
                    row.get("execution_test_data_sha256"),
                )
                if row.get("execution_test_data_id") is not None
                else None
            ),
            execution_processing_output=(
                _exact_pin(
                    row.get("execution_processing_output_id"),
                    row.get("execution_processing_output_revision_id"),
                    row.get("execution_processing_output_sha256"),
                )
                if row.get("execution_processing_output_id") is not None
                else None
            ),
            execution_input_mode=(
                str(row["execution_input_mode"]) if row.get("execution_input_mode") else None
            ),
        )

    def get_run(
        self,
        run_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection:
        organization_id, project_id = self._context_scope(context)
        with self._session(context, decision) as session:
            return self._run_in(session, run_id, organization_id, project_id)

    def save_selection(
        self,
        value: CalibrationSelectionSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot:
        organization_id, project_id = self._scope(value, context)
        selection = value.value
        payload = selection.canonical()
        content_digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        idempotency_digest = hashlib.sha256(
            canonical_json_bytes(selection.intent_canonical())
        ).hexdigest()
        with self._session(context, decision) as session:
            identity = linear_viscoelastic_calibration_selection_table
            revision = linear_viscoelastic_calibration_selection_revision_table
            if idempotency_key is not None:
                existing = (
                    session.execute(
                        sa.select(identity).where(
                            identity.c.organization_id == organization_id,
                            identity.c.project_id == project_id,
                            identity.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if existing is not None:
                    if str(existing["idempotency_digest"]) != idempotency_digest:
                        raise LinearViscoelasticCalibrationConflict(
                            "Selection idempotency key was reused with different content"
                        )
                    return self._selection_in(
                        session, _as_uuid(existing["id"]), organization_id, project_id
                    )
            current = (
                session.execute(
                    sa.select(identity).where(
                        identity.c.id == selection.selection_id,
                        identity.c.organization_id == organization_id,
                        identity.c.project_id == project_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if current is not None:
                return self._selection_in(
                    session, selection.selection_id, organization_id, project_id
                )
            try:
                with session.begin_nested():
                    session.execute(
                        sa.insert(identity).values(
                            id=selection.selection_id,
                            organization_id=organization_id,
                            project_id=project_id,
                            classification=value.classification.value,
                            current_revision_id=selection.selection_revision_id,
                            created_at=selection.created_at,
                            created_by=selection.actor,
                            updated_at=selection.created_at,
                            idempotency_key=idempotency_key,
                            idempotency_digest=idempotency_digest if idempotency_key else None,
                        )
                    )
            except IntegrityError as error:
                replay = (
                    session.execute(
                        sa.select(identity).where(
                            identity.c.organization_id == organization_id,
                            identity.c.project_id == project_id,
                            identity.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                if replay is not None:
                    if str(replay["idempotency_digest"]) != idempotency_digest:
                        raise LinearViscoelasticCalibrationConflict(
                            "Selection idempotency key was reused with different content"
                        ) from error
                    return self._selection_in(
                        session, _as_uuid(replay["id"]), organization_id, project_id
                    )
                raise LinearViscoelasticCalibrationConflict(
                    "Selection identity or idempotency key already exists"
                ) from error
            session.execute(
                sa.insert(revision).values(
                    id=selection.selection_revision_id,
                    aggregate_id=selection.selection_id,
                    organization_id=organization_id,
                    project_id=project_id,
                    classification=value.classification.value,
                    revision_no=1,
                    based_on_revision_id=None,
                    schema_id="urn:cmp:modeling:linear-viscoelastic-calibration-selection:1.0.0",
                    schema_version="1.0.0",
                    content_hash=content_digest,
                    plan_revision_id=selection.plan_revision_id,
                    run_id=selection.run_id,
                    candidate_id=selection.candidate_id,
                    candidate_sha256=selection.candidate_digest,
                    reason=selection.reason,
                    warning_acknowledgements=list(selection.warning_acknowledgements),
                    actor=selection.actor,
                    created_at=selection.created_at,
                    created_by=selection.actor,
                    change_reason=selection.reason,
                    request_id=context.request_id if context else UUID(int=1),
                    trace_id=context.trace_id if context else "sql-calibration",
                    selection_payload=payload,
                )
            )
            return value

    def _selection_in(
        self, session: Session, selection_id: UUID, organization_id: UUID, project_id: UUID
    ) -> CalibrationSelectionSnapshot:
        identity = linear_viscoelastic_calibration_selection_table
        revision = linear_viscoelastic_calibration_selection_revision_table
        row = (
            session.execute(
                sa.select(identity, revision)
                .select_from(
                    identity.join(
                        revision,
                        sa.and_(
                            revision.c.id == identity.c.current_revision_id,
                            revision.c.aggregate_id == identity.c.id,
                            revision.c.organization_id == identity.c.organization_id,
                            revision.c.project_id == identity.c.project_id,
                        ),
                    )
                )
                .where(
                    identity.c.id == selection_id,
                    identity.c.organization_id == organization_id,
                    identity.c.project_id == project_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise LinearViscoelasticCalibrationNotFound("Selection is not visible")
        payload = cast(Mapping[str, object], row["selection_payload"])
        selection = _selection_from_payload(payload)
        return CalibrationSelectionSnapshot(
            selection,
            DataClassification(str(row["classification"])),
            organization_id=organization_id,
            project_id=project_id,
        )

    def get_selection(
        self,
        selection_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot:
        organization_id, project_id = self._context_scope(context)
        with self._session(context, decision) as session:
            return self._selection_in(session, selection_id, organization_id, project_id)
