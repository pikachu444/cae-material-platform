# Issue #167 implementer packet — WAVE-02 / MOD-PROCESS

Date: 2026-07-29  
Writer role: configured `implementer_luna_max`, exactly one writer for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Create the complete four-image `MOD-PROCESS` approval family:

1. `modeling-process-normal-1366x768`
2. `modeling-process-normal-1440x900`
3. `modeling-process-normal-1920x1080`
4. `modeling-process-prerequisite-blocked-1440x900`

This is static reference work only. Do not change production React/CSS, the common reference
manifest, the finite inventory, the common evidence report, user guides, current screenshots, git
state, commits, branches, remotes or GitHub.

`MOD-DATA` is the approved prerequisite. Preserve its frozen shell, compact curve rail, stage strip,
persistent graph and status-bar topology. This family defines the next dependent stage only.

## Product task and main-agent visual judgment

A materials engineer has selected the exact saved synthetic DP780 Test Data revision and needs to:

- control processing membership independently from graph visibility;
- inspect an ordered, deterministic processing sequence;
- focus one operation and understand its source/options/effect beside the persistent graph;
- preview before/after curves without mutating the exact source;
- save one immutable Processing Output only after the preview is current;
- recover from missing prerequisites without losing the Modeling session.

Use the existing synthetic metal tensile reference workflow only. The normal target focuses
`Elastic modulus` with the existing robust calculated method and an explicit strain range. It may
show the observed input, current processed preview and calculated elastic-fit overlay. It must not
introduce manual yield, hidden smoothing/resampling, deleted outliers or a production tensile
standard.

This is professional engineering software. The dominant graph and decision continuity matter more
than decorative cards. Keep one 184–208 px combined rail, one shallow graph-adjacent settings band
and one persistent graph. There is no permanent third inspector.

## Frozen authorities inspected by the main agent

- `AGENTS.md`
- `docs/01-product/service-reference-inventory.yaml` (`MOD-PROCESS`)
- `docs/01-product/desktop-engineering-ui-product-spec.md` section 7.4
- `docs/01-product/desktop-engineering-ui-spec.md` (`P-01`–`P-08`)
- `docs/01-product/desktop-engineering-user-flows.md` Stage 2 Process
- `docs/01-product/visual-acceptance-matrix.md` Modeling Data / Process / Fit checks
- approved prerequisite sources:
  - `docs/00-research/ux-service-reference/modeling-data-normal.html`
  - `docs/00-research/ux-service-reference/reference.css`
  - `docs/00-research/ux-layout-review/modeling.html`
  - `docs/00-research/ux-layout-review/review.css`
- approved prerequisite images:
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
- current live evidence:
  - `docs/user-guide/images/current/modeling-process-1366x768.png`
  - `docs/user-guide/images/current/modeling-process-1440x900.png`
  - `docs/user-guide/images/current/modeling-process-1920x1080.png`
- current contract sources:
  `apps/web/src/common-processing-workbench.tsx`,
  `apps/web/src/design/modeling-workspace-layout.tsx`,
  `apps/web/src/engineering-curve-plot.tsx`,
  `apps/web/src/api.ts`, `apps/web/src/types.ts`, and current processing/session tests.

The approved MOD-DATA and lower `modeling.html` topology are the visual authority. Current live
Process captures and React/API sources supply the real ordered steps, preview, invalidation and
immutable-commit contracts, but are not permission to retain card styling, oversized control
stacks or accidental graph ranges.

## Family ownership

The writer may create or edit only:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- MOD-PROCESS-only staging JSON/evidence under
  `docs/00-research/ux-service-reference/`
- the four target PNGs and target-specific measurement/evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

The writer may reference approved shared HTML/CSS/JS read-only. Do not edit:

- `reference.css`, `reference.js`, `modeling-data-normal.html`, any approved prerequisite source,
  or any existing approved PNG;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- any file under `apps/`;
- any `materials-card*` file or other writer-owned file.

Other agents may work in the repository. Preserve their edits and never reset, clean, stash,
discard or overwrite unrelated files.

## Required target definitions

### Normal at all three viewports

- Reuse one semantic HTML structure plus bounded viewport overrides.
- Preserve the approved Modeling application shell and compact context header. `Process` is active
  in `Data | Process | Fit | Export`; status says the exact Test Data source is saved while the
  processing preview is not saved.
- Rail defaults remain 184 px at 1366, 192 px at 1440 and 208 px at 1920, with the approved divider
  behavior. It contains:
  - `Curves · 3 curves · 2 included`;
  - filter;
  - canonical `Tensile tests` parent;
  - `Specimen 01/02/03 · r1` rows;
  - separate inclusion checkboxes and icon-only plot visibility controls;
  - ordered `Processing operations` below the curve group.
- Use the existing ordered synthetic metal steps, in plain user language:
  resolve duplicate x, elastic modulus, proof stress, necking boundary, engineering-to-true/plastic.
  Do not place the hardening-fit step in Process; it belongs to Fit.
- Focus `Elastic modulus`. The shallow settings band shows `Step 2 · Elastic modulus`, source
  quantities, calculated/robust method, start/end engineering strain and graph range selection.
  It may show the calculated result as preview evidence. Manual override fields remain absent in
  this normal automatic-method state.
- Top/task commands distinguish `Preview changes` from `Save processed curves`. The normal target
  shows a current preview (`Preview · not saved`) so Save may be enabled. `Save processed curves`
  is the sole filled primary commit action; Preview is secondary.
- Put processed-curve label and save reason in the shallow settings band, adjacent to Save, without
  creating a third column or obscuring the graph.
- Graph header states the selected operation and exact source revision. Show observed input,
  processed preview and elastic-fit overlay with clear legend. Raw/source remains visible or
  recoverable.
- Axis ranges use data-relative padding, not hard-coded fixture maxima: derive padding from finite
  plotted span/magnitude, preserve a physical zero origin when appropriate, and leave visible
  headroom beyond the largest x/y values. Lines must not press against plot edges.
- Settings or inclusion changes visibly stale downstream Fit/Export current pointers without
  mutating immutable history. Graph visibility alone is local and must not invalidate outputs.
- Recipe, Batch, raw JSON, hashes and detailed workup evidence stay in a closed Advanced/Evidence
  disclosure.

### Prerequisite blocked 1440×900

- Preserve the same shell, Process-active stage strip, 192 px rail, shallow band and persistent
  graph region.
- The exact saved Test Data and/or compatible Mapping Profile prerequisite is absent. Do not choose
  a first/latest fallback and do not inherit a fake Processing Output.
- Rail truthfully says no compatible saved curves; operation rows may remain visible but disabled
  only if that helps explain the intended sequence.
- Name the unmet prerequisite in the shallow band. `Preview changes` and `Save processed curves`
  are disabled with an adjacent reason.
- The graph stays mounted with a concise blocked explanation; it must not show a believable current
  processed result.
- Offer one safe primary recovery action, `Back to Data`. Preserve material/family/session context
  and do not fabricate a Mapping Profile, recipe, review or release state.

## Evidence-only states

Exercise at 1366×768, 1440×900 and 1920×1080 without creating additional approval PNGs:

- long curve rail and operation list: independent rail scroll, selected item remains visible after
  keyboard focus, graph width/topology unchanged, no clipped identity;
- preview loading: preserve selected exact source, operation settings and previous graph; announce
  calculation and ensure a newer change supersedes the previous request;
- commit loading: preserve preview and settings, disable duplicate commit, report engineering
  calculation/job state without calling the result saved until success;
- preview or commit error: preserve draft, curve membership, selected operation and graph; announce
  the failed action and offer retry without clearing context.

The prerequisite-blocked target also needs deterministic responsive evidence at 1366×768,
1440×900 and 1920×1080 proving no topology change. Only its 1440×900 PNG is an approval image.

## Static-region → production contract mapping

This reference freezes future structure; it does not implement the React port.

| Static region | Current React/component/data contract to preserve later |
| --- | --- |
| Application/status shell | `ApplicationShell` plus `publishWorkspaceStatus`; exact selection/revision, job, warning, connection |
| Stage strip/context | `CommonProcessingWorkbench.workflowTask`; route-backed Data/Process/Fit/Export and exact session context |
| Curve/operation rail | `ModelingWorkspaceLayout` navigator, `CanonicalTestDataDocumentResponse`, `configuredSteps`; separate include/visibility |
| Resize divider | `ModelingWorkspaceLayout`; viewport defaults 184/192/208, keyboard/collapse semantics and safe graph minimum |
| Ordered steps | `CommonProcessingStep[]` and method registry; method ID/version/options retained in evidence |
| Draft invalidation | `applyDraftSteps` dispatches `CHANGE_PROCESS`, clears preview/selection and stales downstream current pointers |
| Preview | `previewCommonProcessing`; stateless `execution_mode: preview`, `promotable: false`, exact source/profile hashes |
| Graph | `EngineeringCurvePlot`, base/current stages and graph selection command; source and preview remain distinct |
| Workup | `CommonProcessingWorkupOverride`; manual modulus/necking value, unit and reason only when explicitly selected |
| Save | `commitCommonProcessingOutput`; exact source/profile revisions, server-recomputed steps, immutable output/artifact |
| Error/loading recovery | `previewBusy`, abort/request ordering, `busy`, error/notice; preserve draft, selection and plot |

## Responsive and visual safety rails

- Targets are exactly 1366×768, 1440×900 and 1920×1080 at device scale factor 1.
- Rail actual/ARIA widths match 184/192/208 defaults and stay within the approved 180–240 px range.
- Actual plot width is at least 72% of the post-header workspace at 1440 px. The shallow band never
  becomes a permanent side inspector.
- At 1366×768 preserve 12–13 px tree/metadata and 14 px body/data readability. Use independent
  ribbon/rail scrolling where necessary rather than shrinking text.
- At 1920×1080 the graph expands; do not widen the rail or create a third column.
- All controls, legends, axes and decision labels remain contained with no document/body horizontal
  overflow.

## Deterministic acceptance

Provide a target-aware capture and validator which fail unless:

- each PNG is exactly its named viewport, device scale factor 1, with deterministic font loading;
- there are no console errors, page errors, broken resources or document/body horizontal overflow;
- the normal structure has one compact rail/divider, one shallow settings band and one dominant
  persistent graph, with no third column/nested-card hard-gate failure;
- rail defaults, keyboard adjustment, Home/End, collapse/restore and ARIA values are truthful;
- normal contains three curves/two included, separate inclusion/visibility controls, five Process
  operations, selected Elastic modulus, exact source revision and explicit preview-not-saved state;
- observed input, processed preview and calculated elastic-fit overlay remain distinguishable;
- graph bounds are computed from the plotted data with proportional headroom and are not equal to
  hard-coded fixture extrema;
- changing step/range/inclusion stales preview/downstream state, while visibility change does not;
- Save is the only filled commit command and cannot duplicate-submit; source/label/reason/prerequisite
  requirements are explicit;
- prerequisite blocked has no fake curve/output, names the missing exact prerequisite, keeps graph
  topology and offers Back to Data;
- long/loading/error evidence preserves rail/settings/graph context across all viewports;
- keyboard tab order, focus-visible, stage/rail selection, checkboxes, plot visibility, settings,
  disclosures and actions have measurable semantic consequences.

Run at minimum:

```text
python docs/00-research/ux-service-reference/capture_modeling_process_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

Because the main agent owns manifest integration, the family validator may validate a writer-owned
staging index/measurements before the common manifest entries exist. It must switch to the common
manifest after integration without weakening assertions.

## Handoff

Return:

- exact files changed;
- commands and pass/fail results;
- each approval PNG path, viewport and SHA-256;
- exact measurement/responsive/state-evidence paths;
- any residual limitation.

Do not modify shared integration files to make a gate pass. Do not commit or start another family.
