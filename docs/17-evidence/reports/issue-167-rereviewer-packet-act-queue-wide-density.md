# Issue #167 — ACT-QUEUE wide-density fresh re-review packet

Date: 2026-07-30
Reviewer: one fresh configured read-only `reviewer_terra_high`
Disposition: `approve` or `reject`

## Issue acceptance

Independently determine whether the pending ACT-QUEUE family is ready for product-owner review:

- User defaults to `In progress`; Reviewer defaults to `Needs attention`.
- One deterministic non-production page contains 50 server review requests: 40 pending and 10
  decided. Browser-local Modeling and solver-card history remain distinct.
- The flat semantic table is `Task | Request reason | Status | Updated | Action`.
- User pending rows have no fabricated command: the passive Action cell is a visible em dash with
  accessible name `No available action`, and never repeats lifecycle state.
- Reviewer pending rows expose one row-level `Review`; decision UI is closed by default.
- No readable Material/Owner/person identity, receipt, release or identifier is fabricated.
- Fixed compact row density and an independent proportional local scrollbar use 1366 through 3840
  height without stretched rows, clipping, page overflow or a dominant avoidable blank region.
- Empty/loading/long/error/blocked states and immutable decision recovery remain truthful.

## Candidate and support images

| Target | Image | SHA-256 |
| --- | --- | --- |
| User 1366×768 | `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1366x768.png` | `489d66c6d1d1e80d2d0ae11c94dcf71d27a9c56b0cdcbb59c3623330d562f4d3` |
| User 1440×900 | `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1440x900.png` | `b96554fa362cd301079881ef7503a8822171e34059ba972f17ab7e2c08ed8de8` |
| User 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1920x1080.png` | `730b7144803decf282bb190373cc44c15151e74f028b7b9cfb15f1627c370bbe` |
| Reviewer 1366×768 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1366x768.png` | `1f4d25511fa1dc307839271a132a7c24ef51cf4200cac6a0462d660ec47465f4` |
| Reviewer 1440×900 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1440x900.png` | `e8c7877dbd7d6191ee4d3d68d29f55be9604f537f38c5ff85f20ff59b510694f` |
| Reviewer 1920×1080 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1920x1080.png` | `8c27fa20576d259be8bd84ff215cdc64ab122a497d3f27f57872be843e4fbaf6` |
| Reviewer long decision error 1440×900 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-long-decision-error-1440x900.png` | `82147fecd36a049d4982ae787b903f71c8c95849658467950ae2b18ffaff4f6d` |
| User support 2560×1440 | `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-2560x1440.png` | `04b6b8ad59a29832d7e1342aa2afba5f095bf5ae177c8490cc7fadf189c61ff1` |
| User support 3840×2160 | `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-3840x2160.png` | `2745cd0eb3f26adcb3eb9cde6bf687378b918a52747f69cdf55f9af4fc8a9e20` |
| Reviewer support 2560×1440 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-2560x1440.png` | `3558eda18c9c1275eb84ff3921ce0753865e152808dd1dc9c3aba2565aa1e3c6` |
| Reviewer support 3840×2160 | `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-3840x2160.png` | `0fe966a1ed2d0fa3c2beb5dc7e236d58407bb9324296aac6b8e702eaf62c7db2` |

Open every image above at original resolution. Also inspect the responsive state paths in
`docs/17-evidence/images/issue-167-service-reference/activity-queue-wave04-state-evidence.json`.

## Implementation diff and contracts

Review only the ACT-QUEUE changes in:

- `docs/00-research/ux-service-reference/activity-queue-normal.html`
- `docs/00-research/ux-service-reference/activity-queue.css`
- `docs/00-research/ux-service-reference/activity-queue.js`
- `docs/00-research/ux-service-reference/capture_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/validate_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/activity-queue-wave04.staging.json`
- the images/measurements listed above and the existing Activity state evidence.

Acceptance authority:

- `AGENTS.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/01-product/service-reference-manifest.yaml`
- current Activity contracts in `apps/web/src/material-library.tsx` and its API client.

The review is read-only. Do not modify files, lifecycle records, GitHub, commits or branches.

## Deterministic and interaction results

The active main agent independently reran and observed pass:

```powershell
node --check docs/00-research/ux-service-reference/activity-queue.js
python -m py_compile docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_queue_wave04.py docs/00-research/ux-service-reference/validate_activity_queue_wave04.py
python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_activity_queue_wave04.py --wide-support --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

The validator reports all eleven targets, seven three-viewport state bundles, pointer wheel,
keyboard PageDown, focus visibility, recovery commands, passive Action semantics and zero
console/page errors as pass.

## Mandatory qualitative owner checklist

Record `pass`, `fail` or `not applicable` with direct evidence for every Q-01 through Q-20 from
`docs/01-product/visual-acceptance-matrix.md`. Expected applicability for this Activity family is:

- Q-02, Q-09 and Q-20: applicable;
- Q-01, Q-03–Q-08 and Q-10–Q-19: not applicable unless direct inspection shows that the target
  unexpectedly introduces the corresponding topology.

Any applicable failure rejects the bundle regardless of numeric score. Provide one final
`approve`/`reject` disposition and list every actionable finding in severity order.
