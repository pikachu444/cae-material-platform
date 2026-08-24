from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.review_release.application.release_service import (
    ReleaseRepository,
    ReleaseService,
)
from cmp.modules.review_release.domain.release import (
    CreateRelease,
    InvalidRelease,
    ReleaseConflict,
    ReleaseManifestRecord,
    ReleaseRecord,
    ReleaseState,
    candidate_manifest_sha256,
)

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=UTC)
ORG = UUID("30000000-0000-4000-8000-000000000001")
PROJECT = UUID("30000000-0000-4000-8000-000000000002")
ACTOR = UUID("30000000-0000-4000-8000-000000000003")
REQUEST = UUID("30000000-0000-4000-8000-000000000004")
BASE = UUID("30000000-0000-4000-8000-000000000010")
DIGEST = "a" * 64


def context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Release publisher", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(ACTOR),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST,
        trace_id="trace-release",
        authenticated_at=NOW,
    )


def decision(permission: Permission = Permission.RELEASE_PUBLISH) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.RELEASE_APPROVER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=REQUEST,
        trace_id="trace-release",
        decided_at=NOW,
    )


def command() -> CreateRelease:
    def uid(offset: int) -> UUID:
        return UUID(f"30000000-0000-4000-8000-{offset:012d}")

    return CreateRelease(
        classification=DataClassification.INTERNAL,
        release_code="reference-release",
        title="Reference release",
        material_id=BASE,
        material_revision_id=uid(11),
        material_state_id=uid(12),
        material_state_revision_id=uid(13),
        property_set_id=uid(14),
        property_set_revision_id=uid(15),
        material_model_id=uid(16),
        material_model_revision_id=uid(17),
        material_model_content_sha256=DIGEST,
        solver_card_id=uid(18),
        solver_card_revision_id=uid(19),
        solver_card_content_sha256=DIGEST,
        mapping_report_sha256=DIGEST,
        card_sha256=DIGEST,
        validation_result_id=uid(20),
        validation_result_sha256=DIGEST,
        review_request_id=uid(21),
        review_manifest_sha256="0" * 64,
        provenance_snapshot_sha256=DIGEST,
        reason="Approve exact immutable candidate",
    )


@dataclass
class MemoryReleaseRepository:
    value: ReleaseRecord | None = None

    def create(self, **kwargs: object) -> ReleaseRecord:
        candidate = kwargs["command"]
        assert isinstance(candidate, CreateRelease)
        manifest = ReleaseManifestRecord(
            id=cast(UUID, kwargs["manifest_id"]),
            release_id=cast(UUID, kwargs["release_id"]),
            organization_id=ORG,
            project_id=PROJECT,
            classification=candidate.classification,
            manifest_sha256=DIGEST,
            package_sha256=hashlib.sha256(b"{}").hexdigest(),
            package_size_bytes=2,
            package_media_type="application/vnd.cmp.release-manifest+json",
            material_id=candidate.material_id,
            material_revision_id=candidate.material_revision_id,
            material_state_id=candidate.material_state_id,
            material_state_revision_id=candidate.material_state_revision_id,
            property_set_id=candidate.property_set_id,
            property_set_revision_id=candidate.property_set_revision_id,
            material_model_id=candidate.material_model_id,
            material_model_revision_id=candidate.material_model_revision_id,
            material_model_content_sha256=candidate.material_model_content_sha256,
            solver_card_id=candidate.solver_card_id,
            solver_card_revision_id=candidate.solver_card_revision_id,
            solver_card_content_sha256=candidate.solver_card_content_sha256,
            mapping_report_sha256=candidate.mapping_report_sha256,
            card_sha256=candidate.card_sha256,
            validation_result_id=candidate.validation_result_id,
            validation_result_sha256=candidate.validation_result_sha256,
            review_request_id=candidate.review_request_id,
            review_manifest_sha256=candidate.review_manifest_sha256,
            provenance_snapshot_sha256=candidate.provenance_snapshot_sha256,
            created_at=cast(datetime, kwargs["occurred_at"]),
            created_by=cast(UUID, kwargs["actor_id"]),
            reason=candidate.reason,
            state=ReleaseState.RELEASED,
        )
        self.value = ReleaseRecord(
            id=cast(UUID, kwargs["release_id"]),
            organization_id=ORG,
            project_id=PROJECT,
            classification=candidate.classification,
            release_code=candidate.release_code,
            title=candidate.title,
            channel="reference",
            created_at=cast(datetime, kwargs["occurred_at"]),
            created_by=cast(UUID, kwargs["actor_id"]),
            manifest=manifest,
            package_text="{}",
        )
        return self.value

    def get(self, **kwargs: object) -> ReleaseRecord:
        if self.value is None:
            raise ReleaseConflict("not found")
        return self.value

    def list(self, **kwargs: object) -> tuple[ReleaseRecord, ...]:
        return (self.value,) if self.value else ()


def test_candidate_digest_is_stable_and_review_input_must_match_it() -> None:
    candidate = command()
    expected = candidate_manifest_sha256(candidate)
    assert expected != "0" * 64
    assert replace(candidate, review_manifest_sha256=expected).review_manifest_sha256 == expected
    with pytest.raises(InvalidRelease):
        replace(candidate, review_manifest_sha256="not-a-sha")


def test_candidate_manifest_digest_changes_when_a_component_is_substituted() -> None:
    candidate = command()
    substituted = replace(
        candidate, solver_card_revision_id=UUID("30000000-0000-4000-8000-000000000099")
    )
    assert candidate_manifest_sha256(candidate) != candidate_manifest_sha256(substituted)


def test_released_package_digest_rejects_line_ending_substitution() -> None:
    repository = MemoryReleaseRepository()
    value = repository.create(
        command=command(),
        manifest_id=UUID("30000000-0000-4000-8000-000000000021"),
        release_id=UUID("30000000-0000-4000-8000-000000000020"),
        occurred_at=NOW,
        actor_id=ACTOR,
    )
    lf_package = b"{\n }"
    manifest = replace(
        value.manifest,
        package_sha256=hashlib.sha256(lf_package).hexdigest(),
        package_size_bytes=len(lf_package),
    )
    value = replace(value, manifest=manifest, package_text=lf_package.decode("utf-8"))

    assert len(b"{\r\n}") == value.manifest.package_size_bytes
    with pytest.raises(ReleaseConflict, match="package digest"):
        replace(value, package_text="{\r\n}")


def test_release_service_allocates_immutable_identity_and_enforces_publish_scope() -> None:
    repository = MemoryReleaseRepository()
    ids = iter(
        (
            UUID("30000000-0000-4000-8000-000000000020"),
            UUID("30000000-0000-4000-8000-000000000021"),
            UUID("30000000-0000-4000-8000-000000000022"),
        )
    )
    service = ReleaseService(
        repository=cast(ReleaseRepository, repository),
        id_factory=lambda: next(ids),
        clock=lambda: NOW,
    )

    candidate = command()
    candidate = replace(candidate, review_manifest_sha256=candidate_manifest_sha256(candidate))
    value = service.create(context(), decision(), candidate)

    assert value.id == UUID("30000000-0000-4000-8000-000000000020")
    assert value.manifest.id == UUID("30000000-0000-4000-8000-000000000021")
    assert value.channel == "reference"
    assert value.manifest.state is ReleaseState.RELEASED

    with pytest.raises(ReleaseConflict):
        replace(value, package_text="[]")

    with pytest.raises(ReleaseConflict):
        service.create(context(), decision(Permission.RELEASE_READ), candidate)
