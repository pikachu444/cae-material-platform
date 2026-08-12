from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import cmp.bootstrap.statistics as statistics_bootstrap
from cmp.modules.provenance.adapters.persistence.repository import (
    association_table as provenance_association_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    usage_table as provenance_usage_table,
)
from cmp.modules.statistics.application.replicate_service import (
    REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE,
    SCALAR_DISTRIBUTION_RESULT_AGGREGATE_TYPE,
    SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE,
)
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope


def _id(value: int) -> UUID:
    return UUID(int=value)


class _MappingResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self._row = row

    def mappings(self) -> _MappingResult:
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self._row


class _RecordingSession:
    def __init__(self, row: dict[str, object]) -> None:
        self._row = row
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> _MappingResult:
        self.statements.append(statement)
        return _MappingResult(self._row if getattr(statement, "is_select", False) else None)


def test_distribution_selection_provenance_uses_result_and_exact_plan(
    monkeypatch: Any,
) -> None:
    revision = RevisionRecord(
        revision_id=_id(10),
        aggregate_type=SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE,
        aggregate_id=_id(11),
        scope=TenantScope(_id(1), _id(2), "internal"),
        revision_no=1,
        based_on_revision_id=None,
        schema_id="urn:cmp:statistics:scalar-distribution-selection:1.0.0",
        schema_version="1.0.0",
        content_hash="a" * 64,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        created_by=_id(3),
        change_reason="Select one successful candidate explicitly",
        request_id=_id(4),
        trace_id="issue-210-provenance-test",
    )
    result_entity_id = _id(20)
    plan_entity_id = _id(21)
    selection_entity_id = _id(22)
    activity_id = _id(23)
    entity_ids = {
        SCALAR_DISTRIBUTION_RESULT_AGGREGATE_TYPE: result_entity_id,
        REPLICATE_STATISTICAL_PLAN_AGGREGATE_TYPE: plan_entity_id,
        SCALAR_DISTRIBUTION_SELECTION_AGGREGATE_TYPE: selection_entity_id,
    }

    def entity_id(
        _session: object,
        _event: RevisionCreated,
        *,
        aggregate_type: str,
        revision_id: UUID,
    ) -> UUID:
        assert revision_id.int > 0
        return entity_ids[aggregate_type]

    monkeypatch.setattr(statistics_bootstrap, "_revision_entity_id", entity_id)
    monkeypatch.setattr(
        statistics_bootstrap,
        "_generated_activity_id",
        lambda _session, _event, generated_id: (
            activity_id if generated_id == selection_entity_id else None
        ),
    )
    session = _RecordingSession(
        {
            "distribution_result_revision_id": _id(30),
            "selected_family": "normal",
            "candidate_sha256": "b" * 64,
            "plan_revision_id": _id(31),
            "statistical_run_id": _id(32),
        }
    )

    statistics_bootstrap.SqlScalarDistributionSelectionProvenanceHook()(
        session,  # type: ignore[arg-type]
        RevisionCreated(revision, "draft"),
    )

    usages = [
        statement.compile().params
        for statement in session.statements
        if getattr(statement, "table", None) is provenance_usage_table
    ]
    assert [(item["role"], item["entity_id"], item["ordinal"]) for item in usages] == [
        ("scalar_distribution_result", result_entity_id, 0),
        ("statistical_plan", plan_entity_id, 1),
    ]
    association = next(
        statement
        for statement in session.statements
        if getattr(statement, "table", None)
        is provenance_association_table
    )
    assert association.compile().params["plan_entity_id"] == plan_entity_id
