# 코드 유지·분해·교체·삭제 계획

## 1. 범위와 원칙

이 문서는 latest main을 감사해 다음 Codex가 코드 정리를 안전하게 실행하도록 만든 계획이다. 이 패키지 자체는 코드 변경을 포함하지 않는다.

### 반드시 보존

- 실제 API와 backend domain contract
- 계산·fitting·unit normalization
- raw source immutability
- provenance와 revision
- Processing Output
- solver-neutral Material Model IR
- Neutral model
- plugin/exporter mapping
- `exact | transformed | approximated | unsupported` 의미
- deep link와 필요한 compatibility redirect
- deterministic hooks와 기존 유효 테스트

### 삭제 판단

코드가 낡아 보인다는 이유로 삭제하지 않는다. 다음이 모두 성립해야 삭제한다.

1. 기능이 canonical route/component로 이동했다.
2. import·route·test·CSS selector를 `rg`로 조사했다.
3. user-visible deep link는 redirect 또는 명확한 대체 경로가 있다.
4. backend/API/domain 계산에 영향을 주지 않는다.
5. unit/integration/E2E와 current viewport visual evidence가 통과한다.
6. 삭제한 이름을 current docs와 screenshot manifest에서도 제거했다.

## 2. 최신 main에서 확인된 치명적 상태 결함

### 2.1 추천을 실제 선택처럼 저장

현재 metal default recipe에는 `primary_family: swift`, `secondary_family: voce`, `primary_weight: 0.5`가 미리 들어가고 polymer에는 기본 `selected_term_count`와 selection reason까지 들어갈 수 있다. 사용자는 후보 row를 명시적으로 고르지 않고 reason만 채워 `Commit reviewed fit`으로 진행할 수 있다.

수정:

- default selected candidate는 `null`
- recommendation과 selection을 별도 state/event로 분리
- row의 `Select candidate` event가 없으면 save/submit 불가
- warning acknowledgement를 reason과 별도 field로 둠
- 테스트도 candidate click 없이 commit하는 흐름을 제거

### 2.2 Metal blend identity 손실

계산은 primary+secondary+weight의 blend를 쓰지만 output/ribbon은 primary law 하나처럼 말할 수 있다.

수정:

- `single | blend`를 명시적 mode로 분리
- blend identity에 두 law, ratio, parameters, fit range를 저장
- graph/table/Processing Output/IR/Neutral/Export label을 같은 identity adapter에서 생성

### 2.3 Polymer automatic selection identity 불일치

candidate table은 server scalar `prony_selected_term_count`를 우선할 수 있지만 commit/export는 recipe default term을 사용할 수 있다.

수정:

- server result의 actual selected term과 metrics를 canonical output identity로 사용
- requested selection policy와 result selection을 별도 field로 저장
- table, saved candidate, export가 같은 result ID를 참조

### 2.4 Downstream clear 불가능

session save가 nullish merge라 material/family/Test Data 변경 뒤 previous recipe·output·IR·Neutral pointer를 명시적으로 지우기 어렵다.

수정:

- reducer event 또는 explicit `set/clear` patch contract로 교체
- invalidation matrix를 reducer test로 고정
- history object는 보존하고 current pointer만 clear/stale

### 2.5 Export global fallback

current exact output이 없을 때 전역 Processing Output 또는 첫 existing model을 fallback으로 보일 수 있다. 이 때문에 “현재 fit을 먼저 저장”하라는 안내와 기존 Neutral delivery가 한 화면에 동시에 존재할 수 있다.

수정:

- normal Export는 current session exact output만 허용
- material/state/Test Data/recipe/candidate revision 완전 일치 검사
- 없으면 artifact UI를 렌더하지 않고 prerequisite checklist만 표시
- 기존 released model 재사용은 Materials의 별도 explicit 경로

### 2.6 Validate 단계 부재

현재 stage는 `Data | Process | Fit | Export`이며 fit metric/derivative가 validation처럼 오해될 수 있다.

수정:

- stage model에 Validate와 Review/Release 추가
- backend support가 없는 validation type은 `Not supported`로 명시
- Fit completed badge를 Validated로 바꾸지 않음

### 2.7 Materials query 정확성

최대 50개를 받아 source/solver/status/yield를 client-side로 좁히고 server `total_count`와 섞을 수 있으며 row별 detail+graph+card N+1 호출이 있다.

수정:

- scope/query/facet/sort/page를 server-side query contract로 통합
- results row projection endpoint 또는 batch projection
- facet count와 total을 같은 query에서 계산
- condition-aware property projection
- server 지원 전에는 해당 facet을 숨기고 “전체 catalog filter”처럼 표시하지 않음

## 3. 파일별 처리 지시

| 경로 | 판정 | 필요한 변경 | 삭제 조건 |
|---|---|---|---|
| `apps/web/src/design/application-shell.tsx` | 유지·대폭 개편 | 상태형 `Data→Process→Fit→Validate→Review/Release→Export`, Compare wiring, permission-aware actions | 삭제 금지 |
| `apps/web/src/material-library.tsx` | 분해 필수 | server query projection, family/layout facets, result table, compare, inspector, detail/activity 책임 분리 | 새 component call site와 tests 전환 후 mega implementation 제거 |
| `apps/web/src/materials-browse-tree.tsx` | 유지·개편 | single-option selector 제거, human scope, keyboard tree, loading/error/retry | 삭제 금지 |
| `apps/web/src/material-modeling-workspace.tsx` | 대폭 개편 | session setup, family/objective pin, safe context change, downstream invalidation, exact datasheet route | 기존 silent family switch branch는 reducer 전환 후 삭제 |
| `apps/web/src/common-processing-workbench.tsx` | 반드시 분해 | shared shell과 Data/Process/Fit/Validate/Review/Export controller 분리; 중복 statistics/output UI 제거 | 모든 family route/test 전환 후 단계별 dead branch 제거 |
| `apps/web/src/modeling-data-intake.tsx` | 유지·개편 | raw table/curve, mapping decision table, provenance group, 상태별 primary action | 삭제 금지 |
| `apps/web/src/modeling-fit-decision.tsx` | 유지·전면 개편 | explicit selection, recommendation 분리, stability/compatibility/range/extrapolation columns, blend identity | 삭제 금지 |
| `apps/web/src/engineering-curve-plot.tsx` | 유지·개편 | human quantity label, measured/fit/extrapolated encoding, persistent view state | 삭제 금지 |
| `apps/web/src/design/modeling-workspace-layout.tsx` | 개념 유지·구조 개편 | source navigator + central evidence/table + contextual inspector; stage별 responsive topology | 150px ribbon hack은 대체 후 삭제 |
| `apps/web/src/modeling-session-context.ts` | v3 state model로 교체 | explicit invalidation event/reducer, nullable clear, exact revision pointers, resume state | 기존 `??` merge는 reducer tests 통과 후 삭제 |
| `apps/web/src/reference-elastoplastic-workbench.tsx` | normal path 축소·adapter 유지 | current exact output만, yield 재입력 제거, output→IR 역할만 남김 | global fallback·legacy dataset-to-IR form은 route/ref/test 0 후 삭제 또는 dev/reference 격리 |
| `apps/web/src/reference-linear-viscoelastic-workbench.tsx` | normal path 축소·adapter 유지 | server actual term identity, pinned output only | global fallback·manual normal-path editor는 별도 expert/reference route 전환 후 삭제 |
| `apps/web/src/reference-ogden-prony-workbench.tsx` | normal Modeling에서 제거 후보 | multi-mode test→candidate→validation→release 흐름으로 대체; synthetic defaults는 dev/reference 격리 | production route가 새 flow로 전환되고 test fixture 용도가 분리된 뒤 |
| `apps/web/src/neutral-hyperelastic-export.tsx` | 유지·이름/책임 교정 | 여러 family 공통이면 `neutral-solver-export.tsx` 또는 `solver-card-delivery.tsx`; prerequisite/preflight/delivery 공통 계약 | 기존 export 이름 import 0 후 rename 정리 |
| `apps/web/src/app.tsx` | 유지·legacy route 정리 | canonical Materials/Modeling/Activity로 redirect, lazy import 정리 | deep-link regression 후 ModuleHub JSX 삭제 |
| `apps/web/src/design/layout.css` | 대대적 정리 | semantic token·primitive 유지; 누적 override, ribbon scroll, dead selector 제거 | component migration과 selector usage 0 후 |
| `apps/web/src/styles.css` | legacy 정리 | admin 스타일 중복 제거, canonical component style로 이동 | route/component usage 0 후 |

## 4. 목표 component 경계

정확한 파일명은 현재 convention에 맞춰 조정할 수 있지만 책임은 다음처럼 분리한다.

### 4.1 Materials

```text
material-library.tsx              # route/orchestration only
materials/
  materials-find-page.tsx
  material-search-scope.tsx
  material-query-bar.tsx
  material-facet-panel.tsx
  material-results-grid.tsx
  material-compare-tray.tsx
  selected-material-inspector.tsx
  material-detail-page.tsx
  material-property-layout.tsx
  material-curves-panel.tsx
  material-cae-cards-table.tsx
  material-relations-panel.tsx
  material-query-state.ts
  material-display-adapters.ts
```

원칙:

- query state와 display adapter를 UI component 밖에서 공유한다.
- same material condition projection을 results/inspector/detail이 재사용한다.
- row별 N+1 fetch를 component 안에서 숨기지 않는다.
- 현재 export·route compatibility를 유지하는 thin wrapper는 잠시 허용한다.

### 4.2 Modeling

```text
modeling/
  modeling-session-shell.tsx
  modeling-stage-stepper.tsx
  modeling-session-context-v3.ts
  modeling-invalidation-reducer.ts
  curve-specimen-rail.tsx
  persistent-evidence-plot.tsx
  data/
    data-stage.tsx
    source-inspector.tsx
    mapping-table.tsx
    provenance-editor.tsx
  process/
    process-stage.tsx
    operation-pipeline.tsx
    operation-inspector.tsx
    elastic-plastic-separation.tsx
    replicate-analysis.tsx
  fit/
    fit-stage.tsx
    candidate-table.tsx
    candidate-inspector.tsx
    fit-range-editor.tsx
    model-identity.ts
  validate/
    validate-stage.tsx
    validation-plan.tsx
    validation-results.tsx
  review/
    review-stage.tsx
    review-package.tsx
  export/
    export-stage.tsx
    prerequisite-checklist.tsx
    delivery-lineage.tsx
    mapping-preflight.tsx
    native-card-preview.tsx
```

원칙:

- `common-processing-workbench.tsx`가 모든 domain과 stage를 한 파일에서 소유하지 않는다.
- family별 계산 adapter는 유지하되 공통 state 명칭을 공유한다.
- 그래프 view state는 stage UI remount와 분리한다.
- normal flow와 expert/reference harness를 분리한다.

## 5. Materials 코드 결정

### 5.1 Fixed filter rail 제거 순서

현재 hardcoded control을 즉시 다른 static list로 바꾸지 않는다.

1. server query/facet capability를 확인한다.
2. `MaterialFacetDefinition`을 family/layout/scope에 따라 반환하도록 한다.
3. categorical count와 numeric quantity/unit semantics를 정의한다.
4. result total/page와 facet aggregate가 같은 query를 쓰게 한다.
5. 새 panel을 feature-flag 또는 bounded route에서 검증한다.
6. 기존 `Material class`, `Manufacturer/source`, `CAE card`, `Validation/release`, `Yield strength min/max` stack을 제거한다.

### 5.2 Provider/source 분리

- `Provider`: material record를 제공하는 organization/source collection
- `Evidence source`: property/curve가 measured, supplier, derived, fitted, generic, AI-estimated 중 무엇인지
- manufacturer가 domain에 별도 entity면 provider와도 분리
- 임의로 density/modulus/yield 중 하나의 reference를 대표 source로 쓰지 않는다.

### 5.3 Results projection

필요한 최소 projection:

```text
material identity
family
form/condition
provider
release/current/version
layout-specific quantities with condition/source
curve/model/card availability summaries
solver compatibility summaries
```

detail, graph, card를 row마다 따로 fetch하지 않는다. 정확한 endpoint shape는 기존 API convention을 따르고 OpenAPI/schema/test를 함께 갱신한다.

### 5.4 Start Modeling

- supported family registry로 route 가능 여부를 판정한다.
- exact material revision과 state를 session setup에 전달한다.
- objective를 고르지 않은 채 Fit으로 가지 않는다.
- unsupported family는 `Unsupported workflow`와 이유를 표시한다.

## 6. Modeling 코드 결정

### 6.1 Session reducer event

최소 event:

```text
CREATE_SESSION
CHANGE_SETUP
PIN_TEST_DATA
SAVE_PROCESSED_DATASET
RUN_FIT_COMPLETED
SELECT_CANDIDATE
SAVE_CANDIDATE
RUN_VALIDATION_COMPLETED
SUBMIT_REVIEW
REVIEW_DECIDED
RELEASE_MODEL
CHANGE_EXPORT_TARGET
DELIVER_ARTIFACT
INVALIDATE_DOWNSTREAM
RESTORE_VIEW_STATE
```

event test는 04 문서의 invalidation matrix를 그대로 검증한다.

### 6.2 Fit selection state

현재 default recipe의 계산 기본값과 user decision을 분리한다.

```text
fit_configuration.recommended_starting_values
fit_run.candidates
fit_run.recommendation
engineer_decision.selected_candidate_id = null initially
engineer_decision.selection_reason
engineer_decision.warning_acknowledgements
```

`recommended_starting_values`가 있어도 candidate row는 Selected가 아니다.

### 6.3 Yield 중복 제거

`reference-elastoplastic-workbench.tsx`에서 IR promotion 시 `propertySet.yield_stress_pa`가 없다는 이유로 curve-derived yield를 다시 입력하게 하는 normal flow를 재검토한다.

우선순위:

1. Process의 reviewed/saved derived yield와 definition을 Processing Output에 포함
2. IR promotion은 해당 exact output을 source로 사용
3. catalog property set의 yield는 read-only consistency evidence
4. 불일치하면 hidden fallback이 아니라 explicit discrepancy/revision workflow

backend contract가 derived yield를 운반하지 못하면 그 gap을 먼저 명시하고 schema migration을 별도 PR로 한다. UI에 두 번째 bare yield input을 추가하지 않는다.

### 6.4 Export source pin

- Export component prop/API query에 session exact output ID를 필수로 전달
- source mismatch면 blocked
- current output이 없으면 fallback selector도 렌더하지 않음
- Materials에서 기존 released model을 export하는 경로는 별도 route contract

### 6.5 Validate 최소 수직 slice

실제 solver job까지 한 번에 지원하기 어렵다면 다음 순서로 구현한다.

1. stage와 status contract
2. saved candidate에 대한 mathematical/holdout validation
3. persistent validation record
4. Review prerequisite 연결
5. solver/physical validation은 supported target부터 확장

`Not supported`를 명시하는 것이 fake pass보다 낫다.

## 7. Legacy module·CSS 정리

### 7.1 route/component 후보

`apps/web/src/app.tsx`의 다음 legacy module hub는 DUI-07~09에서 기능 이동과 deep-link 검증 후 제거 후보로 둔다.

- `ModuleHubPage`
- `moduleHubContent`
- `ModuleArea`
- `/tests`
- `/datasets`
- `/models`
- `/governance`
- `/jobs-reviews`

route URL은 바로 삭제하지 않고 canonical Materials/Modeling/Activity context로 redirect한다.

### 7.2 selector 후보

새 component migration 후 usage 0을 확인한 뒤 제거:

- `.module-material-grid`
- `.module-material-card`
- `.page-heading.module-heading`
- `.page-stack`
- `.page-heading`
- `.content-card`
- `.hero-card`
- `.detail-hero`
- `.compact-hero`

Administration style가 `styles.css`와 `design/layout.css` 양쪽에 중복되면 canonical primitive로 옮기고 하나를 제거한다.

### 7.3 제거하지 않을 CSS

- semantic typography/spacing/status/source/mapping/curve token
- current Materials/Modeling/Activity canonical layout primitive
- accessibility focus/keyboard styles
- active route가 실제 사용하는 responsive rules

## 8. 코드 작업 순서

```text
Contract tests
→ session/query state model
→ component extraction without behavior change
→ targeted UX/state correction
→ route migration
→ visual/regression evidence
→ dead JSX/CSS deletion
→ docs and screenshot manifest
```

대규모 파일을 먼저 삭제한 뒤 다시 동작을 맞추지 않는다. 각 slice에서 이전과 새 경로의 ownership을 명시한다.

## 9. 필수 회귀 테스트

### Materials

- 10,000-material fixture에서 source/card/yield facets가 전체 server result에 적용된다.
- total, facet count, page rows가 같은 query를 사용한다.
- polymer/elastomer에서는 Yield facet이 보이지 않는다.
- metal Yield facet은 definition·condition·unit을 가진다.
- Provider와 Evidence source가 다른 데이터로 표시된다.
- family별 result column이 바뀌고 항상 Yield 열이 남지 않는다.
- compare tray가 filter 변경 후에도 독립적으로 유지된다.
- card target이 둘 이상이면 모호한 generic preview가 없다.

### Modeling state

- 새 session은 Data 또는 setup에서 시작한다.
- material/state/Test Data/family 변경 시 Output→IR→Neutral→preflight current pointer가 모두 clear/stale 된다.
- 다른 material의 Processing Output이 selector/API request에 등장하지 않는다.
- current exact output이 없으면 Export card UI는 렌더되지 않는다.

### Fit

- metal/polymer 모두 explicit row selection 전 save/submit 불가.
- recommendation 변경이 selection을 바꾸지 않는다.
- blend identity에 두 law와 ratio가 포함된다.
- polymer auto selection label이 server actual selected term과 일치한다.
- selection reason만 입력해 review 상태가 생기지 않는다.

### Workflow language

- 실제 audit event 없이 `Reviewed`, `Validated`, `Released`, `Delivered`가 렌더되지 않는다.
- Save, Select, Submit, Approve, Release, Preview, Deliver가 별도 command다.

### View state and accessibility

- Data→Process→Fit 이동 후 graph zoom·visibility·selected curve/candidate 복원.
- keyboard로 tree, result grid, candidate table, tabs, primary action을 사용할 수 있다.
- 1366×768에서 primary action, reason, warning acknowledgement가 숨은 ribbon scroll 안에만 있지 않다.
- 1440×900과 1920×1080에서도 page horizontal overflow가 없다.

## 10. PR별 안전 체크리스트

- [ ] 적용되는 `AGENTS.md` 확인
- [ ] dirty worktree와 사용자 변경 보존
- [ ] before behavior와 exact route 기록
- [ ] domain/API 변경 여부 명시
- [ ] new state event와 invalidation test
- [ ] normal path에서 internal vocabulary 제거
- [ ] keyboard/focus/empty/loading/error/stale 상태
- [ ] current viewport screenshot
- [ ] screenshot manifest와 source SHA 일치
- [ ] obsolete import/route/selector `rg` 확인
- [ ] current docs와 historical evidence 역할 구분
- [ ] #119를 이유로 자동 LLM reviewer 재활성화하지 않음

