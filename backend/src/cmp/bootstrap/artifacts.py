"""Compose T-09 uploads from PostgreSQL RLS and a development object-store adapter."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.adapters.persistence.uploads import (
    SqlAlchemyUploadRepository,
)
from cmp.modules.artifacts.adapters.storage.filesystem import (
    FilesystemMultipartObjectStore,
)
from cmp.modules.artifacts.application.uploads import (
    UploadCapabilityCodec,
    UploadPolicy,
    UploadService,
)


def build_upload_service(
    identity: IdentityServices,
    settings: Settings,
) -> UploadService | None:
    if (
        identity.engine is None
        or identity.rls_context is None
        or settings.upload_storage_root is None
        or settings.upload_capability_secret is None
    ):
        return None
    # The filesystem adapter is intentionally non-production. Production must select an
    # S3-compatible adapter with TLS/encryption/object-lock controls rather than silently
    # accepting a local path.
    if settings.environment == "production":
        return None
    sessions = sessionmaker(
        identity.engine,
        class_=Session,
        expire_on_commit=False,
    )
    repository = SqlAlchemyUploadRepository(
        session_factory=sessions,
        rls_context=identity.rls_context,
    )
    policy = UploadPolicy(
        max_object_bytes=settings.upload_max_object_bytes,
        default_part_bytes=settings.upload_part_bytes,
        session_ttl=timedelta(seconds=settings.upload_session_ttl_seconds),
    )
    return UploadService(
        repository=repository,
        object_store=FilesystemMultipartObjectStore(
            Path(settings.upload_storage_root)
        ),
        capabilities=UploadCapabilityCodec(
            settings.upload_capability_secret.encode("utf-8")
        ),
        policy=policy,
    )
