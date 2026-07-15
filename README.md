# CAE Material Data Platform

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

Material class와 호환성 라우팅을 먼저 제공하고 있습니다. 다음 구현 단위에서 shear
relaxation 데이터, linear Prony IR, Abaqus `*VISCOELASTIC`, Ogden-Prony IR과 OpenRadioss
LAW62를 순차적으로 연결합니다. 공식 mapping과 domain review가 완료되기 전 결과물은
`reference/non-production`으로 표시됩니다.

## 지원 상태

| Material workflow | Model/IR | Solver output | 상태 |
| --- | --- | --- | --- |
| 기본 탄성 | isotropic linear elasticity | OpenRadioss `/MAT/ELAST` | reference 구현 |
| Steel 탄소성 | tabulated isotropic plasticity, reference Voce | OpenRadioss LAW36, Abaqus isotropic plasticity | reference 구현 |
| Polymer 선형 점탄성 | generalized Maxwell/Prony | Abaqus time-domain viscoelasticity | IR·DB·API·UI 구현, Abaqus card 다음 단계 |
| Elastomer 초점탄성 | Ogden + Prony | Abaqus, OpenRadioss LAW62 | 후속 수직 기능 |
| 실제 solver 실행 검증 | virtual specimen/HPC | solver result evidence | 현재 우선순위에서 제외 |

`reference`는 데이터 흐름과 mapping 계약을 실행할 수 있다는 뜻이며, 실제 제품 설계에
바로 사용할 수 있도록 검증·승인된 재료 모델이라는 뜻이 아닙니다.

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
