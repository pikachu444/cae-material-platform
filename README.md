# CAE Material Platform

시험 원본부터 재료 모델, CAE solver card까지 exact revision과 provenance를 유지하며 관리하는
재료 정보·모델링 플랫폼입니다. 일반 사용자는 기존 Material을 먼저 검색하고 검토한 뒤 native
solver card를 바로 내려받습니다. 적합한 결과가 없을 때만 시험 데이터를 Modeling으로 가져와
처리·fitting·export합니다.

> 현재 저장소의 수치 모델, fixture와 solver mapping은 공개식 기반의
> `reference/non-production` 범위입니다. 승인된 재료값, 생산용 constitutive model 또는 solver
> qualification을 대신하지 않습니다.

![Materials 검색과 선택 문맥](docs/user-guide/images/current/materials-search-1440x900.png)

![그래프 중심 Modeling Fit](docs/user-guide/images/current/modeling-fit-1440x900.png)

## 핵심 사용 흐름

### 기존 Material에서 solver card 받기

`Materials 검색 → 결과 비교 → Material 상세 → CAE Cards → preview/download`

- 이름·grade, family, 제조사/source, 수치 범위, solver와 release 상태로 검색합니다.
- Browse Tree에서 `Database → Profile → Table → Folder → Record` 계층을 탐색합니다.
- 상세의 `Overview | Properties | Curves | CAE Cards | Evidence`에서 Layout 기반 데이터를 봅니다.
- 선택한 Material 문맥을 유지한 채 Abaqus `.inp` 또는 OpenRadioss `.rad`를 미리 보고 받습니다.

### 시험 데이터에서 새 card 만들기

`Modeling Data → Process → Fit → Export → Material Library 저장`

- Canonical Test Data JSON 또는 승인형 CSV/TSV/XLSX 입력을 사용합니다.
- channel, quantity semantics와 원본/정규화 단위를 명시적으로 확인합니다.
- graph-centered workbench에서 처리 단계, 후보 응답, residual과 extrapolation을 검토합니다.
- Material Model IR을 거쳐 mapping 상태를 확인한 뒤 native card와 Neutral Material JSON을 받습니다.

## 주요 기능

- 검색, typed facet/range, saved Subset, 다중 Record·revision 비교
- Database/Profile/Table/Folder/Record Tree와 keyboard 탐색
- migration 없는 Table, Attribute, Layout, Subset, Link Type 관리
- text, integer, scalar, boolean, date/time, quantity, table, curve, file, Record reference
- exact-revision 양방향 Record link와 Material-to-card workflow
- immutable raw/released artifact, stable identity/revision 분리, derived-data provenance
- CSV/TSV/XLSX 및 versioned Canonical Test Data JSON import/export
- explicit processing, fitting candidate·residual 비교, Material Model IR 승격
- exact/transformed/approximated/unsupported solver mapping과 native card preview/download
- role-gated Administration, Activity, audit·release·bundle 고급 흐름

## 5분 로컬 실행

필수 도구는 Git, Docker Desktop(Compose 포함)입니다. 저장소 루트에서 실행합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
```

`postgres`와 `api`가 healthy이고 `migrate`, `reference-plugins`, `seed`가 0으로 종료되면
<http://127.0.0.1:5173>을 엽니다. Demo user session은 자동으로 준비되며 API URL이나 토큰을 입력하지
않습니다. API health는 <http://127.0.0.1:8000/api/v1/health>에서 확인할 수 있습니다.

첫 확인 시나리오:

1. `/materials`에서 `DP780`을 검색합니다.
2. 결과를 선택해 주요 물성과 대표 curve를 확인합니다.
3. **CAE Cards**에서 OpenRadioss native text를 미리 봅니다.
4. `.rad`를 내려받습니다.
5. **Browse Tree**를 열어 같은 Record의 Related/Workflow/Evidence를 확인합니다.
6. 카드가 없을 때만 **Modeling → Data**로 이동해 JSON 또는 CSV/XLSX를 등록합니다.

종료는 다음 명령을 사용합니다. `-v`는 synthetic demo volume을 영구 삭제하므로 필요한 경우에만
사용하십시오.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml down
```

Windows/WSL 설치와 장애 진단은 [Compose 실행 가이드](deploy/compose/README.md)를 참고하십시오.

## 전역 화면

| 화면 | 역할 |
| --- | --- |
| `Materials` | 검색·필터·비교, Browse Tree, 5영역 datasheet, 직접 card 다운로드 |
| `Modeling` | Data, Process, Fit, Export와 Advanced Recipe/Batch/JSON |
| `Activity` | 최근 작업, 검토·release, 고급 job/bundle 진입 |
| `Administration` | role-gated Table/Attribute/Layout/Subset/Link Type 및 접근 관리 |

기존 `/database`, `/catalog/*`, `/datasets/*` route는 deep-link 호환을 위해 남아 있지만 일반 사용자의
주 메뉴는 아닙니다. UUID, hash, full revision, classification, Mapping Profile JSON과 provenance graph는
Evidence, Advanced 또는 Administration에서 확인합니다.

## 구조

```text
apps/web            React/Vite engineering workbench
apps/api            protected HTTP application
backend/src/cmp     domain, service, adapters, workers and tools
contracts           OpenAPI, event, JSON and IR contracts
plugins             isolated reference/production plugin boundaries
deploy              local Compose and deployment assets
docs                product, domain, architecture, guides and evidence
tests               unit, contract, integration, migration and security tests
```

핵심 경계는 PostgreSQL의 tenant/RLS·immutable revision 모델, content-addressed artifact storage,
durable jobs, isolated plugins, Material Model IR입니다. 자세한 설계는
[시스템 아키텍처](docs/05-architecture/system-architecture.md)와
[canonical domain model](docs/03-domain/canonical-domain-model.md)을 참고하십시오.

## 개발과 검증

Python 3.12, `uv`, Node.js/npm을 사용합니다.

```powershell
uv sync --all-groups
npm ci
uv run pytest tests/contracts
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

전체 명령과 PostgreSQL gate는 [개발 가이드](DEVELOPMENT.md), 테스트 범위는
[테스트 전략](docs/14-testing/test-strategy.md)을 따릅니다. 구현을 변경하기 전 [AGENTS.md](AGENTS.md)와
해당 backlog Task를 먼저 읽으십시오.

## 문서

- [문서 포털과 상태 분류](docs/README.md)
- [사용자 가이드](docs/user-guide/index.md)
- [관리자 가이드](docs/admin-guide/index.md)
- [요구사항](docs/02-requirements/requirements.md)
- [revision과 provenance](docs/04-provenance/revision-and-provenance.md)
- [API·event·job 계약](docs/08-contracts/api-events-jobs.md)
- [security·tenancy·audit](docs/11-security/security-tenancy-audit.md)
- [현재 구현 상태](IMPLEMENTATION_STATUS.md)
- [backlog](docs/13-delivery/backlog.md)

이 저장소는 private 개발 저장소입니다. 실제 기밀 시험 데이터, production credential 또는 승인되지
않은 solver 자료를 commit하지 마십시오.
