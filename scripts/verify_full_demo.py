"""Verify the clean three-family demo through protected HTTP resources."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections.abc import Mapping, Sequence
from typing import Any, cast

import httpx

MATERIALS = {
    "CMP-DEMO-DP780": ("tabulated-plasticity-models", {"abaqus", "openradioss"}),
    "CMP-DEMO-POLYMER-PRONY": ("linear-viscoelastic-models", {"abaqus"}),
    "CMP-DEMO-ELASTOMER-OGDEN": ("ogden-prony-models", {"abaqus", "openradioss"}),
}


def _json(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeError(f"{response.request.url.path} did not return an object")
    return cast(dict[str, Any], value)


def _items(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("items")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    return content if isinstance(content, Mapping) else {}


def verify_full_demo(base_url: str) -> dict[str, object]:
    with httpx.Client(base_url=base_url, timeout=60.0) as anonymous:
        token = str(_json(anonymous.get("/demo-identity/token"))["access_token"])
    result: dict[str, object] = {}
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    ) as client:
        materials = _items(_json(client.get("/materials?limit=100")))
        for material_code, (model_path, required_solvers) in MATERIALS.items():
            material = next(
                (
                    item
                    for item in materials
                    if _content(item).get("material_code") == material_code
                ),
                None,
            )
            if material is None:
                raise RuntimeError(f"clean demo is missing {material_code}")
            material_id = str(material["material_id"])
            detail = _json(client.get(f"/materials/{material_id}"))
            states = detail.get("states")
            if not isinstance(states, list) or not states or not isinstance(states[0], dict):
                raise RuntimeError(f"{material_code} has no Material State")
            state_id = str(states[0]["material_state_id"])
            models = _items(_json(client.get(f"/material-states/{state_id}/{model_path}")))
            if not models:
                raise RuntimeError(f"{material_code} has no {model_path}")
            solvers: set[str] = set()
            selected_model = models[0]
            for candidate_model in models:
                candidate_model_id = str(candidate_model["material_model_id"])
                cards = _items(
                    _json(client.get(f"/{model_path}/{candidate_model_id}/solver-cards"))
                )
                candidate_solvers = {
                    str(target.get("solver"))
                    for item in cards
                    if isinstance((target := item.get("target")), Mapping)
                }
                solvers.update(candidate_solvers)
                if required_solvers <= candidate_solvers:
                    selected_model = candidate_model
            model = selected_model
            model_id = str(model["material_model_id"])
            missing = required_solvers - solvers
            if missing:
                raise RuntimeError(f"{material_code} is missing cards for {sorted(missing)}")
            revision = model.get("current_revision")
            result[material_code] = {
                "material_id": material_id,
                "material_state_id": state_id,
                "material_model_id": model_id,
                "material_model_revision_no": (
                    revision.get("revision_no") if isinstance(revision, Mapping) else None
                ),
                "solver_cards": sorted(solvers),
            }

        polymer = next(
            item
            for item in materials
            if _content(item).get("material_code") == "CMP-DEMO-POLYMER-PRONY"
        )
        polymer_id = str(polymer["material_id"])
        polymer_detail = _json(client.get(f"/materials/{polymer_id}"))
        polymer_states = polymer_detail.get("states")
        if (
            not isinstance(polymer_states, list)
            or not polymer_states
            or not isinstance(polymer_states[0], Mapping)
        ):
            raise RuntimeError("clean demo polymer has no Material State")
        polymer_state_id = str(polymer_states[0]["material_state_id"])
        polymer_models = _items(
            _json(client.get(f"/material-states/{polymer_state_id}/linear-viscoelastic-models"))
        )
        processed_model = next(
            (
                item
                for item in polymer_models
                if isinstance(_content(item).get("processing_promotion_evidence"), Mapping)
            ),
            None,
        )
        if processed_model is None:
            raise RuntimeError("clean demo polymer has no Processing-promoted IR")
        processed_content = _content(processed_model)
        processing_evidence = processed_content["processing_promotion_evidence"]
        assert isinstance(processing_evidence, Mapping)
        terms = processed_content.get("terms")
        if (
            not isinstance(terms, list)
            or not 1 <= len(terms) <= 10
            or processing_evidence.get("selected_term_count") != len(terms)
        ):
            raise RuntimeError("processed polymer IR does not preserve selected Prony terms")
        polymer_recipe = next(
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_prony"
        )
        polymer_batch = next(
            item
            for item in _items(_json(client.get("/common-processing-batches")))
            if item.get("label") == "CMP demo polymer Prony batch"
        )
        if polymer_batch.get("status") != "succeeded":
            raise RuntimeError("polymer Processing Recipe batch did not succeed")
        polymer_attempt = next(
            item
            for item in polymer_batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        )
        polymer_output = next(
            item
            for item in _items(_json(client.get("/processing-outputs")))
            if item.get("processing_output_id") == polymer_attempt.get("output_id")
        )
        exact_output = processing_evidence.get("processing_output")
        recipe_batch = processing_evidence.get("recipe_batch")
        exact_recipe = (
            recipe_batch.get("processing_recipe") if isinstance(recipe_batch, Mapping) else None
        )
        if (
            not isinstance(exact_output, Mapping)
            or exact_output.get("id") != polymer_output.get("processing_output_id")
            or exact_output.get("revision_id")
            != polymer_output.get("current_revision", {}).get("id")
            or exact_output.get("sha256") != polymer_output.get("output_sha256")
            or not isinstance(exact_recipe, Mapping)
            or exact_recipe.get("id") != polymer_recipe.get("processing_recipe_id")
            or exact_recipe.get("revision_id")
            != polymer_recipe.get("current_revision", {}).get("id")
            or not isinstance(recipe_batch, Mapping)
            or not isinstance(polymer_attempt, Mapping)
            or recipe_batch.get("processing_batch_id") != polymer_batch.get("batch_id")
            or recipe_batch.get("batch_attempt_id") != polymer_attempt.get("attempt_id")
        ):
            raise RuntimeError(
                "processed polymer IR does not pin the exact Recipe/Batch/Output execution"
            )
        polymer_candidates = _items(
            _json(client.get(f"/bulk-export-candidates?material_id={polymer_id}"))
        )
        polymer_neutral = None
        for candidate in polymer_candidates:
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            candidate_id = source.get("neutral_material_id")
            if not isinstance(candidate_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{candidate_id}"))
            selection = candidate_neutral.get("document", {}).get("candidate_selection", {})
            if (
                isinstance(selection, Mapping)
                and selection.get("kind") == "prony_processing_output_selection"
            ):
                polymer_neutral = candidate_neutral
                break
        if polymer_neutral is None:
            raise RuntimeError("clean demo polymer has no Processing-selected Neutral JSON")
        polymer_neutral_id = str(polymer_neutral["neutral_material_id"])
        neutral_recipe = (
            polymer_neutral.get("document", {}).get("sources", {}).get("processing_recipe", {})
        )
        if (
            neutral_recipe.get("status") != "exact_revision"
            or neutral_recipe.get("reference", {}).get("id")
            != polymer_recipe.get("processing_recipe_id")
            or neutral_recipe.get("reference", {}).get("revision_id")
            != polymer_recipe.get("current_revision", {}).get("id")
        ):
            raise RuntimeError("polymer Neutral JSON does not pin the exact Processing Recipe")
        polymer_cards = _items(
            _json(client.get(f"/neutral-materials/{polymer_neutral_id}/solver-cards"))
        )
        polymer_native_cards: dict[str, dict[str, str]] = {}
        for solver, keyword in {
            "abaqus": b"*VISCOELASTIC, TIME=PRONY",
            "openradioss": b"/VISC/LPRONY/",
        }.items():
            polymer_card = next(
                (item for item in polymer_cards if item.get("target", {}).get("solver") == solver),
                None,
            )
            if polymer_card is None:
                raise RuntimeError(f"clean demo polymer Neutral JSON has no {solver} card")
            polymer_native = client.get(
                f"/neutral-solver-cards/{polymer_card['solver_card_id']}/download"
            )
            polymer_native.raise_for_status()
            if keyword not in polymer_native.content:
                raise RuntimeError(f"clean demo polymer native card omits {solver} Prony data")
            polymer_native_cards[solver] = {
                "solver_card_id": str(polymer_card["solver_card_id"]),
                "sha256": hashlib.sha256(polymer_native.content).hexdigest(),
            }
        polymer_bundle_id = None
        polymer_selection_content: Mapping[str, Any] | None = None
        for export_job in _items(_json(client.get("/export-jobs"))):
            selection_id = export_job.get("export_selection_id")
            if not isinstance(selection_id, str):
                continue
            export_selection = _json(client.get(f"/export-selections/{selection_id}"))
            selection_content = export_selection.get("current_revision", {}).get("content", {})
            if (
                isinstance(selection_content, Mapping)
                and selection_content.get("selection_label")
                == "CMP polymer Recipe to dual-solver governed transfer"
                and export_job.get("state") == "succeeded"
                and isinstance(export_job.get("bundle_id"), str)
            ):
                polymer_bundle_id = str(export_job["bundle_id"])
                polymer_selection_content = selection_content
                break
        if polymer_bundle_id is None or polymer_selection_content is None:
            raise RuntimeError("polymer Recipe-to-card Bulk ZIP was not generated")
        polymer_bundle = _json(client.get(f"/export-bundles/{polymer_bundle_id}"))
        required_kinds = {
            "test_data_json",
            "mapping_profile_json",
            "processing_recipe_json",
            "neutral_material_json",
            "neutral_solver_mapping_report",
            "neutral_solver_card_native",
        }
        component_kinds = {
            component.get("source", {}).get("kind")
            for component in polymer_selection_content.get("members", [])
            if isinstance(component, Mapping)
        }
        if not required_kinds <= component_kinds:
            raise RuntimeError("polymer Bulk ZIP omits a Recipe-to-card representation")
        result["polymer_processing_journey"] = {
            "processing_recipe_id": polymer_recipe["processing_recipe_id"],
            "processing_batch_id": polymer_batch["batch_id"],
            "processing_output_id": polymer_output["processing_output_id"],
            "material_model_id": processed_model["material_model_id"],
            "selected_term_count": len(terms),
            "neutral_material_id": polymer_neutral_id,
            "bulk_bundle_id": polymer_bundle_id,
            "bulk_component_count": polymer_bundle["component_count"],
            "solver_cards": polymer_native_cards,
        }

        metal = next(
            item for item in materials if _content(item).get("material_code") == "CMP-DEMO-DP780"
        )
        metal_id = str(metal["material_id"])
        tables = _items(_json(client.get("/catalog/tables")))
        table = next(
            item for item in tables if _content(item).get("key") == "demo_material_records"
        )
        subsets = _items(
            _json(client.get(f"/catalog/tables/{table['table_id']}/subsets"))
        )
        workflow_subset = next(
            (item for item in subsets if item.get("name") == "DP780 workflow records"),
            None,
        )
        if not isinstance(workflow_subset, Mapping):
            raise RuntimeError("clean demo Explorer has no reusable DP780 Subset")
        subset_filter = workflow_subset.get("filter_definition")
        if not isinstance(subset_filter, Mapping) or subset_filter.get("text") != "DP780":
            raise RuntimeError("clean demo Explorer Subset does not preserve its search")
        searched = _json(
            client.post(
                "/catalog/records:search",
                json={
                    "table_id": table["table_id"],
                    "text": "CMP-DEMO-DP780",
                    "limit": 20,
                },
            )
        )
        records = [
            item
            for item in _items(searched)
            if _content(item).get("external_key") == "CMP-DEMO-DP780"
        ]
        if len(records) != 1:
            raise RuntimeError("clean demo Catalog record is missing or ambiguous")
        catalog_record = records[0]
        catalog_revision = catalog_record.get("current_revision")
        if not isinstance(catalog_revision, Mapping):
            raise RuntimeError("clean demo Catalog record has no exact revision")
        binding = _json(
            client.get(
                f"/catalog/records/{catalog_record['record_id']}/revisions/"
                f"{catalog_revision['id']}/domain-binding"
            )
        )
        if binding.get("object_id") != metal_id or binding.get("kind") != "material":
            raise RuntimeError("clean demo Catalog binding does not pin the metal Material")
        workflow = _json(
            client.get(
                f"/catalog/workflow-explorer/{catalog_record['record_id']}/revisions/"
                f"{catalog_revision['id']}?depth=5"
            )
        )
        workflow_nodes = workflow.get("nodes")
        if not isinstance(workflow_nodes, list) or len(workflow_nodes) < 6:
            raise RuntimeError("clean demo Workflow Explorer does not reach the Neutral revision")
        neutral_record = next(
            (
                item
                for item in workflow_nodes
                if item.get("domain_binding", {}).get("kind") == "neutral_material"
            ),
            None,
        )
        if not isinstance(neutral_record, Mapping):
            raise RuntimeError("clean demo Workflow Explorer has no Neutral node")
        card_graph = _json(
            client.get(
                f"/catalog/workflow-explorer/{neutral_record['record_id']}/revisions/"
                f"{neutral_record['record_revision_id']}?depth=1"
            )
        )
        card_nodes = card_graph.get("nodes")
        if not isinstance(card_nodes, list):
            raise RuntimeError("clean demo card Workflow graph has no nodes")
        card_bindings = [
            item.get("domain_binding", {}).get("kind")
            for item in card_nodes
            if isinstance(item, Mapping)
        ]
        if card_bindings.count("neutral_solver_card") != 2:
            raise RuntimeError("clean demo Workflow Explorer does not branch to both cards")

        documents = _items(_json(client.get("/test-data-documents")))
        metal_replicates = [
            item
            for item in documents
            if str(item.get("document_key", "")).startswith("CMP-DEMO-DP780-TEST-JSON")
        ]
        if len(metal_replicates) < 3:
            raise RuntimeError("clean demo must expose three distinct DP780 Test JSON replicates")
        document = next(
            item for item in documents if item.get("document_key") == "CMP-DEMO-DP780-TEST-JSON"
        )
        document_revision = document.get("current_revision")
        if not isinstance(document_revision, Mapping):
            raise RuntimeError("clean demo Test JSON has no exact revision")
        downloaded_test = client.get(
            f"/test-data-documents/{document['test_data_document_id']}/revisions/"
            f"{document_revision['id']}/content"
        )
        downloaded_test.raise_for_status()
        canonical_test = downloaded_test.json()
        if canonical_test["material"]["grade"] != "DP780":
            raise RuntimeError("clean demo Test JSON did not preserve Material metadata")

        profile = next(
            item
            for item in _items(_json(client.get("/mapping-profiles")))
            if item.get("content", {}).get("profile_key") == "cmp_demo_tensile_json"
        )
        recipe = next(
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_tensile_cleanup"
        )
        if recipe.get("content", {}).get("lifecycle_state") != "published":
            raise RuntimeError("clean demo Processing Recipe is not published")
        batch = next(
            item
            for item in _items(_json(client.get("/common-processing-batches")))
            if item.get("label") == "CMP clean demo canonical JSON batch"
        )
        if batch.get("status") != "succeeded":
            raise RuntimeError("clean demo Processing Batch did not succeed")
        batch_attempt = next(
            item
            for item in batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        )
        metal_detail = _json(client.get(f"/materials/{metal_id}"))
        metal_states = metal_detail.get("states")
        if not isinstance(metal_states, list) or not metal_states:
            raise RuntimeError("clean demo metal Material has no State for Recipe evidence")
        metal_state_id = str(metal_states[0]["material_state_id"])
        metal_models = _items(
            _json(client.get(f"/material-states/{metal_state_id}/tabulated-plasticity-models"))
        )
        metal_model = next(
            item
            for item in metal_models
            if isinstance(_content(item).get("processing_projection"), Mapping)
        )
        metal_projection = _content(metal_model)["processing_projection"]
        assert isinstance(metal_projection, Mapping)
        metal_recipe_batch = metal_projection.get("recipe_batch")
        exact_metal_recipe = (
            metal_recipe_batch.get("processing_recipe")
            if isinstance(metal_recipe_batch, Mapping)
            else None
        )
        if (
            not isinstance(exact_metal_recipe, Mapping)
            or exact_metal_recipe.get("id") != recipe.get("processing_recipe_id")
            or exact_metal_recipe.get("revision_id")
            != recipe.get("current_revision", {}).get("id")
            or not isinstance(metal_recipe_batch, Mapping)
            or not isinstance(batch_attempt, Mapping)
            or metal_recipe_batch.get("processing_batch_id") != batch.get("batch_id")
            or metal_recipe_batch.get("batch_attempt_id") != batch_attempt.get("attempt_id")
            or metal_projection.get("output_revision_id")
            != batch_attempt.get("output_revision_id")
        ):
            raise RuntimeError("metal IR does not pin the exact Recipe/Batch/Output execution")

        candidates = _items(_json(client.get(f"/bulk-export-candidates?material_id={metal_id}")))
        neutral_source = next(
            candidate["source"]
            for candidate in candidates
            if candidate.get("source", {}).get("kind") == "neutral_material_json"
        )
        neutral_id = str(neutral_source["neutral_material_id"])
        neutral = _json(client.get(f"/neutral-materials/{neutral_id}"))
        if neutral["document"]["material_model_ir"]["model_family"] != (
            "isotropic_tabulated_plasticity"
        ):
            raise RuntimeError("clean demo selected Neutral JSON is not the metal family")
        neutral_recipe = neutral["document"]["sources"]["processing_recipe"]
        if (
            neutral_recipe.get("status") != "exact_revision"
            or neutral_recipe.get("reference", {}).get("id")
            != recipe.get("processing_recipe_id")
            or neutral_recipe.get("reference", {}).get("revision_id")
            != recipe.get("current_revision", {}).get("id")
        ):
            raise RuntimeError("metal Neutral JSON does not pin the exact Processing Recipe")
        neutral_download = client.get(f"/neutral-materials/{neutral_id}/download")
        neutral_download.raise_for_status()
        if (
            hashlib.sha256(neutral_download.content).hexdigest()
            != neutral["document_artifact"]["sha256"]
        ):
            raise RuntimeError("downloaded Neutral JSON digest does not match its Artifact")

        neutral_cards = _items(_json(client.get(f"/neutral-materials/{neutral_id}/solver-cards")))
        neutral_solvers = {
            str(card.get("target", {}).get("solver")): card for card in neutral_cards
        }
        if set(neutral_solvers) != {"abaqus", "openradioss"}:
            raise RuntimeError("clean demo Neutral JSON does not have both native cards")
        native_downloads: dict[str, str] = {}
        for solver, card in neutral_solvers.items():
            card_id = str(card["solver_card_id"])
            native = client.get(f"/neutral-solver-cards/{card_id}/download")
            native.raise_for_status()
            expected = card["current_revision"]["content"]["card_sha256"]
            actual = hashlib.sha256(native.content).hexdigest()
            if actual != expected:
                raise RuntimeError(f"downloaded {solver} card digest does not match")
            native_downloads[solver] = actual

        job = None
        for candidate_job in _items(_json(client.get("/export-jobs"))):
            selection_id = candidate_job.get("export_selection_id")
            if not isinstance(selection_id, str):
                continue
            candidate_selection = _json(client.get(f"/export-selections/{selection_id}"))
            candidate_content = candidate_selection.get("current_revision", {}).get("content", {})
            if (
                isinstance(candidate_content, Mapping)
                and candidate_content.get("selection_label")
                == "CMP clean demo complete governed transfer"
                and candidate_job.get("state") == "succeeded"
                and candidate_job.get("bundle_id")
            ):
                job = candidate_job
                break
        if job is None:
            raise RuntimeError("clean demo metal Bulk ZIP was not generated")
        bundle_id = str(job["bundle_id"])
        bundle = _json(client.get(f"/export-bundles/{bundle_id}"))
        authorization = _json(client.post(f"/export-bundles/{bundle_id}/download-authorizations"))
        parsed_base = httpx.URL(base_url)
        authority = parsed_base.host
        if parsed_base.port is not None:
            authority = f"{authority}:{parsed_base.port}"
        transfer_url = (
            f"{parsed_base.scheme}://{authority}/{str(authorization['transfer_url']).lstrip('/')}"
        )
        archive = httpx.get(
            transfer_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Artifact-Transfer-Token": authorization["transfer_token"],
            },
            timeout=60.0,
        )
        archive.raise_for_status()
        archive_digest = hashlib.sha256(archive.content).hexdigest()
        if f"sha256:{archive_digest}" != bundle["archive_sha256"]:
            raise RuntimeError("downloaded Bulk ZIP digest does not match its committed Bundle")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as package:
            names = set(package.namelist())
            if {"manifest.json", "checksums.sha256", "README.txt"} - names:
                raise RuntimeError(
                    "clean demo Bulk ZIP is missing its governed sidecars: "
                    + ", ".join(sorted(names))
                )
            manifest = json.loads(package.read("manifest.json"))

        result["clean_product_journey"] = {
            "catalog_record_id": catalog_record["record_id"],
            "catalog_subset_id": workflow_subset["subset_id"],
            "catalog_workflow_node_count": len(workflow_nodes) + 2,
            "test_data_document_id": document["test_data_document_id"],
            "metal_test_data_replicate_count": len(metal_replicates),
            "mapping_profile_id": profile["mapping_profile_id"],
            "processing_recipe_id": recipe["processing_recipe_id"],
            "processing_batch_id": batch["batch_id"],
            "processing_batch_attempt_id": batch_attempt["attempt_id"],
            "metal_model_schema_version": _content(metal_model)["model_schema_version"],
            "neutral_material_id": neutral_id,
            "neutral_solver_card_sha256": native_downloads,
            "bulk_bundle_id": bundle_id,
            "bulk_bundle_sha256": archive_digest,
            "bulk_component_count": len(manifest["components"]),
        }
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the clean public synthetic demo.")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("CMP_DEMO_API_BASE_URL", "http://127.0.0.1:8000/api/v1"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    result = verify_full_demo(_parser().parse_args(argv).api_base_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
