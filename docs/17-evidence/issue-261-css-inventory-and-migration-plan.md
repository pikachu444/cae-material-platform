# Issue #261 FE-06 CSS inventory와 migration plan

상태: 첫 bounded unit 완료 후보 — inventory와 plan만 포함하며 production migration은 시작하지 않음

기준: `main@be4166d840280d5ff0e0a419815002f60b31eeab`

branch: `issue-261-fe06-css-inventory`

상위 program: #249, FE-06

## 범위와 판정

이 단위는 #261의 권장 순서 중 첫 항목인 **inventory와 migration plan**만 수행한다. production
React, CSS, DOM, API, URL, state, 사용자 문구, user guide, screenshot manifest와 화면 픽셀은 바꾸지
않는다. 새 repository rule 문서를 만들지 않고, 이 issue evidence와 결정적 inventory만 추가한다.

현재 구현 판정은 다음과 같다.

| 항목 | 시작 판정 | 이 단위 결과 |
| --- | --- | --- |
| #256 신규 global selector guard | 부분 완료 | 기존 rule과 allowance를 바꾸지 않고 최신 merge-base provenance만 동기화했다. Guard는 `0 violations`, 기존 warning 15개로 통과한다. |
| shared token/typography/primitive/shell 분리 | 부분 완료 | 기존 네 owner file과 import 순서를 inventory에 고정했다. Legacy 파일과 같은 selector가 남아 있다. |
| feature-owned CSS | 부분 완료 | Modeling normalization과 Data CSS 두 파일만 존재한다. Legacy global과 같은 selector 25행이 이 두 파일에도 존재한다. |
| selector owner/consumer/cascade inventory | 누락 | 2,834 rule-group, comma를 펼친 3,585 selector 행을 모두 기록했다. |
| production CSS migration | 누락 | 의도적으로 미수행. 다음 bounded unit부터 시작한다. |

## 권위와 보존할 사용자 흐름

권위는 활성 사용자 지시, #261, parent #249, FE-00~FE-06 roadmap, root와 `apps/web/AGENTS.md`,
frontend UI 원칙, frontend architecture, visual acceptance matrix 순이다. 이 단위는
`material-platform-frontend-architecture` preflight에 따라 구조 이동과 semantic visual 변경을
분리한다.

다음 migration들이 보존해야 할 대표 흐름은 다음과 같다.

| 필드 | 고정 내용 |
| --- | --- |
| Setup | 정확한 Material/State/Test Data와 revision을 가진 Modeling session에서 `/modeling?stage=data` 또는 `/datasets/processing?stage=data`를 연다. |
| Operator actions | Library 또는 Local file에서 현재 Test Data를 확인하고, mapping을 해결하고, graph를 유지한 채 Process로 진행한다. |
| Visible outcome | compact rail, source/mapping decision, persistent dominant graph와 다음 유효 action이 같은 topology와 geometry를 유지한다. |
| Persistence/read-back | exact source/revision, session restore, last-valid graph, downstream invalidation과 Materials read-back 계약이 바뀌지 않는다. |
| Recovery | empty new session과 invalid mapping에서 source와 마지막 유효 graph를 보존하고 기존 repair action에 도달할 수 있다. |
| Preserved contracts | API/DTO/URL/session v4/revision/persistence/keyboard/focus/local scroll/approved visual reference를 모두 보존한다. |
| Forbidden shortcuts | selector rename을 목표로 삼기, CSS module/framework 추가, route별 4K patch, CSS `zoom`, blanket scale, consumer 확인 없는 삭제, 한 selector 복제, golden blind update를 금지한다. |

현재 inventory 단위는 runtime을 건드리지 않으므로 위 흐름의 browser 재실행과 새 screenshot은 N/A다.
다음 production migration 단위는 이 흐름과 별도 negative/recovery state를 실제로 다시 검증한다.

## 결정적 inventory 산출물

전체 selector별 증거는
[`issue-261-css-selector-inventory.json`](issue-261-css-selector-inventory.json)에 있다. 각 행은 다음을
포함한다.

- 안정적인 `CSS-nnnn` id, source file/line/rule/selector index와 main CSS import rank;
- comma로 분리한 selector, 계산한 specificity, `@media`/`@container` context, declaration property와
  declaration SHA-256;
- subject class/id의 production/test class producer와 selector API reference를 각각 찾은 결과;
- 제안 owner, consumer route/state, migration batch와 target file;
- exact-selector group, 동일 target/property cascade group, owned CSS의 same-selector peer;
- deep descendant, `:has`, `!important`, raw color, literal weight, dead/duplicate/wide-workaround 후보.

[`check_issue_261_css_inventory.mjs`](../../scripts/check_issue_261_css_inventory.mjs)는 두 legacy file과
모든 비교 CSS를 다시 파싱해 JSON을 byte-for-byte 검증한다. `--write`는 source가 의도적으로 바뀐
다음 migration 단위에서만 사용한다.

정적 consumer 검색은 JSX/TS의 static, template, conditional branch를 포함한 `className`/`*ClassName`
producer와 `querySelector`/`closest` 같은 문자열 reference를 production/test별로 분리한다. Production
reference만 있는 59행은 dead 후보에서 제외했다. `no-subject-class-evidence-observed`와 test-only
reference는 **삭제 후보**이지 zero-consumer 승인 결과가 아니다. 계산된 변수, 외부 DOM, portal, lazy
route와 실제 DOM은 후속 unit의 browser/bundle evidence로 다시 확인해야 한다.

## 현재 stylesheet와 load boundary

`main.tsx`의 base import 순서는 `styles.css` → `tokens.css` → `typography.css` → `primitives.css` →
`layout.css` → `shell.css`다. Production build는 base를 `index-*.css` 하나로 만들고,
`modeling-stage-normalization.css`와 `modeling-data-stage.css`를 각각 Modeling lazy CSS asset으로
분리한다. 따라서 같은 specificity의 feature rule은 Modeling route에서 base 뒤에 load되는 현재
cascade에 의존한다. 후속 migration은 이 순서를 우연한 구현 세부로 취급하지 말고 computed-style
provenance로 고정해야 한다.

| 현재 file | lines | rule-groups | selector rows | 현재 importer / 실제 책임 | disposition |
| --- | ---: | ---: | ---: | --- | --- |
| `src/styles.css` | 8,140 | 1,382 | 1,672 | `main.tsx`; legacy cross-feature/base/responsive | feature cohort를 옮긴 뒤 zero-consumer가 된 rule만 제거한다. 최종적으로 feature 책임을 받지 않는다. |
| `src/design/tokens.css` | 192 | 3 | 3 | `main.tsx`; shared tokens/density | token definition만 소유한다. |
| `src/design/typography.css` | 102 | 16 | 25 | `main.tsx`; shared typography roles | ordinary route arrangement를 받지 않는다. |
| `src/design/primitives.css` | 360 | 54 | 77 | `main.tsx`; generic semantic primitives | generic interaction/appearance만 소유한다. |
| `src/design/layout.css` | 9,021 | 1,452 | 1,913 | `main.tsx`; shared layout와 legacy route layout 혼재 | feature rule을 단계적으로 비운 뒤 generic pane/split/layout만 남긴다. |
| `src/design/shell.css` | 466 | 63 | 71 | `main.tsx`; application shell/navigation/status | route-specific feature geometry를 받지 않는다. |
| `src/features/modeling/ui/modeling-stage-normalization.css` | 436 | 66 | 80 | `modeling-stage-shell.tsx`; Modeling-wide stage grammar | Modeling shell/stage-owned target. Global shell을 복제하지 않는다. |
| `src/features/modeling/ui/stages/data/modeling-data-stage.css` | 1,057 | 150 | 169 | `modeling-data-intake.tsx`; Data stage | 첫 production migration의 기존 target. |

## 전체 분류 결과

Guard의 `CMP-FE-GLOBAL-CSS-SELECTOR` 기준은 comma list 하나를 한 rule-group으로 세므로 2,834다.
Inventory는 owner가 달라질 수 있는 comma member를 분리해 3,585행으로 확장한다. 두 수치는 정확히
같은 source를 다른 단위로 센 결과다.

| Source | rule-groups | selector rows |
| --- | ---: | ---: |
| `styles.css` | 1,382 | 1,672 |
| `design/layout.css` | 1,452 | 1,913 |
| 합계 | 2,834 | 3,585 |

| 제안 owner | selector rows | 의미 |
| --- | ---: | --- |
| Modeling-specific | 1,586 | Data/Process/Fit/Export, Modeling shell/family workbench 후보 |
| Materials-specific | 483 | Materials search/tree/detail/card와 record/datasheet 후보 |
| Administration-specific | 393 | database/schema/record/access 후보 |
| Activity-specific | 55 | queue/review/recovery 후보 |
| Shared application shell | 196 | shell/navigation/toolbar/status 책임 후보 |
| Shared form/table/plot primitive | 99 | generic primitive 후보 |
| Shared pane/split/layout | 20 | resizable/generic pane 후보 |
| Shared token/density/typography | 4 | root/token/role 후보 |
| Legacy cross-feature | 211 | 현재 consumer가 둘 이상이라 그대로 이동하면 안 되는 selector |
| Unresolved legacy | 538 | live owner characterization 전 이동 금지 |

Dead 후보를 별도 제거 batch로 빼고 실제 실행 순서를 적용하면 다음과 같다.

| Migration batch | selector rows | source 분포 | target ownership |
| --- | ---: | --- | --- |
| M1A Modeling Data | 233 | layout 224 / styles 9 | 기존 `modeling-data-stage.css` |
| M1B Modeling Process | 151 | layout 137 / styles 14 | Process stage-owned CSS |
| M1C Modeling Fit | 98 | layout 60 / styles 38 | Fit stage-owned CSS |
| M1D Modeling Export | 270 | layout 18 / styles 252 | Export stage-owned CSS |
| M1E Modeling shell/family | 717 | layout 270 / styles 447 | Modeling-wide 또는 owning family component CSS |
| M2 Materials | 405 | layout 386 / styles 19 | planned Materials feature CSS |
| M3A Administration | 382 | layout 181 / styles 201 | planned Administration feature CSS |
| M3B Activity | 48 | layout 8 / styles 40 | planned Activity feature CSS |
| M4 shared cleanup | 301 | layout 234 / styles 67 | existing tokens/typography/primitives/layout/shell |
| M6 zero-production-consumer 후보 | 533 | layout 167 / styles 366 | live zero-consumer 후에만 삭제 |
| HOLD owner/cross-feature split | 447 | layout 228 / styles 219 | owner를 먼저 분리하며 selector 복제 금지 |

## Consumer route/state 증거

JSON의 각 selector 행은 subject class producer/reference consumer file과 아래 route/state family를 연결한다. 승인된
service reference manifest 72개도 함께 확인했다.

| Owner | consumer route | 반드시 다시 여는 state/reference |
| --- | --- | --- |
| Materials | `/materials`, detail tabs, exact record, solver-card preview | search normal/long/empty; datasheet normal/empty/related-long; card normal/approximation-blocked/unsupported-blocked |
| Modeling | `/modeling`, `/datasets/processing` | Data normal/empty-new-session/long-invalid-mapping-blocked; Process normal/prerequisite-blocked; Fit normal/candidate-parameters-long; Export normal/source-blocked/approximation-blocked/delivered |
| Administration | `/administration/*`, `/catalog/schema`, `/catalog/records`, `/catalog/explorer` | database normal; Table/Attribute/Layout/Subset/Link draft; stale/long-invalid; access denied/revoke; publish not-configured |
| Activity | `/activity`, `/jobs-reviews` | user normal; reviewer normal/long-decision-error; recovery not-configured |
| Shared | 모든 인증 route | shell, keyboard/focus, local scroll, status, overflow와 모든 영향 route의 five-viewport gate |

## Specificity와 cascade 후보

### Exact selector와 source-order dependency

- exact selector가 두 번 이상 나타나는 group은 496개, 관련 selector 행은 1,147개다.
- 같은 at-context에서 합칠 수 있는 selector group은 305개, 관련 행은 668개다.
- 두 legacy file에 걸친 same-selector group은 19개, 관련 행은 52개다. 대표 항목은
  `.native-preview`, `.modeling-export-blocked`, `.method-builder-card`, `.method-library`,
  `.persistent-modeling-plot`, `.step-option-panel`, `.modeling-support-drawer`,
  `.modeling-graph-workspace`, `.test-json-page`, `.material-database-page`,
  `.material-database-toolbar`와 `.saved-test-documents`다. 전체 member와 source order는
  `EXACT-nnnn` group에 있다.
- declaration SHA와 at-context까지 같은 byte-duplicate rule은 0개다. 따라서 이 inventory는
  단순 중복 삭제를 승인하지 않는다. 3개 identical-declaration group도 서로 다른 media context라
  live behavior 확인 전에는 삭제하지 않는다.
- target class/property가 같은 잠재 cascade group은 1,999개다. 이는 충돌 가능성 index이며 DOM
  match 증명은 아니다. 각 selector는 specificity와 group id를 함께 가진다.

### 이미 owned CSS와 같은 selector

Legacy selector 25행이 non-legacy CSS에도 있다.

| Cohort | rows | 현재 dependency |
| --- | ---: | --- |
| shared | 4 | `:root`↔tokens, `.ux-page`↔typography, `.ux-result-row`↔primitives, Modeling shell `:has(...)`↔shell |
| Modeling Data | 12 | `layout.css`와 `modeling-data-stage.css`의 같은 selector가 base/lazy order로 합성됨 |
| Modeling Export | 9 | `styles.css`와 `modeling-stage-normalization.css`의 같은 selector가 base/lazy order로 합성됨 |

이 25행은 이동을 시작하기 좋은 후보지만, same-selector라는 사실만으로 legacy declaration 전체가
무효인 것은 아니다. shorthand/longhand와 서로 다른 property가 합쳐지는 경우가 있으므로 현재
effective declaration을 owned file에 보존한 뒤 source rule을 제거한다.

### Dead 후보

533행은 production class producer와 production selector reference가 모두 관찰되지 않았다. 이 중
527행은 subject class evidence가 없고 6행은 test reference에만 있다. Production reference만 있는
59행은 이 수치와 M6에서 제외했다. 가장 큰 묶음은 unresolved legacy 296행과 Modeling 117행이다.
삭제 조건은 모두 동일하다.

1. exact class 생성 경로와 template/dynamic 조합을 repository search로 재검사한다.
2. production bundle에서 selector/class consumer가 없음을 확인한다.
3. 영향 route의 normal/exception DOM에서 `document.querySelectorAll(selector) === 0`을 확인한다.
4. 삭제 전후 five-viewport geometry와 keyboard/focus/overflow/console을 확인한다.
5. 같은 cascade group의 다른 rule이 숨겨진 fallback을 제공하지 않는지 확인한다.

이 다섯 조건 전에는 JSON의 `deadCandidate`를 제거 승인으로 해석하지 않는다.

### `:has`, deep descendant와 `!important`

| 후보 | rows | 처리 조건 |
| --- | ---: | --- |
| deep descendant | 898 | feature DOM contract가 실제 owner인지 확인하고, shared가 feature 내부 구조에 의존하지 않게 이동한다. |
| `:has(...)` | 50 | owner와 필요한 state predicate를 기록한다. 그중 shell↔route coupling 24행은 M4 전에 feature 이동 또는 명시적 shell contract를 정한다. |
| `!important` | 14 | 소비자와 현재 competing declaration을 computed style로 고정하고 필요성/제거 조건을 같은 migration unit에 기록한다. |
| raw color literal | 704 | 기존 semantic token과 의미가 동일한 경우에만 치환한다. CSS 이동과 broad visual normalization을 섞지 않는다. |
| literal font weight | 250 | 기존 typography role과 정확히 일치할 때만 치환한다. |

### Wide route workaround 후보

#256의 `CMP-FE-WIDE-MEDIA` 두 block은 `layout.css`의 Materials 전용 selector다.

| at-rule | selector ids | 현재 증거와 disposition |
| --- | --- | --- |
| `@media (min-width: 1600px)` | `CSS-1451..1453` | `.materials-workspace.filters-visible/context-visible`; state class의 production producer/reference가 없어 dead/workaround 후보. M2 live DOM에서 zero-consumer를 증명하기 전 삭제 금지. |
| `@media (min-width: 1800px)` | `CSS-1467..1472` | Material response/native preview layout. 조건부 template class인 `has-linked-response`를 포함해 6행 모두 production producer가 있다. M2에서 approved 1920/2560/3840 composition과 비교해 feature-owned responsive contract로 이동한다. |

두 block을 shared display-tier 정책으로 가장해 유지하거나 route-specific 4K patch로 다시 만들지 않는다.

## 다음 bounded production unit — M1A0 Data same-selector overlap

다음 unit은 전체 M1A 233행을 한 번에 옮기지 않는다. 이미 owned Data CSS와 selector가 겹치는
12행/11 rule-group만 이동한다. FE-05의 현재 Data screen과 lazy CSS boundary가 검증되어 있어 가장
작고 관찰 가능한 첫 migration이다.

### 파일 소유권

| File | 다음 unit 권한 |
| --- | --- |
| `apps/web/src/design/layout.css` | 아래 12 selector member가 속한 11 legacy rule-group만 제거/축소한다. 다른 route selector를 재배열하지 않는다. |
| `apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css` | 현재 effective Data declaration만 기존 same-selector rule에 병합한다. 같은 selector를 새 파일에 복제하지 않는다. |
| `apps/web/src/design/modeling-workspace-layout.tsx` | 변경하지 않는다. `dataLayoutMode`와 `ResizeObserver`로 제한된 Data split class emission을 focused test의 read-only contract로 사용한다. |
| `apps/web/src/common-processing-workbench.tsx` | 변경하지 않는다. non-Data caller가 `dataLayoutMode`를 넘기지 않아 plot-panel class를 만들지 않는다는 negative contract를 고정한다. |
| `apps/web/frontend-guard-baseline.json` | 최종 실제 line count와 global rule count를 낮춰 해결된 debt가 돌아오지 못하게 한다. `sourceSha`는 그 unit의 merge-base다. |
| inventory script/JSON과 issue evidence | 이동 후 새 source count, cascade와 zero-consumer 결과를 재생성한다. |
| tests와 visual evidence | 기존 Data component/workbench tests, fresh five-viewport before/after와 normal/empty/invalid state만 소유한다. |

React/TSX/DOM/API/type/session/user-guide 변경이 필요해지면 이 CSS-only unit을 멈추고 별도 경계를
결정한다.

### 정확한 selector packet

| ID | legacy source | specificity / context | selector | legacy properties | owned peer |
| --- | --- | --- | --- | --- | --- |
| `CSS-0979` | `layout.css:4812` | `0-1-0`, base | `.data-mapping-resolved` | `min-width` | Data CSS line 863 |
| `CSS-0997` | `layout.css:4879` | `0-1-0`, base | `.data-mapping-resolved` | `align-items,border-left,display,gap,padding-left` | Data CSS line 863 |
| `CSS-0998` | `layout.css:4888` | `0-1-0`, base | `.data-mapping-resolved` | `border-left-color` | Data CSS line 863 |
| `CSS-1041` | `layout.css:5070` | `0-1-0`, base | `.data-source-decision-grid` | `align-items,container-type,display,gap,grid-template-columns,min-width` | Data CSS line 859 |
| `CSS-1052` | `layout.css:5155` | `0-2-0`, base | `.data-mapping-decision .data-mapping-table` | `overflow,padding-top` | Data CSS line 869 |
| `CSS-1053` | `layout.css:5160` | `0-2-1`, base | `.data-mapping-decision .data-mapping-table table` | `table-layout` | Data CSS line 877 |
| `CSS-1054` | `layout.css:5164` | `0-2-1`, base | `.data-mapping-decision .data-mapping-table th` | `overflow-wrap,white-space` | Data CSS line 881 |
| `CSS-1055` | `layout.css:5164` | `0-2-1`, base | `.data-mapping-decision .data-mapping-table td` | `overflow-wrap,white-space` | Data CSS line 881 |
| `CSS-1081` | `layout.css:5311` | `0-1-1`, base | `.data-source-advanced > summary` | `color,cursor,font-size` | Data CSS line 943 |
| `CSS-1207` | `layout.css:5961` | `0-1-0`, `max-width:900px` | `.data-source-decision-grid` | `grid-template-columns` | Data CSS line 859 |
| `CSS-1495` | `layout.css:7148` | `0-1-0`, base | `.modeling-data-plot-panel` | `min-height,min-width` | Data CSS line 530 |
| `CSS-1499` | `layout.css:7176` | `0-1-0`, base | `.modeling-data-plot-panel` | `min-height,overflow` | Data CSS line 530 |

`CSS-1495`와 `CSS-1499`의 producer file 이름만 보면 shared Modeling layout처럼 보이지만 실제
emission은 Data 전용이다. `ModelingWorkspaceLayout`의 `dataSplit` branch는 `dataLayoutMode`가 있고
`ResizeObserver`가 존재할 때만 `.modeling-data-plot-panel`을 만든다. 이 prop을 전달하는 유일한
caller는 `modeling-data-workspace.tsx`의 Data workspace다. Process/Fit의
`common-processing-workbench.tsx` caller는 이 prop을 전달하지 않아 fallback fragment에서 ribbon과
plot을 그대로 렌더링하며 해당 class를 만들지 않는다. JSON은 두 ID의 route를
`/modeling?stage=data`, `/datasets/processing?stage=data`로, state를
`dataLayoutMode=compact|content-fit`와 `ResizeObserver available`로 기록한다. 따라서 기존 Data lazy
CSS가 두 selector의 owner이며, 다음 unit은 이 positive/negative branch를 focused test로 먼저 고정한다.

### Property-level 이동 규칙

| Selector | 현재 cascade | 이동 규칙 |
| --- | --- | --- |
| `.data-mapping-resolved` | 세 legacy block 뒤에 same-specificity owned block이 load된다. Owned `border-left` shorthand는 legacy color/width/style에도 영향을 준다. | computed style에서 살아 있는 `display/gap/min-width` 등만 owned rule로 옮기고, owned override와 충돌하는 legacy longhand는 복제하지 않는다. |
| `.data-source-decision-grid` | legacy가 display/alignment/gap/container/min-width를 공급하고 owned CSS가 columns를 최종 결정한다. 900px media columns는 owned value 뒤에서 효력이 없다. | 살아 있는 generic layout property를 Data owner로 병합하고 obsolete media member는 전 viewport computed proof 뒤 제거한다. |
| mapping table/table/th/td | legacy와 owned rule이 서로 다른 property를 더하거나 wrap/overflow 값을 덮어쓴다. | `padding-top`, `table-layout`처럼 살아 있는 property만 병합한다. 최종 owned `overflow`, `overflow-wrap`, `white-space`를 유지한다. |
| advanced summary | legacy cursor가 살아 있고 owned color/font-size가 최종값이다. | cursor만 필요한지 keyboard/pointer로 확인해 병합하고 중복 color/font-size는 제거한다. |
| Data plot panel | Data-only split branch에서 legacy 두 block이 min-size/overflow를 공급하고 owned rule이 flex/alignment/background를 공급한다. | positive Data split과 negative Process/Fit fallback test를 고정한 뒤 최종 `min-width:0`, `min-height:240px`, `overflow:hidden`의 현재 geometry를 owned rule에서 명시한다. |

### 정확한 예상 delta와 acceptance

이 packet을 selector 추가 없이 그대로 병합하면 다음 결과가 나와야 한다.

| Metric | 현재 | M1A0 예상 |
| --- | ---: | ---: |
| global rule-groups / guard debt | 2,834 | 2,826 |
| expanded global selector rows | 3,585 | 3,573 |
| non-legacy same-selector rows | 25 | 13 |
| M1A same-selector packet | 12 | 0 |

예상치와 실제가 다르면 rule을 더 삭제해 숫자를 맞추지 말고 comma member/cascade 차이를 진단한다.
12행은 11개 rule-group을 건드리지만 완전히 사라지는 group은 8개다. `CSS-0979`의 group에는
`CSS-0976..0978`, `CSS-0997`의 group에는 `CSS-0996`, `CSS-1495`의 group에는 `CSS-1494`가 남으므로
세 group은 comma member만 축소한다. JSON의 `migrationPlan.nextBoundedUnit`이 이 membership과
`2,834 → 2,826` 계산을 결정적으로 검증한다.

필수 checks:

1. inventory check의 known-current 2,834/3,585/25가 migration 전 통과한다.
2. Data intake/workspace, common workbench와 Modeling layout focused tests가 통과하고, Data split은
   plot-panel class를 만들며 Process/Fit fallback은 만들지 않음을 검증한다.
3. production build가 base CSS와 Modeling/Data lazy CSS boundary를 유지한다.
4. `/modeling?stage=data`와 `/datasets/processing?stage=data`에서 normal, empty-new-session,
   long-invalid-mapping-blocked, mapping-resolved를 검증한다.
5. 1366×768, 1440×900, 1920×1080, 2560×1440, 3840×2160 100% zoom before/after 원본과
   header/navigator/control/graph 100%-pixel crop을 비교한다.
6. computed property provenance, page/local overflow, keyboard/focus, console, reload/session restore,
   last-valid graph를 확인한다.
7. 정보 위계, 공학 작업 흐름, responsive/wide-screen composition 세 #249 축을 각각 PASS로 기록한다.
8. frontend guard의 global debt와 `layout.css` hotspot baseline을 실제 감소량으로 낮춘다.

의도하지 않은 pixel/geometry 차이는 regression이다. DOM 변경, owner가 없는 shared dependency,
approved reference와 현재 owner direction의 충돌, 또는 lazy CSS load order를 보존할 수 없는 경우 중단한다.

## 이후 migration 순서

1. M1A0 Data same-selector 12행을 이동한다.
2. 남은 M1A Data selector를 component region별로 bounded 이동한다.
3. M1B Process, M1C Fit, M1D Export, M1E Modeling shell/family를 각각 분리한다.
4. M2 Materials를 search/tree/detail/card state와 함께 옮긴다.
5. M3A Administration과 M3B Activity를 서로 다른 owner file로 옮긴다.
6. feature가 빠진 뒤 M4 shared shell/token/primitive/layout을 정리한다.
7. 마지막 M6에서만 live zero-consumer를 증명한 dead selector를 제거한다.
8. HOLD 447행은 consumer가 둘 이상이거나 owner가 불명확하므로 owner split 전에는 이동하거나
   복제하지 않는다.

각 unit은 전 unit의 inventory JSON을 새 source에서 재생성하고 감소한 guard baseline을 다시 올리지
않는다. #261은 이 inventory unit만으로 완료하거나 닫지 않는다.

## Stop hook 진단 경계와 #283 correction Plan Mode 입력

Codex app-server `0.146.1`의 실제 Stop invocation을 별도 read-only turn에서 계측했다. 원본 stdin은
다음과 같았다.

```json
{"session_id":"01a01817-45c5-7f71-b533-dc1ca2219db3","turn_id":"01a01817-4766-7752-97da-e5cb6a178208","transcript_path":null,"cwd":"C:\\SourceCodes\\cae-material-platform-worktrees\\issue-261-fe06-css-inventory","hook_event_name":"Stop","model":"gpt-5.6-sol","permission_mode":"bypassPermissions","stop_hook_active":false,"last_assistant_message":"HOOK_DIAGNOSTIC_OK"}
```

실행 cwd는 payload와 같은
`C:\SourceCodes\cae-material-platform-worktrees\issue-261-fe06-css-inventory`였다. 실제 runner는
primary checkout의 `C:\SourceCodes\cae-material-platform\.codex\hooks.json`을 trusted source로
읽은 뒤 아래 outer process를 만들었다.

```text
C:\Users\pikac\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe
  -NoProfile -Command
  powershell -NoProfile -NonInteractive -Command "$root = git rev-parse --show-toplevel; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Set-Location -LiteralPath $root; uv run python (Join-Path $root '.codex/hooks/documentation_gate.py')"
```

outer `pwsh`가 큰따옴표 안 `$root`와 `$LASTEXITCODE`를 먼저 확장해서, 내부
`powershell.exe`가 실제 받은 `-Command` 인자는 다음처럼 변형됐다.

```text
 = git rev-parse --show-toplevel; if ( -ne 0) { exit  }; Set-Location -LiteralPath ; uv run python (Join-Path  '.codex/hooks/documentation_gate.py')
```

동일 cwd와 command nesting의 stderr 시작은 다음과 같았고, `git`, `uv`, Python gate는 생성되기
전에 exit 1이 됐다.

```text
= : The term '=' is not recognized as the name of a cmdlet, function, script file, or operable program.
At line:1 char:2
+  = git rev-parse --show-toplevel; if ( -ne 0) { exit  }; Set-Location ...
+  ~
-ne : The term '-ne' is not recognized as the name of a cmdlet, function, script file, or operable program.
Set-Location : Missing an argument for parameter 'LiteralPath'.
Join-Path : Cannot process command because of one or more missing mandatory parameters: ChildPath.
```

app-server가 보존한 실제 완료 event도 underlying stderr 대신 다음 generic failure만 노출했다.

```json
{"method":"hook/completed","params":{"threadId":"01a01817-45c5-7f71-b533-dc1ca2219db3","turnId":"01a01817-4766-7752-97da-e5cb6a178208","run":{"id":"stop:1:C:\\SourceCodes\\cae-material-platform\\.codex\\hooks.json","eventName":"stop","handlerType":"command","executionMode":"sync","scope":"turn","sourcePath":"C:\\SourceCodes\\cae-material-platform\\.codex\\hooks.json","source":"project","displayOrder":1,"status":"failed","statusMessage":"Checking unfinished visual documentation","startedAt":1787110579,"completedAt":1787110580,"durationMs":511,"entries":[{"kind":"error","text":"hook exited with code 1"}]}}}
```

계측한 runner PATH로 `where.exe uv`를 다시 실행한 결과는 아래 순서였다. 따라서 `.local`의 구버전이
선택된 것이 원인이 아니다.

```text
C:\Users\pikac\AppData\Local\hermes\bin\uv.exe
uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)
C:\Users\pikac\.local\bin\uv.exe
uv 0.11.0 (1f31f0e9f 2026-03-23 x86_64-pc-windows-msvc)
```

또한 `hooks/list(cwds=[이 worktree])`는 active worktree의 수정 여부와 무관하게 primary checkout의
`.codex/hooks.json`, 기존 command와 `trustStatus: trusted`를 반환했다. 이는 linked worktree에서
hook config는 primary checkout에서 읽고 cwd는 linked worktree를 쓰는 Codex host 결함
([openai/codex#23996](https://github.com/openai/codex/issues/23996))과 일치한다. main이나 다른
worktree를 수정해야만 현재 앱의 실제 source를 바꿀 수 있으므로 이번 승인된 #261 inventory 범위를
넘는다.

후속 #283 correction은 Plan Mode에서 먼저 #283의 현재 mypy/pytest 기준선 복구 권위에 hook correction을
포함할지 owner 확인을 받아야 한다. 승인될 때의 최소 후보는 Stop handler의 Windows command 안쪽을
single-quoted script로 바꿔 outer expansion을 막는 것이다.

```text
powershell -NoProfile -NonInteractive -Command '$root = git rev-parse --show-toplevel; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Set-Location -LiteralPath $root; uv run python (Join-Path $root ''.codex/hooks/documentation_gate.py'')'
```

이 후보는 동일한 outer `pwsh` nesting, cwd, Stop payload에서 exit 0을 냈다. #283의 실행 unit은
일반 checkout 또는 hook source와 branch가 동일한 격리 clone에서 `hooks/list` source를 먼저 증명하고,
실제 `hook/completed.status=success`, 원본 stdin, cwd, PATH/두 uv 해석 순서, gate output을 다시
캡처해야 한다. `PreToolUse`의 같은 quoting pattern은 별도 issue-owned 범위 없이는 함께 바꾸지 않는다.
이번 진단에서 만든 `.codex` 변경, probe source/binary와 temp log는 모두 제거했다.

## 현재 단위 검증 기록

| Gate | 결과 |
| --- | --- |
| Repository/branch/base | PASS — remote와 Git common dir는 `pikachu444/cae-material-platform`, branch와 HEAD/origin-main은 요청한 `issue-261-fe06-css-inventory` / `be4166d...`다. 시작 worktree는 clean이었다. |
| Inventory determinism | PASS — 2,834 rule-group과 3,585 selector 행, source SHA/line/hash/cascade/consumer 결과가 byte-for-byte 재생성된다. |
| Inventory consumer regression | PASS — static/template/conditional `className`, selector reference 분리와 실제 `processing-workbench-page`, `modeling-support-drawer`, `has-linked-response` 및 생성 JSON batch 회귀 4/4가 통과한다. |
| #256 frontend guard | 초기 FAIL 후 PASS — baseline `sourceSha`만 `6f0c991...`에서 현재 merge-base `be4166d...`로 고쳤다. Allowance/count/rule은 불변이며 최종 0 violations, 기존 warning 15개다. |
| Production build | PASS — TypeScript, Vite와 bundle budget 통과. Base CSS 344.91 kB, Modeling CSS 9.72 kB, Data CSS 21.85 kB로 lazy boundary가 확인됐다. |
| Frontend guard tests | PASS — 17/17. Global-selector debt 감소 허용, 신규 selector 차단과 baseline provenance mismatch 차단을 포함한다. |
| User guide / documentation impact | PASS — pinned `uv run`으로 user-guide 20문서/119 current captures/743 local links/2,254 images와 documentation impact 5 changed files/0 visual sources를 확인했다. |
| Product runtime / Compose / DB / browser / reload / five viewport | N/A — production React/CSS/DOM/data를 변경하지 않은 inventory-only unit이다. |
| User guide / screenshot manifest mutation | N/A — `verify_documentation_impact(worktree)`가 현재 5개 변경을 visual source 0개로 분류한다. 따라서 current guide, screenshot manifest, current PNG를 바꾸지 않으며, changed unconsumed visual source에만 허용되는 documentation-impact exception YAML도 만들지 않는다. 이 행이 issue-owned N/A 기록이다. |
| Codex Stop documentation hook | SCOPE-EXPANSION BOUNDARY — `verify_documentation_impact(worktree)` 자체는 uv `0.12.5`에서 PASS지만 실제 app hook은 gate 이전 outer PowerShell 변수 확장으로 code 1이다. runner PATH는 Hermes `0.12.5`를 `.local` `0.11.0`보다 먼저 해석하므로 uv가 원인이 아니다. host는 primary checkout의 hook config를 강제하므로 main/다른 worktree를 건드리지 않는 이번 단위에서는 수정하지 않고 #283 Plan Mode correction 입력으로 남겼다. |
| Diff hygiene | PASS — tracked diff와 새 evidence/script의 trailing whitespace 검사가 통과한다. |
| Toolchain diagnostic | repository 요구 uv `0.12.5`와 현재 실행기가 일치한다. Node `24.18.0`/npm `11.13.0`은 요구 `24.19.0`/`11.17.0`보다 낮아 `npm ci` engine warning은 남지만 production build와 해당 검사는 통과했다. |

Commit, push, GitHub comment, PR, ready transition, merge와 issue close는 모두 수행하지 않는다.
