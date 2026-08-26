# Local Docker Compose demo

`docker-compose.demo.yml`은 `deploy/stack/topology.yaml`에서 생성됩니다. OS 공통 진입점은
`uv run cmp-stack --profile demo --runtime compose <doctor|up|down|status|logs>`이며 기존 직접
Compose 명령도 호환됩니다. Web image는 Node로 production assets을 build하지만 최종 runtime은
Python `cmp-web` front door라 실행 중 Node나 Vite dev server를 사용하지 않습니다.

This is an explicit development-only composition for the first product vertical slice:

```text
Material → Material State → typed basic properties → reference IR
→ OpenRadioss /MAT/ELAST mapping → immutable Solver Card
→ normalized tensile Dataset → tabulated-plasticity IR
→ OpenRadioss /MAT/LAW36 and Abaqus *PLASTIC cards
```

It also seeds a synthetic reference tensile CSV through the protected upload and Dataset APIs,
derives a non-production pre-necking hardening curve, and generates downloadable `.rad` and `.inp`
cards through the same API used by the browser. The repository's T-18 `contract_echo` reference
plugin is included and checked by the `reference-plugins` service, but is not registered or activated
for this Material-to-card slice because it implements no Material, Test, fitting, or exporter
behavior. It is intentionally not a production deployment template.

## Windows installation prerequisites

You do not need to install the API or PostgreSQL separately for this demo. Compose builds the API,
worker, and web images and runs PostgreSQL 16 in a container. You do need a working WSL 2 and Docker
Desktop installation.

The following actions require the Windows user because they can request elevation, license/terms
acceptance, BIOS/UEFI virtualization changes, or a reboot:

1. In PowerShell, inspect WSL:

   ```powershell
   wsl --status
   wsl --version
   ```

2. If WSL is absent, open **PowerShell as Administrator**, run `wsl --install`, and reboot when
   Windows asks. If it is present, run `wsl --update`. If Windows reports that virtualization is
   disabled, enable CPU virtualization in BIOS/UEFI before continuing.
3. Install Docker Desktop from the
   [official Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).
   On an organization-managed computer, use the company-approved package and license policy. A
   command-line option is `winget install -e --id Docker.DockerDesktop`, but the installer and first
   launch still require user interaction.
4. Start Docker Desktop, accept the applicable terms, select/use the WSL 2 engine, and wait until the
   Docker Engine reports that it is running. This repository uses Linux containers; keep Docker in
   Linux-container/WSL 2 mode. Docker Desktop need not expose an unauthenticated TCP daemon.
5. Open a new PowerShell window and verify:

   ```powershell
   wsl --status
   docker version
   docker compose version
   ```

If `docker` is not found after installation, close and reopen the terminal. If the client is present
but cannot reach the engine, start/restart Docker Desktop and recheck the WSL integration. The
[Microsoft WSL installation guide](https://learn.microsoft.com/windows/wsl/install) covers the
Windows feature and reboot requirements. Lack of local administrator rights or a corporate policy
that blocks WSL/Docker must be resolved by the user or IT; repository code cannot bypass it.

## Start the full stack

```bash
docker compose -f deploy/compose/docker-compose.demo.yml up --build
# or: make demo
```

For continued manual inspection of the permanent demo, run it in the background:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
```

Before any live database or browser gate, run the read-only environment preflight. It rejects stale
or foreign Compose projects that own a required host port and checks the canonical project labels,
health, config path, working directory, and image IDs:

```powershell
make compose-preflight
# include the optional isolated integration-test database when that gate is selected:
uv run python scripts/check_compose_environment.py --include-postgres-test
```

Rebuild and recreate the canonical project for the current work before accepting a preflight result;
the command never stops, removes, or mutates containers or volumes.

## Permanent demo and disposable verification

`cmp-local-demo` is the persistent project for human demonstration. Automated demo verification must
not call its API or mount its `cmp-local-demo_cmp_demo_postgres` and
`cmp-local-demo_cmp_demo_objects` volumes. Run the isolated path instead:

```powershell
uv run python scripts/run_disposable_demo_test.py
# or: make demo-verify
```

The runner validates the merged `docker-compose.demo.yml` and `docker-compose.demo-test.yml` config,
chooses a unique `cmp-demo-test-*` project, removes fixed database/API host ports, and gives Web a
random localhost port only when `--e2e` is selected. Its database and object-store volumes are named
from that unique project. It runs migrate, seeds the same clean database twice, discovers every
non-system product/domain table in that database, and verifies identical counts and content after both
runs. Required coverage fails closed unless it includes Catalog State and direct links, Processing,
Neutral revisions,
solver cards, and review requests. It then runs API or browser verification and removes only that test
project and its volumes even after a failed check. A repeat failure names the runner stage and the
conflicting Catalog projection. If a running permanent demo is available, the runner also prints and
compares its volume identity and core record/revision counts before and after.

The snapshot normalizes only `identity.external_identity.last_seen_at`, which authentication updates
while obtaining the demo token. The external identity and every other field remain part of the exact
comparison.

The 1,000-record performance fixture remains a separate later check and is not hidden inside this
repeat-seed command.

For a bounded browser regression, combine `--e2e` with one or more
`--e2e-spec e2e/<spec>.spec.ts` arguments. Omitting `--e2e-spec` keeps the existing full-suite
behavior; either path uses the same disposable seed, snapshot, and cleanup boundary.

Wait until `postgres` and `api` are healthy. `migrate`, `reference-plugins`, and `seed` are one-shot
services and must exit with code 0. Check the API independently:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

When rebuilding selected services after a schema change, build and run `migrate` before starting
the new API or worker image. Compose gives `migrate` its own image even though it shares the API
Dockerfile:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml build migrate api worker web
docker compose -f deploy/compose/docker-compose.demo.yml run --rm migrate
docker compose -f deploy/compose/docker-compose.demo.yml up -d --force-recreate api worker web
```

Starting new application images against the previous schema is intentionally unsupported. A full
`up --build -d` already builds the one-shot migration image and applies this order through
`depends_on`.

Open `http://127.0.0.1:5173`. The demo workspace prepares a short-lived local session automatically
because the API is explicitly started with both `CMP_ENVIRONMENT=demo` and
`CMP_DEMO_IDENTITY=true`. Users do not enter an API URL or token. Every subsequent request still
travels through normal JWT verification, RBAC, PostgreSQL RLS, immutable revision/provenance hooks,
and the non-owner `cmp_app` role.

The local API is `http://127.0.0.1:8000/api/v1`; PostgreSQL is exposed on `127.0.0.1:54329` only for
local inspection. OTLP/HTTP is localhost `4318` and the Collector's Prometheus endpoint is
`http://127.0.0.1:8889/metrics`. The data is synthetic and not validated engineering data.

The optional recovery profile uses a separate image with a PostgreSQL 16 client and never replaces
the running demo database:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile operations run --rm restore-drill
```

It restores into a random temporary database, verifies the independent filesystem-object snapshot
and writes a JSON report below `.cache/restore-drill/`. See the
[operations and recovery guide](../../docs/user-guide/11-operations-and-recovery.md).

## Run the PostgreSQL integration gate

Keep the demo database SCRAM-authenticated. The integration harness creates temporary passwordless
application roles, so start its separate localhost-only, tmpfs-backed PostgreSQL profile. From the
repository root:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile test up -d postgres-test
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_test_owner@127.0.0.1:54330/postgres"
uv run pytest -m container_service tests/integration -ra
uv run python scripts/repository_tasks.py ci --require-container-tests
```

The marker suite must have zero failures and zero skips. The task CLI collects and logs the exact
`container_service` count on every run and rejects PostgreSQL marker drift; the count is not a
hard-coded acceptance value. A Windows host without Docker uses
`uv run python scripts/repository_tasks.py ci --host-only` and logs the exact exclusion count. Do not
substitute the non-owner `cmp_app` credentials and never point this variable at a production or shared
database. The tests create/drop temporary databases and roles.
The `postgres-test` service publishes only `127.0.0.1:54330`, uses `trust` only inside this isolated
test container, and stores its cluster in tmpfs. It must not be used as a deployment pattern.
The full procedure and acceptance rule are in
[the test strategy](../../docs/14-testing/test-strategy.md#p0-1-windowscompose-verification-runbook).

When troubleshooting, capture state and logs before deleting anything:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
docker compose -f deploy/compose/docker-compose.demo.yml logs --no-color postgres migrate api seed
```

Common causes are Docker Desktop not running, WSL/virtualization not enabled, host ports `54329`,
`8000`, or `5173` already in use, or a stale synthetic demo volume after a migration change. Stop the
persistent demo without deleting its volumes with:

```bash
docker compose -f deploy/compose/docker-compose.demo.yml down
# or: make demo-down
```

No Make target removes the persistent `cmp-local-demo` volumes. Do not use `down -v` on that project
for routine verification. The disposable runner applies `down -v` only to its validated, unique
`cmp-demo-test-*` project.

If another local process owns port `8000`, the browser workbench still reaches the API through the
Compose-internal web proxy at `http://127.0.0.1:5173/api/v1`. Stop or reconfigure the unrelated
process before using the API's direct host URL; never terminate an unknown process automatically.
