# ADR-0021: Reference shear-relaxation processing creates a separate Dataset identity

## 먼저 읽기

- **무엇을 정했나요?** normalized shear-relaxation Dataset에서 관측된 시간 범위를 양 끝 포함해 자르고,
  exact Recipe와 Run에 연결된 별도 processed Dataset과 Parquet Artifact를 만듭니다.
- **왜 중요한가요?** calibration 입력 구간을 재현하면서 raw·normalized data를 바꾸거나 interpolation,
  resampling, smoothing을 숨기는 일을 막기 위해서입니다.
- **언제 읽나요?** shear-relaxation crop, Processing Recipe·Run, processed Dataset identity 또는 Prony
  calibration 입력 조건을 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `inclusive crop`은 선택한 시작·끝 관측점을 모두 포함해 범위를 자르는
  방식입니다. `separate Dataset identity`는 처리 결과가 원본의 새 버전이 아니라 독립된 파생
  Dataset이라는 뜻이고, provenance가 사용한 source와 Recipe를 연결합니다.
- **상태 표기는?** `Accepted`는 이 observed-point crop 경계를 채택했다는 뜻입니다. production Prony
  항 수·bounds·validation threshold나 solver qualification을 정했다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-16
- Related: ADR-0007, ADR-0019, ADR-0020; T-19; P2 item 3

## Context

The reference shear-relaxation ingress preserves immutable raw CSV revision 1 and normalized SI
Parquet revision 2. Prony calibration needs an explicit, reproducible input window, but changing
either imported revision or hiding crop/interpolation behavior would violate revision and provenance
invariants.

## Decision

The first shear-relaxation Processing step is an inclusive time crop over observed normalized
points. It never interpolates, resamples, smooths, extrapolates, or edits source bytes.

The platform stores a stable Processing Recipe identity and immutable typed revision, a committed
Run pinned to exact Recipe and normalized Dataset revisions, one immutable derived Parquet Artifact,
and a separate stable processed Dataset identity at revision 1. Dedicated PostgreSQL columns,
tables, checks, composite tenant foreign keys, indexes, forced RLS, immutable revision triggers, and
Run transition guards enforce the contract. No generic EAV or opaque parameter payload is used.
Provenance records both the normalized Dataset revision and Recipe revision as used entities and
binds the generation activity to the concrete Run.

## Consequences

Raw and normalized revision history remains unchanged. Different Processing Runs can produce
independent derived Dataset identities without moving a shared source head. Bounded Prony
calibration can require a concrete `processed` revision and exact processing evidence.

This ADR does not select production Prony term counts, bounds, objective weights, validation
thresholds, or a solver qualification policy. Those remain explicit reference-only decisions in the
next calibration increment.
