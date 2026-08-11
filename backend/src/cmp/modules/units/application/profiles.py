"""Stable Unit Profile identity, immutable revisions, and explicit conversions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.units.domain.profiles import UnitProfileContent, UnitProfilePin
from cmp.modules.units.domain.system import (
    ConversionResult,
    QuantityReference,
    UnitError,
    convert_value,
    unit_system_contract,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

UNIT_PROFILE_AGGREGATE_TYPE = "units.unit_profile"
UNIT_PROFILE_SCHEMA_ID = "urn:cmp:units:unit-profile:1.0.0"
UNIT_PROFILE_SCHEMA_VERSION = "1.0.0"


class UnitProfileNotFound(UnitError):
    def __init__(self, message: str = "Unit Profile revision is not visible") -> None:
        super().__init__(
            code="CMP-UNIT-0007",
            message=message,
            location="unit_profile",
        )


@dataclass(frozen=True, slots=True)
class UnitProfileSnapshot:
    id: UUID
    current: RevisionRecord
    content: UnitProfileContent

    @property
    def pin(self) -> UnitProfilePin:
        return UnitProfilePin(self.id, self.current.revision_id, self.current.content_hash)


@dataclass(frozen=True, slots=True)
class CreateUnitProfile:
    classification: DataClassification
    content: UnitProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseUnitProfile:
    expected_current_revision_id: UUID
    content: UnitProfileContent
    change_reason: str


class UnitProfileRepository(Protocol):
    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[UnitProfileContent]: ...

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> UnitProfileSnapshot: ...

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> UnitProfileSnapshot: ...

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[UnitProfileSnapshot, ...]: ...


def _require(
    context: SecurityContext, decision: AuthorizationDecision, permission: Permission
) -> None:
    if (
        decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
        or permission.value not in decision.database_permissions
    ):
        raise UnitError(
            code="CMP-UNIT-0008",
            message="authorization decision lacks the required Unit Profile capability",
            location="authorization",
        )


class CommonUnitService:
    def __init__(
        self,
        *,
        repository: UnitProfileRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id = id_factory

    @staticmethod
    def unit_system() -> dict[str, object]:
        return unit_system_contract()

    @staticmethod
    def convert(
        value: str | Decimal,
        *,
        original_unit_string: str,
        source: QuantityReference,
        target: QuantityReference,
        location: str,
    ) -> ConversionResult:
        return convert_value(
            value,
            original_unit_string=original_unit_string,
            source=source,
            target=target,
            location=location,
        )

    def create_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateUnitProfile,
    ) -> UnitProfileSnapshot:
        _require(context, decision, Permission.UNITS_WRITE)
        profile_id = self._id()
        record = RevisionService(
            aggregate_type=UNIT_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=profile_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=UNIT_PROFILE_SCHEMA_ID,
                schema_version=UNIT_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return UnitProfileSnapshot(profile_id, record, command.content)

    def revise_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseUnitProfile,
    ) -> UnitProfileSnapshot:
        _require(context, decision, Permission.UNITS_WRITE)
        current = self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )
        if current.content.profile_key != command.content.profile_key:
            raise UnitError(
                code="CMP-UNIT-0005",
                message="Unit Profile key cannot change across revisions",
                location="content.profile_key",
            )
        record = RevisionService(
            aggregate_type=UNIT_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=profile_id,
                scope=current.current.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=UNIT_PROFILE_SCHEMA_ID,
                schema_version=UNIT_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return UnitProfileSnapshot(profile_id, record, command.content)

    def get_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        *,
        write: bool = False,
    ) -> UnitProfileSnapshot:
        _require(
            context,
            decision,
            Permission.UNITS_WRITE if write else Permission.UNITS_READ,
        )
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    def get_profile_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> UnitProfileSnapshot:
        _require(context, decision, Permission.UNITS_READ)
        return self._repository.get_profile_revision(
            context=context,
            decision=decision,
            profile_id=profile_id,
            revision_id=revision_id,
        )

    def resolve_pin(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        pin: UnitProfilePin,
    ) -> UnitProfileSnapshot:
        snapshot = self.get_profile_revision(
            context, decision, pin.profile_id, pin.revision_id
        )
        if snapshot.current.content_hash != pin.content_sha256:
            raise UnitError(
                code="CMP-UNIT-0009",
                message="Unit Profile content hash does not match the exact revision",
                location="unit_profile.content_sha256",
            )
        return snapshot

    def list_profiles(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[UnitProfileSnapshot, ...]:
        _require(context, decision, Permission.UNITS_READ)
        return self._repository.list_profiles(context=context, decision=decision)


__all__ = [
    "UNIT_PROFILE_AGGREGATE_TYPE",
    "UNIT_PROFILE_SCHEMA_ID",
    "UNIT_PROFILE_SCHEMA_VERSION",
    "CommonUnitService",
    "CreateUnitProfile",
    "ReviseUnitProfile",
    "UnitProfileNotFound",
    "UnitProfileRepository",
    "UnitProfileSnapshot",
]
