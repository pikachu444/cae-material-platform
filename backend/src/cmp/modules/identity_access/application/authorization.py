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
    FeatureGrant,
    Permission,
    ProductAccessAssignment,
    ProductAccessSummary,
    ProductRole,
    Role,
    RoleBinding,
    product_role_preset,
)
from cmp.modules.identity_access.domain.security import SecurityContext


class RoleBindingRepository(Protocol):
    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]: ...


class ProductAccessAssignmentReader(Protocol):
    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[ProductAccessAssignment, ...]: ...


class ProductAccessAssignmentRepository(ProductAccessAssignmentReader, Protocol):
    def list_assignments(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[ProductAccessAssignment, ...]: ...

    def append_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment: ProductAccessAssignment,
        created_at: datetime,
        grant_reason: str,
    ) -> ProductAccessAssignment: ...

    def revoke_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None: ...


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
            Permission.UNITS_READ,
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
            Permission.CATALOG_SCHEMA_APPLY,
            Permission.UNITS_READ,
            Permission.UNITS_WRITE,
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
            Permission.UNITS_READ,
            Permission.TESTING_READ,
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
            Permission.UNITS_READ,
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
            Permission.REVIEW_REQUEST,
            Permission.REVIEW_READ,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.CAE_ANALYST: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.UNITS_READ,
            Permission.TESTING_READ,
            Permission.ARTIFACT_READ,
            # A reference validation run freezes a rendered deck and terminal
            # evidence as immutable Artifacts, and reads the selected Dataset
            # revision.  These are transaction-local dependencies of
            # validation.execute; they do not grant public write routes.
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_READ,
            Permission.STATISTICS_READ,
            Permission.PROCESSING_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.EXPORT_EXECUTE,
            Permission.VALIDATION_READ,
            Permission.VALIDATION_EXECUTE,
            Permission.REVIEW_REQUEST,
            Permission.REVIEW_READ,
            Permission.JOB_READ,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    Role.DOMAIN_REVIEWER: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.UNITS_READ,
            Permission.REVIEW_READ,
            Permission.REVIEW_DECIDE,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.RELEASE_APPROVER: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.UNITS_READ,
            Permission.ARTIFACT_READ,
            Permission.TESTING_READ,
            Permission.DATASET_READ,
            Permission.PROCESSING_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.VALIDATION_READ,
            Permission.REVIEW_READ,
            Permission.RELEASE_READ,
            Permission.RELEASE_PUBLISH,
            Permission.PROVENANCE_READ,
        }
    ),
    Role.CONSUMER: frozenset(
        {Permission.CATALOG_READ, Permission.RELEASE_READ, Permission.UNITS_READ}
    ),
    Role.PLUGIN_MAINTAINER: frozenset({Permission.PLUGIN_READ, Permission.PLUGIN_SUBMIT}),
    # Operational role for project-scoped service principals.  The configured background
    # worker executes isolated plugin Jobs and the external export queue, so it needs the
    # corresponding command permissions while remaining outside human product access.
    # It is provisioned outside the public role-administration service and cannot grant
    # review, release, or plugin activation permissions.
    Role.JOB_RUNNER: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.EXPORT_EXECUTE,
            Permission.PLUGIN_READ,
            Permission.JOB_READ,
            Permission.JOB_EXECUTE,
        }
    ),
    Role.AUDITOR: frozenset({Permission.AUDIT_READ, Permission.PROVENANCE_READ}),
}

_PRODUCT_BASE_PERMISSIONS = frozenset(
    {
        Permission.CATALOG_READ,
        Permission.UNITS_READ,
        Permission.TESTING_READ,
        Permission.ARTIFACT_READ,
        Permission.DATASET_READ,
        Permission.PROCESSING_READ,
        Permission.STATISTICS_READ,
        Permission.MODELING_READ,
        Permission.EXPORT_READ,
        Permission.VALIDATION_READ,
        Permission.REVIEW_READ,
        # Every product assignment may submit its own immutable work for review;
        # deciding and review-backed publication remain Reviewer-only grants.
        Permission.REVIEW_REQUEST,
        Permission.RELEASE_READ,
        Permission.PROVENANCE_READ,
        Permission.JOB_READ,
    }
)

PRODUCT_FEATURE_PERMISSIONS: Mapping[FeatureGrant, frozenset[Permission]] = {
    FeatureGrant.SCHEMA_CONFIGURATION: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.CATALOG_SCHEMA_APPLY,
            Permission.UNITS_READ,
            Permission.UNITS_WRITE,
        }
    ),
    FeatureGrant.CATALOG_EDIT: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.TESTING_WRITE,
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_WRITE,
        }
    ),
    FeatureGrant.PROCESSING_CALIBRATION: frozenset(
        {
            Permission.ARTIFACT_WRITE,
            Permission.DATASET_WRITE,
            Permission.PROCESSING_EXECUTE,
            Permission.STATISTICS_EXECUTE,
            Permission.MODELING_WRITE,
            Permission.CALIBRATION_EXECUTE,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
    FeatureGrant.MODEL_APPROVAL: frozenset(
        {
            Permission.REVIEW_DECIDE,
            Permission.RELEASE_PUBLISH,
        }
    ),
    FeatureGrant.SOLVER_CARD_EXPORT: frozenset(
        {
            Permission.EXPORT_EXECUTE,
            Permission.JOB_SUBMIT,
            Permission.JOB_CONTROL,
        }
    ),
}

_FEATURE_EVIDENCE_ROLES: Mapping[FeatureGrant, frozenset[Role]] = {
    FeatureGrant.SCHEMA_CONFIGURATION: frozenset({Role.DATA_STEWARD}),
    FeatureGrant.CATALOG_EDIT: frozenset({Role.DATA_STEWARD, Role.TEST_ENGINEER}),
    FeatureGrant.PROCESSING_CALIBRATION: frozenset(
        {Role.STATISTICAL_ANALYST, Role.MATERIAL_MODELER}
    ),
    FeatureGrant.MODEL_APPROVAL: frozenset({Role.DOMAIN_REVIEWER, Role.RELEASE_APPROVER}),
    FeatureGrant.SOLVER_CARD_EXPORT: frozenset({Role.CAE_ANALYST}),
}


def permissions_for_product_assignment(
    assignment: ProductAccessAssignment,
) -> frozenset[Permission]:
    permissions = set(_PRODUCT_BASE_PERMISSIONS)
    if assignment.product_role is ProductRole.ADMINISTRATOR:
        permissions.update({Permission.IDENTITY_MANAGE, Permission.PROJECT_MANAGE})
    for grant in assignment.feature_grants:
        permissions.update(PRODUCT_FEATURE_PERMISSIONS[grant])
    return frozenset(permissions)


def evidence_roles_for_product_assignment(
    assignment: ProductAccessAssignment,
) -> frozenset[Role]:
    roles = {Role.CONSUMER}
    if assignment.product_role is ProductRole.ADMINISTRATOR:
        roles.add(Role.ORG_ADMIN)
    for grant in assignment.feature_grants:
        roles.update(_FEATURE_EVIDENCE_ROLES[grant])
    return frozenset(roles)


def _legacy_feature_grants(roles: set[Role]) -> set[FeatureGrant]:
    permissions: set[Permission] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS[role])
    return {
        grant
        for grant, required in PRODUCT_FEATURE_PERMISSIONS.items()
        if required.issubset(permissions)
    }


_MODIFYING_OPERATIONS = frozenset(
    {
        "activate",
        "control",
        "decide",
        "execute",
        "manage",
        "publish",
        "request",
        "schema.apply",
        "submit",
        "write",
    }
)
_DATABASE_PERMISSION_DEPENDENCIES: Mapping[Permission, frozenset[Permission]] = {
    Permission.UNITS_WRITE: frozenset({Permission.UNITS_READ}),
    # Published Materials is one server-scoped projection. Its currentness query
    # re-checks exact heads, while curve preview resolves verified Artifact bytes and
    # already-recorded Dataset/Statistics ownership in the same RLS transaction.
    # Carry these read capabilities internally; this does not authorize their APIs.
    Permission.CATALOG_READ: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.PROCESSING_READ,
            Permission.STATISTICS_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
    ),
    # Review evidence is resolved server-side from the immutable subject revision
    # before the governance row is inserted.  The resolver supports one closed set
    # of subject domains, so the review command carries their read capabilities into
    # the transaction-local RLS settings while retaining the normal review scope.
    Permission.REVIEW_REQUEST: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
        }
    ),
    # Catalog registration reads a verified immutable source Artifact and may materialize
    # normalized curve Artifacts before it creates typed Record revisions. These are internal
    # command capabilities only; the public Artifact endpoints continue to require their own
    # explicit artifact permission.
    Permission.CATALOG_WRITE: frozenset(
        {Permission.ARTIFACT_READ, Permission.ARTIFACT_WRITE, Permission.UNITS_READ}
    ),
    Permission.CATALOG_SCHEMA_APPLY: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.UNITS_READ,
        }
    ),
    # Reference import detection reads the verified immutable raw artifact before
    # it records a human-approved mapping revision.  This remains a transaction
    # capability only; the public Artifact endpoint still requires artifact.read.
    Permission.TESTING_WRITE: frozenset({Permission.CATALOG_READ, Permission.ARTIFACT_READ}),
    # A Dataset is an immutable interpretation of an Artifact and its Material State
    # lineage is resolved through the pinned Test Run and Specimen. Reading a curve
    # therefore needs row-visible Artifact and Testing access. These remain
    # transaction capabilities; their public endpoints still authorize independently.
    Permission.DATASET_READ: frozenset(
        {Permission.ARTIFACT_READ, Permission.TESTING_READ, Permission.UNITS_READ}
    ),
    Permission.DATASET_WRITE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.CATALOG_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
    ),
    # Processing previews reconstruct their typed result from immutable output Artifacts and
    # pinned Dataset/Test evidence. Exact DMA output read-back also validates the immutable
    # provenance graph before returning the typed result. These are transaction-local read
    # capabilities only; they do not authorize the public Dataset, Artifact, Testing, or
    # Provenance endpoints.
    Permission.PROCESSING_READ: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.DATASET_READ,
            Permission.PROVENANCE_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
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
            Permission.UNITS_READ,
        }
    ),
    # A Statistics-owned result preview reads its own typed immutable curve Artifact. This is an
    # internal database capability only; it does not authorize the public Artifact endpoint.
    Permission.STATISTICS_READ: frozenset({Permission.ARTIFACT_READ}),
    # A committed Statistical Run reads pinned Dataset Artifacts and writes one immutable typed
    # curve-result Artifact. These are transaction-local capabilities, not public Artifact
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
    Permission.MODELING_WRITE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.CATALOG_READ,
            # Neutral Material promotion atomically registers its exact Catalog
            # owner in the same transaction.  This is transaction-local
            # capability closure; the public Catalog write endpoint still
            # requires an explicit top-level CATALOG_WRITE decision.
            Permission.CATALOG_WRITE,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            # A model promotion reads one exact immutable Processing Output revision. This is
            # transaction-local capability closure and does not grant the processing HTTP API.
            Permission.PROCESSING_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
    ),
    Permission.CALIBRATION_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.CATALOG_READ,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            # The calibration application resolves one fixed active package
            # while creating the immutable Job Spec. This is transaction-local
            # dependency closure; it does not grant the caller the Plugin API.
            Permission.PLUGIN_READ,
            Permission.STATISTICS_READ,
            Permission.TESTING_READ,
        }
    ),
    # The exporting projection reads exact immutable sources across bounded modules. These
    # remain transaction-local database capabilities; they do not authorize the caller to use
    # the Catalog, Dataset, Testing, Modeling, or Artifact HTTP APIs directly.
    Permission.EXPORT_READ: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.CATALOG_READ,
            Permission.DATASET_READ,
            Permission.MODELING_READ,
            Permission.PROCESSING_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
    ),
    Permission.EXPORT_EXECUTE: frozenset(
        {
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            # Target delivery records the immutable solver-card relationship in Catalog's
            # identity and revision binding tables.  These are transaction-local capabilities
            # for the already-authorized export command; they do not grant Catalog HTTP writes.
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.DATASET_READ,
            Permission.EXPORT_READ,
            Permission.MODELING_READ,
            Permission.PROCESSING_READ,
            Permission.TESTING_READ,
            Permission.UNITS_READ,
        }
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
            Permission.STATISTICS_READ,
            Permission.TESTING_READ,
            Permission.VALIDATION_READ,
        }
    ),
    # Approval projects exact subject evidence and writes the Materials publication
    # marker in the same transaction.  Carry every closed subject-domain read plus
    # Catalog write into transaction-local RLS; public endpoints still authorize
    # each operation independently.
    Permission.REVIEW_DECIDE: frozenset(
        {
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.DATASET_READ,
            Permission.EXPORT_READ,
            Permission.MODELING_READ,
            Permission.PROVENANCE_READ,
            Permission.REVIEW_READ,
        }
    ),
    Permission.RELEASE_PUBLISH: frozenset(
        {
            Permission.REVIEW_READ,
            Permission.RELEASE_READ,
            Permission.PROVENANCE_READ,
            Permission.MODELING_READ,
            Permission.EXPORT_READ,
            Permission.VALIDATION_READ,
        }
    ),
    Permission.PLUGIN_SUBMIT: frozenset({Permission.PLUGIN_READ}),
    Permission.PLUGIN_ACTIVATE: frozenset({Permission.PLUGIN_READ}),
    Permission.JOB_SUBMIT: frozenset({Permission.JOB_READ}),
    Permission.JOB_CONTROL: frozenset({Permission.JOB_READ}),
    # The operational runner is authorized through the generic Job command only.  These
    # capabilities are transaction-local closure for reading exact inputs, committing
    # immutable output Artifacts, and saving the calibration projection; they do not add
    # ``calibration.execute`` to the public Job Runner role.
    Permission.JOB_EXECUTE: frozenset(
        {
            Permission.JOB_READ,
            Permission.ARTIFACT_READ,
            Permission.ARTIFACT_WRITE,
            Permission.CALIBRATION_EXECUTE,
            # Calibration Run reconciliation reads the modeling-owned projection before
            # committing its immutable execution ledger.  This is transaction-local
            # closure for JOB_EXECUTE, not a public modeling permission grant.
            Permission.MODELING_READ,
        }
    ),
}

# These commands may invoke a T-13 fail-closed provenance hook in the owning domain
# transaction. ``provenance.write`` is deliberately not a public role permission; it is a
# minimum DB capability derived only after one of the owning commands was authorized.
_PROVENANCE_WRITING_COMMANDS = frozenset(
    {
        Permission.TESTING_WRITE,
        Permission.CATALOG_WRITE,
        Permission.CATALOG_SCHEMA_APPLY,
        Permission.UNITS_WRITE,
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

# T-16 outbox rows are inserted only by an already-authorized owning command, including the
# transaction-local JOB_EXECUTE closure used when a worker commits an immutable output. Dispatch
# and inbox capabilities remain exclusive to the project-scoped operational Job Runner.
_EVENT_PUBLISHING_COMMANDS = frozenset(
    {
        Permission.CATALOG_WRITE,
        Permission.CATALOG_SCHEMA_APPLY,
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
        Permission.JOB_EXECUTE,
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
        product_assignments: ProductAccessAssignmentReader | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._bindings = bindings
        self._product_assignments = product_assignments
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
        product_applicable = (
            self._product_assignments.find_applicable(context, observed_at)
            if self._product_assignments is not None
            else ()
        )
        product_granting = tuple(
            assignment
            for assignment in product_applicable
            if assignment.applies_to(context, observed_at)
            and permission in permissions_for_product_assignment(assignment)
        )
        if not granting and not product_granting:
            raise AuthorizationDenied("permission_denied")

        maximum = max(
            (
                *(binding.max_classification for binding in granting),
                *(assignment.max_classification for assignment in product_granting),
            ),
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
            roles=tuple(
                sorted(
                    {
                        *(binding.role for binding in granting),
                        *(
                            role
                            for assignment in product_granting
                            for role in evidence_roles_for_product_assignment(assignment)
                        ),
                    },
                    key=str,
                )
            ),
            database_permissions=database_permissions_for(permission),
            max_classification=maximum,
            allow_export_controlled=(
                any(binding.allow_export_controlled for binding in granting)
                or any(assignment.allow_export_controlled for assignment in product_granting)
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
            decided_at=observed_at,
        )

    def effective_product_access(self, context: SecurityContext) -> ProductAccessSummary:
        """Project legacy bindings and first-class assignments into the simple UI vocabulary."""

        observed_at = self._clock()
        legacy = tuple(
            item
            for item in self._bindings.find_applicable(context, observed_at)
            if item.applies_to(context, observed_at)
        )
        product = (
            tuple(
                item
                for item in self._product_assignments.find_applicable(context, observed_at)
                if item.applies_to(context, observed_at)
            )
            if self._product_assignments is not None
            else ()
        )
        legacy_roles = {item.role for item in legacy}
        grants = _legacy_feature_grants(legacy_roles)
        grants.update(grant for item in product for grant in item.feature_grants)
        # Administrator v2 assignments are deliberately projected to their
        # corrected four-grant preset.  In particular, a migrated v1 row must
        # not leak the historical model-approval grant into the product summary.
        has_product_administrator = any(
            item.product_role is ProductRole.ADMINISTRATOR for item in product
        )
        if has_product_administrator:
            grants = set(product_role_preset(ProductRole.ADMINISTRATOR))
        administrator = any(
            item.product_role is ProductRole.ADMINISTRATOR for item in product
        ) or bool(legacy_roles & {Role.ORG_ADMIN, Role.PLATFORM_ADMIN})
        reviewer = any(item.product_role is ProductRole.REVIEWER for item in product)
        return ProductAccessSummary(
            product_role=(
                ProductRole.ADMINISTRATOR
                if administrator
                else ProductRole.REVIEWER
                if reviewer
                else ProductRole.USER
            ),
            feature_grants=tuple(sorted(grants, key=str)),
            legacy_compatible=bool(legacy),
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


@dataclass(frozen=True, slots=True)
class GrantProductAccess:
    organization_id: UUID
    project_id: UUID | None
    subject: BindingSubject
    product_role: ProductRole
    feature_grants: tuple[FeatureGrant, ...]
    max_classification: DataClassification
    allow_export_controlled: bool
    grant_reason: str
    valid_from: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        _reason("grant_reason", self.grant_reason)
        if tuple(sorted(set(self.feature_grants), key=str)) != self.feature_grants:
            raise ValueError("feature_grants must be sorted and unique")


@dataclass(frozen=True, slots=True)
class RevokeProductAccess:
    assignment_id: UUID
    reason: str

    def __post_init__(self) -> None:
        if self.assignment_id.int == 0:
            raise ValueError("assignment_id must be non-zero")
        _reason("reason", self.reason)


class ProductAccessAdministrationService:
    """Manage the simple product model while preserving T-04 authorization and RLS."""

    def __init__(
        self,
        *,
        authorization: AuthorizationService,
        repository: ProductAccessAssignmentRepository,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._authorization = authorization
        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def effective(self, context: SecurityContext) -> ProductAccessSummary:
        return self._authorization.effective_product_access(context)

    def list_assignments(self, context: SecurityContext) -> tuple[ProductAccessAssignment, ...]:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        return self._repository.list_assignments(context=context, decision=decision)

    def grant(
        self, context: SecurityContext, command: GrantProductAccess
    ) -> ProductAccessAssignment:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        if command.organization_id != context.organization_id or command.project_id not in {
            None,
            context.project_id,
        }:
            raise AuthorizationDenied("product_access_scope_mismatch")
        created_at = self._clock()
        valid_from = command.valid_from or created_at
        if valid_from < created_at:
            raise ValueError("valid_from cannot precede grant creation time")
        assignment = ProductAccessAssignment(
            id=self._id_factory(),
            organization_id=command.organization_id,
            project_id=command.project_id,
            subject=command.subject,
            product_role=command.product_role,
            # New grants are task presets. Existing append-only User rows with custom
            # grants remain readable/effective through the repository projection.
            feature_grants=product_role_preset(command.product_role),
            max_classification=command.max_classification,
            allow_export_controlled=command.allow_export_controlled,
            valid_from=valid_from,
            expires_at=command.expires_at,
        )
        return self._repository.append_assignment(
            context=context,
            decision=decision,
            assignment=assignment,
            created_at=created_at,
            grant_reason=command.grant_reason,
        )

    def revoke(self, context: SecurityContext, command: RevokeProductAccess) -> None:
        decision = self._authorization.authorize(context, Permission.IDENTITY_MANAGE)
        self._repository.revoke_assignment(
            context=context,
            decision=decision,
            assignment_id=command.assignment_id,
            revoked_at=self._clock(),
            reason=command.reason,
        )
