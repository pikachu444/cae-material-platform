# Issue #261 B4 combined CSS ownership integration evidence

**Status: PASS — completed combined batch and Main live/browser/original-resolution visual acceptance.**

This bounded B4 record integrates the approved B1 Modeling, M2 Materials and M3 governance
ownership handoffs without changing DOM, API, copy, state or revision contracts. The independently
accepted source production tree is `92ec19bada2c4b5f3db91d4c661317b13b347b4a` on frozen base
`4d53d95ce926b96b84e47f9d942127f0853d8ed2`. After PR #311 merged as
`fa417118cf77989d617024e68a4730d828d790df`, the same production meaning was replayed as
`59224efb39a8c2a325f0b3bfdcba4a6d76584cbc`. The resulting product tree is unchanged from the
accepted source payload; only PR #311's two evidence-hash corrections are additionally present.

## Coherent completed batch

The single task-local batch ran in this order: **fresh build → seed twice → live captures → E2E
contracts → cleanup**. It used isolated project `cmp-demo-test-261b4`, browser zoom 100%, DPR 1,
and the five CSS viewports `1366x768`, `1440x900`, `1920x1080`, `2560x1440`, and `3840x2160`.
The permanent `cmp-local-demo` before/after identity and count were unchanged. The disposable
isolated project was removed after the batch.

Authoritative machine-readable artifacts are
[`combined-batch-results.json`](images/issue-261-b4-css-ownership-integration/combined-batch-results.json),
[`combined-live-measurements.json`](images/issue-261-b4-css-ownership-integration/combined-live-measurements.json),
and the 207 PNG / 8 JSON files retained beneath
`docs/17-evidence/images/issue-261-b4-css-ownership-integration/`.
The image manifest is accompanied by six registered exact-hash duplicate-group sidecars so every
historical/provenance image remains addressable without broad duplicate exemptions.

## Coverage and automated result

| Area | Captures / files |
| --- | ---: |
| Activity live five-viewport | 13 |
| Administration access live five-viewport | 6 |
| Administration database live five-viewport | 10 |
| Administration records live five-viewport | 5 |
| Administration object states | 5 |
| Materials live | 15 |
| Modeling exact-stage five-viewport | 104 |
| Modeling compatibility alias | 1 |
| Deterministic Materials contract | 16 |
| Schema-bundles administration | 32 (27 PNG + 5 JSON) |
| **Combined evidence total** | **207 PNG + 8 JSON** |

The combined E2E status is **PASS**. The issue-261 M2 Materials contract, schema-bundles
administration, Administration button semantics, and Administration database workflow each passed.
There are 21 live metric records; horizontal overflow, visible alerts, and console errors are all
zero. Modeling has 24 measurements with zero modeled issues. The compatibility alias is preserved.

Prior evidence is reused by exact hash where it is the same artifact: Administration access `6/6`,
Materials contract `15/16`, and Modeling `93/104`. The remaining differences are dynamic output
identity or capture data, not a new UI design. The imported task-specific B1, M2 and M3 evidence
directories and reports remain retained and independently addressable.

## Main visual and user-impact acceptance

Main opened the combined originals at source resolution and accepted the ownership regression across
the three required #249 synthesis axes:

- **Carbon information hierarchy — PASS.** Flat panes and dividers remain primary; status and
  action hierarchy is preserved without decorative nesting or cascade drift.
- **COMSOL engineering task flow — PASS.** Materials supports exact detail, download and
  Start Modeling; Modeling preserves Data → Process → Fit → Export; Administration preserves
  plan → confirm → apply/read-back; Activity keeps error and recovery reachable.
- **SAP responsive/wide-screen logic — PASS.** All five CSS viewports retain a full-shell
  adaptation, tables/graphs/previews grow into available space, navigators and forms retain readable
  bounds, and no clipping, horizontal overflow, or unreachable action was observed.

User-impact acceptance is **PASS**: Materials keeps exact URL/revision/download and fail-closed
behavior; Modeling keeps exact session pins; Activity keeps error/recovery behavior. No cascade,
state, URL, revision, download, or recovery regression was found.

This is CSS geometry evidence. Actual-device Windows 4K physical readability remains the existing
#223 boundary and is not claimed here.

## Causal N/A and deferred boundaries

The following bounded diagnostics were not replayed because their causes were proven outside CSS:

1. `review-publication-recovery.spec.ts` stops before UI setup because the current seed has no
   `CMP-DEMO-DP780-NEUTRAL` record with a `neutral_material` binding. The failure is an API fixture
   mismatch, not CSS. Replacement coverage passed with exact URL/revision/download/fail-closed
   Materials assertions, exact Modeling session pins, and Activity recovery.
2. `capture_current_product.py --only-materials` assumes Search is the initial `/materials` state,
   while the approved #249 state correctly opens Browse. The diagnostic showed the Browse tree,
   exact DP780 r1, no alert, and `searchCount=0`; the replacement was the settled Browse → Filters →
   exact-detail five-viewport live capture.
3. The canonical live seed has no released CAE card. The deterministic M2 fixture supplies the exact
   card preview/download journey at all five viewports. Supporting live Materials images that retain
   async loading/checking labels are preserved as provenance only; settled M2 evidence and browser
   assertions are the acceptance record.

## Documentation-impact publication resolution

The required one-shot check on the new-main replay failed because the imported standalone M2 proof
covered only `layout.css + materials.css`, not the complete combined visual-source set. PR #311's 21
Modeling manifests were no longer changed candidates after merge, proving that the former stacked
history cause had disappeared and leaving one bounded aggregation gap.

The publication correction does not rewrite a historical manifest or PNG and does not run another
capture batch. It adds one current B4 publication proof that reuses the already registered,
byte-identical M2 five-viewport triplets and binds them to the exact ten combined CSS hashes. The
checker change is limited to three composition rules needed by this existing evidence: a current
combined proof may be a superset of an unchanged historical proof; same-issue registered
before/after evidence may be reused across task evidence roots; and a TSX change that adds only
side-effect imports of concurrently changed CSS is attributed to those CSS files rather than counted
as a second visual implementation change.

Focused contract verification passes: documentation-impact tests `95/95`, inventory tests `20/20`,
deterministic inventory `2,106 / 1,777 / 6`, and worktree documentation impact `10 visual sources /
10 byte-identical CSS visual sources by #261`. This resolves the former
`DEFERRED_STACKED_HISTORICAL_EVIDENCE` publication boundary without guide-image churn, historical
evidence manipulation, or a new visual-validation framework.

## Disposition and inventory checkpoint

The preserved ownership disposition is: Modeling **505 moved + 38 deferred**; Materials **257
moved**; Governance **506 dispositions** (**505 tuples + CSS-0725 peer**). M4/M6/shared seams,
HOLD **446 rows**, M1E, and other features remain out of scope for this B4 integration.

The regenerated combined inventory remains **2,106 selector rows / 1,777 rule groups** with M4
**314**, HOLD **504**, and **6** cross-CSS duplicate groups. These residual routes remain explicit;
they are not silently closed by this evidence unit.

The combined B4 status is therefore **PASS for Main live/browser/visual acceptance and focused
publication evidence gates**. The coherent five-viewport batch is reused without replay. #223
physical readability remains deferred, PR #311 is merged, and #261 stays open for the residual
2,106 selector rows.
