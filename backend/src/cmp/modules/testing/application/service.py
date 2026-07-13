"""Create immutable Specimen, Test Method, and Test Run records for the reference CSV slice."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.testing.domain.reference_tensile import (
    REFERENCE_TENSILE_METHOD_CODE,
    REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
    REFERENCE_TENSILE_SCHEMA_VERSION,
    SpecimenContent,
    TestingConflict,
    TestMethodContent,
    TestRunContent,
)
from cmp.shared.application.revisions import (
    CreateRevisionedAggregate,
    RevisionService,
    RevisionStore,
)
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

SPECIMEN_AGGREGATE_TYPE = "testing.specimen"
TEST_METHOD_AGGREGATE_TYPE = "testing.test_method"
TEST_RUN_AGGREGATE_TYPE = "testing.test_run"
SPECIMEN_SCHEMA_ID = "urn:cmp:testing:reference-specimen:1.0.0"
TEST_METHOD_SCHEMA_ID = "urn:cmp:testing:reference-uniaxial-tensile-method:1.0.0"
TEST_RUN_SCHEMA_ID = "urn:cmp:testing:reference-uniaxial-tensile-run:1.0.0"


@dataclass(frozen=True, slots=True)
class RevisionSnapshot[ContentT]:
    record: RevisionRecord
    content: ContentT


@dataclass(frozen=True, slots=True)
class SpecimenSnapshot:
    id: UUID
    material_state_id: UUID
    current: RevisionSnapshot[SpecimenContent]


@dataclass(frozen=True, slots=True)
class TestMethodSnapshot:
    id: UUID
    current: RevisionSnapshot[TestMethodContent]


@dataclass(frozen=True, slots=True)
class TestRunSnapshot:
    id: UUID
    specimen_id: UUID
    test_method_id: UUID
    current: RevisionSnapshot[TestRunContent]


@dataclass(frozen=True, slots=True)
class MaterialStateSource:
    classification: DataClassification
    content: SpecimenContent


@dataclass(frozen=True, slots=True)
class CreateSpecimen:
    material_state_id: UUID
    material_state_revision_id: UUID
    specimen_code: str
    orientation: str | None
    preparation_note: str | None
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileMethod:
    classification: DataClassification
    change_reason: str


@dataclass(frozen=True, slots=True)
class CreateReferenceTensileRun:
    specimen_id: UUID
    specimen_revision_id: UUID
    test_method_id: UUID
    test_method_revision_id: UUID
    run_label: str
    performed_at: datetime
    test_temperature_k: float | None
    crosshead_speed_mm_per_min: float | None
    change_reason: str


class TestingRepository(Protocol):
    def specimen_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[SpecimenContent]: ...

    def test_method_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestMethodContent]: ...

    def test_run_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[TestRunContent]: ...

    def load_material_state_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
        material_state_revision_id: UUID,
        specimen_code: str,
        orientation: str | None,
        preparation_note: str | None,
    ) -> MaterialStateSource: ...

    def load_specimen_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
        specimen_revision_id: UUID,
    ) -> tuple[DataClassification, SpecimenContent]: ...

    def load_test_method_source(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
        test_method_revision_id: UUID,
    ) -> tuple[DataClassification, TestMethodContent]: ...

    def get_specimen(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSnapshot: ...

    def list_specimens_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[SpecimenSnapshot, ...]: ...

    def get_test_method(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
    ) -> TestMethodSnapshot: ...

    def list_test_methods(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[TestMethodSnapshot, ...]: ...

    def get_test_run(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> TestRunSnapshot: ...

    def list_test_runs_for_material_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TestRunSnapshot, ...]: ...


def _require(
    context: SecurityContext,
    decision: AuthorizationDecision,
    permission: Permission,
) -> None:
    if (
        decision.permission is not permission
        or decision.principal_id != context.principal.id
        or decision.organization_id != context.organization_id
        or decision.project_id != context.project_id
        or decision.request_id != context.request_id
        or decision.trace_id != context.trace_id
    ):
        raise TestingConflict("authorization decision does not match testing request")


class TestingService:
    """Use T-06 revisions for the three explicit records required before CSV import."""

    def __init__(
        self,
        *,
        repository: TestingRepository,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._repository = repository
        self._id_factory = id_factory

    def _id(self) -> UUID:
        value = self._id_factory()
        if value.int == 0:
            raise RuntimeError("testing id_factory returned a zero UUID")
        return value

    def create_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateSpecimen,
    ) -> SpecimenSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        source = self._repository.load_material_state_source(
            context=context,
            decision=decision,
            material_state_id=command.material_state_id,
            material_state_revision_id=command.material_state_revision_id,
            specimen_code=command.specimen_code,
            orientation=command.orientation,
            preparation_note=command.preparation_note,
        )
        specimen_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, source.classification.value
        )
        record = RevisionService(
            aggregate_type=SPECIMEN_AGGREGATE_TYPE,
            store=self._repository.specimen_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=specimen_id,
                scope=scope,
                schema_id=SPECIMEN_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=source.content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return SpecimenSnapshot(
            specimen_id,
            source.content.material_state_id,
            RevisionSnapshot(record, source.content),
        )

    def create_reference_tensile_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileMethod,
    ) -> TestMethodSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        content = TestMethodContent(
            REFERENCE_TENSILE_METHOD_CODE,
            REFERENCE_TENSILE_METHOD_DISPLAY_NAME,
        )
        method_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, command.classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_METHOD_AGGREGATE_TYPE,
            store=self._repository.test_method_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=method_id,
                scope=scope,
                schema_id=TEST_METHOD_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestMethodSnapshot(method_id, RevisionSnapshot(record, content))

    def create_reference_tensile_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        command: CreateReferenceTensileRun,
    ) -> TestRunSnapshot:
        _require(context, decision, Permission.TESTING_WRITE)
        specimen_classification, _specimen = self._repository.load_specimen_source(
            context=context,
            decision=decision,
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
        )
        method_classification, method = self._repository.load_test_method_source(
            context=context,
            decision=decision,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
        )
        if specimen_classification is not method_classification:
            raise TestingConflict("Specimen and Test Method classifications must match")
        if method.method_code != REFERENCE_TENSILE_METHOD_CODE:
            raise TestingConflict("Test Run requires the reference tensile method")
        content = TestRunContent(
            specimen_id=command.specimen_id,
            specimen_revision_id=command.specimen_revision_id,
            test_method_id=command.test_method_id,
            test_method_revision_id=command.test_method_revision_id,
            run_label=command.run_label,
            performed_at=command.performed_at,
            test_temperature_k=command.test_temperature_k,
            crosshead_speed_mm_per_min=command.crosshead_speed_mm_per_min,
        )
        run_id = self._id()
        scope = TenantScope(
            context.organization_id, context.project_id, specimen_classification.value
        )
        record = RevisionService(
            aggregate_type=TEST_RUN_AGGREGATE_TYPE,
            store=self._repository.test_run_store(context, decision),
        ).create(
            CreateRevisionedAggregate(
                aggregate_id=run_id,
                scope=scope,
                schema_id=TEST_RUN_SCHEMA_ID,
                schema_version=REFERENCE_TENSILE_SCHEMA_VERSION,
                content=content,
                created_by=context.principal.id,
                change_reason=command.change_reason,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        return TestRunSnapshot(
            run_id,
            content.specimen_id,
            content.test_method_id,
            RevisionSnapshot(record, content),
        )

    def get_specimen(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        specimen_id: UUID,
    ) -> SpecimenSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_specimen(
            context=context, decision=decision, specimen_id=specimen_id
        )

    def list_specimens_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[SpecimenSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_specimens_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )

    def get_test_method(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_method_id: UUID,
    ) -> TestMethodSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_test_method(
            context=context, decision=decision, test_method_id=test_method_id
        )

    def list_test_methods(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[TestMethodSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_test_methods(context=context, decision=decision)

    def get_test_run(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        test_run_id: UUID,
    ) -> TestRunSnapshot:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.get_test_run(
            context=context, decision=decision, test_run_id=test_run_id
        )

    def list_test_runs_for_material_state(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[TestRunSnapshot, ...]:
        _require(context, decision, Permission.TESTING_READ)
        return self._repository.list_test_runs_for_material_state(
            context=context, decision=decision, material_state_id=material_state_id
        )
