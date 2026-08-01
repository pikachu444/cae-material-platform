# Issue #167 WAVE-05 pre-publish image-contract correction packet

Date: 2026-07-29
Author: active `/root` primary agent
Correction role: one fresh configured `correction_terra_high`, read/write, sole correction for this deterministic failure

## Trigger

The WAVE-05 Luna Max writer completed its bundle validator, but the repository pre-publish gate
failed after the main agent registered the #167 structured image manifests with the documentation
inventory. The failure is not permission to delete or fabricate captures. It exposes two missing
archive contracts:

1. #167 YAML/JSON manifests and measurements must count as structured image references.
2. A small set of intentionally equal historical captures needs an explicit, bounded duplicate
   equivalence with a human-readable rationale.

The main agent already has uncommitted, in-scope edits in
`backend/src/cmp/tools/user_guide.py` and `docs/17-evidence/screenshot-archive.yaml`. Preserve and
complete those edits. Do not revert or replace unrelated work.

## Allowed ownership

- `backend/src/cmp/tools/user_guide.py`
- focused contract tests under `tests/contracts/`
- `docs/user-guide/screenshot-manifest.yaml` only if the existing manifest is the narrowest
  authoritative location for explicit duplicate allowances
- `docs/17-evidence/screenshot-archive.yaml`
- this correction packet only if recording exact test evidence is useful

Do not edit #167 visual HTML/CSS/JavaScript, approval PNGs, production React/CSS, the common
service-reference manifest, inventory, or shared freeze report.

## Required behavior

1. Keep structured reference discovery narrowly scoped to:
   - `docs/01-product/service-reference-manifest.yaml`;
   - #167 staging/state/measurement JSON files;
   - existing fixed structured image manifests.
2. Reject missing referenced files, paths outside the repository, and whitespace-concatenated
   pseudo-paths.
3. Continue rejecting unregistered images.
4. Continue rejecting duplicate hashes by default.
5. Add an explicit allowance mechanism for historical-only duplicate groups only when every exact
   path is listed and a non-empty rationale explains why the final visual is intentionally equal.
   Allowances must be rejected when repeated, malformed, outside `docs/17-evidence/images/`, or
   unused.
6. Register only the currently observed intentional groups:
   - ADM number editor equals its number-type conditional-state evidence, at all three viewports.
   - ADM long-invalid equals long-scroll evidence, at all three viewports.
   - ADM database error equals selection-continuity-after-error evidence, at all three viewports.
   - ADM database loading equals stale-response-suppression-while-loading evidence, at all three
     viewports.
   - ADM database normal equals normal-scroll and splitter-restored-normal evidence, at all three
     viewports.
   - Materials card normal 1366 equals successful error-recovery 1366 evidence.
7. Do not permit directory globs as duplicate allowances and do not globally exempt #167.
8. Preserve the superseded MOD-EXPORT layout concept through its explicit screenshot archive entry.

## Deterministic acceptance

- `uv run python -m pytest tests/contracts/test_user_guide.py -q`
- focused new positive and negative tests for the duplicate allowance parser/gate
- `uv run ruff check backend/src/cmp/tools/user_guide.py tests/contracts`
- `git diff --check`
- a direct `verify_user_guide` run reports zero orphan images and zero invalid duplicate groups
- no PNG bytes change

Return the exact files changed and test results. Do not commit, push, or spawn another agent.
