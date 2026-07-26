"""UXC-06C1 stateless native preview contract.

This is intentionally *not* a card-delivery service.  It takes one already
verified, concrete source chain from a narrow application port and produces a
deterministic response only.  In particular it does not allocate an artifact,
solver-card, receipt, Activity event, or cache row.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cmp.modules.exporting.domain.neutral_hyperelastic import (
    NeutralHyperelasticExportError,
    NeutralHyperelasticExportTarget,
)
from cmp.modules.exporting.domain.neutral_solver import (
    NeutralMappingReport,
    build_neutral_solver_card,
    preflight_neutral_solver_export,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.neutral_material import NeutralMaterialDocument


class TargetPreviewConflict(Exception):
    """The caller's exact source, target, or expected identity is not current."""


@dataclass(frozen=True, slots=True)
class ExactPreviewSource:
    """A server-proven Processing Output -> IR -> Neutral chain.

    `resolver` is responsible for proving the governed output is in the
    request scope and that each supplied revision is the concrete relation of
    its predecessor.  A browser pin is never accepted here.
    """

    processing_output_id: UUID
    processing_output_revision_id: UUID
    processing_output_sha256: str
    material_id: UUID
    material_revision_id: UUID
    material_state_id: UUID
    material_state_revision_id: UUID
    material_model_ir_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    neutral: NeutralMaterialDocument


class ExactPreviewSourceResolver(Protocol):
    async def resolve_for_target_preview(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        processing_output_id: UUID,
        processing_output_revision_id: UUID,
        neutral_material_id: UUID,
        neutral_material_revision_id: UUID,
    ) -> ExactPreviewSource: ...


@dataclass(frozen=True, slots=True)
class CreateTargetPreview:
    processing_output_id: UUID
    processing_output_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    target: NeutralHyperelasticExportTarget
    solver_material_id: int
    material_name: str
    expected_mapping_report_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class TargetPreview:
    """An ephemeral response whose identity covers every byte-affecting input."""

    preview_identity: str
    filename: str
    native_text: str
    native_sha256: str
    mapping_report_sha256: str
    mapping: dict[str, object]
    source: dict[str, str]
    target: dict[str, str]
    acknowledgement_identity: str | None
    non_production: bool = True
    delivery_status: str = "unavailable_pending_uxc_06c2"


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _require_read(context: SecurityContext, decision: AuthorizationDecision) -> None:
    if (
        decision.permission is not Permission.EXPORT_READ
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise TargetPreviewConflict("authorization does not match target-preview request")


def _warnings(report: NeutralMappingReport) -> bool:
    return any(item.status in {"approximated", "ignored"} for item in report.items)


def _extension(target: NeutralHyperelasticExportTarget) -> str:
    return "inp" if target.is_abaqus else "rad"


class TargetPreviewService:
    def __init__(self, *, resolver: ExactPreviewSourceResolver) -> None:
        self._resolver = resolver

    async def preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateTargetPreview,
    ) -> TargetPreview:
        _require_read(context, decision)
        return await self._preview(context, decision, command)

    async def preview_for_delivery(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateTargetPreview,
    ) -> TargetPreview:
        if (
            decision.permission is not Permission.EXPORT_EXECUTE
            or decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise TargetPreviewConflict("authorization does not match target-delivery request")
        return await self._preview(context, decision, command)

    async def _preview(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateTargetPreview,
    ) -> TargetPreview:
        source = await self._resolver.resolve_for_target_preview(
            context=context,
            decision=decision,
            processing_output_id=command.processing_output_id,
            processing_output_revision_id=command.processing_output_revision_id,
            neutral_material_id=command.neutral_material_id,
            neutral_material_revision_id=command.neutral_material_revision_id,
        )
        try:
            report = preflight_neutral_solver_export(
                neutral_material_id=source.neutral_material_id,
                neutral_material_revision_id=source.neutral_material_revision_id,
                source=source.neutral,
                target=command.target,
            )
            if not report.exportable:
                raise TargetPreviewConflict("target mapping is unsupported")
            if (
                command.expected_mapping_report_sha256 is not None
                and command.expected_mapping_report_sha256 != report.digest
            ):
                raise TargetPreviewConflict("target mapping acknowledgement is stale")
            verified_report, card = build_neutral_solver_card(
                neutral_material_id=source.neutral_material_id,
                neutral_material_revision_id=source.neutral_material_revision_id,
                source=source.neutral,
                target=command.target,
                expected_mapping_report_sha256=report.digest,
                solver_material_id=command.solver_material_id,
                material_name=command.material_name,
            )
        except NeutralHyperelasticExportError as error:
            raise TargetPreviewConflict("target mapping cannot produce a native preview") from error
        if verified_report.digest != report.digest:
            raise TargetPreviewConflict("target mapping changed while rendering native preview")
        mapping = report.canonical()
        native_text = card.card_text
        native_sha256 = card.card_sha256
        target = {
            "solver": command.target.solver,
            "version": command.target.version,
            "unit_system": command.target.unit_system,
            "solver_material_id": str(command.solver_material_id),
            "material_name": command.material_name,
        }
        source_identity = {
            "processing_output_id": str(source.processing_output_id),
            "processing_output_revision_id": str(source.processing_output_revision_id),
            "processing_output_sha256": source.processing_output_sha256,
            "material_id": str(source.material_id),
            "material_revision_id": str(source.material_revision_id),
            "material_state_id": str(source.material_state_id),
            "material_state_revision_id": str(source.material_state_revision_id),
            "material_model_ir_revision_id": str(source.material_model_ir_revision_id),
            "neutral_material_id": str(source.neutral_material_id),
            "neutral_material_revision_id": str(source.neutral_material_revision_id),
        }
        identity = _canonical_digest(
            {
                "source": source_identity,
                "target": target,
                "mapping_report_sha256": report.digest,
                "native_sha256": native_sha256,
            }
        )
        acknowledgement = identity if _warnings(report) else None
        return TargetPreview(
            preview_identity=identity,
            filename=(
                f"{command.material_name}-{command.target.solver}-{command.target.version}-"
                f"{native_sha256[:12]}.{_extension(command.target)}"
            ),
            native_text=native_text,
            native_sha256=native_sha256,
            mapping_report_sha256=report.digest,
            mapping=mapping,
            source=source_identity,
            target=target,
            acknowledgement_identity=acknowledgement,
        )
