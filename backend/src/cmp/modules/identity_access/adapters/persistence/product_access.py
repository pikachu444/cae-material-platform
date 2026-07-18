"""PostgreSQL adapter for T-59 product-facing access assignments."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from cmp.modules.identity_access.adapters.persistence.rls import SqlAlchemyRlsContext
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    AuthorizationDenied,
    AuthorizationUnavailable,
    BindingSubject,
    DataClassification,
    FeatureGrant,
    ProductAccessAssignment,
    ProductRole,
    RoleBindingConflict,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from sqlalchemy.orm import Session

_metadata = sa.MetaData()

PRODUCT_ACCESS_ASSIGNMENT = sa.Table(
    "product_access_assignment",
    _metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("organization_id", sa.Uuid()),
    sa.Column("project_id", sa.Uuid()),
    sa.Column("classification", sa.String()),
    sa.Column("subject_type", sa.String()),
    sa.Column("principal_id", sa.Uuid()),
    sa.Column("group_issuer", sa.String()),
    sa.Column("group_name", sa.String()),
    sa.Column("product_role", sa.String()),
    sa.Column("schema_configuration", sa.Boolean()),
    sa.Column("catalog_edit", sa.Boolean()),
    sa.Column("processing_calibration", sa.Boolean()),
    sa.Column("model_approval", sa.Boolean()),
    sa.Column("solver_card_export", sa.Boolean()),
    sa.Column("max_classification", sa.String()),
    sa.Column("allow_export_controlled", sa.Boolean()),
    sa.Column("valid_from", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("created_by", sa.Uuid()),
    sa.Column("grant_reason", sa.Text()),
    sa.Column("revoked_at", sa.DateTime(timezone=True)),
    sa.Column("revoked_by", sa.Uuid()),
    sa.Column("revocation_reason", sa.Text()),
    schema="identity",
)

_FEATURE_COLUMNS = {
    FeatureGrant.SCHEMA_CONFIGURATION: "schema_configuration",
    FeatureGrant.CATALOG_EDIT: "catalog_edit",
    FeatureGrant.PROCESSING_CALIBRATION: "processing_calibration",
    FeatureGrant.MODEL_APPROVAL: "model_approval",
    FeatureGrant.SOLVER_CARD_EXPORT: "solver_card_export",
}


class SqlAlchemyProductAccessRepository:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: SqlAlchemyRlsContext,
    ) -> None:
        self._session_factory = session_factory
        self._rls_context = rls_context

    @staticmethod
    def _assignment(row: sa.Row[tuple[object, ...]]) -> ProductAccessAssignment:
        subject = (
            BindingSubject.for_principal(row.principal_id)
            if row.subject_type == "principal"
            else BindingSubject.for_group(row.group_issuer, row.group_name)
        )
        grants = tuple(
            sorted(
                (
                    grant
                    for grant, column in _FEATURE_COLUMNS.items()
                    if bool(getattr(row, column))
                ),
                key=str,
            )
        )
        return ProductAccessAssignment(
            id=row.id,
            organization_id=row.organization_id,
            project_id=row.project_id,
            subject=subject,
            product_role=ProductRole(row.product_role),
            feature_grants=grants,
            max_classification=DataClassification(row.max_classification),
            allow_export_controlled=bool(row.allow_export_controlled),
            valid_from=row.valid_from,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )

    @staticmethod
    def _select() -> sa.Select[tuple[object, ...]]:
        return sa.select(PRODUCT_ACCESS_ASSIGNMENT)

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[ProductAccessAssignment, ...]:
        query = self._select().where(
            PRODUCT_ACCESS_ASSIGNMENT.c.organization_id == context.organization_id,
            sa.or_(
                PRODUCT_ACCESS_ASSIGNMENT.c.project_id.is_(None),
                PRODUCT_ACCESS_ASSIGNMENT.c.project_id == context.project_id,
            ),
            PRODUCT_ACCESS_ASSIGNMENT.c.revoked_at.is_(None),
            PRODUCT_ACCESS_ASSIGNMENT.c.valid_from <= observed_at,
            sa.or_(
                PRODUCT_ACCESS_ASSIGNMENT.c.expires_at.is_(None),
                PRODUCT_ACCESS_ASSIGNMENT.c.expires_at > observed_at,
            ),
        ).order_by(PRODUCT_ACCESS_ASSIGNMENT.c.id)
        return self._read(context=context, decision=None, query=query)

    def list_assignments(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> tuple[ProductAccessAssignment, ...]:
        query = self._select().where(
            PRODUCT_ACCESS_ASSIGNMENT.c.organization_id == context.organization_id,
            sa.or_(
                PRODUCT_ACCESS_ASSIGNMENT.c.project_id.is_(None),
                PRODUCT_ACCESS_ASSIGNMENT.c.project_id == context.project_id,
            ),
        ).order_by(
            PRODUCT_ACCESS_ASSIGNMENT.c.revoked_at.is_not(None),
            PRODUCT_ACCESS_ASSIGNMENT.c.created_at.desc(),
            PRODUCT_ACCESS_ASSIGNMENT.c.id,
        )
        return self._read(context=context, decision=decision, query=query)

    def _read(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision | None,
        query: sa.Select[tuple[object, ...]],
    ) -> tuple[ProductAccessAssignment, ...]:
        try:
            with self._session_factory() as session, session.begin():
                if decision is None:
                    self._rls_context.bind_authentication(session, context)
                else:
                    self._rls_context.bind_authorization(session, context, decision)
                rows = session.execute(query).all()
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("product access store is unavailable") from error
        try:
            return tuple(self._assignment(row) for row in rows)
        except (TypeError, ValueError) as error:
            raise AuthorizationUnavailable("product access data is invalid") from error

    def append_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment: ProductAccessAssignment,
        created_at: datetime,
        grant_reason: str,
    ) -> ProductAccessAssignment:
        subject_values = {
            "subject_type": "principal" if assignment.subject.principal_id else "group",
            "principal_id": assignment.subject.principal_id,
            "group_issuer": assignment.subject.group_issuer,
            "group_name": assignment.subject.group_name,
        }
        feature_values = {
            column: grant in assignment.feature_grants
            for grant, column in _FEATURE_COLUMNS.items()
        }
        try:
            with self._session_factory() as session, session.begin():
                self._rls_context.bind_authorization(session, context, decision)
                session.execute(
                    sa.insert(PRODUCT_ACCESS_ASSIGNMENT).values(
                        id=assignment.id,
                        organization_id=assignment.organization_id,
                        project_id=assignment.project_id,
                        classification="restricted",
                        **subject_values,
                        product_role=assignment.product_role.value,
                        **feature_values,
                        max_classification=assignment.max_classification.value,
                        allow_export_controlled=assignment.allow_export_controlled,
                        valid_from=assignment.valid_from,
                        expires_at=assignment.expires_at,
                        created_at=created_at,
                        created_by=context.principal.id,
                        grant_reason=grant_reason,
                    )
                )
        except sa.exc.IntegrityError as error:
            raise RoleBindingConflict("product_access_assignment_conflict") from error
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("product access store is unavailable") from error
        return assignment

    def revoke_assignment(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        assignment_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        try:
            with self._session_factory() as session, session.begin():
                self._rls_context.bind_authorization(session, context, decision)
                result = session.execute(
                    sa.update(PRODUCT_ACCESS_ASSIGNMENT)
                    .where(
                        PRODUCT_ACCESS_ASSIGNMENT.c.id == assignment_id,
                        PRODUCT_ACCESS_ASSIGNMENT.c.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=revoked_at,
                        revoked_by=context.principal.id,
                        revocation_reason=reason,
                    )
                )
                if getattr(result, "rowcount", None) != 1:
                    raise AuthorizationDenied("product_access_not_found_or_forbidden")
        except AuthorizationDenied:
            raise
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("product access store is unavailable") from error
