# Issue #167 reviewer packet — WAVE-03 / MOD-FIT

Date: 2026-07-29
Review mode: fresh, independent, read-only

## Issue acceptance boundary

Freeze the complete Modeling Fit reference family:

- normal at 1366×768, 1440×900 and 1920×1080;
- candidate-parameters-long at 1440×900.

Evaluate the engineer task, not decoration: compare recomputed material-model candidates against
the exact processed evidence, distinguish recommendation from explicit engineer selection, inspect
the observed/extrapolated boundary, and open contained parameter evidence without losing the
persistent graph. A recommendation must never silently become the selected candidate.

Inspect the deterministic 1366×768, 1440×900 and 1920×1080 evidence for no-candidate empty,
calculating, stale/no-selection blocked and candidate-calculation error. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero
and complete evidence. Do not modify files.

## Approved parent references

MOD-DATA:

- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `docs/17-evidence/images/issue-167-service-reference/modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`

MOD-PROCESS:

- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1366x768.png`
  — `c537c7caf60d668a82021e50cdc0307b185faf118d5091edc41c10d9c5ef0cad`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1440x900.png`
  — `57d5c9e8f9ebbf21315ca94f76eb21e11ce116526afffc717973ebb514417461`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1920x1080.png`
  — `154c21e6679b999ee63ca65c10ac6e7af8a8ebdb54b69490be67460078ce53c1`

Fit-specific lower authority:

- `docs/00-research/ux-layout-review/modeling.html`
- `docs/00-research/ux-layout-review/review.css`
- `docs/17-evidence/images/ux-layout-review/modeling-reference-comparison.png`
- `docs/00-research/images/gui-reference/modeler-fit-extrapolation.png`

## Candidate images

- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1366x768.png`
  — `33e84e09265d07a5c836c82c21622b64ca1f35fbd9646a1fe1aeb1589bf0efe7`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1440x900.png`
  — `194c1cad19ae8712b0c29d82b0b0c439989cf556d9a812468a13712066b7e9c3`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-normal-1920x1080.png`
  — `82cdcb393097c9ba767e82c3cddf8f582787f81f6496018ac3eea0ce064c96c4`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-candidate-parameters-long-1440x900.png`
  — `d16c32e031d17bc34aed6ba660d0f7796e9bd214dc7ee6601922a075c0f6aae0`

All state-evidence paths, dimensions and SHA-256 values are recorded in
`docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json`.

## Implementation diff

Review only:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json`
- `docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json`
- the four candidate images/measurements and 12 state images/measurements named above.

No approved parent source/image, shared manifest/inventory, production React/CSS or other family
was changed. Common lifecycle registration is deliberately deferred until this review finishes.

## Main-agent evaluation and deterministic results

The main agent opened all four final candidates and every one of the 12 responsive state images at
original resolution. The initial writer result was rejected during main-agent inspection until:

- plot limits were derived from finite data with 10% proportional headroom and an altered-extrema
  proof, rather than hard-coded maxima or paths ending at the plot boundary;
- normal data/control text computed to at least 13 px and metadata/help to at least 12 px;
- the long disclosure kept the graph mounted, showed all candidate rows, explicit selection,
  readable parameter names/value/unit/bounds, reason and applicable warning acknowledgement;
- the stale state set the actual visible Target strain input and all explanatory copy consistently
  to `1.20`, cleared the selection and disabled Save at all three viewports.

The same original Luna Max writer made these pre-review corrections. No correction agent or model
substitution was used.

```text
family capture from final sources                               pass, 4 approval + 12 state outputs
independent pending-lifecycle family validator                  pass, 4 targets
normal recommendation / engineer selection                     present / absent
normal Save / adjacent reason                                   disabled / present
long selection / reason / warning acknowledgement               explicit / present / checked
plot finite x/y maxima                                          0.42 / 1260
plot derived limits / proportional headroom                     0.50 / 1400 / 10%
altered-extrema proof                                           pass
1440 graph workspace width share                                >= 72%
splitter Arrow/Home/End/collapse/restore geometry + ARIA         pass
input/inclusion invalidation; update does not auto-select        pass
reason + applicable acknowledgement gate Save                   pass
graph views and disclosure preserve selection/context           pass
stale input/copy/selection/Save at 1366/1440/1920                1.20 / aligned / none / disabled
loading/error preserve exact source, rail, ribbon and graph      pass
typography / nested interactive controls / legacy selectors     pass / zero / zero
console errors / page errors / document overflow                zero
Ruff / Node syntax / diff checks                                pass
approved parent hashes                                          unchanged
candidate lifecycle evidence                                    pending / approval absent
```

Rerun:

```text
uv run --with playwright python docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py --all-packet-targets --expect-main-agent-status pending
uv run ruff check docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py
node --check docs/00-research/ux-service-reference/modeling-fit.js
git diff --check -- docs/00-research/ux-service-reference/modeling-fit-normal.html docs/00-research/ux-service-reference/modeling-fit.css docs/00-research/ux-service-reference/modeling-fit.js docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json
```

Return one disposition (`approve` or `changes_requested`), V-01–V-16 scores, hard-gate failures,
actionable findings with direct file/evidence paths, and residual concerns. Independently open all
four candidates plus representative responsive state evidence and rerun the validator. Do not edit.
