# 문서 포털

문서는 세 상태로 관리합니다. 기계 판독 규칙은
[`documentation-manifest.yaml`](documentation-manifest.yaml)에 있습니다.

| 상태 | 의미 | 변경 원칙 |
| --- | --- | --- |
| `current` | 현재 사용·개발·운영 화면과 절차 | 코드와 같은 변경 단위에서 갱신 |
| `authoritative` | 제품·도메인·아키텍처·계약 규범 | 구현 전에 관련 ID와 문단을 확인 |
| `reference` | 외부 조사·비교 입력 또는 범위가 정해진 이슈 증거 | 제품 계약은 `current`·`authoritative` 문서와 활성 이슈에서 확인 |

완료 보고서와 과거 캡처는 working tree에 쌓지 않습니다. Git 이력과 병합된 GitHub issue/PR이
변경 연대기를 보존합니다.

## 저장소 지도

처음부터 모든 폴더를 읽지 말고, 찾는 내용에 맞는 입구에서 시작합니다.

### 루트에서 찾기

| 찾는 내용 | 시작 위치 |
| --- | --- |
| 제품 소개와 5분 실행 | [루트 README](../README.md) |
| 저장소 작업 규칙 | [저장소 작업 지침](../AGENTS.md) |
| 개발 환경과 명령 | [DEVELOPMENT](../DEVELOPMENT.md) |
| 현재 구현 범위 | [현재 구현 상태](../IMPLEMENTATION_STATUS.md) |
| 제품 코드 | [웹 애플리케이션](../apps/) · [backend](../backend/) |
| 기계 판독 contract | [contract 안내](../contracts/README.md) |
| 비운영 예제와 입력 자료 | [fixture 안내](../fixtures/README.md) |

### `docs/`에서 찾기

| 찾는 내용 | 위치 |
| --- | --- |
| 제품 사용과 운영 절차 | [사용자 가이드](user-guide/index.md) · [관리자 가이드](admin-guide/index.md) |
| 제품 원칙과 요구사항 | [제품과 UX](01-product/) · [요구사항](02-requirements/) |
| contract의 의미와 경계 | [API·이벤트·작업 계약](08-contracts/api-events-jobs.md) |
| 작업 순서와 검증 | [현재 전달 backlog](13-delivery/backlog.md) · [테스트 전략](14-testing/test-strategy.md) |
| 저장소와 문서 관리 | [저장소 운영 문서](16-repository/) |
| 조사·비교 입력과 이슈 증거 | [조사 자료](00-research/) · [이슈 증거](17-evidence/) — 정확한 이슈가 가리킬 때만 확인 |

## 읽기 경로 세 가지

### 제품을 사용하거나 현재 동작을 확인할 때

1. [루트 README](../README.md)에서 제품 범위와 실행 방법을 확인합니다.
2. [사용자 가이드](user-guide/index.md) 또는 [관리자 가이드](admin-guide/index.md)에서 하려는 작업을 찾습니다.
3. 문서와 실제 화면이 다르면 [현재 구현 상태](../IMPLEMENTATION_STATUS.md)와 정확한 활성 이슈를 함께 확인합니다.

### 일반 이슈를 구현할 때

1. [저장소 작업 지침](../AGENTS.md)을 읽습니다.
2. [현재 전달 backlog](13-delivery/backlog.md)에서 작업 순서와 선행 조건을 확인합니다.
3. 정확한 활성 GitHub issue에서 소유 범위와 완료 조건을 확인합니다.
4. 현재 코드와 [현재 구현 상태](../IMPLEMENTATION_STATUS.md)를 보고, `rg`로 영향받는 문단만 찾습니다.

`apps/web` 작업은 추가로 [`apps/web/AGENTS.md`](../apps/web/AGENTS.md)를 따릅니다.

### contract나 fixture를 확인할 때

1. 정확한 이슈와 연결된 요구사항에서 확인할 동작과 ID를 먼저 찾습니다.
2. [API·이벤트·작업 계약](08-contracts/api-events-jobs.md)과 [contract 안내](../contracts/README.md)에서 의미와 기계 판독 파일을 연결합니다.
3. [fixture 안내](../fixtures/README.md)에서 용도와 비운영 경계, 상세 문서의 읽기 순서를 확인한 뒤, 이슈가 가리키는 원본 fixture만 엽니다.

## 권위가 충돌할 때

문서, 현재 코드·화면, contract·fixture, 활성 이슈의 내용이 서로 다르면 편한 쪽을 골라 진행하지
않습니다. 변경을 멈추고 충돌한 두 경로와 문장·ID, 실제로 확인한 동작을 기록한 뒤 활성 이슈나
제품 소유자 지시에서 해결합니다. 해결 전에는 contract를 좁히거나 fixture를 현재 정답처럼 바꾸지
않습니다.

#167의 승인 시각 기준은 [inventory](01-product/service-reference-inventory.yaml)와
[manifest](01-product/service-reference-manifest.yaml)에서 확인합니다. 등록된 화면과 현재 제품 소유자
지시가 충돌하면 활성 이슈의 지시가 우선하며, 같은 범위에서 관련 기준 자료도 함께 갱신합니다.

## 제품과 설계

- [제품 비전](01-product/product-vision.md)
- [데스크톱 엔지니어링 사용자 흐름](01-product/desktop-engineering-user-flows.md)
- [UI 제품·상호작용 명세](01-product/desktop-engineering-ui-product-spec.md)
- [UI 컴포넌트 명세](01-product/desktop-engineering-ui-spec.md)
- [프론트엔드 UI 원칙](01-product/frontend-ui-principles.md)
- [프론트엔드 아키텍처](05-architecture/frontend-architecture.md)
- [프론트엔드 아키텍처·UI 재정비 로드맵](12-roadmap/frontend-refactoring-roadmap.md)
- [프론트엔드 변경 검토 절차](16-repository/frontend-change-review-playbook.md)
- [시각 수용 매트릭스](01-product/visual-acceptance-matrix.md)
- [4K·고DPI 화면 대응 전략과 결정 기록](12-roadmap/high-dpi-display-strategy.md)
- [데스크톱 엔지니어링 UI 도구·검수 절차](01-product/desktop-engineering-ui-tooling.md)
- [현재 delivery backlog](13-delivery/backlog.md)
- [요구사항](02-requirements/requirements.md)
- [스키마 기반 통합 요구사항 추적표](02-requirements/schema-driven-requirement-traceability.md)
- [스키마 기반 통합 원본 문서·샘플 포맷](00-research/schema-driven-integration-source/README.md)
- [정규 도메인 모델 (canonical domain model)](03-domain/canonical-domain-model.md)
- [리비전과 출처 추적 (revision·provenance)](04-provenance/revision-and-provenance.md)
- [시스템 아키텍처](05-architecture/system-architecture.md)
- [Material Model IR](07-ir/material-model-ir.md)
- [API·이벤트·작업 계약](08-contracts/api-events-jobs.md)
- [보안·테넌시·감사](11-security/security-tenancy-audit.md)

## 전달과 검증

- [현재 전달 backlog](13-delivery/backlog.md)
- [프론트엔드 아키텍처·UI 재정비 로드맵](12-roadmap/frontend-refactoring-roadmap.md)
- [프론트엔드 변경 검토 절차](16-repository/frontend-change-review-playbook.md)
- [테스트 전략](14-testing/test-strategy.md)
- [제품 작업 합격 조건과 증거](14-testing/product-work-acceptance.md)
- [현재 화면 캡처 목록 (screenshot manifest)](user-guide/screenshot-manifest.yaml)
- [사용자 가이드와 이미지 유지 규칙](user-guide/MAINTENANCE.md)
- [승인 시각 기준 목록](01-product/service-reference-inventory.yaml)
- [승인 자료·해시 목록](01-product/service-reference-manifest.yaml)

큰 문서를 관성적으로 모두 읽지 마십시오. 정확한 issue와 target ID를 먼저 정하고 `rg`로 관련 문단만
찾습니다. `docs/_incoming/2026-07-24-organic-ux-update/`는 #162 전용 입력이므로 그 전 작업에서는
열지 않습니다.
