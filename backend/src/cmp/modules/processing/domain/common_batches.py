"""Exact-selection batch execution records for common Processing Recipes (T-54)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from cmp.modules.processing.application.common_outputs import (
        FitDecisionSnapshot,
        ProcessingWorkupOverride,
    )
from cmp.modules.processing.domain.common_pipeline import CommonPipelineError
from cmp.shared.domain.revisions import TenantScope


class BatchAttemptStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BatchStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BatchRevisionPin:
    aggregate_id: UUID
    revision_id: UUID


@dataclass(frozen=True, slots=True)
class BatchMemberPlan:
    member_id: UUID
    ordinal: int
    source_document: BatchRevisionPin
    source_document_sha256: str
    workup_overrides: tuple[ProcessingWorkupOverride, ...] = ()
    fit_decision: FitDecisionSnapshot | None = None


@dataclass(frozen=True, slots=True)
class BatchAttempt:
    attempt_id: UUID
    member_id: UUID
    attempt_no: int
    status: BatchAttemptStatus
    output: BatchRevisionPin | None
    error_code: str | None
    error_detail: str | None
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class CommonProcessingBatch:
    batch_id: UUID
    scope: TenantScope
    label: str
    recipe: BatchRevisionPin
    recipe_sha256: str
    members: tuple[BatchMemberPlan, ...]
    attempts: tuple[BatchAttempt, ...]
    created_at: datetime
    created_by: UUID
    request_id: UUID
    trace_id: str

    def __post_init__(self) -> None:
        if not self.label.strip() or len(self.label) > 200:
            raise CommonPipelineError("Batch label must contain 1..200 characters")
        if not self.members or len(self.members) > 500:
            raise CommonPipelineError("Batch requires 1..500 exact input revisions")
        if tuple(item.ordinal for item in self.members) != tuple(range(len(self.members))):
            raise CommonPipelineError("Batch member ordinals must be contiguous from zero")
        if len({item.member_id for item in self.members}) != len(self.members):
            raise CommonPipelineError("Batch member identities must be unique")
        if len({item.source_document for item in self.members}) != len(self.members):
            raise CommonPipelineError("Batch exact input revisions must be unique")

    @property
    def latest_attempts(self) -> dict[UUID, BatchAttempt]:
        latest: dict[UUID, BatchAttempt] = {}
        for attempt in self.attempts:
            existing = latest.get(attempt.member_id)
            if existing is None or attempt.attempt_no > existing.attempt_no:
                latest[attempt.member_id] = attempt
        return latest

    @property
    def status(self) -> BatchStatus:
        latest = self.latest_attempts
        if not latest:
            return BatchStatus.PLANNED
        if len(latest) < len(self.members):
            return BatchStatus.RUNNING
        succeeded = sum(
            item.status is BatchAttemptStatus.SUCCEEDED for item in latest.values()
        )
        if succeeded == len(self.members):
            return BatchStatus.SUCCEEDED
        if succeeded:
            return BatchStatus.PARTIAL
        return BatchStatus.FAILED
