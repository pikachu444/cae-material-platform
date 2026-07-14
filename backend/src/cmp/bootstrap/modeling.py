"""Compose the non-production reference Material Model IR service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.modeling.adapters.persistence.calibration_repository import (
    SqlAlchemyCalibrationRepository,
)
from cmp.modules.modeling.adapters.persistence.repository import SqlAlchemyModelingRepository
from cmp.modules.modeling.application.calibration import ReferenceCalibrationService
from cmp.modules.modeling.application.service import MaterialModelService
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook


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
