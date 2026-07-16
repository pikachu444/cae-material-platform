from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from cmp.modules.catalog.domain.model import InvalidCatalogCommand
from cmp.modules.catalog.domain.process_run import (
    BalanceBasis,
    LotFlow,
    ProcessRunContent,
    process_run_canonical,
)


def _id(suffix: int) -> UUID:
    return UUID(f"39000000-0000-4000-8000-{suffix:012d}")


def _flow(suffix: int, quantity: str, unit: str) -> LotFlow:
    return LotFlow.from_original(
        material_lot_id=_id(suffix),
        material_lot_revision_id=_id(suffix + 100),
        original_quantity=Decimal(quantity),
        original_unit=unit,
    )


def _run(*, inputs: tuple[LotFlow, ...], outputs: tuple[LotFlow, ...]) -> ProcessRunContent:
    return ProcessRunContent(
        process_definition_id=_id(1),
        process_definition_revision_id=_id(101),
        material_state_id=_id(2),
        material_state_revision_id=_id(102),
        run_code="RUN-001",
        started_at=datetime(2026, 7, 16, 9, tzinfo=UTC),
        ended_at=datetime(2026, 7, 16, 10, tzinfo=UTC),
        operator_name="Demo operator",
        equipment_reference="FURNACE-01",
        balance_basis=BalanceBasis.MASS,
        balance_tolerance_fraction=Decimal("0.001"),
        balance_not_assessed_reason=None,
        inputs=inputs,
        outputs=outputs,
    )


def test_process_run_supports_mass_normalization_split_and_merge() -> None:
    split = _run(
        inputs=(_flow(10, "1", "kg"),),
        outputs=(_flow(20, "400", "g"), _flow(21, "600", "g")),
    )
    merge = _run(
        inputs=(_flow(30, "250", "g"), _flow(31, "750000", "mg")),
        outputs=(_flow(40, "1", "kg"),),
    )

    assert split.balance is not None and split.balance.within_tolerance
    assert merge.balance is not None and merge.balance.within_tolerance
    assert split.balance.input_total == Decimal("1")
    assert split.balance.output_total == Decimal("1.000")
    assert process_run_canonical(split)["inputs"][0]["normalized_unit"] == "kg"  # type: ignore[index]


def test_process_run_rejects_dimension_mismatch_and_out_of_tolerance_balance() -> None:
    with pytest.raises(InvalidCatalogCommand, match="dimensions"):
        _run(inputs=(_flow(10, "1", "kg"),), outputs=(_flow(20, "1", "L"),))
    with pytest.raises(InvalidCatalogCommand, match="outside"):
        _run(inputs=(_flow(10, "1", "kg"),), outputs=(_flow(20, "900", "g"),))


def test_process_run_balance_has_storage_stable_decimal_evidence() -> None:
    run = ProcessRunContent(
        process_definition_id=_id(1),
        process_definition_revision_id=_id(101),
        material_state_id=_id(2),
        material_state_revision_id=_id(102),
        run_code="RUN-DECIMAL",
        started_at=datetime(2026, 7, 16, 9, tzinfo=UTC),
        ended_at=None,
        operator_name=None,
        equipment_reference=None,
        balance_basis=BalanceBasis.MASS,
        balance_tolerance_fraction=Decimal("0.1"),
        balance_not_assessed_reason=None,
        inputs=(_flow(10, "3", "kg"),),
        outputs=(_flow(20, "2.8", "kg"),),
    )

    assert run.balance is not None
    assert run.balance.relative_difference == Decimal("0.066666666666666666666667")
    assert process_run_canonical(run)["balance"] == {
        "input_total": "3",
        "output_total": "2.8",
        "relative_difference": "0.066666666666666666666667",
        "within_tolerance": True,
    }


def test_process_run_requires_explicit_reason_when_balance_is_not_assessed() -> None:
    with pytest.raises(InvalidCatalogCommand, match="not_assessed_reason"):
        ProcessRunContent(
            process_definition_id=_id(1),
            process_definition_revision_id=_id(101),
            material_state_id=_id(2),
            material_state_revision_id=_id(102),
            run_code="RUN-NA",
            started_at=datetime(2026, 7, 16, 9, tzinfo=UTC),
            ended_at=None,
            operator_name=None,
            equipment_reference=None,
            balance_basis=BalanceBasis.NOT_ASSESSED,
            balance_tolerance_fraction=None,
            balance_not_assessed_reason=None,
            inputs=(_flow(10, "1", "kg"),),
            outputs=(_flow(20, "1", "1"),),
        )
