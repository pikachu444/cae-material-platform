# Issue #167 — Remaining Administration product-owner packet

Date: `2026-07-31`  
Branch: `agent/complete-167-and-157`  
Baseline: latest `issue-167-service-reference-freeze`  
Lifecycle: **main-agent accepted; independent reviewer pending; product-owner approval absent**

## Scope

This packet completes the finite 72-image service-reference inventory without changing production React, backend, API, migrations, or current user-guide screenshots. It adds the remaining 17 approval units for `ADM-SCHEMA-RELATIONS`, `ADM-ACCESS`, and `ADM-PUBLISH`, plus 45 evidence-only state captures and 10 deterministic 2560/3840 wide captures.

The publication family is intentionally blocked. The current service has no Catalog publication transition or policy endpoint, so the references preserve saved draft definitions and never fabricate a published state, receipt, release, or successful transition.

## Static source to production contract mapping

| Reference family | Static regions | Existing production component/API contract | Preserved behavior |
| --- | --- | --- | --- |
| Layout | Schema navigator → Layout list → ordered-field editor + saved Record preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Layout list/create/revise APIs | Current Table revision, exact Attribute revisions, ordered fields, draft validation, saved Record preview |
| Subset | Schema navigator → Subset list → typed filters + scoped result preview | `apps/web/src/configurable-catalog-admin.tsx`; configurable Catalog Subset list/create/revise APIs and server-scoped Record query | Filter definition, same-query total/rows, authorization scope, draft/error preservation |
| Link Type | Schema navigator → Link Type list → endpoint/label/cardinality editor + Related test | `apps/web/src/configurable-catalog-admin.tsx`; Link Type and exact Record Link APIs | Source/target Tables, independent cardinalities, forward/reverse labels, exact endpoint revisions, no latest alias |
| Access | Access navigator → assignment list → readable task preset / revoke confirmation | `apps/web/src/product-access-center.tsx`; product assignment list/grant/revoke APIs | User/Reviewer/Administrator roles, scope/classification, denied boundary, required revoke reason |
| Publish | Lifecycle navigator → saved draft change set → validation boundary | No production publication endpoint | Publish disabled, saved drafts preserved, validation/recovery only, no fabricated success |

## Approval targets

| Target | Family/state | SHA-256 |
| --- | --- | --- |
| [administration-layout-edit-draft-1366x768](../images/issue-167-service-reference/administration-layout-edit-draft-1366x768.png) | `layout` / `draft` | `c82f9c7a43c0e086218816082eaf1881a2e4d672882d792fc4eb79aa33eaa7e7` |
| [administration-layout-edit-draft-1440x900](../images/issue-167-service-reference/administration-layout-edit-draft-1440x900.png) | `layout` / `draft` | `bf6377f0c9bd4ac9076fc5b6583a8671fea00cd941f06c6faabd6a5bd1d8f16f` |
| [administration-layout-edit-draft-1920x1080](../images/issue-167-service-reference/administration-layout-edit-draft-1920x1080.png) | `layout` / `draft` | `e4dbd3a0ebf01b2270dc9670d04963f22f728f00c4151dcdd39dd04f2527fd23` |
| [administration-subset-edit-draft-1366x768](../images/issue-167-service-reference/administration-subset-edit-draft-1366x768.png) | `subset` / `draft` | `d047fbf5204bae67681f0c4663f2732920a4b0a063680597695dcefc4a91137c` |
| [administration-subset-edit-draft-1440x900](../images/issue-167-service-reference/administration-subset-edit-draft-1440x900.png) | `subset` / `draft` | `bf93f96d807e9a4766f9a2f645bda0ebfb83b08890c62bcc943d8b86894c2122` |
| [administration-subset-edit-draft-1920x1080](../images/issue-167-service-reference/administration-subset-edit-draft-1920x1080.png) | `subset` / `draft` | `6349535e69692c86a07a9d4424c5f97cf8fa093d431b754894cbd05fa871780b` |
| [administration-link-type-edit-draft-1366x768](../images/issue-167-service-reference/administration-link-type-edit-draft-1366x768.png) | `link` / `draft` | `d07cbd0f99f049ea01fc7acc9041cb12f3d059ed4513923dd9a8d383cfdb8e0b` |
| [administration-link-type-edit-draft-1440x900](../images/issue-167-service-reference/administration-link-type-edit-draft-1440x900.png) | `link` / `draft` | `29cb0b45b2cbc418928860baf6ef6ec2f73422ef15ed2ac6b219186ec49b8421` |
| [administration-link-type-edit-draft-1920x1080](../images/issue-167-service-reference/administration-link-type-edit-draft-1920x1080.png) | `link` / `draft` | `c69ab99c8ed55ffcabc56b8cb2f23368c41e36b02c5b993074eb001fcf548450` |
| [administration-access-normal-1366x768](../images/issue-167-service-reference/administration-access-normal-1366x768.png) | `access` / `normal` | `b2562dbb6df24c19aa226d3f4bcb4fbc623b94a7d83f65973901ae4be36ef528` |
| [administration-access-normal-1440x900](../images/issue-167-service-reference/administration-access-normal-1440x900.png) | `access` / `normal` | `0b76852380eb166e335abbfd5945a00e506becf678757ce0c83898821c432806` |
| [administration-access-normal-1920x1080](../images/issue-167-service-reference/administration-access-normal-1920x1080.png) | `access` / `normal` | `893745491e80309fd9fc7ae5623ba0778cc1f6072a3e8571f0706dab42243eaa` |
| [administration-access-denied-1440x900](../images/issue-167-service-reference/administration-access-denied-1440x900.png) | `access` / `denied` | `8981bed572ecc8f4757980a33a547e4c431634b1c3b5b7abc48976c23dc912e8` |
| [administration-access-revoke-confirm-1440x900](../images/issue-167-service-reference/administration-access-revoke-confirm-1440x900.png) | `access` / `revoke-confirm` | `84bbb7af0d70832ef547a1e99269bce6242a565b629bb04d71481a96c5526d81` |
| [administration-publish-blocked-1366x768](../images/issue-167-service-reference/administration-publish-blocked-1366x768.png) | `publish` / `blocked` | `3bdeb595aff942f0b560fe77101d611d3de5c1056cdb6293705828e3cdbd02ac` |
| [administration-publish-blocked-1440x900](../images/issue-167-service-reference/administration-publish-blocked-1440x900.png) | `publish` / `blocked` | `9dfb80c19d2450a8c351e18f165ff37ecc7fb61a2574323ac704d9b472e251dc` |
| [administration-publish-blocked-1920x1080](../images/issue-167-service-reference/administration-publish-blocked-1920x1080.png) | `publish` / `blocked` | `b7da7e5f567fd77b4bbd54403bf7ae980dc0de3fe604c9c169da1e0f0c267f1b` |

## Deterministic evidence

```text
approval targets                                      17 / 17
evidence-only states                                  15 families / 45 images
wide evidence                                         10 images
exact viewport and SHA checks                          pass
browser console/page errors                            0 / 0
page horizontal/vertical overflow                      0 / 0
nested interactive controls                            0
prohibited legacy selectors                            0
active filled primary commands                         <= 1 per state
body/data typography                                   <= 13.5 px
keyboard splitter and Ctrl+S/revoke interactions        pass
family-specific truth and recovery checks               pass
WAVE-06 validator                                       1480 checks / pass
service-reference inventory                             72 total; 55 approved; 17 pending
```

The main agent opened the canonical approval images at original resolution and checked the three-pane topology, dense list/editor relationship, text containment, command priority, preview continuity, and wide-screen bounded task cluster. The 17 targets remain `pending` until explicit product-owner approval. No product-owner approval is inferred from the request to implement this work.

A fresh Terra/Luna reviewer was not callable from this execution surface. No substitute review is claimed. The deterministic evidence and product-owner packet are therefore preserved with reviewer lifecycle still pending.
