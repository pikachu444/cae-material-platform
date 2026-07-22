# T-65 clean-demo product journey evidence

Date: `2026-07-18`

## Proven path

A clean `cmp-local-demo` PostgreSQL volume was migrated to
`20260913_078_t65_binding_rls` and seeded only through protected product APIs. The seed created:

- one canonical 12-point `cmp.test-data` tensile revision;
- one exact Mapping Profile and a published revision of a three-step Processing Recipe;
- one successful Batch and immutable selected Processing Output;
- one selected tabulated-plasticity Material Model IR and canonical Neutral Material JSON;
- Abaqus and OpenRadioss mapping reports and native ASCII cards from that same Neutral revision;
- a deterministic nine-component bundle with `manifest.json`, `checksums.sha256` and `README.txt`;
- eight exact-revision Workflow Explorer nodes from Material through both native cards.

Migration 078 changes only the database target validator used by the closed domain-binding trigger.
It executes the fully scoped existence checks as the function owner so target-module RLS cannot hide a
valid cross-module revision. It returns no target data, keeps same organization/project/classification
checks and leaves caller authorization on the binding API intact.

## Download verification

The protected verifier downloaded the exact Test JSON, Neutral JSON, Abaqus `.inp`, OpenRadioss
`.rad` and governed ZIP. The clean run reported:

- Abaqus card SHA-256: `92b8829d1bbe57dca137b3864948e824d0ea897f7bea940567c53d802af15b49`
- OpenRadioss card SHA-256: `586212afc82789f6232f58c840adb21183231bdab8ba0b5f46fcd03ccc50bc7a`
- Bulk ZIP SHA-256: `54b88a6ae96518e14c1698ec2536111886fb8c36eadd3a45e4c1b2ef49c329b1`
- Bulk component count: `9`

Playwright then repeated both exact card downloads and used the connected Exports UI to download the
ZIP. Both scenarios passed and recomputed the committed SHA-256 values.

## GUI evidence

![T-65 exact governed downloads](../images/t65-clean-demo-downloads.png)

The reproducible capture script is
`docs/17-evidence/capture-scripts/capture_t65_demo.mjs`; the user procedure is
`docs/user-guide/17-clean-demo-download-validation.md`. These artifacts prove the bounded reference
journey, not actual Abaqus/OpenRadioss execution or production material qualification.
