"""Resolve exact governed Test Data into one explicit calibration input contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise
from uuid import UUID

from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    TestDataDocumentSnapshot,
)
from cmp.modules.datasets.application.governed_import import GovernedImportService
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    TestCondition,
    TestDataChannel,
    parse_canonical_test_data,
)
from cmp.modules.datasets.domain.governed_tabular import TabularDataSchema
from cmp.modules.identity_access.application.authorization import AuthorizationService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    ArtifactPin,
    ChannelAvailability,
    ExactRevisionPin,
    GovernedViscoelasticInputSemantics,
    InputChannelSemantics,
    LinearViscoelasticInputError,
    PointDisposition,
    PointPartition,
)
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_MEDIA_TYPE,
    CommonProcessingOutputService,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
    DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
    DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
    DmaPartition,
    frequency_master_curve_from_parquet,
)

_CANONICAL_MEDIA_TYPE = "application/vnd.cmp.test-data+json"
_PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
_RELAXATION_SEMANTICS = (
    "time.elapsed",
    "mechanics.modulus.shear.relaxation",
)
_DMA_SEMANTICS = (
    "physics.temperature",
    "frequency.cyclic",
    "mechanics.modulus.storage",
    "mechanics.modulus.loss",
)
_TEMPERATURE_SEMANTICS = {"physics.temperature", "temperature.test"}


@dataclass(frozen=True, slots=True)
class ResolveGovernedViscoelasticInput:
    test_data_id: UUID
    test_data_revision_id: UUID
    selected_temperature_k: Decimal | float
    point_dispositions: tuple[PointDisposition, ...]
    availability: ChannelAvailability


@dataclass(frozen=True, slots=True)
class ResolveProcessedViscoelasticInput:
    processing_output_id: UUID
    processing_output_revision_id: UUID
    availability: ChannelAvailability


@dataclass(frozen=True, slots=True)
class ResolvedGovernedViscoelasticInput:
    classification: DataClassification
    test_data: ExactRevisionPin
    canonical_artifact: ArtifactPin
    normalized_artifact: ArtifactPin
    raw_source_sha256: str
    import_profile: ExactRevisionPin
    profile_sha256: str
    semantics: GovernedViscoelasticInputSemantics
    processing_output: ExactRevisionPin | None = None
    processing_metadata_artifact: ArtifactPin | None = None
    processing_result_artifact: ArtifactPin | None = None


def _active_channels(
    document: CanonicalTestDataDocument,
    expected: tuple[str, ...],
) -> tuple[TestDataChannel, ...]:
    by_semantics: dict[str, TestDataChannel] = {}
    for channel in document.channels:
        if channel.quantity_semantics in expected:
            if channel.quantity_semantics in by_semantics:
                raise LinearViscoelasticInputError(
                    "governed Test Data contains a duplicate active quantity channel",
                    code="INPUT_CHANNEL_SEMANTICS_DUPLICATE",
                )
            by_semantics[channel.quantity_semantics] = channel
    if set(by_semantics) != set(expected):
        raise LinearViscoelasticInputError(
            "governed Test Data does not contain the exact approved quantity channels",
            code="INPUT_CHANNEL_SEMANTICS_UNSUPPORTED",
        )
    channels = tuple(by_semantics[item] for item in expected)
    if any(value is None for channel in channels for value in channel.normalized_values):
        raise LinearViscoelasticInputError(
            "active governed channels cannot contain missing normalized values",
            code="INPUT_ACTIVE_CHANNEL_MISSING_VALUE",
        )
    return channels


def _condition(conditions: tuple[TestCondition, ...], semantics: set[str]) -> TestCondition | None:
    matches = tuple(item for item in conditions if item.quantity_semantics in semantics)
    if len(matches) > 1:
        raise LinearViscoelasticInputError(
            "governed Test Data contains ambiguous duplicate conditions",
            code="INPUT_CONDITION_AMBIGUOUS",
        )
    return matches[0] if matches else None


def _channel_contract(channels: tuple[TestDataChannel, ...]) -> tuple[InputChannelSemantics, ...]:
    return tuple(
        InputChannelSemantics(
            key=item.key,
            quantity_semantics=item.quantity_semantics,
            axis_role=item.axis_role.value,
            original_unit_string=item.original_unit_string,
            normalized_unit=item.normalized_unit,
        )
        for item in channels
    )


def _validate_partition_domain(
    *,
    command: ResolveGovernedViscoelasticInput,
    mode: str,
    channels: tuple[TestDataChannel, ...],
) -> None:
    if len(command.point_dispositions) != len(channels[0].normalized_values):
        raise LinearViscoelasticInputError(
            "point dispositions must cover every Test Data source row",
            code="INPUT_POINT_PARTITION_INCOMPLETE",
        )
    selected = Decimal(str(command.selected_temperature_k))
    if not selected.is_finite() or selected <= 0:
        raise LinearViscoelasticInputError(
            "selected_temperature_k must be a positive finite value",
            code="INPUT_TEMPERATURE_INVALID",
        )
    if mode == "dma":
        temperatures = tuple(
            Decimal(str(value)) for value in channels[0].normalized_values if value is not None
        )
        if selected not in temperatures:
            raise LinearViscoelasticInputError(
                "selected DMA temperature does not exist in the exact Test Data revision",
                code="INPUT_TEMPERATURE_NOT_FOUND",
            )
        for disposition, temperature in zip(command.point_dispositions, temperatures, strict=True):
            if temperature != selected and disposition.partition is not PointPartition.EXCLUDED:
                raise LinearViscoelasticInputError(
                    "DMA rows outside the selected temperature must be explicitly excluded",
                    code="INPUT_TEMPERATURE_PARTITION_MISMATCH",
                    recovery_hint=(
                        "Mark every row outside the selected isothermal slice EXCLUDED with "
                        "an engineer reason, then create a new Plan."
                    ),
                )
        active_frequencies = tuple(
            Decimal(str(value))
            for value, disposition, temperature in zip(
                channels[1].normalized_values,
                command.point_dispositions,
                temperatures,
                strict=True,
            )
            if value is not None
            and temperature == selected
            and disposition.partition is not PointPartition.EXCLUDED
        )
        if any(right <= left for left, right in pairwise(active_frequencies)):
            raise LinearViscoelasticInputError(
                "active DMA frequency rows must be unique and increasing",
                code="INPUT_DOMAIN_NOT_INCREASING",
            )
    else:
        active_times = tuple(
            Decimal(str(value))
            for value, disposition in zip(
                channels[0].normalized_values,
                command.point_dispositions,
                strict=True,
            )
            if value is not None and disposition.partition is not PointPartition.EXCLUDED
        )
        if any(right <= left for left, right in pairwise(active_times)):
            raise LinearViscoelasticInputError(
                "active relaxation time rows must be unique and increasing",
                code="INPUT_DOMAIN_NOT_INCREASING",
            )


class GovernedLinearViscoelasticInputResolver:
    """Server-side exact-revision resolver; clients cannot supply Artifact or digest pins."""

    def __init__(
        self,
        *,
        test_data: CanonicalTestDataService,
        governed_imports: GovernedImportService,
        authorization: AuthorizationService,
        processing_outputs: CommonProcessingOutputService | None = None,
    ) -> None:
        self._test_data = test_data
        self._governed_imports = governed_imports
        self._authorization = authorization
        self._processing_outputs = processing_outputs

    def assert_current_revisions(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        test_data: ExactRevisionPin,
        import_profile: ExactRevisionPin,
        processing_output: ExactRevisionPin | None = None,
    ) -> None:
        """Reject promotion after a pinned upstream aggregate acquires a new head.

        The old Plan, Run, Selection, and promoted model remain immutable and readable.
        This check only prevents an old exact context from being presented as current.
        """

        if (
            decision.permission is not Permission.CALIBRATION_EXECUTE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
        ):
            raise LinearViscoelasticInputError(
                "calibration authorization does not match the staleness request"
            )
        dataset_read = self._authorization.authorize(context, Permission.DATASET_READ)
        current_test_data = next(
            (
                item
                for item in self._test_data.list_documents(context, dataset_read)
                if item.id == test_data.aggregate_id
            ),
            None,
        )
        if current_test_data is None:
            raise LinearViscoelasticInputError(
                "pinned Test Data stable identity is no longer visible",
                code="INPUT_UPSTREAM_NOT_VISIBLE",
            )
        current_profile = self._governed_imports.get_profile(
            context,
            dataset_read,
            import_profile.aggregate_id,
        )
        changes: list[str] = []
        if current_test_data.current.revision_id != test_data.revision_id:
            changes.append(
                "Test Data "
                f"{test_data.aggregate_id} pinned={test_data.revision_id} "
                f"current={current_test_data.current.revision_id}"
            )
        if current_profile.current.record.revision_id != import_profile.revision_id:
            changes.append(
                "Import Profile "
                f"{import_profile.aggregate_id} pinned={import_profile.revision_id} "
                f"current={current_profile.current.record.revision_id}"
            )
        if processing_output is not None:
            if self._processing_outputs is None:
                raise LinearViscoelasticInputError(
                    "Processing Output currentness check is unavailable",
                    code="INPUT_UPSTREAM_NOT_VISIBLE",
                )
            processing_read = self._authorization.authorize(context, Permission.PROCESSING_READ)
            current_output = next(
                (
                    item
                    for item in self._processing_outputs.list_outputs(context, processing_read)
                    if item.id == processing_output.aggregate_id
                ),
                None,
            )
            if current_output is None:
                raise LinearViscoelasticInputError(
                    "pinned Processing Output stable identity is no longer visible",
                    code="INPUT_UPSTREAM_NOT_VISIBLE",
                )
            if current_output.current.revision_id != processing_output.revision_id:
                changes.append(
                    "Processing Output "
                    f"{processing_output.aggregate_id} pinned={processing_output.revision_id} "
                    f"current={current_output.current.revision_id}"
                )
        if changes:
            raise LinearViscoelasticInputError(
                "upstream current revision changed: " + "; ".join(changes),
                code="INPUT_UPSTREAM_STALE",
                recovery_hint=(
                    "Keep the old exact model as history or create a new Plan from the "
                    "current upstream revisions."
                ),
            )

    async def resolve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ResolveGovernedViscoelasticInput,
    ) -> ResolvedGovernedViscoelasticInput:
        if (
            decision.permission is not Permission.CALIBRATION_EXECUTE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
        ):
            raise LinearViscoelasticInputError(
                "calibration authorization does not match the input request"
            )
        dataset_read = self._authorization.authorize(context, Permission.DATASET_READ)
        snapshot, canonical_bytes = await self._test_data.export_document(
            context,
            dataset_read,
            command.test_data_id,
            command.test_data_revision_id,
        )
        try:
            decoded = json.loads(canonical_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LinearViscoelasticInputError(
                "canonical Test Data Artifact is not valid UTF-8 JSON",
                code="INPUT_CANONICAL_ARTIFACT_INVALID",
            ) from error
        if not isinstance(decoded, dict):
            raise LinearViscoelasticInputError(
                "canonical Test Data Artifact must be a JSON object",
                code="INPUT_CANONICAL_ARTIFACT_INVALID",
            )
        document = parse_canonical_test_data(decoded)
        return self._resolve_snapshot(snapshot, document, context, dataset_read, command)

    async def resolve_processing_output(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ResolveProcessedViscoelasticInput,
    ) -> ResolvedGovernedViscoelasticInput:
        """Resolve a confirmed DMA frequency master curve into a production calibration input."""

        if (
            decision.permission is not Permission.CALIBRATION_EXECUTE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
        ):
            raise LinearViscoelasticInputError(
                "calibration authorization does not match the processed input request"
            )
        if self._processing_outputs is None:
            raise LinearViscoelasticInputError(
                "Processing Output input resolution is unavailable",
                code="INPUT_PROCESSING_OUTPUT_UNAVAILABLE",
            )
        if command.availability.sweep.value != "PROVIDED":
            raise LinearViscoelasticInputError(
                "DMA master curve requires sweep availability=PROVIDED",
                code="INPUT_SWEEP_STATUS_REQUIRED",
            )
        processing_read = self._authorization.authorize(context, Permission.PROCESSING_READ)
        output, result_bytes = await self._processing_outputs.export_exact_result(
            context,
            processing_read,
            command.processing_output_id,
            command.processing_output_revision_id,
        )
        content = output.content
        if (
            len(content.steps) != 1
            or content.steps[0].method_id != DMA_FREQUENCY_MASTER_CURVE_METHOD_ID
            or content.steps[0].method_version != DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION
            or content.independent_quantity != "frequency.angular.reduced"
            or content.result_schema_ref != DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID
            or content.result_media_type != _PARQUET_MEDIA_TYPE
            or content.source_profile_kind != "governed_import_profile"
            or content.governed_import_profile is None
            or content.governed_import_profile_sha256 is None
            or content.result_artifact_id is None
            or content.result_sha256 is None
        ):
            raise LinearViscoelasticInputError(
                "Processing Output is not the governed DMA frequency master-curve contract",
                code="INPUT_PROCESSING_OUTPUT_SCHEMA_UNSUPPORTED",
                recovery_hint=(
                    "Create a confirmed horizontal DMA TTS Processing Output and pin "
                    "its exact revision."
                ),
            )
        rows = frequency_master_curve_from_parquet(result_bytes)
        if len(rows) != content.final_point_count:
            raise LinearViscoelasticInputError(
                "Processing Output row count differs from its immutable metadata",
                code="INPUT_PROCESSING_OUTPUT_ROW_COUNT_MISMATCH",
            )
        if tuple(row.source_ordinal for row in rows) != tuple(range(len(rows))):
            raise LinearViscoelasticInputError(
                "DMA master-curve rows must preserve every source ordinal exactly once",
                code="INPUT_POINT_PARTITION_INCOMPLETE",
            )
        active = tuple(row for row in rows if row.partition is not DmaPartition.EXCLUDED)
        calibration = tuple(row for row in rows if row.partition is DmaPartition.CALIBRATION)
        if len(calibration) < 3:
            raise LinearViscoelasticInputError(
                "DMA master curve requires at least three calibration rows",
                code="INPUT_CALIBRATION_POINT_COUNT",
            )
        active_frequencies = tuple(row.reduced_angular_frequency_rad_per_s for row in active)
        if (
            any(value is None or value <= 0 for value in active_frequencies)
            or len(set(active_frequencies)) != len(active_frequencies)
            or any(row.storage_modulus_pa <= 0 or row.loss_modulus_pa < 0 for row in active)
        ):
            raise LinearViscoelasticInputError(
                "DMA master-curve active rows have invalid or duplicate response coordinates",
                code="INPUT_DOMAIN_INVALID",
                recovery_hint=(
                    "Correct or explicitly exclude the affected temperature rows and "
                    "create a new output."
                ),
            )
        shift_law = content.steps[0].options.get("shift_law")
        if not isinstance(shift_law, dict):
            raise LinearViscoelasticInputError(
                "DMA master curve does not serialize its shift law",
                code="INPUT_SHIFT_POLICY_MISSING",
            )
        reference_temperature = shift_law.get("reference_temperature_k")
        try:
            reference_temperature_k = Decimal(str(reference_temperature))
        except Exception as error:
            raise LinearViscoelasticInputError(
                "DMA master curve reference temperature is invalid",
                code="INPUT_TEMPERATURE_INVALID",
            ) from error
        if not reference_temperature_k.is_finite() or reference_temperature_k <= 0:
            raise LinearViscoelasticInputError(
                "DMA master curve reference temperature is invalid",
                code="INPUT_TEMPERATURE_INVALID",
            )

        dataset_read = self._authorization.authorize(context, Permission.DATASET_READ)
        snapshot, _ = await self._test_data.export_document(
            context,
            dataset_read,
            content.source_document.aggregate_id,
            content.source_document.revision_id,
        )
        if (
            snapshot.current.content_hash != content.source_document_sha256
            or snapshot.content.canonical_sha256 != content.source_canonical_artifact_sha256
        ):
            raise LinearViscoelasticInputError(
                "DMA master curve source Test Data pin is inconsistent",
                code="INPUT_SOURCE_DIGEST_MISMATCH",
            )
        source = snapshot.content.governed_source
        if source is None or source.tabular_import is None:
            raise LinearViscoelasticInputError(
                "DMA master curve has no governed source lineage",
                code="INPUT_GOVERNED_SOURCE_REQUIRED",
            )
        profile = self._governed_imports.get_profile_revision_for_calibration(
            context,
            dataset_read,
            content.governed_import_profile.aggregate_id,
            content.governed_import_profile.revision_id,
        )
        if (
            profile.revision.record.content_hash != content.governed_import_profile_sha256
            or profile.revision.content.data_schema is not TabularDataSchema.DMA_TEMPERATURE_SWEEP
            or profile.revision.content.deformation_mode != "shear"
            or source.tabular_import.import_profile.aggregate_id != profile.profile_id
            or source.tabular_import.import_profile.revision_id
            != profile.revision.record.revision_id
        ):
            raise LinearViscoelasticInputError(
                "DMA master curve Import Profile lineage is inconsistent",
                code="INPUT_PROFILE_DIGEST_MISMATCH",
            )
        classification = DataClassification(snapshot.current.scope.classification)
        if classification.value != output.current.scope.classification:
            raise LinearViscoelasticInputError(
                "DMA master curve classification differs from its source Test Data",
                code="INPUT_CLASSIFICATION_MISMATCH",
            )
        dispositions = tuple(
            PointDisposition(
                row.source_ordinal,
                PointPartition(row.partition.value),
                row.exclusion_reason,
            )
            for row in rows
        )
        semantics = GovernedViscoelasticInputSemantics(
            mode="dma_frequency_master_curve",
            deformation_mode="shear",
            channels=(
                InputChannelSemantics(
                    "reduced_angular_frequency_rad_per_s",
                    "frequency.angular.reduced",
                    "independent",
                    "rad/s",
                    "rad/s",
                ),
                InputChannelSemantics(
                    "storage_modulus_pa",
                    "mechanics.modulus.storage",
                    "dependent",
                    "Pa",
                    "Pa",
                ),
                InputChannelSemantics(
                    "loss_modulus_pa",
                    "mechanics.modulus.loss",
                    "dependent",
                    "Pa",
                    "Pa",
                ),
            ),
            point_dispositions=dispositions,
            selected_temperature_k=reference_temperature_k,
            temperature_source="processing_reference_temperature",
            frequency_kind="reduced_angular_rad_per_s",
            angular_frequency_conversion=(
                "omega_reduced_rad_per_s=omega_rad_per_s*shift_factor;"
                "frequency_reduced_hz=omega_reduced_rad_per_s/(2*pi)"
            ),
            source_kind="processing_output",
            processing_method=(
                f"{DMA_FREQUENCY_MASTER_CURVE_METHOD_ID}"
                f"@{DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION}"
            ),
        )
        return ResolvedGovernedViscoelasticInput(
            classification=classification,
            test_data=ExactRevisionPin(
                snapshot.id,
                snapshot.current.revision_id,
                snapshot.current.content_hash,
            ),
            canonical_artifact=ArtifactPin(
                snapshot.content.canonical_artifact_id,
                snapshot.content.canonical_sha256,
                _CANONICAL_MEDIA_TYPE,
            ),
            normalized_artifact=ArtifactPin(
                snapshot.content.normalized_artifact_id,
                snapshot.content.normalized_sha256,
                _PARQUET_MEDIA_TYPE,
            ),
            raw_source_sha256=snapshot.content.source.sha256,
            import_profile=ExactRevisionPin(
                profile.profile_id,
                profile.revision.record.revision_id,
                profile.revision.record.content_hash,
            ),
            profile_sha256=profile.revision.record.content_hash,
            semantics=semantics,
            processing_output=ExactRevisionPin(
                output.id,
                output.current.revision_id,
                output.current.content_hash,
            ),
            processing_metadata_artifact=ArtifactPin(
                content.output_artifact_id,
                content.output_sha256,
                PROCESSING_OUTPUT_MEDIA_TYPE,
            ),
            processing_result_artifact=ArtifactPin(
                content.result_artifact_id,
                content.result_sha256,
                content.result_media_type,
            ),
        )

    def _resolve_snapshot(
        self,
        snapshot: TestDataDocumentSnapshot,
        document: CanonicalTestDataDocument,
        context: SecurityContext,
        dataset_read: AuthorizationDecision,
        command: ResolveGovernedViscoelasticInput,
    ) -> ResolvedGovernedViscoelasticInput:
        source = snapshot.content.governed_source
        if source is None or source.tabular_import is None:
            raise LinearViscoelasticInputError(
                "calibration accepts direct exact governed Test Data only",
                code="INPUT_GOVERNED_SOURCE_REQUIRED",
            )
        tabular = source.tabular_import
        profile = self._governed_imports.get_profile_revision_for_calibration(
            context,
            dataset_read,
            tabular.import_profile.aggregate_id,
            tabular.import_profile.revision_id,
        )
        profile_content = profile.revision.content
        expected: tuple[str, ...]
        if profile_content.data_schema is TabularDataSchema.SHEAR_RELAXATION:
            mode = "relaxation"
            expected = _RELAXATION_SEMANTICS
        elif profile_content.data_schema is TabularDataSchema.DMA_FREQUENCY_TEMPERATURE_SWEEP:
            if profile_content.deformation_mode != "shear":
                raise LinearViscoelasticInputError(
                    "governed DMA Import Profile must declare deformation_mode=shear",
                    code="INPUT_DMA_DEFORMATION_MODE_REQUIRED",
                )
            mode = "dma"
            expected = _DMA_SEMANTICS
            if command.availability.sweep.value != "PROVIDED":
                raise LinearViscoelasticInputError(
                    "governed DMA requires sweep availability=PROVIDED",
                    code="INPUT_SWEEP_STATUS_REQUIRED",
                )
        else:
            raise LinearViscoelasticInputError(
                "only governed shear relaxation or governed shear DMA is supported",
                code="INPUT_PROFILE_SCHEMA_UNSUPPORTED",
            )
        channels = _active_channels(document, expected)
        _validate_partition_domain(command=command, mode=mode, channels=channels)
        selected_temperature = Decimal(str(command.selected_temperature_k))
        temperature_source = "channel"
        if mode == "relaxation":
            temperature = _condition(document.conditions, _TEMPERATURE_SEMANTICS)
            if (
                temperature is None
                or temperature.normalized_unit != "K"
                or temperature.normalized_value != selected_temperature
            ):
                raise LinearViscoelasticInputError(
                    "relaxation Test Data must carry the exact selected temperature in K",
                    code="INPUT_TEMPERATURE_MISMATCH",
                )
            temperature_source = "condition"
        strain = _condition(document.conditions, {"mechanics.strain.shear"})
        if strain is not None and strain.normalized_unit != "1":
            raise LinearViscoelasticInputError(
                "shear strain amplitude condition must normalize to unit 1",
                code="INPUT_STRAIN_AMPLITUDE_SEMANTICS_INVALID",
            )
        semantics = GovernedViscoelasticInputSemantics(
            mode=mode,
            deformation_mode="shear",
            channels=_channel_contract(channels),
            point_dispositions=command.point_dispositions,
            selected_temperature_k=selected_temperature,
            temperature_source=temperature_source,
            strain_amplitude=strain.normalized_value if strain is not None else None,
            frequency_kind="cyclic_hz" if mode == "dma" else "not_applicable",
            angular_frequency_conversion=(
                "omega_rad_per_s=2*pi*frequency_hz" if mode == "dma" else "not_applicable"
            ),
        )
        classification = DataClassification(snapshot.current.scope.classification)
        return ResolvedGovernedViscoelasticInput(
            classification=classification,
            test_data=ExactRevisionPin(
                snapshot.id,
                snapshot.current.revision_id,
                snapshot.current.content_hash,
            ),
            canonical_artifact=ArtifactPin(
                snapshot.content.canonical_artifact_id,
                snapshot.content.canonical_sha256,
                _CANONICAL_MEDIA_TYPE,
            ),
            normalized_artifact=ArtifactPin(
                snapshot.content.normalized_artifact_id,
                snapshot.content.normalized_sha256,
                _PARQUET_MEDIA_TYPE,
            ),
            raw_source_sha256=snapshot.content.source.sha256,
            import_profile=ExactRevisionPin(
                profile.profile_id,
                profile.revision.record.revision_id,
                profile.revision.record.content_hash,
            ),
            profile_sha256=profile.revision.record.content_hash,
            semantics=semantics,
        )
