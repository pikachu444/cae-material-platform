from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.application.uploads import (
    UploadCapabilityCodec,
    UploadPolicy,
)
from cmp.modules.artifacts.domain.uploads import (
    InvalidUpload,
    ObjectStoreError,
    UploadAccessDenied,
    UploadExpired,
    UploadSession,
    UploadState,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)

NOW = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
ORG = UUID("88000000-0000-4000-8000-000000000001")
PROJECT = UUID("88000000-0000-4000-8000-000000000002")
ACTOR = UUID("88000000-0000-4000-8000-000000000003")
TRACE = "00-00000000000000000000000000000088-0000000000000088-01"


def _context(*, project_id: UUID = PROJECT, actor_id: UUID = ACTOR) -> SecurityContext:
    return SecurityContext(
        principal=Principal(actor_id, PrincipalType.USER, "Uploader", True),
        organization_id=ORG,
        project_id=project_id,
        issuer="https://test-idp.invalid",
        subject=str(actor_id),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _session() -> UploadSession:
    return UploadSession(
        id=uuid4(),
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        state=UploadState.OPEN,
        original_filename="raw.bin",
        media_type="application/octet-stream",
        expected_size_bytes=10,
        expected_sha256="0" * 64,
        part_size_bytes=4,
        expected_part_count=3,
        test_run_revision_id=None,
        staging_object_key=f"staging/{ORG}/{PROJECT}/{uuid4()}.raw",
        object_upload_id=str(uuid4()),
        idempotency_key="upload-1",
        submission_digest="1" * 64,
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
        created_by=ACTOR,
        request_id=uuid4(),
        trace_id=TRACE,
        updated_at=NOW,
        terminal_at=None,
        raw_asset_id=None,
        failure_code=None,
    )


def test_upload_policy_bounds_size_part_count_and_environment_maximum() -> None:
    policy = UploadPolicy(
        max_object_bytes=1024,
        default_part_bytes=256,
        min_part_bytes=64,
        max_part_bytes=512,
        max_parts=4,
    )

    assert policy.part_size(1024, None) == 256
    assert policy.part_size(32, None) == 32
    with pytest.raises(ValueError, match="size exceeds"):
        policy.part_size(1025, None)
    with pytest.raises(ValueError, match="part"):
        policy.part_size(1024, 63)
    with pytest.raises(ValueError, match="part"):
        policy.part_size(32, 513)


def test_blank_upload_environment_is_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CMP_UPLOAD_STORAGE_ROOT", "")
    monkeypatch.setenv("CMP_UPLOAD_CAPABILITY_SECRET", "")
    monkeypatch.setenv("CMP_ARTIFACT_TRANSFER_SECRET", "")

    settings = Settings.from_environment()

    assert settings.upload_storage_root is None
    assert settings.upload_capability_secret is None
    assert settings.artifact_transfer_secret is None


def test_upload_capability_is_actor_tenant_expiry_and_signature_scoped() -> None:
    session = _session()
    codec = UploadCapabilityCodec(b"t09-test-secret-must-be-at-least-32-bytes", clock=lambda: NOW)
    token = codec.issue(session)

    codec.verify(token, session, _context())
    with pytest.raises(UploadAccessDenied, match="scope"):
        codec.verify(token, session, _context(project_id=uuid4()))
    with pytest.raises(UploadAccessDenied):
        codec.verify(token[:-1] + ("A" if token[-1] != "A" else "B"), session, _context())
    expired = UploadCapabilityCodec(
        b"t09-test-secret-must-be-at-least-32-bytes",
        clock=lambda: session.expires_at,
    )
    with pytest.raises(UploadExpired):
        expired.verify(token, session, _context())


def test_filesystem_object_store_streams_parts_and_never_overwrites(
    tmp_path: Path,
) -> None:
    store = FilesystemMultipartObjectStore(tmp_path / "objects")
    key = f"staging/{ORG}/{PROJECT}/{uuid4()}.raw"
    payload = b"abcdefghij"

    async def chunks(value: bytes, size: int = 2) -> AsyncIterator[bytes]:
        for offset in range(0, len(value), size):
            await asyncio.sleep(0)
            yield value[offset : offset + size]

    async def run() -> None:
        upload_id = await store.initiate(key, "application/octet-stream")
        first = await store.upload_part(
            object_key=key,
            upload_id=upload_id,
            part_number=1,
            chunks=chunks(payload[:6]),
            expected_size=6,
        )
        replay = await store.upload_part(
            object_key=key,
            upload_id=upload_id,
            part_number=1,
            chunks=chunks(payload[:6]),
            expected_size=6,
        )
        assert replay == first
        with pytest.raises(ObjectStoreError, match="different bytes"):
            await store.upload_part(
                object_key=key,
                upload_id=upload_id,
                part_number=1,
                chunks=chunks(b"ABCDEF"),
                expected_size=6,
            )
        second = await store.upload_part(
            object_key=key,
            upload_id=upload_id,
            part_number=2,
            chunks=chunks(payload[6:]),
            expected_size=4,
        )
        completed = await store.complete(
            object_key=key,
            upload_id=upload_id,
            parts=(first, second),
        )
        assert completed.sha256 == hashlib.sha256(payload).hexdigest()
        assert store.read_for_testing(key) == payload
        replayed = await store.complete(
            object_key=key,
            upload_id=upload_id,
            parts=(first, second),
        )
        assert replayed == completed

        undersized_key = f"staging/{ORG}/{PROJECT}/{uuid4()}.raw"
        undersized_id = await store.initiate(
            undersized_key,
            "application/octet-stream",
        )
        with pytest.raises(InvalidUpload, match="size differs"):
            await store.upload_part(
                object_key=undersized_key,
                upload_id=undersized_id,
                part_number=1,
                chunks=chunks(b"short"),
                expected_size=6,
            )

    asyncio.run(run())


def test_filesystem_object_store_rejects_path_injection(tmp_path: Path) -> None:
    store = FilesystemMultipartObjectStore(tmp_path / "objects")

    with pytest.raises(ObjectStoreError, match="unsafe"):
        asyncio.run(store.initiate("../escape", "application/octet-stream"))
