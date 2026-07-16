"""Rotation-friendly text credentials loaded from atomically replaced files."""

from __future__ import annotations

from pathlib import Path


class RotatingTextFile:
    """Read a bounded token on every call so a sidecar can rotate it without restart."""

    def __init__(self, path: Path, *, maximum_bytes: int = 16 * 1024) -> None:
        if not 64 <= maximum_bytes <= 1024 * 1024:
            raise ValueError("credential maximum_bytes is outside the safe bound")
        self._path = path
        self._maximum_bytes = maximum_bytes

    def __call__(self) -> str:
        if self._path.is_symlink() or not self._path.is_file():
            raise RuntimeError("credential path must be a regular non-symlink file")
        size = self._path.stat().st_size
        if not 1 <= size <= self._maximum_bytes:
            raise RuntimeError("credential file size is outside the safe bound")
        value = self._path.read_bytes()
        if len(value) != size:
            raise RuntimeError("credential changed during read")
        try:
            token = value.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise RuntimeError("credential must be ASCII") from error
        if not token or any(character.isspace() for character in token):
            raise RuntimeError("credential must be one non-empty token")
        return token
