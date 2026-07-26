from __future__ import annotations

import sys
from collections.abc import Mapping
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = spec_from_file_location("seed_full_demo", _SCRIPTS / "seed_full_demo.py")
assert _SPEC is not None and _SPEC.loader is not None
_SEED_FULL_DEMO = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SEED_FULL_DEMO)
_ensure_governed_test_data_revision = _SEED_FULL_DEMO._ensure_governed_test_data_revision
_governed_sources_for_tensile_documents = (
    _SEED_FULL_DEMO._governed_sources_for_tensile_documents
)
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


def test_legacy_demo_test_data_advances_to_proof_bearing_revision_without_mutating_history(
) -> None:
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
    sources = _governed_sources_for_tensile_documents(
        material=_resource("material_id", "material-1", "material-r1", {}),
        material_state=_resource("material_state_id", "state-1", "state-r1", {}),
        test_runs=(
            _resource(
                "test_run_id", "run-1", "run-r1", {"run_label": "CMP demo tensile replicate 1"}
            ),
            _resource(
                "test_run_id", "run-2", "run-r2", {"run_label": "CMP demo tensile replicate 2"}
            ),
            _resource(
                "test_run_id", "run-3", "run-r3", {"run_label": "CMP demo tensile replicate 3"}
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
    assert {source["material_state"]["revision_id"] for source in sources.values()} == {
        "state-r1"
    }


def test_tensile_demo_governed_source_fails_closed_for_ambiguous_run_label() -> None:
    run = _resource("test_run_id", "run-1", "run-r1", {"run_label": "CMP demo tensile replicate 1"})

    with pytest.raises(DemoSeedError, match="exactly one Test Run"):
        _governed_sources_for_tensile_documents(
            material=_resource("material_id", "material-1", "material-r1", {}),
            material_state=_resource("material_state_id", "state-1", "state-r1", {}),
            test_runs=(run, run),
        )
