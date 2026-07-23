"""Single deterministic Codex PreToolUse publication gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from cmp.tools.documentation_impact import verify_documentation_impact
from cmp.tools.pre_publish import (
    classify_command,
    resolve_publication_target,
    run_pre_publish_pipeline,
)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _deny(reason: str) -> None:
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


def _documentation_reason(project: Path, mode: str) -> str | None:
    try:
        verify_documentation_impact(project, cast(Any, mode))
    except Exception as error:
        return (
            f"Documentation gate failed ({mode}): {error}. Update required current documentation "
            "evidence and run `make docs-screenshots` plus `make docs-impact`."
        )
    return None


def evaluate(payload: object, project: Path) -> str | None:
    data = _mapping(payload)
    event_name = str(data.get("hook_event_name", data.get("hookEventName", "")))
    if event_name != "PreToolUse":
        return None
    command = str(_mapping(data.get("tool_input")).get("command", ""))
    command_kind = classify_command(command)
    if command_kind == "ordinary":
        return None
    if command_kind == "commit-and-publish":
        return (
            "Commit and publish commands must be run separately. The independent reviewer can only "
            "review the committed origin/main...HEAD diff, not a future commit in the same shell "
            "command."
        )
    if command_kind == "commit":
        return _documentation_reason(project, "staged")
    try:
        target = resolve_publication_target(project, command)
        run_pre_publish_pipeline(
            project,
            independent_reviews=False,
            emit=lambda message: print(message, file=sys.stderr),
            publication_target=target,
        )
        if target is not None and resolve_publication_target(project, command) != target:
            return "Target PR head/base changed during review; rerun the publication command."
    except Exception as error:
        detail = getattr(error, "detail_path", None)
        suffix = f" Detailed result: {detail}." if detail else ""
        return f"Pre-publish review gate failed: {error}.{suffix}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError) as error:
        _deny(f"Pre-publish hook input is invalid: {error}")
        return 0
    project = Path(__file__).resolve().parents[2]
    reason = evaluate(payload, project)
    if reason:
        _deny(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
