# 테스트 전략과 Solver-card Golden-file 테스트

## 1. 품질 목표

이 플랫폼의 실패는 단순 UI 오류뿐 아니라 단위 변환 오류, provenance 누락, 잘못된 parameter, solver card semantic 변화처럼 눈에 잘 띄지 않는 공학 오류를 포함한다. 따라서 일반 software test와 scientific validation을 분리하되 release gate에서 결합한다.

## 2. 테스트 분류

| ID prefix | 범주 | 실행 주기 |
| --- | --- | --- |
| `UT-*` | pure unit/domain/numeric function | 모든 PR |
| `PT-*` | property-based/metamorphic | 모든 PR 또는 nightly |
| `CT-*` | OpenAPI/event/job/plugin/schema contract | 모든 PR |
| `IT-*` | PostgreSQL/object store/worker/runner integration | 모든 PR |
| `ST-*` | security/RLS/sandbox/parser fuzz | PR + nightly |
| `NT-*` | numeric/scientific reference | 모든 scientific 변경 |
| `GT-*` | solver-card golden/semantic | exporter 변경마다 |
| `SV-*` | licensed solver verification | nightly/release candidate |
| `MT-*` | migration/upgrade/restore | release candidate |
| `PF-*` | performance/load/soak/fault injection | nightly/release candidate |
| `E2E-*` | raw→release vertical scenario | release candidate |

## 3. 일반 software test

### 3.1 Domain unit test

- aggregate/revision immutability
- lifecycle transition
- optimistic concurrency
- organization/project classification propagation
- selection membership hash
- job state machine/retry policy
- mapping report policy
- release completeness policy

DB/framework 없이 실행 가능한 domain test를 우선한다.

### 3.2 Contract test

- OpenAPI request/response와 generated client
- JSON Schema positive/negative fixtures
- CloudEvents envelope와 event data schema
- Job Spec/Result Manifest
- plugin manifest/version range
- IR envelope/model payload
- backward/forward compatibility와 breaking-change detection

Consumer-driven contract가 필요한 외부 PLM/HPC adapter는 target 결정 후 추가한다.

### 3.3 Integration test

Ephemeral PostgreSQL과 S3-compatible test storage를 사용한다.

- transaction + RLS
- multipart upload/staging/finalization
- worker claim/lease/crash/retry
- outbox publish/dedup
- plugin runner artifact I/O/sandbox
- provenance completeness/recursive query
- backup/restore fixture

Mock repository만으로 통과하는 test를 persistence integration의 대체로 쓰지 않는다.

## 4. Scientific numeric test

### 4.1 Reference test

각 numeric plugin/function은 다음을 갖는다.

- reference dataset의 출처·license
- expected values/curves
- absolute/relative/ULP tolerance 선택 이유
- input domain과 invalid cases
- 독립 계산 또는 domain expert 승인
- algorithm/plugin/dependency version

상용 제품 출력을 무단 복제한 fixture를 사용하지 않는다. 공개 표준, analytic solution, synthetic data 또는 사용 권한이 있는 내부 reference를 사용한다.

### 4.2 Property/metamorphic test

구체 모델에 맞는 property를 domain expert가 선택한다.

- unit conversion round-trip 또는 normalized equivalence
- 동일 point 중복/재정렬에 대한 명시된 behavior
- positive scale change와 response relation
- parameter bound enforcement
- symmetry/invariance
- monotonicity/energy/stability 조건
- 동일 seed reproducibility
- resampling density가 specimen weight를 바꾸지 않음

모든 material model에 monotonicity 같은 property를 일괄 적용하지 않는다.

### 4.3 Numeric tolerance

- 금액처럼 exact한 metadata/digest/schema는 exact equality
- deterministic serialized artifact는 byte equality가 목표
- floating result는 method별 abs/rel tolerance
- solver result는 metric/curve tolerance와 solver/platform matrix
- tolerance 완화는 code review와 domain approval 필요
- NaN/Inf는 explicit expected case 외에는 실패

## 5. 통계 test fixture

- hand-calculated mean/SD/median/MAD/IQR
- single observation, all equal, missing/censored, near-zero mean
- lot/batch strata와 unbalanced group
- curves with unequal grids/domains/truncation
- intersection/union-with-mask behavior
- bootstrap fixed-seed result
- outlier candidate와 adjudication scope
- converged Calibration Candidate versus explicit human Selection reason/current-revision promotion
- reference Validation Template/Plan exact revision pinning; mock/manual Result Manifest parity;
  normal/abnormal/not-available termination; shell-like external-job rejection; target/native-result
  mismatch; immutable deck/log/manifest evidence without a validation verdict
- T-28 reference interpretation: SI unit/target validation, finite/monotonic/truncated output,
  explicit observed-grid interpolation with no extrapolation, fixed relative-RMSE threshold,
  abnormal-output `not_evaluated`, and calibration Selection/holdout overlap rejection
- T-29 review governance: immutable request/decision rows, draft→review→approved or
  changes_requested transitions, manifest digest pinning, stale revision rejection, and
  author/reviewer separation of duties
- curve point 수를 늘려도 replicate `n` 불변
- display downsample과 full calculation 분리

## 6. Provenance·revision test

### 필수 invariants

1. output entity는 primary generation activity 하나를 가진다.
2. activity input은 구체 immutable entity revision이다.
3. derivation/revision DAG에 금지 cycle이 없다.
4. release에서 raw까지 complete path가 있다.
5. raw/released artifact digest는 변하지 않는다.
6. failure/cancel run도 usage/agent/log lineage를 가진다.
7. outlier decision은 input artifact를 변경하지 않는다.
8. migration은 old entity를 보존하고 explicit activity를 만든다.
9. a promoted IR must pin the current Candidate Selection revision, exact Candidate/diagnostics
   digests, and evaluated source IR revision; superseded selections and stale IR heads fail.
10. a T-28 Validation Result must pin the terminal Result Manifest and exact experimental Selection
    revision, create separate response/health/result Artifacts, and preserve every earlier Run,
    Manifest, Dataset, IR, Card, and result fact. The result cannot pass after abnormal/unhealthy
    evidence or fit/holdout overlap.

Property-based graph fixture와 intentionally corrupt DB fixture를 모두 둔다.

## 7. Solver-card golden-file 전략

### 7.1 Golden의 목적

Exporter code, unit conversion, formatting, solver version support가 바뀔 때 승인된 card의 text와 의미가 의도치 않게 바뀌는 것을 탐지한다.

Golden은 solver 정확성을 단독으로 증명하지 않는다. syntax/semantic regression과 licensed solver verification을 연결하는 기준이다.

### 7.2 Fixture matrix

각 golden case는 다음 tuple로 식별한다.

```text
(ir_fixture_id,
 ir_schema_version,
 exporter_plugin_digest,
 target_solver,
 target_solver_version,
 card_type,
 unit_system,
 export_options_profile)
```

Production model/solver가 `TBD`인 동안 synthetic exporter fixture만 둔다.

### 7.3 비교 단계

1. IR fixture schema/semantic validation
2. exporter preflight mapping report 비교
3. card 생성
4. raw byte 또는 canonical text 비교
5. parser/normalizer가 있으면 semantic representation 비교
6. syntax checker/dry-run hook
7. licensed solver smoke/virtual specimen reference

## Reference elastoplastic multi-solver regression matrix

The bounded tensile-to-card slice is verified at four distinct boundaries:

1. Domain tests verify engineering-to-true stress/log-strain/true-plastic-strain equations,
   first-maximum necking cutoff, monotone hardening, explicit yield anchor, rejection of softening,
   and mandatory post-necking approximation acknowledgement.
2. Artifact/application tests verify pinned Property Set and Dataset revisions, verified SI
   Parquet input, immutable hardening Parquet output, source/excluded point counts, scope and
   classification equality, and no source revision mutation.
3. Mapping/API/browser tests verify explicit OpenRadioss/Abaqus target tuples, all mapping-status
   values including visible `approximated`, report-digest acknowledgement, card preview/download,
   and the connected Material State workbench flow.
4. Golden regressions compare byte-exact OpenRadioss `/MAT/LAW36` + `/FUNCT` `.rad` and Abaqus
   `*DENSITY` + `*ELASTIC` + isotropic `*PLASTIC` `.inp` output. A golden match establishes
   deterministic mapping regression only; it is not solver qualification.

PostgreSQL-marked coverage additionally checks the organization/project/classification composite
source FKs, explicit transformation-count constraint, hardening Artifact guard, family-stability
guard, and forced RLS. It requires the disposable PostgreSQL DSN described below. Licensed or
installed solver execution is not part of normal CI; an eventual production gate must add
OpenRadioss Starter/dry-run and licensed Abaqus data-check fixtures under an approved version
matrix.

## T-31 PostgreSQL integration prerequisites

The PostgreSQL-marked suites are intentionally conditional. They are skipped when
`CMP_TEST_POSTGRES_DSN` is not set; a skipped result is not a passing database verification.
The DSN must point to a reachable disposable PostgreSQL 16+ server and be accepted by
SQLAlchemy/psycopg. Never use a production, shared development, or otherwise valuable database.

### P0-1 Windows/Compose verification runbook

The repository Compose file is the canonical local P0-1 environment. Docker Desktop must already
be installed, started, and configured with the WSL 2 backend. From the repository root in
PowerShell:

```powershell
docker version
docker compose version
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml --profile test up -d postgres-test
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Expected state:

- `postgres`, `postgres-test`, `api`, `worker`, and `web` are running; both PostgreSQL services and API become healthy;
- `migrate`, `reference-plugins`, and `seed` exit with code 0;
- the health response reports success and `http://127.0.0.1:5173` opens;
- the browser's local demo identity can read the seeded Material/Dataset/IR/cards.

The SCRAM-authenticated demo database on `127.0.0.1:54329` is for the running product. Do not weaken
it for the test harness. The `test` profile starts a separate localhost-only PostgreSQL 16 owner on
`127.0.0.1:54330`, backed by tmpfs and configured for passwordless temporary application roles.
Use this disposable owner DSN for the marked suites:

```powershell
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest -m postgresql tests/integration -ra
```

The P0-1 pass condition is **zero failures and zero PostgreSQL-marked skips**. The previously
observed `62 skipped` is a snapshot of the current collected suite, not a stable expected count;
new migrations/modules may add tests. With the same environment variable still set, execute the
CI-equivalent suite:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/ci.sh
```

On a shell with GNU Make, the equivalent commands are:

```bash
CMP_TEST_POSTGRES_DSN=postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres make test-postgresql
CMP_TEST_POSTGRES_DSN=postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres make ci
```

The test owner needs permission to create an isolated temporary database and application role.
Tests migrate each temporary database to `head`, exercise non-owner RLS paths, and remove the
temporary database. `cmp_app` is intentionally unsuitable because application roles must not create
databases, roles, schemas, RLS helper functions, triggers, or extensions.

Collect diagnostic evidence before teardown when a step fails:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
docker compose -f deploy/compose/docker-compose.demo.yml logs --no-color postgres migrate api seed
```

After verification, remove the development containers and synthetic volumes:

```powershell
Remove-Item Env:CMP_TEST_POSTGRES_DSN -ErrorAction SilentlyContinue
docker compose -f deploy/compose/docker-compose.demo.yml down -v
```

`down -v` permanently removes only the explicitly disposable local demo volume when this canonical
composition is used. Do not copy this teardown command to another project or production context.

Docker is not required by the Python test implementation itself; another disposable PostgreSQL 16+
server is acceptable when the same owner privileges and isolation rules are satisfied. The live
P0-1 gate completed on 2026-07-27: the marker suite recorded 62 passed with zero skips or failures,
and the CI-equivalent run recorded 452 Python tests plus 21 Vitest tests. The count may grow; skip
zero and failure zero remain the contract. Evidence is recorded in `IMPLEMENTATION_STATUS.md`.

T-31 additionally verifies append-only release lifecycle events, terminal projections, explicit
usage facts, successor/predecessor impact, and tenant-scoped RLS. A withdrawn or superseded
release is never deleted or silently replaced, and package download/consume is rejected after the
terminal transition.

The T-33/T-34 browser regression suite also exercises the protected evidence boundary: curve
workbench previews keep representation/unit and deterministic sampling metadata visible, while the
Lineage and Audit Inspector calls entity, bounded lineage, completeness, event, and integrity APIs
without reconstructing a graph in the browser. Graph truncation and invalid audit integrity remain
visible warning states. These browser tests use mocked HTTP responses; live tenant/RLS behavior
still requires the PostgreSQL prerequisite above.

### 7.4 Volatile field 처리

timestamp, absolute path, random ID처럼 의미 없는 field는 exporter가 deterministic mode에서 제거하는 것이 우선이다. 제거할 수 없으면 `golden-normalization-policy`에 path와 이유를 allowlist한다.

숫자, keyword, parameter, units, table ordering, sign, interpolation option을 volatile 처리해서는 안 된다.

### 7.5 Golden update workflow

```mermaid
flowchart TD
    Diff["Golden diff 발생"] --> Reason["변경 이유·ADR/Task 연결"]
    Reason --> Software["Exporter maintainer 검토"]
    Software --> Domain["Solver domain 검토"]
    Domain --> Solver["Syntax/solver verification"]
    Solver --> Commit["새 golden+manifest commit"]
```

자동 `--update-golden` 결과를 검토 없이 commit하지 않는다.

### 7.6 Golden manifest

```json
{
  "case_id": "GT-TBD-001",
  "ir_fixture_sha256": "hex",
  "exporter_package_digest": "sha256:...",
  "target": {"solver": "TBD", "version": "TBD", "card_type": "TBD"},
  "unit_system": "TBD",
  "mapping_report_sha256": "hex",
  "card_sha256": "hex",
  "semantic_sha256": "hex",
  "approved_by": ["software-review-id", "domain-review-id"],
  "approval_date": "RFC3339",
  "reference_solver_run_id": null
}
```

## 8. Licensed solver test tier

Commercial solver license 때문에 모든 PR에서 solver를 실행하지 못할 수 있다.

| Tier | 환경 | 내용 |
| --- | --- | --- |
| Tier 0 | PR public/internal CI | exporter unit, golden text, parser, mock runner |
| Tier 1 | nightly licensed runner | card syntax/small virtual specimen |
| Tier 2 | release candidate | full selected validation template/reference |
| Tier 3 | periodic certification | supported solver/version matrix |

Tier 1 이상 결과는 solver version, platform, executable digest/installation ID, license context, runner, deck/result digest를 기록한다.

## 9. Plugin TCK

- manifest/schema/capability
- declared determinism
- corrupt/missing artifact
- cancel/deadline/resource quota
- no-network and filesystem escape
- structured diagnostics
- output role/media/schema/size
- provenance fields
- backward compatibility
- extension-specific scientific reference

TCK 통과는 scientific validity를 자동 보증하지 않는다. domain acceptance suite가 추가로 필요하다.

## 10. Security test

- role-action matrix와 SoD
- cross-organization/project/classification RLS
- list/count/facet/autocomplete leak
- object token scope/expiry/replay
- upload path/size/media/digest
- parser fuzz, decompression bomb, malformed solver output
- plugin network/path/symlink/process escape
- solver command injection
- secret/log redaction
- audit mutation/reorder/delete
- supply-chain digest/signature substitution
- backup privileged path와 restore access

## 11. Migration·upgrade test

- clean install latest schema
- supported previous release→latest migration
- rollback이 필요한 경우 명시; data migration은 forward-fix 우선
- revision/content hash 보존
- old IR/plugin/event compatibility
- migration provenance
- large-table lock/time budget
- backup restore 후 migration rehearsal

Migration script가 released/raw record를 재작성하면 명시적 ADR, before/after digest report, domain approval을 요구한다.

## 12. Performance·resilience test

- 2 GiB streaming upload 또는 합의한 최대값
- 10 million-point dataset import/view
- 10,000 material/release search
- 10,000-edge lineage traversal
- concurrent worker claim과 organization quota
- long solver wait/heartbeat
- object store transient failure
- DB failover/connection loss
- plugin memory/time exhaustion
- event publisher crash/duplicate
- backup/restore RPO/RTO drill

수치는 실제 sample 측정 후 NFR을 갱신한다.

## 13. E2E vertical scenario

Release candidate마다 다음을 자동 또는 반자동 실행한다.

```text
synthetic/approved raw tensile files
→ material/state/lot/batch/specimen/test context
→ upload/digest/import mapping
→ normalized dataset/original units
→ QC/statistics/outlier assessment
→ processing selection
→ calibration candidates
→ IR revision
→ exporter preflight/card golden
→ mock/licensed virtual specimen
→ review/approval/release
→ release-to-raw lineage and package digest verification
```

구체 production model/card는 결정 전까지 synthetic reference로 대체하고 release channel은 `non-production`으로 표시한다.

## 14. Test data governance

- 실제 기업 시험 데이터는 source control에 commit하지 않는다.
- fixture는 synthetic, anonymized 또는 명시적 사용 권한이 있어야 한다.
- fixture manifest에 source/license/classification/owner/retention을 기록한다.
- raw fixture도 immutable digest로 관리한다.
- domain golden은 변경 이유와 승인 history를 보존한다.
- production incident data를 test에 넣을 때 secret/IP/개인정보를 검토한다.

## 15. Release gate

### 모든 release

- lint/type/unit/contract/integration
- migration dry run
- RLS/security critical suite
- provenance invariants
- synthetic E2E

### Scientific/plugin/exporter 변경

- numeric reference/property tests
- plugin TCK
- domain reviewer approval
- golden diff review
- 해당 solver licensed tier 결과

### Production release

- critical/high unresolved security finding 0 또는 공식 risk acceptance
- backup/restore drill 유효
- NFR benchmark report
- release package integrity verification

## 16. 실패 처리

- flaky test는 자동 재실행만으로 숨기지 않고 owner/issue/expiry가 있는 quarantine에 둔다.
- numeric tolerance 초과를 단순 tolerance 확대만으로 해결하지 않는다.
- golden diff를 snapshot update로 덮지 않는다.
- solver version/environment 차이를 결과 metadata에서 숨기지 않는다.
- failing scientific test가 있으면 관련 plugin/release activation을 차단한다.

### T-30 Release completeness invariants

Release tests must verify a stable candidate-manifest digest, exact Material Model/Solver Card/
Validation/Review/provenance identity matching, passed-validation and approved-review requirements,
unsupported or approximated mapping rejection, organization/project/classification isolation, and
immutable Manifest/Artifact rows. The authenticated download must return the package digest as an
ETag and the package bytes must verify against the stored SHA-256.

### P0-2 multi-replicate Selection gate

The first P0-2 increment adds these mandatory checks:

- unit: 2..50 ordered members, distinct Dataset/Test Run revisions, one Material State and tenant
  scope, append-only revision history, and mixed-state rejection;
- migration/PostgreSQL: explicit member table and FKs, Dataset/Test Run uniqueness,
  normalized/processed representation guard, exact deferred member count, forced RLS, immutable
  rows, and downgrade refusal while multi-member evidence exists;
- contract/API: create, list-by-Material-State, get-current, and append-revision operations match
  source and runtime OpenAPI contracts;
- browser: member controls use concrete Dataset revision IDs, prior revisions are not edited, and
  pinned curves share one SI plot scale with member identity visible;
- demo regression: three synthetic calibration Test Runs produce three independent Dataset
  revisions and one replicate Selection, while a fourth Test Run/Dataset remains disjoint for
  holdout validation, all through protected HTTP APIs.

### P1 Voce-to-card and holdout gate

- unit: public Voce response evaluation, bounded deterministic calibration, parameter diagnostics,
  fixed tabulated projection, exact-response holdout pass, perturbed-response fail, and no refit;
- PostgreSQL/migration: explicit Plan/Attempt/Candidate/Selection/IR and holdout Plan/Run/Result/
  point tables, exact foreign keys, immutable guards, forced RLS, no JSONB/EAV payload, and online
  upgrade/downgrade/re-upgrade through migration 037;
- API/contract: calibration, Candidate acceptance, IR promotion, two-solver preflight/card preview/
  download, holdout Plan execution, complete lineage identifiers, Artifact digests, and explicit
  `solver_execution=not_used`;
- browser: experimental/fitted/residual Candidate comparison, human acceptance, calibrated card
  controls, independent Dataset selector, observed/predicted holdout curve, RMSE and reference
  verdict;
- regression: reject calibration/holdout Dataset or Test Run overlap, stale revisions, cross-scope
  inputs, malformed Artifacts, unsupported IR versions, and silent solver approximation.

The gate proves only the non-production reference material-model workflow. Golden cards verify
deterministic mapping, not solver acceptance. Real OpenRadioss/Abaqus execution and qualification
remain P2 and must receive separate fixtures, licenses, version matrices, parsers, and owner-approved
thresholds before their tests can be enabled.

The second P0-2 increment extends this gate with:

- unit: strictly increasing input strain, exact common intersection, deterministic declared grid,
  piecewise-linear expected values, and hard rejection of extrapolation/non-overlap;
- migration/PostgreSQL: typed grid/policy columns, crop/alignment shape constraints, batch/member
  uniqueness, Selection-member/Recipe-kind guards, immutable terminal transitions, and provenance
  activity/plan finalization limited to the creating request;
- contract/API: explicit policy request/response and grouped member outputs with concrete processed
  Dataset revision links;
- browser: editable grid start/end/count, visible fixed policies, committed batch summary, and a
  separate processed-revision overlay;
- regression: output point count may differ from input without abusing crop `removed_point_count`,
  while each source normalized revision and Artifact digest remain unchanged.

Pointwise statistics may now consume only these explicit aligned processed revisions; it still may
not align or interpolate inputs internally.

The third P0-2 increment adds a domain-kernel gate before persistence is connected:

- specimen count, rather than point count, defines `n` and the sample standard deviation;
- scalar and every pointwise row retain mean, sample SD, median, MAD, IQR, min/max, CV, and the
  declared two-sided 95% Student-t mean interval;
- an unequal exact processed grid is rejected and Statistics performs no hidden alignment;
- the typed Parquet round trip preserves all declared statistics and rejects a different schema;
- the immutable plan canonical form pins one Selection revision and declares processed-only input,
  exact-grid policy, quantile method, and confidence-interval method.

The fourth P0-2 increment makes the persisted Statistics/QC gate mandatory:

- migration/PostgreSQL: explicit Plan/Revision, Run/ordered Member, Result/Revision, and QC tables;
  exact-count and pin-consistency guards; append-only revisions; terminal Run transitions; indexes;
  forced RLS; and no JSONB/EAV fallback;
- migration lifecycle: fresh upgrade to `20260730_033_p02`, downgrade to 032, and re-upgrade against
  disposable PostgreSQL 16 without losing prior P0-2 evidence;
- service/API: Plan sample count equals the pinned Selection member count, only processed revisions
  are accepted, exact members and QC are returned, and bounded curve preview verifies Artifact
  digest/schema/point count;
- provenance: the Result generation activity uses the exact Selection and Plan revisions and
  derives the immutable Result and curve Artifact under the same tenant/classification scope;
- browser: alignment outputs require a separate explicit Selection before Plan creation; Run QC,
  specimen scalar statistics, observed range, mean, and Student-t 95% CI band are rendered from the
  protected API; and no display data becomes a calculation input;
- regression: source normalized/processed Dataset revisions and Artifacts remain unchanged, the
  legacy two-selection pair flow remains valid, and authorization includes only the explicit
  Artifact read needed for curve preview.

The fifth P0-2 gate adds multi-member outlier evidence and append-only human assessment. Tests prove
that candidates are not deletions, assessments never mutate candidates or source data, no automatic
exclusion occurs, and calibration exclusion is fixed to a concrete scope revision. The gate now
includes modified-z and MAD-zero unit tests, protected API and React flow regressions, the migration
suite, a `033 → 034 → 033 → 034` PostgreSQL exercise, and a live two-candidate flow that records
one retained and one calibration-only excluded Assessment before producing a 2-included/
1-excluded immutable Scope.

### P2 Material-class and viscoelastic gates

- Catalog: legacy v1 revisions remain hash-stable and read as `unclassified`; v2 revisions require
  a checked class, support tenant-scoped filtering, and cannot be updated in place.
- Steel regression: existing tabulated/Voce IR, two-solver preflight, preview, download and golden
  files remain byte/semantically stable after classification routing.
- Linear viscoelasticity: Prony ratio sums, positive ordered relaxation times, finite values,
  deterministic response evaluation, typed persistence/RLS, Abaqus golden card, and explicit
  missing-bulk acknowledgement are mandatory.
- Data/calibration: raw and normalized shear-relaxation curves remain distinct; processing is an
  explicit revisioned activity; bounded deterministic fitting stores attempts, candidates,
  residuals, selection reason and promoted IR lineage.
- Hyper-viscoelasticity: canonical Ogden/Prony conventions and solver transforms require analytical
  equivalence tests; non-representable bulk relaxation must be `unsupported` for LAW62.

#### ADR-0023 bounded Ogden–Prony gate

The reference elastomer slice must pass all of the following without external solver execution:

- domain invariants for positive finite μ/α, one-to-five positive ordered relaxation times,
  normalized shear-ratio sum below one, exact source revision pins, and elastomer-only routing;
- analytical N=1 incompressible uniaxial reference response checks;
- byte-exact Abaqus and OpenRadioss golden fixtures plus card SHA-256 verification;
- preflight digest acknowledgement and explicit `exact`/`transformed`/`approximated`/
  `not_applicable` statuses, including mandatory `approximated` LAW62 volumetric response;
- PostgreSQL migration, tenant/classification FK, RLS, immutable revision, deferred term-count/order,
  and source-IR/card-term equality checks;
- protected API create/list/read/preflight/create-card/preview/download and Material State browser
  workflow for both targets.

Solver execution and solver-result equivalence are intentionally excluded by product decision.
They require a separate version/license/element/formulation matrix and must not be inferred from
keyword rendering or golden text equality.
- End to end: Material class -> State -> property/test data -> exact IR revision -> mapping report
  -> preview/download must pass in the browser against PostgreSQL. Golden/semantic tests do not
  claim real solver acceptance.

The first linear-viscoelastic gate is implemented by migration 040 and its offline migration test,
domain limit/invariant tests, a PostgreSQL repository integration that restores ordered terms and
exact source revision pins, protected OpenAPI/JSON Schema contract checks, and a React regression
that creates an IR and renders the backend response curve. The Docker demo was also exercised with
a synthetic polymer Material: two terms produced 41 response points and the expected instantaneous
to long-time shear-modulus decrease. The Abaqus golden/export gate is implemented by migration
041, typed term persistence, official keyword mapping evidence and byte-golden regression. The
shear-relaxation ingress gate is implemented by migration 042, CSV mapping/unit/parser tests,
raw-versus-normalized revision constraints, PostgreSQL migration execution, protected contract
checks and the connected React workflow. Migration 043 implements the Processing half with
observed-point crop unit tests, protected API tests, typed/non-EAV offline migration assertions,
live PostgreSQL migration and Run execution, source/output revision checks, two-input provenance
verification, React regression and production frontend build. The bounded calibration half remains
implemented by migration 044 with deterministic synthetic-recovery unit tests, diagnostic Parquet
round-trip, protected API tests, typed/non-EAV offline migration assertions, PostgreSQL migration,
live four-start Run execution, persisted Candidate readback, and connected React/build regression.
The gate preserves exact Dataset/model revision pins, rejects fewer than five processed points,
shows bound/rank/uncertainty status, and proves that execution does not create a selection or IR
revision. Migration 045 implements the separate human selection/promotion gate. Tests require an
explicit selection reason, exact succeeded-Run/converged-Candidate membership and digests,
compare-and-swap against the still-current baseline, stable Material Model identity with revision
increment, schema 1.1 promotion evidence, typed non-EAV persistence, forced RLS and DB trigger
validation. A browser regression proves no Candidate is selected automatically. The Abaqus
regression uses promoted evidence-bearing IR content, pins the exact promoted revision, previews
`*VISCOELASTIC`, downloads the same bytes and verifies the card digest.
The 2026-07-16 CI-equivalent evidence for migration 043 is 527 Python tests and 27 Vitest tests with
zero failures, plus a successful TypeScript/Vite production build and live Docker Run execution.

The migration 044 gate on 2026-07-16 recorded `make ci` as 467 passed plus 64 expected
PostgreSQL-without-DSN skips, 27 Vitest passed, and a successful production build. Re-running the
PostgreSQL marker suite against Compose PostgreSQL 16 with the isolated test DSN produced 64
passed, zero skipped and zero failed. Live demo persistence also produced one six-point processed
Dataset, four Candidates, and six diagnostic rows per Candidate.

The migration 045 gate on 2026-07-16 recorded 471 Python tests and 27 Vitest tests with zero
failures, a successful production frontend build, and 64/64 PostgreSQL marker tests against the
isolated Compose PostgreSQL 16 service. Live verification promoted one reviewed Candidate to
revision 2 of the same model, generated an Abaqus card from that exact revision, and matched the
downloaded bytes to the persisted card SHA-256.
# T-07 Catalog genealogy verification

The bounded Process/Lot/State Genealogy vertical is verified at four layers:

- domain tests reject an empty genealogy and identity/revision half-pairs;
- API tests prove that selected Process and Lot revision IDs, never `latest`, cross the HTTP
  contract;
- PostgreSQL tests create and revise the full Material -> State -> Process/Lot -> Genealogy graph,
  verify forced RLS, tenant isolation, composite scoped foreign keys, and immutable-row triggers;
- frontend tests prove that visible governed selections submit the exact revision IDs returned by
  the API.

Future full T-07 fixtures must add multi-lot acceptance, split/merge, Process Run input/output,
cycle rejection, and material-balance cases without weakening these revision-pinning regressions.

## Live user E2E evidence gate (2026-07-16)

The Compose demo must be capable of completing one clean, protected, PostgreSQL-backed path from
experimental-data registration to a downloadable material card without replacing any source or
published revision. The recorded run used a newly created polymer Material and proved:

1. typed Material, State and basic Property Set revisions were committed;
2. a Specimen and shear-relaxation Test Run pinned the exact State and Method revisions;
3. the CSV upload completed as an immutable Raw Asset/Artifact, then produced separate normalized
   and processed Dataset identities;
4. the explicit crop Run reduced six normalized observations to five processed observations;
5. a deterministic five-start bounded Prony Run persisted five converged Candidates and five-point
   observed/predicted/residual diagnostics per Candidate;
6. a human reason and exact Candidate digest produced an immutable Candidate Selection, and
   promotion appended Material Model revision 2 based on revision 1 under the same stable identity;
7. Abaqus mapping preflight was exportable and its SHA-256 was acknowledged before the card row was
   committed;
8. preview contained `*DENSITY`, `*ELASTIC`, and `*VISCOELASTIC`; HTTP download returned 418 bytes
   whose SHA-256 exactly matched the stored card digest.

The browser evidence additionally renders the processed curve, sorted Candidates, residual view,
promoted IR/card preview, OpenRadioss LAW62 approximation notice, and exact Process/Lot genealogy.
The complete IDs, digests, commands, expected negative check, and screenshots are in
`docs/15-demo/user-e2e-evidence-2026-07-16.md`.
