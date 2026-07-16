# CAE Material Data Platform

## 서비스 사용자가 할 수 있는 일

이 서비스는 재료를 등록하고 시험·처리·모델 이력을 연결한 뒤 CAE solver용 material card를
얻는 재료 데이터 플랫폼입니다. 로컬 데모에서는 다음 세 흐름을 실제 화면에서 실행할 수
있습니다.

- 금속: Material/State/기본 물성 → tensile data → tabulated plasticity 또는 reference Voce
  → OpenRadioss LAW36 또는 Abaqus `*PLASTIC` card
- 폴리머: shear-relaxation raw/normalized/processed Dataset → bounded Prony calibration과 사람
  candidate 선택 → 새 immutable linear-Prony IR revision → Abaqus `*VISCOELASTIC` card
- 엘라스토머: Material/State/기본 물성 → one-term Ogden + shear-Prony IR → mapping preflight
  → Abaqus Ogden `.inp` 또는 OpenRadioss LAW62 `.rad` preview/download

결과에 표시되는 `reference / non-production`은 실제 입력·저장·다운로드가 동작한다는
뜻이지만, 특정 회사 재료의 승인값이나 solver qualification을 의미하지 않습니다. 특히
LAW62의 incompressibility는 ν=0.495로 근사되므로 mapping report에 `approximated`로 표시됩니다.

빠른 시작은 Docker Desktop 실행 후 아래 명령을 사용합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml up --build
```

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

현재는 단일 State에 제조 공정 1개, 열처리 공정 1개, Lot/Batch 1개를 고정하는 bounded
T-07 범위입니다. 공정 run의 입력·출력, lot split/merge, multi-lot acceptance, ERP 연동은
후속 범위입니다.

[http://127.0.0.1:5173](http://127.0.0.1:5173)에서 **Connected token → Use local demo
identity → Save connection**을 선택합니다. 개발·migration·테스트 상세는
[DEVELOPMENT.md](DEVELOPMENT.md)에 분리되어 있습니다.

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
- 시험 CSV를 Raw Asset으로 보존한 뒤 column/unit mapping을 승인하고 normalized Dataset 생성
- 반복시험 curve, 통계, QC, outlier candidate와 사람의 판정을 분리해 검토
- solver-neutral Material Model IR과 mapping report를 확인
- OpenRadioss 또는 Abaqus material card를 미리 보고 다운로드
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
→ 관측점 시간 구간 Recipe/Run과 별도 processed Dataset
→ manual linear Prony IR
→ bounded two-term Prony calibration과 multistart candidate/residual 비교
→ Abaqus *VISCOELASTIC mapping report → preview → .inp download
```

현재 Dataset은 raw/normalized/processed로 구분되고 처리 Recipe와 Run이 정확한 revision을
고정합니다. 처리된 curve는 bounded two-term generalized-Maxwell reference model에 fitting할
수 있고, deterministic multistart candidate, 관측/예측 curve, residual, 수렴·bound·식별성
상태를 화면에서 비교할 수 있습니다. 사람의 candidate 선택과 새 IR revision 승격은 다음
구현 단위이며 현재 가장 낮은 objective를 자동 승인하지 않습니다. Ogden-Prony와
OpenRadioss LAW62는 그 이후의 별도 초점탄성 수직 기능이며,
선형 Prony를 LAW62로 조용히 변환하지 않습니다. 공식 mapping과 domain review가 완료되기
전 결과물은 `reference/non-production`으로 표시됩니다.

### 웹 화면에서 시작하는 순서

1. **Materials**에서 Material을 만들고 class를 `metal`, `polymer` 또는 `elastomer`로 선택합니다.
2. Material 상세에서 State를 만들고 density, Young's modulus, Poisson ratio를 입력합니다.
3. Steel은 **Test data workflow**, Polymer/Elastomer는 **Shear-relaxation Dataset**을 엽니다.
4. 시험 방법과 Test Run을 만든 뒤 CSV와 실제 column/unit 의미를 입력합니다.
5. normalized curve를 확인하고 필요한 시간 구간을 processed Dataset으로 커밋합니다.
6. baseline linear-Prony IR을 만든 뒤 processed Dataset으로 bounded calibration을 실행합니다.
7. candidate의 objective, fitted curve, residual과 warning을 비교합니다. 현재 단계에서는
   candidate 선택과 IR 승격을 자동 수행하지 않습니다.
8. solver/version을 고른 뒤 mapping 상태를 확인하고 card를 미리 보거나 다운로드합니다.

화면에 표시된 `reference` 결과는 실행 가능한 독립 구현 예제이지, 특정 회사의 재료나
제품 설계에 대해 승인된 값이 아닙니다.
점탄성 업로드 형식은 [reference-shear-relaxation.csv](examples/data/reference-shear-relaxation.csv)를
사용해 볼 수 있습니다(`time_s`, `shear_modulus_mpa`, 단위 `s`/`MPa`).

## 지원 상태

| Material workflow | Model/IR | Solver output | 상태 |
| --- | --- | --- | --- |
| 기본 탄성 | isotropic linear elasticity | OpenRadioss `/MAT/ELAST` | reference 구현 |
| Steel 탄소성 | tabulated isotropic plasticity, reference Voce | OpenRadioss LAW36, Abaqus isotropic plasticity | reference 구현 |
| Polymer 선형 점탄성 | shear-relaxation Dataset + generalized Maxwell/Prony | Abaqus time-domain `*VISCOELASTIC` | raw/normalized/processed 보존, bounded multistart fitting, candidate/residual 검토, 사람 선택, 새 IR revision 승격, card preview/download reference 구현 |
| Elastomer 초점탄성 | one-term Ogden + 1~5 shear-Prony | Abaqus Ogden, OpenRadioss LAW62 | 명시적 preflight와 card preview/download reference 구현; LAW62 ν=0.495 근사는 mapping report에 표시 |
| 실제 solver 실행 검증 | virtual specimen/HPC | solver result evidence | 현재 우선순위에서 제외 |

`reference`는 데이터 흐름과 mapping 계약을 실행할 수 있다는 뜻이며, 실제 제품 설계에
바로 사용할 수 있도록 검증·승인된 재료 모델이라는 뜻이 아닙니다.

실제 Docker/PostgreSQL 환경에서 수행한 사용자 흐름과 화면은
[2026-07-16 E2E 검증 기록](docs/15-demo/user-e2e-evidence-2026-07-16.md)에서 확인할 수 있습니다.

### 현재 Polymer 사용자 흐름

사용자는 shear-relaxation CSV를 raw/normalized/processed Dataset으로 보존한 뒤 bounded Prony
calibration을 실행할 수 있습니다. 각 candidate의 fitted curve, residual, convergence 및 bound
warning을 검토하고 직접 candidate와 선택 사유를 확정해야 합니다. 이 작업은 기존 Material
Model identity를 유지하면서 새 immutable IR revision을 추가합니다. 승격된 revision에서
Abaqus 2025 mapping report, `*VISCOELASTIC` card preview와 `.inp` 다운로드를 바로 생성할 수
있으며, 자동 candidate 승인이나 원본 데이터 덮어쓰기는 없습니다.

## 로컬에서 실행

Docker Desktop이 실행 중인 상태에서 다음 명령을 사용합니다.

```powershell
make demo
# 또는
docker compose -f deploy/compose/docker-compose.demo.yml up --build
```

브라우저에서 [http://127.0.0.1:5173](http://127.0.0.1:5173)을 열고 **Connection**에서
**Use local demo identity**를 선택합니다. API는 `http://127.0.0.1:8000`, PostgreSQL은
Compose 내부 서비스로 실행됩니다. 실제 회사 데이터는 포함되지 않습니다.

상세 설치, migration, 테스트, 아키텍처와 문제 해결은
[DEVELOPMENT.md](DEVELOPMENT.md)를 참고하십시오. 제품 범위는
[product vision](docs/01-product/product-vision.md), 데이터 불변성과 provenance는
[revision and provenance](docs/04-provenance/revision-and-provenance.md), 현재 구현 상태는
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)에 정리되어 있습니다.

## 데이터 보호 원칙

- 원본 파일과 발행된 artifact/revision은 수정하거나 덮어쓰지 않습니다.
- stable identity와 immutable revision을 분리합니다.
- 계산과 card 생성은 항상 `latest`가 아닌 정확한 입력 revision을 참조합니다.
- 원래 단위 문자열, normalized 단위와 quantity semantics를 함께 보존합니다.
- outlier는 삭제하지 않고 candidate와 사용자 판정을 별도 기록합니다.
- mapping의 `exact`, `transformed`, `approximated`, `ignored`, `unsupported`,
  `not_applicable` 상태를 숨기지 않습니다.
- organization/project authorization을 API와 PostgreSQL RLS 양쪽에서 적용합니다.
