# ADR-0016: Reference Release completeness gate and immutable package

## 먼저 읽기

- **무엇을 정했나요?** exact Material lineage·IR·solver card·validation result·review를 한 package에
  고정하고, validation과 review가 통과하며 mapping에 미지원·근사가 없을 때만 Release를 만듭니다.
- **왜 중요한가요?** 배포 시점에 더 최신인 다른 결과를 몰래 끼워 넣지 않고, 사용자가 받은 package를
  같은 입력과 digest로 다시 확인할 수 있게 하기 위해서입니다.
- **언제 읽나요?** Release publish gate, manifest·package 생성, download·ETag, review·validation 연결
  또는 Release 저장 방식을 바꿀 때 읽습니다.
- **용어를 쉽게 말하면:** `completeness gate`는 필요한 증거가 모두 맞아야 통과하는 차단 조건이고,
  `Release manifest`는 package에 들어간 정확한 revision과 digest 목록입니다. `ETag`는 내려받은
  내용이 같은지 확인하는 HTTP 식별값입니다.
- **상태 표기는?** `Accepted`는 database-backed reference Release 경계를 채택했다는 뜻입니다.
  signed distribution, production object storage나 production solver qualification 완료를 뜻하지 않습니다.

- Status: Accepted
- Date: 2026-07-24
- Scope: T-30 reference Release channel

## Context

The platform already stores immutable Material Model IR, Solver Card, Validation Result, and
review evidence, but those facts were not yet composed into a user-visible CAE delivery artifact.
T-30 must provide a small end-to-end Release flow without turning the platform into a generic
payload store or claiming production solver qualification.

## Decision

1. The first Release channel is explicitly `reference` and has only the `released` state. A stable
   Release identity is separate from an immutable `release_manifest` and immutable
   `release_artifact` package row.
2. A publish command names one Material/State/Property lineage, Material Model revision, Solver
   Card revision, Validation Result, T-29 Review Request, and provenance snapshot. Each source is
   checked in the same organization/project/classification scope and by its SHA-256 digest.
3. Publication fails closed unless the Validation Result is `passed`, the Review decision is
   `approved` for the exact candidate digest, the Solver Card is the declared non-production
   reference card, and every typed mapping status is neither `unsupported` nor `approximated`.
4. PostgreSQL uses explicit typed tables, composite tenant foreign keys, unique identities,
   indexes, forced RLS, and the existing immutable-row trigger. No generic EAV, key/value, or
   catch-all release JSON column is introduced. The package document is a small explicit manifest;
   its digest and byte length are stored alongside it.
5. The protected API exposes create/list/read/download and the React workbench exposes the same
   reference channel. Download returns the stored package digest as a strong ETag.

## Consequences

- A Release is reproducible and cannot silently substitute a newer model/card/result/review.
- The database-backed package is intentionally a reference/development delivery adapter. A
  production object-store artifact, signed distribution, supersede/withdraw lifecycle, retention,
  and release approval matrix remain T-31+ decisions.
- The gate currently consumes the existing T-22/T-25/T-28/T-29 reference records and therefore
  does not add Material, importer, fitting, or solver-specific domain behavior.
