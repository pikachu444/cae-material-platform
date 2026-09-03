from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from cmp.bootstrap.datasets import (
    SqlReferenceDatasetInputProvenanceHook,
    SqlReferenceDatasetSelectionProvenanceHook,
    SqlReferenceProcessedDatasetProvenanceHook,
)
from cmp.modules.artifacts.application.uploads import CompleteUpload, CreateUpload, RecordUploadPart
from cmp.modules.artifacts.domain.content import ArtifactNotFound, ArtifactRecord
from cmp.modules.audit.adapters.persistence.repository import SqlAlchemyRevisionAuditHook
from cmp.modules.catalog.application.service import CreateMaterial, CreateMaterialState
from cmp.modules.catalog.domain.model import MaterialClass, MaterialContent, MaterialStateContent
from cmp.modules.datasets.adapters.persistence.canonical_test_data import (
    SqlAlchemyCanonicalTestDataRepository,
)
from cmp.modules.datasets.adapters.persistence.repository import SqlAlchemyDatasetRepository
from cmp.modules.datasets.application.canonical_tabular_adapter import (
    CanonicalTabularAdapterInput,
    canonical_from_governed_tabular,
)
from cmp.modules.datasets.application.canonical_test_data import (
    CanonicalTestDataService,
    ExactRevisionRef,
    GovernedTabularTestDataSource,
    GovernedTestDataSource,
    ImportCanonicalTestData,
)
from cmp.modules.datasets.application.canonical_test_data import (
    TestDataDocumentSnapshot as _TestDataDocumentSnapshot,
)
from cmp.modules.datasets.application.governed_import import (
    CreateImportProfile,
    GovernedImportService,
    ImportProfileSnapshot,
)
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    DATASET_SCHEMA_ID,
    CreateReferenceDatasetSelection,
    DatasetService,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestCondition as _TestCondition,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestExecutionMetadata as _TestExecutionMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestMaterialMetadata as _TestMaterialMetadata,
)
from cmp.modules.datasets.domain.canonical_test_data import (
    TestSpecimenMetadata as _TestSpecimenMetadata,
)
from cmp.modules.datasets.domain.governed_tabular import (
    AxisRole,
    GovernedChannelMapping,
    GovernedImportProfileContent,
    QuantityKind,
    TabularDataSchema,
    TabularFileFormat,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    REFERENCE_TENSILE_SCHEMA_VERSION,
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
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.processing.adapters.persistence.common_outputs import (
    SqlAlchemyCommonProcessingOutputRepository,
)
from cmp.modules.processing.adapters.persistence.dma_provenance import (
    DMA_DERIVATION_KIND,
    DMA_DOMAIN_RUN_TYPE,
    DMA_METADATA_ARTIFACT_ROLE,
    DMA_METADATA_SCHEMA,
    DMA_OUTPUT_REVISION_TYPE,
    DMA_RESULT_ARTIFACT_ROLE,
    DMA_TEST_DATA_REVISION_TYPE,
    SqlAlchemyDmaProvenanceWriter,
    dma_submission_digest,
)
from cmp.modules.processing.adapters.persistence.repository import SqlAlchemyProcessingRepository
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_AGGREGATE_TYPE,
    ProcessingOutputSnapshot,
)
from cmp.modules.processing.application.dma_frequency_master_curve import (
    CreateDmaFrequencyMasterCurve,
    DmaFrequencyMasterCurveService,
    DmaImportProfilePin,
    DmaTestDataPin,
)
from cmp.modules.processing.application.service import (
    CreateReferenceTensileCropRecipe,
    ExecuteReferenceTensileCrop,
    ProcessingService,
)
from cmp.modules.processing.domain.dma_frequency_master_curve import (
    DmaPartition,
    DmaRowDisposition,
    WlfShiftLaw,
)
from cmp.modules.processing.domain.reference_tensile_crop import (
    ProcessingRunStatus,
    ReferenceTensileCropRecipeContent,
)
from cmp.modules.provenance.adapters.persistence.repository import SqlAlchemyRevisionProvenanceHook
from cmp.modules.provenance.domain.model import ActivityStatus
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.testing.application.service import (
    CreateReferenceTensileMethod,
    CreateReferenceTensileRun,
    CreateSpecimen,
)
from cmp.shared.adapters.persistence.revisions import SqlRevisionHook
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    ReviseAggregate,
    RevisionService,
)
from cmp.shared.domain.revisions import TenantScope
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_catalog_postgresql import PostgresHarness as CatalogHarness
from test_catalog_postgresql import postgres as _catalog_postgres_fixture

postgres = _catalog_postgres_fixture

POSTGRES_DSN = os.getenv("CMP_TEST_POSTGRES_DSN")

pytestmark = [
    pytest.mark.postgresql,
    pytest.mark.container_service,
    pytest.mark.skipif(
        POSTGRES_DSN is None,
        reason="CMP_TEST_POSTGRES_DSN is required for PostgreSQL integration",
    ),
]

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
ORG = UUID("c9000000-0000-4000-8000-000000000001")
PROJECT_A = UUID("c9000000-0000-4000-8000-000000000002")
PROJECT_B = UUID("c9000000-0000-4000-8000-000000000003")
ACTOR = UUID("c9000000-0000-4000-8000-000000000004")
SERVICE_ACTOR = UUID("c9000000-0000-4000-8000-000000000006")
OTHER_ORG = UUID("c9000000-0000-4000-8000-000000000007")


class _AcceptGovernedSource:
    def verify(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


class _StaticAuthorization:
    def authorize(self, context: SecurityContext, permission: Permission) -> AuthorizationDecision:
        return _decision(context, permission)


class _RecordingOutputRepository(SqlAlchemyCommonProcessingOutputRepository):
    def __init__(self, **kwargs: Any) -> None:
        self.commit_calls = 0
        super().__init__(**kwargs)

    def commit_in_artifact_session(self, *args: Any, **kwargs: Any) -> ProcessingOutputSnapshot:
        self.commit_calls += 1
        return super().commit_in_artifact_session(*args, **kwargs)


class _FailAfterOutputRevisionProvenance:
    def __call__(self, _session: Session, event_value: object) -> None:
        revision = getattr(event_value, "revision", None)
        if getattr(revision, "aggregate_type", None) == PROCESSING_OUTPUT_AGGREGATE_TYPE:
            raise RuntimeError("injected ordinary output revision provenance failure")


class _FailAfterDmaGraph:
    def __init__(self, writer: SqlAlchemyDmaProvenanceWriter) -> None:
        self.writer = writer

    def __call__(self, **kwargs: Any) -> None:
        self.writer(**kwargs)
        raise RuntimeError("injected DMA graph specialization failure")


class _FailImmediatelyBeforeAudit:
    after_output_specializer = True

    def __call__(self, _session: Session, _event: object) -> None:
        raise RuntimeError("injected failure immediately before audit append")


@dataclass(frozen=True, slots=True)
class DmaHarness:
    catalog: CatalogHarness
    test_data: CanonicalTestDataService
    governed_imports: GovernedImportService
    source: _TestDataDocumentSnapshot
    profile: ImportProfileSnapshot
    outputs: _RecordingOutputRepository
    writer: SqlAlchemyDmaProvenanceWriter


def _context(
    *,
    actor_id: UUID = ACTOR,
    principal_type: PrincipalType = PrincipalType.USER,
    organization_id: UUID = ORG,
    project_id: UUID = PROJECT_A,
) -> SecurityContext:
    return SecurityContext(
        principal=Principal(
            actor_id,
            principal_type,
            (
                "Issue 391 DMA service"
                if principal_type is PrincipalType.SERVICE
                else "T07 Catalog Steward"
            ),
            True,
        ),
        organization_id=organization_id,
        project_id=project_id,
        issuer="urn:cmp:test",
        subject=str(actor_id),
        token_id=f"issue391-{actor_id}",
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=f"00-{actor_id.hex[:32]}-{actor_id.hex[:16]}-01",
        authenticated_at=NOW,
    )


def _decision(
    context: SecurityContext,
    permission: Permission,
    *,
    max_classification: DataClassification = DataClassification.RESTRICTED,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        permission=permission,
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=max_classification,
        allow_export_controlled=False,
        request_id=context.request_id,
        trace_id=context.trace_id,
        decided_at=NOW,
    )


def _profile() -> GovernedImportProfileContent:
    return GovernedImportProfileContent(
        profile_label="Issue 391 fixed-frequency DMA temperature sweep",
        data_schema=TabularDataSchema.DMA_TEMPERATURE_SWEEP,
        file_format=TabularFileFormat.CSV,
        sheet_name=None,
        header_row=1,
        encoding="utf-8",
        delimiter=",",
        decimal_separator=".",
        channels=(
            GovernedChannelMapping(
                0, "temperature", QuantityKind.TEMPERATURE, "degC", AxisRole.INDEPENDENT
            ),
            GovernedChannelMapping(
                1, "storage", QuantityKind.STORAGE_MODULUS, "MPa", AxisRole.DEPENDENT
            ),
            GovernedChannelMapping(2, "tan_delta", QuantityKind.TAN_DELTA, "1", AxisRole.DEPENDENT),
        ),
        schema_version="1.3.0",
        deformation_mode="shear",
    )


def _source_document(profile: GovernedImportProfileContent) -> Any:
    frequency = _TestCondition(
        key="frequency",
        quantity_semantics="frequency.cyclic",
        original_value=Decimal("1.0"),
        original_unit_string="Hz",
        normalized_value=Decimal("1.0"),
        normalized_unit="Hz",
    )
    return canonical_from_governed_tabular(
        CanonicalTabularAdapterInput(
            document_id="ISSUE-391-DMA-SOURCE",
            material=_TestMaterialMetadata("Synthetic maker", "Issue 391 reference polymer"),
            test=_TestExecutionMetadata(
                test_date=datetime(2026, 9, 3, tzinfo=UTC).date(),
                operator="Issue 391 test operator",
                laboratory="Synthetic DMA laboratory",
                method="DMA fixed-frequency temperature sweep",
            ),
            specimen=_TestSpecimenMetadata("ISSUE-391-SPECIMEN"),
            conditions=(frequency,),
            source_file_name="issue391-dma.csv",
            source_bytes=(
                b"temperature,storage,tan_delta\n20,1.10,0.10\n40,0.90,0.20\n60,0.70,0.15\n"
            ),
            profile=profile,
        )
    )


def _output_repository(
    catalog: CatalogHarness,
    *extra_hooks: SqlRevisionHook,
) -> SqlAlchemyCommonProcessingOutputRepository:
    hooks: tuple[SqlRevisionHook, ...] = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        *extra_hooks,
        SqlAlchemyRevisionAuditHook(),
    )
    return SqlAlchemyCommonProcessingOutputRepository(
        session_factory=catalog.sessions,
        rls_context=catalog.rls,
        revision_hooks=hooks,
    )


def _dma_service(
    harness: DmaHarness,
    *,
    outputs: SqlAlchemyCommonProcessingOutputRepository | None = None,
    writer: Callable[..., None] | None = None,
    id_factory: Callable[[], UUID] = uuid4,
) -> DmaFrequencyMasterCurveService:
    return DmaFrequencyMasterCurveService(
        test_data=harness.test_data,
        governed_imports=harness.governed_imports,
        outputs=outputs or harness.outputs,
        artifacts=harness.catalog.artifacts,
        authorization=cast(Any, _StaticAuthorization()),
        id_factory=id_factory,
        dma_provenance_writer=writer or harness.writer,
    )


def _command(harness: DmaHarness, *, label: str) -> CreateDmaFrequencyMasterCurve:
    return CreateDmaFrequencyMasterCurve(
        input_mode="fixed_frequency_temperature_sweep",
        classification=DataClassification.RESTRICTED,
        label=label,
        test_data=DmaTestDataPin(
            harness.source.id,
            harness.source.current.revision_id,
            harness.source.current.content_hash,
        ),
        import_profile=DmaImportProfilePin(
            harness.profile.id,
            harness.profile.current.record.revision_id,
            harness.profile.current.record.content_hash,
        ),
        dispositions=tuple(
            DmaRowDisposition(ordinal, DmaPartition.CALIBRATION) for ordinal in range(3)
        ),
        shift_law=WlfShiftLaw(313.15, 17.44, 51.6),
        confirmed=True,
        confirmation_reason="Issue 391 integration acceptance fixture.",
        change_reason="Persist the issue 391 DMA output.",
    )


@pytest.fixture(scope="module")
def dma_postgres(request: pytest.FixtureRequest) -> Iterator[DmaHarness]:
    catalog_postgres = cast(CatalogHarness, request.getfixturevalue("postgres"))
    profile_context = _context()
    profile_decision = _decision(profile_context, Permission.DATASET_WRITE)
    with catalog_postgres.admin_engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO identity.principal "
                "(id, principal_type, display_name, active, created_at, updated_at) "
                "VALUES (:id, 'service', 'Issue 391 DMA Service', true, :now, :now)"
            ),
            {"id": SERVICE_ACTOR, "now": NOW},
        )

    hooks = (
        SqlInitialLifecycleHook(),
        SqlAlchemyRevisionProvenanceHook(),
        SqlAlchemyRevisionAuditHook(),
    )
    test_data = CanonicalTestDataService(
        repository=SqlAlchemyCanonicalTestDataRepository(
            session_factory=catalog_postgres.sessions,
            rls_context=catalog_postgres.rls,
            revision_hooks=hooks,
        ),
        artifacts=catalog_postgres.artifacts,
        governed_source_verifier=cast(Any, _AcceptGovernedSource()),
    )
    profile = catalog_postgres.governed_imports.create_profile(
        profile_context,
        profile_decision,
        CreateImportProfile(
            classification=DataClassification.RESTRICTED,
            content=_profile(),
            change_reason="Create the issue 391 integration Import Profile.",
        ),
    )
    profile_ref = ExactRevisionRef(profile.id, profile.current.record.revision_id)
    source_context = _context()
    source_decision = _decision(source_context, Permission.DATASET_WRITE)
    source = asyncio.run(
        test_data.import_document(
            source_context,
            source_decision,
            ImportCanonicalTestData(
                classification=DataClassification.RESTRICTED,
                document=_source_document(profile.current.content),
                governed_source=GovernedTestDataSource(
                    material=ExactRevisionRef(uuid4(), uuid4()),
                    material_state=ExactRevisionRef(uuid4(), uuid4()),
                    test_run=ExactRevisionRef(uuid4(), uuid4()),
                    tabular_import=GovernedTabularTestDataSource(
                        raw_asset_id=uuid4(),
                        raw_artifact_id=uuid4(),
                        import_run_id=uuid4(),
                        import_profile=profile_ref,
                        normalized_dataset=ExactRevisionRef(uuid4(), uuid4()),
                    ),
                ),
                change_reason="Import the issue 391 canonical DMA source.",
            ),
        )
    )
    outputs = _RecordingOutputRepository(
        session_factory=catalog_postgres.sessions,
        rls_context=catalog_postgres.rls,
        revision_hooks=hooks,
    )
    writer = SqlAlchemyDmaProvenanceWriter(
        session_factory=catalog_postgres.sessions,
        rls_context=catalog_postgres.rls,
    )
    yield DmaHarness(
        catalog=catalog_postgres,
        test_data=test_data,
        governed_imports=catalog_postgres.governed_imports,
        source=source,
        profile=profile,
        outputs=outputs,
        writer=writer,
    )


def _artifact_records(
    harness: DmaHarness,
    context: SecurityContext,
    snapshot: ProcessingOutputSnapshot,
) -> tuple[ArtifactRecord, ArtifactRecord]:
    decision = _decision(context, Permission.ARTIFACT_READ)
    metadata = harness.catalog.artifacts.get_artifact(
        context=context,
        decision=decision,
        artifact_id=snapshot.content.output_artifact_id,
    )
    result = harness.catalog.artifacts.get_artifact(
        context=context,
        decision=decision,
        artifact_id=cast(UUID, snapshot.content.result_artifact_id),
    )
    return metadata, result


def _assert_dma_graph(
    harness: DmaHarness,
    context: SecurityContext,
    snapshot: ProcessingOutputSnapshot,
) -> None:
    metadata, result = _artifact_records(harness, context, snapshot)
    assert snapshot.content.output_artifact_id == metadata.artifact.id
    assert snapshot.content.output_sha256 == metadata.artifact.sha256
    assert snapshot.content.result_artifact_id == result.artifact.id
    assert snapshot.content.result_sha256 == result.artifact.sha256
    assert metadata.artifact.artifact_role == DMA_METADATA_ARTIFACT_ROLE
    assert metadata.artifact.schema_ref == DMA_METADATA_SCHEMA
    assert result.artifact.artifact_role == DMA_RESULT_ARTIFACT_ROLE
    assert result.artifact.schema_ref == snapshot.content.result_schema_ref
    assert (
        hashlib.sha256(
            (
                asyncio.run(
                    harness.catalog.artifacts.read_verified_bytes(
                        context,
                        _decision(context, Permission.PROCESSING_EXECUTE),
                        metadata.artifact.id,
                        maximum_bytes=25 * 1024 * 1024,
                    )
                )
            )[1]
        ).hexdigest()
        == metadata.artifact.sha256
    )
    assert (
        hashlib.sha256(
            (
                asyncio.run(
                    harness.catalog.artifacts.read_verified_bytes(
                        context,
                        _decision(context, Permission.PROCESSING_EXECUTE),
                        result.artifact.id,
                        maximum_bytes=25 * 1024 * 1024,
                    )
                )
            )[1]
        ).hexdigest()
        == result.artifact.sha256
    )

    harness.writer.validate(
        context=context,
        decision=_decision(context, Permission.PROCESSING_EXECUTE),
        snapshot=snapshot,
        metadata_artifact=metadata,
        result_artifact=result,
    )
    params = {
        "organization_id": ORG,
        "project_id": PROJECT_A,
        "classification": DataClassification.RESTRICTED.value,
        "revision_id": snapshot.current.revision_id,
        "metadata_id": metadata.artifact.id,
        "result_id": result.artifact.id,
        "test_revision_id": harness.source.current.revision_id,
        "profile_revision_id": harness.profile.current.record.revision_id,
        "normalized_id": harness.source.content.normalized_artifact_id,
        "principal_id": context.principal.id,
    }
    with harness.catalog.admin_engine.connect() as connection:
        activities = (
            connection.execute(
                sa.text(
                    "SELECT id, activity_type, domain_run_type, domain_run_id, status, "
                    "submission_digest, recorded_by, request_id, trace_id "
                    "FROM provenance.activity "
                    "WHERE organization_id = :organization_id AND project_id = :project_id "
                    "AND classification = :classification AND domain_run_id = :revision_id"
                ),
                params,
            )
            .mappings()
            .all()
        )
        assert len(activities) == 1
        activity = activities[0]
        activity_id = cast(UUID, activity["id"])
        assert activity["activity_type"] == "processing.dma_frequency_master_curve"
        assert activity["domain_run_type"] == DMA_DOMAIN_RUN_TYPE
        assert activity["domain_run_id"] == snapshot.current.revision_id
        assert activity["status"] == ActivityStatus.SUCCEEDED.value
        assert activity["recorded_by"] == context.principal.id
        assert activity["request_id"] == context.request_id
        assert activity["trace_id"] == context.trace_id
        assert activity["submission_digest"] == dma_submission_digest(snapshot, metadata, result)

        usages = (
            connection.execute(
                sa.text(
                    "SELECT role, ordinal FROM provenance.usage WHERE activity_id = :activity_id "
                    "ORDER BY ordinal"
                ),
                {"activity_id": activity_id},
            )
            .mappings()
            .all()
        )
        assert [(row["role"], row["ordinal"]) for row in usages] == [
            ("source_test_data", 0),
            ("source_import_profile", 1),
            ("source_normalized_artifact", 2),
        ]

        generated = (
            connection.execute(
                sa.text(
                    "SELECT entity_id, role FROM provenance.generation "
                    "WHERE activity_id = :activity_id ORDER BY entity_id"
                ),
                {"activity_id": activity_id},
            )
            .mappings()
            .all()
        )
        output_entity_ids = {
            cast(UUID, row["entity_id"])
            for row in connection.execute(
                sa.text(
                    "SELECT id AS entity_id FROM provenance.entity "
                    "WHERE organization_id = :organization_id "
                    "AND project_id = :project_id AND classification = :classification "
                    "AND reference_id IN (:revision_id, :metadata_id, :result_id)"
                ),
                params,
            )
            .mappings()
            .all()
        }
        assert len(generated) == 3
        assert {row["role"] for row in generated} == {"primary"}
        assert {row["entity_id"] for row in generated} == output_entity_ids
        assert len(output_entity_ids) == 3

        entity_rows = (
            connection.execute(
                sa.text(
                    "SELECT id, entity_type, reference_kind, reference_type, reference_id, "
                    "content_sha256, generation_requirement "
                    "FROM provenance.entity WHERE organization_id = :organization_id "
                    "AND project_id = :project_id AND classification = :classification "
                    "AND reference_id IN (:test_revision_id, :profile_revision_id, :normalized_id, "
                    ":revision_id, :metadata_id, :result_id)"
                ),
                params,
            )
            .mappings()
            .all()
        )
        assert len(entity_rows) == 6
        expected_entities = {
            harness.source.current.revision_id: (
                DMA_TEST_DATA_REVISION_TYPE,
                "revision",
                harness.source.current.content_hash,
            ),
            harness.profile.current.record.revision_id: (
                "datasets.import_profile.revision",
                "revision",
                harness.profile.current.record.content_hash,
            ),
            harness.source.content.normalized_artifact_id: (
                "artifact.artifact",
                "artifact",
                harness.source.content.normalized_sha256,
            ),
            snapshot.current.revision_id: (
                DMA_OUTPUT_REVISION_TYPE,
                "revision",
                snapshot.current.content_hash,
            ),
            metadata.artifact.id: ("artifact.artifact", "artifact", metadata.artifact.sha256),
            result.artifact.id: ("artifact.artifact", "artifact", result.artifact.sha256),
        }
        for row in entity_rows:
            expected = expected_entities[cast(UUID, row["reference_id"])]
            assert (row["entity_type"], row["reference_kind"], row["content_sha256"]) == expected
            assert row["reference_type"] == expected[0]
            assert row["generation_requirement"] == "primary"

        associations = (
            connection.execute(
                sa.text(
                    "SELECT agent_id, role FROM provenance.association "
                    "WHERE activity_id = :activity_id"
                ),
                {"activity_id": activity_id},
            )
            .mappings()
            .all()
        )
        assert len(associations) == 1
        assert associations[0]["role"] == "author"
        agent = (
            connection.execute(
                sa.text(
                    "SELECT agent_type, reference_id FROM provenance.agent WHERE id = :agent_id"
                ),
                {"agent_id": associations[0]["agent_id"]},
            )
            .mappings()
            .one()
        )
        assert agent["agent_type"] == context.principal.principal_type.value
        assert agent["reference_id"] == context.principal.id

        attributions = (
            connection.execute(
                sa.text(
                    "SELECT entity_id, agent_id, role FROM provenance.attribution "
                    "WHERE entity_id IN (SELECT id FROM provenance.entity "
                    "WHERE organization_id = :organization_id AND project_id = :project_id "
                    "AND classification = :classification "
                    "AND reference_id IN (:revision_id, :metadata_id, :result_id))"
                ),
                params,
            )
            .mappings()
            .all()
        )
        assert len(attributions) == 3
        assert {row["role"] for row in attributions} == {"author"}
        assert {row["agent_id"] for row in attributions} == {associations[0]["agent_id"]}

        derivations = (
            connection.execute(
                sa.text(
                    "SELECT generated_entity_id, used_entity_id, derivation_kind "
                    "FROM provenance.derivation WHERE activity_id = :activity_id"
                ),
                {"activity_id": activity_id},
            )
            .mappings()
            .all()
        )
        assert len(derivations) == 9
        assert {row["derivation_kind"] for row in derivations} == {DMA_DERIVATION_KIND}
        assert {row["generated_entity_id"] for row in derivations} == output_entity_ids

        registrations = connection.execute(
            sa.text(
                "SELECT count(*) FROM provenance.activity "
                "WHERE activity_type = 'artifact.registration' "
                "AND domain_run_id IN (:metadata_id, :result_id)"
            ),
            params,
        ).scalar_one()
        assert registrations == 0

        audit_rows = (
            connection.execute(
                sa.text(
                    "SELECT actor_type, actor_id, action, target_type, target_id, outcome, "
                    "request_id, trace_id FROM audit.event "
                    "WHERE organization_id = :organization_id AND project_id = :project_id "
                    "AND target_type = 'processing.common_processing_output.revision' "
                    "AND target_id = :revision_id"
                ),
                params,
            )
            .mappings()
            .all()
        )
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit["actor_type"] == context.principal.principal_type.value
        assert audit["actor_id"] == context.principal.id
        assert audit["action"] == "processing.common_processing_output.revision.create"
        assert audit["outcome"] == "success"
        assert audit["request_id"] == context.request_id
        assert audit["trace_id"] == context.trace_id


@pytest.mark.parametrize(
    ("actor_id", "principal_type"),
    ((ACTOR, PrincipalType.USER), (SERVICE_ACTOR, PrincipalType.SERVICE)),
)
def test_dma_success_persists_the_complete_batch_graph_for_user_and_service(
    dma_postgres: DmaHarness,
    actor_id: UUID,
    principal_type: PrincipalType,
) -> None:
    context = _context(actor_id=actor_id, principal_type=principal_type)
    created = asyncio.run(
        _dma_service(dma_postgres).create(
            context,
            _decision(context, Permission.PROCESSING_EXECUTE),
            _command(dma_postgres, label=f"Issue 391 {principal_type.value} output {uuid4()}"),
        )
    )
    assert dma_postgres.outputs.commit_calls >= 1
    _assert_dma_graph(dma_postgres, context, created.master_curve_output)


def test_dma_rls_hides_exact_output_across_tenant_project_and_classification(
    dma_postgres: DmaHarness,
) -> None:
    context = _context()
    created = asyncio.run(
        _dma_service(dma_postgres).create(
            context,
            _decision(context, Permission.PROCESSING_EXECUTE),
            _command(dma_postgres, label=f"Issue 391 RLS output {uuid4()}"),
        )
    )
    metadata_id = created.master_curve_output.content.output_artifact_id

    wrong_project = _context(project_id=PROJECT_B)
    assert (
        dma_postgres.outputs.list_outputs(
            context=wrong_project,
            decision=_decision(wrong_project, Permission.PROCESSING_READ),
        )
        == ()
    )
    with pytest.raises(ArtifactNotFound):
        dma_postgres.catalog.artifacts.get_artifact(
            context=wrong_project,
            decision=_decision(wrong_project, Permission.ARTIFACT_READ),
            artifact_id=metadata_id,
        )

    wrong_tenant = _context(organization_id=OTHER_ORG)
    assert (
        dma_postgres.outputs.list_outputs(
            context=wrong_tenant,
            decision=_decision(wrong_tenant, Permission.PROCESSING_READ),
        )
        == ()
    )

    restricted_hidden = _decision(
        context,
        Permission.PROCESSING_READ,
        max_classification=DataClassification.INTERNAL,
    )
    assert dma_postgres.outputs.list_outputs(context=context, decision=restricted_hidden) == ()
    with pytest.raises(ArtifactNotFound):
        dma_postgres.catalog.artifacts.get_artifact(
            context=context,
            decision=_decision(
                context,
                Permission.ARTIFACT_READ,
                max_classification=DataClassification.INTERNAL,
            ),
            artifact_id=metadata_id,
        )


async def _single_upload_chunk(value: bytes) -> AsyncIterator[bytes]:
    yield value


def test_migration_107_preserves_existing_non_dma_processing_specializer(
    request: pytest.FixtureRequest,
) -> None:
    """Exercise the real Processing -> Dataset hook path after the DMA guard replacement."""
    postgres = cast(CatalogHarness, request.getfixturevalue("postgres"))

    context = _context()
    artifact_decision = _decision(context, Permission.ARTIFACT_WRITE)
    artifact_read = _decision(context, Permission.ARTIFACT_READ)
    catalog_decision = _decision(context, Permission.CATALOG_WRITE)
    dataset_decision = _decision(context, Permission.DATASET_WRITE)
    processing_decision = _decision(context, Permission.PROCESSING_EXECUTE)
    testing_read = _decision(context, Permission.TESTING_READ)
    testing_write = _decision(context, Permission.TESTING_WRITE)
    dataset_repository = SqlAlchemyDatasetRepository(
        session_factory=postgres.sessions,
        rls_context=postgres.rls,
        revision_hooks=(
            SqlInitialLifecycleHook(),
            SqlAlchemyRevisionProvenanceHook(),
            SqlReferenceDatasetInputProvenanceHook(),
            SqlReferenceDatasetSelectionProvenanceHook(),
            SqlReferenceProcessedDatasetProvenanceHook(),
            SqlAlchemyRevisionAuditHook(),
        ),
    )
    datasets = DatasetService(repository=dataset_repository, artifacts=postgres.artifacts)
    processing = ProcessingService(
        repository=SqlAlchemyProcessingRepository(
            session_factory=postgres.sessions,
            rls_context=postgres.rls,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
        ),
        datasets=datasets,
        testing=postgres.testing,
        artifacts=postgres.artifacts,
    )

    material = postgres.service.create_material(
        context,
        catalog_decision,
        CreateMaterial(
            DataClassification.RESTRICTED,
            MaterialContent(
                f"Issue 391 non-DMA material {uuid4().hex[:8]}",
                f"ISSUE-391-NONDMA-{uuid4().hex[:8]}",
                "synthetic non-production",
                material_class=MaterialClass.OTHER,
            ),
            "Create issue 391 non-DMA guard material.",
        ),
    )
    state = postgres.service.create_material_state(
        context,
        catalog_decision,
        CreateMaterialState(
            MaterialStateContent(
                material.id,
                material.current.record.revision_id,
                "Issue 391 non-DMA guard state",
            ),
            "Create issue 391 non-DMA guard state.",
        ),
    )
    specimen = postgres.testing.create_specimen(
        context,
        testing_write,
        CreateSpecimen(
            state.id,
            state.current.record.revision_id,
            f"ISSUE-391-NONDMA-{uuid4().hex[:8]}",
            None,
            "Synthetic non-production migration regression fixture.",
            "Create issue 391 non-DMA guard specimen.",
        ),
    )
    method = next(
        (
            item
            for item in postgres.testing.list_test_methods(context, testing_read)
            if item.current.content.method_code == "reference_uniaxial_tensile"
        ),
        None,
    )
    if method is None:
        method = postgres.testing.create_reference_tensile_method(
            context,
            testing_write,
            CreateReferenceTensileMethod(
                DataClassification.RESTRICTED,
                "Create issue 391 non-DMA guard tensile method.",
            ),
        )
    test_run = postgres.testing.create_reference_tensile_run(
        context,
        testing_write,
        CreateReferenceTensileRun(
            specimen.id,
            specimen.current.record.revision_id,
            method.id,
            method.current.record.revision_id,
            f"Issue 391 non-DMA guard run {uuid4().hex[:8]}",
            NOW,
            296.15,
            1.0,
            "Create issue 391 non-DMA guard tensile run.",
        ),
    )

    raw_value = b"issue-391-reference-tensile-source," + uuid4().bytes
    raw_upload = asyncio.run(
        postgres.uploads.create(
            context,
            artifact_decision,
            CreateUpload(
                classification=DataClassification.RESTRICTED,
                original_filename="issue391-reference.csv",
                media_type="text/csv",
                expected_size_bytes=len(raw_value),
                expected_sha256=hashlib.sha256(raw_value).hexdigest(),
                idempotency_key=f"issue391-nondma-upload-{uuid4()}",
            ),
        )
    )
    asyncio.run(
        postgres.uploads.record_part(
            context,
            artifact_decision,
            RecordUploadPart(raw_upload.session.id, 1, raw_upload.capability),
            _single_upload_chunk(raw_value),
        )
    )
    completion = asyncio.run(
        postgres.uploads.complete(
            context,
            artifact_decision,
            CompleteUpload(raw_upload.session.id, raw_upload.capability),
        )
    )
    assert completion.available_artifact_id is not None
    raw_artifact_id = completion.available_artifact_id
    raw_artifact = postgres.artifacts.get_artifact(
        context=context,
        decision=artifact_read,
        artifact_id=raw_artifact_id,
    )

    mapping = ReferenceTensileMapping("strain", "stress", "1", "Pa")
    normalized_value = normalized_parquet_bytes(
        (
            CurvePoint(0.0, 1.0),
            CurvePoint(0.01, 2.0),
            CurvePoint(0.02, 3.0),
            CurvePoint(0.03, 4.0),
        ),
        mapping,
    )
    normalized_artifact = asyncio.run(
        postgres.artifacts.finalize_derived_bytes(
            context,
            artifact_decision,
            classification=DataClassification.RESTRICTED,
            artifact_role="dataset.normalized_curve",
            schema_ref=REFERENCE_TENSILE_PARQUET_SCHEMA,
            media_type="application/vnd.apache.parquet",
            value=normalized_value,
            idempotency_key=f"issue391-nondma-normalized-{uuid4()}",
        )
    )
    scope = TenantScope(ORG, PROJECT_A, DataClassification.RESTRICTED.value)
    dataset_id = uuid4()
    raw_content = DatasetContent(
        test_run_id=test_run.id,
        test_run_revision_id=test_run.current.record.revision_id,
        raw_asset_id=completion.raw_asset.id,
        raw_artifact_id=raw_artifact_id,
        data_artifact_id=raw_artifact_id,
        data_sha256=raw_artifact.artifact.sha256,
        representation=DatasetRepresentation.RAW,
        source_dataset_revision_id=None,
        point_count=4,
        mapping=mapping,
    )
    revision_service = RevisionService(
        aggregate_type=DATASET_AGGREGATE_TYPE,
        store=dataset_repository.dataset_store(context, dataset_decision),
        clock=lambda: NOW,
    )
    raw_revision = revision_service.create(
        CreateRevisionedAggregate(
            aggregate_id=dataset_id,
            scope=scope,
            schema_id=DATASET_SCHEMA_ID,
            schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
            content=raw_content,
            created_by=context.principal.id,
            change_reason="Create issue 391 non-DMA guard source.",
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
    )
    normalized_content = DatasetContent(
        test_run_id=raw_content.test_run_id,
        test_run_revision_id=raw_content.test_run_revision_id,
        raw_asset_id=raw_content.raw_asset_id,
        raw_artifact_id=raw_content.raw_artifact_id,
        data_artifact_id=normalized_artifact.artifact.id,
        data_sha256=normalized_artifact.artifact.sha256,
        representation=DatasetRepresentation.NORMALIZED,
        source_dataset_revision_id=raw_revision.revision_id,
        point_count=4,
        mapping=mapping,
    )
    normalized_revision = revision_service.revise(
        ReviseAggregate(
            aggregate_id=dataset_id,
            scope=scope,
            expected_current_revision_id=raw_revision.revision_id,
            based_on_revision_id=raw_revision.revision_id,
            schema_id=DATASET_SCHEMA_ID,
            schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
            content=normalized_content,
            created_by=context.principal.id,
            change_reason="Normalize issue 391 non-DMA guard source.",
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
    )
    selection = datasets.create_reference_dataset_selection(
        context,
        dataset_decision,
        CreateReferenceDatasetSelection(
            classification=DataClassification.RESTRICTED,
            selection_label=f"Issue 391 non-DMA guard selection {uuid4()}",
            dataset_revision_id=normalized_revision.revision_id,
            change_reason="Pin issue 391 non-DMA guard source.",
        ),
    )
    recipe = processing.create_reference_tensile_crop_recipe(
        context,
        processing_decision,
        CreateReferenceTensileCropRecipe(
            classification=DataClassification.RESTRICTED,
            content=ReferenceTensileCropRecipeContent(
                "Issue 391 non-DMA guard crop",
                0.01,
                0.03,
            ),
            change_reason="Create issue 391 non-DMA guard recipe.",
        ),
    )
    run = asyncio.run(
        processing.execute_reference_tensile_crop(
            context,
            processing_decision,
            ExecuteReferenceTensileCrop(
                selection_id=selection.id,
                selection_revision_id=selection.current.record.revision_id,
                recipe_id=recipe.id,
                recipe_revision_id=recipe.current.record.revision_id,
                change_reason="Execute issue 391 non-DMA guard crop.",
            ),
        )
    )

    assert run.status is ProcessingRunStatus.SUCCEEDED
    with postgres.admin_engine.connect() as connection:
        activities = (
            connection.execute(
                sa.text(
                    "SELECT activity_type, domain_run_type, domain_run_id, input_required, "
                    "status, request_id, trace_id FROM provenance.activity "
                    "WHERE organization_id = :organization_id AND project_id = :project_id "
                    "AND classification = :classification "
                    "AND domain_run_id = :domain_run_id"
                ),
                {
                    "organization_id": ORG,
                    "project_id": PROJECT_A,
                    "classification": DataClassification.RESTRICTED.value,
                    "domain_run_id": run.id,
                },
            )
            .mappings()
            .all()
        )

    assert len(activities) == 1
    activity = activities[0]
    assert activity["activity_type"] == "processing.reference_tensile_crop"
    assert activity["domain_run_type"] == "processing.processing_run"
    assert activity["domain_run_id"] == run.id
    assert activity["input_required"] is True
    assert activity["status"] == ActivityStatus.SUCCEEDED.value
    assert activity["request_id"] == context.request_id
    assert activity["trace_id"] == context.trace_id


def _authoritative_counts(catalog: CatalogHarness) -> dict[str, int]:
    scoped = {
        "organization_id": ORG,
        "project_id": PROJECT_A,
        "classification": DataClassification.RESTRICTED.value,
    }
    scoped_tables = {
        "artifacts": "artifact.artifact",
        "artifact_integrity": "artifact.integrity_observation",
        "artifact_projection": "artifact.integrity_projection",
        "outputs": "processing.common_processing_output",
        "output_revisions": "processing.common_processing_output_revision",
        "output_steps": "processing.common_processing_output_step",
        "activities": "provenance.activity",
        "entities": "provenance.entity",
        "usages": "provenance.usage",
        "generations": "provenance.generation",
        "revisions": "provenance.revision",
        "derivations": "provenance.derivation",
        "associations": "provenance.association",
        "attributions": "provenance.attribution",
    }
    queries = {
        name: (
            f"SELECT count(*) FROM {table} "
            "WHERE organization_id = :organization_id "
            "AND project_id = :project_id AND classification = :classification"
        )
        for name, table in scoped_tables.items()
    }
    queries["audit"] = (
        "SELECT count(*) FROM audit.event "
        "WHERE organization_id = :organization_id AND project_id = :project_id"
    )
    with catalog.admin_engine.connect() as connection:
        return {
            name: int(connection.execute(sa.text(query), scoped).scalar_one())
            for name, query in queries.items()
        }


def test_dma_rollback_at_second_artifact_row_insert_leaves_no_authoritative_rows(
    dma_postgres: DmaHarness,
) -> None:
    context = _context()
    before = _authoritative_counts(dma_postgres.catalog)
    app_engine = cast(Engine, dma_postgres.catalog.sessions.kw["bind"])
    observed = {"artifact_inserts": 0}

    def fail_second_artifact_insert(
        _connection: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _execution_context: Any,
        _executemany: bool,
    ) -> None:
        normalized = " ".join(statement.lower().split())
        if "insert into artifact.artifact" in normalized or (
            'insert into "artifact"."artifact"' in normalized
        ):
            observed["artifact_inserts"] += 1
            if observed["artifact_inserts"] == 2:
                raise RuntimeError("injected second Artifact row failure")

    event.listen(app_engine, "before_cursor_execute", fail_second_artifact_insert)
    try:
        with pytest.raises(RuntimeError, match="injected second Artifact row failure"):
            asyncio.run(
                _dma_service(dma_postgres).create(
                    context,
                    _decision(context, Permission.PROCESSING_EXECUTE),
                    _command(dma_postgres, label=f"Issue 391 artifact rollback {uuid4()}"),
                )
            )
    finally:
        event.remove(app_engine, "before_cursor_execute", fail_second_artifact_insert)
    assert observed["artifact_inserts"] == 2
    assert _authoritative_counts(dma_postgres.catalog) == before


@pytest.mark.parametrize("failure", ("revision_provenance", "dma_graph", "before_audit"))
def test_dma_rollback_faults_leave_no_authoritative_output_or_graph_rows(
    dma_postgres: DmaHarness,
    failure: str,
) -> None:
    context = _context()
    before = _authoritative_counts(dma_postgres.catalog)
    real_writer = SqlAlchemyDmaProvenanceWriter(
        session_factory=dma_postgres.catalog.sessions,
        rls_context=dma_postgres.catalog.rls,
    )
    if failure == "revision_provenance":
        outputs = _output_repository(dma_postgres.catalog, _FailAfterOutputRevisionProvenance())
        writer: Callable[..., None] = real_writer
    elif failure == "dma_graph":
        outputs = _output_repository(dma_postgres.catalog)
        writer = _FailAfterDmaGraph(real_writer)
    else:
        outputs = _output_repository(dma_postgres.catalog, _FailImmediatelyBeforeAudit())
        writer = real_writer

    with pytest.raises(RuntimeError, match="injected"):
        asyncio.run(
            _dma_service(dma_postgres, outputs=outputs, writer=writer).create(
                context,
                _decision(context, Permission.PROCESSING_EXECUTE),
                _command(dma_postgres, label=f"Issue 391 {failure} rollback {uuid4()}"),
            )
        )

    assert _authoritative_counts(dma_postgres.catalog) == before
