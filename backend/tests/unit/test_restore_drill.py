import hashlib
from pathlib import Path

import pytest
from cmp.tools.restore_drill import (
    ObjectEvidence,
    RestoreDrillError,
    _release_sample_status,
    verify_objects,
)


def _stored_path(root: Path, key: str) -> Path:
    path = (root / "objects").joinpath(*key.split("/")).with_suffix(".blob")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_manifest_verifier_accepts_exact_restored_bytes(tmp_path: Path) -> None:
    payload = b"immutable material evidence\n"
    path = _stored_path(tmp_path, "sha256/ab/example.data")
    path.write_bytes(payload)
    evidence = ObjectEvidence(
        "raw_asset",
        "raw-1",
        "sha256/ab/example.data",
        hashlib.sha256(payload).hexdigest(),
        len(payload),
    )

    result = verify_objects(tmp_path, (evidence,))

    assert result[0].status == "verified"
    assert result[0].observed_sha256 == evidence.sha256


def test_manifest_verifier_reports_missing_and_mismatch(tmp_path: Path) -> None:
    (tmp_path / "objects").mkdir()
    mismatch = _stored_path(tmp_path, "sha256/ab/mismatch")
    mismatch.write_bytes(b"changed")
    expected = hashlib.sha256(b"expected").hexdigest()

    result = verify_objects(
        tmp_path,
        (
            ObjectEvidence("artifact", "one", "sha256/ab/missing", expected, 8),
            ObjectEvidence("artifact", "two", "sha256/ab/mismatch", expected, 8),
        ),
    )

    assert [item.status for item in result] == ["missing", "mismatch"]


@pytest.mark.parametrize("key", ("../escape", "/absolute", "safe/../../escape", "bad\\key"))
def test_manifest_verifier_rejects_unsafe_storage_key(tmp_path: Path, key: str) -> None:
    (tmp_path / "objects").mkdir()
    evidence = ObjectEvidence("artifact", "one", key, "0" * 64, 0)

    with pytest.raises(RestoreDrillError, match=r"unsafe|forbidden"):
        verify_objects(tmp_path, (evidence,))


def test_release_sample_requires_evidence_when_a_release_exists() -> None:
    assert _release_sample_status(release_count=0, verified_artifacts=0) == (
        "not_present_in_source"
    )
    assert _release_sample_status(release_count=1, verified_artifacts=0) == (
        "release_has_no_verified_artifact"
    )
    assert _release_sample_status(release_count=1, verified_artifacts=2) == "verified"
