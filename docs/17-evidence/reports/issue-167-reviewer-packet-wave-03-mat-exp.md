# Issue #167 reviewer packet — WAVE-03 / MAT-EXP exceptional states

Date: 2026-07-29  
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the two remaining Materials explorer approval references:

- long result set at 1440×900;
- empty result set at 1440×900.

The already approved three-viewport normal family is frozen. Evaluate whether these two states
preserve its continuous navigator/results/selected-context topology, result-grid dominance,
server-scoped count semantics, selected-material continuity where applicable, readable tree kinds,
one clear recovery action and no overlap, clipping or page overflow. Long must render one
deterministic 50-row page with a total greater than 50 and independent result scrolling. Empty must
clear every material selection in the results, tree and selected-context region while keeping the
browse hierarchy mounted.

Also inspect the deterministic 1366×768, 1440×900 and 1920×1080 evidence for long, empty, query
loading, lazy tree loading, query error and tree error. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero
and complete evidence. Do not modify files.

## Approved parent references

- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png`
  — `b1fc0cfeaaa0734e22d6678eef3ef6ca03cecdbce3d6588d8bee18f4a9572065`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png`
  — `8f99dba3ec20cc75f29ab938dfa42682ff741ef624fcdd495b89fd673e49c53b`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png`
  — `b92757e5f80cbcd020f73d54af65cd700112497a76e40f412cfc0a60988ef191`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/materials-search-long-1440x900.png`
  — `8c70f5790ed02d1864d456f5947975871122b712d28d523096330e021e2b7f06`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-empty-1440x900.png`
  — `19bb7a9e50496786a87eb22f0c8a9f31a1da944bcc76a55f451b1d157135648e`

The 1366 and 1920 responsive siblings use
`materials-search-{long,empty}-1440x900.responsive-{1366x768,1920x1080}.{png,measurements.json}`.
All loading/error evidence, exact paths, dimensions and SHA-256 values are recorded in
`docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/materials-search-exceptional.html`
- `docs/00-research/ux-service-reference/materials-search-exceptional.css`
- `docs/00-research/ux-service-reference/materials-search-exceptional.js`
- `docs/00-research/ux-service-reference/capture_materials_search_wave03.py`
- `docs/00-research/ux-service-reference/validate_materials_search_wave03.py`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.staging.json`
- `docs/17-evidence/images/issue-167-service-reference/materials-search-wave03.state-evidence.json`
- the candidate, responsive and state images/measurements named above.

No approved parent source/image, shared manifest/inventory, production React/CSS or other family
was changed. Common lifecycle registration is deliberately deferred until the two WAVE-03 family
reviews finish.

## Main-agent evaluation and deterministic results

The main agent opened both final candidate PNGs at original resolution. Its first empty-state
inspection rejected a stale highlighted DP780 Record; the same initial writer removed the visual
and ARIA selection from every Record while retaining the hierarchy, added a deterministic
assertion, and recaptured the family. The final empty image now has zero selected tree/result rows,
`No material selected`, no datasheet action and one `Clear search` action.

```text
family capture from final sources                               pass, 18 outputs
independent pending-lifecycle family validator                  pass, 18 targets
long rows / total / result scroll                               50 / 126 / independent
long selected context / one Open datasheet                      pass / pass
empty selected tree/result/context                              0 / 0 / absent
empty recovery                                                  one Clear search
tree kind containment / horizontal overflow                     pass / 0
keyboard search, tree, results, splitters and retries           pass
loading/error context retention and recovery                    pass
legacy active-route selectors                                   zero
console errors / page errors / document overflow                zero
Ruff / Node syntax / diff checks                                pass
frozen normal hashes and validators                             unchanged / pass
candidate lifecycle evidence                                    pending / approval absent
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Independently open the
two candidates and representative state evidence and rerun the validator. Do not edit.
