# Issue #167 wide correction packet — MOD-PROCESS

Date: 2026-07-30  
Writer role: configured `implementer_luna_max`, exactly one writer  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Correct the already approved `MOD-PROCESS` family so its persistent engineering plot has stable
CSS-pixel geometry at canonical and wide viewports. Recapture the complete four-reference approval
family:

1. `modeling-process-normal-1366x768`
2. `modeling-process-normal-1440x900`
3. `modeling-process-normal-1920x1080`
4. `modeling-process-prerequisite-blocked-1440x900`

Also persist same-topology support evidence:

- normal `2560x1440`;
- normal `3840x2160`;
- prerequisite-blocked responsive `1366x768` and `1920x1080`;
- the existing long-rail, preview/commit-loading and preview/commit-error matrix at
  1366×768, 1440×900 and 1920×1080.

This is static reference work only. Do not change production React/CSS, commit, push, create or
update a PR, or start another family. The four canonical images change lifecycle to `pending` and
require fresh main-agent, reviewer and product-owner approval.

## Main-agent inspection and reason for correction

The main agent opened the current 1366×768, 1440×900, 1920×1080 and prerequisite-blocked images at
original resolution and inspected the static source, current React/API/session contracts, corrected
MOD-DATA graph implementation, issue #167 and the cumulative qualitative checklist.

The approved workspace topology remains sound: one compact curve/process rail, one shallow current
operation band and one dominant persistent graph. Exact Test Data, independent inclusion/visibility,
ordered processing steps, current preview, immutable Processing Output commit and stale downstream
pointers must remain.

The graph implementation is not acceptable for wide completion:

- the SVG is fixed to `viewBox="0 0 1000 500"` and stretched with
  `preserveAspectRatio="none"`;
- at 1920×1080 the Y-axis title and ticks are already visibly enlarged relative to the stable
  application typography; the direct 3840 audit measured a 3609×1723 render box with the same fixed
  coordinate system;
- `950 MPa` puts the unit in a tick while the Y title omits it, and the X title is detached into a
  separate footer;
- the wide footer legend consumes a full lane and mixes curve identity with preview workflow
  status;
- the data attributes calculate proportional headroom but the hard-coded SVG paths, ticks and frame
  do not use the calculated bounds.

The correction must address the coordinate system, axes, paths, legend and evidence as one coherent
plot contract. A CSS-only scale or font override is forbidden.

## Authorities and prerequisites

- `AGENTS.md`
- `.codex/config.toml` and `.codex/agents/implementer-luna-max.toml`
- `docs/01-product/service-reference-inventory.yaml` (`MOD-PROCESS`)
- `docs/01-product/desktop-engineering-ui-product-spec.md` sections 4.2, 7.4
- `docs/01-product/desktop-engineering-ui-spec.md` sections 3.3, 6.3–6.5
- `docs/01-product/desktop-engineering-user-flows.md` Modeling Process flow
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-01, Q-05–Q-07, Q-09, Q-15 and Q-20
- approved corrected MOD-DATA sources and images, read-only:
  - `docs/00-research/ux-service-reference/modeling-data-normal.html`
  - `docs/00-research/ux-service-reference/modeling-data.js`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-2560x1440.png`
  - `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-3840x2160.png`
- current production contracts, read-only:
  - `apps/web/src/common-processing-workbench.tsx`
  - `apps/web/src/design/modeling-workspace-layout.tsx`
  - `apps/web/src/modeling-stage-shell.tsx`
  - `apps/web/src/engineering-curve-plot.tsx`
  - `apps/web/src/api.ts`
  - `apps/web/src/types.ts`
  - `apps/web/src/modeling-session-context.ts`
  - their current tests

MOD-DATA is approved and is the dependency prerequisite. Preserve all approved MOD-DATA hashes.
MOD-FIT and MOD-EXPORT remain untouched.

## Exact ownership

The writer may edit only:

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`
- MOD-PROCESS canonical, responsive, wide-support and state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit:

- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- any approved MOD-DATA, MAT-CARD, MOD-FIT or MOD-EXPORT source/image;
- any file under `apps/`;
- any unrelated dirty-worktree file.

Other work exists in the repository. Do not reset, clean, stash, discard, overwrite or reformat
unrelated changes.

## Preserved product and state contract

Normal Process must retain:

- `Data | Process | Fit | Export`, with Process active;
- one 184/192/208 px combined rail at 1366/1440/1920 and a 5 px truthful keyboard/collapse divider;
- three Test Data curve identities, Specimen 01/02 included and Specimen 03 excluded;
- selection, processing inclusion and local plot visibility as three separate consequences;
- five ordered operations: resolve duplicate x, elastic modulus, proof stress, necking boundary and
  engineering-to-true/plastic;
- `Step 2 · Elastic modulus`, automatic robust method, start/end engineering strain, graph range,
  processed label and save reason in one shallow graph-adjacent band;
- exactly one `Preview changes` command and `Save processed curves` as the sole filled commit action;
- a current unsaved preview whose upstream edits stale Fit/Export current pointers without mutating
  immutable history;
- observed input, processed preview and calculated elastic-fit overlay;
- Advanced/Evidence for recipe, batch, mapping and hashes.

The static-to-production contract remains:

| Reference region/action | Production contract preserved for later port |
| --- | --- |
| Curve/process rail | `ModelingWorkspaceLayout`, exact Test Data and configured-step state |
| Inclusion/visibility | inclusion changes analysis and invalidates as required; visibility is local |
| Draft option change | `CHANGE_PROCESS`, clears current preview/selection and downstream current pointers |
| Preview | `previewCommonProcessing`, exact document/profile plus server steps, abort/supersede ordering |
| Save | `commitCommonProcessingOutput`, exact revisions and server recomputation, immutable Processing Output |
| Stage readiness | `ModelingStageShell`; Fit remains blocked until a current Processing Output exists |
| Graph | `EngineeringCurvePlot`; source/current stage and selection remain distinct |

Prerequisite-blocked must retain the same topology, show no believable processed result, name the
missing exact Test Data revision and compatible Mapping Profile, disable Preview/Save/operations and
offer `Back to Data` without choosing a first/latest fallback.

Loading/error evidence preserves exact source, membership, focused step, settings and last-valid
graph. A newer preview supersedes an older request. Commit loading prevents duplicate submission.
Failure never clears the draft or calls an output saved.

## Required graph correction

### One responsive coordinate system

- Remove the fixed `1000×500` / `preserveAspectRatio="none"` contract.
- Measure the rendered graph canvas in CSS pixels and set the SVG width, height and viewBox to the
  same measured dimensions.
- Recompute frame, grid, axes, ticks, paths, selection/hit regions and blocked backdrop from that
  same coordinate system on initial render, resize and navigator resize/collapse.
- Use a `ResizeObserver` plus a deterministic forced-render hook for capture. Do not transform or
  stretch a pre-authored path.
- Keep text and strokes stable in CSS pixels. Use non-scaling strokes or an equivalent same-scale
  result; no viewport-dependent glyph/stroke inflation.

The corrected MOD-DATA renderer is an implementation reference for geometry only. Preserve
MOD-PROCESS series, overlays and state semantics rather than copying its Data-stage content.

### Engineering axes and headroom

- Plot the synthetic observed, processed-preview and elastic-fit data from finite numeric arrays.
  Paths must be generated from the current axis bounds.
- Derive each upper bound from the displayed finite data span with a proportional headroom ratio,
  then choose a readable nice bound/tick interval. Do not use a fixture maximum as the display
  boundary.
- Preserve zero on both axes for this total engineering stress–strain response.
- The largest finite X and Y values must remain measurably clear of the top/right frame at every
  normal viewport.
- Use compact stable 11 px ticks and 11–12 px titles:
  - Y title: `Engineering stress (MPa)`
  - X title: `Engineering strain [1]`
- Tick labels are numeric only. Do not repeat `MPa` in the top Y tick.
- Axis titles, ticks, frame and graph controls may not collide. Keep margins economical and stable;
  do not grow them with the viewport.
- The selected elastic-fit interval remains visually meaningful and must be computed from the same
  data coordinates.

### Legend and workflow status

- Place the compact curve legend inside a measured curve-free plot quadrant, lower-right when clear.
  It must move to another safe quadrant or use a compact docked fallback if it would overlap curves,
  axes, labels, blocked overlays or selection feedback.
- The legend identifies only `Observed input`, `Processed preview` and `Calculated elastic fit`.
  It does not reserve a wide footer row.
- Keep `Preview · not saved` and source recoverability in the existing ribbon/header/status
  hierarchy, not as a fourth legend item.
- The X-axis title stays centered under the plot frame in the SVG coordinate system rather than in
  a detached footer.

### Wide-screen use of space

- At 1920×1080 and 2560×1440, the rail and operation band remain bounded while the persistent graph
  consumes the elastic remainder.
- The first corrected 3840×2160 capture is explicitly rejected by the active main agent. Stable
  11–12 px SVG text and non-scaling strokes fixed distortion, but a roughly 3,600×1,700 plot still
  overwhelms the 208 px rail and shallow ribbon. Passing SVG geometry is not sufficient when the
  full-screen working proportions remain implausible.
- At 3840×2160 only, bound the graph to a useful engineering working height and use the recovered
  lower region for one flat `Processed response` point grid. Populate it directly from the same
  finite `PROCESS_STRAIN`, observed-series and processed-preview arrays used by the SVG. Columns are
  `Engineering strain [1]`, the three observed stresses and `Processed preview (MPa)`. Do not
  interpolate, resample, smooth, enrich or fabricate rows.
- The exact point grid is result evidence, not a third inspector. It spans the existing graph result
  region below the plot, uses ordinary 12–13 px table text and compact rows, and has no explanatory
  paragraph, badge, developer vocabulary or duplicate workflow controls. All ten exact rows should
  fit at 3840 without a false scrollbar.
- Do not stretch rail rows, forms, prose or plot typography to fill width.
- Do not create a permanent third column, explanatory filler or a dominant blank panel.
- Canonical 1366/1440/1920 and 2560 support retain the graph-first topology. The 3840 graph-plus-grid
  composition is a deliberate responsive topology change and therefore becomes one additional
  lifecycle target rather than support-only evidence. The active main agent will integrate that
  target into the common inventory/manifest after the family passes its gates.

### Navigator overflow

- Normal short content shows no fake scrollbar.
- The long-rail exercise must expose a discoverable independent local scrollbar with a reserved
  track and proportional thumb. Long stored identities remain reachable without colliding with the
  scrollbar; keyboard focus keeps the selected row visible.
- Rail scrolling or resizing must not change graph topology or plot bounds semantics.

## Deterministic capture and validation

Extend capture and validation so they fail unless:

- canonical PNG dimensions and DSF are exact;
- normal `2560x1440` and `3840x2160` PNGs plus measurements are persisted and hashed in staging;
- there are no console/page/resource errors or body/document overflow;
- SVG render width/height and viewBox match the measured graph box within a small tolerance;
- `preserveAspectRatio="none"` and a fixed 1000×500 coordinate system are absent;
- tick/title font sizes and stroke widths remain stable within tolerance at 1366, 1440, 1920, 2560
  and 3840;
- numeric-only ticks and exact axis titles are present;
- data arrays, displayed bounds, headroom ratio, nice steps and point-to-frame clearances are
  recorded and validated;
- the internal legend is contained, does not intersect plotted curves/frame/axes/titles/blocked
  overlay and does not create a footer lane;
- the 3840 image records a bounded graph box plus exactly ten point-grid rows sourced from the
  renderer arrays, with matching numeric values, no table overflow and no fake local rail;
- 1366, 1440, 1920 and 2560 contain no `Processed response` grid;
- rail/ribbon/graph ratios, 184/192/208 defaults, keyboard divider effects and topology are
  preserved, except for the explicitly registered 3840 graph-plus-grid topology;
- normal, blocked, long, loading and error interaction/state assertions continue to pass;
- approved MOD-DATA and unrelated family hashes remain unchanged.

The four canonical staging targets remain `pending`. The main agent alone integrates the common
manifest, inventory and shared evidence report after deterministic and visual inspection.

Run at minimum:

```text
python docs/00-research/ux-service-reference/capture_modeling_process_wave02.py --help
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --help
python docs/00-research/ux-service-reference/capture_modeling_process_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

## Writer handoff

Return:

- exact files changed;
- commands and pass/fail results;
- the four canonical target paths, dimensions and SHA-256 values;
- 2560/3840 support paths, dimensions and SHA-256 values;
- responsive/state evidence paths;
- measured plot geometry, typography/stroke stability, headroom and legend collision results;
- any residual limitation.

Do not declare visual approval, edit shared integration files, commit or start another family.
