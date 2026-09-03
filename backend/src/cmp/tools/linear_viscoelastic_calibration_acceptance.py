"""Deterministic non-production setup material for the linear-viscoelastic calibrator.

The live Artifact/Plugin registry transaction is intentionally supplied by the deployment
composition.  This module owns the authority-sensitive part: key validation before any
write, detached signature/SBOM bytes, exact per-role idempotency keys, and a schema-aware
registration envelope that can be handed to the existing T-10/T-17 adapters.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.plugins.application.registry import (
    ActivatePackage,
    ControlPackage,
    PluginRegistryService,
    RegisterPackage,
    RegisterSchema,
)
from cmp.modules.plugins.domain.registry import ArtifactReference, SchemaRole
from cmp.shared.domain.revisions import content_sha256

try:
    from scripts.build_linear_viscoelastic_calibrator import build_package
except ModuleNotFoundError:  # Installed backend package; repository scripts are not a package.
    _builder_path = (
        Path(__file__).resolve().parents[4] / "scripts" / "build_linear_viscoelastic_calibrator.py"
    )
    _builder_spec = importlib.util.spec_from_file_location("cmp_lve_package_builder", _builder_path)
    if _builder_spec is None or _builder_spec.loader is None:
        raise RuntimeError("linear-viscoelastic package builder is unavailable") from None
    _builder_module = importlib.util.module_from_spec(_builder_spec)
    _builder_spec.loader.exec_module(_builder_module)
    build_package = _builder_module.build_package

PLUGIN_ID = "cmp.linear_viscoelastic.calibrator"
PLUGIN_VERSION = "1.0.2"
SIGNATURE_SCHEMA_ID = "urn:cmp:artifact:detached-signature:1.0.0"
SIGNATURE_PAYLOAD_PREFIX = "cmp-plugin-package-sha256-v1"
IDEMPOTENCY_PREFIX = "linear-viscoelastic-calibrator:1.0.2"


class AcceptanceArtifactPublisher(Protocol):
    """Publish one exact payload through the deployment's normal Artifact boundary."""

    def publish(
        self,
        *,
        role: str,
        payload: bytes,
        media_type: str,
        expected_sha256: str,
        idempotency_key: str,
    ) -> ArtifactReference: ...


def private_key_from_environment(environ: dict[str, str] | None = None) -> Ed25519PrivateKey:
    """Validate the ephemeral acceptance key before callers perform a write."""

    values = os.environ if environ is None else environ
    raw = values.get("CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64")
    if raw is None:
        raise RuntimeError("CMP_CALIBRATION_ACCEPTANCE_ED25519_PRIVATE_KEY_B64 is required")
    try:
        key_bytes = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as error:
        raise RuntimeError("CMP calibration acceptance key must be valid base64") from error
    if len(key_bytes) != 32:
        raise RuntimeError("CMP calibration acceptance key must decode to exactly 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(key_bytes)


def detached_signature_document(package_sha256: str, private_key: Ed25519PrivateKey) -> bytes:
    if len(package_sha256) != 64 or any(char not in "0123456789abcdef" for char in package_sha256):
        raise ValueError("package_sha256 must be lowercase SHA-256")
    message = f"{SIGNATURE_PAYLOAD_PREFIX}\n{package_sha256}\n".encode("ascii")
    signature = private_key.sign(message)
    value = {
        "schema_id": SIGNATURE_SCHEMA_ID,
        "schema_version": "1.0.0",
        "algorithm": "ed25519",
        "purpose": SIGNATURE_PAYLOAD_PREFIX,
        "key_status": "non_production_ephemeral",
        "public_key_b64": base64.b64encode(private_key.public_key().public_bytes_raw()).decode(
            "ascii"
        ),
        "signature_b64": base64.b64encode(signature).decode("ascii"),
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def cyclonedx_sbom_document(*, package_sha256: str, dependency_lock_sha256: str) -> bytes:
    """Return deterministic CycloneDX 1.5 JSON with no timestamps or host paths."""

    for name, digest in (
        ("package_sha256", package_sha256),
        ("dependency_lock_sha256", dependency_lock_sha256),
    ):
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"{name} must be lowercase SHA-256")
    value: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": [
            {
                "bom-ref": f"pkg:cmp/{PLUGIN_ID}@{PLUGIN_VERSION}",
                "group": "cmp",
                "name": PLUGIN_ID,
                "version": PLUGIN_VERSION,
                "type": "application",
                "hashes": [{"alg": "SHA-256", "content": package_sha256}],
                "properties": [{"name": "dependency.lock.sha256", "value": dependency_lock_sha256}],
            }
        ],
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def artifact_idempotency_keys(
    package_sha256: str,
    *,
    signature_sha256: str | None = None,
    sbom_sha256: str | None = None,
) -> dict[str, str]:
    """Key every uploaded payload by its own bytes, not only by the package bytes."""

    digests = {
        "package": package_sha256,
        "signature": signature_sha256 or package_sha256,
        "sbom": sbom_sha256 or package_sha256,
    }
    for role, digest in digests.items():
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"{role}_sha256 must be lowercase SHA-256")
    return {role: f"{IDEMPOTENCY_PREFIX}:{digest}:{role}" for role, digest in digests.items()}


def prepare_acceptance_setup(
    *,
    package_root: Path,
    output_directory: Path,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build all setup bytes after key validation and return a write-ready envelope.

    Crucially, key validation is the first operation.  The function performs no file write
    until the key has been decoded and length-checked; callers can then upload each distinct
    Artifact and register/activate them transactionally using the existing services.
    """

    private_key = private_key_from_environment(environ)
    output_directory.mkdir(parents=True, exist_ok=True)
    package_path = output_directory / "linear-viscoelastic-calibrator.zip"
    manifest_path = output_directory / "linear-viscoelastic-calibrator.manifest.json"
    manifest = build_package(package_root, package_path, manifest_path)
    package_payload = package_path.read_bytes()
    package_sha256 = hashlib.sha256(package_payload).hexdigest()
    lock_sha256 = hashlib.sha256((package_root / "dependency.lock").read_bytes()).hexdigest()
    signature_payload = detached_signature_document(package_sha256, private_key)
    sbom_payload = cyclonedx_sbom_document(
        package_sha256=package_sha256,
        dependency_lock_sha256=lock_sha256,
    )
    # These are deliberately separate files/Artifact payloads; no manifest self-reference.
    signature_path = output_directory / "linear-viscoelastic-calibrator.signature.json"
    sbom_path = output_directory / "linear-viscoelastic-calibrator.sbom.json"
    signature_path.write_bytes(signature_payload)
    sbom_path.write_bytes(sbom_payload)
    signature_sha256 = hashlib.sha256(signature_payload).hexdigest()
    sbom_sha256 = hashlib.sha256(sbom_payload).hexdigest()
    return {
        "manifest": manifest,
        "package_sha256": package_sha256,
        "dependency_lock_sha256": lock_sha256,
        "signature_sha256": signature_sha256,
        "sbom_sha256": sbom_sha256,
        "idempotency_keys": artifact_idempotency_keys(
            package_sha256,
            signature_sha256=signature_sha256,
            sbom_sha256=sbom_sha256,
        ),
        "paths": {
            "package": str(package_path),
            "manifest": str(manifest_path),
            "signature": str(signature_path),
            "sbom": str(sbom_path),
        },
        "non_production": True,
        "verification_reason": "non-production backend acceptance",
        "activation": "tenant_project",
    }


def _schema_registrations(package_root: Path) -> tuple[RegisterSchema, ...]:
    values = (
        ("config.schema.json", SchemaRole.CONFIG),
        ("run-result.schema.json", SchemaRole.OUTPUT),
        ("objective-history.schema.json", SchemaRole.EVIDENCE),
        ("response-residuals.schema.json", SchemaRole.EVIDENCE),
    )
    result: list[RegisterSchema] = []
    for file_name, role in values:
        document = json.loads((package_root / "schemas" / file_name).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("$id"), str):
            raise RuntimeError(f"{file_name} must be a schema object with an exact $id")
        result.append(
            RegisterSchema(
                schema_id=str(document["$id"]),
                extension_ordinal=1,
                role=role,
                document=document,
                sha256=content_sha256(document),
            )
        )
    return tuple(result)


def register_activate_and_read_back(
    *,
    context: SecurityContext,
    submit_decision: AuthorizationDecision,
    activate_decision: AuthorizationDecision,
    read_decision: AuthorizationDecision,
    registry: PluginRegistryService,
    artifacts: AcceptanceArtifactPublisher,
    package_root: Path,
    output_directory: Path,
    classification: DataClassification = DataClassification.INTERNAL,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the bounded package admission proof after validating the caller seed.

    Missing or malformed Ed25519 input fails in ``prepare_acceptance_setup`` before the
    publisher or registry can be called.  Successful execution uses the normal Artifact and
    Plugin Registry boundaries, verifies eligibility, activates the exact digest, and reads it
    back both by package ID and by active plugin identity.
    """

    setup = prepare_acceptance_setup(
        package_root=package_root,
        output_directory=output_directory,
        environ=environ,
    )
    paths = setup["paths"]
    idempotency_keys = setup["idempotency_keys"]
    if not isinstance(paths, dict) or not isinstance(idempotency_keys, dict):
        raise RuntimeError("acceptance setup returned an invalid payload envelope")
    media_types = {
        "package": "application/zip",
        "signature": "application/vnd.cmp.detached-signature+json",
        "sbom": "application/vnd.cyclonedx+json",
    }
    expected_hashes = {
        "package": str(setup["package_sha256"]),
        "signature": str(setup["signature_sha256"]),
        "sbom": str(setup["sbom_sha256"]),
    }
    published: dict[str, ArtifactReference] = {}
    for role in ("package", "signature", "sbom"):
        payload = Path(str(paths[role])).read_bytes()
        reference = artifacts.publish(
            role=role,
            payload=payload,
            media_type=media_types[role],
            expected_sha256=expected_hashes[role],
            idempotency_key=str(idempotency_keys[role]),
        )
        if (
            reference.sha256 != expected_hashes[role]
            or reference.size_bytes != len(payload)
            or reference.media_type != media_types[role]
        ):
            raise RuntimeError(f"published {role} Artifact differs from acceptance bytes")
        published[role] = reference
    registered = registry.register(
        context,
        submit_decision,
        RegisterPackage(
            classification=classification,
            manifest=setup["manifest"],
            package_artifact=published["package"],
            signature_artifact=published["signature"],
            sbom_artifact=published["sbom"],
            schemas=_schema_registrations(package_root),
            idempotency_key=(f"{IDEMPOTENCY_PREFIX}:{setup['package_sha256']}:registry"),
        ),
    )
    package_id = registered.package.id
    registry.verify(
        context,
        activate_decision,
        ControlPackage(package_id, "non-production backend acceptance verification"),
    )
    registry.activate(
        context,
        activate_decision,
        ActivatePackage(package_id, "non-production backend acceptance activation"),
    )
    by_id = registry.get(context, read_decision, package_id)
    active = registry.get_active(
        context,
        read_decision,
        plugin_id=PLUGIN_ID,
        plugin_version=PLUGIN_VERSION,
        package_digest=str(setup["package_sha256"]),
    )
    if by_id.id != package_id or active.id != package_id or not by_id.active or not active.active:
        raise RuntimeError("activated calibrator package did not survive exact registry read-back")
    return {
        **setup,
        "package_id": str(package_id),
        "registration_replayed": registered.replayed,
        "state": by_id.state.value,
        "active": True,
        "artifact_ids": {role: str(reference.artifact_id) for role, reference in published.items()},
        "schema_sha256": {schema.schema_id: schema.sha256 for schema in by_id.schemas},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("plugins/production/linear_viscoelastic_calibrator"),
    )
    parser.add_argument(
        "--output-directory", type=Path, default=Path("dist/linear-viscoelastic-acceptance")
    )
    args = parser.parse_args(argv)
    payload = prepare_acceptance_setup(
        package_root=args.package_root.resolve(), output_directory=args.output_directory.resolve()
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
