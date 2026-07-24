# 공식 제품 자료 조사와 설계 시사점

구조화된 공식 출처와 적용 제한은
[`product-reference-source-catalog.json`](product-reference-source-catalog.json)에 유지한다.

기준일: `2026-07-16`

## 1. 조사 원칙

- 제품 공급사의 공식 제품 페이지, 공식 도움말, 공식 개발자 문서만 제품 사실의 근거로 사용했다.
- 마케팅 문구는 기능의 존재를 확인하는 데만 사용하고 성능·정확성·내부 구현을 추정하지 않았다.
- 공개 API가 노출하는 object model은 통합 인터페이스일 수 있으므로 실제 내부 DB schema로 간주하지 않았다.
- 경쟁 제품의 UI 순서, 파일 구조, card mapping, fitting 알고리즘 구현은 복제 대상이 아니다.

## 2. 제품명과 시점

Siemens는 2025년 3월 26일 Altair Engineering 인수 완료를 공식 발표했다. 따라서 2025년 Altair 도움말의 `Altair Material Modeler` 및 `Altair Material Data Center` 표기와 현재 Siemens 제품 페이지의 `Simcenter Material Modeler` 및 `Simcenter Material Data Center` 표기가 공존한다. 이 패키지는 현재 제품군을 말할 때 `Simcenter`를 사용하고, 과거 도움말을 인용할 때 문서에 적힌 `Altair` 명칭을 유지한다. [Siemens 인수 완료 발표](https://press.siemens.com/global/en/pressrelease/siemens-acquires-altair-create-most-complete-ai-powered-portfolio-industrial-software)

## 3. Ansys Granta MI

### 3.1 공개 자료에서 확인된 기능

| 확인 내용 | 근거 | 판정 |
| --- | --- | --- |
| 기업 재료 정보를 생성·통제·저장하고 CAD/CAE/PLM과 통합한다. | [Granta MI Enterprise 제품 페이지](https://www.ansys.com/products/materials/granta-mi) | `FACT-PUBLIC` |
| 데이터·정보·전문지식의 capture, processing, approval을 위한 workflow 도구를 제공한다. | 같은 제품 페이지의 capabilities | `FACT-PUBLIC` |
| 시험실에서 설계 데이터까지 추적 가능한 시험·분석 프로세스를 지원한다고 설명한다. | 같은 페이지의 Test Data Management 항목 | `FACT-PUBLIC` |
| 공식 scripting API는 Database, Table, Record, AttributeDefinition/Value, record link를 다룬다. | [Granta MI Scripting Toolkit API 구조](https://developer.ansys.com/docs/granta-mi-scripting-toolkit-4-2/user_guide/streamlined_api.md) | `FACT-PUBLIC` |
| 공개 API에는 tabular, functional series/grid, file 등 여러 attribute 유형과 attribute unit 정보가 있다. | 같은 API 구조 문서 | `FACT-PUBLIC` |
| 공개 API 문서에는 ObjectHistory, RecordVersionHistory, DataRevisionHistory가 revision 정보를 표현한다고 적혀 있다. | 같은 API 구조 문서 | `FACT-PUBLIC` |
| 공식 toolkit에는 FEA exporter 개념과 데이터 통계·비선형 fitting·validation 예제가 공개되어 있다. | [FEA exporter API](https://developer.ansys.com/docs/granta-mi-scripting-toolkit-4-2/api/supporting.md), 위 API 문서의 sample 목록 | `FACT-PUBLIC` |

### 3.2 이 설계에 반영하는 기능적 교훈

- 재료의 단일 datasheet보다 시험·분석·승인 과정 전체가 관리 대상이어야 한다.
- scalar, table, curve, file은 서로 다른 데이터 의미를 갖고 schema와 단위를 명시해야 한다.
- 재료 record 사이의 관계와 revision history가 중요하다.
- CAE 배포는 별도 exporter 책임으로 분리해야 한다.

### 3.3 추정하지 않는 내용

- Granta MI 서버가 어떤 상용 DB 또는 graph DB를 사용하는지
- 실제 내부 table/record schema와 키 구조
- revision이 event sourcing, snapshot, delta 중 무엇으로 구현되는지
- exporter의 내부 intermediate representation과 mapping 규칙
- workflow engine의 내부 실행 모델

공개 object model과 내부 schema를 동일시하지 않는다.

## 4. Simcenter Material Data Center

### 4.1 공개 자료에서 확인된 기능

| 확인 내용 | 근거 | 판정 |
| --- | --- | --- |
| proprietary 및 supplier material data를 통합하고 full traceability를 제공한다고 설명한다. | [Simcenter Material Data Center 제품 페이지](https://www.siemens.com/en-us/products/simcenter/materials-science-management/material-data-center/) | `FACT-PUBLIC` |
| role-based access, auditable/full revision control, validated data의 single source of truth를 강조한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| SaaS와 on-premises 배포, strict RBAC, revision management, flexible data structure를 공개적으로 제시한다. | 같은 페이지의 scalable/configurable platform 항목 | `FACT-PUBLIC` |
| experimental, statistical, solver-ready dataset을 관리한다고 설명한다. | 같은 항목 | `FACT-PUBLIC` |
| CAE solver card 생성과 CAE 도구 내 plugin 연계를 제공한다고 설명한다. | 같은 페이지의 solver-card 및 CAE ecosystem 항목 | `FACT-PUBLIC` |
| SAP·PLM·ERP 및 제3자 응용을 위한 API 통합을 제시한다. | 같은 페이지의 enterprise connectivity 및 FAQ | `FACT-PUBLIC` |
| 검색, numerical property range filter, 비교, proprietary private database를 지원한다고 설명한다. | 같은 페이지의 FAQ | `FACT-PUBLIC` |

### 4.2 이 설계에 반영하는 기능적 교훈

- 실험 데이터, 통계 결과, solver-ready model/card는 한 record의 덮어쓰기 필드가 아니라 서로 연결된 revisioned artifact여야 한다.
- enterprise 통합과 접근제어는 부가기능이 아니라 domain data와 함께 설계해야 한다.
- card 전달 시 단위 변환과 대상 application 적합성을 자동 검증해야 한다.

### 4.3 MVP에서 의도적으로 따라가지 않는 기능

- 상용 reference material library 및 공급업체 데이터 계약
- 생성형 AI 검색, 누락 물성 예측, 유사 재료 추천
- sustainability 및 restricted-substance compliance
- PLM/ERP별 완성형 connector

이 기능들은 유용하지만 원본 보존→보정→검증→발행 수직 기능의 선행조건이 아니다.

## 5. Simcenter Material Modeler

### 5.1 현재 Siemens 공식 페이지에서 확인된 기능

| 확인 내용 | 근거 | 판정 |
| --- | --- | --- |
| raw material test data를 simulation-ready model로 변환하고 automated curve fitting과 integrated validation을 제공한다. | [Simcenter Material Modeler 제품 페이지](https://www.siemens.com/en-us/products/simcenter/materials-science-management/material-modeler/) | `FACT-PUBLIC` |
| CSV, Excel, solver-native format을 포함한 복수 형식 import를 설명한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| smoothing, scaling, shifting, mean curve, extrapolation/fitting 기능을 설명한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| elastoplastic, hyperelastic, viscoelastic, viscoplastic 및 rate/temperature dependency를 설명한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| virtual specimen을 이용한 validation을 설명한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| Radioss, LS-DYNA, OptiStruct, Abaqus, Ansys, AutoForm용 material card를 예시로 든다. | 같은 제품 페이지 | `FACT-PUBLIC` |

### 5.2 Altair 2025 공식 도움말에서 확인된 세부 workflow

- elastoplastic workflow는 import → prepare → curve fitting/extrapolation → material card → advanced strain-rate/failure/simulation으로 구성되어 있다. [Altair Material Modeler 개요](https://2025.help.altair.com/2025/material_modeler/topics/material_modeler/altair_material_modeler_about_r.htm)
- 공개 도움말은 CSV/TXT/DAT/Excel import, 곡선별 설정, curve fitting을 설명한다. [Import Data](https://2025.help.altair.com/2025/material_modeler/topics/material_modeler/data_import_t.htm)
- tutorial은 Young's modulus 평가·조정, smoothing, 반복 곡선 mean, necking point 선택, true-stress/true-plastic-strain 변환, 복수 fitting 함수 비교를 보여 준다. 이는 공개된 사용자 기능이지 내부 알고리즘 사양이 아니다. [Plastic behavior tutorial](https://2025.help.altair.com/2025/material_modeler/topics/material_modeler/tutorials/amm_material_plastic_behavior.htm)
- 2025 elastoplastic 도움말의 Simulation Panel은 해당 validation run이 Radioss만 지원된다고 명시한다. 현재 Siemens 제품 페이지는 더 넓게 integrated virtual specimens를 설명하므로, 지원 범위는 제품 버전·workflow에 따라 달라질 수 있다. [Simulation Panel](https://2025.help.altair.com/2025/material_modeler/topics/material_modeler/simulation_panel_t.htm)
- 공개 Material Modeler 도움말은 Voce, Swift, Hockett--Sherby, Ghosh 후보를 같은 시험
  곡선에 맞춰 비교하고, 두 후보를 사용자가 정한 비율로 조합한 뒤 명시적 strain 범위까지
  외삽하는 사용자 흐름을 설명한다. 이는 후보 family와 사용자 선택 흐름의 근거이며 상용
  optimizer의 내부 목적함수·초기값·경계값을 뜻하지 않는다.
  [Plastic behavior tutorial](https://help.altair.com/material_modeler/topics/material_modeler/tutorials/amm_material_plastic_behavior.htm),
  [Extrapolation](https://help.altair.com/material_modeler/topics/material_modeler/extrapolation_t.htm)
- 네 공개 hardening 식은 공개 문헌의 비교표와 대조했다. 플랫폼 구현은 predicted-minus-observed
  normalized least squares, 데이터에서 유도한 명시적 초기값/경계와 SciPy TRF를 독립적으로
  사용하며 결과에 lower/initial/fitted/upper, RMSE와 외삽 domain을 모두 남긴다.
  [공개 hardening 식 비교 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC9143126/)

### 5.3 이 설계에 반영하는 기능적 교훈

- 전처리 동작도 계산 이력의 일부이며, 사용자가 곡선을 직접 바꿨더라도 recipe와 결과 revision이 남아야 한다.
- 평균 곡선과 개별 곡선을 모두 보존해야 한다.
- fitting 품질과 solver-level 가상 시편 검증은 별도 evidence다.
- 하나의 보정 결과에서 여러 solver card를 만들 수 있으므로 neutral model과 exporter를 분리해야 한다.
- exporter가 의미가 다른 solver model로 변환할 때 silent approximation을 금지해야 한다.

## 6. Ansys MCalibration

### 6.1 공개 자료에서 확인된 기능

| 확인 내용 | 근거 | 판정 |
| --- | --- | --- |
| 실험 데이터에서 재료 parameter를 반자동으로 추출하고 보정한다. | [Ansys MCalibration 제품 페이지](https://www.ansys.com/products/structures/mcalibration) | `FACT-PUBLIC` |
| viscoelastic, viscoplastic, anisotropic model calibration을 지원한다고 설명한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| test dataset 정리, virtual experiment, model stability check를 공개 기능으로 제시한다. | 같은 제품 페이지 | `FACT-PUBLIC` |
| Veryst의 공개 사례는 복수 시험 curve에 구성모델을 맞추고 parameter를 FE 전처리기용 형식으로 저장하는 흐름을 설명한다. | [Veryst Material Model Calibration](https://www.veryst.com/services/testing/material-model-calibration) | `FACT-PUBLIC` |

### 6.2 이 설계에 반영하는 범위

- 시험 데이터 정리 작업은 immutable Processing Recipe/Run으로 흡수한다.
- parameter initial value, bounds, objective, multistart와 diagnostics는 Modeling의 Calibration
  Plan/Run/Candidate로 흡수한다.
- candidate 비교와 사람 선택을 수치 수렴과 분리한다.
- material-point 또는 virtual experiment는 Validation evidence로 분리한다.
- 선택된 결과는 solver-neutral IR revision으로 승격한 뒤 exporter를 거친다.

### 6.3 복제하지 않는 범위

- MCalibration 전용 bounded module 또는 독립 제품
- proprietary UI, 내부 schema, 비공개 file format과 optimizer 구현
- PolyUMod 고유 모델, 초기값 database 또는 상용 제품 고유 명칭
- 화면이나 실행 결과를 역공학해 만든 parameter/mapping fixture

MCalibration은 calibration capability의 누락을 확인하기 위한 참고 제품이다. 이 플랫폼의
중심은 Material catalog, test data, processing/statistics, neutral IR, solver card와 governance다.

## 7. 외부 표준·기술 근거

### 7.1 Provenance

W3C PROV-DM은 provenance를 domain-agnostic한 Entity, Activity, Agent와 그 관계로 정의하고 도메인 확장점을 제공한다. 이 설계는 RDF/OWL graph DB를 의무화하지 않고, 이 개념을 PostgreSQL typed relation으로 매핑한다. [W3C PROV-DM](https://www.w3.org/TR/prov-dm/), [W3C PROV Primer](https://www.w3.org/TR/prov-primer/)

### 7.2 단위

UCUM은 과학·공학·비즈니스의 측정 단위를 위한 code system이다. 이 설계는 원문 unit string을 별도로 보존하면서 canonical unit code에 UCUM-compatible 표현을 사용한다. [UCUM](https://unitsofmeasure.org/)

### 7.3 통계와 이상치

NIST는 outlier를 다른 관측치에서 현저히 벗어난 관측치로 설명하며, 정상 데이터의 특성을 먼저 파악하고 잠재 outlier를 식별해야 한다고 설명한다. 이 설계는 outlier 자동 삭제를 금지하고 candidate detection과 adjudication을 분리한다. [NIST Outlier Detection](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm), [NIST Outlier 설명](https://www.itl.nist.gov/div898/handbook/prc/section1/prc16.htm)

NIST는 측정 결과가 curve처럼 고차원 함수 데이터일 때 functional statistical methods의 필요성도 설명한다. 따라서 scalar summary와 curve ensemble analysis를 별도 기능으로 정의한다. [NIST Functional Analysis of Variance](https://www.nist.gov/programs-projects/functional-analysis-variance)

## 8. 기존 초기안 검토

### 8.1 유지할 내용

- Python/FastAPI, PostgreSQL, 객체 저장소, React, 비동기 worker의 기본 조합
- 모듈형 모놀리스 우선
- Material → State → Lot → Test → Dataset → Processing → Statistics → Model → Card → Validation이라는 큰 흐름
- Importer, Processor, Statistical Analyzer, Material Model, Calibrator, Validator, Solver Exporter 확장점

### 8.2 보완 또는 수정한 내용

1. **선형 lineage 오류**: 실제 데이터는 여러 raw curve가 한 통계 결과·calibration에 들어가고 하나의 IR에서 여러 card·validation이 파생되는 DAG다.
2. **identity와 revision 혼재**: Material, Dataset, Model의 안정 ID와 immutable content revision을 분리해야 한다.
3. **시험 문맥 부족**: Test Method, Campaign, Run, Condition, Specimen, Instrument, Calibration을 분리해야 재현 가능하다.
4. **Lot/Batch/process 부족**: 공급 lot와 가공 batch, 제조 process definition과 process execution을 구분해야 한다.
5. **플러그인 신뢰 경계 누락**: Python interface만 정의하면 dependency 충돌·보안·재현성이 해결되지 않는다. manifest, artifact contract, isolated runner가 필요하다.
6. **IR 의미론 부족**: 파라미터 이름/값만으로는 solver-neutral하지 않다. stress/strain measure, kinematics, units, tables, interpolation, validity domain, mapping report가 필요하다.
7. **Graph DB 판단 근거 부족**: lineage 탐색을 위한 graph-shaped data와 graph database의 필요성은 다르다. known relation, ACID, RLS가 중요한 MVP에는 PostgreSQL이 적합하다.
8. **가상 검증 실행 누락**: 상용 solver version, license, HPC runner, template, deck, logs, result extraction까지 provenance에 포함해야 한다.
9. **통계의 독립 표본 단위 누락**: curve point를 표본으로 취급하면 안 된다. bootstrap과 산포 계산의 기본 표본 단위는 specimen/test run이다.
10. **발행 개념 부족**: 계산 완료와 승인된 release는 다르다. reviewer decision과 immutable release package가 필요하다.

## 9. 조사 결론

기능적 대체 제품의 핵심은 경쟁 제품의 화면을 합치는 것이 아니다. 다음 네 가지를 하나의 제품 규칙으로 묶는 데 있다.

1. 원본과 모든 파생물의 불변성 및 provenance
2. 시험·통계·보정의 공학적 재현성
3. solver-neutral model semantics와 명시적 exporter mapping
4. 검토·승인된 release만 downstream CAE에 공급하는 governance
