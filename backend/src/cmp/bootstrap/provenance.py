"""Compose the T-13 provenance query service from the authoritative PostgreSQL store."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
)
from cmp.modules.provenance.application.service import ProvenanceService


def build_provenance_service(identity: IdentityServices) -> ProvenanceService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ProvenanceService(
        repository=SqlAlchemyProvenanceRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
        )
    )
