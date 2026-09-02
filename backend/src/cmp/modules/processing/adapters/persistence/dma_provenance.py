"""DMA master-curve provenance finalization in the owning SQL adapter.

The DMA application service owns the scientific decision.  This adapter owns the
transaction-local translation of that decision into the typed provenance tables.
It deliberately does not create an activity for either DMA output Artifact: the
single Processing Output revision Activity is specialized in place and generates
the revision plus the two Artifact entities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.artifacts.domain.content import ArtifactRecord
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.processing.application.common_outputs import ProcessingOutputSnapshot
from cmp.modules.provenance.domain.model import (
    ActivityStatus,
    AgentReference,
    AgentType,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceAgent,
    ProvenanceConflict,
    ProvenanceEntity,
    ProvenanceScope,
)
from cmp.shared.domain.revisions import content_sha256

DMA_ACTIVITY_TYPE = "processing.dma_frequency_master_curve"
DMA_DOMAIN_RUN_TYPE = "processing.common_processing_output"
DMA_METHOD_ID = "polymer.dma_frequency_master_curve"
DMA_METHOD_VERSION = "1.0.0"
DMA_PROVENANCE_CONTRACT = "issue391.dma_frequency_master_curve@1.0.0"
DMA_DERIVATION_KIND = DMA_ACTIVITY_TYPE
DMA_OUTPUT_REVISION_TYPE = "processing.common_output.revision"
DMA_TEST_DATA_REVISION_TYPE = "datasets.test_data_document.revision"
DMA_IMPORT_PROFILE_REVISION_TYPE = "datasets.import_profile.revision"
DMA_ARTIFACT_TYPE = "artifact.artifact"
DMA_NORMALIZED_ARTIFACT_ROLE = "test-data.normalized-parquet"
DMA_NORMALIZED_ARTIFACT_SCHEMA = "urn:cmp:test-data:normalized-parquet:1.1.0"
DMA_PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"
DMA_METADATA_ARTIFACT_ROLE = "processing.common-output-json"
DMA_RESULT_ARTIFACT_ROLE = "processing.dma-result-parquet"
DMA_METADATA_SCHEMA = "urn:cmp:processing:common-output:1.6.0"

# This adapter only needs the immutable Artifact identity columns while it is
# finalizing or validating the DMA graph.  Keep the narrow SQL relation local to
# this persistence adapter so one module never imports another module's private
# adapter tables.
artifact_record_table = sa.table(
    "artifact",
    sa.column("organization_id", sa.Uuid()),
    sa.column("project_id", sa.Uuid()),
    sa.column("id", sa.Uuid()),
    sa.column("classification", sa.String()),
    sa.column("artifact_kind", sa.String()),
    sa.column("artifact_role", sa.String()),
    sa.column("schema_ref", sa.String()),
    sa.column("media_type", sa.String()),
    sa.column("sha256", sa.String()),
    schema="artifact",
)


def _scope_columns() -> tuple[Any, ...]:
    return (
        sa.column("organization_id", sa.Uuid()),
        sa.column("project_id", sa.Uuid()),
        sa.column("classification", sa.String()),
    )


provenance_entity_table = sa.table(
    "entity",
    *_scope_columns(),
    sa.column("id", sa.Uuid()),
    sa.column("entity_type", sa.String()),
    sa.column("reference_kind", sa.String()),
    sa.column("reference_type", sa.String()),
    sa.column("reference_id", sa.Uuid()),
    sa.column("content_sha256", sa.String()),
    sa.column("generation_requirement", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("recorded_at", sa.DateTime(timezone=True)),
    sa.column("recorded_by", sa.Uuid()),
    sa.column("request_id", sa.Uuid()),
    sa.column("trace_id", sa.String()),
    schema="provenance",
)
provenance_activity_table = sa.table(
    "activity",
    *_scope_columns(),
    sa.column("id", sa.Uuid()),
    sa.column("activity_type", sa.String()),
    sa.column("domain_run_type", sa.String()),
    sa.column("domain_run_id", sa.Uuid()),
    sa.column("status", sa.String()),
    sa.column("input_required", sa.Boolean()),
    sa.column("output_required", sa.Boolean()),
    sa.column("started_at", sa.DateTime(timezone=True)),
    sa.column("ended_at", sa.DateTime(timezone=True)),
    sa.column("submission_digest", sa.String()),
    sa.column("recorded_at", sa.DateTime(timezone=True)),
    sa.column("recorded_by", sa.Uuid()),
    sa.column("request_id", sa.Uuid()),
    sa.column("trace_id", sa.String()),
    schema="provenance",
)
provenance_agent_table = sa.table(
    "agent",
    *_scope_columns(),
    sa.column("id", sa.Uuid()),
    sa.column("agent_type", sa.String()),
    sa.column("reference_id", sa.Uuid()),
    sa.column("recorded_at", sa.DateTime(timezone=True)),
    sa.column("recorded_by", sa.Uuid()),
    sa.column("request_id", sa.Uuid()),
    sa.column("trace_id", sa.String()),
    schema="provenance",
)


def _provenance_relation_table(name: str, *columns: Any) -> Any:
    return sa.table(
        name,
        *_scope_columns(),
        *columns,
        sa.column("recorded_at", sa.DateTime(timezone=True)),
        sa.column("recorded_by", sa.Uuid()),
        schema="provenance",
    )


provenance_usage_table = _provenance_relation_table(
    "usage",
    sa.column("activity_id", sa.Uuid()),
    sa.column("entity_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("ordinal", sa.Integer()),
)
provenance_generation_table = _provenance_relation_table(
    "generation",
    sa.column("entity_id", sa.Uuid()),
    sa.column("activity_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("generated_at", sa.DateTime(timezone=True)),
)
provenance_derivation_table = _provenance_relation_table(
    "derivation",
    sa.column("generated_entity_id", sa.Uuid()),
    sa.column("used_entity_id", sa.Uuid()),
    sa.column("activity_id", sa.Uuid()),
    sa.column("derivation_kind", sa.String()),
)
provenance_association_table = _provenance_relation_table(
    "association",
    sa.column("activity_id", sa.Uuid()),
    sa.column("agent_id", sa.Uuid()),
    sa.column("role", sa.String()),
    sa.column("plan_entity_id", sa.Uuid()),
)
provenance_attribution_table = _provenance_relation_table(
    "attribution",
    sa.column("entity_id", sa.Uuid()),
    sa.column("agent_id", sa.Uuid()),
    sa.column("role", sa.String()),
)

# Local aliases keep the graph code readable while making the ownership of each
# SQL relation explicit in this adapter.
entity_table = provenance_entity_table
activity_table = provenance_activity_table
agent_table = provenance_agent_table
usage_table = provenance_usage_table
generation_table = provenance_generation_table
derivation_table = provenance_derivation_table
association_table = provenance_association_table
attribution_table = provenance_attribution_table


class RlsContext:
    """Small structural type for the composition-root authorization binder."""

    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None: ...


def _scope(snapshot: ProcessingOutputSnapshot) -> ProvenanceScope:
    return ProvenanceScope(
        snapshot.current.scope.organization_id,
        snapshot.current.scope.project_id,
        DataClassification(snapshot.current.scope.classification),
    )


def _relation_values(
    scope: ProvenanceScope,
    *,
    recorded_at: datetime,
    recorded_by: UUID,
) -> dict[str, object]:
    return {
        "organization_id": scope.organization_id,
        "project_id": scope.project_id,
        "classification": scope.classification.value,
        "recorded_at": recorded_at,
        "recorded_by": recorded_by,
    }


def _artifact_reference(artifact: ArtifactRecord) -> ImmutableEntityReference:
    return ImmutableEntityReference(
        EntityReferenceKind.ARTIFACT,
        DMA_ARTIFACT_TYPE,
        artifact.artifact.id,
        artifact.artifact.sha256,
    )


def _revision_reference(
    reference_type: str,
    revision_id: UUID,
    sha256: str,
) -> ImmutableEntityReference:
    return ImmutableEntityReference(
        EntityReferenceKind.REVISION,
        reference_type,
        revision_id,
        sha256,
    )


def _entity_candidate(
    *,
    entity_id: UUID,
    scope: ProvenanceScope,
    entity_type: str,
    reference: ImmutableEntityReference,
    created_at: datetime,
    recorded_by: UUID,
) -> ProvenanceEntity:
    return ProvenanceEntity(
        id=entity_id,
        scope=scope,
        entity_type=entity_type,
        reference=reference,
        generation_requirement=GenerationRequirement.PRIMARY,
        created_at=created_at,
        recorded_at=created_at,
        recorded_by=recorded_by,
    )


def _scope_values(scope: ProvenanceScope) -> dict[str, object]:
    return {
        "organization_id": scope.organization_id,
        "project_id": scope.project_id,
        "classification": scope.classification.value,
    }


def _entity_values(
    entity: ProvenanceEntity,
    *,
    request_id: UUID,
    trace_id: str,
) -> dict[str, object]:
    return {
        **_scope_values(entity.scope),
        "id": entity.id,
        "entity_type": entity.entity_type,
        "reference_kind": entity.reference.kind.value,
        "reference_type": entity.reference.reference_type,
        "reference_id": entity.reference.reference_id,
        "content_sha256": entity.reference.content_sha256,
        "generation_requirement": entity.generation_requirement.value,
        "created_at": entity.created_at,
        "recorded_at": entity.recorded_at,
        "recorded_by": entity.recorded_by,
        "request_id": request_id,
        "trace_id": trace_id,
    }


def _agent_values(
    agent: ProvenanceAgent,
    *,
    request_id: UUID,
    trace_id: str,
) -> dict[str, object]:
    return {
        **_scope_values(agent.scope),
        "id": agent.id,
        "agent_type": agent.reference.agent_type.value,
        "reference_id": agent.reference.reference_id,
        "recorded_at": agent.recorded_at,
        "recorded_by": agent.recorded_by,
        "request_id": request_id,
        "trace_id": trace_id,
    }


def _entity_from_row(row: Mapping[str, object]) -> ProvenanceEntity:
    scope = ProvenanceScope(
        cast(UUID, row["organization_id"]),
        cast(UUID, row["project_id"]),
        DataClassification(str(row["classification"])),
    )
    return ProvenanceEntity(
        id=cast(UUID, row["id"]),
        scope=scope,
        entity_type=str(row["entity_type"]),
        reference=ImmutableEntityReference(
            EntityReferenceKind(str(row["reference_kind"])),
            str(row["reference_type"]),
            cast(UUID, row["reference_id"]),
            str(row["content_sha256"]),
        ),
        generation_requirement=GenerationRequirement(str(row["generation_requirement"])),
        created_at=cast(datetime, row["created_at"]),
        recorded_at=cast(datetime, row["recorded_at"]),
        recorded_by=cast(UUID, row["recorded_by"]),
    )


def _ensure_entity(
    session: Session,
    candidate: ProvenanceEntity,
    *,
    request_id: UUID,
    trace_id: str,
) -> ProvenanceEntity:
    row = (
        session.execute(
            sa.select(entity_table).where(
                entity_table.c.organization_id == candidate.scope.organization_id,
                entity_table.c.project_id == candidate.scope.project_id,
                entity_table.c.reference_kind == candidate.reference.kind.value,
                entity_table.c.reference_type == candidate.reference.reference_type,
                entity_table.c.reference_id == candidate.reference.reference_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is not None:
        existing = _entity_from_row(row)
        if (
            existing.entity_type != candidate.entity_type
            or existing.reference.content_sha256 != candidate.reference.content_sha256
            or existing.generation_requirement is not candidate.generation_requirement
            or existing.scope != candidate.scope
        ):
            raise ProvenanceConflict(
                "immutable Entity reference was already registered with different facts"
            )
        return existing
    session.execute(
        sa.insert(entity_table).values(
            _entity_values(candidate, request_id=request_id, trace_id=trace_id)
        )
    )
    return candidate


def _ensure_agent(
    session: Session,
    candidate: ProvenanceAgent,
    *,
    request_id: UUID,
    trace_id: str,
) -> ProvenanceAgent:
    row = (
        session.execute(
            sa.select(agent_table).where(
                agent_table.c.organization_id == candidate.scope.organization_id,
                agent_table.c.project_id == candidate.scope.project_id,
                agent_table.c.classification == candidate.scope.classification.value,
                agent_table.c.agent_type == candidate.reference.agent_type.value,
                agent_table.c.reference_id == candidate.reference.reference_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is not None:
        return ProvenanceAgent(
            id=cast(UUID, row["id"]),
            scope=candidate.scope,
            reference=candidate.reference,
            recorded_at=cast(datetime, row["recorded_at"]),
            recorded_by=cast(UUID, row["recorded_by"]),
        )
    session.execute(
        sa.insert(agent_table).values(
            _agent_values(candidate, request_id=request_id, trace_id=trace_id)
        )
    )
    return candidate


def _has_generation(session: Session, scope: ProvenanceScope, entity_id: UUID) -> bool:
    return (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(generation_table)
            .where(
                generation_table.c.organization_id == scope.organization_id,
                generation_table.c.project_id == scope.project_id,
                generation_table.c.classification == scope.classification.value,
                generation_table.c.entity_id == entity_id,
            )
        )
        or 0
    ) > 0


def _step_options(snapshot: ProcessingOutputSnapshot) -> Mapping[str, Any]:
    if len(snapshot.content.steps) != 1:
        raise ProvenanceConflict("DMA Processing Output must contain exactly one Processing Step")
    step = snapshot.content.steps[0]
    if step.method_id != DMA_METHOD_ID or step.method_version != DMA_METHOD_VERSION:
        raise ProvenanceConflict("DMA Processing Output method identity is not current")
    return step.options


def _input_facts(snapshot: ProcessingOutputSnapshot) -> tuple[dict[str, object], ...]:
    options = _step_options(snapshot)
    if (
        snapshot.content.governed_import_profile is None
        or snapshot.content.governed_import_profile_sha256 is None
    ):
        raise ProvenanceConflict("DMA output has no governed Import Profile pin")
    try:
        normalized_id = UUID(str(options["source_normalized_artifact_id"]))
        normalized_sha256 = str(options["source_normalized_artifact_sha256"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProvenanceConflict("DMA step lacks an exact normalized Artifact pin") from error
    return (
        {
            "logical_role": "source_test_data",
            "ordinal": 0,
            "kind": EntityReferenceKind.REVISION.value,
            "type": DMA_TEST_DATA_REVISION_TYPE,
            "id": str(snapshot.content.source_document.revision_id),
            "sha256": snapshot.content.source_document_sha256,
        },
        {
            "logical_role": "source_import_profile",
            "ordinal": 1,
            "kind": EntityReferenceKind.REVISION.value,
            "type": DMA_IMPORT_PROFILE_REVISION_TYPE,
            "id": str(snapshot.content.governed_import_profile.revision_id),
            "sha256": snapshot.content.governed_import_profile_sha256,
        },
        {
            "logical_role": "source_normalized_artifact",
            "ordinal": 2,
            "kind": EntityReferenceKind.ARTIFACT.value,
            "type": DMA_ARTIFACT_TYPE,
            "id": str(normalized_id),
            "sha256": normalized_sha256,
        },
    )


def _output_facts(
    snapshot: ProcessingOutputSnapshot,
    metadata_artifact: ArtifactRecord,
    result_artifact: ArtifactRecord,
) -> tuple[dict[str, object], ...]:
    return (
        {
            "logical_role": "output",
            "kind": EntityReferenceKind.REVISION.value,
            "type": DMA_OUTPUT_REVISION_TYPE,
            "id": str(snapshot.current.revision_id),
            "sha256": snapshot.current.content_hash,
        },
        {
            "logical_role": "metadata",
            "kind": EntityReferenceKind.ARTIFACT.value,
            "type": DMA_ARTIFACT_TYPE,
            "id": str(metadata_artifact.artifact.id),
            "sha256": metadata_artifact.artifact.sha256,
        },
        {
            "logical_role": "result",
            "kind": EntityReferenceKind.ARTIFACT.value,
            "type": DMA_ARTIFACT_TYPE,
            "id": str(result_artifact.artifact.id),
            "sha256": result_artifact.artifact.sha256,
        },
    )


def dma_submission_digest(
    snapshot: ProcessingOutputSnapshot,
    metadata_artifact: ArtifactRecord,
    result_artifact: ArtifactRecord,
) -> str:
    """Build the closed, ordered Activity submission object required by #391."""

    step = snapshot.content.steps[0]
    value = {
        "provenance_contract": DMA_PROVENANCE_CONTRACT,
        "activity_type": DMA_ACTIVITY_TYPE,
        "domain_run_type": DMA_DOMAIN_RUN_TYPE,
        "domain_run_id": str(snapshot.current.revision_id),
        "status": ActivityStatus.SUCCEEDED.value,
        "method": {"id": DMA_METHOD_ID, "version": DMA_METHOD_VERSION},
        "processing_step": {
            "method_id": step.method_id,
            "method_version": step.method_version,
            "options": step.options,
        },
        "inputs": list(_input_facts(snapshot)),
        "outputs": list(_output_facts(snapshot, metadata_artifact, result_artifact)),
    }
    return content_sha256(value)


class SqlAlchemyDmaProvenanceWriter:
    """Specialize the ordinary revision provenance graph inside its SQL transaction."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        rls_context: RlsContext,
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._sessions = session_factory
        self._rls = rls_context
        self._id_factory = id_factory

    def __call__(
        self,
        *,
        session: object,
        context: SecurityContext,
        decision: AuthorizationDecision,
        snapshot: ProcessingOutputSnapshot,
        metadata_artifact: ArtifactRecord,
        result_artifact: ArtifactRecord,
    ) -> None:
        if not isinstance(session, Session):
            raise TypeError("DMA provenance requires a SQLAlchemy Session")
        self._rls.bind_authorization(session, context, decision)
        self._write(
            session,
            context=context,
            snapshot=snapshot,
            metadata_artifact=metadata_artifact,
            result_artifact=result_artifact,
        )

    def validate(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        snapshot: ProcessingOutputSnapshot,
        metadata_artifact: ArtifactRecord,
        result_artifact: ArtifactRecord,
    ) -> None:
        """Validate the complete graph during exact Processing Output read-back."""

        with self._sessions() as session, session.begin():
            self._rls.bind_authorization(session, context, decision)
            self._validate(
                session,
                context=context,
                snapshot=snapshot,
                metadata_artifact=metadata_artifact,
                result_artifact=result_artifact,
            )

    def _agent(
        self,
        session: Session,
        scope: ProvenanceScope,
        context: SecurityContext,
        recorded_at: datetime,
    ) -> Any:
        principal = (
            session.execute(
                sa.text(
                    "SELECT principal_type, active FROM identity.principal WHERE id = :principal_id"
                ),
                {"principal_id": context.principal.id},
            )
            .mappings()
            .one_or_none()
        )
        if (
            principal is None
            or not bool(principal["active"])
            or principal["principal_type"] not in {AgentType.USER.value, AgentType.SERVICE.value}
        ):
            raise ProvenanceConflict("DMA creator is not an active user or service Agent")
        return _ensure_agent(
            session,
            ProvenanceAgent(
                id=self._id_factory(),
                scope=scope,
                reference=AgentReference(
                    AgentType(str(principal["principal_type"])), context.principal.id
                ),
                recorded_at=recorded_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )

    def _ensure_revision_input(
        self,
        session: Session,
        *,
        scope: ProvenanceScope,
        reference_type: str,
        revision_id: UUID,
        sha256: str,
        snapshot: ProcessingOutputSnapshot,
        context: SecurityContext,
    ) -> ProvenanceEntity:
        entity = _ensure_entity(
            session,
            _entity_candidate(
                entity_id=self._id_factory(),
                scope=scope,
                entity_type=reference_type,
                reference=_revision_reference(reference_type, revision_id, sha256),
                created_at=snapshot.current.created_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        if not _has_generation(session, scope, entity.id):
            raise ProvenanceConflict(
                f"source revision Entity {reference_type}:{revision_id} has no primary generation"
            )
        return entity

    @staticmethod
    def _validate_artifact(
        session: Session,
        *,
        scope: ProvenanceScope,
        artifact_id: UUID,
        sha256: str,
        artifact_kind: str,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
    ) -> None:
        row = (
            session.execute(
                sa.select(artifact_record_table).where(
                    artifact_record_table.c.organization_id == scope.organization_id,
                    artifact_record_table.c.project_id == scope.project_id,
                    artifact_record_table.c.classification == scope.classification.value,
                    artifact_record_table.c.id == artifact_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (
            row["artifact_kind"] != artifact_kind
            or row["artifact_role"] != artifact_role
            or row["schema_ref"] != schema_ref
            or row["media_type"] != media_type
            or row["sha256"] != sha256
        ):
            raise ProvenanceConflict("DMA Artifact pin, scope, or classification is invalid")

    @staticmethod
    def _validate_output_artifact(
        artifact: ArtifactRecord,
        *,
        scope: ProvenanceScope,
        artifact_id: UUID | None,
        sha256: str | None,
        artifact_role: str,
        schema_ref: str,
        media_type: str,
    ) -> None:
        if artifact_id is None or sha256 is None:
            raise ProvenanceConflict("DMA Processing Output Artifact pin is incomplete")
        value = artifact.artifact
        if (
            value.id != artifact_id
            or value.organization_id != scope.organization_id
            or value.project_id != scope.project_id
            or value.classification != scope.classification
            or value.artifact_kind.value != "derived"
            or value.artifact_role != artifact_role
            or value.schema_ref != schema_ref
            or value.media_type != media_type
            or value.sha256 != sha256
        ):
            raise ProvenanceConflict("DMA output Artifact pin, scope, or classification drifted")

    def _ensure_artifact_input(
        self,
        session: Session,
        *,
        scope: ProvenanceScope,
        artifact_id: UUID,
        sha256: str,
        created_at: datetime,
        context: SecurityContext,
        snapshot: ProcessingOutputSnapshot,
        agent: Any,
    ) -> ProvenanceEntity:
        entity = _ensure_entity(
            session,
            _entity_candidate(
                entity_id=self._id_factory(),
                scope=scope,
                entity_type=DMA_ARTIFACT_TYPE,
                reference=ImmutableEntityReference(
                    EntityReferenceKind.ARTIFACT,
                    DMA_ARTIFACT_TYPE,
                    artifact_id,
                    sha256,
                ),
                created_at=created_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        if _has_generation(session, scope, entity.id):
            return entity

        # The general Artifact service intentionally has no provenance side effect.  If an
        # imported normalized Artifact predates this unit, close its own primary generation
        # with a narrow source-materialization activity.  This is not an artifact.registration
        # activity and is never used for either DMA output Artifact.
        activity_id = self._id_factory()
        relation_base = _relation_values(
            scope,
            recorded_at=snapshot.current.created_at,
            recorded_by=context.principal.id,
        )
        session.execute(
            sa.insert(activity_table).values(
                **{
                    **{
                        "organization_id": scope.organization_id,
                        "project_id": scope.project_id,
                        "classification": scope.classification.value,
                    },
                    "id": activity_id,
                    "activity_type": "processing.dma_source_artifact",
                    "domain_run_type": "processing.dma_source_artifact",
                    "domain_run_id": artifact_id,
                    "status": ActivityStatus.SUCCEEDED.value,
                    "input_required": False,
                    "output_required": True,
                    "started_at": snapshot.current.created_at,
                    "ended_at": snapshot.current.created_at,
                    "submission_digest": content_sha256(
                        {
                            "activity_type": "processing.dma_source_artifact",
                            "artifact_id": str(artifact_id),
                            "sha256": sha256,
                        }
                    ),
                    "recorded_at": snapshot.current.created_at,
                    "recorded_by": context.principal.id,
                    "request_id": context.request_id,
                    "trace_id": context.trace_id,
                }
            )
        )
        session.execute(
            sa.insert(association_table).values(
                **relation_base,
                activity_id=activity_id,
                agent_id=agent.id,
                role="author",
                plan_entity_id=None,
            )
        )
        session.execute(
            sa.insert(generation_table).values(
                **relation_base,
                entity_id=entity.id,
                activity_id=activity_id,
                role="primary",
                generated_at=snapshot.current.created_at,
            )
        )
        session.execute(
            sa.insert(attribution_table).values(
                **relation_base,
                entity_id=entity.id,
                agent_id=agent.id,
                role="author",
            )
        )
        return entity

    def _ensure_output_entity(
        self,
        session: Session,
        *,
        scope: ProvenanceScope,
        snapshot: ProcessingOutputSnapshot,
        reference: ImmutableEntityReference,
        created_at: datetime,
        context: SecurityContext,
    ) -> ProvenanceEntity:
        entity = _ensure_entity(
            session,
            _entity_candidate(
                entity_id=self._id_factory(),
                scope=scope,
                entity_type=reference.reference_type,
                reference=reference,
                created_at=created_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        return entity

    def _write(
        self,
        session: Session,
        *,
        context: SecurityContext,
        snapshot: ProcessingOutputSnapshot,
        metadata_artifact: ArtifactRecord,
        result_artifact: ArtifactRecord,
    ) -> None:
        scope = _scope(snapshot)
        current = snapshot.current
        if current.created_by != context.principal.id:
            raise ProvenanceConflict("DMA revision creator differs from the active principal")
        if metadata_artifact.artifact.id != snapshot.content.output_artifact_id:
            raise ProvenanceConflict("DMA metadata Artifact pin differs from Processing Output")
        if result_artifact.artifact.id != snapshot.content.result_artifact_id:
            raise ProvenanceConflict("DMA result Artifact pin differs from Processing Output")
        self._validate_output_artifact(
            metadata_artifact,
            scope=scope,
            artifact_id=snapshot.content.output_artifact_id,
            sha256=snapshot.content.output_sha256,
            artifact_role=DMA_METADATA_ARTIFACT_ROLE,
            schema_ref=DMA_METADATA_SCHEMA,
            media_type="application/vnd.cmp.processing-output+json",
        )
        self._validate_output_artifact(
            result_artifact,
            scope=scope,
            artifact_id=snapshot.content.result_artifact_id,
            sha256=snapshot.content.result_sha256,
            artifact_role=DMA_RESULT_ARTIFACT_ROLE,
            schema_ref=snapshot.content.result_schema_ref or "",
            media_type=snapshot.content.result_media_type or DMA_PARQUET_MEDIA_TYPE,
        )

        agent = self._agent(session, scope, context, current.created_at)
        source_test_data = self._ensure_revision_input(
            session,
            scope=scope,
            reference_type=DMA_TEST_DATA_REVISION_TYPE,
            revision_id=snapshot.content.source_document.revision_id,
            sha256=snapshot.content.source_document_sha256,
            snapshot=snapshot,
            context=context,
        )
        if snapshot.content.governed_import_profile is None:
            raise ProvenanceConflict("DMA output has no governed Import Profile pin")
        source_profile = self._ensure_revision_input(
            session,
            scope=scope,
            reference_type=DMA_IMPORT_PROFILE_REVISION_TYPE,
            revision_id=snapshot.content.governed_import_profile.revision_id,
            sha256=snapshot.content.governed_import_profile_sha256 or "",
            snapshot=snapshot,
            context=context,
        )
        options = _step_options(snapshot)
        try:
            source_artifact_id = UUID(str(options["source_normalized_artifact_id"]))
            source_artifact_sha256 = str(options["source_normalized_artifact_sha256"])
        except (KeyError, TypeError, ValueError) as error:
            raise ProvenanceConflict("DMA step lacks a valid normalized Artifact id") from error
        if source_artifact_id.int == 0:
            raise ProvenanceConflict("DMA step lacks a non-zero normalized Artifact pin")
        self._validate_artifact(
            session,
            scope=scope,
            artifact_id=source_artifact_id,
            sha256=source_artifact_sha256,
            artifact_kind="derived",
            artifact_role=DMA_NORMALIZED_ARTIFACT_ROLE,
            schema_ref=DMA_NORMALIZED_ARTIFACT_SCHEMA,
            media_type=DMA_PARQUET_MEDIA_TYPE,
        )
        source_artifact = self._ensure_artifact_input(
            session,
            scope=scope,
            artifact_id=source_artifact_id,
            sha256=source_artifact_sha256,
            created_at=current.created_at,
            context=context,
            snapshot=snapshot,
            agent=agent,
        )
        output_revision = self._ensure_output_entity(
            session,
            scope=scope,
            snapshot=snapshot,
            reference=_revision_reference(
                DMA_OUTPUT_REVISION_TYPE,
                current.revision_id,
                current.content_hash,
            ),
            created_at=current.created_at,
            context=context,
        )
        metadata_entity = self._ensure_output_entity(
            session,
            scope=scope,
            snapshot=snapshot,
            reference=_artifact_reference(metadata_artifact),
            created_at=metadata_artifact.artifact.created_at,
            context=context,
        )
        result_entity = self._ensure_output_entity(
            session,
            scope=scope,
            snapshot=snapshot,
            reference=_artifact_reference(result_artifact),
            created_at=result_artifact.artifact.created_at,
            context=context,
        )
        input_entities = (source_test_data, source_profile, source_artifact)
        output_entities = (output_revision, metadata_entity, result_entity)

        activity_row = (
            session.execute(
                sa.select(activity_table)
                .where(
                    activity_table.c.organization_id == scope.organization_id,
                    activity_table.c.project_id == scope.project_id,
                    activity_table.c.domain_run_id == current.revision_id,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if activity_row is None:
            raise ProvenanceConflict("ordinary output revision provenance Activity is missing")
        activity_id = cast(UUID, activity_row["id"])
        if activity_row["recorded_by"] != context.principal.id:
            raise ProvenanceConflict(
                "revision provenance Activity has another responsible principal"
            )
        if activity_row["request_id"] != context.request_id:
            raise ProvenanceConflict("revision provenance Activity belongs to another request")
        digest = dma_submission_digest(snapshot, metadata_artifact, result_artifact)
        if activity_row["activity_type"] == DMA_ACTIVITY_TYPE:
            if activity_row["submission_digest"] != digest:
                raise ProvenanceConflict("DMA provenance Activity digest is immutable")
        elif activity_row["activity_type"] == "core.revision_commit":
            session.execute(
                sa.update(activity_table)
                .where(
                    activity_table.c.organization_id == scope.organization_id,
                    activity_table.c.project_id == scope.project_id,
                    activity_table.c.id == activity_id,
                )
                .values(
                    activity_type=DMA_ACTIVITY_TYPE,
                    domain_run_type=DMA_DOMAIN_RUN_TYPE,
                    status=ActivityStatus.SUCCEEDED.value,
                    input_required=True,
                    output_required=True,
                    submission_digest=digest,
                )
            )
        else:
            raise ProvenanceConflict("output revision provenance Activity has an incompatible type")

        self._ensure_single_author(session, scope, activity_id, agent.id)
        for ordinal, (entity, fact) in enumerate(
            zip(input_entities, _input_facts(snapshot), strict=True)
        ):
            self._ensure_usage(
                session,
                scope=scope,
                activity_id=activity_id,
                entity_id=entity.id,
                role=str(fact["logical_role"]),
                ordinal=ordinal,
                recorded_at=current.created_at,
                recorded_by=context.principal.id,
            )
        for entity in output_entities:
            self._ensure_generation(
                session,
                scope=scope,
                activity_id=activity_id,
                entity_id=entity.id,
                role="primary",
                generated_at=current.created_at,
                recorded_at=current.created_at,
                recorded_by=context.principal.id,
            )
            self._ensure_attribution(
                session,
                scope=scope,
                entity_id=entity.id,
                agent_id=agent.id,
                role="author",
                recorded_at=current.created_at,
                recorded_by=context.principal.id,
            )
            for used in input_entities:
                self._ensure_derivation(
                    session,
                    scope=scope,
                    activity_id=activity_id,
                    generated_entity_id=entity.id,
                    used_entity_id=used.id,
                    recorded_at=current.created_at,
                    recorded_by=context.principal.id,
                )
        self._validate(
            session,
            context=context,
            snapshot=snapshot,
            metadata_artifact=metadata_artifact,
            result_artifact=result_artifact,
        )

    @staticmethod
    def _ensure_single_author(
        session: Session,
        scope: ProvenanceScope,
        activity_id: UUID,
        agent_id: UUID,
    ) -> None:
        rows = session.execute(
            sa.select(association_table.c.agent_id, association_table.c.role).where(
                association_table.c.organization_id == scope.organization_id,
                association_table.c.project_id == scope.project_id,
                association_table.c.classification == scope.classification.value,
                association_table.c.activity_id == activity_id,
            )
        ).all()
        if len(rows) != 1 or rows[0].agent_id != agent_id or rows[0].role != "author":
            raise ProvenanceConflict("DMA revision Activity must have exactly one author Agent")

    @staticmethod
    def _ensure_usage(
        session: Session,
        *,
        scope: ProvenanceScope,
        activity_id: UUID,
        entity_id: UUID,
        role: str,
        ordinal: int,
        recorded_at: datetime,
        recorded_by: UUID,
    ) -> None:
        row = (
            session.execute(
                sa.select(usage_table).where(
                    usage_table.c.organization_id == scope.organization_id,
                    usage_table.c.project_id == scope.project_id,
                    usage_table.c.classification == scope.classification.value,
                    usage_table.c.activity_id == activity_id,
                    usage_table.c.role == role,
                    usage_table.c.ordinal == ordinal,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            if row["entity_id"] != entity_id:
                raise ProvenanceConflict("DMA input usage position is immutable")
            return
        session.execute(
            sa.insert(usage_table).values(
                **_relation_values(scope, recorded_at=recorded_at, recorded_by=recorded_by),
                activity_id=activity_id,
                entity_id=entity_id,
                role=role,
                ordinal=ordinal,
            )
        )

    @staticmethod
    def _ensure_generation(
        session: Session,
        *,
        scope: ProvenanceScope,
        activity_id: UUID,
        entity_id: UUID,
        role: str,
        generated_at: datetime,
        recorded_at: datetime,
        recorded_by: UUID,
    ) -> None:
        rows = session.execute(
            sa.select(generation_table.c.activity_id, generation_table.c.role).where(
                generation_table.c.organization_id == scope.organization_id,
                generation_table.c.project_id == scope.project_id,
                generation_table.c.classification == scope.classification.value,
                generation_table.c.entity_id == entity_id,
            )
        ).all()
        if rows:
            if len(rows) != 1 or rows[0].activity_id != activity_id or rows[0].role != role:
                raise ProvenanceConflict(
                    "DMA output Entity generation is not the current primary generation"
                )
            return
        session.execute(
            sa.insert(generation_table).values(
                **_relation_values(scope, recorded_at=recorded_at, recorded_by=recorded_by),
                entity_id=entity_id,
                activity_id=activity_id,
                role=role,
                generated_at=generated_at,
            )
        )

    @staticmethod
    def _ensure_attribution(
        session: Session,
        *,
        scope: ProvenanceScope,
        entity_id: UUID,
        agent_id: UUID,
        role: str,
        recorded_at: datetime,
        recorded_by: UUID,
    ) -> None:
        rows = session.execute(
            sa.select(attribution_table.c.agent_id, attribution_table.c.role).where(
                attribution_table.c.organization_id == scope.organization_id,
                attribution_table.c.project_id == scope.project_id,
                attribution_table.c.classification == scope.classification.value,
                attribution_table.c.entity_id == entity_id,
            )
        ).all()
        if rows:
            if len(rows) != 1 or rows[0].agent_id != agent_id or rows[0].role != role:
                raise ProvenanceConflict("DMA output Entity attribution is immutable")
            return
        session.execute(
            sa.insert(attribution_table).values(
                **_relation_values(scope, recorded_at=recorded_at, recorded_by=recorded_by),
                entity_id=entity_id,
                agent_id=agent_id,
                role=role,
            )
        )

    @staticmethod
    def _ensure_derivation(
        session: Session,
        *,
        scope: ProvenanceScope,
        activity_id: UUID,
        generated_entity_id: UUID,
        used_entity_id: UUID,
        recorded_at: datetime,
        recorded_by: UUID,
    ) -> None:
        row = (
            session.execute(
                sa.select(derivation_table).where(
                    derivation_table.c.organization_id == scope.organization_id,
                    derivation_table.c.project_id == scope.project_id,
                    derivation_table.c.classification == scope.classification.value,
                    derivation_table.c.generated_entity_id == generated_entity_id,
                    derivation_table.c.used_entity_id == used_entity_id,
                    derivation_table.c.derivation_kind == DMA_DERIVATION_KIND,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            if row["activity_id"] != activity_id:
                raise ProvenanceConflict("DMA derivation is attached to another Activity")
            return
        session.execute(
            sa.insert(derivation_table).values(
                **_relation_values(scope, recorded_at=recorded_at, recorded_by=recorded_by),
                generated_entity_id=generated_entity_id,
                used_entity_id=used_entity_id,
                activity_id=activity_id,
                derivation_kind=DMA_DERIVATION_KIND,
            )
        )

    def _validate(
        self,
        session: Session,
        *,
        context: SecurityContext,
        snapshot: ProcessingOutputSnapshot,
        metadata_artifact: ArtifactRecord,
        result_artifact: ArtifactRecord,
    ) -> None:
        scope = _scope(snapshot)
        current = snapshot.current
        self._validate_output_artifact(
            metadata_artifact,
            scope=scope,
            artifact_id=snapshot.content.output_artifact_id,
            sha256=snapshot.content.output_sha256,
            artifact_role=DMA_METADATA_ARTIFACT_ROLE,
            schema_ref=DMA_METADATA_SCHEMA,
            media_type="application/vnd.cmp.processing-output+json",
        )
        self._validate_output_artifact(
            result_artifact,
            scope=scope,
            artifact_id=snapshot.content.result_artifact_id,
            sha256=snapshot.content.result_sha256,
            artifact_role=DMA_RESULT_ARTIFACT_ROLE,
            schema_ref=snapshot.content.result_schema_ref
            if snapshot.content.result_schema_ref is not None
            else "",
            media_type=snapshot.content.result_media_type
            if snapshot.content.result_media_type is not None
            else "",
        )
        options = _step_options(snapshot)
        try:
            source_artifact_id = UUID(str(options["source_normalized_artifact_id"]))
            source_artifact_sha256 = str(options["source_normalized_artifact_sha256"])
        except (KeyError, TypeError, ValueError) as error:
            raise ProvenanceConflict("DMA step lacks a valid normalized Artifact pin") from error
        if source_artifact_id.int == 0:
            raise ProvenanceConflict("DMA step lacks a non-zero normalized Artifact pin")
        self._validate_artifact(
            session,
            scope=scope,
            artifact_id=source_artifact_id,
            sha256=source_artifact_sha256,
            artifact_kind="derived",
            artifact_role=DMA_NORMALIZED_ARTIFACT_ROLE,
            schema_ref=DMA_NORMALIZED_ARTIFACT_SCHEMA,
            media_type=DMA_PARQUET_MEDIA_TYPE,
        )
        activity_rows = (
            session.execute(
                sa.select(activity_table).where(
                    activity_table.c.organization_id == scope.organization_id,
                    activity_table.c.project_id == scope.project_id,
                    activity_table.c.classification == scope.classification.value,
                    activity_table.c.domain_run_type == DMA_DOMAIN_RUN_TYPE,
                    activity_table.c.domain_run_id == current.revision_id,
                )
            )
            .mappings()
            .all()
        )
        if len(activity_rows) != 1:
            raise ProvenanceConflict(
                "DMA Processing Output must have exactly one terminal Activity"
            )
        activity = activity_rows[0]
        if (
            activity["activity_type"] != DMA_ACTIVITY_TYPE
            or activity["status"] != ActivityStatus.SUCCEEDED.value
            or not activity["input_required"]
            or not activity["output_required"]
            or activity["recorded_by"] != current.created_by
            or activity["request_id"] != current.request_id
            or activity["trace_id"] != current.trace_id
            or activity["submission_digest"]
            != dma_submission_digest(snapshot, metadata_artifact, result_artifact)
        ):
            raise ProvenanceConflict("DMA terminal Activity facts or digest drifted")
        activity_id = cast(UUID, activity["id"])
        source_facts = _input_facts(snapshot)
        output_facts = _output_facts(snapshot, metadata_artifact, result_artifact)
        expected_input_ids = tuple(
            self._entity_id_for_fact(session, scope, item) for item in source_facts
        )
        expected_output_ids = tuple(
            self._entity_id_for_fact(session, scope, item) for item in output_facts
        )
        usage_rows = session.execute(
            sa.select(usage_table.c.entity_id, usage_table.c.role, usage_table.c.ordinal).where(
                usage_table.c.organization_id == scope.organization_id,
                usage_table.c.project_id == scope.project_id,
                usage_table.c.classification == scope.classification.value,
                usage_table.c.activity_id == activity_id,
            )
        ).all()
        if len(usage_rows) != 3:
            raise ProvenanceConflict("DMA Activity must have exactly three ordered inputs")
        expected_roles = tuple(str(item["logical_role"]) for item in source_facts)
        usage_by_ordinal = sorted(usage_rows, key=lambda row: int(row.ordinal))
        if (
            tuple(row.entity_id for row in usage_by_ordinal) != expected_input_ids
            or tuple(row.role for row in usage_by_ordinal) != expected_roles
            or tuple(int(row.ordinal) for row in usage_by_ordinal) != (0, 1, 2)
        ):
            raise ProvenanceConflict("DMA Activity input usage roles or ordinals drifted")
        generation_rows = session.execute(
            sa.select(generation_table.c.entity_id, generation_table.c.role).where(
                generation_table.c.organization_id == scope.organization_id,
                generation_table.c.project_id == scope.project_id,
                generation_table.c.classification == scope.classification.value,
                generation_table.c.activity_id == activity_id,
            )
        ).all()
        if (
            len(generation_rows) != 3
            or {row.entity_id for row in generation_rows} != set(expected_output_ids)
            or any(row.role != "primary" for row in generation_rows)
        ):
            raise ProvenanceConflict("DMA Activity output generations drifted")
        association_rows = session.execute(
            sa.select(association_table.c.agent_id, association_table.c.role).where(
                association_table.c.organization_id == scope.organization_id,
                association_table.c.project_id == scope.project_id,
                association_table.c.classification == scope.classification.value,
                association_table.c.activity_id == activity_id,
            )
        ).all()
        if len(association_rows) != 1 or association_rows[0].role != "author":
            raise ProvenanceConflict("DMA Activity author association cardinality drifted")
        agent_row = session.execute(
            sa.select(agent_table.c.agent_type, agent_table.c.reference_id).where(
                agent_table.c.organization_id == scope.organization_id,
                agent_table.c.project_id == scope.project_id,
                agent_table.c.classification == scope.classification.value,
                agent_table.c.id == association_rows[0].agent_id,
            )
        ).first()
        if (
            agent_row is None
            or agent_row.reference_id != context.principal.id
            or agent_row.agent_type
            not in {
                AgentType.USER.value,
                AgentType.SERVICE.value,
            }
        ):
            raise ProvenanceConflict("DMA Activity author is not the actual user/service Agent")
        attribution_rows = session.execute(
            sa.select(
                attribution_table.c.entity_id,
                attribution_table.c.agent_id,
                attribution_table.c.role,
            ).where(
                attribution_table.c.organization_id == scope.organization_id,
                attribution_table.c.project_id == scope.project_id,
                attribution_table.c.classification == scope.classification.value,
                attribution_table.c.agent_id == association_rows[0].agent_id,
                attribution_table.c.role == "author",
                attribution_table.c.entity_id.in_(expected_output_ids),
            )
        ).all()
        if len(attribution_rows) != 3 or {row.entity_id for row in attribution_rows} != set(
            expected_output_ids
        ):
            raise ProvenanceConflict("DMA output attributions drifted")
        derivation_rows = session.execute(
            sa.select(
                derivation_table.c.generated_entity_id,
                derivation_table.c.used_entity_id,
                derivation_table.c.activity_id,
                derivation_table.c.derivation_kind,
            ).where(
                derivation_table.c.organization_id == scope.organization_id,
                derivation_table.c.project_id == scope.project_id,
                derivation_table.c.classification == scope.classification.value,
                derivation_table.c.activity_id == activity_id,
                derivation_table.c.derivation_kind == DMA_DERIVATION_KIND,
            )
        ).all()
        expected_derivations = {
            (output_id, input_id)
            for output_id in expected_output_ids
            for input_id in expected_input_ids
        }
        if (
            len(derivation_rows) != 9
            or {(row.generated_entity_id, row.used_entity_id) for row in derivation_rows}
            != expected_derivations
        ):
            raise ProvenanceConflict("DMA derivation cardinality or scope drifted")
        self._validate_entities(
            session,
            scope=scope,
            snapshot=snapshot,
            metadata_artifact=metadata_artifact,
            result_artifact=result_artifact,
            expected_input_ids=expected_input_ids,
            expected_output_ids=expected_output_ids,
        )

    @staticmethod
    def _entity_id_for_fact(
        session: Session,
        scope: ProvenanceScope,
        fact: Mapping[str, object],
    ) -> UUID:
        try:
            reference_id = UUID(str(fact["id"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ProvenanceConflict("DMA provenance fact has an invalid immutable id") from error
        entity_id = session.scalar(
            sa.select(entity_table.c.id).where(
                entity_table.c.organization_id == scope.organization_id,
                entity_table.c.project_id == scope.project_id,
                entity_table.c.classification == scope.classification.value,
                entity_table.c.reference_kind == fact["kind"],
                entity_table.c.reference_type == fact["type"],
                entity_table.c.reference_id == reference_id,
            )
        )
        if entity_id is None:
            raise ProvenanceConflict("DMA provenance graph is missing an immutable Entity")
        return cast(UUID, entity_id)

    @staticmethod
    def _validate_entities(
        session: Session,
        *,
        scope: ProvenanceScope,
        snapshot: ProcessingOutputSnapshot,
        metadata_artifact: ArtifactRecord,
        result_artifact: ArtifactRecord,
        expected_input_ids: tuple[UUID, ...],
        expected_output_ids: tuple[UUID, ...],
    ) -> None:
        rows = session.execute(
            sa.select(
                entity_table.c.id,
                entity_table.c.entity_type,
                entity_table.c.reference_kind,
                entity_table.c.reference_type,
                entity_table.c.reference_id,
                entity_table.c.content_sha256,
                entity_table.c.generation_requirement,
            ).where(
                entity_table.c.organization_id == scope.organization_id,
                entity_table.c.project_id == scope.project_id,
                entity_table.c.classification == scope.classification.value,
                entity_table.c.id.in_(expected_input_ids + expected_output_ids),
            )
        ).all()
        if len(rows) != 6:
            raise ProvenanceConflict("DMA graph is missing an immutable Entity")
        row_by_id = {row.id: row for row in rows}
        if any(row.generation_requirement != GenerationRequirement.PRIMARY.value for row in rows):
            raise ProvenanceConflict("DMA graph contains a non-primary Entity")
        source_facts = _input_facts(snapshot)
        output_facts = _output_facts(snapshot, metadata_artifact, result_artifact)
        for expected, entity_id in zip(source_facts, expected_input_ids, strict=True):
            row = row_by_id.get(entity_id)
            if row is None or (
                row.entity_type != expected["type"]
                or row.reference_kind != expected["kind"]
                or row.reference_type != expected["type"]
                or str(row.reference_id) != expected["id"]
                or row.content_sha256 != expected["sha256"]
            ):
                raise ProvenanceConflict("DMA input Entity facts drifted")
        for expected, entity_id in zip(output_facts, expected_output_ids, strict=True):
            row = row_by_id.get(entity_id)
            if row is None or (
                row.entity_type != expected["type"]
                or row.reference_kind != expected["kind"]
                or row.reference_type != expected["type"]
                or str(row.reference_id) != expected["id"]
                or row.content_sha256 != expected["sha256"]
            ):
                raise ProvenanceConflict("DMA output Entity facts drifted")
