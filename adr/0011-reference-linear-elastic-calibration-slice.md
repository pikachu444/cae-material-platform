# ADR-0011: Reference linear-elastic Calibration keeps numerical execution bounded and evidence-first

## 먼저 읽기

- **무엇을 정했나요?** 하나의 정확한 tensile Selection과 선형탄성 IR revision을 고정해, 제한된
  해석식으로 후보를 계산하고 성공·실패한 모든 Attempt와 진단 결과를 보존합니다.
- **왜 중요한가요?** calibration이 원본 Dataset이나 IR을 덮어쓰지 않으면서도 같은 입력과 조건으로
  계산을 재현할 수 있고, 수치 실패도 숨기지 않기 위해서입니다.
- **언제 읽나요?** Calibration Plan, optimizer, objective, Attempt·Candidate 저장, diagnostics 화면 또는
  새 model calibration을 설계할 때 읽습니다.
- **용어를 쉽게 말하면:** `Calibration Plan`은 입력·parameter 범위·계산 규칙을 고정한 버전이고,
  `Attempt`는 한 번의 계산 시도, `Candidate`는 그 시도에서 나온 후보 parameter입니다.
  `diagnostics`는 관측값·예측값·오차를 담은 검토 증거입니다.
- **상태 표기는?** `Accepted`는 이 선형탄성 reference 계산 경계를 채택했다는 뜻입니다. production
  constitutive model·optimizer·합격 기준이나 solver validation을 승인했다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-19
- Decision owners: Product, Scientific Software, Material Modeling
- Related: `T-23`, `T-22`, `T-19`, `T-25`, ADR-004, ADR-005, ADR-006, ADR-007

## Context

The product is a material-data and CAE-use platform.  Calibration is a bounded capability on the
path from immutable Test Data and Processing outputs to a Material Model IR; it is not a separate
MCalibration-style application and it cannot be allowed to overwrite Material, Dataset, or IR
revisions.

The current product has one non-production Material Model IR: small-strain isotropic linear
elasticity.  It also has one typed reference tensile Dataset path, including immutable normalized
and processed curve revisions and one-member Selections.  The next useful vertical capability is
to prove that a user can pin those inputs, execute a reproducible candidate calculation, inspect
typed diagnostics, and retain both success and failure evidence.  No approved production
constitutive equation, optimizer, acceptance criterion, or solver-based validation target has
been selected.

## Decision

1. Implement a deliberately narrow, non-production `reference_uniaxial_linear_elasticity`
   Calibration Plan.  A stable Plan identity has immutable revisions.  Each revision pins exactly
   one concrete normalized or processed tensile Selection revision and one concrete reference
   linear-elastic Material Model IR revision.  It never follows a moving Dataset or Model head.
2. The initial evaluator is the public closed-form relation `sigma = E * epsilon` for finite,
   non-negative engineering tensile points.  The only parameter is `youngs_modulus_pa`; its lower
   bound, initial value, upper bound, normalization stress scale, uniform point weight,
   all-observed-points domain, reject-on-missing-data policy, multistart count, and signed seed
   are explicit Plan fields.
3. The initial calibrator is an analytic bounded weighted least-squares reference implementation,
   not SciPy and not a production optimizer choice.  It retains deterministic multistart Attempts
   so the Plan/Run/Attempt/Candidate orchestration can be tested without claiming a generic
   optimizer, uncertainty estimate, material-point integration, or calibrated solver card.
4. A durable Calibration Run records a fixed Plan revision, Selection revision, Dataset revision,
   Model revision, R3 reference environment digest, and every Attempt.  A successful Attempt
   creates a typed Candidate and an immutable Parquet diagnostics Artifact containing observed,
   predicted, residual, and normalized-residual channels.  Failed Attempts and failed terminal
   Runs remain visible; source inputs are never changed.
5. PostgreSQL uses explicit `modeling.calibration_plan`, `_revision`, `calibration_run`,
   `calibration_attempt`, and `calibration_candidate` relations.  Composite
   organization/project/classification foreign keys, indexes, forced RLS, append-only guards, and
   trigger checks enforce same-scope input coherence and prohibit candidate mutation.  No generic
   EAV or optimizer/settings JSON store is introduced.
6. The protected API and Material State workbench expose the exact pinning, numerical conventions,
   Run state, Candidate summary, and bounded diagnostics preview.  They label the workflow
   non-production.  Candidate selection and promotion to a new IR revision are intentionally a
   separate human decision in `T-24`.

## Consequences

- The user can traverse `Material State -> Dataset Selection -> Calibration Plan -> Run ->
  Candidate diagnostics` through the same tenant-scoped web workbench that already owns Material
  and Test Data workflows.
- Calibration does not alter a Property Set, Material Model IR, Raw Asset, normalized Dataset,
  processed Dataset, Statistics Result, or Solver Card.  A subsequent IR promotion must append a
  new Model revision with explicit selection evidence.
- Exact equality is not claimed for an unspecified future optimizer or external solver.  The R3
  declaration applies only to the stated reference evaluator/calibrator/environment digest and
  its declared tolerance.
- A selected production model, TestModeAdapter, optimizer, objective weighting policy,
  uncertainty method, domain acceptance rule, and material-point/virtual-specimen validation
  remain explicit domain decisions rather than hidden defaults.

## Revisit trigger

- A Material Modeling owner approves a concrete constitutive model and its parameter semantics.
- An optimizer, transforms/scaling, multistart policy, or uncertainty/identifiability method is
  approved for a declared TestModeAdapter.
- A candidate must be promoted through review/approval to an IR and then validated against a
  target solver/template.
