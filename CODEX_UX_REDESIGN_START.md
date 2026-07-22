# Codex UX Redesign — Start Here

> Status: historical entrypoint — do not begin implementation from this file. Use [CODEX_DESKTOP_ENGINEERING_UI_START.md](CODEX_DESKTOP_ENGINEERING_UI_START.md) and its linked program brief instead. This file is retained only to preserve the former redesign record.

Implementation status (`2026-07-21`): the T-94 design gate and T-95–T-97 live implementation are
complete. Future changes must preserve the same reference-similarity, full-width, governed Tree and
JSON/CSV/XLSX-to-card acceptance gates. Final evidence is in
`docs/17-evidence/reports/t97-reference-similarity-final.md`.

현재 작업 저장소는 `pikachu444/cae-material-platform`이다.

이 문서는 검색 중심 UX 개편 작업의 실행 진입점이다. 아래 기획 문서를 모두 읽은 뒤 현행 분석부터 실제 프론트엔드 구현과 검증까지 진행하라.

## 반드시 읽을 기획 문서

1. `docs/01-product/ux-redesign-package/00_UX_REDESIGN_GOAL.md`
2. `docs/01-product/ux-redesign-package/01_RESEARCH_EVIDENCE_AND_COLLECTION.md`
3. `docs/01-product/ux-redesign-package/02_UX_REDESIGN_EXECUTION_PLAN.md`
4. `docs/01-product/ux-redesign-package/03_UX_ACCEPTANCE_CRITERIA.md`
5. `docs/01-product/ux-redesign-package/04_CODEX_MASTER_PROMPT.md`
6. `docs/01-product/ux-redesign-package/05_REFERENCE_SOURCES.md`

그리고 기존 저장소의 다음 파일을 확인하라.

- `AGENTS.md`
- `README.md`
- `IMPLEMENTATION_STATUS.md`
- `docs/01-product/product-vision.md`
- `docs/01-product/product-experience-spec.md`
- `docs/01-product/gui-functional-parity-plan.md`
- `docs/00-research/official-product-research.md`
- `docs/00-research/product-capability-map.md`
- `docs/13-delivery/backlog.md`
- `apps/web/src/app.tsx`
- `apps/web/src/material-database-explorer.tsx`
- `apps/web/src/material-modeling-workspace.tsx`
- `apps/web/src/common-processing-workbench.tsx`
- `apps/web/src/canonical-test-data-workbench.tsx`
- `apps/web/src/styles.css`

## 확정된 제품 방향

기존 백엔드, PostgreSQL 데이터 모델, stable identity와 immutable revision, provenance, Processing/Calibration engine, Neutral Material JSON, solver mapping, Abaqus/OpenRadioss exporter는 보존한다.

이번 작업의 최우선 사용자 흐름은 다음과 같다.

```text
재료 검색 → 재료 상세 검토 → CAE solver card 미리보기 및 다운로드
```

두 번째 사용자 흐름은 다음과 같다.

```text
시험 데이터 업로드 → 데이터 처리 → 모델 fitting → solver card 생성 → Material Library 저장
```

Recipe, Batch, Governance, Administration은 위 두 흐름을 보조하는 고급 기능이다.

## 수행 범위

1. clean demo를 실행하고 현행 주요 화면과 사용자 작업 baseline을 기록한다.
2. route/component/API/terminology/CSS 구조를 분석한다.
3. 제품 문서와 `AGENTS.md`를 검색 중심 방향으로 수정한다.
4. 일관된 design tokens와 application shell을 구현한다.
5. `/materials`를 기본 진입점으로 만들고 검색·필터·결과 table을 구현한다.
6. Material Detail을 `Overview | Properties | Curves | CAE Cards | Evidence`로 재구성한다.
7. Modeling을 `Data | Process | Fit | Export` 4단계로 단순화한다.
8. Mapping Profile, Recipe, Batch, exact revision, JSON definition은 `Advanced` 또는 `Evidence`로 이동한다.
9. 중복 route, legacy component와 dead CSS를 정리한다.
10. 실제 사용자 task, accessibility, frontend/backend/PostgreSQL, clean demo와 card download를 검증한다.

분석만 하고 중단하지 말고, 기획 문서의 PR 분할 순서에 따라 가능한 범위까지 실제 구현하라.

## 기본 화면에서 숨길 내부 개념

삭제하지 말고 `Evidence`, `Advanced` 또는 `Administration`으로 이동한다.

- UUID와 aggregate ID
- full revision ID
- SHA/content hash
- classification
- change reason
- Mapping Profile JSON
- Recipe lifecycle
- compatibility preflight 용어
- API/token/tenant/security vocabulary

## 금지사항

- 색상, 그림자, border-radius만 바꾸고 UX 개선이라고 주장하지 않는다.
- 기존 화면에 panel과 card를 계속 추가하는 방식으로 해결하지 않는다.
- backend domain model을 다시 설계하지 않는다.
- 새로운 constitutive model, solver, optimizer 또는 importer를 추가하지 않는다.
- 경쟁 제품 화면을 그대로 복제하지 않는다.
- 테스트 통과만으로 제품 UX 완료라고 선언하지 않는다.
- 전체 프론트엔드를 검증 없이 한 번에 rewrite하지 않는다.

## 목표 navigation과 route

```text
Materials | Modeling | Activity
```

```text
/                         → /materials
/materials                → search/result
/materials/:materialId    → detail
/materials/:materialId/cards/:cardId → preview/download
/modeling                 → Data/Process/Fit/Export
/activity                 → recent jobs/reviews
/settings or /admin       → role-gated administration
```

기존 deep link는 redirect 또는 compatibility route로 유지한다.

## 최종 수용 시나리오

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
Canonical Test Data JSON / CSV / XLSX upload
→ mapping 확인
→ Process
→ Fit
→ Abaqus/OpenRadioss Export
→ Library에서 다시 검색
```

- top-level 단계 4개
- JSON 입력은 schema/channel/quantity semantics/original+normalized unit을 복원
- CSV/XLSX 입력은 worksheet/column/channel/unit mapping을 확인
- invalid schema/unit/worksheet/column은 silent fallback 없이 오류 표시
- normal path에서 JSON editor 직접 작성 불필요; JSON/IR/report는 Evidence에서 다운로드
- 기존 provenance와 solver mapping contract 유지

## 작업 보고

각 PR 또는 단계에서 다음을 기록하라.

1. scope
2. before/after screenshot
3. 완료한 사용자 task
4. 변경한 파일
5. 테스트 결과
6. 알려진 한계
7. 다음 단계

`modernized`, `polished`, `enterprise-grade` 같은 추상적 표현보다 실제 task와 화면 근거로 설명하라.

## Reference image requirement

Before analyzing or implementing the frontend, open every local image in
`docs/00-research/ux-reference-gallery/images/` and read the gallery README.
Do not rely only on filenames, alt text or source links. Record which interaction
principle from each image is applied to each redesigned screen.

## Mandatory design approval gate

Do not begin production React/CSS changes immediately after the reference audit. First produce a
responsive, non-production layout prototype for Materials, Material Detail/CAE Card, and Modeling,
render it at 1366×768, 1440×900, and 1920×1080, and compare it directly with every gallery image.

The comparison must evaluate region topology, dominant-area ratio, information density, typography,
surface/divider grammar, selection continuity, primary action placement, and progressive disclosure.
Pixel similarity, brand color, icons, logos, and exact commercial geometry are excluded.

Each screen must score at least 85/100 under `docs/01-product/ux-visual-system.md`. Region topology,
dominant result/graph area, and zero nested-card violations are hard gates. Product-owner approval of
the comparison prototype is required before implementation. A prior functional screenshot or test
pass does not waive this gate.

The product owner approved the responsive comparison at commit `40726f6` on 2026-07-21. Production
implementation may proceed, but every live screen must pass the same structural rubric and hard gates.

## Documentation synchronization contract

Every implementation PR updates the requirements/product contract, status/backlog, relevant API or
JSON contract, user/admin guide, screenshot manifest, before/after evidence, tests, and known limits
that changed in that PR. The final acceptance PR audits consistency; it is not the first time product
documentation is updated.
