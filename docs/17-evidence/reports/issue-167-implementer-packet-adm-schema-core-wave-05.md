# Issue #167 implementer packet — WAVE-05 ADM-SCHEMA-CORE

Date: 2026-07-29  
Status: ready for one configured implementer  
Issue: https://github.com/pikachu444/cae-material-platform/issues/167

## 1. Bounded assignment

Create the complete static service-reference bundle for `ADM-SCHEMA-CORE` only:

- `ADM-DB` — Database design scope and schema object navigator;
- `ADM-TBL` — Table edit draft;
- `ADM-ATR` — typed Attribute edit draft;
- the Table stale-revision conflict exception;
- the long/invalid Attribute exception;
- deterministic responsive, interaction, overflow, empty, loading, saving and error evidence named
  below.

This is reference authoring only. Do not change production React/CSS, backend/API contracts, the
common service-reference inventory, the common manifest, or the common #167 evidence report.

The configured `implementer_luna_max` role is callable in this surface and is authoritative from
`.codex/agents/implementer-luna-max.toml`. Do not reinterpret model or agent configuration.

## 2. Authority inspected by the main agent

The active `/root` main agent directly inspected:

- `AGENTS.md`;
- GitHub issue #167;
- `.codex/config.toml` and `.codex/agents/*.toml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`;
- `docs/01-product/desktop-engineering-ui-spec.md`;
- `docs/01-product/visual-acceptance-matrix.md`;
- `docs/user-guide/12-configurable-catalog-and-modeling.md`;
- `apps/web/src/configurable-catalog-admin.tsx`;
- `apps/web/src/configurable-catalog-admin.test.tsx`;
- `apps/web/src/api.ts`;
- `apps/web/src/types.ts`;
- `contracts/catalog/configurable-catalog-resources.schema.json`;
- the Table/Attribute list, create and revise operations in
  `contracts/http/openapi.yaml`;
- current Administration captures at 1366×768, 1440×900 and 1920×1080;
- the historical UXC-00D Administration captures;
- `granta-admin-schema-tool.png`, `granta-admin-tables.png`,
  `granta-functional-edit.png` and `granta-admin-layout.png`.

Use the mandatory skills already selected for this visual task:
`desktop-engineering-ui`, `frontend-ui-engineering`, `web-design-guidelines`, and
`webapp-testing`.

## 3. Main-agent comparison and product judgment

Preserve from the current product:

- one selected Table scopes Attributes, Layouts and Subsets;
- object-family selection updates the adjacent list in place;
- existing definitions and local draft values are distinct;
- typed Attribute fields are conditional;
- immutable revisions replace overwrite semantics;
- current Table/Attribute list responses and exact revision metadata remain the data source;
- errors retain the last valid selection and draft.

Correct in the new reference:

- remove the redundant persistent `Workspace setup` side rail from the Database design task. It
  creates a fourth column and wastes the compact viewport;
- use exactly three persistent work panes:
  `Schema objects | Object list | Property editor`;
- keep a shallow Administration context/command row above the three panes;
- use the main pane for actual rows and editable properties, not introductory copy;
- prevent the 1920 layout from becoming mostly blank by giving the property sheet a useful,
  bounded reading width while the pane itself remains flexible;
- do not carry the historical UXC-00D `Edit / Duplicate / Delete / Save` command set into every
  state. Commands must follow the selected object and real state;
- borrow Granta's compact selection/list/property rhythm, not its branding, icons or proprietary
  geometry;
- use direct property rows and inline validation rather than nested cards, banners full of prose,
  pills or technical status labels.

The current service has no governed editable Database or Profile resource. The `ADM-DB` reference
therefore shows Database design as a workspace scope, not as a fabricated Database/Profile entity.
It may identify the current workspace/project context in ordinary language, but it must not invent
a database revision, lock, publish status or editable Profile.

The HTTP contract already defines Table and Attribute revise endpoints using exact `If-Match`.
The current React adapter does not expose those functions yet. These static edit references define
the later production target; they do not claim that current React already performs the revision.

## 4. Exact approval images

Create exactly these 11 approval candidates:

| Target ID | State | Viewport |
| --- | --- | --- |
| `administration-database-normal-1366x768` | normal | 1366×768 |
| `administration-database-normal-1440x900` | normal | 1440×900 |
| `administration-database-normal-1920x1080` | normal | 1920×1080 |
| `administration-table-edit-draft-1366x768` | draft | 1366×768 |
| `administration-table-edit-draft-1440x900` | draft | 1440×900 |
| `administration-table-edit-draft-1920x1080` | draft | 1920×1080 |
| `administration-attribute-edit-draft-1366x768` | draft | 1366×768 |
| `administration-attribute-edit-draft-1440x900` | draft | 1440×900 |
| `administration-attribute-edit-draft-1920x1080` | draft | 1920×1080 |
| `administration-edit-stale-conflict-1440x900` | stale-revision-conflict | 1440×900 |
| `administration-attribute-long-invalid-1440x900` | long-invalid | 1440×900 |

The two topology-changing exceptions also require deterministic responsive evidence at
1366×768 and 1920×1080. Do not register those responsive siblings as additional approval images.

## 5. Owned paths

The implementer owns only new ADM-SCHEMA-CORE paths:

- `docs/00-research/ux-service-reference/administration-schema-core.html`;
- `docs/00-research/ux-service-reference/administration-schema-core.css`;
- `docs/00-research/ux-service-reference/administration-schema-core.js`;
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`;
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`;
- new images, measurements and state evidence under
  `docs/17-evidence/images/issue-167-service-reference/` whose names begin with
  `administration-database-`, `administration-table-`, `administration-attribute-`, or
  `administration-edit-stale-`.

Do not edit shared CSS/JavaScript, `service-reference-inventory.yaml`,
`service-reference-manifest.yaml`, `issue-167-service-reference-freeze.md`, any other bundle's
source/capture/image, or any production file.

## 6. Shared topology and visual grammar

### 6.1 Vertical structure

Use:

1. the established compact CMP application bar;
2. one shallow Administration task/context row with `Database design`;
3. a compact command group aligned to the right;
4. the three-pane workspace for all remaining height;
5. the compact status row.

No marketing title, product subtitle, onboarding paragraph, workspace-setup navigation rail or
card dashboard is allowed.

### 6.2 Three-pane geometry

At the three normal viewports:

| Viewport | Schema objects | Object list | Property editor |
| --- | ---: | ---: | --- |
| 1366×768 | 220–232 px | 292–320 px | remaining dominant width |
| 1440×900 | 232–248 px | 312–344 px | remaining dominant width |
| 1920×1080 | 252–272 px | 344–384 px | remaining dominant width |

Use two visible 1 px dividers with at least a 5 px keyboard/pointer separator hit area.
ArrowLeft/ArrowRight adjust a pane by 8 px; Home/End reach documented min/max values. ARIA values and
rendered widths must remain synchronized. Resizing may not create document-level overflow.

The property editor is flexible. Its editable labels/controls use a readable internal maximum line
length, but the pane itself is not a centered page card.

### 6.3 Density and overflow

- normal object rows: 24–26 px;
- body/data: 13 px regular/medium;
- metadata: 11.5–12 px;
- pane headings: 13.5–14 px;
- one-line identities with `min-width: 0`, truncation and full-value access;
- tabular numerals for counts and revision numbers;
- sticky pane/list headings;
- every pane owns its vertical overflow;
- reserve a visibly distinct scrollbar track only when that local content genuinely overflows;
- local rails may not cover row text;
- long lists and property sheets must work by pointer, wheel and keyboard;
- normal short states and empty lists must not display fake scroll rails.

## 7. Screen contracts

### 7.1 `ADM-DB` — Database design normal

User task: choose the schema object family and current Table whose definitions will be inspected.

Visible structure:

- context title: `Database design`;
- short context value identifying the current workspace/project, not a fake governed Database;
- commands: `Refresh`, `Preview datasheet`, and one state-specific primary `Add Table`;
- left pane heading `Schema objects`;
- compact rows for `Tables`, `Attributes`, `Layouts`, `Subsets`, `Link Types`, each with a count;
- a `Current table` selector below the object rows when Tables exist;
- center pane heading `Tables` with a dense list of realistic synthetic Table identities;
- selected row remains highlighted with a restrained fill and leading accent;
- right pane heading is the selected Table name and shows a compact read-only definition:
  `Purpose`, `Attributes`, `Layouts`, `Subsets`;
- one concise next-step line and a secondary `Edit Table` action are allowed. Do not insert an
  explanatory paragraph under every row.

Data source mapping:

- Table list/count/selection → `listConfigurableCatalogTables`;
- dependent counts → the selected Table's Attribute/Layout/Subset list responses;
- `Current table` changes only scoped list/detail selection;
- `Refresh` retains the current selection when it still exists;
- `Preview datasheet` maps to the real configurable Record/datasheet route;
- exact IDs, hashes, classification and change reason stay in Advanced/Evidence.

Truth boundary:

- do not render Database/Profile records, revision IDs, a lock command or Publish;
- do not imply that `Add Table` edits an existing Table;
- no fake record counts when the current Table projection does not provide them.

### 7.2 `ADM-TBL` — Table edit draft

User task: edit one current Table definition and save a new immutable revision.

Keep the same three panes. Select `Tables` and the exact current Table row. The right pane becomes a
draft property sheet:

- `Table name` — editable;
- `Reference key` — visible read-only stable identity;
- `Description` — editable;
- `Change reason` — required for save;
- compact `Based on current revision` status in ordinary language; full revision ID stays Advanced;
- dirty state appears once in the editor heading/status, not as repeated badges;
- primary command: `Save new revision`;
- secondary command: `Discard draft`;
- changing local fields invalidates only the local preview/current edit result;
- saving appends a new Table revision; it never overwrites the previous revision or existing Records.

Do not show classification as editable because the Table revise request does not accept it.
Do not show Duplicate/Delete in this bundle.

Deterministic states:

- clean current definition;
- dirty valid draft;
- saving with duplicate submit blocked;
- save error preserving every field and change reason;
- successful response advances current head without deleting history.

### 7.3 `ADM-ATR` — typed Attribute edit draft

User task: edit a typed Attribute definition while understanding which fields determine Record
entry, unit semantics and validation.

Keep `Attributes` selected and scope the list to the current Table. Use a realistic synthetic number
Attribute such as `Density`.

Right-pane normal draft fields:

- `Attribute name`;
- `Reference key` as read-only stable identity;
- `Value type` as read-only for an existing definition;
- `Required when creating a record`;
- `Quantity` / engineering meaning;
- `Standard unit`;
- `Minimum` and `Maximum` only for a number Attribute;
- `Entry guidance`;
- required `Change reason`;
- `Save new revision` as the sole filled primary;
- `Discard draft` as secondary.

Conditional field evidence must prove:

- number → quantity, standard unit, min/max;
- discrete → allowed choices, without number-unit fields;
- record reference → related Table, without number-unit or allowed-choice fields;
- text → optional length/pattern only when supplied by the contract.

Do not show all type-specific fields simultaneously. Do not use UUIDs, JSON, hashes or internal
schema IDs in the normal editor.

### 7.4 stale-revision conflict exception

Represent a real `412 If-Match` conflict without discarding the local Table draft.

- keep all three panes and the edited values visible;
- place one compact conflict region at the top of the property editor;
- say that a newer Table definition exists and the local draft is preserved;
- offer exactly `Reload current`, `Keep local as new revision`, and `Cancel`;
- no success/release/publish claim;
- full ETag/revision identifiers remain in Advanced;
- keyboard focus starts on the recovery region and returns to the edited field or selected row after
  resolution.

### 7.5 long/invalid Attribute exception

Use deliberately long but plausible stored identity, entry guidance and allowed-choice content.
Demonstrate:

- the object list preserves the full identity through local horizontal access or a tooltip without
  making every row multiline;
- the property editor scrolls independently with a visible reserved proportional rail;
- field labels and controls remain aligned;
- inline validation is adjacent to each affected field;
- a concise editor summary names the number of invalid fields;
- `Save new revision` is disabled and its reason is visible;
- correcting a field clears only that field error and does not discard other draft values;
- no document/page overflow, text/scrollbar collision or giant banner.

## 8. Static-region to production mapping

| Static region | Later production component/state/contract |
| --- | --- |
| application and Administration context rows | `ApplicationShell`, Administration route context |
| task command row | `WorkspaceCommandBar`; state-specific Add/Edit/Save/Discard commands |
| three-pane workspace | `ResizableSplitPane` with two synchronized separators |
| Schema objects | `NavigatorTree`-style flat object family navigator; current `objectKind` state |
| Current table | selected Table stable identity; table-scoped list requests |
| object list | `EngineeringDataGrid`/dense list backed by current Table/Attribute APIs |
| read-only definition | immutable current revision response |
| Table draft sheet | `TableReviseRequest` plus exact current ETag/`If-Match` |
| Attribute draft sheet | `AttributeRequest` plus exact current ETag/`If-Match` |
| conditional typed fields | `AttributeDataType` and `AttributeContentInput` |
| dirty/saving/error state | local draft state; old immutable revision remains unchanged |
| stale conflict recovery | `412` response; preserve local fields and resolve explicitly |
| technical disclosure | IDs, hash, classification, schema ID/version and raw ETag only |

## 9. Accessibility and interaction evidence

The static reference must provide and validate:

- semantic buttons, links, labels, form controls and status/error regions;
- visible `:focus-visible` treatment;
- no clickable `div`/`span`;
- icon-only controls, if any, have accessible names;
- object family and object rows are keyboard reachable;
- Arrow/Home/End behavior for both splitters;
- Tab order follows context commands → navigator → list → editor → status;
- long local lists/property sheet respond to wheel, PageDown and keyboard focus;
- disabled Save exposes the invalid prerequisite in visible text;
- form errors are associated with controls and focus the first invalid field on submit;
- dirty draft warns before a simulated navigation away;
- no `outline: none` without replacement, `transition: all`, disabled zoom or paste blocking;
- no console or page errors.

## 10. Deterministic state evidence

Generate machine-readable 1366/1440/1920 evidence for:

- catalog empty: no Tables, with `Add Table` as the one next command;
- catalog loading: retain the shell and previous valid selection;
- catalog error: retain prior rows/selection and expose `Retry`;
- Table saving;
- Table save error with draft preserved;
- Attribute type-conditional fields;
- Attribute saving;
- Attribute save error with every field preserved;
- both exception states at all three viewports;
- splitter min/default/max widths;
- normal and long local-scroll ranges;
- selection continuity and stale-response suppression;
- page/document/body horizontal overflow of zero.

## 11. Forbidden shortcuts

- no production React/CSS changes;
- no common manifest, inventory or common evidence edits;
- no fourth persistent workspace navigation column;
- no cards, KPI tiles, gradients, decorative badges or repeated eyebrow labels;
- no fabricated Database/Profile resource, database lock, publication or success state;
- no fake Edit/Duplicate/Delete command set disconnected from the selected state;
- no mutable overwrite wording;
- no technical IDs, hashes, JSON, ETag or schema IDs on the normal surface;
- no all-types-at-once Attribute form;
- no fake scrollbars in normal short content;
- no native scrollbar that disappears from the captured pixels when overflow evidence is required;
- no fixed SVG/raster stretching;
- no arbitrary per-viewport screenshot-only overlay;
- no commits, pushes, PRs or GitHub writes.

## 12. Required implementation gates

Run in this order:

```text
uv run --with playwright python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --help
uv run --with playwright python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --help
uv run --with playwright python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
uv run --with playwright python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
uv run python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
uv run ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check -- <all owned ADM-SCHEMA-CORE source/evidence paths>
```

The validator must verify exact image dimensions and SHA-256, region geometry, row/font density,
splitter behavior, form semantics, one-primary-action state, conditional fields, local scrolling,
draft preservation, error recovery, zero page overflow, zero console/page errors, no legacy
active-route selectors and the applicable qualitative checklist requirements.

## 13. Handoff

Return:

- every changed/created path;
- all 11 approval target hashes and viewports;
- responsive exception and deterministic state evidence counts;
- exact gate results;
- any residual risk.

Do not request product-owner approval. The `/root` main agent will integrate the common manifest and
evidence serially, run the deterministic gate again, open every image at original resolution,
prepare the reviewer packet, invoke one fresh read-only reviewer, repeat the qualitative gate and
then submit the images to the product owner.
