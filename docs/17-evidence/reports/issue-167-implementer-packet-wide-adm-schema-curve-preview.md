# Issue #167 implementer packet — ADM-SCHEMA-CORE wide Layout/Record curve preview

Date: 2026-07-30
Owner: active `/root` main agent
Scope: product-owner-authorized new correction cycle after the wide Q-20 rejection

## 1. Rejected result and acceptance boundary

The previous deterministic implementation passed, but the fresh reviewer rejected Q-20. At
2560×1440 the workspace is 1,290 px high and at 3840×2160 it is 2,010 px high, while the normal
editor/preview content remains approximately 388 px high. Two four-row tables stretch horizontally
and leave a dominant avoidable blank region.

Replace that composition with a truthful, synchronized projection of the current `Materials master`
Layout and saved DP780 Record. Use a Layout-selected `curve` Attribute and its saved Record
Artifact value to add a linked material-response plot beneath compact Layout/value evidence. This
is the same current Layout/Record context, not filler, a dashboard, a fourth inspector or an
invented analysis result.

Do not change production React/CSS, the common manifest, inventory, policy, shared evidence report,
GitHub state, commits or pushes.

## 2. Authority and contracts

Read and follow:

- GitHub #167 and `AGENTS.md`;
- `docs/01-product/desktop-engineering-ui-product-spec.md`, especially 4.2.1 and 9;
- `docs/01-product/desktop-engineering-ui-spec.md`, especially 3.4 and 7;
- `docs/01-product/visual-acceptance-matrix.md`, especially Q-09, Q-17–Q-20;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 47–55;
- the previous implementer, correction and reviewer packets for wide ADM-SCHEMA-CORE;
- `contracts/catalog/configurable-catalog-resources.schema.json`: `AttributeDataType` includes
  `curve`; `LayoutItem` pins an exact Attribute Definition revision;
- `contracts/catalog/configurable-catalog-record-resources.schema.json`: a saved `curve` value is an
  exact Artifact reference;
- OpenAPI Table/Attribute/Layout revision contracts;
- `apps/web/src/configurable-catalog-admin.tsx` as the production capability boundary;
- Materials DP780 synthetic datasheet response as the plot-data comparison source.

Visual comparisons:

- rejected `administration-database-normal-wide-2560x1440.png` and
  `administration-database-normal-wide-3840x2160.png`;
- the 1920 normal/Table-draft/Attribute-draft candidates;
- Granta layout/record examples registered in the visual matrix;
- the accepted-internal MAT-DETAIL wide graph treatment for axis/geometry discipline only.

## 3. Exact user value and state contract

An Administrator selects a Table or Attribute and immediately sees how the current saved Layout
projects the current saved Record. The companion view must demonstrate that user-selected,
exact-revision Attribute Definitions—not a hard-coded universal field set—control the datasheet.
A selected `curve` Attribute links the saved curve Artifact to a read-only response graph.

Preserve:

- three-pane `Schema objects ⇆ Object list ⇆ Property editor / preview` topology;
- bounded navigator/list/form widths and compact identity-first columns;
- current Table selection, Add Table/Add Attribute, conditional typed fields, immutable-revision
  edit flow, dirty/save/error/conflict behavior and local scroll controls;
- saved Record preview remains unchanged by a local draft until a revision is saved;
- zero-Table and new unsaved Table states expose no stale Table/Layout/Record/curve projection;
- loading/error may retain the last valid synchronized projection;
- no Duplicate/Delete/Publish/reorder claim outside the current capability boundary.

## 4. Required wide composition

1. Expand the synthetic `Materials master` Attribute fixture to the declared 12 defined fields,
   using compact identity/type/revision rows. The active `Material datasheet` Layout explicitly pins
   and orders those fields, including one `curve` Attribute named `Representative response`.
2. The saved DP780 Record supplies matching typed values. Scalar values retain units/conditions;
   the curve value is represented as a saved linked Artifact and is not editable in this preview.
3. In the preview:
   - keep Record/Table/Layout identity compact;
   - show bounded `Record values` and `Layout fields` evidence without stretching rows or prose;
   - render `Representative response` as a read-only graph below those tables;
   - identify it as the saved Record’s curve value and Layout field, not a calculated preview.
4. The graph uses the synthetic DP780 engineering response already used by MAT-DETAIL. Axes are
   `Engineering strain` and `Engineering stress (MPa)`. Domain headroom remains data-span-relative
   and the curve stays clear of the frame.
5. Use one responsive coordinate system for plot box, SVG viewBox, axes, ticks, labels, path,
   legend/hit geometry. SVG is acceptable and preferred here; Canvas/WebGL is unnecessary unless
   the implementer proves SVG cannot satisfy density/interaction cost. CSS non-uniform scaling is
   forbidden.
6. At 1920, the full preview remains useful without squeezing the bounded property form. At
   2560/3840, the graph expands into the vertical result region so the preview reaches the useful
   lower workspace rather than stopping around 388 px. Text, table rows and form controls remain
   normal size.
7. The graph is absent in zero-Table/new-Table/no-Layout states. Attribute drafts outside the saved
   Layout do not fabricate a value; drafts inside the saved Layout may highlight the corresponding
   saved row but never mutate the saved value or graph.
8. Provide semantic table markup and an accessible graph name/description. Preserve keyboard
   preview toggle/focus and local scroll behavior.

## 5. Captures and preservation boundary

Recapture:

- `administration-database-normal-1920x1080.png`;
- `administration-table-edit-draft-1920x1080.png`;
- `administration-attribute-edit-draft-1920x1080.png`;
- every affected 1920 evidence-only state;
- `administration-database-normal-wide-2560x1440.png`;
- `administration-database-normal-wide-3840x2160.png`.

The eight registered 1366/1440 approval hashes must remain exact:

- database 1366 `9995b53dae3a9907fe95f33ad9eed0b4a96a19fe1d7e7d19f61f89249f313724`;
- database 1440 `1b2491632ca17a96bbcd32efeac6d8d4cc5555b5ee43eaaa016085538828a2bf`;
- Table draft 1366 `9de662dd7dfa2453a66c0b0da830193b4061c25796406b3d88803f8ec5fc8c69`;
- Table draft 1440 `2390d47c2b9828f9aa4ae2a0d47d1829b2b4567c2584f13aac5863d0561cb284`;
- Attribute draft 1366 `e6682346823355eb99da5eb72eb5c795a31b4847a025d5f554a572e607d7dfd0`;
- Attribute draft 1440 `3db6cd5a26221bf62d13bcedd07c7d3a309df3984ef81914a5828da47f9a1a62`;
- stale conflict 1440 `e64c034fb1ad3fd6428ca319d91bde6ec7c675b95b5332d7cb2db49a9552cd21`;
- long invalid 1440 `51157e7802a56e093d228a74770cd43b6ad85bc7cb4be2161eca1859087f3994`.

Preserve every unaffected 1366/1440 evidence-only image exactly where the new preview is hidden.

## 6. Deterministic evidence

Extend the existing family capture/validator, then run:

- all eleven approval targets and sixty state captures;
- two wide captures;
- exact frozen lower hashes;
- Table/Attribute selection and saved-preview synchronization;
- all 12 Layout field IDs/revisions, corresponding Record values and curve Artifact identity;
- no curve/record/layout leakage in zero-Table/new-Table states;
- draft changes do not mutate the saved Record or curve;
- graph axis names/units, path containment, data-relative headroom and rendered-box/viewBox parity;
- at 1920/2560/3840, graph/result region reaches the useful lower workspace and there is no dominant
  avoidable blank remainder; record the geometry in measurements;
- normal preview has no fake rail; genuine editor/preview overflow retains visible proportional
  local controls with pointer/wheel/keyboard consequences;
- splitters, conditional fields, duplicate-submit, selection continuity, stale-response
  suppression, conflict recovery, exact dimensions/hashes, zero page/body overflow and zero browser
  errors.

Run capture/validator `--help` first, then captures/validators, Ruff, Python compilation,
`node --check`, inventory validation and `git diff --check`.

## 7. Owned paths and forbidden writes

Owned:

- `docs/00-research/ux-service-reference/administration-schema-core.{html,css,js}`;
- its WAVE-05 capture, validator and staging JSON;
- affected Administration image and measurement outputs described above.

Do not edit:

- `apps/web/**`;
- Materials, Modeling or Activity sources/evidence;
- common manifest, inventory, product/UI policy or shared freeze report;
- GitHub, commits, pushes, PRs or branches.

Return changed paths, new hashes, preserved hashes, gate results and residual risks only.
