# Synthetic fixtures

Only synthetic, non-confidential data may be committed here.

- `tensile-toe-zero-intercept-v1.json` contains explicit, non-production strain/stress
  references for the issue #212 OLS zero-intercept regression and replay gates.

- [`metal-hardening-reference-v1.json`](metal-hardening-reference-v1.json): deterministic,
  non-production Voce, Swift, Hockett–Sherby, and Altair 2025 Ghosh stress/tangent references.

- [`dma-temperature-sweep-linear-viscoelastic-v1.json`](dma-temperature-sweep-linear-viscoelastic-v1.json):
  fixed-frequency DMA temperature sweep with explicit tabulated shifts, closed-form generalized
  Maxwell truth, serialized fit policy, and a linked Abaqus golden card.
- [`linear-viscoelastic-abaqus-reference-v1.json`](linear-viscoelastic-abaqus-reference-v1.json):
  complete synthetic isotropic static properties and normalized Prony terms used to verify a
  reusable Abaqus material-card export without supplementing public experiments.

