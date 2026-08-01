# Issue #167 Administration — owner-authorized terminology, typography and readability correction

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>
PR: <https://github.com/pikachu444/cae-material-platform/pull/170>

## Explicit owner authorization and bounds

On 2026-08-01 the product owner explicitly rejected the remaining Administration candidate after
the main-agent original-resolution audit exposed user-language, typography and visible truncation
failures that the previous deterministic and reviewer gates missed. The owner explicitly authorized
this additional bounded correction and directed the configured Luna Max implementer to perform it.
This packet records that one-task exception to the repository's normal correction limit; it does not
change the default policy and does not authorize any further correction, production React/CSS work,
commit, push, PR action, approval-state change or #157 work.

Use exactly one already configured `implementer_luna_max` writer. Preserve all unrelated dirty work.
Do not reset, clean, stash, discard, revert or rewrite history.

The writer owns only:

- `docs/00-research/ux-service-reference/administration-remaining.css`
- `docs/00-research/ux-service-reference/administration-remaining.js`
- `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
- `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- all recaptured WAVE-06 Administration PNG and measurement JSON files under
  `docs/17-evidence/images/issue-167-service-reference/`

Do not edit `AGENTS.md`, product/UI specifications, either common manifest, common evidence report,
review packets/results, the product-owner packet, production code or any unrelated file. The main
agent owns serial integration after implementation.

## Authority and preserved contracts

Read before editing:

- root `AGENTS.md`
- `.agents/skills/desktop-engineering-ui/SKILL.md`
- `.agents/skills/frontend-ui-engineering/SKILL.md`
- `.agents/skills/web-design-guidelines/SKILL.md`
- `.agents/skills/webapp-testing/SKILL.md`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-administration-remaining-product-owner-packet.md`
- `docs/17-evidence/reports/issue-167-second-correction-packet-adm-relations-access-luna.md`
- the current source, measurement JSON and all 72 WAVE-06 images

Preserve the three-pane Administration topology, complete Layout/Subset/Link Type selection and
roving-keyboard behavior, exact revision/link semantics, independent cardinalities, Access role and
scope behavior, Publish's truthful not-configured boundary, local scrolling, state recovery, one
filled primary action maximum and bounded left/top wide composition. Do not invent data, policy,
capability, identifiers, filler or a new component grammar.

## Failure A — replace implementation language with Administrator language

The normal surface currently contains implementation or architecture phrases that a user should not
need to decode. Replace the visible copy everywhere it can render, including normal, error, loading,
empty, denied, confirmation and blocked states.

Forbidden rendered phrases, case-insensitive:

- `identity-provider` / `identity provider`
- `feature grant` / `feature grants`
- `server-scoped query`
- `task-based product roles` and `task-based access`
- `pinned`, `latest alias` and `exact revision policy`
- `catalog publish boundary`, `draft definitions preserved` and implementation/capability/endpoint/
  row-policy prose

Required consequence-first replacements:

- Access subject: `Team · material-reviewers`; Add form placeholder: `User or team name`.
- Access page context: `Atlas workspace · product access`; preview subtitle: `What this Reviewer can do`.
- Subset preview subtitle: plain filtered-result language such as `Records matching the current filters`.
- Link helper: `Saving keeps the selected Table versions.`
- Link information note: `Saved links keep the selected source and target Record versions. Newer
  versions do not change these links.`
- Link preview subtitle: explain the visible branch in plain language rather than database or
  implementation prose.
- Publish normal copy: use `Publishing not configured`, `Saved drafts`, `Validate drafts`, what is
  available now and the next Administrator action. Remove boundary/evidence wording from footer and
  status copy.

The governed terms `Table`, `Attribute`, `Layout`, `Subset`, `Link Type`, `Record`, `Revision`,
`Cardinality`, `User`, `Reviewer`, `Administrator`, `Classification` and `Catalog publishing` remain
valid when they name the object or decision the Administrator is actually managing.

Add a deterministic rendered-text assertion covering every family and registered state. Merely
changing the normal screenshot while leaving forbidden copy in another state is failure.

## Failure B — enforce one coherent typography system

`administration-remaining.css` currently uses many 10.4–10.9 px values and ordinary 650-weight text.
Replace the scattered small sizes with a scoped token system and apply it consistently:

- data, form controls, values and ordinary list/table content: `13px`;
- metadata, help, revision, status, column labels and secondary context: `11.5px` or `12px`;
- ordinary rows, buttons and explanatory text: weight no greater than `600`;
- 650 may remain only for true section/page headings already belonging to the shared shell.

Scope changes to WAVE-06 Administration references. Do not edit the shared
`administration-schema-core.css` because it is authority for already approved families; use narrowly
scoped overrides in `administration-remaining.css` for inherited status/footer/help text that falls
below the new floor. Do not increase padding indiscriminately or turn the compact workspace into a
spacious form.

Add computed-style assertions at 1366, 1440, 1920, 2560 and 3840 proving representative visible data
is at least 13 px, representative visible metadata/help/status is at least 11.5 px, and ordinary
rows/buttons/explanatory copy do not exceed weight 600. Hidden nodes do not count as evidence.

## Failure C — remove avoidable visible truncation

The current 1366/1440 examples clip ordinary sample identities and values even though the adjacent
editor still has sufficient width. Correct the layout without adding a second line to compact object
list rows and without sacrificing editor dominance.

- Keep the Administration object-list width within the existing product range of 280–420 px, but
  make it wide enough at 1366/1440/1920 for the ordinary Layout, Subset and Link Type fixture names.
- Keep genuinely long list identities single-line with ellipsis plus the existing full accessible
  name/title and full selected editor heading.
- Allow solver-card names in Subset result preview and source/target identities in Related Records
  preview to wrap within their own row or expose another immediate full-value presentation. Do not
  hide ordinary fixture values behind ellipsis.
- Wrapped rows grow naturally and remain separated by their row boundary. They must not collide with
  adjacent values, revision columns, scroll rails or pane dividers.
- Preserve local scrolling when the taller rows genuinely overflow. Do not add decorative rails.

Add deterministic assertions for the ordinary fixture names/values at 1366 and 1440: the rendered
text must be fully visible or intentionally wrapped, and no text, row, action or column may overlap
another element or a splitter/scroll rail.

## Failure D — high-resolution evidence must prove readability, not only containment

Keep the agreed wide-screen behavior: related task components remain a bounded left/top working
cluster; no table, form or preview stretches merely to fill 2560/3840; unused space remains only at
the far right and bottom. Do not use CSS `transform`, `zoom`, non-uniform scaling or a changed device
scale factor to make the evidence look larger.

At both 2560×1440 and 3840×2160, the same typography-token assertions from Failure B must pass and
the useful cluster must be at least as readable as the 1920 version: no smaller computed text, no
new truncation, no internal void, no child clipping and no overlap. Wide capture remains
`device_scale_factor=1` so the evidence is an honest worst-case CSS-pixel layout. The 3840 image may
retain trailing whitespace; inventing filler or automatically magnifying the entire application is
forbidden.

## Capture and deterministic gates

Because shared WAVE-06 CSS and copy change, recapture the complete registered set:

- 17 approval targets;
- 45 evidence-only state captures;
- 10 wide support captures;
- total: 72 captures.

Run and report:

```powershell
node --check docs/00-research/ux-service-reference/administration-remaining.js
.venv\Scripts\ruff.exe check docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

All existing interaction, containment, truth and inventory checks must continue to pass. Add the new
rendered-language, typography, visible-value, overlap and high-resolution assertions; do not weaken or
delete an existing check to obtain a pass. Return changed paths, exact command results, residual risks
and the 17 approval image paths with SHA-256. Do not update common manifests/reports or request
product-owner approval; the main agent performs integration and original-image review.
