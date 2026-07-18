"""Compose the typed Material Catalog vertical slice from shared PostgreSQL services."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.links import SqlAlchemyCatalogLinkRepository
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.adapters.persistence.repository import SqlAlchemyCatalogRepository
from cmp.modules.catalog.application.configurable import ConfigurableCatalogService
from cmp.modules.catalog.application.links import CatalogLinkService
from cmp.modules.catalog.application.records import CatalogRecordService
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook


def build_catalog_service(identity: IdentityServices) -> CatalogService | None:
    """Wire generic lifecycle, provenance, and audit hooks into typed catalog revisions."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return CatalogService(
        repository=SqlAlchemyCatalogRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


def build_configurable_catalog_service(
    identity: IdentityServices,
) -> ConfigurableCatalogService | None:
    """Wire the administrator-defined schema aggregates to the same governed hooks."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ConfigurableCatalogService(
        repository=SqlAlchemyConfigurableCatalogRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


def build_catalog_record_service(identity: IdentityServices) -> CatalogRecordService | None:
    """Wire configurable Folder/Record revisions to schema definitions and typed values."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    hooks = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        SqlAlchemyRevisionAuditHook(),
    )
    schema_repository = SqlAlchemyConfigurableCatalogRepository(
        session_factory=sessions,
        rls_context=identity.rls_context,
        revision_hooks=hooks,
    )
    return CatalogRecordService(
        repository=SqlAlchemyCatalogRecordRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
        schema_repository=schema_repository,
    )


def build_catalog_link_service(identity: IdentityServices) -> CatalogLinkService | None:
    """Wire dual explorers and exact-revision links to the configurable Catalog stores."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    hooks = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        SqlAlchemyRevisionAuditHook(),
    )
    return CatalogLinkService(
        repository=SqlAlchemyCatalogLinkRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
        schema_repository=SqlAlchemyConfigurableCatalogRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
        record_repository=SqlAlchemyCatalogRecordRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
    )
