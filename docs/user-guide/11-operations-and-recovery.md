# 운영 상태 확인과 격리 복구 드릴

이 문서는 Docker demo의 관측성과 복구 기능을 확인하는 운영자용 절차입니다. 재료시험 원본이나
발행 revision을 직접 수정하지 않으며, 복구 드릴은 실행 중인 `cmp` 데이터베이스를 교체하지 않습니다.

## Format definitions 적용 복구

Administrator가 **Administration → Format definitions**에서 작업할 때는 source Artifact와 서버가
만든 plan이 복구 경계입니다. 화면에 실패가 표시되면 다음 순서로 처리합니다.

1. **Support reference**를 기록합니다. 이 correlation ID만 로그 검색에 사용하고 JSON 원문, token,
   organization/project 식별자나 request body를 지원 채널에 복사하지 않습니다.
2. 업로드 또는 plan 실패라면 선택한 파일과 진단 위치·remediation을 확인합니다. 원본 Artifact를
   수정하지 말고 고친 JSON을 새 source Artifact로 올려 새 plan을 만듭니다.
   이전 요청이 끝난 뒤 **Replace files**로 source를 교체합니다. 이 동작은 이전 plan과
   복구 좌표를 함께 비우며, 진행 중인 upload·plan·read-back 결과와 새 파일을 섞지 않습니다.
3. `stale plan`이면 Apply를 재전송하지 않습니다. **Plan again**으로 현재 Catalog 기준의 fingerprint와
   action을 다시 받고, 변경 개수와 영향을 처음부터 검토합니다.
4. Apply 응답 이후 연결이 끊겼다면 같은 내용을 다시 적용하려 하지 말고, 화면을 새로고침해 저장된
   application 좌표로 immutable read-back을 먼저 실행합니다. application 결과가 있으면 그것이 적용
   여부의 권위 있는 증거입니다.
5. Export checksum, ETag, Digest 또는 source evidence가 맞지 않으면 파일을 사용하거나 배포하지
   않습니다. Support reference와 application ID로 서버 응답을 조사하고 새 export를 요청합니다.

부분 성공을 가정하거나 Catalog current pointer를 직접 되돌리지 않습니다. 선택한 정의 파일에 없는 기존 정의와
Record는 적용 대상이 아니며, migration-required 진단은 별도 승인된 migration 작업으로 해결합니다.
User와 Reviewer가 apply/read-back/export에 접근했다면 403이어야 하며, 성공 응답은 권한 회귀로
취급합니다.

## API와 worker 상태 확인

1. 서비스를 실행하고 `http://127.0.0.1:5173`에서 local demo identity로 연결합니다.
2. 상단 **Governance**를 엽니다.
3. **API observability**에서 전체 request/5xx/active 수와 route-template별 요청 수, 평균 latency,
   p95 bucket 상한을 확인합니다.
4. 새 상태가 필요하면 **Refresh snapshot**을 누릅니다.

이 패널은 `audit.read`가 있어야 열립니다. URL, query, header, request body, 원본 시험값, credential과
tenant 식별자는 API 응답이나 application log에 넣지 않습니다. 여러 API/worker를 합친 장기 추세는
OTLP backend가 권위 있는 출처이며 이 화면은 한 API process의 bounded snapshot입니다.


Collector가 받은 trace/metric과 Prometheus 형식 metric은 다음으로 확인합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml logs otel-collector
Invoke-WebRequest http://127.0.0.1:8889/metrics
```

## 운영 규모 성능 게이트

일반 demo의 2 MiB 검사는 빠른 회귀용입니다. 10,000 Material과 2 GiB object 검사는 별도 isolated
PostgreSQL/object volume에서만 실행하십시오. 기존 원본이나 revision을 삭제하지 않고 deterministic
synthetic Material revision과 실제 multipart Ingestion Event를 추가하므로 실행 전 명시적
acknowledgement가 필요합니다. 전체 명령과 안전장치는
[`deploy/performance/README.md`](../../deploy/performance/README.md)에 있습니다.

성공 시 **Materials** 검색 결과의 전체 개수가 현재 권한 범위의 Material 수를 표시하고, canonical
report의 `production_scale_accepted`가 `true`여야 합니다. 2026-07-16 기준 검증값은 10,000개
Material, Catalog p95 182.128 ms, 2 GiB/32-part upload 22.999 MiB/s, peak Python allocation
67,164,359 bytes입니다. report SHA-256은
`96d75ca787695ad5848b0b65562554a93f8aa63dd204b82d92e159f723cef481`입니다.


이 결과는 장시간 soak, API/worker/PostgreSQL/object-storage 중단·복구, object lock/KMS/retention을
대체하지 않습니다. 장애 주입 중에도 이미 발행되거나 커밋된 revision과 object digest가 바뀌지
않는지를 별도 gate에서 확인해야 합니다.

## Mixed-workload 장애 드릴

다음 명령은 10,000 Material 구성에서 Catalog, Bundle 목록, health 요청을 지속하면서 PostgreSQL을
pause하고 API, worker, web을 순서대로 stop/start합니다. 서비스 중단을 수반하므로 공유 또는 운영
환경에 실행하지 마십시오.

```powershell
uv run cmp-soak-fault-acceptance `
  --base-url http://127.0.0.1:18000/api/v1 `
  --web-url http://127.0.0.1:5173 `
  --soak-seconds 300 `
  --minimum-materials 10000 `
  --acknowledge-service-disruption
```

실패하거나 Ctrl+C로 종료해도 tool은 자신이 pause/stop한 서비스를 역순으로 unpause/start합니다.
종료 후 아래 항목을 확인하십시오.

- `faults[*].passed: true`, 각 `recovery_seconds`가 60초 이하
- `workload.ordinary_failures: 0`; 장애 창의 실패는 별도 집계
- 연산별 `ordinary_latency.p95_ms`가 2,000 ms 미만
- `resources.passed: true`
- `invariants.after_catalog.total_count`가 시작값과 같음
- Bundle ID, size와 SHA-256이 시작값과 같음

2026-07-16 reference run은 총 373.361256초, 3,243 samples, 장애 밖 오류 0건으로 통과했습니다.
report SHA-256은
`d68253e7ce75528a0f807b945f98019e37f55052b2f8457d54076ff6e85f535c`입니다. 현재 object storage는
API/worker가 공유하는 local volume이므로 이 결과를 독립 object-storage 장애, object lock/KMS 또는
overnight endurance 검증으로 해석하지 마십시오.

## 격리 복구 드릴

다음 명령은 PostgreSQL custom dump를 만들고 무작위 이름의 임시 DB에 복원합니다. immutable object는
별도 snapshot 폴더에 복사해 크기와 SHA-256을 검사합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile operations run --rm restore-drill
```

성공 보고서는 `.cache/restore-drill/<drill-id>/report.json`에 남습니다. 다음 필드를 확인하십시오.

- `status: passed`, `counts_match: true`
- `raw_assets_sampled == raw_assets_verified`
- `objects_sampled == objects_verified`
- `dangling_lineage_edges: 0`
- Release가 있으면 `release_artifacts_mismatched: 0`; 없으면
  `release_sample_status: not_present_in_source`
- `duration_seconds`가 승인된 RTO 안에 있는지

명령은 생성한 임시 DB만 삭제합니다. 운영 acceptance에는 versioned object storage, object lock,
KMS/retention 권한, scheduled backup과 실제 승인 Release를 포함한 별도 드릴이 필요합니다.
## Product-pilot acceptance

The operator can run one read-only acceptance after the demo bootstrap and worker are healthy. It
does not create or revise user records.

```powershell
$env:CMP_PRODUCT_PILOT_POSTGRES_DSN = `
  "postgresql://cmp_owner:cmp_owner_development_only@127.0.0.1:54329/cmp"
uv run cmp-product-pilot-acceptance
```

Success means the composed PostgreSQL service contains all three reference user paths (Steel,
Polymer and Elastomer), their promoted solver-neutral IR evidence, the required downloadable
Abaqus/OpenRadioss cards, and a checksum-valid 22-component Bulk Export ZIP. It does not mean that
the reference material parameters are approved engineering data, that a solver job was executed,
or that external KMS/HSM/WORM services have passed acceptance.
