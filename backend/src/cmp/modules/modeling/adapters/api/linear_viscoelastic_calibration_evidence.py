"""Stable HTTP projection for linear-viscoelastic response-residual evidence."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationResponseResidualProjection,
)
from cmp.modules.modeling.domain.linear_viscoelastic_response_residuals import (
    LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_MAX_ROWS,
    LinearViscoelasticResponseChannel,
    LinearViscoelasticResponsePartition,
    LinearViscoelasticResponseResidualRow,
)

type Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class ResponseResidualRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recommendation_id: UUID
    candidate_id: UUID
    candidate_sha256: Sha256
    rule_version: Literal["linear_viscoelastic_bic@1.0.0"]


class ResponseResidualArtifactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: UUID
    sha256: Sha256
    artifact_role: Literal["response-residuals"]
    schema_ref: Literal[
        "urn:cmp:modeling:linear-viscoelastic-calibration-response-residuals:1.0.0"
    ]
    media_type: Literal["application/vnd.apache.parquet"]
    size_bytes: Annotated[int, Field(ge=0)]


class ResponseResidualRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ordinal: Annotated[int, Field(ge=0)]
    channel: LinearViscoelasticResponseChannel
    observed: float
    predicted: float
    residual: float
    partition: LinearViscoelasticResponsePartition

    @classmethod
    def from_domain(
        cls, value: LinearViscoelasticResponseResidualRow
    ) -> ResponseResidualRowResponse:
        return cls(
            ordinal=value.ordinal,
            channel=value.channel,
            observed=value.observed,
            predicted=value.predicted,
            residual=value.residual,
            partition=value.partition,
        )


class ResponseResidualEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: UUID
    plan_revision_id: UUID
    recommendation: ResponseResidualRecommendationResponse
    artifact: ResponseResidualArtifactResponse
    rows: Annotated[
        tuple[ResponseResidualRowResponse, ...],
        Field(min_length=1, max_length=LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_MAX_ROWS),
    ]

    @classmethod
    def from_domain(
        cls, value: CalibrationResponseResidualProjection
    ) -> ResponseResidualEvidenceResponse:
        return cls(
            run_id=value.run_id,
            plan_revision_id=value.plan_revision_id,
            recommendation=ResponseResidualRecommendationResponse.model_validate(
                {
                    "recommendation_id": value.recommendation_id,
                    "candidate_id": value.candidate_id,
                    "candidate_sha256": value.candidate_sha256,
                    "rule_version": value.recommendation_rule_version,
                }
            ),
            artifact=ResponseResidualArtifactResponse.model_validate(
                {
                    "artifact_id": value.artifact.artifact_id,
                    "sha256": value.artifact.sha256,
                    "artifact_role": value.artifact.artifact_role,
                    "schema_ref": value.artifact.schema_ref,
                    "media_type": value.artifact.media_type,
                    "size_bytes": value.artifact.size_bytes,
                }
            ),
            rows=tuple(ResponseResidualRowResponse.from_domain(row) for row in value.rows),
        )


__all__ = ["ResponseResidualEvidenceResponse"]
