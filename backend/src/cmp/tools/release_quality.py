"""Reproducible SBOM, vulnerability, and signed release-quality evidence."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from cmp.shared.domain.revisions import canonical_json_bytes

TRIVY_IMAGE: Final = (
    "aquasec/trivy:0.72.0@sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f"
)
DEFAULT_IMAGES: Final = (
    "api=cmp-local-demo-api:latest",
    "worker=cmp-local-demo-worker:latest",
    "web=cmp-local-demo-web:latest",
    "restore=cmp-local-demo-restore-drill:latest",
)


class ReleaseQualityError(RuntimeError):
    """Release-quality evidence could not be generated or verified safely."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> tuple[str, int]:
    if path.is_symlink() or not path.is_file():
        raise ReleaseQualityError(f"evidence is not a regular file: {path.name}")
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _json_object(raw: str | bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ReleaseQualityError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ReleaseQualityError(f"{label} must be a JSON object")
    return value


def vulnerability_counts(report: Mapping[str, Any]) -> dict[str, int]:
    """Count Trivy findings by severity without trusting absent/invalid fields."""

    counts = {severity: 0 for severity in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL")}
    results = report.get("Results", [])
    if not isinstance(results, list):
        raise ReleaseQualityError("Trivy report Results must be an array")
    for result in results:
        if not isinstance(result, dict):
            raise ReleaseQualityError("Trivy report result must be an object")
        vulnerabilities = result.get("Vulnerabilities", []) or []
        if not isinstance(vulnerabilities, list):
            raise ReleaseQualityError("Trivy Vulnerabilities must be an array")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise ReleaseQualityError("Trivy vulnerability must be an object")
            severity = vulnerability.get("Severity")
            if not isinstance(severity, str):
                raise ReleaseQualityError("Trivy vulnerability severity is missing")
            normalized = severity.upper()
            if normalized not in counts:
                counts["UNKNOWN"] += 1
            else:
                counts[normalized] += 1
    return counts


def _safe_bundle_path(root: Path, relative: str) -> Path:
    if "\\" in relative or "\x00" in relative:
        raise ReleaseQualityError("evidence path contains a forbidden separator")
    posix_path = PurePosixPath(relative)
    if (
        posix_path.is_absolute()
        or not posix_path.parts
        or any(part in {"", ".", ".."} for part in posix_path.parts)
    ):
        raise ReleaseQualityError("evidence path is unsafe")
    candidate = root.joinpath(*posix_path.parts).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ReleaseQualityError("evidence path escapes the bundle") from error
    return candidate


def _public_pem(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ReleaseQualityError("signing key must be an unencrypted Ed25519 PEM key")
    return key


def write_signed_manifest(
    bundle: Path,
    manifest: Mapping[str, Any],
    private_key: Ed25519PrivateKey,
) -> dict[str, Any]:
    """Write a canonical manifest, detached signature, and public verification key."""

    bundle.mkdir(parents=True, exist_ok=True)
    public_pem = _public_pem(private_key.public_key())
    document = dict(manifest)
    document["signature"] = {
        "algorithm": "Ed25519",
        "public_key_sha256": _sha256_bytes(public_pem),
    }
    payload = canonical_json_bytes(document)
    signature = private_key.sign(payload)
    (bundle / "quality-manifest.json").write_bytes(payload)
    (bundle / "quality-manifest.sig").write_text(
        base64.b64encode(signature).decode("ascii") + "\n", encoding="ascii"
    )
    (bundle / "quality-public-key.pem").write_bytes(public_pem)
    return document


def verify_bundle(bundle: Path, *, trusted_public_key: Path | None = None) -> dict[str, Any]:
    """Verify canonical encoding, detached signature, trust key, and every evidence digest."""

    root = bundle.resolve(strict=True)
    manifest_path = root / "quality-manifest.json"
    signature_path = root / "quality-manifest.sig"
    public_key_path = root / "quality-public-key.pem"
    payload = manifest_path.read_bytes()
    document = _json_object(payload, label="quality manifest")
    if canonical_json_bytes(document) != payload:
        raise ReleaseQualityError("quality manifest is not canonical JSON")

    public_pem = public_key_path.read_bytes()
    if trusted_public_key is not None and trusted_public_key.read_bytes() != public_pem:
        raise ReleaseQualityError("bundle public key does not match the trusted public key")
    signature_metadata = document.get("signature")
    if not isinstance(signature_metadata, dict):
        raise ReleaseQualityError("quality manifest signature metadata is missing")
    if signature_metadata.get("algorithm") != "Ed25519":
        raise ReleaseQualityError("quality manifest uses an unsupported signature algorithm")
    if signature_metadata.get("public_key_sha256") != _sha256_bytes(public_pem):
        raise ReleaseQualityError("public key digest does not match the manifest")
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseQualityError("quality public key is not Ed25519")
    try:
        detached = base64.b64decode(
            signature_path.read_text(encoding="ascii").strip(), validate=True
        )
        key.verify(detached, payload)
    except (binascii.Error, InvalidSignature, ValueError, TypeError) as error:
        raise ReleaseQualityError("quality manifest signature is invalid") from error

    evidence = document.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ReleaseQualityError("quality manifest must contain evidence")
    observed_paths: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise ReleaseQualityError("quality evidence entry must be an object")
        relative = item.get("path")
        expected_sha = item.get("sha256")
        expected_size = item.get("size_bytes")
        if not isinstance(relative, str) or relative in observed_paths:
            raise ReleaseQualityError("quality evidence path is missing or duplicated")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ReleaseQualityError("quality evidence digest is malformed")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ReleaseQualityError("quality evidence size is malformed")
        path = _safe_bundle_path(root, relative)
        observed_sha, observed_size = _sha256_file(path)
        if observed_sha != expected_sha or observed_size != expected_size:
            raise ReleaseQualityError(f"quality evidence digest mismatch: {relative}")
        observed_paths.add(relative)
    return document


def _run(
    command: list[str],
    *,
    cwd: Path,
    output: Path | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    executable = shutil.which(command[0]) or command[0]
    completed = subprocess.run(
        [executable, *command[1:]], cwd=cwd, capture_output=True, text=True, check=False
    )
    if output is not None:
        output.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr or completed.stdout).strip().splitlines()[-1:]
        message = detail[0][:500] if detail else "command failed without diagnostics"
        raise ReleaseQualityError(f"release-quality command failed: {message}")
    return completed


def _tool_version(command: list[str], *, cwd: Path) -> str:
    result = _run(command, cwd=cwd)
    return result.stdout.strip().splitlines()[0][:200]


def _parse_images(values: Iterable[str]) -> tuple[tuple[str, str], ...]:
    parsed: list[tuple[str, str]] = []
    names: set[str] = set()
    for value in values:
        name, separator, reference = value.partition("=")
        if not separator or not name.isidentifier() or not reference.strip() or name in names:
            raise ReleaseQualityError(
                "images must use unique python_identifier=container_reference"
            )
        parsed.append((name, reference.strip()))
        names.add(name)
    if not parsed:
        raise ReleaseQualityError("at least one container image is required")
    return tuple(parsed)


def _component(path: Path, *, root: Path, media_type: str) -> dict[str, Any]:
    digest, size = _sha256_file(path)
    relative = path.relative_to(root).as_posix()
    return {"media_type": media_type, "path": relative, "sha256": digest, "size_bytes": size}


def _trivy_command(bundle: Path, *arguments: str) -> list[str]:
    mount = f"{bundle.resolve()}:/evidence"
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        mount,
        "-v",
        "cmp_trivy_cache:/root/.cache/",
        TRIVY_IMAGE,
        *arguments,
    ]


def generate_bundle(
    *,
    workspace: Path,
    bundle: Path,
    images: tuple[tuple[str, str], ...],
    private_key: Ed25519PrivateKey,
    signing_mode: str,
) -> dict[str, Any]:
    """Generate all quality evidence and fail closed on any critical finding."""

    root = workspace.resolve(strict=True)
    output = bundle.resolve(strict=False)
    source_status = _run(["git", "status", "--porcelain"], cwd=root).stdout.strip()
    if source_status:
        raise ReleaseQualityError(
            "release-quality evidence requires a clean working tree; commit or remove changes first"
        )
    output.mkdir(parents=True, exist_ok=False)
    evidence: list[dict[str, Any]] = []

    python_sbom = output / "python-sbom.cdx.json"
    _run(
        [
            "uv",
            "export",
            "--format",
            "cyclonedx1.5",
            "--locked",
            "--no-dev",
            "--output-file",
            str(python_sbom),
        ],
        cwd=root,
    )
    evidence.append(
        _component(python_sbom, root=output, media_type="application/vnd.cyclonedx+json")
    )

    node_sbom = output / "node-sbom.cdx.json"
    _run(
        [
            "npm",
            "sbom",
            "--package-lock-only",
            "--omit=dev",
            "--sbom-format",
            "cyclonedx",
            "--sbom-type",
            "application",
        ],
        cwd=root,
        output=node_sbom,
    )
    evidence.append(_component(node_sbom, root=output, media_type="application/vnd.cyclonedx+json"))

    python_audit = output / "python-vulnerabilities.json"
    python_result = _run(
        ["uv", "audit", "--locked", "--no-dev", "--output-format", "json"],
        cwd=root,
        output=python_audit,
        allow_failure=True,
    )
    python_report = _json_object(python_audit.read_bytes(), label="uv audit report")
    python_vulnerabilities = python_report.get("vulnerabilities")
    if not isinstance(python_vulnerabilities, list):
        raise ReleaseQualityError("uv audit report vulnerabilities must be an array")
    evidence.append(_component(python_audit, root=output, media_type="application/json"))

    node_audit = output / "node-vulnerabilities.json"
    node_result = _run(
        ["npm", "audit", "--json", "--package-lock-only", "--omit=dev"],
        cwd=root,
        output=node_audit,
        allow_failure=True,
    )
    node_report = _json_object(node_audit.read_bytes(), label="npm audit report")
    node_metadata = node_report.get("metadata")
    node_counts = node_metadata.get("vulnerabilities") if isinstance(node_metadata, dict) else None
    if not isinstance(node_counts, dict):
        raise ReleaseQualityError("npm audit vulnerability metadata is missing")
    evidence.append(_component(node_audit, root=output, media_type="application/json"))

    policy_results: dict[str, Any] = {
        "node": {"counts": node_counts, "return_code": node_result.returncode},
        "python": {
            "count": len(python_vulnerabilities),
            "return_code": python_result.returncode,
        },
        "images": {},
    }
    image_targets: list[dict[str, str]] = []
    for name, reference in images:
        inspect = _run(["docker", "image", "inspect", "--format", "{{.Id}}", reference], cwd=root)
        image_id = inspect.stdout.strip()
        image_targets.append({"image_id": image_id, "name": name, "reference": reference})
        sbom = output / f"{name}-image-sbom.cdx.json"
        _run(
            _trivy_command(
                output,
                "image",
                "--format",
                "cyclonedx",
                "--output",
                f"/evidence/{sbom.name}",
                reference,
            ),
            cwd=root,
        )
        evidence.append(_component(sbom, root=output, media_type="application/vnd.cyclonedx+json"))
        vulnerability_report = output / f"{name}-image-vulnerabilities.json"
        _run(
            _trivy_command(
                output,
                "image",
                "--scanners",
                "vuln",
                "--severity",
                "HIGH,CRITICAL",
                "--format",
                "json",
                "--output",
                f"/evidence/{vulnerability_report.name}",
                reference,
            ),
            cwd=root,
        )
        image_report = _json_object(vulnerability_report.read_bytes(), label=f"{name} Trivy report")
        counts = vulnerability_counts(image_report)
        policy_results["images"][name] = {"counts": counts, "image_id": image_id}
        evidence.append(
            _component(vulnerability_report, root=output, media_type="application/json")
        )

    critical = int(node_counts.get("critical", 0))
    critical += sum(
        int(result["counts"]["CRITICAL"]) for result in policy_results["images"].values()
    )
    blocking_findings = critical + len(python_vulnerabilities)
    passed = (
        blocking_findings == 0
        and python_result.returncode == 0
        and node_result.returncode == 0
    )
    manifest: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "evidence": sorted(evidence, key=lambda item: str(item["path"])),
        "images": image_targets,
        "policy": {
            "blocking_findings": blocking_findings,
            "critical_vulnerability_limit": 0,
            "known_python_vulnerability_limit": 0,
            "observed_critical_vulnerabilities": critical,
            "passed": passed,
            "results": policy_results,
        },
        "schema": "cmp.release-quality-manifest.v1",
        "signing_mode": signing_mode,
        "source_commit": _run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip(),
        "tools": {
            "docker": _tool_version(["docker", "--version"], cwd=root),
            "npm": _tool_version(["npm", "--version"], cwd=root),
            "trivy": TRIVY_IMAGE,
            "uv": _tool_version(["uv", "--version"], cwd=root),
        },
    }
    document = write_signed_manifest(output, manifest, private_key)
    verify_bundle(output)
    if not passed:
        raise ReleaseQualityError(
            f"release-quality policy failed with {blocking_findings} blocking findings"
        )
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="generate and sign release-quality evidence")
    generate.add_argument("--root", type=Path, default=Path.cwd())
    generate.add_argument("--output", type=Path)
    generate.add_argument("--image", action="append", default=[])
    signing = generate.add_mutually_exclusive_group(required=True)
    signing.add_argument("--private-key", type=Path)
    signing.add_argument("--ephemeral-local-key", action="store_true")
    verify = commands.add_parser("verify", help="verify a signed quality evidence bundle")
    verify.add_argument("--bundle", type=Path, required=True)
    verify.add_argument("--trusted-public-key", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "verify":
        document = verify_bundle(args.bundle, trusted_public_key=args.trusted_public_key)
        print(json.dumps({"passed": True, "source_commit": document["source_commit"]}))
        return
    root: Path = args.root
    output: Path = args.output or (
        root / ".cache" / "release-quality" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    private_key = (
        _load_private_key(args.private_key)
        if args.private_key is not None
        else Ed25519PrivateKey.generate()
    )
    signing_mode = "supplied_ed25519_key" if args.private_key is not None else "ephemeral_local"
    document = generate_bundle(
        workspace=root,
        bundle=output,
        images=_parse_images(args.image or DEFAULT_IMAGES),
        private_key=private_key,
        signing_mode=signing_mode,
    )
    print(
        json.dumps(
            {
                "bundle": os.fspath(output.resolve()),
                "critical_vulnerabilities": document["policy"]["observed_critical_vulnerabilities"],
                "passed": document["policy"]["passed"],
                "signing_mode": signing_mode,
            }
        )
    )


if __name__ == "__main__":
    main()
