"""PostgreSQL persistence for typed Ogden-Prony IR revisions and terms."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.adapters.persistence.repository import (
    material_model_revision_table,
    material_model_table,
)
from cmp.modules.modeling.application.ogden_prony import (
    OgdenPronyModelSnapshot,
    OgdenPronyRepository,
)
from cmp.modules.modeling.application.service import MATERIAL_MODEL_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.modeling.domain.reference_ogden_prony import (
    REFERENCE_OGDEN_PRONY_FAMILY_ID,
    ReferenceOgdenPromotionEvidence,
    ReferenceOgdenPronyContent,
    ReferenceOgdenPronyNotFound,
    ReferenceOgdenTerm,
    ReferenceShearPronyTerm,
    reference_ogden_prony_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope

metadata = material_model_table.metadata

ogden_prony_revision_table = sa.Table(
    "ogden_prony_revision",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ogden_mu_pa", sa.Double(), nullable=False),
    sa.Column("ogden_alpha", sa.Double(), nullable=False),
    sa.Column("law62_poisson_ratio", sa.Double(), nullable=False),
    sa.Column("term_count", sa.Integer(), nullable=False),
    schema="modeling",
)
ogden_prony_term_table = sa.Table(
    "ogden_prony_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("g_ratio", sa.Double(), nullable=False),
    sa.Column("relaxation_time_s", sa.Double(), nullable=False),
    schema="modeling",
)
ogden_promotion_evidence_table = sa.Table(
    "ogden_promotion_evidence",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("material_model_id", sa.Uuid(), nullable=False),
    sa.Column("material_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("promoted_from_model_revision_id", sa.Uuid(), nullable=False),
    sa.Column("selection_id", sa.Uuid(), nullable=False),
    sa.Column("selection_revision_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_run_id", sa.Uuid(), nullable=False),
    sa.Column("calibration_candidate_id", sa.Uuid(), nullable=False),
    sa.Column("candidate_sha256", sa.CHAR(64), nullable=False),
    sa.Column("diagnostics_artifact_id", sa.Uuid(), nullable=False),
    sa.Column("diagnostics_sha256", sa.CHAR(64), nullable=False),
    schema="modeling",
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
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


def _content_values(content: ReferenceOgdenPronyContent) -> dict[str, Any]:
    return {
        "model_family_id": content.model_family_id,
        "model_schema_digest": content.model_schema_digest,
        "material_id": content.material_id,
        "material_revision_id": content.material_revision_id,
        "material_state_id": content.material_state_id,
        "material_state_revision_id": content.material_state_revision_id,
        "property_set_id": content.property_set_id,
        "property_set_revision_id": content.property_set_revision_id,
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.catalog_youngs_modulus_pa,
        "poisson_ratio": content.catalog_poisson_ratio,
        "source_yield_stress_pa": None,
        "reference_temperature_k": content.reference_temperature_k,
        "calibration_evidence_kind": (
            "reference_ogden_candidate_selection"
            if content.promotion_evidence is not None
            else "manual_catalog_projection"
        ),
        "non_production": True,
    }


def _write_terms(session: Session, draft: RevisionDraft[ReferenceOgdenPronyContent]) -> None:
    content = draft.content
    scope = draft.scope
    session.execute(
        sa.insert(ogden_prony_revision_table).values(
            organization_id=scope.organization_id,
            project_id=scope.project_id,
            classification=scope.classification,
            material_model_id=draft.aggregate_id,
            material_model_revision_id=draft.revision_id,
            ogden_mu_pa=content.ogden_term.mu_pa,
            ogden_alpha=content.ogden_term.alpha,
            law62_poisson_ratio=content.law62_poisson_ratio,
            term_count=len(content.prony_terms),
        )
    )
    session.execute(
        sa.insert(ogden_prony_term_table),
        [
            {
                "organization_id": scope.organization_id,
                "project_id": scope.project_id,
                "classification": scope.classification,
                "material_model_id": draft.aggregate_id,
                "material_model_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "g_ratio": term.g_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
            for ordinal, term in enumerate(content.prony_terms, 1)
        ],
    )
    evidence = content.promotion_evidence
    if evidence is not None:
        session.execute(
            sa.insert(ogden_promotion_evidence_table).values(
                organization_id=scope.organization_id,
                project_id=scope.project_id,
                classification=scope.classification,
                material_model_id=draft.aggregate_id,
                material_model_revision_id=draft.revision_id,
                promoted_from_model_revision_id=(
                    evidence.promoted_from_model_revision_id
                ),
                selection_id=evidence.selection_id,
                selection_revision_id=evidence.selection_revision_id,
                calibration_run_id=evidence.calibration_run_id,
                calibration_candidate_id=evidence.calibration_candidate_id,
                candidate_sha256=evidence.candidate_sha256,
                diagnostics_artifact_id=evidence.diagnostics_artifact_id,
                diagnostics_sha256=evidence.diagnostics_sha256,
            )
        )


_TABLES = TypedRevisionTables[ReferenceOgdenPronyContent](
    aggregate_type=MATERIAL_MODEL_AGGREGATE_TYPE,
    identity_table=material_model_table,
    revision_table=material_model_revision_table,
    canonical_content=reference_ogden_prony_canonical,
    content_values=_content_values,
    identity_values=lambda content: {"material_state_id": content.material_state_id},
    revision_content_writer=_write_terms,
)


_REVISION_NAMES = (
    "id",
    "aggregate_id",
    "organization_id",
    "project_id",
    "classification",
    "revision_no",
    "based_on_revision_id",
    "schema_id",
    "schema_version",
    "content_hash",
    "created_at",
    "created_by",
    "change_reason",
    "request_id",
    "trace_id",
    "model_family_id",
    "model_schema_digest",
    "material_id",
    "material_revision_id",
    "material_state_id",
    "material_state_revision_id",
    "property_set_id",
    "property_set_revision_id",
    "density_kg_per_m3",
    "youngs_modulus_pa",
    "poisson_ratio",
    "reference_temperature_k",
    "non_production",
)

_EVIDENCE_NAMES = (
    "promoted_from_model_revision_id",
    "selection_id",
    "selection_revision_id",
    "calibration_run_id",
    "calibration_candidate_id",
    "candidate_sha256",
    "diagnostics_artifact_id",
    "diagnostics_sha256",
)


class SqlAlchemyOgdenPronyRepository(OgdenPronyRepository):
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
    def _session(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> Any:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def material_model_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ReferenceOgdenPronyContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _statement() -> sa.Select[Any]:
        revision = material_model_revision_table
        summary = ogden_prony_revision_table
        evidence = ogden_promotion_evidence_table
        return (
            sa.select(
                *(revision.c[name] for name in _REVISION_NAMES),
                summary.c.ogden_mu_pa,
                summary.c.ogden_alpha,
                summary.c.law62_poisson_ratio,
                summary.c.term_count,
                *(evidence.c[name] for name in _EVIDENCE_NAMES),
            )
            .select_from(
                material_model_table.join(
                    revision,
                    sa.and_(
                        revision.c.id == material_model_table.c.current_revision_id,
                        revision.c.aggregate_id == material_model_table.c.id,
                        revision.c.organization_id == material_model_table.c.organization_id,
                        revision.c.project_id == material_model_table.c.project_id,
                    ),
                ).join(
                    summary,
                    sa.and_(
                        summary.c.material_model_id == revision.c.aggregate_id,
                        summary.c.material_model_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                ).outerjoin(
                    evidence,
                    sa.and_(
                        evidence.c.material_model_id == revision.c.aggregate_id,
                        evidence.c.material_model_revision_id == revision.c.id,
                        evidence.c.organization_id == revision.c.organization_id,
                        evidence.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(revision.c.model_family_id == REFERENCE_OGDEN_PRONY_FAMILY_ID)
        )

    @staticmethod
    def _terms(session: Session, row: Any) -> tuple[ReferenceShearPronyTerm, ...]:
        values = session.execute(
            sa.select(
                ogden_prony_term_table.c.g_ratio,
                ogden_prony_term_table.c.relaxation_time_s,
            )
            .where(
                ogden_prony_term_table.c.organization_id == row["organization_id"],
                ogden_prony_term_table.c.project_id == row["project_id"],
                ogden_prony_term_table.c.material_model_revision_id == row["id"],
            )
            .order_by(ogden_prony_term_table.c.ordinal)
        ).mappings()
        return tuple(
            ReferenceShearPronyTerm(float(item["g_ratio"]), float(item["relaxation_time_s"]))
            for item in values
        )

    @classmethod
    def _snapshot(cls, session: Session, row: Any) -> OgdenPronyModelSnapshot:
        evidence = (
            ReferenceOgdenPromotionEvidence(
                selection_id=cast(UUID, row["selection_id"]),
                selection_revision_id=cast(UUID, row["selection_revision_id"]),
                calibration_run_id=cast(UUID, row["calibration_run_id"]),
                calibration_candidate_id=cast(UUID, row["calibration_candidate_id"]),
                candidate_sha256=str(row["candidate_sha256"]),
                diagnostics_artifact_id=cast(UUID, row["diagnostics_artifact_id"]),
                diagnostics_sha256=str(row["diagnostics_sha256"]),
                promoted_from_model_revision_id=cast(
                    UUID, row["promoted_from_model_revision_id"]
                ),
            )
            if row["selection_id"] is not None
            else None
        )
        content = ReferenceOgdenPronyContent(
            material_id=cast(UUID, row["material_id"]),
            material_revision_id=cast(UUID, row["material_revision_id"]),
            material_state_id=cast(UUID, row["material_state_id"]),
            material_state_revision_id=cast(UUID, row["material_state_revision_id"]),
            property_set_id=cast(UUID, row["property_set_id"]),
            property_set_revision_id=cast(UUID, row["property_set_revision_id"]),
            density_kg_per_m3=float(row["density_kg_per_m3"]),
            catalog_youngs_modulus_pa=float(row["youngs_modulus_pa"]),
            catalog_poisson_ratio=float(row["poisson_ratio"]),
            ogden_term=ReferenceOgdenTerm(
                float(row["ogden_mu_pa"]), float(row["ogden_alpha"])
            ),
            prony_terms=cls._terms(session, row),
            reference_temperature_k=float(row["reference_temperature_k"]),
            promotion_evidence=evidence,
            law62_poisson_ratio=float(row["law62_poisson_ratio"]),
            model_family_id=str(row["model_family_id"]),
            model_schema_digest=str(row["model_schema_digest"]),
            non_production=bool(row["non_production"]),
        )
        return OgdenPronyModelSnapshot(
            cast(UUID, row["aggregate_id"]),
            content.material_state_id,
            RevisionSnapshot(_record(row), content),
        )

    def get_material_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> OgdenPronyModelSnapshot:
        statement = self._statement().where(
            material_model_table.c.id == material_model_id,
            material_model_table.c.organization_id == context.organization_id,
            material_model_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ReferenceOgdenPronyNotFound("Ogden-Prony model is not visible")
                return self._snapshot(session, row)
            except DBAPIError as error:
                raise ReferenceOgdenPronyNotFound("Ogden-Prony model is unavailable") from error

    def get_material_model_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
        material_model_revision_id: UUID,
    ) -> RevisionSnapshot[ReferenceOgdenPronyContent]:
        revision = material_model_revision_table
        summary = ogden_prony_revision_table
        evidence = ogden_promotion_evidence_table
        statement = (
            sa.select(
                *(revision.c[name] for name in _REVISION_NAMES),
                summary.c.ogden_mu_pa,
                summary.c.ogden_alpha,
                summary.c.law62_poisson_ratio,
                summary.c.term_count,
                *(evidence.c[name] for name in _EVIDENCE_NAMES),
            )
            .select_from(
                revision.join(
                    summary,
                    sa.and_(
                        summary.c.material_model_id == revision.c.aggregate_id,
                        summary.c.material_model_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                ).outerjoin(
                    evidence,
                    sa.and_(
                        evidence.c.material_model_id == revision.c.aggregate_id,
                        evidence.c.material_model_revision_id == revision.c.id,
                        evidence.c.organization_id == revision.c.organization_id,
                        evidence.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(
                revision.c.model_family_id == REFERENCE_OGDEN_PRONY_FAMILY_ID,
                revision.c.aggregate_id == material_model_id,
                revision.c.id == material_model_revision_id,
                revision.c.organization_id == context.organization_id,
                revision.c.project_id == context.project_id,
            )
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ReferenceOgdenPronyNotFound(
                        "Ogden-Prony model revision is not visible"
                    )
                return self._snapshot(session, row).current
            except DBAPIError as error:
                raise ReferenceOgdenPronyNotFound(
                    "Ogden-Prony model revision is unavailable"
                ) from error

    def list_material_model_revisions(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[RevisionSnapshot[ReferenceOgdenPronyContent], ...]:
        revision = material_model_revision_table
        summary = ogden_prony_revision_table
        evidence = ogden_promotion_evidence_table
        statement = (
            sa.select(
                *(revision.c[name] for name in _REVISION_NAMES),
                summary.c.ogden_mu_pa,
                summary.c.ogden_alpha,
                summary.c.law62_poisson_ratio,
                summary.c.term_count,
                *(evidence.c[name] for name in _EVIDENCE_NAMES),
            )
            .select_from(
                revision.join(
                    summary,
                    sa.and_(
                        summary.c.material_model_id == revision.c.aggregate_id,
                        summary.c.material_model_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                ).outerjoin(
                    evidence,
                    sa.and_(
                        evidence.c.material_model_id == revision.c.aggregate_id,
                        evidence.c.material_model_revision_id == revision.c.id,
                        evidence.c.organization_id == revision.c.organization_id,
                        evidence.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(
                revision.c.model_family_id == REFERENCE_OGDEN_PRONY_FAMILY_ID,
                revision.c.aggregate_id == material_model_id,
                revision.c.organization_id == context.organization_id,
                revision.c.project_id == context.project_id,
            )
            .order_by(revision.c.revision_no.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
                if not rows:
                    raise ReferenceOgdenPronyNotFound(
                        "Ogden-Prony model revisions are not visible"
                    )
                return tuple(self._snapshot(session, row).current for row in rows)
            except DBAPIError as error:
                raise ReferenceOgdenPronyNotFound(
                    "Ogden-Prony model revisions are unavailable"
                ) from error

    def list_material_models_for_state(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_state_id: UUID,
    ) -> tuple[OgdenPronyModelSnapshot, ...]:
        statement = (
            self._statement()
            .where(
                material_model_table.c.material_state_id == material_state_id,
                material_model_table.c.organization_id == context.organization_id,
                material_model_table.c.project_id == context.project_id,
            )
            .order_by(material_model_revision_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
                return tuple(self._snapshot(session, row) for row in rows)
            except DBAPIError as error:
                raise ReferenceOgdenPronyNotFound("Ogden-Prony models are unavailable") from error
