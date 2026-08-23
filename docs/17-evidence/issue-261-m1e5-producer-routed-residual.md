# Issue #261 M1E5 producer-routed residual

## Status

The bounded source relocation is accepted by Main after final packet inspection. Main visual/runtime
acceptance is PASS; this report does not claim physical Windows 4K device readability or a separate
Product Owner/device review. The durable evidence record is [the M1E5 image manifest](images/issue-261-m1e5-producer-routed-residual/manifest.json), and its validator is
[`capture_issue_261_m1e5_visual_evidence.py`](../../scripts/capture_issue_261_m1e5_visual_evidence.py).

## Frozen packet

The historical source inventory is pinned to base `f51fa6da9856b48e9e3be1ac77e0c2a16b1f9f8a`, with
SHA-256 `3f172e1642ab2dedf054beaa88c765ea00ef6578ffdcc893258837431b598965`. The candidate residual
contains 60 rows in 51 groups. The approved move contains 58 rows in 49 groups with ordered tuple
digest `0f6aa0655f142ce6e86d795038ce30c6af3ba3cb42b094f01571995fd01831b5`; the retained two-row
hold has digest `e71f72f787214b01e40d6c6109e37fe54d4263899dc9eeff0aabd0a3e1fa7880`.

The deterministic source oracle proves that all approved identities are absent from the two legacy
CSS files, present exactly once in their truthful owner, and preserve declarations, important
flags, at-context, source order and complete/mixed group boundaries. The two hyperelastic chart
selectors remain in `styles.css` with the accepted processing cascade and are absent from owner CSS.

## Current durable checks

The post-move CSS inventory records 1,391 legacy selector rows and 1,184 rule groups. The frontend
guard baseline is synchronized to those counts and the M1E5 checkpoint is
`ACCEPTED_MAIN_VISUAL_AND_RUNTIME`. The source oracle, bundle oracle (source mode), inventory check
and final visual-evidence validator are executable without fabricating image records. Product and
Storybook bundle evidence was inspected in Main's final packet; physical Windows 4K readability
remains deferred to #223.

## Topology disposition

The manifest retains six captured target topologies: Modeling Data metal, Materials curves, governed
import, canonical Test JSON, exports, and the seeded elastomer Fit producer. The retained
`modeling-process-elastomer-hold` remains a negative normal topology captured at all five CSS
viewports. The six source-only no-screenshot states are the three metal Process/Fit/Export states,
`modeling-fit-polymer`, `modeling-export-polymer`, and `modeling-export-elastomer`; each is
`N/A_REDUNDANT_NO_LIVE_TARGETS` with empty viewport and crop requirements. The two direct-route
equivalence groups and their two aliases remain unchanged and do not add duplicate captures.

The governed-import route remains a captured topology for its seven LIVE contracts. CSS-0887 is
now `N_A_SOURCE_TEST`: the normal producer did not materialize its conditional preview
`.curve-heading` row, so the manifest keeps source/component/import/bundle proof without inventing a
visible locator or changing the route capture.

## Main acceptance record

Main inspected native originals and representative direct 100%-pixel crops at the required CSS
extremes and recorded seven captured topologies/states across five viewports each. Before and after
each contain 230 files (195 PNG and 35 computed JSON); their tree SHA-256 digests are
`aa04391a18abefa75333233f242ec10a5ef52710d057fdf2edf0eaac6991b795` and
`5034120f72edca441c1ac20d5b49a0238b65a1c2322153d4add99ad2b3d3dc5f`. Selector computed equality is
190/190, page geometry 35/35, crop geometry/display/overflow 160/160, and selector geometry
175/190; the only 15 differences are the seed-generated Materials revision-prefix glyph width for
CSS-0161/CSS-0162/CSS-0164, with x/y/height unchanged. PNG byte identity is 160/195 and no clipping,
overflow or topology regression was found. Exact-base targeted and disposable candidate runtime
checks passed, aliases passed at 1440×900, one isolated seed run was used, and disposable resources
were removed without touching permanent `cmp-local-demo` volumes. The frozen 38 LIVE / 20
`N_A_SOURCE_TEST` / 2 `RETAINED_HOLD` partition remains unchanged, including CSS-0158 focus-visible,
the `.digest-line` source/component/import/bundle-only records, and CSS-0887 N/A. Physical Windows
4K readability remains deferred to #223.
