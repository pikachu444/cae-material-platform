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

The full scoring method and hard gates are defined in
[`ux-visual-system.md`](../01-product/ux-visual-system.md).
