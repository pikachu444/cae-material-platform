# T-47 production release signing identity

Status: external signer contract and local verification implemented; operator signer deployment
and live key ceremony pending.

Release-quality evidence already contains canonical SBOM, vulnerability and container-image
reports. This unit separates production identity from those bytes: the quality process never loads
a production private key. It asks an operator-provided no-shell command adapter to describe its
public identity and sign the exact canonical manifest bytes, then verifies the returned signature
locally against an independently supplied trust root.

## Trust and failure rules

- `CMP_ENVIRONMENT=production` rejects both ephemeral and PEM private-key modes. Production must use
  the external signer adapter.
- Generation requires both an expected key ID and a trusted Ed25519 public-key file. A self-declared
  key returned by the signer is insufficient.
- Describe and sign responses must retain the same algorithm and key ID. The sign response must
  attest the requested SHA-256, and the signature is verified before any manifest is published.
- The process is executed without a shell, has a bounded timeout and 64-KiB response ceiling, and
  never includes signer stderr in evidence or exception text.
- The signed manifest records algorithm, provider, key ID and public-key SHA-256. Verification can
  pin both the trusted key and expected key ID, so key substitution and ambiguous rotation fail.
- Local ephemeral signing remains a reproducibility/integrity test only. It is not builder identity
  and must not be accepted by a production release policy.

The command adapter can wrap an approved HSM, Vault Transit, cloud signing service or keyless
identity workflow. This repository intentionally does not embed provider credentials, private-key
material or a vendor-specific key API.

## External command protocol

The executable receives one canonical JSON object on stdin and returns one JSON object on stdout.
It is invoked first with `describe`, then with `sign`.

```json
{"operation":"describe","schema":"cmp.external-signing-request.v1"}
```

```json
{
  "algorithm": "Ed25519",
  "key_id": "vault:transit/cmp-release/keys/production-v1",
  "operation": "describe",
  "provider": "vault-transit",
  "public_key_pem_base64": "...",
  "schema": "cmp.external-signing-response.v1"
}
```

The sign request adds `payload_base64`, `payload_sha256`, `algorithm` and `key_id`. Its response
echoes the schema, operation, algorithm, key ID and payload SHA-256 and returns
`signature_base64`. The adapter signs the decoded payload bytes, not a re-serialized JSON object.

## Generation and verification

The JSON command array avoids shell quoting and injection. Place it last only for readability; it
is one normal option value.

```powershell
$signer = '["cmp-vault-signer","--key","cmp-release/production-v1"]'
uv run cmp-release-quality generate `
  --root . `
  --external-signer-command-json $signer `
  --trusted-public-key C:\approved\cmp-release-production-v1.pem `
  --expected-key-id vault:transit/cmp-release/keys/production-v1
```

```powershell
uv run cmp-release-quality verify `
  --bundle .cache\release-quality\<run-id> `
  --trusted-public-key C:\approved\cmp-release-production-v1.pem `
  --expected-key-id vault:transit/cmp-release/keys/production-v1
```

The signing command, trusted key and key ID are deployment inputs. The command implementation must
authenticate to its signer using the organization's workload-identity or secret-delivery policy;
do not place bearer tokens or private keys in command arguments. During rotation, approve the new
key/key-ID pair before generation, retain the old public trust record for historical bundles, and
never re-sign an existing manifest in place.

Contract tests execute a separate signer process and prove approved identity, valid signature,
untrusted-key rejection, corrupted-signature rejection and production local-key rejection. A real
production signing service, identity attestation and operator key ceremony have not been executed
in this workstation environment and remain release acceptance conditions.
