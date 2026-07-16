"""Compose T-09/T-10 Artifact services from PostgreSQL and object storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.persistence.content import (
    SqlAlchemyArtifactRepository,
)
from cmp.modules.artifacts.adapters.persistence.uploads import (
    SqlAlchemyUploadRepository,
)
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.adapters.storage.s3 import (
    S3GovernancePolicy,
    S3GovernedObjectStore,
)
from cmp.modules.artifacts.application.content import (
    ArtifactPolicy,
    ArtifactService,
    ArtifactTransferCodec,
    ContentObjectStore,
)
from cmp.modules.artifacts.application.uploads import (
    MultipartObjectStore,
    UploadCapabilityCodec,
    UploadPolicy,
    UploadService,
)
from cmp.modules.jobs.adapters.persistence.artifact_events import (
    SqlArtifactAvailableOutboxHook,
)


@dataclass(frozen=True, slots=True)
class ArtifactServices:
    upload: UploadService | None
    content: ArtifactService | None


class ArtifactObjectStore(MultipartObjectStore, ContentObjectStore, Protocol):
    """Storage composition contract shared by upload and Artifact services."""


def build_artifact_services(
    identity: IdentityServices,
    settings: Settings,
) -> ArtifactServices:
    if identity.engine is None or identity.rls_context is None:
        return ArtifactServices(None, None)
    store = build_object_store(settings)
    if store is None:
        return ArtifactServices(None, None)
    sessions = sessionmaker(
        identity.engine,
        class_=Session,
        expire_on_commit=False,
    )
    content: ArtifactService | None = None
    if settings.artifact_transfer_secret is not None:
        content = ArtifactService(
            repository=SqlAlchemyArtifactRepository(
                session_factory=sessions,
                rls_context=identity.rls_context,
                available_hooks=(SqlArtifactAvailableOutboxHook(),),
            ),
            object_store=store,
            transfers=ArtifactTransferCodec(settings.artifact_transfer_secret.encode("utf-8")),
            policy=ArtifactPolicy(
                transfer_ttl=timedelta(seconds=settings.artifact_transfer_ttl_seconds)
            ),
        )
    upload: UploadService | None = None
    if settings.upload_capability_secret is not None:
        upload = UploadService(
            repository=SqlAlchemyUploadRepository(
                session_factory=sessions,
                rls_context=identity.rls_context,
            ),
            object_store=store,
            capabilities=UploadCapabilityCodec(settings.upload_capability_secret.encode("utf-8")),
            raw_asset_finalizer=content,
            policy=UploadPolicy(
                max_object_bytes=settings.upload_max_object_bytes,
                default_part_bytes=settings.upload_part_bytes,
                session_ttl=timedelta(seconds=settings.upload_session_ttl_seconds),
            ),
        )
    return ArtifactServices(upload, content)


def build_object_store(
    settings: Settings,
) -> ArtifactObjectStore | None:
    backend = settings.object_store_backend.strip().lower()
    if backend == "filesystem":
        if settings.environment == "production":
            raise ValueError("production must configure the governed S3 object-store adapter")
        if settings.upload_storage_root is None:
            return None
        return FilesystemMultipartObjectStore(Path(settings.upload_storage_root))
    if backend != "s3":
        raise ValueError("CMP_OBJECT_STORE_BACKEND must be filesystem or s3")
    if settings.s3_bucket is None or settings.s3_kms_key_id is None:
        raise ValueError("the governed S3 adapter requires bucket and KMS key identity")
    if settings.environment == "production" and settings.s3_endpoint_url is not None:
        if not settings.s3_endpoint_url.startswith("https://"):
            raise ValueError("production S3-compatible endpoints must use HTTPS")
    boto3: Any = import_module("boto3")
    botocore_config: Any = import_module("botocore.config")
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        config=botocore_config.Config(
            signature_version="s3v4",
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )
    policy = S3GovernancePolicy(
        bucket=settings.s3_bucket,
        expected_bucket_owner=settings.s3_expected_bucket_owner,
        kms_key_id=settings.s3_kms_key_id,
        prefix=settings.s3_prefix,
        retention_days=settings.s3_retention_days,
        retention_mode=settings.s3_retention_mode,
        part_size_bytes=max(settings.upload_part_bytes, 5 * 1024 * 1024),
    )
    store = S3GovernedObjectStore(client, policy)
    store.validate_bucket_governance()
    return store


def build_upload_service(
    identity: IdentityServices,
    settings: Settings,
) -> UploadService | None:
    return build_artifact_services(identity, settings).upload
