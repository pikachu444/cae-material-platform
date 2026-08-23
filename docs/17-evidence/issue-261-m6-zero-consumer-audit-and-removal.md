# Issue #261 FE-06 M6 — zero-consumer legacy CSS audit and removal

Status: **Main live/browser/original-resolution acceptance passed; Balanced independent audit approved**.
The candidate is based on merged `main` `593dfd3dab3a22ec93bc9d9a078c05b6f1f1c329` (PR #318).

## Bounded architecture and acceptance packet

- Authority: active owner instruction for #261 M6, Issue #261, parent #249, the PR #318 exact
  `556`-row / `495`-group handoff, and the FE-00 through FE-06 roadmap.
- Existing behavior classification: CSS ownership migration was complete through PR #318; M6 removal
  was missing. The handoff rows were production-loaded legacy CSS candidates, not pre-approved
  deletions.
- Change class: behavior-preserving structural CSS debt removal. No semantic visual movement,
  DOM/class rename, route, copy, API, state, dependency, or exact-revision change is included.
- Primary journey: Materials Browse/Search → exact Material revision → Start Modeling → exact Test Data
  → Data → Process → Fit → explicit saved model → Export → solver card → Materials read-back/download.
  Visible and reload/read-back outcomes, exact identity/revision, session continuity, persistent graph,
  invalidation, retry, and recovery remain unchanged.
- Owned production files: only `apps/web/src/styles.css` and
  `apps/web/src/design/layout.css`. Evidence, deterministic audit/apply/guard scripts, the selector
  inventory, and frontend-guard baseline are supporting artifacts. Both registered legacy hotspots only
  lose proven-unused rows.
- Recovery: Git retains the complete frozen base. The transformer always reconstructs the two outputs
  from that base and refuses any tuple, declaration, source-context, REMOVE, or HOLD drift.
- Forbidden shortcuts: no selector-sized issues, micro-batches, name-search-only deletion, selector
  copy, DOM/class rename, golden masking, route-specific override, CSS `zoom`, blanket scaling,
  fabricated content, or product behavior/API change.

## Frozen proof and disposition

[`issue-261-m6-zero-consumer-audit.json`](../../scripts/fixtures/issue-261-m6-zero-consumer-audit.json)
is the row-complete authority. It maps every PR #318 tuple one-to-one and records the static producer and
reference result, non-CSS production-bundle result, exact live selector result, disposition, owner, and
removal condition. Its handoff digest is
`41a6cda0826c330fbf430462e8dbfc0de8041f2cd9344baf9ce1c08c66ffc900`.

| Disposition | Rows | Groups | Rule |
| --- | ---: | ---: | --- |
| REMOVE | 511 | 462 touched | All three axes are zero: static, production bundle, and live DOM. |
| Fully removed groups | — | 452 | Every selector row in the frozen source group passed REMOVE. |
| Partially shrunk groups | — | 10 | Only independently proven comma-selector peers were removed. |
| HOLD false positives | 45 | 43 | At least one static, bundle, or live signal remains. |
| Resulting legacy inventory | 67 | 65 | 22 prior accepted-in-place rows plus 45 M6 HOLD rows; zero M6 candidates. |

The `45` HOLD rows remain owned by their exact current legacy source. Each fixture row contains one or
more of `STATIC_SUBJECT_EVIDENCE_OR_NO_SUBJECT`,
`PRODUCTION_BUNDLE_SUBJECT_EVIDENCE_OR_NO_SUBJECT`, and
`LIVE_EXACT_SELECTOR_MATCH_OR_QUERY_ERROR`, plus its candidate owner and this executable removal
condition: resolve every recorded signal to zero, identify or retire the exact producer topology, then
repeat the production build and the 13-topology live selector audit. The implementation does not
reclassify these false positives as dead debt.

The live audit exposed twelve exact selectors that the static scan alone would have misclassified,
including `.materials-scroll-rail-y`, the narrow-viewport `.materials-scroll-rail-x`, Fit-stage composed
selectors, the active configured-step selector, the ready-to-create Export state, and the interactive pan
state. They are HOLD. Twenty-seven HOLD rows
also retain production-bundle subject-token evidence. This is why zero static evidence alone was never
treated as deletion authority.

## Static, bundle, and live evidence

- Static: the frozen inventory searched quoted JSX/TS literals, templates, conditional branches,
  producers, references, and test-only evidence. A REMOVE row has a real subject token and no static
  producer/reference signal.
- Production bundle: [`issue-261-m6-production-bundle.json`](issue-261-m6-production-bundle.json)
  audits every frozen subject token in Vite `.js` and `.html` assets before and after removal. All 511
  REMOVE rows remain at zero; all 27 HOLD rows that had bundle evidence retain it.
- Live DOM: `document.querySelectorAll` audited 465 unique exact selectors across thirteen settled
  route/state topologies at 1440×900 before removal and all five CSS viewports after the first candidate.
  Both audits cover all 556 rows and have zero query errors. The five-viewport audit exposed
  `.materials-scroll-rail-x` only in narrow Export, so it was restored and reclassified HOLD before final
  acceptance. The removal decision therefore has route/state and responsive proof rather than a
  name-search inference.
- Production output: TypeScript, Vite, and the raw/gzip bundle budget pass. The largest entry is
  260,615 bytes against the 300,000-byte hard ceiling; the largest lazy chunk is 116,596 bytes against
  131,000 bytes.

## Live visual and responsive acceptance

The accepted manifest is
[`live/manifest.json`](images/issue-261-m6-zero-consumer-audit-and-removal/live/manifest.json).
It records thirteen production topologies at 1366×768, 1440×900, 1920×1080, 2560×1440, and
3840×2160, browser zoom 100%, DPR 1, and 305 before/after artifact pairs (65 full-screen originals plus
header, navigator, table/form, graph, native-preview, and stage-control crops where applicable).

Main opened all 610 registered before/after PNGs at original resolution. Of 305 pairs, 272 are
pixel-identical; 50 of 65 originals are pixel-identical. Twenty-seven changed artifact pairs are
confined to three deterministic seed identities: the declared curve revision hash, generated Material
Model IR and Mapping Profile UUID/hash lines in the native Export preview, and the selected distribution
candidate hash. Six additional Materials Search pairs contain only 2–15 raster pixels of variance
(maximum channel delta 5) across the large viewports. Identity difference bounds are at most 32 pixels
high; layout, content extent, controls, graph/native-preview geometry, clipping, and interaction
reachability are unchanged. Maximum changed ratio is `0.01517335` on the narrow Export crop and
`0.00415504` on any full-screen original.

The #249 synthesis passes all three mandatory axes:

- Information hierarchy: **PASS**. Results, exact identity/revision, dominant graph/native preview,
  and subordinate evidence/delivery surfaces remain unchanged.
- Engineering task flow: **PASS**. Materials-to-Modeling and Data → Process → Fit → Export continuity,
  saved model selection, and Materials read-back remain unchanged.
- Responsive/wide-screen composition: **PASS** at all five CSS viewports. Shared shell, panes, tables,
  graphs, and native preview preserve their accepted geometry without route-specific scaling.

Actual physical Windows 4K readability remains `DEFERRED_TO_223`. There is no observed geometry,
clipping, overflow, or interaction regression to defer.

## Main qualitative checklist

| Item | Main disposition | Evidence |
| --- | --- | --- |
| 긴 탐색 트리의 독립 스크롤 (Q-01) | PASS | Materials and Modeling navigator originals/crops retain the visible local scroll topology. |
| 긴 결과 목록의 독립 스크롤 (Q-02) | PASS | Materials results and related-data lists preserve independent result behavior; the sparse search state has no fabricated scrollbar. |
| Materials 탐색 행의 밀도·정렬 (Q-03) | PASS | Materials navigator rows, glyph grid, identities, and selection are pixel-identical. |
| Fit 리본과 그래프 공간 보존 (Q-04) | PASS | Fit ribbon/stage-control and engineering-graph crops retain all groups and graph dominance at five viewports. |
| 공학 그래프 축의 충돌 없는 배치 (Q-05) | PASS | All graph crops retain axis/title/unit separation with no collision. |
| 곡선 범례와 결정 상태의 분리 (Q-06) | PASS | Legend and decision surfaces remain separate across curve, Fit, and distribution states. |
| 반응형 그래프 glyph·stroke 비율 (Q-07) | PASS | Five-viewport graphs retain exact geometry; no SVG stretch or scale rule was added. |
| 항복 응답의 양의 시작점·정확한 표기 (Q-08) | PASS | The accepted synthetic tensile/Fit states and labels are unchanged. |
| 오버플로 표시의 발견성·조작성 (Q-09) | PASS | Navigator, native preview, and long mapping tracks remain visible and reachable. |
| Fit 범례의 곡선 충돌 회피 (Q-10) | PASS | Fit graph/legend crops are pixel-identical to the accepted base. |
| Fit 탐색 레일의 Materials 일관성 (Q-11) | PASS | Materials and Modeling rails retain their shared flat-pane rhythm and distinct task controls. |
| 정확한 Export selected model 분기·unit system 선택 (Q-12) | PASS | Export exact branch, selected model, capability-backed units, and mapping content persist; only generated UUID/hash text differs. |
| Export 행 문법·보조 문구 (Q-13) | PASS | Compact setup/result grammar and consequence copy are unchanged. |
| Export 준비 상태의 단일 표현 (Q-14) | PASS | Ready/review/blocker state remains single and consistent. |
| 공학 그래프의 데이터 여백·축 정확성 (Q-15) | PASS | Curve, Fit, polymer, elastomer, and distribution graphs retain domain headroom and units at every viewport. |
| Export native solver-card preview 우선순위·독립 스크롤 (Q-16) | PASS | Native preview stays dominant with an independent local scrollbar and bounded Mapping details. |
| Administration Object 목록의 식별성·용어 (Q-17) | PASS | Database/list/preview originals and crops are pixel-identical to the accepted identity-first base. |
| Administration `Add`·저장 뷰 동작 (Q-18) | PASS | Existing accepted Administration interaction/runtime contract is unchanged; this unit has no DOM or handler change. |
| Administration `Link Type` cardinality·정확한 개정본 (Q-19) | PASS | Exact revision/cardinality surfaces and API/DOM contracts are unchanged. |
| 전체 화면 폭·고해상도 전 제품 구성 (Q-20) | PASS | Five viewport originals span the shell; graphs/tables/previews grow while navigators and prose stay bounded. No new wide override, zoom, or scale exists. |

## Verification and delivery state

Completed implementation checks:

- exact frozen transformer: **PASS**, 511 REMOVE rows; 462 touched groups; 452 full removals; 10
  partial shrinks; 45 HOLD rows retained;
- inventory and frontend guard: **PASS**, 67 rows / 65 groups, zero deletion candidates, 0 guard
  violations / 15 registered warnings;
- M6 regression: **PASS**, 5/5;
- cumulative inventory, M4, and FE-06 regression slice: **PASS**, 28/28;
- production build/bundle audit: **PASS**, including 24/24 bundle-budget tests;
- complete web regression suite: **PASS**, 71 files / 412 tests with two workers;
- Storybook production build: **PASS** (the existing vendor chunk-size warning remains non-blocking);
- Compose preflight, disposable seed, thirteen route/state captures, reload/read-back assertions, and
  disposable cleanup: **PASS**;
- five-viewport comparison and Main acceptance: **PASS**, status
  `ACCEPTED_MAIN_VISUAL_AND_RUNTIME`;
- user-guide and documentation-impact checks: **PASS**, 20 guide documents / 124 current captures /
  4,692 local links / 8,682 images and 636 changed files / two visual sources;
- `git diff --check`: **PASS**;
- canonical Balanced independent completed-result audit: **APPROVE** after correcting the screenshot
  manifest to name the actual M6 capture procedure and rerunning the guide check.

Publication and remote-main read-back are recorded in the #261 and #249 delivery comments after merge.
Issue #261 and parent #249 remain open by owner instruction; no issue is created, deleted, closed, or
reopened.
