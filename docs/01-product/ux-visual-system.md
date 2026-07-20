# UX visual system and reference-similarity contract

Status: authoritative; production implementation requires an approved responsive prototype

## 1. Design grammar

This is an engineering application, not a document page or a dashboard of independent cards.
Materials and Modeling use the full application width with 16–24 px side margins at 1440 px.
Workspace regions share one continuous surface and are separated by alignment, whitespace, and thin
dividers. Radius and shadow are reserved for controls and overlays, not persistent workspace panes.

- Page title: 18–20 px, regular/medium; never a marketing hero.
- Body and engineering data: 14 px minimum.
- Tree, table support text, and metadata: 12–13 px minimum, regular/medium.
- Tree row: 24–28 px. Result row: 32–40 px.
- One accent color; selected state must also use shape, underline, or background.
- One primary action per current task region.
- No nested cards, decorative gradients, repeated uppercase eyebrows, or badge collections.

## 2. Materials layout

At 1440 px the application workspace has 32–48 px total outer margin. The default structure is a
220–250 px explorer and a fluid result/datasheet. Optional selected context is 280–300 px and may
open only when it leaves at least 820 px for results. At 1366 px the context defaults closed.

The explorer contains the actual Database → Profile → Table → Folder → Record hierarchy and compact
filter disclosures on the same surface. Search and Tree selection restore the same Record and exact
revision. Tree rows use normal text and a flat selected row; they are never separate cards.

## 3. Modeling layout

The default Process/Fit structure is a 180–210 px curve/process explorer and one fluid graph region.
A permanent third inspector column is forbidden. Current-step controls sit in a graph-adjacent ribbon
no higher than 156 px; advanced Recipe, Batch, JSON, revision, and detailed diagnostics use a drawer
or disclosure.

At 1440 px the actual graph SVG is at least 1,050 px wide and at least 72% of the workspace. It is at
least 920 px at 1366 and 1,450 px at 1920. Curve names use 12–13 px regular text, at most two lines,
and expose the full value on hover/focus. Candidate, fitting range, blend, and extrapolation controls
remain visible in the current-step ribbon.

## 4. Structural reference rubric

Reference and target screenshots are annotated with normalized rectangles for navigation,
search/control band, explorer/filter, result/datasheet, context, curve tree, settings, graph, primary
action, and advanced disclosure. Browser DOM bounds provide the target measurements.

| Criterion | Points | Pass condition |
| --- | ---: | --- |
| Region topology | 25 | Required regions have the reference-derived order and adjacency. |
| Dominant area and proportion | 25 | The same user-work region dominates; area differs by no more than 12 percentage points. |
| Information density and typography | 15 | The specified type and row ranges pass; title/body ratio is no more than 1.5. |
| Surface and divider grammar | 15 | Zero nested cards and zero persistent pane shadows; dividers establish hierarchy. |
| Selection and task continuity | 10 | The selected Material/curve owns the visible detail or graph without losing context. |
| Primary action and disclosure | 10 | One current primary action; advanced/internal information does not compete. |

Every screen must score 85/100 or better. Region topology, the dominant result/graph, and zero nested
cards are hard gates independent of total score. Pixel-level similarity, SSIM, brand colors, logos,
commercial icons, and proprietary names are not scored.

## 5. Screen-specific hard gates

- Materials fails if Tree is only a link, results are not wider than context, or headings/forms occupy
  more first-viewport area than data.
- Modeling fails if a permanent third column exists, the graph is below 70% of workspace width, three
  or more boxed bars precede the graph, curve names are oversized/truncated, or key inputs exist only
  under Advanced.
- CAE Card fails if more than one primary action competes with Download, technical IDs appear in the
  normal viewport, or solver context is detached from the selected Material.

Any deliberate deviation is recorded with the product requirement that justifies it. A score never
replaces explicit product-owner approval of the side-by-side review.
