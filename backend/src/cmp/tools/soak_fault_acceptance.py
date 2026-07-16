"""Time-bounded mixed-workload soak and fail-safe Docker fault acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen

from cmp.tools.performance_acceptance import (
    FullStackClient,
    PerformanceAcceptanceError,
    latency_summary,
    write_report,
)


class SoakFaultAcceptanceError(RuntimeError):
    """The soak/fault run is unsafe, malformed, or failed acceptance."""


@dataclass(frozen=True, slots=True)
class WorkloadSample:
    operation: str
    latency_ms: float
    succeeded: bool
    inside_fault_window: bool
    error_type: str | None = None


class WorkloadRecorder:
    """Thread-safe, bounded soak evidence without request/response payloads."""

    def __init__(self, *, maximum_samples: int = 100_000) -> None:
        if not 1 <= maximum_samples <= 1_000_000:
            raise ValueError("maximum soak samples must be within 1..1,000,000")
        self._maximum_samples = maximum_samples
        self._samples: list[WorkloadSample] = []
        self._dropped = 0
        self._lock = threading.Lock()

    def record(self, sample: WorkloadSample) -> None:
        if not math.isfinite(sample.latency_ms) or sample.latency_ms < 0:
            raise ValueError("soak latency must be finite and non-negative")
        with self._lock:
            if len(self._samples) >= self._maximum_samples:
                self._dropped += 1
                return
            self._samples.append(sample)

    def summary(self, *, p95_limit_ms: float) -> dict[str, Any]:
        with self._lock:
            samples = tuple(self._samples)
            dropped = self._dropped
        operations: dict[str, dict[str, Any]] = {}
        for name in sorted({sample.operation for sample in samples}):
            selected = [sample for sample in samples if sample.operation == name]
            ordinary_successes = [
                sample.latency_ms
                for sample in selected
                if sample.succeeded and not sample.inside_fault_window
            ]
            operations[name] = {
                "fault_window_failures": sum(
                    not sample.succeeded and sample.inside_fault_window for sample in selected
                ),
                "ordinary_failures": sum(
                    not sample.succeeded and not sample.inside_fault_window
                    for sample in selected
                ),
                "ordinary_latency": (
                    latency_summary(ordinary_successes) if ordinary_successes else None
                ),
                "ordinary_successes": len(ordinary_successes),
                "sample_count": len(selected),
            }
        ordinary_failures = sum(
            not sample.succeeded and not sample.inside_fault_window for sample in samples
        )
        p95_values = [
            float(operation["ordinary_latency"]["p95_ms"])
            for operation in operations.values()
            if operation["ordinary_latency"] is not None
        ]
        return {
            "dropped_samples": dropped,
            "operations": operations,
            "ordinary_failures": ordinary_failures,
            "ordinary_p95_limit_ms": p95_limit_ms,
            "passed": bool(operations)
            and dropped == 0
            and ordinary_failures == 0
            and all(operation["ordinary_successes"] > 0 for operation in operations.values())
            and all(value < p95_limit_ms for value in p95_values),
            "sample_count": len(samples),
        }


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments), capture_output=True, text=True, check=False, timeout=120
    )


class DockerComposeController:
    """Allow-listed demo service faults with mandatory reverse-order recovery."""

    _ALLOWED_SERVICES = frozenset({"api", "postgres", "web", "worker"})

    def __init__(
        self,
        compose_files: Sequence[Path],
        *,
        runner: CommandRunner = _default_runner,
    ) -> None:
        if not compose_files:
            raise SoakFaultAcceptanceError("at least one Compose file is required")
        self._prefix = ["docker", "compose"]
        for compose_file in compose_files:
            self._prefix.extend(("-f", str(compose_file)))
        self._runner = runner
        self._recovery: list[tuple[str, str]] = []
        configured = set(self._run("config", "--services").splitlines())
        missing = self._ALLOWED_SERVICES - configured
        if missing:
            raise SoakFaultAcceptanceError(
                f"Compose project is missing required services: {', '.join(sorted(missing))}"
            )

    def _run(self, *arguments: str) -> str:
        result = self._runner((*self._prefix, *arguments))
        if result.returncode != 0:
            raise SoakFaultAcceptanceError(
                f"Docker Compose command failed: {' '.join(arguments)}"
            )
        return result.stdout.strip()

    def pause(self, service: str) -> None:
        self._validate_service(service)
        self._run("pause", service)
        self._recovery.append((service, "unpause"))

    def stop(self, service: str) -> None:
        self._validate_service(service)
        self._run("stop", "--timeout", "10", service)
        self._recovery.append((service, "start"))

    def recover(self, service: str) -> None:
        for index in range(len(self._recovery) - 1, -1, -1):
            pending_service, action = self._recovery[index]
            if pending_service == service:
                self._run(action, service)
                del self._recovery[index]
                return
        raise SoakFaultAcceptanceError(f"service {service} has no pending recovery action")

    def recover_all(self) -> None:
        failures: list[str] = []
        while self._recovery:
            service, action = self._recovery.pop()
            try:
                self._run(action, service)
            except SoakFaultAcceptanceError:
                failures.append(service)
        if failures:
            raise SoakFaultAcceptanceError(
                f"failed to restore services: {', '.join(sorted(failures))}"
            )

    def is_running(self, service: str) -> bool:
        self._validate_service(service)
        running = set(self._run("ps", "--status", "running", "--services").splitlines())
        return service in running

    def resource_snapshot(self) -> dict[str, dict[str, int]]:
        snapshot: dict[str, dict[str, int]] = {}
        for service in sorted(self._ALLOWED_SERVICES):
            container_id = self._run("ps", "-q", service)
            if not container_id:
                raise SoakFaultAcceptanceError(f"service {service} has no container")
            result = self._runner(
                ("docker", "stats", "--no-stream", "--format", "{{json .}}", container_id)
            )
            if result.returncode != 0:
                raise SoakFaultAcceptanceError(f"Docker stats failed for service {service}")
            try:
                document = json.loads(result.stdout.strip())
            except json.JSONDecodeError as error:
                raise SoakFaultAcceptanceError(
                    f"Docker stats returned malformed JSON for service {service}"
                ) from error
            if not isinstance(document, dict):
                raise SoakFaultAcceptanceError("Docker stats document must be an object")
            memory = document.get("MemUsage")
            pids = document.get("PIDs")
            if not isinstance(memory, str) or not isinstance(pids, (int, str)):
                raise SoakFaultAcceptanceError("Docker stats omitted memory or PID evidence")
            snapshot[service] = {
                "memory_bytes": parse_memory_bytes(memory.partition("/")[0].strip()),
                "pids": int(pids),
            }
        return snapshot

    @classmethod
    def _validate_service(cls, service: str) -> None:
        if service not in cls._ALLOWED_SERVICES:
            raise SoakFaultAcceptanceError(f"fault service is not allow-listed: {service}")


def parse_memory_bytes(value: str) -> int:
    units = {
        "B": 1,
        "KB": 1000,
        "KIB": 1024,
        "MB": 1000**2,
        "MIB": 1024**2,
        "GB": 1000**3,
        "GIB": 1024**3,
    }
    compact = value.strip().upper().replace(" ", "")
    for unit in sorted(units, key=len, reverse=True):
        if compact.endswith(unit):
            number = compact[: -len(unit)]
            try:
                parsed = float(number)
            except ValueError as error:
                raise SoakFaultAcceptanceError("Docker memory value is malformed") from error
            if not math.isfinite(parsed) or parsed < 0:
                raise SoakFaultAcceptanceError("Docker memory value is invalid")
            return round(parsed * units[unit])
    raise SoakFaultAcceptanceError("Docker memory unit is unsupported")


def _require_loopback_url(value: str, *, label: str) -> str:
    parsed = urlsplit(value.rstrip("/"))
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SoakFaultAcceptanceError(f"{label} must be a credential-free loopback URL")
    return value.rstrip("/")


def _git_commit(root: Path) -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode != 0 or status.stdout.strip():
        raise SoakFaultAcceptanceError("acceptance evidence requires a clean Git working tree")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit.returncode != 0:
        raise SoakFaultAcceptanceError("source commit is unavailable")
    return commit.stdout.strip()


def _catalog_snapshot(client: FullStackClient) -> dict[str, int]:
    _, document = client.json_request(f"/materials?{urlencode({'limit': 100})}")
    items = document.get("items")
    total_count = document.get("total_count")
    if (
        not isinstance(items, list)
        or not isinstance(total_count, int)
        or isinstance(total_count, bool)
        or total_count < len(items)
    ):
        raise SoakFaultAcceptanceError("Catalog response omitted authorized cardinality")
    return {"returned_count": len(items), "total_count": total_count}


def _bundle_snapshot(client: FullStackClient) -> dict[str, Any]:
    _, listed = client.json_request("/export-bundles")
    items = listed.get("items")
    if not isinstance(items, list) or not items:
        raise SoakFaultAcceptanceError("fault acceptance requires an immutable Bundle")
    bundles = [item for item in items if isinstance(item, dict)]
    if not bundles:
        raise SoakFaultAcceptanceError("Bundle list has no typed item")
    bundle = max(bundles, key=lambda item: int(item.get("archive_size_bytes", 0)))
    bundle_id = bundle.get("export_bundle_id")
    if not isinstance(bundle_id, str):
        raise SoakFaultAcceptanceError("Bundle item omitted its identity")
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
        raise SoakFaultAcceptanceError("Bundle authorization omitted transfer evidence")
    content = client.request(
        transfer_url, headers={"Artifact-Transfer-Token": transfer_token}
    ).body
    digest = hashlib.sha256(content).hexdigest()
    if expected_digest not in {digest, f"sha256:{digest}"} or expected_size != len(content):
        raise SoakFaultAcceptanceError("Bundle download digest or size changed")
    return {"bundle_id": bundle_id, "sha256": digest, "size_bytes": len(content)}


def _invariants_match(
    before_catalog: Mapping[str, int],
    after_catalog: Mapping[str, int],
    before_bundle: Mapping[str, Any],
    after_bundle: Mapping[str, Any],
) -> bool:
    return (
        before_catalog.get("total_count") == after_catalog.get("total_count")
        and before_bundle.get("bundle_id") == after_bundle.get("bundle_id")
        and before_bundle.get("sha256") == after_bundle.get("sha256")
        and before_bundle.get("size_bytes") == after_bundle.get("size_bytes")
    )


def _web_probe(web_url: str, *, timeout_seconds: float) -> None:
    try:
        with urlopen(web_url, timeout=timeout_seconds) as response:
            if response.status != 200 or not response.read(1024):
                raise SoakFaultAcceptanceError("web probe returned an invalid response")
    except (OSError, URLError) as error:
        raise SoakFaultAcceptanceError("web endpoint is unavailable") from error


def _wait_for_failure(action: Callable[[], object], *, limit_seconds: float) -> float:
    started = time.perf_counter()
    deadline = started + limit_seconds
    while time.perf_counter() < deadline:
        try:
            action()
        except Exception:
            return time.perf_counter() - started
        time.sleep(0.1)
    raise SoakFaultAcceptanceError("injected outage was not observed before its deadline")


def _wait_for_recovery(action: Callable[[], object], *, limit_seconds: float) -> float:
    started = time.perf_counter()
    deadline = started + limit_seconds
    while time.perf_counter() < deadline:
        try:
            action()
        except Exception:
            time.sleep(0.25)
            continue
        return time.perf_counter() - started
    raise SoakFaultAcceptanceError("service did not recover before its deadline")


def _run_workload(
    *,
    client: FullStackClient,
    recorder: WorkloadRecorder,
    fault_window: threading.Event,
    stop: threading.Event,
    worker_index: int,
    interval_seconds: float,
) -> None:
    operations: tuple[tuple[str, Callable[[], object]], ...] = (
        ("catalog", lambda: _catalog_snapshot(client)),
        ("bundle_list", lambda: client.json_request("/export-bundles")),
        ("health", lambda: client.request("/health", authenticated=False)),
    )
    ordinal = worker_index
    while not stop.is_set():
        name, action = operations[ordinal % len(operations)]
        ordinal += 1
        started_inside_fault = fault_window.is_set()
        started = time.perf_counter()
        error_type: str | None = None
        succeeded = True
        try:
            action()
        except Exception as error:
            succeeded = False
            error_type = type(error).__name__
        recorder.record(
            WorkloadSample(
                name,
                (time.perf_counter() - started) * 1000,
                succeeded,
                started_inside_fault or fault_window.is_set(),
                error_type,
            )
        )
        stop.wait(interval_seconds)


def _resource_growth(
    before: Mapping[str, Mapping[str, int]],
    after: Mapping[str, Mapping[str, int]],
    *,
    limit_bytes: int,
) -> dict[str, Any]:
    services: dict[str, Any] = {}
    passed = True
    for service in sorted(before):
        growth = after[service]["memory_bytes"] - before[service]["memory_bytes"]
        within_limit = growth <= limit_bytes
        passed = passed and within_limit
        services[service] = {
            "after_memory_bytes": after[service]["memory_bytes"],
            "after_pids": after[service]["pids"],
            "before_memory_bytes": before[service]["memory_bytes"],
            "before_pids": before[service]["pids"],
            "memory_growth_bytes": growth,
            "within_growth_limit": within_limit,
        }
    return {"memory_growth_limit_bytes": limit_bytes, "passed": passed, "services": services}


def _fault_result(
    *,
    service: str,
    action: str,
    outage_observed_seconds: float,
    recovery_seconds: float,
    recovery_limit_seconds: float,
) -> dict[str, Any]:
    return {
        "action": action,
        "outage_observed": True,
        "outage_observed_seconds": round(outage_observed_seconds, 6),
        "passed": recovery_seconds <= recovery_limit_seconds,
        "recovery_limit_seconds": recovery_limit_seconds,
        "recovery_seconds": round(recovery_seconds, 6),
        "service": service,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-url", default="http://127.0.0.1:18000/api/v1")
    parser.add_argument("--web-url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compose-file", action="append", type=Path)
    parser.add_argument("--soak-seconds", type=float, default=300)
    parser.add_argument("--fault-hold-seconds", type=float, default=5)
    parser.add_argument("--recovery-limit-seconds", type=float, default=60)
    parser.add_argument("--http-timeout-seconds", type=float, default=2)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--request-interval-ms", type=int, default=250)
    parser.add_argument("--ordinary-p95-limit-ms", type=float, default=2000)
    parser.add_argument("--minimum-materials", type=int, default=10_000)
    parser.add_argument("--memory-growth-limit-mib", type=int, default=512)
    parser.add_argument("--acknowledge-service-disruption", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if not args.acknowledge_service_disruption:
        raise SoakFaultAcceptanceError(
            "the drill stops or pauses local services; pass the explicit disruption acknowledgement"
        )
    if not 30 <= args.soak_seconds <= 3600:
        raise SoakFaultAcceptanceError("soak duration must be between 30 and 3600 seconds")
    if not 1 <= args.fault_hold_seconds <= 30:
        raise SoakFaultAcceptanceError("fault hold must be between 1 and 30 seconds")
    if not 5 <= args.recovery_limit_seconds <= 300:
        raise SoakFaultAcceptanceError("recovery limit must be between 5 and 300 seconds")
    if not 0.5 <= args.http_timeout_seconds <= 10:
        raise SoakFaultAcceptanceError("HTTP timeout must be between 0.5 and 10 seconds")
    if not 1 <= args.concurrency <= 16 or not 10 <= args.request_interval_ms <= 10_000:
        raise SoakFaultAcceptanceError("workload concurrency or interval is outside policy")
    if not 1 <= args.minimum_materials <= 1_000_000:
        raise SoakFaultAcceptanceError("minimum Material count is outside policy")
    if not 1 <= args.memory_growth_limit_mib <= 4096:
        raise SoakFaultAcceptanceError("memory growth limit is outside policy")

    root = args.root.resolve(strict=True)
    source_commit = _git_commit(root)
    base_url = _require_loopback_url(args.base_url, label="API base URL")
    web_url = _require_loopback_url(args.web_url, label="web URL")
    compose_files = args.compose_file or [
        Path("deploy/compose/docker-compose.demo.yml"),
        Path("deploy/performance/docker-compose.production-scale.yml"),
    ]
    resolved_compose: list[Path] = []
    for compose_file in compose_files:
        resolved = (
            (root / compose_file).resolve()
            if not compose_file.is_absolute()
            else compose_file.resolve()
        )
        if root not in resolved.parents or not resolved.is_file():
            raise SoakFaultAcceptanceError("Compose files must exist inside the repository")
        resolved_compose.append(resolved)

    client = FullStackClient(base_url, timeout_seconds=args.http_timeout_seconds)
    client.request("/health", authenticated=False)
    client.authenticate_demo()
    _web_probe(web_url, timeout_seconds=args.http_timeout_seconds)
    before_catalog = _catalog_snapshot(client)
    if before_catalog["total_count"] < args.minimum_materials:
        raise SoakFaultAcceptanceError("Catalog does not meet the declared soak cardinality")
    before_bundle = _bundle_snapshot(client)
    controller = DockerComposeController(resolved_compose)
    before_resources = controller.resource_snapshot()
    recorder = WorkloadRecorder()
    fault_window = threading.Event()
    stop = threading.Event()
    threads = [
        threading.Thread(
            target=_run_workload,
            kwargs={
                "client": client,
                "recorder": recorder,
                "fault_window": fault_window,
                "stop": stop,
                "worker_index": index,
                "interval_seconds": args.request_interval_ms / 1000,
            },
            name=f"cmp-soak-{index}",
            daemon=True,
        )
        for index in range(args.concurrency)
    ]
    started = time.perf_counter()
    faults: list[dict[str, Any]] = []
    try:
        for thread in threads:
            thread.start()
        time.sleep(args.soak_seconds / 2)

        fault_window.set()
        controller.pause("postgres")
        try:
            observed = _wait_for_failure(
                lambda: _catalog_snapshot(client), limit_seconds=args.http_timeout_seconds + 2
            )
            time.sleep(args.fault_hold_seconds)
        finally:
            controller.recover("postgres")
        recovered = _wait_for_recovery(
            lambda: _catalog_snapshot(client), limit_seconds=args.recovery_limit_seconds
        )
        faults.append(
            _fault_result(
                service="postgres",
                action="pause/unpause",
                outage_observed_seconds=observed,
                recovery_seconds=recovered,
                recovery_limit_seconds=args.recovery_limit_seconds,
            )
        )
        fault_window.clear()

        fault_window.set()
        controller.stop("api")
        try:
            observed = _wait_for_failure(
                lambda: client.request("/health", authenticated=False),
                limit_seconds=args.http_timeout_seconds + 2,
            )
            time.sleep(args.fault_hold_seconds)
        finally:
            controller.recover("api")
        recovered = _wait_for_recovery(
            lambda: client.request("/health", authenticated=False),
            limit_seconds=args.recovery_limit_seconds,
        )
        client.authenticate_demo()
        _catalog_snapshot(client)
        faults.append(
            _fault_result(
                service="api",
                action="stop/start",
                outage_observed_seconds=observed,
                recovery_seconds=recovered,
                recovery_limit_seconds=args.recovery_limit_seconds,
            )
        )
        fault_window.clear()

        fault_window.set()
        controller.stop("worker")
        try:
            if controller.is_running("worker"):
                raise SoakFaultAcceptanceError("worker stop fault was not observed")
            observed = 0.0
            time.sleep(args.fault_hold_seconds)
        finally:
            controller.recover("worker")
        recovery_started = time.perf_counter()
        _wait_for_recovery(
            lambda: controller.is_running("worker") or (_ for _ in ()).throw(RuntimeError()),
            limit_seconds=args.recovery_limit_seconds,
        )
        recovered = time.perf_counter() - recovery_started
        faults.append(
            _fault_result(
                service="worker",
                action="stop/start",
                outage_observed_seconds=observed,
                recovery_seconds=recovered,
                recovery_limit_seconds=args.recovery_limit_seconds,
            )
        )
        fault_window.clear()

        fault_window.set()
        controller.stop("web")
        try:
            observed = _wait_for_failure(
                lambda: _web_probe(web_url, timeout_seconds=args.http_timeout_seconds),
                limit_seconds=args.http_timeout_seconds + 2,
            )
            time.sleep(args.fault_hold_seconds)
        finally:
            controller.recover("web")
        recovered = _wait_for_recovery(
            lambda: _web_probe(web_url, timeout_seconds=args.http_timeout_seconds),
            limit_seconds=args.recovery_limit_seconds,
        )
        faults.append(
            _fault_result(
                service="web",
                action="stop/start",
                outage_observed_seconds=observed,
                recovery_seconds=recovered,
                recovery_limit_seconds=args.recovery_limit_seconds,
            )
        )
        fault_window.clear()

        time.sleep(args.soak_seconds / 2)
    finally:
        fault_window.set()
        stop.set()
        for thread in threads:
            thread.join(timeout=args.http_timeout_seconds + 5)
        controller.recover_all()

    duration = time.perf_counter() - started
    after_catalog = _catalog_snapshot(client)
    after_bundle = _bundle_snapshot(client)
    after_resources = controller.resource_snapshot()
    workload = recorder.summary(p95_limit_ms=args.ordinary_p95_limit_ms)
    resources = _resource_growth(
        before_resources,
        after_resources,
        limit_bytes=args.memory_growth_limit_mib * 1024 * 1024,
    )
    invariants = {
        "after_bundle": after_bundle,
        "after_catalog": after_catalog,
        "before_bundle": before_bundle,
        "before_catalog": before_catalog,
        "exact_material_cardinality_and_bundle_bytes_preserved": _invariants_match(
            before_catalog, after_catalog, before_bundle, after_bundle
        ),
    }
    passed = (
        duration >= args.soak_seconds
        and len(faults) == 4
        and all(fault["passed"] for fault in faults)
        and workload["passed"]
        and resources["passed"]
        and invariants["exact_material_cardinality_and_bundle_bytes_preserved"]
    )
    report: dict[str, Any] = {
        "claims": {
            "docker_demo_soak_fault_gate_passed": passed,
            "production_object_storage_fault_in_scope": False,
            "solver_execution_in_scope": False,
        },
        "created_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(duration, 6),
        "environment": {
            "api_base_url": base_url,
            "compose_files": [str(path.relative_to(root)) for path in resolved_compose],
            "concurrency": args.concurrency,
            "fault_hold_seconds": args.fault_hold_seconds,
            "http_timeout_seconds": args.http_timeout_seconds,
            "request_interval_ms": args.request_interval_ms,
            "soak_seconds": args.soak_seconds,
            "web_url": web_url,
        },
        "faults": faults,
        "invariants": invariants,
        "passed": passed,
        "resources": resources,
        "schema": "cmp.soak-fault-acceptance.v1",
        "source_commit": source_commit,
        "workload": workload,
    }
    output = args.output or (
        root
        / ".cache"
        / "soak-fault-acceptance"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    digest = write_report(output, report)
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": passed,
                "report_sha256": digest,
            },
            separators=(",", ":"),
        )
    )
    if not passed:
        raise SoakFaultAcceptanceError("soak/fault acceptance failed; inspect the signed report")


if __name__ == "__main__":
    try:
        main()
    except (PerformanceAcceptanceError, SoakFaultAcceptanceError) as error:
        raise SystemExit(str(error)) from error
