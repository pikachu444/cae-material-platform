# #167 WAVE-03 MOD-FIT implementer packet

Date: 2026-07-29
Author: main Sol High agent
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Bounded assignment

Create the complete MOD-FIT reference family: three normal viewports, one canonical long candidate
detail state, and deterministic responsive/state evidence. This is static reference work only. Do
not edit production React/CSS, common manifest/inventory/evidence, GitHub or another family.

Approval targets:

1. `modeling-fit-normal-1366x768`
2. `modeling-fit-normal-1440x900`
3. `modeling-fit-normal-1920x1080`
4. `modeling-fit-candidate-parameters-long-1440x900`

Dependency prerequisites:

- MOD-DATA is approved at all three normal viewports.
- MOD-PROCESS is approved at all three normal viewports plus prerequisite-blocked.
- Exact shared-shell references and hashes are in
  `docs/01-product/service-reference-manifest.yaml`.
- `docs/00-research/ux-layout-review/modeling.html`,
  `docs/00-research/ux-layout-review/review.css`,
  `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png` and
  `docs/00-research/images/gui-reference/modeler-fit-extrapolation.png` govern Fit topology.

The approved Data/Process dark application shell, compact stage strip and responsive rail are the
newer shared visual authority. The approved `modeling.html`/`review.css` governs Fit-specific region
structure: compact Curves/Process rail, 31 px step heading plus approximately 72 px normal controls,
closed Candidate parameters disclosure, separate compact graph header and dominant persistent plot.
Do not restore the rejected white three-column workbench or its permanent inspector.

## 2. User task and product judgment

An engineer compares recomputed material-model candidates against processed observed evidence, sees
the observed/extrapolated boundary, distinguishes recommendation from selection, and can inspect
parameters without losing the graph. A recommendation never becomes the engineer's selected model.

The normal approval image is the dominant comparison view with recomputed candidates and no current
engineer selection. Candidate parameters are closed. `Save fit & continue` is visibly disabled with
an adjacent reason. The exact preview blend may be plotted, but it is labelled `Preview`, not
`Selected`.

## 3. Preserved React/API/state contracts

| Static region or state | Production contract represented |
| --- | --- |
| shared shell/stages | `ModelingStageShell`: Data, Process, Fit, Export only |
| current exact source | `ModelingSessionSummary.processingOutput` and exact Test Data/Mapping Profile pins |
| compact rail | `F-01`/`P-01` compatible curve rows and configured ordered process/fit sequence |
| Fit ribbon | current `CommonProcessingStep.options` for metal hardening fit/extrapolation |
| candidate computation | current server preview/stage `scalar_results`; `Update candidates` is not a save |
| recommendation | lowest available calculated metric; evidence only |
| engineer selection | `FitDecisionSelection`; explicit row event only |
| save snapshot | `buildFitDecisionSnapshot`; non-empty reason and selected-row acknowledgement gating |
| graph | persistent server series; Response/Residual/Tangent view and observed/extrapolated boundary |
| invalidation | option/inclusion change clears current candidate selection/downstream pointers, not immutable history |

Preserve these truths:

- exact source is a saved Processing Output revision; never use `latest`;
- Voce, Swift, Hockett–Sherby and Ghosh are synthetic reference candidates only;
- the exact calculated two-law preview blend is a separate selectable row after recomputation;
- the graph and decision evidence use both law names and ratio;
- candidate metrics, parameter values/bounds and warnings come from one recomputed stage fixture;
- validation, review, approval, release and delivery are absent from normal Fit language;
- UUIDs, hashes, Recipe JSON and raw Mapping Profile keys stay in Advanced/Evidence.

## 4. Normal visual/state contract

### Shared regions

- Dark 46 px application bar consistent with approved MOD-DATA/MOD-PROCESS.
- Compact context/title row and `Data | Process | Fit | Export` stage strip.
- 184/192/208 px rail at 1366/1440/1920 with one 5 px resizer/collapse control.
- No permanent third inspector.
- Body/data 13 px; metadata and decision help 12 px minimum with normal wrapping.
- One filled primary command at most. `Save fit & continue` is the commit action; with no selection
  it is disabled and its missing requirement is adjacent. `Update candidates` is secondary once
  results already exist.

### Rail

- `Curves · 3 curves · 2 included`, native test-method disclosure, three exact specimen/revision
  rows.
- Inclusion checkbox, curve-selection button and icon-only plot visibility are semantic siblings,
  never nested interactive controls.
- Ordered Fit rail uses the configured visible sequence: Sort duplicate x, True/plastic conversion,
  Necking boundary, Hardening fit. Do not substitute one `Fit candidates` row.
- Rail scroll is independent under long labels.

### Normal ribbon

Keep the Fit-specific grouping from `modeling.html`:

1. Candidate equations
2. Fit domain: Start/End
3. Selected blend: Primary/Secondary
4. Primary contribution and Review metric
5. Extrapolation: Target strain/Output points
6. Graph interaction: Select fit range/Pick point
7. compact closed `Candidate parameters` disclosure

Do not duplicate range/point actions in the graph toolbar. Input changes mark candidates/selection
stale and require Update candidates.

### Normal graph

- Header: `Stress response · observed evidence and hardening candidates`.
- Compact controls: Response, Residual, Tangent modulus, Reset view.
- Plot observed workup plus decision-relevant candidate laws and `Preview Swift/Voce 50/50 blend`.
- Visibly shade and label `EXTRAPOLATED · UNOBSERVED`.
- Legend is compact, contained and may be locally hidden.
- At 1440 the plot region width is at least 72% of the workspace; the graph remains vertically
  dominant at every viewport.
- Axis limits are derived from finite plotted data using proportional headroom, not fixed maxima.
  Record the finite extrema, headroom ratio and derived limits. Include a deterministic altered-data
  assertion proving limits change when extrema change.

## 5. Long candidate-parameters approval state

Canonical image: 1440×900.

- Open the Candidate parameters disclosure from the graph-adjacent band.
- Show a complete candidate comparison table with model/law, recommendation, metric, fit/
  extrapolation range, stability, compatibility, warning and explicit selection control.
- Include the exact calculated blend as its own row.
- Focus one selected candidate only after an explicit selection event; show a non-empty synthetic
  selection reason and only its applicable warning acknowledgement.
- Show parameter value/unit/lower/upper evidence for the selected law(s). Long realistic parameter
  names and bound content must wrap or scroll inside the disclosure, never expand a page-wide
  inspector.
- Cap/scroll the disclosure so the persistent graph stays mounted and visibly useful below it.
- Closing the disclosure must restore the full dominant normal graph.

## 6. Evidence-only states

Persist independently named PNGs, exact dimensions and SHA-256 for all three viewports:

- no-candidate empty: source/rail/ribbon/graph remain; no selection; one Update candidates action;
- calculating: prior graph and inputs remain, `aria-busy`/announced progress is local, no blank page;
- stale/no-selection blocked: changed intent is named, recommendation is not selected, Save disabled,
  Update candidates is the safe recovery;
- candidate calculation error: last good graph/rail/input stays visible, failed method is named and
  Retry/Update candidates is available.

Also record normal interactions at all three viewports:

- option/inclusion change invalidates selection;
- successful Update candidates does not auto-select;
- candidate row selection is explicit;
- reason and selected-row warning acknowledgement gate Save;
- input change after selection disables Save until recompute/reselect;
- Response/Residual/Tangent views preserve selection/context;
- Candidate parameters opens/closes and returns graph space;
- curve selection, inclusion and visibility remain independent under pointer/keyboard;
- splitter Arrow/Home/End/collapse/restoration changes actual geometry and ARIA;
- long rail scroll does not change graph width.

Do not keep these screenshots only in memory.

## 7. Source and ownership

Owned paths may include only new MOD-FIT WAVE-03 paths:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json`
- new MOD-FIT WAVE-03 PNG/measurement/state JSON under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit approved `modeling-data*`, `modeling-process*`, `modeling.html`, `review.css`, common
manifest/inventory/evidence, MAT-EXP paths or any production file.

## 8. Evidence schema and hard gates

For every approval target record source paths, state/viewport, image path/dimensions/SHA-256, date,
pending lifecycle, region geometry, ribbon/rail/plot share, typography, plot extrema/headroom,
selection/recommendation identities, controls, interaction outcomes, browser errors/overflow and the
zero legacy-selector report for:

`page-stack`, `page-heading`, `content-card`, `module-material-card`, `hero-actions`, `eyebrow`,
`status-badge`, `count-chip`.

Validator hard gates:

- approved MOD-DATA/MOD-PROCESS hashes are unchanged;
- exact shared shell and Fit-specific topology are present;
- 184–210 px rail, no third inspector, graph width ≥72% at 1440;
- normal disclosure closed, recommendation present, engineer selection absent, Save disabled with
  reason, preview blend names both laws and ratio;
- long disclosure is open, complete, independently contained, and graph remains visible;
- candidate inputs/rows/metrics/parameters/warnings are complete and internally consistent;
- proportional axis derivation and altered-extrema proof pass;
- all responsive/state evidence PNG paths exist and hashes/dimensions match;
- body/data/metadata typography is readable; no clipped decision text;
- semantic controls, accessible names, visible focus, no nested interactive controls;
- zero console/page errors and zero document/body overflow.

## 9. Required commands

Run both helpers with `--help` before capture, then:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_modeling_data.py --all-packet-targets --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
uv run ruff check docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py
node --check docs/00-research/ux-service-reference/modeling-fit.js
git diff --check
```

The process validator's staging expectation remains `pending`; product-owner lifecycle is recorded in
the common manifest, which this writer must not edit.

Open all four approval PNGs and representative exceptional-state PNGs at original resolution before
returning. Report changed paths, exact commands/results, approval-image hashes and residual risks.
Do not request product-owner approval.
