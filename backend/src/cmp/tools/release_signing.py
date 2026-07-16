"""Local and external signer adapters for canonical release-quality manifests."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cmp.shared.domain.revisions import canonical_json_bytes

_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}$")
_PROVIDER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_RESPONSE_BYTES = 64 * 1024


class ExternalSigningError(RuntimeError):
    """An external signing identity or signature failed closed."""


@dataclass(frozen=True, slots=True)
class SignerIdentity:
    algorithm: str
    key_id: str
    provider: str
    public_key_pem: bytes

    def __post_init__(self) -> None:
        if self.algorithm != "Ed25519":
            raise ExternalSigningError("signer algorithm must be Ed25519")
        if _KEY_ID.fullmatch(self.key_id) is None:
            raise ExternalSigningError("signer key identity is invalid")
        if _PROVIDER.fullmatch(self.provider) is None:
            raise ExternalSigningError("signer provider identity is invalid")
        canonical_public_key(self.public_key_pem)


class ManifestSigner(Protocol):
    def identity(self) -> SignerIdentity: ...

    def sign(self, payload: bytes) -> bytes: ...


def canonical_public_key(value: bytes) -> bytes:
    """Validate and canonicalize an Ed25519 public key as SubjectPublicKeyInfo PEM."""

    try:
        key = serialization.load_pem_public_key(value)
    except (ValueError, TypeError) as error:
        raise ExternalSigningError("trusted public key is not valid PEM") from error
    if not isinstance(key, Ed25519PublicKey):
        raise ExternalSigningError("trusted public key is not Ed25519")
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


class LocalEd25519Signer:
    """Compatibility signer for development evidence, never a production identity claim."""

    def __init__(self, private_key: Ed25519PrivateKey, *, mode: str) -> None:
        if mode not in {"ephemeral_local", "supplied_ed25519_key"}:
            raise ValueError("local signing mode is invalid")
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._private_key = private_key
        self._identity = SignerIdentity(
            algorithm="Ed25519",
            key_id=f"local:{hashlib.sha256(public_key).hexdigest()}",
            provider=mode,
            public_key_pem=public_key,
        )

    def identity(self) -> SignerIdentity:
        return self._identity

    def sign(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)


class ExternalCommandSigner:
    """Invoke a no-shell signer process while retaining public-key verification locally."""

    def __init__(
        self,
        command: tuple[str, ...],
        *,
        trusted_public_key: bytes,
        expected_key_id: str,
        timeout_seconds: float = 30.0,
        cwd: Path | None = None,
    ) -> None:
        if not command or not command[0].strip() or any("\x00" in item for item in command):
            raise ExternalSigningError("external signer command is invalid")
        if _KEY_ID.fullmatch(expected_key_id) is None:
            raise ExternalSigningError("expected signer key identity is invalid")
        if not 0 < timeout_seconds <= 300:
            raise ExternalSigningError("external signer timeout must be between 0 and 300 seconds")
        executable = shutil.which(command[0]) or command[0]
        self._command = (executable, *command[1:])
        self._trusted_public_key = canonical_public_key(trusted_public_key)
        self._expected_key_id = expected_key_id
        self._timeout_seconds = timeout_seconds
        self._cwd = cwd
        self._identity = self._describe()

    def identity(self) -> SignerIdentity:
        return self._identity

    def sign(self, payload: bytes) -> bytes:
        digest = hashlib.sha256(payload).hexdigest()
        response = self._invoke(
            {
                "algorithm": self._identity.algorithm,
                "key_id": self._identity.key_id,
                "operation": "sign",
                "payload_base64": base64.b64encode(payload).decode("ascii"),
                "payload_sha256": digest,
                "schema": "cmp.external-signing-request.v1",
            }
        )
        self._require_response(response, operation="sign")
        if response.get("algorithm") != self._identity.algorithm:
            raise ExternalSigningError("external signer changed algorithm")
        if response.get("key_id") != self._identity.key_id:
            raise ExternalSigningError("external signer changed key identity")
        if response.get("payload_sha256") != digest:
            raise ExternalSigningError("external signer did not attest the requested payload")
        encoded = response.get("signature_base64")
        if not isinstance(encoded, str):
            raise ExternalSigningError("external signer omitted signature")
        try:
            signature = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ExternalSigningError("external signer returned malformed signature") from error
        try:
            key = serialization.load_pem_public_key(self._identity.public_key_pem)
            if not isinstance(key, Ed25519PublicKey):
                raise ExternalSigningError("external signer public key changed type")
            key.verify(signature, payload)
        except (InvalidSignature, ValueError, TypeError) as error:
            raise ExternalSigningError(
                "external signature failed trusted-key verification"
            ) from error
        return signature

    def _describe(self) -> SignerIdentity:
        response = self._invoke(
            {
                "operation": "describe",
                "schema": "cmp.external-signing-request.v1",
            }
        )
        self._require_response(response, operation="describe")
        encoded = response.get("public_key_pem_base64")
        if not isinstance(encoded, str):
            raise ExternalSigningError("external signer omitted public key")
        try:
            public_key = canonical_public_key(base64.b64decode(encoded, validate=True))
        except (binascii.Error, ValueError) as error:
            raise ExternalSigningError("external signer returned malformed public key") from error
        identity = SignerIdentity(
            algorithm=str(response.get("algorithm", "")),
            key_id=str(response.get("key_id", "")),
            provider=str(response.get("provider", "")),
            public_key_pem=public_key,
        )
        if identity.key_id != self._expected_key_id:
            raise ExternalSigningError("external signer key identity is not approved")
        if identity.public_key_pem != self._trusted_public_key:
            raise ExternalSigningError("external signer public key is not approved")
        return identity

    @staticmethod
    def _require_response(response: dict[str, Any], *, operation: str) -> None:
        if response.get("schema") != "cmp.external-signing-response.v1":
            raise ExternalSigningError("external signer response schema is unsupported")
        if response.get("operation") != operation:
            raise ExternalSigningError("external signer response operation is incorrect")

    def _invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        payload = canonical_json_bytes(request) + b"\n"
        try:
            completed = subprocess.run(
                self._command,
                cwd=self._cwd,
                env=os.environ.copy(),
                input=payload,
                capture_output=True,
                timeout=self._timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ExternalSigningError("external signer invocation failed") from error
        if completed.returncode != 0:
            raise ExternalSigningError("external signer rejected the request")
        if not completed.stdout or len(completed.stdout) > _MAX_RESPONSE_BYTES:
            raise ExternalSigningError("external signer response size is invalid")
        try:
            response = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ExternalSigningError("external signer response is not valid JSON") from error
        if not isinstance(response, dict):
            raise ExternalSigningError("external signer response must be a JSON object")
        return response
