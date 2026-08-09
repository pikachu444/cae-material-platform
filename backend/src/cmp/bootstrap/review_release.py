"""Compose the T-29 governance review service from shared PostgreSQL services."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.review_release.adapters.persistence.evidence import (
    SqlAlchemyReviewSubjectResolver,
)
from cmp.modules.review_release.adapters.persistence.publication import (
    SqlAlchemyReviewApprovalProjector,
)
from cmp.modules.review_release.adapters.persistence.repository import SqlAlchemyReviewRepository
from cmp.modules.review_release.application.service import ReviewService
from cmp.modules.review_release.domain.evidence import (
    LegacyReviewSubjectResolver,
    ReviewSubjectEvidenceRegistry,
)


def build_review_service(identity: IdentityServices) -> ReviewService | None:
    if identity.engine is None or identity.rls_context is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    registry = ReviewSubjectEvidenceRegistry((LegacyReviewSubjectResolver(),))
    for subject_type in (
        "catalog.material",
        "catalog.configurable_record",
        "datasets.test_data_document",
        "modeling.material_model",
        "exporting.solver_card",
        "exporting.neutral_solver_card",
    ):
        registry.register(
            SqlAlchemyReviewSubjectResolver(
                subject_type=subject_type,
                session_factory=sessions,
                rls_context=identity.rls_context,
            )
        )
    return ReviewService(
        repository=SqlAlchemyReviewRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            approval_projector=SqlAlchemyReviewApprovalProjector(),
        ),
        evidence_registry=registry,
    )
