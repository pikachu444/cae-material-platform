# Codex 실행용 마스터 프롬프트

아래 프롬프트를 `pikachu444/cae-material-platform`에서 실행하는 Codex에
전달한다. 전달 자료는 최신 `main`의
`docs/_incoming/2026-07-24-organic-ux-update/`에 있다.

---

당신은 `pikachu444/cae-material-platform`의 제품·도메인 UX·프론트엔드·상태 계약을 함께 책임지는 senior engineering agent다.

이번 작업은 화면을 예쁘게 바꾸는 일이 아니다. 최신 `main`의 실제 구현을 기준으로 문서와 코드를 정리하고, 모든 세부 컴포넌트가 재료 데이터·model calibration·governance·solver delivery 업무에 필요한 이유를 갖도록 대대적으로 교정하는 일이다.

## 기준선

이 전달 자료의 감사 기준선은 다음과 같다.

- `main@d16d925d71310d940f93ed5707e7bc229e4c4809`
- PR #124 병합 완료
- DUI-01~06 완료
- DUI-07~09 미완료
- issue #119 독립 리뷰 게이트 보류
- 자동 LLM review 비활성 유지

실행 시 remote `main`이 더 최신이면 그 HEAD를 사용하되, `d16d925` 이후 변경을 먼저 감사하고 이 명세와의 차이를 기록하라. 완료된 DUI-01~06을 과거 프롬프트대로 다시 구현하지 마라.

## 최종 목표

제품은 다음 세 업무 공간을 가진 high-density CAE materials workbench다.

- `Materials`: governed material knowledge를 찾고, 비교하고, 근거·revision을 확인하고, 승인된 model/card를 재사용
- `Modeling`: test data를 import·map·process·fit·validate·review/release하고 solver artifact로 전달
- `Activity`: review·job·warning·delivery를 실제 상태에서 재개

Granta, Granta Selector, Material Modeler, Material Data Center의 화면을 복제하지 마라. 공개 자료에서 검증된 업무 원리를 현재 API, revision, provenance, Material Model IR, exporter mapping contract에 맞게 재해석하라.

## 반드시 먼저 읽을 것

1. 저장소의 모든 applicable `AGENTS.md`
2. 최신 `README.md`, `IMPLEMENTATION_STATUS.md`, `docs/README.md`, `docs/design-index.md`
3. `docs/documentation-manifest.yaml`
4. `docs/01-product/`의 product vision, program brief, user flows, product spec, UI spec, visual acceptance matrix
5. `docs/13-delivery/desktop-engineering-ui-backlog.md`
6. `docs/user-guide/navigation-contract.yaml`, `screenshot-manifest.yaml`
7. PR #124와 latest main의 관련 code/test/evidence
8. 이 전달 패키지의 `README.md`
9. `01_LATEST_MAIN_AUDIT_AND_DOCUMENT_INTEGRATION.md`
10. `02_REFERENCE_SERVICE_WORKFLOW_SYNTHESIS.md`
11. `03_COMPONENT_RATIONALE_SPEC.md`
12. `04_WORKFLOW_STATE_AND_INVALIDATION_CONTRACT.md`
13. `05_CODE_DISPOSITION_AND_REFACTOR_PLAN.md`
14. `06_DELIVERY_PLAN_AND_ACCEPTANCE.md`
15. `08_INTEGRATION_MANIFEST.yaml`
16. 외부 사실 확인이 필요할 때 `09_SOURCE_CATALOG.json`

자료와 latest main이 다르면 코드를 맹목적으로 따르거나 자료를 맹목적으로 덮어쓰지 마라. 실제 domain contract, 사용자 outcome, 최신 evidence를 대조해 차이를 기록하고 판단하라.

## 첫 작업: 문서를 유기적으로 통합

이 전달 폴더는 이미 `main`에 임시로 커밋되어 있다. 이를 새 canonical UX
package로 승격하거나 장기 보관하지 마라. 유효 내용을 기존 권위 문서와
코드에 흡수하고, 모든 inbound link와 실행 참조를 정리한 후 이 임시
폴더 전체를 삭제하라.

`01_LATEST_MAIN_AUDIT_AND_DOCUMENT_INTEGRATION.md`의 경로 매핑대로:

1. 공식 제품 사실은 기존 `docs/00-research/`에 병합한다.
2. 제품 경계는 `product-vision.md`에 둔다.
3. 사용자 목적·state transition·recovery는 `desktop-engineering-user-flows.md`에 둔다.
4. 화면 정보 구조는 `desktop-engineering-ui-product-spec.md`에 둔다.
5. component의 이유·배치·visible condition·input/output·state·error·invalidation은 `desktop-engineering-ui-spec.md`를 단일 원본으로 삼는다.
6. 측정 가능한 viewport·density·accessibility 조건은 `visual-acceptance-matrix.md`에 둔다.
7. 실행 순서와 상태는 backlog에만 둔다.
8. `CODEX_DESKTOP_ENGINEERING_UI_START.md`를 유일한 Codex 시작 문서로 유지한다.
9. PR #124 이전 상태를 current 문서에서 제거한다.
10. 유효 내용을 병합하고 inbound link를 수정한 뒤 old UX package·old start prompt·중복 권위 문서를 삭제한다.

Historical evidence와 screenshot archive는 삭제하거나 current spec으로 다시 쓰지 마라.

문서 통합 전용 PR을 먼저 만들고 다음을 증명하라.

- stale DUI-06 pending 표현 0
- 서로 충돌하는 canonical component/typography/state 규칙 0
- deleted doc inbound link 0
- current screenshot와 manifest source SHA 일치

## 모든 컴포넌트에 적용할 판정

각 visible component와 engineering field에 다음을 코드·spec·test로 답하라.

- 사용자는 무엇을 판단하거나 완료하는가?
- 이 요소가 없으면 어떤 업무가 실패하는가?
- 왜 이 단계와 이 위치에 있어야 하는가?
- 어떤 family/workflow/permission/data state에서만 보이는가?
- 값은 어디에서 왔고 unit, condition, source, revision은 무엇인가?
- 어떤 prerequisite가 필요한가?
- 변경하면 무엇이 stale 또는 clear 되는가?
- loading/empty/warning/blocked/error/restricted 상태는 무엇인가?
- 실패 후 어떤 input/selection/plot state를 보존하는가?

답할 수 없는 요소는 “전문적으로 보인다”는 이유로 설명문을 붙여 유지하지 마라. 올바른 업무에 연결해 재설계하거나 삭제하라.

## 반드시 바로잡을 Materials 문제

현재 fixed filter rail을 그대로 미화하지 마라.

- `Material class`
- `Manufacturer/source`
- `CAE card`
- `Validation/release`
- 모든 family에 상시 노출되는 `Yield strength min/max`

를 다음 semantics로 교체하라.

1. scope와 quick search
2. browse tree/subset
3. server-defined contextual facets with counts
4. active filter chips
5. server-side result projection/sort/page/total
6. independent compare tray
7. condition-aware selected inspector

세부 결정:

- Provider와 Evidence source를 분리한다.
- Release state와 Validation availability를 분리한다.
- Solver facet은 solver/version, model availability, release와 mapping state를 갖는다.
- property facet/column은 active family와 governed layout가 정의할 때만 보인다.
- Yield는 전역 기본 filter에서 제거한다.
- Yield가 필요한 metal/tensile view에서는 definition, condition, unit, source를 가진 server-side range facet으로만 재도입한다.
- `property_sets[0]`을 대표값으로 쓰지 않는다.
- 최대 50개 client subset에 filter를 적용하면서 전체 catalog 결과처럼 보이지 않게 한다.
- row별 detail/graph/card N+1을 projection/batch query로 교체한다.
- unknown/composite/ceramic을 metal Modeling으로 fallback하지 않는다.
- 여러 solver target이 있으면 generic `Preview card`를 쓰지 않는다.

## 반드시 바로잡을 Modeling 문제

### Session과 단계

- 새 session은 setup/Data에서 시작한다. Fit을 default로 하지 않는다.
- family/objective/material/state/Test Data를 exact pin한다.
- permanent family tab으로 context를 조용히 바꾸지 않는다.
- `Data → Process → Fit → Validate → Review/Release → Export` stateful stepper를 만든다.
- current session state는 explicit reducer/event 또는 clear 가능한 patch contract로 관리한다.

### Downstream invalidation

- material/state/family/Test Data 변경은 Processed→Fit→Validation→Review current pointer→IR→Neutral→Export를 stale/clear한다.
- mapping 변경은 모든 downstream을 stale한다.
- process recipe, modulus, yield, necking 변경은 새 Processed revision과 downstream stale을 만든다.
- model/bounds/range 변경은 fit candidates와 downstream을 stale한다.
- selected candidate 변경은 validation/review/export를 stale한다.
- target solver/version/unit 변경은 source model을 유지하고 target artifacts만 재생성한다.
- stale history는 보존하지만 current action의 fallback으로 쓰지 않는다.

### Data

- raw table/curve, file parser issue, sheet/header/decimal을 저장 전에 보여준다.
- mapping row마다 source column, proposed quantity, raw unit, normalized unit, conversion sample과 status를 보여준다.
- Test Run에서 온 provenance와 manual edit를 구분한다.
- 상태형 primary action은 `Inspect → Confirm mapping → Save dataset`.
- 실제 review event가 없으면 `reviewed data`라고 쓰지 않는다.

### Process

- 왼쪽은 specimen/curve의 identity, condition, include, visibility, warning을 보여준다.
- Alignment/mean/band는 compatible replicate가 둘 이상일 때 `Replicate analysis`로만 노출한다.
- operation palette는 current curve에 적용 가능한 human-purpose group만 보여준다.
- operation inspector는 한 operation의 purpose, scope, suggestion source, parameters, preview effect, warnings를 보여준다.
- internal method registry dump를 normal UI에 노출하지 않는다.
- `Commit reviewed output` 대신 `Save processed curves`를 쓴다.

### Yield definition

bare `Yield strength` input을 Fit, 모든 material의 공통 metadata form, Export에 두지 마라.

metal elastoplastic의 `Process > Elastic–plastic separation`에:

- Young’s modulus auto/manual + range
- `Yield definition`: 기본 `Rp0.2 · derived from curve`, 대안 user criterion
- calculated yield value + source + graph marker
- necking point + valid measured range
- manual override value + unit + reason
- curve 범위/elastic sample/necking 관계 검증

을 둔다.

supplier datasheet yield는 evidence이며 curve-derived value를 조용히 대체하지 않는다. hyperelastic·viscoelastic에서는 숨긴다.

### Fit

- 왼쪽은 test/specimen curve set이지 arbitrary settings filter가 아니다.
- 중앙은 response/residual/derivative/extrapolation evidence와 candidate decision table이다.
- 오른쪽은 선택 candidate의 parameters/bounds/range/blend/compatibility/reason/warning acknowledgement다.
- 이 구조는 고정 3열을 복제하기 위한 것이 아니라 evidence set, behavior, assumptions를 동시에 판단하기 위한 것이다. viewport와 stage에 따라 접거나 재배치하라.
- 최저 RMSE/BIC는 `Recommended`이지 `Selected`가 아니다.
- default selection은 `null`.
- 사용자가 row action으로 선택하기 전에는 save/submit 불가.
- reason 입력만으로 selection/review를 만들지 않는다.
- `Single law`와 `Blend`를 분리한다.
- blend identity에 두 law와 ratio를 Processing Output→IR→Neutral→Export까지 보존한다.
- polymer automatic result는 server actual selected term을 canonical identity로 사용한다.
- Fit completed, Validated, Reviewed를 구분한다.

### Validate·Review·Release

- Fit metric을 validation이라고 이름만 바꾸지 않는다.
- saved candidate에 대한 validation plan, reference, coverage, run result가 필요하다.
- unsupported validation은 `Not supported`, policy가 없으면 `Not configured`.
- Save candidate, Submit for review, Request changes, Approve, Release를 분리한다.
- released object를 직접 overwrite하지 않는다.

### Export

- current session exact output만 normal source로 허용한다.
- 전역 Processing Output이나 첫 existing model fallback을 제거한다.
- source가 없으면 기존 card UI를 보여주지 말고 prerequisite checklist만 표시한다.
- Processing Output→IR→Neutral→preflight→native card lineage를 primary work area로 둔다.
- target solver/version/unit, required fields와 mapping state를 보여준다.
- `exact | transformed | approximated | ignored | unsupported`와 영향을 표시한다.
- Preview와 Deliver를 분리한다.
- delivered artifact에 filename, checksum, source revision, target, actor/time을 기록하고 Materials/Activity와 연결한다.
- Export에서 curve alignment/mean controls를 제거하고 source response는 secondary disclosure로만 둔다.

## 코드 정리 지시

`05_CODE_DISPOSITION_AND_REFACTOR_PLAN.md`의 파일별 판정을 따른다.

특히:

- `material-library.tsx`를 query/facet/grid/compare/inspector/detail 단위로 분해한다.
- `common-processing-workbench.tsx`를 shared shell과 stage controller로 분해한다.
- `modeling-session-context.ts`의 nullish merge를 invalidation을 표현할 수 있는 v3 state model로 교체한다.
- `modeling-fit-decision.tsx`는 유지하되 explicit decision table로 개편한다.
- `reference-*workbench.tsx`의 domain adapter는 보존하고 global fallback·normal-path manual legacy form은 격리/제거한다.
- 여러 family export를 담당한다면 `neutral-hyperelastic-export.tsx`의 이름과 책임을 교정한다.
- `app.tsx`의 legacy module hub는 DUI-07~09 기능 이동과 deep-link 검증 후 redirect+삭제한다.
- component migration 뒤 usage 0을 확인한 selector와 누적 CSS만 삭제한다.

backend/API/calculation/revision/provenance/mapping code를 UI가 낡았다는 이유로 삭제하지 마라.

## 구현 순서

기존 DUI 번호를 다시 매기지 말고 `06_DELIVERY_PLAN_AND_ACCEPTANCE.md`의 순서로 진행한다.

1. UXC-00 문서 단일화
2. UXC-01 Materials query/facet/result
3. UXC-02 session state/stage shell
4. UXC-03 Data/Process
5. UXC-04 Fit decision
6. UXC-05 Validate/Review/Release
7. UXC-06 Exact Export
8. DUI-07 Admin
9. DUI-08 Activity
10. DUI-09 Storybook/legacy cleanup
11. UXC-99 final E2E gate

각 slice는 하나의 사용자 outcome과 bounded diff를 가져야 한다. 무관한 backend 재작성이나 새로운 dashboard/AI/admin 기능을 섞지 마라.

## 대표 완료 시나리오

### A. governed material 재사용

```text
Search
→ facet by condition/release/solver compatibility
→ inspect exact revision/evidence
→ compare if needed
→ choose released model and target
→ inspect mapping/native preview
→ deliver traceable card
→ reopen from Materials and Activity
```

### B. test data에서 card까지

```text
Create session
→ inspect raw data
→ confirm axes/units/conditions
→ save dataset
→ prepare curves and physical workup
→ save processed curves
→ run candidates
→ explicitly select single/blend
→ save candidate
→ validate
→ review and release
→ preview target card
→ deliver artifact
```

### C. invalidation과 복구

```text
correct a unit mapping
→ see all downstream stale
→ recompute
→ retry a failed candidate without losing plot/input state
→ ensure stale or other-material output never appears in Export
```

세 시나리오가 실제 state와 data로 끝나지 않으면 완료가 아니다.

## 검증

각 PR마다:

- unit/domain reducer/query tests
- API/schema tests
- component states
- integration/E2E
- keyboard/focus/accessibility
- 1366×768, 1440×900, 1920×1080
- before/after screenshot
- exact source SHA in screenshot manifest
- current docs와 backlog
- dead import/route/selector `rg`

를 실행한다.

최소 회귀:

- explicit candidate selection 전 save/submit 불가
- recommendation change가 selection을 바꾸지 않음
- blend identity 일치
- polymer actual term identity 일치
- upstream 변경 시 all downstream invalidated
- current exact source 없으면 Export artifact UI 없음
- 다른 material output 사용 불가
- 10,000-material fixture에서 server facet/count/result 일치
- non-metal에 Yield facet 없음
- route/stage 이동 후 query/filter/selection/zoom/visibility 복원
- 실제 event 없이 Reviewed/Validated/Released/Delivered 문구 없음

## 삭제와 중단 규칙

삭제는 기능 이동, ref/route/test/CSS usage 0, deep-link redirect, regression evidence가 있을 때만 한다.

다음 contract가 없으면 fake UI를 만들지 말고 gap을 backlog에 기록한다.

- condition-aware property facet
- actual candidate result identity
- safe session clear/invalidation
- review/release policy
- production solver/version mapping
- validation threshold/reference

지원 가능한 수직 slice는 계속 완료하되, unsupported 범위를 명확히 표시한다.

## 최종 산출물

- 기존 문서 트리에 통합된 권위·reference·current 문서
- 중복·stale prompt/spec 제거
- corrected Materials/Modeling/Activity UX
- 안전하게 분해된 component/state code
- 실제 event와 일치하는 status language
- tests, screenshots, evidence, updated manifest
- 삭제한 code/doc와 보존한 compatibility route 목록
- 남은 domain policy·API gap 목록

최종 통합 PR에는
`docs/_incoming/2026-07-24-organic-ux-update/`를 남기지 마라. 통합된 기존
문서와 코드가 유일한 결과여야 한다.

---
