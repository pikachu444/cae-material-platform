import json
from pathlib import Path

from cmp.apps.api import app
from cmp.tools.contracts import load_yaml

PROJECT_ROOT = Path(__file__).parents[2]


def test_issue342_json_registration_contract_is_additive_and_runtime_bound() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    runtime = app.openapi()
    operations = {
        "/api/v1/catalog/json-record-formats": ("get", "listInstalledJsonRecordFormats"),
        "/api/v1/catalog/json-record-registrations:preview": (
            "post",
            "previewCatalogJsonRecordRegistration",
        ),
        "/api/v1/catalog/json-record-registrations/{preview_token}:save": (
            "post",
            "saveCatalogJsonRecordRegistration",
        ),
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source.json": (
            "get",
            "downloadExactJsonCatalogRecordSource",
        ),
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source.csv": (
            "get",
            "downloadExactJsonCatalogRecordSourceCsv",
        ),
        "/api/v1/catalog/records/{record_id}/revisions/{record_revision_id}/source-availability": (
            "get",
            "getExactJsonCatalogRecordSourceAvailability",
        ),
    }
    for path, (method, operation_id) in operations.items():
        assert source["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["operationId"] == operation_id
        assert runtime["paths"][path][method]["security"] == [{"BearerAuth": []}]

    contract_path = PROJECT_ROOT / "contracts/catalog/json-record-registration.schema.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["$id"].endswith("json-record-registration.schema.json")
    assert contract["$defs"]["SaveResponse"]["properties"]["lifecycle"] == {"const": "DRAFT"}
    assert contract["$defs"]["SaveResponse"]["properties"]["publication"]["properties"][
        "allowed"
    ] == {"const": False}
    assert "application_revision_id" in contract["$defs"]["InstalledFormat"]["required"]
    assert "source_sha256" in contract["$defs"]["TablePin"]["required"]
    assert "reference_pins" in contract["$defs"]["PreviewRequest"]["properties"]
    assert "domain_bindings" in contract["$defs"]["PreviewRequest"]["properties"]
    assert "domain_bindings" in contract["$defs"]["SaveRequest"]["properties"]
    assert "fields" in contract["$defs"]["FileResult"]["required"]
    assert "record_name" in contract["$defs"]["FileResult"]["properties"]
    assert "review_path" not in contract["$defs"]["SaveResponse"]["properties"]["records"][
        "items"
    ]["properties"]


def test_legacy_tabular_registration_routes_remain_documented_as_draft_only() -> None:
    source = load_yaml(PROJECT_ROOT / "contracts/http/openapi.yaml")
    for path in (
        "/api/v1/catalog/record-registrations:preview",
        "/api/v1/catalog/record-registrations:publish",
    ):
        description = source["paths"][path]["post"]["description"]
        assert "draft" in description.lower()
        assert "publication" in description.lower()
