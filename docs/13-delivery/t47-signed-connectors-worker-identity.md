# T-47 signed connectors and worker identity rotation

Status: transport contracts, worker composition and unit acceptance implemented; live external
receiver and production identity-provider acceptance pending.

This unit delivers existing immutable transactional-outbox CloudEvents. It does not add a
Teamcenter/PLM schema, mutate Material/Dataset/IR/card revisions or make a connector the system of
record. PostgreSQL `events.outbox_event` remains authoritative and `events.outbox_delivery` retains
attempt, lease, failure/poison and published-time evidence.

## Signed delivery contract

Every delivery wraps the canonical CloudEvent in `cmp.signed-event-delivery.v1`. The signed
manifest includes connector kind/audience, event data SHA-256 and external signer algorithm,
provider, key ID and public-key digest. The detached Ed25519 signature and signed-manifest digest
are then placed in one canonical transport body. Event ID is the receiver idempotency key.

Supported production-pilot transports are deliberately narrow:

- `rest` and `webhook` send an HTTPS POST with no URL credentials/query/fragment. Redirects are not
  followed. A receiver accepts only by returning 2xx and `X-CMP-Accepted-Digest` equal to the exact
  body SHA-256. A mismatched acknowledgement is rejected rather than silently published.
- `object_storage` writes the exact signed body through the configured immutable object-store port
  under organization/project/event/digest-scoped keys. Replay resolves to the same final bytes.
- 4xx receiver rejection (except 429) is typed separately from temporary transport failure. The
  existing leased outbox retry/poison policy owns bounded retry and stale-worker fencing.

Both REST and webhook use the same byte/security contract; their semantic difference is the
receiver workflow, not an alternate event schema. Proprietary PLM mappings and credentials remain
out of scope.

## Worker and credential rotation

The worker now reads `CMP_WORKER_ACCESS_TOKEN_FILE` on every queue cycle. A sidecar or workload
identity agent can atomically replace that file without process restart. The reader rejects
symlinks, non-files, oversized/non-ASCII values and whitespace-bearing tokens. Production rejects
the legacy inline `CMP_WORKER_ACCESS_TOKEN`.

HTTP connector bearer credentials use the same rotating-file boundary and are read on every
delivery. Do not put bearer values in URLs, command arguments, logs or environment variables. The
external event signer uses the independently pinned command/public-key/key-ID contract from
`t47-production-signing.md`; worker/API processes never load its private key.

```dotenv
CMP_WORKER_ACCESS_TOKEN_FILE=/run/secrets/cmp-worker.token
CMP_EVENT_CONNECTOR_KIND=webhook
CMP_EVENT_CONNECTOR_ENDPOINT=https://receiver.example.com/cmp/events
CMP_EVENT_CONNECTOR_BEARER_TOKEN_FILE=/run/secrets/cmp-receiver.token
CMP_EVENT_SIGNER_COMMAND_JSON=["cmp-vault-signer","--key","cmp-events/production-v1"]
CMP_EVENT_SIGNER_TRUSTED_PUBLIC_KEY=/run/trust/cmp-events-production-v1.pem
CMP_EVENT_SIGNER_EXPECTED_KEY_ID=vault:transit/cmp-events/keys/production-v1
CMP_EVENT_SIGNER_TIMEOUT_SECONDS=30
```

Use `rest`, `webhook`, `object_storage` or `none`. Plain HTTP is available only for an explicitly
enabled loopback development receiver and is forbidden in production.

## Acceptance and remaining evidence

Unit tests verify deterministic/verifiable signatures, rotating bearer values, digest-bound HTTP
acknowledgement, endpoint credential/HTTP rejection, immutable object replay, rotating worker
identity and production inline-token rejection. Existing outbox tests verify lease, retry, poison,
ordering and published receipts.

A production acceptance must still deploy the external signer and OIDC/workload-identity sidecar,
rotate both worker and receiver tokens during active delivery, send duplicate event IDs to the real
receiver, verify one side effect plus matching accepted digest, and exercise receiver outage/retry.
No external endpoint or production IdP credential was available on this workstation, so that live
claim remains pending.
