# 구현 상태

이 문서는 현재 코드가 제공하는 기능과 알려진 공백을 설명합니다. 작업 순서와 승인 기준선은
[현재 전달 backlog](docs/13-delivery/backlog.md), 완료 이력은 Git과 병합된 GitHub issue/PR에서
확인합니다.

## 제품 진입점

- 일반 사용자 메뉴: `Materials | Modeling | Activity`
- 기본 route: `/materials`
- Material Detail: `Overview | Properties | Curves | CAE Cards | Evidence`
- Modeling: `Data | Process | Fit | Export`
- Administration: 권한이 있는 사용자에게 Table/Attribute/Layout/Subset/Link Type과 접근 관리 제공
- legacy `/database`, `/catalog/*`, `/datasets/*`: deep-link 호환성 유지

Search-first는 탐색 우선순위만 바꿉니다. Database/Profile/Table/Folder/Record Tree, typed
Attribute, Layout, Subset, exact-revision Link Type과 workflow projection은 유지됩니다. Validation과
review/release는 Modeling의 normal stage가 아니라 Advanced와 Activity의 별도 governed action입니다.

## 현재 기능

| 영역 | 구현 상태 |
| --- | --- |
| Materials | Browse 기본의 explorer/result/datasheet workspace, server-scoped Material class 검색·정렬·pagination, Browse Tree, 선택 문맥, detail 5개 영역, solver card preview/download |
| Modeling | exact Material/State/Test Data session pin, Data/Process/Fit/Export, processing·fitting, 선택 모델 저장, Material Model IR·Neutral·solver card 생성, upstream 변경에 따른 downstream clear/stale/regenerate |
| Activity | review queue, Material/Solver Card 요청 진입, Reviewer 승인·반려. failed-job recovery, server receipt와 release projection은 아직 없음 |
| Administration | configurable Table/Attribute/Layout/Subset/Link Type, Folder/Record tree, typed search·compare, exact Record links와 접근 관리 |
| Exchange | CSV/TSV/XLSX governed import, versioned Test Data JSON, Neutral Material JSON, deterministic package |
| Governance | immutable review/release/artifact, exact revision, provenance/audit, organization/project 권한 |
| Operations | Compose demo, worker/job, observability, recovery·performance·security 검증 도구. clean full-demo는 preview에서 선택한 fit evidence와 metal manual necking override를 exact revision으로 보존하고, DP780 selected model review request 하나와 Materials의 solver card preview·검토 후 다운로드를 검증 |

Engineering 수치와 solver 결과는 bounded synthetic `reference/non-production` 범위입니다.
Production 표준, plugin, solver correlation과 validation threshold는 domain approval 전까지
완료로 간주하지 않습니다.

## 알려진 공백

- production UI는 PR #156 기능 기준선이며, PR #170의 승인 target은 아직 #158부터 #161까지
  화면별로 React에 이식해야 합니다.
- Materials의 provider/evidence source, condition-aware property, validation·solver readiness는
  실제 governed query projection이 없는 상태에서 추론하지 않습니다.
- Activity의 실패 작업 복구, delivery receipt와 release projection은 #160 범위입니다.
- `docs/_incoming/2026-07-24-organic-ux-update/`의 유효 내용 흡수와 삭제는 #162 범위입니다.
- 실제 identity provider/directory, 운영 object storage/KMS/WORM, credential rotation/outage,
  external receiver와 장시간 endurance는 production 환경 수용이 남아 있습니다.

## 검증 진입점

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
uv run pytest tests/contracts
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

전체 synthetic demo는 `make demo`, `make demo-verify` 또는 Compose 명령으로 확인합니다.
PostgreSQL, performance, security와 production acceptance는 [개발 가이드](DEVELOPMENT.md)와
[테스트 전략](docs/14-testing/test-strategy.md)을 따릅니다. 의사결정이 필요한 항목은
[위험·미결정 사항](docs/15-governance/risks-open-questions-decisions.md)에 기록합니다.
