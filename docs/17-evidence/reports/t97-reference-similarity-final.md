# T-97 final Search-first and reference-similarity acceptance

Date: 2026-07-21

This report closes the approved T-94 design policy against the live T-95–T-97 implementation. It
does not use color, logo, icon or pixel similarity as evidence. The comparison uses region order,
dominant data/graph proportion, row and type density, divider/surface grammar, selected-object
continuity, solver-card action placement and progressive disclosure.

## Change classification

### Kept

- PostgreSQL-backed Database → Profile → Table → Folder → Record hierarchy and exact Record
  revision context.
- Configurable Table, all typed Attribute Definitions, Layout, saved Subset, Link Type,
  bidirectional exact-revision Record links and Layout-driven Datasheets.
- Typed material search/facets/normalized quantity ranges, multiple-Record and revision comparison.
- Material → State → Test/Test Data → Dataset → Recipe/Processing Output → Material Model IR →
  Neutral Material → solver-card provenance.
- Immutable raw/released bytes, stable identity versus revision, original/normalized unit and
  quantity semantics, retained outliers and explicit solver mapping states.
- Existing metal, polymer and elastomer processing/calibration engines. The redesign changes their
  facade, not their numerical or persistence contracts.

### Structurally changed

- `/materials` is the default entry and owns search, governed Browse Tree, dense results and optional
  selected context on one continuous workspace.
- Material Detail is `Overview | Properties | Curves | CAE Cards | Evidence`; Layout values are
  projected into these tabs and extra Layouts remain available from Evidence.
- Modeling is `Data | Process | Fit | Export`. Its curve/process navigator is 180–196 px, settings
  use a shallow horizontal ribbon and the graph consumes the remaining width.
- `/datasets/import` now restores the exact recent Modeling Material State and mounts the real
  governed CSV/TSV/XLSX importer. It is no longer an unreachable component or a mock upload.
- A reviewed Processing Output can be selected even when an older Neutral revision already exists;
  the user is not trapped on the previous Neutral/Card chain.
- Search/filter/sort/navigator/selected-Material state is encoded in the URL and Detail return path.
- Administration keeps its engines while using compact data rows and dividers instead of schema
  cards and a decorative dark rail.

### Removed or demoted

- Normal global navigation no longer exposes separate Database, Tests, Datasets, Models, Exports,
  Governance and Administration products. The visible menu is `Materials | Modeling | Activity`.
- A dead Common Processing lazy route was removed. `/catalog/schema` and `/datasets/processing` are
  intentional compatibility routes to the canonical Administration and Modeling workspaces.
- Permanent third-column Modeling inspector, nested persistent cards, decorative gradients,
  repeated large eyebrow text and default-view UUID/hash/Mapping JSON were removed or moved to
  Advanced/Evidence.

### Intentionally not implemented

- Production material/model approval, actual Abaqus/OpenRadioss execution correlation and
  proprietary laboratory formats remain outside this reference/non-production scope.
- Optional column resizing is not required for acceptance; bounded minimum widths, ellipsis/title,
  sticky key columns and horizontal table scrolling remain the current policy.
- The upload-to-card path remains longer than known-material download because it requires explicit
  unit, mapping, extrapolation and solver-approximation decisions. None is silently skipped.

## Direct reference-image interpretation

Every local image below was opened directly during the T-94 design gate; filenames and README text
were not used as a substitute for visual inspection. Commercial branding, colors, icons, proprietary
names, exact geometry and inferred internal workflows were excluded.

### UX reference gallery

| Directly inspected image | Applied design method |
| --- | --- |
| `granta-mi-favourites-list.png` | Stable narrow navigator, compact divider rows and selected Record continuity; no card-per-record treatment. |
| `material-data-center-search-detail.png` | Search/filter position remains stable while result selection updates optional contextual detail. |
| `material-data-center-cae-model.png` | Solver context, compatibility warning and native Download stay together; Download is the current primary action. |
| `material-modeler-curve-fitting.png` | One persistent dominant graph, short curve labels and graph-adjacent task controls. |
| `material-modeler-hyperelastic-fitting.jpg` | Observed points and candidates share one plot; settings support the plot rather than becoming a dashboard column. |

### Granta MI official GUI references

| Directly inspected image | Applied design method |
| --- | --- |
| `granta-profile.png` | Database/Profile/Table scope remains explicit above Contents; it is not replaced by a family facet. |
| `granta-contents-tree.png` | 26 px hierarchical rows, node type/depth/selection marker, fixed Tree search and independent node scroll. |
| `granta-list-results.png` | Adjacent compact list/table comparison with stable selected-row ownership. |
| `granta-datasheet-embedded.png` | Selected Record opens a datasheet in context instead of a new dashboard stack. |
| `granta-datasheet-full.png` | Flat Layout sections and property rows use whitespace and dividers before borders. |
| `granta-curves-view.png` | Curve information remains attached to the selected Material and uses an engineering plot rather than a decorative card. |
| `granta-functional-edit.png` | Typed value/unit editing remains an explicit governed action; display and editing modes are not conflated. |
| `granta-admin-schema-tool.png` | Table/Attribute structure remains administrator-defined without requiring a migration. |
| `granta-admin-tables.png` | Tables and their definitions are compact data rows on one workspace. |
| `granta-admin-layout.png` | Ordered Attribute placement remains a real Layout contract and projects into the user datasheet. |
| `granta-record-links-datasheet.png` | Related Records use typed forward/reverse labels in the datasheet context. |
| `granta-record-links-edit.png` | Source/target Table, cardinality, direction and exact revision binding remain administrator controls. |
| `granta-record-links-explore.png` | Related/Workflow navigation preserves the selected Record and graph ancestry. |

### Material Modeler official GUI references

| Directly inspected image | Applied design method |
| --- | --- |
| `modeler-start-data.png` | Imported curves are ordinary one-line entries next to the plot; source/unit detail is not a large curve tile. |
| `modeler-youngs-auto.png` | Automatic engineering result and selected range remain visible with the response. |
| `modeler-youngs-manual.png` | Manual controls are bounded to the current task and do not reduce graph width. |
| `modeler-necking-point.png` | Point/range selection acts directly on the persistent curve and requires explicit application. |
| `modeler-fit-extrapolation.png` | Four fitting candidates, observed boundary and unobserved extrapolation are compared in one large plot. |
| `modeler-create-cae-card.png` | Reviewed Fit flows directly into solver/law/unit selection in Export. |
| `modeler-cae-card-details.png` | Native solver text is previewed before exact `.inp`/`.rad` download; mapping evidence remains available. |

## Live desktop measurements

Chromium reports a 15 px vertical scrollbar, so both requested browser width and DOM client width are
recorded. Outer margin is the total left plus right margin around the engineering workspace.

### Materials

| Browser viewport | Client / workspace | Outer margin | Tree/filter | Main results | Context | Readable result columns |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1366×768 | 1351 / 1304.6 px | 46.4 px | 244 px | 1058.6 px | closed | Compare, Material, Family, Source, Yield, CAE cards |
| 1440×900 | 1425 / 1376.1 px | 49.0 px | 264 px | 830.1 px | 280 px | all six; key names remain one line |
| 1920×1080 | 1905 / 1841 px | 64 px | 280 px | 1259 px | 300 px | all six with expanded name/source allocation |

At 1366 px the optional context closes instead of shrinking results. The DP780 Browse Tree renders
ordinary 12.5 px labels in exact 26 px rows and retains Database/Profile/Table/Material Library/
Metals/Steels/DP780 ancestors. A Tree-local `DP780` search returned eight governed Record matches,
including Test JSON, Processing Output, IR and two native cards. `ArrowRight` followed by `ArrowDown`
moved focus from Database to Profile with roving `tabindex=0`.

Before the redesign, the common `main` CSS was capped at 1180 px with `margin: 0 auto`: at a nominal
1440 px viewport that left 260 px of total outer space, and Materials had no integrated governed Tree.
The live 1440 workspace is now 1376.1 px with 49 px total outer margin, a 196.1 px/16.6% usable-width
increase plus a real 264 px Tree/filter navigator.

### Modeling

| Browser viewport | Client / workspace | Outer margin | Curve/process rail | Graph region | Actual graph SVG | SVG/workspace |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1366×768 | 1351 / 1304.6 px | 46.4 px | 180.3 px | 1124.3 px | 1099.9 px | 84.3% |
| 1440×900 | 1425 / 1376.1 px | 49.0 px | 190.1 px | 1186.0 px | 1161.6 px | 84.4% |
| 1920×1080 | 1905 / 1841 px | 64 px | 196 px | 1645 px | 1620.6 px | 88.0% |

The 124 px settings ribbon occupies a row above the graph; opening it does not change graph width.
At 1366 it defaults closed. The rejected implementation used a permanent three-column workspace and
a 743 px graph at 1440. The live graph is 1161.6 px, +418.6 px/+56.3%, and exceeds the 1050 px/72%
hard gate. `Specimen 01`, `Curve 01`–`Curve 03` are 12.5 px normal labels in 26 px rows; units live on
axes and mapping controls. No page-level horizontal overflow was present at any measured viewport.

### Typography and surface grammar

- Page titles are 18–20 px; body/data is at least 14 px; Tree labels are 12.5 px; visible engineering
  metadata and graph controls have a 12 px CSS floor.
- Tree/result/curve/Attribute rows use dividers and flat selection backgrounds. Persistent workspace
  panes have no radius or shadow and no persistent card contains another card.
- The only sub-12 px Tree glyphs are non-text disclosure/type symbols with their human-readable label
  in the same 12.5 px `treeitem`.
- Visible controls in Materials and Modeling have accessible names; the audited pages have no unnamed
  button/input/select/textarea/link and no document-level horizontal overflow.

## Live structural-similarity score

| Live screen | Topology /25 | Dominant area /25 | Density /15 | Surface /15 | Continuity /10 | Action/disclosure /10 | Total | Hard gates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Materials Search | 25 | 24 | 14 | 15 | 10 | 9 | **97** | pass |
| Browse Tree + results | 25 | 25 | 15 | 15 | 10 | 9 | **99** | pass |
| Material Detail / CAE Card | 25 | 23 | 14 | 15 | 10 | 10 | **97** | pass |
| Modeling Fit | 25 | 25 | 15 | 15 | 10 | 9 | **99** | pass |
| Modeling Export / Card | 24 | 24 | 14 | 15 | 10 | 10 | **97** | pass |
| Administration | 24 | 23 | 14 | 15 | 10 | 9 | **95** | pass |

All screens exceed 85/100. Region order/adjacency, dominant result/graph, zero nested persistent
cards and one task primary action pass as independent hard gates. These scores reuse the approved
T-94 masks but substitute live DOM bounds and current screenshots for prototype geometry.

## Browser scenarios and task path

Counts below are pointer/primary-control activations; text entry, select-option changes and the OS
file chooser are excluded so the number is reproducible across keyboard and pointer use.

### A — known Material to OpenRadioss card

`DP780` search → selected result → Material Detail → OpenRadioss native preview → `.rad` download.

- 4 pointer actions from the populated search field; 3 post-search primary task actions.
- The first Detail viewport showed name/grade/family/source, key properties, representative curve,
  conditions, card availability and Preview/Download.
- Downloaded native `/MAT/LAW36` file: `CMP_DEMO_DP780_NEUTRAL-… (1).rad`, 5090 bytes.
- No UUID, digest or Mapping Profile JSON was entered.

### B — governed Browse Tree

Browse Tree → `DP780` Tree search → DP780 Record → Evidence/Workflow → CAE Cards.

- 5 pointer actions, excluding the Tree query text.
- Exact hierarchy and selected Record/revision context survived Search/Tree/Detail transitions.
- Evidence showed Material → State → Test JSON → Processing Output → IR → Neutral → Abaqus and
  OpenRadioss, with typed Related labels rather than flat attachment strings.

### C — Administration

Administration → Database design → Table → add Attribute → create Layout → database preview → DP780
Datasheet.

- 7 primary/navigation actions, excluding form fields.
- Created synthetic text Attribute `ux_acceptance_note_20260721`, placed it in a new Engineering
  datasheet Layout and observed `UX acceptance note · text · Not set` through the real Catalog API and
  PostgreSQL. Existing saved Subset and many:many Link Type remained present.

### D — JSON/CSV/XLSX data to two solver cards

The acceptance used the real upload controls and the synthetic `dp600-acceptance.xlsx` fixture:

1. governed CSV preview restored `% → 1` and `MPa → Pa` mapping;
2. governed XLSX preview selected `Tensile Data`, approved an immutable Profile and created raw plus
   normalized SI Dataset revisions for 12 rows;
3. the canonical adapter created `cmp.test-data` revision 2 with 12 points and exact original/
   normalized unit semantics;
4. Process preserved the source and produced `12 → 12 → 6 → 101` points;
5. Fit compared Swift/Ghosh/Hockett–Sherby/Voce and exposed response, residual and unobserved
   extrapolation. Best relative RMSE was 0.177%;
6. Export selected the new reviewed Processing Output, required extrapolation acknowledgement,
   created Material Model IR and Neutral Material revisions, then required explicit mapping review;
7. Abaqus `*MATERIAL/*DENSITY/*ELASTIC/*PLASTIC` and OpenRadioss
   `#RADIOSS /UNIT/1 /MAT/LAW36 /FUNCT` native previews were downloaded;
8. Materials search then reported four cards for DP780, proving Library discovery of the new cards.

The complete path used 24 primary/navigation activations, excluding mapping form values and file
selection. Four of those are the top-level `Data | Process | Fit | Export` transitions. The longer
count reflects explicit immutable import, unit, extrapolation and solver-approximation decisions.

Downloaded acceptance artifacts:

- `METAL_REFERENCE-a40ab3e5-0c31-4c00-87ef-d0ff8b4cbcf3.inp` — 4393 bytes.
- `METAL_REFERENCE-b618a046-f7ac-40a2-83db-6a34b24224c0.rad` — 5074 bytes.

The canonical JSON path was separately server-validated: 3 points, one condition, strain `% → 1`,
stress `MPa → Pa`, and one explicit missing value in each channel. JSON is therefore a first-class
acceptance input, not an omitted documentation-only format.

## Screenshots

### Before

- `docs/17-evidence/images/ux-layout-review/rejected-materials-1440x900.png`
- `docs/17-evidence/images/ux-layout-review/rejected-modeling-1440x900.png`

### Reference comparisons and approved masks

- `docs/17-evidence/images/ux-layout-review/materials-reference-comparison.png`
- `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`
- `docs/17-evidence/images/ux-layout-review/card-reference-comparison.png`

### Live after

- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1366x768.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1440x900.png`
- `docs/17-evidence/images/desktop-engineering-ui/dui-02/materials-results-1920x1080.png`
- `docs/17-evidence/images/ux-redesign-v2/final-browse-tree-1366x768.png`
- `docs/17-evidence/images/ux-redesign-v2/final-modeling-fit-1366x768.png`
- `docs/17-evidence/images/ux-redesign-v2/final-modeling-fit-1440x900.png`
- `docs/17-evidence/images/ux-redesign-v2/final-modeling-fit-1920x1080.png`

## Verification

- Frontend: 36 files / 92 tests after the final full-suite rerun; TypeScript/Vite production build
  and bundle budgets passed (entry 247051 B, largest lazy Modeling chunk 110470 B, governed import
  chunk 14000 B).
- Backend: 858 collected, **782 passed / 76 expected PostgreSQL skips**; the new OOXML regression
  accepts both relative and legal absolute worksheet relationship targets and still rejects unsafe
  backslash/parent traversal.
- Isolated PostgreSQL: 76 selected integration tests run against the dedicated tmpfs service.
- Accessibility/browser: named controls, semantic table/tree/tab roles, visible roving Tree focus,
  Arrow navigation, Tree-local search and zero page-level horizontal overflow were exercised.
- Clean demo: a separately named Docker project with new PostgreSQL/object volumes runs migration,
  synthetic seed and `verify_full_demo.py`; shared acceptance data is not deleted to fake a clean run.

## Remaining limits

- The local acceptance DB now contains additional immutable synthetic revisions. The isolated clean
  demo, not that mutated DB, is authoritative for seed reproducibility.
- The checked screenshots exercise the metal reference path. Polymer and elastomer engines retain
  their existing T-89/T-90 browser evidence but were not recaptured at all three desktop widths.
- Scenario D is deliberately not reduced to a one-click export; explicit unit/mapping and
  approximation acknowledgements are domain safety gates.
- All demonstrated artifacts remain `reference/non-production`; this report does not approve a
  production constitutive model, validation threshold or native solver qualification.
