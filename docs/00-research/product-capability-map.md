# Product capability map

기준일: `2026-07-18`

이 문서는 제품 방향과 실제 구현 사이의 단일 추적표다. 상용 제품의 공개 사용자 기능은
제품 요구사항을 점검하는 기준일 뿐이며, 비공개 schema, UI, 알고리즘 또는 파일 형식을
복제하지 않는다. 상세 조사 근거는 [공식 제품 자료 조사](official-product-research.md)에 있다.

상태는 다음 네 값만 사용한다.

- `implemented`: PostgreSQL/domain, API/calculation, connected UI, automated test가 모두 있다.
- `partial`: 일부 계층 또는 제한된 reference workflow만 있다.
- `missing`: 제품 사용자가 실행할 수 있는 기능이 없다.
- `mischaracterized`: 기존 문서의 완료·범위 설명이 실제 코드보다 넓다.

## Capability matrix

| Capability | 공개 근거와 제품 결정 | 현재 상태 | DB | API | UI | Test | Requirement / Task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Configurable Table 및 Attribute Definition | Granta MI 공개 object model과 Attribute 관리 기능을 참고한다. 관리자가 migration 없이 scalar, curve, file, link attribute를 정의한다. | `implemented` | identity/revision + 9 typed value tables | protected create/list/revise | connected schema designer | unit/API/PostgreSQL/UI | `FR-CFG-001~005`, `T-49` |
| Layout, Subset, datasheet | Granta의 Layout/Subset 개념을 참고하되 독자 UI로 구현한다. Layout 순서로 typed Record를 작성하고 검색 조건을 Subset revision으로 저장·재적용한다. | `implemented` | revision + ordered items/filter + typed values | create/list/revise/apply | connected datasheet | API/PostgreSQL/UI | `FR-CFG-006~007`, `T-49/T-50` |
| Material/State 고정 property | stable identity, immutable revision, density/E/ν/yield property set이 있다. 완전 관리형 schema로 대체하지 않고 호환 projection으로 유지한다. | `partial` | 있음 | 있음 | 있음 | 있음 | `FR-CAT-001~002`, `T-07/T-49` |
| Catalog Explorer | Workspace → Table → Folder → Record 탐색과 breadcrumb/deep link를 제공한다. 이는 Granta Contents Tree를 참고한 플랫폼 고유 구조다. | `implemented` | migration 060/061 current-record projection | lazy children API | `/catalog/explorer` | PostgreSQL/API/React/live browser | `FR-NAV-001`, `T-51` |
| Material Workflow Explorer | Material → State → Test/Specimen → Dataset → Processing → IR → Card → Release를 exact revision link로 투영한다. | `partial` | T-62 migration 075가 configurable Record revision을 실제 Material/State/Specimen/Test/Data/Processing/Model/Neutral/Card/Release revision에 closed typed binding하고 기존 exact Record Link graph에 투영한다. 전체 demo genealogy 자동 구성은 T-65 범위다. | binding create/read + bounded graph API | bound node badge/deep-link workbench navigation | same-scope target trigger, immutable PostgreSQL/API/React regression | `FR-NAV-002`, `T-51/T-62/T-65` |
| Typed arbitrary record link | 관리자가 Link Type, 방향명, 허용 Table, cardinality를 정의하고 양 끝 revision을 고정한다. | `implemented` | explicit Link Type/Link identity+revision tables | protected create/revise/query API | Link Type/link editor/deactivate | endpoint/cardinality/latest/cross-scope/immutability | `FR-LNK-001~005`, `T-51` |
| Search, facet, compare, saved subset | configurable Record의 이름·설명·text Attribute 검색, Folder, discrete facet, normalized number range, exact revision compare와 saved Subset을 제공한다. | `implemented` | typed search indexes | bounded search/compare | connected search/datasheet | API/PostgreSQL/React | `FR-NAV-003~006`, `T-50` |
| Canonical Test Data JSON | JSON을 공식 교환 형식으로 하고 CSV/TSV/XLSX는 같은 구조로 변환하는 adapter가 된다. 원본 JSON과 digest를 보존한다. | `implemented` | typed identity/revision/condition/channel + JSON/Parquet Artifact pins | validate/adapter/import/revise/list/exact/package export | connected `/datasets/test-json` | schema/domain/API/React/live PostgreSQL round-trip | `FR-JSON-001~006`, `T-52` |
| Mapping Profile | 자유 Attribute/채널을 계산 quantity에 연결하는 revisioned profile이다. | `implemented` | explicit identity/revision + typed channel/Attribute binding, exact Attribute Definition pin | create/list/get/revise + strong ETag | create/select/revise JSON editor | domain/API/fresh PostgreSQL/React/live browser | `FR-MAP-001~004`, `T-53`; Recipe ownership is T-54 |
| Common Processing Workbench | crop, scale/shift, resample, smoothing, curve alignment/statistics를 ordered method pipeline으로 구성하고 단계별 overlay와 scalar result를 본다. | `implemented` | exact input/profile FK + one-revision Output/step + Artifact pin | twelve-method preview, ensemble alignment/statistics, commit/list/download | exact Test Data/profile/steps + shared-axis stage/member/statistics overlay + scalar result + Output list/download | numeric/domain/API/migration/React/live Docker/browser | `FR-PRO-001~010`, `T-53`; reusable Recipe/batch는 T-54, family method는 T-55 |
| Saved Recipe library 및 batch | versioned recipe를 저장·수정·재사용하고 선택한 Dataset에 preflight 후 batch 실행한다. | `implemented` | exact-profile Recipe identity/revisions/ordered steps + immutable exact-input Batch/Member/Attempt | Recipe lifecycle, per-member preflight/execute/list/detail/failed-only retry | connected Recipe Library + compatibility report + Batch Run Monitor | domain/API/migrations 065~066/React/live PostgreSQL/browser | `FR-BAT-001~006`, `T-54`; durable queued scale-out is an optimization, not a missing product contract |
| 금속 탄소성 modeling | 다섯 E 선택, proof stress, 비파괴 necking 후보, true/plastic 변환, Voce/Swift/Hockett–Sherby/Ghosh fitting, 두 후보 조합과 bounded extrapolation을 Recipe method로 구현했다. selected Output은 exact Test/Profile lineage와 함께 IR `1.2.0` 및 canonical Neutral JSON으로 승격된다. | `partial` | explicit Output/Test/Profile/selection/domain columns, curve Artifact + migration 076 Neutral metal projection | metal methods, Output→IR→Neutral promote/import/download | 후보/선택 overlay, exact Output 선택, IR/Neutral lineage, JSON download | analytical/deterministic/domain/API/migration/React/PostgreSQL | Neutral 보존은 완료. exact Neutral revision에서 두 solver card를 재생성하는 통합 경로는 `T-64`. `FR-MOD-M-001/006/007`, `T-55M/T-63/T-64` |
| 폴리머 점탄성 modeling | 공통 Recipe의 log-time/1~10항 후보 비교와 기존 bounded two-term reviewed Prony calibration을 제공하며, reviewed generalized-Maxwell IR을 canonical Neutral JSON으로 승격한다. | `partial` | linear-Prony IR + migration 076 ordered Neutral Prony rows and exact relaxation Dataset source | reviewed IR→Neutral promote/import/download | calibration candidate/diagnostics와 Neutral JSON download | 수치/domain/API/schema/React | canonical 승격은 완료. 공통 1~10항 Output 승격 통합과 Neutral 기반 Abaqus 재생성은 `T-64`; OpenRadioss linear-Prony는 명시적 `unsupported`. `FR-MOD-P-001~003`, `T-55P/T-63/T-64` |
| 엘라스토머 초탄성/초점탄성 modeling | exact multi-test revision을 네 공개식에 fitting하고 reviewed family를 canonical Neutral JSON과 두 solver card로 연결한다. | `partial` | hyperelastic Candidate/diagnostics + migration 076 exact baseline Prony overlay rows | family promotion now preserves exact source model and ordered Prony overlay | connected comparison/promotion/export | equation/schema/API/PostgreSQL/React | optional Prony overlay 보존은 완료. T-64가 overlay를 포함한 family별 Neutral exporter parity를 완성한다. `FR-MOD-E-004`, `T-55E/T-63/T-64` |
| Neutral Material JSON | `cmp.neutral-material`은 metal, linear-viscoelastic, hyperelastic/hyper-viscoelastic selected model을 같은 versioned envelope로 교환한다. | `implemented` | migration 076 closed model/selection/source kinds, explicit family columns and ordered Prony rows | three promote routes, validate/import/get/download, exact source/digest verification | metal/polymer/hyper workbench creation and download controls | schema/domain/API/migration/numeric round-trip/React/PostgreSQL | 기존 1.0 hyper 문서 canonical bytes를 보존하면서 세 family union을 지원한다. Solver/Bulk consumer parity는 별도 `T-64`. `FR-JSON-007~009`, `T-56/T-63` |
| Solver mapping과 native card | 공식 solver 문서 기반 manifest, six-state preflight, ASCII/sidecar를 제공한다. | `partial` | hyperelastic Neutral exact FK와 기존 family별 IR/card 저장소가 분리됨 | hyperelastic canonical export와 별도 metal/polymer exporter | family별 화면 | golden/API/UI | 카드 자체는 bounded scope에서 동작하지만 canonical Neutral revision 하나에서 세 재료군을 일관되게 재생성하지 못한다. `T-57/T-63` |
| JSON+ZIP bulk package | exact Test JSON, Mapping Profile, Recipe, Neutral JSON, mapping report와 native card를 기존 immutable Selection/Job/Bundle 엔진으로 조립한다. revision-addressed path, manifest, checksum과 omission을 보존한다. | `implemented` | migration 073 typed source pairs + exact composite FK | discover/select/job/bundle/download | six canonical groups, immutable ZIP, job/bundle monitor | domain/API/migration/React/live Docker/PostgreSQL/checksum verification | `FR-EXP-005~006`, `T-58` |
| 단순 사용자 권한 | Administrator/User, 다섯 typed feature grant, legacy-role projection과 grant/revoke 화면을 제공한다. | `implemented` | Migration 074 typed assignment | `/product-access/*` | `/access` | unit/API/PostgreSQL/UI | `FR-ACC-001~004`, `T-59` |
| 사용자 매뉴얼과 GUI evidence | 깨끗한 Compose seed와 Dashboard의 세 안내 경로, walkthrough와 screenshot gate를 제공한다. | `partial` | migration 074 head에서 seed | verifier는 Material/State/Model/Card 존재만 확인 | guided Dashboard | Playwright는 세 버튼과 Exports route 이동만 확인 | 계획의 tree/search/link→import→recipe/batch→fit→Neutral→card→bulk 조작과 실제 다운로드는 검증하지 않는다. 공통 API client도 trace ID를 사용자 오류에 보존하지 않는다. `FR-UX-001~003`, `T-60/T-61/T-65` |

## 공식 공개 근거

- [Granta MI Contents Tree와 Profile](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/MI_Viewer_Help/MI_Viewer/GetStart_Profile.html)
- [Granta MI Attribute 관리](https://ansyshelp.ansys.com/public/Views/Secured/Granta/v261/en/Granta_MI/mi_admin_and_config/managing_attributes.html)
- [Granta MI Record Links](https://developer.ansys.com/docs/granta-mi-scripting-toolkit-4-2/samples/streamlined/16_Link_Records.md)
- [Altair Material Modeler 개요](https://help.altair.com/material_modeler/topics/material_modeler/altair_material_modeler_about_r.htm)
- [Altair Material Modeler 금속 처리 예제](https://help.altair.com/material_modeler/topics/material_modeler/tutorials/amm_material_plastic_behavior.htm)
- [Simcenter Material Modeler](https://www.siemens.com/en-us/products/simcenter/materials-science-management/material-modeler/)

## 완료 판정 규칙

Backlog Task는 다음 증거가 모두 연결되기 전에는 `implemented`가 아니다.

1. 명시적 PostgreSQL migration과 organization/project/classification 경계
2. domain/application contract와 protected API
3. 실제 API에 연결된 사용자 화면
4. unit, PostgreSQL integration, UI/E2E regression
5. 사용자 또는 관리자 가이드와 변경된 GUI capture

기존 foundation이나 bounded reference 구현은 보존한다. 다만 위 다섯 조건 중 빠진 계층이
있으면 이 표에서는 `partial`로 표시한다.
