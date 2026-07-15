"""PostgreSQL adapter for immutable Ogden-Prony Solver Cards."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.adapters.persistence.repository import (
    SqlSolverCardInputProvenanceHook,
    solver_card_revision_table,
    solver_card_table,
)
from cmp.modules.exporting.application.ogden_prony_service import (
    OgdenPronyExportingRepository,
    OgdenPronySolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_ogden_prony import (
    ABAQUS_EXPORTER_ID,
    OPENRADIOSS_EXPORTER_ID,
    MappingStatus,
    OgdenPronyExportTarget,
    OgdenPronySolverCardNotFound,
    ReferenceOgdenPronySolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_ogden_prony import ReferenceShearPronyTerm
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope

metadata = solver_card_table.metadata

ogden_prony_card_revision_table = sa.Table(
    "ogden_prony_solver_card_revision",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ogden_mu_pa", sa.Double(), nullable=False),
    sa.Column("ogden_alpha", sa.Double(), nullable=False),
    sa.Column("law62_poisson_ratio", sa.Double(), nullable=False),
    sa.Column("term_count", sa.Integer(), nullable=False),
    sa.Column("ogden_mapping_status", sa.String(32), nullable=False),
    sa.Column("prony_mapping_status", sa.String(32), nullable=False),
    sa.Column("volumetric_mapping_status", sa.String(32), nullable=False),
    schema="exporting",
)
ogden_prony_card_term_table = sa.Table(
    "ogden_prony_solver_card_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("g_ratio", sa.Double(), nullable=False),
    sa.Column("relaxation_time_s", sa.Double(), nullable=False),
    schema="exporting",
)


class RlsContext(Protocol):
    def bind_authorization(
        self, session: Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None: ...


def _record(row: Any) -> RevisionRecord:
    return RevisionRecord(
        revision_id=cast(UUID, row["id"]),
        aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
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


def _status(row: Any, name: str) -> MappingStatus:
    return cast(MappingStatus, str(row[name]))


def _content_values(content: ReferenceOgdenPronySolverCardContent) -> dict[str, Any]:
    return {
        "material_model_id": content.material_model_id,
        "material_model_revision_id": content.material_model_revision_id,
        "model_schema_digest": content.model_schema_digest,
        "target_solver": content.target.solver,
        "target_version": content.target.version,
        "target_unit_system": content.target.unit_system,
        "solver_material_id": content.solver_material_id,
        "card_title": content.material_name,
        "material_name": content.material_name,
        "density_kg_per_m3": content.density_kg_per_m3,
        "youngs_modulus_pa": content.catalog_youngs_modulus_pa,
        "poisson_ratio": content.catalog_poisson_ratio,
        "source_yield_stress_pa": None,
        "hardening_curve_artifact_id": None,
        "hardening_curve_sha256": None,
        "hardening_curve_point_count": None,
        "extension_max_true_plastic_strain": None,
        "post_necking_extension_policy": None,
        "hardening_curve_mapping_status": None,
        "extension_mapping_status": None,
        "applicable_temperature_min_k": None,
        "applicable_temperature_max_k": None,
        "applicable_strain_rate_min_per_s": None,
        "applicable_strain_rate_max_per_s": None,
        "applicability_note": None,
        "density_mapping_status": content.density_mapping_status,
        "youngs_modulus_mapping_status": content.ogden_mapping_status,
        "poisson_ratio_mapping_status": content.volumetric_mapping_status,
        "source_yield_mapping_status": "not_applicable",
        "temperature_applicability_mapping_status": content.temperature_mapping_status,
        "strain_rate_applicability_mapping_status": "not_applicable",
        "unit_system_mapping_status": content.unit_system_mapping_status,
        "mapping_report_sha256": content.mapping_report_sha256,
        "card_text": content.card_text,
        "card_sha256": content.card_sha256,
        "exporter_id": content.exporter_id,
        "exporter_version": content.exporter_version,
        "exporter_digest": content.exporter_digest,
        "non_production": content.non_production,
    }


def _write_terms(
    session: Session, draft: RevisionDraft[ReferenceOgdenPronySolverCardContent]
) -> None:
    content = draft.content
    common = {
        "organization_id": draft.scope.organization_id,
        "project_id": draft.scope.project_id,
        "classification": draft.scope.classification,
        "solver_card_id": draft.aggregate_id,
        "solver_card_revision_id": draft.revision_id,
    }
    session.execute(
        sa.insert(ogden_prony_card_revision_table).values(
            **common,
            ogden_mu_pa=content.ogden_mu_pa,
            ogden_alpha=content.ogden_alpha,
            law62_poisson_ratio=content.law62_poisson_ratio,
            term_count=len(content.prony_terms),
            ogden_mapping_status=content.ogden_mapping_status,
            prony_mapping_status=content.prony_mapping_status,
            volumetric_mapping_status=content.volumetric_mapping_status,
        )
    )
    session.execute(
        sa.insert(ogden_prony_card_term_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "g_ratio": term.g_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
            for ordinal, term in enumerate(content.prony_terms, 1)
        ],
    )


_TABLES = TypedRevisionTables[ReferenceOgdenPronySolverCardContent](
    aggregate_type=SOLVER_CARD_AGGREGATE_TYPE,
    identity_table=solver_card_table,
    revision_table=solver_card_revision_table,
    canonical_content=lambda content: content.canonical(),
    content_values=_content_values,
    identity_values=lambda content: {
        "material_model_id": content.material_model_id,
        "target_solver": content.target.solver,
        "target_version": content.target.version,
        "target_unit_system": content.target.unit_system,
        "solver_material_id": content.solver_material_id,
    },
    revision_content_writer=_write_terms,
)

_REVISION_COLUMNS = (
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
    "material_model_id",
    "material_model_revision_id",
    "model_schema_digest",
    "target_solver",
    "target_version",
    "target_unit_system",
    "solver_material_id",
    "material_name",
    "density_kg_per_m3",
    "youngs_modulus_pa",
    "poisson_ratio",
    "density_mapping_status",
    "temperature_applicability_mapping_status",
    "unit_system_mapping_status",
    "mapping_report_sha256",
    "card_text",
    "card_sha256",
    "exporter_id",
    "exporter_version",
    "exporter_digest",
    "non_production",
)


class SqlAlchemyOgdenPronyExportingRepository(OgdenPronyExportingRepository):
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
    ) -> Iterator[Session]:
        with self._sessions() as session, session.begin():
            self._bind(session, context, decision)
            yield session

    def solver_card_store(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        source_model_revision_id: UUID,
    ) -> RevisionStore[ReferenceOgdenPronySolverCardContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=(*self._hooks, SqlSolverCardInputProvenanceHook(source_model_revision_id)),
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _statement() -> sa.Select[Any]:
        revision = solver_card_revision_table
        summary = ogden_prony_card_revision_table
        return (
            sa.select(
                *(revision.c[name] for name in _REVISION_COLUMNS),
                summary.c.ogden_mu_pa,
                summary.c.ogden_alpha,
                summary.c.law62_poisson_ratio,
                summary.c.ogden_mapping_status,
                summary.c.prony_mapping_status,
                summary.c.volumetric_mapping_status,
            )
            .select_from(
                solver_card_table.join(
                    revision,
                    sa.and_(
                        revision.c.id == solver_card_table.c.current_revision_id,
                        revision.c.aggregate_id == solver_card_table.c.id,
                        revision.c.organization_id == solver_card_table.c.organization_id,
                        revision.c.project_id == solver_card_table.c.project_id,
                    ),
                ).join(
                    summary,
                    sa.and_(
                        summary.c.solver_card_id == revision.c.aggregate_id,
                        summary.c.solver_card_revision_id == revision.c.id,
                        summary.c.organization_id == revision.c.organization_id,
                        summary.c.project_id == revision.c.project_id,
                    ),
                )
            )
            .where(revision.c.exporter_id.in_((ABAQUS_EXPORTER_ID, OPENRADIOSS_EXPORTER_ID)))
        )

    @staticmethod
    def _terms(session: Session, row: Any) -> tuple[ReferenceShearPronyTerm, ...]:
        values = session.execute(
            sa.select(
                ogden_prony_card_term_table.c.g_ratio,
                ogden_prony_card_term_table.c.relaxation_time_s,
            )
            .where(
                ogden_prony_card_term_table.c.organization_id == row["organization_id"],
                ogden_prony_card_term_table.c.project_id == row["project_id"],
                ogden_prony_card_term_table.c.solver_card_revision_id == row["id"],
            )
            .order_by(ogden_prony_card_term_table.c.ordinal)
        ).mappings()
        return tuple(
            ReferenceShearPronyTerm(float(item["g_ratio"]), float(item["relaxation_time_s"]))
            for item in values
        )

    @classmethod
    def _snapshot(cls, session: Session, row: Any) -> OgdenPronySolverCardSnapshot:
        target = OgdenPronyExportTarget(
            str(row["target_solver"]),
            str(row["target_version"]),
            str(row["target_unit_system"]),
        )
        content = ReferenceOgdenPronySolverCardContent(
            material_model_id=cast(UUID, row["material_model_id"]),
            material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
            target=target,
            solver_material_id=int(row["solver_material_id"]),
            material_name=str(row["material_name"]),
            density_kg_per_m3=float(row["density_kg_per_m3"]),
            catalog_youngs_modulus_pa=float(row["youngs_modulus_pa"]),
            catalog_poisson_ratio=float(row["poisson_ratio"]),
            ogden_mu_pa=float(row["ogden_mu_pa"]),
            ogden_alpha=float(row["ogden_alpha"]),
            law62_poisson_ratio=float(row["law62_poisson_ratio"]),
            prony_terms=cls._terms(session, row),
            density_mapping_status=_status(row, "density_mapping_status"),
            ogden_mapping_status=_status(row, "ogden_mapping_status"),
            prony_mapping_status=_status(row, "prony_mapping_status"),
            volumetric_mapping_status=_status(row, "volumetric_mapping_status"),
            temperature_mapping_status=_status(row, "temperature_applicability_mapping_status"),
            unit_system_mapping_status=_status(row, "unit_system_mapping_status"),
            mapping_report_sha256=str(row["mapping_report_sha256"]),
            card_text=str(row["card_text"]),
            card_sha256=str(row["card_sha256"]),
            exporter_id=str(row["exporter_id"]),
            exporter_version=str(row["exporter_version"]),
            exporter_digest=str(row["exporter_digest"]),
            model_schema_digest=str(row["model_schema_digest"]),
            non_production=bool(row["non_production"]),
        )
        return OgdenPronySolverCardSnapshot(
            cast(UUID, row["aggregate_id"]),
            content.material_model_id,
            target,
            content.solver_material_id,
            content.material_name,
            RevisionSnapshot(_record(row), content),
        )

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> OgdenPronySolverCardSnapshot:
        statement = self._statement().where(
            solver_card_table.c.id == solver_card_id,
            solver_card_table.c.organization_id == context.organization_id,
            solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise OgdenPronySolverCardNotFound("Ogden-Prony card is not visible")
                return self._snapshot(session, row)
            except DBAPIError as error:
                raise OgdenPronySolverCardNotFound("Ogden-Prony card is unavailable") from error

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[OgdenPronySolverCardSnapshot, ...]:
        statement = (
            self._statement()
            .where(
                solver_card_table.c.material_model_id == material_model_id,
                solver_card_table.c.organization_id == context.organization_id,
                solver_card_table.c.project_id == context.project_id,
            )
            .order_by(solver_card_revision_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            try:
                rows = session.execute(statement).mappings().all()
                return tuple(self._snapshot(session, row) for row in rows)
            except DBAPIError as error:
                raise OgdenPronySolverCardNotFound("Ogden-Prony cards are unavailable") from error
