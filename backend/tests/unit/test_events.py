from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from cmp.modules.identity_access.application.authorization import database_permissions_for
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from cmp.modules.jobs.application.events import OutboxPublisher
from cmp.modules.jobs.domain.events import (
    ClaimedCloudEvent,
    CloudEventDraft,
    CloudEventRecord,
    InvalidCloudEvent,
)

NOW = datetime(2026, 7, 13, 16, 0, tzinfo=UTC)
ORG = UUID("95000000-0000-4000-8000-000000000001")
PROJECT = UUID("95000000-0000-4000-8000-000000000002")
ACTOR = UUID("95000000-0000-4000-8000-000000000003")
AGGREGATE = UUID("95000000-0000-4000-8000-000000000004")
EVENT = UUID("95000000-0000-4000-8000-000000000005")
LEASE = UUID("95000000-0000-4000-8000-000000000006")
REQUEST = UUID("95000000-0000-4000-8000-000000000007")
TRACE = "00-00000000000000000000000000000095-0000000000000095-01"


def _draft() -> CloudEventDraft:
    return CloudEventDraft(
        organization_id=ORG,
        project_id=PROJECT,
        classification=DataClassification.INTERNAL,
        aggregate_type="artifact.artifact",
        aggregate_id=AGGREGATE,
        event_type="io.cmp.artifact.available.v1",
        source="urn:cmp:module:artifacts",
        subject=f"artifacts/{AGGREGATE}",
        data_schema="urn:cmp:schema:event:artifact-available:1.0.0",
        data={"artifact_id": str(AGGREGATE), "sha256": "a" * 64},
        occurred_at=NOW,
        recorded_by=ACTOR,
        request_id=REQUEST,
        trace_id=TRACE,
        deduplication_key=f"artifact.available:{AGGREGATE}",
    )


def _record() -> CloudEventRecord:
    return CloudEventRecord(EVENT, 1, _draft(), NOW)


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.SERVICE, "Event Publisher", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id="event-token",
        groups=(),
        scopes=(),
        request_id=REQUEST,
        trace_id=TRACE,
        authenticated_at=NOW,
    )


def _decision() -> AuthorizationDecision:
    return AuthorizationDecision(
        principal_id=ACTOR,
        organization_id=ORG,
        project_id=PROJECT,
        permission=Permission.JOB_EXECUTE,
        roles=(Role.JOB_RUNNER,),
        database_permissions=database_permissions_for(Permission.JOB_EXECUTE),
        max_classification=DataClassification.RESTRICTED,
        allow_export_controlled=False,
        request_id=REQUEST,
        trace_id=TRACE,
        decided_at=NOW,
    )


def test_cloud_event_envelope_is_canonical_tenant_scoped_and_content_only() -> None:
    event = _record()

    envelope = event.envelope()

    assert envelope["specversion"] == "1.0"
    assert envelope["id"] == str(EVENT)
    assert envelope["cmpsequence"] == 1
    assert envelope["cmporganizationid"] == str(ORG)
    assert envelope["cmpprojectid"] == str(PROJECT)
    assert envelope["data"] == _draft().data
    assert "storage_key" not in envelope["data"]
    assert event.draft.data_sha256 == _draft().data_sha256


def test_cloud_event_rejects_non_absolute_source_and_non_object_data() -> None:
    with pytest.raises(InvalidCloudEvent, match="absolute URI"):
        replace(_draft(), source="relative/source")
    with pytest.raises(InvalidCloudEvent, match="object"):
        replace(_draft(), data=["not", "an", "object"])


class _Repository:
    def __init__(self, *, poison: bool = False) -> None:
        self.claimed = (
            ClaimedCloudEvent(
                _record(),
                LEASE,
                NOW + timedelta(seconds=30),
                1,
            ),
        )
        self.published_ids: list[UUID] = []
        self.failed_ids: list[UUID] = []
        self.poison = poison

    def claim(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        limit: int,
        lease_duration: timedelta,
        now: datetime,
    ) -> tuple[ClaimedCloudEvent, ...]:
        del context, decision, limit, lease_duration, now
        return self.claimed

    def published(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        published_at: datetime,
    ) -> None:
        del context, decision, lease_token, published_at
        self.published_ids.append(event_id)

    def failed(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        event_id: UUID,
        lease_token: UUID,
        failure_code: str,
        retry_at: datetime,
        failed_at: datetime,
        maximum_attempts: int,
    ) -> bool:
        del (
            context,
            decision,
            lease_token,
            failure_code,
            retry_at,
            failed_at,
            maximum_attempts,
        )
        self.failed_ids.append(event_id)
        return self.poison


class _Transport:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.events: list[CloudEventRecord] = []

    def publish(self, event: CloudEventRecord) -> None:
        if self.failure is not None:
            raise self.failure
        self.events.append(event)


class _RejectedEvent(RuntimeError):
    code = "schema_rejected"


def test_publisher_marks_success_and_quarantines_poison_without_retry_loop() -> None:
    success_repository = _Repository()
    transport = _Transport()
    success = OutboxPublisher(
        repository=success_repository,
        transport=transport,
        clock=lambda: NOW + timedelta(seconds=1),
    ).publish_batch(_context(), _decision())

    assert (success.claimed, success.published, success.retry_scheduled, success.poisoned) == (
        1,
        1,
        0,
        0,
    )
    assert success_repository.published_ids == [EVENT]
    assert [event.id for event in transport.events] == [EVENT]

    poison_repository = _Repository(poison=True)
    poison = OutboxPublisher(
        repository=poison_repository,
        transport=_Transport(failure=_RejectedEvent()),
        clock=lambda: NOW + timedelta(seconds=1),
        maximum_attempts=1,
    ).publish_batch(_context(), _decision())

    assert (poison.published, poison.retry_scheduled, poison.poisoned) == (0, 0, 1)
    assert poison_repository.failed_ids == [EVENT]
