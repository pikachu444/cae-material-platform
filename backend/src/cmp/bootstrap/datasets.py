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
from cmp.modules.catalog.application.service import CatalogService
from cmp.modules.datasets.adapters.integration.governed_test_data_source import (
    CatalogTestingGovernedTestDataSourceVerifier,
)
from cmp.modules.datasets.adapters.persistence.canonical_test_data import (
    SqlAlchemyCanonicalTestDataRepository,
)
from cmp.modules.datasets.adapters.persistence.governed_import_repository import (
    SqlAlchemyGovernedImportRepository,
)
from cmp.modules.datasets.adapters.persistence.repository import (
    SqlAlchemyDatasetRepository,
    dataset_revision_table,
    dataset_selection_member_table,
    dataset_selection_revision_table,
    shear_relaxation_dataset_revision_table,
)
from cmp.modules.datasets.adapters.persistence.viscoelastic_master_repository import (
    SqlAlchemyViscoelasticDatasetRepository,
)
from cmp.modules.datasets.adapters.persistence.viscoelastic_master_repository import (
    derived_dataset_revision_table as viscoelastic_derived_revision_table,
)
from cmp.modules.datasets.adapters.persistence.viscoelastic_master_repository import (
    selection_member_table as viscoelastic_selection_member_table,
)
from cmp.modules.datasets.application.canonical_test_data import CanonicalTestDataService
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetService,
)
from cmp.modules.datasets.application.shear_relaxation import (
    SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
    ShearRelaxationDatasetService,
)
from cmp.modules.datasets.application.viscoelastic_master import (
    VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE,
    VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
    ViscoelasticDatasetService,
)
from cmp.modules.datasets.domain.reference_tensile import DatasetRepresentation
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.processing.application.service import PROCESSING_RECIPE_AGGREGATE_TYPE
from cmp.modules.processing.application.shear_relaxation import (
    SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
)
from cmp.modules.processing.application.viscoelastic_master_curve import (
    VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
)
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
from cmp.modules.testing.application.service import TestingService
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
    sa.Column("run_kind", sa.String(100), nullable=False),
    schema="processing",
)
_shear_processing_run_table = sa.Table(
    "shear_relaxation_run",
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
        if (
            revision.aggregate_type
            not in {DATASET_AGGREGATE_TYPE, SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE}
            or revision.revision_no != 1
        ):
            return
        revision_table = (
            dataset_revision_table
            if revision.aggregate_type == DATASET_AGGREGATE_TYPE
            else shear_relaxation_dataset_revision_table
        )
        dataset_row = (
            session.execute(
                sa.select(
                    revision_table.c.raw_asset_id,
                    revision_table.c.representation,
                ).where(
                    revision_table.c.organization_id == revision.scope.organization_id,
                    revision_table.c.project_id == revision.scope.project_id,
                    revision_table.c.aggregate_id == revision.aggregate_id,
                    revision_table.c.id == revision.revision_id,
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
            aggregate_type=revision.aggregate_type,
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
                derivation_kind=(
                    "reference_tensile_import"
                    if revision.aggregate_type == DATASET_AGGREGATE_TYPE
                    else "reference_shear_relaxation_import"
                ),
            )
        )


class SqlReferenceDatasetSelectionProvenanceHook:
    """Link every ordered Selection member to the immutable Dataset revision it names."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != DATASET_SELECTION_AGGREGATE_TYPE:
            return
        selection = (
            session.execute(
                sa.select(
                    dataset_selection_revision_table.c.selection_kind,
                    dataset_selection_revision_table.c.dataset_revision_id,
                ).where(
                    dataset_selection_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    dataset_selection_revision_table.c.project_id == revision.scope.project_id,
                    dataset_selection_revision_table.c.classification
                    == revision.scope.classification,
                    dataset_selection_revision_table.c.aggregate_id == revision.aggregate_id,
                    dataset_selection_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if selection is None:
            raise ProvenanceConflict("Selection revision is missing from its typed store")
        selected_revision_ids: tuple[UUID, ...]
        if selection["selection_kind"] == "reference_curve_dataset_revision":
            selected_revision_ids = (cast(UUID, selection["dataset_revision_id"]),)
        else:
            selected_revision_ids = tuple(
                cast(UUID, value)
                for value in session.scalars(
                    sa.select(dataset_selection_member_table.c.dataset_revision_id)
                    .where(
                        dataset_selection_member_table.c.organization_id
                        == revision.scope.organization_id,
                        dataset_selection_member_table.c.project_id == revision.scope.project_id,
                        dataset_selection_member_table.c.classification
                        == revision.scope.classification,
                        dataset_selection_member_table.c.selection_id == revision.aggregate_id,
                        dataset_selection_member_table.c.selection_revision_id
                        == revision.revision_id,
                    )
                    .order_by(dataset_selection_member_table.c.ordinal.asc())
                )
            )
        if not selected_revision_ids:
            raise ProvenanceConflict("Selection revision has no concrete Dataset members")
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
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
                        "dataset_revision_ids": [str(value) for value in selected_revision_ids],
                    }
                ),
            )
        )
        for ordinal, selected_revision_id in enumerate(selected_revision_ids):
            selected_entity_id = _revision_provenance_entity_id(
                session,
                event,
                aggregate_type=DATASET_AGGREGATE_TYPE,
                revision_id=selected_revision_id,
            )
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **_relation_values(event),
                    activity_id=activity_id,
                    entity_id=selected_entity_id,
                    role="dataset_member",
                    ordinal=ordinal,
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
                    _processing_run_table.c.run_kind,
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
        run_kind = str(processing_row["run_kind"])
        activity_type = (
            "processing.reference_tensile_alignment"
            if run_kind == "reference_tensile_common_grid_linear"
            else "processing.reference_tensile_crop"
        )
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
                activity_type=activity_type,
                domain_run_type="processing.processing_run",
                domain_run_id=processing_run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": activity_type,
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
            sa.insert(provenance_usage_table).values(
                **_relation_values(event),
                activity_id=activity_id,
                entity_id=recipe_entity_id,
                role="processing_recipe_revision",
                ordinal=1,
            )
        )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **_relation_values(event),
                generated_entity_id=generated_entity_id,
                used_entity_id=source_entity_id,
                activity_id=activity_id,
                derivation_kind=run_kind,
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


class SqlShearRelaxationProcessedDatasetProvenanceHook:
    """Bind a processed shear curve to its normalized input, Recipe, and Run."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if (
            revision.aggregate_type != SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE
            or revision.revision_no != 1
        ):
            return
        output = (
            session.execute(
                sa.select(
                    shear_relaxation_dataset_revision_table.c.representation,
                    shear_relaxation_dataset_revision_table.c.source_dataset_revision_id,
                    shear_relaxation_dataset_revision_table.c.processing_run_id,
                ).where(
                    shear_relaxation_dataset_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    shear_relaxation_dataset_revision_table.c.project_id
                    == revision.scope.project_id,
                    shear_relaxation_dataset_revision_table.c.aggregate_id == revision.aggregate_id,
                    shear_relaxation_dataset_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if output is None:
            raise ProvenanceConflict("processed shear Dataset revision is missing")
        if str(output["representation"]) != "processed":
            return
        source_revision_id = cast(UUID | None, output["source_dataset_revision_id"])
        processing_run_id = cast(UUID | None, output["processing_run_id"])
        if source_revision_id is None or processing_run_id is None:
            raise ProvenanceConflict("processed shear Dataset lacks source or Run")
        processing = (
            session.execute(
                sa.select(
                    _shear_processing_run_table.c.recipe_revision_id,
                    _shear_processing_run_table.c.input_dataset_revision_id,
                ).where(
                    _shear_processing_run_table.c.organization_id == revision.scope.organization_id,
                    _shear_processing_run_table.c.project_id == revision.scope.project_id,
                    _shear_processing_run_table.c.classification == revision.scope.classification,
                    _shear_processing_run_table.c.id == processing_run_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            processing is None
            or cast(UUID, processing["input_dataset_revision_id"]) != source_revision_id
        ):
            raise ProvenanceConflict("processed shear Dataset does not match its Run input")
        recipe_revision_id = cast(UUID, processing["recipe_revision_id"])
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        source_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
            revision_id=source_revision_id,
        )
        recipe_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=SHEAR_RELAXATION_RECIPE_AGGREGATE_TYPE,
            revision_id=recipe_revision_id,
        )
        activity_id = _generated_activity_id(session, event, generated_entity_id)
        activity_type = "processing.reference_shear_relaxation_time_crop"
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type=activity_type,
                domain_run_type="processing.shear_relaxation_run",
                domain_run_id=processing_run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": activity_type,
                        "processing_run_id": str(processing_run_id),
                        "recipe_revision_id": str(recipe_revision_id),
                        "source_dataset_revision_id": str(source_revision_id),
                        "output_dataset_revision_id": str(revision.revision_id),
                    }
                ),
            )
        )
        values = _relation_values(event)
        session.execute(
            sa.insert(provenance_usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=source_entity_id,
                role="normalized_dataset_revision",
                ordinal=0,
            )
        )
        session.execute(
            sa.insert(provenance_usage_table).values(
                **values,
                activity_id=activity_id,
                entity_id=recipe_entity_id,
                role="processing_recipe_revision",
                ordinal=1,
            )
        )
        session.execute(
            sa.insert(provenance_derivation_table).values(
                **values,
                generated_entity_id=generated_entity_id,
                used_entity_id=source_entity_id,
                activity_id=activity_id,
                derivation_kind="reference_shear_relaxation_inclusive_time_crop",
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


class SqlViscoelasticSelectionProvenanceHook:
    """Record every exact replicate Dataset revision used by a T-42 Selection."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != VISCOELASTIC_SELECTION_AGGREGATE_TYPE:
            return
        members = (
            session.execute(
                sa.select(viscoelastic_selection_member_table)
                .where(
                    viscoelastic_selection_member_table.c.organization_id
                    == revision.scope.organization_id,
                    viscoelastic_selection_member_table.c.project_id
                    == revision.scope.project_id,
                    viscoelastic_selection_member_table.c.selection_revision_id
                    == revision.revision_id,
                )
                .order_by(viscoelastic_selection_member_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        if not members:
            raise ProvenanceConflict("viscoelastic Selection members are missing")
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
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
                        "hook": "datasets.viscoelastic_replicate_selection",
                        "selection_revision_id": str(revision.revision_id),
                        "member_revision_ids": [str(row["dataset_revision_id"]) for row in members],
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, row in enumerate(members):
            source_entity_id = _revision_provenance_entity_id(
                session,
                event,
                aggregate_type=SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
                revision_id=cast(UUID, row["dataset_revision_id"]),
            )
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=source_entity_id,
                    role="shear_relaxation_dataset_revision",
                    ordinal=ordinal,
                )
            )
            session.execute(
                sa.insert(provenance_derivation_table).values(
                    **values,
                    generated_entity_id=generated_entity_id,
                    used_entity_id=source_entity_id,
                    activity_id=activity_id,
                    derivation_kind="selection_membership",
                )
            )


class SqlViscoelasticDerivedDatasetProvenanceHook:
    """Bind every derived representation to its Selection, Plan, Run, and curves."""

    def __call__(self, session: Session, event: RevisionCreated) -> None:
        revision = event.revision
        if revision.aggregate_type != VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE:
            return
        output = (
            session.execute(
                sa.select(viscoelastic_derived_revision_table).where(
                    viscoelastic_derived_revision_table.c.organization_id
                    == revision.scope.organization_id,
                    viscoelastic_derived_revision_table.c.project_id
                    == revision.scope.project_id,
                    viscoelastic_derived_revision_table.c.id == revision.revision_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if output is None:
            raise ProvenanceConflict("viscoelastic derived Dataset revision is missing")
        selection_revision_id = cast(UUID, output["selection_revision_id"])
        plan_revision_id = cast(UUID, output["processing_plan_revision_id"])
        processing_run_id = cast(UUID, output["processing_run_id"])
        members = (
            session.execute(
                sa.select(viscoelastic_selection_member_table)
                .where(
                    viscoelastic_selection_member_table.c.organization_id
                    == revision.scope.organization_id,
                    viscoelastic_selection_member_table.c.project_id
                    == revision.scope.project_id,
                    viscoelastic_selection_member_table.c.selection_revision_id
                    == selection_revision_id,
                )
                .order_by(viscoelastic_selection_member_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        generated_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=VISCOELASTIC_DERIVED_DATASET_AGGREGATE_TYPE,
            revision_id=revision.revision_id,
        )
        selection_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=VISCOELASTIC_SELECTION_AGGREGATE_TYPE,
            revision_id=selection_revision_id,
        )
        plan_entity_id = _revision_provenance_entity_id(
            session,
            event,
            aggregate_type=VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
            revision_id=plan_revision_id,
        )
        activity_id = _generated_activity_id(session, event, generated_entity_id)
        activity_type = f"processing.viscoelastic_{output['representation']}"
        domain_run_type = (
            f"processing.viscoelastic_master_output.{output['representation']}"
        )
        session.execute(
            sa.update(provenance_activity_table)
            .where(
                provenance_activity_table.c.organization_id == revision.scope.organization_id,
                provenance_activity_table.c.project_id == revision.scope.project_id,
                provenance_activity_table.c.classification == revision.scope.classification,
                provenance_activity_table.c.id == activity_id,
            )
            .values(
                activity_type=activity_type,
                domain_run_type=domain_run_type,
                domain_run_id=processing_run_id,
                input_required=True,
                submission_digest=content_sha256(
                    {
                        "hook": activity_type,
                        "processing_run_id": str(processing_run_id),
                        "selection_revision_id": str(selection_revision_id),
                        "plan_revision_id": str(plan_revision_id),
                        "output_revision_id": str(revision.revision_id),
                    }
                ),
            )
        )
        values = _relation_values(event)
        for ordinal, (entity_id, role) in enumerate(
            (
                (selection_entity_id, "viscoelastic_selection_revision"),
                (plan_entity_id, "viscoelastic_master_plan_revision"),
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
        for offset, row in enumerate(members, start=2):
            source_entity_id = _revision_provenance_entity_id(
                session,
                event,
                aggregate_type=SHEAR_RELAXATION_DATASET_AGGREGATE_TYPE,
                revision_id=cast(UUID, row["dataset_revision_id"]),
            )
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **values,
                    activity_id=activity_id,
                    entity_id=source_entity_id,
                    role="source_curve_revision",
                    ordinal=offset,
                )
            )
            session.execute(
                sa.insert(provenance_derivation_table).values(
                    **values,
                    generated_entity_id=generated_entity_id,
                    used_entity_id=source_entity_id,
                    activity_id=activity_id,
                    derivation_kind=str(output["representation"]),
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


def build_governed_import_service(
    identity: IdentityServices,
    testing: TestingService | None,
    artifacts: ArtifactService | None,
) -> GovernedImportService | None:
    """Compose the T-41 importer without bypassing Testing or Artifact boundaries."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or testing is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return GovernedImportService(
        repository=SqlAlchemyGovernedImportRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        testing=testing,
        artifacts=artifacts,
    )


def build_canonical_test_data_service(
    identity: IdentityServices,
    artifacts: ArtifactService | None,
    catalog: CatalogService | None = None,
    testing: TestingService | None = None,
    governed_import: GovernedImportService | None = None,
) -> CanonicalTestDataService | None:
    """Compose canonical JSON import/export with immutable Artifacts and revision hooks."""

    if identity.engine is None or identity.rls_context is None or artifacts is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return CanonicalTestDataService(
        repository=SqlAlchemyCanonicalTestDataRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        artifacts=artifacts,
        governed_source_verifier=(
            None
            if catalog is None or testing is None
            else CatalogTestingGovernedTestDataSourceVerifier(
                catalog=catalog,
                testing=testing,
                governed_import=governed_import,
            )
        ),
    )


def build_shear_relaxation_dataset_service(
    identity: IdentityServices,
    artifacts: ArtifactService | None,
) -> ShearRelaxationDatasetService | None:
    """Build the reference viscoelastic data slice on the shared revision infrastructure."""

    if identity.engine is None or identity.rls_context is None or artifacts is None:
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ShearRelaxationDatasetService(
        repository=SqlAlchemyDatasetRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlReferenceDatasetInputProvenanceHook(),
                SqlShearRelaxationProcessedDatasetProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        artifacts=artifacts,
    )


def build_viscoelastic_dataset_service(
    identity: IdentityServices,
    shear_datasets: ShearRelaxationDatasetService | None,
    testing: TestingService | None,
) -> ViscoelasticDatasetService | None:
    """Compose immutable T-42 replicate Selections and derived Datasets."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or shear_datasets is None
        or testing is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ViscoelasticDatasetService(
        repository=SqlAlchemyViscoelasticDatasetRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlViscoelasticSelectionProvenanceHook(),
                SqlViscoelasticDerivedDatasetProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        shear_datasets=shear_datasets,
        testing=testing,
    )
