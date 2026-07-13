"""Compose the reference Dataset service with the immutable Artifact service."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.adapters.persistence.repository import (
    SqlAlchemyDatasetRepository,
    dataset_revision_table,
    dataset_selection_revision_table,
)
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetService,
)
from cmp.modules.datasets.domain.reference_tensile import DatasetRepresentation
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.processing.application.service import PROCESSING_RECIPE_AGGREGATE_TYPE
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
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
from cmp.modules.provenance.domain.model import (
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceConflict,
    ProvenanceEntity,
    ProvenanceScope,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.shared.domain.revisions import RevisionCreated, content_sha256

_metadata = sa.MetaData()
_raw_asset_table = sa.Table(
    "raw_asset",
    _metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    schema="artifact",
)
_processing_run_table = sa.Table(
    "processing_run",
    _metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("recipe_revision_id", sa.Uuid(), nullable=False),
    sa.Column("input_dataset_revision_id", sa.Uuid(), nullable=False),
    schema="processing",
)


def _revision_provenance_entity_id(
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


class SqlReferenceDatasetInputProvenanceHook:
    """Composition-root hook linking a Dataset import to its immutable Raw Asset.

    The Dataset module owns its typed Dataset tables and Provenance owns the typed graph tables.
    Keeping this cross-capability relation in the bootstrap composition root avoids a private
    persistence dependency while still committing all facts in one revision transaction.
    """

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != DATASET_AGGREGATE_TYPE or revision.revision_no != 1:
            return
        dataset_row = (
            session.execute(
                sa.select(
                    dataset_revision_table.c.raw_asset_id,
                    dataset_revision_table.c.representation,
                ).where(
                    dataset_revision_table.c.organization_id == revision.scope.organization_id,
                    dataset_revision_table.c.project_id == revision.scope.project_id,
                    dataset_revision_table.c.aggregate_id == revision.aggregate_id,
                    dataset_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if dataset_row is None:
            raise ProvenanceConflict("new Dataset revision is missing from the typed store")
        if str(dataset_row["representation"]) != DatasetRepresentation.RAW.value:
            # A committed processed Dataset also starts a separate stable identity at revision 1,
            # but its input is a normalized Dataset revision rather than a Raw Asset.
            return
        raw_asset_id = cast(UUID, dataset_row["raw_asset_id"])
        raw_asset = (
            session.execute(
                sa.select(_raw_asset_table.c.sha256, _raw_asset_table.c.created_at).where(
                    _raw_asset_table.c.organization_id == revision.scope.organization_id,
                    _raw_asset_table.c.project_id == revision.scope.project_id,
                    _raw_asset_table.c.classification == revision.scope.classification,
                    _raw_asset_table.c.id == raw_asset_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if raw_asset is None:
            raise ProvenanceConflict("Dataset Raw Asset is not visible for provenance")
        scope = ProvenanceScope(
            revision.scope.organization_id,
            revision.scope.project_id,
            DataClassification(revision.scope.classification),
        )
        raw_entity = SqlAlchemyProvenanceRepository._ensure_entity(
            session,
            ProvenanceEntity(
                id=self._id_factory(),
                scope=scope,
                entity_type="artifact.raw_asset",
                reference=ImmutableEntityReference(
                    EntityReferenceKind.RAW_ASSET,
                    "artifact.raw_asset",
                    raw_asset_id,
                    str(raw_asset["sha256"]),
                ),
                generation_requirement=GenerationRequirement.NONE,
                created_at=raw_asset["created_at"],
                recorded_at=revision.created_at,
                recorded_by=revision.created_by,
            ),
            request_id=revision.request_id,
            trace_id=revision.trace_id,
        )
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        activity_id = _generated_activity_id(session, event, generated_entity_id)
        values = _relation_values(event)
        session.execute(
            sa.insert(provenance_usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=raw_entity.id,
                role="raw_asset",
                ordinal=0,
            )
        )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **values,
                generated_entity_id=generated_entity_id,
                used_entity_id=raw_entity.id,
                activity_id=activity_id,
                derivation_kind="reference_tensile_import",
            )
        )


class SqlReferenceDatasetSelectionProvenanceHook:
    """Link a pinned one-member Selection revision to the immutable Dataset it names."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != DATASET_SELECTION_AGGREGATE_TYPE:
            return
        selected_revision_id = session.scalar(
            sa.select(dataset_selection_revision_table.c.dataset_revision_id).where(
                dataset_selection_revision_table.c.organization_id
                == revision.scope.organization_id,
                dataset_selection_revision_table.c.project_id == revision.scope.project_id,
                dataset_selection_revision_table.c.classification == revision.scope.classification,
                dataset_selection_revision_table.c.aggregate_id == revision.aggregate_id,
                dataset_selection_revision_table.c.id == revision.revision_id,
            )
        )
        if selected_revision_id is None:
            raise ProvenanceConflict("Selection revision is missing from its typed store")
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        selected_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_AGGREGATE_TYPE,
            revision_id=cast(UUID, selected_revision_id),
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
                        "hook": "t19.reference_dataset_selection",
                        "selection_revision_id": str(revision.revision_id),
                        "dataset_revision_id": str(selected_revision_id),
                    }
                ),
            )
        )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **_relation_values(event),
                activity_id=activity_id,
                entity_id=selected_entity_id,
                role="dataset_member",
                ordinal=0,
            )
        )


class SqlReferenceProcessedDatasetProvenanceHook:
    """Represent a committed crop as a Dataset derivation with its Recipe plan attached."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != DATASET_AGGREGATE_TYPE or revision.revision_no != 1:
            return
        output_row = (
            session.execute(
                sa.select(
                    dataset_revision_table.c.representation,
                    dataset_revision_table.c.source_dataset_revision_id,
                    dataset_revision_table.c.processing_run_id,
                ).where(
                    dataset_revision_table.c.organization_id == revision.scope.organization_id,
                    dataset_revision_table.c.project_id == revision.scope.project_id,
                    dataset_revision_table.c.classification == revision.scope.classification,
                    dataset_revision_table.c.aggregate_id == revision.aggregate_id,
                    dataset_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if output_row is None:
            raise ProvenanceConflict("processed Dataset revision is missing from its typed store")
        if str(output_row["representation"]) != DatasetRepresentation.PROCESSED.value:
            return
        source_revision_id = cast(UUID | None, output_row["source_dataset_revision_id"])
        processing_run_id = cast(UUID | None, output_row["processing_run_id"])
        if source_revision_id is None or processing_run_id is None:
            raise ProvenanceConflict(
                "processed Dataset provenance requires source and Processing Run"
            )
        processing_row = (
            session.execute(
                sa.select(
                    _processing_run_table.c.recipe_revision_id,
                    _processing_run_table.c.input_dataset_revision_id,
                ).where(
                    _processing_run_table.c.organization_id == revision.scope.organization_id,
                    _processing_run_table.c.project_id == revision.scope.project_id,
                    _processing_run_table.c.classification == revision.scope.classification,
                    _processing_run_table.c.id == processing_run_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if processing_row is None:
            raise ProvenanceConflict("processed Dataset Processing Run is not visible")
        if cast(UUID, processing_row["input_dataset_revision_id"]) != source_revision_id:
            raise ProvenanceConflict("processed Dataset source does not match its Processing Run")
        recipe_revision_id = cast(UUID, processing_row["recipe_revision_id"])
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        source_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_AGGREGATE_TYPE,
            revision_id=source_revision_id,
        )
        recipe_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=PROCESSING_RECIPE_AGGREGATE_TYPE,
            revision_id=recipe_revision_id,
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
                activity_type="processing.reference_tensile_crop",
                domain_run_type="processing.processing_run",
                domain_run_id=processing_run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": "t19.reference_tensile_crop",
                        "processing_run_id": str(processing_run_id),
                        "recipe_revision_id": str(recipe_revision_id),
                        "source_dataset_revision_id": str(source_revision_id),
                        "output_dataset_revision_id": str(revision.revision_id),
                    }
                ),
            )
        )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **_relation_values(event),
                activity_id=activity_id,
                entity_id=source_entity_id,
                role="normalized_dataset_revision",
                ordinal=0,
            )
        )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **_relation_values(event),
                generated_entity_id=generated_entity_id,
                used_entity_id=source_entity_id,
                activity_id=activity_id,
                derivation_kind="reference_tensile_inclusive_crop",
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
            .values(plan_entity_id=recipe_entity_id)
        )


def build_dataset_service(
    identity: IdentityServices,
    artifacts: ArtifactService | None,
) -> DatasetService | None:
    """Build only when both authoritative SQL and immutable object content are configured."""

    if identity.engine is None or identity.rls_context is None or artifacts is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return DatasetService(
        repository=SqlAlchemyDatasetRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlReferenceDatasetInputProvenanceHook(),
                SqlReferenceDatasetSelectionProvenanceHook(),
                SqlReferenceProcessedDatasetProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        artifacts=artifacts,
    )
