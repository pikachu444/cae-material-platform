"""Exercise a real governed S3 adapter and emit redacted immutable-control evidence."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cmp.bootstrap.artifacts import build_object_store
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.storage.s3 import S3GovernedObjectStore
from cmp.modules.artifacts.domain.uploads import ObjectStoreError
from cmp.shared.domain.revisions import canonical_json_bytes

_PATTERN = hashlib.sha256(b"cmp-governed-storage-acceptance-v1").digest()
_CHUNK_BYTES = 1024 * 1024
_MAXIMUM_PAYLOAD_BYTES = 512 * 1024 * 1024


class GovernedStorageAcceptanceError(RuntimeError):
    """Live governed storage did not satisfy the production-pilot gate."""


def deterministic_chunks(size_bytes: int) -> Iterator[bytes]:
    if not 0 < size_bytes <= _MAXIMUM_PAYLOAD_BYTES:
        raise GovernedStorageAcceptanceError("acceptance payload is outside the safe bound")
    remaining = size_bytes
    block = (_PATTERN * ((_CHUNK_BYTES // len(_PATTERN)) + 1))[:_CHUNK_BYTES]
    while remaining:
        observed = min(remaining, len(block))
        yield block[:observed]
        remaining -= observed


def deterministic_digest(size_bytes: int) -> str:
    digest = hashlib.sha256()
    for chunk in deterministic_chunks(size_bytes):
        digest.update(chunk)
    return digest.hexdigest()


async def run_acceptance(
    store: S3GovernedObjectStore,
    *,
    payload_size_bytes: int,
    source_commit: str,
) -> dict[str, object]:
    """Run the write/read/retention gate against an already composed real adapter."""

    started_at = datetime.now(UTC)
    run_id = uuid4().hex
    expected_sha256 = deterministic_digest(payload_size_bytes)
    staging_key = f"staging/acceptance/{run_id}.bin"
    final_key = f"final/acceptance/{run_id}/{expected_sha256}.bin"

    async def chunks() -> AsyncIterator[bytes]:
        for chunk in deterministic_chunks(payload_size_bytes):
            await asyncio.sleep(0)
            yield chunk

    bucket_governance = await asyncio.to_thread(store.validate_bucket_governance)
    staged = await store.stage_stream(
        object_key=staging_key,
        chunks=chunks(),
        media_type="application/octet-stream",
        expected_sha256=expected_sha256,
        expected_size_bytes=payload_size_bytes,
    )
    promoted = await store.promote(
        source_key=staged.object_key,
        target_key=final_key,
        expected_sha256=expected_sha256,
        expected_size_bytes=payload_size_bytes,
    )
    observed_digest = hashlib.sha256()
    observed_size = 0
    async for chunk in store.stream(final_key):
        observed_digest.update(chunk)
        observed_size += len(chunk)
    if observed_size != payload_size_bytes or observed_digest.hexdigest() != expected_sha256:
        raise GovernedStorageAcceptanceError("retained object differs after independent download")
    objects = await store.list_objects(f"final/acceptance/{run_id}/")
    if len(objects) != 1 or objects[0] != promoted:
        raise GovernedStorageAcceptanceError("retained object is not uniquely discoverable")
    deletion_rejected = False
    try:
        await store.discard(final_key)
    except ObjectStoreError:
        deletion_rejected = True
    if not deletion_rejected:
        raise GovernedStorageAcceptanceError("final object deletion was not rejected")
    governance = await store.governance_evidence(final_key)
    ended_at = datetime.now(UTC)
    return {
        "bucket_governance": bucket_governance,
        "completed_at": ended_at.isoformat(),
        "duration_seconds": (ended_at - started_at).total_seconds(),
        "final_object": {
            "deletion_rejected": deletion_rejected,
            "governance": governance,
            "logical_key_sha256": hashlib.sha256(final_key.encode()).hexdigest(),
            "sha256": promoted.sha256,
            "size_bytes": promoted.size_bytes,
            "version_id_sha256": hashlib.sha256(promoted.version_id.encode()).hexdigest(),
        },
        "passed": True,
        "schema": "cmp.governed-storage-acceptance.v1",
        "source_commit": source_commit,
        "started_at": started_at.isoformat(),
    }


def _source_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or len(value) != 40:
        raise GovernedStorageAcceptanceError("source commit could not be resolved")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--payload-bytes", type=int, default=0)
    parser.add_argument("--acknowledge-retained-test-object", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not args.acknowledge_retained_test_object:
        raise GovernedStorageAcceptanceError(
            "--acknowledge-retained-test-object is required because the test creates "
            "a locked object"
        )
    settings = Settings.from_environment()
    if settings.environment != "production" or settings.object_store_backend.lower() != "s3":
        raise GovernedStorageAcceptanceError(
            "live acceptance requires CMP_ENVIRONMENT=production and the s3 adapter"
        )
    configured_part_size = max(settings.upload_part_bytes, 5 * 1024 * 1024)
    payload_size = args.payload_bytes or (2 * configured_part_size + 173)
    if payload_size <= configured_part_size:
        raise GovernedStorageAcceptanceError(
            "acceptance payload must cross the configured multipart boundary"
        )
    root = args.root.resolve(strict=True)
    store = build_object_store(settings)
    if not isinstance(store, S3GovernedObjectStore):
        raise GovernedStorageAcceptanceError("governed S3 adapter was not composed")
    report = asyncio.run(
        run_acceptance(
            store,
            payload_size_bytes=payload_size,
            source_commit=_source_commit(root),
        )
    )
    output: Path = args.output or (
        root
        / ".cache"
        / "governed-storage-acceptance"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        / "report.json"
    )
    if output.exists():
        raise GovernedStorageAcceptanceError("acceptance report already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(report)
    output.write_bytes(payload)
    print(
        json.dumps(
            {
                "passed": True,
                "report": str(output.resolve()),
                "report_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
