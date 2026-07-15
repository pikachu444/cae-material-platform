"""Immutable human acceptance of one converged reference Voce Candidate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

REFERENCE_VOCE_SELECTION_SCHEMA_ID = (
    "urn:cmp:modeling:reference-voce-candidate-selection:1.0.0"
)
REFERENCE_VOCE_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_VOCE_SELECTION_DECISION = "accepted_for_tabulated_ir_projection"


class VoceCandidateSelectionError(Exception):
    pass


class InvalidVoceCandidateSelection(VoceCandidateSelectionError, ValueError):
    pass


class VoceCandidateSelectionConflict(VoceCandidateSelectionError):
    pass


class VoceCandidateSelectionNotFound(VoceCandidateSelectionError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceVoceCandidateSelectionContent:
    selection_label: str
    voce_calibration_run_id: UUID
    voce_calibration_candidate_id: UUID
    candidate_sha256: str
    selection_reason: str
    selection_decision: str = REFERENCE_VOCE_SELECTION_DECISION
    non_production: bool = True

    def __post_init__(self) -> None:
        if not self.selection_label or self.selection_label != self.selection_label.strip():
            raise InvalidVoceCandidateSelection("selection_label must be non-empty and trimmed")
        if len(self.selection_label) > 160 or "\x00" in self.selection_label:
            raise InvalidVoceCandidateSelection("selection_label exceeds its typed contract")
        for name, value in (
            ("voce_calibration_run_id", self.voce_calibration_run_id),
            ("voce_calibration_candidate_id", self.voce_calibration_candidate_id),
        ):
            if value.int == 0:
                raise InvalidVoceCandidateSelection(f"{name} must not be the zero UUID")
        if len(self.candidate_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.candidate_sha256
        ):
            raise InvalidVoceCandidateSelection("candidate_sha256 is invalid")
        if not self.selection_reason or self.selection_reason != self.selection_reason.strip():
            raise InvalidVoceCandidateSelection("selection_reason must be non-empty and trimmed")
        if len(self.selection_reason) > 2_000 or "\x00" in self.selection_reason:
            raise InvalidVoceCandidateSelection("selection_reason exceeds its typed contract")
        if self.selection_decision != REFERENCE_VOCE_SELECTION_DECISION or not self.non_production:
            raise InvalidVoceCandidateSelection("selection must retain its reference decision")


def reference_voce_candidate_selection_canonical(
    value: ReferenceVoceCandidateSelectionContent,
) -> dict[str, object]:
    return {
        "selection_label": value.selection_label,
        "voce_calibration_run_id": str(value.voce_calibration_run_id),
        "voce_calibration_candidate_id": str(value.voce_calibration_candidate_id),
        "candidate_sha256": value.candidate_sha256,
        "selection_reason": value.selection_reason,
        "selection_decision": value.selection_decision,
        "non_production": value.non_production,
    }


REFERENCE_VOCE_SELECTION_SCHEMA_DIGEST = content_sha256(
    {
        "schema_id": REFERENCE_VOCE_SELECTION_SCHEMA_ID,
        "schema_version": REFERENCE_VOCE_SELECTION_SCHEMA_VERSION,
        "fields": [
            "selection_label",
            "voce_calibration_run_id",
            "voce_calibration_candidate_id",
            "candidate_sha256",
            "selection_reason",
            "selection_decision",
            "non_production",
        ],
    }
)
