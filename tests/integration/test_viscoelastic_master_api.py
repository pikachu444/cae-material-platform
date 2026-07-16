from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.datasets.adapters.api.viscoelastic_master import (
    install_viscoelastic_selection_api,
)
from cmp.modules.datasets.application.viscoelastic_master import (
    CreateViscoelasticSelection,
    ViscoelasticDatasetService,
    ViscoelasticSelectionSnapshot,
)
from cmp.modules.datasets.application.viscoelastic_master import (
    RevisionSnapshot as DatasetRevisionSnapshot,
)
from cmp.modules.datasets.domain.reference_shear_relaxation import ShearRelaxationPoint
from cmp.modules.datasets.domain.viscoelastic_master import (
    ViscoelasticSelectionContent,
    ViscoelasticSelectionMember,
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
from cmp.modules.processing.adapters.api.viscoelastic_master_curve import (
    install_viscoelastic_master_api,
)
from cmp.modules.processing.application.viscoelastic_master_curve import (
    VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
    CreateViscoelasticMasterPlan,
    ExecuteViscoelasticMasterPlan,
    RevisionSnapshot,
    ViscoelasticMasterPlanSnapshot,
    ViscoelasticMasterPreview,
    ViscoelasticMasterRun,
    ViscoelasticMasterService,
)
from cmp.modules.processing.domain.reference_tensile_crop import ProcessingRunStatus
from cmp.modules.processing.domain.viscoelastic_master_curve import (
    AlignedCurve,
    ManualShiftFactor,
    MasterCurvePoint,
    ShiftFactorEvidence,
    ShiftMethod,
    TemperatureStatistics,
    TemperatureStatisticsPoint,
    ViscoelasticMasterPlanContent,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
IDS = tuple(
    UUID(f"f2000000-0000-4000-8000-{index:012d}") for index in range(1, 30)
)
ORG, PROJECT, ACTOR = IDS[:3]
SELECTION, SELECTION_REVISION, PLAN, PLAN_REVISION, RUN = IDS[3:8]
TRACE = "00-000000000000000000000000000000f2-00000000000000f2-01"
SCOPE = TenantScope(ORG, PROJECT, "internal")
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Material Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://test.invalid",
    subject=str(ACTOR),
    token_id=str(uuid4()),
    groups=(),
    scopes=("openid",),
    request_id=uuid4(),
    trace_id=TRACE,
    authenticated_at=NOW,
)


def _decision(permission: Permission) -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=permission,
        roles=tuple(
            sorted(
                (Role.MATERIAL_MODELER, Role.DATA_STEWARD),
                key=lambda role: role.value,
            )
        ),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


DATASET_READ = _decision(Permission.DATASET_READ)
DATASET_WRITE = _decision(Permission.DATASET_WRITE)
PROCESSING_READ = _decision(Permission.PROCESSING_READ)
PROCESSING_EXECUTE = _decision(Permission.PROCESSING_EXECUTE)


def _record(
    aggregate_type: str, aggregate_id: UUID, revision_id: UUID, schema_id: str
) -> RevisionRecord:
    return RevisionRecord(
        revision_id=revision_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        scope=SCOPE,
        revision_no=1,
        based_on_revision_id=None,
        schema_id=schema_id,
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=NOW,
        created_by=ACTOR,
        change_reason="API fixture",
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
    )


MEMBERS = (
    ViscoelasticSelectionMember(0, IDS[8], IDS[9], IDS[10], IDS[11], 293.15),
    ViscoelasticSelectionMember(1, IDS[12], IDS[13], IDS[14], IDS[15], 313.15),
)
SELECTION_CONTENT = ViscoelasticSelectionContent(
    "Polymer replicate temperatures", IDS[16], IDS[17], MEMBERS
)
SELECTION_SNAPSHOT = ViscoelasticSelectionSnapshot(
    SELECTION,
    DatasetRevisionSnapshot(
        _record(
            "datasets.viscoelastic_selection",
            SELECTION,
            SELECTION_REVISION,
            "urn:cmp:datasets:viscoelastic-selection:1.0.0",
        ),
        SELECTION_CONTENT,
    ),
)
PLAN_CONTENT = ViscoelasticMasterPlanContent(
    plan_label="293 K master curve",
    selection_id=SELECTION,
    selection_revision_id=SELECTION_REVISION,
    reference_temperature_k=293.15,
    grid_point_count=31,
    shift_method=ShiftMethod.MANUAL,
    manual_shift_factors=(
        ManualShiftFactor(293.15, 0.0),
        ManualShiftFactor(313.15, -1.0),
    ),
)
PLAN_SNAPSHOT = ViscoelasticMasterPlanSnapshot(
    PLAN,
    RevisionSnapshot(
        _record(
            VISCOELASTIC_MASTER_PLAN_AGGREGATE_TYPE,
            PLAN,
            PLAN_REVISION,
            "urn:cmp:processing:viscoelastic-master-plan:1.0.0",
        ),
        PLAN_CONTENT,
    ),
)
FACTORS = (
    ShiftFactorEvidence(293.15, 0.0, "reference", None, None, None),
    ShiftFactorEvidence(313.15, -1.0, "manual", None, None, None),
)
RUN_VALUE = ViscoelasticMasterRun(
    id=RUN,
    scope=SCOPE,
    plan_id=PLAN,
    plan_revision_id=PLAN_REVISION,
    selection_id=SELECTION,
    selection_revision_id=SELECTION_REVISION,
    status=ProcessingRunStatus.SUCCEEDED,
    source_curve_count=2,
    temperature_count=2,
    aligned_row_count=6,
    statistics_row_count=6,
    master_row_count=3,
    aligned_dataset_id=IDS[18],
    aligned_dataset_revision_id=IDS[19],
    statistics_dataset_id=IDS[20],
    statistics_dataset_revision_id=IDS[21],
    master_dataset_id=IDS[22],
    master_dataset_revision_id=IDS[23],
    wlf_c1=None,
    wlf_c2_k=None,
    shift_factors=FACTORS,
    failure_code=None,
    change_reason="Commit master curve",
    started_at=NOW,
    ended_at=NOW,
    created_by=ACTOR,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
)


class _DatasetService:
    def create_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateViscoelasticSelection,
    ) -> ViscoelasticSelectionSnapshot:
        assert context is CONTEXT and decision is DATASET_WRITE
        assert len(command.members) == 2
        return SELECTION_SNAPSHOT

    def get_selection(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        selection_id: UUID,
    ) -> ViscoelasticSelectionSnapshot:
        assert context is CONTEXT and decision is DATASET_READ and selection_id == SELECTION
        return SELECTION_SNAPSHOT

    def list_selections(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[ViscoelasticSelectionSnapshot, ...]:
        assert context is CONTEXT and decision is DATASET_READ and material_state_id == IDS[16]
        return (SELECTION_SNAPSHOT,)


class _ProcessingService:
    def create_plan(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateViscoelasticMasterPlan,
    ) -> ViscoelasticMasterPlanSnapshot:
        assert context is CONTEXT and decision is PROCESSING_EXECUTE
        assert command.content.manual_shift_factors[1].log10_a_t == -1.0
        return PLAN_SNAPSHOT

    async def execute(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ExecuteViscoelasticMasterPlan,
    ) -> ViscoelasticMasterRun:
        assert context is CONTEXT and decision is PROCESSING_EXECUTE
        assert command.plan_revision_id == PLAN_REVISION
        return RUN_VALUE

    def get_run(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ViscoelasticMasterRun:
        assert context is CONTEXT and decision is PROCESSING_READ and run_id == RUN
        return RUN_VALUE

    async def preview(
        self, context: SecurityContext, decision: AuthorizationDecision, run_id: UUID
    ) -> ViscoelasticMasterPreview:
        assert context is CONTEXT and decision is PROCESSING_READ and run_id == RUN
        points = tuple(
            ShearRelaxationPoint(10.0**index, 10_000_000.0 - index * 1_000_000.0)
            for index in range(3)
        )
        aligned = tuple(
            AlignedCurve(
                item.ordinal,
                item.dataset_revision_id,
                item.test_run_revision_id,
                item.temperature_k,
                points,
            )
            for item in MEMBERS
        )
        statistics = tuple(
            TemperatureStatistics(
                item.temperature_k,
                1,
                tuple(
                    TemperatureStatisticsPoint(
                        point.time_s,
                        1,
                        point.shear_modulus_pa,
                        None,
                        point.shear_modulus_pa,
                        point.shear_modulus_pa,
                        point.shear_modulus_pa,
                    )
                    for point in points
                ),
            )
            for item in MEMBERS
        )
        master = tuple(
            MasterCurvePoint(
                point.time_s,
                2,
                point.shear_modulus_pa,
                100_000.0,
                point.shear_modulus_pa - 100_000.0,
                point.shear_modulus_pa + 100_000.0,
            )
            for point in points
        )
        return ViscoelasticMasterPreview(
            RUN_VALUE,
            SELECTION_SNAPSHOT.current,
            aligned,
            statistics,
            master,
        )


def _application() -> FastAPI:
    application = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def dataset_read(request: Request) -> None:
        request.state.authorization_decision = DATASET_READ

    def dataset_write(request: Request) -> None:
        request.state.authorization_decision = DATASET_WRITE

    def processing_read(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_READ

    def processing_execute(request: Request) -> None:
        request.state.authorization_decision = PROCESSING_EXECUTE

    install_viscoelastic_selection_api(
        application,
        service=cast(ViscoelasticDatasetService, _DatasetService()),
        security_dependency=security,
        read_dependency=dataset_read,
        write_dependency=dataset_write,
    )
    install_viscoelastic_master_api(
        application,
        service=cast(ViscoelasticMasterService, _ProcessingService()),
        security_dependency=security,
        read_dependency=processing_read,
        execute_dependency=processing_execute,
    )
    return application


def _request(method: str, path: str, body: dict[str, object] | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_application()), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)

    return asyncio.run(send())


def test_viscoelastic_master_api_preserves_selection_shift_and_output_evidence() -> None:
    selection = _request(
        "POST",
        "/api/v1/viscoelastic-selections",
        {
            "classification": "internal",
            "selection_label": "Polymer replicate temperatures",
            "members": [
                {
                    "dataset_id": str(item.dataset_id),
                    "dataset_revision_id": str(item.dataset_revision_id),
                }
                for item in MEMBERS
            ],
            "change_reason": "Pin exact temperature evidence",
        },
    )
    assert selection.status_code == 201
    assert selection.json()["content"]["temperature_count"] == 2
    assert selection.json()["content"]["members"][0]["outlier_status"] == "not_assessed"
    plan = _request(
        "POST",
        "/api/v1/processing-plans/viscoelastic-master-curve",
        {
            "classification": "internal",
            "plan_label": "293 K master curve",
            "selection_id": str(SELECTION),
            "selection_revision_id": str(SELECTION_REVISION),
            "reference_temperature_k": 293.15,
            "grid_point_count": 31,
            "shift_method": "manual",
            "manual_shift_factors": [
                {"temperature_k": 293.15, "log10_a_t": 0},
                {"temperature_k": 313.15, "log10_a_t": -1},
            ],
            "change_reason": "Define exact TTS policy",
        },
    )
    assert plan.status_code == 201
    run = _request(
        "POST",
        "/api/v1/processing-runs/viscoelastic-master-curve",
        {
            "plan_id": str(PLAN),
            "plan_revision_id": str(PLAN_REVISION),
            "change_reason": "Commit master curve",
        },
    )
    assert run.status_code == 201
    assert run.json()["master_dataset_revision_id"] == str(IDS[23])
    preview = _request(
        "GET", f"/api/v1/processing-runs/viscoelastic-master-curve/{RUN}/preview"
    )
    assert preview.status_code == 200
    assert preview.json()["policy"]["domain"] == "common_intersection_no_extrapolation"
    assert preview.json()["run"]["shift_factors"][1]["log10_a_t"] == -1.0
    assert len(preview.json()["aligned_curves"]) == 2
