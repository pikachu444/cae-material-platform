# Issue #261 M1E3 Modeling family CSS ownership evidence

Date: 2026-08-22

Frozen base: `7e198e58d400cfbb54a1da9006c1e084bdf3ec09`

Scope: behavior-preserving ownership relocation only; no React DOM, copy, API, URL, state,
route, contract, product-semantic, breakpoint, or token change.

## Result and frozen packet

The independent requirements audit approved the merged-base packet before production edits. Its
151 selector rows / 139 touched source groups have roster digest
`ad02e6533379a27e7219c62763abe2369a6a2b7e36d4b9ee2c10780171485854` and split into:

- engineering-curve/calibration: 55 rows / 52 groups;
- Export/delivery/elastoplastic: 70 rows / 63 groups;
- viscoelastic/elastomer: 26 rows / 24 groups;
- legacy source split: `design/layout.css` 8 rows / 8 groups and `styles.css` 143 rows /
  131 groups.

The move removes 130 complete legacy groups and shrinks nine mixed groups. The 13 non-M1E peers
`CSS-0873`, `CSS-0874`, `CSS-0875`, `CSS-0924`, `CSS-1104`, `CSS-1171`, `CSS-1174`, `CSS-1177`,
`CSS-1218`, `CSS-1701`, `CSS-1702`, `CSS-1748`, and `CSS-1753` remain in their original legacy
groups. `CSS-0876 .icon-button` is property-unioned into the existing
`modeling-viscoelastic-workbenches.css` owner rule, so the selector is not duplicated and all old
and moved declarations remain effective.

The source oracle proves exact row IDs, serial source order, at-contexts, declaration signatures,
importers, full removals, mixed shrinks, and retained peers. The regenerated residual inventory is
exactly 1,621 rows / 1,343 groups, M1E is 232 / 188, and `crossCssDuplicate` is six. The explicitly
excluded complement remains unchanged: 62 rows / 52 groups with actual Materials, `/exports`,
`/datasets/import`, or `/datasets/test-json` consumers, plus the 170 / 136 common core
workbench/stage residual. M1A, M1B, M4, HOLD, and M6 remain outside this unit.

## Truthful owner and bundle topology

The engineering-curve, calibration, and viscoelastic/elastomer grammars move into their existing
producer-owned modules. The coherent Export/delivery/elastoplastic grammar moves into
`modeling-export-delivery-workbenches.css`, imported once by the actual lazy Modeling stage shell
after `modeling-export-stage.css` and before `modeling-stage-normalization.css`.

The production and Storybook bundle oracle resolves built CSS rather than relying on source
imports. It proves every target tuple is emitted through the expected owner, at the expected
multiplicity and cascade position, with no missing or unexpected duplicate row. Production retains
the lazy Modeling owner chunk; Storybook retains the same effective stylesheet order. The
`.icon-button` declaration union is emitted once with `border`, `color`, `background`, `width`,
`height`, `border-radius`, `font-size`, and `line-height` intact.

## Primary journey and preserved state

Setup uses deterministic synthetic non-production demo data. The primary metal journey selects the
exact DP780 Material/State/Test Data, reads the saved Process result, opens Fit, compares the four
candidate laws and explicitly saves the `swift + voce 50/50` model. Export then reads that selected
model, shows the native solver preview, exact/converted/reviewed mapping consequences and fit curve,
requires the approximation acknowledgement, creates the solver card, and exposes the artifact and
receipt links.

The same journey is captured on `/modeling` and its compatibility alias `/datasets/processing`.
Blocked source and unacknowledged approximation states keep their recovery action visible. The
selected model survives route alias navigation and a browser reload. The pre-existing delivery
component does not rehydrate the just-created artifact from `exportArtifact` after a full browser
reload; the reload record therefore truthfully shows the preserved selected source and the existing
Fit-result recovery surface, not a fabricated delivered state. The frozen base behaves identically,
and state hydration is explicitly outside this CSS-only unit.

Polymer Process/Fit blocked recovery, elastomer multi-mode Fit, and elastomer Export prerequisite
states exercise the other moved family grammars without inventing a production family/model choice.
Five focused Storybook states cover the engineering curve, mapping statuses, blocked/ready stage
navigator, and mixed target preview.

## Visual and runtime evidence

The retained evidence directory is
[`images/issue-261-m1e3-modeling-family-ownership`](images/issue-261-m1e3-modeling-family-ownership).
Its [exact image index](images/issue-261-m1e3-modeling-family-ownership/image-index.md) links every
retained original and crop at its lifecycle path.
Its before and after `cascade-provenance.json` files register 43 Product records and five Storybook
records. Product records include full originals plus direct 100%-pixel header, navigator, controls,
and graph/native-preview crops. Captures use browser zoom 100%, DPR 1, and CSS viewports 1366×768,
1440×900, 1920×1080, 2560×1440, and 3840×2160 where required.

The separate
[`issue-261-m1e3-documentation-impact` proof](images/issue-261-m1e3-documentation-impact/manifest.json)
reuses the five unchanged registered Modeling Fit guide images byte-for-byte as the repository's
current-documentation CSS-migration contract. It records the frozen implementation base, current
CSS hashes, before/current/after equality, zoom 100%, DPR 1, and standard density without replacing
or relabeling any current guide capture.

The authoritative
[`before-after-comparison.json`](images/issue-261-m1e3-modeling-family-ownership/before-after-comparison.json)
reports 48/48 geometry/text-preserving records and 220/220 behavior-preserving image pairs. Of those,
187 are pixel-identical. The remaining 33 differ only in generated synthetic UUID, hash, or artifact
filename text; normalized DOM text, target bounds, computed values, and all surrounding pixels remain
within the identity-only gate. There are zero geometry/text failures and zero pixel failures.

Main opened every after-state original at source resolution and inspected representative 100%-pixel
crops for each family, both route aliases, Export readiness/delivery/reload, and 4K header/navigator/
controls/graph composition. No target has page horizontal overflow, clipped task controls, an
unreachable recovery action, a one-sided fixed-width work island, or an unrelated internal void.
Bounded navigators/forms retain their task width while plots and native previews consume useful
space. Automated 3840×2160 is deterministic geometry evidence only; physical Windows 4K readability
at 100%, 150%, and 200% remains the #223 gate.

The related-data subsection is absent from this exact seeded family surface in both frozen-base and
current capture. The capture marks only that heading N/A after the exact family, graph, task, and
route assertions pass; it does not substitute a different state or relax any moved-selector check.

## Mandatory #249 design synthesis

- Information hierarchy — PASS. Application navigation, task heading, four-stage navigator,
  bounded property rail, dominant engineering graph/native preview, and disclosed technical evidence
  retain the approved Carbon-level priority at every recorded viewport.
- Engineering task flow — PASS. Data → Process → Fit → explicit saved model → Export → explicit
  acknowledgement → solver-card creation remains sequential and visible. Preview, selected model,
  saved result, readiness, delivery, and recovery remain distinct.
- Responsive/wide-screen composition — PASS for deterministic geometry. The SAP-style allocation
  keeps forms bounded and lets engineering canvases grow at 1920/2560/3840 without page clipping,
  route-specific scaling, filler, or uniform prose stretching.

Q-01 and Q-04 through Q-16 pass on the applicable Modeling surfaces. Q-02, Q-03, and Q-17 through
Q-19 are outside this Modeling-only unit. Q-20 passes for deterministic full-viewport geometry. The
fresh Web Interface Guidelines audit found no new actionable issue in the changed CSS/import line:
the unit preserves existing focus, semantic-control, scroll, and responsive behavior and introduces
no transition, zoom, transform-scaling, animation, image, or interaction code.

## Deterministic gates

- exact M1E3 source oracle: 2/2 tests pass;
- inventory and migration regression: 20/20 tests pass;
- frontend guard: 0 violations / 15 preserved warnings; its unit suite passes 17/17;
- full web regression: 71 files / 412 tests pass;
- production build and official bundle budget pass (entry 260,342 / 300,000 bytes; largest affected
  lazy workbench 116,373 / 131,000 bytes);
- Storybook production build passes;
- production + Storybook generated bundle oracle passes;
- capture helper passes Ruff and Python byte-compilation;
- user-guide, documentation-impact, and diff-hygiene checks pass; pre-publish is recorded at
  publication.

## Independent review

The independent read-only reviewer returned **APPROVE with no actionable findings** after inspecting
the frozen-base diff, rerunning the 2/2 source roster test, 20/20 inventory regression, production
and Storybook built-CSS bundle oracle, and `git diff --check`, and reviewing the scoped Product and
Storybook originals at source resolution. Q-01 and Q-04 through Q-16 pass, Q-20 passes for
deterministic geometry, and the out-of-scope Materials/Administration items are N/A. The only
recorded non-actionable residual is the explicit #223 physical Windows 4K readability gate.

## Environment boundary

Repository Compose preflight correctly rejected the preserved canonical project when it belonged to
another worktree. No permanent data or named volume was deleted. All visual phases used isolated,
disposable repository Compose projects with real PostgreSQL/API/web services; each project was
removed with only its project-scoped containers, volumes, local images, and network. The temporary
detached frozen-base reconstruction supplied only the before source and was removed after evidence
acceptance.

Issue #261 stays open. Its post-move M1E residual is exactly 232 rows / 188 groups: the coherent
170 / 136 common core workbench/stage residual is the next ownership-audit candidate, while the
62 / 52 cross-route-consumed complement remains deferred to its actual Materials/import/export/test
JSON producers.
