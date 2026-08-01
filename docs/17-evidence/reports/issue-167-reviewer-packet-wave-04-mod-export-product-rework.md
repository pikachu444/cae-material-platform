# Issue #167 — MOD-EXPORT product rework fresh reviewer packet

Date: 2026-07-29
Role: fresh configured Terra High reviewer, read-only
Disposition required: `approve` or `changes_requested`

## 1. Acceptance authority

Read:

- repository `AGENTS.md`;
- `docs/01-product/desktop-engineering-ui-product-spec.md` — Modeling Export;
- `docs/01-product/desktop-engineering-ui-spec.md` — Export field contracts;
- `docs/01-product/visual-acceptance-matrix.md` — route gate, V-01–V-16 and mandatory
  Q-01–Q-11;
- `docs/17-evidence/reports/issue-167-product-owner-rework-packet-wave-04-mod-export.md`;
- `docs/17-evidence/reports/issue-167-correction-packet-wave-04-mod-export-product-rework.md`;
- section 40 of `docs/17-evidence/reports/issue-167-service-reference-freeze.md`.

This replaces the unapproved earlier MOD-EXPORT candidates. The product owner approved the region
direction, not these final images. Product-owner approval is still absent.

## 2. Candidate sources and exact references

Review only:

- `docs/00-research/ux-service-reference/modeling-export-normal.html`;
- `docs/00-research/ux-service-reference/modeling-export.css`;
- `docs/00-research/ux-service-reference/modeling-export.js`;
- `docs/00-research/ux-service-reference/capture_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/validate_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/modeling-export-wave04.staging.json`.

Open every approval image at original resolution:

| Image | Viewport | SHA-256 |
| --- | --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1366x768.png` | 1366×768 | `5a4b4f3c728cb9844f092bbbc57f5fc378068962247919d10374239c72d59b6d` |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1440x900.png` | 1440×900 | `8fcb8a8465ecc1cebdfc596ef6df5382ca3313c35d68d343161e92ddbbf389e5` |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-normal-1920x1080.png` | 1920×1080 | `77260893b0808266b02b1940fe54a11fec9464680542a591fbd6ceb2e54a4f74` |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-source-blocked-1440x900.png` | 1440×900 | `376c4134269f964e7d408636c22ed08aab563589a4a2c57bf10067e5af321d37` |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-approximation-blocked-1440x900.png` | 1440×900 | `dae621e1ed1ef4835b50c919dd30d9cc560b964d5d31bef3fda9ab3acd8f2bc8` |
| `docs/17-evidence/images/issue-167-service-reference/modeling-export-delivered-1440x900.png` | 1440×900 | `9bbe26cc0b68a4efe582d8daff16f4de3aed18aa2518ab4c2ea4f3763d044922` |

Then open every other `modeling-export-*.png` in the evidence directory at original resolution,
excluding only the explicitly rough, read-only `modeling-export-layout-concept-1440x900.png`. This
includes the three-viewport no-target, checking, creation-error and long-mapping bundles; the
1366/1920 source-blocked, review-required and created siblings; and:

- linear-viscoelastic:
  `modeling-export-family-linear-viscoelastic-1440x900.png`,
  SHA-256 `cb0a66d2d797da3360a3bf32f20eeb5aeccfac2933d9a921b72b21e619901f00`;
- hyperelastic:
  `modeling-export-family-hyperelastic-1440x900.png`,
  SHA-256 `9a475a8a314aed488b3e8a5cae79b4f196d1398be13c49998404f7e85e584d43`.

## 3. Contract and qualitative questions

Independently verify:

- Density is governed upstream, read-only here, and Source/Output appears only when a target output
  exists.
- `kg · m · s; stress in Pa`, `7.80000000E+03 kg/m³`, `2.10000000E+11 Pa` and the native numbers
  agree.
- Abaqus and OpenRadioss have the packet's different Unit convention status/counts.
- no-target has no concrete target tuple or target mapping; source-blocked has no stale source;
  review-required needs exact identity acknowledgement; created exposes Solver Card/Delivery
  details without normal-surface receipt language.
- family readiness, rows, counts, axes and legends are derived from actual family content.
- metal, linear-viscoelastic and hyperelastic axes/legends remain visible, professional, uniformly
  scaled, status-bar clear and curve-free.
- setup, native preview and long Mapping details expose discoverable local overflow.
- discarded visible words (`preflight`, `mapping sheet`, `next safe action`, undisclosed
  `receipt/evidence`) do not reappear.
- there is one filled primary task action and one state-specific recovery; no nested cards or
  permanent third control inspector.

Complete V-01–V-16 and every Q-01–Q-11 item independently, with `pass`, `fail` or justified
`not-applicable` plus direct image evidence. Numeric success is insufficient.

## 4. Deterministic evidence

The main agent reran and passed:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_modeling_export_wave04.py --help
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_export_wave04.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_modeling_export_wave04.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_export_wave04.py --all-packet-targets --expect-main-agent-status pending
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py --all-packet-targets --expect-main-agent-status accepted
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_modeling_export_wave04.py docs/00-research/ux-service-reference/validate_modeling_export_wave04.py
node --check docs/00-research/ux-service-reference/modeling-export.js
git diff --check
```

Reported interactions: splitter Arrow/Home/End, setup collapse/restore, target invalidation, exact
acknowledgement gate, immutable Solver Card creation, receipt disclosed only after Delivery details,
single recovery action, local pointer/wheel/keyboard overflow, zero console/page/resource errors and
zero body/document overflow.

## 5. Reviewer output

Read-only: do not edit any file, GitHub item or git state. Return:

1. disposition;
2. V-01–V-16 scores and total out of 32, naming any hard-gate failure;
3. completed Q-01–Q-11 with direct evidence;
4. any contract/accessibility/full-screen qualitative finding ranked by severity;
5. residual concerns or an explicit statement that none remain.

Do not request product-owner approval and do not review unrelated dirty-worktree changes.
