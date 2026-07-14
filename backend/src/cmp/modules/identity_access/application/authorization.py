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
            Permission.CATALOG_READ,
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
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
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
            Permission.CATALOG_READ,
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
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
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.TESTING_READ,
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.DATASET_WRITE,
            Permission.STATISTICS_READ,
            Permission.PROCESSING_READ,
            Permission.PROCESSING_EXECUTE,
            Permission.MODELING_READ,
            Permission.MODELING_WRITE,
            Permission.EXPORT_READ,
            Permission.EXPORT_EXECUTE,
            Permission.CALIBRATION_EXECUTE,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.CAE_ANALYST: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.ARTIFACT_READ,
            # A reference validation run freezes a rendered deck and terminal
            # evidence as immutable Artifacts, and reads the selected Dataset
            # revision.  These are transaction-local dependencies of
            # validation.execute; they do not grant public write routes.
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
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
            Permission.CATALOG_READ,
            Permission.REVIEW_READ,
            Permission.REVIEW_DECIDE,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.RELEASE_APPROVER: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.REVIEW_READ,
            Permission.RELEASE_READ,
            Permission.RELEASE_PUBLISH,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.CONSUMER: frozenset({Permission.CATALOG_READ, Permission.RELEASE_READ}),
    Role.PLUGIN_MAINTAINER: frozenset({Permission.PLUGIN_READ, Permission.PLUGIN_SUBMIT}),
    # Operational role for service principals. T-18 adds only the package and scoped
    # artifact permissions required to resolve inputs and commit validated outputs.
    # It is provisioned outside the public role-administration service and cannot grant
    # human business, review, release, or plugin activation permissions.
    Role.JOB_RUNNER: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.PLUGIN_READ,
            Permission.JOB_READ,
            Permission.JOB_EXECUTE,
        }
    ),
    Role.AUDITOR: frozenset({Permission.AUDIT_READ, Permission.PROVENANCE_READ}),
}

_MODIFYING_OPERATIONS = frozenset(
    {"activate", "control", "decide", "execute", "manage", "publish", "submit", "write"}
)
_DATABASE_PERMISSION_DEPENDENCIES: Mapping[Permission, frozenset[Permission]] = {
    # Reference import detection reads the verified immutable raw artifact before
    # it records a human-approved mapping revision.  This remains a transaction
    # capability only; the public Artifact endpoint still requires artifact.read.
    Permission.TESTING_WRITE: frozenset({Permission.CATALOG_READ, Permission.ARTIFACT_READ}),
    # A Dataset is an immutable interpretation of an Artifact.  Reading a curve
    # therefore needs the same row-visible Artifact access as reading its Dataset
    # metadata; otherwise the API could disclose metadata but not safely load the
    # immutable content it identifies.
    Permission.DATASET_READ: frozenset({Permission.ARTIFACT_READ}),
    Permission.DATASET_WRITE: frozenset(
        {Permission.ARTIFACT_READ, Permission.ARTIFACT_WRITE, Permission.TESTING_READ}
    ),
    # A committed Processing Run reads a pinned Dataset Artifact, writes a new immutable derived
    # Artifact, and asks the Dataset owner to register the resulting processed Dataset revision.
    # These are transaction-local capabilities only; the public Dataset/Artifact write endpoints
    # still require their own top-level permissions.
    Permission.PROCESSING_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.DATASET_WRITE,
            Permission.PROCESSING_READ,
            Permission.TESTING_READ,
        }
    ),
    # A committed Statistical Run reads two pinned Dataset Artifacts and writes one immutable
    # typed curve-result Artifact. These are transaction-local capabilities, not public Artifact
    # endpoint grants inferred by the Statistics route.
    Permission.STATISTICS_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.STATISTICS_READ,
        }
    ),
    # Candidate diagnostics are immutable derived Artifacts exposed only through a Modeling-owned
    # preview route. This remains an internal database capability, not public Artifact API access.
    Permission.MODELING_READ: frozenset({Permission.ARTIFACT_READ}),
    Permission.MODELING_WRITE: frozenset({Permission.CATALOG_READ, Permission.MODELING_READ}),
    Permission.CALIBRATION_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
        }
    ),
    Permission.EXPORT_READ: frozenset({Permission.MODELING_READ}),
    Permission.EXPORT_EXECUTE: frozenset(
        {Permission.ARTIFACT_READ, Permission.MODELING_READ, Permission.EXPORT_READ}
    ),
    # Validation result previews read only Validation-owned typed reports, but those reports
    # are immutable Artifacts.  The capability is transaction-local; it does not make the
    # public Artifact content route reachable through validation.read.
    Permission.VALIDATION_READ: frozenset({Permission.ARTIFACT_READ}),
    Permission.VALIDATION_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.VALIDATION_READ,
        }
    ),
    Permission.REVIEW_DECIDE: frozenset({Permission.REVIEW_READ, Permission.PROVENANCE_READ}),
    Permission.RELEASE_PUBLISH: frozenset(
        {Permission.REVIEW_READ, Permission.RELEASE_READ, Permission.PROVENANCE_READ}
    ),
    Permission.PLUGIN_SUBMIT: frozenset({Permission.PLUGIN_READ}),
    Permission.PLUGIN_ACTIVATE: frozenset({Permission.PLUGIN_READ}),
    Permission.JOB_SUBMIT: frozenset({Permission.JOB_READ}),
    Permission.JOB_CONTROL: frozenset({Permission.JOB_READ}),
    Permission.JOB_EXECUTE: frozenset({Permission.JOB_READ}),
}

# These commands may invoke a T-13 fail-closed provenance hook in the owning domain
# transaction. ``provenance.write`` is deliberately not a public role permission; it is a
# minimum DB capability derived only after one of the owning commands was authorized.
_PROVENANCE_WRITING_COMMANDS = frozenset(
    {
        Permission.TESTING_WRITE,
        Permission.CATALOG_WRITE,
        Permission.ARTIFACT_WRITE,
        Permission.DATASET_WRITE,
        Permission.PROCESSING_EXECUTE,
        Permission.STATISTICS_EXECUTE,
        Permission.MODELING_WRITE,
        Permission.CALIBRATION_EXECUTE,
        Permission.EXPORT_EXECUTE,
        Permission.VALIDATION_EXECUTE,
        Permission.REVIEW_DECIDE,
        Permission.RELEASE_PUBLISH,
        Permission.JOB_EXECUTE,
    }
)

# T-16 outbox rows are inserted only by an already-authorized owning command. Dispatch and
# inbox capabilities belong exclusively to the project-scoped operational Job Runner.
_EVENT_PUBLISHING_COMMANDS = frozenset(
    {
        Permission.ARTIFACT_WRITE,
        Permission.TESTING_WRITE,
        Permission.DATASET_WRITE,
        Permission.PROCESSING_EXECUTE,
        Permission.STATISTICS_EXECUTE,
        Permission.MODELING_WRITE,
        Permission.CALIBRATION_EXECUTE,
        Permission.EXPORT_EXECUTE,
        Permission.VALIDATION_EXECUTE,
        Permission.REVIEW_DECIDE,
        Permission.RELEASE_PUBLISH,
    }
)


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
    if permission in _PROVENANCE_WRITING_COMMANDS:
        permissions.update({"provenance.read", "provenance.write"})
    if permission in _EVENT_PUBLISHING_COMMANDS:
        permissions.add("events.publish")
    # T-05 audit rows are appended only from an already-authorized modifying command.
    # ``audit.append`` is an internal transaction capability, never a role permission or
    # public graph-style write API.
    if operation in _MODIFYING_OPERATIONS:
        permissions.add("audit.append")
    if permission is Permission.JOB_EXECUTE:
        permissions.update({"events.consume", "events.dispatch"})
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

    def authorize(self, context: SecurityContext, permission: Permission) -> AuthorizationDecision:
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
            allow_export_controlled=any(binding.allow_export_controlled for binding in granting),
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

    def grant(self, context: SecurityContext, command: GrantRoleBinding) -> RoleBinding:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        if command.organization_id != context.organization_id or command.project_id not in {
            None,
            context.project_id,
        }:
            raise AuthorizationDenied("binding_scope_mismatch")
        if command.role in {Role.PLATFORM_ADMIN, Role.JOB_RUNNER}:
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

    def revoke(self, context: SecurityContext, command: RevokeRoleBinding) -> None:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        self._repository.revoke(
            context=context,
            decision=decision,
            binding_id=command.binding_id,
            revoked_at=self._clock(),
            reason=command.reason,
        )
