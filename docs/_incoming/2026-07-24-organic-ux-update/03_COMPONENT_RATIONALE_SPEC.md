# 컴포넌트·필드 상세 명세

## 1. 명세 형식과 판정 규칙

열 수나 카드 모양은 결과일 뿐 요구사항이 아니다. 모든 visible component와 engineering field는 다음 계약을 가진다.

| 필드 | 의미 |
|---|---|
| `user_job` | 사용자가 이 요소로 끝내려는 판단 또는 행동 |
| `why` | 이 요소가 없을 때 생기는 업무상 손실 |
| `placement` | 다른 증거·설정·결정과의 관계 때문에 이 위치여야 하는 이유 |
| `visible_when` | family, workflow, stage, permission, data state에 따른 노출 조건 |
| `source` | 입력 데이터의 출처, revision, condition, unit |
| `requires` | 활성화되기 위한 선행조건 |
| `action_output` | 사용자가 바꾸거나 실행했을 때 생성되는 결과 |
| `states` | idle/loading/dirty/ready/warning/blocked/error/stale 등의 상태 |
| `validation` | 허용 값, 물리·데이터·권한 검증 |
| `invalidates` | 변경 시 stale 또는 폐기해야 하는 downstream artifact |
| `recovery` | 오류 뒤 보존할 문맥과 다음 행동 |
| `not_allowed` | 의미를 흐리거나 거짓 가용성을 만드는 패턴 |

다음 중 하나라도 답하지 못하는 요소는 구현을 보류하고 삭제 또는 비노출한다.

- 어떤 사용자 결정을 돕는가?
- 어떤 source와 condition을 쓰는가?
- 어떤 workflow에서만 유효한가?
- 변경 영향은 무엇인가?
- 미지원·오류를 어떻게 알리는가?

## 2. 전역 제품 shell

### G-01 Global navigation

- `user_job`: Materials, Modeling, Activity라는 서로 다른 업무 공간으로 이동한다.
- `why`: 검색·calibration·작업 재개를 섞지 않고 현재 업무 경계를 알게 한다.
- `placement`: application shell 최상단에 고정한다. 화면 내부 단계 nav보다 한 계층 위다.
- `visible_when`: 인증된 모든 일반 사용자. 역할별 admin은 별도 permission-aware entry로 노출한다.
- `action_output`: route가 바뀌되 현재 workspace의 query, selection, expanded tree, session stage, plot state를 보존한다.
- `states`: current, available, restricted. “준비 중” route는 primary nav에 넣지 않는다.
- `not_allowed`: `Tests | Datasets | Models | Governance | Jobs` 같은 내부 module hub를 같은 수준에 되살리는 것.

### G-02 Workspace identity header

- `user_job`: 지금 보고 있는 material 또는 modeling session의 identity와 상태를 확인한다.
- `why`: 같은 이름의 다른 form·condition·revision을 잘못 쓰는 것을 막는다.
- `placement`: global nav 아래, page title과 primary action이 있는 한 줄.
- `visible_when`: material detail 또는 modeling session.
- `source`: exact material revision/session revision.
- `content`: human name, form/condition, workflow objective, working/review/released state, version.
- `not_allowed`: UUID·hash·method ID를 title보다 크게 표시하거나 page title·pane title·subtitle에서 같은 문장을 반복.

### G-03 Primary action

- `user_job`: 현재 단계의 다음 완료 행동을 명확히 실행한다.
- `placement`: workspace header 오른쪽 또는 현재 task inspector의 footer 중 한 곳에만 둔다.
- `requires`: action별 prerequisite가 충족되어야 한다.
- `states`: enabled, calculating, blocked, failed, completed.
- `blocked behavior`: disabled 이유와 미충족 선행조건을 바로 옆에 표시한다.
- `not_allowed`: 화면당 동등한 primary button 여러 개, icon-only 중요 action, toast만 남기는 long-running action.

### G-04 Evidence/Advanced disclosure

- `user_job`: 정상 업무에서는 필요 없지만 감사·진단에 필요한 내부 근거를 확인한다.
- `content`: UUID, checksum, method/plugin key, raw JSON, API path, exact transformation log.
- `placement`: 관련 object의 local disclosure 또는 evidence tab.
- `visible_when`: 사용자가 명시적으로 열었을 때; 권한이 필요한 데이터는 restricted 처리.
- `not_allowed`: 정상 label이나 table의 기본 열로 노출.

## 3. Materials Explorer

### 3.1 정보 구조

```text
Materials
├─ Find
│  ├─ Scope + quick search
│  ├─ Browse tree / contextual facets
│  ├─ Results + compare tray
│  └─ Selected-material inspector
└─ Material detail
   ├─ Identity + state + version
   ├─ Overview / Properties / Curves / CAE Cards / Evidence
   └─ Relations + revision context
```

이 구조는 “3열이 예뻐서”가 아니다. 사용자가 분류·필터를 바꾸면서 후보를 스캔하고, 현재 한 후보의 핵심 근거를 route 이동 없이 확인해야 하기 때문이다. 좁은 viewport에서는 rail과 inspector를 drawer로 접어도 각 역할은 유지한다.

### M-01 Search scope

- `user_job`: 어떤 governed collection과 release 범위를 검색하는지 확인한다.
- `why`: 같은 query가 다른 subset·권한·version state에서 다른 결과를 내는 이유를 알게 한다.
- `placement`: quick search 바로 위 또는 같은 header의 작은 context label.
- `visible_when`: 항상. 선택 가능한 scope가 둘 이상일 때만 selector가 된다.
- `source`: server search profile/subset/permission context.
- `action_output`: scope 변경 시 query는 보존하고 facets·columns·results를 새 scope에 맞게 재계산한다.
- `states`: loading, active, unavailable, restricted.
- `recovery`: unavailable scope이면 기존 query를 보존하고 가능한 scope를 제시한다.
- `not_allowed`: option이 하나인 `Database`/`Profile` select, 내부 table name, 가짜 복수 선택.

### M-02 Quick search

- `user_job`: name, grade, code, standard처럼 이미 아는 재료를 빠르게 찾는다.
- `why`: 가장 빈번한 Find 경로다.
- `placement`: results 전체를 지배하므로 workspace 상단의 가장 강한 입력.
- `visible_when`: Find 화면.
- `source`: server-side material search index와 permitted subset.
- `action_output`: query token과 server result set. suggestion은 무엇을 검색하는지 `Grade`, `Standard`, `Property` 유형을 표시한다.
- `states`: idle, typing, searching, result, no match, partial/restricted, error.
- `validation`: property range suggestion은 unit과 operator를 가져야 한다.
- `recovery`: query, cursor, active scope와 facets를 보존하고 retry.
- `not_allowed`: 모든 route·command·internal ID를 뒤섞은 만능 command palette, 50개 client page만 검색한 결과.

### M-03 Browse tree

- `user_job`: 정확한 이름을 모를 때 material family와 governed collection을 계층적으로 탐색한다.
- `why`: 검색어를 모르는 사용자에게 organization taxonomy를 제공한다.
- `placement`: Find 왼쪽 rail의 위쪽. facets보다 먼저 scope를 정한다.
- `visible_when`: Browse mode 또는 Find에서 rail이 열린 경우.
- `source`: configurable tables/folders/records/subsets의 human view.
- `action_output`: active category/subset path와 result constraint.
- `states`: collapsed, expanded, selected, loading children, empty, error.
- `recovery`: expansion과 selected path를 보존한 retry.
- `not_allowed`: `DB/P/T/R` glyph만으로 type 표현, tree click으로 무관한 engineering input form 생성, 내부 schema를 product taxonomy처럼 표시.

### M-04 Contextual facet panel

- `user_job`: 현재 result set을 사용 목적과 조건에 맞게 좁힌다.
- `why`: 수백·수천 record에서 비교 가능한 후보군을 만든다.
- `placement`: Browse tree 아래 또는 같은 rail의 `Filters` tab. 결과와 가깝고 central scan을 침범하지 않는다.
- `visible_when`: server가 active scope/family/layout에 적용 가능한 facet definition을 반환할 때.
- `source`: server-side facet definition과 전체 matching catalog의 aggregate count.
- `action_output`: server query constraint, active chip, updated count와 results.
- `states`: available, selected, disabled with zero count, loading, unavailable, error.
- `validation`: categorical value는 명시적 code/label; numeric range는 quantity·unit·min/max·missing policy 필요.
- `invalidates`: current row selection이 새 result에 없으면 selection만 해제; compare tray는 독립 유지하되 out-of-scope 표시.
- `recovery`: 실패 시 이전 result와 filter 선택을 유지하고 “필터 재계산 실패”를 표시.
- `not_allowed`: client가 받아온 첫 50개에만 필터 적용, count 없는 고정 dropdown stack, family 무관 property의 상시 노출.

#### 기본 facet 정의

| facet | 노출 조건 | 이유 | 데이터 의미 | 금지 |
|---|---|---|---|---|
| Material family | 둘 이상의 family가 scope에 있을 때 | domain workflow와 property layout을 좁힘 | governed classification | class fallback으로 unknown을 metal 처리 |
| Provider | provider metadata가 있을 때 | 조직·supplier 출처로 좁힘 | material/provider relationship | measurement reference를 manufacturer로 표시 |
| Evidence source | source type filter가 유용할 때 | measured/derived/fitted/generic를 구분 | property/curve provenance | Provider와 한 field로 합침 |
| Release state | 권한 범위에 둘 이상 state가 있을 때 | 사용 가능한 version 판단 | Draft/In review/Released/Superseded/Withdrawn | validation과 한 dropdown으로 합침 |
| Validation availability | test/model/card validation 정보가 있을 때 | 검증 근거가 있는 후보를 찾음 | Not run/Partial/Passed/Warning/Failed/Unsupported | release state처럼 취급 |
| Solver compatibility | CAE 재사용 목적 view 또는 solver filter 선택 시 | target delivery 가능성 판단 | solver/version + exact/approx/unsupported + release | `Abaqus/OpenRadioss` hardcode |
| Form/condition | 같은 grade에 여러 form·condition이 있을 때 | 물성 적용 조건을 맞춤 | form, temper, thickness, direction, temperature 등 | record name과 condition을 분리한 채 숨김 |
| Property range | active family/layout가 해당 quantity를 정의할 때 | engineering constraint로 후보 축소 | condition-aware quantity projection | `property_sets[0]` 임의 사용 |

### M-05 Yield definition facet

현재 `Yield strength min/max`가 왜 필요한지와 어디에 있어야 하는지를 별도로 고정한다.

- `user_job`: metal tensile 후보를 특정 proof/yield stress 범위로 좁힌다.
- `why`: 강도 수준이 명확한 metal 선택 업무에서는 유용하지만 모든 material 탐색의 공통 조건은 아니다.
- `placement`: `Metal` 또는 tensile-property saved view의 contextual property facet group.
- `visible_when`:
  - active family가 metal elastoplastic이고
  - server layout가 yield/proof quantity와 condition semantics를 제공하며
  - 사용자가 property facets를 열었을 때.
- `source`: condition-aware property projection. 각 값은 yield definition, unit, temperature, direction, form/condition, source revision을 가진다.
- `input`: min, max, unit, yield definition. 필요하면 missing-value include toggle.
- `action_output`: 전체 catalog에 적용되는 server query.
- `states`: not applicable, available, selected, partial missing, restricted.
- `validation`: min ≤ max; unit convertible; 정의가 다른 `Rp0.2`, upper/lower yield 등을 조용히 혼합하지 않음.
- `recovery`: invalid range는 inline 설명; result와 다른 filters를 유지.
- `not_allowed`:
  - All classes, polymer, elastomer, composite, ceramic에서 상시 노출
  - 첫 Property Set의 값을 대표값으로 사용
  - condition·definition 없이 `Yield strength`라고만 표시
  - material 생성 입력과 search facet을 같은 control로 재사용

결론: 현재 전역 fixed filter에서는 제거한다. 위 contract를 server query가 지원할 때 condition-aware metal facet으로 재도입한다.

### M-06 Active filter summary

- `user_job`: 현재 결과가 왜 좁혀졌는지 확인하고 특정 조건만 되돌린다.
- `placement`: search 아래, results header 위.
- `content`: scope, query, category path, selected facet을 human-readable chip으로 표시.
- `action_output`: remove one, clear group, clear all.
- `states`: no filters, active, stale definition.
- `not_allowed`: rail을 닫으면 filter context가 사라지는 것, `Clear filters` 하나만 두어 무엇이 지워질지 모르게 하는 것.

### M-07 Results header and pagination

- `user_job`: 전체 matching 결과와 현재 loaded page를 구분한다.
- `placement`: results table 바로 위.
- `content`: `N matches · rows a–b`, active sort, layout/column view, refresh time.
- `source`: 같은 server query의 total과 page metadata.
- `states`: loading, partial page, fully loaded, stale, error.
- `not_allowed`: client-filtered subset 수와 unfiltered server total을 함께 `shown/total`로 표시.

### M-08 Results table

- `user_job`: identity, condition, 상태, 핵심 property, model/card readiness로 후보를 빠르게 스캔한다.
- `why`: dense scientific catalog의 primary comparison surface다.
- `placement`: 중앙 dominant area.
- `visible_when`: Find result가 하나 이상.
- `source`: server-side condition-aware row projection. sort/filter/pagination도 같은 query contract를 사용한다.
- `default columns`: grade/name, material family, form/condition, provider, release/version, active layout의 핵심 property, curve/model/card availability.
- `action_output`: row select는 inspector context를 바꾸고, open은 exact detail route, compare add는 tray만 바꾼다.
- `states`: loading skeleton, populated, no match, partial/restricted fields, row error.
- `validation`: property column마다 quantity·unit·condition semantics가 명확해야 한다.
- `recovery`: sort/column widths/page/row selection을 보존한 retry.
- `not_allowed`: GUID/hash/plugin key 기본 열, 모든 family에 Yield 열 고정, row마다 detail·graph·card N+1 호출, checkbox selection을 자동 compare로 간주.

### M-09 Column/layout chooser

- `user_job`: current task에 필요한 property를 같은 의미의 saved view로 본다.
- `placement`: results header 우측 secondary action.
- `visible_when`: server-defined layout가 둘 이상.
- `source`: governed layout/attribute definition.
- `action_output`: column set, property facet availability, unit display.
- `states`: current, loading, unavailable.
- `not_allowed`: 각 사용자가 의미 없는 내부 attribute를 무제한 추가하거나 모든 property를 한 표에 넣는 것.

### M-10 Compare tray

- `user_job`: shortlist의 property·curve·model/card readiness를 조건과 출처까지 비교한다.
- `why`: results scan과 심층 비교는 서로 다른 cognitive task다.
- `placement`: 화면 하단 dock 또는 명시적 side workspace. route 이동 후에도 shortlist 유지.
- `visible_when`: 한 개 이상 add; 비교 view는 두 개 이상.
- `source`: exact material revisions와 comparable quantity definitions.
- `action_output`: add/remove/reorder/base pin, only-differences view, curve overlay.
- `states`: ready, condition mismatch, missing, restricted, superseded, error.
- `validation`: unit conversion 가능 여부, 같은 property definition인지, condition mismatch를 확인.
- `recovery`: 한 record 실패가 전체 compare를 없애지 않음.
- `not_allowed`: 값이 크면 무조건 green, source/condition 없는 숫자 나열, 영구 disabled Compare command.

### M-11 Selected-material inspector

- `user_job`: detail을 열기 전에 선택 후보의 적합성·신뢰성·다음 행동을 판단한다.
- `placement`: results 오른쪽 context pane. row selection과 동시에 갱신되므로 table과 가까워야 한다.
- `visible_when`: row selected; 좁은 화면에서는 drawer.
- `content priority`:
  1. identity + form/condition
  2. release/current/superseded + version
  3. provider/source quality
  4. active layout의 핵심 property
  5. test/model/card readiness
  6. primary next action
- `states`: loading, ready, restricted, stale/superseded, unsupported workflow.
- `action_output`: open datasheet, add to compare, start modeling, open exact card target.
- `not_allowed`: 빈 공간을 큰 카드로 채움, internal ID 강조, `Ready solver cards`를 material draft 상태와 무관하게 표시.

### M-12 Start Modeling

- `user_job`: exact material revision과 objective를 새 modeling session의 context로 전달한다.
- `placement`: selected inspector 또는 material detail의 release/readiness 문맥 가까이.
- `visible_when`: 선택 material family가 지원되고 사용자가 modeling 권한을 가질 때.
- `requires`: exact material revision, supported physical workflow, objective 또는 test data 연결.
- `action_output`: 새 session setup. material/state/family는 explicit pin.
- `states`: available, requires setup, unsupported, restricted.
- `validation`: composite/ceramic/unknown을 metal로 fallback하지 않음.
- `not_allowed`: context 없이 곧바로 Fit stage로 열기.

### M-13 Material detail header

- `user_job`: 사용하려는 정확한 material identity와 revision을 확인한다.
- `placement`: detail 상단 고정.
- `content`: `Grade · form · condition · direction`, provider, Released/Draft, current/superseded/withdrawn, version, last reviewed.
- `primary action`: 현재 state에 따라 `Use released card`, `Start modeling`, `Submit for review` 중 하나.
- `not_allowed`: condition을 탭 안에 숨김, card 개수를 identity보다 강조, 여러 target이 있는데 모호한 `Preview card`.

### M-14 Datasheet layouts

- `user_job`: 목적별로 property, curve, CAE artifact, evidence를 단계적으로 읽는다.
- `placement`: detail header 아래 tabs.
- `tabs`: Overview, Properties, Curves, CAE Cards, Evidence. 관계가 중요하면 Relations를 별도 tab 또는 context pane으로 둔다.
- `source`: governed layout + exact revision.
- `states`: loaded, partial/restricted, empty with reason, error.
- `not_allowed`: 모든 attribute를 하나의 긴 accordion으로 펼침, 빈 tab을 성공처럼 노출.

### M-15 Property row

- `user_job`: 값이 현재 사용 조건에 적합하고 신뢰할 수 있는지 판단한다.
- `content`: display name, value/range, unit, condition, source type, revision; uncertainty가 있으면 함께 표시.
- `placement`: property group 안에서 value와 provenance를 같은 row 또는 즉시 인접 disclosure에 둔다.
- `states`: measured, derived, fitted, generic, AI-estimated, missing, not applicable, restricted.
- `not_allowed`: 색만으로 source 표현, tooltip에만 condition 숨김, generic/fitted를 measured처럼 표시.

### M-16 Representative curve

- `user_job`: 선택 record의 응답 형상과 적용 조건을 빠르게 확인한다.
- `source`: governed curve endpoint와 exact test/model/condition.
- `placement`: Overview의 보조 evidence 또는 Curves tab의 primary plot.
- `states`: available, multiple curves, missing, restricted.
- `not_allowed`: native solver card text를 파싱해 실제 시험 curve처럼 표시, 축·단위·condition 없는 curve.

### M-17 CAE Cards table and chooser

- `user_job`: 승인된 source model에서 특정 solver artifact를 안전하게 preview·deliver한다.
- `placement`: Material detail의 CAE Cards tab. 여러 target을 비교할 폭이 필요하다.
- `columns`: solver/version, law/card, source model revision, condition, unit system, mapping state, validation coverage, release state, updated, blocked reason.
- `requires`: exact released/reviewed model, target solver/version, supported mapping, required parameters.
- `action_output`: target-specific preflight → native preview → deliver artifact.
- `states`: ready, exact, transformed, approximated, unsupported, missing parameter, validation warning, restricted.
- `validation`: approximation/ignored field와 영향, target version compatibility, unit conversion, source lineage.
- `not_allowed`: solver target을 고르지 않은 generic `Preview card`, approximation 무경고, generic data를 조용히 포함, source revision 없는 download.

### M-18 Relations and revision context

- `user_job`: material–test–processed dataset–model–card–document lineage와 successor/predecessor를 이해한다.
- `placement`: detail context pane 또는 Relations layout.
- `row content`: human relationship, object identity, condition, state, version, available action.
- `states`: current, superseded, withdrawn, restricted, broken link.
- `not_allowed`: 모든 relation을 같은 중요도로 나열, GUID를 relation label로 사용.

## 4. Modeling Workbench

### 4.1 정보 구조

```text
Modeling session
├─ Session setup
├─ Data
├─ Process
├─ Fit
├─ Validate
├─ Review / Release
└─ Export
```

공통 workbench는 모든 단계에서 같은 3열을 강제하지 않는다. 각 영역의 역할은 다음 원리로 정한다.

- 왼쪽: 현재 판단에 사용할 source·specimen·operation·candidate의 navigator
- 중앙: 사람이 판단해야 하는 주 evidence와 폭이 필요한 table
- 오른쪽: 현재 선택한 대상 하나의 설정·warning·결정
- 상단: exact session context, stage state, primary action

Data mapping처럼 table 폭이 더 필요한 단계에서는 왼쪽 rail을 접고, Export처럼 lineage와 preflight가 중심인 단계에서는 plot을 secondary disclosure로 내린다. 중요한 것은 열 수가 아니라 source, evidence, setting, decision의 관계다.

### W-01 Session setup

- `user_job`: 어떤 material, physical workflow, objective, source data로 작업할지 고정한다.
- `why`: family와 objective가 필요한 시험 유형·process·model 후보·export를 결정한다.
- `placement`: 새 session 진입 화면. Data 이후의 permanent family tab으로 두지 않는다.
- `visible_when`: 새 session 또는 explicit “Change setup”.
- `source`: selected material revision, supported workflow registry, connected test data.
- `input`: material/state, workflow family, objective, optional target use/solver.
- `action_output`: versioned session context; first stage는 Data.
- `states`: incomplete, ready, unsupported, restricted.
- `validation`: unknown family를 metal로 fallback하지 않음; source와 objective compatibility 확인.
- `invalidates`: 기존 session에서 변경하면 Test Data 이후 전부.
- `recovery`: 변경 영향 목록을 보여주고 cancel 또는 new working revision 선택.
- `not_allowed`: 새 session의 default stage를 Fit으로 설정, family tab click으로 material을 조용히 바꿈.

### W-02 Stage stepper

- `user_job`: 전체 진행 위치, 완료·차단·stale 상태, 다음 선행조건을 이해한다.
- `placement`: Modeling command bar에 고정.
- `stages`: `Data → Process → Fit → Validate → Review/Release → Export`.
- `states`: not started, current, complete, warning, blocked, stale.
- `action_output`: 완료된 stage로 이동; blocked stage click은 prerequisite 설명.
- `not_allowed`: URL tab만 바뀌고 상태 의미가 없는 nav, Fit complete를 Validated로 표시.

### W-03 Session context strip

- `user_job`: current material/state/test dataset/processed revision/model decision을 잃지 않는다.
- `placement`: stepper 아래 한 줄; stage content보다 위.
- `content`: human material+condition, workflow objective, dataset revision, current working version, dirty/stale marker.
- `behavior`: Process 이후 material/state/family는 read-only pin. 변경은 setup으로 돌아가 explicit invalidation.
- `not_allowed`: Export dock에서 material/state를 늦게 바꿈, internal method ID 노출.

### W-04 Stage primary action

- `Data`: `Save dataset`
- `Process`: `Save processed curves`
- `Fit`: 상태에 따라 `Run fit` 또는 `Save selected candidate`
- `Validate`: `Run validation`
- `Review`: `Submit for review`, reviewer에게는 `Approve` 또는 `Request changes`
- `Release`: `Release version`
- `Export`: `Generate preview` 후 artifact가 준비되면 `Deliver card`

하나의 `Complete`나 `Commit reviewed ...`가 여러 상태 전이를 동시에 만들면 안 된다.

## 5. Data stage

### D-01 Source mode tabs

- `user_job`: governed library data, local test file, expert canonical JSON 중 source 방식을 선택한다.
- `placement`: Data stage 시작점.
- `visible_when`: dataset이 아직 pin되지 않았거나 replace action을 실행했을 때.
- `modes`: `Library`, `Local file`; `Canonical JSON`은 Advanced.
- `states`: empty, inspecting, mapped, saved.
- `recovery`: tab 전환 시 진행 상태를 보존하거나 discard confirmation.
- `not_allowed`: expert JSON을 일반 file import와 같은 비중으로 강조.

### D-02 Library exact revision selector

- `user_job`: 이미 governed된 정확한 test dataset을 재사용한다.
- `source`: permitted dataset revisions.
- `row content`: dataset name, specimen, test type, temperature/direction/rate, points/channels, revision state.
- `action_output`: selected exact dataset revision.
- `states`: available, superseded, restricted, incompatible.
- `not_allowed`: 이름과 `rN`만 보여 condition·시험 유형을 숨김.

### D-03 Local file inspector

- `user_job`: parser가 파일을 어떻게 읽었는지 저장 전에 확인한다.
- `placement`: source selection 뒤 중앙 primary area.
- `input`: 실제 지원하는 CSV/TSV/XLSX 등 parser extension만 표시.
- `output`: sheet/header/decimal/column detection, raw table, raw curve preview, parse issues.
- `states`: uploading, parsing, preview, warning, blocked, error.
- `validation`: 빈 열, mixed decimal, nonnumeric rows, duplicate/nonmonotonic x, missing sheet/header.
- `recovery`: file과 선택 sheet/header를 보존하고 correction/retry.
- `not_allowed`: 제품 소개의 “any format” 문구를 실제 지원 범위처럼 표시.

### D-04 Test identity and provenance

- `user_job`: 시험 결과가 어떤 specimen·조건·실험에서 왔는지 고정한다.
- `placement`: raw preview 옆 provenance group 또는 연결된 Test Run summary.
- `source`: Test Run metadata가 있으면 자동 채움; 사용자가 편집하면 provenance event.
- `fields`: specimen, test type, temperature, direction, strain rate/frequency/time domain, lab, operator, equipment/method when available.
- `visible_when`: 해당 workflow가 요구하는 필드만.
- `validation`: 필수 이유와 source를 label/help에 설명.
- `not_allowed`: Maker/Operator/Lab를 맥락 없이 모두 필수 text field로 나열.

### D-05 Axis and unit mapping table

- `user_job`: 원본 column을 물리 quantity와 단위로 해석한다.
- `placement`: raw table/plot과 동시에 볼 수 있는 중앙 table 또는 오른쪽 mapping inspector.
- `row content`: source column, sample values, proposed meaning, raw unit, normalized unit, scale/offset, status.
- `action_output`: mapping preview와 normalized curve.
- `states`: proposed, confirmed, warning, missing, conflict.
- `validation`: required x/y, unit dimension, duplicate meaning, conversion sample, monotonicity requirement.
- `invalidates`: confirm 이후 mapping을 바꾸면 Process 이후 전부 stale.
- `recovery`: invalid row만 강조하고 다른 mapping과 raw preview 유지.
- `not_allowed`: `metal.strain.semantic_key` 같은 내부 key를 기본 label로 표시.

### D-06 Data plot

- `user_job`: raw와 mapped curve가 물리적으로 예상한 모양인지 확인한다.
- `placement`: mapping table과 같은 main evidence area.
- `content`: raw/mapped overlay, axis name/unit, selected channel/specimen, issue marker.
- `states`: no mapping, partial, ready, warning.
- `not_allowed`: `Preview source`, `Preview on graph`, `Register reviewed data`를 같은 상태에서 동등한 action으로 제공.

### D-07 Save dataset

- `requires`: source parsed, required mapping confirmed, provenance minimum met, blocking issues resolved.
- `action_output`: immutable raw source + versioned normalized dataset + mapping profile + provenance.
- `label`: `Save dataset`; review가 실제 없으면 `reviewed data`라고 부르지 않는다.
- `states`: dirty, saving, saved, failed.
- `recovery`: 실패 시 source/mapping/plot state 보존.

## 6. Process stage

### P-01 Curve/specimen rail

- `user_job`: 처리하고 fitting에 사용할 specimen과 curve를 선택하고 상태를 본다.
- `placement`: 왼쪽. evidence set 선택은 plot과 operation inspector를 모두 지배한다.
- `row content`: specimen ID, test mode, condition, included/excluded, visible/hidden, quality warning.
- `controls`: `Include in processing/fit`와 `Show on plot`을 별개 control로 둔다.
- `states`: included, excluded with reason, hidden, invalid, warning, selected.
- `not_allowed`: `Curve 01`만 표시, checkbox 하나가 visibility·fit inclusion·statistics inclusion을 동시에 뜻함.

### P-02 Replicate analysis

- `user_job`: 반복 시험의 alignment, mean, band와 outlier를 검토한다.
- `placement`: curve rail의 영구 control이 아니라 `Replicate analysis` secondary panel.
- `visible_when`: 호환 가능한 replicate가 2개 이상.
- `input`: alignment policy/points, member inclusion, mean/band policy, intersection/extrapolation policy.
- `action_output`: derived aggregate curve와 member preservation.
- `states`: unavailable, preview, warning, saved.
- `invalidates`: aggregate를 쓰는 downstream Fit 이후.
- `not_allowed`: Data·Fit·Export 모든 단계에 `Alignment points`, `Add mean & band`를 상시 표시.

### P-03 Add operation palette

- `user_job`: 현재 curve에 필요한 처리 작업을 목적 중심으로 추가한다.
- `placement`: operation pipeline의 secondary action.
- `visible_when`: current workflow, curve state, prerequisite에 적용 가능한 operation만.
- `grouping`: data quality, alignment/aggregation, smoothing, physical workup, domain transformation.
- `item content`: human name, purpose, required input, downstream effect.
- `action_output`: versioned recipe operation draft.
- `not_allowed`: registry의 11개 method ID를 flat details 목록으로 노출, option이 하나인데 `Add operation 11` 표시.

### P-04 Operation pipeline

- `user_job`: 처리 순서와 각 단계의 상태·영향을 이해하고 재현한다.
- `placement`: 왼쪽 또는 compact navigator. plot 폭을 과도하게 줄이지 않는다.
- `row content`: order, human purpose label, scope, clean/dirty/warning/saved.
- `actions`: select, reorder, disable/remove, undo.
- `validation`: invalid order와 missing prerequisite를 계산 전에 설명.
- `not_allowed`: 기술 method key를 primary label, operation과 fit candidate를 같은 rail에 혼합.

### P-05 Operation inspector

- `user_job`: 선택 operation 하나의 가정과 결과 영향을 조정한다.
- `placement`: 오른쪽 contextual inspector. 중앙 before/after graph와 동시에 봐야 한다.
- `content order`: purpose → scope → auto suggestion/source → parameters → preview effect → warnings → reset.
- `states`: clean, dirty, calculating, ready, warning, error.
- `recovery`: numeric input과 graph selection을 보존한 retry.
- `not_allowed`: smoothing·shift·mean·yield·necking field를 한 무작위 form에 동시에 노출, 150px ribbon 안에 숨김.

### P-06 Elastic–plastic separation

- `user_job`: metal engineering tensile curve의 elastic/plastic 경계와 유효 측정 범위를 정의한다.
- `placement`: Process operation inspector. Fit에는 두지 않는다.
- `visible_when`: metal elastoplastic workflow와 필요한 tensile curve가 있을 때.
- `subcomponents`:
  - Young’s modulus: auto/manual, detection range, calculated value, graph region
  - Yield definition: Rp0.2 또는 user criterion, calculated value, marker
  - Necking point: auto/manual, valid measured range end, marker
- `source`: selected processed tensile curve와 exact operation recipe.
- `validation`: elastic sample 부족, negative/nonphysical value, curve 범위 밖, yield가 necking 이후, range overlap.
- `manual override`: value + unit + reason; suggested/derived/manual source 표시.
- `invalidates`: processed dataset 새 revision, Fit·Validate·Review·Export stale.
- `not_allowed`: supplier datasheet yield로 derived value를 몰래 대체, hyperelastic/viscoelastic에 표시.

### P-07 Before/after plot

- `user_job`: operation이 source curve에 미친 영향을 판단한다.
- `placement`: 중앙 dominant evidence.
- `series`: Raw, Prepared, Excluded, Aggregate, current preview, modulus/yield/necking marker.
- `states`: no selection, preview, ready, warning.
- `behavior`: operation 변경 후에도 selected curve, zoom, visible series 보존.
- `not_allowed`: `Selected stage` 같은 모호한 label, 축·단위 없는 그래프.

### P-08 Save processed curves

- `requires`: recipe valid, preview computed, blocking warnings resolved or acknowledged.
- `action_output`: exact source dataset + recipe revision + processed curve revision.
- `label`: `Save processed curves`.
- `states`: dirty, saving, saved, failed.
- `not_allowed`: 실제 review 없이 `Commit reviewed output`.

## 7. Fit stage

### F-01 Fit curve rail

- `user_job`: calibration evidence set을 구성하고 각 시험 조건을 확인한다.
- `placement`: 왼쪽; plot과 candidate calculation의 input을 지배한다.
- `row content`: specimen/test type/condition, included/excluded, visible/hidden, warning.
- `visible_when`: saved processed curves가 있을 때.
- `filter`: curve가 많을 때만 test type, temperature, direction, strain rate를 목록 위에 제공.
- `invalidates`: included set 변경 시 candidate·validation·review·export stale.
- `not_allowed`: navigation click으로 arbitrary settings field를 생성.

### F-02 Physical workflow label

- `user_job`: 지금 calibrate하는 물리 model family를 확인한다.
- `placement`: session context; read-only.
- `examples`: Metal elastoplastic, Hyperelastic, Linear viscoelastic.
- `not_allowed`: Voce/Swift를 solver card로, MAT24/LAW36을 calibration family로 표시.

### F-03 Calibration approach/model selector

- `user_job`: current physics와 evidence에 맞는 candidate model set을 고른다.
- `placement`: 오른쪽 inspector 상단 또는 run-fit setup.
- `visible_when`: 호환 model이 둘 이상이거나 사용자가 명시적 model choice를 해야 할 때.
- `source`: domain registry의 supported calibration models와 prerequisites.
- `action_output`: parameter schema와 fit run definition.
- `states`: compatible, incompatible with reason, unsupported, selected.
- `not_allowed`: 모든 model/failure/rate option을 상시 노출, option이 하나인데 `Add fit method 1`.

### F-04 Parameter and bounds editor

- `user_job`: optimizer의 initial value, min/max, fixed/free 가정을 확인·조정한다.
- `placement`: 선택한 model 아래 오른쪽 inspector.
- `visible_when`: model selection 후 해당 schema가 있을 때.
- `row content`: human parameter, value, unit, lower/upper, fixed/free, near-bound warning.
- `validation`: physical/domain bound, lower < upper, unit compatibility.
- `invalidates`: 변경 시 해당 fit candidates와 downstream validation/export.
- `not_allowed`: model 선택 전 빈 parameter field, internal parameter key만 표시.

### F-05 Fit range and extrapolation definition

- `user_job`: 측정 범위, fit에 쓴 범위, solver 사용 예상 범위의 차이를 판단한다.
- `placement`: 중앙 graph range band + 오른쪽 numeric inspector.
- `input`: fit start/end, excluded region, target use range, extrapolation law/blend.
- `output`: measured/fit/extrapolated/solver-used bands.
- `validation`: range order, measured coverage, nonphysical extrapolation, unsupported target.
- `not_allowed`: measured·fit·extrapolated를 같은 선으로 표시, range를 details 안에 숨김.

### F-06 Run fit

- `requires`: processed revision pinned, evidence set nonempty, model schema valid.
- `action_output`: candidate run records; 사용자 selection은 만들지 않는다.
- `states`: ready, queued, running, partially completed, failed, completed.
- `recovery`: 실패한 candidate만 retry 가능; curve set, parameters, zoom 보존.
- `not_allowed`: 계산 완료 시 자동 `Selected`.

### F-07 Dominant fit plot

- `user_job`: measured/processed/fitted/extrapolated response와 residual/tangent를 눈으로 검토한다.
- `placement`: 중앙, 가용 workbench 폭의 실질적 주 영역. 저장소 hard gate와 viewport를 함께 만족하되 inspector를 사용할 수 없게 만드는 artificial ribbon score는 금지.
- `modes`: response, residual, derivative/tangent, extrapolation/stability.
- `content`: axis name/unit, legend, selected candidate, range bands, condition, metric definition.
- `behavior`: mode/stage 이동 후 zoom, visibility, selected curve/candidate 보존.
- `not_allowed`: `metal.hardening_fit_extrapolate` 같은 method ID를 title로 사용, 작은 graph 옆 거대 form.

### F-08 Candidate comparison table

- `user_job`: error뿐 아니라 범위·안정성·mapping 적합성을 함께 비교한다.
- `placement`: 중앙 graph 아래 또는 넓은 decision dock. 폭이 필요한 표이므로 좁은 rail에 넣지 않는다.
- `columns`: decision, law/model, fit metric+definition, fit range, extrapolation behavior, stability, parameter summary, solver compatibility, warning.
- `states`: not run, running, converged, warning, failed, incompatible.
- `labels`: `Recommended`와 `Selected`를 별도 column/state로 표시.
- `not_allowed`: 모든 row에 같은 applicability 문자열, 정의 없는 score, 최저 RMSE/BIC를 `BEST`와 `Selected`로 동시에 표시.

### F-09 Explicit candidate selection

- `user_job`: 엔지니어가 사용할 model candidate를 근거와 함께 선택한다.
- `requires`: candidate run complete; blocking physical failure 없음.
- `input`: explicit row action, selection reason; warning이 있으면 별도 acknowledgement.
- `action_output`: working decision record. 아직 review/approval/release가 아님.
- `states`: none, selected, changed, stale.
- `invalidates`: candidate 변경 시 validation·review·release·export.
- `not_allowed`:
  - default `primary_family`, `selected_term_count`를 사용자 selection으로 사용
  - reason만 입력하면 자동 commit
  - recommendation 변경 시 selected candidate 자동 변경

### F-10 Single law / Blend mode

- `user_job`: 단일 hardening law와 두 law blend 중 무엇을 사용하는지 정확히 정의한다.
- `placement`: selected candidate inspector.
- `visible_when`: domain model이 blend를 지원할 때.
- `single output identity`: selected law + parameters + range.
- `blend output identity`: primary law + secondary law + ratio + parameters + range.
- `validation`: ratio 범위, 두 law compatibility, extrapolation/stability.
- `not_allowed`: 50% Swift + 50% Voce를 `Swift reviewed fit`으로 기록.

### F-11 Save selected candidate

- `requires`: explicit candidate selected, reason present, warning acknowledgement complete.
- `action_output`: immutable candidate snapshot과 decision record.
- `state`: Saved, not Reviewed.
- `not_allowed`: `Commit reviewed fit`로 save·select·review를 한 번에 실행.

## 8. Validate stage

### V-01 Validation plan

- `user_job`: 어떤 질문을 어떤 reference와 range에서 검증할지 정의한다.
- `placement`: Validate 시작점의 inspector.
- `input`: saved candidate revision, validation type, reference/holdout/specimen, range, solver/version when solver validation.
- `states`: unavailable, ready, unsupported, invalid.
- `not_allowed`: Fit metric을 validation이라고 이름만 바꿈.

### V-02 Mathematical/data validation

- `user_job`: holdout 또는 excluded data에서 response error와 stability를 평가한다.
- `output`: run revision, overlay, region-specific metric, pass/warning/fail/unchecked.
- `validation`: metric definition과 threshold source를 명시. 제품 결정이 없으면 `TBD/Not configured`.
- `not_allowed`: threshold를 임의로 만들거나 “낮은 error”만으로 physical validity 판정.

### V-03 Solver/physical validation

- `user_job`: mapped solver artifact 또는 model response가 reference behavior를 재현하는지 확인한다.
- `input`: frozen model snapshot, solver/version, specimen/problem definition.
- `output`: persistent job, computed/reference overlay, region metrics, logs/evidence.
- `states`: not run, not supported, queued, running, passed, warning, failed, canceled.
- `not_allowed`: Not run/Not supported를 success 색상, toast만으로 long job 완료.

### V-04 Validation result

- `placement`: 중앙 overlay + 오른쪽 result/issue summary.
- `content`: validation type, coverage, reference revision, metric definition, threshold source, warning/failure impact.
- `invalidates`: source model 또는 validation plan 변경 시 review/release/export stale.
- `recovery`: failed run retry 시 plan, selection, plot state 보존.

## 9. Review and Release

### R-01 Review package

- `user_job`: source부터 candidate·validation·mapping warning까지 변경 근거를 검토한다.
- `content`: material/test revisions, mapping, process recipe, selected model identity, parameter/range, validation results, warnings, diff from previous release, author reason.
- `placement`: Review stage의 main summary; 원본 evidence로 drill-down 가능.
- `states`: draft, submitted, changes requested, approved.
- `not_allowed`: candidate save 직후 자동 reviewed 상태.

### R-02 Submit for review

- `requires`: saved candidate, required validation policy satisfied 또는 명시적 waiver policy.
- `action_output`: immutable review package + review request + Activity item.
- `not_allowed`: 승인자를 추측하거나 role 정책을 하드코딩.

### R-03 Approve / Request changes

- `visible_when`: reviewer permission.
- `input`: decision, comment; warning override가 있으면 정책과 reason.
- `action_output`: auditable review event.
- `states`: approved, changes requested.
- `not_allowed`: 작성자와 검토자의 행위를 한 버튼으로 합침.

### R-04 Release version

- `requires`: approved review와 조직 release policy.
- `action_output`: immutable released model revision; previous release는 successor relation을 가진다.
- `not_allowed`: 기존 released object overwrite, Save를 Publish/Release와 동일시.

## 10. Export stage

### E-01 Export prerequisite checklist

- `user_job`: 현재 exact model이 target artifact를 만들 준비가 되었는지 확인한다.
- `placement`: Export main area의 첫 부분.
- `checks`: current session output, exact material/state/dataset match, IR, review/release policy, validation coverage, solver/version, units, required parameters, mapping support.
- `states`: pass, warning, blocked, stale.
- `not_allowed`: “Commit reviewed fit first”와 다른 기존 delivery를 동시에 표시.

### E-02 Exact source pin

- `user_job`: 어떤 Processing Output과 model revision을 내보내는지 확인한다.
- `placement`: checklist와 lineage의 시작.
- `source`: current session exact output만 기본 허용.
- `validation`: material/state/Test Data/recipe/candidate revision 완전 일치.
- `not_allowed`: 전역 Processing Output 또는 첫 existing model fallback, material/state와 무관한 method ID 필터.

### E-03 Delivery lineage

- `user_job`: 변환 단계와 각 artifact의 identity를 추적한다.
- `placement`: Export의 primary work area.
- `chain`: Processing Output → Material Model IR → Neutral model → target preflight → native card.
- `content`: revision, created from, status, mapping difference, actor/time.
- `not_allowed`: 내부 JSON blob만 보여주거나 단계가 성공했다고 가정.

### E-04 Solver target selector

- `user_job`: solver/version/law/unit system과 필요한 condition을 명시한다.
- `visible_when`: exact source model pinned.
- `source`: supported exporter registry.
- `input`: solver, version, compatible law, unit system, target ID and required options.
- `validation`: mapping compatibility와 required field.
- `invalidates`: target 변경은 source model을 유지하고 preflight/preview/artifact만 stale.
- `not_allowed`: solver 선택 전에 material ID와 solver-only field 노출.

### E-05 Mapping preflight

- `user_job`: source model과 target card 사이의 손실·변환·근사를 승인 가능한지 판단한다.
- `content`: each field mapping `exact | transformed | approximated | ignored | unsupported`, impact, validation coverage, alternative.
- `states`: ready, warning, blocked.
- `not_allowed`: approximation/ignored field 무경고, unsupported를 disabled button만으로 설명.

### E-06 Native card preview

- `user_job`: 실제 전달 파일의 keyword, unit, parameter, curve reference를 생성 전에 확인한다.
- `requires`: preflight not blocked.
- `action_output`: target-specific ephemeral preview.
- `states`: generating, ready, warning, failed, stale.
- `recovery`: target settings과 scroll/cursor 보존.
- `not_allowed`: preview를 delivered artifact로 기록.

### E-07 Deliver card

- `requires`: current preview, required warning acknowledgement, release/delivery permission.
- `action_output`: persistent artifact with filename, checksum, source revision, target, actor/time; Materials CAE Cards와 Activity에 연결.
- `states`: delivering, delivered, failed.
- `not_allowed`: source version 없는 download, Preview와 Deliver를 같은 action으로 처리.

### E-08 Source response disclosure

- `user_job`: 필요할 때 source model의 response와 validation evidence를 다시 확인한다.
- `placement`: Export의 collapsed secondary disclosure.
- `not_allowed`: Export에 curve rail, alignment, mean/band control을 영구 표시.

## 11. Activity

### A-01 Work queue sections

- `user_job`: 자신에게 필요한 다음 행동과 최근 결과를 찾는다.
- `sections`: Needs attention, In progress, Recent outcomes.
- `placement`: Activity main page.
- `source`: 실제 review/job/session/delivery state.
- `not_allowed`: infrastructure queue name, 빈 dashboard card, 임의 통계.

### A-02 Activity item

- `content`: human material/workflow, exact state, last actor, timestamp, next action, warning/failure impact.
- `action_output`: 정확한 route와 object/session revision으로 resume.
- `states`: review requested, changes requested, mapping warning, validation queued/running/failed, ready to release, delivered.
- `recovery`: target object가 superseded/restricted면 이유와 가능한 successor/action 제공.
- `not_allowed`: generic “job complete” toast archive, route만 열고 exact state를 잃음.

### A-03 Long-running job row

- `content`: Queued/Running/Completed/Failed/Canceled, stage, elapsed time, initiator, input revision.
- `actions`: cancel when safe, retry same revision, open evidence.
- `not_allowed`: spinner만 표시, browser refresh 후 상태 소실.

## 12. Family별 조건부 필드

| field/component | Metal elastoplastic | Hyperelastic | Viscoelastic | 표시 규칙 |
|---|---:|---:|---:|---|
| Young’s modulus detection | Process | 숨김 | 필요 시 별도 model input | metal curve workup 목적 |
| Yield definition / Rp0.2 | Process | 숨김 | 숨김 | Fit parameter가 아님 |
| Necking point | Process | 숨김 | 숨김 | uniform deformation measured range의 끝 |
| Voce/Swift/Ghosh 등 | Fit | 숨김 | 숨김 | metal hardening candidate |
| Ogden/Mooney–Rivlin 등 | 숨김 | Fit | 숨김 | 필요한 multiaxial test set과 연결 |
| Prony term / DMA·relaxation | 숨김 | 필요 시 coupled branch | Fit | time/frequency evidence 있을 때 |
| Strain-rate model | rate curves 있을 때 | 지원 workflow와 data 있을 때 | 별도 물리 계약 | 대응 evidence 없는 Advanced card 금지 |
| Failure criteria | base model과 failure data 이후 | 숨김 | 숨김 | 기본 Fit에서 상시 노출 금지 |
| Density·Poisson ratio | exporter가 요구할 때 | exporter가 요구할 때 | exporter가 요구할 때 | calibration setting과 분리 |
| Material ID·solver units | Export | Export | Export | solver target 전에는 숨김 |

## 13. Typography, density, state 표현

- page title, pane title, body, data, label, metadata, code의 semantic typography token을 하나의 권위 명세로 둔다.
- body/data 크기는 기존 권위 문서 간 충돌을 해소해 한 값으로 고정하고 component-local 임의 크기를 금지한다.
- scientific number는 unit과 함께 정렬하며 원본 precision과 display precision을 구분한다.
- status, source type, mapping state, curve role은 semantic token을 공유한다.
- 색만으로 상태·source·curve를 구분하지 않는다. text/shape/line style을 병행한다.
- graph는 axis name/unit, legend, selected curve, range와 metric definition을 가진다.
- 1366×768에서도 primary action, selection reason, warning acknowledgement가 내부 scroll을 찾아야만 보이는 구조가 아니어야 한다.
- table은 sticky header, sort, resize, column customization, keyboard row navigation과 visible focus를 제공한다.

## 14. 컴포넌트 삭제 판정

다음이면 유지 근거가 없다.

- 실제 route·user flow에서 도달할 수 없음
- 현재 API/domain contract가 지원하지 않는데 static mock으로만 보임
- 다른 component와 같은 action/state를 중복 소유
- normal path에 내부 diagnostic만 노출
- family/workflow 조건과 무관한 engineering-looking field
- 미지원 상태를 fallback default로 숨김
- 목적·source·condition·invalidation을 설명할 수 없음

삭제 전에 route/import/test/CSS selector 참조를 확인하고, 기능이 다른 canonical component로 이동했으며 deep link가 redirect되는지 증명한다.
