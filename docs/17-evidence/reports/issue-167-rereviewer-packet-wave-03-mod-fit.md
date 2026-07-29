# Issue #167 fresh re-review packet — WAVE-03 / MOD-FIT correction

Date: 2026-07-29
Review mode: fresh, independent, read-only

## Issue acceptance

Review the product-owner-authorized correction of the four still-pending Fit references:

- normal at 1366×768, 1440×900 and 1920×1080;
- candidate-parameters-long at 1440×900.

The correction must make Fit graph-first without changing its state/data semantics: compact
26–28 px curve and 24–26 px operation rows, a contained responsive Fit ribbon, one shallow
computation/decision band, centered `Stress (MPa)` and `Equivalent plastic strain` axis titles,
numeric-only ticks, finite-data-derived 10% headroom, and an on-demand bottom parameter drawer. The
open drawer must scroll independently, use no more than 35% of the workspace and preserve an actual
plot at least 230 px high. Recommendation and explicit selection remain distinct; the status bar
must name the selected candidate/task and reset after invalidation.

Open all 16 current MOD-FIT images at original resolution, including no-candidate, calculating,
stale/blocked and error states at three viewports. Score V-01–V-16 from
`docs/01-product/visual-acceptance-matrix.md`. Passing requires at least 28/32, no hard-gate zero
and complete evidence. Specifically reject any 1366 ribbon collision, squeezed empty graph, axis
label collision or meaningless clipped decision/recovery text. Do not edit any file.

The product owner rejected the preceding reviewed version because title/tick/axis gaps remained too
large, the x title appeared absent, and unused graph/footer space still made the plot feel squeezed.
Specifically verify the current visible 13 px centered x title, compact y-title/tick/axis adjacency,
reduced plot insets, and matching engineering-axis grammar in normal and long states. Passing
mechanical non-intersection alone is insufficient.

Authoritative correction packet:
`docs/17-evidence/reports/issue-167-correction-packet-wave-03-mod-fit.md`.

## Approved parents

MOD-DATA:

- `modeling-data-normal-1366x768.png`
  — `07ca35cd91a01b10616d171ff2f7efb68f1f0adb4e73fa77e381cf6853693e95`
- `modeling-data-normal-1440x900.png`
  — `fa4c2bbae72a56fcbeac21e7b62a7471be44fb7f602058c155d0a128cb5bdb6f`
- `modeling-data-normal-1920x1080.png`
  — `b75163296be31a39b567943ccecd8a85005647ae692272f2cdf7d134b0ea27f5`

MOD-PROCESS:

- `modeling-process-normal-1366x768.png`
  — `c537c7caf60d668a82021e50cdc0307b185faf118d5091edc41c10d9c5ef0cad`
- `modeling-process-normal-1440x900.png`
  — `57d5c9e8f9ebbf21315ca94f76eb21e11ce116526afffc717973ebb514417461`
- `modeling-process-normal-1920x1080.png`
  — `154c21e6679b999ee63ca65c10ac6e7af8a8ebdb54b69490be67460078ce53c1`

All paths above are under
`docs/17-evidence/images/issue-167-service-reference/`.

## Corrected candidates and evidence

- `modeling-fit-normal-1366x768.png`
  — `5d3a59d3fb6a947defd23450fee2f979f81fb16687381343bea5b94de962f504`
- `modeling-fit-normal-1440x900.png`
  — `be4a9b051a266c4f8c55ebb0136046c3c016e6beaf278669200c91046ead8749`
- `modeling-fit-normal-1920x1080.png`
  — `4bd100acbe61bcaa5359949da9ef602ac7b64493799fb66ecaeb65a58ef0a4bf`
- `modeling-fit-candidate-parameters-long-1440x900.png`
  — `84d5ba46d5fa81850376558595c75b73f1a1a6b5c7a4c9a0721e782155f3d545`
- complete state paths, dimensions and hashes:
  `docs/17-evidence/images/issue-167-service-reference/modeling-fit-state-evidence.json`

The source/evidence diff boundary is:

- `docs/00-research/ux-service-reference/modeling-fit-normal.html`
- `docs/00-research/ux-service-reference/modeling-fit.css`
- `docs/00-research/ux-service-reference/modeling-fit.js`
- `docs/00-research/ux-service-reference/capture_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/validate_modeling_fit_wave03.py`
- `docs/00-research/ux-service-reference/modeling-fit-wave03.staging.json`
- the four candidate plus 12 state images/measurements and state-evidence JSON
- the four MOD-FIT pending lifecycle entries only in
  `docs/01-product/service-reference-manifest.yaml`

No approved parent, production UI or other family was changed.

## Main-agent and deterministic evidence

The main agent opened every final image at original resolution. In addition to preserving the
earlier graph-first corrections, it directly corrected the product-owner axis-spacing finding:
the visible x title is persistent at 13 px, title/tick/axis gaps are bounded, unused SVG/footer
space is reduced and normal/long images use the same engineering-axis grammar.

```text
family validator                                             pass, 4 + 12
normal actual plot Fit-workspace share                       >= 45% all viewports
long actual plot / drawer share                              >= 230 px and >=30% / <=35%
empty drawer / useful plot                                   closed / pass all viewports
drawer internal overflow + PageDown                          pass
curve / operation row heights                               26–28 / 24–26 px
axis titles / ticks                                          centered unit titles / numeric only
visible x title / x-title-to-tick gap                        13 px / 0–18 px
y-title-to-tick / y-tick-to-axis gaps                        2–24 px / 2–12 px
plot left/right/bottom inset ratios                          <=6.5% / <=6.5% / <=11.5%
visible axis title-tick/legend collision                     zero
finite extrema / headroom / altered-extrema proof            0.42, 1260 / 10% / pass
normal selection / Save                                      absent / disabled with reason
long selection / reason / acknowledgement / Save             explicit / present / checked / enabled
status footer selection and invalidation reset                pass
splitters, curve controls, graph modes and invalidation       pass
console/page errors; overflow; nested controls                zero
parent validators / Ruff / Node / inventory / diff            pass
lifecycle                                                     pending / main accepted / PO absent
```

Fresh Terra High result: `approve`; V-01–V-16 all `2`, total `32/32`; no hard-gate failure or
actionable finding. All 16 images were inspected at original resolution. The calculation, stale
and error overlays cross the upper plot area intentionally but remain readable and preserve the
graph/context at all three viewports; this is a non-blocking residual concern.
