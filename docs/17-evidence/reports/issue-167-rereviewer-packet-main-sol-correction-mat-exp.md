# #167 fresh review packet — MAT-EXP direct correction

Date: 2026-07-30
Mode: bounded read-only review

Follow the reviewer role and workflow defined by `AGENTS.md`, `.codex/config.toml` and the configured
reviewer agent file. Do not edit files.

## Acceptance under review

1. Pointer or Enter selection of a Materials tree `Record` selects the matching result and updates
   the selected-material identity, grade, description, family, status and status-bar context.
2. Non-Record tree selection does not fabricate or replace material context.
3. Result selection and Open datasheet behavior remain intact.
4. Normal tree identities remain complete and genuine overflow retains discoverable local rails.
5. Approved long/empty exceptional evidence remains frozen and the exceptional validator no longer
   treats replaced normal images as frozen.

## Required original-resolution images

| Image | SHA-256 |
| --- | --- |
| `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1366x768.png` | `cca897729caeb457bc19635b55a1ae55a56525b6ffd1ab76fcce0ad72c35f53e` |
| `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1440x900.png` | `9315da065f39e4ca9d92b1b8192c171aae3595a5bcc82ce49607f0398ec00ecc` |
| `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.png` | `b8f515eccb3b3a85798edd20302d7d517969262eec25e4711af686f852060486` |
| `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.wide-evidence-2560x1440.png` | `ac8009b61eadbbb0555434396d13c438d3696f9bcaff841adb3ac021d7fd9703` |
| `docs/17-evidence/images/issue-167-service-reference/materials-search-normal-1920x1080.wide-evidence-3840x2160.png` | `87f5ac36ae52cb43184f02ead70305645c7b3a94a931cc1282189c4b2cf00a44` |

## Implementation and evidence

- packet:
  `docs/17-evidence/reports/issue-167-main-sol-direct-correction-packet-materials-admin.md`;
- implementation:
  `materials-search-normal.html`, `reference.js`;
- browser evidence:
  `capture_reference.py` and the three normal `*.measurements.json` files;
- deterministic contracts:
  `validate_reference.py`, `validate_materials_search_wave03.py`;
- lifecycle/evidence:
  `docs/01-product/service-reference-manifest.yaml`,
  `docs/17-evidence/reports/issue-167-service-reference-freeze.md` §60.

Rerun the three normal validators with expected main-agent status `accepted`, the 1920 wide evidence
gate and the exceptional all-packet validator with measurement status `pending`. Inspect the
pointer/keyboard synchronization fields in each measurement file. Complete every applicable
Q-01–Q-20 item before V-01–V-16 scoring. Return actionable findings first and then exactly
`approve` or `changes_requested`.
