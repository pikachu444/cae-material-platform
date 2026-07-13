from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4, uuid5

import pytest
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
)
from cmp.modules.datasets.application.service import (
    DatasetRepository,
    DatasetRevisionSnapshot,
    DatasetService,
    DatasetSnapshot,
    ImportReferenceTensileCsv,
    ReferenceTestRunSource,
    RevisionSnapshot,
)
from cmp.modules.datasets.domain.reference_tensile import (
    REFERENCE_TENSILE_PARQUET_SCHEMA,
    CurvePoint,
    DatasetContent,
    DatasetNotFound,
    DatasetRepresentation,
    InvalidDatasetData,
    ReferenceTensileMapping,
    dataset_canonical,
    normalized_parquet_bytes,
    normalized_points_from_parquet,
    parse_reference_tensile_csv,
    preview_points,
)
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
from cmp.modules.testing.domain.reference_tensile import REFERENCE_TENSILE_METHOD_CODE
from cmp.shared.application.revisions import RevisionStore, RevisionTransaction
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
)

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
ORG = UUID("f1000000-0000-4000-8000-000000000001")
PROJECT = UUID("f1000000-0000-4000-8000-000000000002")
ACTOR = UUID("f1000000-0000-4000-8000-000000000003")
TEST_RUN = UUID("f1000000-0000-4000-8000-000000000004")
TEST_RUN_REVISION = UUID("f1000000-0000-4000-8000-000000000005")
RAW_ASSET = UUID("f1000000-0000-4000-8000-000000000006")
RAW_ARTIFACT = UUID("f1000000-0000-4000-8000-000000000007")
TRACE = "00-000000000000000000000000000000f1-00000000000000f1-01"
RAW_CSV = b"strain_pct,stress_mpa\n0,0\n1,100\n2,125\n"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Test Engineer", True),
        organization_id=ORG,
        project_id=PROJECT,
        issuer="https://test-idp.invalid",
        subject=str(ACTOR),
        token_id=str(uuid4()),
        groups=(),
        scopes=("openid",),
        request_id=uuid4(),
        trace_id=TRACE,
        authenticated_at=NOW,
    )


CONTEXT = _context()
WRITE = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.DATASET_WRITE,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=database_permissions_for(Permission.DATASET_WRITE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


def _mapping() -> ReferenceTensileMapping:
    return ReferenceTensileMapping("strain_pct", "stress_mpa", "%", "MPa")


@dataclass
class _State:
    heads: dict[UUID, UUID]
    records: dict[UUID, RevisionRecord]
    contents: dict[UUID, DatasetContent]
    events: list[RevisionCreated]


class _Transaction(RevisionTransaction[DatasetContent]):
    def __init__(self, state: _State) -> None:
        self._state = state

    @staticmethod
    def _record(
        draft: RevisionDraft[DatasetContent],
        revision_no: int,
        based_on_revision_id: UUID | None,
    ) -> RevisionRecord:
        return RevisionRecord(
            revision_id=draft.revision_id,
            aggregate_type=draft.aggregate_type,
            aggregate_id=draft.aggregate_id,
            scope=draft.scope,
            revision_no=revision_no,
            based_on_revision_id=based_on_revision_id,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )

    def create(self, draft: RevisionDraft[DatasetContent]) -> RevisionRecord:
        if draft.aggregate_id in self._state.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        record = self._record(draft, 1, None)
        self._state.heads[draft.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def revise(
        self,
        draft: RevisionDraft[DatasetContent],
        expected_current_revision_id: UUID,
    ) -> RevisionRecord:
        current_id = self._state.heads.get(draft.aggregate_id)
        if current_id is None:
            raise AggregateNotFound(str(draft.aggregate_id))
        if current_id != expected_current_revision_id:
            raise RevisionConflict(
                expected_current_revision_id, self._state.records[current_id].ref
            )
        current = self._state.records[current_id]
        record = self._record(draft, current.revision_no + 1, current_id)
        self._state.heads[draft.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        self._state.events.append(event)


class _Store(RevisionStore[DatasetContent]):
    def __init__(self) -> None:
        self.state = _State({}, {}, {}, [])

    def canonical_content(self, content: DatasetContent) -> object:
        return dataset_canonical(content)

    def transaction(self) -> AbstractContextManager[RevisionTransaction[DatasetContent]]:
        return self._transaction()

    @contextmanager
    def _transaction(self) -> Iterator[RevisionTransaction[DatasetContent]]:
        yield _Transaction(self.state)


def _artifact_record(
    *,
    artifact_id: UUID,
    payload: bytes,
    kind: ArtifactKind,
    schema_ref: str | None,
    source_raw_asset_id: UUID | None,
    media_type: str,
) -> ArtifactRecord:
    digest = hashlib.sha256(payload).hexdigest()
    return ArtifactRecord(
        Artifact(
            id=artifact_id,
            organization_id=ORG,
            project_id=PROJECT,
            classification=DataClassification.INTERNAL,
            artifact_kind=kind,
            artifact_role=(
                "raw.source" if kind is ArtifactKind.RAW else "dataset.normalized_curve"
            ),
            schema_ref=schema_ref,
            media_type=media_type,
            size_bytes=len(payload),
            sha256=digest,
            storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest),
            encryption_profile="test",
            source_raw_asset_id=source_raw_asset_id,
            source_pending_id=uuid4(),
            created_at=NOW,
            created_by=ACTOR,
        ),
        IntegrityStatus.VERIFIED,
        NOW,
        uuid4(),
    )


class _Artifacts:
    def __init__(self) -> None:
        self.raw = _artifact_record(
            artifact_id=RAW_ARTIFACT,
            payload=RAW_CSV,
            kind=ArtifactKind.RAW,
            schema_ref=None,
            source_raw_asset_id=RAW_ASSET,
            media_type="text/csv",
        )
        self.derived_calls = 0
        self.fail_next_derived = False

    async def read_verified_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        artifact_id: UUID,
        *,
        maximum_bytes: int,
    ) -> tuple[ArtifactRecord, bytes]:
        assert context is CONTEXT
        assert decision is WRITE
        assert artifact_id == RAW_ARTIFACT
        assert maximum_bytes >= len(RAW_CSV)
        return self.raw, RAW_CSV

    async def finalize_derived_bytes(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        *,
        classification: DataClassification,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
        value: bytes,
        idempotency_key: str,
    ) -> ArtifactRecord:
        assert context is CONTEXT
        assert decision is WRITE
        assert classification is DataClassification.INTERNAL
        assert artifact_role == "dataset.normalized_curve"
        assert schema_ref == REFERENCE_TENSILE_PARQUET_SCHEMA
        assert media_type == "application/vnd.apache.parquet"
        self.derived_calls += 1
        if self.fail_next_derived:
            self.fail_next_derived = False
            raise RuntimeError("synthetic object-store interruption")
        return _artifact_record(
            artifact_id=uuid5(UUID("f1000000-0000-4000-8000-000000000099"), idempotency_key),
            payload=value,
            kind=ArtifactKind.DERIVED,
            schema_ref=schema_ref,
            source_raw_asset_id=None,
            media_type=media_type,
        )


class _Repository(DatasetRepository):
    def __init__(self) -> None:
        self.store = _Store()

    def dataset_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[DatasetContent]:
        assert context is CONTEXT
        assert decision is WRITE
        return self.store

    def load_reference_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
        test_run_revision_id: UUID,
    ) -> ReferenceTestRunSource:
        assert context is CONTEXT
        assert decision is WRITE
        assert test_run_id == TEST_RUN
        assert test_run_revision_id == TEST_RUN_REVISION
        return ReferenceTestRunSource(DataClassification.INTERNAL, REFERENCE_TENSILE_METHOD_CODE)

    def get_dataset(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> DatasetSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        revision_id = self.store.state.heads.get(dataset_id)
        if revision_id is None:
            raise DatasetNotFound(str(dataset_id))
        record = self.store.state.records[revision_id]
        content = self.store.state.contents[revision_id]
        return DatasetSnapshot(dataset_id, content.test_run_id, RevisionSnapshot(record, content))

    def get_dataset_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_revision_id: UUID,
    ) -> DatasetRevisionSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        record = self.store.state.records[dataset_revision_id]
        return DatasetRevisionSnapshot(
            record.aggregate_id,
            RevisionSnapshot(record, self.store.state.contents[dataset_revision_id]),
        )

    def list_dataset_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        dataset_id: UUID,
    ) -> tuple[RevisionSnapshot[DatasetContent], ...]:
        assert context is CONTEXT
        assert decision is WRITE
        return tuple(
            RevisionSnapshot(record, self.store.state.contents[record.revision_id])
            for record in sorted(
                self.store.state.records.values(), key=lambda item: item.revision_no
            )
            if record.aggregate_id == dataset_id
        )

    def list_datasets_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[DatasetSnapshot, ...]:
        del context, decision, material_state_id
        return ()


def _command() -> ImportReferenceTensileCsv:
    return ImportReferenceTensileCsv(
        test_run_id=TEST_RUN,
        test_run_revision_id=TEST_RUN_REVISION,
        raw_asset_id=RAW_ASSET,
        raw_artifact_id=RAW_ARTIFACT,
        mapping=_mapping(),
        change_reason="import reference tensile CSV",
    )


def test_reference_csv_requires_explicit_mapping_and_preserves_original_units() -> None:
    parsed = parse_reference_tensile_csv(RAW_CSV, _mapping())

    assert parsed.raw_points[1] == CurvePoint(1.0, 100.0)
    assert parsed.normalized_points[1] == CurvePoint(0.01, 100_000_000.0)
    assert normalized_points_from_parquet(normalized_parquet_bytes(parsed.normalized_points)) == (
        parsed.normalized_points
    )
    source = tuple(CurvePoint(float(index), float(index)) for index in range(9))
    assert preview_points(source, 3) == (
        CurvePoint(0.0, 0.0),
        CurvePoint(4.0, 4.0),
        CurvePoint(8.0, 8.0),
    )


@pytest.mark.parametrize(
    ("payload", "mapping"),
    [
        (b"strain,stress\n0,0\n0,1\n", ReferenceTensileMapping("strain", "stress", "1", "Pa")),
        (b"strain,stress\n0,0\n1,\n", ReferenceTensileMapping("strain", "stress", "1", "Pa")),
        (b"other,stress\n0,0\n1,1\n", ReferenceTensileMapping("strain", "stress", "1", "Pa")),
    ],
)
def test_reference_csv_rejects_implicit_or_invalid_curve_data(
    payload: bytes,
    mapping: ReferenceTensileMapping,
) -> None:
    with pytest.raises(InvalidDatasetData):
        parse_reference_tensile_csv(payload, mapping)


def test_dataset_import_appends_raw_then_normalized_revision_and_is_idempotent() -> None:
    repository = _Repository()
    artifacts = _Artifacts()
    service = DatasetService(repository=repository, artifacts=cast(Any, artifacts))

    created = asyncio.run(service.import_reference_tensile_csv(CONTEXT, WRITE, _command()))
    repeated = asyncio.run(service.import_reference_tensile_csv(CONTEXT, WRITE, _command()))

    revisions = repository.list_dataset_revisions(
        context=CONTEXT, decision=WRITE, dataset_id=created.id
    )
    assert created.current.content.representation is DatasetRepresentation.NORMALIZED
    assert created.current.record.revision_no == 2
    assert repeated.current.record.revision_id == created.current.record.revision_id
    assert [item.content.representation for item in revisions] == [
        DatasetRepresentation.RAW,
        DatasetRepresentation.NORMALIZED,
    ]
    assert revisions[0].content.data_artifact_id == RAW_ARTIFACT
    assert revisions[1].content.source_dataset_revision_id == revisions[0].record.revision_id
    assert artifacts.derived_calls == 1


def test_dataset_import_recovers_from_failure_after_raw_revision_is_fixed() -> None:
    repository = _Repository()
    artifacts = _Artifacts()
    artifacts.fail_next_derived = True
    service = DatasetService(repository=repository, artifacts=cast(Any, artifacts))

    with pytest.raises(RuntimeError, match="object-store interruption"):
        asyncio.run(service.import_reference_tensile_csv(CONTEXT, WRITE, _command()))
    assert len(repository.store.state.records) == 1
    only_content = next(iter(repository.store.state.contents.values()))
    assert only_content.representation is DatasetRepresentation.RAW

    completed = asyncio.run(service.import_reference_tensile_csv(CONTEXT, WRITE, _command()))
    assert completed.current.content.representation is DatasetRepresentation.NORMALIZED
    assert len(repository.store.state.records) == 2
