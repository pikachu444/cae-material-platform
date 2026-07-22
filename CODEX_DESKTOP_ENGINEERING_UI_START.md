# Codex Desktop Engineering UI Start

This is the entrypoint for the existing CAE Material Platform desktop-workbench rebuild. It replaces
ad-hoc prompts about making the UI “look more like” Granta MI or Material Modeler.

## Goal

Keep the existing material, test-data, processing, fitting, validation, revision/provenance and
solver-card capabilities intact while replacing the presentation and task flow with a dense desktop
engineering workbench. The user must be able to recognise and complete the Granta-style data-explorer
and Material-Modeler-style calibration workflows without encountering a generic SaaS dashboard.

## Paste this request into a new Codex session

> Read this file first. Preserve every existing API and domain contract, then complete only the next approved DUI task. Use the external UI, audit and browser-testing skills; verify the real flow at all three desktop viewports, fix every failed gate, and do not mark the task done before regression and evidence are complete.

## Read in order

1. `AGENTS.md`
2. `docs/01-product/desktop-engineering-ui-program-brief.md`
3. `docs/01-product/desktop-engineering-ui-product-spec.md`
4. `docs/01-product/gui-functional-parity-plan.md`
5. `docs/01-product/desktop-engineering-ui-tooling.md`
6. `docs/13-delivery/desktop-engineering-ui-backlog.md`
7. `.codex/skills/desktop-engineering-ui/SKILL.md`
8. `docs/00-research/ux-reference-gallery/README.md`
9. `docs/00-research/images/gui-reference/README.md` and every relevant local image it inventories
10. the relevant screen section in `docs/01-product/gui-functional-parity-plan.md`
11. current route code, tests, screenshots and user guides

## Program rule

- Do not begin with a generic visual cleanup, a CSS-only pass or a disconnected mockup.
- Draft PR #112 owns DUI-01 and requires product-owner acceptance before DUI-02 starts. First check
  and record that status; do not silently bypass it.
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
