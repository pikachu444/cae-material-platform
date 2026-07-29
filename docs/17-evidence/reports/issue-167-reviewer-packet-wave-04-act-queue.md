# Issue #167 reviewer packet — WAVE-04 / ACT-QUEUE

Date: 2026-07-29
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the first Activity service-reference bundle without inventing server projections that the
current product does not own:

- User queue normal at 1366×768, 1440×900 and 1920×1080;
- Reviewer queue normal at 1366×768, 1440×900 and 1920×1080;
- Reviewer long decision-submission error at 1440×900.

The User view may show the user's pending review request, browser-local Modeling resume and
browser-local solver-card outcome. It must not show reviewer decision controls. The Reviewer view
shows generic pending requests with one row-level Review action; the expanded form keeps one request,
one decision and a required reason. It must not fabricate readable people, release state or a server
receipt.

Inspect all seven approval images and all 21 responsive state images at original resolution. The
state evidence covers User empty, loading, long-row containment and queue error, plus Reviewer
user-role blocked, stale/unauthorized and decision-submission error. Current rows, request, selected
decision and reason remain mounted when recovery permits it. A service-error recovery uses one
`Retry decision`; stale authorization uses one `Refresh access` and cannot submit a decision.

Score V-01–V-16 and independently complete Q-01–Q-11 from
`docs/01-product/visual-acceptance-matrix.md`. A numeric score cannot override an applicable
qualitative failure. Return `approve` only with at least 28/32, no hard-gate zero, complete evidence
and no applicable Q failure. Do not modify any file.

Authoritative implementation and correction packets:

- `docs/17-evidence/reports/issue-167-implementer-packet-act-queue-wave-04.md`
- `docs/17-evidence/reports/issue-167-correction-packet-wave-04-act-queue.md`

## Approved authority and dependencies

- approved product/visual baseline `55cfa62` / PR #156;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`;
- current review request/decision API and browser-local Activity contracts inspected in the
  implementer packet.

This is the ACT-U bundle and the bounded ACT-R extension. There is no approved Activity reference
whose unsupported data projection may be copied.

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1366x768.png`
  — `45ecff451bdd3b3f7d11cf8b6afb1f25cda17be19a4118c68ba5d4c37745e523`
- `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1440x900.png`
  — `12b9cb7bd6d16ae57521ac69ac5dd61160d8ce3423d13e00ee66361cedfcc2aa`
- `docs/17-evidence/images/issue-167-service-reference/activity-user-normal-1920x1080.png`
  — `46cfb14e2a1ca9c8953d408004e9eff47d25c1fc7c4c311ff761509c4bd652ce`
- `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1366x768.png`
  — `8139b08582acb9ff1595490a88486f6b4eff684271f5775a14b357c125f0b29b`
- `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1440x900.png`
  — `daf7a2bacafaf0ae2f3c254a8a055fd4e57f6eb3dda05480726a90e9521fef3b`
- `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-normal-1920x1080.png`
  — `517ffdde4f5b1c49da291acd97c2f6abab9a8318e7793f05ceebeabb9db50c7b`
- `docs/17-evidence/images/issue-167-service-reference/activity-reviewer-long-decision-error-1440x900.png`
  — `bbcfcadd5555273afd030973f1f9e0da5ea18494722e975de3796eb0a90baaaa`

Every responsive state path, dimension and SHA-256 is recorded in
`docs/17-evidence/images/issue-167-service-reference/activity-queue-wave04-state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/activity-queue-normal.html`
- `docs/00-research/ux-service-reference/activity-queue.css`
- `docs/00-research/ux-service-reference/activity-queue.js`
- `docs/00-research/ux-service-reference/capture_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/validate_activity_queue_wave04.py`
- `docs/00-research/ux-service-reference/activity-queue-wave04.staging.json`
- the ACT-QUEUE candidate, measurement and state-evidence files named above;
- the seven ACT-QUEUE pending entries in
  `docs/01-product/service-reference-manifest.yaml`.

Production React/CSS, other families and approved references are outside the review diff.

## Main-agent original-resolution evaluation

The main `/root` agent opened all seven approval images and all 21 state images at original
resolution. The initial long-decision-error candidate was rejected despite passing its automated
gate: it paired a retained non-empty reason with `Reason is required`, reported `Ready` at page
level and exposed competing Record/Retry commands. The one authorized correction now keeps the
selected request, decision and reason, reports `Decision not recorded`, and exposes one filled
`Retry decision`.

The final main-agent Q record is:

| ID | Result | Direct evidence / topology reason |
| --- | --- | --- |
| Q-01 | not-applicable | Activity has no navigator tree. |
| Q-02 | pass | `activity-reviewer-normal-1366x768.png` exposes the local queue rail; User empty images have no fake result rail. |
| Q-03 | not-applicable | This is not Materials navigation. |
| Q-04 | not-applicable | Activity has no Fit control ribbon or graph. |
| Q-05 | not-applicable | Activity has no engineering axes. |
| Q-06 | not-applicable | Activity has no curve identities or graph legend. |
| Q-07 | not-applicable | Activity has no responsive plot. |
| Q-08 | not-applicable | Activity has no stress–plastic-strain response. |
| Q-09 | pass | Reviewer normal/error/stale images retain a distinct local overflow rail without covering queue text; pointer/wheel/keyboard consequences are persisted in measurements. |
| Q-10 | not-applicable | Activity has no Fit legend. |
| Q-11 | not-applicable | Activity has no Fit rail. |

## Deterministic and interaction results

```text
family capture from final sources                              pass
pending-lifecycle family validator                             pass, 7 approval + 21 state images
User role / Reviewer role boundary                             pass
selected decision and non-empty reason retention               pass
service-error recovery / competing submit command              one Retry decision / absent
stale authorization recovery / decision submission             one Refresh access / absent
empty/loading/error/long-row context preservation               pass
queue local scroll / pointer-wheel-keyboard consequences        pass
computed typography / clipping / page overflow                 pass / zero / zero
legacy active-route selectors / nested interactions             zero / zero
console errors / page errors                                   zero / zero
inventory / Ruff / Node syntax / scoped diff checks             pass
lifecycle                                                       pending / main accepted / PO absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, the completed
Q-01–Q-11 table, hard-gate failures, actionable findings with direct paths, and residual concerns.
Independently open every approval and state image at original resolution and rerun the validator.
Do not edit.
