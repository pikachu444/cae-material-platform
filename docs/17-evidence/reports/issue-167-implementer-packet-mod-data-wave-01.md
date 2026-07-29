# Issue #167 implementer packet — WAVE-01 / MOD-DATA

Date: 2026-07-29
Writer role: configured `implementer_luna_max`, exactly one writer for this family
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Create the complete five-image `MOD-DATA` approval family:

1. `modeling-data-normal-1366x768`
2. `modeling-data-normal-1440x900`
3. `modeling-data-normal-1920x1080`
4. `modeling-data-empty-new-session-1440x900`
5. `modeling-data-long-invalid-mapping-blocked-1440x900`

This is static reference work only. Do not change production React/CSS, the common reference
manifest, the finite inventory, the common evidence report, user guides, current screenshots, git
state, commits, branches, remotes or GitHub.

## Product task and visual judgment

A materials engineer enters Modeling at Data and must establish a trustworthy Test Data input
before Process, Fit or Export. The workspace must keep a compact curve/source navigator, a
shallow current-stage control ribbon and a dominant persistent graph. It must support:

- choosing an exact saved Test Data revision;
- inspecting a local CSV/TSV/XLSX source before saving;
- explicitly mapping independent/dependent channels, quantity meaning and raw/normalized units;
- seeing a graph preview without confusing it with saved output;
- starting with no data and one clear first action;
- blocking invalid mapping adjacent to the decision while preserving source evidence and graph
  context.

There is no permanent third inspector. Settings remain graph-adjacent in a shallow ribbon or
Advanced disclosure. The graph remains visible while settings change. This is engineering
software: dense, legible controls and result continuity matter more than cards or decoration.

## Frozen authorities inspected by the main agent

- `AGENTS.md`
- `docs/01-product/service-reference-inventory.yaml` (`MOD-DATA`)
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/00-research/ux-layout-review/modeling.html`
- `docs/00-research/ux-layout-review/review.css`
- `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`
- current live evidence:
  - `docs/user-guide/images/current/modeling-data-1366x768.png`
  - `docs/user-guide/images/current/modeling-data-1440x900.png`
  - `docs/user-guide/images/current/modeling-data-1920x1080.png`
- current contract sources:
  `apps/web/src/common-processing-workbench.tsx`,
  `apps/web/src/modeling-data-intake.tsx`,
  `apps/web/src/design/modeling-workspace-layout.tsx`,
  `apps/web/src/engineering-curve-plot.tsx`,
  `apps/web/src/api.ts`, `apps/web/src/types.ts`,
  and current Modeling tests.

The approved lower `modeling.html`/`review.css` topology supplies the visual grammar: compact
184–208 px rail, shallow task controls and dominant graph. Current Data live captures and React/API
sources supply real state and task contracts, but are not permission to preserve accidental
current styling.

## Family ownership

The writer may create or edit only:

- `docs/00-research/ux-service-reference/modeling-data*.html`
- `docs/00-research/ux-service-reference/modeling-data*.css`
- `docs/00-research/ux-service-reference/modeling-data*.js`
- a MOD-DATA-only capture helper under
  `docs/00-research/ux-service-reference/`
- a MOD-DATA-only validator under
  `docs/00-research/ux-service-reference/`
- the five target PNGs and their target-specific measurement/evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit:

- `reference.css`, `reference.js`, any `materials-*` source, or existing approved PNG;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- any file under `apps/`;
- any other writer's `materials-datasheet*` files.

Other agents may work in the repository. Preserve their edits and never reset, clean, stash,
discard or overwrite unrelated files.

## Required target definitions

### Normal at all three viewports

- Reuse one semantic HTML structure plus bounded viewport overrides.
- Application shell: Materials | Modeling | Activity, Modeling active.
- Compact context header and Data | Process | Fit | Export stage strip, Data active. Later stages
  remain visible but are not implied complete.
- Navigator width defaults: 184 px at 1366, 192 px at 1440, 208 px at 1920, with a 5 px interactive
  divider and collapsible, truthful ARIA behavior. The graph gets all remaining dominant width.
- Source ribbon: `Library | Local file | Test Data JSON`, with Library active in normal. Show the
  exact synthetic `CMP-DEMO-DP780-TEST-JSON-03 · r1` selection and three saved datasets.
- Rail: Tensile tests, three specimen revisions, two included, selection and graph visibility
  controls. Long technical IDs are not primary labels.
- Plot: `Source preview`, selected exact revision, mapped input and preview distinction, engineering
  strain/stress axes and restrained controls. Provide data-relative range headroom so the curve
  never presses against extrema.
- A preview is explicitly `not saved`. There is no Save-dataset command in the Library normal state.
- `Advanced source settings` is a disclosure, not a permanent third column.

### Empty new session 1440×900

- Keep the same shell, stage strip, compact rail/ribbon/graph topology.
- No Test Data, Mapping Profile, Recipe, selected model or downstream current pointer is inherited.
- Rail truthfully says no curves. Library says no saved datasets.
- Graph remains in place with a concise preparation explanation.
- The single primary next task is `Local file`; activating it switches the ribbon to source/file
  intake. Do not show a fake saved revision, completed preview or downstream readiness.

### Long invalid mapping blocked 1440×900

- Keep the same shell, rail, source ribbon and persistent graph. Local file is active.
- Show a synthetic raw source inspector with long column labels and a short sample table.
- Show an explicit two-row mapping decision table: axis, source column, quantity semantics, raw
  unit, normalized unit and status.
- Use a real invalid state supported by the current contract: both axes select the same source
  column and/or a unit does not match the intended quantity. State the adjacent reason without
  guessing or silently converting.
- Include a human-readable mapping change-reason field.
- `Update preview`/`Save dataset` is visibly blocked while invalid. The graph may retain the last
  valid preview only if it is clearly labeled stale/not updated; otherwise show a preserved graph
  placeholder. Never imply the invalid source is saved.
- Long file, sheet, channel and record labels must wrap/truncate deliberately with full native
  titles and no overlap or horizontal page overflow.
- Raw bytes, original unit text and normalized semantics remain visibly distinct; full raw asset
  UUID/checksum belongs in an Advanced/Evidence disclosure, not the normal task line.

## Static-region → production contract mapping

This reference freezes future structure; it does not implement the React port.

| Static region | Current React/component/data contract to preserve later |
| --- | --- |
| Application/status shell | `ApplicationShell` plus `publishWorkspaceStatus`; selection, exact revision, jobs, warnings, connection |
| Context/stage strip | `CommonProcessingWorkbench` + `ModelingStageShell`; route-backed Data/Process/Fit/Export and downstream invalidation |
| Curve/source rail | `ModelingWorkspaceLayout` navigator; exact `CanonicalTestDataDocumentResponse` revisions, include/visibility and selected document |
| Resize divider | `ModelingWorkspaceLayout`; viewport defaults 184/192/208, 180–240 safety range, collapse/expand and actual-width ARIA |
| Source ribbon | `ModelingDataIntake`; Library/Local/Test Data JSON source state |
| Library selection | `selectedDocumentId`, `loadDocument`, `trackDocuments`; exact Test Data revision only |
| Upload/inspect | `uploadGovernedTabularFile` → `previewGovernedTabularImport`; verified raw asset/artifact and source format/sheet/header evidence |
| Mapping table | `GovernedChannelMapping`/`GovernedImportProfileContent`; independent/dependent axis, source quantity, original unit, normalized unit |
| Mapping block | current `firstColumn === secondColumn`, required change reason and complete Test Run/name/maker/operator/lab checks |
| Graph preview | `previewCommonProcessing`/`EngineeringCurvePlot`; preview arrays are non-authoritative and do not mutate saved Test Data |
| Save | `executeGovernedTabularImport` plus import/revise canonical Test Data; exact Material/State/Test Run/profile revisions and classification continuity |
| Advanced source settings | current disclosure; Mapping Profile JSON, IDs and checksums remain Advanced/Evidence |

Use only the existing synthetic DP780 non-production fixture. Do not choose or imply a production
tensile standard, material family, constitutive model, optimizer policy, solver card, virtual
specimen or validation threshold.

## Deterministic acceptance

Provide a target-aware capture and validator which fail unless:

- each PNG is exactly its named viewport at device scale factor 1;
- there are no console errors, page errors or document/body horizontal overflow;
- normal geometry uses one compact rail, one divider, one main surface, one shallow ribbon and one
  dominant graph; there is no permanent third inspector or nested-card hard-gate failure;
- navigator actual and ARIA widths match at default, keyboard adjustment, Home/End and collapsed/
  restored states, without reducing the main graph below its safe minimum;
- all normal task labels, all three sources, four stages, three curves/two included, exact revision,
  unsaved preview status, axes and legends are present and contained;
- normal Library selection changes selected curve/record context; source tabs change their visible
  task controls; disclosure open/close and graph controls have measurable semantic consequences;
- Empty contains no saved dataset or downstream pointer and has exactly one primary Local-file
  consequence;
- invalid mapping contains raw inspector and both mapping rows, announces the adjacent conflict,
  keeps preview/save disabled, preserves original-versus-normalized units and never claims save;
- long content is contained in its region with no clipped decision text;
- canonical Empty/Invalid targets also generate responsive evidence at 1366×768, 1440×900 and
  1920×1080 proving the topology does not change. Only the canonical 1440 PNG is an approval image;
- detecting/saving loading and parse/import/save error states are exercised at all three viewports
  as deterministic same-topology evidence, preserving source/mapping/graph context.

Run at minimum:

```text
python <MOD-DATA capture helper> --all-packet-targets
python <MOD-DATA validator> --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check <changed Python helpers>
node --check <changed JavaScript files>
git diff --check
```

Because the main agent owns manifest integration, the family validator may validate a writer-owned
staging index/measurements before the manifest entries exist. It must be able to switch to the
common manifest after integration without weakening assertions.

## Handoff

Return:

- exact files changed;
- commands and pass/fail results;
- each PNG path, viewport and SHA-256;
- exact measurement/evidence paths;
- any residual limitation.

Do not modify shared integration files to make a gate pass. Do not commit or start another family.
