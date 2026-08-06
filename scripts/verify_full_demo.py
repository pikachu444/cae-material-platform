"""Verify the clean three-family demo through protected HTTP resources."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import httpx

MATERIALS = {
    "CMP-DEMO-DP780": ("tabulated-plasticity-models", {"abaqus", "openradioss"}),
    "CMP-DEMO-POLYMER-PRONY": ("linear-viscoelastic-models", {"abaqus"}),
    "CMP-DEMO-ELASTOMER-OGDEN": ("ogden-prony-models", {"abaqus", "openradioss"}),
}
EXPECTED_SYNTHETIC_STATE_ROUTE = "Synthetic reference preparation; not for engineering use"
FORBIDDEN_SYNTHETIC_STATE_ROUTE = "Synthetic reference production route"
CANONICAL_RECIPE_KEY = "cmp_demo_tensile_cleanup"
CANONICAL_BATCH_LABEL = "CMP clean demo canonical JSON batch · 2025 hardening contract"
HARDENING_EQUATION_CONTRACT = "altair-material-modeler-2025-v1"
HARDENING_FAMILIES = ["voce", "swift", "hockett_sherby", "ghosh"]


class ProcessingLineageError(ValueError):
    """The model projection does not resolve to one exact Processing execution."""


@dataclass(frozen=True, slots=True)
class ProcessingContractExecutionIdentity:
    """The exact execution/output tuple currently required by the demo contract.

    The verifier uses every field.  The optional fields make the pure resolver useful for
    focused checks that only have the stable execution identities available.
    """

    recipe_id: str | None = None
    recipe_revision_id: str | None = None
    recipe_sha256: str | None = None
    batch_id: str | None = None
    batch_member_id: str | None = None
    batch_attempt_id: str | None = None
    batch_attempt_no: int | None = None
    output_id: str | None = None
    output_revision_id: str | None = None
    output_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingLineageResolution:
    """Resolved immutable lineage and its relationship to the current contract execution."""

    recipe_id: str
    recipe_revision_id: str
    recipe_sha256: str
    batch_id: str
    batch_member_id: str
    batch_attempt_id: str
    batch_attempt_no: int
    output_id: str
    output_revision_id: str
    output_sha256: str
    batch: Mapping[str, Any]
    attempt: Mapping[str, Any]
    output: Mapping[str, Any]
    is_current_contract_execution: bool
    is_immutable_predecessor: bool

    @property
    def is_predecessor(self) -> bool:
        """Compatibility alias for callers that use the shorter state name."""

        return self.is_immutable_predecessor


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProcessingLineageError(f"{field} must be a non-empty string")
    return value


def _required_attempt_no(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProcessingLineageError(f"{field} must be a positive integer")
    return value


def _normalise_sha256(value: object, *, field: str) -> str:
    digest = _required_text(value, field=field)
    return digest.removeprefix("sha256:")


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProcessingLineageError(f"{field} must be an object")
    return value


def _identity_value(
    identity: Mapping[str, Any],
    *,
    nested: Mapping[str, Any] | None,
    keys: Sequence[str],
) -> object | None:
    for key in keys:
        if key in identity:
            return cast(object, identity[key])
    if nested is not None:
        for key in keys:
            if key in nested:
                return cast(object, nested[key])
    return None


def _current_identity(
    value: ProcessingContractExecutionIdentity | Mapping[str, Any],
) -> ProcessingContractExecutionIdentity:
    if isinstance(value, ProcessingContractExecutionIdentity):
        return value
    identity = _mapping(value, field="current contract execution/output identity")
    recipe = next(
        (
            candidate
            for key in ("processing_recipe", "recipe")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    batch = next(
        (
            candidate
            for key in ("processing_batch", "batch")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    attempt = next(
        (
            candidate
            for key in ("batch_attempt", "attempt")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )
    output = next(
        (
            candidate
            for key in ("processing_output", "output")
            if isinstance((candidate := identity.get(key)), Mapping)
        ),
        None,
    )

    def optional_text(keys: Sequence[str], nested: Mapping[str, Any] | None) -> str | None:
        found = _identity_value(identity, nested=nested, keys=keys)
        return None if found is None else _required_text(found, field=keys[0])

    def optional_digest(keys: Sequence[str], nested: Mapping[str, Any] | None) -> str | None:
        found = _identity_value(identity, nested=nested, keys=keys)
        return None if found is None else _normalise_sha256(found, field=keys[0])

    attempt_no_value = _identity_value(
        identity,
        nested=attempt,
        keys=("batch_attempt_no", "attempt_no"),
    )
    if attempt_no_value is not None:
        attempt_no = _required_attempt_no(attempt_no_value, field="batch_attempt_no")
    else:
        attempt_no = None
    return ProcessingContractExecutionIdentity(
        recipe_id=optional_text(("recipe_id", "processing_recipe_id"), recipe),
        recipe_revision_id=optional_text(
            ("recipe_revision_id", "processing_recipe_revision_id"), recipe
        ),
        recipe_sha256=optional_digest(
            ("recipe_sha256", "processing_recipe_sha256"), recipe
        ),
        batch_id=optional_text(("batch_id", "processing_batch_id"), batch),
        batch_member_id=optional_text(("batch_member_id", "processing_batch_member_id"), batch),
        batch_attempt_id=optional_text(
            ("batch_attempt_id", "processing_batch_attempt_id", "attempt_id"), attempt
        ),
        batch_attempt_no=attempt_no,
        output_id=optional_text(("output_id", "processing_output_id"), output),
        output_revision_id=optional_text(
            ("output_revision_id", "processing_output_revision_id"), output
        ),
        output_sha256=optional_digest(
            ("output_sha256", "processing_output_sha256"), output
        ),
    )


def resolve_processing_projection_lineage(
    processing_projection: Mapping[str, Any],
    batch_responses: Sequence[Mapping[str, Any]],
    processing_output_responses: Sequence[Mapping[str, Any]],
    current_contract_execution: ProcessingContractExecutionIdentity | Mapping[str, Any],
) -> ProcessingLineageResolution:
    """Resolve a projection through one exact immutable Recipe/Batch/Output execution.

    Every lookup is fail-closed: missing, duplicate, mismatched, or non-successful records are
    rejected.  A resolved tuple is either the supplied current contract execution or a distinct
    immutable predecessor; a predecessor may not reuse any current revision/execution/output ID.
    """

    projection = _mapping(processing_projection, field="processing_projection")
    recipe_batch = _mapping(
        projection.get("recipe_batch"), field="processing_projection.recipe_batch"
    )
    processing_recipe = _mapping(
        recipe_batch.get("processing_recipe"),
        field="processing_projection.recipe_batch.processing_recipe",
    )
    recipe_id = _required_text(processing_recipe.get("id"), field="processing recipe id")
    recipe_revision_id = _required_text(
        processing_recipe.get("revision_id"), field="processing recipe revision id"
    )
    recipe_sha256 = _normalise_sha256(
        processing_recipe.get("sha256"), field="processing recipe sha256"
    )
    batch_id = _required_text(
        recipe_batch.get("processing_batch_id"), field="processing batch id"
    )
    batch_member_id = _required_text(
        recipe_batch.get("batch_member_id"), field="processing batch member id"
    )
    batch_attempt_id = _required_text(
        recipe_batch.get("batch_attempt_id"), field="processing batch attempt id"
    )
    batch_attempt_no = _required_attempt_no(
        recipe_batch.get("batch_attempt_no"), field="processing batch attempt no"
    )
    output_id = _required_text(projection.get("output_id"), field="processing output id")
    output_revision_id = _required_text(
        projection.get("output_revision_id"), field="processing output revision id"
    )
    output_sha256 = _normalise_sha256(
        projection.get("output_sha256"), field="processing output sha256"
    )

    matching_batches = [
        item
        for item in batch_responses
        if isinstance(item, Mapping) and item.get("batch_id") == batch_id
    ]
    if len(matching_batches) != 1:
        raise ProcessingLineageError(
            f"processing batch {batch_id} must resolve to exactly one response"
        )
    batch = matching_batches[0]
    if (
        batch.get("recipe_id") != recipe_id
        or batch.get("recipe_revision_id") != recipe_revision_id
        or _normalise_sha256(batch.get("recipe_sha256"), field="batch recipe sha256")
        != recipe_sha256
    ):
        raise ProcessingLineageError("processing batch recipe pin does not match the projection")

    members = batch.get("members")
    if not isinstance(members, list):
        raise ProcessingLineageError("processing batch has no member records")
    matching_members = [
        member
        for member in members
        if isinstance(member, Mapping) and member.get("member_id") == batch_member_id
    ]
    if len(matching_members) != 1:
        raise ProcessingLineageError(
            f"processing batch member {batch_member_id} must resolve to exactly one record"
        )

    attempts = batch.get("attempts")
    if not isinstance(attempts, list):
        raise ProcessingLineageError("processing batch has no attempt records")
    matching_attempts = [
        attempt
        for attempt in attempts
        if isinstance(attempt, Mapping)
        and attempt.get("attempt_id") == batch_attempt_id
        and attempt.get("member_id") == batch_member_id
    ]
    if len(matching_attempts) != 1:
        raise ProcessingLineageError(
            f"processing batch attempt {batch_attempt_id} must resolve to exactly one "
            "member attempt"
        )
    attempt = matching_attempts[0]
    if (
        attempt.get("status") != "succeeded"
        or attempt.get("attempt_no") != batch_attempt_no
        or attempt.get("output_id") != output_id
        or attempt.get("output_revision_id") != output_revision_id
    ):
        raise ProcessingLineageError(
            "processing batch attempt is not the successful exact projection output"
        )

    matching_outputs = [
        item
        for item in processing_output_responses
        if isinstance(item, Mapping) and item.get("processing_output_id") == output_id
    ]
    if len(matching_outputs) != 1:
        raise ProcessingLineageError(
            f"processing output {output_id} must resolve to exactly one response"
        )
    output = matching_outputs[0]
    output_revision = _mapping(
        output.get("current_revision"), field="processing output current revision"
    )
    if output_revision.get("id") != output_revision_id:
        raise ProcessingLineageError(
            "processing output current revision does not match the projection"
        )
    if (
        _normalise_sha256(output.get("output_sha256"), field="processing output sha256")
        != output_sha256
    ):
        raise ProcessingLineageError("processing output digest does not match the projection")

    current = _current_identity(current_contract_execution)
    resolved_values: dict[str, str | int] = {
        "recipe_id": recipe_id,
        "recipe_revision_id": recipe_revision_id,
        "recipe_sha256": recipe_sha256,
        "batch_id": batch_id,
        "batch_member_id": batch_member_id,
        "batch_attempt_id": batch_attempt_id,
        "batch_attempt_no": batch_attempt_no,
        "output_id": output_id,
        "output_revision_id": output_revision_id,
        "output_sha256": output_sha256,
    }
    current_values: dict[str, str | int] = {
        key: value
        for key, value in (
            ("recipe_id", current.recipe_id),
            ("recipe_revision_id", current.recipe_revision_id),
            ("recipe_sha256", current.recipe_sha256),
            ("batch_id", current.batch_id),
            ("batch_member_id", current.batch_member_id),
            ("batch_attempt_id", current.batch_attempt_id),
            ("batch_attempt_no", current.batch_attempt_no),
            ("output_id", current.output_id),
            ("output_revision_id", current.output_revision_id),
            ("output_sha256", current.output_sha256),
        )
        if value is not None
    }
    is_current = bool(current_values) and all(
        resolved_values[key] == value for key, value in current_values.items()
    )
    predecessor_identity_fields = (
        "recipe_revision_id",
        "batch_id",
        "batch_attempt_id",
        "output_id",
        "output_revision_id",
    )
    if not is_current and any(
        key in current_values and resolved_values[key] == current_values[key]
        for key in predecessor_identity_fields
    ):
        raise ProcessingLineageError(
            "immutable predecessor reuses a current recipe revision, batch, attempt, or "
            "output identity"
        )

    return ProcessingLineageResolution(
        recipe_id=recipe_id,
        recipe_revision_id=recipe_revision_id,
        recipe_sha256=recipe_sha256,
        batch_id=batch_id,
        batch_member_id=batch_member_id,
        batch_attempt_id=batch_attempt_id,
        batch_attempt_no=batch_attempt_no,
        output_id=output_id,
        output_revision_id=output_revision_id,
        output_sha256=output_sha256,
        batch=batch,
        attempt=attempt,
        output=output,
        is_current_contract_execution=is_current,
        is_immutable_predecessor=not is_current,
    )


# Keep the shorter name available to lightweight callers and focused tests.
resolve_processing_lineage = resolve_processing_projection_lineage


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


def _pending_model_review(
    client: httpx.Client, *, model: Mapping[str, Any], label: str
) -> Mapping[str, Any]:
    model_id = str(model["material_model_id"])
    revision = model.get("current_revision")
    if not isinstance(revision, Mapping):
        raise RuntimeError(f"{label} has no exact current model revision")
    revision_id = str(revision["id"])
    requests = _items(
        _json(
            client.get(
                "/review-requests?aggregate_type=modeling.material_model"
                f"&aggregate_id={model_id}&revision_id={revision_id}"
            )
        )
    )
    if len(requests) != 1:
        raise RuntimeError(f"{label} does not have exactly one pending review request")
    request = requests[0]
    if (
        request.get("aggregate_type") != "modeling.material_model"
        or request.get("aggregate_id") != model_id
        or request.get("revision_id") != revision_id
        or request.get("manifest_sha256") != revision.get("content_hash")
        or request.get("lifecycle_state") != "review"
        or request.get("decision") is not None
    ):
        raise RuntimeError(f"{label} review request is not pending for the exact model revision")
    return request


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
            state_content = _content(states[0])
            route = state_content.get("manufacturing_route")
            if material_code == "CMP-DEMO-DP780" and (
                route != EXPECTED_SYNTHETIC_STATE_ROUTE
                or route == FORBIDDEN_SYNTHETIC_STATE_ROUTE
            ):
                raise RuntimeError(
                    f"{material_code} has an invalid synthetic State preparation label"
                )
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

        elastomer = next(
            item
            for item in materials
            if _content(item).get("material_code") == "CMP-DEMO-ELASTOMER-OGDEN"
        )
        elastomer_id = str(elastomer["material_id"])
        elastomer_neutral = None
        for candidate in _items(
            _json(client.get(f"/bulk-export-candidates?material_id={elastomer_id}"))
        ):
            source = candidate.get("source")
            if not isinstance(source, Mapping) or source.get("kind") != "neutral_material_json":
                continue
            neutral_id = source.get("neutral_material_id")
            if not isinstance(neutral_id, str):
                continue
            candidate_neutral = _json(client.get(f"/neutral-materials/{neutral_id}"))
            model_ir = candidate_neutral.get("document", {}).get("material_model_ir", {})
            if (
                isinstance(model_ir, Mapping)
                and model_ir.get("model_family") == "hyperelastic"
                and model_ir.get("constitutive_model", {}).get("family") == "ogden_1"
            ):
                elastomer_neutral = candidate_neutral
                break
        if elastomer_neutral is None:
            raise RuntimeError("clean demo elastomer has no reviewed Ogden Neutral JSON")
        elastomer_sources = elastomer_neutral["document"]["sources"]
        elastomer_datasets = elastomer_sources.get("datasets")
        if not isinstance(elastomer_datasets, list) or len(elastomer_datasets) != 4:
            raise RuntimeError("elastomer Neutral JSON does not pin four exact Datasets")
        roles = [item.get("role") for item in elastomer_datasets if isinstance(item, Mapping)]
        modes = {
            str(item.get("test_mode")) for item in elastomer_datasets if isinstance(item, Mapping)
        }
        if (
            roles.count("calibration") != 3
            or roles.count("holdout") != 1
            or modes
            != {
                "uniaxial_tension",
                "planar_tension",
                "biaxial_tension",
            }
        ):
            raise RuntimeError("elastomer Neutral JSON roles or test modes are incomplete")
        selection = elastomer_neutral["document"]["candidate_selection"]
        run_id = str(selection["calibration_run_id"])
        family_candidate_id = str(selection["candidate_id"])
        elastomer_run = _json(client.get(f"/ogden-calibration-runs/{run_id}"))
        families = elastomer_run.get("family_candidates")
        if (
            elastomer_run.get("calibration_curve_count") != 3
            or elastomer_run.get("holdout_curve_count") != 1
            or elastomer_run.get("test_mode_count") != 3
            or elastomer_run.get("candidate_count") != 8
            or not isinstance(families, list)
            or {item.get("family") for item in families if isinstance(item, Mapping)}
            != {"neo_hookean", "mooney_rivlin", "yeoh", "ogden_1"}
        ):
            raise RuntimeError("elastomer calibration Run is not the complete multi-mode fit")
        diagnostics = _json(
            client.get(f"/hyperelastic-family-candidates/{family_candidate_id}/diagnostics")
        )
        diagnostic_points = diagnostics.get("points")
        if not isinstance(diagnostic_points, list) or len(diagnostic_points) != 52:
            raise RuntimeError("elastomer family Candidate does not preserve 52 diagnostics points")
        prony = elastomer_neutral["document"]["material_model_ir"].get("prony_overlay")
        if (
            not isinstance(prony, Mapping)
            or prony.get("status") != "exact_revision"
            or not isinstance(prony.get("terms"), list)
            or len(prony["terms"]) != 2
        ):
            raise RuntimeError("elastomer Neutral JSON lost its exact two-term Prony overlay")
        elastomer_neutral_id = str(elastomer_neutral["neutral_material_id"])
        elastomer_cards = _items(
            _json(client.get(f"/neutral-materials/{elastomer_neutral_id}/solver-cards"))
        )
        elastomer_native: dict[str, str] = {}
        for solver, keyword in (
            ("abaqus", b"*HYPERELASTIC, OGDEN, N=1"),
            ("openradioss", b"/MAT/LAW62"),
        ):
            card = next(
                (
                    item
                    for item in elastomer_cards
                    if item.get("target", {}).get("solver") == solver
                ),
                None,
            )
            if card is None:
                raise RuntimeError(f"elastomer Neutral JSON has no {solver} native card")
            native = client.get(f"/neutral-solver-cards/{card['solver_card_id']}/download")
            native.raise_for_status()
            if keyword not in native.content:
                raise RuntimeError(f"elastomer {solver} card is missing its native keyword")
            elastomer_native[solver] = hashlib.sha256(native.content).hexdigest()
        result["elastomer_modeling_journey"] = {
            "neutral_material_id": elastomer_neutral_id,
            "calibration_plan_id": elastomer_sources["calibration_plan"]["id"],
            "calibration_run_id": run_id,
            "family_candidate_id": family_candidate_id,
            "dataset_count": len(elastomer_datasets),
            "diagnostics_point_count": len(diagnostic_points),
            "prony_term_count": len(prony["terms"]),
            "neutral_solver_card_sha256": elastomer_native,
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
        polymer_members = polymer_batch.get("members")
        polymer_source = (
            polymer_members[0].get("source")
            if isinstance(polymer_members, list)
            and len(polymer_members) == 1
            and isinstance(polymer_members[0], Mapping)
            else None
        )
        if (
            not isinstance(polymer_members, list)
            or len(polymer_members) != 1
            or not isinstance(polymer_members[0], Mapping)
            or not isinstance(polymer_source, Mapping)
            or polymer_source.get("fit_decision") is None
            or polymer_source.get("workup_overrides") != []
            or polymer_output.get("fit_decision") != polymer_source.get("fit_decision")
            or polymer_output.get("workup_overrides") != polymer_source.get("workup_overrides")
        ):
            raise RuntimeError("polymer batch/output did not preserve explicit fit evidence")
        processed_model = next(
            (
                item
                for item in polymer_models
                if isinstance(_content(item).get("processing_promotion_evidence"), Mapping)
                and _content(item)["processing_promotion_evidence"]
                .get("processing_output", {})
                .get("id")
                == polymer_output.get("processing_output_id")
            ),
            None,
        )
        if processed_model is None:
            raise RuntimeError("clean demo polymer has no exact Processing-promoted IR")
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
            candidate_recipe = (
                candidate_neutral.get("document", {})
                .get("sources", {})
                .get("processing_recipe", {})
                .get("reference", {})
            )
            if (
                isinstance(selection, Mapping)
                and selection.get("kind") == "prony_processing_output_selection"
                and isinstance(candidate_recipe, Mapping)
                and candidate_recipe.get("id") == polymer_recipe.get("processing_recipe_id")
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

        dma_document = next(
            item
            for item in _items(_json(client.get("/test-data-documents")))
            if item.get("document_key") == "CMP-DEMO-POLYMER-DMA-JSON"
        )
        dma_profile = next(
            item
            for item in _items(_json(client.get("/mapping-profiles")))
            if item.get("content", {}).get("profile_key") == "polymer-dma-frequency"
        )
        dma_recipe = next(
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == "cmp_demo_polymer_dma_prony"
        )
        dma_batch = next(
            item
            for item in _items(_json(client.get("/common-processing-batches")))
            if item.get("label") == "CMP demo polymer DMA Prony batch"
            and item.get("recipe_revision_id") == dma_recipe.get("current_revision", {}).get("id")
        )
        if dma_batch.get("status") != "succeeded":
            raise RuntimeError("polymer DMA Processing Recipe batch did not succeed")
        dma_attempt = next(
            item
            for item in dma_batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        )
        dma_output = next(
            item
            for item in _items(_json(client.get("/processing-outputs")))
            if item.get("processing_output_id") == dma_attempt.get("output_id")
        )
        dma_members = dma_batch.get("members")
        dma_source = (
            dma_members[0].get("source")
            if isinstance(dma_members, list)
            and len(dma_members) == 1
            and isinstance(dma_members[0], Mapping)
            else None
        )
        if (
            not isinstance(dma_members, list)
            or len(dma_members) != 1
            or not isinstance(dma_members[0], Mapping)
            or not isinstance(dma_source, Mapping)
            or dma_source.get("fit_decision") is None
            or dma_source.get("workup_overrides") != []
            or dma_output.get("fit_decision") != dma_source.get("fit_decision")
            or dma_output.get("workup_overrides") != dma_source.get("workup_overrides")
        ):
            raise RuntimeError("DMA batch/output did not preserve explicit fit evidence")
        dma_model = next(
            (
                item
                for item in polymer_models
                if _content(item)
                .get("processing_promotion_evidence", {})
                .get("processing_output", {})
                .get("id")
                == dma_output.get("processing_output_id")
            ),
            None,
        )
        if dma_model is None:
            raise RuntimeError("clean demo polymer has no exact DMA-promoted IR")
        dma_content = _content(dma_model)
        dma_evidence = dma_content.get("processing_promotion_evidence", {})
        dma_terms = dma_content.get("terms")
        if (
            not isinstance(dma_evidence, Mapping)
            or dma_evidence.get("selected_term_count") != 2
            or not isinstance(dma_terms, list)
            or len(dma_terms) != 2
        ):
            raise RuntimeError("DMA IR does not preserve the joint storage/loss Prony selection")
        dma_neutral = None
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
                and selection.get("processing_output", {}).get("id")
                == dma_output.get("processing_output_id")
                and selection.get("selected_series")
                == "modulus.storage.prony.selected+modulus.loss.prony.selected"
            ):
                dma_neutral = candidate_neutral
                break
        if dma_neutral is None:
            raise RuntimeError("clean demo polymer has no DMA Neutral Material JSON")
        dma_sources = dma_neutral.get("document", {}).get("sources", {})
        dma_tests = dma_sources.get("datasets", []) if isinstance(dma_sources, Mapping) else []
        if (
            not isinstance(dma_tests, list)
            or len(dma_tests) != 1
            or dma_tests[0].get("test_mode") != "dma_frequency"
            or dma_sources.get("mapping_profile", {}).get("reference", {}).get("id")
            != dma_profile.get("mapping_profile_id")
        ):
            raise RuntimeError(
                "DMA Neutral JSON does not pin its exact test mode and Mapping Profile"
            )
        dma_cards = _items(
            _json(
                client.get(f"/neutral-materials/{dma_neutral['neutral_material_id']}/solver-cards")
            )
        )
        dma_native_cards: dict[str, dict[str, str]] = {}
        for solver, keyword in (
            ("abaqus", b"*VISCOELASTIC, TIME=PRONY"),
            ("openradioss", b"/VISC/LPRONY"),
        ):
            card = next(
                item for item in dma_cards if item.get("target", {}).get("solver") == solver
            )
            native = client.get(f"/neutral-solver-cards/{card['solver_card_id']}/download")
            native.raise_for_status()
            if keyword not in native.content:
                raise RuntimeError(f"DMA native card omits {solver} Prony data")
            dma_native_cards[solver] = {
                "solver_card_id": str(card["solver_card_id"]),
                "sha256": hashlib.sha256(native.content).hexdigest(),
            }
        result["polymer_dma_journey"] = {
            "test_data_document_id": dma_document["test_data_document_id"],
            "mapping_profile_id": dma_profile["mapping_profile_id"],
            "processing_recipe_id": dma_recipe["processing_recipe_id"],
            "processing_batch_id": dma_batch["batch_id"],
            "processing_output_id": dma_output["processing_output_id"],
            "material_model_id": dma_model["material_model_id"],
            "neutral_material_id": dma_neutral["neutral_material_id"],
            "selected_term_count": len(dma_terms),
            "solver_cards": dma_native_cards,
        }

        metal = next(
            item for item in materials if _content(item).get("material_code") == "CMP-DEMO-DP780"
        )
        metal_id = str(metal["material_id"])
        tables = _items(_json(client.get("/catalog/tables")))
        table = next(
            item for item in tables if _content(item).get("key") == "demo_material_records"
        )
        subsets = _items(_json(client.get(f"/catalog/tables/{table['table_id']}/subsets")))
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
        catalog_attributes = _items(
            _json(client.get(f"/catalog/tables/{table['table_id']}/attributes"))
        )
        attribute_keys = {
            str(item.get("attribute_definition_id")): _content(item).get("key")
            for item in catalog_attributes
        }
        projected = _json(
            client.post(
                "/catalog/records:search",
                json={
                    "table_id": table["table_id"],
                    "domain_binding_kind": "material",
                    "limit": 100,
                },
            )
        )
        for expected_code, expected_material in (
            ("CMP-DEMO-POLYMER-PRONY", polymer),
            ("CMP-DEMO-ELASTOMER-OGDEN", elastomer),
        ):
            projected_record = next(
                (
                    item
                    for item in _items(projected)
                    if _content(item).get("external_key") == expected_code
                ),
                None,
            )
            if not isinstance(projected_record, Mapping):
                raise RuntimeError(f"clean demo Catalog is missing {expected_code} projection")
            projected_binding = projected_record.get("domain_binding")
            if (
                not isinstance(projected_binding, Mapping)
                or projected_binding.get("kind") != "material"
                or projected_binding.get("object_id") != expected_material["material_id"]
            ):
                raise RuntimeError(f"clean demo Catalog binding does not pin {expected_code}")
            value_keys = {
                attribute_keys.get(str(value.get("attribute_definition_id")))
                for value in _content(projected_record).get("values", [])
                if isinstance(value, Mapping)
            }
            if not {
                "material_class",
                "provider",
                "evidence_source",
                "condition_summary",
            } <= value_keys:
                raise RuntimeError(f"clean demo {expected_code} projection lacks evidence fields")
        workflow = _json(
            client.get(
                f"/catalog/workflow-explorer/{catalog_record['record_id']}/revisions/"
                f"{catalog_revision['id']}?depth=5"
            )
        )
        workflow_nodes = workflow.get("nodes")
        if not isinstance(workflow_nodes, list) or len(workflow_nodes) < 6:
            raise RuntimeError("clean demo Workflow Explorer does not reach the Neutral revision")
        workflow_kinds = {
            item.get("domain_binding", {}).get("kind")
            for item in workflow_nodes
            if isinstance(item, Mapping)
        }
        if not {
            "test_data",
            "processing_output",
            "material_model",
            "neutral_material",
        } <= workflow_kinds:
            raise RuntimeError("clean demo Workflow Explorer omits linked curve/model evidence")
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
        recipes = [
            item
            for item in _items(_json(client.get("/common-processing-recipes")))
            if item.get("content", {}).get("recipe_key") == CANONICAL_RECIPE_KEY
        ]
        if len(recipes) != 1:
            raise RuntimeError("clean demo must expose exactly one canonical Processing Recipe")
        recipe = recipes[0]
        recipe_content = recipe.get("content")
        recipe_revision = recipe.get("current_revision")
        if (
            not isinstance(recipe_content, Mapping)
            or recipe_content.get("lifecycle_state") != "published"
            or not isinstance(recipe_revision, Mapping)
            or not isinstance(recipe_revision.get("id"), str)
            or not isinstance(recipe_revision.get("content_hash"), str)
        ):
            raise RuntimeError(
                "clean demo canonical Processing Recipe is not an exact published revision"
            )
        recipe_steps = recipe_content.get("steps")
        if (
            not isinstance(recipe_steps, list)
            or not recipe_steps
            or not isinstance(recipe_steps[-1], Mapping)
            or recipe_steps[-1].get("method_id") != "metal.hardening_fit_extrapolate"
            or not isinstance(recipe_steps[-1].get("options"), Mapping)
        ):
            raise RuntimeError("clean demo canonical Recipe has no final hardening step")
        hardening_options = recipe_steps[-1]["options"]
        if (
            hardening_options.get("equation_contract") != HARDENING_EQUATION_CONTRACT
            or hardening_options.get("families") != HARDENING_FAMILIES
        ):
            raise RuntimeError("clean demo canonical Recipe has the wrong hardening contract")
        all_batch_responses = _items(_json(client.get("/common-processing-batches")))
        canonical_batches = [
            item
            for item in all_batch_responses
            if (
                item.get("label") == CANONICAL_BATCH_LABEL
                and item.get("recipe_id") == recipe.get("processing_recipe_id")
                and item.get("recipe_revision_id") == recipe_revision.get("id")
                and item.get("recipe_sha256") == recipe_revision.get("content_hash")
            )
        ]
        if len(canonical_batches) != 1:
            raise RuntimeError(
                "clean demo must expose exactly one canonical Batch pinned to the current Recipe"
            )
        batch = canonical_batches[0]
        if batch.get("status") != "succeeded":
            raise RuntimeError("clean demo Processing Batch did not succeed")
        succeeded_attempts = [
            item
            for item in batch.get("attempts", [])
            if isinstance(item, Mapping) and item.get("status") == "succeeded"
        ]
        if len(succeeded_attempts) != 1:
            raise RuntimeError("clean demo canonical Batch must have exactly one succeeded attempt")
        batch_attempt = succeeded_attempts[0]
        all_processing_output_responses = _items(_json(client.get("/processing-outputs")))
        matching_metal_outputs = [
            item
            for item in all_processing_output_responses
            if item.get("processing_output_id") == batch_attempt.get("output_id")
        ]
        if len(matching_metal_outputs) != 1:
            raise RuntimeError("clean demo canonical Batch output must resolve exactly once")
        metal_output = matching_metal_outputs[0]
        metal_members = batch.get("members")
        metal_source = (
            metal_members[0].get("source")
            if isinstance(metal_members, list)
            and len(metal_members) == 1
            and isinstance(metal_members[0], Mapping)
            else None
        )
        metal_workup = (
            metal_source.get("workup_overrides") if isinstance(metal_source, Mapping) else None
        )
        metal_output_revision = metal_output.get("current_revision")
        if (
            not isinstance(metal_members, list)
            or len(metal_members) != 1
            or not isinstance(metal_members[0], Mapping)
            or not isinstance(metal_source, Mapping)
            or not isinstance(metal_workup, list)
            or len(metal_workup) != 1
            or metal_workup[0].get("kind") != "necking_boundary"
            or metal_source.get("fit_decision") is None
            or metal_output.get("fit_decision") != metal_source.get("fit_decision")
            or metal_output.get("workup_overrides") != metal_workup
            or batch_attempt.get("member_id") != metal_members[0].get("member_id")
            or batch_attempt.get("output_id") != metal_output.get("processing_output_id")
            or not isinstance(metal_output_revision, Mapping)
            or batch_attempt.get("output_revision_id") != metal_output_revision.get("id")
        ):
            raise RuntimeError("metal batch/output did not preserve fit and necking evidence")
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
        metal_review = _pending_model_review(
            client, model=metal_model, label="metal selected model"
        )
        if not isinstance(metal_output_revision, Mapping):
            raise RuntimeError("clean demo canonical Processing Output has no current revision")
        metal_output_sha256 = metal_output.get("output_sha256")
        if not isinstance(metal_output_sha256, str) or not metal_output_sha256:
            raise RuntimeError("clean demo canonical Processing Output has no output digest")
        current_contract = ProcessingContractExecutionIdentity(
            recipe_id=str(recipe["processing_recipe_id"]),
            recipe_revision_id=str(recipe_revision["id"]),
            recipe_sha256=str(recipe_revision["content_hash"]),
            batch_id=str(batch["batch_id"]),
            batch_member_id=str(metal_members[0]["member_id"]),
            batch_attempt_id=str(batch_attempt["attempt_id"]),
            batch_attempt_no=(
                int(batch_attempt["attempt_no"])
                if isinstance(batch_attempt.get("attempt_no"), int)
                and not isinstance(batch_attempt.get("attempt_no"), bool)
                else None
            ),
            output_id=str(metal_output["processing_output_id"]),
            output_revision_id=str(metal_output_revision["id"]),
            output_sha256=metal_output_sha256,
        )
        metal_lineage = resolve_processing_projection_lineage(
            metal_projection,
            all_batch_responses,
            all_processing_output_responses,
            current_contract,
        )
        metal_recipe_batch = metal_projection.get("recipe_batch")
        exact_metal_recipe = (
            metal_recipe_batch.get("processing_recipe")
            if isinstance(metal_recipe_batch, Mapping)
            else None
        )
        if (
            not isinstance(exact_metal_recipe, Mapping)
            or exact_metal_recipe.get("id") != metal_lineage.recipe_id
            or exact_metal_recipe.get("revision_id") != metal_lineage.recipe_revision_id
            or not isinstance(metal_recipe_batch, Mapping)
            or not isinstance(batch_attempt, Mapping)
            or metal_recipe_batch.get("processing_batch_id") != metal_lineage.batch_id
            or metal_recipe_batch.get("batch_attempt_id") != metal_lineage.batch_attempt_id
            or metal_projection.get("output_id") != metal_lineage.output_id
            or metal_projection.get("output_revision_id") != metal_lineage.output_revision_id
        ):
            raise RuntimeError("metal IR does not pin the exact Recipe/Batch/Output execution")
        if metal_lineage.is_immutable_predecessor:
            current_claims = {
                "recipe_revision_id": current_contract.recipe_revision_id,
                "batch_id": current_contract.batch_id,
                "batch_attempt_id": current_contract.batch_attempt_id,
                "output_id": current_contract.output_id,
                "output_revision_id": current_contract.output_revision_id,
            }
            predecessor_claims = {
                "recipe_revision_id": metal_lineage.recipe_revision_id,
                "batch_id": metal_lineage.batch_id,
                "batch_attempt_id": metal_lineage.batch_attempt_id,
                "output_id": metal_lineage.output_id,
                "output_revision_id": metal_lineage.output_revision_id,
            }
            if any(
                current_value is not None and predecessor_claims[key] == current_value
                for key, current_value in current_claims.items()
            ):
                raise RuntimeError(
                    "metal predecessor IR claims a current Recipe/Batch/Attempt/Output identity"
                )

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
        neutral_selection = neutral["document"].get("candidate_selection")
        neutral_output = (
            neutral_selection.get("processing_output")
            if isinstance(neutral_selection, Mapping)
            else None
        )
        neutral_output_sha256 = (
            neutral_selection.get("processing_output_sha256")
            if isinstance(neutral_selection, Mapping)
            else None
        )
        if (
            not isinstance(neutral_recipe, Mapping)
            or neutral_recipe.get("status") != "exact_revision"
            or neutral_recipe.get("reference", {}).get("id") != metal_lineage.recipe_id
            or neutral_recipe.get("reference", {}).get("revision_id")
            != metal_lineage.recipe_revision_id
            or not isinstance(neutral_output, Mapping)
            or neutral_output.get("id") != metal_lineage.output_id
            or neutral_output.get("revision_id") != metal_lineage.output_revision_id
            or not isinstance(neutral_output_sha256, str)
            or _normalise_sha256(
                neutral_output_sha256, field="neutral processing output sha256"
            )
            != metal_lineage.output_sha256
        ):
            raise RuntimeError(
                "metal Neutral JSON does not pin the exact resolved Processing Recipe/Output"
            )
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
            "review_request_id": metal_review["review_request_id"],
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
