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
| Persistence/read-back | The Task 1 structural round trip projects 6 Tables and 5 direct Link Types and proves deterministic apply, exact-source export and no-op re-plan; unchanged-fixture application remains Task 2-owned. The browser restores category, query, exact data revision and local scroll state. Human business-key references resolve to a pinned target revision that does not move when the target gets a newer revision. |
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

Task 2 owns the additional common units. The approved source files already normalize to deterministic
canonical bytes and report the still-unsupported units precisely. The Task 1 PostgreSQL structural
round trip substitutes only those unit tokens in the test helper; it does not alter the source fixture
or weaken validation. Full unchanged-fixture apply is therefore intentionally left for the next issue
work unit. The structural round trip now preserves every applied field's original schema ID,
version, source file, file SHA-256 and JSON location, and exports the exact source-set bytes and
media type rather than replacing them with the canonical adapter output.

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
| Focused Python aggregate | PASS — 195 tests across source adapter, bundle, contract, migration, API and user-guide coverage, including the exact original-source export and unbound exact-link category regressions |
| Full frontend regression | PASS — 63 files, 351 tests |
| PostgreSQL bundle/configurable data integration | PASS — 10 tests, including 6 Tables, 5 direct Links, per-field original coordinates/hash, exact human-reference pin, category search, no-op apply and byte-identical source-set export/re-plan |
| Frontend component tests and TypeScript | PASS — 31 focused tests across routing alias, category tree, exact direct links and pinned detail; typecheck passes |
| Production web build | PASS — the existing Browse tree is preload-started as a 17,304-byte lazy chunk without a visual redesign; `material-library` is 114,036 bytes with 16,964 bytes of hard-limit headroom. The unrelated existing `common-processing-workbench` soft warning remains. |
| Browser journey | PASS — 2 Playwright flows render the established Materials workspace with four visible category roots, populated center detail and no normal-surface storage controls |
| Browser geometry | PASS — five required viewports, DPR 1 and 100% zoom; zero measured document overflow |
| Original-resolution review | PASS — 15 originals and 60 direct crops opened at original resolution |
| Canonical Compose | N/A — preflight rejected the running project because it belongs to another preserved worktree; no container or data was changed, and isolated browser fixtures are not represented as Compose persistence |
| Physical 4K readability | DEFERRED TO #223 — 3840×2160 automation proves CSS geometry only |
| Balanced independent audit | PASS — correction re-audit approved exact source preservation, six-source/five-product disposition, per-field origin, exact-source export and Task 2 unit boundary |
| Product Owner geometry approval | Pending before merge |

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
