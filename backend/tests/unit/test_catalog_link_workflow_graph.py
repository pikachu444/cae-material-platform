from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.catalog.application.configurable import ConfigRevision
from cmp.modules.catalog.application.links import (
    LINK_TYPE_AGGREGATE_TYPE,
    RECORD_LINK_AGGREGATE_TYPE,
    CatalogLinkService,
    RecordLinkSnapshot,
)
from cmp.modules.catalog.application.records import RecordSearchResult, RecordSnapshot
from cmp.modules.catalog.domain.configurable import (
    CatalogDataCategory,
    CatalogTableContent,
    ConfigurableCatalogNotFound,
)
from cmp.modules.catalog.domain.links import LinkTypeContent, RecordLinkContent
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

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
ORG = UUID("ef000000-0000-4000-8000-000000000001")
PROJECT = UUID("ef000000-0000-4000-8000-000000000002")
ACTOR = UUID("ef000000-0000-4000-8000-000000000003")
TABLE = UUID("ef000000-0000-4000-8000-000000000004")
TABLE_REVISION = UUID("ef000000-0000-4000-8000-000000000005")
ROOT = UUID("ef000000-0000-4000-8000-000000000006")
ROOT_REVISION = UUID("ef000000-0000-4000-8000-000000000007")
CHILD = UUID("ef000000-0000-4000-8000-000000000008")
CHILD_REVISION = UUID("ef000000-0000-4000-8000-000000000009")
LINK_TYPE = UUID("ef000000-0000-4000-8000-00000000000a")
LINK_TYPE_REVISION = UUID("ef000000-0000-4000-8000-00000000000b")
LINK = UUID("ef000000-0000-4000-8000-00000000000c")
LINK_REVISION = UUID("ef000000-0000-4000-8000-00000000000e")
TRACE_ID = "00-000000000000000000000000000000ef-00000000000000ef-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Workflow User", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id="workflow-token",
        groups=(),
        scopes=("openid",),
        request_id=UUID("ef000000-0000-4000-8000-00000000000d"),
        trace_id=TRACE_ID,
        authenticated_at=NOW,
    )


CONTEXT = _context()


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.CATALOG_READ,
        roles=(Role.DATA_STEWARD,),
        database_permissions=database_permissions_for(Permission.CATALOG_READ),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=CONTEXT.trace_id,
        decided_at=NOW,
    )


def _revision(aggregate_type: str, aggregate_id: UUID, revision_id: UUID) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        aggregate_type,
        aggregate_id,
        TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        1,
        None,
        f"urn:cmp:{aggregate_type}:1.0.0",
        "1.0.0",
        "a" * 64,
        NOW,
        ACTOR,
        "workflow graph test",
        CONTEXT.request_id,
        CONTEXT.trace_id,
    )


def _record_revision(
    record_id: UUID, revision_id: UUID, name: str
) -> ConfigRevision[CatalogRecordContent]:
    return ConfigRevision(
        _revision("catalog.configurable_record", record_id, revision_id),
        CatalogRecordContent(TABLE, TABLE_REVISION, name, external_key=name.lower()),
    )


class _Records:
    def __init__(self, published: set[UUID]) -> None:
        self.revisions = {
            ROOT: _record_revision(ROOT, ROOT_REVISION, "Root"),
            CHILD: _record_revision(CHILD, CHILD_REVISION, "Child"),
        }
        self.published = published
        self.revision_calls: Counter[tuple[UUID, UUID]] = Counter()
        self.publication_calls: Counter[UUID] = Counter()

    def get_record_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogRecordContent]:
        del context, decision
        self.revision_calls[(record_id, revision_id)] += 1
        revision = self.revisions[record_id]
        assert revision.record.revision_id == revision_id
        return revision

    def search_records(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        query: Any,
    ) -> RecordSearchResult:
        del context, decision
        assert query.record_id is not None
        self.publication_calls[query.record_id] += 1
        revision = self.revisions[query.record_id]
        if query.record_id not in self.published:
            return RecordSearchResult((), 0, ())
        return RecordSearchResult(
            (RecordSnapshot(query.record_id, TABLE, revision),),
            1,
            (),
        )


class _Schemas:
    def __init__(self) -> None:
        self.table_revision = ConfigRevision(
            _revision("catalog.configurable_table", TABLE, TABLE_REVISION),
            CatalogTableContent(
                "workflow_records",
                "Workflow Records",
                data_category=CatalogDataCategory.TECHNICAL_DATA,
            ),
        )
        self.calls = 0

    def get_table_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        table_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[CatalogTableContent]:
        del context, decision
        assert (table_id, revision_id) == (TABLE, TABLE_REVISION)
        self.calls += 1
        return self.table_revision


class _Links:
    def __init__(self) -> None:
        link_type = LinkTypeContent(
            "workflow_link",
            "Workflow link",
            TABLE,
            TABLE_REVISION,
            TABLE,
            TABLE_REVISION,
            "contains",
            "contained by",
        )
        self.link_type_revision = ConfigRevision(
            _revision(LINK_TYPE_AGGREGATE_TYPE, LINK_TYPE, LINK_TYPE_REVISION),
            link_type,
        )
        self.link = RecordLinkSnapshot(
            LINK,
            ConfigRevision(
                _revision(RECORD_LINK_AGGREGATE_TYPE, LINK, LINK_REVISION),
                RecordLinkContent(
                    LINK_TYPE,
                    LINK_TYPE_REVISION,
                    ROOT,
                    ROOT_REVISION,
                    CHILD,
                    CHILD_REVISION,
                ),
            ),
        )
        self.link_type_calls = 0
        self.list_calls: Counter[UUID] = Counter()

    def list_domain_bindings(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID,
    ) -> tuple[Any, ...]:
        del context, decision, record_id, record_revision_id
        return ()

    def get_link_type_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        link_type_id: UUID,
        revision_id: UUID,
    ) -> ConfigRevision[LinkTypeContent]:
        del context, decision
        assert (link_type_id, revision_id) == (LINK_TYPE, LINK_TYPE_REVISION)
        self.link_type_calls += 1
        return self.link_type_revision

    def list_record_links(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        record_id: UUID,
        record_revision_id: UUID | None,
        include_inactive: bool,
    ) -> tuple[RecordLinkSnapshot, ...]:
        del context, decision, record_revision_id, include_inactive
        self.list_calls[record_id] += 1
        return (self.link,)


def _service(records: _Records, schemas: _Schemas, links: _Links) -> CatalogLinkService:
    return CatalogLinkService(cast(Any, links), cast(Any, schemas), cast(Any, records))


def test_workflow_graph_reuses_exact_endpoint_and_link_type_reads() -> None:
    records = _Records({ROOT, CHILD})
    schemas = _Schemas()
    links = _Links()

    graph = _service(records, schemas, links).workflow_graph(
        CONTEXT,
        _decision(),
        ROOT,
        ROOT_REVISION,
        depth=2,
        published_only=True,
    )

    assert {(node.record_id, node.record_revision_id) for node in graph.nodes} == {
        (ROOT, ROOT_REVISION),
        (CHILD, CHILD_REVISION),
    }
    assert tuple(item.link.id for item in graph.links) == (LINK,)
    assert records.revision_calls == Counter(
        {(ROOT, ROOT_REVISION): 1, (CHILD, CHILD_REVISION): 1}
    )
    assert records.publication_calls == Counter({ROOT: 1, CHILD: 1})
    assert schemas.calls == 2
    assert links.link_type_calls == 1
    assert links.list_calls == Counter({ROOT: 1, CHILD: 1})


def test_workflow_graph_hides_unpublished_linked_endpoint() -> None:
    records = _Records({ROOT})
    schemas = _Schemas()
    links = _Links()

    graph = _service(records, schemas, links).workflow_graph(
        CONTEXT,
        _decision(),
        ROOT,
        ROOT_REVISION,
        depth=2,
        published_only=True,
    )

    assert [(node.record_id, node.record_revision_id) for node in graph.nodes] == [
        (ROOT, ROOT_REVISION)
    ]
    assert graph.links == ()
    assert records.publication_calls == Counter({ROOT: 1, CHILD: 1})


def test_workflow_graph_rejects_unpublished_root() -> None:
    records = _Records(set())
    schemas = _Schemas()
    links = _Links()

    with pytest.raises(ConfigurableCatalogNotFound, match="not published"):
        _service(records, schemas, links).workflow_graph(
            CONTEXT,
            _decision(),
            ROOT,
            ROOT_REVISION,
            depth=2,
            published_only=True,
        )
