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
from cmp.modules.modeling.adapters.api.prony_candidate_promotion import (
    install_prony_candidate_promotion_api,
)
from cmp.modules.modeling.application.linear_viscoelasticity import (
    LinearViscoelasticModelSnapshot,
)
from cmp.modules.modeling.application.prony_candidate_promotion import (
    CreatePronyCandidateSelection,
    PromoteSelectedPronyCandidate,
    PronyCandidatePromotionService,
    PronyCandidateSelectionSnapshot,
)
from cmp.modules.modeling.application.service import RevisionSnapshot
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticContent,
    ReferencePronyPromotionEvidence,
)
from cmp.modules.modeling.domain.reference_prony_candidate_selection import (
    ReferencePronyCandidateSelectionContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 16, tzinfo=UTC)
IDS = tuple(UUID(int=value) for value in range(1, 30))
ORG, PROJECT, ACTOR, SELECTION, SELECTION_REVISION, RUN, CANDIDATE = IDS[:7]
MODEL, BASELINE_REVISION, PROMOTED_REVISION, MATERIAL, MATERIAL_REVISION = IDS[7:12]
STATE, STATE_REVISION, PROPERTIES, PROPERTIES_REVISION, DIAGNOSTICS = IDS[12:17]
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


def _record(revision_id: UUID, aggregate_id: UUID, revision_no: int) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type="modeling.fixture",
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=revision_no,
        based_on_revision_id=BASELINE_REVISION if revision_no == 2 else None,
        schema_id="urn:cmp:test:fixture",
        schema_version="1.1.0" if revision_no == 2 else "1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


SELECTION_CONTENT = ReferencePronyCandidateSelectionContent(
    selection_label="Reviewed Candidate 1",
    prony_calibration_run_id=RUN,
    prony_calibration_candidate_id=CANDIDATE,
    candidate_sha256="b" * 64,
    baseline_model_id=MODEL,
    baseline_model_revision_id=BASELINE_REVISION,
    selection_reason="Reviewed residuals and bound warnings.",
)
SELECTION_SNAPSHOT = PronyCandidateSelectionSnapshot(
    SELECTION,
    RevisionSnapshot(_record(SELECTION_REVISION, SELECTION, 1), SELECTION_CONTENT),
)
BASE_CONTENT = ReferenceLinearViscoelasticContent(
    material_id=MATERIAL,
    material_revision_id=MATERIAL_REVISION,
    material_state_id=STATE,
    material_state_revision_id=STATE_REVISION,
    property_set_id=PROPERTIES,
    property_set_revision_id=PROPERTIES_REVISION,
    density_kg_per_m3=1200.0,
    youngs_modulus_pa=3e9,
    poisson_ratio=0.35,
    bulk_relaxation_status=BulkRelaxationStatus.NOT_CHARACTERIZED,
    terms=(PronyTerm(0.2, 0.0, 0.1),),
)
PROMOTED = LinearViscoelasticModelSnapshot(
    MODEL,
    STATE,
    RevisionSnapshot(
        _record(PROMOTED_REVISION, MODEL, 2),
        replace(
            BASE_CONTENT,
            terms=(PronyTerm(0.25, 0.0, 0.2), PronyTerm(0.3, 0.0, 20.0)),
            prony_promotion_evidence=ReferencePronyPromotionEvidence(
                SELECTION,
                SELECTION_REVISION,
                RUN,
                CANDIDATE,
                "b" * 64,
                DIAGNOSTICS,
                "c" * 64,
            ),
        ),
    ),
)


class _Service:
    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreatePronyCandidateSelection,
    ) -> PronyCandidateSelectionSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert command.calibration_candidate_id == CANDIDATE
        return SELECTION_SNAPSHOT

    def get_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, selection_id: UUID
    ) -> PronyCandidateSelectionSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_READ
        assert selection_id == SELECTION
        return SELECTION_SNAPSHOT

    def promote(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: PromoteSelectedPronyCandidate,
    ) -> LinearViscoelasticModelSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert selection_id == SELECTION
        assert command.selection_revision_id == SELECTION_REVISION
        return PROMOTED


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_READ)

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_WRITE)

    install_prony_candidate_promotion_api(
        app,
        service=cast(PronyCandidatePromotionService, _Service()),
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
            "/api/v1/prony-candidate-selections",
            json={
                "classification": "internal",
                "selection_label": "Reviewed Candidate 1",
                "calibration_run_id": str(RUN),
                "calibration_candidate_id": str(CANDIDATE),
                "selection_reason": "Reviewed residuals and bound warnings.",
            },
        )
        assert created.status_code == 201
        assert created.json()["current_revision"]["content"]["candidate_sha256"] == (
            "sha256:" + "b" * 64
        )
        promoted = await client.post(
            f"/api/v1/prony-candidate-selections/{SELECTION}/promotions",
            json={
                "selection_revision_id": str(SELECTION_REVISION),
                "change_reason": "Promote reviewed Candidate.",
            },
        )
        assert promoted.status_code == 201
        body = promoted.json()
        assert body["material_model_id"] == str(MODEL)
        assert body["current_revision"]["revision_no"] == 2
        assert body["current_revision"]["content"]["model_schema_version"] == "1.1.0"
        assert body["current_revision"]["content"]["prony_promotion_evidence"][
            "selection_revision_id"
        ] == str(SELECTION_REVISION)


def test_human_selection_and_promotion_api_contract() -> None:
    asyncio.run(_exercise())
