# Codex Master Prompt — Search-first UX Redesign

당신은 `pikachu444/cae-material-platform`의 제품 책임자, enterprise UX architect와 React/TypeScript 엔지니어다.

이번 작업은 기능 추가가 아니라 제품 방향과 프론트엔드 정보 구조의 재설계다.

기존 technical progress와 backend/domain/calculation/export engine은 보존한다. 그러나 현재 프론트엔드는 기능이 많다는 이유로 모든 내부 개념을 한꺼번에 노출하여 복잡하고 읽기 어렵다. 기존 T-75~T-93의 엔진 연결과 검증을 폐기하지 말되, 해당 화면이 사용자 경험 완료라는 판단은 재검토한다.

## 제품 우선순위

1. 기존 재료 검색 → 상세 검토 → CAE solver card 다운로드
2. 시험 데이터 업로드 → 처리 → fitting → 새 solver card 생성 → Material Library 저장
3. Recipe, Batch, Governance와 Administration은 위 두 경로를 보조하는 고급 기능

## 반드시 읽을 파일

1. `CODEX_UX_REDESIGN_START.md`
2. `AGENTS.md`
3. `README.md`
4. `IMPLEMENTATION_STATUS.md`
5. `docs/01-product/product-vision.md`
6. `docs/01-product/product-experience-spec.md`
7. `docs/01-product/gui-functional-parity-plan.md`
8. `docs/00-research/official-product-research.md`
9. `docs/00-research/product-capability-map.md`
10. `docs/13-delivery/backlog.md`
11. 이 디렉터리의 `00`~`05` 기획 문서
12. `apps/web/src/app.tsx`
13. `apps/web/src/material-database-explorer.tsx`
14. `apps/web/src/material-modeling-workspace.tsx`
15. `apps/web/src/common-processing-workbench.tsx`
16. `apps/web/src/canonical-test-data-workbench.tsx`
17. `apps/web/src/styles.css`

## 보존할 것

- PostgreSQL schema와 existing domain model
- stable identity와 immutable revision
- original/normalized unit와 quantity semantics
- provenance engine
- Processing/Calibration engine
- Material Model IR와 Neutral Material JSON
- exact/transformed/approximated/unsupported mapping
- unsupported block와 approximation acknowledgement
- native Abaqus/OpenRadioss card
- clean demo seed와 existing reference material journeys
- domain regression tests

## 기본 화면에서 숨길 것

삭제하지 말고 `Evidence`, `Advanced` 또는 `Administration`으로 이동한다.

- UUID와 aggregate ID
- full revision ID
- SHA/content hash
- classification
- change reason
- Mapping Profile JSON
- Recipe lifecycle
- compatibility preflight terminology
- immutable/exact revision 반복 문구
- governance vocabulary
- API/token/tenant/security vocabulary

## 절대 하지 말 것

- 색상, 그림자와 border-radius만 바꾸고 UX 개선이라고 주장하지 않는다.
- 기존 component에 새로운 card/panel을 계속 추가하지 않는다.
- backend를 다시 설계하지 않는다.
- 새 constitutive model, solver, optimizer 또는 importer를 추가하지 않는다.
- Granta/Material Data Center/Material Modeler 화면을 pixel 단위로 복제하지 않는다.
- 테스트 통과만으로 product UX completion이라고 선언하지 않는다.
- 현재 screenshot을 보지 않고 문서 설명만으로 UI를 수정하지 않는다.
- 전체 프론트엔드를 검증 없이 한 번에 rewrite하지 않는다.

## Phase 0 — Current baseline

1. 현재 `main`과 branch 상태를 확인한다.
2. clean demo를 실행한다.
3. 다음 route를 1440×900과 1366×768로 캡처한다.
   - Dashboard
   - Material Database search/result/detail
   - Test Data import
   - Metal / Polymer / Elastomer Modeling
   - Card delivery
   - Recipe/Batch
   - Administration
4. 다음 task를 수행하고 측정한다.
   - DP780 검색 후 Abaqus/OpenRadioss card 다운로드
   - solver filter
   - curve 확인
   - CSV/XLSX import 후 modeling 진입
   - processed result에서 card 생성
5. route/component/API inventory를 작성한다.
6. UI terminology inventory를 작성한다.
7. `styles.css`의 color/font/spacing/radius/shadow/gradient/component 중복을 audit한다.
8. 공식 공개 자료의 interaction principle을 정리한다.

생성할 문서:

```text
docs/15-demo/evidence/ux-current-baseline.md
docs/01-product/ux-route-inventory.md
docs/01-product/ux-terminology-inventory.md
docs/01-product/ux-style-audit.md
docs/00-research/ux-reference-analysis.md
```

Phase 0 분석을 커밋한 뒤 중단하지 말고 후속 구현 단계로 진행한다. 단, baseline과 목표 IA가 일치하지 않는 중대한 불확실성이 있으면 문서에 가정을 명시하고 가장 보수적인 방향으로 진행한다.

## Phase 1 — 문서와 계약 확정

다음을 검색 중심 제품 방향과 일치시키라.

```text
AGENTS.md
README.md
IMPLEMENTATION_STATUS.md
docs/01-product/product-vision.md
docs/01-product/product-experience-spec.md
docs/01-product/gui-functional-parity-plan.md
docs/00-research/product-capability-map.md
docs/13-delivery/backlog.md
adr/0035-search-first-product-surface.md
docs/01-product/ux-redesign-goal.md
docs/01-product/ux-information-architecture.md
docs/01-product/ux-visual-system.md
```

`AGENTS.md`에 다음 UX invariant를 추가한다.

- Materials search is the default product entry.
- Search-to-download must work without internal IDs or governance terminology.
- One page has one dominant user job.
- Internal objects are accessed through Evidence/Advanced.
- Do not add a new panel when an existing region can express the task.
- Search/download usability has priority over Recipe/Batch/Admin polish.
- UX completion requires live task evidence and current screenshots.
- Preserve domain contracts while simplifying the facade.

## Phase 2 — Design system and application shell

새 foundation을 도입한다.

```text
apps/web/src/design/
  tokens.css
  typography.css
  primitives.css
  layout.css
```

요구사항:

- accent color 1개
- neutral surface hierarchy 3단계 이하
- radius 2종 이하
- shadow 2종 이하
- decorative gradient 제거
- nested card 최소화
- whitespace와 divider 중심 section 구분
- body 14px 이상
- metadata 12px 이상
- primary data 16px 이상
- click target 목표 32×32px 이상
- visible focus
- WCAG 2.2 AA contrast
- color-only status 금지
- 한 region의 primary button 1개
- 1440×900 first viewport major region 최대 3개

일반 사용자 navigation:

```text
Materials | Modeling | Activity
```

Administration은 user/settings menu 또는 role-gated route에 둔다.

## Phase 3 — Material Search

`/materials`를 서비스 기본 진입점으로 만든다.

필수 기능:

- quick search
- material family
- maker/source
- key numeric property range
- solver availability
- validation/release status
- sortable semantic data table
- row quick preview 또는 detail navigation
- result count
- loading/empty/error state
- keyboard navigation
- one clear primary action

검색 결과에 최소 다음을 표시한다.

```text
name/grade
family
maker/source
key properties
condition summary
available solvers
status
updated date
```

## Phase 4 — Material Detail and Card Download

탭은 최대 5개다.

```text
Overview | Properties | Curves | CAE Cards | Evidence
```

첫 viewport에 material identity, key properties, applicability, card availability와 primary download action이 보여야 한다.

CAE Cards에서 solver, version, law/model, unit system, mapping 상태, preview와 download를 제공한다.

revision, provenance, mapping report와 checksum은 Evidence에 둔다.

## Phase 5 — Modeling simplification

기존 6단계를 다음 4단계로 재구성한다.

```text
Data | Process | Fit | Export
```

- `Data`: 파일 또는 Library data 선택, 시험 종류, channel/unit mapping
- `Process`: curve 선택, crop, smoothing, resample, 반복시험 통계
- `Fit`: model candidate, response, residual, extrapolation
- `Export`: selected model, solver mapping, card preview/download, Library 저장

기존 calculation engine을 재사용한다. Mapping Profile, Recipe Library, Batch Monitor, exact revision과 JSON definition은 Advanced로 이동한다.

## Phase 6 — Cleanup and verification

- 기존 Dashboard module inventory 제거
- 중복 route와 legacy component 정리
- dead CSS 삭제
- existing deep link redirect/compatibility 유지
- user guide와 screenshot 갱신

필수 수용 시나리오:

### Search-to-download

```text
DP780 검색
→ result 선택
→ OpenRadioss card preview
→ .rad download
```

- 신규 사용자 기준 60초 이내
- primary action 3회 이하
- UUID/SHA 입력 없음

### Upload-to-card

```text
CSV/XLSX upload
→ mapping 확인
→ Process
→ Fit
→ Abaqus/OpenRadioss Export
→ Library에서 다시 검색
```

- top-level 단계 4개
- JSON editor 불필요
- 기존 provenance와 solver mapping contract 유지

## PR 순서

1. evidence/docs/ADR/AGENTS
2. design system/shell
3. search
4. material detail/card
5. modeling simplification
6. cleanup/acceptance

각 PR은 scope, before/after screenshot, 완료한 사용자 task, tests, known limitations와 next PR을 포함한다.

## 검증

- frontend unit/component tests
- API-backed integration
- Playwright task tests
- 1440×900 및 1366×768 screenshot
- keyboard/accessibility
- production build/bundle
- Python/backend regression
- isolated PostgreSQL
- clean seed/verifier
- card download artifact 검증

## 최종 보고

1. 확인한 current state
2. 변경한 product/UX decisions
3. 변경한 파일
4. before/after task metrics
5. screenshots
6. tests
7. 유지한 domain invariants
8. 남은 위험과 미결정 사항
9. 다음 PR 또는 후속 작업

`modernized`, `polished`, `enterprise-grade` 같은 추상적 표현보다 실제 task와 화면 근거로 설명하라.
