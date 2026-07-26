from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
from cmp.modules.datasets.application.service import (
    CalibrationDatasetSource,
    DatasetRevisionSnapshot,
    DatasetService,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevision,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    normalized_parquet_bytes,
)
from cmp.modules.identity_access.application.authorization import database_permissions_for
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
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
    ReferencePropertySource,
)
from cmp.modules.modeling.application.tabulated_plasticity import (
    CreateReferenceTabulatedPlasticityModel,
    PromoteProcessingOutputToTabulatedPlasticity,
    TabulatedPlasticityModelService,
    TabulatedPlasticityRepository,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    HardeningPointOrigin,
    InvalidTabulatedPlasticity,
    ReferenceIsotropicTabulatedPlasticityContent,
    TabulatedPlasticityConflict,
    hardening_curve_from_parquet,
    reference_isotropic_tabulated_plasticity_canonical,
)
from cmp.modules.modeling.domain.reference_linear_elasticity import ReferenceLinearElasticContent
from cmp.modules.modeling.domain.reference_processed_tabulated_plasticity import (
    ReferenceProcessedTabulatedPlasticityContent,
    reference_processed_tabulated_plasticity_canonical,
)
from cmp.modules.processing.application.common_batches import (
    CommonBatchService,
    ProcessingExecutionOrigin,
)
from cmp.modules.processing.application.common_outputs import (
    CommonProcessingOutputService,
    ExactRevisionPin,
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
    ProcessingOutputContent,
    ProcessingOutputSnapshot,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.shared.application.revisions import RevisionStore, RevisionTransaction
from cmp.shared.domain.revisions import (
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
)

NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)
ORG = UUID("e4000000-0000-4000-8000-000000000001")
PROJECT = UUID("e4000000-0000-4000-8000-000000000002")
ACTOR = UUID("e4000000-0000-4000-8000-000000000003")
STATE = UUID("e4000000-0000-4000-8000-000000000004")
PROPERTY_SET = UUID("e4000000-0000-4000-8000-000000000005")
PROPERTY_REVISION = UUID("e4000000-0000-4000-8000-000000000006")
DATASET = UUID("e4000000-0000-4000-8000-000000000007")
DATASET_REVISION = UUID("e4000000-0000-4000-8000-000000000008")
SOURCE_ARTIFACT = UUID("e4000000-0000-4000-8000-000000000009")
HARDENING_ARTIFACT = UUID("e4000000-0000-4000-8000-00000000000a")
MODEL = UUID("e4000000-0000-4000-8000-00000000000b")
PROCESSING_OUTPUT = UUID("e4000000-0000-4000-8000-000000000030")
PROCESSING_OUTPUT_REVISION = UUID("e4000000-0000-4000-8000-000000000031")
TEST_DOCUMENT = UUID("e4000000-0000-4000-8000-000000000032")
TEST_DOCUMENT_REVISION = UUID("e4000000-0000-4000-8000-000000000033")
MAPPING_PROFILE = UUID("e4000000-0000-4000-8000-000000000034")
MAPPING_PROFILE_REVISION = UUID("e4000000-0000-4000-8000-000000000035")
TRACE = "00-000000000000000000000000000000e4-00000000000000e4-01"

SOURCE_POINTS = (
    CurvePoint(0.0, 0.0),
    CurvePoint(0.001, 210_000_000.0),
    CurvePoint(0.002, 350_000_000.0),
    CurvePoint(0.004, 370_000_000.0),
    CurvePoint(0.02, 450_000_000.0),
    CurvePoint(0.10, 520_000_000.0),
    CurvePoint(0.15, 500_000_000.0),
)
SOURCE_BYTES = normalized_parquet_bytes(SOURCE_POINTS)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
WRITE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.MODELING_WRITE,
    roles=(Role.MATERIAL_MODELER,),
    database_permissions=database_permissions_for(Permission.MODELING_WRITE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _artifact(
    artifact_id: UUID,
    value: bytes,
    *,
    role: str,
    schema_ref: str,
) -> ArtifactRecord:
    digest = hashlib.sha256(value).hexdigest()
    return ArtifactRecord(
        Artifact(
            id=artifact_id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            artifact_kind=ArtifactKind.DERIVED,
            artifact_role=role,
            schema_ref=schema_ref,
            media_type="application/vnd.apache.parquet",
            size_bytes=len(value),
            sha256=digest,
            storage_key=content_object_key(
                ORG,
                PROJECT,
                DataClassification.INTERNAL,
                digest,
            ),
            encryption_profile="test",
            source_raw_asset_id=None,
            source_pending_id=uuid4(),
            created_at=NOW,
            created_by=ACTOR,
        ),
        IntegrityStatus.VERIFIED,
        NOW,
        uuid4(),
    )


SOURCE_RECORD = _artifact(
    SOURCE_ARTIFACT,
    SOURCE_BYTES,
    role="dataset.normalized_curve",
    schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
)


def _dataset_source() -> CalibrationDatasetSource:
    content = DatasetContent(
        test_run_id=UUID("e4000000-0000-4000-8000-000000000010"),
        test_run_revision_id=UUID("e4000000-0000-4000-8000-000000000011"),
        raw_asset_id=UUID("e4000000-0000-4000-8000-000000000012"),
        raw_artifact_id=UUID("e4000000-0000-4000-8000-000000000013"),
        data_artifact_id=SOURCE_ARTIFACT,
        data_sha256=SOURCE_RECORD.artifact.sha256,
        representation=DatasetRepresentation.NORMALIZED,
        source_dataset_revision_id=UUID("e4000000-0000-4000-8000-000000000014"),
        point_count=len(SOURCE_POINTS),
        mapping=ReferenceTensileMapping("strain", "stress", "1", "Pa"),
    )
    record = RevisionRecord(
        revision_id=DATASET_REVISION,
        aggregate_type="datasets.dataset",
        aggregate_id=DATASET,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=2,
        based_on_revision_id=content.source_dataset_revision_id,
        schema_id="urn:cmp:datasets:reference-uniaxial-tensile:1.0.0",
        schema_version="1.0.0",
        content_hash="b" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="normalize source curve",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )
    return CalibrationDatasetSource(
        DatasetRevisionSnapshot(DATASET, DatasetRevision(record, content)),
        STATE,
    )


class _MaterialModels:
    def __init__(self, material_class: str = "metal") -> None:
        self.material_class = material_class

    def get_reference_property_source_for_tabulated_plasticity(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        material_state_id: UUID,
        property_set_revision_id: UUID,
    ) -> ReferencePropertySource:
        assert context is CONTEXT and decision is WRITE
        assert material_state_id == STATE and property_set_revision_id == PROPERTY_REVISION
        return ReferencePropertySource(
            DataClassification.INTERNAL,
            self.material_class,
            ReferenceLinearElasticContent(
                material_id=UUID("e4000000-0000-4000-8000-000000000020"),
                material_revision_id=UUID("e4000000-0000-4000-8000-000000000021"),
                material_state_id=STATE,
                material_state_revision_id=UUID("e4000000-0000-4000-8000-000000000022"),
                property_set_id=PROPERTY_SET,
                property_set_revision_id=PROPERTY_REVISION,
                density_kg_per_m3=7_850.0,
                youngs_modulus_pa=210_000_000_000.0,
                poisson_ratio=0.3,
                source_yield_stress_pa=355_000_000.0,
            ),
        )


class _Datasets:
    def get_calibration_dataset_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> CalibrationDatasetSource:
        assert context is CONTEXT and decision is WRITE
        assert dataset_revision_id == DATASET_REVISION
        return _dataset_source()


class _ProcessingOutputs:
    def __init__(self) -> None:
        strains = [ordinal / 40 for ordinal in range(21)]
        stresses = [250_000_000.0 + ordinal * 5_000_000.0 for ordinal in range(21)]
        self.value = json.dumps(
            {
                "result": {
                    "stages": [
                        {
                            "method_id": "metal.hardening_fit_extrapolate",
                            "series": [
                                {
                                    "quantity": "strain.true_plastic",
                                    "unit": "1",
                                    "values": strains,
                                },
                                {
                                    "quantity": "stress.hardening.selected",
                                    "unit": "Pa",
                                    "values": stresses,
                                },
                            ],
                        }
                    ]
                }
            },
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(self.value).hexdigest()
        step = ProcessingStep(
            "metal.hardening_fit_extrapolate",
            "1.0.0",
            {
                "families": ["voce", "swift"],
                "fit_minimum_strain": 0.0001,
                "fit_maximum_strain": 0.1,
                "extrapolation_maximum_strain": 0.5,
                "primary_family": "swift",
                "secondary_family": "voce",
                "primary_weight": 0.5,
            },
        )
        content = ProcessingOutputContent(
            label="DP600 selected hardening",
            source_document=ExactRevisionPin(TEST_DOCUMENT, TEST_DOCUMENT_REVISION),
            source_document_sha256="3" * 64,
            source_canonical_artifact_sha256="4" * 64,
            mapping_profile=ExactRevisionPin(MAPPING_PROFILE, MAPPING_PROFILE_REVISION),
            mapping_profile_sha256="5" * 64,
            steps=(step,),
            independent_quantity="strain.true_plastic",
            stage_count=2,
            final_point_count=21,
            output_artifact_id=UUID("e4000000-0000-4000-8000-000000000036"),
            output_sha256=digest,
            fit_decision=FitDecisionSnapshot(
                candidate_key="swift+voce",
                mode="blend",
                primary_law="swift",
                secondary_law="voce",
                primary_weight=0.5,
                parameter_sets=(
                    FitDecisionParameterSet(
                        "swift",
                        (FitDecisionParameter("K", 500_000_000.0, "Pa"),),
                    ),
                    FitDecisionParameterSet(
                        "voce",
                        (FitDecisionParameter("Q", 300_000_000.0, "Pa"),),
                    ),
                ),
                fit_minimum=0.0001,
                fit_maximum=0.1,
                extrapolation_maximum=0.5,
                extrapolation_policy="bounded",
                metric_definition="relative_rmse",
                metric_value=0.01,
                requested_term_policy=None,
                actual_term_count=None,
                selection_reason="Select the tested bounded blend.",
                warning_acknowledged=True,
            ),
        )
        record = RevisionRecord(
            revision_id=PROCESSING_OUTPUT_REVISION,
            aggregate_type="processing.common_output",
            aggregate_id=PROCESSING_OUTPUT,
            scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
            revision_no=1,
            based_on_revision_id=None,
            schema_id="urn:cmp:processing:common-output:1.0.0",
            schema_version="1.0.0",
            content_hash="6" * 64,
            created_at=NOW,
            created_by=ACTOR,
            change_reason="save selected hardening",
            request_id=CONTEXT.request_id,
            trace_id=TRACE,
        )
        self.snapshot = ProcessingOutputSnapshot(PROCESSING_OUTPUT, record, content)

    async def export_exact(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        output_revision_id: UUID,
    ) -> tuple[ProcessingOutputSnapshot, bytes]:
        assert context is CONTEXT and decision is WRITE
        assert output_id == PROCESSING_OUTPUT
        assert output_revision_id == PROCESSING_OUTPUT_REVISION
        return self.snapshot, self.value


class _Artifacts:
    def __init__(self) -> None:
        self.hardening_bytes: bytes | None = None

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT and decision is WRITE
        assert artifact_id == SOURCE_ARTIFACT and maximum_bytes >= len(SOURCE_BYTES)
        return SOURCE_RECORD, SOURCE_BYTES

    async def finalize_derived_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        value: bytes,
        idempotency_key: str,
    ) -> ArtifactRecord:
        assert context is CONTEXT and decision is WRITE
        assert classification is DataClassification.INTERNAL
        assert artifact_role == "modeling.hardening_curve"
        assert media_type == "application/vnd.apache.parquet"
        assert idempotency_key.startswith(
            ("modeling-hardening:", "processed-tabulated-projection:")
        )
        self.hardening_bytes = value
        return _artifact(HARDENING_ARTIFACT, value, role=artifact_role, schema_ref=schema_ref)


class _Transaction(RevisionTransaction[ReferenceIsotropicTabulatedPlasticityContent]):
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def create(
        self, draft: RevisionDraft[ReferenceIsotropicTabulatedPlasticityContent]
    ) -> RevisionRecord:
        record = RevisionRecord(
            revision_id=draft.revision_id,
            aggregate_type=draft.aggregate_type,
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            revision_no=1,
            based_on_revision_id=None,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )
        self.repository.content = draft.content
        self.repository.record = record
        return record

    def revise(
        self,
        draft: RevisionDraft[ReferenceIsotropicTabulatedPlasticityContent],
        expected_current_revision_id: UUID,
    ) -> RevisionRecord:
        del draft, expected_current_revision_id
        raise AssertionError("this slice creates a new stable model identity")

    def stage(self, event: RevisionCreated) -> None:
        self.repository.event = event


class _Store(RevisionStore[ReferenceIsotropicTabulatedPlasticityContent]):
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def canonical_content(self, content: ReferenceIsotropicTabulatedPlasticityContent) -> object:
        if isinstance(content, ReferenceProcessedTabulatedPlasticityContent):
            return reference_processed_tabulated_plasticity_canonical(content)
        return reference_isotropic_tabulated_plasticity_canonical(content)

    def transaction(
        self,
    ) -> AbstractContextManager[RevisionTransaction[ReferenceIsotropicTabulatedPlasticityContent]]:
        return self._transaction()

    @contextmanager
    def _transaction(
        self,
    ) -> Iterator[RevisionTransaction[ReferenceIsotropicTabulatedPlasticityContent]]:
        yield _Transaction(self.repository)


class _Repository:
    def __init__(self) -> None:
        self.content: ReferenceIsotropicTabulatedPlasticityContent | None = None
        self.record: RevisionRecord | None = None
        self.event: RevisionCreated | None = None
        self.store = _Store(self)

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceIsotropicTabulatedPlasticityContent]:
        assert context is CONTEXT and decision is WRITE
        return self.store


def _service(
    repository: _Repository,
    artifacts: _Artifacts,
    *,
    material_class: str = "metal",
    processing_outputs: _ProcessingOutputs | None = None,
    processing_batches: object | None = None,
) -> TabulatedPlasticityModelService:
    return TabulatedPlasticityModelService(
        repository=cast(TabulatedPlasticityRepository, repository),
        material_models=cast(MaterialModelService, _MaterialModels(material_class)),
        datasets=cast(DatasetService, _Datasets()),
        artifacts=cast(ArtifactService, artifacts),
        processing_outputs=cast(CommonProcessingOutputService, processing_outputs),
        processing_batches=cast(CommonBatchService, processing_batches),
        id_factory=lambda: MODEL,
    )


def _command(*, acknowledge: bool = True) -> CreateReferenceTabulatedPlasticityModel:
    return CreateReferenceTabulatedPlasticityModel(
        material_state_id=STATE,
        property_set_revision_id=PROPERTY_REVISION,
        dataset_revision_id=DATASET_REVISION,
        extension_max_true_plastic_strain=0.25,
        acknowledge_post_necking_approximation=acknowledge,
        change_reason="derive explicit pre-necking reference hardening curve",
    )


def test_service_pins_sources_and_persists_the_explicit_hardening_artifact() -> None:
    repository = _Repository()
    artifacts = _Artifacts()

    snapshot = asyncio.run(_service(repository, artifacts).create_model(CONTEXT, WRITE, _command()))

    assert snapshot.id == MODEL
    assert snapshot.current.record.aggregate_type == MATERIAL_MODEL_AGGREGATE_TYPE
    content = snapshot.current.content
    assert content.property_set_revision_id == PROPERTY_REVISION
    assert content.source_dataset_id == DATASET
    assert content.source_dataset_revision_id == DATASET_REVISION
    assert content.hardening_curve_artifact_id == HARDENING_ARTIFACT
    assert content.necking_engineering_strain == pytest.approx(0.10)
    assert content.characterized_max_true_plastic_strain < 0.25
    assert content.extension_max_true_plastic_strain == 0.25
    assert content.post_necking_approximation_acknowledged is True
    assert artifacts.hardening_bytes is not None
    points = hardening_curve_from_parquet(artifacts.hardening_bytes)
    assert points[0].origin is HardeningPointOrigin.CATALOG_YIELD_ANCHOR
    assert points[-1].origin is HardeningPointOrigin.APPROVED_CONSTANT_EXTENSION
    assert points[-1].true_yield_stress_pa == points[-2].true_yield_stress_pa
    assert repository.event is not None


def test_service_rejects_unacknowledged_post_necking_extension_before_persistence() -> None:
    repository = _Repository()
    artifacts = _Artifacts()

    with pytest.raises(InvalidTabulatedPlasticity, match="explicitly acknowledged"):
        asyncio.run(
            _service(repository, artifacts).create_model(
                CONTEXT,
                WRITE,
                _command(acknowledge=False),
            )
        )

    assert repository.content is None
    assert artifacts.hardening_bytes is None


def test_service_rejects_nonmetal_material_before_reading_or_deriving_curve_data() -> None:
    repository = _Repository()
    artifacts = _Artifacts()

    with pytest.raises(
        TabulatedPlasticityConflict,
        match="requires a Material revision classified as metal",
    ):
        asyncio.run(
            _service(repository, artifacts, material_class="polymer").create_model(
                CONTEXT, WRITE, _command()
            )
        )

    assert repository.content is None
    assert artifacts.hardening_bytes is None


def test_service_promotes_exact_selected_hardening_output_without_refitting() -> None:
    repository = _Repository()
    artifacts = _Artifacts()
    outputs = _ProcessingOutputs()
    command = PromoteProcessingOutputToTabulatedPlasticity(
        material_state_id=STATE,
        property_set_revision_id=PROPERTY_REVISION,
        processing_output_id=PROCESSING_OUTPUT,
        processing_output_revision_id=PROCESSING_OUTPUT_REVISION,
        acknowledge_bounded_extrapolation=True,
        change_reason="promote exact selected hardening output",
    )

    snapshot = asyncio.run(
        _service(repository, artifacts, processing_outputs=outputs).promote_processing_output(
            CONTEXT, WRITE, command
        )
    )

    content = snapshot.current.content
    assert isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
    assert content.processing_output_revision_id == PROCESSING_OUTPUT_REVISION
    assert content.source_test_data_revision_id == TEST_DOCUMENT_REVISION
    assert content.mapping_profile_revision_id == MAPPING_PROFILE_REVISION
    assert content.primary_family == "swift"
    assert content.secondary_family == "voce"
    assert content.primary_weight == 0.5
    assert artifacts.hardening_bytes is not None
    points = hardening_curve_from_parquet(
        artifacts.hardening_bytes,
        transformation_profile_id=content.transformation_profile_id,
        transformation_profile_digest=content.transformation_profile_digest,
    )
    assert len(points) == 21
    assert all(point.origin is HardeningPointOrigin.PROCESSING_SELECTED_SAMPLE for point in points)
    assert points[-1].true_plastic_strain == 0.5


def test_service_preserves_saved_recipe_and_successful_batch_origin() -> None:
    class _Batches:
        def find_execution_origin(self, *args: object) -> ProcessingExecutionOrigin:
            del args
            return ProcessingExecutionOrigin(
                recipe_id=UUID(int=301),
                recipe_revision_id=UUID(int=302),
                recipe_sha256="3" * 64,
                batch_id=UUID(int=303),
                member_id=UUID(int=304),
                attempt_id=UUID(int=305),
                attempt_no=1,
            )

    repository = _Repository()
    command = PromoteProcessingOutputToTabulatedPlasticity(
        material_state_id=STATE,
        property_set_revision_id=PROPERTY_REVISION,
        processing_output_id=PROCESSING_OUTPUT,
        processing_output_revision_id=PROCESSING_OUTPUT_REVISION,
        acknowledge_bounded_extrapolation=True,
        change_reason="promote exact Recipe Batch hardening output",
    )

    snapshot = asyncio.run(
        _service(
            repository,
            _Artifacts(),
            processing_outputs=_ProcessingOutputs(),
            processing_batches=_Batches(),
        ).promote_processing_output(CONTEXT, WRITE, command)
    )

    content = snapshot.current.content
    assert isinstance(content, ReferenceProcessedTabulatedPlasticityContent)
    assert content.model_schema_version == "1.3.0"
    assert content.recipe_batch is not None
    assert content.recipe_batch.recipe_revision_id == UUID(int=302)
    assert content.recipe_batch.batch_attempt_id == UUID(int=305)
