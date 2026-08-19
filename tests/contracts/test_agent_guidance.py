from __future__ import annotations

from pathlib import Path

from cmp.tools.user_guide import _documentation_classes

ROOT = Path(__file__).parents[2]
AGENTS = ROOT / "AGENTS.md"
AGENTS_MAX_BYTES = 16 * 1024
BACKLOG = ROOT / "docs" / "13-delivery" / "backlog.md"


def test_root_agent_guidance_stays_within_context_budget() -> None:
    assert len(AGENTS.read_bytes()) <= AGENTS_MAX_BYTES


def test_root_agent_guidance_keeps_authority_and_acceptance_boundaries() -> None:
    guidance = AGENTS.read_text(encoding="utf-8")

    for required in (
        "docs/13-delivery/backlog.md",
        "docs/14-testing/product-work-acceptance.md",
        ".agents/skills/desktop-engineering-ui",
        "docs/01-product/visual-acceptance-matrix.md",
        "git pull --ff-only origin main",
        "active issue",
        "all its listed units finish",
        "primary user journey",
        "visible outcome",
        "persistence/read-back outcome",
        "preserved contract/state",
        "Database/Profile/Table/Folder/Record",
        "dominant persistent graph",
        "`make compose-preflight`",
        "explicit owner instruction",
        "failure or scope",
        "renewed authority",
        "expected base/head/diff/paths",
        "inspect the pending diff",
        "After commit and before publication",
        "inspect the exact commit diff",
        "fetch and read back remote state",
        "Immediately after merge",
        "verify the remote `main` merge SHA",
        "git reset",
        "git clean",
        "stash",
    ):
        assert required in guidance

    for personal_instruction in (
        ".codex/config.toml",
        ".codex/agents",
        "gpt-5.6",
        "fork_turns",
        "followup_task",
        "close_agent",
        "max_concurrent_threads_per_session",
        "Full workflow",
        "Balanced",
    ):
        assert personal_instruction not in guidance


def test_personal_orchestration_files_are_absent_from_repository() -> None:
    for relative in (
        ".codex/config.toml",
        ".codex/agents",
        "docs/14-testing/codex-orchestration-workflow.md",
        "docs/14-testing/codex-orchestration",
        "docs/14-testing/main-orchestrator-acceptance.md",
    ):
        assert not (ROOT / relative).exists()


def test_cold_start_routes_user_work_in_product_order() -> None:
    backlog = BACKLOG.read_text(encoding="utf-8")

    work_units = (
        "#157 깨끗한 데모 실행",
        "#159 Materials 검색·조회·다운로드",
        "#159 물성 데이터 등록·관리",
        "#158 Modeling Data",
        "#158 Modeling Process",
        "#158 Modeling Fit",
        "#158 Modeling Export",
        "#160 검토·승인·DB 공개·복구",
        "#161 공통 화면·전역 레이아웃 기반",
        "#162 Ubuntu VM·문서 최종 검증",
        "#162 공개 실측 데이터 최종 검증",
    )
    positions = [backlog.index(unit) for unit in work_units]
    assert positions == sorted(positions)
    assert "실제 화면이 바뀔 때만 visual skill" in backlog
    assert "`modeling-fit` 승인 화면" in backlog
    assert "새 Codex 작업" in backlog
    assert "Materials에서 필요한 물성을 검색" in backlog
    assert "모든 결과에서 원본 데이터까지 역추적" in backlog
    assert "NIST Numisheet 2020" in backlog


def test_retired_instruction_documents_are_absent_and_unreferenced() -> None:
    retired = (
        "CODEX_DESKTOP_ENGINEERING_UI_START.md",
        "desktop-engineering-ui-backlog.md",
        "production-pilot-execution-plan.md",
        "codex-orchestration-workflow.md",
        "main-orchestrator-acceptance.md",
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

    assert classes[".agents/skills/desktop-engineering-ui/SKILL.md"] == "authoritative"
    assert classes[".agents/skills/frontend-ui-engineering/SKILL.md"] == "authoritative"
