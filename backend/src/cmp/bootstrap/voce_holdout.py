"""Compose the solver-independent reference Voce holdout service."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from cmp.bootstrap.security import IdentityServices
from cmp.bootstrap.validation import (
    _ensure_artifact_entity,
    _required_revision_entity_id,
)
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
from cmp.modules.datasets.application.service import DATASET_AGGREGATE_TYPE, DatasetService
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.application.service import MATERIAL_MODEL_AGGREGATE_TYPE
from cmp.modules.modeling.application.tabulated_plasticity import (
    TabulatedPlasticityModelService,
)
from cmp.modules.provenance.adapters.persistence.repository import (
    SqlAlchemyProvenanceRepository,
    SqlAlchemyRevisionProvenanceHook,
    activity_table,
    association_table,
    derivation_table,
    generation_table,
    usage_table,
)
from cmp.modules.provenance.domain.model import (
    ActivityStatus,
    AgentReference,
    AgentType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceConflict,
    ProvenanceScope,
)
from cmp.modules.review_release.adapters.persistence.lifecycle import SqlInitialLifecycleHook
from cmp.modules.statistics.application.replicate_outlier_service import (
    ReplicateOutlierService,
)
from cmp.modules.validation.adapters.persistence.voce_holdout_repository import (
    SqlAlchemyVoceHoldoutRepository,
)
from cmp.modules.validation.application.voce_holdout import (
    VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
    ReferenceVoceHoldoutService,
)
from cmp.modules.validation.domain.reference_virtual_specimen import (
    ValidationArtifactReference,
)
from cmp.modules.validation.domain.reference_voce_holdout import ReferenceVoceHoldoutResult
from cmp.shared.domain.revisions import content_sha256


class SqlVoceHoldoutEvidenceHook:
    """Attach audit and provenance facts atomically with one immutable V3 Result."""

    def __init__(self) -> None:
        self._audit = SqlAlchemyAuditWriter()

    def __call__(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
        classification: DataClassification,
        result: ReferenceVoceHoldoutResult,
        change_reason: str,
    ) -> None:
        del decision
        scope = ProvenanceScope(context.organization_id, context.project_id, classification)
        sources = {
            "holdout_plan": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=VOCE_HOLDOUT_PLAN_AGGREGATE_TYPE,
                revision_id=result.plan_revision_id,
            ),
            "calibrated_material_model": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
                revision_id=result.material_model_revision_id,
            ),
            "holdout_dataset": _required_revision_entity_id(
                session,
                scope,
                aggregate_type=DATASET_AGGREGATE_TYPE,
                revision_id=result.holdout_dataset_revision_id,
            ),
        }
        comparison = ValidationArtifactReference(
            result.comparison_artifact_id, result.comparison_sha256
        )
        output = _ensure_artifact_entity(
            session,
            scope=scope,
            reference=comparison,
            entity_type="validation.reference_voce_holdout_comparison",
            recorded_at=result.created_at,
            context=context,
            id_factory=uuid4,
        )
        principal_type = session.scalar(
            sa.text("SELECT principal_type FROM identity.principal WHERE id = :principal_id"),
            {"principal_id": context.principal.id},
        )
        if principal_type not in {"user", "service"}:
            raise ProvenanceConflict("holdout operator is not an active provenance Agent")
        agent = SqlAlchemyProvenanceRepository._ensure_agent(
            session,
            ProvenanceAgent(
                id=uuid4(),
                scope=scope,
                reference=AgentReference(AgentType(str(principal_type)), context.principal.id),
                recorded_at=result.created_at,
                recorded_by=context.principal.id,
            ),
            request_id=context.request_id,
            trace_id=context.trace_id,
        )
        digest = content_sha256(
            {
                "hook": "p1.reference_voce_holdout",
                "run_id": str(result.run_id),
                "result_id": str(result.id),
                "plan_revision_id": str(result.plan_revision_id),
                "material_model_revision_id": str(result.material_model_revision_id),
                "holdout_dataset_revision_id": str(result.holdout_dataset_revision_id),
                "comparison_sha256": result.comparison_sha256,
            }
        )
        activity = ProvenanceActivity(
            id=uuid4(),
            scope=scope,
            activity_type="validation.reference_voce_holdout",
            domain_run_type="validation.voce_holdout_run",
            domain_run_id=result.run_id,
            status=ActivityStatus.SUCCEEDED,
            started_at=result.created_at,
            ended_at=result.created_at,
            submission_digest=digest,
            recorded_at=result.created_at,
            recorded_by=context.principal.id,
        )
        common = {
            "organization_id": scope.organization_id,
            "project_id": scope.project_id,
            "classification": scope.classification.value,
            "recorded_at": result.created_at,
            "recorded_by": context.principal.id,
        }
        session.execute(
            sa.insert(activity_table).values(
                **common,
                id=activity.id,
                activity_type=activity.activity_type,
                domain_run_type=activity.domain_run_type,
                domain_run_id=activity.domain_run_id,
                status=activity.status.value,
                input_required=True,
                output_required=True,
                started_at=activity.started_at,
                ended_at=activity.ended_at,
                submission_digest=activity.submission_digest,
                request_id=context.request_id,
                trace_id=context.trace_id,
            )
        )
        for ordinal, (role, entity_id) in enumerate(sources.items()):
            session.execute(
                sa.insert(usage_table).values(
                    **common,
                    activity_id=activity.id,
                    entity_id=entity_id,
                    role=role,
                    ordinal=ordinal,
                )
            )
        session.execute(
            sa.insert(association_table).values(
                **common,
                activity_id=activity.id,
                agent_id=agent.id,
                role="operator",
                plan_entity_id=sources["holdout_plan"],
            )
        )
        session.execute(
            sa.insert(generation_table).values(
                **common,
                entity_id=output,
                activity_id=activity.id,
                role="holdout_comparison",
                generated_at=result.created_at,
            )
        )
        for entity_id in sources.values():
            session.execute(
                sa.insert(derivation_table).values(
                    **common,
                    generated_entity_id=output,
                    used_entity_id=entity_id,
                    activity_id=activity.id,
                    derivation_kind="reference_voce_holdout",
                )
            )
        self._audit.append(
            session,
            AuditEventDraft(
                id=uuid4(),
                scope=AuditScope(context.organization_id, context.project_id),
                occurred_at=result.created_at,
                actor_type=AuditActorType(str(principal_type)),
                actor_id=context.principal.id,
                action="validation.voce_holdout.execute",
                target_type="validation.voce_holdout_run",
                target_id=result.run_id,
                outcome=AuditOutcome.SUCCESS,
                request_id=context.request_id,
                trace_id=context.trace_id,
                ip_or_client=redact_ip_or_client(None),
                reason=change_reason,
            ),
        )


def build_reference_voce_holdout_service(
    identity: IdentityServices,
    models: TabulatedPlasticityModelService | None,
    statistics: ReplicateOutlierService | None,
    datasets: DatasetService | None,
    artifacts: ArtifactService | None,
) -> ReferenceVoceHoldoutService | None:
    if (
        identity.engine is None
        or identity.rls_context is None
        or models is None
        or statistics is None
        or datasets is None
        or artifacts is None
    ):
        return None
    sessions = sessionmaker(identity.engine, class_=Session, expire_on_commit=False)
    return ReferenceVoceHoldoutService(
        repository=SqlAlchemyVoceHoldoutRepository(
            session_factory=sessions,
            rls_context=identity.rls_context,
            revision_hooks=(
                SqlInitialLifecycleHook(),
                SqlAlchemyRevisionProvenanceHook(),
                SqlAlchemyRevisionAuditHook(),
            ),
            result_hooks=(SqlVoceHoldoutEvidenceHook(),),
        ),
        models=models,
        statistics=statistics,
        datasets=datasets,
        artifacts=artifacts,
    )
