# ADR-0022: Bounded reference Prony calibration does not select or promote automatically

## 먼저 읽기

- **무엇을 정했나요?** exact processed shear-relaxation Dataset과 baseline IR을 사용해 비운영 2항
  generalized-Maxwell 후보를 반복 계산하고, 모든 Candidate와 진단을 남기되 자동 선택·승격하지 않습니다.
- **왜 중요한가요?** 가장 작은 objective를 곧바로 공학적으로 승인된 model로 취급하거나 기존 manual
  IR을 덮어쓰지 않고, bounds·식별성·불확실성 부족까지 검토할 수 있게 하기 위해서입니다.
- **언제 읽나요?** Prony Calibration Plan, optimizer·multistart, Candidate 정렬·선택, diagnostics 또는
  linear-viscoelastic IR promotion을 바꿀 때 읽습니다.
- **용어를 쉽게 말하면:** `Prony term`은 relaxation 크기와 시간을 나타내는 한 항이고, `multistart`는
  여러 초기값에서 계산을 반복하는 방식입니다. `identifiability`는 data가 parameter를 구분하기에
  충분한지를 뜻하며, 낮은 objective만으로 사람의 선택을 대신하지 않습니다.
- **상태 표기는?** `Accepted`는 이 2항 reference calibration 경계를 채택했다는 뜻입니다. production
  term 수·bounds·optimizer, LAW62 또는 solver execution이 승인됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0007, ADR-0020, ADR-0021; T-23, T-24; P2 item 3

## Context

The platform now preserves normalized shear-relaxation evidence and explicit processed Dataset
revisions. A usable calibration increment must fit data reproducibly without turning one numerical
minimum into an unreviewed engineering decision or overwriting the manual baseline IR.

## Decision

The first calibration is a non-production, solver-neutral, two-term generalized-Maxwell reference
model. A revisioned Plan pins one exact processed Dataset revision and one exact baseline
linear-viscoelastic IR revision. The baseline supplies the instantaneous shear modulus and must
declare bulk relaxation `not_characterized`; this shear-only workflow never invents bulk terms.

The fitted parameters are total shear ratio, fast-term fraction, fast relaxation time and slow
relaxation time. Ratio parameters are bounded in physical coordinates. Time constants use a log
transform and disjoint fast/slow bounds. SciPy `least_squares(method="trf")` and NumPy PCG64 provide
the fixed reference optimizer and deterministic multistart contract. Uniform normalized modulus
residuals are the only objective in this increment.

Plan revisions, Runs, Attempts and Candidates use dedicated PostgreSQL tables and composite tenant
foreign keys. Observed, predicted and residual points are immutable Parquet Artifacts. Each
Candidate records objective, RMSE, mean residual, convergence reason, evaluation counts, bound
warning, Jacobian-rank identifiability status and an explicit `not_assessed_reference` uncertainty
status. Database guards require a processed Dataset, the exact baseline model family, matching
Material State revision, and missing bulk characterization.

Execution returns all Candidates and does not create a Candidate Selection or Material Model
revision. The UI may sort Candidates by objective for inspection but may not label the first row as
approved or promote it automatically.

## Consequences

Repeated Runs with the same Plan and environment are reproducible and leave auditable numerical
evidence. Bounds, rank deficiency and missing uncertainty remain visible. A subsequent explicit
human action must record the chosen Candidate and reason before appending a new immutable
linear-Prony IR revision. Abaqus export then pins that promoted revision through the existing
preflight/card boundary.

This ADR does not define production term-count selection, time-temperature superposition,
frequency-domain fitting, nonlinear hyperelasticity, solver execution qualification, or
OpenRadioss LAW62. Ogden-Prony/LAW62 is a separate model family and vertical feature.

## Implementation note

Migration 045 implements the subsequent human decision described above. Selection is a dedicated
stable identity with an immutable typed revision. Promotion appends schema 1.1 to the baseline
Material Model identity and pins Selection, Run, Candidate and diagnostics digests. Database
triggers independently validate the exact organization/project/classification lineage. The
existing Abaqus exporter consumes the promoted revision without changing the solver-neutral model
family; the card remains explicitly reference/non-production.
