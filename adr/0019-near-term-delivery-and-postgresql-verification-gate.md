# ADR-0019: Near-term delivery waves start with a live PostgreSQL verification gate

## 먼저 읽기

- **무엇을 정했나요?** 작업 순서를 live PostgreSQL 검증, repeat-test 처리·통계, bounded nonlinear
  calibration, production·solver 확장의 네 단계로 나눴습니다. 뒤의 update는 reference P0-2·P1 완료와
  P2 잔여 범위를 기록합니다.
- **왜 중요한가요?** skipped database test나 mock 화면을 실제 통합 검증으로 오해하지 않고, 검증된
  기반 위에서 다음 기능을 확장하며 production 결정을 앞당기지 않기 위해서입니다.
- **언제 읽나요?** 관련 기능의 선후 관계, PostgreSQL evidence 필요 여부, reference calibration의 완료
  범위 또는 아직 남은 solver·production hardening을 판단할 때 읽습니다.
- **용어를 쉽게 말하면:** `delivery wave`는 함께 검증할 작업 순서 묶음이고, `live PostgreSQL gate`는
  disposable database에서 migration·RLS·통합 test가 실제로 통과해야 하는 조건입니다.
  `solver-independent validation`은 solver 실행 없이 model response와 holdout data를 비교합니다.
- **상태 표기는?** 이 ADR은 전달 순서 결정으로 채택됐습니다. 본문의 일부 reference wave 완료 기록이
  P2 production model·threshold·solver qualification까지 완료됐다는 뜻은 아닙니다.

- Status: Accepted for delivery sequencing
- Date: 2026-07-14
- Related requirements: FR-DAT-001~008, FR-CAL-001~007, FR-IR-001~005, FR-EXP-001~004,
  FR-VAL-005, NFR-REP-001~003, NFR-SEC-006
- Related tasks: T-19~T-26, T-33, T-35~T-38, T-D01~T-D03

## Context

The repository already has a runnable Material-to-card reference vertical, including immutable
Dataset revisions, bounded tensile processing, solver-neutral linear and tabulated-plasticity IRs,
and explicit OpenRadioss/Abaqus exporters. It also has PostgreSQL migrations and 62 currently
collected PostgreSQL-gated integration tests. On the current Windows development host those tests
have not run because Docker Desktop, a local PostgreSQL service, and
`CMP_TEST_POSTGRES_DSN` are unavailable.

The remaining work was documented across individual Tasks, but not as one near-term execution
order. In particular, the documents did not make the following order explicit:

1. prove the existing schema, RLS, migration, and full-stack demo against live PostgreSQL;
2. deepen repeat-test processing and statistics before adding another broad foundation;
3. connect a bounded nonlinear calibration reference to the existing IR/card path; and
4. defer real solver execution qualification while retaining solver-independent validation.

## Decision

The following delivery waves govern the next work. They are sequencing labels for the current
product increment; existing Task priority labels and the long-term roadmap remain traceability
metadata.

### P0-1 — Local runtime and PostgreSQL verification gate

P0-1 is complete only when all of the following evidence exists on a disposable local environment:

1. Docker Compose starts PostgreSQL 16, migration/bootstrap, non-owner API, worker, web, reference
   plugin check, and synthetic seed from `deploy/compose/docker-compose.demo.yml`.
2. Migration and seed containers exit successfully, API health returns HTTP 200, the web workbench
   opens, and the seeded Material-to-card flow is visible.
3. `CMP_TEST_POSTGRES_DSN` points to the Compose PostgreSQL owner endpoint on host port `54329`.
4. `pytest -m postgresql tests/integration` completes with zero PostgreSQL-marked skips and zero
   failures. The observed count `62` is a current collection result, not a permanent contract.
5. The CI-equivalent suite runs with the same DSN and remains green. Offline migration rendering or
   mocked browser tests do not substitute for this gate.

The DSN must never point to a production or shared database. Tests create and remove temporary
databases and roles and therefore require the disposable owner account declared by the demo
composition.

### P0-2 — Repeat-test data processing, statistics, QC, and outlier scope

After P0-1, extend the existing T-19/T-20/T-21 reference vertical rather than adding unrelated
foundation abstractions:

1. A Selection revision may pin multiple concrete normalized/processed Dataset revisions from
   distinct Test Runs while preserving each specimen curve.
2. Alignment/resampling, if required, is an explicit versioned Processing step with a declared
   domain, method, grid, extrapolation policy, and output Artifact. It is never a display-side or
   statistical hidden operation.
3. Scalar and pointwise curve statistics record specimen-level `n`, method, assumptions, valid
   domain, and uncertainty status. Raw, normalized, processed, and statistical representations stay
   distinguishable in persistence, API, and UI.
4. QC observations, outlier candidates, human assessments, and calibration-specific exclusion scope
   remain separate immutable facts. No source curve is deleted or overwritten.
5. The vertical includes typed persistence, protected API, connected web UI, unit/API/browser
   regression tests, and PostgreSQL/RLS integration coverage.

Production statistical profiles and thresholds still require domain approval. Synthetic fixtures
may exercise the framework without presenting their values as approved engineering policy.

### P1 — Bounded nonlinear calibration to IR and solver cards

P1 connects repeat-test evidence to the already implemented card outputs:

```text
immutable selections
→ versioned processing
→ reference nonlinear calibration candidates
→ human candidate selection
→ solver-neutral calibrated IR
→ explicit tabulated-plasticity projection
→ OpenRadioss/Abaqus preflight, preview, and download
```

The recommended first implementation is a **non-production reference** Voce saturation-hardening
evaluator for monotonic uniaxial tensile plastic response:

```text
sigma_y(epsilon_p) = sigma_0 + Q * (1 - exp(-b * epsilon_p))
```

It uses a SciPy `least_squares` adapter with explicit initial values, bounds, parameter scaling,
deterministic seed/multistart, stopping conditions, and durable failure status. This is an executable
reference choice, not selection of a production constitutive model or optimizer policy. Production
parameterization, bounds, weights, fixtures, tolerances, and scientific acceptance remain subject to
Constitutive Domain approval.

`TestModeAdapter`, `MaterialModelEvaluator`, `ObjectiveEngine`, and `OptimizerAdapter` remain separate
interfaces. Each candidate retains objective terms, prediction, residual, convergence reason,
evaluation/iteration counts, warnings, bound-sticking, and explicit identifiability/uncertainty
status. Unsupported diagnostics are stored as `not_assessed`/`not_provided`, never implied success.

Promotion appends a new calibrated Material Model IR revision. A separate deterministic activity may
project the parametric response onto the existing
`urn:cmp:reference:isotropic-tabulated-plasticity:1.0.0` family; its sampling grid, transformation
profile, Artifact digest, applicability, and source Candidate/Selection revisions are explicit. The
existing OpenRadioss and Abaqus exporters consume that frozen tabulated IR without solver-specific
keywords entering the calibrated IR.

P1 validation is solver-independent: material-model response checks and disjoint holdout Selection
comparison. Calibration/holdout specimen overlap fails or warns according to an explicit versioned
policy. Actual OpenRadioss/Abaqus execution, solver dry-run/data-check, HPC integration, and solver
qualification are deferred to P2 by product-owner direction; existing T-27/T-28 reference evidence
records remain intact.

### P2 — Domain expansion and production hardening

P2 contains work that does not block the preceding product vertical:

- Process/Lot/Batch genealogy, broader property/curve families, Campaign/Instrument, and additional
  importer formats;
- production model/calibrator/exporter approval and additional material families, test modes,
  optimizers, solvers, rate/temperature dependence, damage, and failure;
- real solver execution qualification, parser/data-check fixtures, HPC runners, and approved
  validation thresholds;
- T-35/T-36 observability, backup/restore/integrity drills, T-37/T-38 release quality/performance/
  security hardening, and external release/connectors.

## Consequences

- No schema-changing slice may claim PostgreSQL verification until P0-1 has zero marked skips.
- Missing Docker/PostgreSQL is an environment prerequisite, not evidence that skipped integration
  tests passed.
- Product development stays centered on Material DB → Test Data → Statistics/Processing → Material
  Model → Solver Card → Validation/Release.
- The reference Voce/SciPy slice may be implemented with synthetic data, but it cannot be labeled
  production validated or used to silently approve a card.
- Real solver verification is deferred, not deleted. Golden card tests remain mapping regressions,
  not solver qualification.

## Revisit triggers

- A Constitutive Domain owner approves a production model, objective, parameter bounds, and
  scientific reference fixtures.
- A Solver Domain owner supplies an approved OpenRadioss or licensed Abaqus execution matrix.
- The local Compose topology no longer represents the supported developer runtime.
- P0-2 evidence shows a different processing or statistics capability must precede nonlinear
  calibration.

## Delivery update: P0-2 and P1 reference scope complete

P0-2 now persists the complete bounded repeat-test path: explicit common-grid processing,
specimen-level scalar/curve Statistics and QC, immutable outlier evidence, append-only human
assessment, and a calibration-specific input Scope. P1 now persists bounded multi-curve Voce
calibration Attempts and Candidates, human Candidate selection, a calibrated solver-neutral IR,
an explicit frozen tabulated projection, and OpenRadioss/Abaqus card generation.

P1 validation uses a stable holdout Plan revision and a typed immutable Run/Result. The holdout
Dataset and Test Run must both be disjoint from every included or excluded calibration Scope member.
The public reference Voce evaluator predicts the observed holdout points directly; it does not
refit, interpolate, execute a solver, or reinterpret a card. The comparison Artifact and provenance
activity preserve every exact input revision. The fixed relative-RMSE threshold of `0.05` is a
versioned non-production reference profile only.

P2 remains the next wave. It includes actual OpenRadioss/Abaqus data-check or execution evidence,
HPC adapters, solver-result extraction and qualification, approved constitutive/threshold fixtures,
broader Catalog/Test domain support, and operational/release hardening. Product-owner direction to
exclude solver execution validation from the current wave is therefore preserved explicitly.
