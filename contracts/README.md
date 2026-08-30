# Public contract baseline

## 처음 읽는 개발자를 위한 안내

이 디렉터리의 **contract(계약)** 는 법률 문서가 아니라, 서로 따로 바뀔 수 있는 API,
worker, plugin, client가 같은 요청·응답·이벤트 모양과 실패 조건을 지키도록 정한 약속입니다.
아래 `Status`는 이 README가 다루는 작업과 현재 HTTP 계약 버전을 알려 주는 목록이지, 적힌
기능이 모두 운영 환경에서 완성됐다는 표시는 아닙니다.

### 용어를 먼저 이해하기

- **OpenAPI**: REST API의 주소, HTTP 방식, 요청·응답과 인증 방법을 기계가 읽을 수 있게 적은
  명세입니다. 이 저장소의 현재 원본은 [`http/openapi.yaml`](http/openapi.yaml)입니다.
- **AsyncAPI**: 비동기 이벤트의 채널, 메시지 모양과 전달 규칙을 적은 명세입니다. 시작 파일은
  [`events/asyncapi.yaml`](events/asyncapi.yaml)이고, 실제 JSON 모양은 같은 폴더의 schema가
  더 자세히 제한합니다.
- **JSON Schema**: JSON 문서에 어떤 필드가 필요하고 어떤 값이 허용되거나 금지되는지 검사하는
  규칙입니다. 이름이 `*.schema.json`인 파일이 여기에 해당합니다.
- **baseline**: 이미 받아들인 이전 OpenAPI의 호환성 기준점입니다. 현재 명세의 복사본이나
  최신본이 아닙니다. 검사를 통과하려고
  [`http/openapi.baseline.yaml`](http/openapi.baseline.yaml)을 현재 파일로 덮어쓰면 안 됩니다.
- **fixture**: 계약이 받아들여야 하거나 거부해야 하는 상황을 재현하는 고정 예제 데이터입니다.
  이 디렉터리에서는 [`examples/positive`](examples/positive)는 통과해야 하고,
  [`examples/negative`](examples/negative)는 실패해야 합니다.
- **generated client**: OpenAPI를 입력으로 도구가 다시 만드는 호출 코드입니다. 현재 저장소에는
  health API만 다루는 작은 [Python client](../generated/python/cmp_api_client/client.py)가 있으며,
  이 파일을 직접 고치지 않습니다.

### 흔한 작업은 여기서 시작하기

| 하려는 일 | 먼저 열 파일 | 이어서 확인할 곳 |
| --- | --- | --- |
| REST endpoint, 요청·응답 또는 인증 변경 | [`http/openapi.yaml`](http/openapi.yaml) | 영향받는 runtime route와 `tests/contracts/test_contracts.py` |
| 기존 API 호환성 판단 | 현재 [`openapi.yaml`](http/openapi.yaml)과 [`openapi.baseline.yaml`](http/openapi.baseline.yaml) | 아래 Versioning policy와 호환성 검사 결과 |
| 이벤트를 발행하거나 소비 | [`events/asyncapi.yaml`](events/asyncapi.yaml) | 해당 `events/*.schema.json`과 전달·중복 처리 규칙 |
| Job, plugin, Dataset 같은 JSON 문서 변경 | 대상 폴더의 `*.schema.json` | 같은 의미의 positive/negative example과 실제 validator |
| 어떤 계약 파일이 있는지 탐색 | 아래 **Files** 목록 | 해당 파일의 `$id`, version, required 필드와 관련 테스트 |

짧게 읽으려면 ① 작업에 해당하는 원본 계약, ② 성공·실패 example, ③ 아래 Versioning policy,
④ 실제 소비 코드와 검사를 차례로 봅니다. 상세한 파일 설명은 이 안내 뒤의 기존 **Files** 목록에
그대로 남아 있습니다.

### 실제로 어디서 쓰이나

- [`cmp.tools.contracts`](../backend/src/cmp/tools/contracts.py)는 루트의 모든 JSON Schema 문법,
  OpenAPI·AsyncAPI 기본 구조, 연결된 positive/negative example과 생성 client 최신성을 검사합니다.
- [`tests/contracts/test_contracts.py`](../tests/contracts/test_contracts.py)는 OpenAPI 원본을 FastAPI가
  내놓는 runtime OpenAPI와 대조하고, 생성 client가 재생성 결과와 같은지 확인합니다.
- Job Spec, ArtifactAvailable event, plugin manifest는 운영 코드가 패키지에 포함된 schema 복사본을
  읽어 검증합니다. 대표 소비자는 [Job validator](../backend/src/cmp/modules/jobs/adapters/contracts/jsonschema.py),
  [event validator](../backend/src/cmp/modules/jobs/adapters/contracts/events_jsonschema.py),
  [plugin validator](../backend/src/cmp/modules/plugins/adapters/contracts/jsonschema.py)입니다. 계약 테스트는
  이 복사본이 루트의 공개 계약과 정확히 같은지 확인합니다.
- 따라서 OpenAPI YAML이 모든 endpoint를 실행 중에 직접 만드는 것도, 모든 JSON Schema가 루트
  경로에서 그대로 로드되는 것도 아닙니다. 계약 원본, runtime 형상과 패키지 복사본이 함께 맞아야
  최신 상태입니다.

### 계약 검사는 무엇을 확인하나

저장소 루트에서 다음 명령을 실행합니다.

```text
make check-contracts
```

`make`를 사용할 수 없는 환경에서는 같은 두 검사를 직접 실행합니다.

```text
uv run cmp-check-contracts lint --root .
uv run cmp-check-contracts compat --baseline contracts/http/openapi.baseline.yaml --current contracts/http/openapi.yaml
```

`lint`는 schema 문법, OpenAPI·AsyncAPI 기본 구조, 지정된 성공·실패 example, 생성 client 최신성을
확인합니다. `compat`은 baseline과 비교해 endpoint·operation·response·schema·property 삭제와
optional 필드의 required 전환을 보수적으로 막습니다. 테스트에 등록된 endpoint·component가
runtime에도 대응하는지와 패키지 복사본까지 확인하려면
`uv run pytest tests/contracts/test_contracts.py`도 실행합니다. OpenAPI를 의도적으로
바꾼 뒤 생성 client만 오래됐다는 오류가 나면 원본을 다시 확인하고 `make generate-client`로
재생성하며, 생성 파일을 손으로 맞추지 않습니다.

이 검사들은 형식과 알려진 호환성 경계를 확인할 뿐, 새 동작의 제품 의미나 운영 적합성을 대신
승인하지 않습니다.

### 멈추고 권위를 확인해야 할 때

- 활성 issue·requirement·ADR의 결정과 계약 또는 runtime 동작이 서로 다를 때
- 호환성 실패를 없애기 위해 baseline을 갱신하거나 기존 필드를 조용히 지우고 싶을 때
- 공개 계약과 패키지 schema, 생성 client 또는 runtime OpenAPI가 이유 없이 어긋날 때
- 운영 표준·재료 모델·허용 오차처럼 아직 제품 소유자가 정하지 않은 의미가 필요할 때

이 경우 한쪽을 최신이라고 추측해 맞추지 않습니다. 충돌한 경로와 검사 결과를 기록하고 권위를
해결한 뒤 진행합니다. breaking change라면 아래 정책대로 새 major 계약, ADR과 migration 안내가
필요합니다.

Status: foundation `T-02` through `T-18`, plus reference vertical subsets `T-07`, `T-08`,
`T-11`, `T-12`, `T-19`, `T-20`, `T-21`, `T-22`, `T-25`, `T-26`, `T-27`, `T-28`, `T-29`,
the `T-32` workbench, and product-depth slices `T-39` through `T-42`. HTTP contract version
`0.40.0`.

## Files

- `http/openapi.yaml`: REST source contract
- `http/openapi.baseline.yaml`: last accepted compatibility baseline
- `events/asyncapi.yaml`: CloudEvents 1.0 ArtifactAvailable and Schema Bundle applied events with
  at-least-once delivery contracts
- `events/*.schema.json`: immutable event payload/envelope contracts without storage keys
- `jobs/*.schema.json`: immutable runner envelopes
- `artifacts/*.schema.json`: upload/Raw Asset plus immutable Artifact metadata, transfer grant,
  completion, and sanitized problem contracts
- `provenance/*.schema.json`: immutable Entity, bounded lineage/impact, generic provenance
  completeness, and sanitized problem contracts
- `audit/*.schema.json`: payload-free audit event page, bounded export, integrity report, and
  sanitized problem contracts
- `plugins/plugin-manifest.schema.json`: package metadata baseline
- `plugins/plugin-package-registration.schema.json`: signed package/SBOM/schema registration input
- `plugins/plugin-package-resource.schema.json`: immutable package and state-history resource
- `plugins/plugin-problem.schema.json`: sanitized registry problem response
- `catalog/schema-definition-bundle.schema.json`: arbitrary-cardinality Catalog Schema Definition
  Bundle v1 with a closed draft 2020-12 keyword/extension subset, data categories, business keys,
  quantity/discrete hints and bundle-local references only
- `catalog/schema-definition-source-set.schema.json`: exact path-sorted, per-content checksummed
  multi-file source envelope consumed by the source adapter before canonical bundle planning
- `catalog/schema-definition-plan.schema.json`: exact Artifact-bound deterministic
  `create/update/no-op/conflict/error` dry-run result with an explicit empty write set
- `catalog/schema-definition-bundle-application.schema.json`: immutable apply/read-back evidence and
  the exact Artifact/SHA-256/`plan_fingerprint` request boundary
- `units/unit-resources.schema.json`: additive common-unit contract `1.1.0` with the original
  bounded CAE registry plus explicit `speed` (`m/s`, `mm/s`, `mm/min`) and density `tonne/mm3`,
  structured conversion errors, and immutable Unit Profile resources; `kg_m_s` remains a
  compatibility identifier rather than a production default
- `datasets/curve-channel-metadata.schema.json`: additive curve definition contract `1.0.0` for
  channel roles and quantity semantics, original/normalized/display units, exact scale/offset,
  typed scalar or pointwise deviation evidence, immutable Artifact/revision/source pins, and
  calculation provenance
- `ir/material-model-ir-envelope.schema.json`: common IR envelope baseline
- `datasets/reference-tensile-resources.schema.json`: typed reference tensile Dataset, curve, and
  immutable one-member Selection resources
- `datasets/viscoelastic-master-resources.schema.json`: ordered exact-revision viscoelastic
  replicate Selections with temperature and explicit outlier-assessment status
- `datasets/governed-import-resources.schema.json`: approved reusable CSV/TSV/XLSX Import
  Profiles, needs-input previews, terminal Import Runs, and raw/normalized typed Dataset metadata
- `testing/reference-import-resources.schema.json`: immutable header-only Detection Report and
  human-confirmed typed Import Mapping identity/revision resources
- `testing/test-context-resources.schema.json`: governed Campaign, Instrument, dated Calibration,
  typed Condition Snapshot, and exact Test Run Context revision resources
- `processing/reference-tensile-crop-resources.schema.json`: typed crop/common-grid Recipes,
  committed member Runs, and grouped replicate alignment output
  resources for the reference Processing slice
- `processing/reference-import-resources.schema.json`: typed pinned reference Import Run resource
  with immutable inputs and terminal Dataset output link
- `processing/viscoelastic-master-curve-resources.schema.json`: explicit manual/WLF shift Plan,
  terminal Run, three typed output revisions, and bounded aligned/statistics/master preview
- `statistics/reference-tensile-pair-resources.schema.json`: typed two-selection reference
  Statistics/QC Plan, committed Run, scalar/curve Result, and bounded curve preview resources
- `statistics/reference-tensile-outlier-resources.schema.json`: typed immutable reference-pair
  Detection Plans, zero-or-two review_required candidates, append-only human Assessments, and
  exact-scope comparison resources without source mutation or automatic exclusion
- `statistics/reference-tensile-replicate-outlier-resources.schema.json`: non-production
  multi-replicate modified-z evidence, append-only human Assessment, and immutable calibration
  input Scope resources that preserve every source Dataset and Selection revision
- `validation/reference-virtual-specimen-resources.schema.json`: typed non-production reference
  virtual-specimen Template/Plan revisions, exact immutable IR/Card/Selection pins, durable Run,
  and shared mock/manual Result Manifest Artifact evidence
- `validation/reference-result-interpretation-resources.schema.json`: typed non-production
  response extraction, numerical-health, observed-grid comparison, and immutable reference verdict
  evidence; it does not claim production model or solver validation
- `governance/review-resources.schema.json`: immutable review request/decision resources with
  manifest-digest pinning, lifecycle state, and separation-of-duties evidence
- `revisions/revision-metadata.schema.json`: content-free typed-revision metadata envelope
- `identity/me-response.schema.json`: authenticated principal and selected tenant context
- `examples/positive`: examples that must validate
- `examples/negative`: examples that must be rejected

## Versioning policy

- Major: semantic or structural breaking change
- Minor: backward-compatible additive change
- Patch: clarification or non-semantic correction
- OpenAPI removals, response removals, property removals, and optional-to-required changes fail the
  baseline compatibility check.
- JSON Schema and event contracts use their own explicit version fields and immutable schema IDs.
- These contracts contain only explicitly marked non-production reference material, tensile,
  processing, IR, and solver semantics; they make no production qualification claim.
- Revision content remains resource-specific; the common schema must never gain a generic
  `content`/EAV payload.
- Schema Definition Bundle v1 preserves its exact immutable Artifact identity and accepts only local
  fragments or exact record `$id` references declared inside the same bundle. Source and bundle
  organization/project/classification must match. Unknown keywords,
  external URL/file/network references and unrepresentable Catalog projection fail closed. Planning
  reads an RLS-bound repeatable read-only snapshot and treats stale exact dependency revision pins as
  updates. It folds append-only placement history by logical Profile/Table key and never deletes
  missing Catalog objects. Apply re-plans under a project/table lock and accepts no client actions;
  its revisions, exact publication markers, immutable application/bindings, Artifact provenance,
  audit and outbox event share one transaction. Export is allowed only while current heads and
  publication still equal the application bindings, then returns canonical JSON from the exact
  retained source Artifact.
- `/api/v1/me` accepts bearer access tokens; ID tokens are not an interchangeable credential.
- Identity responses require both organization and project UUIDs. `/me` remains an authenticated
  identity/context response and does not imply authorization. Each protected endpoint must bind an
  explicit T-04 permission before opening its resource transaction.
- Role and clearance details are internal policy state rather than a public `/me` field. A future
  role-management API requires its own versioned request/response schema.
- Job submission requires an idempotency key and an immutable Job Spec. Retry appends a new
  Attempt/Spec pair; it never rewrites an existing attempt or accepts a moving `latest` input.
- Result manifests remain immutable references and digests. T-10 owns Artifact finalization and
  integrity observations; T-16 owns durable scheduling/outbox rather than the T-15 projection.
- The T-18 Python runner packages exact copies of Job Spec/Result Manifest 1.0. A Result Manifest
  records whether the runtime was non-production; the execution service rejects a mode mismatch.
- Upload creation pins filename/MIME/size/SHA-256 and streams immutable numbered parts. Raw Asset
  responses expose digest and `staged_verified` state but never an internal object-store key;
  completion may return the T-10 available Artifact ID.
- Artifact metadata exposes content digest, semantic role/schema, encryption profile, and current
  integrity status. Staging/final object keys stay internal; byte transfer requires bearer
  authorization plus an actor/tenant/content/expiry-bound capability header.
- Provenance Entity responses expose immutable typed UUID/digest references and primary-generation
  completeness. T-14 lineage/impact responses are read-only, bounded, deterministically ordered,
  and cursor-paginated; completeness is eligible only when no issue remains. Moving heads and
  graph writes are rejected, and Release-specific policy remains outside this contract.
- ArtifactAvailable is emitted from the same transaction as Artifact commit, uses aggregate
  sequence and tenant/classification CloudEvent extensions, and exposes content metadata but no
  staging/final object key. Duplicate delivery is expected and consumer inbox deduplication is
  mandatory.
- Plugin registration separates a stable Definition from immutable version/digest Packages. A
  package becomes eligible only after an authorized verification event and activation is scoped to
  the selected organization/project; revocation never overwrites package or state-history facts.
- Audit access is read-only and requires `audit.read`. Events expose explicit actor/action/target,
  outcome, request/trace, redacted client, reason, and hash fields; raw payloads, secrets, and object
  keys are forbidden. Export is capped at 10000 events and includes its chain anchor and roots.
- A reference Processing Run pins one normalized Dataset revision and one typed crop Recipe revision.
  Its processed output is a separate immutable Dataset identity, never a replacement for raw or
  normalized source bytes. Generic processing payloads and implicit interpolation are forbidden.
- The reference importer records header evidence separately from user confirmation. A Detection
  Report always remains `needs_input`; a human-confirmed Mapping revision pins its Raw
  Asset/Artifact and digest, and an Import Run must pin that concrete revision before it can create
  Dataset output. Low-confidence suggestions never become a committed mapping automatically.
- A reference Statistical Plan pins exactly two distinct normalized Selection revisions from distinct
  Test Runs. Curve statistics require identical observed engineering-strain grids; the contract
  explicitly forbids implicit alignment/resampling and marks the two-sample confidence interval as
  `not_provided_reference_pair`.
- A curve preview validates the complete immutable Artifact before producing a same-index bounded
  sample. Contract `1.0.0` distinguishes `declared`, reviewed `legacy_compatible`, and honest
  `absent` metadata. Only an explicit lower/upper pair with one band group is rendered as a band;
  method/version, pointwise or simultaneous coverage, confidence/quantile parameters and source
  counts retain their recorded meanings. Unknown legacy formats remain readable as values without
  inferred channels, units, deviation or Fit eligibility; known-but-corrupt formats fail closed.
- Common-unit quantities use the exact #205 registry and Unit Profile trace. Existing canonical
  quantities outside that closed registry, including `frequency.cyclic`/`Hz`, require their stored
  explicit scale/offset and are neither rejected nor added to the registry by this contract.
- A reference Validation Plan pins concrete Template, Material Model IR, Solver Card, and
  experimental Selection revisions; `reference_inline_mock` and `manual_attach` share one
  immutable Result Manifest shape. T-28 extracts a typed SI response only from bounded native
  evidence, records numerical health separately, and compares at the observed experimental strain
  grid with explicit linear interpolation and no extrapolation. Normal termination alone is not a
  pass; abnormal/unhealthy output and fitted-selection overlap are `not_evaluated`. No shell command
  field is public.

Run `make check-contracts` after every contract change. Accepting a breaking change requires a new
major contract, an ADR, and migration guidance; do not overwrite the baseline to hide the break.

