from __future__ import annotations

import sys
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

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

    assert _SEED_FULL_DEMO._catalog_record_content_matches(
        reordered_content, desired_content
    )


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
        assert _SEED_FULL_DEMO._preserve_material_family(
            {"material_family": family}, fixture_families[0]
        ) == family


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
                        "Public synthetic T-60 reference fixture; "
                        "not validated engineering data."
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
