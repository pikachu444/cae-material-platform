"""Pure domain rules for solver-neutral Material Model IR records."""

from .reference_calibration_candidate_selection import (
    REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
    REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
    ReferenceCalibrationCandidateSelectionContent,
)
from .reference_linear_elastic_calibration import (
    REFERENCE_LINEAR_ELASTIC_CALIBRATION_PLAN_KIND,
    REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_ID,
    REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION,
    ReferenceLinearElasticCalibrationPlanContent,
)
from .reference_linear_elasticity import (
    REFERENCE_MODEL_FAMILY_ID,
    REFERENCE_MODEL_SCHEMA_DIGEST,
    REFERENCE_MODEL_SCHEMA_VERSION,
    ReferenceLinearElasticContent,
    reference_linear_elastic_ir,
)

__all__ = [
    "REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID",
    "REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION",
    "REFERENCE_LINEAR_ELASTIC_CALIBRATION_PLAN_KIND",
    "REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_ID",
    "REFERENCE_LINEAR_ELASTIC_CALIBRATION_SCHEMA_VERSION",
    "REFERENCE_MODEL_FAMILY_ID",
    "REFERENCE_MODEL_SCHEMA_DIGEST",
    "REFERENCE_MODEL_SCHEMA_VERSION",
    "ReferenceCalibrationCandidateSelectionContent",
    "ReferenceLinearElasticCalibrationPlanContent",
    "ReferenceLinearElasticContent",
    "reference_linear_elastic_ir",
]
