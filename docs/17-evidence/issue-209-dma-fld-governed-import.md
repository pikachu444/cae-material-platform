# Issue #209 — DMA·FLD governed import

## Authority and current-state audit

Work continues on `codex/issue-209` after fast-forwarding the preserved branch to
`origin/main` `a512c76aa55b5423e06f6b09eb1015ddf28f3aca`. The latest issue body, the
schema-driven integration source packet, traceability P4/G6, and the exact DMA/FLD source-v2
record schemas are the authority for this unit.

The existing product already preserves immutable CSV/TSV/XLSX bytes, creates versioned human-
confirmed Import Profiles, pins exact Test Run and Profile revisions, writes separate raw and
normalized governed Dataset revisions, converts the same source to canonical Test Data, and pins
exact Material, Material State, and Test Run revisions. Issue #209 does not replace those paths.
It adds only the missing bounded behavior for `dma_frequency_temperature_sweep` and
`forming_limit_diagram`.

`dma_strain_sweep`, general source-v2 bundle compatibility, new common units or a bundle adapter,
and DMA-to-master-curve/Prony/IR wiring belong to #246 and are forbidden in this delivery.

## Primary user journey and acceptance

| Part | Issue-owned journey |
| --- | --- |
| Setup | An authenticated modeler opens **Modeling → Data** with one exact synthetic non-production Material, Material State, and Test Run revision. The modeler has either a DMA frequency-temperature sweep or an FLD CSV/TSV/XLSX source. |
| Actions | Upload the immutable file; inspect the selected worksheet/header; select DMA frequency-temperature sweep or forming limit; map every required channel and its declared unit; review the normalized-unit consequence; preview the governed curve; enter the mapping reason and Test Data metadata; save; then open the saved exact Test Data revision for review. |
| Visible outcome | DMA requires temperature and frequency independent channels plus storage and loss modulus dependent channels, with optional tan delta. FLD requires minor strain and major strain. The channel table, source preview, graph preview, status, and actionable diagnostics stay in the existing two-pane Modeling Data workspace without a third inspector. FLD remains first-class saved Test Data even though this issue adds no FLD processing. |
| Persistence/read-back | A successful save retains the raw Artifact bytes and SHA-256, immutable Import Profile revision, raw and normalized governed Dataset revisions, and canonical Test Data revision pinned to the exact Material, Material State, and Test Run. Reload reads the saved exact revision and its source/channel provenance. |
| Preserved state | Original bytes and earlier revisions never change. Original unit text and normalized values remain separate. DMA frequency is represented with the existing explicit-legacy `Hz` channel contract; this issue does not extend the common unit registry. No value is silently resampled, smoothed, sorted, defaulted, or dropped. |
| Recovery | Missing columns and invalid cells produce deterministic row/cell/channel diagnostics. NaN/Inf, duplicate DMA temperature-frequency coordinates, duplicate FLD minor-strain coordinates, non-positive frequency, sub-absolute-zero temperature, and negative modulus fail closed. The bounded policy is whole-file rejection: the Raw Artifact and failed Import Run remain, while no Dataset or canonical Test Data revision is created. Corrected input can be retried; replaying the same idempotency key and immutable inputs reads the same Run instead of duplicating it. |
| Owned scope | Governed-import contract/domain/API/persistence, the two new profile rules, canonical adapter semantics, bounded synthetic fixtures, focused unit/API/PostgreSQL/browser tests, Modeling Data controls, current guide/screenshots, and delivery records. |
| Forbidden shortcuts | No `dma_strain_sweep`; no source-v2-wide adapter or compatibility claim; no new common `Hz`/bundle/unit adapter; no DMA-to-Prony/master-curve/IR route; no FLD simulation; no generic Catalog-only bypass; no source mutation, row dropping, hidden default, arbitrary EAV, route-specific 4K override, CSS zoom, or transform scaling. |
| Exact acceptance | Positive CSV/TSV/XLSX cases and canonical round-trip pass for both schemas. Four required DMA channels (plus optional tan delta) and two FLD channels are independently enforced. Unit, missing/duplicate, NaN/Inf, temperature/modulus/frequency boundary, and signed FLD strain cases are deterministic. PostgreSQL proves tenant scope, diagnostic persistence, and idempotent retry. The exact canonical Test Data revision can be submitted to the existing review flow. The live Modeling Data journey, reload, failure/recovery, five 100%-zoom viewports, required original/crop inspection, independent Balanced audit, and product-owner visual approval pass before merge. |

## Verification record

| Gate | Result |
| --- | --- |
| Focused domain/API/migration tests | `71 passed` for governed tabular rules, canonical adapter/API, review evidence, source integration, demo hydration, and migration behavior. |
| Modeling Data React tests | `40 passed` for the workbench and intake journeys. |
| PostgreSQL acceptance | The Issue #209 persistence/idempotency/diagnostic test, governed Test Data review test, migration upgrade/downgrade/re-upgrade test, and touched Ogden governed-import regression each passed in an isolated database. |
| Atomic failure regression | The PostgreSQL Issue #209 test injects failure immediately after the normalized Artifact is finalized and again after the raw Dataset revision is staged. In both cases the failed Run and one immutable derived Artifact remain, governed Dataset and canonical Test Data identity counts do not increase, same-key replay is identical, and a new-key retry creates exactly the raw/normalized Dataset pair. |
| User-guide contracts | `32 passed` for user-guide and documentation-impact contract tests; `cmp-check-user-guide` reports 116 registered current captures with no orphan image. |
| Build and style | The production web build, affected Ruff checks, `cmp-check-doc-impact`, and `git diff --check` pass. The web bundle remains under its hard budget; the existing `common-processing-workbench` and `material-library` warning thresholds are reported but do not exceed the enforced limit. |
| Compose and browser | Canonical Compose preflight, migration, demo seed, live save/reload, deterministic failure, corrected retry, exact review reachability, and the five-viewport capture complete successfully. |
| Visual evidence integrity | [`visual-evidence.yaml`](images/issue-209-dma-fld-governed-import/visual-evidence.yaml) lists 77 PNGs. Every file matches its SHA-256, byte count, and pixel dimensions; all originals and direct 100%-pixel crops were opened at original resolution. |

One intentionally over-broad PostgreSQL selection combined unrelated catalog tests in a shared
session and exposed two existing order-dependent fixture assumptions: a fixed lifecycle count and a
fixed reference method code. No product code or fixture was weakened. The four changed or directly
touched PostgreSQL cases were rerun independently and passed, which is the applicable #209 boundary.

At 1366×768, 1440×900, 1920×1080, 2560×1440, and 3840×2160, browser zoom is 100%, DPR is 1, and
document/body horizontal overflow is zero. Header, navigator, mapping controls, decision/diagnostic
surface, and graph remain visible and bounded. The 1440 rejected-DMA primary journey intentionally
preserves the last accepted graph while showing the failed draft; clean secondary viewport sessions
show no session Test Data. Both paths prove that the rejected Import Run creates no Dataset or
canonical Test Data revision.

The available Windows displays are 2560×1440 and 2560×1600 at 96 DPI and 100% scale. The automated
3840×2160 CSS viewport establishes geometry only; physical 4K readability remains deferred to #223.
The independent Balanced audit and Product Owner visual-geometry decision are recorded against the
exact publication candidate and PR before merge.
