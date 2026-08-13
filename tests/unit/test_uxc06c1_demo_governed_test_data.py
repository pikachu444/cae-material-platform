from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, cast

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = spec_from_file_location("seed_full_demo", _SCRIPTS / "seed_full_demo.py")
assert _SPEC is not None and _SPEC.loader is not None
_SEED_FULL_DEMO = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SEED_FULL_DEMO)
_ensure_governed_test_data_revision = _SEED_FULL_DEMO._ensure_governed_test_data_revision
_governed_sources_for_tensile_documents = _SEED_FULL_DEMO._governed_sources_for_tensile_documents
_canonical_recipe_content = _SEED_FULL_DEMO._canonical_recipe_content
_ensure_canonical_recipe = _SEED_FULL_DEMO._ensure_canonical_recipe
_ensure_canonical_batch = _SEED_FULL_DEMO._ensure_canonical_batch
_CANONICAL_BATCH_LABEL = _SEED_FULL_DEMO._CANONICAL_BATCH_LABEL
_BATCH_POLL_ATTEMPTS = _SEED_FULL_DEMO._BATCH_POLL_ATTEMPTS
DemoSeedError = _SEED_FULL_DEMO.DemoSeedError


class _LegacyDemoApi:
    def __init__(self) -> None:
        self.history = {
            "test_data_document_id": "document-1",
            "current_revision": {
                "id": "revision-1",
                "revision_no": 1,
                "content_hash": "a" * 64,
            },
            "governed_source": None,
        }
        self.document = {"document_id": "CMP-DEMO-DP780-TEST-JSON", "channels": []}
        self.writes: list[dict[str, Any]] = []

    def get(self, path: str) -> dict[str, Any]:
        assert path == "/test-data-documents/document-1/revisions/revision-1/content"
        return deepcopy(self.document)

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        assert path == "/test-data-documents/document-1/revisions"
        assert headers == {"If-Match": '"revision:1:sha256:' + "a" * 64 + '"'}
        self.writes.append(dict(payload))
        return {
            "test_data_document_id": "document-1",
            "current_revision": {
                "id": "revision-2",
                "revision_no": 2,
                "content_hash": "b" * 64,
            },
            "governed_source": payload["governed_source"],
        }


def test_legacy_demo_test_data_advances_to_proof_bearing_revision_without_mutating_history() -> (
    None
):
    api = _LegacyDemoApi()
    governed_source = {
        "material": {"aggregate_id": "material-1", "revision_id": "material-r1"},
        "material_state": {"aggregate_id": "state-1", "revision_id": "state-r1"},
        "test_run": {"aggregate_id": "run-1", "revision_id": "run-r1"},
    }

    current = _ensure_governed_test_data_revision(api, api.history, governed_source)

    assert api.history["governed_source"] is None
    assert api.writes[0]["document"] == api.document
    assert current["current_revision"]["id"] == "revision-2"
    assert current["governed_source"] == governed_source
    assert _ensure_governed_test_data_revision(api, current, governed_source) == current
    response_with_optional_null = deepcopy(current)
    response_with_optional_null["governed_source"] = {
        **governed_source,
        "tabular_import": None,
    }
    assert (
        _ensure_governed_test_data_revision(
            api,
            response_with_optional_null,
            governed_source,
        )
        == response_with_optional_null
    )
    assert len(api.writes) == 1


def _resource(
    stable_key: str, stable_id: str, revision_id: str, content: Mapping[str, object]
) -> dict[str, Any]:
    return {
        stable_key: stable_id,
        "current_revision": {
            "id": revision_id,
            "revision_no": 1,
            "content_hash": "a" * 64,
            "content": dict(content),
        },
    }


def test_tensile_demo_documents_pin_their_matching_distinct_test_runs() -> None:
    specimens = tuple(
        _resource(
            "specimen_id",
            f"specimen-{index}",
            f"specimen-r1-{index}",
            {
                "material_id": "material-1",
                "material_revision_id": "material-r1",
                "material_state_id": "state-1",
                "material_state_revision_id": "state-r1",
                "specimen_code": f"CMP-DEMO-DP780-T-00{index}",
            },
        )
        for index in (1, 2, 3)
    )
    sources = _governed_sources_for_tensile_documents(
        material=_resource("material_id", "material-1", "material-r2", {}),
        material_state=_resource("material_state_id", "state-1", "state-r2", {}),
        specimens=specimens,
        test_runs=(
            _resource(
                "test_run_id",
                "run-1",
                "run-r1",
                {
                    "run_label": "CMP demo tensile replicate 1",
                    "specimen_id": "specimen-1",
                    "specimen_revision_id": "specimen-r1-1",
                },
            ),
            _resource(
                "test_run_id",
                "run-2",
                "run-r2",
                {
                    "run_label": "CMP demo tensile replicate 2",
                    "specimen_id": "specimen-2",
                    "specimen_revision_id": "specimen-r1-2",
                },
            ),
            _resource(
                "test_run_id",
                "run-3",
                "run-r3",
                {
                    "run_label": "CMP demo tensile replicate 3",
                    "specimen_id": "specimen-3",
                    "specimen_revision_id": "specimen-r1-3",
                },
            ),
        ),
    )

    assert [
        sources[key]["test_run"]
        for key in (
            "CMP-DEMO-DP780-TEST-JSON",
            "CMP-DEMO-DP780-TEST-JSON-02",
            "CMP-DEMO-DP780-TEST-JSON-03",
        )
    ] == [
        {"aggregate_id": "run-1", "revision_id": "run-r1"},
        {"aggregate_id": "run-2", "revision_id": "run-r2"},
        {"aggregate_id": "run-3", "revision_id": "run-r3"},
    ]
    assert {source["material"]["revision_id"] for source in sources.values()} == {"material-r1"}
    assert {source["material_state"]["revision_id"] for source in sources.values()} == {"state-r1"}


def test_tensile_demo_governed_source_fails_closed_for_ambiguous_run_label() -> None:
    run = _resource(
        "test_run_id",
        "run-1",
        "run-r1",
        {
            "run_label": "CMP demo tensile replicate 1",
            "specimen_id": "specimen-1",
            "specimen_revision_id": "specimen-r1",
        },
    )

    with pytest.raises(DemoSeedError, match="exactly one Test Run"):
        _governed_sources_for_tensile_documents(
            material=_resource("material_id", "material-1", "material-r1", {}),
            material_state=_resource("material_state_id", "state-1", "state-r1", {}),
            specimens=(),
            test_runs=(run, run),
        )


def test_tensile_demo_governed_source_fails_closed_for_missing_specimen_pin() -> None:
    run = _resource(
        "test_run_id",
        "run-1",
        "run-r1",
        {
            "run_label": "CMP demo tensile replicate 1",
            "specimen_id": "specimen-1",
            "specimen_revision_id": "specimen-r1",
        },
    )

    with pytest.raises(DemoSeedError, match="exactly one Specimen"):
        _governed_sources_for_tensile_documents(
            material=_resource("material_id", "material-1", "material-r1", {}),
            material_state=_resource("material_state_id", "state-1", "state-r1", {}),
            specimens=(),
            test_runs=(run,),
        )


def test_tensile_demo_governed_source_fails_closed_for_ambiguous_specimen_pin() -> None:
    run = _resource(
        "test_run_id",
        "run-1",
        "run-r1",
        {
            "run_label": "CMP demo tensile replicate 1",
            "specimen_id": "specimen-1",
            "specimen_revision_id": "specimen-r1",
        },
    )
    specimen = _resource(
        "specimen_id",
        "specimen-1",
        "specimen-r1",
        {
            "material_id": "material-1",
            "material_revision_id": "material-r1",
            "material_state_id": "state-1",
            "material_state_revision_id": "state-r1",
        },
    )

    with pytest.raises(DemoSeedError, match="exactly one Specimen"):
        _governed_sources_for_tensile_documents(
            material=_resource("material_id", "material-1", "material-r1", {}),
            material_state=_resource("material_state_id", "state-1", "state-r1", {}),
            specimens=(specimen, specimen),
            test_runs=(run,),
        )


def test_tensile_demo_governed_source_fails_closed_for_mismatched_specimen_owner() -> None:
    run = _resource(
        "test_run_id",
        "run-1",
        "run-r1",
        {
            "run_label": "CMP demo tensile replicate 1",
            "specimen_id": "specimen-1",
            "specimen_revision_id": "specimen-r1",
        },
    )
    specimen = _resource(
        "specimen_id",
        "specimen-1",
        "specimen-r1",
        {
            "material_id": "other-material",
            "material_revision_id": "material-r1",
            "material_state_id": "state-1",
            "material_state_revision_id": "state-r1",
        },
    )

    with pytest.raises(DemoSeedError, match="does not match"):
        _governed_sources_for_tensile_documents(
            material=_resource("material_id", "material-1", "material-r1", {}),
            material_state=_resource("material_state_id", "state-1", "state-r1", {}),
            specimens=(specimen,),
            test_runs=(run,),
        )


_PROFILE = {
    "mapping_profile_id": "profile-1",
    "current_revision": {
        "id": "profile-r1",
        "revision_no": 1,
        "content_hash": "p" * 64,
    },
}


def _recipe(content: Mapping[str, Any], *, revision_no: int = 1) -> dict[str, Any]:
    return {
        "processing_recipe_id": "recipe-1",
        "content": deepcopy(dict(content)),
        "current_revision": {
            "id": f"recipe-r{revision_no}",
            "revision_no": revision_no,
            "content_hash": chr(96 + revision_no) * 64,
        },
    }


class _RecipeApi:
    def __init__(self, recipe: Mapping[str, Any] | None = None) -> None:
        self.recipe = deepcopy(dict(recipe)) if recipe is not None else None
        self.writes: list[dict[str, Any]] = []

    def get(self, path: str) -> dict[str, Any]:
        assert path == "/common-processing-recipes"
        return {"items": [deepcopy(self.recipe)] if self.recipe is not None else []}

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        self.writes.append({"path": path, "payload": deepcopy(dict(payload)), "headers": headers})
        if path == "/common-processing-recipes":
            self.recipe = _recipe(payload["content"])
            return deepcopy(self.recipe)
        assert path == "/common-processing-recipes/recipe-1/revisions"
        assert self.recipe is not None
        revision_no = int(self.recipe["current_revision"]["revision_no"]) + 1
        self.recipe = _recipe(payload["content"], revision_no=revision_no)
        return deepcopy(self.recipe)


def test_canonical_recipe_absent_uses_draft_then_published_flow() -> None:
    api = _RecipeApi()

    result = _ensure_canonical_recipe(api, profile=_PROFILE)

    assert result["content"]["lifecycle_state"] == "published"
    assert [write["path"] for write in api.writes] == [
        "/common-processing-recipes",
        "/common-processing-recipes/recipe-1/revisions",
    ]
    assert api.writes[1]["headers"] == {"If-Match": '"revision:1:sha256:' + "a" * 64 + '"'}


def test_canonical_recipe_legacy_published_appends_one_draft_then_publishes_with_etags() -> None:
    desired = _canonical_recipe_content(
        profile_id="profile-1", profile_revision_id="profile-r1", profile_hash="p" * 64
    )
    legacy = deepcopy(desired)
    legacy["lifecycle_state"] = "published"
    legacy["steps"][-1]["options"]["equation_contract"] = "legacy-contract"
    api = _RecipeApi(_recipe(legacy))

    result = _ensure_canonical_recipe(api, profile=_PROFILE)

    assert result["content"]["lifecycle_state"] == "published"
    assert len(api.writes) == 2
    assert "legacy outputs are not replayed" in api.writes[0]["payload"]["change_reason"]
    assert api.writes[0]["headers"] == {"If-Match": '"revision:1:sha256:' + "a" * 64 + '"'}
    assert api.writes[1]["headers"] == {"If-Match": '"revision:2:sha256:' + "b" * 64 + '"'}
    assert api.writes[0]["payload"]["content"]["steps"][-1]["options"]["equation_contract"] == (
        "altair-material-modeler-2025-v1"
    )
    assert api.writes[0]["payload"]["change_reason"] != api.writes[1]["payload"]["change_reason"]


def test_canonical_recipe_exact_draft_publishes_without_extra_draft() -> None:
    desired = _canonical_recipe_content(
        profile_id="profile-1", profile_revision_id="profile-r1", profile_hash="p" * 64
    )
    api = _RecipeApi(_recipe(desired))

    result = _ensure_canonical_recipe(api, profile=_PROFILE)

    assert result["content"]["lifecycle_state"] == "published"
    assert len(api.writes) == 1
    assert api.writes[0]["payload"]["content"]["lifecycle_state"] == "published"


def test_canonical_recipe_exact_published_is_idempotently_reused() -> None:
    desired = _canonical_recipe_content(
        profile_id="profile-1", profile_revision_id="profile-r1", profile_hash="p" * 64
    )
    desired["lifecycle_state"] = "published"
    api = _RecipeApi(_recipe(desired))

    result = _ensure_canonical_recipe(api, profile=_PROFILE)

    assert result["current_revision"]["id"] == "recipe-r1"
    assert api.writes == []


def test_canonical_recipe_mismatched_draft_fails_closed() -> None:
    desired = _canonical_recipe_content(
        profile_id="profile-1", profile_revision_id="profile-r1", profile_hash="p" * 64
    )
    desired["steps"][-1]["options"]["families"] = ["voce"]
    api = _RecipeApi(_recipe(desired))

    with pytest.raises(DemoSeedError, match="mismatched draft"):
        _ensure_canonical_recipe(api, profile=_PROFILE)
    assert api.writes == []


def _batch(*, status: str, batch_id: str = "batch-1") -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "label": _CANONICAL_BATCH_LABEL,
        "recipe_id": "recipe-1",
        "recipe_revision_id": "recipe-r2",
        "recipe_sha256": "r" * 64,
        "status": status,
        "attempts": [
            {
                "attempt_id": "attempt-1",
                "status": "succeeded" if status == "succeeded" else "failed",
                "output_id": "output-1" if status == "succeeded" else None,
                "output_revision_id": "output-r1" if status == "succeeded" else None,
            }
        ],
    }


class _BatchApi:
    def __init__(
        self,
        listed: Sequence[Mapping[str, Any]],
        *,
        details: Sequence[Mapping[str, Any]] = (),
        created: Mapping[str, Any] | None = None,
        retried: Mapping[str, Any] | None = None,
    ) -> None:
        self.listed = [deepcopy(dict(item)) for item in listed]
        self.details = [deepcopy(dict(item)) for item in details]
        self.created = (
            deepcopy(dict(created)) if created is not None else _batch(status="succeeded")
        )
        self.retried = (
            deepcopy(dict(retried)) if retried is not None else _batch(status="succeeded")
        )
        self.writes: list[dict[str, Any]] = []
        self.get_paths: list[str] = []

    def get(self, path: str) -> dict[str, Any]:
        self.get_paths.append(path)
        if path == "/common-processing-batches":
            return {"items": deepcopy(self.listed)}
        assert path.startswith("/common-processing-batches/")
        return self.details.pop(0) if self.details else deepcopy(self.listed[0])

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        self.writes.append({"path": path, "payload": deepcopy(dict(payload)), "headers": headers})
        if path == "/common-processing-batches:preflight":
            return {"compatible": True}
        if path == "/common-processing-batches":
            return deepcopy(self.created)
        assert path.endswith(":retry-failed")
        return deepcopy(self.retried)


def _ensure_batch(api: _BatchApi) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _ensure_canonical_batch(
            api,
            recipe_id="recipe-1",
            recipe_revision_id="recipe-r2",
            recipe_hash="r" * 64,
            source={"document_id": "document-1", "revision_id": "document-r1"},
        ),
    )


def test_canonical_batch_zero_selection_preflights_and_creates_literal_contract_batch() -> None:
    api = _BatchApi([])

    result = _ensure_batch(api)

    assert result["status"] == "succeeded"
    assert [write["path"] for write in api.writes] == [
        "/common-processing-batches:preflight",
        "/common-processing-batches",
    ]
    assert api.writes[1]["payload"]["label"] == _CANONICAL_BATCH_LABEL


def test_canonical_batch_succeeded_selection_is_reused_without_writes() -> None:
    api = _BatchApi([_batch(status="succeeded")])

    assert _ensure_batch(api)["batch_id"] == "batch-1"
    assert api.writes == []


def test_canonical_batch_failed_selection_retries_once_and_requires_success() -> None:
    api = _BatchApi([_batch(status="failed")], retried=_batch(status="succeeded"))

    assert _ensure_batch(api)["status"] == "succeeded"
    assert [write["path"] for write in api.writes] == [
        "/common-processing-batches/batch-1:retry-failed"
    ]


def test_canonical_batch_running_selection_polls_to_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_SEED_FULL_DEMO, "_BATCH_POLL_DELAY_SECONDS", 0)
    api = _BatchApi(
        [_batch(status="running")],
        details=[_batch(status="running"), _batch(status="succeeded")],
    )

    assert _ensure_batch(api)["status"] == "succeeded"
    assert api.get_paths == [
        "/common-processing-batches",
        "/common-processing-batches/batch-1",
        "/common-processing-batches/batch-1",
    ]


def test_canonical_batch_nonterminal_polling_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_SEED_FULL_DEMO, "_BATCH_POLL_DELAY_SECONDS", 0)
    monkeypatch.setattr(_SEED_FULL_DEMO, "_BATCH_POLL_ATTEMPTS", 2)
    api = _BatchApi([_batch(status="running")], details=[_batch(status="running")])

    with pytest.raises(DemoSeedError, match="bounded polling"):
        _ensure_batch(api)
    assert api.writes == []


def test_canonical_batch_ambiguity_fails_closed_without_touching_candidates() -> None:
    api = _BatchApi([_batch(status="succeeded"), _batch(status="succeeded", batch_id="batch-2")])

    with pytest.raises(DemoSeedError, match="multiple canonical JSON batches"):
        _ensure_batch(api)
    assert api.writes == []
