from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from cmp.modules.catalog.adapters.api.configurable import install_configurable_catalog_api
from cmp.modules.catalog.adapters.api.links import install_catalog_link_api
from cmp.modules.catalog.application.configurable import ConfigRevision, TableSnapshot
from cmp.modules.catalog.application.links import (
    LINK_TYPE_AGGREGATE_TYPE,
    RECORD_LINK_AGGREGATE_TYPE,
    CatalogExplorerChildren,
    DomainBindingKind,
    DomainRevisionBinding,
    LinkEndpoint,
    LinkTypeSnapshot,
    RecordLinkSnapshot,
    RecordLinkView,
    WorkflowGraph,
)
from cmp.modules.catalog.application.records import RECORD_AGGREGATE_TYPE, RecordSnapshot
from cmp.modules.catalog.domain.configurable import CatalogTableContent
from cmp.modules.catalog.domain.records import CatalogRecordContent
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

NOW = datetime(2026, 7, 18, 16, 0, tzinfo=UTC)
ORG = UUID("dd000000-0000-4000-8000-000000000001")
PROJECT = UUID("dd000000-0000-4000-8000-000000000002")
ACTOR = UUID("dd000000-0000-4000-8000-000000000003")
MATERIAL_TABLE = UUID("dd000000-0000-4000-8000-000000000004")
MATERIAL_TABLE_REV = UUID("dd000000-0000-4000-8000-000000000005")
TEST_TABLE = UUID("dd000000-0000-4000-8000-000000000006")
TEST_TABLE_REV = UUID("dd000000-0000-4000-8000-000000000007")
MATERIAL = UUID("dd000000-0000-4000-8000-000000000008")
MATERIAL_REV = UUID("dd000000-0000-4000-8000-000000000009")
TEST = UUID("dd000000-0000-4000-8000-000000000010")
TEST_REV = UUID("dd000000-0000-4000-8000-000000000011")
LINK_TYPE = UUID("dd000000-0000-4000-8000-000000000012")
LINK_TYPE_REV = UUID("dd000000-0000-4000-8000-000000000013")
LINK = UUID("dd000000-0000-4000-8000-000000000014")
LINK_REV_1 = UUID("dd000000-0000-4000-8000-000000000015")
LINK_REV_2 = UUID("dd000000-0000-4000-8000-000000000016")
DOMAIN_MATERIAL = UUID("dd000000-0000-4000-8000-000000000017")
DOMAIN_MATERIAL_REV = UUID("dd000000-0000-4000-8000-000000000018")
BINDING = UUID("dd000000-0000-4000-8000-000000000019")


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
        trace_id="00-000000000000000000000000000000dd-00000000000000dd-01",
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
    revision_no: int = 1,
    based_on: UUID | None = None,
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
        self.link_type: LinkTypeSnapshot | None = None
        self.link: RecordLinkSnapshot | None = None
        self.binding: DomainRevisionBinding | None = None
        self.material_endpoint = LinkEndpoint(
            MATERIAL, MATERIAL_REV, 1, MATERIAL_TABLE, "DP780", "dp780"
        )
        self.test_endpoint = LinkEndpoint(TEST, TEST_REV, 1, TEST_TABLE, "Tensile run 1", "t-1")
        self.tables = (
            TableSnapshot(
                MATERIAL_TABLE,
                ConfigRevision(
                    _revision("catalog.configurable_table", MATERIAL_TABLE, MATERIAL_TABLE_REV),
                    CatalogTableContent("materials", "Materials"),
                ),
            ),
            TableSnapshot(
                TEST_TABLE,
                ConfigRevision(
                    _revision("catalog.configurable_table", TEST_TABLE, TEST_TABLE_REV),
                    CatalogTableContent("tests", "Tests"),
                ),
            ),
        )

    def list_tables(self, context: Any, decision: Any) -> tuple[TableSnapshot, ...]:
        del context, decision
        return self.tables

    def explorer_children(
        self, context: Any, decision: Any, table_id: UUID, parent_folder_id: UUID | None
    ) -> CatalogExplorerChildren:
        del context, decision
        assert table_id == MATERIAL_TABLE and parent_folder_id is None
        record = RecordSnapshot(
            MATERIAL,
            MATERIAL_TABLE,
            ConfigRevision(
                _revision(RECORD_AGGREGATE_TYPE, MATERIAL, MATERIAL_REV),
                CatalogRecordContent(MATERIAL_TABLE, MATERIAL_TABLE_REV, "DP780"),
            ),
        )
        return CatalogExplorerChildren(self.tables[0], (), (record,))

    def create_link_type(self, context: Any, decision: Any, command: Any) -> LinkTypeSnapshot:
        del context, decision
        self.link_type = LinkTypeSnapshot(
            LINK_TYPE,
            ConfigRevision(
                _revision(LINK_TYPE_AGGREGATE_TYPE, LINK_TYPE, LINK_TYPE_REV), command.content
            ),
        )
        return self.link_type

    def list_link_types(self, context: Any, decision: Any) -> tuple[LinkTypeSnapshot, ...]:
        del context, decision
        return (self.link_type,) if self.link_type else ()

    def get_link_type_for_write(
        self, context: Any, decision: Any, link_type_id: UUID
    ) -> LinkTypeSnapshot:
        del context, decision
        assert link_type_id == LINK_TYPE and self.link_type is not None
        return self.link_type

    def create_record_link(self, context: Any, decision: Any, command: Any) -> RecordLinkSnapshot:
        del context, decision
        self.link = RecordLinkSnapshot(
            LINK,
            ConfigRevision(
                _revision(RECORD_LINK_AGGREGATE_TYPE, LINK, LINK_REV_1), command.content
            ),
        )
        return self.link

    def get_record_link_for_write(
        self, context: Any, decision: Any, record_link_id: UUID
    ) -> RecordLinkSnapshot:
        del context, decision
        assert record_link_id == LINK and self.link is not None
        return self.link

    def revise_record_link(
        self, context: Any, decision: Any, record_link_id: UUID, command: Any
    ) -> RecordLinkSnapshot:
        del context, decision
        assert record_link_id == LINK
        self.link = RecordLinkSnapshot(
            LINK,
            ConfigRevision(
                _revision(RECORD_LINK_AGGREGATE_TYPE, LINK, LINK_REV_2, 2, LINK_REV_1),
                command.content,
            ),
        )
        return self.link

    def revise_link_type(self, *args: Any, **kwargs: Any) -> LinkTypeSnapshot:
        del args, kwargs
        assert self.link_type is not None
        return self.link_type

    def _view(self) -> RecordLinkView:
        assert self.link is not None and self.link_type is not None
        return RecordLinkView(
            self.link,
            self.link_type.current,
            self.material_endpoint,
            self.test_endpoint,
        )

    def list_record_links(self, *args: Any, **kwargs: Any) -> tuple[RecordLinkView, ...]:
        del args, kwargs
        return (self._view(),) if self.link is not None else ()

    def workflow_graph(self, *args: Any, **kwargs: Any) -> WorkflowGraph:
        del args, kwargs
        material = LinkEndpoint(
            MATERIAL,
            MATERIAL_REV,
            1,
            MATERIAL_TABLE,
            "DP780",
            "dp780",
            self.binding,
        )
        return WorkflowGraph(
            material,
            (material, self.test_endpoint),
            (self._view(),) if self.link is not None else (),
        )

    def bind_domain_revision(
        self,
        context: Any,
        decision: Any,
        record_id: UUID,
        revision_id: UUID,
        command: Any,
    ) -> DomainRevisionBinding:
        del context, decision
        assert record_id == MATERIAL and revision_id == MATERIAL_REV
        self.binding = DomainRevisionBinding(
            BINDING,
            record_id,
            revision_id,
            command.kind,
            command.object_id,
            command.revision_id,
            f"/materials/{command.object_id}?revision_id={command.revision_id}",
        )
        return self.binding

    def get_domain_binding(
        self, context: Any, decision: Any, record_id: UUID, revision_id: UUID
    ) -> DomainRevisionBinding | None:
        del context, decision
        assert record_id == MATERIAL and revision_id == MATERIAL_REV
        return self.binding

    def resolve_domain_binding(
        self,
        context: Any,
        decision: Any,
        kind: DomainBindingKind,
        object_id: UUID,
        revision_id: UUID,
    ) -> DomainRevisionBinding | None:
        del context, decision
        if self.binding is None:
            return None
        if (
            self.binding.kind is kind
            and self.binding.object_id == object_id
            and self.binding.revision_id == revision_id
        ):
            return self.binding
        return None


def _app(service: _Service) -> FastAPI:
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
    install_catalog_link_api(
        app,
        service=cast(Any, service),
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


def _link_type_body() -> dict[str, Any]:
    return {
        "classification": "internal",
        "content": {
            "key": "material_test_evidence",
            "name": "Material test evidence",
            "source_table_id": str(MATERIAL_TABLE),
            "source_table_revision_id": str(MATERIAL_TABLE_REV),
            "target_table_id": str(TEST_TABLE),
            "target_table_revision_id": str(TEST_TABLE_REV),
            "forward_label": "has test evidence",
            "reverse_label": "is test evidence for",
            "source_cardinality": "many",
            "target_cardinality": "many",
            "description": None,
        },
        "change_reason": "create API Link Type",
    }


def _link_body(active: bool = True) -> dict[str, Any]:
    return {
        "classification": "internal",
        "content": {
            "link_type_id": str(LINK_TYPE),
            "link_type_revision_id": str(LINK_TYPE_REV),
            "source_record_id": str(MATERIAL),
            "source_record_revision_id": str(MATERIAL_REV),
            "target_record_id": str(TEST),
            "target_record_revision_id": str(TEST_REV),
            "active": active,
            "note": "exact evidence link",
        },
        "change_reason": "create API Record Link",
    }


@pytest.mark.anyio
async def test_explorer_link_create_reverse_graph_and_deactivation_contract() -> None:
    service = _Service()
    app = _app(service)
    roots = await _request(app, "GET", "/api/v1/catalog/explorer/tables")
    assert roots.status_code == 200
    assert [item["current_revision"]["content"]["name"] for item in roots.json()["items"]] == [
        "Materials",
        "Tests",
    ]
    children = await _request(
        app, "GET", f"/api/v1/catalog/explorer/tables/{MATERIAL_TABLE}/children"
    )
    assert children.status_code == 200
    assert children.json()["records"][0]["current_revision"]["content"]["name"] == "DP780"

    link_type = await _request(app, "POST", "/api/v1/catalog/link-types", json=_link_type_body())
    assert link_type.status_code == 201
    assert link_type.json()["current_revision"]["content"]["reverse_label"] == (
        "is test evidence for"
    )
    created = await _request(app, "POST", "/api/v1/catalog/record-links", json=_link_body())
    assert created.status_code == 201
    assert created.json()["record_link_id"] == str(LINK)

    reverse = await _request(
        app,
        "GET",
        f"/api/v1/catalog/records/{TEST}/links?revision_id={TEST_REV}",
    )
    assert reverse.status_code == 200
    assert reverse.json()["items"][0]["source"]["record_id"] == str(MATERIAL)
    graph = await _request(
        app,
        "GET",
        f"/api/v1/catalog/workflow-explorer/{MATERIAL}/revisions/{MATERIAL_REV}?depth=2",
    )
    assert graph.status_code == 200
    assert {node["name"] for node in graph.json()["nodes"]} == {"DP780", "Tensile run 1"}

    revised_body = _link_body(active=False)
    revised_body.pop("classification")
    revised = await _request(
        app,
        "POST",
        f"/api/v1/catalog/record-links/{LINK}/revisions",
        headers={"If-Match": created.headers["etag"]},
        json=revised_body,
    )
    assert revised.status_code == 201
    assert revised.json()["current_revision"]["revision_no"] == 2
    assert revised.json()["current_revision"]["content"]["active"] is False


@pytest.mark.anyio
async def test_latest_alias_and_missing_exact_revision_are_rejected_by_schema() -> None:
    app = _app(_Service())
    body = _link_body()
    body["content"]["source_record_revision_id"] = "latest"
    response = await _request(app, "POST", "/api/v1/catalog/record-links", json=body)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_record_revision_can_pin_and_open_an_exact_domain_revision() -> None:
    app = _app(_Service())
    path = f"/api/v1/catalog/records/{MATERIAL}/revisions/{MATERIAL_REV}/domain-binding"
    created = await _request(
        app,
        "POST",
        path,
        json={
            "kind": DomainBindingKind.MATERIAL.value,
            "object_id": str(DOMAIN_MATERIAL),
            "revision_id": str(DOMAIN_MATERIAL_REV),
        },
    )
    assert created.status_code == 201
    assert created.json()["workbench_path"] == (
        f"/materials/{DOMAIN_MATERIAL}?revision_id={DOMAIN_MATERIAL_REV}"
    )

    fetched = await _request(app, "GET", path)
    assert fetched.status_code == 200
    assert fetched.json()["revision_id"] == str(DOMAIN_MATERIAL_REV)

    resolved = await _request(
        app,
        "GET",
        "/api/v1/catalog/domain-bindings:resolve",
        params={
            "kind": "material",
            "object_id": str(DOMAIN_MATERIAL),
            "revision_id": str(DOMAIN_MATERIAL_REV),
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["record_id"] == str(MATERIAL)
    missing = await _request(
        app,
        "GET",
        "/api/v1/catalog/domain-bindings:resolve",
        params={
            "kind": "material",
            "object_id": str(DOMAIN_MATERIAL),
            "revision_id": str(uuid4()),
        },
    )
    assert missing.status_code == 200
    assert missing.json() is None

    graph = await _request(
        app,
        "GET",
        f"/api/v1/catalog/workflow-explorer/{MATERIAL}/revisions/{MATERIAL_REV}",
    )
    assert graph.status_code == 200
    assert graph.json()["root"]["domain_binding"]["kind"] == "material"
