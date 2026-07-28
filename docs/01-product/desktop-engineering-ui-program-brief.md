# Desktop Engineering UI Rebuild Program Brief

Status: authoritative program brief; execution handoff is `AGENTS.md`
Date: 2026-07-28
Scope: existing CAE Material Platform presentation-layer rebuild  
Supersedes: the standalone V2 UI ZIP and the legacy `ux-redesign-package` startup prompts as
implementation sources. Their useful conclusions are absorbed here and into the linked canonical
repository documents; the legacy package remains historical context only.

## Current delivery boundary

`55cfa62` (PR #156) is the approved product/visual implementation baseline. Start every task from the
latest `main` with `git pull --ff-only origin main`. PR #125–#165 are merged bounded scope; they are not
a queue to reimplement. The next product-level order is #157 demo, #158 Fit, #159 Materials, #160
Governance/Activity, #161 DUI-09, then #162 UXC-99. The incoming package remains temporary reference
until #162 completes absorption and an inbound-link audit. See `AGENTS.md` for the mandatory one-writer,
deterministic-gate, fresh-reviewer execution rule.

## 1. Goal

Preserve the existing Material Database, test-data handling, statistics/processing, calibration,
validation, solver-card delivery, review/release, API and domain contracts. Replace the current
presentation and interaction layer so that the browser behaves like a compact desktop CAE workbench.

The intended user experience is functional parity with the public working grammar of Ansys Granta
and Altair Material Modeler:

- Materials work is a high-density explorer: find or browse, inspect, compare, then preview or
  download a valid solver card.
- Modeling work is a continuous calibration studio: select data, prepare it, fit, then generate a
  solver card without losing the active graph or session. Validation and review/release are distinct
  governed Advanced/Activity actions, not normal-stage tiles.
- The result must look and behave like a Windows engineering program delivered in a browser, not a
  landing page, mobile layout, content portal or card-heavy SaaS dashboard.

Do not copy names, logos, product assets, proprietary schemas, private behavior or exact pixel
traces. Reuse only publicly observable workflow, information hierarchy and interaction grammar.

## 2. Non-negotiable scope

### Preserve

- Existing API endpoints, calculation engines, file formats and download behavior.
- Database/Profile/Table/Folder/Record navigation; Table, Attribute, Layout, Subset and Link Type
  administration; exact-revision links.
- Stable identity versus immutable revision, provenance, original/normalized units and quantity
  semantics.
- Test-data import, processing, fitting, validation, Material Model IR, mapping classifications and
  native Abaqus/OpenRadioss card workflows.
- Existing routes and deep links unless a compatible redirect is explicit.
- Existing user-visible data and numerical results. Characterization and regression tests must prove
  behavior did not change because of the UI migration.

### Replace

- Existing page hierarchy, authenticated web header, centered navigation, hero copy, oversized
  margins, rounded card grammar and route-by-route page flow.
- Route markup and CSS only after controller/state/API behavior has been extracted or protected by
  tests.
- Legacy selectors and duplicate interaction surfaces once the new workbench path is functionally
  equivalent.

### Do not add in this program

- New solver mappings, constitutive models, test standards, optimizer policies or validation
  thresholds.
- Backend/domain/database migrations justified only by a visual rewrite.
- Electron, Tauri or another native wrapper.
- A disconnected mock/demo UI in production paths.

## 3. Source-of-truth order

Read these documents in this order before changing a visual route:

1. [AGENTS.md](../../AGENTS.md)
2. this brief
3. [Desktop Engineering UI Product and Interaction Specification](desktop-engineering-ui-product-spec.md)
4. [Desktop engineering UI specification](desktop-engineering-ui-spec.md)
5. [Desktop Engineering UI Tooling](desktop-engineering-ui-tooling.md)
6. [Desktop Engineering UI Delivery Backlog](../13-delivery/desktop-engineering-ui-backlog.md)
7. [Project desktop-engineering-ui skill](../../.codex/skills/desktop-engineering-ui/SKILL.md)
8. [Official GUI image manifest](../00-research/images/gui-reference/README.md), every image relevant
   to the screen, and current product screenshots/evidence.

If a previous ZIP, mockup, screenshot or ad-hoc prompt disagrees with those sources, the repository
documents above win. The standalone mockup is only a discussion artifact; its data, SVGs and
setTimeout interactions must not enter production code.

## 4. Locked workbench grammar

The 46 px application bar, 38 px workspace command bar, and 24 px semantic status bar are historical
DUI-01 evidence, not current authority. The shared product header is 44–48 px. Workspace controls and
status appear only where the actual workspace and user task require them: Modeling uses compact
context/stage controls with a shallow graph-adjacent ribbon, and no permanent generic command/status
bands may consume graph space. Materials, Activity, and Administration must not gain generic bands
that their current route does not render.

| Workspace | Primary reference grammar | Required topology | Explicitly not allowed |
| --- | --- | --- | --- |
| Materials | Granta data explorer | Navigator/facets/tree → dense grid, datasheet or comparison center → optional selected-record context | Material-card gallery, separate search/browse pages, blanking the workspace on selection |
| Material Detail / Card delivery | Granta datasheet + card review | Compact record context → tabs/property sheet or native preview → delivery properties/evidence disclosure | UUID/JSON-first normal flow, card CTA detached from the selected record |
| Modeling | Material Modeler calibration studio | Curve/process rail → persistent central plot → shallow current-stage ribbon or optional task drawer | Permanent third inspector that steals graph width, stage-specific unrelated pages |
| Compare | Granta comparison workflow | Selection set → property rows × record columns matrix → mapping/card preview when applicable | KPI dashboard, one card per material |
| Administration | Granta schema tool | Object navigator → list/data grid → contextual property editor and preview | Task-card landing page, schema editing through free-form JSON by default |
| Activity | Dense engineering work queue | Work queue/saved view → row-specific resume or review actions | KPI tile dashboard |

The normal-user global routes stay Materials, Modeling and Activity. Administration remains role-gated.
Within a workspace, global navigation, contextual navigation and selected-object commands must not be
mixed into one visual list.

### Interaction rules

- A selection set is persistent across coordinated views. Selecting records in a grid and switching
  to Curve or Compare retains selection and filters.
- Materials single-click updates context in place; Enter/double-click opens the datasheet in the
  center region while the navigator remains available. Back/forward restores the prior context.
- Modeling keeps one plot mounted throughout Data, Process, Fit and Export. Stage changes alter
  commands, overlays and a shallow graph-adjacent control band; they must not discard the selected curves or
  graph state.
- Panes divide by alignment and 1 px splitters before background, radius, border or shadow. Persist
  pane sizes and collapsed state where the backlog requires it.
- Use compact rows, tabular numeric alignment, unit-aware values, contextual command bars and one
  filled primary command per current task. Put raw IDs, JSON and verbose provenance in Evidence,
  Advanced or Administration.

## 5. Functional migration method

This is a brownfield migration, not a visual overlay and not a new frontend beside the existing one.

### Phase 0 — inventory before replacement

For the current DUI task, create a function migration table with:

| Existing route/component | Current user action/state | API/controller/state owner | New workbench location | Regression/E2E proof | Legacy removal condition |
| --- | --- | --- | --- | --- | --- |

Include loading, empty, error, disabled, unsaved-change, exact-revision and download states. Never
delete a route component simply because its markup looks old; first move or protect its behavior.

### Delivery sequence

Use the backlog in order:

1. Future major workspace redesign: `AGENTS.md` requires reference comparison, responsive prototype,
   measured region ratios and recorded product-owner approval before any production React/CSS work.
2. DUI-02 Materials split workspace and in-place datasheet.
3. DUI-03 contextual card delivery.
4. DUI-04 persistent Modeling session and graph-adjacent control band.
5. DUI-05 data intake and processing.
6. DUI-06 fit and export decision workflow.
7. DUI-07 Administration object navigator/property editor.
8. DUI-08 Activity resume and attention model.
9. DUI-09 component workbench and final legacy CSS removal.

One pull request implements one bounded DUI slice. A “frontend rewrite” that combines those slices
without independent user-flow evidence is not acceptable.

## 6. Official references and evidence

The repository already holds the official Granta and Material Modeler reference manifest. Open the
actual relevant local images; do not treat only their filenames, a gallery description, or an AI
summary as evidence.

For every visual pull request, record:

| Item | Required evidence |
| --- | --- |
| Reference review | Exact image names opened, applied layout/interaction principle, intentional difference and its reason |
| Current task | Before/after screenshots and a user-action/state transition |
| Functional parity | Real API data, actual success/error/disabled behavior and download/import/fitting regression where relevant |
| Desktop geometry | 1366×768, 1440×900 and 1920×1080 captures; shell/pane/padding/row/plot/overflow measurement table |
| UI quality | Legacy-selector report, keyboard/focus check and no page-level horizontal overflow |
| Documentation | Updated user guide, screenshot manifest and visual evidence required by AGENTS.md |

Reference images are planning and review input, not product assets. Do not copy them into shipped UI,
and do not create new production screens from static mock data.

## 7. Skill assurance and automatic quality loop

The complete installation commands, skill roles, precedence and mandatory audit loop are owned only
by [Desktop Engineering UI Tooling](desktop-engineering-ui-tooling.md). Read and apply that section
before any approved DUI implementation.

The required four layers are the existing project `desktop-engineering-ui` skill plus
`frontend-ui-engineering`, `web-design-guidelines` and `webapp-testing`. The repository
specification and domain invariants remain authoritative if a generic external recommendation
conflicts with the desktop workbench contract.

For every screen, the tooling-defined loop is mandatory: inspect the current route and references,
implement against actual state/API, test the real flow at all three desktop viewports, audit, correct
every hard-gate failure, then recapture/retest and update evidence.

## 8. Completion definition

A DUI slice is complete only when all of the following are true:

- The real feature works through actual API/state flows; no production mock substitutes for it.
- Existing numerical/domain/solver-card behavior is unchanged or a separately approved product
  decision documents the change.
- The screen passes the required visual-acceptance matrix with no topology, data/plot-dominance,
  nested-card or overflow hard-gate failure.
- Keyboard, focus, loading, empty, disabled and error states were tested.
- Screenshots and measurements exist at all required desktop viewports.
- Legacy classes/components were removed, isolated or explicitly deferred to the owning DUI task.
- The repository’s documentation and screenshot gates pass.
- The pull request says what user task changed, what reference grammar was applied, what was verified,
  and what remains intentionally deferred.

## 9. Session start

[AGENTS.md](../../AGENTS.md) is the single current execution handoff. It owns baseline, issue order,
approval references, and execution gates. [CODEX_DESKTOP_ENGINEERING_UI_START.md](../../CODEX_DESKTOP_ENGINEERING_UI_START.md)
is a short compatibility pointer only; do not treat it as an independent paste prompt.
