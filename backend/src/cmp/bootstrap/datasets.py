"""Compose the reference Dataset service with the immutable Artifact service."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.datasets.adapters.persistence.repository import (
    SqlAlchemyDatasetRepository,
    dataset_revision_table,
)
from cmp.modules.datasets.application.service import DATASET_AGGREGATE_TYPE, DatasetService
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
    SqlAlchemyRevisionProvenanceHook,
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
from cmp.shared.domain.revisions import RevisionCreated

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
                sa.select(dataset_revision_table.c.raw_asset_id).where(
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
        generated_entity_id = session.scalar(
            sa.select(provenance_entity_table.c.id).where(
                provenance_entity_table.c.organization_id == revision.scope.organization_id,
                provenance_entity_table.c.project_id == revision.scope.project_id,
                provenance_entity_table.c.classification == revision.scope.classification,
                provenance_entity_table.c.reference_kind == EntityReferenceKind.REVISION.value,
                provenance_entity_table.c.reference_type == f"{DATASET_AGGREGATE_TYPE}.revision",
                provenance_entity_table.c.reference_id == revision.revision_id,
            )
        )
        if generated_entity_id is None:
            raise ProvenanceConflict("generated Dataset provenance Entity is missing")
        activity_id = session.scalar(
            sa.select(provenance_generation_table.c.activity_id).where(
                provenance_generation_table.c.organization_id == revision.scope.organization_id,
                provenance_generation_table.c.project_id == revision.scope.project_id,
                provenance_generation_table.c.classification == revision.scope.classification,
                provenance_generation_table.c.entity_id == generated_entity_id,
            )
        )
        if activity_id is None:
            raise ProvenanceConflict("generated Dataset provenance Activity is missing")
        values: dict[str, Any] = {
            "organization_id": revision.scope.organization_id,
            "project_id": revision.scope.project_id,
            "classification": revision.scope.classification,
            "recorded_at": revision.created_at,
            "recorded_by": revision.created_by,
        }
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
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        artifacts=artifacts,
    )
