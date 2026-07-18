"""PostgreSQL adapter for immutable cards generated from Neutral Material revisions."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol, cast
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from cmp.modules.exporting.application.neutral_hyperelastic_service import (
    NEUTRAL_SOLVER_CARD_AGGREGATE_TYPE,
    NeutralHyperelasticExportingRepository,
    NeutralHyperelasticSolverCardSnapshot,
)
from cmp.modules.exporting.application.service import RevisionSnapshot
from cmp.modules.exporting.domain.neutral_hyperelastic import (
    MappingStatus,
    NeutralHyperelasticExportTarget,
    NeutralHyperelasticSolverCardContent,
    NeutralHyperelasticSolverCardNotFound,
)
from cmp.modules.exporting.domain.neutral_solver import (
    NeutralCardContent,
    NeutralFamilySolverCardContent,
)
from cmp.modules.identity_access.domain.authorization import AuthorizationDecision
from cmp.modules.identity_access.domain.security import SecurityContext
from cmp.modules.modeling.domain.hyperelastic_families import HyperelasticFamily
from cmp.modules.modeling.domain.neutral_material import (
    NeutralArtifactReference,
    NeutralHyperelasticParameters,
    NeutralModelFamily,
    NeutralPronyTerm,
)
from cmp.shared.adapters.persistence.revisions import (
    SqlAlchemyRevisionStore,
    SqlRevisionHook,
    TypedRevisionTables,
)
from cmp.shared.application.revisions import RevisionStore
from cmp.shared.domain.revisions import RevisionDraft, RevisionRecord, TenantScope

metadata = sa.MetaData()

neutral_solver_card_table = sa.Table(
    "neutral_solver_card",
    metadata,
    sa.Column("id", sa.Uuid(), nullable=False),
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("target_solver", sa.String(64), nullable=False),
    sa.Column("target_version", sa.String(64), nullable=False),
    sa.Column("target_unit_system", sa.String(64), nullable=False),
    sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
    sa.Column("current_revision_id", sa.Uuid(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.Uuid(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="exporting",
)

neutral_solver_card_revision_table = sa.Table(
    "neutral_solver_card_revision",
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
    sa.Column("neutral_material_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_revision_id", sa.Uuid(), nullable=False),
    sa.Column("neutral_material_sha256", sa.CHAR(64), nullable=False),
    sa.Column("model_family", sa.String(64), nullable=True),
    sa.Column("model_schema_digest", sa.CHAR(64), nullable=True),
    sa.Column("family", sa.String(32), nullable=False),
    sa.Column("c10_pa", sa.Double(), nullable=True),
    sa.Column("c01_pa", sa.Double(), nullable=True),
    sa.Column("c20_pa", sa.Double(), nullable=True),
    sa.Column("c30_pa", sa.Double(), nullable=True),
    sa.Column("ogden_mu_pa", sa.Double(), nullable=True),
    sa.Column("ogden_alpha", sa.Double(), nullable=True),
    sa.Column("density_kg_per_m3", sa.Double(), nullable=False),
    sa.Column("youngs_modulus_pa", sa.Double(), nullable=True),
    sa.Column("poisson_ratio", sa.Double(), nullable=True),
    sa.Column("initial_yield_stress_pa", sa.Double(), nullable=True),
    sa.Column("hardening_curve_artifact_id", sa.Uuid(), nullable=True),
    sa.Column("hardening_curve_sha256", sa.CHAR(64), nullable=True),
    sa.Column("hardening_curve_schema_ref", sa.String(255), nullable=True),
    sa.Column("hardening_curve_point_count", sa.Integer(), nullable=True),
    sa.Column("bulk_relaxation_status", sa.String(32), nullable=True),
    sa.Column("reference_temperature_k", sa.Double(), nullable=True),
    sa.Column("applicable_strain_min", sa.Double(), nullable=True),
    sa.Column("applicable_strain_max", sa.Double(), nullable=True),
    sa.Column("applicable_time_min_s", sa.Double(), nullable=True),
    sa.Column("applicable_time_max_s", sa.Double(), nullable=True),
    sa.Column("target_solver", sa.String(64), nullable=False),
    sa.Column("target_version", sa.String(64), nullable=False),
    sa.Column("target_unit_system", sa.String(64), nullable=False),
    sa.Column("solver_material_id", sa.BigInteger(), nullable=False),
    sa.Column("material_name", sa.String(80), nullable=False),
    sa.Column("density_mapping_status", sa.String(32), nullable=False),
    sa.Column("constitutive_mapping_status", sa.String(32), nullable=False),
    sa.Column("volumetric_mapping_status", sa.String(32), nullable=False),
    sa.Column("applicability_mapping_status", sa.String(32), nullable=False),
    sa.Column("calibration_mapping_status", sa.String(32), nullable=False),
    sa.Column("unit_system_mapping_status", sa.String(32), nullable=False),
    sa.Column("mapping_report_sha256", sa.CHAR(64), nullable=False),
    sa.Column("card_text", sa.Text(), nullable=False),
    sa.Column("card_sha256", sa.CHAR(64), nullable=False),
    sa.Column("exporter_id", sa.String(255), nullable=False),
    sa.Column("exporter_version", sa.String(64), nullable=False),
    sa.Column("exporter_digest", sa.CHAR(64), nullable=False),
    sa.Column("non_production", sa.Boolean(), nullable=False),
    schema="exporting",
)

neutral_solver_card_mapping_item_table = sa.Table(
    "neutral_solver_card_mapping_item",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
    sa.Column("name", sa.String(80), nullable=False),
    sa.Column("status", sa.String(32), nullable=False),
    schema="exporting",
)

neutral_solver_card_prony_term_table = sa.Table(
    "neutral_solver_card_prony_term",
    metadata,
    sa.Column("organization_id", sa.Uuid(), nullable=False),
    sa.Column("project_id", sa.Uuid(), nullable=False),
    sa.Column("classification", sa.String(64), nullable=False),
    sa.Column("solver_card_id", sa.Uuid(), nullable=False),
    sa.Column("solver_card_revision_id", sa.Uuid(), nullable=False),
    sa.Column("ordinal", sa.SmallInteger(), nullable=False),
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
        aggregate_type=NEUTRAL_SOLVER_CARD_AGGREGATE_TYPE,
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


def _parameter_values(parameters: NeutralHyperelasticParameters) -> dict[str, float | None]:
    return {
        "c10_pa": parameters.c10_pa,
        "c01_pa": parameters.c01_pa,
        "c20_pa": parameters.c20_pa,
        "c30_pa": parameters.c30_pa,
        "ogden_mu_pa": parameters.mu_pa,
        "ogden_alpha": parameters.alpha,
    }


def _mapping(content: NeutralCardContent, name: str, default: MappingStatus) -> MappingStatus:
    return dict(content.mapping_statuses).get(name, default)


def _content_values(content: NeutralCardContent) -> dict[str, Any]:
    values: dict[str, Any] = {
        "neutral_material_id": content.neutral_material_id,
        "neutral_material_revision_id": content.neutral_material_revision_id,
        "neutral_material_sha256": content.neutral_material_sha256,
        "density_kg_per_m3": content.density_kg_per_m3,
        "applicable_strain_min": content.applicable_strain_min,
        "applicable_strain_max": content.applicable_strain_max,
        "target_solver": content.target.solver,
        "target_version": content.target.version,
        "target_unit_system": content.target.unit_system,
        "solver_material_id": content.solver_material_id,
        "material_name": content.material_name,
        "density_mapping_status": _mapping(content, "density", "not_applicable"),
        "constitutive_mapping_status": _mapping(
            content,
            "constitutive_parameters",
            _mapping(
                content,
                "isotropic_elasticity",
                _mapping(content, "instantaneous_isotropic_elasticity", "not_applicable"),
            ),
        ),
        "volumetric_mapping_status": _mapping(
            content,
            "volumetric_response",
            _mapping(content, "bulk_relaxation", "not_applicable"),
        ),
        "applicability_mapping_status": _mapping(content, "applicability", "not_applicable"),
        "calibration_mapping_status": _mapping(content, "calibration_evidence", "not_applicable"),
        "unit_system_mapping_status": _mapping(content, "unit_system", "not_applicable"),
        "mapping_report_sha256": content.mapping_report_sha256,
        "card_text": content.card_text,
        "card_sha256": content.card_sha256,
        "exporter_id": content.exporter_id,
        "exporter_version": content.exporter_version,
        "exporter_digest": content.exporter_digest,
        "non_production": True,
    }
    if isinstance(content, NeutralHyperelasticSolverCardContent):
        values.update(
            family=content.family.value,
            **_parameter_values(content.parameters),
        )
    else:
        curve = content.hardening_curve
        parameters = content.hyperelastic_parameters
        values.update(
            model_family=content.model_family.value,
            model_schema_digest=content.model_schema_digest,
            family=content.family,
            **(
                _parameter_values(parameters)
                if parameters is not None
                else {
                    "c10_pa": None,
                    "c01_pa": None,
                    "c20_pa": None,
                    "c30_pa": None,
                    "ogden_mu_pa": None,
                    "ogden_alpha": None,
                }
            ),
            youngs_modulus_pa=content.youngs_modulus_pa,
            poisson_ratio=content.poisson_ratio,
            initial_yield_stress_pa=content.initial_yield_stress_pa,
            hardening_curve_artifact_id=curve.artifact_id if curve else None,
            hardening_curve_sha256=curve.sha256 if curve else None,
            hardening_curve_schema_ref=curve.schema_ref if curve else None,
            hardening_curve_point_count=curve.point_count if curve else None,
            bulk_relaxation_status=content.bulk_relaxation_status,
            reference_temperature_k=content.reference_temperature_k,
            applicable_time_min_s=content.applicable_time_min_s,
            applicable_time_max_s=content.applicable_time_max_s,
        )
    return values


def _write_family_rows(session: Session, draft: RevisionDraft[NeutralCardContent]) -> None:
    content = draft.content
    if isinstance(content, NeutralHyperelasticSolverCardContent):
        return
    session.execute(
        sa.insert(neutral_solver_card_mapping_item_table),
        [
            {
                "organization_id": draft.scope.organization_id,
                "project_id": draft.scope.project_id,
                "classification": draft.scope.classification,
                "solver_card_id": draft.aggregate_id,
                "solver_card_revision_id": draft.revision_id,
                "ordinal": ordinal,
                "name": name,
                "status": status,
            }
            for ordinal, (name, status) in enumerate(content.mapping_statuses, 1)
        ],
    )
    if content.prony_terms:
        session.execute(
            sa.insert(neutral_solver_card_prony_term_table),
            [
                {
                    "organization_id": draft.scope.organization_id,
                    "project_id": draft.scope.project_id,
                    "classification": draft.scope.classification,
                    "solver_card_id": draft.aggregate_id,
                    "solver_card_revision_id": draft.revision_id,
                    "ordinal": term.ordinal,
                    "g_ratio": term.g_ratio,
                    "k_ratio": term.k_ratio,
                    "relaxation_time_s": term.relaxation_time_s,
                }
                for term in content.prony_terms
            ],
        )


_TABLES = TypedRevisionTables[NeutralCardContent](
    aggregate_type=NEUTRAL_SOLVER_CARD_AGGREGATE_TYPE,
    identity_table=neutral_solver_card_table,
    revision_table=neutral_solver_card_revision_table,
    canonical_content=lambda content: content.canonical(),
    content_values=_content_values,
    identity_values=lambda content: {
        "neutral_material_id": content.neutral_material_id,
        "target_solver": content.target.solver,
        "target_version": content.target.version,
        "target_unit_system": content.target.unit_system,
        "solver_material_id": content.solver_material_id,
    },
    revision_content_writer=_write_family_rows,
)


class SqlAlchemyNeutralHyperelasticExportingRepository(NeutralHyperelasticExportingRepository):
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
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> RevisionStore[NeutralCardContent]:
        return SqlAlchemyRevisionStore(
            session_factory=self._sessions,
            tables=_TABLES,
            hooks=self._hooks,
            session_binder=lambda session: self._bind(session, context, decision),
        )

    @staticmethod
    def _statement() -> sa.Select[Any]:
        identity = neutral_solver_card_table
        revision = neutral_solver_card_revision_table
        return sa.select(*(revision.c[column.name] for column in revision.c)).select_from(
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

    @staticmethod
    def _parameters(row: Any) -> NeutralHyperelasticParameters:
        return NeutralHyperelasticParameters(
            HyperelasticFamily(str(row["family"])),
            c10_pa=float(row["c10_pa"]) if row["c10_pa"] is not None else None,
            c01_pa=float(row["c01_pa"]) if row["c01_pa"] is not None else None,
            c20_pa=float(row["c20_pa"]) if row["c20_pa"] is not None else None,
            c30_pa=float(row["c30_pa"]) if row["c30_pa"] is not None else None,
            mu_pa=float(row["ogden_mu_pa"]) if row["ogden_mu_pa"] is not None else None,
            alpha=float(row["ogden_alpha"]) if row["ogden_alpha"] is not None else None,
        )

    @classmethod
    def _snapshot(cls, session: Session, row: Any) -> NeutralHyperelasticSolverCardSnapshot:
        target = NeutralHyperelasticExportTarget(
            str(row["target_solver"]),
            str(row["target_version"]),
            str(row["target_unit_system"]),
        )
        if row["model_family"] is None:
            statuses: tuple[tuple[str, MappingStatus], ...] = (
                ("density", cast(MappingStatus, str(row["density_mapping_status"]))),
                (
                    "constitutive_parameters",
                    cast(MappingStatus, str(row["constitutive_mapping_status"])),
                ),
                (
                    "volumetric_response",
                    cast(MappingStatus, str(row["volumetric_mapping_status"])),
                ),
                (
                    "applicability",
                    cast(MappingStatus, str(row["applicability_mapping_status"])),
                ),
                (
                    "calibration_evidence",
                    cast(MappingStatus, str(row["calibration_mapping_status"])),
                ),
                ("unit_system", cast(MappingStatus, str(row["unit_system_mapping_status"]))),
            )
            content: NeutralCardContent = NeutralHyperelasticSolverCardContent(
                neutral_material_id=cast(UUID, row["neutral_material_id"]),
                neutral_material_revision_id=cast(UUID, row["neutral_material_revision_id"]),
                neutral_material_sha256=str(row["neutral_material_sha256"]),
                family=HyperelasticFamily(str(row["family"])),
                target=target,
                solver_material_id=int(row["solver_material_id"]),
                material_name=str(row["material_name"]),
                density_kg_per_m3=float(row["density_kg_per_m3"]),
                parameters=cls._parameters(row),
                applicable_strain_min=float(row["applicable_strain_min"]),
                applicable_strain_max=float(row["applicable_strain_max"]),
                mapping_statuses=statuses,
                mapping_report_sha256=str(row["mapping_report_sha256"]),
                card_text=str(row["card_text"]),
                card_sha256=str(row["card_sha256"]),
                exporter_id=str(row["exporter_id"]),
                exporter_version=str(row["exporter_version"]),
                exporter_digest=str(row["exporter_digest"]),
            )
        else:
            status_rows = session.execute(
                sa.select(
                    neutral_solver_card_mapping_item_table.c.name,
                    neutral_solver_card_mapping_item_table.c.status,
                )
                .where(
                    neutral_solver_card_mapping_item_table.c.organization_id
                    == row["organization_id"],
                    neutral_solver_card_mapping_item_table.c.project_id == row["project_id"],
                    neutral_solver_card_mapping_item_table.c.solver_card_revision_id == row["id"],
                )
                .order_by(neutral_solver_card_mapping_item_table.c.ordinal)
            ).all()
            statuses = tuple(
                (str(item.name), cast(MappingStatus, str(item.status))) for item in status_rows
            )
            term_rows = (
                session.execute(
                    sa.select(neutral_solver_card_prony_term_table)
                    .where(
                        neutral_solver_card_prony_term_table.c.organization_id
                        == row["organization_id"],
                        neutral_solver_card_prony_term_table.c.project_id == row["project_id"],
                        neutral_solver_card_prony_term_table.c.solver_card_revision_id == row["id"],
                    )
                    .order_by(neutral_solver_card_prony_term_table.c.ordinal)
                )
                .mappings()
                .all()
            )
            terms = tuple(
                NeutralPronyTerm(
                    int(item["ordinal"]),
                    float(item["g_ratio"]),
                    float(item["k_ratio"]),
                    float(item["relaxation_time_s"]),
                )
                for item in term_rows
            )
            model_family = NeutralModelFamily(str(row["model_family"]))
            curve = (
                NeutralArtifactReference(
                    cast(UUID, row["hardening_curve_artifact_id"]),
                    str(row["hardening_curve_sha256"]),
                    str(row["hardening_curve_schema_ref"]),
                    int(row["hardening_curve_point_count"]),
                )
                if row["hardening_curve_artifact_id"] is not None
                else None
            )
            parameters = (
                cls._parameters(row) if model_family is NeutralModelFamily.HYPERELASTIC else None
            )
            content = NeutralFamilySolverCardContent(
                neutral_material_id=cast(UUID, row["neutral_material_id"]),
                neutral_material_revision_id=cast(UUID, row["neutral_material_revision_id"]),
                neutral_material_sha256=str(row["neutral_material_sha256"]),
                model_family=model_family,
                family=str(row["family"]),
                model_schema_digest=str(row["model_schema_digest"]),
                target=target,
                solver_material_id=int(row["solver_material_id"]),
                material_name=str(row["material_name"]),
                density_kg_per_m3=float(row["density_kg_per_m3"]),
                hyperelastic_parameters=parameters,
                youngs_modulus_pa=(
                    float(row["youngs_modulus_pa"])
                    if row["youngs_modulus_pa"] is not None
                    else None
                ),
                poisson_ratio=(
                    float(row["poisson_ratio"]) if row["poisson_ratio"] is not None else None
                ),
                initial_yield_stress_pa=(
                    float(row["initial_yield_stress_pa"])
                    if row["initial_yield_stress_pa"] is not None
                    else None
                ),
                hardening_curve=curve,
                prony_terms=terms,
                bulk_relaxation_status=(
                    str(row["bulk_relaxation_status"])
                    if row["bulk_relaxation_status"] is not None
                    else None
                ),
                reference_temperature_k=(
                    float(row["reference_temperature_k"])
                    if row["reference_temperature_k"] is not None
                    else None
                ),
                applicable_strain_min=(
                    float(row["applicable_strain_min"])
                    if row["applicable_strain_min"] is not None
                    else None
                ),
                applicable_strain_max=(
                    float(row["applicable_strain_max"])
                    if row["applicable_strain_max"] is not None
                    else None
                ),
                applicable_time_min_s=(
                    float(row["applicable_time_min_s"])
                    if row["applicable_time_min_s"] is not None
                    else None
                ),
                applicable_time_max_s=(
                    float(row["applicable_time_max_s"])
                    if row["applicable_time_max_s"] is not None
                    else None
                ),
                mapping_statuses=statuses,
                mapping_report_sha256=str(row["mapping_report_sha256"]),
                card_text=str(row["card_text"]),
                card_sha256=str(row["card_sha256"]),
                exporter_id=str(row["exporter_id"]),
                exporter_version=str(row["exporter_version"]),
                exporter_digest=str(row["exporter_digest"]),
            )
        return NeutralHyperelasticSolverCardSnapshot(
            cast(UUID, row["aggregate_id"]),
            content.neutral_material_id,
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
    ) -> NeutralHyperelasticSolverCardSnapshot:
        statement = self._statement().where(
            neutral_solver_card_table.c.id == solver_card_id,
            neutral_solver_card_table.c.organization_id == context.organization_id,
            neutral_solver_card_table.c.project_id == context.project_id,
        )
        with self._session(context, decision) as session:
            try:
                row = session.execute(statement).mappings().one_or_none()
            except DBAPIError as error:
                raise NeutralHyperelasticSolverCardNotFound("solver card is unavailable") from error
            if row is None:
                raise NeutralHyperelasticSolverCardNotFound("solver card is not visible")
            return self._snapshot(session, row)

    def list_solver_cards_for_neutral_material(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        neutral_material_id: UUID,
    ) -> tuple[NeutralHyperelasticSolverCardSnapshot, ...]:
        statement = (
            self._statement()
            .where(
                neutral_solver_card_table.c.neutral_material_id == neutral_material_id,
                neutral_solver_card_table.c.organization_id == context.organization_id,
                neutral_solver_card_table.c.project_id == context.project_id,
            )
            .order_by(neutral_solver_card_revision_table.c.created_at.desc())
        )
        with self._session(context, decision) as session:
            rows = session.execute(statement).mappings().all()
            return tuple(self._snapshot(session, row) for row in rows)
