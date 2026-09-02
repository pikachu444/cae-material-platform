from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

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
from cmp.modules.modeling.adapters.api.linear_viscoelastic_calibration import (
    install_linear_viscoelastic_calibration_api,
)
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationResponseResidualArtifactEvidence,
    CalibrationResponseResidualProjection,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
)
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    LinearViscoelasticCalibrationService,
)
from cmp.modules.modeling.domain.linear_viscoelastic_response_residuals import (
    LinearViscoelasticResponseChannel,
    LinearViscoelasticResponsePartition,
    LinearViscoelasticResponseResidualRow,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 31, tzinfo=UTC)
ORG = UUID(int=200)
PROJECT = UUID(int=201)
ACTOR = UUID(int=202)
RUN = UUID(int=203)
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="urn:cmp:test",
    subject=str(ACTOR),
    token_id="linear-viscoelastic-api-evidence",
    groups=(),
    scopes=("openid",),
    request_id=UUID(int=204),
    trace_id="00-00000000000000000000000000000203-0000000000000203-01",
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.MODELING_READ,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.MODELING_READ),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=CONTEXT.trace_id,
    decided_at=NOW,
)


def _projection() -> CalibrationResponseResidualProjection:
    return CalibrationResponseResidualProjection(
        run_id=RUN,
        plan_revision_id=UUID(int=205),
        recommendation_id=UUID(int=206),
        candidate_id=UUID(int=207),
        candidate_sha256="a" * 64,
        recommendation_rule_version="linear_viscoelastic_bic@1.0.0",
        artifact=CalibrationResponseResidualArtifactEvidence(
            artifact_id=UUID(int=208),
            sha256="b" * 64,
            artifact_role="response-residuals",
            schema_ref=(
                "urn:cmp:modeling:linear-viscoelastic-calibration-"
                "response-residuals:1.0.0"
            ),
            media_type="application/vnd.apache.parquet",
            size_bytes=512,
        ),
        rows=(
            LinearViscoelasticResponseResidualRow(
                ordinal=0,
                channel=LinearViscoelasticResponseChannel.RELAXATION,
                observed=12.0,
                predicted=11.5,
                residual=-0.5,
                partition=LinearViscoelasticResponsePartition.CALIBRATION,
            ),
        ),
    )


class _Service:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[UUID] = []

    async def get_response_residual_evidence(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationResponseResidualProjection:
        assert context is CONTEXT
        assert decision is DECISION
        self.calls.append(run_id)
        if self.failure is not None:
            raise self.failure
        return _projection()


def _client(service: _Service) -> TestClient:
    application = FastAPI()

    def security(request: Request) -> SecurityContext:
        request.state.security_context = CONTEXT
        return CONTEXT

    def read(request: Request) -> AuthorizationDecision:
        request.state.authorization_decision = DECISION
        return DECISION

    install_linear_viscoelastic_calibration_api(
        application,
        service=cast(LinearViscoelasticCalibrationService, service),
        security_dependency=security,
        read_dependency=read,
        write_dependency=read,
        execute_dependency=read,
    )
    return TestClient(application)


def test_endpoint_returns_exact_recommendation_and_artifact_evidence() -> None:
    service = _Service()
    response = _client(service).get(
        f"/api/v1/linear-viscoelastic-calibration-runs/{RUN}/response-residuals"
    )

    assert response.status_code == 200, response.json()
    document = response.json()
    assert document["run_id"] == str(RUN)
    assert document["recommendation"]["candidate_id"] == str(UUID(int=207))
    assert document["recommendation"]["candidate_sha256"] == "a" * 64
    assert document["artifact"] == {
        "artifact_id": str(UUID(int=208)),
        "sha256": "b" * 64,
        "artifact_role": "response-residuals",
        "schema_ref": (
            "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
        ),
        "media_type": "application/vnd.apache.parquet",
        "size_bytes": 512,
    }
    assert document["rows"] == [
        {
            "ordinal": 0,
            "channel": "relaxation",
            "observed": 12.0,
            "predicted": 11.5,
            "residual": -0.5,
            "partition": "CALIBRATION",
        }
    ]
    assert service.calls == [RUN]


def test_endpoint_reports_non_succeeded_run_as_conflict() -> None:
    response = _client(
        _Service(
            failure=LinearViscoelasticCalibrationConflict(
                "response-residual evidence requires an exact succeeded Run"
            )
        )
    ).get(
        f"/api/v1/linear-viscoelastic-calibration-runs/{RUN}/response-residuals"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CMP-MODELING-IMMUTABLE_CONFLICT"


def test_endpoint_keeps_hidden_or_missing_run_not_found() -> None:
    response = _client(
        _Service(failure=LinearViscoelasticCalibrationNotFound("Run is not visible"))
    ).get(f"/api/v1/linear-viscoelastic-calibration-runs/{RUN}/response-residuals")

    assert response.status_code == 404
    assert response.json()["code"] == "CMP-MODELING-RESOURCE_NOT_FOUND"
