# CAE Material Data Platform

재료 정보를 자유롭게 구성하고 찾아 쓰는 **Material Information System**과 시험 curve를
처리·fitting·extrapolation하여 CAE card로 만드는 **Material Modeling Workbench**를 하나로
연결하는 서비스입니다.

목표 사용자 흐름은 다음과 같습니다.

```text
Catalog tree/search/link → Test Data JSON → Mapping Profile
→ saved Processing Recipe / Batch → Neutral Material JSON
→ Abaqus/OpenRadioss mapping report → native material card
```

검토한 금속 탄소성, generalized-Maxwell 점탄성, Neo-Hookean/Mooney--Rivlin/Yeoh/Ogden
초탄성·초점탄성 모델은 canonical Neutral Material JSON으로 승격한 뒤 같은 화면에서 solver
mapping 상태를 검토하고 native ASCII card와 JSON sidecar를 내려받을 수 있습니다. 금속은
Abaqus `*PLASTIC`/OpenRadioss LAW36, 선형 점탄성은 Abaqus Prony와 조건부 OpenRadioss
`/VISC/LPRONY`, Ogden+Prony는 Abaqus와 OpenRadioss LAW62의 명시된 reference 범위를 지원합니다.
LPRONY는 nearly-incompressible shear-only 자료와 total-strain solid property 요구를 사용자가
확인한 경우에만 생성합니다. 그 밖의 조합은 `unsupported`로
차단하고, 근사 mapping은 명시적 확인 전에는 카드를 만들 수 없습니다.

Exports 화면에서는 exact Test Data JSON, Mapping Profile, Processing Recipe, Neutral Material
JSON, mapping report와 native card를 선택해 `manifest.json`과 `checksums.sha256`을 포함한
immutable ZIP으로 받을 수 있습니다.

현재 저장소에는 위 흐름을 지지하는 PostgreSQL, revision, processing, Neutral JSON과 exporter
엔진이 구현되어 있습니다. T-75부터 일반 화면의 API/token 설정을 제거하고 자동 demo session,
제품 중심 Dashboard와 **Material Database / Material Modeling / Jobs & Reviews / Administration**
내비게이션으로 교체했습니다. T-76은 Database/Profile/Table/Folder/Record **Contents Tree**와
Material에서 두 solver card까지 이어지는 exact-revision **Workflow Tree**를 실제 PostgreSQL
데이터에 연결했습니다. Layout Datasheet·AMDC식 검색/비교와 그래프 중심 Modeling Workbench는
[GUI 기능·사용성 동등성 제품 계획](docs/01-product/gui-functional-parity-plan.md)에 따라 순차 교체
중입니다. T-77은 같은
`/database` workspace에 Layout section 기반 Datasheet, 원본/정규화 단위, discrete facet,
normalized 수치 범위와 다중 Record 비교를 연결했습니다. T-79는 `/modeling`에 exact Dataset과
Recipe 단계, 서버 계산 곡선, 단계별 option을 함께 유지하는 그래프 중심 Modeling Workbench를
연결했습니다. T-80은 같은 화면에 Metal/Polymer/Elastomer track, Step/Recipe/Batch inspector와
각 재료군의 실제 Material/State/Property context를 연결했습니다. 금속 hardening 네 후보,
폴리머 Prony 처리, 엘라스토머 multi-mode 네 model family·multistart·residual 비교까지 Docker
데모에서 계산됩니다. T-81은 세 흐름을 같은 **Reviewed delivery** 기반에 연결했지만, 이 상태는
Material Modeler 수준의 GUI 완료가 아니라 engine integration evidence입니다. 사용자는 현재
exact evidence와 Neutral Material JSON을 확인하고 Abaqus/OpenRadioss의 모든 mapping 상태를
검토·승인한 뒤 native ASCII card를 미리보기·다운로드하거나 같은 Material의 bulk package로
이동할 수 있습니다. T-84~T-93은 현재의 긴 form stack과 제한된 graph를 직접 조작 가능한
engineering workbench로 교체하고 Material Database tree/datasheet 사용성을 다시 검증합니다.
따라서 아직 전체 제품 경험 완료 상태로 표시하지 않습니다. T-85의 첫 검증 체크포인트는
Material Modeling을 compact engineering shell로 바꾸고 실제 server curve에 axis/unit/tick,
crosshair, zoom/pan/reset, curve visibility와 graph range/point selection을 연결했습니다. 변경된
step option은 300 ms 뒤 최신 요청만 preview하며 이전 요청은 취소합니다. Dashboard도 Material
Database와 Material Modeling의 목적·시작 동작을 나란히 보여주는 작업 홈으로 교체했습니다.
금속 Prepare와 네 경화식 Fit/Extrapolate guided control은 T-86/T-87에서 검증했습니다. T-88은
같은 상단 workflow의 Card task에서 exact reviewed result, Neutral JSON, six-state mapping과 실제
Abaqus `.inp`/OpenRadioss `.rad` preview·download를 끝내도록 delivery 화면을 통합했습니다.
폴리머 T-89는 relaxation/DMA graph, Prony 후보·잔차, WLF/Arrhenius master curve와 두 solver card
경로까지 검증했습니다. 엘라스토머 graph/task 동등성은 T-90에서 계속 구현합니다.

현재 제품 빌드는 고정 Material/State schema와 세 가지 `reference/non-production` modeling
흐름에 더해, 관리자가 migration 없이 Table/typed Attribute/Layout/Subset을 정의하는 Catalog
schema designer와 Layout 기반 typed Record datasheet, Folder, text/facet/normalized-range 검색,
saved Subset, exact revision 비교를 제공합니다. Catalog/Workflow Explorer와 관리자가 정의하는
exact-revision Record Link도 실제 PostgreSQL/API/UI로 연결되어 있습니다. Explorer에서 각
workbench로 이동할 수 있고 Material, Test JSON, Processing Output, Neutral Material 및 Solver Card
화면에서도 같은 exact revision을 역조회하여 연결된 Workflow Explorer와 관련 데이터로 돌아갈 수 있습니다. Canonical Test JSON은
검증·CSV/TSV/XLSX 변환·immutable revision·exact 다운로드·checksum JSON+ZIP까지 연결됐습니다.
일반 Mapping Profile과 Processing Recipe/Batch도 실제 API/UI에 연결되어 있으며, clean demo는
Test JSON 등록부터 published Recipe의 Batch 실행, selected Neutral과 두 native card, checksum ZIP까지
재현합니다. 참조 범위와 production qualification의 차이는
[제품 capability map](docs/00-research/product-capability-map.md)에서 확인할 수 있습니다.
금속과 폴리머의 saved Recipe 실행은 성공한 exact Batch Attempt를 IR `1.3.0`과 Neutral JSON에
보존하므로, 사용자는 모델 화면에서 처리 Recipe로 되돌아가 옵션과 실행 결과를 확인할 수 있습니다.

## 서비스 사용자가 할 수 있는 일

이 서비스는 재료를 등록하고 시험·처리·모델 이력을 연결한 뒤 CAE solver용 material card를
얻는 재료 데이터 플랫폼입니다. 로컬 데모에서는 Catalog 관리와 다음 세 흐름을 실제 화면에서 실행할 수
있습니다.

- Catalog 관리: **Catalog**에서 record Table을 만들고 number/text/discrete/file/curve/
  record-reference Attribute, datasheet Layout과 saved Subset을 revision으로 저장. 이어서
  **Catalog records**에서 Folder/Record를 만들고 원본·정규화 단위를 보존해 검색·비교
- Material Database 탐색: **Material Database**에서 Database → Profile → Table → nested Folder →
  Record를 펼치고, 가운데 Workflow Tree에서 Material/State/Test/Processing/Model/Neutral/Card를
  exact revision으로 이동. Datasheet에서 Layout section과 원본/정규화 단위를 확인하고 이름·key·
  설명·text Attribute, discrete facet, normalized range로 검색하거나 여러 Record를 Layout 순서로 비교
- 시험 JSON: **Datasets → Test Data JSON**에서 maker/시험/시편/채널/원본·정규화 단위를
  저장 전 검증하고 stable identity와 immutable revision으로 등록한 뒤 exact JSON을 다시 다운로드
- 금속: Material/State/기본 물성 → governed CSV/TSV/XLSX tensile data → tabulated plasticity 또는 reference Voce
  → OpenRadioss LAW36 또는 Abaqus `*PLASTIC` card
- 폴리머: shear-relaxation raw/normalized/processed Dataset → 공통 Recipe에서 1~10항 Prony
  후보 비교 → exact Processing Output과 순간 전단계수 일치 여부를 사람이 검토 → 새 immutable
  linear-Prony IR와 Neutral Material JSON → Abaqus `*VISCOELASTIC` 또는 조건부 OpenRadioss
  `/VISC/LPRONY` card. 기존 bounded two-term
  calibration 경로도 호환을 위해 유지합니다. 여러
  온도의 반복시험은 common log-time 구간 통계와 수동/WLF shift를 거쳐 master-curve Dataset으로
  별도 보존
- 엘라스토머: governed uniaxial/planar/biaxial normalized curve → versioned scientific profile
  → 저장된 Calibration Plan exact revision 재실행 또는 Dataset 역할/mode/weight 수정 후 새 revision
  → deterministic Neo-Hookean/Mooney–Rivlin/Yeoh/Ogden family 비교와 residual/stability 검토
  → 현재 지원되는 one-term Ogden + shear-Prony IR
  → Abaqus Ogden `.inp` 또는 OpenRadioss LAW62 `.rad` preview/download. Candidate의 governed
  human Selection → current-ETag 확인 → 같은 Material Model identity에 append-only IR revision

결과에 표시되는 `reference / non-production`은 실제 입력·저장·다운로드가 동작한다는
뜻이지만, 특정 회사 재료의 승인값이나 solver qualification을 의미하지 않습니다. 특히
LAW62의 incompressibility는 ν=0.495로 근사되므로 mapping report에 `approximated`로 표시됩니다.

사용자 권한은 [Administration](http://127.0.0.1:5173/administration) 화면에서 `Administrator` 또는 `User`와
다섯 기능 권한으로 관리합니다. schema 구성, catalog 편집, processing/calibration, model 승인,
solver card export를 각각 부여할 수 있습니다. 일반 화면은 사용자/팀 이름만 받으며 API/token,
principal/issuer와 내부 정책 용어를 노출하지 않습니다. 기존 세부 enforcement는 향후 세밀한 권한의
확장점으로 유지됩니다. 자세한 절차는 [사용자 권한 가이드](docs/user-guide/15-product-access.md)와
[관리자 가이드](docs/admin-guide/index.md)를 참고하십시오.

빠른 시작은 Docker Desktop 실행 후 아래 명령을 사용합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml up --build
```

첫 실행은 금속 탄소성, 폴리머 점탄성, 엘라스토머 초탄성/초점탄성의 공개 합성 데이터를 자동으로
준비합니다. 다른 터미널에서 아래 명령으로 세 Material과 Abaqus/OpenRadioss card를 확인할 수
있습니다.

```powershell
make demo-verify
```

Windows PowerShell에 `make`가 없으면 같은 검증을 직접 실행할 수 있습니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml run --rm --no-deps seed python scripts/verify_full_demo.py --api-base-url http://api:8000/api/v1
```

[세 재료 계열 통합 데모](docs/user-guide/16-guided-demo.md)는 Dashboard에서 시험 데이터, 처리,
중립 모델, mapping report, native card와 bulk ZIP까지 이동하는 순서를 설명합니다. 실제 파일과
SHA-256을 확인하는 절차는 [clean demo 다운로드 검증](docs/user-guide/17-clean-demo-download-validation.md)을
따르십시오.

### Material genealogy (Process / Lot / Batch)

Material State 화면의 **Catalog genealogy** 영역에서는 제조 공정, 열처리 공정, Lot/Batch를
별도 관리 레코드로 등록하고 연결할 수 있습니다. 각 레코드는 고정 ID와 변경 불가능한
revision을 따로 가지며, State genealogy는 화면에 보이는 최신 값을 암묵적으로 참조하지 않고
선택 당시의 정확한 State/Process/Lot revision을 저장합니다. 기존 State의 자유 텍스트 route,
heat treatment, lot 필드는 과거 입력과 출처 보존을 위해 그대로 유지됩니다.

사용 순서는 다음과 같습니다.

1. Material과 Material State를 생성합니다.
2. State 카드에서 Process 또는 Lot/Batch revision 1을 등록합니다.
3. 제조 공정, 열처리 공정, Lot/Batch를 선택하고 **Establish genealogy**를 실행합니다.
4. 이후 연결을 고치면 기존 연결을 덮어쓰지 않고 새 genealogy revision이 추가됩니다.

State genealogy와 별도로 Process Run은 consumed/produced Lot revision을 여러 개 고정하고
mass/volume/count balance, split/merge와 Specimen source Lot를 보존합니다. ERP/PLM 연동은
아직 후속 범위입니다.

[http://127.0.0.1:5173](http://127.0.0.1:5173)을 열면 demo workspace가 자동으로 준비됩니다.
사용자가 API 주소나 token을 설정할 필요가 없습니다. 개발·migration·테스트 상세는
[DEVELOPMENT.md](DEVELOPMENT.md)에 분리되어 있습니다.

운영 후보 빌드의 SBOM, 취약점 검사, 서명된 품질 증거와 프론트엔드 용량 기준은 서비스
사용 절차와 분리해 [release-quality 운영 가이드](deploy/supply-chain/README.md)에 설명합니다.
실제 Docker API의 bounded 성능·보안 baseline과 production-scale 미검증 경계는
[performance acceptance 가이드](deploy/performance/README.md)에서 확인할 수 있습니다.

재료의 출처와 변경 이력을 보존하면서 시험 데이터, 재료 모델, CAE solver용 material
card를 하나의 흐름으로 관리하는 웹 서비스입니다. 제품의 중심은 calibration 도구 하나가
아니라 다음 전체 연결입니다.

```text
Material DB → Test Data → Statistics / Processing
→ Material Model IR → Solver Card → Validation / Release
```

Granta MI 계열의 재료·상태·lot/batch·공정·시험 연결 방식과 Altair Material Data Center
계열의 검색·CAE 활용 흐름을 참고하되, 상용 제품의 schema나 UI를 복제하지 않습니다.
MCalibration은 시험 전처리, fitting diagnostics와 candidate 비교 기능을 보완하기 위한
참고 대상일 뿐 별도 제품이나 bounded module이 아닙니다.

## 사용자가 할 수 있는 일

- Material을 등록하고 organization/project 범위에서 이름, 코드, family와 class로 검색
- 제조·열처리 상태와 출처가 명시된 density, Young's modulus, Poisson ratio, yield stress 기록
- 모든 변경을 원본 덮어쓰기 대신 새 immutable revision으로 보존하고 비교
- CSV/TSV/XLSX를 Raw Asset으로 보존한 뒤 reusable column/unit Profile을 승인하고 normalized Dataset 생성
- 반복시험 curve, 통계, QC, outlier candidate와 사람의 판정을 분리해 검토
- solver-neutral Material Model IR과 mapping report를 확인
- OpenRadioss 또는 Abaqus material card를 미리 보고 다운로드
- **Exports**에서 raw/Parquet/CSV/IR/schema/mapping report/native card exact revision을 선택해
  manifest와 SHA-256이 포함된 immutable ZIP Bundle로 다운로드
- model, card, validation, review와 release까지 provenance/lineage를 추적

## 현재 제공되는 시연 흐름

### Steel 탄소성

```text
Metal / Steel Material
→ Material State와 기본 물성
→ tensile Dataset와 명시적 processing
→ tabulated plasticity 또는 reference Voce IR
→ OpenRadioss LAW36 / Abaqus *ELASTIC + *PLASTIC
→ mapping report → preview → download
```

### Polymer 점탄성

```text
Polymer / Elastomer Material
→ Material State와 기본 물성
→ shear-relaxation CSV 원본 보존과 명시적 column/unit mapping
→ raw revision + normalized SI Dataset revision과 curve 확인
→ 다온도 replicate Selection → alignment/statistics → shift evidence → master-curve Dataset
→ 관측점 시간 구간 Recipe/Run과 별도 processed Dataset
→ manual linear Prony IR 또는 공통 Recipe의 1~10항 Prony 후보 비교
→ exact Processing Output, BIC/RMSE/잔차와 catalog G₀ 일치 검토
→ reviewed generalized-Maxwell IR와 Neutral Material JSON
→ Abaqus *VISCOELASTIC 또는 조건부 OpenRadioss LPRONY mapping report → preview → .inp/.rad download
```

현재 Dataset은 raw/normalized/processed/aligned/statistical/master-curve representation으로
구분되고 처리 Plan/Recipe와 Run이 정확한 revision을 고정합니다. 다온도 반복시험 처리는
공통 log-time 교집합에서만 선형 보간하며 외삽하지 않고, 수동 `log10(aT)` 또는 세 온도
이상의 deterministic WLF fit evidence를 저장합니다. 처리된 curve는 공통 Processing Recipe에서
1~10항 generalized-Maxwell 후보에 fitting할 수 있습니다. 자동 BIC 또는 명시적 항수를 선택하며,
서버는 저장된 Output Artifact에서 항과 수치 지표를 다시 읽어 client 입력으로 대체하지 않습니다.
사용자는 BIC/RMSE, 잔차와 catalog 순간 전단계수 G₀의 불일치율 및 사례별 허용 한계를 검토해야
합니다. 검토된 Output은 새 stable Material Model identity의 immutable IR revision과 canonical
Neutral Material JSON으로 승격됩니다. 기존 bounded two-term multistart Candidate 흐름도 호환
경로로 유지되며 어느 경로도 가장 낮은 objective를 자동 승인하지 않습니다. 별도
Ogden--Prony IR은 Abaqus와 OpenRadioss LAW62 card를
생성하며 선형 Prony를 LAW62로 조용히 변환하지 않습니다. 공식 mapping과 domain review가
완료되기 전 결과물은 `reference/non-production`으로 표시됩니다.

### 웹 화면에서 시작하는 순서

1. **Materials**에서 Material을 만들고 class를 `metal`, `polymer` 또는 `elastomer`로 선택합니다.
2. Material 상세에서 State를 만들고 density, Young's modulus, Poisson ratio를 입력합니다.
3. Steel은 **Test data workflow**, Polymer/Elastomer는 **Shear-relaxation Dataset**을 엽니다.
4. 시험 방법과 Test Run을 만든 뒤 CSV와 실제 column/unit 의미를 입력합니다.
5. normalized curve를 확인하고 필요한 시간 구간을 processed Dataset으로 커밋합니다.
6. 공통 Processing에서 `polymer.prony_fit_compare`를 포함한 Recipe를 publish하고 Batch preflight 후
   실행합니다. 성공한 exact Attempt의 Output이 IR `1.3.0`과 Neutral JSON의 Recipe provenance로
   이어집니다.
7. **Models**에서 exact Output의 selected 항수, BIC/RMSE, residual과 catalog G₀ 불일치율을 검토하고
   사례별 허용 한계와 선택 이유를 기록한 뒤 새 IR revision으로 승격합니다.
8. **Create Neutral JSON and solver mapping**을 실행한 뒤 Abaqus mapping 상태를 확인하고 card를
   미리 보거나 다운로드합니다. 기존 bounded calibration Candidate도 호환 경로로 사용할 수 있습니다.
9. 여러 결과를 함께 전달하려면 상단 **Exports**에서 exact revision을 선택하고 Bundle을 만든 뒤
   ZIP을 다운로드합니다.

전역 **Tests / Datasets / Models / Governance**는 독립된 데이터 사일로가 아니라 선택한
Material의 **Test data / Datasets & Processing / Models & Cards / Governance** 문맥 탭으로
연결됩니다. 메뉴 설명과 문제 해결은
[사용자 내비게이션 가이드](docs/user-guide/10-navigation-and-troubleshooting.md)에 있습니다.

화면에 표시된 `reference` 결과는 실행 가능한 독립 구현 예제이지, 특정 회사의 재료나
제품 설계에 대해 승인된 값이 아닙니다.
인장 governed import는 [reference-tensile.csv](examples/data/reference-tensile.csv)를 사용해
볼 수 있습니다(`engineering_strain_pct`, `engineering_stress_mpa`, 단위 `%`/`MPa`). 점탄성
기존 흐름은 [reference-shear-relaxation.csv](examples/data/reference-shear-relaxation.csv)를
사용합니다(`time_s`, `shear_modulus_mpa`, 단위 `s`/`MPa`). 자세한 절차는
[governed tabular import 가이드](docs/user-guide/08-governed-tabular-import.md)에 있습니다.
여러 표현을 한 번에 받는 절차는
[Bulk Export Bundle 가이드](docs/user-guide/09-bulk-export.md)를 참고하십시오. Export Center는
작은 Bundle을 즉시 만들고, 큰 Bundle은 durable Job으로 접수해 외부 worker에서 조립합니다.
Artifact가 커밋된 뒤 Bundle 연결이 실패해도 digest와 크기를 숨기지 않고 재조정 상태로 표시합니다.

## 지원 상태

| Material workflow | Model/IR | Solver output | 상태 |
| --- | --- | --- | --- |
| 기본 탄성 | isotropic linear elasticity | OpenRadioss `/MAT/ELAST` | reference 구현 |
| Steel 탄소성 | tabulated isotropic plasticity, reference Voce | OpenRadioss LAW36, Abaqus isotropic plasticity | reference 구현 |
| Polymer 선형 점탄성 | shear-relaxation Dataset + generalized Maxwell/Prony | Abaqus time-domain `*VISCOELASTIC`, 조건부 OpenRadioss `/VISC/LPRONY` | raw/normalized/processed 보존, 다온도 replicate 통계와 수동/WLF/Arrhenius master curve, 공통 Recipe 1~10항 fitting과 기존 bounded calibration, BIC/RMSE/residual/G₀ 검토, exact Output→IR→Neutral 승격, card preview/download reference 구현; LPRONY는 ADR-0032 경계만 허용 |
| Elastomer 초점탄성 | governed multi-test fitting + one-term Ogden + 1~5 shear-Prony | Abaqus Ogden, OpenRadioss LAW62 | exact Dataset/Profile/State/baseline revision Plan, deterministic candidates, holdout, rank/uncertainty, fitted/residual UI, human Candidate Selection, 반복 append-only IR promotion, revision history와 card preview/download reference 구현; LAW62 ν=0.495 근사는 mapping report에 표시 |
| 실제 solver 실행 검증 | virtual specimen/HPC | solver result evidence | 현재 우선순위에서 제외 |

`reference`는 데이터 흐름과 mapping 계약을 실행할 수 있다는 뜻이며, 실제 제품 설계에
바로 사용할 수 있도록 검증·승인된 재료 모델이라는 뜻이 아닙니다.

실제 Docker/PostgreSQL 환경에서 수행한 사용자 흐름과 화면은
[2026-07-16 E2E 검증 기록](docs/15-demo/user-e2e-evidence-2026-07-16.md)에서 확인할 수 있습니다.

### 현재 Polymer 사용자 흐름

사용자는 shear-relaxation CSV/Test JSON을 보존한 뒤 재사용 가능한 Recipe에서 1~10항 Prony
후보 비교를 실행할 수 있습니다. 각 Output의 fitted curve, residual, BIC/RMSE와 순간 전단계수
일치 여부를 검토하고 사례별 한계와 선택 사유를 확정해야 합니다. 서버가 exact Output Artifact를
다시 읽어 새 immutable IR revision과 Neutral JSON을 만듭니다. 기존 bounded two-term Candidate
흐름은 호환을 위해 유지됩니다. 승격된 revision에서
Abaqus 2025 `*VISCOELASTIC` 또는 ADR-0032 조건을 만족하는 OpenRadioss 2025 `/VISC/LPRONY`
mapping report, card preview와 `.inp`/`.rad` 다운로드를 바로 생성할 수
있으며, 자동 candidate 승인이나 원본 데이터 덮어쓰기는 없습니다.

다온도 반복시험 예제 데이터는 서비스 실행 후 다음 명령으로 추가할 수 있습니다. 이 helper는
공개 synthetic curve만 만들며 실제 회사 재료값을 포함하지 않습니다.

```powershell
uv run python scripts/seed_viscoelastic_master_demo.py
```

생성된 Material 상세의 **Viscoelastic master curve**에서 두 개 이상의 온도와 반복 curve를
선택하고 reference temperature 및 수동/WLF shift 방식을 정하면 aligned/statistical/master
Dataset이 각각 새 immutable revision으로 생성됩니다.

Elastomer 다중시험 fitting 예제는 다음 helper로 추가할 수 있습니다. analytical
uniaxial/planar/biaxial curve 3개와 별도 holdout 1개를 governed normalized Dataset으로 만든 뒤
deterministic Ogden Run까지 실행합니다.

```powershell
uv run python scripts/seed_ogden_calibration_demo.py
```

사람이 화면에서 수행하는 선택·승격 흐름까지 로컬 회귀 데이터로 준비하려면 명시적으로
`--promote`를 붙입니다. 이 옵션은 자동 승인 정책이 아니라 사용자가 실행한 demo-only 명령이며,
Selection 사유와 current IR ETag를 기록하고 기존 Solver Card digest가 그대로인지 확인합니다.

```powershell
uv run python scripts/seed_ogden_calibration_demo.py --promote
```

## 로컬에서 실행

Docker Desktop이 실행 중인 상태에서 다음 명령을 사용합니다.

```powershell
make demo
# 또는
docker compose -f deploy/compose/docker-compose.demo.yml up --build
```

브라우저에서 [http://127.0.0.1:5173](http://127.0.0.1:5173)을 엽니다. demo workspace는
자동으로 시작되며 내부 서비스 연결은 화면에 노출되지 않습니다. 실제 회사 데이터는 포함되지 않습니다.

상세 설치, migration, 테스트, 아키텍처와 문제 해결은
[DEVELOPMENT.md](DEVELOPMENT.md)를 참고하십시오. 제품 범위는
[product vision](docs/01-product/product-vision.md), 데이터 불변성과 provenance는
[revision and provenance](docs/04-provenance/revision-and-provenance.md), 현재 구현 상태는
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)에 정리되어 있습니다.

처음 사용하는 사용자는 [사용자 가이드](docs/user-guide/index.md)에서 demo 실행부터 Steel,
Polymer, Elastomer 시험 데이터와 material card 생성 절차를 따라갈 수 있습니다. 화면이나
사용자 workflow를 변경하는 PR은 관련 가이드와 화면 이미지를 함께 갱신해야 합니다.

운영자는 [운영 상태 확인과 격리 복구 드릴](docs/user-guide/11-operations-and-recovery.md)에서
민감정보가 제거된 Governance 관측성 화면, Collector metric과 실행 중인 DB를 교체하지 않는
PostgreSQL/object 복구 검증 절차를 확인할 수 있습니다.

## 데이터 보호 원칙

- 원본 파일과 발행된 artifact/revision은 수정하거나 덮어쓰지 않습니다.
- stable identity와 immutable revision을 분리합니다.
- 계산과 card 생성은 항상 `latest`가 아닌 정확한 입력 revision을 참조합니다.
- 원래 단위 문자열, normalized 단위와 quantity semantics를 함께 보존합니다.
- outlier는 삭제하지 않고 candidate와 사용자 판정을 별도 기록합니다.
- mapping의 `exact`, `transformed`, `approximated`, `ignored`, `unsupported`,
  `not_applicable` 상태를 숨기지 않습니다.
- organization/project authorization을 API와 PostgreSQL RLS 양쪽에서 적용합니다.
