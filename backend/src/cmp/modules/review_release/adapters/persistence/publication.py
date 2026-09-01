"""Atomic review approval projection into immutable governance and Catalog read markers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.review_release.domain.evidence import ReviewSubjectEvidence
from cmp.modules.review_release.domain.lifecycle import ReviewConflict

metadata = sa.MetaData()

review_publication_projection_table = sa.Table(
    "review_publication_projection",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("review_request_id", sa.Uuid(), nullable=False),
    sa.Column("subject_type", sa.String(64), nullable=False),
    sa.Column("subject_id", sa.Uuid(), nullable=False),
    sa.Column("subject_revision_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=True),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=True),
    sa.Column("neutral_artifact_sha256", sa.CHAR(64), nullable=True),
    sa.Column("material_id", sa.Uuid(), nullable=True),
    sa.Column("material_revision_id", sa.Uuid(), nullable=True),
    sa.Column("record_id", sa.Uuid(), nullable=True),
    sa.Column("record_revision_id", sa.Uuid(), nullable=True),
    sa.Column("record_table_id", sa.Uuid(), nullable=True),
    sa.Column("record_table_revision_id", sa.Uuid(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_by", sa.Uuid(), nullable=False),
    schema="governance",
)

catalog_publication_marker_table = sa.Table(
    "publication_marker",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_type", sa.String(128), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("revision_id", sa.Uuid(), nullable=False),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("published_by", sa.Uuid(), nullable=False),
    schema="catalog",
)

catalog_record_table = sa.Table(
    "catalog_record",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)

catalog_material_revision_table = sa.Table(
    "material_revision",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("id", sa.Uuid(), nullable=False),
    schema="catalog",
)

domain_record_binding_table = sa.Table(
    "domain_record_binding",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("record_revision_id", sa.Uuid(), nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)

_subject_identity_tables = {
    "catalog.material": sa.Table(
        "material",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="catalog",
    ),
    "catalog.configurable_record": catalog_record_table,
    "datasets.test_data_document": sa.Table(
        "test_data_document",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="datasets",
    ),
    "modeling.material_model": sa.Table(
        "material_model",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="modeling",
    ),
    "exporting.solver_card": sa.Table(
        "solver_card",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="exporting",
    ),
    "exporting.neutral_solver_card": sa.Table(
        "neutral_solver_card",
        metadata,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=False),
        schema="exporting",
    ),
}


class ReviewApprovalProjector(Protocol):
    def project(
        self,
        *,
        session: Session,
        context: SecurityContext,
        review_request_id: UUID,
        review_decision_id: UUID | None = None,
        evidence: ReviewSubjectEvidence,
        published_by: UUID,
        occurred_at: datetime,
    ) -> None: ...


class SqlAlchemyReviewApprovalProjector:
    """Project only an approved, exact evidence snapshot in the decision transaction."""

    def __init__(self, *, plan_projector: Any | None = None) -> None:
        self._plan_projector = plan_projector

    def project(
        self,
        *,
        session: Session,
        context: SecurityContext,
        review_request_id: UUID,
        review_decision_id: UUID | None = None,
        evidence: ReviewSubjectEvidence,
        published_by: UUID,
        occurred_at: datetime,
    ) -> None:
        if evidence.subject_type == "modeling.linear_viscoelastic_calibration_plan":
            if self._plan_projector is None:
                raise ReviewConflict("linear-viscoelastic Plan approval projector is unavailable")
            self._plan_projector.project(
                session=session,
                context=context,
                review_request_id=review_request_id,
                review_decision_id=review_decision_id,
                evidence=evidence,
                approved_by=published_by,
                occurred_at=occurred_at,
            )
            return
        subject_identity = _subject_identity_tables.get(evidence.subject_type)
        if subject_identity is None:
            raise ReviewConflict("review subject identity is not registered")
        current_subject_revision = session.execute(
            sa.select(subject_identity.c.current_revision_id).where(
                subject_identity.c.organization_id == context.organization_id,
                subject_identity.c.project_id == context.project_id,
                subject_identity.c.classification == evidence.classification.value,
                subject_identity.c.id == evidence.subject_id,
            )
        ).scalar_one_or_none()
        if current_subject_revision != evidence.subject_revision_id:
            raise ReviewConflict("review subject revision is not current")
        record_id = evidence.affected_record_id
        record_revision_id = evidence.affected_record_revision_id
        record_table_id = evidence.affected_table_id
        record_table_revision_id = evidence.affected_table_revision_id
        material_id = evidence.affected_material_id
        material_revision_id = evidence.affected_material_revision_id
        if record_id is not None and record_revision_id is not None:
            if record_table_id is None or record_table_revision_id is None:
                raise ReviewConflict(
                    "approved review evidence must identify the exact Record table revision"
                )
            current_record_revision = session.execute(
                sa.select(catalog_record_table.c.current_revision_id).where(
                    catalog_record_table.c.organization_id == context.organization_id,
                    catalog_record_table.c.project_id == context.project_id,
                    catalog_record_table.c.id == record_id,
                )
            ).scalar_one_or_none()
            if current_record_revision != record_revision_id:
                raise ReviewConflict("affected Materials Record revision is not current")
            if evidence.subject_type == "catalog.configurable_record":
                if (
                    evidence.subject_id != record_id
                    or evidence.subject_revision_id != record_revision_id
                ):
                    raise ReviewConflict("Record review must publish its exact reviewed revision")
            else:
                kind = evidence.subject_type.rsplit(".", 1)[-1]
                # The catalog binding uses the stable domain_kind vocabulary.  Neutral/model
                # subjects are normalized to their registered source kind here.
                kind = {
                    "test_data_document": "test_data",
                    "material_model": "material_model",
                    "solver_card": "solver_card",
                    "neutral_solver_card": "neutral_solver_card",
                }.get(kind, kind)
                binding = session.execute(
                    sa.select(domain_record_binding_table.c.record_id).where(
                        domain_record_binding_table.c.organization_id == context.organization_id,
                        domain_record_binding_table.c.project_id == context.project_id,
                        domain_record_binding_table.c.domain_kind == kind,
                        domain_record_binding_table.c.domain_object_id == evidence.subject_id,
                        domain_record_binding_table.c.domain_revision_id
                        == evidence.subject_revision_id,
                        domain_record_binding_table.c.record_id == record_id,
                        domain_record_binding_table.c.record_revision_id == record_revision_id,
                    )
                ).scalar_one_or_none()
                if binding != record_id:
                    raise ReviewConflict(
                        "review subject does not have the current exact Record binding"
                    )
        elif (
            evidence.subject_type == "datasets.test_data_document"
            and material_id is not None
            and material_revision_id is not None
            and record_table_id is None
            and record_table_revision_id is None
        ):
            exact_material_revision = session.execute(
                sa.select(catalog_material_revision_table.c.id).where(
                    catalog_material_revision_table.c.organization_id == context.organization_id,
                    catalog_material_revision_table.c.project_id == context.project_id,
                    catalog_material_revision_table.c.classification
                    == evidence.classification.value,
                    catalog_material_revision_table.c.aggregate_id == material_id,
                    catalog_material_revision_table.c.id == material_revision_id,
                )
            ).scalar_one_or_none()
            if exact_material_revision is None:
                raise ReviewConflict("affected governed Material revision is not visible")
        else:
            raise ReviewConflict(
                "approved review evidence must identify an exact Material or Materials Record"
            )
        values: dict[str, Any] = {
            "organization_id": context.organization_id,
            "project_id": context.project_id,
            "classification": evidence.classification.value,
            "review_request_id": review_request_id,
            "subject_type": evidence.subject_type,
            "subject_id": evidence.subject_id,
            "subject_revision_id": evidence.subject_revision_id,
            "neutral_material_id": evidence.neutral_material_id,
            "neutral_material_revision_id": evidence.neutral_material_revision_id,
            "neutral_artifact_sha256": evidence.neutral_artifact_sha256,
            "material_id": material_id,
            "material_revision_id": material_revision_id,
            "record_id": record_id,
            "record_revision_id": record_revision_id,
            "record_table_id": record_table_id,
            "record_table_revision_id": record_table_revision_id,
            "published_at": occurred_at,
            "published_by": published_by,
        }
        session.execute(sa.insert(review_publication_projection_table).values(**values))
        # Catalog publication_marker is a Record-facing contract.  The immutable
        # review_publication_projection carries the governed subject identity; Materials
        # re-evaluates that subject and its exact binding at query time.
        if record_id is not None and record_revision_id is not None:
            session.execute(
                pg_insert(catalog_publication_marker_table)
                .values(
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    classification=evidence.classification.value,
                    aggregate_type="catalog.configurable_record",
                    aggregate_id=record_id,
                    revision_id=record_revision_id,
                    published_at=occurred_at,
                    published_by=published_by,
                )
                .on_conflict_do_nothing()
            )
