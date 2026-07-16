"""Verify the live Steel, Polymer, Elastomer and bulk-export product pilot."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

import psycopg

from cmp.shared.domain.revisions import canonical_json_bytes
from cmp.tools.performance_acceptance import FullStackClient


class ProductPilotAcceptanceError(RuntimeError):
    """The composed product pilot is incomplete or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class MaterialExpectation:
    code: str
    material_class: str
    model_collection: str
    evidence_key: str
    card_markers: Mapping[str, tuple[str, ...]]
    minimum_test_runs: int
    required_run_label_fragments: tuple[str, ...]
    minimum_datasets: int = 0
    minimum_relaxation_datasets: int = 0


EXPECTATIONS = (
    MaterialExpectation(
        code="CMP-DEMO-DP780",
        material_class="metal",
        model_collection="tabulated-plasticity-models",
        evidence_key="calibration_projection",
        card_markers={
            "abaqus": ("*MATERIAL", "*ELASTIC", "*PLASTIC"),
            "openradioss": ("/MAT/LAW36/",),
        },
        minimum_test_runs=4,
        required_run_label_fragments=("replicate 1", "replicate 2", "replicate 3", "holdout"),
        minimum_datasets=6,
    ),
    MaterialExpectation(
        code="POLY-PRONY-001",
        material_class="polymer",
        model_collection="linear-viscoelastic-models",
        evidence_key="prony_promotion_evidence",
        card_markers={"abaqus": ("*MATERIAL", "*ELASTIC", "*VISCOELASTIC")},
        minimum_test_runs=6,
        required_run_label_fragments=("273.15 K", "293.15 K", "313.15 K"),
        minimum_relaxation_datasets=6,
    ),
    MaterialExpectation(
        code="DEMO-ELAST-001",
        material_class="elastomer",
        model_collection="ogden-prony-models",
        evidence_key="promotion_evidence",
        card_markers={
            "abaqus": ("*MATERIAL", "*HYPERELASTIC", "*VISCOELASTIC"),
            "openradioss": ("/MAT/LAW62/",),
        },
        minimum_test_runs=4,
        required_run_label_fragments=("uniaxial", "planar", "biaxial", "holdout"),
    ),
)


def _items(document: Mapping[str, Any], *, label: str) -> list[dict[str, Any]]:
    value = document.get("items")
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProductPilotAcceptanceError(f"{label} must contain an object array named items")
    return value


def _object(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProductPilotAcceptanceError(f"{label} must be an object")
    return value


def _text(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProductPilotAcceptanceError(f"{label} must be a non-empty string")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(client: FullStackClient, path: str) -> dict[str, Any]:
    try:
        _, document = client.json_request(path)
    except RuntimeError as error:
        raise ProductPilotAcceptanceError(str(error)) from error
    return document


def _select_material(client: FullStackClient, expectation: MaterialExpectation) -> dict[str, Any]:
    query = urlencode({"q": expectation.code, "limit": 5})
    items = _items(_json(client, f"/materials?{query}"), label=expectation.code)
    exact = [
        item
        for item in items
        if _object(
            _object(item.get("current_revision"), label="Material revision").get("content"),
            label="Material content",
        ).get("material_code")
        == expectation.code
    ]
    if len(exact) != 1:
        raise ProductPilotAcceptanceError(
            f"{expectation.code} must resolve to exactly one visible Material"
        )
    return exact[0]


def _revision_content(resource: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    revision = _object(resource.get("current_revision"), label=f"{label} revision")
    return _object(revision.get("content"), label=f"{label} content")


def _verify_cards(
    client: FullStackClient,
    *,
    collection: str,
    model_id: str,
    required_markers: Mapping[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    cards = _items(
        _json(client, f"/{collection}/{model_id}/solver-cards"),
        label=f"{collection} Solver Cards",
    )
    verified: list[dict[str, Any]] = []
    for solver, markers in required_markers.items():
        matches = [
            card
            for card in cards
            if _object(card.get("target"), label="Solver Card target").get("solver") == solver
        ]
        if not matches:
            raise ProductPilotAcceptanceError(f"{collection} has no {solver} Solver Card")
        card = matches[0]
        card_id = _text(card.get("solver_card_id"), label="Solver Card id")
        links = _object(card.get("links"), label="Solver Card links")
        preview_path = _text(links.get("preview"), label="Solver Card preview link")
        download_path = _text(links.get("download"), label="Solver Card download link")
        preview = client.request(preview_path, headers={"Accept": "text/plain"}).body
        download = client.request(download_path, headers={"Accept": "text/plain"}).body
        if preview != download:
            raise ProductPilotAcceptanceError(f"{solver} preview and download bytes differ")
        decoded = download.decode("utf-8")
        missing = [marker for marker in markers if marker not in decoded]
        if missing:
            raise ProductPilotAcceptanceError(
                f"{solver} Solver Card is missing markers: {', '.join(missing)}"
            )
        content = _revision_content(card, label="Solver Card")
        expected_digest = _text(content.get("card_sha256"), label="Solver Card digest")
        observed_digest = _sha256(download)
        if observed_digest != expected_digest.removeprefix("sha256:"):
            raise ProductPilotAcceptanceError(f"{solver} Solver Card digest mismatch")
        statuses = _object(content.get("mapping_statuses"), label="mapping statuses")
        invalid_statuses = sorted(
            status
            for status in statuses.values()
            if status
            not in {
                "exact",
                "transformed",
                "approximated",
                "ignored",
                "unsupported",
                "not_applicable",
            }
        )
        if invalid_statuses:
            raise ProductPilotAcceptanceError(
                f"{solver} Solver Card contains invalid mapping statuses"
            )
        verified.append(
            {
                "solver": solver,
                "solver_card_id": card_id,
                "solver_card_revision_id": _text(
                    _object(card.get("current_revision"), label="Solver Card revision").get("id"),
                    label="Solver Card revision id",
                ),
                "sha256": observed_digest,
                "size_bytes": len(download),
                "mapping_statuses": statuses,
            }
        )
    return verified


def _verify_material(
    client: FullStackClient, expectation: MaterialExpectation
) -> tuple[dict[str, Any], str, str]:
    material = _select_material(client, expectation)
    material_id = _text(material.get("material_id"), label="Material id")
    material_content = _revision_content(material, label="Material")
    if material_content.get("material_class") != expectation.material_class:
        raise ProductPilotAcceptanceError(f"{expectation.code} has the wrong Material class")

    detail = _json(client, f"/materials/{material_id}")
    states = detail.get("states")
    property_sets = detail.get("property_sets")
    if not isinstance(states, list) or len(states) != 1 or not isinstance(states[0], dict):
        raise ProductPilotAcceptanceError(f"{expectation.code} must have one demo Material State")
    if not isinstance(property_sets, list) or not property_sets:
        raise ProductPilotAcceptanceError(f"{expectation.code} has no typed Property Set")
    state = states[0]
    state_id = _text(state.get("material_state_id"), label="Material State id")
    state_revision = _object(state.get("current_revision"), label="Material State revision")
    properties = _revision_content(property_sets[0], label="Property Set")
    for required in ("density_kg_per_m3", "youngs_modulus_pa", "poisson_ratio"):
        if not isinstance(properties.get(required), (int, float)):
            raise ProductPilotAcceptanceError(
                f"{expectation.code} Property Set is missing typed {required}"
            )

    runs = _items(
        _json(client, f"/material-states/{state_id}/test-runs"),
        label=f"{expectation.code} Test Runs",
    )
    if len(runs) < expectation.minimum_test_runs:
        raise ProductPilotAcceptanceError(f"{expectation.code} has too few Test Runs")
    run_labels = [
        str(_revision_content(run, label="Test Run").get("run_label", "")).lower() for run in runs
    ]
    for fragment in expectation.required_run_label_fragments:
        if not any(fragment.lower() in label for label in run_labels):
            raise ProductPilotAcceptanceError(
                f"{expectation.code} has no Test Run matching {fragment!r}"
            )

    datasets = _items(
        _json(client, f"/material-states/{state_id}/datasets"),
        label=f"{expectation.code} Datasets",
    )
    if len(datasets) < expectation.minimum_datasets:
        raise ProductPilotAcceptanceError(f"{expectation.code} has too few typed Datasets")
    relaxation = _items(
        _json(client, f"/material-states/{state_id}/shear-relaxation-datasets"),
        label=f"{expectation.code} relaxation Datasets",
    )
    if len(relaxation) < expectation.minimum_relaxation_datasets:
        raise ProductPilotAcceptanceError(
            f"{expectation.code} has too few shear-relaxation Datasets"
        )
    if expectation.minimum_relaxation_datasets:
        representations = {
            _revision_content(item, label="relaxation Dataset").get("representation")
            for item in relaxation
        }
        if not {"normalized", "processed"}.issubset(representations):
            raise ProductPilotAcceptanceError(
                f"{expectation.code} must retain normalized and processed relaxation Datasets"
            )

    models = _items(
        _json(client, f"/material-states/{state_id}/{expectation.model_collection}"),
        label=f"{expectation.code} models",
    )
    fitted = [
        model
        for model in models
        if isinstance(
            _revision_content(model, label="Material Model").get(expectation.evidence_key),
            dict,
        )
    ]
    if not fitted:
        raise ProductPilotAcceptanceError(
            f"{expectation.code} has no human-promoted fitted Material Model IR"
        )
    model = fitted[0]
    model_id = _text(model.get("material_model_id"), label="Material Model id")
    model_revision = _object(model.get("current_revision"), label="Material Model revision")
    model_content = _revision_content(model, label="Material Model")
    if model_content.get("material_state_id") != state_id or not model_content.get(
        "non_production"
    ):
        raise ProductPilotAcceptanceError(
            f"{expectation.code} Material Model scope or reference status is invalid"
        )
    cards = _verify_cards(
        client,
        collection=expectation.model_collection,
        model_id=model_id,
        required_markers=expectation.card_markers,
    )
    return (
        {
            "material_code": expectation.code,
            "material_class": expectation.material_class,
            "material_id": material_id,
            "material_revision_id": _text(
                _object(material.get("current_revision"), label="Material revision").get("id"),
                label="Material revision id",
            ),
            "material_state_id": state_id,
            "material_state_revision_id": _text(
                state_revision.get("id"), label="Material State revision id"
            ),
            "property_set_revision_id": _text(
                _object(
                    property_sets[0].get("current_revision"),
                    label="Property Set revision",
                ).get("id"),
                label="Property Set revision id",
            ),
            "test_run_count": len(runs),
            "dataset_count": len(datasets),
            "relaxation_dataset_count": len(relaxation),
            "material_model_id": model_id,
            "material_model_revision_id": _text(
                model_revision.get("id"), label="Material Model revision id"
            ),
            "material_model_schema": model_revision.get("schema_id"),
            "fitting_evidence": model_content[expectation.evidence_key],
            "solver_cards": cards,
        },
        material_id,
        state_id,
    )


def verify_bundle_bytes(
    archive: bytes,
    *,
    archive_sha256: str,
    manifest_sha256: str,
    component_count: int,
    omission_count: int,
) -> dict[str, Any]:
    """Verify one downloaded immutable bundle without trusting its manifest."""

    observed_archive_sha256 = _sha256(archive)
    if observed_archive_sha256 != archive_sha256.removeprefix("sha256:"):
        raise ProductPilotAcceptanceError("bulk ZIP digest does not match persistence metadata")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            names = bundle.namelist()
            unsafe_path = any(name.startswith("/") or ".." in Path(name).parts for name in names)
            if len(names) != len(set(names)) or unsafe_path:
                raise ProductPilotAcceptanceError("bulk ZIP contains duplicate or unsafe paths")
            manifest_bytes = bundle.read("manifest.json")
            checksums_text = bundle.read("checksums.sha256").decode("ascii")
            manifest = json.loads(manifest_bytes)
            if not isinstance(manifest, dict):
                raise ProductPilotAcceptanceError("bulk manifest must be an object")
            checksum_entries: dict[str, str] = {}
            for line in checksums_text.splitlines():
                digest, separator, path = line.partition("  ")
                if separator != "  " or len(digest) != 64 or path in checksum_entries:
                    raise ProductPilotAcceptanceError("bulk checksum inventory is malformed")
                checksum_entries[path] = digest
            expected_paths = set(names) - {"checksums.sha256"}
            if set(checksum_entries) != expected_paths:
                raise ProductPilotAcceptanceError("bulk checksum inventory is incomplete")
            for path, digest in checksum_entries.items():
                if _sha256(bundle.read(path)) != digest:
                    raise ProductPilotAcceptanceError(f"bulk component digest mismatch: {path}")
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise ProductPilotAcceptanceError("bulk ZIP is malformed") from error

    if _sha256(manifest_bytes) != manifest_sha256.removeprefix("sha256:"):
        raise ProductPilotAcceptanceError("bulk manifest digest mismatch")
    components = manifest.get("components")
    omissions = manifest.get("omissions")
    if not isinstance(components, list) or len(components) != component_count:
        raise ProductPilotAcceptanceError("bulk manifest component count mismatch")
    if not isinstance(omissions, list) or len(omissions) != omission_count:
        raise ProductPilotAcceptanceError("bulk manifest omission count mismatch")
    kinds = {
        _object(
            _object(component, label="bundle component").get("source"),
            label="bundle source",
        ).get("kind")
        for component in components
    }
    required_kinds = {
        "raw_original",
        "dataset_parquet",
        "dataset_csv",
        "model_ir_json",
        "model_ir_schema",
        "solver_mapping_report",
        "solver_card_native",
    }
    if not required_kinds.issubset(kinds):
        missing = sorted(required_kinds - kinds)
        raise ProductPilotAcceptanceError(
            f"bulk manifest is missing representation kinds: {', '.join(missing)}"
        )
    return {
        "archive_sha256": observed_archive_sha256,
        "archive_size_bytes": len(archive),
        "manifest_sha256": _sha256(manifest_bytes),
        "component_count": len(components),
        "omission_count": len(omissions),
        "representation_kinds": sorted(str(kind) for kind in kinds),
    }


def _transfer_path(client: FullStackClient, value: str) -> str:
    parsed = urlsplit(value)
    if not parsed.scheme and not parsed.netloc:
        return value
    base = urlsplit(client.base_url)
    if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
        raise ProductPilotAcceptanceError("bundle transfer URL crosses the configured API origin")
    path = parsed.path
    if parsed.query:
        path += f"?{parsed.query}"
    return path


def _verify_bundle(client: FullStackClient) -> tuple[dict[str, Any], str]:
    bundles = _items(_json(client, "/export-bundles"), label="Bulk Export Bundles")
    eligible = [
        bundle
        for bundle in bundles
        if isinstance(bundle.get("component_count"), int)
        and bundle["component_count"] >= 22
        and bundle.get("omission_count") == 0
    ]
    if not eligible:
        raise ProductPilotAcceptanceError("no complete 22-component bulk bundle is available")
    bundle = eligible[0]
    bundle_id = _text(bundle.get("export_bundle_id"), label="Bundle id")
    _, authorization = client.json_request(
        f"/export-bundles/{bundle_id}/download-authorizations",
        method="POST",
        expected=(201,),
    )
    transfer = client.request(
        _transfer_path(
            client, _text(authorization.get("transfer_url"), label="Bundle transfer URL")
        ),
        headers={
            "Accept": "application/zip",
            "Artifact-Transfer-Token": _text(
                authorization.get("transfer_token"), label="Bundle transfer token"
            ),
        },
    )
    verified = verify_bundle_bytes(
        transfer.body,
        archive_sha256=_text(bundle.get("archive_sha256"), label="Bundle digest"),
        manifest_sha256=_text(bundle.get("manifest_sha256"), label="Manifest digest"),
        component_count=int(bundle["component_count"]),
        omission_count=int(bundle["omission_count"]),
    )
    return (
        {
            "export_bundle_id": bundle_id,
            "export_selection_id": bundle.get("export_selection_id"),
            **verified,
        },
        bundle_id,
    )


def _postgres_evidence(
    dsn: str, *, material_ids: Sequence[str], state_ids: Sequence[str], bundle_id: str
) -> dict[str, Any]:
    normalized = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(normalized) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            server = connection.execute(
                "SELECT current_database(), current_setting('server_version')"
            ).fetchone()
            materials = connection.execute(
                "SELECT count(*) FROM catalog.material WHERE id = ANY(%s::uuid[])",
                (list(material_ids),),
            ).fetchone()
            models = connection.execute(
                "SELECT count(*) FROM modeling.material_model "
                "WHERE material_state_id = ANY(%s::uuid[])",
                (list(state_ids),),
            ).fetchone()
            bundles = connection.execute(
                "SELECT count(*) FROM exporting.bulk_export_bundle WHERE id = %s::uuid",
                (bundle_id,),
            ).fetchone()
    except psycopg.Error as error:
        raise ProductPilotAcceptanceError("PostgreSQL acceptance query failed") from error
    if server is None or materials is None or models is None or bundles is None:
        raise ProductPilotAcceptanceError("PostgreSQL acceptance query returned no evidence")
    if materials[0] != len(material_ids) or models[0] < len(state_ids) or bundles[0] != 1:
        raise ProductPilotAcceptanceError("PostgreSQL rows do not match live API identities")
    return {
        "database": server[0],
        "server_version": server[1],
        "matched_material_identities": materials[0],
        "matched_material_model_identities": models[0],
        "matched_export_bundles": bundles[0],
        "transaction_mode": "read_only",
    }


def _git_commit(root: Path, *, allow_dirty: bool) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
    )
    if status.returncode != 0:
        raise ProductPilotAcceptanceError("Git working tree status is unavailable")
    if status.stdout.strip() and not allow_dirty:
        raise ProductPilotAcceptanceError("acceptance evidence requires a clean Git working tree")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if commit.returncode != 0:
        raise ProductPilotAcceptanceError("source commit is unavailable")
    return commit.stdout.strip()


def _write_report(output: Path, report: Mapping[str, Any]) -> str:
    output.mkdir(parents=True, exist_ok=False)
    payload = canonical_json_bytes(dict(report))
    digest = _sha256(payload)
    (output / "report.json").write_bytes(payload)
    (output / "report.sha256").write_text(f"{digest}  report.json\n", encoding="ascii")
    return digest


def run_acceptance(
    *,
    root: Path,
    base_url: str,
    postgres_dsn: str,
    output: Path,
    http_timeout_seconds: float,
    allow_dirty: bool,
) -> tuple[dict[str, Any], str]:
    commit = _git_commit(root, allow_dirty=allow_dirty)
    client = FullStackClient(base_url, timeout_seconds=http_timeout_seconds)
    health = client.request("/health", authenticated=False)
    health_document = FullStackClient.json_object(health, label="health response")
    if health_document.get("status") != "ok":
        raise ProductPilotAcceptanceError("API health is not ready")
    client.authenticate_demo()

    workflows: list[dict[str, Any]] = []
    material_ids: list[str] = []
    state_ids: list[str] = []
    for expectation in EXPECTATIONS:
        workflow, material_id, state_id = _verify_material(client, expectation)
        workflows.append(workflow)
        material_ids.append(material_id)
        state_ids.append(state_id)
    bundle, bundle_id = _verify_bundle(client)
    postgres = _postgres_evidence(
        postgres_dsn, material_ids=material_ids, state_ids=state_ids, bundle_id=bundle_id
    )
    report = {
        "schema": "cmp.product-pilot-acceptance.v1",
        "recorded_at": datetime.now(UTC).isoformat(),
        "source_commit": commit,
        "base_url": base_url,
        "acceptance_scope": {
            "solver_execution": "excluded",
            "reference_models": "non-production",
            "workflow_count": len(workflows),
        },
        "health": health_document,
        "postgresql": postgres,
        "workflows": workflows,
        "bulk_export": bundle,
        "status": "passed",
    }
    digest = _write_report(output, report)
    return report, digest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-url", default="http://127.0.0.1:18000/api/v1")
    parser.add_argument(
        "--postgres-dsn", default=os.environ.get("CMP_PRODUCT_PILOT_POSTGRES_DSN", "")
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--http-timeout-seconds", type=float, default=60)
    parser.add_argument("--allow-dirty", action="store_true")
    return parser


def main() -> None:
    args = _parser().parse_args()
    root = args.root.resolve()
    if not args.postgres_dsn:
        raise SystemExit("CMP_PRODUCT_PILOT_POSTGRES_DSN or --postgres-dsn is required")
    output = args.output or (
        root / ".cache" / "product-pilot-acceptance" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    try:
        report, digest = run_acceptance(
            root=root,
            base_url=args.base_url,
            postgres_dsn=args.postgres_dsn,
            output=output,
            http_timeout_seconds=args.http_timeout_seconds,
            allow_dirty=args.allow_dirty,
        )
    except (ProductPilotAcceptanceError, RuntimeError, OSError) as error:
        print(f"product-pilot acceptance failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(
        json.dumps(
            {
                "status": report["status"],
                "workflow_count": len(report["workflows"]),
                "bundle_id": report["bulk_export"]["export_bundle_id"],
                "report": str(output / "report.json"),
                "report_sha256": digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
