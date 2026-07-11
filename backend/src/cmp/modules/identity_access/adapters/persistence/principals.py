"""PostgreSQL principal and immutable external-identity resolution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa
from cmp.modules.identity_access.domain.security import (
    AccessDenied,
    AuthenticationFailed,
    AuthenticationUnavailable,
    Principal,
    PrincipalType,
    VerifiedAccessToken,
)
from sqlalchemy.orm import Session

_metadata = sa.MetaData()

PRINCIPAL = sa.Table(
    "principal",
    _metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("principal_type", sa.String()),
    sa.Column("display_name", sa.String()),
    sa.Column("active", sa.Boolean()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    schema="identity",
)

EXTERNAL_IDENTITY = sa.Table(
    "external_identity",
    _metadata,
    sa.Column("id", sa.Uuid()),
    sa.Column("principal_id", sa.Uuid()),
    sa.Column("issuer", sa.String()),
    sa.Column("subject", sa.String()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    schema="identity",
)

class SqlAlchemyPrincipalRepository:
    """Resolve a trusted issuer/subject pair and optionally provision its projection."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        auto_provision: bool,
    ) -> None:
        self._session_factory = session_factory
        self._auto_provision = auto_provision

    @staticmethod
    def _principal(row: sa.Row[tuple[object, ...]]) -> Principal:
        return Principal(
            id=row.id,
            principal_type=PrincipalType(row.principal_type),
            display_name=row.display_name,
            active=row.active,
        )

    @staticmethod
    def _select(issuer: str, subject: str) -> sa.Select[tuple[object, ...]]:
        return (
            sa.select(
                PRINCIPAL.c.id,
                PRINCIPAL.c.principal_type,
                PRINCIPAL.c.display_name,
                PRINCIPAL.c.active,
                EXTERNAL_IDENTITY.c.id.label("external_identity_id"),
            )
            .select_from(
                EXTERNAL_IDENTITY.join(
                    PRINCIPAL, EXTERNAL_IDENTITY.c.principal_id == PRINCIPAL.c.id
                )
            )
            .where(
                EXTERNAL_IDENTITY.c.issuer == issuer,
                EXTERNAL_IDENTITY.c.subject == subject,
            )
        )

    def resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        try:
            return self._resolve_or_provision(token, observed_at)
        except sa.exc.SQLAlchemyError as error:
            raise AuthenticationUnavailable("principal store is unavailable") from error

    def _resolve_or_provision(
        self, token: VerifiedAccessToken, observed_at: datetime
    ) -> Principal:
        with self._session_factory() as session, session.begin():
            row = session.execute(self._select(token.issuer, token.subject)).one_or_none()
            if row is None:
                if not self._auto_provision:
                    raise AccessDenied("principal_not_provisioned")
                identity_lock_key = f"{len(token.issuer)}:{token.issuer}{token.subject}"
                session.execute(
                    sa.text(
                        "SELECT pg_advisory_xact_lock(hashtextextended(:identity_key, 0))"
                    ),
                    {"identity_key": identity_lock_key},
                )
                row = session.execute(
                    self._select(token.issuer, token.subject)
                ).one_or_none()
                if row is None:
                    principal_id = uuid4()
                    session.execute(
                        sa.insert(PRINCIPAL).values(
                            id=principal_id,
                            principal_type=token.principal_type.value,
                            display_name=token.display_name,
                            active=True,
                            created_at=observed_at,
                            updated_at=observed_at,
                        )
                    )
                    session.execute(
                        sa.insert(EXTERNAL_IDENTITY).values(
                            id=uuid4(),
                            principal_id=principal_id,
                            issuer=token.issuer,
                            subject=token.subject,
                            created_at=observed_at,
                            last_seen_at=observed_at,
                        )
                    )
                    row = session.execute(
                        self._select(token.issuer, token.subject)
                    ).one_or_none()
                if row is None:
                    raise AuthenticationFailed("principal_resolution_failed")

            principal = self._principal(row)
            if principal.principal_type is not token.principal_type:
                raise AuthenticationFailed("principal_type_mismatch")
            session.execute(
                sa.update(EXTERNAL_IDENTITY)
                .where(EXTERNAL_IDENTITY.c.id == row.external_identity_id)
                .values(
                    last_seen_at=sa.func.greatest(
                        EXTERNAL_IDENTITY.c.last_seen_at, observed_at
                    )
                )
            )
            if principal.display_name != token.display_name:
                session.execute(
                    sa.update(PRINCIPAL)
                    .where(PRINCIPAL.c.id == principal.id)
                    .values(
                        display_name=token.display_name,
                        updated_at=sa.func.greatest(PRINCIPAL.c.updated_at, observed_at),
                    )
                )
                principal = Principal(
                    id=principal.id,
                    principal_type=principal.principal_type,
                    display_name=token.display_name,
                    active=principal.active,
                )
            return principal
