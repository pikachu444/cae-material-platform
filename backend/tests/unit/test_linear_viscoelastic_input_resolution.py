from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest
from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTabularTestDataSource,
    GovernedTestDataSource,
    canonical_json_bytes,
)
from cmp.modules.datasets.application.canonical_test_data import (
    TestDataDocumentContent as CanonicalDocumentContent,
)
from cmp.modules.datasets.application.governed_import import (
    ImportProfileRevisionSnapshot,
    ImportProfileSnapshot,
    RevisionSnapshot,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    CanonicalTestDataDocument,
    ChannelAxisRole,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestCondition as CanonicalCondition,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestDataChannel as CanonicalChannel,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestDataSource as CanonicalSource,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as CanonicalExecution,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as CanonicalMaterial,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as CanonicalSpecimen,
)
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedImportProfileContent,
    InvalidGovernedImport,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.modeling.application.linear_viscoelastic_input_resolution import (
    GovernedLinearViscoelasticInputResolver,
    ReadProcessedViscoelasticFitInput,
    ResolveGovernedViscoelasticInput,
    ResolveProcessedViscoelasticInput,
)
from cmp.modules.modeling.domain.linear_viscoelastic_calibration import (
    ChannelAvailability,
    DataAvailability,
    ExactRevisionPin,
    LinearViscoelasticInputError,
    PointDisposition,
    PointPartition,
)
from cmp.modules.processing.application.common_outputs import (
    ExactRevisionPin as ProcessingRevisionPin,
)
from cmp.modules.processing.application.common_outputs import (
    ProcessingOutputContent,
    ProcessingOutputSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
    DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
    DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
    DmaFrequencyMasterCurveRow,
    DmaPartition,
    frequency_master_curve_parquet_bytes,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

NOW = datetime(2026, 8, 28, tzinfo=UTC)
ORG = UUID(int=1)
PROJECT = UUID(int=2)
ACTOR = UUID(int=3)
TEST_DATA_ID = UUID(int=10)
TEST_DATA_REVISION_ID = UUID(int=11)
PROFILE_ID = UUID(int=12)
PROFILE_REVISION_ID = UUID(int=13)
SHA = "a" * 64
OUTPUT_ID = UUID(int=50)
OUTPUT_REVISION_ID = UUID(int=51)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Input resolver", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test.invalid",
        subject=str(ACTOR),
        token_id="input-resolution",
        groups=(),
        scopes=(),
        request_id=UUID(int=4),
        trace_id="00-00000000000000000000000000000001-0000000000000001-01",
        authenticated_at=NOW,
    )


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=tuple(sorted({Permission.DATASET_READ.value, permission.value})),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=UUID(int=4),
        trace_id="00-00000000000000000000000000000001-0000000000000001-01",
        decided_at=NOW,
    )


class _Authorization:
    def authorize(self, _context: SecurityContext, permission: Permission) -> AuthorizationDecision:
        return _decision(permission)


def _channel(
    key: str,
    semantics: str,
    role: ChannelAxisRole,
    original_unit: str,
    normalized_unit: str,
    values: tuple[str, ...],
) -> CanonicalChannel:
    decimals = tuple(Decimal(item) for item in values)
    scale = Decimal(1_000_000) if original_unit == "MPa" else Decimal(1)
    return CanonicalChannel(
        key=key,
        name=key,
        quantity_semantics=semantics,
        axis_role=role,
        original_unit_string=original_unit,
        normalized_unit=normalized_unit,
        normalization_scale=scale,
        normalization_offset=Decimal(0),
        original_values=tuple(item / scale for item in decimals),
        normalized_values=decimals,
        missing_reasons=tuple(None for _ in decimals),
    )


def _document(mode: str) -> CanonicalTestDataDocument:
    if mode == "relaxation":
        channels: tuple[CanonicalChannel, ...] = (
            _channel(
                "time",
                "time.elapsed",
                ChannelAxisRole.INDEPENDENT,
                "s",
                "s",
                ("0.1", "1", "10", "100"),
            ),
            _channel(
                "g",
                "mechanics.modulus.shear.relaxation",
                ChannelAxisRole.DEPENDENT,
                "MPa",
                "Pa",
                ("9000000", "7000000", "5000000", "4000000"),
            ),
        )
    else:
        channels = (
            _channel(
                "temperature",
                "physics.temperature",
                ChannelAxisRole.INDEPENDENT,
                "K",
                "K",
                ("298.15", "298.15", "298.15", "313.15", "313.15"),
            ),
            _channel(
                "frequency",
                "frequency.cyclic",
                ChannelAxisRole.INDEPENDENT,
                "Hz",
                "Hz",
                ("1", "10", "100", "1", "10"),
            ),
            _channel(
                "storage",
                "mechanics.modulus.storage",
                ChannelAxisRole.DEPENDENT,
                "MPa",
                "Pa",
                ("1", "2", "3", "4", "5"),
            ),
            _channel(
                "loss",
                "mechanics.modulus.loss",
                ChannelAxisRole.DEPENDENT,
                "MPa",
                "Pa",
                ("0.1", "0.2", "0.3", "0.4", "0.5"),
            ),
        )
    return CanonicalTestDataDocument(
        document_type="cmp.test-data",
        schema_version="1.0.0",
        document_id=f"governed-{mode}",
        material=CanonicalMaterial("CMP", "Synthetic", None),
        test=CanonicalExecution(date(2026, 8, 28), "engineer", "lab", mode, None, None),
        specimen=CanonicalSpecimen("specimen-1", None),
        conditions=(
            CanonicalCondition(
                "temperature",
                "physics.temperature",
                Decimal("298.15"),
                "K",
                Decimal("298.15"),
                "K",
            ),
            CanonicalCondition(
                "strain_amplitude",
                "mechanics.strain.shear",
                Decimal("0.01"),
                "1",
                Decimal("0.01"),
                "1",
            ),
        ),
        channels=channels,
        source=CanonicalSource("source.csv", "text/csv", SHA),
    )


def _profile(mode: str, *, deformation_mode: str | None = None) -> GovernedImportProfileContent:
    if mode == "relaxation":
        mappings: tuple[GovernedChannelMapping, ...] = (
            GovernedChannelMapping(0, "time", QuantityKind.TIME, "s", AxisRole.INDEPENDENT),
            GovernedChannelMapping(1, "g", QuantityKind.SHEAR_MODULUS, "MPa", AxisRole.DEPENDENT),
        )
        schema = TabularDataSchema.SHEAR_RELAXATION
        version = "1.1.0"
    else:
        mappings = (
            GovernedChannelMapping(
                0, "temperature", QuantityKind.TEMPERATURE, "K", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(
                1, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
            ),
            GovernedChannelMapping(2, "loss", QuantityKind.LOSS_MODULUS, "MPa", AxisRole.DEPENDENT),
        )
        schema = TabularDataSchema.DMA_TEMPERATURE_SWEEP
        version = "1.3.0"
    return GovernedImportProfileContent(
        profile_label=f"{mode} profile",
        data_schema=schema,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=mappings,
        schema_version=version,
        deformation_mode=deformation_mode,
    )


def _revision(aggregate_id: UUID, revision_id: UUID, aggregate_type: str) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id=f"urn:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash=SHA,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="test",
        request_id=UUID(int=4),
        trace_id="trace",
    )


def _snapshot(document: CanonicalTestDataDocument, *, governed: bool = True) -> object:
    tabular = GovernedTabularTestDataSource(
        raw_asset_id=UUID(int=20),
        raw_artifact_id=UUID(int=21),
        import_run_id=UUID(int=22),
        import_profile=ExactRevisionRef(PROFILE_ID, PROFILE_REVISION_ID),
        normalized_dataset=ExactRevisionRef(UUID(int=23), UUID(int=24)),
    )
    source = (
        GovernedTestDataSource(
            material=ExactRevisionRef(UUID(int=30), UUID(int=31)),
            material_state=ExactRevisionRef(UUID(int=32), UUID(int=33)),
            test_run=ExactRevisionRef(UUID(int=34), UUID(int=35)),
            tabular_import=tabular,
        )
        if governed
        else None
    )
    content = CanonicalDocumentContent(
        document_key=document.document_id,
        material=document.material,
        test=document.test,
        specimen=document.specimen,
        conditions=document.conditions,
        channels=(),
        source=document.source,
        canonical_artifact_id=UUID(int=40),
        canonical_sha256=SHA,
        normalized_artifact_id=UUID(int=41),
        normalized_sha256=SHA,
        point_count=document.point_count,
        governed_source=source,
    )
    return SimpleNamespace(
        id=TEST_DATA_ID,
        current=_revision(TEST_DATA_ID, TEST_DATA_REVISION_ID, "datasets.test_data_document"),
        content=content,
    )


def _resolver(
    document: CanonicalTestDataDocument,
    profile: GovernedImportProfileContent,
    *,
    governed: bool = True,
    current_test_data_revision_id: UUID = TEST_DATA_REVISION_ID,
    current_profile_revision_id: UUID = PROFILE_REVISION_ID,
) -> GovernedLinearViscoelasticInputResolver:
    snapshot = _snapshot(document, governed=governed)
    current_snapshot = _snapshot(document, governed=governed)
    current_snapshot.current = _revision(  # type: ignore[attr-defined]
        TEST_DATA_ID,
        current_test_data_revision_id,
        "datasets.test_data_document",
    )

    class TestData:
        async def export_document(self, *_args: object) -> tuple[object, bytes]:
            return snapshot, canonical_json_bytes(document)

        def list_documents(self, *_args: object) -> tuple[object, ...]:
            return (current_snapshot,)

    class Imports:
        def get_profile_revision_for_calibration(
            self, *_args: object
        ) -> ImportProfileRevisionSnapshot:
            record = _revision(PROFILE_ID, PROFILE_REVISION_ID, "datasets.import_profile")
            return ImportProfileRevisionSnapshot(
                PROFILE_ID,
                RevisionSnapshot(record, profile),
            )

        def get_profile(self, *_args: object) -> ImportProfileSnapshot:
            record = _revision(
                PROFILE_ID,
                current_profile_revision_id,
                "datasets.import_profile",
            )
            return ImportProfileSnapshot(
                PROFILE_ID,
                RevisionSnapshot(record, profile),
            )

    return GovernedLinearViscoelasticInputResolver(
        test_data=TestData(),  # type: ignore[arg-type]
        governed_imports=Imports(),  # type: ignore[arg-type]
        authorization=_Authorization(),  # type: ignore[arg-type]
    )


def test_upstream_current_revision_change_blocks_current_promotion_context() -> None:
    resolver = _resolver(
        _document("relaxation"),
        _profile("relaxation"),
        current_profile_revision_id=UUID(int=999),
    )

    with pytest.raises(LinearViscoelasticInputError) as error:
        resolver.assert_current_revisions(
            _context(),
            _decision(Permission.CALIBRATION_EXECUTE),
            test_data=ExactRevisionPin(TEST_DATA_ID, TEST_DATA_REVISION_ID, SHA),
            import_profile=ExactRevisionPin(PROFILE_ID, PROFILE_REVISION_ID, SHA),
        )

    assert error.value.code == "INPUT_UPSTREAM_STALE"
    assert f"pinned={PROFILE_REVISION_ID}" in str(error.value)
    assert "current=00000000-0000-0000-0000-0000000003e7" in str(error.value)
    assert "old exact model as history" in error.value.recovery_hint


def test_resolves_relaxation_source_pins_units_temperature_and_partitions() -> None:
    document = _document("relaxation")
    resolver = _resolver(document, _profile("relaxation"))
    result = asyncio.run(
        resolver.resolve(
            _context(),
            _decision(Permission.CALIBRATION_EXECUTE),
            ResolveGovernedViscoelasticInput(
                TEST_DATA_ID,
                TEST_DATA_REVISION_ID,
                298.15,
                tuple(PointDisposition(index, PointPartition.CALIBRATION) for index in range(4)),
                ChannelAvailability(),
            ),
        ),
    )

    assert result.test_data.revision_id == TEST_DATA_REVISION_ID
    assert result.canonical_artifact.media_type == "application/vnd.cmp.test-data+json"
    assert result.raw_source_sha256 == SHA
    assert result.semantics.mode == "relaxation"
    assert result.semantics.temperature_source == "condition"
    assert result.semantics.strain_amplitude == Decimal("0.01")
    assert result.semantics.channels[1].original_unit_string == "MPa"
    assert result.semantics.channels[1].normalized_unit == "Pa"


def test_dma_requires_shear_profile_and_explicit_isothermal_exclusions() -> None:
    document = _document("dma")
    resolver = _resolver(document, _profile("dma", deformation_mode="shear"))
    dispositions = (
        PointDisposition(0, PointPartition.CALIBRATION),
        PointDisposition(1, PointPartition.CALIBRATION),
        PointDisposition(2, PointPartition.CALIBRATION),
        PointDisposition(3, PointPartition.EXCLUDED, "different temperature"),
        PointDisposition(4, PointPartition.EXCLUDED, "different temperature"),
    )
    result = asyncio.run(
        resolver.resolve(
            _context(),
            _decision(Permission.CALIBRATION_EXECUTE),
            ResolveGovernedViscoelasticInput(
                TEST_DATA_ID,
                TEST_DATA_REVISION_ID,
                298.15,
                dispositions,
                ChannelAvailability(sweep=DataAvailability.PROVIDED),
            ),
        ),
    )

    assert result.semantics.mode == "dma"
    assert result.semantics.frequency_kind == "cyclic_hz"
    assert result.semantics.angular_frequency_conversion == "omega_rad_per_s=2*pi*frequency_hz"

    invalid = list(dispositions)
    invalid[3] = PointDisposition(3, PointPartition.HOLDOUT)
    with pytest.raises(LinearViscoelasticInputError, match="explicitly excluded"):
        asyncio.run(
            resolver.resolve(
                _context(),
                _decision(Permission.CALIBRATION_EXECUTE),
                ResolveGovernedViscoelasticInput(
                    TEST_DATA_ID,
                    TEST_DATA_REVISION_ID,
                    298.15,
                    tuple(invalid),
                    ChannelAvailability(sweep=DataAvailability.PROVIDED),
                ),
            ),
        )


def test_rejects_ungoverned_source_and_dma_without_shear_profile() -> None:
    document = _document("relaxation")
    ungoverned = _resolver(document, _profile("relaxation"), governed=False)
    command = ResolveGovernedViscoelasticInput(
        TEST_DATA_ID,
        TEST_DATA_REVISION_ID,
        298.15,
        tuple(PointDisposition(index, PointPartition.CALIBRATION) for index in range(4)),
        ChannelAvailability(),
    )
    with pytest.raises(LinearViscoelasticInputError, match="direct exact governed"):
        asyncio.run(
            ungoverned.resolve(_context(), _decision(Permission.CALIBRATION_EXECUTE), command)
        )

    with pytest.raises(InvalidGovernedImport, match="deformation_mode=shear"):
        _profile("dma", deformation_mode=None)


def test_resolves_exact_dma_master_curve_processing_output() -> None:
    document = CanonicalTestDataDocument(
        document_type="cmp.test-data",
        schema_version="1.0.0",
        document_id="governed-dma-temperature-sweep",
        material=CanonicalMaterial("CMP", "Synthetic", None),
        test=CanonicalExecution(
            date(2026, 8, 28), "engineer", "lab", "dma-temperature-sweep", None, None
        ),
        specimen=CanonicalSpecimen("specimen-1", None),
        conditions=(
            CanonicalCondition(
                "frequency",
                "frequency.cyclic",
                Decimal("1"),
                "Hz",
                Decimal("1"),
                "Hz",
            ),
        ),
        channels=(
            _channel(
                "temperature",
                "physics.temperature",
                ChannelAxisRole.INDEPENDENT,
                "K",
                "K",
                ("293.15", "303.15", "313.15", "323.15"),
            ),
            _channel(
                "storage",
                "mechanics.modulus.storage",
                ChannelAxisRole.DEPENDENT,
                "MPa",
                "Pa",
                ("3000000", "2800000", "2400000", "1900000"),
            ),
            _channel(
                "loss",
                "mechanics.modulus.loss",
                ChannelAxisRole.DEPENDENT,
                "MPa",
                "Pa",
                ("100000", "300000", "500000", "200000"),
            ),
        ),
        source=CanonicalSource("source.csv", "text/csv", SHA),
    )
    profile = GovernedImportProfileContent(
        profile_label="DMA temperature sweep",
        data_schema=TabularDataSchema.DMA_TEMPERATURE_SWEEP,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0, "temperature", QuantityKind.TEMPERATURE, "K", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(
                1, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
            ),
            GovernedChannelMapping(2, "loss", QuantityKind.LOSS_MODULUS, "MPa", AxisRole.DEPENDENT),
        ),
        schema_version="1.3.0",
        deformation_mode="shear",
    )
    source_snapshot = _snapshot(document)
    result_rows = tuple(
        DmaFrequencyMasterCurveRow(
            input_mode="fixed_frequency_temperature_sweep",
            source_sweep_ordinal=None,
            representative_temperature_k=293.15 + index * 10.0,
            partition=(DmaPartition.HOLDOUT if index == 3 else DmaPartition.CALIBRATION),
            is_reference=index == 2,
            exclusion_reason=None,
            holdout_evaluation_status=("not_applicable_no_curve_overlap" if index == 3 else None),
            source_ordinals=(index,),
            measured_temperature_k=(293.15 + index * 10.0,),
            source_frequency_hz=(1.0,),
            angular_frequency_rad_per_s=(6.283185307179586,),
            storage_modulus_pa=((3_000_000.0, 2_800_000.0, 2_400_000.0, 1_900_000.0)[index],),
            loss_modulus_pa=((100_000.0, 300_000.0, 500_000.0, 200_000.0)[index],),
            source_tan_delta=(None,),
            loss_modulus_origin=("measured",),
            reduced_angular_frequency_rad_per_s=(6.283185307179586 * 10.0 ** (2.0 - index),),
            raw_angular_frequency_min_rad_per_s=6.283185307179586,
            raw_angular_frequency_max_rad_per_s=6.283185307179586,
            shifted_angular_frequency_min_rad_per_s=(6.283185307179586 * 10.0 ** (2.0 - index)),
            shifted_angular_frequency_max_rad_per_s=(6.283185307179586 * 10.0 ** (2.0 - index)),
            comparison_sweep_ordinal=None,
            observed_log10_a_t=0.0 if index == 2 else None,
            applied_log10_a_t=2.0 - index,
            shift_factor=10.0 ** (2.0 - index),
            shift_residual_log10_a_t=0.0 if index == 2 else None,
            overlap_log10_reduced_angular_frequency_min=None,
            overlap_log10_reduced_angular_frequency_max=None,
            scoring_point_count=None,
            storage_mse=None,
            loss_mse=None,
            storage_rmse=None,
            loss_rmse=None,
            weighted_mse=None,
            adjacent_success=None,
            adjacent_status=None,
            adjacent_iterations=None,
            adjacent_evaluations=None,
            adjacent_objective=None,
        )
        for index in range(4)
    )
    result_bytes = frequency_master_curve_parquet_bytes(result_rows)
    result_sha = hashlib.sha256(result_bytes).hexdigest()
    step = ProcessingStep(
        DMA_FREQUENCY_MASTER_CURVE_METHOD_ID,
        DMA_FREQUENCY_MASTER_CURVE_METHOD_VERSION,
        {
            "input_mode": "fixed_frequency_temperature_sweep",
            "source_normalized_artifact_id": str(UUID(int=41)),
            "source_normalized_artifact_sha256": SHA,
            "result_row_count": 4,
            "frequency_conversion": "omega_rad_per_s=2*pi*frequency_hz",
            "shift_direction": "omega_reduced=omega*10**log10_a_t",
            "log_base": 10,
            "reference": {
                "source_sweep_ordinal": None,
                "source_ordinal": 2,
                "representative_temperature_k": 313.15,
            },
            "shift_law": {
                "kind": "manual_tabulated",
                "reference_temperature_k": 313.15,
                "parameter_source": "supplied",
                "manual_table": [
                    {"temperature_k": 293.15, "log10_a_t": 2.0},
                    {"temperature_k": 303.15, "log10_a_t": 1.0},
                    {"temperature_k": 313.15, "log10_a_t": 0.0},
                    {"temperature_k": 323.15, "log10_a_t": -1.0},
                ],
            },
            "scoring": None,
            "adjacent_optimizer": None,
            "law_optimizer": None,
            "residual_summary": None,
            "application_range": None,
            "assessment": {
                "adequacy": "not_assessed",
                "uncertainty": "not_provided",
                "identifiability": "not_assessed",
                "production_readiness": "non_production",
            },
            "warnings": [
                "DMA_TTS_LVR_EVIDENCE_MISSING",
                "DMA_TTS_TEMPERATURE_EQUILIBRIUM_EVIDENCE_MISSING",
                "DMA_TTS_PRECONDITIONING_EVIDENCE_MISSING",
            ],
        },
    )
    output = ProcessingOutputSnapshot(
        OUTPUT_ID,
        _revision(OUTPUT_ID, OUTPUT_REVISION_ID, "processing.common_output"),
        ProcessingOutputContent(
            label="DMA frequency master curve",
            source_document=ProcessingRevisionPin(TEST_DATA_ID, TEST_DATA_REVISION_ID),
            source_document_sha256=SHA,
            source_canonical_artifact_sha256=SHA,
            mapping_profile=None,
            mapping_profile_sha256=None,
            steps=(step,),
            independent_quantity="frequency.angular.reduced",
            stage_count=2,
            final_point_count=4,
            output_artifact_id=UUID(int=52),
            output_sha256="b" * 64,
            source_profile_kind="governed_import_profile",
            governed_import_profile=ProcessingRevisionPin(PROFILE_ID, PROFILE_REVISION_ID),
            governed_import_profile_sha256=SHA,
            result_artifact_id=UUID(int=53),
            result_sha256=result_sha,
            result_schema_ref=DMA_FREQUENCY_MASTER_CURVE_PARQUET_SCHEMA_ID,
            result_media_type="application/vnd.apache.parquet",
        ),
    )

    class TestData:
        async def export_document(self, *_args: object) -> tuple[object, bytes]:
            return source_snapshot, canonical_json_bytes(document)

        def list_documents(self, *_args: object) -> tuple[object, ...]:
            return (source_snapshot,)

    class Imports:
        def get_profile_revision_for_calibration(
            self, *_args: object
        ) -> ImportProfileRevisionSnapshot:
            return ImportProfileRevisionSnapshot(
                PROFILE_ID,
                RevisionSnapshot(
                    _revision(PROFILE_ID, PROFILE_REVISION_ID, "datasets.import_profile"),
                    profile,
                ),
            )

        def get_profile(self, *_args: object) -> ImportProfileSnapshot:
            return ImportProfileSnapshot(
                PROFILE_ID,
                RevisionSnapshot(
                    _revision(PROFILE_ID, PROFILE_REVISION_ID, "datasets.import_profile"),
                    profile,
                ),
            )

    class Outputs:
        async def export_exact_result(
            self, *_args: object, **_kwargs: object
        ) -> tuple[ProcessingOutputSnapshot, bytes]:
            return output, result_bytes

        def list_outputs(self, *_args: object) -> tuple[ProcessingOutputSnapshot, ...]:
            return (output,)

    resolver = GovernedLinearViscoelasticInputResolver(
        test_data=TestData(),  # type: ignore[arg-type]
        governed_imports=Imports(),  # type: ignore[arg-type]
        authorization=_Authorization(),  # type: ignore[arg-type]
        processing_outputs=Outputs(),  # type: ignore[arg-type]
    )
    resolved = asyncio.run(
        resolver.resolve_processing_output(
            _context(),
            _decision(Permission.CALIBRATION_EXECUTE),
            ResolveProcessedViscoelasticInput(
                OUTPUT_ID,
                OUTPUT_REVISION_ID,
                ChannelAvailability(sweep=DataAvailability.PROVIDED),
            ),
        )
    )

    assert resolved.processing_output == ExactRevisionPin(OUTPUT_ID, OUTPUT_REVISION_ID, SHA)
    assert resolved.processing_result_artifact is not None
    assert resolved.processing_result_artifact.sha256 == result_sha
    assert resolved.semantics.mode == "dma_frequency_master_curve"
    assert resolved.semantics.selected_temperature_k == Decimal("313.15")
    assert resolved.semantics.source_kind == "processing_output"
    assert len(resolved.semantics.point_dispositions) == 3
    assert all(
        item.partition is PointPartition.CALIBRATION
        for item in resolved.semantics.point_dispositions
    )
    fit_input = asyncio.run(
        resolver.read_processing_output_fit_input(
            _context(),
            _decision(Permission.MODELING_READ),
            ReadProcessedViscoelasticFitInput(OUTPUT_ID, OUTPUT_REVISION_ID),
        )
    )
    assert fit_input.mode == "dma_frequency_master_curve"
    assert fit_input.coordinate_quantity == "frequency.angular.reduced"
    assert fit_input.coordinate_unit == "rad/s"
    assert fit_input.reference_temperature_k == Decimal("313.15")
    assert [channel.channel for channel in fit_input.response_channels] == [
        "dma_storage",
        "dma_loss",
    ]
    first_source_row = next(item for item in fit_input.rows if item.source_ordinal == 0)
    reduced_frequencies = result_rows[0].reduced_angular_frequency_rad_per_s
    assert reduced_frequencies is not None
    assert first_source_row.coordinate == reduced_frequencies[0]
    assert first_source_row.storage_modulus_pa == result_rows[0].storage_modulus_pa[0]
    assert first_source_row.loss_modulus_pa == result_rows[0].loss_modulus_pa[0]
    assert fit_input.rows[-1].partition is PointPartition.CALIBRATION
    resolver.assert_current_revisions(
        _context(),
        _decision(Permission.CALIBRATION_EXECUTE),
        test_data=resolved.test_data,
        import_profile=resolved.import_profile,
        processing_output=resolved.processing_output,
    )
