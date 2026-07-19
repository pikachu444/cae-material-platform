# T-87 Metal Fit and Extrapolate evidence

## Accepted outcome

The Metal workbench now exposes the existing public-equation engine as an engineering comparison
task instead of a generic option form:

- Voce, Swift, Hockett–Sherby and Ghosh are fitted by the server with the same normalized objective;
- the exact observed true-stress/true-plastic workup remains visible beside every candidate;
- Stress response, predicted-minus-observed Residual and numerical Tangent Modulus use the returned
  server candidate arrays and preserve each series' own sampling grid;
- relative RMSE is visible in the first viewport, while fitted values and lower/upper bounds remain
  available per candidate in the task inspector;
- the selected result is an explicit primary/secondary blend and the ratio updates through the
  cancellable server preview;
- the observed fit boundary is explicit, the unobserved region is shaded, and the selected
  extrapolated line is dashed;
- an engineering selection reason is a bounded Recipe option and is retained with the chosen
  families, ratio, fit range and maximum extrapolation strain;
- preview changes create no revision; Recipe save or immutable Processing Output commit retains the
  existing append-only boundary.

All equations are independent public reference implementations and remain `reference/non-production`.
No proprietary optimizer, parameter database or UI asset is reproduced.

## Browser evidence

- [candidate, observed evidence and bounded extrapolation](../images/t87-metal-fit-candidate-comparison.png)
- [candidate residual comparison](../images/t87-metal-fit-residual.png)

The capture script fails unless the live Docker page exposes the hardening graph, observed workup,
candidate evidence, explicit unobserved marker and residual axis. Both images use the three exact
synthetic DP780 Test Data revisions seeded into PostgreSQL.

## Numerical and interaction verification

- analytical fixtures cover all four public hardening equations;
- deterministic repeated fits preserve selected output and scalar evidence;
- hidden/unbounded extrapolation is rejected;
- frontend fixtures verify linear interpolation, predicted-minus-observed residual and tangent slope;
- the browser journey verifies real server values, not hard-coded plot arrays;
- focused Python, Vitest and production build/bundle checks pass before the full merge gate.

T-87 accepts Metal candidate comparison and bounded extrapolation usability. T-88 still owns cohesive
Neutral Material JSON review, six-state solver mapping and both native card downloads in the same task flow.
