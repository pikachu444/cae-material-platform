from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from cmp.modules.datasets.application.canonical_tabular_adapter import (
    CanonicalTabularAdapterInput,
    canonical_from_governed_tabular,
)
from cmp.modules.datasets.application.canonical_test_data import (
    canonical_json_bytes,
    canonical_test_data_curve_definition,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataError,
    ChannelAxisRole,
    parse_canonical_test_data,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as ExecutionMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as MaterialMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as SpecimenMetadata,
)
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedImportProfileContent,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
)


def _profile() -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label="DMA frequency-temperature sweep",
        data_schema=TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0, "temperature", QuantityKind.TEMPERATURE, "degC", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(
                1, "frequency", QuantityKind.FREQUENCY, "Hz", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(
                2, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
            ),
            GovernedChannelMapping(3, "loss", QuantityKind.LOSS_MODULUS, "MPa", AxisRole.DEPENDENT),
        ),
    )


def test_dma_governed_adapter_preserves_source_semantics_and_affine_normalization() -> None:
    document = canonical_from_governed_tabular(
        CanonicalTabularAdapterInput(
            document_id="SYNTHETIC-DMA-001",
            material=MaterialMetadata("Synthetic maker", "Reference polymer"),
            test=ExecutionMetadata(
                date(2026, 8, 13),
                "Modeler",
                "Reference lab",
                "DMA frequency-temperature sweep",
            ),
            specimen=SpecimenMetadata("DMA-SPECIMEN-01"),
            conditions=(),
            source_file_name="synthetic-dma.csv",
            source_bytes=(b"temperature,frequency,storage,loss\n-40,1,1200,120\n20,1,900,90\n"),
            profile=_profile(),
        )
    )

    channels = {item.key: item for item in document.channels}
    assert channels["temperature"].quantity_semantics == "physics.temperature"
    assert channels["temperature"].normalization_scale == Decimal("1.0")
    assert channels["temperature"].normalization_offset == Decimal("273.15")
    assert float(channels["temperature"].normalized_values[0]) == pytest.approx(233.15)
    assert channels["frequency"].quantity_semantics == "frequency.cyclic"
    assert channels["frequency"].axis_role is ChannelAxisRole.INDEPENDENT
    assert channels["storage_modulus"].quantity_semantics == "mechanics.modulus.storage"
    assert channels["loss_modulus"].quantity_semantics == "mechanics.modulus.loss"
    assert channels["storage_modulus"].normalization_scale == Decimal("1000000.0")
    assert len(canonical_test_data_curve_definition(document.channels).channels) == 4

    canonical = json.loads(canonical_json_bytes(document))
    assert parse_canonical_test_data(canonical).digest == document.digest
    canonical["channels"][2]["normalized_values"][0] = "1200000001"
    with pytest.raises(CanonicalTestDataError, match="explicit normalization"):
        parse_canonical_test_data(canonical)


def test_fld_governed_adapter_preserves_independent_schema_semantics() -> None:
    profile = GovernedImportProfileContent(
        profile_label="Forming limit diagram",
        data_schema=TabularDataSchema.FORMING_LIMIT,
        file_format=TabularFileFormat.TSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter="\t",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0, "minor", QuantityKind.MINOR_STRAIN, "1", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(1, "major", QuantityKind.MAJOR_STRAIN, "1", AxisRole.DEPENDENT),
        ),
    )
    document = canonical_from_governed_tabular(
        CanonicalTabularAdapterInput(
            document_id="SYNTHETIC-FLD-001",
            material=MaterialMetadata("Synthetic maker", "Reference sheet"),
            test=ExecutionMetadata(
                date(2026, 8, 13),
                "Modeler",
                "Reference lab",
                "Forming limit diagram",
            ),
            specimen=SpecimenMetadata("FLD-SPECIMEN-01"),
            conditions=(),
            source_file_name="synthetic-fld.tsv",
            source_bytes=b"minor\tmajor\n-0.1\t0.35\n0.05\t0.28\n-0.02\t0.31\n",
            profile=profile,
        )
    )

    channels = {item.key: item for item in document.channels}
    assert channels["minor_strain"].quantity_semantics == "mechanics.strain.minor"
    assert channels["minor_strain"].axis_role is ChannelAxisRole.INDEPENDENT
    assert channels["major_strain"].quantity_semantics == "mechanics.strain.major"
    assert channels["minor_strain"].normalized_values == (
        Decimal("-0.1"),
        Decimal("0.05"),
        Decimal("-0.02"),
    )

    canonical = json.loads(canonical_json_bytes(document))
    assert parse_canonical_test_data(canonical).digest == document.digest
    canonical["channels"][1]["normalized_values"][1] = "0.29"
    with pytest.raises(CanonicalTestDataError, match="explicit normalization"):
        parse_canonical_test_data(canonical)
