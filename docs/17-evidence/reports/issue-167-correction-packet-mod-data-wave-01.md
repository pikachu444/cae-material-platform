# Issue #167 correction packet — WAVE-01 / MOD-DATA

Date: 2026-07-29  
Correction role: configured `correction_terra_high`, one and only correction for this family  
Issue: <https://github.com/pikachu444/cae-material-platform/issues/167>

## Why this correction is authorized

The fresh read-only review scored the family 31/32 but requested one correction. In the invalid
mapping responsive state, the auto-height Data ribbon occupies about 73% of the available workspace
at 1366×768 and leaves the graph canvas only 103 px high. The 1440×900 canonical canvas is 235 px
high. This fails the Modeling requirement for a persistent, meaningfully usable dominant graph even
though the page has no horizontal overflow.

The direct cause is the invalid-state combination around
`docs/00-research/ux-service-reference/modeling-data.css`: the Data ribbon grows with all mapping
content while `.state-invalid .graph-canvas, .state-invalid .source-plot` remove the normal graph
minimum.

## Bounded outcome

Correct only the MOD-DATA invalid-mapping layout and its bounded capture/validation evidence so the
complete mapping decision and a readable last-valid graph remain visible together at 1366×768,
1440×900 and 1920×1080.

This is static reference work only. Do not change production React/CSS, shared inventory/evidence
reports, user guides, current screenshots, git state, commits, branches, remotes or GitHub.

## Allowed ownership

You may edit only:

- `docs/00-research/ux-service-reference/modeling-data-normal.html`
- `docs/00-research/ux-service-reference/modeling-data.css`
- `docs/00-research/ux-service-reference/modeling-data.js`
- `docs/00-research/ux-service-reference/capture_modeling_data.py`
- `docs/00-research/ux-service-reference/validate_modeling_data.py`
- MOD-DATA-only staging/measurement/state evidence under
  `docs/17-evidence/images/issue-167-service-reference/`
- the five MOD-DATA canonical PNGs and their exceptional responsive PNG siblings

Do not edit the common manifest, finite inventory, common evidence report, reviewer packet,
Materials sources/evidence or any file under `apps/`. Other work exists in this worktree; preserve
it and never reset, clean, stash or discard it.

## Required correction

- Preserve one compact navigator, one divider, one shallow Data region and one persistent graph.
- At every invalid-state viewport, keep the raw source inspector, explicit two-row mapping decision,
  adjacent conflict, change reason, original/normalized unit distinction, and disabled Update
  preview/Save dataset boundary usable and deliberately contained.
- Recompose or compact the invalid-only Data content instead of globally shrinking text. Do not
  remove required decisions, hide them behind Advanced, introduce a third inspector, or allow
  horizontal page/table overflow. A contained internal disclosure or scrolling region is acceptable
  only if the screenshot still exposes the complete blocking decision and its recovery path.
- Restore a meaningful graph allocation. The graph panel must occupy at least 42% of the invalid
  main workspace height at each viewport. Its canvas must be at least 210 px at 1366×768, 265 px at
  1440×900 and 300 px at 1920×1080.
- Keep the stale boundary explicit: `Last valid preview · stale · not updated`; never imply the
  invalid mapping was previewed or saved.
- Do not alter the normal or Empty topology, interactions, copy, graphs or registered candidate
  pixels unless a shared-source change makes a strictly necessary no-regression recapture.
- Add deterministic assertions for the invalid graph share and viewport-specific canvas minimums.

## Required verification and handoff

Recapture all five canonical MOD-DATA targets and all invalid responsive evidence. Re-run the full
MOD-DATA validator and the writer packet's deterministic checks. Report:

- exact files changed;
- all commands and results;
- final invalid graph/ribbon/canvas measurements at 1366, 1440 and 1920;
- final SHA-256 values for any changed canonical/responsive PNG;
- confirmation that normal and Empty hashes are unchanged;
- any residual limitation.

Do not update shared integration documents, commit, or start another family.
