"""Replay provenance helpers for the bounded linear-viscoelastic worker.

The digest format here is deliberately independent of Git archive metadata and file mtimes.
It is used as evidence only; it does not permit a caller to override container detection or
silently substitute an image for an OCI execution.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import struct
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

BUILD_PROVENANCE_RULE_VERSION = "cmp_python_package_tree_sha256@1.0.0"


def _regular_package_files(root: Path) -> tuple[tuple[str, Path], ...]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("package root must be a real directory")
    values: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError(f"package tree cannot contain symlinks: {relative}")
        if path.is_dir():
            continue
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if not path.is_file():
            raise ValueError(f"package tree member is not a regular file: {relative}")
        name = PurePosixPath(*relative.parts).as_posix()
        name.encode("utf-8")
        values.append((name, path))
    return tuple(sorted(values, key=lambda item: item[0].encode("utf-8")))


def cmp_python_package_tree_sha256(root: Path) -> str:
    """Hash UTF-8 POSIX paths and contents with explicit uint64 lengths."""

    digest = hashlib.sha256()
    digest.update(BUILD_PROVENANCE_RULE_VERSION.encode("ascii") + b"\n")
    for name, path in _regular_package_files(root):
        encoded = name.encode("utf-8")
        content = path.read_bytes()
        digest.update(struct.pack(">Q", len(encoded)))
        digest.update(encoded)
        digest.update(struct.pack(">Q", len(content)))
        digest.update(content)
    return digest.hexdigest()


def _oci_detected() -> tuple[bool, tuple[str, ...]]:
    markers: list[str] = []
    if Path("/.dockerenv").is_file():
        markers.append("/.dockerenv")
    if Path("/run/.containerenv").is_file():
        markers.append("/run/.containerenv")
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8", errors="replace")
    except OSError:
        cgroup = ""
    if any(token in cgroup.lower() for token in ("docker", "containerd", "kubepods", "libpod")):
        markers.append("/proc/1/cgroup")
    return bool(markers), tuple(markers)


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


@dataclass(frozen=True, slots=True)
class BuildProvenance:
    source_commit: str
    uv_lock_sha256: str
    cmp_package_tree_sha256: str
    execution_environment_digest: str
    execution_environment: dict[str, Any]
    versions: dict[str, str | None]

    def canonical(self) -> dict[str, Any]:
        return {
            "source_commit": self.source_commit,
            "uv_lock_sha256": self.uv_lock_sha256,
            "cmp_package_tree_sha256": self.cmp_package_tree_sha256,
            "cmp_package_tree_rule_version": BUILD_PROVENANCE_RULE_VERSION,
            "execution_environment_digest": self.execution_environment_digest,
            "execution_environment": dict(self.execution_environment),
            "versions": dict(self.versions),
        }


def build_provenance(
    *,
    repository_root: Path,
    package_root: Path,
    environment: dict[str, str] | None = None,
) -> BuildProvenance:
    """Capture source/dependency/package/runtime evidence for one execution.

    OCI status is detected from host markers/cgroups.  ``CMP_CONTAINER_IMAGE_DIGEST`` is
    accepted only as required evidence after detection; it never forces OCI status.
    """

    values = os.environ if environment is None else environment
    source_commit = values.get("CMP_SOURCE_COMMIT")
    if not source_commit:
        raise RuntimeError("CMP_SOURCE_COMMIT is required for calibration provenance")
    lock = repository_root / "uv.lock"
    if not lock.is_file() or lock.is_symlink():
        raise RuntimeError("uv.lock is required for calibration provenance")
    uv_lock_sha256 = hashlib.sha256(lock.read_bytes()).hexdigest()
    oci, markers = _oci_detected()
    image_digest = values.get("CMP_CONTAINER_IMAGE_DIGEST")
    if oci and (
        image_digest is None
        or len(image_digest) != 71
        or not image_digest.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in image_digest[7:])
    ):
        raise RuntimeError("CMP_CONTAINER_IMAGE_DIGEST is required for OCI execution")
    environment_document: dict[str, Any] = {
        "oci": oci,
        "container_markers": list(markers),
        "container_image_digest": image_digest if oci else None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    environment_digest = hashlib.sha256(
        json.dumps(
            environment_document, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()
    versions = {
        package: _version(package)
        for package in ("cae-material-platform", "numpy", "scipy", "pyarrow", "pydantic")
    }
    return BuildProvenance(
        source_commit=source_commit,
        uv_lock_sha256=uv_lock_sha256,
        cmp_package_tree_sha256=cmp_python_package_tree_sha256(package_root),
        execution_environment_digest=environment_digest,
        execution_environment=environment_document,
        versions=versions,
    )
