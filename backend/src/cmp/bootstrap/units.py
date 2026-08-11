"""Compose the common unit service without selecting a production Unit Profile."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.units.adapters.persistence.profiles import SqlAlchemyUnitProfileRepository
from cmp.modules.units.application.profiles import CommonUnitService


def build_common_unit_service(identity: IdentityServices) -> CommonUnitService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return CommonUnitService(
        repository=SqlAlchemyUnitProfileRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


__all__ = ["build_common_unit_service"]
