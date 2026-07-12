# T-18 Isolated runner, Python SDK, compatibility test kit 구현 기록

## 1. 추적성

- Task: `T-18`
- Requirements: `FR-PLG-001`, `FR-PLG-003`, `FR-PLG-004`, `NFR-REP-001`,
  `NFR-REP-003`, `NFR-DR-002`, `NFR-PERF-006`, `NFR-SEC-002`, `NFR-SEC-005`,
  `NFR-SEC-006`, `NFR-MOD-001`, `NFR-MOD-002`, `NFR-COMP-001`, `NFR-DOC-001`
- ADR: `ADR-001`, `ADR-002`, `ADR-003`, `ADR-004`
- 선행 구현: T-02 Job Spec/Result Manifest 1.0, T-03 service principal security context,
  T-04 authorization/RLS, T-15 Job/Attempt/Lease worker, T-17 immutable package registry

T-18은 승인된 package와 immutable Job Spec을 받아 격리된 process/container에서 실행하고,
Result Manifest와 staged output을 다시 검증하는 범위다. Material, 시험 importer, fitting,
constitutive model, calibration, solver exporter의 과학·도메인 동작은 구현하지 않는다.

## 2. 아키텍처 질문과 권장 가정

구현을 중단할 정도의 질문은 없었고, 다음 보수적 가정을 적용했다.

1. **T-10 artifact store 미구현**: package/input byte materialization과 validated output/manifest
   commit은 명시적 application port로 둔다. runner는 전달받은 모든 byte의 digest와 size를 다시
   검증하지만 authoritative object availability나 commit 성공을 가장하지 않는다.
2. **개발 runner의 신뢰 수준**: local subprocess와 Python audit/monkey-patch guard는 reviewed
   synthetic/development package용 defense-in-depth다. host kernel 수준의 production security boundary로
   취급하지 않는다.
3. **production runtime**: 특정 Docker, containerd, Kubernetes, cloud vendor를 선택하지 않는다.
   runtime-neutral OCI plan과 capability attestation port를 제공하며, 필수 control 하나라도 증명되지
   않으면 실행 전에 거부한다.
4. **현재 registry admission**: T-17 Manifest 1.0은 `non_production: true` package만 허용한다.
   OCI adapter와 Result Manifest 계약은 production-ready지만 production image admission/signing policy는
   후속 registry/supply-chain 결정이 필요하다.
5. **TCK 의미**: 일곱 extension type은 같은 contract-echo fixture로 protocol만 검증한다. TCK 통과는
   scientific validity, domain evidence, commercial solver compatibility를 의미하지 않는다.
6. **worker bootstrap**: trusted project-scoped service principal, T-10 materializer/committer, runtime이
   모두 주입될 때만 `plugin.run` handler를 구성한다. 누락된 배포 설정을 가짜 credential이나 local
   mutable path로 대체하지 않고 CLI는 idle 상태를 유지한다.
7. **1.0 contract bound 보정**: T-18 이전에는 실행 가능한 production package/runner가 없었다.
   첫 executable boundary를 열기 전에 기존 Job Spec/Result Manifest 1.0의 unbounded string/array/int와
   opaque staged reference를 repository 정책 한계에 맞게 좁힌다. 외부 production package admission 후에는
   같은 narrowing을 1.0에 적용하지 않고 새 major와 migration window가 필요하다.

## 3. 모듈 경계

| 계층 | 책임 |
| --- | --- |
| Domain | sandbox policy, resource/output bounds, executable package, staged input/output, validated result |
| Application | Job/package identity, tenant, resource/config/input/output allowlist, Result Manifest와 byte 재검증 |
| Planning | T-17 active package 조회, extension/schema 선택, T-10 materialization port, runner limit 구성 |
| SDK | typed Job Spec view, read-only input, bounded output, cancellation/deadline, deterministic RNG, diagnostics |
| Subprocess adapter | package ZIP 검증/추출, attempt-scoped staging, child process timeout/cancel, bounded file protocol |
| OCI adapter | vendor-neutral execution plan과 production capability attestation |
| Worker bridge | T-15 Attempt terminal state/failure taxonomy와 committed manifest reference 매핑 |

Core는 entrypoint를 문자열로만 다룬다. 실제 `module:attribute` import는 독립 runner process 내부에서만
수행한다. Architecture rule `ARCH-003`은 production뿐 아니라 reference implementation을 core에서
import하는 것도 거부한다.

## 4. Python SDK와 runner protocol

SDK package는 `cmp-plugin-sdk` 0.1.0이며 runner contract 1.0을 사용한다.

- `RunnerJobSpec`: schema 검증이 끝난 immutable Job Spec의 typed read view
- `PluginExtension`: `describe`, `validate_job`, `run` 세 method contract
- `RunContext.read_input`: attempt-scoped regular file만 열고 size/SHA-256을 다시 검증
- `RunContext.write_output`: declared role/schema/media type과 per-role/total byte limit 적용
- `temporary_path`: ephemeral workspace 아래 safe relative path만 허용
- `raise_if_cancelled`: marker 기반 cooperative cancellation과 immutable deadline 확인
- `rng`: Job Spec seed로 초기화한 deterministic RNG
- `Diagnostic`: bounded code/severity/message/evidence 구조

Runner가 plugin에서 Result Manifest 객체를 받지 않는다. Plugin은 SDK context에 output과 diagnostics를
기록하고 generic outcome만 반환한다. Standalone runner가 job/attempt/reproducibility identity와 timing을
포함한 Result Manifest를 직접 생성하고 schema 1.0으로 검증한다. Plugin exception detail과 filesystem
경로는 외부 diagnostic에 포함하지 않는다.

## 5. 격리와 무결성

### Local subprocess — non-production

- package archive SHA-256/size, ZIP entry count/unpacked size, dependency lock digest 재검증
- absolute/drive/backslash/`..` path, duplicate/encrypted entry, symlink/hardlink 생성 거부
- input을 fresh attempt directory에 복사하고 child SDK가 다시 digest/size 검증
- output root는 새로 할당하고 symlink/traversal/ambiguous staged reference 거부
- output file과 Result Manifest의 role/schema/media type/size/SHA-256을 parent가 다시 검증
- network/socket, child process, ambient filesystem, link creation을 development guard로 거부
- minimal environment, no stdin, bounded stdout/stderr/control documents
- parent-enforced deadline/timeout과 cancellation grace 후 강제 종료

이 control은 Python code가 우회할 수 없는 production sandbox라고 주장하지 않는다. Production은 다음
OCI capability를 모두 runtime 밖에서 강제하고 attestation해야 한다. Local response policy는
`enforcement_attested=false`이며 non-root/read-only-root/no-new-privileges/syscall-profile을 거짓으로
표시하지 않는다.

### OCI-ready production plan

- digest-pinned image
- non-root user
- read-only root filesystem과 input mount
- ephemeral output mount
- network none
- no-new-privileges
- host socket 미노출
- syscall profile
- CPU/memory/PID quota

Kubernetes operator, scheduler, image registry, secret broker 구현은 T-18 범위가 아니다.

## 6. Tenant, worker, provenance

`RegistryPluginExecutionPlanner`는 worker security context의 organization/project와 claimed Job tenant가
다르면 package 조회 전에 거부한다. T-17 repository의 internal active lookup은 RLS transaction 안에서
plugin ID, exact version, package digest, `eligible` projection, immutable activation을 모두 요구한다.
Revoked/unavailable package와 다른 project row는 같은 opaque not-found로 처리한다.

`job_runner` service role에는 실행에 필요한 최소 `job.read`, `job.execute`, `plugin.read`,
`artifact.read`, `artifact.write`만 추가했다. Plugin submit/activate, review, release 권한은 없다.

Validated Result Manifest와 output commit은 T-10 committer port가 원자적으로 수행해야 한다. 성공은 모든
expected output이 있어야 한다. 실패/timeout/cancelled manifest도 provenance activity로 commit할 수 있지만,
부분 output은 `retain_on_failure`가 명시된 diagnostic output policy만 통과한다. Committer가 다른 manifest
digest를 반환하면 Attempt finalize 전에 fail closed한다.

## 7. PostgreSQL migration과 API 계약

T-18은 **새 migration이나 generic execution table을 추가하지 않는다**.

- durable Job/Attempt/Lease/Runner capability와 terminal manifest reference는 T-15 table을 재사용한다.
- package identity/schema/state/activation과 tenant RLS는 T-17 table을 재사용한다.
- T-17 repository에 RLS-bound active package lookup만 추가했다.
- authoritative artifact/object relation은 T-10 소유이므로 임시 FK/table/EAV를 만들지 않았다.

새 public HTTP endpoint도 없다. 내부 worker protocol만 추가했다. Public/packaged Job Spec 1.0에는
string/array/int64 bound를 명확히 했고, Result Manifest 1.0의 `non_production`은 boolean으로 확장했다.
Application service는 이 값이 실제 execution mode와 정확히 일치하는지 검증한다. SDK에 포함된 두 schema는
public contract와 JSON-equivalent인지 contract test로 고정한다. Platform HTTP contract version은 0.7.0이다.

## 8. 검증 범위

- SDK unit: descriptor/TCK matrix, input rehash, output bound, safe path, deterministic RNG,
  cancellation, deadline
- Application unit: tenant mismatch, active package/extension/config resolution, worker result/failure
  mapping, sanitized package error
- OCI unit: complete plan control과 하나의 capability라도 빠진 runtime의 fail-closed
- Subprocess integration: 일곱 extension type, staged input/output, seed reproducibility, timeout,
  cooperative cancellation
- Security regression: network, child process, context traversal, ambient read, symlink, oversized
  output, digest substitution, corrupt ZIP, unsafe archive path
- Result regression: schema-valid corrupt/missing output, execution-mode mismatch, failed partial-output
  retention policy
- PostgreSQL: exact digest active lookup, revoked package 차단, cross-project RLS
- Architecture/contract: core→reference/production implementation import 금지, public/SDK schema 동일성

## 9. 미결정 및 후속 경계

- T-09/T-10 object-store upload, scoped access token, materializer, atomic output/manifest commit
- T-13 typed provenance Entity/Activity/Agent relation과 T-16 reconciliation/outbox
- runner service credential 발급·회전, secret broker와 deployment composition
- production OCI runtime/vendor, image pull/cache, signature/trust root, SBOM/vulnerability/license policy
- per-tenant/job-class quota accounting과 operating-system resource enforcement
- runner contract minor-version support/deprecation window와 non-Python SDK TCK distribution

이 항목은 현재 계약에 가짜 구현이나 mutable placeholder로 넣지 않았다. 후속 task는 Job/Attempt와
Package의 immutable identity/digest를 유지한 채 port 뒤에 추가한다.
