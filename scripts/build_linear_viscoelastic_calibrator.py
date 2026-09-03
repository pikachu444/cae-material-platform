"""Build the deterministic linear-viscoelastic calibrator package and external manifest.

The ZIP is intentionally a tiny allowlisted artifact.  The manifest is emitted separately
so it can contain the package digest without a self-reference and can be registered as a
typed Plugin Package record by the acceptance tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

PLUGIN_ID = "cmp.linear_viscoelastic.calibrator"
PLUGIN_VERSION = "1.0.2"
_ALLOWED = {
    "dependency.lock",
    "linear_viscoelastic_calibrator/plugin.py",
    "schemas/config.schema.json",
    "schemas/run-result.schema.json",
    "schemas/response-residuals.schema.json",
    "schemas/objective-history.schema.json",
}


def _files(root: Path) -> list[tuple[str, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("package root must be a real directory")
    discovered: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        posix = PurePosixPath(*relative.parts).as_posix()
        # Python may leave interpreter cache beside a source file during local checks;
        # caches are never package members and are excluded before allowlist validation.
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"symlink is not allowed in package: {posix}")
        if path.is_dir():
            continue
        if posix not in _ALLOWED:
            raise ValueError(f"unknown package path: {posix}")
        details = path.stat()
        if not stat.S_ISREG(details.st_mode):
            raise ValueError(f"package path is not a regular file: {posix}")
        discovered.append((posix, path))
    if set(item[0] for item in discovered) != _ALLOWED:
        missing = sorted(_ALLOWED - {item[0] for item in discovered})
        raise ValueError(f"required package paths are missing: {missing}")
    return sorted(discovered, key=lambda item: item[0].encode("ascii"))


def package_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for name, path in _files(root):
        encoded = name.encode("ascii")
        payload = path.read_bytes()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def build_package(root: Path, output_zip: Path, manifest_path: Path) -> dict[str, Any]:
    files = _files(root)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as archive:
        archive.comment = b""
        for name, path in files:
            info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.create_version = 10
            info.extract_version = 10
            info.flag_bits = 0
            info.compress_type = zipfile.ZIP_STORED
            info.extra = b""
            info.comment = b""
            info.external_attr = (0o644 & 0xFFFF) << 16
            info.internal_attr = 0
            archive.writestr(info, path.read_bytes())
    package_digest = hashlib.sha256(output_zip.read_bytes()).hexdigest()
    manifest: dict[str, Any] = {
        "manifest_version": "1.0",
        "plugin_id": PLUGIN_ID,
        "display_name": "Linear Viscoelastic Calibrator",
        "plugin_version": PLUGIN_VERSION,
        "package_digest": f"sha256:{package_digest}",
        "contract_api": ">=1.0 <2.0",
        "extensions": [
            {
                "type": "calibrator",
                "entrypoint": "linear_viscoelastic_calibrator.plugin:LinearViscoelasticCalibrator",
                "capabilities": ["generalized-maxwell-shear"],
            }
        ],
        "permissions": {
            "network": "none",
            "artifact_read_roles": [
                "calibration.plan",
                "processing-output.metadata",
                "processing-output.result",
                "test-data.canonical",
                "test-data.normalized",
            ],
            "artifact_write_roles": [
                "calibration.run-result",
                "objective-history",
                "response-residuals",
            ],
        },
        "resources": {"cpu": 2.0, "memory_mb": 4096, "gpu": 0, "timeout_s": 3600},
        "non_production": True,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path("plugins/production/linear_viscoelastic_calibrator")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("dist/linear-viscoelastic-calibrator.zip")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("dist/linear-viscoelastic-calibrator.manifest.json")
    )
    args = parser.parse_args(argv)
    build_package(args.root.resolve(), args.output.resolve(), args.manifest.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
