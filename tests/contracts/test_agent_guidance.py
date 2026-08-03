from __future__ import annotations

import tomllib
from pathlib import Path

from cmp.tools.user_guide import _documentation_classes

ROOT = Path(__file__).parents[2]
AGENTS = ROOT / "AGENTS.md"
AGENTS_MAX_BYTES = 8 * 1024
AGENTS_DIR = ROOT / ".codex" / "agents"
BACKLOG = ROOT / "docs" / "13-delivery" / "backlog.md"


def _agent_config(filename: str) -> dict[str, object]:
    return tomllib.loads((AGENTS_DIR / filename).read_text(encoding="utf-8"))


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
        "git pull --ff-only origin main",
        "active issue stays on",
        "all its listed units finish",
        "configured role actually loaded",
        "report the exact error",
        "`make compose-preflight`",
        "git reset",
        "git clean",
        "stash",
    ):
        assert required in guidance

    for removed_instruction in ("#119", "automatic LLM review"):
        assert removed_instruction not in guidance

    for duplicated_model_instruction in ("GPT-", "Luna", "Terra", "Extra High"):
        assert duplicated_model_instruction not in guidance


def test_agent_role_configs_encode_writer_reviewer_and_correction_boundaries() -> None:
    assert not (AGENTS_DIR / "correction-terra-high.toml").exists()

    correction = _agent_config("correction-luna-max.toml")
    assert correction["model"] == "gpt-5.6-luna"
    assert correction["model_reasoning_effort"] == "max"
    assert "Fresh one-shot" in str(correction["description"])

    implementer = _agent_config("implementer-luna-max.toml")
    implementer_instructions = str(implementer["developer_instructions"])
    assert "packet's automated gates" in implementer_instructions
    assert "unrun or blocked gates" in implementer_instructions
    assert "never claim main-orchestrator live acceptance" in implementer_instructions

    reviewer = _agent_config("reviewer-terra-high.toml")
    reviewer_instructions = str(reviewer["developer_instructions"])
    assert "every issue-required viewport" in reviewer_instructions
    assert "original resolution" in reviewer_instructions
    assert "never substitute a representative subset" in reviewer_instructions


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
        "#161 공통 화면 정리",
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
