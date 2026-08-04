import sqlalchemy as sa
from cmp.modules.modeling.adapters.persistence.linear_viscoelasticity_repository import (
    linear_viscoelastic_processing_evidence_table,
)
from cmp.modules.modeling.adapters.persistence.neutral_material_repository import (
    neutral_material_revision_table,
)
from cmp.modules.modeling.adapters.persistence.repository import material_model_revision_table
from cmp.modules.processing.adapters.persistence.common_outputs import revision_table
from sqlalchemy.dialects import postgresql


def test_fit_decision_evidence_binds_python_none_as_sql_null() -> None:
    columns = (
        material_model_revision_table.c.fit_decision_evidence,
        linear_viscoelastic_processing_evidence_table.c.fit_decision_evidence,
        neutral_material_revision_table.c.fit_decision_evidence,
        revision_table.c.fit_decision,
    )

    for column in columns:
        processor = column.type.bind_processor(postgresql.dialect())

        assert processor is not None
        assert processor(None) is None


def test_processing_fit_decision_sqlite_probe_preserves_null_and_object_history() -> None:
    metadata = sa.MetaData()
    probe = sa.Table(
        "fit_decision_probe",
        metadata,
        sa.Column("revision_no", sa.Integer, primary_key=True),
        sa.Column("fit_decision", revision_table.c.fit_decision.type, nullable=True),
    )
    prior_decision = {"candidate_key": "prior", "mode": "single"}
    current_decision = {"candidate_key": "current", "mode": "blend"}

    engine = sa.create_engine("sqlite:///:memory:")
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                sa.insert(probe),
                [
                    {"revision_no": 1, "fit_decision": None},
                    {"revision_no": 2, "fit_decision": prior_decision},
                    {"revision_no": 3, "fit_decision": current_decision},
                ],
            )
            persisted = connection.execute(
                sa.select(probe).order_by(probe.c.revision_no)
            ).mappings().all()
            storage = connection.execute(
                sa.text(
                    "SELECT revision_no, fit_decision IS NULL AS is_sql_null, "
                    "json_type(fit_decision) AS json_kind "
                    "FROM fit_decision_probe ORDER BY revision_no"
                )
            ).mappings().all()
    finally:
        engine.dispose()

    assert [dict(row) for row in persisted] == [
        {"revision_no": 1, "fit_decision": None},
        {"revision_no": 2, "fit_decision": prior_decision},
        {"revision_no": 3, "fit_decision": current_decision},
    ]
    assert [dict(row) for row in storage] == [
        {"revision_no": 1, "is_sql_null": 1, "json_kind": None},
        {"revision_no": 2, "is_sql_null": 0, "json_kind": "object"},
        {"revision_no": 3, "is_sql_null": 0, "json_kind": "object"},
    ]
