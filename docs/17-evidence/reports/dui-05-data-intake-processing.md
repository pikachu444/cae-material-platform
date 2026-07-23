# DUI-05 Data intake and processing evidence

Verified on 2026-07-23 against the rebuilt Docker Compose demo, protected API and PostgreSQL-backed
synthetic reference data. This bounded slice reuses T-41 governed import, T-52 canonical Test Data
and T-54 common processing contracts. It adds no production test standard, vendor parser,
processing algorithm or persistence migration.

## Implemented scope

- Modeling Data owns one `Library | Local file | Test Data JSON` source chooser beside the
  persistent graph. The compatibility routes `/datasets/import` and `/datasets/test-json` remain
  available for advanced administration and evidence work.
- Local CSV/TSV/XLSX bytes are uploaded as immutable Raw Asset/Artifact evidence before inspection.
  A one-sheet XLSX is selected automatically; a multi-sheet workbook returns only the worksheet
  names until the user chooses one.
- An existing human-approved Import Profile is reused only when classification, file format,
  worksheet, header/locale and all source columns match exactly. A resolved mapping is summarized.
  Test type, the two required channels and their original units appear only when the match is
  missing, ambiguous or deliberately edited.
- Local files and canonical JSON are validated and rendered in the same persistent graph before
  registration. The final command first executes the governed Import Run, then registers the
  canonical Test Data exact revision. A failed Import Run cannot partially register Test Data.
- Process retains direct graph range and point commands. `Preview processing` remains ephemeral;
  `Commit reviewed output` is visible in the shallow current-step ribbon. Mapped input and selected
  stage remain separately controllable and visually distinct.
- Original unit strings, normalized units, quantity semantics, source SHA-256, exact Test Run,
  exact Import Profile and raw/normalized Dataset revisions remain server-governed evidence.

## Live flow and measurements

The current product capture script exercised Data → Process → Fit → Export at all target
viewports and rejected unfinished async state, horizontal overflow or a graph drawable below 72%
of the Modeling workspace. A separate native Playwright run selected the synthetic
`reference-tensile.csv`, uploaded immutable bytes, received an unresolved-mapping attention state,
filled only missing test context, previewed the canonical curve with the single explicit mapping
stage and stopped with `Register reviewed data` visible. No Library row remained selected during
the unregistered preview. It produced no console errors and no horizontal overflow.

| Viewport | Data ribbon | Graph drawable | Split workspace | Drawable share | Overflow |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 106 px | 1,019.0 px | 1,350.0 px | 75.5% | 0 px |
| 1440×900 | 106 px | 1,139.0 px | 1,424.0 px | 80.0% | 0 px |
| 1920×1080 | 106 px | 1,575.5 px | 1,904.0 px | 82.7% | 0 px |

At every viewport the Process ribbon exposed `Commit reviewed output`, and the graph exposed both
`Mapped input` and `Selected stage`. The live local-file preview at 1440×900 retained an 80.0%
drawable share.

## Material Modeler reference comparison

`modeler-start-data.png`, `modeler-youngs-manual.png`, `modeler-necking-point.png` and
`material-modeler-curve-fitting.png` were compared directly. The implementation follows their
source-first staged flow, dominant persistent graph, graph-adjacent engineering controls and
explicit preview-to-result decision. It preserves this product's exact revision, provenance and
unit evidence instead of copying proprietary decoration or inferring production domain policy.

| Screen | Structure /20 | Density /20 | Data dominance /20 | Command grammar /20 | Disclosure /20 | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Data · Library | 19 | 18 | 19 | 18 | 18 | 92 |
| Data · Local file | 18 | 17 | 18 | 19 | 18 | 90 |
| Data · JSON | 18 | 18 | 19 | 18 | 18 | 91 |
| Process | 19 | 18 | 19 | 19 | 18 | 93 |

All screens exceed 85/100. Topology, dominant-area, nested-card, graph-width and
horizontal-overflow hard gates pass.

## Regression

- Web production build and bundle budgets: passed; intake is a 16.6 kB lazy chunk.
- Web unit/component regression: 45 files, 114 tests passed.
- Backend unit and architecture: 435 tests passed.
- Governed XLSX discovery: unique-sheet, multi-sheet, formula and unsafe relationship cases passed.
- Contract suite: 162 tests passed after aligning the DUI-03 capture-count/activity assertions with
  the already merged 23-screen manifest.
- Live current product capture: 23 images generated from the rebuilt Compose application.
- Live local CSV preview: immutable upload, attention-only mapping, graph preview, 0 console errors,
  0 horizontal overflow.
