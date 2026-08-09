# 문서 포털

문서는 세 상태로 관리합니다. 기계 판독 규칙은
[`documentation-manifest.yaml`](documentation-manifest.yaml)에 있습니다.

| 상태 | 의미 | 변경 원칙 |
| --- | --- | --- |
| `current` | 현재 사용·개발·운영 화면과 절차 | 코드와 같은 변경 단위에서 갱신 |
| `authoritative` | 제품·도메인·아키텍처·계약 규범 | 구현 전에 관련 ID와 문단을 확인 |
| `reference` | 외부 제품 조사와 비교 자료 | 설계 입력으로만 사용하며 제품 계약으로 간주하지 않음 |

완료 보고서와 과거 캡처는 working tree에 쌓지 않습니다. Git 이력과 병합된 GitHub issue/PR이
변경 연대기를 보존합니다.

## 시작점

- 프로젝트 개요와 실행: [루트 README](../README.md)
- 개발 환경과 명령: [DEVELOPMENT](../DEVELOPMENT.md)
- 현재 구현 상태: [IMPLEMENTATION_STATUS](../IMPLEMENTATION_STATUS.md)
- 사용자 가이드: [사용자 가이드](user-guide/index.md)
- 관리자 가이드: [관리자 가이드](admin-guide/index.md)

새 작업은 [AGENTS.md](../AGENTS.md)와 정확한 GitHub issue에서 시작합니다. 현재 production
React/CSS 기준은 `55cfa62`(PR #156), 승인된 시각 target은 `7601ec8`(PR #170)입니다. #167의
72개 target은 [inventory](01-product/service-reference-inventory.yaml)와
[manifest](01-product/service-reference-manifest.yaml)에서 확인합니다.

## 제품과 설계

- [제품 비전](01-product/product-vision.md)
- [Desktop engineering 사용자 흐름](01-product/desktop-engineering-user-flows.md)
- [UI 제품·상호작용 명세](01-product/desktop-engineering-ui-product-spec.md)
- [UI 컴포넌트 명세](01-product/desktop-engineering-ui-spec.md)
- [시각 수용 매트릭스](01-product/visual-acceptance-matrix.md)
- [4K·고DPI 화면 대응 전략과 결정 기록](12-roadmap/high-dpi-display-strategy.md)
- [Desktop engineering UI 도구·검수 절차](01-product/desktop-engineering-ui-tooling.md)
- [현재 delivery backlog](13-delivery/backlog.md)
- [요구사항](02-requirements/requirements.md)
- [canonical domain model](03-domain/canonical-domain-model.md)
- [revision과 provenance](04-provenance/revision-and-provenance.md)
- [시스템 아키텍처](05-architecture/system-architecture.md)
- [Material Model IR](07-ir/material-model-ir.md)
- [API·event·job 계약](08-contracts/api-events-jobs.md)
- [security·tenancy·audit](11-security/security-tenancy-audit.md)

## 전달과 검증

- [현재 전달 backlog](13-delivery/backlog.md)
- [테스트 전략](14-testing/test-strategy.md)
- [제품 작업 합격 조건과 증거](14-testing/product-work-acceptance.md)
- [현재 screenshot manifest](user-guide/screenshot-manifest.yaml)
- [사용자 가이드와 이미지 유지 규칙](user-guide/MAINTENANCE.md)
- [승인 시각 target inventory](01-product/service-reference-inventory.yaml)
- [승인 asset/hash manifest](01-product/service-reference-manifest.yaml)

큰 문서를 관성적으로 모두 읽지 마십시오. 정확한 issue와 target ID를 먼저 정하고 `rg`로 관련 문단만
찾습니다. `docs/_incoming/2026-07-24-organic-ux-update/`는 #162 전용 입력이므로 그 전 작업에서는
열지 않습니다.
