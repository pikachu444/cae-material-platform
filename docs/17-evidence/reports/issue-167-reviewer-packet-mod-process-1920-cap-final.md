# Issue #167 fresh reviewer packet — MOD-PROCESS 1920 graph cap

Date: 2026-07-31
Reviewer: one fresh configured read-only `reviewer_terra_high`
Requested disposition: `approve` or `changes_requested`

## Bounded acceptance

The product owner approved ADM-SCHEMA-CORE only and rejected MOD-PROCESS wide scaling with the
explicit direction: use the 1920 graph size as the limit. This review covers only the resulting
MOD-PROCESS correction and its preserved state/interaction evidence.

Required result:

- 1920×1080 remains the maximum useful graph reference;
- 2560 and 3840 must not enlarge the graph beyond that useful bound;
- the 3840 topology keeps a truthful ten-row Processed response table but bounds it to its
  five-column content and places it with the graph as a coherent left/top result cluster;
- unused space is allowed only after the complete task at the right and bottom; no fabricated
  content or viewport-filling stretch;
- `preview-loading` and `commit-loading` visibly disable both Preview and Save commands;
- the existing navigator, graph, data/headroom, typography, legend, axis, task-language,
  invalidation, blocked recovery, keyboard and scrolling contracts remain intact.

## Exact implementation and evidence

Review the diff only for:

- `docs/00-research/ux-service-reference/modeling-process.css`;
- `docs/00-research/ux-service-reference/modeling-process.js`;
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`;
- the MOD-PROCESS images, measurements and JSON evidence below.

Open every lifecycle image at original resolution:

| Target | SHA-256 |
| --- | --- |
| `modeling-process-normal-1366x768.png` | `6722bd80c851b47c941cbac92c03e10a6106566fef940fabe9d8ab61c7fec825` |
| `modeling-process-normal-1440x900.png` | `122cf29074eea18bfd0549ad40dc0d9143b1ee6bb2bd82df6266194645b5d3ae` |
| `modeling-process-normal-1920x1080.png` | `87a861aa3e8822e4fe19645230f426f902ced609eea09e62b6fdae67f1a9cf09` |
| `modeling-process-prerequisite-blocked-1440x900.png` | `2f3ed351bbb22b604e6a7bed189b52cd7b9945f8620633d2442482654492ed30` |
| `modeling-process-normal-3840x2160.png` | `abe0d8396e2a77df8a14ef81a5d62111e0469435352356559d402e2d9db9b4b4` |

Also open the supporting
`modeling-process-normal-2560x1440.png`
(`0f63b5d5c9e8648e5d9d9b41d75462a7b31403819a1c3f790ace9a487ba92f65`)
and all fifteen originals registered by:

- `docs/17-evidence/images/issue-167-service-reference/modeling-process-state-evidence.json`;
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-responsive-evidence.json`.

Measured result:

- 1920 graph: 1689×680 at x=222, y=344;
- 2560 graph: 1689×680 at x=222, y=358;
- 3840 graph: 1689×680 at x=222, y=358;
- 3840 table: 880×330.5 at x=1931, y=358 — same top edge and 20 px gutter.

## Independently rerun

Run:

```powershell
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status accepted
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
python -m py_compile docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

The active main agent ran these gates successfully and opened all five lifecycle originals, the
2560 support original and the 1920 preview-loading original. The main-agent internal disposition is
`accepted`; product-owner approval remains absent.

## Required qualitative review

Before disposition, complete every applicable V-01–V-16 and Q-01–Q-20 item from
`docs/01-product/visual-acceptance-matrix.md`, with pass/fail/not-applicable and direct image/source
evidence. Measurements are supporting evidence only.

In particular:

- Q-04: shallow Modeling control ribbon and persistent dominant graph;
- Q-05: compact professional axes, units and ticks without collision;
- Q-06/Q-10: compact in-plot legend in a curve-free region;
- Q-07: no glyph/stroke/aspect distortion across viewports;
- Q-09/Q-11: readable independent navigator/long-rail behavior;
- Q-20: added wide area does not stretch the graph/table, distribute related controls, introduce
  filler or create an unfinished component interior.

Reject even with passing measurements if the 2560/3840 composition reads as an oversized poster,
the graph and table appear unrelated, the blank region falls between related components rather
than after the task, or any visible engineering/task-language defect remains.
