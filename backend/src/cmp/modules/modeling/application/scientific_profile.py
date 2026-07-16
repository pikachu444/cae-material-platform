"""Application service for immutable scientific calibration profile revisions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.scientific_profile import (
    SCIENTIFIC_PROFILE_SCHEMA_ID,
    SCIENTIFIC_PROFILE_SCHEMA_VERSION,
    ScientificApprovalStatus,
    ScientificProfileConflict,
    ScientificProfileContent,
    ScientificProfileFamily,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

SCIENTIFIC_PROFILE_AGGREGATE_TYPE = "modeling.scientific_profile"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot:
    record: RevisionRecord
    content: ScientificProfileContent


@dataclass(frozen=True, slots=True)
class ScientificProfileSnapshot:
    id: UUID
    current: RevisionSnapshot


@dataclass(frozen=True, slots=True)
class CreateScientificProfile:
    classification: str
    content: ScientificProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseScientificProfile:
    expected_current_revision_id: UUID
    content: ScientificProfileContent
    change_reason: str


class ScientificProfileRepository(Protocol):
    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ScientificProfileContent]: ...

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> ScientificProfileSnapshot: ...

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> RevisionSnapshot: ...

    def list_profiles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        family: ScientificProfileFamily | None,
    ) -> tuple[ScientificProfileSnapshot, ...]: ...


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
        raise ScientificProfileConflict("authorization decision does not match profile request")


def _text(name: str, value: str, maximum: int) -> str:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")
    return value


class ScientificProfileService:
    def __init__(
        self,
        *,
        repository: ScientificProfileRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateScientificProfile,
    ) -> ScientificProfileSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        self._require_reference_status(command.content)
        profile_id = self._id_factory()
        if profile_id.int == 0:
            raise RuntimeError("scientific profile id_factory returned zero")
        record = RevisionService(
            aggregate_type=SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=profile_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    _text("classification", command.classification, 64),
                ),
                schema_id=SCIENTIFIC_PROFILE_SCHEMA_ID,
                schema_version=SCIENTIFIC_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_text("change_reason", command.change_reason, 2000),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ScientificProfileSnapshot(profile_id, RevisionSnapshot(record, command.content))

    def revise(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseScientificProfile,
    ) -> ScientificProfileSnapshot:
        _require(context, decision, Permission.MODELING_WRITE)
        self._require_reference_status(command.content)
        current = self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )
        if current.current.content.family is not command.content.family:
            raise ScientificProfileConflict(
                "scientific profile family cannot change across revisions"
            )
        if current.current.content.profile_label != command.content.profile_label:
            raise ScientificProfileConflict(
                "scientific profile label is stable and cannot change across revisions"
            )
        record = RevisionService(
            aggregate_type=SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=profile_id,
                scope=current.current.record.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=SCIENTIFIC_PROFILE_SCHEMA_ID,
                schema_version=SCIENTIFIC_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=_text("change_reason", command.change_reason, 2000),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ScientificProfileSnapshot(profile_id, RevisionSnapshot(record, command.content))

    def get(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> ScientificProfileSnapshot:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    def list(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        family: ScientificProfileFamily | None = None,
    ) -> tuple[ScientificProfileSnapshot, ...]:
        _require(context, decision, Permission.MODELING_READ)
        return self._repository.list_profiles(
            context=context, decision=decision, family=family
        )

    def get_revision_for_calibration(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> RevisionSnapshot:
        if decision.permission is not Permission.CALIBRATION_EXECUTE:
            raise ScientificProfileConflict("calibration execution permission is required")
        return self._repository.get_profile_revision(
            context=context,
            decision=decision,
            profile_id=profile_id,
            profile_revision_id=profile_revision_id,
        )

    @staticmethod
    def _require_reference_status(content: ScientificProfileContent) -> None:
        if content.approval_status is not ScientificApprovalStatus.REFERENCE_UNAPPROVED:
            raise ScientificProfileConflict(
                "domain approval requires a governed review transition that is not yet available"
            )
