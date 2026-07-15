from __future__ import annotations

from uuid import UUID

import pytest
from cmp.modules.catalog.domain.model import (
    InvalidCatalogCommand,
    LotKind,
    MaterialLotContent,
    ProcessDefinitionContent,
    ProcessKind,
    StateGenealogyContent,
    state_genealogy_canonical,
)

STATE = UUID("da000000-0000-4000-8000-000000000001")
STATE_REV = UUID("da000000-0000-4000-8000-000000000002")
PROCESS = UUID("da000000-0000-4000-8000-000000000003")
PROCESS_REV = UUID("da000000-0000-4000-8000-000000000004")
MATERIAL = UUID("da000000-0000-4000-8000-000000000005")
MATERIAL_REV = UUID("da000000-0000-4000-8000-000000000006")


def test_typed_process_lot_and_genealogy_keep_exact_revision_links() -> None:
    process = ProcessDefinitionContent(
        "HT-QT-01", "Quench and temper", ProcessKind.HEAT_TREATMENT
    )
    lot = MaterialLotContent(
        MATERIAL,
        MATERIAL_REV,
        "HEAT-2026-0716",
        LotKind.BATCH,
        manufacturer="Reference mill",
    )
    genealogy = StateGenealogyContent(
        material_state_id=STATE,
        material_state_revision_id=STATE_REV,
        heat_treatment_process_id=PROCESS,
        heat_treatment_process_revision_id=PROCESS_REV,
    )

    assert process.kind is ProcessKind.HEAT_TREATMENT
    assert lot.material_revision_id == MATERIAL_REV
    assert state_genealogy_canonical(genealogy)["heat_treatment_process_revision_id"] == str(
        PROCESS_REV
    )


def test_state_genealogy_rejects_missing_typed_links() -> None:
    with pytest.raises(InvalidCatalogCommand, match="at least one typed link"):
        StateGenealogyContent(STATE, STATE_REV)


def test_state_genealogy_rejects_identity_without_revision() -> None:
    with pytest.raises(InvalidCatalogCommand, match="supplied together"):
        StateGenealogyContent(
            STATE,
            STATE_REV,
            manufacturing_process_id=PROCESS,
        )
