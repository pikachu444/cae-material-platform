# Issue #167 service reference freeze

Status: in progress; reference authoring packet and approval evidence

Issue: [#167 — Complete service reference freeze](https://github.com/pikachu444/cae-material-platform/issues/167)

Baseline: `6e835a5b1797f237993d296ebca76736da82cb7b` on latest `main`

Requirements: `FR-NAV-003`, `FR-UX-005`, `FR-UX-010`, `FR-UX-011`,
`NFR-SEC-006`

Architecture decisions: `ADR-0028`, `ADR-0030`, `ADR-0034`

Backlog: `docs/13-delivery/desktop-engineering-ui-backlog.md` — `#167`

## Execution contract

- The main agent owns requirement interpretation, product/UX judgment, the authoring packet, direct
  image inspection, and the final disposition.
- GPT-5.6 Luna is not callable in this surface. Because #167 is a large service-wide reference
  freeze, the first bounded author is one fresh GPT-5.6 Sol High subagent under the large-change
  exception in `AGENTS.md`.
- The author must read this exact packet and work only on the bounded target below. A second writing
  agent must not run concurrently.
- After deterministic checks and main-agent inspection, one fresh GPT-5.6 Terra High read-only
  reviewer receives only the bounded reviewer packet. At most one evidence-backed correction and
  re-review is permitted.
- Automatic LLM review remains disabled under #119.
- Production React/CSS, current user-guide screenshots, backend, API, domain data, and the incoming
  package are outside this reference-only slice.

## Main-agent source inspection

The main agent read the issue, repository instructions, required visual skills, product/interaction
specifications, domain/revision/architecture contracts, API authorization rules, test strategy, and
the current Materials implementation before writing this packet.

Actual images opened at original resolution:

- `docs/00-research/ux-reference-gallery/images/granta-mi-favourites-list.png`
- `docs/00-research/ux-reference-gallery/images/material-data-center-search-detail.png`
- `docs/00-research/images/gui-reference/granta-profile.png`
- `docs/00-research/images/gui-reference/granta-list-results.png`
- `docs/17-evidence/images/ux-layout-review/materials-1440x900.jpg`
- `docs/17-evidence/images/uxc-00d-responsive-design/materials-1440x900.png`
- `docs/user-guide/images/current/materials-search-1440x900.png`

Applied principles:

- retain a stable Database/Profile/Table/Folder/Record navigator and independent tree search;
- keep the dense result grid wider and more important than optional selected context;
- update selected context in place and put the exact next command next to that context;
- use flat dividers, compact rows, restrained titles, and data-first density;
- preserve the current compact application shell and server-scoped query contract.

Explicitly excluded:

- commercial branding, icons, colors, proprietary database structure, and exact geometry;
- UXC-00D's `Manufacturer/source`, `Yield`, `Condition`, and `CAE cards` search-result projections,
  because the current scoped Materials query does not supply their governed source, quantity,
  condition, unit, or readiness semantics;
- a global Compare command, property/card claims in selected context, released-card language,
  UUIDs, hashes, classification, JSON, and provenance on the normal search screen.

## Authoring packet 01 — Materials search / normal / 1440×900

### Exact target

Create the first pending #167 reference image:

`materials-search-normal-1440x900`

This target is one image approval unit. Its HTML/CSS foundation must be responsive enough for later
1366×768 and 1920×1080 captures, but this packet captures and registers only 1440×900. Do not create
or submit the later viewport images before the product owner reviews this first image.

Required new files:

- `docs/00-research/ux-service-reference/materials-search-normal.html`
- `docs/00-research/ux-service-reference/reference.css`
- `docs/00-research/ux-service-reference/reference.js`
- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.measurements.json`

The source and image paths above are exact. Reuse lessons from
`docs/00-research/ux-layout-review/materials.html`, `review.css`, and `review.js`, but do not mutate
those historical sources or reuse their invalid result projections.

### User task

A User searches for a known steel, sees a complete authorized result page, selects one row without
losing the navigator or result state, and can open its datasheet. The first viewport must make the
query, governed tree, result total, selected row, selected context, and `Open datasheet` consequence
obvious without exposing internal identifiers.

### Required screen content

Use synthetic, non-production reference copy only.

- Application bar: current compact dark shell, `CMP`, `CAE Material Platform`,
  `Materials | Modeling | Activity`, `Demo user`; no subtitle or marketing copy.
- Workspace command bar: compact `Materials` title only. Do not add generic commands.
- Search band: query value `steel`, one filled `Find` action.
- Navigator modes: `Browse | Filters | Subsets`, with `Browse` selected.
- Scope controls: `Materials Database`, `Engineering Materials`, `Demo Material Records`.
- Tree-local search: `Find folder or record`, followed by a visible
  Database → Profile → Table → Folder → Record hierarchy and selected DP780 record.
- Results: `1–6 of 6 matches`, helper text `Enter opens · select up to 3 to compare`, and exactly the
  governed columns `Compare | Material / grade | Family | Description | Status`.
- Rows: six synthetic steel-oriented reference rows whose visible values all match the query.
  The first selected row is `DP780 synthetic demo steel`, grade `DP780-REF`, family `Metal`,
  description `Synthetic local-demo data; not validated engineering data.`, status `Draft`.
  Other rows must remain plainly synthetic/non-production and must not imply a production standard,
  released card, approved model, or confidential source.
- Selected context: `Selected material`, the selected name and grade, the same description,
  `Family: Metal`, `Status: Draft`, and one `Open datasheet` action.
- Status bar: selected human name/code, `r1 · draft`, `No active job`, `0 warnings`, `Online`.

Do not show provider, manufacturer, source, Yield, condition, property values, solver availability,
card readiness, release, validation, approval, or download on this search target. Those fields have
no current server-scoped Materials search projection and belong to later exact datasheet/card
references only when their source contracts exist.

### Layout and visual authority

At 1440×900:

- application bar: 46 px;
- workspace command bar: 38 px;
- search band: 40 px;
- status bar: 24 px;
- outer workspace margin: 8 px on each side;
- navigator: 264 px;
- optional selected context: 280 px;
- divider visual: 1 px with a 5 px accessible hit region;
- result region: remaining width and at least 720 px;
- tree rows: 24–26 px, 12–13 px regular/medium labels;
- result rows: 32–36 px, 13–14 px data text;
- controls: 2–4 px radius only; persistent panes/tables: zero radius and zero shadow.

Results must be wider than selected context. Use alignment, white space, and dividers before
background, border, radius, or shadow. Do not use gradients, nested cards, badges for counts,
eyebrows, hero copy, decorative illustration, or a centered fixed-width page.

The selected row uses a flat accent background plus an accent edge. Table headers are visually
resizable and sticky in the intended production mapping. Long text truncates with a title while the
row identity remains understandable.

### Static-region → production contract mapping

| Static region | Current React/component | State/source contract | Preserved behavior |
| --- | --- | --- | --- |
| application and command bars | `ApplicationShell`, `commandsFor()` | route-derived Materials workspace | 46/38/24 shell, primary navigation, status |
| search band | `MaterialSearchPage`, `.materials-page-header`, `.materials-search-form` | `draftQuery` → `query` → `listMaterials()` | Enter/Find applies query and URL state |
| continuous workspace | `ResizableSplitPane` id `cmp-materials-results` | persisted navigator/context sizing | results remain dominant; context optional |
| navigator modes | `MaterialSearchPage` navigator | `leftMode` | Browse/Filters/Subsets remain sibling modes |
| governed tree | `MaterialsBrowseTree` | Database/Profile/Table/Folder/Record APIs and exact selected record | independent scroll/search and exact record open |
| result header/table | `MaterialSearchPage`, `EngineeringColumnResizeHandle` | `materials`, `totalCount`, `familyFacets`, sort/offset from one `listMaterials` response | same scoped total/rows/facets; local selection/compare |
| selected context | `MaterialSearchPage` context pane | selected `MaterialResponse` only | row selection updates context in place |
| status | `publishWorkspaceStatus()` | selected revision, loading/error/job state | human context first; technical evidence omitted |

The source of result content is the current `GET /materials` product query exposed by
`listMaterials()`. Organization/project authorization, RLS, result rows, total, and facets remain
one fail-closed server scope. The static page illustrates that contract; it must not invent client
enrichment or a second count.

### Required semantics and interaction

- Use semantic header/nav/main/aside/section/table/form/button elements.
- Search input has an accessible name and `Ctrl/Cmd+K` focus support.
- Tree uses `role=tree`/`treeitem`, roving focus, Up/Down/Home/End, and Enter selection.
- Result rows are keyboard focusable; Enter exposes the datasheet consequence without navigating
  away during the reference check.
- Compare checkboxes and row selection are distinct controls.
- All icon-only controls, if any, have accessible names. Color is not the sole state cue.
- The normal captured state must contain no loading/error/unfinished status and no console error.

### Deterministic capture and checks

Follow `.agents/skills/webapp-testing/SKILL.md`: this is static HTML, so inspect selectors directly,
use native headless Chromium Playwright, wait for `document.fonts.ready`, and capture exactly the
browser viewport rather than a full-page image.

`capture_reference.py` must:

- accept a target id or exact HTML/image paths without hidden current-route dependencies;
- launch headless Chromium;
- open the local HTML through an absolute file URI;
- set 1440×900 exactly and use device scale factor 1;
- assert no page-level horizontal or vertical overflow;
- assert the declared region dimensions, table/tree row density, visible context, and one selected
  row;
- exercise search focus, tree keyboard movement, and result-row Enter behavior;
- fail on browser console errors or uncaught page errors;
- write the PNG and deterministic measurement JSON.

`validate_reference.py` must:

- run with `--help` and a target/image option;
- verify required files, exact 1440×900 PNG dimensions, source/image manifest paths, SHA-256, date,
  and status vocabulary;
- verify forbidden normal-path terms/columns are absent;
- verify the manifest entry is `pending`, main-agent evaluation is initially `pending`, and
  product-owner approval is unset;
- print a compact PASS/FAIL report and exit non-zero on any failure.

The author must run:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1440x900
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900
uv run cmp-check-user-guide --root .
```

Do not run `make docs-screenshots`; this slice does not change production React/CSS or current
screenshots. Do not commit, push, open a PR, or edit the GitHub issue. Return the changed paths,
commands/results, measurements, and any residual concern to the main agent.

## Main-agent evaluation 01

The main agent regenerated and opened the 1440×900 PNG at original resolution after the author
stopped writing. The image preserves the required `Navigator | Data Grid | optional Inspector`
topology, keeps the 870 px result grid dominant over the 264 px navigator and 280 px selected
context, and keeps query, total, selected row, selected context, next action, and status visible in
the first viewport. Typography, row density, hierarchy, dividers, and selection cues are readable
without cards, badges, decorative copy, overlap, clipping, or page overflow.

Visual-acceptance score: 32/32. V-01 through V-16 each score 2; no hard gate scores 0. The pane
splitters support keyboard resize, the context has the approved 1366 px collapse behavior, and
column-resize seams are visible for the intended production mapping.

Independent main-agent command results:

- deterministic recapture: passed with the registered SHA-256 unchanged;
- reference validator: 66/66 initial checks and 67/67 accepted-lifecycle checks passed;
- documentation user-guide check: passed;
- documentation impact check in worktree mode: passed;
- Ruff, JavaScript syntax, and `git diff --check`: passed;
- console errors, page errors, nested persistent cards, and page overflow: zero.

The bounded fresh reviewer packet is
`docs/17-evidence/reports/issue-167-reviewer-packet-01.md`.

Fresh GPT-5.6 Terra High read-only review returned `approve`, 32/32, no hard-gate failure, no
findings, and no residual concern. The product owner approved this image in conversation on
2026-07-28.

## Image disposition

Reference image:
[materials-search-normal-1440x900.png](../images/issue-167-service-reference/materials-search-normal-1440x900.png)

| Target | Main-agent evaluation | Product-owner status | Date |
| --- | --- | --- | --- |
| `materials-search-normal-1440x900` | accepted (32/32) | approved | 2026-07-28 |

## Current execution handoff for approval unit 02

The repository-local custom agents are enabled by `.codex/config.toml`, and the active execution
surface exposes the exact configured `implementer_luna_max`, `reviewer_terra_high`, and
`correction_terra_high` roles. The statement in the original approval-unit-01 execution record about
Luna availability describes that prior run only. It does not apply to this continuation. Approval
unit 02 therefore uses one `implementer_luna_max` writer followed, after deterministic and
main-agent gates, by one fresh read-only `reviewer_terra_high`.

The product owner has already approved
`Materials / search-results / normal / 1440×900`. That image, its measurements, manifest lifecycle,
and SHA-256 are frozen inputs. They must not be regenerated, resubmitted, or changed.

## Main-agent source inspection for approval unit 02

The main agent directly inspected:

- issue #167 and the repository instructions, current branch, uncommitted handoff, documentation
  manifest, reference manifest, and approval-unit-01 evidence;
- the approved original-resolution
  `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`;
- the current original-resolution
  `docs/user-guide/images/current/materials-search-1366x768.png` and
  `docs/user-guide/images/current/materials-search-1440x900.png`;
- the historical responsive comparison
  `docs/17-evidence/images/uxc-00d-responsive-design/materials-1366x768.png`;
- the governed navigator/list references
  `docs/00-research/images/gui-reference/granta-profile.png` and
  `docs/00-research/images/gui-reference/granta-list-results.png`;
- `MaterialSearchPage`, `MaterialsBrowseTree`, `ResizableSplitPane`,
  `EngineeringColumnResizeHandle`, `listMaterials()`, the Catalog material query repository/API,
  current navigation contract, UI specification, product specification, and visual rubric.

The preserved production contracts are:

- `draftQuery → query → listMaterials()` with URL-preserved query, mode, sort, offset, and selection;
- one fail-closed organization/project/classification-scoped server query for rows, total, and
  material-class facets;
- Database/Profile/Table/Folder/Record navigation with independent tree search, exact Record
  selection, roving focus, arrow/Home/End/Enter behavior, and virtualized rows;
- local compare selection distinct from row selection; row selection updates context in place;
- compact viewport defaults from `ResizableSplitPane` and
  `docs/user-guide/navigation-contract.yaml`: 244 px navigator, 1,102 px nominal main region, and
  Context collapsed before the result grid is compressed;
- user-visible normal search fields limited to Material/grade, Family, Description, and Status.

The approved shared static source already implements the compact breakpoint at `max-width: 1399px`:
244 px navigator, one 5 px navigator divider, dominant result grid, and hidden optional Context.
Approval unit 02 derives from that existing responsive source. It is not authorization to revise the
approved 1440×900 topology or production React/CSS.

## Authoring packet 02 — Materials search / normal / 1366×768

### Exact target and ownership

Create exactly one new approval image:

`materials-search-normal-1366x768`

The single writer owns only the bounded capture/validation/registration work below. Do not create a
1920×1080 image or any other screen/state. Do not edit production React/CSS, backend, API, domain
data, current user-guide screenshots, the incoming package, GitHub, or approval-unit-01 lifecycle
evidence.

Expected changed or added paths:

- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.measurements.json`

Capture registration: [materials-search-normal-1366x768.png](../images/issue-167-service-reference/materials-search-normal-1366x768.png)

The approved shared sources are inputs and must remain byte-identical:

- `docs/00-research/ux-service-reference/materials-search-normal.html`
- `docs/00-research/ux-service-reference/reference.css`
- `docs/00-research/ux-service-reference/reference.js`

The approved 1440×900 PNG, measurement JSON, manifest entry, and registered SHA-256
`8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b` must remain unchanged.
Do not run the 1440 capture target. If the existing responsive source cannot satisfy this packet,
stop and report the exact deterministic failure instead of redesigning it.

### User task and visible result

A User searches for `steel`, scans six authorized synthetic results beside the governed hierarchy,
keeps the selected DP780 row visible, and can use Enter on that row to expose the datasheet
consequence. At this compact viewport the optional selected-material Context is intentionally
collapsed before the grid is compressed. The selected human name/code and revision remain visible in
the status bar. This is the product-spec compact behavior, not missing content.

Preserve exactly the approved copy, six synthetic rows, governed column inventory, selected row/tree
state, flat dividers, and one filled `Find` command. Do not add a compact-only banner, inspector
replacement, card, toolbar, floating command, unsupported property/card claim, or technical
identifier. Do not expose provider/manufacturer/source, Yield, condition, property values, solver or
card readiness, validation/approval/release, or download.

### Responsive acceptance at 1366×768

- exact browser viewport 1366×768 at device scale factor 1;
- application/command/search/status heights 46/38/40/24 px;
- 8 px left and right workspace margins;
- navigator 244 px;
- visible navigator divider 5 px hit region with 1 px visual rule;
- result region 1,101 px, at least 720 px, and the dominant workspace area;
- selected Context and its divider not visible in the captured compact default;
- tree rows 25 px and result rows 36 px;
- six visible result rows, exactly one selected result row and one selected Record tree row;
- sticky governed headers `Compare | Material / grade | Family | Description | Status`;
- one filled primary command, zero nested persistent cards, zero page-level overflow;
- no clipping or overlap in the application bar, search, tree, grid headers/rows, or status bar;
- `Ctrl/Cmd+K`, search submit, tree Up/Down/Home/End/Enter, and result-row Enter all pass even while
  optional Context is collapsed.

The measurement JSON must record the compact Context as collapsed/not visible rather than fabricating
a zero-width visible pane. Hidden regions may be represented as `null` or an explicit collapsed
state, but the target-specific validator must check that representation deterministically.

### Capture and validation implementation

Extend the existing scripts to use per-target configuration instead of a single hard-coded viewport.
Both the approved 1440 target and the new 1366 target must remain valid CLI choices. Target-specific
configuration must own viewport, image/measurement paths, navigator width, Context visibility and
width, expected divider count, and expected result width or safe range. Shared content and
interaction assertions remain shared.

`capture_reference.py` must capture only the requested target, wait for
`document.fonts.ready`, measure only visible splitters, fail on console/page errors, assert the
target-specific compact topology, and write a viewport screenshot rather than a full-page image.
It must not rewrite or touch another target's files.

`validate_reference.py` must resolve expected paths and dimensions by target, verify one unique
manifest entry, source paths, PNG dimensions, measurement target/viewport/hash, date and lifecycle,
the approved forbidden-term/column/copy contract, console/page errors, interactions, and zero
overflow. For the new target it must require `status: pending`,
`main_agent_evaluation.status: pending` with no notes, and no product-owner approval. For the
existing target it must continue to accept the recorded approved/accepted lifecycle without
weakening its checks.

Register the new manifest entry with the shared source paths, exact 1366×768 viewport, generated
image/measurement paths, computed SHA-256, date `2026-07-28`, `status: pending`, pending main-agent
evaluation, and no product-owner approval.

### Required deterministic commands

Run and report all results:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Also compute and report the current SHA-256 of both PNGs and confirm the approved 1440 hash above is
unchanged. Do not run `make docs-screenshots`; there is no production visual change. Do not commit,
push, open a PR, merge, write to GitHub, or request product-owner approval. Return changed paths,
measurements, command results, and residual concerns to the main agent.

## Main-agent evaluation 02

The main agent independently reran the 1366×768 capture, opened the resulting PNG at original
resolution, and compared it with the approved 1440×900 reference, current 1366×768 product capture,
historical responsive proposal, and governed tree/list references.

The compact reference preserves the same task and hierarchy as the approved standard viewport while
applying the authoritative compact rule: a 244 px navigator, 5 px accessible divider, 1,101 px
dominant result grid, and optional Context collapsed before result compression. Query, complete
authorized result count, six rows, selected DP780 row, selected tree Record, status, and the
row-Enter datasheet consequence remain available. The first viewport has no overlap, clipping that
loses task meaning, nested persistent cards, or page-level overflow. Truncated tree text retains its
full title and the selected identity remains readable in the grid and status bar.

Visual-acceptance score: 32/32. V-01 through V-16 each score 2; no hard gate scores 0. V-05 passes
through the approved compact Context-collapse behavior and visible navigator divider. V-12 passes
because selection updates the same row/context/status state without remounting, while the compact
default intentionally keeps optional Context closed. V-16's legacy selector inventory is zero.

Independent main-agent results:

- deterministic 1366 recapture: passed; navigator/results/context = 244/1,101/collapsed;
- 1366 reference validator: 84/84 checks passed with pending product-owner lifecycle;
- frozen 1440 validator: 86/86 checks passed; approved SHA-256 unchanged;
- Ruff and JavaScript syntax: passed;
- user-guide image/link/manifest check: passed;
- worktree documentation-impact check: passed with 0 production visual sources;
- whitespace check: passed;
- console errors, page errors, nested persistent cards, and page overflow: zero;
- latest Web Interface Guidelines audit: no new finding; shared approved HTML/CSS/JS was unchanged.

SHA-256:

- 1366×768:
  `e835d486d04e643d009e15cd6cb02b0009fdcafae75a950940ad5220970c63ea`;
- frozen approved 1440×900:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`.

The bounded fresh reviewer packet is
`docs/17-evidence/reports/issue-167-reviewer-packet-02.md`. Product-owner status remains pending.

## Approval-unit-02 disposition

Reference image:
[materials-search-normal-1366x768.png](../images/issue-167-service-reference/materials-search-normal-1366x768.png)

| Target | Main-agent evaluation | Product-owner status | Date |
| --- | --- | --- | --- |
| `materials-search-normal-1366x768` | accepted (32/32) | pending | 2026-07-28 |

## Correction packet 02-A — lifecycle validator transition

Status: one evidence-backed correction authorized after the deterministic main-agent gate

Observed failure:

```text
uv run python docs/00-research/ux-service-reference/validate_reference.py \
  --target materials-search-normal-1366x768 \
  --expect-main-agent-status accepted

FAIL main-agent-evaluation: expected 'pending', got 'accepted'
```

Cause boundary:

- `validate_reference.py` stores the authoring-time default
  `evaluation_status: pending` for the 1366 target;
- the main-agent evaluation correctly advanced the manifest entry to `accepted` with notes;
- the validator still unconditionally compares the manifest to the authoring-time default before
  applying `--expect-main-agent-status`, so its explicit lifecycle override cannot validate the
  post-evaluation state.

Exact correction:

- edit only `docs/00-research/ux-service-reference/validate_reference.py`;
- when `--expect-main-agent-status` is supplied, use it as the target's expected evaluation status;
- otherwise retain the per-target authoring-time default, so the initial pending gate remains
  deterministic;
- avoid duplicate or contradictory status checks and retain the existing pending-notes/completed-
  notes rules;
- do not edit the manifest, images, measurements, shared HTML/CSS/JS, evidence conclusions, or any
  production/current file.

Required gates:

```powershell
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/validate_reference.py
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Return the exact changed lines and command results. This is the sole correction pass for approval
unit 02. Do not commit, push, write to GitHub, start another writer, or request approval.

### Correction 02-A result

Fresh `correction_terra_high` changed only `validate_reference.py`: the explicit
`--expect-main-agent-status` now selects the expected lifecycle value, while omitting the option
retains each target's authoring-time default. The contradictory duplicate comparison was removed;
pending/completed notes rules remain intact.

The main agent independently reran the full bounded gates after the correction:

- 1366 accepted lifecycle: 84/84 checks passed;
- frozen 1440 accepted lifecycle: 86/86 checks passed;
- both registered image SHA-256 values unchanged;
- Ruff, JavaScript syntax, user-guide, documentation-impact, and whitespace checks passed;
- production visual sources changed: zero.

No further correction pass is available or required.

## Independent reviewer disposition 02

Fresh `reviewer_terra_high` completed the bounded read-only review on 2026-07-28 with `approve`.
V-01 through V-16 scored 2 each for 32/32; no hard gate scored 0. The reviewer independently reran
the 1366 84/84 and frozen 1440 86/86 validators, confirmed both registered hashes, and reported no
finding or residual compact-usability/reference-authority concern. Product-owner approval remains
unset.

## Product-owner review 02 — changes requested

The product owner reviewed the submitted 1366×768 image on 2026-07-28 and did not approve it. Two
visible defects override the earlier main-agent and independent-reviewer acceptance:

1. the submitted compact image removes the selected-material region that is present in the supplied
   service reference and in the already approved 1440×900 reference;
2. the right edges of the governed tree-kind labels `Database`, `Profile`, `Table`, `Folder`, and
   `Record` are clipped.

Direct source inspection confirms both causes. The `max-width: 1399px` rule in `reference.css`
explicitly hides `.context-divider` and `.selected-context`. The same compact rule reduces the
navigator to 244 px while `.material-tree` retains a 252 px minimum width, creating pane-local
horizontal overflow that the page-level overflow gate did not measure.

The current PNG remains registered only as an unapproved historical attempt. Its earlier 32/32
evaluation is superseded by the product-owner review and must not be presented again for approval.

### Main-agent service and engineering judgment

The local Granta and Altair Material Data Center references support a deliberate two-level pattern,
not indiscriminate column removal:

- Granta list results permit property columns to be selected, resized, sorted and pinned, but the
  engineering values carry quantity, unit, condition or range semantics. A condition-dependent
  property such as Yield must therefore never be a universal fixed column. If a later server-scoped
  metal query exposes Yield, the comparable condition and unit must travel with it.
- Altair and embedded Granta views keep a selected-record detail region beside the result set. This
  is useful for identity, classification, a small number of governed attributes, and the transition
  to full detail.
- A full property sheet, curve plot, linked data and solver-card evidence need the wider Datasheet
  workspace shown by Granta's full Datasheet. They must not be compressed into a 280 px context
  pane.

The platform decision is therefore:

- keep the search-result defaults `Material / grade | Family | Description | Status`;
- do not add fixed `Yield`, `Condition`, or `CAE Cards` columns to this normal search reference;
- restore the 280 px selected-material summary at 1366×768 with the supported identity,
  description, Family, Status, and `Open datasheet` action;
- keep the result grid wider than the selected context and at least 720 px;
- treat condition-aware property columns as later server-backed column choices, never client
  inference or unconditional fields;
- show the complete `Overview | Properties | Curves | CAE Cards | Related | Evidence` Datasheet in
  its own #167 detail approval unit, where the center result region changes in place and the
  navigator/query context remains recoverable.

With the 1,350 px workspace, 244 px navigator, two 5 px splitter hit areas and 280 px selected
context, the corrected result region is 816 px. This satisfies the 720 px safety rail and remains
wider than the optional context.

## Prepared visual re-authoring packet 02-B

Status: prepared by the main agent, but not executable without an explicit process exception because
correction 02-A is recorded above as the sole correction pass for approval unit 02.

Target exactly one replacement approval image:

`materials-search-normal-1366x768`

Preserve byte-for-byte:

- approved `materials-search-normal-1440x900.png` and SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- approved shared `materials-search-normal.html`, `reference.css`, and `reference.js`;
- production React/CSS, API/state contracts, current user-guide captures, and all other #167
  approval units.

Use a target-specific static CSS override for the 1366 capture rather than changing the shared
approved source. The bounded author may change only:

- one new target-specific 1366 CSS source;
- `capture_reference.py` and `validate_reference.py`;
- the 1366 manifest entry;
- the 1366 PNG and measurement JSON.

Required visual result:

- 244 px navigator, 5 px divider, 816 px result grid, 5 px divider, 280 px selected context;
- selected context visibly contains the supported selected-material summary and `Open datasheet`;
- all `Database`, `Profile`, `Table`, `Folder`, and `Record` kind labels are fully visible;
- the tree scroller has zero horizontal overflow, and every visible `.tree-kind` right edge remains
  inside the navigator content edge;
- default result headers remain exactly `Compare`, `Material / grade`, `Family`, `Description`,
  `Status`;
- result rows may truncate descriptive text but must preserve full Material identity through the
  existing title/grade contract;
- no fixed Yield, Condition or CAE Cards column, no inferred property/card state, no full Datasheet
  squeezed into the context pane, no nested cards, overlap, clipping or page overflow.

The capture and validator must record and assert context visibility, both splitters, exact region
widths, tree-scroller horizontal overflow, tree-kind edge containment, the unchanged governed
headers, interaction consequences, and zero console/page errors. After recapture, reset the 1366
manifest lifecycle to `status: pending` and `main_agent_evaluation.status: pending` with no
product-owner approval. Recompute only the 1366 image hash.

The bounded deterministic gates are:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Do not create any other image, edit production sources, commit, push, open a PR, write to GitHub, or
request approval. A fresh read-only review may begin only after the deterministic and direct
main-agent image gates pass.

### Product-owner process exception and correction 02-B result

The product owner explicitly approved treating correction 02-A as a validator-only incident outside
the visual-correction count. The approved exception allowed exactly one fresh
`correction_terra_high` visual writer for packet 02-B and, if the deterministic and main-agent gates
passed, exactly one fresh read-only `reviewer_terra_high`. It did not change model roles, permit a
second concurrent writer, or authorize any later image, commit, push, PR, merge, GitHub write, or
production React/CSS work.

The single visual correction writer changed only:

- `docs/00-research/ux-service-reference/materials-search-normal-1366x768.css`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- the 1366 entry in `docs/01-product/service-reference-manifest.yaml`;
- the 1366 PNG and measurement JSON.

The target-only stylesheet restores the 280 px selected context and gives the 244 px navigator tree
zero internal minimum-width overflow. The approved shared HTML/CSS/JS remain byte-identical, and the
approved 1440 PNG remains byte-identical.

### Main-agent evaluation 02-B

The main agent independently reran the capture and every bounded deterministic gate, then opened the
corrected 1366 PNG and approved 1440 PNG at original resolution and compared them directly with the
local Granta list/embedded/full Datasheet and Altair search/detail references.

Observed corrected topology:

- navigator: 244 px;
- navigator divider: 5 px hit area / 1 px visible rule;
- result grid: 816 px;
- context divider: 5 px hit area / 1 px visible rule;
- selected-material context: 280 px;
- tree and result rows: 25 px and 36 px;
- visible splitters: 2;
- page and tree horizontal overflow: 0;
- all seven tree-kind right edges: 245 px, within the 252 px navigator content edge;
- selected result row, selected tree Record, selected summary and `Open datasheet`: present;
- default result columns:
  `Compare | Material / grade | Family | Description | Status`;
- filled primary commands: 1;
- nested persistent cards, console errors and page errors: 0;
- search shortcut, tree keyboard path and result Enter Datasheet consequence: passed.

Independent gate results:

- 1366 deterministic recapture: passed;
- 1366 validator with pending lifecycle: 89/89;
- frozen 1440 validator with accepted lifecycle: 87/87;
- Ruff and JavaScript syntax: passed;
- user-guide image/link/manifest check: passed;
- worktree documentation-impact check: passed with 0 production visual sources;
- whitespace check: passed.

SHA-256:

- corrected 1366 PNG:
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`;
- frozen approved 1440 PNG:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- frozen shared HTML:
  `ff9f6367f2369778734f7255ca5beb7ac86508dbf215cf6133721ce60cfe5988`;
- frozen shared CSS:
  `0f09dae7b9350e73613d21b3c2694e609b71b9486ecfd3c8546fcd691758b589`;
- frozen shared JavaScript:
  `788cb8278e7bc50dd2cdee8bad06517488bd8a6fffb04af2424fc32321c7c2af`.

Main-agent visual acceptance: 32/32. V-01 through V-16 each score 2 and no hard gate scores 0. The
result grid remains the dominant task region despite restoring context; every governed tree kind is
readable; no engineering property is shown without condition/unit semantics; and full attributes,
curves, links and CAE Cards remain assigned to the later Datasheet approval unit rather than being
compressed into the search inspector.

The manifest main-agent evaluation is now `accepted`; the reference itself remains `pending` and has
no product-owner approval. A fresh read-only review is the next permitted action.

### Fresh read-only reviewer disposition 02-B

Fresh `reviewer_terra_high` returned `changes_requested`, V-05 = 0 and all other criteria = 2, for
30/32. No hard-gate criterion scored zero. The reviewer confirmed that the two product-owner visual
findings are resolved and found no additional condition/unit semantics or source-authority issue.

The remaining defect is functional. The target-only CSS fixes the complete grid to
`244px 5px 816px 5px 280px`, while the preserved splitter keyboard handler changes only
`--navigator-width` or `--context-width`. The ARIA value therefore changes without a visible layout
change. The capture gate does not currently exercise splitter resizing.

The main agent independently reproduced the finding:

```text
initial      [244, 816, 280]  navigator aria=264  context aria=280
nav-right    [244, 816, 280]  navigator aria=272  context aria=280
context-left [244, 816, 280]  navigator aria=272  context aria=288
```

This is not acceptable for engineering software: a visible separator with a resize affordance must
change the corresponding workspace geometry, keep its ARIA value synchronized, and retain enough
result width to compare data. The corrected image is not submitted for product-owner approval. The
manifest main-agent evaluation is superseded to `rejected`; product-owner approval remains unset.

The product-owner-approved exception authorized one visual correction and one fresh re-review. Both
have now been consumed, so no further writer or reviewer may be started without another explicit
process exception.

## Product-owner exception and correction packet 02-C

The product owner explicitly authorized one additional fresh `correction_terra_high` visual writer
and, only after deterministic and direct main-agent acceptance, one additional fresh read-only
`reviewer_terra_high`. This exception is limited to the V-05 splitter defect in the same
`materials-search-normal-1366x768` approval unit. It does not authorize another image, a different
model/role, concurrent writers, production React/CSS, commit, push, PR, merge, or GitHub write.

Status: ready for exactly one writer

### Exact defect and engineering decision

The failed 1366 override fixes the complete grid to
`244px 5px 816px 5px 280px`. The preserved shared handler changes
`--navigator-width`/`--context-width`, so ARIA state changes without a visible layout consequence.
The initial navigator is also visually 244 px while the inherited `aria-valuenow` remains 264.

Do not patch this with another fixed grid, hide the splitters, merely alter ARIA, weaken V-05, or
change only the screenshot. A visible engineering-workspace separator must:

- move the corresponding pane on ArrowLeft/ArrowRight/Home/End;
- keep `aria-valuenow` equal to the actual pane width;
- expose a truthful current `aria-valuemin`/`aria-valuemax`;
- keep the selected context visible;
- keep the result grid at least 720 px;
- keep page and tree horizontal overflow at zero;
- preserve tree-kind containment and the approved information boundary.

The 1,350 px workspace has two 5 px splitter hit areas. With a 720 px minimum result region, the
combined navigator and context budget is 620 px. Starting widths remain navigator 244 px, results
816 px and context 280 px. Dynamic maxima therefore depend on the other pane:

```text
navigator maximum = min(360, 620 - current context width)
context maximum   = min(480, 620 - current navigator width)
```

At the default state the truthful maxima are navigator 340 px and context 376 px. Navigator End and
Context End must each produce a 720 px result region without clipping or overflow.

### Bounded implementation ownership

Preserve byte-for-byte:

- `materials-search-normal.html`;
- shared `reference.css` and `reference.js`;
- approved 1440 PNG, measurement JSON and SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- production React/CSS, API/state contracts, current user-guide captures and all other #167 units.

The single writer may change only:

- `docs/00-research/ux-service-reference/materials-search-normal-1366x768.css`;
- one new target-specific
  `docs/00-research/ux-service-reference/materials-search-normal-1366x768.js`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- the 1366 manifest entry;
- the 1366 PNG and measurement JSON.

Register the target-specific JavaScript as `sources.javascript_override` and inject it only for the
registered 1366 capture, after the target CSS. It must own 1366 splitter key handling without editing
the frozen shared handler. A document capture-phase handler may stop the inherited splitter event
before the target listener, then apply the bounded variable layout. Do not block unrelated keyboard
events.

The 1366 CSS must use the live variables rather than fixed pane columns:

```css
:root {
  --navigator-width: 244px;
  --context-width: 280px;
}

.materials-workspace {
  grid-template-columns:
    var(--navigator-width)
    var(--splitter-hit)
    minmax(720px, 1fr)
    var(--splitter-hit)
    var(--context-width);
}
```

Retain the existing context visibility and zero-minimum-width tree corrections.

The target JavaScript must initialize ARIA from the actual 244/280 pane widths, update both dynamic
maxima whenever either pane moves, clamp Home/End and arrow moves to the truthful range, write CSS
variables and ARIA together, and leave the result region at or above 720 px. Layout reads and writes
must be bounded to initialization and splitter input; do not add polling or animation.

### Deterministic interaction evidence

Enhance `capture_reference.py` so the registered 1366 target exercises the target script before
capturing the normal default image. It may reload and reinject the registered target overrides
between bounded interaction sequences so the final screenshot returns to the 244/816/280 default.
Record exact before/after geometry and ARIA evidence in the measurement JSON.

At minimum assert:

```text
default:       navigator/results/context = 244/816/280; aria now = 244/280
navigator +8:  navigator/results/context = 252/808/280; navigator aria now = 252
navigator Home: navigator = 200; result >= 720; aria now = 200
navigator End:  navigator = 340; result = 720; aria now/max = 340
context +8:    navigator/results/context = 244/808/288; context aria now = 288
context Home:  context = 260; result >= 720; aria now = 260
context End:   context = 376; result = 720; aria now/max = 376
```

For every exercised state assert page overflow zero, selected context visible, results at least
720 px, and visible/ARIA widths synchronized. The final default capture must still assert:

- navigator/results/context 244/816/280;
- two functional splitters;
- tree horizontal overflow zero and all tree-kind right edges inside the navigator content edge;
- selected-material summary and `Open datasheet`;
- governed default columns only;
- six result rows, one selected result/tree row, one primary command, no nested cards;
- search, tree keyboard and result Enter Datasheet consequences;
- no console or page errors.

Update `validate_reference.py` to require the target JavaScript source registration and all stored
splitter evidence. Do not weaken the approved 1440 lifecycle/hash checks. Reset only the 1366
manifest lifecycle to `status: pending`, `main_agent_evaluation.status: pending`, no notes and no
product-owner approval, then recompute only the 1366 PNG hash.

### Required gates

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1366x768.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Report exact changed paths, default and extreme measurements, both PNG hashes, all command results
and residual concerns. Do not create or submit another image, edit production sources, commit, push,
write to GitHub, start another agent, or request product-owner approval.

### Correction 02-C result and main-agent evaluation

The single authorized `correction_terra_high` writer changed only the packet-owned 1366 target CSS,
new target JavaScript, capture/validator, 1366 manifest entry, PNG and measurement JSON. Shared
HTML/CSS/JavaScript, approved 1440 assets and production sources remain byte-identical.

The main agent independently audited the target code, reran the registered capture and all bounded
gates, used a separate native Playwright exercise for every required splitter state, and opened the
1366 and approved 1440 PNGs at original resolution.

Independent splitter reproduction:

```text
default:        widths 244/816/280; navigator now/max 244/340; context now/max 280/376
navigator +8:   widths 252/808/280; navigator now/max 252/340
navigator Home: widths 200/860/280; navigator now/max 200/340
navigator End:  widths 340/720/280; navigator now/max 340/340
context +8:     widths 244/808/288; context now/max 288/376
context Home:   widths 244/836/260; context now/max 260/376
context End:    widths 244/720/376; context now/max 376/376
```

Every state kept page/body horizontal overflow at zero, the selected context visible, actual pane
width equal to `aria-valuenow`, and results at or above 720 px. The target capture-phase listener
handles only splitter ArrowLeft/ArrowRight/Home/End input; ordinary search, tree and result keyboard
paths still pass.

Independent gate results:

- 1366 deterministic recapture: passed;
- 1366 validator with pending lifecycle: 148/148;
- frozen 1440 validator with accepted lifecycle: 88/88;
- Ruff and both shared/target JavaScript syntax checks: passed;
- user-guide and documentation-impact checks: passed, with 0 production visual sources;
- whitespace check: passed;
- shared HTML/CSS/JavaScript SHA-256 values unchanged;
- approved 1440 PNG SHA-256 unchanged:
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- corrected 1366 PNG SHA-256:
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`.

The default PNG is byte-identical to the visually corrected 02-B image because 02-C corrects the
previously false splitter affordance without changing the default geometry. Direct image review
confirms the selected-material context, readable governed tree kinds, dominant 816 px result region,
restrained flat density, supported default columns and absence of overlap/clipping.

Latest Web Interface Guidelines audit: no new finding. The target listener has a visible semantic
separator as its exact input, handles keyboard state and ARIA together, and performs bounded layout
reads only during initialization and explicit splitter input.

Main-agent visual acceptance: 32/32. V-01 through V-16 each score 2; no hard gate scores zero.
Manifest main-agent evaluation is `accepted`; reference status remains `pending` and product-owner
approval is unset. The next permitted action is one fresh read-only review against a new bounded
reviewer packet.

### Fresh read-only reviewer disposition 02-C

Fresh `reviewer_terra_high` independently returned `approve`, 32/32, with V-01 through V-16 each
scoring 2, no hard-gate zero, no actionable finding and no residual concern.

The reviewer reran the 1366 148-check and frozen 1440 88-check validators, confirmed both hashes,
opened both images at original resolution, independently exercised both splitters through default,
Arrow, Home and End, and verified ordinary search/tree/result keyboard paths plus in-place selected
context updates. Actual pane width, dynamic ARIA, 720 px minimum result width, zero
document/body/tree overflow, target-only source registration, frozen shared/1440 authority and the
condition/unit information boundary all passed.

Approval unit 02 is ready for product-owner review. Only the corrected
`materials-search-normal-1366x768.png` may be submitted. Reference status remains `pending`;
product-owner approval is unset. No later image, commit, push, PR, merge, GitHub write or production
React/CSS work is authorized before the product owner responds.

### Product-owner approval 02

The product owner approved correction 02-C in conversation on 2026-07-28. Manifest status is now
`approved` with the exact image SHA-256
`b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`.

The next unapproved same-screen responsive approval unit is
`Materials / search-results / normal / 1920×1080`. It must begin as a new main-agent packet and use
one configured Luna Max implementer, deterministic gates, direct main-agent image review, a separate
reviewer packet and one fresh Terra High read-only reviewer. The two approved 1440×900 and 1366×768
images, their source registrations, measurements, hashes and lifecycle records are frozen inputs and
must not be regenerated, resubmitted or changed.

## Implementer packet 03 — Materials search normal 1920×1080

Status: ready for exactly one configured `implementer_luna_max` writer

Approval unit:

```text
Materials / search-results / normal / 1920×1080
```

Reference image:
[materials-search-normal-1920x1080.png](../images/issue-167-service-reference/materials-search-normal-1920x1080.png)

This is the next unapproved #167 reference. It is a new responsive approval unit, not permission to
change production React/CSS or to revisit either approved image.

### Main-agent source and contract review

The main agent directly inspected GitHub #167, the two approved images at original resolution,
their registered static sources and measurements, the current `/materials` React workspace,
`listMaterials` request/response state, URL restoration, row/tree selection and Datasheet navigation,
the responsive pane contract, current 1920 live capture, and the Granta and Altair research images.

The exact frozen visual inputs are:

- approved 1440×900 PNG SHA-256
  `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`;
- approved 1366×768 PNG SHA-256
  `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`;
- shared HTML SHA-256
  `ff9f6367f2369778734f7255ca5beb7ac86508dbf215cf6133721ce60cfe5988`;
- shared CSS SHA-256
  `0f09dae7b9350e73613d21b3c2694e609b71b9486ecfd3c8546fcd691758b589`;
- shared JavaScript SHA-256
  `788cb8278e7bc50dd2cdee8bad06517488bd8a6fffb04af2424fc32321c7c2af`.

The current application contract preserves:

- one continuous navigator/result/selected-context workspace;
- Database → Profile → Table → Folder → Record browsing and keyboard selection;
- URL-restored query, family, sort, direction, mode, selected material and offset;
- rows, total and material-class facet counts from the same scoped server request;
- result selection updating the context pane without replacing the result grid;
- Enter, double click and `Open datasheet` navigating to the selected Datasheet;
- Compare, Material/grade, Family, Description and Status as the normal default columns.

The production wide contract is navigator 280 px, optional context 300 px and a result region no
smaller than 720 px. The static shell has 8 px horizontal workspace padding and two 5 px splitter
hit areas, so its exact 1920 default geometry is:

```text
navigator / results / context = 280 / 1314 / 300 px
workspace = 1904 px
```

The static geometry is evidence for topology and dominance, not a replacement for the production
component's own container calculation.

### Engineering and information-boundary decision

Do not add fixed Yield, Condition, CAE Card, provider, mapping, approval or release columns merely
because the wide viewport has room. Yield is condition-dependent and valid only when a compatible
server projection supplies property definition, value, unit, condition and source. The existing
search response does not supply that governed projection. Inventing those columns would make the
wide screenshot look denser while teaching a false domain contract.

Use the additional width to improve row scanning and Description continuity. Keep the selected
material summary at 300 px with its supported identity, Family, Status and `Open datasheet`
consequence. Full attribute tables, conditions, units, curves, linked data and solver-card evidence
belong to the later Materials Datasheet/detail/card approval units. This follows the useful part of
Granta/Altair: stable search context plus a deliberate detail transition, without copying a
property-rich result schema that this service does not yet provide.

### Static region to application/contract mapping

| Static reference region | Existing application/contract to preserve |
| --- | --- |
| application and command bars | `/materials` normal-user shell and compact Materials title |
| search band | server-scoped query plus URL-restored search state |
| 280 px navigator | governed catalog scope and Database/Profile/Table/Folder/Record tree |
| 1314 px result region | `MaterialSearchPage` result table, total, selection and compare behavior |
| 300 px selected context | selected row summary and explicit Datasheet navigation |
| two separators | `ResizableSplitPane` navigator/context keyboard resize contract |
| status bar | unobtrusive workspace status, not a competing task card |

### Target-specific implementation

Preserve byte-for-byte:

- `materials-search-normal.html`, `reference.css` and `reference.js`;
- both approved PNGs, measurement JSON files, SHA-256 values, source registrations, accepted
  main-agent evaluations and product-owner approvals;
- the approved 1366 target CSS and JavaScript;
- all production React/CSS/API/state sources and current user-guide captures;
- every other #167 approval unit.

The single writer may change only:

- one new
  `docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js`;
- `docs/00-research/ux-service-reference/capture_reference.py`;
- `docs/00-research/ux-service-reference/validate_reference.py`;
- the new 1920 entry in `docs/01-product/service-reference-manifest.yaml`;
- one new 1920 PNG and one new measurement JSON under
  `docs/17-evidence/images/issue-167-service-reference/`.

No target CSS override is required: the frozen shared `@media (min-width: 1700px)` rule already
sets the required 280/300 widths. The HTML's inherited navigator `aria-valuenow="264"` and context
`aria-valuenow="280"` are not truthful at this viewport. Add a target-only JavaScript initializer,
registered as `sources.javascript_override`, which reads the rendered navigator and selected-context
widths once after target injection and synchronizes only the two separators' `aria-valuenow`.
The shared handler must continue to own ArrowLeft/ArrowRight/Home/End behavior and the existing
200–360 navigator and 260–480 context ranges. Do not duplicate its event handler, use polling, alter
HTML, or hide the resize affordance.

Generalize the capture's splitter exercise by target configuration instead of adding another
target-id-only branch. The final normal screenshot must be taken after a clean reload and target
override reinjection, at the default 280/1314/300 geometry. Register and capture only
`materials-search-normal-1920x1080`; do not recapture approved targets.

### Deterministic interaction evidence

The new measurement JSON must store and the capture/validator must assert:

```text
default:         280 / 1314 / 300; aria now 280 / 300; max 360 / 480
navigator +8:    288 / 1306 / 300; navigator aria now 288
navigator Home:  200 / 1394 / 300; navigator aria now 200
navigator End:   360 / 1234 / 300; navigator aria now/max 360
context +8:      280 / 1306 / 308; context aria now 308
context Home:    280 / 1354 / 260; context aria now 260
context End:     280 / 1134 / 480; context aria now/max 480
```

For every splitter state, assert actual pane widths equal ARIA current values, both ARIA ranges stay
truthful, the selected context remains visible, result width stays at least 720 px and page/body
horizontal overflow is zero. For the final default capture also assert:

- exact viewport 1920×1080 and default region geometry 280/1314/300;
- exactly two visible 1 px divider lines inside 5 px keyboard hit areas;
- tree horizontal overflow zero and every Database/Profile/Table/Folder/Record kind fully contained;
- result grid is the dominant area, with six dense rows and no nested cards;
- default columns remain exactly Compare, Material/grade, Family, Description and Status;
- no forbidden visible Yield/Condition/CAE/provider/mapping/approval/release terms;
- one selected result/tree record, selected summary and `Open datasheet`;
- search, tree keyboard, row selection and result Enter/Datasheet consequences;
- one primary command and no console or uncaught page errors.

Update the validator lifecycle expectations so the two frozen references require
`status: approved` and accepted main-agent evaluation. The new 1920 manifest entry starts with
`status: pending`, `main_agent_evaluation.status: pending`, no evaluation notes and no
`product_owner_approval`. Record the exact shared sources, the target-only JavaScript, PNG,
measurement path, viewport, date and computed PNG SHA-256.

### Forbidden shortcuts

Do not edit production code, introduce target CSS, change shared or approved target sources, weaken
existing checks, change test expectations to tolerate clipping, generate a different visual design,
add unsupported engineering data, embed the PNG, edit another approval unit, commit, push, create a
PR, merge, write to GitHub, start another agent, or request product-owner approval.

### Required gates

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_reference.py --target materials-search-normal-1920x1080
uv run python docs/00-research/ux-service-reference/validate_reference.py --help
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_reference.py docs/00-research/ux-service-reference/validate_reference.py
node --check docs/00-research/ux-service-reference/reference.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1366x768.js
node --check docs/00-research/ux-service-reference/materials-search-normal-1920x1080.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Report exact changed paths, all default/extreme measurements, the two frozen and new PNG hashes,
every command result and residual concerns. Stop after implementation and local gates; the main
agent owns direct image judgment, reviewer packet creation and reviewer authorization.

### Implementer result 03 and main-agent rejection

The configured `implementer_luna_max` loaded successfully and completed only the packet-owned
1920 source registration, one-time ARIA initializer, generalized capture/validator, pending manifest
entry, PNG and measurement JSON. The writer reported all required gates passing. The main agent
independently reran the 1920 capture and every gate:

- 1920 pending validator: 147/147;
- frozen 1440 accepted validator: 88/88;
- frozen 1366 accepted validator: 150/150;
- Ruff, all JavaScript syntax checks, user-guide inventory, documentation impact and whitespace:
  passed;
- shared HTML/CSS/JavaScript and both approved PNG hashes: unchanged;
- new 1920 PNG SHA-256:
  `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`.

The main agent opened the 1920, approved 1440 and approved 1366 PNGs at original resolution. The
1920 default image preserves the continuous 280/1314/300 workspace, dominant result region, readable
default tree kinds, selected-material summary, supported five columns, flat density and absence of
unsupported property/card fields. Ordinary search, tree Home/End/Arrow/Enter, result selection,
context update and Datasheet consequence also pass without browser errors.

The main agent then used a separate native Playwright session rather than the stored measurement
JSON. Default, Arrow and maximum pane states matched the packet, but navigator Home exposed a
functional responsive defect:

```text
navigator Home: widths 200/1394/300; aria now 200/300
document overflow 0; body overflow 0; tree horizontal overflow 52
tree content edge 208; every tree-kind right edge 253
```

At the registered 200 px minimum, the base `.material-tree { min-width: 252px; }` pushes
Database/Profile/Table/Folder/Record kinds beyond the visible navigator. This recreates the exact
class of clipping the product owner previously identified. A valid ARIA value and a large result
region do not make the pane usable when governed catalog kinds disappear.

Main-agent disposition: `rejected`. No reviewer is authorized for this implementation. Reference
status remains `pending`, product-owner approval remains unset, and no image is submitted.

## Sole correction packet 03-A — 1920 navigator minimum containment

Status: ready for exactly one fresh configured `correction_terra_high` writer

This is the one correction allowed for approval unit
`Materials / search-results / normal / 1920×1080`. It addresses only the independently reproduced
tree containment defect. It does not authorize redesign, another model/role, a second correction,
production code, another reference unit, commit, push, PR, merge or GitHub write.

### Exact correction

Add one target-only stylesheet:

```text
docs/00-research/ux-service-reference/materials-search-normal-1920x1080.css
```

Its only layout correction must allow the existing grid row tracks to shrink inside the resizable
navigator:

```css
.material-tree {
  min-width: 0;
}
```

A short capture-only comment is allowed. Do not change pane defaults/ranges, spacing, typography,
colors, row content or any shared source. Register it as `sources.css_override` for the 1920 target
and inject it only for that registered capture. Keep the existing 1920 JavaScript initializer and
the shared splitter handler unchanged.

The main agent separately injected this rule in memory at navigator Home and measured:

```text
navigator/results/context = 200/1394/300
tree horizontal overflow = 0
tree content edge = 208
tree-kind right edges = 201
```

This demonstrates a bounded correction; it is not authority to make additional changes.

### Bounded correction ownership

Preserve byte-for-byte every shared source, the approved 1440 and 1366 sources/assets/lifecycle,
production code and all other #167 units. The sole correction writer may change only:

- new `materials-search-normal-1920x1080.css`;
- `capture_reference.py`;
- `validate_reference.py`;
- only the 1920 manifest entry;
- only the 1920 PNG and measurement JSON.

Do not edit the 1920 JavaScript unless a syntax/source-registration correction is necessary; no such
defect is currently known. Do not edit this packet.

### Strengthened deterministic evidence

For every stored 1920 splitter state—not only the final default—capture and validate:

- tree scroller horizontal overflow equals zero;
- every `.tree-kind` right edge is at or inside the navigator/tree content edge;
- page/body horizontal overflow equals zero;
- actual navigator/context widths equal ARIA current values;
- result width remains at least 720 px and selected context remains visible.

The required 1920 pane/ARIA values remain exactly:

```text
default          280/1314/300; now 280/300; max 360/480
navigator +8     288/1306/300; now 288/300
navigator Home   200/1394/300; now 200/300
navigator End    360/1234/300; now 360/300
context +8       280/1306/308; now 280/308
context Home     280/1354/260; now 280/260
context End      280/1134/480; now 280/480
```

After the correction, reset only the 1920 main-agent evaluation to `pending` with no notes; keep
reference status `pending` and product-owner approval absent. Recompute the 1920 PNG hash even if the
default image is byte-identical.

Run every gate from implementer packet 03 with 1920 expected `pending`, 1440 and 1366 expected
`accepted`, plus JavaScript syntax checks. Report exact paths, all seven pane/ARIA/tree states, all
three PNG hashes, every gate result and residual concern, then stop. Do not start a reviewer or ask
for product-owner approval.

### Correction 03-A result and main-agent evaluation

The one fresh configured `correction_terra_high` writer added only the registered 1920 target CSS,
strengthened capture/validator tree evidence, reset the 1920 lifecycle, and recaptured its PNG and
measurement JSON. The target rule is exactly `.material-tree { min-width: 0; }`; it changes no
default geometry or visible styling.

The main agent independently audited the correction, reran the 1920 capture and all deterministic
gates, opened the corrected 1920 and both approved same-state images at original resolution, and
used a fresh native Playwright page with only the registered 1920 CSS/JavaScript injected.

Independent geometry and containment:

```text
default          280/1314/300  now 280/300  tree overflow 0  kind right 281 <= edge 288
navigator +8     288/1306/300  now 288/300  tree overflow 0  kind right 289 <= edge 296
navigator Home   200/1394/300  now 200/300  tree overflow 0  kind right 201 <= edge 208
navigator End    360/1234/300  now 360/300  tree overflow 0  kind right 361 <= edge 368
context +8       280/1306/308  now 280/308  tree overflow 0  kind right 281 <= edge 288
context Home     280/1354/260  now 280/260  tree overflow 0  kind right 281 <= edge 288
context End      280/1134/480  now 280/480  tree overflow 0  kind right 281 <= edge 288
```

Every state also kept document/body horizontal overflow zero, selected context visible, navigator
range 200–360, context range 260–480 and results at least 1134 px. Independent ordinary-task
exercise passed Ctrl+K/submit, tree Home/End/Arrow/Enter, DP600 row selection with in-place context
update and DP600 Datasheet consequence. Headers remain exactly
`Compare | Material / grade | Family | Description | Status`; no visible Yield, Condition, CAE Card,
provider, mapping, approval or release term was found; console and page errors were empty.

Independent gates:

- 1920 validator with pending main lifecycle: 162/162;
- approved 1440 validator: 88/88;
- approved 1366 validator: 150/150;
- capture/validator help, Ruff, shared/1366/1920 JavaScript syntax, user-guide inventory,
  documentation impact and whitespace: passed;
- shared HTML/CSS/JavaScript and both approved PNG hashes: unchanged;
- corrected 1920 PNG SHA-256:
  `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`.

The corrected default PNG is byte-identical to the initial 03 image because the correction removes
only minimum-width interaction overflow. Direct image judgment confirms a full-width desktop
workspace, restrained shell, flat dividers, readable 25/36 px tree/result rows, dominant scan-first
result area, selected-material continuity and no visual attempt to fill wide space with unsupported
engineering fields.

Main-agent visual acceptance: 32/32. V-01 through V-16 each score 2; no hard gate scores zero.
Manifest main-agent evaluation is `accepted`; reference status remains `pending` and product-owner
approval is unset. The next permitted action is one fresh read-only review against reviewer packet
03.

### Fresh read-only reviewer disposition 03

Fresh `reviewer_terra_high` independently returned `approve`, 32/32, with V-01 through V-16 each
scoring 2, no hard-gate zero, no actionable finding and no residual concern.

The reviewer opened all three supplied PNGs at original resolution, reran the accepted-lifecycle
1920/1440/1366 validators at 162/88/150 checks, independently exercised both 1920 splitters through
default, Arrow, Home and End, and confirmed ordinary search/tree/result/context/Datasheet behavior.
Actual pane/ARIA synchronization, minimum 1134 px results, selected context, zero
document/body/tree overflow, navigator Home kind containment, target-only source registration,
frozen shared/approved hashes and the condition/unit information boundary all passed.

Approval unit 03 is ready for product-owner review. Only
`materials-search-normal-1920x1080.png` may be submitted. Reference status remains `pending`;
product-owner approval is unset. No later image, commit, push, PR, merge, GitHub write or production
React/CSS work is authorized before the product owner responds.

### Product-owner approval 03

The product owner approved the 1920×1080 image in conversation on 2026-07-28 after confirming that
the apparent smaller text came from fit-to-window image scaling rather than a viewport-specific font
change, then explicitly requested the next work. Manifest status is now `approved` with exact image
SHA-256 `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`.

The complete `Materials / search-results / normal` responsive set at 1366×768, 1440×900 and
1920×1080 is now approved and frozen. The next approval unit must be selected from the remaining
#167 inventory after direct issue/product-contract inspection; none of these three images, sources,
measurements, hashes or lifecycle records may be regenerated, resubmitted or changed.

## Approval-sequence decision 04

GitHub #167 does not prescribe an image-by-image order inside its screen inventory. The main agent
therefore applied the issue's user-flow order and the canonical product contract. The three approved
search-result images already contain the persistent Browse navigator and visible
Database/Profile/Table/Folder/Record tree, so creating another normal tree-only screenshot would
duplicate the same workspace without advancing the user's task.

The next unapproved approval unit is:

```text
Materials / datasheet overview / normal / 1440×900
```

It advances the selected Record from search/tree context into governed detail. Responsive 1366 and
1920 variants follow only after the 1440 structure is product-owner approved. CAE card preview is a
later separate screen; this overview exposes only the supported visible preview/download entry
points.

## Implementer packet 04 — Materials datasheet overview normal 1440×900

Status: ready for exactly one configured `implementer_luna_max` writer

Reference image:
[materials-datasheet-overview-normal-1440x900.png](../images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png)

### Main-agent source and contract review

The main agent directly inspected:

- GitHub #167 and the complete current reference manifest/evidence;
- all three approved search-result images and their frozen HTML/CSS/JavaScript;
- `docs/00-research/ux-layout-review/detail.html`, `review.css` and
  `docs/17-evidence/images/ux-layout-review/detail-1440x900.jpg`;
- current live `material-detail-1440x900.png` and the historical DUI-02 datasheet;
- Granta embedded/full Datasheet and typed Record-link images;
- Altair Material Data Center search/detail and CAE-model images;
- current `MaterialDetailPage`, route matching, return-path storage, `MaterialsBrowseTree`,
  `ResizableSplitPane`, Material/Property Set/Catalog graph contracts, card discovery/evidence
  actions and tests;
- canonical product/UI specifications and the Materials Detail visual rubric.

The old layout-review image supplies useful two-region datasheet structure but is not #167
authority. It has a tree overlap, five tabs, an indirect `Related and Evidence` action and status/
property assumptions that must not be copied. The current live capture keeps real state contracts
but permanently spends width on a Related context, hides Related inside Evidence, and can render a
long repetitive card rail. This new reference resolves the target product structure without editing
production code.

### User task and product judgment

The task is:

```text
selected DP780 synthetic Record
→ assess typed applicability
→ inspect representative response
→ see available native card formats
→ open Preview or Download
```

Search context remains recoverable through `Back to results`; the selected Record remains visible in
the Browse Tree. The main datasheet, not a permanent third context pane, owns detail.

Do not fill the overview with disconnected KPI cards. Use a compact property sheet:

```text
Property | Value | Unit | Condition | Source
```

Yield is forbidden as an unconditional search column, but is valid here because the selected metal
Record's typed Property Set supplies value, unit/source semantics and applicability. The static data
must be explicitly synthetic/non-production. Do not invent a production tensile standard, solver
policy, validation result or release event.

Use six directly accessible tabs:

```text
Overview | Properties | Curves | CAE Cards | Related | Evidence
```

`Related` is not hidden inside Evidence. Full IDs, hashes, classification, change reason and mapping
reports remain absent from the normal overview.

### Static region to current application/contract mapping

| Static region | Preserved application/contract |
| --- | --- |
| dark application bar | `ApplicationShell`; Materials/Modeling/Activity |
| compact detail command bar | stored `/materials?...` return path and selected Material context |
| 264 px Browse navigator | `MaterialsBrowseTree`, exact selected Record and keyboard path |
| one 5 px separator | `ResizableSplitPane` navigator range 200–360 |
| record header | `getMaterialDetail().material.current_revision` and human material identity |
| six-tab strip | canonical Material Datasheet contract; active Overview URL consequence |
| compact property sheet | typed `PropertySetContent`, normalized unit, applicability and source |
| representative curve | existing `representativeCurve`/engineering plot projection |
| condition summary | typed applicability plus selected Material State; missing values stay explicit |
| CAE delivery summary | graph/bulk-discovered `SolverCardSummary`; preview/download evidence gate |
| bottom status bar | current selection, exact revision status, jobs/warnings/connection |

Production currently has five tabs and a permanent Related context. This reference intentionally
sets the #159 target contract: Related becomes a first-class tab and the normal Overview is a
two-region navigator/datasheet workspace. This is not authorization to edit React now.

### Exact 1440 geometry and visual grammar

Reuse the approved search reference's `reference.css` unchanged for application tokens, typography,
focus, controls, tree density and status grammar. Add a detail-specific stylesheet; never modify the
frozen shared file.

At 1440×900:

```text
application bar = 46 px
detail command bar = 38 px
status bar = 24 px
workspace = x 8, width 1424 px, height 792 px
navigator / divider / datasheet = 264 / 5 / 1155 px
datasheet main content / internal aside ≈ 840–854 / 300 px
```

The result/datasheet region must remain at least 720 px across navigator
ArrowLeft/ArrowRight/Home/End. Tree and body/page horizontal overflow must stay zero at every state.
Tree rows remain 25 px; property rows target 30–34 px. Use flat rules and alignment, no nested
persistent cards, shadows, gradients, pill badges or large explanatory header.

The first viewport must show:

- selected `DP780 synthetic demo steel` and `DP780-REF`;
- explicit `Synthetic reference data · not validated engineering data`;
- Draft status without implying review/release;
- all six tabs with Overview active;
- Density, Young's modulus, Yield strength and Poisson ratio with separate Value, Unit, Condition
  and Source columns;
- a readable representative curve with axis labels and legend;
- application condition/state summary;
- exactly two synthetic reference native formats, Abaqus `.inp` and OpenRadioss `.rad`;
- visible Preview and Download entry points without scrolling;
- one filled primary command total;
- no full UUID/hash/mapping report/provenance text.

If card delivery status needs wording, use `Reference card` or `Available` only. Do not claim
Validated, Approved, Released or Delivered.

### Accessible static interactions

Create semantic HTML and one target JavaScript with bounded behavior:

- `Ctrl/Cmd+K` focuses the navigator search;
- navigator search submit records a DP780 tree-search consequence without losing ancestors;
- tree Up/Down/Home/End moves focus; Enter selects the DP780 Record;
- the single separator initializes truthful ARIA from the rendered 264 px pane and changes actual
  width plus `aria-valuenow` on ArrowLeft/ArrowRight/Home/End;
- `Back to results` records restoration of the prior query/selection;
- the six semantic tab buttons support click plus Left/Right/Home/End keyboard focus/selection and
  record a route consequence; Overview is restored before the final capture;
- Preview OpenRadioss records the exact card-preview consequence;
- Download `.rad` records a delivery consequence without creating a real file or claiming a release;
- all focus states remain visible and no unrelated key input is intercepted.

Use buttons for actions and anchors only for actual static navigation. Every input has a label,
meaningful name and `autocomplete="off"`. Decorative icons are hidden from assistive technology.
No polling, animation or layout read in a render loop.

### New bounded sources and ownership

The single writer may create/change only:

- new `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`;
- new `docs/00-research/ux-service-reference/materials-datasheet.css`;
- new `docs/00-research/ux-service-reference/materials-datasheet.js`;
- new `docs/00-research/ux-service-reference/capture_materials_datasheet.py`;
- new `docs/00-research/ux-service-reference/validate_materials_datasheet.py`;
- one new 1440 entry in `docs/01-product/service-reference-manifest.yaml`;
- one new PNG and measurement JSON under
  `docs/17-evidence/images/issue-167-service-reference/`.

The HTML may link the frozen `reference.css` followed by the new detail stylesheet. Register both
exact paths in the manifest. The new capture/validator must be standalone so approved search
capture/validator behavior is not changed.

Preserve byte-for-byte:

- all approved search HTML/CSS/JavaScript, target overrides, PNGs, measurements, hashes and
  lifecycle entries;
- all production React/CSS/API/state/test/user-guide sources and current captures;
- every historical/research/reference input;
- configuration and evidence packets not owned above.

### Deterministic capture and validation

Register only target id `materials-datasheet-overview-normal-1440x900`.
`capture_materials_datasheet.py` must:

- expose `--help` and `--target`;
- launch headless Chromium at exact 1440×900, device scale factor 1;
- load the static HTML and wait for fonts;
- exercise the splitter and ordinary interactions, reloading before the final normal screenshot;
- reject console/page errors;
- store exact measurements, interaction consequences and computed PNG SHA-256.

Store and assert splitter states:

```text
default:        navigator/divider/datasheet = 264/5/1155; aria now 264; min/max 200/360
navigator +8:   272/5/1147; aria now 272
navigator Home: 200/5/1219; aria now 200
navigator End:  360/5/1059; aria now/max 360
```

For every state assert:

- actual navigator width equals `aria-valuenow`;
- datasheet width remains at least 720 px;
- document/body/tree horizontal overflow equals zero;
- every tree-kind right edge is inside the navigator content edge;
- selected Record and first-viewport delivery commands remain visible.

Final default measurements/DOM validation must include:

- exact viewport, region geometry and one 5 px splitter with a 1 px visible rule;
- 25 px tree rows and 30–34 px property rows;
- selected tree Record count 1;
- six tabs, Overview selected, Related directly visible;
- property headers exactly `Property | Value | Unit | Condition | Source`;
- four property rows with non-empty unit/condition/source semantics;
- exactly two solver formats and visible Preview/Download;
- one filled primary command and zero nested persistent cards;
- no forbidden visible UUID/hash/checksum/Mapping Profile/Recipe/Batch/provenance text;
- no unsupported review/release/validated/approved/delivered label;
- all recorded ordinary interaction consequences true;
- no page/body vertical or horizontal overflow at the final normal viewport.

The manifest entry starts:

```text
screen: materials-datasheet-overview
state: normal
viewport: 1440×900 @ 1
status: pending
main_agent_evaluation.status: pending
product_owner_approval: absent
date: 2026-07-28
```

### Required gates

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --help
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_materials_datasheet.py docs/00-research/ux-service-reference/validate_materials_datasheet.py
node --check docs/00-research/ux-service-reference/materials-datasheet.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Report exact changed paths, default/extreme measurements, image hash, all three frozen image hashes,
all command results and residual concerns. Stop after implementation and local gates. Do not edit
production sources, approved assets, evidence packet, configuration, commit, push, write GitHub,
start another agent or request product-owner approval.

## Main-agent evaluation 04 — Materials datasheet overview normal 1440×900

Date: 2026-07-28

Result: `accepted` at 32/32 with no visual hard-gate failure.

The configured `implementer_luna_max` writer created only the Packet 04 sources, pending manifest
entry and target evidence. During the still-active initial writer pass, the main agent opened the
first PNG at original resolution and rejected fixed-width tree-kind clipping: `Database` and the
selected `Record` kind were visually shortened. The writer changed the detail-scoped tree grid so
kind labels retain max-content width, removed the inherited selected-kind prefix in this navigator,
and added exact-text/client-width/containment checks for every splitter state. This was completed
inside the original writer turn; no correction agent was used.

The final registered PNG is:

```text
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.png
SHA-256 bf2f2e20bcde69ddefc24f8701837ba8805d2f377cbfcab6be30b3f5eaf14c8a
```

The main agent opened that PNG again at original 1440×900 and directly compared it with the approved
search-result 1440×900 authority. The same application/navigation/tree/status grammar is preserved.
The detail replaces the search result/context columns with one dominant datasheet while retaining
the selected Record in the navigator. The internal 855/300 content/aside division keeps a readable
typed property sheet and representative curve beside application condition and bounded CAE-card
delivery. The overview does not become a KPI-card dashboard or expose Evidence-only identifiers.

Product judgment:

- condition-aware Yield is appropriate in the selected metal Record's typed datasheet, but remains
  excluded from universal search-result columns;
- separate `Value | Unit | Condition | Source` columns preserve engineering meaning;
- the representative curve remains the largest data graphic;
- exactly two clearly synthetic native reference formats expose Preview/Download without claiming a
  production standard, validation, review, approval, release or delivery event;
- all six canonical tabs are directly visible, including Related as distinct from Evidence;
- the flat explorer/datasheet workspace uses dividers instead of nested cards or decoration.

Independent native Playwright reproduced:

```text
default          264/5/1155  aria 264
navigator +8     272/5/1147  aria 272
navigator Home   200/5/1219  aria 200
navigator End    360/5/1059  aria 360
```

Every state kept actual and ARIA width equal, datasheet width above 720 px, and
document/body/tree horizontal overflow at zero. Exact visible kind texts were
`Database/Profile/Table/Folder/Folder/Record/Record`; every kind had
`scrollWidth <= clientWidth` and stayed inside the tree content edge. Ctrl+K focus, DP780 tree
search, tree Enter selection, tab End/Home/ArrowRight, Overview restoration, OpenRadioss Preview,
OpenRadioss `.rad` Download and Back-to-results restoration all produced their registered
consequences with no console or page errors.

The main agent reran the complete Packet 04 gate set. The datasheet capture and pending validator
passed before lifecycle advancement; the approved search validators passed at 88/150/164 checks and
their registered hashes remained:

```text
1440 8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b
1366 b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065
1920 b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191
```

Ruff, JavaScript syntax, user-guide classification/link/image checks, documentation-impact and
`git diff --check` passed. Production React/CSS/API/state/test sources and all approved reference
assets remain unchanged.

The reference remains `pending` with product-owner approval absent. It may advance only to a fresh,
read-only reviewer after a separate reviewer packet is stored.

## Product-owner feedback and sole correction packet 04-A — graph range headroom

Date: 2026-07-28

Status: ready for exactly one configured `correction_terra_high` writer.

The product owner did not approve the first submitted datasheet image. The exact finding was that
the graph range appears fitted to the maximum x/y values, leaving the response curve visually
cramped against the upper and right plot boundaries.

The main agent reopened the submitted 1440×900 PNG and the plot source at original resolution. The
finding is valid: the current synthetic curve ends at the right plot boundary (`x = 732`) and above
the top `800 MPa` grid line (`y = 17`, while the grid begins at `y = 27`). The issue is axis-domain
selection, not graph size, typography or surrounding datasheet topology.

### Engineering judgment

Use stable rounded "nice" engineering axes instead of fitting the domain to the last data point:

```text
x range: 0.00–0.25 engineering strain
y range: 0–1,000 MPa engineering stress
synthetic curve still ends near 0.20 strain and approximately 850 MPa
```

This leaves about 20% horizontal domain headroom and 15% vertical headroom while keeping familiar
round ticks. Do not change the synthetic data values or imply a tensile standard, extrapolation,
validation result or production suitability. The extra range is display margin only.

### Exact visual correction

Keep the SVG view box, graph frame, legend, section height and the complete surrounding page
geometry unchanged.

Within the existing plot area (`x 64–732`, `y 27–191`):

- remap the existing response curve from a fitted 0.20/approximately-850 domain to the
  0.25/1,000 domain;
- the curve must start at the origin and end near plot coordinate `(598, 52)`;
- preserve the existing curve shape and stroke; do not extrapolate it toward the new axes;
- use vertical grid positions for 0.00, 0.05, 0.10, 0.15, 0.20 and 0.25;
- use horizontal grid positions for 0, 250, 500, 750 and 1,000 MPa;
- visibly label at least `0`, `0.10`, `0.20`, `0.25` on x and `0`, `500`,
  `1,000 MPa` on y;
- retain `Engineering strain`, `Engineering stress`, the representative-response legend and the
  condition line;
- update the accessible SVG description so it states that the synthetic curve ends near 0.20 strain
  while the displayed axes extend to 0.25 strain and 1,000 MPa.

The target should retain at least 120 SVG units of right headroom and at least 20 SVG units of top
headroom between the response path bounding box and plot boundary. The response path must remain
fully inside the plot area.

### Scope and preservation

The sole correction writer may change only:

- the existing graph SVG in
  `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`;
- plot-domain/headroom capture evidence in
  `docs/00-research/ux-service-reference/capture_materials_datasheet.py`;
- matching deterministic assertions in
  `docs/00-research/ux-service-reference/validate_materials_datasheet.py`;
- the datasheet entry's image hash/lifecycle in
  `docs/01-product/service-reference-manifest.yaml`;
- the existing datasheet PNG and measurements JSON.

Preserve byte-for-byte:

- `materials-datasheet.css` and `materials-datasheet.js`;
- every non-graph HTML region and all displayed property/condition/card values;
- navigator/splitter/datasheet geometry and interactions;
- all approved search sources, images, measurements, hashes and lifecycle;
- production React/CSS/API/state/test/user-guide sources;
- configuration, evidence and reviewer packets.

The corrected manifest entry must remain:

```text
status: pending
main_agent_evaluation.status: pending
product_owner_approval: absent
```

### Deterministic evidence and gates

Extend the standalone datasheet capture/validator to store and assert:

- declared axis maxima `x = 0.25`, `y = 1000 MPa`;
- response-path bounding box and endpoint;
- plot-area bounds;
- right headroom at least 120 SVG units;
- top headroom at least 20 SVG units;
- response path fully inside the plot area;
- required visible tick/axis/legend/condition text.

Rerun:

```powershell
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --help
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-main-agent-status accepted
uv run ruff check docs/00-research/ux-service-reference/capture_materials_datasheet.py docs/00-research/ux-service-reference/validate_materials_datasheet.py
node --check docs/00-research/ux-service-reference/materials-datasheet.js
uv run cmp-check-user-guide --root .
uv run cmp-check-doc-impact --root . --mode worktree
git diff --check
```

Report exact changed paths, plot bounds/path/headroom, new image hash, preserved CSS/JavaScript and
approved-image hashes, all gate results and residual concerns. Stop after correction and local
gates. Do not edit production, use a second writer, commit, push, write GitHub, open a PR or request
product-owner approval.

## Main-agent evaluation 04-A — corrected graph range

Date: 2026-07-28

Result: `accepted` at 32/32 with no visual hard-gate failure.

The configured `correction_terra_high` writer performed the only correction allowed for this
approval unit. It changed only the graph SVG, standalone plot evidence/assertions, target manifest
hash/lifecycle and target image/measurements. The frozen detail CSS/JavaScript hashes remained:

```text
materials-datasheet.css
  3ccb42ddc80c597472d1858898add18be8d10dba0d63bfe27c92847b15b404f6
materials-datasheet.js
  2bf6bb304314c7f38a9d73ecf6159be2e55336b76d60a88122372abf6b75d101
```

The corrected registered PNG is:

```text
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.png
SHA-256 ff99eb5fd091ef44ebdc03967641dad94b327beb6428adb0d13ccf514c6c5f9e
```

The main agent opened the corrected PNG at original 1440×900. The product-owner finding is resolved:
the response now ends at the `0.20` vertical grid position while the x axis continues to `0.25`;
the approximately 850 MPa endpoint sits below a rounded `1,000 MPa` ceiling. The resulting empty
space reads as intentional engineering-plot range rather than clipping. The curve remains the
dominant graphic, and neither the plot frame nor surrounding datasheet topology changed.

Independent native Playwright measured:

```text
plot area       left 64 / right 732 / top 27 / bottom 191
path start      64 / 191
path endpoint   598.4000 / 51.8000
right headroom  133.6000 SVG units
top headroom     24.8000 SVG units
axis maxima      0.25 strain / 1,000 MPa
```

The full response-path bounding box remained inside the plot. Required visible tick/axis labels and
the accessible description passed. The independent browser also reproduced all navigator states:

```text
default          264/5/1155  aria 264
navigator +8     272/5/1147  aria 272
navigator Home   200/5/1219  aria 200
navigator End    360/5/1059  aria 360
```

Every state retained zero document/body/tree horizontal overflow and fully rendered tree kinds.
Ctrl+K search, DP780 consequence, tab selection/restoration, OpenRadioss Preview/Download and
Back-to-results restoration remained intact with no console/page errors.

The main agent reran the complete 04-A gate set. The corrected datasheet capture and pending
validator passed; all three approved search validators passed at 88/150/164 checks and their hashes
remained `8f99…c53b`, `b1fc…2065` and `b927…f191`. Ruff, JavaScript syntax, user-guide,
documentation-impact and `git diff --check` passed. No production source changed.

The target main-agent evaluation advanced to `accepted`; the reference remains `pending` with
product-owner approval absent. A separate fresh read-only re-review is required before resubmission.

## Product-owner refinement 04-A.1 — data-relative domain policy

Date: 2026-07-28

Status: continuation of the same sole correction writer before re-review.

Before re-review began, the product owner clarified that `0.25` and `1,000 MPa` must not be
hard-coded axis policy. The displayed domain must be derived from the actual data range by a
proportional offset.

This clarification is correct and supersedes any interpretation of the 04-A rounded maxima as fixed
values. The current synthetic series happens to resolve to the same visible maxima, but the
reference must register the derivation so another material or curve cannot reuse those numbers
blindly.

Use this deterministic policy:

```text
data minima: x = 0.00 strain, y = 0 MPa
data maxima: x = 0.20 strain, y = 850 MPa
upper headroom ratio: 10% of each data span
target intervals: x = 5, y = 4
nice step factors: 1, 2, 2.5, 5, 10 × 10^n

paddedMax = dataMax + (dataMax - dataMin) × 0.10
roughStep = (paddedMax - dataMin) / targetIntervals
niceStep = smallest allowed nice step >= roughStep
domainMax = ceil(paddedMax / niceStep) × niceStep
```

For this series only, the derived result is:

```text
x padded max 0.22 → nice step 0.05 → domain max 0.25
y padded max 935 MPa → nice step 250 MPa → domain max 1,000 MPa
```

The zero origin is preserved because this selected synthetic stress-strain response begins at the
physical origin. Do not add symmetric negative padding.

The same `correction_terra_high` writer must continue; do not start another writer. It may update
only the already authorized 04-A paths. The serialized static SVG may contain the derived rendering
coordinates, but it must declare:

- series minima/maxima;
- headroom ratio;
- target interval counts;
- nice-step factors or policy identifier;
- resulting derived axis maxima.

The capture and validator must independently recompute the padded maxima, nice steps, domain maxima
and expected curve endpoint from those declared data extrema/policy. They must fail if the serialized
axis or endpoint stops matching the derivation. The endpoint for exactly 850 MPa on the derived
1,000 MPa domain is approximately `(598.4, 51.6)` in the existing plot area.

Retain the visual headroom, tick labels and page geometry from 04-A. Re-run the complete 04-A gate
set and report the declared inputs, recomputed domain, endpoint/headroom, image hash and preserved
assets. The target lifecycle returns to `pending/pending/absent` until main evaluation and fresh
re-review are repeated.

## Main-agent evaluation 04-A.1 — data-relative graph domain

Date: 2026-07-28

Result: `accepted` at 32/32 with no visual hard-gate failure.

The same sole `correction_terra_high` writer continued before re-review. No second writer or
correction agent was started. The final registered PNG is:

```text
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.png
SHA-256 c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8
```

The reference now declares the curve data extrema and domain policy separately from the serialized
axis result:

```text
series strain       0.00–0.20
series stress       0–850 MPa
upper padding       10% of data span
target intervals    x 5 / y 4
nice factors        1 / 2 / 2.5 / 5 / 10 × 10^n
```

The standalone capture and validator each recompute:

```text
strain padded max   0.22
strain rough/step   0.044 / 0.05
strain domain max   0.25
stress padded max   935 MPa
stress rough/step   233.75 / 250 MPa
stress domain max   1,000 MPa
derived endpoint    598.4 / 51.6
```

They fail if the serialized axis maxima or response endpoint no longer matches those declared data
inputs and policy. The static SVG stores the deterministic rendered result; `0.25` and `1,000` are
therefore evidence outputs for this synthetic series, not reusable fixed product policy.

The main agent reopened the final PNG at original 1440×900. It retains the intended visible
headroom and the curve still ends at the `0.20` grid position below the `1,000 MPa` ceiling. The
response bounding box remains inside the plot with 133.6 right and 24.6 top SVG units of space.

A separate main-agent Python/Playwright sequence independently read the declared DOM inputs and
implemented the nice-step derivation without calling the project capture/validator helpers. It
reproduced both domains and endpoint, then passed all four navigator states, exact tree-kind
containment, search, tab, Preview/Download and Back-to-results consequences with no browser errors.

The complete 04-A gate set passed again. Frozen detail CSS/JavaScript and all three approved search
images/hashes remained unchanged. Production sources were not touched.

The main-agent lifecycle advanced to `accepted`; the reference remains `pending` with
product-owner approval absent. A fresh read-only re-review is required before resubmission.

## Product-owner approval 04 and approval-sequence decision 05

Date: 2026-07-28

The product owner approved the final corrected reference in conversation:

```text
Materials / datasheet overview / normal / 1440×900
SHA-256 c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8
```

Approval followed the data-relative 10% span headroom refinement and fresh 32/32 read-only
re-review. The manifest status is now `approved`, main-agent evaluation remains `accepted`, and
product-owner approval/date/evidence are recorded. This exact image, data-relative domain policy,
sources and measurement evidence are frozen and must not be regenerated or resubmitted.

GitHub #167 remains open and its scope is unchanged. The approved search-result responsive trio and
the approved 1440 datasheet overview now establish the selected-Record flow. Per approval-sequence
decision 04, responsive datasheet variants follow the 1440 structural approval.

The next unapproved approval unit is:

```text
Materials / datasheet overview / normal / 1366×768
```

This compact viewport comes before 1920×1080 because it is the harder safety case: the Browse
navigator, typed property sheet, representative graph and CAE delivery entry points must remain
readable without clipping or collapsing detail into cards. It must reuse the approved 1440
structure and data-relative graph-domain policy, not redesign them.

After product-owner approval of the 1366 image, the next planned unit is:

```text
Materials / datasheet overview / normal / 1920×1080
```

The CAE-card preview/download screen remains a separate later approval unit after the normal
datasheet responsive trio. No next image, packet, writer, commit, push, PR or production source work
was started while answering the product owner's sequence question.

## Implementer packet 05 — Materials datasheet overview normal 1366×768

Date: 2026-07-28

Writer: exactly one configured `implementer_luna_max`

Approval unit:

```text
Materials / datasheet overview / normal / 1366×768
target id: materials-datasheet-overview-normal-1366x768
```

This packet is the main Sol agent's authoritative bounded instruction. The writer implements it; the
writer does not reinterpret the issue, redesign the approved datasheet, change production React/CSS,
or begin the 1920 reference.

### Frozen authority and source boundary

The exact approved parent reference is:

```text
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.png
SHA-256 c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8
```

The responsive grammar also follows the approved compact search reference:

```text
docs/17-evidence/images/issue-167-service-reference/
  materials-search-normal-1366x768.png
SHA-256 b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065
```

The following shared datasheet sources and approved 1440 evidence are frozen byte-for-byte:

```text
docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html
SHA-256 7b9611b6398f6cbd21db52663e654c4eba60da8feea28ba9d4ec76b2e1e00de6

docs/00-research/ux-service-reference/materials-datasheet.css
SHA-256 3ccb42ddc80c597472d1858898add18be8d10dba0d63bfe27c92847b15b404f6

docs/00-research/ux-service-reference/materials-datasheet.js
SHA-256 2bf6bb304314c7f38a9d73ecf6159be2e55336b76d60a88122372abf6b75d101

docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.png
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1440x900.measurements.json
```

Do not regenerate, rewrite, reformat, or update lifecycle data for the approved 1440 target. All
three approved Materials search images, measurements, source hashes and lifecycle records are also
frozen.

The only expected additions/changes are:

```text
docs/00-research/ux-service-reference/
  materials-datasheet-overview-normal-1366x768.css               new
  materials-datasheet-overview-normal-1366x768.js                new
  capture_materials_datasheet.py                                target support
  validate_materials_datasheet.py                               target support
docs/01-product/service-reference-manifest.yaml                 new target entry only
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1366x768.png              new
  materials-datasheet-overview-normal-1366x768.measurements.json new
```

If another path appears necessary, stop and report it instead of expanding scope.

### User task and preserved product contracts

The normal user continues from a selected `Record` in Materials search to one continuous datasheet
workspace. The first viewport must expose:

- the compact Browse navigator with the selected DP780 record;
- material identity and synthetic/Draft state;
- the six direct tabs `Overview | Properties | Curves | CAE Cards | Related | Evidence`;
- the four governed property rows with columns
  `Property | Value | Unit | Condition | Source`;
- the representative response and its application condition;
- CAE delivery readiness with OpenRadioss and Abaqus formats plus Preview/Download consequences.

Preserve the existing static interactions and semantics: Ctrl+K search, typed tree selection,
keyboard tabs with restoration, Back-to-results restoration, splitter keyboard control, and both
delivery actions. Preserve native controls, labels, visible focus, ARIA relationships and URL/state
consequences. Do not add full IDs, hashes, provenance, mapping JSON, Yield, condition facets, solver
card columns, or another permanent inspector.

The static-region to future production-contract mapping remains:

| Static region | Production component/contract to preserve later |
|---|---|
| Browse navigator | `MaterialsBrowseTree`, catalog graph, selected record and stored return path |
| Datasheet identity | `MaterialDetailPage`, `getMaterialDetail`, `MaterialDetail` |
| Governed properties | `PropertySetContent` and condition/unit/source semantics |
| Representative response | `representativeCurve`; data-relative display domain only |
| CAE delivery | existing solver-card availability and Preview/Download consequences |
| Split workspace | `ResizableSplitPane`; one navigator separator, no permanent third inspector |

This approval unit changes reference evidence only. It does not port that mapping into production.

### Exact compact responsive rule

Do not reduce any approved font size. At 1366×768 the app/command/status bars remain 46/38/24 px,
and the workspace remains at x=8 with width 1350 and height 660. Reclaim width for governed data by
using only these target-local CSS changes:

```css
:root {
  --navigator-width: 244px;
}

.overview-grid {
  grid-template-columns: minmax(0, 1fr) 280px;
}
```

Do not introduce target-local font, row-height, plot-height, card, padding, overflow, or content
overrides. The default measured geometry must be:

```text
navigator / divider / datasheet       244 / 5 / 1101
main data / CAE delivery              821 / 280
plot frame width                      797
```

The 1366 target-local JavaScript must derive the compact navigator maximum once from rendered
geometry rather than store the result as an unexplained constant:

```text
compactMax =
  min(
    360,
    floor(workspaceWidth - dividerWidth - asideWidth - 720)
  )

at 1366×768:
  min(360, floor(1350 - 5 - 280 - 720)) = 345
```

Set the separator's `aria-valuemax` to that result and synchronize `aria-valuenow` with the actual
244 px navigator width. The shared keyboard handler must then produce:

```text
default          244 / 5 / 1101   main 821 / aside 280   plot 797   aria 244/345
ArrowRight       252 / 5 / 1093   main 813 / aside 280   plot 789   aria 252/345
Home             200 / 5 / 1145   main 865 / aside 280   plot 841   aria 200/345
End              345 / 5 / 1000   main 720 / aside 280   plot 696   aria 345/345
```

The 720 px main-data width is the safety rail from the product responsive contract, not a general
new product constant. The target script must not intercept unrelated keys, create a second splitter
handler, or mutate shared source. The actual navigator width and ARIA value must agree in every
state.

### Graph and information-design authority

The graph must remain the approved data-relative rendering:

```text
series strain       0.00–0.20
series stress       0–850 MPa
upper padding       10% of each data span
target intervals    x 5 / y 4
nice factors        1 / 2 / 2.5 / 5 / 10 × 10^n
derived domains     0.25 strain / 1,000 MPa
derived endpoint    598.4 / 51.6 in the existing SVG coordinate system
```

The displayed maxima are outputs for this series, not hard-coded reusable axis policy. Preserve the
visible right/top headroom, tick labels, legend and accessible description. The plot and property
rows remain more visually important than metadata or CAE delivery. Retain the approved flat
divider-led topology: no nested cards, decorative gradients, badge proliferation, sticky overlay,
or route-specific presentation layer.

### Capture and registration

Extend the existing standalone capture so it accepts both datasheet target IDs. For every page load
phase used by capture or interaction checks, use a target-aware load helper that:

1. opens the shared approved HTML;
2. injects the target CSS after the base/detail styles;
3. injects the target JavaScript after the target CSS;
4. waits for `document.fonts.ready`.

Do this for initial capture, splitter states, interaction checks and final capture. A plain reload
must not silently lose the injected override. Do not add the 1366 assets to the shared HTML.

Register a new manifest target whose source list contains the shared HTML, base CSS, detail CSS and
shared JavaScript plus explicit `css_override` and `javascript_override` fields for the two new
target files. Register the capture and validator, viewport, image, measurements, date and SHA-256.
Lifecycle starts exactly as:

```yaml
status: pending
main_agent_evaluation:
  status: pending
product_owner_approval:
  status: absent
```

Do not claim main-agent, reviewer, or product-owner acceptance.

### Deterministic acceptance

The 1366 capture/validator must fail unless all of the following are true:

- viewport and PNG are exactly 1366×768;
- measured default and four navigator states equal the geometry above within the existing
  measurement tolerance;
- main data width never drops below 720 px;
- separator min/max/now are truthful at 200/345/current width;
- document, body, datasheet panel and tree horizontal overflow are zero in every state;
- `Database`, `Profile`, `Table`, `Folder`, and `Record` are present and their rendered right edges
  remain inside the tree content edge in every state;
- the selected DP780 record, all six tabs, four property rows, representative graph, application
  condition, CAE delivery summary, both formats, Preview and Download remain visible in the first
  viewport;
- no property header/body cell is horizontally clipped in any splitter state;
- graph inputs, nice-step derivation, domains and endpoint independently recompute to the approved
  policy; response path remains contained with visible top/right headroom;
- search, tree selection, keyboard tabs, splitter keys, Preview, Download and Back-to-results have
  their existing visible consequences;
- no console error, page error, unintended page scrollbar or layout overlap occurs;
- shared source and every approved image/evidence hash remain unchanged.

Audit the result against the current Web Interface Guidelines: semantic buttons/links/tabs,
associated labels, visible keyboard focus, no new fake controls, no new ellipsis label for a
non-dialog action, no render-time layout loop, and deliberate containment/truncation. Record the
audit outcome in measurements evidence.

Run and report at minimum:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_materials_datasheet.py --target materials-datasheet-overview-normal-1366x768
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --help
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1366x768 --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_materials_datasheet.py --target materials-datasheet-overview-normal-1440x900 --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1440x900 --expect-status approved
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1366x768 --expect-status approved
uv run python docs/00-research/ux-service-reference/validate_reference.py --target materials-search-normal-1920x1080 --expect-status approved
uv run ruff check docs/00-research/ux-service-reference/capture_materials_datasheet.py docs/00-research/ux-service-reference/validate_materials_datasheet.py
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.js
uv run cmp-check-user-guide
uv run cmp-check-doc-impact
git diff --check
```

Open the final PNG at original resolution before reporting. Report changed paths, exact measured
states, target SHA-256, full gate results, frozen-asset hash confirmation and any residual concern.
Do not commit, push, open or modify a PR, update GitHub, start another writer/reviewer, or request
product-owner approval.

## Main-agent implementation inspection 05 and correction packet 05-A

Date: 2026-07-28

The configured `implementer_luna_max` completed packet 05 without a model-call error or
substitution. The registered candidate is:

[materials-datasheet-overview-normal-1366x768.png](../images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png)

```text
SHA-256 362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98
```

The main Sol agent opened this candidate and the approved 1440 parent at original resolution. The
candidate preserves the approved font sizes, six-tab topology, four governed property rows,
data-relative plot and 280 px CAE delivery region. All intended first-viewport content is visible,
the tree kinds are readable, the property cells appear contained, and the graph retains useful
right/top headroom. No visual redesign finding was identified.

The main code inspection did identify one deterministic-gate defect. The writer's native browser
run measured the required splitter states correctly, but the serialized `splitter_evidence` and
validator assert only total datasheet width. They do not serialize and independently require the
per-state main/aside/plot widths or property-cell containment. In particular,
`assert_splitter()` checks `widths["datasheet"] >= 720`; packet 05 requires the inner main-data
region itself to remain at least 720 px. A future regression could therefore pass the registered
validator while violating the compact safety rail.

This fails the main-agent deterministic gate. Use the one permitted fresh configured
`correction_terra_high` writer for correction 05-A. Do not change any visual source or redesign the
candidate. Authorized paths are limited to:

```text
docs/00-research/ux-service-reference/capture_materials_datasheet.py
docs/00-research/ux-service-reference/validate_materials_datasheet.py
docs/01-product/service-reference-manifest.yaml
docs/17-evidence/images/issue-167-service-reference/
  materials-datasheet-overview-normal-1366x768.png
  materials-datasheet-overview-normal-1366x768.measurements.json
```

The manifest and PNG are authorized only if the deterministic recapture changes their registered
digest. The expected result is no visual-source change and no intentional visual difference.
Approved 1440 evidence, all search evidence, shared HTML/CSS/JavaScript, 1366 target CSS/JavaScript
and production sources are frozen.

Correction requirements:

1. Extend every splitter snapshot with rendered widths for `.overview-main`, `.overview-aside` and
   `.plot-frame`.
2. Extend every splitter snapshot with property-table containment evidence. It must identify all
   header/body cells, require every cell's rendered box to stay inside the property table's visible
   horizontal boundary, require each cell's scroll width not to exceed its client width within the
   existing tolerance, and require no table/container horizontal overflow.
3. Capture and independently validate these exact per-state widths:

```text
default       main 821 / aside 280 / plot 797
ArrowRight    main 813 / aside 280 / plot 789
Home          main 865 / aside 280 / plot 841
End           main 720 / aside 280 / plot 696
```

4. Change the safety-rail assertion to the inner main-data width. Every state must fail below
   720 px. Keep total navigator/divider/datasheet and ARIA assertions unchanged.
5. For the default final viewport, serialize and validate that the selected DP780 record, all six
   tabs, four property rows and headers, representative graph, application-condition region,
   CAE-delivery region, both formats and all Preview/Download controls have rendered boxes inside
   the 1366×768 viewport above the status bar. `checkVisibility()` alone is insufficient.
6. Keep the target-aware load/injection sequence and existing interaction/plot derivation gates.
   Do not weaken a 1440 or approved-search check.
7. Recapture 1366, rerun the packet 05 gates using each validator's actual supported CLI, and open
   the final PNG at original resolution. `cmp-check-user-guide` must now pass because the candidate
   has a Markdown evidence link in this section.

Report the new serialized per-state evidence, final candidate digest, frozen hashes, complete gate
results and residual concerns. Do not start a reviewer, commit, push, modify GitHub, or request
product-owner approval.

## Main-agent evaluation 05-A — Materials datasheet overview normal 1366×768

Date: 2026-07-28

Result: `accepted` at 32/32 with no visual hard-gate failure.

The only configured `correction_terra_high` writer changed the standalone capture/validator and
regenerated 1366 measurements. It did not change the manifest, PNG, shared source, 1366 target
CSS/JavaScript or production source. The candidate remains:

[materials-datasheet-overview-normal-1366x768.png](../images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png)

```text
SHA-256 362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98
```

The strengthened serialized and independently validated splitter evidence is:

```text
state         navigator/divider/datasheet   main/aside/plot   ARIA now/max
default       244/5/1101                    821/280/797       244/345
ArrowRight    252/5/1093                    813/280/789       252/345
Home          200/5/1145                    865/280/841       200/345
End           345/5/1000                    720/280/696       345/345
```

Every state contains 5 property header and 20 body cells. All 25 rendered boxes stay within the
table boundary, each cell scroll width fits its client width, table/container overflow is zero, and
the inner main-data region never falls below 720 px. Document, body and tree overflow also remain
zero, with all typed tree kinds inside the content edge.

At the default 1366×768 state the status bar begins at y=744. The selected DP780 record, six tabs,
five property headers, four property rows, representative graph, application-condition region,
CAE-delivery region, two formats, two Preview controls and two Download controls all have rendered
boxes inside the viewport above that boundary.

The main Sol agent recaptured the target, opened it again at original resolution and compared it
directly with the approved 1440 parent. Font sizes and data density are preserved; the compact
navigator and 280 px delivery summary give the property sheet and graph more space without altering
the approved region structure. The tree types and values are readable, the property table is not
clipped, both CAE actions are visible, and the graph keeps the approved top/right range headroom.

A separate main-agent inline Python/Playwright sequence did not call the project capture/validator
helpers. It independently reproduced all four layouts and ARIA values, checked all 25 property cells
and tree-kind edges in every state, confirmed first-viewport boxes, exercised search and
OpenRadioss Preview/Download, and observed no console/page errors. Reading the DOM series/policy and
implementing the nice-step calculation independently produced `0.25` strain and `1,000 MPa`; the
response bounding box remained in `64/27–732/191` with endpoint approximately `598.4/51.6`.

The main agent reran the complete registered gate set:

```text
1366 capture                                      pass
1366 datasheet validator, pending lifecycle      pass
1440 datasheet validator, accepted lifecycle     pass
1440/1366/1920 search validators                 pass, 88/150/164 checks
Ruff and both JavaScript syntax checks            pass
user-guide and documentation-impact checks       pass
git diff --check                                  pass
```

After this evaluation the 1366 target manifest lifecycle advances to main-agent `accepted`. The
reference remains `pending` and product-owner approval remains absent. A separate fresh
`reviewer_terra_high` read-only review is required before the image may be submitted.

## Fresh reviewer disposition 05

Date: 2026-07-28

The configured fresh `reviewer_terra_high` completed an independent read-only review:

```text
disposition     approve
V-01–V-16       2 each
total           32/32
hard-gate zero  none
findings        none
residuals       none
```

The reviewer matched all registered/approved hashes and lifecycle, reran the complete gate set, and
used a separate native Playwright path without trusting capture/helper measurements. It reproduced
all four compact splitter layouts, truthful ARIA, 25 contained property cells, zero page/table/tree
overflow and first-viewport containment above y=744.

It independently recomputed the data-relative domain and response endpoint, varied input extrema to
confirm the maxima are not fixed display policy, and exercised search, tree, tabs,
Back-to-results and Preview/Download without browser errors. Direct original-resolution comparison
found preserved approved topology, readable text, property/graph dominance and restrained delivery.

The reference remains `pending`, main-agent evaluation is `accepted`, and product-owner approval is
absent. Exactly the registered 1366 PNG may now be submitted; no next reference, commit, push, PR,
merge or production visual work may start before the product owner's decision.

## Product-owner approval 05 and inventory-count audit

Date: 2026-07-28

The product owner approved the submitted reference in conversation:

```text
Materials / datasheet overview / normal / 1366×768
SHA-256 362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98
```

The manifest status is now `approved`, main-agent evaluation remains `accepted`, and product-owner
approval/date/evidence are recorded. This exact image, target override, responsive safety rails and
measurement evidence are frozen.

The product owner then requested an exact #167 progress count because the image-by-image workflow is
too slow. GitHub #167 does not currently define a finite final image count. The `AGENTS.md`
shorthand can be mechanically decomposed into 19 named functional categories; assigning one
independent normal-state image to every category at all three viewports would produce a provisional
57-image planning denominator. The issue does not state that every named category must be a separate
image—continuous workspaces can cover more than one—and it additionally requires relevant
long-label, empty, loading, blocked and error states without assigning those states to exact
screens. Therefore 57 is not an official minimum or final total; the authoritative total remains
undefined until a target-by-state inventory is frozen.

The current manifest contains five registered images, all approved:

```text
Materials search normal             1366×768 / 1440×900 / 1920×1080
Materials datasheet overview normal 1366×768 / 1440×900
```

The fifth registered image is the approval recorded above. Against the provisional 57-image
planning denominator, progress is 5/57 (8.8%) with 52 provisional normal slots remaining. Category
co-location may reduce that denominator, while required state variants will increase it. No next
image was started while reporting this count.

## Product-owner workflow authorization 06 — bounded parallel bundles

Date: 2026-07-29

The product owner authorized replacing sequential image-by-image execution with dependency-aware
parallel screen-family work and batch approval. They also requested materially fewer progress
messages.

The repository rules now permit, for #167 only:

- at most two dependency-independent family writers at once;
- disjoint family source/capture/image ownership with no concurrent edits to shared source,
  manifest or common evidence;
- one writer and at most one correction per family bundle;
- three normal viewport images in one implementation/review bundle;
- one canonical 1440×900 image for a topology-changing exceptional state, with deterministic
  1366/1440/1920 browser evidence;
- additional compact/wide exceptional images only after measured responsive topology divergence;
- fresh read-only review per family bundle, with independent reviewers allowed in parallel;
- one product-owner response approving multiple explicitly listed image paths and hashes.

Every image still receives its own manifest lifecycle, and the main agent still opens and evaluates
every original. User-facing progress suppresses per-command logs and reports only material blockers,
model-call failures and completed approval bundles.

## Authoritative finite inventory 07

Date: 2026-07-29

The previous provisional 57-image denominator is superseded by the finite inventory:

[service-reference-inventory.yaml](../../01-product/service-reference-inventory.yaml)

```text
screen families          18
implementation bundles   13
normal images             54  (18 × 3 viewports)
canonical exceptions      18  (1440×900)
total images              72
approved at inventory      5
remaining                 67
```

Same-topology long, empty, loading, blocked and error variants remain mandatory deterministic
1366/1440/1920 evidence but do not create duplicate approval PNGs. An inventory version bump and
product-owner approval are required if testing proves an exceptional state needs its own compact or
wide topology image.

The inventory records the dependency DAG and truthful capability boundaries. Activity recovery is
`Not configured` because the current product has no readable user-task recovery projection.
Administration publish is `Not configured` because configurable catalog resources are draft-only
and have no publication transition/policy endpoint. Neither reference may fabricate a successful
job recovery, receipt, release or catalog publish event.

The deterministic inventory validator passed:

```text
PASS issue-167 service-reference inventory:
18 families, 13 bundles, 54 normal + 18 exceptional = 72 images
progress at freeze: 5/72 approved; 67 remaining
first parallel wave: MAT-DETAIL + MOD-DATA
```

The first parallel approval wave is:

```text
MAT-DETAIL
  materials-datasheet-overview-normal-1920x1080
  materials-datasheet-related-long-1440x900
  materials-datasheet-empty-1440x900

MOD-DATA
  modeling-data-normal-1366x768
  modeling-data-normal-1440x900
  modeling-data-normal-1920x1080
  modeling-data-empty-new-session-1440x900
  modeling-data-long-invalid-mapping-blocked-1440x900
```

`MAT-DETAIL` is unblocked by the approved MAT-EXP normal selected-Record trio. `MOD-DATA` depends
only on the frozen shared Modeling shell/session contract. Their source, capture and image ownership
must be disjoint. The common manifest and this evidence report remain main-agent integration paths.

## WAVE-01 implementation, correction and main-agent gate 08

Date: 2026-07-29

The main Sol agent directly inspected the approved MAT-DETAIL parents, Modeling reference/current
captures, production React/API/state contracts and responsive rules, then persisted two bounded
packets before calling writers:

- [MAT-DETAIL implementer packet](issue-167-implementer-packet-mat-detail-wave-01.md)
- [MOD-DATA implementer packet](issue-167-implementer-packet-mod-data-wave-01.md)

Two configured `implementer_luna_max` agents loaded successfully and worked concurrently on
disjoint family paths. Neither edited production code, the inventory, the common manifest or this
report, and no substitute model was used.

Both writer capture/validation sets passed. Direct original-resolution inspection by the main agent
then rejected the first MAT-DETAIL exceptional-state result for two packet misses: Empty had removed
the selected DP780 Record header, and Related used short generic direction labels instead of proving
long forward/reverse Link Type containment. The main agent persisted the
[sole correction packet](issue-167-correction-packet-mat-detail-wave-01.md), and one fresh configured
`correction_terra_high` corrected only those paths and strengthened the deterministic assertions.
The normal 1920 asset and both approved parents remained unchanged.

The final registered candidates are:

```text
MAT-DETAIL
materials-datasheet-overview-normal-1920x1080
  eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849
materials-datasheet-related-long-1440x900
  810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6
materials-datasheet-empty-1440x900
  8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6

MOD-DATA
modeling-data-normal-1366x768
  07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95
modeling-data-normal-1440x900
  fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f
modeling-data-normal-1920x1080
  b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5
modeling-data-empty-new-session-1440x900
  d646d6bca74671114f46504d43a86f6115b6163607cbb0c9cb124962a31cf668
modeling-data-long-invalid-mapping-blocked-1440x900
  9ea42420431f3b220ce94d6dbe33c23548a589fc4fda68f63129e021f09e53f1
```

The main agent recaptured both families from the final source state, reran their registered
validators after common-manifest integration and independently exercised the pages through native
Playwright without calling either family helper:

```text
MAT-DETAIL family capture and accepted-lifecycle validator     pass
MOD-DATA family capture and accepted-lifecycle validator       pass
inventory, Ruff and JavaScript syntax gates                    pass
independent MAT normal/Related/Empty interactions              pass
independent MOD normal at 1366/1440/1920                       pass
independent MOD Empty/Invalid/Error interactions               pass
console/page errors and horizontal overflow                    zero
```

Main-agent visual disposition:

| Family/targets | Score | Hard-gate failure | Result |
| --- | ---: | --- | --- |
| MAT-DETAIL three candidates | 32/32 | none | accepted |
| MOD-DATA five candidates | 32/32 | none | accepted |

The wide Materials reference keeps a restrained 280 px navigator, one 5 px divider, 1319 px
datasheet main and 300 px application/delivery context. Related retains the selected Record and
wraps long human Link Type labels; Empty preserves Record identity and has one safe return without
fabricated data.

Modeling uses the required 184/192/208 px rails and gives the persistent graph 1177/1243/1707 px at
the three normal viewports. The selected exact Test Data, inclusion/visibility controls,
Library/Local/JSON source decisions and explicit unsaved preview remain continuous. Empty has no
inherited downstream pointer and one Local-file next step. Invalid retains raw samples, explicit
axis/quantity/raw/normalized-unit mapping, adjacent conflict, disabled preview/save and the clearly
stale last-valid graph.

All eight manifest rows remain `pending`, main-agent evaluation is `accepted`, and product-owner
approval is absent. Two bounded fresh read-only reviewer packets are required before WAVE-01 may be
submitted as one approval batch.

### WAVE-01 image evidence index

Canonical approval candidates:

![Materials datasheet normal at 1920×1080](../images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png)

![Materials Related long at 1440×900](../images/issue-167-service-reference/materials-datasheet-related-long-1440x900.png)

![Materials selected-Record Empty at 1440×900](../images/issue-167-service-reference/materials-datasheet-empty-1440x900.png)

![Modeling Data normal at 1366×768](../images/issue-167-service-reference/modeling-data-normal-1366x768.png)

![Modeling Data normal at 1440×900](../images/issue-167-service-reference/modeling-data-normal-1440x900.png)

![Modeling Data normal at 1920×1080](../images/issue-167-service-reference/modeling-data-normal-1920x1080.png)

![Modeling Data Empty new session at 1440×900](../images/issue-167-service-reference/modeling-data-empty-new-session-1440x900.png)

![Modeling Data invalid mapping blocked at 1440×900](../images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-1440x900.png)

Exceptional-state responsive evidence:

![Materials Related long responsive at 1366×768](../images/issue-167-service-reference/materials-datasheet-related-long-1440x900.responsive-1366x768.png)

![Materials Related long responsive at 1920×1080](../images/issue-167-service-reference/materials-datasheet-related-long-1440x900.responsive-1920x1080.png)

![Materials Empty responsive at 1366×768](../images/issue-167-service-reference/materials-datasheet-empty-1440x900.responsive-1366x768.png)

![Materials Empty responsive at 1920×1080](../images/issue-167-service-reference/materials-datasheet-empty-1440x900.responsive-1920x1080.png)

![Modeling Data Empty responsive at 1366×768](../images/issue-167-service-reference/modeling-data-empty-new-session-responsive-1366x768.png)

![Modeling Data Empty responsive at 1920×1080](../images/issue-167-service-reference/modeling-data-empty-new-session-responsive-1920x1080.png)

![Modeling Data invalid mapping responsive at 1366×768](../images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-responsive-1366x768.png)

![Modeling Data invalid mapping responsive at 1920×1080](../images/issue-167-service-reference/modeling-data-long-invalid-mapping-blocked-responsive-1920x1080.png)

## WAVE-01 reviewer and MOD-DATA correction gate 09

Date: 2026-07-29

Two fresh configured `reviewer_terra_high` agents reviewed the disjoint families read-only.
MAT-DETAIL was approved at 32/32 with no finding or hard-gate failure. The first MOD-DATA review
scored 31/32 and requested one bounded correction: at 1366×768 the invalid state's auto-height Data
ribbon used about 73% of the workspace and left only 103 px of graph canvas; the canonical
1440×900 canvas was 235 px. This failed Modeling's required persistent dominant-graph topology
despite otherwise complete interaction, containment and lifecycle evidence.

The main agent persisted the
[sole MOD-DATA correction packet](issue-167-correction-packet-mod-data-wave-01.md) before calling one
fresh configured `correction_terra_high`. The invalid-only source now places the raw inspector
beside the complete mapping decision. No required mapping field, conflict, reason, disabled action
or stale-preview boundary was removed, and normal/Empty canonical images remained unchanged.

Direct original-resolution inspection and independent native Playwright produced:

| Viewport | Data ribbon | Graph / main workspace | Graph canvas | Result |
| --- | ---: | ---: | ---: | --- |
| 1366×768 | 338 px | 263 / 622 px (42%) | 218 px | accepted |
| 1440×900 | 338 px | 395 / 754 px (52%) | 350 px | accepted |
| 1920×1080 | 320 px | 593 / 934 px (63%) | 548 px | accepted |

The independent run also reproduced the complete raw inspector, two mapping rows, adjacent
same-column conflict, change reason, disabled Update preview/Save dataset, exact stale graph
context, three plot curves, truthful splitter ARIA/actual width and zero document, body or table
horizontal overflow. The corrected canonical hash is:

```text
modeling-data-long-invalid-mapping-blocked-1440x900
  9ea42420431f3b220ce94d6dbe33c23548a589fc4fda68f63129e021f09e53f1
```

Canonical 1440 exceptional images now serve as their own middle responsive evidence. Redundant
same-pixel 1440 siblings were removed from both families; 1366 and 1920 responsive siblings remain.
This mechanical evidence de-duplication did not change any canonical Materials hash, any normal
Modeling hash or the Empty Modeling hash. Both integrated family validators, inventory, Ruff,
JavaScript syntax, whitespace, user-guide and documentation-impact checks pass.

The fresh bounded MOD-DATA re-review scored the corrected visuals 32/32. Its first disposition
identified one evidence-package mismatch only: the packet's 1366 responsive SHA did not match the
final recapture, and the validator did not yet bind responsive image bytes to state evidence. The
main agent corrected the packet hash and added path, existence, SHA-256 and dimension assertions;
no source or image changed. The same fresh reviewer verified both actions read-only and returned
`approve`. The prior evidence-integrity hard-gate failure is resolved.

Final reviewer dispositions:

| Family | Reviewer result | Score | Hard-gate failure |
| --- | --- | ---: | --- |
| MAT-DETAIL | approve | 32/32 | none |
| MOD-DATA after sole correction | approve | 32/32 | none |

WAVE-01 is now `product-owner-pending`. All eight manifest entries remain `pending`, their
main-agent evaluation remains `accepted`, and product-owner approval remains `absent`.

## Product-owner approval 10 — WAVE-01

Date: 2026-07-29

The product owner approved all eight explicitly submitted WAVE-01 images and hashes in one
conversation response. Each target now has its own `approved` manifest lifecycle and
product-owner approval evidence:

```text
materials-datasheet-overview-normal-1920x1080
  eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849
materials-datasheet-related-long-1440x900
  810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6
materials-datasheet-empty-1440x900
  8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6
modeling-data-normal-1366x768
  07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95
modeling-data-normal-1440x900
  fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f
modeling-data-normal-1920x1080
  b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5
modeling-data-empty-new-session-1440x900
  d646d6bca74671114f46504d43a86f6115b6163607cbb0c9cb124962a31cf668
modeling-data-long-invalid-mapping-blocked-1440x900
  9ea42420431f3b220ce94d6dbe33c23548a589fc4fda68f63129e021f09e53f1
```

Inventory progress is now 13/72 approved with 59 remaining. WAVE-01 is closed as `approved`.
The next inventory-ordered independent bundles are MAT-CARD, now unblocked by MAT-DETAIL, and
MOD-PROCESS, now unblocked by MOD-DATA. No production React/CSS, commit, push, PR or merge is
authorized by this approval.

## 11. WAVE-02 start — MAT-CARD + MOD-PROCESS

Date: 2026-07-29

The main agent directly re-opened issue #167, the approved prerequisite HTML/CSS and original PNGs,
the current live screenshots, the React/API/state contracts, the responsive rules, the canonical
component registry and the user-flow/visual acceptance gates. The two inventory-ordered families
are independent after their approved prerequisites:

- `MAT-CARD` depends on approved `MAT-DETAIL`;
- `MOD-PROCESS` depends on approved `MOD-DATA`.

The bounded parallel rule therefore permits two disjoint configured Luna Max writers. Their
main-agent-authored authoritative packets are:

- `docs/17-evidence/reports/issue-167-implementer-packet-mat-card-wave-02.md`
- `docs/17-evidence/reports/issue-167-implementer-packet-mod-process-wave-02.md`

MAT-CARD owns only `materials-card-preview*` source/capture/validator/staging evidence and its five
target images. MOD-PROCESS owns only `modeling-process*` source/capture/validator/staging evidence
and its four target images. Neither writer may edit shared CSS/JavaScript, inventory, manifest,
common evidence, production code or the other family. Shared integration remains serially owned by
the main agent after both handoffs.

## 12. WAVE-02 implementation, sole corrections and main-agent gate

Date: 2026-07-29

The two configured Luna Max writers completed disjoint MAT-CARD and MOD-PROCESS sources, capture
helpers, validators, target measurements and responsive/state evidence without touching shared or
production files. Both writer gate sets passed.

The main agent then opened all nine approval PNGs at original resolution. Two main-agent visual
failures were found before review:

- MAT-CARD normal/approximation native previews retained a fixed approximately 400 px height,
  leaving the 1440 and especially 1920 engineering workspace underused; the delivery-sheet header
  also repeated a clipped status in exceptional states.
- MOD-PROCESS 1366 and 1440 placed the Engineering strain axis label under the right-aligned
  legend/status, visibly clipping the label; `Preview changes` was duplicated in the title row and
  operation band.

Each family therefore used its one permitted fresh Terra High correction:

- MAT-CARD now fills the full available native-pane height (`443/443`, `569/569`, `749/749` for the
  three normal viewports), preserves independent scrolling and records zero clipped decision text.
- MOD-PROCESS now reserves separate contained axis-label and legend/status lanes and retains one
  title-row Preview command plus the sole filled `Save processed curves` commit action.

After correction, the main agent re-opened every approval PNG at original resolution and accepted
all nine. The direct inspection confirmed the approved prerequisite shells, exact context,
task/result continuity, responsive topology, readable engineering evidence, proportional graph
headroom, explicit approximation/unsupported/prerequisite boundaries and absence of clipping,
overlap, nested-card hard-gate failures or page overflow.

Final approval-image SHA-256:

```text
materials-card-preview-normal-1366x768
  60497b5fef2239cd17a468b4e8fcf1316e0bccca5b753600aff5f240b21a4372
materials-card-preview-normal-1440x900
  74f06d51955b1d7b8f95fed9aaa8f17af147ca00435d7e04f619638c977b2f21
materials-card-preview-normal-1920x1080
  8b9758160f441197c440aa11c8c5886cae75ce5e07e001a2aa4cf2fee60a1513
materials-card-approximation-blocked-1440x900
  2ea15b1bb5d0984296bab458a7d8572111f816c12f87ba5830ec3cbef7d7be92
materials-card-unsupported-blocked-1440x900
  688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d
modeling-process-normal-1366x768
  07e7c5f0dd913ac69d17a5c650f48ccd8e4a1930254a5e2d370987ecd3bf3358
modeling-process-normal-1440x900
  f1afcc0c0fbde30d255405abe31777c9642d08cbab779cabe2e16b7a513137d9
modeling-process-normal-1920x1080
  6354707d8e11e31808326e975a62ad9ca062297dd96aa437351b143076d57533
modeling-process-prerequisite-blocked-1440x900
  9511259e95654421a71c70bd198ccbf005a1df060cd40a0ab182c4bd0a03c76c
```

Main-agent deterministic gates passed for both family validators, responsive/state evidence,
inventory, Ruff, JavaScript syntax and `git diff --check`. Product-owner approval remains absent
and no dependent family, production change, commit, push, PR or merge has started.

## 13. WAVE-02 fresh reviewer dispositions

Date: 2026-07-29

Fresh configured Terra High read-only reviews were run independently from:

- `docs/17-evidence/reports/issue-167-reviewer-packet-wave-02-mat-card.md`
- `docs/17-evidence/reports/issue-167-reviewer-packet-wave-02-mod-process.md`

Both reviews returned `changes_requested` after each family had already used its one permitted
correction. No second correction, re-review or product-owner image submission is authorized by the
bounded #167 rule.

### MAT-CARD

- Visual score: 32/32; no V-01–V-16 hard-gate failure.
- Blocking evidence finding: the required error-state capture clicks Retry before recording its
  screenshot/snapshot. The resulting three error entries report `state: normal` and
  `error_visible: false`; the validator checks retained preview text but does not assert the actual
  pre-retry error state.
- Direct paths:
  `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`,
  `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`,
  `docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`.

### MOD-PROCESS

- Visual score: 31/32; no hard-gate zero.
- Blocking accessibility finding: each curve row is a focusable `role="button"` containing an
  inclusion checkbox and an icon button. The nested interactive structure makes the outer row and
  eye button both resolve as the `Hide Specimen 02 from plot` button in a fresh role query.
- Direct path:
  `docs/00-research/ux-service-reference/modeling-process-normal.html`.

Candidate images and manifest registrations remain `pending`, with main-agent visual evaluation
accepted and product-owner approval absent. No image was submitted for approval, no dependent
family was started and no production/commit/push/PR/merge action was taken.

## 14. Product-owner-authorized WAVE-02 second correction

Date: 2026-07-29

After the first fresh reviews reported the two bounded failures above, the product owner explicitly
authorized a second correction followed by re-review. This is a recorded WAVE-02 exception to the
default one-correction limit; it does not authorize redesign, a third correction, dependent-family
work, production changes, commit, push, PR or merge.

The main agent re-inspected both findings and persisted the exact correction packets before calling
writers:

- `docs/17-evidence/reports/issue-167-second-correction-packet-wave-02-mat-card.md`
- `docs/17-evidence/reports/issue-167-second-correction-packet-wave-02-mod-process.md`

The families remain independent with disjoint ownership. MAT-CARD is limited to capturing the
actual pre-retry error state and separately proving recovery. MOD-PROCESS is limited to replacing
the nested interactive curve row with sibling semantic controls and proving unique accessible names
and keyboard behavior. Shared manifest and evidence integration remains main-agent-only and
serial.

## 15. WAVE-02 second-correction main-agent gate

Date: 2026-07-29

Two fresh configured Terra High correction writers completed the disjoint packets. MAT-CARD changed
only its capture/validator and regenerated family evidence. Its five approval-image hashes remained
unchanged. MOD-PROCESS replaced the interactive row wrapper with sibling checkbox, curve-selection
button and visibility button semantics, also separating the resize separator from its collapse
button; its four approval-image hashes changed and were integrated serially into the manifest.

The main agent independently inspected the changed source, all three MAT-CARD error/recovery
records and all three MOD-PROCESS accessibility/keyboard records. The results are:

```text
MAT-CARD pre-retry state/error/Retry/preview/context            pass at 1366/1440/1920
MAT-CARD separate normal recovery/announcement/context         pass at 1366/1440/1920
MOD-PROCESS exact Hide Specimen 02 role count                  1 at 1366/1440/1920
MOD-PROCESS distinct Select Specimen 02 role count/name        1 / pass
MOD-PROCESS nested interactive descendants                    0
MOD-PROCESS pointer/keyboard selection and control preservation pass
family validators, inventory, Ruff, Node and diff checks       pass
browser/page errors, page overflow and clipped decision text   zero
```

The main agent opened all nine approval PNGs at original resolution after the second correction.
The five MAT-CARD images retain the previously accepted visual appearance. The four recaptured
MOD-PROCESS images retain the approved shell, graph dominance, proportional range headroom,
separate axis/legend lanes, complete task/result continuity and blocked recovery, without new
overlap, clipping or visual topology changes.

Final approval-image SHA-256:

```text
materials-card-preview-normal-1366x768
  60497b5fef2239cd17a468b4e8fcf1316e0bccca5b753600aff5f240b21a4372
materials-card-preview-normal-1440x900
  74f06d51955b1d7b8f95fed9aaa8f17af147ca00435d7e04f619638c977b2f21
materials-card-preview-normal-1920x1080
  8b9758160f441197c440aa11c8c5886cae75ce5e07e001a2aa4cf2fee60a1513
materials-card-approximation-blocked-1440x900
  2ea15b1bb5d0984296bab458a7d8572111f816c12f87ba5830ec3cbef7d7be92
materials-card-unsupported-blocked-1440x900
  688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d
modeling-process-normal-1366x768
  1ff458abf035810ed9ad41c7a157e26010f734477c53993de886970c1cb51c8a
modeling-process-normal-1440x900
  670075447a9e24848ac65efef5c996c8d601eda3917fb62d5b1d5f5a5a6f4dc4
modeling-process-normal-1920x1080
  d959b4a3d229b43b5062db67881823c38bec47b14d6601addf5baeff71c00eb6
modeling-process-prerequisite-blocked-1440x900
  533f19b7bfc9c1bec1a6cc97a37a3666df50482196f0a0c905e13f4200c08bdd
```

Both families remain `pending` with main-agent evaluation accepted and product-owner approval
absent. The bounded fresh re-review packets are:

- `docs/17-evidence/reports/issue-167-rereviewer-packet-wave-02-mat-card.md`
- `docs/17-evidence/reports/issue-167-rereviewer-packet-wave-02-mod-process.md`

No dependent family, production change, commit, push, PR or merge has started.

## 16. WAVE-02 second-correction re-review dispositions

Date: 2026-07-29

Both independent read-only re-reviews returned `changes_requested`, so the nine candidate images
were not submitted for product-owner approval.

The MAT-CARD review used a newly created configured Terra High reviewer. A second new reviewer
thread could not be created because the agent runtime returned `agent thread limit reached`. No
model was substituted. MOD-PROCESS was therefore reviewed in a new read-only turn by an existing
configured Terra High reviewer that had no prior MOD-PROCESS involvement. This runtime limitation
and both failing results keep the bundle unapproved.

### MAT-CARD — 29/32, hard-gate failure

- V-16 scored `0`: the family records no active-route legacy-selector report for
  `page-stack`, `page-heading`, `content-card`, `module-material-card`, `hero-actions`, `eyebrow`,
  `status-badge` and `count-chip`.
- Long, loading, error and Retry-recovery screenshots are captured only in memory. Their JSON
  snapshots and hashes cannot be independently opened because the browser-evidence PNGs are not
  persisted with paths and hash binding.
- V-06 scored `1`: computed 13 px body/data typography is not recorded and validated across the
  required viewports.
- Direct paths:
  `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`,
  `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`,
  `docs/00-research/ux-service-reference/materials-card-wave02.state-evidence.json`.

### MOD-PROCESS — 31/32, no hard-gate failure

- The requested nested-interactive correction passed: exact semantic curve controls, zero nested
  interactive descendants and pointer/keyboard behavior all verified.
- V-06 scored `1`: `docs/00-research/ux-service-reference/modeling-process.css` reduces
  `.setting small` decision metadata to 8 px at 1366×768 and 8.5 px at another compact breakpoint,
  conflicting with the required readable 12–13 px metadata range.
- The shallow ribbon and graph must be revalidated for clipping/overflow after restoring readable
  metadata size.

The default one-correction limit was already exceeded under the product owner's explicit
second-correction exception. A third correction is not authorized. Both families remain
`pending`, product-owner approval remains absent, and no dependent family, production change,
commit, push, PR or merge has started.

## 17. Product-owner-authorized main Sol High direct completion

Date: 2026-07-29

The product owner subsequently authorized the main Sol High agent to perform the correction
directly and requested a joint product-owner review when complete. No implementation or correction
subagent was called, no reviewer agent was substituted, and this section supersedes only the
authorization state at the end of section 16. It does not authorize approval, dependent-family
work, production changes, commit, push, PR or merge.

The main agent applied the two bounded corrections:

- MAT-CARD capture now records a zero-count active-route report for `page-stack`, `page-heading`,
  `content-card`, `module-material-card`, `hero-actions`, `eyebrow`, `status-badge` and
  `count-chip`; it also records and validates computed 13 px body and 12–12.5 px representative
  tree/data/metadata text.
- MAT-CARD long, loading and pre-Retry error states now persist one PNG at each required viewport.
  The three Retry recoveries persist separately. The validator opens all 12 files, checks exact
  dimensions and binds every file to its recorded SHA-256.
- MOD-PROCESS `.setting small` decision metadata now computes to 12 px with a 14 px line height,
  wraps normally and is not ellipsized. The ribbon, settings grid and graph bounds are recorded and
  validated after the typography change.

The user-requested skills influenced the correction as follows:

- `desktop-engineering-ui` kept the approved shell and region topology fixed while treating the
  original PNGs and measured layout as the visual gate.
- `frontend-ui-engineering` and `web-design-guidelines` required readable metadata, semantic
  controls, visible focus, deliberate wrapping and zero nested interactive controls.
- `webapp-testing` required browser capture at 1366×768, 1440×900 and 1920×1080, persisted
  screenshots, console/page error collection and deterministic geometry assertions.

The scoped Web Interface Guidelines audit found no `transition: all`, suppressed focus outline,
zoom restriction, non-semantic click target or new nested interactive control. Existing semantic
buttons, labels, `aria-label` values, tabs, separators and graph descriptions remain intact.

Deterministic evidence:

```text
MAT-CARD approval captures                              pass 5/5
MAT-CARD responsive/state evidence                     pass
MAT-CARD persisted state PNGs                          9 primary + 3 recoveries
MAT-CARD missing/hash-mismatched state PNGs            0
MAT-CARD legacy-selector count across captured states  0
MAT-CARD body/data/metadata typography                 13 / 12–12.5 px
MOD-PROCESS approval captures                          pass 4/4
MOD-PROCESS decision metadata                          12 px / 14 px / 0 clipped
MOD-PROCESS ribbon heights                             192 / 198 / 184 px normal
MOD-PROCESS blocked ribbon height                      228 px
MOD-PROCESS graph heights                              407 / 531 / 725 px normal
MOD-PROCESS blocked graph height                       501 px
MOD-PROCESS document overflow                         0 / 0 at every target
browser console errors / page errors                  0 / 0
Ruff / Node syntax / inventory / diff checks          pass
```

The main agent opened all 12 new MAT-CARD state PNGs and all four changed MOD-PROCESS approval PNGs
at original resolution. The five MAT-CARD approval PNG bytes remain unchanged from the previously
accepted visual inspection. Long/loading/error/recovery states retain the selected Record,
identity, delivery and native-preview context without clipping or page overflow. The 12 px
MOD-PROCESS metadata is materially more readable; natural wrapping increases the shallow ribbon
only as needed while the persistent engineering graph remains dominant, the axis/legend lanes stay
separate, and blocked recovery remains adjacent to the unmet prerequisite.

Product-owner review bundle:

```text
materials-card-preview-normal-1366x768
  60497b5fef2239cd17a468b4e8fcf1316e0bccca5b753600aff5f240b21a4372
materials-card-preview-normal-1440x900
  74f06d51955b1d7b8f95fed9aaa8f17af147ca00435d7e04f619638c977b2f21
materials-card-preview-normal-1920x1080
  8b9758160f441197c440aa11c8c5886cae75ce5e07e001a2aa4cf2fee60a1513
materials-card-approximation-blocked-1440x900
  2ea15b1bb5d0984296bab458a7d8572111f816c12f87ba5830ec3cbef7d7be92
materials-card-unsupported-blocked-1440x900
  688a0fd8bd9d4d72042f2ad21813df3b8f7ede78b128f75d3cfb1a6c63466d6d
modeling-process-normal-1366x768
  c537c7caf60d668a82021e50cdc0307b185faf118d5091edc41c10d9c5ef0cad
modeling-process-normal-1440x900
  57d5c9e8f9ebbf21315ca94f76eb21e11ce116526afffc717973ebb514417461
modeling-process-normal-1920x1080
  154c21e6679b999ee63ca65c10ac6e7af8a8ebdb54b69490be67460078ce53c1
modeling-process-prerequisite-blocked-1440x900
  9d71022e7c9bff6a5b88de70985a34aaf2e30d3bd1715a69a5e7c5bbd40b9868
```

All nine references remain `pending`, and `product_owner_approval` remains `absent` until the user
reviews and explicitly approves this bundle.

## 18. WAVE-02 product-owner approval

Date: 2026-07-29

The product owner explicitly approved the complete nine-image bundle listed in section 17. The main
agent advanced each MAT-CARD and MOD-PROCESS manifest entry independently to `approved`, recorded
the approval date and conversation evidence, and advanced the authoritative inventory to 22/72
approved with 50 images remaining.

The approved targets are:

```text
materials-card-preview-normal-1366x768
materials-card-preview-normal-1440x900
materials-card-preview-normal-1920x1080
materials-card-approximation-blocked-1440x900
materials-card-unsupported-blocked-1440x900
modeling-process-normal-1366x768
modeling-process-normal-1440x900
modeling-process-normal-1920x1080
modeling-process-prerequisite-blocked-1440x900
```

The remaining 50 references are finite and grouped as follows:

```text
MAT-EXP exceptional long/empty states                 2
MOD-FIT                                                4
MOD-EXPORT                                             6
ACT-QUEUE user/reviewer                                7
ACT-RECOVERY                                           3
ADM-SCHEMA-CORE database/table/attribute              11
ADM-SCHEMA-RELATIONS layout/subset/link                9
ADM-ACCESS                                             5
ADM-PUBLISH                                            3
                                                      --
                                                      50
```

The next dependency-ready candidates are the two remaining MAT-EXP exceptional references,
MOD-FIT, ACT-QUEUE and ADM-SCHEMA-CORE. Under the bounded parallel rule, at most two disjoint
families may be written concurrently after the main agent prepares their packets. MOD-EXPORT waits
for MOD-FIT; ACT-RECOVERY waits for the shared Activity queue topology; Administration relations,
access and publish follow their recorded core dependencies.

No production change, commit, push, PR or merge was performed.

## 19. WAVE-03 start — MAT-EXP exceptional states + MOD-FIT

Date: 2026-07-29

The main Sol agent directly re-opened issue #167, the complete authority set, current manifest and
inventory, the approved Materials normal sources/images, the approved MOD-DATA and MOD-PROCESS
sources/images, the Fit reference comparison and `modeling.html`/`review.css`, and the current
React/API/state contracts. The next six approval units form two dependency-ready, disjoint bundles:

- `MAT-EXP` adds only the canonical 1440×900 long-results and empty-results exceptional states to
  the already approved three-viewport Materials search family.
- `MOD-FIT` follows approved MOD-DATA and MOD-PROCESS with three normal viewports and one canonical
  1440×900 long candidate-parameters state.

The main-agent-authored implementation packets are:

- [MAT-EXP WAVE-03 implementer packet](issue-167-implementer-packet-mat-exp-wave-03.md)
- [MOD-FIT WAVE-03 implementer packet](issue-167-implementer-packet-mod-fit-wave-03.md)

The configured `implementer_luna_max` role was present in the active agent registry and two fresh
writers were started concurrently. MAT-EXP owns only its new exceptional-state source, capture,
validation, staging and image paths. MOD-FIT owns only its new Fit source, capture, validation,
staging and image paths. Neither writer may edit shared CSS/JavaScript, the common manifest,
inventory or this report; prerequisite sources and approved images remain frozen. The main agent
will integrate common lifecycle evidence serially only after both family gates and independent
reviews pass.

## 20. WAVE-03 completed gate and product-owner review bundle

Date: 2026-07-29

Both configured Luna Max writers completed their disjoint family assignments without editing the
shared manifest, inventory, evidence report or production UI. Luna was callable; no model
substitution occurred. The main agent corrected two packet command/lifecycle statements before
final execution: the MOD-FIT browser validator runs with the Playwright environment, and the
already approved MOD-DATA parent uses `main_agent_evaluation.status: accepted`.

### MAT-EXP result

The initial empty image retained a stale selected DP780 tree row and selected revision. The same
initial writer cleared every result/tree/context selection, removed the datasheet action, added one
Clear search recovery and recaptured the evidence. The final family validator passed all 18 images:
two canonical approval references, four compact/wide responsive siblings and 12 loading/error state
captures.

The main agent opened all 18 final images at original resolution. Long preserves one selected
record/context, 50 rows from 126 server-scoped matches and independent result scrolling. Empty
preserves the catalog hierarchy while showing no selected material or revision. Loading, tree-lazy
loading, query error and tree error retain truthful context and adjacent recovery with no clipping,
overflow or browser errors.

Fresh read-only Terra High review:

```text
disposition                                                approve
V-01–V-16                                                  2 each
total                                                       32/32
hard-gate failures / actionable findings                    none / none
```

Reviewer packet:
`docs/17-evidence/reports/issue-167-reviewer-packet-wave-03-mat-exp.md`.

### MOD-FIT result

Main-agent inspection rejected the initial reference until the same Luna writer:

- replaced boundary-ending/fixed-looking plot paths with finite plotted data, 10% proportional
  headroom, nice derived 0.50 strain / 1400 MPa limits and an altered-extrema proof;
- restored 13 px body/data/control text and 12 px metadata/help text;
- contained the long candidate table, complete candidate rows, selection, law-specific parameter
  value/unit/bounds, reason and warning acknowledgement while keeping the graph mounted;
- made the stale state set the actual Target strain input and all explanatory copy to `1.20`,
  clear the selection and disable Save at every viewport.

The main agent opened all four final approval images and all 12 state images at original resolution.
Normal references keep the compact curve/sequence rail, shallow Fit ribbon and persistent graph;
recommendation remains evidence, no engineer selection is implied and Save remains disabled with
its reason. Empty, calculating, stale/blocked and calculation-error states retain exact source,
rail, inputs and graph without blanking the workspace.

Fresh read-only Terra High review:

```text
disposition                                                approve
V-01–V-13 / V-14 / V-15–V-16                              2 each / 1 / 2 each
total                                                       31/32
hard-gate failures                                          none
non-blocking production-port concern                        status bar should reflect selected candidate
```

The reviewer accepted the static reference because selection is explicitly reflected in the
decision ribbon and long disclosure. The production port must also reflect selected-candidate/task
text in its status bar. The long disclosure intentionally shows four law-specific parameter rows;
blend/domain/target inputs remain visible in the ribbon and must remain accessible in production.

Reviewer packet:
`docs/17-evidence/reports/issue-167-reviewer-packet-wave-03-mod-fit.md`.

### Integrated deterministic gate

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
all main-agent original-image inspections                   34 / pass
MOD-FIT x/y finite extrema                                  0.42 / 1260
MOD-FIT derived limits / headroom                           0.50 / 1400 / 10%
altered-extrema derivation                                  pass
splitter/input/selection/save/graph/disclosure interactions pass
legacy active-route selectors / nested controls             zero / zero
console errors / page errors / document overflow            zero / zero / zero
Ruff / Node syntax / diff checks                            pass
service-reference inventory                                 18 families / 72 images / pass
```

The main agent registered every candidate independently with `status: pending`,
`main_agent_evaluation.status: accepted` and `product_owner_approval.status: absent`.

Product-owner review bundle:

```text
materials-search-long-1440x900
  8c70f5790ed02d1864d456f5947975871122b712d28d523096330e021e2b7f06
materials-search-empty-1440x900
  19bb7a9e50496786a87eb22f0c8a9f31a1da944bcc76a55f451b1d157135648e
modeling-fit-normal-1366x768
  33e84e09265d07a5c836c82c21622b64ca1f35fbd9646a1fe1aeb1589bf0efe7
modeling-fit-normal-1440x900
  194c1cad19ae8712b0c29d82b0b0c439989cf556d9a812468a13712066b7e9c3
modeling-fit-normal-1920x1080
  82cdcb393097c9ba767e82c3cddf8f582787f81f6496018ac3eea0ce064c96c4
modeling-fit-candidate-parameters-long-1440x900
  d16c32e031d17bc34aed6ba660d0f7796e9bd214dc7ee6601922a075c0f6aae0
```

All six references remain pending product-owner approval. Authoritative progress therefore remains
22/72 approved with 50 remaining. Explicit approval of this six-image bundle will advance progress
to 28/72 approved with 44 remaining. No dependent family, production change, commit, push, PR or
merge has started.

## 21. WAVE-03 product-owner correction authorization

Date: 2026-07-29

The product owner rejected mechanical-only acceptance of the pending six-image WAVE-03 bundle and
authorized one qualitative correction before re-review. The main Sol agent reviewed the supplied
GRANTA MI photographs and the product owner's clarification: they show Administrator-configured
Material/Neutral Material datasheets, and any graph renders an exact linked saved Record/revision
rather than a client-side reprocessing result. They are not Fit topology authority.

The correction applies only to the six pending WAVE-03 candidates. The three approved Materials
normal parents and the approved MOD-DATA/MOD-PROCESS parents remain byte-frozen and lifecycle-frozen.
After reviewing the corrected candidates, any consistency-driven proposal to reopen an approved
reference must explicitly name the image and receive separate product-owner authorization.

Main-agent-authored correction packets:

- [MAT-EXP WAVE-03 correction packet](issue-167-correction-packet-wave-03-mat-exp.md)
- [MOD-FIT WAVE-03 correction packet](issue-167-correction-packet-wave-03-mod-fit.md)

MAT-EXP must make tree/result scrolling discoverable, reduce tree indentation/type-label width tax
and preserve longer engineering identities. MOD-FIT must restore graph dominance, use a compact rail,
move on-demand parameters into a bounded bottom drawer, standardize engineering axis titles/units and
prove proportional data-derived ranges. Each family will receive one configured fresh Terra High
correction writer, deterministic and main-agent original-image gates, then a fresh read-only Terra
High re-review. The pending lifecycle and 22/72 approved count remain unchanged.

## 22. WAVE-03 correction implementation and main-agent gate

Date: 2026-07-29

Two configured fresh Terra High correction writers completed the disjoint MAT-EXP and MOD-FIT
families. No model substitution, approved-parent change, production change or GitHub action
occurred. The main agent serially registered only the six corrected pending hashes and temporarily
reset their main-agent lifecycle to `pending` for fresh re-review.

The main agent opened all 18 corrected MAT-EXP images and all 16 corrected MOD-FIT images at
original resolution. It required additional same-writer corrections before accepting the review
packets:

- the first long Fit drawer left an actual plot below the 230 px target;
- the Fit footer did not initially identify the explicitly selected candidate/task;
- a subsequent 1366 normal capture forced the Fit ribbon into one clipped line;
- the no-candidate 1366 evidence opened an empty drawer and reduced the graph to about 60 px.

The final bundle resolves all four. MAT-EXP has visible independent tree/result scrolling,
25 px tree rows, 9 px depth increments and no repeated full-width node-type label. Fit has a clean
two-row 1366 ribbon, centered unit-bearing axis titles, numeric-only ticks, a graph-first normal
layout, a bounded bottom drawer with a 230 px or taller long-state plot, truthful footer selection
state, and a closed-drawer empty state.

Integrated deterministic result:

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
main-agent original-resolution inspections                  34 / pass
approved parent validators and hashes                       pass / unchanged
tree and result local wheel/PageDown scrolling              pass
normal Fit actual plot share                                >=45%
long Fit actual plot / drawer share                         >=230 px, >=30% / <=35%
axis notation, centering and collision gates                pass
empty Fit drawer / useful graph                             closed / pass
selection footer and invalidation reset                     pass
console/page errors / document overflow / nested controls   zero
Ruff / Node syntax / inventory / diff checks                pass
```

Fresh read-only reviewer packets:

- [MAT-EXP WAVE-03 re-review packet](issue-167-rereviewer-packet-wave-03-mat-exp.md)
- [MOD-FIT WAVE-03 re-review packet](issue-167-rereviewer-packet-wave-03-mod-fit.md)

The six images remain pending product-owner approval. Authoritative progress remains 22/72
approved with 50 remaining.

## 23. WAVE-03 correction findings and final re-review

Date: 2026-07-29

The first fresh read-only reviewers identified two concrete issues that the deterministic checks
had not yet excluded:

- the MAT-EXP empty state rendered `Find` and `Clear search` as two filled primary actions;
- the visible long-state Fit `Stress (MPa)` overlay intersected the `700` tick while the validator
  measured a hidden SVG label.

The same single authorized correction writer for each family resolved its bounded finding. No
replacement writer, model substitution, approved-parent edit, production change or GitHub action
occurred. The MAT-EXP validator now requires `Find` to be the sole visible filled action and keeps
`Clear search` as a secondary recovery. The MOD-FIT capture and validator now measure the actually
visible axis title and reject title/tick/legend intersection.

The main agent reopened all 18 final MAT-EXP and all 16 final MOD-FIT images at original resolution,
then reran the integrated gates. Two newly configured fresh Terra High read-only reviewers each
opened the complete family bundle and independently returned `approve`, V-01–V-16 all `2`, total
`32/32`, with no hard-gate or actionable finding. MAT-EXP retains one non-blocking caution: its
358 px tree minimum creates 93–129 px of local horizontal overflow, so later work should not expand
that dependency.

Final product-owner candidates:

```text
materials-search-long-1440x900
  c754705a8e8b2bcc2c960cadc820c982a132721c35c7840c756afa516dcf5d9a
materials-search-empty-1440x900
  32943f5f7890046c02c5ad127c3dacd162a5c1308d87ed41da35daff72f646af
modeling-fit-normal-1366x768
  06b8a7c434a389ab2ed7fd1a7a0e86bc9e66e3a0d00dba1550a7387cb685647b
modeling-fit-normal-1440x900
  d0b91783896a5d12ba71b463621123b58a064d1ce91ce15a56d58b03821db904
modeling-fit-normal-1920x1080
  d74a8ba9a2c906cf06e9661c093c468df07ce792659e07ebcf146828dd31b0e9
modeling-fit-candidate-parameters-long-1440x900
  32f3752f97e20a4d8baeadab82fa9bcece1b83e82eeb5d610d488158dcb724fb
```

The six entries remain `pending` with product-owner approval absent; their main-agent evaluation is
now `accepted`. Progress therefore remains 22/72 approved with 50 remaining. Approval of this exact
six-image batch advances progress to 28/72 approved with 44 remaining. Approved parents remain
frozen. No dependent family, production change, commit, push, PR or merge has started.

## 24. WAVE-03 product-owner visual rejection after re-review

Date: 2026-07-29

Before approving the six-image batch, the product owner identified two visible defects that the
main-agent and independent review had missed:

- MAT-EXP's synthetic vertical scrollbar indicator overpainted long tree identity text instead of
  occupying a reserved native scrollbar gutter;
- MOD-FIT proved only non-intersection, not compact engineering-axis spacing. The Y title/ticks/axis
  consumed too much horizontal gutter, while the X title sat too far below its ticks and therefore
  appeared absent. The unused bottom SVG space also reduced the effective plot height.

The product-owner criticism is accepted as a review-gate failure. The six references are not being
submitted for approval and their main-agent lifecycle has returned to `pending`. The main Sol agent
will directly remove the tree overlay scrollbar, rely on a reserved native gutter, tighten and
measure title/tick/axis adjacency, make the X title visibly persistent at 13 px, and reduce unused
plot insets. Existing approved parents remain frozen.

## 25. WAVE-03 direct main-agent correction and reviewer handoff

Date: 2026-07-29

The main Sol agent directly corrected the two product-owner findings without changing an approved
parent, production UI or another reference family:

- MAT-EXP removed the synthetic tree scrollbar element. The overflowing tree now uses its native
  scrollbar with a measured 15 px reserved gutter and no custom overlay over identity text at
  1366×768, 1440×900 or 1920×1080.
- MOD-FIT now keeps a visible centered 13 px `Equivalent plastic strain` title, bounds its
  title/tick/axis gaps, reduces unused SVG/footer insets and uses the same engineering-axis grammar
  in normal and long states. At 1366×768 the measured x-title-to-tick, y-title-to-tick and
  y-tick-to-axis gaps are approximately 4.6 px, 5.0 px and 7.4 px; plot left/right/bottom inset
  ratios are approximately 6.0%, 5.8% and 10.7%. The finite-data-derived 10% range headroom is
  unchanged.

The main agent opened both MAT-EXP candidates, their four responsive siblings, all 12 MAT-EXP state
images, all four MOD-FIT candidates and all 12 MOD-FIT state images at original resolution. It
found no remaining title/scrollbar overlap, missing axis title, axis collision, page overflow or
topology regression.

Deterministic result before fresh read-only re-review:

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
approved Materials normal validators and hashes             3 / pass / unchanged
approved MOD-DATA / MOD-PROCESS parent validators            pass / unchanged
native tree gutter / custom overlay                         15 px / absent
visible x title / x-title-to-tick gap                       13 px / 0–18 px
y-title-to-tick / y-tick-to-axis gaps                       2–24 px / 2–12 px
plot left/right/bottom inset ratios                         <=6.5% / <=6.5% / <=11.5%
Ruff / Node syntax / inventory / diff checks                pass
inventory progress                                           22/72 approved; 50 remaining
```

Current pending candidate hashes:

```text
materials-search-long-1440x900
  bc3812759e3fae464fde19782767e5680f10ba343898f3beb9d59b362613a66d
materials-search-empty-1440x900
  35e814d1e807468f97e3daaa6507a4ae98bba1a1e5d3fa2dc731a0e77a922725
modeling-fit-normal-1366x768
  5d3a59d3fb6a947defd23450fee2f979f81fb16687381343bea5b94de962f504
modeling-fit-normal-1440x900
  be4a9b051a266c4f8c55ebb0136046c3c016e6beaf278669200c91046ead8749
modeling-fit-normal-1920x1080
  4bd100acbe61bcaa5359949da9ef602ac7b64493799fb66ecaeb65a58ef0a4bf
modeling-fit-candidate-parameters-long-1440x900
  84d5ba46d5fa81850376558595c75b73f1a1a6b5c7a4c9a0721e782155f3d545
```

Two fresh read-only Terra High reviewers independently opened their complete family bundles at
original resolution and returned `approve`, V-01–V-16 all `2`, total `32/32`, with no hard-gate
failure or actionable finding. MAT-EXP has no material residual concern. MOD-FIT retains one
non-blocking observation: calculation/stale/error overlays intentionally cross the upper plot area,
but remain readable and preserve the graph/context at all three viewports.

All six family lifecycles remain `pending`, main-agent evaluation is now `accepted`, and
product-owner approval remains absent. Progress remains 22/72 approved with 50 remaining until the
product owner approves these exact hashes.

## 26. WAVE-03 product-owner rebuild authorization

Date: 2026-07-29

The product owner did not approve the six candidates in section 25. In addition to the earlier
scrollbar and axis-spacing defects, direct review identified that:

- both long tree and result regions need discoverable local scrolling and more usable long-identity
  access;
- the Fit ribbon, decision band, horizontal legend and parameter drawer still reduce graph
  visibility;
- the fixed SVG uses `preserveAspectRatio="none"`, visibly distorting engineering typography at
  wider viewports;
- the hardening response is mislabeled and physically inconsistent: it plots `(0, 0)` although the
  current contract is positive true yield stress versus true plastic strain.

The product owner authorized rebuilding the same six still-pending candidates with all eight
findings applied together. The existing direct-main-agent exception remains in force: the main Sol
High agent owns the rebuild, followed by deterministic gates, original-resolution inspection and
one fresh configured Terra High read-only review. No other writing model is substituted.

The authoritative rebuild packet is
[WAVE-03 product-owner rebuild packet](issue-167-product-owner-rebuild-packet-wave-03.md).
Lifecycle progress remains 22/72 approved with 50 remaining. Approved parents, production code and
all later bundles remain frozen.

## 27. WAVE-03 integrated eight-finding rebuild and reviewer handoff

Date: 2026-07-29

The user-authorized main Sol High rebuild applied the complete eight-finding packet to the same six
still-pending references. No approved parent, production React/CSS, other family, inventory
denominator or GitHub state changed.

MAT-EXP now has independent native tree and long-result scrolling. The 1440 long tree measures
249 px client width against 558 px scroll width, with 190 px vertical and 309 px horizontal
overflow. Arrow-key horizontal scrolling and wheel/PageDown vertical scrolling produce local
consequences without moving the document. Full Database/Profile/Table/Folder/Record identities and
accessible labels are retained instead of permanently truncating their underlying strings. The
long result keeps 50 of 126 rows, one truthful selected material and 1127 px of independently
scrollable vertical result overflow.

MOD-FIT now uses a measured responsive SVG whose viewBox exactly matches its rendered width and
height at every capture; `preserveAspectRatio="none"` and non-uniform scaling are absent. A compact
11 px tick / 11.5 px title grammar, centered `True plastic strain [1]` x title, unit-bearing
`True yield stress (MPa)` y title and right-side legend leave the graph dominant. The 1440 normal
actual plot is 481 px high and uses 80.2% of the Fit workspace; the long state retains an
approximately 375 px plot above a 148 px independently scrollable candidate drawer. The synthetic
hardening fixtures use deterministic public law forms, start every curve at zero true plastic
strain and positive 312 MPa initial yield stress, and derive the displayed 0–0.50 / 200–1400 MPa
nice ranges from finite plotted spans plus 10% proportional headroom.

The main agent opened all 18 MAT-EXP and 16 MOD-FIT images at original resolution. It found the
information density, local-scroll behavior, graph dominance, compact axis typography, right-side
legend, undistorted responsive geometry and state continuity acceptable. Loading, empty,
stale/blocked and error states preserve their relevant graph/source or selection context without
page overflow.

Deterministic result before fresh read-only review:

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
tree/result independent scrolling and native bars           pass
full tree identity access / no text-covering overlay         pass
responsive SVG viewBox/rendered size / scale delta           exact / 0
quantity/unit/start-point contracts                          pass
axis/legend containment and collision gates                 pass
normal/long graph dominance and drawer bounds                pass
console/page errors / document overflow / nested controls   zero
Web Interface Guidelines audit                              pass
approved-parent validators and hashes                       pass / unchanged
Ruff / Node syntax / inventory / diff checks                pass
inventory progress                                           22/72 approved; 50 remaining
```

Current pending candidate hashes:

```text
materials-search-long-1440x900
  c486fc6f6236c44083e2d8a52502be6d59729f2e8849ffcb46301ca9ef2365a2
materials-search-empty-1440x900
  9ce804bf79dcb083ccb979a15b2245847e30fae6da5849dba6a6c351706d03b0
modeling-fit-normal-1366x768
  6752cb38650332daadf0273903e99319ca807e92c4d797a0ca4c314304524543
modeling-fit-normal-1440x900
  6c4ad9a9b73f956cb3986017e7afc403f19fb8dfe9450ac078ee69c937be57ac
modeling-fit-normal-1920x1080
  ee2d95c45fc8c01e0ed02eb96832bcdaa8c290341e2c211ac8209378b2bd00c5
modeling-fit-candidate-parameters-long-1440x900
  336eafcad832cf0f149d32fc7aad2c880b97b9ba0c1df000a7cc8fe4f847b180
```

The bounded fresh review packet is
[WAVE-03 integrated rebuild reviewer packet](issue-167-reviewer-packet-wave-03-rebuild.md).
All six references remain `pending`, main-agent evaluation is `accepted`, product-owner approval is
absent, and progress remains 22/72 approved with 50 remaining.

The configured fresh Terra High read-only reviewer then opened the complete 18-image MAT-EXP and
16-image MOD-FIT bundles at original resolution, verified every listed hash/dimension and reran the
bounded non-mutating gates. It returned `approve`, V-01–V-16 all `2`, total `32/32`, with no hard
gate failure or actionable finding. The only residual observation is the expected pending
product-owner lifecycle.

## 28. WAVE-03 final product-owner tree/legend amendment

Date: 2026-07-29

The product owner did not approve the section 27 hashes. Direct inspection established two defects
that deterministic DOM overflow checks and the earlier qualitative review failed to catch:

- the Materials tree/result panes are technically scrollable, but the captured pixels do not make
  their operating scrollbars discoverable; verbose explanation appended to nearly every tree node
  also makes the navigator coarser than the supplied compact tree reference;
- the Fit curve legend still taxes graph width as a permanent right column although the current
  response leaves a safe lower-right plot region.

These are cumulative findings 9 and 10 in the updated
[WAVE-03 product-owner rebuild packet](issue-167-product-owner-rebuild-packet-wave-03.md), not a
replacement for findings 1–8. The product-wide desktop UI specification and visual acceptance
matrix now require perceptually visible reserved scroll controls, concise tree identities and a
collision-checked plot-internal curve legend with measured fallback.

The six section 27 images and hashes remain historical unapproved evidence. Their lifecycle remains
`pending`; main-agent evaluation is reset to `pending-rebuild`, product-owner approval remains
absent, and inventory progress remains 22/72 approved with 50 remaining. The authorized main Sol
High direct correction, deterministic gates, original-resolution main-agent inspection and one
fresh configured Terra High read-only review remain the required execution path. Approved parents,
production React/CSS, other families and GitHub state remain frozen.

## 29. WAVE-03 cumulative ten-finding rebuild and final reviewer handoff

Date: 2026-07-29

The main Sol High agent applied the section 28 amendment to the same six pending references. The
product-wide specification, UI component contract, visual acceptance matrix and WAVE-03 rebuild
packet now retain all ten cumulative findings.

MAT-EXP now uses reserved application-owned scrollbar rails synchronized with the native scrolling
viewport. At 1440×900 the tree measures 251 px client width against 561 px content width, with
199 px vertical and 310 px horizontal overflow. Its vertical and horizontal thumbs measure 363 px
and 111 px, remain outside the text viewport and are operable by pointer, keyboard and wheel. The
long result has 1127 px local vertical overflow and a 270 px proportional thumb. The empty result
has no fake rail. Tree labels are concise stored identities with regular disclosure/type glyphs;
the complete few genuinely long identities remain reachable through the conditional horizontal
rail.

MOD-FIT no longer reserves an external legend column. The curve-only legend uses the measured
lower-right plot region at 1366×768, 1440×900, 1920×1080 and the 1440×900 long state. Independent
segment sampling reports zero curve intersection, the placement algorithm reports zero collision,
the legend stays inside the plot stage and external width tax is 0 px. Plot widths are respectively
1177 px, 1243 px, 1707 px and 1243 px. The long state keeps a 336 px actual plot above the bounded
candidate drawer. A geometry-aware alternate-quadrant search and compact docked fallback remain
available when changed data would occupy the current region.

The main agent opened all 18 MAT-EXP and all 16 MOD-FIT images at original resolution. It found the
scroll controls perceptually discoverable, tree density materially improved, graph width recovered,
axis typography/quantities consistent and curve/legend/state-overlay relationships clear at every
viewport. Loading, empty, stale/blocked and error states retain the applicable result/source,
selection and recovery context without page overflow.

Deterministic result before fresh read-only review:

```text
MAT-EXP approval/responsive/state targets                   18 / pass
MOD-FIT approval/state targets                              4 + 12 / pass
tree visible vertical/horizontal rails and thumb contrast   pass
tree/result pointer, keyboard and wheel consequences        pass
empty result fake scrollbar                                absent
Fit lower-right legend / collision / external width tax     pass / 0 / 0 px
responsive SVG viewBox/rendered size / scale delta           exact / 0
quantity/unit/start-point and proportional range contracts  pass
axis/title/legend containment and graph dominance           pass
loading/empty/stale/error continuity                        pass
console/page errors / document overflow / nested controls   zero
Web Interface Guidelines audit                              pass
approved-parent validators and hashes                       pass / unchanged
Ruff / Node syntax / inventory / documentation impact       pass
user-guide image-reference check                            not a #167 gate; reports the existing
                                                            untracked service-reference image set
inventory progress                                           22/72 approved; 50 remaining
```

Current pending candidate hashes:

```text
materials-search-long-1440x900
  43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484
materials-search-empty-1440x900
  d9e4fed1d8c17ca86b7c14dfe57909591b44ff8ec300286bb49f3a940fb5e1b1
modeling-fit-normal-1366x768
  eb8c23a9df376f1ab9a7604f29088bf022af10f49a0f9310f55c8308fbeb0843
modeling-fit-normal-1440x900
  0cacfb3970d015a78f231c160f3f2b8fa15a917653740acdbf51aed874b31fd8
modeling-fit-normal-1920x1080
  06ef5ba17d8fdfc6eb2ef80cb592b55d8b18fd0f99067472b81da5fc674fa18b
modeling-fit-candidate-parameters-long-1440x900
  ad8166d12a647f0908fbc59997eeb87d063b79fa44a4bb095b45d8ed22346424
```

The bounded final review packet is
[WAVE-03 final scroll/legend reviewer packet](issue-167-reviewer-packet-wave-03-final-scroll-legend.md).
All six references remain `pending`; main-agent evaluation is `accepted`, product-owner approval is
absent and progress remains 22/72 approved with 50 remaining.

Fresh configured Terra High read-only review result:

```text
disposition                                  approve for product-owner review
V-01–V-16 / total                            2 each / 32 of 32
hard gates / actionable findings             pass / none
original artifact evidence                   34 of 34 dimensions and hashes matched
bounded validators / Ruff / Node / diff      pass
non-blocking residual                        seven-entry Fit legend is compact at 1366×768,
                                             but readable, contained and curve-free
```

This reviewer disposition does not change lifecycle state. The six references still await explicit
product-owner approval and inventory progress remains 22/72 approved with 50 remaining.

## 30. WAVE-03 Fit navigator visual-consistency amendment

Date: 2026-07-29

The product owner accepted the corrected Materials tree treatment but found the Fit left rail
qualitatively awkward in typography and arrangement. Direct comparison confirmed that the rail's
function was correct but its bold 13 px specimen names, circular color marks, uppercase section
chrome and weak parent/child indentation compressed several distinct decisions into a coarse visual
block. This was not detected by the prior numeric row-height and graph-dominance gates.

The product specification, canonical UI contract, visual acceptance matrix and WAVE-03 rebuild
packet now retain this as cumulative finding 11. Modeling does not copy the Database/Profile/Table/
Folder/Record hierarchy. It adopts the same flat desktop grammar while keeping its stage-specific
membership checkbox, curve selection, plot-color sample and visibility command.

The main Sol High agent corrected the existing Fit reference directly:

- responsive rail widths remain 184/192/208 px, so no graph-width tax or stage-topology change was
  introduced;
- section labels use sentence case and 11.5 px metadata;
- specimen identities use regular 12.5 px text with secondary 11.5 px revision text;
- the method parent has an aligned disclosure/type glyph and its children have one stable indent;
- plot colors use 3×16 px vertical samples rather than circular badges;
- selected rows use the same restrained fill and 3 px leading accent as Materials;
- `True/plastic conversion` fits at the 184 px minimum rather than truncating;
- overflow remains local with a stable conditional scrollbar gutter.

The deterministic navigator gate independently proves all three specimen identities, revisions and
four sequence labels are unclipped at every required viewport; identity weight is 400, hierarchy
indentation is within the 8–24 px contract, section text transformation is `none`, the curve sample
is a square-cornered line, selected fill differs from the rail background, and injected long rail
content scrolls without changing graph width.

The main agent opened the four approval candidates and all twelve empty/calculating/stale/error
captures at original resolution. It found the rail materially calmer and more legible, with clearer
method/specimen/sequence hierarchy and no loss of graph dominance, axis/legend quality, drawer
containment or recovery context.

Current corrected Fit hashes:

```text
modeling-fit-normal-1366x768
  41a775d88b32c9528d742858fdfbcf86dda6b391f3ad704337ee9d9781487a93
modeling-fit-normal-1440x900
  7ba66c5f5d5605dd897f1bb511fcaa888985c5472d378a56ce849ded55ed0db5
modeling-fit-normal-1920x1080
  f7a6aaf8720659bdadf1559347e08b8d1c5b920633c8ce954b34ba39aa7ee261
modeling-fit-candidate-parameters-long-1440x900
  500e66fa38e8b7f6adde92f7aa3f309a41aa7f27cb5ef3ebe322fad07abce881
```

The two Materials candidates and their hashes are unchanged. All six WAVE-03 candidates remain
`pending` for product-owner approval; inventory progress remains 22/72 approved with 50 remaining.

Fresh configured Terra High read-only review result:

```text
disposition                                  approve for product-owner review
V-01–V-16 / total                            2 each / 32 of 32
hard gates / actionable findings             pass / none
four candidates + twelve state images        original-resolution review and hashes pass
Fit validator / Ruff / Node / diff           pass
non-blocking residual                        long rail scroll is deterministic interaction evidence;
                                             the short normal rail does not itself overflow
```

This disposition does not alter lifecycle. The four corrected Fit references still require explicit
product-owner approval.

## 31. WAVE-03 corrected Modeling Fit product-owner approval

Date: 2026-07-29

The product owner explicitly approved the four corrected Modeling Fit references submitted from
section 30:

```text
modeling-fit-normal-1366x768
  41a775d88b32c9528d742858fdfbcf86dda6b391f3ad704337ee9d9781487a93
modeling-fit-normal-1440x900
  7ba66c5f5d5605dd897f1bb511fcaa888985c5472d378a56ce849ded55ed0db5
modeling-fit-normal-1920x1080
  f7a6aaf8720659bdadf1559347e08b8d1c5b920633c8ce954b34ba39aa7ee261
modeling-fit-candidate-parameters-long-1440x900
  500e66fa38e8b7f6adde92f7aa3f309a41aa7f27cb5ef3ebe322fad07abce881
```

Each exact manifest lifecycle is now `approved`, with product-owner approval dated 2026-07-29.
The two unchanged Materials WAVE-03 candidates were not part of the four-image submission and remain
`pending`; they are not inferred as approved from the Fit response. Inventory progress advances to
26/72 approved with 46 remaining. No later reference, production React/CSS, commit, push, PR or merge
was started as part of this lifecycle update.

Post-approval validation passed the 18-family/13-bundle inventory reconciliation, all four MOD-FIT
approval targets and state/interaction gates, and the scoped diff check.

## 32. Qualitative review workflow hardening

Date: 2026-07-29

After auditing the prior review outcomes, the product owner retained the fresh Terra High reviewer as
an independent contract, evidence, accessibility and full-screen usability gate, but explicitly
rejected treating its numeric score as final design approval. The main agent remains responsible for
product/UX judgment and the product owner remains the final visual approver.

The visual acceptance matrix now owns one mandatory Q-01–Q-11 qualitative checklist containing the
eleven cumulative product-owner findings. The desktop-engineering skill, root instructions and Terra
reviewer configuration require independent original-resolution checklist evidence. An applicable
qualitative failure blocks handoff even when deterministic gates and V-01–V-16 pass. A generic Web
Interface Guidelines audit remains supplemental rather than CAE design authority.

Project `.codex/config.toml` now pins future project sessions to `gpt-5.6-sol` with `xhigh` reasoning.
The fresh reviewer remains `gpt-5.6-terra` with `high` reasoning and read-only access. The active
turn inherited the pre-existing global `gpt-5.6-sol`/`xhigh` configuration and cannot change model
mid-turn. The active `/root` primary agent and the main agent are the same role; implementer and
reviewer are subordinate agents. Future sessions can verify the project pin directly instead of
inferring identity from the role name.

This process change does not alter any approved or pending reference lifecycle, image, hash,
production React/CSS, commit, push, PR or merge state.

## 33. GitHub #167 progress checklist synchronization

Date: 2026-07-29

GitHub issue #167 previously contained no task checkboxes and retained the older Sol High,
single-writer and score-oriented reviewer wording. Its body now matches the repository authority:

- the active `/root` primary agent is the Sol XHigh main agent;
- #167 may use at most two dependency-independent, disjoint screen-family writers;
- both main agent and fresh Terra High reviewer must complete Q-01–Q-11 at original resolution;
- reviewer score cannot replace main-agent judgment or product-owner approval.

The issue now records the verified 18-family/13-bundle/72-image inventory, lifecycle evidence system,
five fully approved bundles, MAT-EXP at 3/5 and total progress at 26/72. Only completed facts are
checked. The remaining 46 images, whole-set deterministic gate and #167 PR/merge remain unchecked;
the issue remains open.

## 34. WAVE-04 bounded batch start

Date: 2026-07-29

To reduce product-owner wait time without weakening the per-image lifecycle, the main `/root` Sol
XHigh agent inspected the next dependency-independent families and their exact current contracts:

- `MOD-EXPORT` depends on the approved `MOD-FIT` bundle and owns six approval candidates;
- `ACT-QUEUE` freezes ACT-U before its ACT-R role extension and owns seven approval candidates.

The main agent compared the approved Modeling Fit graph/source shell, approved Materials native-card
preview, prior reference-only Export/Activity captures, current React/API/state contracts and the
Q-01–Q-11 qualitative owner checklist. It then persisted two disjoint implementer packets:

- `issue-167-implementer-packet-mod-export-wave-04.md`
- `issue-167-implementer-packet-act-queue-wave-04.md`

The packets prohibit shared CSS/JavaScript, manifest, inventory, common-evidence and production
edits. They reserve separate source/capture/image ownership and require original-resolution
qualitative self-review in addition to deterministic gates. One configured Luna Max implementer may
now write each family concurrently under the bounded #167 two-writer rule.

No new reference has been generated, reviewed or approved at this point. The two pending MAT-EXP
references remain unchanged. Inventory progress remains 26/72 approved with 46 remaining.

## 35. WAVE-04 MOD-EXPORT main-agent rejection and sole correction

Date: 2026-07-29

The Luna Max MOD-EXPORT writer completed six approval images and twelve responsive state images. Its
capture, family validator, approved Fit dependency validator, inventory, Ruff, JavaScript syntax and
scoped diff gates passed. The active `/root` main agent nevertheless rejected the family after
opening all six approval images at original resolution.

The deterministic gate had missed contradictory state labels, inconsistent mapping counts/visible
rows, an incorrect stress unit attached to plastic strain, an absent delivered-receipt action and an
unsafe source-blocked command hierarchy. The source graph also retained axis/legend glyphs too small
for useful 1366/1440 inspection. Q-11 was incorrectly marked applicable to an Export properties pane
that has no Fit rail.

These findings are persisted in
`issue-167-correction-packet-wave-04-mod-export.md`. Under the configured one-correction rule, one
fresh Terra High correction implementer will update only writer-owned MOD-EXPORT paths, strengthen
the validator and regenerate the evidence. No lifecycle status changes: the six candidates remain
pending/not accepted, the two MAT-EXP candidates remain pending and inventory progress remains
26/72 approved with 46 remaining.

## 36. WAVE-04 ACT-QUEUE main-agent rejection and sole correction

Date: 2026-07-29

The Luna Max ACT-QUEUE writer completed seven approval images and twenty-one responsive state images.
Its family validator, inventory, Ruff, JavaScript syntax and scoped diff gates passed. The active
`/root` main agent opened all seven approval images at original resolution. The six User/Reviewer
normal images passed the main qualitative topology check, but the canonical Reviewer long-decision-
error image did not.

The preserved non-empty reason was paired with `Reason is required`, the initial page status still
said `Ready`, and filled `Record decision` plus a separate Retry created an ambiguous duplicate
recovery. The automated gate had checked that the form and Retry existed but not their coherent
relationship.

The bounded correction is persisted in
`issue-167-correction-packet-wave-04-act-queue.md`. One fresh Terra High correction implementer will
update only ACT-QUEUE-owned paths, strengthen the state assertions and regenerate the bundle. No
lifecycle status changes: all seven Activity candidates remain pending/not accepted, the six Export
candidates remain in correction, the two MAT-EXP candidates remain pending and progress remains
26/72 approved with 46 remaining.

## 37. WAVE-04 ACT-QUEUE corrected main-agent acceptance

Date: 2026-07-29

The sole Terra High correction resolved the three contradictions identified in section 36. The
active `/root` Sol XHigh main agent then opened all seven approval images and all twenty-one
responsive state images at original resolution. The corrected service-error state preserves the
selected request, decision and non-empty reason, reports `Decision not recorded` and exposes one
`Retry decision`. The stale/unauthorized state separately reports that review access needs refresh,
retains the selected request and reason, exposes one `Refresh access` and cannot submit a decision.

The main qualitative record is Q-02 and Q-09 pass: the compact Reviewer queue has a distinct local
overflow rail and the empty User result has no fake rail; pointer, wheel and keyboard consequences
are persisted. Q-01 and Q-03–Q-08/Q-10/Q-11 are not applicable because Activity has no navigator
tree, Materials navigator, Fit graph/axes/legend or Fit rail.

Final approval candidates:

| Reference | SHA-256 |
| --- | --- |
| `activity-user-normal-1366x768.png` | `45ecff451bdd3b3f7d11cf8b6afb1f25cda17be19a4118c68ba5d4c37745e523` |
| `activity-user-normal-1440x900.png` | `12b9cb7bd6d16ae57521ac69ac5dd61160d8ce3423d13e00ee66361cedfcc2aa` |
| `activity-user-normal-1920x1080.png` | `46cfb14e2a1ca9c8953d408004e9eff47d25c1fc7c4c311ff761509c4bd652ce` |
| `activity-reviewer-normal-1366x768.png` | `8139b08582acb9ff1595490a88486f6b4eff684271f5775a14b357c125f0b29b` |
| `activity-reviewer-normal-1440x900.png` | `daf7a2bacafaf0ae2f3c254a8a055fd4e57f6eb3dda05480726a90e9521fef3b` |
| `activity-reviewer-normal-1920x1080.png` | `517ffdde4f5b1c49da291acd97c2f6abab9a8318e7793f05ceebeabb9db50c7b` |
| `activity-reviewer-long-decision-error-1440x900.png` | `bbcfcadd5555273afd030973f1f9e0da5ea18494722e975de3796eb0a90baaaa` |

The final family validator passes all seven approval targets, all seven three-viewport state
bundles and deterministic pointer/keyboard/recovery evidence. Inventory, Ruff, JavaScript syntax
and scoped diff checks pass. The seven common-manifest entries remain `pending`, record main-agent
acceptance and intentionally have product-owner approval absent. A bounded fresh read-only reviewer
packet is persisted at `issue-167-reviewer-packet-wave-04-act-queue.md`.

The fresh Terra High reviewer independently opened the same twenty-eight images at original
resolution and reran the bounded validator. Disposition: `approve`; V-01–V-16 all `2` for `32/32`;
Q-02/Q-09 pass with the same direct queue/overflow evidence; all other Q items are not applicable
for the recorded topology. There is no hard-gate failure, actionable finding or material residual
concern. Product-owner approval remains absent.

## 38. WAVE-04 MOD-EXPORT corrected main-agent acceptance

Date: 2026-07-29

The sole Terra High correction resolved the section 35 rejection. Before reviewer handoff, the
active `/root` Sol XHigh main agent opened the six approval images, twelve same-topology state images
and six exceptional responsive siblings at original resolution. This direct review found and
corrected additional automated-gate gaps: an ellipsized source-context quantity, concrete target
defaults in the no-target state, loading status/action contradictions, an incoherent delivery-retry
label, inaccessible long mapping rows and missing three-viewport evidence for the topology-changing
approval states.

The final source graph labels `Yield stress (MPa)` against `True plastic strain [1]`, starts at a
positive initial yield stress, preserves responsive glyph/stroke proportions and keeps its compact
legend in a curve-free region. The long mapping evidence exposes all 28 wrapped identities through
a reserved local scroll rail. Source-blocked, approximation-blocked and delivered preserve truthful
action/lifecycle boundaries at 1366, 1440 and 1920.

Final approval candidates:

| Reference | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `2e19f612f7ff6edc026f11541e64e32c7c03e75738fcc39af2c17df87d37ab43` |
| `modeling-export-normal-1440x900.png` | `514a88da7d0106b1a5522724de58b173bc98998eb543370f681c1c1572493a92` |
| `modeling-export-normal-1920x1080.png` | `2798779cb7c87a160a7a41014eb0de690c92dfb672399c513aefc48b20006e7c` |
| `modeling-export-source-blocked-1440x900.png` | `25cf93f53351919643775fb79789e8a0b9eace914a0c17e131446161cc934554` |
| `modeling-export-approximation-blocked-1440x900.png` | `374ac6b28dbc5723aac6ae73db1dfe3994eb67ad987c7bde66e8bd974d82efae` |
| `modeling-export-delivered-1440x900.png` | `de49f9feeec1e90f57d7f89587c450bf903d005d9cececfd8f6eeb3dfb44b134` |

The main qualitative record is Q-05–Q-10 pass. Q-01–Q-04 and Q-11 are not applicable because
Export has no navigator tree, result list, Materials navigator, Fit control ribbon or Fit curve
rail. The final capture/validator, MOD-FIT dependency validator, inventory, Ruff, JavaScript syntax
and scoped diff checks pass. Six common-manifest entries remain `pending`, record main-agent
acceptance and intentionally have product-owner approval absent. The fresh read-only reviewer packet
is persisted at `issue-167-reviewer-packet-wave-04-mod-export.md`.

The fresh Terra High reviewer independently opened all twenty-four final images at original
resolution and reran the bounded validator. Disposition: `approve`; V-01–V-16 all `2` for `32/32`;
Q-05–Q-10 pass and Q-01–Q-04/Q-11 are not applicable for the recorded topology. All image hashes,
the 28-row local scroll ranges, state semantics and responsive evidence match. There is no
hard-gate failure, actionable finding or material residual concern. Product-owner approval remains
absent.

## 39. WAVE-04 MOD-EXPORT product-owner layout and semantics rework

Date: 2026-07-29

The product owner did not approve the section 38 candidates. The independent reviewer result did not
override the product-owner findings: the full-width shallow graph compressed the result, the black
native-card surface was visually alien to the rest of the workspace, and developer/governance-first
labels such as `Export preflight`, `Next safe action`, `Mapping sheet`, `Preflight evidence` and
normal-path `receipt/evidence` did not explain a user task.

The product owner approved a rough region direction with Destination and generation status at left,
a dominant light Solver Card preview in the center, and read-only Mapping details above a compact Fit
source preview at right. Follow-up discussion clarified:

- Mapping rows/statuses are deterministic for one exact source/target tuple but change when the
  source family, solver/version/unit capability or representability changes.
- Density and other physical source values are read-only in Export. Export may change their output
  representation but never edits the governed source revision.
- Material State is source/applicability context unless it becomes an actual target dependency; it
  is not counted merely to produce another exact mapping.
- Export status has three user states: Ready to create, Review required and Cannot create.
- metal, linear-viscoelastic and hyperelastic sources retain one region topology but require
  family-specific mapping rows and graph quantities.

Direct contract inspection also found that the old static preview labelled the target `kg_m_s` while
emitting tonne/mm³ and MPa-scale native values. The replacement reference must use internally
consistent synthetic kg/m³ and Pa values and show Source/Output units. It must preserve the backend
technical mapping report under Advanced rather than changing exact/transformed/approximated/
unsupported semantics for visual convenience.

The clarified product rules are now authoritative in the product spec, UI field contract and
Modeling Export acceptance gate. The main agent persisted the bounded replacement packet at:

`docs/17-evidence/reports/issue-167-product-owner-rework-packet-wave-04-mod-export.md`

One configured Luna Max writer may replace only unapproved MOD-EXPORT-owned source/capture/evidence.
The six manifest entries remain pending, their previous hashes remain historical unapproved evidence
until serial main-agent integration, and progress remains 26/72. No approved dependency, production
React/API/backend, inventory count, commit, push, PR or merge is changed.

## 40. WAVE-04 MOD-EXPORT product rework — corrected main-agent acceptance

Date: 2026-07-29

The configured Luna Max writer replaced the unapproved section 38 candidates from the product-owner
packet in section 39. Its first result passed the family validator but failed Ruff and the main
agent's original-resolution product/contract gate. One fresh configured Terra High correction agent
then remained the sole correction writer while the active `/root` Sol XHigh main agent completed the
full approval/state/family image review.

That direct review blocked issues which numeric success alone did not prove:

- source-blocked copy retained a stale saved Fit identity;
- OpenRadioss incorrectly inherited Abaqus's transformed unit status;
- normal delivered copy exposed receipt vocabulary instead of Delivery details;
- linear-viscoelastic and hyperelastic readiness claimed an approximation while their rows counted
  zero;
- the hyperelastic x-axis title fell behind the status bar and the viscoelastic legend crossed its
  descending curve;
- rejected `preflight`/`evidence` language survived in exceptional states;
- delivery error exposed two retry actions;
- no-target fabricated a concrete version/unit/mapping result and dimmed an otherwise exact upstream
  Fit source.

The corrected two-pane workspace now keeps Destination and Export check at left, a dominant light
native Solver Card preview in the center, and Mapping details above a compact family-specific Fit
source at right. Physical source values are read-only. The normal kg-m-s fixture consistently uses
kg/m³ and Pa; target mappings show Source/Output consequences. Abaqus reports Exact 2 /
Transformed 3 / Approximated 1, while the OpenRadioss review state correctly reports Exact 3 /
Transformed 2 / Approximated 1. No-target exposes no concrete target tuple or mapping result.
Source-blocked exposes no stale Fit identity. Delivered exposes `Open solver card` and
`Delivery details`, with receipt identity disclosed only after that bounded action or Advanced.

Family evidence preserves the same topology while changing actual quantities and rows:

- metal: `True stress (MPa)` versus `True plastic strain [1]`, positive initial yield stress;
- linear viscoelastic: `Normalized shear modulus [1]` versus `log time (s)`, upper-right curve-free
  legend;
- hyperelastic: `Nominal stress (kPa)` versus `Stretch ratio [1]`, with selected mode controls.

The main qualitative owner checklist is:

| Item | Result | Direct evidence |
| --- | --- | --- |
| Q-01 | not-applicable | Export has no navigator tree. |
| Q-02 | not-applicable | Mapping details are decision consequences, not a result list; their overflow is covered by Q-09. |
| Q-03 | not-applicable | Materials navigation is not mounted in Modeling Export. |
| Q-04 | not-applicable | Fit controls/candidate drawer are upstream; Export retains only source context. |
| Q-05 | pass | All three family graphs show compact quantity/unit titles, clear ticks and titles above the status bar. |
| Q-06 | pass | Legends remain compact and inside the bounded Fit source rather than forming a footer. |
| Q-07 | pass | SVGs use uniform `preserveAspectRatio`, stable glyph/stroke scale and validated container bounds. |
| Q-08 | pass | Metal uses true stress versus true plastic strain and begins at positive stress at zero plastic strain. |
| Q-09 | pass | Setup, Mapping details and native preview reserve local tracks; 28-row/long-native pointer, wheel and keyboard evidence passes. |
| Q-10 | pass | Metal/hyperelastic legends use curve-free lower-right space; viscoelastic uses curve-free upper-right space with deterministic collision checks. |
| Q-11 | not-applicable | Export has no Fit curve rail. |

Final approval candidates:

| Reference | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `5a4b4f3c728cb9844f092bbbc57f5fc378068962247919d10374239c72d59b6d` |
| `modeling-export-normal-1440x900.png` | `8fcb8a8465ecc1cebdfc596ef6df5382ca3313c35d68d343161e92ddbbf389e5` |
| `modeling-export-normal-1920x1080.png` | `77260893b0808266b02b1940fe54a11fec9464680542a591fbd6ceb2e54a4f74` |
| `modeling-export-source-blocked-1440x900.png` | `376c4134269f964e7d408636c22ed08aab563589a4a2c57bf10067e5af321d37` |
| `modeling-export-approximation-blocked-1440x900.png` | `dae621e1ed1ef4835b50c919dd30d9cc560b964d5d31bef3fda9ab3acd8f2bc8` |
| `modeling-export-delivered-1440x900.png` | `9bbe26cc0b68a4efe582d8daff16f4de3aed18aa2518ab4c2ea4f3763d044922` |

The MOD-EXPORT validator passes all six targets, seven state bundles, two family adaptations,
interaction invalidation, acknowledgement, immutable creation, receipt-disclosure, action-count,
language, overflow, accessibility, graph-bound and legend-collision gates. The accepted MOD-FIT
dependency validator, inventory, Ruff, JavaScript syntax, Web Interface Guidelines audit and
`git diff --check` pass. The six common-manifest entries remain `pending`, now contain the final
hashes and main-agent acceptance, and intentionally retain product-owner approval `absent`.

The bounded fresh read-only reviewer packet is:

`docs/17-evidence/reports/issue-167-reviewer-packet-wave-04-mod-export-product-rework.md`

## 41. WAVE-04 MOD-EXPORT product rework — fresh review and final internal gate

Date: 2026-07-29

One fresh configured Terra High read-only reviewer opened all 26 final MOD-EXPORT approval, state,
responsive and family images at original resolution, excluding only the rough layout concept. It
reran the bounded MOD-EXPORT validator with pending lifecycle and returned `approve`.

Independent results:

- V-01–V-16: 32/32, no hard-gate failure;
- Q-05–Q-10: pass;
- Q-01–Q-04 and Q-11: justified not-applicable for Export topology;
- hashes, source/target/unit consistency, Abaqus/OpenRadioss mapping difference, no-target and
  source-blocked truth boundaries, exact acknowledgement, immutable Solver Card creation, bounded
  receipt disclosure, family-specific readiness/axes/legend placement, local overflow, keyboard
  paths and discarded-language absence all pass;
- no actionable finding or residual reviewer concern.

After that disposition, the active `/root` Sol XHigh main agent reopened the six approval images at
original resolution. The final internal product/UX judgment remains accepted: the light native
preview is dominant, the setup/result-context topology remains coherent at all three normal
viewports, status/actions follow the actual state, engineering graph quantities and legends remain
professional and readable, and no clipping/overlap/semantic contradiction blocks product-owner
handoff.

The six references remain `pending` with product-owner approval `absent`. No later reference,
production React/CSS, commit, push, PR or merge starts before the product owner responds.

## 42. WAVE-04 MOD-EXPORT post-review product-owner rejection and main-agent correction

Date: 2026-07-29

The product owner rejected the section 41 images after the configured writer, sole correction and
fresh re-review had completed. Therefore the section 41 reviewer disposition remains valid only for
its recorded hashes and is superseded for the current candidates. The product owner explicitly
authorized the active `/root` main agent to make this correction directly. No substitute writer and
no additional LLM reviewer was invoked.

The correction treats the feedback as a product-language and information-composition failure, not a
set of isolated pixel requests:

- the Fit source plot now computes ten-percent headroom from each displayed data span rather than
  absolute constants; the metal zero-plastic-strain anchor remains at zero, curves clear the frame,
  SVG geometry stays uniform and each material family keeps its own quantities and units;
- the left setup pane now contains only selected model/Fit identity, Destination and one Export
  check. Duplicate Density, Source/Output, Saved/Pinned and explanatory lineage prose were removed;
- Mapping details now use one compact title/value/status grammar. Technical mapping counts and
  classifications remain under the closed Advanced disclosure instead of being narrated in every
  row;
- readiness appears once as `Ready to create`, `Review required` or `Cannot create`, followed by one
  exact action or blocker. Preview and Mapping details no longer repeat the same state in competing
  alert treatments;
- the native solver-card preview remains dominant. Six normal mapping rows fit without a decorative
  scrollbar; genuine long mapping and native output expose independent visible proportional scroll
  affordances.

These findings are now permanent policy in the canonical qualitative owner checklist as Q-12–Q-16,
in addition to the earlier Q-01–Q-11 requirements. The Export UI field contracts and product policy
record the same information-economy, readiness, graph-domain and local-overflow rules so later
implementation and review packets cannot rely on chat memory.

Current approval hashes:

| Approval image | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `f78a74e87f0274405908443f0aae5971b9a35c2c480d03a5b6a9f6db3d6171dc` |
| `modeling-export-normal-1440x900.png` | `ea159468e2f39396f0fdbe1167c6c6ac85eb20795ac95f2784c0e3731caab874` |
| `modeling-export-normal-1920x1080.png` | `fa5be024fc5e664827a6a94b6f42b7495af0b153fea8f81697a0470ef45efd05` |
| `modeling-export-source-blocked-1440x900.png` | `d36f108bcd930f8ccfa50db974175e272293b3669c188225e82dd4f665468ebe` |
| `modeling-export-approximation-blocked-1440x900.png` | `bf50a54ee9e3425f7f74568099f1e11265437961f98ce0708cfed003fd28d9e4` |
| `modeling-export-delivered-1440x900.png` | `9a6e05688192149a829b1fd3b60613a17cc2fa68d73bf6dbd7f1e960763cfe29` |

The active main agent reopened all 26 current approval, responsive state and family-adaptation images
at original resolution. Q-12–Q-16 pass where applicable: setup/result copy is coherent, state
emphasis is not duplicated, normal content has no fake scrollbar, long content has visible local
scrolling, the preview remains dominant, and metal/linear-viscoelastic/hyperelastic graphs use
professional compact typography, correct family axes and data-proportional clearance. Deterministic
recapture reproduced all six hashes. The MOD-EXPORT six-target/state/family/interaction validator,
the accepted MOD-FIT dependency validator, 18-family inventory, Ruff, JavaScript syntax,
manifest/staging/image hash and pending-lifecycle checks, Q-01–Q-16 completeness and
the current Web Interface Guidelines audit plus `git diff --check` all pass.

The six references remain `pending` with product-owner approval `absent`. This correction proceeds
directly to product-owner visual review. No later reference, production React/CSS, commit, push, PR
or merge starts before that response.

## 43. WAVE-04 MOD-EXPORT selected-model branch and exact-link correction

Date: 2026-07-29

The product owner asked how one experiment is managed when multiple fitting methods produce solver
cards, and whether platform data remains linked. The canonical answer is now recorded in the product
and UI specifications instead of being left in chat:

- one exact Test Data or Processing Output revision may branch into multiple independently saved
  model decisions, such as Swift, Voce and a Swift/Voce blend; sibling branches are immutable and do
  not overwrite one another;
- each saved branch promotes to its own Material Model IR revision;
- every Solver Card pins one exact Material Model IR revision, exporter target tuple and mapping
  digest, so multiple target-specific cards from the same experiment can coexist;
- the derivation chain remains explicit through immutable revision references:
  Test Data → Processing Output → selected decision/Material Model IR → Solver Card;
- current workspace pointers are conveniences only. No derived entity follows `latest`, and
  `Open in Fit` returns to the exact selected branch.

This did not justify another normal-surface lineage panel. The Export page already carries the
experiment, method and condition as page context. The setup pane now names only the selected model,
which is the branch the user is about to export. The ambiguous `Fit result / r1 · Tensile` row and
all visible `Fit r1` shorthand were removed. Exact revision identifiers and the full provenance
chain stay in Advanced, Evidence and history.

Current approval hashes, superseding the section 42 candidates:

| Approval image | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `60e59283aaece5de88cdf134a5c2fcc2c593cee945ff442573295f81bc969cda` |
| `modeling-export-normal-1440x900.png` | `bc6b87f1eb1a6b74a30615aaee7b892cf5c426d2eae061ccfbd3d2dd4e9763c6` |
| `modeling-export-normal-1920x1080.png` | `52dbfc0b47b5c8df2f7a743443a41db5c0c218f2313b675c8ad7b32fcdb24898` |
| `modeling-export-source-blocked-1440x900.png` | `0a5cfced5fc8a9f5098f9e7b9ef35f0e1e9023aa0cf4f623fcb0f4182c830483` |
| `modeling-export-approximation-blocked-1440x900.png` | `ebf7cedfd88554a8d8017cd2afc9b697e38a732b585966cc2a82759fadea0515` |
| `modeling-export-delivered-1440x900.png` | `eadcd9eb3eead872758ad9387916c3d2cd9ee4fac276aca6b2623e3f0a023db4` |

Family-adaptation hashes:

| Evidence image | SHA-256 |
| --- | --- |
| `modeling-export-linear-viscoelastic-1440x900.png` | `a8a8987dc4cc4e0bdd715a04ec5254745044dc8ef621def173c49991dc9c5b76` |
| `modeling-export-hyperelastic-1440x900.png` | `fa6bb422dc2e5edaa59ddafc6add0790c409bb360c4c2af425c47c205dfbfc60` |

The active main agent reopened all 26 recaptured approval, responsive-state and family-adaptation
images at original resolution. The selected model is consistent across setup, preview, bounded
source context and status; no normal surface exposes ambiguous `r1`; blocked state fabricates no
branch identity; and the earlier graph, information-economy, responsive, overflow and family
findings remain corrected. The six-target/state/family/interaction validator passes with zero
console errors, page errors or overflow. No additional writer or reviewer was invoked for this
product-owner-authorized direct main-agent correction.

The six references remain `pending`, main-agent evaluation is `accepted`, and product-owner approval
is `absent`. No later reference, production React/CSS, commit, push, PR or merge starts before the
product owner responds.

## 44. WAVE-04 MOD-EXPORT unit-system capability correction

Date: 2026-07-29

The product owner identified that a read-only `Output units` value made the unit system look like a
fixed property of the product rather than part of the exporter target tuple. The active main agent
accepted the discoverability finding but rejected a flow that knowingly accepts an unsupported unit
system and only then opens a warning or disables `Create solver card`.

The corrected policy and reference use one capability-backed `Output unit system` selector:

- the selector remains visible even when the selected reference exporter offers one supported value;
- only exporter-declared supported values are selectable;
- capability-declared unavailable alternatives may be shown disabled with their reason, so the
  selection concept remains discoverable without creating an invalid intermediate state;
- a valid unit-system change clears preview, acknowledgement and delivery pointers and requires a
  new Export check;
- without a Destination the unit selector is disabled and shows no inferred tuple.

No additional production unit system was invented. The current synthetic non-production exporter
still declares only `kg_m_s`; the normal closed selector shows `kg · m · s`, while its disabled
capability row states that other unit systems are unavailable.

Current approval hashes, superseding the section 43 candidates:

| Approval image | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `235b25e7bdd8668b341316c9c0b7e48c64c55f3098c1bb2208b6c23161cec770` |
| `modeling-export-normal-1440x900.png` | `38e6e300d7aa1258bf4523b0d768920df42653956a9e1659aabf9232bdd2d0b0` |
| `modeling-export-normal-1920x1080.png` | `363516b847e3298ed85ca7c7c06e1bef564fbaddca93ff17baba1cc8bd2d7a85` |
| `modeling-export-source-blocked-1440x900.png` | `2b406f84eb8180d994a87766da021b1e09c3e7b0869907d02bc9614bc5c6320f` |
| `modeling-export-approximation-blocked-1440x900.png` | `04a85b17f8eb6490aaf0edfe2cb3c898336329bfa33b40a66ee7c41c3215dbc9` |
| `modeling-export-delivered-1440x900.png` | `4979f4d070e17d0703052efcb2e0152d0858043467bc549e091b25204effc1cc` |

Family-adaptation hashes:

| Evidence image | SHA-256 |
| --- | --- |
| `modeling-export-linear-viscoelastic-1440x900.png` | `b76e0ed4dfbad72b27d26351f77205efa3d03ace9ed76d68edfe23395a04eecf` |
| `modeling-export-hyperelastic-1440x900.png` | `f13385ff93498ae0be83d35b6799640da85210a3624eb3dca2e095c3884d7bc4` |

The active main agent reopened all 26 approval, responsive-state and family-adaptation images at
original resolution. The added selector does not crowd the 1366×768 setup pane, clip labels, reduce
the dominant preview below its gate or change responsive topology. Source-blocked, review-required,
delivered, loading, error and long-content states remain coherent. The no-Destination state disables
the unit selector without leaking a target tuple. Metal, linear-viscoelastic and hyperelastic
adaptations retain the same family-correct mapping and graph contracts.

The full validator passes six approval targets, seven state bundles, two family adaptations,
capability discoverability, tuple invalidation, acknowledgement, immutable delivery, accessibility
and zero overflow/browser errors. No additional writer or reviewer was invoked for this
product-owner-authorized direct main-agent correction.

The six references remain `pending`, main-agent evaluation is `accepted`, and product-owner approval
is `absent`. No later reference, production React/CSS, commit, push, PR or merge starts before the
product owner responds.

## 45. WAVE-04 MOD-EXPORT product-owner approval

Date: 2026-07-29

The product owner explicitly approved the MOD-EXPORT result after the capability-backed
`Output unit system` correction. The approval applies independently to these six registered
references and their existing SHA-256 values:

| Approved reference | SHA-256 |
| --- | --- |
| `modeling-export-normal-1366x768.png` | `235b25e7bdd8668b341316c9c0b7e48c64c55f3098c1bb2208b6c23161cec770` |
| `modeling-export-normal-1440x900.png` | `38e6e300d7aa1258bf4523b0d768920df42653956a9e1659aabf9232bdd2d0b0` |
| `modeling-export-normal-1920x1080.png` | `363516b847e3298ed85ca7c7c06e1bef564fbaddca93ff17baba1cc8bd2d7a85` |
| `modeling-export-source-blocked-1440x900.png` | `2b406f84eb8180d994a87766da021b1e09c3e7b0869907d02bc9614bc5c6320f` |
| `modeling-export-approximation-blocked-1440x900.png` | `04a85b17f8eb6490aaf0edfe2cb3c898336329bfa33b40a66ee7c41c3215dbc9` |
| `modeling-export-delivered-1440x900.png` | `4979f4d070e17d0703052efcb2e0152d0858043467bc549e091b25204effc1cc` |

All six manifest entries are now `approved` with an individual product-owner lifecycle record.
The authoritative progress is 32/72 approved with 40 images remaining. This approval unlocks no
production React/CSS work; it only completes the MOD-EXPORT reference-family gate.

## 46. WAVE-05 ADM-SCHEMA-CORE main-agent acceptance

Date: 2026-07-29

The configured Luna Max implementer completed the independent ADM-SCHEMA-CORE bundle under the
main-agent-authored packet. The active `/root` main agent reran its eleven-target, eighteen-state,
three-viewport, interaction and accessibility validator, the finite inventory validator and
`git diff --check`, then opened all eleven approval images at original resolution.

The main-agent qualitative gate accepts the current candidates:

- Database, Table edit and Attribute edit use one continuous three-pane desktop workspace:
  `Schema objects | Object list | Property editor`;
- the former redundant persistent setup/sidebar is absent, so the workspace never becomes four
  columns;
- 12–13 px schema and metadata text, dense rows, flat dividers and restrained state color keep the
  Administration workspace consistent with the approved Materials explorer without copying its
  domain-specific tree;
- Table and Attribute forms distinguish stable identity from editable definition and make
  `Save new revision` the governed consequence; hashes and ETags remain in Advanced/Evidence;
- the stale-conflict state preserves the local draft and gives reload, keep-as-new-revision and
  cancel as explicit recovery paths;
- the long-invalid Attribute keeps the application shell and selection fixed while the editor uses
  local scrolling, adjacent error text and a truthfully disabled Save action;
- all three normal viewports preserve the same topology without page overflow, overlap, clipped
  controls, nested cards or a permanent fourth inspector.

Current approval candidates:

| Pending reference | SHA-256 |
| --- | --- |
| `administration-database-normal-1366x768.png` | `e0c2951b04d473c3d6b7e133c815446a22810037e7cfe1ae0b6664d9e0af07d6` |
| `administration-database-normal-1440x900.png` | `901f13632255d95added7455eb539ff78c9e8cefaa115f9aaa23b043af088ea9` |
| `administration-database-normal-1920x1080.png` | `b54ac84e90ea3dac980e8f7c0bc71fd10687d4777cffa11106ad519fac99e1f6` |
| `administration-table-edit-draft-1366x768.png` | `e95e21879f7877d4054a263005df835da8fb86a2d487e8375ccc463e751c758e` |
| `administration-table-edit-draft-1440x900.png` | `91edbc0bc8913832ee5f48f495e38d570a725407baaf76fa5bcb278b7d17c34f` |
| `administration-table-edit-draft-1920x1080.png` | `c8102c5e056a9848e7788aae183864fa65e774fad830eb96da62aad9a3cc46c3` |
| `administration-attribute-edit-draft-1366x768.png` | `e037e9b409bd3a16bafa4e4287454c2a3a2372a06b6d92c47fd8b5fd80ab47b7` |
| `administration-attribute-edit-draft-1440x900.png` | `e0f2ee98460f5ef5d5669aa37f26391763e3fc09085a314d85b2448dc3f02d11` |
| `administration-attribute-edit-draft-1920x1080.png` | `228757c2613d8dc552ec10db510780bb0ed0bae45a400c2122d0e0035117de32` |
| `administration-edit-stale-conflict-1440x900.png` | `7a6befe06cf47a5eacbbe552658258d88e87336c57957832908a45b9a58b9d9e` |
| `administration-attribute-long-invalid-1440x900.png` | `eaf1e78c4be5e5c488f81f494144ff4d8464cd962768a969bc58a18d3a9ce766` |

The candidates remain `pending` with product-owner approval `absent`. A bounded reviewer packet and
one fresh read-only Terra High review are still required before product-owner handoff.

## 47. WAVE-05 ADM-SCHEMA-CORE main-agent correction gate

Date: 2026-07-29

The main agent continued the required original-resolution review across all 54 evidence-only
captures and rejected two issues that had passed the first deterministic run:

- conditional discrete, Record-reference and text states leaked Density draft values into the
  selected Attribute editor;
- the long-invalid Attribute name crossed its Name cell and collided with Definition text.

The sole configured Terra High correction writer received the persisted correction packet at
`docs/17-evidence/reports/issue-167-correction-packet-wave-05-adm-typed-state-semantics.md`.
The correction initializes every visible draft from the selected Attribute and deterministically
binds the selected row, editor title, name, reference key, value type, typed fields and guidance.
Long names now ellipsize inside the Name cell, with measured non-overlap through Definition and Rev.

The main agent opened the nine corrected typed-state images, all three corrected long-invalid
responsive images and all three identical long-scroll evidence images at original resolution.
The Database, Table and ordinary Attribute approval targets remain byte-for-byte unchanged. The
required containment correction changes only the long-invalid approval candidate:

| Corrected pending reference | SHA-256 |
| --- | --- |
| `administration-attribute-long-invalid-1440x900.png` | `eaf1e78c4be5e5c488f81f494144ff4d8464cd962768a969bc58a18d3a9ce766` |

The full ADM validator, inventory validator, focused user-guide tests, Ruff, JavaScript syntax,
structured image registration and `git diff --check` must pass again before the fresh reviewer is
started. Product-owner approval remains absent.

## 48. WAVE-05 ADM-SCHEMA-CORE independent review and final internal gate

Date: 2026-07-29

A new read-only configured Terra High reviewer independently opened all eleven approval images and
all 54 evidence-only images at original resolution. After the reviewer packet's environment command
was corrected from `uv run python` to the repository's Playwright-enabled `python`, the ADM
validator, finite inventory, Ruff, JavaScript syntax and `git diff --check` all passed.

The reviewer returned `approve`, V-01 through V-16 at 2/2 each for 32/32, with no hard-gate failure,
actionable finding or residual concern. Applicable qualitative checklist results passed for local
list overflow and long-content scroll/containment; Materials/Modeling/Export-only checks were
recorded not applicable. The reviewer explicitly confirmed:

- all typed Attribute states keep selection, title, name, reference, value type, typed fields and
  guidance semantically aligned;
- the long Attribute name ellipsizes inside Name without crossing Definition or Rev;
- all three viewports retain one flat three-pane workspace with no fourth inspector, nested-card
  composition, page overflow or clipped control;
- stale-conflict recovery preserves the local draft and exposes the three intended choices.

After the reviewer disposition, the main `/root` agent reopened all eleven approval images at
original resolution and repeated the product/UX gate. It accepts the complete ADM-SCHEMA-CORE
bundle for product-owner review. All eleven manifest entries remain individually `pending` with
product-owner approval `absent`; no dependent Administration bundle is authorized until approval.
