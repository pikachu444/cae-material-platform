from uuid import UUID

from cmp.modules.identity_access.application.authorization import (
    database_permissions_for,
)
from cmp.modules.identity_access.domain.authorization import Permission
from cmp.modules.testing.adapters.persistence.repository import SqlAlchemyTestingRepository
from sqlalchemy.dialects import postgresql


def test_material_state_test_run_query_uses_each_relation_once() -> None:
    statement = SqlAlchemyTestingRepository._current_runs_for_material_state_statement(
        organization_id=UUID("10000000-0000-0000-0000-000000000001"),
        project_id=UUID("20000000-0000-0000-0000-000000000001"),
        material_state_id=UUID("30000000-0000-0000-0000-000000000001"),
    )

    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
        )
    )
    assert sql.count("testing.test_run JOIN testing.test_run_revision") == 1
    assert sql.count("JOIN testing.specimen") == 1


def test_dataset_read_carries_its_artifact_and_testing_lineage_capabilities() -> None:
    permissions = set(database_permissions_for(Permission.DATASET_READ))
    assert {
        Permission.DATASET_READ.value,
        Permission.ARTIFACT_READ.value,
        Permission.TESTING_READ.value,
    } <= permissions


def test_modeling_workflows_carry_testing_lineage_capability_directly() -> None:
    for permission in (
        Permission.MODELING_WRITE,
        Permission.CALIBRATION_EXECUTE,
        Permission.VALIDATION_EXECUTE,
    ):
        assert Permission.TESTING_READ.value in database_permissions_for(permission)
