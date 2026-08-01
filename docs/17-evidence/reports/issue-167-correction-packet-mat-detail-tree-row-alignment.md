# Issue #167 correction packet — MAT-DETAIL tree-row alignment

Date: 2026-07-30
Owner: active `/root` main agent
Correction writer: one fresh configured `correction_terra_high`
Scope: sole correction for the pending `Materials / Datasheet / Overview / normal` wide-density bundle

## Product-owner finding and deterministic diagnosis

The product owner rejected the submitted 1920×1080 representative image because each navigator
identity appears on a different line from its type glyph. The active main agent reproduced the
failure in the rendered DOM.

There is no newline character in the label. The normal navigator grid declares columns for
disclosure, type glyph and label, but the Datasheet HTML child order is
`disclosure → label → type glyph`. The label is explicitly placed in column 3 before the later type
glyph requests column 2. With ordinary sparse grid auto-placement, Chromium moves that glyph to the
next implicit row.

Measured 1920×1080 failure:

- every `.tree-row` is 25 px high;
- the label occupies the first implicit row;
- the `.tree-kind` box starts at the label bottom;
- label and type-glyph centers differ by 12.5 px for all 7 nodes.

This is an applicable Q-03 failure. Deterministic containment, overflow and row-height checks did not
measure child-row alignment, so the prior gate and reviewer incorrectly passed it.

## Bounded correction

Correct the shared normal navigator grid rule in
`docs/00-research/ux-service-reference/materials-navigator.css`:

- explicitly place `.tree-disclosure`, `.tree-kind` and `.tree-label` on grid row 1;
- retain their existing columns, 24–26 px row height, indentation, glyphs, identity text and
  horizontal/vertical overflow behavior;
- do not use a transform, top/margin nudge, new line-height, absolute positioning or a Datasheet-only
  visual offset;
- do not reorder the shared Datasheet HTML. Related/Empty intentionally disable the normal navigator
  stylesheet and use the base `disclosure → label → textual kind` order; reordering the HTML would
  break those already-approved states.

The Search normal HTML already orders `disclosure → type glyph → label`; explicit grid row 1 must be
pixel-neutral there. The six approved Datasheet Related/Empty canonical/responsive images must remain
byte-identical.

## Required executable evidence

Update only the Datasheet capture/validator evidence needed to make this regression impossible:

1. `capture_materials_datasheet_wave01.py` records, for every tree row:
   - DOM child class order;
   - disclosure, kind and label box centers;
   - maximum center delta;
   - whether all three resolve to the same CSS grid row.
2. `validate_materials_datasheet_wave01.py` fails unless:
   - the normal navigator resolves all 7 nodes to one grid row;
   - each child center delta is at most 0.5 px;
   - compact/wide targets and splitter-width snapshots retain the same contract.
3. Recapture the 1366×768, 1440×900 and 1920×1080 normal targets plus 2560×1440 and 3840×2160
   supporting evidence.
4. Assert the six approved Related/Empty hashes remain byte-identical.
5. Confirm the three approved Search normal image hashes remain unchanged:
   - 1366×768 `bd400b2f913a0d2c8c1e5dba6565c05b12055118ffbbaac1b9e5845cf6bfff89`
   - 1440×900 `7f96a68d0ff03eb20b95abf831354e6a1052e34f0246871c9318ede0cce367a0`
   - 1920×1080 `57f136268f52386c99cb13970f694cf40a30bdb57a6bc3badcab0b70a24ed3ae`

## Ownership and preservation

The correction writer may edit only:

- `docs/00-research/ux-service-reference/materials-navigator.css`
- `docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py`
- `docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py`
- the three normal Datasheet PNG/measurement pairs
- the two normal wide-evidence PNG/measurement pairs
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-wave01.staging.json`

Do not edit the common manifest, inventory, product/UI specifications, acceptance matrix, common
evidence report, Search sources/evidence, Related/Empty sources/evidence, production React/CSS or any
unrelated dirty-worktree path. Do not commit, push, open a PR or start another agent.

Preserve without reinterpretation:

- the exact ordered 29-point Engineering strain / Engineering stress source;
- data-span-relative axis headroom and proportional SVG geometry;
- compact graph-only versus wide graph-plus-grid topology;
- response-grid local scroll contract;
- navigator resizing, local scroll and complete identity behavior;
- Application condition, CAE delivery, tabs, actions and all domain/state semantics.

## Required commands

Run:

```powershell
python docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1366x768
python docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1440x900
python docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --all-packet-targets --expect-main-agent-status rejected --assert-preserved-hashes
python docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py --target materials-datasheet-overview-normal-1920x1080 --wide-evidence --expect-main-agent-status rejected --assert-preserved-hashes
node --check docs/00-research/ux-service-reference/materials-datasheet.js
node --check docs/00-research/ux-service-reference/materials-navigator.js
python -m py_compile docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_datasheet_wave01.py docs/00-research/ux-service-reference/validate_materials_datasheet_wave01.py
git diff --check
```

Return exact changed paths, new image SHA-256 values, alignment measurements, preserved-hash proof
and command outcomes. The active main agent owns manifest/evidence integration, original-image
review, reviewer packet and product-owner handoff.
