# T-55M hardening candidate evidence

Verified on `2026-07-18` against the real Docker Compose API, PostgreSQL and React workbench.

- Route: `/datasets/processing`
- Exact Test Data: `DP600-T55M-12PT`, revision 1
  (`6891f91a-f4f2-4bc8-b976-6e8f09444903`)
- Exact Mapping Profile revision: `77ae40ab-3f23-42b0-b7a6-bd28388cef93`
- Processing Recipe identity: `fd9171ab-8d77-4319-9a80-3e94ed030a2e`
- Published Recipe revision 4: `55182183-eda6-4503-bb5d-fd5e10be8bf9`
- Batch: `7d37d8c3-27c9-4d00-8eee-30fefa078699`
- Successful Attempt: `034e2237-46e2-481e-af5b-4c490c4eb441`
- Immutable Output revision: `b3644458-1799-4fbc-bdd9-48a8230fefc3`
- Output SHA-256:
  `b9ef93207432e754c1a5f6122f848302533d988c3c7fa28ef957f7dd5ee57896`
- Final output: 101 points over plastic strain `[0, 0.5]`; observed fit domain is
  `[0.0001, 0.1]` and `(0.1, 0.5]` is explicitly diagnosed as extrapolated.
- Candidate families: Voce, Swift, Hockett--Sherby and Ghosh.
- Selection: `0.5 * Swift + 0.5 * Voce`.

The UI screenshot records all seven pipeline stages, the four candidate series, the selected
combination, diagnostics and scalar results. The server rejects non-SI normalized quantities,
implicit extrapolation, non-positive/non-monotone predictions and invalid family/domain choices.
Recipe r4 and the Output preserve the options and every fitted parameter's
lower/initial/fitted/upper values; the source Test Data and earlier Recipe revisions remain unchanged.
