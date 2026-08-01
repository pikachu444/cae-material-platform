# Issue #167 — Remaining Administration product-owner packet

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Baseline: latest `issue-167-service-reference-freeze`
Lifecycle: **product-owner approved all 17 WAVE-06 targets**

## Scope

This packet completes the finite 72-image service-reference inventory without changing production React, backend, API, migrations, or current user-guide screenshots. It adds the remaining 17 approval units for `ADM-SCHEMA-RELATIONS`, `ADM-ACCESS`, and `ADM-PUBLISH`, plus 45 evidence-only state captures and 10 deterministic 2560/3840 wide captures.

The publication family is intentionally blocked: Catalog publishing is not configured. The references keep saved definitions editable, make the disabled command’s reason visible, and direct an Administrator to enable publishing when the governed release process is available.

## Static source to production contract mapping

| Reference family | Static regions | Existing production component/API contract | Preserved behavior |
| --- | --- | --- | --- |
| Layout | Schema navigator → Layout list → ordered-field editor + saved Record preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Layout list/create/revise APIs | Current Table revision, exact Attribute revisions, ordered fields, draft validation, saved Record preview |
| Subset | Schema navigator → Subset list → typed filters + scoped result preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Subset list/create/revise APIs and server-scoped Record query | Filter definition, same-query total/rows, authorization scope, draft/error preservation |
| Link Type | Schema navigator → Link Type list → endpoint/label/cardinality editor + Related test | `apps/web/src/configurable-catalog-admin.tsx`; Link Type and exact Record Link APIs | Source/target Tables, independent cardinalities, forward/reverse labels, exact endpoint revisions, no latest alias |
| Access | Access navigator → assignment list → readable task preset / revoke confirmation | `apps/web/src/product-access-center.tsx`; product assignment list/grant/revoke APIs | User/Reviewer/Administrator roles, scope/classification, denied boundary, required revoke reason |
| Publish | Lifecycle navigator → saved draft change set → validation boundary | Catalog publishing is not configured | One disabled Publish command, editable saved drafts, validation/recovery, and a clear Administrator next step |

## Approval targets

| Target | Family/state | SHA-256 |
| --- | --- | --- |
| [administration-layout-edit-draft-1366x768](../images/issue-167-service-reference/administration-layout-edit-draft-1366x768.png) | `layout` / `draft` | `83b33ba1a8fe4dd7f9e68d532781b348373f67f5b7fb581c2195b8b670dd7e38` |
| [administration-layout-edit-draft-1440x900](../images/issue-167-service-reference/administration-layout-edit-draft-1440x900.png) | `layout` / `draft` | `c644c810f9bf09521e638500db6bc2ea79de9052e5ed99abef9aa9e4823e8899` |
| [administration-layout-edit-draft-1920x1080](../images/issue-167-service-reference/administration-layout-edit-draft-1920x1080.png) | `layout` / `draft` | `2b8feeced8fe13f26c00d5c0d84f46e823ce7e952276b664ecfa6363c200c1ec` |
| [administration-subset-edit-draft-1366x768](../images/issue-167-service-reference/administration-subset-edit-draft-1366x768.png) | `subset` / `draft` | `ebb696e2198c2ee809bcbc3a96537624296879146489e0686c8fda6897ae571c` |
| [administration-subset-edit-draft-1440x900](../images/issue-167-service-reference/administration-subset-edit-draft-1440x900.png) | `subset` / `draft` | `2944564a8bfb23b56547e9fe5a5b7bbe4d90225d8b25191d10cdc760e0bebf0f` |
| [administration-subset-edit-draft-1920x1080](../images/issue-167-service-reference/administration-subset-edit-draft-1920x1080.png) | `subset` / `draft` | `3c47bd6bfce907fb552e1d420f0595592b14fd443897726fa4f0a22d7d9aadcd` |
| [administration-link-type-edit-draft-1366x768](../images/issue-167-service-reference/administration-link-type-edit-draft-1366x768.png) | `link` / `draft` | `a45ce72250ae6abd4590aa236cacc31ad7d0b68bfe2596fc3764cb9eb3d9fb3b` |
| [administration-link-type-edit-draft-1440x900](../images/issue-167-service-reference/administration-link-type-edit-draft-1440x900.png) | `link` / `draft` | `b1d8eae9026501b63103592fb50ceaed9d65c1876b01041d713d2f320110876d` |
| [administration-link-type-edit-draft-1920x1080](../images/issue-167-service-reference/administration-link-type-edit-draft-1920x1080.png) | `link` / `draft` | `b6cc86a9255c1f1afb9e70feac549a3b6b376192e36f8f3ff5e67fea197a19ce` |
| [administration-access-normal-1366x768](../images/issue-167-service-reference/administration-access-normal-1366x768.png) | `access` / `normal` | `76aa2c7b7457e42cb6afaee775efdaadb396c67bdfb51c0d8c049bf32b4262b8` |
| [administration-access-normal-1440x900](../images/issue-167-service-reference/administration-access-normal-1440x900.png) | `access` / `normal` | `d29cefa9daf262f0a74ae924ba2a45cce82d4ed41e8c847c4850400515b939fa` |
| [administration-access-normal-1920x1080](../images/issue-167-service-reference/administration-access-normal-1920x1080.png) | `access` / `normal` | `8a8be47905e2af0e6eb24ce03c3140d15280604ae007a7af28d14dd4063c94c2` |
| [administration-access-denied-1440x900](../images/issue-167-service-reference/administration-access-denied-1440x900.png) | `access` / `denied` | `71a9a09ebc2adcfdbfea56d009a5f8cdcb6e10098c2d51d4e5ccec298826ac51` |
| [administration-access-revoke-confirm-1440x900](../images/issue-167-service-reference/administration-access-revoke-confirm-1440x900.png) | `access` / `revoke-confirm` | `c42857301a53219e05e2c810ddeb3accca96d346c6c198c0c92964cb57622171` |
| [administration-publish-blocked-1366x768](../images/issue-167-service-reference/administration-publish-blocked-1366x768.png) | `publish` / `blocked` | `422bf607c3488ef2f24b325bb8eac9b1bc5c1d8bd9bdf8f20c876991a69c8ea9` |
| [administration-publish-blocked-1440x900](../images/issue-167-service-reference/administration-publish-blocked-1440x900.png) | `publish` / `blocked` | `893e7dce8bfea50a48390e56b2eb31b16839b6e116687600a123a0a121d5008a` |
| [administration-publish-blocked-1920x1080](../images/issue-167-service-reference/administration-publish-blocked-1920x1080.png) | `publish` / `blocked` | `15d79a5708930be1793cbe7336f066196362d4793a48dfcc2176df10034b5b0d` |

## Deterministic evidence

```text
approval targets                                      17 / 17
evidence-only states                                  15 families / 45 images
wide evidence                                         10 images
exact viewport and SHA checks                          pass
browser console/page errors                            0 / 0
page horizontal/vertical overflow                      0 / 0
editor-grid, column, heading, and action containment    pass
nested interactive controls                            0
prohibited legacy selectors                            0
active filled primary commands                         <= 1 per state
body/data typography                                   <= 13.5 px
keyboard splitter and Ctrl+S/revoke interactions        pass
family-specific truth and recovery checks               pass
WAVE-06 validator                                       2642 checks / pass
service-reference inventory                             72 total; 72 approved; 0 pending
```

The configured Luna Max writer completed the product-owner-authorized additional correction without model substitution. The main agent rejected the first result after original-resolution inspection exposed clipped Link Type related-record revision values at 1366px. Luna corrected the row geometry and added a regression that fails the clipped layout before passing the corrected one.

The main agent independently reran all deterministic gates, then opened every changed Link Type approval, state and wide image at original resolution. Complete related revisions, safe right clearance, three-pane topology, dense list/editor relationship, command priority, preview continuity, bounded wide task cluster, keyboard focus/selection continuity and truthful recovery states pass without a hard-gate failure.

A fresh Access review then rejected stale selection and incomplete revoke/cancel behavior that the pixel suite did not exercise. Luna replaced hard-coded assignment content with selected-assignment data, added role-appropriate previews and keyboard continuity, unified the revoke renderer, restored the selected normal editor on Cancel, removed role-prefixed identity copy, made the revoke warning role-neutral and corrected the empty status to `Assignments · none`. The new regression failed four focused checks against the rejected behavior before passing; the final suite passes 2,642 checks. The main agent opened all 16 Access originals and repeated the interaction and qualitative gates.

One new fresh Terra High read-only reviewer then opened all 16 final Access originals and independently exercised the corrected selection, keyboard, revoke and Cancel paths. It returned `approve` with no finding. Relations and Publish retain their current fresh `approve` dispositions because their final pixels and contracts did not change. After all reviewer dispositions, the main agent repeated the final product/UX judgment: plain product language, professional typography, content boundaries, error/recovery truth, exact-revision visibility and bounded 2560/3840 composition pass. The product owner then reviewed the submitted 17-image batch and approved it in conversation. All 72 finite #167 reference targets are now approved and individually registered; this approval does not itself authorize production React/CSS work before the #167 PR/merge gate completes.
