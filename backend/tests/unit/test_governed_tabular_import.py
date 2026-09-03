from __future__ import annotations

import io
import zipfile
from dataclasses import replace
from uuid import UUID

import pytest
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedImportProfileContent,
    InvalidGovernedImport,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
    import_profile_canonical,
    inspect_tabular_source,
    normalized_parquet_bytes,
    parse_governed_source,
    parse_governed_source_evidence,
    read_tabular_source_rows,
)

RAW_ASSET = UUID("10000000-0000-0000-0000-000000000001")
RAW_ARTIFACT = UUID("10000000-0000-0000-0000-000000000002")
SHA = "a" * 64


def _axial_profile(
    *,
    file_format: TabularFileFormat = TabularFileFormat.CSV,
    sheet_name: str | None = None,
    decimal_separator: str = ".",
) -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label="Approved tension import",
        data_schema=TabularDataSchema.MONOTONIC_TENSION,
        file_format=file_format,
        sheet_name=sheet_name,
        header_row=1,
        encoding="binary" if file_format is TabularFileFormat.XLSX else "utf-8",
        delimiter=None if file_format is TabularFileFormat.XLSX else ";",
        decimal_separator=decimal_separator,
        channels=(
            GovernedChannelMapping(
                0,
                "strain",
                QuantityKind.ENGINEERING_STRAIN,
                "%",
                AxisRole.INDEPENDENT,
            ),
            GovernedChannelMapping(
                1,
                "stress",
                QuantityKind.ENGINEERING_STRESS,
                "MPa",
                AxisRole.DEPENDENT,
            ),
        ),
    )


def _dma_profile(
    *,
    file_format: TabularFileFormat = TabularFileFormat.CSV,
    sheet_name: str | None = None,
    include_tan_delta: bool = False,
) -> GovernedImportProfileContent:
    channels: tuple[GovernedChannelMapping, ...] = (
        GovernedChannelMapping(
            0,
            "source_sweep_ordinal",
            QuantityKind.SOURCE_SWEEP_ORDINAL,
            "1",
            AxisRole.AUXILIARY,
        ),
        GovernedChannelMapping(
            1, "temperature", QuantityKind.TEMPERATURE, "degC", AxisRole.INDEPENDENT
        ),
        GovernedChannelMapping(2, "frequency", QuantityKind.FREQUENCY, "Hz", AxisRole.INDEPENDENT),
        GovernedChannelMapping(
            3, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
        ),
        GovernedChannelMapping(4, "loss", QuantityKind.LOSS_MODULUS, "MPa", AxisRole.DEPENDENT),
    )
    if include_tan_delta:
        channels = (
            *channels,
            GovernedChannelMapping(5, "tan_delta", QuantityKind.TAN_DELTA, "1", AxisRole.DEPENDENT),
        )
    return GovernedImportProfileContent(
        profile_label="DMA frequency-temperature sweep",
        data_schema=TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP,
        file_format=file_format,
        sheet_name=sheet_name,
        header_row=1,
        encoding="binary" if file_format is TabularFileFormat.XLSX else "utf-8",
        delimiter=(
            None
            if file_format is TabularFileFormat.XLSX
            else "\t"
            if file_format is TabularFileFormat.TSV
            else ","
        ),
        decimal_separator=".",
        channels=channels,
        schema_version="1.3.0",
        deformation_mode="shear",
    )


def _dma_temperature_profile() -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label="Fixed-frequency DMA temperature sweep",
        data_schema=TabularDataSchema.DMA_TEMPERATURE_SWEEP,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0,
                "temperature",
                QuantityKind.TEMPERATURE,
                "degC",
                AxisRole.INDEPENDENT,
            ),
            GovernedChannelMapping(
                1,
                "storage",
                QuantityKind.STORAGE_MODULUS,
                "MPa",
                AxisRole.DEPENDENT,
            ),
            GovernedChannelMapping(
                2,
                "tan_delta",
                QuantityKind.TAN_DELTA,
                "1",
                AxisRole.DEPENDENT,
            ),
        ),
        schema_version="1.3.0",
        deformation_mode="shear",
    )


def _fld_profile(
    *, file_format: TabularFileFormat = TabularFileFormat.TSV
) -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label="Forming limit",
        data_schema=TabularDataSchema.FORMING_LIMIT,
        file_format=file_format,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter="\t" if file_format is TabularFileFormat.TSV else ",",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0, "minor", QuantityKind.MINOR_STRAIN, "1", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(1, "major", QuantityKind.MAJOR_STRAIN, "1", AxisRole.DEPENDENT),
        ),
    )


def _xlsx_table(headers: tuple[str, ...], rows: tuple[tuple[float, ...], ...]) -> bytes:
    def reference(index: int, row: int) -> str:
        return f"{chr(ord('A') + index)}{row}"

    header_cells = "".join(
        f'<c r="{reference(index, 1)}" t="inlineStr"><is><t>{header}</t></is></c>'
        for index, header in enumerate(headers)
    )
    data_rows = "".join(
        f'<row r="{row_index}">'
        + "".join(
            f'<c r="{reference(column_index, row_index)}"><v>{value}</v></c>'
            for column_index, value in enumerate(row)
        )
        + "</row>"
        for row_index, row in enumerate(rows, start=2)
    )
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="worksheets/sheet1.xml"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
</Relationships>"""
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
 <row r="1">{header_cells}</row>{data_rows}
</sheetData></worksheet>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()


def _xlsx(
    *,
    formula: bool = False,
    absolute_target: bool = False,
    worksheet_target: str | None = None,
    second_sheet: bool = False,
) -> bytes:
    second_sheet_manifest = '<sheet name="Repeat" sheetId="2" r:id="rId2"/>' if second_sheet else ""
    workbook = (
        """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="Data" sheetId="1" r:id="rId1"/>"""
        + second_sheet_manifest
        + """</sheets></workbook>"""
    )
    worksheet_target = worksheet_target or (
        "/xl/worksheets/sheet1.xml" if absolute_target else "worksheets/sheet1.xml"
    )
    second_relationship = (
        """<Relationship Id="rId2" Target="worksheets/sheet2.xml"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>"""
        if second_sheet
        else ""
    )
    rels = f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="{worksheet_target}"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>
 {second_relationship}
</Relationships>"""
    calculated = "<f>A2*2</f><v>100</v>" if formula else "<v>100</v>"
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
 <row r="1"><c r="A1" t="inlineStr"><is><t>strain</t></is></c>
 <c r="B1" t="inlineStr"><is><t>stress</t></is></c></row>
 <row r="2"><c r="A2"><v>0</v></c><c r="B2">{calculated}</c></row>
 <row r="3"><c r="A3"><v>1</v></c><c r="B3"><v>200</v></c></row>
</sheetData></worksheet>"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        if second_sheet:
            archive.writestr("xl/worksheets/sheet2.xml", sheet)
    return output.getvalue()


def test_semicolon_decimal_comma_is_explicit_and_normalized() -> None:
    profile = _axial_profile(decimal_separator=",")
    source = b"strain;stress\n0,0;100,0\n1,0;200,0\n"

    preview = inspect_tabular_source(
        source,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        raw_sha256=SHA,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=";",
        decimal_separator=",",
    )
    parsed = parse_governed_source(source, profile)

    assert preview.status == "needs_input"
    assert preview.header_columns == ("strain", "stress")
    assert parsed.rows == ((0.0, 100_000_000.0), (0.01, 200_000_000.0))
    assert normalized_parquet_bytes(parsed).startswith(b"PAR1")


def test_force_displacement_requires_pinned_geometry() -> None:
    channels = (
        GovernedChannelMapping(
            0, "extension", QuantityKind.DISPLACEMENT, "mm", AxisRole.INDEPENDENT
        ),
        GovernedChannelMapping(1, "load", QuantityKind.FORCE, "kN", AxisRole.DEPENDENT),
    )
    with pytest.raises(InvalidGovernedImport, match="requires positive gauge length"):
        GovernedImportProfileContent(
            profile_label="Geometry missing",
            data_schema=TabularDataSchema.MONOTONIC_TENSION,
            file_format=TabularFileFormat.CSV,
            sheet_name=None,
            header_row=1,
            encoding="utf-8",
            delimiter=",",
            decimal_separator=".",
            channels=channels,
        )

    profile = GovernedImportProfileContent(
        profile_label="Geometry pinned",
        data_schema=TabularDataSchema.MONOTONIC_TENSION,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=channels,
        initial_gauge_length_m=0.05,
        initial_cross_section_area_m2=10e-6,
    )
    parsed = parse_governed_source(b"extension,load\n0,0\n1,2\n", profile)
    assert parsed.rows[1] == pytest.approx((0.02, 200_000_000.0))


def test_xlsx_discovers_a_unique_sheet_and_rejects_formulas() -> None:
    source = _xlsx()
    preview = inspect_tabular_source(
        source,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        raw_sha256=SHA,
        file_format=TabularFileFormat.XLSX,
        sheet_name="Data",
        header_row=1,
        encoding="binary",
        delimiter=None,
        decimal_separator=".",
    )
    assert preview.sheet_names == ("Data",)
    assert preview.selected_sheet_name == "Data"
    assert preview.header_columns == ("strain", "stress")
    assert parse_governed_source(
        source, _axial_profile(file_format=TabularFileFormat.XLSX, sheet_name="Data")
    ).rows[-1] == (0.01, 200_000_000.0)

    with pytest.raises(InvalidGovernedImport, match="formulas"):
        inspect_tabular_source(
            _xlsx(formula=True),
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            raw_sha256=SHA,
            file_format=TabularFileFormat.XLSX,
            sheet_name="Data",
            header_row=1,
            encoding="binary",
            delimiter=None,
            decimal_separator=".",
        )


def test_xlsx_with_multiple_sheets_returns_discovery_before_reading_rows() -> None:
    preview = inspect_tabular_source(
        _xlsx(second_sheet=True),
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        raw_sha256=SHA,
        file_format=TabularFileFormat.XLSX,
        sheet_name=None,
        header_row=1,
        encoding="binary",
        delimiter=None,
        decimal_separator=".",
    )

    assert preview.sheet_names == ("Data", "Repeat")
    assert preview.selected_sheet_name is None
    assert preview.header_columns == ()
    assert preview.sample_rows == ()
    assert preview.status == "needs_input"


def test_xlsx_accepts_an_ooxml_absolute_worksheet_relationship_target() -> None:
    preview = inspect_tabular_source(
        _xlsx(absolute_target=True),
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        raw_sha256=SHA,
        file_format=TabularFileFormat.XLSX,
        sheet_name=None,
        header_row=1,
        encoding="binary",
        delimiter=None,
        decimal_separator=".",
    )

    assert preview.header_columns == ("strain", "stress")
    assert preview.sample_rows[-1] == ("1", "200")


@pytest.mark.parametrize(
    "worksheet_target",
    ("../worksheets/sheet1.xml", "worksheets\\sheet1.xml"),
)
def test_xlsx_rejects_unsafe_worksheet_relationship_targets(worksheet_target: str) -> None:
    with pytest.raises(InvalidGovernedImport, match="worksheet relationship is unsafe"):
        inspect_tabular_source(
            _xlsx(worksheet_target=worksheet_target),
            raw_asset_id=RAW_ASSET,
            raw_artifact_id=RAW_ARTIFACT,
            raw_sha256=SHA,
            file_format=TabularFileFormat.XLSX,
            sheet_name="Data",
            header_row=1,
            encoding="binary",
            delimiter=None,
            decimal_separator=".",
        )


def test_schema_does_not_accept_arbitrary_quantity_pairs() -> None:
    with pytest.raises(InvalidGovernedImport, match="simple shear requires"):
        GovernedImportProfileContent(
            profile_label="Wrong shear mapping",
            data_schema=TabularDataSchema.SIMPLE_SHEAR,
            file_format=TabularFileFormat.TSV,
            sheet_name=None,
            header_row=1,
            encoding="utf-8",
            delimiter="\t",
            decimal_separator=".",
            channels=_axial_profile().channels,
        )


def test_catalog_registration_parser_returns_every_named_row() -> None:
    sheet_names, selected_sheet, rows = read_tabular_source_rows(
        b"Material;Code;E\nSteel A;A;210,5\nSteel B;B;205,0\n",
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=";",
        decimal_separator=",",
    )

    assert sheet_names == ()
    assert selected_sheet is None
    assert rows == (
        {"Material": "Steel A", "Code": "A", "E": "210,5"},
        {"Material": "Steel B", "Code": "B", "E": "205,0"},
    )


def test_dma_frequency_temperature_sweep_normalizes_current_five_channel_shape() -> None:
    evidence = parse_governed_source_evidence(
        b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,-40,1,1200,120\n1,20,2,900,90\n2,-20,10,1000,100\n",
        _dma_profile(),
    )

    assert evidence.normalized.columns == (
        QuantityKind.SOURCE_SWEEP_ORDINAL,
        QuantityKind.TEMPERATURE,
        QuantityKind.FREQUENCY,
        QuantityKind.STORAGE_MODULUS,
        QuantityKind.LOSS_MODULUS,
    )
    assert evidence.normalized.rows[0] == pytest.approx(
        (1, 233.15, 1.0, 1_200_000_000.0, 120_000_000.0)
    )
    assert evidence.normalized.rows[-1] == pytest.approx(
        (2, 253.15, 10.0, 1_000_000_000.0, 100_000_000.0)
    )
    assert evidence.original_rows[0][0] == 1
    assert evidence.normalization_offsets == (0.0, 273.15, 0.0, 0.0, 0.0)


def test_dma_current_profile_rejects_duplicate_frequency_with_temperature_jitter() -> None:
    source = (
        b"source_sweep_ordinal,temperature,frequency,storage,loss\n"
        b"1,20,1,1200,120\n1,20.01,1,1100,110\n"
    )

    with pytest.raises(InvalidGovernedImport) as caught:
        parse_governed_source(source, _dma_profile())

    assert caught.value.diagnostics[0].error_code == "duplicate_coordinate"


def test_dma_optional_tan_delta_and_xlsx_use_the_same_profile_rules() -> None:
    source = _xlsx_table(
        ("source_sweep_ordinal", "temperature", "frequency", "storage", "loss", "tan_delta"),
        ((1, -30, 1, 1100, 110, 0.1), (1, 30, 2, 800, 80, 0.1)),
    )
    parsed = parse_governed_source(
        source,
        _dma_profile(
            file_format=TabularFileFormat.XLSX,
            sheet_name="Data",
            include_tan_delta=True,
        ),
    )

    assert parsed.columns[-1] is QuantityKind.TAN_DELTA
    assert parsed.rows[1] == pytest.approx((1, 303.15, 2.0, 800_000_000.0, 80_000_000.0, 0.1))
    assert normalized_parquet_bytes(parsed).startswith(b"PAR1")


@pytest.mark.parametrize("token", ("1.0", "+1", "1e0", "0", "9223372036854775808"))
def test_dma_source_sweep_ordinal_accepts_only_direct_positive_int64_tokens(token: str) -> None:
    source = (
        "source_sweep_ordinal,temperature,frequency,storage,loss\n"
        f"{token},-30,1,1100,110\n1,30,1,800,80\n"
    ).encode()
    with pytest.raises(InvalidGovernedImport) as caught:
        parse_governed_source(source, _dma_profile())
    assert caught.value.diagnostics
    assert caught.value.diagnostics[0].error_code in {
        "invalid_integral_token",
        "invalid_decimal_separator",
        "ordinal_out_of_range",
    }


def test_fixed_frequency_dma_temperature_profile_preserves_signed_loss_factor() -> None:
    profile = _dma_temperature_profile()
    evidence = parse_governed_source_evidence(
        b"temperature,storage,tan_delta\n-30,1100,0.10\n0,900,0.30\n30,700,-0.02\n",
        profile,
    )

    assert evidence.normalized.columns == (
        QuantityKind.TEMPERATURE,
        QuantityKind.STORAGE_MODULUS,
        QuantityKind.TAN_DELTA,
    )
    assert evidence.original_rows[-1] == (30.0, 700.0, -0.02)
    assert evidence.normalized.rows[-1] == pytest.approx((303.15, 700_000_000.0, -0.02))
    canonical = import_profile_canonical(profile)
    assert canonical["schema_version"] == "1.3.0"
    assert canonical["deformation_mode"] == "shear"


def test_fixed_frequency_dma_temperature_profile_requires_1_3_shear_contract() -> None:
    with pytest.raises(InvalidGovernedImport, match=r"schema 1\.3\.0"):
        replace(_dma_temperature_profile(), schema_version="1.2.0")
    with pytest.raises(InvalidGovernedImport, match="deformation_mode=shear"):
        replace(_dma_temperature_profile(), deformation_mode=None)


def test_forming_limit_accepts_signed_non_monotonic_strain_without_sorting() -> None:
    parsed = parse_governed_source(
        b"minor\tmajor\n-0.20\t0.32\n0.10\t0.28\n-0.05\t0.30\n",
        _fld_profile(),
    )

    assert parsed.columns == (QuantityKind.MINOR_STRAIN, QuantityKind.MAJOR_STRAIN)
    assert parsed.rows == ((-0.2, 0.32), (0.1, 0.28), (-0.05, 0.3))


@pytest.mark.parametrize(
    ("source", "profile", "codes"),
    (
        (
            b"source_sweep_ordinal,temperature,frequency,loss\n1,0,1,10\n1,20,1,8\n",
            _dma_profile(),
            {"missing_required_column"},
        ),
        (
            b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,0,1,NaN,\n1,20,1,Inf,5\n",
            _dma_profile(),
            {"non_finite_value", "missing_value"},
        ),
        (
            b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,0,1,10,5\n1,0,1,9,4\n",
            _dma_profile(),
            {"duplicate_coordinate"},
        ),
        (
            b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,-274,1,10,5\n1,0,1,9,4\n",
            _dma_profile(),
            {"temperature_below_absolute_zero"},
        ),
        (
            b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,0,0,10,5\n1,20,1,9,4\n",
            _dma_profile(),
            {"frequency_not_positive"},
        ),
        (
            b"source_sweep_ordinal,temperature,frequency,storage,loss\n1,0,1,-10,5\n1,20,1,9,4\n",
            _dma_profile(),
            {"negative_dma_response"},
        ),
        (
            b"minor\tmajor\n-0.2\t0.3\n-0.2\t0.4\n",
            _fld_profile(),
            {"duplicate_coordinate"},
        ),
    ),
)
def test_dma_fld_fail_closed_with_structured_diagnostics(
    source: bytes,
    profile: GovernedImportProfileContent,
    codes: set[str],
) -> None:
    with pytest.raises(InvalidGovernedImport) as caught:
        parse_governed_source(source, profile)

    assert codes <= {item.error_code for item in caught.value.diagnostics}
    assert [item.ordinal for item in caught.value.diagnostics] == list(
        range(len(caught.value.diagnostics))
    )
    assert all(item.recovery_hint for item in caught.value.diagnostics)


def test_dma_and_fld_profiles_reject_wrong_channel_contracts() -> None:
    with pytest.raises(InvalidGovernedImport, match="source_sweep_ordinal"):
        replace(_dma_profile(), channels=_dma_profile().channels[:3])

    with pytest.raises(InvalidGovernedImport, match="minor_strain/major_strain"):
        replace(_fld_profile(), channels=_axial_profile().channels)
