# 프론트엔드 변경 검토 절차

상태: authoritative repository procedure
범위: `apps/web`의 구조 변경과 사용자에게 보이는 React/CSS 변경

## 1. 변경을 먼저 분류한다

해당하는 항목을 모두 기록한다.

- feature behavior
- structural refactor
- semantic visual change
- defect correction
- shared primitive/token
- application shell/layout
- documentation/evidence only

structural refactor와 broad semantic visual change는 원칙적으로 별도 PR이다.

## 2. 작업 전 읽기

1. 정확한 issue와 승인된 작업 단위
2. root `AGENTS.md`와 `apps/web/AGENTS.md`
3. [프론트엔드 UI 원칙](../01-product/frontend-ui-principles.md)
4. [프론트엔드 아키텍처](../05-architecture/frontend-architecture.md)
5. 정확한 route/product contract
6. 적용되는 [시각 수용 매트릭스](../01-product/visual-acceptance-matrix.md) 절과 승인 reference
7. 대상 component, state/controller, API, style와 test

그 뒤 project-local `material-platform-frontend-architecture` skill로 preflight packet을 만든다.

## 3. Preflight packet

```text
Primary user journey:
Owned feature:
Change classes:
Current owner files:
Current responsibilities:
Target owner files and dependency direction:
Registered hotspot impact:
Preserved API/domain/URL/revision contracts:
Preserved state transitions and recovery:
Structural movement:
Semantic visual movement:
Helper/color/weight/chip/surface/wide-screen rationale:
Compatibility and removal condition:
Tests:
Viewport/interaction evidence:
Forbidden shortcuts:
Owner decisions required:
```

파일 목록만 있는 계획은 충분하지 않다.

## 4. Architecture review

다음을 확인한다.

- dependency 방향이 `app -> features -> shared`를 따른다.
- feature가 다른 feature의 내부를 deep import하지 않는다.
- circular dependency가 없다.
- route/page가 composition 중심이다.
- 큰 render block 안에 여러 async workflow와 recovery가 추가되지 않는다.
- feature API/model/controller/UI 소유자가 명확하다.
- 등록 hotspot에 extraction plan 없이 새 책임을 넣지 않는다.
- legacy global CSS에 새 feature selector를 추가하지 않는다.
- compatibility code에 제거 이슈와 exit condition이 있다.
- Materials↔Modeling과 Data→Process→Fit→Export의 exact-context continuity를 보존한다.

같은 책임을 여러 wrapper 파일에 나눠 놓는 기계적 분할은 거절한다.

## 5. UI semantics review

새로 보이는 각 요소에 대해 다음 역할을 설명한다.

- color
- weight
- badge/chip
- helper copy
- border/card surface
- illustration/diagram
- wide-screen space

“더 명확해 보인다”, “빈 공간을 채운다”, “다른 card와 맞춘다”, “smallest diff다”만으로는 승인하지
않는다.

확인 사항:

- 일반 heading과 label은 neutral role이다.
- accent는 action, selection, focus와 link에 한정한다.
- status color/chip은 실제 상태만 표현한다.
- helper copy는 consequence, block, recovery 또는 engineering interpretation을 설명한다.
- 정상 작업공간에 장식용 illustration이 없다.
- plot은 engineering usefulness가 증가하는 범위까지만 커진다.
- 넓은 공간은 실제 contract-backed companion data 또는 균형 잡힌 여백을 사용한다.

## 6. Behavior와 접근성

- exact identity와 revision
- Materials 검색·Tree·selection continuity
- Modeling session과 stage continuity
- upstream invalidation과 stale state
- restore, retry와 recovery
- loading, empty, blocked와 error
- keyboard operation과 visible focus
- local scroll ownership
- page-level horizontal overflow 없음
- 새 console error 없음

## 7. Evidence

### 구조만 변경하는 경우

- affected unit/component test
- production build
- primary journey와 recovery 실행
- DOM/layout이 바뀔 수 있으면 viewport geometry 확인
- 책임 경계 before/after map

### 사용자에게 보이는 경우

- 1366×768, 1440×900, 1920×1080, 2560×1440, 3840×2160의 live before/after
- original-resolution full screen과 요구되는 100% crop
- interaction, keyboard와 recovery evidence
- 1920/2560/3840 semantic composition 판정
- 필요한 경우 실제 4K physical-readability 판정

contact sheet만 보고 승인하지 않는다. test pass는 ownership, semantic hierarchy 또는 visual composition
failure를 덮지 않는다.

## 8. Review disposition

- `APPROVED`
- `APPROVED_WITH_RECORDED_FOLLOWUP`: authority가 명시적으로 허용한 잔여 항목만
- `CHANGES_REQUIRED`
- `BLOCKED_BY_PRODUCT_DECISION`
- `BLOCKED_BY_INVALID_EVIDENCE`

## 9. PR 본문 형식

```text
Scope:
Change class:
Primary user journey:
User-visible behavior:
Architecture movement:
Hotspot responsibility before/after:
UI semantic changes:
Contracts preserved:
Tests:
Viewport/interaction evidence:
Physical 4K disposition:
Compatibility/removal issue:
Remaining debt:
Owner decisions required:
```
