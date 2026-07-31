# Issue #167 MOD-PROCESS final fresh-review packet

Date: 2026-07-31

## Scope and authority

Review only the product-owner-authorized MOD-PROCESS correction described in
`issue-167-owner-authorized-correction-packet-mod-process-final.md` and section 97 of
`issue-167-service-reference-freeze.md`. This is a read-only review. Do not edit, recapture, commit,
push, or review unrelated dirty-worktree changes.

The approved prerequisite is the saved Test Data/process contract already recorded in the packet.
The user task is to select observed curves, calculate an elastic preview, inspect the response, and
save a new processing result without mistaking a preview for saved data. Preserve the compact
curve/process rail, shallow graph-adjacent controls, dominant engineering graph, immutable saved
Test Data, explicit preview/save boundary, and blocked prerequisite recovery.

## Files to inspect

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-state-evidence.json`
- `docs/01-product/service-reference-manifest.yaml`

## Lifecycle and supporting originals

| Image | SHA-256 |
| --- | --- |
| `modeling-process-normal-1366x768.png` | `6722bd80c851b47c941cbac92c03e10a6106566fef940fabe9d8ab61c7fec825` |
| `modeling-process-normal-1440x900.png` | `122cf29074eea18bfd0549ad40dc0d9143b1ee6bb2bd82df6266194645b5d3ae` |
| `modeling-process-normal-1920x1080.png` | `5c9db6b591e0117989071172ae53444a35e7337359c3db8d7c77050610a17d77` |
| `modeling-process-prerequisite-blocked-1440x900.png` | `2f3ed351bbb22b604e6a7bed189b52cd7b9945f8620633d2442482654492ed30` |
| `modeling-process-normal-2560x1440.png` (support) | `44799e263a57c03a16ecaf36e5977596309c0cb02bf06df2bfc583b826d2be68` |
| `modeling-process-normal-3840x2160.png` | `b85c3f65263724539ce27afe3ec235c4a89ea0586ccf39b2f5b4a4fe95ea807c` |

Open each at original resolution. At 3840, verify that compact controls stop at their natural
working width, the graph remains an engineering result rather than a decorative canvas, and the
synchronized Processed response grid uses the additional lower region. At 2560, verify that the
graph remains proportionate without an avoidable filler panel.

## Persisted state originals

Open all fifteen state images at original resolution and verify their hashes against
`modeling-process-state-evidence.json`:

- `modeling-process-state-long-rail-{1366x768,1440x900,1920x1080}.png`
- `modeling-process-state-preview-loading-{1366x768,1440x900,1920x1080}.png`
- `modeling-process-state-commit-loading-{1366x768,1440x900,1920x1080}.png`
- `modeling-process-state-preview-error-{1366x768,1440x900,1920x1080}.png`
- `modeling-process-state-commit-error-{1366x768,1440x900,1920x1080}.png`

The long rail must contain truthful specimen rows in the existing row grammar, show a reserved
proportional local scrollbar, and never invent Evidence/provenance rows. Loading and failure states
must use one inline consequence banner, keep the graph and current source/settings available, disable
only the affected action, and avoid repeated overlays or developer/internal terminology.

## Required deterministic gates

Run:

```powershell
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m py_compile docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

## Independent review contract

Complete V-01–V-16 and every Q-01–Q-20 row from
`docs/01-product/visual-acceptance-matrix.md`, marking non-applicable items explicitly. In particular:

- Q-02/Q-09/Q-11: independent rail scrolling, truthful long rows, visible reserved track and no
  covered labels;
- Q-05–Q-08/Q-10: compact professional axes, centered titles with units, data-relative headroom,
  non-distorted response and a compact curve-free legend;
- Q-20: 1920/2560/3840 must preserve stable typography/control density, avoid stretched controls or
  decorative empty regions, and expose only meaningful response data when topology expands.

Reject for any applicable qualitative failure even if the scripts pass. Report exact actionable
findings first, then disposition (`approve` or `changes_requested`), V score, hard-gate result,
Q-01–Q-20 evidence, and residual concern. Product-owner approval must remain absent.
