# Implementation Status

Date: `2026-07-26`
Foundation version: `0.32.0`

## UXC-06C1 stateless exact target preview implemented (2026-07-26)

Exporting now reads one exact governed Processing Output and its exact Neutral/embedded Material
Model IR relation through narrow Processing/Modeling application ports under `EXPORT_READ`. Missing,
restricted, cross-scope, cross-classification, unrelated, or stale relations fail closed without
distinguishing their source. The preview endpoint produces deterministic mapping/native/preview
SHA-256 identities and writes no Solver Card, Artifact, receipt, Activity, or session delivery pin.

Normal Modeling exposes only the two declared reference/non-production target tuples after every
current E-01–04 pin plus session IR/Neutral pin is present. C2 delivery remains unavailable; an
approximation acknowledgement identity is Evidence-only C2 input, never a C1 acknowledgement.

## UXC-03B curve/specimen rail density correction implemented (2026-07-26)

Process and Fit now use one compact Test Data tree row per exact specimen revision. Calculation
inclusion remains an explicit checkbox that dispatches `CHANGE_SELECTION`; browser-local plot
visibility uses a separate accessible eye control and does not invalidate immutable or downstream
state. The generic `Curve NN` fallback and repeated visible `Hide`/`Show` row are removed.

Data, Validate and Review/Release do not expose the editable rail. Export removes the navigator and
divider entirely, reclaims the graph/evidence width, fail-closes any persisted replicate view to the
pipeline response, and exposes neither alignment nor Mean & band controls. Current Process, Fit and
Export evidence covers 1366×768, 1440×900 and 1920×1080. Full web tests, build/type/bundle gates,
documentation gates and one bounded independent re-review pass.

## UXC-06B exact Export source provenance implemented (2026-07-26)

Governed local-file Test Data registration now carries exact Material, Material State and Test Run
revision references. The server validates the complete Test Run→Specimen→State→Material relation
through narrow Catalog/Testing application-service calls under the same authorization and
classification boundary. The verified projection is part of immutable Canonical Test Data revision
content and its hash, while the canonical scientific JSON Artifact remains byte-compatible.

Common Processing Output preflight copies that projection only from the exact Test Data revision
into immutable Output content, API response and Artifact. Nullable migration columns preserve
historical and JSON-only revisions as explicit missing proof without inference or backfill. Export
reports matching proof as current and mismatches as stale, but still reports the independent
ephemeral target-preview producer as not supported. Preview, Deliver, receipt, Activity and Material
CAE Card writes remain UXC-06C scope.

## UXC-05 governed validation boundary implemented (2026-07-26)

Normal Modeling now has a session-bound validation surface for the existing synthetic reference
contracts. The current selection must match server calibration-candidate evidence and the session-pinned
Material Model IR and OpenRadioss Solver Card revisions before a user can select exact Template and
Dataset Selection revisions and create one Validation Plan. A same-State model is never substituted;
common Processing Output candidates without a compatible adapter are explicitly `Not supported`. Fit
evidence remains visibly separate from the returned Validation Result. The workbench has no
latest/first-item fallback and preserves invalidation history when inputs change.

The repository does not yet expose an immutable candidate-package producer or complete release-policy
input for this session. Therefore Submit, Request changes, Approve and Release are distinct, explicit
`Not configured`/`Not run` states rather than fabricated SHA-256 values or a manual-ID normal path.
Exact candidate/result/card context can be sent to Activity and the governed reference harness. This is
a bounded policy boundary, not approval or release completion.

## UXC-04 explicit Fit decision and model identity implemented (2026-07-26)

The bounded `agent/uxc-04-fit-decision-identity` branch separates a calculated recommendation,
explicit engineer selection, immutable saved result and downstream model/export evidence. Selection
starts null. Metal exposes four calculated single-law rows plus the exact calculated preview blend;
changing preview laws or ratio requires recalculation, and the graph says `Preview` until an
engineer explicitly selects a row. Polymer permits only the actual server-produced term identity and
measured range, with no requested-policy or `0..1` fallback.

The Processing Output stores a typed Fit Decision snapshot after server recomputation and identity,
range, metric, parameter and bound validation. The exact selected identity and reason then project as
descriptive provenance through the existing synthetic reference model/Neutral paths. Export
eligibility requires the session's exact selected output and the typed snapshot; upstream changes
invalidate downstream current pointers without mutating immutable revisions. Current live evidence
covers 26 screenshots at 1366×768, 1440×900 and 1920×1080. The bounded reviewer found and verified
fixes for curve identity, saved-current invalidation, preview reselection and parameter completeness;
final completion remains gated on CI and PR merge.

## DUI-06 Fit and Export decision workflow implemented (2026-07-24)

The bounded `codex/dui-06-fit-export` branch connects the existing synthetic reference Fit and
solver-delivery contracts. Fit now compares candidate status, error, applicability and warnings in
one table, retains response/residual/tangent views and requires a selected candidate plus engineering
reason before appending an immutable Processing Output. The browser session pins that output's exact
identity and revision.

Export carries the reviewed decision into the existing Processing Output → Material Model IR →
Neutral Material → mapping preflight → native card chain. Solver, version and SI unit system are
visible before preflight, unsupported mappings remain blocked, approximation acknowledgement is
unchanged, and the generated card links to the Material's CAE Cards view. No production equation,
optimizer, solver policy or threshold was selected. Live acceptance, viewport measurements,
reference scoring, screenshots and regressions are recorded in
`docs/17-evidence/reports/dui-06-fit-export-decision.md`.

## DUI-03 contextual solver-card delivery implemented (2026-07-23)

GitHub issue #117 now has a bounded Material-to-card delivery slice on
`codex/dui-03-contextual-solver-card-delivery`. Selected Material context, Material Detail and CAE
Cards use the exact card mapping report to choose Download, Preview, Create card or Start Modeling.
Exact/transformed mappings download without confirmation; approximated/ignored states require one
adjacent acknowledgement; unsupported fields remain named and blocked.

The native ASCII preview is a flat two-pane text/property workspace. Card creation reuses the
existing exact Neutral Material preflight and synthetic non-production exporters. Preview/download
activity keeps exact Material and card revision IDs in browser-local Activity. No backend, database,
worker, OpenAPI or domain schema changed. `FR-IR-005`, `FR-EXP-001`, `FR-EXP-002`,
`FR-UX-001/003/006/009`, `ADR-004`, `ADR-008` and `ADR-0034` are linked in the evidence report at
`docs/17-evidence/reports/dui-03-contextual-solver-card-delivery.md`.

## Search-first reference-layout implementation accepted (2026-07-21)

The T-85~T-93 engine and functional browser evidence remain valid, but their visual acceptance is
reopened. The 1440 px Modeling screen gave the actual graph only 743 px (55.7% of its workspace),
kept a permanent third inspector column, oversized/truncated curve rows, and stacked boxed bars above
the plot. The Materials entry did not present its governed hierarchy as a normal-density continuous
explorer. Those results do not reproduce the design grammar visible in the directly opened Granta MI,
Material Data Center, and Material Modeler references.

The responsive prototypes, structural similarity report, and product-owner approval defined by
the current visual acceptance matrix are complete at commit `40726f6`. T-95–T-97 have now applied the
same topology, dominant-area, density, surface/divider, continuity and primary-action gates to the
live React application.

The approved follow-up
review replaced Modeling's multi-line source-ID curve blocks with 26 px plain-text tree rows and
added a fixed Tree-local search, retained ancestor path, independent node scroll, keyboard movement,
and Browse/Filters/Subsets modes to Materials. The large-volume 10,000-record fixture now renders
fewer than 150 virtualized `treeitem` nodes in the live component. The server-backed Tree retains
Database/Profile/Table/Folder ancestors.

The accepted production implementation uses the full application width, `Materials | Modeling | Activity`,
compact 20 px workspace titles, 14 px data text, and divider-led surfaces. At 1440×900 the live
Materials shell measures 1,376 px wide with 264 px filters, 830 px results, and 280 px selected
context. At 1366×768 the context is closed and the result region receives the remaining width. This
screen retains the actual governed Tree, typed search and saved Subsets instead of replacing them
with Material-family facets.

Modeling is `Data | Process | Fit | Export` and uses a 190.1 px curve/process tree plus a 1,186 px
fluid graph region at 1440×900; its actual SVG is 1,161.6 px/84.4% of workspace versus the rejected
743 px graph. The current-step inspector is a 124 px horizontal ribbon, never a permanent third
column. JSON, CSV and XLSX were exercised through the real canonical/governed import engines and then
Process/Fit/IR/Neutral/Abaqus/OpenRadioss and Material Library discovery.

The final T-97 evidence records 1366/1440/1920 DOM bounds, every local reference image's applied
interaction principle, 95–99/100 structural scores, Tree keyboard/search behavior, native card
downloads, frontend/backend/PostgreSQL regression and an isolated clean Docker seed/verifier. See
`docs/17-evidence/reports/t97-reference-similarity-final.md`.

## Product experience correction (T-84)

The T-79~T-81 work connected real calculation, Neutral Material and exporter engines, but its
completion reports again treated connected technical controls as Material Modeler-level usability.
The live `/modeling` review rejected that conclusion: the initial graph was blank before the latest
checkpoint, the page is a long form stack, graph interaction is minimal, and family workflows do
not yet provide the direct manipulation described by the public Material Modeler tutorials.

The authoritative corrective plan is
the current desktop engineering UI backlog.
T-79~T-81 remain valid **engine-integration evidence**, not accepted product GUI completion. The
validated branch checkpoints `3b5c11c` and `be3442d` preserve that work while T-84~T-93 replace the
interaction layer incrementally.

## Earlier product experience correction (T-74)

The previous T-73 statement confused bounded engineering evidence with an accepted product
experience. The repository has reusable database, revision, calculation and export foundations, but
the current web shell is **not** a completed Granta/Material Data Center-like Material Information
System or Material Modeler-like cohesive workbench. T-74 withdraws that product-completion claim and
starts the product-facing rebuild defined by ADR-0034 and the product experience specification.

| Product capability | Actual current state | Next Task |
| --- | --- | --- |
| Administrator-defined Table/Attribute/Layout/Subset/Link Type | T-92 accepts the guided Database design surface for migration-free typed configuration and exact Link Types | T-93 clean product acceptance |
| Catalog record datasheet/search/facet/compare | T-91/T-92 accept the three-pane Layout Datasheet, typed facets/ranges, saved Subset and Layout comparison | T-93 clean product acceptance |
| Catalog and Material Workflow Explorers | T-91 accepts automatic nested demo entry, Catalog/Workflow projection, exact linked navigation, keyboard disclosure and session restoration | T-93 clean product acceptance |
| Arbitrary typed exact-revision record links | T-51 implemented: administrator Link Type, cardinality, forward/reverse navigation | Production link taxonomy (outside v3) |
| Canonical Test Data JSON/JSON+ZIP | T-52 implemented: validate/import/revise/exact export, governed CSV/TSV/XLSX adapter and deterministic checksum package | Production importer qualification (outside v3) |
| General Mapping Profile and Processing Workbench | T-86~T-90 accept all three family paths: compact workbench, exact curve selection, guided processing, response/residual comparison, immutable Neutral review and two native card previews/downloads. | T-92 Recipe/Batch polish |
| Saved Recipe library/general batch execution | T-92 accepts published Recipe auto-restore, lifecycle/exact revision, clone/revise/publish and family-filtered member-level Batch monitor | T-93 clean product acceptance |
| Metal/Polymer/Elastomer modeling | Metal is accepted through T-88, Polymer relaxation/DMA through T-89, and Elastomer multi-mode/holdout/four-family/Prony/card through T-90. All are reference/non-production models; actual solver correlation remains excluded. | T-93 clean product acceptance |
| Neutral Material exchange JSON | T-63 implements three closed typed families, exact source-kind verification, canonical round-trip, PostgreSQL projections and connected JSON download controls; T-65 verifies exact download | Production material qualification (outside v3) |
| Abaqus/OpenRadioss native cards | T-64 regenerates bounded metal, polymer and elastomer cards from exact Neutral revisions with explicit unsupported/approximation states; T-65 Playwright verifies exact Abaqus/OpenRadioss native downloads | Actual solver execution (excluded) |
| Canonical JSON Bulk Package | T-58 implemented: exact Test/Profile/Recipe/Neutral/report/card sources in deterministic checksum-verifiable JSON+ZIP | Production package qualification (outside v3) |
| Administrator/User feature grants | T-59 implemented: typed assignments, five explicit feature grants, effective-access/API/UI and legacy-role projection | Production identity integration (outside v3) |
| Clean guided product demo | T-93 accepts clean-volume migration/seed, cohesive Dashboard/Database/three-family Modeling/Card browser journeys and full regression evidence | Production material/solver qualification (outside reference goal) |

The [product capability map](../00-research/product-capability-map.md) is the authoritative status
matrix. T-49 through T-73 remain valid engineering evidence only for their bounded contracts. They
must not be read as product-experience completion.

## Product rebuild in progress

- `T-85` (`completed; graph/session foundation accepted`): the interrupted plot work was preserved
  and extracted into a reusable `EngineeringCurvePlot`. Each series retains its own x-array, so raw,
  resampled and extrapolated curves with different point counts are not joined against the wrong grid.
  The live plot now has quantity/unit axes, engineering-scaled ticks, crosshair coordinates, zoom,
  pan, reset and interactive visibility. The normal curve rail filters by declared channel quantity
  semantics and test method instead of Material name/grade heuristics. A compact engineering header
  and collapsed method library move the persistent plot and task inspector into the 1440×900 first
  viewport. Focused Vitest, production build/bundle budgets and a live Docker/PostgreSQL browser
  interaction passed. Evidence is in `docs/17-evidence/reports/t85-engineering-modeling-shell.md`.
  A later checkpoint added graph range/point selection, explicit Recipe-draft Apply, cancellable
  300 ms previews and exact Datasheet/Test/recent-session restoration. Supplemental content now uses
  progressive disclosure and the live 1440×900 surface keeps curve/step rail, graph and task inspector
  visible together. T-85 is complete; family-specific T-86~T-90 and product acceptance remain open.
  The Dashboard audit also found that a marketing-style hero and three demo cards did not explain the
  two core jobs clearly enough. T-85 now owns its replacement with an explicit Material Database lane
  and Material Modeling lane; recent work and reference workflows remain supporting content rather
  than the product definition.

- `T-86` (`completed`): the Metal Prepare workspace provides exact curve include/exclude, guided crop,
  scale/shift, resampling and three smoothing methods; five Elastic Modulus methods; graph-selected elastic,
  proof and hardening ranges; a necking point applied to downstream true/plastic Workup; and a server-calculated
  replicate mean/95% confidence band in the primary plot. Three distinct synthetic DP780 Test JSON revisions
  make this path demonstrable in a clean seed. Evidence is in
  `docs/17-evidence/reports/t86-metal-prepare-direct-manipulation.md`. T-87 subsequently completed the
  fit/extrapolation comparison surface.

- `T-87` (`completed`): the Metal Fit/Extrapolate stage now compares the four public hardening
  equations against the exact observed plastic workup in one persistent graph. Stress response,
  predicted-minus-observed residual and tangent-modulus views use the server-evaluated candidate
  series; relative RMSE, fitted parameters and bounds remain visible as numerical evidence. The
  selected blend changes through primary/secondary and ratio controls, while the unobserved domain
  is shaded and the selected extension is dashed. Fit range, bounded extension and the required
  engineering selection reason remain deterministic Recipe options. Evidence is in
  `docs/17-evidence/reports/t87-metal-fit-extrapolation.md`. T-88 subsequently completed cohesive
  Neutral/Card delivery.

- `T-89` (`completed`): Polymer Material Modeling now has separate relaxation and DMA flows.
  Relaxation supplies log-time Prony comparison and WLF/Arrhenius master-curve evidence; DMA jointly
  fits measured storage/loss modulus with one Prony set and presents response/residual/BIC/terms on a
  log-frequency graph. Exact published Recipe/Batch Outputs promote to IR and Neutral JSON and create
  both Abaqus `TIME=PRONY` and acknowledged OpenRadioss `/VISC/LPRONY` cards. The Card task follows the
  selected Test Data revision instead of reopening an unrelated model. Live PostgreSQL/browser proof
  is in `docs/17-evidence/reports/t89-polymer-viscoelastic-workbench.md`. T-90 subsequently accepted
  the Elastomer multi-mode workbench.

- `T-90` (`completed`): Elastomer Fit restores the saved exact Plan, Dataset roles/modes/weights,
  reviewed Run and selected family diagnostics without a normal-path UUID field. A vertical family
  rail and persistent response/residual plot share the first 1440×900 viewport and distinguish three
  calibration modes from an explicit holdout. The current model's ordered Prony overlay is visible,
  and the same session previews Abaqus Ogden+Prony and OpenRadioss LAW62 ASCII. Approximation/ignored
  mapping now requires explicit review before new card generation. Evidence is in
  `docs/17-evidence/reports/t90-elastomer-multimode-workbench.md`. T-91 now owns Database parity.

- `T-91` (`completed`): Material Database now opens on an actual governed demo Datasheet instead of
  an empty center pane. The persistent left pane exposes the realistic Database/Profile/Table/Folder/
  Record hierarchy and switches to an exact revision Workflow graph without duplicating records. The
  middle pane renders configured Layout values and domain-specific Test/Model/Card views; the context
  pane follows forward/reverse links or immutable revision history. Tree disclosure supports arrow,
  Home and End keys, and the last exact revision is restored within the browser session. Live Docker/
  PostgreSQL screenshots are in `docs/17-evidence/reports/t91-material-database-parity.md`. T-92 now owns
  search, guided administration and Recipe/Batch polish.

- `T-92` (`completed`): the current family's reviewed published Processing Recipe is restored by
  default instead of showing an unrelated empty draft. Recipe Library exposes lifecycle, exact revision,
  clone, append and publish actions. Batch Monitor is filtered to compatible family Recipes, shows
  member-level compatibility/output points and summarizes successful attempts while retaining failed-only
  retry. The existing typed search/facet/range/Subset/Layout comparison and guided Table/Attribute/Layout/
  Link Type Administration were re-audited in the live Docker/PostgreSQL product. Evidence is in
  `docs/17-evidence/reports/t92-search-admin-recipe-batch.md`. T-93 now owns clean product acceptance.

- `T-93` (`completed for the bounded reference product`): Docker/PostgreSQL/object volumes were
  removed and the complete service was rebuilt, migrated and seeded from zero. The verifier reproduced
  the exact Catalog workflow, three-family processing/modeling evidence, Neutral JSON, native Abaqus/
  OpenRadioss cards and bulk bundles. Live browser acceptance covered Dashboard, the GRANTA-like
  Database Datasheet/link projections, Metal, Polymer and Elastomer graphs and their Card tasks. A stale
  session revision discovered during clean acceptance now falls back to a valid newly seeded record.
  Full Python, actual PostgreSQL and frontend regressions passed. Evidence is in
  `docs/17-evidence/reports/t93-clean-product-acceptance.md`. Reference model status remains explicit;
  real solver correlation and company material qualification remain outside this acceptance.

- `T-88` (`completed`): **Card** is now a first-class task in the Material Modeling shell rather than
  a legacy drawer below the graph. It pins friendly Material/State and exact reviewed Output/IR/Neutral
  evidence, exposes solver/version/law/card identity, displays all six mapping meanings and blocks silent
  approximation or unsupported generation. After creation the result prioritizes the line-oriented native
  ASCII preview and `.inp`/`.rad` plus mapping JSON downloads while keeping evidence reopenable. Live
  Docker/PostgreSQL journeys generated and downloaded both Abaqus and OpenRadioss cards. Evidence is in
  `docs/17-evidence/reports/t88-neutral-card-delivery.md`. T-89 now owns the Polymer relaxation/DMA workbench.

- `T-81` (`engine integration verified; product UX rejected`): all three Material Modeling tracks now finish in one
  four-state reviewed-delivery panel: exact evidence, canonical Neutral JSON, explicit solver
  mapping and native card. It summarizes the selected model/Processing Output, exact inputs, curve
  stages, selection reason and applicability; downloads the Neutral JSON; requires review of every
  six-state Abaqus/OpenRadioss mapping; then previews/downloads the immutable ASCII card and mapping
  report. Exact Material and bulk-package navigation no longer requires copied UUIDs. Live Docker
  journeys restored the existing DP780 and polymer Neutral revisions, reproduced an elastomer
  four-family/eight-start fit and promoted its selected Ogden family, and created an acknowledged
  DP780 Abaqus card. The re-entry journey also found and fixed duplicate Neutral promotion in the
  metal UI. Evidence is in `docs/17-evidence/reports/t81-reviewed-delivery.md`. TypeScript, production
  build, bundle budgets and all 69 frontend tests pass. This proves the retained delivery engine,
  not Material Modeler-level usability. T-84~T-93 replace and re-accept the product interaction.

- `T-80` (`engine integration verified; product UX partial`): `/modeling` exposes explicit Metal elastoplastic,
  Polymer viscoelastic and Elastomer hyper-viscoelastic tracks. A family switch resets the prior
  Test Data choice, loads the matching Material/State/Property revision and changes the available
  method contract. Step options, versioned Recipe authoring and exact Batch preflight/execution/retry
  are one graph-adjacent inspector. Live Docker journeys calculated the four metal hardening
  candidates, polymer log-time/Prony processing and an exact four-curve elastomer Plan with four
  hyperelastic families, eight multistart candidates and fitted/residual diagnostics. Evidence and
  current screenshots are in `docs/17-evidence/reports/t80-family-modeling-tracks.md`. All 69 frontend
  tests, 775 default Python tests, 76 isolated PostgreSQL tests and all static/contract/document/
  bundle gates passed. T-81 subsequently connected the reviewed Neutral/Card engine step; its
  product interaction remains subject to T-88~T-90 acceptance.

- `T-79` (`engine integration verified; product UX partial`): `/modeling` presents Import → Map → Prepare → Fit →
  Extrapolate → Card as one product flow. The central work area keeps exact Dataset/curve selection,
  ordered Recipe stages, the real server-calculated curve/candidate overlay and the selected stage's
  structured options together. Mapping and Recipe JSON plus full numerical parameter evidence remain
  available in collapsed advanced sections instead of dominating the normal workflow. Preview stays
  ephemeral; only the existing explicit server commit creates a revisioned Processing Output. A live
  DP780 Test JSON and published Recipe produced four hardening candidates plus a selected combination
  with no browser console errors. Evidence is recorded in
  `docs/17-evidence/reports/t79-material-modeling-workspace.md`. The CI command body passed 775 default
  Python tests, 68 frontend tests, Ruff, mypy, architecture, contract/OpenAPI, user-guide and bundle
  gates; the isolated PostgreSQL marker suite passed all 76 tests. T-80 subsequently connected the
  family engines and Recipe/Batch controls; T-85~T-92 own clone-level interaction acceptance.

- `T-78` (`implemented and verified`): product Administration now has Overview, Database design and
  Users & access navigation. The database surface manages Tables, nine typed Attribute kinds,
  Layouts, Subsets and exact source/target Table-revision Link Types. The access surface exposes
  only Administrator/User, a user/team name and five readable capabilities; token/API, principal,
  issuer, classification-policy and legacy compatibility vocabulary remain internal. Existing
  resource/action/scope enforcement is retained as the granular extension point. Live Docker
  screenshots and tests are recorded in `docs/17-evidence/reports/t78-product-administration.md`.
  The complete CI command body passed 775 default Python tests, 68 frontend tests and all static,
  contract, document and bundle gates; all 76 isolated PostgreSQL tests passed separately.

- `T-77` (`implemented and verified`): `/database` now opens the same exact Record revision from the
  Contents Tree or typed search results and renders administrator-defined Layout sections,
  original/normalized numeric units and quantity semantics. Users can filter discrete facets and
  normalized numeric ranges and compare selected Records side by side in Layout order. Properties,
  curve Artifact provenance, exact solver cards and forward/reverse links remain in the same
  revision context. The clean demo creates eight typed Attributes plus the `Material overview`
  Layout without a database migration and repeat seeding keeps the same revision. Live screenshots
  and the explicit decision to implement semantic curve overlay in T-79 are recorded in
  `docs/17-evidence/reports/t77-material-datasheet-search.md`. The complete CI command body passed 775
  default Python tests, 65 frontend tests and all static/contract/document/bundle gates; all 76
  environment-gated PostgreSQL tests passed separately against the isolated Docker database.

- `T-76` (`implemented and verified`): `/database` now presents a three-pane product workspace with
  Database/Profile/Table/nested-Folder/Record lazy Contents Tree, an exact-revision Material → State
  → Test Data → Processing Output → Material Model IR → Neutral Material → Abaqus/OpenRadioss
  Workflow Tree and direct Related Data. Governed nodes open the existing exact workbench route.
  Migration 082 separates the stable Catalog identity-to-domain mapping from append-only exact
  Record revision bindings, and a Record Link can append a revision that advances exact endpoint
  pins without rewriting history. Live PostgreSQL seed/reseed retained all 8 Record heads, the
  graph returned 8 nodes and 7 links, and browser evidence is recorded in
  `docs/17-evidence/reports/t76-material-database-tree.md`. T-77 subsequently completed Layout
  Datasheet, facets and comparison; semantic curve overlay remains T-79. Verification passed the
  official CI command body with 775 Python and
  64 frontend tests plus all static/document/bundle gates; the 76 isolated PostgreSQL tests also
  passed against the Docker test database.

- `T-75` (`implemented and verified`): the web application now establishes the explicitly enabled
  local demo session in the background and shows only a normal sign-in boundary when that session
  is unavailable. API address, bearer-token and connection controls were removed from the product
  UI. The primary shell is Dashboard, Material Database, Material Modeling, Jobs & Reviews and
  Administration; the Dashboard provides global material search, three task entry points and the
  three realistic synthetic material families from the live catalog. Frontend tests pass 62/62,
  the TypeScript/Vite/bundle build passes, and Docker browser evidence is recorded in
  `docs/17-evidence/reports/t75-product-session-shell.md`. T-76 subsequently completed the hierarchical
  Contents/Workflow Tree and T-77 subsequently completed Datasheet/search/compare. Graph-centered
  Modeling is now graph-centered through T-79; family-aware controls and final Neutral/Card delivery
  remain T-80 through T-81.

- `T-74` (`implemented and verified`): withdraw the v3 product-completion claim, establish the
  product experience contract and create the T-75~T-83 replacement sequence. Existing engine
  evidence remains intact. Full CI passed 774 Python and 62 frontend tests plus the static type,
  architecture, contract, OpenAPI, user-guide and bundle gates.

## Completed engineering foundations

- `T-73` (superseded product conclusion): its DB/API/test evidence remains useful, but its product
  completion conclusion is withdrawn by T-74 because the browser acceptance scope was too narrow.

- `T-72`: the hyperelastic Modeling Workbench now lists saved Calibration Plans for the current
  Material State and baseline model. Users can execute an exact immutable Plan revision or reload
  its Dataset roles, test modes and weights and append a new revision through compare-and-swap.
  The existing typed Plan identity/revision/member tables are reused without a migration. API,
  React and live Docker/browser checks pass. The isolated PostgreSQL suite passed all 76 tests and
  full CI passed 774 Python tests, 62 frontend tests, static typing, architecture, contracts,
  OpenAPI compatibility, user-guide evidence and the production bundle gate.

- `T-71`: Catalog Explorer now searches record name, key, description and text Attributes without
  leaving the tree/workflow surface. A saved Subset applies its immutable filter definition and
  opens each exact current Record revision directly in the Workflow graph. The clean demo seeds a
  reusable `DP780 workflow records` Subset and the protected verifier checks it. Reseeding also now
  selects the direct Dataset-derived tabulated-plasticity model by exact Dataset revision instead
  of relying on arbitrary model list order when a processed IR is present. Protected
  Docker/PostgreSQL verification passed, followed by full CI with 774 Python tests and 62 frontend
  tests; the default Python runner reported 76 environment-gated PostgreSQL tests as skipped after
  they had been exercised through the protected Docker path.

- `T-70`: the existing published metal Recipe/Batch path now retains its exact execution origin
  through processed tabulated-plasticity IR `1.3.0`, canonical Neutral JSON, Abaqus/OpenRadioss
  cards and the 13-component Bulk package. Migration 081 adds typed Recipe/Batch/Member/Attempt
  columns and deferred validation against the successful Attempt and exact Output revision. The
  metal workbench displays the Recipe revision and Batch attempt with a deep link to the monitor;
  historical direct Output IR `1.2.0` remains readable. Clean PostgreSQL verification passed all
  76 environment-gated tests; the full CI script passed 773 Python tests (76 PostgreSQL tests
  separately exercised), 61 frontend tests, contracts, architecture, documentation and production
  bundle gates.

- `T-69`: saved published polymer
  Recipes now execute through the common Batch engine and their successful exact Output revision is
  promoted without copying or refitting. Migration 080 stores the exact Recipe digest and
  Batch/Member/Attempt identifiers beside existing Output/Test/Profile evidence and validates that
  the Attempt succeeded with that Output. IR schema `1.3.0` and Neutral JSON preserve the exact
  Recipe revision; the polymer workbench displays the execution evidence and links back to the
  Recipe Library/Batch Monitor. Clean demo packaging includes the Recipe-to-Abaqus/OpenRadioss
  transfer set. Historical direct Outputs remain compatible as schema `1.2.0`.

- `T-68`: an exact generalized-Maxwell Neutral revision can now generate an OpenRadioss 2025
  `/MAT/LAW1` + `/VISC/LPRONY` reference fragment only when bulk relaxation is uncharacterized,
  every `k_ratio` is zero, and `0.49 <= nu < 0.5`. Form 2 and `flag_visc=2` preserve instantaneous
  rigidity and shear-only ratios. The mapping report marks the nearly-incompressible interpretation
  and required external solid `/PROP I_smstr=10 or 12` as acknowledged approximations. Compressible
  or bulk-relaxing records remain `unsupported`, and no LAW62 conversion occurs. The existing typed
  migration 077 card/mapping/term projection stores the new target without a schema change. The
  returning polymer workbench discovers its exact existing Neutral revision, avoiding a duplicate
  promotion. Clean Compose seed/verifier produced and checksum-verified both Abaqus and OpenRadioss
  cards; current browser evidence is in `docs/17-evidence/reports/t68-openradioss-lprony.md`.

- `T-67`: the reusable common Processing Recipe can now promote an exact saved
  `polymer.prony_fit_compare` Output into a typed one-to-ten-term generalized-Maxwell IR. The server
  re-exports and verifies the immutable Output Artifact rather than trusting coefficients from the
  browser, pins the canonical Test Data and Mapping Profile revisions, and stores selected-term,
  BIC/RMSE and catalog-versus-fitted instantaneous shear-modulus review evidence. A user enters a
  case-specific mismatch limit and explicitly reviews the evidence before promotion. The same
  workbench creates a canonical Neutral Material JSON and uses the shared mapping flow to generate
  Abaqus `*VISCOELASTIC`; T-68 later adds a separate conditional OpenRadioss LPRONY path. Migration 079 adds the
  closed typed evidence projection and ten-term constraints. Clean Compose seeding and the protected
  verifier reproduced Output `2cfc3108-3618-444c-96bc-c35329291446`, IR
  `38ee5225-f451-40ce-94f9-557cc99ce1b4`, Neutral
  `bdbc87ce-8024-4d82-a871-efa3efa40028` and Abaqus card
  `12047cb3-e1ae-4dea-b58d-6bc1ea124fb1` from public synthetic data.

- `T-66`: exact governed domain revisions can now resolve back to their configurable Catalog Record
  revision through the protected `catalog.read` boundary. Material, canonical Test JSON, common
  Processing Output and Neutral/Card screens show an **Exact linked data** panel with the depth-5
  Workflow graph and Explorer deep link. Explorer nodes still open their pinned workbench paths;
  starting at the clean Test JSON now exposes Material, Processing Output, selected IR, Neutral JSON
  and both native cards in one graph. The direct-link list no longer mislabels non-incident graph
  edges. API, PostgreSQL, React and Playwright regressions cover the reverse journey.

- `T-65`: clean PostgreSQL now seeds a canonical twelve-point tensile Test JSON, exact Mapping
  Profile, published three-step Processing Recipe, successful Batch Output, selected tabulated-
  plasticity IR, canonical Neutral JSON and exact Abaqus/OpenRadioss cards. An eight-node
  revision-pinned Workflow Explorer graph connects those governed objects. Migration 078 lets the
  scoped binding validator inspect cross-module targets without exposing their rows to callers.
  The protected verifier and Playwright download both native cards and the nine-component Bulk ZIP,
  recompute SHA-256 values and validate the archive controls. The current screenshot and walkthrough
  are recorded under `docs/17-evidence` and `docs/user-guide`. Actual solver execution remains excluded.

- `T-64`: one exact Neutral Material revision now drives the shared solver mapping/report/card API
  and connected workbench UI. Metal regenerates Abaqus `*PLASTIC` and OpenRadioss LAW36; polymer
  regenerates Abaqus Prony and conditionally maps ADR-0032-eligible records to OpenRadioss LPRONY;
  hyperelastic Prony overlays regenerate
  Abaqus cards and one-term Ogden LAW62 only. Migration 077 stores the closed model family, typed
  parameters, ordered Prony terms and every mapping state in append-only PostgreSQL projections.
  The generic card routes coexist with T-57 compatibility aliases, and T-58 bulk discovery consumes
  the same immutable card rows. Solver execution remains excluded; T-65 owns clean-seed browser
  downloads and screenshot evidence.

- `T-63`: `cmp.neutral-material` now has a closed typed union for selected metal isotropic
  tabulated plasticity, reviewed generalized-Maxwell/Prony and hyperelastic families with an exact
  optional Prony overlay. Migration 076 projects model family, selection kind, metal parameters,
  applicability and ordered Prony terms into explicit PostgreSQL columns/tables; a closed source
  discriminator verifies exact governed Dataset, canonical Test Data or shear-relaxation Dataset
  revisions. The API promotes exact selected metal and polymer IR evidence, validates/imports all
  three families, preserves canonical numeric round trips and downloads the immutable JSON. Metal
  and shear-relaxation workbenches expose the promotion/download controls. T-64 completes bounded
  family-specific native card regeneration and shared Bulk source parity.

- `T-62`: migration 075 adds an immutable, same-scope, closed-kind binding from one configurable
  Catalog Record revision to one exact governed domain revision. PostgreSQL validates each target
  against its explicit Material, State, Specimen, Test Run, Test Data, Processing Output, Material
  Model, Neutral Material, Solver Card, Neutral Solver Card or Release table and rejects stale UUIDs
  and cross-scope targets. The existing forward/reverse Record Link graph now returns this binding;
  the connected Explorer shows its kind/revision and opens the corresponding flat-route workbench.
  API, migration, React and non-bypass PostgreSQL tests cover creation, graph projection, invalid
  targets and immutable mutation rejection. T-65 remains responsible for seeding the complete graph.

- `T-60`: clean Compose now seeds three public synthetic material-family journeys through protected
  APIs. `make demo-verify` confirms the exact Material/State/Model heads and required Abaqus/
  OpenRadioss cards. Dashboard guided routes, a unified walkthrough, deterministic fixture stamp,
  live PostgreSQL/API proof and screenshot gate are connected. Solver execution remains excluded.

- `T-59`: Migration 074 adds an explicit typed product access assignment with `Administrator` or
  `User` and five boolean feature grants: schema configuration, catalog editing,
  processing/calibration, model approval and solver-card export. Assignment grants are immutable;
  changes revoke the prior row and append a new one. The authorization service maps the simple
  vocabulary back to the existing permission/RLS boundary and projects legacy role bindings for
  compatibility. `/api/v1/product-access/*` and the connected `/access` screen expose effective
  access and Administrator-only grant/revoke operations. A live Docker/PostgreSQL demo returned the
  seeded Administrator assignment and all five effective grants.

- `T-58`: Migration 073 extends the existing immutable Export Selection/Job/Bundle engine with six
  explicit typed source pairs: canonical Test Data JSON, Mapping Profile JSON, Processing Recipe
  JSON, Neutral Material JSON, Neutral solver mapping report and Neutral native card. The source
  resolver produces deterministic revision-addressed paths, validates stored Artifact/report
  digests, and never uses a generic payload. The connected Bulk Export Center displays and selects
  these representations. A live Docker/PostgreSQL run assembled a 16-component package containing
  all six kinds; all `checksums.sha256` entries and the manifest were independently verified.

- `T-57`: canonical Neutral Material revisions now drive an explicit versioned eight-entry
  Abaqus/OpenRadioss capability manifest. Migration 072 stores an immutable card identity/revision
  with a composite tenant/classification foreign key to the exact Neutral revision, typed family
  coefficients, all six mapping states, report/card hashes and native ASCII; no generic parameter
  payload is authoritative. Abaqus 2025 emits direct `*HYPERELASTIC` forms for Neo-Hookean,
  Mooney--Rivlin, Yeoh and one-term Ogden. OpenRadioss 2025 uses LAW94 for Neo-Hookean/Yeoh and
  LAW82 for Mooney--Rivlin/Ogden; exact coefficient transformations and LAW82's explicit `nu=0.495`
  approximation are visible before creation. The connected UI requires a current mapping-report
  SHA-256 and explicit acknowledgement when an approximation is present, then exposes preview,
  native `.inp`/`.rad` download and the JSON sidecar. Actual solver execution validation remains
  deliberately outside this Task.

- `T-56`: a reviewed Neo-Hookean, Mooney--Rivlin, Yeoh or one-term Ogden family Candidate can be
  promoted into a new stable Neutral Material identity and immutable revision. Migration 071 stores
  explicit typed family parameters and exact composite references to Material/State/Property,
  Plan/Run/Candidate, Mapping Profile, Dataset and canonical Artifact; no generic parameter map or
  EAV payload is authoritative. `cmp.neutral-material` `1.0.0` deterministically preserves exact
  source Artifact digests, normalized/fitted/residual curves, human selection reason, objective,
  parameter bounds, applicability and reference validation. Protected validate/import/get/download
  APIs and the connected workbench reject scope, digest, family-parameter and evidence mismatches.
  Live Docker/PostgreSQL verification restored one four-family Run, selected Ogden, created Neutral
  model r1 with four exact Dataset revisions and twelve curve stages, and exposed the exact JSON
  download. Solver-native family mapping remains T-57 and is not implied by this exchange contract.

- `T-55E` modeling kernel and connected comparison Workbench: exact uniaxial, planar and biaxial
  Dataset revisions are evaluated against public incompressible Neo-Hookean, Mooney--Rivlin, Yeoh
  and one-term Ogden equations under one normalized weighting contract. Deterministic multistart
  fitting stores one explicitly typed Candidate per family in migrations 069/070; family-specific
  parameter shapes are enforced without JSON/EAV. Per-mode objectives, calibration/holdout NRMSE,
  convergence, fitted-domain monotonicity and warnings are returned by the protected API. Every
  observed/predicted/residual point is pinned as an immutable Parquet Artifact and can be opened
  from the connected Workbench. The established Ogden--Prony selection/IR/card path remains usable.
  Selecting any of the four families into the general Neutral Material envelope is T-56; exact
  Abaqus/OpenRadioss family capability mapping is T-57, so those downstream paths are not claimed
  complete here.

- `T-55P`: the common Processing Workbench now exposes solver-neutral
  `polymer.log_time_resample` and `polymer.prony_fit_compare` methods. The latter fits an explicit
  user-selected set of one-to-ten-term generalized-Maxwell candidates with shared bounds and
  objective, stores every candidate curve plus normalized RMSE/BIC, and selects either by BIC or an
  explicit term count. A polymer relaxation Mapping Profile/Recipe template makes the path usable
  without authoring JSON from scratch. The existing exact Dataset/Selection master-curve workflow
  now supports manual, WLF, and Arrhenius shifts; migration 068 stores fitted Arrhenius activation
  energy in a typed constrained column and retains observed/predicted shift residuals. The existing
  reviewed linear-Prony IR promotion and Abaqus 2025 `*VISCOELASTIC` card remain supported. T-68
  additionally supports ADR-0032's nearly-incompressible shear-only OpenRadioss `/VISC/LPRONY`
  fragment. Linear viscoelasticity remains explicitly unsupported for OpenRadioss LAW62 rather than
  being silently converted. T-67 connects a newly committed common one-to-ten-term Output to a
  reviewed typed IR, canonical Neutral Material document and both eligible card workflows.

- `T-55M`: the metal methods run in the common Processing Workbench and published Recipe/Batch path.
  OLS, Huber robust, chord, secant and manual Young's modulus, proof stress, non-destructive necking
  candidate, explicit true/plastic conversion and Voce/Swift/Hockett--Sherby/Ghosh candidate fitting are
  versioned methods. The selected fitted curve is an immutable Output. IR family `1.2.0` pins that exact
  Output plus source Test Data and Mapping Profile revisions, candidate selection and bounded domain in
  explicit PostgreSQL columns and constraints. The Material workbench promotes it without refitting,
  then runs visible Abaqus/OpenRadioss preflight and native `.inp`/`.rad` preview/download. Live Docker/
  PostgreSQL verification used Output revision `b3644458-1799-4fbc-bdd9-48a8230fefc3`, IR revision
  `4080a694-876d-483f-8b70-89db47fa6610`, and verified both card SHA-256 values.
  Final verification: 689 general backend/contract/architecture tests passed (75 PostgreSQL-only
  tests skipped in that run), all 75 isolated PostgreSQL integration tests passed separately, and
  all 50 React tests plus the production bundle budget passed.
- `T-54`: published common Recipe revisions now execute against an immutable exact Test Data
  selection. Migration 066 stores explicit Batch, Member and append-only Attempt rows with composite
  tenant/classification foreign keys to exact Recipe, Test Data and successful Processing Output
  revisions. Preflight blocks incompatible inputs before persistence. Execution isolates members so
  successful immutable Outputs survive another member failure; retry appends attempts only for members
  whose latest attempt failed. The connected Batch Run Monitor shows exact pins, compatibility,
  derived status, attempt number, output revision or error. Live PostgreSQL verification processed two
  DP600 revisions into two outputs from Recipe r2, and browser evidence records the successful monitor.
- `T-53`: a solver/test/material-neutral method registry provides sort/duplicate policy,
  crop, scale/shift, linear resampling, moving average, Savitzky–Golay and smoothing spline. Mapping
  Profile identity/revisions and typed channel/Attribute bindings persist in explicit PostgreSQL tables;
  exact Attribute Definition revisions are pinned when used. The connected `/datasets/processing`
  workbench loads exact Test Data JSON, creates or revises reusable profiles and compares every
  server-produced stage on shared axes. Preview is deliberately not promotable. A separate commit
  reloads exact Test Data/Profile revisions, recomputes the pipeline and persists a one-revision-only
  Output plus canonical JSON Artifact; browser preview arrays are never authoritative. Multi-curve
  preview applies the same mapping/preprocessing to exact Test Data identities, retains every member,
  aligns only on the observed domain intersection without extrapolation, and exposes pointwise mean,
  median, sample SD, MAD, IQR and 95% mean CI with explicit assumptions in API and UI. Versioned
  Recipe ownership and exact batch execution are completed by T-54; Neutral Material promotion remains T-56.
- `T-52 increment 1`: `cmp.test-data` 1.0.0 now has schema plus semantic validation, a connected
  `/datasets/test-json` preview/import/list/download workflow, explicit PostgreSQL identity/revision,
  typed condition/channel rows and immutable canonical JSON/normalized Parquet Artifact pins. Exact
  revision download was verified byte-for-byte in the Docker/PostgreSQL demo. Deterministic JSON+ZIP,
  same-identity append uses a strong current-revision ETag and never overwrites prior evidence.
  Current exact revisions can be downloaded as a deterministic JSON+ZIP with manifest and detached
  checksums. The governed CSV/TSV/XLSX parser now exposes original and normalized evidence to a
  connected canonical adapter UI/API; direct JSON and CSV adapter paths produce the same canonical
  digest. Larger cross-capability package profiles remain T-58 scope.
- `T-51`: Catalog Explorer now lazily expands administrator-defined Table, nested Folder and current
  Record nodes while preserving the existing flat routes. Material Workflow Explorer projects
  arbitrary active Record Links as a bounded, cycle-safe graph; every endpoint and Link Type pins an
  exact immutable revision rather than a `latest` alias. Migration 061 adds explicit Link Type and
  Record Link identity/revision tables, composite tenant/classification/exact-revision foreign keys,
  forced RLS, immutable triggers, endpoint compatibility, duplicate and cardinality guards. Protected
  APIs and the connected Explorer UI support forward/reverse traversal, deep links, Link Type creation,
  exact target selection and append-only deactivation. Fresh PostgreSQL, API/migration/React tests and
  a live Docker browser workflow verified DP600 material r2 ↔ tensile-test r1 in both directions.
- `T-50`: configurable Folder and Record stable identities now append immutable revisions in
  migration 060. Record revisions pin the current Table, exact Folder and exact Attribute revisions;
  nine type-specific value relations preserve original/normalized number evidence, artifacts and
  exact record references without JSON/EAV authority. Protected APIs create/revise/read/history,
  execute bounded text/discrete/normalized-range search with authorized facet counts, and compare
  exact revisions. The connected **Catalog records** screen consumes Layout order, saves and applies
  Subset filters, edits datasheets, shows revision differences and creates nested Folders. Fresh
  PostgreSQL with a non-bypass role, folder-cycle guards, API/migration/React tests and live Docker
  browser evidence cover the implemented scope. Dual Explorers and arbitrary Link Types are completed
  by T-51.
- `T-49`: administrator-defined Catalog Table, typed Attribute Definition, Layout and saved Subset
  stable identities use immutable revisions in migration 059. Nine type-specific record-value
  relations replace an untyped EAV/JSON authority; number values preserve original and normalized
  value/unit plus quantity semantics, while file/curve values pin artifact digest and reference
  values pin an exact target record revision. Composite tenant/classification FKs, forced RLS,
  immutable triggers and type/unit/discrete/reference guards are active. Protected create/list/
  revise APIs require current ETags, and the connected **Catalog** schema designer creates real
  definitions without a DB migration. Focused API, fresh PostgreSQL, migration, React and user-guide
  regressions plus a live Docker/PostgreSQL/browser workflow provide the current evidence. Record
  datasheet/search/facet/compare is completed by T-50.
- `T-01`: modular-monolith repository skeleton, bounded-module namespaces, deployable API and
  worker shells, developer commands, architecture rules and regression fixtures
- `T-02`: OpenAPI/AsyncAPI baseline, JSON Schema registry, positive/negative contract examples,
  deterministic minimal client generation, compatibility detector and validation pipeline
- `T-03`: strict OIDC JWT access-token validation, user/service principal resolution, immutable
  external identity projection, request security context, `/api/v1/me`, and development test IdP
- `T-04`: conservative deny-by-default role matrix, principal/group role bindings, append/revoke
  administration, classification ABAC, reusable authorization dependency, and forced PostgreSQL RLS
- `T-05`: project-scoped append-only audit chain, DB-computed canonical SHA-256, periodic segment
  roots, atomic revision hook, tamper verification, and protected query/export/integrity API
- `T-06`: framework-free aggregate revision kernel, explicit typed-table SQLAlchemy adapter,
  PostgreSQL/Alembic immutability and tenant primitives, initial lifecycle event/projection,
  strong ETag and revision metadata contracts
- `T-07` expanded vertical: Material and Material State stable identities separated from immutable typed
  revisions; explicit SI density/Young's modulus/Poisson ratio/optional yield property columns,
  per-value source and applicability; search/detail/history/compare APIs; provenance/audit/lifecycle
  hooks; PostgreSQL composite tenant/classification FKs, indexes, and forced RLS. Typed Process
  Definition, Material Lot/Batch, and State Genealogy identities now have append-only revisions;
  genealogy revisions pin exact State, Process, and Lot revisions with role/scope/material guards,
  protected APIs, and a connected Material State UI.
- `T-39`: explicit Process Run stable identities and immutable revisions pin one exact Process
  Definition and Material State revision plus ordered consumed/produced Lot revisions. Decimal
  quantities preserve original governed units and normalized SI evidence; assessed mass, volume,
  or count balances reject dimension/tolerance mismatches, while `not_assessed` requires a reason.
  Multi-lot split/merge, current-head graph-cycle rejection, tenant/classification isolation,
  forced RLS, immutable child rows, and exact Specimen-to-source-Lot genealogy are enforced in
  PostgreSQL migration 049 and exposed through protected APIs and the Material State workbench.
  Verification passed 561 Python tests, 30 web tests, production frontend build, live PostgreSQL
  constraints/RLS and a Docker browser workflow without skips or browser console errors.
- `T-40`: governed Test Campaign, Instrument, dated Calibration, typed Test Condition Snapshot and
  one-to-one Test Run Context stable identities use immutable revisions in PostgreSQL migration
  050. Campaigns explicitly declare standard designation/edition/conformance or an approved
  deviation; common conditions use typed temperature, humidity, loading-rate, orientation and
  medium columns rather than EAV/JSON. Each Context pins the exact Test Run, Method-backed
  Campaign/Condition, Instrument and Calibration revisions. Service and deferred database guards
  reject cross-scope or mismatched sources, stale/failed calibration, overlapping usable validity
  intervals and revision mutation. Protected APIs and the connected Material State workbench show
  only calibration records valid at the historical Run time. Verification passed 568 Python tests,
  31 web tests, ruff, mypy over 480 source files, architecture/contracts, the production frontend
  build, a fresh PostgreSQL 001--050 migration and a live Docker browser workflow without skips,
  test warnings or browser console errors.
- `T-41`: governed CSV/TSV/XLSX import with immutable source Artifact, explicit `needs_input`
  Preview Report, reusable human-approved typed Profile revisions, exact terminal Import Run and
  separate raw/normalized Dataset revisions. Parser limits, locale/sheet choices, formula/macro/
  external-link rejection and force/displacement geometry requirements are explicit. Migration 051,
  protected API, connected workbench and live PostgreSQL/browser evidence are complete.
- `T-42`: a multi-member Viscoelastic Selection revision pins exact normalized shear-relaxation
  Dataset/Test Run revisions and test temperatures. An immutable Master Curve Plan selects manual
  shift factors or deterministic WLF fitting with a reference temperature. The terminal Run creates
  separate aligned, pointwise-statistics and master-curve Dataset revisions plus ordered shift
  evidence; common log-time interpolation never extrapolates. Explicit migration 052 tables,
  composite tenant keys, forced RLS, immutable/deferred guards, provenance subactivities, protected
  APIs and the connected React workbench expose individual replicates, `n`, sample bands, outlier
  status, shifted curves and the master curve. The reference slice preserves every input and does
  not claim scientific or solver qualification.
- `T-08` reference subset: explicit Specimen, reference uniaxial tensile Test Method, and Test Run
  stable identities with immutable typed revisions; a Test Run pins concrete Specimen/Test Method
  revisions, a State-specific specimen code, optional test temperature/crosshead speed, protected
  APIs, audit/provenance/lifecycle hooks, PostgreSQL tenant/classification FKs, RLS, and immutable
  tables. Campaign, instrument, standard, and production test-method variants remain separate work.
- `T-11` reference subset: an immutable header-only Detection Report is created only from a verified
  UTF-8 CSV Raw Artifact and always remains `needs_input`; a stable Import Mapping identity has
  append-only, human-confirmed typed revisions that pin the exact Detection Report/Raw source and
  mapping digest; a Processing Import Run pins the concrete Test Run and Mapping revisions before
  delegating through the Dataset public application port. Explicit PostgreSQL
  `testing.import_detection_report`, `testing.import_mapping`,
  `testing.import_mapping_revision`, and `processing.import_run` tables enforce source/digest/output
  consistency, RLS, indexes, and append-only transitions. The Material State workbench calls the
  separate detect → approve → import APIs; the bounded `reference_inline` adapter is
  non-production and not a generic production importer/plugin worker.
- `T-12` reference subset: a user-confirmed UTF-8 reference tensile CSV mapping with explicit
  engineering strain/stress columns and limited `1`/`%` and `Pa`/`kPa`/`MPa`/`GPa` units; one stable
  Dataset identity appends raw CSV and normalized SI Parquet revisions without overwriting either;
  typed channel semantics, Raw Asset/Artifact/Test Run concrete references, raw-input provenance,
  bounded curve preview, PostgreSQL constraints/RLS, protected APIs, and deterministic regression
  coverage. The T-11 synthetic header detector/mapping orchestration is now present, while generic
  production importer plugins, arbitrary channel schemas, and other test formats remain separate
  work.
- `T-19` reference subset: an immutable one-member Selection pins one normalized reference tensile
  Dataset revision; a stable Recipe with immutable typed revisions performs only inclusive observed
  engineering-strain crop; a committed Processing Run creates a typed processed Parquet Artifact
  and a separate processed Dataset identity/revision 1. It preserves raw/normalized source bytes,
  records Selection/Recipe/output revision audit facts and concrete Processing provenance, and
  provides protected API plus Material State workbench controls. Multi-input selection, resampling,
  true-strain transforms, and durable Run reconciliation remain outside this subset.
- Reference elastoplastic multi-solver vertical (`T-D03` bounded subset): one concrete normalized
  or processed tensile Dataset revision and one typed Property Set revision produce an immutable
  solver-neutral isotropic tabulated-plasticity IR. The transformation converts engineering data
  only through the first global stress maximum, retains source/pre-yield/post-necking counts and
  necking index, rejects implicit repair/smoothing, and stores the hardening curve as a verified
  Parquet Artifact. A user-approved constant-stress extension remains visibly `approximated`.
  Explicit OpenRadioss 2025 `/MAT/LAW36` + `/FUNCT` and Abaqus 2025 `*DENSITY` + `*ELASTIC` +
  isotropic `*PLASTIC` mappings share the same IR, require the exact mapping-report digest, and
  expose protected preview/download plus byte-exact `.rad`/`.inp` golden regressions. This is a
  non-production monotonic, ambient, rate-independent reference slice without damage/failure or
  solver qualification.
- P2 linear-viscoelastic vertical (ADR-0020 item 3): a polymer/elastomer Material
  revision and one exact Property Set revision can create a stable Material Model identity with an
  immutable typed generalized-Maxwell/Prony revision. Explicit PostgreSQL companion tables store
  one to five ordered shear/bulk ratios and SI relaxation times under composite tenant keys, forced
  RLS, immutable triggers, deferred sum/order/evidence guards, and an exact source-class trigger.
  Protected create/list/read/response APIs and the connected Material State workbench expose manual
  term entry, explicit characterized/not-characterized bulk evidence, and a deterministic
  solver-neutral relaxation preview. Migration 041 adds an immutable Abaqus 2025 time-domain card
  projection with capability manifest, exact preflight acknowledgement, typed card/term tables,
  source-IR equality constraints, `.inp` preview/download, byte SHA-256 and golden regression. The
  Material State UI runs this full IR-to-card flow. Migrations 042--045 additionally preserve
  raw/normalized/processed shear-relaxation Datasets, execute explicit observed-point processing,
  fit a bounded deterministic two-term Prony model with multistart diagnostics, require a human
  Candidate Selection reason, and append the accepted Candidate as schema 1.1 of the same stable
  IR identity before card generation. No solver execution or production qualification is claimed.
- P2 hyper-viscoelastic vertical (ADR-0020 item 4 / ADR-0023 bounded reference scope): an
  explicitly elastomer-classified Material revision and exact Property Set revision create a
  stable Material Model identity with an immutable one-term Ogden plus one-to-five shear-Prony
  revision. Migrations 046/047 add explicit typed IR/card summary and term tables, composite
  tenant/classification foreign keys, forced RLS, immutable triggers, deferred source-term equality
  checks, and no EAV payload. Protected API and the Material State UI provide manual IR entry,
  Abaqus/OpenRadioss target selection, complete mapping status inspection, preflight digest
  acknowledgement, immutable card preview, and `.inp`/`.rad` download. Abaqus incompressibility
  maps exactly through D1=0; OpenRadioss LAW62's fixed ν=0.495 is recorded as `approximated`.
  Byte-exact golden fixtures and live PostgreSQL/API/UI verification cover both targets. Multiple
  Ogden terms, temperature dependence, compressible data, production calibration, and solver
  execution/qualification remain excluded.
- `T-20` reference subset: an immutable Statistical Plan pins exactly two existing one-member
  normalized Dataset Selection revisions from distinct Test Runs; a committed Statistical Run records
  typed QC observations and either fails durably or creates a separate immutable Statistical Result
  revision plus typed Parquet pointwise curve Artifact. Scalar statistics use one peak engineering
  stress per Test Run (`n=2`) with mean/sample SD/median/MAD/IQR/range/CV; curve statistics require
  exact observed engineering-strain grid equality and never align, interpolate, resample, or
  extrapolate. The API, provenance/audit hooks, PostgreSQL constraints/RLS, and Material State
  workbench expose the pinned inputs, QC, result scalar values, and mean curve. Larger groups, CI
  estimation, and approved alignment Processing remain outside this reference slice.
- `T-21` reference subset: an immutable Outlier Detection Plan pins one successful reference-pair
  Statistical Result revision and a declared relative peak-difference threshold. A committed
  Detection Run creates zero candidates below that threshold or exactly two review_required
  candidates at/above it, never chooses a true outlier at n=2, and never excludes data
  automatically. Separate immutable human Assessment identities record retained or
  excluded_from_reference_analysis only against the candidate's exact Statistical Plan revision.
  Typed PostgreSQL tables, composite tenant/classification FKs, forced RLS, append-only guards,
  provenance/audit hooks, contracts, APIs, and the Material State workbench expose append-only
  assessment history and a comparison projection without changing any Raw Asset, Dataset,
  Selection, or Statistics Result or creating a derived Selection.
- `T-21` P0-2 multi-replicate extension: a typed modified-z Detection Plan pins one exact
  multi-replicate Statistical Result revision and evaluates specimen-level peak stress from every
  pinned processed Dataset Artifact. An immutable Run stores zero or more `review_required`
  candidates, with explicit MAD-zero/nonmedian evidence and no infinite score. Separate append-only
  human Assessments drive an immutable calibration input Scope that pins every original
  Dataset/Test Run member plus the exact Candidate/Assessment revision for any decision. At least
  two members remain included; Raw Assets, Datasets, Selections, Results, prior scopes, and
  published outputs are never changed. Migration `20260731_034_p02`, composite tenant and
  classification FKs, forced RLS, append-only guards, API/contracts, React controls, unit/API/web
  regressions, and live PostgreSQL include/exclude verification are implemented. This is a bounded
  non-production review method, not an automatic scientific outlier decision.
- `T-32` MVP subset: React/Vite Material Catalog workbench backed by protected Catalog, Modeling,
  and Exporting APIs; Dashboard, search, Material creation, State and typed Property Set
  entry/revision, revision compare/history, provenance summary, and the reference
  IR→mapping-preflight→Solver Card preview/download workflow. Test upload and tabular column-mapping
  UI remain outside this subset.
- `T-32` extension: the protected Material State screen now drives the reference tensile sequence:
  concrete Specimen selection, reference Method registration, immutable Test Run creation, browser
  multipart CSV upload, explicit column/unit mapping, and raw/normalized Dataset revision/curve
  inspection. It remains deliberately limited to the reference tensile CSV contract.
- `T-32` extension: the same Material State screen now selects two pinned normalized Selections,
  creates a Statistical Plan, commits the reference Statistics/QC Run, surfaces passed/failed QC,
  scalar output, and the immutable mean-curve preview. It does not conceal grid mismatch through a
  browser-side alignment or alter either source revision.
- `T-32` extension: after the reference Statistics Result is visible, the same screen can pin a
  declared outlier-review threshold, commit a zero-or-two-candidate Detection Run, append a human
  assessment, and view the exact-scope history. The UI explicitly states that n=2 cannot identify
  an outlier and that no automatic deletion or source mutation occurs.
- `T-32` extension: the reference Calibration workbench now distinguishes a numerically converged
  Candidate from a human acceptance. It records a required Selection label/reason, displays the
  non-production acceptance status, and provides a separate stale-safe action that appends the
  promoted Material Model IR revision with its typed evidence.
- `T-33` reference workbench slice: the existing Material State workbench now presents raw,
  normalized, processed, statistical, fitted/residual, and validation curves through their
  protected display-view APIs. Every view labels representation, SI units, point counts, and
  deterministic preview sampling; fitted and validation panels retain residual/health status and
  never run fitting in the browser. This remains the bounded reference tensile path, not a generic
  plotting or downsampling service.
- `T-34` reference governance evidence slice: the Dashboard now includes a protected Lineage and
  Audit Inspector alongside the Review and Release workbenches. It loads one immutable provenance
  Entity, bounded upstream lineage or downstream impact, completeness, audit events, and audit
  integrity with explicit truncation/invalid warnings. No graph is reconstructed client-side and
  no audit payload, object key, or tenant scope is exposed; the inspector resolves a typed immutable
  revision/artifact reference to the opaque Entity UUID or accepts that UUID directly.
- Local demo composition: an explicit `CMP_ENVIRONMENT=demo` + `CMP_DEMO_IDENTITY=true` Docker
  Compose profile now runs PostgreSQL, owner-only migration/bootstrap, a non-owner `cmp_app` API,
  worker, React workbench, filesystem object storage, checked reference-plugin asset, and an
  API-driven synthetic seed. The seed creates a Material/State/properties/reference IR/OpenRadioss
  card plus a reference tensile Raw Asset and raw/normalized Dataset revisions, then derives the
  tabulated-plasticity IR and both OpenRadioss/Abaqus elastoplastic cards without direct database
  writes or an authorization/RLS bypass.
- `T-22` reference subset: a stable Material Model identity and immutable reference
  isotropic-linear-elastic IR revision projected from one concrete Property Set revision; explicit
  SI density/Young's modulus/Poisson ratio columns, source-yield disposition, semantic/unit bounds,
  Material→State→Property lineage composite FKs, API/list/history resources, provenance/audit/lifecycle
  hooks, PostgreSQL RLS, and non-production-only contract. Generic model-schema registration and
  production model families remain separate work; the bounded reference Candidate evidence path is
  implemented by `T-24`.
- `T-23` reference subset: a stable Calibration Plan identity with immutable typed revisions that
  pin one normalized or processed tensile Selection revision and one reference linear-elastic
  Material Model IR revision; explicit Young's-modulus bounds/initial value, normalization scale,
  point-weighting, multistart count, and seed; durable append-only Run/Attempt/Candidate records;
  typed observed/predicted/residual Parquet diagnostics Artifacts; protected API/contract and a
  Material State calibration workbench. The bounded analytic `sigma = E * epsilon` WLS evaluator
  is explicitly non-production and R3 only for its recorded reference environment. Uncertainty,
  production optimizer/model choice, and solver validation remain separate work.
- `T-24` reference subset: a stable Candidate Selection identity is fixed to one succeeded
  Calibration Run and has append-only human decision revisions. Each revision pins one converged
  Candidate and Candidate SHA-256 with an explicit reason; numerical convergence and human
  acceptance remain separate. Promotion only accepts the current Selection revision and only while
  the exact Material Model revision evaluated by the Run is still current. It appends a new
  reference IR revision with typed Selection/revision, Candidate/SHA-256, Run, and diagnostics
  Artifact/SHA-256 evidence. Explicit PostgreSQL tables, composite tenant/classification FKs,
  forced RLS, immutable guards, trigger-level evidence checks, protected API/contract, integration
  coverage, and the Material State workbench are implemented. It is non-production and is not a
  formal approval, release, uncertainty, or solver-validation decision.
- `T-25` reference subset: an explicit OpenRadioss 2025 `/MAT/ELAST` exporter for only the
  reference linear-elastic IR and `kg_m_s` units; typed capability/preflight/mapping-report and
  immutable Solver Card identity/revision tables, source-revision FKs, SHA-256 report/card digests,
  provenance/audit/RLS, protected preview/download APIs, and no generic exporter/options payload.
  Production solver qualification, additional targets, transforms, approximations, and release
  approval remain separate work.
- `T-26` reference subset: a byte-exact `.rad` golden fixture plus report-acknowledgement,
  unsupported-target, and text-tamper regressions. A multi-target/version matrix, semantic parser,
  and domain-review golden-update workflow remain separate work.
- `T-27` reference subset: stable Validation Template and Validation Plan identities append typed
  immutable revisions that pin exact Template, reference Material Model IR, OpenRadioss Solver Card,
  and experimental Dataset Selection revisions. A durable Run retains an immutable reference deck,
  stdout/stderr, optional bounded native result, and same-shaped Result Manifest for explicit
  inline-mock or manual-attachment evidence. Explicit PostgreSQL tables/constraints/indexes,
  composite tenant/classification FKs, forced RLS, state/role trigger guards, audit, and provenance
  preserve the evidence tuple. The protected Material State workbench creates/pins/submits/collects
  actual API resources and labels the feature as non-production. No real solver/HPC process,
  numerical-health result, comparison metric, validation pass, approval, or release claim exists;
  those are `T-28` and later work (ADR-0013).
- `T-28` reference subset: a terminal T-27 Result Manifest now produces separate immutable typed
  response-extraction, numerical-health, and experimental-comparison result records/Artifacts.
  Explicit PostgreSQL tables, composite tenant/classification FKs, forced RLS, immutable guards,
  comparison-point rows, provenance, audit, protected evaluate/read/curve APIs, and Material State
  workbench UI retain the frozen input tuple. The first profile validates declared SI response
  units/target/curve health, compares only on the observed experimental strain grid with linear
  interpolation/no extrapolation, uses fixed relative RMSE `0.05`, and records abnormal/unhealthy/
  missing/unit-invalid/alignment-invalid/fit-overlap outcomes as `not_evaluated`. It is reference
  evidence only, not real solver/HPC qualification, production material validation, approval, or
  release policy (ADR-0014).
- `T-29` reference governance subset: immutable `governance.review_request` and
  `governance.review_decision` tables pin an aggregate revision and manifest digest; protected
  request/list/read/decision APIs advance the shared lifecycle event/projection in one transaction.
  The author cannot decide, stale manifest or newer revision approval is rejected, decisions are
  append-only, and `changes_requested` requires a newly created immutable revision. The React
  dashboard includes a digest-pinned request/decision workbench and recent-review list. The MVP
  fixes the required role to `domain_reviewer`; configurable matrices, comments/evidence, legal
  signatures, and Release publication remain outside this task.
- `T-30` reference Release completeness subset: immutable `governance.release`, typed
  `release_manifest`, and digest-fixed `release_artifact` rows with composite tenant/classification
  keys, explicit Material Model/Solver Card/Validation/Review foreign keys, forced RLS, and
  append-only guards. The publish gate requires exact lineage and SHA-256 matches, a passed
  Validation Result, approved T-29 Review digest, non-production card, and no unsupported or
  approximated mapping statuses. Protected create/list/read/download APIs and a React Release
  workbench expose the reference package channel. Supersede/withdraw, production object storage,
  and broader release evidence policy remain outside T-30.
- `T-09`: resumable streaming multipart sessions, HMAC actor/tenant/expiry capabilities,
  immutable part manifests, verified staging Raw Assets, append-only ingestion events, duplicate
  content detection, protected API, filesystem development adapter, and forced PostgreSQL RLS
- `T-10`: tenant/classification-scoped content-addressed promotion, immutable Artifact manifests,
  append-only integrity observations/issues, guarded current projection, mismatch reconciliation,
  scoped streaming download, protected API, and forced PostgreSQL RLS
- `T-13`: typed Entity/Activity/Agent and six core relation families, immutable owner-reference
  resolution, atomic run/revision hooks, deferred completeness, DAG cycle guards, protected Entity
  lookup, and forced PostgreSQL RLS
- `T-14`: bounded recursive upstream/downstream lineage, downstream impact filters and opaque
  pagination, deterministic shortest paths, generic Entity-root completeness gate, typed
  security-invoker read models, graph explosion limits, and tenant/classification-safe APIs
- `T-15`: stable Job/immutable Attempt separation, versioned Job Spec digests, PostgreSQL atomic
  claim/lease/heartbeat/recovery, generic retry taxonomy, runner resources, protected Job API,
  and a handler-neutral durable worker
- `T-16`: transactional CloudEvent outbox, aggregate sequence and producer deduplication, fenced
  at-least-once delivery, poison quarantine, inbox deduplication, atomic ArtifactAvailable event,
  durable reconciliation schedule/run lease, and staging-only retention receipts
- `T-17`: stable Plugin Definition/immutable Package separation, Manifest 1.0 and JSON Schema
  validation, explicit capability/schema/supply-chain references, append-only verification and
  activation history, project-scoped allowlisting, protected API, and forced PostgreSQL RLS
- `T-18`: framework-free Python SDK, immutable Job Spec/Result Manifest execution service,
  reviewed-package subprocess runner, OCI-ready production plan and capability attestation,
  tenant-scoped active-package planning, durable worker bridge, and seven-extension TCK

## Runtime proof

- FastAPI health endpoint: `GET /api/v1/health`
- Web workbench: `http://127.0.0.1:5173` after `npm run dev --workspace @cmp/web`; it uses the
  configured bearer token and `/api/v1` contract without an authorization bypass
- Unconfigured durable-worker idle verification: `cmp-worker --once --json`
- Generated client calls a live Uvicorn process in integration tests
- Worker starts in a separate subprocess and exits successfully in one-cycle mode
- OIDC validation uses exact issuer/audience, explicit asymmetric algorithms, configured JWKS,
  access-token type checking, required organization/project context, and sanitized failures
- PostgreSQL principal persistence keeps `(issuer, subject)` immutable, produces opaque UUIDv4 IDs,
  and serializes concurrent JIT provisioning without duplicate actors
- PostgreSQL authorization runs under a non-owner `NOSUPERUSER NOBYPASSRLS` role with
  transaction-local principal/tenant/permission/clearance context
- Classification-aware RLS filters list/count/facet operations and rejects cross-project or
  above-clearance writes; tenant composite FKs normalize hidden/unknown target failures
- Revision writes use concrete UUID bases, canonical SHA-256, transaction-local fail-closed hooks,
  and PostgreSQL compare-and-swap head advancement
- Material Catalog writes append separate Material, State, and Property Set revisions; original
  rows reject mutation/deletion, State/Property identities cannot move to another parent, and all
  parent references are concrete revisions rather than moving heads
- Catalog search/detail and writes use `catalog.read`/`catalog.write` with organization/project and
  classification RLS; PostgreSQL integration proves cross-project hiding plus lifecycle, provenance,
  and audit facts for every Catalog revision
- Reference Material Model creation uses `modeling.write` plus its explicit `catalog.read`
  dependency; source values are selected by concrete Property Set revision, then persisted with
  concrete Material/State/Property revision references. PostgreSQL constraints prevent mixed parent
  lineage, RLS hides cross-project models, and original IR revisions reject mutation/deletion.
- Reference Solver Card creation consumes a concrete Material Model revision only; an explicit
  OpenRadioss 2025 `/MAT/ELAST` `kg_m_s` preflight returns every mapping status and its digest must
  be acknowledged before an immutable typed card revision is written. PostgreSQL T-25 integration
  coverage proves provenance/audit derivation, tenant isolation, and card-revision immutability.
- Reference tensile Test Runs pin the exact Specimen and Test Method revisions used at registration;
  a Dataset import accepts only the matching tenant/classification Test Run and the completed
  `text/csv` Raw Asset Artifact, then appends raw and normalized Dataset revisions rather than
  mutating source bytes or a published curve.
- Dataset CSV import rejects missing/duplicate columns, unsupported units, non-finite/negative
  points, non-monotonic engineering strain, and ambiguous mapping. It produces typed SI Parquet
  only after the user supplied the mapping, and attaches the Raw Asset as input provenance to the
  Dataset generation activity.
- Reference Processing pins exact Selection, Recipe, and normalized Dataset revisions before it
  creates a committed Run. The only reference operation is an inclusive observed-point crop: it
  creates a new processed Dataset identity and never edits raw/normalized revisions, interpolates
  points, or treats a browser curve preview as an artifact.
- The processed Dataset generation activity records the Processing Run, normalized Dataset usage,
  typed Recipe plan, output derivation, and generic revision audit facts in tenant/classification
  scope. If output Dataset commit succeeds but the terminal Run projection fails, the Run remains
  executing for explicit reconciliation rather than being falsely marked failed.
- Reference Statistics first validates that the two immutable Selection inputs resolve to distinct
  Test Runs and reads both normalized Artifacts without changing them. It stores an explicit failed
  terminal Run plus typed QC when an Artifact is unreadable, its point count disagrees with its
  revision, or the observed engineering-strain grids differ; no implicit alignment path exists.
- A successful Statistics Run creates a separate derived typed curve Artifact and immutable Result
  revision before its terminal transition, then records QC in the same terminal transaction. Result
  provenance captures both Selection revisions and the Plan; the two-sample confidence interval is
  explicitly `not_provided_reference_pair` rather than manufactured from point pseudo-replicates.
- Reference Calibration resolves only concrete Selection, Dataset, and Material Model revisions
  through public bounded-module ports, verifies shared Material State and tenant scope, and records
  a durable terminal failure if its typed curve Artifact cannot be read. Its analytic bounded WLS
  evaluator writes a separate typed diagnostics Artifact and immutable Candidate per recorded
  multistart Attempt; it never changes source curves or the IR it evaluated.
- Candidate Selection requires a succeeded Run and exact converged Candidate digest, retains human
  reason/history separately from convergence, and can promote only the current Selection revision
  against the still-current evaluated IR revision. The new IR revision records concrete Selection,
  Candidate, Run, and diagnostics Artifact evidence; all prior IR/Candidate/Run revisions remain
  immutable.
- The Material State workbench calls the protected Testing/Dataset/Upload APIs directly; it keeps
  raw and normalized curve revisions selectable, labels their units, and uses deterministic preview
  sampling rather than treating a browser plot as a calculation artifact.
- The local Compose workbench can request a demo token only from an explicitly enabled demo API;
  the in-process token issuer is absent from normal/production configuration, and the resulting
  token follows the same JWT verification, group role-binding, authorization, and RLS path as a
  normal API request. The database bootstrap creates an owner-distinct `cmp_app` role and grants
  only the existing bounded-module table/function operations it requires.
- PostgreSQL integration uses a migration-managed explicit typed fixture; no generic EAV/content
  table exists
- Job submission is tenant-idempotent; every retry appends a distinct immutable Attempt/Job Spec
- PostgreSQL claim uses runner serialization and `FOR UPDATE SKIP LOCKED`; fencing tokens reject
  stale heartbeat/finalize calls after lease recovery
- Failure/cancel/timeout attempts remain queryable, terminal attempts and Job results are immutable,
  and identical finalize calls replay without a second commit
- Job/Attempt/Runner RLS uses the same request/service principal, tenant, permission, and
  classification context as API resources
- Plugin Maintainers can register but cannot self-verify or activate; Org Admin verification and
  activation commands use a separate permission and append actor/request/trace facts
- PostgreSQL rejects plugin ID/version digest substitution, package/history mutation, activation
  before eligibility, incomplete schema/capability bundles, revoked packages, and cross-project
  access even when opaque UUIDs are known
- Active package lookup is pinned to project, plugin ID, exact version, and package digest; revoked
  or cross-project packages are hidden before runner materialization
- The local T-18 runner rehashes package/input/output bytes, safely extracts bounded ZIP entries,
  rejects links and traversal, supplies only scoped SDK I/O, and enforces parent timeout/cancel
- Network, child-process, ambient-path, symlink, oversized-output, corrupt-package, and corrupt
  Result Manifest fixtures fail closed with sanitized diagnostics
- An OCI runtime must attest every production isolation control before receiving an execution plan;
  core contains no Docker, Kubernetes, vendor runtime, or plugin implementation dependency
- Identical seeds produce byte-identical synthetic RNG output, and all seven extension types pass
  the same domain-neutral contract-echo compatibility matrix
- Upload parts stream incrementally to a fresh server-generated staging key; exact per-part and
  complete-object size/SHA-256 are checked before a Raw Asset can be committed
- Upload capabilities are deterministically signed but not persisted as plaintext, and are bound
  to session, organization, project, actor, and expiry in addition to bearer authorization
- PostgreSQL blocks part replacement, Raw Asset/Ingestion Event mutation, incomplete completion,
  invalid state transitions, cross-project reads/writes, and storage-key exposure in API contracts
- Same-classification duplicate bytes reuse one Raw Asset while appending a distinct immutable
  ingestion event; mismatch and cancellation leave no successful Raw Asset fact
- Raw Asset promotion never updates its staging fact; one separate immutable Artifact references
  it, and cross-actor duplicate ingestion reuses the same available Artifact
- PostgreSQL requires an exact promoting pending manifest before Artifact insertion and an exact
  immutable observation before integrity projection change; terminal pending/Artifact rows reject
  every mutation or deletion
- Content keys include organization, project, classification, and SHA-256; filesystem promotion
  rehashes source/final bytes and uses no-overwrite commit with idempotent identical replay
- Reconciliation recovers object-success/DB-gap, records missing/corrupt observations and
  orphan/missing-staging issues, and never rewrites an Artifact manifest
- Download grants are canonical HMAC capabilities bound to actor, tenant, Artifact, digest, and
  expiry; bearer authorization remains required and public contracts contain no object keys
- Raw Asset→synthetic revision commit records typed usage, generation, derivation, and association
  atomically; the same domain-run graph replays while digest substitution is rejected
- PostgreSQL rejects generated orphan Entity records, incomplete Activities, duplicate primary
  generation, reverse dependency cycles, cross-project reads, and every provenance mutation/delete
- T-06 typed revision transactions can install a fail-closed hook that records revision generation,
  author association/attribution, and `wasRevisionOf` in the caller's transaction
- Public provenance access is read-only Entity lookup, bounded lineage/impact, and completeness;
  moving heads, DB table details, raw payloads, and object keys are absent from the contract
- Recursive discovery and RLS-protected Entity materialization use separate bounded SQL phases so
  PostgreSQL avoids a pathological security-view join plan; known DAG paths remain deterministic
- A 10-hop chain and 10,000-edge fan-out run under the two-second query assertion, while depth 20,
  10,000 nodes, page size 1,000, cycles, duplicate paths, cursor rebinding, and graph truncation
  fail closed
- Artifact finalization and ArtifactAvailable outbox append commit or roll back together; exact
  replay emits one event, schema validation fails the transaction, and event data contains no
  object-store key
- Outbox aggregate sequence blocks out-of-order claims; publisher crash recovery replaces the
  lease token, stale fencing is rejected, poison blocks later aggregate events, and duplicate
  consumer delivery creates one inbox receipt
- Reconciliation schedules reclaim expired runs as timed out, append a fresh fenced run, execute
  the existing T-10 reconciler, and record idempotent cleanup only after discarding an eligible
  terminal pending staging object; the content-addressed final object remains intact
- Audit append derives only from an authorized modifying command; PostgreSQL serializes each
  project chain and computes sequence, previous hash, recorded time, and event hash itself
- Periodic roots cover only the next contiguous unsealed range and form their own root chain;
  application recomputation matches PostgreSQL and reports unsealed tail events separately
- Audit rows and roots reject update/delete, cross-project readers see no rows, and mutation,
  reorder, or deletion performed through a privileged tamper fixture makes integrity invalid
- Public audit access is read-only event query, bounded export, and integrity reporting; raw
  payloads, secrets, IP addresses, object keys, and generic JSON/EAV are absent from DB/contracts

## Validation result

Normal command: `make ci`. This Windows environment has no native `make`, so the exact underlying
`scripts/ci.sh` target was invoked through Git Bash with the locked local environment. The
PostgreSQL integration suite additionally requires `CMP_TEST_POSTGRES_DSN`.

```text
Ruff: passed
mypy strict: passed (374 source files)
Architecture rules: passed
Contract lint: passed
OpenAPI compatibility: passed
Alembic `upgrade head --sql`: passed
PostgreSQL marker suite: 62 passed, 0 skipped, 0 failed
CI-equivalent pytest with the same disposable PostgreSQL DSN: 452 passed
Root web check: build passed; Vitest: 21 passed
Live P0-1 environment: Docker Engine 29.6.1, Compose 5.3.0, PostgreSQL 16, migration/bootstrap,
  non-owner API, worker, web, reference-plugin check, and synthetic seed all completed successfully.
  The disposable `postgres-test` profile supplied the owner DSN without weakening the
  SCRAM-authenticated demo database. Browser smoke verified the seeded Material, Material State,
  typed properties, normalized tensile Dataset, tabulated-plasticity IR, and OpenRadioss/Abaqus
  card previews and downloads.
T-11/T-19/T-21/T-D03 have unit, API integration, migration SQL, and browser-workbench regression
coverage.
Online Alembic `base -> head -> base`, forced-RLS integration, and the full CI-equivalent suite now
run against disposable PostgreSQL. This live pass exposed and fixed migration downgrade ordering,
composite-key, finite-value, SQL construction, authorization-capability, and typed-query defects
that offline SQL rendering could not prove.
```

## Intentionally absent

- Public role-management API/UI and deployment-specific DB role/secret provisioning
- Export-control nationality/compartment policy (`OQ-SEC-002`)
- Full Process Run input/output graphs, lot split/merge and multi-lot acceptance; richer typed
  property/curve families; Test Campaign/Instrument records; production importer plugin approval;
  arbitrary channel schemas; and non-reference Dataset channels
- General multi-member Selection/filter semantics, arbitrary recipe graphs, durable Processing Run
  reconciliation, inverse post-necking identification, calibration-specific outlier scope,
  larger-replicate/CI statistics, and production nonlinear calibration
- Production release publication, external PLM replacement, and release-specific evidence policy
  beyond the bounded T-30/T-31 reference channel
- Production S3 adapter, KMS/object-lock/versioning/replication provisioning, external event
  transport credentials, and deployment runner credentials
- T-17 authoritative package-Artifact admission, T-18 materializer/committer deployment wiring,
  and signature/SBOM/malware/vulnerability verification automation
- A selected production OCI runtime implementation and production package/image admission policy
- Production plugins
- External audit root signer, SIEM/WORM connector, retention/legal-hold policy, and deployment
  service-principal scheduling for periodic sealing
- Production fitting algorithms, production solver cards/targets, or qualified validation
  thresholds; the implemented linear/tabulated IRs and OpenRadioss/Abaqus cards are bounded
  reference outputs and are not production-qualified
- Production web identity/session integration, external demo IdP deployment, and a production
  Compose/deployment profile; the checked-in demo issuer is explicitly local-only

## Next gate

**Updated 2026-07-18 (superseded below):** the reference Test/Dataset, committed Processing, exact-grid
two-sample Statistics/QC, and append-only outlier-review slices are implemented. The completed
reference Material → Property Set → IR → OpenRadioss Card path remains the product's
second-priority CAE-use vertical slice; this T-21 work supports the separate Test Data → Statistics
demonstration and does not replace it. T-11 now makes the reference CSV path explicitly
detect → human mapping approval → pinned Import Run → immutable Dataset revisions. The next requested
sequence is T-23/T-24 reference calibration and candidate selection, then T-27/T-28 validation. Any
expansion beyond the existing exact linear-elastic OpenRadioss mapping also requires a documented
target/model mapping decision; it must not be silently inferred.

**Update 2026-07-19:** T-23 is now implemented as a non-production reference Calibration
Plan/Run/Attempt/Candidate diagnostics slice. It demonstrates `Selection revision -> Material
Model IR revision -> Candidate diagnostics` without mutating the source Dataset or IR. The next
requested work is T-24 human candidate selection and append-only IR promotion, followed by T-27/T-28
validation. Any expansion beyond the exact reference linear-elastic OpenRadioss mapping requires a
documented target/model decision and must not be silently inferred.

**Update 2026-07-20:** T-24 now completes the bounded reference path `Calibration Run ->
converged Candidate -> human Candidate Selection revision -> appended Material Model IR revision`.
The workbench and API make the human acceptance reason explicit, retain typed evidence, and reject
superseded Selection revisions or stale evaluated IR heads. The next requested work is `T-27`, then
`T-28`: a narrow non-production Validation Template/Runner slice followed by result extraction,
numerical-health, and experimental-comparison evidence. Neither step may imply a production solver,
HPC integration, approval, or release policy without a separate documented decision.

**Update 2026-07-21:** T-27 now completes the evidence-only boundary
`Validation Template revision -> Validation Plan revision -> deck -> Run -> Result Manifest`.
Both mock and manual branches retain the same immutable Artifact/provenance shape; the mock runner
does not execute a solver and `normal` termination is not a validation pass. The next requested
work is `T-28`: bounded native-result extraction, numerical-health, experimental comparison, and
an explicit non-production verdict that must keep abnormal/no-output runs `not_evaluated`.

**Update 2026-07-22:** T-28 now completes that bounded non-production interpretation path:
`Result Manifest -> typed SI response extraction -> numerical-health report -> observed-grid
comparison -> immutable Validation Result`. The API/workbench expose the extracted evidence,
health, holdout-independence, metric, threshold, and curve preview. The next delivery work is
T-29 review/lifecycle and T-30 release evidence gating; a real solver/HPC adapter, production
threshold, multiple solver/template support, and domain qualification remain explicit decisions.

**Update 2026-07-23:** T-29 now completes the bounded governance path:
`draft revision -> review request pinned to manifest digest -> separated reviewer decision ->
approved/changes_requested lifecycle projection`. Review facts and decisions are immutable,
tenant-scoped, and transactionally linked to lifecycle events. A stale digest, newer revision,
author-only decision, or repeated decision is rejected; changes requested cannot be resubmitted
without a new revision. The next delivery work is T-30 Release completeness and evidence gating.

**Update 2026-07-24:** T-30 now completes the bounded reference Release path:
`approved candidate -> typed completeness/integrity gate -> immutable Release Manifest ->
reference package search/download`. The gate binds one Material Model, Solver Card, passed
Validation Result, approved Review digest, and provenance snapshot by explicit IDs and SHA-256
digests; cross-tenant, stale, draft, unsupported, approximated, or partial inputs fail closed.
The API and dashboard expose the package, while supersede/withdraw and production publication
remain T-31+ scope.

**Update 2026-07-25:** T-31 now adds an append-only Release lifecycle projection and transition
event relation. A released package can be explicitly superseded by a same-scope successor or
withdrawn; the immutable Release, Manifest, and package rows remain untouched. Download and
explicit consume operations append typed usage facts, while the impact API reports predecessor,
successor, transition history, usage, and terminal warnings. The React Release workbench exposes
the lifecycle controls and prevents terminal download. Automatic PLM replacement, production
publication, and solver reruns remain outside this bounded reference slice.

**Update 2026-07-25:** T-33/T-34 now make the workbench path reviewable end to end. Curve panels
show raw/processed/statistical/fitted/validation evidence with explicit units and sampled-preview
labels, while the Dashboard Lineage and Audit Inspector reads bounded provenance paths,
completeness, append-only events, and chain integrity next to the existing Review/Release commands.
The next gate is a live PostgreSQL-backed demo/test run and then T-35/T-36 operational observability
and restore drills; generic importer formats, production solver/HPC execution, and external release
publication remain separate decisions.

**Update 2026-07-26:** the product vertical now performs actual bounded tensile-data reduction and
multi-solver card extraction. A normalized/processed engineering curve is converted only through
its first maximum stress to true stress and true plastic strain; source/excluded counts and the
necking index remain immutable evidence. The resulting IR drives OpenRadioss LAW36 and Abaqus
isotropic-plasticity cards through explicit preflight, preview, and download APIs and the Material
State workbench. The constant post-necking extension is `approximated`, never silently exact. Real
solver execution, inverse post-necking identification, rate/temperature dependence, damage/failure,
and production qualification remain separate decisions.

**Update 2026-07-27:** P0-1 is complete on a live Docker/PostgreSQL stack. Migration/bootstrap/seed,
non-owner API/worker/web, protected local-demo identity, PostgreSQL marker tests, CI-equivalent tests,
and browser smoke all passed. The online downgrade cycle and forced-RLS paths found defects that now
have regression coverage. The next implementation wave is P0-2 multi-replicate
Selection/processing/statistics/QC/outlier scope and its connected curve UI.

**Current delivery order (ADR-0019, accepted 2026-07-14):** all existing foundation and vertical
results above remain in place. Remaining work is now sequenced as follows:

1. `P0-1` — **complete**: Docker/Compose, migration/seed, live PostgreSQL/RLS integration,
   skip-zero marker suite, CI-equivalent suite, and protected browser smoke are recorded above.
2. `P0-2` — **complete**: expand T-19/T-20/T-21 from one/two-curve reference subsets to immutable multi-member
   repeat-test Selection, explicit processing/alignment, specimen-level statistics/pointwise bands,
   QC/outlier assessment with calibration-specific scope, and connected curve UI.
3. `P1` — **complete for the bounded non-production reference scope**: add the reference Voce/SciPy nonlinear calibration path, nonlinear
   Candidate diagnostics and human selection, calibrated solver-neutral IR plus explicit tabulated
   projection, and existing OpenRadioss/Abaqus preflight/preview/download. Add solver-independent
   material-model and disjoint-holdout validation; do not claim production model/optimizer approval.
4. `P2` — Process/Lot/Batch and broader domain expansion, production plugins/decisions, actual
   OpenRadioss/Abaqus execution qualification and HPC, observability, backup/restore, performance,
   security, and external release hardening.

Product-owner direction explicitly defers actual solver execution verification to P2. Existing
T-27/T-28 mock/manual evidence and immutable results are retained; they are neither deleted nor
reclassified as solver qualification. The immediate implementation gate is now the explicitly
documented `P2` decision and hardening wave.

Prior planning note (superseded): the first vertical flow was described as a non-production reference subset:
Material → State → typed Property Set → frozen reference IR → explicit OpenRadioss mapping report
→ immutable card preview/download. The next contiguous product step is the Test/Dataset vertical
slice: Specimen/Test metadata, reference tensile CSV upload, column/unit mapping, raw and
normalized curve viewing, and a concrete Material link. T-30 still owns Release creation and
evidence policy; T-17/T-18 production Artifact composition and release-specific retention/backup
policy are not implied complete.

## P0-2 progress (2026-07-28)

The first P0-2 increment is implemented. A typed `reference_tensile_replicate_set` Selection
revision pins 2..50 ordered normalized/processed Dataset revisions from distinct concrete Test Run
revisions and one Material State. Membership is stored in
`datasets.dataset_selection_member` with explicit foreign keys, uniqueness constraints, forced
RLS, immutable-row protection, and a deferred member-count guard; it is not JSON or EAV.

The API supports create/list/get/append-revision. The Material State tensile workbench supports
member selection and a common-scale overlay of pinned curves. Synthetic demo data now creates
three independent Test Runs/Datasets and one replicate Selection. Legacy one-member Selections are
backfilled without changing their revision hashes.

The second P0-2 increment is also implemented. Migration `20260729_032_p02` adds a typed
`reference_tensile_common_grid_linear` Recipe revision with explicit start/end/count,
`intersection` domain, `piecewise_linear` interpolation, and `reject` extrapolation columns and
database constraints. A grouped execution pins the multi-member Selection and Recipe revisions,
then creates one immutable `processing_run`, derived Artifact, and separate processed Dataset
identity/revision per member. The API and Material State workbench expose the policy, exact grid,
batch result, processed overlays, and concrete output revision links. No source revision is edited
and no statistical calculation performs hidden alignment.

The third and fourth P0-2 increments implement the complete persisted multi-replicate
Statistics/QC slice. The typed, solver-neutral kernel treats the 2..50 Selection members as the
specimen-level sample, requires already processed exact grids, and calculates peak-stress scalar
and pointwise mean, sample standard deviation, median, MAD, IQR, min/max, coefficient of variation,
and two-sided 95% Student-t mean intervals. Migration `20260730_033_p02` adds explicit typed Plan,
Plan Revision, Run, ordered Run Member, Result, Result Revision, and QC Observation tables with
foreign keys, constraints, indexes, forced RLS, immutable revision guards, and terminal Run-state
guards; no JSON/EAV storage is used.

The protected API creates/lists/reads Plans, commits and reads Runs, and reads immutable Results and
bounded pointwise curve previews. Provenance records the concrete Selection/Plan usages, Result
derivation, and `statistics.reference_tensile_replicates` generation activity. The connected web
flow explicitly pins alignment outputs as a new immutable Selection before creating a Plan; it then
shows exact members, QC, peak scalar statistics, observed range, mean, and Student-t 95% CI band.
Statistics performs no interpolation or hidden alignment, and the earlier pair workflow remains
unchanged.

P0-2 is complete through multi-member outlier evidence, append-only human assessment, and an
immutable calibration-specific input Scope. The bounded P1 wave described below subsequently added
multi-curve Voce calibration, Candidate diagnostics and selection, calibrated IR, two-solver card
generation, and solver-independent holdout validation. No automatic source mutation or exclusion
is permitted.

Verification includes a live non-owner Docker/PostgreSQL execution that committed three independent
31-point processed Dataset revisions in one batch. Unit tests cover interpolation, common-domain,
monotonicity, and extrapolation rejection; API integration covers explicit policy and grouped output;
migration regression covers typed columns, guards, RLS-compatible provenance finalization, and the
absence of JSONB/EAV. Migration 033 was also exercised as fresh upgrade, downgrade to 032, and
re-upgrade against disposable PostgreSQL 16. Updated full-suite counts are recorded after the
P0-2 persistence gate is merged.

## P1 completion (2026-08-03)

P1 is complete for the explicitly non-production reference scope. The platform consumes an
immutable calibration input Scope containing multiple preserved processed tensile curves, runs a
bounded deterministic Voce/SciPy `least_squares` calibration, stores every Attempt/Candidate and
diagnostic, requires append-only human Candidate selection, and promotes the accepted Candidate to
a calibrated solver-neutral Material Model IR. A separate frozen 51-point tabulated projection
feeds the existing OpenRadioss LAW36 and Abaqus elastoplastic exporters, including mapping preflight,
preview, Artifact-backed download, and deterministic regression fixtures.

Migration `20260803_037_p1` and the connected API/workbench add solver-independent holdout
validation. One immutable Plan pins the calibrated IR and an independent tensile Dataset. Both the
Dataset revision and Test Run revision must be disjoint from every calibration Scope member. The
Result retains exact observed/predicted/residual points, RMSE, relative RMSE, source/comparison
Artifact digests, full calibration lineage, audit, and provenance. The fixed `0.05` reference
threshold and `solver_execution=not_used` marker prevent this evidence from being mistaken for
production or solver qualification. The demo seed now provides three calibration curves and a
fourth disjoint holdout curve.

The completion gate passed 497 Python tests and 24 web tests, plus ruff, mypy, architecture,
OpenAPI contract lint/compatibility, TypeScript, and production web build checks. A live non-owner
Docker/PostgreSQL run also persisted both calibrated OpenRadioss and Abaqus cards and a four-point
disjoint holdout result with comparison Artifact/provenance evidence.

Remaining P2 work is deliberately not implemented: broader Process/Lot/Batch/Campaign/Instrument
domain depth and importer/property families; approved production constitutive models, objectives,
bounds and scientific fixtures; actual OpenRadioss/Abaqus data-check/execution, HPC adapters,
solver-output parsing and qualification; and observability, disaster-recovery, performance,
security, external release and connector hardening. Solver execution validation remains excluded by
product-owner direction until that P2 scope is explicitly resumed.

## P2 product vertical started (2026-07-15)

ADR-0020 changes the next execution order without discarding the completed foundation. Material
revision schema v2 adds a governed class for workflow guidance; legacy v1 revisions remain
unchanged and read as `unclassified`. The user-facing README now leads with Material management,
test/processing, IR and card workflows while the detailed engineering runbook lives in
`DEVELOPMENT.md`.

The ordered P2 delivery was: Steel elastoplastic regression protection; linear Prony IR and
Abaqus viscoelastic card; shear-relaxation import/processing/calibration; Ogden-Prony Abaqus and
OpenRadioss LAW62 cards; then Process/Lot/Batch genealogy. These are reference/non-production
capabilities until domain-approved schemas, numeric fixtures and mappings are available. Actual
solver execution validation remains excluded.

### Shear-relaxation Dataset increment

Migration 042 and the Dataset/Testing applications now implement the data-ingress half of P2 item
3. A declared `reference_shear_relaxation` Test Method and Test Run pin exact Specimen and Material
State revisions. The browser uploads a UTF-8 CSV as an immutable Raw Asset, requires explicit time
and shear-modulus columns and units, then creates separate raw and normalized Dataset revisions.
Normalized points are stored as a typed SI Parquet Artifact (`s`, `Pa`); the original units remain
in the revision. PostgreSQL uses dedicated non-EAV identity/revision tables, composite tenant/source
foreign keys, RLS, immutable revision triggers, and indexes. Raw-Asset usage is recorded in the
Provenance graph. The Material State screen renders a bounded deterministic curve preview.

Migration 043 completes the explicit Processing half. An inclusive observed-point time crop is
stored as a stable Recipe plus immutable revision; a committed Run pins exact normalized Dataset
and Recipe revisions and produces a verified derived Parquet Artifact. Its output is revision 1 of
a separate processed Dataset identity rather than a mutation of the imported Dataset. PostgreSQL
enforces typed columns, composite tenant FKs, normalized-input and terminal-transition guards,
forced RLS, and immutable Recipe revisions. Provenance records the source Dataset and Recipe as
inputs to the concrete Run. The Material State screen exposes time bounds, states that no
interpolation occurs, and previews the processed curve.

Live Docker/PostgreSQL verification on 2026-07-16 migrated to
`20260809_043_shear_proc` and committed a 6-point normalized input to a 3-point processed output
from `1 s` through `100 s`, with two provenance usages. Backend unit, contract, API, offline
migration, frontend test, and frontend build gates passed for this increment. The CI-equivalent
gate completed with 527 Python tests and 27 Vitest tests, plus a successful production web build.

Migration 044 implements the next bounded calibration increment. A revisioned Plan pins one exact
processed shear-relaxation Dataset revision and one exact baseline linear-Prony IR revision. The
reference two-term generalized-Maxwell evaluator fixes the baseline instantaneous shear modulus,
fits bounded total shear ratio, fast-term fraction and two separated log-time constants, and runs
deterministic SciPy TRF multistart with PCG64. Runs, Attempts and Candidates use explicit non-EAV
tables; observed/predicted/residual points are immutable Parquet Artifacts. Candidate objective,
RMSE, mean residual, convergence reason, evaluation counts, bound warning, Jacobian-rank
identifiability and explicit unassessed uncertainty are returned by the API and rendered in the
Material State workflow. No Candidate is selected or promoted automatically.

Live Docker/PostgreSQL verification migrated to `20260810_044_prony_cal`, retained all six observed
points in a separate processed Dataset, executed four deterministic starts, persisted four
Candidates and read back six diagnostic rows for the displayed Candidate. The successful live Run
is `40192c69-7491-4b68-828c-f76e5f491280`. The fixture reached the slow-time lower bound, and that
fact remains visible as a warning rather than being silently accepted.

The repository `make ci` gate passed with 467 Python tests and 27 Vitest tests; its 64 PostgreSQL
cases were expected skips because that command had no DSN. The same PostgreSQL marker suite was
then run against the isolated Compose PostgreSQL 16 service with `CMP_TEST_POSTGRES_DSN`, producing
64 passed, zero skipped and zero failed. Type checking covered 450 source files; architecture,
contract lint/compatibility and the production frontend build also passed.

Migration 045 completes P2 item 3. A human explicitly selects one converged Candidate, records a
reason, and creates an immutable Candidate Selection revision. Promotion uses compare-and-swap on
the exact baseline revision and appends schema 1.1 to the same stable Material Model identity. The
new IR pins the Selection, Run, Candidate and diagnostics Artifact digests. PostgreSQL validates
the exact tenant-scoped lineage and prevents the earlier linear-elastic Candidate guard from
handling the distinct Prony evidence kind. The connected UI requires an explicit Review action;
it never defaults to the lowest objective Candidate.

Live Docker/PostgreSQL verification selected Candidate
`0b8bd19e-5a0c-4ef2-923f-bec290f19c0f`, retained its visible slow-time lower-bound warning, and
promoted model `5ffc8864-e995-49d7-8fc9-f421ec48d45f` from revision 1 to revision 2
`4241a279-9e92-40df-ba7c-54c42d9cb75c`. Abaqus preflight reported density, elasticity and shear
Prony terms as exact, bulk/temperature as not applicable, and SI target transformation as
transformed. Solver Card `8c1569a4-b55a-4be2-969c-4c8abea1a656` pins that promoted revision;
preview and downloaded bytes matched SHA-256
`fdb9b4bdbb66e706d0350185940dbbfe9be4fe42d1156178fcee930a5638a1ce`.

The CI-equivalent gate passed with 471 Python tests and 27 Vitest tests, plus ruff, mypy over 456
source files, architecture rules, contract lint/compatibility and the production frontend build.
The isolated Compose PostgreSQL 16 marker suite then passed 64/64 with zero skips or failures.

At that increment boundary, the ordered next work was P2 item 4 Ogden-Prony/Abaqus/OpenRadioss
LAW62 and P2 item 5 Process/Lot/Batch genealogy. Both bounded reference slices are now complete as
recorded below. Actual solver execution qualification remains excluded by product-owner direction.

### Steel elastoplastic routing increment

The existing tabulated-plasticity and calibrated Voce paths now require the exact source Material
revision to be classified as `metal`. Modeling resolves that pinned revision through the Property
Set and Material State chain; an application guard rejects non-metal input before reading curve
bytes, and migration 039 adds a PostgreSQL insert trigger for the same invariant. The frontend
shows the elastoplastic workbench only for the class pinned by the State and offers explicit
append-only State rebase guidance when the Material head changed. The demo seed reclassifies and
rebases legacy demo Material/State/Property revisions through protected APIs. Existing
OpenRadioss LAW36 and Abaqus golden outputs are unchanged.

### Ogden--Prony and Catalog genealogy completion

Migrations 046/047 complete the bounded P2 item 4 reference vertical. An elastomer-classified
Material State and exact Property Set revision create a typed one-term Ogden plus one-to-five
shear-Prony IR. Abaqus 2025 and OpenRadioss 2025 are separate explicit targets with immutable
mapping reports and card revisions. Abaqus uses incompressible `D1=0`; OpenRadioss LAW62 records
its fixed `nu=0.495` conversion as `approximated`. Both cards have deterministic golden bytes,
preview/download APIs, and connected UI. Linear-Prony is never silently routed to LAW62.

Migration 048 completes the bounded P2 item 5/T-07 genealogy subset. Process Definition and
Material Lot/Batch stable identities each append immutable typed revisions. A State Genealogy
revision pins the exact Material State revision and optional manufacturing, heat-treatment, and
Lot/Batch revisions under composite organization/project/classification foreign keys, forced RLS,
immutable triggers, and deferred semantic guards. The Material State screen creates and revises
these links without replacing historical facts. Full Process Run inputs/outputs, split/merge, and
multi-lot acceptance remain future T-07 depth.

### Live user E2E evidence (2026-07-16)

The Compose demo was exercised against PostgreSQL 16 through the protected API and connected React
workbench. A new polymer Material was created and carried through:

`Material/State/Property Set -> Specimen/Test Run -> immutable CSV Raw Asset -> normalized Dataset
-> explicit crop Processing Run -> bounded five-start Prony Calibration -> reviewed Candidate
Selection -> IR revision 1 to 2 promotion -> Abaqus mapping preflight -> immutable .inp card`.

The Processing Run succeeded with six normalized and five processed points. All five Calibration
Candidates converged; the reviewed Candidate retained objective, RMSE, residual Artifact and bound
diagnostics. The promoted IR kept the same stable Material Model identity and a new revision ID.
The downloaded 418-byte Abaqus card returned HTTP 200 with a filename-bearing attachment header;
its SHA-256 exactly matched the stored card digest. The card contains `*DENSITY`, `*ELASTIC`, and
`*VISCOELASTIC`. Browser evidence also rechecked the Ogden--Prony LAW62 preview and exact-revision
Process/Lot genealogy. See `docs/17-evidence/reports/user-e2e-evidence-2026-07-16.md`.

## Current remaining work after the bounded P2 verticals

The user-visible reference flows requested by ADR-0020 are implemented. Remaining work is not a
new foundation rewrite; it is production depth and additional vertical coverage:

1. **Catalog/Test depth:** Process Run inputs/outputs, lot split/merge and multi-lot acceptance;
   Test Campaign, Instrument/calibration, standards, condition snapshots, and Specimen source-lot
   genealogy.
2. **Real data breadth:** governed property/curve families, production importer packages and
   mapping approval for selected laboratory formats, arbitrary channel schemas, richer replicate
   statistics, and viscoelastic alignment/master-curve/temperature-shift processing decisions.
3. **Scientific qualification:** domain-approved steel, linear-viscoelastic and hyper-viscoelastic
   schemas, parameter bounds, objective profiles, reference curves, tolerances, uncertainty and
   identifiability policy. The current Voce, two-term Prony, and one-term Ogden paths remain
   reference/non-production.
4. **Exporter productionization:** official version matrices, semantic card parsers/data-checks,
   approved golden fixtures and release policy. Actual solver execution/qualification remains
   explicitly excluded by product-owner direction.
5. **Operations and governance hardening:** production identity/role administration, object-store
   object lock/KMS/retention, package signing/SBOM/scanning, T-35 observability, T-36 restore drill,
   T-37 release-quality evidence, T-38 performance/security acceptance, and external PLM/CAE
   connectors. T-47 must also reconcile and expose an immutable derived output if a later step of a
   multi-output Run fails; committed evidence is never deleted or hidden, but failed Runs must not
   leave it operationally undiscoverable.

## Production-pilot execution baseline (2026-07-16)

ADR-0025 through ADR-0027 and backlog T-39 through T-47 now turn the remaining product depth into a
resumable implementation program. The program preserves migrations 001--048 and prioritizes the
user-visible Material/Test -> Dataset/Processing -> Calibration -> neutral IR -> Abaqus/OpenRadioss
Card -> Bulk Export workflow. Actual solver execution remains excluded. Domain-unapproved numeric
profiles and mappings remain visibly `reference/unapproved`.

The first documentation increment is complete. Official research now records MCalibration only as
a Processing/Modeling/Validation reference, not a product boundary. The stale pre-implementation
design index and README Candidate-selection claims are corrected. Requirements, domain, IR, API,
fitting and test documents now define iterative promotion evidence, governed CSV/TSV/XLSX intake,
immutable Bulk Export Bundles and the user-guide/screenshot gate. A Korean task-oriented guide
covers current Steel, Polymer and Elastomer workflows and reuses nine dated E2E screenshots through
an explicit manifest; future GUI changes must update the affected guide and capture evidence.

Verification: the guide link/manifest check validated nine documents and seven images. With the
disposable PostgreSQL 16 DSN enabled, the CI-equivalent suite passed 553 Python tests with zero
skips or failures, 28 Vitest tests, ruff, mypy over 469 source files, architecture and contract
checks, OpenAPI compatibility and the production Vite build. T-39 then added migration 049 and the
connected Process Run/Lot/Specimen source workflow. T-40 added migration 050 and the exact
Campaign/Instrument/Calibration/Condition execution-context workflow. T-41 adds migration 051 and
an end-to-end governed CSV/TSV/XLSX intake: immutable source Artifact, explicit `needs_input`
preview, human-approved reusable Import Profile revision, terminal exact-pinned Import Run and
separate raw/normalized SI Dataset revisions. CSV/TSV locale and XLSX sheet/formula/macro/external
link/decompression constraints are explicit; force/displacement derivation requires pinned
   geometry. T-42 then adds exact multi-temperature replicate selection, explicit common-domain
   alignment/statistics, manual or deterministic WLF shift evidence and separate immutable master-
   curve output. T-43 then adds typed scientific profiles and bounded multi-test Ogden fitting;
   T-44 adds append-only human Candidate promotion and T-45 Bulk Export is the next unit.

T-41 verification on 2026-07-16: migration 051 completed an upgrade/downgrade/re-upgrade round trip
on disposable PostgreSQL 16. The CI-equivalent gate passed 576 Python tests with zero skips or
failures, 32 Vitest tests, ruff, mypy over 486 source files, architecture and contract lint,
OpenAPI compatibility and the production Vite build; clean npm install/audit reported zero
vulnerabilities. Live protected API execution imported nine synthetic tensile rows into distinct
raw and normalized revisions, and the connected browser workbench reported no warning/error.

T-42 verification on 2026-07-16: the protected Docker/PostgreSQL workflow processed six synthetic
public relaxation curves at three temperatures into 606 aligned rows, 303 statistical rows and 101
master points. WLF evidence recorded the reference and fitted shifts, while the browser rendered
the shifted replicates, `n=2`, sample standard-deviation band and master curve without console
warnings/errors. Migration 052 completed a fresh 001--052 upgrade plus 052--051--052 round trip on
PostgreSQL 16. The CI-equivalent gate passed 585 Python tests with zero skips/failures, 33 Vitest
tests, ruff, mypy over 497 source files, architecture/contract/OpenAPI compatibility and the
production frontend build; npm audit reported zero vulnerabilities.

## T-43 scientific profiles and multi-test Ogden fitting (2026-07-16)

Foundation version `0.29.0` adds migrations 053 and 054 without rewriting prior revisions.
Migration 053 stores typed Steel Voce, Polymer linear-Prony and Elastomer Ogden--Prony scientific
profile identities/revisions with forced RLS; it does not use JSON/EAV and refuses direct
`domain_approved` self-assertion. Migration 054 stores typed exact-revision Ogden Plans and ordered
calibration/holdout members, terminal Runs, multistart Attempts/Candidates, mode objectives,
convergence, rank/condition, covariance/95% CI or explicit not-estimable state, warnings and exact
diagnostics Artifact references. The same migration expands the typed Test Method constraint with
separate reference planar- and biaxial-tension methods so multi-mode evidence is not mislabeled as
uniaxial execution.

The bounded numerical adapter consumes governed normalized engineering-strain/nominal-stress
curves and supports public one-term incompressible Ogden uniaxial, planar and equibiaxial nominal
responses. Weighting is normalized point → curve → mode; PCG64 starts and SciPy TRF execution are
deterministic. The React workbench is connected to the real API and database and exposes exact
Dataset selection, calibration/holdout roles, mode/curve weights, Candidate comparison,
uncertainty and fitted/residual plots. Single-mode and missing-holdout evidence remain allowed but
visibly warned. No solver is run, no Candidate is automatically accepted and no baseline or source
revision is overwritten. T-44 adds the separate human Candidate selection and repeated append-only
IR promotion gate described below.

Verification: analytic limit/recovery/weight/rank/holdout/deterministic-Parquet tests, protected API
tests, PostgreSQL 001→054→053→054 migration round trip, and a live PostgreSQL
upload→governed normalized Dataset→Plan→multistart fit→Candidate/Artifact persistence test all
pass. Project RLS and immutable-row rejection are exercised. The CI-equivalent gate passed 600
Python tests with zero skips/failures, 35 Vitest tests, ruff, mypy over 512 source files,
architecture/contract/OpenAPI compatibility and the production Vite build; npm audit reported zero
vulnerabilities. Browser verification found no console errors.

## T-44 iterative Ogden promotion evidence (2026-07-16)

Foundation version `0.30.0` adds migration 055 without rewriting any T-43 Plan, Run, Candidate,
diagnostics Artifact, Material Model revision, Solver Card or Release. The migration adds explicit
`ogden_candidate_selection`, `ogden_candidate_selection_revision` and
`ogden_promotion_evidence` tables; no JSON/EAV payload is used. Composite foreign keys and forced
RLS bind every row to one organization/project/classification. PostgreSQL validates succeeded Run,
converged Candidate, candidate/diagnostics digests, exact prior model revision, schema 1.1 owner,
and fitted `mu`/`alpha`. Unique constraints reject Candidate or Selection reuse, and immutable-row
triggers reject updates and deletes.

The protected API records a mandatory human Selection reason and requires the current Material
Model strong `If-Match` before promotion. A successful decision keeps the stable Material Model
identity and appends r2/r3 with one revision-owned evidence record; prior evidence is read through
the revision chain and is never copied into a mutable collection. The React workbench exposes the
human gate, promotion reason, 412 stale-head behavior and newest-first IR history. The existing
Abaqus Ogden and OpenRadioss LAW62 preflight/card paths immediately use the new current revision,
while cards already generated from prior revisions retain their payload and SHA-256. No solver is
executed and no Candidate is automatically accepted.

Verification includes 001→055 and 055→054→055 PostgreSQL 16 migration runs, exact-evidence API
tests, stale ETag rejection, browser selection/promotion/history coverage and a semantic regression
that proves a later IR promotion cannot alter a prior Solver Card payload or digest. The opt-in
`uv run python scripts/seed_ogden_calibration_demo.py --promote` helper creates only public
synthetic evidence and verifies any existing card digests during a local repeated-promotion round.

T-44 verification on 2026-07-16 passed fresh 001→055 and 055→054→055 PostgreSQL 16 migration
runs. The CI-equivalent gate passed 606 Python tests with zero skips or failures, 35 Vitest tests,
ruff, mypy over 518 source files, architecture and contract lint, OpenAPI compatibility and the
production Vite build; clean npm install/audit reported zero vulnerabilities. Two live protected
promotion rounds produced r2 then r3 on one stable model identity and verified three prior Solver
Card revision/digest pairs unchanged. Connected-browser verification recorded the three-revision
history and cards with no warning or error logs.

## T-45 immutable Bulk Export Bundle (2026-07-16)

Foundation version `0.31.0` adds migration 056 without changing any prior Raw Asset, Dataset,
Material Model IR, Solver Card, Release or Artifact. Explicit `export_selection`, append-only
`export_selection_revision`, ordered typed member/omission, durable job and immutable bundle tables
pin concrete raw/artifact/Dataset/model/card revision references. Composite tenant/project/
classification foreign keys, forced RLS, maximum-classification and job-transition guards, a
1,000-component/5-GiB domain limit and lifecycle/provenance/audit revision hooks are enforced in
PostgreSQL. No generic EAV or untyped options payload is used.

The protected `/exports` workbench discovers one Material's exact representations, creates an
immutable Selection, assembles a normalized deterministic ZIP and downloads it with the existing
short-lived Artifact transfer capability. Archives contain the requested raw originals, canonical
Parquet, readable CSV, IR JSON/schema, mapping reports and native Abaqus/OpenRadioss cards plus
`manifest.json`, `checksums.sha256` and `README.md`. Required missing/unauthorized inputs block;
optional omissions remain explicit. Release approval semantics are unchanged. The bounded API
assembles up to 64 MiB inline while persisting queued→running→succeeded/failed. The later T-47
migration 057 adds external worker assembly, committed-output visibility and reconciliation without
rewriting this T-45 Selection/Bundle model.

Live Docker/PostgreSQL evidence created a 22-component DP780 Bundle and obtained `201` download
authorization followed by `200` Artifact transfer. A second Selection created after hook wiring
recorded one lifecycle projection, one provenance Entity and one append-only audit event. The ZIP
download path, manifest/checksum contents and exact representation labels were verified in the
connected browser without visible token or confidential data. Full CI evidence is recorded after
the T-45 gate below.

T-45 verification on 2026-07-16 passed a fresh PostgreSQL 16 `001→056` migration and
`056→055→056` round trip. The CI-equivalent gate passed 613 Python tests with zero skips or
failures, 36 Vitest tests, ruff, mypy over 526 source files, architecture/contract lint, OpenAPI
compatibility and the production Vite build; clean npm install/audit reported zero vulnerabilities.

## T-46 product navigation and user-guide gate (2026-07-16)

The React service now exposes global Dashboard, Materials, Tests, Datasets, Models, Exports and
Governance routes. Tests/Datasets/Models/Governance read the real scoped Material Catalog and route
the user into stable Material identity context. Existing `/materials/{id}` deep links remain the
Overview; `/testing`, `/datasets`, `/models` and `/governance` render only the relevant workbenches
for each exact Material State, reducing unrelated API calls and long-page ambiguity. The global
Governance hub contains the connected Review, Release and Lineage/Audit inspectors.

A Korean navigation/troubleshooting guide describes the end-to-end task order and token, empty
context, class compatibility, mapping and Bundle failures. The machine-readable navigation
contract and `cmp-check-user-guide` verify guide links, seven route labels, screenshot manifest
uniqueness, image existence/size and declared viewport dimensions. The command is available as
`make docs-screenshots` and runs in CI. Docker browser evidence records both the Models hub and
DP780 Models & Cards context with no token or confidential data visible.

T-46 verification on 2026-07-16 passed 614 Python tests with zero skips/failures, 38 Vitest
tests, ruff, mypy over 528 source files, architecture/contract/OpenAPI compatibility, the new
12-document/20-capture/7-route guide gate and the production Vite build. The connected Docker
browser also opened the global Governance hub with the real Review, Release and Lineage/Audit
workbenches and showed no visible application error.

## T-47 observability and isolated recovery subset (2026-07-16)

Foundation version `0.32.0` adds no domain migration and preserves every existing Material, raw
asset, Dataset, IR, Solver Card, Bundle and Release revision. API and worker now own separate
OpenTelemetry SDK providers and export vendor-neutral OTLP/HTTP traces and metrics. The worker
continues the exact W3C trace context persisted on its durable Job into a consumer span. Structured
application logs are fail-closed and allow-listed; raw Uvicorn access logs are disabled so URLs,
queries, headers, bodies, test payloads, tenant identifiers and credentials are not serialized.

The protected operations API and Governance panel expose only one API process's bounded method,
route-template, status-family and latency-bucket snapshot. It requires `audit.read`; the explicit
local demo group receives the read-only auditor role, while production role policy is unchanged.
The Compose demo includes an OpenTelemetry Collector with OTLP/HTTP ingestion and a localhost-only
Prometheus endpoint.

The separate restore image contains the PostgreSQL 16 client while API/worker images do not. The
drill creates a custom-format dump, restores it to a random temporary database, copies immutable
objects to a distinct report directory and verifies typed relation counts, raw/artifact bytes and
provenance references. The successful live run completed in 32.018 seconds, matched raw 18/18 and
total object samples 100/100, found zero dangling lineage edges and cleaned the temporary database.
The demo source contained no Release, which is reported as `not_present_in_source`; Release digest
recovery, scheduled/versioned backups, object lock/KMS/retention, production signing trust,
production-scale benchmark/security acceptance and signed connectors remain ordered T-47 work.
Bounded local benchmark/security and external-worker Bundle assembly are now implemented in later
T-47 subsets below.

The T-47 subset gate passed 627 Python tests with the disposable PostgreSQL 16 DSN and zero
skip/failure, 39 Vitest tests, ruff, mypy over 536 source files, architecture/contract/OpenAPI and
13-document/21-capture user-guide checks, production Vite build and npm audit with zero
vulnerabilities.

## T-47 bounded performance and security acceptance subset (2026-07-16)

`cmp-performance-acceptance` now drives the real Docker API for Catalog latency, authentication
negative cases, a 2 MiB/32-part immutable upload with capability-tamper denial, governed Bundle
authorization/download with SHA-256/size verification, and the real deterministic 64-MiB inline
Bundle builder. It writes canonical JSON plus a detached SHA-256, refuses a dirty source tree and
requires explicit acknowledgement that an Ingestion Event will be appended. Twelve harness unit
tests cover percentile math, finite inputs, Bundle checksum coverage, unsafe URL/path handling and
report substitution.

The accepted local run at commit `9d5c147` recorded Catalog p95/p99 44.292/45.978 ms, upload
throughput 1.266 MiB/s, Bundle download p95 21.894 ms and 64-MiB assembly in 1.950184 seconds with
70,112,942 bytes incremental Python peak. Authentication/path/capability threat checks and all
digests passed. Its canonical report digest is
`3a2464dbf27f5359f19dfc865e0254b68dc55a3040f665a85eb84491b7bbdaa7`.

This closes only the bounded local baseline. The report explicitly says
`production_scale_accepted=false` because the bounded demo exposed 4 Materials rather than 10,000
and used the documented 2-MiB CI upload rather than 2 GiB. The later production-scale subset below
closes the 10,000-Material PostgreSQL search and 2-GiB object streaming conditions without changing
this bounded report.

The complete performance/security branch gate passed 649 Python tests with the disposable
PostgreSQL 16 DSN and zero skip/failure, all 39 frontend tests, ruff, mypy over 540 source files,
architecture/contract/OpenAPI and 13-document/21-capture user-guide checks, the production bundle
budget and npm audit with zero vulnerabilities.

## T-47 supply-chain quality and frontend budget subset (2026-07-16)

`cmp-release-quality` now exports production Python and Node CycloneDX SBOMs, runs `uv audit` and
`npm audit`, records CycloneDX SBOMs and HIGH/CRITICAL Trivy reports for the exact API, worker, web
and restore image IDs, and fails closed on a scanner command/schema error, any known Python
or Node vulnerability or any critical image finding. The evidence index is canonical JSON signed with
Ed25519; verification binds every relative path, byte size and SHA-256 and rejects manifest,
signature, public-key, evidence and path substitution. The local ephemeral signing option is
explicitly an integrity proof rather than builder identity. Production KMS/keyless identity and
trusted-key distribution remain unfinished.

API/worker images discard the unused Debian Perl runtime after the final immutable build step. The
separate restore image calls PostgreSQL 16 binaries directly and also removes its package-management
wrapper/Perl runtime. A live restore drill after minimization still passed all metadata, object and
lineage checks. The signed live scan reported zero known Python vulnerabilities, zero known npm
findings and zero critical findings across all four images.

React domain workbenches are now route/context lazy-loaded. The initial production JavaScript fell
from 541,662 to 269,778 bytes and the largest lazy chunk is 88,163 bytes. Every production build
enforces a 300,000-byte entry and 120,000-byte lazy-chunk ceiling. The complete branch gate passed
637 Python tests (including nine supply-chain regressions and the PostgreSQL suite) with zero
skip/failure, all 39 frontend tests, ruff, mypy over 538 source files, architecture/contract/OpenAPI,
13-document/21-capture user-guide checks, the production bundle budget and npm audit with zero
vulnerabilities.

## T-47 external Bundle worker and output reconciliation subset (2026-07-16)

Migration 057 adds a typed, append-only `exporting.bulk_export_output_commit` with explicit
organization/project/classification foreign keys, SHA-256/size constraints and forced RLS. Bulk
Export Job transitions now include `reconciliation_required` and `reconciling`; PostgreSQL guards
attempt increments and legal state changes. Existing Selection, source revision, Bundle and Artifact
rows are neither rewritten nor replaced.

Estimates above the default 64-MiB inline limit return `202 Accepted`. The composed worker claims a
Job with `FOR UPDATE SKIP LOCKED`, builds the same normalized deterministic ZIP bytes in a temporary
file, streams them through Artifact staging/finalization, records immutable output evidence, and
then projects the Bundle. If that last projection fails, the Job and Export Center expose the
committed SHA-256/size as `reconciliation_required`; a later worker claim links the existing output
without reading sources or assembling a second archive. The API lists Job history, attempt, state
and committed output, and the React Export Center polls active states and distinguishes output
commit from Bundle availability.

The Docker/PostgreSQL demo deliberately lowered the inline limit to 16 KiB and completed a
22-component DP780 Job. Output commit `7842eac7-aa26-4b4e-9492-2d84382b52ae` projected Bundle
`8ba6290e-cb2d-4722-9dc3-7d786d6e8251`; the 21,822-byte Artifact and downloaded ZIP both matched
SHA-256 `04f6aeca5f0f0ff48448dcb0f3c2e4d3e361b890027869b7f3943562d27097ab`.

This subset does not claim the 1,000-component/5-GiB domain limit as production-qualified. The
external path currently bounds each source member at 64 MiB. Hard-kill recovery for a claimed
`running` Job is implemented in the next subset; worker identity/token rotation, soak/fault
acceptance, object-lock/KMS/retention, production signing identity and signed connectors remain
ordered T-47 work. The production-scale subset below closes the 10,000-Material/2-GiB conditions.

Verification passed migration 057 on PostgreSQL 16, including the 057→056→057 round trip. The
CI-equivalent gate passed all 654 Python tests and all 40 Vitest tests with zero skips or failures,
ruff, mypy over 542 source files, architecture and contract lint, OpenAPI compatibility,
13-document/22-capture/7-route user-guide checks, the production Vite build and npm audit with zero
vulnerabilities. The entry JavaScript remained within budget at 269,827 bytes and the largest lazy
chunk remained 88,163 bytes.

## T-47 external Bundle worker lease recovery subset (2026-07-16)

Migration 058 adds explicit `lease_token`, `heartbeat_at` and `lease_expires_at` columns to the
typed Bulk Export Job. Queued external work is claimed atomically with `FOR UPDATE SKIP LOCKED`.
An active worker renews its lease between bounded assembly, hashing and streaming phases; an
expired `running` or `reconciling` Job is reclaimed with a new opaque fencing token and incremented
attempt. PostgreSQL transition guards reject an expired heartbeat renewal, and every output,
reconciliation, success or failure mutation verifies the current unexpired token. Inline assembly
remains lease-free, terminal Jobs clear all lease fields, and the token is never returned by the API.
An active Job left by a 057 process receives a deterministic expired bootstrap lease during upgrade,
so it is reclaimed rather than orphaned; downgrade is blocked while any active leased Job remains.

The API and Export Center expose only heartbeat and recovery-deadline timestamps so operators can
see when an active Job becomes reclaimable. The default lease is 120 seconds; the synthetic Docker
demo uses 15 seconds to make failure recovery observable. Organization/project/classification RLS
and the immutable Export Selection, source revision, Artifact output commit and Bundle boundaries
are unchanged.

The live Docker/PostgreSQL fault drill created a 22-component, 22,117-byte DP780 Selection. A
manually claimed Job remained `idle` to another worker before its deadline, then was recovered after
expiry and completed as attempt 2 with Bundle `f23a24ad-6a97-416b-8155-c0061f64871d`. Lease fields
were cleared at success. Unit and PostgreSQL tests additionally prove heartbeat extension, direct
expired-heartbeat rejection and stale-worker fencing.

The CI-equivalent gate passed all 658 Python/PostgreSQL tests and all 41 Vitest tests with zero
skips or failures, ruff, mypy over 544 source files, architecture and contract lint, OpenAPI
compatibility, 13-document/23-capture/7-route user-guide checks, the production Vite bundle budget
and npm audit with zero vulnerabilities. Migration 058 also passed 058→057→058 against the live
Docker PostgreSQL database before the hard-kill drill. A separate live 057-active→058 upgrade gave
the legacy Job an expired bootstrap lease, rejected an unsafe downgrade and completed it as attempt 2.

## T-47 10,000-Material and 2-GiB production-scale subset (2026-07-16)

No migration or existing row rewrite is introduced. Catalog search now returns an explicit
`total_count` computed by `count(*) OVER()` on the same organization/project/classification RLS
filtered current-head query as the bounded result page. Dashboard, Material list and global module
hubs display this authorized total rather than misrepresenting a page length as Catalog size.

`cmp-performance-fixture` is an acknowledged, opt-in tool for an isolated PostgreSQL composition.
It appends deterministic synthetic Material identities and immutable r1 revisions until the target
cardinality is reached, rejects unsafe database targets by default and is idempotent at the revision
level. `cmp-performance-acceptance` schema v2 generates deterministic source bytes in bounded
chunks, prehashes them, streams them through the actual multipart API and records maximum chunk and
incremental Python allocation as first-class evidence. `--require-production-scale` fails unless at
least 10,000 Materials are visible and exactly 2 GiB is digest/size verified.

The live isolated Docker/PostgreSQL run inserted 9,996 synthetic rows beside four demo Materials in
17.418893 seconds. Thirty Catalog requests returned 100 bounded rows with `total_count=10000` at
p95/p99 182.128/187.088 ms. The API finalized 2,147,483,648 bytes as 32 64-MiB parts in 89.048012
seconds at 22.999 MiB/s; terminal digest and size matched. The maximum generated chunk was
67,108,864 bytes and peak incremental Python allocation was 67,164,359 bytes, below the 192-MiB
gate. Bundle download, the 64-MiB inline builder and auth/capability/path negative checks also
passed. Report source commit is `b506f6415f49774fb32692cf680ed56c866e9902`; canonical report
SHA-256 is `96d75ca787695ad5848b0b65562554a93f8aa63dd204b82d92e159f723cef481`.

The complete branch gate passed 661 Python/PostgreSQL tests and 41 Vitest tests with zero skips or
failures, ruff, mypy over 545 source files, architecture and contract lint, OpenAPI compatibility,
13-document/24-capture/7-route user-guide checks, the production Vite bundle budget and npm audit
with zero vulnerabilities. Focused deterministic-source, fixture-safety and request-timeout tests
also passed after the final timeout bound.

This subset does not qualify the 5-GiB Bundle domain ceiling. The next T-47 unit below adds the
bounded production-pilot mixed-workload Compose fault gate. Independent object-storage failure and
overnight endurance remain production-infrastructure conditions, followed by object
lock/KMS/retention plus production signing identity, then signed connectors and worker
identity/token rotation. Licensed solver execution remains out of scope.

## T-47 mixed-workload soak and Compose fault subset (2026-07-16)

No migration, domain revision or object mutation is introduced. `cmp-soak-fault-acceptance` accepts
only loopback endpoints and repository-owned Compose files, requires explicit disruption approval
and allow-lists `postgres`, `api`, `worker` and `web`. Every pause/stop records a pending inverse
operation and the finalizer restores them in reverse order. Workload evidence stores no response
body, token, raw value or exception text.

Three concurrent threads execute Catalog, Bundle-list and health reads before, during and after
PostgreSQL pause/unpause plus API/worker/web stop/start. Expected fault-window errors are separate
from ordinary errors. Recovery requires all relevant probes to remain continuously stable for two
seconds, not one lucky response. Final acceptance also requires ordinary p95 below two seconds,
per-service memory growth below 512 MiB, unchanged authorized Material cardinality and a fresh
download of the exact same immutable Bundle bytes.

The first live run correctly failed because three in-flight recovery-tail requests were labeled
ordinary after a single successful probe. All services recovered, Material count, Bundle digest and
resource gates were intact. The harness was strengthened to use continuous multi-probe stability
and to report compact error-type counts. A 60-second diagnostic then passed before the final run.

The final source commit `4563bd68c4e36fe743099e9e62733979b85e54bd` run lasted 373.361256
seconds with 3,243 samples, 102 expected fault-window failures and zero ordinary failures.
Catalog/Bundle-list/health p95 were 223.419/45.849/23.423 ms. PostgreSQL, API, worker and web
recovered in 2.809797/8.362320/3.200068/2.665459 seconds. API/PostgreSQL/worker memory growth was
11,219,763/4,508,876/125,829 bytes and web reclaimed 6,081,741 bytes. The Catalog stayed at exactly
10,000 and Bundle `8ba6290e-cb2d-4722-9dc3-7d786d6e8251` retained 21,822 bytes and SHA-256
`04f6aeca5f0f0ff48448dcb0f3c2e4d3e361b890027869b7f3943562d27097ab`. Canonical report SHA-256 is
`d68253e7ce75528a0f807b945f98019e37f55052b2f8457d54076ff6e85f535c`.

This is a five-minute production-pilot composition gate, not an overnight endurance or independent
production object-storage failover claim. The local filesystem adapter is shared by API and worker;
object lock/KMS/retention and externally managed object-store fault evidence remain the next T-47
unit, followed by production signing and signed connector identity/token rotation.

The complete branch gate passed 672 Python/PostgreSQL tests and 41 Vitest tests with zero skips or
failures, ruff, mypy over 547 source files, architecture and contract lint, OpenAPI compatibility,
13-document/24-capture/7-route user-guide checks, the production Vite bundle budget and npm audit
with zero vulnerabilities.

## T-47 governed S3-compatible storage adapter subset (2026-07-17)

Production composition no longer permits the local filesystem object store. The new adapter keeps
SDK types outside domain/application code and validates bucket versioning, Object Lock and exact
default SSE-KMS key identity before serving traffic. Multipart staging sends SHA-256 checksums;
final promotion reads a pinned staging version and uses an atomic `If-None-Match: *` write with an
explicit checksum, KMS key and retain-until date. Only non-authoritative staging versions can be
discarded through the application port.

Five SDK-contract/acceptance tests cover unsafe production fallback, governance mismatch,
KMS/COMPLIANCE promotion, multipart checksum verification and the redacted live-gate workflow;
the complete Artifact-focused subset passes 14
tests. These tests do not qualify a real cloud KMS or WORM bucket. Live bucket/KMS/failover evidence
remains pending credentials and approved infrastructure. The current atomic promotion ceiling is
5,000,000,000 bytes, which covers the qualified 2-GiB ingestion path but not the domain 5-GiB Bundle
ceiling. Production signing identity and signed connectors remain the next implementation units.

## T-47 external production signing adapter subset (2026-07-17)

Release-quality generation now accepts a no-shell external signer command with a two-step
describe/sign protocol. The process sends canonical manifest bytes and SHA-256, pins an
independently supplied Ed25519 public key and expected key ID, verifies the returned signature
locally, and records provider/key identity in the signed manifest. Verification can pin the same
trust pair. Signer stderr, private keys and credentials are not copied into evidence.

`CMP_ENVIRONMENT=production` rejects ephemeral and supplied PEM private keys; those remain local
integrity modes only. Twelve release-quality unit tests pass, including a real child-process signer,
untrusted identity, corrupted signature and production-local-key rejection. No production
HSM/Vault/keyless endpoint or key ceremony was available, so live production identity acceptance
remains pending. Signed delivery connectors and runtime identity/token rotation are next.

The complete branch gate passed 680 Python/PostgreSQL tests and 41 Vitest tests with zero skips or
failures, ruff, mypy over 551 source files, architecture and contract lint, OpenAPI compatibility,
13-document/24-capture/7-route user-guide checks, the production Vite bundle budget and npm audit
with zero vulnerabilities. The workstation has neither GNU Make nor Git Bash, so the exact commands
from `scripts/ci.sh` were run in PowerShell rather than through the `make ci` wrapper.

## T-47 signed connector and worker identity subset (2026-07-17)

Existing tenant-scoped transactional-outbox events can now be wrapped in a deterministic externally
signed delivery manifest and published through HTTPS REST/webhook or immutable object storage.
HTTP delivery requires an exact digest acknowledgement and event-ID idempotency key; redirects,
URL credentials/query secrets and non-loopback HTTP are rejected. Object delivery uses immutable
organization/project/event/digest keys and is replay-idempotent. Existing outbox lease, retry,
poison and published-time records remain the delivery authority.

Worker OIDC tokens and optional receiver bearer tokens can be atomically rotated through bounded,
non-symlink files and are read for every cycle/delivery. Production rejects an inline worker token.
Ten new connector/rotation tests pass together with the existing event/worker tests. A real external
receiver, signer, IdP/workload-identity sidecar and during-delivery token-rotation/outage drill were
not available and remain live production acceptance conditions.

The complete connector branch gate passed 690 Python/PostgreSQL tests and 41 Vitest tests with zero
skips/failures, ruff, mypy over 555 source files, architecture and user-guide checks, the production
web bundle budget and npm audit with zero vulnerabilities.

## Final composed product-pilot acceptance gate (2026-07-17)

`cmp-product-pilot-acceptance` is the read-only final gate for the local PostgreSQL composition. It
authenticates through the explicit demo issuer and resolves the exact DP780 Steel, linear-Prony
Polymer and Ogden--Prony Elastomer Material identities. For each path it verifies typed
Material/State/Property revisions, required test context, normalized/processed evidence, a
human-promoted fitted solver-neutral IR, and the required downloadable Solver Cards. Card preview
and download bytes must match the persisted card SHA-256 and required Abaqus/OpenRadioss keyword
markers; mapping values are restricted to the six published statuses.

The same gate downloads a complete 22-component Bulk Export ZIP and independently verifies the
archive digest, manifest digest, every `checksums.sha256` entry, safe unique paths, zero omissions,
and raw/Dataset/IR/schema/mapping/native-card representation coverage. A read-only PostgreSQL
transaction then confirms the API's Material, Material Model and Bundle stable identities are
durable rows. Unit regression covers valid bundles, component tampering, missing representations
and archive digest mismatch. Actual solver execution remains excluded, and live external
KMS/WORM/HSM/receiver/endurance acceptance still requires approved infrastructure and credentials.

The clean-tree gate passed on commit `a401b34ccc2ff4df0fd577f70c29b9e8a839bf41` against the live
Docker API and PostgreSQL 16.14 demo. It verified three workflows, five required downloadable
cards, and Bundle `f23a24ad-6a97-416b-8155-c0061f64871d` with 22 components and zero omissions.
Canonical report SHA-256 is
`d0ca507324e9b94b558d52b0c3fbf5d7e9c5fb947a67cc98adbf388155466f4e`; the Bundle SHA-256 is
`2957276e628bf4d97d4724baabe72da67671bc924c15077ea7e2ae441f774fac`.

The final CI-equivalent gate passed 695 Python/PostgreSQL tests and 41 Vitest tests with zero skips
or failures, ruff, mypy over 557 source files, architecture and contract lint, OpenAPI
compatibility, 13-document/24-capture/7-route user-guide validation, the production Vite bundle
budget and npm audit with zero vulnerabilities.

