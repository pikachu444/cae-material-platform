"""Compose the T-05 audit read service from the authoritative PostgreSQL store."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyAuditRepository
from cmp.modules.audit.application.service import AuditService


def build_audit_service(identity: IdentityServices) -> AuditService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return AuditService(
        repository=SqlAlchemyAuditRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
        )
    )
