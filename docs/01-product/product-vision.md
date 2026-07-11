# 제품 비전, 사용자 역할, 핵심 흐름, 범위

## 1. 제품 비전

재료시험 파일과 개인별 스크립트, spreadsheet, solver card가 분산된 상태를 없애고, **어떤 시험과 처리·보정·검증을 거쳐 어떤 solver card가 승인되었는지 설명할 수 있는 재료모델 공급망**을 만든다.

제품의 핵심 가치는 단순한 material database가 아니라 다음 질문에 즉시 답하는 것이다.

- 이 카드가 어떤 material, state, lot/batch, specimen, test condition에서 나왔는가?
- 원본 파일과 원본 단위는 무엇이며 누가 언제 가져왔는가?
- 어떤 QC·outlier 판정과 전처리가 적용되었는가?
- 어떤 model·optimizer·설정·코드 버전으로 fitting했는가?
- fitting 데이터와 validation 데이터는 어떻게 구분했는가?
- neutral IR이 대상 solver에서 정확히 표현되었는가, 근사 또는 누락은 무엇인가?
- 누가 검토·승인했고 현재 유효한 release는 무엇인가?

## 2. 제품 원칙

1. 데이터의 출처를 결과보다 먼저 보여 준다.
2. 원본은 고치지 않고 새 파생 revision을 만든다.
3. 단위 변환과 curve 변환은 숨은 UI 동작이 아니라 versioned activity다.
4. 통계적 이상과 물리적 부적합을 구분한다.
5. 평균 곡선만 남기지 않고 개별 specimen을 추적한다.
6. fitting 성공과 물리적 타당성, solver 검증, 승인 상태를 구분한다.
7. solver card는 neutral model의 target-specific projection이다.
8. core는 시험 표준·구성모델·솔버를 알지 않는다.
9. 자동화가 전문가 판단을 대체하지 않고 판단 근거를 고정한다.
10. 웹 UI는 engineering calculation engine, validation, data pipeline을 조작하고 검토하는 shell이다.

## 3. 목표 사용자와 역할

| 역할 | 주 책임 | 생성/판정하는 항목 |
| --- | --- | --- |
| Test Engineer | 시험 계획·시편·조건·장비·원본 등록 | Campaign, Specimen, Test Run, Raw Asset, 시험 QC |
| Lab Data Steward | 메타데이터·단위·식별자 품질 관리 | Dataset mapping, metadata correction revision, data-quality issue |
| Statistical Analyst | 반복시험 산포·outlier candidate·불확도 분석 | Statistical Analysis Run, QC Observation, outlier recommendation |
| Material Modeler | 전처리 recipe, 구성모델 선택, calibration | Processed Dataset, Calibration Run, Material Model IR revision |
| CAE Analyst | 대상 solver mapping, card 생성, virtual specimen 검증 | Solver Card, Validation Plan/Run, mapping acceptance |
| Domain Reviewer | 통계·구성모델·검증 근거 기술 검토 | Review decision, requested change |
| Release Approver | 조직 정책에 따른 최종 발행 승인 | Released Material Model Package |
| Material Data Consumer | 승인된 재료모델 검색·사용 | 다운로드·사용 기록; 데이터 변경 권한 없음 |
| Plugin Maintainer | 시험·모델·solver 확장 구현·서명 | Plugin Package, manifest, compatibility evidence |
| Platform Administrator | 사용자·정책·runner·보관·운영 관리 | Identity mapping, policy, runner registration |
| Auditor | 전체 이력과 승인 근거 열람 | read-only audit/provenance report |

한 사용자가 여러 역할을 가질 수 있지만 production release에서는 작성자와 최종 승인자의 분리를 기본 정책으로 권고한다.

## 4. 핵심 사용자 흐름

### 4.1 시험 원본 수집

1. Test Engineer가 campaign, material state, lot/batch, specimen, condition을 선택하거나 생성한다.
2. 파일을 upload session으로 등록한다.
3. Importer plugin이 형식을 탐지하고 column/unit mapping 초안을 만든다.
4. 사용자가 mapping을 확인한다.
5. 플랫폼은 원본 바이트와 digest를 고정하고 normalized dataset revision을 별도로 생성한다.
6. 누락·모순 메타데이터는 issue로 남기며 원본 파일은 수정하지 않는다.

### 4.2 반복시험 QC·산포 분석

1. 사용자가 비교 population의 grouping key를 확인한다.
2. specimen-level QC와 scalar feature extraction을 실행한다.
3. Statistical Analyzer가 개별 곡선, scalar distribution, pointwise curve band, candidate outlier를 생성한다.
4. 사용자는 outlier candidate를 `accept`, `exclude-from-specific-analysis`, `needs-retest`, `not-outlier`로 판정하고 근거를 기록한다.
5. exclusion은 해당 analysis/calibration selection에만 적용되고 원본·dataset을 삭제하지 않는다.

### 4.3 전처리와 구성방정식 보정

1. Material Modeler가 입력 dataset revision과 selection을 고정한다.
2. Processor recipe를 구성하고 preview 후 실행한다.
3. 처리 결과와 각 단계의 diagnostics가 새 dataset revision으로 생성된다.
4. Material Model plugin과 Calibrator plugin을 선택한다.
5. parameter bounds, objective, weights, constraints, seed, multistart를 설정한다.
6. calibration 결과, residual, convergence, uncertainty, applicability를 검토한다.
7. 선택한 결과로 Material Model IR revision을 생성한다.

### 4.4 카드 생성과 가상 시편 검증

1. CAE Analyst가 solver, solver version, unit system, exporter version을 선택한다.
2. exporter capability check가 `exact`, `transformed`, `approximated`, `unsupported` mapping을 보고한다.
3. unsupported가 있으면 생성이 중단된다. approximation은 명시적 승인 없이는 release 대상이 될 수 없다.
4. card와 mapping report를 생성한다.
5. versioned virtual specimen template 및 runner로 solver를 실행하거나 외부 실행 결과를 반입한다.
6. 실험 곡선과 solver response, 수치 안정성, 종료 상태, metric을 저장한다.

### 4.5 검토·승인·발행

1. 작성자가 release candidate를 제출한다.
2. 시스템이 provenance completeness, required validations, exporter mapping, open issue를 검사한다.
3. Domain Reviewer가 기술 검토하고 승인 또는 변경 요청한다.
4. Release Approver가 최종 승인한다.
5. immutable release manifest, IR, cards, validation report, provenance snapshot을 발행한다.
6. supersede/withdraw는 기존 release를 삭제하지 않고 새 lifecycle event로 처리한다.

## 5. 대표 MVP 수직 기능

| 단계 | MVP 산출물 | 상태 |
| --- | --- | --- |
| 반복 인장시험 업로드 | raw asset, import mapping, test-run linkage | `CONFIRMED` |
| 메타데이터·단위 정규화 | normalized dataset revision | `CONFIRMED` |
| 시편별 QC·산포 | QC observations, scalar/curve statistics | `CONFIRMED` |
| 곡선 전처리 | processing recipe/run, processed dataset | `CONFIRMED` |
| 구성방정식 fitting | calibration run, parameter set, diagnostics | model `TBD` |
| 한 종류 solver card | card artifact, mapping report | solver/card `TBD` |
| 가상 시편 검증 | validation run, extracted response, comparison | template/solver `TBD` |
| 검토·승인·발행 | review decisions, release package | `CONFIRMED` |

## 6. MVP 범위

- 단일 기업 내 organization/project space
- 웹 기반 metadata·workflow·review UI
- 대용량 streaming upload와 immutable raw storage
- 한 종류의 반복 인장시험 importer plugin
- original 및 normalized unit 동시 보존
- specimen/test-run 중심 dataset 및 curve visualization
- 기본 scalar·curve 산포, QC rule, outlier adjudication
- versioned processor recipe 및 실행
- 한 개의 Material Model plugin과 한 개 이상의 Calibrator algorithm
- solver-neutral IR validation
- 한 solver exporter
- 한 virtual specimen template과 수동/runner 실행 계약
- OIDC 기반 인증, RBAC, project/data classification
- complete provenance, audit, revision, review, release
- REST API, async job, event/outbox 계약
- plugin manifest, compatibility test kit, synthetic reference plugins

구체 모델·solver 선택 전에는 synthetic reference plugin으로 core 계약만 검증한다.

## 7. 비범위

- 경쟁 제품의 UI, schema, proprietary format, 알고리즘 복제
- 상용 reference material library의 재배포
- 모든 인장시험 표준·재료군·구성모델·solver 지원
- LIMS, PLM, ERP, SDMS 전체 대체
- 시험기 직접 제어와 laboratory scheduling
- 범용 mesh/pre-post processor
- 상용 solver 자체 제공 또는 라이선스 우회
- 자동으로 생성된 결과의 무인 production 승인
- AI 기반 누락 물성 예측·재료 추천·생성형 검색
- regulatory QMS 또는 전자서명 규정 준수 인증 자체
- graph database, data lakehouse, microservice fleet의 선제 도입

## 8. 제품 성공 지표

### 8.1 MVP acceptance metric

- 선정된 한 개 vertical scenario가 raw file에서 approved release까지 끊김 없이 실행된다.
- release manifest의 모든 산출물이 원본까지 역추적된다.
- 같은 입력·plugin digest·설정으로 deterministic step을 재실행하면 동일 digest 또는 허용 오차 내 동일 수치가 나온다.
- 원본 asset을 application API로 수정·삭제할 수 없다.
- unit mapping 누락 또는 의미 불일치가 silent conversion으로 통과하지 않는다.
- exporter의 unsupported mapping이 card 생성 성공으로 표시되지 않는다.
- outlier exclusion 전후 결과를 재현하고 비교할 수 있다.
- 승인되지 않은 model/card를 production channel에서 조회하거나 내려받을 수 없다.

### 8.2 후속 운영 지표

- 시험 원본에서 첫 QC report까지 걸린 lead time
- 수작업 단위·column mapping 재작업률
- 중복 시험 및 중복 model/card 수
- release당 provenance completeness 비율
- calibration/validation 실패 원인 분류와 재실행 성공률
- solver card golden regression pass rate
- 승인된 model의 downstream 사용량과 superseded version 사용 경고 건수

## 9. 제품이 하지 말아야 할 오해

- 높은 R² 또는 낮은 fitting error는 물리 모델이 타당하다는 뜻이 아니다.
- 평균 곡선은 반복시험 population 전체를 대체하지 않는다.
- neutral IR은 모든 solver 표현을 완전히 동일하게 만들지 않는다.
- provenance graph가 있다고 결과가 자동으로 신뢰되는 것은 아니다. 입력·방법·검토의 품질이 필요하다.
- plugin 방식은 도메인 검증 책임을 core 개발자에게서 없애지 않는다. 책임의 위치와 계약을 분명하게 만든다.

