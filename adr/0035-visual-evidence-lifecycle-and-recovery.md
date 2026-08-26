# ADR-0035: Visual evidence lifecycle and recovery

- Status: Accepted
- Date: 2026-08-26
- Scope: repository documentation and release/governance evidence

## Context

Visual evidence has three different jobs. A temporary capture is useful while a UI change is being
reviewed, a current guide image explains the product that is checked out, and historical evidence
must remain reproducible after the implementation has moved on. Treating those bytes as one mutable
pool made it possible for an old issue packet or an ignored capture to look like current guidance.

## Decision

The repository owner chose a tracked current lifecycle, frozen historical evidence, and ignored
transient review space so new guidance can be read back from a clean checkout without rewriting
old issue packets.

1. The documentation manifest declares three non-overlapping roots: current
   `docs/user-guide/images/current`, frozen `docs/17-evidence/images`, and ignored transient
   `.artifacts`. Raster policy is limited to `.png`, `.jpg`, and `.jpeg`, case-insensitively.
2. Review captures are written to `.artifacts` first. A reviewed product change promotes exactly the
   affected current guide Markdown, screenshot manifest, and one complete five-view PNG family
   (`1366x768`, `1440x900`, `1920x1080`, `2560x1440`, `3840x2160`). A clean checkout can therefore
   read current guidance from tracked Markdown, manifest, and current PNGs alone.
3. Frozen evidence is immutable by default. The exact #167 current-product exception consists of the
   three issue-289 administration database originals and requires both the service-reference
   manifest and issue-289 visual-evidence manifest in the same diff. The #184-to-#223 handoff is
   limited to the base-derived 30 missing originals, add-only, with the issue-184 manifest updated;
   working-tree manifest state is only read back after an allowed addition. Actual-device #223
   rasters are add/modify-only with a same-root `manifest.json` or `visual-evidence.yaml` update.
4. Checksums, provenance, viewport identity, and five-view preservation remain part of the evidence
   records. The repository does not claim that the full clone becomes smaller: the existing roughly
   514 MB historical evidence is untouched. If a deleted script or frozen byte is needed, recover
   the exact base snapshot with `git show 94d8a1cdefa104fb41865171093b0657966b159f:<path>`.
5. Hooks and offline checks must not perform live GitHub lookups. The lifecycle gate is evaluated
   from the diff, the checked-out manifests, and the fixed base snapshot only.

## Consequences

- CSS and React/CSS user-visible changes cannot bypass current documentation merely because their
  bytes happen to match an old evidence packet.
- Old #261 evidence remains frozen, while its completed top-level helper scripts may be removed from
  the working tree and recovered from the fixed base when historical investigation requires them.
- Product-owner visual acceptance and the actual Windows 4K readability gate remain separate from
  deterministic offline geometry and lifecycle checks.
