# T-97 Materials state continuity and compact Administration

Date: 2026-07-21

## Bounded implementation slice

This increment closes two continuity gaps without replacing the configurable Catalog engine.
Materials search, typed filters, sorting, navigator mode and selected Material are encoded in the
`/materials` query. Opening Material Detail records that exact return path, and returning restores
the previous results rather than starting a new search. The last Browse Record remains a governed
`ConfigurableLinkEndpoint`; re-entry reloads its real Table/Folder ancestor path instead of storing a
flat material-family imitation.

Administration keeps the existing Table, Attribute, Layout, Subset and exact Link Type APIs, while
using the same compact visual grammar as Materials and Modeling. The 220 px navigator and 52 px
Attribute rows use plain labels and dividers. The old 48 px heading, dark proprietary-looking rail,
rounded schema cards and repeated status surfaces are removed. Attribute Description now writes to
the existing immutable `help_text` contract.

## Reference and before/after comparison

| Source inspected | Interaction principle applied |
| --- | --- |
| `docs/00-research/images/gui-reference/granta-contents-tree.png` | A narrow, ordinary-font navigation rail and selected-row marker remain readable without large tiles. |
| `docs/00-research/images/gui-reference/granta-profile.png` | Table/Attribute definitions are data rows on one continuous surface, not independent feature cards. |
| `docs/00-research/ux-reference-gallery/images/granta-mi-favourites-list.png` | Repeated records use compact list rhythm, restrained type metadata and horizontal dividers. |
| Existing `docs/15-demo/images/t78-database-design.png` | Before: 48 px title, 250 px dark rail, two rounded container cards and eight rounded Attribute cards. |
| `docs/15-demo/images/ux-redesign-v2/administration-database-1440x900.png` | After: 20 px title, 220 px light rail, 340 px Table definition column, 792.1 px Attribute/Layout column and eight 52 px divider rows. |

Brand colors, logos, commercial icons, product names and proprietary workflows were not copied.

## Live measurements

Docker/Chromium at a 1440×900 viewport reported:

| Measurement | Result |
| --- | ---: |
| Browser content width | 1,425 px |
| Administration workspace | 1,425 px |
| Outer horizontal margin | 0 px |
| Navigation | 220 px |
| Overview content | 1,205 px |
| Database Table definition column | 340 px |
| Attribute/Layout column | 792.1 px |
| Page title | 20 px CSS / 25 px line box |
| Attribute row | 52 px |
| Overview task row | 90.4 px |

The workspace begins immediately below the 61 px application header and does not inherit a document
`max-width` or centered margin.

## Actual browser scenario

The administrator scenario used the live protected API and PostgreSQL-backed demo:

1. opened `Administration → Database design`;
2. selected `Demo Material Records` Table;
3. added synthetic text Attribute `ux_acceptance_note_20260721`, display name `UX acceptance note`
   and a Description through the real create-Attribute contract;
4. created a new `Engineering datasheet` Layout from current exact Attribute revisions;
5. opened the Material Database preview and selected the DP780 Record;
6. verified `UX acceptance note · text · Not set` in the Record Datasheet.

The scenario also confirmed one saved Subset and one `many:many` Link Type with forward/reverse
labels. The new Attribute is intentionally empty; no engineering value was invented.

## Verification

- Focused React suite: 3 files, 15 tests passed before the Description field extension; its API
  assertion was then extended to cover `help_text` and is included in the full-suite gate.
- Materials component coverage verifies URL query restoration, Detail return and exact Browse Record
  ancestor restoration under one second.
- Browser DOM confirmed Table, nine typed Attributes after the synthetic scenario, two Layouts, one
  Subset, exact Link Type cardinality/labels and Layout-driven Record projection.
- Compatibility routes `/catalog/schema` and `/datasets/processing` now render the canonical
  Administration and Modeling workspaces; the dead Common Processing lazy import was removed.

## Remaining limits

- The synthetic Attribute mutation is local demo acceptance data and is not committed as a product
  fixture or production domain definition.
- Column resizing remains optional; Administration uses bounded columns and the existing responsive
  single-column fallback below 1100 px.
- The final 1366/1440/1920 scenario matrix, accessibility audit, clean-demo and backend regression are
  tracked by the remaining T-97 acceptance increment.
