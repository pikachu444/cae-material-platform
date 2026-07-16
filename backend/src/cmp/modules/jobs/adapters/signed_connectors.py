"""Signed, idempotent CloudEvent delivery adapters for HTTP and object storage."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from cmp.modules.artifacts.domain.content import StoredObject
from cmp.modules.jobs.domain.events import CloudEventRecord
from cmp.shared.domain.revisions import canonical_json_bytes
from cmp.tools.release_signing import ManifestSigner

_KIND = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class ConnectorDeliveryError(RuntimeError):
    code = "connector_unavailable"


class ConnectorRejected(ConnectorDeliveryError):
    code = "connector_rejected"


@dataclass(frozen=True, slots=True)
class SignedEventPayload:
    body: bytes
    sha256: str


class SignedEventEncoder:
    def __init__(self, signer: ManifestSigner, *, kind: str, audience: str) -> None:
        if _KIND.fullmatch(kind) is None:
            raise ValueError("connector kind is invalid")
        parsed = urlsplit(audience)
        if not parsed.scheme or parsed.username is not None or parsed.password is not None:
            raise ValueError("connector audience must be an absolute URI without credentials")
        self._signer = signer
        self._kind = kind
        self._audience = audience

    def encode(self, event: CloudEventRecord) -> SignedEventPayload:
        identity = self._signer.identity()
        manifest = {
            "delivery": {"audience": self._audience, "kind": self._kind},
            "event": event.envelope(),
            "event_data_sha256": event.draft.data_sha256,
            "schema": "cmp.signed-event-delivery.v1",
            "signature": {
                "algorithm": identity.algorithm,
                "key_id": identity.key_id,
                "provider": identity.provider,
                "public_key_sha256": hashlib.sha256(identity.public_key_pem).hexdigest(),
            },
        }
        signed_bytes = canonical_json_bytes(manifest)
        signature = self._signer.sign(signed_bytes)
        body = canonical_json_bytes(
            {
                "manifest": manifest,
                "manifest_sha256": hashlib.sha256(signed_bytes).hexdigest(),
                "signature_base64": base64.b64encode(signature).decode("ascii"),
            }
        )
        return SignedEventPayload(body, hashlib.sha256(body).hexdigest())


class HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def close(self) -> None: ...


type HttpSender = Callable[[urllib.request.Request, float], HttpResponse]


def _default_sender(request: urllib.request.Request, timeout: float) -> HttpResponse:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    return cast(
        HttpResponse,
        urllib.request.build_opener(NoRedirect).open(request, timeout=timeout),
    )


class SignedHttpEventTransport:
    """POST a signed envelope and require a digest-bound receiver acknowledgement."""

    def __init__(
        self,
        endpoint: str,
        encoder: SignedEventEncoder,
        *,
        bearer_token: Callable[[], str] | None = None,
        timeout_seconds: float = 10.0,
        allow_loopback_http: bool = False,
        sender: HttpSender | None = None,
    ) -> None:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("connector endpoint must be an HTTP(S) URL without credentials/query")
        loopback = parsed.hostname in {"127.0.0.1", "::1", "localhost"}
        if parsed.scheme != "https" and not (allow_loopback_http and loopback):
            raise ValueError("connector endpoint must use HTTPS")
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("connector timeout must be between 1 and 60 seconds")
        self._endpoint = endpoint
        self._encoder = encoder
        self._bearer_token = bearer_token
        self._timeout_seconds = timeout_seconds
        self._sender = sender or _default_sender

    def publish(self, event: CloudEventRecord) -> None:
        payload = self._encoder.encode(event)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/vnd.cmp.signed-event+json",
            "Idempotency-Key": str(event.id),
            "X-CMP-Delivery-SHA256": payload.sha256,
        }
        if self._bearer_token is not None:
            headers["Authorization"] = f"Bearer {self._bearer_token()}"
        request = urllib.request.Request(
            self._endpoint,
            data=payload.body,
            headers=headers,
            method="POST",
        )
        try:
            response = self._sender(request, self._timeout_seconds)
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500 and error.code != 429:
                raise ConnectorRejected("connector rejected the signed delivery") from error
            raise ConnectorDeliveryError("connector is temporarily unavailable") from error
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise ConnectorDeliveryError("connector is temporarily unavailable") from error
        try:
            if not 200 <= response.status < 300:
                raise ConnectorDeliveryError("connector returned an unsuccessful status")
            if response.headers.get("X-CMP-Accepted-Digest") != payload.sha256:
                raise ConnectorRejected("connector acknowledgement digest is missing or incorrect")
        finally:
            response.close()


class ConnectorObjectStore(Protocol):
    async def stage_bytes(
        self, *, object_key: str, value: bytes, media_type: str
    ) -> StoredObject: ...

    async def promote(
        self,
        *,
        source_key: str,
        target_key: str,
        expected_sha256: str,
        expected_size_bytes: int,
    ) -> StoredObject: ...


class SignedObjectStorageEventTransport:
    """Commit each signed delivery to one immutable content-identified connector object."""

    def __init__(
        self,
        store: ConnectorObjectStore,
        encoder: SignedEventEncoder,
        *,
        kind: str = "object_storage",
    ) -> None:
        if _KIND.fullmatch(kind) is None:
            raise ValueError("connector kind is invalid")
        self._store = store
        self._encoder = encoder
        self._kind = kind

    def publish(self, event: CloudEventRecord) -> None:
        payload = self._encoder.encode(event)
        draft = event.draft
        root = (
            f"connectors/{self._kind}/{draft.organization_id}/{draft.project_id}/"
            f"{event.id}/{payload.sha256}.json"
        )

        async def commit() -> None:
            staged = await self._store.stage_bytes(
                object_key=f"staging/{root}",
                value=payload.body,
                media_type="application/vnd.cmp.signed-event+json",
            )
            final = await self._store.promote(
                source_key=staged.object_key,
                target_key=f"final/{root}",
                expected_sha256=payload.sha256,
                expected_size_bytes=len(payload.body),
            )
            if final.sha256 != payload.sha256 or final.size_bytes != len(payload.body):
                raise ConnectorDeliveryError("connector object differs from signed delivery")

        try:
            asyncio.run(commit())
        except ConnectorDeliveryError:
            raise
        except Exception as error:
            raise ConnectorDeliveryError("connector object storage is unavailable") from error


__all__ = [
    "ConnectorDeliveryError",
    "ConnectorRejected",
    "SignedEventEncoder",
    "SignedEventPayload",
    "SignedHttpEventTransport",
    "SignedObjectStorageEventTransport",
]
