from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.provenance.adapters.api.provenance import install_provenance_api
from cmp.modules.provenance.application.lineage import ProvenanceLineageService
from cmp.modules.provenance.application.service import (
    ProvenanceService,
    ResolvedActivityCommit,
)
from cmp.modules.provenance.domain.lineage import (
    CompletenessIssue,
    DependencyEdge,
    LineageDirection,
    LineageGraph,
    LineageRelation,
    LineageVertex,
)
from cmp.modules.provenance.domain.model import (
    ActivityCommitResult,
    CompletenessState,
    EntityCompleteness,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceEntity,
    ProvenanceNotFound,
    ProvenanceRecord,
    ProvenanceScope,
)
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
ORG = UUID("8e000000-0000-4000-8000-000000000001")
PROJECT = UUID("8e000000-0000-4000-8000-000000000002")
ACTOR = UUID("8e000000-0000-4000-8000-000000000003")
ENTITY = UUID("8e000000-0000-4000-8000-000000000004")
REFERENCE = UUID("8e000000-0000-4000-8000-000000000005")
ACTIVITY = UUID("8e000000-0000-4000-8000-000000000006")
SOURCE_ENTITY = UUID("8e000000-0000-4000-8000-000000000008")
SOURCE_REFERENCE = UUID("8e000000-0000-4000-8000-000000000009")
TRACE = "00-0000000000000000000000000000008e-000000000000008e-01"
DIGEST = hashlib.sha256(b"provenance-api").hexdigest()

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Provenance Reader", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test-idp.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=UUID("8e000000-0000-4000-8000-000000000007"),
    trace_id=TRACE,
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.PROVENANCE_READ,
    roles=(Role.AUDITOR,),
    database_permissions=database_permissions_for(Permission.PROVENANCE_READ),
    max_classification=DataClassification.RESTRICTED,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record() -> ProvenanceRecord:
    entity = ProvenanceEntity(
        id=ENTITY,
        scope=ProvenanceScope(ORG, PROJECT, DataClassification.INTERNAL),
        entity_type="synthetic.dataset_revision",
        reference=ImmutableEntityReference(
            EntityReferenceKind.REVISION,
            "synthetic.dataset_revision",
            REFERENCE,
            DIGEST,
        ),
        generation_requirement=GenerationRequirement.PRIMARY,
        created_at=NOW,
        recorded_at=NOW,
        recorded_by=ACTOR,
    )
    return ProvenanceRecord(
        entity,
        ACTIVITY,
        EntityCompleteness(CompletenessState.COMPLETE, ()),
    )


def _source_record() -> ProvenanceRecord:
    entity = ProvenanceEntity(
        id=SOURCE_ENTITY,
        scope=ProvenanceScope(ORG, PROJECT, DataClassification.INTERNAL),
        entity_type="artifact.raw_asset",
        reference=ImmutableEntityReference(
            EntityReferenceKind.RAW_ASSET,
            "artifact.raw_asset",
            SOURCE_REFERENCE,
            hashlib.sha256(b"source").hexdigest(),
        ),
        generation_requirement=GenerationRequirement.NONE,
        created_at=NOW,
        recorded_at=NOW,
        recorded_by=ACTOR,
    )
    return ProvenanceRecord(
        entity,
        None,
        EntityCompleteness(CompletenessState.COMPLETE, ()),
    )


class _Repository:
    def commit_activity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        commit: ResolvedActivityCommit,
    ) -> ActivityCommitResult:
        del context, decision, commit
        raise AssertionError("the public API must not expose graph writes")

    def get_entity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        entity_id: UUID,
    ) -> ProvenanceRecord:
        del context, decision
        if entity_id != ENTITY:
            raise ProvenanceNotFound(str(entity_id))
        return _record()

    def find_entity_by_reference(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        reference_type: str,
        reference_id: UUID,
    ) -> ProvenanceRecord:
        del context, decision
        if reference_type != "synthetic.dataset_revision" or reference_id != REFERENCE:
            raise ProvenanceNotFound(f"{reference_type}:{reference_id}")
        return _record()

    def load_lineage_graph(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        root_entity_id: UUID,
        direction: LineageDirection,
        max_depth: int,
        max_nodes: int,
    ) -> LineageGraph:
        del context, decision, max_depth, max_nodes
        if root_entity_id != ENTITY:
            raise ProvenanceNotFound(str(root_entity_id))
        if direction is LineageDirection.DOWNSTREAM:
            return LineageGraph(
                ENTITY,
                direction,
                (LineageVertex(_record(), 0),),
                (),
                False,
            )
        return LineageGraph(
            ENTITY,
            direction,
            (
                LineageVertex(_record(), 0),
                LineageVertex(_source_record(), 1),
            ),
            (
                DependencyEdge(
                    ENTITY,
                    SOURCE_ENTITY,
                    LineageRelation.USAGE_GENERATION,
                    ACTIVITY,
                ),
            ),
            False,
        )

    def activity_completeness_issues(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        activity_ids: tuple[UUID, ...],
    ) -> tuple[CompletenessIssue, ...]:
        del context, decision, activity_ids
        return ()


def _application() -> FastAPI:
    application = FastAPI()
    repository = _Repository()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = DECISION

    install_provenance_api(
        application,
        service=ProvenanceService(repository=repository),
        security_dependency=security,
        read_dependency=read,
        lineage_service=ProvenanceLineageService(repository=repository),
    )
    return application


def _request(path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=_application())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(send())


def test_provenance_entity_contract_exposes_no_database_details() -> None:
    response = _request(f"/api/v1/provenance/entities/{ENTITY}")

    assert response.status_code == 200
    assert response.json()["completeness"] == {"state": "complete", "issues": []}
    assert response.json()["generation_activity_id"] == str(ACTIVITY)
    serialized = response.text
    assert "domain_ref_table" not in serialized
    assert "storage_key" not in serialized


def test_provenance_entity_can_be_resolved_from_typed_reference() -> None:
    response = _request(
        f"/api/v1/provenance/entities/by-reference?reference_type=synthetic.dataset_revision&reference_id={REFERENCE}"
    )

    assert response.status_code == 200
    assert response.json()["entity_id"] == str(ENTITY)
    assert response.json()["reference"]["id"] == str(REFERENCE)


def test_provenance_api_sanitizes_unknown_and_invalid_identifier() -> None:
    missing = _request(f"/api/v1/provenance/entities/{uuid4()}")
    invalid = _request("/api/v1/provenance/entities/not-a-uuid")

    assert missing.status_code == 404
    assert missing.json()["code"] == "CMP-PROVENANCE-0001"
    assert str(ENTITY) not in missing.text
    assert invalid.status_code == 422
    assert invalid.headers["content-type"].startswith("application/problem+json")
    assert invalid.json()["code"] == "CMP-PROVENANCE-0002"


def test_lineage_impact_completeness_and_cursor_contracts() -> None:
    lineage = _request(f"/api/v1/provenance/entities/{ENTITY}/lineage?limit=1&max_depth=10")
    impact = _request(f"/api/v1/provenance/entities/{ENTITY}/impact")
    completeness = _request(f"/api/v1/provenance/entities/{ENTITY}/completeness")

    assert lineage.status_code == 200
    assert lineage.json()["nodes"][0]["path"] == [str(ENTITY)]
    assert lineage.json()["next_cursor"] is not None
    assert impact.status_code == 200
    assert impact.json()["direction"] == "downstream"
    assert completeness.status_code == 200
    assert completeness.json()["eligible"] is True

    invalid_cursor = _request(f"/api/v1/provenance/entities/{ENTITY}/lineage?cursor=not-canonical")
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["code"] == "CMP-PROVENANCE-0002"
