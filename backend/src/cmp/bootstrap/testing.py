"""Compose the typed reference testing service from shared PostgreSQL hooks."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.testing.adapters.persistence.repository import SqlAlchemyTestingRepository
from cmp.modules.testing.adapters.persistence.test_context_repository import (
    SqlAlchemyTestContextRepository,
)
from cmp.modules.testing.application.service import TestingService
from cmp.modules.testing.application.test_context import TestContextService


def build_testing_service(
    identity: IdentityServices,
    artifacts: ArtifactService | None = None,
) -> TestingService | None:
    """Reuse lifecycle, provenance, and audit hooks for every testing revision."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return TestingService(
        repository=SqlAlchemyTestingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        artifacts=artifacts,
    )


def build_test_context_service(identity: IdentityServices) -> TestContextService | None:
    """Compose the typed execution-context capability over the shared revision kernel."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return TestContextService(
        repository=SqlAlchemyTestContextRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )
