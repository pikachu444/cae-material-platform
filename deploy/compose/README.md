# Local Docker Compose demo

This is an explicit development-only composition for the first product
vertical slice:

```text
Material → Material State → typed basic properties → reference IR
→ OpenRadioss /MAT/ELAST mapping → immutable Solver Card
```

It also seeds a synthetic reference tensile CSV through the protected upload
and Dataset APIs. The repository's T-18 `contract_echo` reference plugin is
included and checked by the `reference-plugins` service, but is not registered
or activated for this Material-to-card slice because it implements no Material,
Test, fitting, or exporter behavior. It is intentionally not a production
deployment template.

```bash
docker compose -f deploy/compose/docker-compose.demo.yml up --build
# or: make demo
```

Open `http://127.0.0.1:5173`, select **Connection**, choose **Use local demo
identity**, then save the connection. The browser receives a 15-minute signed
token only because the API is explicitly started with both
`CMP_ENVIRONMENT=demo` and `CMP_DEMO_IDENTITY=true`. Every subsequent request
still travels through normal JWT verification, RBAC, PostgreSQL RLS, immutable
revision/provenance hooks, and the non-owner `cmp_app` role.

The local API is `http://127.0.0.1:8000/api/v1`; PostgreSQL is exposed on
`127.0.0.1:54329` only for local inspection. The data is synthetic and not
validated engineering data. Tear it down with:

```bash
docker compose -f deploy/compose/docker-compose.demo.yml down -v
# or: make demo-down
```

