# Reference-layout design review

This directory is the mandatory design gate before production React/CSS implementation. The pages
are responsive static prototypes; they do not call product APIs and are not application routes.

- [`materials.html`](materials.html): governed searchable explorer, sibling Filter/Subset modes,
  dense results, selected context
- [`detail.html`](detail.html): Layout-style Material datasheet and direct CAE action
- [`modeling.html`](modeling.html): 26 px plain-text curve/process tree, settings ribbon, dominant Fit graph
- [`activity.html`](activity.html): role-aware attention queue with saved views and row-specific actions
- [`administration.html`](administration.html): object navigator, object list, property editor and live preview
- [`export.html`](export.html): reviewed graph continuity into solver mapping/export
- [`card.html`](card.html): focused native preview and one Download action

`region-annotations.json` records the normalized structural regions observed directly in each local
reference. `similarity-report.md` records browser-measured prototype dimensions, rubric scoring,
known deviations, and the approval decision. Historical captures live under
`docs/17-evidence/images/ux-layout-review/`; the product-owner-approved UXC-00D four-screen
proposal lives under `docs/17-evidence/images/uxc-00d-responsive-design/`.

Review order:

1. Open the five reference images at original resolution.
2. Open each prototype at 1366×768, 1440×900, and 1920×1080.
3. Compare region topology, dominant-area proportion, density, surface grammar, selection continuity,
   action position, and progressive disclosure.
4. Reject any hard-gate failure even if the total score is 85 or higher.
5. UXC-00D was explicitly approved by the product owner on 2026-07-26. Production React/CSS work
   may begin against these hard gates; the static pages remain proposal evidence, not current routes.
