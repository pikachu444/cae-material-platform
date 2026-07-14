"""Non-production reference Import Run values for the T-11 orchestration slice."""

from __future__ import annotations

from enum import StrEnum

REFERENCE_IMPORT_RUN_KIND = "reference_uniaxial_tensile_csv"
REFERENCE_IMPORT_EXECUTION_MODE = "reference_inline"


class ImportRunStatus(StrEnum):
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
