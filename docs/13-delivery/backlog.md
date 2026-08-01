# 현재 전달 Backlog

이 문서는 다음 작업과 읽기 경로만 관리합니다. 완료 이력은 Git과 병합된 GitHub issue/PR에서
확인합니다. 새 Codex 작업은 `AGENTS.md`, 이 표의 첫 미완료 issue, 해당 GitHub 본문 순서로
시작합니다.

## 기준선

- production React/CSS: PR #156, commit `55cfa62`
- 승인된 시각 target: PR #170, commit `7601ec8`
- #167 결과: 18 family, 13 bundle, 72/72 이미지 승인 완료
- target 선택: `docs/01-product/service-reference-inventory.yaml`
- 정확한 HTML/CSS/image/hash: `docs/01-product/service-reference-manifest.yaml`
- 자동 LLM review: #119가 열려 있는 동안 비활성

#167의 승인 target은 다시 만들거나 재승인하지 않습니다. 과거 packet, correction 이미지와 완료
보고서는 working tree에 보관하지 않고 Git/PR 이력에서 조회합니다.

## 실행 순서와 문서 라우팅

| 순서 | Issue | 작업 유형 | 처음 읽을 범위 | 종료 조건 |
| ---: | --- | --- | --- | --- |
| 1 | [#157 demo](https://github.com/pikachu444/cae-material-platform/issues/157) | clean demo, backend/domain, 조건부 UI | issue, 실패한 seed/verifier 계약, 관련 requirement·ADR·test. 실제 UI diff가 있을 때만 visual skill과 target을 읽음 | clean demo와 verifier, 관련 test, 필요한 현재 화면·문서, 제품 소유자 확인, merge |
| 2 | [#158 Fit](https://github.com/pikachu444/cae-material-platform/issues/158) | Modeling Fit production UI | issue, `desktop-engineering-ui`, inventory의 `modeling-fit`, 선택된 manifest entry, Fit React/API/state/test | 계약 보존, 필수 viewport·상태·키보드 검증, 시각 승인, merge |
| 3 | [#159 Materials](https://github.com/pikachu444/cae-material-platform/issues/159) | Materials·Administration data/UI | issue, visual skill, Materials/Admin target family, query/tree/detail/card와 권한 계약 | query·revision·download·권한 회귀, 시각 승인, merge |
| 4 | [#160 Governance/Activity](https://github.com/pikachu444/cae-material-platform/issues/160) | 복합 API/state/UI | issue, visual skill, Activity/Admin target family, governance·recovery·authorization 계약 | 역할 E2E, 복구·invalidation·immutable artifact 회귀, 시각 승인, merge |
| 5 | [#161 DUI-09](https://github.com/pikachu444/cae-material-platform/issues/161) | 공통 component·legacy 정리 | issue, visual/frontend skill, 활성 route·공통 component·selector와 approved target | component 상태, 접근성·overflow, 참조 0 삭제, 시각 승인, merge |
| 6 | [#162 UXC-99](https://github.com/pikachu444/cae-material-platform/issues/162) | 역할 E2E·문서·최종 정리 | issue, merged routes, 전체 current/reference inventory, 문서 manifest. 이 단계에서만 incoming을 읽음 | clean role E2E, current 문서·화면 일치, incoming 흡수·참조 0·삭제, 최종 승인, merge |

## 공통 운영

- 표의 첫 미완료 issue만 진행하고 merge 후 다음 issue는 새 Codex 작업에서 시작합니다.
- 메인 에이전트가 exact issue와 현재 계약을 해석해 구현 packet을 GitHub issue에 저장합니다.
  구현자와 reviewer는 그 packet의 정확한 URL만 받습니다.
- 모델, 수정 횟수, reviewer, 승인, commit/push/PR/merge 경계는 `AGENTS.md`와 `.codex` 설정을
  따릅니다. 이 문서나 issue 본문에서 중복 정의하지 않습니다.
- 대형 spec과 manifest는 처음부터 읽지 않습니다. `rg`로 ID·family·component를 찾아 관련 절과
  선택된 entry만 읽고, 시각 작업에서는 승인 이미지를 원본 해상도로 직접 확인합니다.
- `docs/_incoming/2026-07-24-organic-ux-update/`는 #162 전에는 읽거나 삭제하지 않습니다.
