from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.application.authorization import (
    ROLE_PERMISSIONS,
    AuthorizationService,
    GrantRoleBinding,
    RevokeRoleBinding,
    RoleBindingAdministrationService,
    database_permissions_for,
    permissions_for_product_assignment,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    AuthorizationDenied,
    BindingSubject,
    DataClassification,
    FeatureGrant,
    Permission,
    ProductAccessAssignment,
    ProductRole,
    Role,
    RoleBinding,
    product_role_preset,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)

NOW = datetime(2026, 7, 11, 5, 0, tzinfo=UTC)
ORG = UUID("60000000-0000-4000-8000-000000000001")
PROJECT = UUID("60000000-0000-4000-8000-000000000002")
PRINCIPAL = UUID("60000000-0000-4000-8000-000000000003")
ISSUER = "https://test-idp.invalid"
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def _context(
    *,
    organization_id: UUID = ORG,
    project_id: UUID = PROJECT,
    groups: tuple[str, ...] = ("project-modelers",),
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(PRINCIPAL, PrincipalType.USER, "Policy User", True),
        organization_id=organization_id,
        project_id=project_id,
        issuer=ISSUER,
        subject="policy-user",
        token_id=str(uuid4()),
        groups=groups,
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _binding(
    role: Role,
    *,
    subject: BindingSubject | None = None,
    organization_id: UUID = ORG,
    project_id: UUID | None = PROJECT,
    maximum: DataClassification = DataClassification.INTERNAL,
    export: bool = False,
    valid_from: datetime = NOW - timedelta(days=1),
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> RoleBinding:
    return RoleBinding(
        id=uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        subject=subject or BindingSubject.for_principal(PRINCIPAL),
        role=role,
        max_classification=maximum,
        allow_export_controlled=export,
        valid_from=valid_from,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


class _Bindings:
    def __init__(self, *bindings: RoleBinding) -> None:
        self.bindings = bindings

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        del context, observed_at
        return self.bindings


class _ProductAssignments:
    def __init__(self, *assignments: ProductAccessAssignment) -> None:
        self.assignments = assignments

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[ProductAccessAssignment, ...]:
        del context, observed_at
        return self.assignments


def _product_assignment(
    role: ProductRole,
    *grants: FeatureGrant,
    subject: BindingSubject | None = None,
) -> ProductAccessAssignment:
    effective_grants = tuple(sorted(set(grants), key=str))
    if role in {ProductRole.ADMINISTRATOR, ProductRole.REVIEWER}:
        effective_grants = product_role_preset(role)
    return ProductAccessAssignment(
        id=uuid4(),
        organization_id=ORG,
        project_id=PROJECT,
        subject=subject or BindingSubject.for_principal(PRINCIPAL),
        product_role=role,
        feature_grants=effective_grants,
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        valid_from=NOW - timedelta(days=1),
    )


def _service(*bindings: RoleBinding) -> AuthorizationService:
    return AuthorizationService(bindings=_Bindings(*bindings), clock=lambda: NOW)


def test_user_feature_grants_authorize_only_the_selected_product_capability() -> None:
    assignment = _product_assignment(ProductRole.USER, FeatureGrant.SOLVER_CARD_EXPORT)
    service = AuthorizationService(
        bindings=_Bindings(),
        product_assignments=_ProductAssignments(assignment),
        clock=lambda: NOW,
    )

    decision = service.authorize(_context(), Permission.EXPORT_EXECUTE)

    assert Role.CAE_ANALYST in decision.roles
    assert Permission.EXPORT_EXECUTE in permissions_for_product_assignment(assignment)
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        service.authorize(_context(), Permission.CALIBRATION_EXECUTE)


def test_administrator_has_corrected_features_and_identity_management() -> None:
    assignment = _product_assignment(ProductRole.ADMINISTRATOR)
    service = AuthorizationService(
        bindings=_Bindings(),
        product_assignments=_ProductAssignments(assignment),
        clock=lambda: NOW,
    )

    summary = service.effective_product_access(_context())
    decision = service.authorize(_context(), Permission.IDENTITY_MANAGE)
    schema_apply = service.authorize(_context(), Permission.CATALOG_SCHEMA_APPLY)

    assert summary.product_role is ProductRole.ADMINISTRATOR
    assert summary.feature_grants == product_role_preset(ProductRole.ADMINISTRATOR)
    assert not summary.legacy_compatible
    assert Role.ORG_ADMIN in decision.roles
    assert Role.DATA_STEWARD in schema_apply.roles
    assert {
        Permission.ARTIFACT_READ.value,
        Permission.CATALOG_READ.value,
        Permission.CATALOG_WRITE.value,
        Permission.CATALOG_SCHEMA_APPLY.value,
        "provenance.write",
        "audit.append",
        "events.publish",
    }.issubset(schema_apply.database_permissions)
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        service.authorize(_context(), Permission.REVIEW_DECIDE)


def test_reviewer_has_the_fixed_review_preset_without_access_administration() -> None:
    assignment = _product_assignment(ProductRole.REVIEWER)
    service = AuthorizationService(
        bindings=_Bindings(),
        product_assignments=_ProductAssignments(assignment),
        clock=lambda: NOW,
    )

    summary = service.effective_product_access(_context())
    review = service.authorize(_context(), Permission.REVIEW_DECIDE)
    export = service.authorize(_context(), Permission.EXPORT_EXECUTE)

    assert summary.product_role is ProductRole.REVIEWER
    assert summary.feature_grants == product_role_preset(ProductRole.REVIEWER)
    assert Role.DOMAIN_REVIEWER in review.roles
    assert Role.CAE_ANALYST in export.roles
    assert Permission.CATALOG_READ.value in export.database_permissions
    assert Permission.CATALOG_WRITE.value in export.database_permissions
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        service.authorize(_context(), Permission.IDENTITY_MANAGE)
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        service.authorize(_context(), Permission.CATALOG_WRITE)
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        service.authorize(_context(), Permission.CATALOG_SCHEMA_APPLY)


def test_effective_product_role_precedence_does_not_promote_legacy_features() -> None:
    legacy_model_approval = _product_assignment(ProductRole.USER, FeatureGrant.MODEL_APPROVAL)
    reviewer = _product_assignment(ProductRole.REVIEWER)
    administrator = _product_assignment(ProductRole.ADMINISTRATOR)

    assert (
        AuthorizationService(
            bindings=_Bindings(),
            product_assignments=_ProductAssignments(legacy_model_approval),
            clock=lambda: NOW,
        )
        .effective_product_access(_context())
        .product_role
        is ProductRole.USER
    )
    assert (
        AuthorizationService(
            bindings=_Bindings(),
            product_assignments=_ProductAssignments(reviewer),
            clock=lambda: NOW,
        )
        .effective_product_access(_context())
        .product_role
        is ProductRole.REVIEWER
    )
    assert (
        AuthorizationService(
            bindings=_Bindings(),
            product_assignments=_ProductAssignments(reviewer, administrator),
            clock=lambda: NOW,
        )
        .effective_product_access(_context())
        .product_role
        is ProductRole.ADMINISTRATOR
    )


def test_reviewer_assignment_cannot_weaken_or_expand_its_preset() -> None:
    with pytest.raises(ValueError, match="fixed product preset"):
        ProductAccessAssignment(
            id=uuid4(),
            organization_id=ORG,
            project_id=PROJECT,
            subject=BindingSubject.for_principal(PRINCIPAL),
            product_role=ProductRole.REVIEWER,
            feature_grants=(FeatureGrant.MODEL_APPROVAL,),
            max_classification=DataClassification.RESTRICTED,
            allow_export_controlled=False,
            valid_from=NOW - timedelta(days=1),
        )


def test_legacy_role_bindings_project_to_the_simple_product_vocabulary() -> None:
    service = _service(
        _binding(Role.TEST_ENGINEER),
        _binding(Role.DATA_STEWARD),
        _binding(Role.STATISTICAL_ANALYST),
        _binding(Role.MATERIAL_MODELER),
        _binding(Role.CAE_ANALYST),
    )

    summary = service.effective_product_access(_context())

    assert summary.product_role is ProductRole.USER
    assert FeatureGrant.CATALOG_EDIT in summary.feature_grants
    assert FeatureGrant.PROCESSING_CALIBRATION in summary.feature_grants
    assert FeatureGrant.SOLVER_CARD_EXPORT in summary.feature_grants
    assert summary.legacy_compatible


@pytest.mark.parametrize(
    ("role", "permission"),
    [
        (Role.ORG_ADMIN, Permission.IDENTITY_MANAGE),
        (Role.TEST_ENGINEER, Permission.TESTING_WRITE),
        (Role.DATA_STEWARD, Permission.DATASET_WRITE),
        (Role.DATA_STEWARD, Permission.CATALOG_SCHEMA_APPLY),
        (Role.STATISTICAL_ANALYST, Permission.STATISTICS_EXECUTE),
        (Role.MATERIAL_MODELER, Permission.CALIBRATION_EXECUTE),
        (Role.CAE_ANALYST, Permission.VALIDATION_EXECUTE),
        (Role.DOMAIN_REVIEWER, Permission.REVIEW_DECIDE),
        (Role.RELEASE_APPROVER, Permission.RELEASE_PUBLISH),
        (Role.PLUGIN_MAINTAINER, Permission.PLUGIN_SUBMIT),
        (Role.JOB_RUNNER, Permission.JOB_EXECUTE),
        (Role.AUDITOR, Permission.AUDIT_READ),
    ],
)
def test_conservative_mvp_role_matrix_grants_documented_actions(
    role: Role, permission: Permission
) -> None:
    decision = _service(_binding(role)).authorize(_context(), permission)

    assert decision.roles == (role,)
    assert permission.value in decision.database_permissions


def test_admin_roles_do_not_implicitly_receive_business_or_approval_access() -> None:
    assert Permission.TESTING_READ not in ROLE_PERMISSIONS[Role.PLATFORM_ADMIN]
    assert Permission.RELEASE_PUBLISH not in ROLE_PERMISSIONS[Role.PLATFORM_ADMIN]
    assert Permission.TESTING_READ not in ROLE_PERMISSIONS[Role.ORG_ADMIN]
    assert Permission.RELEASE_PUBLISH not in ROLE_PERMISSIONS[Role.PROJECT_ADMIN]
    assert Permission.PLUGIN_ACTIVATE not in ROLE_PERMISSIONS[Role.PLUGIN_MAINTAINER]
    assert ROLE_PERMISSIONS[Role.JOB_RUNNER] == {
        Permission.ARTIFACT_READ,
        Permission.ARTIFACT_WRITE,
        Permission.EXPORT_EXECUTE,
        Permission.PLUGIN_READ,
        Permission.JOB_READ,
        Permission.JOB_EXECUTE,
    }
    assert Permission.PLUGIN_ACTIVATE not in ROLE_PERMISSIONS[Role.JOB_RUNNER]
    assert Permission.PLUGIN_SUBMIT not in ROLE_PERMISSIONS[Role.JOB_RUNNER]


def test_modeling_write_closes_catalog_binding_transaction_capability() -> None:
    permissions = set(database_permissions_for(Permission.MODELING_WRITE))

    assert Permission.CATALOG_WRITE.value in permissions

    # This is a database capability closure only.  Public endpoint authorization
    # continues to use the caller's explicit top-level permission decision.


def test_each_role_action_also_grants_its_typed_database_dependencies() -> None:
    for permissions in ROLE_PERMISSIONS.values():
        for action in permissions:
            typed_dependencies = {
                Permission(value)
                for value in database_permissions_for(action)
                if value
                not in {
                    "governance.read",
                    "governance.write",
                    "provenance.read",
                    "provenance.write",
                    "events.publish",
                    "events.dispatch",
                    "events.consume",
                    "audit.append",
                }
            }
                # Closed subject resolution, target delivery, and the published Materials
                # projection carry bounded cross-module capabilities only in the command
                # transaction. They intentionally are not public grants on the reviewer or
                # CAE_ANALYST roles.
            typed_dependencies.difference_update(
                    {
                        Permission.ARTIFACT_READ,
                        Permission.CATALOG_READ,
                    Permission.CATALOG_WRITE,
                        Permission.CALIBRATION_EXECUTE,
                    Permission.DATASET_READ,
                    Permission.EXPORT_READ,
                    Permission.MODELING_READ,
                        Permission.PROCESSING_READ,
                        Permission.STATISTICS_READ,
                        Permission.TESTING_READ,
                        Permission.UNITS_READ,
                }
            )
            assert typed_dependencies.issubset(permissions)


def test_catalog_write_carries_internal_curve_artifact_materialization_capability() -> None:
    database_permissions = set(database_permissions_for(Permission.CATALOG_WRITE))

    assert {
        Permission.CATALOG_WRITE.value,
        Permission.ARTIFACT_READ.value,
        Permission.ARTIFACT_WRITE.value,
        Permission.UNITS_READ.value,
    }.issubset(database_permissions)

    decision = _service(_binding(Role.DATA_STEWARD)).authorize(
        _context(), Permission.CATALOG_WRITE
    )
    assert decision.permission is Permission.CATALOG_WRITE
    assert {
        Permission.ARTIFACT_READ.value,
        Permission.ARTIFACT_WRITE.value,
        Permission.UNITS_READ.value,
        "events.publish",
    }.issubset(decision.database_permissions)


def test_no_binding_or_wrong_tenant_project_subject_and_group_issuer_are_denied() -> None:
    context = _context()
    wrong_bindings = (
        _binding(Role.DATA_STEWARD, organization_id=uuid4()),
        _binding(Role.DATA_STEWARD, project_id=uuid4()),
        _binding(
            Role.DATA_STEWARD,
            subject=BindingSubject.for_principal(uuid4()),
        ),
        _binding(
            Role.DATA_STEWARD,
            subject=BindingSubject.for_group("https://other-idp.invalid", "project-modelers"),
        ),
    )

    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        _service(*wrong_bindings).authorize(context, Permission.DATASET_WRITE)


def test_exact_issuer_group_and_org_wide_binding_apply_to_selected_project() -> None:
    binding = _binding(
        Role.MATERIAL_MODELER,
        project_id=None,
        subject=BindingSubject.for_group(ISSUER, "project-modelers"),
        maximum=DataClassification.CONFIDENTIAL,
    )

    decision = _service(binding).authorize(_context(), Permission.MODELING_WRITE)

    assert decision.max_classification is DataClassification.CONFIDENTIAL
    assert decision.allows(ORG, PROJECT, DataClassification.CONFIDENTIAL)
    assert not decision.allows(ORG, PROJECT, DataClassification.RESTRICTED)


def test_action_and_clearance_are_not_combined_across_unrelated_bindings() -> None:
    writer = _binding(
        Role.TEST_ENGINEER,
        maximum=DataClassification.INTERNAL,
        export=False,
    )
    unrelated_clearance = _binding(
        Role.CONSUMER,
        maximum=DataClassification.RESTRICTED,
        export=True,
    )

    decision = _service(writer, unrelated_clearance).authorize(_context(), Permission.TESTING_WRITE)

    assert decision.roles == (Role.TEST_ENGINEER,)
    assert decision.max_classification is DataClassification.INTERNAL
    assert not decision.allow_export_controlled
    assert not decision.allows(ORG, PROJECT, DataClassification.CONFIDENTIAL)
    assert not decision.allows(ORG, PROJECT, DataClassification.EXPORT_CONTROLLED)


def test_explicit_export_clearance_is_independent_of_standard_rank() -> None:
    binding = _binding(
        Role.CAE_ANALYST,
        maximum=DataClassification.CONFIDENTIAL,
        export=True,
    )

    decision = _service(binding).authorize(_context(), Permission.VALIDATION_READ)

    assert decision.allows(ORG, PROJECT, DataClassification.CONFIDENTIAL)
    assert not decision.allows(ORG, PROJECT, DataClassification.RESTRICTED)
    assert decision.allows(ORG, PROJECT, DataClassification.EXPORT_CONTROLLED)


def test_expired_and_revoked_bindings_are_denied() -> None:
    expired = _binding(Role.DATA_STEWARD, expires_at=NOW)
    revoked = _binding(Role.DATA_STEWARD, revoked_at=NOW - timedelta(hours=1))

    with pytest.raises(AuthorizationDenied):
        _service(expired, revoked).authorize(_context(), Permission.DATASET_WRITE)


def test_write_decision_expands_only_required_read_and_governance_permissions() -> None:
    decision = _service(_binding(Role.DATA_STEWARD)).authorize(_context(), Permission.DATASET_WRITE)

    assert decision.database_permissions == (
        "artifact.read",
        "artifact.write",
        "audit.append",
        "catalog.read",
        "dataset.read",
        "dataset.write",
        "events.publish",
        "governance.read",
        "governance.write",
        "provenance.read",
        "provenance.write",
        "testing.read",
        "units.read",
    )


def test_review_request_decision_can_resolve_each_registered_subject_domain() -> None:
    decision = _service(_binding(Role.MATERIAL_MODELER)).authorize(
        _context(), Permission.REVIEW_REQUEST
    )

    assert {
        "catalog.read",
        "dataset.read",
        "export.read",
        "modeling.read",
    }.issubset(decision.database_permissions)


def test_catalog_read_decision_can_recheck_published_cross_domain_heads() -> None:
    decision = _service(_binding(Role.DOMAIN_REVIEWER)).authorize(
        _context(), Permission.CATALOG_READ
    )

    assert {
        "catalog.read",
        "dataset.read",
        "export.read",
        "modeling.read",
        "processing.read",
        "testing.read",
    }.issubset(decision.database_permissions)


def test_cross_module_execution_decision_contains_only_explicit_dependencies() -> None:
    decision = _service(_binding(Role.CAE_ANALYST)).authorize(
        _context(), Permission.VALIDATION_EXECUTE
    )

    assert decision.database_permissions == (
        "artifact.read",
        "artifact.write",
        "audit.append",
        "dataset.read",
        "events.publish",
        "export.read",
        "governance.read",
        "governance.write",
        "modeling.read",
        "provenance.read",
        "provenance.write",
        "statistics.read",
        "testing.read",
        "validation.execute",
        "validation.read",
    )


def test_export_read_decision_can_resolve_exact_processing_sources() -> None:
    decision = _service(_binding(Role.CAE_ANALYST)).authorize(_context(), Permission.EXPORT_READ)

    assert "processing.read" in decision.database_permissions
    assert "processing.write" not in decision.database_permissions


def test_job_runner_receives_dispatch_consumer_and_outbox_capabilities() -> None:
    decision = _service(_binding(Role.JOB_RUNNER)).authorize(_context(), Permission.JOB_EXECUTE)

    assert {
        "events.consume",
        "events.dispatch",
        "events.publish",
    }.issubset(decision.database_permissions)
    assert {
        Permission.ARTIFACT_READ.value,
        Permission.ARTIFACT_WRITE.value,
        Permission.CALIBRATION_EXECUTE.value,
        Permission.MODELING_READ.value,
    }.issubset(decision.database_permissions)
    assert "audit.append" in decision.database_permissions
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        _service(_binding(Role.JOB_RUNNER)).authorize(
            _context(), Permission.CALIBRATION_EXECUTE
        )
    assert Permission.CATALOG_WRITE not in ROLE_PERMISSIONS[Role.JOB_RUNNER]
    assert Permission.REVIEW_DECIDE not in ROLE_PERMISSIONS[Role.JOB_RUNNER]
    assert Permission.PLUGIN_ACTIVATE not in ROLE_PERMISSIONS[Role.JOB_RUNNER]


def test_project_scoped_job_runner_can_execute_the_configured_export_queue() -> None:
    decision = _service(_binding(Role.JOB_RUNNER)).authorize(
        _context(), Permission.EXPORT_EXECUTE
    )

    assert decision.roles == (Role.JOB_RUNNER,)
    assert Permission.EXPORT_EXECUTE.value in decision.database_permissions
    assert {
        Permission.ARTIFACT_READ.value,
        Permission.ARTIFACT_WRITE.value,
        Permission.CATALOG_WRITE.value,
        Permission.EXPORT_READ.value,
        Permission.MODELING_READ.value,
        Permission.PROCESSING_READ.value,
        Permission.TESTING_READ.value,
        Permission.UNITS_READ.value,
    }.issubset(decision.database_permissions)
    assert Permission.CALIBRATION_EXECUTE.value not in ROLE_PERMISSIONS[Role.JOB_RUNNER]


class _AdministrationRepository:
    def __init__(self) -> None:
        self.appended: RoleBinding | None = None
        self.revoked: UUID | None = None

    def append(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: RoleBinding,
        created_at: datetime,
        grant_reason: str,
    ) -> RoleBinding:
        assert context.principal.id == decision.principal_id
        assert created_at == NOW
        assert grant_reason == "approved project assignment"
        self.appended = binding
        return binding

    def revoke(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        assert context.principal.id == decision.principal_id
        assert revoked_at == NOW
        assert reason == "assignment ended"
        self.revoked = binding_id


def test_org_admin_can_append_and_revoke_scoped_immutable_bindings() -> None:
    repository = _AdministrationRepository()
    authorization = _service(_binding(Role.ORG_ADMIN, project_id=None))
    fixed_id = UUID("60000000-0000-4000-8000-000000000099")
    administration = RoleBindingAdministrationService(
        authorization=authorization,
        repository=repository,
        id_factory=lambda: fixed_id,
        clock=lambda: NOW,
    )
    context = _context()

    binding = administration.grant(
        context,
        GrantRoleBinding(
            organization_id=ORG,
            project_id=PROJECT,
            subject=BindingSubject.for_group(ISSUER, "new-reviewers"),
            role=Role.DOMAIN_REVIEWER,
            max_classification=DataClassification.RESTRICTED,
            allow_export_controlled=False,
            grant_reason="approved project assignment",
        ),
    )
    administration.revoke(
        context,
        RevokeRoleBinding(binding_id=fixed_id, reason="assignment ended"),
    )

    assert binding.id == fixed_id
    assert repository.appended == binding
    assert repository.revoked == fixed_id


def test_role_administration_rejects_cross_context_scope_and_non_admin_role() -> None:
    context = _context()
    command = GrantRoleBinding(
        organization_id=ORG,
        project_id=uuid4(),
        subject=BindingSubject.for_principal(uuid4()),
        role=Role.CONSUMER,
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        grant_reason="cross project attempt",
    )
    repository = _AdministrationRepository()
    administration = RoleBindingAdministrationService(
        authorization=_service(_binding(Role.ORG_ADMIN, project_id=None)),
        repository=repository,
        clock=lambda: NOW,
    )

    with pytest.raises(AuthorizationDenied, match="binding_scope_mismatch"):
        administration.grant(context, command)

    with pytest.raises(AuthorizationDenied, match="platform_role_operator_only"):
        administration.grant(
            context,
            GrantRoleBinding(
                organization_id=ORG,
                project_id=None,
                subject=BindingSubject.for_principal(uuid4()),
                role=Role.PLATFORM_ADMIN,
                max_classification=DataClassification.INTERNAL,
                allow_export_controlled=False,
                grant_reason="privilege escalation attempt",
            ),
        )

    with pytest.raises(AuthorizationDenied, match="platform_role_operator_only"):
        administration.grant(
            context,
            GrantRoleBinding(
                organization_id=ORG,
                project_id=PROJECT,
                subject=BindingSubject.for_principal(uuid4()),
                role=Role.JOB_RUNNER,
                max_classification=DataClassification.INTERNAL,
                allow_export_controlled=False,
                grant_reason="runner role must be operator provisioned",
            ),
        )

    non_admin = RoleBindingAdministrationService(
        authorization=_service(_binding(Role.PLATFORM_ADMIN, project_id=None)),
        repository=repository,
        clock=lambda: NOW,
    )
    with pytest.raises(AuthorizationDenied, match="permission_denied"):
        non_admin.grant(context, command)
