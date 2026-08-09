# Issue #161 — shared UI foundation evidence

## Disposition

Implementation and source-level automated verification are present on
`agent/issue-161-shared-ui-foundation`, based on `main@e907419`. The production web build, focused
Vitest suite, and shared-layout/capture contracts pass. This packet does **not** claim visual
acceptance or issue completion: the current Codex environment has no Docker/Compose runtime, so it
cannot rebuild the canonical API/PostgreSQL demo or replace the affected current product-route
screenshots. The PR must remain draft and must not merge until the live capture and Product Owner
review below are complete.

Actual Windows 4K 100%/150%/200% physical-readability approval remains the final #223 responsibility.
#161 still requires deterministic CSS viewport evidence at 1366×768, 1440×900, 1920×1080,
2560×1440, and 3840×2160; that evidence is not a substitute for #223.

## Baseline classification

| Area | Baseline | #161 disposition |
| --- | --- | --- |
| Application shell | already full viewport | preserve |
| Activity | shared-looking but Activity-named compact tokens; balanced 166rem comparison table | promote token names; preserve bounded comparison table |
| Materials search/detail/card preview | local scroll rails and resizable panes existed; primary shells were capped at 1920px | remove shell cap; preserve bounded navigator/context and real overflow |
| Modeling Data/Process/Fit | graph reflow and panes existed; route classes enforced 1920px width and 878px wide-height caps | move boundary to common elastic shell; retain stage selectors only for graph chrome |
| Modeling Export | three-pane task existed; outer task was capped at 1920px | make outer task elastic; retain readable setup/context panes |
| Administration | functional three-pane editor; structure split between `design/layout.css` and legacy `styles.css` | give structure one active owner; bound navigator/forms, not the shell |
| Tree/table/plot metrics | values were duplicated between CSS and TS components | centralize semantic CSS tokens and numeric TS metrics |
| Display profiles | no approved Compact/Standard/Large product setting | unchanged; #221 owns the decision |

## Primary user journey and preserved behavior

1. A user searches or browses Materials, opens an exact Material revision, and previews/downloads a
   solver card without page-level horizontal overflow.
2. The same user moves through Modeling Data → Process → Fit → Export. The navigator remains bounded,
   the central plot/native preview consumes remaining space, axes/units/legend stay inside their
   plot, and the selected exact revisions and saved results do not change.
3. A Reviewer uses Activity without losing its related five-column comparison geometry or local
   long-history scrollbar.
4. An Administrator opens Database design. The shell spans the viewport while navigation and the
   readable property form remain bounded.
5. Keyboard users can focus tables, splitters, column handles, trees, and local scroll rails; disabled,
   selected, warning, error, loading, empty, and long-value states retain visible semantics.

No API, persistence, revision, review, release, solver mapping, or authorization contract changes.
No fill rows, duplicated records, synthetic product content, CSS `zoom`, blanket `scale`, or
resolution-specific 2560/3840 route override is introduced.

## Implemented common boundary

- `apps/web/src/design/tokens.css` owns shared desktop typography, row/control, pane/cell, readable
  form, comparison table, workspace, navigator/context, splitter, scrollbar, and plot tokens.
- `apps/web/src/design/metrics.ts` owns numeric viewport, Materials/Modeling pane, tree, scroll rail,
  graph margin, and keyboard resize metrics used by TypeScript geometry.
- `apps/web/src/design/layout.css` owns the elastic Materials/Modeling/Administration structures and
  the single active Administration structural definition.
- `apps/web/src/design/primitives.css` supplies common table hover/focus/selection, disabled input,
  notice, empty, warning, success, and error states.
- `scripts/capture_current_product.py` rejects a shell narrower than 97% of the viewport and, from
  1920px upward, rejects visible primary workspaces narrower than 80% of the viewport. A legacy
  1920px island therefore fails at 2560 and 3840.
- Historical `modeling-*-workspace-bounded` selectors were replaced with neutral
  `modeling-workspace-stage-*` selectors. Stage selectors now own only stage-specific graph chrome;
  `.modeling-workspace-shell` owns the common boundary.

## Approved-reference inspection

The following approved #167 originals were opened at original resolution before the implementation
was classified. This is a reference-topology review only; it is **not** after-change visual evidence
or Product Owner acceptance.

- Materials: `materials-search-normal-1920x1080`,
  `materials-datasheet-overview-normal-1920x1080`, and
  `materials-card-preview-normal-1920x1080`
- Modeling: `modeling-data-normal-1920x1080`, `modeling-process-normal-1920x1080`,
  `modeling-fit-normal-1920x1080`, and `modeling-export-normal-1920x1080`
- Activity: `activity-reviewer-normal-1920x1080`
- Administration: `administration-database-normal-1920x1080`,
  `administration-table-edit-draft-1920x1080`,
  `administration-attribute-edit-draft-1920x1080`,
  `administration-layout-edit-draft-1920x1080`,
  `administration-subset-edit-draft-1920x1080`, and
  `administration-link-type-edit-draft-1920x1080`

The references consistently preserve bounded navigation and context panes, a flexible primary
table/plot/preview region, and readable-width forms. Administration overview and layout/subset/link
editors intentionally use multiple elastic panes, while simple table/attribute forms stay readable
inside the flexible work area. Those relationships are the boundary encoded by #161; their exact
future profile sizing remains owned by #221 and #184.

## Automated verification completed

| Gate | Result |
| --- | --- |
| `npm run build --workspace @cmp/web` | pass; TypeScript, Vite production build, and bundle budget |
| Focused Vitest: metrics, split panes, Modeling layout, column resize, engineering plot, common Processing Workbench | 59 passed |
| Remaining runnable Vitest files | 58 files / 294 tests passed |
| Focused Python contracts: shared UI foundation, Activity density migration, current capture and documentation-impact contracts | 76 passed |
| Full Python contracts | 260 passed; 7 unrelated failures reproduced unchanged on `main@e907419` |
| Fixed-cap/workaround source scan | no active 1920px/120rem/878px cap, 2560/3840 media override, CSS zoom, or blanket scale |
| Administration duplicate selector scan | structural selectors live in `design/layout.css`, zero legacy owners in `styles.css` |
| Current user-guide integrity | pass: 20 guides, 84 captures, 345 local links, 250 images |
| Latest Web Interface Guidelines source review | no new finding in the changed UI sources |

The 7 baseline contract failures are the pre-existing AGENTS byte limit/backlog wording assertions,
2 Windows path/discovery assertions running on POSIX, and 3 tests that still expect 77 captures and
the pre-#160 manifest scope although main contains 84. They are not changed or hidden by #161. Two
additional Vitest files use the literal network host `http://test`; this sandbox blocks the request
before Vitest can finish them. Both files remain part of the normal CI requirement.

Full repository tests and documentation/pre-publish gates must be recorded after the live evidence
update. The documentation-impact gate currently fails exactly because no current PNG changed. That
failure is expected until the canonical recapture is performed and must not be waived.

## Required live evidence before ready-for-review

1. Start the clean canonical Compose demo from this exact commit and run preflight/verification.
2. Capture affected normal and long/empty/error states at browser zoom 100% for all five CSS
   viewports. At minimum include Materials search/detail/card preview, Modeling Data/Process/Fit/Export,
   Activity, and Administration Database/Records.
3. Keep each original PNG and matching 100%-pixel crops for shell edge, navigator/main boundary,
   table/scrollbar, graph axes/legend, native preview, long tree label, and readable property form.
4. Open every selected approved reference and every new original/crop at original resolution. Record
   exact rectangles, dimensions, hashes, source commit, command, fixture, and environment.
5. Verify no page horizontal overflow, fixed-width island, filler, clipped control/value, scrollbar
   overlap, distorted SVG, axis/legend collision, or route-only high-resolution override.
6. Update `docs/user-guide/images/current/`, `docs/user-guide/screenshot-manifest.yaml`, affected guide
   prose, and this packet. Run the full product acceptance and independent read-only review.
7. Obtain Product Owner review of the complete before/after packet. Keep physical 4K readability
   explicitly deferred to #223.

## Current blocker

`docker`, `podman`, PostgreSQL, and a system Chromium executable are absent in this Codex environment.
The repository capture CLI can be inspected and its contracts tested, but the canonical live product
state cannot be started here. Existing current screenshots remain the immutable pre-#161 baseline and
have not been relabeled or edited to simulate after evidence.
