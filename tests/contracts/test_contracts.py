from copy import deepcopy
from pathlib import Path

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
    assert runtime["paths"]["/api/v1/health"]["get"]["operationId"] == "getHealth"
    assert set(runtime["components"]["schemas"]["HealthResponse"]["required"]) == set(
        source["components"]["schemas"]["HealthResponse"]["required"]
    )

