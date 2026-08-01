# Issue #167 ACT-RECOVERY product-language reviewer packet

Date: 2026-07-31
Review mode: fresh, independent, read-only

## Review boundary

Review only the corrected `ACT-RECOVERY` reference family. Do not edit any file, review unrelated
dirty-worktree changes, or reinterpret dependent families. This is a static-reference gate, not
production React/CSS work.

The family adds one truthful Activity capability boundary:

- failed calculations are not inspected in Activity;
- one browser-local saved Modeling session can be resumed;
- the User queue continues to show the approved server request contract;
- recovery empty removes only the local session;
- refresh loading keeps current rows mounted;
- an action failure remains attached to the local session and exposes one `Try again`;
- the primary queue uses product language only: Material, Test Data, selected model and solver card
  review;
- no provenance, mapping, evidence, immutable-revision or other internal workflow vocabulary is
  exposed in the primary surface.

The active main agent rejected the first implementation despite passing deterministic geometry
because its repeated request labels exposed internal workflow vocabulary. Review the sole correction
independently. Automated measurements are supporting evidence, not the visual conclusion.

## Approved dependency

The product owner approved the exact `ACT-QUEUE` User and Reviewer references registered in
`docs/01-product/service-reference-manifest.yaml`. Their source hashes are frozen by the
ACT-RECOVERY validator:

| Source | SHA-256 |
| --- | --- |
| `activity-queue-normal.html` | `3c74d943e447eaa020109a1be527969224f273ac131a1a0625504f62d085034f` |
| `activity-queue.css` | `26bd2cd69708f712f2d2a78ab0f8ee476bafb9f34a93ee24b5a91940448a87ce` |
| `activity-queue.js` | `880b479eacab90de92200deee48810cb6614160ea221fb78db6a8d39aac050c5` |

## Exact implementation and contract paths

- `docs/00-research/ux-service-reference/activity-recovery-blocked.html`
- `docs/00-research/ux-service-reference/activity-recovery.css`
- `docs/00-research/ux-service-reference/activity-recovery.js`
- `docs/00-research/ux-service-reference/capture_activity_recovery.py`
- `docs/00-research/ux-service-reference/validate_activity_recovery.py`
- `docs/00-research/ux-service-reference/activity-recovery.staging.json`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/17-evidence/reports/issue-167-implementer-packet-act-recovery.md`
- `docs/17-evidence/reports/issue-167-correction-packet-act-recovery-product-language.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 91–92

## Original-resolution images and hashes

Open every image below at original resolution.

| Role/state | Image | SHA-256 |
| --- | --- | --- |
| approval target | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-blocked-1366x768.png` | `66e93ab285651dcd0095b8f928836611ffbae84165fb6ccc765ed14c8e71c252` |
| approval target | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-blocked-1440x900.png` | `03aa747651b1703b269d2d3fdb96b21572343a22a5aa57ba81b55d8dfd80057d` |
| approval target | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-blocked-1920x1080.png` | `254750dbfeb9eeedc3ac79b9c606ceb7dcc13eb9f83f34cf7f5c831bbb54aaf1` |
| wide support | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-blocked-2560x1440.png` | `3d020a39361fc00d3c100f792d98d9f666e23771f549d9e0853ad6131c7f12af` |
| wide support | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-blocked-3840x2160.png` | `fb019293c76c660d447a8df597abb3bc005f1fbbac7f7c2a910872000bc0fdc8` |
| empty 1366 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-empty-1366x768.png` | `d968e0edd4ccfdfe634cd939cff931aac2a1044ec0540217eaaa2b639a57a50b` |
| empty 1440 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-empty-1440x900.png` | `a1025933258aeda518b61f59da2f3a81f778430e9cfd67df762d53ba3285a6c4` |
| empty 1920 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-empty-1920x1080.png` | `1d6531c1dcfab952979151e38a71a6073eb0dffe491642d7294dd21284e2b725` |
| loading 1366 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-loading-1366x768.png` | `4cf9e607c664b0236d258ade13bd0aa106c3b47867b8775a43b362ada4bf2136` |
| loading 1440 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-loading-1440x900.png` | `3ace6974fe143ea3c3c1eec117a51cc3d7684e10de3ee48fe60535343b9b095a` |
| loading 1920 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-loading-1920x1080.png` | `feae284b16d590c9e96ba5f3c6f19090b417258c94668b670c0b13bf1d52755a` |
| action error 1366 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-action-error-1366x768.png` | `857a0053365d220f1089f3c8132c049a16ecc8ca06f43e246b50e7367207777c` |
| action error 1440 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-action-error-1440x900.png` | `2a069ec9923d029f02c12945e3f6115b4fd1ff4cd68d3caf70a02c9fcde67f9a` |
| action error 1920 | `docs/17-evidence/images/issue-167-service-reference/activity-recovery-action-error-1920x1080.png` | `8c821d3850d313aa72bd164e7c9cac345c52a38e1f0e9dcf6068bdf5323db4f5` |

The state relationships and exact per-viewport hashes are also recorded in
`docs/17-evidence/images/issue-167-service-reference/activity-recovery-state-evidence.json`.

## Deterministic evidence

The active main agent ran these non-mutating gates after the correction and manifest integration:

```powershell
python docs/00-research/ux-service-reference/capture_activity_recovery.py --help
python docs/00-research/ux-service-reference/validate_activity_recovery.py --help
python docs/00-research/ux-service-reference/validate_activity_recovery.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_activity_recovery.py docs/00-research/ux-service-reference/validate_activity_recovery.py
python -m py_compile docs/00-research/ux-service-reference/capture_activity_recovery.py docs/00-research/ux-service-reference/validate_activity_recovery.py
node --check docs/00-research/ux-service-reference/activity-recovery.js
git diff --check
```

Independently verify hashes and rerun the non-mutating gates. The finite inventory must report
`54 normal + 18 exceptional + 1 topology variant = 73 images`, `37/73 approved`.

## Required independent qualitative review

Complete Q-01–Q-20 from `docs/01-product/visual-acceptance-matrix.md`, marking each item `pass`,
`fail`, or `not-applicable` with a topology reason and direct path evidence. In particular:

- judge the full-screen proportions at every viewport, not only the validator output;
- verify additional width/height reveals useful rows at fixed density without uniformly stretching
  copy or leaving an avoidable dominant blank region;
- verify the visible local queue rail is discoverable, reserved and proportional without covering
  request text;
- verify local session, server request and failed-calculation boundaries remain clear;
- reject useless explanatory copy, fabricated recovery functions, and internal/developer terms;
- verify empty, loading and action-error states preserve current context and one truthful recovery
  consequence without competing actions.

Return actionable findings first, then one disposition: `approve` or `changes_requested`. Include the
completed Q-01–Q-20 record. The reviewer is not the final design authority; the active main agent
repeats the original-resolution full-screen judgment after review.
