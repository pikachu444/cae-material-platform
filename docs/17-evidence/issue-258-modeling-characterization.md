# Issue #258 — Modeling behavior characterization

This record characterizes the current Modeling workflow for FE-03 under parent issue #249. The
issue body and the owner-approved frontend refactoring roadmap remain authoritative. Work started
from fetched `origin/main` `8fad879dfc183237815d76f3837feb813bc0aaeb`. This unit adds regression
contracts and a responsibility map; it does not change production React, CSS, API calls, DTOs,
routes, or persisted session shapes.

## Starting-state classification

The labels below describe production behavior on the starting SHA. Characterization tests added by
#258 make existing behavior observable but do not promote a partial or missing behavior to complete.

| Area | Status | Current evidence and boundary |
| --- | --- | --- |
| Materials → Modeling handoff | Partial | A pinned Material detail writes its exact Material revision before `Start Modeling`, and a Test Data detail writes its exact Test Data revision. The generic Material action does not bind a State or Test Data revision, while the Test Data action does not bind Material or State. |
| Exact URL context | Complete for supplied current refs | When Material and State IDs plus revisions are present, they win over the first list entries and are persisted. A mismatched Material or State revision is blocked and is not replaced by that aggregate's current head. |
| Context-free entry | Partial | Without a matching query or restorable session, Modeling selects the first Material and first State returned by the current-head endpoints. That behavior is recorded as risk, not as an accepted exact-context contract. |
| Modeling session | Partial | The browser-local v4 aggregate preserves exact refs, active stage, graph selection, reload state, invalidation evidence, and recovery. v1–v3 records migrate to v4. There is no durable server session identity or cross-browser read-back. |
| Data → Process → Fit → Export continuity | Complete for the characterized local journey | Existing integration coverage exercises exact Test Data selection, previews, immutable Process/Fit output saves, explicit fit choice and reason, stage navigation, retry, repin protection, and Export gating. |
| Candidate, selection, and saved-result distinctions | Partial | The reducer distinguishes `fitCandidate`, `selection`, and `processingOutput`, and invalidates downstream pointers in order. Production Fit does not currently set `fitCandidate`, and the selected and saved fit may use the same Processing Output identity. |
| Export delivery pin | Complete | Successful delivery validates the exact source/target response and writes the returned Solver Card ID and exact revision to the session `exportArtifact` pointer. |
| Materials read-back | Partial | The delivery receipt and session pointer retain the exact Solver Card revision, but the visible `Open solver card` route contains the card ID without a revision query. |
| Activity delivery projection | Missing | Delivery activity is not projected from the durable delivery receipt. The current Activity list is browser-local preview/download activity and the Export test explicitly observes no Activity receipt projection. |
| Responsibility and dependency map | Missing before #258; complete in this record | No FE-03 map or consolidated silent-fallback inventory existed on the starting SHA. The sections below provide the bounded input for FE-04. |

## Primary acceptance journey

| Part | Characterized journey |
| --- | --- |
| Setup | A user starts from an exact current Material revision, exact Material State revision, and exact canonical Test Data revision with a compatible Mapping Profile. Existing synthetic non-production fixtures supply processing and fitting capabilities. |
| Actions | Open Modeling with the exact context; inspect Data; preview and explicitly save Process; run and compare Fit candidates; select one with a reason and save the immutable result; open Export; select a target, review mappings, acknowledge an approximation when required, and create a Solver Card. |
| Visible outcome | The selected exact context remains visible, the persistent graph and stage controls reflect Data/Process/Fit, successful saves are identified as current, Export remains a separate explicit stage, and delivery shows the immutable card and receipt identities. |
| Persistence/read-back | Browser session v4 retains exact record refs, stage and graph selection across reload. Process/Fit outputs and delivery receipts are server resources. A successful delivery pins the exact Solver Card revision in `exportArtifact`; the subsequent Materials URL itself remains unpinned and is therefore partial. |
| Preserved contract/state | IDs and revision IDs travel together. Preview is not saved output; candidate choice, saved Fit output, Export preview, delivery receipt, and Solver Card remain distinct concepts. Upstream changes clear, stale, or mark downstream pointers for regeneration without rewriting immutable outputs. |
| Recovery | A stale query revision fails closed. Preview and delivery failures keep the last valid exact inputs and expose retry. A changed source, candidate, target, or Material context invalidates the relevant downstream current pointers. Reload restores exact refs only when the current response still contains the same ID and revision. |
| Owned scope | Four characterization test files, this evidence record, the v4 user-flow correction, the FE-03 roadmap link, and the guard baseline provenance SHA. |
| Forbidden shortcuts | No `latest`, first-item, current-head, global-output, or another-session fallback is asserted as the normal exact journey. No runtime refactor, layout normalization, new API/DTO, durable-session design, Activity feature, or FE-04 extraction is included. |
| Exact acceptance | Focused and full frontend regression, guard, build, canonical Compose preflight/recreate/health, existing Modeling browser consistency flow, documentation gates, clean diff, and one Balanced independent audit. |

## Characterization anchors

| Contract | Code boundary | Regression anchor |
| --- | --- | --- |
| Pinned Material `Start Modeling` stores the exact displayed revision | `apps/web/src/material-library.tsx` | `material-library-pinned.test.tsx` — `starts Modeling with the exact pinned Material revision in the browser session` |
| Exact URL Material/State beats list order; stale revisions fail closed | `apps/web/src/material-modeling-workspace.tsx` | `material-modeling-workspace.test.tsx` — exact URL, stale Material, and stale State cases |
| Exact Data/Process/Fit/Export continuity and stage persistence | `apps/web/src/common-processing-workbench.tsx` | `common-processing-workbench.test.tsx` — `characterizes exact Data, Process, Fit, and Export continuity with explicit recovery` |
| Successful delivery pins the exact card revision in the session | `apps/web/src/modeling-target-preview.tsx` | `modeling-target-preview.test.tsx` — `delivers only the current preview and binds the required acknowledgement identity` |
| Ordered invalidation, reload, migration, and explicit pointer clearing | `apps/web/src/modeling-session-context.ts` | `modeling-session-context.test.ts` |

## Fallback and coupling inventory

These paths are observations of the current implementation. They are intentionally not approved as
normal exact-context behavior by #258.

| Path | Current behavior | Classification/risk |
| --- | --- | --- |
| Material detail → Modeling | Stores exact Material only, then routes with stage and family. | Partial: State and Test Data remain unbound. |
| Test Data detail → Modeling | Stores exact Test Data only, then routes with stage and inferred family. | Partial: Material and State remain unbound. |
| Modeling without query or restorable Material | Uses `items[0]` from the current-head Material list. | Partial: order-dependent first-item fallback can create unintended context. |
| Modeling without query or restorable State | Uses `states[0]` from the selected current Material detail. | Partial: order-dependent first-item fallback can create unintended condition context. |
| Prior browser session whose Material revision is no longer listed | Selects a compatible current Material and shows a warning. | Partial: current-head substitution is visible but not exact revision recovery. Query-supplied stale refs instead fail closed. |
| Legacy Test Data focus | If exact selected refs exist but no valid focused ref is stored, focus uses the first exact ref. | Partial: compatibility-only `legacy-focus` behavior; exact ref order is persistence/display data, not authority for new selection. |
| Fit candidate/selection/save | The reducer has separate pointers, but current Fit writes the saved Processing Output and selection without a production `fitCandidate` pointer. | Partial: semantic states are coupled to one output identity. |
| Export → Materials | Session/receipt contains `solver_card_revision_id`; the navigation URL is `/materials/{material}/cards/{card}`. | Partial: visible read-back resolves by aggregate/current route rather than the delivered revision. |
| Export → Activity | No durable delivery-receipt projection is shown. | Missing: existing browser-local preview/download activity is not delivery read-back. |

## Responsibility and dependency map

| Boundary | Current responsibility | Depends on / feeds | FE-04 constraint |
| --- | --- | --- | --- |
| `app.tsx` | Parses application routes, lazy-loads Modeling/Test Data/Materials pages, and supplies navigation and connection callbacks. | Route string → workspace component; shell/permissions surround the feature. | Keep route registration/composition here; do not move Modeling orchestration into the application shell. |
| `material-library.tsx` and `canonical-test-data-workbench.tsx` | Own Materials and Test Data user actions that seed the browser Modeling session and navigate to `/modeling`. | Exact source resource → session adapter → app navigation. | Handoff creation must become an explicit exact-source contract before removing compatibility calls. |
| `material-modeling-workspace.tsx` | Resolves family, Material, State, query refs and restored refs; blocks stale query revisions; connects the family engine and Common Workbench. | Materials API + session reducer → exact live context → Common Workbench. | Candidate exact-source/session controller boundary; preserve fail-closed query behavior and document current-head fallbacks separately. |
| `modeling-session-context.ts` | Defines browser-local v4 state, v1–v3 migration, exact record refs, reducer events, invalidation, stale evidence, and persistence. | All Modeling producers/consumers; session storage. | Keep reducer and migration pure/testable. Do not add server identity or change the public shape in FE-03. |
| `common-processing-workbench.tsx` | Owns method registries/defaults, source resolution, Data/Process/Fit orchestration, async previews/saves, workspace persistence, graph/rail composition, and Export stage composition. | API/types, session callbacks, stage components, family workbenches, plot, and Export boundary. | This is the registered hotspot for #259. Extract one responsibility at a time under characterization tests. |
| `modeling-stage-shell.tsx` and `design/modeling-workspace-layout.tsx` | Present stage navigation and shared workspace regions. | Workflow task + session state → user commands/layout. | Preserve DOM/interaction contracts during structural movement; visual normalization belongs to FE-05/#260. |
| `modeling-data-intake.tsx` and `modeling-process-panel.tsx` | Present Data intake and Process controls while Common Workbench owns most orchestration state. | Exact sources/methods/preview callbacks from Common Workbench. | Move orchestration only after pure registry and controller boundaries are established. |
| `modeling-fit-decision*.ts(x)` and `modeling-fit-output.ts` | Validate candidate decision input and construct/validate saved Fit output contracts. | Fit preview/candidate + user reason → immutable output/selection refs. | Preserve the currently observed candidate/selection coupling until a separately authorized semantic change. |
| `modeling-target-preview.tsx`, `modeling-target-delivery.tsx`, `modeling-target-preview-result.tsx` | Validate exact Export prerequisites, create preview/delivery, present results, and pin `exportArtifact`. | Exact selected output/IR/Neutral refs + target → delivery receipt/card revision. | Candidate Export boundary; preserve request/response identity checks and retry behavior. |
| `api.ts` and `types.ts` | Shared HTTP compatibility surface and cross-feature DTO definitions. | Every stage and feature boundary. | FE-03 makes no API/type changes; feature ownership migration is FE-08/#263. |
| `styles.css` and `design/layout.css` | Legacy global feature selectors and shared/route layout policy. | All visible Modeling regions. | No #258 edits. CSS ownership is FE-06/#261 and Modeling visual normalization is FE-05/#260. |

Dependency direction targeted by later structural work is
`app route → Modeling feature controller → stage/domain boundaries → shared design primitives`.
The current map documents deviations without implementing that movement in this issue.

## Bounded FE-04 candidates

Each candidate is independently reviewable and must preserve the anchors above. They are planning
inputs for #259, not work authorized by #258.

1. **Pure registry:** move method registries, family defaults, labels, and request transformations from
   the Common Workbench behind pure functions with unchanged request snapshots.
2. **Exact-source/session controller:** isolate Material/State/query/session resolution and session
   events while retaining fail-closed stale queries and explicitly named compatibility fallbacks.
3. **Process orchestration:** move Process preview/commit/retry state behind a feature-owned controller;
   keep the stage panel presentational and preserve last-valid evidence.
4. **Fit restore/selection:** isolate exact saved-output restore, candidate comparison, explicit selection
   reason, and invalidation without silently inventing a `fitCandidate` identity.
5. **Export boundary:** move exact prerequisite, preview, acknowledgement, delivery, and read-back
   coordination behind a bounded feature API while preserving the exact `exportArtifact` revision.

## Validation applicability

- Production DOM/layout and CSS changed: **N/A**. No production React/CSS file is edited, so tracked
  screenshot manifests, new five-viewport before/after images, and visual owner approval are not #258
  acceptance artifacts.
- Public API, DTO, route, persisted session shape, backend, database, schema, and migration changed:
  **N/A**. Their implementation and integration suites are outside this characterization-only delta.
- Live browser consistency: **applicable** through the repository's existing canonical Modeling
  consistency capture, used to check stage/reload/recovery, console errors, and overflow without
  treating unchanged pixels as a visual redesign.
- Merge and downstream FE units: **not authorized**. The Draft PR remains open; FE-04 and later work do
  not start from this unit.

## Verification record

| Gate | Result |
| --- | --- |
| Focused characterization regression | PASS — 4 files, 56 tests (`material-library-pinned`, `material-modeling-workspace`, `common-processing-workbench`, and `modeling-target-preview`). |
| Full web regression | PASS — 64 files, 376 tests. The frontend guard's own 17 tests also pass. |
| Frontend guard | PASS — 0 violations and the same 15 registered baseline warnings. The only baseline edit is `sourceSha` set to the branch merge-base `8fad879dfc183237815d76f3837feb813bc0aaeb`; counts, exceptions, owners, and follow-ups are unchanged. |
| Production web build | PASS — TypeScript and Vite build pass. The existing `common-processing-workbench` lazy chunk is 128,270 raw bytes, a warning with 2,730 bytes of hard-limit headroom. No production source changed. |
| Canonical Compose preflight and health | PASS/PARTIAL — read-only preflight passed before and after recreate; canonical postgres and API are healthy and web is running. Recreate preserved volumes as required. The canonical seed exited 1 because the preserved #246 Catalog record already had an exact binding and the idempotent seed POST returned `CMP-CATALOG-0018`; no data was deleted and the unchanged seed was not replayed. |
| Isolated clean Compose seed | PASS — the same base composition with only an isolated project/volumes and non-conflicting host ports completed migrate, full demo seed, API health, and web health. The temporary project and its two temporary volumes were removed after the browser checks; canonical data was untouched. |
| Modeling browser consistency | PARTIAL — on the clean isolated seed, `--only-modeling-consistency` reached 1366×768 Fit, then the existing geometry assertion failed: expected drawable width 728, observed 1,038. A narrower `--only-modeling-data-session` run completed the pin-free session shell plus Data/reload checks at all five required and two wide viewports, then failed in the final invalid-mapping fixture because `Independent source column` was absent. Both failures occur on unchanged production DOM/CSS; no failed staged screenshots were published or registered, and #258 did not expand into FE-05 visual work. |
| User guide and documentation impact | PASS — 20 guide documents, 119 current captures, 161 classified Markdown files, 665 local links, and 2,046 images; documentation impact reports 8 changed files and 0 visual sources. |
| Diff hygiene | PASS — `git diff --check`. |
| Backend/DB/schema/migration regression | N/A — no backend, schema, migration, contract, API, or DTO implementation changed. Compose was used only for the applicable live frontend characterization. |
| Tracked screenshots/manifest and five-viewport before/after | N/A — no production React/CSS/DOM/layout change. The browser runs above are runtime consistency checks, not new visual approval evidence. |
| Balanced independent audit | PASS — `independent_auditor_terra_high` returned `approve` after checking scope, exact-context tests, fallback classifications, v4 migration wording, guard provenance, validation evidence, and the explicitly partial browser result. |
