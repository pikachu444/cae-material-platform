"""Compose the typed reference Processing service from public Dataset and Artifact ports."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.datasets.application.shear_relaxation import ShearRelaxationDatasetService
from cmp.modules.datasets.application.viscoelastic_master import ViscoelasticDatasetService
from cmp.modules.processing.adapters.persistence.repository import SqlAlchemyProcessingRepository
from cmp.modules.processing.adapters.persistence.shear_relaxation_repository import (
    SqlAlchemyShearRelaxationProcessingRepository,
)
from cmp.modules.processing.adapters.persistence.viscoelastic_master_curve_repository import (
    SqlAlchemyViscoelasticMasterRepository,
)
from cmp.modules.processing.application.service import ProcessingService
from cmp.modules.processing.application.shear_relaxation import (
    ShearRelaxationProcessingService,
)
from cmp.modules.processing.application.viscoelastic_master_curve import (
    ViscoelasticMasterService,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.testing.application.service import TestingService


def build_processing_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    testing: TestingService | None,
    artifacts: ArtifactService | None,
) -> ProcessingService | None:
    """Build only when the authoritative Dataset and Artifact services are available."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or testing is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ProcessingService(
        repository=SqlAlchemyProcessingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        testing=testing,
        artifacts=artifacts,
    )


def build_shear_relaxation_processing_service(
    identity: IdentityServices,
    datasets: ShearRelaxationDatasetService | None,
    artifacts: ArtifactService | None,
) -> ShearRelaxationProcessingService | None:
    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ShearRelaxationProcessingService(
        repository=SqlAlchemyShearRelaxationProcessingRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        artifacts=artifacts,
    )


def build_viscoelastic_master_service(
    identity: IdentityServices,
    datasets: ViscoelasticDatasetService | None,
    shear_datasets: ShearRelaxationDatasetService | None,
    artifacts: ArtifactService | None,
) -> ViscoelasticMasterService | None:
    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or shear_datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ViscoelasticMasterService(
        repository=SqlAlchemyViscoelasticMasterRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        shear_datasets=shear_datasets,
        artifacts=artifacts,
    )
