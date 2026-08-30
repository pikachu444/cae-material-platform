"""Package registration primitives for linear-viscoelastic acceptance."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import httpx

from cmp.shared.domain.revisions import content_sha256
from cmp.tools.linear_viscoelastic_acceptance_http import (
    LinearViscoelasticAcceptanceError,
    artifact_reference,
    required_mapping,
    required_string,
    response_json,
    upload_artifact,
)
from cmp.tools.linear_viscoelastic_calibration_acceptance import (
    prepare_acceptance_setup,
)


def register_calibrator(client: httpx.Client, package_root: Path) -> dict[str, Any]:
    """Register, activate, and read back the exact non-production plugin package."""

    with tempfile.TemporaryDirectory(prefix="cmp-lve-acceptance-") as output:
        setup = prepare_acceptance_setup(
            package_root=package_root,
            output_directory=Path(output),
        )
        paths = required_mapping(setup.get("paths"), "acceptance paths")
        digest = required_string(setup.get("package_sha256"), "package_sha256")
        keys = required_mapping(setup.get("idempotency_keys"), "idempotency_keys")
        media_types = {
            "package": "application/zip",
            "signature": "application/vnd.cmp.detached-signature+json",
            "sbom": "application/vnd.cyclonedx+json",
        }
        artifacts = {
            role: upload_artifact(
                client,
                value=Path(required_string(paths.get(role), f"paths.{role}")).read_bytes(),
                filename=f"linear-viscoelastic-calibrator.{role}",
                media_type=media_types[role],
                idempotency_key=keys[role],
            )
            for role in ("package", "signature", "sbom")
        }
        schemas: list[dict[str, Any]] = []
        for filename, role in (
            ("config.schema.json", "config"),
            ("run-result.schema.json", "output"),
            ("objective-history.schema.json", "evidence"),
            ("response-residuals.schema.json", "evidence"),
        ):
            document = json.loads((package_root / "schemas" / filename).read_text("utf-8"))
            if not isinstance(document, dict) or not isinstance(document.get("$id"), str):
                raise LinearViscoelasticAcceptanceError(
                    f"{filename} must be an object with an exact schema id"
                )
            schemas.append(
                {
                    "schema_id": document["$id"],
                    "extension_ordinal": 1,
                    "role": role,
                    "document": document,
                    "sha256": content_sha256(document),
                }
            )
        registered = response_json(
            client.post(
                "/plugins/packages",
                json={
                    "classification": "internal",
                    "manifest": setup["manifest"],
                    "package_artifact": artifact_reference(artifacts["package"]),
                    "signature_artifact": artifact_reference(artifacts["signature"]),
                    "sbom_artifact": artifact_reference(artifacts["sbom"]),
                    "schemas": schemas,
                },
                headers={"Idempotency-Key": f"linear-viscoelastic-calibrator:{digest}:registry"},
            )
        )
        package_id = required_string(registered.get("package_id"), "package_id")
        reason = {"reason": "non-production backend acceptance"}
        response_json(client.post(f"/plugins/packages/{package_id}:verify", json=reason))
        response_json(client.post(f"/plugins/packages/{package_id}:activate", json=reason))
        reloaded = response_json(client.get(f"/plugins/packages/{package_id}"))
        if not reloaded.get("active") or reloaded.get("package_digest") != f"sha256:{digest}":
            raise LinearViscoelasticAcceptanceError(
                "exact calibrator package did not survive API read-back"
            )
        return reloaded
