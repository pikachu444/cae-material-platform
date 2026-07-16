from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import pytest
from cmp.bootstrap.artifacts import _build_object_store
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.storage.s3 import (
    S3GovernancePolicy,
    S3GovernedObjectStore,
)
from cmp.modules.artifacts.domain.uploads import ObjectStoreError

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
BUCKET = "cmp-production-artifacts"
KMS_KEY = "arn:aws:kms:ap-northeast-2:123456789012:key/cmp-artifacts"


class _S3Error(Exception):
    def __init__(self, code: str) -> None:
        self.response = {"Error": {"Code": code}}
        super().__init__(code)


class _FakeS3:
    def __init__(self) -> None:
        self.versioning = "Enabled"
        self.lock_enabled = "Enabled"
        self.kms_key_id = KMS_KEY
        self.objects: dict[str, dict[str, Any]] = {}
        self.uploads: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._version = 0

    def _record(self, operation: str, values: dict[str, Any]) -> None:
        self.calls.append((operation, values.copy()))

    def _store(self, key: str, body: bytes, values: dict[str, Any]) -> dict[str, str]:
        self._version += 1
        version = f"v{self._version}"
        etag = hashlib.md5(body, usedforsecurity=False).hexdigest()
        self.objects[key] = {
            "Body": body,
            "ContentLength": len(body),
            "ETag": f'"{etag}"',
            "VersionId": version,
            "Metadata": values.get("Metadata", {}),
            "ServerSideEncryption": values.get("ServerSideEncryption"),
            "SSEKMSKeyId": values.get("SSEKMSKeyId"),
            "ObjectLockMode": values.get("ObjectLockMode"),
            "ObjectLockRetainUntilDate": values.get("ObjectLockRetainUntilDate"),
        }
        return {"ETag": f'"{etag}"', "VersionId": version}

    def get_bucket_versioning(self, **values: Any) -> dict[str, str]:
        self._record("get_bucket_versioning", values)
        return {"Status": self.versioning}

    def get_object_lock_configuration(self, **values: Any) -> dict[str, Any]:
        self._record("get_object_lock_configuration", values)
        return {"ObjectLockConfiguration": {"ObjectLockEnabled": self.lock_enabled}}

    def get_bucket_encryption(self, **values: Any) -> dict[str, Any]:
        self._record("get_bucket_encryption", values)
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": self.kms_key_id,
                        }
                    }
                ]
            }
        }

    def put_object(self, **values: Any) -> dict[str, str]:
        self._record("put_object", values)
        key = str(values["Key"])
        if values.get("IfNoneMatch") == "*" and key in self.objects:
            raise _S3Error("PreconditionFailed")
        raw_body = values["Body"]
        body = raw_body.read() if callable(getattr(raw_body, "read", None)) else raw_body
        return self._store(key, bytes(body), values)

    def head_object(self, **values: Any) -> dict[str, Any]:
        self._record("head_object", values)
        record = self.objects.get(str(values["Key"]))
        if record is None:
            raise _S3Error("NoSuchKey")
        return {key: value for key, value in record.items() if key != "Body"}

    def get_object(self, **values: Any) -> dict[str, BytesIO]:
        self._record("get_object", values)
        record = self.objects.get(str(values["Key"]))
        if record is None:
            raise _S3Error("NoSuchKey")
        return {"Body": BytesIO(record["Body"])}

    def copy_object(self, **values: Any) -> dict[str, str]:
        self._record("copy_object", values)
        source = values["CopySource"]
        record = self.objects.get(str(source["Key"]))
        if record is None or record["VersionId"] != source["VersionId"]:
            raise _S3Error("NoSuchVersion")
        return self._store(str(values["Key"]), record["Body"], values)

    def delete_object(self, **values: Any) -> dict[str, bool]:
        self._record("delete_object", values)
        key = str(values["Key"])
        record = self.objects.get(key)
        if record is not None and record["VersionId"] == values["VersionId"]:
            del self.objects[key]
        return {"DeleteMarker": True}

    def create_multipart_upload(self, **values: Any) -> dict[str, str]:
        self._record("create_multipart_upload", values)
        upload_id = f"upload-{len(self.uploads) + 1}"
        self.uploads[upload_id] = {"request": values, "parts": {}}
        return {"UploadId": upload_id}

    def upload_part(self, **values: Any) -> dict[str, str]:
        self._record("upload_part", values)
        upload = self.uploads[str(values["UploadId"])]
        body = bytes(values["Body"])
        upload["parts"][int(values["PartNumber"])] = body
        etag = hashlib.md5(body, usedforsecurity=False).hexdigest()
        return {"ETag": f'"{etag}"'}

    def complete_multipart_upload(self, **values: Any) -> dict[str, str]:
        self._record("complete_multipart_upload", values)
        upload = self.uploads.pop(str(values["UploadId"]))
        body = b"".join(upload["parts"][number] for number in sorted(upload["parts"]))
        request = upload["request"] | values
        return self._store(str(values["Key"]), body, request)

    def abort_multipart_upload(self, **values: Any) -> dict[str, bool]:
        self._record("abort_multipart_upload", values)
        self.uploads.pop(str(values["UploadId"]), None)
        return {"Aborted": True}

    def list_objects_v2(self, **values: Any) -> dict[str, Any]:
        self._record("list_objects_v2", values)
        prefix = str(values["Prefix"])
        return {
            "Contents": [{"Key": key} for key in self.objects if key.startswith(prefix)],
            "IsTruncated": False,
        }


def _store(client: _FakeS3) -> S3GovernedObjectStore:
    return S3GovernedObjectStore(
        client,
        S3GovernancePolicy(
            bucket=BUCKET,
            kms_key_id=KMS_KEY,
            retention_days=3650,
            expected_bucket_owner="123456789012",
        ),
        clock=lambda: NOW,
    )


def test_s3_policy_and_bootstrap_fail_closed_for_unsafe_production_storage() -> None:
    with pytest.raises(ValueError, match="canonical"):
        S3GovernancePolicy(BUCKET, KMS_KEY, 3650, prefix="/cmp")
    with pytest.raises(ValueError, match="governed S3"):
        _build_object_store(Settings(environment="production"))
    with pytest.raises(ValueError, match="HTTPS"):
        _build_object_store(
            Settings(
                environment="production",
                object_store_backend="s3",
                s3_endpoint_url="http://storage.example.test",
                s3_bucket=BUCKET,
                s3_kms_key_id=KMS_KEY,
            )
        )


def test_s3_governance_validation_requires_versioning_lock_and_exact_kms_key() -> None:
    client = _FakeS3()
    store = _store(client)

    evidence = store.validate_bucket_governance()

    assert evidence["versioning"] == "Enabled"
    assert evidence["object_lock_enabled"] is True
    client.versioning = "Suspended"
    with pytest.raises(ObjectStoreError, match="versioning"):
        store.validate_bucket_governance()
    client.versioning = "Enabled"
    client.kms_key_id = "arn:aws:kms:other"
    with pytest.raises(ObjectStoreError, match="configured KMS"):
        store.validate_bucket_governance()


def test_s3_promotion_applies_kms_and_compliance_retention_and_preserves_bytes() -> None:
    client = _FakeS3()
    store = _store(client)
    value = b"immutable solver-card evidence"
    digest = hashlib.sha256(value).hexdigest()

    async def run() -> None:
        staged = await store.stage_bytes(
            object_key="staging/org/project/card.k",
            value=value,
            media_type="text/plain",
        )
        promoted = await store.promote(
            source_key=staged.object_key,
            target_key="final/org/project/card.k",
            expected_sha256=digest,
            expected_size_bytes=len(value),
        )
        observed = b"".join([chunk async for chunk in store.stream(promoted.object_key)])
        assert observed == value
        assert await store.inspect(staged.object_key) is None
        with pytest.raises(ObjectStoreError, match="non-authoritative staging"):
            await store.discard(promoted.object_key)

    asyncio.run(run())
    final = client.objects["cmp/final/org/project/card.k"]
    assert final["ServerSideEncryption"] == "aws:kms"
    assert final["SSEKMSKeyId"] == KMS_KEY
    assert final["ObjectLockMode"] == "COMPLIANCE"
    assert final["ObjectLockRetainUntilDate"] > NOW
    assert final["Metadata"] == {"cmp-sha256": digest}
    final_put = next(
        values
        for operation, values in client.calls
        if operation == "put_object" and values["Key"].startswith("cmp/final/")
    )
    assert final_put["IfNoneMatch"] == "*"
    assert final_put["ChecksumSHA256"]


def test_s3_multipart_upload_sends_part_checksums_and_verifies_completed_bytes() -> None:
    client = _FakeS3()
    store = _store(client)
    value = b"first-partsecond-part"

    async def chunks(part: bytes) -> AsyncIterator[bytes]:
        yield part[:3]
        yield part[3:]

    async def run() -> None:
        key = "staging/org/project/raw.bin"
        upload_id = await store.initiate(key, "application/octet-stream")
        first = await store.upload_part(
            object_key=key,
            upload_id=upload_id,
            part_number=1,
            chunks=chunks(b"first-part"),
            expected_size=len(b"first-part"),
        )
        second = await store.upload_part(
            object_key=key,
            upload_id=upload_id,
            part_number=2,
            chunks=chunks(b"second-part"),
            expected_size=len(b"second-part"),
        )
        completed = await store.complete(
            object_key=key,
            upload_id=upload_id,
            parts=(first, second),
        )
        assert completed.sha256 == hashlib.sha256(value).hexdigest()
        assert completed.size_bytes == len(value)

    asyncio.run(run())
    part_calls = [values for operation, values in client.calls if operation == "upload_part"]
    assert len(part_calls) == 2
    assert all("ChecksumSHA256" in values for values in part_calls)
    initiated = next(
        values for operation, values in client.calls if operation == "create_multipart_upload"
    )
    assert initiated["ServerSideEncryption"] == "aws:kms"
    assert initiated["ChecksumAlgorithm"] == "SHA256"
