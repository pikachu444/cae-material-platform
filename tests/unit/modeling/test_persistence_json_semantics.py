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
