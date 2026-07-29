# Issue #167 sole correction packet — WAVE-04 / MOD-EXPORT

Date: 2026-07-29
Author: active `/root` Sol XHigh main agent
Correction role: fresh configured Terra High, sole correction for this family
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Boundary

Correct the Luna Max MOD-EXPORT result in place. Read the original implementer packet and this
packet in full. Retain the approved shell, Export split topology, exact current contracts and all
working deterministic evidence. Do not redesign the family, modify a dependency, touch ACT-QUEUE,
production, shared manifest/inventory/common evidence, GitHub or git state.

Owned paths are exactly the MOD-EXPORT paths in section 7 of
`issue-167-implementer-packet-mod-export-wave-04.md`.

## Main-agent original-image rejection

The writer's deterministic validator passed, but direct original-resolution inspection of all six
approval images rejected the bundle. The following are blocking:

1. State truth is contradictory.
   - source-blocked still says `Saved Fit result · Export preview`, `Export preview ready`,
     `0 warnings` and retains a saved Fit selection in the footer;
   - approximation-blocked still says preview ready with `0 warnings`;
   - delivered still says Export preview ready instead of delivered/receipt created.
   Update top context, stage status and status-bar selection/job/warning for every canonical and
   evidence state. The validator must assert the visible state-specific values.
2. Source-blocked recovery is wrong.
   - the body shows a filled disabled Deliver button instead of one safe primary `Back to Fit`;
   - Regenerate preview looks actionable despite the missing source;
   - the mapping row says `Missing target quantity` although the exact saved source is missing;
   - copy says choose a source before selecting a target while a target is already selected.
   Provide one body-level safe primary Back to Fit, hide the duplicate top recovery in this state,
   visibly disable preview, name the exact missing source and preserve the selected target without
   contradictory copy.
3. Mapping evidence is internally inconsistent.
   - normal shows `Exact 3 + Transformed 2 = 5 rows` but only two exact and two transformed rows;
   - approximation shows counts totaling six but the header and visible list contain five.
   Add the missing truthful exact mapping row or correct the counts. At every state, the header row
   count, visible rows and category totals must agree. Validate this from visible DOM rows, not all
   hidden rows.
4. Delivered receipt is not actionable.
   Copy says the receipt is a secondary link, but no visible receipt link exists. Keep
   `Open delivered card` as the sole filled primary and provide one visible secondary
   `Open receipt` action using the existing synthetic receipt identity. Do not add Activity,
   review, approval or release semantics.
5. Engineering quantity copy is wrong and the source graph is not usefully readable.
   - `True plastic strain · MPa` assigns a stress unit to plastic strain. Replace it with a compact,
     correct pair such as `Yield stress (MPa) vs true plastic strain [1]`.
   - at 1366/1440 the graph axis/legend glyphs are too small for useful inspection. Keep this region
     bounded and secondary, but make rendered ticks at least 10 px and titles/legend at least
     10.5–11 px, with no collisions. Preserve positive initial true yield stress, the correct
     quantities, in-plot curve-free legend, data-relative range/headroom and uniform SVG geometry.
6. The qualitative checklist overclaims applicability.
   Q-11 is not applicable because Export has no Fit rail. Q-02 concerns a result list rather than a
   mapping sheet and may be N/A with that reason; Q-09 must still evaluate the long mapping/native
   overflow affordance. Q-05 cannot pass until the rendered graph typography and corrected quantity
   copy are directly evidenced. Recompute all Q-01–Q-11 records after recapture.

## Preserve

- 300–360 px properties pane and dominant native card preview;
- exact selected saved source/target and ephemeral-preview versus immutable-delivery distinction;
- synthetic Abaqus/OpenRadioss 2025 kg-m-s boundary;
- approximation acknowledgement bound to its exact identity;
- no unsupported normal mapping, no automatic delivery, no fabricated Activity projection;
- independent properties/native/mapping scrolling and zero page overflow;
- all four evidence-only states at 1366×768, 1440×900 and 1920×1080;
- one filled primary action per current state and visible disabled reasons.

## Required gate strengthening

Extend the writer-owned validator so it fails on every rejection above:

- expected top/stage/footer state strings for normal, source-blocked, approximation-blocked,
  delivered, no-target, loading, delivery-error and long-mapping;
- visible mapping category counts equal displayed count and header row count;
- source-blocked has one filled Back to Fit, no enabled Regenerate/Deliver and a source-specific
  mapping explanation;
- delivered has one filled Open delivered card and one visible secondary Open receipt;
- correct source quantity copy;
- computed rendered graph tick/title/legend sizes, label containment, positive initial yield,
  responsive uniformity and curve-free legend;
- corrected per-state Q-01–Q-11 applicability/evidence.

Run both helpers with `--help`, recapture every target/state, then rerun the original packet commands,
Ruff, Node syntax, inventory and scoped diff checks. Open all six corrected candidates and
representative evidence images at original resolution.

## Handoff

Return changed files, exact commands/results, six new SHA-256 values, state-evidence paths,
Q-01–Q-11 results and residual concerns. Do not edit shared integration files, request approval,
commit or start another family.
