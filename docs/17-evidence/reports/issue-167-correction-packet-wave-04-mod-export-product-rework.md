# Issue #167 — MOD-EXPORT product rework correction packet

Date: 2026-07-29
Status: sole correction authorized after the Luna Max result failed deterministic and main-agent gates
Writer: one fresh configured Terra High correction agent
Authority: `AGENTS.md`, the current product/UI specifications, the visual acceptance matrix, and
`issue-167-product-owner-rework-packet-wave-04-mod-export.md`

## 1. Scope and ownership

Correct the current unapproved MOD-EXPORT product-rework bundle only. Preserve all unrelated dirty
worktree changes. The correction writer may edit only:

- `docs/00-research/ux-service-reference/modeling-export-normal.html`;
- `docs/00-research/ux-service-reference/modeling-export.css`;
- `docs/00-research/ux-service-reference/modeling-export.js`;
- `docs/00-research/ux-service-reference/capture_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/validate_modeling_export_wave04.py`;
- `docs/00-research/ux-service-reference/modeling-export-wave04.staging.json`;
- MOD-EXPORT-only images, measurements and state/family evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

Do not edit the common manifest, inventory, evidence report, product policy, production code, git
state or GitHub. Do not reset, clean, stash, discard, commit, push, open or merge a PR.

## 2. Deterministic failure

`uv run ruff check` fails with 29 findings in the two MOD-EXPORT Python helpers: E702/E703 statement
layout, I001 import order and F841 unused local. Correct all findings without weakening Ruff or adding
broad suppressions. The exact Ruff command in section 5 must pass.

## 3. Main-agent original-resolution failures

These failures were found by direct inspection of the current 1366, 1440, 1920 and family/state
images. They are blockers even though the current validator passes.

1. **Source-blocked state contradicts itself.** The left setup correctly says that no saved Fit result
   exists, but the right Fit source copy still names `Swift / Voce 50/50 blend · saved Fit r1`. In
   source-blocked, the graph and all adjacent copy must consistently say that no saved Fit result is
   selected. Do not expose a stale source identity. `Back to Fit` remains the primary recovery. A
   source-link control that cannot resolve an exact source must be disabled or replaced with
   non-interactive unavailable text.
2. **OpenRadioss unit status is wrong.** The inspected backend mapping contract makes unit-system
   mapping `exact` for OpenRadioss and `transformed` for Abaqus. In the OpenRadioss
   approximation-review screen, show Unit convention as Exact and update counts to
   Exact 3 / Transformed 2 / Approximated 1 / Advanced N/A 2. Validator assertions and preview text
   must enforce this target-specific difference. The same exact source+target tuple still must be
   identical across relevant states.
3. **Receipt vocabulary leaked into the normal delivered view.** The product packet requires
   `Open solver card` plus secondary `Delivery details`. Replace normal-surface `Open receipt`,
   `receipt created`, visible receipt IDs and status-bar receipt language with Solver Card/delivery
   language. Receipt identity may appear only after the bounded Delivery details or Advanced
   disclosure is opened.
4. **Family-adaptation readiness contradicts its own counts.** Both linear-viscoelastic and
   hyperelastic evidence show Approximated `0`, yet say `1 approximation acknowledged` and describe a
   bounded extension. For families with no approximation, show Ready to create, zero blockers and no
   approximation/acknowledgement claim. Derive summary, help, status bar and button state from the
   actual family rows and counts rather than metal constants.
5. **Family rows must match the declared total.** Linear-viscoelastic declares five user rows and one
   transformed mapping but its 1440 image exposes only four Exact rows. Ensure the target-specific
   Unit convention consequence is present and reachable/visible, and validate row names, statuses and
   counts for each family.
6. **Every engineering graph needs both quantities and units.** The hyperelastic Fit source lacks its
   x-axis title; use the actual selected mode quantity, e.g. `Stretch ratio [1]`, with
   `Nominal stress (kPa)` on y. The linear-viscoelastic graph must identify time on x and the
   normalized shear-response quantity as dimensionless on y (e.g. `Normalized shear modulus [1]`).
   Keep labels compact, unwarped and clear of ticks, curves, legend and status bar.
7. Preserve the improvements already verified: dominant light native preview; read-only source and
   source/output density; `True stress (MPa)` versus `True plastic strain [1]`; visible post-necking
   acknowledgement row; `1 approximation acknowledged`; and `kg · m · s; stress in Pa`.
8. Long Mapping details and long native previews must retain an unmistakable local scrollbar/rail at
   original resolution, with no title collision.

### Main-agent correction-phase follow-up

The first corrected hyperelastic capture still fails Q-05 at original resolution:

- `modeling-export-family-hyperelastic-1440x900.png` does not visibly expose
  `Stretch ratio [1]`;
- its measured source-graph box ends at y=894 while the status bar starts at y=876, so the status
  bar covers the bottom 18 px even though the label is technically inside the SVG.

Keep the same sole correction agent and adjust the family graph region so the complete hyperelastic
graph, ticks and x-axis title end above the status bar with a small clear gap. Add a validator
assertion that the rendered graph and every axis-title bounding box are contained above the status
bar, not merely inside the SVG wrapper. Recapture all packet targets/evidence and rerun every gate.

The subsequent original-resolution check found one remaining Q-06 placement failure in
`modeling-export-family-linear-viscoelastic-1440x900.png`: the lower-right legend crosses the
descending relaxation curve. Keep the same correction agent and place the viscoelastic legend in
clear plot whitespace (the upper-right region is appropriate for this curve) without changing the
safe metal/hyperelastic placements. Add a family-specific deterministic overlap/position assertion,
recapture all packet targets/evidence and rerun every gate.

The complete state-image review then found rejected product language surviving in the delivery-error
and long-mapping evidence. Replace visible `preflight` with the canonical `Export check` language
and describe the failed action as Solver Card creation, not a delivery request. Remove synthetic
`evidence 01`…`evidence 28` suffixes from visible long Mapping details; use neutral target-field or
mapping-detail identifiers that do not reintroduce developer/governance vocabulary. Add a
deterministic assertion that every normal/state/family surface is free of visible `preflight`,
`mapping sheet`, `next safe action` and undisclosed `receipt/evidence` language. Receipt identity
remains allowed only after the explicit Delivery details or Advanced disclosure. Keep the same
correction agent, recapture all packet targets/evidence and rerun every gate.

The corrected 1366 delivery-error image also exposes a second, partially clipped
`Retry Export check` below the intended `Retry create`. This violates the packet's one-specific-
retry rule because the last valid Export check and preview are explicitly preserved. In
delivery-error, expose only `Retry create`; do not render a redundant check action. Add a
state-specific assertion for exactly one visible recovery action, keep the same correction agent,
recapture all packet targets/evidence and rerun every gate.

The no-target state still renders an undeclared concrete tuple (`Version 2025`, `kg · m · s`) and
six Abaqus-like Mapping detail rows while the solver/format selector is empty. This contradicts the
target-dependent mapping contract. With no Destination selected, show no version/unit defaults, no
target mapping digest/counts/rows and no target-specific native consequence. Mapping details should
provide one neutral `Select Destination` placeholder; the Fit source may remain as upstream source
context. Add assertions for an empty target tuple, zero mapping rows/counts and no concrete target
values before selection. Keep the same correction agent, recapture all packet targets/evidence and
rerun every gate.

In the corrected no-target capture, hide the orphaned Output marker beside source Density while no
target representation exists. Also keep the exact upstream Fit source graph and `Open full graph`
visually active: a missing Destination invalidates target mapping/native preview, not the selected
Fit result. Add state-specific assertions for no Output marker/value and an active undimmed Fit
source. Keep the same correction agent, recapture all packet targets/evidence and rerun every gate.

## 4. Validator strengthening

The validator must fail for each issue above. Add target/family-specific assertions for:

- source-blocked Fit copy and source-link availability;
- Abaqus versus OpenRadioss unit row/status/counts;
- absence of receipt vocabulary and IDs before Delivery details/Advanced disclosure;
- family-specific readiness text, counts, row sets and graph axis titles;
- visible/reachable local scroll rails in long mapping/native-preview evidence.

Keep lifecycle `pending` and product-owner approval absent. Do not mark the main-agent evaluation
accepted.

## 5. Required gates

Run and report:

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

Return exact changed paths, all results, six approval-image paths/viewports/SHA-256 values, family
adaptation hashes and residual concerns. Do not request product-owner approval.
