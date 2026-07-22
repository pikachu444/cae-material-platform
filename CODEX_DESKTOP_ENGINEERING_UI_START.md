# Codex Desktop Engineering UI Start

This is the entrypoint for the existing CAE Material Platform desktop-workbench rebuild. It replaces
ad-hoc prompts about making the UI “look more like” Granta MI or Material Modeler.

## Goal

Keep the existing material, test-data, processing, fitting, validation, revision/provenance and
solver-card capabilities intact while replacing the presentation and task flow with a dense desktop
engineering workbench. The user must be able to recognise and complete the Granta-style data-explorer
and Material-Modeler-style calibration workflows without encountering a generic SaaS dashboard.

## Paste this request into a new Codex session

> CODEX_DESKTOP_ENGINEERING_UI_START.md를 먼저 읽어라. PR #112의 제품 책임자 승인이 기록되지 않았으면 구현하지 말고 막힌 이유만 보고하라. 승인됐으면 문서에 적힌 프로젝트 단위 외부 스킬을 설치·확인하고, 기존 API·도메인 계약을 보존한 채 다음 DUI 작업 하나만 구현하라. 실제 흐름·회귀검증·세 가지 데스크톱 해상도 검수를 통과할 때까지 수정하고 증거를 남겨라.

## Read in order

1. `AGENTS.md`
2. `docs/01-product/desktop-engineering-ui-program-brief.md`
3. `docs/01-product/desktop-engineering-ui-product-spec.md`
4. `docs/01-product/gui-functional-parity-plan.md`
5. `docs/01-product/desktop-engineering-ui-tooling.md`
6. `docs/13-delivery/backlog.md`
7. `docs/13-delivery/desktop-engineering-ui-backlog.md`
8. `.codex/skills/desktop-engineering-ui/SKILL.md`
9. `docs/00-research/ux-reference-gallery/README.md`
10. `docs/00-research/images/gui-reference/README.md` and every relevant local image it inventories
11. the relevant screen section in `docs/01-product/gui-functional-parity-plan.md`
12. current route code, tests, screenshots and user guides

## Program rule

- Do not begin with a generic visual cleanup, a CSS-only pass or a disconnected mockup.
- `AGENTS.md` requires product-owner approval before production React/CSS changes. Treat Draft PR
  #112 as unaccepted until the approval is recorded. PR #112 was approved and merged on 2026-07-22;
  DUI-02 therefore passed this gate. If a later slice lacks its required approval, stop and report it.
- After that acceptance, implement the delivery backlog in order. One pull request owns one bounded
  DUI slice.
- Preserve database, revision/provenance, unit and solver-mapping contracts. Move the facade, not
  the scientific/domain behavior.
- For every slice, use the project desktop-engineering-ui skill plus the three external skills defined
  in `desktop-engineering-ui-tooling.md`.
- A visual task is not complete until it has real API/state proof, task-flow regression tests,
  1366×768/1440×900/1920×1080 captures, keyboard/focus checks, reference comparison, legacy-selector
  disposition and updated current documentation.

The official GUI reference manifest is mandatory screen-level evidence. A gallery description,
filename or AI summary by itself is not a review.
