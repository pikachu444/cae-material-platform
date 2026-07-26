from pathlib import Path


def test_uxc06c2_migration_keeps_card_receipt_and_outbox_evidence_immutable() -> None:
    text = Path(
        "backend/migrations/versions/20260726_089_uxc06c2_atomic_delivery.py"
    ).read_text(encoding="utf-8")

    for required in (
        "solver_card_delivery_receipt",
        "delivery_identity",
        "native_sha256",
        "mapping_report_sha256",
        "mapping_statuses",
        "neutral_solver_card_revision",
        "events.outbox_event",
        "reject_immutable_row_mutation",
        "FORCE ROW LEVEL SECURITY",
    ):
        assert required in text
    assert "UPDATE exporting.solver_card_delivery_receipt" not in text
