# ADR-0014: Reference Validation Result interpretation is explicit, immutable, and non-production

## 먼저 읽기

- **무엇을 정했나요?** 실행 응답 추출, 수치 건강 상태, 시험 곡선 비교를 서로 다른 불변 기록으로
  남깁니다. 출력이 건강하고 calibration 입력과 독립적일 때만 정해진 reference profile로 비교합니다.
- **왜 중요한가요?** solver가 끝났다는 사실만으로 pass를 만들거나, 잘못된 unit·손상된 출력·범위 밖
  값을 조용히 고쳐 평가하는 일을 막기 위해서입니다.
- **언제 읽나요?** validation response parser, health check, curve interpolation, metric·threshold,
  holdout 독립성, 결과 상태나 비교 화면을 바꿀 때 읽습니다.
- **용어를 쉽게 말하면:** `numerical health`는 출력이 평가 가능한 상태인지 먼저 확인하는 검사입니다.
  `observed-grid interpolation`은 시험에서 관측한 strain 위치 안에서만 simulation 값을 구하는 방식이고,
  `not_evaluated`는 실패 판정조차 낼 조건이 되지 않았다는 뜻입니다.
- **상태 표기는?** `Accepted`는 문서에 적힌 비운영 reference 해석 profile을 채택했다는 뜻입니다.
  `passed` 결과도 production solver·material model의 자격이나 release 승인을 뜻하지 않습니다.

- Status: Accepted
- Date: 2026-07-22
- Decision owners: Product, CAE Domain, Scientific Software
- Related: `T-28`, `T-27`, `T-20`, `T-23`, `T-24`, ADR-0013

## Context

T-27 preserves an exact immutable Validation Run evidence tuple but deliberately makes no numerical
health or experimental agreement claim. A normal runner termination, a native-output file, or a
small visual curve difference must not become an implicit validation pass. The first implementation
still uses a bounded non-production reference virtual-specimen workflow, so it must communicate a
useful result without implying a qualified solver, material model, test method, or release decision.

## Decision

1. `T-28` appends three immutable typed records for exactly one terminal Validation Run:
   `ValidationResponseExtraction`, `ValidationNumericalHealthReport`, and `ValidationResult`.
   The response extraction and reports are separate derived Artifacts with SHA-256 pointers; source
   Result Manifest, native Artifact, experimental Selection, IR, Card, and prior results are never
   modified or replaced.
2. The reference native response must declare the existing OpenRadioss 2025 `kg_m_s` target and,
   when units are supplied, `engineering_strain: 1` and `engineering_stress_pa: Pa`. The extracted
   typed response is SI-only. Invalid JSON/schema, target, unit, finite value, or monotonicity is a
   recorded `not_evaluated`/`unhealthy` reason, never a default conversion or silent repair.
3. Numerical health is independent of experimental comparison. The initial health profile checks
   terminal solver state, native-result availability, expected/observed output count, finite values,
   and strictly increasing strain. Abnormal termination, unavailable output, malformed output, or a
   truncated curve cannot receive a `passed` or `failed` experimental verdict; it is
   `not_evaluated` with a reason code.
4. The sole initial comparison profile is
   `urn:cmp:validation:reference-linear-interpolation-observed-grid:1.0.0`: compare at every
   observed experimental strain point, linearly interpolate only within the extracted simulated
   curve domain, and reject extrapolation. The metric is relative RMSE normalized by the maximum
   absolute observed stress. The fixed reference threshold is `0.05`; no UI/API default can replace
   it silently.
5. Calibration evidence is checked before a verdict. A manual IR has
   `not_applicable_manual_ir`; a calibration Selection different from the validation Selection is
   `independent_selection`; exact same Selection/revision is
   `overlaps_calibration_selection`. Overlap is `not_evaluated`, even if the curve metric is small.
6. PostgreSQL owns explicit tenant-scoped tables, constraints, indexes, RLS, immutable triggers,
   and cross-record guards. Comparison points are explicit rows rather than an EAV/JSON payload and
   a deferred guard requires their count to match the frozen metric result.
7. The protected API exposes explicit evaluate/read/curve-preview operations. The web workbench
   makes extraction, numerical health, holdout independence, metrics, Artifact evidence, and the
   observed-versus-simulated curve visible. It labels every result as non-production reference
   evidence.

## Consequences

- The platform now distinguishes execution evidence, response extraction, numerical health,
  experimental agreement, and future review/release decisions.
- A `passed` value is only a result of this documented reference profile. It is not a production
  CAE solver validation, a material qualification, a model approval, or a release gate.
- A real solver runner, more complex response alignment, domain-approved threshold, multiple test
  conditions, and release acceptance remain separately versioned work. They may add new profiles;
  they must not reinterpret or overwrite this T-28 result.

## Revisit trigger

- A CAE/test domain owner approves a real target solver executable, virtual-specimen template,
  observable mapping, and acceptance policy.
- A validated model needs a different metric, controlled resampling, or a multi-specimen
  aggregation policy.
- Review/release requires a profile-specific evidence gate beyond this reference verdict.
