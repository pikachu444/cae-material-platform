from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.artifacts.adapters.api.content import install_content_artifact_api
from cmp.modules.artifacts.application.content import (
    ArtifactDownload,
    ArtifactDownloadGrant,
)
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactAccessDenied,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
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
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 12, 18, 0, tzinfo=UTC)
ORG = UUID("8d000000-0000-4000-8000-000000000001")
PROJECT = UUID("8d000000-0000-4000-8000-000000000002")
ACTOR = UUID("8d000000-0000-4000-8000-000000000003")
ARTIFACT = UUID("8d000000-0000-4000-8000-000000000004")
RAW = UUID("8d000000-0000-4000-8000-000000000005")
PAYLOAD = b"immutable-api-artifact"
TOKEN = "t10." + "b" * 96
TRACE = "00-0000000000000000000000000000008d-000000000000008d-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Artifact Reader", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.ARTIFACT_READ,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=database_permissions_for(Permission.ARTIFACT_READ),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record() -> ArtifactRecord:
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    return ArtifactRecord(
        Artifact(
            id=ARTIFACT,
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            artifact_kind=ArtifactKind.RAW,
            artifact_role="raw.source",
            schema_ref=None,
            media_type="application/octet-stream",
            size_bytes=len(PAYLOAD),
            sha256=digest,
            storage_key=content_object_key(
                ORG, PROJECT, DataClassification.INTERNAL, digest
            ),
            encryption_profile="deployment-default",
            source_raw_asset_id=RAW,
            source_pending_id=uuid4(),
            created_at=NOW,
            created_by=ACTOR,
        ),
        IntegrityStatus.VERIFIED,
        NOW,
        uuid4(),
    )


class _ArtifactService:
    def __init__(self) -> None:
        self.record = _record()

    def get_artifact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactRecord:
        del context, decision
        if artifact_id != ARTIFACT:
            raise ArtifactNotFound(str(artifact_id))
        return self.record

    async def issue_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
    ) -> ArtifactDownloadGrant:
        self.get_artifact(context, decision, artifact_id)
        return ArtifactDownloadGrant(
            artifact_id,
            TOKEN,
            NOW + timedelta(minutes=5),
            f"/api/v1/artifacts/{artifact_id}/content",
            self.record.artifact.sha256,
            self.record.artifact.size_bytes,
            self.record.artifact.media_type,
        )

    async def open_download(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        token: str,
    ) -> ArtifactDownload:
        self.get_artifact(context, decision, artifact_id)
        if token != TOKEN:
            raise ArtifactAccessDenied("invalid token")

        async def chunks() -> AsyncIterator[bytes]:
            yield PAYLOAD[:5]
            await asyncio.sleep(0)
            yield PAYLOAD[5:]

        return ArtifactDownload(self.record, chunks())


def _application() -> FastAPI:
    application = FastAPI()
    service = _ArtifactService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = DECISION

    install_content_artifact_api(
        application,
        service=cast(Any, service),
        security_dependency=security,
        read_dependency=read,
    )
    return application


def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(method, path, headers=headers)

    return asyncio.run(send())


def test_artifact_api_metadata_token_and_stream_hide_storage_key() -> None:
    application = _application()
    metadata = _request(application, "GET", f"/api/v1/artifacts/{ARTIFACT}")

    assert metadata.status_code == 200
    assert metadata.json()["integrity_status"] == "verified"
    assert "storage_key" not in metadata.text
    grant = _request(
        application,
        "POST",
        f"/api/v1/artifacts/{ARTIFACT}:download-token",
    )
    assert grant.status_code == 200
    assert grant.json()["transfer_token"] == TOKEN
    assert grant.headers["Cache-Control"] == "private, no-store"
    assert "storage_key" not in grant.text
    downloaded = _request(
        application,
        "GET",
        f"/api/v1/artifacts/{ARTIFACT}/content",
        headers={"Artifact-Transfer-Token": TOKEN},
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PAYLOAD
    assert downloaded.headers["X-Content-SHA256"] == hashlib.sha256(
        PAYLOAD
    ).hexdigest()


def test_artifact_api_hides_unknown_and_rejects_tampered_or_missing_token() -> None:
    application = _application()
    unknown = _request(application, "GET", f"/api/v1/artifacts/{uuid4()}")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "CMP-ARTIFACT-0001"

    tampered = _request(
        application,
        "GET",
        f"/api/v1/artifacts/{ARTIFACT}/content",
        headers={"Artifact-Transfer-Token": TOKEN[:-1] + "A"},
    )
    assert tampered.status_code == 403
    assert tampered.json()["code"] == "CMP-ARTIFACT-0002"
    missing = _request(
        application,
        "GET",
        f"/api/v1/artifacts/{ARTIFACT}/content",
    )
    assert missing.status_code == 422
