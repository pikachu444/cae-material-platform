from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from cmp.modules.datasets.adapters.api.canonical_test_data import (
    CanonicalTestDataInput,
    install_canonical_test_data_api,
)
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    ExactRevisionRef,
    ExactTestDataRevisionRef,
    GovernedTestDataSource,
    ImportCanonicalTestData,
    ReviseCanonicalTestData,
    canonical_json_bytes,
)
from cmp.modules.datasets.application.canonical_test_data import (
    TestDataChannelSummary as ChannelSummary,
)
from cmp.modules.datasets.application.canonical_test_data import (
    TestDataDocumentContent as DocumentContent,
)
from cmp.modules.datasets.application.canonical_test_data import (
    TestDataDocumentSnapshot as DocumentSnapshot,
)
from cmp.modules.datasets.application.canonical_test_data import (
    test_data_content_canonical as canonical_test_data_content,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.shared.domain.revisions import AggregateAlreadyExists, RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 17, 0, tzinfo=UTC)
ORG = UUID("de000000-0000-4000-8000-000000000001")
PROJECT = UUID("de000000-0000-4000-8000-000000000002")
ACTOR = UUID("de000000-0000-4000-8000-000000000003")
DOCUMENT = UUID("de000000-0000-4000-8000-000000000004")
REVISION = UUID("de000000-0000-4000-8000-000000000005")
REVISION_TWO = UUID("de000000-0000-4000-8000-000000000008")
CANONICAL_ARTIFACT = UUID("de000000-0000-4000-8000-000000000006")
PARQUET_ARTIFACT = UUID("de000000-0000-4000-8000-000000000007")
MATERIAL = UUID("de000000-0000-4000-8000-000000000009")
MATERIAL_REVISION = UUID("de000000-0000-4000-8000-000000000010")
STATE = UUID("de000000-0000-4000-8000-000000000011")
STATE_REVISION = UUID("de000000-0000-4000-8000-000000000012")
TEST_RUN = UUID("de000000-0000-4000-8000-000000000013")
TEST_RUN_REVISION = UUID("de000000-0000-4000-8000-000000000014")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Dataset User", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-000000000000000000000000000000de-00000000000000de-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.DATASET_WRITE,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.DATASET_WRITE),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


class _Service:
    def __init__(self) -> None:
        self.snapshot: DocumentSnapshot | None = None
        self.value = b""

    async def import_document(
        self, context: Any, decision: Any, command: ImportCanonicalTestData
    ) -> DocumentSnapshot:
        del context, decision
        document = command.document
        self.value = canonical_json_bytes(document)
        content = DocumentContent(
            document_key=document.document_id,
            material=document.material,
            test=document.test,
            specimen=document.specimen,
            conditions=document.conditions,
            channels=tuple(
                ChannelSummary(
                    item.key,
                    item.name,
                    item.quantity_semantics,
                    item.axis_role.value,
                    item.original_unit_string,
                    item.normalized_unit,
                    str(item.normalization_scale),
                    str(item.normalization_offset),
                    len(item.original_values),
                    sum(value is None for value in item.original_values),
                )
                for item in document.channels
            ),
            source=document.source,
            canonical_artifact_id=CANONICAL_ARTIFACT,
            canonical_sha256=document.digest,
            normalized_artifact_id=PARQUET_ARTIFACT,
            normalized_sha256="b" * 64,
            point_count=document.point_count,
            governed_source=command.governed_source,
        )
        record = RevisionRecord(
            REVISION,
            "datasets.test_data_document",
            DOCUMENT,
            TenantScope(ORG, PROJECT, command.classification.value),
            1,
            None,
            "urn:cmp:test-data:1.0.0",
            "1.0.0",
            "c" * 64,
            NOW,
            ACTOR,
            command.change_reason,
            CONTEXT.request_id,
            CONTEXT.trace_id,
        )
        self.snapshot = DocumentSnapshot(DOCUMENT, record, content)
        return self.snapshot

    def list_documents(self, *args: Any, **kwargs: Any) -> tuple[DocumentSnapshot, ...]:
        del args, kwargs
        return (self.snapshot,) if self.snapshot else ()

    async def export_document(
        self, *args: Any, **kwargs: Any
    ) -> tuple[DocumentSnapshot, bytes]:
        del args, kwargs
        assert self.snapshot is not None
        return self.snapshot, self.value

    def get_document_for_write(
        self, context: Any, decision: Any, document_id: UUID
    ) -> DocumentSnapshot:
        del context, decision
        assert document_id == DOCUMENT
        assert self.snapshot is not None
        return self.snapshot

    async def revise_document(
        self,
        context: Any,
        decision: Any,
        document_id: UUID,
        command: ReviseCanonicalTestData,
    ) -> DocumentSnapshot:
        del context, decision
        assert document_id == DOCUMENT
        assert command.expected_current_revision_id == REVISION
        assert self.snapshot is not None
        self.value = canonical_json_bytes(command.document)
        record = RevisionRecord(
            REVISION_TWO,
            "datasets.test_data_document",
            DOCUMENT,
            TenantScope(ORG, PROJECT, "internal"),
            2,
            REVISION,
            "urn:cmp:test-data:1.0.0",
            "1.0.0",
            "d" * 64,
            NOW,
            ACTOR,
            command.change_reason,
            CONTEXT.request_id,
            CONTEXT.trace_id,
        )
        self.snapshot = DocumentSnapshot(
            DOCUMENT,
            record,
            replace(self.snapshot.content, governed_source=command.governed_source),
        )
        return self.snapshot

    async def export_package(
        self,
        context: Any,
        decision: Any,
        references: tuple[ExactTestDataRevisionRef, ...],
    ) -> tuple[Any, str, int]:
        return await CanonicalTestDataService.export_package(
            cast(Any, self), context, decision, references
        )


class _ConflictingService(_Service):
    async def import_document(
        self, context: Any, decision: Any, command: ImportCanonicalTestData
    ) -> DocumentSnapshot:
        del context, decision, command
        raise AggregateAlreadyExists("document key already exists")


def _app(service: _Service | None = None) -> FastAPI:
    app = FastAPI()

    async def security(request: Request) -> SecurityContext:
        request.state.security_context = CONTEXT
        return CONTEXT

    async def write(request: Request) -> AuthorizationDecision:
        decision = _decision()
        request.state.authorization_decision = decision
        return decision

    install_canonical_test_data_api(
        app,
        service=cast(Any, service),
        security_dependency=security,
        read_dependency=write,
        write_dependency=write,
    )
    return app


def _fixture() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[2]
    return cast(
        dict[str, Any],
        json.loads(
            (root / "contracts/examples/positive/canonical-test-data.json").read_text(
                encoding="utf-8"
            )
        ),
    )


@pytest.mark.anyio
async def test_test_data_json_preview_preserves_metadata_units_and_missingness() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/test-data:validate", json=_fixture())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["material_maker"] == "CMP Demo Metals"
    assert body["operator"] == "Kim Tester"
    assert body["point_count"] == 3
    assert body["channels"][1]["original_unit_string"] == "MPa"
    assert body["channels"][1]["normalized_unit"] == "Pa"
    assert body["channels"][1]["missing_count"] == 1
    assert body["canonical_document"]["channels"][1]["missing_reasons"][2] == (
        "instrument dropout"
    )


@pytest.mark.anyio
async def test_test_data_json_preview_rejects_incorrect_explicit_normalization() -> None:
    fixture = _fixture()
    fixture["channels"][1]["normalized_values"][1] = "204000000"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/test-data:validate", json=fixture)

    assert response.status_code == 422
    assert "explicit normalization" in response.json()["detail"]


@pytest.mark.anyio
async def test_csv_adapter_and_direct_json_have_identical_canonical_result() -> None:
    source = b"strain,stress\n0,0\n0.001,205\n0.002,310\n"
    request = {
        "document_id": "DP600-CSV-01",
        "material": {"maker": "CMP Demo Metals", "grade": "DP600", "lot_batch": None},
        "test": {
            "date": "2026-07-18",
            "operator": "Kim Tester",
            "laboratory": "CMP Laboratory",
            "method": "uniaxial tensile reference method",
            "equipment_maker": None,
            "equipment_model": None,
        },
        "specimen": {"specimen_id": "CSV-S-01", "description": None},
        "conditions": [],
        "source_file_name": "dp600.csv",
        "source_base64": base64.b64encode(source).decode("ascii"),
        "profile": {
            "profile_label": "DP600 strain-stress CSV",
            "data_schema": "monotonic_tension",
            "file_format": "csv",
            "sheet_name": None,
            "header_row": 1,
            "encoding": "utf-8",
            "delimiter": ",",
            "decimal_separator": ".",
            "channels": [
                {
                    "ordinal": 0,
                    "source_column": "strain",
                    "source_quantity": "engineering_strain",
                    "original_unit": "1",
                    "axis_role": "independent",
                },
                {
                    "ordinal": 1,
                    "source_column": "stress",
                    "source_quantity": "engineering_stress",
                    "original_unit": "MPa",
                    "axis_role": "dependent",
                },
            ],
            "initial_gauge_length_m": None,
            "initial_cross_section_area_m2": None,
            "approval_kind": "human_confirmed",
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        converted = await client.post("/api/v1/test-data:convert-tabular", json=request)
        direct = await client.post(
            "/api/v1/test-data:validate", json=converted.json()["canonical_document"]
        )

    assert converted.status_code == 200
    assert direct.status_code == 200
    assert converted.json()["document_sha256"] == direct.json()["document_sha256"]
    channel = converted.json()["canonical_document"]["channels"][1]
    assert channel["original_unit_string"] == "MPa"
    assert channel["normalized_unit"] == "Pa"
    assert channel["original_values"] == ["0", "205", "310"]
    assert channel["normalized_values"] == ["0", "205000000", "310000000"]


@pytest.mark.anyio
async def test_import_list_and_exact_revision_export_round_trip() -> None:
    service = _Service()
    app = _app(service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/v1/test-data-documents",
            json={
                "classification": "internal",
                "document": _fixture(),
                "change_reason": "Import canonical test evidence",
            },
        )
        listed = await client.get("/api/v1/test-data-documents")
        exported = await client.get(
            f"/api/v1/test-data-documents/{DOCUMENT}/revisions/{REVISION}/content"
        )

    assert imported.status_code == 201
    assert imported.json()["test_data_document_id"] == str(DOCUMENT)
    assert imported.json()["canonical_artifact_id"] == str(CANONICAL_ARTIFACT)
    assert imported.headers["etag"].startswith('"revision:1:')
    assert listed.json()["items"][0]["document_key"] == "DP600-TENSILE-01"
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith('"DP600-TENSILE-01.json"')
    assert json.loads(exported.content) == _fixture()


@pytest.mark.anyio
async def test_import_returns_exact_server_governed_source_without_changing_artifact_json() -> None:
    service = _Service()
    payload = {
        "material": {
            "aggregate_id": str(MATERIAL),
            "revision_id": str(MATERIAL_REVISION),
        },
        "material_state": {
            "aggregate_id": str(STATE),
            "revision_id": str(STATE_REVISION),
        },
        "test_run": {
            "aggregate_id": str(TEST_RUN),
            "revision_id": str(TEST_RUN_REVISION),
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/v1/test-data-documents",
            json={
                "classification": "internal",
                "document": _fixture(),
                "change_reason": "Register exact governed source",
                "governed_source": payload,
            },
        )
        exported = await client.get(
            f"/api/v1/test-data-documents/{DOCUMENT}/revisions/{REVISION}/content"
        )

    assert imported.status_code == 201
    assert imported.json()["governed_source"] == payload
    assert exported.status_code == 200
    assert "governed_source" not in json.loads(exported.content)

    assert service.snapshot is not None
    governed = GovernedTestDataSource(
        material=ExactRevisionRef(MATERIAL, MATERIAL_REVISION),
        material_state=ExactRevisionRef(STATE, STATE_REVISION),
        test_run=ExactRevisionRef(TEST_RUN, TEST_RUN_REVISION),
    )
    qualified = canonical_test_data_content(
        replace(service.snapshot.content, governed_source=governed)
    )
    unqualified = canonical_test_data_content(
        replace(service.snapshot.content, governed_source=None)
    )
    assert qualified["governed_source"] == payload
    assert qualified != unqualified


@pytest.mark.anyio
async def test_duplicate_document_identity_is_a_conflict_not_a_server_error() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(_ConflictingService())),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/test-data-documents",
            json={
                "classification": "internal",
                "document": _fixture(),
                "change_reason": "Duplicate identity",
            },
        )

    assert response.status_code == 409


@pytest.mark.anyio
async def test_append_revision_requires_exact_current_etag() -> None:
    service = _Service()
    app = _app(service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        imported = await client.post(
            "/api/v1/test-data-documents",
            json={
                "classification": "internal",
                "document": _fixture(),
                "change_reason": "Import revision one",
            },
        )
        revised = await client.post(
            f"/api/v1/test-data-documents/{DOCUMENT}/revisions",
            headers={"If-Match": imported.headers["etag"]},
            json={"document": _fixture(), "change_reason": "Append revision two"},
        )
        missing_precondition = await client.post(
            f"/api/v1/test-data-documents/{DOCUMENT}/revisions",
            json={"document": _fixture(), "change_reason": "Unsafe append"},
        )

    assert revised.status_code == 201
    assert revised.json()["current_revision"]["revision_no"] == 2
    assert revised.json()["current_revision"]["based_on_revision_id"] == str(REVISION)
    assert missing_precondition.status_code == 428


@pytest.mark.anyio
async def test_exact_revision_package_is_deterministic_and_checksum_verifiable() -> None:
    service = _Service()
    app = _app(service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/test-data-documents",
            json={
                "classification": "internal",
                "document": _fixture(),
                "change_reason": "Package source",
            },
        )
        payload = {"revisions": [{"document_id": str(DOCUMENT), "revision_id": str(REVISION)}]}
        first = await client.post("/api/v1/test-data-packages:download", json=payload)
        second = await client.post("/api/v1/test-data-packages:download", json=payload)

    assert first.status_code == 200
    assert first.content == second.content
    assert first.headers["x-content-sha256"] == hashlib.sha256(first.content).hexdigest()
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        checksums = archive.read("checksums.sha256").decode("ascii")
        data_path = manifest["entries"][0]["path"]
        data = archive.read(data_path)
    assert names == sorted(names)
    assert manifest["document_type"] == "cmp.test-data-package"
    assert manifest["entries"][0]["revision_id"] == str(REVISION)
    assert f"{hashlib.sha256(data).hexdigest()}  {data_path}" in checksums


@pytest.mark.anyio
async def test_large_package_spools_and_streams_in_bounded_chunks() -> None:
    service = _Service()
    await service.import_document(
        CONTEXT,
        _decision(),
        ImportCanonicalTestData(
            DataClassification.INTERNAL,
            CanonicalTestDataInput.model_validate(_fixture()).to_domain(),
            "Prepare large package snapshot",
        ),
    )
    large_value = hashlib.shake_256(b"cmp-large-package-fixture").digest(10 * 1024 * 1024)

    async def large_export(*args: Any, **kwargs: Any) -> tuple[DocumentSnapshot, bytes]:
        del args, kwargs
        assert service.snapshot is not None
        return service.snapshot, large_value

    service.export_document = large_export  # type: ignore[method-assign]
    stream, digest, size = await service.export_package(
        CONTEXT,
        _decision(),
        (ExactTestDataRevisionRef(DOCUMENT, REVISION),),
    )
    try:
        assert size > 8 * 1024 * 1024
        chunks = iter(lambda: stream.read(1024 * 1024), b"")
        package = b"".join(chunks)
    finally:
        stream.close()
    assert len(package) == size
    assert hashlib.sha256(package).hexdigest() == digest
