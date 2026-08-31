from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from cmp.modules.catalog.adapters.persistence import neutral_material_binding as binding
from cmp.shared.domain.revisions import RevisionCreated, RevisionRecord, TenantScope

ORG = UUID("72000000-0000-4000-8000-000000000001")
PROJECT = UUID("72000000-0000-4000-8000-000000000002")
ACTOR = UUID("72000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 8, 30, tzinfo=UTC)


def _event() -> RevisionCreated:
    return RevisionCreated(
        RevisionRecord(
            revision_id=UUID("72000000-0000-4000-8000-000000000010"),
            aggregate_type="modeling.neutral_material",
            aggregate_id=UUID("72000000-0000-4000-8000-000000000011"),
            scope=TenantScope(ORG, PROJECT, "internal"),
            revision_no=1,
            based_on_revision_id=None,
            schema_id="urn:cmp:test:neutral",
            schema_version="1.0.0",
            content_hash="a" * 64,
            created_at=NOW,
            created_by=ACTOR,
            change_reason="test promotion",
            request_id=UUID("72000000-0000-4000-8000-000000000012"),
            trace_id="00-72000000000000000000000000000072-0000000000000072-01",
        ),
        "draft",
    )


def _card_event(aggregate_type: str) -> RevisionCreated:
    base = _event()
    return replace(
        base,
        revision=replace(
            base.revision,
            aggregate_type=aggregate_type,
            aggregate_id=UUID("72000000-0000-4000-8000-000000000050"),
            revision_id=UUID("72000000-0000-4000-8000-000000000051"),
        ),
    )


def _model_event() -> RevisionCreated:
    base = _event()
    return replace(
        base,
        revision=replace(
            base.revision,
            aggregate_type="modeling.material_model",
            aggregate_id=UUID("72000000-0000-4000-8000-000000000050"),
            revision_id=UUID("72000000-0000-4000-8000-000000000051"),
        ),
    )


class _Result:
    def __init__(self, *, one: object = None, many: list[object] | None = None) -> None:
        self._one = one
        self._many = many or []

    def mappings(self) -> _Result:
        return self

    def one_or_none(self) -> object:
        return self._one

    def all(self) -> list[object]:
        return self._many


class _Session:
    def __init__(self, *results: _Result) -> None:
        self._results = list(results)
        self.writes = 0

    def execute(self, _statement: object) -> _Result:
        if not self._results:
            self.writes += 1
            return _Result()
        return self._results.pop(0)

    def scalar(self, _statement: object) -> object:
        return None


class _OwnerSession:
    def __init__(self, rows: list[dict[str, UUID]], identity_exists: bool = False) -> None:
        self.rows = rows
        self.identity_exists = identity_exists

    def execute(self, _statement: object) -> _Result:
        return _Result(many=self.rows)

    def scalar(self, _statement: object) -> object:
        return self.identity_exists


def _neutral_row(event: RevisionCreated) -> dict[str, UUID]:
    return {
        "id": event.revision.revision_id,
        "aggregate_id": event.revision.aggregate_id,
        "organization_id": ORG,
        "project_id": PROJECT,
        "classification": "internal",
        "material_id": UUID("72000000-0000-4000-8000-000000000020"),
        "material_revision_id": UUID("72000000-0000-4000-8000-000000000021"),
        "material_state_id": UUID("72000000-0000-4000-8000-000000000022"),
        "material_state_revision_id": UUID("72000000-0000-4000-8000-000000000023"),
        "processing_output_id": None,
        "processing_output_revision_id": None,
    }


def _model_row(event: RevisionCreated) -> dict[str, UUID]:
    return {
        "id": event.revision.revision_id,
        "aggregate_id": event.revision.aggregate_id,
        "organization_id": ORG,
        "project_id": PROJECT,
        "classification": "internal",
        "material_id": UUID("72000000-0000-4000-8000-000000000020"),
        "material_revision_id": UUID("72000000-0000-4000-8000-000000000021"),
        "material_state_id": UUID("72000000-0000-4000-8000-000000000022"),
        "material_state_revision_id": UUID("72000000-0000-4000-8000-000000000023"),
        "processing_output_id": None,
        "processing_output_revision_id": None,
        "model_family_id": "urn:cmp:reference:isotropic-tabulated-plasticity:1.2.0",
        "model_schema_digest": "b" * 64,
        "processing_source_document_id": UUID("72000000-0000-4000-8000-000000000024"),
        "processing_source_document_revision_id": UUID("72000000-0000-4000-8000-000000000025"),
    }


def test_material_model_projects_the_exact_peer_model_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _model_event()
    owner = (
        UUID("72000000-0000-4000-8000-000000000060"),
        UUID("72000000-0000-4000-8000-000000000061"),
    )
    current_owners = iter((None, owner))
    monkeypatch.setattr(
        binding,
        "_current_catalog_owner",
        lambda *_args, **_kwargs: next(current_owners),
    )
    session = _Session(
        _Result(one=_model_row(event)),
        _Result(
            many=[
                {
                    "aggregate_id": UUID("72000000-0000-4000-8000-000000000052"),
                    "id": UUID("72000000-0000-4000-8000-000000000053"),
                }
            ]
        ),
    )
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: owner)

    binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 2


def test_material_model_projects_peer_when_schema_digest_is_representation_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct Fit 1.2 representation may inherit a seeded 1.3 owner.

    Exact material/state, model family, source document and current identity
    still gate the peer query; the schema digest alone is not a Catalog-owner
    identity.  This guards the real Export journey without permitting a base
    Material or latest/first fallback.
    """
    event = _model_event()
    model = _model_row(event)
    model["model_schema_digest"] = "c" * 64
    owner = (
        UUID("72000000-0000-4000-8000-000000000060"),
        UUID("72000000-0000-4000-8000-000000000061"),
    )
    current_owners = iter((None, owner))
    monkeypatch.setattr(
        binding,
        "_current_catalog_owner",
        lambda *_args, **_kwargs: next(current_owners),
    )
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: owner)
    session = _Session(
        _Result(one=model),
        _Result(
            many=[
                {
                    "aggregate_id": UUID("72000000-0000-4000-8000-000000000052"),
                    "id": UUID("72000000-0000-4000-8000-000000000053"),
                }
            ]
        ),
    )

    binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 2


def test_unbound_material_model_is_a_valid_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _model_event()
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: None)
    session = _Session(_Result(one=_model_row(event)), _Result(many=[]))

    binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 0


def test_material_model_without_source_lineage_is_not_matched_to_null_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _model_event()
    model = _model_row(event)
    model["processing_source_document_id"] = None
    model["processing_source_document_revision_id"] = None
    monkeypatch.setattr(
        binding,
        "_owner_for_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("NULL-source peer must not be inspected")
        ),
    )
    session = _Session(_Result(one=model))

    binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 0


def test_material_model_owner_conflict_fails_before_catalog_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _model_event()
    expected = (
        UUID("72000000-0000-4000-8000-000000000060"),
        UUID("72000000-0000-4000-8000-000000000061"),
    )
    existing = (
        UUID("72000000-0000-4000-8000-000000000062"),
        expected[1],
    )
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: expected)
    monkeypatch.setattr(binding, "_current_catalog_owner", lambda *_args, **_kwargs: existing)
    session = _Session(
        _Result(one=_model_row(event)),
        _Result(
            many=[
                {
                    "aggregate_id": UUID("72000000-0000-4000-8000-000000000052"),
                    "id": UUID("72000000-0000-4000-8000-000000000053"),
                }
            ]
        ),
    )

    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="conflicting"):
        binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 0


def test_stale_peer_model_owner_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _model_event()
    monkeypatch.setattr(
        binding,
        "_owner_for_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            binding.NeutralMaterialCatalogBindingConflict(
                "exact material Catalog owner is stale or incomplete"
            )
        ),
    )
    session = _Session(
        _Result(one=_model_row(event)),
        _Result(
            many=[
                {
                    "aggregate_id": UUID("72000000-0000-4000-8000-000000000052"),
                    "id": UUID("72000000-0000-4000-8000-000000000053"),
                }
            ]
        ),
    )

    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="stale"):
        binding.catalog_binding_for_material_model(session, event)

    assert session.writes == 0


def test_solver_card_projects_the_exact_model_owner_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _card_event("exporting.solver_card")
    model_id = UUID("72000000-0000-4000-8000-000000000060")
    model_revision_id = UUID("72000000-0000-4000-8000-000000000061")
    owner = (
        UUID("72000000-0000-4000-8000-000000000062"),
        UUID("72000000-0000-4000-8000-000000000063"),
    )
    card_row = {
        "material_model_id": model_id,
        "material_model_revision_id": model_revision_id,
    }
    current_owners = iter((None, owner))
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: owner)
    monkeypatch.setattr(
        binding,
        "_current_catalog_owner",
        lambda *_args, **_kwargs: next(current_owners),
    )
    session = _Session(_Result(one=card_row))

    binding.catalog_binding_for_solver_card(session, event)

    assert session.writes == 2

    monkeypatch.setattr(binding, "_current_catalog_owner", lambda *_args, **_kwargs: owner)
    idempotent_session = _Session(_Result(one=card_row))
    binding.catalog_binding_for_solver_card(idempotent_session, event)
    assert idempotent_session.writes == 0


def test_neutral_solver_card_projects_the_exact_neutral_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _card_event("exporting.neutral_solver_card")
    neutral_id = UUID("72000000-0000-4000-8000-000000000070")
    neutral_revision_id = UUID("72000000-0000-4000-8000-000000000071")
    owner = (
        UUID("72000000-0000-4000-8000-000000000072"),
        UUID("72000000-0000-4000-8000-000000000073"),
    )
    monkeypatch.setattr(binding, "_owner_for_neutral", lambda *_args, **_kwargs: owner)
    current_owners = iter((None, owner))
    monkeypatch.setattr(
        binding,
        "_current_catalog_owner",
        lambda *_args, **_kwargs: next(current_owners),
    )
    session = _Session(
        _Result(
            one={
                "neutral_material_id": neutral_id,
                "neutral_material_revision_id": neutral_revision_id,
            }
        )
    )

    binding.catalog_binding_for_neutral_solver_card(session, event)

    assert session.writes == 2


def test_catalog_owner_resolution_fails_closed_for_partial_and_stale_rows() -> None:
    kwargs = {
        "organization_id": ORG,
        "project_id": PROJECT,
        "classification": "internal",
        "domain_kind": "material_model",
        "domain_object_id": UUID("72000000-0000-4000-8000-000000000080"),
        "domain_revision_id": UUID("72000000-0000-4000-8000-000000000081"),
    }
    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="stale"):
        binding._current_catalog_owner(
            _OwnerSession([], identity_exists=True),
            **kwargs,
        )
    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="stale"):
        binding._current_catalog_owner(
            _OwnerSession(
                [
                    {
                        "record_id": UUID("72000000-0000-4000-8000-000000000082"),
                        "record_revision_id": UUID("72000000-0000-4000-8000-000000000083"),
                        "current_revision_id": UUID("72000000-0000-4000-8000-000000000084"),
                    }
                ]
            ),
            **kwargs,
        )


def test_catalog_owner_resolution_fails_closed_for_conflicting_records() -> None:
    kwargs = {
        "organization_id": ORG,
        "project_id": PROJECT,
        "classification": "internal",
        "domain_kind": "neutral_material",
        "domain_object_id": UUID("72000000-0000-4000-8000-000000000090"),
        "domain_revision_id": UUID("72000000-0000-4000-8000-000000000091"),
    }
    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="conflicting"):
        binding._current_catalog_owner(
            _OwnerSession(
                [
                    {
                        "record_id": UUID("72000000-0000-4000-8000-000000000092"),
                        "record_revision_id": UUID("72000000-0000-4000-8000-000000000093"),
                        "current_revision_id": UUID("72000000-0000-4000-8000-000000000093"),
                    },
                    {
                        "record_id": UUID("72000000-0000-4000-8000-000000000094"),
                        "record_revision_id": UUID("72000000-0000-4000-8000-000000000095"),
                        "current_revision_id": UUID("72000000-0000-4000-8000-000000000095"),
                    },
                ]
            ),
            **kwargs,
        )


def test_unrelated_neutral_promotion_is_a_valid_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _event()
    session = _Session(
        _Result(one=_neutral_row(event)),
        _Result(many=[]),
    )

    binding.catalog_binding_for_neutral_material(session, event)

    assert session.writes == 0


def test_conflicting_exact_model_owners_fail_before_catalog_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _event()
    model_a = {
        "aggregate_id": UUID("72000000-0000-4000-8000-000000000030"),
        "id": UUID("72000000-0000-4000-8000-000000000031"),
    }
    model_b = {
        "aggregate_id": UUID("72000000-0000-4000-8000-000000000032"),
        "id": UUID("72000000-0000-4000-8000-000000000033"),
    }
    record_a = UUID("72000000-0000-4000-8000-000000000040")
    record_b = UUID("72000000-0000-4000-8000-000000000041")
    session = _Session(_Result(one=_neutral_row(event)), _Result(many=[model_a, model_b]))
    monkeypatch.setattr(
        binding,
        "_owner_for_model",
        lambda *_args, **kwargs: (
            record_a,
            UUID("72000000-0000-4000-8000-000000000042"),
        )
        if kwargs["model_id"] == model_a["aggregate_id"]
        else (record_b, UUID("72000000-0000-4000-8000-000000000043")),
    )

    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="conflicting"):
        binding.catalog_binding_for_neutral_material(session, event)

    assert session.writes == 0


def test_existing_neutral_owner_conflict_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _event()
    model = {
        "aggregate_id": UUID("72000000-0000-4000-8000-000000000030"),
        "id": UUID("72000000-0000-4000-8000-000000000031"),
    }
    expected = (
        UUID("72000000-0000-4000-8000-000000000040"),
        UUID("72000000-0000-4000-8000-000000000042"),
    )
    session = _Session(_Result(one=_neutral_row(event)), _Result(many=[model]))
    monkeypatch.setattr(binding, "_owner_for_model", lambda *_args, **_kwargs: expected)
    monkeypatch.setattr(
        binding,
        "_owner_for_neutral",
        lambda *_args, **_kwargs: (
            UUID("72000000-0000-4000-8000-000000000041"),
            expected[1],
        ),
    )

    with pytest.raises(binding.NeutralMaterialCatalogBindingConflict, match="conflicting"):
        binding.catalog_binding_for_neutral_material(session, event)

    assert session.writes == 0
