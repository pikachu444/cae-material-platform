# P2-C5 independent review

**Disposition: approve for checkpoint.** Reviewed source SHA-256 `b6ed7659efb00298c85adbfeb9989529fadc07479491390cec4cefeb97c5c847`.

The prior 1366 visibility failure is corrected. [workspaces.html:160](../workspaces.html#L160)-[172](../workspaces.html#L172) appends the preview, scrolls its header only when it is outside the viewport, and preserves the pre-preview list position for detail return. [workspaces.html:189](../workspaces.html#L189)-[216](../workspaces.html#L216) preserves the physical second-click identity after that scroll and keeps collapse/reopen, visible-detail, Enter, and double-click paths.

Opened original-resolution evidence for every A-F preview at 1366×768, 1024×900, and 360×900, plus the current 1920×1080 previews. All 18 narrow captures visibly contain “미리보기”, selected identity, and detailed-open/collapse controls; no header is off-viewport. The 1920 views retain useful list/preview composition and readable plots.

`checks.json` records 230 passing checks and zero runtime errors. It verifies preview-header visibility and physical 120 ms mouse double-click after preview scrolling at all six viewport sizes for all six candidates; it also verifies query/page/local-scroll/focus return, explicit relation, and the exact native-download SHA.

## Q-01–Q-20 qualitative checklist

| Item | Result | Evidence |
| --- | --- | --- |
| Q-01 | N/A | No long navigator tree in this reader-comparison state. |
| Q-02 | Pass | Local result scrolling is retained; return is checked for every candidate. |
| Q-03 | N/A | No compact Materials browse-tree target in this prototype. |
| Q-04 | Pass | One click now yields a visible preview at every reviewed narrow viewport; detail, pagination, collapse and return remain covered. |
| Q-05 | Pass | Current 1920 A-F previews show compact, non-colliding engineering axes and titles. |
| Q-06 | Pass | Legend is compact and separate from selection actions. |
| Q-07 | Pass | Current source retains proportional SVG sizing; inspected previews show no distortion. |
| Q-08 | N/A | Fixture is labelled engineering stress–strain, not a true-yield response. |
| Q-09 | N/A | No changed overflow-affordance topology in this correction. |
| Q-10 | N/A | No Modeling Fit screen. |
| Q-11 | N/A | No Modeling rail target. |
| Q-12 | N/A | No Export setup target. |
| Q-13 | N/A | No Export setup/result target. |
| Q-14 | N/A | No Export readiness state. |
| Q-15 | Pass | Current preview plots retain axes, unit titles, zero anchor and clear curve/frame spacing. |
| Q-16 | N/A | Reader comparison, not Export native-preview topology. |
| Q-17 | N/A | No Administration Object list. |
| Q-18 | N/A | No Administration add/saved-view flow. |
| Q-19 | Pass | Direct related-item traversal is tested for every candidate; no inferred card chain. |
| Q-20 | Pass | 1366/1440/1920/2560/3840 browser-viewport checks pass without overflow; physical Windows high-DPI readability remains outside this evidence. |

Limits: this is a synthetic 48-Test-Data/8-Card comparison prototype with no production API, asynchronous behavior, reload persistence, owner-selected winner, production cutover, or physical high-DPI approval.
