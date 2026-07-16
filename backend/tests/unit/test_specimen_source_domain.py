from __future__ import annotations

from typing import cast
from uuid import UUID

import pytest
from cmp.modules.testing.domain.reference_tensile import InvalidTestingData
from cmp.modules.testing.domain.specimen_source import (
    SpecimenSourceContent,
    SpecimenSourceLot,
    specimen_source_canonical,
)


def _id(suffix: int) -> UUID:
    return UUID(f"39100000-0000-4000-8000-{suffix:012d}")


def test_specimen_source_keeps_ordered_exact_lot_revisions() -> None:
    content = SpecimenSourceContent(
        specimen_id=_id(1),
        specimen_revision_id=_id(101),
        sources=(
            SpecimenSourceLot(_id(2), _id(102), "primary source"),
            SpecimenSourceLot(_id(3), _id(103)),
        ),
    )

    document = specimen_source_canonical(content)
    sources = cast(list[dict[str, str | None]], document["sources"])

    assert [item["material_lot_revision_id"] for item in sources] == [
        str(_id(102)),
        str(_id(103)),
    ]


def test_specimen_source_rejects_duplicate_exact_lot_revision() -> None:
    source = SpecimenSourceLot(_id(2), _id(102))
    with pytest.raises(InvalidTestingData, match="only once"):
        SpecimenSourceContent(_id(1), _id(101), (source, source))
