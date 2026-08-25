# 구현 상태

이 문서는 현재 코드가 제공하는 기능과 알려진 공백을 설명합니다. 작업 순서와 승인 기준선은
[현재 전달 backlog](docs/13-delivery/backlog.md), 완료 이력은 Git과 병합된 GitHub issue/PR에서
확인합니다.

## 제품 진입점

- 일반 사용자 메뉴: `Materials | Modeling | Activity`
- 기본 route: `/materials`
- Material Detail: `Overview | Properties | Curves | CAE Cards | Evidence`
- Modeling: `Data | Process | Fit | Export`
- Administration: 권한이 있는 사용자에게 Database/Profile과 Table/Attribute/Layout/Subset/Link Type의
  초안·검증·발행, canonical JSON 또는 checksummed source-set/ZIP Schema Definition Bundle의
  계획·명시적 적용·read-back·검증 export, Folder/Record 단건·다건 등록과 접근 관리를 제공
- legacy `/catalog/*`, `/datasets/*`: deep-link 호환성 유지; 일반 사용자 시작점은 `/materials`

Search-first는 탐색 우선순위만 바꿉니다. 관리자는 Administration에서 Database/Profile/Table/Folder/Record와 typed
Attribute, Layout, Subset, exact-revision Link Type과 workflow projection은 유지됩니다. Validation과
review/release는 Modeling의 normal stage가 아니라 Advanced와 Activity의 별도 governed action입니다.

## 현재 기능

| 영역 | 구현 상태 |
| --- | --- |
| Materials | `/materials`의 Browse 기본 explorer/result/datasheet workspace, server-scoped 검색·정렬·pagination, 기존 Browse Tree 안의 Technical Data/Test Data/Simulation Data/Solver Cards와 각 데이터 항목, 선택 문맥, detail 5개 영역, 직접 연결의 category별 표시, exact-revision curve chart/channel·unit·deviation evidence, solver card preview/download; 내부 저장 구조는 Administration에서만 제공 |
| Modeling | exact Material/State/Test Data session pin, Data/Process/Fit/Export, Materials와 공유하는 curve definition/display adapter, Process의 exact source/profile preview·last-valid blocked recovery·immutable saved-result comparison, 사용자가 고른 구간의 명시적 tensile toe OLS 보정·품질 경고 승인·exact Fit 입력, processed replicate `peak_engineering_stress_pa`의 선택형 Distribution analysis sheet와 Normal/Lognormal/Weibull 후보 비교·explicit selected model revision, processing·fitting, 선택 모델 저장, Material Model IR·Neutral·solver card 생성, upstream 변경에 따른 downstream clear/stale/regenerate |
| Activity | role-aware review queue, exact Material/Test Data/Solver Card request entry, Reviewer-only approval/change decisions, exact governed Material 또는 current Record 기반 Test Data projection, Processing Batch context/retry, browser recovery facts, and review-backed Record publication projection |
| Administration | Database/Profile과 configurable Table/Attribute/Layout/Subset/Link Type의 revision 관리·발행, Definition Bundle upload-plan-confirm-apply-read-back-export, Folder/Record tree, typed search·compare, 단건·다건 등록, exact Record links와 접근 관리 |
| Catalog schema bundle | canonical bundle JSON, manifest+참조 JSON, checksummed source-set envelope 또는 ZIP의 exact immutable Artifact를 adapter 경계에서 검증하고 임의 개수 JSON Schema draft 2020-12 정의를 source set 내부에서만 resolve해 결정론적 plan 생성; Administrator 전용 화면과 API에서 exact SHA-256/`plan_fingerprint` 재검증, 원자 apply/publication, immutable application read-back, provenance와 checksum-verified current-state export |
| Common units | contract `1.0.0`의 8개 bounded dimension과 explicit Decimal conversion, stable identity/immutable revision Unit Profile API, exact profile/application trace를 Processing·Fit·Export와 PostgreSQL provenance에 연결 |
| Curve metadata | contract `1.0.0`의 channel role/quantity/original·normalized·display unit, typed scalar·pointwise deviation, exact Artifact/revision/source/calculation provenance; current Parquet metadata와 schema별 legacy adapter를 Dataset·Test Data·Processing·Statistics·Catalog·Materials·Modeling에 연결 |
| Exchange | CSV/TSV/XLSX governed import와 versioned Test Data JSON; DMA frequency-temperature sweep(temperature/frequency/storage/loss, optional tan delta)와 FLD(minor/major strain)의 atomic whole-file validation, actionable row/cell diagnostics, idempotent retry, exact Raw/Profile/Run/Dataset/Material provenance; Neutral Material JSON, deterministic package |
| Governance | immutable review/release/artifact, exact revision, provenance/audit, organization/project 권한 |
| Operations | versioned topology에서 생성되는 Compose demo, Docker·WSL 없는 Windows host PostgreSQL/API/worker/Node-free Web stack CLI, Windows 11 x64 user/machine scope offline bundle·checksum 검증·멱등 재설치·데이터 보존 제거·Private/Domain LocalSubnet Web 방화벽 경계, local/LAN URL·상태·로그, observability와 recovery·performance·security 검증 도구, Make/bash 호환 wrapper와 Linux full/Windows host-only CI가 공유하는 운영체제 중립 Python task CLI. clean full-demo는 preview에서 선택한 fit evidence와 metal manual necking override를 exact revision으로 보존하고, DP780 selected model review request 하나와 Materials의 solver card preview·검토 후 다운로드를 검증 |

Engineering 수치와 solver 결과는 bounded synthetic `reference/non-production` 범위입니다.
Production 표준, plugin, solver correlation과 validation threshold는 domain approval 전까지
완료로 간주하지 않습니다.

## 알려진 공백

- 관리자는 임의 개수의 JSON Schema 정의를 bundle로 검증하고 no-write plan을 만든 뒤
  **Administration → Definition bundles**에서 정확한 version, source SHA-256, plan fingerprint와
  변경 개수를 확인해 적용할 수 있습니다. Apply는 current RLS snapshot을 lock 아래서 서버 재계획하고
  필요한 revision·publication·provenance·audit·outbox를 한 transaction으로 저장합니다. 화면은
  immutable application을 다시 읽고 checksum/source evidence가 일치하는 export만 제공합니다. Stale
  plan은 재계획하며 User/Reviewer 접근, client-authored action, 부분 변경과 Current Record migration
  충돌을 차단합니다. #205의 `x-unit` handoff는 stable common unit ID만 검증하며 기본 Unit Profile을
  선택하지 않습니다. 예시 schema 이름과 개수는 제품 고정 형식이 아닙니다. 상세 순서는
  [#204~#216 통합 계획](docs/12-roadmap/schema-driven-material-integration-plan.md)과 backlog가 소유합니다.
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
  production default는 없고, representative envelope와 approved Fit input은 다음 #211 범위입니다.
- Tensile toe compensation은 사용자가 지정한 linear estimation domain에
  `tensile.toe_zero_intercept@1.0.0` OLS를 적용해 strain 축만 평행 이동합니다. 원본 Test Data와 stress는
  바꾸지 않으며 R²·offset 경고를 승인해야 새 immutable Processing Output으로 저장할 수 있습니다.
  자동 toe 탐지, 장비 compliance 추정, production tensile standard나 acceptance threshold 선택은
  제공하지 않습니다.
- #158 Data/Process/Fit/Export production UI는 PR #183~#202에서 현재 화면에 연결했습니다.
  Administration 공개·복구 refinement는 #161, Definition Bundle 화면은 #208에서 연결했습니다.
  남은 Template/OIDC 화면은 각각 #214, #215에서 별도 검수합니다.
- #209의 DMA frequency-temperature sweep와 FLD는 governed Data 등록·canonical read-back·review
  projection까지만 연결합니다. `dma_strain_sweep`, source-v2 전체 adapter, 추가 unit/bundle adapter와
  DMA→Prony/master curve/Material Model IR 연결은 #246 범위입니다.
- Materials의 provider/evidence source, condition-aware property, validation·solver readiness는
  실제 governed query projection이 없는 상태에서 추론하지 않습니다.
- Activity의 실패 작업 복구와 review-backed Record publication은 #160 범위입니다. Authoritative
  delivery receipt producer와 full release package projection은 아직 명시적으로 준비되지 않았습니다.
- `docs/_incoming/2026-07-24-organic-ux-update/`의 유효 내용 흡수와 삭제는 #162 범위입니다.
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
[테스트 전략](docs/14-testing/test-strategy.md)을 따릅니다. 의사결정이 필요한 항목은
[위험·미결정 사항](docs/15-governance/risks-open-questions-decisions.md)에 기록합니다.
