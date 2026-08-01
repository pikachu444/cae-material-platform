# Issue #167 correction packet — Materials navigator lifecycle validation

Date: 2026-07-30
Owner: active `/root` main agent
Correction role: one fresh configured Terra High implementer
Scope: sole correction after post-integration deterministic validation failed

## Gate disposition

The six normal MAT-EXP/MAT-DETAIL images pass original-resolution inspection and their interaction,
overflow and preservation measurements. After the main agent registered their new hashes as pending,
two validator lifecycle assumptions failed:

- `validate_reference.py` still hard-codes the previous 2026-07-28 approved lifecycle and does not
  recognize the shared `materials-navigator.css` / `materials-navigator.js` source keys. All three
  pending search targets therefore fail `date`, `reference-status` and pending product-owner
  lifecycle checks.
- `validate_materials_datasheet_wave01.py --all-packet-targets ...` treats the byte-identically
  preserved Related-long and empty references as pending, while the authoritative common manifest
  correctly keeps those unchanged references approved.

These are deterministic evidence defects, not visual defects. Do not change or recapture any image.

## Required correction

1. Make the MAT-EXP validator accept the registered 2026-07-30 pending lifecycle before owner
   approval, require `main_agent_evaluation.status: accepted` when requested, and require no
   product-owner disposition for a pending target using the repository's actual manifest convention.
2. Register the shared navigator CSS/JavaScript in the validator's exact source contract and keep
   the existing route-specific CSS/JavaScript contracts.
3. Make MAT-DETAIL validation distinguish:
   - the three changed normal targets: pending, main-agent accepted, owner absent;
   - the unchanged Related-long and empty references: approved with their existing owner evidence.
4. Keep the exceptional canonical and responsive hashes exactly frozen:
   - MAT-EXP search-long canonical
     `43f146e60baf2d933265d952e22fce5cd0c1e2ca0e9145eea0e72a9677da2484`;
   - MAT-EXP search-empty canonical
     `d9e4fed1d8c17ca86b7c14dfe57909591b44ff8ec300286bb49f3a940fb5e1b1`;
   - MAT-DETAIL Related-long canonical
     `810394678a9a77c1c35adc4a1848ca45eadd71a1a95a69ea94af7266405079b6`;
   - MAT-DETAIL empty canonical
     `8df98559459f03db925e02251e10a84265b9ff1e21cd8f4573dd9d2a090548e6`;
   - every registered 1366/1920 responsive sibling already asserted by the implementation packet.
5. Do not weaken any navigator, splitter, scrollbar, full-identity, wide-viewport, graph or
   preservation assertion merely to obtain a pass.

## Ownership and gates

Own only:

- `docs/00-research/ux-service-reference/validate_reference.py`;
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`;
- the MAT-DETAIL staging JSON only if its lifecycle mirror must be corrected.

Do not edit HTML/CSS/JavaScript, images, measurements, common manifest/inventory/policy/report,
production React/CSS, Administration files, GitHub state, commits or pushes. Other work exists in
the worktree; preserve it and do not reset, clean, stash, revert or overwrite it.

Run:

- both validator `--help` commands;
- all three MAT-EXP target validations, including 1920 wide evidence;
- MAT-DETAIL all-packet validation plus the 1920 wide-evidence and frozen-hash checks;
- Ruff, Python compilation, inventory validation and `git diff --check`.

Return changed paths and exact command results. No image may change.
