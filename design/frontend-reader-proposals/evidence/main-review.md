# Main checkpoint acceptance

2026-09-07 · P2-C5. Source SHA is recorded in checks.json and independent-review.md.

Main implemented the accepted click/preview/detail flow directly. Result DOM stays connected during
selection. Detail removes the result list; closing restores query, page, local offsets and focus.
Minimal preview-heading scrolling fixes offscreen actions on narrow viewports. A physical second
click retains the first record even if scrolling moves the row. Removed the obsolete C narrow rule
that hid the remaining full-detail window. The final browser run passed 230 checks with no errors.

Main inspected all six 1920 list-preview and full-detail screens during implementation, all six final
1920 card originals, and all six corrected 1366 previews. The independent reviewer inspected final
1366/1024/360 originals across A–F and approved the bounded checkpoint (see independent-review.md).
The seven-page comparison PDF was rendered and every page inspected for layout and content.

Hierarchy: separate name/material/specimen/test/temperature/rate columns; individual card property,
value and unit rows. Engineering flow: direct lookup and exact stored card download; no generation
detour. Responsive composition: wide side previews for A/B/C/E; bottom preview when width is limited
and in D/F. Preview body may continue below the fold. Full-detail views reclaim list space.

Candidate tradeoffs remain real: A spends width on facets; B's form consumes height; C adds window
chrome; D's sparse card view has excessive spare room; E is weaker for comparison; F suits shortlists.
These are unselected alternatives, not a claim of equivalent production readiness or measured user
preference. No blanket physical 4K/readability approval. The screenshots are CSS viewports at device
scale factor 1. No API, async race, database, writer or reload persistence acceptance is claimed.

The React foundation is a separate earlier draft: 18 tests, typecheck and prototype/ordinary builds
passed. D0 documentation had earlier Main/independent acceptance; current changes remove residual
A/B/brownfield and overbroad architecture-skill routing and preserve the accepted interaction policy.

Disposition: suitable for owner-authorized three local checkpoint commits; no push, PR, merge,
production design selection, cutover or full-program completion.
