from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from cmp.modules.audit.domain.model import (
    GENESIS_HASH,
    AuditActorType,
    AuditEvent,
    AuditIntegrityIssueCode,
    AuditIntegrityState,
    AuditOutcome,
    AuditScope,
    AuditSegmentRoot,
    canonical_event_bytes,
    event_sha256,
    redact_ip_or_client,
    segment_root_sha256,
    verify_audit_integrity,
)

NOW = datetime(2026, 7, 13, 13, 0, tzinfo=UTC)
ORG = UUID("a5000000-0000-4000-8000-000000000001")
PROJECT = UUID("a5000000-0000-4000-8000-000000000002")
ACTOR = UUID("a5000000-0000-4000-8000-000000000003")
REQUEST = UUID("a5000000-0000-4000-8000-000000000004")
TRACE = "00-000000000000000000000000000000a5-00000000000000a5-01"


def _event(sequence: int, previous_hash: str) -> AuditEvent:
    provisional = AuditEvent(
        id=UUID(f"a5000000-0000-4000-8000-{sequence:012d}"),
        scope=AuditScope(ORG, PROJECT),
        sequence_no=sequence,
        occurred_at=NOW + timedelta(seconds=sequence),
        recorded_at=NOW + timedelta(seconds=sequence, microseconds=123456),
        actor_type=AuditActorType.USER,
        actor_id=ACTOR,
        action="synthetic.fixture.revision.create",
        target_type="synthetic.fixture.revision",
        target_id=UUID(f"a6000000-0000-4000-8000-{sequence:012d}"),
        outcome=AuditOutcome.SUCCESS,
        request_id=REQUEST,
        trace_id=TRACE,
        ip_or_client="policy-redacted",
        reason=f"append fixture {sequence}",
        previous_hash=previous_hash,
        event_hash=GENESIS_HASH,
    )
    return replace(provisional, event_hash=event_sha256(provisional))


def _chain() -> tuple[AuditEvent, ...]:
    first = _event(1, GENESIS_HASH)
    second = _event(2, first.event_hash)
    return first, second, _event(3, second.event_hash)


def _root(events: tuple[AuditEvent, ...]) -> AuditSegmentRoot:
    provisional = AuditSegmentRoot(
        id=UUID("a7000000-0000-4000-8000-000000000001"),
        scope=AuditScope(ORG, PROJECT),
        segment_no=1,
        first_sequence_no=1,
        last_sequence_no=len(events),
        event_count=len(events),
        first_event_hash=events[0].event_hash,
        last_event_hash=events[-1].event_hash,
        previous_root_hash=GENESIS_HASH,
        root_hash=GENESIS_HASH,
        created_at=NOW + timedelta(minutes=1),
        created_by=ACTOR,
        request_id=REQUEST,
        trace_id=TRACE,
    )
    return replace(provisional, root_hash=segment_root_sha256(provisional))


def test_canonical_hash_is_deterministic_length_framed_and_client_is_redacted() -> None:
    event = _chain()[0]

    assert canonical_event_bytes(event) == canonical_event_bytes(event)
    assert event_sha256(event) == event.event_hash
    assert b"cmp-audit-event-v1" in canonical_event_bytes(event)
    assert redact_ip_or_client("203.0.113.42") == "policy-redacted"
    assert redact_ip_or_client("Bearer secret") == "policy-redacted"


def test_integrity_accepts_a_valid_hash_chain_and_periodic_root() -> None:
    events = _chain()
    report = verify_audit_integrity(events, (_root(events),))

    assert report.state is AuditIntegrityState.VALID
    assert report.sealed_through_sequence_no == 3
    assert report.unsealed_event_count == 0
    assert report.issues == ()


def test_integrity_detects_event_mutation_reorder_and_deletion() -> None:
    events = _chain()
    mutated = replace(events[1], reason="mutated after append")
    mutation = verify_audit_integrity((events[0], mutated, events[2]))
    reordered = verify_audit_integrity((events[1], events[0], events[2]))
    deleted = verify_audit_integrity((events[0], events[2]), (_root(events),))

    assert AuditIntegrityIssueCode.EVENT_HASH_MISMATCH in {
        issue.code for issue in mutation.issues
    }
    assert AuditIntegrityIssueCode.EVENT_SEQUENCE_GAP in {
        issue.code for issue in reordered.issues
    }
    assert {
        AuditIntegrityIssueCode.EVENT_SEQUENCE_GAP,
        AuditIntegrityIssueCode.EVENT_PREVIOUS_HASH_MISMATCH,
        AuditIntegrityIssueCode.SEGMENT_EVENT_MISSING,
    }.issubset({issue.code for issue in deleted.issues})
