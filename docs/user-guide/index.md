# CAE Material Platform 사용자 가이드

이 가이드는 재료시험·재료모델·CAE 사용자가 synthetic demo에서 Material을 찾고 검토하거나 시험
데이터로 새 solver card를 만드는 절차를 설명합니다. 모든 결과는 `reference/non-production`이며
회사의 승인된 재료값이나 solver qualification을 대신하지 않습니다.

## 먼저 할 일

1. [서비스 실행과 자동 demo session](01-getting-started.md)
2. [Search-first Materials와 Modeling](18-search-first-materials.md)
3. [메뉴·route와 문제 해결](10-navigation-and-troubleshooting.md)

기본 경로는 다음과 같습니다.

```text
Materials 검색 → 결과 선택·비교 → 상세 검토 → CAE card preview/download
```

적합한 결과가 없을 때만 다음 경로를 사용합니다.

```text
Modeling Data(JSON/CSV/XLSX) → Process → Fit → Export → Material Library 저장
```

![Search-first Materials 검색과 선택 문맥](images/current/materials-search-1440x900.png)

![그래프 중심 Modeling Fit](images/current/modeling-fit-1440x900.png)

## 업무별 가이드

| 목적 | 가이드 |
| --- | --- |
| Steel 시험에서 Abaqus/OpenRadioss card | [Steel elastoplastic](02-steel-elastoplastic.md) |
| Polymer 완화시험과 Prony card | [Polymer viscoelastic](03-polymer-viscoelastic.md) |
| Elastomer Ogden–Prony card | [Elastomer](04-elastomer-ogden-prony.md) |
| revision, mapping과 다운로드 의미 | [Revision과 다운로드](05-revisions-downloads.md) |
| Process Run/Lot/Specimen genealogy | [Process genealogy](06-process-run-genealogy.md) |
| Campaign·장비·시험 조건 | [Test execution context](07-test-execution-context.md) |
| CSV/TSV/XLSX 승인형 import | [Governed tabular import](08-governed-tabular-import.md) |
| Test JSON·Neutral·card ZIP | [Bulk export](09-bulk-export.md) |
| 운영 상태와 복구 | [Operations](11-operations-and-recovery.md) |
| Tree, Layout, comparison, workflow | [Configurable catalog](12-configurable-catalog-and-modeling.md) |
| Canonical Test Data JSON | [JSON 등록](13-canonical-test-data-json.md) |
| Processing Recipe·Batch·workbench | [Common processing](14-common-processing-workbench.md) |
| Administrator/User 기능 권한 | [Product access](15-product-access.md) |
| 세 재료 계열 통합 demo | [Guided demo](16-guided-demo.md) |
| clean demo와 다운로드 검증 | [Clean demo validation](17-clean-demo-download-validation.md) |

## 화면의 정보 배치

- 일반 사용자 메뉴는 `Materials | Modeling | Activity`입니다.
- Materials의 Browse Tree는 Database/Profile/Table/Folder/Record 계층과 검색을 유지합니다.
- Material Detail은 `Overview | Properties | Curves | CAE Cards | Evidence`로 투영합니다.
- Modeling은 compact curve/process explorer와 넓은 graph를 유지하고 설정은 ribbon/drawer로 엽니다.
- full UUID, hash, classification, exact revision, JSON과 provenance graph는 Evidence/Advanced에 둡니다.
- Table/Attribute/Layout/Subset/Link Type 관리는 role-gated Administration에서 수행합니다.

![Searchable Browse Tree](images/current/materials-browse-1440x900.png)

![Material Detail과 native card action](images/current/material-detail-1440x900.png)

## 현재 제한

- 실제 production 재료 데이터와 solver correlation은 포함하지 않습니다.
- 공개식 기반 reference model의 결과를 승인된 engineering 값으로 사용하지 않습니다.
- production identity provider, confidential-data 운영과 domain-approved golden은 별도 승인이 필요합니다.
- 이전 deep link는 호환을 위해 열릴 수 있지만 현재 전역 navigation을 설명하지 않습니다.
