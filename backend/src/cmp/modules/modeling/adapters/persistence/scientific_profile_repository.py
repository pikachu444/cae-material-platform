"""PostgreSQL adapter for typed scientific calibration profile revisions."""

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
from cmp.modules.modeling.adapters.persistence.repository import metadata
from cmp.modules.modeling.application.scientific_profile import (
    SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
    RevisionSnapshot,
    ScientificProfileRepository,
    ScientificProfileSnapshot,
)
from cmp.modules.modeling.domain.scientific_profile import (
    OgdenScientificParameters,
    PronyScientificParameters,
    ScientificApprovalStatus,
    ScientificProfileContent,
    ScientificProfileFamily,
    ScientificProfileNotFound,
    VoceScientificParameters,
    scientific_profile_canonical,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

scientific_profile_table = sa.Table(
    "scientific_profile",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("profile_label", sa.String(160), nullable=False),
    sa.Column("family", sa.String(64), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="modeling",
)

scientific_profile_revision_table = sa.Table(
    "scientific_profile_revision",
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
    sa.Column("profile_label", sa.String(160), nullable=False),
    sa.Column("family", sa.String(64), nullable=False),
    sa.Column("model_family_id", sa.String(255), nullable=False),
    sa.Column("approval_status", sa.String(32), nullable=False),
    sa.Column("optimizer", sa.String(64), nullable=False),
    sa.Column("residual_definition", sa.String(64), nullable=False),
    sa.Column("aggregation_order", sa.String(64), nullable=False),
    sa.Column("missing_data_policy", sa.String(32), nullable=False),
    sa.Column("holdout_policy", sa.String(32), nullable=False),
    sa.Column("uncertainty_policy", sa.String(64), nullable=False),
    sa.Column("multistart_count", sa.Integer(), nullable=False),
    sa.Column("seed", sa.Integer(), nullable=False),
    sa.Column("status_note", sa.String(500), nullable=False),
    sa.Column("voce_sigma0_initial_pa", sa.Double(), nullable=True),
    sa.Column("voce_sigma0_lower_pa", sa.Double(), nullable=True),
    sa.Column("voce_sigma0_upper_pa", sa.Double(), nullable=True),
    sa.Column("voce_sigma0_scale_pa", sa.Double(), nullable=True),
    sa.Column("voce_q_initial_pa", sa.Double(), nullable=True),
    sa.Column("voce_q_lower_pa", sa.Double(), nullable=True),
    sa.Column("voce_q_upper_pa", sa.Double(), nullable=True),
    sa.Column("voce_q_scale_pa", sa.Double(), nullable=True),
    sa.Column("voce_b_initial", sa.Double(), nullable=True),
    sa.Column("voce_b_lower", sa.Double(), nullable=True),
    sa.Column("voce_b_upper", sa.Double(), nullable=True),
    sa.Column("voce_b_scale", sa.Double(), nullable=True),
    sa.Column("prony_term_count_min", sa.Integer(), nullable=True),
    sa.Column("prony_term_count_max", sa.Integer(), nullable=True),
    sa.Column("prony_total_shear_ratio_upper", sa.Double(), nullable=True),
    sa.Column("prony_relaxation_time_lower_s", sa.Double(), nullable=True),
    sa.Column("prony_relaxation_time_upper_s", sa.Double(), nullable=True),
    sa.Column("ogden_mu_initial_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_lower_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_upper_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_scale_pa", sa.Double(), nullable=True),
    sa.Column("ogden_alpha_initial", sa.Double(), nullable=True),
    sa.Column("ogden_alpha_lower", sa.Double(), nullable=True),
    sa.Column("ogden_alpha_upper", sa.Double(), nullable=True),
    sa.Column("ogden_alpha_scale", sa.Double(), nullable=True),
    sa.Column("ogden_uniaxial_weight", sa.Double(), nullable=True),
    sa.Column("ogden_planar_weight", sa.Double(), nullable=True),
    sa.Column("ogden_biaxial_weight", sa.Double(), nullable=True),
    schema="modeling",
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
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


def _content_values(content: ScientificProfileContent) -> dict[str, Any]:
    voce, prony, ogden = content.voce, content.prony, content.ogden
    return {
        "profile_label": content.profile_label,
        "family": content.family.value,
        "model_family_id": content.family.model_family_id,
        "approval_status": content.approval_status.value,
        "optimizer": content.optimizer,
        "residual_definition": content.residual_definition,
        "aggregation_order": content.aggregation_order,
        "missing_data_policy": content.missing_data_policy,
        "holdout_policy": content.holdout_policy,
        "uncertainty_policy": content.uncertainty_policy,
        "multistart_count": content.multistart_count,
        "seed": content.seed,
        "status_note": content.status_note,
        "voce_sigma0_initial_pa": voce.sigma0_initial_pa if voce else None,
        "voce_sigma0_lower_pa": voce.sigma0_lower_pa if voce else None,
        "voce_sigma0_upper_pa": voce.sigma0_upper_pa if voce else None,
        "voce_sigma0_scale_pa": voce.sigma0_scale_pa if voce else None,
        "voce_q_initial_pa": voce.q_initial_pa if voce else None,
        "voce_q_lower_pa": voce.q_lower_pa if voce else None,
        "voce_q_upper_pa": voce.q_upper_pa if voce else None,
        "voce_q_scale_pa": voce.q_scale_pa if voce else None,
        "voce_b_initial": voce.b_initial if voce else None,
        "voce_b_lower": voce.b_lower if voce else None,
        "voce_b_upper": voce.b_upper if voce else None,
        "voce_b_scale": voce.b_scale if voce else None,
        "prony_term_count_min": prony.term_count_min if prony else None,
        "prony_term_count_max": prony.term_count_max if prony else None,
        "prony_total_shear_ratio_upper": prony.total_shear_ratio_upper if prony else None,
        "prony_relaxation_time_lower_s": prony.relaxation_time_lower_s if prony else None,
        "prony_relaxation_time_upper_s": prony.relaxation_time_upper_s if prony else None,
        "ogden_mu_initial_pa": ogden.mu_initial_pa if ogden else None,
        "ogden_mu_lower_pa": ogden.mu_lower_pa if ogden else None,
        "ogden_mu_upper_pa": ogden.mu_upper_pa if ogden else None,
        "ogden_mu_scale_pa": ogden.mu_scale_pa if ogden else None,
        "ogden_alpha_initial": ogden.alpha_initial if ogden else None,
        "ogden_alpha_lower": ogden.alpha_lower if ogden else None,
        "ogden_alpha_upper": ogden.alpha_upper if ogden else None,
        "ogden_alpha_scale": ogden.alpha_scale if ogden else None,
        "ogden_uniaxial_weight": ogden.uniaxial_weight if ogden else None,
        "ogden_planar_weight": ogden.planar_weight if ogden else None,
        "ogden_biaxial_weight": ogden.biaxial_weight if ogden else None,
    }


_TABLES = TypedRevisionTables[ScientificProfileContent](
    aggregate_type=SCIENTIFIC_PROFILE_AGGREGATE_TYPE,
    identity_table=scientific_profile_table,
    revision_table=scientific_profile_revision_table,
    canonical_content=scientific_profile_canonical,
    content_values=_content_values,
    identity_values=lambda content: {
        "profile_label": content.profile_label,
        "family": content.family.value,
    },
)


def _optional_float(row: Any, name: str) -> float:
    value = row[name]
    if value is None:
        raise ScientificProfileNotFound(f"scientific profile is missing {name}")
    return float(value)


def _optional_int(row: Any, name: str) -> int:
    value = row[name]
    if value is None:
        raise ScientificProfileNotFound(f"scientific profile is missing {name}")
    return int(value)


def _content(row: Any) -> ScientificProfileContent:
    family = ScientificProfileFamily(str(row["family"]))
    voce = (
        VoceScientificParameters(
            *(
                _optional_float(row, name)
                for name in (
                    "voce_sigma0_initial_pa",
                    "voce_sigma0_lower_pa",
                    "voce_sigma0_upper_pa",
                    "voce_sigma0_scale_pa",
                    "voce_q_initial_pa",
                    "voce_q_lower_pa",
                    "voce_q_upper_pa",
                    "voce_q_scale_pa",
                    "voce_b_initial",
                    "voce_b_lower",
                    "voce_b_upper",
                    "voce_b_scale",
                )
            )
        )
        if family is ScientificProfileFamily.STEEL_VOCE
        else None
    )
    prony = (
        PronyScientificParameters(
            _optional_int(row, "prony_term_count_min"),
            _optional_int(row, "prony_term_count_max"),
            _optional_float(row, "prony_total_shear_ratio_upper"),
            _optional_float(row, "prony_relaxation_time_lower_s"),
            _optional_float(row, "prony_relaxation_time_upper_s"),
        )
        if family is ScientificProfileFamily.POLYMER_LINEAR_PRONY
        else None
    )
    ogden = (
        OgdenScientificParameters(
            *(
                _optional_float(row, name)
                for name in (
                    "ogden_mu_initial_pa",
                    "ogden_mu_lower_pa",
                    "ogden_mu_upper_pa",
                    "ogden_mu_scale_pa",
                    "ogden_alpha_initial",
                    "ogden_alpha_lower",
                    "ogden_alpha_upper",
                    "ogden_alpha_scale",
                    "ogden_uniaxial_weight",
                    "ogden_planar_weight",
                    "ogden_biaxial_weight",
                )
            )
        )
        if family is ScientificProfileFamily.ELASTOMER_OGDEN_PRONY
        else None
    )
    return ScientificProfileContent(
        profile_label=str(row["profile_label"]),
        family=family,
        approval_status=ScientificApprovalStatus(str(row["approval_status"])),
        multistart_count=int(row["multistart_count"]),
        seed=int(row["seed"]),
        voce=voce,
        prony=prony,
        ogden=ogden,
        optimizer=str(row["optimizer"]),
        residual_definition=str(row["residual_definition"]),
        aggregation_order=str(row["aggregation_order"]),
        missing_data_policy=str(row["missing_data_policy"]),
        holdout_policy=str(row["holdout_policy"]),
        uncertainty_policy=str(row["uncertainty_policy"]),
        status_note=str(row["status_note"]),
    )


class SqlAlchemyScientificProfileRepository(ScientificProfileRepository):
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

    def profile_store(
        self, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[ScientificProfileContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _statement() -> sa.Select[Any]:
        return sa.select(scientific_profile_revision_table).select_from(
            scientific_profile_table.join(
                scientific_profile_revision_table,
                sa.and_(
                    scientific_profile_table.c.current_revision_id
                    == scientific_profile_revision_table.c.id,
                    scientific_profile_table.c.id
                    == scientific_profile_revision_table.c.aggregate_id,
                    scientific_profile_table.c.organization_id
                    == scientific_profile_revision_table.c.organization_id,
                    scientific_profile_table.c.project_id
                    == scientific_profile_revision_table.c.project_id,
                ),
            )
        )

    @staticmethod
    def _snapshot(row: Any) -> ScientificProfileSnapshot:
        record = _record(row)
        return ScientificProfileSnapshot(
            record.aggregate_id, RevisionSnapshot(record, _content(row))
        )

    def get_profile(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
    ) -> ScientificProfileSnapshot:
        statement = self._statement().where(
            scientific_profile_table.c.id == profile_id,
            scientific_profile_table.c.organization_id == context.organization_id,
            scientific_profile_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ScientificProfileNotFound("scientific profile is not visible")
                return self._snapshot(row)
            except DBAPIError as error:
                raise ScientificProfileNotFound("scientific profile is not available") from error

    def get_profile_revision(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        profile_id: UUID,
        profile_revision_id: UUID,
    ) -> RevisionSnapshot:
        statement = sa.select(scientific_profile_revision_table).where(
            scientific_profile_revision_table.c.aggregate_id == profile_id,
            scientific_profile_revision_table.c.id == profile_revision_id,
            scientific_profile_revision_table.c.organization_id == context.organization_id,
            scientific_profile_revision_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ScientificProfileNotFound(
                        "scientific profile revision is not visible"
                    )
                return RevisionSnapshot(_record(row), _content(row))
            except DBAPIError as error:
                raise ScientificProfileNotFound(
                    "scientific profile revision is not available"
                ) from error

    def list_profiles(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        family: ScientificProfileFamily | None,
    ) -> tuple[ScientificProfileSnapshot, ...]:
        statement = self._statement().where(
            scientific_profile_table.c.organization_id == context.organization_id,
            scientific_profile_table.c.project_id == context.project_id,
        )
        if family is not None:
            statement = statement.where(scientific_profile_revision_table.c.family == family.value)
        statement = statement.order_by(
            scientific_profile_revision_table.c.profile_label,
            scientific_profile_revision_table.c.created_at.desc(),
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
                return tuple(self._snapshot(row) for row in rows)
            except DBAPIError as error:
                raise ScientificProfileNotFound("scientific profiles are not available") from error
