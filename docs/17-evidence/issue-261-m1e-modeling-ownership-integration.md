# Issue #261 M1E Modeling ownership integration evidence

Date: 2026-08-22
Base: `60cca28cc24bd7b734925b732b0b090a6534387f`
Scope: behavior-preserving ownership relocation plus one bounded compact stage-navigator correction; no DOM, copy, API, URL, or state change.

## Integrated result

- Lane A replayed first from the frozen base: validation 37 selector rows / 26 complete groups and engineering curve plot 62 / 59 (styles 37 / 36 before layout 25 / 23).
- Lane B replayed second onto the Lane A result: calibration/validation 84 / 78 and viscoelastic/Prony 50 / 46.
- Lane C then replayed the modeling core shell: 101 selector rows / 95 complete groups from styles and layout, in original source order, with its production and Storybook side-effect import owners. The independent-review correction that gives the production stage shell two interactive rows at 900 px and below is explicit fixture metadata embedded in the existing responsive owner row, so the relocation counts remain 101 / 95.
- The frozen oracle contains exactly 334 original selector rows / 304 complete groups. It records source path, source rule/selector order, selector, at-context, declaration signature, mixed groups, exclusions, imports, and guard relocations without depending on regenerated residual row IDs or the residual inventory hash.
- The regenerated canonical residual inventory is exactly 1,772 selector rows / 1,473 groups: M1E 383, M4 314, HOLD 504, M6 533, M1B 29, and M1A 9.
- CSS-1120, CSS-1153, CSS-1161, CSS-2014, CSS-2017, mixed groups 363/1045, and responsive peers CSS-1349/1350/1352/2030/2032 remain in legacy ownership.
- Frontend guard baseline source SHA is the frozen base. Only stale exceptions created by these moves were removed, and only exact relocation exceptions for pre-existing raw colors/font weights were added. The real guard reports 0 violations and 15 unchanged warnings.
- The regenerated inventory records the same seven pre-existing cross-file ownership duplicates. The compact correction stays in the unique owner-local `.modeling-stage-shell` row and uses two bounded important declarations to outrank CSS-0148, CSS-0612, and CSS-0614 without copying their M4 shared-shell selector. Remove the importance when M4 retires that legacy sizing.

## Isolated live acceptance

GNU Make is unavailable, so the repository preflight implementation, `uv run python scripts/check_compose_environment.py`, was run directly. It rejected the canonical `cmp-local-demo` because that environment belongs to another worktree. The canonical project was not stopped, recreated, seeded, or deleted.

M1E2 used only the isolated `cmp-demo-test-m1e2shell` project. It built the current sources, seeded the full demo twice, proved the 304-table snapshot repeat-stable, and passed `scripts/verify_full_demo.py`. Product phases used `http://127.0.0.1:32783` sequentially; Storybook phases used `:32784` sequentially. The temporary reconstruction was base `60cca28cc24bd7b734925b732b0b090a6534387f` plus only the four already accepted M1E owner styles/imports. Its legacy source contained 1,873 rows / 1,568 groups, exactly 101 rows / 95 groups more than the candidate residual.

The earlier cumulative M1E evidence remains the authority for the exact Data → Process → explicit saved Process result → Fit → explicit saved model → Export/read-back journey and four compatibility aliases. M1E2 did not repeat that domain run. Its bounded live probe targeted only the core shell topology: both `/modeling?stage=data` and `/datasets/processing?stage=data`, the five mandatory viewports, six responsive boundary pairs, hover, pressed selection, Advanced disclosure, reload/resume, and the live Fit Candidate parameters dock.

The capture fixture cannot truthfully synthesize four server-dependent or deliberately hidden states. Their live-matrix disposition is explicit rather than supplemented with newly invented feature behavior:

- stale Recipe conflict: N/A because no pre-existing exact fixture safely produces the server conflict; the newly invented M1E2 behavior test was removed;
- stale Material/State family context: no substitution of a current head for a stale URL revision;
- hidden top-level Saved outputs support drawer: test-only/N/A for live capture; the existing exact DOM/disclosure characterization remains authoritative while the core layout intentionally hides that companion;
- uncalculated Process plot: test-only/N/A for live capture because the canonical seeded route resumes its saved preview; the existing exact draft/history/current and deferred-reconciliation regression tests remain authoritative.

The JSON names exact pre-existing component tests where they exist and records the stale Recipe state as N/A without a test. Neither phase contains an invalid state record or browser/console error.

After capture, the isolated project was removed with its project-scoped containers, volumes, local images, and network; independent queries returned zero remaining containers and zero volumes. The frozen-base temporary directory was also removed. The canonical project still has its two original named volumes and the same eight before/after counts: catalog records 20, catalog record revisions 59, domain record bindings 83, Materials 3, Material revisions 3, Test Data document revisions 20, solver-card revisions 7, and material-model revisions 205.

## Screenshots and geometry

- M1E2 retains 268 PNGs: 119 Product pairs and 15 Storybook pairs, with before and after present for every image.
- Product records: 31 before / 31 after. Storybook records: 15 before / 15 after.
- Required viewports: 1366×768, 1440×900, 1920×1080, 2560×1440, and 3840×2160. Boundary probes: 860/861×768, 900/901×768, and 1180/1181×900.
- Runtime: browser zoom 100%, DPR 1, and `visualViewport.scale` 1.
- Pixel result: Product has 98/119 pixel-identical pairs, 18 intentional compact-navigator correction pairs, three bounded native `select` glyph raster variances, and zero unexpected changes. Storybook is 15/15 pixel-identical. The six corrected Product records are exactly the two routes at 860, 861, and 900 px: the shell grows from 34 to 68 px, all Data/Process/Fit/Export controls are visible, contained, enabled, and reachable, and the persistent graph yields 34 px without losing content. Every unaffected Product record has exact computed bounds; normalized relocation declarations have zero drift in Product and Storybook.
- A focused browser probe loaded the current minified shared and lazy owner CSS in production order. At 860, 861, and 900 px it computed `min-height: 68px`, `flex-basis: 68px`, and two 34 px grid rows with all four buttons within the shell; at 901 px it computed the original 34 px single row. This proves the owner-local important declarations preserve the accepted effective cascade without a recapture or demo-data mutation.
- The three non-semantic raster variances are confined to the native Test type/Condition select glyph: 72 pixels in each 901×768 route at `[155,268,170,278]`, and 81 pixels in the alias 1920×1080 state at `[164,271,180,278]`. The affected controls retain exact bounds, computed values, text, and normalized declarations. Required five-viewport geometry passes 50/50 image surfaces; 49/50 are pixel-identical and the remaining pair is that bounded 81-pixel native-control variance.
- Main opened all 268 PNGs at original resolution. After correction, Main reopened all 18 intentional correction images and all six before/after native-control-variance originals; after the owner-local consolidation, Main again opened the eight 860/861/900/901 Product route originals at original resolution. The required five-view composition retains the bounded curve/process rail, reachable task controls and disclosures, dominant persistent graph, and useful wide-screen growth without a one-sided work island or clipping.
- The corrected 900 px production boundary now uses the same visible two-row task topology already demonstrated by the isolated Storybook surface; 901 px remains the one-row boundary. The 860/861 samples prove the compact rule on both sides of the neighboring rail transition. The 1180/1181 layout transition remains pixel-identical.

The comparison authority is `docs/17-evidence/images/issue-261-m1e2-modeling-core-shell/before-after-comparison.json`. The generated CSS oracle also passed for `apps/web/dist` and `apps/web/storybook-static`: the production owner chunk is emitted through the existing lazy Modeling workspace path, and all 101 owner rows / 95 source groups have the expected selector/context multiplicities with no missing or unexpected duplicate moved selector.

## #249 design synthesis

- Information hierarchy — PASS. The application bar, task heading, stage navigator, bounded rail/form, dominant engineering canvas, and disclosure-only technical evidence preserve the approved Carbon-level hierarchy at every viewport.
- Engineering task flow — PASS. Data selection, Process calculation/save, Fit preview/explicit save, Export exact-source preview, and blocked recovery surfaces remain sequential, visible, reachable, and distinct, including all four stage controls at the compact production boundary. No recommendation, preview, saved result, or artifact state is conflated.
- Responsive/wide-screen composition — PASS for deterministic geometry. Rails and forms retain readable bounds while tables, plots, and the native preview consume useful width. There is no one-sided 1920-pixel island, clipping, horizontal page overflow, route-specific scale workaround, or uniformly stretched prose.

## Q-01 through Q-20

- Q-01 PASS — navigator scrollbar affordance remains visible and discoverable where the rail can scroll.
- Q-02 N/A — Materials result-list density is outside this Modeling-only unit.
- Q-03 N/A — Materials navigation is outside this Modeling-only unit.
- Q-04 PASS — Fit ribbon and graph remain visually linked with the persistent engineering canvas.
- Q-05 PASS — plot axes preserve readable labels and engineering units.
- Q-06 PASS — legend, selected state, preview state, and saved state remain distinct.
- Q-07 PASS — plot glyphs and line strokes retain their semantic distinction.
- Q-08 PASS — yield-start marker remains reachable and visually legible.
- Q-09 PASS — overflow remains discoverable through the bounded rail and local scroll surfaces.
- Q-10 PASS — Fit legend content does not collide with the graph or controls.
- Q-11 PASS — Fit rail composition remains consistent with the shared Materials/Modeling shell.
- Q-12 PASS — Export keeps the exact selected model and unit identity visible.
- Q-13 PASS — Export rows preserve the approved grammar and concise copy.
- Q-14 PASS — readiness uses one expression rather than competing status treatments.
- Q-15 PASS — plot headroom and axes remain balanced at the required deterministic viewports.
- Q-16 PASS — native preview retains local scrolling without destabilizing the surrounding shell.
- Q-17 N/A — Administration surface is outside this Modeling-only unit.
- Q-18 N/A — Administration surface is outside this Modeling-only unit.
- Q-19 N/A — Administration surface is outside this Modeling-only unit.
- Q-20 PASS for deterministic geometry — wide composition uses the full viewport without a fixed work island, clipping, or route-specific scaling.

## Deterministic gates

- Combined inventory/oracle/frontend-guard tests: 45/45 passed.
- Affected core-shell component tests: 45/45 passed after removing the newly invented stale Recipe behavior test from this CSS-only unit.
- Full web regression: 71 files, 412/412 existing tests passed; its frontend-guard unit suite also passed 17/17.
- M1E2 generated CSS bundle oracle: production and Storybook passed at 101 rows / 95 groups.
- TypeScript, production build, and official bundle budget: passed. Entry 260,342 / 300,000 bytes; largest affected lazy workbench 116,373 / 131,000 bytes.
- Storybook production build: passed.
- Canonical residual inventory: 1,772 selector rows / 1,473 groups with the required batch totals.
- Real frontend guard: passed, 0 violations / 15 baseline warnings.

## Independent review

The first independent read-only review found one blocker: production reserved only one 34 px flex row while the 900 px navigator rendered a second row, clipping Export. The compact correction and recaptured evidence resolve that finding. A later ownership audit moved its two declarations into the existing responsive owner row, restored the duplicate baseline to seven, and retained the same computed geometry. The same reviewer independently reran the 28-test inventory/replay suite and generated bundle oracle, reopened all 31 Product and 15 Storybook after-state originals plus the 900 px crops, classified the three native-select glyph deltas nonblocking, and returned `APPROVE/PASS` with no actionable findings. Q-01 and Q-04 through Q-16 pass; Q-02, Q-03, and Q-17 through Q-19 are N/A; Q-20 passes for deterministic geometry. All three mandatory #249 axes pass.

## Boundary

These deterministic CSS viewports prove geometry only. They are not an actual-device Windows 4K readability record. Windows 4K at 100%, 150%, and 200% remains explicitly deferred to Issue #223.

The latest owner instruction authorizes the bounded corrective commit, push, PR ready transition, required checks, and merge. Issue #261 remains open after this unit for the 383 residual M1E rows and later migration batches.
