# T-55M selected Processing Output to solver cards evidence

Verified on `2026-07-18` against the Docker Compose API, PostgreSQL 16 and connected React UI.

- Exact Processing Output identity: `d97041a6-d9f0-4b53-98dc-8d967912c777`
- Exact Processing Output revision: `b3644458-1799-4fbc-bdd9-48a8230fefc3`
- Output SHA-256: `b9ef93207432e754c1a5f6122f848302533d988c3c7fa28ef957f7dd5ee57896`
- Exact source Test Data revision: `54a3b805-ad50-41e0-843e-f4b3ff4601f0`
- Exact Mapping Profile revision: `8948d217-0772-427f-9fde-14740d100b60`
- Promoted Material Model identity: `70298535-3283-4ed3-ac10-2a7b4ad5aee7`
- Promoted Material Model revision: `4080a694-876d-483f-8b70-89db47fa6610`
- Model family: `urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0`
- Hardening Artifact: 101 points over true plastic strain `[0, 0.5]`
- Candidate selection: `0.5 * Swift + 0.5 * Voce`; observed fitting maximum `0.1`
- OpenRadioss card: `/MAT/LAW36`, native `.rad`, SHA-256
  `42ec90d652f64bc345a40daed995ca5f5353d67937049ce824b986ab67e77034`
- Abaqus card: `*DENSITY`, `*ELASTIC`, `*PLASTIC`, native `.inp`, SHA-256
  `f2bb8ce70ddd372d1fd1097c22e6504258df23bbbe7de4da0399ac1ebc4431e1`

The mapping reports contained only `exact`, `transformed`, `approximated` and `not_applicable`;
the bounded extrapolation was not silent. Preview and download were exercised through the public API
and the UI listed both native cards from the same immutable IR. The fixture is synthetic and
reference/non-production; this evidence does not claim solver execution or material qualification.
