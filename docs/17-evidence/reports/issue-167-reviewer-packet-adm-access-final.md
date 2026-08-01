# Issue #167 — ADM-ACCESS final reviewer packet

Date: 2026-08-01
Review mode: fresh configured Terra High, independent and read-only
Lifecycle: 5 approval targets `pending`; main-agent correction gate passed; product-owner approval absent

## Bounded acceptance

Review only the final Administration access bundle. It freezes normal assignment review, denied
access, revoke confirmation, empty/loading/service-error behavior and wide support. This is static
#167 reference work, not production React/CSS.

The UI must preserve task-based User, Reviewer and Administrator roles; workspace/project scope;
maximum classification; readable granted work; and a truthful last-valid-result recovery. It must
use one local `Cancel` in revoke confirmation, avoid duplicate destructive commands, and keep all
normal task regions bounded and visible at 2560×1440 and 3840×2160. The empty state must consistently
show zero assignments in both navigation and list count.

Authority and implementation:

- Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
- Approved checkpoint: `issue-167-service-reference-freeze` at `3b72d48`
- Candidate: `agent/complete-167-and-157` at `2bcbbfa` plus current correction diff
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/17-evidence/reports/issue-167-administration-remaining-correction-packet.md`
- `docs/00-research/ux-service-reference/administration-remaining.html`
- `docs/00-research/ux-service-reference/administration-remaining.css`
- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`

Open every image at original resolution. All images live under
`docs/17-evidence/images/issue-167-service-reference/`.

Approval targets:

| Image | SHA-256 |
| --- | --- |
| `administration-access-normal-1366x768.png` | `63a8dc4c03fbe2800e978b4bc2dfed12b2da497be6de94e7b34b48ca0deb3972` |
| `administration-access-normal-1440x900.png` | `13854a88c9e71364c78d21977f48a69cf6a1d53b17f97ae2569e2ae885130602` |
| `administration-access-normal-1920x1080.png` | `a766432f4e9255d48773697629ba0fc189d4a3f7ffb15224568bf11efe2e64f2` |
| `administration-access-denied-1440x900.png` | `3ed2470f3dccb92fa5f4e0bef3a88d2bf11fd5404ed0b700de6428bc6a3c2981` |
| `administration-access-revoke-confirm-1440x900.png` | `26e048df7e2f9a5d0922801402ddd24df35137a6684d39d58b93bf0cc2a9397e` |

Wide support:

| Image | SHA-256 |
| --- | --- |
| `administration-access-normal-wide-2560x1440.png` | `c739eadf0076d69ba542d48047102a91d7b040c213dfafdeb2c41a560099c280` |
| `administration-access-normal-wide-3840x2160.png` | `928e2b23e7c7c7cc2d3a73b200cd70c2b620c7991b65175de11a8bfe7d3f2cbf` |

State evidence, each at 1366×768, 1440×900 and 1920×1080:

- `administration-access-empty-*` — expected PNG SHA-256 values are
  `ca122b4fb563248e13402dd78f1422a6e2e531f29cc431303ebc2b132e1ad686`,
  `191aa19063dd7d7a965ea0c6712b39af0179c2247ff8c360b35b7eef2258d278`, and
  `296259d9a34fe7eaf968d558c07fc223bb75c22888a0be5b5be92a1a6459d65a` in viewport order
- `administration-access-loading-*`
- `administration-access-service-error-*`

## Supplied deterministic result

Main-agent rerun result: `PASS: 1815 checks across 72 captures`; inventory validator passed with
`55/72 approved; 17 remaining`; node syntax, Ruff, `py_compile` and `git diff --check` passed. The
validator explicitly asserts that the access empty-state navigation count and list count are both
zero while normal/loading/error retain their intended counts.

## Required independent disposition

Complete V-01–V-16 and Q-01–Q-20 with direct path evidence. Treat Q-02, Q-09 and Q-20 as applicable,
and independently judge task clarity, role/scope/classification hierarchy, normal/denied/revoke
continuity, destructive-action prominence, last-valid-result recovery, count truthfulness, wide
containment, typography and the absence of redundant or developer-facing prose.

Return exactly `approve` or `changes_requested`, findings and residual risks. Do not edit files,
recapture evidence, change lifecycle state, commit, push or infer product-owner approval.
