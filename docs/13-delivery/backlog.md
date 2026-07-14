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

- **MVP progress (2026-07-13):** Material, Material State, and typed basic Property Set revisions
  are implemented with explicit PostgreSQL tables/constraints/indexes/RLS, create/search/detail/
  compare APIs, and same-transaction lifecycle/provenance/audit hooks. Process/Lot/Batch genealogy
  and its multi-lot acceptance fixtures remain pending; this records a completed MVP subset, not the
  full T-07 task.

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

- **목적:** geometry/mesh/BC/output template과 managed/manual solver 실행을 versioned plan으로 관리한다.
- **입력과 출력:** 입력은 card/IR, template revision, solver target, runner; 출력은 deck, external job ref, logs, native result manifest.
- **영향 데이터/API:** `validation.template*`, `plan*`, `run`, runner capability; validation submit/poll/cancel/attach API.
- **범위/제외:** mock runner와 generic scheduler contract 포함; 실제 HPC/solver adapter는 target 결정 후 구현.
- **선행 작업:** T-25, T-15, T-18, T-10.
- **완료 조건:** mock managed run과 manual attach가 동일 Result Manifest/provenance 요구를 충족한다.
- **테스트:** 단위—template/command allowlist/status mapping; 통합—submit/poll/cancel/collect; 회귀—shell injection, wrong solver version, license/queue timeout, callback replay.
- **담당:** Software runner; CAE Domain Expert가 template/solver settings 승인.

#### T-28. Result extraction, numerical health, experimental validation — `P0`

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

#### T-36. Backup/restore, object integrity, disaster-recovery drill — `P1`

- **목적:** metadata, raw, release, plugin artifact를 목표 RPO/RTO 안에서 복구하고 digest/lineage를 검증한다.
- **입력과 출력:** 입력은 backup policy/snapshots/object versions; 출력은 restored environment, integrity/completeness report.
- **영향 데이터/API:** backup config, integrity/reconciliation jobs; admin drill records.
- **범위/제외:** automated backup/restore verification 포함; multi-region active-active 제외.
- **선행 작업:** T-10, T-13, T-30, T-35.
- **완료 조건:** 격리 환경 restore 후 sample release/raw digest와 lineage가 일치하고 drill 시간이 기록된다.
- **테스트:** 단위—manifest verifier; 통합—DB+object restore; 회귀—missing object version, RLS backup omission, key access failure.
- **담당:** Platform/Software 주 담당; Security/Data Owner가 retention/restore acceptance 승인.

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

- **목적:** 선정 구성방정식과 calibration policy를 구현한다.
- **입력과 출력:** processed selection/plan → parameter candidates, diagnostics, IR payload.
- **영향 데이터/API:** model payload schema와 plugin manifest; core API 변경 없음이 목표.
- **범위/제외:** 선정 model/observable/domain만 포함; 다른 material family 제외.
- **선행 작업:** Stage 0 결정, T-22~T-24.
- **완료 조건:** analytic/literature/internal reference와 tolerance 일치, identifiability/invalid input evidence 승인.
- **테스트:** 단위—constitutive limits/Jacobian 또는 response; 통합—calibration; 회귀—reference parameter/curve/IR.
- **담당:** Scientific Software 구현; Constitutive Domain Expert 주 승인.

### T-D03. `[TBD]` Solver Exporter·Validation plugin

- **목적:** 선정 solver/version/card로 IR을 mapping하고 virtual specimen에서 검증한다.
- **입력과 출력:** IR/template/reference → card, mapping report, solver result, metrics.
- **영향 데이터/API:** exporter capability, validation template/profile; core API 변경 없음이 목표.
- **범위/제외:** 선정 solver/version/card/template만 포함; 다른 solver 제외.
- **선행 작업:** Stage 0 결정, T-25~T-28.
- **완료 조건:** domain-approved golden card와 reference solver result 일치, unsupported/approximation policy 검증.
- **테스트:** 단위—mapping/parser/units; 통합—IR→solver→metrics; 회귀—golden card/licensed solver fixtures.
- **담당:** Software/CAE Automation 구현; Solver/CAE Domain Expert 주 승인.

