from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.catalog.adapters.api.configurable import install_configurable_catalog_api
from cmp.modules.catalog.application.configurable import (
    ATTRIBUTE_AGGREGATE_TYPE,
    LAYOUT_AGGREGATE_TYPE,
    SUBSET_AGGREGATE_TYPE,
    TABLE_AGGREGATE_TYPE,
    AttributeSnapshot,
    ConfigRevision,
    LayoutSnapshot,
    SubsetSnapshot,
    TableSnapshot,
)
from cmp.modules.catalog.domain.configurable import ConfigurableCatalogDraftDeleteBlocked
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

NOW = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
ORG = UUID("d9000000-0000-4000-8000-000000000001")
PROJECT = UUID("d9000000-0000-4000-8000-000000000002")
ACTOR = UUID("d9000000-0000-4000-8000-000000000003")
TABLE = UUID("d9000000-0000-4000-8000-000000000004")
TABLE_REVISION = UUID("d9000000-0000-4000-8000-000000000005")
ATTRIBUTE = UUID("d9000000-0000-4000-8000-000000000006")
ATTRIBUTE_REVISION = UUID("d9000000-0000-4000-8000-000000000007")
LAYOUT = UUID("d9000000-0000-4000-8000-000000000008")
LAYOUT_REVISION = UUID("d9000000-0000-4000-8000-000000000009")
SUBSET = UUID("d9000000-0000-4000-8000-000000000010")
SUBSET_REVISION = UUID("d9000000-0000-4000-8000-000000000011")


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Catalog Administrator", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id="00-000000000000000000000000000000d9-00000000000000d9-01",
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


def _record(
    aggregate_type: str, aggregate_id: UUID, revision_id: UUID, digest: str
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:cmp:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash=digest,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="configurable catalog fixture",
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
    )


class _Service:
    def __init__(self) -> None:
        self.table: TableSnapshot | None = None
        self.attribute: AttributeSnapshot | None = None
        self.layout: LayoutSnapshot | None = None
        self.subset: SubsetSnapshot | None = None
        self.deleted: list[tuple[str, UUID, UUID]] = []
        self.delete_block_reason: str | None = None

    def delete_draft(
        self,
        context: Any,
        decision: Any,
        aggregate_type: str,
        aggregate_id: UUID,
        command: Any,
    ) -> None:
        del context, decision
        if self.delete_block_reason is not None:
            raise ConfigurableCatalogDraftDeleteBlocked(self.delete_block_reason)
        self.deleted.append((aggregate_type, aggregate_id, command.expected_current_revision_id))
        if aggregate_type == TABLE_AGGREGATE_TYPE:
            self.table = None

    def create_table(self, context: Any, decision: Any, command: Any) -> TableSnapshot:
        del context, decision
        self.table = TableSnapshot(
            TABLE,
            ConfigRevision(
                _record(TABLE_AGGREGATE_TYPE, TABLE, TABLE_REVISION, "a" * 64), command.content
            ),
        )
        return self.table

    def list_tables(self, context: Any, decision: Any) -> tuple[TableSnapshot, ...]:
        del context, decision
        return (self.table,) if self.table is not None else ()

    def get_table(self, context: Any, decision: Any, table_id: UUID) -> TableSnapshot:
        del context, decision
        assert table_id == TABLE and self.table is not None
        return self.table

    def get_table_for_write(self, context: Any, decision: Any, table_id: UUID) -> TableSnapshot:
        return self.get_table(context, decision, table_id)

    def revise_table(
        self, context: Any, decision: Any, table_id: UUID, command: Any
    ) -> TableSnapshot:
        del context, decision, table_id, command
        assert self.table is not None
        return self.table

    def create_attribute(self, context: Any, decision: Any, command: Any) -> AttributeSnapshot:
        del context, decision
        self.attribute = AttributeSnapshot(
            ATTRIBUTE,
            TABLE,
            ConfigRevision(
                _record(
                    ATTRIBUTE_AGGREGATE_TYPE,
                    ATTRIBUTE,
                    ATTRIBUTE_REVISION,
                    "b" * 64,
                ),
                command.content,
            ),
        )
        return self.attribute

    def list_attributes(
        self, context: Any, decision: Any, table_id: UUID
    ) -> tuple[AttributeSnapshot, ...]:
        del context, decision
        assert table_id == TABLE
        return (self.attribute,) if self.attribute is not None else ()

    def get_attribute_for_write(
        self, context: Any, decision: Any, attribute_id: UUID
    ) -> AttributeSnapshot:
        del context, decision
        assert attribute_id == ATTRIBUTE and self.attribute is not None
        return self.attribute

    def get_attribute_revision(
        self,
        context: Any,
        decision: Any,
        attribute_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[Any]:
        del context, decision
        assert attribute_id == ATTRIBUTE and revision_id == ATTRIBUTE_REVISION
        assert self.attribute is not None
        return self.attribute.current

    def revise_attribute(
        self, context: Any, decision: Any, attribute_id: UUID, command: Any
    ) -> AttributeSnapshot:
        del context, decision, attribute_id, command
        assert self.attribute is not None
        return self.attribute

    def create_layout(self, context: Any, decision: Any, command: Any) -> LayoutSnapshot:
        del context, decision
        self.layout = LayoutSnapshot(
            LAYOUT,
            TABLE,
            ConfigRevision(
                _record(LAYOUT_AGGREGATE_TYPE, LAYOUT, LAYOUT_REVISION, "c" * 64),
                command.content,
            ),
        )
        return self.layout

    def get_layout_for_write(self, context: Any, decision: Any, layout_id: UUID) -> LayoutSnapshot:
        del context, decision
        assert layout_id == LAYOUT and self.layout is not None
        return self.layout

    def revise_layout(
        self, context: Any, decision: Any, layout_id: UUID, command: Any
    ) -> LayoutSnapshot:
        del context, decision, layout_id, command
        assert self.layout is not None
        return self.layout

    def create_subset(self, context: Any, decision: Any, command: Any) -> SubsetSnapshot:
        del context, decision
        self.subset = SubsetSnapshot(
            SUBSET,
            TABLE,
            ConfigRevision(
                _record(SUBSET_AGGREGATE_TYPE, SUBSET, SUBSET_REVISION, "d" * 64),
                command.content,
            ),
        )
        return self.subset

    def get_subset_for_write(self, context: Any, decision: Any, subset_id: UUID) -> SubsetSnapshot:
        del context, decision
        assert subset_id == SUBSET and self.subset is not None
        return self.subset

    def revise_subset(
        self, context: Any, decision: Any, subset_id: UUID, command: Any
    ) -> SubsetSnapshot:
        del context, decision, subset_id, command
        assert self.subset is not None
        return self.subset

    def list_layouts(
        self, context: Any, decision: Any, table_id: UUID
    ) -> tuple[LayoutSnapshot, ...]:
        del context, decision, table_id
        return (self.layout,) if self.layout is not None else ()

    def list_subsets(
        self, context: Any, decision: Any, table_id: UUID
    ) -> tuple[SubsetSnapshot, ...]:
        del context, decision, table_id
        return (self.subset,) if self.subset is not None else ()


def _app(service: _Service) -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.CATALOG_READ)

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.CATALOG_WRITE)

    install_configurable_catalog_api(
        app,
        service=cast(Any, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
        schema_configuration_dependency=security,
    )
    return app


def _request(app: FastAPI, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)

    import asyncio

    return asyncio.run(run())


def test_configurable_catalog_api_creates_table_and_typed_attribute() -> None:
    service = _Service()
    app = _app(service)

    table = _request(
        app,
        "POST",
        "/api/v1/catalog/tables",
        json={
            "classification": "internal",
            "content": {"key": "materials", "name": "Materials"},
            "change_reason": "create configurable material table",
        },
    )
    assert table.status_code == 201
    assert table.headers["etag"] == '"revision:1:sha256:' + "a" * 64 + '"'
    assert table.json()["current_revision"]["content"]["key"] == "materials"

    attribute = _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/attributes",
        json={
            "content": {
                "table_revision_id": str(TABLE_REVISION),
                "key": "youngs_modulus",
                "name": "Young's modulus",
                "data_type": "number",
                "required": True,
                "quantity_semantics": "modulus.elastic.young",
                "normalized_unit": "Pa",
                "minimum_number": 0,
            },
            "change_reason": "add governed modulus attribute",
        },
    )
    assert attribute.status_code == 201
    content = attribute.json()["current_revision"]["content"]
    assert content["data_type"] == "number"
    assert content["normalized_unit"] == "Pa"

    listed = _request(app, "GET", f"/api/v1/catalog/tables/{TABLE}/attributes")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["attribute_definition_id"] == str(ATTRIBUTE)

    exact = _request(
        app,
        "GET",
        f"/api/v1/catalog/attributes/{ATTRIBUTE}/revisions/{ATTRIBUTE_REVISION}",
    )
    assert exact.status_code == 200
    assert exact.json()["id"] == str(ATTRIBUTE_REVISION)
    assert exact.json()["content"]["name"] == "Young's modulus"


def test_configurable_catalog_api_requires_current_revision_etag() -> None:
    service = _Service()
    app = _app(service)
    _request(
        app,
        "POST",
        "/api/v1/catalog/tables",
        json={
            "content": {"key": "tests", "name": "Tests"},
            "change_reason": "create tests table",
        },
    )

    stale = _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/revisions",
        headers={"If-Match": '"revision:1:sha256:' + "f" * 64 + '"'},
        json={
            "content": {"key": "tests", "name": "Laboratory Tests"},
            "change_reason": "rename table",
        },
    )
    assert stale.status_code == 412
    assert stale.json()["code"] == "CMP-CATALOG-0003"


def test_configurable_catalog_api_rejects_invalid_discrete_definition() -> None:
    service = _Service()
    app = _app(service)

    response = _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/attributes",
        json={
            "content": {
                "table_revision_id": str(TABLE_REVISION),
                "key": "temper",
                "name": "Temper",
                "data_type": "discrete",
            },
            "change_reason": "invalid empty discrete attribute",
        },
    )
    assert response.status_code == 422


def test_configurable_catalog_api_creates_revisioned_layout_and_subset() -> None:
    service = _Service()
    app = _app(service)
    _request(
        app,
        "POST",
        "/api/v1/catalog/tables",
        json={
            "content": {"key": "materials", "name": "Materials"},
            "change_reason": "create materials table",
        },
    )
    _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/attributes",
        json={
            "content": {
                "table_revision_id": str(TABLE_REVISION),
                "key": "manufacturer",
                "name": "Manufacturer",
                "data_type": "text",
            },
            "change_reason": "add manufacturer attribute",
        },
    )

    layout = _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/layouts",
        json={
            "table_revision_id": str(TABLE_REVISION),
            "name": "Datasheet",
            "items": [
                {
                    "attribute_definition_id": str(ATTRIBUTE),
                    "attribute_definition_revision_id": str(ATTRIBUTE_REVISION),
                    "section": "General",
                    "ordinal": 0,
                }
            ],
            "change_reason": "create datasheet layout",
        },
    )
    assert layout.status_code == 201
    assert layout.headers["etag"] == '"revision:1:sha256:' + "c" * 64 + '"'
    assert layout.json()["items"][0]["section"] == "General"

    subset = _request(
        app,
        "POST",
        f"/api/v1/catalog/tables/{TABLE}/subsets",
        json={
            "table_revision_id": str(TABLE_REVISION),
            "name": "All records",
            "filter_definition": {},
            "change_reason": "create initial subset",
        },
    )
    assert subset.status_code == 201
    assert subset.headers["etag"] == '"revision:1:sha256:' + "d" * 64 + '"'
    assert subset.json()["filter_definition"] == {}

    stale = _request(
        app,
        "POST",
        f"/api/v1/catalog/layouts/{LAYOUT}/revisions",
        headers={"If-Match": '"revision:1:sha256:' + "f" * 64 + '"'},
        json={
            "table_revision_id": str(TABLE_REVISION),
            "name": "Updated datasheet",
            "items": [],
            "change_reason": "update layout",
        },
    )
    assert stale.status_code == 412


def test_configurable_catalog_api_deletes_only_with_current_revision_etag() -> None:
    service = _Service()
    app = _app(service)
    created = _request(
        app,
        "POST",
        "/api/v1/catalog/tables",
        json={
            "content": {"key": "mistake", "name": "Incorrect draft"},
            "change_reason": "create draft for deletion",
        },
    )

    stale = _request(
        app,
        "DELETE",
        f"/api/v1/catalog/tables/{TABLE}",
        headers={"If-Match": '"revision:1:sha256:' + "f" * 64 + '"'},
    )
    assert stale.status_code == 412
    assert service.table is not None

    deleted = _request(
        app,
        "DELETE",
        f"/api/v1/catalog/tables/{TABLE}",
        headers={"If-Match": created.headers["etag"]},
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert service.deleted == [(TABLE_AGGREGATE_TYPE, TABLE, TABLE_REVISION)]
    assert service.table is None


def test_configurable_catalog_api_maps_atomic_stale_delete_to_precondition_failure() -> None:
    service = _Service()
    app = _app(service)
    created = _request(
        app,
        "POST",
        "/api/v1/catalog/tables",
        json={
            "content": {"key": "racing_draft", "name": "Racing draft"},
            "change_reason": "create a draft for the race check",
        },
    )
    service.delete_block_reason = "stale"

    response = _request(
        app,
        "DELETE",
        f"/api/v1/catalog/tables/{TABLE}",
        headers={"If-Match": created.headers["etag"]},
    )

    assert response.status_code == 412
    assert response.json()["code"] == "CMP-CATALOG-0003"
    assert service.table is not None
