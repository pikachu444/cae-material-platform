"""Compose typed reference Statistics/QC with Dataset, Artifact, audit, and provenance ports."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.application.service import (
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetService,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyRevisionProvenanceHook,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    activity_table as provenance_activity_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    association_table as provenance_association_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    derivation_table as provenance_derivation_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    entity_table as provenance_entity_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    generation_table as provenance_generation_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    usage_table as provenance_usage_table,
)
from cmp.modules.provenance.domain.model import EntityReferenceKind, ProvenanceConflict
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.statistics.adapters.persistence.replicate_outlier_repository import (
    SqlAlchemyReplicateOutlierRepository,
)
from cmp.modules.statistics.adapters.persistence.replicate_repository import (
    SqlAlchemyReplicateStatisticsRepository,
)
from cmp.modules.statistics.adapters.persistence.replicate_repository import (
    plan_revision_table as replicate_plan_revision_table,
)
from cmp.modules.statistics.adapters.persistence.replicate_repository import (
    result_revision_table as replicate_result_revision_table,
)
from cmp.modules.statistics.adapters.persistence.repository import (
    SqlAlchemyStatisticsRepository,
    outlier_assessment_revision_table,
    outlier_candidate_table,
    outlier_detection_plan_revision_table,
    statistical_plan_revision_table,
    statistical_result_revision_table,
)
from cmp.modules.statistics.application.replicate_outlier_service import (
    ReplicateOutlierService,
)
from cmp.modules.statistics.application.replicate_service import (
    REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
    ReplicateStatisticsService,
)
from cmp.modules.statistics.application.service import (
    OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
    OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
    STATISTICAL_PLAN_AGGREGATE_TYPE,
    STATISTICAL_RESULT_AGGREGATE_TYPE,
    StatisticsService,
)
from cmp.shared.domain.revisions import RevisionCreated, content_sha256


def _revision_entity_id(
    session: Session,
    event: RevisionCreated,
    *,
    aggregate_type: str,
    revision_id: UUID,
) -> UUID:
    entity_id = session.scalar(
        sa.select(provenance_entity_table.c.id).where(
            provenance_entity_table.c.organization_id == event.revision.scope.organization_id,
            provenance_entity_table.c.project_id == event.revision.scope.project_id,
            provenance_entity_table.c.classification == event.revision.scope.classification,
            provenance_entity_table.c.reference_kind == EntityReferenceKind.REVISION.value,
            provenance_entity_table.c.reference_type == f"{aggregate_type}.revision",
            provenance_entity_table.c.reference_id == revision_id,
        )
    )
    if entity_id is None:
        raise ProvenanceConflict("required immutable revision provenance Entity is missing")
    return cast(UUID, entity_id)


def _generated_activity_id(session: Session, event: RevisionCreated, entity_id: UUID) -> UUID:
    activity_id = session.scalar(
        sa.select(provenance_generation_table.c.activity_id).where(
            provenance_generation_table.c.organization_id == event.revision.scope.organization_id,
            provenance_generation_table.c.project_id == event.revision.scope.project_id,
            provenance_generation_table.c.classification == event.revision.scope.classification,
            provenance_generation_table.c.entity_id == entity_id,
        )
    )
    if activity_id is None:
        raise ProvenanceConflict("generated immutable revision Activity is missing")
    return cast(UUID, activity_id)


def _relation_values(event: RevisionCreated) -> dict[str, object]:
    revision = event.revision
    return {
        "organization_id": revision.scope.organization_id,
        "project_id": revision.scope.project_id,
        "classification": revision.scope.classification,
        "recorded_at": revision.created_at,
        "recorded_by": revision.created_by,
    }


class SqlReferenceStatisticalPlanProvenanceHook:
    """Attach both concrete Selection revisions to the immutable Statistical Plan revision."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != STATISTICAL_PLAN_AGGREGATE_TYPE:
            return
        row = (
            session.execute(
                sa.select(
                    statistical_plan_revision_table.c.first_selection_revision_id,
                    statistical_plan_revision_table.c.second_selection_revision_id,
                ).where(
                    statistical_plan_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    statistical_plan_revision_table.c.project_id == revision.scope.project_id,
                    statistical_plan_revision_table.c.classification
                    == revision.scope.classification,
                    statistical_plan_revision_table.c.aggregate_id == revision.aggregate_id,
                    statistical_plan_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProvenanceConflict("Statistical Plan revision is missing from its typed store")
        generated_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        first_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["first_selection_revision_id"]),
        )
        second_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["second_selection_revision_id"]),
        )
        activity_id = _generated_activity_id(session, event, generated_entity_id)
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "t20.reference_tensile_pair_plan",
                        "plan_revision_id": str(revision.revision_id),
                        "first_selection_revision_id": str(row["first_selection_revision_id"]),
                        "second_selection_revision_id": str(row["second_selection_revision_id"]),
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, entity_id in enumerate((first_entity_id, second_entity_id)):
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=entity_id,
                    role="dataset_selection_member",
                    ordinal=ordinal,
                )
            )


class SqlReferenceStatisticalResultProvenanceHook:
    """Record a Statistics Run output as a derivation of its pinned Plan and Selections."""

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if (
            revision.aggregate_type != STATISTICAL_RESULT_AGGREGATE_TYPE
            or revision.revision_no != 1
        ):
            return
        row = (
            session.execute(
                sa.select(
                    statistical_result_revision_table.c.statistical_run_id,
                    statistical_result_revision_table.c.plan_revision_id,
                    statistical_result_revision_table.c.first_selection_revision_id,
                    statistical_result_revision_table.c.second_selection_revision_id,
                ).where(
                    statistical_result_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    statistical_result_revision_table.c.project_id == revision.scope.project_id,
                    statistical_result_revision_table.c.classification
                    == revision.scope.classification,
                    statistical_result_revision_table.c.aggregate_id == revision.aggregate_id,
                    statistical_result_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProvenanceConflict("Statistical Result revision is missing from its typed store")
        result_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        plan_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["plan_revision_id"]),
        )
        first_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["first_selection_revision_id"]),
        )
        second_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["second_selection_revision_id"]),
        )
        activity_id = _generated_activity_id(session, event, result_entity_id)
        run_id = cast(UUID, row["statistical_run_id"])
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type="statistics.reference_tensile_pair",
                domain_run_type="statistics.statistical_run",
                domain_run_id=run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "t20.reference_tensile_pair_result",
                        "statistical_run_id": str(run_id),
                        "plan_revision_id": str(row["plan_revision_id"]),
                        "first_selection_revision_id": str(row["first_selection_revision_id"]),
                        "second_selection_revision_id": str(row["second_selection_revision_id"]),
                        "result_revision_id": str(revision.revision_id),
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, entity_id in enumerate((first_entity_id, second_entity_id)):
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=entity_id,
                    role="dataset_selection_member",
                    ordinal=ordinal,
                )
            )
            session.execute(
                sa.insert(provenance_derivation_table).values(
                    **values,
                    generated_entity_id=result_entity_id,
                    used_entity_id=entity_id,
                    activity_id=activity_id,
                    derivation_kind="reference_tensile_pair_statistics",
                )
            )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=plan_entity_id,
                role="statistical_plan",
                ordinal=2,
            )
        )
        session.execute(
            sa.update(provenance_association_table)
            .where(
                provenance_association_table.c.organization_id == revision.scope.organization_id,
                provenance_association_table.c.project_id == revision.scope.project_id,
                provenance_association_table.c.classification == revision.scope.classification,
                provenance_association_table.c.activity_id == activity_id,
                provenance_association_table.c.role == "author",
            )
            .values(plan_entity_id=plan_entity_id)
        )


class SqlReplicateStatisticalPlanProvenanceHook:
    """Attach the concrete multi-member Selection revision to its immutable Plan."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE:
            return
        selection_revision_id = session.scalar(
            sa.select(replicate_plan_revision_table.c.selection_revision_id).where(
                replicate_plan_revision_table.c.organization_id == revision.scope.organization_id,
                replicate_plan_revision_table.c.project_id == revision.scope.project_id,
                replicate_plan_revision_table.c.classification == revision.scope.classification,
                replicate_plan_revision_table.c.aggregate_id == revision.aggregate_id,
                replicate_plan_revision_table.c.id == revision.revision_id,
            )
        )
        if selection_revision_id is None:
            raise ProvenanceConflict("replicate Statistical Plan revision is missing")
        plan_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        selection_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, selection_revision_id),
        )
        activity_id = _generated_activity_id(session, event, plan_entity_id)
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "p02.reference_tensile_replicate_plan",
                        "plan_revision_id": str(revision.revision_id),
                        "selection_revision_id": str(selection_revision_id),
                    }
                ),
            )
        )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **_relation_values(event),
                activity_id=activity_id,
                entity_id=selection_entity_id,
                role="dataset_selection",
                ordinal=0,
            )
        )


class SqlReplicateStatisticalResultProvenanceHook:
    """Specialize one result commit as a derivation of its Plan and Selection."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if (
            revision.aggregate_type != REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE
            or revision.revision_no != 1
        ):
            return
        row = (
            session.execute(
                sa.select(
                    replicate_result_revision_table.c.statistical_run_id,
                    replicate_result_revision_table.c.plan_revision_id,
                    replicate_result_revision_table.c.selection_revision_id,
                ).where(
                    replicate_result_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    replicate_result_revision_table.c.project_id == revision.scope.project_id,
                    replicate_result_revision_table.c.classification
                    == revision.scope.classification,
                    replicate_result_revision_table.c.aggregate_id == revision.aggregate_id,
                    replicate_result_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProvenanceConflict("replicate Statistical Result revision is missing")
        result_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=REPLICATE_STATISTICAL_RESULT_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        plan_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["plan_revision_id"]),
        )
        selection_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["selection_revision_id"]),
        )
        activity_id = _generated_activity_id(session, event, result_entity_id)
        run_id = cast(UUID, row["statistical_run_id"])
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type="statistics.reference_tensile_replicates",
                domain_run_type="statistics.replicate_statistical_run",
                domain_run_id=run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "p02.reference_tensile_replicate_result",
                        "statistical_run_id": str(run_id),
                        "plan_revision_id": str(row["plan_revision_id"]),
                        "selection_revision_id": str(row["selection_revision_id"]),
                        "result_revision_id": str(revision.revision_id),
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, (role, entity_id) in enumerate(
            (("dataset_selection", selection_entity_id), ("statistical_plan", plan_entity_id))
        ):
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=entity_id,
                    role=role,
                    ordinal=ordinal,
                )
            )
            session.execute(
                sa.insert(provenance_derivation_table).values(
                    **values,
                    generated_entity_id=result_entity_id,
                    used_entity_id=entity_id,
                    activity_id=activity_id,
                    derivation_kind="reference_tensile_replicate_statistics",
                )
            )
        session.execute(
            sa.update(provenance_association_table)
            .where(
                provenance_association_table.c.organization_id == revision.scope.organization_id,
                provenance_association_table.c.project_id == revision.scope.project_id,
                provenance_association_table.c.classification == revision.scope.classification,
                provenance_association_table.c.activity_id == activity_id,
                provenance_association_table.c.role == "author",
            )
            .values(plan_entity_id=plan_entity_id)
        )


class SqlReferenceOutlierDetectionPlanProvenanceHook:
    """Make a detector configuration explicitly use one immutable Statistical Result."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE:
            return
        row = (
            session.execute(
                sa.select(
                    outlier_detection_plan_revision_table.c.statistical_result_revision_id,
                ).where(
                    outlier_detection_plan_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    outlier_detection_plan_revision_table.c.project_id == revision.scope.project_id,
                    outlier_detection_plan_revision_table.c.classification
                    == revision.scope.classification,
                    outlier_detection_plan_revision_table.c.aggregate_id == revision.aggregate_id,
                    outlier_detection_plan_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProvenanceConflict(
                "Outlier Detection Plan revision is missing from its typed store"
            )
        detector_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        result_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["statistical_result_revision_id"]),
        )
        activity_id = _generated_activity_id(session, event, detector_entity_id)
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type="statistics.reference_pair_outlier_detection_plan",
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "t21.reference_pair_outlier_detection_plan",
                        "detection_plan_revision_id": str(revision.revision_id),
                        "statistical_result_revision_id": str(
                            row["statistical_result_revision_id"]
                        ),
                    }
                ),
            )
        )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **_relation_values(event),
                activity_id=activity_id,
                entity_id=result_entity_id,
                role="statistical_result",
                ordinal=0,
            )
        )


class SqlReferenceOutlierAssessmentProvenanceHook:
    """Relate an immutable human decision to its candidate's frozen evidence graph."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != OUTLIER_ASSESSMENT_AGGREGATE_TYPE:
            return
        row = (
            session.execute(
                sa.select(
                    outlier_assessment_revision_table.c.candidate_id,
                    outlier_assessment_revision_table.c.statistical_plan_revision_id,
                    outlier_candidate_table.c.detection_run_id,
                    outlier_candidate_table.c.detection_plan_revision_id,
                    outlier_candidate_table.c.statistical_result_revision_id,
                )
                .select_from(
                    outlier_assessment_revision_table.join(
                        outlier_candidate_table,
                        sa.and_(
                            outlier_candidate_table.c.organization_id
                            == outlier_assessment_revision_table.c.organization_id,
                            outlier_candidate_table.c.project_id
                            == outlier_assessment_revision_table.c.project_id,
                            outlier_candidate_table.c.classification
                            == outlier_assessment_revision_table.c.classification,
                            outlier_candidate_table.c.id
                            == outlier_assessment_revision_table.c.candidate_id,
                        ),
                    )
                )
                .where(
                    outlier_assessment_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    outlier_assessment_revision_table.c.project_id == revision.scope.project_id,
                    outlier_assessment_revision_table.c.classification
                    == revision.scope.classification,
                    outlier_assessment_revision_table.c.aggregate_id == revision.aggregate_id,
                    outlier_assessment_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ProvenanceConflict("Outlier Assessment revision is missing from typed evidence")
        assessment_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=OUTLIER_ASSESSMENT_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        plan_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_PLAN_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["statistical_plan_revision_id"]),
        )
        detector_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=OUTLIER_DETECTION_PLAN_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["detection_plan_revision_id"]),
        )
        result_entity_id = _revision_entity_id(
            session,
            event,
            aggregate_type=STATISTICAL_RESULT_AGGREGATE_TYPE,
            revision_id=cast(UUID, row["statistical_result_revision_id"]),
        )
        activity_id = _generated_activity_id(session, event, assessment_entity_id)
        run_id = cast(UUID, row["detection_run_id"])
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type="statistics.reference_pair_outlier_assessment",
                domain_run_type="statistics.outlier_detection_run",
                domain_run_id=run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "t21.reference_pair_outlier_assessment",
                        "assessment_revision_id": str(revision.revision_id),
                        "candidate_id": str(row["candidate_id"]),
                        "statistical_plan_revision_id": str(row["statistical_plan_revision_id"]),
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, (entity_id, role) in enumerate(
            (
                (plan_entity_id, "statistical_plan_scope"),
                (detector_entity_id, "outlier_detection_plan"),
                (result_entity_id, "statistical_result"),
            )
        ):
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=entity_id,
                    role=role,
                    ordinal=ordinal,
                )
            )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **values,
                generated_entity_id=assessment_entity_id,
                used_entity_id=result_entity_id,
                activity_id=activity_id,
                derivation_kind="reference_pair_outlier_assessment",
            )
        )
        session.execute(
            sa.update(provenance_association_table)
            .where(
                provenance_association_table.c.organization_id == revision.scope.organization_id,
                provenance_association_table.c.project_id == revision.scope.project_id,
                provenance_association_table.c.classification == revision.scope.classification,
                provenance_association_table.c.activity_id == activity_id,
                provenance_association_table.c.role == "author",
            )
            .values(plan_entity_id=plan_entity_id)
        )


def build_statistics_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    artifacts: ArtifactService | None,
) -> StatisticsService | None:
    """Build only when the authoritative Dataset and immutable Artifact services are present."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return StatisticsService(
        repository=SqlAlchemyStatisticsRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlReferenceStatisticalPlanProvenanceHook(),
                SqlReferenceStatisticalResultProvenanceHook(),
                SqlReferenceOutlierDetectionPlanProvenanceHook(),
                SqlReferenceOutlierAssessmentProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        artifacts=artifacts,
    )


def build_replicate_statistics_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    artifacts: ArtifactService | None,
) -> ReplicateStatisticsService | None:
    """Build the P0-2 multi-member Statistics slice on the same authoritative ports."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReplicateStatisticsService(
        repository=SqlAlchemyReplicateStatisticsRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlReplicateStatisticalPlanProvenanceHook(),
                SqlReplicateStatisticalResultProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        artifacts=artifacts,
    )


def build_replicate_outlier_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    artifacts: ArtifactService | None,
) -> ReplicateOutlierService | None:
    """Build persisted evidence, assessment, and calibration-scope workflows."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    common_hooks = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        SqlAlchemyRevisionAuditHook(),
    )
    return ReplicateOutlierService(
        repository=SqlAlchemyReplicateOutlierRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=common_hooks,
        ),
        statistics=SqlAlchemyReplicateStatisticsRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
        ),
        datasets=datasets,
        artifacts=artifacts,
    )
