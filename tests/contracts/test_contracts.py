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


def test_optional_to_required_change_is_breaking() -> None:
    baseline = load_yaml(PROJECT_ROOT / "contracts/http/openapi.baseline.yaml")
    current = deepcopy(baseline)
    current["components"]["schemas"]["HealthResponse"]["properties"]["build"] = {
        "type": "string"
    }
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
    assert {"organization_id", "project_id", "content_hash"}.issubset(
        revision["required"]
    )
    assert "sha256" in etag["schema"]["pattern"]


def test_me_contract_requires_project_and_runtime_bearer_security() -> None:
    schema_path = PROJECT_ROOT / "contracts/identity/me-response.schema.json"
    failures = validate_example(
        schema_path,
        PROJECT_ROOT / "contracts/examples/negative/me-response-missing-project.json",
    )
    runtime = app.openapi()

    assert any("project_id" in failure for failure in failures)
    assert runtime["paths"]["/api/v1/me"]["get"]["operationId"] == "getMe"
    assert runtime["paths"]["/api/v1/me"]["get"]["security"] == [
        {"BearerAuth": []}
    ]
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
    assert source["paths"]["/api/v1/jobs"]["post"]["responses"]["202"][
        "headers"
    ]["Location"]["required"]


def test_packaged_runtime_job_spec_schema_matches_public_contract_exactly() -> None:
    public = json.loads(
        (PROJECT_ROOT / "contracts/jobs/job-spec.schema.json").read_text(
            encoding="utf-8"
        )
    )
    packaged = json.loads(
        files("cmp.modules.jobs.contracts")
        .joinpath("job-spec.schema.json")
        .read_text(encoding="utf-8")
    )

    assert packaged == public

