# RD-02 correction packet C1

Status: Main-diagnosed first connected checkpoint failures, 2026-09-07. Execute only after the
initial implementation writer stops. This completes the existing approved v4 scope; no publication,
processing execution, new engineering calculation, or broad backend migration is authorized.

Authority: [approved v4 packet](rd02-connected-reader-packet.md), current root/apps/web-next AGENTS,
UI principles, architecture, and **design/frontend-reader-proposals/material-workspace/index.html,
workspace.css, workspace.js**. Open the actual accepted HTML source and Main's reference PNG before
editing. Do not reinterpret this as permission to design another generic split-table dashboard.

Main evidence: `.artifacts/rd02/checkpoint/{browser,behavior,card-pin-mismatch}.json` and the original
1920 PNGs. Before images and accepted reference PNG are under `.artifacts/rd02/`. Those are failed
checkpoint evidence, not current-guide images or an owner-approved UI. Initial API revisions and
download bytes are independently verified under `.artifacts/rd02/live/`.

## First intermediate checkpoint M1 (owner steering; full scope unchanged)

Do not wait for every reader/contract/test to finish before Main acceptance. Stabilize one primary
Test Data journey first: exact source/pin → actual x/y and units → optional right preview containing
curve and conditions → expanded detail hiding the list → return preserving query/page/selection/
scroll/focus → actual JSON download. Tell Main when this route and its shared layout/curve files are
safe to inspect, and hold those files briefly while Main checks the actual1920 screen and interaction.
Main then returns findings while other independent C1 work continues. This is an intermediate result,
not permission to omit Materials/Processing/Models/Cards, contracts, final tests or5viewport evidence.

Main opened the accepted HTML and captured both reference states at1920:
`.artifacts/rd02/reference-test-data-preview-1920.png` and
`.artifacts/rd02/reference-test-data-expanded-1920.png`. Preview keeps results dominant with a usable
curve/conditions pane and close/expand controls. Expanded uses bounded conditions/file information
beside a dominant actual curve, replacing the list. These are synthetic visual references only.
Do not port their synthetic calculations, first-test inference or future processing buttons.

The correction role remains the same. Its current turn was interrupted and resumed solely to apply
this intermediate-first order; all written files and the full C1 acceptance remain preserved.

M1 Main read-back: `.artifacts/rd02/m1/` diagnosed retained empty preview width, Enter's native click
overriding expansion, visible Open details bypassing focus capture, and whole-workspace scrolling.
The same writer corrected these. `.artifacts/rd02/m1b/behavior.json` and `close.json` pass Enter,
double-click, visible-action return focus, URL preservation, optional-preview removal with full result
width, nonuniform actual x coordinates, and the original 1,959-byte JSON. Main opened
`m1b/geometry-screen.png` at original resolution and confirmed the visible curve/conditions and
bounded workspace geometry. Early paint-incomplete captures are not final visual evidence.
Actual result-region scroll restoration, tree/filter/sort, normal engineering copy and all other C1
outcomes still require completion. This intermediate result does not approve the complete UI.

## Concrete diagnosis and required correction

1. **The approved workspace and detail state are missing.** All readers currently render a table and
   an always-reserved right column. Materials has no card/table switch, left expandable material/state/
   specimen navigation or separate filters. Empty preview consumes a large region. Double-click simply
   calls single-select; Main observed unchanged URL and still-visible Documents list. No close, expand,
   return or focus restoration exists. Build the accepted material-centered layout: compact task rail,
   actual left tree/filter area, dominant results with Materials property cards/table, optional preview,
   and expanded detail replacing the results region. Single click previews; double-click, Enter and a
   visible detail action expand. Return restores q/type/material/sort/page/selection/list scroll/focus.
   Use actual stored state/specimen links; a label without identity is not an invented specimen node.
   Material tree/list uses explicit server paging and response count/facets. No first-page-as-all tree.
   Filtering/sorting/page changes close an off-page preview; Main's no-match query currently leaves it.

2. **Exact card URLs silently read current.** Main supplied primary card ID with another card's pin.
   Browser requested the primary card's current index pin and enabled download instead of rejecting it.
   `ConnectedCardsReader` passes the current `selected` row into `readCard`; the URL pin only affects the
   query key. Rebuild detail routing around required typed stable ID + exact pin + explicit family,
   independent of current list/page contents. Self/download paths must use the requested pin. Verify
   returned aggregate ID AND revision ID and artifact identity/hash; absent/mismatched fields fail
   closed. Never override a current row's label/pin to make a historical response look current.
   The same rule applies to Test Data/Processing/Models: current lists cannot be a prerequisite for
   an exact detail route, and filtering or a denied optional list cannot erase authorized detail.
   Existing model APIs may return current snapshots: compare the requested pin and fail closed if that
   exact snapshot is not available; never substitute. Do not add new model writes/revision migrations.

3. **The primary stored relationship chain cannot be traversed.** `/models` enumerates only
   `/material-states/{id}/material-models` (one reference-elastic model), excluding the primary
   tabulated model and linear/Ogden families. A generic text search is not an exact generation relation.
   Use typed family adapters for existing model endpoints and explicit stored input fields. A Model
   route may be contextual to an exact state/family; do not label an incomplete material traversal as
   a complete project model list. App composes feature public exports; no deep feature-internal imports.
   Test detail shows saved Processing Outputs where source_document ID AND pin match; Processing detail
   shows its input and derived model(s); model shows cards matching model ID AND pin; card reverses to
   the stored exact model/input. Neutral routes use exact neutral/document source references. Show
   same-material membership separately, with a truthful partial-error/retry region when optional
   related reads fail. Do not infer generation from material membership or string matching in q.

   Actual primary: source41d6520e-5385-468f-b178-9356b870bfa8/pin847bf1b2-302e-40b0-8e9c-1580630d98f4;
   output1f9e7596-7f7b-4aab-9eb5-32e3b26206f6/pin26087e6f-d1af-42c7-a5b2-6cafe973b190;
   modela711f7dc-2cc8-43ec-bc75-d7770a2bdceb/pine939c398-e1b3-4f9c-983a-a9674d7024f0;
   card32e16173-aaa1-4a29-a079-3c2eb03a4276/pind5343207-3ff3-48db-847b-47c7ce321c1d.
   All13 primary cards and two same-material different Test Data IDs are recorded in
   `live/primary-reader-chain.json` and `baseline-download-evidence.json`. Existing model
   711f2632-018a-4ea4-b0fb-6d9b7c6c2f07 has a different generation input: do not include its cards as
   derived from the selected test. The seed also has a legitimate second output for the primary test;
   show all stored exact matching outputs, not just Main's new fixture.

   Actual read-back is `.artifacts/rd02/live/expected-primary-relations.json`: the primary source has
   two exact saved outputs. The new direct output points to its tabulated model and 13 cards.
   The seed output also appears in neutral document `c8e26809-218d-4919-8de0-7db5cf75359d` under
   `document.candidate_selection.processing_output`; that neutral revision has two exact cards.
   Its `material_model_ir.model` identifies the neutral model itself, so do not invent a link from
   the separate seed tabulated model to the neutral model. Follow the explicit source/output/neutral
   references and keep unrelated same-material cards outside the generation chain.

4. **The scientific curve is materially misleading.** `CurvePlot` receives only y values, spaces them
   by array index, drops nulls and joins across gaps, has no real x/y axes, and uses non-uniform SVG
   stretching. Test Data labels this as strain→stress despite nonuniform strain spacing. Processing
   passes its first (independent strain) series as y. Replace with a bounded shared domain curve
   component that accepts validated x/y channel pairs, physical quantities/units and actual finite
   x coordinates. Preserve null gaps, channel alignment and reported preview sampling. Use actual
   element dimensions for geometry and readable axes/ticks/legend; no preserveAspectRatio=none,
   resampling, hidden conversion, fit or engineering defaults. Choose channels by the backend's
   declared curve definition, not first-item fallback. Support a visible explicit dependent-channel
   choice where several valid measured responses exist. A malformed/unsupported pair shows its state.

5. **Normal UI is dominated by compatibility plumbing.** Current headings say EXACT REVISION, rows
   show UUID/revision/native SHA and non-status badges; material filters show truncated UUIDs; card
   detail starts with raw mapping JSON; Processing exposes Mapping Profile/options JSON before results.
   Follow accepted reference and product language: names/codes, meaningful type, conditions, units,
   applicability and actual output state on normal surfaces. Put UUIDs, pins, hashes and raw payload
   in a compact Evidence/Advanced disclosure. Card native text and readable mapping status remain
   available; do not use raw JSON as the engineering detail. Label Test Data JSON, Processing Output
   JSON and native card downloads distinctly. Display source/current comparison as an older-input
   indicator without silently regenerating saved outputs. Technical identifiers must still be
   recoverable exactly in Evidence; moving them does not delete identity information.

6. **Contracts and recovery are not verified by the old tests.** Initial 18 tests cover the inherited
   prototype only. Add meaningful connected regressions for exact identity/pin mismatch, malformed
   channel metadata, nonuniform x/null gaps, actual generation versus same-material counterexample,
   complete local12-row paging/filter/sort/counts, off-page close, expand/return/scroll/focus, delayed
   response after selection/close, source-current change, and independently denied optional readers.
   Server-object query keys include authenticated tenant/project scope. Explicit Connect local demo
   is permitted; normal requests never mint identity. Keep403 local and preserve valid credentials.
   Download failures must be locally visible/retryable, not unhandled async exceptions. Backend
   exact/card-index regression tests must execute query construction and permissions (DATASET-only,
   EXPORT-only, both, neither), not compileall alone. All reads retain tenant/project/RLS boundaries.
   Main also verified that contracts/http/openapi.yaml still lacks the new project card list and exact
   Test Data detail, and has not recorded the optional revision parameters. Synchronize the bounded
   read contracts and run their applicable contract gates. Preserve openapi.baseline.yaml and existing
   DMA contracts; no unreviewed golden replacement.

## Ownership, sequence and stopping rule

Canonical correction writer owns apps/web-next runtime/tests/README and the already bounded
datasets/processing/exporting read contracts/tests and registration. Do not modify unrelated engines,
DMA calculations, original redesign checkout, personal settings, Main evidence/scripts or planning
records. Preserve all staged snapshot and unstaged changes. You are not alone in the checkout; Main
owns docs/evidence and live environment. No second writer runs concurrently.

Implement the existing primary journey completely before calling this pass complete. Group reader
state/layout primitives only where actually shared; domain adapters, relations and display components
remain feature-owned. Keep app→features→shared direction, module-scoped feature CSS and shared tokens.
Do not add a generic framework or retain duplicate zero-consumer connected code. Prototype code can
remain behind its separate build, but the live build must not import fixture data or prototype gateway.

First fix scientific and exact identity contracts; next finish primary chain and reader states; then
port accepted composition and normal engineering content; finally add affected regressions and run
typecheck, live build, prototype guards and backend tests. Re-read every numbered C1 outcome before
handoff. Report exact tests and remaining failures candidly. Passing typecheck alone is not completion.

Main owns server rebuild/preflight, real browser downloads and exact byte comparison, source-head
advance after normal evidence, five viewport originals/crops, min/max negative states, guide/manifest,
and independent reviewer. Owner visual and physical Windows readability remain separate dispositions.
The intermediate five-viewport full capture was deferred because missing expanded/optional-preview
states invalidate that acceptance set; do not fabricate evidence of states that do not exist yet.
