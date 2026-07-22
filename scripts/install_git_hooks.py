"""Safely install or verify the repository's versioned Git hooks path."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


class HookInstallationError(RuntimeError):
    """Raised when a conflicting or incomplete hook installation is detected."""


def _git(project: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=project,
        check=check,
        capture_output=True,
        text=True,
    )


def repository_root(seed: Path) -> Path:
    return Path(_git(seed.resolve(), "rev-parse", "--show-toplevel").stdout.strip()).resolve()


def verify_hooks(project: Path) -> None:
    root = repository_root(project)
    configured = _git(
        root, "config", "--local", "--get", "core.hooksPath", check=False
    ).stdout.strip()
    if configured != ".githooks":
        raise HookInstallationError(
            f"local core.hooksPath must be exactly .githooks; found {configured or '<unset>'}"
        )
    hook = root / ".githooks" / "pre-push"
    if not hook.is_file():
        raise HookInstallationError("versioned .githooks/pre-push is missing")
    content = hook.read_text(encoding="utf-8")
    required = (
        'uv run cmp-pre-publish --root "$repo_root" --trigger git-pre-push',
        '--remote-name "$1" --remote-location "$2"',
    )
    if any(fragment not in content for fragment in required):
        raise HookInstallationError("pre-push does not call the common pre-publish gate")


def install_hooks(project: Path) -> None:
    root = repository_root(project)
    existing = _git(
        root, "config", "--local", "--get", "core.hooksPath", check=False
    ).stdout.strip()
    if existing and existing != ".githooks":
        raise HookInstallationError(
            "refusing to replace an existing local core.hooksPath "
            f"({existing}); integrate .githooks/pre-push manually"
        )
    _git(root, "config", "--local", "core.hooksPath", ".githooks")
    verify_hooks(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            verify_hooks(args.root)
            action = "verified"
        else:
            install_hooks(args.root)
            action = "installed"
    except (OSError, subprocess.CalledProcessError, HookInstallationError) as error:
        parser.exit(1, f"Git hook installation failed: {error}\n")
    print(f"Git hooks {action}: core.hooksPath=.githooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
