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

Clone 후 versioned local pre-push hook을 설치하고 검증합니다. 기존 custom `core.hooksPath`가 있으면
installer가 덮어쓰지 않습니다.

```powershell
uv run python scripts/install_git_hooks.py --root .
uv run python scripts/install_git_hooks.py --root . --check
```

Codex project hook은 `/hooks`에서 내용을 확인하고 trust합니다. 자동 publication hook은 모델을
호출하지 않고 결정적 검사만 수행합니다. 비용이 드는 독립 리뷰는 별도 승인을 받은 경우에만
명시적으로 실행합니다. 현재 상태와 남은 설계 작업은
[pre-publish 게이트](docs/14-testing/codex-pre-publish-review.md)를 따릅니다.

Production 시험 표준, 재료 모델, optimizer, solver mapping과 validation threshold의 TBD를 임의로
결정하지 마십시오. synthetic `reference/non-production` adapter만 사용합니다.

## 2. 개발 환경

- Python `3.12.14`
- [uv](https://docs.astral.sh/uv/) `0.12.5`
- Node.js `24.19.0` LTS와 npm `11.17.0`
- full integration gate용 Docker Desktop/Engine과 Docker Compose
- Windows에서 container를 사용할 때는 WSL 2 기반 Linux container 권장

`.python-version`과 `.node-version`이 로컬 개발 기준을 기록합니다. 먼저 설치된 도구 버전을
확인한 뒤 잠금 파일을 바꾸지 않는 방식으로 환경을 준비합니다.

```powershell
uv --version
node --version
npm --version
uv python install
uv sync --all-groups --locked
npm ci --workspaces --include-workspace-root
uv run python scripts/check_development_environment.py
```

`uv sync`는 저장소의 `.venv`를 자동으로 만들고 `uv.lock`의 패키지를 설치합니다. 별도로 가상환경을
활성화하지 않아도 `uv run ...`이 이 환경을 사용합니다. `.venv`와 `node_modules`는 각 컴퓨터에만
있고 Git에 저장하지 않습니다. Python 패키지는 `pyproject.toml + uv.lock`, 웹 패키지는
`package.json + package-lock.json`이 기준이므로 중복되는 `requirements.txt`를 만들지 않습니다.

버전을 올릴 때는 버전 파일, 프로젝트 설정, Dockerfile, lockfile과 개발환경 검사를 한 PR에서
함께 갱신합니다. Docker image digest도 새 tag의 manifest를 확인한 뒤 함께 바꿉니다. 저장소가
요구하는 버전과 현재 도구가 다르면 전역 설치를 자동으로 바꾸지 않고 검사에서 실제 값과 필요한
값을 함께 보여 줍니다.

## 3. 전체 demo 실행

Compose와 host process는 같은 versioned topology와 `cmp-stack` 명령을 사용합니다.

```powershell
uv run cmp-stack --profile demo --runtime compose doctor
uv run cmp-stack --profile demo --runtime compose up
uv run cmp-stack --profile demo --runtime compose status
```

`postgres`와 `api`가 healthy이고 `migrate`, `reference-plugins`, `seed`가 0으로 종료되어야 합니다.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Web은 <http://127.0.0.1:5173>, API는 <http://127.0.0.1:8000/api/v1>입니다. Demo mode에서는
브라우저가 제한된 local session을 자동으로 준비합니다. 사용자가 API 주소, Bearer token 또는 내부
identity 식별자를 입력하는 화면은 현재 제품 계약이 아닙니다.

`cmp-local-demo`는 사람이 이어서 살펴보는 영구 Demo project입니다. 반복 자동 검증은 이 project의
API나 volume을 사용하지 않습니다. 다음 명령은 매번 고유한 `cmp-demo-test-*` project와 전용 DB 및
object-store volume을 만들고 migrate한 뒤, 같은 깨끗한 DB에서 seed를 두 번 실행합니다. 두 실행
사이에 실제 DB에서 발견한 모든 non-system product/domain schema의 identity, revision, Catalog
record, State, processing, Neutral, review, domain binding, direct link가 늘거나 달라지지 않아야
전체 확인으로 넘어갑니다. 성공·실패 모두 해당 test project만 `down -v`로 제거합니다. 인증 토큰
발급 시 갱신되는
`identity.external_identity.last_seen_at`만 비교에서 정규화하며, 해당 identity와 나머지 열은 그대로
검사합니다.

```powershell
uv run python scripts/run_disposable_demo_test.py
# 또는 Make가 있는 환경: make demo-verify
```

브라우저 검증도 영구 Demo에 연결하지 않습니다. `make demo-e2e`는 같은 격리 runner에 `--e2e`를
전달하고 Web만 임의 localhost port로 노출합니다. 두 번째 seed나 domain binding이 실패하면 runner가
`repeat demo seed`와 해당 Catalog projection 단계를 함께 표시합니다. bounded 회귀 확인은 `--e2e`와
`--e2e-spec e2e/<spec>.spec.ts`를 함께 반복 지정할 수 있으며, 생략하면 전체 E2E suite를 실행합니다.

종료:

```powershell
uv run cmp-stack --profile demo --runtime compose down
```

`make demo-down`과 위 `down` 명령은 컨테이너만 내리고 `cmp-local-demo` DB와 object-store volume을
보존합니다. 영구 Demo에는 반복 검증 정리용 `down -v`를 사용하지 마십시오. 격리 runner만 자신이
생성한 `cmp-demo-test-*` project에 `down -v`를 실행합니다.

Docker·WSL 없는 Windows 실행, local/LAN URL과 데이터 위치는
[공통 Stack CLI](deploy/stack/README.md), Compose 설치·port·migration·복구 문제는
[Compose 실행 가이드](deploy/compose/README.md)를 따릅니다.

Windows 11 x64 offline bundle은 연결된 Windows 빌드 환경에서만 생성합니다. 다음 명령은 #282 버전
authority와 text-only manifest를 대조하고 각 archive의 SHA-256을 검증한 뒤 Python/PostgreSQL과
production Web asset만 제품 payload에 넣습니다. Node/npm/uv는 build-only입니다.

```powershell
uv run python scripts/build_windows_offline_bundle.py --profile demo --output-dir C:\cmp-bundles
```

산출물과 실제 인증 값은 저장소에 추가하지 않습니다. 상세 절차와 Server 입력은
[Windows bundle README](deploy/windows/README.md)를 따릅니다.

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
uv run python scripts/repository_tasks.py ci --host-only
```

GNU Make 사용 환경에서는 `make lint`, `make typecheck`, `make test`, `make web-build`,
`make web-test`, `make docs-screenshots`, `make install-hooks`, `make verify-hooks`,
`make pre-publish`, `make ci`를 사용할 수 있습니다. `make pre-publish`는 결정적 검사만 수행합니다.
`make pre-publish-review`는 모델 비용이 발생하는 명시적 opt-in 명령이므로 사용자의 사전 승인이
있을 때만 실행합니다. `make ci`와 `scripts/ci.sh`는 아래의 운영체제 중립 CLI를 그대로 호출하며
검사 순서나 실패 전파를 별도로 정의하지 않습니다.

```powershell
uv run python scripts/repository_tasks.py ci --host-only
```

Docker 없는 host-only 실행은 `container_service` marker 대상의 정확한 제외 개수를 출력한 뒤 나머지
검사를 실행합니다. `--host-only`와 `--require-container-tests`는 함께 사용할 수 없습니다. CLI는
사용자가 지정한 uv 환경 변수를 보존하고, 지정하지 않은 cache·가상환경·임시 경로는 uv와 Python
표준 라이브러리의 운영체제별 기본 위치를 사용합니다. `/tmp` 경로를 합성하지 않습니다.

## 6. PostgreSQL integration gate

통합 테스트는 별도의 localhost-only, tmpfs-backed PostgreSQL을 사용합니다. Demo DB나 production
DB를 test DSN으로 지정하지 마십시오.

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile test up -d postgres-test
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest -m container_service tests/integration -ra
uv run python scripts/repository_tasks.py ci --require-container-tests
```

`postgresql`은 DB 요구사항을, `container_service`는 저장소 CI가 준비하는 외부 서비스 경계를
표시합니다. 현재 PostgreSQL integration module은 두 marker를 함께 가져야 하며 CLI는 marker drift를
오류로 처리합니다. 이 suite는 temporary database/role을 생성·삭제합니다. 0 failure, 0 skip이
기준이며 고정된 test 개수에 의존하지 않습니다.

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
