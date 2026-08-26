# Visual evidence lifecycle

This repository treats visual evidence as a governed release input, not as a scratch directory.
The authoritative machine-readable rules are in
[`docs/documentation-manifest.yaml`](../documentation-manifest.yaml), and the offline impact gate
enforces them before documentation is accepted.

The approved repository-owner choice is to keep only the affected canonical current screenshot
families and manifest tracked for new product guidance, while preserving existing historical
evidence in place and using the .artifacts directory for transient review material.

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

## Primary journey

For a user-visible React/CSS change, capture and review before/after originals and direct crops in
`.artifacts`. When the change is accepted, promote the affected current guide Markdown, the current
screenshot manifest, and a same-stem five-file PNG family at `1366x768`, `1440x900`, `1920x1080`,
`2560x1440`, and `3840x2160` into `docs/user-guide/images/current/`. The documentation-impact check
then verifies the observable contract. Historical evidence or transient artifacts alone never
satisfy it.

## Fixed exceptions

- #167's static bundle is immutable. Only the three issue-289 administration database current-product
  originals may change, and only when both `docs/01-product/service-reference-manifest.yaml` and
  `docs/17-evidence/images/issue-289-administration-database-workflow/visual-evidence.yaml` change
  in the same diff. Every other issue-289 raster remains frozen.
- #184 to #223 permits exactly the 30 names missing in the base snapshot
  `94d8a1cdefa104fb41865171093b0657966b159f` under `after/{compact,standard,large}/`. They are
  add-only, require the issue-184 manifest in the diff, and the working-tree manifest must read back
  the added name as no longer missing.
- Actual-device #223 rasters may be added or modified only with `manifest.json` or
  `visual-evidence.yaml` in the same issue root. Deletes and renames are rejected.

## Recovery

The lifecycle gate does not delete historical bytes. If a mistaken raster or script is introduced
under a frozen path, move a review capture to `.artifacts` or promote it through the current
lifecycle; restore a historical byte or helper from the fixed base snapshot with:

```powershell
git show 94d8a1cdefa104fb41865171093b0657966b159f:<path>
```

The command restores or inspects one exact path; it does not imply that a full-clone history has
shrunk. The existing approximately 514 MB evidence collection remains untouched. Checksums,
provenance, exact viewport identity and five-view preservation remain authoritative, and hooks never
depend on a live GitHub lookup.
