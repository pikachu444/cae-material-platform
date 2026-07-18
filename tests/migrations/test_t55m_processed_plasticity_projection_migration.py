from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).parents[2]


def test_t55m_projection_uses_explicit_exact_lineage_and_database_guards() -> None:
    output = StringIO()
    command.upgrade(
        Config(str(PROJECT_ROOT / "alembic.ini"), output_buffer=output),
        "head",
        sql=True,
    )
    sql = output.getvalue()

    for value in (
        "processing_output_id uuid",
        "processing_output_revision_id uuid",
        "processing_source_document_revision_id uuid",
        "processing_mapping_profile_revision_id uuid",
        "hardening_candidate_families jsonb",
        "hardening_primary_family varchar(32)",
        "hardening_primary_weight float8",
        "fk_mdl_model_processing_output_exact",
        "fk_mdl_model_processing_source_exact",
        "fk_mdl_model_processing_profile_exact",
        "processing_recipe_selection",
        "guard_processed_plasticity_projection_insert",
        "metal.hardening_fit_extrapolate",
        "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0",
        "selected_fitted_bounded_extrapolation",
        "ck_exporting_solver_card_extension",
    ):
        assert value in sql
    projection = sql[sql.index("ADD COLUMN processing_output_id uuid") :]
    assert "value_text" not in projection
    assert "attribute_value" not in projection
