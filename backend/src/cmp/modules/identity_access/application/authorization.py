"""T-04 deny-by-default RBAC/ABAC authorization service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    AuthorizationDenied,
    BindingSubject,
    DataClassification,
    Permission,
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import SecurityContext


class RoleBindingRepository(Protocol):
    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]: ...


class RoleBindingAdministrationRepository(Protocol):
    def append(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: RoleBinding,
        created_at: datetime,
        grant_reason: str,
    ) -> RoleBinding: ...

    def revoke(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...


ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = {
    Role.PLATFORM_ADMIN: frozenset({Permission.PLATFORM_MANAGE}),
    Role.ORG_ADMIN: frozenset(
        {
            Permission.IDENTITY_MANAGE,
            Permission.PROJECT_MANAGE,
            Permission.PLUGIN_READ,
            Permission.PLUGIN_ACTIVATE,
        }
    ),
    Role.PROJECT_ADMIN: frozenset({Permission.PROJECT_MANAGE}),
    Role.TEST_ENGINEER: frozenset(
        {
            Permission.TESTING_READ,
            Permission.TESTING_WRITE,
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.DATA_STEWARD: frozenset(
        {
            Permission.TESTING_READ,
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.DATASET_WRITE,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
        }
    ),
    Role.STATISTICAL_ANALYST: frozenset(
        {
            Permission.DATASET_READ,
            Permission.STATISTICS_READ,
            Permission.STATISTICS_EXECUTE,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.MATERIAL_MODELER: frozenset(
        {
            Permission.DATASET_READ,
            Permission.STATISTICS_READ,
            Permission.PROCESSING_READ,
            Permission.PROCESSING_EXECUTE,
            Permission.MODELING_READ,
            Permission.MODELING_WRITE,
            Permission.CALIBRATION_EXECUTE,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.CAE_ANALYST: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.EXPORT_EXECUTE,
            Permission.VALIDATION_READ,
            Permission.VALIDATION_EXECUTE,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.DOMAIN_REVIEWER: frozenset(
        {
            Permission.REVIEW_READ,
            Permission.REVIEW_DECIDE,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.RELEASE_APPROVER: frozenset(
        {
            Permission.REVIEW_READ,
            Permission.RELEASE_READ,
            Permission.RELEASE_PUBLISH,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.CONSUMER: frozenset({Permission.RELEASE_READ}),
    Role.PLUGIN_MAINTAINER: frozenset(
        {Permission.PLUGIN_READ, Permission.PLUGIN_SUBMIT}
    ),
    Role.AUDITOR: frozenset({Permission.AUDIT_READ, Permission.PROVENANCE_READ}),
}

_MODIFYING_OPERATIONS = frozenset(
    {"activate", "control", "decide", "execute", "manage", "publish", "submit", "write"}
)
_DATABASE_PERMISSION_DEPENDENCIES: Mapping[Permission, frozenset[Permission]] = {
    Permission.PROCESSING_EXECUTE: frozenset(
        {Permission.DATASET_READ, Permission.PROCESSING_READ}
    ),
    Permission.STATISTICS_EXECUTE: frozenset(
        {Permission.DATASET_READ, Permission.STATISTICS_READ}
    ),
    Permission.MODELING_WRITE: frozenset({Permission.MODELING_READ}),
    Permission.CALIBRATION_EXECUTE: frozenset(
        {Permission.DATASET_READ, Permission.MODELING_READ}
    ),
    Permission.EXPORT_EXECUTE: frozenset(
        {Permission.ARTIFACT_READ, Permission.MODELING_READ, Permission.EXPORT_READ}
    ),
    Permission.VALIDATION_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.VALIDATION_READ,
        }
    ),
    Permission.REVIEW_DECIDE: frozenset(
        {Permission.REVIEW_READ, Permission.PROVENANCE_READ}
    ),
    Permission.RELEASE_PUBLISH: frozenset(
        {Permission.REVIEW_READ, Permission.RELEASE_READ, Permission.PROVENANCE_READ}
    ),
    Permission.PLUGIN_SUBMIT: frozenset({Permission.PLUGIN_READ}),
    Permission.PLUGIN_ACTIVATE: frozenset({Permission.PLUGIN_READ}),
    Permission.JOB_SUBMIT: frozenset({Permission.JOB_READ}),
    Permission.JOB_CONTROL: frozenset({Permission.JOB_READ}),
}


def database_permissions_for(permission: Permission) -> tuple[str, ...]:
    """Expand one authorized command into its minimum transaction-local DB permissions."""

    module, operation = permission.value.split(".", maxsplit=1)
    permissions = {
        permission.value,
        *(item.value for item in _DATABASE_PERMISSION_DEPENDENCIES.get(permission, ())),
    }
    read_permission = f"{module}.read"
    if operation != "read" and any(item.value == read_permission for item in Permission):
        permissions.add(read_permission)
    if module not in {"audit", "identity", "platform", "project", "provenance"}:
        permissions.add("governance.read")
        if operation in _MODIFYING_OPERATIONS:
            permissions.add("governance.write")
    return tuple(sorted(permissions))


class AuthorizationService:
    def __init__(
        self,
        *,
        bindings: RoleBindingRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bindings = bindings
        self._clock = clock or (lambda: datetime.now(UTC))

    def authorize(
        self, context: SecurityContext, permission: Permission
    ) -> AuthorizationDecision:
        observed_at = self._clock()
        applicable = self._bindings.find_applicable(context, observed_at)
        granting = tuple(
            binding
            for binding in applicable
            if binding.applies_to(context, observed_at)
            and permission in ROLE_PERMISSIONS[binding.role]
        )
        if not granting:
            raise AuthorizationDenied("permission_denied")

        maximum = max(
            (binding.max_classification for binding in granting),
            key=lambda value: (
                DataClassification.INTERNAL,
                DataClassification.CONFIDENTIAL,
                DataClassification.RESTRICTED,
            ).index(value),
        )
        return AuthorizationDecision(
            principal_id=context.principal.id,
            organization_id=context.organization_id,
            project_id=context.project_id,
            permission=permission,
            roles=tuple(sorted({binding.role for binding in granting}, key=str)),
            database_permissions=database_permissions_for(permission),
            max_classification=maximum,
            allow_export_controlled=any(
                binding.allow_export_controlled for binding in granting
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
            decided_at=observed_at,
        )


def _reason(name: str, value: str) -> None:
    if not value or value != value.strip() or len(value) > 2000 or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..2000 characters")


@dataclass(frozen=True, slots=True)
class GrantRoleBinding:
    organization_id: UUID
    project_id: UUID | None
    subject: BindingSubject
    role: Role
    max_classification: DataClassification
    allow_export_controlled: bool
    grant_reason: str
    valid_from: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _reason("grant_reason", self.grant_reason)


@dataclass(frozen=True, slots=True)
class RevokeRoleBinding:
    binding_id: UUID
    reason: str

    def __post_init__(self) -> None:
        if self.binding_id.int == 0:
            raise ValueError("binding_id must be non-zero")
        _reason("reason", self.reason)


class RoleBindingAdministrationService:
    def __init__(
        self,
        *,
        authorization: AuthorizationService,
        repository: RoleBindingAdministrationRepository,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._authorization = authorization
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def grant(
        self, context: SecurityContext, command: GrantRoleBinding
    ) -> RoleBinding:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        if command.organization_id != context.organization_id or command.project_id not in {
            None,
            context.project_id,
        }:
            raise AuthorizationDenied("binding_scope_mismatch")
        if command.role is Role.PLATFORM_ADMIN:
            raise AuthorizationDenied("platform_role_operator_only")
        created_at = self._clock()
        valid_from = command.valid_from or created_at
        if valid_from < created_at:
            raise ValueError("valid_from cannot precede grant creation time")
        binding = RoleBinding(
            id=self._id_factory(),
            organization_id=command.organization_id,
            project_id=command.project_id,
            subject=command.subject,
            role=command.role,
            max_classification=command.max_classification,
            allow_export_controlled=command.allow_export_controlled,
            valid_from=valid_from,
            expires_at=command.expires_at,
        )
        return self._repository.append(
            context=context,
            decision=decision,
            binding=binding,
            created_at=created_at,
            grant_reason=command.grant_reason,
        )

    def revoke(
        self, context: SecurityContext, command: RevokeRoleBinding
    ) -> None:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        self._repository.revoke(
            context=context,
            decision=decision,
            binding_id=command.binding_id,
            revoked_at=self._clock(),
            reason=command.reason,
        )
