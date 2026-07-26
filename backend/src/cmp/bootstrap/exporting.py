"""Compose the non-production reference Solver Card service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.bootstrap.settings import Settings
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.exporting.adapters.persistence.bulk_export_repository import (
    SqlAlchemyBulkExportRepository,
)
from cmp.modules.exporting.adapters.persistence.bulk_export_sources import (
    SqlAlchemyBulkExportSourceResolver,
)
from cmp.modules.exporting.adapters.persistence.elastoplastic_repository import (
    SqlAlchemyElastoplasticExportingRepository,
)
from cmp.modules.exporting.adapters.persistence.linear_viscoelastic_repository import (
    SqlAlchemyLinearViscoelasticExportingRepository,
)
from cmp.modules.exporting.adapters.persistence.neutral_hyperelastic_repository import (
    SqlAlchemyNeutralHyperelasticExportingRepository,
)
from cmp.modules.exporting.adapters.persistence.ogden_prony_repository import (
    SqlAlchemyOgdenPronyExportingRepository,
)
from cmp.modules.exporting.adapters.persistence.repository import SqlAlchemyExportingRepository
from cmp.modules.exporting.adapters.persistence.target_delivery_receipts import (
    SqlTargetDeliveryReceiptRecorder,
)
from cmp.modules.exporting.application.bulk_export import BulkExportPolicy, BulkExportService
from cmp.modules.exporting.application.elastoplastic_service import (
    ElastoplasticSolverCardService,
)
from cmp.modules.exporting.application.linear_viscoelastic_service import (
    LinearViscoelasticSolverCardService,
)
from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    NeutralHyperelasticSolverCardService,
)
from cmp.modules.exporting.application.ogden_prony_service import OgdenPronySolverCardService
from cmp.modules.exporting.application.service import SolverCardService
from cmp.modules.exporting.application.target_delivery import DeliveryReceiptRecorder
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.neutral_material import NeutralMaterialService
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook


def build_bulk_export_service(
    identity: IdentityServices,
    artifacts: ArtifactService | None,
    settings: Settings | None = None,
) -> BulkExportService | None:
    """Compose immutable typed selections and deterministic bundle assembly."""

    if identity.engine is None or identity.rls_context is None or artifacts is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    policy = (
        BulkExportPolicy(
            inline_assembly_maximum_bytes=settings.bulk_export_inline_maximum_bytes,
            external_member_maximum_bytes=(settings.bulk_export_external_member_maximum_bytes),
            external_job_lease_seconds=settings.bulk_export_job_lease_seconds,
        )
        if settings is not None
        else None
    )
    return BulkExportService(
        repository=SqlAlchemyBulkExportRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        sources=SqlAlchemyBulkExportSourceResolver(
            session_factory=sessions,
            rls_context=identity.rls_context,
            artifacts=artifacts,
        ),
        artifacts=artifacts,
        policy=policy,
    )


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

    if identity.engine is None or identity.rls_context is None or material_models is None:
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


def build_linear_viscoelastic_solver_card_service(
    identity: IdentityServices,
    material_models: LinearViscoelasticModelService | None,
) -> LinearViscoelasticSolverCardService | None:
    """Compose the bounded Abaqus Prony exporter over the typed reference IR."""

    if identity.engine is None or identity.rls_context is None or material_models is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return LinearViscoelasticSolverCardService(
        repository=SqlAlchemyLinearViscoelasticExportingRepository(
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


def build_ogden_prony_solver_card_service(
    identity: IdentityServices,
    material_models: OgdenPronyModelService | None,
) -> OgdenPronySolverCardService | None:
    """Compose Abaqus Ogden-Prony and OpenRadioss LAW62 exporters."""

    if identity.engine is None or identity.rls_context is None or material_models is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return OgdenPronySolverCardService(
        repository=SqlAlchemyOgdenPronyExportingRepository(
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


def build_neutral_hyperelastic_solver_card_service(
    identity: IdentityServices,
    neutral_materials: NeutralMaterialService | None,
) -> NeutralHyperelasticSolverCardService | None:
    """Compose versioned Abaqus/OpenRadioss exporters over canonical Neutral JSON."""

    if identity.engine is None or identity.rls_context is None or neutral_materials is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return NeutralHyperelasticSolverCardService(
        repository=SqlAlchemyNeutralHyperelasticExportingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        neutral_materials=neutral_materials,
    )


def build_target_delivery_receipt_recorder(
    identity: IdentityServices,
) -> DeliveryReceiptRecorder | None:
    """Compose the read/write receipt adapter over the same tenant RLS context."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return SqlTargetDeliveryReceiptRecorder(
        session_factory=sessions,
        rls_context=identity.rls_context,
    )
