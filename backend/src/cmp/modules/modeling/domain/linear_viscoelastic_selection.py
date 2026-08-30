"""Selection acknowledgement, model promotion, and selected-array evidence."""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import numpy as np

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    NORMALIZED_ARRAY_EVIDENCE_RULE_VERSION,
    SELECTED_ARRAY_DIGEST_RULE_VERSION,
    LinearViscoelasticInputError,
    LinearViscoelasticSelectionError,
    RunStatus,
    _sha256,
    _uuid,
)
from cmp.modules.modeling.domain.linear_viscoelastic_policy import (
    LinearViscoelasticCalibrationPlan,
)
from cmp.modules.modeling.domain.linear_viscoelastic_results import (
    CalibrationCandidate,
    CalibrationRecommendation,
    CalibrationRunResult,
)
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_DIGEST_1_4,
    BulkRelaxationStatus,
    PronyTerm,
    ReferenceLinearViscoelasticCalibrationEvidence,
    ReferenceLinearViscoelasticContent,
)
from cmp.shared.domain.revisions import canonical_json_bytes


def selection_acknowledgement(
    *,
    code: str,
    rule_version: str,
    plan_revision_id: UUID,
    run_id: UUID,
    candidate_id: UUID,
    model_revision_id: UUID | None,
    actor: UUID,
    reason: str,
    acknowledged_at: datetime,
) -> dict[str, object]:
    """Build the exact warning acknowledgement envelope required by Selection."""

    for name, value in (
        ("plan_revision_id", plan_revision_id),
        ("run_id", run_id),
        ("candidate_id", candidate_id),
        ("actor", actor),
    ):
        _uuid(value, name)
    if model_revision_id is not None:
        _uuid(model_revision_id, "model_revision_id")
    if not reason or reason != reason.strip():
        raise LinearViscoelasticSelectionError("selection reason is required and must be trimmed")
    if acknowledged_at.tzinfo is None or acknowledged_at.utcoffset() is None:
        raise LinearViscoelasticSelectionError("acknowledgement time must be timezone-aware")
    return {
        "code": code,
        "rule_version": rule_version,
        "plan_revision_id": str(plan_revision_id),
        "run_id": str(run_id),
        "candidate_id": str(candidate_id),
        "model_revision_id": str(model_revision_id) if model_revision_id is not None else None,
        "actor": str(actor),
        "reason": reason,
        "time": acknowledged_at.astimezone(UTC).isoformat(),
    }


def promote_selected_linear_viscoelastic_candidate(
    *,
    candidate: CalibrationCandidate,
    selection: LinearViscoelasticSelection,
    recommendation: CalibrationRecommendation,
    plan: LinearViscoelasticCalibrationPlan,
    run: CalibrationRunResult,
    material_id: UUID,
    material_revision_id: UUID,
    material_state_id: UUID,
    material_state_revision_id: UUID,
    property_set_id: UUID,
    property_set_revision_id: UUID,
    density_kg_per_m3: float,
    poisson_ratio: float,
    reference_temperature_k: float,
) -> ReferenceLinearViscoelasticContent:
    """Promote only an exact engineer Selection into non-production IR 1.4.

    The solver-neutral IR derives ``G0`` from the selected physical candidate and uses
    ``G0 = G_inf + ΣGi`` and ``gi = Gi/G0``.  Bulk relaxation remains explicitly
    ``not_characterized`` with zero ``ki`` terms; no exporter mapping is changed here.
    """

    if (
        selection.candidate_id != candidate.candidate_id
        or selection.candidate_digest != candidate.digest
    ):
        raise LinearViscoelasticSelectionError(
            "promotion candidate does not match immutable Selection"
        )
    if (
        selection.plan_revision_id != plan.plan_revision_id
        or selection.run_id != run.run_id
        or run.plan_revision_id != plan.plan_revision_id
    ):
        raise LinearViscoelasticSelectionError(
            "promotion Plan, Run, and immutable Selection revisions do not match"
        )
    recommended_candidate = next(
        (
            value
            for value in run.candidates
            if value.candidate_id == recommendation.candidate_id
        ),
        None,
    )
    if (
        run.recommendation != recommendation
        or recommended_candidate is None
        or recommendation.candidate_digest != recommended_candidate.digest
    ):
        raise LinearViscoelasticSelectionError(
            "promotion Recommendation does not match the immutable successful Run"
        )
    if run.status is not RunStatus.SUCCEEDED or candidate not in run.candidates:
        raise LinearViscoelasticSelectionError("promotion requires the exact successful Run result")
    if len(candidate.physical_parameters) != 1 + 2 * candidate.term_count:
        raise LinearViscoelasticSelectionError("candidate parameter vector is not complete")
    g_inf = float(candidate.physical_parameters[0])
    moduli = tuple(
        float(item) for item in candidate.physical_parameters[1 : candidate.term_count + 1]
    )
    taus = tuple(float(item) for item in candidate.physical_parameters[1 + candidate.term_count :])
    g0 = g_inf + sum(moduli)
    if not math.isfinite(g0) or g0 <= 0:
        raise LinearViscoelasticSelectionError(
            "selected candidate has no positive instantaneous shear modulus"
        )
    if plan.test_data is None or plan.test_data.sha256 is None:
        raise LinearViscoelasticSelectionError(
            "promotion requires the exact Test Data revision digest"
        )
    if plan.import_profile is None or plan.import_profile.sha256 is None:
        raise LinearViscoelasticSelectionError(
            "promotion requires the exact Import Profile revision digest"
        )
    if plan.canonical_artifact is None or plan.normalized_artifact is None:
        raise LinearViscoelasticSelectionError(
            "promotion requires exact canonical and normalized Artifacts"
        )
    selection_digest = hashlib.sha256(canonical_json_bytes(selection.canonical())).hexdigest()
    recommendation_digest = hashlib.sha256(
        canonical_json_bytes(recommendation.canonical())
    ).hexdigest()
    evidence = ReferenceLinearViscoelasticCalibrationEvidence(
        plan_id=plan.plan_id,
        plan_revision_id=plan.plan_revision_id,
        plan_sha256=plan.digest,
        run_id=run.run_id,
        run_sha256=run.digest,
        candidate_id=candidate.candidate_id,
        candidate_sha256=candidate.digest,
        selection_id=selection.selection_id,
        selection_revision_id=selection.selection_revision_id,
        selection_sha256=selection_digest,
        recommendation_id=recommendation.recommendation_id,
        recommendation_sha256=recommendation_digest,
        canonical_test_data_id=plan.test_data.aggregate_id,
        canonical_test_data_revision_id=plan.test_data.revision_id,
        canonical_test_data_sha256=plan.test_data.sha256,
        canonical_artifact_id=plan.canonical_artifact.artifact_id,
        canonical_artifact_sha256=plan.canonical_artifact.sha256,
        normalized_artifact_id=plan.normalized_artifact.artifact_id,
        normalized_artifact_sha256=plan.normalized_artifact.sha256,
        import_profile_id=plan.import_profile.aggregate_id,
        import_profile_revision_id=plan.import_profile.revision_id,
        import_profile_sha256=plan.import_profile.sha256,
    )
    terms = tuple(
        PronyTerm(g_ratio=modulus / g0, k_ratio=0.0, relaxation_time_s=tau)
        for modulus, tau in zip(moduli, taus, strict=True)
    )
    return ReferenceLinearViscoelasticContent(
        material_id=material_id,
        material_revision_id=material_revision_id,
        material_state_id=material_state_id,
        material_state_revision_id=material_state_revision_id,
        property_set_id=property_set_id,
        property_set_revision_id=property_set_revision_id,
        density_kg_per_m3=density_kg_per_m3,
        youngs_modulus_pa=2 * g0 * (1 + poisson_ratio),
        poisson_ratio=poisson_ratio,
        bulk_relaxation_status=BulkRelaxationStatus.NOT_CHARACTERIZED,
        terms=terms,
        reference_temperature_k=reference_temperature_k,
        calibration_evidence=evidence,
        model_schema_digest=REFERENCE_CALIBRATED_LINEAR_VISCOELASTIC_SCHEMA_DIGEST_1_4,
        non_production=True,
    )


@dataclass(frozen=True, slots=True)
class LinearViscoelasticSelection:
    """Engineer-selected candidate; never aliases or substitutes parameters."""

    selection_id: UUID
    selection_revision_id: UUID
    plan_revision_id: UUID
    run_id: UUID
    candidate_id: UUID
    candidate_digest: str
    reason: str
    warning_acknowledgements: tuple[Mapping[str, object], ...]
    actor: UUID
    created_at: datetime

    def __post_init__(self) -> None:
        for name, value in (
            ("selection_id", self.selection_id),
            ("selection_revision_id", self.selection_revision_id),
            ("plan_revision_id", self.plan_revision_id),
            ("run_id", self.run_id),
            ("candidate_id", self.candidate_id),
            ("actor", self.actor),
        ):
            _uuid(value, name)
        _sha256(self.candidate_digest, "candidate_digest")
        if not self.reason or self.reason != self.reason.strip():
            raise LinearViscoelasticSelectionError("Selection requires a non-empty reason")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise LinearViscoelasticSelectionError("selection created_at must be timezone-aware")
        for acknowledgement in self.warning_acknowledgements:
            required = {
                "code",
                "rule_version",
                "plan_revision_id",
                "run_id",
                "candidate_id",
                "actor",
                "reason",
                "time",
            }
            if not required.issubset(acknowledgement):
                raise LinearViscoelasticSelectionError("warning acknowledgement is incomplete")

    def canonical(self) -> dict[str, object]:
        return {
            "selection_id": str(self.selection_id),
            "selection_revision_id": str(self.selection_revision_id),
            "plan_revision_id": str(self.plan_revision_id),
            "run_id": str(self.run_id),
            "candidate_id": str(self.candidate_id),
            "candidate_digest": self.candidate_digest,
            "reason": self.reason,
            "warning_acknowledgements": [dict(item) for item in self.warning_acknowledgements],
            "actor": str(self.actor),
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }

    def intent_canonical(self) -> dict[str, object]:
        """Canonical engineer intent, excluding server-assigned identity and time."""

        return {
            "plan_revision_id": str(self.plan_revision_id),
            "run_id": str(self.run_id),
            "candidate_id": str(self.candidate_id),
            "candidate_digest": self.candidate_digest,
            "reason": self.reason,
            "warning_acknowledgements": [dict(item) for item in self.warning_acknowledgements],
            "actor": str(self.actor),
        }


def selected_arrays_digest(
    matrix: Sequence[Sequence[float]] | np.ndarray,
    *,
    channels: Sequence[str],
    source_ordinals: Sequence[int] | Mapping[str, Sequence[int]],
) -> str:
    """Digest exact little-endian C-order float64 selected arrays and metadata."""

    values = np.asarray(matrix, dtype="<f8", order="C")
    if values.ndim != 2:
        raise ValueError("selected arrays must be a two-dimensional matrix")
    if isinstance(source_ordinals, Mapping):
        ordinal_document: object = {
            str(key): [int(item) for item in value] for key, value in source_ordinals.items()
        }
    else:
        ordinal_document = [int(item) for item in source_ordinals]
    header = canonical_json_bytes(
        {
            "rule_version": SELECTED_ARRAY_DIGEST_RULE_VERSION,
            "dtype": "ieee754-binary64",
            "byte_order": "little",
            "layout": "C",
            "shape": list(values.shape),
            "channels": list(channels),
            "source_ordinals": ordinal_document,
        }
    )
    payload = values.tobytes(order="C")
    stream = (
        SELECTED_ARRAY_DIGEST_RULE_VERSION.encode("ascii")
        + b"\n"
        + struct.pack(">Q", len(header))
        + header
        + struct.pack(">Q", len(payload))
        + payload
    )
    return hashlib.sha256(stream).hexdigest()


def selected_arrays_digest_bytes(
    matrix: Sequence[Sequence[float]] | np.ndarray,
    *,
    channels: Sequence[str],
    source_ordinals: Sequence[int] | Mapping[str, Sequence[int]],
) -> bytes:
    """Return the exact bytes used by :func:`selected_arrays_digest` for evidence tests."""

    values = np.asarray(matrix, dtype="<f8", order="C")
    if isinstance(source_ordinals, Mapping):
        ordinal_document: object = {
            str(key): [int(item) for item in value] for key, value in source_ordinals.items()
        }
    else:
        ordinal_document = [int(item) for item in source_ordinals]
    header = canonical_json_bytes(
        {
            "rule_version": SELECTED_ARRAY_DIGEST_RULE_VERSION,
            "dtype": "ieee754-binary64",
            "byte_order": "little",
            "layout": "C",
            "shape": list(values.shape),
            "channels": list(channels),
            "source_ordinals": ordinal_document,
        }
    )
    payload = values.tobytes(order="C")
    return (
        SELECTED_ARRAY_DIGEST_RULE_VERSION.encode("ascii")
        + b"\n"
        + struct.pack(">Q", len(header))
        + header
        + struct.pack(">Q", len(payload))
        + payload
    )


def normalized_arrow_float64_to_numpy_evidence(
    table: Any,
    *,
    selected_ordinals: Sequence[int],
    columns: Sequence[str] | None = None,
) -> dict[str, object]:
    """Verify a normalized Arrow table is float64 and record exact NumPy evidence."""

    try:
        import pyarrow as pa
    except ImportError as error:  # pragma: no cover - dependency is required by the platform
        raise LinearViscoelasticInputError("pyarrow is required for normalized evidence") from error
    if not isinstance(table, pa.Table):
        raise LinearViscoelasticInputError("normalized evidence requires a pyarrow.Table")
    names = tuple(columns) if columns is not None else tuple(table.column_names)
    if not names:
        raise LinearViscoelasticInputError("normalized evidence requires at least one column")
    arrays: list[np.ndarray] = []
    for name in names:
        if name not in table.column_names:
            raise LinearViscoelasticInputError(f"normalized Arrow column {name!r} is missing")
        column = table[name]
        if not pa.types.is_float64(column.type):
            raise LinearViscoelasticInputError(
                f"normalized Arrow column {name!r} must be float64",
                code="INPUT_NORMALIZED_ARRAY_NOT_FLOAT64",
            )
        arrays.append(np.asarray(column.to_numpy(zero_copy_only=False), dtype="<f8"))
    matrix = np.column_stack(arrays).astype("<f8", order="C", copy=False)
    float_hex = [[float(value).hex() for value in row] for row in matrix.tolist()]
    payload = matrix.tobytes(order="C")
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "rule_version": NORMALIZED_ARRAY_EVIDENCE_RULE_VERSION,
        "arrow_schema": str(table.schema),
        "columns": list(names),
        "selected_ordinals": [int(item) for item in selected_ordinals],
        "dtype": "float64",
        "shape": list(matrix.shape),
        "order": "C",
        "float_hex": float_hex,
        "digest": digest,
    }


compute_selected_arrays_digest = selected_arrays_digest
