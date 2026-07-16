# T-47 governed object-storage adapter

Status: adapter and contract tests implemented; live infrastructure qualification pending.

This unit replaces the production filesystem fallback with an explicit S3-compatible boundary.
It does not change Material, Dataset, IR, card or provenance identities. PostgreSQL remains the
metadata authority, while raw and derived bytes remain immutable Artifact objects.

## Storage invariants

- `staging/` objects are non-authoritative, encrypted working copies. They may be removed by the
  reconciliation/retention process.
- `final/` objects are written with SHA-256 evidence, `If-None-Match: *`, SSE-KMS and an explicit
  Object Lock retain-until date. A final object is never deleted through the application port.
- Versioning, Object Lock and exact default KMS-key identity are inspected during composition. A
  missing, suspended or mismatched control fails startup rather than selecting a weaker adapter.
- Every write and read can pin the configured 12-digit bucket owner. Logical keys are canonical
  POSIX paths below one configured prefix; traversal and alternate separators are rejected.
- Multipart uploads send SHA-256 part checksums and verify the completed object by streaming the
  authoritative bytes. No Artifact digest is trusted from an ETag.
- Promotion reads the exact staging version and performs a conditional final `PutObject`. A race
  succeeds only when the already-created final object has the same digest and size.

The current conditional promotion supports objects up to the S3 single-PUT limit of 5,000,000,000
bytes. This covers the qualified 2-GiB production-pilot upload. The domain-level 5-GiB Bundle
ceiling remains explicit but is not yet qualified with this adapter; multipart conditional final
promotion is required before advertising that upper bound in production.

## Required environment

```dotenv
CMP_ENVIRONMENT=production
CMP_OBJECT_STORE_BACKEND=s3
CMP_S3_REGION=ap-northeast-2
CMP_S3_BUCKET=cmp-production-artifacts
CMP_S3_PREFIX=cmp
CMP_S3_EXPECTED_BUCKET_OWNER=123456789012
CMP_S3_KMS_KEY_ID=arn:aws:kms:ap-northeast-2:123456789012:key/replace-me
CMP_S3_RETENTION_DAYS=3650
CMP_S3_RETENTION_MODE=COMPLIANCE
```

`CMP_S3_ENDPOINT_URL` is optional for AWS S3. A compatible private endpoint must use HTTPS in
production. `CMP_S3_KMS_KEY_ID` must use the same resolved key identity returned by bucket
encryption and object metadata; do not mix an alias in one location and an ARN in another.

The runtime role needs the narrow bucket/prefix operations used by the adapter: bucket versioning,
encryption and Object Lock inspection; object get/head/list/put/delete-version for staging;
multipart create/upload/complete/abort; and the KMS data-key/decrypt permissions needed by the
provider. It must not receive Object Lock bypass or final-object delete authority. Infrastructure
provisioning remains outside the application process.

## Provisioning and acceptance

1. Create the bucket with Object Lock enabled and enable versioning. Object Lock cannot be treated
   as an after-the-fact application flag.
2. Configure default SSE-KMS with the exact approved customer-managed key.
3. Configure the organization-approved default retention mode and period. The application still
   supplies retention on each final write so a missing bucket default cannot silently weaken it.
4. Apply TLS, private-network, role and KMS policies. Separate staging cleanup permission from final
   retention administration.
5. Start API and worker with the same storage configuration. Startup must fail on any governance
   mismatch.
6. Run the live T-47 storage acceptance in the target account, record bucket/key aliases without
   secrets, verify an immutable final digest/version/retention date, and exercise an independently
   managed object-storage interruption and recovery.

Unit tests use an in-memory SDK double to prove request shape, checksum, conditional write,
retention, encryption and fail-closed behavior. They are not evidence that a cloud account, KMS
policy, WORM compliance control or independent failover has passed. Live qualification is blocked
until deployment credentials and an approved bucket/KMS endpoint are supplied.

Primary provider references:

- [Amazon S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)
- [Amazon S3 Object Lock retention](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock-managing.html)
- [Boto3 multipart upload contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/create_multipart_upload.html)
