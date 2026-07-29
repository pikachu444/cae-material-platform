# Issue #167 implementer packet — WAVE-02 / MAT-CARD

Date: 2026-07-29  
Writer role: configured `implementer_luna_max`, exactly one writer for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Bounded outcome

Create the complete five-image `MAT-CARD` approval family:

1. `materials-card-preview-normal-1366x768`
2. `materials-card-preview-normal-1440x900`
3. `materials-card-preview-normal-1920x1080`
4. `materials-card-approximation-blocked-1440x900`
5. `materials-card-unsupported-blocked-1440x900`

This is static reference work only. Do not change production React/CSS, the common reference
manifest, the finite inventory, the common evidence report, user guides, current screenshots, git
state, commits, branches, remotes or GitHub.

`MAT-DETAIL` is the approved prerequisite. Preserve its frozen shell, Browse tree, exact selected
Record header and datasheet tab topology. This family defines what appears when the engineer enters
the active `CAE Cards` tab and opens one exact native card.

## Product task and main-agent visual judgment

A materials engineer has selected the synthetic DP780 Record and needs to:

- verify the exact native solver text before download;
- understand solver, version, unit system, revision/lifecycle and mapping disposition;
- download an exact supported card without an extra confirmation;
- review and explicitly acknowledge an approximation before download;
- understand a named unsupported mapping and take a safe recovery action without receiving a fake
  artifact.

The native ASCII preview is the dominant engineering evidence. The delivery/property sheet is a
restrained 300–320 px companion, not a dashboard card or permanent application-level inspector.
Mapping states are status semantics, so restrained status labels are valid; do not use decorative
badges. Full IDs, hashes, Mapping Profile JSON and checksums stay under `Advanced mapping evidence`.

Use synthetic non-production content only. For the normal reference use an exact/exportable
reference target such as the existing synthetic Abaqus `.inp` path, with only exact or transformed
mapping states. Do not make the normal reference require acknowledgement. Do not choose or imply a
production solver card, material model, tensile standard or mapping policy.

## Frozen authorities inspected by the main agent

- `AGENTS.md`
- `docs/01-product/service-reference-inventory.yaml` (`MAT-CARD`)
- `docs/01-product/desktop-engineering-ui-product-spec.md` sections 5.6 and 6
- `docs/01-product/desktop-engineering-ui-spec.md` (`M-13–18`, `E-01–08`)
- `docs/01-product/desktop-engineering-user-flows.md` Flow A and Flow C
- `docs/01-product/visual-acceptance-matrix.md` Material Detail and Modeling Export checks
- approved prerequisite sources:
  - `docs/00-research/ux-service-reference/materials-datasheet-overview-normal.html`
  - `docs/00-research/ux-service-reference/materials-datasheet.css`
  - `docs/00-research/ux-service-reference/reference.css`
- approved prerequisite images:
  - `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1366x768.png`
  - `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1440x900.png`
  - `docs/17-evidence/images/issue-167-service-reference/materials-datasheet-overview-normal-1920x1080.png`
- current live evidence:
  - `docs/user-guide/images/current/solver-card-preview-1366x768.png`
  - `docs/user-guide/images/current/solver-card-preview-1440x900.png`
  - `docs/user-guide/images/current/solver-card-preview-1920x1080.png`
- current contract sources:
  `apps/web/src/material-library.tsx`,
  `apps/web/src/solver-card-delivery-ui.tsx`,
  `apps/web/src/solver-card-delivery.ts`,
  `apps/web/src/modeling-target-preview.tsx`,
  `apps/web/src/modeling-target-delivery.tsx`,
  `apps/web/src/api.ts`, `apps/web/src/types.ts`, and current solver-card tests.

The approved MAT-DETAIL sources/images are the visual authority for the application shell,
navigator width, Record identity header, tabs, typography, dividers and status bar. Current live
card captures and React/API sources supply real behavior and data contracts, but are not permission
to keep their disconnected full-page card route or accidental styling.

## Family ownership

The writer may create or edit only:

- `docs/00-research/ux-service-reference/materials-card-preview-normal.html`
- `docs/00-research/ux-service-reference/materials-card-preview.css`
- `docs/00-research/ux-service-reference/materials-card-preview.js`
- `docs/00-research/ux-service-reference/capture_materials_card_wave02.py`
- `docs/00-research/ux-service-reference/validate_materials_card_wave02.py`
- MAT-CARD-only staging JSON/evidence under
  `docs/00-research/ux-service-reference/`
- the five target PNGs and target-specific measurement/evidence files under
  `docs/17-evidence/images/issue-167-service-reference/`

The writer may reference approved shared HTML/CSS/JS read-only. Do not edit:

- `reference.css`, `reference.js`, `materials-datasheet.css`, any approved prerequisite source,
  or any existing approved PNG;
- `docs/01-product/service-reference-manifest.yaml`;
- `docs/01-product/service-reference-inventory.yaml`;
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md`;
- any file under `apps/`;
- any `modeling-process*` file or other writer-owned file.

Other agents may work in the repository. Preserve their edits and never reset, clean, stash,
discard or overwrite unrelated files.

## Required target definitions

### Normal at all three viewports

- Reuse one semantic HTML structure plus bounded viewport overrides.
- Preserve the approved Materials shell, Browse navigator, `DP780 synthetic demo steel` Record
  header, exact `r1 · Draft` context, tabs and status bar. `CAE Cards` is active.
- The center workspace uses two regions:
  `dominant native text preview | 300–320 px delivery/property sheet`.
- Keep the approved navigator proportions/defaults from MAT-DETAIL at the named viewport. Its tree
  remains independently scrollable and the selected Record remains visible. No tree label or type
  is clipped without a deliberate ellipsis and full `title`.
- Native preview has a clear filename/target heading, readable monospaced 12–13 px text, line
  continuity, independent vertical/horizontal scrolling and no page-level horizontal overflow.
- The normal synthetic exact card is exportable and does not require acknowledgement. `Download
  .inp` is the sole filled primary command and is visible without scrolling.
- The delivery sheet shows human task fields first: solver/format, version, unit system, card
  revision, lifecycle and a compact mapping summary. `Material ID` is not a prominent normal-path
  field; if retained, place it in Advanced evidence.
- Show named exact/transformed mapping rows only as needed to understand the artifact. Full mapping
  report, card/revision IDs and checksums remain in a closed `Advanced mapping evidence`
  disclosure.
- The status bar reports exact Record/card context, no active job, warning count and online state.
- Buttons and tabs have keyboard/focus-visible behavior. Do not use nested cards, decorative
  gradients, repeated eyebrow labels or a second equal primary action.

### Approximation blocked 1440×900

- Preserve the complete normal shell, selected Record, active tab, preview text and two-region
  topology.
- Use one named synthetic approximation with a concise engineering consequence, for example the
  bounded post-necking extension supported by existing reference evidence.
- Place the warning and unchecked acknowledgement immediately beside the mapping decision.
- `Download .rad` is present but disabled until the checkbox is checked. The state is explicitly
  `Review required · download blocked`, not unsupported and not delivered.
- Checking the acknowledgement must enable download and update the local state/announcement; it
  must not imply review approval, release or a newly generated revision.
- Mapping Evidence remains available as a secondary disclosure. Do not hide the native preview or
  selected Record context.

### Unsupported blocked 1440×900

- Preserve the same shell, selected Record, active tab and two-region topology.
- Name the unsupported target field and why it cannot be represented. No acknowledgement may
  bypass an unsupported mapping.
- Do not render believable native file contents for a card that was never generated. The dominant
  preview region instead says `Native preview unavailable` and that preflight stopped before
  artifact creation, while retaining enough target context to diagnose the block.
- Do not show an enabled or fake download command. A disabled `Download blocked` status may occupy
  the command location so the consequence is unambiguous.
- Provide one safe secondary recovery action, `Open Modeling`, and keep `Back to CAE Cards`
  available. Do not silently select another model, target or revision.

## Evidence-only states

Exercise at 1366×768, 1440×900 and 1920×1080 without creating additional approval PNGs:

- long native text scroll: native text remains readable and independently scrollable; delivery
  controls stay visible; no document/body overflow;
- preview or mapping loading: preserve shell, Record header, tabs and region dimensions; disabled
  command explains that exact evidence is loading;
- preview or download error: preserve last valid preview, mapping context and acknowledgement;
  announce the error and provide a bounded retry without resetting the Record/card selection.

Canonical approximation/unsupported targets also need deterministic responsive evidence at all
three viewports proving no topology change. Only their 1440×900 PNGs are approval images.

## Static-region → production contract mapping

This reference freezes future structure; it does not implement the React port.

| Static region | Current React/component/data contract to preserve later |
| --- | --- |
| Application/status shell | `ApplicationShell` plus `publishWorkspaceStatus`; selection, revision, jobs, warnings, connection |
| Browse/Record shell | `MaterialDetailPage`, `MaterialsBrowseTree`, `ResizableSplitPane`; exact selected Record/revision and return context |
| CAE Cards tab | Material detail `tabs`, `CardTable`, `SolverAvailability`; exact selected card remains URL/session-restorable |
| Native preview | `SolverCardPreviewPage` plus `previewSolverCardText`; native text is task evidence and not synthesized client-side |
| Delivery fields | `SolverCardEvidence.target`, revision/lifecycle and card summary; target solver/version/unit tuple |
| Mapping disposition | `mappingDisposition`: unsupported → blocked, approximated/ignored → review, otherwise direct |
| Approximation acknowledgement | `acknowledged` is local and gates download only for `review`; it is not review/release state |
| Download | `downloadSolverCardArtifact`; exact artifact/filename and recent delivery activity |
| Mapping evidence | `downloadSolverMappingArtifact`; mapping report plus revision/checksum fields under disclosure |
| Error/loading recovery | current preview/evidence/download error paths; preserve material/card context and retry safely |

## Responsive and visual safety rails

- Page minimum remains the approved desktop 1180 px floor; targets are exactly 1366×768,
  1440×900 and 1920×1080 at device scale factor 1.
- Navigator remains visually identical to approved MAT-DETAIL at each viewport.
- After navigator and divider, the native preview receives the dominant remaining width; the
  delivery sheet must not exceed 320 px and must not cause page overflow.
- At 1366×768 keep every primary task label, selected Record identity, native filename, mapping
  disposition and primary action visible. Use region scrolling, not smaller-than-approved text.
- At 1920×1080 allow the native region to expand; do not widen the delivery sheet into dead space.
- Body/data text remains 14 px where practical; tree and metadata remain readable 12–13 px.

## Deterministic acceptance

Provide a target-aware capture and validator which fail unless:

- each PNG is exactly its named viewport, device scale factor 1, with deterministic font loading;
- there are no console errors, page errors, broken resources or document/body horizontal overflow;
- shell/navigator/header/tabs/status geometry matches the approved prerequisite within bounded
  safety rails;
- the normal structure has one native preview and one 300–320 px delivery sheet, with the native
  region dominant and no permanent third column/nested-card hard-gate failure;
- normal has an exportable exact/transformed-only mapping, no acknowledgement, one enabled filled
  Download command and closed Advanced evidence;
- approximation has one named approximation, adjacent unchecked acknowledgement and disabled
  download; checking it enables the command without changing revision/lifecycle language;
- unsupported names a blocker, contains no believable native artifact, has no bypass and offers
  Open Modeling/back recovery;
- long/loading/error evidence preserves selected Record/card context and pane geometry;
- keyboard tab order, focus-visible, tabs, disclosure, acknowledgement, back/recovery and download
  enablement have measurable semantic consequences;
- every long identity/text string is contained with full native title or scroll access;
- responsive evidence exists for normal, both exceptional states and all evidence-only states at
  1366/1440/1920.

Run at minimum:

```text
python docs/00-research/ux-service-reference/capture_materials_card_wave02.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_materials_card_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_materials_card_wave02.py docs/00-research/ux-service-reference/validate_materials_card_wave02.py
node --check docs/00-research/ux-service-reference/materials-card-preview.js
git diff --check
```

Because the main agent owns manifest integration, the family validator may validate a writer-owned
staging index/measurements before the common manifest entries exist. It must switch to the common
manifest after integration without weakening assertions.

## Handoff

Return:

- exact files changed;
- commands and pass/fail results;
- each approval PNG path, viewport and SHA-256;
- exact measurement/responsive/state-evidence paths;
- any residual limitation.

Do not modify shared integration files to make a gate pass. Do not commit or start another family.
