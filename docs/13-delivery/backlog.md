# Epic, Story, Task 수준 상세 작업명세

## 1. 사용 규칙

- 우선순위 `P0`: MVP vertical slice에 필수, `P1`: release hardening, `P2`: 후속.
- 각 Task는 독립적인 PR 또는 작게 나눈 연속 PR의 완료 단위다.
- `담당`에서 `Software`는 software developer, `Domain`은 재료시험·통계·구성모델·solver 전문가를 뜻한다.
- production 시험/model/solver plugin은 `TBD` 결정 전 synthetic reference만 구현한다.

## 1.1 2026-07-13 제품 우선순위 결정

ADR-006에 따라 다음 delivery 순서를 적용한다.

1. `T-07`의 Material/State/typed Property MVP subset과 Material management UI
2. `T-22`의 reference linear-elastic IR subset
3. `T-25`/`T-26`의 OpenRadioss `/MAT/ELAST` reference card, preflight, download 및 golden subset
4. 그 다음 Test/Dataset→Processing/QC/Statistics→Calibration→Validation/Release 수직 slice

이는 foundation을 폐기하는 결정이 아니다. T-03~T-06, T-09~T-10, T-13~T-18은 새
domain write와 UI가 재사용해야 하는 product substrate다. Process/Lot/Batch, production
solver plugin, fitting, virtual specimen 및 release는 첫 card slice의 필수 조건이 아니다.

## 1.2 현재 실행 순서: P0-1 → P0-2 → P1 → P2

ADR-0019는 이미 구현된 foundation과 Material-to-card 수직 기능을 유지하면서 다음 작업을
아래 순서로 실행하도록 결정한다. 이 표의 표기는 현재 제품 increment의 실행 wave이며,
각 Task 제목의 기존 우선순위 표기를 삭제하거나 과거 완료 상태를 되돌리지 않는다.

| Wave | 범위 | 관련 Task | Exit gate |
| --- | --- | --- | --- |
| `P0-1` | Docker Compose 전체 서비스와 live PostgreSQL 통합검증 | T-04~T-18, T-31, T-37 | migration/seed/API/web가 동작하고 PostgreSQL marker suite가 skip 0/failure 0이며 DSN을 유지한 CI-equivalent suite가 통과한다. |
| `P0-2` | 복수 반복시험 Selection, 명시적 processing/alignment, 통계·QC·outlier scope와 연결 UI | T-19~T-21, T-32/T-33 | 개별 curve를 보존한 채 raw/normalized/processed/statistical view가 구분되고, 계산·판정이 immutable revision/provenance를 가지며 PostgreSQL/RLS/API/browser test가 통과한다. |
| `P1` | bounded nonlinear reference calibration, workbench, calibrated IR 승격, 기존 OpenRadioss/Abaqus card 연결, solver-independent holdout/material-model validation | T-22~T-26, T-33, T-D02 | candidate diagnostics와 사람 선택을 거쳐 새 IR revision/card가 생성되고 calibration/holdout overlap policy와 regression evidence가 명시된다. |
| `P2` | Catalog genealogy와 production domain 확장, 실제 solver/HPC 검증, 운영·복구·release hardening | T-07/T-08 잔여, T-27/T-28 production 범위, T-34~T-38, T-D01~T-D03 production 범위 | 관련 domain/solver/운영 결정과 승인 fixture가 준비되고 각 Task gate가 통과한다. |

### P0-1 실행 체크리스트

1. Windows에서는 WSL 2와 Docker Desktop/Compose v2를 준비하고 Docker Engine을 실행한다.
2. `deploy/compose/docker-compose.demo.yml`을 build/up하여 PostgreSQL 16, migration/bootstrap,
   non-owner API, worker, web, reference-plugin check, synthetic seed 상태를 확인한다.
3. `--profile test`의 localhost/tmpfs `postgres-test`를 시작하고
   `127.0.0.1:54330`의 disposable owner DSN을 `CMP_TEST_POSTGRES_DSN`으로 설정한다.
4. `pytest -m postgresql tests/integration`을 실행한다. 현재 관측된 62개는 고정 계약이
   아니며 완료 조건은 PostgreSQL marker의 **skip 0/failure 0**이다.
5. 같은 DSN으로 CI-equivalent suite를 실행하고 결과를 `IMPLEMENTATION_STATUS.md`에 기록한다.

별도 PostgreSQL 설치는 필수가 아니다. Compose의 PostgreSQL을 사용하면 된다. production,
공유 개발, 또는 보존해야 하는 DB를 통합시험 DSN으로 사용해서는 안 된다.

**완료 증거 (2026-07-27):** Docker Engine 29.6.1/Compose 5.3.0에서 PostgreSQL 16,
migration/bootstrap, non-owner API, worker, web, reference-plugin check, synthetic seed가
정상 실행됐다. localhost 전용 tmpfs `postgres-test` profile로 PostgreSQL marker suite
`62 passed / 0 skipped / 0 failed`, 같은 DSN의 CI-equivalent suite `452 passed`, web
Vitest `21 passed`를 기록했다. 브라우저 smoke는 Material/State/property/Dataset/IR과
OpenRadioss/Abaqus 카드 preview/download를 확인했다. 따라서 현재 실행 wave는 `P0-2`다.

이 문단은 `P0-1` 완료 당시의 관측 기록이다. 이후 `P0-2`와 bounded reference `P1`은 아래
implementation note의 범위로 완료됐으며, 현재 다음 실행 wave는 `P2`다.

### P0-2 구현 순서

1. 여러 concrete Dataset revision을 pin하는 Selection과 specimen/Test Run 단위 membership
2. explicit processing step으로서 alignment/resampling과 결과 Dataset revision
3. specimen-level scalar statistics, pointwise curve band, QC observation
4. outlier candidate와 사람 assessment, calibration별 exclusion scope
5. Material State의 반복 curve 비교 및 raw/normalized/processed/statistical 화면

Display downsampling은 계산 입력이 아니며, alignment/resampling/extrapolation은 브라우저나
통계 코드가 암묵적으로 수행하지 않는다.

### P1 reference 범위

첫 nonlinear calibration은 ADR-0019의 non-production reference Voce saturation hardening과
SciPy `least_squares` adapter를 권장 가정으로 사용한다. 이는 production 구성방정식이나
optimizer policy 결정이 아니다. `TestModeAdapter`, `MaterialModelEvaluator`, `ObjectiveEngine`,
`OptimizerAdapter`를 분리하고 initial value/bounds/scaling/seed/multistart/stopping/failure,
objective terms/prediction/residual/convergence/warning/identifiability/uncertainty status를
명시적으로 보존한다.

선택된 Candidate는 solver-neutral calibrated IR revision을 append한다. 기존
`isotropic-tabulated-plasticity` IR로 투영할 때 sampling grid, transform profile, Artifact
digest와 source Candidate/Selection을 고정한 별도 activity/revision을 만들고, 그 revision에서
OpenRadioss/Abaqus preflight/preview/download를 실행한다. 실제 solver 실행·data-check·HPC와
solver qualification은 제품 소유자 결정에 따라 `P2`로 미루며, P1은 material-model response와
겹치지 않는 holdout Selection 검증까지만 포함한다.

## E-01. 제품 기준선과 계약 기반

### S-01.1. 저장소와 아키텍처 규칙을 고정한다

#### T-01. 모듈형 모놀리스 저장소 skeleton 및 ADR 도입 — `P0`

- **목적:** bounded module, dependency direction, API/worker/runner 배포 단위를 코드 구조로 강제한다.
- **입력과 출력:** 입력은 이 설계 패키지와 module 목록; 출력은 repository skeleton, dependency policy, ADR template, developer commands.
- **영향 데이터/API:** DB/API 변경 없음; 향후 모든 module namespace와 package boundary에 영향.
- **범위/제외:** module package, lint/type/test config, architecture test 포함; business 기능·UI 구현 제외.
- **선행 작업:** 없음.
- **완료 조건:** API와 worker가 empty health endpoint로 실행되고 core domain이 framework adapter를 import하지 않으며 ADR-001~005가 repository에 있다.
- **테스트:** 단위—package import smoke; 통합—API/worker startup; 회귀—금지 dependency를 넣은 fixture가 architecture test에서 실패.
- **담당:** Software 주 담당; Domain은 module 용어와 경계 검토.

#### T-02. Contract 및 versioning baseline — `P0`

- **목적:** REST, event, job, artifact, plugin, IR schema의 버전 규칙과 validation pipeline을 만든다.
- **입력과 출력:** 입력은 contract 문서; 출력은 OpenAPI/AsyncAPI skeleton, JSON Schema registry, compatibility policy, code-generation command.
- **영향 데이터/API:** `/api/v1/health`, schema registry metadata; 모든 향후 public contract.
- **범위/제외:** 빈 contract와 validation CI 포함; production resource endpoint 구현 제외.
- **선행 작업:** T-01.
- **완료 조건:** contract lint/generation이 재현되고 breaking-change detector가 CI에서 동작한다.
- **테스트:** 단위—schema positive/negative; 통합—generated client가 health API 호출; 회귀—optional→required 변경 fixture가 breaking으로 탐지.
- **담당:** Software 주 담당; Domain은 scientific schema naming/semantic review.

## E-02. Identity, 권한, 감사

### S-02.1. Enterprise identity와 data boundary를 적용한다

#### T-03. OIDC principal 및 request security context — `P0`

- **목적:** enterprise user/service identity를 검증하고 organization/project context를 모든 command에 전달한다.
- **입력과 출력:** 입력은 OIDC issuer/client/group mapping config; 출력은 Principal, token validation, request actor/context.
- **영향 데이터/API:** `identity.principal`, `identity.external_identity`; 인증 middleware와 `/me` endpoint.
- **범위/제외:** OIDC와 development test IdP adapter 포함; password/MFA 자체 구현 제외.
- **선행 작업:** T-01, T-02.
- **완료 조건:** user/service token이 actor로 resolve되고 invalid issuer/audience/expired token이 거부된다.
- **테스트:** 단위—claim mapping; 통합—test IdP login/service credential; 회귀—token confusion, missing project context.
- **담당:** Software 주 담당; Domain은 사용자 역할 목록 검토.

#### T-04. RBAC·ABAC와 PostgreSQL RLS — `P0`

- **목적:** organization/project/classification에 대한 deny-by-default 접근을 service와 DB 양쪽에서 강제한다.
- **입력과 출력:** 입력은 principal/context/role binding; 출력은 authorization decision과 RLS session context.
- **영향 데이터/API:** `identity.role_binding`, project/classification columns; 모든 resource query/command.
- **범위/제외:** MVP role matrix와 project isolation 포함; 복잡한 export-control nationality policy 제외.
- **선행 작업:** T-03, 각 domain table의 tenant columns.
- **완료 조건:** application role은 RLS bypass가 아니고 권한 밖 row/search count/artifact token을 볼 수 없다.
- **테스트:** 단위—policy matrix; 통합—두 organization/project fixture; 회귀—list/count/facet/FK-error information leakage.
- **담당:** Software 주 담당; Domain/Product가 role-action matrix 승인.

### S-02.2. 변경과 승인을 감사한다

#### T-05. Append-only audit event와 tamper evidence — `P1`

- **목적:** 보안·data revision·job·approval·plugin 관리 행위를 변경 불가능한 audit로 남긴다.
- **입력과 출력:** 입력은 command outcome/security event; 출력은 hash-linked audit event, export segment, integrity report.
- **영향 데이터/API:** `audit.event`, `audit.segment_root`; auditor query/export API.
- **범위/제외:** append-only DB와 periodic root 포함; 외부 SIEM/WORM vendor connector 제외.
- **선행 작업:** T-03, T-04.
- **완료 조건:** update/delete가 DB privilege로 막히고 chain 검사가 변조 fixture를 탐지한다.
- **테스트:** 단위—canonical hash/redaction; 통합—command transaction audit; 회귀—event reorder/delete/mutation detection.
- **담당:** Software 주 담당; Security/Auditor가 field·retention 검토.

## E-03. Revisioned catalog와 시험 문맥

### S-03.1. 안정 identity와 immutable revision을 공통 구현한다

#### T-06. Aggregate revision kernel — `P0`

- **목적:** identity/head pointer, immutable revision, optimistic concurrency, lifecycle projection의 공통 pattern을 구현한다.
- **입력과 출력:** 입력은 create/revise command와 expected revision; 출력은 새 revision, content hash, provenance/audit hook.
- **영향 데이터/API:** typed aggregate/revision 공통 columns; `POST .../revisions`, ETag.
- **범위/제외:** reusable application/repository pattern 포함; generic EAV revision table 제외.
- **선행 작업:** T-01, T-02.
- **완료 조건:** concurrent stale update가 거부되고 released content row는 update되지 않는다.
- **테스트:** 단위—canonicalization/hash/revision number; 통합—concurrent transaction; 회귀—head-following input과 released-row mutation 차단.
- **담당:** Software 주 담당; Domain은 correction/revision semantics 검토.

### S-03.2. 재료·공정·시편·시험을 분리한다

#### T-07. Material/State/Process/Lot/Batch domain — `P0`

- **Expanded vertical progress (2026-07-16):** Material, Material State, and typed basic Property
  Set revisions are joined by governed Process Definition, Material Lot/Batch, and State Genealogy
  stable identities with immutable typed revisions. Genealogy revisions pin exact State, Process,
  and Lot revisions; role, tenant/classification, and Material-revision equality are enforced in
  the service and PostgreSQL. Protected APIs and the Material State UI create/select/revise these
  links. Process-run input/output graphs, lot split/merge, multi-lot acceptance fixtures, and ERP
  integration remain pending, so this is still a bounded T-07 subset rather than the full Task.

- **목적:** material identity, state, process definition/run, lot, batch 및 input/output 관계를 구현한다.
- **입력과 출력:** 입력은 metadata/revision commands; 출력은 typed catalog revisions와 batch genealogy.
- **영향 데이터/API:** `catalog.material*`, `material_state*`, `process*`, `lot*`, `batch*`, `batch_input`; catalog CRUD/revision/search API.
- **범위/제외:** canonical 공통 필드와 extension schema 포함; 실제 ERP connector와 상세 화학조성 ontology 제외.
- **선행 작업:** T-06, T-04.
- **완료 조건:** multi-lot→batch, lot split, process-run output fixture가 저장·조회되고 state와 test condition이 혼동되지 않는다.
- **테스트:** 단위—domain invariants; 통합—genealogy/query/RLS; 회귀—cycle, invalid material/state, cross-project relation 차단.
- **담당:** Software 구현; Domain이 Lot/Batch/process 의미와 fixture 승인.

#### T-08. Specimen/Test Method/Campaign/Run/Instrument domain — `P0`

- **MVP progress (2026-07-14):** A deliberately narrow reference tensile subset is implemented:
  `Specimen`, the fixed `reference_uniaxial_tensile` Test Method, and `Test Run` stable identities
  with immutable typed revisions. Test Runs pin concrete Specimen/Method revisions and retain
  optional temperature/crosshead-speed metadata. Campaign, Instrument, condition snapshots, and
  production test-method variants remain pending; this is not a claim that the complete T-08 task
  is finished.

- **목적:** 물리 specimen, method definition, campaign, actual run, condition snapshot, instrument/calibration reference를 구현한다.
- **입력과 출력:** 입력은 specimen/test metadata; 출력은 immutable run context와 completeness issue.
- **영향 데이터/API:** `catalog.specimen*`, `testing.test_method*`, `campaign*`, `test_run*`, `condition_snapshot`, `instrument*`; testing API.
- **범위/제외:** plugin extension metadata validation 포함; 시험기 직접 제어·scheduling 제외.
- **선행 작업:** T-06, T-07, T-17 schema registry.
- **완료 조건:** test run이 구체 specimen, method revision, condition, instrument를 고정하고 correction revision을 지원한다.
- **테스트:** 단위—required metadata/physical identity rule; 통합—campaign→run→specimen lineage; 회귀—method head 변경이 과거 run을 바꾸지 않음.
- **담당:** Software 구현; Test Domain Expert가 required metadata와 fixture 승인.

## E-04. 원본 수집, artifact, dataset, 단위

### S-04.1. 원본 바이트를 변경 불가능하게 수집한다

#### T-09. Streaming multipart upload와 Raw Asset 생성 — `P0`

- **목적:** 대용량 파일을 API 메모리에 적재하지 않고 수집하고 test run/actor 문맥을 기록한다.
- **입력과 출력:** 입력은 upload request/chunks/completion; 출력은 Raw Asset, Ingestion Event, SHA-256/size/MIME manifest.
- **영향 데이터/API:** `artifact.upload_session`, `raw_asset`, `ingestion_event`; `/uploads`, complete, artifact metadata API.
- **범위/제외:** resumable upload와 duplicate content detection 포함; file parser/normalization 제외.
- **선행 작업:** T-03, T-04, T-06, object-store adapter.
- **완료 조건:** 2 GiB test 또는 환경 허용 최대 fixture를 streaming하고 digest 불일치를 거부한다.
- **테스트:** 단위—part manifest/digest; 통합—object store multipart, resume, cancel; 회귀—overwrite, path injection, cross-project token.
- **담당:** Software 주 담당; Test Domain은 원본 metadata 검토.

#### T-10. Content-addressed artifact와 integrity reconciler — `P0`

- **목적:** raw/derived/release object의 immutable key, state transition, DB/object mismatch 탐지를 구현한다.
- **입력과 출력:** 입력은 staged object/expected role/schema; 출력은 available artifact 또는 integrity issue.
- **영향 데이터/API:** `artifact.artifact`, `artifact_pending`, integrity status/job; artifact download-token API.
- **범위/제외:** staging→final, digest/size, orphan/missing reconciliation 포함; 장기 archive vendor 구현 제외.
- **선행 작업:** T-09, T-15 job engine.
- **완료 조건:** missing/orphan/corrupt fixture를 탐지하고 released/raw object overwrite가 불가능하다.
- **테스트:** 단위—content key/state machine; 통합—copy/failure/reconcile; 회귀—DB success/object missing, duplicate finalize idempotency.
- **담당:** Software 주 담당; Security가 access/retention 검토.

### S-04.2. Import mapping과 canonical dataset을 만든다

#### T-11. Importer detect·mapping approval·import orchestration — `P0`

- **Reference progress (2026-07-18):** The bounded synthetic UTF-8 CSV header adapter is
  implemented as a non-production `reference_inline` slice. It persists immutable Detection
  Reports that always remain `needs_input`, stable Import Mapping identities with immutable
  human-confirmed revisions, and Processing Import Runs pinned to concrete Test Run, Raw
  Artifact, and Mapping revisions. The Material State workbench uses the separate
  detect → approve → import API flow. This is not a production generic importer plugin or a claim
  of automatic column/unit inference.
- **목적:** format 탐지와 사용자 승인 mapping, 실제 import를 분리해 silent guessing을 막는다.
- **입력과 출력:** 입력은 Raw Asset, hints, Importer plugin; 출력은 Detection Report, Mapping Revision, normalized import job/result.
- **영향 데이터/API:** `testing.import_mapping*`, `processing.import_run`; `/imports:detect`, `/import-mappings`, `/imports`.
- **범위/제외:** synthetic importer와 generic UI contract 포함; production tensile format은 `TBD` 후 plugin task로 분리.
- **선행 작업:** T-09, T-15, T-17, T-18.
- **완료 조건:** ambiguous column/unit가 `needs_input`이 되고 승인 mapping digest가 import input으로 고정된다.
- **테스트:** 단위—mapping schema/confidence rule; 통합—detect→approve→import; 회귀—mapping 변경 후 과거 import 재현, low-confidence auto-commit 차단.
- **담당:** Software framework; Test Domain이 production mapping/plugin 승인.

#### T-12. Dataset Revision, channel semantics, 단위 normalization — `P0`

- **MVP progress (2026-07-14):** One reference tensile CSV path is implemented. A confirmed mapping
  creates an immutable raw Dataset revision from a completed Raw Asset/Artifact and appends one
  normalized SI Parquet revision under the same stable Dataset identity. The implementation stores
  typed engineering strain/stress channel semantics, preserves original units, rejects guessing,
  and exposes a bounded raw/normalized curve preview. Generic importer detection/approval and
  arbitrary Dataset schemas remain pending; this is not a claim that the complete T-12 task is
  finished.

- **목적:** original/normalized unit과 quantity kind, channel schema를 보존한 Parquet dataset revision을 구현한다.
- **입력과 출력:** 입력은 importer output/artifacts/schema; 출력은 Dataset Revision Manifest, channel metadata, unit conversion activity.
- **영향 데이터/API:** `datasets.dataset*`, `dataset_channel`, artifact refs; dataset revision/view API.
- **범위/제외:** UCUM-compatible code, original unit text, engineering/true semantic 구분 포함; 모든 단위 ontology 완성 제외.
- **선행 작업:** T-10, T-11, T-13 provenance.
- **완료 조건:** normalized data를 원본 unit으로 검증 가능하고 unit/quantity mismatch가 blocking diagnostic을 만든다.
- **테스트:** 단위—factor/offset/dimension/quantity kind; 통합—Parquet schema roundtrip; 회귀—MPa↔Pa, %↔1, engineering vs true confusion, locale decimal.
- **담당:** Software 구현; Domain이 quantity-kind mapping과 허용 conversion 승인.

## E-05. Provenance, job, event 신뢰성

### S-05.1. 전체 lineage를 typed relation으로 저장한다

#### T-13. W3C PROV 매핑 typed schema와 write service — `P0`

- **목적:** Entity/Activity/Agent 및 usage/generation/derivation/revision/association을 typed relation으로 구현한다.
- **입력과 출력:** 입력은 domain revision/run commit hook; 출력은 provenance node/relation과 completeness status.
- **영향 데이터/API:** `provenance.*`; internal write service와 entity lookup.
- **범위/제외:** core relation과 cycle/invariant 포함; RDF/graph DB/export 제외.
- **선행 작업:** T-06.
- **완료 조건:** output entity에 primary generation이 하나이고 run input/agent가 연결된다.
- **테스트:** 단위—relation constraints/cycle; 통합—raw→dataset activity; 회귀—orphan output, mutable head input, duplicate generation 차단.
- **담당:** Software 주 담당; Domain은 activity/role vocabulary 검토.

#### T-14. Upstream/downstream/impact query와 completeness gate — `P0`

- **목적:** release→raw 역추적, raw→release 영향 분석, 고아/누락 검사를 제공한다.
- **입력과 출력:** 입력은 provenance root/query filters; 출력은 bounded subgraph, paths, completeness report.
- **영향 데이터/API:** lineage read model/index; `/lineage/...` endpoints.
- **범위/제외:** recursive CTE, pagination/limits, project filtering 포함; arbitrary graph analytics 제외.
- **선행 작업:** T-13, T-04.
- **완료 조건:** known DAG fixture를 양방향 조회하고 권한 경계를 넘지 않으며 release gate가 누락을 차단한다.
- **테스트:** 단위—path/cycle/limit; 통합—10-hop/10k-edge SLO fixture; 회귀—classification leak, duplicate path, graph explosion guard.
- **담당:** Software 주 담당; Auditor/Domain이 report 해석 검토.

### S-05.2. 긴 계산을 durable하게 실행한다

#### T-15. PostgreSQL Job/Attempt/Lease engine — `P0`

- **목적:** import, processing, statistics, calibration, export, validation의 장시간 실행과 재시작을 관리한다.
- **입력과 출력:** 입력은 immutable Job Spec/resource policy; 출력은 Job/Attempt states, progress, Result Manifest reference.
- **영향 데이터/API:** `jobs.job`, `job_attempt`, `runner`, lease fields; `/jobs`, cancel/retry.
- **범위/제외:** claim/heartbeat/timeout/cancel/retry 포함; general-purpose DAG workflow engine 제외.
- **선행 작업:** T-01, T-02.
- **완료 조건:** worker crash 후 lease expiry/new attempt, duplicate finalize idempotency, terminal failure taxonomy가 동작한다.
- **테스트:** 단위—state machine/retry policy; 통합—concurrent claim/crash/cancel; 회귀—double execution commit, stale heartbeat, retry of invalid input.
- **담당:** Software 주 담당; Domain은 error taxonomy/자동 retry 허용 범위 검토.

#### T-16. Transactional outbox와 artifact reconciliation — `P0`

- **목적:** DB commit과 domain event를 일치시키고 object/DB 비원자성을 복구한다.
- **입력과 출력:** 입력은 committed domain transaction/pending artifact; 출력은 CloudEvent, outbox delivery, reconciliation issue.
- **영향 데이터/API:** `events.outbox`, consumer inbox, reconciliation jobs; AsyncAPI.
- **범위/제외:** at-least-once, dedup, sequence 포함; Kafka 등 외부 broker 필수 도입 제외.
- **선행 작업:** T-10, T-15, T-02.
- **완료 조건:** event 누락/유령 event가 없고 duplicate delivery가 중복 side effect를 만들지 않는다.
- **테스트:** 단위—CloudEvent/schema/dedup; 통합—transaction rollback/publisher crash; 회귀—out-of-order, duplicate, poison event.
- **담당:** Software 주 담당; Integration owner가 event catalog 검토.

## E-06. Plugin SDK와 격리 실행

### S-06.1. Plugin을 등록·검증하고 core에서 분리한다

#### T-17. Plugin manifest/package/schema registry — `P0`

- **목적:** plugin identity/version/digest/capability/schema/resource/security policy를 immutable하게 등록한다.
- **입력과 출력:** 입력은 signed package/manifest/SBOM; 출력은 validated Plugin Package와 activation eligibility.
- **영향 데이터/API:** `plugins.definition`, `package`, `schema`, `activation`; plugin package API.
- **범위/제외:** digest uniqueness, compatibility, project allowlist 포함; public marketplace와 untrusted plugin 제외.
- **선행 작업:** T-02, T-04, T-10.
- **완료 조건:** 동일 ID/version의 다른 digest가 거부되고 schema/capability 누락 package가 활성화되지 않는다.
- **테스트:** 단위—manifest/schema/version range; 통합—package register/activate/audit; 회귀—digest substitution, revoked package, cross-project activation.
- **담당:** Software 주 담당; Plugin Maintainer/Domain이 capability와 scientific evidence 승인.

#### T-18. Isolated runner, Python SDK, compatibility test kit — `P0`

- **목적:** core DB 접근 없이 Job Spec/Result Manifest로 plugin을 안전하고 재현 가능하게 실행한다.
- **입력과 출력:** 입력은 approved plugin package와 Job Spec; 출력은 validated Result Manifest/artifacts/diagnostics.
- **영향 데이터/API:** runner capability/attempt; internal runner protocol, SDK package, TCK.
- **범위/제외:** subprocess developer runner와 OCI-ready production adapter 포함; Kubernetes-specific operator 제외.
- **선행 작업:** T-15, T-17, T-10.
- **완료 조건:** synthetic 7종 extension이 TCK를 통과하고 core code가 implementation package를 import하지 않는다.
- **테스트:** 단위—SDK validation/cancel/RNG; 통합—sandbox artifact I/O/timeout; 회귀—network attempt, path traversal, oversized output, corrupt manifest.
- **담당:** Software 주 담당; 각 Domain Expert가 reference plugin expected result 승인.

## E-07. Selection, processing, QC, 산포

### S-07.1. 계산 입력과 전처리를 불변으로 고정한다

#### T-19. Selection Revision과 Processing Recipe/Run — `P0`

- **2026-07-15 reference subset:** 하나의 normalized reference tensile Dataset revision을
  pin하는 typed Selection, one-step inclusive engineering-strain crop Recipe, committed Run,
  typed processed Artifact와 별도 Dataset identity/revision 1, provenance/audit/RLS/API/웹
  흐름을 구현했다. source raw/normalized revision은 수정하지 않으며 preview output,
  interpolation, generic JSON/EAV를 사용하지 않는다. 여러 member/filter, resample/true
	  transform, durable reconciliation worker 및 production curve method는 여전히 후속 범위다.

- **ADR-0019 P0-2 next subset:** 복수 Test Run의 concrete Dataset revisions를 보존하는
  multi-member Selection, explicit alignment/resampling Recipe revision, 별도 processed Dataset
  revision과 반복 curve UI를 다음 구현 단위로 한다. grid/method/domain/extrapolation policy가
  없으면 계산을 거부하며 source Dataset revision은 수정하지 않는다.

- **목적:** specimen/dataset membership과 ordered processing step을 재현 가능한 input으로 고정한다.
- **입력과 출력:** 입력은 dataset revisions/member filters/step configs; 출력은 Selection Revision, Recipe Revision, processed Dataset Revision.
- **영향 데이터/API:** `datasets.selection*`, `processing.recipe*`, `processing_run`; selection/recipe/run API.
- **범위/제외:** crop/identity/resample synthetic steps, preview/commit 구분 포함; production curve method는 domain plugin 작업.
- **선행 작업:** T-12, T-13, T-18.
- **완료 조건:** membership/recipe 변경이 새 revision을 만들고 preview artifact가 release input이 되지 않는다.
- **테스트:** 단위—selection hash/step composition; 통합—multi-input processing/provenance; 회귀—latest-head drift, hidden interpolation, manual edit without operation.
- **담당:** Software framework; Domain이 processing steps/parameters 승인.

### S-07.2. 반복시험 QC와 통계를 산출한다

#### T-20. QC rule, scalar feature, Statistical Plan/Run — `P0`

- **2026-07-16 reference subset:** existing one-member normalized Dataset Selections remain intact;
  a typed Statistical Plan pins exactly two distinct Selection revisions from distinct Test Runs.
  A committed Run records typed QC and produces a separate immutable Result revision plus Parquet
  curve artifact only when the two observed engineering-strain grids are exactly equal. Scalar
  statistics use peak stress per Test Run (`n=2`) and report mean/sample SD/median/MAD/IQR/range/CV;
  curve output carries mean/sample SD/median/min/max. No hidden alignment, resampling,
  interpolation, extrapolation, or two-sample CI is performed (`not_provided_reference_pair`).
  PostgreSQL typed tables/RLS/constraints, provenance/audit, API, and Material State workbench are
  implemented. Multi-member grouping, approved alignment processing, larger-n uncertainty, and
	  domain-approved statistical method/tolerance profiles remain separate work.
- **ADR-0019 P0-2 next subset:** multi-member specimen-level `n`, pointwise band와 valid-domain
  metadata를 추가하되, 승인되지 않은 CI/threshold를 production policy로 표시하지 않는다.
- **목적:** specimen-level QC와 scalar/curve statistics를 grouping/assumption과 함께 계산한다.
- **입력과 출력:** 입력은 Selection Revision, aligned dataset, Statistical Plan; 출력은 features, QC observations, scalar/curve result artifacts.
- **영향 데이터/API:** `statistics.plan*`, `run`, `feature`, `qc_observation`, `result`; statistical API.
- **범위/제외:** 기본 descriptive/robust statistics와 pointwise band 포함; mixed effects/functional ANOVA 제외.
- **선행 작업:** T-19, T-18.
- **완료 조건:** replicate n이 specimen 기준이고 n/method/group/assumption이 모든 결과에 포함된다.
- **테스트:** 단위—known mean/SD/MAD/IQR/CI edge cases; 통합—curve alignment→statistics; 회귀—point pseudo-replication, masked-domain/extrapolation, unit-equivalent result.
- **담당:** Software/Scientific Computing 구현; Statistics/Materials Domain이 method/fixture/tolerance 승인.

#### T-21. Outlier candidate·판정·scope 비교 — `P0`

- **2026-07-17 reference subset:** completed for the existing two-selection reference tensile
  Statistics Result only. A typed immutable Detection Plan pins the exact Result revision and a
  declared relative peak-difference threshold; its committed run emits zero candidates below the
  threshold or both pair members as review_required at/above it. Separate immutable Assessment
  identities record retained or excluded_from_reference_analysis against the exact Statistical Plan
  revision. The typed comparison projection, PostgreSQL constraints/RLS, provenance/audit, API,
  contracts, and workbench preserve all source evidence and create neither automatic deletion nor a
	  derived Selection. Multi-member methods and calibration-specific scope remain outside this subset.
- **ADR-0019 P0-2 next subset:** 여러 member에 대한 candidate evidence와 사람 assessment를
  calibration-specific Selection/exclusion scope로 투영한다. 원본/normalized/processed curve는
  삭제하거나 덮어쓰지 않는다.

- **목적:** 이상치 후보 탐지와 사람 판정을 분리하고 특정 analysis/calibration exclusion만 표현한다.
- **입력과 출력:** 입력은 QC/statistics evidence와 detector plan; 출력은 candidate, append-only assessment, derived Selection Revision/comparison.
- **영향 데이터/API:** `statistics.outlier_candidate`, `outlier_assessment`; assessment API와 comparison query.
- **범위/제외:** robust/rule-based synthetic detector와 workflow 포함; automatic deletion/black-box anomaly model 제외.
- **선행 작업:** T-20, T-05 audit.
- **완료 조건:** 판정 전후 raw/dataset digest가 같고 scope가 다른 calibration에 누출되지 않는다.
- **테스트:** 단위—decision transition/scope; 통합—candidate→assessment→selection; 회귀—input mutation, bulk decision audit loss, stale evidence assessment.
- **담당:** Software workflow; Domain Expert가 detector와 판정 reason/profile 승인.

## E-08. Material Model, calibration, IR

### S-08.1. Model family를 core 밖에서 정의한다

#### T-22. Material Model IR envelope와 model schema registry — `P0`

- **2026-07-14 reference subset:** `urn:cmp:reference:isotropic-linear-elasticity:1.0.0`의
  stable identity/immutable revision, concrete Catalog revision lineage, typed SI elasticity
  columns, semantic/unit validation, protected create/read/history API, provenance/audit/RLS를
  구현했다. 이는 production schema registry 또는 calibration IR 전체 완료를 뜻하지 않는다.

- **목적:** 공통 semantics/units/applicability/evidence와 plugin-owned constitutive payload를 검증한다.
- **입력과 출력:** 입력은 model schema/plugin와 IR candidate; 출력은 IR Revision, L0~L4 validation report.
- **영향 데이터/API:** `modeling.model_family`, `model_schema`, `material_model*`; IR create/validate API.
- **범위/제외:** synthetic analytic model schema 포함; production model family는 `TBD` 후 별도 plugin task.
- **선행 작업:** T-17, T-18, T-13.
- **완료 조건:** 새 model schema가 core migration 없이 등록되고 unit/convention/payload mismatch가 거부된다.
- **테스트:** 단위—envelope/schema/quantity/table constraints; 통합—plugin physical checks/provenance; 회귀—arbitrary code, missing validity, schema digest substitution.
- **담당:** Software framework; Constitutive Domain Expert가 production schema/semantics 승인.

### S-08.2. Calibration을 재현하고 candidate를 비교한다

#### T-23. Calibration Plan/Run/Attempt orchestration — `P0`

**Reference subset status (2026-07-19): implemented.** The bounded slice pins one normalized or
processed tensile Selection revision and one reference linear-elastic Material Model IR revision,
then preserves explicit Plan/Run/Attempt/Candidate records and typed diagnostics Artifacts. It is
non-production only; the separate human Candidate Selection and append-only IR promotion are now
implemented by T-24.

**ADR-0019 P1 next subset:** add a bounded non-production reference Voce evaluator and SciPy
`least_squares` adapter for multi-curve monotonic tensile selections. Keep the test-mode, evaluator,
objective, and optimizer interfaces separate; persist explicit bounds/scaling/seed/multistart,
objective terms, convergence and failure evidence. This does not approve a production equation,
optimizer, parameter range, weighting, or acceptance threshold.

- **목적:** immutable inputs, model/calibrator, objective/bounds/seed를 고정하고 isolated runner에서 보정한다.
- **입력과 출력:** 입력은 Selection/processed dataset revisions, model schema, calibrator, plan; 출력은 attempts/candidates, parameters, residual/convergence artifacts.
- **영향 데이터/API:** `modeling.calibration_plan*`, `calibration_run`, `calibration_attempt`; calibration API.
- **범위/제외:** synthetic model/calibrator와 multistart framework 포함; production equation/optimizer choice 제외.
- **선행 작업:** T-19, T-22, T-15, T-18.
- **완료 조건:** 동일 seed/environment 재실행이 declared tolerance를 만족하고 failed/nonconverged run을 보존한다.
- **테스트:** 단위—objective aggregation/bounds/state; 통합—model+calibrator co-location/multistart; 회귀—curve point weighting bias, seed loss, retry/multistart 혼동.
- **담당:** Software/Scientific Computing 구현; Constitutive Domain이 objective/bounds/acceptance 승인.

#### T-24. Candidate diagnostics, selection, IR 승격 — `P0`

**Reference subset status (2026-07-20): implemented.** A stable Candidate Selection identity is
fixed to one succeeded Calibration Run and records append-only human decision revisions. Only an
exact converged Candidate may be selected, each decision requires a reason, and promotion only
works from the current Selection revision while the exact evaluated Material Model IR revision is
still current. Promotion appends a new non-production reference IR revision with typed
Selection/Candidate/Run/diagnostics evidence; it does not overwrite any source or published
revision. PostgreSQL tables, constraints, indexes, RLS, triggers, API contracts, unit/API/browser
regressions, and the Material State workbench are present. General candidate comparison, formal
	  approval/release, uncertainty, and solver validation remain outside this bounded subset.

**ADR-0019 P1 next subset:** compare nonlinear Candidates across the pinned curves, retain
prediction/residual and explicit identifiability/uncertainty status, then append a calibrated IR and
an explicitly derived tabulated-plasticity IR suitable for the existing two exporters. No Candidate,
source IR, Dataset, or already published card may be rewritten.

- **목적:** 여러 calibration candidate의 parameter/objective/residual/identifiability를 비교하고 선택 이유와 함께 IR revision을 만든다.
- **입력과 출력:** 입력은 terminal calibration candidates; 출력은 selection decision, chosen parameter set, IR Revision/evidence.
- **영향 데이터/API:** calibration candidate/selection records, material-model revision; compare/promote API.
- **범위/제외:** 비교 read model과 evidence requirement 포함; 자동 best-objective production 승인 제외.
- **선행 작업:** T-23, T-22, T-05.
- **완료 조건:** converged status와 domain acceptance가 분리되고 selection reason 없이는 promotion이 실패한다.
- **테스트:** 단위—eligibility/evidence rule; 통합—candidate→IR provenance; 회귀—failed candidate promotion, input/validation overlap 미표시, stale candidate.
- **담당:** Software UI/API; Material Modeler/Reviewer가 candidate 선택 승인.

## E-09. Solver export와 virtual specimen

### S-09.1. Target mapping을 명시하고 card를 생성한다

#### T-25. Solver Exporter capability/preflight/export framework — `P0`

- **2026-07-14 reference subset:** generic exporter/run framework 대신 ADR-006의 OpenRadioss
  2025 `/MAT/ELAST`, `kg_m_s`, reference linear-elastic IR 한 target tuple을 explicit typed
  tables/API/UI로 구현했다. mapping report acknowledgement, immutable card preview/download,
  provenance/audit/RLS를 포함한다. production exporter, arbitrary options, plugin-owned target
  payload, release approval은 이 subset에 포함되지 않는다.

- **목적:** IR→target mapping의 exact/transformed/approximated/unsupported 상태와 승인 조건을 강제한다.
- **입력과 출력:** 입력은 IR Revision, target solver/version/card/unit/options, exporter package; 출력은 Mapping Report, Solver Card Revision.
- **영향 데이터/API:** `exporting.target`, `export_run`, `mapping_report`, `solver_card*`; preflight/card API.
- **범위/제외:** synthetic text exporter 포함; production solver/card는 `TBD` 후 별도 plugin task.
- **선행 작업:** T-22, T-18, T-15.
- **완료 조건:** report digest와 export input이 일치하고 unsupported는 실패, approximation은 승인 없이 release 불가다.
- **테스트:** 단위—capability/mapping/unit transform; 통합—preflight approval→export; 회귀—silent default, target version drift, report replay.
- **담당:** Software framework; Solver Domain Expert가 production mapping/card 승인.

#### T-26. Solver-card golden/semantic comparison harness — `P0`

- **2026-07-14 reference subset:** reference IR fixture의 byte-exact `.rad` golden card,
  report acknowledgement mismatch, card-text tamper, unsupported target regression을 CI에
  추가했다. multiple target/version matrix, parser-based semantic diff, 그리고 domain-review
  golden-update workflow는 후속 범위다.

- **목적:** exporter 변경이 card text와 의미에 미치는 영향을 review 가능한 회귀 test로 고정한다.
- **입력과 출력:** 입력은 IR fixtures, target/version/options, approved golden; 출력은 byte/normalized semantic diff와 test result.
- **영향 데이터/API:** test fixtures/golden manifest; production API 없음, CI와 exporter TCK 영향.
- **범위/제외:** volatile field normalization policy와 negative fixture 포함; commercial solver 실행은 licensed nightly로 분리.
- **선행 작업:** T-25, T-18.
- **완료 조건:** intentional golden update는 exporter+domain reviewer 승인을 요구하고 unreviewed diff가 CI를 실패시킨다.
- **테스트:** 단위—normalizer/parser; 통합—exporter fixture matrix; 회귀—unit/sign/precision/keyword ordering/solver-version cases.
- **담당:** Software harness; Solver Domain Expert가 golden과 semantic diff 승인.

### S-09.2. Card를 solver에서 검증한다

#### T-27. Validation Template와 Solver/HPC Runner Adapter — `P0`

- **상태 (2026-07-21):** reference subset 구현. `validation_template`/`validation_plan` stable
  identity와 immutable revision, exact IR/Card/Selection pinning, `validation_run`, typed Result
  Manifest, deck/stdout/stderr/native Artifact 증거, PostgreSQL RLS/trigger/provenance/audit,
  protected API와 Material State workbench를 제공한다. `reference_inline_mock` 및 bounded manual
	  attach만 포함하며, 실제 solver/HPC adapter와 verdict는 구현하지 않는다(ADR-0013, T-28).

- **Current sequencing (ADR-0019):** 실제 OpenRadioss/Abaqus 실행, dry-run/data-check, HPC adapter와
  solver qualification은 P2로 보류한다. 기존 reference evidence/run boundary는 유지하며 삭제하거나
  production pass로 재해석하지 않는다.

- **목적:** geometry/mesh/BC/output template과 managed/manual solver 실행을 versioned plan으로 관리한다.
- **입력과 출력:** 입력은 card/IR, template revision, solver target, runner; 출력은 deck, external job ref, logs, native result manifest.
- **영향 데이터/API:** `validation.template*`, `plan*`, `run`, runner capability; validation submit/poll/cancel/attach API.
- **범위/제외:** mock runner와 generic scheduler contract 포함; 실제 HPC/solver adapter는 target 결정 후 구현.
- **선행 작업:** T-25, T-15, T-18, T-10.
- **완료 조건:** mock managed run과 manual attach가 동일 Result Manifest/provenance 요구를 충족한다.
- **테스트:** 단위—template/command allowlist/status mapping; 통합—submit/poll/cancel/collect; 회귀—shell injection, wrong solver version, license/queue timeout, callback replay.
- **담당:** Software runner; CAE Domain Expert가 template/solver settings 승인.

#### T-28. Result extraction, numerical health, experimental validation — `P0`

- **상태 (2026-07-22):** reference subset 구현. terminal Result Manifest에서 별도 immutable
  normalized-response Artifact, numerical-health report Artifact, comparison-result Artifact와
  explicit `validation_response_extraction`/`validation_numerical_health_report`/
  `validation_result`/comparison-point rows를 append한다. native SI unit/target/curve integrity,
  termination, health, observed-grid linear interpolation/no extrapolation, fixed relative-RMSE
  `0.05`, calibration Selection overlap을 명시적으로 판정한다. abnormal/unhealthy/no-output/
  unit-or-alignment-invalid/overlap 결과는 `not_evaluated`이고 pass가 될 수 없다. protected
  evaluate/read/curve API와 Material State workbench가 이를 표시한다. 이는 non-production
  reference evidence이며 real solver/HPC qualification, production threshold, approval/release는
	  포함하지 않는다(ADR-0014).

- **Current sequencing (ADR-0019):** P1은 solver-independent material-model response check와
  calibration input과 겹치지 않는 holdout Selection 비교만 확장한다. 실제 solver 결과 해석과
  production threshold 승인은 P2다.

- **목적:** native result를 normalized response로 추출하고 solver health와 실험 비교 verdict를 분리한다.
- **입력과 출력:** 입력은 native result/log, experimental Selection, extraction/metric profiles; 출력은 response artifact, health report, metrics, Validation Result.
- **영향 데이터/API:** `validation.result`, metric/threshold profile; validation result API.
- **범위/제외:** synthetic/mock result extractor와 metric 포함; production threshold는 `TBD`.
- **선행 작업:** T-27, T-20, T-18.
- **완료 조건:** abnormal solver termination은 metric이 좋아도 pass가 아니고 `not_evaluated`가 명시된다.
- **테스트:** 단위—metric/alignment/threshold/health; 통합—result→extract→compare; 회귀—missing output, truncated curve, unit mismatch, fit/holdout overlap.
- **담당:** Software/Scientific Computing 구현; CAE/Test Domain이 observable/metric/threshold 승인.

## E-10. 검토, 승인, 발행

### S-10.1. 기술 검토와 역할 분리를 강제한다

#### T-29. Lifecycle state machine와 Review Request/Decision — `P0`

- **목적:** draft→review→approved 상태, changes requested, append-only decision, separation of duties를 구현한다.
- **입력과 출력:** 입력은 candidate manifest, reviewer/approver decision; 출력은 lifecycle events/current projection/decision records.
- **영향 데이터/API:** `governance.lifecycle_event`, `review_request`, `review_decision`; review APIs.
- **범위/제외:** configurable required roles와 comment/evidence 포함; 법적 전자서명 인증 제외.
- **선행 작업:** T-04, T-05, T-14, T-24, T-28.
- **완료 조건:** author-only final approval과 stale candidate approval이 차단되고 변경 요청이 새 revision을 요구한다.
- **테스트:** 단위—transition/SoD; 통합—submit/review/change/approve; 회귀—decision mutation, manifest digest mismatch, privilege escalation.
- **담당:** Software workflow; Product/Domain/Quality가 approval matrix 승인.

### S-10.2. Immutable release를 공급한다

#### T-30. Release completeness gate와 immutable package/channel — `P0`

- **목적:** 승인된 IR/card/validation/review/provenance만 하나의 digest-fixed release로 발행한다.
- **입력과 출력:** 입력은 approved candidate manifest; 출력은 Release Manifest/package, released search/download channel.
- **영향 데이터/API:** `governance.release`, `release_manifest`, release artifact; create/search/download API.
- **범위/제외:** completeness/integrity/mapping policy와 production channel 포함; PLM/CAE connector 제외.
- **선행 작업:** T-29, T-14, T-10, T-26.
- **완료 조건:** package 구성요소가 고정되고 draft/unsupported/incomplete artifact가 channel에 노출되지 않는다.
- **테스트:** 단위—gate policy/manifest hash; 통합—publish/download/verify; 회귀—component substitution, unauthorized draft download, partial package.
- **담당:** Software 구현; Release Approver/Domain이 evidence profile 승인.

#### T-31. Supersede/withdraw와 downstream impact analysis — `P1`

- **목적:** 과거 release를 삭제하지 않고 교체·사용 중지하며 영향을 받는 card/validation/consumer를 찾는다.
- **입력과 출력:** 입력은 current/new release와 reason; 출력은 lifecycle event, predecessor/successor relation, impact report/warning.
- **영향 데이터/API:** release relation/lifecycle, usage record; supersede/withdraw/impact APIs.
- **범위/제외:** platform 내 download/use record와 warning 포함; 외부 PLM 자동 교체 제외.
- **선행 작업:** T-30, T-14.
- **완료 조건:** 이전 package가 조회 가능하고 production search는 current policy를 따르며 pinned old use에는 경고가 표시된다.
- **테스트:** 단위—transition/current selection; 통합—release chain/impact query; 회귀—history deletion, supersede cycle, withdrawn artifact silent use.
- **담당:** Software 주 담당; Release Governance가 policy 승인.

## E-11. Engineering Web Workbench

### S-11.1. Data와 provenance를 조작·검토한다

#### T-32. Catalog/Test/Upload/Mapping UI — `P0`

- **Runnable demo extension (2026-07-14):** `deploy/compose/docker-compose.demo.yml` now composes
  PostgreSQL, owner migration/bootstrap, non-owner API, worker, workbench, object storage, checked
  reference-plugin asset, and API-driven synthetic demo data. The browser may request a local token
  only when the API is explicitly in `demo` mode; all Material/Test/Dataset/IR/Card requests still
  use the normal JWT, authorization, and RLS boundaries. This is a development demonstration, not
  a production deployment or a generic plugin workflow.

- **Extension (2026-07-14):** The Material State screen now calls protected Testing, Upload, and
  Dataset APIs for the reference tensile path: Specimen/Test Run creation, multipart CSV upload,
  explicit column/unit confirmation, raw/normalized Dataset revision selection, and bounded curve
  preview. Generic testing/importer UX, mapping review for arbitrary formats, and workflow approval
  remain pending.

- **MVP progress (2026-07-14):** The protected Material Catalog UI is implemented: dashboard,
  Material search/create/detail, Material State entry, typed basic Property Set create/revision,
  revision history/compare, and provenance summary. The narrow reference tensile upload/mapping
  surface is implemented as described above; generic test/importer UX remains pending, and this is
  not a claim that the full T-32 task is complete.

- **목적:** material-state-lot/batch-specimen-test 문맥과 upload/mapping confirmation을 오류 없이 입력한다.
- **입력과 출력:** 입력은 OpenAPI resources/schema; 출력은 typed forms, upload progress, mapping review, issue display.
- **영향 데이터/API:** T-07~T-12 APIs; client-side state만 별도.
- **범위/제외:** accessibility, unit/semantic preview, provenance links 포함; 시험기 desktop control 제외.
- **선행 작업:** T-02, T-07~T-12, T-04.
- **완료 조건:** 사용자가 ambiguous mapping을 확인하고 raw/normalized metadata를 나란히 볼 수 있다.
- **테스트:** 단위—form/schema/state; 통합—upload→mapping→dataset; 회귀—stale ETag, large upload, role/read-only, locale numeric.
- **담당:** Software/UX 주 담당; Test/Data Steward가 workflow usability 승인.

#### T-33. Curve/Statistics/Calibration/Validation Workbench — `P0`

- **목적:** 개별·processed·fitted·simulated curve, scatter, residual, candidate, validation을 동일 의미/단위로 비교한다.
- **입력과 출력:** 입력은 dataset/statistics/calibration/validation APIs와 display artifacts; 출력은 filters, plots, comparison/selection commands.
- **영향 데이터/API:** T-19~T-28 read/command APIs; display-view endpoint.
- **범위/제외:** large-data downsampling, n(x), outlier scope, warnings 포함; browser에서 fitting 계산 수행 제외.
- **선행 작업:** T-19~T-28, T-32 shell.
- **완료 조건:** raw/processed/fitted/simulated 상태와 units가 명시되고 display downsample이 계산 input과 구분된다.
- **테스트:** 단위—plot mapping/status/accessibility; 통합—candidate compare/promote/validate; 회귀—axis/unit mismatch, hidden excluded curve, truncated data, stale selection.
- **담당:** Software/UX 구현; Statistical/Material/CAE Domain이 plot와 decision flow 승인.

#### T-34. Review/Release/Lineage/Audit UI — `P1`

- **목적:** reviewer가 candidate evidence와 upstream lineage, mapping warning, audit를 한 화면 흐름에서 확인한다.
- **입력과 출력:** 입력은 review/release/lineage/audit API; 출력은 decision command, completeness report, package verification view.
- **영향 데이터/API:** T-14, T-29~T-31, T-05.
- **범위/제외:** role-specific view와 downloadable report 포함; 범용 graph visualization studio 제외.
- **선행 작업:** T-29~T-31, T-14.
- **완료 조건:** reviewer가 원본까지 evidence path를 열고 stale digest 없이 decision할 수 있다.
- **테스트:** 단위—state/permission; 통합—changes-requested→new revision→approve; 회귀—unauthorized audit, stale review, large lineage limit.
- **담당:** Software/UX 구현; Reviewer/Auditor가 acceptance 승인.

## E-12. 운영, 복구, 품질 gate

### S-12.1. 실행을 관측하고 복구한다

#### T-35. OpenTelemetry logs/metrics/traces와 운영 dashboard — `P1`

- **목적:** request→job→plugin→solver 전 구간을 trace ID로 연결하고 SLO/실패 원인을 관측한다.
- **입력과 출력:** 입력은 application/runner instrumentation; 출력은 traces, structured logs, metrics, alert/runbook links.
- **영향 데이터/API:** telemetry backend; domain DB에는 trace ID만 저장.
- **범위/제외:** redaction, job queue/lease/plugin/solver metrics 포함; 특정 commercial APM 종속 제외.
- **선행 작업:** T-03, T-15, T-18, T-27.
- **완료 조건:** end-to-end trace와 failure taxonomy dashboard가 있고 secret/raw data가 log에 없다.
- **테스트:** 단위—redaction/context propagation; 통합—API→worker→runner trace; 회귀—missing trace, high-cardinality labels, secret fixture.
- **담당:** Software/Platform 주 담당; Operations가 alerts/runbook 승인.
- **2026-07-16 구현 subset:** API/worker가 vendor-neutral OTLP/HTTP trace와 metric을 Collector로
  전송하고 Job에 저장된 W3C trace context를 worker consumer span으로 이어간다. 애플리케이션
  request log는 허용된 route template/method/status/latency만 JSON으로 출력하며 raw access log를
  끈다. `GET /api/v1/operations/observability`와 Governance panel은 `audit.read` 권한으로 bounded
  process snapshot을 표시한다. Production alert backend, multi-replica aggregation과 solver span은
  아직 남아 있다.

#### T-36. Backup/restore, object integrity, disaster-recovery drill — `P1`

- **목적:** metadata, raw, release, plugin artifact를 목표 RPO/RTO 안에서 복구하고 digest/lineage를 검증한다.
- **입력과 출력:** 입력은 backup policy/snapshots/object versions; 출력은 restored environment, integrity/completeness report.
- **영향 데이터/API:** backup config, integrity/reconciliation jobs; admin drill records.
- **범위/제외:** automated backup/restore verification 포함; multi-region active-active 제외.
- **선행 작업:** T-10, T-13, T-30, T-35.
- **완료 조건:** 격리 환경 restore 후 sample release/raw digest와 lineage가 일치하고 drill 시간이 기록된다.
- **테스트:** 단위—manifest verifier; 통합—DB+object restore; 회귀—missing object version, RLS backup omission, key access failure.
- **담당:** Platform/Software 주 담당; Security/Data Owner가 retention/restore acceptance 승인.
- **2026-07-16 구현 subset:** PostgreSQL 16 custom dump를 무작위 격리 DB에 복원하고 별도 object
  snapshot에서 raw/artifact SHA-256·크기, relation count와 provenance dangling edge를 검사하는
  `cmp-restore-drill`을 제공한다. 실제 demo drill은 32.018초, raw 18/18, 전체 object 표본
  100/100, dangling lineage 0으로 통과했다. Source에 Release가 없어 release sample은
  `not_present_in_source`로 명시됐다. Production scheduled backup, versioned object lock,
  KMS/retention 승인과 Release가 포함된 재드릴은 남아 있다.

### S-12.2. Scientific·security·performance regression을 release gate로 만든다

#### T-37. 통합 CI test matrix와 quality gate — `P0/P1`

- **목적:** unit, contract, integration, scientific reference, golden, security, migration, performance test를 release별로 실행한다.
- **입력과 출력:** 입력은 code/contracts/plugins/fixtures/goldens; 출력은 signed test report와 release gate result.
- **영향 데이터/API:** CI configuration/test artifacts; production domain model 없음.
- **범위/제외:** open-source CI에서 mock solver, licensed nightly runner 분리 포함; 모든 solver를 PR마다 실행 제외.
- **선행 작업:** 전 P0 task의 test suites; T-26.
- **완료 조건:** 요구사항/task ID 추적, flaky quarantine policy, domain golden approval workflow가 동작한다.
- **테스트:** 단위—test tooling 자체 smoke; 통합—ephemeral full stack vertical; 회귀—migration from prior version, RLS matrix, numeric/golden fixtures.
- **담당:** Software/QA 주 담당; 각 Domain Expert가 scientific/golden test 결과 승인.

#### T-38. Performance·capacity·security acceptance — `P1`

- **목적:** NFR SLO와 threat controls를 production 전 실제 규모 fixture에서 검증한다.
- **입력과 출력:** 입력은 representative file/curve/catalog/lineage/job load와 threat cases; 출력은 benchmark, bottleneck, remediation, security report.
- **영향 데이터/API:** index/config/quota 조정 가능; public contract 변경은 별도 ADR.
- **범위/제외:** upload, search, lineage, concurrent jobs, RLS, parser/plugin sandbox, penetration test 포함; 무제한 scale 보장 제외.
- **선행 작업:** T-04, T-09~T-16, T-18, T-33, T-35.
- **완료 조건:** agreed SLO를 충족하거나 승인된 exception/개선 backlog가 있고 critical security finding 0건이다.
- **테스트:** 단위—benchmark harness correctness; 통합—full-stack load/soak/fault injection; 회귀—baseline 대비 허용 threshold 초과 시 CI/nightly 실패.
- **담당:** Platform/Security/QA 주 담당; Product/Domain이 representative workload와 risk acceptance 승인.

## 2. Domain-specific 후속 Task template

첫 시험/model/solver가 결정되면 아래 세 Task를 구체화한다. 현재 이름은 placeholder이며 production 구현을 승인하지 않는다.

### T-D01. `[TBD]` 인장시험 Importer·Processor plugin

- **목적:** 선정 시험 표준·재료군의 raw file과 metadata를 canonical dataset으로 변환한다.
- **입력과 출력:** 승인 sample files/standard/mapping → normalized curves, features, QC evidence.
- **영향 데이터/API:** Test Method schema, Import Mapping, Dataset channels; core API 변경은 원칙적으로 없음.
- **범위/제외:** 선정 format/standard만 포함; 다른 시험기/표준 제외.
- **선행 작업:** Stage 0 결정, T-11, T-12, T-18, T-19.
- **완료 조건:** 모든 sample과 known edge case가 domain-approved expected result와 일치한다.
- **테스트:** 단위—parser/units/transforms; 통합—raw→dataset; 회귀—vendor format/golden curves.
- **담당:** Software 구현; Test Domain Expert 주 승인.

### T-D02. `[TBD]` Material Model·Calibrator plugin

- **Reference next subset (ADR-0019):** production 결정을 기다리는 동안 synthetic monotonic
  tensile fixtures만 사용하는 bounded Voce/SciPy reference adapter를 구현할 수 있다. formula,
  parameter semantics, bounds, objective, grid projection, package/library version 및 diagnostics를
  고정하고 `reference_only`로 표시한다. Domain-approved parameter ranges, reference curves,
  tolerances와 production plugin packaging은 여전히 미결정이며 T-D02를 완료로 만들지 않는다.

- **목적:** 선정 구성방정식과 calibration policy를 구현한다.
- **입력과 출력:** processed selection/plan → parameter candidates, diagnostics, IR payload.
- **영향 데이터/API:** model payload schema와 plugin manifest; core API 변경 없음이 목표.
- **범위/제외:** 선정 model/observable/domain만 포함; 다른 material family 제외.
- **선행 작업:** Stage 0 결정, T-22~T-24.
- **완료 조건:** analytic/literature/internal reference와 tolerance 일치, identifiability/invalid input evidence 승인.
- **테스트:** 단위—constitutive limits/Jacobian 또는 response; 통합—calibration; 회귀—reference parameter/curve/IR.
- **담당:** Scientific Software 구현; Constitutive Domain Expert 주 승인.

### T-D03. `[TBD]` Solver Exporter·Validation plugin

- **Reference progress (2026-07-26):** A bounded non-production vertical is implemented before a
  production plugin decision. One normalized/processed monotonic tensile Dataset revision and a
  typed Property Set revision produce an immutable isotropic tabulated-plasticity IR and Parquet
  hardening Artifact. The reduction records the engineering-to-true profile, source and excluded
  point counts, first maximum-stress index, Catalog yield anchor, and an explicitly acknowledged
  constant-stress extension. The same frozen IR maps to OpenRadioss 2025 `/MAT/LAW36` + `/FUNCT`
  and Abaqus 2025 `*DENSITY` + `*ELASTIC` + isotropic `*PLASTIC`. Preflight reports the extension
  as `approximated`; card creation pins the report digest. Protected API/UI preview/download,
  explicit PostgreSQL columns/FKs/checks/indexes/RLS, and `.rad`/`.inp` golden fixtures are present.
  Real solver execution, semantic parser/dry-run, rate/temperature dependence, damage/failure,
  inverse post-necking identification, domain approval, and production plugin packaging remain
	  incomplete and keep T-D03 open.

- **Current sequencing (ADR-0019):** calibrated IR에서 기존 두 reference card로 이어지는
  deterministic mapping은 P1에 포함하지만, 실제 solver 실행과 qualification은 P2로 보류한다.

- **목적:** 선정 solver/version/card로 IR을 mapping하고 virtual specimen에서 검증한다.
- **입력과 출력:** IR/template/reference → card, mapping report, solver result, metrics.
- **영향 데이터/API:** exporter capability, validation template/profile; core API 변경 없음이 목표.
- **범위/제외:** 선정 solver/version/card/template만 포함; 다른 solver 제외.
- **선행 작업:** Stage 0 결정, T-25~T-28.
- **완료 조건:** domain-approved golden card와 reference solver result 일치, unsupported/approximation policy 검증.
- **테스트:** 단위—mapping/parser/units; 통합—IR→solver→metrics; 회귀—golden card/licensed solver fixtures.
- **담당:** Software/CAE Automation 구현; Solver/CAE Domain Expert 주 승인.

### T-30 implementation note (2026-07-24)

The bounded reference Release slice is implemented: explicit PostgreSQL Release, Release Manifest,
and package Artifact rows; fail-closed candidate/review/validation/mapping checks; protected
create/list/read/download API; React Release workbench; and unit, integration, contract, and
migration regression coverage. The channel is intentionally `reference` only; supersede/withdraw
and production publication remain T-31+.

### T-31 implementation note (2026-07-25)

Implemented the bounded lifecycle/impact slice: explicit tenant-scoped lifecycle projection,
append-only supersede/withdraw events, typed download/consume usage facts, protected lifecycle and
impact APIs, and Release workbench controls. A supersede requires an explicit same-scope successor;
withdraw has no successor. The immutable Release, Manifest, package, and downstream revisions are
never updated or deleted. Terminal package download/consume is rejected and impact reports expose
links, transition history, usage, and warnings. Automatic PLM replacement and production
publication remain out of scope.

### T-33/T-34 implementation note (2026-07-25)

The reference web workbench now exposes the existing protected display-view APIs together: raw,
normalized, processed, statistical, fitted/residual, and validation curves retain explicit
representation/units, point counts, and deterministic preview-sampling status. Browser plotting is
display-only and never becomes a calculation input. The Dashboard governance area adds a bounded
Lineage and Audit Inspector next to the Review and Release workbenches. A reviewer can inspect an
immutable provenance Entity, upstream lineage or downstream impact, completeness state, recent
tenant/project audit events, and audit-chain integrity. Graph truncation and invalid integrity are
visible warnings; client-side graph reconstruction, hidden payloads, and cross-organization/project
reads are not allowed. The inspector resolves a typed immutable revision/artifact reference to the
opaque Entity UUID or accepts that UUID directly. Generic graph visualization and production audit
export remain outside this slice.

### P0-2 implementation note (2026-07-28)

P0-2 item 1 is implemented by migration `20260728_030_p02`, the replicate Selection API, the
connected Material State curve-overlay workbench, and three-run synthetic demo data. The Selection
pins 2..50 ordered concrete normalized/processed Dataset revisions from distinct Test Run
revisions. Membership uses explicit rows, foreign keys, uniqueness, forced RLS, immutable-row
guards, and a deferred exact-count check; it is not JSON or EAV.

P0-2 item 2 is implemented by migration `20260729_032_p02`. The typed
`reference_tensile_common_grid_linear` Recipe stores grid start/end/count, `intersection` domain,
`piecewise_linear` interpolation, and `reject` extrapolation in explicit columns and constraints.
One grouped request creates an ordered committed Run and separate processed Dataset revision for
every pinned member. The connected workbench shows the declared policy and the resulting overlay.
Source Dataset revisions remain immutable; hidden alignment remains forbidden.

Item 3 is implemented end to end. Specimen-level `n`, scalar/pointwise mean, sample SD, median,
MAD, IQR, min/max, coefficient of variation, two-sided 95% Student-t mean interval, exact
processed-grid QC, and a typed Parquet result schema are persisted by migration
`20260730_033_p02`. Explicit Plan/Plan Revision, Run/ordered Member, Result/Result Revision, and QC
Observation tables enforce concrete revision pins, tenant/classification scope, terminal-state
rules, forced RLS, and immutability without JSON/EAV. Protected create/list/read/execute/result/
curve APIs and provenance hooks are connected to the Material State workbench. The browser requires
an explicit immutable Selection of aligned outputs, then displays QC, scalar statistics, observed
range, mean, and Student-t 95% CI band. Statistics performs no alignment or interpolation.

P0-2 item 4 is implemented by migration `20260731_034_p02`. A typed non-production modified-z
Plan pins one exact multi-replicate Statistical Result revision; its immutable Run evaluates every
preserved processed Dataset member and stores review evidence only. MAD-zero/nonmedian evidence is
explicit and no infinite score or automatic exclusion is produced. Separate append-only human
Assessment revisions drive an immutable calibration input Scope with exact Dataset/Test Run/
Candidate/Assessment pins and at least two retained members. Protected APIs, JSON Schema/OpenAPI,
the connected workbench, unit/API/web tests, migration downgrade/re-upgrade, and live PostgreSQL
include/exclude flows are present. No source Dataset/Selection/Result revision is changed.

### P1 implementation note (2026-08-03)

P1 is implemented for the bounded non-production reference scope. Migration `20260801_035_p1`
adds explicit Voce Plan/Run/Attempt/Candidate tables and deterministic SciPy `least_squares`
execution over an immutable calibration input Scope. Migration `20260802_036_p1` adds append-only
human Candidate selection and the calibrated `1.1` IR projection. The projection freezes a declared
51-point true-plastic-strain grid and explicit constant extension; the existing OpenRadioss LAW36
and Abaqus `*ELASTIC`/`*PLASTIC` exporters then provide preflight, preview, and download without
placing solver keywords in the IR.

Migration `20260803_037_p1` completes solver-independent holdout validation with typed Plan,
Plan Revision, Run, Result, and comparison-point tables. A holdout Dataset and Test Run must be
disjoint from every calibration Scope member, including excluded members. Evaluation calls the
same public Voce material-model evaluator at the observed holdout points, performs no refit and no
solver/card execution, and stores a comparison Artifact, RMSE, relative RMSE, and the explicit
non-production `0.05` reference verdict with audit/provenance lineage. The connected workbench
shows observed/predicted curves and the `solver_execution=not_used` boundary.

The next execution wave is P2. Ordered priorities are: (1) approved production domain decisions and
Catalog/Test genealogy expansion, (2) real solver data-check/execution/HPC adapters and immutable
result evidence when the product owner re-enables that scope, (3) approved solver-result parsers,
scientific fixtures, thresholds, and qualification, and (4) observability, backup/restore,
performance/security, and external release hardening. No P2 item is silently treated as complete.

### P2 product-vertical amendment (ADR-0020)

Before broader operational foundation work, P2 proceeds through user-visible verticals:

1. Governed Material class revisions and workflow compatibility guidance, preserving legacy
   revisions as `unclassified`.
2. Steel elastoplastic regression protection using the existing tabulated/Voce IR and
   OpenRadioss LAW36/Abaqus exporters.
3. Linear generalized-Maxwell/Prony IR, shear-relaxation data processing and Abaqus time-domain
   viscoelastic card preview/download.
4. Ogden-Prony hyper-viscoelastic IR with explicit Abaqus and OpenRadioss LAW62 mappings.
5. Explicit Process Definition/Run, Material Lot/Batch, Batch Input and Process Output genealogy.

Every increment includes typed PostgreSQL persistence, protected API, connected frontend, and
unit/integration/regression tests. Solver execution qualification remains excluded until explicitly
re-enabled. Reference outputs do not close the production T-D02/T-D03 approval tasks.

P2 item 2 is complete for the bounded reference routing scope. Migration 039 and the Modeling
application require tabulated/Voce plasticity IRs to pin an exact `metal` Material revision. The UI
does not expose the Steel workbench for polymer, elastomer or unclassified State revisions, and
legacy States can explicitly append a revision that adopts the current classified Material. This
does not add a production constitutive model or solver qualification.

P2 item 3 is complete through the following ordered vertical increments. Migration 040 and the typed Modeling
application/API/UI implement the manual linear Prony IR. Migration 041 and the Exporting
application/API/UI now add the Abaqus 2025 `*DENSITY`, instantaneous `*ELASTIC`, and
`*VISCOELASTIC, TIME=PRONY, TYPE=ISOTROPIC` vertical: exact source revision pinning, explicit mapping
preflight, immutable typed Prony card rows, byte-digest golden output, preview, and `.inp` download.
Bulk relaxation remains evidence-bearing (`characterized` or `not_characterized`) and is never a
silent default. Migration 042 completes the shear-relaxation ingress increment with an explicit
Test Method/Run, immutable raw CSV, typed raw/normalized Dataset revisions, SI Parquet Artifact,
tenant/source FKs, RLS, Provenance usage and a connected browser curve preview. Processing and
bounded Prony calibration remain the next P2 item 3 increment; they must create revisioned
activities/candidates and may not overwrite the raw or normalized curve. Migration 043 completes
the Processing portion with a typed observed-point time-crop Recipe revision, exact-input Run,
derived Artifact, separate processed Dataset identity, provenance, forced RLS and connected UI.
Migration 044 completes bounded two-term generalized-Maxwell fitting: exact processed Dataset and
baseline IR pins, bounded/log-transformed parameters, deterministic PCG64 multistart, typed
Plan/Run/Attempt/Candidate rows, immutable residual diagnostics Artifacts, API and connected UI.
Migration 045 completes human selection and promotion. A reviewed Candidate and reason become an
immutable typed Selection revision; an exact-baseline compare-and-swap then appends schema 1.1 to
the same Material Model identity. The promoted IR pins Selection, Run, Candidate and diagnostics
digests, and the existing Abaqus exporter pins that promoted revision through preflight, preview
and download. The lowest displayed objective remains only a sorting aid, never an automatic
engineering decision.
OpenRadioss LAW62 remains
explicitly outside this linear family and belongs to P2 item 4.

### P2 item 4 implementation note (2026-08-13)

The bounded reference Ogden–Prony vertical is implemented by ADR-0023 and migrations 046/047.
It stores one Ogden μ/α pair and one-to-five normalized shear-Prony terms in explicit immutable
tables for elastomer Material revisions only. The protected API and Material State UI now execute
Material/State/Property Set → Ogden–Prony IR → mapping preflight → immutable card → preview/download.
Abaqus 2025 `*HYPERELASTIC` + `*VISCOELASTIC` and OpenRadioss 2025 `/MAT/LAW62` are the only
declared targets. LAW62 ν=0.495 remains visibly `approximated`; linear-Prony is never silently
routed to LAW62. Golden byte fixtures and live PostgreSQL/API/UI checks cover both targets.

This completes only the ADR-0023 reference slice. Production hyperelastic calibration, additional
Ogden terms, compressible/temperature-dependent response, external solver execution, and solver
qualification remain P2 work. The next product priority was the bounded T-07 Process/Lot/Batch
genealogy slice described below.

### P2 item 5 implementation note (2026-08-14)

ADR-0024 and migration 048 implement the bounded exact-revision Catalog genealogy slice. Process
Definition and Material Lot/Batch are separate stable identities with immutable typed revisions.
One State Genealogy identity appends revisions that pin the exact Material State revision and
optional manufacturing Process, heat-treatment Process, and Lot/Batch revisions. Composite
organization/project/classification foreign keys, forced RLS, immutable-row triggers, deferred
role/material/scope guards, protected API commands, and the connected Material State UI prevent a
historical State from silently following a newer Process or Lot head. This is typed relational
persistence, not JSON/EAV.

The bounded ADR-0020 product-vertical sequence is therefore complete through items 1--5. This does
not complete the full T-07 task. The next recommended product depth is:

1. Process Run identities and immutable revisions with typed input Lot/Batch consumption and
   output Lot production;
2. split/merge quantities, multi-lot acceptance and Specimen source-lot links;
3. Test Campaign, Instrument/calibration and condition snapshots from T-08;
4. governed production property/curve schemas and selected laboratory importer packages;
5. an iterative-calibration promotion decision: either create a new Material Model identity for
   every accepted calibration or define a new IR revision schema that preserves an evidence chain
   across `r3+`; the current safe contract rejects replacing promotion evidence;
6. domain-approved scientific fixtures and exporter qualification. Actual solver execution stays
   excluded until the product owner explicitly restores that scope.

The live user E2E record at `docs/15-demo/user-e2e-evidence-2026-07-16.md` proves the connected
polymer path from test registration through normalized/processed data, bounded Prony fitting,
human Candidate selection, immutable IR promotion and Abaqus card download. It also records UI
evidence for item 4 LAW62 output and item 5 exact-revision genealogy.

## E-13. Production-pilot product completion

ADR-0025 replaces the open-ended P2 list with the following resumable sequence. These Tasks extend
the existing implementation; they do not reopen completed foundation or bounded reference work.
Each Task must deliver typed persistence, protected API, connected UI, tests and user-guide updates
in the same vertical increment. Actual solver execution remains excluded.

### S-13.1. Complete Catalog and Test context

#### T-39. Process Run input/output, split/merge and Specimen source genealogy — `P0`

- **목적:** actual Process execution을 Definition과 분리하고 consumed/produced Lot revision을
  재현 가능한 graph로 저장한다.
- **입력과 출력:** exact Process/Material State/Lot revisions, operator/time/equipment and typed
  quantities → immutable Process Run revision, ordered inputs/outputs, balance result and Specimen
  source links.
- **영향 데이터/API:** explicit Process Run identity/revision/input/output and Specimen-source
  tables; create/revise/list/read and genealogy queries.
- **정책:** quantity는 decimal + original UCUM + normalized SI다. balance basis는
  `mass|volume|count|not_assessed`; 미평가 사유가 필수다. multi-lot과 split/merge를 허용하고
  assessed basis의 dimension/tolerance mismatch는 거부한다.
- **완료 조건:** exact revision graph, tenant/classification FK, forced RLS, cycle rejection,
  immutable history와 connected genealogy UI가 동작한다.
- **테스트:** unit balance/split/merge; PostgreSQL deferred constraints/RLS; API/browser exact-pin;
  source revision mutation and cross-project regression.
- **구현 상태 (2026-07-16):** 완료. Migration 049의 explicit typed tables, immutable revisions,
  ordered Lot flows, deferred material/balance/cycle guards, forced RLS와 Specimen source exact-pin을
  protected API 및 Material State 화면에 연결했다. 지원 수량 단위는 현재 `kg|g|mg`,
  `m3|L|mL|cm3`, `1`로 제한하며 원본 단위와 normalized SI를 함께 보존한다.

#### T-40. Test Campaign, Instrument calibration and condition snapshots — `P0`

- **목적:** 시험 목적, 장비와 실행 시점의 표준·교정·환경 조건을 Test Run에 고정한다.
- **입력과 출력:** Campaign/Instrument/Calibration revisions, standard designation/edition/
  deviation, typed temperature/humidity/rate/orientation/medium → exact Test Run links.
- **영향 데이터/API:** Campaign, Instrument, Calibration Record, Condition Snapshot identities
  and revisions; Test Run linking commands and searches.
- **정책:** 공통 조건은 explicit columns다. method-specific extension만 schema ID/version/digest
  검증 JSON을 허용하며 generic EAV를 사용하지 않는다.
- **완료 조건:** 과거 Run이 최신 장비 교정이나 Method head를 따라가지 않고 UI에서 실행
  당시 snapshot을 확인할 수 있다.
- **테스트:** expiration/overlap/deviation rules, PostgreSQL exact FK/RLS, API/browser workflow,
  stale calibration and hidden-default regression.

- **구현 상태 (2026-07-16):** 완료. Migration 050은 Campaign, Instrument, Calibration,
  Condition Snapshot, Test Run Context를 각각 stable identity와 immutable revision으로
  분리한다. Test Run Context는 Campaign/Method/Condition/Instrument/Calibration의 exact
  revision을 고정하며 실행 시각을 벗어난 교정, usable 교정 기간 중복, Method 불일치,
  cross-scope 연결을 서비스와 PostgreSQL 제약에서 거부한다. 공통 조건은 온도·습도·속도·
  방향·매질의 명시적 typed column으로 저장하고 generic EAV/JSON payload를 사용하지 않는다.
  protected API와 Material State 화면은 유효 교정만 선택 가능하게 표시한다.

### S-13.2. Make test-data ingestion and processing usable

#### T-41. Governed CSV/TSV/XLSX importer and channel schemas — `P0`

- **목적:** 선정된 공개 tabular 형식으로 실제 시험 파일을 안전하게 등록하고 mapping을
  재사용한다.
- **입력과 출력:** immutable CSV/TSV/XLSX Raw Asset, explicit sheet/header/encoding/locale,
  column/unit/quantity mapping → approved Import Profile revision plus raw/normalized Dataset.
- **초기 schema:** monotonic tension/compression, planar/biaxial/simple shear and shear relaxation.
  force/displacement input requires pinned specimen geometry before stress/strain derivation.
- **정책:** detect/preview는 suggestion일 뿐이며 unresolved mapping은 `needs_input`이다. 원본
  bytes, original units, normalized SI, per-row errors and failed Import Run evidence를 보존한다.
- **범위 제외:** proprietary laboratory formats and arbitrary vendor reverse engineering.
- **테스트:** parser/locale/formula/decompression limits, unit/schema fixtures, PostgreSQL
  persistence/RLS, mapping approval UI and raw/normalized immutability regression.
- **구현 상태 (2026-07-16):** 완료. Migration 051은 Import Profile, Preview Report,
  terminal Import Run, raw/normalized governed Dataset과 channel을 명시적 typed table로
  저장하며 강제 RLS, exact composite FK, immutable revision/head guard를 적용한다. CSV/TSV는
  encoding/delimiter/decimal을, XLSX는 sheet를 명시하고 formula, macro, external link와
  decompression 한계를 검사한다. UI는 immutable upload → `needs_input` preview → 사람의
  reusable Profile 승인 → exact Run 실행 → 별도 raw/normalized SI Dataset을 연결한다.
  Force/displacement 변환은 monotonic tension/compression과 양수 geometry pin이 있을 때만
  허용된다. Proprietary vendor parser는 범위 밖이다.

#### T-42. Viscoelastic replicate statistics, temperature shift and master curve — `P0`

**구현 상태 (2026-07-16): complete, reference/non-production.** Migration 052와 protected API,
React workbench가 exact normalized Dataset/Test Run/temperature Selection, manual 또는 WLF Plan,
별도 aligned/statistics/master Dataset revision과 ordered shift evidence를 구현한다. 실제
PostgreSQL provenance/RLS와 browser curve가 검증 대상이며 source revision은 변경하지 않는다.

- **목적:** 여러 relaxation curve와 온도를 보존하면서 비교·정렬·통계·master curve를
  명시적 Processing으로 만든다.
- **입력과 출력:** exact replicate Selection and temperature conditions → aligned Dataset,
  scalar/pointwise statistics, shift-factor evidence and master-curve Dataset revisions.
- **정책:** log-time common intersection, piecewise-linear interpolation and no extrapolation are
  defaults. User shift factors are allowed; WLF fitting requires at least three temperatures and a
  selected reference temperature. Every shift/fit remains an ordered Recipe step.
- **완료 조건:** raw/normalized/aligned/statistical/master representations remain distinct and the
  browser shows individual curves, n, band, outlier status and shifted curves.
- **테스트:** hand fixtures, no-overlap/unequal-temperature/missing-condition cases, deterministic
  WLF recovery, PostgreSQL provenance and browser curve regression.

### S-13.3. Qualify and iterate neutral models

#### T-43. Scientific profiles, uncertainty and hyper-viscoelastic fitting — `P0/P1`

**구현 상태 (2026-07-16): complete for the bounded reference Ogden slice.** Migration 053은
Steel Voce, Polymer linear-Prony, Elastomer Ogden--Prony별 typed scientific profile identity와
immutable revision을 제공한다. Migration 054는 exact profile/Material State/baseline IR/governed
Dataset revisions를 pin하는 Plan, ordered calibration/holdout members, deterministic multistart
Run/Attempt/Candidate, per-mode objective, convergence, rank/covariance/95% CI 또는 명시적
`not_estimable` 상태, warning과 Parquet diagnostics Artifact를 저장한다. React workbench는
curve 역할·mode·weight, candidate 비교, fitted/residual plot을 실제 API와 DB에서 표시한다.
각 governed curve의 Test Run은 uniaxial, planar 또는 biaxial reference Test Method revision을
별도로 pin하므로 Dataset schema만 바꿔 loading mode를 가장하지 않는다.
현재 fitter는 normalized engineering-strain/nominal-stress와 one-term incompressible Ogden의
uniaxial/planar/equibiaxial public equations로 제한되며 `reference/unapproved`이고 solver를
실행하거나 Candidate를 자동 승인하지 않는다. 별도 human Selection과 Candidate promotion은
아래 T-44에서 구현되었다.

- **목적:** reference Steel Voce/tabulated, Polymer linear-Prony and Elastomer Ogden--Prony paths에
  versioned parameter/objective/diagnostic profiles를 제공한다.
- **입력과 출력:** multi-test processed Selections, initial/bounds/scaling/objective/weights →
  multistart Candidates, residual/prediction, holdout, uncertainty/identifiability status and IR.
- **정책:** Steel Voce/tabulated, one-to-ten-term Prony and one-term Ogden plus one-to-five Prony가
  초기 범위다. Elastomer는 multiple TestModeAdapter를 동시 사용하고 single-mode evidence에는
  insufficiency warning을 기록한다.
- **승인:** 공개 analytic/synthetic fixture는 구현 가능하지만 Domain sign-off 전 status는
  `reference/unapproved`다. 빈 uncertainty를 성공처럼 표시하지 않는다.
- **테스트:** analytic limits, bounded recovery, objective weighting, rank/covariance, holdout,
  deterministic artifact and UI candidate comparison.

#### T-44. Iterative Calibration and append-only promotion evidence — `P0` — implemented 2026-07-16

- **목적:** 같은 Material Model stable identity에서 이전 evidence를 잃지 않고 `r3+`를 만든다.
- **결정:** ADR-0026의 revision-owned evidence chain을 구현한다.
- **영향 데이터/API:** promotion evidence per IR revision, prior-revision comparison and promotion
  command with current ETag.
- **완료 조건:** new Selection/Candidate가 current head에 새 revision을 append하고 모든 prior
  IR/Card/Release가 byte/digest stable하다.
- **테스트:** repeated promotion, stale head, reused Candidate, cross-scope, prior-card stability
  and browser calibration-round comparison.
- **구현 결과:** migration 055가 typed Ogden Candidate Selection identity/revision과 각 promoted
  IR revision이 소유하는 `ogden_promotion_evidence`를 추가했다. Selection은 exact succeeded Run,
  converged Candidate, candidate/diagnostics digest와 baseline model revision을 pin한다. Promotion은
  strong current `If-Match`를 요구하고 같은 Material Model에 schema 1.1 revision을 append한다.
  Candidate/Selection 재사용, stale head, cross-scope/lineage 불일치는 API와 PostgreSQL 양쪽에서
  거부한다. 화면은 선택 사유, 승격 사유, current revision과 newest-first evidence history를 표시하며
  prior card payload/digest 안정성을 회귀 테스트한다. Solver 실행과 자동 Candidate 승격은 없다.

### S-13.4. Deliver data and keep the service operable

#### T-45. Immutable Bulk Export Bundle — `P0`

- **목적:** test data, neutral data, mapping evidence and cards를 한 번에 전달한다.
- **입력과 출력:** revisioned Export Selection → durable Job → immutable deterministic ZIP Bundle.
- **구성:** raw originals, Parquet, CSV, IR JSON/schema, mapping reports, native cards,
  `manifest.json`, `checksums.sha256`, README.
- **정책:** ADR-0027, one tenant/project, maximum classification propagation, no silent omission,
  1,000 components/5 GiB initial limit and existing short-lived Artifact download authorization.
- **테스트:** deterministic ZIP/digest, missing/unsupported preflight, RLS/classification, retry,
  large-job failure and browser Export Center download.
- **2026-07-16 reference subset:** migration 056, typed exact-revision Selection/member/omission,
  durable state-guarded Job, immutable deterministic ZIP Artifact, maximum classification/RLS,
  lifecycle/provenance/audit hooks, protected discovery/create/read/download APIs and connected
  `/exports` UI are complete. The Docker/PostgreSQL workflow downloaded a 22-component Bundle and
  verified manifest/checksum evidence. Up to 64 MiB is assembled inline by default; migration 057
  and the T-47 worker now queue larger estimates, assemble deterministic bytes on disk, stream the
  Artifact commit, expose immutable output evidence and reconcile a later Bundle-projection failure
  without reassembly. Migration 058 adds heartbeat/expiry, atomic expired-job reclamation,
  attempt increments and fencing-token checks for every external output/terminal transition. The
  1,000-component/5-GiB ceiling is a domain limit, not production-scale acceptance; the current
  external worker still caps each source component at 64 MiB.

#### T-46. User navigation, manuals and screenshot maintenance — `P0`

- **목적:** 신규 사용자가 개발 문서를 읽지 않고 Material→Test→Model→Card를 수행한다.
- **출력:** global Materials/Tests/Datasets/Models/Exports/Governance navigation, contextual Material
  tabs, Korean task-oriented guides, sample files, troubleshooting and deterministic screenshots.
- **정책:** user-visible workflow PR은 guide and screenshot manifest를 함께 갱신한다. Existing
  deep links remain compatible and screenshots contain no token/confidential/local personal data.
- **테스트:** route/deep-link/accessibility, deterministic demo seed browser E2E, referenced-image
  integrity and stale-guide PR gate.
- **2026-07-16 reference subset:** seven global module routes, Material Overview/Test data/Datasets
  & Processing/Models & Cards/Governance context routes, connected Material selection hubs, real
  Governance workbenches, Korean navigation/troubleshooting instructions and two current browser
  captures are complete. `cmp-check-user-guide`/`make docs-screenshots` now fail CI on navigation,
  link, manifest, image-size or declared-viewport drift.

#### T-47. Observability, restore, supply-chain, performance and connector hardening — `P1`

- **목적:** production-pilot의 failure/복구/배포/외부 전달 evidence를 완성한다.
- **범위:** T-35 OpenTelemetry and redaction dashboard, T-36 DB/object restore drill, T-37 full
  matrix, T-38 benchmark/security, object lock/KMS/retention adapters, SBOM/vulnerability/signature,
  signed manifest REST/webhook/object-storage connector, and reconciliation/visibility for an
  immutable derived output committed before a later multi-output Run step fails.
- **제외:** credential 없는 proprietary Teamcenter/PLM connector and licensed solver execution.
- **완료 조건:** RPO/RTO drill, bundle/release digest restore, critical security finding zero or
  explicit risk acceptance, benchmark report and traceable connector delivery.
- **테스트:** secret/log redaction, trace propagation, restore checksum/lineage, dependency/image
  scan, signature substitution, load/soak and connector retry/idempotency.
- **진행 상태 (2026-07-16):** T-35 redacted OpenTelemetry/API-worker propagation/dashboard, T-36
  격리 PostgreSQL/object restore subset, Python/Node/container CycloneDX SBOM, dependency/image
  vulnerability gate, canonical Ed25519 quality manifest와 signature/evidence/key substitution
  회귀, frontend workbench code splitting 및 hard bundle budget까지 구현·실데이터 검증 완료.
  local ephemeral key는 builder identity가 아니며 production KMS/keyless trust는 완료로 간주하지
  않는다. 실제 Catalog/API, 2 MiB/32-part upload, capability/auth/path threat, governed Bundle
  download와 64 MiB inline assembly의 bounded local benchmark/report gate를 완료했다. 이어서
  isolated PostgreSQL에 exact 10,000개 Material identity/revision을 append하고 API에서 RLS 범위의
  전체 cardinality와 제한된 page를 한 query로 반환하도록 했다. 실제 2 GiB deterministic source를
  32개 64 MiB part로 streaming해 digest/size와 192 MiB 이하 Python allocation을 확인했으며
  `--require-production-scale` report가 `production_scale_accepted=true`로 통과했다. migration
  057, streaming Artifact finalization, composed worker와 Export Center Job 목록으로 64 MiB 초과
  예상 작업의 외부 조립 및 failed-later-step output reconciliation visibility를 구현했고, 실제
  Docker/PostgreSQL 22-component Bundle의 저장/다운로드 digest를 검증했다. Migration 058의
  lease/heartbeat/fencing으로 만료 전 이중 claim 차단, hard-kill 뒤 attempt 2 회수와 stale
  worker finalization 거부를 PostgreSQL 및 실제 Compose worker에서 검증했다. 057 active Job은
  upgrade 시 expired bootstrap lease를 받아 고아가 되지 않으며 active downgrade는 차단된다.
  10,000-Material 구성에서 5분 mixed Catalog/Bundle/health soak와 PostgreSQL pause, API/worker/web
  stop/start를 실행했고 장애 밖 오류 0건, 모든 복구 60초 이내, Material cardinality와 Bundle digest
  불변, 서비스 memory growth gate를 통과했다. local volume composition은 독립 object-storage fault를
  대표하지 않는다. 남은 순서는 (1) object lock/KMS/retention 및 production signing adapter,
  (2) signed-manifest
  REST/webhook/object-storage connector와 운영 token rotation이다.

- **2026-07-17 governed storage subset:** production composition은 명시적인 S3-compatible
  adapter를 선택하고 bucket versioning, Object Lock, 정확한 SSE-KMS key가 아니면 fail closed
  한다. Staging은 암호화하되 정리 가능하고, final promotion은 조건부 write, checksum 검증과
  retention lock을 적용한다. Contract test는 완료했다. 실제 bucket/KMS/failover acceptance,
  production signing identity와 signed connector는 순서대로 남아 있다. 상세 계약은
  `docs/13-delivery/t47-governed-object-storage.md`에 기록한다.

- **2026-07-17 production signing subset:** canonical quality manifest는 production에서
  process-local private key를 거부하고, 별도 command adapter의 Ed25519 identity/signature를
  독립 trusted public key와 expected key ID로 검증한다. 실제 HSM/Vault/keyless signer 배포와
  key ceremony evidence는 남아 있다. 계약은 `docs/13-delivery/t47-production-signing.md`다.

- **2026-07-17 branch gate:** 실제 PostgreSQL 16을 포함한 Python 680개와 Vitest 41개가
  skip/failure 없이 통과했고 ruff, mypy 551 files, architecture/contracts/OpenAPI, user-guide,
  production web budget과 npm audit 0 vulnerabilities를 확인했다. 이 workstation에는 GNU Make와
  Git Bash가 없어 `make ci` wrapper 대신 `scripts/ci.sh`와 동일한 명령을 PowerShell에서 실행했다.

- **2026-07-17 signed connector/identity subset:** 기존 leased transactional outbox에 external
  Ed25519 signed REST/webhook/object-storage delivery를 연결했다. HTTP는 exact digest receipt와
  idempotency key를 요구하고 object storage는 immutable tenant/event/digest key를 사용한다.
  Worker와 HTTP bearer는 atomically replaced token file을 매 cycle/delivery마다 다시 읽으며
  production inline token은 거부한다. 실제 receiver/IdP rotation acceptance는 남아 있다.
  전체 gate는 PostgreSQL 포함 Python 690개, Vitest 41개, ruff/mypy 555 files, architecture,
  user-guide, production web budget과 npm audit 0 vulnerabilities를 통과했다.

## E-14. Configurable Material Information System and Modeling Workbench

ADR-0028~0030과 [제품 capability map](../00-research/product-capability-map.md)이 이 Epic의
단일 상태 기준이다. T-39~T-47에서 만든 foundation과 bounded reference vertical은 폐기하지
않고 compatibility projection 또는 method implementation으로 재사용한다. 각 Task는 DB/domain,
API/calculation, connected UI, automated test, guide/screenshot을 모두 갖춰야 완료된다.

### S-14.1. Correct the product baseline and make the catalog configurable

#### T-48. Product capability map and status correction — `P0`

- **범위:** 공식 공개 자료 기반 capability map, ADR-0028~0030, vision/requirements/domain/
  architecture/IR/fitting/backlog/README/status 정합화.
- **완료 조건:** 실제 증거 없는 capability는 `partial/missing/mischaracterized`로 표시하고
  T-49~T-60의 단일 의존 순서를 문서화한다.
- **테스트:** Markdown links/headings, requirement/Task reference와 user-guide manifest lint.

#### T-49. Configurable Table, Attribute, Layout and Subset — `P0`

- **범위:** stable Table/Attribute/Layout/Subset identities, immutable revisions, type-specific
  value storage(number/integer/text/boolean/date/discrete/file/curve/reference), unit semantics,
  validation, administrator API와 schema designer UI.
- **완료 조건:** migration 없이 Table/Attribute/Layout/Subset definition revision을 추가하고
  type/unit/reference validation을 PostgreSQL, API와 연결된 관리자 화면에서 확인한다. 실제
  record form/search의 definition 소비는 T-50 완료 조건이다.
- **테스트:** type/unit/validation negative, revision concurrency, tenant/classification FK/RLS,
  PostgreSQL round-trip, React administrator E2E.

#### T-50. Catalog Record, datasheet, search, facet and compare — `P0`

- **범위:** Folder/Record identities와 revisions, typed search indexes, Layout datasheet, saved
  Subset, text/facet/range query, record comparison과 current/exact deep links.
- **완료 조건:** 사용자가 tree 또는 search에서 record를 찾아 단위·출처·revision 차이를 비교한다.
- **테스트:** folder cycle, normalized range, authorized count/facet, saved-query compatibility,
  10,000-record bounded query와 Playwright browse/search/compare.
- **구현 증거 (2026-07-18):** migration 060, nine typed value relations를 소비하는 Folder/Record
  service와 protected API, Layout-driven datasheet, text/discrete/normalized-range 검색, facet,
  saved Subset, exact revision compare를 연결했다. fresh PostgreSQL non-bypass role, API/React 및
  migration 회귀를 통과했다. 전체 Catalog/Workflow tree와 arbitrary Link Type은 T-51이다.

#### T-51. Dual Explorer and typed revision-pinned record links — `P0`

- **범위:** Catalog Explorer, Material Workflow Explorer, Link Type, forward/reverse Record Link,
  breadcrumb/deep-link navigation. 기존 flat routes와 State genealogy를 유지한다.
- **완료 조건:** Material에서 Test/Dataset/Processing/IR/Card/Release까지 exact revision link로
  이동하고 관리자 정의 cardinality를 강제한다.
- **테스트:** endpoint/cardinality/cross-scope/latest negative, reverse query, lazy-tree UI E2E.
- **구현 증거 (2026-07-18):** migration 061의 명시적 Link Type/Record Link identity와 immutable
  revision, composite scope/exact-revision FK, RLS/immutability/cardinality/endpoint trigger를
  구현했다. protected API는 lazy Catalog children, Link Type, forward/reverse links와 bounded
  workflow graph를 제공한다. `/catalog/explorer`는 Table → Folder → Record 트리와 exact-revision
  deep link, Link Type/target 선택, append-only 비활성화를 실제 API에 연결한다. fresh PostgreSQL
  non-bypass role, migration/API/React 테스트와 Docker 브라우저에서 DP600 r2 ↔ tensile-test r1
  양방향 이동을 검증했다. 다음 product slice는 T-52 canonical Test JSON이다.

### S-14.2. Establish JSON exchange and reusable processing

#### T-52. Canonical Test JSON and deterministic JSON+ZIP — `P0`

- **범위:** `cmp.test-data` JSON Schema, validate/preview/import/export, raw JSON preservation,
  internal Parquet conversion, CSV/TSV/XLSX adapter, 25 MiB package threshold와 chunk manifest.
- **완료 조건:** metadata/unit/curve lossless round-trip과 tabular/JSON normalized equivalence.
- **테스트:** schema/semantic negatives, digest/checksum/path safety, large streaming/chunk memory.
- **구현 증거 (increment 1, 2026-07-18):** `cmp.test-data` validate/semantic preview, stable
  Test Data identity + immutable revision, typed condition/channel persistence, canonical JSON과
  normalized Parquet Artifact pin, list와 exact-revision JSON download를 PostgreSQL/API/UI까지
  연결했다. exact current ETag 기반 revision append와 과거 revision 재다운로드도 Docker에서
  검증했다. 뒤의 완료 증거에서 JSON+ZIP과 tabular adapter까지 같은 Task로 마무리했다.
- **완료 증거 (2026-07-18):** 기존 governed CSV/TSV/XLSX parser가 original row와 explicit
  normalized row/scale을 동시에 반환하도록 확장하고 canonical adapter API/UI에 연결했다.
  direct JSON과 CSV adapter의 canonical digest 동등성, XLSX 안전 parser, deterministic ZIP,
  checksum/path, immutable revision round-trip을 검증하여 T-52를 완료했다. 여러 capability를
  포함하는 대형 package profile은 계획대로 T-58에서 확장한다.

#### T-53. Mapping Profile and common Processing Workbench — `P0`

- **범위:** revisioned Attribute/channel Mapping Profile, method registry, crop, scale/shift,
  resample, moving-average, Savitzky–Golay, spline, alignment/statistics, stage overlay UI.
- **완료 조건:** 사용자가 mapping과 ordered steps를 편집하고 preview 후 immutable output을 만든다.
- **테스트:** method schema/composition, numeric public fixture, preview/commit separation, UI E2E.
- **Increment 1 증거 (2026-07-18):** explicit PostgreSQL identity/revision/binding tables에 Mapping
  Profile을 저장·개정하고 exact Attribute Definition revision을 고정한다. 일곱 개의 versioned
  deterministic method와 composed preview API, exact Test Data/profile/step editor, 공통 축 stage
  overlay를 연결했다. Docker/PostgreSQL에서 profile r1→r2와 실제 server preview를 검증했다.
- **완료 범위:** preview를 새 immutable Processing output revision으로 commit하고, 복수 curve
  alignment와 통계 method/API/UI를 연결한 뒤 전체 UI E2E와 `make ci`를 통과시킨다.
- **Increment 2 증거 (2026-07-18):** commit API는 exact Test Data/Profile revision을 서버에서 다시
  읽어 재계산하며 browser preview 배열을 받지 않는다. migration 064의 one-revision-only Output,
  ordered Step, composite exact FK와 Artifact FK에 저장하고 JSON을 digest와 함께 다운로드한다.
  Docker API와 연결 UI에서 commit/list/download 및 byte SHA-256 일치를 검증했다.
- **Increment 3 완료 증거 (2026-07-18):** 두 개 이상의 exact Test Data identity를 같은 Mapping
  Profile/ordered preprocessing으로 계산하고 관측 domain 교집합에서만 linear alignment한다.
  모든 member를 보존하며 mean/median/sample SD/MAD/IQR/95% mean CI와 수학적 가정을 API/UI에
  표시한다. 두 실제 Docker/PostgreSQL DP600 revision의 21-point 결과와 React/API/numeric 회귀를
  검증했다. Recipe revision, exact batch Selection과 retry/promotion은 T-54로 넘긴다.

#### T-54. Versioned Recipe library and batch execution — `P0`

- **범위:** Recipe draft/published revisions, library, exact input Selection, compatibility
  preflight, per-member Run/Attempt, Batch Monitor와 failed-member retry.
- **완료 조건:** 저장한 방식을 다른 Dataset 또는 검색 선택에 재사용하고 성공 결과를 보존한다.
- **테스트:** deterministic rerun, incompatible member, partial failure/retry, no overwrite, UI E2E.
- **Increment 1 증거 (2026-07-18):** common Recipe stable identity/immutable revision/ordered typed
  step을 migration 065로 추가하고 exact Mapping Profile revision+digest를 고정했다. API와 연결 UI가
  draft 생성, strong ETag revision append, reviewed publish와 Library 재선택을 지원한다. Docker
  PostgreSQL에서 r1 draft→r2 published와 exact pin을 검증했다.
- **Increment 2 완료 증거 (2026-07-18):** migration 066의 immutable Batch/Member/Attempt가 exact
  published Recipe와 exact Test Data revision을 고정한다. API는 member별 compatibility preflight,
  isolated execution, derived batch status, complete attempt history와 failed-only retry를 제공한다.
  성공 Output은 다른 member 실패 시에도 보존되고 retry는 이전 Attempt를 덮어쓰지 않는다.
  실제 Docker/PostgreSQL에서 DP600 두 revision을 Recipe r2로 preflight/실행해 2/2 Output 성공을
  확인했으며 React Batch Run Monitor와 browser screenshot으로 연결 상태를 검증했다.
- **상태:** `complete`. 대규모 비동기 queue 분산은 현재 계약을 바꾸지 않는 후속 최적화다.

### S-14.3. Deepen the three public-equation reference modeling tracks

#### T-55M. Metal elastoplastic workbench — `P0`

- **범위:** 복수 elastic/proof methods, explicit true/plastic conversion, manual/automatic necking
  candidate, Voce/Swift/Hockett–Sherby/Ghosh fitting, candidate combine와 bounded extrapolation.
- **완료 조건:** Recipe/Neutral JSON에 선택 방법과 domain이 남고 기존 two-solver card로 이어진다.
- **테스트:** analytical/golden numeric fixtures, bounds/residual/extrapolation regression, UI E2E.
- **구현 증거 (1차):** common method registry에 `metal.elastic_modulus`,
  `metal.proof_stress`, `metal.necking_candidate`, `metal.engineering_to_true_plastic`을 추가했다.
  E 산정은 OLS, Huber robust regression, chord, secant, manual을 명시적으로 구분한다. 자동 necking은
  후보만 보고하고 원본을 자르지 않으며, true/plastic 변환은 사용자가 확정한 index 또는 전체 관측
  domain을 선택한다. scalar 결과와 변환 curve는 Processing Output/Recipe/Batch의 기존 불변 계약으로
  재실행된다. normalized strain `1`, stress `Pa`가 아니면 계산을 거부한다.
- **구현 증거 (2차, 2026-07-18):** `metal.hardening_fit_extrapolate`가 공개 Voce,
  Swift, Hockett–Sherby, Ghosh 식을 동일한 normalized predicted-minus-observed least-squares로
  fitting한다. 2~4개 후보, fit domain, extrapolation maximum(`<=5`), 출력 point 수, primary/
  secondary와 조합 weight를 모두 Recipe option으로 요구한다. 각 parameter의 lower/initial/fitted/
  upper, RMSE/relative RMSE, observed/extrapolated domain과 candidate/selected curve가 immutable
  Output에 저장된다. UI는 네 후보와 선택 조합을 함께 표시한다. 실제 Docker/PostgreSQL에서
  `DP600-T55M-12PT r1`을 Recipe `r4 published`로 preflight/batch 실행해 Batch
  `7d37d8c3-27c9-4d00-8eee-30fefa078699`, Output revision
  `b3644458-1799-4fbc-bdd9-48a8230fefc3`, 101 points 성공을 확인했다.
- **구현 증거 (3차, 완료, 2026-07-18):** 선택된 `stress.hardening.selected` Processing Output의
  identity/revision/digest, source Test Data revision과 Mapping Profile revision을 정확히 고정하는
  tabulated-plasticity IR family `1.2.0`을 추가했다. 후보 family, primary/secondary 선택, blend
  weight, fit/extrapolation domain과 사용자 acknowledgement는 명시적 PostgreSQL column/constraint로
  저장되며, Processing Output과 source/profile의 composite tenant/classification FK 및 trigger가
  최종 method/version/digest를 검증한다. Material 상세의 elastoplastic workbench에서 exact Output을
  선택해 IR로 승격하고 같은 화면에서 Abaqus/OpenRadioss mapping preflight, preview, `.inp`/`.rad`
  download까지 실행한다. 실제 Docker/PostgreSQL에서 Output revision
  `b3644458-1799-4fbc-bdd9-48a8230fefc3`을 IR revision
  `4080a694-876d-483f-8b70-89db47fa6610`으로 승격하고 두 solver card의 ASCII download와 SHA-256을
  확인했다. 단위/domain/API/migration/React 회귀 테스트가 이 경로를 고정한다.
- **상태:** `complete`. Neutral Material 교환 envelope와 bulk package는 각각 T-56/T-58 범위다.

#### T-55P. Polymer linear-viscoelastic workbench — `P0`

- **범위:** relaxation/log-time processing, configurable Prony terms/bounds, manual/automatic term
  selection, manual/WLF/Arrhenius shift와 master curve, supported solver mappings.
- **완료 조건:** candidate/residual/domain을 비교하고 unsupported mapping을 명시적으로 차단한다.
- **테스트:** synthetic Maxwell/WLF/Arrhenius fixtures, term selection, mapping regression, UI E2E.
- **구현 증거 (완료, 2026-07-18):** 공통 method registry에
  `polymer.log_time_resample`과 `polymer.prony_fit_compare`를 추가했다. 사용자는 1~10 사이의
  후보 항수를 복수 지정하고 동일 normalized objective/bounds에서 비교한 뒤 BIC 자동 선택 또는
  명시적 항수 선택을 저장할 수 있다. 후보 curve, selected curve, RMSE, BIC, equilibrium/
  instantaneous modulus와 선택된 `g_i`, `tau_i`가 immutable Processing Output에 포함된다.
  Polymer relaxation Mapping Profile/Recipe template를 UI에서 바로 불러올 수 있다. 기존 exact
  Selection master-curve 경로는 manual/WLF에 Arrhenius fit을 추가했고, migration 068이 활성화에너지와
  shift residual evidence를 typed PostgreSQL column/row로 보존한다. 기존 reviewed linear-Prony IR와
  Abaqus 2025 `*VISCOELASTIC` preview/download는 유지한다. OpenRadioss LAW62는 별도 Ogden-Prony
  hyper-viscoelastic family이므로 linear Prony를 silent 변환하지 않고 `unsupported`로 차단한다.
  공통 1~10항 Output의 Neutral JSON/IR promotion은 T-67에서 완료했다.
- **상태:** `complete`. 계산·후보 비교·Recipe/Batch Output과 exact Output의 reviewed IR/Neutral/
  Abaqus card 연결이 T-67까지 완료됐다. Production material qualification은 별도다.

#### T-55E. Elastomer hyperelastic/hyper-viscoelastic workbench — `P0`

- **범위:** weighted uniaxial/planar/biaxial input, Neo-Hookean/Mooney–Rivlin/Yeoh/Ogden,
  multistart, stability/physical diagnostics와 optional Prony overlay.
- **완료 조건:** candidate를 사람이 선택·승격하고 지원되는 Abaqus/OpenRadioss card로 이어진다.
- **테스트:** public equation/limit fixtures, multi-test residual, stability and mapping regression.
- **구현 증거 (modeling 단계 완료, 2026-07-18):** 공개 incompressible
  Neo-Hookean/Mooney–Rivlin/Yeoh/one-term Ogden nominal-stress 식을 동일한 exact Dataset
  revisions와 normalized weighting에 적용한다. deterministic multistart 결과는 migration
  069의 family별 명시적 parameter column과 제약으로 저장한다. migration 070은 각 후보의
  observed/predicted/residual points를 immutable Parquet Artifact로 고정한다. API와 Workbench는
  family별 objective, calibration/holdout NRMSE, convergence, fitted-domain monotonicity warning,
  parameter와 curve/residual을 비교한다. 기존 Ogden--Prony 선택/승격/card 경로는 유지한다.
  네 family에 공통인 사람 선택과 Neutral IR 승격은 T-56, Abaqus/OpenRadioss capability와
  native ASCII는 T-57에서 완료한다. 따라서 제품 전체 완료로 해석하지 않는다.
- **상태:** `complete` for the T-55E calculation/comparison boundary; downstream delivery remains
  `T-56/T-57`.

### S-14.4. Exchange, deliver and document the selected model

#### T-56. Neutral Material JSON and IR promotion — `P0`

- **범위:** `cmp.neutral-material` validate/import/export, curve stages, candidate/selection,
  applicability, exact source/mapping/recipe revision과 IR promotion.
- **완료 조건:** export/import 뒤 같은 IR과 mapping report를 재현한다.
- **테스트:** schema/version/cross-scope negative, deterministic round-trip와 digest regression.
- **상태:** `complete` for the bounded hyperelastic family path. Migration 071, protected
  promote/validate/import/get/download API, connected human-selection UI, deterministic JSON
  Artifact, fresh PostgreSQL migration and live browser evidence are implemented. Solver capability
  consumption remains T-57.

#### T-57. Abaqus/OpenRadioss capability and native export — `P0`

- **범위:** 공식 solver 문서 기반 versioned capability manifest, six-state preflight/report,
  ASCII preview/download와 기존 exporter 확장.
- **완료 조건:** silent default/approximation 없이 각 지원 family의 card와 sidecar를 생성한다.
- **테스트:** approved semantic/golden fixture, parser/syntax hook와 unsupported negative.
- **상태:** `complete` for the declared reference scope. Migration 072 and the protected API pin an
  exact Neutral Material revision and persist typed family coefficients, six-state mapping evidence,
  card/report digests and native ASCII. Abaqus 2025 supports direct Neo-Hookean, Mooney--Rivlin,
  Yeoh and one-term Ogden keywords. OpenRadioss 2025 maps Neo-Hookean/Yeoh to LAW94 and
  Mooney--Rivlin/Ogden to LAW82; coefficient transforms and the explicit LAW82 `nu=0.495`
  approximation are never silent. The connected workbench requires preflight digest acknowledgement
  and provides preview, native download and mapping-report JSON. Actual solver execution is excluded.

#### T-58. Canonical Bulk JSON package — `P0`

- **상태:** `complete` for the declared canonical package scope. Migration 073 adds explicit exact
  revision source pairs and composite foreign keys for Test Data JSON, Mapping Profile, Processing
  Recipe, Neutral Material JSON and Neutral solver report/card. The existing deterministic
  Selection/Job/Bundle engine and connected UI now assemble all six representations without a
  generic payload. Manifest and checksum verification passed on a live 16-component Docker bundle.

- **범위:** 기존 immutable Bundle에 Test JSON, Mapping Profile, Recipe, Neutral JSON, mapping
  report와 native card package profile 추가.
- **완료 조건:** manifest/checksum이 모든 exact source와 representation을 검증한다.
- **테스트:** deterministic ZIP, omission/tamper/path negative와 large external worker assembly.

#### T-59. Administrator/User feature grants — `P1`

- **범위:** 제품 역할 두 개와 schema, catalog, processing/calibration, approval, export grants.
  기존 permission/RLS는 호환 enforcement로 유지한다.
- **완료 조건:** 작업 중심 권한 UI/API와 tenant 격리 regression이 통과한다.
- **테스트:** grant matrix positive/negative, legacy-token compatibility와 cross-scope RLS.
- **구현 증거 (`2026-07-18`):** Migration 074의 typed assignment와 append/revoke guard,
  product-to-internal permission projection, legacy role 호환 projection, effective/grant/list/revoke
  API 및 `/access` 관리자 화면을 연결했다. Docker/PostgreSQL demo group은 Administrator와 다섯
  grant를 실제 API에서 확인했다. 일반 User의 관리 API 403과 기능별 positive/negative 회귀를
  자동화했다.

#### T-60. End-to-end demo, manuals and screenshot gate — `P0`

- **범위:** demo Material/Test JSON/Recipe/Neutral JSON/cards, Dashboard 시작점, user/admin guide,
  deterministic GUI capture와 `make demo`/Compose 절차.
- **완료 조건:** tree/search/link → import → recipe/batch → fit → IR → preflight/card/bulk의 두
  solver 및 세 material-family reference 시나리오가 실제 API/PostgreSQL에서 완료된다.
- **테스트:** Playwright product journey, screenshot manifest, clean Compose seed와 `make ci`.
- **구현 증거 (`2026-07-18`):** migration 074의 빈 PostgreSQL/object-store 볼륨에서 Compose
  seed가 protected API만 사용하여 금속·폴리머·엘라스토머 reference 자료를 생성했다. 금속과
  엘라스토머의 Abaqus/OpenRadioss, 폴리머 Abaqus card를 `make demo-verify`로 재조회했다.
  Dashboard 세 family entry, deterministic fixture stamp, 통합 사용자 walkthrough와 desktop
  screenshot manifest를 연결했다. 실제 solver 실행·qualification은 범위에서 제외한다.
- **완료 감사 (`2026-07-18`):** 위 증거는 세 시작점과 기존 model/card 존재를 증명하지만,
  이 Task의 전체 완료 조건인 실제 domain Workflow link, UI import/recipe/batch/fitting,
  세 family Neutral JSON, native/ZIP download를 증명하지 않는다. 따라서 제품 전체 기준 상태를
  `partial`로 정정하고 T-61~T-65에서 남은 계약을 완료한다.

#### T-61. V3 completion audit and actionable web errors — `P0`

- **범위:** 요구사항별 증거 감사, capability/status 정정, web API 오류의 problem code와 trace ID 보존.
- **완료 조건:** bounded 구현과 전체 제품 완료 주장을 구분하고 모든 API 오류 화면에서 support
  reference를 복사할 수 있다.
- **테스트:** capability audit 문서 gate, common API client problem regression, 대표 UI error.

#### T-62. Domain-backed Material Workflow Explorer — `P0`

- **상태 (`2026-07-18`):** `implemented` (complete demo genealogy seeding remains T-65).
- **구현 증거:** migration 075 `catalog.domain_record_binding`, binding create/read API, Workflow
  graph projection, governed workbench deep links, migration/API/React/non-bypass PostgreSQL tests.

- **범위:** configurable Record revision을 Material/State/Test/Specimen/Dataset/Processing Output/
  Material Model/Neutral/Card/Release exact revision에 typed binding하고 기존 Record Link graph와 결합한다.
- **완료 조건:** 실제 Material identity에서 시작해 각 workbench exact revision으로 이동하며
  reverse navigation과 tenant/classification/immutability를 강제한다.
- **테스트:** endpoint별 composite FK, cross-scope/stale/latest negative, PostgreSQL graph와 Playwright.

#### T-63. Three-family canonical Neutral Material promotion — `P0`

- **상태 (`2026-07-18`):** `implemented`. Migration 076, closed three-family schema/domain,
  exact source-kind verification, promote/import/download API와 metal/polymer/hyper UI를 구현했다.
  family별 Neutral 기반 card/bulk consumer 통합은 T-64가 담당한다.

- **범위:** metal selected hardening, polymer selected generalized-Maxwell, hyperelastic optional
  Prony overlay를 closed typed union으로 추가하고 exact Processing/Recipe/Profile/Candidate evidence를 보존한다.
- **완료 조건:** 세 family document가 import/export round-trip 후 같은 IR과 mapping preflight를 재현한다.
- **테스트:** family parameter/curve/domain schema, exact source FK, digest tamper, numeric round-trip, UI.

#### T-64. Neutral exporter and Bulk parity — `P0`

- **상태 (`2026-07-18`):** `implemented`. Migration 077 generalizes the immutable Neutral solver
  card projection, the shared API/UI preflight flow consumes metal, polymer and elastomer Neutral
  revisions, and existing T-58 source discovery consumes every persisted family card without a
  second solver-specific copy. T-65 owns clean-seed download E2E and screenshots.
- **구현 경계:** metal maps to Abaqus `*PLASTIC` and OpenRadioss `LAW36`; generalized-Maxwell maps
  to Abaqus `*VISCOELASTIC` and reports OpenRadioss as `unsupported`; hyperelastic Prony overlays
  map to Abaqus and only one-term Ogden maps to OpenRadioss `LAW62`. Other potentials are rejected
  before generation rather than silently transformed.

- **범위:** 세 family Neutral revision에서 지원 target card/report를 생성하고 T-58 source discovery와 연결한다.
- **완료 조건:** 기존 bounded exporter 결과와 semantic equivalence를 유지하며 unsupported/approximation을
  명시하고 canonical bundle에 exact document/report/native card를 포함한다.
- **테스트:** Abaqus/OpenRadioss golden/semantic, stale preflight, bundle manifest/checksum.

#### T-65. Full clean-demo product journey — `P0`

- **상태 (`2026-07-18`):** `implemented`. Clean PostgreSQL seed가 canonical tensile Test JSON,
  exact Mapping Profile, published Processing Recipe, successful Batch Output, selected metal IR,
  Neutral JSON, Abaqus/OpenRadioss native card와 9-component checksum bundle을 생성한다.
  여덟 revision-pinned Catalog/Workflow 노드가 실제 domain revision에 연결되고, protected verifier와
  Playwright가 두 native ASCII와 ZIP을 다운로드해 SHA-256을 재검증한다. Migration 078은 caller RLS를
  우회해 데이터를 노출하지 않으면서 fully-scoped cross-module binding target만 검증한다.
- **범위:** actual Catalog binding, Test JSON, Mapping Profile, Recipe/Batch, selected Neutral,
  preflight/card와 Bulk ZIP을 clean Compose seed와 task-oriented UI journey에 연결한다.
- **완료 조건:** 세 family의 지원 범위에서 사용자가 실제 입력부터 결과 다운로드까지 수행하고
  Playwright가 native ASCII와 ZIP checksum을 검증한다.
- **테스트:** clean PostgreSQL seed/reseed, protected verifier, full Playwright downloads,
  screenshot manifest와 `make ci`.

#### T-66. Bidirectional exact-revision workflow navigation — `P0`

- **상태 (`2026-07-19`):** `implemented`.
- **범위:** exact domain kind/object/revision을 현재 Catalog RLS 범위에서 Record revision으로
  역조회한다. Material, canonical Test JSON, common Processing Output와 Neutral/Card workbench는
  **Exact linked data** 패널에서 같은 depth-5 graph와 Explorer deep link를 제공한다.
- **완료 조건:** Test JSON에서 Explorer로 역이동한 뒤 Material, Processing Output, Model IR,
  Neutral JSON과 Abaqus/OpenRadioss Card 노드를 한 화면에서 확인하고 각 exact workbench link를
  열 수 있다. 선택 노드의 direct edge만 forward/reverse 목록에 표시한다.
- **테스트:** protected API, PostgreSQL RLS reverse lookup, React navigation component, clean-demo
  Playwright reverse navigation, current screenshot와 user guide.

#### T-67. Reviewed generalized-Maxwell Output to card — `P0`

- **상태 (`2026-07-19`):** `implemented`.
- **범위:** ADR-0031에 따라 exact `polymer.prony_fit_compare` Processing Output을 검토하여
  1~10항 typed linear-viscoelastic IR, canonical Neutral Material JSON과 Abaqus native card로 연결한다.
- **완료 조건:** server가 Artifact에서 selected terms를 재구성하고 Test JSON/Mapping Profile/
  Processing Output/Property Set exact revision과 modulus-consistency evidence를 고정한다. UI는 후보
  선택 근거를 표시하고 명시적 review 이후에만 IR/Neutral/card를 생성한다. OpenRadioss는
  `unsupported`를 유지한다.
- **테스트:** 공개 generalized-Maxwell 수치 fixture, digest/step/unit/modulus mismatch negative,
  10-term PostgreSQL constraints, API/React/Playwright journey, Neutral round-trip와 Abaqus ASCII golden.
- **구현 증거 (`2026-07-19`):** migration 079가 exact Processing Output/Test Data/Mapping Profile/
  Property Set composite pin과 1~10항 ordered evidence를 저장한다. application service는 client가
  보낸 coefficient를 받지 않고 immutable Output Artifact를 다시 export·검증하여 final
  `polymer.prony_fit_compare` step의 selected terms와 BIC/RMSE를 재구성한다. UI는 사례별 허용
  G₀ mismatch와 명시적 review를 요구하고 IR evidence, Neutral JSON, Abaqus `*VISCOELASTIC`
  mapping/card를 같은 화면에 연결한다. Clean Compose seed/verifier와 PostgreSQL head migration,
  React regression, 현재 GUI capture가 이 경로를 확인한다. OpenRadioss는 `unsupported`다.

#### T-68. Conditional OpenRadioss linear-Prony card — `P0`

- **상태 (`2026-07-19`):** `implemented`.
- **범위:** ADR-0032에 따라 reviewed generalized-Maxwell Neutral revision을 OpenRadioss 2025
  `/MAT/LAW1` + `/VISC/LPRONY` native reference fragment로 조건부 생성한다. LAW62 변환은 금지한다.
- **허용 경계:** bulk relaxation 미특성화, 모든 `k_ratio=0`, `0.49 <= nu < 0.5`, Form 2,
  `flag_visc=2`. 외부 solid `/PROP`의 `I_smstr=10/12` 요구와 nearly-incompressible shear-only
  가정은 `approximated` mapping으로 사용자 확인을 요구한다. 그 밖의 조합은 `unsupported`다.
- **완료 조건:** exact Neutral revision에서 ratio/time을 재계산 없이 렌더링하고 official keyword
  URL, capability manifest, mapping report, preview/download, immutable card persistence를 같은 기존
  API/UI 흐름으로 제공한다. 실제 solver 실행 검증은 포함하지 않는다.
- **테스트:** eligibility 경계, bulk negative, deterministic ASCII golden, stale report digest,
  capability manifest, React acknowledgement, PostgreSQL/API와 clean-demo browser evidence.
- **구현 증거 (`2026-07-19`):** family-neutral exporter `2.1.0`이 조건을 서버에서 재검증하고
  LAW1/LPRONY ASCII와 official documentation URL을 생성한다. 기존 migration 077의 typed target,
  mapping row, ordered Prony row와 immutable card projection을 재사용하므로 새 DB migration은
  필요하지 않다. returning workbench는 exact Processing Output/State/Property evidence로 기존
  Neutral revision을 다시 열어 중복 promotion 없이 preflight를 계속한다. Clean Compose seed와
  protected verifier가 같은 Neutral revision의 Abaqus/OpenRadioss 다운로드 SHA-256을 확인했고,
  browser capture는 approximation 확인과 native preview를 검증했다.

#### T-69. Saved polymer Recipe/Batch to dual-solver package — `P0`

- **상태 (`2026-07-19`):** `implemented` and verified.
- **범위:** published polymer Processing Recipe를 exact Test JSON에 Batch 실행하고, 성공한 Attempt의
  Output을 reviewed generalized-Maxwell IR, Neutral JSON, Abaqus/OpenRadioss 카드와 Bulk ZIP으로
  연결한다.
- **완료 조건:** IR `1.3.0`이 exact Recipe digest와 Batch/Member/Attempt/Output revision을 고정하고,
  Neutral JSON이 `processing_recipe=exact_revision`을 제공한다. clean seed/verifier는 같은 Recipe의
  JSON, Neutral, 두 mapping report/card가 들어간 checksum package를 검증한다.
- **DB/API/UI:** migration 080의 typed nullable origin columns/all-or-none FK/validation trigger,
  Processing-owned origin resolver, connected polymer evidence panel과 Recipe/Batch monitor link.
- **테스트:** domain invariants, migration, PostgreSQL exact origin, React, clean Compose seed/verifier,
  browser screenshot, full `make ci`.

#### T-70. Saved metal Recipe/Batch to dual-solver package — `P0`

- **상태 (`2026-07-19`):** `implemented` and verified.
- **범위:** 기존 published metal Processing Recipe/Batch 계산을 다시 구현하지 않고, 성공한 exact
  Attempt의 Output을 processed tabulated-plasticity IR, Neutral JSON, Abaqus/OpenRadioss 카드와
  Bulk ZIP까지 추적한다.
- **완료 조건:** 신규 IR `1.3.0`이 exact Recipe digest와 Batch/Member/Attempt/Output revision을
  고정하고 Neutral JSON은 `processing_recipe=exact_revision`을 제공한다. 기존 direct Output IR
  `1.2.0`은 수정하지 않고 계속 읽는다.
- **DB/API/UI:** migration 081의 typed nullable origin columns, exact composite FKs, all-or-none
  constraint와 deferred successful-Attempt validator; 금속 IR evidence와 Recipe/Batch monitor link.
- **테스트:** domain/service/migration/PostgreSQL/API/React, clean Compose protected verifier,
  browser screenshot와 full CI. 격리 PostgreSQL suite는 76개 모두 통과했고, 전체 CI는
  Python 773개 통과/환경-gated 76개 skip(앞선 suite에서 실행), frontend 61개 통과 및
  architecture/contract/user-guide/production bundle gate를 통과했다.

#### T-71. Explorer-integrated search and saved Subsets — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`; full CI passed with 774 Python tests
  (`76` environment-gated PostgreSQL tests skipped by the default runner after separate protected
  Docker verification) and 62 frontend tests.
- **범위:** Catalog tree와 별도 Records 검색 화면 사이의 탐색 단절을 제거한다. Explorer에서
  Table을 선택하고 이름/key/설명/text Attribute를 검색하거나 저장된 Subset revision을 적용한다.
- **완료 조건:** 검색 결과의 exact current Record revision을 선택하면 같은 화면의 Workflow graph,
  forward/reverse links와 governed workbench deep link가 열린다. Subset의 folder/discrete/normalized
  number filter도 숨김 없이 기존 typed search API에 전달한다.
- **DB/API/UI:** 기존 explicit Record/typed value/Subset revision과 search API를 재사용하고,
  Explorer가 Subset을 table별로 로드해 query를 실행한다. clean demo는 재사용 가능한 DP780
  workflow Subset을 seed한다.
- **회귀:** React는 저장된 filter 변환과 exact revision navigation을 검증한다. protected verifier는
  clean reseed의 Subset identity/filter를 검사한다. processed IR이 추가된 DB의 reseed가 임의 model
  order에 의존하지 않도록 exact Dataset-derived model 선택 회귀도 포함한다.

#### T-72. Reusable hyperelastic Calibration Plan library — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`; isolated PostgreSQL suite 76건,
  full CI Python 774건과 frontend 62건이 모두 통과했다.
- **범위:** 생성 후 화면에서 다시 찾을 수 없던 multi-test hyperelastic Calibration Plan을
  Material State의 Modeling Workbench 안에서 목록·조회·재사용한다.
- **완료 조건:** 사용자는 저장된 exact Plan revision을 그대로 재실행하거나, 고정된 Plan
  identity를 불러와 Dataset 역할/mode/weight를 수정하고 compare-and-swap 방식으로 새 revision을
  추가한다. label, Material State identity와 baseline model identity는 변경할 수 없다.
- **DB/API/UI:** 기존 `modeling.ogden_calibration_plan*` typed identity/revision/member 테이블과
  revision kernel을 재사용한다. list/get/revise API, strong ETag, `Saved Calibration Plan library`,
  `Use exact revision`, `Save new Plan revision` 흐름을 연결한다. schema 변경이 없어 migration은
  추가하지 않는다.
- **회귀:** API contract, stale/stable identity revision 규칙, 실제 PostgreSQL r1→r2 append와
  tenant visibility, React request translation, production build와 live Docker/browser 화면을 검증한다.

#### T-73. Integrated product v3 completion audit — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** capability map, 실제 코드, clean PostgreSQL seed/verifier, 브라우저 evidence와 사용자
  가이드를 다시 대조해 통합 v3 목표의 완료 경계를 확정한다.
- **판정:** configurable Table/typed Attribute/Layout/Subset, Catalog/Workflow Explorer,
  search/compare/exact links, Test JSON, Mapping Profile, Processing Recipe/Batch, 금속·폴리머·
  엘라스토머 modeling, Neutral JSON, Abaqus/OpenRadioss card와 checksum Bulk ZIP은 v3의 bounded
  reference 범위에서 DB/API/UI/Test 증거가 모두 있다.
- **예외:** 고정 Material/State property는 configurable Catalog와 병행되는 compatibility
  projection이라 `partial`을 유지한다. actual solver execution, production material qualification,
  production identity/object-store 운영은 계획에서 명시한 후속 범위다.
- **검증:** 최종 full CI Python 774건, 별도 PostgreSQL 76건, frontend 62건, clean-demo verifier,
  55개 GUI capture gate와 문서/아키텍처/계약/OpenAPI/bundle gate가 통과했다.

#### T-74. Product experience reset and completion correction — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** T-73의 bounded engineering evidence는 보존하되 제품 완료 결론을 철회한다.
  ADR-0034와 `docs/01-product/product-experience-spec.md`를 사용자-facing 단일 기준으로 삼고,
  engine evidence와 product acceptance를 분리한다.
- **완료 조건:** README, implementation status, capability map, requirements와 architecture가
  visible API/token, flat Explorer와 disconnected Modeling UI를 완료로 표현하지 않는다.
- **테스트:** 문서 링크/guide gate, `git diff --check`, architecture/contract 문서 정합성.
  Full CI는 Python 774건(별도 PostgreSQL 환경이 필요한 76건 skip), frontend 62건과 static
  type/architecture/contracts/OpenAPI/user-guide/bundle gate를 통과했다.

#### T-75. Hidden product session, product shell and Dashboard — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** visible API connection/bearer token을 제거한다. demo는 same-origin 자동 session,
  non-demo는 일반 login boundary를 사용한다. primary navigation을 Material Database, Material
  Modeling, Jobs & Reviews, Administration으로 교체하고 Dashboard를 material search/recent/
  favorite/modeling/job/review/create/import 중심으로 재구성한다.
- **완료 조건:** clean demo 접속 후 configuration dialog 없이 데이터가 보이고 token 만료가 빈
  화면을 만들지 않는다. 기존 bearer API는 integration compatibility로만 유지한다.
- **테스트:** session refresh/error, no-token-text DOM assertion, Dashboard→workspace E2E, screenshot.
  Frontend 62건과 TypeScript/Vite/bundle gate가 통과했고 clean Docker browser에서 자동 session,
  세 demo Material과 다섯 product navigation을 확인했다. 화면 증거는
  `docs/15-demo/evidence/t75-product-session-shell.md`에 기록했다.

#### T-76. Persistent hierarchical Material Database Contents Tree — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** Database/Profile → Table → nested Folder → Record tree와 exact-link Workflow Tree를
  product read model로 제공한다. 기존 Folder/Record/Subset/Link/Binding engine을 재사용한다.
- **완료 조건:** tree는 datasheet와 linked workbench 이동 중 유지되고 selection/expansion,
  Subset, breadcrumb, deep link와 version state를 보존한다. workflow는 flat card list가 아니다.
- **테스트:** nested folders, cycles, lazy expansion, subset visibility, reverse link, deep-link E2E.
  `/database`의 실제 Docker/PostgreSQL 화면에서 DP780의 Metals → Steels 계층, 8-node/7-link exact
  workflow, Test Data workbench 이동과 복귀를 확인했다. Migration 082는 같은 stable Record의 새
  revision이 같은 exact domain revision을 다시 고정할 수 있게 하되 다른 stable Record의 중복
  소유는 거부한다. Record Link endpoint pin 전진과 비활성화도 append-only link revision으로
  검증한다. 화면 증거는 `docs/15-demo/evidence/t76-material-database-tree.md`에 있다.

#### T-77. Layout Datasheet, AMDC-style search and comparison — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** three-pane Material Database에서 Layout-driven Datasheet, quick/advanced search,
  discrete facet/normalized-range filters, record compare와 exact-revision tab을 제공한다. record
  tabs는 Workflow/Datasheet/Properties/Curves/CAE Cards/Links다. curve Attribute는 artifact provenance와
  linked Test Data 이동을 제공하며, channel semantics가 필요한 raw/normalized/processed overlay는
  가짜 generic plot으로 만들지 않고 T-79 persistent Modeling plot에서 구현한다.
- **완료 조건:** tree와 search가 동일 datasheet를 열고 linked/local values 및 revision context를
  구분하며, 관련 record를 열어도 browse context가 유지된다. 관리자가 여러 Layout을 정의하면
  datasheet와 비교 화면에서 Layout을 선택하고 그 item 순서로 값을 읽는다.
- **테스트:** typed filter/normalization, Layout, exact revision, linked navigation과 comparison을
  Vitest 및 live Docker/PostgreSQL Playwright 화면으로 검증했다. clean seed/reseed는 같은 Record
  revision을 유지했다. 화면 증거는 `docs/15-demo/evidence/t77-material-datasheet-search.md`에 있다.

#### T-78. Product Administration and extensible access — `P1`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** Administrator/User, 기능 토글, Database/Profile/Table/Attribute/Layout/Subset/Link Type
  관리를 하나의 task-oriented Administration에 통합한다. 내부 granular enforcement는 유지한다.
- **완료 조건:** 일반 권한 설정은 policy vocabulary 없이 가능하고, future resource/action/scope
  grant가 schema rewrite 없이 추가될 extension point가 contract test로 고정된다.
- **테스트:** product `/administration`은 Overview/Database design/Users & access를 하나의 좌측 작업
  구조로 제공한다. database 화면은 clean demo의 8 typed Attributes/Layout/Subset/Link Type을 읽고
  exact Table revision을 사용하는 새 Link Type을 만들 수 있다. access 화면은 token/API/principal/
  issuer/classification policy vocabulary를 숨기고 Administrator/User와 다섯 product capability만
  표시한다. 화면 증거는 `docs/15-demo/evidence/t78-product-administration.md`에 있다.

#### T-79. Graph-centered Material Modeling shell and data preparation — `P0`

- **상태 (`2026-07-19`):** `implemented and verified`.
- **범위:** Dataset/curve list, persistent main plot, step options와 Import → Map → Prepare → Fit →
  Extrapolate → Card navigation을 한 workspace로 제공한다. Test JSON/CSV/XLSX, Mapping Profile,
  common Processing methods와 preview/commit engine을 재사용한다.
- **완료 조건:** raw/normalized/processed overlay와 diagnostics가 option 변경 즉시 preview되고,
  명시적 commit만 immutable Output을 만든다. UUID 복사나 module route 이동이 필요 없다.
- **테스트:** import/map, step reorder/options, preview-vs-commit, curve stage E2E와 screenshot.
- **구현 증거:** `/modeling`은 exact Test Data 목록, ordered Recipe 단계, 서버 계산 curve overlay와
  선택 단계의 구조화된 option editor를 한 3열 작업공간에 유지한다. 게시된 Recipe를 불러와
  raw/mapped/processed/fitted/extrapolated stage를 비교할 수 있으며 상세 JSON과 수치 parameter는
  고급 펼침 영역으로 분리했다. 실제 Docker/PostgreSQL 데모와 회귀 증거는
  `docs/15-demo/evidence/t79-material-modeling-workspace.md`에 있다. Family별 완전한 option/candidate
  UX와 Recipe/Batch 통합은 T-80, Neutral/Card 연결은 T-81이다.

#### T-80. Family modeling tracks and reusable Recipe/Batch UX — `P0`

- **범위:** 같은 Workbench shell에서 metal elastoplastic, polymer viscoelastic, elastomer
  hyperelastic/hyper-viscoelastic methods를 제공하고 Recipe save/revise/reuse와 Batch preflight/
  execution/retry/monitor를 연결한다.
- **완료 조건:** 금속 E/proof/necking/four-family fitting/combination/extrapolation, polymer
  Prony/WLF/Arrhenius, elastomer multi-mode/four-family/stability/Prony overlay를 plot과 option panel에서
  실행·비교한다.
- **테스트:** existing numeric fixtures + family-specific browser journeys + deterministic Recipe/Batch.
- **구현 증거:** `/modeling`의 Metal/Polymer/Elastomer tab이 family별 Mapping/Method 계약과 exact
  Material/State/Property context를 전환한다. Step/Recipe/Batch inspector가 persistent graph 옆에서
  save/publish/preflight/execute/retry를 제공한다. 실제 Docker journey에서 metal hardening 네 후보,
  polymer log-time/Prony, elastomer 4 exact curve Plan·4 family·8 multistart·residual을 실행했다.
  `docs/15-demo/evidence/t80-family-modeling-tracks.md`에 screenshot과 검증 결과가 있다. T-81의
  reviewed Neutral/Card final step을 제외하고 T-80은 완료·검증됐다.

#### T-81. Reviewed result to Neutral Material and solver cards — `P0`

- **범위:** candidate review, exact Recipe/Batch/Attempt/Output evidence, Neutral JSON, mapping preflight,
  Abaqus/OpenRadioss preview/download와 Material Datasheet backlink를 Workbench 마지막 단계에 통합한다.
- **완료 조건:** silent mapping 없이 card를 내려받고 Material record에서 Test/Recipe/Neutral/Card
  exact links를 다시 열 수 있다. 기존 exporters와 Bulk package engine을 재사용한다.
- **테스트:** three-family Neutral/card semantic regression, download SHA-256, linked return E2E.
- **Engine integration evidence:** `verified`; **product GUI completion:** `rejected by T-84`.
  All three family tracks use the same four-state
  reviewed-delivery panel. It summarizes exact source/selection/model evidence, restores an existing
  Processing Output-backed Neutral revision on re-entry, downloads canonical Neutral JSON, runs the
  existing six-state preflight, requires approximation acknowledgement and previews/downloads the
  native card plus mapping report. Material-datasheet and bulk-package navigation are direct product
  actions. The live metal, polymer and elastomer journeys and current screenshot are recorded in
  `docs/15-demo/evidence/t81-reviewed-delivery.md`. This evidence is retained while T-85~T-90
  replace the long form stack and generic option editor with graph-direct family workbenches.

#### T-82. Realistic hierarchical demo and task-oriented manuals — `P0`

- **범위:** one-table flat seed를 Metals/Polymers/Elastomers와 Tensile/Relaxation/Hyperelastic nested
  hierarchy로 교체한다. 사용자는 ID를 복사하지 않고 tree/search에서 세 흐름을 발견한다.
- **완료 조건:** auto-session clean demo, current GUI captures, user/admin guide와 screenshot manifest가
  새 product shell 및 workspace를 설명한다.
- **테스트:** clean volume seed/reseed, tree counts/links, guide capture gate, desktop responsive E2E.

#### T-83. Product acceptance audit — `P0`

- **범위:** `product-experience-spec.md`의 모든 explicit requirement를 clean deployment에서 감사한다.
- **완료 조건:** home에서 시작해 material find → datasheet/test curve → modeling processing/fitting →
  candidate/extrapolation → Recipe reuse → Neutral → two solver cards → linked Material return을 사람이
  이해 가능한 label만으로 완료한다. API/seed/direct-deep-link evidence로 대체하지 않는다.
- **테스트:** full Playwright journey, downloads, screenshots, manuals, `make ci`와 protected PostgreSQL.

T-82/T-83 are superseded as product-GUI completion tasks by the stricter T-84~T-93 sequence in
[`gui-functional-parity-plan.md`](../01-product/gui-functional-parity-plan.md). Their demo/manual and
clean-acceptance intent is retained in T-93.

#### T-84. Product status correction and interaction inventory — `P0`

- **상태 (`2026-07-20`):** `completed`. 공개 GUI reference 20개, interaction inventory,
  과장된 완료 판정 철회와 T-85~T-93 acceptance 기준이 권위 계획서에 고정됐다.
- T-79~T-81을 engine evidence와 GUI acceptance로 분리하고 공개 workflow의 action/result를
  Capability/Interaction/E2E 대응표로 고정한다.
- 기존 component와 API를 유지·재배치·교체·누락으로 분류하고 안정 체크포인트를 보존한다.

#### T-85. Engineering shell and graph foundation — `P0`

- compact session/task shell, curve rail, persistent graph, task inspector와 stage/status bar.
- auto first plot, axis/unit/tick/tooltip, zoom/pan, legend/visibility와 cancellable preview.
- Dashboard를 마케팅 소개 화면이 아닌 제품 작업 홈으로 교체한다. 첫 화면에서
  `Material Database`(tree/search/datasheet)와 `Material Modeling`(prepare/fit/extrapolate/card)의
  목적과 다음 동작을 분리하고, 최근 Material/진행 중 session/reference workflow로 바로 이동한다.
- Dashboard 합격 기준은 두 코어 경로의 차이와 연결 관계를 별도 설명 없이 이해하고 각각 한 번의
  동작으로 시작할 수 있는 것이다. Job, API, token, tenant, UUID 중심 상태판은 허용하지 않는다.
- **상태 (`2026-07-20`):** `completed`. reusable `EngineeringCurvePlot`, series별 독립 x-grid,
  family-compatible curve rail, axis/unit/tick/crosshair, zoom/pan/reset/visibility와 compact
  1440×900 shell이 live Compose에서 검증됐다. 이후 range/point command의 ephemeral overlay와
  Recipe draft 적용, 300 ms debounce/이전 request cancellation, Database/Modeling 작업 레인
  Dashboard까지 연결했다. 이후 exact Material Datasheet/Test Data/recent session context 복원,
  supplemental panel disclosure와 Elastic Modulus 전용 method/range/manual slider까지 실제
  Docker 브라우저에서 검증했다. T-86 이후의 method-specific 작업은 별도 Task로 계속한다.
- **증거:** `docs/15-demo/evidence/t85-engineering-modeling-shell.md`,
  `docs/15-demo/images/t85-engineering-modeling-shell.png`.

#### T-86. Metal Prepare direct manipulation — `P0`

- smoothing/mean/statistics, elastic methods/range/manual slider, proof/necking markers와 Workup.
- **상태 (`2026-07-20`):** `completed`. exact curve include/exclude, guided crop/scale-shift/resample/
  moving-average/Savitzky–Golay/spline, elastic method 5종, graph range, manual E slider, proof offset,
  necking point-to-Workup 적용과 true/plastic policy가 persistent graph와 inspector에 연결됐다.
  서버는 복수 exact revision에 공통 전처리만 적용해 observed-domain intersection에서 member/mean/
  95% mean CI를 계산한다. 세 synthetic DP780 replicate와 1440×900 Docker 증거를 포함한다.
- **증거:** `docs/15-demo/evidence/t86-metal-prepare-direct-manipulation.md`,
  `docs/15-demo/images/t86-metal-prepare-workbench.png`,
  `docs/15-demo/images/t86-metal-replicate-statistics.png`.

#### T-87. Metal Fit and Extrapolate direct manipulation — `P0`

- four-family comparison, residual/derivative, fit domain, parameter/bounds, ratio slider와 save.
- **상태 (`2026-07-20`):** `completed`. 동일한 server preview가 Voce/Swift/Hockett–Sherby/
  Ghosh 후보, 관측 true-plastic workup, 선택 blend를 persistent graph에 표시한다. Response,
  predicted-minus-observed Residual, numerical Tangent Modulus 보기를 전환하며 fit boundary 이후는
  shaded/dashed `EXTRAPOLATED · UNOBSERVED` 영역으로 구분한다. 후보별 relative RMSE를 첫 화면에서
  비교하고 parameter의 lower/fitted/upper와 bound sticking을 inspector에서 검토한다. graph range,
  primary/secondary, blend ratio와 bounded strain을 300 ms cancellable server preview에 연결하고,
  선택 이유를 Recipe option에 보존한다. 저장/commit은 기존 immutable Recipe/Processing Output
  경계를 사용하며 preview가 source를 덮어쓰지 않는다.
- **증거:** `docs/15-demo/evidence/t87-metal-fit-extrapolation.md`,
  `docs/15-demo/images/t87-metal-fit-candidate-comparison.png`,
  `docs/15-demo/images/t87-metal-fit-residual.png`.

#### T-88. In-workbench Neutral and Card delivery — `P0`

- **상태 (`2026-07-20`):** `complete`. `/modeling` 상단의 **Card** task가 Fit graph 아래의
  legacy delivery drawer를 대체한다. exact Material/State와 reviewed Processing Output/IR을 고정한 뒤
  기존 canonical Neutral Material revision을 복원하고, solver/version/law/material identity를 같은
  task에서 설정한다. six-state mapping legend와 field-level preflight를 항상 표시하며
  `approximated`는 명시적 acknowledgement를 요구하고 `unsupported`는 생성을 차단한다. 생성 후
  evidence/mapping은 접어 native ASCII result에 공간을 주되 다시 열어 검토할 수 있다. 실제 Docker/
  PostgreSQL browser journey가 Abaqus `.inp`, OpenRadioss `.rad`와 mapping JSON download를 검증했다.
- **범위:** guided Neutral review, solver/version/law form, six-state mapping과 two native card downloads.
- **증거:** `docs/15-demo/evidence/t88-neutral-card-delivery.md`,
  `docs/15-demo/images/t88-abaqus-card-delivery.png`,
  `docs/15-demo/images/t88-openradioss-card-delivery.png`.

#### T-89. Polymer workbench parity — `P0`

- **상태 (`2026-07-20`):** `complete`. Relaxation과 DMA Test JSON을 quantity semantics로
  구분하고 compatible Mapping Profile/Recipe를 자동 선택한다. relaxation은 log-time resampling,
  Prony 후보·잔차와 WLF/Arrhenius master curve를 제공한다. DMA는 storage/loss를 하나의 Prony
  parameter set으로 동시 fitting하고 log-frequency response/residual, BIC, nRMSE와 ordered term을
  표시한다. 두 경로 모두 exact Batch Output→IR→Neutral JSON→Abaqus/OpenRadioss card로 이어지며,
  OpenRadioss 근사는 명시적 확인 없이는 생성할 수 없다.
- **증거:** `docs/15-demo/evidence/t89-polymer-viscoelastic-workbench.md`와
  `docs/15-demo/images/t89-polymer-*.png`.

#### T-90. Elastomer workbench parity — `P0`

- **상태 (`2026-07-20`):** `complete`. `/modeling`의 Elastomer Fit은 저장된 exact Plan과
  Dataset 역할/mode/weight, reviewed Run과 selected family diagnostics를 자동 복원한다. normal
  path에서 Run UUID 입력은 필요하지 않다. 3 calibration + 1 holdout, uniaxial/planar/biaxial,
  네 public family와 8 multistart Candidate를 사용하며 family rail과 52-point response/residual
  graph를 1440×900 첫 viewport에 함께 표시한다. 현재 model revision의 ordered Prony overlay도
  독립 evidence로 표시한다. 같은 session에서 Neutral JSON과 Abaqus Ogden+Prony/OpenRadioss
  LAW62 native ASCII를 preview/download하며 approximation/ignored mapping은 명시적 확인 없이
  새 Card를 만들 수 없다.
- **증거:** `docs/15-demo/evidence/t90-elastomer-multimode-workbench.md`와
  `docs/15-demo/images/t90-elastomer-*.png`.

#### T-91. Material Database tree and datasheet parity — `P0`

- **상태 (`2026-07-20`):** `complete`. `/database`는 clean demo 진입 시 첫 유용한
  Record와 그 nested Folder 경로를 자동으로 열고 실제 Layout Datasheet를 표시한다. 좌측은
  Catalog/Workflow projection을 전환하며 Workflow는 8 exact revision Record와 7 typed link를
  복제 없이 투영한다. 중앙은 Overview/Properties/Curves/Test Data/Models/CAE Cards/Links를,
  우측은 forward/reverse Related와 immutable Revisions를 제공한다. 방향키/Home/End으로 tree를
  이동·전개·축소하고 마지막 exact revision 문맥을 session에서 복원한다. 검색·Layout 비교와
  normalized facet/range 엔진은 유지된다.
- **증거:** `docs/15-demo/evidence/t91-material-database-parity.md`와
  `docs/15-demo/images/t91-material-database-*.png`.

#### T-92. Search/Compare/Admin and Recipe/Batch polish — `P1`

- **상태 (`2026-07-20`):** `complete`. T-77/T-91의 typed text/facet/normalized range 검색,
  saved Subset과 Layout 비교를 유지한다. Administration은 Table, typed Attribute, Layout,
  Subset, Link Type과 단순 Admin/User access 작업으로 안내한다. Modeling inspector는 현재
  material family의 published Recipe를 자동 복원하고 lifecycle/exact revision을 표시하며,
  clone/new revision/publish를 제공한다. Batch monitor는 다른 family run을 숨기고 exact Test
  Data compatibility를 member별 output point/diagnostic으로 preflight하며 성공/전체 attempt와
  실패 재실행 상태를 표시한다.
- **증거:** `docs/15-demo/evidence/t92-search-admin-recipe-batch.md`와
  `docs/15-demo/images/t92-*.png`.

#### T-93. Clean clone-level product acceptance — `P0`

- **상태 (`2026-07-20`):** `complete` for the bounded reference product. 기존 demo PostgreSQL과
  object volume을 제거한 뒤 migration/build/seed를 처음부터 실행했다. clean verifier는 8-node
  Material workflow, 금속 3 replicate와 19-component bulk, Polymer relaxation/DMA, Elastomer 4
  Dataset·52 diagnostics point, 그리고 reference 범위의 Abaqus/OpenRadioss native card를 재현했다.
  실제 브라우저에서 Dashboard → Database Datasheet/links → Metal/Polymer/Elastomer graph → 각
  Card task를 확인했다. 이전 seed의 session revision이 남은 경우 새 Catalog의 유효 Record로
  fallback하는 회귀도 추가했다.
- **검증:** Ruff, mypy 652 files, architecture, OpenAPI lint/compat, Python 779 passed/76 expected
  skipped, actual PostgreSQL 76 passed, frontend 34 files/83 tests, production bundle budgets,
  user-guide checker, clean Docker seed/verifier와 live browser.
- **증거:** `docs/15-demo/evidence/t93-clean-product-acceptance.md`와
  `docs/15-demo/images/t93-clean-*.png`.
- **명시적 경계:** 공개식 기반 reference model 제품 흐름의 승인이다. 실제 solver 실행 상관,
  회사별 재료 qualification과 production-approved model 승인은 여전히 별도 검증 대상이다.
