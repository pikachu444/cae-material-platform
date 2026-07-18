"""Framework-free T-04 RBAC/ABAC policy value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    IdentityAccessError,
    SecurityContext,
)

_DATABASE_PERMISSION = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


class AuthorizationDenied(AccessDenied):
    """No active binding grants the requested action and row attributes."""


class AuthorizationUnavailable(IdentityAccessError):
    """Authorization data or its database enforcement boundary is unavailable."""


class RoleBindingConflict(IdentityAccessError):
    """An identical immutable role grant already exists."""


class DataClassification(StrEnum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    EXPORT_CONTROLLED = "export_controlled"


_STANDARD_CLASSIFICATION_RANK = {
    DataClassification.INTERNAL: 0,
    DataClassification.CONFIDENTIAL: 1,
    DataClassification.RESTRICTED: 2,
}


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    PROJECT_ADMIN = "project_admin"
    TEST_ENGINEER = "test_engineer"
    DATA_STEWARD = "data_steward"
    STATISTICAL_ANALYST = "statistical_analyst"
    MATERIAL_MODELER = "material_modeler"
    CAE_ANALYST = "cae_analyst"
    DOMAIN_REVIEWER = "domain_reviewer"
    RELEASE_APPROVER = "release_approver"
    CONSUMER = "consumer"
    PLUGIN_MAINTAINER = "plugin_maintainer"
    JOB_RUNNER = "job_runner"
    AUDITOR = "auditor"


class Permission(StrEnum):
    PLATFORM_MANAGE = "platform.manage"
    IDENTITY_MANAGE = "identity.manage"
    PROJECT_MANAGE = "project.manage"
    CATALOG_READ = "catalog.read"
    CATALOG_WRITE = "catalog.write"
    TESTING_READ = "testing.read"
    TESTING_WRITE = "testing.write"
    ARTIFACT_READ = "artifact.read"
    ARTIFACT_WRITE = "artifact.write"
    DATASET_READ = "dataset.read"
    DATASET_WRITE = "dataset.write"
    PROCESSING_READ = "processing.read"
    PROCESSING_EXECUTE = "processing.execute"
    STATISTICS_READ = "statistics.read"
    STATISTICS_EXECUTE = "statistics.execute"
    MODELING_READ = "modeling.read"
    MODELING_WRITE = "modeling.write"
    CALIBRATION_EXECUTE = "calibration.execute"
    EXPORT_READ = "export.read"
    EXPORT_EXECUTE = "export.execute"
    VALIDATION_READ = "validation.read"
    VALIDATION_EXECUTE = "validation.execute"
    REVIEW_REQUEST = "review.request"
    REVIEW_READ = "review.read"
    REVIEW_DECIDE = "review.decide"
    RELEASE_READ = "release.read"
    RELEASE_PUBLISH = "release.publish"
    PLUGIN_READ = "plugin.read"
    PLUGIN_SUBMIT = "plugin.submit"
    PLUGIN_ACTIVATE = "plugin.activate"
    JOB_READ = "job.read"
    JOB_SUBMIT = "job.submit"
    JOB_CONTROL = "job.control"
    JOB_EXECUTE = "job.execute"
    PROVENANCE_READ = "provenance.read"
    AUDIT_READ = "audit.read"


class ProductRole(StrEnum):
    """Small product-facing role vocabulary exposed to normal administrators."""

    ADMINISTRATOR = "administrator"
    USER = "user"


class FeatureGrant(StrEnum):
    """Product capabilities that can be assigned without exposing internal RBAC roles."""

    SCHEMA_CONFIGURATION = "schema_configuration"
    CATALOG_EDIT = "catalog_edit"
    PROCESSING_CALIBRATION = "processing_calibration"
    MODEL_APPROVAL = "model_approval"
    SOLVER_CARD_EXPORT = "solver_card_export"


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _trimmed(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{name} must be trimmed and contain 1..{maximum} characters")


@dataclass(frozen=True, slots=True)
class BindingSubject:
    principal_id: UUID | None = None
    group_issuer: str | None = None
    group_name: str | None = None

    def __post_init__(self) -> None:
        principal = self.principal_id is not None
        group = self.group_issuer is not None or self.group_name is not None
        if principal == group:
            raise ValueError("binding subject must be exactly one principal or group")
        if principal:
            if self.principal_id is not None and self.principal_id.int == 0:
                raise ValueError("principal binding UUID must be non-zero")
            return
        if self.group_issuer is None or self.group_name is None:
            raise ValueError("group binding requires issuer and group name")
        _trimmed("group_issuer", self.group_issuer, 2048)
        _trimmed("group_name", self.group_name, 255)

    @classmethod
    def for_principal(cls, principal_id: UUID) -> BindingSubject:
        return cls(principal_id=principal_id)

    @classmethod
    def for_group(cls, issuer: str, group_name: str) -> BindingSubject:
        return cls(group_issuer=issuer, group_name=group_name)

    def matches(self, context: SecurityContext) -> bool:
        if self.principal_id is not None:
            return self.principal_id == context.principal.id
        return self.group_issuer == context.issuer and self.group_name in context.groups


@dataclass(frozen=True, slots=True)
class RoleBinding:
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    subject: BindingSubject
    role: Role
    max_classification: DataClassification
    allow_export_controlled: bool
    valid_from: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.id.int == 0 or self.organization_id.int == 0:
            raise ValueError("binding and organization UUIDs must be non-zero")
        if self.project_id is not None and self.project_id.int == 0:
            raise ValueError("project UUID must be non-zero when present")
        if self.max_classification is DataClassification.EXPORT_CONTROLLED:
            raise ValueError(
                "max_classification is limited to internal/confidential/restricted; "
                "use allow_export_controlled for the export compartment"
            )
        _aware("valid_from", self.valid_from)
        if self.expires_at is not None:
            _aware("expires_at", self.expires_at)
            if self.expires_at <= self.valid_from:
                raise ValueError("expires_at must follow valid_from")
        if self.revoked_at is not None:
            _aware("revoked_at", self.revoked_at)
            if self.revoked_at < self.valid_from:
                raise ValueError("revoked_at cannot precede valid_from")

    def applies_to(self, context: SecurityContext, observed_at: datetime) -> bool:
        _aware("observed_at", observed_at)
        return (
            self.organization_id == context.organization_id
            and (self.project_id is None or self.project_id == context.project_id)
            and self.subject.matches(context)
            and self.revoked_at is None
            and self.valid_from <= observed_at
            and (self.expires_at is None or observed_at < self.expires_at)
        )


@dataclass(frozen=True, slots=True)
class ProductAccessAssignment:
    """Append-only Administrator/User assignment with explicit typed feature grants."""

    id: UUID
    organization_id: UUID
    project_id: UUID | None
    subject: BindingSubject
    product_role: ProductRole
    feature_grants: tuple[FeatureGrant, ...]
    max_classification: DataClassification
    allow_export_controlled: bool
    valid_from: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.id.int == 0 or self.organization_id.int == 0:
            raise ValueError("assignment and organization UUIDs must be non-zero")
        if self.project_id is not None and self.project_id.int == 0:
            raise ValueError("project UUID must be non-zero when present")
        if tuple(sorted(set(self.feature_grants), key=str)) != self.feature_grants:
            raise ValueError("feature grants must be sorted and unique")
        if self.product_role is ProductRole.ADMINISTRATOR and set(self.feature_grants) != set(
            FeatureGrant
        ):
            raise ValueError("Administrator assignments must contain every product feature grant")
        if self.max_classification is DataClassification.EXPORT_CONTROLLED:
            raise ValueError("use allow_export_controlled for the export compartment")
        _aware("valid_from", self.valid_from)
        if self.expires_at is not None:
            _aware("expires_at", self.expires_at)
            if self.expires_at <= self.valid_from:
                raise ValueError("expires_at must follow valid_from")
        if self.revoked_at is not None:
            _aware("revoked_at", self.revoked_at)
            if self.revoked_at < self.valid_from:
                raise ValueError("revoked_at cannot precede valid_from")

    def applies_to(self, context: SecurityContext, observed_at: datetime) -> bool:
        _aware("observed_at", observed_at)
        return (
            self.organization_id == context.organization_id
            and (self.project_id is None or self.project_id == context.project_id)
            and self.subject.matches(context)
            and self.revoked_at is None
            and self.valid_from <= observed_at
            and (self.expires_at is None or observed_at < self.expires_at)
        )


@dataclass(frozen=True, slots=True)
class ProductAccessSummary:
    """Effective product vocabulary returned to the signed-in user."""

    product_role: ProductRole
    feature_grants: tuple[FeatureGrant, ...]
    legacy_compatible: bool

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.feature_grants), key=str)) != self.feature_grants:
            raise ValueError("effective feature grants must be sorted and unique")


def classification_allows(
    maximum: DataClassification,
    allow_export_controlled: bool,
    requested: DataClassification,
) -> bool:
    if maximum is DataClassification.EXPORT_CONTROLLED:
        raise ValueError("standard maximum cannot be export_controlled")
    if requested is DataClassification.EXPORT_CONTROLLED:
        return allow_export_controlled
    return _STANDARD_CLASSIFICATION_RANK[requested] <= _STANDARD_CLASSIFICATION_RANK[maximum]


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    principal_id: UUID
    organization_id: UUID
    project_id: UUID
    permission: Permission
    roles: tuple[Role, ...]
    database_permissions: tuple[str, ...]
    max_classification: DataClassification
    allow_export_controlled: bool
    request_id: UUID
    trace_id: str
    decided_at: datetime

    def __post_init__(self) -> None:
        if any(
            value.int == 0
            for value in (
                self.principal_id,
                self.organization_id,
                self.project_id,
                self.request_id,
            )
        ):
            raise ValueError("authorization UUIDs must be non-zero")
        if not self.roles or tuple(sorted(set(self.roles), key=str)) != self.roles:
            raise ValueError("authorization roles must be non-empty, sorted, and unique")
        if (
            not self.database_permissions
            or tuple(sorted(set(self.database_permissions))) != self.database_permissions
            or any(
                _DATABASE_PERMISSION.fullmatch(permission) is None
                for permission in self.database_permissions
            )
        ):
            raise ValueError("database permissions must be non-empty, sorted, and unique")
        if self.permission.value not in self.database_permissions:
            raise ValueError("requested permission must be present in database permissions")
        if self.max_classification is DataClassification.EXPORT_CONTROLLED:
            raise ValueError("standard maximum cannot be export_controlled")
        _trimmed("trace_id", self.trace_id, 255)
        _aware("decided_at", self.decided_at)

    def allows(
        self,
        organization_id: UUID,
        project_id: UUID,
        classification: DataClassification,
    ) -> bool:
        return (
            organization_id == self.organization_id
            and project_id == self.project_id
            and classification_allows(
                self.max_classification,
                self.allow_export_controlled,
                classification,
            )
        )
