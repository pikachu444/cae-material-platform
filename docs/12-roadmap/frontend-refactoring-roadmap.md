# 프론트엔드 아키텍처 및 UI 체계 재정비 로드맵

상태: active program plan
상위 이슈: [#249 프론트엔드 아키텍처 및 UI 체계 재정비](https://github.com/pikachu444/cae-material-platform/issues/249)
분석 기준선: `main@3e642e8`
방식: 전면 재작성·전면 재디자인 없이 점진적으로 개선

## 1. 왜 지금 정비하는가

현재 제품은 backend contract, exact revision, provenance와 검증 방식이 비교적 명확하다. 프론트엔드도
Materials 조회와 `Data | Process | Fit | Export` 기능은 동작하지만, 기능을 화면 단위로 누적하면서
다음 문제가 커질 위험이 있다.

- route, API, 상태 전이, domain transformation과 JSX가 큰 파일에 함께 존재한다.
- `api.ts`, `types.ts`와 global CSS에 여러 feature 책임이 모인다.
- helper copy, card, eyebrow, chip, 색상과 bold가 화면마다 다른 의미로 사용될 수 있다.
- 고해상도에서 실제 정보량보다 plot이나 빈 영역만 커질 수 있다.
- 새 기능을 작은 diff로 넣는 과정에서 기존 hotspot이 계속 커질 수 있다.

이 프로그램의 목적은 코드를 보기 좋게 나누는 것이 아니다. 사용자가 가장 자주 수행하는 다음 흐름을
더 자연스럽고 안전하게 유지할 수 있는 구조를 만드는 것이다.

```text
Materials에서 필요한 결과를 검색·검토·다운로드

또는

Material/Test Data 선택
→ Data → Process → Fit → 모델 선택·저장 → Export
→ 생성 결과를 Materials에서 다시 조회·다운로드
```

## 2. 유지할 것과 바꿀 것

유지한다.

- 현재 navigation과 application shell
- Materials explorer/result/datasheet 구조
- Modeling의 compact rail과 dominant persistent graph
- exact revision, invalidation, recovery와 backend contract
- 기존 density/token과 다섯 viewport 검증 체계
- 승인된 route별 시각 target

바꾼다.

- 기능과 코드 책임의 소유권
- 큰 component의 state/API/render 혼재
- feature 간 import와 global CSS 누적 방식
- 의미 없는 helper copy, card, eyebrow, chip, 임의 색·굵기
- wide-screen에서 정보를 배치하는 기준
- Codex와 다른 agent가 작업 전 확인하는 규칙

## 3. 작업 원칙

- production behavior를 characterization한 뒤 구조를 옮긴다.
- 구조 분리와 broad visual normalization은 별도 PR로 한다.
- 기존 debt를 한 번에 fail시키지 않고 baseline을 만든 뒤 새 위반부터 막는다.
- 숫자만 보고 파일을 쪼개지 않는다.
- feature 개발을 전면 중단하지 않는다. 다만 등록된 hotspot에 새 책임을 추가하는 frontend-heavy
  작업은 extraction plan 없이 진행하지 않는다.
- backend-only backlog는 기존 순서를 유지할 수 있다. #249의 각 구현 단계는 별도 bounded issue와
  제품 소유자 우선순위 결정을 필요로 한다.

## 4. 단계

### FE-00 — 문서와 agent 계약 통합

이번 단계다.

산출물:

- 프론트엔드 UI 원칙
- 프론트엔드 아키텍처
- 이 로드맵
- frontend change review playbook
- `apps/web/AGENTS.md`
- project-local frontend architecture skill
- root `AGENTS.md`, 기존 desktop UI skill과 문서 포털의 최소 routing 보강

완료 조건:

- production React/CSS를 변경하지 않는다.
- 기존 user flow/UI spec/visual matrix를 중복하거나 폐기하지 않는다.
- Codex가 frontend 작업 전 읽을 경로와 stop condition을 알 수 있다.

### FE-01 — 악화 방지 guard

- feature deep import와 cycle 감시
- 등록 hotspot의 신규 책임·성장 감시
- legacy global CSS에 신규 feature selector 추가 감시
- raw color, arbitrary font weight, generic card/eyebrow/non-status chip의 신규 사용 감시
- route 전용 4K override 감시

기존 debt는 warning baseline으로 시작한다. 합의 없이 저장소 전체를 실패시키지 않는다.

### FE-02 — 공통 semantic UI 기반

- typography role과 neutral metadata/status role
- consequence/block/recovery/engineering-condition copy pattern
- flat pane/surface primitive
- plot useful-bound pattern
- 승인 패턴과 anti-pattern의 작은 예제 및 test

route를 다시 디자인하지 않는다.

구현 계약:

- shared owner는 `apps/web/src/design`이며 의존 방향은 `app -> features -> shared`를 유지한다.
- `SemanticText`는 `workspaceTitle | sectionHeading | label | value | metadata | importantResult`를
  제공한다.
- `SemanticStatus`는 실제 `success | warning | danger`만 허용하며 보이는 label을 요구한다.
- `WorkbenchMessage`는 `loading | empty | blocked | error | recovery | engineeringCondition`을 제공하고,
  recovery에는 keyboard로 도달 가능한 action을 요구한다.
- `EngineeringPane`과 `EngineeringSection`은 접근 가능한 flat grouping을 제공한다.
- `EngineeringPlotRegion`은 필수 plot과 실제 데이터·label이 함께 있는 선택적 companion만 렌더링한다.
- plot useful bound는 공통 픽셀 상한이 아니라 각 plot family의 승인된 feature-owned CSS/token이
  소유한다.
- `Foundation/SemanticUI` Storybook 예제는 synthetic non-production 데이터만 사용하며 제품 route에
  연결하지 않는다.

FE-02는 기존 `ux-meta`, `ux-kicker`, `ux-notice`, `eyebrow`, `status-chip`, `workbench-card` 소비자를
일괄 migration하지 않는다. 남은 Modeling route migration은 #260, Materials·Administration은 #262,
제품 전체 잔여 검증은 #264가 소유한다. 다음 독립 프로그램 단위는 #258이며 FE-02에서 시작하지
않는다.

### FE-03 — Modeling 동작 특성화

- `Data | Process | Fit | Export` primary journey
- Materials에서 넘겨받은 exact context
- selection, revision, persistence, restore와 invalidation
- retry, blocked와 recovery
- 주요 API call과 DOM/interaction behavior

현재 동작을 test와 responsibility map으로 고정한다. broad visual change는 하지 않는다.
현재 판정, fallback 목록, 책임 지도와 회귀 anchor는
[`issue-258-modeling-characterization.md`](https://github.com/pikachu444/cae-material-platform/issues/258)에 기록한다.

### FE-04 — Modeling 구조 분리

- pure registry/default/transformation
- controller/reducer와 async orchestration
- stage/region UI
- feature-owned API/model
- bounded compatibility export

목표는 `common-processing-workbench.tsx`가 composition 중심이 되도록 책임을 이동하는 것이다.

### FE-05 — Modeling 시각 문법 정규화

- 불필요한 helper copy 제거 또는 이동
- generic card/eyebrow/non-status chip 정리
- typography와 semantic color 통일
- plot의 유용한 크기 범위와 2560/3840 composition 개선

다섯 viewport 원본과 1920/2560/3840 semantic review를 수행한다. 4K는 plot 확대만으로 통과하지 않는다.

### FE-06 — CSS 소유권 migration

- shared shell/token/primitive와 feature style의 소유권 분리
- Modeling, Materials, Administration selector를 bounded unit으로 이동
- zero-consumer 확인 뒤 legacy selector 제거
- cascade와 specificity 감소

### FE-07 — Materials와 Administration 정비

- Materials의 search/browse/selection/detail/card handoff 보존
- Administration의 object/task 중심 구조 보존
- hotspot의 controller/UI/API 책임 분리
- 동일 semantic UI 원칙 적용

### FE-08 — App, API와 type modularization

- **FE-08A — App와 route composition**: `app.tsx`에서 typed route registry/parser, browser
  navigation·popstate, lazy route/page composition과 product-session boundary를 app-owned module로
  분리한다. `/materials` canonical flow와 exact Record/Card/Material Model/Neutral/Card revision,
  Materials↔Modeling handoff, Modeling stage query, Activity·Administration 및 `/catalog/*`,
  `/datasets/*`, `/jobs-reviews`, `/access` compatibility deep link를 같은 URL/query 계약으로
  유지한다. 남은 root page import는 소비 route와 제거 조건을 기록한다.
- **FE-08B — API ownership**: shared transport/auth/error normalization과 resource-owned API를
  분리하고 기존 `api.ts`에는 bounded compatibility만 남긴다.
- **FE-08C — Type/model ownership**: transport DTO, feature-owned model/type과 최소 shared primitive를
  분리하고 기존 `types.ts` compatibility를 zero-consumer 증거 뒤 제거한다.

각 단위는 별도 publication boundary를 가지며 FE-08A 뒤 다음 단위는 FE-08B다. FE-08A 구조
이동은 copy, DOM hierarchy, CSS, layout 또는 public payload를 바꾸지 않으며, unsupported exact-card
kind와 unknown path는 기존 Materials fallback을 유지한다. FE-08B·FE-08C를 앞당기거나 세 단위를
repository-wide rewrite로 합치지 않는다.

repository-wide rewrite를 하지 않는다.

### #331 — Legacy UI/CSS 최종 이관 및 제거

- #261의 67행/65그룹 inventory를 seed로 latest main의 consumer와 owner를 다시 감사
- 실제 사용 중인 legacy 문법을 semantic UI 또는 정확한 feature/shared owner로 이관
- zero-consumer selector, import와 legacy file 제거
- selector별 tiny task가 아니라 coherent route/family batch로 수행
- 정상 화면 legacy inventory 0과 five-viewport 질적 검토를 #264 전에 완료

### FE-09 — 제품 전체 종료 검증

- 주요 route/state의 behavior와 visual semantics 재검증
- user guide, screenshot manifest, architecture와 delivery 기록 동기화
- 실제 Windows 4K 검증이 남아 있으면 #223 계약으로 완료
- 남은 debt와 의도적 예외 기록

## 5. 권장 순서

```text
FE-00 → FE-01 → FE-02
                    │
                    ▼
            FE-03 → FE-04 → FE-05
                                │
                                ▼
                      FE-06 → FE-07 → FE-08 → #331 → FE-09
```

FE-01과 FE-02는 diff가 독립적이면 병행할 수 있다. FE-03은 FE-00이 병합된 뒤 시작한다. FE-05는
FE-04의 behavior preservation이 확인되기 전에 시작하지 않는다. #331은 FE-08이 실제 owner와
compatibility 경계를 확정한 뒤 시작하고, FE-09(#264) 전에 끝낸다.

## 6. 사용자에게 보이는 변화

이 작업이 진행되면 사용자는 다음을 기대할 수 있다.

- Material을 찾고 상세·카드·Modeling으로 이동할 때 문맥을 덜 잃는다.
- Data, Process, Fit과 Export가 같은 프로그램 안의 연속 작업으로 느껴진다.
- 중요 데이터와 동작이 먼저 보이고 일반 설명문은 줄어든다.
- 색상, bold, chip과 panel이 같은 의미로 사용된다.
- FHD에서 충분한 정보 밀도를 유지하고, 넓은 화면에서는 실제 비교·evidence 용량이 늘어난다.
- 새 기능을 넣을 때 기존 대형 파일 전체를 건드릴 가능성이 줄어든다.

## 7. 각 단계 보고 항목

- 정확한 owned scope
- primary user journey
- 보존한 API/domain/state/recovery contract
- hotspot 책임의 전후 비교
- test와 viewport evidence
- compatibility와 제거 조건
- 남은 debt와 다음 bounded unit

상위 #249는 프로그램 전체를 추적한다. 실제 코드 변경은 단계마다 별도 issue/PR로 진행하며, 제품
소유자의 명시적 지시 없이 merge하지 않는다.
