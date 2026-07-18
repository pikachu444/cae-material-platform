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
| Material Workflow Explorer | Material → State → Test/Specimen → Dataset → Processing → IR → Card → Release를 exact revision link로 투영한다. | `implemented` | migration 061 graph projection | bounded cycle-safe graph API | exact-revision graph/deep link | forward/reverse graph regression | `FR-NAV-002`, `T-51` |
| Typed arbitrary record link | 관리자가 Link Type, 방향명, 허용 Table, cardinality를 정의하고 양 끝 revision을 고정한다. | `implemented` | explicit Link Type/Link identity+revision tables | protected create/revise/query API | Link Type/link editor/deactivate | endpoint/cardinality/latest/cross-scope/immutability | `FR-LNK-001~005`, `T-51` |
| Search, facet, compare, saved subset | configurable Record의 이름·설명·text Attribute 검색, Folder, discrete facet, normalized number range, exact revision compare와 saved Subset을 제공한다. | `implemented` | typed search indexes | bounded search/compare | connected search/datasheet | API/PostgreSQL/React | `FR-NAV-003~006`, `T-50` |
| Canonical Test Data JSON | JSON을 공식 교환 형식으로 하고 CSV/TSV/XLSX는 같은 구조로 변환하는 adapter가 된다. 원본 JSON과 digest를 보존한다. | `implemented` | typed identity/revision/condition/channel + JSON/Parquet Artifact pins | validate/adapter/import/revise/list/exact/package export | connected `/datasets/test-json` | schema/domain/API/React/live PostgreSQL round-trip | `FR-JSON-001~006`, `T-52` |
| Mapping Profile | 자유 Attribute/채널을 계산 quantity에 연결하는 revisioned profile이다. | `implemented` | explicit identity/revision + typed channel/Attribute binding, exact Attribute Definition pin | create/list/get/revise + strong ETag | create/select/revise JSON editor | domain/API/fresh PostgreSQL/React/live browser | `FR-MAP-001~004`, `T-53`; Recipe ownership is T-54 |
| Common Processing Workbench | crop, scale/shift, resample, smoothing, curve alignment/statistics를 ordered method pipeline으로 구성하고 단계별 overlay와 scalar result를 본다. | `implemented` | exact input/profile FK + one-revision Output/step + Artifact pin | twelve-method preview, ensemble alignment/statistics, commit/list/download | exact Test Data/profile/steps + shared-axis stage/member/statistics overlay + scalar result + Output list/download | numeric/domain/API/migration/React/live Docker/browser | `FR-PRO-001~010`, `T-53`; reusable Recipe/batch는 T-54, family method는 T-55 |
| Saved Recipe library 및 batch | versioned recipe를 저장·수정·재사용하고 선택한 Dataset에 preflight 후 batch 실행한다. | `implemented` | exact-profile Recipe identity/revisions/ordered steps + immutable exact-input Batch/Member/Attempt | Recipe lifecycle, per-member preflight/execute/list/detail/failed-only retry | connected Recipe Library + compatibility report + Batch Run Monitor | domain/API/migrations 065~066/React/live PostgreSQL/browser | `FR-BAT-001~006`, `T-54`; durable queued scale-out is an optimization, not a missing product contract |
| 금속 탄소성 modeling | 다섯 E 선택, proof stress, 비파괴 necking 후보, true/plastic 변환, Voce/Swift/Hockett–Sherby/Ghosh fitting, 두 후보 조합과 bounded extrapolation을 Recipe method로 구현했다. selected Output은 exact Test/Profile lineage와 함께 IR `1.2.0`으로 승격되며 같은 Material workbench에서 Abaqus/OpenRadioss card로 이어진다. | `implemented` | explicit Output/Test/Profile/selection/domain columns, composite FK, guard trigger, curve Artifact | metal methods, commit/batch, exact Output promotion, IR/curve, preflight/card | 후보/선택 overlay, exact Output 선택, IR lineage, 두 solver preview/download | analytical/deterministic/domain/API/migration/React/live Docker/PostgreSQL/card download | `FR-MOD-M-001~007`, `T-55M` |
| 폴리머 점탄성 modeling | 공통 Recipe에서 log-time 처리와 1~10항 generalized-Maxwell 후보 비교, BIC/수동 선택을 수행한다. exact Selection master curve는 manual/WLF/Arrhenius를 지원하며 기존 reviewed IR에서 Abaqus card를 생성한다. linear Prony→OpenRadioss LAW62는 명시적으로 unsupported다. 공통 Output의 Neutral JSON/IR promotion은 T-56 경계다. | `implemented` | 있음 | 있음 | 있음 | 있음 | `FR-MOD-P-001~003`, `T-55P`, `T-56` |
| 엘라스토머 초탄성/초점탄성 modeling | exact multi-test revision을 Neo-Hookean/Mooney–Rivlin/Yeoh/Ogden 공개식에 같은 weighting으로 fitting하고 family별 parameter, per-mode objective, holdout, stability warning과 immutable residual Artifact를 비교 UI에서 조회한다. 검토한 family Candidate는 canonical Neutral Material JSON/IR로 승격되고 같은 화면에서 두 solver의 native card로 이어진다. 기존 Ogden–Prony IR/card도 유지된다. | `implemented` | migration 069/070 typed Candidate + Artifact pin, 071 Neutral revision, 072 card revision | protected run/diagnostics/promotion/JSON/preflight/card API | connected family table + curve/residual + human promotion + report/preview/download | equation/limit/round-trip/API/PostgreSQL/React/live browser | `FR-MOD-E-001~004`, `T-55E~T-57` |
| Neutral Material JSON | `cmp.neutral-material` 1.0.0이 exact Material/State/Property, Plan/Run/Candidate, Mapping Profile, Dataset/Artifact digest, normalized/fitted/residual curve, 선택 근거, applicability와 typed IR을 결정적으로 보존한다. validate/import/get/download와 exact-revision solver consumption이 연결되어 있다. | `implemented` | migration 071 explicit typed identity/revision/source Dataset, migration 072 exact card FK | promote/validate/import/get/download/preflight | family 선택, digest, JSON download/import, solver target/report | schema/domain/API/migration/fresh PostgreSQL/React/live browser | `FR-JSON-007~010`, `T-56/T-57` |
| Solver mapping과 native card | 공식 2025 문서를 고정한 versioned manifest가 네 초탄성 family의 Abaqus/OpenRadioss mapping을 선언한다. 여섯 상태, preflight SHA 승인, immutable preview/download와 JSON sidecar가 실제 Neutral revision에서 동작한다. 지원 범위 밖 모델이나 solver는 명시적으로 차단한다. | `implemented` | migration 072 typed family/card/report columns + exact Neutral FK | manifest/preflight/create/list/get/report/preview/download | target 선택, 상태 검토, 근사 승인, ASCII/JSON download | golden/semantic/API/migration/React, unsupported/stale-report negative | `FR-EXP-*`, `T-57` |
| JSON+ZIP bulk package | exact Test JSON, Mapping Profile, Recipe, Neutral JSON, mapping report와 native card를 기존 immutable Selection/Job/Bundle 엔진으로 조립한다. revision-addressed path, manifest, checksum과 omission을 보존한다. | `implemented` | migration 073 typed source pairs + exact composite FK | discover/select/job/bundle/download | six canonical groups, immutable ZIP, job/bundle monitor | domain/API/migration/React/live Docker/PostgreSQL/checksum verification | `FR-EXP-005~006`, `T-58` |
| 단순 사용자 권한 | Administrator/User, 다섯 typed feature grant, legacy-role projection과 grant/revoke 화면을 제공한다. | `implemented` | Migration 074 typed assignment | `/product-access/*` | `/access` | unit/API/PostgreSQL/UI | `FR-ACC-001~004`, `T-59` |
| 사용자 매뉴얼과 GUI evidence | 기존 reference workflow 안내와 screenshot gate가 있으나 새 Explorer/Recipe/JSON 흐름은 기능 구현과 함께 추가해야 한다. | `partial` | 해당 없음 | 해당 없음 | 기존 화면 | guide gate 있음 | `FR-UX-001~003`, `T-60` |

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
