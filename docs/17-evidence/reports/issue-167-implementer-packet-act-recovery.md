# Issue #167 implementer packet — ACT-RECOVERY

Date: 2026-07-30
Writer role: configured `implementer_luna_max`, exactly one writer for this family
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Create the complete three-image `ACT-RECOVERY` approval family:

1. `activity-recovery-blocked-1366x768`
2. `activity-recovery-blocked-1440x900`
3. `activity-recovery-blocked-1920x1080`

The canonical state is `not-configured`. The product has durable Job resources and an opaque
get/retry command, but it does not have a readable Activity projection that joins a failed
calculation to the user's exact Material, Modeling session, stage and selection. The UI must tell
that truth without fabricating a failed row or successful retry.

Also persist same-topology support evidence:

- normal `2560x1440` and `3840x2160`;
- `recovery-empty`, `recovery-loading` and `recovery-action-error` at 1366×768, 1440×900 and
  1920×1080.

This family is independent of the concurrent MOD-PROCESS wide correction. Its approved ACT-QUEUE
dependency is frozen and read-only. Do not change production React/CSS, commit, push, create or
update a PR, or start another family.

## Main-agent product judgment

The user opens Activity because work failed or appears stuck and wants to continue from the exact
engineering context. The current platform cannot safely list such work by readable Material/session
identity. An opaque job ID, failure code or Retry button would look operational while lacking the
required user-task projection.

The reference must therefore preserve the approved Activity workspace and available browser-local
Modeling context, state the unavailable capability once in plain language, and lead to the one safe
action that actually exists: resume/open Modeling. It must not become a large empty error page.

The main agent opened approved ACT-U/ACT-R images at 1440, 1920 and 3840, inspected their static
source, current `ActivityPage`, Modeling session storage, browser-local solver-card history, Job
schema/OpenAPI and the cumulative qualitative checklist. The approved flat queue, compact type,
local scroll and wide-screen row density are the visual authority.

## Authorities and exact truth boundary

- `AGENTS.md`
- `.codex/config.toml` and `.codex/agents/implementer-luna-max.toml`
- `docs/01-product/service-reference-inventory.yaml` (`ACT-X`, `ACT-RECOVERY`)
- `docs/01-product/desktop-engineering-ui-product-spec.md` section 8
- `docs/01-product/desktop-engineering-ui-spec.md` Activity and global workspace contracts
- `docs/01-product/desktop-engineering-user-flows.md`
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-02, Q-09 and Q-20
- `docs/05-architecture/system-architecture.md`
- `contracts/jobs/job-resource.schema.json`
- `contracts/http/openapi.yaml` Job get/retry endpoints
- current production, read-only:
  - `apps/web/src/material-library.tsx` (`ActivityPage`)
  - `apps/web/src/modeling-session-context.ts`
  - `apps/web/src/solver-card-delivery.ts`
  - `apps/web/src/api.ts`
  - `apps/web/src/types.ts`
  - their tests
- approved ACT-QUEUE authority, read-only:
  - `docs/00-research/ux-service-reference/activity-queue-normal.html`
  - `docs/00-research/ux-service-reference/activity-queue.css`
  - `docs/00-research/ux-service-reference/activity-queue.js`
  - approved `activity-user-normal-*`, `activity-reviewer-normal-*` and
    `activity-reviewer-long-decision-error-1440x900` images.

There is no production web API that lists general jobs for Activity or maps them to readable user
tasks. The Bulk Export job list is a different bounded feature and cannot be reused as general
recovery. Do not infer a job from browser-local Modeling state.

## Exact ownership

The writer may create/edit only:

- `docs/00-research/ux-service-reference/activity-recovery-blocked.html`
- `docs/00-research/ux-service-reference/activity-recovery.css`
- `docs/00-research/ux-service-reference/activity-recovery.js`
- `docs/00-research/ux-service-reference/capture_activity_recovery.py`
- `docs/00-research/ux-service-reference/validate_activity_recovery.py`
- `docs/00-research/ux-service-reference/activity-recovery.staging.json`
- ACT-RECOVERY-only canonical, wide, state and measurement evidence under
  `docs/17-evidence/images/issue-167-service-reference/`

The writer may load `activity-queue.css` as a frozen base or copy its measured tokens into the owned
CSS, but may not edit ACT-QUEUE sources or images.

Do not edit:

- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- any `activity-queue*`, MOD-PROCESS or other family-owned file;
- any file under `apps/`;
- any unrelated dirty-worktree file.

Other work exists in the repository. Do not reset, clean, stash, discard, overwrite or reformat
unrelated changes.

## Required normal reference

### Frozen shell and view

- Preserve the approved dark application bar and `Materials | Modeling | Activity`, with Activity
  active.
- Use the same compact Activity heading, quiet Refresh action, saved views and status bar.
- `In progress` is active because the safe continuation is the browser-local Modeling session.
- Keep the flat locally scrolling work table and the exact columns
  `Task | Request reason | Status | Updated | Action`.
- There is no dashboard, card gallery, hero, nested panel stack or permanent side inspector.

### One truthful unavailable boundary

Immediately inside the selected In progress view, use one shallow flat status strip, not a card:

- title: `Failed calculations`;
- plain status: `Not available in Activity`;
- one concise consequence:
  `Activity cannot yet list failed calculations with their Modeling context. Resume the saved
  Modeling session to inspect the current step.`

This statement appears once. Do not repeat it in the page heading, table rows, action column and
status bar with different colors or wording.

User-visible copy must not contain `projection`, `job ID`, `attempt`, `runner`, `manifest`,
`failure code`, `receipt`, `outbox`, `release`, `UUID`, hash or API vocabulary. Do not display a
fake failed calculation row, retry eligibility, progress, success state or server recovery command.
`Not available in Activity` is preferable to exposing the internal state name `not-configured`.

Refresh applies only to the available Activity queue/local context. It never claims to refresh or
discover failed jobs.

### Preserve useful available work

Below the shallow boundary, keep the approved representative In progress data:

- first visible row is the browser-local `Resume Modeling session`;
- context is `DP780 Dual-Phase Steel · Fit · selected model not saved` or an equally concise
  rendering of the same approved local session contract;
- status is `Saved in this browser`;
- one row action `Resume Modeling` is the sole filled primary action;
- the remaining rows are the same representative pending review-request page used by approved
  ACT-U, with no User decision controls.

The local session row is not a failed job and must not be labelled `Retry`. Activating it changes
the simulated destination to the exact saved Modeling context and announces the result.

Use the existing 40 pending requests plus the one local session so larger viewports expose more
truthful rows at the same compact density. Do not stretch rows/prose, fabricate Material/Owner
names, or leave a dominant avoidable blank region. The list scrolls locally and keeps a reserved,
discoverable proportional rail only when it overflows.

### Command and copy hierarchy

- One filled action at most: `Resume Modeling`.
- `Refresh` and saved-view controls remain quiet.
- Avoid generic `Retry` in the normal state.
- No explanatory paragraph beneath every row or control.
- Status-bar copy is concise user context; it does not expose a capability matrix.

## Evidence-only states

Capture each state at 1366×768, 1440×900 and 1920×1080 without adding approval inventory items.

### recovery-empty

- The unavailable boundary remains unchanged.
- No browser-local Modeling session is present and no Resume action is shown.
- Pending review requests may remain if the server queue is available.
- Show one safe quiet action, `Open Modeling`, without calling it recovery.
- Do not show a fake local scrollbar when the rendered list does not overflow.

### recovery-loading

- Preserve the last valid unavailable boundary, local session row and current queue rows.
- Refresh becomes `Refreshing…` and duplicate refresh is disabled.
- Announce that available Activity work is being refreshed; never say failed jobs are loading.
- The shell and table do not blank or change topology.

### recovery-action-error

- Simulate failure to open the saved Modeling session, not a server job retry.
- Preserve the exact local session row, queue, selection and scroll position.
- Show one short inline error adjacent to that row and one `Try again` consequence.
- A later successful action clears the error and opens the same saved Modeling context.

## Responsive, qualitative and accessibility contract

- Canonical targets are exact 1366×768, 1440×900 and 1920×1080 at DSF 1.
- Persist 2560×1440 and 3840×2160 support images and measurements.
- 12–13 px metadata and 14 px primary task text remain stable through 3840.
- Larger height reveals more complete rows at the same row height. Do not scale type, row height,
  status strip or buttons with viewport dimensions.
- The status strip remains shallow relative to the queue and does not become a centered empty-state
  card.
- Table identities and reasons remain readable; text never collides with the local scroll rail.
- Saved-view tabs support ArrowLeft/ArrowRight, Home and End with truthful selection/focus.
- Refresh, Resume/Open Modeling and Try again have focus-visible and measurable consequences.
- There are no nested interactive controls, clipped actions, body/document overflow, console/page
  errors or inaccessible color-only states.

## Deterministic capture and validation

Capture/validator must fail unless:

- every canonical and state PNG has the exact named dimensions and DSF 1;
- normal 2560/3840 support PNGs and measurements are persisted and hashed in staging;
- approved ACT-QUEUE source/image hashes remain unchanged;
- shell, saved views, active In progress state, flat table columns and local status bar match;
- the exact unavailable title/status/consequence appears once and forbidden internal vocabulary is
  absent from the visible normal surface;
- no row claims to be a failed job and no normal action says Retry;
- 41 normal rows are present, with the local session first and 40 server review requests;
- User decision controls are absent;
- Resume is the only filled action and changes the saved Modeling destination;
- Refresh affects only the available queue context;
- empty/loading/action-error preserve the required context and consequences;
- local scrollbar visibility, reserved track, proportional thumb, wheel/PageDown/End and selected-row
  visibility are exercised where overflow is genuine;
- 1366/1440/1920/2560/3840 type and row sizes remain within stable tolerances;
- large-screen row count increases without dominant blank area or stretched prose;
- there are zero console/page/resource errors and zero body/document overflow.

The staging lifecycle remains `pending`. The main agent alone integrates the common manifest,
inventory and shared report after deterministic and original-resolution review.

Run at minimum:

```text
python docs/00-research/ux-service-reference/capture_activity_recovery.py --help
python docs/00-research/ux-service-reference/validate_activity_recovery.py --help
python docs/00-research/ux-service-reference/capture_activity_recovery.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_activity_recovery.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_recovery.py docs/00-research/ux-service-reference/validate_activity_recovery.py
node --check docs/00-research/ux-service-reference/activity-recovery.js
git diff --check
```

## Writer handoff

Return:

- exact files changed;
- commands and pass/fail results;
- three canonical paths, dimensions and SHA-256 values;
- 2560/3840 support paths, dimensions and SHA-256 values;
- state evidence paths;
- row/type/scroll/large-screen and interaction measurements;
- any residual limitation.

Do not declare visual approval, edit shared integration files, commit or start another family.
