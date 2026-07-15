"""Immutable human selection of one bounded reference Prony Candidate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

REFERENCE_PRONY_SELECTION_SCHEMA_ID = (
    "urn:cmp:modeling:reference-prony-candidate-selection:1.0.0"
)
REFERENCE_PRONY_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_PRONY_SELECTION_DECISION = "accepted_for_linear_prony_ir_revision"


class PronyCandidateSelectionError(Exception):
    pass


class InvalidPronyCandidateSelection(PronyCandidateSelectionError, ValueError):
    pass


class PronyCandidateSelectionConflict(PronyCandidateSelectionError):
    pass


class PronyCandidateSelectionNotFound(PronyCandidateSelectionError):
    pass


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidPronyCandidateSelection(f"{name} must be a non-zero UUID")


@dataclass(frozen=True, slots=True)
class ReferencePronyCandidateSelectionContent:
    selection_label: str
    prony_calibration_run_id: UUID
    prony_calibration_candidate_id: UUID
    candidate_sha256: str
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    selection_reason: str
    selection_decision: str = REFERENCE_PRONY_SELECTION_DECISION
    non_production: bool = True

    def __post_init__(self) -> None:
        if (
            not self.selection_label
            or self.selection_label != self.selection_label.strip()
            or len(self.selection_label) > 160
            or "\x00" in self.selection_label
        ):
            raise InvalidPronyCandidateSelection(
                "selection_label must be trimmed and contain 1..160 characters"
            )
        for name in (
            "prony_calibration_run_id",
            "prony_calibration_candidate_id",
            "baseline_model_id",
            "baseline_model_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        if len(self.candidate_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.candidate_sha256
        ):
            raise InvalidPronyCandidateSelection("candidate_sha256 must be lowercase SHA-256")
        if (
            not self.selection_reason
            or self.selection_reason != self.selection_reason.strip()
            or len(self.selection_reason) > 2_000
            or "\x00" in self.selection_reason
        ):
            raise InvalidPronyCandidateSelection(
                "selection_reason must be trimmed and contain 1..2000 characters"
            )
        if (
            self.selection_decision != REFERENCE_PRONY_SELECTION_DECISION
            or not self.non_production
        ):
            raise InvalidPronyCandidateSelection("reference selection contract was changed")

    def canonical(self) -> dict[str, object]:
        return {
            "selection_label": self.selection_label,
            "prony_calibration_run_id": str(self.prony_calibration_run_id),
            "prony_calibration_candidate_id": str(self.prony_calibration_candidate_id),
            "candidate_sha256": self.candidate_sha256,
            "baseline_model_id": str(self.baseline_model_id),
            "baseline_model_revision_id": str(self.baseline_model_revision_id),
            "selection_reason": self.selection_reason,
            "selection_decision": self.selection_decision,
            "non_production": self.non_production,
        }


REFERENCE_PRONY_SELECTION_SCHEMA_DIGEST = content_sha256(
    {
        "schema_id": REFERENCE_PRONY_SELECTION_SCHEMA_ID,
        "schema_version": REFERENCE_PRONY_SELECTION_SCHEMA_VERSION,
        "decision": REFERENCE_PRONY_SELECTION_DECISION,
        "non_production": True,
    }
)
