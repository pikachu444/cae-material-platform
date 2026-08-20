# ADR-0027: bulk delivery uses an immutable Export Bundle

## 먼저 읽기

- **무엇을 정했나요?** 사용자가 고른 exact raw·processed data, IR, mapping report, solver card를
  manifest와 checksum이 있는 결정론적 ZIP인 Export Bundle로 비동기 생성합니다.
- **왜 중요한가요?** 공학 data 묶음 전달과 승인된 Release publication을 섞지 않고, 누락·권한 문제를
  미리 차단하며 같은 입력에서 같은 bytes를 다시 만들기 위해서입니다.
- **언제 읽나요?** bulk download, Export Selection·Job, ZIP 구성·한도, manifest·checksum 또는 PLM/CAE
  connector용 package를 구현할 때 읽습니다.
- **용어를 쉽게 말하면:** `Export Selection`은 bundle에 넣을 exact revision과 표현 순서를 고른 기록이고,
  `Export Bundle`은 그 선택으로 만든 감사 가능한 전달 파일입니다. `preflight`는 생성 전에 필수 항목·
  권한·지원 여부를 확인하며, `deterministic`은 같은 입력이면 같은 bytes가 나온다는 뜻입니다.
- **상태 표기는?** `Accepted`는 불변 bulk-transfer 방식을 채택했다는 뜻입니다. Bundle이 승인된
  Release를 대신하거나 외부 connector가 구현 완료됐다는 뜻은 아닙니다.

- Status: Accepted
- Date: 2026-07-16
- Related: T-10, T-13 through T-16, T-25, T-30, T-45

## Context

Individual Artifact and Solver Card downloads exist. A Release currently downloads an immutable
release manifest, not an archive containing selected raw/normalized/processed data, neutral IRs
and cards. Changing Release semantics would mix governed publication with an engineer's bulk data
transfer request.

## Decision

1. Introduce a revisioned `Export Selection` that pins ordered component revisions and requested
   representations. A durable Export Job creates one immutable Export Bundle result.
2. Keep Release and Export Bundle separate. Release is an approved publication; Export Bundle is
   an authorized, audited transfer assembled from explicit immutable inputs.
3. The ZIP contains original raw files, canonical Parquet, readable CSV, IR JSON and schemas,
   mapping reports, native solver cards, `manifest.json`, `checksums.sha256` and a bundle README as
   requested and available.
4. Missing, unsupported or unauthorized required components block preflight. Optional omissions
   appear explicitly in the manifest; nothing is silently dropped.
5. Normalize ZIP ordering and timestamps so identical inputs/options produce identical bytes and
   SHA-256. Each successful retry creates or reuses content by digest without mutating a bundle.
6. Bundle scope is one organization/project and its classification is at least the most restrictive
   included component. Existing short-lived Artifact download authorization is reused.
7. The initial limit is 1,000 components or 5 GiB per bundle and is deployment-configurable.

## Consequences

- Users can transfer experimental, neutral and solver-ready representations together with proof of
  origin and integrity.
- Large assembly remains asynchronous and uses the existing Job/Artifact reconciliation boundary.
- External PLM/CAE connectors can consume the same manifest later without becoming a prerequisite.
