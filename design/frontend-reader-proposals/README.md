# Six unselected engineering reader proposals

P2-C5 · 2026-09-07. Open `index.html` in a browser. Choose A–F in the upper selector.
These are independent static proposals, not the React draft in `apps/web-next` or a production release.

Working update after P2-C5: the owner prefers the Granta layout direction. A now starts with a desktop
list/right-preview area, material/specimen browsing and separate name/temperature/rate filters.
Returning from full detail restores its preview as well as list context. The committed P2-C5 PDF and
`evidence/` are the earlier comparison; they do not certify this later source. New verification output
is `.artifacts/granta-reader-update/`. The other five layouts retain their comparison role.

| Proposal | Composition | Best candidate use | Tradeoff |
| --- | --- | --- | --- |
| A · Granta-inspired | Facets and technical sheet | Classification-heavy lookup | Extra navigation consumes width |
| B · Total Materia-inspired | Explicit search console and separate document | Primary data/card lookup | Tall search form; repeated curve comparison needs another view |
| C · Koyfin-inspired | Watchlist and analysis windows | Repeated analytical inspection | Window chrome and split space |
| D · TradingView-inspired | Screener and dominant chart | Curve investigation | Sparse card data leaves excess room |
| E · Document synthesis | Index and technical document | Reading one engineering record | Less benefit for large-screen comparison |
| F · Condition synthesis | Transposed matrix and notebook | A small shortlisted comparison | Poor as the first view of thousands of records |

Main recommends evaluating B for primary lookup, D for curve work and F for shortlisted comparison.
This is a task-fit judgment, not a measured user preference or an owner selection. Do not blend all six
into one screen. The matching task navigation is intentional; body layout differences are preserved.
Reference names describe inspiration, not reproduction of vendor code, assets or affiliation.

Single-click selects and previews. Double-click, Enter or Open detail opens full detail. Collapse keeps
selection. Return restores query, page, local scroll and focus. Page/filter changes clear transient
selection. Small screens bring the preview heading/actions into view; its body may require scrolling.
Properties, units and conditions are separate fields. One exact stored card example downloads without
processing or generating it again. Other cards explicitly lack a native file.

## Reproduce

From repository root with the locked Node dependencies installed:

```text
node design/frontend-reader-proposals/verify.mjs
```

The source is `workspaces.html`; the verifier creates the standalone wrapper and evidence under
`.artifacts/reader-proposals/`. `index.html` is a generated copy of that wrapper. The committed `evidence/`
contains the frozen P2-C5 capture set, source hash, browser checks and review. `build_report.py` generates
`comparison.pdf` from those images using ReportLab and Korean fonts (Windows Malgun by default).

See [comparison.pdf](comparison.pdf) for one proposal per page and [assessment.md](assessment.md) for
the original brief coverage, skills assessment, remaining implementation and limitations.

Synthetic 48 Test Data/8 Card metadata records; one native reference file. No production API, persistence
across reload, asynchronous processing, database migration, scientific qualification or physical 4K
approval is claimed. Browser geometry and interaction evidence do not select a production design.
