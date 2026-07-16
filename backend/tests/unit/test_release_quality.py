import json
from pathlib import Path

import pytest
from cmp.tools.release_quality import (
    ReleaseQualityError,
    verify_bundle,
    vulnerability_counts,
    write_signed_manifest,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _bundle(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    evidence = tmp_path / "python-sbom.cdx.json"
    evidence.write_text('{"bomFormat":"CycloneDX"}', encoding="utf-8")
    import hashlib

    payload = evidence.read_bytes()
    write_signed_manifest(
        tmp_path,
        {
            "created_at": "2026-07-16T00:00:00+00:00",
            "evidence": [
                {
                    "media_type": "application/vnd.cyclonedx+json",
                    "path": evidence.name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
            ],
            "policy": {"passed": True},
            "schema": "cmp.release-quality-manifest.v1",
            "signing_mode": "ephemeral_local",
            "source_commit": "a" * 40,
        },
        Ed25519PrivateKey.generate(),
    )
    return tmp_path


def test_signed_quality_bundle_verifies_exact_evidence(tmp_path: Path) -> None:
    document = verify_bundle(_bundle(tmp_path))

    assert document["policy"] == {"passed": True}
    assert document["signature"]["algorithm"] == "Ed25519"


def test_quality_bundle_rejects_evidence_substitution(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "python-sbom.cdx.json").write_text("substituted", encoding="utf-8")

    with pytest.raises(ReleaseQualityError, match="digest mismatch"):
        verify_bundle(bundle)


def test_quality_bundle_rejects_manifest_or_signature_tampering(tmp_path: Path) -> None:
    manifest_bundle = _bundle(tmp_path / "manifest")
    manifest_path = manifest_bundle / "quality-manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["policy"]["passed"] = False
    manifest_path.write_text(
        json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    with pytest.raises(ReleaseQualityError, match="signature is invalid"):
        verify_bundle(manifest_bundle)

    signature_bundle = _bundle(tmp_path / "signature")
    (signature_bundle / "quality-manifest.sig").write_text("AAAA\n", encoding="ascii")
    with pytest.raises(ReleaseQualityError, match="signature is invalid"):
        verify_bundle(signature_bundle)


def test_quality_bundle_requires_configured_trust_key(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    other_bundle = _bundle(tmp_path / "other")

    with pytest.raises(ReleaseQualityError, match="trusted public key"):
        verify_bundle(bundle, trusted_public_key=other_bundle / "quality-public-key.pem")


def test_quality_bundle_rejects_duplicate_evidence_path(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    document = json.loads((bundle / "quality-manifest.json").read_text(encoding="utf-8"))
    document["evidence"].append(dict(document["evidence"][0]))
    for name in ("quality-manifest.json", "quality-manifest.sig", "quality-public-key.pem"):
        (bundle / name).unlink()
    write_signed_manifest(bundle, document, Ed25519PrivateKey.generate())

    with pytest.raises(ReleaseQualityError, match="duplicated"):
        verify_bundle(bundle)


@pytest.mark.parametrize("relative", ("../escape.json", "/absolute.json", "bad\\path.json"))
def test_quality_bundle_rejects_unsafe_evidence_path(tmp_path: Path, relative: str) -> None:
    bundle = _bundle(tmp_path)
    manifest_path = bundle / "quality-manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["evidence"][0]["path"] = relative
    # Re-sign the maliciously structured manifest so path validation, not signature
    # validation, is the boundary under test.
    for name in ("quality-manifest.json", "quality-manifest.sig", "quality-public-key.pem"):
        (bundle / name).unlink()
    write_signed_manifest(bundle, document | {"signature": None}, Ed25519PrivateKey.generate())

    with pytest.raises(ReleaseQualityError, match=r"unsafe|forbidden|escapes"):
        verify_bundle(bundle)


def test_trivy_vulnerability_counts_are_explicit() -> None:
    report = {
        "Results": [
            {
                "Vulnerabilities": [
                    {"Severity": "CRITICAL"},
                    {"Severity": "HIGH"},
                    {"Severity": "future"},
                ]
            },
            {"Vulnerabilities": None},
        ]
    }

    assert vulnerability_counts(report) == {
        "UNKNOWN": 1,
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 1,
        "CRITICAL": 1,
    }
