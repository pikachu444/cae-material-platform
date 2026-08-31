import json
import re
from pathlib import Path

import yaml
from cmp import __version__
from cmp.modules.provenance.adapters.persistence.repository import (
    activity_table,
    agent_table,
    association_table,
    attribution_table,
    derivation_table,
    entity_table,
    generation_table,
    revision_table,
    usage_table,
)
from cmp.tools.user_guide import _documentation_classes

ROOT = Path(__file__).parents[2]
API_DOC = ROOT / "docs/architecture/api-events-jobs.md"
PROVENANCE_DOC = ROOT / "docs/domain/revision-and-provenance.md"
CANONICAL_DOC = ROOT / "docs/domain/canonical-domain-model.md"
OPENAPI = ROOT / "contracts/http/openapi.yaml"
ASYNCAPI = ROOT / "contracts/events/asyncapi.yaml"


def _normalize_operation(method: str, path: str) -> tuple[str, str]:
    path = path.removeprefix("/api/v1").split("?", maxsplit=1)[0]
    path = re.sub(r"\{[^}]+\}", "{}", path)
    return method, path


def test_api_events_guide_declares_its_authoritative_semantic_role() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    classes = _documentation_classes(ROOT)

    assert classes["docs/architecture/api-events-jobs.md"] == "authoritative"
    assert "Status: authoritative semantic guide" in text
    assert "전체 endpoint catalog를 복제하지 않는다" in text
    assert "contracts/http/openapi.yaml" in text
    assert "contracts/events/asyncapi.yaml" in text


def test_documented_http_version_and_operations_follow_openapi() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    openapi = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    documented_versions = set(re.findall(r"HTTP contract(?:는)? `([^`]+)`", text))
    operation_pattern = re.compile(
        r"\b(GET|POST|PUT|PATCH|DELETE) "
        r"((?:/api/v1)?/[A-Za-z0-9_{}:./?=-]+)"
    )
    documented = {
        _normalize_operation(method, path)
        for method, path in operation_pattern.findall(text)
    }
    contracted = {
        _normalize_operation(method.upper(), path)
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }

    assert documented_versions == {openapi["info"]["version"]} == {__version__}
    assert documented - contracted == set()


def test_current_event_catalog_matches_published_and_runtime_sources() -> None:
    text = API_DOC.read_text(encoding="utf-8")
    asyncapi = yaml.safe_load(ASYNCAPI.read_text(encoding="utf-8"))
    rows = {
        event_type: status
        for event_type, status in re.findall(
            r"^\| `(io\.cmp\.[^`]+)` \| `([^`]+)` \|", text, flags=re.MULTILINE
        )
    }
    expected = {
        "io.cmp.artifact.available.v1": "published-contract",
        "io.cmp.catalog.schema-definition-bundle.applied.v1": "published-contract",
        "io.cmp.exporting.solver-card-delivered.v1": "runtime-only-uncontracted",
    }
    published = {
        channel["address"] for channel in asyncapi["channels"].values()
    }
    emitter = (
        ROOT
        / "backend/src/cmp/modules/exporting/adapters/persistence/target_delivery_receipts.py"
    ).read_text(encoding="utf-8")
    stale_event_types = {
        "raw-asset.ingested.v1",
        "dataset.revision.created.v1",
        "qc.run.completed.v1",
        "statistics.run.completed.v1",
        "processing.run.completed.v1",
        "calibration.run.completed.v1",
        "material-model.revision.created.v1",
        "solver-card.generated.v1",
        "validation.run.completed.v1",
        "review.decision.recorded.v1",
        "release.published.v1",
        "release.superseded.v1",
        "plugin.package.activated.v1",
        "com.cmp.material-model.revision.created.v1",
    }

    assert rows == expected
    assert {event for event, status in rows.items() if status == "published-contract"} == published
    assert "io.cmp.exporting.solver-card-delivered.v1" in emitter
    assert "io.cmp.exporting.solver-card-delivered.v1" not in published
    assert all(event_type not in text for event_type in stale_event_types)


def test_provenance_pseudo_schema_tracks_application_persistence_columns() -> None:
    text = PROVENANCE_DOC.read_text(encoding="utf-8")
    blocks = {
        name: [
            column.strip()
            for column in body.replace("\n", " ").split(",")
            if column.strip()
        ]
        for name, body in re.findall(
            r"provenance\.(\w+)\(\s*(.*?)\s*\)", text, flags=re.DOTALL
        )
    }
    tables = {
        "entity": entity_table,
        "activity": activity_table,
        "agent": agent_table,
        "usage": usage_table,
        "generation": generation_table,
        "derivation": derivation_table,
        "association": association_table,
        "revision": revision_table,
        "attribution": attribution_table,
    }

    assert set(blocks) == set(tables)
    for name, table in tables.items():
        assert blocks[name] == list(table.c.keys()), name


def test_public_provenance_projection_is_distinct_from_persistence_evidence() -> None:
    text = PROVENANCE_DOC.read_text(encoding="utf-8")
    schema = json.loads(
        (ROOT / "contracts/provenance/provenance-entity-resource.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert "contracts/provenance/provenance-entity-resource.schema.json" in text
    assert schema["properties"]["reference"]["$ref"] == "#/$defs/entityReference"
    assert set(schema["$defs"]["entityReference"]["required"]) == {
        "kind",
        "type",
        "id",
        "sha256",
    }
    assert {"request_id", "trace_id"}.isdisjoint(schema["properties"])
    assert "request_id" in text and "trace_id" in text


def test_unimplemented_physical_material_batch_is_not_a_current_aggregate() -> None:
    text = CANONICAL_DOC.read_text(encoding="utf-8")

    assert not re.search(r"\bmaterial_batch(?:_revision)?\b", text)
    assert not re.search(r"\bbatch_input\b", text)
    assert "별도 physical `MaterialBatch` resource" in text
    assert "현재 구현되지 않았고 후속 범위로 남는다" in text
