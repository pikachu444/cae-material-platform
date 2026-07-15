"""Compose the non-production reference Material Model IR service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.modeling.adapters.persistence.calibration_repository import (
    SqlAlchemyCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.candidate_selection_repository import (
    SqlAlchemyCandidateSelectionRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import SqlAlchemyModelingRepository
from cmp.modules.modeling.adapters.persistence.tabulated_plasticity_repository import (
    SqlAlchemyTabulatedPlasticityRepository,
)
from cmp.modules.modeling.adapters.persistence.voce_calibration_repository import (
    SqlAlchemyVoceCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.voce_candidate_selection_repository import (
    SqlAlchemyVoceCandidateSelectionRepository,
)
from cmp.modules.modeling.application.calibration import ReferenceCalibrationService
from cmp.modules.modeling.application.candidate_selection import CandidateSelectionService
from cmp.modules.modeling.application.service import MaterialModelService
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.modeling.application.voce_calibration import (
    ReferenceVoceCalibrationService,
)
from cmp.modules.modeling.application.voce_candidate_projection import (
    VoceCandidateProjectionService,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.statistics.application.replicate_outlier_service import (
    ReplicateOutlierService,
)


def build_material_model_service(identity: IdentityServices) -> MaterialModelService | None:
    """Reuse lifecycle/provenance/audit hooks for every reference IR revision."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return MaterialModelService(
        repository=SqlAlchemyModelingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


def build_reference_calibration_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    material_models: MaterialModelService | None,
    artifacts: ArtifactService | None,
) -> ReferenceCalibrationService | None:
    """Compose the bounded non-production calibration slice from public module services."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or material_models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferenceCalibrationService(
        repository=SqlAlchemyCalibrationRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        material_models=material_models,
        artifacts=artifacts,
    )


def build_reference_voce_calibration_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    catalog: CatalogService | None,
    statistics: ReplicateOutlierService | None,
    artifacts: ArtifactService | None,
) -> ReferenceVoceCalibrationService | None:
    """Compose reviewed multi-curve inputs with the bounded SciPy reference adapter."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or catalog is None
        or statistics is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferenceVoceCalibrationService(
        repository=SqlAlchemyVoceCalibrationRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        statistics=statistics,
        datasets=datasets,
        catalog=catalog,
        artifacts=artifacts,
    )


def build_tabulated_plasticity_model_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    material_models: MaterialModelService | None,
    artifacts: ArtifactService | None,
) -> TabulatedPlasticityModelService | None:
    """Compose the explicit Dataset-to-elastoplastic-IR projection."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or material_models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return TabulatedPlasticityModelService(
        repository=SqlAlchemyTabulatedPlasticityRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        material_models=material_models,
        artifacts=artifacts,
    )


def build_candidate_selection_service(
    identity: IdentityServices,
    calibrations: ReferenceCalibrationService | None,
    material_models: MaterialModelService | None,
) -> CandidateSelectionService | None:
    """Compose T-24 human Candidate Selection without bypassing Calibration/Model services."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or calibrations is None
        or material_models is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return CandidateSelectionService(
        repository=SqlAlchemyCandidateSelectionRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        calibrations=calibrations,
        material_models=material_models,
    )


def build_voce_candidate_projection_service(
    identity: IdentityServices,
    calibrations: ReferenceVoceCalibrationService | None,
    material_models: MaterialModelService | None,
    artifacts: ArtifactService | None,
) -> VoceCandidateProjectionService | None:
    """Compose human Voce acceptance with the shared tabulated-IR persistence boundary."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or calibrations is None
        or material_models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    hooks = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        SqlAlchemyRevisionAuditHook(),
    )
    return VoceCandidateProjectionService(
        selections=SqlAlchemyVoceCandidateSelectionRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
        material_model_repository=SqlAlchemyTabulatedPlasticityRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=hooks,
        ),
        calibrations=calibrations,
        material_models=material_models,
        artifacts=artifacts,
    )
