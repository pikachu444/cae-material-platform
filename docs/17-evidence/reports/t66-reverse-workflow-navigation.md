# T-66 reverse workflow navigation evidence

Date: `2026-07-19`

## Product behavior

The Catalog API now resolves a closed domain kind, stable object UUID and exact revision UUID back to
the unique configurable Record revision that represents it. The query uses the existing indexed,
tenant/classification-scoped binding table and the caller's `catalog.read` RLS decision.

The shared **Exact linked data** panel consumes that reverse lookup and the existing bounded graph API.
It is connected to Material, canonical Test Data JSON, common Processing Output and Neutral/Card
workbenches. A missing projection is stated explicitly rather than following a `latest` alias.

The Explorer requests the supported depth of five. Its node grid displays the whole reachable clean
journey, while **Forward and reverse links** displays only edges incident to the selected exact Record.

## Verification

- protected reverse-binding API: exact hit and null miss regression;
- PostgreSQL: exact reverse lookup through the non-bypass application role;
- React: Explorer and related-workbench links, exact-revision URLs and missing-projection state;
- Playwright: canonical DP780 Test JSON → Workflow Explorer → selected IR → Neutral JSON → exact
  Abaqus/OpenRadioss card nodes;
- OpenAPI contract and generated Python client updated additively.

![Exact Test JSON reverse navigation to the complete governed graph](../images/historical-task-screenshots/t66-reverse-workflow-navigation.png)
