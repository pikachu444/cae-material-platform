# Issue #167 owner-authorized ADM-SCHEMA-CORE preview information-architecture packet

Date: 2026-07-31

## Authority and authorization

- Issue: [#167 — service reference freeze](https://github.com/pikachu444/cae-material-platform/issues/167)
- Product/UX authority: the active `/root` main agent under repository `AGENTS.md`.
- Product-owner authorization: after withholding the pending ADM-SCHEMA-CORE bundle, the product
  owner approved the direction in conversation on 2026-07-31 with `좋아 이 방향으로 수정해`.
- Canonical checklist:
  [visual-acceptance-matrix.md](../../01-product/visual-acceptance-matrix.md), Q-01–Q-20.
- Product contract:
  [desktop-engineering-ui-product-spec.md](../../01-product/desktop-engineering-ui-product-spec.md),
  §4.2.1 and §9.
- UI contract:
  [desktop-engineering-ui-spec.md](../../01-product/desktop-engineering-ui-spec.md), §7.

This authorization replaces only the rejected ADM-SCHEMA-CORE preview composition. It does not
approve any resulting image.

## Main-agent diagnosis

The existing source is functionally truthful but visually and behaviorally unacceptable:

1. At 1700–2399 px it auto-opens a companion preview solely from viewport width and stacks
   `Record values` and `Layout fields` in fixed 54 px rails. At 2400 px and above the rails become
   only 142 px.
2. At widths below 1700, `Preview datasheet` changes status text and sets
   `window.__previewRequested`, but does not expose any preview or return path.
3. The 1920 Attribute edit therefore shows two simultaneous miniature tables with little usable
   scanning height.
4. The 2560/3840 normal view gives the linked graph a separate full-width lower band that expands
   until it visually overwhelms the schema editor, while the saved Record/Layout evidence remains a
   thin strip.
5. The curve is a saved `Representative response` Artifact value in the selected Layout. It is
   valid in the saved Record preview, but it is not a reason to show a dominant graph beside an
   unrelated Density Attribute edit.

The product owner correctly identified that real configurations can contain many Attributes. A tiny
fixed viewport yields a tiny scrollbar thumb and makes both projections harder to understand, not
more informative.

## Preserved product, state and data contracts

The writer must preserve all of the following:

- the flat `Schema objects ⇆ Object list ⇆ property editor/preview` workspace;
- current Table scope and selection continuity;
- Table list `Name | Rev` and Attribute list `Name | Value type | Rev`;
- Add Table and Add Attribute right-pane draft states;
- conditional Attribute fields for number, discrete choice, record reference and text;
- immutable definition revisions, exact Attribute Definition revision pins, required change reason,
  saved-versus-local-draft truth, stale-conflict recovery and duplicate-submit protection;
- `PREVIEW_RECORD`, its saved values, `material-layout` and its ordered exact field revisions;
- the invalid long local Attribute name must never rename a saved Record value or Layout field;
- a curve is rendered only from the saved `representative-response` Artifact field and remains
  semantically linked to that saved Record value;
- no invented Database/Profile edit, publish, delete, duplicate or production capability;
- no production React/CSS, commit, push, PR or merge.

The relevant domain source of truth is
[canonical-domain-model.md](../../03-domain/canonical-domain-model.md): an Attribute Definition
Revision owns immutable type/quantity/unit/validation semantics, a Record Revision owns its typed
values, and a Layout Revision owns the visible Attribute order/grouping.

## Required composition

### One task, one active projection

- Use one preview surface with two accessible task choices: `Record preview` and
  `Layout definition`.
- `Record preview` is the default. Its header shows the saved Record, governing Layout name,
  immutable Layout revision and field count without duplicating prose.
- Its active grid shows saved values in Layout order with Attribute, Value and Condition. Unit stays
  with the value.
- `Layout definition` shows ordered Attribute identity, value type and exact Definition revision.
- Never render both grids as simultaneous miniature tables. Only the active table occupies the
  available preview height.
- The full Layout definition remains primarily owned by the dependent Layout editor; this core
  bundle provides the read-only on-demand projection needed to prove the contract.

### Responsive behavior

- 1366×768 and 1440×900 normal edit targets remain editor-first.
- Activating `Preview datasheet` below 1920 must expose a real full-height auxiliary pane or replace
  the right editor surface. Provide an obvious `Back to editor`/`Close preview` action, restore focus,
  and preserve the draft.
- At 1920×1080 and above, preview may be a bounded companion pane. Visibility is a user task state,
  not an automatic consequence of `window.innerWidth`.
- Navigator, Object list and property form stay bounded. Do not stretch prose or form controls at
  2560/3840.
- The active preview grid uses `min-height: 0` and truthful overflow. A distinct reserved track and
  proportional thumb appear only when rows overflow. Pointer, wheel, PageDown/Arrow, Home and End
  behavior must have measured consequences.
- Include enough stored fields in the deterministic fixture to demonstrate meaningful scanning and
  a usable scrollbar at 1366, 1440, 1920, 2560 and 3840 without fabricating new semantics.

### Conditional linked graph

- Put the linked curve inside `Record preview`, after or beside the active saved-value grid only when
  the active saved Layout contains the curve/table Artifact field.
- Keep it secondary and bounded at every viewport. It must not become a full-screen lower band or
  expand indefinitely at 2560/3840.
- Density or another scalar Attribute edit must not show an unrelated graph. The Record preview may
  still expose the curve row; opening/choosing that row may reveal the linked plot.
- Preserve compact engineering-axis typography, real aspect ratio, data-relative headroom and
  non-uniform-stretch prohibition.

### Copy and accessibility

- Use the canonical ongoing-operation strings `Loading catalog…` and `Saving new revision…`.
- Use semantic buttons, tabs/table markup, visible `:focus-visible`, labels and `aria-live`.
- The preview task choices expose selected state and keyboard navigation.
- The auxiliary compact preview traps no focus and returns focus to the invoking command.
- Avoid developer vocabulary, filler explanations, repeated headings, badges and nested cards.

## Exact writer ownership

The sole configured Luna Max implementer owns only:

- `docs/00-research/ux-service-reference/administration-schema-core.html`
- `docs/00-research/ux-service-reference/administration-schema-core.css`
- `docs/00-research/ux-service-reference/administration-schema-core.js`
- `docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py`
- `docs/00-research/ux-service-reference/administration-schema-core-wave05.staging.json`
- the ADM-SCHEMA-CORE-owned PNG/measurement/state evidence below
  `docs/17-evidence/images/issue-167-service-reference/`.

The writer must not edit shared product specs, the common service-reference inventory/manifest,
the common freeze report, screenshot archive, GitHub issue, production files or another family.
Unrelated worktree changes belong to other ongoing bundles and must remain untouched.

## Capture and gate requirements

Recapture all eleven lifecycle targets, all registered ADM-SCHEMA-CORE evidence-only states and the
2560×1440/3840×2160 support images. Preserve the finite 11-image lifecycle denominator; preview-open
and projection-switch behavior belongs in deterministic interaction/state evidence, not a new
approval target.

The capture/validator must additionally prove:

- compact preview opens visibly, has a visible return action and preserves draft/context;
- preview visibility is not decided only by viewport width;
- one active projection at a time and accessible `Record preview | Layout definition` switching;
- active grid overflow, proportional rail and pointer/wheel/keyboard consequences;
- exact saved projection remains unchanged by unsaved/invalid draft edits;
- curve visibility is conditional on saved curve field/task selection;
- graph frame has explicit maximum geometry at 1920/2560/3840 and never dominates the workspace;
- no page-level overflow, overlap, clipped action, fake scrollbar or partial row;
- no console/page error.

Required commands:

```powershell
python docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_schema_core_wave05.py docs/00-research/ux-service-reference/validate_administration_schema_core_wave05.py
node --check docs/00-research/ux-service-reference/administration-schema-core.js
git diff --check
```

The writer returns changed paths, exact command results and residual risks. It does not make an
acceptance decision.

## Main-agent and reviewer hard gates

After deterministic gates, the active main agent opens every changed lifecycle, state and wide PNG
at original resolution and completes Q-01–Q-20. At minimum, these failures block:

- the 1920 Attribute editor still contains simultaneous tiny Record/Layout grids;
- compact `Preview datasheet` still provides no visible preview/return;
- long preview content receives a token-height viewport or an unusably tiny thumb;
- a Density edit shows a dominant unrelated response graph;
- 2560/3840 graph or blank space overwhelms schema work;
- any saved preview changes from an unsaved draft;
- any internal/developer term, clipped identity, fake rail, partial row or inaccessible task choice.

Only after the main gate passes may a fresh configured Terra High read-only reviewer receive a
bounded reviewer packet. The reviewer opens every named original, independently records Q-01–Q-20
and checks the exact evidence. Product-owner approval remains absent until the resulting image set
is explicitly submitted and approved.
