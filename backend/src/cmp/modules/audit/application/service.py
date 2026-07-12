"""Protected audit query, export, integrity, and periodic sealing orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from cmp.modules.audit.domain.model import (
    AuditConflict,
    AuditEvent,
    AuditIntegrityReport,
    AuditOutcome,
    AuditSegmentRoot,
    verify_audit_integrity,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext


@dataclass(frozen=True, slots=True)
class AuditEventQuery:
    after_sequence: int = 0
    limit: int = 100
    action: str | None = None
    actor_id: UUID | None = None
    target_type: str | None = None
    target_id: UUID | None = None
    outcome: AuditOutcome | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None

    def __post_init__(self) -> None:
        if self.after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        if not 1 <= self.limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.target_id is not None and self.target_type is None:
            raise ValueError("target_id requires target_type")
        for name, value in (
            ("occurred_from", self.occurred_from),
            ("occurred_to", self.occurred_to),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{name} must be timezone-aware")
        if (
            self.occurred_from is not None
            and self.occurred_to is not None
            and self.occurred_to < self.occurred_from
        ):
            raise ValueError("occurred_to cannot precede occurred_from")


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    events: tuple[AuditEvent, ...]
    next_after_sequence: int | None


@dataclass(frozen=True, slots=True)
class AuditExportSegment:
    from_sequence: int
    to_sequence: int
    anchor_previous_hash: str
    events: tuple[AuditEvent, ...]
    segment_roots: tuple[AuditSegmentRoot, ...]
    integrity: AuditIntegrityReport


class AuditRepository(Protocol):
    def query_events(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: AuditEventQuery,
    ) -> AuditEventPage: ...

    def load_chain(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]: ...

    def export_range(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        from_sequence: int,
        to_sequence: int,
    ) -> tuple[str, tuple[AuditEvent, ...], tuple[AuditSegmentRoot, ...]]: ...

    def seal_next(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        maximum_events: int,
    ) -> AuditSegmentRoot | None: ...


class AuditService:
    def __init__(self, *, repository: AuditRepository) -> None:
        self._repository = repository

    @staticmethod
    def _assert_read_scope(
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        if (
            decision.permission is not Permission.AUDIT_READ
            or "audit.read" not in decision.database_permissions
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise AuditConflict("audit authorization does not match the request scope")

    def query_events(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: AuditEventQuery,
    ) -> AuditEventPage:
        self._assert_read_scope(context, decision)
        return self._repository.query_events(
            context=context,
            decision=decision,
            query=query,
        )

    def integrity(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> AuditIntegrityReport:
        self._assert_read_scope(context, decision)
        events, roots = self._repository.load_chain(context=context, decision=decision)
        return verify_audit_integrity(events, roots)

    def export(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        from_sequence: int,
        to_sequence: int,
    ) -> AuditExportSegment:
        self._assert_read_scope(context, decision)
        if from_sequence <= 0 or to_sequence < from_sequence:
            raise ValueError("audit export range is invalid")
        if to_sequence - from_sequence + 1 > 10_000:
            raise ValueError("audit export is limited to 10000 events")
        all_events, all_roots = self._repository.load_chain(
            context=context,
            decision=decision,
        )
        anchor, events, roots = self._repository.export_range(
            context=context,
            decision=decision,
            from_sequence=from_sequence,
            to_sequence=to_sequence,
        )
        return AuditExportSegment(
            from_sequence=from_sequence,
            to_sequence=to_sequence,
            anchor_previous_hash=anchor,
            events=events,
            segment_roots=roots,
            integrity=verify_audit_integrity(all_events, all_roots),
        )

    def seal_next(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        maximum_events: int = 1000,
    ) -> AuditSegmentRoot | None:
        self._assert_read_scope(context, decision)
        if "audit.seal" not in decision.database_permissions:
            raise AuditConflict("audit sealing requires the internal audit.seal capability")
        if not 1 <= maximum_events <= 10_000:
            raise ValueError("maximum_events must be between 1 and 10000")
        return self._repository.seal_next(
            context=context,
            decision=decision,
            maximum_events=maximum_events,
        )
