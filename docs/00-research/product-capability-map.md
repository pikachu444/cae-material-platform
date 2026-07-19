# Product capability map

기준일: `2026-07-19`

이 문서는 제품 방향과 실제 구현 사이의 단일 추적표다. 상용 제품의 공개 사용자 기능은
제품 요구사항을 점검하는 기준일 뿐이며, 비공개 schema, UI, 알고리즘 또는 파일 형식을
복제하지 않는다. 상세 조사 근거는 [공식 제품 자료 조사](official-product-research.md)에 있다.

상태는 다음 네 값만 사용한다.

- `implemented`: clean deployment의 task-oriented browser journey까지 사용자가 완료하며
  PostgreSQL/domain, API/calculation, connected product UI와 automated test 증거가 모두 있다.
- `partial`: engine 또는 isolated technical UI는 있으나 통합 product experience가 완료되지 않았다.
- `missing`: 제품 사용자가 실행할 수 있는 기능이 없다.
- `mischaracterized`: 기존 문서의 완료·범위 설명이 실제 코드보다 넓다.

## Capability matrix

| Capability | 공개 근거와 제품 결정 | 현재 상태 | DB | API | UI | Test | Requirement / Task |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Configurable Table 및 Attribute Definition | Granta MI 공개 object model과 Attribute 관리 기능을 참고한다. 관리자가 migration 없이 scalar, curve, file, link attribute를 정의한다. | `implemented` | identity/revision + 9 typed value tables | protected create/list/revise | task-oriented Administration Database design | unit/API/PostgreSQL/Vitest/live browser | `FR-CFG-001~005`, `T-49/T-78` |
| Layout, Subset, datasheet | Granta의 Layout/Subset 개념을 참고하되 독자 UI로 구현한다. Layout 순서로 typed Record를 작성하고 검색 조건을 Subset revision으로 저장·재적용한다. | `implemented` | revision + ordered items/filter + typed values | create/list/revise/apply | Layout-selectable persistent Datasheet with original/normalized units | API/PostgreSQL/Vitest/live browser | `FR-CFG-006~007`, `T-49/T-50/T-77` |
| Material/State 고정 property | stable identity, immutable revision, density/E/ν/yield property set이 있다. 완전 관리형 schema로 대체하지 않고 호환 projection으로 유지한다. | `partial` | 있음 | 있음 | 있음 | 있음 | `FR-CAT-001~002`, `T-07/T-49` |
| Catalog Explorer | Database/Profile → Table → nested Folder → Record를 persistent Contents Tree로 제공한다. | `implemented` | Folder/Record/Subset와 stable domain binding | lazy children/search API | product `/database` three-pane Contents Tree; legacy flat route retained | nested lazy expansion/live PostgreSQL/browser | `FR-NAV-001/003/006`, `T-51/T-71/T-76` |
| Material Workflow Explorer | Material → State → Test/Specimen → Dataset → Processing → IR → Neutral → Card를 exact revision link로 계층 투영한다. | `implemented` | exact binding/link revision engine | depth-eight bidirectional graph API | hierarchical Workflow Tree, Related Data와 exact workbench deep link | link pin advance/reverse/deep-link/live browser | `FR-NAV-002`, `T-51/T-62/T-65/T-66/T-76` |
| Typed arbitrary record link | 관리자가 Link Type, 방향명, 허용 Table, cardinality를 정의하고 양 끝 revision을 고정한다. | `implemented` | explicit Link Type/Link identity+revision tables | protected create/revise/query API | Administration Link Type + Datasheet/Workflow exact navigation | endpoint/cardinality/latest/cross-scope/immutability/live browser | `FR-LNK-001~005`, `T-51/T-77/T-78` |
| Search, facet, compare, saved subset | configurable Record의 이름·설명·text Attribute 검색, Folder, discrete facet, normalized number range, exact revision compare와 saved Subset을 제공한다. | `implemented` | typed search indexes | bounded search/compare | persistent results, facets, ranges and Layout-ordered multi-Record comparison | API/PostgreSQL/Vitest/live browser | `FR-NAV-003~006`, `T-50/T-77` |
| Canonical Test Data JSON | JSON을 공식 교환 형식으로 하고 CSV/TSV/XLSX는 같은 구조로 변환하는 adapter가 된다. 원본 JSON과 digest를 보존한다. | `partial` | typed identity/revision/condition/channel + JSON/Parquet Artifact pins | validate/adapter/import/revise/list/exact/package export | exact Test Data list/load is integrated into Modeling; guided import still opens the dedicated importer | schema/domain/API/React/live PostgreSQL/browser | `FR-JSON-001~006`, `T-52/T-79` |
| Mapping Profile | 자유 Attribute/채널을 계산 quantity에 연결하는 revisioned profile이다. | `partial` | explicit identity/revision + typed channel/Attribute binding, exact Attribute Definition pin | create/list/get/revise + strong ETag | saved/template Map step is integrated; advanced JSON remains available | domain/API/fresh PostgreSQL/React/live browser | `FR-MAP-001~004`, `T-53/T-79/T-80` |
| Common Processing Workbench | crop, scale/shift, resample, smoothing, curve alignment/statistics를 ordered method pipeline으로 구성하고 단계별 overlay와 scalar result를 본다. | `implemented` | exact input/profile/Output engine | preview/commit methods | graph-centered Dataset/stage/curve/options workspace with advanced evidence | numeric/API/Vitest/live Docker/browser | `FR-PRO-001~010`, `T-53/T-79` |
| Saved Recipe library 및 batch | versioned recipe를 저장·수정·재사용하고 선택한 Dataset에 preflight 후 batch 실행한다. | `partial` | Recipe/Batch engine implemented | lifecycle/preflight/execute/retry | cohesive authoring and monitor pending | domain/API/PostgreSQL | `FR-BAT-001~007`, `T-54/T-69/T-70/T-80/T-81` |
| 금속 탄소성 modeling | E/proof/necking/true-plastic/four-family fitting/combination/extrapolation engine이 있다. 하나의 persistent-plot workflow와 immediate option preview는 미완성이다. | `partial` | engine evidence retained | methods/promotion/export retained | family workbench pending | numeric/backend evidence retained | `FR-MOD-M-001~007`, `T-55M/T-70/T-80` |
| 폴리머 점탄성 modeling | log-time/Prony/WLF and promotion/export engine이 있다. curve/term/residual을 한 workbench에서 조작하는 제품 흐름은 미완성이다. | `partial` | engine evidence retained | fitting/promotion/export retained | family workbench pending | numeric/backend evidence retained | `FR-MOD-P-001~005`, `T-55P/T-67~T-69/T-80` |
| 엘라스토머 초탄성/초점탄성 modeling | multi-test/four-family fitting and saved Plan engine이 있다. mode/weight/candidate/stability를 한 workbench에서 조작하는 제품 흐름은 미완성이다. | `partial` | engine evidence retained | Plan/fitting/promotion/export retained | family workbench pending | numeric/backend evidence retained | `FR-MOD-E-001~004`, `T-55E/T-72/T-80` |
| Neutral Material JSON | `cmp.neutral-material`은 metal, linear-viscoelastic, hyperelastic/hyper-viscoelastic selected model을 같은 versioned envelope로 교환한다. | `partial` | typed three-family engine implemented | promotion/validate/import/download implemented | disconnected family controls; final Workbench step pending | schema/domain/API/migration/numeric | `FR-JSON-007~009`, `T-56/T-63/T-64/T-81` |
| Solver mapping과 native card | 공식 solver 문서 기반 manifest, six-state preflight, ASCII/sidecar를 제공한다. | `partial` | typed export engine implemented | exact-Neutral preflight/report/card implemented | scattered preview/download controls; final Workbench and Datasheet integration pending | golden/domain/API/migration/UI | `T-57/T-64/T-81` |
| JSON+ZIP bulk package | exact Test JSON, Mapping Profile, Recipe, Neutral JSON, mapping report와 native card를 기존 immutable Selection/Job/Bundle 엔진으로 조립한다. revision-addressed path, manifest, checksum과 omission을 보존한다. | `partial` | package engine implemented | discover/select/job/bundle/download | technical Export Center; linked product action pending | domain/API/migration/checksum | `FR-EXP-005~006`, `T-58/T-81` |
| 단순 사용자 권한 | Administrator/User와 다섯 기능 grant를 제품 어휘로 제공하고 세밀한 resource/action/scope enforcement는 내부 확장점으로 유지한다. | `implemented` | Migration 074 typed assignment | `/product-access/*` | integrated Users & access without token/API/policy vocabulary | unit/API/PostgreSQL/Vitest/live browser | `FR-ACC-001~005`, `T-59/T-75/T-78` |
| 사용자 매뉴얼과 GUI evidence | 자동 demo session, 계층 Material Database, Layout Datasheet와 search/compare는 실제 화면으로 문서화됐다. 세 family 전체의 cohesive Modeling journey와 home-to-card acceptance는 아직 남아 있다. | `partial` | hierarchy/schema seed retained | verifier retained | current Dashboard/Database/Datasheet captures; Modeling replacement pending | T-75~T-77 browser evidence, full journey pending | `FR-UX-001~009`, `T-60/T-65/T-75~T-77/T-82/T-83` |

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
