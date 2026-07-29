# Issue #167 implementer packet — WAVE-01 / MAT-DETAIL

Date: 2026-07-29  
Writer role: configured `implementer_luna_max`, exactly one writer for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Complete the remaining three approval images in the `MAT-DETAIL` family without changing the two
approved parent images:

1. `materials-datasheet-overview-normal-1920x1080`
2. `materials-datasheet-related-long-1440x900`
3. `materials-datasheet-empty-1440x900`

This is static reference work only. Do not change production React/CSS, the common reference
manifest, the finite inventory, the common evidence report, user guides, current screenshots, git
state, commits, branches, remotes or GitHub.

## Product task and visual judgment

A normal Materials user has selected an exact material Record from the catalog tree and continues
inside one explorer/datasheet workspace. They must be able to:

- retain Database/Profile/Table/Folder/Record location and selected Record context;
- read governed properties with value, unit, condition and source together;
- inspect a representative engineering response with data-relative axis headroom;
- see application conditions and available native solver-card delivery;
- follow Related records without losing the current Record or explorer context;
- recover safely when the selected Record contains no displayable governed data.

The approved reference is a dense desktop engineering datasheet, not a dashboard. Dividers,
alignment and flat table/graph regions take priority over cards, badges, shadows or decorative
containers. Tree text is 12–13 px and data/body text is 14 px where practical. The graph/property
region remains dominant; the navigator and context column stay restrained.

## Frozen authorities inspected by the main agent

- `AGENTS.md`
- `docs/01-product/service-reference-inventory.yaml` (`MAT-DETAIL`)
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/00-research/ux-service-reference/reference.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`
- `docs/00-research/ux-service-reference/materials-datasheet.css`
- `docs/00-research/ux-service-reference/materials-datasheet.js`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.css`
- `docs/00-research/ux-service-reference/materials-datasheet-overview-normal-1366x768.js`
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  (`c54bcab3b473ea0b6a451cb5def06b672d88efde8d7007c185d26d94802b54c8`)
- `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  (`362b5ad430f7e10ef9533589e34186c42bce28cca6d9bbf799c91e5538ca5a98`)
- current contract sources:
  `apps/web/src/material-library.tsx`,
  `apps/web/src/material-datasheet-projection.tsx`,
  `apps/web/src/materials-browse-tree.tsx`,
  `apps/web/src/design/resizable-split-pane.tsx`,
  `apps/web/src/api.ts`, and `apps/web/src/types.ts`

The approved 1440 and 1366 images, their registered HTML/CSS/JS and their data-relative
plot-domain policy are visual authority. Do not redesign them.

## Family ownership

The writer may create or edit only:

- `docs/00-research/ux-service-reference/materials-datasheet*.html`
- `docs/00-research/ux-service-reference/materials-datasheet*.css`
- `docs/00-research/ux-service-reference/materials-datasheet*.js`
- a MAT-DETAIL-only capture helper under
  `docs/00-research/ux-service-reference/`
- a MAT-DETAIL-only validator under
  `docs/00-research/ux-service-reference/`
- the three target PNGs and their target-specific measurement/evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit:

- `reference.css`, `reference.js`, or any `materials-search*` source;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- either approved 1440/1366 datasheet PNG, measurement file or lifecycle source;
- any file under `apps/`;
- any other writer's `modeling-data*` files.

Other agents may work in the repository. Preserve their edits and never reset, clean, stash,
discard or overwrite unrelated files.

## Required target definitions

### Normal 1920×1080

- Use the exact normal overview content and interactions of the two approved parents.
- Add only a target-specific responsive override when needed.
- Start from a restrained approximately 280 px navigator and 300 px context column, with one 5 px
  interactive navigator divider and a dominant datasheet main region. Derive and record the exact
  safe geometry; do not force these approximate values if containment proves a nearby value better.
- Keep all six tabs, four property rows, representative graph, application condition and both
  Abaqus/OpenRadioss Preview and Download entry points visible.
- Keep the plot series extrema and `10% of each data span → nice step` range policy. For the frozen
  synthetic series, the declared axes remain 0.25 strain and 1,000 MPa; the curve must not touch
  the top or right boundary.
- Exercise default and keyboard splitter states. ARIA values must equal actual navigator width.
  Datasheet main width must never fall below 720 px.

### Related long 1440×900

- Keep application bar, command bar, selected DP780 Record, navigator, divider, record header,
  status bar and six-tab strip in the same locations as the approved overview.
- Activate `Related`; do not replace the page with a separate feature card or workflow graph.
- The main region is a flat relation table/list with columns equivalent to Relationship,
  Related Record, Record type, Exact revision and task consequence.
- Include synthetic, visibly long forward and reverse relationship wording and long record names to
  prove containment. Long labels wrap deliberately or truncate with a native `title`; never clip.
- Provide at least one forward and one reverse exact-revision relation. The visible language is user
  terminology; full UUIDs/hashes/provenance remain in Evidence and are not shown here.
- Selecting a related row updates the restrained right context; the single primary task consequence
  opens that exact related Record. Do not pretend the relation mutates.
- Keep navigator selection and current record identity intact through the interaction.

### Empty 1440×900

- Keep the same shell, navigator selection, record header, tab strip and status bar.
- Show a truthful selected Record with no displayable governed properties, curves or available
  solver card; do not fabricate values or formats.
- The main data region contains one concise empty explanation and one safe next command:
  `Back to results`. The command must cause a measurable route/hash consequence.
- The right context states why delivery is unavailable without technical identifiers.
- No nested card, decorative illustration, disabled fake download, repeated empty panels or
  oversized marketing copy.

## Static-region → production contract mapping

This reference freezes future structure; it does not implement the React port.

| Static region | Current React/component contract to preserve later |
| --- | --- |
| Application/status shell | `ApplicationShell` workspace status; selected material/revision/job/warning/connection |
| Navigator and tree | `MaterialsBrowseTree`; Database/Profile/Table/Folder/Record hierarchy, requested exact Record, keyboard selection/open |
| Resize divider | `ResizableSplitPane`; persisted viewport-class widths, collapse/expand and truthful ARIA |
| Record header/tabs | `MaterialDetailPage`; exact current material revision and route-backed overview/properties/curves/cards/evidence tasks |
| Property sheet | `currentProperty` plus `MaterialDatasheetProjection`; original/normalized quantity semantics and exact source continuity |
| Representative response | `RepresentativeCurve`/linked workflow data; persistent condition and no raw/released mutation |
| Related panel | `getCatalogWorkflowGraph`; forward/reverse Link Type labels and exact source/target revision endpoints |
| Delivery summary | `SolverCardAction`/solver-card evidence; native preview/download only when actually available |
| Empty/error return | current `materialsReturnPath()`/Back to Materials behavior; preserve selected context where data exists |

Do not invent a production tensile standard, material family policy, constitutive model, solver
mapping, validation threshold or confidential data. Use the existing synthetic DP780 reference.

## Deterministic acceptance

Provide a target-aware capture and validator which fail unless:

- each PNG is exactly its named viewport at device scale factor 1;
- there are no console errors, page errors or document/body horizontal overflow;
- one visible 5 px splitter has a 1 px rule and truthful keyboard/ARIA continuity;
- every tree-kind label and required table cell is inside its pane at all exercised widths;
- normal 1920 preserves the approved tabs, properties, formats, actions, row density and
  data-derived plot-domain computation;
- Related has one active tab, long-label containment, forward/reverse exact relations, row selection
  → context update and exact-record open consequence;
- Empty preserves selected Record/shell and has exactly one primary safe-return consequence with no
  fabricated property, curve or delivery data;
- normal and exceptional states have zero nested persistent-card hard-gate failures;
- all visible controls are semantic and keyboard reachable with visible focus;
- canonical Related/Empty targets also generate responsive evidence at 1366×768, 1440×900 and
  1920×1080 proving the topology does not change. Only the canonical 1440 PNG is an approval image.

Run at minimum:

```text
python <MAT-DETAIL capture helper> --all-packet-targets
python <MAT-DETAIL validator> --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check <changed Python helpers>
node --check <changed JavaScript files>
git diff --check
```

Because the main agent owns manifest integration, the family validator may validate a writer-owned
staging index/measurements before the manifest entries exist. It must be able to switch to the
common manifest after integration without weakening assertions.

## Handoff

Return:

- exact files changed;
- commands and pass/fail results;
- each PNG path, viewport and SHA-256;
- exact measurement/evidence paths;
- any residual limitation.

Do not modify shared integration files to make a gate pass. Do not commit or start another family.
