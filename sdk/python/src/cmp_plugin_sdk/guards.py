"""Best-effort developer-runner guards; OCI policy remains the production boundary."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn


class DevelopmentSandboxViolation(PermissionError):
    """Reviewed development plugin attempted a forbidden ambient capability."""


def _deny(message: str) -> NoReturn:
    raise DevelopmentSandboxViolation(message)


def _network_denied(*args: object, **kwargs: object) -> NoReturn:
    del args, kwargs
    _deny("network access is denied by the local plugin runner")


def _process_denied(*args: object, **kwargs: object) -> NoReturn:
    del args, kwargs
    _deny("child process creation is denied by the local plugin runner")


def _resolved_roots(values: tuple[Path, ...]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for value in values:
        try:
            resolved = value.resolve(strict=True)
        except OSError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    return tuple(roots)


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def install_development_guards(
    *,
    package_root: Path,
    input_root: Path,
    output_root: Path,
    workspace_root: Path,
) -> None:
    """Deny common network/process/path escapes for reviewed non-production fixtures.

    Python audit hooks are defense in depth, not a substitute for a non-root, network-none OCI
    sandbox. The production adapter refuses runtimes that do not attest those controls.
    """

    # Editable development installs can place the entire application source tree on
    # ``sys.path``. Only the interpreter environments and this SDK package are library
    # roots; arbitrary import search paths must not become filesystem capabilities.
    library_candidates = [
        Path(sys.base_prefix),
        Path(sys.prefix),
        Path(__file__).resolve().parent,
    ]
    read_roots = _resolved_roots(
        (package_root, input_root, output_root, workspace_root, *library_candidates)
    )
    write_roots = _resolved_roots((output_root, workspace_root))

    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket."):
            _deny("network access is denied by the local plugin runner")
        if event in {
            "subprocess.Popen",
            "os.system",
            "os.posix_spawn",
            "os.posix_spawnp",
            "pty.spawn",
        } or event.startswith("os.spawn"):
            _deny("child process creation is denied by the local plugin runner")
        if event in {"os.symlink", "os.link"}:
            _deny("link creation is denied by the local plugin runner")
        if event != "open" or not args or isinstance(args[0], int):
            return
        raw_path = args[0]
        if not isinstance(raw_path, (str, bytes, os.PathLike)):
            _deny("runner received an invalid filesystem path")
        path = Path(os.fsdecode(raw_path)).resolve(strict=False)
        mode = args[1] if len(args) > 1 else "r"
        flags = args[2] if len(args) > 2 else 0
        writing = (
            isinstance(mode, str)
            and any(marker in mode for marker in ("w", "a", "x", "+"))
        ) or (
            isinstance(flags, int)
            and bool(
                flags
                & (
                    os.O_WRONLY
                    | os.O_RDWR
                    | os.O_CREAT
                    | os.O_TRUNC
                    | os.O_APPEND
                )
            )
        )
        allowed = write_roots if writing else read_roots
        if not _inside(path, allowed):
            _deny("filesystem access escapes the local plugin sandbox")

    sys.addaudithook(audit)
    patches = (
        (socket, "socket", _network_denied),
        (socket, "create_connection", _network_denied),
        (socket, "getaddrinfo", _network_denied),
        (subprocess, "Popen", _process_denied),
        (subprocess, "run", _process_denied),
        (subprocess, "call", _process_denied),
        (subprocess, "check_call", _process_denied),
        (subprocess, "check_output", _process_denied),
        (os, "system", _process_denied),
    )
    for target, name, replacement in patches:
        setattr(target, name, replacement)
