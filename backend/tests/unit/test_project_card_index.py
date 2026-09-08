from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from cmp.modules.exporting.application.project_card_index import (
    CARD_FAMILY_NEUTRAL_SOLVER,
    CARD_FAMILY_UNSUPPORTED,
    ProjectCardIndexRow,
    ProjectCardIndexService,
)
from cmp.modules.identity_access.domain.authorization import (
    AuthorizationDecision,
    DataClassification,
    Permission,
    Role,
)
from cmp.modules.identity_access.domain.security import (
    Principal,
    PrincipalType,
    SecurityContext,
)
from sqlalchemy.dialects import postgresql


class Repository:
    def __init__(self, rows: tuple[ProjectCardIndexRow, ...]) -> None:
        self.rows = rows

    def list_current_cards(
        self, *, context: SecurityContext, decision: AuthorizationDecision
    ) -> tuple[ProjectCardIndexRow, ...]:
        assert context.project_id == decision.project_id
        return self.rows


def _scope(
    *,
    permission: Permission = Permission.EXPORT_READ,
    database_permissions: tuple[str, ...] = (Permission.EXPORT_READ.value,),
) -> tuple[SecurityContext, AuthorizationDecision]:
    principal_id = uuid4()
    organization_id = uuid4()
    project_id = uuid4()
    request_id = uuid4()
    now = datetime.now(UTC)
    context = SecurityContext(
        principal=Principal(principal_id, PrincipalType.USER, "Reader", True),
        organization_id=organization_id,
        project_id=project_id,
        issuer="cmp.test",
        subject="reader",
        token_id="token-1",
        groups=(),
        scopes=("export.read",),
        request_id=request_id,
        trace_id="trace-1",
        authenticated_at=now,
    )
    decision = AuthorizationDecision(
        principal_id=principal_id,
        organization_id=organization_id,
        project_id=project_id,
        permission=permission,
        roles=(Role.CONSUMER,),
        database_permissions=database_permissions,
        max_classification=DataClassification.INTERNAL,
        allow_export_controlled=False,
        request_id=request_id,
        trace_id="trace-1",
        decided_at=now,
    )
    return context, decision


def _row(
    *,
    schema_id: str,
    model_family: str | None = None,
    title: str = "Card",
    material_id: UUID | None = None,
    material_model_id: UUID | None = None,
    material_model_revision_id: UUID | None = None,
) -> ProjectCardIndexRow:
    return ProjectCardIndexRow(
        solver_card_id=uuid4(),
        revision_id=uuid4(),
        revision_no=1,
        schema_id=schema_id,
        content_hash="a" * 64,
        title=title,
        material_model_id=material_model_id,
        material_model_revision_id=material_model_revision_id,
        neutral_material_id=uuid4() if model_family else None,
        material_id=material_id,
        target_solver="openradioss",
        target_version="2025",
        target_unit_system="kg_m_s",
        solver_material_id=1200,
        card_sha256="b" * 64,
        exporter_id="cmp.test.exporter",
        model_family=model_family,
        family=model_family,
        created_at=datetime.now(UTC),
    )


def test_index_returns_complete_scope_and_classifies_generalized_maxwell() -> None:
    context, decision = _scope()
    rows = tuple(
        _row(
            schema_id="urn:cmp:exporting:neutral-family-card:2.0.0",
            model_family="generalized_maxwell",
            title=f"Card {index:02d}",
        )
        for index in range(13)
    )
    service = ProjectCardIndexService(repository=Repository(rows))

    page = service.list(context, decision, query="openradioss")

    assert page.total_count == 13
    assert len(page.items) == 13
    assert page.page_size == 12
    assert {item.card_family for item in page.items} == {CARD_FAMILY_NEUTRAL_SOLVER}


def test_index_keeps_unknown_schema_visible_and_rejects_mismatched_scope() -> None:
    context, decision = _scope()
    unknown = _row(schema_id="urn:cmp:exporting:future-card:9.0.0")
    service = ProjectCardIndexService(repository=Repository((unknown,)))

    page = service.list(context, decision)

    assert page.items[0].card_family == CARD_FAMILY_UNSUPPORTED
    assert page.items[0].unsupported_reason is not None
    with pytest.raises(ValueError, match="authorization decision"):
        service.list(
            context,
            AuthorizationDecision(
                principal_id=decision.principal_id,
                organization_id=decision.organization_id,
                project_id=decision.project_id,
                permission=Permission.EXPORT_READ,
                roles=decision.roles,
                database_permissions=decision.database_permissions,
                max_classification=decision.max_classification,
                allow_export_controlled=decision.allow_export_controlled,
                request_id=uuid4(),
                trace_id=decision.trace_id,
                decided_at=decision.decided_at,
            ),
        )


@pytest.mark.parametrize(
    ("permission", "database_permissions", "allowed"),
    [
        (Permission.EXPORT_READ, (Permission.EXPORT_READ.value,), True),
        (
            Permission.EXPORT_READ,
            (Permission.DATASET_READ.value, Permission.EXPORT_READ.value),
            True,
        ),
        (Permission.DATASET_READ, (Permission.DATASET_READ.value,), False),
        (Permission.CATALOG_READ, (Permission.CATALOG_READ.value,), False),
    ],
)
def test_index_permission_matrix_requires_export_read(
    permission: Permission,
    database_permissions: tuple[str, ...],
    allowed: bool,
) -> None:
    context, decision = _scope(permission=permission, database_permissions=database_permissions)
    service = ProjectCardIndexService(
        repository=Repository(
            (_row(schema_id="urn:cmp:exporting:reference-openradioss-elast:1.0.0"),)
        )
    )
    if allowed:
        assert service.list(context, decision).total_count == 1
    else:
        with pytest.raises(ValueError, match="authorization decision"):
            service.list(context, decision)


def test_material_membership_filter_does_not_infer_model_generation() -> None:
    context, decision = _scope()
    material_id = uuid4()
    model_id = uuid4()
    rows = (
        _row(
            schema_id="urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0",
            title="Primary generated card",
            material_id=material_id,
            material_model_id=model_id,
            material_model_revision_id=uuid4(),
        ),
        _row(
            schema_id="urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0",
            title="Same material, different generation",
            material_id=material_id,
            material_model_id=uuid4(),
            material_model_revision_id=uuid4(),
        ),
        _row(
            schema_id="urn:cmp:exporting:reference-isotropic-tabulated-plasticity-card:1.0.0",
            title="Different material",
            material_id=uuid4(),
            material_model_id=model_id,
            material_model_revision_id=uuid4(),
        ),
    )
    service = ProjectCardIndexService(repository=Repository(rows))

    page = service.list(context, decision, material_id=material_id)

    assert {item.title for item in page.items} == {
        "Primary generated card",
        "Same material, different generation",
    }
    assert all(
        item.material_model_id != model_id
        for item in page.items
        if item.title == "Same material, different generation"
    )


class _Result:
    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, object]]:
        return []


class _Session:
    def __init__(self) -> None:
        self.statements: list[sa.Select[tuple[object, ...]]] = []

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def begin(self) -> _Session:
        return self

    def execute(self, statement: sa.Select[tuple[object, ...]]) -> _Result:
        self.statements.append(statement)
        return _Result()


class _Rls:
    def __init__(self) -> None:
        self.calls = 0

    def bind_authorization(
        self, session: _Session, context: SecurityContext, decision: AuthorizationDecision
    ) -> None:
        assert context.organization_id == decision.organization_id
        assert context.project_id == decision.project_id
        self.calls += 1


def test_sql_repository_constructs_both_scope_bound_queries_and_binds_rls() -> None:
    from cmp.modules.exporting.adapters.persistence.project_card_index import (
        SqlAlchemyProjectCardIndexRepository,
    )

    context, decision = _scope()
    session = _Session()
    rls = _Rls()
    repository = SqlAlchemyProjectCardIndexRepository(
        session_factory=lambda: session,  # type: ignore[arg-type]
        rls_context=rls,  # type: ignore[arg-type]
    )
    assert repository.list_current_cards(context=context, decision=decision) == ()
    assert len(session.statements) == 2
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    compiled = " ".join(str(statement.compile(dialect=dialect)) for statement in session.statements)
    assert "organization_id" in compiled
    assert "project_id" in compiled
    assert rls.calls == 1


@pytest.mark.parametrize(
    ("schema_id", "model_family", "expected_family"),
    [
        ("urn:cmp:exporting:neutral-family-card:2.0.0", "generalized_maxwell", "neutral_solver"),
        (
            "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0",
            "hyperelastic",
            "neutral_hyperelastic",
        ),
    ],
)
def test_neutral_index_links_use_installed_router(
    schema_id: str, model_family: str, expected_family: str
) -> None:
    from cmp.modules.exporting.adapters.api.project_card_index import (
        ProjectCardIndexItemResponse,
    )

    row = _row(schema_id=schema_id, model_family=model_family)
    assert row.card_family == expected_family
    response = ProjectCardIndexItemResponse.from_row(row)
    base = f"/api/v1/neutral-solver-cards/{row.solver_card_id}"
    pin = f"?revision_id={row.revision_id}"
    assert response.links == {
        "self": base + pin,
        "preview": base + "/preview" + pin,
        "download": base + "/download" + pin,
    }
