import json
import sys
import textwrap
from pathlib import Path

import pytest
from cmp.tools.release_quality import (
    ReleaseQualityError,
    main,
    verify_bundle,
    vulnerability_counts,
    write_signed_manifest,
)
from cmp.tools.release_signing import ExternalCommandSigner, ExternalSigningError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY_ID = "vault:transit/cmp-release/keys/production-v1"


def _external_signer(
    tmp_path: Path, *, corrupt_signature: bool = False
) -> tuple[ExternalCommandSigner, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "external-private.pem"
    public_path = tmp_path / "trusted-public.pem"
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    script = tmp_path / "fake_external_signer.py"
    script.write_text(
        textwrap.dedent(
            """
            import base64
            import hashlib
            import json
            import sys
            from pathlib import Path
            from cryptography.hazmat.primitives import serialization

            request = json.load(sys.stdin)
            key = serialization.load_pem_private_key(Path(sys.argv[1]).read_bytes(), None)
            public = key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            response = {
                "algorithm": "Ed25519",
                "key_id": "vault:transit/cmp-release/keys/production-v1",
                "operation": request["operation"],
                "schema": "cmp.external-signing-response.v1",
            }
            if request["operation"] == "describe":
                response["provider"] = "test-hsm"
                response["public_key_pem_base64"] = base64.b64encode(public).decode("ascii")
            else:
                payload = base64.b64decode(request["payload_base64"], validate=True)
                signature = key.sign(payload)
                if len(sys.argv) > 2:
                    signature = bytes([signature[0] ^ 1]) + signature[1:]
                response["payload_sha256"] = hashlib.sha256(payload).hexdigest()
                response["signature_base64"] = base64.b64encode(signature).decode("ascii")
            print(json.dumps(response, sort_keys=True, separators=(",", ":")))
            """
        ),
        encoding="utf-8",
    )
    command: tuple[str, ...] = (sys.executable, str(script), str(key_path))
    if corrupt_signature:
        command += ("corrupt",)
    signer = ExternalCommandSigner(
        command,
        trusted_public_key=public_path.read_bytes(),
        expected_key_id=KEY_ID,
        cwd=tmp_path,
    )
    return signer, public_path


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


def test_external_signer_identity_and_signature_are_pinned_and_verified(tmp_path: Path) -> None:
    signer, trusted_public_key = _external_signer(tmp_path / "signer")
    bundle = tmp_path / "bundle"
    evidence = bundle / "evidence.json"
    bundle.mkdir()
    evidence.write_text("{}", encoding="utf-8")
    import hashlib

    document = write_signed_manifest(
        bundle,
        {
            "evidence": [
                {
                    "path": evidence.name,
                    "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
                    "size_bytes": evidence.stat().st_size,
                }
            ],
            "policy": {"passed": True},
            "schema": "cmp.release-quality-manifest.v1",
            "signing_mode": "external_command",
            "source_commit": "b" * 40,
        },
        signer,
    )

    assert document["signature"]["key_id"] == KEY_ID
    assert document["signature"]["provider"] == "test-hsm"
    assert (
        verify_bundle(
            bundle,
            trusted_public_key=trusted_public_key,
            expected_key_id=KEY_ID,
        )
        == document
    )
    with pytest.raises(ReleaseQualityError, match="key identity"):
        verify_bundle(
            bundle,
            trusted_public_key=trusted_public_key,
            expected_key_id="vault:transit/cmp-release/keys/other",
        )


def test_external_signer_rejects_untrusted_or_invalid_signatures(tmp_path: Path) -> None:
    _, approved_public_key = _external_signer(tmp_path / "approved")
    other_root = tmp_path / "other"
    _external_signer(other_root)
    with pytest.raises(ExternalSigningError, match="public key is not approved"):
        ExternalCommandSigner(
            (
                sys.executable,
                str(other_root / "fake_external_signer.py"),
                str(other_root / "external-private.pem"),
            ),
            trusted_public_key=approved_public_key.read_bytes(),
            expected_key_id=KEY_ID,
        )

    corrupt_signer, _ = _external_signer(tmp_path / "corrupt", corrupt_signature=True)
    with pytest.raises(ExternalSigningError, match="trusted-key verification"):
        corrupt_signer.sign(b"canonical manifest")


def test_production_release_quality_rejects_process_local_private_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CMP_ENVIRONMENT", "production")

    with pytest.raises(ReleaseQualityError, match="external signing identity"):
        main(["generate", "--root", str(tmp_path), "--ephemeral-local-key"])


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
