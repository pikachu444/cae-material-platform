"""Compose the typed reference Processing service from public Dataset and Artifact ports."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.application.service import DatasetService
from cmp.modules.processing.adapters.persistence.repository import SqlAlchemyProcessingRepository
from cmp.modules.processing.application.service import ProcessingService
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
