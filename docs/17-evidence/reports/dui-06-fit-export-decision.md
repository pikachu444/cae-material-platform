# DUI-06 Fit and Export decision evidence

Verified on 2026-07-24 against the rebuilt Docker Compose demo and deterministic synthetic DP780
reference data. This bounded slice connects existing T-24, T-25 and T-33 capabilities to the
normal-user Modeling workspace. It implements FR-CAL-004/005, FR-IR-005 and FR-EXP-001/002
presentation and decision continuity without changing their backend, database or OpenAPI contracts.

## Implemented scope

- Fit presents the 4 calculated metal hardening candidates in one flat table with decision, status,
  error, applicability and warning columns. The selected parameters and bounds remain available in
  one disclosure.
- Stress response, residual and tangent modulus reuse the persistent graph. The observed and
  unobserved extrapolation ranges remain visibly separated.
- `Commit reviewed fit` requires a calculated candidate and a non-empty engineering reason. It
  appends an immutable Processing Output and stores its exact identity and revision in the Modeling
  session. Editing only the reason does not rerun or silently alter the numerical preview.
- Export carries the reviewed candidate, method, observed range, exact decision evidence and reason.
  The family workbench selects that exact Processing Output and does not fall back to an unrelated
  earlier model while the reviewed output has not yet been promoted.
- The existing promotion chain remains explicit:
  Processing Output → Material Model IR → Neutral Material JSON → mapping preflight → native solver
  card. Solver, version and `kg·m·s (SI)` unit system are visible before preflight.
- Unsupported mappings remain blocked. Approximated or ignored mappings retain their adjacent
  acknowledgement. A completed card exposes native ASCII and mapping-report downloads plus a
  semantic link to the Material's CAE Cards view.
- Metal and linear-viscoelastic Neutral restoration no longer lets a slower historical lookup erase
  a newly created Neutral result. The same race protection is applied to both family paths.

This work does not choose a production tensile standard, constitutive equation, optimizer, solver
policy, virtual specimen or validation threshold. All numerical evidence remains synthetic,
non-production reference evidence.

## Live decision chain

The live browser obtained the local demo identity and used the protected API through the real web
application at 1440×900:

1. loaded the exact DP780 Test Data revision;
2. opened Fit and found 4 candidate rows;
3. confirmed the commit was disabled without a reason and enabled after entering one;
4. exercised response, residual and tangent views;
5. committed Processing Output `231eb986-6124-4eca-a10a-f962657332df`;
6. confirmed the browser session pinned that output identity and its concrete revision;
7. promoted Material Model IR `3c63f7bd-b390-4447-9fc6-b6fe2302497f`;
8. created Neutral Material `2b73f685-ad8f-4882-ba19-8ca0d61df734`;
9. ran an exportable mapping preflight with the target tuple visible;
10. created solver card `ade533e1-4e7c-4eb9-9d72-a5b8c80ea255`;
11. found the native download and Material CAE Cards link.

The flow ended with 0 px horizontal overflow and no browser console or page errors. IDs above belong
only to the disposable synthetic demo run; the captured current-product baseline was generated
before this acceptance write so screenshots remain deterministic.

## Viewport measurements

The capture and measurement browser opened current-stage settings where necessary and measured the
rendered horizontal graph axis against the complete Modeling split workspace.

| Viewport | Drawable graph width | Workspace width | Drawable share | Candidate rows | Overflow |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 1018.95 px | 1350 px | 75.48% | 4 | 0 px |
| 1440×900 | 1139.03 px | 1424 px | 79.99% | 4 | 0 px |
| 1920×1080 | 1575.46 px | 1904 px | 82.74% | 4 | 0 px |

All viewports exceed the 72% capture hard gate. The candidate table scrolls inside the shallow
graph-adjacent ribbon; it does not create a permanent third column or reduce graph width.

## Reference comparison

The same Material Modeler reference set used for DUI-04 was reviewed again for its
fit/extrapolation, CAE-card creation and card-detail topology. DUI-06 follows the reference's compact
candidate comparison, persistent graph, observed/unobserved distinction and result-to-card sequence.
It deliberately adds this product's exact-revision, provenance, mapping-state and non-production
language.

| Screen | Structure /20 | Density /20 | Data dominance /20 | Command grammar /20 | Disclosure /20 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fit | 19 | 18 | 20 | 18 | 18 | 93 |
| Export | 19 | 17 | 18 | 19 | 18 | 91 |

Both screens exceed 85/100. Topology, dominant-area, nested-card, graph-width and horizontal-overflow
hard gates pass. Fit retains internal vertical scrolling to preserve the graph; Export retains an
internally scrolling bottom dock at shorter viewports. These are explicit bounded trade-offs.

## Current captures

`scripts/capture_current_product.py` generated all 23 current-product images from the clean live
Compose application. Fit captures require the named 4-row candidate table, all 6 decision columns
and the reviewed-fit command. Export captures require the reviewed-delivery heading, exact Neutral
delivery component, visible solver unit tuple, resolved Catalog workflow links and the shared 72%
graph-width gate.

The current user guide includes Fit and Export at 1366×768, 1440×900 and 1920×1080. The capture
command completed with 23/23 outputs and exact viewport dimensions.

## Regression

- Web unit/integration: 45 files, 114 tests passed with 2 workers.
- Changed Fit/session/Neutral/family-workbench subset: 5 files, 10 tests passed.
- Backend unit, repository unit, architecture and contract suites: 658 tests passed.
- Production TypeScript/Vite build and bundle budgets: passed; entry 255.25 kB, Modeling lazy chunk
  116.83 kB and Fit decision lazy chunk 7.59 kB.
- Live Fit → exact Processing Output → IR → Neutral → mapping preflight → native card: passed.
- Current screenshot capture: 23 images at 3 target viewports, passed.
- Current Web Interface Guidelines review: named tables and controls, semantic navigation links,
  visible native focus behavior, labelled form controls, horizontal-overflow handling and
  tabular-number comparison passed for the changed surface.
