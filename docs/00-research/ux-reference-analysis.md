# Reference-derived layout analysis and rejected interpretation

Status: authoritative input for the design approval gate

Every image in `ux-reference-gallery/images` was opened at original resolution. This analysis is
about layout grammar and interaction, not pixels, color, branding, icons, or inferred internals.

| Reference | Opened visual structure | Transfer to this product | Do not transfer |
| --- | --- | --- | --- |
| Granta MI favourites/list | Narrow continuous browse surface beside a dominant dense list; normal-size row labels, thin dividers, explicit row selection, almost no component boxes. | Keep a persistent governed explorer next to dense material results/datasheet. | Logo, dark brand rail, proprietary database names and icons. |
| Material Data Center search/detail | Persistent filters, flexible results, and selected detail are unequal connected regions; selection visibly owns the right detail. | Preserve query and selection while results and context update; context is optional when width is tight. | Orange annotation markers, branding, exact result-card decoration. |
| Material Data Center CAE Model | One short sequential solver/model/unit surface ending in Download. | Keep card selection inside Material context and make Download the single primary action. | Commercial solver catalog and product terminology. |
| Material Modeler curve fitting | A shallow, horizontally dense control band sits above a graph spanning almost all width. | Put current-step controls in a compact ribbon and let the graph own the remainder. | Exact workflow labels, equations, icons, or desktop widget styling. |
| Material Modeler hyperelastic fitting | A narrow settings list supports a plot occupying roughly 70% of the work area; candidate visibility maps directly to curves. | Keep compact curve/candidate controls adjacent and guarantee a graph-dominant ratio. | Proprietary model list, target solver names, and pixel geometry. |

## Corrected interpretation

The previous interpretation accepted a 210–250 px rail, a 743 px graph, and a 280–340 px persistent
inspector at 1440 px. That reproduced the count of three columns without reproducing Material
Modeler's graph dominance. It also treated Granta-style hierarchy as a secondary route instead of a
normal-density explorer integrated with the data surface. That interpretation is rejected.

The approved target uses:

- Materials: explorer + dominant results/datasheet, with optional context only when width permits;
- Modeling: curve/process explorer + dominant graph, with a shallow settings ribbon and advanced drawer;
- CAE Card: one focused delivery surface with one Download action;
- flat continuous workspace regions instead of independent rounded cards.

## Follow-up density correction

The first prototype still rendered each Modeling curve as a 39–56 px multi-line evidence item. That
choice attempted to preserve the full imported identifier and revision in the always-visible rail,
but it contradicted both the Modeler reference and progressive disclosure. The reference treats
curve/file names as ordinary compact list strings; units live in graph axes and mapping controls.
The corrected prototype therefore uses 26 px tree rows with `Specimen 01`-style labels and moves the
full source ID, revision, unit mapping, and provenance to hover/focus detail or Evidence.

The first Materials prototype also proved only an eight-node tree and had no Tree-local search. That
was insufficient evidence for a governed large database. The corrected explorer has fixed Browse /
Filters / Subsets modes, a fixed `Find in tree` field, an independently scrolling hierarchy, retained
ancestor paths for matches, keyboard focus movement, node-type glyphs, and a 240–280 px responsive
pane. Production acceptance additionally requires lazy server loading and row virtualization against
a synthetic 10,000-record hierarchy.

The full scoring method and hard gates are defined in
[`ux-visual-system.md`](../01-product/ux-visual-system.md).
