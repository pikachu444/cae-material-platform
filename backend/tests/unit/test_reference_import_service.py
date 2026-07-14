from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.artifacts.domain.content import (
    Artifact,
    ArtifactKind,
    ArtifactRecord,
    IntegrityStatus,
    content_object_key,
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
from cmp.modules.testing.application.service import (
    IMPORT_MAPPING_AGGREGATE_TYPE,
    CreateReferenceImportMapping,
    DetectSyntheticCsvImport,
    ImportDetectionReportSnapshot,
    ImportMappingSnapshot,
    ReviseReferenceImportMapping,
    RevisionSnapshot,
)
from cmp.modules.testing.application.service import (
    TestingRepository as RepositoryPort,
)
from cmp.modules.testing.application.service import (
    TestingService as ServiceUnderTest,
)
from cmp.modules.testing.domain.import_mapping import (
    ReferenceImportMappingContent,
    reference_import_mapping_canonical,
)
from cmp.modules.testing.domain.reference_tensile import TestingConflict as MappingConflict
from cmp.shared.application.revisions import RevisionStore, RevisionTransaction
from cmp.shared.domain.revisions import (
    AggregateAlreadyExists,
    AggregateNotFound,
    RevisionConflict,
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
)

NOW = datetime(2026, 7, 18, 10, 0, tzinfo=UTC)
ORG = UUID("f3000000-0000-4000-8000-000000000001")
PROJECT = UUID("f3000000-0000-4000-8000-000000000002")
ACTOR = UUID("f3000000-0000-4000-8000-000000000003")
RAW_ASSET = UUID("f3000000-0000-4000-8000-000000000004")
RAW_ARTIFACT = UUID("f3000000-0000-4000-8000-000000000005")
REPORT = UUID("f3000000-0000-4000-8000-000000000006")
MAPPING = UUID("f3000000-0000-4000-8000-000000000007")
TRACE = "00-000000000000000000000000000000f3-00000000000000f3-01"
CSV = b"strain_pct,stress_mpa,temperature_k\n0,0,293.15\n1,100,293.15\n"


def _context() -> SecurityContext:
    return SecurityContext(
        principal=Principal(ACTOR, PrincipalType.USER, "Test engineer", True),
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
    permission=Permission.TESTING_WRITE,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=database_permissions_for(Permission.TESTING_WRITE),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=NOW,
)


@dataclass
class _State:
    heads: dict[UUID, UUID]
    records: dict[UUID, RevisionRecord]
    contents: dict[UUID, ReferenceImportMappingContent]
    events: list[RevisionCreated]


class _Transaction(RevisionTransaction[ReferenceImportMappingContent]):
    def __init__(self, state: _State) -> None:
        self._state = state

    @staticmethod
    def _record(
        draft: RevisionDraft[ReferenceImportMappingContent],
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

    def create(self, draft: RevisionDraft[ReferenceImportMappingContent]) -> RevisionRecord:
        if draft.aggregate_id in self._state.heads:
            raise AggregateAlreadyExists(str(draft.aggregate_id))
        record = self._record(draft, 1, None)
        self._state.heads[record.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def revise(
        self,
        draft: RevisionDraft[ReferenceImportMappingContent],
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
        self._state.heads[record.aggregate_id] = record.revision_id
        self._state.records[record.revision_id] = record
        self._state.contents[record.revision_id] = draft.content
        return record

    def stage(self, event: RevisionCreated) -> None:
        self._state.events.append(event)


class _MappingStore(RevisionStore[ReferenceImportMappingContent]):
    def __init__(self) -> None:
        self.state = _State({}, {}, {}, [])

    def canonical_content(self, content: ReferenceImportMappingContent) -> object:
        return reference_import_mapping_canonical(content)

    def transaction(
        self,
    ) -> AbstractContextManager[RevisionTransaction[ReferenceImportMappingContent]]:
        return self._transaction()

    @contextmanager
    def _transaction(self) -> Iterator[RevisionTransaction[ReferenceImportMappingContent]]:
        yield _Transaction(self.state)


class _Artifacts:
    def __init__(self) -> None:
        digest = hashlib.sha256(CSV).hexdigest()
        self.record = ArtifactRecord(
            artifact=Artifact(
                id=RAW_ARTIFACT,
                organization_id=ORG,
                project_id=PROJECT,
                classification=DataClassification.INTERNAL,
                artifact_kind=ArtifactKind.RAW,
                artifact_role="raw.source",
                schema_ref=None,
                media_type="text/csv",
                size_bytes=len(CSV),
                sha256=digest,
                storage_key=content_object_key(ORG, PROJECT, DataClassification.INTERNAL, digest),
                encryption_profile="test",
                source_raw_asset_id=RAW_ASSET,
                source_pending_id=uuid4(),
                created_at=NOW,
                created_by=ACTOR,
            ),
            integrity_status=IntegrityStatus.VERIFIED,
            last_checked_at=NOW,
            last_observation_id=uuid4(),
        )

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
        assert maximum_bytes == 16 * 1024 * 1024
        return self.record, CSV


class _Repository:
    def __init__(self) -> None:
        self.store = _MappingStore()
        self.reports: dict[UUID, ImportDetectionReportSnapshot] = {}

    def import_mapping_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceImportMappingContent]:
        assert context is CONTEXT
        assert decision is WRITE
        return self.store

    def create_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        report: ImportDetectionReportSnapshot,
    ) -> ImportDetectionReportSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        self.reports[report.id] = report
        return report

    def get_import_detection_report(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        detection_report_id: UUID,
    ) -> ImportDetectionReportSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        return self.reports[detection_report_id]

    def get_import_mapping(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        mapping_id: UUID,
    ) -> ImportMappingSnapshot:
        assert context is CONTEXT
        assert decision is WRITE
        revision_id = self.store.state.heads[mapping_id]
        return ImportMappingSnapshot(
            id=mapping_id,
            current=RevisionSnapshot(
                self.store.state.records[revision_id], self.store.state.contents[revision_id]
            ),
        )


def _service() -> tuple[ServiceUnderTest, _Repository]:
    identifiers = iter((REPORT, MAPPING))
    repository = _Repository()
    return (
        ServiceUnderTest(
            repository=cast(RepositoryPort, repository),
            artifacts=cast(ArtifactService, _Artifacts()),
            id_factory=lambda: next(identifiers),
            clock=lambda: NOW,
        ),
        repository,
    )


def test_detection_requires_explicit_human_mapping_and_preserves_prior_revision() -> None:
    service, repository = _service()

    report = asyncio.run(
        service.detect_synthetic_csv_import(
            CONTEXT,
            WRITE,
            DetectSyntheticCsvImport(raw_asset_id=RAW_ASSET, raw_artifact_id=RAW_ARTIFACT),
        )
    )

    assert report.id == REPORT
    assert report.report.status.value == "needs_input"
    assert report.report.strain_confidence.value == "low"
    assert report.report.stress_confidence.value == "low"
    assert repository.store.state.records == {}

    created = service.create_reference_import_mapping(
        CONTEXT,
        WRITE,
        CreateReferenceImportMapping(
            detection_report_id=report.id,
            mapping_label="original reference labels",
            strain_column="strain_pct",
            stress_column="stress_mpa",
            strain_unit="%",
            stress_unit="MPa",
            change_reason="Human confirms original CSV units and channel meaning.",
        ),
    )
    first = created.current
    revised = service.revise_reference_import_mapping(
        CONTEXT,
        WRITE,
        MAPPING,
        ReviseReferenceImportMapping(
            expected_current_revision_id=first.record.revision_id,
            detection_report_id=report.id,
            strain_column="strain_pct",
            stress_column="stress_mpa",
            strain_unit="%",
            stress_unit="Pa",
            change_reason="Correct human-approved stress unit without rewriting the first Mapping.",
        ),
    )

    assert revised.current.record.revision_no == 2
    assert revised.current.content.stress_unit == "Pa"
    assert repository.store.state.contents[first.record.revision_id].stress_unit == "MPa"
    assert revised.current.content.raw_artifact_id == RAW_ARTIFACT
    assert [event.revision.aggregate_type for event in repository.store.state.events] == [
        IMPORT_MAPPING_AGGREGATE_TYPE,
        IMPORT_MAPPING_AGGREGATE_TYPE,
    ]


def test_mapping_rejects_a_column_not_present_in_the_frozen_detection_report() -> None:
    service, _repository = _service()
    report = asyncio.run(
        service.detect_synthetic_csv_import(
            CONTEXT,
            WRITE,
            DetectSyntheticCsvImport(raw_asset_id=RAW_ASSET, raw_artifact_id=RAW_ARTIFACT),
        )
    )

    with pytest.raises(MappingConflict, match="frozen Detection Report"):
        service.create_reference_import_mapping(
            CONTEXT,
            WRITE,
            CreateReferenceImportMapping(
                detection_report_id=report.id,
                mapping_label="bad mapping",
                strain_column="unobserved_strain",
                stress_column="stress_mpa",
                strain_unit="1",
                stress_unit="MPa",
                change_reason="Attempt to use an unobserved column.",
            ),
        )
