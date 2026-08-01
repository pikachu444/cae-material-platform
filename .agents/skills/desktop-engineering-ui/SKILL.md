---
name: desktop-engineering-ui
description: Execute or review CAE Material Platform visual work, including approved-reference selection, React/CSS porting, screenshots, and full-screen qualitative acceptance.
---

# Desktop Engineering UI

Build a compact browser-delivered engineering workspace, not a marketing site or generic card
dashboard. Follow `AGENTS.md` for agent selection, correction limits, publication and current work.

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

Before calling a writer, the main agent stores one bounded packet naming:

- the user task and exact assets/screens;
- static region to component, event, state and data-source mapping;
- preserved behavior, loading/empty/blocked/error states and invalidation contracts;
- forbidden shortcuts, required captures, interactions and tests.

The writer implements that packet without reinterpreting product requirements.

## Verify the complete screen

At the issue's required viewports, verify the task flow, keyboard path, state recovery, selection
continuity, local scroll discoverability and absence of page overflow, clipping, overlap or distorted
plots. Capture live/reference comparisons and update the required current guide, screenshot manifest
and live screenshots.

After deterministic gates, the main agent opens every target/state image at original resolution and
records pass, fail or not-applicable evidence for Q-01 through Q-20. Judge the whole screen before an
isolated control: engineering credibility, information density, hierarchy, graph/table/tree dominance,
whitespace, typography, meaningful wide-screen use and responsive continuity. Numeric measurements
support this judgment but cannot override a qualitative failure.

## Independent review and approval

The main agent stores a bounded reviewer packet containing issue acceptance, approved references,
implementation diff, live/comparison paths, interaction/test results and the completed checklist. The
configured fresh read-only reviewer independently checks the same evidence and returns actionable
findings plus an approval disposition.

The main agent repeats the original-resolution product/UX judgment after review. The product owner is
the final visual approver. Follow `AGENTS.md` for correction and re-review limits; automatic LLM review
remains disabled under #119.
