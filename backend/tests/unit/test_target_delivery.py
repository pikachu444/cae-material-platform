from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from cmp.modules.exporting.adapters.persistence import target_delivery_receipts
from cmp.modules.exporting.adapters.persistence.target_delivery_receipts import (
    SqlTargetDeliveryReceiptRecorder,
)
from cmp.modules.exporting.application.target_delivery import (
    CreateTargetDelivery,
    DeliveryReceipt,
    DeliveryReceiptRecorder,
    TargetDeliveryConflict,
    TargetDeliveryDuplicate,
    TargetDeliveryService,
)
from cmp.modules.exporting.application.target_preview import TargetPreview
from cmp.modules.exporting.domain.neutral_hyperelastic import NeutralHyperelasticExportTarget
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.jobs.domain.events import EventConflict
from sqlalchemy.exc import IntegrityError

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


def preview(*, acknowledgement: str | None = "a" * 64) -> TargetPreview:
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
    )


class Previews:
    def __init__(self, value: TargetPreview) -> None:
        self.value = value

    async def preview_for_delivery(self, *_: object) -> TargetPreview:
        return self.value


class Cards:
    def __init__(self) -> None:
        self.hooks: tuple[object, ...] = ()
        self.error: Exception | None = None

    async def create_card(self, *_: object, additional_hooks: tuple[object, ...]):
        if self.error is not None:
            raise self.error
        self.hooks = additional_hooks
        content = SimpleNamespace(card_sha256="b" * 64)
        card = SimpleNamespace(
            id=IDS[4],
            current=SimpleNamespace(
                content=content, record=SimpleNamespace(revision_id=IDS[5], created_at=NOW)
            ),
        )
        return card, SimpleNamespace(digest="c" * 64)


class Receipts(DeliveryReceiptRecorder):
    def __init__(self) -> None:
        self.created = 0
        self.existing: DeliveryReceipt | None = None

    def hook_for(self, **_: object):
        def hook(_: object, __: object) -> None:
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
            previews=cast(object, Previews(preview())), cards=cast(object, cards), receipts=receipts
        ).deliver(CONTEXT, DECISION, command())
    )
    _, receipt = result
    assert receipt.solver_card_id == IDS[4]
    assert receipt.delivery_identity == "a" * 64
    assert len(cards.hooks) == 1


@pytest.mark.parametrize(
    "values", [{"acknowledgement_identity": None}, {"preview_identity": "f" * 64}]
)
def test_delivery_fails_closed_for_missing_acknowledgement_or_stale_preview(
    values: dict[str, object],
) -> None:
    service = TargetDeliveryService(
        previews=cast(object, Previews(preview())), cards=cast(object, Cards()), receipts=Receipts()
    )
    with pytest.raises(TargetDeliveryConflict):
        asyncio.run(service.deliver(CONTEXT, DECISION, command(**values)))


def test_delivery_retry_returns_the_same_receipt_without_creating_another_card() -> None:
    cards, receipts = Cards(), Receipts()
    receipts.existing = delivery_receipt()
    _, returned_receipt = asyncio.run(
        TargetDeliveryService(
            previews=cast(object, Previews(preview())),
            cards=cast(object, cards),
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

        async def create_card(self, *_: object, additional_hooks: tuple[object, ...]):
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
        previews=cast(object, Previews(preview())), cards=cast(object, cards), receipts=receipts
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
        previews=cast(object, Previews(preview())), cards=cast(object, cards), receipts=receipts
    )

    with pytest.raises(TargetDeliveryConflict, match="no immutable receipt"):
        asyncio.run(service.deliver(CONTEXT, DECISION, command()))


def test_receipt_hook_translates_only_expected_delivery_identity_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DuplicateOrig:
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="solver_card_delivery_receipt",
            constraint_name="solver_card_delivery_receipt_organization_id_project_id_delivery_identity_key",
        )

    class OtherDuplicateOrig:
        sqlstate = "23505"
        diag = SimpleNamespace(
            table_name="solver_card_delivery_receipt", constraint_name="other_key"
        )

    class OutboxDuplicateOrig:
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
        session_factory=cast(object, None),
        rls_context=cast(object, None),
        writer=cast(object, Writer()),
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
            SimpleNamespace(revision=revision),
        )
    with pytest.raises(IntegrityError):
        hook(
            FakeSession(IntegrityError("insert", {}, OtherDuplicateOrig())),
            SimpleNamespace(revision=revision),
        )

    outbox_recorder = SqlTargetDeliveryReceiptRecorder(
        session_factory=cast(object, None),
        rls_context=cast(object, None),
        writer=cast(object, OutboxDuplicateWriter()),
    )
    with pytest.raises(TargetDeliveryDuplicate):
        outbox_recorder.hook_for(context=CONTEXT, preview=preview(), receipt_id=IDS[3])(
            FakeSession(IntegrityError("unused", {}, OtherDuplicateOrig())),
            SimpleNamespace(revision=revision),
        )
