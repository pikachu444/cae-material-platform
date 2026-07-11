# Codex 구현용 저장소 문서 구조

## 1. 목표

Codex 또는 다른 coding agent가 domain 결정을 임의로 만들지 않고, contract와 task 단위로 안전하게 구현하도록 repository layout, dependency rule, 작업 순서를 정의한다.

## 2. 권고 repository tree

```text
cae-material-platform/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── pnpm-workspace.yaml
├── package.json
├── Makefile
├── .env.example
├── docs/
│   ├── 00-research/
│   ├── 01-product/
│   ├── 02-requirements/
│   ├── 03-domain/
│   ├── 04-provenance/
│   ├── 05-architecture/
│   ├── 06-plugins/
│   ├── 07-ir/
│   ├── 08-contracts/
│   ├── 09-analytics/
│   ├── 10-execution/
│   ├── 11-security/
│   ├── 12-roadmap/
│   ├── 13-delivery/
│   ├── 14-testing/
│   ├── 15-governance/
│   └── 16-repository/
├── adr/
│   ├── 0001-modular-monolith.md
│   ├── 0002-postgresql-provenance.md
│   ├── 0003-immutable-artifacts.md
│   ├── 0004-isolated-plugins.md
│   └── 0005-material-model-ir.md
├── contracts/
│   ├── http/openapi.yaml
│   ├── events/asyncapi.yaml
│   ├── events/schemas/
│   ├── jobs/job-spec.schema.json
│   ├── jobs/result-manifest.schema.json
│   ├── plugins/plugin-manifest.schema.json
│   ├── ir/material-model-ir-envelope.schema.json
│   └── examples/
├── backend/
│   ├── src/cmp/
│   │   ├── bootstrap/
│   │   ├── shared/
│   │   │   ├── domain/
│   │   │   ├── contracts/
│   │   │   └── observability/
│   │   └── modules/
│   │       ├── identity_access/
│   │       ├── catalog/
│   │       ├── testing/
│   │       ├── artifacts/
│   │       ├── datasets/
│   │       ├── processing/
│   │       ├── statistics/
│   │       ├── modeling/
│   │       ├── exporting/
│   │       ├── validation/
│   │       ├── review_release/
│   │       ├── provenance/
│   │       ├── audit/
│   │       ├── plugins/
│   │       └── jobs/
│   ├── migrations/
│   └── tests/
├── apps/
│   ├── api/
│   ├── worker/
│   ├── plugin-runner/
│   └── web/
├── sdk/
│   └── python/cmp_plugin_sdk/
├── plugins/
│   ├── reference/
│   │   ├── synthetic-importer/
│   │   ├── identity-processor/
│   │   ├── reference-statistics/
│   │   ├── analytic-material-model/
│   │   ├── reference-calibrator/
│   │   ├── reference-validator/
│   │   └── text-solver-exporter/
│   └── production/
├── frontend/
│   └── src/
├── tests/
│   ├── architecture/
│   ├── contracts/
│   ├── integration/
│   ├── scientific/
│   ├── golden/
│   ├── security/
│   ├── migrations/
│   └── e2e/
├── fixtures/
│   ├── synthetic/
│   └── manifests/
├── deploy/
│   ├── compose/
│   ├── helm/
│   └── observability/
└── scripts/
```

MVP에서는 `deploy/helm`을 placeholder로 두고 실제 target이 결정된 뒤 구현할 수 있다.

## 3. Module 내부 구조

```text
modules/catalog/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── commands.py
│   ├── events.py
│   └── errors.py
├── application/
│   ├── services.py
│   ├── handlers.py
│   └── queries.py
├── ports/
│   ├── repositories.py
│   └── external_services.py
├── adapters/
│   ├── persistence/
│   └── api/
└── tests/
```

### Dependency rule

```text
domain <- application <- ports/adapters <- bootstrap/apps
```

- domain은 FastAPI, SQLAlchemy, S3, plugin package를 import하지 않는다.
- module은 다른 module의 adapter/repository를 직접 import하지 않는다.
- cross-module command는 application service, read는 public query port를 사용한다.
- core/backend는 `plugins/production` implementation을 import하지 않는다.
- contracts package는 domain-specific executable logic을 포함하지 않는다.

Architecture test로 이 규칙을 강제한다.

## 4. PostgreSQL schema ownership

| Module | Schema |
| --- | --- |
| identity/access | `identity` |
| catalog | `catalog` |
| testing | `testing` |
| artifacts | `artifact` |
| datasets | `dataset` |
| processing | `processing` |
| statistics | `statistics` |
| modeling | `modeling` |
| exporting | `exporting` |
| validation | `validation` |
| review/release | `governance` |
| provenance | `provenance` |
| audit | `audit` |
| plugins | `plugin` |
| jobs/events | `job`, `eventing` |

Migration 파일 이름에 owner module과 task ID를 넣는다.

```text
20260711_001_T06_revision_kernel.py
20260711_002_T13_provenance_core.py
```

다른 module table을 변경하는 migration은 공동 owner review와 ADR이 필요하다.

## 5. Contract-first 작업 순서

각 Task는 다음 순서로 구현한다.

1. 관련 `FR/NFR`, ADR, Task를 PR description에 연결
2. domain terminology/invariant 확인
3. JSON Schema/OpenAPI/event contract 또는 internal port 작성
4. positive/negative contract fixture 작성
5. domain entity/service 구현
6. persistence/runner adapter 구현
7. integration/security/provenance test
8. 문서와 decision/open question 갱신
9. domain review가 필요한 expected result/golden 승인

## 6. Codex 작업 guardrail

Codex는 다음을 임의 결정하지 않는다.

- production tensile standard/material family
- production constitutive equation/parameters/objective
- production solver/card/keyword/unit mapping
- validation geometry/BC/metric/threshold
- regulatory compliance claim

미결정 값이 필요하면 `TBD` contract, synthetic reference plugin, explicit issue를 사용한다. production처럼 보이는 임시 model/card를 넣지 않는다.

## 7. Reference plugin의 목적

Reference plugin은 framework와 provenance를 검증한다.

| Plugin | 허용 목적 | 금지 |
| --- | --- | --- |
| synthetic importer | mapping/import contract | 실제 시험 format 지원 주장 |
| identity processor | recipe/run/provenance | 실제 smoothing 기준 주장 |
| reference statistics | known synthetic result | production outlier policy |
| analytic material model | IR/evaluator contract | 실제 재료 구성모델 주장 |
| reference calibrator | deterministic optimization flow | production parameter 사용 |
| reference validator | evidence schema | 실제 solver validation 주장 |
| text exporter | mapping/golden framework | 상용 solver card로 배포 |

모든 reference output에는 `non-production` marker를 넣고 production release channel에서 차단한다.

## 8. 권고 developer command

실제 bootstrap에서 다음 interface를 제공한다.

```text
make bootstrap
make lint
make typecheck
make test-unit
make test-contract
make test-integration
make test-scientific
make test-security
make test-e2e-reference
make migrate
make run-api
make run-worker
make run-web
```

명령 내부 tool은 바뀔 수 있지만 developer-facing command는 문서화하고 CI와 동일하게 유지한다.

## 9. AGENTS.md 필수 내용

- 읽어야 할 문서 순서
- 확정/가정/TBD 판정 규칙
- module dependency rule
- raw/release immutability
- migration/contract/golden update 금지사항
- task별 Definition of Done
- domain review가 필요한 파일 경로
- test command
- 실제/민감 데이터 저장 금지

이 패키지 root의 `AGENTS.md`를 시작점으로 제공한다.

## 10. PR checklist

```text
[ ] FR/NFR, Task, ADR 연결
[ ] 사실/가정/TBD를 임의로 바꾸지 않음
[ ] public contract/schema 갱신 및 compatibility 확인
[ ] immutable revision/input ref 사용
[ ] provenance usage/generation/agent 포함
[ ] organization/project/RLS 적용
[ ] unit/quantity-kind behavior 명시
[ ] unit/integration/regression test 추가
[ ] scientific/golden 변경은 domain 승인
[ ] migration/restore 영향 검토
[ ] log/diagnostic에 secret/raw data 없음
```

## 11. 첫 구현 순서

```text
T-01 → T-02 → T-06
     → T-03 → T-04
     → T-15 → T-17 → T-18
     → T-09 → T-10 → T-13 → T-14 → T-16
     → T-07 → T-08 → T-11 → T-12
     → T-19 → T-20 → T-21
     → T-22 → T-23 → T-24
     → T-25 → T-26 → T-27 → T-28
     → T-29 → T-30
```

UI T-32/T-33은 관련 API와 vertical slice별로 병행한다. T-05, T-31, T-34~T-38은 P0 기능과 병행 또는 hardening 단계에서 완료한다.

## 12. 첫 Codex 실행 단위

처음 한 번에 전체 platform을 만들지 않는다. 첫 구현 request는 다음으로 제한한다.

```text
T-01 + T-02:
- repository skeleton
- one health endpoint
- empty worker startup
- architecture test
- contract lint pipeline
- no business tables
```

검증 후 T-06 revision kernel로 이동한다.

