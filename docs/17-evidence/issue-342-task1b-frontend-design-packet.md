# Issue #342 Task 1B — frontend implementation and visual acceptance packet

## Status and boundary

Status: **APPROVED — implemented, Main-accepted, independently reviewed, and product-owner approved.**

This packet describes the live production React implementation, not the earlier proposed mockup. Five
valid-preview originals (and their current-guide images) were captured against a fully fresh Docker
composition with new PostgreSQL/object volumes, fresh API/worker/web images, and the Issue #342 migration.
The other forty state/viewport originals use production React with the repository-standard mocked API
boundary for deterministic state coverage. Main's fresh-Docker PostgreSQL/API/browser acceptance passed
exact source/provenance/name reload read-back, atomic rollback, publication visibility, and exact download
checks. The product owner reviewed the presented 1920×1080, 2560×1440, and 3840×2160 originals and
approved the corrected page on 2026-08-28.

## User journey and control contract

1. The operator opens **Administration → Records → Import records**. The existing Records type/search/list
   surface is replaced by the import workspace until **Close** restores it.
2. **Add files** accepts JSON and the existing CSV/TSV/XLSX formats. The chosen file bytes determine the
   import path; the operator does not choose a record type, format, or revision in the import workspace.
3. For JSON, the server matches every file to one accessible installed exact format revision. The normal
   surface shows the user-readable **Detected content** name; exact revision and provenance stay in the
   stored response/evidence contract.
4. **Preview** validates the whole batch. A rejected file reports filename, exact JSON location, cause,
   and recovery. The selected files and last valid result remain available across retryable failures.
5. After a valid preview, the operator enters **Reason for change** and presses local **Save**. The left
   step remains **Save draft** so the result is unambiguous. Saving is atomic and creates drafts only;
   review and publication remain separate governed states.
6. **Open records** returns to the exact saved table/revision context. It never substitutes the first
   record, a latest revision, or another session result.

The normal surface contains no raw reference JSON, UUID, SHA, preview token, package identity, wrapper,
binding count, ZIP explanation, classification, or revision selector. The visible names are inventoried
once in `live/normal-surface-inventory.json`.

## Shared component and geometry inventory

- Shared semantic/control ownership: `live/component-style-inventory.json`.
- Five-viewport bounds, DPR, page overflow, pane allocation, field/action bounds, and hidden surrounding
  Records surfaces: `live/valid-preview-measurements.json`.
- All state/viewport document and pane bounds: `live/state-inventory.json`.
- Direct 100%-pixel header, workspace, and control crops for valid preview: `live/crops/`.

The implementation uses the shared semantic pane, text, message, button, field, and input primitives.
The original-resolution review confirmed common font roles and baselines, vertically centered single-line
controls, readable disabled controls, shared spacing, flat panes, bounded prose/forms, and elastic file and
preview areas. Selector/computed measurements are supporting evidence; the PASS decisions below are
qualitative judgments of each original.

At 1366×768, long filename and Record cells intentionally retain the table's ellipsis behavior. Each cell
now exposes its exact unabridged value through the native title affordance and accessible name; the focused
component test verifies both values. This resolves the independent review's Q-17 finding without widening
the pane or adding a page-specific tooltip treatment.

## Compact state / viewport matrix

`P` means PASS. Each row reuses one original for all five judgments; criteria are not duplicated into
separate rows.

| State | Viewport / original | Typography / alignment | Padding | Helper copy | Whitespace / density | Concise names |
| --- | --- | --- | --- | --- | --- | --- |
| normal | [1366×768](issue-342-ui-acceptance/live/originals/issue342-normal-1366x768.png) | P | P | P | P | P |
| normal | [1440×900](issue-342-ui-acceptance/live/originals/issue342-normal-1440x900.png) | P | P | P | P | P |
| normal | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-normal-1920x1080.png) | P | P | P | P | P |
| normal | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-normal-2560x1440.png) | P | P | P | P | P |
| normal | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-normal-3840x2160.png) | P | P | P | P | P |
| empty | [1366×768](issue-342-ui-acceptance/live/originals/issue342-empty-1366x768.png) | P | P | P | P | P |
| empty | [1440×900](issue-342-ui-acceptance/live/originals/issue342-empty-1440x900.png) | P | P | P | P | P |
| empty | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-empty-1920x1080.png) | P | P | P | P | P |
| empty | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-empty-2560x1440.png) | P | P | P | P | P |
| empty | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-empty-3840x2160.png) | P | P | P | P | P |
| loading | [1366×768](issue-342-ui-acceptance/live/originals/issue342-loading-1366x768.png) | P | P | P | P | P |
| loading | [1440×900](issue-342-ui-acceptance/live/originals/issue342-loading-1440x900.png) | P | P | P | P | P |
| loading | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-loading-1920x1080.png) | P | P | P | P | P |
| loading | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-loading-2560x1440.png) | P | P | P | P | P |
| loading | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-loading-3840x2160.png) | P | P | P | P | P |
| error | [1366×768](issue-342-ui-acceptance/live/originals/issue342-error-1366x768.png) | P | P | P | P | P |
| error | [1440×900](issue-342-ui-acceptance/live/originals/issue342-error-1440x900.png) | P | P | P | P | P |
| error | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-error-1920x1080.png) | P | P | P | P | P |
| error | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-error-2560x1440.png) | P | P | P | P | P |
| error | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-error-3840x2160.png) | P | P | P | P | P |
| upload-error | [1366×768](issue-342-ui-acceptance/live/originals/issue342-upload-error-1366x768.png) | P | P | P | P | P |
| upload-error | [1440×900](issue-342-ui-acceptance/live/originals/issue342-upload-error-1440x900.png) | P | P | P | P | P |
| upload-error | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-upload-error-1920x1080.png) | P | P | P | P | P |
| upload-error | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-upload-error-2560x1440.png) | P | P | P | P | P |
| upload-error | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-upload-error-3840x2160.png) | P | P | P | P | P |
| invalid-preview | [1366×768](issue-342-ui-acceptance/live/originals/issue342-invalid-preview-1366x768.png) | P | P | P | P | P |
| invalid-preview | [1440×900](issue-342-ui-acceptance/live/originals/issue342-invalid-preview-1440x900.png) | P | P | P | P | P |
| invalid-preview | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-invalid-preview-1920x1080.png) | P | P | P | P | P |
| invalid-preview | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-invalid-preview-2560x1440.png) | P | P | P | P | P |
| invalid-preview | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-invalid-preview-3840x2160.png) | P | P | P | P | P |
| valid-preview | [1366×768](issue-342-ui-acceptance/live/originals/issue342-valid-preview-1366x768.png) | P | P | P | P | P |
| valid-preview | [1440×900](issue-342-ui-acceptance/live/originals/issue342-valid-preview-1440x900.png) | P | P | P | P | P |
| valid-preview | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-valid-preview-1920x1080.png) | P | P | P | P | P |
| valid-preview | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-valid-preview-2560x1440.png) | P | P | P | P | P |
| valid-preview | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-valid-preview-3840x2160.png) | P | P | P | P | P |
| save-error | [1366×768](issue-342-ui-acceptance/live/originals/issue342-save-error-1366x768.png) | P | P | P | P | P |
| save-error | [1440×900](issue-342-ui-acceptance/live/originals/issue342-save-error-1440x900.png) | P | P | P | P | P |
| save-error | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-save-error-1920x1080.png) | P | P | P | P | P |
| save-error | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-save-error-2560x1440.png) | P | P | P | P | P |
| save-error | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-save-error-3840x2160.png) | P | P | P | P | P |
| saved | [1366×768](issue-342-ui-acceptance/live/originals/issue342-saved-1366x768.png) | P | P | P | P | P |
| saved | [1440×900](issue-342-ui-acceptance/live/originals/issue342-saved-1440x900.png) | P | P | P | P | P |
| saved | [1920×1080](issue-342-ui-acceptance/live/originals/issue342-saved-1920x1080.png) | P | P | P | P | P |
| saved | [2560×1440](issue-342-ui-acceptance/live/originals/issue342-saved-2560x1440.png) | P | P | P | P | P |
| saved | [3840×2160](issue-342-ui-acceptance/live/originals/issue342-saved-3840x2160.png) | P | P | P | P | P |

## #249 three-axis judgment

- **Carbon information hierarchy — PASS:** one Import records entry, one current step, flat panes, one
  primary local action, and technical identity removed from the normal surface.
- **COMSOL engineering task flow — PASS:** Files → Preview → Save draft is explicit; file rows retain
  validation status and the selected file owns its preview/diagnostic context.
- **SAP responsive/wide-screen logic — PASS:** the navigator stays bounded, additional width goes to the
  file list and preview, additional height remains local scroll capacity, and all five viewports have no
  page-level overflow or clipped commands.

Main opened all 45 originals at original resolution and the valid-preview direct crops. The product owner
then reviewed the presented 1920×1080, 2560×1440, and 3840×2160 valid-preview originals and approved the
corrected page on 2026-08-28.
