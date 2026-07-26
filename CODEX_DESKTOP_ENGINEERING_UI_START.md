# Codex Desktop Engineering UI Start

This is the sole Codex entrypoint for the CAE Material Platform desktop-workbench program. It
replaces all earlier UX-redesign prompts and packages.

## Goal

Keep the existing material, test-data, processing, fitting, validation, revision/provenance and
solver-card capabilities intact while replacing the presentation and task flow with a dense desktop
engineering workbench. The user must be able to recognise and complete the Granta-style data-explorer
and Material-Modeler-style calibration workflows without encountering a generic SaaS dashboard.

## Paste this request into a new Codex session

> `CODEX_DESKTOP_ENGINEERING_UI_START.md`를 먼저 읽어라. `docs/13-delivery/desktop-engineering-ui-backlog.md`에서 다음 pending UXC/DUI 작업 하나를 확인하고, 기존 API·도메인 계약을 보존해 구현하라. PR #124/DUI-01~06은 완료됐으므로 다시 구현하지 않는다. 실제 흐름·결정적 회귀검증·1366×768/1440×900/1920×1080 live-browser 검수를 통과하고 current guide, screenshot manifest와 evidence를 갱신할 때까지 작업한다. #119의 자동 LLM review는 활성화하지 않는다.

## Read in order

1. `AGENTS.md`
2. `docs/01-product/product-vision.md`
3. `docs/01-product/desktop-engineering-user-flows.md`
4. `docs/01-product/desktop-engineering-ui-product-spec.md`
5. `docs/01-product/desktop-engineering-ui-spec.md`
6. `docs/01-product/visual-acceptance-matrix.md`
7. `docs/01-product/desktop-engineering-ui-tooling.md`
8. `docs/13-delivery/backlog.md`
9. `docs/13-delivery/desktop-engineering-ui-backlog.md`
10. `.codex/skills/desktop-engineering-ui/SKILL.md`
11. `docs/00-research/ux-reference-gallery/README.md`
12. `docs/00-research/images/gui-reference/README.md` and relevant inventoried images
13. current route code, tests, screenshots and user guides

## Program rule

- Do not begin with a generic visual cleanup, a CSS-only pass or a disconnected mockup.
- `AGENTS.md` requires a reference comparison, responsive prototype, measured region ratios and
  explicit product-owner approval before production React/CSS changes. DUI-01~06, including PR
  #124/DUI-06, are complete. UXC-00R is the documentation authority correction; remaining work is
  Reviewer access migration, Materials query/presentation gaps, DUI-07, DUI-08 and DUI-09. Do not
  claim future workflow states are implemented. If a later visual slice lacks its approval, stop and
  report it.
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
