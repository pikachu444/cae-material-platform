# Release-quality evidence

This gate produces a reviewable, signed evidence bundle for one source commit and the exact local
container image IDs selected for delivery. It does not upload source, images, SBOMs, or scan reports.

## Generate the bundle

Build all release targets first:

```powershell
docker compose -f deploy/compose/docker-compose.demo.yml --profile operations build api worker web restore-drill
uv run cmp-release-quality generate --root . --ephemeral-local-key
```

The default output is `.cache/release-quality/<UTC timestamp>/` and contains:

- production Python and Node CycloneDX SBOMs;
- `uv audit` and `npm audit` reports;
- CycloneDX SBOM and Trivy HIGH/CRITICAL report for API, worker, web and restore images;
- the exact source commit, image IDs, tool versions and policy result in canonical
  `quality-manifest.json`;
- detached Ed25519 signature and public key.

The policy fails on any known Python vulnerability, any critical npm vulnerability, any critical
container finding, a failed audit command, or malformed scanner output. HIGH image findings remain
visible in the signed report and require release review; they are not silently discarded.

The implementation uses the official [uv CycloneDX export](https://docs.astral.sh/uv/concepts/projects/export/),
[npm SBOM](https://docs.npmjs.com/cli/v11/commands/npm-sbom/),
[npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit/) and
[Trivy image/SBOM scanner](https://trivy.dev/docs/dev/guide/supply-chain/sbom/) interfaces. Trivy is
pinned by both version and image digest.

## Verify and establish trust

An ephemeral local key proves that the manifest and evidence files have not been substituted after
this invocation. It is deliberately labelled `ephemeral_local` and does **not** establish builder
identity or production trust.

```powershell
uv run cmp-release-quality verify --bundle .cache/release-quality/<run-id>
```

For a controlled pilot, provide an unencrypted PKCS#8 Ed25519 private key through a protected CI
secret mount, retain its public key as the release trust root, and verify against that exact key:

```powershell
uv run cmp-release-quality generate --root . --private-key C:\secure\release-signing-key.pem
uv run cmp-release-quality verify --bundle .cache/release-quality/<run-id> `
  --trusted-public-key C:\secure\release-public-key.pem
```

Verification rejects non-canonical manifests, invalid signatures, a different trusted key, unsafe
or duplicate paths, symlinks, size drift and SHA-256 substitution. Production KMS/keyless signing,
certificate identity and transparency-log policy remain T-47 work; the local Ed25519 mechanism must
not be described as equivalent to a production signing service. For the future keyless adapter,
follow the official [Sigstore verification model](https://docs.sigstore.dev/cosign/verifying/verify/).

## Frontend budget

`npm run build --workspace @cmp/web` lazy-loads domain workbenches and fails when the initial entry
exceeds 300,000 bytes or any lazy JavaScript chunk exceeds 120,000 bytes. Override variables are for
explicit benchmark experiments only; increasing a committed budget requires review and updated
performance evidence.
