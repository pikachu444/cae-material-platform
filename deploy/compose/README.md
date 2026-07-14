# Local Docker Compose demo

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

For verification and tests it is more convenient to run in the background:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml config --quiet
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
```

Wait until `postgres` and `api` are healthy. `migrate`, `reference-plugins`, and `seed` are one-shot
services and must exit with code 0. Check the API independently:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
```

Open `http://127.0.0.1:5173`, select **Connection**, choose **Use local demo identity**, then save the
connection. The browser receives a 15-minute signed token only because the API is explicitly started
with both `CMP_ENVIRONMENT=demo` and `CMP_DEMO_IDENTITY=true`. Every subsequent request still travels
through normal JWT verification, RBAC, PostgreSQL RLS, immutable revision/provenance hooks, and the
non-owner `cmp_app` role.

The local API is `http://127.0.0.1:8000/api/v1`; PostgreSQL is exposed on `127.0.0.1:54329` only for
local inspection. The data is synthetic and not validated engineering data.

## Run the PostgreSQL integration gate

The Compose owner account is deliberately privileged only for this disposable demo. From the
repository root:

```powershell
$env:CMP_TEST_POSTGRES_DSN = "postgresql+psycopg://cmp_owner:cmp_owner_development_only@127.0.0.1:54329/cmp"
uv run pytest -m postgresql tests/integration -ra
& "C:\Program Files\Git\bin\bash.exe" scripts/ci.sh
```

The marker suite must have zero failures and zero skips; do not treat the currently observed count
of 62 as permanent. Do not substitute the non-owner `cmp_app` credentials and never point this
variable at a production or shared database. The tests create/drop temporary databases and roles.
The full procedure and acceptance rule are in
[the test strategy](../../docs/14-testing/test-strategy.md#p0-1-windowscompose-verification-runbook).

When troubleshooting, capture state and logs before deleting anything:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml ps --all
docker compose -f deploy/compose/docker-compose.demo.yml logs --no-color postgres migrate api seed
```

Common causes are Docker Desktop not running, WSL/virtualization not enabled, host ports `54329`,
`8000`, or `5173` already in use, or a stale synthetic demo volume after a migration change. Only
after saving useful logs, tear the disposable environment down with:

```bash
docker compose -f deploy/compose/docker-compose.demo.yml down -v
# or: make demo-down
```

`down -v` deletes the Compose demo database and object-store volumes permanently. It is safe only
for this synthetic local composition and must not be copied to a production or unrelated project
context.
