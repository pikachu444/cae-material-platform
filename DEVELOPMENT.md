# CAE Material Platform 개발 가이드

이 문서는 현재 저장소를 로컬에서 실행하고 변경을 검증하는 절차만 다룹니다. 제품 사용법은
[사용자 가이드](docs/user-guide/index.md), 구조와 불변조건은 [문서 포털](docs/README.md)에서
확인하십시오.

## 1. 변경 전 확인

1. [AGENTS.md](AGENTS.md)의 필수 문서와 불변조건을 읽습니다.
2. [backlog](docs/13-delivery/backlog.md)에서 하나의 Task 또는 명확한 하위 범위를 선택합니다.
3. `git status --short --branch`로 사용자 변경을 확인하고 보존합니다.
4. contract를 바꾸는 작업은 adapter보다 OpenAPI/IR/schema를 먼저 수정합니다.
5. visual 작업은 제품 정책, reference 비교, viewport evidence와 screenshot manifest를 같은 변경에
   포함합니다.

Production 시험 표준, 재료 모델, optimizer, solver mapping과 validation threshold의 TBD를 임의로
결정하지 마십시오. synthetic `reference/non-production` adapter만 사용합니다.

## 2. 개발 환경

- Python 3.12와 [uv](https://docs.astral.sh/uv/)
- Node.js와 npm
- Docker Desktop/Engine과 Docker Compose
- Windows에서는 WSL 2 기반 Linux container 권장

```powershell
uv sync --all-groups
npm ci
```

## 3. 전체 demo 실행

가장 재현 가능한 실행 경로는 Compose입니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
```

`postgres`와 `api`가 healthy이고 `migrate`, `reference-plugins`, `seed`가 0으로 종료되어야 합니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Web은 <http://127.0.0.1:5173>, API는 <http://127.0.0.1:8000/api/v1>입니다. Demo mode에서는
브라우저가 제한된 local session을 자동으로 준비합니다. 사용자가 API 주소, Bearer token 또는 내부
identity 식별자를 입력하는 화면은 현재 제품 계약이 아닙니다.

전체 synthetic 흐름을 API에서 다시 확인합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml run --rm --no-deps seed `
  python scripts/verify_full_demo.py --api-base-url http://api:8000/api/v1
```

종료:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml down
```

`down -v`는 이 Compose project의 demo DB와 object-store volume을 삭제합니다. 필요한 evidence와
로그를 먼저 저장하고 synthetic local demo임을 확인한 경우에만 실행하십시오.

설치·port·migration·복구 문제는 [Compose 실행 가이드](deploy/compose/README.md)를 따릅니다.

## 4. 현재 제품 확인 순서

### Material 검색과 card 다운로드

1. `/materials`에서 DP780을 검색합니다.
2. 결과 row를 선택하고 Overview, Properties와 Curves를 확인합니다.
3. CAE Cards에서 OpenRadioss 또는 Abaqus native text를 미리 보고 내려받습니다.
4. Browse Tree에서 Database/Profile/Table/Folder/Record 탐색과 검색을 확인합니다.
5. Evidence에서 exact links, workflow와 기술 provenance를 확인합니다.

### Modeling

1. `/modeling`의 Data에서 Canonical JSON 또는 CSV/TSV/XLSX를 선택합니다.
2. channel, quantity semantics, 원본/정규화 단위를 확인합니다.
3. Process에서 crop/smoothing/resampling과 반복시험 통계를 검토합니다.
4. Fit에서 후보 response, residual과 extrapolation을 비교합니다.
5. Export에서 reviewed IR, mapping report, native card와 Library 저장을 확인합니다.

Recipe/Batch, Mapping Profile, full revision과 JSON definition은 Advanced에 있어야 하며 그래프를
영구적인 세 번째 inspector 열로 압축하지 않아야 합니다.

### Administration

우측 workspace menu에서 `/administration`을 엽니다. Database design은 Table, typed Attribute,
Layout, Subset과 exact-revision Link Type을 migration 없이 관리합니다. 일반 사용자의 전역 메뉴는
`Materials | Modeling | Activity`입니다.

## 5. 로컬 개발 프로세스

API와 worker를 Compose 밖에서 실행할 때 필요한 DSN과 identity는 개발 환경에서만 설정합니다.

```powershell
uv run uvicorn cmp.apps.api:app --host 127.0.0.1 --port 8000
uv run cmp-worker
npm run dev --workspace @cmp/web
```

실제 통합 검증은 Compose의 non-owner application role과 PostgreSQL RLS를 사용해야 합니다. 단위
테스트 성공을 tenant/security 검증으로 간주하지 마십시오.

자주 쓰는 명령:

```powershell
uv run ruff check .
uv run mypy --no-incremental
uv run pytest backend/tests/unit tests/architecture
uv run pytest tests/contracts
uv run pytest tests/integration
npm run build --workspace @cmp/web
npm run test:web
uv run cmp-check-user-guide --root .
```

GNU Make 사용 환경에서는 `make lint`, `make typecheck`, `make test`, `make web-build`,
`make web-test`, `make docs-screenshots`, `make ci`를 사용할 수 있습니다.

## 6. PostgreSQL integration gate

통합 테스트는 별도의 localhost-only, tmpfs-backed PostgreSQL을 사용합니다. Demo DB나 production
DB를 test DSN으로 지정하지 마십시오.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile test up -d postgres-test
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest -m postgresql tests/integration -ra
```

이 suite는 temporary database/role을 생성·삭제합니다. 0 failure, 0 skip이 기준이며 고정된 test
개수에 의존하지 않습니다.

## 7. 문서와 화면 변경

활성 문서와 역사 evidence를 섞지 않습니다.

- 문서 상태는 [documentation manifest](docs/documentation-manifest.yaml)에 등록합니다.
- 일반 사용자 UI 변경은 현재 가이드, 현재 screenshot manifest와 실제 PNG를 같은 commit에 둡니다.
- 현재 대표 PNG는 실행 중인 deterministic Compose demo에서 `make docs-capture`로
  `docs/user-guide/images/current`에 생성합니다.
- `apps/web/src/app.tsx`의 route/nav를 바꾸면 navigation contract도 갱신합니다.
- 현재 문서에는 archive screenshot을 사용하지 않습니다.
- visual acceptance는 1366×768, 1440×900, 가능하면 1920×1080에서 실제 브라우저로 확인합니다.

```powershell
make docs-capture
uv run cmp-check-user-guide --root .
```

스크린샷을 통과시키기 위해 manifest의 크기만 바꾸거나 golden을 무검토 갱신하지 마십시오. 제품
정책, reference comparison과 측정 evidence가 먼저입니다.

## 8. 데이터·보안 불변조건

- raw bytes와 released artifact는 immutable입니다.
- stable identity와 immutable revision을 분리합니다.
- run과 link는 `latest`가 아니라 exact revision을 참조합니다.
- 원본/정규화 단위와 quantity semantics를 함께 보존합니다.
- outlier 원본을 삭제하지 않습니다.
- derived entity는 input usage, generation activity와 agent를 가집니다.
- production solver card는 Material Model IR revision을 필요로 합니다.
- mapping은 exact/transformed/approximated/unsupported를 명시하고 unsupported를 차단합니다.
- organization/project authorization을 service와 database 양쪽에서 강제합니다.

상세 계약은 [requirements](docs/02-requirements/requirements.md),
[revision/provenance](docs/04-provenance/revision-and-provenance.md),
[security](docs/11-security/security-tenancy-audit.md)를 따릅니다.

## 9. 문제 진단

파괴적인 정리 전에 상태와 로그를 저장합니다.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
docker compose -f deploy/compose/docker-compose.demo.yml logs --no-color postgres migrate api seed web worker
```

기존 schema에 새 API/worker image를 먼저 띄우지 마십시오. schema 변경 시 migration image를 함께
build하고 `migrate` 성공 뒤 application service를 교체합니다. 포트 5173/8000/54329를 다른 process가
사용 중이면 해당 process의 소유를 확인한 뒤 중지하거나 port를 조정합니다.
