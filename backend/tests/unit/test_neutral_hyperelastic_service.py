from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.exporting.adapters.api import neutral_hyperelastic_solver_cards as cards_api
from cmp.modules.exporting.application import neutral_hyperelastic_service as service_module
from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardService,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext

NEUTRAL_ID = UUID(int=1)
NEUTRAL_REVISION = UUID(int=2)
NEUTRAL_IR_REVISION = UUID(int=3)
UPSTREAM_IR_REVISION = UUID(int=4)
ACTOR = UUID(int=5)
NOW = datetime(2026, 8, 1, tzinfo=UTC)
CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Card service", True),
    organization_id=UUID(int=6),
    project_id=UUID(int=7),
    issuer="test",
    subject=str(ACTOR),
    token_id="token",
    groups=(),
    scopes=(),
    request_id=UUID(int=8),
    trace_id="card-service-test",
    authenticated_at=NOW,
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=CONTEXT.organization_id,
    project_id=CONTEXT.project_id,
    permission=Permission.EXPORT_EXECUTE,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=(Permission.EXPORT_EXECUTE.value,),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=CONTEXT.trace_id,
    decided_at=NOW,
)


class _NeutralMaterials:
    async def get_neutral_material_revision_for_export(self, *_: object) -> object:
        return SimpleNamespace(
            id=NEUTRAL_ID,
            current=SimpleNamespace(
                revision_id=NEUTRAL_REVISION,
                scope=SimpleNamespace(classification=DataClassification.INTERNAL.value),
            ),
            document=SimpleNamespace(
                material_model_ir=SimpleNamespace(
                    model=SimpleNamespace(revision_id=NEUTRAL_IR_REVISION)
                )
            ),
        )


class _Repository:
    def solver_card_store(self, **_: object) -> object:
        return object()


class _RevisionService:
    def __init__(self, **_: object) -> None:
        pass

    def create(self, draft: object) -> object:
        draft = cast(SimpleNamespace, draft)
        return SimpleNamespace(
            revision_id=UUID(int=10),
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            created_at=NOW,
        )


def _rendered_card(source_revision: UUID) -> SimpleNamespace:
    text = f"*MATERIAL\n# CMP material-model-revision {source_revision}\n"
    return SimpleNamespace(card_text=text, card_sha256=hashlib.sha256(text.encode()).hexdigest())


def _service(monkeypatch: pytest.MonkeyPatch) -> NeutralHyperelasticSolverCardService:
    monkeypatch.setattr(service_module, "RevisionService", _RevisionService)

    def build(**kwargs: object) -> tuple[object, object]:
        source_revision = cast(UUID, kwargs["source_material_model_ir_revision_id"])
        return SimpleNamespace(digest="r" * 64), _rendered_card(source_revision)

    monkeypatch.setattr(service_module, "build_neutral_solver_card", build)
    return NeutralHyperelasticSolverCardService(
        repository=cast(object, _Repository()),
        neutral_materials=cast(object, _NeutralMaterials()),
        id_factory=lambda: UUID(int=9),
    )


def _command(**overrides: object) -> CreateNeutralHyperelasticSolverCard:
    values: dict[str, object] = {
        "neutral_material_id": NEUTRAL_ID,
        "neutral_material_revision_id": NEUTRAL_REVISION,
        "target": NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
        "expected_mapping_report_sha256": "r" * 64,
        "solver_material_id": 1,
        "material_name": "REFERENCE",
        "change_reason": "persist exact card",
    }
    values.update(overrides)
    return CreateNeutralHyperelasticSolverCard(**values)  # type: ignore[arg-type]


def test_direct_card_service_defaults_to_neutral_embedded_ir_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(monkeypatch)
    snapshot, _ = asyncio.run(service.create_card(CONTEXT, DECISION, _command()))
    content = snapshot.current.content
    assert f"material-model-revision {NEUTRAL_IR_REVISION}" in content.card_text
    assert content.card_sha256 == hashlib.sha256(content.card_text.encode()).hexdigest()


def test_internal_delivery_override_changes_metal_card_bytes_and_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(monkeypatch)
    expected = _rendered_card(UPSTREAM_IR_REVISION)
    snapshot, _ = asyncio.run(
        service.create_card(
            CONTEXT,
            DECISION,
            _command(
                source_material_model_ir_revision_id=UPSTREAM_IR_REVISION,
                expected_card_sha256=expected.card_sha256,
            ),
        )
    )
    content = snapshot.current.content
    assert f"material-model-revision {UPSTREAM_IR_REVISION}" in content.card_text
    assert f"material-model-revision {NEUTRAL_IR_REVISION}" not in content.card_text
    assert content.card_sha256 == expected.card_sha256


def test_http_create_card_contract_cannot_supply_internal_source_override() -> None:
    assert "source_material_model_ir_revision_id" not in cards_api.CreateCardRequest.model_fields
    with pytest.raises(ValueError):
        cards_api.CreateCardRequest(
            neutral_material_revision_id=NEUTRAL_REVISION,
            target={"solver": "abaqus", "version": "2025", "unit_system": "kg_m_s"},
            expected_mapping_report_sha256="r" * 64,
            solver_material_id=1,
            material_name="REFERENCE",
            change_reason="persist exact card",
            source_material_model_ir_revision_id=str(UPSTREAM_IR_REVISION),
        )
