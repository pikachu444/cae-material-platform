from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.api.ogden_candidate_promotion import (
    install_ogden_candidate_promotion_api,
)
from cmp.modules.modeling.application.ogden_candidate_promotion import (
    CreateOgdenCandidateSelection,
    OgdenCandidatePromotionService,
    OgdenCandidateSelectionSnapshot,
    PromoteSelectedOgdenCandidate,
)
from cmp.modules.modeling.application.ogden_prony import OgdenPronyModelSnapshot
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_ogden_candidate_selection import (
    ReferenceOgdenCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_ogden_prony import (
    ReferenceOgdenPromotionEvidence,
    ReferenceOgdenPronyContent,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 7, 16, tzinfo=UTC)
IDS = tuple(UUID(int=value) for value in range(1, 24))
(
    ORG,
    PROJECT,
    ACTOR,
    SELECTION,
    SELECTION_REVISION,
    RUN,
    CANDIDATE,
    MODEL,
    BASELINE_REVISION,
    PROMOTED_REVISION,
    MATERIAL,
    MATERIAL_REVISION,
    STATE,
    STATE_REVISION,
    PROPERTIES,
    PROPERTIES_REVISION,
    DIAGNOSTICS,
) = IDS[:17]
TRACE = "00-000000000000000000000000000000c1-00000000000000c1-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://idp.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


def _record(
    revision_id: UUID,
    aggregate_id: UUID,
    revision_no: int,
    content_hash: str,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id,
        "modeling.fixture",
        aggregate_id,
        TenantScope(ORG, PROJECT, "internal"),
        revision_no,
        BASELINE_REVISION if revision_no == 2 else None,
        "urn:cmp:test:fixture",
        "1.1.0" if revision_no == 2 else "1.0.0",
        content_hash,
        NOW,
        ACTOR,
        "fixture",
        CONTEXT.request_id,
        TRACE,
    )


SELECTION_CONTENT = ReferenceOgdenCandidateSelectionContent(
    "Reviewed Ogden Candidate",
    RUN,
    CANDIDATE,
    "b" * 64,
    DIAGNOSTICS,
    "c" * 64,
    MODEL,
    BASELINE_REVISION,
    "Reviewed residual, convergence, bounds, and uncertainty evidence.",
)
SELECTION_SNAPSHOT = OgdenCandidateSelectionSnapshot(
    SELECTION,
    RevisionSnapshot(
        _record(SELECTION_REVISION, SELECTION, 1, "d" * 64), SELECTION_CONTENT
    ),
)
BASE_CONTENT = ReferenceOgdenPronyContent(
    MATERIAL,
    MATERIAL_REVISION,
    STATE,
    STATE_REVISION,
    PROPERTIES,
    PROPERTIES_REVISION,
    1100.0,
    3.0e6,
    0.49,
    ReferenceOgdenTerm(1.2e6, 2.4),
    (ReferenceShearPronyTerm(0.2, 1.0),),
)
BASELINE = OgdenPronyModelSnapshot(
    MODEL,
    STATE,
    RevisionSnapshot(_record(BASELINE_REVISION, MODEL, 1, "a" * 64), BASE_CONTENT),
)
PROMOTED = OgdenPronyModelSnapshot(
    MODEL,
    STATE,
    RevisionSnapshot(
        _record(PROMOTED_REVISION, MODEL, 2, "e" * 64),
        replace(
            BASE_CONTENT,
            ogden_term=ReferenceOgdenTerm(2.0e6, 2.0),
            promotion_evidence=ReferenceOgdenPromotionEvidence(
                SELECTION,
                SELECTION_REVISION,
                RUN,
                CANDIDATE,
                "b" * 64,
                DIAGNOSTICS,
                "c" * 64,
                BASELINE_REVISION,
            ),
        ),
    ),
)


class _Service:
    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateOgdenCandidateSelection,
    ) -> OgdenCandidateSelectionSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert command.calibration_candidate_id == CANDIDATE
        return SELECTION_SNAPSHOT

    def get_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, selection_id: UUID
    ) -> OgdenCandidateSelectionSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_READ
        assert selection_id == SELECTION
        return SELECTION_SNAPSHOT

    def get_current_model_for_promotion(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        selection_revision_id: UUID,
    ) -> OgdenPronyModelSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert selection_id == SELECTION and selection_revision_id == SELECTION_REVISION
        return BASELINE

    def promote(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: PromoteSelectedOgdenCandidate,
    ) -> OgdenPronyModelSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert selection_id == SELECTION
        assert command.expected_current_model_revision_id == BASELINE_REVISION
        return PROMOTED


def _app(service: object | None = None) -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_READ)

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_WRITE)

    install_ogden_candidate_promotion_api(
        app,
        service=cast(OgdenCandidatePromotionService, service or _Service()),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return app


async def _exercise() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        created = await client.post(
            "/api/v1/ogden-candidate-selections",
            json={
                "classification": "internal",
                "selection_label": "Reviewed Ogden Candidate",
                "calibration_run_id": str(RUN),
                "calibration_candidate_id": str(CANDIDATE),
                "selection_reason": (
                    "Reviewed residual, convergence, bounds, and uncertainty evidence."
                ),
            },
        )
        assert created.status_code == 201
        assert created.json()["current_revision"]["content"]["diagnostics_sha256"] == (
            "sha256:" + "c" * 64
        )
        stale = await client.post(
            f"/api/v1/ogden-candidate-selections/{SELECTION}/promotions",
            headers={"If-Match": f'"revision:1:sha256:{"0" * 64}"'},
            json={
                "selection_revision_id": str(SELECTION_REVISION),
                "change_reason": "Promote reviewed Candidate.",
            },
        )
        assert stale.status_code == 412
        assert stale.headers["etag"] == f'"revision:1:sha256:{"a" * 64}"'
        promoted = await client.post(
            f"/api/v1/ogden-candidate-selections/{SELECTION}/promotions",
            headers={"If-Match": f'"revision:1:sha256:{"a" * 64}"'},
            json={
                "selection_revision_id": str(SELECTION_REVISION),
                "change_reason": "Promote reviewed Candidate.",
            },
        )
        assert promoted.status_code == 201
        body = promoted.json()
        assert body["material_model_id"] == str(MODEL)
        assert body["current_revision"]["revision_no"] == 2
        assert body["current_revision"]["content"]["promotion_evidence"][
            "promoted_from_model_revision_id"
        ] == str(BASELINE_REVISION)


def test_iterative_ogden_selection_and_promotion_api_contract() -> None:
    asyncio.run(_exercise())


class _CandidateAlreadyUsedService(_Service):
    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateOgdenCandidateSelection,
    ) -> OgdenCandidateSelectionSnapshot:
        raise IntegrityError("insert selection", {}, Exception("candidate already used"))


async def _exercise_candidate_reuse_conflict() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(_CandidateAlreadyUsedService())),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ogden-candidate-selections",
            json={
                "classification": "internal",
                "selection_label": "Reused Ogden Candidate",
                "calibration_run_id": str(RUN),
                "calibration_candidate_id": str(CANDIDATE),
                "selection_reason": "Try to reuse an already governed Candidate.",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The Candidate or Selection is already used by a promotion."
    )


def test_reused_ogden_candidate_is_a_conflict_not_service_unavailable() -> None:
    asyncio.run(_exercise_candidate_reuse_conflict())
