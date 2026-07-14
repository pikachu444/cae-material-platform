"""Typed human acceptance evidence for a reference calibration Candidate.

The selection is intentionally distinct from numerical convergence.  A Candidate may converge
without being acceptable for an IR revision; a human creates an immutable Selection revision with
an explicit reason before promotion is possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cmp.shared.domain.revisions import content_sha256

REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID = (
    "urn:cmp:modeling:reference-calibration-candidate-selection:1.0.0"
)
REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION = "1.0.0"
REFERENCE_CANDIDATE_SELECTION_DECISION = "accepted_for_reference_ir_promotion"


class CandidateSelectionError(Exception):
    """Base error for reference calibration candidate-selection commands."""


class InvalidCandidateSelection(CandidateSelectionError, ValueError):
    """A typed human selection is malformed or would hide an acceptance decision."""


class CandidateSelectionConflict(CandidateSelectionError):
    """A selection's immutable run, candidate, or source IR relation conflicts."""


class CandidateSelectionNotFound(CandidateSelectionError):
    """A requested Selection revision is absent or invisible in the tenant."""


def _nonzero(name: str, value: UUID) -> None:
    if value.int == 0:
        raise InvalidCandidateSelection(f"{name} must be non-zero")


def _text(name: str, value: str, maximum: int) -> None:
    if not value or value != value.strip() or len(value) > maximum or "\x00" in value:
        raise InvalidCandidateSelection(
            f"{name} must be trimmed and contain 1..{maximum} characters"
        )


def _sha256(name: str, value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise InvalidCandidateSelection(f"{name} must be a lowercase SHA-256 hex digest")


@dataclass(frozen=True, slots=True)
class ReferenceCalibrationCandidateSelectionContent:
    """One human decision pinned to an immutable converged Candidate.

    ``selection_label`` belongs to the stable Selection identity and is deliberately omitted from
    the revision canonical payload.  The Revision kernel prevents it from changing on later
    revisions; candidate/reason changes become append-only revision content.
    """

    selection_label: str
    calibration_run_id: UUID
    calibration_candidate_id: UUID
    candidate_sha256: str
    selection_reason: str
    selection_decision: str = REFERENCE_CANDIDATE_SELECTION_DECISION
    non_production: bool = True

    def __post_init__(self) -> None:
        _text("selection_label", self.selection_label, 160)
        _nonzero("calibration_run_id", self.calibration_run_id)
        _nonzero("calibration_candidate_id", self.calibration_candidate_id)
        _sha256("candidate_sha256", self.candidate_sha256)
        _text("selection_reason", self.selection_reason, 2000)
        if self.selection_decision != REFERENCE_CANDIDATE_SELECTION_DECISION:
            raise InvalidCandidateSelection(
                "selection_decision is not supported by the reference slice"
            )
        if not self.non_production:
            raise InvalidCandidateSelection(
                "reference candidate selection must remain non-production"
            )


def reference_calibration_candidate_selection_canonical(
    content: ReferenceCalibrationCandidateSelectionContent,
) -> dict[str, object]:
    """Canonical immutable decision content, excluding stable identity label."""

    return {
        "selection_schema_id": REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
        "selection_schema_version": REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
        "calibration_run_id": str(content.calibration_run_id),
        "calibration_candidate_id": str(content.calibration_candidate_id),
        "candidate_sha256": content.candidate_sha256,
        "selection_reason": content.selection_reason,
        "selection_decision": content.selection_decision,
        "non_production": content.non_production,
    }


REFERENCE_CANDIDATE_SELECTION_SCHEMA_DIGEST = content_sha256(
    {
        "schema_id": REFERENCE_CANDIDATE_SELECTION_SCHEMA_ID,
        "schema_version": REFERENCE_CANDIDATE_SELECTION_SCHEMA_VERSION,
        "fields": {
            "calibration_run_id": "uuid",
            "calibration_candidate_id": "uuid",
            "candidate_sha256": "sha256",
            "selection_reason": "trimmed text",
            "selection_decision": REFERENCE_CANDIDATE_SELECTION_DECISION,
        },
        "non_production": True,
    }
)
