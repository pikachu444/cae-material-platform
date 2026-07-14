"""Compose the T-30 reference release service from shared PostgreSQL services."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.review_release.adapters.persistence.release_repository import (
    SqlAlchemyReleaseRepository,
)
from cmp.modules.review_release.application.release_service import ReleaseService


def build_release_service(identity: IdentityServices) -> ReleaseService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReleaseService(
        repository=SqlAlchemyReleaseRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
        )
    )
