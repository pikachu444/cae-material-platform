from __future__ import annotations

from uuid import uuid4

from cmp.modules.catalog.adapters.persistence.records import (
    SqlAlchemyCatalogRecordRepository,
)
from cmp.modules.catalog.domain.records import CatalogRecordQuery
from sqlalchemy.dialects import postgresql


def test_published_materials_query_rechecks_review_subject_and_record_heads() -> None:
    statement = SqlAlchemyCatalogRecordRepository._filtered_statement(
        CatalogRecordQuery(uuid4(), published_only=True)
    )
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
    sql = str(compiled)

    assert "governance.review_publication_projection" in sql
    assert "review_subject_current_head" in sql
    assert "catalog.domain_record_binding" in sql
    assert "catalog.catalog_record.current_revision_id" in sql
    assert "exporting.neutral_solver_card" in sql
    assert "modeling.neutral_material" in sql
    assert "neutral_material_id" in sql
    assert "neutral_material_revision_id" in sql


def test_configurable_record_publication_requires_the_same_exact_domain_binding() -> None:
    statement = SqlAlchemyCatalogRecordRepository._filtered_statement(
        CatalogRecordQuery(
            uuid4(),
            published_only=True,
            domain_binding_kind="neutral_material",
            domain_binding_object_id=uuid4(),
            domain_binding_revision_id=uuid4(),
        )
    )
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
    sql = str(compiled)

    assert (
        "governance.review_publication_projection.subject_id = "
        "governance.review_publication_projection.record_id"
    ) in sql
    assert (
        "governance.review_publication_projection.subject_revision_id = "
        "governance.review_publication_projection.record_revision_id"
    ) in sql
    assert (
        "catalog.domain_record_binding.record_id = "
        "governance.review_publication_projection.record_id"
    ) in sql
    assert (
        "catalog.domain_record_binding.record_revision_id = "
        "governance.review_publication_projection.record_revision_id"
    ) in sql
    assert "catalog.domain_record_binding.domain_kind" in sql
    assert "catalog.domain_record_binding.domain_object_id" in sql
    assert "catalog.domain_record_binding.domain_revision_id" in sql
    # A neutral-material query may only match the exact configurable-record
    # subject branch.  The model/card subject heads remain in the currentness
    # union, but their neutral pins must not be compared with the requested
    # domain object/revision as a fallback binding.
    assert compiled.params["subject_type_2"] == "catalog.configurable_record"
    assert compiled.params["subject_type_8"] == [
        "modeling.material_model",
        "exporting.solver_card",
    ]
    assert (
        "governance.review_publication_projection.neutral_material_id = "
        "%(domain_object_id_1)s"
    ) not in sql
    assert (
        "governance.review_publication_projection.neutral_material_revision_id = "
        "%(domain_revision_id_1)s"
    ) not in sql
