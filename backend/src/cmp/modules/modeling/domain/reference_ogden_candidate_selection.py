"""Immutable human selection of one governed Ogden calibration Candidate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

REFERENCE_OGDEN_SELECTION_SCHEMA_ID = (
    "urn:cmp:modeling:reference-ogden-candidate-selection:1.0.0"
)
REFERENCE_OGDEN_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_OGDEN_SELECTION_DECISION = "accepted_for_ogden_prony_ir_revision"


class OgdenCandidateSelectionError(Exception):
    pass


class InvalidOgdenCandidateSelection(OgdenCandidateSelectionError, ValueError):
    pass


class OgdenCandidateSelectionConflict(OgdenCandidateSelectionError):
    pass


class OgdenCandidateSelectionNotFound(OgdenCandidateSelectionError):
    pass


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidOgdenCandidateSelection(f"{name} must be a non-zero UUID")


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise InvalidOgdenCandidateSelection(f"{name} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ReferenceOgdenCandidateSelectionContent:
    selection_label: str
    ogden_calibration_run_id: UUID
    ogden_calibration_candidate_id: UUID
    candidate_sha256: str
    diagnostics_artifact_id: UUID
    diagnostics_sha256: str
    baseline_model_id: UUID
    baseline_model_revision_id: UUID
    selection_reason: str
    selection_decision: str = REFERENCE_OGDEN_SELECTION_DECISION
    non_production: bool = True

    def __post_init__(self) -> None:
        if (
            not self.selection_label
            or self.selection_label != self.selection_label.strip()
            or len(self.selection_label) > 160
            or "\x00" in self.selection_label
        ):
            raise InvalidOgdenCandidateSelection(
                "selection_label must be trimmed and contain 1..160 characters"
            )
        for name in (
            "ogden_calibration_run_id",
            "ogden_calibration_candidate_id",
            "diagnostics_artifact_id",
            "baseline_model_id",
            "baseline_model_revision_id",
        ):
            _nonzero(name, getattr(self, name))
        _sha256("candidate_sha256", self.candidate_sha256)
        _sha256("diagnostics_sha256", self.diagnostics_sha256)
        if (
            not self.selection_reason
            or self.selection_reason != self.selection_reason.strip()
            or len(self.selection_reason) > 2_000
            or "\x00" in self.selection_reason
        ):
            raise InvalidOgdenCandidateSelection(
                "selection_reason must be trimmed and contain 1..2000 characters"
            )
        if (
            self.selection_decision != REFERENCE_OGDEN_SELECTION_DECISION
            or not self.non_production
        ):
            raise InvalidOgdenCandidateSelection("reference selection contract was changed")

    def canonical(self) -> dict[str, object]:
        return {
            "selection_label": self.selection_label,
            "ogden_calibration_run_id": str(self.ogden_calibration_run_id),
            "ogden_calibration_candidate_id": str(self.ogden_calibration_candidate_id),
            "candidate_sha256": self.candidate_sha256,
            "diagnostics_artifact_id": str(self.diagnostics_artifact_id),
            "diagnostics_sha256": self.diagnostics_sha256,
            "baseline_model_id": str(self.baseline_model_id),
            "baseline_model_revision_id": str(self.baseline_model_revision_id),
            "selection_reason": self.selection_reason,
            "selection_decision": self.selection_decision,
            "non_production": self.non_production,
        }


REFERENCE_OGDEN_SELECTION_SCHEMA_DIGEST = content_sha256(
    {
        "schema_id": REFERENCE_OGDEN_SELECTION_SCHEMA_ID,
        "schema_version": REFERENCE_OGDEN_SELECTION_SCHEMA_VERSION,
        "decision": REFERENCE_OGDEN_SELECTION_DECISION,
        "diagnostics_are_pinned": True,
        "non_production": True,
    }
)
