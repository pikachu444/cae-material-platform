from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import httpx
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.api.neutral_material import install_neutral_material_api
from cmp.modules.modeling.application.neutral_material import (
    ImportNeutralMaterial,
    NeutralMaterialService,
    NeutralMaterialSnapshot,
    PromoteHyperelasticFamilyCandidate,
    PromoteLinearViscoelasticModelToNeutral,
    PromoteMetalModelToNeutral,
)
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    HYPERELASTIC_CURVE_STAGES,
    CurveStage,
    EvidenceStatus,
    NeutralCandidateSelection,
    NeutralCurve,
    NeutralDatasetRole,
    NeutralDatasetSource,
    NeutralHyperelasticIR,
    NeutralHyperelasticParameters,
    NeutralMaterialDocument,
    NeutralTestMode,
    OptionalRevisionEvidence,
    RevisionReference,
    neutral_material_from_json_bytes,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope
from fastapi import FastAPI, Request

NOW = datetime(2026, 7, 18, tzinfo=UTC)
IDS = tuple(UUID(int=value) for value in range(1, 32))
ORG, PROJECT, ACTOR, NEUTRAL, REVISION, CANDIDATE, ARTIFACT = IDS[:7]
TRACE = "00-000000000000000000000000000000d1-00000000000000d1-01"
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Modeler", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="https://idp.invalid",
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
        roles=(Role.MATERIAL_MODELER,),
        database_permissions=database_permissions_for(permission),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=CONTEXT.request_id,
        trace_id=TRACE,
        decided_at=NOW,
    )


def _ref(offset: int) -> RevisionReference:
    return RevisionReference(IDS[offset], IDS[offset + 1])


def _document() -> NeutralMaterialDocument:
    dataset = _ref(19)
    return NeutralMaterialDocument(
        document_id=NEUTRAL,
        organization_id=ORG,
        project_id=PROJECT,
        classification="internal",
        material=_ref(7),
        material_state=_ref(9),
        property_set=_ref(11),
        calibration_plan=_ref(13),
        scientific_profile=_ref(15),
        mapping_profile=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE, "Governed normalized Dataset was used directly."
        ),
        processing_recipe=OptionalRevisionEvidence(
            EvidenceStatus.NOT_APPLICABLE, "No recipe was used in this reference run."
        ),
        source_datasets=(
            NeutralDatasetSource(
                dataset,
                NeutralDatasetRole.CALIBRATION,
                NeutralTestMode.UNIAXIAL_TENSION,
                IDS[21],
                "a" * 64,
            ),
        ),
        curves=tuple(
            NeutralCurve(
                stage,
                dataset.revision_id,
                NeutralTestMode.UNIAXIAL_TENSION,
                "strain.engineering",
                "1",
                "stress.nominal.residual" if stage is CurveStage.RESIDUAL else "stress.nominal",
                "Pa",
                (0.0, 0.1),
                (0.0, 1000.0),
            )
            for stage in HYPERELASTIC_CURVE_STAGES
        ),
        selection=NeutralCandidateSelection(
            IDS[22],
            CANDIDATE,
            "b" * 64,
            IDS[23],
            "c" * 64,
            "Reviewed objective, residual, stability, and applicable range.",
            0.01,
            0.02,
            None,
            "monotonic_on_fitted_domain",
            ("no_holdout_data",),
        ),
        material_model_ir=NeutralHyperelasticIR(
            RevisionReference(NEUTRAL, REVISION),
            "urn:cmp:modeling:neutral-hyperelastic-ir:1.0.0",
            "1.0.0",
            "d" * 64,
            NeutralHyperelasticParameters(HyperelasticFamily.NEO_HOOKEAN, c10_pa=1_000_000.0),
            1100.0,
            "incompressible",
        ),
        applicable_strain_min=0.0,
        applicable_strain_max=0.1,
        validation_status="reference_numerical_checks_passed",
    )


DOCUMENT = _document()
SNAPSHOT = NeutralMaterialSnapshot(
    NEUTRAL,
    RevisionRecord(
        REVISION,
        "modeling.neutral_material",
        NEUTRAL,
        TenantScope(ORG, PROJECT, "internal"),
        1,
        None,
        "urn:cmp:modeling:neutral-hyperelastic-ir:1.0.0",
        "1.0.0",
        "e" * 64,
        NOW,
        ACTOR,
        "Promote reviewed family Candidate.",
        CONTEXT.request_id,
        TRACE,
    ),
    ARTIFACT,
    "f" * 64,
    DOCUMENT,
)


class _Service:
    async def promote_family_candidate(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteHyperelasticFamilyCandidate,
    ) -> NeutralMaterialSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert command.candidate_id == CANDIDATE
        return SNAPSHOT

    async def promote_metal_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteMetalModelToNeutral,
    ) -> NeutralMaterialSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert command.material_model_id == IDS[28]
        assert command.material_model_revision_id == IDS[29]
        return SNAPSHOT

    async def promote_linear_viscoelastic_model(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: PromoteLinearViscoelasticModelToNeutral,
    ) -> NeutralMaterialSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert command.material_model_id == IDS[28]
        assert command.material_model_revision_id == IDS[29]
        return SNAPSHOT

    async def get_neutral_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> NeutralMaterialSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_READ
        assert neutral_material_id == NEUTRAL
        return SNAPSHOT

    async def import_neutral_material(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: ImportNeutralMaterial,
    ) -> NeutralMaterialSnapshot:
        assert context is CONTEXT and decision.permission is Permission.MODELING_WRITE
        assert neutral_material_from_json_bytes(command.value) == DOCUMENT
        return SNAPSHOT

    @staticmethod
    def validate_json(value: bytes) -> NeutralMaterialDocument:
        return neutral_material_from_json_bytes(value)


def _app() -> FastAPI:
    app = FastAPI()

    def security(request: Request) -> None:
        request.state.security_context = CONTEXT

    def read(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_READ)

    def write(request: Request) -> None:
        request.state.authorization_decision = _decision(Permission.MODELING_WRITE)

    install_neutral_material_api(
        app,
        service=cast(NeutralMaterialService, _Service()),
        security_dependency=security,
        read_dependency=read,
        write_dependency=write,
    )
    return app


async def _exercise() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app()), base_url="http://test"
    ) as client:
        promoted = await client.post(
            "/api/v1/neutral-materials:promote",
            json={
                "candidate_id": str(CANDIDATE),
                "selection_reason": "Reviewed objective, residual, and stability evidence.",
                "change_reason": "Promote reviewed family Candidate.",
            },
        )
        assert promoted.status_code == 201
        assert promoted.headers["location"].endswith(str(NEUTRAL))
        assert promoted.json()["document"]["document_type"] == "cmp.neutral-material"

        for path in (
            "/api/v1/neutral-materials:promote-metal",
            "/api/v1/neutral-materials:promote-linear-viscoelastic",
        ):
            family_promoted = await client.post(
                path,
                json={
                    "material_model_id": str(IDS[28]),
                    "material_model_revision_id": str(IDS[29]),
                    "selection_reason": "Reviewed exact selected result evidence.",
                    "change_reason": "Promote typed model to Neutral Material.",
                },
            )
            assert family_promoted.status_code == 201
            assert family_promoted.headers["location"].endswith(str(NEUTRAL))

        loaded = await client.get(f"/api/v1/neutral-materials/{NEUTRAL}")
        assert loaded.status_code == 200
        assert (
            loaded.json()["document"]["material_model_ir"]["constitutive_model"]["family"]
            == "neo_hookean"
        )

        downloaded = await client.get(f"/api/v1/neutral-materials/{NEUTRAL}/download")
        assert downloaded.status_code == 200
        assert downloaded.content == DOCUMENT.to_json_bytes()
        assert downloaded.headers["content-disposition"].endswith(f'{NEUTRAL}.json"')

        validated = await client.post(
            "/api/v1/neutral-materials:validate", json=DOCUMENT.canonical()
        )
        assert validated.status_code == 200
        assert validated.json() == {
            "valid": True,
            "document_id": str(NEUTRAL),
            "content_sha256": DOCUMENT.content_sha256,
            "family": "neo_hookean",
            "source_dataset_count": 1,
            "curve_stage_count": 3,
        }

        imported = await client.post(
            "/api/v1/neutral-materials:import",
            json={
                "document": DOCUMENT.canonical(),
                "change_reason": "Import canonical Neutral Material JSON.",
            },
        )
        assert imported.status_code == 201
        assert imported.json()["neutral_material_revision_id"] == str(REVISION)

        tampered = DOCUMENT.canonical()
        candidate_selection = cast(dict[str, object], tampered["candidate_selection"])
        candidate_selection["reason"] = "Tampered reason"
        rejected = await client.post("/api/v1/neutral-materials:validate", json=tampered)
        assert rejected.status_code == 422


def test_neutral_material_api_promotes_validates_and_downloads_canonical_json() -> None:
    asyncio.run(_exercise())
