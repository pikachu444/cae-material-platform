from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from cmp.modules.exporting.adapters.persistence import target_delivery_receipts
from cmp.modules.exporting.adapters.persistence.target_delivery_receipts import (
    OutboxWriter,
    RlsContext,
    SqlTargetDeliveryReceiptRecorder,
)
from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    CreateNeutralHyperelasticSolverCard,
    NeutralHyperelasticSolverCardService,
)
from cmp.modules.exporting.application.target_delivery import (
    CreateTargetDelivery,
    DeliveryReceipt,
    DeliveryReceiptRecorder,
    TargetDeliveryConflict,
    TargetDeliveryDuplicate,
    TargetDeliveryService,
)
from cmp.modules.exporting.application.target_preview import TargetPreview, TargetPreviewService
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticSolverCardConflict,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.jobs.domain.events import EventConflict
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfilePin,
)
from cmp.modules.units.domain.system import DimensionId
from cmp.shared.domain.revisions import RevisionCreated
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

IDS = tuple(UUID(int=value) for value in range(1, 12))
NOW = datetime(2026, 7, 26, tzinfo=UTC)
CONTEXT = SecurityContext(
    Principal(IDS[0], PrincipalType.USER, "Deliver", True),
    IDS[1],
    IDS[2],
    "test",
    "deliver",
    "token",
    (),
    (),
    IDS[3],
    "delivery-test",
    NOW,
)
DECISION = AuthorizationDecision(
    IDS[0],
    IDS[1],
    IDS[2],
    Permission.EXPORT_EXECUTE,
    (Role.TEST_ENGINEER,),
    (Permission.EXPORT_EXECUTE.value,),
    DataClassification.INTERNAL,
    False,
    IDS[3],
    "delivery-test",
    NOW,
)


def preview(
    *,
    acknowledgement: str | None = "a" * 64,
    unit_profile: UnitProfilePin | None = None,
    unit_applications: tuple[UnitApplication, ...] = (),
) -> TargetPreview:
    return TargetPreview(
        preview_identity="a" * 64,
        filename="REFERENCE.inp",
        native_text="*MATERIAL",
        native_sha256="b" * 64,
        mapping_report_sha256="c" * 64,
        mapping={"items": [{"status": "approximated"}]},
        source={
            "processing_output_id": str(IDS[4]),
            "processing_output_revision_id": str(IDS[5]),
            "processing_output_sha256": "d" * 64,
            "material_id": str(IDS[6]),
            "material_revision_id": str(IDS[7]),
            "material_state_id": str(IDS[8]),
            "material_state_revision_id": str(IDS[9]),
            "material_model_ir_revision_id": str(IDS[10]),
            "neutral_material_id": str(IDS[4]),
            "neutral_material_revision_id": str(IDS[5]),
        },
        target={
            "solver": "abaqus",
            "version": "2025",
            "unit_system": "kg_m_s",
            "solver_material_id": "1",
            "material_name": "REFERENCE",
        },
        acknowledgement_identity=acknowledgement,
        unit_profile=unit_profile,
        unit_applications=unit_applications,
    )


class Previews:
    def __init__(self, value: TargetPreview) -> None:
        self.value = value

    async def preview_for_delivery(self, *_: object) -> TargetPreview:
        return self.value


class Cards:
    def __init__(self, unit_applications: tuple[UnitApplication, ...] = ()) -> None:
        self.hooks: tuple[object, ...] = ()
        self.error: Exception | None = None
        self.calls = 0
        self.command: CreateNeutralHyperelasticSolverCard | None = None
        self.unit_applications = unit_applications

    async def create_card(
        self, *args: object, additional_hooks: tuple[object, ...]
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        self.hooks = additional_hooks
        self.command = cast(CreateNeutralHyperelasticSolverCard, args[2])
        unit_profile = getattr(self.command, "unit_profile", None)
        content = SimpleNamespace(
            card_sha256="b" * 64,
            unit_profile=unit_profile,
            unit_applications=self.unit_applications,
        )
        card = SimpleNamespace(
            id=IDS[4],
            current=SimpleNamespace(
                content=content, record=SimpleNamespace(revision_id=IDS[5], created_at=NOW)
            ),
            unit_profile=unit_profile,
            unit_applications=self.unit_applications,
        )
        return card, SimpleNamespace(digest="c" * 64)


class Receipts(DeliveryReceiptRecorder):
    def __init__(self) -> None:
        self.created = 0
        self.existing: DeliveryReceipt | None = None

    def hook_for(self, **_: object) -> Callable[[object, RevisionCreated], None]:
        def hook(_: object, __: RevisionCreated) -> None:
            self.created += 1

        return hook

    def find_by_delivery_identity(self, **_: object) -> DeliveryReceipt | None:
        return self.existing

    def get(self, **_: object) -> DeliveryReceipt | None:
        return self.existing


def delivery_receipt() -> DeliveryReceipt:
    return DeliveryReceipt(
        receipt_id=uuid5(NAMESPACE_URL, f"urn:cmp:target-delivery:{'a' * 64}"),
        delivery_identity="a" * 64,
        solver_card_id=IDS[4],
        solver_card_revision_id=IDS[5],
        filename="REFERENCE.inp",
        native_sha256="b" * 64,
        mapping_report_sha256="c" * 64,
        mapping_statuses=("approximated",),
        source=preview().source,
        target=preview().target,
        occurred_at=NOW.isoformat(),
        recorded_by=IDS[0],
    )


def command(**overrides: object) -> CreateTargetDelivery:
    values: dict[str, object] = dict(
        processing_output_id=IDS[4],
        processing_output_revision_id=IDS[5],
        neutral_material_id=IDS[4],
        neutral_material_revision_id=IDS[5],
        target=NeutralHyperelasticExportTarget("abaqus", "2025", "kg_m_s"),
        solver_material_id=1,
        material_name="REFERENCE",
        preview_identity="a" * 64,
        expected_mapping_report_sha256="c" * 64,
        acknowledgement_identity="a" * 64,
    )
    values.update(overrides)
    return CreateTargetDelivery(**values)  # type: ignore[arg-type]


def test_delivery_binds_current_preview_acknowledgement_and_card_hook() -> None:
    cards, receipts = Cards(), Receipts()
    result = asyncio.run(
        TargetDeliveryService(
            previews=cast(TargetPreviewService, Previews(preview())),
            cards=cast(NeutralHyperelasticSolverCardService, cards),
            receipts=receipts,
        ).deliver(CONTEXT, DECISION, command())
    )
    _, receipt = result
    assert receipt.solver_card_id == IDS[4]
    assert receipt.delivery_identity == "a" * 64
    assert len(cards.hooks) == 1


def test_delivery_passes_revalidated_upstream_ir_to_card_and_receipt() -> None:
    cards, receipts = Cards(), Receipts()
    delivered_preview, receipt = asyncio.run(
        TargetDeliveryService(
            previews=cast(TargetPreviewService, Previews(preview())),
            cards=cast(NeutralHyperelasticSolverCardService, cards),
            receipts=receipts,
        ).deliver(CONTEXT, DECISION, command())
    )

    assert delivered_preview.source["material_model_ir_revision_id"] == str(IDS[10])
    assert cards.command is not None
    assert cards.command.source_material_model_ir_revision_id == IDS[10]
    assert cards.command.source_material_model_ir_revision_id != IDS[5]
    assert receipt.source["material_model_ir_revision_id"] == str(IDS[10])
    assert receipt.native_sha256 == delivered_preview.native_sha256


def test_delivery_preserves_exact_unit_profile_trace_in_card_command_and_receipt() -> None:
    pin = UnitProfilePin(IDS[6], IDS[7], "e" * 64)
    applications = (
        UnitApplication(
            "solver_card.density",
            UnitApplicationRole.SOLVER_EXPORT,
            "mass.density",
            DimensionId.MASS_PER_VOLUME,
            "kg/m3",
        ),
    )
    cards, receipts = Cards(applications), Receipts()
    profiled_preview = preview(unit_profile=pin, unit_applications=applications)

    delivered_preview, receipt = asyncio.run(
        TargetDeliveryService(
            previews=cast(TargetPreviewService, Previews(profiled_preview)),
            cards=cast(NeutralHyperelasticSolverCardService, cards),
            receipts=receipts,
        ).deliver(CONTEXT, DECISION, command(unit_profile=pin))
    )

    assert cards.command is not None
    assert cards.command.unit_profile == pin
    assert delivered_preview.unit_profile == pin
    assert receipt.unit_profile == pin
    assert receipt.unit_applications == applications


def test_delivery_fails_closed_when_persisted_card_drops_unit_profile_trace() -> None:
    pin = UnitProfilePin(IDS[6], IDS[7], "e" * 64)
    applications = (
        UnitApplication(
            "solver_card.density",
            UnitApplicationRole.SOLVER_EXPORT,
            "mass.density",
            DimensionId.MASS_PER_VOLUME,
            "kg/m3",
        ),
    )
    service = TargetDeliveryService(
        previews=cast(
            TargetPreviewService,
            Previews(preview(unit_profile=pin, unit_applications=applications)),
        ),
        cards=cast(NeutralHyperelasticSolverCardService, Cards()),
        receipts=Receipts(),
    )

    with pytest.raises(TargetDeliveryConflict, match="application trace"):
        asyncio.run(service.deliver(CONTEXT, DECISION, command(unit_profile=pin)))


@pytest.mark.parametrize(
    "values", [{"acknowledgement_identity": None}, {"preview_identity": "f" * 64}]
)
def test_delivery_fails_closed_for_missing_acknowledgement_or_stale_preview(
    values: dict[str, object],
) -> None:
    service = TargetDeliveryService(
        previews=cast(TargetPreviewService, Previews(preview())),
        cards=cast(NeutralHyperelasticSolverCardService, Cards()),
        receipts=Receipts(),
    )
    with pytest.raises(TargetDeliveryConflict):
        asyncio.run(service.deliver(CONTEXT, DECISION, command(**values)))


def test_delivery_retry_returns_the_same_receipt_without_creating_another_card() -> None:
    cards, receipts = Cards(), Receipts()
    receipts.existing = delivery_receipt()
    _, returned_receipt = asyncio.run(
        TargetDeliveryService(
            previews=cast(TargetPreviewService, Previews(preview())),
            cards=cast(NeutralHyperelasticSolverCardService, cards),
            receipts=receipts,
        ).deliver(CONTEXT, DECISION, command())
    )
    assert returned_receipt is receipts.existing
    assert cards.hooks == ()


def test_concurrent_delivery_race_returns_the_committed_receipt_once() -> None:
    receipts = Receipts()

    class RacingCards(Cards):
        def __init__(self) -> None:
            super().__init__()
            self.arrived = 0
            self.barrier = asyncio.Barrier(2)
            self.committed = asyncio.Event()

        async def create_card(
            self, *_: object, additional_hooks: tuple[object, ...]
        ) -> tuple[SimpleNamespace, SimpleNamespace]:
            self.arrived += 1
            arrival = self.arrived
            await self.barrier.wait()
            if arrival == 1:
                self.hooks = additional_hooks
                receipts.existing = delivery_receipt()
                self.committed.set()
                return await super().create_card(*_, additional_hooks=additional_hooks)
            await self.committed.wait()
            raise TargetDeliveryDuplicate("delivery identity committed by the other transaction")

    cards = RacingCards()
    service = TargetDeliveryService(
        previews=cast(TargetPreviewService, Previews(preview())),
        cards=cast(NeutralHyperelasticSolverCardService, cards),
        receipts=receipts,
    )

    async def deliver_twice() -> tuple[
        tuple[TargetPreview, DeliveryReceipt], tuple[TargetPreview, DeliveryReceipt]
    ]:
        return cast(
            tuple[tuple[TargetPreview, DeliveryReceipt], tuple[TargetPreview, DeliveryReceipt]],
            await asyncio.gather(
                service.deliver(CONTEXT, DECISION, command()),
                service.deliver(CONTEXT, DECISION, command()),
            ),
        )

    first, second = asyncio.run(deliver_twice())
    assert first[1] == receipts.existing
    assert second[1] is receipts.existing
    assert cards.arrived == 2


def test_delivery_race_fails_closed_when_the_rolled_back_receipt_is_not_visible() -> None:
    cards, receipts = Cards(), Receipts()
    cards.error = TargetDeliveryDuplicate("delivery transaction rolled back")
    service = TargetDeliveryService(
        previews=cast(TargetPreviewService, Previews(preview())),
        cards=cast(NeutralHyperelasticSolverCardService, cards),
        receipts=receipts,
    )

    with pytest.raises(TargetDeliveryConflict, match="no immutable receipt"):
        asyncio.run(service.deliver(CONTEXT, DECISION, command()))


def test_injected_malformed_native_card_fails_before_receipt_write() -> None:
    """A renderer/validator fault must leave both card and receipt stores unchanged."""

    cards, receipts = Cards(), Receipts()
    cards.error = NeutralHyperelasticSolverCardConflict(
        "generated card differs from the approved target preview"
    )
    service = TargetDeliveryService(
        previews=cast(TargetPreviewService, Previews(preview())),
        cards=cast(NeutralHyperelasticSolverCardService, cards),
        receipts=receipts,
    )

    with pytest.raises(NeutralHyperelasticSolverCardConflict, match="generated card differs"):
        asyncio.run(service.deliver(CONTEXT, DECISION, command()))
    assert cards.calls == 1
    assert receipts.created == 0
    assert receipts.existing is None


def test_receipt_hook_translates_only_expected_delivery_identity_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DuplicateOrig(Exception):
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="solver_card_delivery_receipt",
            constraint_name="solver_card_delivery_receipt_organization_id_project_id_delivery_identity_key",
        )

    class OtherDuplicateOrig(Exception):
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="solver_card_delivery_receipt", constraint_name="other_key"
        )

    class OutboxDuplicateOrig(Exception):
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="outbox_event", constraint_name="uq_events_outbox_deduplication"
        )

    class FakeSession:
        def __init__(self, error: IntegrityError) -> None:
            self.error = error

        def execute(self, _: object) -> None:
            raise self.error

    class Writer:
        def append(self, *_: object, **__: object) -> object:
            return SimpleNamespace(event=SimpleNamespace(id=IDS[3]))

    class OutboxDuplicateWriter:
        def append(self, *_: object, **__: object) -> object:
            error = IntegrityError("insert", {}, OutboxDuplicateOrig())
            raise EventConflict("database rejected immutable outbox event") from error

    monkeypatch.setattr(target_delivery_receipts, "Session", FakeSession)
    recorder = SqlTargetDeliveryReceiptRecorder(
        session_factory=cast(sessionmaker[Session], None),
        rls_context=cast(RlsContext, None),
        writer=cast(OutboxWriter, Writer()),
    )
    revision = SimpleNamespace(
        aggregate_id=IDS[4],
        revision_id=IDS[5],
        scope=SimpleNamespace(classification="internal"),
        created_at=NOW,
    )
    hook = recorder.hook_for(context=CONTEXT, preview=preview(), receipt_id=IDS[3])

    with pytest.raises(TargetDeliveryDuplicate):
        hook(
            FakeSession(IntegrityError("insert", {}, DuplicateOrig())),
            cast(RevisionCreated, SimpleNamespace(revision=revision)),
        )
    with pytest.raises(IntegrityError):
        hook(
            FakeSession(IntegrityError("insert", {}, OtherDuplicateOrig())),
            cast(RevisionCreated, SimpleNamespace(revision=revision)),
        )

    outbox_recorder = SqlTargetDeliveryReceiptRecorder(
        session_factory=cast(sessionmaker[Session], None),
        rls_context=cast(RlsContext, None),
        writer=cast(OutboxWriter, OutboxDuplicateWriter()),
    )
    with pytest.raises(TargetDeliveryDuplicate):
        outbox_recorder.hook_for(context=CONTEXT, preview=preview(), receipt_id=IDS[3])(
            FakeSession(IntegrityError("unused", {}, OtherDuplicateOrig())),
            cast(RevisionCreated, SimpleNamespace(revision=revision)),
        )
