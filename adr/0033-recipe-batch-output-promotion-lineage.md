# ADR-0033: Exact Recipe/Batch execution lineage for promoted Processing Outputs

## 먼저 읽기

- **무엇을 정했나요?** 성공한 Batch Attempt를 게시된 Recipe 리비전과 Processing Output 리비전을 잇는 공식 근거로 사용합니다. 승격된 모델, Neutral Material JSON, solver card와 내보내기 묶음까지 정확한 Recipe·Batch·Member·Attempt 식별자를 이어서 보존합니다.
- **왜 중요한가요?** 현재값이나 `latest`를 따라가거나 Recipe 필드를 복사하지 않아도, 어떤 절차를 어떤 실행에서 사용해 결과를 만들었는지 재현할 수 있습니다. Recipe 기록이 없던 과거의 직접 실행 결과도 거짓 계보를 붙이지 않고 계속 읽을 수 있습니다.
- **언제 읽나요?** Recipe 게시, Batch 실행, Processing Output 승격, 실행 계보 저장, Neutral Material JSON 또는 일괄 내보내기의 근거 표시를 다룰 때 읽습니다.
- **용어를 쉽게 말하면:** Recipe는 재사용할 수 있게 게시한 처리 절차이고, Batch는 그 절차를 여러 입력에 실행한 작업입니다. Member는 Batch 안의 한 입력, Attempt는 그 입력에 대한 한 번의 실행이며, `exact_revision`은 바뀔 수 있는 최신본이 아니라 특정 리비전을 가리킨다는 뜻입니다.
- **상태 표기는?** Accepted는 성공한 Batch Attempt를 정확한 계보의 기준으로 삼는 결정을 채택했다는 뜻입니다. 모든 과거 Output에 Recipe 근거가 이미 있다는 뜻이 아니며, 기존 기록을 새 계보로 다시 쓰지도 않습니다.

- Status: Accepted
- Date: 2026-07-19
- Deciders: CMP maintainers
- Related: ADR-0029, ADR-0031, T-54, T-55M, T-55P, T-67, T-69, T-70

## Context

A common Processing Output pins its exact Test Data, Mapping Profile, ordered method versions and
result Artifact. A successful Batch Attempt already pins that Output revision and its Batch pins an
exact published Processing Recipe revision. T-67 could promote the Output to a generalized-Maxwell
IR, but did not resolve this existing execution relation. Consequently its Neutral JSON correctly
described direct steps while failing to prove that the steps came from a saved, reusable Recipe.

Copying Recipe fields onto every Processing Output would duplicate ownership and could diverge from
the append-only Batch Attempt record. Searching only by the current Recipe or Output head would also
break reproducibility.

## Decision

The successful `common_processing_batch_attempt` remains the authoritative relation between an
exact Processing Output revision and the exact published Recipe revision owned by its Batch.
Processing exposes a read port that resolves this relation under the caller's tenant and
classification scope. Modeling consumes that port during reviewed polymer or metal promotion and
stores:

- exact Recipe identity, revision and canonical digest;
- exact Batch, Member and successful Attempt identities and attempt number;
- the existing exact Output, Test Data and Mapping Profile evidence.

Migration 080 adds the polymer evidence table columns and migration 081 adds the corresponding
metal IR revision columns. Both use composite exact-revision foreign keys, all-or-none constraints
and deferred triggers that prove the Attempt succeeded and produced the same Output revision. The
family IR canonical schema is `1.3.0` when this origin exists. Historical direct Outputs keep their
`1.2.0` evidence and remain readable.

Neutral promotion maps the exact Recipe revision into `processing_recipe.status=exact_revision`.
The Batch execution identifiers remain in typed IR evidence; the Neutral exchange does not invent a
second Batch schema. Bulk discovery then includes the exact Recipe JSON together with Test JSON,
Mapping Profile, Neutral JSON, reports and both eligible native cards.

## Consequences

- A saved polymer or metal Recipe can be published, batch-executed, reviewed and followed without a
  `latest` alias through IR, Neutral JSON, solver cards and checksum package.
- Direct historical Outputs are not rewritten and clearly report that no Recipe/Batch pin exists.
- An Output produced outside Batch remains promotable for compatibility, but cannot claim Recipe
  reuse evidence.
- No new generic EAV or JSON authority is introduced; PostgreSQL constraints verify the lineage.
