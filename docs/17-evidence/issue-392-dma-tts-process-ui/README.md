# Issue #392 DMA TTS Process UI acceptance

## Scope classification

- Complete before this unit: Issue #391 backend multi-temperature/multi-frequency DMA TTS
  recommendation, immutable Processing Output, exact resource read, digest and provenance contracts; Issue
  #377 Modeling shell and 1–10-term Prony Fit selection flow.
- Partial before this unit: fixed-frequency DMA could enter Process and Fit, but the browser client classified
  the multi-frequency result incompletely and could not prepare, save, read back or fit the specialized output.
- Missing and implemented here: strict fixed/multi/direct routing; backend recommendation consumption;
  multi-sweep Process rail and raw/shifted presentation; one explicit create followed by exact specialized and
  common-resource reads; retry semantics; exact calibration/checking partitions through Fit; browser and visual
  acceptance.
- Owned exclusions: Issue #380's full live acceptance and export coverage are not claimed.

## Primary user journey

The browser imports the bounded NIST SRM 2491-derived six-temperature frequency-sweep fixture, resolves the
five required DMA channels, and enters Process. It asks the backend for the recommendation, displays sweep 4
at 303.15 K as the recommended reference without recalculating that decision in React, and keeps sweep 1 as
the checking partition. The engineer may review Advanced controls, then performs one explicit **Save TTS
processing output** action. After `201`, the client reads the exact specialized output and common Processing
Output link, displays raw plus backend-shifted sweeps, and continues with that pinned revision to Fit. Fit
calculates the 1–10-term candidates, exposes the recommendation separately from engineer Selection, saves an
alternate selection with a reason, and reads the same decision back after reload.

Recovery is distinct from creation: `4xx` validation keeps the draft editable; timeout, network and `5xx`
responses are shown as outcome unknown and never auto-repeat the create POST. Once `201` is known, failures in
exact read or common-link loading retry only those GETs.

## Acceptance result

- Main browser journey: PASS. Exact import → recommendation → one create → exact read → Fit candidates →
  alternate Selection/reason → reload completed against the production Compose stack.
- Regression journeys: PASS. Fixed-frequency DMA Process/Fit and the isolated Issue #392 fixture flow remain
  operational.
- Preserved contracts: PASS. No `latest`, first-item or global-output fallback; React consumes backend
  recommendation, diagnostics, partitions and shifted values verbatim.
- Persistence/read-back: PASS. The exact saved Processing Output and engineer Fit selection survive reload.
- Recovery: PASS in focused component tests for editable `4xx`, outcome-unknown `5xx`, and no automatic POST
  replay.
- Five viewport geometry: PASS at 1366×768, 1440×900, 1920×1080, 2560×1440 and 3840×2160, browser zoom 100%,
  DPR 1. Physical Windows 4K readability remains governed by #223.

## #249 synthesis disposition

- Information hierarchy: PASS. The flat sweep rail, recommendation/advanced decision band, dominant graph and
  saved-result details form one readable hierarchy without nested cards or a permanent inspector.
- Engineering task flow: PASS. Raw review → backend recommendation → explicit save → exact read-back → Fit is
  visible and ordered; error recovery stays at the affected operation.
- Responsive/wide-screen composition: PASS. The sweep rail remains bounded, controls retain readable widths,
  and the graph uses additional width and height at 1920/2560/3840 without a capped work island or synthetic
  filler.

## Q-01–Q-20 disposition

| Check | Result | Evidence |
| --- | --- | --- |
| Q-01 | PASS | The six-sweep Process navigator is independently bounded and scrollable when content exceeds it. |
| Q-02 | N/A | This unit has no long result-list surface; the saved output is a bounded detail result. |
| Q-03 | N/A | Materials navigation is unchanged. |
| Q-04 | PASS | The carried output reaches the existing shallow Fit controls, dominant graph and bounded decision dock. |
| Q-05 | PASS | Process and Fit axes, units and titles remain collision-free at all captured viewports. |
| Q-06 | PASS | Temperature/channel curve identity stays compact and separate from recommendation and save state. |
| Q-07 | PASS | Plot geometry is recomputed per viewport with unchanged glyph/stroke proportions and no SVG scaling shortcut. |
| Q-08 | N/A | No metal yield response is changed. |
| Q-09 | PASS | The bounded sweep rail provides a discoverable local overflow track with keyboard/wheel consequences. |
| Q-10 | PASS | The final Fit capture keeps its legend in a curve-free region and preserves graph width. |
| Q-11 | PASS | Multi-input Process uses the shared flat navigator rhythm; it is functional rather than decorative. |
| Q-12 | N/A | Export branching and unit-system controls are outside Issue #392. |
| Q-13 | N/A | Export row grammar is unchanged. |
| Q-14 | N/A | Export readiness is unchanged. |
| Q-15 | PASS | Reduced angular-frequency domain/headroom is derived from the displayed backend values. |
| Q-16 | N/A | Solver-card preview is unchanged. |
| Q-17 | N/A | Administration lists are unchanged. |
| Q-18 | N/A | Administration add/save behavior is unchanged. |
| Q-19 | N/A | Administration Link Type behavior is unchanged. |
| Q-20 | PASS | All five shells span the viewport; the rail and prose stay bounded while graphs gain useful space. |

The exact asset paths, dimensions and SHA-256 values are registered in [manifest.yaml](manifest.yaml).
Product-owner visual geometry disposition remains pending and is a merge gate, not a PR gate.
