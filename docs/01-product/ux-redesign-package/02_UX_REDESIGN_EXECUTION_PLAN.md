# UX Redesign Execution Plan

## 1. 실행 원칙

- backend domain, immutable revision, provenance, Neutral IR와 solver mapping 계약은 유지한다.
- 일반 사용자 UI에서 내부 artifact를 숨기되 삭제하지 않는다.
- 새 기능을 추가하기 전에 search/download task를 완성한다.
- 큰 한 번의 rewrite 대신 검증 가능한 PR 단위로 진행한다.
- `테스트 통과`와 `사용하기 좋은 제품`을 같은 의미로 취급하지 않는다.

## 2. Phase 0 — Baseline and Audit

목적: 현재 문제를 재현 가능한 증거로 고정한다.

작업:

1. clean demo 실행
2. 주요 route current screenshot 캡처
3. 사용자 task 5개 baseline 측정
4. route/component/API inventory
5. UI terminology inventory
6. CSS token/duplication audit
7. usability issue severity 분류

산출물:

```text
docs/15-demo/evidence/ux-current-baseline.md
docs/15-demo/images/ux-baseline/*.png
docs/01-product/ux-route-inventory.md
docs/01-product/ux-terminology-inventory.md
docs/01-product/ux-style-audit.md
```

## 3. Phase 1 — Product Direction Reset

목적: 기능 목록 중심 구현이 반복되지 않도록 authoritative documents를 수정한다.

수정 대상:

- `AGENTS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`
- `docs/01-product/product-vision.md`
- `docs/01-product/product-experience-spec.md`
- `docs/01-product/gui-functional-parity-plan.md`
- `docs/00-research/product-capability-map.md`
- `docs/13-delivery/backlog.md`

추가 대상:

```text
adr/0035-search-first-product-surface.md
docs/01-product/ux-redesign-goal.md
docs/01-product/ux-information-architecture.md
docs/01-product/ux-visual-system.md
```

`AGENTS.md`에 추가할 UX invariant:

- Materials search is the default product entry.
- Normal users complete search-to-download without internal IDs or governance terminology.
- One page has one dominant user job.
- Internal objects remain available through Evidence/Advanced, not the default path.
- Do not add a new panel/card when an existing area can express the task.
- Search/download usability has priority over Recipe, Batch, Governance and Administration polish.
- Do not claim UX completion without live task evidence and current screenshots.
- Preserve engine contracts; simplify the facade.

## 4. Phase 2 — Design System Reset

새 foundation:

```text
apps/web/src/design/
  tokens.css
  typography.css
  primitives.css
  layout.css
```

권장 primitives:

- AppShell
- TopNavigation
- SearchBar
- FilterPanel
- DataTable
- DetailHeader
- Tabs
- PropertyList
- CurvePanel
- StatusLabel
- PrimaryAction
- EmptyState
- ErrorState
- AdvancedDisclosure

규칙:

- accent color 1개
- surface hierarchy 3단계 이하
- radius 2종 이하
- shadow 2종 이하
- spacing scale 4/8 기반
- body 14~16px
- metadata 12~13px
- primary button variant 1개
- badge는 상태에만 사용
- decorative gradient 제거
- nested card 제거
- border보다 whitespace와 section divider 우선

새 화면은 새 token만 사용한다. 기존 화면은 동시에 전부 변환하지 않고, 새 Materials 경로가 완료되면 dead CSS와 legacy component를 제거한다.

## 5. Phase 3 — Search-first Material Library

라우트:

```text
/                 → /materials
/materials        → search/list
/materials/:id    → material detail
/materials/:id/cards/:cardId → preview/download
```

필수 기능:

- global quick search
- material family filter
- maker/source filter
- key property range
- solver availability
- validation/release status
- sortable result table
- optional row quick preview
- saved URL query state
- keyboard navigation
- loading/empty/error states

P0에서 제외:

- complex schema administration
- full workflow graph
- batch operation
- revision compare
- arbitrary record link authoring

이 기능들은 backend에서 유지하고 Advanced/Admin route에서 제공한다.

Acceptance slice:

```text
DP780 검색
→ 결과 행 선택
→ Overview 확인
→ CAE Cards
→ OpenRadioss .rad 다운로드
```

## 6. Phase 4 — Material Detail and Card Delivery

구조:

```text
Header
  name / grade / maker / status
  primary solver-card action

Tabs
  Overview
  Properties
  Curves
  CAE Cards
  Evidence
```

CAE Cards tab:

- solver
- solver version
- law/model
- unit system
- availability
- exact/transformed/approximated/unsupported summary
- preview
- download
- regenerate/create path

Evidence에서만 제공:

- exact source revisions
- provenance graph
- mapping report
- checksums
- audit trail

## 7. Phase 5 — Modeling Simplification

기존 calculation component를 폐기하지 않고 4단계 shell로 감싼다.

### Data

- local file 또는 existing Material/Test Data 선택
- test type auto-detection
- channel mapping table
- unit confirmation
- curve preview

### Process

- curve list와 include/exclude
- crop/range
- smoothing/resample
- replicate mean/band
- persistent graph

### Fit

- model candidates
- response/residual view
- parameter summary
- extrapolation domain
- selection reason

### Export

- selected model summary
- target solver
- mapping summary
- card preview/download
- save to Material Library

Advanced drawer:

- Mapping Profile
- Recipe Library
- Batch Monitor
- exact revisions
- JSON definition
- diagnostic IDs

## 8. Phase 6 — Legacy Consolidation

- old Dashboard module inventory 제거
- `/database`를 advanced explorer 또는 admin tool로 재정의
- dedicated Test Data JSON editor를 Advanced import로 이동
- duplicate modeling routes 정리
- unused component와 CSS 제거
- route redirect와 backward-compatible links 추가
- user guide를 Materials-first로 재작성

## 9. PR 분할

### PR 1 — UX evidence and direction reset

- baseline captures
- research document
- goal/IA/visual system
- ADR
- AGENTS/product docs/backlog update

### PR 2 — Design system and application shell

- tokens/primitives
- new top navigation
- route structure

### PR 3 — Material search

- search/filter/table
- result state
- detail navigation
- Playwright baseline task

### PR 4 — Material detail and card download

- five tabs
- card preview/download
- Evidence disclosure
- search-to-download acceptance

### PR 5 — Modeling four-stage shell

- Data/Process/Fit/Export
- legacy engine adaptation
- Advanced disclosure
- upload-to-card acceptance

### PR 6 — Cleanup and final acceptance

- legacy route/component/CSS removal
- docs/user guide
- accessibility
- visual regression
- final clean demo evidence

## 10. 테스트 전략

### Unit/component

- search query state
- filter combination
- result sorting
- card availability label
- advanced disclosure
- stage state persistence
- error recovery

### Integration

- real API-backed material search
- exact detail/property/curve/card retrieval
- solver card preview/download
- file conversion/import
- modeling session handoff

### Playwright task tests

1. search and download
2. filter by solver
3. inspect curves
4. upload and map
5. fit and export
6. open Evidence without contaminating normal path

### Visual regression

필수 viewport:

- 1440×900
- 1366×768

### Accessibility

- keyboard-only search/result/detail/download
- visible focus
- label/description association
- semantic table
- contrast
- target size
- no color-only state
- reduced-motion behavior

## 11. 위험과 통제

### 새 shell 위에 기존 복잡성을 다시 노출

normal path와 Advanced path의 content contract를 문서화하고 PR마다 기본 viewport screenshot을 검사한다.

### 기능 손실 우려로 모든 내용을 남김

기능 삭제와 기본 노출 제거를 구분한다. Evidence/Advanced에서 접근 가능하면 normal path에서 제거한다.

### CSS만 바꾸고 완료

task time, click count와 terminology count를 acceptance에 포함한다.

### 한 PR에서 대규모 rewrite

각 PR은 하나의 사용자 task를 완료하고 독립적으로 검증한다.
