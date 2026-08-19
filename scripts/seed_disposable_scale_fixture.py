from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from cmp.apps.demo_seed import DemoApi, DemoSeedError

FIXTURE_COUNT = 1_000
PAGE_SIZE = 50
FIXTURE_PREFIX = "CMP-SCALE-"
EXACT_LOOKUP_INDEX = 731
PROJECT_PATTERN = re.compile(r"^cmp-demo-test-[a-z0-9][a-z0-9-]{0,31}$")
DISPOSABLE_MARKER = "CMP_DISPOSABLE_PROJECT_NAME"
DESCRIPTION = "Disposable synthetic scale metadata; no curve or production use."
PROVIDERS = (
    "Disposable Lab A",
    "Disposable Lab B",
    "Disposable Lab C",
    "Disposable Lab D",
)
EVIDENCE_SOURCES = (
    "Synthetic metadata only",
    "Synthetic index only",
)
CONDITIONS = (
    "Ambient synthetic metadata",
    "Cold synthetic metadata",
    "Warm synthetic metadata",
)


@dataclass(frozen=True)
class ScaleRecordSpec:
    index: int
    code: str
    name: str
    material_class: str
    material_family: str
    provider: str
    evidence_source: str
    condition: str


def validate_disposable_context(project_name: str, marker: str | None) -> str:
    project = project_name.strip().lower()
    if not PROJECT_PATTERN.fullmatch(project):
        raise DemoSeedError(
            "scale fixture requires a project name matching cmp-demo-test-<unique-token>; "
            f"refusing project={project_name!r}"
        )
    if marker != project:
        raise DemoSeedError(
            f"scale fixture requires {DISPOSABLE_MARKER}={project}; "
            f"actual={marker!r}"
        )
    return project


def scale_record_spec(index: int) -> ScaleRecordSpec:
    if not 0 <= index < FIXTURE_COUNT:
        raise ValueError(f"scale fixture index must be in [0, {FIXTURE_COUNT}): {index}")
    if index < 500:
        material_class = "metal"
        material_family = "dual-phase steel"
    elif index < 800:
        material_class = "polymer"
        material_family = "linear viscoelastic polymer"
    else:
        material_class = "elastomer"
        material_family = "Ogden hyper-viscoelastic elastomer"
    code = f"{FIXTURE_PREFIX}{index:04d}"
    condition = CONDITIONS[index % len(CONDITIONS)]
    return ScaleRecordSpec(
        index=index,
        code=code,
        name=f"Disposable scale material {index:04d} · {material_class} · {condition}",
        material_class=material_class,
        material_family=material_family,
        provider=PROVIDERS[index % len(PROVIDERS)],
        evidence_source=EVIDENCE_SOURCES[0] if index % 5 < 3 else EVIDENCE_SOURCES[1],
        condition=condition,
    )


def fixture_specs() -> tuple[ScaleRecordSpec, ...]:
    return tuple(scale_record_spec(index) for index in range(FIXTURE_COUNT))


def _items(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = value.get("items")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise DemoSeedError("scale fixture API response did not contain an items list")
    return items


def _content(value: Mapping[str, Any]) -> Mapping[str, Any]:
    revision = value.get("current_revision")
    content = revision.get("content") if isinstance(revision, Mapping) else None
    if not isinstance(content, Mapping):
        raise DemoSeedError("scale fixture API response did not contain current revision content")
    return content


def _stable_id(value: Mapping[str, Any], key: str) -> str:
    identifier = value.get(key)
    if not isinstance(identifier, str) or not identifier:
        raise DemoSeedError(f"scale fixture API response did not contain {key}")
    return identifier


def _revision_id(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    identifier = revision.get("id") if isinstance(revision, Mapping) else None
    if not isinstance(identifier, str) or not identifier:
        raise DemoSeedError("scale fixture API response did not contain a current revision id")
    return identifier


def _revision_hash(value: Mapping[str, Any]) -> str:
    revision = value.get("current_revision")
    identifier = revision.get("content_hash") if isinstance(revision, Mapping) else None
    if not isinstance(identifier, str) or not identifier:
        raise DemoSeedError("scale fixture API response did not contain a content hash")
    return identifier


def _catalog_resources(
    api: DemoApi,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    table = next(
        (
            item
            for item in _items(api.get("/catalog/tables"))
            if _content(item).get("key") == "demo_material_records"
        ),
        None,
    )
    if table is None:
        raise DemoSeedError("full demo Catalog table demo_material_records is missing")
    table_id = _stable_id(table, "table_id")
    attributes = {
        str(_content(item).get("key")): item
        for item in _items(api.get(f"/catalog/tables/{table_id}/attributes"))
        if _content(item).get("key")
    }
    required = {
        "material_code",
        "material_class",
        "material_family",
        "provider",
        "evidence_source",
        "condition_summary",
        "grade",
    }
    missing = sorted(required - attributes.keys())
    if missing:
        raise DemoSeedError(
            "full demo Catalog table is missing scale fixture attributes: "
            + ", ".join(missing)
        )
    return table, attributes


def _text_value(
    attributes: Mapping[str, Mapping[str, Any]], key: str, value: str
) -> dict[str, str]:
    attribute = attributes[key]
    data_type = "discrete" if _content(attribute).get("data_type") == "discrete" else "text"
    return {
        "data_type": data_type,
        "attribute_definition_id": _stable_id(attribute, "attribute_definition_id"),
        "attribute_definition_revision_id": _revision_id(attribute),
        "value": value,
    }


def _record_values(
    attributes: Mapping[str, Mapping[str, Any]], spec: ScaleRecordSpec
) -> list[dict[str, str]]:
    return [
        _text_value(attributes, "material_code", spec.code),
        _text_value(attributes, "material_class", spec.material_class),
        _text_value(attributes, "material_family", spec.material_family),
        _text_value(attributes, "provider", spec.provider),
        _text_value(attributes, "evidence_source", spec.evidence_source),
        _text_value(attributes, "condition_summary", spec.condition),
        _text_value(attributes, "grade", f"Scale-{spec.index:04d}"),
    ]


def _create_scale_record(
    api: DemoApi,
    *,
    table_id: str,
    table_revision_id: str,
    attributes: Mapping[str, Mapping[str, Any]],
    spec: ScaleRecordSpec,
) -> str:
    try:
        material = api.post(
            "/materials",
            {
                "classification": "internal",
                "content": {
                    "name": spec.name,
                    "material_code": spec.code,
                    "material_family": spec.material_family,
                    "material_class": spec.material_class,
                    "description": DESCRIPTION,
                },
                "change_reason": "Create disposable synthetic scale-search metadata.",
            },
        )
        material_id = _stable_id(material, "material_id")
        material_revision_id = _revision_id(material)
        record = api.post(
            f"/catalog/tables/{table_id}/records",
            {
                "classification": "internal",
                "content": {
                    "table_revision_id": table_revision_id,
                    "name": spec.name,
                    "external_key": spec.code,
                    "description": DESCRIPTION,
                    "folder_id": None,
                    "folder_revision_id": None,
                    "values": _record_values(attributes, spec),
                },
                "change_reason": "Create disposable metadata-only Catalog scale record.",
            },
        )
        record_id = _stable_id(record, "record_id")
        record_revision_id = _revision_id(record)
        api.post(
            f"/catalog/records/{record_id}/revisions/{record_revision_id}/domain-binding",
            {
                "kind": "material",
                "object_id": material_id,
                "revision_id": material_revision_id,
            },
        )
    except DemoSeedError as exc:
        raise DemoSeedError(f"scale fixture record {spec.code} failed: {exc}") from exc
    return spec.code


def _search(
    api: DemoApi,
    *,
    table_id: str,
    text: str,
    offset: int = 0,
    limit: int = PAGE_SIZE,
    facet_attribute_ids: Sequence[str] = (),
) -> dict[str, Any]:
    return api.post(
        "/catalog/records:search",
        {
            "table_id": table_id,
            "text": text,
            "discrete_filters": [],
            "number_filters": [],
            "facet_attribute_ids": list(facet_attribute_ids),
            "offset": offset,
            "limit": limit,
            "domain_binding_kind": "material",
            "sort_by": "external_key",
            "sort_direction": "ascending",
        },
    )


def _ensure_exact_lookup_publication(
    api: DemoApi,
    reviewer_api: DemoApi,
    record: Mapping[str, Any],
) -> None:
    """Approve only the representative exact-lookup record revision."""

    record_id = _stable_id(record, "record_id")
    revision_id = _revision_id(record)
    manifest_sha256 = _revision_hash(record)
    aggregate_type = "catalog.configurable_record"
    requests = _items(
        api.get(
            "/review-requests?aggregate_type="
            f"{aggregate_type}&aggregate_id={record_id}&revision_id={revision_id}&limit=20"
        )
    )
    if len(requests) > 1:
        raise DemoSeedError("scale fixture exact record has duplicate revision reviews")
    if requests:
        request = requests[0]
        if request.get("manifest_sha256") != manifest_sha256:
            raise DemoSeedError("scale fixture exact record review pins a stale manifest")
        decision = request.get("decision")
        if decision is not None and (
            not isinstance(decision, Mapping) or decision.get("decision") != "approved"
        ):
            raise DemoSeedError(
                "scale fixture exact record review has a non-approved decision"
            )
    else:
        request = api.post(
            "/review-requests",
            {
                "classification": "internal",
                "aggregate_type": aggregate_type,
                "aggregate_id": record_id,
                "revision_id": revision_id,
                "manifest_sha256": manifest_sha256,
                "reason": (
                    "Expose one disposable synthetic exact-lookup record "
                    "for browser verification."
                ),
            },
        )
    if request.get("decision") is None:
        reviewer_api.post(
            f"/review-requests/{_stable_id(request, 'review_request_id')}/decisions",
            {
                "expected_manifest_sha256": manifest_sha256,
                "decision": "approved",
                "reason": "Approve only the disposable exact-lookup sample revision.",
            },
        )


def _publish_exact_lookup_sample(
    api: DemoApi,
    reviewer_api: DemoApi,
    *,
    table_id: str,
) -> None:
    exact_spec = scale_record_spec(EXACT_LOOKUP_INDEX)
    response = _search(api, table_id=table_id, text=exact_spec.code, limit=10)
    records = _items(response)
    if response.get("total_count") != 1 or len(records) != 1:
        raise DemoSeedError(
            "scale fixture exact-lookup sample did not resolve before publication"
        )
    _ensure_exact_lookup_publication(api, reviewer_api, records[0])


def _facet_counts(
    response: Mapping[str, Any], attribute_id: str
) -> dict[str, int]:
    facets = response.get("facets")
    if not isinstance(facets, list):
        raise DemoSeedError("scale fixture search did not return facets")
    result: dict[str, int] = {}
    for facet in facets:
        if not isinstance(facet, Mapping) or facet.get("attribute_definition_id") != attribute_id:
            continue
        value = facet.get("value")
        count = facet.get("count")
        if not isinstance(value, str) or not isinstance(count, int):
            raise DemoSeedError("scale fixture search returned an invalid facet bucket")
        result[value] = count
    return result


def verify_scale_fixture(
    api: DemoApi,
    *,
    table: Mapping[str, Any],
    attributes: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    table_id = _stable_id(table, "table_id")
    specs = fixture_specs()
    facet_keys = ("material_class", "provider", "evidence_source")
    facet_ids = tuple(
        _stable_id(attributes[key], "attribute_definition_id") for key in facet_keys
    )
    first_page = _search(
        api,
        table_id=table_id,
        text=FIXTURE_PREFIX,
        facet_attribute_ids=facet_ids,
    )
    if first_page.get("total_count") != FIXTURE_COUNT:
        raise DemoSeedError(
            "scale fixture search count mismatch: "
            f"expected={FIXTURE_COUNT}, actual={first_page.get('total_count')}"
        )

    records: list[dict[str, Any]] = []
    for offset in range(0, FIXTURE_COUNT, PAGE_SIZE):
        page = first_page if offset == 0 else _search(
            api,
            table_id=table_id,
            text=FIXTURE_PREFIX,
            offset=offset,
        )
        items = _items(page)
        if page.get("offset") != offset or page.get("limit") != PAGE_SIZE:
            raise DemoSeedError(
                "scale fixture pagination metadata mismatch: "
                f"offset={page.get('offset')}, limit={page.get('limit')}"
            )
        if len(items) != PAGE_SIZE:
            raise DemoSeedError(
                f"scale fixture page at offset {offset} returned {len(items)} records"
            )
        records.extend(items)

    expected_codes = [spec.code for spec in specs]
    actual_codes = [str(_content(record).get("external_key")) for record in records]
    if actual_codes != expected_codes:
        raise DemoSeedError("scale fixture external keys are not the deterministic 0000-0999 set")
    material_bindings = [record.get("domain_binding") for record in records]
    if any(
        not isinstance(binding, Mapping) or binding.get("kind") != "material"
        for binding in material_bindings
    ):
        raise DemoSeedError("every scale fixture Catalog record must pin a Material revision")
    material_ids = {
        str(binding.get("object_id"))
        for binding in material_bindings
        if isinstance(binding, Mapping)
    }
    if len(material_ids) != FIXTURE_COUNT:
        raise DemoSeedError("scale fixture Material bindings are not one-to-one")
    curve_values = [
        value
        for record in records
        for value in _content(record).get("values", [])
        if isinstance(value, Mapping) and value.get("data_type") == "curve"
    ]
    if curve_values:
        raise DemoSeedError("scale fixture records must remain metadata-only without curve copies")

    expected_facets = {
        "material_class": dict(Counter(spec.material_class for spec in specs)),
        "provider": dict(Counter(spec.provider for spec in specs)),
        "evidence_source": dict(Counter(spec.evidence_source for spec in specs)),
    }
    actual_facets = {
        key: _facet_counts(first_page, attribute_id)
        for key, attribute_id in zip(facet_keys, facet_ids, strict=True)
    }
    if actual_facets != expected_facets:
        raise DemoSeedError(
            f"scale fixture facet counts differ: expected={expected_facets}, actual={actual_facets}"
        )

    exact_spec = scale_record_spec(EXACT_LOOKUP_INDEX)
    exact = _search(api, table_id=table_id, text=exact_spec.code, limit=10)
    exact_items = _items(exact)
    if exact.get("total_count") != 1 or len(exact_items) != 1:
        raise DemoSeedError("scale fixture exact lookup did not return exactly one record")
    exact_record = exact_items[0]
    exact_binding = exact_record.get("domain_binding")
    if not isinstance(exact_binding, Mapping):
        raise DemoSeedError("scale fixture exact lookup did not retain its Material binding")
    detail = api.get(f"/materials/{exact_binding['object_id']}")
    material = detail.get("material")
    if (
        not isinstance(material, Mapping)
        or _content(material).get("material_code") != exact_spec.code
        or _revision_id(material) != exact_binding.get("revision_id")
    ):
        raise DemoSeedError(
            "scale fixture exact lookup did not resolve its pinned Material revision"
        )
    for collection in ("states", "property_sets"):
        value = detail.get(collection)
        if value not in (None, []):
            raise DemoSeedError(
                f"metadata-only scale fixture Material unexpectedly has {collection}"
            )

    empty = _search(api, table_id=table_id, text=f"{FIXTURE_PREFIX}NOT-FOUND", limit=10)
    if empty.get("total_count") != 0 or _items(empty):
        raise DemoSeedError("scale fixture empty lookup returned records")

    representative = _search(api, table_id=table_id, text="CMP-DEMO-DP780", limit=20)
    representative_record = next(
        (
            item
            for item in _items(representative)
            if _content(item).get("external_key") == "CMP-DEMO-DP780"
        ),
        None,
    )
    representative_curves = (
        [
            value
            for value in _content(representative_record).get("values", [])
            if isinstance(value, Mapping) and value.get("data_type") == "curve"
        ]
        if representative_record is not None
        else []
    )
    if not representative_curves:
        raise DemoSeedError("existing DP780 representative curve record is missing")

    return {
        "record_count": FIXTURE_COUNT,
        "material_count": len(material_ids),
        "page_size": PAGE_SIZE,
        "page_count": FIXTURE_COUNT // PAGE_SIZE,
        "facet_counts": actual_facets,
        "scale_curve_values": 0,
        "representative_record": "CMP-DEMO-DP780",
        "representative_curve_values": len(representative_curves),
    }


def seed_disposable_scale_fixture(
    base_url: str,
    *,
    project_name: str,
    marker: str | None,
    workers: int = 8,
) -> dict[str, object]:
    project = validate_disposable_context(project_name, marker)
    if not 1 <= workers <= 16:
        raise DemoSeedError("scale fixture workers must be between 1 and 16")
    api = DemoApi(base_url)
    api.wait_until_healthy()
    api.authenticate()
    reviewer_api = DemoApi(base_url)
    reviewer_api.authenticate("reviewer")
    table, attributes = _catalog_resources(api)
    table_id = _stable_id(table, "table_id")
    table_revision_id = _revision_id(table)
    existing = _search(api, table_id=table_id, text=FIXTURE_PREFIX, limit=1)
    existing_count = existing.get("total_count")
    if existing_count == FIXTURE_COUNT:
        _publish_exact_lookup_sample(api, reviewer_api, table_id=table_id)
        report = verify_scale_fixture(api, table=table, attributes=attributes)
        return {"project": project, "created": 0, **report}
    if existing_count != 0:
        raise DemoSeedError(
            "scale fixture found a partial or conflicting prior population: "
            f"count={existing_count}"
        )

    completed = 0
    specs = fixture_specs()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _create_scale_record,
                api,
                table_id=table_id,
                table_revision_id=table_revision_id,
                attributes=attributes,
                spec=spec,
            ): spec
            for spec in specs
        }
        try:
            for future in as_completed(futures):
                future.result()
                completed += 1
                if completed % 100 == 0:
                    print(f"Disposable scale fixture created: {completed}/{FIXTURE_COUNT}")
        except BaseException:
            for future in futures:
                future.cancel()
            raise

    _publish_exact_lookup_sample(api, reviewer_api, table_id=table_id)
    report = verify_scale_fixture(api, table=table, attributes=attributes)
    return {"project": project, "created": FIXTURE_COUNT, **report}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed and verify 1,000 metadata-only Materials in a disposable demo project."
    )
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--workers", type=int, default=8)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = seed_disposable_scale_fixture(
            args.api_base_url,
            project_name=args.project_name,
            marker=os.getenv(DISPOSABLE_MARKER),
            workers=args.workers,
        )
    except (DemoSeedError, ValueError) as exc:
        print(f"Disposable scale fixture failed: {exc}")
        return 2
    print(f"Disposable scale fixture passed: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
