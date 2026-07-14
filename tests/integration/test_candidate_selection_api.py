from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
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
from cmp.modules.modeling.adapters.api.candidate_selection import install_candidate_selection_api
from cmp.modules.modeling.application.candidate_selection import (
    CalibrationCandidateSelectionSnapshot,
)
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelSnapshot,
    RevisionSnapshot,
)
from cmp.modules.modeling.domain.reference_calibration_candidate_selection import (
    CandidateSelectionConflict,
    ReferenceCalibrationCandidateSelectionContent,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import (
    ReferenceCalibrationEvidence,
    ReferenceLinearElasticContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 20, 10, 0, tzinfo=UTC)
ORG = UUID("fc000000-0000-4000-8000-000000000001")
PROJECT = UUID("fc000000-0000-4000-8000-000000000002")
ACTOR = UUID("fc000000-0000-4000-8000-000000000003")
SELECTION = UUID("fc000000-0000-4000-8000-000000000004")
SELECTION_REVISION = UUID("fc000000-0000-4000-8000-000000000005")
RUN = UUID("fc000000-0000-4000-8000-000000000006")
CANDIDATE = UUID("fc000000-0000-4000-8000-000000000007")
MODEL = UUID("fc000000-0000-4000-8000-000000000008")
MODEL_REVISION = UUID("fc000000-0000-4000-8000-000000000009")
PROMOTED_MODEL_REVISION = UUID("fc000000-0000-4000-8000-00000000000a")
DIAGNOSTICS = UUID("fc000000-0000-4000-8000-00000000000b")
TRACE = "00-000000000000000000000000000000fc-00000000000000fc-01"

CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Material modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test-idp.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)
WRITE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.MODELING_WRITE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.MODELING_WRITE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _record(
    revision_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    *,
    revision_no: int = 1,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id=(
            "urn:cmp:modeling:reference-calibration-candidate-selection:1.0.0"
            if aggregate_id == SELECTION
            else "urn:cmp:modeling:reference-isotropic-linear-elasticity:1.0.0"
        ),
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="API contract fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


class _Service:
    def __init__(self, *, reject_promotion: bool = False) -> None:
        self.reject_promotion = reject_promotion
        self.selection: CalibrationCandidateSelectionSnapshot | None = None

    def create_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, command: Any
    ) -> CalibrationCandidateSelectionSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        content = ReferenceCalibrationCandidateSelectionContent(
            selection_label=command.selection_label,
            calibration_run_id=command.calibration_run_id,
            calibration_candidate_id=command.calibration_candidate_id,
            candidate_sha256="c" * 64,
            selection_reason=command.selection_reason,
        )
        self.selection = CalibrationCandidateSelectionSnapshot(
            SELECTION,
            RevisionSnapshot(
                _record(
                    SELECTION_REVISION,
                    SELECTION,
                    "modeling.calibration_candidate_selection",
                ),
                content,
            ),
        )
        return self.selection

    def get_selection(
        self, context: SecurityContext, decision: AuthorizationDecision, selection_id: UUID
    ) -> CalibrationCandidateSelectionSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        assert selection_id == SELECTION
        assert self.selection is not None
        return self.selection

    def list_selections(
        self, context: SecurityContext, decision: AuthorizationDecision, *, limit: int
    ) -> tuple[CalibrationCandidateSelectionSnapshot, ...]:
        assert context is CONTEXT
        assert decision is WRITE
        assert limit > 0
        return () if self.selection is None else (self.selection,)

    def revise_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: Any,
    ) -> CalibrationCandidateSelectionSnapshot:
        assert selection_id == SELECTION
        return self.create_selection(context, decision, command)

    def promote_selected_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
        command: Any,
    ) -> MaterialModelSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        assert selection_id == SELECTION
        if self.reject_promotion:
            raise CandidateSelectionConflict("source IR is stale")
        evidence = ReferenceCalibrationEvidence(
            calibration_selection_id=SELECTION,
            calibration_selection_revision_id=command.selection_revision_id,
            calibration_run_id=RUN,
            calibration_candidate_id=CANDIDATE,
            calibration_candidate_sha256="c" * 64,
            diagnostics_artifact_id=DIAGNOSTICS,
            diagnostics_sha256="d" * 64,
        )
        content = ReferenceLinearElasticContent(
            material_id=uuid4(),
            material_revision_id=uuid4(),
            material_state_id=uuid4(),
            material_state_revision_id=uuid4(),
            property_set_id=uuid4(),
            property_set_revision_id=uuid4(),
            density_kg_per_m3=7850.0,
            youngs_modulus_pa=205_000_000_000.0,
            poisson_ratio=0.3,
            calibration_evidence=evidence,
        )
        return MaterialModelSnapshot(
            MODEL,
            content.material_state_id,
            RevisionSnapshot(
                _record(
                    PROMOTED_MODEL_REVISION,
                    MODEL,
                    MATERIAL_MODEL_AGGREGATE_TYPE,
                    revision_no=2,
                    based_on_revision_id=MODEL_REVISION,
                ),
                content,
            ),
        )


def _application(*, reject_promotion: bool = False) -> FastAPI:
    application = FastAPI()
    service = _Service(reject_promotion=reject_promotion)

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = WRITE

    def write(request: Request) -> None:
        request.state.authorization_decision = WRITE

    install_candidate_selection_api(
        application,
        service=cast(Any, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return application


def _request(
    application: FastAPI,
    method: str,
    path: str,
    body: object | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def _selection_body() -> dict[str, str]:
    return {
        "classification": "internal",
        "selection_label": "Human accepted reference candidate",
        "calibration_run_id": str(RUN),
        "calibration_candidate_id": str(CANDIDATE),
        "selection_reason": (
            "Human review accepts numerical convergence for reference IR promotion."
        ),
    }


def test_candidate_selection_api_records_human_acceptance_and_promotes_a_new_ir_revision() -> None:
    application = _application()
    selection = _request(
        application,
        "POST",
        "/api/v1/calibration-candidate-selections",
        _selection_body(),
    )

    assert selection.status_code == 201
    assert selection.headers["etag"].startswith('"revision:1:sha256:')
    selection_document = selection.json()
    assert selection_document["current_revision"]["content"]["selection_decision"] == (
        "accepted_for_reference_ir_promotion"
    )
    assert selection_document["current_revision"]["content"]["domain_acceptance_status"] == (
        "accepted_by_human_for_reference_ir_promotion"
    )

    promoted = _request(
        application,
        "POST",
        f"/api/v1/calibration-candidate-selections/{SELECTION}/promote-material-model",
        {
            "selection_revision_id": str(SELECTION_REVISION),
            "expected_material_model_revision_id": str(MODEL_REVISION),
            "change_reason": "Append a reference IR revision with explicit Candidate evidence.",
        },
    )

    assert promoted.status_code == 201
    assert promoted.headers["etag"].startswith('"revision:2:sha256:')
    document = promoted.json()
    evidence = document["material_model"]["current_revision"]["content"]["calibration_evidence"]
    assert evidence["calibration_selection_revision_id"] == str(SELECTION_REVISION)
    assert evidence["calibration_candidate_id"] == str(CANDIDATE)
    assert document["material_model"]["current_revision"]["provenance"][
        "calibration_selection_revision_id"
    ] == str(SELECTION_REVISION)


def test_candidate_selection_api_sanitizes_stale_promotion_conflict() -> None:
    application = _application(reject_promotion=True)
    _request(application, "POST", "/api/v1/calibration-candidate-selections", _selection_body())

    rejected = _request(
        application,
        "POST",
        f"/api/v1/calibration-candidate-selections/{SELECTION}/promote-material-model",
        {
            "selection_revision_id": str(SELECTION_REVISION),
            "expected_material_model_revision_id": str(MODEL_REVISION),
            "change_reason": "Attempt a stale promotion.",
        },
    )

    assert rejected.status_code == 409
    assert rejected.headers["content-type"].startswith("application/problem+json")
    assert rejected.json()["code"] == "CMP-CALIBRATION-0003"
    assert str(MODEL_REVISION) not in rejected.text
