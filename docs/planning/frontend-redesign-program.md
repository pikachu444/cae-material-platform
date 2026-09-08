# Frontend redesign program

Status: redesign in progress; material-centered reader baseline accepted; governance applied; connected reader implemented locally with bounded validation; owner acceptance, write journeys, cutover and retirement remain open
Authority: accepted owner discussion, the canonical data-management policy, and ADR-0036/ADR-0037;
audits are evidence for this target, not product authority.
Related decisions: [ADR-0036](../../adr/0036-material-only-revisions-and-data-links.md), [ADR-0037](../../adr/0037-task-first-frontend-foundation.md)
Current route: this program has owner priority before backlog #195. It does not claim that the
program is complete, and it does not create a substitute issue, PR or merge record.

This is the single planning entry for the integrated redesign. It covers code, documentation,
screens and runtime diagnosis; workflows and assets; information architecture; frontend foundation;
validation; cutover and retirement. RD-01 is the isolated frontend foundation and reader prototype;
it does not connect the production API or complete the later write, validation, cutover or retirement
rows. Production behavior, OpenAPI contracts and migration remain bounded follow-on work.

## 0. 현재 결정과 다음 구현 — 2026-09-07

사용자는 [소재 중심 대표 화면](../../design/frontend-reader-proposals/material-workspace/index.html)의 큰 구조에 동의하고 저장소 규칙 정리안 적용을 지시했다.
현재 화면 기준은 [UI 원칙](../product/frontend-ui-principles.md)에 둔다. 소재 카드/표·트리와 별도 필터·오른쪽 미리보기·확대 상세와 복귀를 이어가며, 필터 항목·열·문구·시각 세부사항은 조정 가능하다.
실험과 솔버 카드 직접 조회·다운로드를 함께 제공한다. 합성 시안은 실제 API나 공학 기본값의 검증을 대신하지 않는다.

규칙의 대체 관계는 [ADR-0038](../../adr/0038-development-guidance-and-reader-baseline.md), 완료 증거·작업 위치·다음 행동은 [현재 상태](frontend-redesign-status.md)에서 확인한다.
개인 모델/effort/오케스트레이션 비용 정책은 사용자의 후속 논의 요청으로 보류한다. 고급 모델의 설계와 낮은 비용 모델의 구현을 나누는 목적을 폐기하거나 Main 직접 구현을 영구 강제하지 않는다.

2026-09-08 현재 대표 조회 화면은 실제 API에 연결되어 있다. 다음 작업은 시안 대비 사용자 검토와 남은 검증을 마무리하고 등록·처리·반복 통계의 연결 업무로 확장하는 것이다. 처리 결과 자체의 저장·다운로드와 모델/카드 생성은 구분한다.
현재 규칙 적용은 DB/API 이관·제품 전환·모든 화면의 시각 승인을 뜻하지 않는다. 아래 진단·비교 이력은 필요한 자산과 이전 판단을 찾는 자료이며 과거 여섯 시안을 반복 제작하라는 지시가 아니다.

## 1. Product outcome and preserved journeys

The material-centered reader baseline now follows UI principles and ADR-0037's 2026-09-07 amendment. Earlier Granta and six-concept notes below preserve the comparison history; they are not a competing current target.

The product remains a CAE material information and modeling application. The redesign makes the
next engineering decision visible at the left of the task surface, keeps result data dominant, and
keeps exact context through saved work. It preserves authorization, scientific validation and
release meaning.

The primary pilot is:

```text
ordinary-ID Test Data search/detail
  → explicitly associated stored Solver Card
  → native download
```

Test Data and Solver Cards each have a direct path and can open independently. A related card is
opened only through the stored association; a title, sibling name or `latest` lookup is never a
relationship. A title metadata PATCH updates the same ordinary row and leaves its association
intact with zero nonmaterial domain revisions.

The second journey remains:

```text
exact Material / State / Test Data
  → Data → Process → Fit → explicit saved model
  → Export → Solver Card → Materials read-back/download
```

The new information policy is [Data management policy](../product/data-management-policy.md): only
Material information edits have domain revision history. State/PropertySet, Specimen, TestRun,
TestData, Dataset, Selection, Mapping Profile, Process, Model, Solver Card and Link data are
stable-ID saved objects; renames preserve links and do not stale science. Input/options changes
affect current eligibility, while immutable saved bytes and saved-result input/settings remain
intact.

## 2. Current diagnosis evidence

The following is the read-only baseline used for D0. Counts are inventory observations, not quality
targets:

| Area | Observation | Consequence for the program |
| --- | --- | --- |
| App/API entry | `app.tsx` is 48 lines and `api.ts` is a 30-line facade | Keep the public entry points as compatibility boundaries while moving ownership behind them. |
| Modeling workbench | `common-processing-workbench` is 2,878 lines, with 56 states and 31 effects | Characterize transitions before extracting controller, stage and result boundaries. |
| Other hotspots | material pages 2,851 lines; Administration records 2,336; intake 1,260; plot 1,502 | Extract by responsibility and journey, not by line count alone. |
| CSS | 43 CSS files and 24,044 raw lines | Establish token and feature ownership before retiring legacy selectors. |
| Bootstrap | seven resource loads use mixed-error `Promise.all` behavior | Preserve current behavior during diagnosis and make partial failure visible in the connected reader. |
| Guards | only `stepsText`, `beforeunload` and `NewSession` are guarded; no SPA navigation guard | Treat save and navigation recovery as an explicit acceptance case. |
| Races | late save/plan races are hypotheses, not confirmed defects | Add evidence before changing the state machine. |
| Fit boundary | parser behavior is stronger than its HTTP surface | Use the parser as a characterization source and prove the API boundary before extraction. |
| Build baseline | old build `cfeb4f57` passes 74 tests in 8 files; Material chunk 130,825 raw / 131,000 budget, gzip 32,772; entry 214,102 raw / gzip 65,283 | Preserve the measurements as historical baseline; measure the new reader and foundation separately. |
| Harness | old route measure harness fails on the old Fit selector and there is no current-user performance record | Do not present the historical API p95 of 182 ms as a frontend metric. |

Historical screen observations are retained at
`docs/user-guide/images/current/{materials-search-1920x1080,materials-search-long-1920x1080,material-detail-2560x1440,modeling-data-1920x1080,modeling-export-1920x1080,modeling-fit-polymer-stale-1920x1080}`.
They are diagnosis evidence, not a new design approval.

The extraction must preserve frontend unit semantics (`value * scale + offset`), deviations as
scale-only, channels/bands, the processing registry and override reasons, and session transitions
including saved Fit, parser, blend, DMA and Prony behavior. Plot crop, fit and necking commands are
real workbench behavior, not decorative graph state.

## 3. Workflow, asset and parity map

The parity map is organized by user task rather than by old page names.

| Task surface | Existing evidence to characterize | Target foundation behavior |
| --- | --- | --- |
| Materials / Test Data | Search, browse, exact detail and current links | Task-left navigation; result table remains dominant; Test Data opens directly and keeps ordinary identity. The reader shows each engineering value with its unit and known condition/applicability, with the associated next action beside the selected result. |
| Solver Cards | Existing card paths, preview and native download | Direct Cards path; explicit association is shown in context; stored properties remain individually readable with value/unit/applicability; native bytes and card JSON remain separate. |
| Modeling Data / Process | Curve explorer, inclusion/visibility, processing registry and saved output | Compact task rail, persistent graph, explicit process output and recovery. |
| Modeling Fit | parser, candidates, recommendation versus selection, saved result, stale state | Candidate comparison and explicit engineer selection stay distinct; source and result context remain exact. |
| Modeling Export | mapping, target tuples, native preview and blockers | Native preview is dominant; mapping status is truthful and unsupported values block creation. |
| Administration | database/profile/table/folder/record definitions | Definitions remain available in Administration; they do not replace the normal Test Data/Card tasks. |
| Activity | request list, local history and review/job/release actions | Keep role-correct queue and distinct local history, without a KPI dashboard. |

The connected reader corpus is ordinary Test Data saved objects authorized by `DATASET_READ` and
stored Solver Cards authorized by `EXPORT_READ`; it does not require a Catalog-published binding just
to query or download. Catalog publication and card release retain their separate meanings where
those lifecycle contracts apply.

Registered references and screenshots document existing behavior and engineering semantics. Current layout authority is UI principles, not the old navigation or section 4's historical candidates. Q items apply to the affected task and state.

The intake and exchange contracts carried into parity work are bounded and explicit:

- governed CSV/TSV/XLSX accepts 16 MiB, 100,000 rows and 512 columns; UTF-8 CSV uses comma or
  semicolon, TSV uses tab, and decimal/header choices are explicit;
- XLSX selects one sheet or an explicit `auto` single-sheet choice; formulas, macros and external
  references are rejected; ZIP content permits 128 members, 32 MiB total expanded content and a
  100:1 expanded ratio;
- canonical JSON accepts 25 MiB, 512 channels and 1,000,000 points; preview defaults to 500 and
  caps at 10,000, while full download returns the exact stored document;
- source-v2 Record JSON is a separate schema intake and does not become an automatic Record to
  compute bridge;
- raw intake is `create/resume → stream complete → server preview/detect → confirm mapping →
  import → read back`;
- ProcessOutput is direct JSON. Dataset CSV/Parquet are supported for bulk transfer, not generic
  processed CSV/XLSX. Native file bytes are not card JSON;
- mapping reports are `exact`, `transformed`, `approximated`, `unsupported`, `ignored` and
  `not_applicable`; unsupported blocks, and approximation/ignore require explicit acknowledgement.

Scientific parity remains bounded: the metal reference full flow is the representative path;
single-temperature DMA and relaxation go directly to Fit/Prony; fixed-frequency DMA temperature
sweeps retain explicit TTS; multi-DMA backend support is the completed #391 base for active #392
and next #380 export work; elastomer remains restricted; common Export outside the metal reference
is not qualified. No production standard, material family, constitutive model, optimizer policy,
solver card or validation threshold is selected here.

## 4. Current comparison candidates

이 절은 이전 비교와 피드백의 **평가 이력**이다. 제목/anchor는 기존 링크 보존을 위해 유지한다. 아래 “current”, “unselected”, “recommended”는 당시 상태이며 현재 구현 기준은 §0과 UI 원칙이다. 네 독립안·두 종합안을 다시 제작하지 않는다.

### Accepted reader interaction — 2026-09-07

The owner accepts the interaction direction without selecting any visual candidate. A single row
click selects the record and opens a concise preview; double-click, visible Open detail action or
Enter opens the full detail. Double-click is never the only way to reach detail. Collapsing preview
restores list space; returning from full detail restores query, page, scroll and selected identity.
Preview contains the key conditions, a small curve or individual saved properties and file status.
It must not crowd out essential result columns or cover pagination. The later owner-requested prototype
interaction uses a right-side preview beside results on desktop, with an actual expandable tree
and separate filters. Do not silently substitute a bottom preview at that target size. Constrained
screens need an explicit focused-preview/return design. Other historical alternatives keep their own
body layouts. Page/filter changes clear an off-page selection, and late responses must
not reopen or overwrite a different selection. Keyboard focus returns to the selected row when it
still exists. Validate the actual sequence with paginated results and delayed detail responses.

Status: implemented in the six P2-C5 static reader proposals under `design/frontend-reader-proposals/`.
P2-C4 remains a frozen comparison of the earlier click behavior. P2-C5 validates actual single-click,
native double-click, visible detail action, Enter/Escape, selected identity and paginated list return.
Its static data does not prove asynchronous API recovery or reload persistence. Those remain RD-02/03
acceptance. This does not update the earlier isolated React foundation's separate A/B reader behavior.
Visual selection is still open. A checkpoint commit may preserve unselected proposals and governance;
it does not mean visual approval, production readiness or authorization to merge/cut over.

### P2-C4 supersession — 2026-09-06 owner feedback

The owner rejected the common reader geometry and the report that showed only E/F. P2-C4 rebuilds
all six bodies independently: A Granta facets/right technical sheet; B Total Materia search console
and full document; C Koyfin linked analytical windows; D TradingView screener and chart terminal;
E document index and technical sheet; F transposed condition matrix and analysis notebook.
The owner prefers the prior calm light blue-gray left task navigation across these alternatives.
That shared rail does not require shared body geometry. Earlier E-first advice is withdrawn pending
the new independent comparison. All six remain unselected. Review must consider the whole screen:
typography, color, lines, numerical fields, conditions, graph, list scale and reachable actions.
Current source and evidence status are recorded in [the versioned checkpoint](frontend-redesign-status.md).
The bounded visual prototype uses 48 synthetic tests and 8 card metadata records; it does not inherit
the previous prototype's scale, asynchronous recovery or persistence acceptance. Real connected
implementation still must meet those product requirements. The owner requests independent review
and a report displaying all six before selection. The descriptions below document the superseded
P2-C3 proposals and cumulative requirements; they do not constrain P2-C4 to identical preview panes.

### Historical P2-C3 comparison

The six candidates use the same Test Data and stored Solver Card, the same exact conditions, values,
units, identities and native bytes, and the same direct lookup, association, download and recovery
journey. The result columns remain independent: data name, material, specimen, test type,
temperature and strain rate. Card results likewise keep card name, material, solver, model, unit
system and file format in separate columns. Values and units occupy separate readable positions.
All six candidates are unselected proposals for comparison. Main recommends evaluating E first for
daily lookup; that recommendation is not an owner selection or production visual approval.
The current refinement starts with an unselected, full-width list, an optional selected-item preview
and an expanded detail. Pagination and return behavior are part of the comparison, not deferred
behind a small static sample. The corpus extends the preserved reference with synthetic pagination
records; it is not a measurement of actual service data size.

### Candidate A — Granta technical sheet

A uses slate application chrome, a light task rail and precise technical sections. Its broad list
opens a bottom Test Data preview or a compact Card sheet where space permits. Expanded detail
retains the structured datasheet and large engineering curve, without a permanent list/detail split.

### Candidate B — Total Materia lookup and export

B uses a white workspace with a prominent title, purple module marker and restrained tab line.
Outlined search fields and a meaningful green Search action lead to a quiet wide result table.
Selecting a row now opens a bounded preview; explicit expansion opens the focused detail page with
list return. Test Data preserves horizontal space for curves; Card facts and download lead before
the optional native-file disclosure. This preview step is a deliberate CAE adaptation.

### Candidate C — Koyfin framed analysis

C uses charcoal outer navigation with separate light work panels, small dark panel-name tabs,
fine cell rules and a pale selected row. The selected analysis keeps a dominant white chart and
its condition/property information below or beside it according to available width. The broad
watchlist is the initial workspace; the selected analysis panel is optional and dismissible. No
dashboard widgets or invented market functions are implied.

### Candidate D — TradingView screener

D uses a white and near-black screener treatment with compact outlined controls, a broad lightly
ruled table and right-aligned numeric conditions. The selected curve/native detail is a lower
engineering dock opened only on selection for this reader adaptation. It carries no financial chart conventions, fake
filters or decorative status colors.

### Candidate E — lookup/detail synthesis

E combines B's lookup title and quiet result flow with A's precise technical detail. A calm light
task rail and restrained grouping support the broad list, optional bottom curve preview and focused
expanded detail. Cards use a compact right preview when useful list width remains. Main recommends
this as the starting comparison for frequent lookup, without implying owner approval.

### Candidate F — comparison workbench synthesis

F combines D's full-width numeric grid, C's small panel headers and A's semantic rows. Test Data
shows the grid above an optional curve preview. Card results add the primary density, modulus, Poisson
and applicability fields; the lower native section does not duplicate that parameter grid. F is
a deliberate synthesis and is not presented as another external product.

### Cumulative comparison brief

- This is an engineering service: direct Test Data and existing Card lookup/download come first;
  it does not regenerate data.
- Material information edits have domain revision history. Other stable-ID names may change without
  breaking links; saved result inputs/settings and native bytes retain their actual meaning.
- Preserve useful left task navigation, exact ordinary identity, explicit stored associations,
  truthful download/error/recovery states and narrow-screen access.
- Keep values, units, conditions and applicability individually readable. Do not replace them with
  a prose Context block, decorative catalog treatment or overlong title helpers.
- Use four independent reference concepts and two synthesized concepts on the same example data.
  No candidate is final before the comparison.
- On new feedback, record the delta in the current checkpoint: what changes, what remains, and which
  screens or evidence are affected. After compaction or resumption, reopen this brief, the current
  checkpoint, and the actual source/evidence/status before editing; a prior verdict or stale proposal
  is not authority. Keep the immediate next action in the checkpoint.
- Reconcile the whole brief at acceptance. Geometry, interaction evidence and reference fidelity are
  all required; a passing numeric check alone does not approve the visual direction.
- Refine all six concepts together: typography, color, separators, density, useful columns, curve
  space and transitions. A collapsible panel alone does not satisfy whole-screen owner feedback.
- Keep the initial lookup unselected and full-width. Preview is optional; expanded detail returns to
  the same query, filters, sorting, page, page size and scroll. Page/filter/sort changes clear transient
  preview selection; they never select the first row or silently show an off-page detail.
- List pagination remains reachable above any bottom preview. Long lists have real native scrolling.
  Delayed detail responses cannot replace a newer selection or reopen a closed preview. Narrow screens
  may use one focused pane with an explicit return rather than squeeze the list and detail together.
  P2-C3 used specific focused-mode breakpoints; these are historical, not a required layout for every
  later proposal. P2-C5 uses side previews where space permits and normal-flow bottom previews on
  narrower screens. Selection brings an offscreen preview header and its actions into view with
  minimal scrolling; the preview body may continue below the fold. Its full detail is explicit. Collapsing
  retains selection; detail return restores the list offset within the available scroll range.
- Main proactively investigates missing workflows and recommends defaults; the owner should not have
  to invent UX behavior or resolve implementation options. Current explicit feedback overrides stale
  A/B recommendations and fixed legacy pane/style prescriptions.
## 5. Foundation and strategy decision

Three strategies are recorded for a reviewable choice:

| Strategy | Benefit | Risk / limit | Decision |
| --- | --- | --- | --- |
| Existing shell only | Smallest immediate diff | Hotspots, mixed state/render ownership and legacy CSS remain the default; hard to prove parity | Keep as compatibility baseline. |
| Minimal partial cleanup | Extract a few controllers and tokens | Can strand two ownership models and leave the primary task flow fragmented | Use only for bounded characterization or unblockers. |
| Full foundation with reused backend | Isolated task-first shell, explicit ownership and a single later cutover while retaining proven backend contracts | Requires parity evidence, migration work and retirement discipline | **Recommended.** |

The recommended foundation is an isolated `apps/web-next` application with temporary CSS/build
boundaries and the same backend. It is a migration workspace, not a long-term dual application.
React 19, TypeScript 7 and Vite 8 remain. Candidate libraries are:

- Radix generic accessible primitives with CSS Modules and CSS custom-property tokens;
- React Router; TanStack Query and TanStack Table;
- React Hook Form and Zod; Lucide; existing resizable panels;
- ECharts only if the scientific/performance proof supports it; otherwise SVG or Recharts;
- existing Storybook, Vitest, Testing Library and Playwright remain the verification layer.

External maintained scientific libraries are allowed when their numeric behavior is validated. Use
packages rather than copying or forking a whole repository. If shadcn source is used, this program
requires an explicit local source-maintenance owner. There is no blanket prohibition on a UI kit or
dependency; every candidate still needs capability, accessibility, bundle and ownership evidence.
No giant common framework is introduced.

## 6. Delivery governance and staged program

The program uses one foundation, a representative connected reader, validation, write journeys,
expansion, a single cutover and retirement. The status rows are:

| Row | Status | Exit evidence |
| --- | --- | --- |
| RD-00 | complete | Policy, program, ADRs, active-rule replacement and reciprocal legacy notices reviewed and accepted. |
| RD-01 | 기반·시안 작성, 큰 구조 합의 | 현재 대표 시안은 material-workspace. 이전 여섯 비교안은 이력이며 세부 화면의 최종 승인은 아직 남음. |
| RD-02 | 로컬 구현·대표 업무 검증 | 실제 소재·실험·처리 결과·모델·카드 조회와 저장 파일 다운로드. 화면 후속 피드백 반영 중이며 최종 사용자 승인은 남음. |
| RD-03 | 일부 검증 완료 | 단위·브라우저·다운로드·다섯 viewport 검사 수행. 전체 공학 기준 데이터·접근성·실제 장비·확장 규모의 acceptance는 미완료. |
| RD-04 | write journeys | Title metadata PATCH, saved result, explicit model/export/card writes and read-back. |
| RD-05 | expansion | Modeling, Activity and Administration parity with the selected strategy and bounded ownership. |
| RD-06 | cutover | Feature, scientific and UX parity; additive migration, rollback rehearsal and new-write reconciliation. |
| RD-07 | retirement | Imports/routes/parity/save/reload/download/security/recovery evidence; old code, CSS and dependencies removed only after zero-consumer proof. |

2026-09-07 계획 보완: RD 번호를 새로 만들지 않는다. RD-01에서 소재 중심 탐색의 대표 화면과
규칙 정리 변경안을 검토한다. RD-02는 소재 경유 및 직접 실험/Card 조회를 함께 연결하고 RD-03에서
검증한다. RD-04의 저장 기능과 RD-05의 확장 초반에 등록·처리·반복 통계·처리 데이터 다운로드를
하나의 대표 업무로 연결한 뒤, 나머지 시험·모델·솔버·관리 기능으로 확장한다. 적용할 통계 가정과
수치 기준은 검증 후 정하며, 이미 있는 처리·통계 엔진을 먼저 평가한다.

Each row preserves unrelated worktree changes and does not authorize a commit, push, PR, merge or
owner publication. Backlog history remains intact: #391 is merged, #392 is open, #380 follows the DMA
program. PR #397 preserved the backend on main `4c545ea1` and the failed UI branch was retired;
the independent redesign snapshot is preserved in the RD-02 worktree. This program has priority before backlog #195
for this redesign task; it does not mark #195 complete.

## 7. Cutover, rollback and retirement

Cutover is a single product transition after feature parity, scientific parity and UX parity are
all evidenced. It is additive: preserve pre-cutover artifacts, database backup and the old build;
run the migration forward; reconcile writes made during the transition; and keep a rollback path
that does not destructively downgrade new data. The private v1 exact compatibility mapping and
unmodified v1 runtime remain explicitly legacy until migration succeeds. Old concrete revisions
become independent objects, not a reconstructed head chain.

Retirement follows zero-consumer proof for old routes, CSS selectors, compatibility exports and
dependencies. The old app is not removed merely because the new reader renders. Recovery rehearsal,
authorization checks, native download checks, reload/read-back and scientific result checks must be
complete before retirement.

## 8. Acceptance and owner decisions

Acceptance covers seven areas: diagnosis; workflow/assets/parity; task-left navigation and direct
data/card paths; the six comparison candidates and later strategy choice; governance; staged migration and
single cutover; and measurable acceptance with actual remaining decisions.

For the primary pilot, evidence must show exact ordinary identity, explicit stored association,
native bytes, direct paths, title PATCH on the same row and zero nonmaterial domain revisions. For
the second journey, evidence must show exact source context, preserved units and typed input/output,
actual settings in saved results, explicit selection, export mapping states, read-back and recovery.
Negative cases cover unsupported or unacknowledged mappings, missing association, stale current
eligibility, partial upload, parser/API disagreement, authorization denial and failed download.

The program records baseline measurements first and then asks the owner to agree any time, click or
latency targets. It invents no observed threshold. Historical API p95 is not a current frontend
performance result.

For the first full foundation evidence set, capture 1366×768, 1440×900, 1920×1080, 2560×1440 and
3840×2160 at browser zoom 100%, with original-resolution images and 100%-pixel crops for header,
navigator, table/form controls and graph/native preview. Review information hierarchy, engineering
task flow and responsive/wide-screen composition separately. The shell spans the viewport; graphs,
tables and native previews grow only when comparison or interaction improves, while navigators,
forms and prose keep readable bounds. A one-sided 1920 px island, large related-region void, tiny
fixed-density controls, fabricated filler, CSS `zoom`, blanket scaling, route-specific 4K overrides
and non-uniform SVG stretching fail geometry review. Actual Windows 4K physical readability is
deferred to #223; it cannot defer a real geometry, clipping, overflow or interaction failure.

Q-01–Q-20 retain useful owner-feedback goals, but their fixed row sizes, control choices and historical
candidate names are under the section 0 governance review. V-01–V-16 remain legacy matrix criteria
for historical implementation evidence only. Remaining decisions concern the material-centered
representative screen, the concrete governance change set, supported statistical populations/methods,
validated chart technology, compatibility migration, measured performance targets and physical display
readability. No production standard, model, optimizer, solver card or validation threshold is selected
by this program. The six historical proposals do not require another complete comparison cycle.

RD-04/05 공동 설계 검토: IR과 Neutral Material JSON은 frontend·backend가 함께 모델의 기준 데이터와
identity, 중복 값/동기화·독립 저장 필요성, 공통 입력부터 solver exporter까지의 계약을 검토한다.
교환 문서를 사용자 필수 생성 단계로 요구할지도 여기서 판단한다. RD-02의 조회 호환 개선으로 이
검토를 완료 처리하지 않으며, 저장 객체/API 개선은 원본·저장 산출물·계산 의미의 이관·동등성 검증과
함께 진행한다. 현재 확인한 코드와 구체적 검토 경계는 기존 frontend architecture/status 기록을 따른다.

현재 Neutral 승격은 별도 ID·revision과 물성 저장을 만들며 embedded model ref도 새 ID를 사용한다.
IR/교환 envelope는 통합 검토 방향이다. 현재 저장 identity가 이미 하나라는 뜻이 아니며, 공통 기준과
중복 저장·동기화·이관 동등성은 frontend·backend 공동 후속 검토에서 결정한다.
