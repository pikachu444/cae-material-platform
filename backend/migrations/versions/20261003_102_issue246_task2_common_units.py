"""Issue #246 Task 2 additive common speed and density units.

Revision ID: 20261003_102_issue246_units
Revises: 20261002_101_issue289_delete
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261003_102_issue246_units"
down_revision: str | None = "20261002_101_issue289_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DIMENSIONS_1_0 = (
    "dimension IN ('force_per_area','length','time','force','mass',"
    "'mass_per_volume','temperature','strain')"
)
_DIMENSIONS_1_1 = (
    "dimension IN ('force_per_area','length','speed','time','force','mass',"
    "'mass_per_volume','temperature','strain')"
)
_UNITS_1_0 = """
  (dimension = 'force_per_area' AND {column} IN ('Pa','kPa','MPa','GPa')) OR
  (dimension = 'length' AND {column} IN ('m','cm','mm','um')) OR
  (dimension = 'time' AND {column} IN ('s','ms','min','h')) OR
  (dimension = 'force' AND {column} IN ('N','kN')) OR
  (dimension = 'mass' AND {column} IN ('kg','g','mg')) OR
  (dimension = 'mass_per_volume' AND {column} IN ('kg/m3','g/cm3')) OR
  (dimension = 'temperature' AND {column} IN ('K','Cel')) OR
  (dimension = 'strain' AND {column} IN ('1','%'))
"""
_UNITS_1_1 = """
  (dimension = 'force_per_area' AND {column} IN ('Pa','kPa','MPa','GPa')) OR
  (dimension = 'length' AND {column} IN ('m','cm','mm','um')) OR
  (dimension = 'speed' AND {column} IN ('m/s','mm/s','mm/min')) OR
  (dimension = 'time' AND {column} IN ('s','ms','min','h')) OR
  (dimension = 'force' AND {column} IN ('N','kN')) OR
  (dimension = 'mass' AND {column} IN ('kg','g','mg')) OR
  (dimension = 'mass_per_volume' AND {column} IN ('kg/m3','g/cm3','tonne/mm3')) OR
  (dimension = 'temperature' AND {column} IN ('K','Cel')) OR
  (dimension = 'strain' AND {column} IN ('1','%'))
"""
_KG_M_S_1_0 = """
  (dimension = 'force_per_area' AND unit_id = 'Pa') OR
  (dimension = 'length' AND unit_id = 'm') OR
  (dimension = 'time' AND unit_id = 's') OR
  (dimension = 'force' AND unit_id = 'N') OR
  (dimension = 'mass' AND unit_id = 'kg') OR
  (dimension = 'mass_per_volume' AND unit_id = 'kg/m3') OR
  (dimension = 'temperature' AND unit_id = 'K') OR
  (dimension = 'strain' AND unit_id = '1')
"""
_KG_M_S_1_1 = """
  (dimension = 'force_per_area' AND unit_id = 'Pa') OR
  (dimension = 'length' AND unit_id = 'm') OR
  (dimension = 'speed' AND unit_id = 'm/s') OR
  (dimension = 'time' AND unit_id = 's') OR
  (dimension = 'force' AND unit_id = 'N') OR
  (dimension = 'mass' AND unit_id = 'kg') OR
  (dimension = 'mass_per_volume' AND unit_id = 'kg/m3') OR
  (dimension = 'temperature' AND unit_id = 'K') OR
  (dimension = 'strain' AND unit_id = '1')
"""


def _replace_check(table: str, name: str, expression: str) -> None:
    op.execute(
        f"""
        ALTER TABLE {table} DROP CONSTRAINT {name};
        ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression});
        """
    )


def _apply_contract(*, version: str) -> None:
    dimensions = _DIMENSIONS_1_1 if version == "1.1.0" else _DIMENSIONS_1_0
    units = _UNITS_1_1 if version == "1.1.0" else _UNITS_1_0
    kg_m_s = _KG_M_S_1_1 if version == "1.1.0" else _KG_M_S_1_0

    _replace_check(
        "units.unit_profile_selection",
        "ck_units_unit_profile_selection_dimension",
        dimensions,
    )
    for name, column in (
        ("ck_units_unit_profile_selection_input", "input_unit_id"),
        ("ck_units_unit_profile_selection_display", "display_unit_id"),
        ("ck_units_unit_profile_selection_solver", "solver_export_unit_id"),
    ):
        expression = units.format(column=column)
        if column == "solver_export_unit_id":
            expression = f"{column} IS NULL OR ({expression})"
        _replace_check("units.unit_profile_selection", name, expression)

    for table, prefix in (
        (
            "processing.common_processing_output_unit_application",
            "ck_processing_output_unit_application",
        ),
        (
            "processing.metal_fit_run_unit_application",
            "ck_processing_metal_fit_unit_application",
        ),
    ):
        _replace_check(table, f"{prefix}_dimension", dimensions)
        _replace_check(table, f"{prefix}_unit", units.format(column="unit_id"))

    _replace_check(
        "exporting.neutral_solver_card_unit_application",
        "ck_exporting_neutral_card_unit_application_kg_m_s",
        kg_m_s,
    )
    _replace_check(
        "exporting.solver_card_delivery_unit_application",
        "ck_exporting_delivery_unit_application_kg_m_s",
        kg_m_s,
    )


def upgrade() -> None:
    _apply_contract(version="1.1.0")


def downgrade() -> None:
    # PostgreSQL refuses this constraint replacement when immutable 1.1-only
    # evidence still exists; the migration never rewrites or deletes revisions.
    _apply_contract(version="1.0.0")
