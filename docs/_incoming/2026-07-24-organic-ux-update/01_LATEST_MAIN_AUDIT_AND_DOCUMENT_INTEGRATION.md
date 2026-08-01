# 최신 main 감사와 문서 통합 지도

## 1. 기준선

- 저장소: `pikachu444/cae-material-platform`
- 최신 확인 커밋: `d16d925d71310d940f93ed5707e7bc229e4c4809`
- 커밋 의미: PR #124 `DUI-06: connect fit decisions to solver-card delivery` 병합
- DUI 상태: DUI-01~06 완료, DUI-07~09 미완료
- 독립 리뷰 게이트 #119: 보류 유지
- 자동 LLM 리뷰: 다시 활성화하지 않음
- deterministic hook·테스트·증거 규칙: 유지

`d16d925`는 이 문서의 감사 기준선이지 영구 고정 SHA가 아니다. 실행 시 `main`이 더 앞서 있으면 최신 HEAD를 다시 감사하고 차이를 반영한다.

## 2. 최신 main에서 확인된 구현

PR #124로 다음 연결은 실제 코드와 테스트에 들어왔다.

```text
Fit candidate
→ engineer decision reason
→ immutable Processing Output
→ Material Model IR
→ Neutral model
→ solver mapping preflight
→ native solver card
```

따라서 “Fit과 Export가 전혀 연결되지 않았다”는 이전 진단은 폐기한다. 그러나 연결이 생겼다는 사실과 사용자 경험이 올바르다는 판단은 다르다. 최신 main에는 다음 핵심 문제가 남아 있다.

- 추천 후보가 실제 사용자 선택 전에 선택된 것처럼 보일 수 있음
- 금속 blend 결과의 identity가 단일 law처럼 기록될 수 있음
- polymer 자동 term 선택과 저장 identity가 달라질 수 있음
- upstream 변경 시 session의 downstream exact revision을 지울 수 없는 병합 방식
- 현재 session 결과가 없을 때 전역 Processing Output이나 기존 model로 fallback 가능
- `Validate` 단계가 없음
- Materials의 일부 필터가 최대 50개 client subset에만 적용되면서 전체 결과처럼 보임
- 모든 family에 항복강도 필터가 노출되고 첫 Property Set의 값이 사용됨
- Export에서 “먼저 reviewed fit을 commit하라”는 차단과 기존 delivery가 동시에 보일 수 있음

이 패키지는 완료된 연결을 버리지 않고, 그 위의 결정·상태·조건·표시 계약을 바로잡는다.

## 3. 저장소 문서의 역할

### 3.1 Authoritative

| 경로 | 단일 책임 |
|---|---|
| `AGENTS.md` | 저장소 전역 제품·구현 불변조건 |
| `CODEX_DESKTOP_ENGINEERING_UI_START.md` | Codex 실행의 유일한 시작점 |
| `docs/01-product/product-vision.md` | 제품 경계, 사용자 가치, 비목표 |
| `docs/01-product/desktop-engineering-user-flows.md` | 사용자 목적, 단계, 상태 전이, 오류 복구 |
| `docs/01-product/desktop-engineering-ui-product-spec.md` | 화면 정보 구조와 업무 상호작용 |
| `docs/01-product/desktop-engineering-ui-spec.md` | 컴포넌트별 존재 이유·배치·표시 조건·상태·키보드·금지 패턴 |
| `docs/01-product/visual-acceptance-matrix.md` | 해상도·밀도·그래프·표·접근성의 측정 가능한 합격 조건 |
| `docs/01-product/desktop-engineering-ui-tooling.md` | 실행·캡처·검증 도구 사용법 |
| `docs/13-delivery/desktop-engineering-ui-backlog.md` | 구현 상태, 의존성, 실행 순서 |

권위 문서끼리 같은 규칙을 중복해서 독립적으로 정의하지 않는다. 예를 들어 component의 `visible_when`은 UI spec이 원본이고, user flow는 그 component가 참여하는 단계만 참조한다.

### 3.2 Reference

| 경로 | 역할 |
|---|---|
| `docs/00-research/official-product-research.md` | 공식 자료에서 확인한 외부 제품의 실제 사용 방식 |
| `docs/00-research/product-capability-map.md` | 참고 제품 기능과 현재 제품 경계의 비교 |
| `docs/00-research/ux-reference-gallery/` | 관찰한 UI 패턴과 출처 |
| `docs/00-research/images/gui-reference/` | 출처가 있는 참고 이미지와 캡처 |
| `docs/00-research/product-reference-source-catalog.json` | 공식 출처의 구조화된 카탈로그 |

Reference의 관찰을 제품 요구사항으로 자동 승격하지 않는다. 채택할 때는 Authoritative 문서에 사용자 문제와 의도적 차이를 기록한다.

### 3.3 Current status and help

- `README.md`
- `IMPLEMENTATION_STATUS.md`
- `docs/README.md`
- `docs/design-index.md`
- `docs/user-guide/**`
- `docs/user-guide/navigation-contract.yaml`
- `docs/user-guide/screenshot-manifest.yaml`

이 문서는 실제 main의 동작을 설명해야 한다. 미래 목표를 현재 기능처럼 쓰지 않는다.

### 3.4 완료 이력

이 패키지가 작성된 뒤 저장소 정책이 바뀌었다. 완료 보고서, 과거 캡처와 archive는 working tree에
누적하지 않고 Git 이력과 병합된 GitHub issue/PR에서 조회한다. #167의 승인 target만 별도 manifest로
유지한다.

## 4. 이전 조사 패키지의 통합 매핑

| 이전 파일 | 처리 | 저장소 대상 |
|---|---|---|
| `01_PRODUCT_BOUNDARIES_AND_RESEARCH_METHOD.md` | 분해·병합 후 폐기 | 조사 방법·버전은 `official-product-research.md`; 제품 경계는 `product-vision.md`; 사실·판단·TBD 규칙은 `docs/design-index.md` |
| `02_GRANTA_USAGE_RESEARCH.md` | 유효 사실만 병합 | `official-product-research.md`; 채택한 원리는 `user-flows`·`product-spec`·`ui-spec` |
| `03_MATERIAL_MODELER_USAGE_RESEARCH.md` | 버전 구분과 실제 흐름을 병합 | `official-product-research.md`; 채택한 원리는 Modeling 관련 권위 문서 |
| `04_CURRENT_PRODUCT_UX_DIAGNOSIS.md` | 기존 내용 폐기 후 최신 main에서 재작성 | 수정 요구는 spec/backlog에 흡수하고 완료본은 Git 이력에서 조회 |
| `05_TARGET_PRODUCT_EXPERIENCE_SPEC.md` | 책임별 분해·병합 | flow는 `user-flows`; 구조는 `product-spec`; 컴포넌트는 `ui-spec`; 수치 기준은 `visual-acceptance-matrix` |
| `06_CODEX_IMPLEMENTATION_BRIEF.md` | 전면 대체 | 현재 backlog와 `CODEX_DESKTOP_ENGINEERING_UI_START.md` |
| `07_UX_RULES.yaml` | 저장소에 추가하지 않고 폐기 | 실행 규칙은 spec/matrix/test로 이동 |
| `08_SOURCE_CATALOG.json` | 정리·이름 변경 | `docs/00-research/product-reference-source-catalog.json` |
| `09_MASTER_HANDOFF_PROMPT.md` | 대체 | `CODEX_DESKTOP_ENGINEERING_UI_START.md`를 유일 실행 진입점으로 유지 |
| 이전 패키지 `README.md` | 저장소에 추가 금지 | 이 통합 문서로 역할 종료 |

이전 `07_UX_RULES.yaml`은 중복 key가 있고 그래프 폭 기준이 기존 hard gate와 충돌하며 고정 열 구조로 오해될 수 있다. 그대로 이식하지 않는다.

## 5. 최신 main에서 즉시 정정할 stale 문서

| 경로 | 현재 문제 | 정정 |
|---|---|---|
| `CODEX_DESKTOP_ENGINEERING_UI_START.md` | #112/#114/#115만 병합됐고 DUI-03·05~09가 pending인 과거 상태 | DUI-01~06과 PR #124 완료를 기록하고, 본 통합 작업의 첫 corrective slice를 다음 작업으로 지정 |
| `docs/01-product/desktop-engineering-ui-program-brief.md` | PR #112 Draft가 후속을 막는다는 과거 문구 | 현재 상태표와 corrective workstream, DUI-07~09 순서로 교체 |
| `docs/13-delivery/desktop-engineering-ui-backlog.md` | DUI-06이 병합 대기이며 예전 권장 PR 순서 | PR #124와 merge SHA로 완료 처리; 기존 번호를 바꾸지 않고 corrective epic을 DUI-07 앞에 삽입 |
| `docs/user-guide/screenshot-manifest.yaml` | `source_commit: 117551a`, 병합 대기 캡처 | SHA만 바꾸지 말고 latest main에서 재캡처한 파일과 상태를 함께 갱신 |
| `docs/user-guide/navigation-contract.yaml` | Modeling 소유 task가 DUI-04 중심 | DUI-04/05/06의 Data·Process·Fit·Export 계약과 Activity pending 범위를 반영 |
| `docs/design-index.md` | 이미 구현된 항목이 “다음 기준선”으로 남음 | 권위 문서 읽기 순서와 사실·관찰·결정·TBD 표기 규칙을 갱신 |
| `docs/README.md` | 주요 UI spec·flows·visual matrix가 제품 문서 목록에서 빠짐 | 문서별 단일 책임과 우선순위를 추가 |
| `IMPLEMENTATION_STATUS.md` | PR #124의 exact decision-to-delivery chain과 남은 결함이 불명확 | 구현된 계약과 아직 미구현인 validation/review·session invalidation을 분리 기록 |

## 6. 권위 문서 충돌 정리

현재 `docs/documentation-manifest.yaml`은 `docs/01-product/**/*.md`를 넓게 authoritative로 분류한다. 그 결과 서로 다른 세대의 글꼴 크기, pane 구조, 진행 상태가 동시에 권위를 가진다.

다음 문서는 유효 내용을 위 단일 책임 문서로 옮기고 inbound link를 바꾼 뒤 삭제한다.

- `docs/01-product/product-experience-spec.md`
- `docs/01-product/ux-visual-system.md`
- `docs/01-product/gui-functional-parity-plan.md`

이관 규칙:

| 기존 내용 | 이동 대상 |
|---|---|
| 제품 경계·비목표 | `product-vision.md` |
| 실제 사용자 업무 | `desktop-engineering-user-flows.md` |
| 정보 구조·컴포넌트·타이포그래피 | `desktop-engineering-ui-product-spec.md`, `desktop-engineering-ui-spec.md` |
| 수치 hard gate | `visual-acceptance-matrix.md` |
| 과거 T-84~T-93·PR 상태 | Git 이력과 병합된 GitHub issue/PR |

충돌 시 우선순위:

1. 실제 API·domain·revision·provenance·solver mapping contract
2. latest main에서 검증된 동작
3. 새로 통합한 authoritative product/UI spec
4. reference research
5. Git/GitHub completion history

## 7. 삭제할 오래된 실행 자료

유효 내용 병합, inbound link 수정, `rg`로 참조 0건 확인 후 삭제:

- `CODEX_UX_REDESIGN_START.md`
- `docs/01-product/ux-redesign-package/README.md`
- `docs/01-product/ux-redesign-package/00_UX_REDESIGN_GOAL.md`
- `docs/01-product/ux-redesign-package/01_RESEARCH_EVIDENCE_AND_COLLECTION.md`
- `docs/01-product/ux-redesign-package/02_UX_REDESIGN_EXECUTION_PLAN.md`
- `docs/01-product/ux-redesign-package/03_UX_ACCEPTANCE_CRITERIA.md`
- `docs/01-product/ux-redesign-package/04_CODEX_MASTER_PROMPT.md`
- `docs/01-product/ux-redesign-package/05_REFERENCE_SOURCES.md`

삭제하지 않을 것:

- 공식 reference image·manifest
- #167 approved reference HTML/CSS/image와 manifest
- domain/ADR/계산/solver/plugin/revision/provenance 계약

삭제 후 `docs/documentation-manifest.yaml`과 `docs/README.md`의 안내를 함께 정리한다.

## 8. 문서 통합의 완료 조건

- 같은 제품 규칙의 권위 원본이 하나다.
- 외부 제품 사실과 현재 제품 결정이 문장 수준에서 구분된다.
- 최신 상태 문서에 PR #124 이전의 pending 표현이 없다.
- 완료된 DUI-01~06을 재구현하라는 지시가 없다.
- 삭제 대상 문서의 inbound link가 0이다.
- README와 user guide가 미래 기능을 현재 기능처럼 말하지 않는다.
- screenshot manifest의 SHA와 이미지가 같은 실행 결과를 가리킨다.
- 모든 visible engineering field가 `purpose`, `placement`, `visible_when`, `source`, `requires`, `invalidates`, `states`, `error_recovery`를 가진다.
- 이 통합 패키지 자체는 저장소에 남지 않는다.

