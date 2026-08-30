"""Governed input semantics and immutable observations for linear-viscoelastic calibration.

The types in this module describe exact source pins, channel conventions, point partitions, and
input validation. They do not perform numerical fitting or persistence.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import pairwise
from typing import Any, Self
from uuid import UUID

from cmp.modules.modeling.domain.linear_viscoelastic_contracts import (
    DataAvailability,
    LinearViscoelasticChannel,
    LinearViscoelasticInputError,
    PointPartition,
    _as_float,
    _decimal,
    _positive,
    _sha256,
    _status,
    _uuid,
)


@dataclass(frozen=True, slots=True)
class ArtifactPin:
    """An exact immutable Artifact identity and digest."""

    artifact_id: UUID
    sha256: str
    media_type: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.artifact_id, "artifact_id")
        _sha256(self.sha256, "artifact sha256")
        if self.media_type is not None and (
            not self.media_type or self.media_type != self.media_type.strip()
        ):
            raise LinearViscoelasticInputError("artifact media_type must be trimmed")

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {"artifact_id": str(self.artifact_id), "sha256": self.sha256}
        if self.media_type is not None:
            result["media_type"] = self.media_type
        return result


@dataclass(frozen=True, slots=True)
class ExactRevisionPin:
    """A stable aggregate plus one exact immutable revision."""

    aggregate_id: UUID
    revision_id: UUID
    sha256: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.aggregate_id, "aggregate_id")
        _uuid(self.revision_id, "revision_id")
        if self.sha256 is not None:
            _sha256(self.sha256, "revision sha256")

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": str(self.aggregate_id),
            "revision_id": str(self.revision_id),
        }
        if self.sha256 is not None:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True, slots=True)
class RelaxationObservation:
    """One governed shear-relaxation modulus row."""

    ordinal: int
    time_s: Decimal | float
    modulus_pa: Decimal | float
    partition: PointPartition = PointPartition.CALIBRATION
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise LinearViscoelasticInputError("source ordinal must be non-negative")
        _as_float(self.time_s, "time_s")
        modulus = _as_float(self.modulus_pa, "modulus_pa")
        if modulus <= 0:
            raise LinearViscoelasticInputError(
                "relaxation modulus must be positive",
                code="INPUT_NONPOSITIVE_MODULUS",
            )
        if self.partition is PointPartition.EXCLUDED and not self.exclusion_reason:
            raise LinearViscoelasticInputError(
                "excluded rows require an exclusion reason", code="INPUT_EXCLUSION_REASON_REQUIRED"
            )
        if self.partition is not PointPartition.EXCLUDED and self.exclusion_reason is not None:
            raise LinearViscoelasticInputError("only excluded rows may have an exclusion reason")

    @property
    def shear_modulus_pa(self) -> Decimal | float:
        return self.modulus_pa

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "time_s": str(_decimal(self.time_s, "time_s")),
            "modulus_pa": str(_decimal(self.modulus_pa, "modulus_pa")),
            "partition": self.partition.value,
            "exclusion_reason": self.exclusion_reason,
        }


RelaxationPoint = RelaxationObservation


@dataclass(frozen=True, slots=True)
class DmaObservation:
    """One governed isothermal shear DMA storage/loss row."""

    ordinal: int
    frequency_hz: Decimal | float
    temperature_k: Decimal | float
    storage_modulus_pa: Decimal | float
    loss_modulus_pa: Decimal | float
    partition: PointPartition = PointPartition.CALIBRATION
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise LinearViscoelasticInputError("source ordinal must be non-negative")
        _positive(self.frequency_hz, "frequency_hz")
        _positive(self.temperature_k, "temperature_k")
        _positive(self.storage_modulus_pa, "storage_modulus_pa")
        loss = _as_float(self.loss_modulus_pa, "loss_modulus_pa")
        if loss < 0:
            raise LinearViscoelasticInputError(
                "loss modulus must be non-negative", code="INPUT_NEGATIVE_LOSS_MODULUS"
            )
        if self.partition is PointPartition.EXCLUDED and not self.exclusion_reason:
            raise LinearViscoelasticInputError(
                "excluded rows require an exclusion reason", code="INPUT_EXCLUSION_REASON_REQUIRED"
            )
        if self.partition is not PointPartition.EXCLUDED and self.exclusion_reason is not None:
            raise LinearViscoelasticInputError("only excluded rows may have an exclusion reason")

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "frequency_hz": str(_decimal(self.frequency_hz, "frequency_hz")),
            "temperature_k": str(_decimal(self.temperature_k, "temperature_k")),
            "storage_modulus_pa": str(_decimal(self.storage_modulus_pa, "storage_modulus_pa")),
            "loss_modulus_pa": str(_decimal(self.loss_modulus_pa, "loss_modulus_pa")),
            "partition": self.partition.value,
            "exclusion_reason": self.exclusion_reason,
        }


DmaPoint = DmaObservation


@dataclass(frozen=True, slots=True)
class ChannelAvailability:
    ramp: DataAvailability = DataAvailability.NOT_PROVIDED
    sweep: DataAvailability = DataAvailability.NOT_PROVIDED
    preconditioning: DataAvailability = DataAvailability.NOT_PROVIDED
    linear_range: DataAvailability = DataAvailability.NOT_PROVIDED

    def __post_init__(self) -> None:
        for name in ("ramp", "sweep", "preconditioning", "linear_range"):
            object.__setattr__(self, name, _status(getattr(self, name), name))

    def canonical(self) -> dict[str, str]:
        return {
            name: getattr(self, name).value
            for name in ("ramp", "sweep", "preconditioning", "linear_range")
        }


@dataclass(frozen=True, slots=True)
class PointDisposition:
    """One explicit source-row decision; source Test Data bytes are never edited."""

    ordinal: int
    partition: PointPartition
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise LinearViscoelasticInputError("source ordinal must be non-negative")
        if self.partition is PointPartition.EXCLUDED:
            if (
                self.exclusion_reason is None
                or self.exclusion_reason != self.exclusion_reason.strip()
                or not self.exclusion_reason
                or len(self.exclusion_reason) > 500
                or "\x00" in self.exclusion_reason
            ):
                raise LinearViscoelasticInputError(
                    "excluded source rows require a 1..500 character reason",
                    code="INPUT_EXCLUSION_REASON_REQUIRED",
                )
        elif self.exclusion_reason is not None:
            raise LinearViscoelasticInputError(
                "only excluded source rows may carry an exclusion reason"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "partition": self.partition.value,
            "exclusion_reason": self.exclusion_reason,
        }


@dataclass(frozen=True, slots=True)
class InputChannelSemantics:
    """Server-resolved quantity and unit meaning for one active governed channel."""

    key: str
    quantity_semantics: str
    axis_role: str
    original_unit_string: str
    normalized_unit: str

    def __post_init__(self) -> None:
        for name in (
            "key",
            "quantity_semantics",
            "axis_role",
            "original_unit_string",
            "normalized_unit",
        ):
            value = getattr(self, name)
            if not value or value != value.strip() or len(value) > 255 or "\x00" in value:
                raise LinearViscoelasticInputError(f"{name} must be 1..255 trimmed characters")
        if self.axis_role not in {"independent", "dependent"}:
            raise LinearViscoelasticInputError(
                "input channel axis_role must be independent or dependent"
            )

    def canonical(self) -> dict[str, str]:
        return {
            "key": self.key,
            "quantity_semantics": self.quantity_semantics,
            "axis_role": self.axis_role,
            "original_unit_string": self.original_unit_string,
            "normalized_unit": self.normalized_unit,
        }


@dataclass(frozen=True, slots=True)
class GovernedViscoelasticInputSemantics:
    """Exact direct-Test-Data interpretation serialized into every production Plan."""

    mode: str
    deformation_mode: str
    channels: tuple[InputChannelSemantics, ...]
    point_dispositions: tuple[PointDisposition, ...]
    selected_temperature_k: Decimal | float | None = None
    temperature_source: str = "not_provided"
    strain_amplitude: Decimal | float | None = None
    strain_amplitude_quantity: str = "mechanics.strain.shear"
    strain_amplitude_unit: str = "1"
    frequency_kind: str = "not_applicable"
    angular_frequency_conversion: str = "not_applicable"
    source_kind: str = "governed_test_data"
    processing_method: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"relaxation", "dma", "dma_frequency_master_curve"}:
            raise LinearViscoelasticInputError(
                "input mode must be relaxation, dma, or dma_frequency_master_curve"
            )
        if self.deformation_mode != "shear":
            raise LinearViscoelasticInputError("production input deformation_mode must be shear")
        if self.mode != "dma_frequency_master_curve" and (
            self.source_kind != "governed_test_data" or self.processing_method is not None
        ):
            raise LinearViscoelasticInputError(
                "direct governed Test Data cannot declare a Processing Output source"
            )
        expected = (
            (
                ("time.elapsed", "independent", "s"),
                ("mechanics.modulus.shear.relaxation", "dependent", "Pa"),
            )
            if self.mode == "relaxation"
            else (
                ("physics.temperature", "independent", "K"),
                ("frequency.cyclic", "independent", "Hz"),
                ("mechanics.modulus.storage", "dependent", "Pa"),
                ("mechanics.modulus.loss", "dependent", "Pa"),
            )
            if self.mode == "dma"
            else (
                ("frequency.angular.reduced", "independent", "rad/s"),
                ("mechanics.modulus.storage", "dependent", "Pa"),
                ("mechanics.modulus.loss", "dependent", "Pa"),
            )
        )
        actual = tuple(
            (item.quantity_semantics, item.axis_role, item.normalized_unit)
            for item in self.channels
        )
        if actual != expected:
            raise LinearViscoelasticInputError(
                "active governed channel quantity, role, or normalized unit is unsupported",
                code="INPUT_CHANNEL_SEMANTICS_UNSUPPORTED",
                recovery_hint=(
                    "Create canonical governed shear relaxation or shear DMA Test Data "
                    "with the approved channel quantities and units."
                ),
            )
        ordinals = tuple(item.ordinal for item in self.point_dispositions)
        if not ordinals or ordinals != tuple(range(len(ordinals))):
            raise LinearViscoelasticInputError(
                "point dispositions must cover every source ordinal exactly once",
                code="INPUT_POINT_PARTITION_INCOMPLETE",
            )
        if (
            sum(item.partition is PointPartition.CALIBRATION for item in self.point_dispositions)
            < 3
        ):
            raise LinearViscoelasticInputError(
                "at least three source rows must be assigned to calibration",
                code="INPUT_CALIBRATION_POINT_COUNT",
            )
        if self.temperature_source not in {
            "channel",
            "condition",
            "processing_reference_temperature",
            "not_provided",
        }:
            raise LinearViscoelasticInputError(
                "temperature_source must be channel, condition, or not_provided"
            )
        if self.selected_temperature_k is not None:
            _positive(self.selected_temperature_k, "selected_temperature_k")
        if self.mode == "dma":
            if self.selected_temperature_k is None or self.temperature_source != "channel":
                raise LinearViscoelasticInputError(
                    "DMA requires one explicit selected channel temperature",
                    code="INPUT_TEMPERATURE_REQUIRED",
                )
            if (
                self.frequency_kind != "cyclic_hz"
                or self.angular_frequency_conversion != "omega_rad_per_s=2*pi*frequency_hz"
            ):
                raise LinearViscoelasticInputError(
                    "DMA requires explicit cyclic Hz and omega=2*pi*f conversion evidence"
                )
        elif self.mode == "dma_frequency_master_curve":
            if (
                self.selected_temperature_k is None
                or self.temperature_source != "processing_reference_temperature"
            ):
                raise LinearViscoelasticInputError(
                    "DMA master curve requires the confirmed reference temperature"
                )
            if (
                self.source_kind != "processing_output"
                or self.processing_method != "polymer.dma_frequency_master_curve@1.0.0"
            ):
                raise LinearViscoelasticInputError(
                    "DMA master curve requires the exact governed Processing Output method"
                )
            if (
                self.frequency_kind != "reduced_angular_rad_per_s"
                or self.angular_frequency_conversion
                != (
                    "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
                    "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
                )
            ):
                raise LinearViscoelasticInputError(
                    "DMA master curve requires explicit reduced angular-frequency evidence"
                )
        elif (
            self.frequency_kind != "not_applicable"
            or self.angular_frequency_conversion != "not_applicable"
        ):
            raise LinearViscoelasticInputError(
                "relaxation input cannot declare a frequency conversion"
            )
        if self.strain_amplitude is not None:
            _positive(self.strain_amplitude, "strain_amplitude")
        if (
            self.strain_amplitude_quantity != "mechanics.strain.shear"
            or self.strain_amplitude_unit != "1"
        ):
            raise LinearViscoelasticInputError(
                "strain amplitude must use mechanics.strain.shear with unit 1"
            )

    def canonical(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "deformation_mode": self.deformation_mode,
            "channels": [item.canonical() for item in self.channels],
            "point_dispositions": [item.canonical() for item in self.point_dispositions],
            "selected_temperature_k": (
                str(_decimal(self.selected_temperature_k, "selected_temperature_k"))
                if self.selected_temperature_k is not None
                else None
            ),
            "temperature_source": self.temperature_source,
            "strain_amplitude": (
                str(_decimal(self.strain_amplitude, "strain_amplitude"))
                if self.strain_amplitude is not None
                else None
            ),
            "strain_amplitude_quantity": self.strain_amplitude_quantity,
            "strain_amplitude_unit": self.strain_amplitude_unit,
            "frequency_kind": self.frequency_kind,
            "angular_frequency_conversion": self.angular_frequency_conversion,
            "source_kind": self.source_kind,
            "processing_method": self.processing_method,
        }


@dataclass(frozen=True, slots=True)
class CanonicalViscoelasticInput:
    """Exact source rows plus the immutable evidence needed by a calibration plan."""

    relaxation: tuple[RelaxationObservation, ...] = ()
    dma: tuple[DmaObservation, ...] = ()
    selected_temperature_k: Decimal | float | None = None
    strain_amplitude: Decimal | float | None = None
    strain_amplitude_key: str = "mechanics.strain.shear"
    strain_amplitude_unit: str = "1"
    availability: ChannelAvailability = field(default_factory=ChannelAvailability)
    profile_deformation_mode: str | None = None
    canonical_test_data: ExactRevisionPin | None = None
    canonical_artifact: ArtifactPin | None = None
    normalized_artifact: ArtifactPin | None = None
    raw_source_sha256: str | None = None
    import_profile: ExactRevisionPin | None = None
    profile_sha256: str | None = None

    def __post_init__(self) -> None:
        if bool(self.relaxation) == bool(self.dma):
            raise LinearViscoelasticInputError(
                "exactly one of governed shear relaxation or governed shear DMA is required",
                code="INPUT_CHANNEL_SET_INVALID",
            )
        # Every calculation is reproducible only when all governed source identities are
        # pinned.  The worker may receive the bytes through a staged directory, but the
        # immutable aggregate/revision and Artifact digests remain part of the input
        # evidence and are never inferred from a mutable latest pointer.
        required_evidence = (
            ("canonical_test_data", self.canonical_test_data, "INPUT_CANONICAL_TEST_DATA_REQUIRED"),
            ("canonical_artifact", self.canonical_artifact, "INPUT_CANONICAL_ARTIFACT_REQUIRED"),
            ("normalized_artifact", self.normalized_artifact, "INPUT_NORMALIZED_ARTIFACT_REQUIRED"),
            ("import_profile", self.import_profile, "INPUT_IMPORT_PROFILE_REQUIRED"),
        )
        for name, value, code in required_evidence:
            if value is None:
                raise LinearViscoelasticInputError(
                    f"{name} exact immutable evidence is required",
                    code=code,
                    recovery_hint=(
                        "Create a new immutable governed source/profile revision and pin "
                        "its Artifacts."
                    ),
                )
        if self.raw_source_sha256 is None:
            raise LinearViscoelasticInputError(
                "raw source SHA-256 is required",
                code="INPUT_RAW_SOURCE_DIGEST_REQUIRED",
                recovery_hint=(
                    "Create a new immutable governed source revision with its raw source digest."
                ),
            )
        if self.profile_sha256 is None:
            raise LinearViscoelasticInputError(
                "Import Profile SHA-256 is required",
                code="INPUT_PROFILE_DIGEST_REQUIRED",
                recovery_hint=(
                    "Create a new immutable Import Profile revision and resolve its "
                    "server-side digest."
                ),
            )
        if self.dma and self.profile_deformation_mode != "shear":
            raise LinearViscoelasticInputError(
                "DMA calibration requires exact profile revision deformation_mode=shear",
                code="INPUT_DMA_DEFORMATION_MODE_REQUIRED",
            )
        if self.profile_deformation_mode not in (None, "shear", "not-characterized"):
            raise LinearViscoelasticInputError(
                "deformation_mode must be shear or not-characterized",
                code="INPUT_PROFILE_MODE_INVALID",
            )
        if self.selected_temperature_k is not None:
            _positive(self.selected_temperature_k, "selected_temperature_k")
        if self.strain_amplitude is not None:
            _positive(self.strain_amplitude, "strain_amplitude")
            if (
                self.strain_amplitude_key != "mechanics.strain.shear"
                or self.strain_amplitude_unit != "1"
            ):
                raise LinearViscoelasticInputError(
                    "strain_amplitude must use mechanics.strain.shear with unit 1",
                    code="INPUT_STRAIN_AMPLITUDE_SEMANTICS_INVALID",
                )
        if self.raw_source_sha256 is not None:
            _sha256(self.raw_source_sha256, "raw_source_sha256")
        if self.profile_sha256 is not None:
            _sha256(self.profile_sha256, "profile_sha256")
        if (
            self.import_profile is not None
            and self.import_profile.sha256 is not None
            and self.profile_sha256 is not None
            and self.import_profile.sha256 != self.profile_sha256
        ):
            raise LinearViscoelasticInputError(
                "Import Profile pin digest differs from resolved profile_sha256",
                code="INPUT_PROFILE_DIGEST_MISMATCH",
                recovery_hint=(
                    "Resolve the digest from the exact immutable Import Profile revision "
                    "and create a new Plan."
                ),
            )
        _validate_observation_ordinals(self.relaxation)
        _validate_observation_ordinals(self.dma)
        _validate_monotonic_input(self)
        if self.dma:
            temperatures = {_decimal(point.temperature_k, "temperature_k") for point in self.dma}
            if len(temperatures) != 1:
                raise LinearViscoelasticInputError(
                    "DMA input must be a single isothermal temperature",
                    code="INPUT_TEMPERATURE_NOT_ISOTHERMAL",
                )
            if self.selected_temperature_k is not None and _decimal(
                self.selected_temperature_k, "selected_temperature_k"
            ) != next(iter(temperatures)):
                raise LinearViscoelasticInputError(
                    "selected temperature must equal the normalized DMA temperature exactly",
                    code="INPUT_TEMPERATURE_MISMATCH",
                )
        if self.relaxation and self.selected_temperature_k is not None:
            # Relaxation may carry a TestCondition temperature in a higher-level adapter;
            # no hidden TTS/tolerance is performed by this first slice.
            _positive(self.selected_temperature_k, "selected_temperature_k")

    @classmethod
    def from_relaxation(cls, points: Iterable[RelaxationObservation], **kwargs: Any) -> Self:
        return cls(relaxation=tuple(points), **kwargs)

    @classmethod
    def from_dma(cls, points: Iterable[DmaObservation], **kwargs: Any) -> Self:
        return cls(dma=tuple(points), **kwargs)

    @property
    def mode(self) -> str:
        return "relaxation" if self.relaxation else "dma"

    @property
    def channels(self) -> tuple[LinearViscoelasticChannel, ...]:
        return (
            (LinearViscoelasticChannel.RELAXATION,)
            if self.relaxation
            else (LinearViscoelasticChannel.DMA_STORAGE, LinearViscoelasticChannel.DMA_LOSS)
        )

    def canonical(self) -> dict[str, object]:
        result: dict[str, object] = {
            "mode": self.mode,
            "relaxation": [point.canonical() for point in self.relaxation],
            "dma": [point.canonical() for point in self.dma],
            "selected_temperature_k": (
                str(_decimal(self.selected_temperature_k, "selected_temperature_k"))
                if self.selected_temperature_k is not None
                else None
            ),
            "strain_amplitude": (
                str(_decimal(self.strain_amplitude, "strain_amplitude"))
                if self.strain_amplitude is not None
                else None
            ),
            "strain_amplitude_key": self.strain_amplitude_key,
            "strain_amplitude_unit": self.strain_amplitude_unit,
            "availability": self.availability.canonical(),
            "profile_deformation_mode": self.profile_deformation_mode,
        }
        for name, value in (
            ("canonical_test_data", self.canonical_test_data),
            ("canonical_artifact", self.canonical_artifact),
            ("normalized_artifact", self.normalized_artifact),
            ("import_profile", self.import_profile),
        ):
            result[name] = value.canonical() if value is not None else None
        result["raw_source_sha256"] = self.raw_source_sha256
        result["profile_sha256"] = self.profile_sha256
        return result


def _validate_observation_ordinals(points: Sequence[object]) -> None:
    ordinals = [
        int(point.ordinal)
        for point in points
        if isinstance(point, (RelaxationObservation, DmaObservation))
    ]
    if len(ordinals) != len(set(ordinals)):
        raise LinearViscoelasticInputError(
            "every source ordinal must occur once", code="INPUT_SOURCE_ORDINAL_DUPLICATE"
        )
    if tuple(sorted(ordinals)) != tuple(ordinals):
        raise LinearViscoelasticInputError(
            "source ordinals must be ordered", code="INPUT_SOURCE_ORDINAL_ORDER"
        )


def _validate_monotonic_input(value: CanonicalViscoelasticInput) -> None:
    if value.relaxation:
        domains = [_as_float(point.time_s, "time_s") for point in value.relaxation]
        for point, domain in zip(value.relaxation, domains, strict=True):
            if domain < 0:
                raise LinearViscoelasticInputError(
                    "relaxation time must be non-negative", code="INPUT_DOMAIN_NEGATIVE"
                )
            if domain == 0 and not (
                point.partition is PointPartition.EXCLUDED
                and point.exclusion_reason == "INSTANTANEOUS_LIMIT"
            ):
                raise LinearViscoelasticInputError(
                    "t=0 is only allowed as EXCLUDED/INSTANTANEOUS_LIMIT",
                    code="INPUT_ZERO_TIME_NOT_ALLOWED",
                )
        if any(right <= left for left, right in pairwise(domains)):
            raise LinearViscoelasticInputError(
                "relaxation domain must be finite, unique, and increasing",
                code="INPUT_DOMAIN_NOT_INCREASING",
            )
    if value.dma:
        domains = [_as_float(point.frequency_hz, "frequency_hz") for point in value.dma]
        if any(right <= left for left, right in pairwise(domains)):
            raise LinearViscoelasticInputError(
                "DMA frequency domain must be finite, unique, and increasing",
                code="INPUT_DOMAIN_NOT_INCREASING",
            )
