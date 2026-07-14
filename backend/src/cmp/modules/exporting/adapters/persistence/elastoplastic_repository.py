"""PostgreSQL adapter for OpenRadioss LAW36 and Abaqus plastic card revisions."""

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
from cmp.modules.exporting.application.elastoplastic_service import (
    ElastoplasticExportingRepository,
    ElastoplasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import SOLVER_CARD_AGGREGATE_TYPE, RevisionSnapshot
from cmp.modules.exporting.domain.reference_isotropic_tabulated_plasticity import (
    ABAQUS_PLASTIC_EXPORTER_ID,
    OPENRADIOSS_LAW36_EXPORTER_ID,
    ElastoplasticExportTarget,
    ElastoplasticSolverCardNotFound,
    MappingStatus,
    ReferenceElastoplasticSolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionRecord, TenantScope

_EXPORTER_IDS = (OPENRADIOSS_LAW36_EXPORTER_ID, ABAQUS_PLASTIC_EXPORTER_ID)


class RlsContext(Protocol):
    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
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


def _content(row: Any) -> ReferenceElastoplasticSolverCardContent:
    return ReferenceElastoplasticSolverCardContent(
        material_model_id=cast(UUID, row["material_model_id"]),
        material_model_revision_id=cast(UUID, row["material_model_revision_id"]),
        target=ElastoplasticExportTarget(
            str(row["target_solver"]),
            str(row["target_version"]),
            str(row["target_unit_system"]),
        ),
        solver_material_id=int(row["solver_material_id"]),
        material_name=str(row["material_name"]),
        density_kg_per_m3=float(row["density_kg_per_m3"]),
        youngs_modulus_pa=float(row["youngs_modulus_pa"]),
        poisson_ratio=float(row["poisson_ratio"]),
        initial_yield_stress_pa=float(row["source_yield_stress_pa"]),
        hardening_curve_artifact_id=cast(UUID, row["hardening_curve_artifact_id"]),
        hardening_curve_sha256=str(row["hardening_curve_sha256"]),
        hardening_curve_point_count=int(row["hardening_curve_point_count"]),
        extension_max_true_plastic_strain=float(
            row["extension_max_true_plastic_strain"]
        ),
        post_necking_extension_policy=str(row["post_necking_extension_policy"]),
        applicable_temperature_min_k=row["applicable_temperature_min_k"],
        applicable_temperature_max_k=row["applicable_temperature_max_k"],
        applicable_strain_rate_min_per_s=row["applicable_strain_rate_min_per_s"],
        applicable_strain_rate_max_per_s=row["applicable_strain_rate_max_per_s"],
        applicability_note=row["applicability_note"],
        density_mapping_status=_status(row, "density_mapping_status"),
        elasticity_mapping_status=_status(row, "youngs_modulus_mapping_status"),
        initial_yield_mapping_status=_status(row, "source_yield_mapping_status"),
        hardening_curve_mapping_status=_status(row, "hardening_curve_mapping_status"),
        extension_mapping_status=_status(row, "extension_mapping_status"),
        temperature_mapping_status=_status(
            row, "temperature_applicability_mapping_status"
        ),
        strain_rate_mapping_status=_status(
            row, "strain_rate_applicability_mapping_status"
        ),
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


def _content_values(content: ReferenceElastoplasticSolverCardContent) -> dict[str, Any]:
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
        "source_yield_stress_pa": content.initial_yield_stress_pa,
        "applicable_temperature_min_k": content.applicable_temperature_min_k,
        "applicable_temperature_max_k": content.applicable_temperature_max_k,
        "applicable_strain_rate_min_per_s": content.applicable_strain_rate_min_per_s,
        "applicable_strain_rate_max_per_s": content.applicable_strain_rate_max_per_s,
        "applicability_note": content.applicability_note,
        "hardening_curve_artifact_id": content.hardening_curve_artifact_id,
        "hardening_curve_sha256": content.hardening_curve_sha256,
        "hardening_curve_point_count": content.hardening_curve_point_count,
        "extension_max_true_plastic_strain": content.extension_max_true_plastic_strain,
        "post_necking_extension_policy": content.post_necking_extension_policy,
        "density_mapping_status": content.density_mapping_status,
        "youngs_modulus_mapping_status": content.elasticity_mapping_status,
        "poisson_ratio_mapping_status": content.elasticity_mapping_status,
        "source_yield_mapping_status": content.initial_yield_mapping_status,
        "hardening_curve_mapping_status": content.hardening_curve_mapping_status,
        "extension_mapping_status": content.extension_mapping_status,
        "temperature_applicability_mapping_status": content.temperature_mapping_status,
        "strain_rate_applicability_mapping_status": content.strain_rate_mapping_status,
        "unit_system_mapping_status": content.unit_system_mapping_status,
        "mapping_report_sha256": content.mapping_report_sha256,
        "card_text": content.card_text,
        "card_sha256": content.card_sha256,
        "exporter_id": content.exporter_id,
        "exporter_version": content.exporter_version,
        "exporter_digest": content.exporter_digest,
        "non_production": content.non_production,
    }


_TABLES: TypedRevisionTables[ReferenceElastoplasticSolverCardContent] = TypedRevisionTables(
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
)


def _columns(table: sa.Table) -> tuple[Any, ...]:
    return (
        table.c.id.label("id"),
        table.c.aggregate_id.label("aggregate_id"),
        table.c.organization_id.label("organization_id"),
        table.c.project_id.label("project_id"),
        table.c.classification.label("classification"),
        table.c.revision_no.label("revision_no"),
        table.c.based_on_revision_id.label("based_on_revision_id"),
        table.c.schema_id.label("schema_id"),
        table.c.schema_version.label("schema_version"),
        table.c.content_hash.label("content_hash"),
        table.c.created_at.label("created_at"),
        table.c.created_by.label("created_by"),
        table.c.change_reason.label("change_reason"),
        table.c.request_id.label("request_id"),
        table.c.trace_id.label("trace_id"),
        table.c.material_model_id,
        table.c.material_model_revision_id,
        table.c.model_schema_digest,
        table.c.target_solver,
        table.c.target_version,
        table.c.target_unit_system,
        table.c.solver_material_id,
        table.c.material_name,
        table.c.density_kg_per_m3,
        table.c.youngs_modulus_pa,
        table.c.poisson_ratio,
        table.c.source_yield_stress_pa,
        table.c.applicable_temperature_min_k,
        table.c.applicable_temperature_max_k,
        table.c.applicable_strain_rate_min_per_s,
        table.c.applicable_strain_rate_max_per_s,
        table.c.applicability_note,
        table.c.hardening_curve_artifact_id,
        table.c.hardening_curve_sha256,
        table.c.hardening_curve_point_count,
        table.c.extension_max_true_plastic_strain,
        table.c.post_necking_extension_policy,
        table.c.density_mapping_status,
        table.c.youngs_modulus_mapping_status,
        table.c.source_yield_mapping_status,
        table.c.hardening_curve_mapping_status,
        table.c.extension_mapping_status,
        table.c.temperature_applicability_mapping_status,
        table.c.strain_rate_applicability_mapping_status,
        table.c.unit_system_mapping_status,
        table.c.mapping_report_sha256,
        table.c.card_text,
        table.c.card_sha256,
        table.c.exporter_id,
        table.c.exporter_version,
        table.c.exporter_digest,
        table.c.non_production,
    )


class SqlAlchemyElastoplasticExportingRepository(ElastoplasticExportingRepository):
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
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        self._rls.bind_authorization(session, context, decision)

    @contextmanager
    def _session(
        self,
        context: SecurityContext,
        decision: AuthorizationDecision,
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
    ) -> RevisionStore[ReferenceElastoplasticSolverCardContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=(*self._hooks, SqlSolverCardInputProvenanceHook(source_model_revision_id)),
            session_binder=lambda session: self._bind(session, context, decision),
        )

    def _current_statement(self) -> sa.Select[Any]:
        identity = solver_card_table
        revision = solver_card_revision_table
        return (
            sa.select(*_columns(revision))
            .select_from(
                identity.join(
                    revision,
                    sa.and_(
                        revision.c.id == identity.c.current_revision_id,
                        revision.c.aggregate_id == identity.c.id,
                        revision.c.organization_id == identity.c.organization_id,
                        revision.c.project_id == identity.c.project_id,
                    ),
                )
            )
            .where(revision.c.exporter_id.in_(_EXPORTER_IDS))
        )

    @staticmethod
    def _snapshot(row: Any) -> ElastoplasticSolverCardSnapshot:
        content = _content(row)
        return ElastoplasticSolverCardSnapshot(
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
    ) -> ElastoplasticSolverCardSnapshot:
        statement = self._current_statement().where(
            solver_card_table.c.id == solver_card_id,
            solver_card_table.c.organization_id == context.organization_id,
            solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise ElastoplasticSolverCardNotFound(
                    "elastoplastic Solver Card is not available"
                ) from error
        if row is None:
            raise ElastoplasticSolverCardNotFound(
                "elastoplastic Solver Card is not visible in this tenant"
            )
        return self._snapshot(row)

    def list_solver_cards_for_model(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        material_model_id: UUID,
    ) -> tuple[ElastoplasticSolverCardSnapshot, ...]:
        statement = (
            self._current_statement()
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
            except DBAPIError as error:
                raise ElastoplasticSolverCardNotFound(
                    "elastoplastic Solver Cards are not available"
                ) from error
        return tuple(self._snapshot(row) for row in rows)
