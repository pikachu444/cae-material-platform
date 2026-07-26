from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from cmp.modules.exporting.adapters.integration.target_preview_source import (
    TargetPreviewSourceAdapter,
)
from cmp.modules.exporting.application import target_preview
from cmp.modules.exporting.application.target_preview import (
    CreateTargetPreview,
    ExactPreviewSource,
    TargetPreviewConflict,
    TargetPreviewService,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.application.neutral_material import (
    NeutralMaterialNotFound,
    NeutralMaterialService,
)
from cmp.modules.modeling.domain.neutral_material import (
    NeutralMaterialDocument,
    NeutralProcessingSelection,
    RevisionReference,
)
from cmp.modules.processing.application.common_outputs import (
    CommonPipelineError,
    CommonProcessingOutputService,
    ProcessingOutputNotFound,
)

IDS = [UUID(int=value) for value in range(1, 13)]


@dataclass(frozen=True)
class FakeReport:
    digest: str = "a" * 64
    exportable: bool = True

    @property
    def items(self) -> tuple[object, ...]:
        return (type("Mapping", (), {"status": "approximated"})(),)

    def canonical(self) -> dict[str, object]:
        return {"items": [{"status": "approximated", "name": "reference-only"}]}


@dataclass(frozen=True)
class FakeCard:
    card_text: str = "*MATERIAL\n*ELASTIC\n210000., .3\n"
    card_sha256: str = "c" * 64


@dataclass(frozen=True)
class FakeExactReport(FakeReport):
    @property
    def items(self) -> tuple[object, ...]:
        return (type("Mapping", (), {"status": "exact"})(),)


class Resolver:
    calls = 0
    solver_card_writes = 0
    artifact_writes = 0
    receipt_writes = 0
    activity_writes = 0

    async def resolve_for_target_preview(self, **_: object) -> ExactPreviewSource:
        self.calls += 1
        return ExactPreviewSource(
            processing_output_id=IDS[0],
            processing_output_revision_id=IDS[1],
            processing_output_sha256="b" * 64,
            material_id=IDS[2],
            material_revision_id=IDS[3],
            material_state_id=IDS[4],
            material_state_revision_id=IDS[5],
            material_model_ir_revision_id=IDS[6],
            neutral_material_id=IDS[7],
            neutral_material_revision_id=IDS[8],
            # Card generation is patched in this focused service test; source
            # resolution owns construction of the real immutable document.
            neutral=cast(NeutralMaterialDocument, None),
        )


def context_and_decision(
    permission: Permission = Permission.EXPORT_READ,
) -> tuple[SecurityContext, AuthorizationDecision]:
    context = SecurityContext(
        principal=Principal(
            id=IDS[9], principal_type=PrincipalType.USER, display_name="Preview", active=True
        ),
        organization_id=IDS[10],
        project_id=IDS[11],
        issuer="test",
        subject="preview",
        token_id="token",
        groups=(),
        scopes=(),
        request_id=IDS[0],
        trace_id="preview-test",
        authenticated_at=datetime.now(UTC),
    )
    return context, AuthorizationDecision(
        permission=permission,
        principal_id=context.principal.id,
        organization_id=context.organization_id,
        project_id=context.project_id,
        request_id=context.request_id,
        trace_id=context.trace_id,
        roles=(Role.TEST_ENGINEER,),
        database_permissions=(permission.value,),
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        decided_at=datetime.now(UTC),
    )


def test_preview_is_deterministic_and_has_no_persistence_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Resolver()
    monkeypatch.setattr(
        target_preview, "preflight_neutral_solver_export", lambda **_: FakeReport()
    )
    monkeypatch.setattr(
        target_preview, "build_neutral_solver_card", lambda **_: (FakeReport(), FakeCard())
    )
    service = TargetPreviewService(resolver=resolver)
    context, decision = context_and_decision()
    command = CreateTargetPreview(
        processing_output_id=IDS[0],
        processing_output_revision_id=IDS[1],
        neutral_material_id=IDS[7],
        neutral_material_revision_id=IDS[8],
        target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
        solver_material_id=101,
        material_name="ReferenceSteel",
    )
    first = asyncio.run(service.preview(context, decision, command))
    second = asyncio.run(service.preview(context, decision, command))
    assert first.preview_identity == second.preview_identity
    assert first.native_sha256 == second.native_sha256
    assert first.acknowledgement_identity == first.preview_identity
    assert first.delivery_status == "unavailable_pending_uxc_06c2"
    assert (
        resolver.calls == 2
    )  # resolver is read-only; service has no repository/artifact/card port
    assert (
        resolver.solver_card_writes,
        resolver.artifact_writes,
        resolver.receipt_writes,
        resolver.activity_writes,
    ) == (0, 0, 0, 0)


def test_preview_rejects_execute_decision_instead_of_escalating_preview_to_delivery() -> None:
    context, decision = context_and_decision(Permission.EXPORT_EXECUTE)
    command = CreateTargetPreview(
        processing_output_id=IDS[0],
        processing_output_revision_id=IDS[1],
        neutral_material_id=IDS[7],
        neutral_material_revision_id=IDS[8],
        target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
        solver_material_id=101,
        material_name="ReferenceSteel",
    )
    with pytest.raises(TargetPreviewConflict, match="authorization"):
        asyncio.run(TargetPreviewService(resolver=Resolver()).preview(context, decision, command))


def test_preview_blocks_unsupported_target_and_stale_mapping_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, decision = context_and_decision()
    command = CreateTargetPreview(
        processing_output_id=IDS[0],
        processing_output_revision_id=IDS[1],
        neutral_material_id=IDS[7],
        neutral_material_revision_id=IDS[8],
        target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
        solver_material_id=101,
        material_name="ReferenceSteel",
    )
    service = TargetPreviewService(resolver=Resolver())
    monkeypatch.setattr(
        target_preview, "preflight_neutral_solver_export", lambda **_: FakeReport(exportable=False)
    )
    with pytest.raises(TargetPreviewConflict, match="unsupported"):
        asyncio.run(service.preview(context, decision, command))

    monkeypatch.setattr(
        target_preview, "preflight_neutral_solver_export", lambda **_: FakeReport()
    )
    with pytest.raises(TargetPreviewConflict, match="acknowledgement is stale"):
        asyncio.run(
            service.preview(
                context,
                decision,
                replace(command, expected_mapping_report_sha256="f" * 64),
            )
        )


def test_preview_omits_acknowledgement_identity_when_mapping_has_no_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        target_preview, "preflight_neutral_solver_export", lambda **_: FakeExactReport()
    )
    monkeypatch.setattr(
        target_preview, "build_neutral_solver_card", lambda **_: (FakeExactReport(), FakeCard())
    )
    context, decision = context_and_decision()
    preview = asyncio.run(
        TargetPreviewService(resolver=Resolver()).preview(
            context,
            decision,
            CreateTargetPreview(
                processing_output_id=IDS[0],
                processing_output_revision_id=IDS[1],
                neutral_material_id=IDS[7],
                neutral_material_revision_id=IDS[8],
                target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
                solver_material_id=101,
                material_name="ReferenceSteel",
            ),
        )
    )

    assert preview.acknowledgement_identity is None


def _source_snapshots(
    *,
    proof: object | None = SimpleNamespace(
        material=SimpleNamespace(aggregate_id=IDS[2], revision_id=IDS[3]),
        material_state=SimpleNamespace(aggregate_id=IDS[4], revision_id=IDS[5]),
    ),
    selected_output_id: UUID = IDS[0],
    selected_output_revision_id: UUID = IDS[1],
    selected_output_sha256: str = "b" * 64,
    ir_revision_id: UUID = IDS[8],
    neutral_material_id: UUID = IDS[2],
    neutral_material_revision_id: UUID = IDS[3],
    neutral_material_state_id: UUID = IDS[4],
    neutral_material_state_revision_id: UUID = IDS[5],
) -> tuple[object, object]:
    output = SimpleNamespace(
        id=IDS[0],
        current=SimpleNamespace(revision_id=IDS[1]),
        content=SimpleNamespace(export_provenance=proof, output_sha256="b" * 64),
    )
    selection = NeutralProcessingSelection(
        processing_output=RevisionReference(selected_output_id, selected_output_revision_id),
        processing_output_sha256=selected_output_sha256,
        reason="Use the exact governed Processing Output.",
        selected_series="hardening",
        candidate_families=("swift", "voce"),
        primary_family="swift",
        secondary_family=None,
        primary_weight=None,
    )
    neutral = SimpleNamespace(
        id=IDS[7],
        current=SimpleNamespace(revision_id=IDS[8]),
        document=SimpleNamespace(
            selection=selection,
            material=RevisionReference(neutral_material_id, neutral_material_revision_id),
            material_state=RevisionReference(
                neutral_material_state_id, neutral_material_state_revision_id
            ),
            material_model_ir=SimpleNamespace(
                model=SimpleNamespace(object_id=IDS[7], revision_id=ir_revision_id)
            ),
        ),
    )
    return output, neutral


class _Outputs:
    def __init__(self, snapshot: object | Exception) -> None:
        self.snapshot = snapshot

    def get_output_revision_for_export(self, *_: object) -> object:
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot


class _NeutralMaterials:
    def __init__(self, snapshot: object | Exception) -> None:
        self.snapshot = snapshot

    async def get_neutral_material_revision_for_export(self, *_: object) -> object:
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot


def _resolve(adapter: TargetPreviewSourceAdapter) -> ExactPreviewSource:
    context, decision = context_and_decision()
    return asyncio.run(
        adapter.resolve_for_target_preview(
            context=context,
            decision=decision,
            processing_output_id=IDS[0],
            processing_output_revision_id=IDS[1],
            neutral_material_id=IDS[7],
            neutral_material_revision_id=IDS[8],
        )
    )


def test_source_adapter_requires_the_exact_governed_output_and_self_pinned_neutral_chain() -> None:
    output, neutral = _source_snapshots()
    resolved = _resolve(
        TargetPreviewSourceAdapter(
            outputs=cast(CommonProcessingOutputService, _Outputs(output)),
            neutral_materials=cast(NeutralMaterialService, _NeutralMaterials(neutral)),
        )
    )

    assert resolved.processing_output_sha256 == "b" * 64
    assert resolved.material_model_ir_revision_id == IDS[8]
    assert resolved.neutral_material_revision_id == IDS[8]

    for keyword, values in (
        ("governed", {"proof": None}),
        ("Neutral/IR", {"selected_output_id": IDS[9]}),
        ("Neutral/IR", {"selected_output_revision_id": IDS[9]}),
        ("Neutral/IR", {"selected_output_sha256": "e" * 64}),
        ("Neutral/IR", {"ir_revision_id": IDS[9]}),
        ("Neutral/IR", {"neutral_material_id": IDS[9]}),
        ("Neutral/IR", {"neutral_material_revision_id": IDS[9]}),
        ("Neutral/IR", {"neutral_material_state_id": IDS[9]}),
        ("Neutral/IR", {"neutral_material_state_revision_id": IDS[9]}),
    ):
        bad_output, bad_neutral = _source_snapshots(**values)
        with pytest.raises(TargetPreviewConflict, match=keyword):
            _resolve(
                TargetPreviewSourceAdapter(
                    outputs=cast(CommonProcessingOutputService, _Outputs(bad_output)),
                    neutral_materials=cast(NeutralMaterialService, _NeutralMaterials(bad_neutral)),
                )
            )


@pytest.mark.parametrize(
    "failure",
    [
        ProcessingOutputNotFound("not found"),
        CommonPipelineError("restricted output"),
        NeutralMaterialNotFound("not found"),
    ],
)
def test_source_adapter_does_not_leak_missing_or_restricted_scope_details(
    failure: Exception,
) -> None:
    _, neutral = _source_snapshots()
    adapter = TargetPreviewSourceAdapter(
        outputs=cast(CommonProcessingOutputService, _Outputs(failure)),
        neutral_materials=cast(NeutralMaterialService, _NeutralMaterials(neutral)),
    )

    with pytest.raises(
        TargetPreviewConflict, match="exact target-preview source is unavailable"
    ) as error:
        _resolve(adapter)

    assert "not found" not in str(error.value)
    assert "restricted" not in str(error.value)
