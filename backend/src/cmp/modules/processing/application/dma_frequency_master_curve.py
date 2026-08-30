"""Application boundary for governed fixed-frequency DMA TTS outputs."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from cmp.modules.artifacts.application.content import (
    ArtifactCommitHook,
    ArtifactService,
    FinalizedArtifact,
)
from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    GovernedTestDataSource,
    TestDataDocumentSnapshot,
)
from cmp.modules.datasets.application.governed_import import (
    GovernedImportService,
    ImportProfileRevisionSnapshot,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
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
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_AGGREGATE_TYPE,
    PROCESSING_OUTPUT_MEDIA_TYPE,
    PROCESSING_OUTPUT_SCHEMA_ID_1_6,
    PROCESSING_OUTPUT_SCHEMA_VERSION_1_6,
    ExactRevisionPin,
    ProcessingOutputContent,
    ProcessingOutputRepository,
    ProcessingOutputSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
    DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
    DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
    DMA_LOSS_MODULUS_METHOD_ID,
    DMA_LOSS_MODULUS_METHOD_VERSION,
    DMA_LOSS_MODULUS_PARQUET_SCHEMA_ID,
    PARQUET_MEDIA_TYPE,
    ArrheniusShiftLaw,
    DmaPartition,
    DmaProcessingError,
    DmaRowDisposition,
    DmaShiftLaw,
    DmaTemperatureSweepRow,
    DmaWlfStartingSuggestion,
    WlfShiftLaw,
    build_frequency_master_curve,
    derive_loss_modulus,
    frequency_master_curve_parquet_bytes,
    loss_modulus_parquet_bytes,
    recommend_wlf_starting_values,
)
from cmp.shared.application.revisions import CreateRevisionedAggregate, RevisionService
from cmp.shared.domain.revisions import TenantScope, canonical_json_bytes


@dataclass(frozen=True, slots=True)
class DmaTestDataPin:
    document_id: UUID
    revision_id: UUID
    content_sha256: str


@dataclass(frozen=True, slots=True)
class DmaImportProfilePin:
    profile_id: UUID
    revision_id: UUID
    content_sha256: str


@dataclass(frozen=True, slots=True)
class RecommendDmaFrequencyMasterCurve:
    test_data: DmaTestDataPin
    import_profile: DmaImportProfilePin


@dataclass(frozen=True, slots=True)
class CreateDmaFrequencyMasterCurve:
    classification: DataClassification
    label: str
    test_data: DmaTestDataPin
    import_profile: DmaImportProfilePin
    dispositions: tuple[DmaRowDisposition, ...]
    shift_law: DmaShiftLaw
    confirmed: bool
    confirmation_reason: str
    change_reason: str
    recommendation_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedDmaFrequencyMasterCurve:
    loss_modulus_output: ProcessingOutputSnapshot | None
    master_curve_output: ProcessingOutputSnapshot


@dataclass(frozen=True, slots=True)
class _ResolvedInput:
    document: CanonicalTestDataDocument
    rows: tuple[DmaTemperatureSweepRow, ...]
    test_data_snapshot: TestDataDocumentSnapshot
    import_profile_snapshot: ImportProfileRevisionSnapshot


def _channel(document: CanonicalTestDataDocument, semantics: str) -> TestDataChannel | None:
    matches = tuple(item for item in document.channels if item.quantity_semantics == semantics)
    if len(matches) > 1:
        raise DmaProcessingError(
            "CMP-PROCESSING-4310",
            f"Test Data repeats channel semantics {semantics}",
            "Correct the governed Import Profile and create a new exact Test Data revision.",
        )
    return matches[0] if matches else None


def _required_channel(document: CanonicalTestDataDocument, semantics: str) -> TestDataChannel:
    channel = _channel(document, semantics)
    if channel is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4304",
            f"Test Data is missing channel semantics {semantics}",
            "Map the required DMA quantity and import a new Test Data revision.",
        )
    return channel


def _float_at(channel: TestDataChannel, ordinal: int) -> float:
    value = channel.normalized_values[ordinal]
    if value is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4304",
            f"channel {channel.key} has a missing value at source ordinal {ordinal}",
            "Correct the source row or explicitly exclude it before governed import.",
        )
    return float(value)


def _frequency_hz(document: CanonicalTestDataDocument) -> float:
    matches = tuple(item for item in document.conditions if item.key == "frequency")
    if (
        len(matches) != 1
        or matches[0].quantity_semantics != "frequency.cyclic"
        or matches[0].normalized_unit != "Hz"
        or matches[0].normalized_value <= Decimal(0)
    ):
        raise DmaProcessingError(
            "CMP-PROCESSING-4304",
            "Test Data does not carry one positive fixed cyclic-frequency condition",
            "Record the measured fixed frequency as frequency.cyclic normalized to Hz.",
        )
    return float(matches[0].normalized_value)


def _rows(document: CanonicalTestDataDocument) -> tuple[DmaTemperatureSweepRow, ...]:
    temperature = _required_channel(document, "physics.temperature")
    storage = _required_channel(document, "mechanics.modulus.storage")
    loss = _channel(document, "mechanics.modulus.loss")
    tan_delta = _channel(document, "mechanics.loss_factor")
    if loss is None and tan_delta is None:
        raise DmaProcessingError(
            "CMP-PROCESSING-4304",
            "Test Data has neither loss modulus nor tan delta",
            "Import loss modulus, tan delta, or both.",
        )
    count = len(temperature.normalized_values)
    channels = tuple(item for item in (storage, loss, tan_delta) if item is not None)
    if any(len(item.normalized_values) != count for item in channels):
        raise DmaProcessingError(
            "CMP-PROCESSING-4310",
            "Test Data DMA channels have different row counts",
            "Reload the exact canonical Test Data artifact.",
        )
    frequency = _frequency_hz(document)
    return tuple(
        DmaTemperatureSweepRow(
            source_ordinal=ordinal,
            temperature_k=_float_at(temperature, ordinal),
            frequency_hz=frequency,
            storage_modulus_pa=_float_at(storage, ordinal),
            loss_modulus_pa=None if loss is None else _float_at(loss, ordinal),
            tan_delta=None if tan_delta is None else _float_at(tan_delta, ordinal),
        )
        for ordinal in range(count)
    )


def _shift_law_canonical(law: DmaShiftLaw) -> dict[str, object]:
    if isinstance(law, WlfShiftLaw):
        return {
            "kind": "wlf",
            "reference_temperature_k": law.reference_temperature_k,
            "c1": law.c1,
            "c2_k": law.c2_k,
        }
    if isinstance(law, ArrheniusShiftLaw):
        return {
            "kind": "arrhenius",
            "reference_temperature_k": law.reference_temperature_k,
            "activation_energy_j_per_mol": law.activation_energy_j_per_mol,
            "gas_constant_j_per_mol_k": law.gas_constant_j_per_mol_k,
        }
    return {
        "kind": "tabulated",
        "reference_temperature_k": law.reference_temperature_k,
        "log10_a_t_by_temperature_k": [
            {"temperature_k": temperature, "log10_a_t": shift}
            for temperature, shift in law.log10_a_t_by_temperature_k
        ],
    }


class DmaFrequencyMasterCurveService:
    def __init__(
        self,
        *,
        test_data: CanonicalTestDataService,
        governed_imports: GovernedImportService,
        outputs: ProcessingOutputRepository,
        artifacts: ArtifactService,
        authorization: AuthorizationService,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._test_data = test_data
        self._governed_imports = governed_imports
        self._outputs = outputs
        self._artifacts = artifacts
        self._authorization = authorization
        self._id = id_factory

    async def _resolve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_data: DmaTestDataPin,
        import_profile: DmaImportProfilePin,
    ) -> _ResolvedInput:
        if decision.permission is not Permission.PROCESSING_EXECUTE:
            raise DmaProcessingError(
                "CMP-PROCESSING-4304",
                "processing authorization is invalid",
                "Request Processing execute permission for this project.",
            )
        dataset_read = self._authorization.authorize(context, Permission.DATASET_READ)
        snapshot, canonical_bytes = await self._test_data.export_document(
            context,
            dataset_read,
            test_data.document_id,
            test_data.revision_id,
        )
        if snapshot.current.content_hash != test_data.content_sha256:
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "Test Data content digest does not match the exact revision",
                "Reload the exact Test Data revision and retry with its content digest.",
            )
        current = self._test_data.get_document(context, dataset_read, test_data.document_id)
        if current.current.revision_id != test_data.revision_id:
            raise DmaProcessingError(
                "CMP-PROCESSING-4309",
                "Test Data pin is no longer current",
                "Create a new TTS output from the current Test Data revision.",
            )
        source = snapshot.content.governed_source
        if source is None or source.tabular_import is None:
            raise DmaProcessingError(
                "CMP-PROCESSING-4304",
                "Test Data has no governed tabular lineage",
                "Import the DMA source through an approved governed Import Profile.",
            )
        lineage_profile = source.tabular_import.import_profile
        if (
            lineage_profile.aggregate_id != import_profile.profile_id
            or lineage_profile.revision_id != import_profile.revision_id
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "Import Profile pin does not match Test Data lineage",
                "Use the exact Import Profile revision recorded by Test Data.",
            )
        profile = self._governed_imports.get_profile_revision_for_calibration(
            context,
            dataset_read,
            import_profile.profile_id,
            import_profile.revision_id,
        )
        if profile.revision.record.content_hash != import_profile.content_sha256:
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "Import Profile content digest does not match the exact revision",
                "Reload the exact Import Profile revision and retry with its digest.",
            )
        current_profile = self._governed_imports.get_profile(
            context, dataset_read, import_profile.profile_id
        )
        if current_profile.current.record.revision_id != import_profile.revision_id:
            raise DmaProcessingError(
                "CMP-PROCESSING-4309",
                "Import Profile pin is no longer current",
                "Create a new TTS output from the current Import Profile revision.",
            )
        if (
            profile.revision.content.data_schema is not TabularDataSchema.DMA_TEMPERATURE_SWEEP
            or profile.revision.content.schema_version != "1.3.0"
            or profile.revision.content.deformation_mode != "shear"
        ):
            raise DmaProcessingError(
                "CMP-PROCESSING-4304",
                "Import Profile is not the governed shear DMA temperature-sweep contract",
                "Use schema 1.3.0 with dma_temperature_sweep and deformation_mode=shear.",
            )
        if snapshot.current.scope.classification != profile.revision.record.scope.classification:
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "Test Data and Import Profile classifications differ",
                "Create aligned governed revisions in the same classification.",
            )
        try:
            decoded = json.loads(canonical_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "canonical Test Data artifact is not valid JSON",
                "Reload the immutable canonical Test Data artifact.",
            ) from error
        if not isinstance(decoded, Mapping):
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "canonical Test Data artifact is not an object",
                "Reload the immutable canonical Test Data artifact.",
            )
        document = parse_canonical_test_data(decoded)
        return _ResolvedInput(document, _rows(document), snapshot, profile)

    async def recommend(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: RecommendDmaFrequencyMasterCurve,
    ) -> DmaWlfStartingSuggestion:
        resolved = await self._resolve(context, decision, command.test_data, command.import_profile)
        return recommend_wlf_starting_values(
            resolved.rows,
            source_evidence={
                "test_data_id": str(command.test_data.document_id),
                "test_data_revision_id": str(command.test_data.revision_id),
                "test_data_sha256": command.test_data.content_sha256,
                "import_profile_id": str(command.import_profile.profile_id),
                "import_profile_revision_id": str(command.import_profile.revision_id),
                "import_profile_sha256": command.import_profile.content_sha256,
            },
        )

    async def create(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateDmaFrequencyMasterCurve,
    ) -> CreatedDmaFrequencyMasterCurve:
        resolved = await self._resolve(context, decision, command.test_data, command.import_profile)
        snapshot = resolved.test_data_snapshot
        if snapshot.current.scope.classification != command.classification.value:
            raise DmaProcessingError(
                "CMP-PROCESSING-4310",
                "requested Processing Output classification differs from Test Data",
                "Use the exact upstream classification.",
            )
        if command.recommendation_sha256 is not None:
            suggestion = await self.recommend(
                context,
                decision,
                RecommendDmaFrequencyMasterCurve(command.test_data, command.import_profile),
            )
            if suggestion.recommendation_sha256 != command.recommendation_sha256:
                raise DmaProcessingError(
                    "CMP-PROCESSING-4310",
                    "recommendation digest does not match the exact inputs",
                    "Reload the recommendation or submit explicitly edited shift settings.",
                )

        loss_output: ProcessingOutputSnapshot | None = None
        if all(row.loss_modulus_pa is None for row in resolved.rows):
            loss_rows = derive_loss_modulus(resolved.rows)
            loss_output = await self._commit_output(
                context=context,
                decision=decision,
                classification=command.classification,
                label=f"{command.label} loss modulus",
                source_document=ExactRevisionPin(
                    command.test_data.document_id, command.test_data.revision_id
                ),
                source_document_sha256=command.test_data.content_sha256,
                source_canonical_artifact_sha256=snapshot.content.canonical_sha256,
                governed_import_profile=ExactRevisionPin(
                    command.import_profile.profile_id, command.import_profile.revision_id
                ),
                governed_import_profile_sha256=command.import_profile.content_sha256,
                step=ProcessingStep(
                    DMA_LOSS_MODULUS_METHOD_ID,
                    DMA_LOSS_MODULUS_METHOD_VERSION,
                    {
                        "formula": "loss_modulus_pa=storage_modulus_pa*tan_delta",
                        "source_normalized_artifact_id": str(
                            snapshot.content.normalized_artifact_id
                        ),
                        "source_normalized_artifact_sha256": snapshot.content.normalized_sha256,
                        "row_count": len(loss_rows),
                    },
                ),
                independent_quantity="physics.temperature",
                final_point_count=len(loss_rows),
                result_schema_ref=DMA_LOSS_MODULUS_PARQUET_SCHEMA_ID,
                result_bytes=loss_modulus_parquet_bytes(loss_rows),
                source_processing_output=None,
                source_processing_output_sha256=None,
                export_provenance=snapshot.content.governed_source,
                change_reason=command.change_reason,
            )

        master_rows = build_frequency_master_curve(
            resolved.rows,
            command.dispositions,
            command.shift_law,
            confirmed=command.confirmed,
            confirmation_reason=command.confirmation_reason,
        )
        master = await self._commit_output(
            context=context,
            decision=decision,
            classification=command.classification,
            label=command.label,
            source_document=ExactRevisionPin(
                command.test_data.document_id, command.test_data.revision_id
            ),
            source_document_sha256=command.test_data.content_sha256,
            source_canonical_artifact_sha256=snapshot.content.canonical_sha256,
            governed_import_profile=ExactRevisionPin(
                command.import_profile.profile_id, command.import_profile.revision_id
            ),
            governed_import_profile_sha256=command.import_profile.content_sha256,
            step=ProcessingStep(
                DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
                DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
                {
                    "shift_law": _shift_law_canonical(command.shift_law),
                    "frequency_conversion": "omega_rad_per_s=2*pi*frequency_hz",
                    "reduction": "omega_reduced=omega_rad_per_s*shift_factor",
                    "horizontal_shift_only": True,
                    "vertical_shift": False,
                    "interpolation": False,
                    "resampling": False,
                    "smoothing": False,
                    "dispositions": [
                        {
                            "source_ordinal": item.source_ordinal,
                            "partition": item.partition.value,
                            "exclusion_reason": item.exclusion_reason,
                        }
                        for item in command.dispositions
                    ],
                    "confirmation": {
                        "confirmed": command.confirmed,
                        "reason": command.confirmation_reason,
                    },
                    "recommendation_sha256": command.recommendation_sha256,
                    "source_normalized_artifact_id": str(snapshot.content.normalized_artifact_id),
                    "source_normalized_artifact_sha256": snapshot.content.normalized_sha256,
                    "row_count": len(master_rows),
                    "calibration_row_count": sum(
                        row.partition is DmaPartition.CALIBRATION for row in master_rows
                    ),
                    "holdout_row_count": sum(
                        row.partition is DmaPartition.HOLDOUT for row in master_rows
                    ),
                    "excluded_row_count": sum(
                        row.partition is DmaPartition.EXCLUDED for row in master_rows
                    ),
                    "tts_adequacy": "not_assessed",
                },
            ),
            independent_quantity="frequency.angular.reduced",
            final_point_count=len(master_rows),
            result_schema_ref=DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
            result_bytes=frequency_master_curve_parquet_bytes(master_rows),
            source_processing_output=(
                None
                if loss_output is None
                else ExactRevisionPin(loss_output.id, loss_output.current.revision_id)
            ),
            source_processing_output_sha256=(
                None if loss_output is None else loss_output.current.content_hash
            ),
            export_provenance=snapshot.content.governed_source,
            change_reason=command.change_reason,
        )
        return CreatedDmaFrequencyMasterCurve(loss_output, master)

    async def _commit_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        label: str,
        source_document: ExactRevisionPin,
        source_document_sha256: str,
        source_canonical_artifact_sha256: str,
        governed_import_profile: ExactRevisionPin,
        governed_import_profile_sha256: str,
        step: ProcessingStep,
        independent_quantity: str,
        final_point_count: int,
        result_schema_ref: str,
        result_bytes: bytes,
        source_processing_output: ExactRevisionPin | None,
        source_processing_output_sha256: str | None,
        export_provenance: GovernedTestDataSource | None,
        change_reason: str,
    ) -> ProcessingOutputSnapshot:
        output_id = self._id()
        result_artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="processing.dma-result-parquet",
            schema_ref=result_schema_ref,
            media_type=PARQUET_MEDIA_TYPE,
            value=result_bytes,
            idempotency_key=f"dma-processing-result:{output_id}",
        )
        result = result_artifact.artifact
        metadata_bytes = canonical_json_bytes(
            {
                "document_type": "cmp.processing-output",
                "document_version": PROCESSING_OUTPUT_SCHEMA_VERSION_1_6,
                "output_id": str(output_id),
                "source_document": {
                    "aggregate_id": str(source_document.aggregate_id),
                    "revision_id": str(source_document.revision_id),
                    "sha256": source_document_sha256,
                    "canonical_artifact_sha256": source_canonical_artifact_sha256,
                },
                "source_profile": {
                    "kind": "governed_import_profile",
                    "aggregate_id": str(governed_import_profile.aggregate_id),
                    "revision_id": str(governed_import_profile.revision_id),
                    "sha256": governed_import_profile_sha256,
                },
                "source_processing_output": None
                if source_processing_output is None
                else {
                    "aggregate_id": str(source_processing_output.aggregate_id),
                    "revision_id": str(source_processing_output.revision_id),
                    "sha256": source_processing_output_sha256,
                },
                "step": {
                    "method_id": step.method_id,
                    "method_version": step.method_version,
                    "options": step.options,
                },
                "result_artifact": {
                    "artifact_id": str(result.id),
                    "sha256": result.sha256,
                    "schema_ref": result.schema_ref,
                    "media_type": result.media_type,
                },
            }
        )

        def content(metadata_artifact: ArtifactRecord) -> ProcessingOutputContent:
            return ProcessingOutputContent(
                label=label,
                source_document=source_document,
                source_document_sha256=source_document_sha256,
                source_canonical_artifact_sha256=source_canonical_artifact_sha256,
                mapping_profile=None,
                mapping_profile_sha256=None,
                steps=(step,),
                independent_quantity=independent_quantity,
                stage_count=2,
                final_point_count=final_point_count,
                output_artifact_id=metadata_artifact.artifact.id,
                output_sha256=metadata_artifact.artifact.sha256,
                source_processing_output=source_processing_output,
                source_processing_output_sha256=source_processing_output_sha256,
                export_provenance=export_provenance,
                source_profile_kind="governed_import_profile",
                governed_import_profile=governed_import_profile,
                governed_import_profile_sha256=governed_import_profile_sha256,
                result_artifact_id=result.id,
                result_sha256=result.sha256,
                result_schema_ref=result.schema_ref,
                result_media_type=result.media_type,
            )

        atomic_writer = getattr(self._outputs, "commit_in_artifact_session", None)
        committed: dict[str, ProcessingOutputSnapshot] = {}
        commit_hook: ArtifactCommitHook | None = None
        if callable(atomic_writer):

            def persist(session: object, finalized: FinalizedArtifact) -> None:
                record = finalized.record
                committed["snapshot"] = atomic_writer(
                    session=session,
                    context=context,
                    decision=decision,
                    output_id=output_id,
                    classification=classification.value,
                    content=content(record),
                    change_reason=change_reason,
                    artifact_created_at=record.artifact.created_at,
                )

            commit_hook = persist
        metadata_artifact = await self._artifacts.finalize_derived_bytes(
            context,
            decision,
            classification=classification,
            artifact_role="processing.common-output-json",
            schema_ref=PROCESSING_OUTPUT_SCHEMA_ID_1_6,
            media_type=PROCESSING_OUTPUT_MEDIA_TYPE,
            value=metadata_bytes,
            idempotency_key=f"common-processing-output:{output_id}",
            **({"commit_hook": commit_hook} if commit_hook is not None else {}),
        )
        if "snapshot" in committed:
            return committed["snapshot"]
        output_content = content(metadata_artifact)
        record = RevisionService(
            aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
            store=self._outputs.output_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=output_id,
                scope=TenantScope(
                    context.organization_id,
                    context.project_id,
                    classification.value,
                ),
                schema_id=PROCESSING_OUTPUT_SCHEMA_ID_1_6,
                schema_version=PROCESSING_OUTPUT_SCHEMA_VERSION_1_6,
                content=output_content,
                created_by=context.principal.id,
                change_reason=change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return ProcessingOutputSnapshot(output_id, record, output_content)
