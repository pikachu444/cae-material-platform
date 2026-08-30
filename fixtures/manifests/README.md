# Fixture manifests

Future fixtures must record source, owner, license, classification, and digest.

- [`metal-hardening-reference-v1.yaml`](metal-hardening-reference-v1.yaml): provenance,
  classification, retention, generation procedure, and SHA-256 for the metal hardening reference.
- [`linear-viscoelastic-abaqus-reference-v1.yaml`](linear-viscoelastic-abaqus-reference-v1.yaml):
  complete synthetic static properties and Prony terms for repeatable Abaqus material-card export;
  it never supplements a public experiment.
- [`dma-temperature-sweep-linear-viscoelastic-v1.yaml`](dma-temperature-sweep-linear-viscoelastic-v1.yaml):
  closed-form fixed-frequency DMA temperature sweep, explicit tabulated shift factors, Prony truth,
  and the linked Abaqus export reference for repeatable end-to-end numerical acceptance.
- [`public-viscoelastic-darus-smp-v1.1.yaml`](public-viscoelastic-darus-smp-v1.1.yaml):
  DaRUS shape-memory-polymer DMA, master-curve, and shift-factor source members and their
  exact-temperature calibration eligibility.
- [`public-viscoelastic-vitrimer-v1.0.yaml`](public-viscoelastic-vitrimer-v1.0.yaml):
  Zenodo vitrimer DMA, normalized relaxation, Arrhenius, and tensile source members. Missing
  absolute relaxation modulus and static properties remain explicit export blockers.

Validate one or more public archives without importing them into the product database:

```powershell
uv run python scripts/verify_public_material_test_data.py `
  --manifest fixtures/manifests/public-viscoelastic-darus-smp-v1.1.yaml `
  --manifest fixtures/manifests/public-viscoelastic-vitrimer-v1.0.yaml
```

