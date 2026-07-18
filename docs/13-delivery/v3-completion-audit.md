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
| 실제 Material에서 Release까지 Workflow Explorer | T-51 graph endpoint는 `catalog.catalog_record_revision` 두 끝점만 허용한다. Material/State/Test/Dataset/IR/Card revision과의 typed binding은 없다. | 미충족 | actual domain revision binding, workbench deep link와 역방향 이동 |
| Test JSON과 tabular adapter | `cmp.test-data`, CSV/TSV/XLSX adapter, exact JSON/ZIP round-trip과 bounded streaming | 충족 | demo에서 실제 등록 증거 강화 |
| Mapping Profile/Recipe/Batch | versioned profile/recipe, member preflight, isolated output와 retry | 충족 | full demo에서 생성·재사용·batch 실행 증거 |
| 금속 처리와 카드 | metal common methods, selected Output→tabulated IR→Abaqus/OpenRadioss | 부분 충족 | 선택 방법, 조합, fitted/extrapolated domain을 canonical Neutral JSON으로 round-trip |
| 폴리머 처리와 카드 | log-time/Prony candidate, master curve, 별도 manual linear-Prony IR와 Abaqus card | 부분 충족 | selected Processing Output→reviewed IR/Neutral promotion. demo가 manual baseline 대신 selected result를 사용해야 함 |
| 엘라스토머 처리와 카드 | multi-mode family compare→Neutral hyperelastic→두 solver card | 부분 충족 | optional Prony overlay를 canonical Neutral family IR에서 보존 |
| Neutral Material JSON | deterministic hyperelastic 1.0.0 document와 import/export | 부분 충족 | metal/linear-viscoelastic/hyper-viscoelastic typed union과 family별 exact source 검증 |
| Canonical Bulk | six exact source representations와 deterministic bundle engine | capability 충족 | clean demo에서 실제 selection/job/ZIP/checksum 다운로드 증거 |
| Admin/User 권한 | T-59 assignment와 five feature grants | 충족 | 없음 |
| 오류 해결 가능성 | API problem은 trace ID를 반환하지만 공통 web client가 버린다. | 미충족 | code/trace ID를 사용자 오류에 보존하고 회귀 테스트 |
| 전체 브라우저 시연 | T-60 Playwright는 Dashboard route 이동만 검사한다. | 미충족 | 입력·처리·승격·preflight·native/ZIP download를 실제 UI/API에서 검증 |

## 후속 의존 순서

1. `T-61`: 이 감사와 상태 정정, 공통 API 오류의 code/trace ID 보존.
2. `T-62`: Configurable Record revision과 실제 domain revision의 typed binding 및 Workflow Explorer.
3. `T-63`: 세 재료군을 포괄하는 canonical Neutral Material union과 selected-result promotion.
4. `T-64`: Neutral revision 기반 family별 exporter parity와 bulk source 연결.
5. `T-65`: clean demo full seed, 실제 native/ZIP download Playwright, 매뉴얼·스크린샷.

각 Task는 DB/domain, API, connected UI, PostgreSQL/브라우저 테스트와 문서 증거를 함께 가져야
완료된다. 실제 solver 실행 qualification은 기존 결정대로 이 감사 범위에서 제외한다.
