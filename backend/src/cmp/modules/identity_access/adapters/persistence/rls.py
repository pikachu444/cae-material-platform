"""Bind trusted T-03/T-04 context to transaction-local PostgreSQL settings."""

from __future__ import annotations

import json

import sqlalchemy as sa
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
)
from cmp.modules.identity_access.domain.security import SecurityContext
from sqlalchemy.orm import Session

_CLASSIFICATION_RANK = {
    DataClassification.INTERNAL: 0,
    DataClassification.CONFIDENTIAL: 1,
    DataClassification.RESTRICTED: 2,
}


class RlsContextMismatch(ValueError):
    """One transaction attempted to replace its authenticated or authorized scope."""


def _json_strings(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


class SqlAlchemyRlsContext:
    """Apply only validated context with PostgreSQL ``is_local=true`` semantics."""

    @staticmethod
    def assert_application_role(session: Session) -> None:
        session.execute(sa.text("SELECT access_control.assert_application_role()"))

    @staticmethod
    def _existing(session: Session) -> dict[str, str | None]:
        return dict(
            session.execute(
                sa.text(
                    "SELECT "
                    "current_setting('cmp.organization_id', true) AS organization_id, "
                    "current_setting('cmp.project_id', true) AS project_id, "
                    "current_setting('cmp.principal_id', true) AS principal_id, "
                    "current_setting('cmp.principal_type', true) AS principal_type, "
                    "current_setting('cmp.issuer', true) AS issuer, "
                    "current_setting('cmp.subject', true) AS subject, "
                    "current_setting('cmp.token_id', true) AS token_id, "
                    "current_setting('cmp.groups', true) AS groups, "
                    "current_setting('cmp.scopes', true) AS scopes, "
                    "current_setting('cmp.request_id', true) AS request_id, "
                    "current_setting('cmp.trace_id', true) AS trace_id"
                )
            ).mappings().one()
        )

    @staticmethod
    def _assert_not_rebound(
        existing: dict[str, str | None], desired: dict[str, str]
    ) -> None:
        for name, value in desired.items():
            current = existing.get(name)
            if current not in {None, ""} and current != value:
                raise RlsContextMismatch(
                    f"transaction-local {name} cannot be rebound to another context"
                )

    def bind_authentication(self, session: Session, context: SecurityContext) -> None:
        self.assert_application_role(session)
        desired = {
            "organization_id": str(context.organization_id),
            "project_id": str(context.project_id),
            "principal_id": str(context.principal.id),
            "principal_type": context.principal.principal_type.value,
            "issuer": context.issuer,
            "subject": context.subject,
            "token_id": context.token_id,
            "groups": _json_strings(context.groups),
            "scopes": _json_strings(context.scopes),
            "request_id": str(context.request_id),
            "trace_id": context.trace_id,
        }
        self._assert_not_rebound(self._existing(session), desired)
        session.execute(
            sa.select(
                sa.func.set_config(
                    "cmp.organization_id", desired["organization_id"], True
                ),
                sa.func.set_config("cmp.project_id", desired["project_id"], True),
                sa.func.set_config("cmp.principal_id", desired["principal_id"], True),
                sa.func.set_config(
                    "cmp.principal_type", desired["principal_type"], True
                ),
                sa.func.set_config("cmp.issuer", desired["issuer"], True),
                sa.func.set_config("cmp.subject", desired["subject"], True),
                sa.func.set_config("cmp.token_id", desired["token_id"], True),
                sa.func.set_config("cmp.groups", desired["groups"], True),
                sa.func.set_config("cmp.scopes", desired["scopes"], True),
                sa.func.set_config("cmp.permissions", "[]", True),
                sa.func.set_config("cmp.roles", "[]", True),
                sa.func.set_config("cmp.max_classification_rank", "-1", True),
                sa.func.set_config("cmp.allow_export_controlled", "false", True),
                sa.func.set_config("cmp.request_id", desired["request_id"], True),
                sa.func.set_config("cmp.trace_id", desired["trace_id"], True),
            )
        )

    def bind_authorization(
        self,
        session: Session,
        context: SecurityContext,
        decision: AuthorizationDecision,
    ) -> None:
        if (
            decision.principal_id != context.principal.id
            or decision.organization_id != context.organization_id
            or decision.project_id != context.project_id
            or decision.request_id != context.request_id
            or decision.trace_id != context.trace_id
        ):
            raise RlsContextMismatch(
                "authorization decision does not belong to the authenticated request"
            )
        self.bind_authentication(session, context)
        rank = _CLASSIFICATION_RANK[decision.max_classification]
        session.execute(
            sa.select(
                sa.func.set_config(
                    "cmp.permissions",
                    _json_strings(decision.database_permissions),
                    True,
                ),
                sa.func.set_config(
                    "cmp.roles",
                    _json_strings(tuple(role.value for role in decision.roles)),
                    True,
                ),
                sa.func.set_config("cmp.max_classification_rank", str(rank), True),
                sa.func.set_config(
                    "cmp.allow_export_controlled",
                    "true" if decision.allow_export_controlled else "false",
                    True,
                ),
            )
        )
