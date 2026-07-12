from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.application.content import (
    ArtifactTransferCodec,
)
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactAccessDenied,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactRecord,
    ArtifactTransferExpired,
    IntegrityStatus,
    InvalidArtifact,
    content_object_key,
    parse_content_object_key,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)

NOW = datetime(2026, 7, 12, 16, 0, tzinfo=UTC)
ORG = UUID("8b000000-0000-4000-8000-000000000001")
PROJECT = UUID("8b000000-0000-4000-8000-000000000002")
ACTOR = UUID("8b000000-0000-4000-8000-000000000003")
RAW = UUID("8b000000-0000-4000-8000-000000000004")
TRACE = "00-0000000000000000000000000000008b-000000000000008b-01"
SECRET = b"t10-artifact-transfer-secret-at-least-32-bytes"


def _context(*, project_id: UUID = PROJECT, actor_id: UUID = ACTOR) -> SecurityContext:
    return SecurityContext(
        principal=Principal(actor_id, PrincipalType.USER, "Artifact User", True),
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


def _record(payload: bytes = b"immutable-artifact") -> ArtifactRecord:
    digest = hashlib.sha256(payload).hexdigest()
    artifact = Artifact(
        id=uuid4(),
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        artifact_kind=ArtifactKind.RAW,
        artifact_role="raw.source",
        schema_ref=None,
        media_type="application/octet-stream",
        size_bytes=len(payload),
        sha256=digest,
        storage_key=content_object_key(
            ORG, PROJECT, DataClassification.INTERNAL, digest
        ),
        encryption_profile="deployment-default",
        source_raw_asset_id=RAW,
        source_pending_id=uuid4(),
        created_at=NOW,
        created_by=ACTOR,
    )
    return ArtifactRecord(artifact, IntegrityStatus.VERIFIED, NOW, uuid4())


def test_content_key_is_canonical_and_tenant_classification_scoped() -> None:
    digest = hashlib.sha256(b"same-bytes").hexdigest()
    key = content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest)

    assert parse_content_object_key(key) == (
        ORG,
        PROJECT,
        DataClassification.INTERNAL,
        digest,
    )
    assert key != content_object_key(
        ORG, uuid4(), DataClassification.INTERNAL, digest
    )
    assert key != content_object_key(
        ORG, PROJECT, DataClassification.RESTRICTED, digest
    )
    invalid_parts = key.split("/")
    invalid_parts[5] = "ff" if digest[:2] != "ff" else "ee"
    with pytest.raises(InvalidArtifact):
        parse_content_object_key("/".join(invalid_parts))


def test_transfer_capability_is_canonical_actor_tenant_content_and_expiry_scoped() -> None:
    record = _record()
    context = _context()
    codec = ArtifactTransferCodec(SECRET, clock=lambda: NOW)
    token = codec.issue(record, context, NOW + timedelta(minutes=5))

    codec.verify(token, record, context)
    with pytest.raises(ArtifactAccessDenied):
        codec.verify(token, record, _context(actor_id=uuid4()))
    with pytest.raises(ArtifactAccessDenied):
        codec.verify(token, _record(b"different"), context)
    with pytest.raises(ArtifactAccessDenied):
        codec.verify(
            token[:-1] + ("A" if token[-1] != "A" else "B"), record, context
        )
    expired = ArtifactTransferCodec(
        SECRET, clock=lambda: NOW + timedelta(minutes=5)
    )
    with pytest.raises(ArtifactTransferExpired):
        expired.verify(token, record, context)


def test_filesystem_promotes_streams_lists_and_never_replaces_content_key(
    tmp_path: Path,
) -> None:
    payload = b"content-addressed-bytes" * 100
    digest = hashlib.sha256(payload).hexdigest()
    staging_key = f"staging/{ORG}/{PROJECT}/{uuid4()}.raw"
    final_key = content_object_key(
        ORG, PROJECT, DataClassification.INTERNAL, digest
    )
    store = FilesystemMultipartObjectStore(tmp_path / "objects")

    async def run() -> None:
        await store.write_for_testing(staging_key, payload)
        first = await store.promote(
            source_key=staging_key,
            target_key=final_key,
            expected_sha256=digest,
            expected_size_bytes=len(payload),
        )
        replay = await store.promote(
            source_key="staging/missing/object.raw",
            target_key=final_key,
            expected_sha256=digest,
            expected_size_bytes=len(payload),
        )
        assert replay == first
        streamed = bytearray()
        async for chunk in store.stream(final_key):
            streamed.extend(chunk)
        assert bytes(streamed) == payload
        listed = await store.list_objects(f"final/{ORG}/{PROJECT}/")
        assert listed == (first,)
        with pytest.raises(ObjectStoreError, match="only non-authoritative"):
            await store.discard(final_key)

        store.corrupt_for_testing(final_key, b"corrupt")
        with pytest.raises(ArtifactIntegrityError, match="different bytes"):
            await store.promote(
                source_key=staging_key,
                target_key=final_key,
                expected_sha256=digest,
                expected_size_bytes=len(payload),
            )

    asyncio.run(run())
