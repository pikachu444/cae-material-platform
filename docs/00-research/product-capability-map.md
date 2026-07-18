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
| Mapping Profile | 자유 Attribute/채널을 계산 quantity에 연결하는 revisioned profile이다. | `partial` | explicit identity/revision + typed channel/Attribute binding, exact Attribute Definition pin | create/list/get/revise + strong ETag | create/select/revise JSON editor | domain/API/fresh PostgreSQL/React/live browser | `FR-MAP-001~004`, `T-53`; immutable profile implemented, Recipe integration remains |
| Common Processing Workbench | crop, scale/shift, resample, smoothing, curve alignment/statistics를 ordered method pipeline으로 구성하고 단계별 overlay를 본다. | `partial` | exact input/profile FK + one-revision Output/step + Artifact pin | seven-method preview, commit/list/download | exact Test Data/profile/steps + shared-axis overlay + Output list/download | numeric/domain/API/migration/React/live Docker/browser | `FR-PRO-001~010`, `T-53`; alignment/statistics remain |
| Saved Recipe library 및 batch | versioned recipe를 저장·수정·재사용하고 선택한 Dataset에 preflight 후 batch 실행한다. 현재 alignment batch는 일반 Recipe batch가 아니다. | `partial` | recipe와 bounded batch | bounded batch | 일반 builder/library 없음 | bounded test | `FR-BAT-001~006`, `T-54` |
| 금속 탄소성 modeling | tensile 처리, tabulated plasticity/reference Voce, Abaqus/OpenRadioss card가 있으나 복수 E 평가·necking·복수 fitting/조합은 없다. | `partial` | 있음 | 있음 | reference UI | 있음 | `FR-MOD-M-001~007`, `T-55M` |
| 폴리머 점탄성 modeling | shear relaxation, bounded Prony, repeat/master-curve subset과 Abaqus card가 있다. 일반 term selection과 전체 WLF/Arrhenius workbench는 제한적이다. | `partial` | 있음 | 있음 | reference UI | 있음 | `FR-MOD-P-001~003`, `T-55P` |
| 엘라스토머 초탄성/초점탄성 modeling | multi-test Ogden–Prony reference flow와 두 solver card가 있다. 복수 모델 family와 일반 pipeline은 없다. | `partial` | 있음 | 있음 | reference UI | 있음 | `FR-MOD-E-001~004`, `T-55E` |
| Neutral Material JSON | 기존 solver-neutral IR은 있으나 source curve, processing, candidate, extrapolation을 함께 운반하는 import/export 문서는 없다. | `partial` | IR 있음 | IR API 있음 | IR 표시 있음 | 있음 | `FR-JSON-007~010`, `T-56` |
| Solver mapping과 native card | Abaqus/OpenRadioss reference mappings, 여섯 mapping 상태, preview/download가 있다. 추가 모델 mapping은 공식 문서와 domain review가 필요하다. | `partial` | 있음 | 있음 | 있음 | golden/semantic 있음 | `FR-EXP-*`, `T-57` |
| JSON+ZIP bulk package | immutable Bundle은 있으나 canonical Test JSON/Neutral JSON/Recipe 중심 package profile은 아직 없다. | `partial` | 있음 | 있음 | 있음 | 있음 | `FR-EXP-005~006`, `T-58` |
| 단순 사용자 권한 | 내부 deny-by-default 역할은 구현됐으나 제품 표면의 Administrator/User + feature grant는 없다. | `mischaracterized` | 복합 정책 있음 | 복합 permission | connection 중심 | security test 있음 | `FR-ACC-001~004`, `T-59` |
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
