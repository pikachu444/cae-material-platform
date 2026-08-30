from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.identity_access.application.authorization import (
    database_permissions_for,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.plugins.adapters.contracts.jsonschema import (
    JsonSchemaPluginContractValidator,
)
from cmp.modules.plugins.application.registry import (
    ActivatePackage,
    PackageRegistrationResult,
    PluginRegistryService,
    RegisterPackage,
    RegisterSchema,
)
from cmp.modules.plugins.domain.registry import (
    ArtifactReference,
    ImmutablePluginManifest,
    InvalidManifest,
    InvalidPackageState,
    PackageAccessDenied,
    PackageRecord,
    PackageState,
    PackageStateEventRecord,
    SchemaDocument,
    SchemaRole,
    assert_package_transition,
)
from cmp.shared.domain.revisions import content_sha256

PROJECT_ROOT = Path(__file__).parents[3]
NOW = datetime(2026, 7, 11, 9, 0, tzinfo=UTC)
ORG = UUID("85000000-0000-4000-8000-000000000001")
PROJECT = UUID("85000000-0000-4000-8000-000000000002")
ACTOR = UUID("85000000-0000-4000-8000-000000000003")
TRACE = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def _manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (PROJECT_ROOT / "contracts/examples/positive/plugin-manifest.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:cmp:plugin:reference-processor:config:1.0.0",
        "type": "object",
        "additionalProperties": False,
    }


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Plugin Maintainer", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject="plugin-maintainer",
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext, permission: Permission = Permission.PLUGIN_SUBMIT
) -> AuthorizationDecision:
    role = (
        Role.PLUGIN_MAINTAINER
        if permission is Permission.PLUGIN_SUBMIT
        else Role.ORG_ADMIN
    )
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(role,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _command(manifest: dict[str, Any] | None = None) -> RegisterPackage:
    document = manifest or _manifest()
    schema = _schema()
    digest = str(document["package_digest"]).removeprefix("sha256:")
    return RegisterPackage(
        classification=DataClassification.INTERNAL,
        manifest=document,
        package_artifact=ArtifactReference(uuid4(), digest, 1024, "application/zip"),
        signature_artifact=ArtifactReference(
            uuid4(), "1" * 64, 256, "application/vnd.dev.cosign.simplesigning.v1+json"
        ),
        sbom_artifact=ArtifactReference(
            uuid4(), "2" * 64, 512, "application/spdx+json"
        ),
        schemas=(
            RegisterSchema(
                str(schema["$id"]),
                1,
                SchemaRole.CONFIG,
                schema,
                content_sha256(schema),
            ),
        ),
        idempotency_key="plugin-registration-1",
    )


class _CaptureRepository:
    def __init__(self) -> None:
        self.schema_ids: tuple[UUID, ...] = ()

    def register(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RegisterPackage,
        definition_id: UUID,
        package_id: UUID,
        event_id: UUID,
        schema_ids: tuple[UUID, ...],
        manifest: ImmutablePluginManifest,
        schemas: tuple[SchemaDocument, ...],
        submission_digest: str,
        now: datetime,
    ) -> PackageRegistrationResult:
        del decision, submission_digest
        self.schema_ids = schema_ids
        event = PackageStateEventRecord(
            event_id,
            package_id,
            1,
            None,
            PackageState.CONTRACT_VALIDATED,
            now,
            context.principal.id,
            "manifest and schemas contract validated",
            context.request_id,
            context.trace_id,
        )
        package = PackageRecord(
            package_id,
            definition_id,
            context.organization_id,
            context.project_id,
            command.classification,
            manifest,
            command.package_artifact,
            command.signature_artifact,
            command.sbom_artifact,
            schemas,
            PackageState.CONTRACT_VALIDATED,
            (event,),
            now,
            context.principal.id,
            context.request_id,
            context.trace_id,
            None,
        )
        return PackageRegistrationResult(package, False)

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
    ) -> PackageRecord:
        del context, decision, package_id
        raise NotImplementedError

    def get_active(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plugin_id: str,
        plugin_version: str,
        package_digest: str,
    ) -> PackageRecord:
        del context, decision, plugin_id, plugin_version, package_digest
        raise NotImplementedError

    def get_active_for_plugin(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        plugin_id: str,
        plugin_version: str,
    ) -> PackageRecord:
        del context, decision, plugin_id, plugin_version
        raise NotImplementedError

    def transition(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        package_id: UUID,
        target: PackageState,
        event_id: UUID,
        reason: str,
        now: datetime,
    ) -> PackageRecord:
        del context, decision, package_id, target, event_id, reason, now
        raise NotImplementedError

    def activate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ActivatePackage,
        activation_id: UUID,
        now: datetime,
    ) -> PackageRecord:
        del context, decision, command, activation_id, now
        raise NotImplementedError


def test_manifest_and_schema_are_canonical_immutable_registration_facts() -> None:
    context = _context()
    repository = _CaptureRepository()
    service = PluginRegistryService(
        repository=repository,
        validator=JsonSchemaPluginContractValidator(),
        clock=lambda: NOW,
    )
    original = _manifest()

    result = service.register(context, _decision(context), _command(original))
    original["display_name"] = "mutated after registration"

    assert result.package.id != result.package.definition_id
    assert result.package.manifest.display_name == "Reference Identity Processor"
    assert result.package.state is PackageState.CONTRACT_VALIDATED
    assert result.package.schemas[0].document() == _schema()
    assert len(repository.schema_ids) == 1
    assert repository.schema_ids[0] not in {
        result.package.id,
        result.package.definition_id,
    }


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda value: value.update(contract_api=">=2.0 <3.0"), "contract_api"),
        (
            lambda value: value["extensions"][0].update(capabilities=[]),
            "capability",
        ),
        (
            lambda value: value["permissions"].update(
                artifact_read_roles=["zeta", "alpha"]
            ),
            "sorted",
        ),
        (
            lambda value: value["resources"].update(cpu=0.0001),
            r"numeric\(10,3\)",
        ),
    ],
)
def test_manifest_rejects_unsupported_contract_or_incomplete_normalized_contract(
    mutation: Any, message: str
) -> None:
    manifest = _manifest()
    mutation(manifest)
    with pytest.raises(InvalidManifest, match=message):
        ImmutablePluginManifest.from_validated_document(manifest)


def test_registration_rejects_digest_substitution_and_missing_schema_coverage() -> None:
    context = _context()
    service = PluginRegistryService(
        repository=_CaptureRepository(),
        validator=JsonSchemaPluginContractValidator(),
        clock=lambda: NOW,
    )
    substituted = _command()
    substituted = RegisterPackage(
        substituted.classification,
        substituted.manifest,
        ArtifactReference(uuid4(), "f" * 64, 1024, "application/zip"),
        substituted.signature_artifact,
        substituted.sbom_artifact,
        substituted.schemas,
        substituted.idempotency_key,
    )
    with pytest.raises(InvalidManifest, match="artifact digest"):
        service.register(context, _decision(context), substituted)

    missing = _command()
    missing = RegisterPackage(
        missing.classification,
        missing.manifest,
        missing.package_artifact,
        missing.signature_artifact,
        missing.sbom_artifact,
        (),
        missing.idempotency_key,
    )
    with pytest.raises(InvalidManifest, match="schemas"):
        service.register(context, _decision(context), missing)


def test_plugin_state_machine_is_terminal_after_rejection_or_revocation() -> None:
    assert_package_transition(
        PackageState.CONTRACT_VALIDATED, PackageState.ELIGIBLE
    )
    assert_package_transition(PackageState.ELIGIBLE, PackageState.REVOKED)
    assert_package_transition(PackageState.ELIGIBLE, PackageState.UNAVAILABLE)

    with pytest.raises(InvalidPackageState):
        assert_package_transition(PackageState.REVOKED, PackageState.ELIGIBLE)
    with pytest.raises(InvalidPackageState):
        assert_package_transition(PackageState.REJECTED, PackageState.ELIGIBLE)


def test_submit_permission_cannot_be_replaced_with_activation_permission() -> None:
    context = _context()
    service = PluginRegistryService(
        repository=_CaptureRepository(),
        validator=JsonSchemaPluginContractValidator(),
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="authorization decision"):
        service.register(
            context,
            _decision(context, Permission.PLUGIN_ACTIVATE),
            _command(),
        )


def test_submission_classification_must_fit_service_layer_clearance() -> None:
    context = _context()
    service = PluginRegistryService(
        repository=_CaptureRepository(),
        validator=JsonSchemaPluginContractValidator(),
        clock=lambda: NOW,
    )
    command = replace(
        _command(), classification=DataClassification.RESTRICTED
    )
    decision = replace(
        _decision(context), max_classification=DataClassification.INTERNAL
    )

    with pytest.raises(PackageAccessDenied, match="clearance"):
        service.register(context, decision, command)
