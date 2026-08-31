from __future__ import annotations

import sys
from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest
from pytest import MonkeyPatch

ROOT = Path(__file__).parents[2]
_SPEC = spec_from_file_location(
    "seed_disposable_scale_fixture",
    ROOT / "scripts" / "seed_disposable_scale_fixture.py",
)
assert _SPEC and _SPEC.loader
scale_fixture = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = scale_fixture
_SPEC.loader.exec_module(scale_fixture)


def _attribute(key: str, *, discrete: bool = False) -> dict[str, Any]:
    return {
        "attribute_definition_id": f"{key}-id",
        "current_revision": {
            "id": f"{key}-revision",
            "content": {"key": key, "data_type": "discrete" if discrete else "text"},
        },
    }


def _attributes() -> dict[str, dict[str, Any]]:
    return {
        "material_information__family": _attribute(
            "material_information__family", discrete=True
        ),
        "material_information__category": _attribute("material_information__category"),
        "material_information__grade": _attribute("material_information__grade"),
        "material_information__details": _attribute("material_information__details"),
        "data_information__record_name": _attribute("data_information__record_name"),
        "data_information__technical_data_id": _attribute(
            "data_information__technical_data_id"
        ),
    }


def test_fixture_specs_are_exactly_1000_searchable_metadata_records() -> None:
    specs = scale_fixture.fixture_specs()

    assert len(specs) == 1_000
    assert len({item.code for item in specs}) == 1_000
    assert specs[0].code == "CMP-SCALE-0000"
    assert specs[-1].code == "CMP-SCALE-0999"
    assert Counter(item.material_class for item in specs) == {
        "Metal": 500,
        "Plastic": 300,
        "Rubber": 200,
    }
    assert all("production" not in item.name.lower() for item in specs)


@pytest.mark.parametrize(
    ("project", "marker"),
    (
        ("cmp-local-demo", "cmp-local-demo"),
        ("cmp-demo-test", "cmp-demo-test"),
        ("cmp-demo-test-proof123", None),
        ("cmp-demo-test-proof123", "cmp-demo-test-other456"),
    ),
)
def test_scale_fixture_rejects_non_disposable_or_unmatched_context(
    project: str, marker: str | None
) -> None:
    with pytest.raises(scale_fixture.DemoSeedError):
        scale_fixture.validate_disposable_context(project, marker)


def test_scale_fixture_accepts_only_the_matching_unique_disposable_project() -> None:
    project = "cmp-demo-test-proof123"

    assert scale_fixture.validate_disposable_context(project, project) == project


def test_scale_record_creates_one_exact_material_binding_without_curve_payloads() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeApi:
        def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            calls.append((path, payload))
            if path == "/materials":
                return {
                    "material_id": "material-731",
                    "current_revision": {
                        "id": "material-revision-731",
                        "content": payload["content"],
                    },
                }
            if path.endswith("/records"):
                return {
                    "record_id": "record-731",
                    "current_revision": {
                        "id": "record-revision-731",
                        "content": payload["content"],
                    },
                }
            return {"binding_id": "binding-731"}

    code = scale_fixture._create_scale_record(
        FakeApi(),
        table_id="table-1",
        table_revision_id="table-revision-1",
        attributes=_attributes(),
        spec=scale_fixture.scale_record_spec(731),
    )

    assert code == "CMP-SCALE-0731"
    assert [path for path, _ in calls] == [
        "/materials",
        "/catalog/tables/table-1/records",
        "/catalog/records/record-731/revisions/record-revision-731/domain-binding",
    ]
    record_values = calls[1][1]["content"]["values"]
    assert len(record_values) == 6
    assert {value["data_type"] for value in record_values} == {"text", "discrete"}
    assert calls[2][1] == {
        "kind": "material",
        "object_id": "material-731",
        "revision_id": "material-revision-731",
    }


def test_exact_lookup_publication_approves_only_the_representative_revision() -> None:
    administrator_calls: list[tuple[str, dict[str, Any]]] = []
    reviewer_calls: list[tuple[str, dict[str, Any]]] = []

    class AdministratorApi:
        def get(self, path: str) -> dict[str, Any]:
            assert path == (
                "/review-requests?aggregate_type=catalog.configurable_record"
                "&aggregate_id=record-731&revision_id=record-revision-731&limit=20"
            )
            return {"items": []}

        def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            administrator_calls.append((path, payload))
            return {"review_request_id": "review-731", "decision": None}

    class ReviewerApi:
        def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
            reviewer_calls.append((path, payload))
            return {"review_request_id": "review-731", "decision": "approved"}

    scale_fixture._ensure_exact_lookup_publication(
        AdministratorApi(),
        ReviewerApi(),
        {
            "record_id": "record-731",
            "current_revision": {
                "id": "record-revision-731",
                "content_hash": "sha256:record-731",
            },
        },
    )

    assert len(administrator_calls) == 1
    assert administrator_calls[0][0] == "/review-requests"
    assert administrator_calls[0][1]["aggregate_id"] == "record-731"
    assert administrator_calls[0][1]["revision_id"] == "record-revision-731"
    assert reviewer_calls == [
        (
            "/review-requests/review-731/decisions",
            {
                "expected_manifest_sha256": "sha256:record-731",
                "decision": "approved",
                "reason": "Approve the disposable exact source-v2 Record revision.",
            },
        )
    ]


def test_exact_lookup_publication_reuses_an_existing_approval() -> None:
    class AdministratorApi:
        def get(self, _path: str) -> dict[str, Any]:
            return {
                "items": [
                    {
                        "review_request_id": "review-731",
                        "manifest_sha256": "sha256:record-731",
                        "decision": {"decision": "approved"},
                    }
                ]
            }

        def post(self, _path: str, _payload: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("an existing approval must not create another request")

    class ReviewerApi:
        def post(self, _path: str, _payload: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("an existing approval must not be decided again")

    scale_fixture._ensure_exact_lookup_publication(
        AdministratorApi(),
        ReviewerApi(),
        {
            "record_id": "record-731",
            "current_revision": {
                "id": "record-revision-731",
                "content_hash": "sha256:record-731",
            },
        },
    )


def test_full_fixture_publication_search_uses_a_bounded_timeout_for_every_page(
    monkeypatch: MonkeyPatch,
) -> None:
    searches: list[tuple[dict[str, Any], float | None]] = []
    published: list[str] = []

    class PublicationApi:
        def post(
            self,
            path: str,
            payload: dict[str, Any],
            *,
            timeout: float | None = None,
        ) -> dict[str, Any]:
            assert path == "/catalog/records:search"
            searches.append((payload, timeout))
            offset = int(payload["offset"])
            return {
                "items": [
                    {
                        "record_id": f"record-{index}",
                        "current_revision": {
                            "id": f"record-revision-{index}",
                            "content_hash": f"sha256:record-{index}",
                        },
                    }
                    for index in range(offset, offset + scale_fixture.PAGE_SIZE)
                ]
            }

    monkeypatch.setattr(
        scale_fixture,
        "_ensure_exact_lookup_publication",
        lambda _api, _reviewer, record: published.append(str(record["record_id"])),
    )

    scale_fixture._publish_all_records(PublicationApi(), object(), table_id="table-1")

    assert len(searches) == scale_fixture.FIXTURE_COUNT // scale_fixture.PAGE_SIZE
    assert [payload["offset"] for payload, _ in searches] == list(
        range(0, scale_fixture.FIXTURE_COUNT, scale_fixture.PAGE_SIZE)
    )
    assert {timeout for _, timeout in searches} == {
        scale_fixture.SCALE_FIXTURE_SEARCH_TIMEOUT_SECONDS
    }
    assert len(published) == scale_fixture.FIXTURE_COUNT
