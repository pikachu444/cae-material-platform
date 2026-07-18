# 통합 제품 구현 계획 v3 완료 감사

기준일: `2026-07-18`

이 문서는 T-60 병합 이후 계획의 완료 조건을 실제 코드와 다시 대조한 결과다. 기존 구현은
폐기하지 않으며, bounded capability가 동작한다는 사실과 전체 제품 수직 경로가 완성됐다는
주장을 구분한다.

## 판정

| 계획 요구 | 현재 증거 | 판정 | 남은 완료 증거 |
| --- | --- | --- | --- |
| migration 없는 Table/Attribute/Layout/Subset | migrations 059~060, typed value tables, 관리자/record UI와 PostgreSQL 테스트 | 충족 | 없음 |
| Catalog tree/search/facet/compare | lazy Record tree, typed search와 exact compare | 충족 | 없음 |
| 실제 Material에서 native card까지 Workflow Explorer | T-62 closed typed domain binding과 T-65의 여덟 exact-revision 노드가 Material→State→Test JSON→Processing Output→IR→Neutral→두 Card를 투영한다. | 충족 | Release 승인은 후속 governance 운영 범위 |
| Test JSON과 tabular adapter | `cmp.test-data`, CSV/TSV/XLSX adapter, exact JSON/ZIP round-trip, bounded streaming과 T-65 canonical tensile seed/download 검증 | 충족 | 없음 |
| Mapping Profile/Recipe/Batch | versioned profile/recipe, member preflight, isolated output/retry와 T-65 published Recipe의 clean Batch 성공 증거 | 충족 | 없음 |
| 금속 처리와 카드 | 다섯 E 방법, 공개식 후보 비교, selected Output→IR→Neutral→Abaqus/OpenRadioss와 clean demo exact download | 충족(참조 범위) | production material/solver qualification은 제외 |
| 폴리머 처리와 카드 | log-time/Prony candidate, master curve, reviewed IR→Neutral→Abaqus card | 충족(참조 범위) | OpenRadioss 조합은 명시적 unsupported; production qualification 제외 |
| 엘라스토머 처리와 카드 | multi-mode family compare→optional Prony overlay Neutral→두 solver card | 충족(참조 범위) | 비-Ogden LAW62는 명시적 unsupported; production qualification 제외 |
| Neutral Material JSON | metal/linear-viscoelastic/hyper-viscoelastic closed typed union, exact source 검증과 canonical round-trip | 충족 | 없음 |
| Canonical Bulk | clean seed가 exact Test/Profile/Recipe/Neutral/report/card 9개를 bundle로 만들고 verifier/Playwright가 ZIP과 SHA-256을 검사한다. | 충족 | 없음 |
| Admin/User 권한 | T-59 assignment와 five feature grants | 충족 | 없음 |
| 오류 해결 가능성 | T-61 공통 web client가 problem code/trace ID를 보존하고 회귀 테스트한다. | 충족 | 없음 |
| 전체 브라우저 시연 | T-65 Playwright가 exact Abaqus/OpenRadioss native ASCII와 governed ZIP을 실제 UI/API에서 다운로드하고 해시를 검증한다. | 충족 | 실제 solver 실행은 제외 |

## 완료된 의존 순서

1. `T-61` 완료: 상태 정정과 공통 API 오류의 code/trace ID 보존.
2. `T-62` 완료: Configurable Record revision과 실제 domain revision의 typed binding 및 Workflow Explorer.
3. `T-63` 완료: 세 재료군 canonical Neutral Material union과 selected-result promotion.
4. `T-64` 완료: Neutral revision 기반 family별 exporter parity와 bulk source 연결.
5. `T-65` 완료: clean demo full seed, 실제 native/ZIP download Playwright, 매뉴얼·스크린샷.

각 Task는 DB/domain, API, connected UI, PostgreSQL/브라우저 테스트와 문서 증거를 함께 가져야
완료된다. 위 다섯 Task는 이 기준을 충족했다. 실제 solver 실행 qualification은 기존 결정대로
이 감사 범위에서 제외한다.
