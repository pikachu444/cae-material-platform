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

Pending implementation, deterministic gates, independent Balanced audit, product-owner visual
approval, PR publication, and merge read-back.
