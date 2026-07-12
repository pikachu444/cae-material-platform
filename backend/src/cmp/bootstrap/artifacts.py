"""Compose T-09/T-10 Artifact services from PostgreSQL and object storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

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
from cmp.modules.artifacts.application.content import (
    ArtifactPolicy,
    ArtifactService,
    ArtifactTransferCodec,
)
from cmp.modules.artifacts.application.uploads import (
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


def build_artifact_services(
    identity: IdentityServices,
    settings: Settings,
) -> ArtifactServices:
    if (
        identity.engine is None
        or identity.rls_context is None
        or settings.upload_storage_root is None
    ):
        return ArtifactServices(None, None)
    # The filesystem adapter is intentionally non-production. Production must select an
    # S3-compatible adapter with TLS/encryption/object-lock controls rather than silently
    # accepting a local path.
    if settings.environment == "production":
        return ArtifactServices(None, None)
    sessions = sessionmaker(
        identity.engine,
        class_=Session,
        expire_on_commit=False,
    )
    store = FilesystemMultipartObjectStore(Path(settings.upload_storage_root))
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


def build_upload_service(
    identity: IdentityServices,
    settings: Settings,
) -> UploadService | None:
    return build_artifact_services(identity, settings).upload
