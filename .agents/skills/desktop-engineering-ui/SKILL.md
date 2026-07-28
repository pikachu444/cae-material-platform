---
name: desktop-engineering-ui
description: Execute or review CAE Material Platform visual work, including static reference creation, React/CSS porting, screenshots, and visual acceptance. Use for any frontend layout, navigation, typography, component, CSS, screenshot, or visual-review task.
---

# Desktop Engineering UI

Build a browser-delivered engineering workspace, never a marketing site or generic card dashboard.

## Read first

Read `AGENTS.md`, `docs/01-product/desktop-engineering-ui-product-spec.md`,
`docs/01-product/visual-acceptance-matrix.md`, the current task, relevant local reference manifest and
images, current screenshot-manifest entries/images, and the relevant UI specification. Also use
`frontend-ui-engineering`, `web-design-guidelines`, and `webapp-testing` for every visual task.

## Reference gate

For #167, build and register the complete service reference set before production visual work:

- Materials search/tree/detail/card;
- Modeling Data/Process/Fit/Export;
- Activity user/reviewer/recovery;
- Administration database/table/attribute/layout/subset/link/access edit/publish;
- 1366×768, 1440×900 and 1920×1080 plus relevant long, empty, loading, blocked and error states.

For every reference, record static HTML/CSS source, rendered-image path and hash, viewport, date,
status, main-agent evaluation, and product-owner approval. The main agent must open and evaluate every
image; no React/CSS implementation starts without product-owner approval of the exact target state.

Approved static HTML/CSS and images are implementation source and visual authority. Port their regions
and CSS faithfully into React while wiring existing state/backend contracts. Do not redesign an
approved topology or add incremental route-specific CSS overrides.

## Implementer packet and workflow

Before spawning an implementer, the main Sol agent must inspect the exact issue, approved HTML/CSS
and images, current components, and preserved state/data contracts. The main agent authors and
delivers the detailed packet; never ask the implementer to discover or rewrite its own requirements.
Name the exact target assets/screens/components, user task, preserved behavior/data/state,
static-region → React component/contract mapping, forbidden shortcuts, required captures and tests.
Preserve catalog hierarchy, revision/provenance, unit semantics, solver mapping, and access contracts.
Use the engineering grammar: split panes, compact grids/property sheets, flat dividers, one filled
primary action, in-place selection, persistent Modeling graph, and technical detail in
Advanced/Evidence.

Open the reference and live route at all required viewports. Verify the full workflow, keyboard path,
loading/empty/blocked/error recovery, no page overflow, no clipping/overlap, state continuity and
legacy-selector report. Capture reference/current side-by-side evidence and update the required current
guide, screenshot manifest and live screenshots. Measurements are safety rails, not an invitation to
pixel-copy or tune arbitrary small numbers.

## Reviewer packet and decision

After implementation and deterministic gates, the main Sol agent prepares the bounded reviewer packet:
issue acceptance, approved references, implementation diff, direct paths to live and comparison
captures, and interaction/test results. The reviewer evaluates full-screen usability and parity:
task flow, topology, information priority, readable density, graph/table/tree dominance,
control-result continuity, overflow, clipping and overlap. Do not accept test success alone. The main
agent owns final UX judgment and directly compares the resulting images before product-owner review.
Permit one evidence-backed correction and fresh re-review at most; do not repeat a failed local CSS
approach. Automatic LLM review stays disabled under #119.
