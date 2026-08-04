from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from cmp.modules.datasets.adapters.persistence.canonical_test_data import (
    document_revision_table,
)
from cmp.modules.processing.adapters.persistence.common_outputs import revision_table
from sqlalchemy.engine import make_url

POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.skipif(
        not POSTGRES_DSN,
        reason="CMP_TEST_POSTGRES_DSN is required for PostgreSQL integration",
    ),
]


def _postgres_url() -> sa.URL:
    assert POSTGRES_DSN is not None
    value = make_url(POSTGRES_DSN)
    if value.drivername in {"postgres", "postgresql"}:
        return value.set(drivername="postgresql+psycopg")
    return value


def test_nullable_provenance_binds_sql_null_and_preserves_old_history() -> None:
    """Exercise migration 088's JSONB constraint with the production bind types."""

    metadata = sa.MetaData()
    history = sa.Table(
        "uxc06c1_nullable_provenance",
        metadata,
        sa.Column("revision_no", sa.Integer, primary_key=True),
        sa.Column("governed_source", document_revision_table.c.governed_source.type),
        sa.Column("export_provenance", revision_table.c.export_provenance.type),
        sa.Column("fit_decision", revision_table.c.fit_decision.type),
    )
    engine = sa.create_engine(_postgres_url())
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "CREATE TEMPORARY TABLE uxc06c1_nullable_provenance ("
                    "revision_no integer PRIMARY KEY, "
                    "governed_source jsonb NULL CHECK (governed_source IS NULL "
                    "OR jsonb_typeof(governed_source) = 'object'), "
                    "export_provenance jsonb NULL CHECK (export_provenance IS NULL "
                    "OR jsonb_typeof(export_provenance) = 'object'), "
                    "fit_decision jsonb NULL CHECK (fit_decision IS NULL "
                    "OR jsonb_typeof(fit_decision) = 'object'))"
                )
            )
            connection.execute(
                sa.insert(history).values(
                    revision_no=1,
                    governed_source=None,
                    export_provenance=None,
                    fit_decision=None,
                )
            )
            proof = {
                "material": {"aggregate_id": "material-1", "revision_id": "material-r1"},
                "material_state": {"aggregate_id": "state-1", "revision_id": "state-r1"},
                "test_run": {"aggregate_id": "run-1", "revision_id": "run-r1"},
            }
            connection.execute(
                sa.insert(history).values(
                    revision_no=2,
                    governed_source=proof,
                    export_provenance=proof,
                    fit_decision=proof,
                )
            )
            rows = connection.execute(
                sa.text(
                    "SELECT revision_no, governed_source IS NULL AS source_is_sql_null, "
                    "jsonb_typeof(governed_source) AS source_kind, "
                    "jsonb_typeof(export_provenance) AS export_kind, "
                    "fit_decision IS NULL AS fit_is_sql_null, "
                    "jsonb_typeof(fit_decision) AS fit_kind "
                    "FROM uxc06c1_nullable_provenance ORDER BY revision_no"
                )
            ).mappings().all()
    finally:
        engine.dispose()

    assert rows == [
        {
            "revision_no": 1,
            "source_is_sql_null": True,
            "source_kind": None,
            "export_kind": None,
            "fit_is_sql_null": True,
            "fit_kind": None,
        },
        {
            "revision_no": 2,
            "source_is_sql_null": False,
            "source_kind": "object",
            "export_kind": "object",
            "fit_is_sql_null": False,
            "fit_kind": "object",
        },
    ]
