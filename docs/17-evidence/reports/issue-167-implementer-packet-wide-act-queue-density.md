# Issue #167 — ACT-QUEUE wide-density implementer packet

Date: 2026-07-30
Owner: active `/root` main agent
Writer: one configured `implementer_luna_max`

## 1. Bounded objective

Replace the stale, deliberately under-filled ACT-QUEUE normal references with a role-correct compact
work table that exercises the existing 50-request list contract and remains useful at 1366×768,
1440×900, 1920×1080, 2560×1440 and 3840×2160. Preserve all review-decision, local-history,
exceptional-state and accessibility contracts. This is static #167 reference work only.

## 2. Authority inspected by the main agent

- GitHub issue #167 and `AGENTS.md`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`, especially wide-screen elasticity and
  Activity;
- `docs/01-product/desktop-engineering-ui-spec.md`, especially the Activity component contract;
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-02, Q-09 and Q-20;
- the current ACT-QUEUE HTML/CSS/JavaScript, capture, validator, staging index and all seven current
  approval images;
- current production `apps/web/src/material-library.tsx`, where
  `listReviewRequests(config, { limit: 50 })` feeds role-filtered pending/decided rows;
- current API client and immutable review-request/decision contracts.

The current 1920×1080 User normal image is rejected by the main agent: three short rows occupy only
the top of the workspace and leave most of the viewport blank although the API already returns a
representative page. It also places a User's own pending review request under `Needs attention`;
production and product contracts place it under `In progress`. The old fresh review predates the
strengthened Q-20 rule and does not authorize handoff.

## 3. Writer-owned paths

The writer may modify only:

- `docs/00-research/ux-service-reference/activity-queue-normal.html`
- `docs/00-research/ux-service-reference/activity-queue.css`
- `docs/00-research/ux-service-reference/activity-queue.js`
- `docs/00-research/ux-service-reference/capture_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/validate_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/activity-queue-wave04.staging.json`
- the seven existing `activity-user-*` / `activity-reviewer-*` approval PNG and measurement pairs;
- the existing ACT-QUEUE evidence-only state PNG/measurement/state-evidence files;
- new normal wide-support PNG/measurement pairs for User and Reviewer at 2560×1440 and 3840×2160.

Do not edit the common manifest, inventory, common evidence report, shared CSS/JavaScript, production
React/CSS, GitHub, commits, pushes, PRs or any other family.

## 4. Product and data contract

1. Keep one flat Activity work queue, not KPI tiles, nested cards or a dashboard.
2. The queue uses a compact semantic table with the visible columns
   `Task | Request reason | Status | Updated | Action`.
3. Do not show Material/Owner names, UUIDs, hashes or exact revision identifiers in the normal table:
   the current response does not supply readable Material or actor names. Exact identifiers remain
   Advanced evidence.
4. Build one deterministic synthetic, non-production 50-request page per role from the supported
   review response fields. Use varied task types, supplied human reasons, lifecycle state and time;
   do not create filler prose or duplicate rows with only an incremented label.
5. User normal:
   - default selected view is `In progress`;
   - own pending requests appear there with the one browser-local Modeling session;
   - no Review/Approve/Request changes/Record decision action exists.
6. Reviewer normal:
   - default selected view is `Needs attention`;
   - pending requests appear there with one row-level Review command;
   - do not permanently open the decision form.
7. Recent outcomes contain immutable returned decisions and the browser-local solver-card history.
   Do not fabricate a server delivery receipt, release, readable person or additional local session.
8. View selectors must have truthful semantics. If they are tabs, inactive panels are real tabpanels
   and hidden. If they scroll within one queue, do not expose a false tablist/tab contract.
9. The long decision error continues to preserve the exact selected request, non-empty reason and
   choice, reports `Decision not recorded`, and offers only `Retry decision`. Stale authorization
   separately offers only `Refresh access`.
10. Empty, loading, long-row, queue-error and role-blocked evidence retain their state-specific
    truth boundaries; the 50-row normal fixture must not leak into empty or focused recovery states.

## 5. Layout and responsive contract

- Keep the existing 46 px product shell, compact heading, saved-view strip, flat dividers and status
  bar.
- Normal rows remain compact and do not stretch with viewport height. Use a stable table header and
  tabular numeric/time alignment where applicable.
- The queue body owns independent vertical scrolling with a reserved, perceptually visible track and
  proportional thumb only on real overflow. Pointer wheel, keyboard PageDown and focus-visible
  evidence remain mandatory.
- At 1366/1440, the table retains complete task/reason/status/action access with no page overflow.
- At 1920/2560/3840, increased height reveals more complete rows at the same density. The normal
  page must not leave a dominant avoidable blank region or widen into cards.
- At 3840, the representative normal page must still contain enough contract-backed rows to avoid
  an under-filled work area. Do not solve this by increasing row height or repeating descriptions.
- Long reasons wrap only when needed and remain reachable; normal short reasons do not become a
  paragraph under every task.

## 6. Deterministic evidence

Strengthen capture and validation to record and assert:

- role-selected default view and section ownership;
- exact server request count, pending/decided split and local-history count;
- table headers, visible row count, row-height range and the absence of invented Material/Owner/ID
  columns;
- local scroll height/client height, computed overflow, reserved track, proportional thumb and
  pointer/keyboard consequences;
- 1366/1440/1920 canonical dimensions and hashes;
- User/Reviewer normal 2560/3840 wide-support dimensions, hashes, density and blank-area safety;
- no body/page horizontal overflow, clipping, nested interactive controls, console or page errors;
- named controls, focus-visible, live alerts/loading announcements and preserved recovery behavior;
- all existing exceptional and evidence-only state contracts.

The common manifest must remain untouched. Write final hashes only to the family staging index and
measurements; the main agent integrates lifecycle records serially.

## 7. Required commands

At minimum run:

```powershell
node --check docs/00-research/ux-service-reference/activity-queue.js
python -m py_compile docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python docs/00-research/ux-service-reference/capture_activity_queue_wave04.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

Add a documented capture/validation option for the four 2560/3840 wide-support images and run it.
Audit the writer-owned HTML/CSS/JavaScript against the freshly fetched Web Interface Guidelines.

## 8. Writer handoff

Return:

- changed paths;
- seven canonical and four wide-support image paths and SHA-256 values;
- deterministic command results;
- a concise mapping of the 50-request fixture to User/Reviewer sections;
- any residual risk.

Do not request product-owner approval. The main agent will open every image at original resolution,
complete Q-01–Q-20, prepare the separate reviewer packet and request one fresh read-only review.
