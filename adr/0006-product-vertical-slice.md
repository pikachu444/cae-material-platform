# ADR-006: 재료 데이터 관리 중심의 첫 제품 수직 기능

## 먼저 읽기

- **무엇을 정했나요?** 첫 사용자 흐름을 Material 등록에서 물성, 중립 IR, mapping 사전 확인을 거쳐
  OpenRadioss 선형탄성 reference solver card를 미리 보고 내려받는 과정으로 한정했습니다.
- **왜 중요한가요?** 기반 기술만 쌓는 대신 실제 재료 관리와 CAE 활용을 끝까지 연결하면서도,
  reference model과 card를 production 검증 결과처럼 과장하지 않기 위해서입니다.
- **언제 읽나요?** Material·State·Property Set·IR·solver card 흐름을 바꾸거나, 첫 reference 기능이
  지원하지 않는 model·solver·validation 범위를 판단할 때 읽습니다.
- **용어를 쉽게 말하면:** `수직 기능`은 저장·API·화면을 한 사용자 작업으로 끝까지 연결한 작은
  제품 단위입니다. `mapping preflight`는 card 생성 전에 옮길 수 없는 항목을 확인하는 절차이고,
  `reference_only`는 예제 경계일 뿐 production 사용을 승인하지 않았다는 뜻입니다.
- **상태 표기는?** `Accepted`는 이 제한된 결정을 채택했다는 뜻입니다. 실제 solver 실행이나
  production model·card 검증이 완료됐다는 뜻은 아닙니다.

- 상태: Accepted
- 기준일: 2026-07-13

## Context

플랫폼에는 revision, provenance, audit, artifact, job 및 plugin 실행 기반이 먼저
구현되었다. 그러나 사용자가 Material을 등록·조회하고 CAE에 사용할 card를 얻는
제품 기능은 아직 없다. 이 프로젝트의 본체는 특정 구성모델 보정 도구의 복제가
아니라 재료 데이터 관리, 시험 데이터 관리, CAE 활용, 검증 및 발행을 연결하는
플랫폼이다.

MCalibration 계열의 workflow는 `processing`, `modeling`, `validation`의 calibration
capability를 보완하는 참고 자료로만 사용한다. proprietary UI, schema, file format,
optimizer, model database 및 제품 고유 동작은 복제하지 않는다.

## Decision

1. 제품 우선순위는 Material catalog와 CAE 활용을 먼저 둔다. calibration은 중요한
   bounded capability이지만 제품의 정체성이나 독립 애플리케이션이 아니다.
2. 첫 end-to-end slice는 `Material → Material State → typed Property Set → Material
   Model IR → mapping preflight → solver card preview/download`이다. 각 단계는
   persistence, protected API 및 web UI를 함께 제공한다.
3. 첫 reference model은 `urn:cmp:reference:isotropic-linear-elasticity:1.0.0`으로
   한정한다. 이 모델은 SI 기준 density (kg/m³), Young's modulus (Pa), Poisson's
   ratio (1)를 가진 small-strain isotropic linear elasticity이며, calibration,
   yield/failure, temperature/rate dependence 또는 production validation을 주장하지
   않는다.
4. 첫 reference target은 **OpenRadioss 2025**의 `/MAT/ELAST` (`/MAT/LAW1`) block
   format으로 한정한다. Altair 공식 Reference Guide는 이 law가 Hooke's law의
   isotropic linear elasticity이며 density, Young's modulus, Poisson's ratio를
   입력함을 정의한다. 카드에는 explicit `/UNIT` declaration과 mapping report digest를
   남긴다. [OpenRadioss `/MAT/LAW1` reference](https://2025.help.altair.com/2025/hwsolvers/rad/topics/solvers/rad/mat_law1_elast_starter_r.htm)
5. 이 target/model은 `reference_only`이고 production validated, solver-executed,
   released 또는 범용 Radioss 지원으로 표시하지 않는다. `/MAT/LAW1`이 표현하지
   않는 IR constituent는 `unsupported` 또는 `not_applicable`으로 명시하며 silent
   default와 silent approximation을 금지한다.

## Consequences

- T-07의 MVP subset과 T-22/T-25의 reference subset, 그리고 Material management UI를
  우선 구현한다. Process/Lot/Batch, 시험 importer, calibration, virtual specimen,
  review/release는 후속 vertical slice로 남긴다.
- Material, State, Property Set, IR 및 Solver Card는 stable identity와 immutable
  revision을 분리한다. core property는 explicit typed columns와 constraints로 저장하며
  generic EAV 또는 free-form content JSON을 사용하지 않는다.
- 모든 write는 existing authorization/RLS, provenance, audit 및 revision hooks를
  재사용한다. Material/IR/card의 관계는 concrete revision ID만 참조한다.
- OpenRadioss keyword/reference fixture의 변경은 공식 documentation 재검토와 golden
  regression update를 요구한다. 실제 solver executable 실행은 별도 validation task와
  licensed environment가 준비되기 전까지 범위 밖이다.

## Revisit trigger

- 첫 실제 material family, test method/raw format, constitutive model, optimizer,
  solver version/card dialect 또는 validation template가 domain owner에게 승인될 때
- reference model/card가 production release에 사용될 가능성이 생길 때
- 여러 model/exporter가 동일한 typed column을 반복적으로 요구해 common envelope
  확장이 필요한 때
