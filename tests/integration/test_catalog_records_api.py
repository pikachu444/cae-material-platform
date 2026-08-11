from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from cmp.modules.artifacts.domain import ArtifactKind
from cmp.modules.catalog.adapters.api.configurable import install_configurable_catalog_api
from cmp.modules.catalog.adapters.api.records import install_catalog_record_api
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.records import (
    FOLDER_AGGREGATE_TYPE,
    RECORD_AGGREGATE_TYPE,
    FolderSnapshot,
    RecordComparison,
    RecordFacetBucket,
    RecordSearchResult,
    RecordSnapshot,
    RecordValueDifference,
    RegistrationPreview,
)
from cmp.modules.catalog.domain.configurable import AttributeDataType
from cmp.modules.catalog.domain.records import CatalogRecordContent, CatalogRecordValue
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    CurvePoint,
    normalized_parquet_bytes,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
ORG = UUID("dc000000-0000-4000-8000-000000000001")
PROJECT = UUID("dc000000-0000-4000-8000-000000000002")
ACTOR = UUID("dc000000-0000-4000-8000-000000000003")
TABLE = UUID("dc000000-0000-4000-8000-000000000004")
TABLE_REV = UUID("dc000000-0000-4000-8000-000000000005")
ATTRIBUTE = UUID("dc000000-0000-4000-8000-000000000006")
ATTRIBUTE_REV = UUID("dc000000-0000-4000-8000-000000000007")
FOLDER = UUID("dc000000-0000-4000-8000-000000000008")
FOLDER_REV = UUID("dc000000-0000-4000-8000-000000000009")
RECORD = UUID("dc000000-0000-4000-8000-000000000010")
RECORD_REV_1 = UUID("dc000000-0000-4000-8000-000000000011")
RECORD_REV_2 = UUID("dc000000-0000-4000-8000-000000000012")
RAW_ASSET = UUID("dc000000-0000-4000-8000-000000000013")
RAW_ARTIFACT = UUID("dc000000-0000-4000-8000-000000000014")
CURVE_ARTIFACT = UUID("dc000000-0000-4000-8000-000000000015")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog User", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-000000000000000000000000000000dc-00000000000000dc-01",
        authenticated_at=NOW,
    )


CONTEXT = _context()


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


def _revision(
    aggregate_type: str,
    aggregate_id: UUID,
    revision_id: UUID,
    revision_no: int,
    based_on: UUID | None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        aggregate_type,
        aggregate_id,
        TenantScope(ORG, PROJECT, "internal"),
        revision_no,
        based_on,
        f"urn:cmp:{aggregate_type}:1.0.0",
        "1.0.0",
        ("a" if revision_no == 1 else "b") * 64,
        NOW,
        ACTOR,
        "API fixture",
        CONTEXT.request_id,
        CONTEXT.trace_id,
    )


class _Service:
    def __init__(self) -> None:
        self.folder: FolderSnapshot | None = None
        self.record: RecordSnapshot | None = None
        self.revisions: list[ConfigRevision[Any]] = []
        self.last_query: Any | None = None
        self.registration: dict[str, Any] | None = None

    def create_folder(self, context: Any, decision: Any, command: Any) -> FolderSnapshot:
        del context, decision
        self.folder = FolderSnapshot(
            FOLDER,
            TABLE,
            ConfigRevision(
                _revision(FOLDER_AGGREGATE_TYPE, FOLDER, FOLDER_REV, 1, None), command.content
            ),
        )
        return self.folder

    def list_folders(self, context: Any, decision: Any, table_id: UUID) -> tuple[Any, ...]:
        del context, decision
        assert table_id == TABLE
        return (self.folder,) if self.folder else ()

    def get_folder_for_write(self, context: Any, decision: Any, folder_id: UUID) -> Any:
        del context, decision
        assert folder_id == FOLDER and self.folder is not None
        return self.folder

    def revise_folder(self, context: Any, decision: Any, folder_id: UUID, command: Any) -> Any:
        del context, decision, folder_id, command
        assert self.folder is not None
        return self.folder

    def create_record(self, context: Any, decision: Any, command: Any) -> RecordSnapshot:
        del context, decision
        current = ConfigRevision(
            _revision(RECORD_AGGREGATE_TYPE, RECORD, RECORD_REV_1, 1, None), command.content
        )
        self.record = RecordSnapshot(RECORD, TABLE, current)
        self.revisions = [current]
        return self.record

    def get_record(self, context: Any, decision: Any, record_id: UUID) -> RecordSnapshot:
        del context, decision
        assert record_id == RECORD and self.record is not None
        return self.record

    def get_record_for_write(self, context: Any, decision: Any, record_id: UUID) -> RecordSnapshot:
        return self.get_record(context, decision, record_id)

    def get_record_revision(
        self,
        context: Any,
        decision: Any,
        record_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[Any]:
        del context, decision
        assert record_id == RECORD
        return next(item for item in self.revisions if item.record.revision_id == revision_id)

    def resolve_curve_ownership(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    def revise_record(
        self, context: Any, decision: Any, record_id: UUID, command: Any
    ) -> RecordSnapshot:
        del context, decision
        assert record_id == RECORD
        current = ConfigRevision(
            _revision(RECORD_AGGREGATE_TYPE, RECORD, RECORD_REV_2, 2, RECORD_REV_1),
            command.content,
        )
        self.record = RecordSnapshot(RECORD, TABLE, current)
        self.revisions.append(current)
        return self.record

    def list_record_revisions(
        self, context: Any, decision: Any, record_id: UUID
    ) -> tuple[Any, ...]:
        del context, decision
        assert record_id == RECORD
        return tuple(self.revisions)

    def search_records(self, context: Any, decision: Any, query: Any) -> RecordSearchResult:
        del context, decision
        self.last_query = query
        assert query.table_id == TABLE and self.record is not None
        return RecordSearchResult((self.record,), 1, (RecordFacetBucket(ATTRIBUTE, "Steel", 1),))

    def compare_record_revisions(
        self,
        context: Any,
        decision: Any,
        record_id: UUID,
        from_revision_id: UUID,
        to_revision_id: UUID,
    ) -> RecordComparison:
        del context, decision
        assert record_id == RECORD
        assert from_revision_id == RECORD_REV_1 and to_revision_id == RECORD_REV_2
        before = self.revisions[0]
        after = self.revisions[1]
        return RecordComparison(
            RECORD,
            before,
            after,
            False,
            (
                RecordValueDifference(
                    ATTRIBUTE,
                    "changed",
                    before.content.values[0],
                    after.content.values[0],
                ),
            ),
        )

    def preview_registration(self, context: Any, decision: Any, **values: Any) -> Any:
        del context, decision
        self.registration = values
        return RegistrationPreview("opaque-token", True, values["rows"], ())


def _app(service: _Service, artifact_service: Any | None = None) -> FastAPI:
    app = FastAPI()

    async def security(request: Request) -> SecurityContext:
        request.state.security_context = CONTEXT
        return CONTEXT

    async def read(request: Request) -> AuthorizationDecision:
        decision = _decision(Permission.CATALOG_READ)
        request.state.authorization_decision = decision
        return decision

    async def write(request: Request) -> AuthorizationDecision:
        decision = _decision(Permission.CATALOG_WRITE)
        request.state.authorization_decision = decision
        return decision

    install_configurable_catalog_api(
        app,
        service=None,
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    install_catalog_record_api(
        app,
        service=cast(Any, service),
        artifact_service=artifact_service,
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return app


async def _request(app: FastAPI, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path, **kwargs)


class _Artifacts:
    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[Any, bytes]:
        assert context == CONTEXT
        assert decision.permission is Permission.CATALOG_WRITE
        assert Permission.ARTIFACT_READ in decision.database_permissions
        assert artifact_id == RAW_ARTIFACT
        assert maximum_bytes == 16 * 1024 * 1024
        return (
            SimpleNamespace(
                artifact=SimpleNamespace(
                    artifact_kind=ArtifactKind.RAW,
                    source_raw_asset_id=RAW_ASSET,
                    sha256="a" * 64,
                    media_type="text/csv",
                )
            ),
            b"Material;Code;E\nSteel A;A;210,5\nSteel B;B;205,0\n",
        )


class _CurveArtifacts:
    def __init__(self, value: bytes, *, schema_ref: str = REFERENCE_TENSILE_PARQUET_SCHEMA):
        self.value = value
        self.schema_ref = schema_ref
        self.sha256 = hashlib.sha256(value).hexdigest()

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[Any, bytes]:
        assert context == CONTEXT
        assert decision.permission in {Permission.CATALOG_READ, Permission.CATALOG_WRITE}
        assert Permission.ARTIFACT_READ in decision.database_permissions
        assert artifact_id == CURVE_ARTIFACT
        assert maximum_bytes == 64 * 1024 * 1024
        return (
            SimpleNamespace(
                artifact=SimpleNamespace(
                    id=CURVE_ARTIFACT,
                    artifact_kind=ArtifactKind.DERIVED,
                    sha256=self.sha256,
                    media_type="application/vnd.apache.parquet",
                    schema_ref=self.schema_ref,
                )
            ),
            self.value,
        )


def _record_body(modulus: str) -> dict[str, Any]:
    return {
        "classification": "internal",
        "content": {
            "table_revision_id": str(TABLE_REV),
            "name": "DP600 Sheet",
            "external_key": "dp600",
            "description": "Demo steel",
            "folder_id": str(FOLDER),
            "folder_revision_id": str(FOLDER_REV),
            "values": [
                {
                    "data_type": "number",
                    "attribute_definition_id": str(ATTRIBUTE),
                    "attribute_definition_revision_id": str(ATTRIBUTE_REV),
                    "original_value": str(Decimal(modulus) / Decimal("1000000")),
                    "original_unit_string": "MPa",
                    "normalized_value": modulus,
                    "normalized_unit": "Pa",
                    "quantity_semantics": "modulus.elastic.young",
                }
            ],
        },
        "change_reason": "API record fixture",
    }


def _curve_record_body(sha256: str) -> dict[str, Any]:
    body = _record_body("210000000000")
    body["content"]["values"] = [
        {
            "data_type": "curve",
            "attribute_definition_id": str(ATTRIBUTE),
            "attribute_definition_revision_id": str(ATTRIBUTE_REV),
            "artifact_id": str(CURVE_ARTIFACT),
            "artifact_sha256": sha256,
        }
    ]
    return body


@pytest.mark.anyio
async def test_registration_preview_reads_the_verified_source_and_preserves_mapping() -> None:
    service = _Service()
    app = _app(service, _Artifacts())

    response = await _request(
        app,
        "POST",
        "/api/v1/catalog/record-registrations:preview",
        json={
            "table_id": str(TABLE),
            "table_revision_id": str(TABLE_REV),
            "mapping": {
                "Material": "name",
                "Code": "code",
                "E": {"attribute": "youngs_modulus", "unit": "GPa"},
            },
            "raw_asset_id": str(RAW_ASSET),
            "raw_artifact_id": str(RAW_ARTIFACT),
            "file_format": "csv",
            "header_row": 1,
            "encoding": "utf-8",
            "delimiter": ";",
            "decimal_separator": ",",
            "corrections": {"2": {"Code": "B-corrected"}},
        },
    )

    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"Material": "Steel A", "Code": "A", "E": "210,5"},
        {"Material": "Steel B", "Code": "B-corrected", "E": "205,0"},
    ]
    assert service.registration is not None
    assert service.registration["mapping"]["E"] == {
        "attribute": "youngs_modulus",
        "unit": "GPa",
    }
    assert service.registration["rows"][1]["Code"] == "B-corrected"
    assert service.registration["source"].artifact_id == RAW_ARTIFACT
    assert service.registration["source"].sha256 == "a" * 64


@pytest.mark.anyio
async def test_record_api_preserves_units_searches_and_compares() -> None:
    service = _Service()
    app = _app(service)
    folder = await _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/folders",
        json={
            "classification": "internal",
            "content": {
                "table_revision_id": str(TABLE_REV),
                "name": "Steels",
                "description": None,
                "parent_folder_id": None,
                "parent_folder_revision_id": None,
            },
            "change_reason": "create folder",
        },
    )
    assert folder.status_code == 201

    created = await _request(
        app, "POST", f"/api/v1/catalog/tables/{TABLE}/records", json=_record_body("210000000000")
    )
    assert created.status_code == 201
    value = created.json()["current_revision"]["content"]["values"][0]
    assert value["original_unit_string"] == "MPa"
    assert value["normalized_unit"] == "Pa"
    assert Decimal(value["normalized_value"]) == Decimal("210000000000")
    assert created.headers["etag"].startswith('"revision:')

    searched = await _request(
        app,
        "POST",
        "/api/v1/catalog/records:search",
        json={
            "table_id": str(TABLE),
            "text": "DP600",
            "facet_attribute_ids": [str(ATTRIBUTE)],
            "domain_binding_kind": "material",
            "include_descendants": True,
            "sort_by": "attribute",
            "sort_attribute_id": str(ATTRIBUTE),
            "sort_direction": "descending",
        },
    )
    assert searched.status_code == 200
    assert searched.json()["total_count"] == 1
    assert service.last_query is not None
    assert service.last_query.domain_binding_kind == "material"
    assert service.last_query.include_descendants is True
    assert service.last_query.sort_by == "attribute"
    assert service.last_query.sort_attribute_id == ATTRIBUTE
    assert service.last_query.sort_direction == "descending"
    assert searched.json()["facets"][0] == {
        "attribute_definition_id": str(ATTRIBUTE),
        "value": "Steel",
        "count": 1,
    }

    revised_body = _record_body("205000000000")
    revised_body.pop("classification")
    revised = await _request(
        app,
        "POST",
        f"/api/v1/catalog/records/{RECORD}/revisions",
        json=revised_body,
        headers={"If-Match": created.headers["etag"]},
    )
    assert revised.status_code == 201
    compared = await _request(
        app,
        "GET",
        f"/api/v1/catalog/records/{RECORD}/revisions:compare"
        f"?from_revision_id={RECORD_REV_1}&to_revision_id={RECORD_REV_2}",
    )
    assert compared.status_code == 200
    assert compared.json()["value_differences"][0]["status"] == "changed"


@pytest.mark.anyio
async def test_record_api_rejects_ambiguous_typed_value_payload() -> None:
    body = _record_body("210000000000")
    body["content"]["values"][0]["value"] = "not allowed on a number"
    response = await _request(
        _app(_Service()),
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/records",
        json=body,
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_curve_pointer_requires_declared_metadata_and_previews_exact_revision() -> None:
    parquet = normalized_parquet_bytes(
        (
            CurvePoint(0.0, 0.0),
            CurvePoint(0.01, 200_000_000.0),
            CurvePoint(0.02, 350_000_000.0),
        )
    )
    artifacts = _CurveArtifacts(parquet)
    service = _Service()
    app = _app(service, artifacts)

    created = await _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/records",
        json=_curve_record_body(artifacts.sha256),
    )
    assert created.status_code == 201

    preview = await _request(
        app,
        "GET",
        f"/api/v1/catalog/records/{RECORD}/revisions/{RECORD_REV_1}/"
        f"curve-values/{ATTRIBUTE}/preview?maximum_points=2",
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["curve_metadata"]["metadata_state"] == "declared"
    assert payload["curve_metadata"]["artifact"]["sha256"] == artifacts.sha256
    assert payload["curve_metadata"]["owning_revision"] == {
        "entity_type": "catalog_record",
        "entity_id": str(RECORD),
        "revision_id": str(RECORD_REV_1),
    }
    assert [item["key"] for item in payload["curve_metadata"]["definition"]["channels"]] == [
        "engineering_strain",
        "engineering_stress",
    ]
    assert payload["curve_series"]["point_count"] == 3
    assert payload["curve_series"]["indices"] == [0, 2]
    returned_channels = {
        item["key"]: item["values"] for item in payload["curve_series"]["channels"]
    }
    assert returned_channels["engineering_stress"] == [0.0, 350_000_000.0]

    rejected = await _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/records",
        json=_curve_record_body("f" * 64),
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "CMP-CATALOG-0020"


@pytest.mark.anyio
async def test_unchanged_historical_unknown_curve_pointer_remains_revisable_without_backfill(
) -> None:
    value = CatalogRecordValue(
        ATTRIBUTE,
        ATTRIBUTE_REV,
        AttributeDataType.CURVE,
        artifact_id=CURVE_ARTIFACT,
        artifact_sha256="e" * 64,
    )
    content = CatalogRecordContent(
        TABLE,
        TABLE_REV,
        "Historical curve",
        "historical-curve",
        "Predates curve channel metadata",
        FOLDER,
        FOLDER_REV,
        (value,),
    )
    current = ConfigRevision(
        _revision(RECORD_AGGREGATE_TYPE, RECORD, RECORD_REV_1, 1, None),
        content,
    )
    service = _Service()
    service.record = RecordSnapshot(RECORD, TABLE, current)
    service.revisions = [current]
    body = _curve_record_body("e" * 64)
    body.pop("classification")
    body["content"].update(
        {
            "name": "Historical curve",
            "external_key": "historical-curve",
            "description": "Predates curve channel metadata",
        }
    )

    revised = await _request(
        _app(service),
        "POST",
        f"/api/v1/catalog/records/{RECORD}/revisions",
        headers={"If-Match": '"revision:1:sha256:' + "a" * 64 + '"'},
        json=body,
    )
    assert revised.status_code == 201, revised.text
