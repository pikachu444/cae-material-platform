# Independent #221 high-DPI decision review

You are the final independent, read-only reviewer for issue #221. Do not modify files, create commits,
push, open or update pull requests, approve a GitHub pull request, or merge anything.

The review decides whether the evidence is sufficient for the product owner to select one shared
4K/high-DPI policy before issue #184 applies it to every route. It does not approve #184, every
application screen, or a new route-specific visual design.

## Required inputs

The review packet must embed or attach the exact version of:

- issue #221 and `docs/12-roadmap/high-dpi-display-strategy.md`;
- the merged #161 token/shell/pane baseline;
- the candidate implementation diff and exact shared tokens;
- the same representative data and state rendered for P1, P2 and P3;
- original 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160 captures;
- 100%-pixel crops of header, navigator, table/form control and graph/native preview;
- actual Windows 4K 100%, 150% and 200% records with monitor size/resolution, Windows scale,
  browser zoom, CSS viewport, `devicePixelRatio`, selected density and original/crop paths;
- pane resize/collapse/reset/persistence, table sizing, plot resize and browser-zoom-200% results;
- completed Q-01 through Q-20 results for every representative screen.

If actual Windows evidence is missing, mismatched, scaled down, or does not identify the environment,
return `BLOCKED_PHYSICAL_EVIDENCE`. Playwright viewport emulation, DOM measurements and contact sheets do
not replace the physical record.

## Review questions

1. Were P1, P2 and P3 compared with the same data, route state, viewport and browser zoom?
2. Does the selected candidate separate logical workspace allocation from physical UI readability?
3. Does the shell span the viewport without leaving a one-sided 1920px work island or dominant internal
   void between related regions?
4. Do navigator, inspector, property form and prose retain justified limits while table, graph and
   native preview receive useful remaining space?
5. Are pane min/ideal/max, resize, collapse, reset, keyboard operation and persistence explicit?
6. Do table identity/action/status columns remain bounded while data/evidence columns use justified
   min/max/flex sizing and local scrolling?
7. Does plot resize recompute render box, axes, legend, labels, paths and hit regions from the actual
   container without non-uniform stretching?
8. Are `Compact / Standard / Large` values, default, user choice, reset and persistence explicit if P2
   is selected?
9. Is any automatic choice based only on DPR, CSS resolution or viewport width? If so, require changes.
10. Are route-specific 4K rules, CSS `zoom`, blanket `transform: scale`, fabricated filler, uniform
    stretching and private route tokens absent?
11. Do 1366/1440/1920 preserve the approved compact engineering topology and primary task?
12. Does browser zoom 200% retain content, functionality and reachable actions without unjustified
    two-axis page scrolling?
13. Are rejected candidates and the remaining #184 route/state migration list explicit?

## Disposition

Return exactly one JSON object and no prose outside it:

```json
{
  "disposition": "APPROVE_DECISION | NEEDS_CHANGES | BLOCKED_PHYSICAL_EVIDENCE",
  "selected_candidate": "P1 | P2 | P3 | null",
  "actual_windows_4k_complete": false,
  "five_viewport_matrix_complete": false,
  "compact_topology_preserved": false,
  "semantic_elasticity_pass": false,
  "density_contract_complete": false,
  "pane_table_plot_contract_complete": false,
  "forbidden_techniques_absent": false,
  "browser_zoom_200_pass": false,
  "evidence_paths": [],
  "blocking_findings": [],
  "non_blocking_findings": [],
  "approved_token_summary": null,
  "issue_184_handoff": []
}
```

`APPROVE_DECISION` requires every boolean to be true, no blocking finding, one selected candidate,
exact shared token/default/reset/persistence terms when applicable, and direct original-resolution
product-owner evidence. Reviewer approval is evidence for the product owner; it does not publish,
merge or replace the owner's explicit decision.
