# Issue #167 sole correction — MOD-DATA axis unit notation

Date: 2026-07-30  
Writer: configured fresh correction writer  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Main-agent override

The first wide implementation and fresh review pass the responsive geometry, but the main agent
rejects one contract deviation before product-owner handoff.

- The authoritative implementation packet requires y-axis `Engineering stress (MPa)`.
- `docs/01-product/desktop-engineering-ui-spec.md` uses `Engineering stress (MPa)`.
- The accumulated engineering-graph rule places the unit in the axis title; the accepted notation
  for stress axes is parentheses, as also used by the current Export graphs.
- The implementation and reviewer instead accepted `Engineering stress [MPa]`.

Numeric and qualitative review do not override the explicit product notation.

## Sole required change

1. Change only the plotted y-axis title from `Engineering stress [MPa]` to
   `Engineering stress (MPa)` in the static renderer, expected labels, accessibility/evidence and
   relevant deterministic assertions.
2. Keep `Engineering strain [1]` unchanged.
3. Do not alter geometry, bounds, margins, fonts, strokes, legend, series, responsive topology,
   source/mapping behavior or state recovery.
4. Recapture all seven targets and existing responsive/state evidence because the rendered text and
   image hashes change. Prove all prior wide gates still pass.

## Ownership and gates

Own only the MOD-DATA packet paths and images listed in
`issue-167-wide-correction-packet-mod-data.md`. Preserve all concurrent work. Do not touch common
manifest/inventory/evidence, production files, other families, git or GitHub state.

Run the full gate set from the parent packet, open all seven targets at original resolution and
report the final hashes. This is the one MOD-DATA correction before fresh re-review.
