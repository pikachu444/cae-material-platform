from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import httpx
import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.review_release.adapters.api.release import install_release_api
from cmp.modules.review_release.application.release_service import ReleaseService
from cmp.modules.review_release.domain.release import (
    CreateRelease,
    RecordReleaseUsage,
    ReleaseImpactRecord,
    ReleaseLifecycleState,
    ReleaseManifestRecord,
    ReleaseRecord,
    ReleaseState,
    ReleaseTransitionKind,
    ReleaseTransitionRecord,
    ReleaseUsageRecord,
    SupersedeRelease,
    WithdrawRelease,
    candidate_manifest_sha256,
)
from fastapi import FastAPI, HTTPException, Request

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=UTC)
ORG = UUID("31000000-0000-4000-8000-000000000001")
PROJECT = UUID("31000000-0000-4000-8000-000000000002")
AUTHOR = UUID("31000000-0000-4000-8000-000000000003")
REQUEST = UUID("31000000-0000-4000-8000-000000000004")
DIGEST = "b" * 64
PACKAGE_TEXT = '{"schema_id":"urn:cmp:governance:release:1.0.0"}'
PACKAGE_SHA = hashlib.sha256(PACKAGE_TEXT.encode("utf-8")).hexdigest()


def _uid(number: int) -> UUID:
    return UUID(f"31000000-0000-4000-8000-{number:012d}")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(AUTHOR, PrincipalType.USER, "Release publisher", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(AUTHOR),
        token_id=str(AUTHOR),
        groups=(),
        scopes=("openid",),
        request_id=REQUEST,
        trace_id="trace-release-api",
        authenticated_at=NOW,
    )


def _decision(permission: Permission) -> AuthorizationDecision:
    context = _context()
    return AuthorizationDecision(
        principal_id=AUTHOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.RELEASE_APPROVER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _command() -> CreateRelease:
    candidate = CreateRelease(
        classification=DataClassification.INTERNAL,
        release_code="api-reference-release",
        title="API reference release",
        material_id=_uid(10),
        material_revision_id=_uid(11),
        material_state_id=_uid(12),
        material_state_revision_id=_uid(13),
        property_set_id=_uid(14),
        property_set_revision_id=_uid(15),
        material_model_id=_uid(16),
        material_model_revision_id=_uid(17),
        material_model_content_sha256=DIGEST,
        solver_card_id=_uid(18),
        solver_card_revision_id=_uid(19),
        solver_card_content_sha256=DIGEST,
        mapping_report_sha256=DIGEST,
        card_sha256=DIGEST,
        validation_result_id=_uid(20),
        validation_result_sha256=DIGEST,
        review_request_id=_uid(21),
        review_manifest_sha256=DIGEST,
        provenance_snapshot_sha256=DIGEST,
        reason="API integration release",
    )
    return replace(candidate, review_manifest_sha256=candidate_manifest_sha256(candidate))


class MemoryReleaseRepository:
    def __init__(self) -> None:
        self.value: ReleaseRecord | None = None
        self.usages: list[ReleaseUsageRecord] = []
        self.successors: dict[UUID, UUID] = {}
        self.predecessors: dict[UUID, UUID] = {}
        self.transitions: list[ReleaseTransitionRecord] = []

    def create(self, **kwargs: object) -> ReleaseRecord:
        command = kwargs["command"]
        assert isinstance(command, CreateRelease)
        manifest = ReleaseManifestRecord(
            id=cast(UUID, kwargs["manifest_id"]),
            release_id=cast(UUID, kwargs["release_id"]),
            organization_id=ORG,
            project_id=PROJECT,
            classification=command.classification,
            manifest_sha256=DIGEST,
            package_sha256=PACKAGE_SHA,
            package_size_bytes=len(PACKAGE_TEXT.encode("utf-8")),
            package_media_type="application/vnd.cmp.release-manifest+json",
            material_id=command.material_id,
            material_revision_id=command.material_revision_id,
            material_state_id=command.material_state_id,
            material_state_revision_id=command.material_state_revision_id,
            property_set_id=command.property_set_id,
            property_set_revision_id=command.property_set_revision_id,
            material_model_id=command.material_model_id,
            material_model_revision_id=command.material_model_revision_id,
            material_model_content_sha256=command.material_model_content_sha256,
            solver_card_id=command.solver_card_id,
            solver_card_revision_id=command.solver_card_revision_id,
            solver_card_content_sha256=command.solver_card_content_sha256,
            mapping_report_sha256=command.mapping_report_sha256,
            card_sha256=command.card_sha256,
            validation_result_id=command.validation_result_id,
            validation_result_sha256=command.validation_result_sha256,
            review_request_id=command.review_request_id,
            review_manifest_sha256=command.review_manifest_sha256,
            provenance_snapshot_sha256=command.provenance_snapshot_sha256,
            created_at=cast(datetime, kwargs["occurred_at"]),
            created_by=cast(UUID, kwargs["actor_id"]),
            reason=command.reason,
            state=ReleaseState.RELEASED,
        )
        self.value = ReleaseRecord(
            id=cast(UUID, kwargs["release_id"]),
            organization_id=ORG,
            project_id=PROJECT,
            classification=command.classification,
            release_code=command.release_code,
            title=command.title,
            channel="reference",
            created_at=cast(datetime, kwargs["occurred_at"]),
            created_by=cast(UUID, kwargs["actor_id"]),
            manifest=manifest,
            package_text=PACKAGE_TEXT,
        )
        return self.value

    def get(self, **kwargs: object) -> ReleaseRecord:
        assert self.value is not None
        return self.value

    def list(self, **kwargs: object) -> tuple[ReleaseRecord, ...]:
        return (self.value,) if self.value else ()

    def record_usage(self, **kwargs: object) -> ReleaseUsageRecord:
        command = kwargs["command"]
        assert isinstance(command, RecordReleaseUsage)
        assert self.value is not None
        if self.value.lifecycle_state is not ReleaseLifecycleState.RELEASED:
            raise RuntimeError("release is terminal")
        usage = ReleaseUsageRecord(
            id=cast(UUID, kwargs["usage_id"]),
            release_id=self.value.id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=self.value.classification,
            usage_kind=command.usage_kind,
            used_by=cast(UUID, kwargs["actor_id"]),
            used_at=cast(datetime, kwargs["occurred_at"]),
            reason=command.reason,
        )
        self.usages.append(usage)
        return usage

    def supersede(self, **kwargs: object) -> ReleaseRecord:
        command = kwargs["command"]
        assert isinstance(command, SupersedeRelease)
        assert self.value is not None
        if self.value.id != kwargs["release_id"]:
            raise KeyError("release")
        self.value = replace(self.value, lifecycle_state=ReleaseLifecycleState.SUPERSEDED)
        self.successors[self.value.id] = command.successor_release_id
        self.predecessors[command.successor_release_id] = self.value.id
        return self.value

    def withdraw(self, **kwargs: object) -> ReleaseRecord:
        command = kwargs["command"]
        assert isinstance(command, WithdrawRelease)
        assert self.value is not None
        transition = ReleaseTransitionRecord(
            id=cast(UUID, kwargs["transition_id"]),
            release_id=self.value.id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=self.value.classification,
            kind=ReleaseTransitionKind.WITHDRAW,
            from_state=ReleaseLifecycleState.RELEASED,
            to_state=ReleaseLifecycleState.WITHDRAWN,
            successor_release_id=None,
            reason=command.reason,
            occurred_at=cast(datetime, kwargs["occurred_at"]),
            occurred_by=cast(UUID, kwargs["actor_id"]),
        )
        self.transitions.append(transition)
        self.value = replace(self.value, lifecycle_state=ReleaseLifecycleState.WITHDRAWN)
        return self.value

    def impact(self, **kwargs: object) -> ReleaseImpactRecord:
        assert self.value is not None
        return ReleaseImpactRecord(
            release=self.value,
            predecessor_release_id=self.predecessors.get(self.value.id),
            successor_release_id=self.successors.get(self.value.id),
            usages=tuple(self.usages),
            transitions=tuple(self.transitions),
            warning=(
                "Release has been withdrawn; do not use it for new solver runs."
                if self.value.lifecycle_state is ReleaseLifecycleState.WITHDRAWN
                else None
            ),
        )


def _app(repository: MemoryReleaseRepository, *, allow_read: bool = True) -> FastAPI:
    service = ReleaseService(
        repository=repository,
        id_factory=iter((_uid(30), _uid(31), _uid(32), _uid(33), _uid(34), _uid(35))).__next__,
        clock=lambda: NOW,
    )
    app = FastAPI()
    context = _context()
    read = _decision(Permission.RELEASE_READ)
    publish = _decision(Permission.RELEASE_PUBLISH)

    def security(_: Request) -> None:
        return None

    def read_permission(request: Request) -> AuthorizationDecision:
        if not allow_read:
            raise HTTPException(status_code=403, detail="release.read denied")
        request.state.security_context = context
        request.state.authorization_decision = read
        return read

    def publish_permission(request: Request) -> AuthorizationDecision:
        request.state.security_context = context
        request.state.authorization_decision = publish
        return publish

    install_release_api(
        app,
        service=service,
        security_dependency=security,
        read_dependency=read_permission,
        publish_dependency=publish_permission,
    )
    return app


@pytest.mark.anyio
async def test_release_api_publishes_lists_reads_and_downloads_digest_fixed_package() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(MemoryReleaseRepository())),
        base_url="http://test",
    ) as client:
        body = {field: str(getattr(_command(), field)) for field in _command().__dataclass_fields__}
        body["classification"] = "internal"
        body["review_manifest_sha256"] = candidate_manifest_sha256(_command())
        created = await client.post("/api/v1/releases", json=body)
        assert created.status_code == 201
        release_id = created.json()["release_id"]
        assert created.json()["channel"] == "reference"
        assert created.json()["manifest"]["state"] == "released"

        listed = await client.get("/api/v1/releases")
        assert listed.status_code == 200
        assert listed.json()["items"][0]["release_id"] == release_id

        downloaded = await client.get(f"/api/v1/releases/{release_id}/download")
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"].startswith(
            "application/vnd.cmp.release-manifest+json"
        )
        assert downloaded.headers["etag"] == f'"sha256:{PACKAGE_SHA}"'
        assert downloaded.content.startswith(b"{")


@pytest.mark.anyio
async def test_release_download_rejects_unauthorized_read_before_package_lookup() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(MemoryReleaseRepository(), allow_read=False)),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/api/v1/releases/{_uid(30)}/download")
        assert response.status_code == 403


@pytest.mark.anyio
async def test_release_usage_withdrawal_and_impact_preserve_terminal_history() -> None:
    repository = MemoryReleaseRepository()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(repository)),
        base_url="http://test",
    ) as client:
        body = {field: str(getattr(_command(), field)) for field in _command().__dataclass_fields__}
        body["classification"] = "internal"
        body["review_manifest_sha256"] = candidate_manifest_sha256(_command())
        created = await client.post("/api/v1/releases", json=body)
        release_id = created.json()["release_id"]

        usage = await client.post(
            f"/api/v1/releases/{release_id}/usage",
            json={"usage_kind": "consume", "reason": "Explicit solver input selection"},
        )
        assert usage.status_code == 201

        withdrawn = await client.post(
            f"/api/v1/releases/{release_id}/withdraw",
            json={"reason": "Reference evidence withdrawn"},
        )
        assert withdrawn.status_code == 200
        assert withdrawn.json()["lifecycle_state"] == "withdrawn"

        impact = await client.get(f"/api/v1/releases/{release_id}/impact")
        assert impact.status_code == 200
        assert impact.json()["release"]["lifecycle_state"] == "withdrawn"
        assert impact.json()["warning"]
        assert len(impact.json()["usages"]) == 1
        assert len(impact.json()["transitions"]) == 1

        download = await client.get(f"/api/v1/releases/{release_id}/download")
        assert download.status_code == 409
