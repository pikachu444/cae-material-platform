"""Atomic Catalog ownership projections for promoted Modeling and Exporting revisions.

The Modeling revision transaction calls this hook after a Neutral Material
revision is written.  When the exact Material Model revision already has a
Catalog owner, the hook projects that same owner to the Neutral Material.  A
missing model owner is intentionally a no-op: unrelated Modeling workflows do
not need a Catalog row.  Existing or stale ownership is never repaired by
guessing; it fails the transaction with an actionable conflict.

Exporting revision stores use the same transaction hook for Solver Cards.  A
Solver Card is projected only to the exact existing owner of its pinned source
revision; this keeps the card revision and its Catalog binding in one commit.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from cmp.shared.adapters.persistence.revisions import SqlRevisionHook
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord


class NeutralMaterialCatalogBindingConflict(RuntimeError):
    """The exact Catalog owner cannot be established without guessing."""


metadata = sa.MetaData()

neutral_material_revision = sa.Table(
    "neutral_material_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("processing_output_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
    schema="modeling",
)
material_model_revision = sa.Table(
    "material_model_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_id", sa.Uuid(), nullable=False),
    sa.Column("material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_id", sa.Uuid(), nullable=False),
    sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
    sa.Column("model_family_id", sa.String(255), nullable=False),
    sa.Column("model_schema_digest", sa.String(64), nullable=False),
    sa.Column("processing_source_document_id", sa.Uuid(), nullable=True),
    sa.Column("processing_source_document_revision_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_id", sa.Uuid(), nullable=True),
    sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
    schema="modeling",
)
material_model_identity = sa.Table(
    "material_model",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    schema="modeling",
)
solver_card_revision = sa.Table(
    "solver_card_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    schema="exporting",
)
neutral_solver_card_revision = sa.Table(
    "neutral_solver_card_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=False),
    schema="exporting",
)
catalog_record = sa.Table(
    "catalog_record",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    schema="catalog",
)
domain_record_identity_binding = sa.Table(
    "domain_record_identity_binding",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)
domain_record_binding = sa.Table(
    "domain_record_binding",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("record_id", sa.Uuid(), nullable=False),
    sa.Column("record_revision_id", sa.Uuid(), nullable=False),
    sa.Column("domain_kind", sa.String(32), nullable=False),
    sa.Column("domain_object_id", sa.Uuid(), nullable=False),
    sa.Column("domain_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    schema="catalog",
)


def _current_catalog_owner(
    session: Session,
    *,
    organization_id: UUID,
    project_id: UUID,
    classification: str,
    domain_kind: str,
    domain_object_id: UUID,
    domain_revision_id: UUID,
) -> tuple[UUID, UUID] | None:
    """Resolve one current owner, rejecting stale or conflicting projections."""

    rows = (
        session.execute(
            sa.select(
                domain_record_identity_binding.c.record_id,
                domain_record_binding.c.record_revision_id,
                catalog_record.c.current_revision_id,
            )
            .select_from(
                domain_record_identity_binding.join(
                    domain_record_binding,
                    sa.and_(
                        domain_record_binding.c.organization_id
                        == domain_record_identity_binding.c.organization_id,
                        domain_record_binding.c.project_id
                        == domain_record_identity_binding.c.project_id,
                        domain_record_binding.c.classification
                        == domain_record_identity_binding.c.classification,
                        domain_record_binding.c.domain_kind
                        == domain_record_identity_binding.c.domain_kind,
                        domain_record_binding.c.domain_object_id
                        == domain_record_identity_binding.c.domain_object_id,
                        domain_record_binding.c.domain_revision_id
                        == domain_record_identity_binding.c.domain_revision_id,
                        domain_record_binding.c.record_id
                        == domain_record_identity_binding.c.record_id,
                    ),
                ).join(
                    catalog_record,
                    sa.and_(
                        catalog_record.c.organization_id
                        == domain_record_binding.c.organization_id,
                        catalog_record.c.project_id == domain_record_binding.c.project_id,
                        catalog_record.c.classification
                        == domain_record_binding.c.classification,
                        catalog_record.c.id == domain_record_binding.c.record_id,
                    ),
                )
            )
            .where(
                domain_record_identity_binding.c.organization_id == organization_id,
                domain_record_identity_binding.c.project_id == project_id,
                domain_record_identity_binding.c.classification == classification,
                domain_record_identity_binding.c.domain_kind == domain_kind,
                domain_record_identity_binding.c.domain_object_id == domain_object_id,
                domain_record_identity_binding.c.domain_revision_id == domain_revision_id,
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        identity_exists = session.scalar(
            sa.select(sa.literal(True)).where(
                domain_record_identity_binding.c.organization_id == organization_id,
                domain_record_identity_binding.c.project_id == project_id,
                domain_record_identity_binding.c.classification == classification,
                domain_record_identity_binding.c.domain_kind == domain_kind,
                domain_record_identity_binding.c.domain_object_id == domain_object_id,
                domain_record_identity_binding.c.domain_revision_id == domain_revision_id,
            )
        )
        if identity_exists:
            raise NeutralMaterialCatalogBindingConflict(
                f"exact {domain_kind} Catalog owner is stale or incomplete"
            )
        binding_exists = session.scalar(
            sa.select(sa.literal(True)).where(
                domain_record_binding.c.organization_id == organization_id,
                domain_record_binding.c.project_id == project_id,
                domain_record_binding.c.classification == classification,
                domain_record_binding.c.domain_kind == domain_kind,
                domain_record_binding.c.domain_object_id == domain_object_id,
                domain_record_binding.c.domain_revision_id == domain_revision_id,
            )
        )
        if binding_exists:
            raise NeutralMaterialCatalogBindingConflict(
                f"exact {domain_kind} Catalog owner is stale or incomplete"
            )
        return None

    if any(row["record_revision_id"] != row["current_revision_id"] for row in rows):
        raise NeutralMaterialCatalogBindingConflict(
            f"exact {domain_kind} Catalog owner points to a stale Record revision"
        )
    owners = {(row["record_id"], row["record_revision_id"]) for row in rows}
    if len({record_id for record_id, _ in owners}) != 1 or len(owners) != 1:
        raise NeutralMaterialCatalogBindingConflict(
            f"exact {domain_kind} revision has conflicting Catalog owners"
        )
    return next(iter(owners))


def _owner_for_model(
    session: Session,
    *,
    organization_id: UUID,
    project_id: UUID,
    classification: str,
    model_id: UUID,
    model_revision_id: UUID,
) -> tuple[UUID, UUID] | None:
    """Return one current Catalog owner for an exact model revision."""

    return _current_catalog_owner(
        session,
        organization_id=organization_id,
        project_id=project_id,
        classification=classification,
        domain_kind="material_model",
        domain_object_id=model_id,
        domain_revision_id=model_revision_id,
    )


def _owner_for_neutral(
    session: Session,
    *,
    organization_id: UUID,
    project_id: UUID,
    classification: str,
    neutral_id: UUID,
    neutral_revision_id: UUID,
) -> tuple[UUID, UUID] | None:
    return _current_catalog_owner(
        session,
        organization_id=organization_id,
        project_id=project_id,
        classification=classification,
        domain_kind="neutral_material",
        domain_object_id=neutral_id,
        domain_revision_id=neutral_revision_id,
    )


def catalog_binding_for_neutral_material(
    session: Session, created: RevisionCreated
) -> None:
    """Project an exact existing model owner to a newly created Neutral revision."""

    revision = created.revision
    if revision.aggregate_type != "modeling.neutral_material":
        return
    neutral = session.execute(
        sa.select(neutral_material_revision).where(
            neutral_material_revision.c.organization_id == revision.scope.organization_id,
            neutral_material_revision.c.project_id == revision.scope.project_id,
            neutral_material_revision.c.classification == revision.scope.classification,
            neutral_material_revision.c.aggregate_id == revision.aggregate_id,
            neutral_material_revision.c.id == revision.revision_id,
        )
    ).mappings().one_or_none()
    if neutral is None:
        raise NeutralMaterialCatalogBindingConflict(
            "created Neutral Material revision is missing its typed source projection"
        )

    model_query = sa.select(
        material_model_revision.c.aggregate_id,
        material_model_revision.c.id,
    ).where(
        material_model_revision.c.organization_id == revision.scope.organization_id,
        material_model_revision.c.project_id == revision.scope.project_id,
        material_model_revision.c.classification == revision.scope.classification,
        material_model_revision.c.material_id == neutral["material_id"],
        material_model_revision.c.material_revision_id == neutral["material_revision_id"],
        material_model_revision.c.material_state_id == neutral["material_state_id"],
        material_model_revision.c.material_state_revision_id
        == neutral["material_state_revision_id"],
    )
    if neutral["processing_output_id"] is not None:
        model_query = model_query.where(
            material_model_revision.c.processing_output_id == neutral["processing_output_id"],
            material_model_revision.c.processing_output_revision_id
            == neutral["processing_output_revision_id"],
        )
    models = session.execute(model_query).mappings().all()
    if not models:
        # Modeling-only flows legitimately have no Catalog owner.
        return
    owners: set[tuple[UUID, UUID]] = set()
    for model in models:
        owner = _owner_for_model(
            session,
            organization_id=revision.scope.organization_id,
            project_id=revision.scope.project_id,
            classification=revision.scope.classification,
            model_id=model["aggregate_id"],
            model_revision_id=model["id"],
        )
        if owner is not None:
            owners.add(owner)
    if len(owners) > 1:
        raise NeutralMaterialCatalogBindingConflict(
            "Neutral Material promotion resolves conflicting exact Material Model owners"
        )
    if not owners:
        return
    record_id, record_revision_id = next(iter(owners))
    current_owner = _owner_for_neutral(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        neutral_id=revision.aggregate_id,
        neutral_revision_id=revision.revision_id,
    )
    if current_owner is not None and current_owner != (record_id, record_revision_id):
        raise NeutralMaterialCatalogBindingConflict(
            "Neutral Material already has a conflicting exact Catalog owner"
        )
    if current_owner == (record_id, record_revision_id):
        return

    now = revision.created_at
    identity_values = {
        "organization_id": revision.scope.organization_id,
        "project_id": revision.scope.project_id,
        "classification": revision.scope.classification,
        "domain_kind": "neutral_material",
        "domain_object_id": revision.aggregate_id,
        "domain_revision_id": revision.revision_id,
        "record_id": record_id,
        "created_at": now,
        "created_by": revision.created_by,
        "request_id": revision.request_id,
        "trace_id": revision.trace_id,
    }
    session.execute(
        postgresql.insert(domain_record_identity_binding)
        .values(**identity_values)
        .on_conflict_do_nothing()
    )
    binding_id = uuid5(
        NAMESPACE_URL,
        f"urn:cmp:catalog-neutral-material:{revision.scope.organization_id}:"
        f"{revision.scope.project_id}:{revision.scope.classification}:"
        f"{revision.aggregate_id}:{revision.revision_id}",
    )
    session.execute(
        postgresql.insert(domain_record_binding)
        .values(id=binding_id, record_revision_id=record_revision_id, **identity_values)
        .on_conflict_do_nothing()
    )
    persisted = _owner_for_neutral(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        neutral_id=revision.aggregate_id,
        neutral_revision_id=revision.revision_id,
    )
    if persisted != (record_id, record_revision_id):
        raise NeutralMaterialCatalogBindingConflict(
            "Neutral Material Catalog binding did not persist its exact owner"
        )


def catalog_binding_for_material_model(
    session: Session, created: RevisionCreated
) -> None:
    """Project a new model to the unique exact peer model Record owner.

    Modeling creates append-only revisions without a Catalog dependency.  A
    source-v2 workflow may already expose the same governed model lineage in a
    Catalog Record, however.  Only that exact peer (material/state, model
    family, and source document) may supply ownership; the schema digest is a
    representation-level revision detail and may differ between the seeded
    1.3 model and the direct Fit 1.2 representation.  The base Material
    Record is deliberately not a fallback because it belongs to
    ``technical_data``.
    """

    revision = created.revision
    if revision.aggregate_type != "modeling.material_model":
        return
    model = session.execute(
        sa.select(material_model_revision).where(
            material_model_revision.c.organization_id == revision.scope.organization_id,
            material_model_revision.c.project_id == revision.scope.project_id,
            material_model_revision.c.classification == revision.scope.classification,
            material_model_revision.c.aggregate_id == revision.aggregate_id,
            material_model_revision.c.id == revision.revision_id,
        )
    ).mappings().one_or_none()
    if model is None:
        raise NeutralMaterialCatalogBindingConflict(
            "created Material Model revision is missing its typed source projection"
        )
    if model["processing_source_document_id"] is None:
        # There is no governed source lineage from which to identify a Catalog
        # model Record.  Do not match an unrelated NULL-source peer.
        return
    peers_query = sa.select(
        material_model_revision.c.aggregate_id,
        material_model_revision.c.id,
    ).select_from(
        material_model_revision.join(
            material_model_identity,
            sa.and_(
                material_model_identity.c.organization_id
                == material_model_revision.c.organization_id,
                material_model_identity.c.project_id == material_model_revision.c.project_id,
                material_model_identity.c.classification
                == material_model_revision.c.classification,
                material_model_identity.c.id == material_model_revision.c.aggregate_id,
                material_model_identity.c.current_revision_id == material_model_revision.c.id,
            ),
        )
    ).where(
        material_model_revision.c.organization_id == revision.scope.organization_id,
        material_model_revision.c.project_id == revision.scope.project_id,
        material_model_revision.c.classification == revision.scope.classification,
        material_model_revision.c.aggregate_id != revision.aggregate_id,
        material_model_revision.c.id != revision.revision_id,
        material_model_revision.c.material_id == model["material_id"],
        material_model_revision.c.material_revision_id == model["material_revision_id"],
        material_model_revision.c.material_state_id == model["material_state_id"],
        material_model_revision.c.material_state_revision_id
        == model["material_state_revision_id"],
        material_model_revision.c.model_family_id == model["model_family_id"],
        material_model_revision.c.processing_source_document_id
        == model["processing_source_document_id"],
        material_model_revision.c.processing_source_document_revision_id
        == model["processing_source_document_revision_id"],
    )
    peers = session.execute(peers_query).mappings().all()
    owners: set[tuple[UUID, UUID]] = set()
    for peer in peers:
        owner = _owner_for_model(
            session,
            organization_id=revision.scope.organization_id,
            project_id=revision.scope.project_id,
            classification=revision.scope.classification,
            model_id=peer["aggregate_id"],
            model_revision_id=peer["id"],
        )
        if owner is not None:
            owners.add(owner)
    if len(owners) > 1:
        raise NeutralMaterialCatalogBindingConflict(
            "Material Model lineage resolves conflicting exact Catalog owners"
        )
    if owners:
        _project_catalog_binding(
            session,
            revision=revision,
            domain_kind="material_model",
            record_owner=next(iter(owners)),
        )


def _project_catalog_binding(
    session: Session,
    *,
    revision: RevisionRecord,
    domain_kind: str,
    record_owner: tuple[UUID, UUID],
) -> None:
    """Persist an exact domain owner without creating a Catalog record."""

    record_id, record_revision_id = record_owner
    current_owner = _current_catalog_owner(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        domain_kind=domain_kind,
        domain_object_id=revision.aggregate_id,
        domain_revision_id=revision.revision_id,
    )
    if current_owner is not None and current_owner != record_owner:
        raise NeutralMaterialCatalogBindingConflict(
            f"{domain_kind} already has a conflicting exact Catalog owner"
        )
    if current_owner == record_owner:
        return

    identity_values = {
        "organization_id": revision.scope.organization_id,
        "project_id": revision.scope.project_id,
        "classification": revision.scope.classification,
        "domain_kind": domain_kind,
        "domain_object_id": revision.aggregate_id,
        "domain_revision_id": revision.revision_id,
        "record_id": record_id,
        "created_at": revision.created_at,
        "created_by": revision.created_by,
        "request_id": revision.request_id,
        "trace_id": revision.trace_id,
    }
    session.execute(
        postgresql.insert(domain_record_identity_binding)
        .values(**identity_values)
        .on_conflict_do_nothing()
    )
    if domain_kind == "neutral_solver_card":
        # Target Delivery's receipt hook uses this stable key before recording
        # its outbox receipt.  Keep direct and Target Delivery creation
        # idempotent across both paths.
        binding_namespace = (
            f"urn:cmp:{revision.scope.organization_id}:{revision.scope.project_id}:"
            f"{revision.scope.classification}:{domain_kind}:"
            f"{revision.aggregate_id}:{revision.revision_id}"
        )
    else:
        binding_namespace = (
            f"urn:cmp:catalog-{domain_kind}:{revision.scope.organization_id}:"
            f"{revision.scope.project_id}:{revision.scope.classification}:"
            f"{revision.aggregate_id}:{revision.revision_id}"
        )
    binding_id = uuid5(NAMESPACE_URL, binding_namespace)
    session.execute(
        postgresql.insert(domain_record_binding)
        .values(id=binding_id, record_revision_id=record_revision_id, **identity_values)
        .on_conflict_do_nothing()
    )
    persisted = _current_catalog_owner(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        domain_kind=domain_kind,
        domain_object_id=revision.aggregate_id,
        domain_revision_id=revision.revision_id,
    )
    if persisted != record_owner:
        raise NeutralMaterialCatalogBindingConflict(
            f"{domain_kind} Catalog binding did not persist its exact owner"
        )


def catalog_binding_for_solver_card(
    session: Session, created: RevisionCreated
) -> None:
    """Project a legacy/reference Solver Card to its exact Model owner."""

    revision = created.revision
    if revision.aggregate_type != "exporting.solver_card":
        return
    card = session.execute(
        sa.select(
            solver_card_revision.c.material_model_id,
            solver_card_revision.c.material_model_revision_id,
        ).where(
            solver_card_revision.c.organization_id == revision.scope.organization_id,
            solver_card_revision.c.project_id == revision.scope.project_id,
            solver_card_revision.c.classification == revision.scope.classification,
            solver_card_revision.c.aggregate_id == revision.aggregate_id,
            solver_card_revision.c.id == revision.revision_id,
        )
    ).mappings().one_or_none()
    if card is None:
        raise NeutralMaterialCatalogBindingConflict(
            "created Solver Card revision is missing its typed source projection"
        )
    owner = _owner_for_model(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        model_id=card["material_model_id"],
        model_revision_id=card["material_model_revision_id"],
    )
    if owner is not None:
        _project_catalog_binding(
            session,
            revision=revision,
            domain_kind="solver_card",
            record_owner=owner,
        )


def catalog_binding_for_neutral_solver_card(
    session: Session, created: RevisionCreated
) -> None:
    """Project a Neutral Solver Card to its exact Neutral Material owner."""

    revision = created.revision
    if revision.aggregate_type != "exporting.neutral_solver_card":
        return
    card = session.execute(
        sa.select(
            neutral_solver_card_revision.c.neutral_material_id,
            neutral_solver_card_revision.c.neutral_material_revision_id,
        ).where(
            neutral_solver_card_revision.c.organization_id == revision.scope.organization_id,
            neutral_solver_card_revision.c.project_id == revision.scope.project_id,
            neutral_solver_card_revision.c.classification == revision.scope.classification,
            neutral_solver_card_revision.c.aggregate_id == revision.aggregate_id,
            neutral_solver_card_revision.c.id == revision.revision_id,
        )
    ).mappings().one_or_none()
    if card is None:
        raise NeutralMaterialCatalogBindingConflict(
            "created Neutral Solver Card revision is missing its typed source projection"
        )
    owner = _owner_for_neutral(
        session,
        organization_id=revision.scope.organization_id,
        project_id=revision.scope.project_id,
        classification=revision.scope.classification,
        neutral_id=card["neutral_material_id"],
        neutral_revision_id=card["neutral_material_revision_id"],
    )
    if owner is not None:
        _project_catalog_binding(
            session,
            revision=revision,
            domain_kind="neutral_solver_card",
            record_owner=owner,
        )


def make_catalog_ownership_projection_hook() -> SqlRevisionHook:
    """Return the composition-bound hook for all Catalog-owned revisions."""

    def hook(session: Session, created: RevisionCreated) -> None:
        catalog_binding_for_material_model(session, created)
        catalog_binding_for_neutral_material(session, created)
        catalog_binding_for_solver_card(session, created)
        catalog_binding_for_neutral_solver_card(session, created)

    return hook


def make_neutral_material_catalog_binding_hook() -> SqlRevisionHook:
    """Return the composition-bound hook without exposing Catalog services to Modeling."""

    def hook(session: Session, created: RevisionCreated) -> None:
        catalog_binding_for_neutral_material(session, created)

    return hook


def make_material_model_catalog_binding_hook() -> SqlRevisionHook:
    """Return the composition-bound hook for Material Model ownership only."""

    def hook(session: Session, created: RevisionCreated) -> None:
        catalog_binding_for_material_model(session, created)

    return hook


__all__ = [
    "NeutralMaterialCatalogBindingConflict",
    "catalog_binding_for_material_model",
    "catalog_binding_for_neutral_material",
    "catalog_binding_for_neutral_solver_card",
    "catalog_binding_for_solver_card",
    "make_catalog_ownership_projection_hook",
    "make_material_model_catalog_binding_hook",
    "make_neutral_material_catalog_binding_hook",
]
