from __future__ import annotations

import io
import sys
import zipfile
from collections.abc import Mapping
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, cast

import pytest

_SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = spec_from_file_location("seed_full_demo_catalog", _SCRIPTS / "seed_full_demo.py")
assert _SPEC is not None and _SPEC.loader is not None
_SEED_FULL_DEMO = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SEED_FULL_DEMO)


def test_catalog_record_content_comparison_uses_attribute_ids_for_value_order() -> None:
    desired_content = {
        "table_revision_id": "table-revision-1",
        "name": "Synthetic polymer",
        "external_key": "CMP-DEMO-POLYMER",
        "values": [
            {
                "attribute_definition_id": "attribute-material-class",
                "value": "polymer",
            },
            {
                "attribute_definition_id": "attribute-density",
                "normalized_value": "950",
            },
        ],
    }
    reordered_content = {
        **desired_content,
        "values": list(reversed(desired_content["values"])),
    }

    assert _SEED_FULL_DEMO._catalog_record_content_matches(reordered_content, desired_content)


def test_catalog_record_content_comparison_keeps_value_and_content_differences() -> None:
    desired_content = {
        "table_revision_id": "table-revision-1",
        "name": "Synthetic elastomer",
        "external_key": "CMP-DEMO-ELASTOMER",
        "values": [
            {
                "attribute_definition_id": "attribute-material-class",
                "value": "elastomer",
            }
        ],
    }
    changed_value_content = {
        **desired_content,
        "values": [
            {
                "attribute_definition_id": "attribute-material-class",
                "value": "polymer",
            }
        ],
    }
    changed_name_content = {**desired_content, "name": "Changed elastomer"}

    assert not _SEED_FULL_DEMO._catalog_record_content_matches(
        changed_value_content, desired_content
    )
    assert not _SEED_FULL_DEMO._catalog_record_content_matches(
        changed_name_content, desired_content
    )


def test_catalog_record_name_repair_is_detected_once_and_second_run_is_stable() -> None:
    desired_content = {
        "table_revision_id": "table-revision-1",
        "name": "DP780 synthetic reference steel",
        "external_key": "CMP-DEMO-DP780",
        "description": "Synthetic DP780 reference record.",
        "values": [
            {
                "attribute_definition_id": "attribute-material-class",
                "value": "metal",
            }
        ],
    }
    stale_content = {**desired_content, "name": "DP780 synthetic demo steel"}

    assert not _SEED_FULL_DEMO._catalog_record_content_matches(stale_content, desired_content)
    # Once the seed writes the current Material name, an identical second run
    # must not create another immutable Catalog revision.
    assert _SEED_FULL_DEMO._catalog_record_content_matches(desired_content, desired_content)


def test_catalog_material_families_remain_fixture_text_and_allowed_values() -> None:
    fixture_families = (
        "dual-phase steel",
        "linear viscoelastic polymer",
        "Ogden hyper-viscoelastic elastomer",
    )
    workflow_families = (
        "Material state",
        "Test data",
        "Processing",
        "Material model",
        "Neutral material",
        "Solver card",
        "Release",
    )

    assert _SEED_FULL_DEMO._catalog_material_family_allowed_values() == (
        *fixture_families,
        *workflow_families,
    )
    for family in fixture_families:
        assert (
            _SEED_FULL_DEMO._preserve_material_family(
                {"material_family": family}, fixture_families[0]
            )
            == family
        )


def test_demo_density_fixture_is_supported_si_and_non_production() -> None:
    assert _SEED_FULL_DEMO._DEMO_METAL_DENSITY_FIXTURE == ("7850", "kg/m^3", "7850")
    assert _SEED_FULL_DEMO._METAL_CATALOG_DESCRIPTION is None


def test_issue342_seed_schema_upload_keeps_the_source_v2_files_unchanged() -> None:
    archive = _SEED_FULL_DEMO._fixture_schema_source_zip()

    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        assert source.namelist() == [
            "catalog-schema-bundle.manifest.json",
            "record-schemas/dma-test-v1.json",
            "record-schemas/elastoplasticity-v2.json",
            "record-schemas/fld-test-v1.json",
            "record-schemas/statistics-v2.json",
            "record-schemas/technical-data-v2.json",
            "record-schemas/tensile-test-v2.json",
        ]
        assert source.read("catalog-schema-bundle.manifest.json") == (
            _SEED_FULL_DEMO._SOURCE_V2_FIXTURE_ROOT
            / "catalog-schema-bundle.manifest.json"
        ).read_bytes()


class _Issue342SchemaBootstrapApi:
    def __init__(self) -> None:
        self.posts: list[tuple[str, float | None]] = []

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        del payload, headers
        self.posts.append((path, timeout))
        if path == "/uploads":
            return {
                "upload": {
                    "upload_id": "schema-upload-1",
                    "state": "open",
                    "expected_part_count": 1,
                },
                "upload_capability": "schema-capability",
            }
        if path == "/uploads/schema-upload-1:complete":
            return {"available_artifact_id": "schema-artifact-1"}
        if path == "/catalog/schema-definition-bundles:plan":
            return {"valid": True, "plan_fingerprint": "a" * 64}
        if path == "/catalog/schema-definition-bundles:apply":
            return {"application_id": "schema-application-1"}
        raise AssertionError(f"unexpected POST {path}")

    def put_bytes(
        self, path: str, payload: bytes, *, headers: Mapping[str, str]
    ) -> dict[str, Any]:
        assert path == "/uploads/schema-upload-1/parts/1"
        assert payload
        assert headers["Upload-Capability"] == "schema-capability"
        assert headers["Content-Type"] == "application/vnd.cmp.catalog-schema-source-set+zip"
        return {"upload_id": "schema-upload-1"}

    def get(self, path: str) -> dict[str, Any]:
        assert path == "/catalog/json-record-formats"
        table_keys = {
            "technical-data": "technical_data",
            "tensile-test": "tensile_test",
            "dma-test": "dma_test",
            "fld-test": "fld_test",
            "elastoplasticity": "elastoplasticity_data",
            "statistics": "statistics_data",
        }
        return {
            "items": [
                {
                    "wrapper": wrapper,
                    "table": {"id": f"{table_key}-id", "key": table_key},
                }
                for wrapper, table_key in table_keys.items()
            ]
        }


def test_issue342_schema_apply_uses_only_the_bounded_extended_timeout() -> None:
    api = _Issue342SchemaBootstrapApi()

    result = _SEED_FULL_DEMO._ensure_issue342_schema_bundle(api)

    assert result["schema_application_id"] == "schema-application-1"
    assert [
        (path, timeout)
        for path, timeout in api.posts
        if path == "/catalog/schema-definition-bundles:apply"
    ] == [("/catalog/schema-definition-bundles:apply", 180.0)]
    assert all(
        timeout is None
        for path, timeout in api.posts
        if path != "/catalog/schema-definition-bundles:apply"
    )


class _SourceV2PreflightApi:
    def __init__(
        self,
        *,
        records: Mapping[str, Mapping[str, Any]] | None = None,
        bindings: Mapping[str, list[Mapping[str, Any]]] | None = None,
    ) -> None:
        manifest, entries = _SEED_FULL_DEMO._source_v2_fixture_manifest()
        del manifest
        self.table_ids = {
            table_key: f"{table_key}-id"
            for table_key in _SEED_FULL_DEMO._SOURCE_V2_TABLE_KEYS
        }
        self.entries = entries
        self.records = dict(records or {})
        self.bindings = {key: list(value) for key, value in (bindings or {}).items()}

    def get(self, path: str) -> dict[str, Any]:
        if path == "/catalog/tables":
            return {
                "items": [
                    {
                        "table_id": table_id,
                        "current_revision": {"content": {"key": table_key}},
                    }
                    for table_key, table_id in sorted(self.table_ids.items())
                ]
            }
        marker = "/catalog/records/"
        if marker in path and path.endswith("/domain-bindings"):
            record_id = path.split("/")[3]
            return {"items": self.bindings.get(record_id, [])}
        raise AssertionError(f"unexpected GET {path}")

    def post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        assert path == "/catalog/records:search"
        table_id = payload["table_id"]
        external_key = payload["text"]
        table_key = next(key for key, value in self.table_ids.items() if value == table_id)
        entry = self.entries.get(external_key)
        if entry is None:
            return {"items": []}
        wrapper_to_table = {
            "technical-data": "technical_data",
            "tensile-test": "tensile_test",
            "dma-test": "dma_test",
            "fld-test": "fld_test",
            "elastoplasticity": "elastoplasticity_data",
            "statistics": "statistics_data",
        }
        if wrapper_to_table[entry["wrapper"]] != table_key:
            return {"items": []}
        value = self.records.get(external_key)
        if value is None:
            return {"items": []}
        return {"items": [value]}


def _source_v2_records() -> dict[str, dict[str, Any]]:
    _, entries = _SEED_FULL_DEMO._source_v2_fixture_manifest()
    return {
        key: {
            "record_id": f"record-{index}",
            "current_revision": {
                "id": f"record-{index}-r1",
                "revision_no": 1,
                "content": {"external_key": key},
            },
        }
        for index, key in enumerate(entries, 1)
    }


def test_source_v2_preflight_rejects_legacy_table_before_mutation() -> None:
    api = _SourceV2PreflightApi()
    api.table_ids = {"demo_material_records": "legacy-id"}

    with pytest.raises(_SEED_FULL_DEMO.DemoSeedError, match="legacy demo_material_records"):
        _SEED_FULL_DEMO._preflight_source_v2_catalog_state(api)


def test_source_v2_preflight_rejects_partial_tables_and_records() -> None:
    api = _SourceV2PreflightApi()
    api.table_ids.pop("statistics_data")
    with pytest.raises(_SEED_FULL_DEMO.DemoSeedError, match="partial table installation"):
        _SEED_FULL_DEMO._preflight_source_v2_catalog_state(api)

    records = _source_v2_records()
    api = _SourceV2PreflightApi(
        records={"CMP-246-TECH-DP780": records["CMP-246-TECH-DP780"]}
    )
    with pytest.raises(_SEED_FULL_DEMO.DemoSeedError, match="partial fifteen-Record"):
        _SEED_FULL_DEMO._preflight_source_v2_catalog_state(api)


def test_source_v2_preflight_accepts_exact_r1_and_rejects_conflicting_owner() -> None:
    records = _source_v2_records()
    tabulated_record_id = records["CMP-246-EP-TABULATED"]["record_id"]
    api = _SourceV2PreflightApi(
        records=records,
        bindings={
            tabulated_record_id: [
                {"kind": "material_model", "object_id": "model-1", "revision_id": "model-r1"}
            ]
        },
    )
    expected = {"CMP-246-EP-TABULATED": ("material_model", "model-1", "model-r1")}
    assert _SEED_FULL_DEMO._preflight_source_v2_catalog_state(
        api, domain_targets=expected
    ) == records

    record_id = records["CMP-246-EP-TABULATED"]["record_id"]
    api.bindings[record_id] = [
        {"kind": "material_model", "object_id": "different", "revision_id": "model-r1"}
    ]
    with pytest.raises(_SEED_FULL_DEMO.DemoSeedError, match="conflicting domain owner"):
        _SEED_FULL_DEMO._preflight_source_v2_catalog_state(api, domain_targets=expected)


def test_source_v2_preflight_rejects_revised_record_without_guessing() -> None:
    records = _source_v2_records()
    revised = records["CMP-246-TECH-DP780"]
    revised["current_revision"]["revision_no"] = 2
    api = _SourceV2PreflightApi(records=records)

    with pytest.raises(_SEED_FULL_DEMO.DemoSeedError, match="immutable r1"):
        _SEED_FULL_DEMO._preflight_source_v2_catalog_state(api)


def test_catalog_attribute_contract_repairs_units_and_semantics_idempotently() -> None:
    desired = _SEED_FULL_DEMO._catalog_attribute_updates(
        table_revision_id="table-r1",
        name="Poisson's ratio",
        data_type="number",
        quantity_semantics="strain",
        normalized_unit="1",
        allowed_values=(),
        minimum_number=0,
        maximum_number=0.5,
    )
    stale = {**desired, "quantity_semantics": "ratio.poisson"}

    assert any(stale.get(field) != value for field, value in desired.items())
    assert not any(desired.get(field) != value for field, value in desired.items())


def test_existing_neutral_selects_its_exact_processing_model() -> None:
    models = [
        {
            "material_model_id": "model-wrong",
            "current_revision": {
                "content": {
                    "processing_projection": {
                        "output_id": "output-other",
                        "output_revision_id": "output-other-r1",
                    }
                }
            },
        },
        {
            "material_model_id": "model-exact",
            "current_revision": {
                "content": {
                    "processing_projection": {
                        "output_id": "output-exact",
                        "output_revision_id": "output-exact-r1",
                    }
                }
            },
        },
    ]
    neutral = {
        "document": {
            "candidate_selection": {
                "processing_output": {
                    "id": "output-exact",
                    "revision_id": "output-exact-r1",
                }
            }
        }
    }

    selected = _SEED_FULL_DEMO._model_for_neutral_processing_output(models, neutral)

    assert selected is models[1]


class _TestDocumentCaptureApi:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []
        self.snapshots: list[dict[str, Any]] = []
        self.revisions: list[str] = []

    def get(self, path: str) -> dict[str, Any]:
        if path == "/test-data-documents?limit=100":
            return {"items": deepcopy(self.snapshots)}
        if path.endswith("/content"):
            document_id = path.split("/")[2]
            ordinal = int(document_id.rsplit("-", 1)[1])
            return deepcopy(self.documents[ordinal - 1])
        raise AssertionError(f"unexpected GET {path}")

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if path == "/test-data-documents":
            assert headers is None
            self.documents.append(deepcopy(payload["document"]))
            ordinal = len(self.documents)
            snapshot = {
                "test_data_document_id": f"document-{ordinal}",
                "document_key": payload["document"]["document_id"],
                "current_revision": {
                    "id": f"document-{ordinal}-r1",
                    "revision_no": 1,
                    "content_hash": f"{ordinal:064x}",
                },
            }
            self.snapshots.append(snapshot)
            return deepcopy(snapshot)
        if path.startswith("/test-data-documents/") and path.endswith("/revisions"):
            document_id = path.split("/")[2]
            ordinal = int(document_id.rsplit("-", 1)[1])
            snapshot = self.snapshots[ordinal - 1]
            current = snapshot["current_revision"]
            assert headers == {
                "If-Match": (
                    f'"revision:{current["revision_no"]}:sha256:{current["content_hash"]}"'
                )
            }
            self.documents[ordinal - 1] = deepcopy(payload["document"])
            revision_no = current["revision_no"] + 1
            snapshot["current_revision"] = {
                "id": f"{document_id}-r{revision_no}",
                "revision_no": revision_no,
                "content_hash": f"{ordinal + revision_no:064x}",
            }
            self.revisions.append(payload["document"]["document_id"])
            return deepcopy(snapshot)
        raise AssertionError(f"unexpected POST {path}")


def test_issue246_test_examples_are_complete_reusable_engineering_records() -> None:
    api = _TestDocumentCaptureApi()

    examples = _SEED_FULL_DEMO._ensure_issue246_test_documents(api)

    assert [item["test_type"] for item in examples].count("Tensile") == 4
    assert [item["test_type"] for item in examples].count("DMA") == 3
    assert [item["test_type"] for item in examples].count("FLD") == 2
    assert len({item["key"] for item in examples}) == 9
    assert len({item["name"] for item in examples}) == 9
    assert all(item["name"].endswith(" · synthetic reference") for item in examples)
    room = next(item for item in examples if item["key"] == "CMP-246-TENSILE-ROOM")
    assert room["condition"] == "23 °C; 0.0067 s⁻¹"
    assert room["result_summary"] == (
        "E 210 GPa; 0.2% proof stress 410 MPa; maximum measured stress 775 MPa; "
        "maximum measured strain 14.0%."
    )
    assert room["curve_coverage"] == (
        "Engineering strain: 0 to 0.14 1; Engineering stress: 0 to 775000000 Pa"
    )
    room_document = next(
        item for item in api.documents if item["document_id"] == "CMP-246-TENSILE-ROOM"
    )
    assert len(room_document["channels"][0]["normalized_values"]) == 8
    assert len(room_document["channels"][1]["normalized_values"]) == 8
    dma = next(item for item in examples if item["key"] == "CMP-246-DMA-+23C")
    assert dma["result_summary"] == (
        "At 1 Hz: storage modulus 7.31 GPa; loss modulus 445 MPa; loss factor 0.061."
    )
    fld = next(item for item in examples if item["key"] == "CMP-246-FLD-NAKAJIMA")
    assert "Plane-strain limit ε1=0.31 at ε2=0.00" in fld["result_summary"]
    fld_document = next(
        item for item in api.documents if item["document_id"] == "CMP-246-FLD-NAKAJIMA"
    )
    assert fld_document["test"]["method"] == (
        "Synthetic non-production forming-limit characterization"
    )
    assert "ISO" not in fld_document["test"]["method"]
    assert all(
        document["test"]["laboratory"] == "CMP synthetic validation laboratory"
        for document in api.documents
    )


def test_issue246_test_example_refreshes_drift_and_then_is_idempotent() -> None:
    api = _TestDocumentCaptureApi()
    _SEED_FULL_DEMO._ensure_issue246_test_documents(api)
    dma_ordinal = next(
        index
        for index, document in enumerate(api.documents)
        if document["document_id"] == "CMP-246-DMA-+23C"
    )
    api.documents[dma_ordinal]["channels"][1]["original_values"] = ["1", "2"]
    api.documents[dma_ordinal]["channels"][1]["normalized_values"] = ["1", "2"]

    refreshed = _SEED_FULL_DEMO._ensure_issue246_test_documents(api)
    stable = _SEED_FULL_DEMO._ensure_issue246_test_documents(api)

    assert api.revisions == ["CMP-246-DMA-+23C"]
    refreshed_dma = next(item for item in refreshed if item["key"] == "CMP-246-DMA-+23C")
    stable_dma = next(item for item in stable if item["key"] == "CMP-246-DMA-+23C")
    assert refreshed_dma["revision_id"] == stable_dma["revision_id"]
    assert refreshed_dma["revision_id"].endswith("-r2")


class _LegacyMaterialApi:
    def __init__(self) -> None:
        self.material: dict[str, Any] = {
            "material_id": "material-1",
            "current_revision": {
                "id": "material-r1",
                "revision_no": 1,
                "content_hash": "a" * 64,
                "change_reason": "Preserve the existing change reason.",
                "content": {
                    "name": "Demo Polymer Prony",
                    "material_code": "CMP-DEMO-POLYMER-PRONY",
                    "material_family": "linear viscoelastic polymer",
                    "material_class": "polymer",
                    "description": (
                        "Public synthetic T-60 reference fixture; not validated engineering data."
                    ),
                },
            },
        }
        self.revisions: list[dict[str, Any]] = []

    def get(self, path: str) -> dict[str, Any]:
        if path == "/materials?q=CMP-DEMO-POLYMER-PRONY&limit=20":
            return {"items": [deepcopy(self.material)]}
        if path == "/materials/material-1":
            return {
                "material": deepcopy(self.material),
                "states": [],
                "property_sets": [],
            }
        raise AssertionError(f"unexpected GET {path}")

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        assert path == "/materials/material-1/revisions"
        assert headers == {"If-Match": '"revision:1:sha256:' + "a" * 64 + '"'}
        self.revisions.append(deepcopy(payload))
        self.material = {
            "material_id": "material-1",
            "current_revision": {
                "id": "material-r2",
                "revision_no": 2,
                "content_hash": "b" * 64,
                "change_reason": payload["change_reason"],
                "content": deepcopy(payload["content"]),
            },
        }
        return deepcopy(self.material)


def test_nonmetal_material_copy_repair_is_single_revision_and_preserves_reason() -> None:
    api = _LegacyMaterialApi()

    first = _SEED_FULL_DEMO._ensure_material(
        api,
        name="Synthetic Polymer Prony",
        material_code="CMP-DEMO-POLYMER-PRONY",
        material_family="linear viscoelastic polymer",
        material_class="polymer",
    )
    second = _SEED_FULL_DEMO._ensure_material(
        api,
        name="Synthetic Polymer Prony",
        material_code="CMP-DEMO-POLYMER-PRONY",
        material_family="linear viscoelastic polymer",
        material_class="polymer",
    )

    content = first["material"]["current_revision"]["content"]
    assert content["name"] == "Synthetic Polymer Prony"
    assert content["description"] == _SEED_FULL_DEMO._NON_METAL_MATERIAL_DESCRIPTION
    assert api.revisions[0]["change_reason"] == "Preserve the existing change reason."
    assert len(api.revisions) == 1
    assert second["material"]["current_revision"]["id"] == "material-r2"


class _CatalogBindingApi:
    def __init__(
        self,
        bindings: list[dict[str, Any]],
        *,
        post_error: Exception | None = None,
    ) -> None:
        self.bindings = deepcopy(bindings)
        self.post_error = post_error
        self.posts: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str) -> dict[str, Any]:
        assert path == "/catalog/records/record-1/revisions/record-r1/domain-bindings"
        return {"items": deepcopy(self.bindings)}

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.post_error is not None:
            raise self.post_error
        self.posts.append((path, deepcopy(payload)))
        created = {"binding_id": "binding-1", **payload}
        self.bindings.append(created)
        return created


def _ensure_test_binding(api: _CatalogBindingApi) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _SEED_FULL_DEMO._ensure_catalog_domain_binding(
            api,
            record_id="record-1",
            record_revision_id="record-r1",
            kind="neutral_material",
            object_id="neutral-1",
            revision_id="neutral-r1",
            stage="Neutral Catalog projection",
        ),
    )


def test_catalog_domain_binding_repeat_run_reuses_the_exact_binding_without_post() -> None:
    exact = {
        "binding_id": "binding-1",
        "kind": "neutral_material",
        "object_id": "neutral-1",
        "revision_id": "neutral-r1",
    }
    api = _CatalogBindingApi([exact])

    assert _ensure_test_binding(api) == exact
    assert api.posts == []


def test_catalog_domain_binding_conflict_names_the_seed_stage() -> None:
    api = _CatalogBindingApi(
        [
            {
                "binding_id": "binding-old",
                "kind": "neutral_material",
                "object_id": "neutral-old",
                "revision_id": "neutral-old-r1",
            }
        ]
    )

    with pytest.raises(
        _SEED_FULL_DEMO.DemoSeedError,
        match=r"Neutral Catalog projection.*conflicts with the expected exact target",
    ):
        _ensure_test_binding(api)


def test_catalog_domain_binding_409_names_the_seed_stage() -> None:
    api = _CatalogBindingApi(
        [],
        post_error=_SEED_FULL_DEMO.DemoSeedError("POST domain-binding returned 409"),
    )

    with pytest.raises(
        _SEED_FULL_DEMO.DemoSeedError,
        match=r"Neutral Catalog projection.*create failed.*409",
    ):
        _ensure_test_binding(api)


def test_baseline_model_selection_skips_newer_promoted_models() -> None:
    promoted = {
        "material_model_id": "promoted-model",
        "current_revision": {
            "content": {
                "property_set_revision_id": "property-r1",
                "processing_promotion_evidence": {"output_id": "output-1"},
            }
        },
    }
    baseline = {
        "material_model_id": "baseline-model",
        "current_revision": {
            "content": {
                "property_set_revision_id": "property-r0",
                "prony_promotion_evidence": None,
                "processing_promotion_evidence": None,
            }
        },
    }

    selected = _SEED_FULL_DEMO._unpromoted_model(
        [promoted, baseline],
        promotion_fields=("prony_promotion_evidence", "processing_promotion_evidence"),
    )

    assert selected is baseline


def test_ogden_repeat_seed_prefers_the_promoted_baseline_identity() -> None:
    promoted = {
        "material_model_id": "promoted-baseline-model",
        "current_revision": {"content": {"promotion_evidence": {"selection_id": "selection-1"}}},
    }
    unpromoted = {
        "material_model_id": "stale-unpromoted-model",
        "current_revision": {"content": {"promotion_evidence": None}},
    }
    models = [promoted, unpromoted]

    selected = next(
        (
            model
            for model in models
            if isinstance(
                _SEED_FULL_DEMO._content(model).get("promotion_evidence"),
                Mapping,
            )
        ),
        None,
    ) or _SEED_FULL_DEMO._unpromoted_model(models, promotion_fields=("promotion_evidence",))

    assert selected is promoted
