# T-86 Metal Prepare direct-manipulation evidence

## Accepted outcome

The Metal Prepare workspace now keeps the exact curve list, ordered Recipe steps, persistent engineering
plot and guided task panel visible together at 1440×900. It is not a JSON-form demonstration:

- each exact tensile revision can be included or excluded from replicate statistics without deleting it;
- crop, scale/shift, linear resampling, moving average, Savitzky–Golay and spline options use guided controls;
- range selections update crop, elastic, proof and hardening domains in the Recipe draft;
- point selection on the necking stage writes an explicit manual boundary into the downstream plastic Workup;
- elastic fit and proof/necking results are rendered as plot overlays or markers from server scalar results;
- replicate alignment, mean and 95% mean-confidence band run on the server and replace the primary plot view;
- replicate statistics apply only common row/curve preprocessing and do not re-run constitutive fitting;
- option changes remain ephemeral until a new Recipe revision or immutable Processing Output is saved.

## Clean demo fixture

`scripts/seed_full_demo.py` creates three distinct synthetic DP780 canonical Test Data revisions. The
replicates preserve separate identities, specimen/lot metadata and source digests. The primary UI selects
two exact revisions by default so **Add mean & band** is immediately demonstrable.

## Browser evidence

- [guided Metal Prepare workbench](../images/t86-metal-prepare-workbench.png)
- [replicate mean and confidence band](../images/t86-metal-replicate-statistics.png)

The Docker browser journey selected an elastic stage and an x-domain, then calculated two exact replicate
curves on a 21-point observed-domain intersection. Both members, their mean and the confidence band were
visible in the main engineering graph; the source revisions remained addressable in the left rail.

## Verification

- focused Vitest for the Workbench and engineering plot;
- TypeScript production build and bundle budget;
- idempotent full-demo seed against live PostgreSQL/API;
- live Docker browser calculation and 1440×900 screenshots;
- full frontend, Python and PostgreSQL regression remain the merge gate for the checkpoint.

T-86 accepts Metal preparation usability only. Candidate residual/derivative comparison and reviewed
extrapolation selection remain T-87; in-workbench Neutral/Card delivery remains T-88.
