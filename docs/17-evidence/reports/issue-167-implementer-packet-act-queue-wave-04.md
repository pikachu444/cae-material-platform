# Issue #167 implementer packet — WAVE-04 / ACT-QUEUE

Date: 2026-07-29
Author: active `/root` Sol XHigh main agent
Writer role: configured `implementer_luna_max`, exactly one writer for this family
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## 1. Bounded outcome and dependency edge

Create the complete seven-image Activity approval bundle:

1. `activity-user-normal-1366x768`
2. `activity-user-normal-1440x900`
3. `activity-user-normal-1920x1080`
4. `activity-reviewer-normal-1366x768`
5. `activity-reviewer-normal-1440x900`
6. `activity-reviewer-normal-1920x1080`
7. `activity-reviewer-long-decision-error-1440x900`

Within this one family, freeze the ACT-U shared queue topology first, then derive ACT-R from it.
This is static service-reference work only. Do not modify production React/CSS, common
manifest/inventory/evidence, current user-guide screenshots, GitHub or git state.

## 2. Product task and main-agent judgment

Activity is a compact role-aware work queue, not a dashboard, audit database or administration
surface. A normal user sees only their pending requests, browser-local Modeling resumptions and
solver-card history. A Reviewer sees requests needing a decision, in-progress work and recent
outcomes, then opens one bounded decision surface without sacrificing queue context. Administrator
governed operations will be frozen in later Administration families.

Use a dense, flat desktop grammar: aligned queue rows and dividers, restrained selection and readable
12–14 px typography. Do not use KPI tiles, large cards, a role selector, fake person/item names,
owners, publish controls, UUIDs, hashes or a permanent third inspector. The queue/results area must
dominate the viewport and long content must expose discoverable local scrolling.

## 3. Authorities inspected by the main agent

- `AGENTS.md`
- `docs/01-product/service-reference-inventory.yaml` (`ACT-U`, `ACT-R`)
- `docs/01-product/desktop-engineering-ui-product-spec.md` Activity queue section
- `docs/01-product/desktop-engineering-ui-spec.md` A-01–A-03 and Activity UI-spec entries
- `docs/01-product/visual-acceptance-matrix.md`, including Q-01–Q-11
- approved shared shell/navigation references
- reference-only Activity captures:
  `docs/17-evidence/images/uxc-00d-responsive-design/activity-1440x900.png` and
  `docs/17-evidence/images/desktop-engineering-ui/dui-01/after/activity-1440x900.jpg`
- current contracts:
  `apps/web/src/material-library.tsx` (`ActivityPage`, `ReviewAction`),
  `apps/web/src/material-library-activity.test.tsx`,
  Activity-related `apps/web/src/api.ts`, `apps/web/src/types.ts`, styling and session/card history

The current review API does not expose reliable user-facing material/request/actor display names.
Normal rows therefore use task type, reason, state and time. Raw identifiers stay in Advanced. Do
not fabricate missing domain semantics to make the screen look populated.

## 4. Preserved role/state contracts

| Surface | Contract represented |
| --- | --- |
| shared shell | normal navigation `Materials | Modeling | Activity`, Activity active |
| user pending | only the signed-in user's pending requests; no decision controls |
| local continuation | browser-local Modeling session may provide a truthful resume row |
| card outcomes | browser-local delivered solver-card history may provide truthful recent rows |
| reviewer queue | pending requests available to Reviewer/Administrator |
| review action | one selected request, Approve or Request changes, non-empty reason required |
| user-role block | User cannot submit a review decision |
| queue error | current/local rows and selected context remain; safe Retry |
| stale/unauthorized | request and typed reason remain visible; decision not reported as successful |

Recommendation, selection, saved result, review request, decision, release and delivery remain
distinct. A Reviewer decision does not release or publish an artifact.

## 5. Shared queue topology

- Use the approved compact application shell and a compact `Activity` title/context row.
- Present three compact queue sections or saved views:
  `Needs attention | In progress | Recent outcomes`.
- Rows are table/list-like, aligned and divider-led. Each row shows only truthful task type, concise
  reason/context, state and relative/absolute time available from the fixture.
- Avoid nested cards and oversized section chrome. Use sentence case, normal/medium weights and
  restrained current-row fill/leading accent.
- The queue is the dominant flexible region. A narrow filter/saved-view rail is allowed only if it
  provides meaningful role/status filtering and follows the approved compact navigator grammar.
- Long queues scroll locally with a visible, reserved scrollbar rail that does not overlap row text.
  Horizontal overflow must not be required for normal rows; a genuinely long identity or reason is
  reachable through wrapping, disclosure or a bounded local horizontal rail.
- Empty/loading/error states preserve the shell and queue geometry.

## 6. ACT-U normal at three viewports

- User role is communicated as context, not an interactive role switch.
- `Needs attention` contains only the user's own pending request work and no Review/Approve/Request
  changes command.
- `In progress` may include a truthful browser-local Modeling resume row with one `Resume Modeling`
  action when the fixture establishes it.
- `Recent outcomes` may include delivered solver-card history with a real `Open card` path.
- A row without a valid next action remains informational; do not add arbitrary Details buttons.
- Use exactly one filled primary action in the current context at most.
- At 1366×768, body/data text remains 14 px and metadata 12–13 px; use scrolling instead of shrinking.

## 7. ACT-R normal at three viewports

- Preserve the same ACT-U shell, saved views, row density, columns and scroll behavior.
- `Needs attention` is the initial dominant queue and contains truthful pending review requests.
- One selected request exposes one `Review` action. The decision UI opens in a bounded in-place or
  graph-adjacent-style region while the queue stays wider; never create a permanent inspector.
- The decision surface names Approve and Request changes as distinct choices and requires a
  non-empty reason. No action is reported successful before the API succeeds.
- In-progress and recent-outcome rows remain available without turning the screen into a dashboard.
- Do not add publish/release commands, person names, owner fields or request item names unavailable
  from the contract.

## 8. Reviewer long-decision-error at 1440×900

- Use enough realistic queue rows and reason length to force local vertical scrolling.
- Keep the selected request visible or deterministically recoverable; the scrollbar must not overlap
  its text or controls.
- The Reviewer has selected a decision and typed a non-empty realistic reason.
- Show an inline decision failure tied to the attempted action. Preserve the request, decision,
  reason and all current queue rows; offer Retry or a safe repeated decision command.
- Do not clear the form, move the request to Recent outcomes or call the decision successful.
- The decision region is bounded and locally scrollable if required. Page/body overflow is forbidden.

## 9. Evidence-only states and interactions

Persist independently named PNGs and state/measurement JSON at all three viewports:

### ACT-U

- empty with one next command;
- loading with local Modeling/session/card history preserved;
- long-row containment and local scrolling;
- queue error with current/local rows preserved and Retry.

### ACT-R

- user-role decision blocked;
- stale or unauthorized review with selected request/reason preserved;
- decision error with reason/request preserved.

Record deterministic pointer and keyboard outcomes for saved-view switching, row selection, queue
scroll, focus-visible, Review open/close, decision choice, reason validation, duplicate-submit
blocking, retry and selected-row restoration. Loading/error announcements must be local and
accessible.

## 10. Source ownership

The writer may create/edit only ACT-QUEUE WAVE-04 paths:

- `docs/00-research/ux-service-reference/activity-queue-normal.html`
- `docs/00-research/ux-service-reference/activity-queue.css`
- `docs/00-research/ux-service-reference/activity-queue.js`
- `docs/00-research/ux-service-reference/capture_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/validate_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/activity-queue-wave04.staging.json`
- ACT-U/ACT-R-only PNG/measurement/state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`

Reference shared sources read-only. Do not edit approved files, shared CSS/JavaScript, common
manifest/inventory/evidence, production paths or MOD-EXPORT files. Another writer is active;
preserve unrelated edits and never reset, clean, stash, discard or overwrite them.

## 11. Deterministic and qualitative gates

The validator must fail unless:

- all seven approval images have exact viewport/dimensions/device scale, hashes and pending lifecycle;
- ACT-U topology is identical across roles and ACT-R is a bounded role extension;
- queue/result width dominates and no KPI/card-dashboard or permanent inspector topology appears;
- user controls contain no decision action; reviewer decision requires a non-empty reason;
- all visible names/fields/actions are supported by current contracts;
- local queue and decision scroll rails are visible when overflow exists and never cover row text;
- normal rows require no document horizontal scroll and all long identities/reasons remain reachable;
- empty/loading/error/stale/unauthorized states preserve applicable context and one safe recovery;
- semantic list/table/controls, focus-visible, accessible names, live error/busy announcements and
  keyboard consequences pass;
- zero console/page/resource errors, nested interactive controls and document/body overflow;
- the legacy-selector report is zero for `page-stack`, `page-heading`, `content-card`,
  `module-material-card`, `hero-actions`, `eyebrow`, `status-badge`, `count-chip`.

Before returning, apply Q-01–Q-11 from the visual acceptance matrix to each original-resolution
approval image and applicable state. Q-01, Q-02, Q-03, Q-09 and Q-11 require explicit evidence;
graph-only items may be not applicable only with a reason. Scores and automated geometry do not
replace qualitative inspection.

Run both helpers with `--help` before source, then at minimum:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_activity_queue_wave04.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
node --check docs/00-research/ux-service-reference/activity-queue.js
git diff --check
```

## 12. Handoff

Return exact changed files, commands/results, seven image paths/viewports/SHA-256 values, evidence
paths, Q-01–Q-11 self-review and residual risks. Open all seven approval targets and representative
states at original resolution. Do not edit shared integration files, request product-owner approval,
commit or start another family.
