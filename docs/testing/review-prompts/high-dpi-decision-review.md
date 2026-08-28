# Independent #221 provisional high-DPI decision review

You are the final independent, read-only reviewer for issue #221. Do not modify files, create commits,
push, open or update pull requests, approve a GitHub pull request, or merge anything.

The review decides whether the evidence is sufficient for the product owner to select one shared
implementation policy before issue #184 applies it to every route. It approves logical layout and
provisional density behavior only. Actual Windows 4K physical readability remains the final #223 gate.
It does not approve #184, #223, every application screen, or a new route-specific visual design.

## Required inputs

The review packet must embed or attach the exact version of:

- issue #221 and `docs/planning/high-dpi-display-strategy.md`;
- the merged #161 token/shell/pane baseline;
- the candidate implementation diff and exact shared tokens;
- the same representative data and state rendered for P1, P2 and P3;
- original 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160 captures;
- 100%-pixel crops of header, navigator, table/form control and graph/native preview;
- the available-display record, including monitor size/resolution, Windows scale, browser zoom, CSS
  viewport and `devicePixelRatio`, plus an explicit `COMPLETE` or `DEFERRED_TO_223` physical status;
- pane resize/collapse/reset/persistence, table sizing, plot resize and browser-zoom-200% results;
- 모든 대표 화면에서 완료한 20개 정성 판정 결과 (Q-01~Q-20).

Missing actual Windows 4K evidence does not block this provisional decision when the packet identifies
the unavailable device condition and routes the exact physical matrix to #223. Playwright viewport
emulation, DOM measurements and contact sheets still do not replace or imply the physical record. If
the packet claims physical readability from those substitutes, return `NEEDS_CHANGES`.

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
14. Is unavailable actual-device evidence recorded as `DEFERRED_TO_223` without a physical-readability
    claim, and does the #223 handoff cover every representative route and high-risk state?

## Disposition

Return exactly one JSON object and no prose outside it:

```json
{
  "disposition": "APPROVE_PROVISIONAL_DECISION | NEEDS_CHANGES",
  "selected_candidate": "P1 | P2 | P3 | null",
  "physical_evidence_status": "COMPLETE | DEFERRED_TO_223",
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
  "issue_184_handoff": [],
  "issue_223_physical_handoff": []
}
```

`APPROVE_PROVISIONAL_DECISION` requires every boolean except `actual_windows_4k_complete` to be true,
no blocking finding, one selected candidate, exact provisional shared token/default/reset/persistence
terms when applicable, original-resolution five-viewport product-owner evidence, and complete handoff
lists for #184 implementation and #223 physical validation. When actual 4K is unavailable,
`physical_evidence_status` must be `DEFERRED_TO_223` and `actual_windows_4k_complete` must remain false.
Reviewer approval is evidence for the product owner; it does not publish, merge, replace the owner's
explicit implementation decision, or claim final physical readability.
