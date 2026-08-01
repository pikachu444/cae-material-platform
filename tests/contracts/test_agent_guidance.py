from __future__ import annotations

from pathlib import Path

from cmp.tools.user_guide import _documentation_classes

ROOT = Path(__file__).parents[2]
AGENTS = ROOT / "AGENTS.md"
AGENTS_MAX_BYTES = 8 * 1024
BACKLOG = ROOT / "docs" / "13-delivery" / "backlog.md"


def test_root_agent_guidance_stays_within_context_budget() -> None:
    assert len(AGENTS.read_bytes()) <= AGENTS_MAX_BYTES


def test_root_agent_guidance_keeps_required_authority_and_safety_routes() -> None:
    guidance = AGENTS.read_text(encoding="utf-8")

    for required in (
        ".codex/config.toml",
        ".codex/agents/*.toml",
        "docs/13-delivery/backlog.md",
        ".agents/skills/desktop-engineering-ui",
        "docs/01-product/visual-acceptance-matrix.md",
        "git reset",
        "git clean",
        "stash",
    ):
        assert required in guidance

    for duplicated_model_instruction in ("GPT-", "Luna", "Terra", "Extra High"):
        assert duplicated_model_instruction not in guidance


def test_cold_start_routes_demo_before_visual_work() -> None:
    backlog = BACKLOG.read_text(encoding="utf-8")

    issue_positions = [backlog.index(f"#{issue}") for issue in range(157, 163)]
    assert issue_positions == sorted(issue_positions)
    assert "실제 UI diff가 있을 때만 visual skill" in backlog
    assert "inventory의 `modeling-fit`" in backlog
    assert "새 Codex 작업" in backlog


def test_retired_instruction_documents_are_absent_and_unreferenced() -> None:
    retired = (
        "CODEX_DESKTOP_ENGINEERING_UI_START.md",
        "desktop-engineering-ui-backlog.md",
        "production-pilot-execution-plan.md",
    )
    stale_reference_paths = (
        "docs/00-research/ux-layout-review/modeling.html",
        "docs/00-research/ux-layout-review/review.css",
    )

    for name in retired:
        assert not any(ROOT.rglob(name))

    markdown = "\n".join(
        path.read_text(encoding="utf-8")
        for path in ROOT.rglob("*.md")
        if not {".git", ".venv", "node_modules"}.intersection(path.parts)
        and "_incoming" not in path.parts
    )
    for value in (*retired, *stale_reference_paths):
        assert value not in markdown


def test_project_skills_are_authoritative_documentation() -> None:
    classes = _documentation_classes(ROOT)

    assert (
        classes[".agents/skills/desktop-engineering-ui/SKILL.md"]
        == "authoritative"
    )
    assert (
        classes[".agents/skills/frontend-ui-engineering/SKILL.md"]
        == "authoritative"
    )
