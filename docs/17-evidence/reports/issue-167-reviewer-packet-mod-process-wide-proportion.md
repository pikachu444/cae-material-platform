# Issue #167 MOD-PROCESS wide-proportion reviewer packet

Date: 2026-07-31

## Review boundary

Perform a fresh, read-only review of the corrected `MOD-PROCESS` reference bundle. Do not edit any
file, reinterpret later screen families, or review unrelated dirty-worktree changes. This is a
static-reference gate, not production React/CSS work.

The bundle must preserve the approved Process task:

- the approved `MOD-DATA` Test Data is the exact prerequisite;
- selection, inclusion and local plot visibility remain distinct;
- the five processing operations retain their order;
- Preview is non-persistent and Save creates one immutable Processing Output;
- a missing compatible saved Test Data disables Preview and Save without inventing fallback data;
- 1366×768, 1440×900, 1920×1080 and supporting 2560×1440 remain graph-first;
- the 3840×2160 topology bounds the graph and uses the recovered region for an exact ten-row
  `Processed response` grid generated from the same displayed arrays, with no interpolation,
  resampling, fabricated enrichment or filler prose.

The active main agent rejected the first 3840 correction because its plot still expanded to roughly
3,609×1,723 pixels. Review the final correction independently; automated geometry is supporting
evidence, not the visual conclusion.

## Approved dependency

The product owner approved these exact `MOD-DATA` references:

| Target | SHA-256 |
| --- | --- |
| `modeling-data-normal-1366x768.png` | `a5a61b1f960575ed5f266d218bc5ff748a4fb986dcc53807604c8e17d0d0e64c` |
| `modeling-data-normal-1440x900.png` | `5e831b9ea26489f44d6b8ef263d104951968f0107aecb983f0cd9ed0ebcefe54` |
| `modeling-data-normal-1920x1080.png` | `fc3fc35693718f5aa5e3902d6b7ade39f8f2009f33c6507fadc6733b517a0fbe` |
| `modeling-data-empty-new-session-1440x900.png` | `c6b7949a32019ef3dc29a3c4dd27444c5a4e466798360c1f76fb650242a105e8` |
| `modeling-data-long-invalid-mapping-blocked-1440x900.png` | `0c661147014fecdb5ad290a9c9ead01d9a389c84f12eb9fe87f6548cbe362356` |

The dependency approval is recorded in
`docs/17-evidence/reports/issue-167-service-reference-freeze.md` section 84 and the authoritative
manifest.

## Exact implementation and contract paths

- `docs/00-research/ux-service-reference/modeling-process-normal.html`
- `docs/00-research/ux-service-reference/modeling-process.css`
- `docs/00-research/ux-service-reference/modeling-process.js`
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`
- `docs/01-product/desktop-engineering-ui-product-spec.md`
- `docs/01-product/desktop-engineering-ui-spec.md`
- `docs/01-product/service-reference-inventory.yaml`
- `docs/01-product/service-reference-manifest.yaml`
- `docs/00-research/ux-service-reference/validate_service_reference_inventory.py`
- `docs/17-evidence/reports/issue-167-wide-correction-packet-mod-process.md`
- `docs/17-evidence/reports/issue-167-correction-packet-mod-process-wide-proportion.md`

Read the issue acceptance and cumulative qualitative rules in:

- `docs/01-product/visual-acceptance-matrix.md`
- `docs/17-evidence/reports/issue-167-service-reference-freeze.md` sections 77 and 84–87

## Original-resolution images and hashes

Open every image below at original resolution.

| Role | Image | SHA-256 |
| --- | --- | --- |
| approval target | `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1366x768.png` | `7e0e53dfea8e842859dda93c7126dd75add1f5a9a1a7ddabce1d780e9e1dc339` |
| approval target | `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1440x900.png` | `bc45bc41a10db0ba0af217e5ae2b60ce978abfaeaea99d19ca701bac490a8f04` |
| approval target | `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-1920x1080.png` | `87a861aa3e8822e4fe19645230f426f902ced609eea09e62b6fdae67f1a9cf09` |
| approval target | `docs/17-evidence/images/issue-167-service-reference/modeling-process-prerequisite-blocked-1440x900.png` | `2f3ed351bbb22b604e6a7bed189b52cd7b9945f8620633d2442482654492ed30` |
| wide support | `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-2560x1440.png` | `44799e263a57c03a16ecaf36e5977596309c0cb02bf06df2bfc583b826d2be68` |
| topology approval target | `docs/17-evidence/images/issue-167-service-reference/modeling-process-normal-3840x2160.png` | `a17b105bb043b42b8920e7f279fc2dba62dd1029392935e2b0d409cca6764e29` |

Also inspect the responsive blocked captures named by the manifest and every long/loading/error
capture named in:

- `docs/17-evidence/images/issue-167-service-reference/modeling-process-responsive-evidence.json`
- `docs/17-evidence/images/issue-167-service-reference/modeling-process-state-evidence.json`

## Deterministic evidence

The active main agent ran these non-mutating gates after the final capture:

```powershell
python docs/00-research/ux-service-reference/capture_modeling_process_wave02.py --help
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --help
python docs/00-research/ux-service-reference/validate_modeling_process_wave02.py --all-packet-targets --expect-main-agent-status pending
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m ruff check docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
python -m py_compile docs/00-research/ux-service-reference/capture_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_modeling_process_wave02.py docs/00-research/ux-service-reference/validate_service_reference_inventory.py
node --check docs/00-research/ux-service-reference/modeling-process.js
git diff --check
```

They passed. Independently verify the hashes and rerun the non-mutating gates. The inventory result
must be `54 normal + 18 exceptional + 1 topology variant = 73 images`, with `37/73 approved`.

## Required independent qualitative review

Complete Q-01–Q-20 from `docs/01-product/visual-acceptance-matrix.md`, marking each item `pass`,
`fail`, or `not-applicable` with a topology reason and direct image/path evidence. In particular:

- judge whether the rail, ribbon, graph, status and optional point grid form a professional whole at
  every viewport rather than merely satisfying measurements;
- reject exaggerated graph scale, stretched typography/rows, weak hierarchy, avoidable blank space,
  decorative or fabricated filler, and internal/developer vocabulary;
- verify compact complete engineering axes, stable glyph/stroke proportions, proportional
  data-derived headroom and a compact curve-free legend;
- verify the 3840 grid contains exactly the same ten finite source/observed/processed points used by
  the graph, remains absent through 2560, and does not introduce a fake scrollbar;
- verify the blocked state has one clear recovery path and does not expose Mapping Profile, full
  identifiers, algorithm names or implementation-state vocabulary in the primary workspace.

Return actionable findings first, followed by `approve` or `changes_requested`. The reviewer is not
the final design authority; the active main agent repeats the original-resolution gate after the
review.
