# Desktop Engineering UI Visual Acceptance Matrix

Status: authoritative visual review gate

## Reference registration and review gate

Before production React/CSS work, use #167's approved static HTML/CSS and rendered image for
every target screen/state. The register records direct source/image paths, image hash, viewport, date,
status, main-agent evaluation and product-owner approval. Required coverage is Materials
search/tree/detail/card; Modeling Data/Process/Fit/Export; Activity user/reviewer/recovery; and
Administration database/table/attribute/layout/subset/link/access edit/publish. The approved #167
reference inventory remains 1366×768, 1440×900, and 1920×1080; every user-visible React/CSS change
also supplies deterministic 2560×1440 and 3840×2160 responsive evidence plus relevant long, empty,
loading, blocked, and error states.

References are implementation authority, not vague inspiration: port their region structure and CSS
faithfully while preserving backend/state/domain contracts. Each later visual PR gives the main
orchestrator and product owner direct reference/current side-by-side live captures, the interaction/test
result and this rubric. Evaluate full-screen task flow, topology, information priority, readability, dominant
tree/table/graph region, control-result continuity, overlap, clipping and overflow. Pixel-perfect
copying and arbitrary fine-number tuning are not acceptance goals; measurements are safety rails.

## UXC measurement and state evidence additions

Every target route is measured at 1366×768, 1440×900, 1920×1080, 2560×1440, and 3840×2160 from a
live deterministic demo with browser zoom fixed at 100%.
The screenshot manifest records executable UI source commit, capture command/date, route, fixture and
viewport; a commit identifier without an actual capture is not capture evidence. The capture settles
async work, has no page-level horizontal overflow, and shows no unfinished checking/loading/
calculating/resolving status.

Acceptance also verifies that Materials total/facet/row values share one server-query scope;
non-metal routes expose no Yield facet; recommendation and selected candidate are distinct; blend
identity names both laws and ratio; upstream changes mark downstream state stale without removing
immutable evidence; and Export offers no artifact action without a current exact source. Validated,
Approved, Released, and Delivered labels require the corresponding audit event.

## Scoring rule

Each route is scored from 0 to 2 for every criterion.

- `0`: missing or contradicts the specification
- `1`: partially implemented or inconsistent
- `2`: fully implemented and verified

A route passes only when:

- total score is at least 28/32 (87.5%, satisfying the repository-wide 85/100 minimum);
- no hard-gate criterion scores 0;
- required screenshots and measurements exist.

The numeric result is necessary but never sufficient. Any applicable failure in the following
qualitative checklist blocks handoff regardless of score.

## Mandatory qualitative owner checklist

This is the canonical record of the cumulative product-owner findings. Every visual
implementer packet links it. After deterministic gates, both the main orchestrator and fresh read-only
reviewer independently open every target/state image at original resolution and record `pass`,
`fail`, or `not-applicable` plus direct image/path evidence for 20개 정성 판정 항목 (Q-01~Q-20). `Not-applicable` requires
a screen-topology reason. A generic web-guideline audit supplements this checklist but cannot replace
it. The main orchestrator evaluates reviewer findings without repeating an unchanged completed checklist,
and the product owner makes the final visual approval.

첫 열에는 간결한 한글 의미를 먼저 쓰고, 괄호 안 Q ID는 기존 증거와 자동 측정을 연결하는
고정 보조 식별자로 유지한다.

| 판정 항목 | Qualitative review requirement |
| --- | --- |
| 긴 탐색 트리의 독립 스크롤 (Q-01) | Long navigator trees expose a visible, independent local scrollbar. |
| 긴 결과 목록의 독립 스크롤 (Q-02) | Long result lists expose a visible, independent local scrollbar; empty results show no fake result scrollbar. |
| Materials 탐색 행의 밀도·정렬 (Q-03) | At the compact tier, Materials navigation uses 24–26 px rows, economical indentation/type glyphs, reachable complete identities and no scrollbar/text collision. An approved high-DPI tier changes row and glyph size only through shared tokens. Disclosure, type glyph and label share one grid row and vertical center; implicit auto-placement onto a second line fails. |
| Fit 리본과 그래프 공간 보존 (Q-04) | Fit controls and status do not squeeze the graph: at the compact tier the six groups remain visible within the 104 px (31 px heading + 72 px controls) ribbon and shared top actions stay 28 px. An approved high-DPI tier may increase ribbon and action tokens while preserving all six groups, baseline alignment, graph dominance, reachable Remove step/Candidate parameters, and local evidence-drawer scrolling. |
| 공학 그래프 축의 충돌 없는 배치 (Q-05) | Engineering axes use compact, consistent typography; values, titles and frame do not collide, the x title is not detached, units appear in titles and unused whitespace is materially minimized. |
| 곡선 범례와 결정 상태의 분리 (Q-06) | Multiple curve identities do not form a wide footer or compete with decision status; the curve legend remains compact and semantically separate. |
| 반응형 그래프 glyph·stroke 비율 (Q-07) | Responsive plots preserve real glyph/stroke proportions; measured plot geometry is recomputed without non-uniform SVG stretching. |
| 항복 응답의 양의 시작점·정확한 표기 (Q-08) | True-yield-stress versus true-plastic-strain response starts at a positive initial yield stress at zero plastic strain and is not mislabeled as total stress–strain. |
| 오버플로 표시의 발견성·조작성 (Q-09) | Overflow affordances are perceptually discoverable in captured pixels with distinct reserved tracks, proportional thumbs and pointer/wheel/keyboard consequences; tree rows remain concise stored identities. |
| Fit 범례의 곡선 충돌 회피 (Q-10) | Fit legend occupies a demonstrably curve-free plot quadrant and recovers graph width, with geometry-aware alternate placement or compact docked fallback on collision. |
| Fit 탐색 레일의 Materials 일관성 (Q-11) | Fit rail shares the Materials navigator's flat pane rhythm, sentence-case sections, regular identity weight, aligned hierarchy, secondary revision text and restrained selection, while preserving curve-specific controls and its own topology. |
| 정확한 Export selected model 분기·unit system 선택 (Q-12) | Export setup identifies the exact branch by its selected model, while the shared experiment/method/condition remains page context. Output unit system remains a capability-backed selector even with one supported value; unsupported alternatives never become a selectable invalid state. Physical properties appear once in Mapping details when they affect output; ambiguous `r1` shorthand, duplicate Source/Output labels, `Saved`, `Pinned`, internal lineage and receipt vocabulary stay out of the normal surface. |
| Export 행 문법·보조 문구 (Q-13) | Export setup and result columns use a consistent compact row grammar. Secondary copy is one short consequence or recovery instruction, not a paragraph squeezed beneath every field or mapping row; technical counts and classifications stay in Advanced. |
| Export 준비 상태의 단일 표현 (Q-14) | Export readiness is expressed once as `Ready to create`, `Review required`, or `Cannot create`, followed by the exact blocker/review/action. The same state is not restated with competing colors or repeated in setup, preview and Mapping details. |
| 공학 그래프의 데이터 여백·축 정확성 (Q-15) | Compact engineering plots derive domain headroom from the displayed data span, preserve a physically meaningful zero anchor where applicable, and keep curves clear of the frame. Family-specific axes, units, glyph proportions and legend placement remain correct at every viewport. |
| Export native solver-card preview 우선순위·독립 스크롤 (Q-16) | Export keeps the native solver-card preview dominant. Mapping details and Fit source share a bounded read-only context column; normal content does not show fake scroll rails, while genuine long mapping/native content exposes independent local scrolling without shrinking or obscuring the graph. |
| Administration Object 목록의 식별성·용어 (Q-17) | Administration Object lists use identity-first, family-specific columns. The Name cell contains only the complete/reachable identity; clipped descriptions, quantity/help sentences and duplicated property prose are forbidden. Tables use `Name | Rev`; Attributes use `Name | Value type | Rev`, with full semantics in the adjacent editor. Normal Administration copy uses governed object/task language and excludes infrastructure prose such as identity-provider, feature-grant, server-query, endpoint, row-policy, pin/latest-alias or capability-boundary wording. Ordinary sample identities, related Record targets and solver-card names remain visibly readable; ellipsis is reserved for genuinely long values with an immediate full-value affordance. |
| Administration `Add`·저장 뷰 동작 (Q-18) | Administration Add commands open a real new-definition draft in the right pane without replacing the navigator, current Table scope or list. Add Table and Add Attribute are exercised; Attribute type changes expose only applicable fields. A later saved projection proves that user-selected exact Attribute revisions drive stored Record values: `Record preview` and `Layout definition` are task-selectable views rather than simultaneous miniature tables, the active long table receives useful height and genuine local scrolling, compact preview opening has a visible return path, and an unrelated scalar Attribute edit does not show a saved curve merely to fill space. |
| Administration `Link Type` cardinality·정확한 개정본 (Q-19) | Administration Link Type and Related/workflow evidence preserve configured `one`/`many` endpoint cardinality and exact revision pins. The UI must support visible one-to-many/many-to-many branching where allowed and must not flatten Material/Test Data/Processing Output/model/Neutral/Solver Card lineage into an implied one-to-one or `latest` chain. |
| 전체 화면 폭·고해상도 전 제품 구성 (Q-20) | At 1920×1080, 2560×1440, and 3840×2160, the application shell spans the viewport and related task regions remain adjacent. Graphs, tables, and native previews expand while extra space materially improves reading, comparison, or interaction; navigators, property forms, and prose retain readable bounds and balanced gutters. A one-sided 1920 px work island, large trailing void caused by an arbitrary shell cap, large internal void between related regions, or tiny fixed-density controls at 2560/3840 fails. Uniformly stretched rows/prose/plots, fabricated filler, route-specific 4K overrides, CSS `zoom`, blanket `transform: scale`, and non-uniform SVG geometry also fail. The compact 13 px data and 11.5–12 px metadata baseline remains valid for standard desktop tiers; shared high-DPI tiers may increase typography, control, row, spacing, pane, and plot tokens after #221's deterministic five-viewport comparison and provisional product-owner decision. #184 applies that provisional shared decision across every route/state. Actual Windows 4K 100%/150%/200% physical readability remains unapproved until #223. A deliberately under-filled normal search fixture still fails when the scoped API already supplies a fuller server page. Sparse plots and secondary Administration graphs remain bounded by task usefulness rather than raw viewport size, while contract-backed companion data may occupy truthful wide-screen space. Activity keeps the full role-correct request list and distinct local history. |

An `approve` disposition must include the completed 20개 정성 판정 결과 (Q-01~Q-20). Automated measurements support
the evidence but do not prove visual quality. Any unresolved applicable `fail` requires
`changes_requested`.

The only transition exception is an already-existing 전체 화면 폭·고해상도 전 제품 구성 (Q-20) failure observed during
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
184–210 px curve/process tree | Persistent dominant plot with shallow graph-adjacent band
```

Additional checks:

- plot remains mounted through task changes;
- actual plot width is at least 72% of workspace at 1440 px;
- curve rows separate inclusion checkbox from icon-only plot visibility;
- compact-tier curve tree is 184–210 px and controls do not create a permanent third column;
- the Modeling rail and Materials navigator read as one desktop product: flat headings, sentence-case
  section labels, regular 12–13 px identities, aligned hierarchy indentation and the same restrained
  leading-accent selection grammar; stage-specific curve controls remain distinct rather than being
  copied into catalog rows;
- at the minimum rail width, every visible specimen identity/revision is unclipped, the narrow
  plot-color sample does not resemble a badge or branch, and long rail content scrolls locally
  without changing graph width;
- task controls are property rows, not cards;
- Fit uses the exact `Hardening response` heading and only the one-line `Ghosh exceeds chart scale` helper when that display condition applies; response/residual/extrapolation state is visible in the plot;
- Fit's normal title row exposes only the human source label/revision and concise surface state; full digest/method/run evidence is reachable through Candidate parameters;
- the curve legend overlays a measured data-free plot quadrant and does not consume a permanent
  right column; deterministic geometry evidence proves it misses curves, boundaries, axes, labels
  and state overlays at every required viewport, with a docked fallback only when no safe quadrant
  exists;
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

#167's approved target inventory is `service-reference-inventory.yaml`; exact HTML/CSS/image/hash and
approval records are in `service-reference-manifest.yaml`. External Materials references include:
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
images explain product grammar but do not override the approved #167 target. Target approval never
marks a production route complete; live implementation still requires browser evidence and approval.

## Required measurement report

Every visual PR records:

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

Every visual PR lists active-route usage of:

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
