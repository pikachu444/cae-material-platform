# 구현 상태

승인된 제품/시각 구현 기준선: `55cfa62` (PR #156)입니다. repository 작업 시작점은 항상
`git pull --ff-only origin main`으로 얻는 최신 `main`입니다. 세부 구현 연대기는
[implementation history](docs/13-delivery/implementation-history.md)에 보존합니다.

## 제품 기준선

- 일반 사용자 메뉴: `Materials | Modeling | Activity`
- 기본 route: `/materials`
- Material Detail: `Overview | Properties | Curves | CAE Cards | Evidence`
- Modeling: `Data | Process | Fit | Export`; validation과 review/release는 Advanced의 별도 governed action이며 normal stage가 아니다. Activity에는 PR #144의 review queue와 PR #145의 exact Material/Solver Card request entry가 현재 제공된다. 남은 failed-job recovery, server receipt, release projection은 #160 범위다.
- Administration: role-gated Table/Attribute/Layout/Subset/Link Type 및 접근 관리
- legacy `/database`, `/catalog/*`, `/datasets/*`: deep-link compatibility

Search-first는 탐색 우선순위 변경입니다. Database/Profile/Table/Folder/Record Tree, typed Attribute,
Layout, Subset, exact-revision 양방향 Link Type과 workflow projection은 유지됩니다.

## 구현된 기준선

| 영역 | 현재 범위 |
| --- | --- |
| Materials | Browse 기본의 연속 explorer/result/datasheet workspace, server-scoped Material class 검색·result table, Browse Tree, 선택 문맥, 5영역 detail, direct card preview/download |
| Modeling | Data/Process/Fit의 184–210 px method→specimen Curves tree, Process/Fit process tree, shallow graph-adjacent control band, persistent dominant graph, Data/Process/Fit/Export; validation/review/release는 Advanced governed action이며 Activity review queue와 exact Material/Solver Card request entry는 current. failed-job recovery, server receipt, release projection은 #160에 남음 |
| Catalog | configurable Table/Attribute/Layout/Subset, Folder/Record tree, typed search·compare, exact Record links |
| Exchange | CSV/TSV/XLSX governed import, versioned Test Data JSON, Neutral Material JSON, deterministic packages |
| Engineering | public-equation reference metal/polymer/elastomer processing·fitting, IR promotion, mapping evidence |
| Governance | immutable review/release/artifact, provenance/audit, Activity 및 Advanced entry |
| Security | OIDC/JWT context, tenant/project authorization, PostgreSQL RLS, append-only audit |
| Operations | Compose demo, worker/jobs, observability, recovery/performance/security acceptance tools |

모든 engineering 수치와 solver 결과는 bounded synthetic `reference/non-production` 범위입니다.
Production 표준·plugin·solver correlation·validation threshold는 domain approval 전까지 완료로 간주하지
않습니다.

## Desktop UI delivery status

PR #124/DUI-06 completed the bounded Fit candidate decision → immutable Processing Output → Material
Model IR → Neutral Material → mapping preflight → native solver-card delivery chain on 2026-07-24.
DUI-01~06 are complete. UXC-02 now provides a v3 clearable session reducer, Data-first reset,
exact Material/State/Test Data session pins, downstream clear/stale/regenerate state and resumable
plot state. The normal shell is exactly `Data | Process | Fit | Export`; validation and review/release
are distinct governed Advanced actions, not implemented normal-stage destinations. PR #144의 Activity review
queue와 PR #145의 exact Material/Solver Card request entry는 current이며, failed-job recovery, server
receipt, release projection은 #160에 남는다. Export has no
current-session fallback. UXC-06B now carries server-verified Material/State/Test Run proof from a
qualified local-file Test Data revision into its Processing Output; historical and JSON-only rows keep
that proof null and remain blocked rather than inferred. UXC-01 has a completed server-scoped Materials Find vertical slice
(text/material-class/sort/page total and rows; no row enrichment N+1). Materials uses local
Browse/Filters/Subsets modes, and the compact result/context surface omits provider/evidence/validation/solver,
condition-aware Yield and Modeling-start projections until their governed query projections are defined. The remaining
governed query projection gaps and final product-level verification remain. The linked #157–#162
sequence below owns those follow-ups; Issue #119 automatic LLM review remains disabled.

## 핵심 보존 계약

- raw bytes와 released artifacts immutable
- stable identity와 immutable revision 분리
- run/link의 exact revision pin
- original/normalized unit와 quantity semantics 보존
- outlier 원본 비삭제와 adjudication 분리
- derived entity의 input/activity/agent provenance
- Material Model IR 기반 solver card
- exact/transformed/approximated/unsupported mapping과 fail-closed unsupported
- organization/project authorization의 service+database enforcement

## 검증 진입점

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
uv run pytest tests/contracts
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

전체 synthetic demo는 `make demo`, `make demo-verify` 또는 Compose 명령으로 확인합니다. PostgreSQL,
performance, security와 product-pilot gate는 [개발 가이드](DEVELOPMENT.md)와
[테스트 전략](docs/14-testing/test-strategy.md)을 따릅니다.

## 남은 범위

PR #125~#164는 merged scope이며 재구현 대상이 아닙니다. 다음 product-level 순서는
[#157 demo](https://github.com/pikachu444/cae-material-platform/issues/157) →
[#158 Fit](https://github.com/pikachu444/cae-material-platform/issues/158) →
[#159 Materials](https://github.com/pikachu444/cae-material-platform/issues/159) →
[#160 Governance/Activity](https://github.com/pikachu444/cae-material-platform/issues/160) →
[#161 DUI-09](https://github.com/pikachu444/cae-material-platform/issues/161) →
[#162 UXC-99](https://github.com/pikachu444/cae-material-platform/issues/162)입니다. #157은 clean
full-seed failure를, #162는 incoming package의 흡수 및 zero-inbound audit 뒤 삭제만을 다룹니다.
#119 automatic LLM review는 계속 비활성입니다.

- production tensile standard, material family/model, optimizer 및 solver qualification 결정
- domain-approved numeric reference, IR payload, solver mapping과 golden 승인
- 실제 identity provider/directory 및 운영 배포 정책 통합
- production plugin packaging과 confidential-data 운영 절차
- backlog의 미완료 Task와 pilot acceptance evidence

상세 우선순위와 완료 조건은 [backlog](docs/13-delivery/backlog.md), 의사결정이 필요한 항목은
[risks/open questions](docs/15-governance/risks-open-questions-decisions.md)를 기준으로 합니다.
