"""Compose the non-production reference Material Model IR service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.application.canonical_test_data import CanonicalTestDataService
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.modeling.adapters.persistence.calibration_repository import (
    SqlAlchemyCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.candidate_selection_repository import (
    SqlAlchemyCandidateSelectionRepository,
)
from cmp.modules.modeling.adapters.persistence.linear_viscoelasticity_repository import (
    SqlAlchemyLinearViscoelasticRepository,
)
from cmp.modules.modeling.adapters.persistence.neutral_material_repository import (
    SqlAlchemyNeutralMaterialRepository,
)
from cmp.modules.modeling.adapters.persistence.ogden_calibration_repository import (
    SqlAlchemyOgdenCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.ogden_candidate_selection_repository import (
    SqlAlchemyOgdenCandidateSelectionRepository,
)
from cmp.modules.modeling.adapters.persistence.ogden_prony_repository import (
    SqlAlchemyOgdenPronyRepository,
)
from cmp.modules.modeling.adapters.persistence.prony_calibration_repository import (
    SqlAlchemyPronyCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.prony_candidate_selection_repository import (
    SqlAlchemyPronyCandidateSelectionRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import SqlAlchemyModelingRepository
from cmp.modules.modeling.adapters.persistence.scientific_profile_repository import (
    SqlAlchemyScientificProfileRepository,
)
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
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelService,
)
from cmp.modules.modeling.application.neutral_material import NeutralMaterialService
from cmp.modules.modeling.application.ogden_calibration import (
    ReferenceOgdenCalibrationService,
)
from cmp.modules.modeling.application.ogden_candidate_promotion import (
    OgdenCandidatePromotionService,
)
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelService
from cmp.modules.modeling.application.prony_calibration import (
    ReferencePronyCalibrationService,
)
from cmp.modules.modeling.application.prony_candidate_promotion import (
    PronyCandidatePromotionService,
)
from cmp.modules.modeling.application.scientific_profile import ScientificProfileService
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
from cmp.modules.processing.application.common_outputs import CommonProcessingOutputService
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.statistics.application.replicate_outlier_service import (
    ReplicateOutlierService,
)
from cmp.modules.testing.application.service import TestingService


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


def build_linear_viscoelastic_model_service(
    identity: IdentityServices,
    material_models: MaterialModelService | None,
) -> LinearViscoelasticModelService | None:
    """Compose manual polymer/elastomer Prony IR creation over shared revision hooks."""

    if identity.engine is None or identity.rls_context is None or material_models is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return LinearViscoelasticModelService(
        repository=SqlAlchemyLinearViscoelasticRepository(
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


def build_ogden_prony_model_service(
    identity: IdentityServices,
    material_models: MaterialModelService | None,
) -> OgdenPronyModelService | None:
    """Compose the elastomer-only manual Ogden-Prony reference IR."""

    if identity.engine is None or identity.rls_context is None or material_models is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return OgdenPronyModelService(
        repository=SqlAlchemyOgdenPronyRepository(
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


def build_scientific_profile_service(
    identity: IdentityServices,
) -> ScientificProfileService | None:
    """Compose versioned family-specific scientific calibration profiles."""

    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ScientificProfileService(
        repository=SqlAlchemyScientificProfileRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        )
    )


def build_reference_ogden_calibration_service(
    identity: IdentityServices,
    profiles: ScientificProfileService | None,
    catalog: CatalogService | None,
    datasets: GovernedImportService | None,
    testing: TestingService | None,
    models: OgdenPronyModelService | None,
    artifacts: ArtifactService | None,
) -> ReferenceOgdenCalibrationService | None:
    """Compose exact governed Datasets with the bounded multi-test Ogden kernel."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or profiles is None
        or catalog is None
        or datasets is None
        or testing is None
        or models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferenceOgdenCalibrationService(
        repository=SqlAlchemyOgdenCalibrationRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        profiles=profiles,
        catalog=catalog,
        datasets=datasets,
        testing=testing,
        models=models,
        artifacts=artifacts,
    )


def build_ogden_candidate_promotion_service(
    identity: IdentityServices,
    calibrations: ReferenceOgdenCalibrationService | None,
    models: OgdenPronyModelService | None,
) -> OgdenCandidatePromotionService | None:
    """Compose human Ogden selection and repeated append-only IR promotion."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or calibrations is None
        or models is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return OgdenCandidatePromotionService(
        selections=SqlAlchemyOgdenCandidateSelectionRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        calibrations=calibrations,
        models=models,
    )


def build_neutral_material_service(
    identity: IdentityServices,
    calibrations: ReferenceOgdenCalibrationService | None,
    datasets: GovernedImportService | None,
    models: OgdenPronyModelService | None,
    artifacts: ArtifactService | None,
    tabulated_models: TabulatedPlasticityModelService | None = None,
    linear_models: LinearViscoelasticModelService | None = None,
    processing_outputs: CommonProcessingOutputService | None = None,
    test_data: CanonicalTestDataService | None = None,
    prony_calibrations: ReferencePronyCalibrationService | None = None,
    shear_datasets: ShearRelaxationDatasetService | None = None,
) -> NeutralMaterialService | None:
    """Compose T-56 selection, typed IR projection, and canonical JSON persistence."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or calibrations is None
        or datasets is None
        or models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return NeutralMaterialService(
        repository=SqlAlchemyNeutralMaterialRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        calibrations=calibrations,
        datasets=datasets,
        models=models,
        artifacts=artifacts,
        tabulated_models=tabulated_models,
        linear_models=linear_models,
        processing_outputs=processing_outputs,
        test_data=test_data,
        prony_calibrations=prony_calibrations,
        shear_datasets=shear_datasets,
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


def build_reference_prony_calibration_service(
    identity: IdentityServices,
    datasets: ShearRelaxationDatasetService | None,
    models: LinearViscoelasticModelService | None,
    artifacts: ArtifactService | None,
) -> ReferencePronyCalibrationService | None:
    """Compose processed shear data with the bounded two-term Prony adapter."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or models is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferencePronyCalibrationService(
        repository=SqlAlchemyPronyCalibrationRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        models=models,
        artifacts=artifacts,
    )


def build_prony_candidate_promotion_service(
    identity: IdentityServices,
    calibrations: ReferencePronyCalibrationService | None,
    models: LinearViscoelasticModelService | None,
) -> PronyCandidatePromotionService | None:
    """Compose explicit human Candidate Selection and append-only IR promotion."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or calibrations is None
        or models is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return PronyCandidatePromotionService(
        selections=SqlAlchemyPronyCandidateSelectionRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        calibrations=calibrations,
        models=models,
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
    processing_outputs: CommonProcessingOutputService | None = None,
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
        processing_outputs=processing_outputs,
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
