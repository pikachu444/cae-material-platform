# #167 Main-agent direct correction packet — Materials and Administration

Date: 2026-07-30
Status: authorized, bounded correction in progress
Writer: active main agent

## Authorization and boundary

The product owner explicitly authorized one additional correction after the rejections recorded in
sections 58–59 of
`docs/17-evidence/reports/issue-167-service-reference-freeze.md`. The active main agent performs this
correction directly. This authorization does not permit production React/CSS work, another screen
family, a commit, push, PR or merge.

The correction is limited to:

- MAT-EXP normal Record-selection synchronization and the stale exceptional-bundle hash gate;
- MAT-DETAIL normal engineering-plot geometry and complete axis semantics;
- ADM-SCHEMA-CORE Table saving/save-error first-view integrity at 1920×1080.

Approved exceptional-state pixels and the accepted 1366×768/1440×900 Administration candidates are
frozen. Existing uncommitted work remains intact.

## Authority inspected by the main agent

- GitHub issue #167 and the current service-reference handoff;
- `AGENTS.md`, `.codex/config.toml` and `.codex/agents/*.toml`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`, including Q-01–Q-20;
- current manifest, inventory and evidence report sections 57–59;
- the exact static HTML/CSS/JavaScript, capture and validation sources named below;
- current production Materials selection contracts and current user-guide captures.

The required visual skills are applied in this order:
`desktop-engineering-ui`, `frontend-ui-engineering`, `web-design-guidelines`, then
`webapp-testing`.

## Exact defects and required outcomes

### MAT-EXP

Sources:

- `docs/00-research/ux-service-reference/materials-search-normal.html`
- `docs/00-research/ux-service-reference/reference.js`
- `docs/00-research/ux-service-reference/capture_reference.py`
- `docs/00-research/ux-service-reference/validate_reference.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`

Required outcome:

1. Selecting a `Record` tree row by pointer or Enter selects the matching result row and updates the
   adjacent selected-material identity, grade, description, family, status and status-bar context.
2. Selecting a non-Record tree node never fabricates or changes material context.
3. Result-row selection and Open Datasheet behavior remain intact.
4. The MAT-EXP exceptional validator freezes only the already-approved long/empty canonical and
   responsive images. Replaced normal images are not treated as frozen exceptional evidence.
5. The default normal pixels may remain byte-identical; interaction evidence must prove the new
   consequence at 1366×768, 1440×900 and 1920×1080.

### MAT-DETAIL

Sources:

- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`
- `docs/00-research/ux-service-reference/materials-datasheet.css`
- `docs/00-research/ux-service-reference/materials-datasheet.js`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1920x1080.js`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`

Required outcome:

1. Every normal viewport derives SVG viewBox, axes, ticks, response path and hit geometry from the
   same rendered width and height; CSS cannot stretch the graph independently by axis.
2. Both titles are present and centered consistently: `Engineering strain` and
   `Engineering stress (MPa)`. Tick values do not repeat units.
3. The displayed synthetic series remains strain `0–0.20` and stress `0–850 MPa`; the data-relative
   10% headroom policy still resolves to nice displayed maxima `0.25` and `1,000 MPa`.
4. The compact viewports use otherwise empty vertical workspace to improve graph legibility without
   clipping the legend, status bar or datasheet actions.
5. Approved Related/empty canonical and responsive pixels remain byte-identical.

### ADM-SCHEMA-CORE

Sources:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`

Required outcome:

1. At 1920×1080, `table-saving` and `table-save-error` show the complete draft form and complete
   `Save new revision` / `Discard draft` row in the initial editor viewport.
2. During these transient/recovery states the draft status or exact recovery action is dominant.
   The saved response graph is suppressed rather than leaving a clipped form above a graph.
3. The synchronized saved Record/Layout preview remains available and truthful; no stale projection
   is fabricated.
4. The normal, Table-draft and Attribute-draft graph/preview contracts remain unchanged.
5. All 1366×768 and 1440×900 Administration approval-image hashes remain exact.

## Forbidden shortcuts

- no assertion relaxation that permits distorted plots, missing units or partially visible controls;
- no hard-coded replacement domain maxima independent of the declared series and headroom policy;
- no page-level scroll, fake scrollbar, clipped button or heading-only graph;
- no production `apps/web/**/*.tsx` or `apps/web/**/*.css` edits;
- no change to approved exceptional-state images;
- no commit, push, PR or merge before product-owner approval.

## Required gates

1. Run each capture script with `--help` before capture.
2. Recapture only the bounded normal/affected state evidence from executable static sources.
3. Prove MAT-EXP pointer and keyboard Record-selection synchronization at all three normal viewports.
4. Prove MAT-DETAIL aspect-ratio parity, complete unit-labelled axes, collision freedom, data-relative
   headroom and first-viewport containment at all three normal and both wide evidence viewports.
5. Prove Table saving/save-error action containment, hidden transient graph, truthful companion
   preview and unchanged lower Administration hashes.
6. Run JavaScript syntax, Python compilation, Ruff, inventory, documentation-impact and diff checks.
7. The main agent opens every affected image at original resolution and records Q-01–Q-20.
8. Prepare three bounded reviewer packets and request fresh, read-only configured Terra High review.
9. After reviewer disposition, the main agent repeats the original-resolution product/UX judgment.
