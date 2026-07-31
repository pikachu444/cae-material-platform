# Issue #167 ADM-SCHEMA-CORE sole correction packet — wide semantic elasticity

Date: 2026-07-31  
Status: main-agent gate rejected; one configured Terra High correction authorized  
Prerequisite: `issue-167-owner-authorized-correction-packet-adm-preview-information-architecture.md`

## Why this correction exists

The Luna implementation corrected the product owner's original finding:

- `Record preview` and `Layout definition` are now separate task projections;
- compact preview is real and reversible;
- the active table has useful height and truthful local scrolling;
- the linked graph is conditional and bounded;
- scalar Attribute editing no longer displays an unrelated graph.

The deterministic gates pass and the active main agent opened all 73 ADM-SCHEMA-CORE lifecycle,
state and wide PNGs at original resolution. The compact, 1920, loading, saving, recovery, validation
and scrolling states pass the qualitative gate. The 2560×1440 and 3840×2160 support images do not.

In:

- `administration-database-normal-wide-2560x1440.png`
  (`23971a28799262c762921a90d35a1c0f5312ad40449392eb9c4427016738da38`)
- `administration-database-normal-wide-3840x2160.png`
  (`f363923b29d99c96bc4c9c3e199cb633f8a10f52fe6cc9118631b17baf7a7f2c`)

the graph no longer dominates, but the correction leaves a very large internal horizontal void
between the bounded property content and the fixed 640 px preview. The failure is not that every
wide-display pixel is unfilled; it is that related working components are separated by what reads as
an empty third column. Contract-backed saved Record values and the selected linked curve are
available and must form a coherent left/top-aligned task cluster. Numeric success is not enough.

## Required product result

Preserve the successful one-task preview architecture. Correct only the wide composition:

- At 1920, keep the current bounded editor-plus-companion behavior unless a small rule cleanup is
  required for consistency.
- At 2560 and 3840, place the bounded editor and open preview in one coherent working cluster that
  starts from the left/top of the editor pane. The preview begins immediately after the normal
  divider and gutter; it must not be pushed to the far right by an empty intermediate column.
- Do not stretch the form controls, descriptive prose, Record grid or graph merely to eliminate
  trailing whitespace. Keep the property editor near its existing useful width (approximately
  760–820 px). The Record grid and graph use bounded readable widths inside the preview. Exact values
  remain implementation choices, not pixel-copy targets.
- Do not solve the failure by restoring a dominant full-width/full-height graph, by showing Record
  and Layout tables together, or by filling space with explanatory copy, cards, badges, internal
  terms or invented controls.
- In the active `Record preview`, when the saved curve field is selected, the saved-value grid and
  bounded graph use a two-region composition inside the same Record task. They share the same top
  edge, remain separated by only the normal gutter and do not stretch across the full display. The
  grid remains the primary projection and keeps useful height; the graph is the selected saved
  field's secondary result.
- `Layout definition` remains the mutually exclusive sibling task. It must not render the graph or
  the Record grid.
- The graph keeps its true aspect ratio, compact engineering labels, data-relative headroom and
  existing maximum-height bound. It must not exceed 360 px height or become the dominant workspace
  region.
- A scalar Attribute edit remains graph-free. Saved-vs-draft, exact revision, Add, stale,
  loading/error, keyboard, focus-return and local-scroll behavior must remain unchanged.

## Wide qualitative safety rails

At 2560×1440 and 3840×2160 with preview open:

- the property editor remains bounded near 760–820 px and the preview begins after no more than a
  normal divider/gutter (target 24 px or less);
- the active Record grid and selected graph are top-aligned and separated by a 12–24 px gutter;
- the Record region remains a readable bounded primary region (target 480–700 px), and the selected
  graph remains a bounded secondary region (target 400–1000 px and no more than 360 px high);
- the task cluster is justified to the left/top. Remaining width and height may appear at the far
  right and bottom after the bounded components;
- no component, control, row, prose block or graph is enlarged solely to occupy the remaining
  viewport;
- the active Record grid must retain at least the existing useful 10-row-class scan height and a
  truthful proportional scrollbar when overflow exists;
- the selected graph must remain secondary to the schema/Record work by area and visual weight.

These bounds are safety rails. The main acceptance remains the original-resolution Q-01–Q-20
qualitative judgment; total viewport fill percentage is deliberately not an acceptance metric.

## Exact correction ownership

The sole configured Terra High correction writer owns only:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- ADM-SCHEMA-CORE-owned PNG/measurement/state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

The correction writer must not edit shared product specs, the common manifest/inventory, this
packet, the common freeze report, production files or another family. Existing unrelated changes
belong to concurrent work and must not be reverted.

## Deterministic proof

Recapture the complete existing ADM packet: eleven lifecycle targets, all registered state evidence,
and both wide images. Do not change the 11-image lifecycle denominator.

Extend the capture/validator so wide evidence records and enforces:

- editor-pane, editor-content, preview-panel and preview-content rectangles;
- the gap between bounded editor content and preview content;
- active Record section, grid and scroll rectangles plus height/overflow/rail measurements;
- graph section, plot width and height, top alignment and inter-component gutter;
- bounded editor/Record/graph dimensions without a viewport-fill ratio;
- one active projection and conditional graph visibility.

Remove or consolidate superseded validator helpers only when doing so is safe and does not broaden
the correction. The final validator must prove the actual active path rather than passing against
stale or duplicate logic.

Required commands:

```powershell
python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

The correction writer returns changed paths, exact results and residual risks. It does not make an
acceptance decision. After the gates pass, the active main agent opens every recaptured original.
Only a passing main gate permits a fresh configured Terra High read-only review and subsequent
product-owner handoff.
