# 구현 상태

이 문서는 현재 코드가 제공하는 기능과 알려진 공백을 설명합니다. 작업 순서와 승인 기준선은
[현재 전달 backlog](docs/planning/backlog.md), 완료 이력은 Git과 병합된 GitHub issue/PR에서
확인합니다.

## 제품 진입점

- 일반 사용자 메뉴: `Materials | Modeling | Activity`
- 기본 route: `/materials`
- Material Detail: `Overview | Properties | Curves | CAE Cards | Evidence`
- Modeling: `Data | Process | Fit | Export`
- Administration: 권한이 있는 사용자에게 `Database | Format definitions | Records | Access` taskbar와
  Database/Profile/Table/Attribute/Layout/Subset/Link Type의 exact identity·revision 초안 관리·검증,
  canonical JSON 또는 checksummed source-set/ZIP Format Definition의 계획·명시적 적용·exact
  application read-back·검증 export, Folder/Record 단건·다건 등록과 접근 관리를 제공
- legacy `/catalog/*`, `/datasets/*`: deep-link 호환성 유지; 일반 사용자 시작점은 `/materials`

Search-first는 탐색 우선순위만 바꿉니다. 관리자는 Administration에서 Database/Profile/Table/Folder/Record와 typed
Attribute, Layout, Subset, exact-revision Link Type과 workflow projection은 유지됩니다. Validation과
review/release는 Modeling의 normal stage가 아니라 Advanced와 Activity의 별도 governed action입니다.

## 현재 기능

| 영역 | 구현 상태 |
| --- | --- |
| Materials | `/materials`의 Browse 기본 explorer/result/datasheet workspace, server-scoped 검색·정렬·pagination, 기존 Browse Tree 안의 Technical Data/Test Data/Simulation Data/Solver Cards와 각 데이터 항목, 선택 문맥, detail 5개 영역, 직접 연결의 category별 표시, exact-revision curve chart/channel·unit·deviation evidence, solver card preview/download; 내부 저장 구조는 Administration에서만 제공 |
| Modeling | exact Material/State/Test Data session pin, Data/Process/Fit/Export, Materials와 공유하는 curve definition/display adapter, Process의 exact source/profile preview·last-valid blocked recovery·immutable saved-result comparison, common-grid piecewise-linear/no-extrapolation alignment, append-only replicate outlier 포함·제외 판단과 exact Dataset/Test Run lineage, immutable pointwise mean/95% CI, calibration input scope exact pinning, 사용자가 고른 구간의 명시적 tensile toe OLS 보정·품질 경고 승인·exact Fit 입력, processed replicate `peak_engineering_stress_pa`의 선택형 Distribution analysis sheet와 Normal/Lognormal/Weibull 후보 비교·explicit selected model revision, processing·fitting, 선택 모델 저장, Material Model IR·Neutral·solver card 생성, upstream 변경에 따른 downstream clear/stale/regenerate |
| Activity | role-aware review queue, exact Material/Test Data/Solver Card request entry, Reviewer-only approval/change decisions, exact governed Material 또는 current Record 기반 Test Data projection, Processing Batch context/retry, browser recovery facts, and review-backed Record publication projection |
| Administration | Database/Profile과 configurable Table/Attribute/Layout/Subset/Link Type의 stable identity·immutable revision 관리와 검증, Format Definition upload-plan-confirm-apply-exact read-back-export, 서버가 파일 wrapper로 resolve하는 installed exact JSON format·strict JSON/package preview·파일별 진단·exact reference pin·원자 DRAFT batch save·source-aware JSON/CSV download, Database preview에서 exact Record로 이어지는 Folder/Record tree·typed search·compare·단건·다건 등록, exact Record links와 접근 관리; Database 정의의 일반 Publish 동작은 아직 구성되지 않음 |
| Catalog schema bundle | canonical bundle JSON, manifest+참조 JSON, checksummed source-set envelope 또는 ZIP의 exact immutable Artifact를 adapter 경계에서 검증하고 임의 개수 JSON Schema draft 2020-12 정의를 source set 내부에서만 resolve해 결정론적 plan 생성; Administrator 전용 화면과 API에서 exact SHA-256/`plan_fingerprint` 재검증, 원자 apply/publication, immutable application read-back, provenance와 checksum-verified current-state export |
| Common units | contract `1.0.0`의 8개 bounded dimension과 explicit Decimal conversion, stable identity/immutable revision Unit Profile API, exact profile/application trace를 Processing·Fit·Export와 PostgreSQL provenance에 연결 |
| Curve metadata | contract `1.0.0`의 channel role/quantity/original·normalized·display unit, typed scalar·pointwise deviation, exact Artifact/revision/source/calculation provenance; current Parquet metadata와 schema별 legacy adapter를 Dataset·Test Data·Processing·Statistics·Catalog·Materials·Modeling에 연결 |
| Exchange | CSV/TSV/XLSX governed import와 versioned Test Data JSON; DMA frequency-temperature sweep(temperature/frequency/storage/loss, optional tan delta)와 FLD(minor/major strain)의 atomic whole-file validation, actionable row/cell diagnostics, idempotent retry, exact Raw/Profile/Run/Dataset/Material provenance; Neutral Material JSON, deterministic package |
| Governance | immutable review/release/artifact, exact revision, provenance/audit, organization/project 권한 |
| Operations | versioned topology에서 생성되는 Compose demo, Docker·WSL 없는 Windows host PostgreSQL/API/worker/Node-free Web stack CLI, Windows 11 x64 user/machine scope offline bundle·checksum 검증·멱등 재설치·데이터 보존 제거·Private/Domain LocalSubnet Web 방화벽 경계, local/LAN URL·상태·로그, observability와 recovery·performance·security 검증 도구, Make/bash 호환 wrapper와 Linux full/Windows host-only CI가 공유하는 운영체제 중립 Python task CLI. PR CI는 명시적 base/head 변경 경로를 fail-closed `full`·`frontend`·`docs` mode로 분류하되 두 required check를 항상 유지하고, schedule/manual은 full을 실행합니다. clean full-demo는 preview에서 선택한 fit evidence와 metal manual necking override를 exact revision으로 보존하고, DP780 selected model review request 하나와 Materials의 solver card preview·검토 후 다운로드를 검증 |

Engineering 수치와 solver 결과는 bounded synthetic `reference/non-production` 범위입니다.
Production 표준, plugin, solver correlation과 validation threshold는 domain approval 전까지
완료로 간주하지 않습니다.

## 알려진 공백

- 관리자는 임의 개수의 JSON Schema 정의를 bundle로 검증하고 no-write plan을 만든 뒤
  **Administration → Format definitions**에서 정확한 version, source SHA-256, plan fingerprint와
  변경 개수를 확인해 적용할 수 있습니다. Apply는 current RLS snapshot을 lock 아래서 서버 재계획하고
  필요한 revision·publication·provenance·audit·outbox를 한 transaction으로 저장합니다. 화면은
  주소에 고정된 immutable application을 다시 읽고 checksum/provenance가 일치하는 export만 제공합니다. Stale
  plan은 재계획하며 User/Reviewer 접근, client-authored action, 부분 변경과 Current Record migration
  충돌을 차단합니다. #205의 `x-unit` handoff는 stable common unit ID만 검증하며 기본 Unit Profile을
  선택하지 않습니다. 예시 schema 이름과 개수는 제품 고정 형식이 아닙니다. 상세 순서는
  [#204~#216 통합 계획](docs/planning/schema-driven-material-integration-plan.md)과 backlog가 소유합니다.
- Unit Profile 관리용 frontend와 production solver 기본 profile은 없습니다. 기존 `kg_m_s`는
  `production_default=false`인 호환 계약이며 추가 solver unit system과 Template는 #213/#214가
  소유합니다. Profile-free 과거 revision과 solver-native bytes는 재작성하지 않습니다.
- Curve metadata가 없는 알 수 없는 과거 Artifact는 기존 값과 availability를 보존하되 채널·단위·편차나
  Fit eligibility를 추정하지 않습니다. Curve metadata adapter는 기존 통계 evidence를 설명할 뿐
  smoothing/alignment/resampling, 대표곡선 또는 승인된 Fit 입력을 만들지 않습니다.
- Scalar distribution은 exact processed replicate Selection의 `peak_engineering_stress_pa`에 승인된
  2-parameter MLE 후보와 AICc/AD bootstrap 비교를 선택형 Modeling 분석 sheet로 제공합니다. n<8,
  constant, unsupported support/quality는
  명시적 not-eligible이며 n 8–19는 경고합니다. Censored, mixture, Bayesian/hierarchical fitting과 자동
  production default는 없습니다. #211은 이미 구현된 common-grid piecewise-linear/no-extrapolation
  alignment, append-only inclusion/exclusion assessment와 exact Dataset/Test Run lineage, pointwise
  mean/95% CI immutable Artifact, calibration input scope exact pinning을 재사용·회귀검증합니다. 실제
  잔여는 pointwise p05/p95 representative revision, representative review/approval/invalidation과 승인된
  representative exact revision을 Fit에서 선택하는 연결입니다.
- Tensile toe compensation은 사용자가 지정한 linear estimation domain에
  `tensile.toe_zero_intercept@1.0.0` OLS를 적용해 strain 축만 평행 이동합니다. 원본 Test Data와 stress는
  바꾸지 않으며 R²·offset 경고를 승인해야 새 immutable Processing Output으로 저장할 수 있습니다.
  자동 toe 탐지, 장비 compliance 추정, production tensile standard나 acceptance threshold 선택은
  제공하지 않습니다.
- #158 Data/Process/Fit/Export production UI는 PR #183~#202에서 현재 화면에 연결했습니다.
  Administration 공개·복구 refinement는 #161, Definition Bundle 화면은 #208에서 연결했습니다.
  남은 Template/OIDC 화면은 각각 #214, #215에서 별도 검수합니다.
- #209의 DMA frequency-temperature sweep와 FLD governed Data 등록·canonical read-back·review
  projection 및 explicit-legacy `Hz`는 완료됐고, #246 Task 1A의 source-v2 adapter도 병합됐습니다.
  #246 Task 1B는 서버가 설치된 exact format revision을 resolve해 실제 JSON 파일을 strict 검증하고,
  파일별 JSON Pointer/위치 진단과 명시적 reference pin을 포함한 durable preview token을 발급하며,
  전체 파일을 한 PostgreSQL transaction에서 DRAFT Record batch로 저장합니다. 원본 bytes/name/MIME/length/SHA,
  binding·unit·curve provenance와 결정론적 source JSON/CSV download는 exact Record revision에 고정되고,
  publication은 기존 review 경계에 남습니다. 이 범위는 #342의 [PR #353](https://github.com/pikachu444/cae-material-platform/pull/353)에서
  fresh PostgreSQL/API/browser 검증, Full 독립 감수와 2026-08-28 제품 소유자 화면 승인을 통과했습니다.
  #341은 additive common-unit `1.1.0`에서 explicit `speed`의 `m/s`·`mm/s`·`mm/min`과 density의
  `tonne/mm3`를 구현하고 변경하지 않은 source-v2 apply/export/no-op을 닫았습니다. #343 Task 2B의
  [PR #356](https://github.com/pikachu444/cae-material-platform/pull/356)은 제품 코드를 추가하지 않고 현재 지원 경계를 확정합니다. governed import 계약과 Modeling 입력은
  `dma_frequency_temperature_sweep`만 지원하며 `dma_strain_sweep`은 선택지와 계약 열거값에서 제외되어
  명시적으로 지원되지 않습니다. source-v2 Record의 `Test Type: Strain Sweep` 값은 동적 형식으로
  검증·보존할 수 있는 데이터 값이지, canonical 처리나 점탄성 계산 지원을 뜻하지 않습니다.
  master curve·Prony·LinearViscoelastic IR의 production 입력·정책·수치 검증 확장은 #195가 소유하며,
  #246 완료만으로 구현됐다고 간주하지 않습니다. #344 Task 3+4의
  [PR #357](https://github.com/pikachu444/cae-material-platform/pull/357)은 #211·#213~#216의 실제 잔여를
  기존 이슈에 유지하고, 근거 없는 역할·optimizer·승인 단계·plugin·비동기 계산·경화식 확장을
  보류했으며 main `1dcd4c90ec8636bc66de46961cbb93a8392fda47`에서 #246을 완료했습니다. 현재 제품 작업은
  #195입니다.
- #195 polymer viscoelastic과 #196 elastomer hyperelastic/hyper-viscoelastic에는 bounded synthetic
  `reference/non-production` 계산·선택·IR/Neutral/export 기반과 각각의 current planning packet이 이미
  있습니다. #195의 다음 범위는 이 기반을 재작성하는 일이 아니라 production DMA/relaxation 입력 의미,
  독립 수치 reference와 acceptance, API 저장·reload, 실제 Modeling 사용자 흐름을 하나의 승인 packet으로
  확정하는 것입니다. 현재 reference 계산 결과와 화면은 production 검증 또는 UI 승인을 뜻하지 않습니다.
  #196의 deferred 잔여도 family별 production 계약이며 기존 packet의 `OPEN_DECISION`은 유지됩니다.
- #276은 직접 등록한 Simulation Data와 Modeling 생성 결과를 capability에 따라 무피팅 곡선 또는
  선택형 Fit/solver-card 경로로 잇는 후보 후속입니다. 현재 `배치 결정 대기`이며 native parent와
  #117 실행 순서는 지정되지 않았습니다.
- Materials의 provider/evidence source, condition-aware property, validation·solver readiness는
  실제 governed query projection이 없는 상태에서 추론하지 않습니다.
- Activity의 실패 작업 복구와 review-backed Record publication은 #160 범위입니다. Authoritative
  delivery receipt producer와 full release package projection은 아직 명시적으로 준비되지 않았습니다.
- #162의 Hyper-V Ubuntu VM은 사용자 제품 설치 방식이 아니라 모든 제품 기능이 병합된 뒤 수행하는
  별도 최종 통합검증 harness입니다. `docs/_incoming/2026-07-24-organic-ux-update/`의 유효 내용 흡수와
  삭제도 이 최종 검증 범위에서만 수행합니다.
- #321/#322~#324로 Docker·WSL 없는 Windows 11 native host와 offline installer 코드 경로가
  `main`에 생겼습니다. 다만 clean-PC offline Demo 전체 흐름, 실제 machine-scope 방화벽·LAN 접속,
  #215 뒤 Server OIDC 검증이 남아 #321은 독립적으로 OPEN이며 #117 순서를 바꾸거나 #162 Ubuntu
  harness를 대체하지 않습니다.
- 실제 identity provider/directory, 운영 object storage/KMS/WORM, credential rotation/outage,
  external receiver와 장시간 endurance는 production 환경 수용이 남아 있습니다.
- Server stack은 Demo identity·seed와 누락된 external auth/secret을 fail-closed로 거부합니다. 다른 PC
  브라우저의 실제 OIDC Code+PKCE login/callback은 별도 소유 이슈 #215가 아직 미구현이므로 Server
  profile을 시작하지 않으며, Demo token이나 수동 bearer 입력으로 우회하지 않습니다.

## 검증 진입점

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
uv run cmp-stack --profile demo --runtime compose doctor
uv run cmp-stack --profile demo --runtime host --postgres-bin <PostgreSQL-16-bin> doctor
uv run python scripts/build_windows_offline_bundle.py --profile demo --output-dir <bundle-dir>
uv run python scripts/repository_tasks.py ci --host-only
uv run pytest tests/contracts
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

전체 synthetic demo는 `make demo`, `make demo-verify` 또는 Compose 명령으로 확인합니다.
PostgreSQL, performance, security와 production acceptance는 [개발 가이드](DEVELOPMENT.md)와
[테스트 전략](docs/testing/test-strategy.md)을 따릅니다. 의사결정이 필요한 항목은
[위험·미결정 사항](docs/planning/risks-open-questions-decisions.md)에 기록합니다.
