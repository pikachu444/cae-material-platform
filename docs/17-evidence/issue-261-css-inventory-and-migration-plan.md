# Issue #261 FE-06 CSS inventory와 migration plan

상태: 첫 bounded unit 완료 후보 — inventory와 plan만 포함하며 production migration은 시작하지 않음

초기 inventory 기준: `main@be4166d840280d5ff0e0a419815002f60b31eeab`; 출판 rebase 기준: `main@22bc9d81b3d9e0facf3ebd436b8a486c5bcbe070`

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

## M1A0 실행 결과 — committed candidate

승인된 inventory 단위는 `bb7a37d74d5f42e591a5043983a09efd61db689c`로 먼저 커밋했다. 문서 영향의
byte-identical CSS migration proof correction은 별도 커밋
`4500fe86a5af5f672eaf1eec6b760740cf55ed8a`, M1A0는
`e9cad946604bce23197382d206ccf286dd970d51`로 커밋했다. M1A0는 React, DOM, API, route,
state, token 또는 breakpoint를 변경하지 않고 아래 effective declaration만 Data owner로 이동했다.

| Selector | Data owner에 남긴 effective declaration | 제거한 legacy dependency |
| --- | --- | --- |
| `.data-mapping-resolved` | `display:flex`, `align-items:center`, `gap:8px`, `min-width:0`, 기존 `padding-left:0`/`border-left:0` | 세 exact legacy member와 owned shorthand에 이미 가려진 warning/success border longhand |
| `.data-source-decision-grid` | `display:grid`, one-column owned columns, `align-items:start`, `gap:8px`, `min-width:0`, `container-type:inline-size` | base two-column rule과 owned rule 뒤에서 효력이 없던 900 px member |
| mapping table | mapping table에만 `padding-top:2px`, table에 `table-layout:fixed`; owned overflow/wrap/white-space 유지 | 네 exact legacy member |
| `.data-source-advanced > summary` | 기존 owned color/font-size와 `cursor:pointer` | 중복 color/font-size와 legacy cursor provider |
| `.modeling-data-plot-panel` | `min-width:0`, `min-height:240px`, `overflow:hidden`과 기존 flex/centering | Data-only split의 두 legacy member |

전역 inventory의 실제 감소는 승인 예상치와 정확히 일치한다.

| Metric | inventory baseline | M1A0 candidate | Delta |
| --- | ---: | ---: | ---: |
| global rule-groups / guard debt | 2,834 | 2,826 | -8 |
| expanded global selector rows | 3,585 | 3,573 | -12 |
| non-legacy same-selector rows | 25 | 13 | -12 |
| M1A Data rows | 233 | 221 | -12 |
| M1A0 exact legacy residual | 12 | 0 | -12 |

### Visual 및 guide evidence

- [M1A0 image manifest](images/issue-261-fe06-m1a0-data-same-selector-overlap/manifest.json)은 100% zoom,
  DPR 1, Standard density에서 두 Data route의 normal 다섯 viewport와
  empty/invalid/locally-scrolled 상태 before/after 원본 32개 및 `/modeling` 원본에서 직접 자른
  100%-pixel crop 64개를 기록한다.
- normal/state 원본 8쌍은 이름별 SHA-256과 bytes가 모두 동일하다. header, stage navigator,
  table/form controls와 graph crop은 resize/resampling 없이 source pixel에서 잘랐다.
- reload/session restore는 두 targeted capture run에서 모두 통과했다. 승인 범위를 넘는 session PNG는
  영구 packet에 남기지 않았다.
- 현재 user-guide Data 이미지 8개도 candidate after와 byte-identical하다. 현재 이미지는 바꾸지 않고
  `docs/user-guide/screenshot-manifest.yaml`의 duplicate provenance에 #261 before/after를 추가했다.
- 독립 감사 finding 뒤 `/datasets/processing?stage=data&family=metal`을 inventory commit의 읽기 전용
  `git archive` baseline과 현재 candidate에서 별도로 캡처했다. 다섯 normal/mapping-resolved viewport와
  empty/long-invalid/locally-scrolled 1440 상태 8쌍은 before/after뿐 아니라 대응하는 `/modeling` 원본과도
  모두 byte-identical하다. 각 pair는 exact route, source SHA, server, SHA-256을 manifest에 보존한다.
- Main original-resolution review는 #249 세 축을 각각 PASS로 판정했다: 현재 selection과 Data가 지배하는
  정보 위계, Library/Local file → exact Test Data → graph → Process 작업 흐름, 1366–3840에서 explorer/form의
  readable bound와 graph의 semantic elasticity가 모두 before와 동일하다.
- automated 3840 capture는 geometry 증거이며 실제 Windows 4K readability를 주장하지 않는다.
  물리 판정은 `DEFERRED_TO_223`이다.

<details>
<summary>Retained before/after originals and direct 100%-pixel crops</summary>

- [before original normal 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-1366x768.png)
- [before header 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1366x768-header-100pct.png)
- [before navigator 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1366x768-navigator-100pct.png)
- [before controls 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1366x768-controls-100pct.png)
- [before graph 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1366x768-graph-100pct.png)
- [before original normal 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-1440x900.png)
- [before header 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1440x900-header-100pct.png)
- [before navigator 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1440x900-navigator-100pct.png)
- [before controls 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1440x900-controls-100pct.png)
- [before graph 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1440x900-graph-100pct.png)
- [before original normal 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-1920x1080.png)
- [before header 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1920x1080-header-100pct.png)
- [before navigator 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1920x1080-navigator-100pct.png)
- [before controls 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1920x1080-controls-100pct.png)
- [before graph 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-1920x1080-graph-100pct.png)
- [before original normal 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-2560x1440.png)
- [before header 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-2560x1440-header-100pct.png)
- [before navigator 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-2560x1440-navigator-100pct.png)
- [before controls 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-2560x1440-controls-100pct.png)
- [before graph 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-2560x1440-graph-100pct.png)
- [before original normal 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-3840x2160.png)
- [before header 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-3840x2160-header-100pct.png)
- [before navigator 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-3840x2160-navigator-100pct.png)
- [before controls 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-3840x2160-controls-100pct.png)
- [before graph 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-3840x2160-graph-100pct.png)
- [before original empty new session](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-empty-1440x900.png)
- [before empty header](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-empty-1440x900-header-100pct.png)
- [before empty navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-empty-1440x900-navigator-100pct.png)
- [before empty controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-empty-1440x900-controls-100pct.png)
- [before empty graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-empty-1440x900-graph-100pct.png)
- [before original invalid mapping](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-invalid-1440x900.png)
- [before invalid header](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-1440x900-header-100pct.png)
- [before invalid navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-1440x900-navigator-100pct.png)
- [before invalid controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-1440x900-controls-100pct.png)
- [before invalid graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-1440x900-graph-100pct.png)
- [before original invalid mapping locally scrolled](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/originals/modeling-data-invalid-scrolled-1440x900.png)
- [before invalid-scrolled header](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png)
- [before invalid-scrolled navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png)
- [before invalid-scrolled controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png)
- [before invalid-scrolled graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png)
- [after original normal 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-1366x768.png)
- [after header 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1366x768-header-100pct.png)
- [after navigator 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1366x768-navigator-100pct.png)
- [after controls 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1366x768-controls-100pct.png)
- [after graph 1366x768](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1366x768-graph-100pct.png)
- [after original normal 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-1440x900.png)
- [after header 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1440x900-header-100pct.png)
- [after navigator 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1440x900-navigator-100pct.png)
- [after controls 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1440x900-controls-100pct.png)
- [after graph 1440x900](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1440x900-graph-100pct.png)
- [after original normal 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-1920x1080.png)
- [after header 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1920x1080-header-100pct.png)
- [after navigator 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1920x1080-navigator-100pct.png)
- [after controls 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1920x1080-controls-100pct.png)
- [after graph 1920x1080](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-1920x1080-graph-100pct.png)
- [after original normal 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-2560x1440.png)
- [after header 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-2560x1440-header-100pct.png)
- [after navigator 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-2560x1440-navigator-100pct.png)
- [after controls 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-2560x1440-controls-100pct.png)
- [after graph 2560x1440](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-2560x1440-graph-100pct.png)
- [after original normal 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-3840x2160.png)
- [after header 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-3840x2160-header-100pct.png)
- [after navigator 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-3840x2160-navigator-100pct.png)
- [after controls 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-3840x2160-controls-100pct.png)
- [after graph 3840x2160](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-3840x2160-graph-100pct.png)
- [after original empty new session](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-empty-1440x900.png)
- [after empty header](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-empty-1440x900-header-100pct.png)
- [after empty navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-empty-1440x900-navigator-100pct.png)
- [after empty controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-empty-1440x900-controls-100pct.png)
- [after empty graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-empty-1440x900-graph-100pct.png)
- [after original invalid mapping](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-invalid-1440x900.png)
- [after invalid header](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-1440x900-header-100pct.png)
- [after invalid navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-1440x900-navigator-100pct.png)
- [after invalid controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-1440x900-controls-100pct.png)
- [after invalid graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-1440x900-graph-100pct.png)
- [after original invalid mapping locally scrolled](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/originals/modeling-data-invalid-scrolled-1440x900.png)
- [after invalid-scrolled header](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png)
- [after invalid-scrolled navigator](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png)
- [after invalid-scrolled controls](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png)
- [after invalid-scrolled graph](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png)

</details>

<details>
<summary>Retained /datasets/processing route-identified before/after originals</summary>

- 1366×768 normal/mapping-resolved: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-1366x768.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-1366x768.png)
- 1440×900 normal/mapping-resolved: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-1440x900.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-1440x900.png)
- 1920×1080 normal/mapping-resolved: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-1920x1080.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-1920x1080.png)
- 2560×1440 normal/mapping-resolved: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-2560x1440.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-2560x1440.png)
- 3840×2160 normal/mapping-resolved: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-3840x2160.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-3840x2160.png)
- 1440×900 empty-new-session: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-empty-1440x900.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-empty-1440x900.png)
- 1440×900 long-invalid-mapping-blocked: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-invalid-1440x900.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-invalid-1440x900.png)
- 1440×900 long-invalid locally scrolled: [before](images/issue-261-fe06-m1a0-data-same-selector-overlap/before/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png) / [after](images/issue-261-fe06-m1a0-data-same-selector-overlap/after/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png)

</details>

### 검증 상태

Inventory regeneration은 2,826 groups / 3,573 rows / 13 cross-CSS duplicate rows와 M1A0 residual 0을
확인했다. 최종 candidate에서 다음 검사를 실행했다.

- `node --test scripts/check_issue_261_css_inventory.test.mjs`: 4 tests PASS.
- `node scripts/check_issue_261_css_inventory.mjs`: PASS; expected/actual delta와 residual 0 일치.
- Data intake/workspace, Modeling layout, common workbench focused Vitest: 4 files / 56 tests PASS.
- `npm run test:frontend-guard`: 17 tests PASS. `npm run check:frontend-guard`: 0 violations,
  기존 baseline warnings 15개만 유지. comma group 세 개는 살아 있는 legacy member의 새 fingerprint를
  #261 owner exception으로 정확히 고정했다.
- `npm run build`: TypeScript와 Vite production build PASS; Data lazy CSS boundary 유지.
- `/modeling` before/after targeted browser capture: 각 11 state PASS. 독립 감사 correction으로
  `/datasets/processing` before/after도 각각 다섯 normal viewport와 세 위험 상태가 PASS했다. bounded
  packet은 두 route의 originals 32개와 `/modeling` 원본에서 직접 자른 100%-pixel crops 64개를 유지하며
  manifest hash, dimensions, crop source pixels, primary original 8쌍과 alias original 8쌍의 byte equality를
  다시 검증했다. alias 8쌍은 대응 primary route 원본과도 byte-identical하다.
- `uv run cmp-check-user-guide --root .`: PASS; 20 guide documents, 119 current captures,
  163 classified Markdown files, 840 local links, 2,350 images. orphan image 0이며 실제 27 crop hash group과
  8 original group의 provenance가 exact path로 등록되어 있다.
- `git diff --check`: PASS. implementation server의 worktree-owned 5174 listener를 확인 후 종료했고,
  승인된 exact M1A0 candidate를 위 SHA로 커밋했다.

Owner-approved correction은 이 false blocker를 일반 exception으로 바꾸지 않았다. 변경된 evidence
manifest의 `documentation_impact` block이 정확한 CSS visual source 두 개, migration 전 source SHA와
등록된 original 전부의 current/before/after 경로를 선언한다. `cmp-check-doc-impact`는 이 block이 이번
diff에 포함되고 다음 조건을 모두 실제 bytes에서 다시 증명할 때만 guide Markdown/current PNG diff를
대신 인정한다.

- visual source 전체가 production `.css`이고 선언 목록과 exact match하며 현재 CSS SHA-256도 proof와
  일치한다.
- source SHA는 current branch ancestor이며 각 CSS는 그 source에서 실제로 변경되었다.
- browser zoom 100%, DPR 1, Standard와 mandatory five viewport normal originals가 모두 있다.
- manifest의 모든 before/after original pair를 current guide capture와 1:1로 덮는다.
- 세 파일의 actual bytes와 SHA-256가 같고 screenshot manifest의 한 duplicate group에 함께 등록된다.
- current PNG 자체는 변경되지 않는다. TSX, 일부 CSS, wildcard 또는 선언만으로는 이 경로를 사용할 수
  없다.

Focused correction tests는 정상 pass와 image bytes drift, stale CSS hash, viewport 누락, visual source
불일치, TSX 포함, duplicate provenance 누락, non-ancestor source SHA를 각각 거부한다. 실제
`uv run cmp-check-doc-impact --root . --mode worktree`도 `2 byte-identical CSS visual sources by #261`로
PASS한다. 따라서 PNG 재인코딩이나 무관한 current screenshot 없이 기존 M1A0 evidence가 documentation
impact gate를 충족한다.

## M1A1 실행 결과 — Data source-tabs component ownership

M1A1은 M1A0 commit `e9cad946604bce23197382d206ccf286dd970d51`에서 남은 M1A 221행 중
Data source-tab component의 정확한 다섯 selector member만 선택했다. production React/DOM, route,
state, token, breakpoint, current guide PNG와 guide Markdown은 바꾸지 않는다.

### 파일 소유권과 금지 확장

| Owned path | 역할 |
| --- | --- |
| `apps/web/src/design/layout.css` | 아래 다섯 legacy global selector rule 제거 |
| `apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css` | 같은 rule bytes와 내부 순서를 기존 Data owner의 더 구체적인 rule 바로 앞에 수용 |
| `apps/web/frontend-guard-baseline.json` | 감소한 global count/line과 살아 있는 exact fingerprint, 이동한 literal weight의 issue-owned 위치만 동기화 |
| `scripts/check_issue_261_css_inventory.mjs` | M1A0 historical delta를 고정하고 M1A1 exact selector/residual/delta를 검사 |
| `scripts/check_issue_261_css_inventory.test.mjs` | M1A1 packet과 다음 M1A2 router 회귀 |
| `docs/17-evidence/issue-261-css-selector-inventory.json` | M1A1 candidate에서 결정적으로 재생성한 inventory |
| `docs/17-evidence/issue-261-css-inventory-and-migration-plan.md` | 이 owned evidence와 다음 bounded router |
| `docs/user-guide/screenshot-manifest.yaml` | byte-identical M1A1 original/crop의 exact duplicate provenance |
| `docs/17-evidence/images/issue-261-fe06-m1a1-data-source-tabs/**` | 두 route before/after originals, direct crops와 strict manifest |

금지 범위는 TSX/DOM/API/session contract 수정, selector rename, token normalization, shared shell/density
정리, adjacent Data selector 이동, route별 workaround, current guide PNG 재인코딩, guide prose 변경과 M1A2
선행 구현이다. 특히 원래 `font-weight:650`을 token으로 바꾸지 않고 exact declaration으로 옮겼다.

### 정확한 selector, consumer와 cascade

| Historical inventory ID | Selector | Consumer / route-state | 보존한 cascade |
| --- | --- | --- | --- |
| CSS-0971 | `.data-source-tabs` | `modeling-data-intake.tsx`, `modeling-data-workspace.tsx`; 두 Data route의 Library/Local file normal·empty·invalid·recovery | `display:flex`, `gap:2px`, border를 더 구체적인 `.modeling-data-workspace .data-source-tabs` 앞에 유지 |
| CSS-0972 | `.data-source-tabs button` | 같은 두 producer의 tab buttons | control size, padding, border, color, font, weight와 cursor를 더 구체적인 owned button rule 앞에 유지 |
| CSS-0973 | `.data-source-tabs button[aria-selected="true"]` | 선택된 Library 또는 Local file tab | selected border/color의 selector와 source order 유지 |
| CSS-0974 | `.data-source-tabs button:hover` | 두 source-tab의 pointer hover | owned base와 같은 기존 bundle 순서 안에서 hover color rule 순서 유지 |
| CSS-0975 | `.data-source-tabs button:focus-visible` | keyboard focus recovery | outline와 negative offset을 그대로 유지 |

다섯 selector는 exact duplicate나 cross-CSS duplicate가 아니며 dead/wide/route-shell workaround도 아니다.
TARGET-0678의 border-bottom과 TARGET-0679의 color는 이 component 내부 cascade dependency다. block은
선언 bytes와 내부 순서를 보존한 채 Data owner의 기존 higher-specificity rules 바로 앞에 들어가므로
두 producer와 두 route의 effective cascade가 바뀌지 않는다.

### Inventory, visual과 contract evidence

| Metric | M1A0 source | M1A1 candidate | Delta |
| --- | ---: | ---: | ---: |
| global rule-groups / guard debt | 2,826 | 2,821 | -5 |
| expanded global selector rows | 3,573 | 3,568 | -5 |
| cross-CSS duplicate rows | 13 | 13 | 0 |
| M1A Data rows | 221 | 216 | -5 |
| M1A1 exact legacy residual | 5 | 0 | -5 |

[M1A1 image manifest](images/issue-261-fe06-m1a1-data-source-tabs/manifest.json)은 browser zoom 100%,
DPR 1, Standard density에서 `/modeling?stage=data&family=metal`과
`/datasets/processing?stage=data&family=metal`의 normal 다섯 viewport 및 empty/invalid/locally-scrolled
상태를 등록한다. 두 route 합계 before/after original 32개와 primary `/modeling` 원본의 direct
100%-source-pixel crop 64개를 남겼다. primary 8쌍과 alias 8쌍은 각각 SHA-256와 bytes가 같고 alias
after도 대응 primary after와 같다. 모든 96 PNG는 screenshot manifest의 exact duplicate provenance에
등록했다. 현재 guide Data original 8개도 current/before/after가 bytes와 hash까지 같다.

<details>

<summary>M1A1 retained primary-route originals and direct 100%-pixel crops</summary>

- [before normal original  1366x768](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-1366x768.png)
- [before normal crop header 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1366x768-header-100pct.png)
- [before normal crop navigator 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1366x768-navigator-100pct.png)
- [before normal crop controls 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1366x768-controls-100pct.png)
- [before normal crop graph 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1366x768-graph-100pct.png)
- [before normal original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-1440x900.png)
- [before normal crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1440x900-header-100pct.png)
- [before normal crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1440x900-navigator-100pct.png)
- [before normal crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1440x900-controls-100pct.png)
- [before normal crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1440x900-graph-100pct.png)
- [before normal original  1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-1920x1080.png)
- [before normal crop header 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1920x1080-header-100pct.png)
- [before normal crop navigator 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1920x1080-navigator-100pct.png)
- [before normal crop controls 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1920x1080-controls-100pct.png)
- [before normal crop graph 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-1920x1080-graph-100pct.png)
- [before normal original  2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-2560x1440.png)
- [before normal crop header 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-2560x1440-header-100pct.png)
- [before normal crop navigator 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-2560x1440-navigator-100pct.png)
- [before normal crop controls 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-2560x1440-controls-100pct.png)
- [before normal crop graph 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-2560x1440-graph-100pct.png)
- [before normal original  3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-3840x2160.png)
- [before normal crop header 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-3840x2160-header-100pct.png)
- [before normal crop navigator 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-3840x2160-navigator-100pct.png)
- [before normal crop controls 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-3840x2160-controls-100pct.png)
- [before normal crop graph 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-3840x2160-graph-100pct.png)
- [before empty-new-session original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-empty-1440x900.png)
- [before empty-new-session crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-empty-1440x900-header-100pct.png)
- [before empty-new-session crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-empty-1440x900-navigator-100pct.png)
- [before empty-new-session crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-empty-1440x900-controls-100pct.png)
- [before empty-new-session crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-empty-1440x900-graph-100pct.png)
- [before long-invalid-mapping-blocked original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-invalid-1440x900.png)
- [before long-invalid-mapping-blocked crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-1440x900-header-100pct.png)
- [before long-invalid-mapping-blocked crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-1440x900-navigator-100pct.png)
- [before long-invalid-mapping-blocked crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-1440x900-controls-100pct.png)
- [before long-invalid-mapping-blocked crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-1440x900-graph-100pct.png)
- [before long-invalid-mapping-blocked-scrolled original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/originals/modeling-data-invalid-scrolled-1440x900.png)
- [before long-invalid-mapping-blocked-scrolled crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png)
- [before long-invalid-mapping-blocked-scrolled crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png)
- [before long-invalid-mapping-blocked-scrolled crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png)
- [before long-invalid-mapping-blocked-scrolled crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/before/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png)
- [after normal original  1366x768](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-1366x768.png)
- [after normal crop header 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1366x768-header-100pct.png)
- [after normal crop navigator 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1366x768-navigator-100pct.png)
- [after normal crop controls 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1366x768-controls-100pct.png)
- [after normal crop graph 1366x768](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1366x768-graph-100pct.png)
- [after normal original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-1440x900.png)
- [after normal crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1440x900-header-100pct.png)
- [after normal crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1440x900-navigator-100pct.png)
- [after normal crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1440x900-controls-100pct.png)
- [after normal crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1440x900-graph-100pct.png)
- [after normal original  1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-1920x1080.png)
- [after normal crop header 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1920x1080-header-100pct.png)
- [after normal crop navigator 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1920x1080-navigator-100pct.png)
- [after normal crop controls 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1920x1080-controls-100pct.png)
- [after normal crop graph 1920x1080](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-1920x1080-graph-100pct.png)
- [after normal original  2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-2560x1440.png)
- [after normal crop header 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-2560x1440-header-100pct.png)
- [after normal crop navigator 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-2560x1440-navigator-100pct.png)
- [after normal crop controls 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-2560x1440-controls-100pct.png)
- [after normal crop graph 2560x1440](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-2560x1440-graph-100pct.png)
- [after normal original  3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-3840x2160.png)
- [after normal crop header 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-3840x2160-header-100pct.png)
- [after normal crop navigator 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-3840x2160-navigator-100pct.png)
- [after normal crop controls 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-3840x2160-controls-100pct.png)
- [after normal crop graph 3840x2160](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-3840x2160-graph-100pct.png)
- [after empty-new-session original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-empty-1440x900.png)
- [after empty-new-session crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-empty-1440x900-header-100pct.png)
- [after empty-new-session crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-empty-1440x900-navigator-100pct.png)
- [after empty-new-session crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-empty-1440x900-controls-100pct.png)
- [after empty-new-session crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-empty-1440x900-graph-100pct.png)
- [after long-invalid-mapping-blocked original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-invalid-1440x900.png)
- [after long-invalid-mapping-blocked crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-1440x900-header-100pct.png)
- [after long-invalid-mapping-blocked crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-1440x900-navigator-100pct.png)
- [after long-invalid-mapping-blocked crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-1440x900-controls-100pct.png)
- [after long-invalid-mapping-blocked crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-1440x900-graph-100pct.png)
- [after long-invalid-mapping-blocked-scrolled original  1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/originals/modeling-data-invalid-scrolled-1440x900.png)
- [after long-invalid-mapping-blocked-scrolled crop header 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png)
- [after long-invalid-mapping-blocked-scrolled crop navigator 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png)
- [after long-invalid-mapping-blocked-scrolled crop controls 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png)
- [after long-invalid-mapping-blocked-scrolled crop graph 1440x900](images/issue-261-fe06-m1a1-data-source-tabs/after/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png)

</details>

<details>

<summary>M1A1 retained /datasets/processing route-identified before/after originals</summary>

- normal-mapping-resolved 1366x768: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-1366x768.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-1366x768.png)
- normal-mapping-resolved 1440x900: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-1440x900.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-1440x900.png)
- normal-mapping-resolved 1920x1080: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-1920x1080.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-1920x1080.png)
- normal-mapping-resolved 2560x1440: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-2560x1440.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-2560x1440.png)
- normal-mapping-resolved 3840x2160: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-3840x2160.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-3840x2160.png)
- empty-new-session 1440x900: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-empty-1440x900.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-empty-1440x900.png)
- long-invalid-mapping-blocked 1440x900: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-invalid-1440x900.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-invalid-1440x900.png)
- long-invalid-mapping-blocked-locally-scrolled 1440x900: [before](images/issue-261-fe06-m1a1-data-source-tabs/before/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png) / [after](images/issue-261-fe06-m1a1-data-source-tabs/after/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png)

</details>


원본 해상도 검토에서 five-viewport normal, empty session, invalid mapping과 locally-scrolled recovery가
모두 visibility, clipping, wrapping, selected source, table/form control, persistent graph와 action
reachability를 보존했다. #249 정보 위계, engineering task flow와 responsive/wide-screen composition은
각각 PASS다. automated 3840×2160 geometry는 PASS이며 실제 Windows 4K 물리 가독성은 권위대로
`DEFERRED_TO_223`이다. Library↔Local file 선택, exact Test Data/session restoration, invalid mapping 차단,
last-valid graph와 Continue to Process contract는 focused Data/workbench tests와 reload capture로 보존한다.

M1A1 candidate에서 inventory unit 4/4, focused Data/Modeling Vitest 56/56, frontend guard tests 17/17,
frontend guard 0 violation/기존 warning 15, TypeScript/Vite production build가 PASS했다. 첫 guard run의
line-sensitive stale fingerprint 세 개와 이동된 기존 literal weight 한 개는 범위를 넓히지 않고 현재
exact source location/fingerprint로 고쳤으며 재실행에서 통과했다. manifest 자체 검사는 80 registered
images, 96 PNG, 64 direct crops, primary 8쌍, alias 8쌍과 screenshot references 96개를 모두 다시 읽어
PASS했다.

`uv run cmp-check-user-guide --root .`은 evidence Markdown에 위 96개 exact link를 등록한 뒤 20 guide
documents, 119 current captures, 937 local links와 2,446 images로 PASS했고 `git diff --check`도 PASS했다.
첫 `uv run cmp-check-doc-impact --root . --mode worktree`는
`exactly one CSS visual-preservation manifest may change`로 FAIL했다. image/CSS hash나 viewport drift가
아니라 worktree mode가 `origin/main...HEAD`의 committed M1A0 manifest와 현재 untracked M1A1 manifest를
validation 전에 함께 active candidate로 센 결정적 검증 결함이었다. 같은 독립 감사자의 첫 verdict도
M1A1 CSS/evidence 자체는 sound하지만 이 blocker 때문에 `CHANGES_REQUESTED`였다.

Owner가 별도 승인한 correction commit `4db84aa2e0a40907efa92fcb9a3467e6fb3b89c0`은
`backend/src/cmp/tools/documentation_impact.py`와 해당 contract tests만 소유한다. 모든 candidate를
기존 strict schema로 먼저 파싱하고, 여러 proof가 있을 때 현재 CSS 전체의
기록 SHA-256과 일치하는 proof가 정확히 하나인지 고른다. 나머지는 같은 visual CSS 집합을 다루며
HEAD에 committed되고 HEAD bytes에서 변경되지 않은 historical proof일 때만 제외한다. 따라서 untracked,
staged 또는 modified stale proof와 current hash를 함께 주장하는 두 proof는 계속 실패한다. 선택된 현재
proof는 기존의 exact visual source, ancestor/source change, current CSS hash, zoom/DPR/density, five viewport,
current/before/after actual PNG bytes/hash와 duplicate provenance 검증을 모두 그대로 통과해야 한다.

Focused correction 12/12와 전체 documentation-impact contract 93/93이 PASS했다. 최소 matrix는 M1A0-only,
M1A1-only, committed M1A0 + current M1A1의 sole-current 선택, two-current 거부를 포함하며 modified stale
historical proof도 거부한다. 실제 worktree gate는 204 changed files, 2 visual sources,
`2 byte-identical CSS visual sources by #261`로 PASS했다. correction 전후 M1A1 tracked diff와 97 untracked
evidence의 byte fingerprint가 각각 `7244bc28...`와 `ea7e6601...`로 동일함도 확인했다. 이어서 inventory
4/4 및 2,821/3,568/M1A 216/residual 0, focused Vitest 56/56, frontend guard 17/17과 0 violation/15 warning,
production build, user-guide 20 documents/119 current/937 links/2,446 images를 다시 PASS했다.
같은 `independent_auditor_terra_high`는 correction이 normal proof를 약화하지 않고 M1A1이 exact 다섯
selector 범위를 유지한다고 확인해 material finding 없이 `APPROVE`했다. correction을 먼저 별도
커밋하고 M1A1 exact candidate를 다음 커밋으로 둘 수 있다는 최종 disposition이다.

## M1A2 실행 결과 — Data source-advanced component ownership

M1A2는 committed M1A1 `8361e85d80e254759e170c1ce7355b9fe49e56ce`을 implementation base로
사용한다. React, DOM, route, API, session, copy, token 또는 breakpoint를 바꾸지 않고 Local file의
`File details` 컴포넌트가 사용하는 세 legacy selector만 기존 Data stage stylesheet로 이동했다.

### 파일 소유권과 금지 확장

| Path | M1A2 ownership |
| --- | --- |
| `apps/web/src/design/layout.css` | 아래 세 exact selector의 legacy rule-group만 제거한다. 다른 Data, shared 또는 HOLD selector는 건드리지 않는다. |
| `apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css` | 같은 effective declaration을 existing lazy Data owner에 둔다. 뒤쪽 shared metadata token의 현재 cascade를 보존한다. |
| `apps/web/frontend-guard-baseline.json` | 실제 global rule-group과 `layout.css` line 감소만 잠근다. allowance를 늘리지 않는다. |
| `scripts/check_issue_261_css_inventory.mjs`, `scripts/check_issue_261_css_inventory.test.mjs`, `docs/17-evidence/issue-261-css-selector-inventory.json` | M1A2 3/3/3/0 packet, zero residual과 다음 M1A3 경계를 고정한다. |
| `docs/user-guide/screenshot-manifest.yaml`, 이 evidence 문서, `docs/17-evidence/images/issue-261-fe06-m1a2-data-source-advanced/**` | current image를 바꾸지 않고 fresh before/after, alias와 direct crops의 exact provenance만 등록한다. |

`modeling-data-intake.tsx`와 그 DOM, 다른 stage CSS, shared primitives/tokens, user-guide current PNG는 변경하지
않는다. Data 213개 잔여행, diagnostics, Library, mapping, responsive rule, M1B 이후 batch, dead/HOLD 후보를
이 단위로 끌어오지 않는다.

### Selector, consumer와 cascade

| Historical row | Selector | Specificity | owner/consumer와 cascade disposition |
| --- | --- | --- | --- |
| `CSS-1060` | `.data-source-advanced` | `0-1-0` | `modeling-data-intake.tsx`가 `/modeling?stage=data`와 `/datasets/processing?stage=data`의 inspected Local file state에서 유일하게 만든다. collapsed state의 `0-4-0` rule이 `padding`을 이기는 현재 관계를 보존한다. |
| `CSS-1068` | `.data-source-advanced > div` | `0-1-1` | open File details의 evidence grid다. 기존 뒤쪽 `.data-source-advanced > :is(summary, div)`가 같은 specificity/source order로 `font-size: var(--ux-metadata-font-size)`를 이겼으므로, 이동 시 obsolete `11.5px` member는 복제하지 않고 그 token rule을 계속 effective owner로 둔다. closed state의 `0-4-1` `display:none`도 그대로 우선한다. |
| `CSS-1069` | `.data-source-advanced code` | `0-1-1` | exact raw-evidence code wrapping/color만 Data owner로 이동한다. exact-selector peer, duplicate-owned peer 또는 later conflicting property가 없다. |

세 행 모두 production subject producer와 focused component test reference가 있고, dead, cross-CSS duplicate,
route-shell coupling, route-specific wide workaround 후보가 아니다. 이동 후 exact legacy residual은 0이다.

| Metric | M1A1 | M1A2 | Delta |
| --- | ---: | ---: | ---: |
| global rule-groups / guard debt | 2,821 | 2,818 | -3 |
| expanded global selector rows | 3,568 | 3,565 | -3 |
| M1A Data rows | 216 | 213 | -3 |
| cross-CSS duplicate rows | 13 | 13 | 0 |

### Live visual evidence

[M1A2 manifest](images/issue-261-fe06-m1a2-data-source-advanced/manifest.json)은 browser zoom 100%, DPR 1,
Standard density에서 primary `/modeling?stage=data&family=metal`과 alias
`/datasets/processing?stage=data&family=metal`을 각각 clean M1A1 before/current M1A2 after로 실행한다.
다섯 normal viewport와 empty, invalid mapping, locally-scrolled recovery의 primary 8쌍, alias 8쌍 및
primary↔alias가 모두 byte-for-byte 동일하다. current guide의 같은 8개 Data image도 before/after와 동일해
새 PNG를 current라고 가장하지 않는다. crop은 아래 original의 exact source pixels를 resize/resampling 없이
header, navigator, table/form controls와 graph 영역으로 잘랐다.

<details>

<summary>M1A2 exact originals and direct 100%-pixel crops</summary>

- 1366x768 normal: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-1366x768.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-1366x768.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-1366x768.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-1366x768.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1366x768-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1366x768-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1366x768-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1366x768-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1366x768-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1366x768-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1366x768-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1366x768-graph-100pct.png)
- 1440x900 normal: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-1440x900.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-1440x900.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-1440x900.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-1440x900.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1440x900-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1440x900-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1440x900-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1440x900-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1440x900-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1440x900-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1440x900-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1440x900-graph-100pct.png)
- 1920x1080 normal: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-1920x1080.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-1920x1080.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-1920x1080.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-1920x1080.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1920x1080-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1920x1080-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1920x1080-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-1920x1080-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1920x1080-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1920x1080-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1920x1080-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-1920x1080-graph-100pct.png)
- 2560x1440 normal: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-2560x1440.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-2560x1440.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-2560x1440.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-2560x1440.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-2560x1440-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-2560x1440-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-2560x1440-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-2560x1440-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-2560x1440-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-2560x1440-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-2560x1440-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-2560x1440-graph-100pct.png)
- 3840x2160 normal: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-3840x2160.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-3840x2160.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-3840x2160.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-3840x2160.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-3840x2160-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-3840x2160-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-3840x2160-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-3840x2160-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-3840x2160-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-3840x2160-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-3840x2160-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-3840x2160-graph-100pct.png)
- 1440x900 empty: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-empty-1440x900.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-empty-1440x900.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-empty-1440x900.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-empty-1440x900.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-empty-1440x900-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-empty-1440x900-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-empty-1440x900-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-empty-1440x900-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-empty-1440x900-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-empty-1440x900-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-empty-1440x900-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-empty-1440x900-graph-100pct.png)
- 1440x900 invalid mapping: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-invalid-1440x900.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-invalid-1440x900.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-invalid-1440x900.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-invalid-1440x900.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-1440x900-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-1440x900-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-1440x900-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-1440x900-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-1440x900-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-1440x900-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-1440x900-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-1440x900-graph-100pct.png)
- 1440x900 invalid mapping scrolled: [before original](images/issue-261-fe06-m1a2-data-source-advanced/before/originals/modeling-data-invalid-scrolled-1440x900.png), [after original](images/issue-261-fe06-m1a2-data-source-advanced/after/originals/modeling-data-invalid-scrolled-1440x900.png), [alias before](images/issue-261-fe06-m1a2-data-source-advanced/before/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png), [alias after](images/issue-261-fe06-m1a2-data-source-advanced/after/routes/datasets-processing/modeling-data-invalid-scrolled-1440x900.png), [before header](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png), [before navigator](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png), [before controls](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png), [before graph](images/issue-261-fe06-m1a2-data-source-advanced/before/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png), [after header](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-scrolled-1440x900-header-100pct.png), [after navigator](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-scrolled-1440x900-navigator-100pct.png), [after controls](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-scrolled-1440x900-controls-100pct.png), [after graph](images/issue-261-fe06-m1a2-data-source-advanced/after/crops/modeling-data-invalid-scrolled-1440x900-graph-100pct.png)

</details>

original-resolution inspection은 아래 acceptance에서 별도 기록한다. automated 3840x2160 geometry는 실제
Windows 4K 물리 가독성이라고 주장하지 않으며 그 최종 판정은 `DEFERRED_TO_223`이다.

### M1A2 Main acceptance

- Inventory contract 4/4와 checker가 PASS했다. 결과는 2,818 global rule-group, 3,565 expanded selector,
  M1A 213행, M1A2 touched/fully removed/partially shrunk `3/3/0`, exact legacy residual 0이다.
- Data intake/workspace, Modeling layout, common workbench focused Vitest는 4 files/56 tests PASS다. 첫
  `npm --prefix ... exec` 호출은 repository root에서 `apps/web` jsdom 설정을 읽지 못해
  `document is not defined`로 끝난 잘못된 runner invocation이었고, 같은 네 파일을 canonical
  `apps/web` cwd에서 실행한 결과가 위 56/56이다.
- Frontend guard contract 17/17, actual guard 0 violation/기존 warning 15가 PASS했다. 세 rule 제거로
  `layout.css`가 8,922줄, global debt가 2,818로 감소했고, M1A2 위쪽 삭제로 줄만 이동한 기존
  `.modeling-data-ribbon-panel` exception fingerprint를 같은 finding에 맞췄다. allowance나 count는
  늘리지 않았다.
- TypeScript/Vite production build와 bundle budget가 PASS했다. emitted base CSS는 343.24 kB,
  Data lazy CSS는 22.97 kB, common workbench CSS는 9.72 kB로 feature lazy boundary를 유지한다.
- Documentation-impact worktree gate는 301 changed files, 2 visual sources,
  `2 byte-identical CSS visual sources by #261`로 PASS했다. user-guide gate도 20문서, 119 current
  captures, 1,034 local links, 2,542 images를 PASS했다. current PNG는 바꾸지 않았으며 crop duplicate
  provenance는 실제 SHA-256별 complete exact-path group으로 등록했다.
- Manifest 재계산은 96 PNG 전부가 manifest에 닫혀 있고, primary original/crop 80개, primary 8쌍,
  alias 8쌍, current-guide triple 8개, direct pixel-exact crop 64개와 current CSS hash 2개가 모두
  일치함을 확인했다. `git diff --check`도 PASS다.
- Main은 after의 normal 다섯 viewport, empty/invalid/invalid-scrolled 세 상태와 header/navigator/
  controls/graph crop 32개를 original resolution으로 열었다. before는 모든 대응 pair가 byte-identical이다.
  #249 정보 계층, engineering task flow, responsive/wide-screen composition은 모두 PASS다. shell,
  selected stage, Local file recovery, mapping blocker, last-valid graph, collapsed File details와 action
  reachability에 clipping/wrapping/overflow/geometry 변화가 없다. 실제 Windows 4K 물리 가독성만 #223에
  남는다.
- 같은 `independent_auditor_terra_high`가 exact 세 selector 이동과 cascade, sole current-hash proof,
  historical manifest 조건, 96 PNG closure를 읽기 전용으로 재검사하고, after original 8개와 direct crop
  32개를 original resolution으로 열었다. #249 세 축과 모든 gate를 재확인한 결과 material finding 없이
  `APPROVE`했다.

## M1A3 실행 결과 — Data import diagnostics ownership

M1A3는 published M1A2가 포함된 `b2feb08eb40def0f8a627c34656daa393432695c`을 implementation base로
사용한다. React, DOM, copy, API, import state, route, token 또는 breakpoint를 바꾸지 않고 실제 rejected DMA
import에서 보이는 `.data-import-diagnostics` region의 재생성 inventory `CSS-1060`부터 `CSS-1066`까지만
기존 Data stage stylesheet로 이동했다.

### 파일 소유권과 금지 확장

| Path | M1A3 ownership |
| --- | --- |
| `apps/web/src/design/layout.css` | 아래 7개 exact selector를 구성하는 6개 legacy rule-group만 제거한다. 다른 Data, shared 또는 HOLD selector는 건드리지 않는다. |
| `apps/web/src/features/modeling/ui/stages/data/modeling-data-stage.css` | 같은 declaration block을 existing lazy Data owner에 선언 순서 그대로 둔다. |
| `apps/web/frontend-guard-baseline.json` | 실제 global rule-group과 `layout.css` line 감소만 잠근다. allowance나 warning budget은 늘리지 않는다. |
| `scripts/check_issue_261_css_inventory.mjs`, `scripts/check_issue_261_css_inventory.test.mjs`, `docs/17-evidence/issue-261-css-selector-inventory.json` | M1A3 `7/6/6/0`, zero residual과 다음 M1A4 owner-packet 경계를 고정한다. |
| `docs/user-guide/screenshot-manifest.yaml`, 이 evidence 문서, `docs/17-evidence/images/issue-261-fe06-m1a3-data-import-diagnostics/**` | current image를 바꾸지 않고 fresh before/after, alias, direct crop, computed-style provenance만 등록한다. |

`modeling-data-intake.tsx`와 그 DOM, 다른 stage CSS, shared primitives/tokens, user-guide current PNG는 변경하지
않는다. `.data-mapping-blockers`와 나머지 M1A 206행, Library/mapping/responsive rule, M1B 이후 batch,
dead/HOLD 후보도 이 단위에 포함하지 않는다.

### Selector, consumer와 cascade

| Historical row | Selector | Specificity | owner/consumer와 cascade disposition |
| --- | --- | --- | --- |
| `CSS-1060` | `.data-import-diagnostics` | `0-1-0` | `modeling-data-intake.tsx`의 rejected import `WorkbenchMessage`가 두 route alias에서 유일하게 만든다. grid, full-column span, spacing, danger rail과 background를 그대로 이동한다. |
| `CSS-1061` | `.data-import-diagnostics header` | `0-1-1` | historical region member다. 현재 `WorkbenchMessage` DOM에는 matching `header`가 없으므로 effective declaration은 없지만, 승인 packet의 exact member로 보존 이동한다. |
| `CSS-1062` | `.data-import-diagnostics header strong` | `0-1-2` | 위 historical header child와 같은 보존 이동이다. 현재 live DOM에는 match가 없으며 이 unit에서 dead 판정을 내리거나 삭제하지 않는다. |
| `CSS-1063` | `.data-import-diagnostics > div` | `0-1-1` | diagnostics table viewport의 horizontal overflow recovery를 보존한다. |
| `CSS-1064` | `.data-import-diagnostics table` | `0-1-1` | five-column rejected-row table의 width, collapse와 compact typography를 보존한다. |
| `CSS-1065` | `.data-import-diagnostics th` | `0-1-1` | header-cell alignment, weight, border와 padding을 다음 comma member와 같은 rule-group에서 보존한다. |
| `CSS-1066` | `.data-import-diagnostics td` | `0-1-1` | rejected row의 wrapping, vertical alignment, border와 padding을 보존한다. |

일곱 행에는 cross-CSS exact duplicate나 route-specific wide-screen workaround가 없다. import order상 owner가
global layout보다 늦게 로드되지만 competing exact selector/property가 없고, 두 alias와 다섯 viewport의
computed values와 geometry가 before/after에서 모두 동일하다. 현재 unmatched인 두 header member는 M6의
live zero-consumer 판정 전까지 dead로 간주하지 않는다. 이동 후 exact legacy residual은 0이다.

| Metric | M1A2 | M1A3 | Delta |
| --- | ---: | ---: | ---: |
| global rule-groups / guard debt | 2,818 | 2,812 | -6 |
| expanded global selector rows | 3,565 | 3,558 | -7 |
| M1A Data rows | 213 | 206 | -7 |
| cross-CSS duplicate rows | 13 | 13 | 0 |

### Live visual evidence

[M1A3 manifest](images/issue-261-fe06-m1a3-data-import-diagnostics/manifest.json)은 browser zoom 100%, DPR 1,
Standard density에서 primary `/modeling?stage=data`와 alias `/datasets/processing?stage=data`를 각각 다섯
final-size fresh browser context로 시작했다. 각 context는 고유한 natural idempotency key로 실제 DMA import를
한 번 거절시키고, 동일한 five-row diagnostics와 recovery를 캡처했다. before 10개와 after 10개의 key는 모두
서로 다르다. established page를 resize하거나 rejected key를 재사용하지 않았다.

두 route의 target original 10쌍, primary의 header/controls/diagnostics/graph direct crop 20쌍이 모두
byte-for-byte 동일하다. diagnostics의 computed color, border, layout, overflow, table/cell values와 geometry
10쌍도 동일하고 stylesheet source만 `modeling-data-stage.css`로 바뀌었다. unsaved rejected state에는
navigator rail이 DOM에 없으므로 navigator crop은 `N/A`; 대신 실제 target인 diagnostics를 direct 100%-pixel
crop으로 등록했다. documentation-impact용 normal current match는 기존 current guide image의 exact bytes를
before/after에 보존하며 current PNG 자체는 변경하지 않는다.

<details>

<summary>M1A3 exact originals and direct 100%-pixel crops</summary>

- 1366x768: [normal before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-1366x768.png), [normal after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-1366x768.png), [rejected before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-import-rejected-1366x768.png), [rejected after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-import-rejected-1366x768.png), [alias before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/routes/datasets-processing/modeling-data-import-rejected-1366x768.png), [alias after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/routes/datasets-processing/modeling-data-import-rejected-1366x768.png), [header before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1366x768-header-100pct.png), [header after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1366x768-header-100pct.png), [controls before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1366x768-controls-100pct.png), [controls after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1366x768-controls-100pct.png), [diagnostics before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1366x768-diagnostics-100pct.png), [diagnostics after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1366x768-diagnostics-100pct.png), [graph before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1366x768-graph-100pct.png), [graph after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1366x768-graph-100pct.png)
- 1440x900: [normal before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-1440x900.png), [normal after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-1440x900.png), [rejected before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-import-rejected-1440x900.png), [rejected after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-import-rejected-1440x900.png), [alias before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/routes/datasets-processing/modeling-data-import-rejected-1440x900.png), [alias after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/routes/datasets-processing/modeling-data-import-rejected-1440x900.png), [header before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1440x900-header-100pct.png), [header after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1440x900-header-100pct.png), [controls before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1440x900-controls-100pct.png), [controls after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1440x900-controls-100pct.png), [diagnostics before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1440x900-diagnostics-100pct.png), [diagnostics after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1440x900-diagnostics-100pct.png), [graph before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1440x900-graph-100pct.png), [graph after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1440x900-graph-100pct.png)
- 1920x1080: [normal before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-1920x1080.png), [normal after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-1920x1080.png), [rejected before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-import-rejected-1920x1080.png), [rejected after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-import-rejected-1920x1080.png), [alias before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/routes/datasets-processing/modeling-data-import-rejected-1920x1080.png), [alias after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/routes/datasets-processing/modeling-data-import-rejected-1920x1080.png), [header before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1920x1080-header-100pct.png), [header after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1920x1080-header-100pct.png), [controls before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1920x1080-controls-100pct.png), [controls after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1920x1080-controls-100pct.png), [diagnostics before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1920x1080-diagnostics-100pct.png), [diagnostics after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1920x1080-diagnostics-100pct.png), [graph before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-1920x1080-graph-100pct.png), [graph after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-1920x1080-graph-100pct.png)
- 2560x1440: [normal before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-2560x1440.png), [normal after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-2560x1440.png), [rejected before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-import-rejected-2560x1440.png), [rejected after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-import-rejected-2560x1440.png), [alias before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/routes/datasets-processing/modeling-data-import-rejected-2560x1440.png), [alias after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/routes/datasets-processing/modeling-data-import-rejected-2560x1440.png), [header before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-2560x1440-header-100pct.png), [header after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-2560x1440-header-100pct.png), [controls before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-2560x1440-controls-100pct.png), [controls after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-2560x1440-controls-100pct.png), [diagnostics before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-2560x1440-diagnostics-100pct.png), [diagnostics after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-2560x1440-diagnostics-100pct.png), [graph before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-2560x1440-graph-100pct.png), [graph after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-2560x1440-graph-100pct.png)
- 3840x2160: [normal before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-3840x2160.png), [normal after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-3840x2160.png), [rejected before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/originals/modeling-data-import-rejected-3840x2160.png), [rejected after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/originals/modeling-data-import-rejected-3840x2160.png), [alias before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/routes/datasets-processing/modeling-data-import-rejected-3840x2160.png), [alias after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/routes/datasets-processing/modeling-data-import-rejected-3840x2160.png), [header before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-3840x2160-header-100pct.png), [header after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-3840x2160-header-100pct.png), [controls before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-3840x2160-controls-100pct.png), [controls after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-3840x2160-controls-100pct.png), [diagnostics before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-3840x2160-diagnostics-100pct.png), [diagnostics after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-3840x2160-diagnostics-100pct.png), [graph before](images/issue-261-fe06-m1a3-data-import-diagnostics/before/crops/modeling-data-import-rejected-3840x2160-graph-100pct.png), [graph after](images/issue-261-fe06-m1a3-data-import-diagnostics/after/crops/modeling-data-import-rejected-3840x2160-graph-100pct.png)

</details>

original-resolution inspection은 아래 Main acceptance에서 별도 기록한다. automated 3840x2160 geometry는 실제
Windows 4K 물리 가독성이라고 주장하지 않으며 그 최종 판정은 `DEFERRED_TO_223`이다.

### M1A3 Main acceptance

- Inventory contract 7/7와 checker가 PASS했다. 결과는 2,812 global rule-group, 3,558 expanded selector,
  M1A 206행, M1A3 touched/fully removed/partially shrunk `6/6/0`, exact legacy residual 0이다.
- Data intake/workspace, Modeling workspace layout, common workbench focused Vitest는 4 files/56 tests PASS다.
  Node `24.19.0`, npm `11.17.0` pinned runtime에서 실행했다.
- Frontend guard contract 17/17, actual guard 0 violation/기존 warning 15가 PASS했다. 6개 rule 제거로
  `layout.css`가 8,882줄, global debt가 2,812로 감소했다. 삭제 아래쪽의 기존 ribbon exception은 같은
  selector의 이동된 line fingerprint에 맞췄고, preserved `#fce8e8` fallback은 Data owner의 exact one-occurrence
  exception으로 옮겼다. raw-color count는 기존 954를 넘지 않는다.
- TypeScript/Vite production build와 bundle budget가 PASS했다. emitted base CSS는 342.59 kB,
  Data lazy CSS는 23.62 kB, common workbench CSS는 9.72 kB로 feature lazy boundary를 유지한다.
- Documentation-impact worktree gate는 82 changed files, 2 visual sources,
  `2 byte-identical CSS visual sources by #261`로 PASS했다. user-guide gate도 20문서, 119 current captures,
  1,105 local links, 2,612 images를 PASS했다. current PNG는 바꾸지 않았다.
- Manifest 재계산은 70 PNG 전부가 manifest와 guide inventory에 닫혀 있고, supporting current pair 5개,
  target original pair 10개, direct crop pair 20개, computed-style/geometry pair 10개와 current CSS hash 2개가
  모두 일치함을 확인했다. before/after 20개 rejected-import idempotency key도 모두 고유하다.
  `git diff --check`도 PASS다.
- Main은 두 alias의 after original 10개와 primary header/controls/diagnostics/graph crop 20개를 original
  resolution으로 열었다. before는 모든 대응 pair가 byte-identical이다. #249 정보 계층, engineering task
  flow, responsive/wide-screen composition은 모두 PASS다. diagnostics five-row recovery, import action과 graph
  reachability에 clipping/wrapping/overflow/geometry 변화가 없다. 실제 Windows 4K 물리 가독성만 #223에 남는다.

## 이후 migration 순서

1. M1A0 Data same-selector 12행은 commit `e9cad946...`에서 이동·검증되었다.
2. M1A1 Data source-tabs 5행은 commit `8361e85d...`에서 이동·검증되었다.
3. M1A2 Data source-advanced 3행은 published M1A2에서 이동·검증되었다.
4. M1A3 Data import diagnostics 7행은 위 candidate에서 이동·검증되었다.
5. 다음 단위 `M1A4-modeling-data-component-region`은 재생성 inventory의 남은 M1A 206행에서 한 component
   region만 새 owner packet으로 선택한다. owner 승인을 받기 전에는 전체 206행을 함께 이동하지 않는다.
6. M1B Process, M1C Fit, M1D Export, M1E Modeling shell/family를 각각 분리한다.
7. M2 Materials를 search/tree/detail/card state와 함께 옮긴다.
8. M3A Administration과 M3B Activity를 서로 다른 owner file로 옮긴다.
9. feature가 빠진 뒤 M4 shared shell/token/primitive/layout을 정리한다.
10. 마지막 M6에서만 live zero-consumer를 증명한 dead selector를 제거한다.
11. HOLD 447행은 consumer가 둘 이상이거나 owner가 불명확하므로 owner split 전에는 이동하거나
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

## 초기 inventory 단위 검증 기록

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
