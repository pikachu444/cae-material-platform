# 구현 순서·수용 기준·완료 정의

## 1. 왜 DUI-07로 바로 가지 않는가

PR #124로 Fit→solver card 연결은 생겼지만, 최신 감사에서 candidate selection, session invalidation, Export fallback, catalog filter semantics에 데이터 정합성 위험이 확인됐다. 이 상태에서 Admin·Activity·legacy cleanup만 진행하면 잘못된 상태를 더 많은 화면에 확산한다.

따라서 기존 DUI-01~09 번호와 역사적 완료 기록은 바꾸지 않고, DUI-07 전에 `UXC` corrective workstream을 넣는다.

- `UXC`는 완료된 DUI-01~06을 재구현하는 프로젝트가 아니다.
- PR #124의 domain chain은 유지한다.
- 문제가 확인된 state·query·component contract만 바로잡는다.
- 각 slice가 끝날 때 권위 문서와 current screenshot을 같은 PR에서 갱신한다.

## 2. 권장 PR 순서

### UXC-00 — 문서 단일화와 최신 기준선

목표: Codex가 서로 충돌하는 옛 프롬프트와 문서를 읽지 않게 한다.

작업:

- PR #124와 `d16d925` 반영
- 01 문서의 integration map대로 research·product·UI spec 병합
- `AGENTS.md`에 visible engineering field contract 추가
- old UX package와 old start prompt의 유효 내용을 옮기고 삭제
- `CODEX_DESKTOP_ENGINEERING_UI_START.md`를 유일 실행 진입점으로 갱신
- 최신 main에서 screenshot 재캡처
- current/historical/reference 책임을 manifest와 docs portal에 반영

수용:

- stale DUI-06 pending 문구 0
- 충돌하는 canonical typography/layout/state 규칙 0
- deleted docs inbound link 0
- screenshot SHA와 실제 capture SHA 일치

### UXC-01 — Materials query·facet·result 정합성

목표: fixed demo filter가 아니라 전체 catalog에 정확히 적용되는 family-aware Find를 만든다.

작업:

- server-side query/facet/result projection
- Provider와 Evidence source 분리
- family/layout-aware property facets와 columns
- Yield fixed filter 제거 후 metal condition-aware contract가 지원될 때만 재도입
- result count/pagination 의미 정정
- row N+1 fetch 제거
- selected inspector와 exact Start Modeling pin

수용:

- 10,000-material fixture에서 facet/count/result 일치
- polymer/elastomer에 Yield facet/column 없음
- metal yield는 definition·condition·unit·source를 가짐
- search/filter/selection/back state 보존
- N+1 request 회귀 없음

### UXC-02 — Modeling session state와 stage shell

목표: 새 session, context 변경, downstream stale를 정확히 만든다.

작업:

- session setup과 Data-first 진입
- family/material/state/Test Data exact pin
- reducer/event 또는 explicit clear patch
- invalidation matrix 구현
- `Data→Process→Fit→Validate→Review/Release→Export` stateful stepper
- persistent graph/view state foundation

수용:

- context 변경 후 이전 output이 current Export에 나타나지 않음
- stage state가 Complete/Blocked/Warning/Stale로 설명됨
- new session이 Fit으로 시작하지 않음
- reducer invalidation tests 통과

### UXC-03 — Data·Process component 재구성

목표: import와 curve preparation의 각 입력이 왜 필요한지, 무엇을 바꾸는지 보이게 한다.

작업:

- raw table/curve inspector
- axis/unit mapping decision table
- provenance group
- curve/specimen rail
- operation palette와 ordered pipeline
- contextual operation inspector
- Replicate analysis secondary panel
- metal Elastic–plastic separation
- `Save dataset`, `Save processed curves`

수용:

- raw/normalized unit과 source revision 확인 가능
- Yield definition이 metal Process에만 존재
- manual override는 unit+reason 필요
- process 변경이 downstream stale
- Data/Process에 primary action 하나씩

### UXC-04 — Fit 결정 정합성

목표: 추천과 선택을 분리하고 model identity를 보존한다.

작업:

- default selection `null`
- explicit candidate selection event
- recommendation/selection 별도 표시
- candidate table의 range·stability·compatibility·warning
- single/blend mode
- polymer actual term identity
- parameter/bounds/range inspector
- `Save selected candidate`

수용:

- row select 전 save 불가
- reason만으로 decision 생성 불가
- recommendation change가 selection을 변경하지 않음
- blend identity가 모든 layer에서 일치
- internal method ID가 normal graph/title에 없음

### UXC-05 — Validate·Review·Release

목표: Fit success를 검증·승인으로 과장하지 않는다.

작업:

- validation plan/result record
- 최소 holdout/data validation 수직 slice
- supported solver validation job
- review package와 Activity 연결
- Submit/Request changes/Approve/Release 분리
- backend policy가 없으면 explicit Not configured

수용:

- validation 미실행 상태가 명확
- Fit metric과 validation 결과가 다른 object
- approved와 released 분리
- review 후 수정은 new working revision

### UXC-06 — Exact Export와 delivery

목표: current source와 mapping 차이를 보존한 traceable artifact를 만든다.

작업:

- current exact source pin
- fallback 제거
- prerequisite checklist
- output→IR→Neutral→preflight→native lineage
- target-specific preview
- Preview/Deliver 분리
- Material CAE Cards와 Activity에 artifact 연결
- `neutral-hyperelastic-export.tsx` 책임·이름 교정

수용:

- current source 없으면 artifact UI 미표시
- 다른 material output 사용 불가
- exact/transformed/approximated/ignored/unsupported 표시
- delivered artifact에 filename/checksum/source/target/actor/time
- preview가 delivered로 기록되지 않음

### DUI-07 — Admin canonicalization

UXC state/query contract 위에서 기존 기능을 canonical navigator/grid/property editor로 이식한다. 일반 Materials/Modeling 경로에 admin control을 섞지 않는다.

### DUI-08 — Activity work queue

UXC-05/06이 만든 실제 review/validation/delivery state를 `Needs attention | In progress | Recent outcomes`으로 연결한다. placeholder dashboard를 만들지 않는다.

### DUI-09 — Storybook·legacy JSX/CSS cleanup

active route usage 0, deep-link redirect, screenshot/test 통과를 확인한 뒤 legacy hub, 중복 CSS, dead selector를 삭제한다.

### UXC-99 — End-to-end commercial-readiness gate

두 대표 시나리오, multi-family seed, 접근성, viewport, failure recovery, 문서·screenshot 일치를 최종 검증한다.

## 3. 대표 완료 시나리오

### 시나리오 A — 승인 material card 재사용

```text
Set governed scope
→ Search by grade/standard
→ Narrow by condition/release/target compatibility
→ Inspect exact material revision and evidence
→ Compare shortlist when needed
→ Choose a released source model and solver target
→ Inspect mapping preflight and native preview
→ Deliver a traceable solver artifact
→ Resume artifact from Material detail and Activity
```

완료 증거:

- search total/facet/page가 server query와 일치
- condition/source/release가 값 가까이 보임
- target이 둘 이상일 때 모호한 CTA 없음
- approximation/unsupported가 숨겨지지 않음
- artifact가 source revision과 연결됨

### 시나리오 B — 시험 데이터에서 solver card까지

```text
Create session with material/workflow/objective
→ Inspect raw source
→ Confirm axes, units and test conditions
→ Save Test Data revision
→ Prepare curves and define physical workup
→ Save Processed Dataset revision
→ Run candidate fits
→ Explicitly select a single law or blend with reason
→ Save candidate
→ Run validation
→ Submit, review and release
→ Generate target preview
→ Deliver solver artifact
```

완료 증거:

- 각 단계의 exact input/output revision 확인 가능
- 추천과 선택이 다름
- Yield definition은 metal Process에서만 존재
- context change가 downstream을 stale/clear
- Fit/Validated/Approved/Released/Delivered 상태가 실제 event와 일치

### 시나리오 C — 실패와 복구

```text
Import unit-mismatched file
→ See exact mapping error
→ Correct unit without losing source/table/plot state
→ Run fit with one failed candidate
→ Retry only failed candidate
→ Select warning candidate and acknowledge impact
→ Change upstream mapping
→ See downstream stale chain
→ Recompute and resume review
```

완료 증거:

- 오류가 무엇/원인/영향/다음 행동을 말함
- 입력·selection·plot view state가 보존됨
- stale output이 Export fallback으로 나타나지 않음

## 4. 테스트 데이터 구성

한 개 DP780 row로 상용 UX를 증명하지 않는다. synthetic seed는 합성임을 표시하고 다음을 포함한다.

### Materials

- released/current/exact-card metal
- alternate form/condition
- withdrawn + successor
- missing curve
- metal, polymer, elastomer, composite/unsupported
- internal draft
- supplier measured, derived, fitted, generic, AI-estimated source
- permission-restricted record
- exact, approximated, unsupported solver mapping

### Modeling

- unit mismatch specimen
- excluded outlier
- compatible replicate 3개
- metal single-law와 blend 후보
- polymer actual automatic term이 recipe default와 다른 사례
- 서로 다른 fit/extrapolation trade-off 후보 3개
- validation pass, warning, fail, not supported
- review requested, changes requested, approved
- current output 없음, 다른 material output 존재

### Activity

- mapping review needed
- validation queued/running/failed
- review requested/changes requested
- ready to release
- delivered artifact

## 5. 계층별 검증

### 5.1 Domain/unit

- unit conversion과 condition semantics
- selection/recommendation/blend identity
- reducer invalidation
- state command vocabulary
- mapping preflight state

### 5.2 API/contract

- server-side facet/count/page consistency
- result projection schema
- exact session output query
- validation/review/release records
- artifact lineage
- OpenAPI/schema migration compatibility

### 5.3 Component

- empty/loading/error/restricted/stale
- conditional field visibility by family/workflow
- keyboard/focus
- action prerequisite와 blocked reason
- no internal key in normal path

### 5.4 Integration/E2E

- 시나리오 A, B, C
- back/refresh/resume
- deep-link redirects
- multi-user review state
- long job persistence/retry

### 5.5 Visual

필수 viewport:

- 1366×768
- 1440×900
- 1920×1080

판정:

- page horizontal overflow 없음
- primary action과 blocked reason이 visible
- graph axis/unit/legend/range/selected candidate visible
- table header·selected row·focus visible
- right inspector가 main evidence를 압도하지 않음
- internal scroll 안에 selection reason·warning ack·primary action만 숨지 않음
- semantic typography/spacing/status/curve role 일치

## 6. 화면별 수용 매트릭스

| 화면 | primary user question | 반드시 보이는 것 | 숨기거나 제거할 것 |
|---|---|---|---|
| Materials Find | 어떤 exact material 후보가 목적에 맞는가? | scope, query, active facets, matching count, condition-aware rows, selected context | internal DB key, global Yield, client-only total |
| Material Detail | 이 revision을 신뢰하고 사용할 수 있는가? | identity/condition/state/version/source, property evidence, related models/cards | ambiguous Preview, card count만 강조 |
| Modeling Data | source를 올바른 물리 quantity로 읽었는가? | raw table/plot, mapping, raw/normalized units, conditions, issues | unrelated process/fit controls |
| Modeling Process | 어떤 처리로 curve가 어떻게 바뀌었는가? | curve set, ordered operations, before/after, purpose/scope, workup markers | registry method dump, bare Yield |
| Modeling Fit | 어떤 model을 왜 선택할 것인가? | evidence set, response/residual/range, candidate comparison, explicit selection | automatic selection, internal IDs |
| Validate | 선택 model이 어디에서 검증되었는가? | plan, reference, coverage, result, unchecked region | Fit metric의 validation 위장 |
| Review/Release | 조직 사용 가능한 version인가? | source chain, diff, warnings, validation, actor decisions | Save=Approve=Release |
| Export | 어떤 exact model이 target card로 어떻게 변환되는가? | prerequisite, lineage, target, mapping differences, native preview | global fallback, curve statistics controls |
| Activity | 내가 지금 처리하거나 재개할 일은 무엇인가? | object, state, actor/time, next action, exact resume | infrastructure queue, empty dashboard metrics |

## 7. 문서와 코드의 동시 갱신

각 PR에서 다음을 같은 변경 집합으로 취급한다.

| 코드 변경 | 반드시 함께 갱신 |
|---|---|
| route/nav/stage | user flows, navigation contract, start prompt |
| component behavior/visibility | product spec, UI spec, component tests |
| state vocabulary/event | user flows, implementation status, Activity contract |
| query/API shape | OpenAPI/schema docs, Materials product spec |
| visual layout/token | UI spec, visual acceptance matrix, screenshots |
| completed backlog slice | backlog, implementation status, evidence report |
| current screenshot | screenshot manifest with exact SHA |

historical evidence는 새 동작으로 덮어쓰지 않는다.

## 8. Definition of Done

기능이 보인다는 이유만으로 완료하지 않는다. 각 slice는 다음을 모두 만족한다.

- 사용자 outcome이 한 문장으로 설명된다.
- 모든 새 visible field에 purpose/source/condition/visibility/invalidation이 있다.
- 자동 추천이 사람의 결정을 대신하지 않는다.
- blocked/empty/loading/error/stale/restricted 상태가 있다.
- API와 UI가 같은 total/revision/state를 말한다.
- current exact source가 없을 때 fallback으로 가짜 성공을 만들지 않는다.
- backend/domain 계산·revision·provenance·mapping contract가 보존된다.
- unit, component, integration, E2E, accessibility test가 통과한다.
- 지정 viewport의 before/after evidence가 있다.
- current docs와 screenshot manifest가 같은 commit을 설명한다.
- obsolete code/doc의 참조 0을 확인하고 나서 삭제했다.
- 이 임시 전달 패키지는 저장소에 남지 않는다.

## 9. Stop 조건

다음이면 그럴듯한 UI를 만들지 말고 contract gap을 기록하고 해당 slice를 멈춘다.

- property facet에 condition-aware server semantics가 없음
- candidate actual result identity를 API가 제공하지 않음
- session pointer를 안전하게 clear/stale 처리할 방법이 없음
- review/release policy나 permission이 정의되지 않음
- solver/version mapping support가 실제 registry에 없음
- validation threshold나 reference가 결정되지 않음

다만 관련 없는 전체 프로그램을 중단하지 않는다. 지원 가능한 vertical slice를 끝내고 unsupported 범위를 명시한다.

