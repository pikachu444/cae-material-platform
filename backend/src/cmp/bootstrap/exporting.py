"""Compose the non-production reference Solver Card service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.exporting.adapters.persistence.elastoplastic_repository import (
    SqlAlchemyElastoplasticExportingRepository,
)
from cmp.modules.exporting.adapters.persistence.repository import SqlAlchemyExportingRepository
from cmp.modules.exporting.application.elastoplastic_service import (
    ElastoplasticSolverCardService,
)
from cmp.modules.exporting.application.service import SolverCardService
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook


def build_solver_card_service(identity: IdentityServices) -> SolverCardService | None:
    """Reuse revision lifecycle/provenance/audit hooks for each immutable card revision."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return SolverCardService(
        repository=SqlAlchemyExportingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


def build_elastoplastic_solver_card_service(
    identity: IdentityServices,
    material_models: TabulatedPlasticityModelService | None,
) -> ElastoplasticSolverCardService | None:
    """Compose both bounded elastoplastic exporters over one solver-neutral IR."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or material_models is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ElastoplasticSolverCardService(
        repository=SqlAlchemyElastoplasticExportingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        material_models=material_models,
    )
