# 사용자 E2E 검증 기록: 시험 데이터에서 Abaqus 카드까지

검증일: 2026-07-16

환경: Docker Compose demo, PostgreSQL 16, protected demo JWT, React workbench

범위: reference/non-production polymer shear-relaxation vertical

## 결과

새 Material을 만든 뒤 원본 시험 CSV 등록부터 처리, 물성 보정, 사람의 후보 선택, 새 IR
revision 승격, Abaqus 카드 preview와 실제 다운로드까지 한 흐름으로 완료했다. 원본 Raw
Asset, normalized Dataset, processed Dataset, baseline IR 또는 승격 전 revision을 수정하거나
덮어쓰지 않았다.

| 단계 | 검증 결과 | 고정된 식별자/증거 |
| --- | --- | --- |
| Material/State/Property | polymer Material, 23 C State, density 1200 kg/m3, E 3 GPa, nu 0.35 | Material `31ac1602-23ba-4255-9889-e41546b342e2`; State `62c1896e-8879-4c6d-abca-5c3156b2ddb6`; Property revision `fccf6b9e-a079-4175-9400-99fde3bbc69d` |
| 시험 등록 | Specimen과 shear-relaxation Test Run이 exact State/Method revision을 고정 | Test Run revision `53ee9f77-51e0-476b-873c-8e9a27ad07d8` |
| 원본/정규화 | CSV가 immutable Raw Asset으로 완료되고 `s`, `Pa` normalized Dataset을 별도 생성 | Raw Asset `6f300800-8705-4274-938a-c8f76bc8c8ea`; normalized revision `d55187c1-7f1a-4999-a136-4fb918967585`; 6 points |
| 명시적 processing | inclusive observed-point crop, no interpolation, `0.01 s`~`100 s` | Run `636638a7-3405-43db-9fc9-86a94da7a3ef`; processed revision `5a9095e1-082f-42f6-b127-f3285ae138ee`; 5 points |
| bounded calibration | PCG64/SciPy TRF, 5 deterministic starts, 5 converged Candidates | Run `8e24f5e0-0d6c-4379-9261-5e4136d74673`; selected Candidate `88737faa-a473-4d17-a40c-ed2dbf71655f`; objective `0.0010759323648068953`; RMSE `28,537,224.93 Pa` |
| 사람 선택/IR 승격 | 선택 이유와 Candidate/diagnostics digest를 고정하고 같은 model identity에 새 revision 추가 | Selection revision `bbe298e4-5ed5-4ebc-aeba-8c96aace314d`; baseline IR `06cdbf61-cb77-47ba-9d6b-028e755bc483`; promoted IR `d800d363-493e-4ff9-b4f0-52d9cba0052b` |
| Abaqus mapping/card | preflight exportable, exact report digest acknowledgement 후 immutable card 생성 | mapping SHA-256 `0b8fa4a4b44e567fdd8baf333ec42ade51db3aac604a509fac1d93da1da23705`; card `326ef8b1-a112-4d5e-80a1-19f3ae7d87d2` |
| 다운로드 무결성 | HTTP 200, attachment filename, 418 bytes; preview에 `*DENSITY`, `*ELASTIC`, `*VISCOELASTIC` 존재 | stored/download SHA-256 `625b21ded4fc67f6459a3f27d422acf636df9b3d356e58f250bb3ee987561264` 일치 |

## 사용자 화면

### Material과 immutable revision

![E2E Material 상세](images/e2e-material-detail.png)

### 시험 등록과 shear-relaxation 처리

![Shear-relaxation workflow](images/e2e-shear-workflow.png)

### processed curve와 multistart Candidates

![Bounded Prony candidates](images/e2e-prony-candidates.png)

### fitted response와 residual evidence

![Prony candidate diagnostics](images/e2e-prony-diagnostics.png)

### 승격 IR에서 생성한 Abaqus card

![Abaqus VISCOELASTIC card](images/e2e-abaqus-card.png)

### exact Process/Lot genealogy

State Genealogy `2152a876-9d18-4e88-ab2b-7cc00c78e030`의 revision
`6ea7e719-7a6e-4fb7-89ce-c185fb0a3d67`은 제조 Process revision
`52218f2e-3aa8-4b43-8fd4-ba1fada8d841`, 열처리 Process revision
`c37a7e05-af56-438c-b5c8-8d60b6b02cf6`, Lot revision
`29b76af2-7d13-40ce-b827-f1c254c292f5`를 명시적으로 고정한다.

![Process and Lot genealogy](images/process-lot-genealogy.png)

### 별도 Ogden--Prony/OpenRadioss LAW62 vertical

선형 Prony 모델을 LAW62로 재사용하지 않는다. 별도 elastomer Ogden--Prony IR의 LAW62
preview에서 고정 `nu=0.495` incompressibility 근사를 명시한다.

![OpenRadioss LAW62 preview](images/ogden-openradioss-law62.png)

### Governed multi-test Ogden fitting

T-43 공개 합성 fixture로 uniaxial, planar, biaxial calibration curve 3개와 별도 uniaxial
holdout 1개를 등록했다. 네 원본은 각각 immutable Raw Asset과 normalized Dataset revision으로
보존된다. Plan은 exact scientific Profile, Material State, baseline Ogden--Prony IR과 네
Dataset revision을 고정한다. PCG64/SciPy TRF 8-start Run은 `mu=2.0000 MPa`, `alpha=2.00000`을
회복했고 Jacobian rank `2/2`, estimated covariance와 95% CI를 기록했다. 1% stress scale을
적용한 holdout RMSE는 `0.0087561 MPa`이며 calibration과 섞이지 않았다.

![Multi-test Ogden Candidates](images/t43-ogden-candidates.png)

Candidate diagnostics는 52개 observed/fitted/residual point를 exact Parquet Artifact로
보존한다. 같은 화면에서 별도 manual baseline IR의 Abaqus/OpenRadioss card preview와 download
진입점도 확인했다. Candidate를 baseline IR에 append-only promotion하는 단계는 T-44 범위다.

![Ogden fitted curve, residual and cards](images/t43-ogden-diagnostics-and-cards.png)

### Human Selection and iterative Ogden promotion

T-44 migration 055 적용 후 같은 Ogden--Prony stable identity에 두 개의 독립적인 succeeded
Run과 converged Candidate를 차례로 human Selection으로 기록했다. 각 promotion은 실행 시점의
strong current IR ETag를 요구했으며 r1→r2→r3을 append했다. r2와 r3은 각각 자신의 Selection,
Run, Candidate, diagnostics digest와 정확한 prior revision을 소유한다.

![Append-only Ogden r1-r3 history](images/t44-ogden-selection-promotion-history.png)

r2 승격 전에 존재한 Abaqus/OpenRadioss 카드 2개와 r2에서 추가한 Abaqus 카드 1개의 stable ID,
revision ID 및 card SHA를 r3 승격 후 재조회해 모두 동일함을 확인했다. 화면에는 current model이
r3이어도 이전 concrete IR revision에 고정된 카드 3개가 그대로 남는다.

![Prior solver cards remain immutable](images/t44-prior-solver-cards-stable.png)

### Exact-revision Bulk Export Bundle

T-45 migration 056 적용 후 DP780 Material에서 원본 CSV, canonical Parquet/readable CSV,
solver-neutral IR/schema, Abaqus/OpenRadioss mapping report와 native card를 exact revision으로
검색했다. 화면에서 22개 representation을 선택하고 immutable Export Selection과 durable Job을
거쳐 deterministic ZIP Bundle을 생성했다.

![Bulk Export exact selection](images/t45-bulk-export-selection.png)

최신 Bundle은 22개 component, 21.3 KiB이며 별도 `manifest.json`, `checksums.sha256`와 README를
포함한다. 브라우저 Download 동작은 Bundle authorization `201 Created` 뒤 Artifact content
`200 OK`를 받았다. 선택 revision에는 lifecycle/provenance/audit fact가 각각 1건 기록됐다.
Release 또는 기존 source/card revision은 변경되지 않았다.

![Immutable Bulk Export Bundles](images/t45-immutable-bundles.png)

### Global module navigation and Material context tabs

T-46은 Dashboard/Materials/Tests/Datasets/Models/Exports/Governance 전역 메뉴를 제공한다.
Tests, Datasets, Models와 Governance 허브는 현재 tenant/project에서 보이는 Material을 실제
Catalog API로 읽고, 선택한 stable identity의 문맥 경로로 이동한다.

![Global Models hub](images/t46-global-navigation-model-hub.png)

기존 `/materials/{material_id}` deep link는 Overview로 유지하면서 `/testing`, `/datasets`,
`/models`, `/governance` 경로를 추가했다. DP780 `/models` 경로에서 exact State와 Property Set,
IR/Card workbench만 로드되고 Dataset/Test/Governance workbench는 다른 탭으로 분리됨을 확인했다.
Governance 전역 허브에는 실제 Review, Release와 Lineage/Audit 작업대가 연결됐다.

![Contextual Material tabs](images/t46-material-context-tabs.png)

## 불변성 negative check

bounded linear-Prony의 최초 `r1 -> r2` 승격은 성공했다. 이후 이미 promotion evidence가 있는 `r2`를 새
Calibration baseline으로 사용해 다른 evidence로 다시 승격하려는 시도는
`a promoted linear-Prony revision cannot silently replace its evidence`로 거부됐다. 이는 이전
승격 증거의 silent replacement를 막는 현재 계약에 부합한다.

T-44는 같은 stable identity에 `r3+`를 추가하고 revision마다 promotion evidence를 소유하게
하는 결정을 governed Ogden Candidate 경로에 구현했다. 이 결정은 다음과 같다.

- 같은 stable identity에 `r3+`를 추가한다.
- 과거와 새 promotion evidence를 revision chain으로 보존한다.
- 기존 bounded linear-Prony 경로는 별도 migration 전까지 원래 single-promotion guard를 유지한다.

따라서 Ogden 경로의 반복 승격과 linear-Prony 경로의 안전한 거부는 서로 다른 명시적 bounded
계약이며 어느 쪽도 이전 evidence를 덮어쓰지 않는다.

## 검증 명령과 회귀 상태

T-43 branch의 최신 CI-equivalent 회귀는 disposable PostgreSQL 16 DSN을 사용해 Python
`600 passed, 0 skipped, 0 failed`, frontend `20 files / 35 tests`를 기록했다. ruff,
mypy(512 source files), architecture, contract lint, OpenAPI compatibility와 production build가
통과했고 npm audit는 취약점 0건이었다. Migration 054는 별도 임시 DB에서
`001→054→053→054` 왕복을 완료했다. Windows PowerShell에서는 Git Bash로 `scripts/ci.sh`를
실행해 `make ci`와 동일한 순서를 검증했다.

T-45 branch의 최신 CI-equivalent 회귀는 PostgreSQL 16 DSN을 사용해 Python
`613 passed, 0 skipped, 0 failed`, frontend `21 files / 36 tests`를 기록했다. Ruff,
mypy(526 source files), architecture, contract lint, OpenAPI compatibility, production build와
npm audit가 통과했다. Migration 056은 별도 임시 DB에서 `001→056→055→056` 왕복을 완료했다.

다운로드 무결성은 아래 계약으로 확인했다.

```text
GET /api/v1/linear-viscoelastic-solver-cards/{card_id}/download
HTTP/1.1 200 OK
Content-Disposition: attachment; filename="E2E_POLYMER_20260716-000336-326ef8b1.inp"
SHA-256(downloaded bytes) == solver_card_revision.card_sha256
```

## 다음 우선순위

1. T-46 global Materials/Tests/Datasets/Models/Exports/Governance navigation과 contextual Material
   tabs, deterministic screenshot/guide gate.
2. T-47 observability, backup/restore, package signing/SBOM/scanning, performance/security,
   large external-worker Bundle assembly와 외부 PLM/CAE connector hardening.

실제 solver 실행과 solver qualification은 제품 소유자 지시에 따라 이 우선순위에서 제외한다.
