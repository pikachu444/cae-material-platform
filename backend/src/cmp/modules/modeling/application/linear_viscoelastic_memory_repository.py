"""Explicit test-only repository for linear-viscoelastic application tests.

Production composition uses the SQLAlchemy repository adapter.  This implementation exists only
for deterministic unit fixtures and intentionally keeps its state local to one test instance.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationPlanSnapshot,
    CalibrationRunProjection,
    CalibrationSelectionSnapshot,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
    LinearViscoelasticCalibrationRepository,
)
from cmp.shared.domain.revisions import canonical_json_bytes


class InMemoryLinearViscoelasticCalibrationRepository:
    """Test-only repository with immutable result and idempotency semantics."""

    def __init__(self) -> None:
        self.plans: dict[UUID, CalibrationPlanSnapshot] = {}
        self.runs: dict[UUID, CalibrationRunProjection] = {}
        self.selections: dict[UUID, CalibrationSelectionSnapshot] = {}
        self.plan_idempotency: dict[str, tuple[str, UUID]] = {}
        self.run_idempotency: dict[str, tuple[str, UUID]] = {}
        self.selection_idempotency: dict[str, tuple[str, UUID]] = {}

    def save_plan(
        self,
        value: CalibrationPlanSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        del context, decision
        digest = value.content_hash
        if idempotency_key is not None:
            existing_idempotency = self.plan_idempotency.get(idempotency_key)
            if existing_idempotency is not None:
                if existing_idempotency[0] != digest:
                    raise LinearViscoelasticCalibrationConflict(
                        "Plan idempotency key was reused with different content"
                    )
                return self.plans[existing_idempotency[1]]
            self.plan_idempotency[idempotency_key] = (digest, value.id)
        if value.id in self.plans:
            existing_plan = self.plans[value.id]
            if existing_plan.content_hash != digest:
                raise LinearViscoelasticCalibrationConflict(
                    "Plan identity maps to different content"
                )
            return existing_plan
        self.plans[value.id] = value
        return value

    def get_plan(
        self,
        plan_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        del context, decision
        try:
            return self.plans[plan_id]
        except KeyError as error:
            raise LinearViscoelasticCalibrationNotFound("Plan is not visible") from error

    def get_plan_revision(
        self,
        plan_id: UUID,
        plan_revision_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationPlanSnapshot:
        del context, decision
        value = self.get_plan(plan_id)
        if value.current.plan_revision_id != plan_revision_id:
            raise LinearViscoelasticCalibrationNotFound("Plan revision is not visible")
        return value

    def save_run(
        self,
        value: CalibrationRunProjection,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection:
        del context, decision
        existing = self.runs.get(value.id)
        if existing is not None and existing != value:
            if existing.result is not None and value.result is not None:
                if existing.result.digest != value.result.digest:
                    raise LinearViscoelasticCalibrationConflict("accepted-result conflict")
            self.runs[value.id] = value
            return value
        self.runs[value.id] = value
        self.run_idempotency[value.idempotency_key] = (value.request_sha256, value.id)
        return value

    def get_run(
        self,
        run_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection:
        del context, decision
        try:
            return self.runs[run_id]
        except KeyError as error:
            raise LinearViscoelasticCalibrationNotFound("Run is not visible") from error

    def find_run_by_idempotency(
        self,
        idempotency_key: str,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationRunProjection | None:
        del context, decision
        existing = self.run_idempotency.get(idempotency_key)
        return self.runs.get(existing[1]) if existing is not None else None

    def save_selection(
        self,
        value: CalibrationSelectionSnapshot,
        *,
        idempotency_key: str | None,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot:
        del context, decision
        digest = hashlib.sha256(canonical_json_bytes(value.value.intent_canonical())).hexdigest()
        if idempotency_key is not None:
            existing_idempotency = self.selection_idempotency.get(idempotency_key)
            if existing_idempotency is not None:
                if existing_idempotency[0] != digest:
                    raise LinearViscoelasticCalibrationConflict(
                        "Selection idempotency key was reused with different content"
                    )
                return self.selections[existing_idempotency[1]]
            self.selection_idempotency[idempotency_key] = (
                digest,
                value.value.selection_id,
            )
        existing_selection = self.selections.get(value.value.selection_id)
        if existing_selection is not None:
            return existing_selection
        self.selections[value.value.selection_id] = value
        return value

    def get_selection(
        self,
        selection_id: UUID,
        *,
        context: SecurityContext | None = None,
        decision: AuthorizationDecision | None = None,
    ) -> CalibrationSelectionSnapshot:
        del context, decision
        try:
            return self.selections[selection_id]
        except KeyError as error:
            raise LinearViscoelasticCalibrationNotFound("Selection is not visible") from error


_IN_MEMORY_REPOSITORY_PROTOCOL: type[LinearViscoelasticCalibrationRepository] = (
    InMemoryLinearViscoelasticCalibrationRepository
)
