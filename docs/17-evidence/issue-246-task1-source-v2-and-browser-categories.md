# Issue #246 Task 1 — source-v2 and category browser evidence

This file records the observed starting state, implemented delta and acceptance evidence for Task 1.
The issue body remains the work specification; it is not restated here. Work started from fetched
`origin/main` `3e642e8c3e96e95dd7d10b19d87e18af53db9e7c`, the final merge of #209.

## Starting-state classification

| Classification | Evidence from current `main` |
| --- | --- |
| Complete | Arbitrary-cardinality canonical bundle validation and planning, atomic apply/read-back/export, the Administration bundle screen, immutable Record revisions and exact Record Links |
| Partial | The checked-in source-v2 data formats existed, but only the canonical single-JSON input crossed the format-setting boundary. The Materials tree retained internal Database/Profile/Table/Folder/Record navigation, while the legacy `/database` component separately projected Catalog and multi-hop Workflow. Neither exposed the approved general-user categories. A data item had a user-supplied external key, but format-declared business-key promotion and human reference resolution were absent. |
| Missing | Checksummed multi-file/ZIP source ingestion, source-v2 extension and cardinality adaptation, deterministic six-format/five-link projection, peer-category query/browser UI without internal storage controls, and direct links grouped by category |

Only the missing and partial Task 1 scope changed. Existing bundle publication, immutable revision,
authorization, Administration storage controls and Workflow evidence behavior remain in place.

## Primary acceptance journey

| Part | Observed Task 1 journey |
| --- | --- |
| Setup | An Administrator selects the seven approved bounded source-v2 files. A user opens the established `/materials` workspace. |
| Actions | The browser builds one path-sorted envelope with a SHA-256 for every file, uploads and plans it. In the existing Browse tree, the user expands one or more of four peer category roots without replacing the current datasheet, opens an item and follows a direct exact link. |
| Visible outcome | The source summary shows 7 files, 6 data formats and 2 unit profiles; the unchanged source is blocked with the exact 10 Task 2 unit diagnostics and no actions. Browse shows `Technical Data`, `Test Data`, `Simulation Data` and `Solver Cards` as visible tree roots above their individual items. Item context groups only stored direct links by those categories. |
| Persistence/read-back | The Task 1 structural, supported-unit round trip projects 6 Tables and 5 direct Link Types and proves deterministic apply, source-Artifact export and no-op re-plan; unchanged-fixture application/export remains Task 2-owned. The browser restores category, query, exact data revision and local scroll state. Human business-key references resolve to a pinned target revision that does not move when the target gets a newer revision. |
| Preserved contract/state | Exact source bytes and unsupported source expressions stay in immutable evidence; raw/released revisions are not mutated. Technical Data is required for Test Data. No relation is fabricated between constitutive families or from FLD to a downstream object. Fit execution, selected model, internal IR and Solver Card remain distinct states. |
| Recovery | Unsafe ZIP paths, duplicate paths, digest mismatch, missing source files, ambiguous business keys, missing Technical Data reference and unsupported schema/unit expressions fail with stable diagnostics. No generic EAV or silent unit/default conversion is introduced. |
| Owned scope | Source-set/definition contracts, source adapter, configurable category/business-key contract and migration, exact reference resolution, data-category query, focused Administration UI, category integration into `/materials`, regression/browser tests, guide and evidence. |
| Forbidden shortcuts | No client-authored plan execution, hierarchy inferred from category, transitive relation in the normal context, visible UUID/hash in normal UI, route-specific scaling, fake data or disturbance of another worktree's Compose environment. Approved corrections to the source data formats are explicit and reviewed. |
| Exact acceptance | Contract-first deterministic plan/apply/export/no-op coverage, PostgreSQL exact-pin and negative tests, focused frontend/build tests, five 100%-zoom DPR-1 viewports, direct 100%-pixel crops, documentation gates, Balanced independent audit and Product Owner geometry approval before merge. |

## Implemented delta and ordered boundary

- `schema-definition-source-set` accepts a prebuilt envelope and supports deterministic envelopes made
  from a manifest plus referenced JSON files or one ZIP. Paths, sizes, media types and digests are
  checked before the existing immutable Artifact boundary.
- The source adapter maps the reviewed source semantics into the canonical configurable contract,
  including source/target cardinality direction, reference-only evidence, reviewed names,
  `tensile_to_elastoplasticity`, `Tensile strength`, data categories and business-key metadata.
- The authoritative source still declares `dma_to_elastoplasticity` and its DMA reference. That
  source/Issue mismatch is preserved byte-for-byte in the immutable artifact and recovered-source
  Markdown. The approved product decision for #246 forbids that relation, so the adapter emits
  `CMP-SCHEMA-SOURCE-0029`, retains the reference as evidence and deliberately omits the product Link
  Type. The canonical result therefore contains exactly the five approved direct links.
- Exactly one text/discrete Attribute may be the business key. Registration rejects a conflicting
  explicit external key, duplicate key or missing required nested Technical Data reference. A human
  reference resolves to one exact target revision and remains pinned.
- Every direct-link endpoint projects the data category from the immutable Table revision pinned by
  that exact Record revision. Domain bindings may refine the display category but are optional, so a
  source-defined unbound Record still appears under its correct peer category instead of `Other`.
- `/materials` remains the existing Materials explorer/result/datasheet workspace. Its Browse tree
  exposes the four categories as visible roots with individual data-item
  children. Database/Profile/Table/Folder/Record stays in Administration. There is no separate
  Catalog/Workflow navigator mode. Normal item context contains only
  direct exact links grouped by category; multi-hop provenance remains in Evidence and internal
  revision UUIDs are absent.

Task 2 owns the additional common units. The approved source files normalize to deterministic
canonical bytes and report the still-unsupported units precisely. The Task 1 PostgreSQL structural
round trip substitutes only those unit tokens in the test helper; it does not alter the checked-in
source fixture or weaken validation. Full unchanged-fixture apply and export are therefore intentionally
left for the next issue work unit. For the applied structural package, the round trip preserves each
field's source schema ID, version, file, file SHA-256 and JSON location, and exports that package's
exact source-set bytes and media type rather than replacing them with the canonical adapter output.

The Product Owner rejected both a central category landing and a later separate database category
tree because they replaced the established Materials design. The final correction removes that
competing component, keeps `/materials` as the user route, and adds only the required branches and grouped
direct links to the established tree/detail surfaces. Rejected interpretations are retained as before
evidence rather than represented as the accepted product. The first audit's contract finding about
per-field source coordinates and exact-source export is corrected in the current packet.

## Verification record

| Check | Result |
| --- | --- |
| Source adapter and bundle unit tests | PASS — 32 tests |
| Focused Python aggregate | PASS — 195 tests across source adapter, bundle, contract, migration, API and user-guide coverage, including structural source-Artifact export and unbound exact-link category regressions |
| Full frontend regression | PASS — 63 files, 351 tests |
| PostgreSQL bundle/configurable data integration | PASS — 10 tests, including 6 Tables, 5 direct Links, applied-field source coordinates/hash, exact human-reference pin, category search, no-op apply and byte-identical structural source-set export/re-plan; unchanged-fixture apply/export remains Task 2-owned |
| Frontend component tests and TypeScript | PASS — 31 focused tests across routing alias, category tree, exact direct links and pinned detail; typecheck passes |
| Production web build | PASS — the existing Browse tree is a 19,131-byte lazy chunk without a visual redesign; `material-library` is 116,355 bytes with 14,645 bytes of hard-limit headroom. The unrelated existing `common-processing-workbench` soft warning remains and there are no budget violations. |
| Browser journey | PASS — the live PostgreSQL/API/worker/frontend journey renders the established Materials workspace with 3 Technical, 9 Test, 3 Simulation and 1 Solver Card records; the selected tensile detail shows its material, setup, conditions, measured results, curve coverage and exact direct links after reload, DMA and FLD show credible engineering values, and DMA has no elastoplasticity relation; no HTTP route is mocked |
| Browser geometry | PASS — the live journey passes five required viewports, DPR 1 and 100% zoom with zero measured document overflow |
| Original-resolution review | PASS — Main opened all 15 final originals and all 60 direct 100%-pixel crops at original resolution after the last data correction |
| Canonical Compose | PASS — a dedicated PostgreSQL composition plus the real API, worker and Vite frontend persisted the full demo seed; a second identical seed kept the visible 3/9/3/1 result |
| Physical 4K readability | DEFERRED TO #223 — 3840×2160 automation proves CSS geometry only |
| Balanced independent audit | PASS — the same canonical auditor found no remaining issues after verifying the byte-identical source fixture, exact live runtime provenance, all registered asset hashes, the focused 34-test regression, Q-01–Q-20 dispositions and the preserved Task 2 boundary |
| Product Owner geometry approval | PASS — after reviewing the presented 1920×1080, 2560×1440 and 3840×2160 category/detail originals, the Product Owner instructed that PR #250 be merged on 2026-08-14 |

## Q-01–Q-20 main-orchestrator visual disposition

The checklist applies once to the complete Task 1A visual packet. `N/A` rows name the missing screen
topology; they do not silently waive an applicable Materials or Administration requirement.

| ID | Result | Evidence or topology reason |
| --- | --- | --- |
| Q-01 | PASS | The fully expanded populated category tree overflows locally at 1366×768 and exposes its independent reserved rail: [`navigator crop`](images/issue-246-source-v2-categories/after/crops/issue246-categories-1366x768-navigator-crop.png), [`measurement`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-1366x768.json). |
| Q-02 | N/A | The accepted category fixture has at most nine result rows and this packet does not target a long or empty result-list state; the shared result-scroll component is unchanged. |
| Q-03 | PASS | The approved shared Standard tier produces 30 px tree rows; disclosure, type glyph and complete stored identity stay on one aligned row without rail collision: [`navigator crop`](images/issue-246-source-v2-categories/after/crops/issue246-categories-1366x768-navigator-crop.png), [`measurement`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-1366x768.json). |
| Q-04 | N/A | No Fit ribbon or graph is present on the Task 1A Materials/Administration states. |
| Q-05 | N/A | No engineering plot axes are present on the target states. |
| Q-06 | N/A | No curve legend is present on the target states. |
| Q-07 | N/A | No responsive SVG plot is present on the target states. |
| Q-08 | N/A | No hardening-response plot is present on the target states. |
| Q-09 | PASS | The long tree uses a distinct reserved track and proportional thumb; its concise identities remain readable in the captured pixels: [`1366 crop`](images/issue-246-source-v2-categories/after/crops/issue246-categories-1366x768-navigator-crop.png). |
| Q-10 | N/A | No Fit legend or collision region is present on the target states. |
| Q-11 | N/A | No Modeling Fit rail is present on the target states. |
| Q-12 | N/A | No Modeling Export setup is present on the target states. |
| Q-13 | N/A | No Modeling Export setup/result columns are present on the target states. |
| Q-14 | N/A | No solver-card creation readiness state is present on the target states. |
| Q-15 | N/A | No engineering plot is present on the target states. |
| Q-16 | N/A | No Modeling Export preview or mapping column is present on the target states. |
| Q-17 | PASS | The retained Administration source-plan state keeps the existing identity-first object list and governed task language: [`1920 original`](images/issue-246-source-v2-categories/after/originals/issue246-source-plan-1920x1080.png). |
| Q-18 | N/A | Task 1A does not change Add Table/Add Attribute draft flows; the target Administration state is source-bundle validation, not definition creation. |
| Q-19 | PASS | Related data shows only the stored Technical and Simulation direct links with exact `r1` pins; the live DMA detail is also asserted to contain no elastoplasticity relation: [`detail crop`](images/issue-246-source-v2-categories/after/crops/issue246-detail-1920x1080-detail-crop.png). |
| Q-20 | PASS | The shell spans 1920/2560/3840 and keeps the tree adjacent to the expanding result/datasheet region without page overflow or a route-specific scale workaround: [`1920`](images/issue-246-source-v2-categories/after/originals/issue246-categories-1920x1080.png), [`2560`](images/issue-246-source-v2-categories/after/originals/issue246-categories-2560x1440.png), [`3840`](images/issue-246-source-v2-categories/after/originals/issue246-categories-3840x2160.png). Automated 4K geometry does not claim physical readability, which remains `DEFERRED_TO_223`. |

## Final live Materials measurement report

All values come from the accepted category state at browser zoom 100%, DPR 1 and the shared Standard
display tier. The 8 px pane padding and 32 px result row are the shared component values; all other
values are recorded in the linked measurement JSON files.

| Metric | 1366×768 | 1440×900 | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Menu height | 50 | 50 | 50 | 50 | 50 |
| Shell used width | 1366 | 1440 | 1920 | 2560 | 3840 |
| Left / right outer gutter | 9 / 9 | 9 / 9 | 9 / 9 | 9 / 9 | 9 / 9 |
| Navigator width | 288 | 288 | 288 | 288 | 288 |
| Main result width | 1054 | 1128 | 1608 | 2248 | 3528 |
| Inspector width | 0 | 0 | 0 | 0 | 0 |
| Normal pane padding | 8 | 8 | 8 | 8 | 8 |
| Result / tree row height | 32 / 30 | 32 / 30 | 32 / 30 | 32 / 30 | 32 / 30 |
| Data font size | 14 | 14 | 14 | 14 | 14 |
| Active display tier | Standard | Standard | Standard | Standard | Standard |
| Filled primary commands | 0 | 0 | 0 | 0 | 0 |
| Nested persistent cards | 0 | 0 | 0 | 0 | 0 |
| Page horizontal overflow | 0 | 0 | 0 | 0 | 0 |

Measurements: [`1366`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-1366x768.json),
[`1440`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-1440x900.json),
[`1920`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-1920x1080.json),
[`2560`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-2560x1440.json), and
[`3840`](images/issue-246-source-v2-categories/after/measurements/issue246-categories-3840x2160.json).

The exact paths, dimensions, hashes, measurements and immutable visual references are registered in
[`visual-evidence.yaml`](images/issue-246-source-v2-categories/visual-evidence.yaml).

| State | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | --- | --- | --- |
| Browse category tree | [1920](images/issue-246-source-v2-categories/after/originals/issue246-categories-1920x1080.png) | [2560](images/issue-246-source-v2-categories/after/originals/issue246-categories-2560x1440.png) | [3840](images/issue-246-source-v2-categories/after/originals/issue246-categories-3840x2160.png) |
| Direct linked item detail | [1920](images/issue-246-source-v2-categories/after/originals/issue246-detail-1920x1080.png) | [2560](images/issue-246-source-v2-categories/after/originals/issue246-detail-2560x1440.png) | [3840](images/issue-246-source-v2-categories/after/originals/issue246-detail-3840x2160.png) |
| Seven-file source validation boundary | [1920](images/issue-246-source-v2-categories/after/originals/issue246-source-plan-1920x1080.png) | [2560](images/issue-246-source-v2-categories/after/originals/issue246-source-plan-2560x1440.png) | [3840](images/issue-246-source-v2-categories/after/originals/issue246-source-plan-3840x2160.png) |

The direct 100%-pixel detail crops used to check the populated center workspace are retained for
[categories 1366](images/issue-246-source-v2-categories/after/crops/issue246-categories-1366x768-detail-crop.png),
[categories 1440](images/issue-246-source-v2-categories/after/crops/issue246-categories-1440x900-detail-crop.png),
[categories 1920](images/issue-246-source-v2-categories/after/crops/issue246-categories-1920x1080-detail-crop.png),
[categories 2560](images/issue-246-source-v2-categories/after/crops/issue246-categories-2560x1440-detail-crop.png),
[categories 3840](images/issue-246-source-v2-categories/after/crops/issue246-categories-3840x2160-detail-crop.png),
[detail 1366](images/issue-246-source-v2-categories/after/crops/issue246-detail-1366x768-detail-crop.png),
[detail 1440](images/issue-246-source-v2-categories/after/crops/issue246-detail-1440x900-detail-crop.png),
[detail 1920](images/issue-246-source-v2-categories/after/crops/issue246-detail-1920x1080-detail-crop.png),
[detail 2560](images/issue-246-source-v2-categories/after/crops/issue246-detail-2560x1440-detail-crop.png), and
[detail 3840](images/issue-246-source-v2-categories/after/crops/issue246-detail-3840x2160-detail-crop.png).

The manifest is the canonical original-resolution inventory: 10 accepted references, 70 artifacts
from the two rejected interpretations, 90 final-candidate artifacts and 3 byte-identical current-guide
copies. Its 173 paths, byte counts and SHA-256 values, plus all 148 PNG dimensions, were checked against
the files after the final capture.
