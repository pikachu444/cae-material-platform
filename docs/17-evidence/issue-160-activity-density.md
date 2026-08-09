# Issue #160 Task 2 — Activity compact density evidence

## Disposition

The bounded Task 2 implementation is present and passes the automated compact-token, geometry,
role, recovery, and browser-capture gates. It does **not** claim that #160 is complete because this
worktree implementation has not been published, merged, or synchronized in delivery tracking. By the
2026-08-09 Product Owner disposition, the real Windows 4K 100%/150%/200% comparison and final physical-
readability classification are deferred to #223 as the last #117 unit and no longer block #160 after
the Task 2 merge. Exact display-density profiles, defaults, persistence, reset behavior, and automatic
selection remain owned by #221; product-wide application remains owned by #184.

Authority was the open #160 Task 2 unit on `main@00955c83ffc21da97f38a58884079a33691b789d`.
Existing behavior was **partial**: Task 1 supplied the role-correct queue, exact revision decisions,
local history, and recovery, but Activity did not consume a shared compact semantic baseline and its
3840-pixel table stretched to 3754 px. This change addresses only that missing token/geometry scope.

## Primary user journey

1. **Setup** — use the deterministic synthetic demo with User, Reviewer, and Administrator personas,
   immutable prior decisions, pending exact-revision requests, and browser-local solver-card history.
2. **Actions** — a Reviewer opens Activity, switches among `Needs attention`, `In progress`, and
   `Recent outcomes`, opens a request, enters a decision reason, and attempts a decision. User and
   Administrator open their default view without decision controls.
3. **Visible outcome** — saved-view tabs, complete task/reason/status/time columns, row actions, and a
   genuine long-history scrollbar remain visible and reachable from 1366×768 through 3840×2160.
4. **Persistence/read-back** — server review requests and immutable decisions are read from the API;
   solver-card opens/downloads remain distinct browser-local history. A reload reads the same
   role-correct server state and local history source.
5. **Preserved contract/state** — Task 1 exact revision, requester snapshot, decision, publication,
   separation-of-duties, and recovery contracts are unchanged. User and Administrator never acquire
   Reviewer decision actions.
6. **Recovery** — a simulated 503 retains the exact request and entered reason; the recovery surface
   keeps the selected-model revision and exposes `Open exact selection`.
7. **Owned scope** — shared compact semantic token declarations, Activity token consumers, semantic
   table columns, wide table geometry, capture assertions, evidence, and current user guidance.
8. **Forbidden shortcuts** — no resolution/DPR media rule, CSS `zoom`, blanket scale transform,
   fabricated server request, filler prose, mutable history, or display-profile policy.
9. **Negative cases** — normal sparse queues have no fake local rail; long history has real overflow;
   non-Reviewer personas have no decision actions; a failed decision preserves the reason.
10. **Exact acceptance** — affected Vitest/contracts, production build, deterministic 13-image
    Activity capture, Q01–Q20 disposition, five-viewport measurements, legacy selector report,
    documentation gates, independent read-only review pass, and bounded Product Owner visual approval.
    Actual Windows 4K physical-readability approval is the explicit #223 follow-up, not Task 2 acceptance.

## Implemented baseline and later shared names

At the #160 capture boundary the declarations lived in `apps/web/src/design/tokens.css` under
Activity-scoped `--ux-compact-*` names. #161 later promoted the same computed Activity values to
shared semantic names so common primitives and other workspaces can consume them without a private
route scale. This historical evidence still describes the captured geometry; the mapping below keeps
its source terminology auditable.

| #160 capture name | Current shared name | Value | Activity consumers |
| --- | --- | ---: | --- |
| `--ux-compact-data-font-size` | `--ux-data-font-size` | 13 px | saved-view tabs, reason, row action |
| `--ux-compact-emphasis-font-size` | `--ux-emphasis-font-size` | 14 px | task identity |
| `--ux-compact-metadata-font-size` | `--ux-metadata-font-size` | 12 px | role/count/description, status, updated time, error/recovery metadata |
| `--ux-compact-table-heading-font-size` | `--ux-table-heading-font-size` | 11 px | table heading |
| `--ux-compact-control-min-height` | `--ux-control-min-block-size` | 36 px | row action |
| `--ux-compact-row-min-height` | `--ux-work-row-min-block-size` | 46 px | request/history row minimum |
| `--ux-compact-pane-padding` | `--ux-pane-padding` | 12 px | local queue pane |
| `--ux-compact-cell-padding-block` | `--ux-cell-padding-block` | 8 px | section heading, table heading/cell |
| `--ux-compact-cell-padding-inline` | `--ux-cell-padding-inline` | 7 px | section heading, table heading/cell |
| `--ux-compact-wide-content-max` | `--ux-comparison-table-max-inline-size` | 166 rem | local queue pane, section heading, table |

The semantic `colgroup` keeps `Task | Request/recovery reason | Status | Updated | Action` at
`20% | 48% | 12% | 12% | 8%`. At 3840 the centered local queue pane is 2656 px wide and its
scrollbar-adjacent table is 2602 px wide; it is not a 1920 px work island and the surrounding
workspace still spans the viewport. Small/standard desktop layouts retain the existing compact flow.

## Environment and capture provenance

- `cmp-local-demo` passed Compose preflight. Its preserved database then returned a review-lifecycle
  409 during seed, so that stale canonical environment was rejected without deleting volumes or
  replaying the same failed seed.
- Acceptance used the preserved Task 1 final `cmp-issue160-final` volumes. Migration completed, API
  and PostgreSQL were healthy, and the current web image was rebuilt from this worktree.
- Before originals are Task 1 on latest `main`. Missing wide history references were reproduced by a
  detached read-only `main@00955c8` frontend connected to the same API. After captures use the current
  frontend and identical server state.
- Long history contains 26 real server outcomes plus 20 bounded synthetic, non-production
  browser-local solver-card activities. These are stored in the product's existing session history,
  not inserted as server review requests. Normal queues remain sparse and truthful.
- Chromium capture uses browser zoom 100%, CSS viewports 1366×768, 1440×900, 1920×1080,
  2560×1440, and 3840×2160, with `devicePixelRatio=1`.
- The active Windows display is `DISPLAY5`, 2560×1440, 96 DPI, scale 100%. No active 3840×2160
  display is available. Therefore actual Windows 4K 100%/150%/200%, its CSS viewport/DPR, original
  pixels, crops, and Product Owner physical-readability classification are **deferred**, not emulated
  as acceptance. #223 owns that final actual-device verification after #162 Task 2; it does not block
  #160 once the bounded Task 2 implementation is merged and delivery tracking is synchronized.

The immutable paths, crop rectangles, dimensions, and hashes are in the
[visual evidence sidecar](images/issue-160-activity-density/visual-evidence.yaml). Every final original
and every 1:1 crop was opened at original resolution.

## Before/after comparison

The five before originals are under `images/issue-160-activity-density/before/`; the thirteen after
state originals remain canonical under `../user-guide/images/current/`. Matching 1920/2560/3840
shell/header, saved-view, grid, action, and local-scrollbar crops are under
`images/issue-160-activity-density/crops/{before,after}/`.

The main measurable change is semantic linkage and related-region geometry. Before, the 3840 table
ran from x=43 to x=3797 (3754 px). After, the local pane runs from x=592 to x=3248 (2656 px), while
the table runs from x=619 to x=3221 (2602 px) with 27 px internal gutters and an adjacent local
scrollbar. At 2560 the table still expands to 2466 px. The accidental generic `.ux-page` typography
is replaced by the authorized compact baseline: task 14 px, data/tab/action 13 px, metadata 12 px,
and heading 11 px. This is not a high-DPI tier decision.

## Five-viewport measurements

All values are live Chromium CSS pixels at zoom 100% and DPR 1. Shell is application bar + command
bar. `History` is `clientHeight/scrollHeight`; every listed long-history state has genuine overflow.

| Viewport | Shell | Workspace | Table x / width | Queue-to-table gutter | Row | Type task/data/meta/head | Action | History | H overflow |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| 1366×768 | 46+38 | 1366 | 47 / 1272 | 27 | 52.5 | 14/13/12/11 | 36; 6 | N/A | no |
| 1440×900 | 46+38 | 1440 | 47 / 1346 | 27 | 52.5 | 14/13/12/11 | 36; 6 | 569/2809 | no |
| 1920×1080 | 46+38 | 1920 | 47 / 1826 | 27 | 52.5 | 14/13/12/11 | 36; 6 | 749/2715 | no |
| 2560×1440 | 46+38 | 2560 | 47 / 2466 | 27 | 52.5 | 14/13/12/11 | 36; 6 | 1109/2441 | no |
| 3840×2160 | 46+38 | 3840 | 619 / 2602 | 27 | 52.5 | 14/13/12/11 | 36; 6 | 1829/2433 | no |

Pane inline padding is 12 px at every viewport, active density is the shared compact baseline,
navigator/inspector widths are N/A, primary row-action count is six in the Reviewer normal fixture,
nested persistent card count is zero, and the normal sparse queue has no vertical overflow.

## Role and state acceptance

| State | Result | Direct evidence |
| --- | --- | --- |
| Reviewer `Needs attention` | pass | `activity-{1366,1440,1920,2560,3840}` originals |
| Reviewer long `Recent outcomes` | pass | `activity-history-{1440,1920,2560,3840}`; real local rail |
| Reviewer decision 503 | pass | `activity-decision-error-1440x900`; reason retained, no API mutation |
| Reviewer recovery | pass | `activity-recovery-1440x900`; exact selection action reachable |
| User default | pass | `activity-user-1440x900`; `In progress`, no decision action |
| Administrator default | pass | `activity-administrator-1440x900`; own `In progress`, no decision action |

## Q01–Q20 matrix

| Gate | Status | Activity disposition and direct path |
| --- | --- | --- |
| Q-01 | N/A | Activity has no navigator tree. |
| Q-02 | PASS | Long `Recent outcomes` has a real local rail at all captured heights; normal sparse queues have none. |
| Q-03 | N/A | No Materials navigator rows. |
| Q-04 | N/A | No Fit ribbon. |
| Q-05 | N/A | No engineering axes. |
| Q-06 | N/A | No curve legend. |
| Q-07 | N/A | No SVG plot. |
| Q-08 | N/A | No true-yield response plot. |
| Q-09 | PASS | Wide local-scrollbar crops show reserved track and proportional thumb; the capture contract verifies real overflow. |
| Q-10 | N/A | No Fit legend. |
| Q-11 | N/A | No Fit rail. |
| Q-12 | N/A | No Export setup. |
| Q-13 | N/A | No Export setup/result columns. |
| Q-14 | N/A | No Export readiness surface. |
| Q-15 | N/A | No engineering plot domain. |
| Q-16 | N/A | No Export native preview. |
| Q-17 | N/A | No Administration object list. |
| Q-18 | N/A | No Administration definition editor. |
| Q-19 | N/A | No Administration link topology. |
| Q-20 | PASS* | Shell spans all five viewports; table grows through 2466 px, then the centered 2656 px local pane contains a 2602 px table and adjacent rail; semantic compact tokens are live; no scaling/media/filler shortcut. `*` This is the Task 2 compact-token/geometry result only. Display-density policy remains #221, product-wide Q-20 remains #184, and Activity actual Windows 4K physical readability is deferred to final unit #223. |

## Legacy selector report

A live `/activity` DOM query at 1440×900 returned zero occurrences for every required selector:
`page-stack`, `page-heading`, `content-card`, `module-material-card`, `hero-actions`, `eyebrow`,
`status-badge`, and `count-chip`. No exception is needed.

## Opened visual artifacts

Before originals:

![Before Activity 1366×768](images/issue-160-activity-density/before/activity-1366x768.png)
![Before Activity 1440×900](images/issue-160-activity-density/before/activity-1440x900.png)
![Before Activity 1920×1080](images/issue-160-activity-density/before/activity-1920x1080.png)
![Before Activity 2560×1440](images/issue-160-activity-density/before/activity-2560x1440.png)
![Before Activity 3840×2160](images/issue-160-activity-density/before/activity-3840x2160.png)
![Before Activity history 1440×900](images/issue-160-activity-density/before/activity-history-1440x900.png)
![Before Activity history 1920×1080](images/issue-160-activity-density/before/activity-history-1920x1080.png)
![Before Activity history 2560×1440](images/issue-160-activity-density/before/activity-history-2560x1440.png)
![Before Activity history 3840×2160](images/issue-160-activity-density/before/activity-history-3840x2160.png)

After originals:

![After Activity 1366×768](../user-guide/images/current/activity-1366x768.png)
![After Activity 1440×900](../user-guide/images/current/activity-1440x900.png)
![After Activity 1920×1080](../user-guide/images/current/activity-1920x1080.png)
![After Activity 2560×1440](../user-guide/images/current/activity-2560x1440.png)
![After Activity 3840×2160](../user-guide/images/current/activity-3840x2160.png)
![After Activity history 1440×900](../user-guide/images/current/activity-history-1440x900.png)
![After Activity history 1920×1080](../user-guide/images/current/activity-history-1920x1080.png)
![After Activity history 2560×1440](../user-guide/images/current/activity-history-2560x1440.png)
![After Activity history 3840×2160](../user-guide/images/current/activity-history-3840x2160.png)
![After Activity User default](../user-guide/images/current/activity-user-1440x900.png)
![After Activity Administrator default](../user-guide/images/current/activity-administrator-1440x900.png)
![After Activity decision error](../user-guide/images/current/activity-decision-error-1440x900.png)
![After Activity recovery](../user-guide/images/current/activity-recovery-1440x900.png)

Before 100%-pixel crops:

![Before 1920 shell/header](images/issue-160-activity-density/crops/before/activity-1920x1080-shell-header.png)
![Before 1920 saved-view tabs](images/issue-160-activity-density/crops/before/activity-1920x1080-saved-view-tabs.png)
![Before 1920 grid text/row](images/issue-160-activity-density/crops/before/activity-1920x1080-grid-text-row.png)
![Before 1920 row action](images/issue-160-activity-density/crops/before/activity-1920x1080-row-action.png)
![Before 1920 local scrollbar](images/issue-160-activity-density/crops/before/activity-1920x1080-local-scrollbar.png)
![Before 2560 shell/header](images/issue-160-activity-density/crops/before/activity-2560x1440-shell-header.png)
![Before 2560 saved-view tabs](images/issue-160-activity-density/crops/before/activity-2560x1440-saved-view-tabs.png)
![Before 2560 grid text/row](images/issue-160-activity-density/crops/before/activity-2560x1440-grid-text-row.png)
![Before 2560 row action](images/issue-160-activity-density/crops/before/activity-2560x1440-row-action.png)
![Before 2560 local scrollbar](images/issue-160-activity-density/crops/before/activity-2560x1440-local-scrollbar.png)
![Before 3840 shell/header](images/issue-160-activity-density/crops/before/activity-3840x2160-shell-header.png)
![Before 3840 saved-view tabs](images/issue-160-activity-density/crops/before/activity-3840x2160-saved-view-tabs.png)
![Before 3840 grid text/row](images/issue-160-activity-density/crops/before/activity-3840x2160-grid-text-row.png)
![Before 3840 row action](images/issue-160-activity-density/crops/before/activity-3840x2160-row-action.png)
![Before 3840 local scrollbar](images/issue-160-activity-density/crops/before/activity-3840x2160-local-scrollbar.png)

After 100%-pixel crops:

![After 1920 shell/header](images/issue-160-activity-density/crops/after/activity-1920x1080-shell-header.png)
![After 1920 saved-view tabs](images/issue-160-activity-density/crops/after/activity-1920x1080-saved-view-tabs.png)
![After 1920 grid text/row](images/issue-160-activity-density/crops/after/activity-1920x1080-grid-text-row.png)
![After 1920 row action](images/issue-160-activity-density/crops/after/activity-1920x1080-row-action.png)
![After 1920 local scrollbar](images/issue-160-activity-density/crops/after/activity-1920x1080-local-scrollbar.png)
![After 2560 shell/header](images/issue-160-activity-density/crops/after/activity-2560x1440-shell-header.png)
![After 2560 saved-view tabs](images/issue-160-activity-density/crops/after/activity-2560x1440-saved-view-tabs.png)
![After 2560 grid text/row](images/issue-160-activity-density/crops/after/activity-2560x1440-grid-text-row.png)
![After 2560 row action](images/issue-160-activity-density/crops/after/activity-2560x1440-row-action.png)
![After 2560 local scrollbar](images/issue-160-activity-density/crops/after/activity-2560x1440-local-scrollbar.png)
![After 3840 shell/header](images/issue-160-activity-density/crops/after/activity-3840x2160-shell-header.png)
![After 3840 saved-view tabs](images/issue-160-activity-density/crops/after/activity-3840x2160-saved-view-tabs.png)
![After 3840 grid text/row](images/issue-160-activity-density/crops/after/activity-3840x2160-grid-text-row.png)
![After 3840 row action](images/issue-160-activity-density/crops/after/activity-3840x2160-row-action.png)
![After 3840 local scrollbar](images/issue-160-activity-density/crops/after/activity-3840x2160-local-scrollbar.png)

## Validation record

- `npm run test --workspace @cmp/web -- --run src/material-library-activity.test.tsx src/app.test.tsx`
  — 31 passed.
- `uv run pytest tests/contracts/test_activity_density_contract.py tests/contracts/test_capture_current_product.py -q`
  — 62 passed.
- `npm run test:e2e --workspace @cmp/web -- review-publication-recovery.spec.ts` — the one realistic
  submit → review → publish/read-back → invalidate/recover browser journey passed.
- `npm run build --workspace @cmp/web` — TypeScript, production Vite build, and bundle budget passed.
- `uv run --with playwright==1.62.0 python scripts/capture_current_product.py ... --only-activity`
  — 13 captures passed, including live computed-token, row/control, wide-bound, balanced-gutter,
  role, retained-error, recovery, and genuine-overflow assertions.
- Ruff, capture output contracts, YAML parsing, `uv run cmp-check-user-guide --root .`,
  `uv run cmp-check-doc-impact --root . --mode worktree`, and `git diff --check` passed.
- On 2026-08-09 the Product Owner approved this bounded Task 2 visual result and explicitly authorized
  commit, push, PR, ready transition, and merge. The repository pre-publish gate remains mandatory
  after commit and is reported from the exact committed tree rather than claimed by this evidence file.

## Acceptance boundary

The Product Owner approved the bounded compact-token and Activity geometry result for #160 Task 2.
After its PR merges and delivery tracking is synchronized, #160 may be completed. The actual Windows
4K 100%/150%/200% physical-readability record is not claimed here; the Product Owner routed that final
verification to #223 as the last #117 unit, so it no longer blocks #160 completion.
