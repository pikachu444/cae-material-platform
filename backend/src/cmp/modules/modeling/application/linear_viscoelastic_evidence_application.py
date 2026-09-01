"""Read-only projection of immutable linear-viscoelastic response evidence."""

from __future__ import annotations

from uuid import UUID

from cmp.modules.artifacts.domain.content import (
    ArtifactAccessDenied,
    ArtifactIntegrityError,
    ArtifactNotFound,
    ArtifactStateError,
    InvalidArtifact,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.linear_viscoelastic_application_contracts import (
    CalibrationApplicationState,
    CalibrationResponseResidualArtifactEvidence,
    CalibrationResponseResidualProjection,
    LinearViscoelasticCalibrationConflict,
    _require,
)
from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    LINEAR_VISCOELASTIC_RESPONSE_RESIDUALS_SCHEMA_ID,
    RunStatus,
)
from cmp.modules.modeling.domain.linear_viscoelastic_response_residuals import (
    InvalidLinearViscoelasticResponseResiduals,
    linear_viscoelastic_response_residuals_from_parquet,
)

_RESPONSE_RESIDUAL_ARTIFACT_ROLE = "response-residuals"
_PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
_MAX_RESPONSE_RESIDUAL_BYTES = 64 * 1024 * 1024


class LinearViscoelasticEvidenceApplication:
    """Read exact persisted evidence without evaluating the constitutive model."""

    async def get_response_residual_evidence(
        self: CalibrationApplicationState,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run_id: UUID,
    ) -> CalibrationResponseResidualProjection:
        _require(context, decision, Permission.MODELING_READ)
        run = self._repository.get_run(run_id, context=context, decision=decision)
        result = run.result
        if run.status != RunStatus.SUCCEEDED.value or result is None:
            raise LinearViscoelasticCalibrationConflict(
                "response-residual evidence requires an exact succeeded Run"
            )
        if result.status is not RunStatus.SUCCEEDED:
            raise LinearViscoelasticCalibrationConflict(
                "Run status differs from its immutable calibration result"
            )
        recommendation = result.recommendation
        if recommendation is None:
            raise LinearViscoelasticCalibrationConflict(
                "succeeded Run has no server Recommendation evidence"
            )
        candidates = tuple(
            candidate
            for candidate in result.candidates
            if candidate.candidate_id == recommendation.candidate_id
        )
        if len(candidates) != 1 or candidates[0].digest != recommendation.candidate_digest:
            raise LinearViscoelasticCalibrationConflict(
                "server Recommendation differs from its immutable Candidate"
            )
        artifact_ids = result.response_residual_artifact_ids
        if len(artifact_ids) != 1:
            raise LinearViscoelasticCalibrationConflict(
                "succeeded Run must pin exactly one response-residual Artifact"
            )
        if self._artifact_service is None:
            raise RuntimeError("Artifact service is unavailable")
        artifact_id = artifact_ids[0]
        try:
            record, value = await self._artifact_service.read_verified_bytes(
                context,
                decision,
                artifact_id,
                maximum_bytes=_MAX_RESPONSE_RESIDUAL_BYTES,
            )
        except ArtifactNotFound as error:
            raise LinearViscoelasticCalibrationConflict(
                "Run response-residual Artifact is missing"
            ) from error
        except (
            ArtifactAccessDenied,
            ArtifactIntegrityError,
            ArtifactStateError,
            InvalidArtifact,
        ) as error:
            raise LinearViscoelasticCalibrationConflict(
                "Run response-residual Artifact failed exact integrity or scope validation"
            ) from error

        artifact = record.artifact
        if (
            artifact.id != artifact_id
            or artifact.artifact_role != _RESPONSE_RESIDUAL_ARTIFACT_ROLE
            or artifact.schema_ref != LINEAR_VISCOELASTIC_RESPONSE_RESIDUALS_SCHEMA_ID
            or artifact.media_type != _PARQUET_MEDIA_TYPE
            or artifact.classification is not run.classification
            or (
                run.organization_id is not None
                and artifact.organization_id != run.organization_id
            )
            or (run.project_id is not None and artifact.project_id != run.project_id)
        ):
            raise LinearViscoelasticCalibrationConflict(
                "response-residual Artifact metadata differs from the exact Run contract"
            )
        try:
            rows = linear_viscoelastic_response_residuals_from_parquet(value)
        except InvalidLinearViscoelasticResponseResiduals as error:
            raise LinearViscoelasticCalibrationConflict(str(error)) from error
        return CalibrationResponseResidualProjection(
            run_id=run.id,
            plan_revision_id=run.plan_revision_id,
            recommendation_id=recommendation.recommendation_id,
            candidate_id=recommendation.candidate_id,
            candidate_sha256=recommendation.candidate_digest,
            recommendation_rule_version=recommendation.rule_version,
            artifact=CalibrationResponseResidualArtifactEvidence(
                artifact_id=artifact.id,
                sha256=artifact.sha256,
                artifact_role=artifact.artifact_role,
                schema_ref=artifact.schema_ref,
                media_type=artifact.media_type,
                size_bytes=artifact.size_bytes,
            ),
            rows=rows,
        )


__all__ = ["LinearViscoelasticEvidenceApplication"]
