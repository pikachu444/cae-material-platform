from __future__ import annotations

import asyncio
import hashlib
import io
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactIntegrityError,
    ArtifactKind,
    ArtifactNotFound,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
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
from cmp.modules.modeling.application.linear_viscoelastic_calibration import (
    CalibrationRunProjection,
    InMemoryLinearViscoelasticCalibrationRepository,
    LinearViscoelasticCalibrationConflict,
    LinearViscoelasticCalibrationNotFound,
    LinearViscoelasticCalibrationService,
)
from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    LINEAR_VISCOELASTIC_BIC_RULE_VERSION,
    LINEAR_VISCOELASTIC_RESPONSE_RESIDUALS_SCHEMA_ID,
    RankStatus,
    RunStatus,
)
from cmp.modules.modeling.domain.linear_viscoelastic_results import (
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
    RankDiagnostic,
)

NOW = datetime(2026, 8, 31, tzinfo=UTC)
ORG = UUID(int=100)
PROJECT = UUID(int=101)
ACTOR = UUID(int=102)
RUN = UUID(int=103)
PLAN = UUID(int=104)
PLAN_REVISION = UUID(int=105)
CANDIDATE = UUID(int=106)
RECOMMENDATION = UUID(int=107)
ARTIFACT = UUID(int=108)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="urn:cmp:test",
        subject=str(ACTOR),
        token_id="linear-viscoelastic-evidence",
        groups=(),
        scopes=("openid",),
        request_id=UUID(int=109),
        trace_id="00-00000000000000000000000000000103-0000000000000103-01",
        authenticated_at=NOW,
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.MODELING_READ,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(Permission.MODELING_READ),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=UUID(int=109),
        trace_id="00-00000000000000000000000000000103-0000000000000103-01",
        decided_at=NOW,
    )


def _candidate() -> CalibrationCandidate:
    return CalibrationCandidate(
        candidate_id=CANDIDATE,
        attempt_ordinal=1,
        term_count=1,
        physical_parameters=(1.0, 2.0, 0.1),
        transformed_parameters=(0.0, 0.69, -2.3),
        rss=0.25,
        bic=1.5,
        calibration_residuals=(-0.5,),
        holdout_residuals=(0.25,),
        rank=RankDiagnostic((1.0,), 1.0, 0.1, 1, RankStatus.FULL_RANK),
        warnings=(),
    )


def _run(
    *,
    status: RunStatus = RunStatus.SUCCEEDED,
    artifact_ids: tuple[UUID, ...] = (ARTIFACT,),
) -> CalibrationRunProjection:
    candidate = _candidate()
    succeeded = status is RunStatus.SUCCEEDED
    result = CalibrationRunResult(
        run_id=RUN,
        plan_revision_id=PLAN_REVISION,
        status=status,
        attempts=(),
        candidates=(candidate,) if succeeded else (),
        recommendation=(
            CalibrationRecommendation(
                RECOMMENDATION,
                candidate.candidate_id,
                candidate.digest,
                LINEAR_VISCOELASTIC_BIC_RULE_VERSION,
            )
            if succeeded
            else None
        ),
        response_residual_artifact_ids=artifact_ids if succeeded else (),
        failure_code=None if succeeded else "CALCULATION_FAILED",
        failure_detail=None if succeeded else "No candidate converged",
        recovery_hint=None if succeeded else "Create a new immutable Plan.",
    )
    return CalibrationRunProjection(
        id=RUN,
        plan_id=PLAN,
        plan_revision_id=PLAN_REVISION,
        plan_sha256="a" * 64,
        classification=DataClassification.INTERNAL,
        job_id=UUID(int=110),
        status=status.value,
        result=result,
        execution_ledger=(),
        idempotency_key="response-evidence-run",
        request_sha256="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
    )


def _parquet_bytes(*, exact: bool = True) -> bytes:
    columns: dict[str, pa.Array] = {
        "ordinal": pa.array([0, 1], type=pa.int64()),
        "channel": pa.array(["relaxation", "relaxation"], type=pa.string()),
        "observed": pa.array([12.0, 10.0], type=pa.float64()),
        "predicted": pa.array([11.5, 10.25], type=pa.float64()),
        "residual": pa.array([-0.5, 0.25], type=pa.float64()),
        "partition": pa.array(["CALIBRATION", "HOLDOUT"], type=pa.string()),
    }
    if not exact:
        columns["unexpected"] = pa.array([0, 0], type=pa.int64())
    stream = io.BytesIO()
    cast(Any, pq.write_table)(pa.table(columns), stream, compression=None)
    return stream.getvalue()


def _record(value: bytes) -> ArtifactRecord:
    digest = hashlib.sha256(value).hexdigest()
    artifact = Artifact(
        id=ARTIFACT,
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        artifact_kind=ArtifactKind.DERIVED,
        artifact_role="response-residuals",
        schema_ref=LINEAR_VISCOELASTIC_RESPONSE_RESIDUALS_SCHEMA_ID,
        media_type="application/vnd.apache.parquet",
        size_bytes=len(value),
        sha256=digest,
        storage_key=content_object_key(
            ORG, PROJECT, DataClassification.INTERNAL, digest
        ),
        encryption_profile="test",
        source_raw_asset_id=None,
        source_pending_id=UUID(int=111),
        created_at=NOW,
        created_by=ACTOR,
    )
    return ArtifactRecord(artifact, IntegrityStatus.VERIFIED, NOW, UUID(int=112))


class _Artifacts:
    def __init__(self, value: bytes, error: Exception | None = None) -> None:
        self.value = value
        self.error = error
        self.calls: list[tuple[UUID, int]] = []

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context.organization_id == ORG
        assert Permission.ARTIFACT_READ.value in decision.database_permissions
        self.calls.append((artifact_id, maximum_bytes))
        if self.error is not None:
            raise self.error
        return _record(self.value), self.value


def _service(
    run: CalibrationRunProjection, artifacts: _Artifacts
) -> LinearViscoelasticCalibrationService:
    repository = InMemoryLinearViscoelasticCalibrationRepository()
    repository.save_run(run)
    return LinearViscoelasticCalibrationService(
        repository=repository,
        artifact_service=cast(ArtifactService, artifacts),
    )


def test_response_evidence_reads_exact_recommended_artifact() -> None:
    value = _parquet_bytes()
    artifacts = _Artifacts(value)
    projection = asyncio.run(
        _service(_run(), artifacts).get_response_residual_evidence(
            _context(), _decision(), RUN
        )
    )

    assert projection.run_id == RUN
    assert projection.plan_revision_id == PLAN_REVISION
    assert projection.recommendation_id == RECOMMENDATION
    assert projection.candidate_id == CANDIDATE
    assert projection.candidate_sha256 == _candidate().digest
    assert projection.artifact.artifact_id == ARTIFACT
    assert projection.artifact.sha256 == hashlib.sha256(value).hexdigest()
    assert [row.partition.value for row in projection.rows] == [
        "CALIBRATION",
        "HOLDOUT",
    ]
    assert artifacts.calls == [(ARTIFACT, 64 * 1024 * 1024)]


@pytest.mark.parametrize(
    ("run", "detail"),
    (
        (_run(status=RunStatus.FAILED), "requires an exact succeeded Run"),
        (_run(artifact_ids=()), "must pin exactly one"),
        (_run(artifact_ids=(ARTIFACT, UUID(int=113))), "must pin exactly one"),
    ),
)
def test_response_evidence_rejects_non_succeeded_or_ambiguous_run(
    run: CalibrationRunProjection,
    detail: str,
) -> None:
    with pytest.raises(LinearViscoelasticCalibrationConflict, match=detail):
        asyncio.run(
            _service(run, _Artifacts(_parquet_bytes())).get_response_residual_evidence(
                _context(), _decision(), RUN
            )
        )


@pytest.mark.parametrize(
    ("artifacts", "detail"),
    (
        (_Artifacts(_parquet_bytes(), ArtifactNotFound("missing")), "Artifact is missing"),
        (
            _Artifacts(_parquet_bytes(), ArtifactIntegrityError("corrupt")),
            "integrity or scope validation",
        ),
        (_Artifacts(_parquet_bytes(exact=False)), "columns are not exact"),
    ),
)
def test_response_evidence_rejects_missing_integrity_or_schema_mismatch(
    artifacts: _Artifacts,
    detail: str,
) -> None:
    with pytest.raises(LinearViscoelasticCalibrationConflict, match=detail):
        asyncio.run(
            _service(_run(), artifacts).get_response_residual_evidence(
                _context(), _decision(), RUN
            )
        )


def test_response_evidence_rejects_recommendation_candidate_digest_mismatch() -> None:
    run = _run()
    assert run.result is not None and run.result.recommendation is not None
    result = replace(
        run.result,
        recommendation=replace(run.result.recommendation, candidate_digest="c" * 64),
    )
    mismatched = replace(run, result=result)

    with pytest.raises(
        LinearViscoelasticCalibrationConflict,
        match="Recommendation differs from its immutable Candidate",
    ):
        asyncio.run(
            _service(mismatched, _Artifacts(_parquet_bytes())).get_response_residual_evidence(
                _context(), _decision(), RUN
            )
        )


def test_response_evidence_rejects_mismatched_authorization_before_artifact_read() -> None:
    artifacts = _Artifacts(_parquet_bytes())
    mismatched = replace(_decision(), project_id=UUID(int=999))

    with pytest.raises(
        LinearViscoelasticCalibrationConflict,
        match="authorization decision does not match request",
    ):
        asyncio.run(
            _service(_run(), artifacts).get_response_residual_evidence(
                _context(), mismatched, RUN
            )
        )
    assert artifacts.calls == []


def test_response_evidence_keeps_hidden_or_missing_run_not_found() -> None:
    service = LinearViscoelasticCalibrationService(
        repository=InMemoryLinearViscoelasticCalibrationRepository(),
        artifact_service=cast(ArtifactService, _Artifacts(_parquet_bytes())),
    )

    with pytest.raises(LinearViscoelasticCalibrationNotFound, match="Run is not visible"):
        asyncio.run(
            service.get_response_residual_evidence(_context(), _decision(), RUN)
        )
