"""Bounded full-stack performance and security acceptance evidence."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import tracemalloc
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from cmp.modules.exporting.domain.bulk_bundle import (
    ExportMemberKind,
    ExportSelectionContent,
    ExportSelectionMember,
    ExportSourceRef,
    ResolvedBundleFile,
    build_deterministic_bundle,
)
from cmp.modules.identity_access.domain.authorization import DataClassification
from cmp.shared.domain.revisions import canonical_json_bytes

_MIB = 1024 * 1024


class PerformanceAcceptanceError(RuntimeError):
    """The bounded acceptance run is unsafe, malformed, or outside policy."""


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    body: bytes
    headers: Mapping[str, str]


def percentile(values: list[float], percentile_value: float) -> float:
    """Return a nearest-rank percentile for an explicit finite sample."""

    if not values or not 0 < percentile_value <= 100:
        raise ValueError("percentile requires samples and a percentile in (0, 100]")
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("latency samples must be finite and non-negative")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value / 100 * len(ordered)) - 1)
    return ordered[index]


def latency_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        raise ValueError("latency summary requires at least one sample")
    return {
        "max_ms": round(max(values), 3),
        "p50_ms": round(percentile(values, 50), 3),
        "p95_ms": round(percentile(values, 95), 3),
        "p99_ms": round(percentile(values, 99), 3),
        "sample_count": len(values),
        "samples_ms": [round(value, 3) for value in values],
    }


class FullStackClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 60) -> None:
        parsed = urlsplit(base_url.rstrip("/"))
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise PerformanceAcceptanceError(
                "API base URL must be an HTTP(S) origin/path without credentials"
            )
        self.base_url = base_url.rstrip("/")
        self._base_path = parsed.path.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._token: str | None = None

    def url_for(self, path: str) -> str:
        if not path.startswith("/") or "\x00" in path:
            raise PerformanceAcceptanceError("API request path must be absolute and safe")
        relative = path
        if self._base_path and (
            path == self._base_path or path.startswith(f"{self._base_path}/")
        ):
            relative = path[len(self._base_path) :] or "/"
        return f"{self.base_url}{relative}"

    def authenticate_demo(self) -> None:
        result = self.request("/demo-identity/token", authenticated=False)
        document = self.json_object(result, label="demo identity response")
        token = document.get("access_token")
        if not isinstance(token, str) or len(token) < 32:
            raise PerformanceAcceptanceError("explicit demo identity did not return a token")
        self._token = token

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        authenticated: bool = True,
        expected: tuple[int, ...] = (200,),
    ) -> HttpResult:
        request_headers = {"Accept": "application/json", **(headers or {})}
        if authenticated:
            if self._token is None:
                raise PerformanceAcceptanceError("API request requires demo authentication")
            request_headers["Authorization"] = f"Bearer {self._token}"
        request = Request(
            self.url_for(path), data=body, headers=request_headers, method=method
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                result = HttpResult(
                    response.status,
                    response.read(),
                    {name.lower(): value for name, value in response.headers.items()},
                )
        except HTTPError as error:
            result = HttpResult(
                error.code,
                error.read(64 * 1024),
                {name.lower(): value for name, value in error.headers.items()},
            )
        except URLError as error:
            raise PerformanceAcceptanceError("full-stack API is unavailable") from error
        if result.status not in expected:
            detail = result.body[:512].decode("utf-8", errors="replace")
            raise PerformanceAcceptanceError(
                f"API {method} {path} returned {result.status}: {detail}"
            )
        return result

    def json_request(
        self,
        path: str,
        *,
        method: str = "GET",
        value: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        authenticated: bool = True,
        expected: tuple[int, ...] = (200,),
    ) -> tuple[HttpResult, dict[str, Any]]:
        body = None
        request_headers = dict(headers or {})
        if value is not None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        result = self.request(
            path,
            method=method,
            body=body,
            headers=request_headers,
            authenticated=authenticated,
            expected=expected,
        )
        return result, self.json_object(result, label=f"API {method} {path}")

    @staticmethod
    def json_object(result: HttpResult, *, label: str) -> dict[str, Any]:
        try:
            document = json.loads(result.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PerformanceAcceptanceError(f"{label} is not JSON") from error
        if not isinstance(document, dict):
            raise PerformanceAcceptanceError(f"{label} must be a JSON object")
        return document


def _measure(action: Callable[[], object], *, samples: int, warmups: int) -> dict[str, Any]:
    for _ in range(warmups):
        action()
    observed: list[float] = []
    for _ in range(samples):
        started = time.perf_counter()
        action()
        observed.append((time.perf_counter() - started) * 1000)
    return latency_summary(observed)


def _catalog_benchmark(
    client: FullStackClient, *, samples: int, warmups: int, p95_limit_ms: float
) -> dict[str, Any]:
    path = f"/materials?{urlencode({'limit': 100})}"
    latest: dict[str, Any] = {}

    def read() -> None:
        nonlocal latest
        _, latest = client.json_request(path)

    latency = _measure(read, samples=samples, warmups=warmups)
    items = latest.get("items")
    if not isinstance(items, list):
        raise PerformanceAcceptanceError("Catalog response items must be an array")
    return {
        "cardinality_visible": len(items),
        "latency": latency,
        "passed_bounded_latency": float(latency["p95_ms"]) < p95_limit_ms
        and float(latency["p99_ms"]) < 1500,
        "p95_limit_ms": p95_limit_ms,
        "production_10000_material_search": (
            "evaluated" if len(items) >= 10_000 else "not_evaluated_at_production_scale"
        ),
    }


def _security_checks(client: FullStackClient) -> dict[str, Any]:
    unauthenticated = client.request("/materials?limit=1", authenticated=False, expected=(401,))
    invalid = client.request(
        "/materials?limit=1",
        authenticated=False,
        headers={"Authorization": "Bearer invalid.invalid.invalid"},
        expected=(401,),
    )
    unsafe_body = {
        "classification": "internal",
        "expected_sha256": hashlib.sha256(b"x").hexdigest(),
        "expected_size_bytes": 1,
        "media_type": "application/octet-stream",
        "original_filename": "../escape.bin",
        "part_size_bytes": 1,
        "test_run_revision_id": None,
    }
    unsafe, _ = client.json_request(
        "/uploads",
        method="POST",
        value=unsafe_body,
        headers={"Idempotency-Key": str(uuid4())},
        expected=(422,),
    )
    leaked = any(
        marker in result.body
        for result in (unauthenticated, invalid, unsafe)
        for marker in (b"invalid.invalid.invalid", b"Authorization", b"../escape.bin")
    )
    return {
        "invalid_bearer_status": invalid.status,
        "passed": not leaked,
        "response_secret_or_input_leak": leaked,
        "unauthenticated_status": unauthenticated.status,
        "unsafe_filename_status": unsafe.status,
    }


def _upload_benchmark(
    client: FullStackClient,
    *,
    size_bytes: int,
    part_size_bytes: int,
    minimum_mib_per_second: float,
) -> dict[str, Any]:
    if size_bytes < 1 or part_size_bytes < 1 or size_bytes % part_size_bytes:
        raise PerformanceAcceptanceError("upload fixture must use positive, evenly sized parts")
    payload = (b"CMP-PERFORMANCE-REFERENCE-FIXTURE-" * (size_bytes // 34 + 1))[:size_bytes]
    digest = hashlib.sha256(payload).hexdigest()
    started = time.perf_counter()
    _, created = client.json_request(
        "/uploads",
        method="POST",
        value={
            "classification": "internal",
            "expected_sha256": digest,
            "expected_size_bytes": size_bytes,
            "media_type": "application/octet-stream",
            "original_filename": f"performance-{digest[:12]}.bin",
            "part_size_bytes": part_size_bytes,
            "test_run_revision_id": None,
        },
        headers={"Idempotency-Key": str(uuid4())},
        expected=(201,),
    )
    upload = created.get("upload")
    capability = created.get("upload_capability")
    if not isinstance(upload, dict) or not isinstance(capability, str):
        raise PerformanceAcceptanceError("upload creation omitted session or capability")
    upload_id = upload.get("upload_id")
    if not isinstance(upload_id, str):
        raise PerformanceAcceptanceError("upload creation omitted upload_id")
    first_part = payload[:part_size_bytes]
    tampered = ("x" if capability[0] != "x" else "y") + capability[1:]
    denied = client.request(
        f"/uploads/{upload_id}/parts/1",
        method="PUT",
        body=first_part,
        headers={
            "Content-Type": "application/octet-stream",
            "Upload-Capability": tampered,
        },
        expected=(403,),
    )
    for index, offset in enumerate(range(0, size_bytes, part_size_bytes), start=1):
        client.request(
            f"/uploads/{upload_id}/parts/{index}",
            method="PUT",
            body=payload[offset : offset + part_size_bytes],
            headers={
                "Content-Type": "application/octet-stream",
                "Upload-Capability": capability,
            },
        )
    _, completed = client.json_request(
        f"/uploads/{upload_id}:complete",
        method="POST",
        value={},
        headers={"Upload-Capability": capability},
    )
    elapsed = time.perf_counter() - started
    raw_asset = completed.get("raw_asset")
    if not isinstance(raw_asset, dict):
        raise PerformanceAcceptanceError("completed upload omitted Raw Asset evidence")
    exact = raw_asset.get("sha256") == digest and raw_asset.get("size_bytes") == size_bytes
    throughput = size_bytes / _MIB / elapsed
    leaked = capability.encode("utf-8") in denied.body
    return {
        "capability_tamper_status": denied.status,
        "digest_and_size_verified": exact,
        "duration_seconds": round(elapsed, 6),
        "minimum_mib_per_second": minimum_mib_per_second,
        "part_count": size_bytes // part_size_bytes,
        "part_size_bytes": part_size_bytes,
        "passed": exact and not leaked and throughput >= minimum_mib_per_second,
        "production_2gib_streaming": (
            "evaluated" if size_bytes >= 2 * 1024**3 else "not_evaluated_at_production_scale"
        ),
        "response_capability_leak": leaked,
        "size_bytes": size_bytes,
        "throughput_mib_per_second": round(throughput, 3),
    }


def _bundle_download_benchmark(
    client: FullStackClient, *, samples: int, warmups: int
) -> dict[str, Any]:
    _, listed = client.json_request("/export-bundles")
    items = listed.get("items")
    if not isinstance(items, list) or not items:
        raise PerformanceAcceptanceError("demo has no immutable Bundle to download")
    bundle = max(
        (item for item in items if isinstance(item, dict)),
        key=lambda item: int(item.get("archive_size_bytes", 0)),
    )
    bundle_id = bundle.get("export_bundle_id")
    if not isinstance(bundle_id, str):
        raise PerformanceAcceptanceError("Bundle response omitted export_bundle_id")
    _, grant = client.json_request(
        f"/export-bundles/{bundle_id}/download-authorizations",
        method="POST",
        value={},
        expected=(201,),
    )
    transfer_url = grant.get("transfer_url")
    transfer_token = grant.get("transfer_token")
    expected_digest = grant.get("sha256")
    expected_size = grant.get("size_bytes")
    if not isinstance(transfer_url, str) or not isinstance(transfer_token, str):
        raise PerformanceAcceptanceError("Bundle authorization omitted transfer capability")
    latest = b""

    def download() -> None:
        nonlocal latest
        latest = client.request(
            transfer_url,
            headers={"Artifact-Transfer-Token": transfer_token},
        ).body

    latency = _measure(download, samples=samples, warmups=warmups)
    digest = hashlib.sha256(latest).hexdigest()
    exact = expected_digest in {digest, f"sha256:{digest}"} and expected_size == len(latest)
    return {
        "archive_size_bytes": len(latest),
        "bundle_id": bundle_id,
        "digest_and_size_verified": exact,
        "latency": latency,
        "passed": exact,
    }


def build_inline_bundle_fixture(size_bytes: int, *, seed: int = 20260716) -> dict[str, Any]:
    if not _MIB <= size_bytes <= 64 * _MIB or size_bytes % _MIB:
        raise PerformanceAcceptanceError("inline Bundle fixture must be 1..64 MiB in whole MiB")
    generator = random.Random(seed)
    members: list[ExportSelectionMember] = []
    files: list[ResolvedBundleFile] = []
    for ordinal in range(1, size_bytes // _MIB + 1):
        value = generator.randbytes(_MIB)
        member = ExportSelectionMember(
            ordinal,
            ExportSourceRef(
                ExportMemberKind.RAW_ORIGINAL,
                raw_asset_id=UUID(int=ordinal),
                artifact_id=UUID(int=10_000 + ordinal),
            ),
            f"raw/performance-{ordinal:03d}.bin",
            hashlib.sha256(value).hexdigest(),
            len(value),
            "application/octet-stream",
            DataClassification.INTERNAL,
            f"Performance fixture {ordinal}",
        )
        members.append(member)
        files.append(ResolvedBundleFile(member, value))
    content = ExportSelectionContent("T-47 inline performance fixture", tuple(members), ())
    tracemalloc.start()
    started = time.perf_counter()
    built = build_deterministic_bundle(
        selection_id=UUID(int=99_001),
        selection_revision_id=UUID(int=99_002),
        content=content,
        files=tuple(files),
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if hashlib.sha256(built.archive).hexdigest() != built.archive_sha256:
        raise PerformanceAcceptanceError("inline Bundle digest verification failed")
    with zipfile.ZipFile(io.BytesIO(built.archive)) as archive:
        checksum_lines = archive.read("checksums.sha256").decode("utf-8").splitlines()
        if len(checksum_lines) != len(members) + 2:
            raise PerformanceAcceptanceError("inline Bundle checksum coverage is incomplete")
    return {
        "archive_size_bytes": len(built.archive),
        "component_count": len(members),
        "duration_seconds": round(elapsed, 6),
        "input_size_bytes": size_bytes,
        "peak_incremental_python_bytes": peak,
        "rng": {
            "algorithm": "python.random.MT19937",
            "python": platform.python_version(),
            "seed": seed,
        },
    }


def _git_commit(root: Path) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False
    )
    if status.returncode != 0 or status.stdout.strip():
        raise PerformanceAcceptanceError("acceptance evidence requires a clean Git working tree")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if commit.returncode != 0:
        raise PerformanceAcceptanceError("source commit is unavailable")
    return commit.stdout.strip()


def write_report(output: Path, report: Mapping[str, Any]) -> str:
    output.mkdir(parents=True, exist_ok=False)
    payload = canonical_json_bytes(dict(report))
    digest = hashlib.sha256(payload).hexdigest()
    (output / "report.json").write_bytes(payload)
    (output / "report.sha256").write_text(f"{digest}  report.json\n", encoding="ascii")
    return digest


def verify_report(output: Path) -> dict[str, Any]:
    payload = (output / "report.json").read_bytes()
    expected_line = (output / "report.sha256").read_text(encoding="ascii").strip()
    expected, separator, name = expected_line.partition("  ")
    if (
        separator != "  "
        or name != "report.json"
        or hashlib.sha256(payload).hexdigest() != expected
    ):
        raise PerformanceAcceptanceError("performance report digest verification failed")
    try:
        report = json.loads(payload)
    except json.JSONDecodeError as error:
        raise PerformanceAcceptanceError("performance report is not JSON") from error
    if not isinstance(report, dict) or canonical_json_bytes(report) != payload:
        raise PerformanceAcceptanceError("performance report is not canonical JSON")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-url", default="http://127.0.0.1:5173/api/v1")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--bundle-download-samples", type=int, default=5)
    parser.add_argument("--upload-bytes", type=int, default=2 * _MIB)
    parser.add_argument("--upload-part-bytes", type=int, default=64 * 1024)
    parser.add_argument("--inline-bundle-bytes", type=int, default=64 * _MIB)
    parser.add_argument("--catalog-p95-limit-ms", type=float, default=500)
    parser.add_argument("--upload-minimum-mib-per-second", type=float, default=1)
    parser.add_argument("--inline-bundle-limit-seconds", type=float, default=30)
    parser.add_argument("--acknowledge-immutable-demo-write", action="store_true")
    parser.add_argument("--require-production-scale", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not args.acknowledge_immutable_demo_write:
        raise PerformanceAcceptanceError(
            "the full-stack fixture appends an immutable demo Raw Asset; "
            "pass the explicit acknowledgement"
        )
    if not 1 <= args.samples <= 1000 or not 0 <= args.warmups <= 100:
        raise PerformanceAcceptanceError("sample and warmup counts are outside bounded policy")
    root = args.root.resolve(strict=True)
    source_commit = _git_commit(root)
    client = FullStackClient(args.base_url)
    health = client.request("/health", authenticated=False)
    client.authenticate_demo()
    catalog = _catalog_benchmark(
        client,
        samples=args.samples,
        warmups=args.warmups,
        p95_limit_ms=args.catalog_p95_limit_ms,
    )
    security = _security_checks(client)
    upload = _upload_benchmark(
        client,
        size_bytes=args.upload_bytes,
        part_size_bytes=args.upload_part_bytes,
        minimum_mib_per_second=args.upload_minimum_mib_per_second,
    )
    download = _bundle_download_benchmark(client, samples=args.bundle_download_samples, warmups=1)
    inline = build_inline_bundle_fixture(args.inline_bundle_bytes)
    inline["limit_seconds"] = args.inline_bundle_limit_seconds
    inline["passed"] = inline["duration_seconds"] <= args.inline_bundle_limit_seconds
    production_scale = (
        catalog["production_10000_material_search"] == "evaluated"
        and upload["production_2gib_streaming"] == "evaluated"
    )
    bounded_passed = all(
        (
            catalog["passed_bounded_latency"],
            security["passed"],
            upload["passed"],
            download["passed"],
            inline["passed"],
        )
    )
    passed = bounded_passed and (production_scale or not args.require_production_scale)
    report: dict[str, Any] = {
        "claims": {
            "bounded_local_gate_passed": bounded_passed,
            "production_scale_accepted": production_scale,
            "solver_execution_in_scope": False,
        },
        "created_at": datetime.now(UTC).isoformat(),
        "environment": {
            "api_base_url": args.base_url,
            "health_status": health.status,
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "operations": {
            "bundle_download": download,
            "catalog_metadata_read": catalog,
            "inline_bundle_assembly": inline,
            "streaming_upload": upload,
        },
        "passed": passed,
        "schema": "cmp.performance-security-acceptance.v1",
        "security": security,
        "source_commit": source_commit,
    }
    output = args.output or (
        root / ".cache" / "performance-acceptance" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    digest = write_report(output, report)
    verify_report(output)
    print(
        json.dumps(
            {
                "bounded_local_gate_passed": bounded_passed,
                "output": os.fspath(output.resolve()),
                "passed": passed,
                "production_scale_accepted": production_scale,
                "report_sha256": digest,
            }
        )
    )
    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
