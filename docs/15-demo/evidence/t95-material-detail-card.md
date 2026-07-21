# T-95 Material Detail, Layout projection, and native CAE card delivery

Date: 2026-07-21

## Bounded implementation slice

Material Detail now keeps the approved five task tabs:

```text
Overview | Properties | Curves | CAE Cards | Evidence
```

The first 1440×900 viewport shows the selected Material name/grade, family, source, lifecycle,
normalized key properties, application conditions, representative curve, available solver formats,
and one primary native download action. OpenRadioss is selected only because it is an actually
available governed card in this demo Material, not as a hidden solver default. The adjacent Preview
action opens its native ASCII before download.

The configurable Catalog remains authoritative. Properties and Curves project the selected Record's
administrator-defined Attribute/Layout data. Evidence offers the additional Layout selector and all
typed values, including original plus normalized quantity text, curve/file artifacts and exact
Record references. No Table, Attribute, Layout, Subset or Link Type engine was replaced.

## Reference-derived interaction principles

| Directly inspected reference | Applied principle |
| --- | --- |
| `docs/00-research/images/gui-reference/granta-datasheet-full.png` | One selected Record owns a flat datasheet with stable sections; persistent panels are divided rather than nested cards. |
| `docs/00-research/images/gui-reference/granta-record-links-datasheet.png` | Related Records use typed forward/reverse labels and visible revision numbers; the full exact IDs remain in disclosure. |
| `docs/00-research/ux-reference-gallery/images/material-data-center-cae-model.png` | Solver availability stays attached to the selected Material and the delivery action is immediately visible. |
| `docs/00-research/images/gui-reference/modeler-create-cae-card.png` and `modeler-cae-card-details.png` | Native card preview precedes or accompanies download; mapping evidence is Advanced, not the main task label. |

The product does not copy source branding, color, proprietary icons, commercial names, or inferred
internal workflows.

## Before and after

- Before: `docs/15-demo/images/ux-layout-review/rejected-materials-1440x900.png` and the legacy
  database/modeling routes required the user to infer where the solver card lived.
- Approved structure: `docs/15-demo/images/ux-layout-review/detail-1440x900.png` and
  `docs/15-demo/images/ux-layout-review/card-1440x900.png`.
- Live after: `docs/15-demo/images/ux-redesign-v2/material-detail-overview-1440x900.png` and
  `docs/15-demo/images/ux-redesign-v2/material-detail-evidence-1440x900.png`.

Live Docker/Chromium measurements at 1440×900:

| Region | Result |
| --- | ---: |
| Material shell | 1,377 px wide; 24 px left outer margin |
| Overview data column | 825.5 px |
| CAE delivery context | 455.5 px |
| Representative curve | 541 × 178 px |
| Page title | 20 px |
| Primary actions in header | one: `Download .rad` |

At 1366×768 the shell remains 1,304.5 px with 23.2/38.2 px outer margins; the main overview is
778.8 px, CAE context 429.7 px, and representative curve 504.8 px wide. No long identity or solver
label wraps character-by-character.

The first viewport contains Material identity, four properties, one curve, application conditions,
two solver formats, Preview and Download. UUID, aggregate ID, hash, classification and change reason
do not appear until `Evidence → Technical revision and provenance identifiers` is expanded.

## User task and click path

Scenario A is now:

```text
DP780 search → result selection → Open material → Preview OpenRadioss → Download .rad
```

This is five pointer activations after text entry/search submission. If preview is not required, the
header's direct Download reduces delivery to four. The CAE Cards tab also provides independent
Preview and direct Download actions for every available native format.

Scenario B's selected Record now exposes:

- direct typed Related Records with forward/reverse labels;
- the ordered Material → State → Test Data → Processing Output → Material Model IR → Neutral Material
  → native solver-card workflow;
- compact `r1` context by default and full exact revisions only in disclosure;
- the configured Layout selector and exact typed values under Evidence.

## Verification

- Unit coverage projects Layout order, preserves `7.85 g/cm^3` and `7850 kg/m^3 · mass density`,
  and keeps curve artifacts in Evidence.
- App integration downloads the preferred `.rad` through the native solver-card endpoint and verifies
  the browser download handoff.
- Live Docker/Chromium verified Preview, direct `.rad` download, Related/Workflow content, Layout
  availability, first-viewport content and the measured widths above.
- Full frontend test/build and user-guide checks are recorded on the PR.

## Remaining limits

- Search query/filter/selection URL persistence and returning from Detail to the same Tree scroll
  position remain for the final T-95 slice.
- Revision comparison still opens through the exact Catalog datasheet; it has not been duplicated in
  the simplified normal Material tabs.
- Production solver correctness remains subject to the repository's domain approval and mapping
  contracts; this UX work does not promote synthetic demo artifacts to production status.
