"""Stable Mapping Profile identities with immutable channel/Attribute revisions (T-53)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.domain.common_pipeline import (
    CommonPipelineError,
    MappingProfileContent,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

MAPPING_PROFILE_AGGREGATE_TYPE = "processing.mapping_profile"
MAPPING_PROFILE_SCHEMA_ID = "urn:cmp:processing:mapping-profile:1.0.0"
MAPPING_PROFILE_SCHEMA_VERSION = "1.0.0"


class MappingProfileNotFound(CommonPipelineError):
    pass


@dataclass(frozen=True, slots=True)
class MappingProfileSnapshot:
    id: UUID
    current: RevisionRecord
    content: MappingProfileContent


@dataclass(frozen=True, slots=True)
class CreateMappingProfile:
    classification: DataClassification
    content: MappingProfileContent
    change_reason: str


@dataclass(frozen=True, slots=True)
class ReviseMappingProfile:
    expected_current_revision_id: UUID
    content: MappingProfileContent
    change_reason: str


class MappingProfileRepository(Protocol):
    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[MappingProfileContent]: ...

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> MappingProfileSnapshot: ...

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> MappingProfileSnapshot: ...

    def list_profiles(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MappingProfileSnapshot, ...]: ...


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
        raise CommonPipelineError("authorization decision lacks Mapping Profile capability")


class MappingProfileService:
    def __init__(
        self,
        *,
        repository: MappingProfileRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id = id_factory

    def create_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateMappingProfile,
    ) -> MappingProfileSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        profile_id = self._id()
        record = RevisionService(
            aggregate_type=MAPPING_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=profile_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    command.classification.value,
                ),
                schema_id=MAPPING_PROFILE_SCHEMA_ID,
                schema_version=MAPPING_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MappingProfileSnapshot(profile_id, record, command.content)

    def revise_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        command: ReviseMappingProfile,
    ) -> MappingProfileSnapshot:
        _require(context, decision, Permission.PROCESSING_EXECUTE)
        current = self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )
        if current.content.profile_key != command.content.profile_key:
            raise CommonPipelineError("Mapping Profile key cannot change across revisions")
        record = RevisionService(
            aggregate_type=MAPPING_PROFILE_AGGREGATE_TYPE,
            store=self._repository.profile_store(context, decision),
        ).revise(
            ReviseAggregate(
                aggregate_id=profile_id,
                scope=current.current.scope,
                expected_current_revision_id=command.expected_current_revision_id,
                based_on_revision_id=command.expected_current_revision_id,
                schema_id=MAPPING_PROFILE_SCHEMA_ID,
                schema_version=MAPPING_PROFILE_SCHEMA_VERSION,
                content=command.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return MappingProfileSnapshot(profile_id, record, command.content)

    def get_profile(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        *,
        write: bool = False,
    ) -> MappingProfileSnapshot:
        _require(
            context,
            decision,
            Permission.PROCESSING_EXECUTE if write else Permission.PROCESSING_READ,
        )
        return self._repository.get_profile(
            context=context, decision=decision, profile_id=profile_id
        )

    def list_profiles(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MappingProfileSnapshot, ...]:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.list_profiles(context=context, decision=decision)

    def get_profile_revision(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        revision_id: UUID,
    ) -> MappingProfileSnapshot:
        _require(context, decision, Permission.PROCESSING_READ)
        return self._repository.get_profile_revision(
            context=context,
            decision=decision,
            profile_id=profile_id,
            revision_id=revision_id,
        )
