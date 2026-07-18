"""CSV/TSV/XLSX governed-import adapter into the canonical cmp.test-data document."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal

from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    ChannelAxisRole,
    TestCondition,
    TestDataChannel,
    TestDataSource,
    TestExecutionMetadata,
    TestMaterialMetadata,
    TestSpecimenMetadata,
)
from cmp.modules.datasets.domain.governed_tabular import (
    GovernedImportProfileContent,
    QuantityKind,
    TabularFileFormat,
    parse_governed_source_evidence,
)

_SEMANTICS: dict[QuantityKind, str] = {
    QuantityKind.ENGINEERING_STRAIN: "mechanics.strain.engineering",
    QuantityKind.ENGINEERING_STRESS: "mechanics.stress.engineering",
    QuantityKind.SHEAR_STRAIN: "mechanics.strain.shear",
    QuantityKind.SHEAR_STRESS: "mechanics.stress.shear",
    QuantityKind.TIME: "time.elapsed",
    QuantityKind.SHEAR_MODULUS: "mechanics.modulus.shear.relaxation",
}

_MEDIA_TYPES = {
    TabularFileFormat.CSV: "text/csv",
    TabularFileFormat.TSV: "text/tab-separated-values",
    TabularFileFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(frozen=True, slots=True)
class CanonicalTabularAdapterInput:
    document_id: str
    material: TestMaterialMetadata
    test: TestExecutionMetadata
    specimen: TestSpecimenMetadata
    conditions: tuple[TestCondition, ...]
    source_file_name: str
    source_bytes: bytes
    profile: GovernedImportProfileContent


def canonical_from_governed_tabular(
    command: CanonicalTabularAdapterInput,
) -> CanonicalTestDataDocument:
    evidence = parse_governed_source_evidence(command.source_bytes, command.profile)
    channels: list[TestDataChannel] = []
    for ordinal, mapping in enumerate(command.profile.channels):
        quantity = mapping.normalized_quantity
        original_values = tuple(
            Decimal(str(row[ordinal])) for row in evidence.original_rows
        )
        normalized_values = tuple(
            Decimal(str(row[ordinal])) for row in evidence.normalized.rows
        )
        channels.append(
            TestDataChannel(
                key=quantity.value,
                name=quantity.value.replace("_", " ").title(),
                quantity_semantics=_SEMANTICS[quantity],
                axis_role=ChannelAxisRole(mapping.axis_role.value),
                original_unit_string=mapping.original_unit,
                normalized_unit=mapping.normalized_unit,
                normalization_scale=Decimal(str(evidence.normalization_scales[ordinal])),
                normalization_offset=Decimal("0"),
                original_values=original_values,
                normalized_values=normalized_values,
                missing_reasons=tuple(None for _ in original_values),
            )
        )
    return CanonicalTestDataDocument(
        document_id=command.document_id,
        material=command.material,
        test=command.test,
        specimen=command.specimen,
        conditions=command.conditions,
        channels=tuple(channels),
        source=TestDataSource(
            file_name=command.source_file_name,
            media_type=_MEDIA_TYPES[command.profile.file_format],
            sha256=hashlib.sha256(command.source_bytes).hexdigest(),
        ),
    )
