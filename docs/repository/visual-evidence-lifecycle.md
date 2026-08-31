# Visual evidence lifecycle

This repository treats visual evidence as a governed release input, not as a scratch directory.
The authoritative machine-readable rules are in
[`docs/documentation-manifest.yaml`](../documentation-manifest.yaml), and the offline impact gate
enforces them before documentation is accepted.

The approved repository-owner choice is to keep only the affected canonical current screenshot
families and manifest tracked for new product guidance. Historical raster evidence is frozen unless
an exact owner-approved cleanup list removes a complete retired packet after its current-guide and
contract references are decoupled. The Materials service-reference conversion is one such bounded
operation: every retired image and measurement pair must be removed only after the current-product
evidence manifest points to the replacement, and the semantic retirement policy verifies raw
merge-base Git-blob hashes, complete-set coupling and zero adjacent-file impact. Explicitly retained
top-level reports remain in place, and the .artifacts directory is used for transient review material.

## Three states

| State | Location | Purpose | Read-back rule |
| --- | --- | --- | --- |
| current | `docs/user-guide/images/current/` | The screenshots linked by the current product guide | A clean checkout must be able to read the current Markdown, screenshot manifest, and tracked PNG family. |
| frozen | `docs/17-evidence/images/` | Historical issue packets, approved references, provenance and checksums | Immutable by default; a path-specific exception must satisfy its coupling contract. |
| transient | `.artifacts/` | Before/after captures, crops and review diagnostics | Ignored and never accepted as documentation impact evidence. |

The roots are repository-relative POSIX paths and do not overlap. Raster extensions are exactly
`.png`, `.jpg`, and `.jpeg`, matched case-insensitively. A malformed manifest, duplicate path,
absolute path, backslash, dot segment, unknown lifecycle, or ambiguous exception overlap fails closed.
Frozen exceptions are resolved before the frozen default so an intentionally nested exception cannot
be mistaken for a general historical write permission.

## Service-reference current-guide lifecycle

The service-reference register also supports `current-guide` beside `static-bundle` and
`current-product-evidence`. A `current-guide` entry is resolved through
`docs/user-guide/screenshot-manifest.yaml` by its exact `guide_screenshot_id`; its image must be the
same tracked PNG under `docs/user-guide/images/current/`, with matching route, viewport, dimensions
and SHA-256. These entries intentionally carry no static-bundle `sources`, `measurements`,
`evidence_manifest` or `evidence_key` fields.

## Primary journey

For a user-visible React/CSS change, capture and review before/after originals and direct crops in
`.artifacts`. When the change is accepted, promote the affected current guide Markdown, the current
screenshot manifest, and a same-stem five-file PNG family at `1366x768`, `1440x900`, `1920x1080`,
`2560x1440`, and `3840x2160` into `docs/user-guide/images/current/`. The documentation-impact check
then verifies the observable contract. Historical evidence or transient artifacts alone never
satisfy it.

## Fixed exceptions

- The historical static bundle is immutable by default. The three Administration database
  current-product originals may change only when both `docs/product/service-reference-manifest.yaml`
  and `docs/17-evidence/images/issue-289-administration-database-workflow/visual-evidence.yaml`
  change in the same diff. Materials current-product references resolve through the screenshot
  manifest's exact route/image/viewport mapping; they do not retain inbound approved-reference lists
  or circular evidence links. Any approved Materials retirement must satisfy the complete-set
  merge-base hash policy described above, and adjacent historical rasters remain frozen.
- #184 to #223 permits exactly the 30 names missing in the base snapshot
  `94d8a1cdefa104fb41865171093b0657966b159f` under `after/{compact,standard,large}/`. They are
  add-only, require the issue-184 manifest in the diff, and the working-tree manifest must read back
  the added name as no longer missing.
- Actual-device #223 rasters may be added or modified only with `manifest.json` or
  `visual-evidence.yaml` in the same issue root. Deletes and renames are rejected.
- #331 authorizes one exact Fit transition from the frozen #167 static bundle to four
  `current-guide` entries. The four named PNGs and their four coupled measurement JSON files may be
  removed only as one eight-member set when the service-reference manifest, service-reference
  inventory, screenshot manifest and this lifecycle policy change in the same diff. Each deleted
  blob must exist at its merge base with the recorded Git-blob SHA-256 (raw repository bytes, not
  host checkout line endings), be absent from the worktree, and the merge base must still be
  available; adjacent files, partial batches, changed/current members and later reuse are rejected.
  Only the four exact PNGs bypass the frozen-raster rule; their JSON files are coupled cleanup
  records, not an additional deletion allowlist.
- #351 authorizes the one-time deletion of the approved 26 immediate evidence roots after removing
  their current screenshot-manifest fields and inbound repository-local links. The 128 current
  screenshots, #223 handoff roots, #289 exception files, unconverted static service-reference
  targets and the retained top-level Markdown allowlist are outside that deletion authority. The
  exact root list and measured byte count are recorded in the issue and its Task 3 pull request.

## Retained top-level evidence Markdown

Only the following eighteen Markdown reports remain directly under `docs/17-evidence/`. They are an
explicit allowlist, grouped by the contract that keeps them in the working tree.

Nested `images/**/image-index.md` files are frozen-raster inventories and archive rationales, not
top-level completion reports. They keep immutable raster packets registered with the offline image
inventory after their completed reports leave the working tree.

### A. Contract-test inputs

The fixed-base historical helper-link test reads these two reports directly:

- [`issue-261-css-inventory-and-migration-plan.md`](../17-evidence/issue-261-css-inventory-and-migration-plan.md)
- [`issue-261-m1e5-producer-routed-residual.md`](../17-evidence/issue-261-m1e5-producer-routed-residual.md)

### B. Retained local contract and selector inputs

The #351 reaggregation keeps these ten reports because contract tests, repository tools or the CSS
selector inventory still consume them as repository-local inputs. The current screenshot manifest
no longer points to historical evidence reports or images; current capture registration and frozen
task evidence are separate contracts. Offline hooks continue to validate only the local inputs they
actually own and never require a live GitHub lookup.

- [`issue-260-modeling-data-visual-normalization.md`](../17-evidence/issue-260-modeling-data-visual-normalization.md)
- [`issue-261-b1-modeling-stage-css-ownership.md`](../17-evidence/issue-261-b1-modeling-stage-css-ownership.md)
- [`issue-261-b4-css-ownership-integration.md`](../17-evidence/issue-261-b4-css-ownership-integration.md)
- [`issue-261-fe06-residual-owner-boundary-consolidation.md`](../17-evidence/issue-261-fe06-residual-owner-boundary-consolidation.md)
- [`issue-261-m1e-modeling-ownership-integration.md`](../17-evidence/issue-261-m1e-modeling-ownership-integration.md)
- [`issue-261-m1e3-modeling-family-ownership.md`](../17-evidence/issue-261-m1e3-modeling-family-ownership.md)
- [`issue-261-m2-materials-css-ownership.md`](../17-evidence/issue-261-m2-materials-css-ownership.md)
- [`issue-261-m6-zero-consumer-audit-and-removal.md`](../17-evidence/issue-261-m6-zero-consumer-audit-and-removal.md)
- [`issue-262-fe07a-materials-architecture-ui.md`](../17-evidence/issue-262-fe07a-materials-architecture-ui.md)
- [`issue-309-modeling-data-axis-overlap.md`](../17-evidence/issue-309-modeling-data-axis-overlap.md)

### C. Open-issue and fixed-exception inputs

These six reports remain because the open #223 handoff or a fixed current-product exception still
uses their human-readable evidence. The current product-owner decision retains the two issue-342
Task 1B packets as fixed reference inputs pending the final Task 4 allowlist.

- [`issue-184-high-dpi-global-implementation.md`](../17-evidence/issue-184-high-dpi-global-implementation.md)
- [`issue-184-to-223-windows-4k-handoff.md`](../17-evidence/issue-184-to-223-windows-4k-handoff.md)
- [`issue-221-high-dpi-decision.md`](../17-evidence/issue-221-high-dpi-decision.md)
- [`issue-289-administration-database-workflow.md`](../17-evidence/issue-289-administration-database-workflow.md)
- [`issue-342-task1b-frontend-design-packet.md`](../17-evidence/issue-342-task1b-frontend-design-packet.md)
- [`issue-342-task1b-json-record-registration.md`](../17-evidence/issue-342-task1b-json-record-registration.md)

## Recovery

Except for an exact owner-approved cleanup such as #351, the lifecycle gate does not delete
historical bytes. If a mistaken raster or script is introduced under a frozen path, move a review
capture to `.artifacts` or promote it through the current lifecycle; inspect or restore a historical
byte or helper from the fixed base snapshot with:

```powershell
git show 94d8a1cdefa104fb41865171093b0657966b159f:<path>
```

The command restores or inspects one exact path; it does not imply that a full-clone history has
shrunk. An approved working-tree deletion likewise does not rewrite Git history. Checksums,
provenance, exact viewport identity and five-view preservation remain authoritative for retained
packets, and hooks never depend on a live GitHub lookup.
