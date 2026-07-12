from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid5

import httpx
from cmp.apps.api import create_app
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.application.uploads import (
    CreateUploadResult,
    RawAssetCompletion,
)
from cmp.modules.artifacts.domain.uploads import (
    IngestionEvent,
    RawAsset,
    RawAssetStorageState,
    UploadNotFound,
    UploadPart,
    UploadSession,
    UploadState,
)
from cmp.modules.identity_access.adapters.development.test_idp import DevelopmentTestIdp
from cmp.modules.identity_access.adapters.oidc.pyjwt import (
    OidcAccessTokenConfig,
    PyJwtAccessTokenVerifier,
)
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.application.security import SecurityContextService
from cmp.modules.identity_access.domain.authorization import (
    BindingSubject,
    DataClassification,
    Role,
    RoleBinding,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    SecurityContext,
    VerifiedAccessToken,
)

ORG = UUID("8a000000-0000-4000-8000-000000000001")
PROJECT = UUID("8a000000-0000-4000-8000-000000000002")
UPLOAD = UUID("8a000000-0000-4000-8000-000000000003")
RAW = UUID("8a000000-0000-4000-8000-000000000004")
EVENT = UUID("8a000000-0000-4000-8000-000000000005")
NAMESPACE = UUID("8a000000-0000-4000-8000-000000000006")
NOW = datetime(2026, 7, 12, 14, 0, tzinfo=UTC)
TRACE = "00-0000000000000000000000000000008a-000000000000008a-01"
PAYLOAD = b"streamed-api-part"
CAPABILITY = "t09." + "a" * 96


class _Principals:
    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        del observed_at
        return Principal(
            uuid5(NAMESPACE, f"{token.issuer}\0{token.subject}"),
            token.principal_type,
            token.display_name,
            True,
        )


class _Bindings:
    def __init__(self, *bindings: RoleBinding) -> None:
        self.bindings = bindings

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        del context, observed_at
        return self.bindings


def _security(idp: DevelopmentTestIdp) -> SecurityContextService:
    return SecurityContextService(
        verifier=PyJwtAccessTokenVerifier(
            config=OidcAccessTokenConfig(
                issuer=idp.issuer,
                audience=idp.audience,
                clock_skew_seconds=0,
            ),
            signing_keys=idp.signing_key_resolver(),
        ),
        principals=_Principals(),
    )


def _session(context: SecurityContext, *, parts: tuple[UploadPart, ...] = ()) -> UploadSession:
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    return UploadSession(
        id=UPLOAD,
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        state=UploadState.OPEN,
        original_filename="raw.bin",
        media_type="application/octet-stream",
        expected_size_bytes=len(PAYLOAD),
        expected_sha256=digest,
        part_size_bytes=len(PAYLOAD),
        expected_part_count=1,
        test_run_revision_id=None,
        staging_object_key=f"staging/{ORG}/{PROJECT}/{UPLOAD}.raw",
        object_upload_id="opaque-store-upload",
        idempotency_key="upload-api-1",
        submission_digest="1" * 64,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        created_by=context.principal.id,
        request_id=context.request_id,
        trace_id=context.trace_id,
        updated_at=NOW,
        terminal_at=None,
        raw_asset_id=None,
        failure_code=None,
        parts=parts,
    )


class _UploadService:
    def __init__(self) -> None:
        self.context: SecurityContext | None = None
        self.session: UploadSession | None = None
        self.received = b""

    async def create(
        self, context: SecurityContext, decision: object, command: object
    ) -> CreateUploadResult:
        del decision, command
        self.context = context
        self.session = _session(context)
        return CreateUploadResult(self.session, CAPABILITY, False)

    def get_upload(
        self, context: SecurityContext, decision: object, upload_id: UUID
    ) -> UploadSession:
        del context, decision
        if self.session is None or upload_id != UPLOAD:
            raise UploadNotFound(str(upload_id))
        return self.session

    async def record_part(
        self,
        context: SecurityContext,
        decision: object,
        command: object,
        chunks: AsyncIterable[bytes],
    ) -> UploadSession:
        del decision, command
        payload = bytearray()
        async for chunk in chunks:
            payload.extend(chunk)
        self.received = bytes(payload)
        part = UploadPart(
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            UPLOAD,
            1,
            len(self.received),
            hashlib.sha256(self.received).hexdigest(),
            hashlib.sha256(self.received).hexdigest(),
            NOW,
            context.principal.id,
        )
        self.session = _session(context, parts=(part,))
        return self.session

    async def complete(
        self, context: SecurityContext, decision: object, command: object
    ) -> RawAssetCompletion:
        del decision, command
        raw = RawAsset(
            RAW,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            hashlib.sha256(PAYLOAD).hexdigest(),
            len(PAYLOAD),
            "application/octet-stream",
            "raw.bin",
            RawAssetStorageState.STAGED_VERIFIED,
            f"staging/{ORG}/{PROJECT}/{UPLOAD}.raw",
            NOW,
            context.principal.id,
        )
        event = IngestionEvent(
            EVENT,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            RAW,
            UPLOAD,
            None,
            False,
            NOW,
            context.principal.id,
            context.request_id,
            context.trace_id,
        )
        assert self.session is not None
        self.session = replace(
            self.session,
            state=UploadState.COMPLETED,
            raw_asset_id=RAW,
            terminal_at=NOW,
        )
        return RawAssetCompletion(self.session, raw, event, False)

    async def cancel(
        self, context: SecurityContext, decision: object, command: object
    ) -> UploadSession:
        del context, decision, command
        assert self.session is not None
        self.session = replace(
            self.session,
            state=UploadState.CANCELLED,
            terminal_at=NOW,
        )
        return self.session

    def get_raw_asset(
        self, context: SecurityContext, decision: object, raw_asset_id: UUID
    ) -> RawAsset:
        del decision
        if raw_asset_id != RAW:
            raise UploadNotFound(str(raw_asset_id))
        return RawAsset(
            RAW,
            ORG,
            PROJECT,
            DataClassification.INTERNAL,
            hashlib.sha256(PAYLOAD).hexdigest(),
            len(PAYLOAD),
            "application/octet-stream",
            "raw.bin",
            RawAssetStorageState.STAGED_VERIFIED,
            f"staging/{ORG}/{PROJECT}/{UPLOAD}.raw",
            NOW,
            context.principal.id,
        )


def _application() -> tuple[object, DevelopmentTestIdp, _UploadService]:
    idp = DevelopmentTestIdp()
    binding = RoleBinding(
        uuid5(NAMESPACE, "uploader-binding"),
        ORG,
        PROJECT,
        BindingSubject.for_group(idp.issuer, "uploaders"),
        Role.TEST_ENGINEER,
        DataClassification.INTERNAL,
        False,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    uploads = _UploadService()
    application = create_app(
        Settings(environment="test"),
        _security(idp),
        AuthorizationService(bindings=_Bindings(binding)),
        upload_service=cast(Any, uploads),
    )
    return application, idp, uploads


def _token(idp: DevelopmentTestIdp, group: str = "uploaders") -> str:
    return idp.issue_user_token(
        subject=group,
        organization_id=ORG,
        project_id=PROJECT,
        display_name=group,
        groups=(group,),
    )


def _request(
    application: object,
    token: str,
    method: str,
    path: str,
    *,
    json_body: object | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=cast(Any, application))
        request_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.request(
                method,
                path,
                json=json_body,
                content=content,
                headers=request_headers,
            )

    return asyncio.run(send())


def test_upload_api_streams_part_completes_and_never_exposes_storage_key() -> None:
    application, idp, uploads = _application()
    token = _token(idp)
    created = _request(
        application,
        token,
        "POST",
        "/api/v1/uploads",
        json_body={
            "classification": "internal",
            "original_filename": "raw.bin",
            "media_type": "application/octet-stream",
            "expected_size_bytes": len(PAYLOAD),
            "expected_sha256": hashlib.sha256(PAYLOAD).hexdigest(),
        },
        headers={"Idempotency-Key": "upload-api-1"},
    )

    assert created.status_code == 201
    assert created.headers["Location"] == f"/api/v1/uploads/{UPLOAD}"
    capability = created.json()["upload_capability"]
    assert capability == CAPABILITY
    assert "staging_object_key" not in created.text
    part = _request(
        application,
        token,
        "PUT",
        f"/api/v1/uploads/{UPLOAD}/parts/1",
        content=PAYLOAD,
        headers={
            "Upload-Capability": capability,
            "Content-Type": "application/octet-stream",
        },
    )
    assert part.status_code == 200
    assert uploads.received == PAYLOAD
    completed = _request(
        application,
        token,
        "POST",
        f"/api/v1/uploads/{UPLOAD}:complete",
        headers={"Upload-Capability": capability},
    )
    assert completed.status_code == 200
    assert completed.json()["raw_asset"]["raw_asset_id"] == str(RAW)
    assert "staging_object_key" not in completed.text
    raw = _request(
        application,
        token,
        "GET",
        f"/api/v1/raw-assets/{RAW}",
    )
    assert raw.status_code == 200
    assert raw.json()["storage_state"] == "staged_verified"


def test_upload_api_requires_artifact_permission_and_safe_filename() -> None:
    application, idp, _ = _application()
    denied = _request(
        application,
        _token(idp, "not-uploaders"),
        "POST",
        "/api/v1/uploads",
        json_body={
            "classification": "internal",
            "original_filename": "raw.bin",
            "media_type": "application/octet-stream",
            "expected_size_bytes": 1,
            "expected_sha256": "0" * 64,
        },
        headers={"Idempotency-Key": "upload-api-denied"},
    )
    assert denied.status_code == 403

    invalid = _request(
        application,
        _token(idp),
        "POST",
        "/api/v1/uploads",
        json_body={
            "classification": "internal",
            "original_filename": "../escape.bin",
            "media_type": "application/octet-stream",
            "expected_size_bytes": 1,
            "expected_sha256": "0" * 64,
        },
        headers={"Idempotency-Key": "upload-api-invalid"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "CMP-UPLOAD-0004"

    whitespace = _request(
        application,
        _token(idp),
        "POST",
        "/api/v1/uploads",
        json_body={
            "classification": "internal",
            "original_filename": " raw.bin ",
            "media_type": "application/octet-stream",
            "expected_size_bytes": 1,
            "expected_sha256": "0" * 64,
        },
        headers={"Idempotency-Key": "upload-api-whitespace"},
    )
    assert whitespace.status_code == 422
