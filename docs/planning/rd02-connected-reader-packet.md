# RD-02 connected reader — implementation packet v4

Status: v4 approved by canonical requirements auditor on 2026-09-07; implementation authorized,
no publication authority. Prior v3 findings were resolved by the frozen v4 choices below.
Workspace: `C:/Users/pikac/.codex/worktrees/d0b9/cae-material-platform`, base/HEAD
`4c545ea18322769b25d67177d609e3eb14202666`; branch `codex/rd02-connected-reader`
(initially detached). Main owns integration and live acceptance.

## Authority and bounded outcome

Read root and apps/web-next AGENTS, frontend-redesign-status, program RD-02 and section 0,
frontend-development, frontend-architecture, frontend-ui-principles, data-management-policy,
ADR-0036/0037/0038, visual-acceptance-matrix and the relevant existing API/schema contracts.
The current owner request prioritizes this reader after PR #397; #392/#195 remain open.
Use design/frontend-reader-proposals/material-workspace/index.html, workspace.css and workspace.js
as the accepted layout/interaction reference. Earlier six proposals and React A/B are historical.

Complete: preserved backend engines, exact artifact routes, canonical Test Data list/content/curve,
common Processing Output list/content, material list/detail and per-model card routes.
Partial: isolated React foundation and primitives. Missing: connected material-centered reader,
direct project-wide card discovery, truthful related-object navigation and live acceptance.

Primary journey: authenticated user directly opens Test Data without choosing a material, searches
and pages stored canonical experiments, single-selects a preview with individually readable conditions,
units and measured curves, then opens expanded detail by double-click/Enter/visible detail action.
Follow stored material/specimen/processing/model/card relationships; distinguish material membership
from actual generation inputs. Download the stored Test Data JSON and Processing Output JSON separately
from the existing native solver card. Return restores query/filter/sort/page/selection/scroll/focus;
reload and direct URLs resolve the same stable object and exact v1 pin. Also support Materials
card/table browsing, expandable material/state/specimen tree, separate applicable filters, and direct
Solver Cards list/detail/download. Show stored engineering properties as item/value/unit/condition.

## Ownership and implementation decisions

Owner steering (2026-09-07): systematic frontend structure and long-term extension are acceptance,
not post-reader cleanup. App owns routing/providers/composition; each feature owns its public UI,
query adapter and reader rules; shared owns only actually reused transport/primitives. Engineering
conditions/properties/curves are domain components, not generic helpers or JSX calculation blocks.
Audit app → features → shared dependency direction and no feature-internal deep imports/cycles.
Do not put the reader into a single ever-growing component or a catch-all gateway containing all
domain logic. Report actual directories/responsibilities and one new-test-condition extension path
including adapter/type/condition component/tests; no unrelated shell or solver changes should be needed.
Document why currently installed Router/Query, native/Radix controls, Table, Lucide and chart primitive
are used or deferred based on task/accessibility/scale/license/maintenance. RHF/Zod apply when the
actual form/validation boundary needs them; no forced Tailwind/shadcn migration or new chart library.
Compare maintenance of a custom primitive with the available library before building one.
Final independent review must cover dependencies, state/CSS ownership, duplicate interim code and
zero-consumer/parity/recovery prerequisites for eventual legacy deletion.

Second owner steering: the required extension example is specifically selected Test Data → processing
entry → basic/advanced settings → execute → compare → save/read-back → Processing Output download.
Document a small typed input handoff with stable identity, exact required v1 pin and validated channel/
condition/unit metadata. Reader selection is not processing input state. Future processing feature
owns eligibility, method-specific settings/draft, request/result identity, stale-current assessment,
save and recovery. It consumes shared curve/condition/error/download components only where genuinely
common; computation never enters a plot renderer. Identify actual existing synchronous/asynchronous
backend contracts before describing execution ownership. Do not prebuild a fake job/polling framework,
empty processing feature or nonfunctional action. Explain which future files change and which reader
files stay unchanged. This future journey is architecture review, not added RD-02 write scope.

- The single writer owns apps/web-next runtime, affected tests and README; bounded API additions in
  backend/src/cmp/modules/{exporting,datasets,processing}/ and bootstrap/apps registration only if
  required for direct reader queries, plus affected contract/schema/regression files. No other writer.
- Main owns this packet, snapshot integration, planning status, evidence/guide registration, environment
  and final live acceptance. Writer may propose follow-up contract gaps but cannot silently omit them.
- Keep the live build free of prototype imports/fallbacks. Do not port synthetic arrays or fake files.
  Use existing installed React Router/TanStack Query, native controls or Radix as appropriate. No new
  generic framework, dependency shopping, package upgrades or personal setting/hook changes.
- Feature adapters own typed v1 response→display mapping. Preserve concrete revision IDs only as
  compatibility pins in adapters/links; do not infer a revision from a stable ID or add editing history.
- Server objects use Query with auth scope/ID/query keys and AbortSignal; URL owns reader state;
  temporary panel state stays local. Authentication must use real server credentials/session, never
  hardcoded identity. Explicit local-demo login is allowed only via existing demo identity endpoint.
- Prefer existing APIs. Existing card lists are per-model; add minimal read-only project-scoped list
  routes through existing exporting services/repositories if necessary, retaining EXPORT_READ,
  tenant/project SQL restrictions and RLS, exact native download routes and card-family distinctions.
  Do not require Materials/Catalog publication or material-read permission to discover cards.
  Do not silently scan a truncated material list to fabricate a global card list.
- Canonical Test Data and Processing Outputs already have project list routes. Use actual returned
  pins/source_document/source_processing_output/model inputs for relationships. Never join on grade,
  specimen label, first item, latest, another session or same-material membership as derivation.
  Surface API-supported material/state/specimen links; metadata without stored domain linkage is
  explicitly unlinked. Unsupported families/routes/files get explicit status, not invented downloads.
- Each list's rows/counts/filters describe the same scope. Material search is server scoped. If an
  existing unpaginated API requires local filtering/paging, identify the scope truthfully and avoid
  false server total/facet claims; add bounded server query support if required by real scale.
- Reuse backend computation/curve response semantics; do not calculate material laws, convert units,
  resample scientific outputs, repair golden bytes or alter DMA logic. Graph axes/series retain
  physical quantity and units; null/missing points are not zero. Raw vs normalized vs processed vs
  native card representations remain distinct. Do not stringify card JSON as a native file.
- This is read-only RD-02: no metadata PATCH form, registration, processing execution, new model/card
  creation or broad revision migration. Unsaved scientific editing is N/A; search/filter drafts must
  survive unrelated query refresh and must not silently vanish on detail return. Existing saved
  older results stay readable/downloadable and are identified with their actual input pins.
- CSS Modules and shared typography/control/row/spacing/pane/plot tokens implement the selected
  full-viewport composition. Right preview remains optional; expanded detail hides list. No route
  4K overrides, CSS zoom/scaling, decorative filler, cramped engineering columns or empty inspector.

## Acceptance and recovery

### Frozen reader contract and corpus (v4)

These frozen choices supersede earlier conditional wording about list/API additions.

The primary end-to-end family is canonical tensile Test Data → saved common Processing Output →
tabulated-plasticity Model → elastoplastic native Card. Preserve the other stored families as explicit
typed readers: reference elastic, linear viscoelastic, Ogden-Prony, neutral solver and neutral hyperelastic.
The UI/API use a discriminant, never infer the family from a title or filename. Direct project card
discovery is mandatory: implement an authorized read-only index with exact ID/pin, family, title,
model pin, material membership when stored, output status and native detail/download routing.
It must enumerate all these existing supported card families without a material/Catalog prerequisite.
Unknown exporter/family records return an explicit unsupported representation, not omission or a fake file.

Freeze list behavior: Materials uses its existing server q/class/offset/limit/name/direction contract
and same-response totals/facets. Canonical Test Data and common Processing Outputs use their complete
authorized project list and local q/type/material filter and stable name-or-key + stable-ID tie-break
sorting, page size 12. The direct card index likewise returns the complete authorized project scope
for local title/solver/family/material filtering, same stable tie-break and page size 12. Show total
after those filters; do not call it a server facet. Material tree paging/loading is explicit, not a
truncated list presented as the whole database. Results reset offset and close off-page preview on
query/filter/sort change; direct detail pins are independent of list-page presence.

Exact reads are mandatory before adapter implementation: add canonical Test Data detail GET accepting
document ID and revision ID, backed by the existing authorized exact snapshot loader. Add optional
revision_id to common Processing Output detail/content and load that exact existing stored revision.
For each included family whose card detail/download currently only reads current, add optional
revision_id using the same authorized existing revision store; keep unpinned legacy behavior unchanged.
Do not return a newer revision when a requested pin is absent. Existing generic/neutral exact routes
are reused. All exact reads verify aggregate ownership and artifact hashes; a missing pin/file is 404
or explicit unsupported, corruption/mismatch fails closed. No DB history migration or revision writes.

Real non-production acceptance corpus must contain two canonical tests on the same stored material,
only one exact TestData→ProcessingOutput→Model→Card derivation chain, and another same-material card
whose generation input differs. The UI separately labels material membership and actual generation,
supports reverse navigation, and never includes the second card in the first test's generated cards.
Use existing fixtures/APIs to prepare this in the isolated DB. Add enough bounded test/card rows to
span two pages (at least 13 for paging regression); multi-page scope checks may use controlled fixtures
but the generation chain and downloads must be actual backend/DB objects and bytes.

Acceptance explicitly changes the current head of a source after saving a result/card, then opens
the old URL/pin and proves old detail and bytes/hash remain exact, with a visible older-input indicator.
Authorization cases: DATASET_READ-only, EXPORT_READ-only, both and neither. A denied optional
Materials/Catalog/other-reader request must not erase a separately authorized direct reader. Test
these scopes at service/DB level and in the browser (real scope identity where the fixture supports it;
label transport-isolated browser denial cases separately). Related-region failure is visible and
retryable locally; partial data is never presented as a complete relation set.

Writer runs typecheck/build, meaningful adapter/query/component regressions and affected backend
unit/contract tests. Cover malformed/mismatched identities, missing association, unauthorized requests,
empty lists, missing/unsupported files, stale saved input, late responses after selection/close,
native-byte preservation and list state restoration. No tests that only mirror implementation.

Main separately validates one realistic stored-object journey on actual backend/PostgreSQL and exact
download bytes/hashes using non-production fixtures. Run Compose preflight, use canonical verified
configuration and fresh isolated test data; preserve persistent volumes. Current daemon initially
failed to connect; installed Docker Desktop was launched. Unavailable environment is recorded as a
blocker, never replaced with mocked success. Browser negative tests may isolate transport failures
but must be explicitly distinguished from real authorization/persistence evidence.

Capture live before/after Materials list, Test Data preview/expanded detail and Solver Card detail at
1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160, zoom 100%. Main opens originals and 100%-pixel
crops of header/navigation/controls/curve or native preview; independently judge information hierarchy,
engineering flow and responsive/wide-screen composition. Record real data scale and geometry;
physical Windows 4K readability remains separate. Owner disposition stays pending until reviewed.

At 1366 and 3840 also capture long names, empty/error/unauthorized states. Normal-surface identity
must be fully readable or have an immediate full-value affordance; essential conditions/units and
controls cannot clip. Require no page horizontal overflow, independent tree/list/preview scrolling,
reachable pagination/detail/download/return, visible keyboard focus, and actual keyboard interaction.
Hidden text/tooltips or geometric measurements alone do not establish readability.

Run affected tests, user-guide check, docs-impact and diff whitespace check. Independent final review
reopens current diff/evidence. Commit/push/PR/merge/cutover require separate authority. Completion is
this representative reader only; RD-04 registration/processing/statistics and RD-05 model/solver
expansion, RD-06 cutover and RD-07 retirement stay in program order.
