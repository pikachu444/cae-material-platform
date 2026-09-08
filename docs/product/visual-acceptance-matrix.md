# Desktop Engineering UI Visual Acceptance Matrix

상태: 현재 화면 검토 기준과 기존 구현 증거 색인. 현재 Q의 적용 범위와 아래 legacy 기록을 구분한다.

## Current target boundary — D0-v3

The [frontend redesign program](../planning/frontend-redesign-program.md) and [ADR-0037](../../adr/0037-task-first-frontend-foundation.md)
define the new visual target. Q-01–Q-20 are the target owner-feedback coverage for the same Test
Data/Card reader and later connected workbench expansion. V-01–V-16 are legacy implementation
criteria retained for historical evidence only. Existing captures and registered HTML/CSS/images are
parity observations; they cannot force the old navigation, Carbon/COMSOL/SAP reference composition
or a stale layout onto the new target.

현재 대표 화면과 조정 가능한 세부사항은 [UI 원칙](frontend-ui-principles.md)을 따른다. 소재 중심 카드/표·트리/필터·오른쪽 미리보기·확대 복귀를 검증한다.
2026-09-08 상세 정보 정리: 아래 과거 Evidence/Advanced 기록은 새 reader에 식별자·해시 영역을 두라는 의무가 아니다. 새 상세 화면은 UI 원칙의 공학 정보 표기 기준을 따른다. 사용한 설정·조건·근사를 읽을 수 있는지 확인하며, 저장 문자열을 접어 둔 것만으로 통과시키지 않는다.
이전 여섯 비교안은 평가 이력이다. 실험/카드 직접 진입·저장된 관계·native 다운로드는 소재 선택 없이 제공한다.
카드 공개/릴리스 상태와 일반 데이터 조회 권한의 의미는 구분한다. 합성 데이터 검사는 실제 API·공학 정확성·성능 검증을 대신하지 않는다.

## Reference registration and review gate

새 기반의 목표는 UI 원칙에 연결된 소재 중심 대표 화면이다. 최초 실제 연결 화면을 검증할 때 그 route·데이터·상태와 current evidence를 등록한다. 아직 합성 시안인 자료를 실제 제품 가이드로 승격하지 않는다. 아래 기존 service-reference 등록 경로는 legacy 구현과 이관 시 보존 업무를 확인하는 데 사용하며 새 화면을 옛 layout으로 고정하지 않는다.

For legacy production React/CSS work, use the registered service-reference inventory and its approved
static HTML/CSS or current-product capture for every target screen/state. The register records direct
source/image paths, image hash, viewport, date, status, main-agent evaluation and product-owner
approval. Materials search/detail/card targets use the source-v2 current-product evidence lifecycle
and the screenshot manifest's exact route, image and viewport mapping; their Phase-A entries may be
marked `operational-evidence-accepted` for temporary behavior/read-back evidence, but that status is
not visual-quality approval and keeps the visual-quality disposition pending. Required coverage
is Materials search/tree/detail/card; Modeling Data/Process/Fit/Export; Activity user/reviewer/recovery;
and Administration database/table/attribute/layout/subset/link/access edit/publish. The historical
static inventory remains available only for targets that have not been converted. The first foundation
shell and connected reader supply deterministic evidence at all five target viewports; later small
changes supply risk-bounded evidence for the affected viewport and state, including relevant long,
empty, loading, blocked and error states.

The current Materials and ADM-DB normal references resolve through the screenshot manifest and its
source-v2 current PNGs. The ADM-DB entries supersede the retired issue-289 fixture; on 2026-09-01 the
product owner approved the presented 1920/2560/3840 originals as no-regression evidence for the #331
CSS retirement, not as approval of the existing design quality. Registered references are parity
evidence for the legacy surface, while the current reader baseline in UI principles is the target
for new foundation work. Each later visual PR gives the main
orchestrator and product owner direct reference/current side-by-side live captures, the interaction/test
result and this rubric. Evaluate full-screen task flow, topology, information priority, readability, dominant
tree/table/graph region, control-result continuity, overlap, clipping and overflow. Pixel-perfect
copying and arbitrary fine-number tuning are not acceptance goals; measurements are safety rails.

### Current-guide references

The service-reference register permits `current-guide` beside `static-bundle` and
`current-product-evidence` for screens represented by the current user guide. Each such entry names
one exact screenshot-manifest capture, route, state, viewport, tracked current PNG and SHA-256; the
resolved image and dimensions must agree across both manifests. Current-guide entries do not carry
static-bundle source, measurement or evidence-record fields. Existing Modeling Fit current-guide
captures remain legacy behavior evidence until their RD migration unit. New foundation review uses the
task-first axes and the current material-centered reader baseline; registered Carbon, COMSOL and
SAP references can explain observed geometry, but do not define the new target or product-owner visual
approval.

## Locked product-owner feedback trace

Current, explicit product-owner feedback overrides a stale registered visual reference for the affected
screen or state. Every user-visible change keeps one locked trace from implementation packet through
publication. The trace records:

| Required field | Contract |
| --- | --- |
| Actionable owner feedback | Preserve the exact actionable sentence. Omit insults, status requests and unrelated conversation, but do not shorten away a requested behavior, layout, term or affected screen. |
| Target | Name every route, screen and state covered by the feedback and the approval packet. |
| Implementation disposition | Record the concrete UI/behavior change, or a named issue/decision when the request is outside the current contract. |
| Evidence | Link the live original-resolution capture and applicable interaction/read-back result. |
| Review disposition | Record Main, canonical read-only reviewer and product-owner disposition separately. |

All target screens and states in one approved scope remain one acceptance set. Completing or presenting
only a convenient subset is not completion. After deterministic gates, Main opens every target original
at original resolution and reconciles every trace row before requesting the canonical independent review.
The product owner then gives an explicit final disposition before publication. Selector counts, DOM
queries, measurements and passing tests are supporting evidence; none substitutes for the full-screen
qualitative review or an unresolved owner-feedback row.

## UXC measurement and state evidence additions

첫 shell/연결 reader와 공통 layout의 큰 변경은 아래 다섯 viewport의 원본을 열고 header·navigator·표/폼·그래프/native preview의 필요한 100% pixel crop을 확인한다. 이후 작은 변경은 영향받는 화면·상태로 한정한다. 캡처 개수 자체가 품질 점수는 아니다.

The first foundation shell and connected reader are measured at 1366×768, 1440×900, 1920×1080,
2560×1440, and 3840×2160 from a live deterministic demo with browser zoom fixed at 100%. Later small
changes use risk-bounded evidence for the affected viewport and state; they do not repeat the full
five-viewport set unless the change risk or owner packet requires it.
The screenshot manifest records executable UI source commit, capture command/date, route, fixture and
viewport; a commit identifier without an actual capture is not capture evidence. The capture settles
async work, has no page-level horizontal overflow, and shows no unfinished checking/loading/
calculating/resolving status.

Acceptance also verifies that Materials total/facet/row values share one server-query scope;
non-metal routes expose no Yield facet; recommendation and selected candidate are distinct; blend
identity names both laws and ratio; upstream changes mark downstream state stale without removing
immutable evidence; and Export offers no artifact action without a current exact source. Validated,
Approved, Released, and Delivered labels require the corresponding audit event.

## Legacy scoring rule

Each route is scored from 0 to 2 for every criterion.

- `0`: missing or contradicts the specification
- `1`: partially implemented or inconsistent
- `2`: fully implemented and verified

A legacy route comparison passes only when:

- total score is at least 28/32 (87.5%, satisfying the repository-wide 85/100 minimum);
- no hard-gate criterion scores 0;
- required screenshots and measurements exist.

The numeric result is necessary but never sufficient. Any applicable failure in the following
qualitative checklist blocks handoff regardless of score.

## Q-01–Q-20 target qualitative owner checklist

This is the target owner-feedback coverage for the redesign program. Every visual implementer packet
links it. After deterministic gates, the main orchestrator and, when assigned, the read-only reviewer independently
open each applicable target/state image at original resolution and record `pass`, `fail`, or
`not-applicable` for affected Q items with direct image/path evidence. Unaffected items may be grouped with a reason. The first
foundation shell and connected reader use all five viewport sizes; later small, risk-bounded changes
use the affected scope recorded in the RD packet. `Not-applicable` requires a screen-topology reason.
A generic web-guideline audit supplements this checklist but cannot replace it. No numeric score or
legacy screenshot is a substitute for owner review of the target reader and its task flow.

첫 열에는 간결한 한글 의미를 먼저 쓰고, 괄호 안 Q ID는 기존 증거와 자동 측정을 연결하는
고정 보조 식별자로 유지한다.

| 판정 항목 | Qualitative review requirement |
| --- | --- |
| 긴 탐색 트리의 독립 스크롤 (Q-01) | Long navigator trees expose a visible, independent local scrollbar. |
| 긴 결과 목록의 독립 스크롤 (Q-02) | Long result lists expose a visible, independent local scrollbar; empty results show no fake result scrollbar. |
| Materials 탐색 행의 밀도·정렬 (Q-03) | 탐색 트리의 펼침·표식·이름을 같은 행에 정렬한다. 지원 화면 크기에서 이름·선택·포커스가 읽히고 스크롤과 겹치지 않는다. 행·글자 크기는 공통 token으로 조정한다. 고정 24–26px는 새 기반의 의무가 아니다. |
| Test Data/Card reader의 결과·곡선 공간 보존 (Q-04) | 현재 대표 화면의 소재 카드/표와 실험/카드 직접 조회에서 선택·오른쪽 미리보기·접기·확대·페이지 이동·복귀를 함께 확인한다. 더블클릭/Enter/버튼으로 상세를 열고 검색·페이지·선택·스크롤·초점을 복원한다. 좁은 화면은 명시적 전환/복귀를 제공한다. 기존 여섯 안 재제작은 요구하지 않는다. 조건·단위는 개별 열/항목으로 읽히며 처리 화면에는 별도 업무 구성을 허용한다. |
| 공학 그래프 축의 충돌 없는 배치 (Q-05) | Engineering axes use compact, consistent typography; values, titles and frame do not collide, the x title is not detached, units appear in titles and unused whitespace is materially minimized. |
| 곡선 범례와 결정 상태의 분리 (Q-06) | Multiple curve identities do not form a wide footer or compete with decision status; the curve legend remains compact and semantically separate. |
| 반응형 그래프 glyph·stroke 비율 (Q-07) | Responsive plots preserve real glyph/stroke proportions; measured plot geometry is recomputed without non-uniform SVG stretching. |
| 항복 응답의 양의 시작점·정확한 표기 (Q-08) | 진응력–소성 변형률 출력은 소성 변형률 0에서 양의 초기 항복응력으로 시작하고 전체 응력–변형률로 잘못 표기하지 않는다. 이 시작점 조건을 공칭 응력–전체 변형률이나 다른 물리량에 적용하지 않는다. 모든 차트의 물리량·단위·변환 의미를 확인한다. |
| 오버플로 표시의 발견성·조작성 (Q-09) | Overflow affordances are perceptually discoverable in captured pixels with distinct reserved tracks, proportional thumbs and pointer/wheel/keyboard consequences; tree rows remain concise stored identities. |
| Fit 범례의 곡선 충돌 회피 (Q-10) | 범례·축·곡선이 겹치지 않고 각 곡선을 식별할 수 있어야 한다. 특정 사분면을 강제하지 않는다. 실제 곡선 수와 지원 viewport에서 배치·대체 위치를 확인한다. |
| Modeling 탐색 레일의 Materials 일관성 (Q-11) | Data and multi-input or multi-step Process rails share the Materials navigator's flat pane rhythm, sentence-case sections, regular identity weight, aligned hierarchy and restrained selection. Fit and the single-step DMA TTS Process do not keep an empty or non-interactive rail merely for visual symmetry; their input identity stays in the shallow context band and the recovered width belongs to graph comparison. |
| 정확한 Export selected model 분기·unit system 선택 (Q-12) | 출력 설정에 선택 모델과 실제 출력 단위를 명확하게 표시한다. 지원 단위가 하나면 고정값, 여러 개면 선택으로 제공할 수 있다. 미지원 대안을 선택 가능하게 만들지 않는다. 출력에 영향을 주는 물성과 근사/미지원 상태를 확인할 수 있게 하고 내부 ID·중복 상태 설명으로 작업면을 채우지 않는다. |
| Export 행 문법·보조 문구 (Q-13) | Export setup and result columns use a consistent compact row grammar. Secondary copy is one short consequence or recovery instruction, not a paragraph squeezed beneath every field or mapping row; technical counts and classifications stay in Advanced. |
| Export 준비 상태의 단일 표현 (Q-14) | Export readiness is expressed once as `Ready to create`, `Review required`, or `Cannot create`, followed by the exact blocker/review/action. The same state is not restated with competing colors or repeated in setup, preview and Mapping details. |
| 공학 그래프의 데이터 여백·축 정확성 (Q-15) | Compact engineering plots derive domain headroom from the displayed data span, preserve a physically meaningful zero anchor where applicable, and keep curves clear of the frame. Family-specific axes, units, glyph proportions and legend placement remain correct at every viewport. |
| Export native solver-card preview 우선순위·독립 스크롤 (Q-16) | Export keeps the native solver-card preview dominant. Mapping details and Fit source share a bounded read-only context column; normal content does not show fake scroll rails, while genuine long mapping/native content exposes independent local scrolling without shrinking or obscuring the graph. |
| Administration Object 목록의 식별성·용어 (Q-17) | Administration Object lists use identity-first, family-specific columns. The Name cell contains only the complete/reachable identity; clipped descriptions, quantity/help sentences and duplicated property prose are forbidden. Tables use `Name`; Attributes use `Name | Value type`, with full semantics in the adjacent editor. Identity remains stable through display-name edits. `Rev` columns in older Administration captures are historical parity evidence only. Normal Administration copy uses governed object/task language and excludes infrastructure prose such as identity-provider, feature-grant, server-query, endpoint, row-policy, pin/latest-alias or capability-boundary wording. Ordinary sample identities, related Record targets and solver-card names remain visibly readable; ellipsis is reserved for genuinely long values with an immediate full-value affordance. |
| Administration `Add`·저장 뷰 동작 (Q-18) | Administration Add commands open a real new-definition draft in the right pane without replacing the navigator, current Table scope or list. Add Table and Add Attribute are exercised; Attribute type changes expose only applicable fields. A later saved projection proves that explicitly selected Attribute IDs and the concrete definition content used by the saved result drive stored Record values; Attribute definitions have no independent domain history. Existing exact-revision fixtures are legacy evidence only: `Record preview` and `Layout definition` are task-selectable views rather than simultaneous miniature tables, the active long table receives useful height and genuine local scrolling, compact preview opening has a visible return path, and an unrelated scalar Attribute edit does not show a saved curve merely to fill space. |
| Link cardinality·명시적 연결 (Q-19) | Related and workflow evidence preserve configured `one`/`many` endpoint cardinality and typed links. Graph traversal can reach both directions, but traversal is not derivation; a Test Data/Card reader opens the explicit stored association and never guesses a sibling card, name, first item or `latest` chain. Ordinary renames preserve the link and do not create a nonmaterial revision. |
| 전체 화면 폭·고해상도 전 제품 구성 (Q-20) | The first foundation shell and connected reader span 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160 at browser zoom 100%; results, curves and native previews gain useful comparison space while navigators, forms and prose keep readable bounds. Known geometry, clipping, overflow or interaction failures cannot be deferred. Later small changes use affected viewport/state evidence. Shared token tiers and actual Windows 4K physical readability are measured and decided through their recorded owner gates; #223 remains the physical-device gate. No route-specific 4K override, CSS `zoom`, blanket transform, fabricated filler or non-uniform geometry is allowed. |

검토 판정에는 영향받은 Q 항목과 실제 증거를 포함한다. 전체 표의 기계적인 재작성이나 수치 점수로 사용자 판단을 대신하지 않는다.
자동 측정은 시각 품질을 대신하지 않는다. 해결하지 않은 적용 대상의 결함은 수정 필요로 기록한다.

### 과거 high-DPI 예외와 전달 이력

아래는 이미 진행한 #160/161·#221·#184의 기록이다. 현재 작업에 과거 예외를 새로 적용하거나 고정 density 값을 복제하는 근거가 아니다. 실제 장비 가독성과 알려진 geometry 결함은 계속 구분한다.

The historical transition exception was an already-existing 전체 화면 폭·고해상도 전 제품 구성 (Q-20) failure observed during
#160 or #161. The reviewer still records `fail`; the main-agent and owner may accept it only as an
explicit #221 decision input and subsequent #184 carryover with original-resolution evidence, every
affected route/state, proof that no new page-specific workaround was added, and an explicit
product-owner disposition. #221 approves the provisional shared policy but is not a pass for the
전체 화면 폭·고해상도 전 제품 구성 (Q-20); #184 applies it to all routes and high-risk states.
The exception blocks #204–#216 until #184
merges. After #184, unavailable actual-device physical readability normally is the only item explicitly
deferred to #223. A one-time 2026-08-11 product-owner disposition also transferred #184's exact 30
fixture-blocked originals, structured-manifest completion, and independent original-resolution re-audit
to #223 while retaining `CHANGES_REQUESTED`; those originals are not PASS. This does not permit a known
geometry, clipping, overflow, or interaction failure to be deferred.

The [#221 decision packet](../17-evidence/issue-221-high-dpi-decision.md) records the baseline-first
five-viewport comparison, browser-zoom audit and Codex recommendation of P2 with a Standard default.
The product owner approved that provisional implementation contract on 2026-08-10 and PR #228 merged it
into `main`. #184 therefore exposes one product-wide `Compact | Standard | Large` setting with `Standard`
as default/reset and browser-local active-user/workspace persistence. Candidate 3 remains rejected because
measured browser zoom alone changes CSS viewport and `devicePixelRatio`, so those signals cannot reliably
identify physical display scale. The [#184 evidence](../17-evidence/issue-184-high-dpi-global-implementation.md)
records the production transplant completed in PR #231/main
`ab27e3947817cefa997e49c5dc1d237ec5035adb` and the exact fixture evidence boundary inherited by #223;
neither #221 approval nor automated #184 geometry is actual Windows 4K physical-readability approval.

## Criteria

아래 V-01~V-16은 기존 구현의 평가 이력이다. 새 기반에는 현재 UI 원칙과 적용되는 Q 기준을 사용한다.

| ID | Criterion | Hard gate | Verification |
| --- | --- | --- | --- |
| V-01 | Main task/data appears in first viewport | yes | screenshot |
| V-02 | Desktop menu and command bars replace marketing header | yes | DOM + screenshot |
| V-03 | Application shell uses the full viewport; bounded semantic subregions have justified limits and balanced gutters | yes | measurement + screenshot |
| V-04 | Persistent panes use flat divider grammar | yes | screenshot/CSS |
| V-05 | Required panes are resizable or have approved collapse behavior | no | interaction test |
| V-06 | Typography follows shared display-tier tokens; compact baseline and provisional high-DPI tier preserve the task | yes | computed style + five-viewport review; actual-display final at #223 |
| V-07 | Pane titles and hierarchy are restrained | no | computed style/screenshot |
| V-08 | Row and control density matches blueprint | yes | measurement |
| V-09 | At most one filled primary command per task context | yes | DOM review |
| V-10 | No nested persistent cards | yes | DOM/CSS review |
| V-11 | Introductory/explanatory copy is minimized | no | copy inventory |
| V-12 | Selection updates context in place | yes | interaction test |
| V-13 | Keyboard navigation covers primary workspace | yes | Playwright/manual |
| V-14 | Status bar reports selection and task state | no | screenshot |
| V-15 | No page-level horizontal overflow | yes | viewport test |
| V-16 | Legacy active-route classes are removed or justified | yes | selector report |

## Route-specific gates

이 절의 topology·480px·24–26px·28px 등은 **기존 앱의 route별 회귀 기준**이다. 해당 legacy 변경에 적용하며 새 기반의 메뉴·행 높이·필터·component를 고정하지 않는다. 새 연결 화면에서는 해당 데이터/권한/출력 의미를 보존하고 현재 UI 원칙에 맞춰 검증한다.

### Materials Search

Required topology:

```text
Menu/Command
Navigator | Data Grid | optional Inspector
Status
```

Additional checks:

- Browse/Search/Subsets share the same navigator area;
- grid columns are resizable;
- result count is not presented as a decorative badge;
- selected material inspector does not exceed 480 px;
- no large page title or description block above the workspace.

### Browse Tree

Additional checks:

- compact-tier 24–26 px rows; approved high-DPI tiers use the shared row token;
- local search fixed above tree;
- default Browse keeps the established Database/Profile ancestors, shows the four peer data
  categories with their data-item children, while Administration retains Table/Folder/Record;
- expanding categories preserves the selected exact data revision and other expanded
  category branches;
- tree scroll is independent;
- overflowing tree/result panes show a distinct reserved track and proportional thumb in the
  captured pixels; DOM overflow or an auto-hidden native scrollbar alone does not pass;
- the vertical and conditional horizontal tree scrollbars operate by pointer, wheel and keyboard,
  never cover node text and preserve access to the complete stored identity;
- node labels are concise identities with aligned disclosure/type glyphs; descriptive qualification
  prose is not repeated in every row;
- selected Record opens datasheet in adjacent context;
- forward/reverse links remain accessible.

### Material Detail

Required topology:

```text
Optional navigator/list | Datasheet tabs and content
```

Additional checks:

- property sheet uses compact rows;
- `Related` is directly accessible;
- card Preview/Download is visible without scrolling;
- technical identifiers remain under Evidence/Advanced;
- no 32 px blanket content padding.

### Modeling Data / Process / Fit

Required topology:

```text
Data / multi-step Process: 184–210 px curve/process tree | Persistent dominant plot + shallow task band
Single-step DMA TTS Process / Fit: full-width dominant plot
     locally scrollable candidate comparison | bounded engineer selection
```

Additional checks:

- plot remains mounted through task changes;
- actual plot width is at least 72% of workspace at 1440 px;
- Modeling uses the same dark application menu bar, navigation color tokens and flat pane/divider grammar
  as Materials, Activity and the current Administration implementation. For Polymer Fit this
  owner-directed product-shell rule supersedes the older registered MOD-FIT white application-bar
  override; Administration's object-editor interactions and three-pane topology are not copied into
  Modeling;
- Data/Process curve rows separate inclusion checkbox from icon-only plot visibility;
- the compact-tier Data and multi-step Process tree is 184–210 px; single-step DMA TTS Process and Fit
  reclaim that width for graph comparison and no stage creates a permanent third column;
- the Modeling rail and Materials navigator read as one desktop product: flat headings, sentence-case
  section labels, regular 12–13 px identities, aligned hierarchy indentation and the same restrained
  leading-accent selection grammar; stage-specific curve controls remain distinct rather than being
  copied into catalog rows;
- at the minimum Data/Process rail width, every visible specimen identity/revision is unclipped, the narrow
  plot-color sample does not resemble a badge or branch, and long rail content scrolls locally
  without changing graph width;
- task controls are property rows, not cards;
- Polymer routing follows the data: relaxation and single-temperature DMA go directly to Fit, while
  fixed-frequency DMA temperature sweeps expose one full-width TTS Process step without a non-interactive
  navigator, one Create WLF master curve action
  and one saved-output Continue to Fit action; no duplicate confirmation checkbox or hidden Process
  output choice is allowed;
- Metal Fit uses the exact `Hardening response` heading and only the one-line `Ghosh exceeds chart scale` helper when that display condition applies; polymer linear-viscoelastic Fit uses the measured response name (`Relaxation response` or `DMA frequency response`) and exposes response/residual/applicability state in its governed Fit surface;
- Metal and Polymer Fit repeat only the human source labels needed to distinguish the active work.
  Exact revision pins, digest, method and run evidence remain in Calculation settings, Advanced or
  Evidence and are not repeated as normal-surface helper text;
- the Metal curve legend overlays a measured data-free plot quadrant and does not consume a permanent
  right column; Polymer response keeps its measured/calculated/validation/not-used legend in a shallow
  graph footer so no legend or status text can cover the response curve. This owner-directed Polymer
  exception supersedes an overlay reference that would reproduce the reported overlap; neither form
  creates a permanent right column;
- Polymer Prony inputs use one locally scrollable parameter table with compact aligned Initial value,
  Minimum, Maximum and Unit columns; 10-term editing keeps the current model and column headings visible;
- Polymer comparison separates percentage Fit difference, percentage Check difference, application range,
  warnings and Recommendation. Normal input and results contain no persistent helper
  paragraph or raw negative BIC; row labels do not repeat point or parameter counts, and Recommendation
  remains distinct from engineer Selection. When they differ, the response graph and exact-value table
  compare both calculated responses instead of showing one candidate while residuals show another;
- cursor/selection state appears in status bar.

### Modeling Export

Required topology:

```text
Destination + Export check | Native card preview | bounded read-only Mapping details / Fit source
```

Additional checks:

- native text preview is the dominant area;
- Destination and Export check fit in a 300–340 px setup pane;
- the Mapping/Fit-source region is read-only result context, not a permanent control inspector;
- physical source values such as Density are read-only and show source/output units when relevant;
- only exporter-declared target tuples are selectable; a one-value version/unit field is not
  presented as a meaningful choice;
- `Ready to create`, `Review required` and `Cannot create` agree with blockers and acknowledgement;
- Material State context is not counted as an exact solver-field mapping;
- native ASCII uses a light code surface and internally consistent target units/values;
- metal, linear-viscoelastic and hyperelastic mapping/plot content use their own quantities without
  changing the approved region topology;
- approximation/unsupported warning is visible;
- Create/Open Solver Card is the sole filled primary command for the current state;
- detailed technical mapping status, JSON, identifiers and receipt mechanics are disclosed.

### Administration

Required topology:

```text
Object navigator | Object list | Property editor / preview
```

Additional checks:

- no task-card landing page in the normal database-design route;
- Table, Attribute, Layout, Subset and Link Type are editable in context;
- Add/Edit/Duplicate/Delete live in command bar;
- Attribute and Link Type editors use property sheets;
- live datasheet preview can be opened adjacent to configuration.

### Activity

Additional checks:

- default view is a work queue/data grid;
- no KPI tile dashboard;
- reviews/jobs/releases use tabs or saved views;
- task action is row-specific.

## Reference and approval disposition

The approved target inventory is `service-reference-inventory.yaml`; exact HTML/CSS/image/hash and
approval records are in `service-reference-manifest.yaml`. Current Materials evidence resolves
through `docs/user-guide/screenshot-manifest.yaml` using the exact search, datasheet and solver-card
routes; it does not import an approved-reference list from a capture or form a circular reference.
External Materials reference assets include:
`docs/00-research/images/gui-reference/granta-profile.png`,
`docs/00-research/images/gui-reference/granta-list-results.png`, and
`docs/00-research/images/gui-reference/granta-datasheet-embedded.png`. Administration references:
`docs/00-research/images/gui-reference/granta-admin-schema-tool.png`,
`docs/00-research/images/gui-reference/granta-functional-edit.png`,
`docs/00-research/images/gui-reference/granta-admin-layout.png`, and
`docs/00-research/images/gui-reference/granta-record-links-datasheet.png`. Modeling references:
`modeler-start-data.png`, `modeler-youngs-auto.png`, `modeler-youngs-manual.png`,
`modeler-necking-point.png`, `modeler-fit-extrapolation.png`, `modeler-create-cae-card.png`, and
`modeler-cae-card-details.png` in `docs/00-research/images/gui-reference/README.md`. These external
images explain product grammar but do not override the registered target. Target approval never marks
a production route complete; live implementation still requires browser evidence and approval.

## Required measurement report

검토 범위에 필요한 측정 항목과 viewport만 기록한다. 아래 다섯 열 양식은 첫 shell/연결 reader 또는 넓은 layout 변경에 사용할 수 있는 예시다.

| Metric | 1366 | 1440 | 1920 | 2560 | 3840 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Menu + command height | | | | | |
| Workspace used width | | | | | |
| Left/right outer gutter | | | | | |
| Navigator width | | | | | |
| Main data/plot width | | | | | |
| Inspector width | | | | | |
| Normal pane padding | | | | | |
| Data row height | | | | | |
| Body font size | | | | | |
| Active display tier | | | | | |
| Primary command count | | | | | |
| Nested persistent card count | | | | | |
| Page horizontal overflow | | | | | |

For #221 and #184, record the available monitor resolution and size, Windows display scale, CSS
viewport, `devicePixelRatio`, browser zoom and active density. If actual 4K is unavailable, record
`DEFERRED_TO_223`; automated emulation cannot replace or imply the missing physical record. #221 compares
candidates and #184 revalidates the provisional candidate across every route/state. #223 requires the
actual Windows 4K record and product-owner readability disposition for the final product-wide gate.

## Legacy selector report

아래는 기존 앱의 selector 정리 대상 목록이다. 해당 legacy 소비자를 이관/삭제하는 작업에서 사용처와 제거 조건을 확인한다. 새 앱의 모든 시각 변경에 이 목록 검색을 강제하지 않는다.

```text
page-stack
page-heading
content-card
module-material-card
hero-actions
eyebrow
status-badge
count-chip
```

Each occurrence must be removed, migrated or explicitly justified as an Advanced/legacy-only exception.

RD-02는 사용자가 승인한 `design/frontend-reader-proposals/material-workspace` 소스의 색·타이포·구조·비율·한국어·행동을 직접 비교해 일치시킨다. 실제 데이터와 지원 기능으로 인해 필요한 차이만 명시하며, 일반적인 pixel-perfect 비목표 문구로 이 시안 일치 요구를 완화하지 않는다.
