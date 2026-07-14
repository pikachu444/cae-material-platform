from datetime import UTC, datetime
from uuid import UUID

import pytest
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.modules.review_release.domain.release import (
    InvalidRelease,
    RecordReleaseUsage,
    ReleaseLifecycleState,
    ReleaseTransitionKind,
    ReleaseTransitionRecord,
    ReleaseUsageKind,
    WithdrawRelease,
)

NOW = datetime(2026, 7, 25, 9, 0, tzinfo=UTC)


def uid(value: int) -> UUID:
    return UUID(f"32000000-0000-4000-8000-{value:012d}")


def test_supersede_transition_requires_explicit_successor_and_released_source() -> None:
    transition = ReleaseTransitionRecord(
        id=uid(1),
        release_id=uid(2),
        organization_id=uid(3),
        project_id=uid(4),
        classification=DataClassification.INTERNAL,
        kind=ReleaseTransitionKind.SUPERSEDE,
        from_state=ReleaseLifecycleState.RELEASED,
        to_state=ReleaseLifecycleState.SUPERSEDED,
        successor_release_id=uid(5),
        reason="Replace with reviewed successor",
        occurred_at=NOW,
        occurred_by=uid(6),
    )
    assert transition.successor_release_id == uid(5)
    with pytest.raises(InvalidRelease):
        ReleaseTransitionRecord(
            id=uid(7),
            release_id=uid(2),
            organization_id=uid(3),
            project_id=uid(4),
            classification=DataClassification.INTERNAL,
            kind=ReleaseTransitionKind.SUPERSEDE,
            from_state=ReleaseLifecycleState.RELEASED,
            to_state=ReleaseLifecycleState.SUPERSEDED,
            successor_release_id=None,
            reason="Missing successor",
            occurred_at=NOW,
            occurred_by=uid(6),
        )


def test_withdraw_and_usage_are_typed_append_only_commands() -> None:
    assert WithdrawRelease(reason="Evidence withdrawn").reason == "Evidence withdrawn"
    assert RecordReleaseUsage(
        usage_kind=ReleaseUsageKind.CONSUME,
        reason="Explicit solver selection",
    ).usage_kind is ReleaseUsageKind.CONSUME
    with pytest.raises(InvalidRelease):
        RecordReleaseUsage(usage_kind="download", reason="bad")  # type: ignore[arg-type]
