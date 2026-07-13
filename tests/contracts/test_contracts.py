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

PROJECT_ROOT = Path(__file__).parents[2]


def test_all_contracts_and_examples_validate() -> None:
    assert validate_contracts(PROJECT_ROOT) == []


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
        "/api/v1/material-states/{material_state_id}/property-sets": {
            "post": "createPropertySet"
        },
        "/api/v1/property-sets/{property_set_id}/revisions": {
            "post": "revisePropertySet"
        },
    }

    for path, values in operations.items():
        for method, operation_id in values.items():
            assert source["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["operationId"] == operation_id
            assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    catalog_contract = (
        PROJECT_ROOT / "contracts/catalog/catalog-resources.schema.json"
    ).read_text(encoding="utf-8")
    assert '"density_kg_per_m3"' in catalog_contract
    assert '"youngs_modulus_pa"' in catalog_contract
    assert '"poisson_ratio"' in catalog_contract
    assert '"key"' not in catalog_contract
    assert '"value"' not in catalog_contract


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
    assert set(runtime["AuditIntegrityResponse"]["required"]) == set(
        integrity["required"]
    )
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
