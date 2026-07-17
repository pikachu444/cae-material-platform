"""Compose the typed Material Catalog vertical slice from shared PostgreSQL services."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.adapters.persistence.configurable import (
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.repository import SqlAlchemyCatalogRepository
from cmp.modules.catalog.application.configurable import ConfigurableCatalogService
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
