import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from cmp import __version__
from cmp.apps.api import app
from cmp.tools.contracts import (
    detect_openapi_breaks,
    load_yaml,
    validate_contracts,
    validate_example,
)
from cmp.tools.generate_client import render_client
from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).parents[2]


def test_metal_fit_reference_assets_are_explicitly_lf_only() -> None:
    """Keep the independent v1 digest stable across checkout platforms."""

    attributes = (PROJECT_ROOT / ".gitattributes").read_text(encoding="utf-8")
    expected = (
        "fixtures/synthetic/metal-hardening-reference-v1.json text eol=lf",
        "fixtures/manifests/metal-hardening-reference-v1.yaml text eol=lf",
    )
    assert all(rule in attributes.splitlines() for rule in expected)
    for relative in (
        "fixtures/synthetic/metal-hardening-reference-v1.json",
        "fixtures/manifests/metal-hardening-reference-v1.yaml",
    ):
        value = (PROJECT_ROOT / relative).read_bytes()
        assert b"\r" not in value, relative


def test_all_contracts_and_examples_validate() -> None:
    assert validate_contracts(PROJECT_ROOT) == []


def test_curve_metadata_positive_and_negative_fixtures() -> None:
    schema = PROJECT_ROOT / "contracts/datasets/curve-channel-metadata.schema.json"
    for name in (
        "curve-channel-metadata.json",
        "curve-channel-metadata-scalar-deviation.json",
        "curve-channel-metadata-legacy-frequency.json",
    ):
        assert (
            validate_example(schema, PROJECT_ROOT / "contracts/examples/positive" / name)
            == []
        )
    for name in (
        "curve-channel-metadata-unpaired-band.json",
        "curve-channel-metadata-conflicting-source-count.json",
    ):
        assert validate_example(
            schema, PROJECT_ROOT / "contracts/examples/negative" / name
        )


def test_latest_revision_reference_fixture_is_rejected() -> None:
    failures = validate_example(
        PROJECT_ROOT / "contracts/jobs/job-spec.schema.json",
        PROJECT_ROOT / "contracts/examples/negative/job-spec-latest.json",
    )

    assert any("uuid" in failure for failure in failures)


def test_revision_metadata_rejects_latest_and_has_no_generic_content() -> None:
    schema_path = PROJECT_ROOT / "contracts/revisions/revision-metadata.schema.json"
    failures = validate_example(
        schema_path,
        PROJECT_ROOT / "contracts/examples/negative/revision-metadata-latest.json",
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert any("uuid" in failure for failure in failures)
    assert "content" not in schema["properties"]


def test_provenance_entity_examples_accept_revision_and_reject_moving_head() -> None:
    schema = PROJECT_ROOT / "contracts/provenance/provenance-entity-resource.schema.json"

    assert (
        validate_example(
            schema,
            PROJECT_ROOT / "contracts/examples/positive/provenance-entity.json",
        )
        == []
    )
    failures = validate_example(
        schema,
        PROJECT_ROOT / "contracts/examples/negative/provenance-entity-moving-head.json",
    )

    assert failures


def test_lineage_and_completeness_examples_enforce_bounded_gate_contract() -> None:
    lineage = PROJECT_ROOT / "contracts/provenance/provenance-lineage.schema.json"
    completeness = PROJECT_ROOT / "contracts/provenance/provenance-completeness.schema.json"

    assert (
        validate_example(
            lineage,
            PROJECT_ROOT / "contracts/examples/positive/provenance-lineage.json",
        )
        == []
    )
    assert (
        validate_example(
            completeness,
            PROJECT_ROOT / "contracts/examples/positive/provenance-completeness.json",
        )
        == []
    )
    assert validate_example(
        completeness,
        PROJECT_ROOT / "contracts/examples/negative/provenance-completeness-false-eligible.json",
    )


def test_optional_to_required_change_is_breaking() -> None:
    baseline = load_yaml(PROJECT_ROOT / "contracts/http/openapi.baseline.yaml")
    current = deepcopy(baseline)
    current["components"]["schemas"]["HealthResponse"]["properties"]["build"] = {"type": "string"}
    current["components"]["schemas"]["HealthResponse"]["required"].append("build")

    breaks = detect_openapi_breaks(baseline, current)

    assert breaks == ["schema HealthResponse: field 'build' became required"]


def test_generated_client_is_deterministic_and_current() -> None:
    generated = PROJECT_ROOT / "generated/python/cmp_api_client/client.py"
    rendered = render_client(PROJECT_ROOT / "contracts/http/openapi.yaml")

    assert generated.read_text(encoding="utf-8") == rendered


def test_runtime_openapi_matches_source_health_shape() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()

    assert "/api/v1/health" in runtime["paths"]
    assert source["info"]["version"] == runtime["info"]["version"] == __version__
    assert runtime["paths"]["/api/v1/health"]["get"]["operationId"] == "getHealth"
    assert set(runtime["components"]["schemas"]["HealthResponse"]["required"]) == set(
        source["components"]["schemas"]["HealthResponse"]["required"]
    )


def test_runtime_openapi_exposes_revision_etag_and_metadata_components() -> None:
    runtime = app.openapi()
    revision = runtime["components"]["schemas"]["RevisionMetadata"]
    etag = runtime["components"]["headers"]["RevisionETag"]

    assert "content" not in revision["properties"]
    assert {"organization_id", "project_id", "content_hash"}.issubset(revision["required"])
    assert "sha256" in etag["schema"]["pattern"]


def test_schema_definition_bundle_contract_and_runtime_expose_plan_apply_and_export() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/catalog/schema-definition-bundles:plan": (
            "post",
            "planCatalogSchemaDefinitionBundle",
        ),
        "/api/v1/catalog/schema-definition-bundles:apply": (
            "post",
            "applyCatalogSchemaDefinitionBundle",
        ),
        "/api/v1/catalog/schema-definition-bundle-applications/{application_id}": (
            "get",
            "getCatalogSchemaDefinitionBundleApplication",
        ),
        "/api/v1/catalog/schema-definition-bundles/{bundle_key}:export": (
            "get",
            "exportCatalogSchemaDefinitionBundle",
        ),
        "/api/v1/catalog/databases": ("get", "listConfigurableCatalogDatabases"),
        "/api/v1/catalog/profiles": ("get", "listConfigurableCatalogProfiles"),
        "/api/v1/catalog/publication:validate": (
            "post",
            "validateConfigurableCatalogPublication",
        ),
    }
    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    bundle_schema = PROJECT_ROOT / "contracts/catalog/schema-definition-bundle.schema.json"
    assert (
        validate_example(
            bundle_schema,
            PROJECT_ROOT / "contracts/examples/positive/schema-definition-bundle-one.json",
        )
        == []
    )
    assert (
        validate_example(
            bundle_schema,
            PROJECT_ROOT / "contracts/examples/positive/schema-definition-bundle-many.json",
        )
        == []
    )
    bundle_contract = json.loads(bundle_schema.read_text(encoding="utf-8"))
    positive_one = json.loads(
        (PROJECT_ROOT / "contracts/examples/positive/schema-definition-bundle-one.json").read_text(
            encoding="utf-8"
        )
    )
    trailing_separator = deepcopy(positive_one)
    trailing_separator["catalog"]["database"]["key"] = "synthetic_database_"
    assert list(
        Draft202012Validator(bundle_contract, format_checker=FormatChecker()).iter_errors(
            trailing_separator
        )
    )
    for keyword, value in (
        ("$id", "urn:cmp:catalog-schema:nested:1.0.0"),
        ("$schema", "https://json-schema.org/draft/2020-12/schema"),
    ):
        nested_scope = deepcopy(positive_one)
        nested_scope["record_schemas"][0]["schema"]["properties"]["active"][keyword] = value
        assert list(
            Draft202012Validator(bundle_contract, format_checker=FormatChecker()).iter_errors(
                nested_scope
            )
        )
    assert validate_example(
        bundle_schema,
        PROJECT_ROOT
        / "contracts/examples/negative/schema-definition-bundle-unsupported-version.json",
    )
    assert validate_example(
        bundle_schema,
        PROJECT_ROOT / "contracts/examples/negative/schema-definition-bundle-nested-id.json",
    )

    response = runtime["components"]["schemas"]["SchemaBundlePlanResponse"]
    assert {
        "source_artifact",
        "catalog_snapshot_fingerprint",
        "plan_fingerprint",
        "action_counts",
        "actions",
        "diagnostics",
        "mutations_applied",
        "delete_missing",
        "write_set",
    }.issubset(response["required"])
    projected = runtime["components"]["schemas"]["ProjectedCatalogResponse"]
    projected_names = {item["$ref"].rsplit("/", maxsplit=1)[-1] for item in projected["anyOf"]}
    assert projected_names == {
        "ProjectedAttributeResponse",
        "ProjectedDefinitionResponse",
        "ProjectedLayoutResponse",
        "ProjectedLinkTypeResponse",
        "ProjectedPlacementResponse",
        "ProjectedProfileResponse",
    }
    apply_request = json.loads(
        (
            PROJECT_ROOT
            / "contracts/catalog/schema-definition-bundle-application.schema.json"
        ).read_text(encoding="utf-8")
    )["$defs"]["ApplyRequest"]
    assert set(apply_request["required"]) == {
        "artifact_id",
        "artifact_sha256",
        "plan_fingerprint",
    }
    assert "actions" not in apply_request["properties"]
    assert "projected" not in apply_request["properties"]
    assert apply_request["properties"]["delete_missing"] == {
        "const": False,
        "default": False,
    }
    application_response = runtime["components"]["schemas"][
        "SchemaBundleApplicationResponse"
    ]
    assert {
        "source_artifact",
        "plan_fingerprint",
        "before_snapshot_fingerprint",
        "after_snapshot_fingerprint",
        "results",
        "delete_missing",
        "idempotency_key",
    }.issubset(application_response["required"])


def test_common_units_profiles_and_export_usage_match_runtime_contracts() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/unit-system": {"get": "getUnitSystem"},
        "/api/v1/unit-conversions": {"post": "convertUnitValue"},
        "/api/v1/unit-profiles": {
            "get": "listUnitProfiles",
            "post": "createUnitProfile",
        },
        "/api/v1/unit-profiles/{profile_id}": {"get": "getUnitProfile"},
        "/api/v1/unit-profiles/{profile_id}/revisions": {
            "post": "reviseUnitProfile"
        },
        "/api/v1/unit-profiles/{profile_id}/revisions/{revision_id}": {
            "get": "getUnitProfileRevision"
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = PROJECT_ROOT / "contracts/units/unit-resources.schema.json"
    assert (
        validate_example(
            schema_path,
            PROJECT_ROOT / "contracts/examples/positive/unit-conversion.json",
        )
        == []
    )
    assert validate_example(
        schema_path,
        PROJECT_ROOT / "contracts/examples/negative/unit-conversion-unsupported.json",
    )

    unit_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    runtime_components = runtime["components"]["schemas"]
    original_unit_text = unit_schema["$defs"]["OriginalUnitText"]["enum"]
    assert runtime["components"]["schemas"]["OriginalUnitTextInput"]["enum"] == (
        original_unit_text
    )
    assert runtime_components["UnitConversionRequest"]["properties"][
        "original_unit_string"
    ] == {"$ref": "#/components/schemas/OriginalUnitTextRequest"}
    assert runtime_components["OriginalUnitTextRequest"]["enum"] == original_unit_text
    assert unit_schema["$defs"]["UnitConversionRequest"]["properties"][
        "original_unit_string"
    ] == {"$ref": "#/$defs/OriginalUnitText"}
    assert unit_schema["$defs"]["CompatibilityUnitSystem"]["properties"][
        "production_default"
    ] == {"const": False}
    assert set(unit_schema["$defs"]["DimensionId"]["enum"]) == {
        "force_per_area",
        "length",
        "time",
        "force",
        "mass",
        "mass_per_volume",
        "temperature",
        "strain",
    }
    assert {"profile_id", "revision_id", "content_sha256"} == set(
        runtime_components["UnitProfilePinInput"]["required"]
    )
    assert {
        "location",
        "role",
        "quantity_semantics",
        "dimension",
        "unit_id",
    } == set(runtime_components["UnitApplicationResponse"]["required"])

    for relative, definition in (
        ("target-preview-resource.schema.json", "Response"),
        ("target-delivery-resource.schema.json", "Response"),
        ("neutral-hyperelastic-resources.schema.json", "CardResponse"),
    ):
        contract = json.loads(
            (PROJECT_ROOT / "contracts/exporting" / relative).read_text(encoding="utf-8")
        )
        assert {"unit_profile", "unit_applications"}.issubset(
            contract["$defs"][definition]["required"]
        )

    card_contract = json.loads(
        (
            PROJECT_ROOT
            / "contracts/exporting/neutral-hyperelastic-resources.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert "allOf" not in card_contract["$defs"]["CreateRequest"]
    assert "unit_profile" in card_contract["$defs"]["CreateRequest"]["properties"]
    assert card_contract["$defs"]["CardResponse"]["properties"]["current_revision"] == {
        "$ref": "#/$defs/CardRevision"
    }
    assert {"unit_profile", "unit_applications"} == set(
        card_contract["$defs"]["ProfileCardContent"]["required"]
    )
    assert {
        "urn:cmp:exporting:neutral-hyperelastic-card:1.0.0",
        "urn:cmp:exporting:neutral-hyperelastic-card:1.1.0",
        "urn:cmp:exporting:neutral-family-card:2.0.0",
        "urn:cmp:exporting:neutral-family-card:2.1.0",
    } == set(card_contract["$defs"]["CardRevision"]["properties"]["schema_id"]["enum"])


def test_configurable_record_contract_carries_live_search_and_binding_projection_fields() -> None:
    schema = json.loads(
        (
            PROJECT_ROOT
            / "contracts/catalog/configurable-catalog-record-resources.schema.json"
        ).read_text(encoding="utf-8")
    )
    definitions = schema["$defs"]
    request = definitions["RecordSearchRequest"]
    response = definitions["RecordResponse"]
    projection = definitions["DomainBindingProjection"]

    live_request_fields = {
        "record_id",
        "domain_binding_kind",
        "include_descendants",
        "sort_by",
        "sort_attribute_id",
        "sort_direction",
    }
    assert live_request_fields.issubset(request["properties"])
    assert request["required"] == ["table_id"]
    assert request["properties"]["sort_by"] == {
        "type": "string",
        "enum": ["name", "external_key", "attribute"],
        "default": "name",
    }
    assert request["properties"]["sort_direction"] == {
        "type": "string",
        "enum": ["ascending", "descending"],
        "default": "ascending",
    }

    assert response["properties"]["domain_binding"] == {
        "oneOf": [{"$ref": "#/$defs/DomainBindingProjection"}, {"type": "null"}]
    }
    assert projection["additionalProperties"] is False
    assert set(projection["required"]) == {
        "binding_id",
        "record_id",
        "record_revision_id",
        "kind",
        "object_id",
        "revision_id",
        "workbench_path",
    }

    runtime = app.openapi()["components"]["schemas"]
    assert live_request_fields.issubset(runtime["RecordSearchRequest"]["properties"])
    assert "domain_binding" in runtime["RecordResponse"]["properties"]


def test_shear_relaxation_vertical_contract_matches_runtime_operations() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/test-methods/reference-shear-relaxation": "post",
        "/api/v1/test-runs/reference-shear-relaxation": "post",
        "/api/v1/shear-relaxation-datasets": "post",
        "/api/v1/material-states/{material_state_id}/shear-relaxation-datasets": "get",
        "/api/v1/shear-relaxation-datasets/{dataset_id}/preview": "get",
    }
    for path, method in operations.items():
        assert path in source["paths"]
        assert source["paths"][path][method]["operationId"] == runtime["paths"][path][method][
            "operationId"
        ]


def test_test_context_contract_matches_runtime_operations() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/test-campaigns": {"get": "listCampaigns", "post": "createCampaign"},
        "/api/v1/instruments": {"get": "listInstruments", "post": "createInstrument"},
        "/api/v1/instruments/{instrument_id}/calibrations": {
            "get": "listCalibrations",
            "post": "createCalibration",
        },
        "/api/v1/test-conditions": {"get": "listConditions", "post": "createCondition"},
        "/api/v1/test-runs/{test_run_id}/context": {
            "get": "getRunContext",
            "post": "createRunContext",
        },
    }

    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]


def test_catalog_contract_and_runtime_expose_typed_material_state_property_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/materials": {"get": "listMaterials", "post": "createMaterial"},
        "/api/v1/materials/{material_id}": {"get": "getMaterial"},
        "/api/v1/materials/{material_id}/revisions": {
            "get": "listMaterialRevisions",
            "post": "reviseMaterial",
        },
        "/api/v1/materials/{material_id}/states": {"post": "createMaterialState"},
        "/api/v1/material-states/{material_state_id}/property-sets": {"post": "createPropertySet"},
        "/api/v1/property-sets/{property_set_id}/revisions": {"post": "revisePropertySet"},
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    catalog_contract = (PROJECT_ROOT / "contracts/catalog/catalog-resources.schema.json").read_text(
        encoding="utf-8"
    )
    assert '"density_kg_per_m3"' in catalog_contract
    assert '"youngs_modulus_pa"' in catalog_contract
    assert '"poisson_ratio"' in catalog_contract
    assert '"total_count"' in catalog_contract
    assert '"key"' not in catalog_contract
    assert '"value"' not in catalog_contract


def test_material_model_contract_and_runtime_expose_typed_reference_ir_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/material-states/{material_state_id}/material-models": {
            "get": "listMaterialModelsForState",
            "post": "createReferenceLinearElasticMaterialModel",
        },
        "/api/v1/material-models/{material_model_id}": {"get": "getMaterialModel"},
        "/api/v1/material-models/{material_model_id}/revisions": {
            "get": "listMaterialModelRevisions"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    modeling_contract = (
        PROJECT_ROOT / "contracts/modeling/reference-linear-elastic-resources.schema.json"
    ).read_text(encoding="utf-8")
    assert '"density_kg_per_m3"' in modeling_contract
    assert '"youngs_modulus_pa"' in modeling_contract
    assert '"poisson_ratio"' in modeling_contract
    assert '"source_yield_stress_pa"' in modeling_contract
    assert '"calibration_evidence"' in modeling_contract
    assert '"calibration_selection_revision_id"' in modeling_contract
    assert '"key"' not in modeling_contract
    assert '"attribute"' not in modeling_contract


def test_reference_calibration_contract_and_runtime_expose_pinned_typed_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/calibration-plans": {
            "post": "createReferenceLinearElasticCalibrationPlan",
            "get": "listCalibrationPlans",
        },
        "/api/v1/calibration-plans/{plan_id}": {
            "patch": "reviseReferenceLinearElasticCalibrationPlan",
            "get": "getCalibrationPlan",
        },
        "/api/v1/calibration-runs": {"post": "executeReferenceLinearElasticCalibration"},
        "/api/v1/calibration-runs/{run_id}": {"get": "getCalibrationRun"},
        "/api/v1/calibration-candidates/{candidate_id}/diagnostics-preview": {
            "get": "previewCalibrationCandidateDiagnostics"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = (
        PROJECT_ROOT
        / "contracts/modeling/reference-linear-elastic-calibration-resources.schema.json"
    )
    serialized = schema_path.read_text(encoding="utf-8")
    assert '"youngs_modulus_lower_bound_pa"' in serialized
    assert '"normalization_stress_scale_pa"' in serialized
    assert '"diagnostics_artifact_id"' in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized

    plan_content = runtime["components"]["schemas"]["ReferenceCalibrationPlanContentResponse"]
    candidate = runtime["components"]["schemas"]["CalibrationCandidateResponse"]
    revise = runtime["components"]["schemas"]["ReferenceCalibrationPlanReviseRequest"]
    assert {"selection_revision_id", "material_model_revision_id", "random_seed"}.issubset(
        plan_content["required"]
    )
    assert {"diagnostics_artifact_id", "candidate_sha256", "bound_sticking"}.issubset(
        candidate["required"]
    )
    assert "classification" not in revise["properties"]


def test_candidate_selection_contract_and_runtime_expose_human_acceptance_and_ir_promotion() -> (
    None
):
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/calibration-candidate-selections": {
            "post": "createReferenceCalibrationCandidateSelection",
            "get": "listCalibrationCandidateSelections",
        },
        "/api/v1/calibration-candidate-selections/{selection_id}": {
            "patch": "reviseReferenceCalibrationCandidateSelection",
            "get": "getCalibrationCandidateSelection",
        },
        "/api/v1/calibration-candidate-selections/{selection_id}/promote-material-model": {
            "post": "promoteSelectedReferenceCalibrationCandidate"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = (
        PROJECT_ROOT
        / "contracts/modeling/reference-calibration-candidate-selection-resources.schema.json"
    )
    serialized = schema_path.read_text(encoding="utf-8")
    assert '"selection_reason"' in serialized
    assert '"candidate_sha256"' in serialized
    assert '"accepted_by_human_for_reference_ir_promotion"' in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized

    content = runtime["components"]["schemas"]["CandidateSelectionContentResponse"]
    promotion = runtime["components"]["schemas"]["CandidateSelectionPromotionRequest"]
    assert {
        "selection_reason",
        "selection_decision",
        "domain_acceptance_status",
    }.issubset(content["required"])
    assert {
        "selection_revision_id",
        "expected_material_model_revision_id",
        "change_reason",
    }.issubset(promotion["required"])


def test_me_contract_requires_project_and_runtime_bearer_security() -> None:
    schema_path = PROJECT_ROOT / "contracts/identity/me-response.schema.json"
    failures = validate_example(
        schema_path,
        PROJECT_ROOT / "contracts/examples/negative/me-response-missing-project.json",
    )
    runtime = app.openapi()

    assert any("project_id" in failure for failure in failures)
    assert runtime["paths"]["/api/v1/me"]["get"]["operationId"] == "getMe"
    assert runtime["paths"]["/api/v1/me"]["get"]["security"] == [{"BearerAuth": []}]
    assert runtime["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"


def test_job_contract_and_runtime_expose_submit_read_cancel_and_retry() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/jobs": ("post", "submitJob"),
        "/api/v1/jobs/{job_id}": ("get", "getJob"),
        "/api/v1/jobs/{job_id}:cancel": ("post", "cancelJob"),
        "/api/v1/jobs/{job_id}:retry": ("post", "retryJob"),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]
    assert source["paths"]["/api/v1/jobs"]["post"]["responses"]["202"]["headers"]["Location"][
        "required"
    ]


def test_packaged_runtime_job_spec_schema_matches_public_contract_exactly() -> None:
    public = json.loads(
        (PROJECT_ROOT / "contracts/jobs/job-spec.schema.json").read_text(encoding="utf-8")
    )
    packaged = json.loads(
        files("cmp.modules.jobs.contracts")
        .joinpath("job-spec.schema.json")
        .read_text(encoding="utf-8")
    )

    assert packaged == public


def test_packaged_artifact_event_schema_matches_async_contract_exactly() -> None:
    public = json.loads(
        (PROJECT_ROOT / "contracts/events/artifact-available.schema.json").read_text(
            encoding="utf-8"
        )
    )
    packaged = json.loads(
        files("cmp.modules.jobs.contracts")
        .joinpath("artifact-available.schema.json")
        .read_text(encoding="utf-8")
    )

    assert packaged == public


def test_python_runner_contract_schemas_match_public_contracts_exactly() -> None:
    for name in ("job-spec.schema.json", "result-manifest.schema.json"):
        public = json.loads((PROJECT_ROOT / "contracts/jobs" / name).read_text(encoding="utf-8"))
        packaged = json.loads(
            files("cmp_plugin_sdk.contracts").joinpath(name).read_text(encoding="utf-8")
        )

        assert packaged == public


def test_upload_contract_and_runtime_expose_stream_complete_cancel_and_raw_asset() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/uploads": ("post", "createUploadSession"),
        "/api/v1/uploads/{upload_id}": ("get", "getUploadSession"),
        "/api/v1/uploads/{upload_id}/parts/{part_number}": ("put", "uploadPart"),
        "/api/v1/uploads/{upload_id}:complete": ("post", "completeUpload"),
        "/api/v1/uploads/{upload_id}:cancel": ("post", "cancelUpload"),
        "/api/v1/raw-assets/{raw_asset_id}": ("get", "getRawAsset"),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]
    assert source["paths"]["/api/v1/uploads"]["post"]["responses"]["201"]["headers"]["Location"][
        "required"
    ]


def test_solver_card_contract_and_runtime_expose_preflight_preview_and_download() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/exporters/reference-openradioss-elast/capabilities": (
            "get",
            "getReferenceOpenRadiossExporterCapabilities",
        ),
        "/api/v1/material-models/{material_model_id}/mapping-preflight": (
            "post",
            "preflightReferenceOpenRadiossMapping",
        ),
        "/api/v1/material-models/{material_model_id}/solver-cards": (
            "post",
            "createReferenceOpenRadiossSolverCard",
        ),
        "/api/v1/solver-cards/{solver_card_id}/preview": ("get", "previewSolverCard"),
        "/api/v1/solver-cards/{solver_card_id}/download": ("get", "downloadSolverCard"),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = PROJECT_ROOT / "contracts/exporting/reference-openradioss-resources.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    card = runtime["components"]["schemas"]["SolverCardContentResponse"]
    report = runtime["components"]["schemas"]["MappingReportResponse"]

    assert "postgresql.JSONB" not in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert "card_text" not in card["properties"]
    assert {"mapping_report_sha256", "card_sha256", "non_production"}.issubset(card["required"])
    assert {"items", "mapping_report_sha256", "exportable"}.issubset(report["required"])


def test_elastoplastic_multisolver_contract_exposes_processing_evidence_and_two_cards() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/material-states/{material_state_id}/tabulated-plasticity-models": {
            "get": "listReferenceTabulatedPlasticityModels",
            "post": "createReferenceTabulatedPlasticityModel",
        },
        "/api/v1/tabulated-plasticity-models/{material_model_id}": {
            "get": "getReferenceTabulatedPlasticityModel"
        },
        "/api/v1/tabulated-plasticity-models/{material_model_id}/hardening-curve": {
            "get": "getReferenceTabulatedPlasticityHardeningCurve"
        },
        "/api/v1/exporters/reference-elastoplastic/capabilities": {
            "get": "getReferenceElastoplasticExporterCapabilities"
        },
        "/api/v1/tabulated-plasticity-models/{material_model_id}/mapping-preflight": {
            "post": "preflightReferenceElastoplasticMapping"
        },
        "/api/v1/tabulated-plasticity-models/{material_model_id}/solver-cards": {
            "get": "listReferenceElastoplasticSolverCards",
            "post": "createReferenceElastoplasticSolverCard",
        },
        "/api/v1/elastoplastic-solver-cards/{solver_card_id}/preview": {
            "get": "previewReferenceElastoplasticSolverCard"
        },
        "/api/v1/elastoplastic-solver-cards/{solver_card_id}/download": {
            "get": "downloadReferenceElastoplasticSolverCard"
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    modeling = json.loads(
        (
            PROJECT_ROOT
            / "contracts/modeling/reference-tabulated-plasticity-resources.schema.json"
        ).read_text(encoding="utf-8")
    )
    exporting = json.loads(
        (
            PROJECT_ROOT
            / "contracts/exporting/reference-elastoplastic-resources.schema.json"
        ).read_text(encoding="utf-8")
    )
    modeling_text = json.dumps(modeling)
    exporting_text = json.dumps(exporting)
    model_content = runtime["components"]["schemas"]["TabulatedPlasticityContentResponse"]
    card_content = runtime["components"]["schemas"]["ElastoplasticCardContentResponse"]
    report = runtime["components"]["schemas"]["ElastoplasticMappingReportResponse"]

    assert {
        "source_point_count",
        "pre_yield_excluded_point_count",
        "post_necking_excluded_point_count",
        "necking_source_point_index",
        "applicability",
    }.issubset(model_content["required"])
    assert "card_text" not in card_content["properties"]
    assert "approximated" in report["properties"]["items"]["items"]["$ref"] or (
        "approximated" in exporting_text
    )
    assert '"openradioss"' in exporting_text and '"abaqus"' in exporting_text
    assert '"key"' not in modeling_text and '"value"' not in modeling_text
    assert '"key"' not in exporting_text and '"value"' not in exporting_text


def test_reference_tensile_contract_and_runtime_expose_typed_test_dataset_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/material-states/{material_state_id}/specimens": {
            "get": "listMaterialStateSpecimens",
            "post": "createSpecimen",
        },
        "/api/v1/test-methods/reference-uniaxial-tensile": {
            "post": "createReferenceTensileTestMethod"
        },
        "/api/v1/test-methods/reference-multiaxial-tension": {
            "post": "createReferenceMultiaxialTensionTestMethod"
        },
        "/api/v1/test-methods": {"get": "listTestMethods"},
        "/api/v1/test-runs": {"post": "createReferenceTensileTestRun"},
        "/api/v1/test-runs/{test_run_id}": {"get": "getTestRun"},
        "/api/v1/material-states/{material_state_id}/test-runs": {
            "get": "listMaterialStateTestRuns"
        },
        "/api/v1/datasets/reference-uniaxial-tensile:import": {
            "post": "importReferenceTensileDataset"
        },
        "/api/v1/datasets/{dataset_id}": {"get": "getDataset"},
        "/api/v1/datasets/{dataset_id}/revisions": {"get": "listDatasetRevisions"},
        "/api/v1/material-states/{material_state_id}/datasets": {
            "get": "listMaterialStateDatasets"
        },
        "/api/v1/dataset-revisions/{dataset_revision_id}/curve": {"get": "previewDatasetCurve"},
        "/api/v1/dataset-selections/reference-tensile-replicates": {
            "get": "listReferenceTensileReplicateSelections",
            "post": "createReferenceTensileReplicateSelection",
        },
        "/api/v1/dataset-selections/reference-tensile-replicates/{selection_id}": {
            "get": "getReferenceTensileReplicateSelection"
        },
        "/api/v1/dataset-selections/reference-tensile-replicates/{selection_id}/revisions": {
            "post": "reviseReferenceTensileReplicateSelection"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    for relative in (
        "contracts/testing/reference-tensile-resources.schema.json",
        "contracts/datasets/reference-tensile-resources.schema.json",
        "contracts/datasets/reference-tensile-replicate-selection-resources.schema.json",
    ):
        serialized = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert "postgresql.JSONB" not in serialized
        assert '"key"' not in serialized
        assert '"value"' not in serialized
    dataset_content = runtime["components"]["schemas"]["DatasetContentResponse"]
    assert {"raw_artifact_id", "data_artifact_id", "mapping_sha256", "channels"}.issubset(
        dataset_content["required"]
    )


def test_reference_tensile_revision_contracts_allow_typed_content_but_no_unknown_fields() -> None:
    metadata = {
        "id": "00000000-0000-0000-0000-000000000001",
        "aggregate_id": "00000000-0000-0000-0000-000000000002",
        "revision_no": 1,
        "based_on_revision_id": None,
        "schema_id": "urn:cmp:test:1.0.0",
        "schema_version": "1.0.0",
        "content_hash": "a" * 64,
        "created_at": "2026-07-14T00:00:00Z",
        "created_by": "00000000-0000-0000-0000-000000000003",
        "change_reason": "reference fixture",
        "organization_id": "00000000-0000-0000-0000-000000000004",
        "project_id": "00000000-0000-0000-0000-000000000005",
        "classification": "internal",
        "lifecycle_state": "draft",
    }
    checks = (
        (
            "contracts/testing/reference-tensile-resources.schema.json",
            "SpecimenRevision",
            {
                **metadata,
                "content": {
                    "material_id": "00000000-0000-0000-0000-000000000006",
                    "material_revision_id": "00000000-0000-0000-0000-000000000007",
                    "material_state_id": "00000000-0000-0000-0000-000000000008",
                    "material_state_revision_id": "00000000-0000-0000-0000-000000000009",
                    "specimen_code": "SP-001",
                    "orientation": None,
                    "preparation_note": None,
                },
            },
        ),
        (
            "contracts/datasets/reference-tensile-resources.schema.json",
            "DatasetRevision",
            {
                **metadata,
                "content": {
                    "test_run_id": "00000000-0000-0000-0000-000000000010",
                    "test_run_revision_id": "00000000-0000-0000-0000-000000000011",
                    "raw_asset_id": "00000000-0000-0000-0000-000000000012",
                    "raw_artifact_id": "00000000-0000-0000-0000-000000000013",
                    "data_artifact_id": "00000000-0000-0000-0000-000000000014",
                    "data_sha256": "b" * 64,
                    "representation": "raw",
                    "source_dataset_revision_id": None,
                    "processing_run_id": None,
                    "point_count": 2,
                    "mapping_sha256": "c" * 64,
                    "importer_id": "urn:cmp:datasets:reference-uniaxial-tensile-csv:1.0.0",
                    "importer_version": "1.0.0",
                    "reference_only": True,
                    "channels": [
                        {
                            "name": "engineering_strain",
                            "quantity_kind": "engineering_strain",
                            "original_column": "strain",
                            "original_unit": "1",
                            "normalized_unit": "1",
                            "axis_role": "independent",
                        },
                        {
                            "name": "engineering_stress",
                            "quantity_kind": "engineering_stress",
                            "original_column": "stress",
                            "original_unit": "MPa",
                            "normalized_unit": "Pa",
                            "axis_role": "dependent",
                        },
                    ],
                },
            },
        ),
    )

    for relative, definition, valid in checks:
        schema = json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
        validator = Draft202012Validator(
            {"$defs": schema["$defs"], "$ref": f"#/$defs/{definition}"},
            format_checker=FormatChecker(),
        )
        assert list(validator.iter_errors(valid)) == []
        assert list(validator.iter_errors({**valid, "unexpected": True}))


def test_reference_statistics_contract_and_runtime_expose_typed_pair_qc_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/statistical-plans/reference-tensile-pair": {
            "post": "createReferenceTensilePairStatisticalPlan"
        },
        "/api/v1/statistical-plans": {"get": "listStatisticalPlans"},
        "/api/v1/statistical-plans/{plan_id}": {"get": "getStatisticalPlan"},
        "/api/v1/statistical-plans/{plan_id}/revisions": {
            "post": "reviseReferenceTensilePairStatisticalPlan"
        },
        "/api/v1/statistical-runs/reference-tensile-pair": {
            "post": "executeReferenceTensilePairStatistics"
        },
        "/api/v1/statistical-runs/{run_id}": {"get": "getStatisticalRun"},
        "/api/v1/statistical-results/{result_id}": {"get": "getStatisticalResult"},
        "/api/v1/statistical-results/{result_id}/curve": {"get": "previewStatisticalResultCurve"},
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    serialized = (
        PROJECT_ROOT / "contracts/statistics/reference-tensile-pair-resources.schema.json"
    ).read_text(encoding="utf-8")
    runtime_schemas = runtime["components"]["schemas"]

    assert '"first_selection_revision_id"' in serialized
    assert '"second_selection_revision_id"' in serialized
    assert '"curve_grid_policy"' in serialized
    assert '"not_provided_reference_pair"' in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert {"sample_count", "qc_observations", "curve_artifact_id"}.issubset(
        runtime_schemas["StatisticalRunResponse"]["required"]
    )
    assert {"scalar", "curve_artifact_id", "curve_point_count"}.issubset(
        runtime_schemas["ReferenceTensilePairResultContentResponse"]["required"]
    )


def test_reference_outlier_contract_and_runtime_expose_append_only_human_scope_workflow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/outlier-detection-plans/reference-tensile-pair": {
            "post": "createReferenceTensilePairOutlierDetectionPlan"
        },
        "/api/v1/outlier-detection-plans": {"get": "listOutlierDetectionPlans"},
        "/api/v1/outlier-detection-plans/{detection_plan_id}": {"get": "getOutlierDetectionPlan"},
        "/api/v1/outlier-detection-plans/{detection_plan_id}/revisions": {
            "post": "reviseReferenceTensilePairOutlierDetectionPlan"
        },
        "/api/v1/outlier-detection-runs/reference-tensile-pair": {
            "post": "executeReferenceTensilePairOutlierDetection"
        },
        "/api/v1/outlier-detection-runs/{run_id}": {"get": "getOutlierDetectionRun"},
        "/api/v1/outlier-assessments/reference-tensile-pair": {
            "post": "createReferenceTensilePairOutlierAssessment"
        },
        "/api/v1/outlier-assessments/{assessment_id}": {"get": "getOutlierAssessment"},
        "/api/v1/outlier-scope-comparisons/reference-tensile-pair": {
            "get": "getReferenceTensilePairOutlierScopeComparison"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    serialized = (
        PROJECT_ROOT / "contracts/statistics/reference-tensile-outlier-resources.schema.json"
    ).read_text(encoding="utf-8")
    runtime_schemas = runtime["components"]["schemas"]

    assert '"automatic_exclusion": {"const": false}' in serialized
    assert '"review_required"' in serialized
    assert '"excluded_from_reference_analysis"' in serialized
    assert '"source_mutation": {"const": false}' in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert {"candidate_count", "candidates", "failure_code"}.issubset(
        runtime_schemas["OutlierDetectionRunResponse"]["required"]
    )
    assert {"assessment_history", "latest_assessment"}.issubset(
        runtime_schemas["OutlierScopeComparisonEntryResponse"]["required"]
    )


def test_reference_import_contract_and_runtime_keep_detection_and_human_approval_separate() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/imports:detect": {"post": "detectReferenceImport"},
        "/api/v1/import-detection-reports/{detection_report_id}": {
            "get": "getImportDetectionReport"
        },
        "/api/v1/import-mappings": {"post": "createReferenceImportMapping"},
        "/api/v1/import-mappings/{mapping_id}": {"get": "getImportMapping"},
        "/api/v1/import-mappings/{mapping_id}/revisions": {"post": "reviseReferenceImportMapping"},
        "/api/v1/imports": {"post": "executeReferenceImport"},
        "/api/v1/imports/{import_run_id}": {"get": "getImportRun"},
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    testing_contract = (
        PROJECT_ROOT / "contracts/testing/reference-import-resources.schema.json"
    ).read_text(encoding="utf-8")
    processing_contract = (
        PROJECT_ROOT / "contracts/processing/reference-import-resources.schema.json"
    ).read_text(encoding="utf-8")
    runtime_schemas = runtime["components"]["schemas"]

    assert '"needs_input"' in testing_contract
    assert '"human_confirmed"' in testing_contract
    assert '"reference_inline"' in processing_contract
    assert '"key"' not in testing_contract
    assert '"value"' not in testing_contract
    assert {"header_columns", "strain_suggestion", "stress_suggestion"}.issubset(
        runtime_schemas["ImportDetectionReportResponse"]["required"]
    )
    assert {"detection_report_id", "dataset_mapping_sha256", "approval_kind"}.issubset(
        runtime_schemas["ImportMappingContentResponse"]["required"]
    )
    assert {"import_mapping_revision_id", "mapping_sha256", "reference_only"}.issubset(
        runtime_schemas["ImportRunResponse"]["required"]
    )


def test_governed_tabular_import_contract_matches_runtime_operations() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/tabular-import-previews": {"post": "previewGovernedTabularImport"},
        "/api/v1/import-profiles": {
            "get": "listGovernedImportProfiles",
            "post": "createGovernedImportProfile",
        },
        "/api/v1/import-profiles/{profile_id}": {"get": "getGovernedImportProfile"},
        "/api/v1/import-profiles/{profile_id}/revisions": {
            "post": "reviseGovernedImportProfile"
        },
        "/api/v1/tabular-import-runs": {"post": "executeGovernedTabularImport"},
        "/api/v1/tabular-import-runs/{run_id}": {"get": "getGovernedTabularImportRun"},
        "/api/v1/governed-datasets/{dataset_id}": {"get": "getGovernedTabularDataset"},
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    contract = (
        PROJECT_ROOT / "contracts/datasets/governed-import-resources.schema.json"
    ).read_text(encoding="utf-8")
    assert all(name in contract for name in ("csv", "tsv", "xlsx", "needs_input"))
    assert all(
        name in contract
        for name in (
            "monotonic_tension",
            "monotonic_compression",
            "planar_tension",
            "biaxial_tension",
            "simple_shear",
            "shear_relaxation",
        )
    )
    assert '"key"' not in contract and '"value"' not in contract


def test_raw_asset_public_contract_never_exposes_internal_storage_key() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "contracts/artifacts/raw-asset-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    runtime = app.openapi()["components"]["schemas"]["RawAssetResponse"]

    assert "staging_object_key" not in schema["properties"]
    assert "storage_key" not in schema["properties"]
    assert "staging_object_key" not in runtime["properties"]
    assert "storage_key" not in runtime["properties"]


def test_content_artifact_contract_and_runtime_expose_scoped_streaming_download() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/artifacts/{artifact_id}": ("get", "getArtifact"),
        "/api/v1/artifacts/{artifact_id}:download-token": (
            "post",
            "issueArtifactDownloadToken",
        ),
        "/api/v1/artifacts/{artifact_id}/content": (
            "get",
            "downloadArtifactContent",
        ),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]
    parameters = source["paths"]["/api/v1/artifacts/{artifact_id}/content"]["get"]["parameters"]
    assert any(item.get("name") == "Artifact-Transfer-Token" for item in parameters)


def test_content_artifact_public_contract_never_exposes_object_key() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "contracts/artifacts/artifact-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    runtime = app.openapi()["components"]["schemas"]["ArtifactResponse"]

    for forbidden in ("storage_key", "staging_object_key", "final_object_key"):
        assert forbidden not in schema["properties"]
        assert forbidden not in runtime["properties"]


def test_provenance_contract_and_runtime_expose_read_only_entity_lookup() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/provenance/entities/by-reference": (
            "get",
            "findProvenanceEntityByReference",
        ),
        "/api/v1/provenance/entities/{entity_id}": (
            "get",
            "getProvenanceEntity",
        ),
        "/api/v1/provenance/entities/{entity_id}/lineage": (
            "get",
            "getProvenanceLineage",
        ),
        "/api/v1/provenance/entities/{entity_id}/impact": (
            "get",
            "getProvenanceImpact",
        ),
        "/api/v1/provenance/entities/{entity_id}/completeness": (
            "get",
            "getProvenanceCompleteness",
        ),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]
    assert all(
        method not in source["paths"][path]
        for path in operations
        for method in ("post", "put", "patch", "delete")
    )


def test_provenance_public_contract_hides_polymorphic_database_details() -> None:
    entity = json.loads(
        (PROJECT_ROOT / "contracts/provenance/provenance-entity-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    runtime = app.openapi()["components"]["schemas"]["ProvenanceEntityResponse"]
    lineage = json.loads(
        (PROJECT_ROOT / "contracts/provenance/provenance-lineage.schema.json").read_text(
            encoding="utf-8"
        )
    )
    completeness = json.loads(
        (PROJECT_ROOT / "contracts/provenance/provenance-completeness.schema.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = json.dumps({"entity": entity, "lineage": lineage, "completeness": completeness})
    runtime_schemas = app.openapi()["components"]["schemas"]

    assert "domain_ref_table" not in serialized
    assert "storage_key" not in serialized
    assert "edge_type" not in serialized
    assert set(runtime["required"]) == set(entity["required"])
    assert set(runtime_schemas["LineagePageResponse"]["required"]) == set(lineage["required"])
    assert set(runtime_schemas["ProvenanceCompletenessResponse"]["required"]) == set(
        completeness["required"]
    )


def test_audit_contract_and_runtime_expose_read_only_query_export_and_integrity() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/audit/events": "listAuditEvents",
        "/api/v1/audit/integrity": "getAuditIntegrity",
        "/api/v1/audit/export": "exportAuditSegment",
    }

    for path, operation_id in operations.items():
        assert set(source["paths"][path]) == {"get"}
        assert set(runtime["paths"][path]) == {"get"}
        assert source["paths"][path]["get"]["operationId"] == operation_id
        assert runtime["paths"][path]["get"]["operationId"] == operation_id
        assert runtime["paths"][path]["get"]["security"] == [{"BearerAuth": []}]


def test_audit_contract_has_no_raw_payload_secret_or_object_key() -> None:
    contract_dir = PROJECT_ROOT / "contracts/audit"
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(contract_dir.glob("*.schema.json"))
    ]
    integrity = json.loads(
        (contract_dir / "audit-integrity.schema.json").read_text(encoding="utf-8")
    )
    serialized = json.dumps(documents)
    runtime = app.openapi()["components"]["schemas"]

    assert '"payload"' not in serialized
    assert "storage_key" not in serialized
    assert "authorization" not in serialized
    assert set(runtime["AuditEventPageResponse"]["required"]) == {
        "events",
        "next_after_sequence",
    }
    assert set(runtime["AuditIntegrityResponse"]["required"]) == set(integrity["required"])
    assert "export_version" in runtime["AuditExportResponse"]["required"]


def test_plugin_contract_and_runtime_expose_registry_lifecycle() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/plugins/packages": ("post", "registerPluginPackage"),
        "/api/v1/plugins/packages/{package_id}": ("get", "getPluginPackage"),
        "/api/v1/plugins/packages/{package_id}:verify": (
            "post",
            "verifyPluginPackage",
        ),
        "/api/v1/plugins/packages/{package_id}:activate": (
            "post",
            "activatePluginPackage",
        ),
        "/api/v1/plugins/packages/{package_id}:revoke": (
            "post",
            "revokePluginPackage",
        ),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]
    assert source["paths"]["/api/v1/plugins/packages"]["post"]["responses"]["201"]["headers"][
        "Idempotent-Replay"
    ]["required"]


def test_packaged_runtime_plugin_manifest_matches_public_contract_exactly() -> None:
    public = json.loads(
        (PROJECT_ROOT / "contracts/plugins/plugin-manifest.schema.json").read_text(encoding="utf-8")
    )
    packaged = json.loads(
        files("cmp.modules.plugins.contracts")
        .joinpath("plugin-manifest.schema.json")
        .read_text(encoding="utf-8")
    )

    assert packaged == public


def test_runtime_plugin_request_and_resource_required_fields_match_public_schemas() -> None:
    runtime = app.openapi()["components"]["schemas"]
    registration = json.loads(
        (PROJECT_ROOT / "contracts/plugins/plugin-package-registration.schema.json").read_text(
            encoding="utf-8"
        )
    )
    resource = json.loads(
        (PROJECT_ROOT / "contracts/plugins/plugin-package-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(runtime["RegisterPluginPackageRequest"]["required"]) == set(registration["required"])
    assert set(runtime["PluginPackageResponse"]["required"]) == set(resource["required"])


def test_reference_validation_result_contract_and_runtime_expose_typed_interpretation() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/validation-runs/{run_id}:evaluate": (
            "post",
            "evaluateReferenceValidationRun",
        ),
        "/api/v1/validation-results/{validation_result_id}": ("get", "getValidationResult"),
        "/api/v1/validation-results/{validation_result_id}/curve": (
            "get",
            "previewValidationResultCurve",
        ),
    }

    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = (
        PROJECT_ROOT / "contracts/validation/reference-result-interpretation-resources.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    result = runtime["components"]["schemas"]["ReferenceValidationResultResponse"]
    health = runtime["components"]["schemas"]["NumericalHealthReportResponse"]
    curve = runtime["components"]["schemas"]["ValidationResultCurveResponse"]
    run = runtime["components"]["schemas"]["ValidationRunResponse"]

    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert "storage_key" not in serialized
    assert {"response_extraction", "numerical_health_report", "holdout_independence"}.issubset(
        result["required"]
    )
    assert {"output_complete", "finite_values", "strictly_increasing_strain"}.issubset(
        health["required"]
    )
    assert {"response_points", "comparison_points", "comparison_sampled"}.issubset(
        curve["required"]
    )
    assert "validation_result" in run["required"]


def test_review_contract_and_runtime_expose_digest_pinned_governance_flow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/review-requests": {
            "post": "createReviewRequest",
            "get": "listReviewRequests",
        },
        "/api/v1/review-requests/{review_request_id}": {"get": "getReviewRequest"},
        "/api/v1/review-requests/{review_request_id}/decisions": {"post": "createReviewDecision"},
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = PROJECT_ROOT / "contracts/governance/review-resources.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    runtime_schemas = runtime["components"]["schemas"]
    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert '"manifest_sha256"' in serialized
    assert '"required_role": {"const": "domain_reviewer"}' in serialized
    assert {"review_request_id", "manifest_sha256", "lifecycle_state", "decision"}.issubset(
        runtime_schemas["ReviewRequestResponse"]["required"]
    )
    assert {"expected_manifest_sha256", "decision", "reason"}.issubset(
        runtime_schemas["ReviewDecisionCreateRequest"]["required"]
    )


def test_release_contract_and_runtime_expose_digest_fixed_completeness_flow() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/releases": {"post": "createRelease", "get": "listReleases"},
        "/api/v1/releases/{release_id}": {"get": "getRelease"},
        "/api/v1/releases/{release_id}/download": {"get": "downloadRelease"},
        "/api/v1/releases/{release_id}/supersede": {"post": "supersedeRelease"},
        "/api/v1/releases/{release_id}/withdraw": {"post": "withdrawRelease"},
        "/api/v1/releases/{release_id}/usage": {"post": "recordReleaseUsage"},
        "/api/v1/releases/{release_id}/impact": {"get": "getReleaseImpact"},
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = PROJECT_ROOT / "contracts/governance/release-resources.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    assert '"key"' not in serialized
    assert '"value"' not in serialized
    assert "package_media_type" in serialized
    assert "provenance_snapshot_sha256" in serialized
    runtime_schemas = runtime["components"]["schemas"]
    assert {
        "material_model_id",
        "solver_card_id",
        "validation_result_id",
        "review_request_id",
        "provenance_snapshot_sha256",
    }.issubset(runtime_schemas["ReleaseCreateRequest"]["required"])
    assert runtime_schemas["ReleaseResponse"]["properties"]["channel"]["const"] == "reference"
    assert set(runtime_schemas["ReleaseResponse"]["properties"]["lifecycle_state"]["enum"]) == {
        "released",
        "superseded",
        "withdrawn",
    }
    assert {
        "predecessor_release_id",
        "successor_release_id",
        "usages",
        "transitions",
        "warning",
    }.issubset(runtime_schemas["ReleaseImpactResponse"]["required"])


def test_multi_replicate_statistics_contract_matches_runtime_and_declares_methods() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/replicate-statistical-plans": {
            "post": "createReferenceTensileReplicateStatisticalPlan",
            "get": "listReferenceTensileReplicateStatisticalPlans",
        },
        "/api/v1/replicate-statistical-plans/{plan_id}": {
            "get": "getReferenceTensileReplicateStatisticalPlan",
        },
        "/api/v1/replicate-statistical-runs": {
            "post": "executeReferenceTensileReplicateStatistics",
        },
        "/api/v1/replicate-statistical-runs/{run_id}": {
            "get": "getReferenceTensileReplicateStatisticalRun",
        },
        "/api/v1/replicate-statistical-results/{result_id}": {
            "get": "getReferenceTensileReplicateStatisticalResult",
        },
        "/api/v1/replicate-statistical-results/{result_id}/curve": {
            "get": "previewReferenceTensileReplicateStatisticalResultCurve",
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = (
        PROJECT_ROOT / "contracts/statistics/reference-tensile-replicate-resources.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    assert '"sample_count"' in serialized
    assert "exact_processed_grid_match_no_alignment" in serialized
    assert "student_t_95_two_sided" in serialized
    assert '"key"' not in serialized
    assert '"value"' not in serialized

    runtime_schemas = runtime["components"]["schemas"]
    assert {"sample_count", "members", "qc_observations"}.issubset(
        runtime_schemas["ReplicateStatisticalRunResponse"]["required"]
    )
    assert {
        "sample_standard_deviation",
        "median_absolute_deviation",
        "interquartile_range",
        "mean_confidence_interval_lower_95",
        "mean_confidence_interval_upper_95",
    }.issubset(runtime_schemas["ReplicateScalarStatisticsResponse"]["required"])


def test_linear_viscoelastic_contract_matches_runtime_and_is_typed() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/material-states/{material_state_id}/linear-viscoelastic-models": {
            "get": "listLinearViscoelasticModels",
            "post": "createLinearViscoelasticModel",
        },
        "/api/v1/linear-viscoelastic-models/{material_model_id}": {
            "get": "getLinearViscoelasticModel",
        },
        "/api/v1/linear-viscoelastic-models/{material_model_id}/response": {
            "get": "previewLinearViscoelasticResponse",
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema_path = (
        PROJECT_ROOT
        / "contracts/modeling/reference-linear-viscoelastic-resources.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    serialized = json.dumps(schema)
    assert "bulk_relaxation_status" in serialized
    assert "relaxation_time_s" in serialized
    assert "instantaneous" in serialized
    assert '"attribute"' not in serialized
    assert '"value"' not in serialized


def test_viscoelastic_master_curve_contract_matches_runtime_and_is_typed() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/viscoelastic-selections": {
            "post": "createViscoelasticSelection",
            "get": "listViscoelasticSelections",
        },
        "/api/v1/viscoelastic-selections/{selection_id}": {
            "get": "getViscoelasticSelection",
        },
        "/api/v1/processing-plans/viscoelastic-master-curve": {
            "post": "createViscoelasticMasterPlan",
        },
        "/api/v1/processing-runs/viscoelastic-master-curve": {
            "post": "executeViscoelasticMasterPlan",
        },
        "/api/v1/processing-runs/viscoelastic-master-curve/{run_id}": {
            "get": "getViscoelasticMasterRun",
        },
        "/api/v1/processing-runs/viscoelastic-master-curve/{run_id}/preview": {
            "get": "previewViscoelasticMasterRun",
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schemas = [
        json.loads(
            (
                PROJECT_ROOT / "contracts/datasets/viscoelastic-master-resources.schema.json"
            ).read_text(encoding="utf-8")
        ),
        json.loads(
            (
                PROJECT_ROOT
                / "contracts/processing/viscoelastic-master-curve-resources.schema.json"
            ).read_text(encoding="utf-8")
        ),
    ]
    serialized = json.dumps(schemas)
    for required in (
        "temperature_k",
        "outlier_status",
        "log10_a_t",
        "common_intersection_no_extrapolation",
        "time_divided_by_a_t",
    ):
        assert required in serialized


def test_scientific_profile_contract_matches_runtime_and_is_typed() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/scientific-profiles": {
            "post": "createScientificProfile",
            "get": "listScientificProfiles",
        },
        "/api/v1/scientific-profiles/{profile_id}": {
            "get": "getScientificProfile",
        },
        "/api/v1/scientific-profiles/{profile_id}/revisions": {
            "post": "reviseScientificProfile",
        },
    }
    for path, methods in operations.items():
        for method, operation_id in methods.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    schema = json.loads(
        (
            PROJECT_ROOT / "contracts/modeling/scientific-profile-resources.schema.json"
        ).read_text(encoding="utf-8")
    )
    serialized = json.dumps(schema)
    for required in (
        "sigma0_initial_pa",
        "term_count_max",
        "mu_initial_pa",
        "alpha_initial",
        "jacobian_covariance_or_not_estimable",
        "explicit_disjoint",
        "reference_unapproved",
    ):
        assert required in serialized
    assert '"attribute"' not in serialized
    assert '"value"' not in serialized


def test_operations_observability_contract_is_redacted_and_low_cardinality() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    path = "/api/v1/operations/observability"

    assert source["paths"][path]["get"]["operationId"] == "getOperationalObservability"
    assert runtime["paths"][path]["get"]["operationId"] == "getOperationalObservability"
    assert runtime["paths"][path]["get"]["security"] == [{"BearerAuth": []}]

    source_schema = source["components"]["schemas"]["OperationSeriesResponse"]
    runtime_schema = runtime["components"]["schemas"]["OperationSeriesResponse"]
    expected = {
        "method",
        "route",
        "status_family",
        "request_count",
        "error_count",
        "duration_sum_ms",
        "p95_upper_bound_ms",
    }
    assert set(source_schema["properties"]) == expected
    assert set(runtime_schema["properties"]) == expected
    serialized = json.dumps(runtime["components"]["schemas"]["OperationalSnapshotResponse"])
    for forbidden in ("url", "query", "header", "body", "token", "organization_id"):
        assert forbidden not in serialized


def test_target_preview_contract_matches_runtime_operation_and_typed_lineage() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    path = "/api/v1/exporting/target-previews"

    assert source["paths"][path]["post"]["operationId"] == "createExactTargetPreview"
    assert runtime["paths"][path]["post"]["operationId"] == "createExactTargetPreview"
    assert runtime["paths"][path]["post"]["security"] == [{"BearerAuth": []}]

    schema = json.loads(
        (PROJECT_ROOT / "contracts/exporting/target-preview-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = json.dumps(schema)
    for required in (
        "processing_output_sha256",
        "material_model_ir_revision_id",
        "neutral_material_revision_id",
        "solver_material_id",
        "acknowledgement_identity",
        "preview_only",
    ):
        assert required in serialized


def test_target_delivery_contract_matches_atomic_runtime_and_receipt_evidence() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    collection = "/api/v1/exporting/target-deliveries"
    member = "/api/v1/exporting/target-deliveries/{receipt_id}"

    assert source["paths"][collection]["post"]["operationId"] == "deliverExactTargetPreview"
    assert runtime["paths"][collection]["post"]["operationId"] == "deliverExactTargetPreview"
    assert runtime["paths"][collection]["post"]["security"] == [{"BearerAuth": []}]
    assert source["paths"][member]["get"]["operationId"] == "getTargetDeliveryReceipt"
    assert runtime["paths"][member]["get"]["operationId"] == "getTargetDeliveryReceipt"
    assert runtime["paths"][member]["get"]["security"] == [{"BearerAuth": []}]

    schema = json.loads(
        (PROJECT_ROOT / "contracts/exporting/target-delivery-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    preview_schema = json.loads(
        (PROJECT_ROOT / "contracts/exporting/target-preview-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )
    serialized = json.dumps(schema)
    for required in (
        "delivery_identity",
        "solver_card_revision_id",
        "native_sha256",
        "mapping_report_sha256",
        "mapping_statuses",
        "recorded_by",
        "receipt",
    ):
        assert required in serialized
    runtime_response = runtime["components"]["schemas"]["TargetDeliveryResponse"]
    runtime_target_ref = runtime_response["properties"]["target"]["$ref"]
    runtime_target_name = runtime_target_ref.rsplit("/", maxsplit=1)[-1]
    runtime_target = runtime["components"]["schemas"][runtime_target_name]
    resolved_target = preview_schema["$defs"]["ResolvedTarget"]
    assert runtime_target["additionalProperties"] is False
    assert set(runtime_target["required"]) == set(resolved_target["required"])
    for field in ("solver", "version", "unit_system", "solver_material_id", "material_name"):
        assert (
            runtime_target["properties"][field]["type"]
            == resolved_target["properties"][field]["type"]
        )
    assert runtime_target["properties"]["solver_material_id"]["type"] == "integer"
