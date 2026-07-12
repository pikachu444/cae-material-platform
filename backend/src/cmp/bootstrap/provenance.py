"""Compose the T-13 provenance query service from the authoritative PostgreSQL store."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
)
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.application.service import ProvenanceService


@dataclass(frozen=True, slots=True)
class ProvenanceServices:
    entity: ProvenanceService | None
    lineage: ProvenanceLineageService | None


def build_provenance_services(identity: IdentityServices) -> ProvenanceServices:
    if identity.engine is None or identity.rls_context is None:
        return ProvenanceServices(None, None)
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    repository = SqlAlchemyProvenanceRepository(
        session_factory=sessions,
        rls_context=identity.rls_context,
    )
    return ProvenanceServices(
        entity=ProvenanceService(repository=repository),
        lineage=ProvenanceLineageService(repository=repository),
    )
