# Issue #167 product-owner-authorized correction packet — MOD-PROCESS 1920 cap

Date: 2026-07-31
Writer: one fresh configured `correction_terra_high`
Mode: one bounded correction after product-owner rejection of the wide-screen proportion

## Authority and decision

The product owner approved only the complete ADM-SCHEMA-CORE bundle and explicitly directed:
`MOD-PROCESS는 1920 크기를 기준으로 그래프를 제한하고 수정한다.`

The active main agent reopened the final MOD-PROCESS originals and measured:

- 1920×1080: graph canvas approximately 1689×680 px — the approved sizing reference;
- 2560×1440: graph canvas approximately 2329×1040 px — rejected viewport-driven enlargement;
- 3840×2160: graph canvas approximately 3609×1407.5 px and five-column Processed response table
  approximately 3609 px wide — rejected viewport-filling composition.

This owner-authorized correction supersedes the former 3840 graph-height acceptance rule. The
1920 graph is now the maximum useful graph size, not a value to scale proportionally with the
viewport.

Read and follow:

- `AGENTS.md`;
- `.codex/config.toml` and `.codex/agents/correction-terra-high.toml`;
- `docs/01-product/visual-acceptance-matrix.md`;
- the current MOD-PROCESS HTML/CSS/JavaScript, capture, validator, staging and state evidence;
- `docs/17-evidence/reports/issue-167-owner-authorized-correction-packet-mod-process-final.md`;
- `docs/17-evidence/reports/issue-167-reviewer-packet-mod-process-final.md`;
- `docs/17-evidence/reports/issue-167-reviewer-packet-mod-process-wide-proportion.md`.

## Owned files

Edit only the MOD-PROCESS packet-owned static reference:

- `docs/00-research/ux-service-reference/modeling-process.css`;
- `docs/00-research/ux-service-reference/modeling-process.js`;
- `docs/00-research/ux-service-reference/capture_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/validate_modeling_process_wave02.py`;
- `docs/00-research/ux-service-reference/modeling-process-wave02.staging.json`;
- MOD-PROCESS candidate/support/state images, measurements and JSON evidence under
  `docs/17-evidence/images/issue-167-service-reference/`.

Do not edit the common manifest, inventory counts, freeze report, UI specification, another family,
production React/CSS, Git state or GitHub state. Other agents and the user own all unrelated
worktree changes; do not revert them.

## Required visual composition

1. Preserve the current 1366×768, 1440×900 and 1920×1080 task topology, rail, shallow operation
   ribbon, graph contract, task language and behavior. Small changes required to share the corrected
   wide rule or busy-state rule are allowed, but do not redesign these viewports.
2. Treat the current 1920 graph canvas (approximately 1689×680 px) as the upper useful graph bound.
   At 2560 and 3840, the graph must not grow materially beyond that bound in either dimension.
   Do not stretch the plot, SVG, typography, strokes, legend or data range to consume the viewport.
3. At 2560, keep the bounded graph left/top aligned directly below its toolbar within the main
   working surface. Unused space begins after the complete task at the right and bottom; do not
   distribute related controls across that space or fabricate filler.
4. At 3840, retain the topology-changing Processed response table, but make it content-appropriate
   for five columns and ten rows. The table must not be full viewport width. Place the bounded graph
   and bounded table as one coherent left/top result cluster with an ordinary 16–24 px relationship
   gutter. Prefer top-aligned adjacency when both remain readable; a compact immediately-below
   placement is acceptable only if it creates the clearer relationship. Do not leave a large void
   between related graph and table.
5. Keep the settings ribbon bounded to its existing useful maximum. Preserve the 184/192/208 px
   navigator defaults, independent rail scrolling, 11/12 px engineering graph typography,
   non-scaling strokes, in-plot collision-free legend, numeric ticks, complete engineering axis
   titles and data-relative top/right headroom.
6. Preserve exactly ten Processed response rows sourced from the renderer arrays. Do not resample,
   interpolate, smooth, enrich or fabricate data. The table remains absent at 1366, 1440, 1920 and
   2560.
7. Do not add prose, badges, internal/developer vocabulary, duplicated commands, decorative cards,
   or controls whose consequence is not represented in the state contract.

## Busy-state defect to correct

The previous fresh review found a real static-evidence mismatch: the captured `preview-loading`
state left the global `Preview changes` command enabled even though the actual preview path prevents
duplicate submission.

- `preview-loading`: disable the sole `Preview changes` command and `Save processed curves`.
- `commit-loading`: disable `Save processed curves` and the sole `Preview changes` command.
- Preserve the existing error recovery and actual duplicate-submit guards.
- Extend capture and validation so each loading-state image proves the visible command states, not
  merely internal dataset flags.

## Deterministic and qualitative gates

Call capture and validator `--help` before execution, then run the complete MOD-PROCESS recapture.
Run the family validator, finite inventory validator, Ruff, Python compilation, Node syntax and
`git diff --check`.

Validation must prove:

- exact dimensions, paths and SHA-256 values;
- zero console, page and resource errors and zero body/document overflow;
- all five lifecycle targets and all existing responsive/loading/error/long-rail evidence;
- graph width and height at 2560 and 3840 do not materially exceed the 1920 graph bound;
- the 3840 table is bounded, content-sized, exactly ten rows, and forms a coherent result cluster
  with the graph;
- loading commands are visibly disabled in both loading states at 1366, 1440 and 1920;
- the finite-data SVG contract, data-relative headroom, stable typography/strokes, legend, axes,
  keyboard behavior, divider behavior, blocked recovery and immutable-revision behavior remain
  intact.

After deterministic success, inspect the 1920, 2560 and 3840 originals qualitatively. Verify that
the plot is still useful at 1920, does not become an oversized poster at wider viewports, and the
3840 result table neither stretches nor floats apart from its graph. Return changed paths, all
commands/results, candidate/support hashes and any residual concern. Do not claim product-owner
approval.
