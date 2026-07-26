# UXC-00R documentation authority audit

Status: historical evidence

Baseline audited: `main@d8feeaf` / PR #136. This documentation-only slice preserves existing
backend, domain, numerical, revision/provenance, solver-card, PR #124 and DUI-01~06 behavior.

## Corrections

- Made the approved product-role target explicit: User, Reviewer, Administrator. Current UI exposes
  Administrator/User only; Reviewer migration remains pending.
- Corrected the normal Modeling path to `Data | Process | Fit | Export`. Validation and review/release
  are distinct governed Advanced/Activity actions, not six normal stage tiles.
- Pinned the approved Modeling geometry to the lower proposal in
  [modeling-reference-comparison.png](../images/ux-layout-review/modeling-reference-comparison.png): 184–210 px tree, shallow
  graph-adjacent band and dominant plot; no permanent inspector column.
- Marked current Activity and Administration captures as pending-redesign evidence rather than target
  approval, and added target component contracts for Materials, Administration, Activity and
  role-gated commands.

## Image disposition

The three retired current-guide Modeling validation PNGs were moved without byte modification to
[the retired-image directory](../images/uxc-00r-retired-modeling-validation/) and registered in
[screenshot-archive.yaml](../screenshot-archive.yaml). Process
and Fit current captures remain current. No Activity or Administration current capture was removed.

## Remaining gate

Reviewer product role/access migration, Materials language/presentation and query projection gaps,
DUI-07 Administration, DUI-08 Activity review queue, DUI-09 legacy cleanup and final incoming-package
deletion remain. The next design-only PR must create responsive prototypes, measure region ratios and
receive explicit product-owner approval before any production React/CSS change. Automatic LLM review
remains disabled under #119.
