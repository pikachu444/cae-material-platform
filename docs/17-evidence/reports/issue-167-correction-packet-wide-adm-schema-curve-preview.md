# Issue #167 correction packet — ADM-SCHEMA-CORE wide Layout/Record preview

Date: 2026-07-30
Owner: active `/root` main agent
Correction role: one fresh configured Terra High implementer
Scope: sole correction after the Luna implementation failed the main-agent original-image gate

## 1. Gate disposition

The Luna implementation passes its deterministic checks and preserves the frozen 1366/1440
targets, but it fails the mandatory qualitative owner gate at original resolution.

Measured failures:

- At 1920×1080 the preview client is 930 px high, but its content is 1,478 px high. The graph frame
  begins at y=1,080.8, below the viewport, so only the `Representative response` heading is visible.
- At 2560×1440 the graph begins at y=933.3 and ends at y=1,765.3. At 3840×2160 it begins at
  y=933.3 and ends at y=2,445.3. The x axis, x-axis title and lower plot region are therefore outside
  the initial viewport in both wide captures.
- The graph remains confined to the right preview column while the bounded 808 px editor column
  has a dominant blank lower region. At 3840 the graph grows to 2,289×1,512 inside the right column
  while the adjacent editor remains almost entirely empty. This replaces one blank region with an
  oversized, partially hidden plot and does not resolve Q-20.
- The two twelve-row tables stretch across very wide columns at 2560/3840, producing excessive
  inter-column whitespace rather than denser, more useful evidence.

This is a design/viewport failure even though scroll access exists. A primary engineering plot must
appear as a complete readable unit in the initial normal wide workspace; a scrollbar is recovery for
genuine detail overflow, not a substitute for the initial graph composition.

## 2. Preserve the successful contract work

Keep:

- the exact twelve Attribute Definition revisions, ordered Layout items, saved Record typed values,
  curve Artifact identity/hash and state-truth rules implemented in the first pass;
- the three-pane outer topology, splitters, editor flows, conditional fields, stale/conflict/error
  behavior and exact lower-view hashes;
- the graph semantics, data-relative headroom, accessible name/description, axes
  `Engineering strain` and `Engineering stress (MPa)`, and non-distorted responsive coordinate
  system;
- absence of saved projection/graph in zero-Table and unsaved new-Table states.

Do not revert the contract expansion merely to make the screen fit.

## 3. Required correction

Recompose the *inside* of the existing editor/preview region so the saved projection uses the
available width and height rather than remaining a narrow fourth-looking rail.

1. In normal read-only state, use a compact top evidence band and a dominant graph band beneath it.
   The graph band may span the full existing editor pane (editor plus preview width) because it is
   the linked result of the same selected Table/Layout/Record, not a new inspector. Do not add an
   outer pane, dashboard card or route.
2. Keep the Table definition summary bounded at the upper left. Keep Record identity plus compact
   Record/Layout evidence at the upper right. The twelve fields remain reachable, but they need not
   all consume unbounded page height:
   - use bounded local table regions with honest visible scrollbars when rows overflow, or
   - use a compact `Record values | Layout fields` switch/disclosure with one bounded table at a
     time.
   Do not hide the field count, exact revisions or the selected curve field.
3. At 1920×1080 normal, the complete plot frame, both axis titles and curve must be visible in the
   initial viewport without scrolling. Target a useful plot height of at least 360 px.
4. At 2560×1440 and 3840×2160, let the graph expand into the available lower editor-pane region,
   but keep its complete frame and axes above the status bar. The rendered box and viewBox must
   remain proportional to one another; do not stretch text or strokes with CSS transforms.
5. Eliminate the dominant blank lower editor region. At each of 1920/2560/3840, the graph should
   begin shortly after the compact top band and reach near the useful lower workspace. Record the
   top-band, graph and remaining-blank geometry.
6. In Table/Attribute edit states, the form remains primary. Preserve a smaller but complete linked
   graph in the preview when space permits; the twelve-field evidence may use a bounded local
   disclosure/scroll region. Never allow the graph heading alone to imply a hidden plot.
7. Normal short table regions show no fake scrollbar. Any real local overflow uses a reserved,
   proportional, keyboard/pointer/wheel-operable rail outside text.
8. Preserve the visual density of the successful 1366/1440 targets exactly. Wide-specific changes
   must not alter their bytes.

## 4. Acceptance evidence

Recapture and inspect:

- the three 1920 approval candidates;
- every affected 1920 state;
- the 2560 and 3840 normal support captures.

The validator must additionally fail when:

- any graph frame or axis title is outside the initial viewport in a graph-bearing normal target;
- the normal preview requires vertical scrolling to reach the graph;
- the graph occupies only the right preview rail while more than 40% of the adjacent editor-pane
  lower region is blank;
- the graph frame bottom is below the status bar;
- a table rail is visible without actual overflow.

Rerun the complete packet capture/validator, frozen lower hashes, state-truth checks, Ruff, Python
compilation, Node syntax, inventory validation and `git diff --check`. Open the final 1920, 2560 and
3840 images at original resolution before returning.

## 5. Ownership and prohibitions

Own only the Administration paths granted in the original wide packet:

- `docs/00-research/ux-service-reference/administration-schema-core.{html,css,js}`;
- its WAVE-05 capture, validator and staging JSON;
- affected Administration image/measurement outputs.

Do not edit Materials, Modeling, Activity, production React/CSS, common manifest/inventory/policy,
the common freeze report, GitHub state, commits, pushes or PRs. Other agents are working in the same
worktree; preserve their changes and never revert or overwrite them.
