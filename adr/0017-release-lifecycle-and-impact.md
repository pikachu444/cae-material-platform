# ADR-0017: Append-only Release lifecycle and downstream impact

## 먼저 읽기

- **무엇을 정했나요?** Release와 package는 바꾸지 않고, 사용 가능 상태와 `superseded`·`withdrawn`
  전환을 별도 event로 누적합니다. 종료된 Release는 조회할 수 있지만 새 사용·다운로드는 막습니다.
- **왜 중요한가요?** 이미 전달된 결과와 audit 증거를 보존하면서도 어떤 Release를 더 이상 쓰면 안
  되는지, 무엇으로 대체됐고 어디에서 사용됐는지 명확히 알리기 위해서입니다.
- **언제 읽나요?** Release 상태 전환, successor 연결, download·consume 차단, usage 기록 또는 impact
  조회를 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `lifecycle projection`은 누적 event로 계산한 현재 사용 상태입니다.
  `superseded`는 명시한 후속 Release로 대체됐다는 뜻이고, `withdrawn`은 대체 여부와 관계없이 새
  사용을 중단한다는 뜻입니다. 기존 package 자체는 삭제되지 않습니다.
- **상태 표기는?** `accepted`는 append-only lifecycle 결정을 채택했다는 뜻입니다. 자동 PLM 교체,
  solver 재실행이나 production 보관 정책이 구현됐다는 뜻은 아닙니다.

- Status: accepted
- Date: 2026-07-25
- Scope: T-31 reference Release channel

## Decision

`governance.release`, `release_manifest`, and `release_artifact` remain immutable facts. A
separate `release_lifecycle_projection` records the current lifecycle state, while
`release_lifecycle_event` records the one permitted transition from `released` to either
`superseded` or `withdrawn`. A supersede event must name an explicit successor Release in the
same organization, project, and classification. There is no automatic replacement or deletion.

`release_usage` records explicit package downloads and consume actions. Usage is accepted only
while the lifecycle projection is `released`; a terminal Release can still be read for audit and
impact analysis, but cannot be downloaded or consumed for new work. The impact response exposes
predecessor/successor links, transition history, usage facts, and a warning for terminal states.

## Rationale and boundaries

Keeping lifecycle state outside the immutable Release row preserves stable identity, immutable
revision/package evidence, and the existing T-30 release completeness contract. Explicit typed
tables and composite tenant keys preserve organization/project isolation without a generic EAV or
unbounded JSON payload. Automatic PLM replacement, solver reruns, production object storage, and
cross-tenant release linking are intentionally outside T-31.

## Consequences

- Reads include `lifecycle_state`; clients must not assume every Release is currently usable.
- Download and consume operations create append-only usage facts and fail with a conflict after a
  terminal transition.
- Supersede/withdraw require `release.publish`; impact and usage reads use `release.read`.
- PostgreSQL integration tests must run against a disposable PostgreSQL instance to verify RLS,
  migration constraints, trigger guards, and concurrent transition behavior.
