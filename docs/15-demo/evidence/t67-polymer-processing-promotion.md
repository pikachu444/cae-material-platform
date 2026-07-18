# T-67 reviewed polymer Processing Output promotion evidence

Date: `2026-07-19`

The clean Compose demo uses public synthetic T-60 relaxation data. It commits a common Processing
Output whose final step is `polymer.prony_fit_compare` version 1, with candidate term counts 1--4
and `automatic_bic` selection. The server re-exported the immutable Output Artifact and promoted the
selected three-term response only after an explicit catalog-G0 mismatch review.

Exact live objects verified through the protected API and PostgreSQL-backed application are:

| Object | Exact identity/revision |
| --- | --- |
| Canonical Test Data | `e076b961-c148-445c-be56-c4ee90d37685` r1 |
| Processing Output | `2cfc3108-3618-444c-96bc-c35329291446` r1 |
| Generalized-Maxwell IR | `38ee5225-f451-40ce-94f9-557cc99ce1b4` r1 |
| Neutral Material JSON | `bdbc87ce-8024-4d82-a871-efa3efa40028` r1 |
| Abaqus native card | `12047cb3-e1ae-4dea-b58d-6bc1ea124fb1` r1 |

The selected Output contains three ordered shear-Prony terms. The UI restored normalized RMSE
`0.002094` and catalog-versus-fitted instantaneous shear-modulus mismatch `0.09%`; those values are
read-only evidence, not form-supplied coefficients. The downloaded Abaqus card SHA-256 was
`48d8d535394bf0c01bbfd02eefbad98d90a863b955c141406d65e95326778f7f` and contains
`*VISCOELASTIC, TIME=PRONY`. OpenRadioss linear viscoelasticity remains an explicit unsupported
mapping and no LAW62 approximation was introduced.

This statement records the T-67 boundary at capture time. T-68 subsequently added the distinct,
conditional LAW1 + LPRONY path documented in `t68-openradioss-lprony.md`; LAW62 remains forbidden.

The two screenshots were captured from the live in-app browser at
`http://127.0.0.1:5173/materials/4e2adbd3-1f4d-4bc1-b03f-d4fe3947c462/models` after authenticating
with the local demo identity. They contain synthetic data only and are not production-material
qualification evidence.
