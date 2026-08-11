"""Build the structured visual-evidence manifest for issue #184."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

BASELINE_COMMIT = "36e8312fa85253ad8fee88f63a3a4bf096d92a9c"
VIEWPORT_PATTERN = re.compile(r"(?P<width>\d{4})x(?P<height>\d{3,4})")
NEW_CAPTURE_METADATA = {
    "administration-access-role-control-1366x768.png": {
        "route": "/administration/access",
        "workflow": "role-control-keyboard-and-selected-state",
        "fixture": "Administrator role preset",
    },
    "modeling-data-invalid-scrolled-1440x900.png": {
        "route": "/modeling?stage=data&family=metal",
        "workflow": "invalid-mapping-local-scroll-and-recovery",
        "fixture": "synthetic DP780 invalid column mapping",
    },
    "modeling-process-manual-1366x768.png": {
        "route": "/modeling?stage=process&family=metal",
        "workflow": "manual-process-local-scroll-and-save-reachability",
        "fixture": "synthetic DP780 manual process setup",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_capture_metadata(path: Path) -> dict[str, dict[str, Any]]:
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    captures = content.get("captures", []) if isinstance(content, dict) else []
    result = {
        Path(str(item["image"])).name: {
            "route": item.get("route", "unregistered"),
            "workflow": item.get("workflow", "unregistered"),
            "fixture": item.get("fixture", "unregistered"),
        }
        for item in captures
        if isinstance(item, dict) and item.get("image")
    }
    result.update(NEW_CAPTURE_METADATA)
    return result


def _viewport_from_name(name: str) -> str | None:
    match = VIEWPORT_PATTERN.search(name)
    if not match:
        return None
    return f"{match.group('width')}x{match.group('height')}"


def _state_fingerprint(metadata: dict[str, Any], name: str) -> str:
    state = {
        "route": metadata.get("route"),
        "workflow": metadata.get("workflow"),
        "fixture": metadata.get("fixture"),
        "capture_name": name,
    }
    encoded = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _image_record(
    path: Path,
    *,
    root: Path,
    capture_commit: str,
    phase: str,
    density: str,
    metadata: dict[str, Any],
    browser_zoom_percent: int = 100,
    dpr: int = 1,
    css_viewport: str | None = None,
    outer_viewport: str | None = None,
    surface: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
    viewport = css_viewport or _viewport_from_name(path.name)
    return {
        "path": _repo_path(path, root),
        "phase": phase,
        "route": metadata.get("route", "unregistered"),
        "workflow": metadata.get("workflow", "unregistered"),
        "fixture": metadata.get("fixture", "unregistered"),
        "surface": surface,
        "source": source,
        "capture_commit": capture_commit,
        "viewport": viewport,
        "outer_viewport": outer_viewport or viewport,
        "browser_zoom_percent": browser_zoom_percent,
        "dpr": dpr,
        "density": density,
        "original_pixels": {"width": width, "height": height},
        "sha256": _sha256(path),
        "state_fingerprint": _state_fingerprint(metadata, path.name),
        "geometry_gate": "BASELINE" if phase == "before" else "PASS",
    }


def _load_submanifest(path: Path, root: Path) -> dict[str, dict[str, Any]]:
    content = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for item in content.get("images", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        item_path = Path(str(item["path"]))
        try:
            key = item_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            key = item_path.as_posix()
        result[key] = item
    return result


def _full_screen_records(
    evidence_root: Path,
    *,
    root: Path,
    capture_commit: str,
    capture_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    before = evidence_root / "before"
    for path in sorted(before.glob("*.png")):
        metadata = capture_metadata.get(path.name, {"route": "unregistered"})
        records.append(
            _image_record(
                path,
                root=root,
                capture_commit=BASELINE_COMMIT,
                phase="before",
                density="pre-P2",
                metadata=metadata,
            )
        )
    for density in ("compact", "standard", "large"):
        directory = evidence_root / "after" / density
        for path in sorted(directory.glob("*.png")):
            metadata = capture_metadata.get(path.name, {"route": "unregistered"})
            records.append(
                _image_record(
                    path,
                    root=root,
                    capture_commit=capture_commit,
                    phase="after",
                    density=density,
                    metadata=metadata,
                )
            )
    return records


def _supplemental_records(
    evidence_root: Path,
    *,
    root: Path,
    capture_commit: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for kind, density in (("crops", "standard"), ("zoom-200", "standard")):
        directory = evidence_root / kind
        submanifest = _load_submanifest(directory / "manifest.json", root)
        for path in sorted(directory.rglob("*.png")):
            key = _repo_path(path, root)
            source = submanifest.get(key, {})
            surface = str(source.get("surface", path.stem))
            route = str(source.get("source", "unregistered")).split("@", 1)[0]
            if route.startswith("live:"):
                route = route.removeprefix("live:")
            metadata = {
                "route": route,
                "workflow": surface,
                "fixture": "issue #184 deterministic synthetic non-production evidence",
            }
            css_viewport = source.get("css_viewport") or source.get("source_viewport")
            outer_viewport = source.get("outer_viewport") or source.get("source_viewport")
            records.append(
                _image_record(
                    path,
                    root=root,
                    capture_commit=capture_commit,
                    phase=kind,
                    density=str(source.get("density", density)),
                    metadata=metadata,
                    browser_zoom_percent=int(source.get("browser_zoom_percent", 100)),
                    dpr=int(source.get("dpr", 1)),
                    css_viewport=str(css_viewport) if css_viewport else None,
                    outer_viewport=str(outer_viewport) if outer_viewport else None,
                    surface=surface,
                    source=str(source.get("source", "live product")),
                )
            )
    return records


def _density_completeness(
    evidence_root: Path, expected: set[str]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for density in ("compact", "standard", "large"):
        found = {path.name for path in (evidence_root / "after" / density).glob("*.png")}
        result[density] = {
            "expected": len(expected),
            "present": len(found & expected),
            "missing": sorted(expected - found),
            "geometry_result": "INCOMPLETE_BASELINE_FIXTURE_BLOCKER"
            if expected - found
            else "PASS",
        }
    return result


def _duplicate_image_allowances(
    root: Path, evidence_root: Path
) -> list[dict[str, Any]]:
    hashes: dict[str, list[str]] = {}
    inventory_roots = (
        root / "docs" / "00-research",
        root / "docs" / "17-evidence" / "images",
        root / "docs" / "user-guide" / "images",
    )
    for inventory_root in inventory_roots:
        if not inventory_root.is_dir():
            continue
        for path in sorted(inventory_root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                hashes.setdefault(_sha256(path), []).append(_repo_path(path, root))
    issue_prefix = _repo_path(evidence_root, root).rstrip("/") + "/"
    return [
        {
            "rationale": (
                "Issue #184 keeps the production-density evidence original and the "
                "byte-identical current-guide copy as separate lifecycle records."
            ),
            "images": sorted(paths),
        }
        for paths in hashes.values()
        if len(paths) > 1 and any(path.startswith(issue_prefix) for path in paths)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=Path(
            "docs/17-evidence/images/issue-184-high-dpi-global-implementation"
        ),
    )
    parser.add_argument(
        "--screenshot-manifest",
        type=Path,
        default=Path("docs/user-guide/screenshot-manifest.yaml"),
    )
    parser.add_argument("--capture-commit", default="PENDING_IMPLEMENTATION_COMMIT")
    args = parser.parse_args()
    root = args.root.resolve()
    evidence_root = (root / args.evidence_root).resolve()
    capture_metadata = _load_capture_metadata(root / args.screenshot_manifest)
    expected = set(capture_metadata)
    images = _full_screen_records(
        evidence_root,
        root=root,
        capture_commit=args.capture_commit,
        capture_metadata=capture_metadata,
    )
    images.extend(
        _supplemental_records(
            evidence_root,
            root=root,
            capture_commit=args.capture_commit,
        )
    )
    route_state_matrix: dict[str, dict[str, list[str]]] = {}
    for image in images:
        if image["phase"] != "after":
            continue
        key = f"{image['route']} | {image['workflow']}"
        route_state_matrix.setdefault(key, {}).setdefault(image["density"], []).append(
            str(image["viewport"])
        )
    for densities in route_state_matrix.values():
        for viewports in densities.values():
            viewports[:] = sorted(set(viewports))
    manifest = {
        "schema_version": 1,
        "issue": 184,
        "policy": "P2",
        "default_density": "standard",
        "allowed_densities": ["compact", "standard", "large"],
        "baseline_commit": BASELINE_COMMIT,
        "capture_commit": args.capture_commit,
        "capture_date": "2026-08-11",
        "browser_zoom_percent": [100, 200],
        "physical_4k_readability": "DEFERRED_TO_223",
        "actual_display": {
            "external_monitor": "2560x1440@59Hz",
            "integrated_display": "2560x1600@165Hz",
            "windows_scale_percent": 100,
            "applied_dpi": 96,
            "actual_3840x2160_monitor_available": False,
        },
        "capture_environment": {
            "compose_project": "cmp-local-demo",
            "browser": "Playwright Chromium",
            "zoom_100_dpr": 1,
            "zoom_200_dpr": 2,
            "synthetic_non_production_data": True,
        },
        "full_screen_density_completeness": _density_completeness(
            evidence_root, expected
        ),
        "known_fixture_blocker": {
            "code": "CMP-CATALOG-0015",
            "affected_after_images_per_density": 10,
            "clean_composition_seed_result": "FAIL_CMP-CATALOG-0004_IMMUTABLE_IDENTITY_CONFLICT",
            "clean_composition_full_demo_result": "FAIL_POLYMER_BULK_ZIP_NOT_GENERATED",
            "verifier_or_data_relaxed": False,
        },
        "route_state_geometry_matrix": route_state_matrix,
        "supplemental_manifests": [
            _repo_path(evidence_root / "crops" / "manifest.json", root),
            _repo_path(evidence_root / "zoom-200" / "manifest.json", root),
        ],
        "allowed_duplicate_groups": _duplicate_image_allowances(root, evidence_root),
        "images": images,
    }
    destination = evidence_root / "visual-evidence.json"
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "path": _repo_path(destination, root),
                "images": len(images),
                "full_screen": sum(
                    image["phase"] in {"before", "after"} for image in images
                ),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
