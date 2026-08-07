"""UXC-06C2 atomic delivery of a server-proven target preview.

The preview remains an ephemeral calculation.  Delivery repeats the exact proof,
requires the preview identity supplied by the browser, then creates one native
card and its immutable outbox receipt through the card revision transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardService,
)
from cmp.modules.exporting.application.target_preview import (
    CreateTargetPreview,
    TargetPreview,
    TargetPreviewConflict,
    TargetPreviewService,
)
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision, Permission
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.domain.revisions import RevisionCreated


class TargetDeliveryConflict(TargetPreviewConflict):
    """A delivery request is stale, unacknowledged, or cannot be persisted."""


class TargetDeliveryDuplicate(RuntimeError):
    """The receipt identity lost a concurrent immutable-delivery race."""


@dataclass(frozen=True, slots=True)
class CreateTargetDelivery:
    processing_output_id: UUID
    processing_output_revision_id: UUID
    neutral_material_id: UUID
    neutral_material_revision_id: UUID
    target: NeutralHyperelasticExportTarget
    solver_material_id: int
    material_name: str
    preview_identity: str
    expected_mapping_report_sha256: str
    acknowledgement_identity: str | None


@dataclass(frozen=True, slots=True)
class DeliveryReceipt:
    receipt_id: UUID
    delivery_identity: str
    solver_card_id: UUID
    solver_card_revision_id: UUID
    filename: str
    native_sha256: str
    mapping_report_sha256: str
    mapping_statuses: tuple[str, ...]
    source: dict[str, str]
    target: dict[str, str]
    occurred_at: str
    recorded_by: UUID


class DeliveryReceiptRecorder:
    """Port deliberately implemented by the Exporting persistence adapter."""

    def hook_for(
        self, *, context: SecurityContext, preview: TargetPreview, receipt_id: UUID
    ) -> Callable[[object, RevisionCreated], None]:
        raise NotImplementedError

    def find_by_delivery_identity(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        delivery_identity: str,
    ) -> DeliveryReceipt | None:
        raise NotImplementedError

    def get(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        receipt_id: UUID,
    ) -> DeliveryReceipt | None:
        raise NotImplementedError


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise TargetDeliveryConflict("authorization does not match target-delivery request")


class TargetDeliveryService:
    def __init__(
        self,
        *,
        previews: TargetPreviewService,
        cards: NeutralHyperelasticSolverCardService,
        receipts: DeliveryReceiptRecorder,
    ) -> None:
        self._previews = previews
        self._cards = cards
        self._receipts = receipts

    async def deliver(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateTargetDelivery,
    ) -> tuple[TargetPreview, DeliveryReceipt]:
        _require(context, decision, Permission.EXPORT_EXECUTE)
        preview = await self._previews.preview_for_delivery(
            context,
            decision,
            CreateTargetPreview(
                processing_output_id=command.processing_output_id,
                processing_output_revision_id=command.processing_output_revision_id,
                neutral_material_id=command.neutral_material_id,
                neutral_material_revision_id=command.neutral_material_revision_id,
                target=command.target,
                solver_material_id=command.solver_material_id,
                material_name=command.material_name,
                expected_mapping_report_sha256=command.expected_mapping_report_sha256,
            ),
        )
        if preview.preview_identity != command.preview_identity:
            raise TargetDeliveryConflict("target preview is stale; regenerate it before delivery")
        if preview.mapping_report_sha256 != command.expected_mapping_report_sha256:
            raise TargetDeliveryConflict("target mapping is stale; regenerate it before delivery")
        if preview.acknowledgement_identity is None:
            if command.acknowledgement_identity is not None:
                raise TargetDeliveryConflict(
                    "an acknowledgement is only valid when this mapping requires one"
                )
        elif command.acknowledgement_identity != preview.acknowledgement_identity:
            raise TargetDeliveryConflict("the required mapping acknowledgement is missing or stale")

        try:
            source_material_model_ir_revision_id = UUID(
                preview.source["material_model_ir_revision_id"]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise TargetDeliveryConflict("target preview source is malformed") from error

        existing = self._receipts.find_by_delivery_identity(
            context=context,
            decision=decision,
            delivery_identity=preview.preview_identity,
        )
        if existing is not None:
            self._require_matching_receipt(existing, preview)
            return preview, existing

        receipt_id = uuid5(NAMESPACE_URL, f"urn:cmp:target-delivery:{preview.preview_identity}")
        hook = self._receipts.hook_for(context=context, preview=preview, receipt_id=receipt_id)
        try:
            card, report = await self._cards.create_card(
                context,
                decision,
                CreateNeutralHyperelasticSolverCard(
                    neutral_material_id=command.neutral_material_id,
                    neutral_material_revision_id=command.neutral_material_revision_id,
                    target=command.target,
                    expected_mapping_report_sha256=command.expected_mapping_report_sha256,
                    solver_material_id=command.solver_material_id,
                    material_name=command.material_name,
                    change_reason=(
                        "Deliver exact UXC-06C2 native solver artifact with immutable receipt"
                    ),
                    expected_card_sha256=preview.native_sha256,
                    source_material_model_ir_revision_id=source_material_model_ir_revision_id,
                ),
                additional_hooks=(hook,),
            )
        except TargetDeliveryDuplicate as error:
            replayed = self._receipts.find_by_delivery_identity(
                context=context,
                decision=decision,
                delivery_identity=preview.preview_identity,
            )
            if replayed is None:
                raise TargetDeliveryConflict(
                    "concurrent delivery rolled back but no immutable receipt is visible"
                ) from error
            self._require_matching_receipt(replayed, preview)
            return preview, replayed
        if report.digest != preview.mapping_report_sha256:
            raise TargetDeliveryConflict(
                "persisted mapping differs from the current target preview"
            )
        return preview, DeliveryReceipt(
            receipt_id=receipt_id,
            delivery_identity=preview.preview_identity,
            solver_card_id=card.id,
            solver_card_revision_id=card.current.record.revision_id,
            filename=preview.filename,
            native_sha256=preview.native_sha256,
            mapping_report_sha256=preview.mapping_report_sha256,
            mapping_statuses=tuple(
                str(item["status"])
                for item in cast(list[dict[str, object]], preview.mapping["items"])
            ),
            source=preview.source,
            target=preview.target,
            occurred_at=card.current.record.created_at.isoformat(),
            recorded_by=context.principal.id,
        )

    @staticmethod
    def _require_matching_receipt(receipt: DeliveryReceipt, preview: TargetPreview) -> None:
        if (
            receipt.delivery_identity != preview.preview_identity
            or receipt.native_sha256 != preview.native_sha256
            or receipt.mapping_report_sha256 != preview.mapping_report_sha256
            or receipt.source != preview.source
            or receipt.target != preview.target
        ):
            raise TargetDeliveryConflict(
                "stored delivery evidence differs from the current target preview"
            )

    def get_receipt(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        receipt_id: UUID,
    ) -> DeliveryReceipt | None:
        _require(context, decision, Permission.EXPORT_READ)
        return self._receipts.get(
            context=context,
            decision=decision,
            receipt_id=receipt_id,
        )
