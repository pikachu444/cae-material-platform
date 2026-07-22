# DUI-04 persistent Modeling workspace evidence

Verified on 2026-07-22 against the rebuilt Docker Compose demo, protected API and PostgreSQL-backed
synthetic reference data. This slice changes the Modeling facade and browser UI session only; fitting,
processing, immutable revision, Material Model IR and solver-card API contracts are unchanged.

## Implemented scope

- One command hierarchy owns `New session`, `Save draft`, `Undo`, `Redo` and the
  `Data | Process | Fit | Export` stages.
- A 180–240 px resizable/collapsible curve and process navigator sits beside one dominant graph.
  Current-step controls use a shallow graph-adjacent ribbon; there is no permanent third column.
- The graph remains mounted across stage changes, including Export and return to Fit. Stage, family,
  selected exact documents, selected step/stage, plot view and ribbon state resume from Modeling
  session schema v2. Legacy v1 sessions migrate without changing their exact revision references.
- Preview is visibly labelled `Preview only · not committed`. Save/undo/redo operate on the Recipe
  draft, browser exit warns for unsaved changes, and New session clears only UI session state after
  confirmation.
- Stage and family are shareable URL query state. Existing deep links and all existing processing,
  fitting and export calls remain in place.
- Data exposes only exact Test Data, Mapping Profile, channel summary and import commands. Process
  owns curve preparation and the necking boundary; Fit alone owns candidate equations, residuals and
  extrapolation comparison. Export keeps the selected fit, observed range and graph visible while a
  flat bottom delivery dock exposes Neutral IR and solver-card work.
- Activity names the exact material/session context, stage, Test Data revision and selected-curve
  count. `Resume Fit` was exercised in the live browser and restored the same session string, exact
  document and both selected curve identities.

## Live flow and measurements

`scripts/capture_dui04_modeling.mjs` obtains the local demo identity, opens an exact DP780 Test Data
revision, waits for the server preview, switches Data → Process → Fit → Export → Fit through the
real command bar, and asserts that the before/after graph nodes are identical. It rejects Data if a
Fit-only candidate control is present, rejects Process if Fit evidence is present, and rejects any
capture containing `Checking…`, `Loading…` or `Calculating…`. After the captures it opens Activity,
resumes Fit, and compares the session, exact Test Data and checked curve identities.

| Viewport | Navigator | Main/plot region | Main share of split workspace | Overflow | Graph preserved |
| --- | ---: | ---: | ---: | ---: | --- |
| 1366×768 | 184 px | 1161 px | 86.0% | 0 px | yes |
| 1440×900 | 192 px | 1227 px | 86.2% | 0 px | yes |
| 1920×1080 | 208 px | 1691 px | 88.8% | 0 px | yes |

The shallow settings ribbon is open at all three target viewports so each stage purpose is visible.
The Export overlay dock occupies 40% of the main surface at most (208/261/333 px at the three target
viewports) and leaves the mounted graph above it. Divider buttons have explicit accessible names and
expanded state. The existing F6 region cycle continues to cover application, commands, main
workspace and status.

## Material Modeler reference comparison

All seven local Material Modeler screens in `docs/00-research/images/gui-reference/material-modeler`
were compared directly: start data, automatic/manual Young's modulus, necking point, fit/extrapolation,
CAE-card creation and card details. The implementation follows their compact staged workflow,
left process/curve ownership, persistent plot, inline engineering controls, observed/extrapolated
distinction and result-to-card progression. It deliberately preserves this product's exact-revision,
provenance and non-production plugin language instead of copying proprietary decoration.

| Screen | Structure /20 | Density /20 | Data dominance /20 | Command grammar /20 | Disclosure /20 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Data | 18 | 17 | 18 | 18 | 17 | 88 |
| Process | 18 | 18 | 19 | 18 | 17 | 90 |
| Fit | 19 | 18 | 20 | 18 | 17 | 92 |
| Export | 18 | 16 | 17 | 18 | 17 | 86 |

All screens exceed 85/100. Topology, dominant-area, nested-card, graph-width and horizontal-overflow
hard gates pass. Export is deliberately scored lowest: its dock must scroll at 1366 and the fixed
engineering plot leaves more lateral breathing room at 1920 than the reference. Those are visible,
bounded limitations rather than a claim of pixel parity or completion of a later delivery task.

## Captures

The screenshot manifest registers Data, Process, Fit and Export at 1366×768, 1440×900 and
1920×1080 under `docs/15-demo/images/ux-redesign-v2/dui-04-modeling-*.png`. Every PNG has the exact
requested viewport dimensions and was captured after asynchronous data completed. The images show
four distinct tasks rather than four copies of the same Fit configuration.

## Regression

- Web production build and bundle budgets: passed.
- Web unit/integration: 42 files, 103 tests passed.
- Modeling session v2 migration, navigator/ribbon accessibility and persistent stage plot tests: passed.
- Live Data → Process → Fit → Export → Fit state continuity and 12 captures: passed.
- Guided Playwright clean-demo regression: 3 scenarios passed, including exact native-card hashes,
  governed ZIP download and exact workflow-revision navigation.
- Backend/default: 789 passed; only the 76 separately executed PostgreSQL-marked tests skipped.
- PostgreSQL/RLS profile: 76 passed, 123 non-PostgreSQL tests deselected.
- Architecture boundary, contract lint, OpenAPI compatibility, clean full-demo verification,
  user-guide/screenshot validation and worktree documentation impact: passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.

Repository-wide Ruff and mypy retain the known baseline outside this UI slice: Ruff reports 30
findings in the installed upstream webapp-testing examples and existing documentation utilities;
mypy reports three existing type errors in `governed_tabular.py`. No Python source changed in DUI-04,
and both complete functional suites above pass.
