from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_ROOT = (
    ROOT
    / "docs"
    / "17-evidence"
    / "images"
    / "issue-184-high-dpi-global-implementation"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", header[16:24])


def test_issue_184_visual_evidence_paths_hashes_and_dimensions_are_exact() -> None:
    manifest = _load(EVIDENCE_ROOT / "visual-evidence.json")

    assert manifest["policy"] == "P2"
    assert manifest["default_density"] == "standard"
    assert manifest["allowed_densities"] == ["compact", "standard", "large"]
    assert manifest["physical_4k_readability"] == "DEFERRED_TO_223"

    images = manifest["images"]
    assert isinstance(images, list)
    assert len(images) == 334
    for item in images:
        assert isinstance(item, dict)
        relative = str(item["path"])
        assert ".issue-184-" not in relative
        path = ROOT / relative
        assert path.is_file(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        width, height = _png_size(path)
        assert item["original_pixels"] == {"width": width, "height": height}


def test_issue_184_density_matrix_records_the_exact_fixture_boundary() -> None:
    manifest = _load(EVIDENCE_ROOT / "visual-evidence.json")
    completeness = manifest["full_screen_density_completeness"]
    expected_missing = [
        "material-cae-cards-1440x900.png",
        "material-detail-1366x768.png",
        "material-detail-1440x900.png",
        "material-detail-1920x1080.png",
        "material-detail-2560x1440.png",
        "material-detail-3840x2160.png",
        "modeling-export-delivered-1440x900.png",
        "solver-card-preview-1366x768.png",
        "solver-card-preview-1440x900.png",
        "solver-card-preview-1920x1080.png",
    ]
    for density in ("compact", "standard", "large"):
        result = completeness[density]
        assert result == {
            "expected": 90,
            "present": 80,
            "missing": expected_missing,
            "geometry_result": "INCOMPLETE_BASELINE_FIXTURE_BLOCKER",
        }

    blocker = manifest["known_fixture_blocker"]
    assert blocker["verifier_or_data_relaxed"] is False
    assert blocker["clean_composition_seed_result"].startswith("FAIL_")
    assert blocker["clean_composition_full_demo_result"].startswith("FAIL_")


def test_issue_184_crop_manifest_points_to_final_unscaled_files() -> None:
    manifest = _load(EVIDENCE_ROOT / "crops" / "manifest.json")
    assert manifest["resampling"] == "none"
    images = manifest["images"]
    assert len(images) == 21
    for item in images:
        relative = Path(str(item["path"])).resolve().relative_to(ROOT)
        assert relative.parts[:5] == (
            "docs",
            "17-evidence",
            "images",
            "issue-184-high-dpi-global-implementation",
            "crops",
        )
        assert (ROOT / relative).is_file()
