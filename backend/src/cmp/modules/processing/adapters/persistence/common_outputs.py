"""PostgreSQL adapter for immutable common Processing Output evidence (T-53)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Literal, Protocol, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.datasets.application.canonical_test_data import (
    ExactRevisionRef,
    GovernedTestDataSource,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import (
    PROCESSING_OUTPUT_AGGREGATE_TYPE,
    PROCESSING_OUTPUT_PROFILE_SCHEMA_ID,
    PROCESSING_OUTPUT_PROFILE_SCHEMA_VERSION,
    PROCESSING_OUTPUT_SCHEMA_ID,
    PROCESSING_OUTPUT_SCHEMA_VERSION,
    ExactRevisionPin,
    FitDecisionParameter,
    FitDecisionParameterSet,
    FitDecisionSnapshot,
    ProcessingOutputContent,
    ProcessingOutputNotFound,
    ProcessingOutputRepository,
    ProcessingOutputSnapshot,
    ProcessingWorkupOverride,
    processing_output_content_canonical,
)
from cmp.modules.processing.domain.common_pipeline import ProcessingStep
from cmp.modules.units.domain.profiles import (
    UnitApplication,
    UnitApplicationRole,
    UnitProfilePin,
)
from cmp.modules.units.domain.system import DimensionId
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import (
    RevisionCreated,
    RevisionDraft,
    RevisionRecord,
    TenantScope,
    content_sha256,
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


metadata = sa.MetaData()
output_table = sa.Table(
    "common_processing_output",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="processing",
)
revision_table = sa.Table(
    "common_processing_output_revision",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("aggregate_id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("revision_no", sa.BigInteger(), nullable=False),
    sa.Column("based_on_revision_id", sa.Uuid(), nullable=True),
    sa.Column("schema_id", sa.String(255), nullable=False),
    sa.Column("schema_version", sa.String(64), nullable=False),
    sa.Column("content_hash", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("change_reason", sa.Text(), nullable=False),
    sa.Column("request_id", sa.Uuid(), nullable=False),
    sa.Column("trace_id", sa.String(255), nullable=False),
    sa.Column("label", sa.String(200), nullable=False),
    sa.Column("source_document_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_revision_id", sa.Uuid(), nullable=False),
    sa.Column("source_document_sha256", sa.CHAR(64), nullable=False),
    sa.Column("source_canonical_artifact_sha256", sa.CHAR(64), nullable=False),
    sa.Column("mapping_profile_id", sa.Uuid(), nullable=True),
    sa.Column("mapping_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("mapping_profile_sha256", sa.CHAR(64), nullable=True),
    sa.Column("source_profile_kind", sa.String(64), nullable=False),
    sa.Column("governed_import_profile_id", sa.Uuid(), nullable=True),
    sa.Column("governed_import_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("governed_import_profile_sha256", sa.CHAR(64), nullable=True),
    sa.Column("independent_quantity", sa.String(160), nullable=False),
    sa.Column("step_count", sa.Integer(), nullable=False),
    sa.Column("stage_count", sa.Integer(), nullable=False),
    sa.Column("final_point_count", sa.Integer(), nullable=False),
    sa.Column("output_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("output_sha256", sa.CHAR(64), nullable=False),
    sa.Column("result_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("result_sha256", sa.CHAR(64), nullable=True),
    sa.Column("result_schema_ref", sa.String(255), nullable=True),
    sa.Column("result_media_type", sa.String(255), nullable=True),
    sa.Column("source_processing_output_id", sa.Uuid(), nullable=True),
    sa.Column("source_processing_output_revision_id", sa.Uuid(), nullable=True),
    sa.Column("source_processing_output_sha256", sa.CHAR(64), nullable=True),
    sa.Column("workup_overrides", sa.JSON(), nullable=False),
    # An absent fit decision is SQL NULL, not the JSON literal null.
    sa.Column("fit_decision", sa.JSON(none_as_null=True), nullable=True),
    # Match migration 088: an absent proof is SQL NULL, not the JSON literal null.
    sa.Column("export_provenance", sa.JSON(none_as_null=True), nullable=True),
    sa.Column("unit_profile_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_revision_id", sa.Uuid(), nullable=True),
    sa.Column("unit_profile_sha256", sa.CHAR(64), nullable=True),
    schema="processing",
)
step_table = sa.Table(
    "common_processing_output_step",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("output_id", sa.Uuid(), nullable=False),
    sa.Column("output_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("method_id", sa.String(160), nullable=False),
    sa.Column("method_version", sa.String(64), nullable=False),
    sa.Column("options_sha256", sa.CHAR(64), nullable=False),
    sa.Column("options", sa.JSON(), nullable=False),
    schema="processing",
)
unit_application_table = sa.Table(
    "common_processing_output_unit_application",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("output_id", sa.Uuid(), nullable=False),
    sa.Column("output_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("location", sa.String(255), nullable=False),
    sa.Column("application_role", sa.String(32), nullable=False),
    sa.Column("quantity_semantics", sa.String(160), nullable=False),
    sa.Column("dimension", sa.String(64), nullable=False),
    sa.Column("unit_id", sa.String(64), nullable=False),
    schema="processing",
)


def _values(value: ProcessingOutputContent) -> dict[str, object]:
    return {
        "label": value.label,
        "source_document_id": value.source_document.aggregate_id,
        "source_document_revision_id": value.source_document.revision_id,
        "source_document_sha256": value.source_document_sha256,
        "source_canonical_artifact_sha256": value.source_canonical_artifact_sha256,
        "mapping_profile_id": (
            None if value.mapping_profile is None else value.mapping_profile.aggregate_id
        ),
        "mapping_profile_revision_id": (
            None if value.mapping_profile is None else value.mapping_profile.revision_id
        ),
        "mapping_profile_sha256": value.mapping_profile_sha256,
        "source_profile_kind": value.source_profile_kind,
        "governed_import_profile_id": (
            None
            if value.governed_import_profile is None
            else value.governed_import_profile.aggregate_id
        ),
        "governed_import_profile_revision_id": (
            None
            if value.governed_import_profile is None
            else value.governed_import_profile.revision_id
        ),
        "governed_import_profile_sha256": value.governed_import_profile_sha256,
        "independent_quantity": value.independent_quantity,
        "step_count": len(value.steps),
        "stage_count": value.stage_count,
        "final_point_count": value.final_point_count,
        "output_artifact_id": value.output_artifact_id,
        "output_sha256": value.output_sha256,
        "result_artifact_id": value.result_artifact_id,
        "result_sha256": value.result_sha256,
        "result_schema_ref": value.result_schema_ref,
        "result_media_type": value.result_media_type,
        "source_processing_output_id": (
            value.source_processing_output.aggregate_id
            if value.source_processing_output is not None
            else None
        ),
        "source_processing_output_revision_id": (
            value.source_processing_output.revision_id
            if value.source_processing_output is not None
            else None
        ),
        "source_processing_output_sha256": value.source_processing_output_sha256,
        "unit_profile_id": (None if value.unit_profile is None else value.unit_profile.profile_id),
        "unit_profile_revision_id": (
            None if value.unit_profile is None else value.unit_profile.revision_id
        ),
        "unit_profile_sha256": (
            None if value.unit_profile is None else value.unit_profile.content_sha256
        ),
        "workup_overrides": [
            {
                "kind": override.kind,
                "original_value": override.original_value,
                "original_unit": override.original_unit,
                "canonical_value": override.canonical_value,
                "canonical_unit": override.canonical_unit,
                "reason": override.reason,
            }
            for override in value.workup_overrides
        ],
        "fit_decision": None
        if value.fit_decision is None
        else {
            "candidate_key": value.fit_decision.candidate_key,
            "mode": value.fit_decision.mode,
            "primary_law": value.fit_decision.primary_law,
            "secondary_law": value.fit_decision.secondary_law,
            "primary_weight": value.fit_decision.primary_weight,
            "parameter_sets": [
                {
                    "law": item.law,
                    "parameters": [
                        {
                            "name": parameter.name,
                            "value": parameter.value,
                            "unit": parameter.unit,
                            "lower": parameter.lower,
                            "upper": parameter.upper,
                        }
                        for parameter in item.parameters
                    ],
                }
                for item in value.fit_decision.parameter_sets
            ],
            "fit_minimum": value.fit_decision.fit_minimum,
            "fit_maximum": value.fit_decision.fit_maximum,
            "extrapolation_maximum": value.fit_decision.extrapolation_maximum,
            "extrapolation_policy": value.fit_decision.extrapolation_policy,
            "metric_definition": value.fit_decision.metric_definition,
            "metric_value": value.fit_decision.metric_value,
            "requested_term_policy": value.fit_decision.requested_term_policy,
            "actual_term_count": value.fit_decision.actual_term_count,
            "selection_reason": value.fit_decision.selection_reason,
            "warning_acknowledged": value.fit_decision.warning_acknowledged,
        },
        "export_provenance": None
        if value.export_provenance is None
        else {
            "material": {
                "aggregate_id": str(value.export_provenance.material.aggregate_id),
                "revision_id": str(value.export_provenance.material.revision_id),
            },
            "material_state": {
                "aggregate_id": str(value.export_provenance.material_state.aggregate_id),
                "revision_id": str(value.export_provenance.material_state.revision_id),
            },
            "test_run": {
                "aggregate_id": str(value.export_provenance.test_run.aggregate_id),
                "revision_id": str(value.export_provenance.test_run.revision_id),
            },
        },
    }


def _write_steps(session: Session, draft: RevisionDraft[ProcessingOutputContent]) -> None:
    session.execute(
        sa.insert(step_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "output_id": draft.aggregate_id,
                "output_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "method_id": step.method_id,
                "method_version": step.method_version,
                "options_sha256": content_sha256(step.options),
                "options": step.options,
            }
            for ordinal, step in enumerate(draft.content.steps)
        ],
    )
    if draft.content.unit_applications:
        session.execute(
            sa.insert(unit_application_table),
            [
                {
                    "organization_id": draft.scope.organization_id,
                    "project_id": draft.scope.project_id,
                    "classification": draft.scope.classification,
                    "output_id": draft.aggregate_id,
                    "output_revision_id": draft.revision_id,
                    "ordinal": ordinal,
                    "location": item.location,
                    "application_role": item.role.value,
                    "quantity_semantics": item.quantity_semantics,
                    "dimension": item.dimension.value,
                    "unit_id": item.unit_id,
                }
                for ordinal, item in enumerate(draft.content.unit_applications)
            ],
        )


_TABLES = TypedRevisionTables(
    aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
    identity_table=output_table,
    revision_table=revision_table,
    canonical_content=processing_output_content_canonical,
    content_values=_values,
    identity_values=lambda value: {"label": value.label},
    revision_content_writer=_write_steps,
)


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
        aggregate_id=cast(UUID, row["aggregate_id"]),
        scope=TenantScope(
            cast(UUID, row["organization_id"]),
            cast(UUID, row["project_id"]),
            str(row["classification"]),
        ),
        revision_no=int(row["revision_no"]),
        based_on_revision_id=cast(UUID | None, row["based_on_revision_id"]),
        schema_id=str(row["schema_id"]),
        schema_version=str(row["schema_version"]),
        content_hash=str(row["content_hash"]),
        created_at=row["created_at"],
        created_by=cast(UUID, row["created_by"]),
        change_reason=str(row["change_reason"]),
        request_id=cast(UUID, row["request_id"]),
        trace_id=str(row["trace_id"]),
    )


def _content(
    row: Any, steps: Sequence[Any], unit_applications: Sequence[Any]
) -> ProcessingOutputContent:
    provenance = row["export_provenance"]
    return ProcessingOutputContent(
        label=str(row["label"]),
        source_document=ExactRevisionPin(
            cast(UUID, row["source_document_id"]),
            cast(UUID, row["source_document_revision_id"]),
        ),
        source_document_sha256=str(row["source_document_sha256"]),
        source_canonical_artifact_sha256=str(row["source_canonical_artifact_sha256"]),
        mapping_profile=(
            None
            if row["mapping_profile_id"] is None
            else ExactRevisionPin(
                cast(UUID, row["mapping_profile_id"]),
                cast(UUID, row["mapping_profile_revision_id"]),
            )
        ),
        mapping_profile_sha256=(
            None if row["mapping_profile_sha256"] is None else str(row["mapping_profile_sha256"])
        ),
        steps=tuple(
            ProcessingStep(
                method_id=str(step["method_id"]),
                method_version=str(step["method_version"]),
                options=dict(step["options"]),
            )
            for step in steps
        ),
        independent_quantity=str(row["independent_quantity"]),
        stage_count=int(row["stage_count"]),
        final_point_count=int(row["final_point_count"]),
        output_artifact_id=cast(UUID, row["output_artifact_id"]),
        output_sha256=str(row["output_sha256"]),
        source_profile_kind=cast(
            Literal["common_mapping_profile", "governed_import_profile"],
            str(row["source_profile_kind"]),
        ),
        governed_import_profile=(
            None
            if row["governed_import_profile_id"] is None
            else ExactRevisionPin(
                cast(UUID, row["governed_import_profile_id"]),
                cast(UUID, row["governed_import_profile_revision_id"]),
            )
        ),
        governed_import_profile_sha256=(
            None
            if row["governed_import_profile_sha256"] is None
            else str(row["governed_import_profile_sha256"])
        ),
        result_artifact_id=cast(UUID | None, row["result_artifact_id"]),
        result_sha256=(None if row["result_sha256"] is None else str(row["result_sha256"])),
        result_schema_ref=(
            None if row["result_schema_ref"] is None else str(row["result_schema_ref"])
        ),
        result_media_type=(
            None if row["result_media_type"] is None else str(row["result_media_type"])
        ),
        source_processing_output=(
            None
            if row["source_processing_output_id"] is None
            else ExactRevisionPin(
                cast(UUID, row["source_processing_output_id"]),
                cast(UUID, row["source_processing_output_revision_id"]),
            )
        ),
        source_processing_output_sha256=(
            None
            if row["source_processing_output_sha256"] is None
            else str(row["source_processing_output_sha256"])
        ),
        workup_overrides=tuple(
            ProcessingWorkupOverride(
                kind=cast(
                    Literal["youngs_modulus", "necking_boundary"],
                    str(override["kind"]),
                ),
                original_value=float(override["original_value"]),
                original_unit=str(override["original_unit"]),
                canonical_value=float(override["canonical_value"]),
                canonical_unit=str(override["canonical_unit"]),
                reason=str(override["reason"]),
            )
            for override in row["workup_overrides"]
        ),
        fit_decision=_fit_decision(row["fit_decision"]),
        export_provenance=None
        if provenance is None
        else GovernedTestDataSource(
            material=ExactRevisionRef(
                UUID(str(provenance["material"]["aggregate_id"])),
                UUID(str(provenance["material"]["revision_id"])),
            ),
            material_state=ExactRevisionRef(
                UUID(str(provenance["material_state"]["aggregate_id"])),
                UUID(str(provenance["material_state"]["revision_id"])),
            ),
            test_run=ExactRevisionRef(
                UUID(str(provenance["test_run"]["aggregate_id"])),
                UUID(str(provenance["test_run"]["revision_id"])),
            ),
        ),
        unit_profile=(
            None
            if row["unit_profile_id"] is None
            else UnitProfilePin(
                cast(UUID, row["unit_profile_id"]),
                cast(UUID, row["unit_profile_revision_id"]),
                str(row["unit_profile_sha256"]),
            )
        ),
        unit_applications=tuple(
            UnitApplication(
                location=str(item["location"]),
                role=UnitApplicationRole(str(item["application_role"])),
                quantity_semantics=str(item["quantity_semantics"]),
                dimension=DimensionId(str(item["dimension"])),
                unit_id=str(item["unit_id"]),
            )
            for item in unit_applications
        ),
    )


def _fit_decision(value: Any) -> FitDecisionSnapshot | None:
    if value is None:
        return None
    return FitDecisionSnapshot(
        candidate_key=str(value["candidate_key"]),
        mode=cast(Literal["single", "blend"], str(value["mode"])),
        primary_law=str(value["primary_law"]),
        secondary_law=value["secondary_law"],
        primary_weight=value["primary_weight"],
        parameter_sets=tuple(
            FitDecisionParameterSet(
                law=str(item["law"]),
                parameters=tuple(
                    FitDecisionParameter(
                        name=str(parameter["name"]),
                        value=float(parameter["value"]),
                        unit=str(parameter["unit"]),
                        lower=None if parameter["lower"] is None else float(parameter["lower"]),
                        upper=None if parameter["upper"] is None else float(parameter["upper"]),
                    )
                    for parameter in item["parameters"]
                ),
            )
            for item in value["parameter_sets"]
        ),
        fit_minimum=float(value["fit_minimum"]),
        fit_maximum=float(value["fit_maximum"]),
        extrapolation_maximum=None
        if value["extrapolation_maximum"] is None
        else float(value["extrapolation_maximum"]),
        extrapolation_policy=str(value["extrapolation_policy"]),
        metric_definition=str(value["metric_definition"]),
        metric_value=float(value["metric_value"]),
        requested_term_policy=value["requested_term_policy"],
        actual_term_count=value["actual_term_count"],
        selection_reason=str(value["selection_reason"]),
        warning_acknowledged=bool(value["warning_acknowledged"]),
    )


class SqlAlchemyCommonProcessingOutputRepository(ProcessingOutputRepository):
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        revision_hooks: Sequence[SqlRevisionHook] = (),
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._hooks = tuple(revision_hooks)

    def _bind(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(self, context: SecurityContext, decision: AuthorizationDecision) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def output_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ProcessingOutputContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def commit_in_artifact_session(
        self,
        *,
        session: object,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
        classification: str,
        content: ProcessingOutputContent,
        change_reason: str,
        artifact_created_at: datetime,
        revision_id: UUID | None = None,
        post_commit_hook: Callable[[object, ProcessingOutputSnapshot], None] | None = None,
    ) -> ProcessingOutputSnapshot:
        """Insert an output revision in the Artifact finalization transaction.

        The Artifact repository invokes this callback after inserting the immutable
        Artifact and integrity rows, but before its transaction commits.  Keeping the
        typed output identity, revision, and step rows on that same SQLAlchemy session
        makes a failure in either aggregate roll back both authoritative records.
        """

        if not isinstance(session, Session):
            raise TypeError("Artifact commit hook supplied a non-SQLAlchemy session")
        self._bind(session, context, decision)
        revision_id = revision_id or uuid4()
        scope = TenantScope(
            context.organization_id,
            context.project_id,
            classification,
        )
        draft = RevisionDraft(
            revision_id=revision_id,
            aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
            aggregate_id=output_id,
            scope=scope,
            schema_id=(
                PROCESSING_OUTPUT_PROFILE_SCHEMA_ID
                if content.unit_profile is not None
                else PROCESSING_OUTPUT_SCHEMA_ID
            ),
            schema_version=(
                PROCESSING_OUTPUT_PROFILE_SCHEMA_VERSION
                if content.unit_profile is not None
                else PROCESSING_OUTPUT_SCHEMA_VERSION
            ),
            content=content,
            content_hash=content_sha256(processing_output_content_canonical(content)),
            created_at=artifact_created_at,
            created_by=context.principal.id,
            change_reason=change_reason,
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        identity_values = _TABLES.encode_identity_values(content)
        session.execute(
            sa.insert(output_table).values(
                id=output_id,
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                classification=scope.classification,
                current_revision_id=revision_id,
                created_at=draft.created_at,
                created_by=draft.created_by,
                updated_at=draft.created_at,
                **identity_values,
            )
        )
        revision_values: dict[str, object] = {
            "id": revision_id,
            "aggregate_id": output_id,
            "organization_id": scope.organization_id,
            "project_id": scope.project_id,
            "classification": scope.classification,
            "revision_no": 1,
            "based_on_revision_id": None,
            "schema_id": draft.schema_id,
            "schema_version": draft.schema_version,
            "content_hash": draft.content_hash,
            "created_at": draft.created_at,
            "created_by": draft.created_by,
            "change_reason": draft.change_reason,
            "request_id": draft.request_id,
            "trace_id": draft.trace_id,
        }
        revision_values.update(_values(content))
        session.execute(sa.insert(revision_table).values(revision_values))
        _write_steps(session, draft)
        record = RevisionRecord(
            revision_id=revision_id,
            aggregate_type=PROCESSING_OUTPUT_AGGREGATE_TYPE,
            aggregate_id=output_id,
            scope=scope,
            revision_no=1,
            based_on_revision_id=None,
            schema_id=draft.schema_id,
            schema_version=draft.schema_version,
            content_hash=draft.content_hash,
            created_at=draft.created_at,
            created_by=draft.created_by,
            change_reason=draft.change_reason,
            request_id=draft.request_id,
            trace_id=draft.trace_id,
        )
        event = RevisionCreated(record, "draft")
        deferred_hooks: list[SqlRevisionHook] = []
        for hook in self._hooks:
            if post_commit_hook is not None and getattr(hook, "after_output_specializer", False):
                deferred_hooks.append(hook)
            else:
                hook(session, event)
        snapshot = ProcessingOutputSnapshot(output_id, record, content)
        if post_commit_hook is not None:
            post_commit_hook(session, snapshot)
            for hook in deferred_hooks:
                hook(session, event)
        return snapshot

    @staticmethod
    def _snapshot(session: Session, row: Any) -> ProcessingOutputSnapshot:
        steps = (
            session.execute(
                sa.select(step_table)
                .where(step_table.c.output_revision_id == row["id"])
                .order_by(step_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        unit_applications = (
            session.execute(
                sa.select(unit_application_table)
                .where(unit_application_table.c.output_revision_id == row["id"])
                .order_by(unit_application_table.c.ordinal)
            )
            .mappings()
            .all()
        )
        record = _record(row)
        return ProcessingOutputSnapshot(
            record.aggregate_id,
            record,
            _content(row, steps, unit_applications),
        )

    def get_output(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        output_id: UUID,
    ) -> ProcessingOutputSnapshot:
        with self._session(context, decision) as session:
            row = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        output_table,
                        sa.and_(
                            output_table.c.organization_id == revision_table.c.organization_id,
                            output_table.c.project_id == revision_table.c.project_id,
                            output_table.c.id == revision_table.c.aggregate_id,
                            output_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .where(output_table.c.id == output_id)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ProcessingOutputNotFound("Processing Output is not visible")
            return self._snapshot(session, row)

    def list_outputs(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProcessingOutputSnapshot, ...]:
        with self._session(context, decision) as session:
            rows = (
                session.execute(
                    sa.select(revision_table)
                    .join(
                        output_table,
                        sa.and_(
                            output_table.c.organization_id == revision_table.c.organization_id,
                            output_table.c.project_id == revision_table.c.project_id,
                            output_table.c.id == revision_table.c.aggregate_id,
                            output_table.c.current_revision_id == revision_table.c.id,
                        ),
                    )
                    .order_by(output_table.c.updated_at.desc(), output_table.c.id)
                )
                .mappings()
                .all()
            )
            return tuple(self._snapshot(session, row) for row in rows)
