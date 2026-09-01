# 프론트엔드 아키텍처

상태: authoritative frontend architecture contract
범위: `apps/web`
이행 방식: 기존 동작을 보존하는 점진적 migration
관련 이슈: [#249 프론트엔드 아키텍처 및 UI 체계 재정비](https://github.com/pikachu444/cae-material-platform/issues/249)

## 1. 목적

프론트엔드는 사용자의 작업 흐름과 코드의 책임 경계가 같은 방향을 가져야 한다. 이 문서의 목적은
다음과 같다.

- Material 조회·재사용과 Test Data→Model→Solver Card 제작 흐름을 자연스럽게 유지한다.
- route, API access, 상태 전이, domain transformation, persistence와 rendering을 구분한다.
- 기능 소유권과 의존 방향을 Codex 및 다른 에이전트가 저장소만 보고 판단하게 한다.
- 이미 커진 파일에 새 책임이 계속 누적되는 것을 막는다.
- 전면 재작성 없이 feature 단위로 옮긴다.

## 2. 하지 않는 일

이 계약만을 이유로 다음을 수행하지 않는다.

- 새로운 UI framework, routing library 또는 state library 도입
- application shell, density, token과 승인된 route topology 교체
- 백엔드 API나 domain 계약 재설계
- line count만을 기준으로 한 기계적 파일 분할
- repository 전체 import를 한 번에 바꾸는 rewrite
- 구조 변경과 대규모 시각 변경을 한 PR에 혼합

새 dependency가 필요하면 별도 이슈에서 현재 도구로 해결할 수 없는 capability gap과 영향을 증명한다.

## 3. 핵심 사용자 흐름을 아키텍처 경계로 사용

### 3.1 Materials에서 Modeling으로

Materials가 exact Material/Record, revision, condition, State 또는 Test Data를 선택해 Modeling을 여는
경우, app-level orchestration은 그 문맥을 명시적인 URL/session contract로 전달한다. Modeling은
`latest`, 첫 번째 목록 항목 또는 다른 session output으로 대체하지 않는다.

### 3.2 Data에서 Export까지

Modeling feature는 `Data | Process | Fit | Export`의 session, invalidation, restore와 recovery를
소유한다. 각 stage UI가 다른 stage의 private state를 직접 수정하지 않는다. 입력 변경은 reducer 또는
controller의 named transition을 통해 downstream current pointer를 clear/stale 처리한다. immutable
revision과 evidence는 유지한다.

### 3.3 Solver Card에서 Materials로

생성·저장된 solver card는 exact model/revision lineage를 유지하며 Materials의 CAE Cards와 workflow에서
다시 찾을 수 있어야 한다. UI가 임시 browser state만으로 완료를 표현하지 않는다.

## 4. 현재 debt hotspot

다음 파일은 migration 전까지 등록된 hotspot으로 관리한다.

- `apps/web/src/common-processing-workbench.tsx`
- `apps/web/src/material-library.tsx`
- `apps/web/src/app.tsx`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `apps/web/src/design/layout.css`

버그 수정과 bounded compatibility 변경은 가능하다. 그러나 새 feature 책임을 추가하려면 해당 이슈에
현재 책임, 추가하려는 책임, 추출 계획 또는 명시적 예외를 기록한다.

line count는 품질 점수가 아니라 검토 trigger다. 대략 400 component lines부터 책임 목록을 요구하고,
600 lines 이상에서 새로운 책임을 추가하려면 extraction plan이 필요하다. routing, API access, domain
transformation, state machine, persistence, rendering 중 세 가지 이상을 한 파일이 소유하면 크기와 무관하게
architecture review를 수행한다.

## 5. 목표 의존 방향

```text
app -> features -> shared
```

- `app`: route, permission boundary, shell과 feature composition
- `features`: Materials, Modeling, Activity, Administration 등 사용자 기능
- `shared`: token, generic UI, layout, API transport와 순수 utility

규칙은 다음과 같다.

1. `shared`는 feature 또는 app을 import하지 않는다.
2. feature는 다른 feature의 내부 파일을 deep import하지 않는다.
3. cross-feature 사용은 상대 feature의 public entry point 또는 app orchestration을 통한다.
4. route/page는 feature와 shell을 조합하고 domain calculation을 소유하지 않는다.
5. feature 간 circular dependency는 허용하지 않는다.
6. 임시 compatibility module은 제거 이슈와 exit condition을 가진다.

## 6. 목표 source 구조

다음은 최종 디렉터리를 한 번에 만드는 지시가 아니라 소유권 방향이다. 실제 migration에서는 현재
코드의 응집도를 확인한 뒤 필요한 경계만 만든다.

```text
apps/web/src/
  app/
    routes/
    shell/

  features/
    materials/
      api/
      model/
      ui/
      routes/
      index.ts
    modeling/
      api/
      model/
      ui/
        stages/
          data/
          process/
          fit/
          export/
      routes/
      index.ts
    activity/
    administration/

  shared/
    api/
    ui/
    layout/
    tokens/
    lib/

  compat/
```

빈 wrapper 파일을 만들거나 기존 결합을 여러 파일에 그대로 복제하는 것은 migration이 아니다.

## 7. 책임 경계

### 7.1 App와 route

소유:

- URL과 route parameter
- permission과 route-level loading/error boundary
- feature composition과 application shell 연결
- Materials↔Modeling 같은 cross-feature handoff

소유하지 않음:

- domain calculation
- 대규모 request/response mapping
- 여러 독립 async workflow
- stage별 세부 UI

### 7.2 Workspace layout

소유:

- navigator, workspace, contextual detail, toolbar와 local scroll topology
- pane sizing, resize와 공통 responsive behavior
- 접근 가능한 region semantics

feature data loading과 domain decision은 소유하지 않는다.

### 7.3 Controller hook 또는 reducer

소유:

- named transition
- async command orchestration
- dirty, stale, blocked, invalidated state
- restore, retry와 recovery
- UI에 필요한 view model derivation

visual styling과 generic layout은 소유하지 않는다.

### 7.4 Feature UI

소유:

- 해당 기능의 field, table, plot, action과 state presentation
- keyboard/focus behavior
- loading, empty, blocked, stale, error와 recovery 표시

global routing이나 다른 feature의 private state를 소유하지 않는다.

### 7.5 API와 model

소유:

- resource-specific API call
- request/response mapping
- 현재 계약에 필요한 runtime validation
- feature-owned type과 pure transformation

UI state를 저장하거나 존재하지 않는 fallback record를 만들지 않는다.

### 7.6 Shared primitive

generic interaction, accessibility와 token 기반 appearance만 소유한다. feature copy, domain default와
route 전용 selector를 포함하지 않는다.

## 8. 상태와 복구 원칙

1. URL과 server state를 source of truth로 유지한다.
2. 명시적 editing lifecycle 없이 server state의 두 번째 client 사본을 만들지 않는다.
3. named transition, invalidation, retry 또는 restore가 있으면 reducer/controller boundary를 둔다.
4. default, registry, mapping과 calculation-independent helper는 render component 밖으로 옮긴다.
5. loading, empty, blocked, stale, error와 recovery를 명시적으로 표현한다.
6. 실패 시 exact source, 선택, draft와 마지막 유효 graph를 가능한 범위에서 보존한다.
7. 한 feature의 prop 전달을 줄이기 위한 목적으로 global store를 도입하지 않는다.

## 9. API와 type migration

현재 `api.ts`와 `types.ts`는 한 번에 제거하지 않는다.

1. feature-owned API/model module을 만든다.
2. 기존 consumer가 필요하면 `api.ts` 또는 `types.ts`에서 bounded compatibility re-export를 제공한다.
3. consumer를 작은 PR 단위로 이동한다.
4. repository search로 zero consumer를 확인한 뒤 re-export를 제거한다.
5. backend contract의 이름과 의미는 유지한다.

## 10. CSS 소유권

공통 design layer는 token, density, typography role, generic primitive, application shell, split pane,
generic table/plot frame을 소유할 수 있다.

feature layer는 feature-specific arrangement, stage grid, local state variant와 route responsive
composition을 소유한다.

- 폐기된 root `src/styles.css`를 다시 만들지 않으며, 새 feature selector는
  `src/design/layout.css`가 아니라 feature-owned stylesheet에 둔다.
- legacy selector를 수정할 때 bounded하고 안전하면 owned style로 이동한다.
- token이 있는데 raw color, arbitrary font weight와 one-off spacing을 추가하지 않는다.
- route 전용 4K media query를 만들지 않는다.
- global selector 변경은 영향받는 모든 route를 명시하고 관련 시각 gate를 수행한다.
- `!important`, deep descendant selector와 `:has`는 소유권·필요성·제거 조건을 기록한다.

## 11. 점진적 migration 방법

hotspot 하나를 옮길 때 다음 순서를 따른다.

1. 현재 책임, dependency, route, state와 test를 기록한다.
2. 실제 primary journey와 recovery를 characterization test로 고정한다.
3. pure function과 registry를 추출한다.
4. controller hook 또는 reducer를 추출한다.
5. 응집된 stage 또는 region UI를 추출한다.
6. bounded compatibility entry point와 필요한 DOM/class contract를 유지한다.
7. behavior, build, interaction과 viewport geometry를 검증한다.
8. 불필요한 helper copy, card, eyebrow, chip, 색상과 굵기는 별도 semantic visual PR에서 정리한다.
9. zero-consumer evidence 뒤 compatibility를 제거한다.

## 12. 첫 migration 대상: Modeling

첫 대상은 `common-processing-workbench.tsx`와 연결된 Modeling flow다. 다음 이름은 책임 후보일 뿐,
그대로 빈 파일을 만들라는 지시가 아니다.

- session/context controller
- Data source와 mapping
- Process preview/commit/recovery
- Fit run/restore/selection
- Export preflight/delivery
- method registry와 pure transformation
- stage-owned UI region
- saved output와 replicate analysis disclosure

먼저 `Data | Process | Fit | Export`의 실제 동작, exact revision, invalidation, persistence와 recovery를
고정한다. 구조 분리 PR에서는 broad visual normalization을 하지 않는다.

## 13. 검증 계약

구조 리팩터링은 다음을 보존한다.

- request/response와 backend contract
- exact identity와 revision
- Materials↔Modeling handoff와 selection continuity
- upstream invalidation
- session restore
- loading, empty, blocked, stale, error, retry와 recovery
- keyboard, focus와 local scroll
- route와 screenshot identity

동작 test를 snapshot으로 대체하지 않는다. 시각 변경이 승인되기 전에 golden을 갱신하지 않는다.

## 14. 완료 조건

하나의 architecture unit은 다음을 만족해야 한다.

- 소유권과 dependency 방향이 명확하다.
- 이동한 책임이 기존 hotspot에 중복으로 남지 않는다.
- compatibility와 제거 조건이 기록된다.
- 관련 test와 production build가 통과한다.
- 필요한 interaction/viewport evidence가 통과한다.
- 사용자 문구와 시각 역할이 [프론트엔드 UI 원칙](../product/frontend-ui-principles.md)을 따른다.
- 남은 debt를 기록하며 전체 프론트가 완료됐다고 과장하지 않는다.

## 15. 예외

예외는 책임, 목표 구조가 부적합한 이유, 영향 파일, test/evidence, 제품 소유자 결정과 제거 조건을
기록한다. “smallest diff” 또는 “기존 파일에도 비슷한 코드가 있다”는 충분한 근거가 아니다.
