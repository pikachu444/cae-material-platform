from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.catalog.adapters.api.catalog import CatalogHttpError
from cmp.modules.catalog.adapters.api.json_record_registration import _error
from cmp.modules.catalog.adapters.persistence.configurable import (
    RlsContext,
    SqlAlchemyConfigurableCatalogRepository,
)
from cmp.modules.catalog.adapters.persistence.json_record_registration import (
    SqlAlchemyInstalledJsonRecordFormatResolver,
    SqlAlchemyJsonRegistrationRepository,
)
from cmp.modules.catalog.adapters.persistence.records import SqlAlchemyCatalogRecordRepository
from cmp.modules.catalog.application.configurable import AttributeSnapshot
from cmp.modules.catalog.application.json_record_registration import (
    InstalledJsonRecordFormat,
    JsonAttributeBinding,
    JsonCurveArtifactIdentity,
    JsonRecordRegistrationService,
    JsonRegistrationPersistence,
    JsonRegistrationToken,
)
from cmp.modules.catalog.application.records import CatalogRecordService, CreateRecord
from cmp.modules.catalog.domain.configurable import AttributeDataType, ConfigurableCatalogConflict
from cmp.modules.catalog.domain.json_record_registration import (
    JSON_MEDIA_TYPE,
    JSON_PACKAGE_MEDIA_TYPE,
    SOURCE_CSV_HEADER,
    JsonRegistrationError,
    JsonRegistrationFile,
    JsonRegistrationFileResult,
    build_registration_package,
    exact_csv_filename,
    exact_json_filename,
    parse_strict_json,
    source_csv_bytes,
    validate_json_record,
    verify_registration_package,
)
from cmp.modules.catalog.domain.records import CatalogRecordContent, CatalogRecordValue
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).parents[3]
SOURCE_SCHEMAS = PROJECT_ROOT / "fixtures/schema-definition-bundle/source-v2/record-schemas"
FIXTURE_ROOT = PROJECT_ROOT / "fixtures/schema-record-data/source-v2-task1b"
SCHEMA_BY_WRAPPER = {
    "technical-data": "technical-data-v2.json",
    "tensile-test": "tensile-test-v2.json",
    "dma-test": "dma-test-v1.json",
    "fld-test": "fld-test-v1.json",
    "elastoplasticity": "elastoplasticity-v2.json",
    "statistics": "statistics-v2.json",
}


def _as_catalog_records(value: object) -> CatalogRecordService:
    """Cast a deliberately minimal test double at the service boundary."""

    return cast(CatalogRecordService, value)


def _as_registration_persistence(value: object) -> JsonRegistrationPersistence:
    """Cast a deliberately minimal persistence double at the service boundary."""

    return cast(JsonRegistrationPersistence, value)


def _compile_clause(statement: sa.ClauseElement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]


def _compiled_params(statement: sa.ClauseElement) -> Mapping[str, object]:
    compiled = statement.compile(dialect=postgresql.dialect())  # type: ignore[no-untyped-call]
    return cast(Mapping[str, object], compiled.params)


def _schema(wrapper: str) -> dict[str, object]:
    value = cast(
        dict[str, object],
        json.loads((SOURCE_SCHEMAS / SCHEMA_BY_WRAPPER[wrapper]).read_text(encoding="utf-8")),
    )
    value["x-wrapper"] = wrapper
    return value


def test_strict_json_reports_utf8_lexical_duplicate_and_nonfinite_locations() -> None:
    with pytest.raises(JsonRegistrationError) as duplicate:
        parse_strict_json(b'{"a": 1,\n "a": 2}', filename="duplicate.json")
    assert duplicate.value.code == "duplicate_json_key"
    assert duplicate.value.line == 2
    assert duplicate.value.column == 2
    assert duplicate.value.byte_offset is not None

    with pytest.raises(JsonRegistrationError) as lexical:
        parse_strict_json(b'{"a": }', filename="broken.json")
    assert lexical.value.code == "invalid_json"
    assert lexical.value.line == 1
    assert lexical.value.column is not None
    assert lexical.value.byte_offset is not None

    with pytest.raises(JsonRegistrationError) as utf8:
        parse_strict_json(b'{"a": "\xff"}', filename="bytes.json")
    assert utf8.value.code == "invalid_utf8"
    assert utf8.value.byte_offset == 7

    with pytest.raises(JsonRegistrationError) as nonfinite:
        parse_strict_json(b'{"a": NaN}', filename="number.json")
    assert nonfinite.value.code == "non_finite_number"
    assert nonfinite.value.line == 1
    assert nonfinite.value.byte_offset is not None


def test_source_v2_validation_requires_exact_wrapper_and_complete_present_curves() -> None:
    source = (FIXTURE_ROOT / "dma/000c.json").read_bytes()
    document, warnings, errors = validate_json_record(
        source,
        _schema("dma-test"),
        filename="000c.json",
    )
    assert isinstance(document, dict)
    assert warnings == ()
    assert errors == ()

    wrong = json.dumps({"tensile-test": {}}).encode()
    with pytest.raises(JsonRegistrationError, match="wrapper 'dma-test'"):
        validate_json_record(wrong, _schema("dma-test"), filename="wrong.json")

    explicit_null = json.loads(source.decode())
    explicit_null["dma-test"]["Test Result"]["Storage Modulus"] = None
    _, _, null_errors = validate_json_record(
        json.dumps(explicit_null).encode(),
        _schema("dma-test"),
        filename="null.json",
    )
    assert any(item.code == "curve_null_invalid" for item in null_errors)

    malformed = json.loads(source.decode())
    malformed["dma-test"]["Test Result"]["Storage Modulus"]["Series 1"]["Storage Modulus (MPa)"] = [
        1
    ]
    _, _, curve_errors = validate_json_record(
        json.dumps(malformed).encode(),
        _schema("dma-test"),
        filename="curve.json",
    )
    assert any(item.code == "curve_length_mismatch" for item in curve_errors)


def test_source_v2_validation_enforces_exact_discrete_values_with_location_and_recovery() -> None:
    schema = _schema("technical-data")
    valid = {
        "technical-data": {
            "Material Information": {"Family": "Metal", "Orientation": "MD"},
            "Sample Information": {},
            "Data Information": {"Technical Data ID": "TECH-1"},
        }
    }
    _, _, valid_errors = validate_json_record(
        json.dumps(valid).encode(), schema, filename="valid.json"
    )
    assert valid_errors == ()

    invalid = {
        "technical-data": {
            "Material Information": {"Family": "steel"},
            "Sample Information": {},
            "Data Information": {"Technical Data ID": "TECH-2"},
        }
    }
    _, _, invalid_errors = validate_json_record(
        json.dumps(invalid).encode(), schema, filename="invalid.json"
    )
    diagnostic = next(item for item in invalid_errors if item.code == "discrete_value_invalid")
    assert diagnostic.filename == "invalid.json"
    assert diagnostic.pointer == "/technical-data/Material Information/Family"
    assert "steel" in diagnostic.message
    assert "Metal" in diagnostic.recovery


def test_api_error_bounds_unexpected_detail_without_losing_problem_construction() -> None:
    context, _ = _security()
    long_detail = "sqlalchemy failure " + ("x" * 2048)

    error = _error(context, RuntimeError(long_detail))

    assert isinstance(error, CatalogHttpError)
    assert len(error.problem.detail) <= 2000
    assert error.problem.detail == long_detail[:2000]


def test_api_error_maps_invalid_preview_to_422_and_conflict_to_409() -> None:
    context, decision = _security()
    service = JsonRecordRegistrationService(
        _as_catalog_records(_FakeRecords()), formats={FORMAT_REVISION: _format()}
    )
    preview = service.preview(
        context,
        decision,
        format_revision_id=FORMAT_REVISION,
        files=(JsonRegistrationFile("invalid.json", b'{"record": {}}'),),
    )
    assert preview.valid is False

    with pytest.raises(
        ValueError, match="all JSON files must be valid before draft save"
    ) as raised:
        service.save(
            context,
            decision,
            token=preview.token,
            format_revision_id=FORMAT_REVISION,
            package_sha256=preview.package_sha256,
            change_reason="JSON registration test",
        )
    invalid_request = _error(context, raised.value)
    assert invalid_request.problem.status == 422
    assert invalid_request.problem.title == "Invalid JSON Record registration request"
    assert invalid_request.problem.code == "CMP-CATALOG-0032"

    conflict = _error(context, ConfigurableCatalogConflict("registration preview token is stale"))
    assert conflict.problem.status == 409
    assert conflict.problem.code == "CMP-CATALOG-0031"


def test_registration_package_is_byte_deterministic_and_has_canonical_zip_metadata() -> None:
    first = JsonRegistrationFile("z.json", b'{"value":2}')
    second = JsonRegistrationFile("a.json", b'{"value":1}')
    options = {
        "scope": {"classification": "internal"},
        "format_pins": {"format_revision_id": "00000000-0000-4000-8000-000000000001"},
    }
    left = build_registration_package((first, second), **options)
    right = build_registration_package((second, first), **options)
    assert left.archive == right.archive
    assert left.sha256 == hashlib.sha256(left.archive).hexdigest()
    assert verify_registration_package(left.archive) == (second, first)

    with zipfile.ZipFile(io.BytesIO(left.archive)) as archive:
        assert archive.comment == b""
        infos = archive.infolist()
        assert [item.filename for item in infos[:2]] == ["manifest.json", "checksums.sha256"]
        for item in infos:
            assert item.flag_bits == 0x800
            assert item.compress_type == zipfile.ZIP_STORED
            assert item.date_time == (1980, 1, 1, 0, 0, 0)
            assert item.create_system == 3
            assert item.create_version == item.extract_version == 20
            assert item.external_attr >> 16 == 0o100644
            assert item.comment == b""
            assert item.extra == b""


def test_registration_package_rejects_compression_and_path_collisions() -> None:
    compressed = io.BytesIO()
    with zipfile.ZipFile(compressed, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("checksums.sha256", b"")
        archive.writestr("records/001-a.json", b"{}")
    with pytest.raises(ValueError, match="STORED"):
        verify_registration_package(compressed.getvalue())

    with pytest.raises(ValueError, match="case-folding"):
        build_registration_package(
            (JsonRegistrationFile("A.json", b"{}"), JsonRegistrationFile("a.json", b"{}"))
        )
    with pytest.raises(ValueError, match="dotdot"):
        build_registration_package((JsonRegistrationFile("../record.json", b"{}"),))


def test_registration_package_scope_must_match_requested_batch_classification() -> None:
    package = build_registration_package(
        (JsonRegistrationFile("record.json", b'{"record":{"id":"R-1"}}'),),
        scope={"classification": "internal"},
    )
    with pytest.raises(ValueError, match="classification"):
        verify_registration_package(package.archive, expected_classification="restricted")


def test_exact_source_filenames_keep_json_and_csv_extensions_distinct() -> None:
    assert exact_json_filename("CMP-246-TECH-DP780", 2) == "CMP-246-TECH-DP780__r2.json"
    assert exact_csv_filename("CMP-246-TECH-DP780", 2) == "CMP-246-TECH-DP780__r2.csv"


def test_source_csv_has_fixed_header_scalar_rules_and_curve_source_order() -> None:
    source = json.loads((FIXTURE_ROOT / "tensile/room.json").read_text(encoding="utf-8"))
    csv_text = source_csv_bytes(source, _schema("tensile-test")).decode("utf-8")
    rows = csv_text.splitlines()
    assert rows[0] == ",".join(SOURCE_CSV_HEADER)
    assert any(
        row.startswith("Test Condition,/tensile-test/Test Condition/Temperature") for row in rows
    )
    curve_rows = [row for row in rows if "Tensile Test Raw Data_Extensometer-Load" in row]
    assert curve_rows[-1].split(",")[9:11] == ["2", "2000"]
    assert "\r" not in csv_text
    assert source_csv_bytes(
        {"tensile-test": {"Data Information": {"Tensile Data ID": "A"}, "Test Result": {}}},
        _schema("tensile-test"),
    ).decode().splitlines()[0] == ",".join(SOURCE_CSV_HEADER)


def test_preview_projects_ordered_bound_fields_and_bounded_curve_summary() -> None:
    text_attribute = SimpleNamespace(
        id=uuid4(),
        current=SimpleNamespace(
            record=SimpleNamespace(revision_id=uuid4()),
            content=SimpleNamespace(
                key="data_information__record_name",
                name="Record name",
                data_type=AttributeDataType.TEXT,
            )
        ),
    )
    curve_attribute = SimpleNamespace(
        id=uuid4(),
        current=SimpleNamespace(
            content=SimpleNamespace(
                key="curve",
                name="Stress curve",
                data_type=AttributeDataType.CURVE,
            )
        ),
    )
    format_value = SimpleNamespace(
        attributes=(
            JsonAttributeBinding(
                "/record/name",
                cast(AttributeSnapshot, text_attribute),
                section="Identity",
                source_key="record_name",
            ),
            JsonAttributeBinding(
                "/record/curve",
                cast(AttributeSnapshot, curve_attribute),
                section="Results",
                curve={
                    "x_pointer": "/record/curve/x",
                    "y_pointer": "/record/curve/y",
                    "x_unit": "s",
                    "y_unit": "MPa",
                },
            ),
        )
    )
    fields = JsonRecordRegistrationService._preview_fields(
        {
            "record": {
                "name": "T-01",
                "curve": {"x": [0, 1, 2], "y": [10, 20, 30]},
            }
        },
        cast(InstalledJsonRecordFormat, format_value),
    )
    assert [(field.section, field.label, field.value) for field in fields[:1]] == [
        ("Identity", "Record name", "T-01")
    ]
    assert JsonRecordRegistrationService._preview_record_name(
        {"record": {"name": "T-01"}}, cast(InstalledJsonRecordFormat, format_value)
    ) == "T-01"
    assert fields[1].summary == "3 points · x s · y MPa"
    assert fields[1].value is None

    context, decision = _security()
    content_format = SimpleNamespace(
        attributes=(format_value.attributes[0],),
        table_id=uuid4(),
        table_revision_id=uuid4(),
        table_key="test-records",
    )
    content = JsonRecordRegistrationService(_as_catalog_records(_FakeRecords()))._content(
        context,
        decision,
        cast(InstalledJsonRecordFormat, content_format),
        {"record": {"name": "T-01"}},
        cast(
            JsonRegistrationFileResult,
            SimpleNamespace(
            filename="record.json",
            external_key="external-key",
            record_name=None,
            ),
        ),
        references={},
        curve_artifacts={},
    )
    assert content.name == "T-01"


def test_source_v2_task1b_fixture_pins_fifteen_bytes_batches_links_and_schema_hashes() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["files"]) == 15
    assert [len(batch["external_keys"]) for batch in manifest["batches"]] == [3, 4, 3, 2, 2, 1]
    assert len(manifest["links"]) == 15
    assert all(item["type"] != "dma_to_elastoplasticity" for item in manifest["links"])
    checksums = {}
    for line in (FIXTURE_ROOT / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        checksums[path] = digest
    assert (
        checksums["manifest.json"]
        == hashlib.sha256((FIXTURE_ROOT / "manifest.json").read_bytes()).hexdigest()
    )
    for item in manifest["files"]:
        raw = (FIXTURE_ROOT / item["path"]).read_bytes()
        assert len(raw) == item["size_bytes"]
        assert hashlib.sha256(raw).hexdigest() == item["sha256"] == checksums[item["path"]]
    for item in manifest["format"]["source_schemas"]:
        raw = PROJECT_ROOT / "fixtures" / item["file"]
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == item["sha256"]
    assert manifest["format"]["application_revision"]["derivation"] == (
        "catalog.schema_definition_bundle.current_application_id"
    )
    assert manifest["format"]["table_revision"]["derivation"] == (
        "catalog.schema_definition_bundle_binding.revision_id"
    )


ORG = UUID("70000000-0000-4000-8000-000000000001")
PROJECT = UUID("70000000-0000-4000-8000-000000000002")
PRINCIPAL = UUID("70000000-0000-4000-8000-000000000003")
FORMAT_REVISION = UUID("70000000-0000-4000-8000-000000000004")


def _security() -> tuple[SecurityContext, AuthorizationDecision]:
    request_id = UUID("70000000-0000-4000-8000-000000000005")
    trace_id = "json-registration-test"
    now = datetime(2026, 8, 27, tzinfo=UTC)
    context = SecurityContext(
        principal=Principal(PRINCIPAL, PrincipalType.USER, "JSON Test User", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject="json-test",
        token_id="json-token",
        groups=("catalog",),
        scopes=("openid",),
        request_id=request_id,
        trace_id=trace_id,
        authenticated_at=now,
    )
    decision = AuthorizationDecision(
        principal_id=PRINCIPAL,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.CATALOG_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=(Permission.CATALOG_READ.value, Permission.CATALOG_WRITE.value),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=request_id,
        trace_id=trace_id,
        decided_at=now,
    )
    return context, decision


def test_existing_pending_batch_appends_ready_before_preview_commit() -> None:
    context, decision = _security()
    format_value = _format()
    batch_id = uuid4()
    source = JsonRegistrationFile("record.json", b'{"record": {}}', artifact_id=str(uuid4()))
    now = datetime(2026, 8, 27, tzinfo=UTC)
    token = JsonRegistrationToken(
        token=str(uuid4()),
        format_revision_id=format_value.format_revision_id,
        caller_id=context.principal.id,
        package_sha256=source.sha256,
        package_artifact_id=None,
        classification=DataClassification.INTERNAL,
        files=(source,),
        documents=({},),
        results=(),
        created_at=now,
        expires_at=now,
    )
    record = SimpleNamespace(
        id=uuid4(),
        current=SimpleNamespace(record=SimpleNamespace(revision_id=uuid4())),
    )
    preview_row = {"id": uuid4(), "batch_id": batch_id}
    existing_batch = {
        "classification": token.classification.value,
        "format_id": format_value.format_id,
        "format_revision_id": format_value.format_revision_id,
        "package_sha256": token.package_sha256,
        "source_state": "artifacts_pending",
    }

    class _Result:
        def __init__(self, mapping: Mapping[str, object] | None = None) -> None:
            self._mapping = mapping
            self.rowcount = 1

        def mappings(self) -> _Result:
            return self

        def one_or_none(self) -> Mapping[str, object] | None:
            return self._mapping

        def all(self) -> list[Mapping[str, object]]:
            return []

    class _Session:
        def __init__(self) -> None:
            self.statements: list[sa.ClauseElement] = []

        def execute(
            self, statement: sa.ClauseElement, *_args: object, **_kwargs: object
        ) -> _Result:
            self.statements.append(statement)
            if len(self.statements) == 1:
                return _Result(preview_row)
            if len(self.statements) == 2:
                return _Result(existing_batch)
            return _Result()

    session = _Session()
    repository = SqlAlchemyJsonRegistrationRepository(
        session_factory=cast(Callable[[], Session], lambda: session),
        rls_context=SimpleNamespace(),
    )
    repository._validate_curve_associations_in_transaction = (  # type: ignore[method-assign]
        lambda **_kwargs: None
    )
    repository._persist_links_in_transaction = lambda **_kwargs: None  # type: ignore[method-assign]

    repository.persist_batch_in_transaction(
        session=cast(Session, session),
        context=context,
        decision=decision,
        token=token,
        format_value=format_value,
        batch_id=batch_id,
        records=(record,),
        curve_artifacts={},
    )

    compiled = [
        _compile_clause(statement)
        for statement in session.statements
    ]
    assert not any(
        "UPDATE catalog.json_record_registration_batch" in statement for statement in compiled
    )
    ready_event_index = next(
        index
        for index, statement in enumerate(compiled)
        if "INSERT INTO catalog.json_record_registration_batch_state_event" in statement
    )
    preview_commit_index = next(
        index
        for index, statement in enumerate(compiled)
        if "UPDATE catalog.json_record_registration_preview" in statement
    )
    assert ready_event_index < preview_commit_index


def test_repository_routes_exact_domain_pins_through_boolean_scoped_lookup() -> None:
    context, decision = _security()

    class _RecordingSession:
        statement: sa.ClauseElement | None = None

        def scalar(self, statement: sa.ClauseElement) -> bool:
            self.statement = statement
            return True

    session = _RecordingSession()
    repository = SqlAlchemyCatalogRecordRepository(
        session_factory=cast(Callable[[], Session], lambda: None),
        rls_context=SimpleNamespace(),
    )

    @contextmanager
    def transaction(
        _context: SecurityContext, _decision: AuthorizationDecision
    ) -> Iterator[_RecordingSession]:
        yield session

    object.__setattr__(repository, "_transaction", transaction)
    binding = (
        "test_data",
        UUID("70000000-0000-4000-8000-00000000000c"),
        UUID("70000000-0000-4000-8000-00000000000d"),
    )

    assert (
        repository.validate_exact_domain_binding(
            context,
            decision,
            classification=DataClassification.INTERNAL,
            binding=binding,
        )
        is True
    )
    assert session.statement is not None
    compiled = _compile_clause(session.statement)
    assert "access_control.catalog_domain_revision_exists" in compiled
    assert compiled.count("CAST(%(") == 2
    assert "AS TEXT)" in compiled
    assert "datasets.test_data_document_revision" not in compiled
    params = _compiled_params(session.statement)
    assert set(params.values()) == {
        ORG,
        PROJECT,
        DataClassification.INTERNAL.value,
        "test_data",
        binding[1],
        binding[2],
    }


def test_source_arrays_remain_evidence_while_scalar_and_curve_bindings_stay_strict() -> None:
    context, decision = _security()
    table_id = uuid4()
    attribute_ids = {"name": uuid4(), "curve": uuid4()}
    revision_ids = {key: uuid4() for key in attribute_ids}
    snapshots = {
        key: SimpleNamespace(
            id=attribute_id,
            table_id=table_id,
            current=SimpleNamespace(
                record=SimpleNamespace(revision_id=revision_ids[key]),
                content=SimpleNamespace(key=key),
            ),
        )
        for key, attribute_id in attribute_ids.items()
    }

    def get_attribute(**kwargs: object) -> SimpleNamespace:
        return next(
            snapshot
            for snapshot in snapshots.values()
            if snapshot.id == kwargs["attribute_id"]
        )

    resolver = SqlAlchemyInstalledJsonRecordFormatResolver(
        session_factory=lambda: cast(Session, None),
        rls_context=cast(RlsContext, SimpleNamespace()),
        artifacts=cast(ArtifactService, SimpleNamespace()),
        schemas=cast(
            SqlAlchemyConfigurableCatalogRepository,
            SimpleNamespace(get_attribute=get_attribute),
        ),
    )
    schema = {
        "x-wrapper": "record",
        "properties": {
            "record": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "x-key": "name"},
                    "hardening_parameters": {
                        "type": ["array", "null"],
                        "items": {"type": "number"},
                        "x-key": "hardening_parameters",
                    },
                    "specimen_widths": {
                        "type": "array",
                        "items": {"type": "number"},
                        "x-key": "specimen_widths",
                    },
                    "curve": {
                        "type": "object",
                        "x-key": "curve",
                        "x-curve": {"x_pointer": "/x", "y_pointer": "/y"},
                    },
                },
            }
        },
    }
    record_properties = cast(
        dict[str, object],
        cast(dict[str, object], cast(dict[str, object], schema["properties"])["record"])[
            "properties"
        ],
    )
    bindings = [
        {
            "target_type": "attribute",
            "parent_external_key": "record",
            "external_key": "name",
            "aggregate_id": attribute_ids["name"],
            "revision_id": revision_ids["name"],
        },
        {
            "target_type": "attribute",
            "parent_external_key": "record",
            "external_key": "curve",
            "aggregate_id": attribute_ids["curve"],
            "revision_id": revision_ids["curve"],
        },
    ]

    resolved = resolver._attribute_bindings(
        context=context,
        decision=decision,
        table_id=table_id,
        table_key="record",
        schema=schema,
        bindings=bindings,
        source_file="record.json",
    )
    assert [binding.json_pointer for binding in resolved] == [
        "/record/name",
        "/record/curve",
    ]

    for missing in ("name", "curve"):
        incomplete = [
            binding for binding in bindings if binding["external_key"] != missing
        ]
        with pytest.raises(ConfigurableCatalogConflict, match=f"'{missing}'"):
            resolver._attribute_bindings(
                context=context,
                decision=decision,
                table_id=table_id,
                table_key="record",
                schema=schema,
                bindings=incomplete,
                source_file="record.json",
            )

    resolved_without_source_coordinates = resolver._attribute_bindings(
        context=context,
        decision=decision,
        table_id=table_id,
        table_key="record",
        schema=schema,
        bindings=bindings,
    )
    assert [binding.json_pointer for binding in resolved_without_source_coordinates] == [
        "/record/name",
        "/record/curve",
    ]

    record_properties["distribution_parameters"] = {
        "type": ["object", "null"],
        "additionalProperties": True,
        "x-key": "distribution_parameters",
    }
    resolved_with_open_object = resolver._attribute_bindings(
        context=context,
        decision=decision,
        table_id=table_id,
        table_key="record",
        schema=schema,
        bindings=bindings,
        source_file="record.json",
    )
    assert [binding.json_pointer for binding in resolved_with_open_object] == [
        "/record/name",
        "/record/curve",
    ]
    record_properties["structured_parameters"] = {
        "type": ["object", "null"],
        "properties": {"value": {"type": "string", "x-key": "structured_value"}},
        "x-key": "structured_parameters",
    }
    with pytest.raises(ConfigurableCatalogConflict, match="'structured_value'"):
        resolver._attribute_bindings(
            context=context,
            decision=decision,
            table_id=table_id,
            table_key="record",
            schema=schema,
            bindings=bindings,
            source_file="record.json",
        )


def test_namespaced_attribute_binding_retains_exact_source_semantic_key() -> None:
    context, decision = _security()
    table_id = uuid4()
    attribute_id = uuid4()
    revision_id = uuid4()
    snapshot = SimpleNamespace(
        id=attribute_id,
        table_id=table_id,
        current=SimpleNamespace(
            record=SimpleNamespace(revision_id=revision_id),
            content=SimpleNamespace(key="data_information__record_name"),
        ),
    )
    resolver = SqlAlchemyInstalledJsonRecordFormatResolver(
        session_factory=lambda: cast(Session, None),
        rls_context=cast(RlsContext, SimpleNamespace()),
        artifacts=cast(ArtifactService, SimpleNamespace()),
        schemas=cast(
            SqlAlchemyConfigurableCatalogRepository,
            SimpleNamespace(get_attribute=lambda **_kwargs: snapshot),
        ),
    )
    schema = {
        "x-wrapper": "record",
        "properties": {
            "record": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "x-key": "record_name"},
                },
            }
        },
    }
    resolved = resolver._attribute_bindings(
        context=context,
        decision=decision,
        table_id=table_id,
        table_key="record",
        schema=schema,
        bindings=(
            {
                "target_type": "attribute",
                "parent_external_key": "record",
                "external_key": "data_information__record_name",
                "source_pointer": "/files/record.json/properties/record/properties/name",
                "aggregate_id": attribute_id,
                "revision_id": revision_id,
            },
        ),
        source_file="record.json",
    )

    assert len(resolved) == 1
    assert resolved[0].source_key == "record_name"


def _format() -> InstalledJsonRecordFormat:
    table_id = UUID("70000000-0000-4000-8000-000000000006")
    schema = {
        "type": "object",
        "properties": {
            "record": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"type": "string", "x-business-key": True}},
            }
        },
    }
    digest = "a" * 64
    return InstalledJsonRecordFormat(
        format_id=UUID("70000000-0000-4000-8000-000000000007"),
        format_revision_id=FORMAT_REVISION,
        format_key="test-json",
        application_id=UUID("70000000-0000-4000-8000-000000000008"),
        application_revision_id=UUID("70000000-0000-4000-8000-000000000009"),
        schema_artifact_id=UUID("70000000-0000-4000-8000-00000000000a"),
        schema_file="record.json",
        schema_pointer="/record",
        schema_sha256=digest,
        table_id=table_id,
        table_revision_id=UUID("70000000-0000-4000-8000-00000000000b"),
        table_key="test-records",
        table_source_file="table.json",
        table_source_pointer="/tables/0",
        table_source_sha256="b" * 64,
        wrapper="record",
        schema=schema,
    )


class _FakeRecords:
    def __init__(self) -> None:
        self.calls = 0
        self._repository = self
        self.commands: tuple[tuple[UUID, CreateRecord], ...] = ()
        self.domain_binding_calls: list[
            tuple[DataClassification, tuple[str, UUID, UUID]]
        ] = []
        self.created_records: tuple[SimpleNamespace, ...] = ()

    def _promote_business_key(
        self, _context: object, _decision: object, content: CatalogRecordContent
    ) -> CatalogRecordContent:
        return content

    def _validate_record(
        self, _context: object, _decision: object, _content: CatalogRecordContent
    ) -> None:
        return None

    def create_records_atomically(self, **_kwargs: object) -> tuple[SimpleNamespace, ...]:
        self.calls += 1
        commands = cast(tuple[tuple[UUID, CreateRecord], ...], _kwargs["records"])
        self.commands = commands
        records: list[SimpleNamespace] = []
        for _, command in commands:
            content = command.content
            records.append(
                SimpleNamespace(
                    id=uuid4(),
                    current=SimpleNamespace(
                        record=SimpleNamespace(revision_id=uuid4(), revision_no=1),
                        content=content,
                    ),
                )
            )
        self.created_records = tuple(records)
        return self.created_records

    def get_record_revision(
        self, _context: object, _decision: object, _record_id: UUID, _revision_id: UUID
    ) -> SimpleNamespace:
        return cast(SimpleNamespace, self.created_records[0].current)

    def validate_exact_domain_binding(
        self,
        _context: object,
        _decision: object,
        *,
        classification: DataClassification,
        binding: tuple[str, UUID, UUID],
    ) -> bool:
        self.domain_binding_calls.append((classification, binding))
        return True


def _number_binding(
    *, normalized_unit: str | None, quantity_semantics: str | None
) -> JsonAttributeBinding:
    attribute = SimpleNamespace(
        id=uuid4(),
        current=SimpleNamespace(
            record=SimpleNamespace(revision_id=uuid4()),
            content=SimpleNamespace(
                key="stress",
                name="Stress",
                data_type=AttributeDataType.NUMBER,
                normalized_unit=normalized_unit,
                quantity_semantics=quantity_semantics,
            ),
        ),
    )
    return JsonAttributeBinding(
        "/record/stress",
        cast(AttributeSnapshot, attribute),
        source_unit="MPa",
        quantity_semantics=quantity_semantics,
    )


@pytest.mark.parametrize(
    ("normalized_unit", "quantity_semantics"),
    ((None, "mechanics.stress.engineering"), ("Pa", None)),
)
def test_incomplete_exact_number_binding_stays_out_of_typed_values(
    normalized_unit: str | None, quantity_semantics: str | None
) -> None:
    context, decision = _security()
    service = JsonRecordRegistrationService(
        CatalogRecordService(SimpleNamespace(), SimpleNamespace())
    )
    binding = _number_binding(
        normalized_unit=normalized_unit, quantity_semantics=quantity_semantics
    )

    candidate = service._value(
        context,
        decision,
        binding,
        2,
        {"record": {"stress": 2}},
        references={},
        curve_artifacts={},
        filename="tensile.json",
    )

    assert candidate is None


def test_complete_exact_number_binding_still_normalizes_to_typed_value() -> None:
    context, decision = _security()
    service = JsonRecordRegistrationService(
        CatalogRecordService(SimpleNamespace(), SimpleNamespace())
    )
    binding = _number_binding(
        normalized_unit="Pa", quantity_semantics="mechanics.stress.engineering"
    )

    candidate = service._value(
        context,
        decision,
        binding,
        2,
        {"record": {"stress": 2}},
        references={},
        curve_artifacts={},
        filename="tensile.json",
    )

    assert isinstance(candidate, CatalogRecordValue)
    assert candidate.original_value == Decimal("2")
    assert candidate.original_unit_string == "MPa"
    assert candidate.normalized_value == Decimal("2000000")
    assert candidate.normalized_unit == "Pa"
    assert candidate.quantity_semantics == "mechanics.stress.engineering"


class _FakeArtifactReader:
    def __init__(self) -> None:
        self.values: dict[UUID, tuple[SimpleNamespace, bytes]] = {}

    async def read_verified_bytes(
        self,
        _context: object,
        _decision: object,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[SimpleNamespace, bytes]:
        assert maximum_bytes > 0
        return self.values[artifact_id]


class _FakeProvenance:
    def __init__(self) -> None:
        self.value: Mapping[str, object] | None = None

    def get_provenance(self, **_kwargs: object) -> Mapping[str, object] | None:
        return self.value


def _curve_format() -> InstalledJsonRecordFormat:
    curve_attribute = SimpleNamespace(
        id=uuid4(),
        current=SimpleNamespace(
            record=SimpleNamespace(revision_id=uuid4()),
            content=SimpleNamespace(
                key="curve",
                name="Stress curve",
                data_type=AttributeDataType.CURVE,
                business_key=False,
                normalized_unit="MPa",
            ),
        ),
    )
    return replace(
        _format(),
        schema={
            "type": "object",
            "properties": {
                "record": {
                    "type": "object",
                    "required": ["id", "curve"],
                    "properties": {
                        "id": {"type": "string", "x-business-key": True},
                        "curve": {
                            "type": "object",
                            "x-curve": {
                                "x_pointer": "/x",
                                "y_pointer": "/y",
                                "x_unit": "s",
                                "y_unit": "MPa",
                            },
                            "properties": {
                                "x": {"type": "array", "items": {"type": "number"}},
                                "y": {"type": "array", "items": {"type": "number"}},
                            },
                        },
                    },
                }
            },
        },
        attributes=(
            JsonAttributeBinding(
                "/record/curve",
                cast(AttributeSnapshot, curve_attribute),
                curve={
                    "x_pointer": "/x",
                    "y_pointer": "/y",
                    "x_unit": "s",
                    "y_unit": "MPa",
                },
                section="Results",
            ),
        ),
    )


class _CurveAssociationResult:
    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.rows = tuple(rows)

    def mappings(self) -> _CurveAssociationResult:
        return self

    def all(self) -> list[Mapping[str, object]]:
        return list(self.rows)


class _CurveAssociationSession:
    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.rows = tuple(rows)

    def execute(self, _statement: sa.ClauseElement) -> _CurveAssociationResult:
        return _CurveAssociationResult(self.rows)


def _curve_association_inputs() -> tuple[
    SecurityContext,
    InstalledJsonRecordFormat,
    JsonRegistrationFile,
    Mapping[str, Any],
    UUID,
    JsonCurveArtifactIdentity,
    dict[str, object],
]:
    context, _ = _security()
    format_value = _curve_format()
    source = JsonRegistrationFile(
        "curve.json",
        b'{"record":{"id":"CURVE-1","curve":{"x":[0,1],"y":[10,20]}}}',
    )
    document = cast(Mapping[str, Any], parse_strict_json(source.content, filename=source.filename))
    batch_id = uuid4()
    identity = JsonCurveArtifactIdentity(uuid4(), "c" * 64, 12)
    row: dict[str, object] = {
        "original_filename": source.filename,
        "json_pointer": "/record/curve",
        "component_ordinal": 1,
        "artifact_id": identity.artifact_id,
        "artifact_sha256": identity.sha256,
        "artifact_size_bytes": identity.size_bytes,
    }
    return context, format_value, source, document, batch_id, identity, row


def test_curve_associations_match_finalized_artifact_identity() -> None:
    context, format_value, source, document, batch_id, identity, row = (
        _curve_association_inputs()
    )
    repository = SqlAlchemyJsonRegistrationRepository(
        session_factory=cast(Callable[[], Session], lambda: None),
        rls_context=cast(RlsContext, SimpleNamespace()),
    )

    repository._validate_curve_associations_in_transaction(
        session=cast(Session, _CurveAssociationSession((row,))),
        context=context,
        format_value=format_value,
        batch_id=batch_id,
        file_documents={(source.filename, source.sha256): document},
        ordered_files=(source,),
        curve_artifacts={(source.filename, "/record/curve"): identity},
    )


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("missing", "incomplete"),
        ("extra", "incomplete"),
        ("artifact_id", "identity is inconsistent"),
        ("artifact_sha256", "identity is inconsistent"),
        ("artifact_size_bytes", "identity is inconsistent"),
        ("component_ordinal", "component order changed"),
    ),
)
def test_curve_associations_reject_missing_extra_or_mismatched_identity(
    case: str, message: str
) -> None:
    context, format_value, source, document, batch_id, identity, row = (
        _curve_association_inputs()
    )
    rows: tuple[Mapping[str, object], ...]
    if case == "missing":
        rows = ()
    elif case == "extra":
        extra = dict(row)
        extra["json_pointer"] = "/record/other-curve"
        rows = (row, extra)
    else:
        changed = dict(row)
        if case == "artifact_id":
            changed["artifact_id"] = uuid4()
        elif case == "artifact_sha256":
            changed["artifact_sha256"] = "d" * 64
        elif case == "artifact_size_bytes":
            changed["artifact_size_bytes"] = identity.size_bytes + 1
        else:
            changed["component_ordinal"] = 2
        rows = (changed,)
    repository = SqlAlchemyJsonRegistrationRepository(
        session_factory=cast(Callable[[], Session], lambda: None),
        rls_context=cast(RlsContext, SimpleNamespace()),
    )

    with pytest.raises(ValueError, match=message):
        repository._validate_curve_associations_in_transaction(
            session=cast(Session, _CurveAssociationSession(rows)),
            context=context,
            format_value=format_value,
            batch_id=batch_id,
            file_documents={(source.filename, source.sha256): document},
            ordered_files=(source,),
            curve_artifacts={(source.filename, "/record/curve"): identity},
        )


class _FakeCurveArtifacts:
    def __init__(self) -> None:
        self.calls = 0
        self.idempotency_keys: list[str] = []
        self.artifact_id = uuid4()
        self.artifact_sha256 = "c" * 64
        self.artifact_size_bytes = 12

    async def finalize_derived_bytes(
        self, *_args: object, **kwargs: object
    ) -> SimpleNamespace:
        self.calls += 1
        self.idempotency_keys.append(cast(str, kwargs["idempotency_key"]))
        artifact = SimpleNamespace(
            id=self.artifact_id,
            sha256=self.artifact_sha256,
            size_bytes=self.artifact_size_bytes,
        )
        finalized = SimpleNamespace(record=SimpleNamespace(artifact=artifact))
        if self.calls == 1:
            commit_hook = cast(Callable[[str, SimpleNamespace], None], kwargs["commit_hook"])
            commit_hook("artifact-session", finalized)
        return SimpleNamespace(artifact=artifact)


class _CurvePersistence:
    def __init__(self) -> None:
        self.batch_id: UUID | None = None
        self.associations: list[tuple[UUID, str, str, UUID]] = []
        self.curve_artifacts: dict[
            tuple[str, str], JsonCurveArtifactIdentity
        ] = {}
        self.persist_attempts = 0
        self.ready_events = 0
        self.record_facts = 0

    def save_preview(self, **_kwargs: object) -> None:
        return None

    def ensure_pending_batch(self, *, batch_id: UUID, **_kwargs: object) -> UUID:
        if self.batch_id is None:
            self.batch_id = batch_id
        assert self.batch_id is not None
        return self.batch_id

    def persist_curve_artifact_in_transaction(self, **kwargs: object) -> None:
        association = (
            cast(UUID, kwargs["batch_id"]),
            cast(str, kwargs["filename"]),
            cast(str, kwargs["json_pointer"]),
            cast(UUID, kwargs["artifact_id"]),
        )
        if association not in self.associations:
            self.associations.append(association)

    def persist_batch_in_transaction(
        self,
        *,
        records: Sequence[object],
        curve_artifacts: Mapping[tuple[str, str], JsonCurveArtifactIdentity],
        **_kwargs: object,
    ) -> None:
        self.curve_artifacts = dict(curve_artifacts)
        self.persist_attempts += 1
        if self.persist_attempts == 1:
            raise RuntimeError("injected post-Artifact Record transaction failure")
        self.record_facts = len(records)
        self.ready_events += 1


class _FailingAtomicRecords(_FakeRecords):
    def create_records_atomically(self, **kwargs: object) -> tuple[SimpleNamespace, ...]:
        self.calls += 1
        commands = cast(tuple[tuple[UUID, CreateRecord], ...], kwargs["records"])
        self.commands = commands
        records = tuple(
            SimpleNamespace(
                id=uuid4(),
                current=SimpleNamespace(
                    record=SimpleNamespace(revision_id=uuid4(), revision_no=1),
                    content=command.content,
                ),
            )
            for _, command in commands
        )
        callback = kwargs.get("after_create")
        if callback is not None:
            after_create = cast(
                Callable[[object, Sequence[SimpleNamespace]], None], callback
            )
            after_create("record-session", records)
        self.created_records = records
        return records


@pytest.mark.anyio
async def test_curve_artifact_failure_reuses_batch_and_artifact_identities() -> None:
    context, decision = _security()
    records = _FailingAtomicRecords()
    artifacts = _FakeCurveArtifacts()
    persistence = _CurvePersistence()
    service = JsonRecordRegistrationService(
        _as_catalog_records(records),
        formats={FORMAT_REVISION: _curve_format()},
        artifact_service=cast(ArtifactService, artifacts),
        persistence=_as_registration_persistence(persistence),
    )
    source = JsonRegistrationFile(
        "curve.json",
        b'{"record":{"id":"CURVE-1","curve":{"x":[0,1],"y":[10,20]}}}',
    )
    preview = service.preview(
        context,
        decision,
        format_revision_id=FORMAT_REVISION,
        files=(source,),
    )
    assert preview.valid is True

    with pytest.raises(RuntimeError, match="post-Artifact"):
        await service.save_async(
            context,
            decision,
            token=preview.token,
            format_revision_id=FORMAT_REVISION,
            package_sha256=preview.package_sha256,
            change_reason="Injected failure",
        )
    assert persistence.batch_id is not None
    first_key = artifacts.idempotency_keys[0]
    expected_key = "json-record-curve-" + hashlib.sha256(
        f"{persistence.batch_id}:{preview.package_sha256}:curve.json:/record/curve".encode()
    ).hexdigest()
    assert first_key == expected_key
    distinct_batch_key = "json-record-curve-" + hashlib.sha256(
        f"{uuid4()}:{preview.package_sha256}:curve.json:/record/curve".encode()
    ).hexdigest()
    assert first_key != distinct_batch_key
    assert persistence.associations == [
        (persistence.batch_id, "curve.json", "/record/curve", artifacts.artifact_id)
    ]
    assert persistence.record_facts == 0
    assert persistence.ready_events == 0
    assert service._tokens[preview.token].state == "open"

    result = await service.save_async(
        context,
        decision,
        token=preview.token,
        format_revision_id=FORMAT_REVISION,
        package_sha256=preview.package_sha256,
        change_reason="Retry after failure",
    )
    assert result.batch_id == persistence.batch_id
    assert artifacts.calls == 2
    assert artifacts.idempotency_keys == [first_key, first_key]
    assert persistence.persist_attempts == 2
    assert persistence.ready_events == 1
    assert persistence.record_facts == 1
    assert len(persistence.associations) == 1
    identity = persistence.curve_artifacts[("curve.json", "/record/curve")]
    assert (identity.artifact_id, identity.sha256, identity.size_bytes) == (
        artifacts.artifact_id,
        artifacts.artifact_sha256,
        artifacts.artifact_size_bytes,
    )


@pytest.mark.anyio
async def test_durable_source_download_reads_verified_artifact_records_for_raw_and_zip() -> None:
    context, write_decision = _security()
    read_decision = replace(write_decision, permission=Permission.CATALOG_READ)
    artifacts = _FakeArtifactReader()
    persistence = _FakeProvenance()
    service = JsonRecordRegistrationService(
        _as_catalog_records(_FakeRecords()),
        artifact_service=cast(ArtifactService, artifacts),
        persistence=_as_registration_persistence(persistence),
    )

    raw = b'{"record":{"id":"RAW-1"}}'
    raw_artifact_id = uuid4()
    artifacts.values[raw_artifact_id] = (
        SimpleNamespace(
            artifact=SimpleNamespace(
                media_type=JSON_MEDIA_TYPE,
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
            )
        ),
        raw,
    )
    persistence.value = {
        "source_artifact_id": raw_artifact_id,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_length_bytes": len(raw),
        "package_artifact_id": None,
        "package_component_path": None,
        "original_filename": "raw.json",
        "classification": "internal",
    }
    filename, media_type, value = await service.source_download_async(
        context,
        read_decision,
        record_id=uuid4(),
        revision_id=uuid4(),
    )
    assert (filename, media_type, value) == ("raw.json", JSON_MEDIA_TYPE, raw)

    component = JsonRegistrationFile("zip.json", b'{"record":{"id":"ZIP-1"}}')
    package = build_registration_package(
        (component,),
        scope={"classification": "internal"},
        format_pins={"format_revision_id": str(FORMAT_REVISION)},
    )
    package_artifact_id = uuid4()
    artifacts.values[package_artifact_id] = (
        SimpleNamespace(
            artifact=SimpleNamespace(
                media_type=JSON_PACKAGE_MEDIA_TYPE,
                sha256=package.sha256,
                size_bytes=len(package.archive),
            )
        ),
        package.archive,
    )
    verified_component = verify_registration_package(
        package.archive, expected_classification="internal"
    )[0]
    persistence.value = {
        "source_artifact_id": None,
        "source_sha256": verified_component.sha256,
        "source_length_bytes": verified_component.size_bytes,
        "package_artifact_id": package_artifact_id,
        "package_component_path": verified_component.package_path,
        "package_sha256": package.sha256,
        "original_filename": verified_component.filename,
        "classification": "internal",
    }
    filename, media_type, value = await service.source_download_async(
        context,
        read_decision,
        record_id=uuid4(),
        revision_id=uuid4(),
    )
    assert (filename, media_type, value) == ("zip.json", JSON_MEDIA_TYPE, component.content)


def test_service_preview_is_non_authoritative_and_save_replay_returns_same_draft_records() -> None:
    context, decision = _security()
    records = _FakeRecords()
    service = JsonRecordRegistrationService(
        _as_catalog_records(records), formats={FORMAT_REVISION: _format()}
    )
    source = JsonRegistrationFile("record.json", b'{"record":{"id":"R-1"}}')
    preview = service.preview(
        context,
        decision,
        format_revision_id=FORMAT_REVISION,
        files=(source,),
    )
    assert preview.valid is True
    assert records.calls == 0
    first = service.save(
        context,
        decision,
        token=preview.token,
        format_revision_id=FORMAT_REVISION,
        package_sha256=preview.package_sha256,
        change_reason="JSON registration test",
    )
    replay = service.save(
        context,
        decision,
        token=preview.token,
        format_revision_id=FORMAT_REVISION,
        package_sha256=preview.package_sha256,
        change_reason="JSON registration retry",
    )
    assert first.replayed is False
    assert replay.replayed is True
    assert replay.batch_id == first.batch_id
    assert replay.records == first.records
    assert records.calls == 1
    read_decision = replace(decision, permission=Permission.CATALOG_READ)
    csv_filename, _, _ = service.source_csv_download(
        context,
        read_decision,
        record_id=first.records[0].id,
        revision_id=first.records[0].current.record.revision_id,
    )
    assert csv_filename == "test-records__r1.csv"


def test_service_auto_resolves_one_wrapper_and_reports_ambiguous_formats() -> None:
    context, decision = _security()
    source = JsonRegistrationFile("record.json", b'{"record":{"id":"R-AUTO"}}')

    unique = JsonRecordRegistrationService(
        _as_catalog_records(_FakeRecords()), formats={FORMAT_REVISION: _format()}
    )
    preview = unique.preview(context, decision, files=(source,))
    assert preview.valid is True
    assert preview.format_revision_id == str(FORMAT_REVISION)
    assert preview.detected_record_type == "test-records"
    assert preview.format is not None
    assert preview.format["wrapper"] == "record"

    second_revision = uuid4()
    second_format = replace(_format(), format_revision_id=second_revision)
    ambiguous = JsonRecordRegistrationService(
        _as_catalog_records(_FakeRecords()),
        formats={FORMAT_REVISION: _format(), second_revision: second_format},
    )
    rejected = ambiguous.preview(context, decision, files=(source,))
    assert rejected.valid is False
    assert rejected.format_revision_id is None
    assert rejected.files[0].errors[0].code == "format_ambiguous"
    assert rejected.files[0].errors[0].pointer == "/"


def test_service_passes_only_verified_exact_domain_pins_to_atomic_record_commands() -> None:
    context, decision = _security()
    records = _FakeRecords()
    service = JsonRecordRegistrationService(
        _as_catalog_records(records), formats={FORMAT_REVISION: _format()}
    )
    binding = (
        "test_data",
        UUID("70000000-0000-4000-8000-00000000000c"),
        UUID("70000000-0000-4000-8000-00000000000d"),
    )
    preview = service.preview(
        context,
        decision,
        format_revision_id=FORMAT_REVISION,
        files=(JsonRegistrationFile("record.json", b'{"record":{"id":"R-2"}}'),),
        domain_bindings=(binding,),
    )
    service.save(
        context,
        decision,
        token=preview.token,
        format_revision_id=FORMAT_REVISION,
        package_sha256=preview.package_sha256,
        change_reason="JSON registration exact binding test",
    )
    assert records.domain_binding_calls == [
        (DataClassification.INTERNAL, binding),
        (DataClassification.INTERNAL, binding),
    ]
    assert records.commands[0][1].domain_bindings == (binding,)
