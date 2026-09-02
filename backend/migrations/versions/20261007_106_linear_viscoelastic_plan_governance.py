"""Issue #377 immutable linear-viscoelastic Plan governance and exact setup resolution."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261007_106_lve_plan_governance"
down_revision: str | None = "20261006_105_dma_tts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PLAN = "linear_viscoelastic_calibration_plan_revision"
_RUN = "linear_viscoelastic_calibration_run"
_APPROVAL = "linear_viscoelastic_calibration_plan_approval"
_FACT = "linear_viscoelastic_calibration_plan_usability_fact"
_RLS_PREFIX = {
    _APPROVAL: "lve_plan_approval",
    _FACT: "lve_plan_usability_fact",
}


def _rls(table: str) -> None:
    """Keep both read visibility and review-decision writes tenant/classification scoped."""

    prefix = _RLS_PREFIX[table]
    op.execute(f"ALTER TABLE modeling.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE modeling.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {prefix}_select ON modeling.{table} FOR SELECT USING
          (access_control.can_access_row(
             organization_id, project_id, classification, 'modeling.read'));
        CREATE POLICY {prefix}_review_insert ON modeling.{table} FOR INSERT
          WITH CHECK (access_control.can_access_row(
             organization_id, project_id, classification, 'review.decide'));
        """
    )


def _immutable(table: str) -> None:
    trigger_name = f"{_RLS_PREFIX[table]}_immutable"
    op.execute(
        f"""
        CREATE TRIGGER {trigger_name}
          BEFORE UPDATE OR DELETE ON modeling.{table}
          FOR EACH ROW EXECUTE FUNCTION revisioning.reject_immutable_row_mutation();
        """
    )


def upgrade() -> None:
    for column in (
        sa.Column("setup_name", sa.String(length=255), nullable=True),
        sa.Column("material_id", sa.Uuid(), nullable=True),
        sa.Column("material_revision_id", sa.Uuid(), nullable=True),
        sa.Column("material_state_id", sa.Uuid(), nullable=True),
        sa.Column("material_state_revision_id", sa.Uuid(), nullable=True),
        sa.Column("input_mode", sa.String(length=64), nullable=True),
        sa.Column("based_on_plan_id", sa.Uuid(), nullable=True),
        sa.Column("based_on_plan_revision_id", sa.Uuid(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("base_diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    ):
        op.add_column(_PLAN, column, schema="modeling")
    op.create_check_constraint(
        "ck_mdl_lve_plan_governance_shape",
        _PLAN,
        "("
        "setup_name IS NULL AND material_id IS NULL AND material_revision_id IS NULL "
        "AND material_state_id IS NULL AND material_state_revision_id IS NULL "
        "AND input_mode IS NULL AND based_on_plan_id IS NULL "
        "AND based_on_plan_revision_id IS NULL AND override_reason IS NULL AND base_diff IS NULL"
        ") OR ("
        "length(btrim(setup_name)) BETWEEN 1 AND 255 "
        "AND material_id IS NOT NULL AND material_revision_id IS NOT NULL "
        "AND material_state_id IS NOT NULL AND material_state_revision_id IS NOT NULL "
        "AND input_mode IN ('relaxation','dma','dma_frequency_master_curve') "
        "AND ((based_on_plan_id IS NULL AND based_on_plan_revision_id IS NULL "
        "AND override_reason IS NULL AND base_diff IS NULL) OR ("
        "based_on_plan_id IS NOT NULL AND based_on_plan_revision_id IS NOT NULL "
        "AND length(btrim(override_reason)) BETWEEN 1 AND 2000 "
        "AND base_diff IS NOT NULL AND jsonb_typeof(base_diff) = 'object'))"
        ")",
        schema="modeling",
    )
    op.create_foreign_key(
        "fk_mdl_lve_plan_material_revision",
        _PLAN,
        "material_revision",
        ["organization_id", "project_id", "classification", "material_id", "material_revision_id"],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="modeling",
        referent_schema="catalog",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mdl_lve_plan_material_state_revision",
        _PLAN,
        "material_state_revision",
        [
            "organization_id",
            "project_id",
            "classification",
            "material_state_id",
            "material_state_revision_id",
        ],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="modeling",
        referent_schema="catalog",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mdl_lve_plan_base_revision",
        _PLAN,
        _PLAN,
        [
            "organization_id",
            "project_id",
            "classification",
            "based_on_plan_id",
            "based_on_plan_revision_id",
        ],
        ["organization_id", "project_id", "classification", "aggregate_id", "id"],
        source_schema="modeling",
        referent_schema="modeling",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_mdl_lve_plan_exact_source_context",
        _PLAN,
        [
            "organization_id",
            "project_id",
            "classification",
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "test_data_id",
            "test_data_revision_id",
            "input_mode",
        ],
        schema="modeling",
    )

    for column in (
        sa.Column("approval_request_id", sa.Uuid(), nullable=True),
        sa.Column("approval_decision_id", sa.Uuid(), nullable=True),
        sa.Column("approval_evidence_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("approval_state", sa.String(length=32), nullable=True),
        sa.Column("approval_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_approved_by", sa.Uuid(), nullable=True),
        sa.Column("execution_material_id", sa.Uuid(), nullable=True),
        sa.Column("execution_material_revision_id", sa.Uuid(), nullable=True),
        sa.Column("execution_material_state_id", sa.Uuid(), nullable=True),
        sa.Column("execution_material_state_revision_id", sa.Uuid(), nullable=True),
        sa.Column("execution_test_data_id", sa.Uuid(), nullable=True),
        sa.Column("execution_test_data_revision_id", sa.Uuid(), nullable=True),
        sa.Column("execution_test_data_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("execution_processing_output_id", sa.Uuid(), nullable=True),
        sa.Column("execution_processing_output_revision_id", sa.Uuid(), nullable=True),
        sa.Column("execution_processing_output_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("execution_input_mode", sa.String(length=64), nullable=True),
    ):
        op.add_column(_RUN, column, schema="modeling")
    op.create_check_constraint(
        "ck_mdl_lve_run_approval_evidence_shape",
        _RUN,
        "("
        "approval_request_id IS NULL AND approval_decision_id IS NULL "
        "AND approval_evidence_sha256 IS NULL AND approval_state IS NULL "
        "AND approval_approved_at IS NULL AND approval_approved_by IS NULL "
        "AND execution_material_id IS NULL AND execution_material_revision_id IS NULL "
        "AND execution_material_state_id IS NULL AND execution_material_state_revision_id IS NULL "
        "AND execution_test_data_id IS NULL AND execution_test_data_revision_id IS NULL "
        "AND execution_test_data_sha256 IS NULL AND execution_processing_output_id IS NULL "
        "AND execution_processing_output_revision_id IS NULL "
        "AND execution_processing_output_sha256 IS NULL AND execution_input_mode IS NULL"
        ") OR ("
        "approval_request_id IS NOT NULL AND approval_decision_id IS NOT NULL "
        "AND approval_evidence_sha256 ~ '^[0-9a-f]{64}$' AND approval_state = 'active' "
        "AND approval_approved_at IS NOT NULL AND approval_approved_by IS NOT NULL "
        "AND execution_material_id IS NOT NULL AND execution_material_revision_id IS NOT NULL "
        "AND execution_material_state_id IS NOT NULL "
        "AND execution_material_state_revision_id IS NOT NULL "
        "AND execution_test_data_id IS NOT NULL AND execution_test_data_revision_id IS NOT NULL "
        "AND execution_test_data_sha256 ~ '^[0-9a-f]{64}$' "
        "AND execution_input_mode IN ('relaxation','dma','dma_frequency_master_curve') "
        "AND ((execution_processing_output_id IS NULL "
        "AND execution_processing_output_revision_id IS NULL "
        "AND execution_processing_output_sha256 IS NULL) OR ("
        "execution_processing_output_id IS NOT NULL "
        "AND execution_processing_output_revision_id IS NOT NULL "
        "AND execution_processing_output_sha256 ~ '^[0-9a-f]{64}$'))"
        ")",
        schema="modeling",
    )
    op.create_foreign_key(
        "fk_mdl_lve_run_approval_request",
        _RUN,
        "review_request",
        ["organization_id", "project_id", "approval_request_id"],
        ["organization_id", "project_id", "id"],
        source_schema="modeling",
        referent_schema="governance",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_mdl_lve_run_approval_decision",
        _RUN,
        "review_decision",
        ["organization_id", "project_id", "approval_decision_id"],
        ["organization_id", "project_id", "id"],
        source_schema="modeling",
        referent_schema="governance",
        ondelete="RESTRICT",
    )

    op.create_table(
        _APPROVAL,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("plan_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("plan_created_by", sa.Uuid(), nullable=False),
        sa.Column("review_request_id", sa.Uuid(), nullable=False),
        sa.Column("review_decision_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=False),
        sa.Column("setup_name", sa.String(length=255), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("material_revision_id", sa.Uuid(), nullable=False),
        sa.Column("material_state_id", sa.Uuid(), nullable=False),
        sa.Column("material_state_revision_id", sa.Uuid(), nullable=False),
        sa.Column("test_data_id", sa.Uuid(), nullable=False),
        sa.Column("test_data_revision_id", sa.Uuid(), nullable=False),
        sa.Column("test_data_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("processing_output_id", sa.Uuid(), nullable=True),
        sa.Column("processing_output_revision_id", sa.Uuid(), nullable=True),
        sa.Column("processing_output_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("input_mode", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id", "project_id", "plan_id", "plan_revision_id",
            name="pk_mdl_lve_plan_approval",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "review_request_id",
            name="uq_mdl_lve_plan_approval_request",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "review_decision_id",
            name="uq_mdl_lve_plan_approval_decision",
        ),
        sa.CheckConstraint("plan_sha256 ~ '^[0-9a-f]{64}$'", name="ck_mdl_lve_approval_plan_sha"),
        sa.CheckConstraint(
            "evidence_sha256 ~ '^[0-9a-f]{64}$' AND test_data_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_mdl_lve_approval_evidence_sha",
        ),
        sa.CheckConstraint(
            "input_mode IN ('relaxation','dma','dma_frequency_master_curve')",
            name="ck_mdl_lve_approval_mode",
        ),
        sa.CheckConstraint(
            "(processing_output_id IS NULL AND processing_output_revision_id IS NULL "
            "AND processing_output_sha256 IS NULL) OR (processing_output_id IS NOT NULL "
            "AND processing_output_revision_id IS NOT NULL "
            "AND processing_output_sha256 ~ '^[0-9a-f]{64}$')",
            name="ck_mdl_lve_approval_processing_shape",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id"],
            [
                "modeling.linear_viscoelastic_calibration_plan_revision.organization_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.project_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.classification",
                "modeling.linear_viscoelastic_calibration_plan_revision.aggregate_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.id",
            ],
            name="fk_mdl_lve_approval_plan_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "review_request_id"],
            [
                "governance.review_request.organization_id",
                "governance.review_request.project_id",
                "governance.review_request.id",
            ],
            name="fk_mdl_lve_approval_review_request",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "review_decision_id"],
            [
                "governance.review_decision.organization_id",
                "governance.review_decision.project_id",
                "governance.review_decision.id",
            ],
            name="fk_mdl_lve_approval_review_decision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_id",
                "material_revision_id",
            ],
            [
                "catalog.material_revision.organization_id",
                "catalog.material_revision.project_id",
                "catalog.material_revision.classification",
                "catalog.material_revision.aggregate_id",
                "catalog.material_revision.id",
            ],
            name="fk_mdl_lve_approval_material_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "material_state_id",
                "material_state_revision_id",
            ],
            [
                "catalog.material_state_revision.organization_id",
                "catalog.material_state_revision.project_id",
                "catalog.material_state_revision.classification",
                "catalog.material_state_revision.aggregate_id",
                "catalog.material_state_revision.id",
            ],
            name="fk_mdl_lve_approval_material_state_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "test_data_id",
                "test_data_revision_id",
            ],
            [
                "datasets.test_data_document_revision.organization_id",
                "datasets.test_data_document_revision.project_id",
                "datasets.test_data_document_revision.classification",
                "datasets.test_data_document_revision.aggregate_id",
                "datasets.test_data_document_revision.id",
            ],
            name="fk_mdl_lve_approval_test_data_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "processing_output_id",
                "processing_output_revision_id",
            ],
            [
                "processing.common_processing_output_revision.organization_id",
                "processing.common_processing_output_revision.project_id",
                "processing.common_processing_output_revision.classification",
                "processing.common_processing_output_revision.aggregate_id",
                "processing.common_processing_output_revision.id",
            ],
            name="fk_mdl_lve_approval_processing_revision",
            ondelete="RESTRICT",
        ),
        schema="modeling",
    )
    op.create_index(
        "ix_mdl_lve_plan_approval_exact_context",
        _APPROVAL,
        [
            "organization_id",
            "project_id",
            "classification",
            "material_id",
            "material_revision_id",
            "material_state_id",
            "material_state_revision_id",
            "test_data_id",
            "test_data_revision_id",
            "processing_output_id",
            "processing_output_revision_id",
            "input_mode",
        ],
        schema="modeling",
    )

    op.create_table(
        _FACT,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("classification", sa.String(length=64), nullable=False),
        sa.Column("fact_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_revision_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("successor_plan_id", sa.Uuid(), nullable=True),
        sa.Column("successor_plan_revision_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint(
            "organization_id",
            "project_id",
            "fact_id",
            name="pk_mdl_lve_usability_fact",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "fact_id", "plan_id", "plan_revision_id",
            name="uq_mdl_lve_usability_fact_identity",
        ),
        sa.CheckConstraint(
            "state IN ('active','superseded','withdrawn')",
            name="ck_mdl_lve_usability_state",
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) BETWEEN 1 AND 2000",
            name="ck_mdl_lve_usability_reason",
        ),
        sa.CheckConstraint(
            "(state = 'superseded' AND successor_plan_id IS NOT NULL "
            "AND successor_plan_revision_id IS NOT NULL) OR "
            "(state IN ('active','withdrawn') AND successor_plan_id IS NULL "
            "AND successor_plan_revision_id IS NULL)",
            name="ck_mdl_lve_usability_successor_shape",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id"],
            [
                "modeling.linear_viscoelastic_calibration_plan_revision.organization_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.project_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.classification",
                "modeling.linear_viscoelastic_calibration_plan_revision.aggregate_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.id",
            ],
            name="fk_mdl_lve_usability_plan_revision",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "organization_id",
                "project_id",
                "classification",
                "successor_plan_id",
                "successor_plan_revision_id",
            ],
            [
                "modeling.linear_viscoelastic_calibration_plan_revision.organization_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.project_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.classification",
                "modeling.linear_viscoelastic_calibration_plan_revision.aggregate_id",
                "modeling.linear_viscoelastic_calibration_plan_revision.id",
            ],
            name="fk_mdl_lve_usability_successor_revision",
            ondelete="RESTRICT",
        ),
        schema="modeling",
    )
    op.create_index(
        "ix_mdl_lve_usability_active_lookup",
        _FACT,
        ["organization_id", "project_id", "classification", "plan_id", "plan_revision_id", "state"],
        schema="modeling",
    )
    _rls(_APPROVAL)
    _rls(_FACT)
    _immutable(_APPROVAL)
    _immutable(_FACT)


def downgrade() -> None:
    bind = op.get_bind()
    if bool(
        bind.execute(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM modeling.linear_viscoelastic_calibration_plan_usability_fact "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_plan_approval "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_plan_revision "
                "WHERE setup_name IS NOT NULL "
                "UNION ALL SELECT 1 FROM modeling.linear_viscoelastic_calibration_run "
                "WHERE approval_request_id IS NOT NULL)"
            )
        ).scalar()
    ):
        raise RuntimeError("cannot downgrade Issue #377 Plan governance while evidence exists")

    for table in (_APPROVAL, _FACT):
        prefix = _RLS_PREFIX[table]
        op.execute(f"DROP POLICY IF EXISTS {prefix}_select ON modeling.{table}")
        op.execute(f"DROP POLICY IF EXISTS {prefix}_review_insert ON modeling.{table}")
        op.execute(f"DROP TRIGGER IF EXISTS {prefix}_immutable ON modeling.{table}")
    op.drop_index("ix_mdl_lve_usability_active_lookup", table_name=_FACT, schema="modeling")
    op.drop_index("ix_mdl_lve_plan_approval_exact_context", table_name=_APPROVAL, schema="modeling")
    op.drop_table(_FACT, schema="modeling")
    op.drop_table(_APPROVAL, schema="modeling")
    for constraint in (
        "fk_mdl_lve_run_approval_decision",
        "fk_mdl_lve_run_approval_request",
    ):
        op.drop_constraint(constraint, _RUN, type_="foreignkey", schema="modeling")
    op.drop_constraint(
        "ck_mdl_lve_run_approval_evidence_shape",
        _RUN,
        type_="check",
        schema="modeling",
    )
    for column in (
        "execution_input_mode",
        "execution_processing_output_sha256",
        "execution_processing_output_revision_id",
        "execution_processing_output_id",
        "execution_test_data_sha256",
        "execution_test_data_revision_id",
        "execution_test_data_id",
        "execution_material_state_revision_id",
        "execution_material_state_id",
        "execution_material_revision_id",
        "execution_material_id",
        "approval_approved_by",
        "approval_approved_at",
        "approval_state",
        "approval_evidence_sha256",
        "approval_decision_id",
        "approval_request_id",
    ):
        op.drop_column(_RUN, column, schema="modeling")
    op.drop_index("ix_mdl_lve_plan_exact_source_context", table_name=_PLAN, schema="modeling")
    for constraint in (
        "fk_mdl_lve_plan_base_revision",
        "fk_mdl_lve_plan_material_state_revision",
        "fk_mdl_lve_plan_material_revision",
    ):
        op.drop_constraint(constraint, _PLAN, type_="foreignkey", schema="modeling")
    op.drop_constraint("ck_mdl_lve_plan_governance_shape", _PLAN, type_="check", schema="modeling")
    for column in (
        "base_diff",
        "override_reason",
        "based_on_plan_revision_id",
        "based_on_plan_id",
        "input_mode",
        "material_state_revision_id",
        "material_state_id",
        "material_revision_id",
        "material_id",
        "setup_name",
    ):
        op.drop_column(_PLAN, column, schema="modeling")
