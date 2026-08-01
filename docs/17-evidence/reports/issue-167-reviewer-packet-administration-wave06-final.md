# Issue #167 — WAVE-06 final fresh reviewer packet

Date: `2026-08-01`
Branch: `agent/complete-167-and-157`
Role: fresh configured Terra High, read-only
Decision requested: `approve` or `reject` with concrete, image-specific findings

## Review boundary

Review the complete final WAVE-06 static reference bundle for:

- `ADM-SCHEMA-RELATIONS`: Layout, Subset and Link Type
- `ADM-ACCESS`: normal, denied, revoke-confirm and recovery states
- `ADM-PUBLISH`: truthful not-configured boundary and recovery states

This is static reference review only. Do not edit files, approve production React/CSS, infer product-
owner approval, commit, push or start another issue. Ignore conclusions from earlier reviewers; inspect
the current files and pixels independently.

## Authoritative acceptance

- GitHub issue: `https://github.com/pikachu444/cae-material-platform/issues/167`
- Product/UI contract:
  `docs/01-product/desktop-engineering-ui-product-spec.md`
- Structural and mandatory qualitative gate:
  `docs/01-product/visual-acceptance-matrix.md`
- Owner-authorized implementer packet:
  `docs/17-evidence/reports/issue-167-owner-authorized-third-correction-packet-adm-language-typography-luna.md`
- Current handoff and hashes:
  `docs/17-evidence/reports/issue-167-administration-remaining-product-owner-packet.md`
- Full finite inventory and history:
  `docs/17-evidence/reports/issue-167-service-reference-freeze.md`

The final result must use plain Administrator language and the established product vocabulary. Visible
UI must not expose implementation-facing terms such as identity-provider, feature grants, server-
scoped query, pinned/latest alias, service/capability boundary, endpoint/policy implementation prose,
UUID/hash/checksum or similar internal evidence language. Governed Administrator objects such as
Table, Attribute, Layout, Subset, Link Type, Record, Revision and Cardinality are allowed and expected.

Data rows and editable values should read near 13px; metadata/help/status should read 11.5–12px;
ordinary text must not use heading weight. Review overall professional cohesion, not only numeric
compliance. Reject awkward density, fragmented prose, arbitrary badges/cards, misleading controls,
clipped identities, hidden values, accidental whitespace between related components or high-resolution
stretching/filler.

## Implementation and evidence paths

- Static source:
  - `docs/00-research/ux-service-reference/administration-remaining.html`
  - `docs/00-research/ux-service-reference/administration-schema-core.css`
  - `docs/00-research/ux-service-reference/administration-remaining.css`
  - `docs/00-research/ux-service-reference/administration-remaining.js`
- Capture and deterministic validation:
  - `docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py`
  - `docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py`
  - `docs/00-research/ux-service-reference/administration-remaining-wave06.staging.json`
- Lifecycle manifest:
  `docs/01-product/service-reference-manifest.yaml`
- Every final PNG and measurement JSON:
  `docs/17-evidence/images/issue-167-service-reference/administration-{layout,subset,link-type,access,publish}*`

The staging JSON is the exact 72-capture index: 17 owner-approval targets, 45 evidence-only state
captures and 10 wide captures. Open all 72 PNGs at original resolution. Do not review a montage or
thumbnail as a substitute.

## Registered owner-approval targets

| Target | SHA-256 |
| --- | --- |
| `administration-layout-edit-draft-1366x768.png` | `83b33ba1a8fe4dd7f9e68d532781b348373f67f5b7fb581c2195b8b670dd7e38` |
| `administration-layout-edit-draft-1440x900.png` | `c644c810f9bf09521e638500db6bc2ea79de9052e5ed99abef9aa9e4823e8899` |
| `administration-layout-edit-draft-1920x1080.png` | `2b8feeced8fe13f26c00d5c0d84f46e823ce7e952276b664ecfa6363c200c1ec` |
| `administration-subset-edit-draft-1366x768.png` | `ebb696e2198c2ee809bcbc3a96537624296879146489e0686c8fda6897ae571c` |
| `administration-subset-edit-draft-1440x900.png` | `2944564a8bfb23b56547e9fe5a5b7bbe4d90225d8b25191d10cdc760e0bebf0f` |
| `administration-subset-edit-draft-1920x1080.png` | `3c47bd6bfce907fb552e1d420f0595592b14fd443897726fa4f0a22d7d9aadcd` |
| `administration-link-type-edit-draft-1366x768.png` | `a45ce72250ae6abd4590aa236cacc31ad7d0b68bfe2596fc3764cb9eb3d9fb3b` |
| `administration-link-type-edit-draft-1440x900.png` | `b1d8eae9026501b63103592fb50ceaed9d65c1876b01041d713d2f320110876d` |
| `administration-link-type-edit-draft-1920x1080.png` | `b6cc86a9255c1f1afb9e70feac549a3b6b376192e36f8f3ff5e67fea197a19ce` |
| `administration-access-normal-1366x768.png` | `76aa2c7b7457e42cb6afaee775efdaadb396c67bdfb51c0d8c049bf32b4262b8` |
| `administration-access-normal-1440x900.png` | `d29cefa9daf262f0a74ae924ba2a45cce82d4ed41e8c847c4850400515b939fa` |
| `administration-access-normal-1920x1080.png` | `8a8be47905e2af0e6eb24ce03c3140d15280604ae007a7af28d14dd4063c94c2` |
| `administration-access-denied-1440x900.png` | `71a9a09ebc2adcfdbfea56d009a5f8cdcb6e10098c2d51d4e5ccec298826ac51` |
| `administration-access-revoke-confirm-1440x900.png` | `c42857301a53219e05e2c810ddeb3accca96d346c6c198c0c92964cb57622171` |
| `administration-publish-blocked-1366x768.png` | `422bf607c3488ef2f24b325bb8eac9b1bc5c1d8bd9bdf8f20c876991a69c8ea9` |
| `administration-publish-blocked-1440x900.png` | `893e7dce8bfea50a48390e56b2eb31b16839b6e116687600a123a0a121d5008a` |
| `administration-publish-blocked-1920x1080.png` | `15d79a5708930be1793cbe7336f066196362d4793a48dfcc2176df10034b5b0d` |

## Independent checks

Run these from the repository root and record exact outcomes:

```powershell
node --check docs/00-research/ux-service-reference/administration-remaining.js
python -m ruff check docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python -m py_compile docs/00-research/ux-service-reference/capture_administration_remaining_wave06.py docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py
python docs/00-research/ux-service-reference/validate_administration_remaining_wave06.py --all-packet-targets
python docs/00-research/ux-service-reference/validate_service_reference_inventory.py
git diff --check
```

Main-agent evidence before review is `PASS: 2642 checks across 72 captures`; inventory is 72 total,
55 approved and 17 pending. Recompute rather than copying this result.

## Mandatory independent qualitative gate

Complete V-01–V-16 and Q-01–Q-20 from the matrix with pass/fail/not-applicable and direct image/source
evidence. In addition, explicitly answer:

1. Does every visible term make sense to an Administrator without requiring implementation knowledge?
2. Are data, metadata, controls and headings typographically consistent and professionally compact?
3. Is there any overlap, boundary collision, partial glyph, avoidable truncation or visually corrupt
   header/status area at any canonical or exceptional viewport?
4. In all Link Type rows, including the three 1366 states, are complete `r4`/`r5` revision values
   visible with right clearance? Confirm the new validator would reject the former clipped layout.
5. Do Layout, Subset and Link Type preserve exact revisions, selectable non-default rows, keyboard
   navigation and truthful saved-draft/recovery continuity?
6. Do Access denial and revocation show only necessary product language, safe recovery and one bounded
   destructive action?
7. Does Publish remain truthfully unavailable without fabricated release state or internal service
   jargon?
8. At 2560 and 3840, is the complete working cluster left/top aligned and content-bounded, with unused
   space only after the task rather than inside related components? Confirm there is no forced table,
   graph or pane stretching and no filler added merely to occupy the viewport.

Reject any applicable qualitative failure regardless of the numeric score or deterministic pass.
Return a concise final disposition with findings ordered by severity and exact file/image references.
