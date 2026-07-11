# 위험요소, 미결정 사항, 의사결정 로그

## 1. 현재 사실·결정·가정 분리

### 1.1 확정 요구사항 `CONFIRMED`

- 원본 불변, original/normalized unit 보존
- Material/State/Process/Lot-Batch/Condition/Specimen 구분
- outlier 비삭제와 판정 근거
- fitting input/code/config provenance
- solver-neutral Material Model IR
- 7종 plugin extension point
- 완전한 provenance와 revision history
- 대표 MVP raw tensile→release 흐름
- 구체 시험/model/solver/card 미결정

### 1.2 설계 결정 `DECISION`

- 모듈형 모놀리스 + 격리 execution plane
- PostgreSQL authoritative store와 typed provenance relation
- object storage + content digest, Parquet normalized arrays
- stable identity + immutable typed revision
- plugin code의 API process 직접 import 금지
- REST/OpenAPI + durable Job + outbox event
- IR common envelope + plugin-owned model payload
- card mapping report와 no-silent-approximation

### 1.3 작업 지속 가정 `ASSUMPTION`

- single-enterprise on-prem/private cloud first
- reviewed internal/partner plugin only
- runner를 통한 solver orchestration과 manual result attach 모두 계약에 포함
- MVP SLO: 99.5%, RPO 15분, RTO 4시간 등은 초기 목표

사용자 답이 오면 해당 가정과 관련 ADR을 갱신한다.

## 2. Risk register

| ID | 위험 | 가능성 | 영향 | 완화 | Trigger/Owner |
| --- | --- | --- | --- | --- | --- |
| `R-001` | 재료군·시험 표준 결정 지연 | 높음 | 높음 | Stage 0 gate, synthetic core 병행 | production plugin 착수 전 / Product+Test Domain |
| `R-002` | IR이 너무 일반적이거나 특정 solver에 편향 | 중 | 매우 높음 | 3개 실제 instance, exporter preflight, schema review | first model/card design / Model+Solver Domain |
| `R-003` | 단위는 맞지만 stress/strain 의미가 틀림 | 중 | 매우 높음 | quantity kind, measure, explicit transform activity | import/IR validation / Test+Model Domain |
| `R-004` | outlier 자동화가 유효 데이터를 제거 | 중 | 높음 | candidate-only, append-only assessment, scope selection | QC policy / Statistics Domain |
| `R-005` | curve point를 독립 표본으로 계산 | 중 | 높음 | replicate-unit invariant/regression | statistics plugin / Statistics Domain |
| `R-006` | optimizer 수렴을 model validity로 오인 | 높음 | 높음 | fit diagnostic/holdout/solver validation 분리 | UI/release gate / Model Domain |
| `R-007` | parameter non-identifiability/overfitting | 높음 | 높음 | multistart, diagnostics, holdout, validity domain | calibration review / Model Domain |
| `R-008` | solver 간 동일 이름 model의 semantics 차이 | 높음 | 매우 높음 | target/version capability와 mapping report | exporter / Solver Domain |
| `R-009` | commercial solver/license/HPC 불안정 | 중 | 높음 | durable waiting, mock/manual path, failure taxonomy | validation / Platform+CAE |
| `R-010` | plugin dependency·보안 충돌 | 중 | 높음 | isolated signed package, no network, quota | plugin activation / Security+Software |
| `R-011` | raw/object와 DB 불일치 | 중 | 매우 높음 | staged commit, reconciler, digest, restore drill | artifact operations / Platform |
| `R-012` | provenance edge 폭증과 query 지연 | 낮음~중 | 중 | indexes, bounded query, closure cache; graph projection trigger | SLO fail / Data Engineer |
| `R-013` | flexible JSONB가 EAV chaos로 변함 | 중 | 높음 | typed core, registered schema/digest, promotion rule | schema review / Architect |
| `R-014` | microservice 선제 도입으로 delivery 지연 | 중 | 높음 | ADR-001, extraction trigger | architecture change / Architect |
| `R-015` | 역할·RLS 누출 | 중 | 매우 높음 | deny-by-default, dual enforcement, matrix tests | security test / Security |
| `R-016` | audit가 secret/raw payload를 유출 | 중 | 높음 | structured allowlist/redaction | logging review / Security |
| `R-017` | golden snapshot을 무비판 업데이트 | 중 | 매우 높음 | two-person software/domain approval, licensed tier | exporter diff / Solver Domain |
| `R-018` | 경쟁 제품 기능 복제와 IP 문제 | 낮음~중 | 높음 | public facts only, independent schema/UI/algorithms | design review / Product+Legal |
| `R-019` | 실제 파일 변종·누락 metadata가 importer를 압도 | 높음 | 높음 | detect/mapping approval, fixture corpus, issue workflow | sample onboarding / Test Domain |
| `R-020` | regulatory/QMS 기대와 실제 기능 차이 | 중 | 높음 | explicit non-claim, gap assessment | regulated customer / Product+Quality |
| `R-021` | source/fixture data 사용 권한 부족 | 중 | 높음 | test-data manifest/license/classification | fixture addition / Data Owner |
| `R-022` | 한 모델에 맞춘 core hardcoding | 중 | 매우 높음 | architecture tests, model schema/plugin boundary | core PR / Architect+Model Domain |

## 3. 아키텍처 영향 질문

| ID | 질문 | 현재 권장 가정 | 답에 따라 바뀌는 것 |
| --- | --- | --- | --- |
| `OQ-ARCH-001` | 첫 운영은 single enterprise인가 multi-tenant SaaS인가? | single enterprise | tenant key, KMS, operations, billing, isolation certification |
| `OQ-ARCH-002` | untrusted third-party plugin을 MVP에서 허용하는가? | 아니오 | sandbox service, marketplace review, network/runtime isolation |
| `OQ-ARCH-003` | 플랫폼이 solver 실행까지 관장하는가? | runner orchestration + manual attach | job/runner/HPC/license/security 범위 |

## 4. Domain 미결정 사항

### 4.1 MVP blocking — Stage 0에서 결정

| ID | 질문 | 결정 owner |
| --- | --- | --- |
| `OQ-TEST-001` | 대표 재료군은 metal/polymer/elastomer/composite 중 무엇인가? | Product + Test/Model Domain |
| `OQ-TEST-002` | 적용 시험 표준과 specimen geometry는 무엇인가? | Test Domain |
| `OQ-TEST-003` | raw file vendor/format/channel/metadata sample은 무엇인가? | Test Domain/Data Steward |
| `OQ-TEST-004` | 시험조건과 반복 population grouping key는 무엇인가? | Test+Statistics Domain |
| `OQ-PROC-001` | zeroing, smoothing, crop, necking 이후, true conversion rule은 무엇인가? | Test+Model Domain |
| `OQ-MODEL-001` | 첫 구성방정식과 parameterization은 무엇인가? | Constitutive Model Domain |
| `OQ-CAL-001` | objective, weighting, bounds, constraints, optimizer는 무엇인가? | Model+Statistics Domain |
| `OQ-SOLVER-001` | 첫 solver/version/card/units는 무엇인가? | CAE/Solver Domain |
| `OQ-VSPEC-001` | virtual specimen geometry/mesh/BC/output은 무엇인가? | CAE Domain |
| `OQ-VSPEC-002` | validation metric/threshold 및 numerical health rule은 무엇인가? | CAE+Test+Model Domain |

### 4.2 Non-blocking 또는 후속

- `OQ-MAT-001`: composition/process metadata의 canonical 범위
- `OQ-BATCH-001`: 조직 ERP의 Lot/Batch 의미와 key
- `OQ-INST-001`: instrument calibration/uncertainty MVP 범위
- `OQ-STAT-001`: mixed-effects/Gauge R&R/tolerance basis 우선순위
- `OQ-IR-002`: portable symbolic equation representation 필요 여부
- `OQ-IR-003`: covariance/uncertainty 필수 수준
- `OQ-DATA-001`: DIC/video/image/multi-modal raw asset
- `OQ-INTEG-001`: 첫 PLM/LIMS/CAE integration target

## 5. Product·security 미결정 사항

- `OQ-PROD-001`: primary buyer와 first user team
- `OQ-PROD-002`: proprietary/reference data licensing 전략
- `OQ-PROD-003`: project-wide material을 enterprise approved catalog로 승격하는 governance
- `OQ-SEC-002`: classification/export-control 정책
- `OQ-SEC-003`: QMS/전자서명/규제 적용 범위
- `OQ-SEC-004`: retention/legal hold/hard-delete 정책
- `OQ-SEC-005`: partner/external collaboration
- `OQ-OPS-001`: deployment platform, IdP, object storage, scheduler/HPC 구체 제품

## 6. Architecture Decision Log

| ADR | 결정 | 상태 | 이유 | 재검토 trigger |
| --- | --- | --- | --- | --- |
| `ADR-001` | 모듈형 모놀리스 + isolated execution plane | Accepted | domain 변화·transaction 일관성과 운영 단순성 | 독립 팀/scale/security boundary |
| `ADR-002` | PostgreSQL authoritative metadata/provenance | Accepted | FK/ACID/RLS/recursive query | graph SLO/analytics trigger |
| `ADR-003` | object storage + content addressing + Parquet | Accepted | immutable large artifact와 typed columnar data | workload benchmark가 부적합 증명 |
| `ADR-004` | identity와 immutable typed revision 분리 | Accepted | history/reproducibility/lost update 방지 | 없음; core invariant |
| `ADR-005` | typed W3C-PROV-inspired relations | Accepted | relation integrity와 interoperable meaning | provenance standard requirement 변화 |
| `ADR-006` | plugin은 out-of-process Job Spec/Result Manifest | Accepted | dependency/security/reproducibility | trusted embedded-only product로 축소될 때도 유지 권고 |
| `ADR-007` | IR common envelope + plugin payload | Accepted | 공통 governance와 model extensibility 균형 | 3개 model instance 검증 실패 |
| `ADR-008` | exporter preflight + no silent approximation | Accepted | solver semantic loss 통제 | 없음; safety invariant |
| `ADR-009` | PostgreSQL durable job/outbox first | Proposed/Accepted for MVP | 운영 구성 최소화 | throughput/workflow complexity SLO 실패 |
| `ADR-010` | single-enterprise first | Assumed | 현재 요구와 보안 비용 | 사용자 답변/SaaS 사업 결정 |
| `ADR-011` | reviewed plugins only | Assumed | MVP 위험·범위 통제 | marketplace 사업 결정 |
| `ADR-012` | solver runner + manual attach | Assumed | virtual validation provenance 완성 | 사용자가 input/output-only 선택 |

## 7. Decision 변경 절차

1. 문제와 실제 evidence/benchmark를 기록한다.
2. 기존 ADR이 해결한 품질 속성을 명시한다.
3. 최소 두 대안을 비용·위험·migration과 비교한다.
4. domain/security 영향을 관련 전문가가 검토한다.
5. 새 ADR을 superseding 상태로 추가한다. 과거 ADR을 지우지 않는다.
6. schema/contract/data migration과 rollback/forward-fix 계획을 연결한다.

## 8. 공개 사실과 설계 추론의 경계

- 경쟁 제품의 공식 자료가 revision, workflow, solver cards, fitting/validation 기능을 설명한다는 것은 `FACT-PUBLIC`이다.
- 그 제품들이 이 문서의 PostgreSQL schema, W3C mapping, plugin contract, IR 구조를 사용한다는 주장은 하지 않는다.
- 이 패키지의 architecture/domain model은 공개 기능과 사용자 요구를 바탕으로 독립적으로 도출한 `DECISION`이다.
- AI-powered 기능이 경쟁 제품에 있다는 사실은 확인되지만 MVP에 AI가 필요하다는 결론으로 연결하지 않는다.

