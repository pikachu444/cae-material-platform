# ADR-0026: iterative calibration appends IR revisions and evidence

## 먼저 읽기

- **무엇을 정했나요?** 같은 논리 model을 다시 calibration할 때 새 model ID를 만들지 않고, exact 이전
  head를 가리키는 새 IR revision과 그 Candidate·Run·diagnostics 증거를 추가합니다.
- **왜 중요한가요?** 한 model의 calibration 이력을 이어서 비교하면서도, 나중 revision이 이전 card·
  Release나 promotion evidence를 바꾸지 않게 하기 위해서입니다.
- **언제 읽나요?** iterative recalibration, Candidate promotion, stale-head 충돌, IR revision chain,
  solver card·Release impact를 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `evidence chain`은 각 IR revision이 사용한 선택·실행·후보 증거의 연결입니다.
  `based_on_revision_id`는 바로 이전 revision을 가리키고, `compare-and-swap`은 예상한 head가 그대로일
  때만 새 revision을 추가하는 충돌 방지 방식입니다.
- **상태 표기는?** 이 결정은 채택됐고 bounded Ogden Candidate workflow에는 구현됐습니다. 이전
  linear-Prony 흐름이나 모든 model family가 같은 evidence-chain으로 전환됐다는 뜻은 아닙니다.

- Status: Accepted and implemented for the bounded Ogden Candidate workflow
- Date: 2026-07-16
- Related: ADR-0012, ADR-0022; T-44

## Context

The current linear-Prony reference path correctly prevents a promoted revision from silently
replacing its calibration evidence. Requiring a new Material Model identity for every recalibration
would, however, split the engineering history of one logical model and make card/release impact
analysis harder.

## Decision

1. Recalibration of the same logical model retains the Material Model stable identity and appends
   revision `rN` with `based_on_revision_id` pointing to the exact prior head.
2. Each IR revision owns one immutable promotion-evidence record that pins the Candidate Selection
   revision, Calibration Run, Candidate and diagnostics digests used for that revision.
3. Prior promotion evidence is read through the revision chain; it is never copied over, replaced
   or collapsed into a mutable list.
4. Promotion requires compare-and-swap against the current IR revision and rejects a reused
   Candidate/Selection, stale head, cross-scope evidence or non-converged Candidate.
5. A user reason remains mandatory. Numerical convergence never performs automatic promotion.
6. Cards and releases continue to pin one exact IR revision. A later calibration does not alter an
   earlier card or release.

## Consequences

- Users can compare calibration rounds without losing stable model identity.
- Migration 055, the protected contract and the connected T-44 UI implement this decision for
  governed multi-test Ogden Candidates. The older bounded linear-Prony path retains its original
  single-promotion guard until it is migrated to the same evidence-chain contract.
- Release impact analysis can distinguish a new model revision from a new logical model.
