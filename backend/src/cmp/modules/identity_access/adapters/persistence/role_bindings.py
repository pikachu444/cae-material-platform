"""PostgreSQL role-binding resolution under subject-scoped RLS."""

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
    Role,
    RoleBinding,
    RoleBindingConflict,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from sqlalchemy.orm import Session

_metadata = sa.MetaData()

ROLE_BINDING = sa.Table(
    "role_binding",
    _metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("organization_id", sa.Uuid()),
    sa.Column("project_id", sa.Uuid()),
    sa.Column("classification", sa.String()),
    sa.Column("subject_type", sa.String()),
    sa.Column("principal_id", sa.Uuid()),
    sa.Column("group_issuer", sa.String()),
    sa.Column("group_name", sa.String()),
    sa.Column("role", sa.String()),
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


class SqlAlchemyRoleBindingRepository:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        rls_context: SqlAlchemyRlsContext,
    ) -> None:
        self._session_factory = session_factory
        self._rls_context = rls_context

    @staticmethod
    def _subject(row: sa.Row[tuple[object, ...]]) -> BindingSubject:
        if row.subject_type == "principal":
            return BindingSubject.for_principal(row.principal_id)
        if row.subject_type == "group":
            return BindingSubject.for_group(row.group_issuer, row.group_name)
        raise AuthorizationUnavailable("role binding contains an invalid subject type")

    @classmethod
    def _binding(cls, row: sa.Row[tuple[object, ...]]) -> RoleBinding:
        return RoleBinding(
            id=row.id,
            organization_id=row.organization_id,
            project_id=row.project_id,
            subject=cls._subject(row),
            role=Role(row.role),
            max_classification=DataClassification(row.max_classification),
            allow_export_controlled=row.allow_export_controlled,
            valid_from=row.valid_from,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )

    def find_applicable(
        self, context: SecurityContext, observed_at: datetime
    ) -> tuple[RoleBinding, ...]:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        subjects: list[sa.ColumnElement[bool]] = [
            sa.and_(
                ROLE_BINDING.c.subject_type == "principal",
                ROLE_BINDING.c.principal_id == context.principal.id,
            )
        ]
        if context.groups:
            subjects.append(
                sa.and_(
                    ROLE_BINDING.c.subject_type == "group",
                    ROLE_BINDING.c.group_issuer == context.issuer,
                    ROLE_BINDING.c.group_name.in_(context.groups),
                )
            )
        query = (
            sa.select(
                ROLE_BINDING.c.id,
                ROLE_BINDING.c.organization_id,
                ROLE_BINDING.c.project_id,
                ROLE_BINDING.c.subject_type,
                ROLE_BINDING.c.principal_id,
                ROLE_BINDING.c.group_issuer,
                ROLE_BINDING.c.group_name,
                ROLE_BINDING.c.role,
                ROLE_BINDING.c.max_classification,
                ROLE_BINDING.c.allow_export_controlled,
                ROLE_BINDING.c.valid_from,
                ROLE_BINDING.c.expires_at,
                ROLE_BINDING.c.revoked_at,
            )
            .where(
                ROLE_BINDING.c.organization_id == context.organization_id,
                sa.or_(
                    ROLE_BINDING.c.project_id.is_(None),
                    ROLE_BINDING.c.project_id == context.project_id,
                ),
                ROLE_BINDING.c.revoked_at.is_(None),
                ROLE_BINDING.c.valid_from <= observed_at,
                sa.or_(
                    ROLE_BINDING.c.expires_at.is_(None),
                    ROLE_BINDING.c.expires_at > observed_at,
                ),
                sa.or_(*subjects),
            )
            .order_by(ROLE_BINDING.c.id)
        )
        try:
            with self._session_factory() as session, session.begin():
                self._rls_context.bind_authentication(session, context)
                rows = session.execute(query).all()
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("role binding store is unavailable") from error
        try:
            return tuple(self._binding(row) for row in rows)
        except (TypeError, ValueError) as error:
            raise AuthorizationUnavailable("role binding data is invalid") from error

    def append(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding: RoleBinding,
        created_at: datetime,
        grant_reason: str,
    ) -> RoleBinding:
        subject_values = {
            "subject_type": "principal" if binding.subject.principal_id else "group",
            "principal_id": binding.subject.principal_id,
            "group_issuer": binding.subject.group_issuer,
            "group_name": binding.subject.group_name,
        }
        try:
            with self._session_factory() as session, session.begin():
                self._rls_context.bind_authorization(session, context, decision)
                session.execute(
                    sa.insert(ROLE_BINDING).values(
                        id=binding.id,
                        organization_id=binding.organization_id,
                        project_id=binding.project_id,
                        classification="restricted",
                        **subject_values,
                        role=binding.role.value,
                        max_classification=binding.max_classification.value,
                        allow_export_controlled=binding.allow_export_controlled,
                        valid_from=binding.valid_from,
                        expires_at=binding.expires_at,
                        created_at=created_at,
                        created_by=context.principal.id,
                        grant_reason=grant_reason,
                    )
                )
        except sa.exc.IntegrityError as error:
            raise RoleBindingConflict("role_binding_conflict") from error
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("role binding store is unavailable") from error
        return binding

    def revoke(
        self,
        *,
        context: SecurityContext,
        decision: AuthorizationDecision,
        binding_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        try:
            with self._session_factory() as session, session.begin():
                self._rls_context.bind_authorization(session, context, decision)
                result = session.execute(
                    sa.update(ROLE_BINDING)
                    .where(
                        ROLE_BINDING.c.id == binding_id,
                        ROLE_BINDING.c.revoked_at.is_(None),
                    )
                    .values(
                        revoked_at=revoked_at,
                        revoked_by=context.principal.id,
                        revocation_reason=reason,
                    )
                )
                if getattr(result, "rowcount", None) != 1:
                    raise AuthorizationDenied("role_binding_not_found_or_forbidden")
        except AuthorizationDenied:
            raise
        except sa.exc.SQLAlchemyError as error:
            raise AuthorizationUnavailable("role binding store is unavailable") from error
