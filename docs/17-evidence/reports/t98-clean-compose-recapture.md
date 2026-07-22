# T98 clean Compose browser recapture

Date: 2026-07-22
Baseline: `main` at `4b2a974` before this documentation-only recapture

## Purpose

The current user-guide screenshots were regenerated from a clean deterministic demo rather than
reusing the previously accepted image bytes. The recapture covers Materials search and Browse Tree,
Material Detail, CAE Cards, Modeling Data/Fit/Export, governed tabular import, Administration, and
Activity.

## Clean environment

The demo stack was removed with its two project-scoped synthetic volumes and rebuilt with:

```text
docker compose -f deploy/compose/docker-compose.demo.yml down -v --remove-orphans
docker compose -f deploy/compose/docker-compose.demo.yml up --build -d
```

PostgreSQL and API health checks passed. Migration and deterministic reference-plugin seed containers
exited with code 0. Browser verification used the web application's `/api/v1` proxy because the host's
direct port 8000 is intercepted by a local HTTPS listener; this does not affect the Compose web route.

## Browser scenarios

| Scenario | Verified result |
| --- | --- |
| DP780 search → selection → Overview/curve → OpenRadioss preview/download | Search, selection, native ASCII preview, and visible `.rad` primary download action passed. Download contract remains covered by browser E2E because the in-app browser does not expose blob downloads as a download event. |
| Browse Tree → Metal/Steel → DP780 → Related/Workflow → CAE Cards | Searchable Database/Profile/Table/Folder/Record hierarchy, exact Record selection, workflow links, and native cards passed. |
| Administration → Table/Attribute/Layout → Record Datasheet | Role-gated configuration routes and clean DP780 Layout projection passed without acceptance-only mutations. |
| JSON/CSV/XLSX → channel/unit mapping → Process/Fit → Export | Canonical JSON and governed tabular entry, graph-dominant Fit, mapping preflight, explicit approximation acknowledgement, generated Abaqus preview/download action, and library workflow passed. |
| Activity | The route and shell baseline passed. This capture does not prove exact session resume or review-attention behavior; DUI-08 remains pending. |

## Viewport and image evidence

Requested browser sizes were 1366×768, 1440×900, and 1920×1080. The in-app browser removes its own
chrome from PNG captures and the host window limited the widest content surface. Therefore
`screenshot-manifest.yaml` records actual PNG dimensions: 1351×760, 1425×891, and 1715×1072 for the
three responsive tiers. The governed import capture is 1440×900 because that route was captured by the
browser's exact viewport surface.

All images use synthetic non-production data. They were checked for black/transparent trailing regions,
unexpected clipping, local personal paths, credentials, and confidential data.

## Regression results

- deterministic full-demo verification: passed for metal, polymer, elastomer, governed workflow, and
  native solver-card SHA-256 evidence;
- web unit tests: 36 files, 92 tests passed;
- browser E2E: 3 tests passed, including Search-first material-family discovery, exact Neutral card and
  governed ZIP downloads, and exact Test JSON workflow navigation;
- user-guide contract: 20 guide documents, 17 current captures, 3 global navigation items, and 178
  classified Markdown files passed;
- documentation impact contract: passed for the complete worktree change set.

The guided-demo E2E was updated in this work unit because it still asserted the removed `/demo` landing
page and a single-bundle seed. It now follows `/materials`, opens each synthetic family through search,
enters bulk packages through Activity disclosure, and matches the downloaded bundle by SHA-256 rather
than list position or total seed count.

## Remaining limits

- The in-app browser cannot prove the filesystem result of a blob download; automated browser tests and
  API/export regression tests remain the authoritative download assertion.
- A physical 1920-wide browser content surface was unavailable on this host. The 1920 responsive CSS
  branch was requested and exercised, while the actual captured content width is recorded as 1715 px.
