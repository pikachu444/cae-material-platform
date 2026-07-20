# Reference-layout design review

This directory is the mandatory design gate before production React/CSS implementation. The pages
are responsive static prototypes; they do not call product APIs and are not application routes.

- [`materials.html`](materials.html): governed explorer, filters, dense results, selected context
- [`detail.html`](detail.html): Layout-style Material datasheet and direct CAE action
- [`modeling.html`](modeling.html): curve/process tree, settings ribbon, dominant Fit graph
- [`export.html`](export.html): reviewed graph continuity into solver mapping/export
- [`card.html`](card.html): focused native preview and one Download action

`region-annotations.json` records the normalized structural regions observed directly in each local
reference. `similarity-report.md` records browser-measured prototype dimensions, rubric scoring,
known deviations, and the approval decision. Captures live under
`docs/15-demo/images/ux-layout-review/`.

Review order:

1. Open the five reference images at original resolution.
2. Open each prototype at 1366×768, 1440×900, and 1920×1080.
3. Compare region topology, dominant-area proportion, density, surface grammar, selection continuity,
   action position, and progressive disclosure.
4. Reject any hard-gate failure even if the total score is 85 or higher.
5. Production implementation begins only after an explicit product-owner approval is recorded.
