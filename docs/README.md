# 문서 포털

문서는 목적과 유지 수준에 따라 네 상태로 분류합니다. 기계 판독 기준은
[`documentation-manifest.yaml`](documentation-manifest.yaml)입니다.

| 상태 | 의미 | 변경 원칙 |
| --- | --- | --- |
| `current` | 현재 사용·개발·운영 화면과 절차 | 코드와 같은 변경 단위에서 갱신 |
| `authoritative` | 제품·domain·architecture·contract 규범 | 구현 전에 읽고 ID/ADR를 추적 |
| `historical` | 완료 Task, 과거 화면과 실행 evidence | 사실 보존, 현재 사용법으로 인용 금지 |
| `reference` | 외부 제품 조사와 비교 자료 | 원칙의 근거이며 제품 계약은 아님 |

## 시작점

- 프로젝트 개요와 실행: [루트 README](../README.md)
- 개발: [DEVELOPMENT](../DEVELOPMENT.md)
- 현재 구현 상태: [IMPLEMENTATION_STATUS](../IMPLEMENTATION_STATUS.md)
- 사용자: [사용자 가이드](user-guide/index.md)
- 관리자: [관리자 가이드](admin-guide/index.md)

## 제품과 설계

- [제품 비전](01-product/product-vision.md)
- [제품 경험 명세](01-product/product-experience-spec.md)
- [UX 시각 시스템](01-product/ux-visual-system.md)
- [Desktop engineering UI 재구축 프로그램](01-product/desktop-engineering-ui-program-brief.md)
- [Desktop engineering UI 제품·상호작용 명세](01-product/desktop-engineering-ui-product-spec.md)
- [GUI 기능·사용성 동등성 계획](01-product/gui-functional-parity-plan.md)
- [Desktop engineering UI 도구·검수 절차](01-product/desktop-engineering-ui-tooling.md)
- 이전 `ux-redesign-package`와 `CODEX_UX_REDESIGN_START.md`는 역사 자료이며 새 구현의 시작점으로 사용하지 않습니다.
- [요구사항](02-requirements/requirements.md)
- [canonical domain model](03-domain/canonical-domain-model.md)
- [revision과 provenance](04-provenance/revision-and-provenance.md)
- [시스템 아키텍처](05-architecture/system-architecture.md)
- [Material Model IR](07-ir/material-model-ir.md)
- [API·event·job 계약](08-contracts/api-events-jobs.md)
- [security·tenancy·audit](11-security/security-tenancy-audit.md)

## 전달과 검증

- [backlog](13-delivery/backlog.md)
- [테스트 전략](14-testing/test-strategy.md)
- [현재 screenshot manifest](user-guide/screenshot-manifest.yaml)
- [과거 screenshot archive](17-evidence/screenshot-archive.yaml)
- [문서·이미지 정합성 감사](17-evidence/documentation-image-audit-2026-07-22.md)
- [구현 연대기](13-delivery/implementation-history.md)

현재 문서에서 역사 screenshot 또는 이전 전역 메뉴를 사용하지 않습니다. 과거 동작을 조사할 때는
`17-evidence`의 historical 문서와 이미지를 명시적으로 열고, 현재 제품 사용법과 혼동하지 마십시오.
