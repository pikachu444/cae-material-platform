from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.datasets.adapters.api.datasets import install_dataset_api
from cmp.modules.datasets.application.service import (
    DATASET_AGGREGATE_TYPE,
    CurvePreview,
    DatasetService,
    DatasetSnapshot,
    ImportReferenceTensileCsv,
)
from cmp.modules.datasets.application.service import (
    RevisionSnapshot as DatasetRevisionSnapshot,
)
from cmp.modules.datasets.domain.curve_metadata import (
    ArtifactPin,
    CurveMetadata,
    CurveSeries,
    MetadataState,
    RevisionPin,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetRepresentation,
    ReferenceTensileMapping,
    reference_tensile_curve_definition,
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
from cmp.modules.testing.adapters.api.testing import install_testing_api
from cmp.modules.testing.application.service import (
    SPECIMEN_AGGREGATE_TYPE,
    SPECIMEN_SOURCE_AGGREGATE_TYPE,
    TEST_METHOD_AGGREGATE_TYPE,
    TEST_RUN_AGGREGATE_TYPE,
    CreateReferenceMultiaxialTensionMethod,
    CreateReferenceTensileMethod,
    CreateReferenceTensileRun,
    CreateSpecimen,
    CreateSpecimenSource,
    ReviseSpecimenSource,
    SpecimenSnapshot,
    SpecimenSourceSnapshot,
)
from cmp.modules.testing.application.service import (
    RevisionSnapshot as RevisionView,
)
from cmp.modules.testing.application.service import (
    TestingService as ServicePort,
)
from cmp.modules.testing.application.service import (
    TestMethodSnapshot as MethodSnapshot,
)
from cmp.modules.testing.application.service import (
    TestRunSnapshot as RunSnapshot,
)
from cmp.modules.testing.domain.reference_tensile import (
    REFERENCE_TENSILE_METHOD_CODE,
    REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    ReferenceTensionMode,
    SpecimenContent,
)
from cmp.modules.testing.domain.reference_tensile import (
    TestMethodContent as MethodContent,
)
from cmp.modules.testing.domain.reference_tensile import (
    TestRunContent as RunContent,
)
from cmp.modules.testing.domain.specimen_source import (
    SpecimenSourceContent,
    SpecimenSourceLot,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 14, 14, 0, tzinfo=UTC)
ORG = UUID("f2000000-0000-4000-8000-000000000001")
PROJECT = UUID("f2000000-0000-4000-8000-000000000002")
ACTOR = UUID("f2000000-0000-4000-8000-000000000003")
MATERIAL = UUID("f2000000-0000-4000-8000-000000000004")
MATERIAL_REVISION = UUID("f2000000-0000-4000-8000-000000000005")
STATE = UUID("f2000000-0000-4000-8000-000000000006")
STATE_REVISION = UUID("f2000000-0000-4000-8000-000000000007")
SPECIMEN = UUID("f2000000-0000-4000-8000-000000000008")
SPECIMEN_REVISION = UUID("f2000000-0000-4000-8000-000000000009")
METHOD = UUID("f2000000-0000-4000-8000-00000000000a")
METHOD_REVISION = UUID("f2000000-0000-4000-8000-00000000000b")
RUN = UUID("f2000000-0000-4000-8000-00000000000c")
RUN_REVISION = UUID("f2000000-0000-4000-8000-00000000000d")
RAW_ASSET = UUID("f2000000-0000-4000-8000-00000000000e")
RAW_ARTIFACT = UUID("f2000000-0000-4000-8000-00000000000f")
DATASET = UUID("f2000000-0000-4000-8000-000000000010")
DATASET_RAW_REVISION = UUID("f2000000-0000-4000-8000-000000000011")
DATASET_NORMALIZED_REVISION = UUID("f2000000-0000-4000-8000-000000000012")
NORMALIZED_ARTIFACT = UUID("f2000000-0000-4000-8000-000000000013")
LOT = UUID("f2000000-0000-4000-8000-000000000014")
LOT_REVISION = UUID("f2000000-0000-4000-8000-000000000015")
SPECIMEN_SOURCE = UUID("f2000000-0000-4000-8000-000000000016")
SPECIMEN_SOURCE_REVISION = UUID("f2000000-0000-4000-8000-000000000017")
TRACE = "00-000000000000000000000000000000f2-00000000000000f2-01"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Test Engineer", True),
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


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


TESTING_READ = _decision(Permission.TESTING_READ)
TESTING_WRITE = _decision(Permission.TESTING_WRITE)
DATASET_READ = _decision(Permission.DATASET_READ)
DATASET_WRITE = _decision(Permission.DATASET_WRITE)


def _record(
    *,
    revision_id: UUID,
    aggregate_id: UUID,
    aggregate_type: str,
    revision_no: int = 1,
    based_on_revision_id: UUID | None = None,
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=TenantScope(ORG, PROJECT, DataClassification.INTERNAL.value),
        revision_no=revision_no,
        based_on_revision_id=based_on_revision_id,
        schema_id=f"urn:cmp:test:{aggregate_type}:1.0.0",
        schema_version="1.0.0",
        content_hash="f" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="reference workflow test",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


def _specimen() -> SpecimenSnapshot:
    content = SpecimenContent(
        MATERIAL,
        MATERIAL_REVISION,
        STATE,
        STATE_REVISION,
        "T-001",
        "rolling",
        "reference coupon",
    )
    return SpecimenSnapshot(
        SPECIMEN,
        STATE,
        RevisionView(
            _record(
                revision_id=SPECIMEN_REVISION,
                aggregate_id=SPECIMEN,
                aggregate_type=SPECIMEN_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _method() -> MethodSnapshot:
    content = MethodContent(
        REFERENCE_TENSILE_METHOD_CODE,
        REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    )
    return MethodSnapshot(
        METHOD,
        RevisionView(
            _record(
                revision_id=METHOD_REVISION,
                aggregate_id=METHOD,
                aggregate_type=TEST_METHOD_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _run() -> RunSnapshot:
    content = RunContent(
        SPECIMEN,
        SPECIMEN_REVISION,
        METHOD,
        METHOD_REVISION,
        "run-001",
        NOW,
        293.15,
        2.0,
    )
    return RunSnapshot(
        RUN,
        SPECIMEN,
        METHOD,
        RevisionView(
            _record(
                revision_id=RUN_REVISION,
                aggregate_id=RUN,
                aggregate_type=TEST_RUN_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _specimen_source() -> SpecimenSourceSnapshot:
    content = SpecimenSourceContent(
        specimen_id=SPECIMEN,
        specimen_revision_id=SPECIMEN_REVISION,
        sources=(SpecimenSourceLot(LOT, LOT_REVISION, "source heat"),),
    )
    return SpecimenSourceSnapshot(
        SPECIMEN_SOURCE,
        SPECIMEN,
        RevisionView(
            _record(
                revision_id=SPECIMEN_SOURCE_REVISION,
                aggregate_id=SPECIMEN_SOURCE,
                aggregate_type=SPECIMEN_SOURCE_AGGREGATE_TYPE,
            ),
            content,
        ),
    )


def _dataset() -> tuple[DatasetSnapshot, DatasetRevisionSnapshot[DatasetContent]]:
    mapping = ReferenceTensileMapping("strain_pct", "stress_mpa", "%", "MPa")
    raw_content = DatasetContent(
        RUN,
        RUN_REVISION,
        RAW_ASSET,
        RAW_ARTIFACT,
        RAW_ARTIFACT,
        "a" * 64,
        DatasetRepresentation.RAW,
        None,
        3,
        mapping,
    )
    raw = DatasetRevisionSnapshot(
        _record(
            revision_id=DATASET_RAW_REVISION,
            aggregate_id=DATASET,
            aggregate_type=DATASET_AGGREGATE_TYPE,
        ),
        raw_content,
    )
    normalized_content = DatasetContent(
        RUN,
        RUN_REVISION,
        RAW_ASSET,
        RAW_ARTIFACT,
        NORMALIZED_ARTIFACT,
        "b" * 64,
        DatasetRepresentation.NORMALIZED,
        DATASET_RAW_REVISION,
        3,
        mapping,
    )
    normalized = DatasetRevisionSnapshot(
        _record(
            revision_id=DATASET_NORMALIZED_REVISION,
            aggregate_id=DATASET,
            aggregate_type=DATASET_AGGREGATE_TYPE,
            revision_no=2,
            based_on_revision_id=DATASET_RAW_REVISION,
        ),
        normalized_content,
    )
    return DatasetSnapshot(DATASET, RUN, normalized), raw


class _TestingService:
    def __init__(self) -> None:
        self.specimen = _specimen()
        self.method = _method()
        self.run = _run()
        self.specimen_source: SpecimenSourceSnapshot | None = None

    def create_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateSpecimen,
    ) -> SpecimenSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.material_state_id == STATE
        assert command.material_state_revision_id == STATE_REVISION
        return self.specimen

    def list_specimens_for_material_state(
        self, context: SecurityContext, decision: AuthorizationDecision, material_state_id: UUID
    ) -> tuple[SpecimenSnapshot, ...]:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert material_state_id == STATE
        return (self.specimen,)

    def create_specimen_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateSpecimenSource,
    ) -> SpecimenSourceSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.content.specimen_revision_id == SPECIMEN_REVISION
        self.specimen_source = _specimen_source()
        return self.specimen_source

    def get_specimen_source_for_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSourceSnapshot | None:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert specimen_id == SPECIMEN
        return self.specimen_source

    def get_specimen_source_for_write(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_source_id: UUID,
    ) -> SpecimenSourceSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert specimen_source_id == SPECIMEN_SOURCE
        assert self.specimen_source is not None
        return self.specimen_source

    def revise_specimen_source(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_source_id: UUID,
        command: ReviseSpecimenSource,
    ) -> SpecimenSourceSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert specimen_source_id == SPECIMEN_SOURCE
        assert command.expected_current_revision_id == SPECIMEN_SOURCE_REVISION
        assert self.specimen_source is not None
        return self.specimen_source

    def create_reference_tensile_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileMethod,
    ) -> MethodSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.classification is DataClassification.INTERNAL
        return self.method

    def create_reference_multiaxial_tension_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceMultiaxialTensionMethod,
    ) -> MethodSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.test_mode is ReferenceTensionMode.PLANAR_TENSION
        return self.method

    def list_test_methods(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[MethodSnapshot, ...]:
        assert context is CONTEXT
        assert decision is TESTING_READ
        return (self.method,)

    def create_reference_tensile_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileRun,
    ) -> RunSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_WRITE
        assert command.specimen_revision_id == SPECIMEN_REVISION
        assert command.test_method_revision_id == METHOD_REVISION
        return self.run

    def get_test_run(
        self, context: SecurityContext, decision: AuthorizationDecision, test_run_id: UUID
    ) -> RunSnapshot:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert test_run_id == RUN
        return self.run

    def list_test_runs_for_material_state(
        self, context: SecurityContext, decision: AuthorizationDecision, material_state_id: UUID
    ) -> tuple[RunSnapshot, ...]:
        assert context is CONTEXT
        assert decision is TESTING_READ
        assert material_state_id == STATE
        return (self.run,)


class _DatasetService:
    def __init__(self) -> None:
        self.dataset, self.raw = _dataset()

    async def import_reference_tensile_csv(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportReferenceTensileCsv,
    ) -> DatasetSnapshot:
        assert context is CONTEXT
        assert decision is DATASET_WRITE
        assert command.test_run_id == RUN
        assert command.test_run_revision_id == RUN_REVISION
        assert command.raw_asset_id == RAW_ASSET
        assert command.raw_artifact_id == RAW_ARTIFACT
        return self.dataset

    def get_dataset(
        self, context: SecurityContext, decision: AuthorizationDecision, dataset_id: UUID
    ) -> DatasetSnapshot:
        assert context is CONTEXT
        assert decision is DATASET_READ
        assert dataset_id == DATASET
        return self.dataset

    def list_dataset_revisions(
        self, context: SecurityContext, decision: AuthorizationDecision, dataset_id: UUID
    ) -> tuple[DatasetRevisionSnapshot[DatasetContent], ...]:
        assert context is CONTEXT
        assert decision is DATASET_READ
        assert dataset_id == DATASET
        return (self.raw, self.dataset.current)

    def list_datasets_for_material_state(
        self, context: SecurityContext, decision: AuthorizationDecision, material_state_id: UUID
    ) -> tuple[DatasetSnapshot, ...]:
        assert context is CONTEXT
        assert decision is DATASET_READ
        assert material_state_id == STATE
        return (self.dataset,)

    async def preview_curve(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
        *,
        maximum_points: int,
    ) -> CurvePreview:
        assert context is CONTEXT
        assert decision is DATASET_READ
        assert dataset_revision_id == DATASET_NORMALIZED_REVISION
        assert maximum_points == 2
        definition = reference_tensile_curve_definition(
            self.dataset.current.content.mapping
        )
        series_preview = CurveSeries(
            definition=definition,
            channels={
                "engineering_strain": (0.0, 0.01, 0.02),
                "engineering_stress": (0.0, 100_000_000.0, 125_000_000.0),
            },
            deviations={},
            source_counts={},
        ).preview(maximum_points)
        return CurvePreview(
            dataset_id=DATASET,
            dataset_revision_id=DATASET_NORMALIZED_REVISION,
            representation=DatasetRepresentation.NORMALIZED,
            point_count=3,
            returned_point_count=2,
            sampled=True,
            strain_unit="1",
            stress_unit="Pa",
            points=(CurvePoint(0.0, 0.0), CurvePoint(0.02, 125_000_000.0)),
            curve_metadata=CurveMetadata(
                state=MetadataState.DECLARED,
                owning_revision=RevisionPin(
                    "dataset", DATASET, DATASET_NORMALIZED_REVISION
                ),
                artifact=ArtifactPin(
                    NORMALIZED_ARTIFACT,
                    "b" * 64,
                    REFERENCE_TENSILE_PARQUET_SCHEMA,
                    "application/vnd.apache.parquet",
                ),
                definition=definition,
            ),
            curve_series=series_preview,
        )


def _application() -> FastAPI:
    application = FastAPI()
    testing = _TestingService()
    datasets = _DatasetService()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def testing_read(request: Request) -> None:
        request.state.authorization_decision = TESTING_READ

    def testing_write(request: Request) -> None:
        request.state.authorization_decision = TESTING_WRITE

    def dataset_read(request: Request) -> None:
        request.state.authorization_decision = DATASET_READ

    def dataset_write(request: Request) -> None:
        request.state.authorization_decision = DATASET_WRITE

    install_testing_api(
        application,
        service=cast(ServicePort, testing),
        security_dependency=security,
        read_dependency=testing_read,
        write_dependency=testing_write,
    )
    install_dataset_api(
        application,
        service=cast(DatasetService, datasets),
        security_dependency=security,
        read_dependency=dataset_read,
        write_dependency=dataset_write,
    )
    return application


def _request(
    application: FastAPI,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict[str, object] | None = None,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=json)

    return asyncio.run(send())


def test_reference_tensile_api_creates_links_and_previews_immutable_dataset_revisions() -> None:
    application = _application()

    specimen = _request(
        application,
        "POST",
        f"/api/v1/material-states/{STATE}/specimens",
        json={
            "material_state_revision_id": str(STATE_REVISION),
            "specimen_code": "T-001",
            "orientation": "rolling",
            "preparation_note": "reference coupon",
            "change_reason": "register specimen",
        },
    )
    assert specimen.status_code == 201
    assert specimen.headers["ETag"] == '"revision:1:sha256:' + "f" * 64 + '"'
    assert specimen.json()["current_revision"]["content"]["material_state_revision_id"] == str(
        STATE_REVISION
    )

    methods = _request(
        application,
        "POST",
        "/api/v1/test-methods/reference-uniaxial-tensile",
        json={"classification": "internal", "change_reason": "register reference method"},
    )
    assert methods.status_code == 201
    assert methods.json()["current_revision"]["content"]["reference_only"] is True
    planar_method = _request(
        application,
        "POST",
        "/api/v1/test-methods/reference-multiaxial-tension",
        json={
            "classification": "internal",
            "test_mode": "planar_tension",
            "change_reason": "register exact planar reference method",
        },
    )
    assert planar_method.status_code == 201
    assert _request(application, "GET", "/api/v1/test-methods").json()["items"][0][
        "test_method_id"
    ] == str(METHOD)

    run = _request(
        application,
        "POST",
        "/api/v1/test-runs",
        json={
            "specimen_id": str(SPECIMEN),
            "specimen_revision_id": str(SPECIMEN_REVISION),
            "test_method_id": str(METHOD),
            "test_method_revision_id": str(METHOD_REVISION),
            "run_label": "run-001",
            "performed_at": NOW.isoformat(),
            "test_temperature_k": 293.15,
            "crosshead_speed_mm_per_min": 2.0,
            "change_reason": "register reference run",
        },
    )
    assert run.status_code == 201
    assert _request(application, "GET", f"/api/v1/test-runs/{RUN}").status_code == 200
    assert _request(application, "GET", f"/api/v1/material-states/{STATE}/test-runs").json()[
        "items"
    ][0]["test_run_id"] == str(RUN)

    imported = _request(
        application,
        "POST",
        "/api/v1/datasets/reference-uniaxial-tensile:import",
        json={
            "test_run_id": str(RUN),
            "test_run_revision_id": str(RUN_REVISION),
            "raw_asset_id": str(RAW_ASSET),
            "raw_artifact_id": str(RAW_ARTIFACT),
            "mapping": {
                "strain_column": "strain_pct",
                "stress_column": "stress_mpa",
                "strain_unit": "%",
                "stress_unit": "MPa",
            },
            "change_reason": "import reference curve",
        },
    )
    assert imported.status_code == 201
    assert imported.json()["current_revision"]["content"]["representation"] == "normalized"
    assert _request(application, "GET", f"/api/v1/datasets/{DATASET}").status_code == 200
    assert (
        len(
            _request(application, "GET", f"/api/v1/datasets/{DATASET}/revisions").json()[
                "revisions"
            ]
        )
        == 2
    )
    assert _request(application, "GET", f"/api/v1/material-states/{STATE}/datasets").json()[
        "items"
    ][0]["dataset_id"] == str(DATASET)

    curve = _request(
        application,
        "GET",
        f"/api/v1/dataset-revisions/{DATASET_NORMALIZED_REVISION}/curve?maximum_points=2",
    )
    assert curve.status_code == 200
    assert curve.json()["sampled"] is True
    assert curve.json()["stress_unit"] == "Pa"
    assert curve.json()["points"][-1]["engineering_stress"] == 125_000_000.0


def test_testing_api_pins_exact_specimen_source_lot_revision() -> None:
    application = _application()
    created = _request(
        application,
        "POST",
        f"/api/v1/specimens/{SPECIMEN}/source-genealogy",
        json={
            "content": {
                "specimen_revision_id": str(SPECIMEN_REVISION),
                "sources": [
                    {
                        "material_lot_id": str(LOT),
                        "material_lot_revision_id": str(LOT_REVISION),
                        "note": "source heat",
                    }
                ],
            },
            "change_reason": "pin source heat",
        },
    )

    assert created.status_code == 201, created.text
    content = created.json()["current_revision"]["content"]
    assert content["specimen_revision_id"] == str(SPECIMEN_REVISION)
    assert content["sources"][0]["material_lot_revision_id"] == str(LOT_REVISION)

    read_back = _request(application, "GET", f"/api/v1/specimens/{SPECIMEN}/source-genealogy")
    assert read_back.status_code == 200
    assert read_back.headers["ETag"] == created.headers["ETag"]

    missing_precondition = _request(
        application,
        "POST",
        f"/api/v1/specimen-source-genealogies/{SPECIMEN_SOURCE}/revisions",
        json={
            "content": {
                "specimen_revision_id": str(SPECIMEN_REVISION),
                "sources": [
                    {
                        "material_lot_id": str(LOT),
                        "material_lot_revision_id": str(LOT_REVISION),
                        "note": "source heat",
                    }
                ],
            },
            "change_reason": "missing optimistic concurrency evidence",
        },
    )
    assert missing_precondition.status_code == 422
    assert missing_precondition.json()["code"] == "CMP-TESTING-0002"

    stale_precondition = _request(
        application,
        "POST",
        f"/api/v1/specimen-source-genealogies/{SPECIMEN_SOURCE}/revisions",
        headers={"If-Match": f'"revision:1:sha256:{"0" * 64}"'},
        json={
            "content": {
                "specimen_revision_id": str(SPECIMEN_REVISION),
                "sources": [
                    {
                        "material_lot_id": str(LOT),
                        "material_lot_revision_id": str(LOT_REVISION),
                        "note": "source heat",
                    }
                ],
            },
            "change_reason": "stale optimistic concurrency evidence",
        },
    )
    assert stale_precondition.status_code == 412
    assert stale_precondition.json()["code"] == "CMP-TESTING-0004"
    assert stale_precondition.headers["ETag"] == created.headers["ETag"]

    revised = _request(
        application,
        "POST",
        f"/api/v1/specimen-source-genealogies/{SPECIMEN_SOURCE}/revisions",
        headers={"If-Match": created.headers["ETag"]},
        json={
            "content": {
                "specimen_revision_id": str(SPECIMEN_REVISION),
                "sources": [
                    {
                        "material_lot_id": str(LOT),
                        "material_lot_revision_id": str(LOT_REVISION),
                        "note": "source heat",
                    }
                ],
            },
            "change_reason": "confirm source heat",
        },
    )
    assert revised.status_code == 200
