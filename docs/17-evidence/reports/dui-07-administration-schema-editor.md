# DUI-07 Administration schema editor evidence

## User outcome

An Administrator can choose a database object, keep a Table context while inspecting its related
definitions, and add only the definitions the current service can actually save. Normal Materials
and Modeling routes do not show Administration controls.

## Implemented workspace

`/administration/database` is a compact three-pane engineering editor:

```text
Objects (220–260 px) | selected object list (280–380 px) | structured properties
```

- **Tables** select the working Table.
- **Attributes**, **Layouts**, and **Subsets** are refreshed from that Table; changing Current table
  replaces only those lists and the details shown beside them.
- **Link Types** stay in their own list and show understandable direction wording, relationship
  cardinality, and the fact that source/target definitions are revision-bound when saved.
- The command bar exposes only `Add Table`, `Add Attribute`, `Add layout`, `Add subset`, and `Add
  Link Type`, because those are the existing live API mutations. Existing definitions state that
  they are read-only instead of presenting false Edit, Duplicate, or Delete controls.
- Attribute fields are conditional: number meaning/unit, discrete choices, and related Table appear
  only for the selected value type.

Stable identity and immutable revision behavior remains in the existing API: adding a definition
does not overwrite a record or a prior definition revision.

## Legacy cleanup

The retired `product-admin-embedded` presentation and its card/detail-grid, schema-row, badge and
form override rules were removed from the active Administration stylesheet. The surviving
`catalog-schema-workbench` selectors serve the compatibility schema route only. No active product
route references `product-admin-embedded`.

## Verification

- Focused React test verifies the navigator, Current table context and an exact-revision Link Type
  create request.
- A two-Table race regression test resolves the older Table request last and verifies that it cannot
  replace the newer Table's Attribute list. This prevents Layout creation from mixing Table and
  Attribute revisions. With no Tables, the UI shows an Add-Table recovery state instead of an empty
  Current table selector.
- Production TypeScript/Vite build passes.
- The capture script records `/administration/database` at 1366×768, 1440×900 and 1920×1080, checks
  the object navigator and table selector, and rejects page-level horizontal overflow.

The screenshot manifest and the user guides are updated in this same change. Capture measurements
and the exact command are recorded by the manifest provenance entry after the live demo capture.
