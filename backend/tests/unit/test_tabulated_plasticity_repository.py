from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import Principal, PrincipalType, SecurityContext
from cmp.modules.modeling.adapters.persistence import (
    tabulated_plasticity_repository as repository_module,
)
from cmp.modules.modeling.adapters.persistence.tabulated_plasticity_repository import (
    SqlAlchemyTabulatedPlasticityRepository,
)
from cmp.modules.modeling.domain.reference_isotropic_tabulated_plasticity import (
    TabulatedPlasticityNotFound,
)
from sqlalchemy.exc import DBAPIError

ORG = UUID(int=1)
PROJECT = UUID(int=2)
ACTOR = UUID(int=3)
OUTPUT = UUID(int=4)
OUTPUT_REVISION = UUID(int=5)
TRACE = "00-00000000000000000000000000000001-0000000000000001-01"


CONTEXT = SecurityContext(
    principal=Principal(ACTOR, PrincipalType.USER, "Repository test", True),
    organization_id=ORG,
    project_id=PROJECT,
    issuer="test",
    subject=str(ACTOR),
    token_id="token",
    groups=(),
    scopes=(),
    request_id=UUID(int=6),
    trace_id=TRACE,
    authenticated_at=datetime(2026, 8, 1, tzinfo=UTC),
)
DECISION = AuthorizationDecision(
    principal_id=ACTOR,
    organization_id=ORG,
    project_id=PROJECT,
    permission=Permission.EXPORT_READ,
    roles=(Role.TEST_ENGINEER,),
    database_permissions=(Permission.EXPORT_READ.value,),
    max_classification=DataClassification.INTERNAL,
    allow_export_controlled=False,
    request_id=CONTEXT.request_id,
    trace_id=TRACE,
    decided_at=CONTEXT.authenticated_at,
)


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows


class _Transaction:
    def __enter__(self) -> _Transaction:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _Session:
    def __init__(self, rows: list[dict[str, Any]], error: DBAPIError | None = None) -> None:
        self.rows = rows
        self.error = error
        self.statement: object | None = None

    def begin(self) -> _Transaction:
        return _Transaction()

    def execute(self, statement: object) -> _Result:
        self.statement = statement
        if self.error is not None:
            raise self.error
        return _Result(self.rows)


class _SessionContext:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __enter__(self) -> _Session:
        return self.session

    def __exit__(self, *_: object) -> None:
        return None


class _Factory:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def __call__(self) -> _SessionContext:
        return _SessionContext(self.session)


class _Rls:
    def __init__(self) -> None:
        self.bound: tuple[object, SecurityContext, AuthorizationDecision] | None = None

    def bind_authorization(
        self, session: object, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        self.bound = (session, context, decision)


def _repository(session: _Session, rls: _Rls) -> SqlAlchemyTabulatedPlasticityRepository:
    return SqlAlchemyTabulatedPlasticityRepository(
        session_factory=cast(Any, _Factory(session)), rls_context=rls
    )


def _row(value: int) -> dict[str, object]:
    return {"id": UUID(int=100 + value), "aggregate_id": UUID(int=200 + value)}


def test_export_revision_query_uses_exact_revision_rows_and_returns_all_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_row(1), _row(2)]
    session = _Session(rows)
    rls = _Rls()
    monkeypatch.setattr(
        repository_module,
        "_record",
        lambda row: SimpleNamespace(
            revision_id=row["id"], aggregate_id=row["aggregate_id"]
        ),
    )
    monkeypatch.setattr(repository_module, "_content", lambda row: SimpleNamespace())

    result = _repository(session, rls).list_processed_model_revisions_for_export(
        context=CONTEXT,
        decision=DECISION,
        processing_output_id=OUTPUT,
        processing_output_revision_id=OUTPUT_REVISION,
    )

    assert [item.material_model_id for item in result] == [UUID(int=201), UUID(int=202)]
    assert [item.revision.record.revision_id for item in result] == [UUID(int=101), UUID(int=102)]
    assert rls.bound == (session, CONTEXT, DECISION)
    statement = cast(Any, session.statement)
    sql = str(statement).lower()
    assert "modeling.material_model_revision" in sql
    assert " join " not in sql
    assert "order by" not in sql
    assert "limit" not in sql
    compiled = statement.compile()
    params = compiled.params
    assert OUTPUT in params.values()
    assert OUTPUT_REVISION in params.values()
    assert ORG in params.values()
    assert PROJECT in params.values()
    assert "processing_output_id" in sql
    assert "processing_output_revision_id" in sql
    assert "model_family_id" in sql


def test_export_revision_query_translates_dbapi_failures_to_typed_not_found() -> None:
    session = _Session([], DBAPIError("SELECT", {}, RuntimeError("database unavailable")))
    with pytest.raises(TabulatedPlasticityNotFound, match="export revisions"):
        _repository(session, _Rls()).list_processed_model_revisions_for_export(
            context=CONTEXT,
            decision=DECISION,
            processing_output_id=OUTPUT,
            processing_output_revision_id=OUTPUT_REVISION,
        )
