# Issue #208 — Schema Definition Bundle Administration evidence

## Boundary and starting state

This packet records bounded implementation evidence for GitHub issue #208. Work started from fetched
`origin/main` `002449a40d45d4378f8d9bea55eb3f354522b30c` on branch
`agent/issue-208-schema-bundle-admin` in the primary checkout. The checkout was clean before the branch
was created. The product owner moved #208 ahead of #212 in parent issue #117 and the delivery backlog;
#208 is therefore the first unfinished unit and #212 remains unstarted.

The issue body, owner instruction, root `AGENTS.md`, backlog row 23, FR-CFG-001 through FR-CFG-006,
the #204 bundle/plan contracts, the #207 apply/read-back/export contracts, and the approved
`ADM-SCHEMA-CORE` visual family are authority. No production material family, tensile standard,
constitutive model, optimizer, solver card or validation threshold is selected here.

Initial implementation classification was:

| Classification | Starting `main` state |
| --- | --- |
| Complete | Strict arbitrary-cardinality JSON Schema bundle validation and no-write planning; atomic apply, read-back and exact-source export; Administrator permission enforced by service/database; current Administration shell and three-pane schema editor |
| Partial | Existing immutable upload API can create the verified source Artifact, but the browser client has no bundle-specific upload limit, request correlation read-back or exact export verification helper |
| Missing | Administrator bundle route and screen; local file preflight; upload → plan → explicit confirmation → apply UI; action/diagnostic inspection; progress, stale-plan and retry states; refresh read-back; checksum-verified export; role-aware frontend denial; browser and five-viewport evidence |

## Primary user journey and acceptance

| Part | Issue-owned journey |
| --- | --- |
| Setup | An authenticated Administrator opens **Administration → Definition bundles** with the bounded synthetic non-production bundle fixture. The bundle contains several schemas and the current Catalog contains both matching and unrelated definitions. |
| Actions | Select one JSON file; pass local MIME, size and JSON checks; upload it as one immutable source Artifact; request the server plan; inspect ordered create/update/no-op/conflict/error rows and the selected row's location, impact and next action; explicitly confirm the exact bundle version, Artifact SHA-256 and plan fingerprint; apply; read the immutable application; export and verify the returned bytes. |
| Visible outcome | The same screen handles any schema count without one control per schema. It shows source identity, exact plan counts, a locally scrollable action table, a bounded detail pane, one enabled primary next action, progress, completion or failure, correlation ID and item-level recovery. Conflict, unsupported and migration-required plans never expose Apply as executable. |
| Persistence/read-back | Refresh restores only safe source/application coordinates from browser session storage, then re-plans or reads the immutable server application. It never stores source bytes, an access token or client-authored plan actions. Successful read-back shows bundle version, created revision identities, source Artifact and verified export checksum. |
| Preserved state | The browser sends only exact Artifact ID/SHA-256, server-issued plan fingerprint, fixed `delete_missing=false` and a fresh idempotency key. The server remains authority and revalidates role, tenant, Artifact, Catalog snapshot and write set. Raw bytes, prior revisions, unrelated definitions and Record data remain unchanged. |
| Recovery | Invalid MIME, empty/oversized/malformed JSON and missing bundle shape fail before upload with focus on the correction. Server diagnostics retain source context. A stale fingerprint preserves the uploaded source and offers **Plan again**; retry never replays unchanged Apply. Refresh restores the last valid plan or result; denied roles see no upload or Apply control. Export digest mismatch fails closed and no download is presented. |
| Owned scope | Bundle Administration React route/component, typed API client and request-ID/export verification support, shared-token CSS, focused frontend/API/browser tests, navigation/permission/state contract, current guide/screenshots, delivery records and this evidence packet. |
| Forbidden shortcuts | No client execution of plan actions; no generic JSON editor or schema-per-card UI; no direct database or browser migration; no token/hash as normal navigation identity; no hidden conflict; no silent export acceptance; no route-specific 4K override, CSS zoom, transform scaling, fabricated filler or unrelated #209/#212 work. |
| Exact acceptance | Issue #208 completion criteria and required negative tests; successful upload-plan-confirm-apply-read-back-export journey; User/Reviewer frontend and API denial; keyboard/focus/long-name checks; five deterministic 100%-zoom viewports with original and required 100%-pixel crops; affected build/contracts/docs gates; one independent Balanced audit of the exact final SHA with no blocking or material finding; product-owner visual approval before ready/merge. |

## Verification record

The corrected browser and planner behavior was frozen as source commit
`64b9be83a03e1760478165b87917e7107852d4f7`; the product-owner visual correction and its recaptured
evidence were frozen as `63176ec5a07647d598753d437fce4339d4f05ebb`. The implementation adds the
lazy Administration route, typed client, shared-token three-pane surface, local/source validation,
server-owned plan review, explicit confirmation, atomic Apply request, mandatory immutable read-back,
safe refresh recovery and verified export. During self-review, the uncertain-completion boundary was
tightened: if Apply returns an application but the mandatory GET fails, the screen withholds success
and export and offers only **Read applied result**. It never replays Apply or re-plans an operation that
may already have committed.

The first independent Balanced audit found two material recovery gaps. The correction makes the
read-only Catalog snapshot include current Record/value activity, emits deterministic
`record_migration_required` error actions and diagnostics before confirmation, and preserves the
apply-time migration conflict if Record state changes after planning. It also locks source replacement
while an Artifact, plan, application or recovery coordinate is active, hides reset during an in-flight
operation, and invalidates stale asynchronous results when **New bundle** explicitly clears the context.
Focused server and browser regressions cover both findings.

During the first product-owner geometry review, the owner rejected the inherited boxed/dark navigation
separators and awkward bold labels, the grey central plan surface, and blue bold target labels as
visually inconsistent. The bounded correction removes the inherited full button borders and `strong`
navigation markup, uses a single soft divider with restrained active emphasis, gives the central plan
pane the normal white work surface, and renders target names in neutral regular-weight text. The source
context pane remains a light neutral navigator surface. All five viewport originals, direct crops, two
state images and the current-guide image were regenerated; product-owner re-review remains pending.

| Check | Result |
| --- | --- |
| Focused Vitest API/component suite | PASS — 26 functional tests, including full flow, role denial, migration-required confirmation block, source replacement lock/reset, stale plan, uncertain Apply/read-back recovery, refresh, invalid file classes and export mismatch; 25 focused app/component tests passed again after the visual correction |
| Full web Vitest regression | PASS — 64 files, 347 tests |
| Production web build and bundle budget | PASS — TypeScript/Vite build; corrected route is a 24.64 kB lazy chunk; existing Material Library warning remains below its hard ceiling |
| Focused Python API integration | PASS — 7 tests, including User/Reviewer apply/read-back/export 403 with zero service calls |
| Planner unit/contract/API regression | PASS — 86 tests, including table update, populated Attribute update and new required Attribute migration-required plans |
| Playwright browser journey | PASS — 1 contract-backed journey, Administrator upload through verified export and refresh plus Reviewer denial |
| Browser geometry | PASS — 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160 at CSS zoom 100%, DPR 1, zero page horizontal overflow |
| Original-resolution qualitative review | PASS — five plan originals, twenty direct 100%-pixel crops, confirmation and applied/read-back/export images opened at original resolution |
| Affected Python contracts/integration | PASS — 98 tests across guide inventory, capture tooling and bundle API integration; 91 guide/capture contracts passed again after the visual correction |
| User guide and documentation impact gates | PASS — 20 guide documents, 101 current captures, 570 local links, 1,745 registered images; 63 changed files and 3 visual sources accounted for |
| Static and diff checks | PASS — Ruff lint on affected Python files, sidecar hashes/dimensions for 27 PNGs and five measurements, `git diff --check` |
| Balanced independent audit | PENDING — the prior pass predates the product-owner visual correction; the same implementation-uninvolved reviewer must audit the corrected exact final SHA before publication. |
| Product Owner visual geometry approval | Pending re-review of the corrected five-viewport evidence before ready/merge |

The exact files, dimensions, hashes, route, fixture and geometry boundaries are registered in
[`visual-evidence.yaml`](images/issue-208-schema-bundle-administration/visual-evidence.yaml). The plan
table reveals more complete rows as the central workspace grows, while source and detail panes remain
readable bounds. The finite 13-row fixture leaves honest unused space at large viewports; no rows or
decorative filler were fabricated. The 3840 CSS capture is geometry evidence only. Physical Windows 4K
100%, 150% and 200% readability remains deferred to #223.

Canonical Compose was rejected at preflight because the running `cmp-local-demo-*` project is owned by
the preserved `C:\SourceCodes\cae-material-platform-issue210` worktree rather than this checkout. It was
not stopped, recreated or treated as #208 evidence. The browser record therefore uses an isolated Vite
server with contract-backed endpoint fixtures and makes no claim of canonical Compose persistence.

Draft delivery is tracked in [PR #242](https://github.com/pikachu444/cae-material-platform/pull/242).
It remains draft until the recorded product-owner visual approval passes.
