# Issue #167 sole correction packet — WAVE-01 / MAT-DETAIL

Date: 2026-07-29  
Correction role: configured fresh `correction_terra_high`  
Parent packet:
`docs/17-evidence/reports/issue-167-implementer-packet-mat-detail-wave-01.md`

## Main-agent rejection findings

The main agent opened all three canonical outputs at original resolution. The normal 1920 image is
accepted without change. Two explicit parent-packet requirements are missing:

1. `materials-datasheet-empty-1440x900.png` removes the selected Record header. The pane jumps from
   blank header space to the tab strip, so the normal DP780 name/code/family/Draft/synthetic-data
   context is not visible. Empty must preserve the selected Record header, tree and tabs while only
   governed values/curves/card delivery are empty.
2. `materials-datasheet-related-long-1440x900.png` uses short generic Relationship values
   (`Forward · source record`, `Reverse · referenced by`). The parent packet requires visibly long,
   human-readable forward and reverse Link Type wording as well as long Record names, so the
   reference actually proves relationship-label containment.

These are main-agent acceptance failures despite the writer validator passing. This is the one and
only authorized MAT-DETAIL correction.

## Required correction

- Restore the frozen normal Record header inside Empty: `DP780 synthetic demo steel`, `DP780-REF`,
  `Metal`, `Draft`, the synthetic/non-validated note, and `Current revision / r1 · Draft`.
- Keep Empty's truthful no-data explanation, exactly one primary safe `Back to results`
  consequence, no properties/curve/solver format and the restrained unavailable-delivery context.
- Replace both Related relationship labels with long, normal-language synthetic Link Type wording.
  One must be the forward label and one the reverse label. Each label must be meaningfully longer
  than 45 characters and describe the relation, not an internal direction/source placeholder.
- Show the selected long relationship wording in the right context.
- Wrap deliberately inside the Relationship column or use controlled truncation with a native
  title. No clipping, overlap or horizontal page overflow at 1366, 1440 or 1920 evidence widths.
- Strengthen the validator so it fails if Empty lacks the visible Record header/status context, or
  if either Related relationship label is generic/short, out of bounds or unavailable in full text.
- Recapture the two corrected canonical images and their three-viewport responsive evidence.
- Update the family staging index and hashes.

## Frozen boundary

Do not change:

- `materials-datasheet-overview-normal-1920x1080.png` or its sources/measurements/hash
  `eda9da6037d7dec12fd4c4c5ce5fa77e993a1faa37f5853b3da5c2203bd35849`;
- approved 1366/1440 parent assets;
- common manifest, inventory, evidence report or production files;
- another agent's `modeling-data*` paths;
- git state, commits, branches, remotes or GitHub.

You own only the MAT-DETAIL Related/Empty override source, family capture/validator, staging file
and Related/Empty evidence files named by the parent packet. Other agents are active; preserve
their work.

## Gates and handoff

Rerun the full parent-family capture/validator plus frozen-parent validators, Ruff, Node syntax,
inventory validation and `git diff --check`. Open both corrected canonical images at original
resolution. Return exact files, commands, canonical hashes and any residual concern. Do not commit.
