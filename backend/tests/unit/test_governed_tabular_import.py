from __future__ import annotations

import io
import zipfile
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
    inspect_tabular_source,
    normalized_parquet_bytes,
    parse_governed_source,
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
