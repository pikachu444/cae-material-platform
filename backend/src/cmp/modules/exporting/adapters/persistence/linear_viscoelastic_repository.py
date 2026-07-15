"""PostgreSQL adapter for immutable Abaqus linear-Prony Solver Cards."""

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
from cmp.modules.exporting.application.linear_viscoelastic_service import (
    LinearViscoelasticExportingRepository,
    LinearViscoelasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_linear_viscoelasticity import (
    ABAQUS_PRONY_EXPORTER_ID,
    LinearViscoelasticExportTarget,
    LinearViscoelasticSolverCardNotFound,
    MappingStatus,
    ReferenceLinearViscoelasticSolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.reference_linear_viscoelasticity import (
    BulkRelaxationStatus,
    PronyTerm,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope

metadata = solver_card_table.metadata

linear_viscoelastic_solver_card_revision_table = sa.Table(
    "linear_viscoelastic_solver_card_revision",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("bulk_relaxation_status", sa.String(32), nullable=False),
    sa.Column("prony_terms_mapping_status", sa.String(32), nullable=False),
    sa.Column("bulk_mapping_status", sa.String(32), nullable=False),
    sa.Column("term_count", sa.Integer(), nullable=False),
    schema="exporting",
)
linear_viscoelastic_solver_card_term_table = sa.Table(
    "linear_viscoelastic_solver_card_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("g_ratio", sa.Double(), nullable=False),
    sa.Column("k_ratio", sa.Double(), nullable=False),
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


def _status(row: Any, column: str) -> MappingStatus:
    return cast(MappingStatus, str(row[column]))


def _content_values(content: ReferenceLinearViscoelasticSolverCardContent) -> dict[str, Any]:
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
        "youngs_modulus_pa": content.youngs_modulus_pa,
        "poisson_ratio": content.poisson_ratio,
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
        "youngs_modulus_mapping_status": content.elasticity_mapping_status,
        "poisson_ratio_mapping_status": content.elasticity_mapping_status,
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
    session: Session, draft: RevisionDraft[ReferenceLinearViscoelasticSolverCardContent]
) -> None:
    content = draft.content
    scope = draft.scope
    common = {
        "organization_id": scope.organization_id,
        "project_id": scope.project_id,
        "classification": scope.classification,
        "solver_card_id": draft.aggregate_id,
        "solver_card_revision_id": draft.revision_id,
    }
    session.execute(
        sa.insert(linear_viscoelastic_solver_card_revision_table).values(
            **common,
            bulk_relaxation_status=content.bulk_relaxation_status.value,
            prony_terms_mapping_status=content.prony_terms_mapping_status,
            bulk_mapping_status=content.bulk_mapping_status,
            term_count=len(content.terms),
        )
    )
    session.execute(
        sa.insert(linear_viscoelastic_solver_card_term_table),
        [
            {
                **common,
                "ordinal": ordinal,
                "g_ratio": term.g_ratio,
                "k_ratio": term.k_ratio,
                "relaxation_time_s": term.relaxation_time_s,
            }
            for ordinal, term in enumerate(content.terms, 1)
        ],
    )


_TABLES = TypedRevisionTables[ReferenceLinearViscoelasticSolverCardContent](
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
    "youngs_modulus_mapping_status",
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


class SqlAlchemyLinearViscoelasticExportingRepository(LinearViscoelasticExportingRepository):
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
    ) -> RevisionStore[ReferenceLinearViscoelasticSolverCardContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=(*self._hooks, SqlSolverCardInputProvenanceHook(source_model_revision_id)),
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _base_statement() -> sa.Select[Any]:
        revision = solver_card_revision_table
        summary = linear_viscoelastic_solver_card_revision_table
        return (
            sa.select(
                *(revision.c[name] for name in _REVISION_COLUMNS),
                summary.c.bulk_relaxation_status,
                summary.c.prony_terms_mapping_status,
                summary.c.bulk_mapping_status,
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
            .where(revision.c.exporter_id == ABAQUS_PRONY_EXPORTER_ID)
        )

    @staticmethod
    def _terms(session: Session, row: Any) -> tuple[PronyTerm, ...]:
        terms = session.execute(
            sa.select(
                linear_viscoelastic_solver_card_term_table.c.g_ratio,
                linear_viscoelastic_solver_card_term_table.c.k_ratio,
                linear_viscoelastic_solver_card_term_table.c.relaxation_time_s,
            )
            .where(
                linear_viscoelastic_solver_card_term_table.c.organization_id
                == row["organization_id"],
                linear_viscoelastic_solver_card_term_table.c.project_id == row["project_id"],
                linear_viscoelastic_solver_card_term_table.c.solver_card_revision_id == row["id"],
            )
            .order_by(linear_viscoelastic_solver_card_term_table.c.ordinal)
        ).mappings()
        return tuple(
            PronyTerm(
                float(term["g_ratio"]),
                float(term["k_ratio"]),
                float(term["relaxation_time_s"]),
            )
            for term in terms
        )

    @classmethod
    def _snapshot(cls, session: Session, row: Any) -> LinearViscoelasticSolverCardSnapshot:
        content = ReferenceLinearViscoelasticSolverCardContent(
            material_model_id=cast(UUID, row["material_model_id"]),
            material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
            target=LinearViscoelasticExportTarget(
                str(row["target_solver"]),
                str(row["target_version"]),
                str(row["target_unit_system"]),
            ),
            solver_material_id=int(row["solver_material_id"]),
            material_name=str(row["material_name"]),
            density_kg_per_m3=float(row["density_kg_per_m3"]),
            youngs_modulus_pa=float(row["youngs_modulus_pa"]),
            poisson_ratio=float(row["poisson_ratio"]),
            bulk_relaxation_status=BulkRelaxationStatus(row["bulk_relaxation_status"]),
            terms=cls._terms(session, row),
            density_mapping_status=_status(row, "density_mapping_status"),
            elasticity_mapping_status=_status(row, "youngs_modulus_mapping_status"),
            prony_terms_mapping_status=_status(row, "prony_terms_mapping_status"),
            bulk_mapping_status=_status(row, "bulk_mapping_status"),
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
        return LinearViscoelasticSolverCardSnapshot(
            id=cast(UUID, row["aggregate_id"]),
            material_model_id=content.material_model_id,
            target=content.target,
            solver_material_id=content.solver_material_id,
            material_name=content.material_name,
            current=RevisionSnapshot(_record(row), content),
        )

    def get_solver_card(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        solver_card_id: UUID,
    ) -> LinearViscoelasticSolverCardSnapshot:
        statement = self._base_statement().where(
            solver_card_table.c.id == solver_card_id,
            solver_card_table.c.organization_id == context.organization_id,
            solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
                if row is None:
                    raise LinearViscoelasticSolverCardNotFound(
                        "linear-viscoelastic Solver Card is not visible"
                    )
                return self._snapshot(session, row)
            except DBAPIError as error:
                raise LinearViscoelasticSolverCardNotFound(
                    "linear-viscoelastic Solver Card is not available"
                ) from error

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[LinearViscoelasticSolverCardSnapshot, ...]:
        statement = (
            self._base_statement()
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
                raise LinearViscoelasticSolverCardNotFound(
                    "linear-viscoelastic Solver Cards are not available"
                ) from error
