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

## 불변성 negative check

최초 `r1 -> r2` 승격은 성공했다. 이후 이미 promotion evidence가 있는 `r2`를 새
Calibration baseline으로 사용해 다른 evidence로 다시 승격하려는 시도는
`a promoted linear-Prony revision cannot silently replace its evidence`로 거부됐다. 이는 이전
승격 증거의 silent replacement를 막는 현재 계약에 부합한다.

반복 보정을 제품 기능으로 제공하려면 다음 중 하나를 결정해야 한다.

- 매 calibration promotion마다 새 Material Model stable identity를 만든다.
- 같은 stable identity에 `r3+`를 추가하되 과거와 새 promotion evidence를 chain으로 보존하는
  새 IR schema를 정의한다.

결정 전까지 UI는 이미 승격된 current revision을 재승격 대상으로 오인하지 않도록 안내해야
한다. 이 항목은 데이터 손실 defect가 아니라 안전하게 닫힌 iterative-calibration UX/domain
decision이다.

## 검증 명령과 회귀 상태

현재 `main` 기준 회귀 결과는 Python `488 passed, 65 skipped`이며, skip은 DSN 없는 기본
실행에서 의도된 PostgreSQL marker다. Compose의 별도 PostgreSQL 16 DSN으로 marker suite를
재실행하면 `65 passed, 0 skipped, 0 failed`다. Frontend는 15 files/28 tests가 통과했고,
ruff, mypy(469 source files), architecture, OpenAPI lint/compatibility와 production build도
통과했다. Windows PowerShell에는 GNU Make가 없어 `make ci`의 각 명령을 같은 환경 변수와
순서로 직접 실행했다.

다운로드 무결성은 아래 계약으로 확인했다.

```text
GET /api/v1/linear-viscoelastic-solver-cards/{card_id}/download
HTTP/1.1 200 OK
Content-Disposition: attachment; filename="E2E_POLYMER_20260716-000336-326ef8b1.inp"
SHA-256(downloaded bytes) == solver_card_revision.card_sha256
```

## 다음 우선순위

1. Process Run input/output, lot split/merge, multi-lot acceptance와 Specimen source-lot 연결.
2. Test Campaign, Instrument/calibration, standard와 condition snapshot.
3. 실제 선정 시험 포맷용 production importer, governed property/curve schema, viscoelastic
   replicate/alignment/master-curve/temperature-shift processing.
4. domain-approved constitutive parameter, bounds, objective, uncertainty, scientific fixtures와
   exporter version/golden 승인.
5. iterative calibration promotion policy 결정과 UI 안내.
6. observability, backup/restore, package signing/SBOM/scanning, performance/security 및 외부
   PLM/CAE connector hardening.

실제 solver 실행과 solver qualification은 제품 소유자 지시에 따라 이 우선순위에서 제외한다.
