"""Codex hook adapter for the repository documentation-impact contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, cast

from cmp.tools.documentation_impact import (
    DocumentationImpactError,
    ImpactMode,
    verify_documentation_impact,
)

_COMMIT = re.compile(r"(?:^|[;&|]\s*)git(?:\.exe)?(?:\s+-C\s+\S+)?\s+commit\b", re.IGNORECASE)
_PUBLISH = re.compile(
    r"(?:^|[;&|]\s*)(?:git(?:\.exe)?(?:\s+-C\s+\S+)?\s+push\b|"
    r"gh(?:\.exe)?\s+pr\s+(?:create|merge)\b)",
    re.IGNORECASE,
)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _deny_pre_tool_use(reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )


def _deny_stop(reason: str) -> None:
    print(
        json.dumps(
            {
                "continue": False,
                "stopReason": "Current documentation evidence is incomplete.",
                "systemMessage": reason,
            },
            ensure_ascii=False,
        )
    )


def _verify(project: Path, modes: tuple[ImpactMode, ...]) -> str | None:
    try:
        for mode in modes:
            verify_documentation_impact(project, mode)
    except DocumentationImpactError as error:
        return (
            f"Documentation gate failed ({mode}): {error}. "
            "Update the current guide, screenshot manifest, live PNG, and navigation contract as "
            "required; then run `make docs-screenshots` and `make docs-impact`."
        )
    return None


def main() -> int:
    payload = _mapping(json.load(sys.stdin))
    project = Path(__file__).resolve().parents[2]
    event_name = str(payload.get("hook_event_name", payload.get("hookEventName", "")))

    if event_name == "PreToolUse":
        command = str(_mapping(payload.get("tool_input")).get("command", ""))
        is_commit = bool(_COMMIT.search(command))
        is_publish = bool(_PUBLISH.search(command))
        if not is_commit and not is_publish:
            return 0
        modes: tuple[ImpactMode, ...]
        if is_commit and is_publish:
            modes = ("range", "staged")
        elif is_publish:
            modes = ("range",)
        else:
            modes = ("staged",)
        reason = _verify(project, modes)
        if reason:
            _deny_pre_tool_use(reason)
        return 0

    if event_name == "Stop":
        reason = _verify(project, ("worktree",))
        if reason:
            _deny_stop(reason)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
