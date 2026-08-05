---
name: desktop-engineering-ui
description: Execute or review CAE Material Platform visual work, including approved-reference selection, React/CSS porting, screenshots, and full-screen qualitative acceptance.
---

# Desktop Engineering UI

Build a compact browser-delivered engineering workspace, not a marketing site or generic card
dashboard. Agent selection, correction limits, publication, and current-worktree boundaries are
external to this visual skill. The main orchestrator fixes writer scope and escalation before applying
the skill; correction and publication boundaries remain external.

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

At the issue's required viewports, verify the task flow, keyboard path, state recovery, selection
continuity, local scroll discoverability and absence of page overflow, clipping, overlap or distorted
plots. Capture live/reference comparisons and update the required current guide, screenshot manifest
and live screenshots.

After implementation and the packet's deterministic gates, the main orchestrator opens every target/state image
at original resolution, repeats the region-by-region comparison, records resolved and unresolved
differences, and completes Q-01 through Q-20 once. Judge the whole screen before an isolated control:
engineering credibility, information density, hierarchy, graph/table/tree dominance, whitespace,
typography, meaningful wide-screen use and responsive continuity. Numeric or existence checks are only
supporting evidence.

## Independent review and approval

Only after the main-orchestrator gate passes, store one bounded reviewer packet containing issue acceptance,
approved references, implementation diff, live/comparison paths, interaction/test results and the
completed checklist. The configured fresh read-only reviewer checks only that evidence and returns
actionable findings plus an approval disposition. It may disagree with the main-orchestrator judgment using
the named criteria, but it does not introduce new acceptance criteria.

The main orchestrator evaluates the findings. Reviewer completion alone does not trigger another full-screen
checklist. If a correction changes implementation or evidence, rerun only the affected comparisons and
gates before fresh review; when neither changed, do not request another reviewer. Correction, approval,
and publication boundaries remain with the main orchestrator and the applicable workflow contract.
