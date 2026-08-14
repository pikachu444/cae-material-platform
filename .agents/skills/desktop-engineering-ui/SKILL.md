---
name: desktop-engineering-ui
description: Execute or review CAE Material Platform visual work, including approved-reference selection, React/CSS porting, five-viewport and Windows 4K/high-DPI evidence, screenshots, and full-screen qualitative acceptance.
---

# Desktop Engineering UI

Build a compact browser-delivered engineering workspace, not a marketing site or generic card
dashboard. Agent selection, correction limits, publication, and current-worktree boundaries are
external to this visual skill. The main orchestrator fixes writer scope and escalation before applying
the skill; correction and publication boundaries remain external.

## Architecture and semantic preflight

Before this visual skill is used for work under `apps/web`, read `apps/web/AGENTS.md` and run the
project-local `material-platform-frontend-architecture` skill whenever the change touches feature
ownership, a registered hotspot, Materials-to-Modeling continuity, state/API/type/CSS structure, helper
copy, semantic emphasis, or wide-screen composition. This visual skill does not authorize a route-topology
redesign, a new frontend dependency, or mixing broad structural and visual changes in one PR.

## Route only the needed context

1. Read the exact GitHub issue.
2. Find its target family in `docs/01-product/service-reference-inventory.yaml` with `rg`.
3. Read only that family's entries in `docs/01-product/service-reference-manifest.yaml` and inspect
   every listed HTML, CSS and image at original resolution.
4. Read Q-01 through Q-20 in `docs/01-product/visual-acceptance-matrix.md`, then only the affected
   route-specific gate and the relevant product/UI-spec sections.
5. Inspect the affected React, API, state and test contracts.

Do not bulk-read the complete product specs, manifest or incoming package. Use
`frontend-ui-engineering` only for production React/CSS/component work, `web-design-guidelines` only
for an explicit UI/accessibility audit, and `webapp-testing` only for live interaction, capture or
browser evidence.

## Prepare and implement from authority

Treat the registered approved HTML/CSS and images as implementation authority for their exact target.
Port their region structure and CSS faithfully while wiring existing data and state contracts. Do not
invent replacement topology, route-specific override layers, fake data fallbacks or decorative
technical content.

Before calling a writer, the main orchestrator opens the exact approved images plus named HTML/CSS at original
resolution, inspects the current live/capture state and stores one bounded packet naming:

- the user task and exact assets/screens;
- static region to component, event, state and data-source mapping;
- region-by-region reference-to-current differences;
- preserved behavior, loading/empty/blocked/error states and invalidation contracts;
- forbidden shortcuts, required captures, interactions and tests.

A family name or image list alone is insufficient. Writer scope and escalation are fixed before this
skill is applied; correction and publication boundaries remain external.

## Verify the complete screen

For every user-visible React/CSS change, capture the task at 1366×768, 1440×900, 1920×1080,
2560×1440, and 3840×2160 with browser zoom fixed at 100%. Capture the live state before implementation
and after each proposed correction. Verify the task flow, keyboard path, state recovery, selection
continuity, local scroll discoverability and absence of page overflow, clipping, overlap or distorted
plots. Capture live/reference comparisons and update the required current guide, screenshot manifest
and live screenshots.

Open each capture at original resolution. Return the 1920/2560/3840 full-screen comparison plus
100%-pixel crops of the header, navigator, table/form controls, and graph or native preview to the
product owner. Do not approve from a scaled contact sheet, DOM measurements, or image dimensions alone.
Automated viewport capture proves CSS geometry. #221 compares representative candidates using the
five original-resolution viewport captures and fixes a provisional shared implementation decision; #184 revalidates that
decision across every route/state. Both record the available display, CSS viewport and device pixel
ratio. When an actual 4K display is unavailable, they record `DEFERRED_TO_223` and do not claim physical
readability. #223 performs the final product-wide Windows 4K 100%, 150%, and 200% check.

Judge wide screens by semantic elasticity. The application shell uses the full viewport; graphs,
tables, and native previews grow while extra space improves the task, while navigators, property forms,
and prose keep readable limits and balanced gutters. Fail a one-sided 1920 px work island, a large void
between related regions, or tiny fixed-density controls at 2560/3840. Also fail uniform stretching,
fabricated filler, route-specific 4K overrides, CSS `zoom`, blanket `transform: scale`, and non-uniform
SVG stretching. Implement scale tiers only through shared typography, control, row, spacing, pane, and
plot tokens.

Only #160 and #161 may record an inherited global layout or density failure for the #221 decision
packet and subsequent #184 carryover. The packet must retain the original-resolution evidence, name
every affected route/state, prove no new page-specific workaround was added, and include the
product-owner disposition. #221 approves the provisional shared policy, not every route; #184 completes
the full automated application. After #184 merges, only unavailable actual-device physical readability
may remain for #223; known geometry, clipping, overflow or interaction failures may not be deferred.

After implementation and the packet's deterministic gates, the main orchestrator opens every target/state image
at original resolution, repeats the region-by-region comparison, records resolved and unresolved
differences, and completes Q-01 through Q-20 once. Judge the whole screen before an isolated control:
engineering credibility, information density, hierarchy, graph/table/tree dominance, whitespace,
typography, meaningful wide-screen use and responsive continuity. Numeric or existence checks are only
supporting evidence.

## Independent review and approval

Only after the main-orchestrator gate passes, store one bounded reviewer packet containing issue acceptance,
approved references, implementation diff, live/comparison paths, interaction/test results and the
completed checklist. The configured canonical read-only reviewer reopens only that evidence and returns
actionable findings plus an approval disposition. It may disagree with the main-orchestrator judgment using
the named criteria, but it does not introduce new acceptance criteria.

The main orchestrator evaluates the findings. Reviewer completion alone does not trigger another full-screen
checklist. If a correction changes implementation or evidence, rerun only the affected comparisons and
gates before review through the same canonical reviewer; when neither changed, do not request another
review. Correction, approval,
and publication boundaries remain with the main orchestrator and the applicable workflow contract.
