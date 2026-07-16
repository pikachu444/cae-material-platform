import base64
import hashlib
import json
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from cmp.modules.artifacts.domain.content import StoredObject
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.jobs.adapters.signed_connectors import (
    ConnectorRejected,
    HttpResponse,
    SignedEventEncoder,
    SignedHttpEventTransport,
    SignedObjectStorageEventTransport,
)
from cmp.modules.jobs.domain.events import CloudEventDraft, CloudEventRecord
from cmp.shared.domain.revisions import canonical_json_bytes
from cmp.tools.release_signing import LocalEd25519Signer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

NOW = datetime(2026, 7, 17, 13, 0, tzinfo=UTC)
ORG = UUID("97000000-0000-4000-8000-000000000001")
PROJECT = UUID("97000000-0000-4000-8000-000000000002")
ACTOR = UUID("97000000-0000-4000-8000-000000000003")
AGGREGATE = UUID("97000000-0000-4000-8000-000000000004")
EVENT = UUID("97000000-0000-4000-8000-000000000005")


def _event() -> CloudEventRecord:
    return CloudEventRecord(
        EVENT,
        1,
        CloudEventDraft(
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            aggregate_type="artifact.artifact",
            aggregate_id=AGGREGATE,
            event_type="io.cmp.artifact.available.v1",
            source="urn:cmp:module:artifacts",
            subject=f"artifacts/{AGGREGATE}",
            data_schema="urn:cmp:schema:event:artifact-available:1.0.0",
            data={"artifact_id": str(AGGREGATE), "sha256": "a" * 64},
            occurred_at=NOW,
            recorded_by=ACTOR,
            request_id=UUID("97000000-0000-4000-8000-000000000006"),
            trace_id="00-97000000000000000000000000000000-9700000000000000-01",
            deduplication_key=f"artifact.available:{AGGREGATE}",
        ),
        NOW,
    )


def _encoder(kind: str = "webhook") -> tuple[SignedEventEncoder, bytes]:
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return (
        SignedEventEncoder(
            LocalEd25519Signer(key, mode="supplied_ed25519_key"),
            kind=kind,
            audience="https://connector.example.test/cmp/events",
        ),
        public,
    )


def test_signed_event_payload_is_deterministic_and_verifiable() -> None:
    encoder, public = _encoder()

    first = encoder.encode(_event())
    second = encoder.encode(_event())

    assert first == second
    document = json.loads(first.body)
    signed = canonical_json_bytes(document["manifest"])
    assert hashlib.sha256(signed).hexdigest() == document["manifest_sha256"]
    key = serialization.load_pem_public_key(public)
    assert isinstance(key, Ed25519PublicKey)
    key.verify(base64.b64decode(document["signature_base64"]), signed)
    assert document["manifest"]["event"]["id"] == str(EVENT)


class _Response:
    status: int
    headers: Mapping[str, str]

    def __init__(self, digest: str) -> None:
        self.status = 202
        self.headers = {"X-CMP-Accepted-Digest": digest}
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_http_connector_rotates_bearer_and_requires_digest_acknowledgement() -> None:
    encoder, _ = _encoder("rest")
    tokens = iter(("first.token.value", "second.token.value"))
    observed: list[dict[str, Any]] = []

    def sender(request: urllib.request.Request, timeout: float) -> HttpResponse:
        assert isinstance(request.data, bytes)
        body = request.data
        digest = hashlib.sha256(body).hexdigest()
        observed.append(
            {
                "authorization": request.get_header("Authorization"),
                "digest": request.get_header("X-cmp-delivery-sha256"),
                "idempotency": request.get_header("Idempotency-key"),
                "timeout": timeout,
            }
        )
        return _Response(digest)

    transport = SignedHttpEventTransport(
        "https://connector.example.test/cmp/events",
        encoder,
        bearer_token=lambda: next(tokens),
        sender=sender,
    )
    transport.publish(_event())
    transport.publish(_event())

    assert [item["authorization"] for item in observed] == [
        "Bearer first.token.value",
        "Bearer second.token.value",
    ]
    assert all(item["digest"] for item in observed)
    assert all(item["idempotency"] == str(EVENT) for item in observed)

    def missing_ack(_request: urllib.request.Request, _timeout: float) -> HttpResponse:
        return _Response("0" * 64)

    rejected = SignedHttpEventTransport(
        "https://connector.example.test/cmp/events", encoder, sender=missing_ack
    )
    with pytest.raises(ConnectorRejected, match="acknowledgement"):
        rejected.publish(_event())


class _ObjectStore:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def stage_bytes(self, *, object_key: str, value: bytes, media_type: str) -> StoredObject:
        assert media_type == "application/vnd.cmp.signed-event+json"
        existing = self.values.setdefault(object_key, value)
        if existing != value:
            raise RuntimeError("different bytes")
        return self._stored(object_key, value)

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject:
        value = self.values[source_key]
        assert hashlib.sha256(value).hexdigest() == expected_sha256
        assert len(value) == expected_size_bytes
        existing = self.values.setdefault(target_key, value)
        if existing != value:
            raise RuntimeError("different bytes")
        del self.values[source_key]
        return self._stored(target_key, value)

    @staticmethod
    def _stored(key: str, value: bytes) -> StoredObject:
        digest = hashlib.sha256(value).hexdigest()
        return StoredObject(key, len(value), digest, digest[:32], "v1")


def test_object_storage_connector_is_immutable_and_replay_idempotent() -> None:
    store = _ObjectStore()
    encoder, _ = _encoder("object_storage")
    transport = SignedObjectStorageEventTransport(store, encoder)

    transport.publish(_event())
    transport.publish(_event())

    final = [key for key in store.values if key.startswith("final/connectors/")]
    assert len(final) == 1
    assert str(ORG) in final[0]
    assert str(PROJECT) in final[0]


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://connector.example.test/events",
        "https://user:secret@connector.example.test/events",
        "https://connector.example.test/events?token=secret",
    ),
)
def test_http_connector_rejects_insecure_or_credential_bearing_endpoint(
    endpoint: str,
) -> None:
    encoder, _ = _encoder()
    with pytest.raises(ValueError, match=r"HTTPS|credentials/query"):
        SignedHttpEventTransport(endpoint, encoder)
