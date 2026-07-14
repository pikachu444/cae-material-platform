"""Compose the bounded non-production T-27 Validation service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.modules.artifacts.application.content import ArtifactService
from cmp.modules.audit.adapters.persistence.repository import (
    SqlAlchemyAuditWriter,
    SqlAlchemyRevisionAuditHook,
)
from cmp.modules.audit.domain.model import (
    AuditActorType,
    AuditEventDraft,
    AuditOutcome,
    AuditScope,
    redact_ip_or_client,
)
from cmp.modules.datasets.application.service import (
    DATASET_SELECTION_AGGREGATE_TYPE,
    DatasetService,
)
from cmp.modules.exporting.application.service import (
    SOLVER_CARD_AGGREGATE_TYPE,
    SolverCardService,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import (
    MATERIAL_MODEL_AGGREGATE_TYPE,
    MaterialModelService,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
    SqlAlchemyRevisionProvenanceHook,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    activity_table as provenance_activity_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    association_table as provenance_association_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    derivation_table as provenance_derivation_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    entity_table as provenance_entity_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    generation_table as provenance_generation_table,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    usage_table as provenance_usage_table,
)
from cmp.modules.provenance.domain.model import (
    ActivityStatus,
    AgentReference,
    AgentType,
    EntityReferenceKind,
    GenerationRequirement,
    ImmutableEntityReference,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceConflict,
    ProvenanceEntity,
    ProvenanceScope,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.validation.adapters.persistence.repository import SqlAlchemyValidationRepository
from cmp.modules.validation.application.service import (
    VALIDATION_PLAN_AGGREGATE_TYPE,
    VALIDATION_TEMPLATE_AGGREGATE_TYPE,
    ReferenceValidationService,
    ValidationRun,
    ValidationRunResultManifest,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    ValidationArtifactReference,
    ValidationRunStatus,
)
from cmp.shared.domain.revisions import content_sha256

_metadata = sa.MetaData()
_artifact_table = sa.Table(
    "artifact",
    _metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("sha256", sa.CHAR(64), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    schema="artifact",
)


def _required_revision_entity_id(
    session: Session,
    scope: ProvenanceScope,
    *,
    aggregate_type: str,
    revision_id: UUID,
) -> UUID:
    entity_id = session.scalar(
        sa.select(provenance_entity_table.c.id).where(
            provenance_entity_table.c.organization_id == scope.organization_id,
            provenance_entity_table.c.project_id == scope.project_id,
            provenance_entity_table.c.classification == scope.classification.value,
            provenance_entity_table.c.reference_kind == EntityReferenceKind.REVISION.value,
            provenance_entity_table.c.reference_type == f"{aggregate_type}.revision",
            provenance_entity_table.c.reference_id == revision_id,
        )
    )
    if entity_id is None:
        raise ProvenanceConflict(
            "Validation requires complete provenance for every pinned revision"
        )
    return cast(UUID, entity_id)


class SqlReferenceValidationRunAuditHook:
    """Write T-05 audit facts from the composed Validation run transaction."""

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory
        self._writer = SqlAlchemyAuditWriter()

    def __call__(
        self,
        session: Session,
        context: SecurityContext,
        run_id: UUID,
        action: str,
        reason: str,
        occurred_at: datetime,
    ) -> None:
        principal_type = session.scalar(
            sa.text("SELECT current_setting('cmp.principal_type', true)")
        )
        if principal_type not in {"user", "service"}:
            raise ProvenanceConflict("Validation audit principal type is unavailable")
        self._writer.append(
            session,
            AuditEventDraft(
                id=self._id_factory(),
                scope=AuditScope(context.organization_id, context.project_id),
                occurred_at=occurred_at,
                actor_type=AuditActorType(str(principal_type)),
                actor_id=context.principal.id,
                action=action,
                target_type="validation.run",
                target_id=run_id,
                outcome=AuditOutcome.SUCCESS,
                request_id=context.request_id,
                trace_id=context.trace_id,
                ip_or_client=redact_ip_or_client(None),
                reason=reason,
            ),
        )


class SqlReferenceValidationRunProvenanceHook:
    """Atomically attach one terminal T-27 Result Manifest graph in the composing layer.

    Validation owns its typed run records and Provenance owns graph persistence.  This hook is
    deliberately composed here, rather than letting either bounded module import the other's
    private persistence layer.  Every generated deck/log/native/manifest Artifact receives one
    immutable generation relation in the same transaction as the terminal Run projection.
    """

    def __init__(self, *, id_factory: Callable[[], UUID] = uuid4) -> None:
        self._id_factory = id_factory

    def __call__(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
        run: ValidationRun,
        manifest: ValidationRunResultManifest,
        terminal_status: ValidationRunStatus,
        ended_at: datetime,
    ) -> None:
        del decision
        if terminal_status not in {ValidationRunStatus.SUCCEEDED, ValidationRunStatus.FAILED}:
            raise ProvenanceConflict("terminal Validation provenance requires a Result Manifest")
        if (
            manifest.content.validation_run_id != run.id
            or manifest.created_by != context.principal.id
        ):
            raise ProvenanceConflict(
                "Validation Result Manifest provenance actor or run is inconsistent"
            )
        scope = ProvenanceScope(
            context.organization_id,
            context.project_id,
            run.classification,
        )
        started_at = run.started_at or run.submitted_at
        activity_ended_at = max(started_at, ended_at, manifest.created_at)
        source_entities = {
            "validation_plan": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=VALIDATION_PLAN_AGGREGATE_TYPE,
                revision_id=run.plan_revision_id,
            ),
            "validation_template": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=VALIDATION_TEMPLATE_AGGREGATE_TYPE,
                revision_id=run.template_revision_id,
            ),
            "material_model": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
                revision_id=run.material_model_revision_id,
            ),
            "solver_card": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
                revision_id=run.solver_card_revision_id,
            ),
            "experimental_selection": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=DATASET_SELECTION_AGGREGATE_TYPE,
                revision_id=run.experimental_selection_revision_id,
            ),
        }
        outputs: list[tuple[str, str, ValidationArtifactReference]] = [
            ("solver_deck", "validation.solver_deck", manifest.content.deck),
            ("runner_stdout", "validation.runner_stdout", manifest.content.stdout),
            ("runner_stderr", "validation.runner_stderr", manifest.content.stderr),
            (
                "result_manifest",
                "validation.run_result_manifest",
                manifest.manifest_artifact,
            ),
        ]
        if manifest.content.native_result is not None:
            outputs.append(
                (
                    "native_solver_result",
                    "validation.native_solver_result",
                    manifest.content.native_result,
                )
            )
        output_entities: dict[str, UUID] = {}
        for role, entity_type, reference in outputs:
            artifact_row = (
                session.execute(
                    sa.select(_artifact_table.c.created_at, _artifact_table.c.sha256).where(
                        _artifact_table.c.organization_id == scope.organization_id,
                        _artifact_table.c.project_id == scope.project_id,
                        _artifact_table.c.classification == scope.classification.value,
                        _artifact_table.c.id == reference.artifact_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if artifact_row is None or str(artifact_row["sha256"]) != reference.sha256:
                raise ProvenanceConflict(
                    "Validation output Artifact is not visible with its declared digest"
                )
            entity = SqlAlchemyProvenanceRepository._ensure_entity(
                session,
                ProvenanceEntity(
                    id=self._id_factory(),
                    scope=scope,
                    entity_type=entity_type,
                    reference=ImmutableEntityReference(
                        EntityReferenceKind.ARTIFACT,
                        "artifact.artifact",
                        reference.artifact_id,
                        reference.sha256,
                    ),
                    generation_requirement=GenerationRequirement.PRIMARY,
                    created_at=cast(datetime, artifact_row["created_at"]),
                    recorded_at=activity_ended_at,
                    recorded_by=context.principal.id,
                ),
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
            output_entities[role] = entity.id
        principal_type = session.scalar(
            sa.text("SELECT principal_type FROM identity.principal WHERE id = :principal_id"),
            {"principal_id": context.principal.id},
        )
        if principal_type not in {"user", "service"}:
            raise ProvenanceConflict("Validation collector is not an active provenance Agent")
        agent = SqlAlchemyProvenanceRepository._ensure_agent(
            session,
            ProvenanceAgent(
                id=self._id_factory(),
                scope=scope,
                reference=AgentReference(AgentType(str(principal_type)), context.principal.id),
                recorded_at=activity_ended_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        activity_status = (
            ActivityStatus.SUCCEEDED
            if terminal_status is ValidationRunStatus.SUCCEEDED
            else ActivityStatus.FAILED
        )
        submission_digest = content_sha256(
            {
                "hook": "t27.reference_validation_run",
                "validation_run_id": str(run.id),
                "status": terminal_status.value,
                "plan_revision_id": str(run.plan_revision_id),
                "template_revision_id": str(run.template_revision_id),
                "material_model_revision_id": str(run.material_model_revision_id),
                "solver_card_revision_id": str(run.solver_card_revision_id),
                "experimental_selection_revision_id": str(run.experimental_selection_revision_id),
                "outputs": {role: str(reference.artifact_id) for role, _, reference in outputs},
            }
        )
        existing_digest = session.scalar(
            sa.select(provenance_activity_table.c.submission_digest).where(
                provenance_activity_table.c.organization_id == scope.organization_id,
                provenance_activity_table.c.project_id == scope.project_id,
                provenance_activity_table.c.classification == scope.classification.value,
                provenance_activity_table.c.domain_run_type == "validation.validation_run",
                provenance_activity_table.c.domain_run_id == run.id,
            )
        )
        if existing_digest is not None:
            if str(existing_digest) != submission_digest:
                raise ProvenanceConflict(
                    "Validation Run already has conflicting terminal provenance"
                )
            return
        activity = ProvenanceActivity(
            id=self._id_factory(),
            scope=scope,
            activity_type="validation.reference_runner_collect",
            domain_run_type="validation.validation_run",
            domain_run_id=run.id,
            status=activity_status,
            started_at=started_at,
            ended_at=activity_ended_at,
            submission_digest=submission_digest,
            recorded_at=activity_ended_at,
            recorded_by=context.principal.id,
        )
        relation_values = {
            "organization_id": scope.organization_id,
            "project_id": scope.project_id,
            "classification": scope.classification.value,
            "recorded_at": activity_ended_at,
            "recorded_by": context.principal.id,
        }
        session.execute(
            sa.insert(provenance_activity_table).values(
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                classification=scope.classification.value,
                id=activity.id,
                activity_type=activity.activity_type,
                domain_run_type=activity.domain_run_type,
                domain_run_id=activity.domain_run_id,
                status=activity.status.value,
                input_required=True,
                output_required=activity.status is ActivityStatus.SUCCEEDED,
                started_at=activity.started_at,
                ended_at=activity.ended_at,
                submission_digest=activity.submission_digest,
                recorded_at=activity.recorded_at,
                recorded_by=activity.recorded_by,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        for ordinal, (role, entity_id) in enumerate(source_entities.items()):
            session.execute(
                sa.insert(provenance_usage_table).values(
                    **relation_values,
                    activity_id=activity.id,
                    entity_id=entity_id,
                    role=role,
                    ordinal=ordinal,
                )
            )
        session.execute(
            sa.insert(provenance_association_table).values(
                **relation_values,
                activity_id=activity.id,
                agent_id=agent.id,
                role="operator",
                plan_entity_id=source_entities["validation_plan"],
            )
        )
        derivation_sources = {
            "solver_deck": ("validation_plan", "validation_template", "solver_card"),
            "runner_stdout": ("validation_plan", "validation_template"),
            "runner_stderr": ("validation_plan", "validation_template"),
            "native_solver_result": (
                "validation_plan",
                "validation_template",
                "material_model",
                "solver_card",
            ),
            "result_manifest": tuple(source_entities),
        }
        for role, entity_id in output_entities.items():
            session.execute(
                sa.insert(provenance_generation_table).values(
                    **relation_values,
                    entity_id=entity_id,
                    activity_id=activity.id,
                    role=role,
                    generated_at=activity_ended_at,
                )
            )
            for source_role in derivation_sources[role]:
                session.execute(
                    sa.insert(provenance_derivation_table).values(
                        **relation_values,
                        generated_entity_id=entity_id,
                        used_entity_id=source_entities[source_role],
                        activity_id=activity.id,
                        derivation_kind="reference_validation_run",
                    )
                )


def build_reference_validation_service(
    identity: IdentityServices,
    datasets: DatasetService | None,
    material_models: MaterialModelService | None,
    solver_cards: SolverCardService | None,
    artifacts: ArtifactService | None,
) -> ReferenceValidationService | None:
    """Reuse the platform hooks while keeping concrete solver execution outside core."""

    if (
        identity.engine is None
        or identity.rls_context is None
        or datasets is None
        or material_models is None
        or solver_cards is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferenceValidationService(
        repository=SqlAlchemyValidationRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
            result_provenance_hook=SqlReferenceValidationRunProvenanceHook(),
            result_audit_hook=SqlReferenceValidationRunAuditHook(),
        ),
        datasets=datasets,
        material_models=material_models,
        solver_cards=solver_cards,
        artifacts=artifacts,
    )
