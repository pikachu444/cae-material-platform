from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess

import pytest
from cmp.tools.soak_fault_acceptance import (
    DockerComposeController,
    SoakFaultAcceptanceError,
    WorkloadRecorder,
    WorkloadSample,
    _invariants_match,
    _require_loopback_url,
    _resource_growth,
    parse_memory_bytes,
)


def test_workload_summary_distinguishes_expected_fault_errors() -> None:
    recorder = WorkloadRecorder()
    recorder.record(WorkloadSample("catalog", 10.0, True, False))
    recorder.record(WorkloadSample("catalog", 12.0, True, False))
    recorder.record(WorkloadSample("catalog", 2.0, False, True, "TimeoutError"))
    recorder.record(WorkloadSample("health", 3.0, True, False))

    summary = recorder.summary(p95_limit_ms=100)

    assert summary["passed"] is True
    assert summary["ordinary_failures"] == 0
    assert summary["operations"]["catalog"]["fault_window_failures"] == 1
    assert summary["operations"]["catalog"]["ordinary_latency"]["p95_ms"] == 12.0


def test_workload_summary_rejects_ordinary_failure_and_latency_regression() -> None:
    recorder = WorkloadRecorder()
    recorder.record(WorkloadSample("catalog", 2500.0, True, False))
    recorder.record(WorkloadSample("health", 5.0, False, False, "RuntimeError"))

    summary = recorder.summary(p95_limit_ms=2000)

    assert summary["passed"] is False
    assert summary["ordinary_failures"] == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    (("512B", 512), ("1.5 MiB", 1572864), ("2GB", 2000000000)),
)
def test_docker_memory_parser_is_unit_explicit(value: str, expected: int) -> None:
    assert parse_memory_bytes(value) == expected


def test_compose_controller_restores_services_in_reverse_fault_order() -> None:
    commands: list[tuple[str, ...]] = []

    def run(arguments: Sequence[str]) -> CompletedProcess[str]:
        command = tuple(arguments)
        commands.append(command)
        stdout = ""
        if command[-2:] == ("config", "--services"):
            stdout = "api\npostgres\nweb\nworker\n"
        return CompletedProcess(command, 0, stdout, "")

    controller = DockerComposeController([Path("demo.yml")], runner=run)
    controller.stop("api")
    controller.pause("postgres")

    controller.recover_all()

    assert commands[-2][-2:] == ("unpause", "postgres")
    assert commands[-1][-2:] == ("start", "api")


def test_compose_controller_rejects_non_allowlisted_fault() -> None:
    def run(arguments: Sequence[str]) -> CompletedProcess[str]:
        return CompletedProcess(
            tuple(arguments), 0, "api\npostgres\nweb\nworker\n", ""
        )

    controller = DockerComposeController([Path("demo.yml")], runner=run)

    with pytest.raises(SoakFaultAcceptanceError, match="allow-listed"):
        controller.stop("object-storage")


def test_loopback_guard_rejects_remote_or_credentialed_targets() -> None:
    assert _require_loopback_url("http://127.0.0.1:18000/api/v1", label="API")
    with pytest.raises(SoakFaultAcceptanceError, match="loopback"):
        _require_loopback_url("https://example.com/api/v1", label="API")
    with pytest.raises(SoakFaultAcceptanceError, match="loopback"):
        _require_loopback_url("http://user:secret@localhost/api/v1", label="API")


def test_final_invariants_pin_catalog_cardinality_and_bundle_bytes() -> None:
    catalog = {"returned_count": 100, "total_count": 10000}
    bundle = {"bundle_id": "bundle-1", "sha256": "a" * 64, "size_bytes": 42}

    assert _invariants_match(catalog, dict(catalog), bundle, dict(bundle)) is True
    assert (
        _invariants_match(
            catalog,
            {"returned_count": 100, "total_count": 9999},
            bundle,
            dict(bundle),
        )
        is False
    )


def test_resource_growth_gate_allows_reclaimed_memory_and_rejects_growth() -> None:
    before = {"api": {"memory_bytes": 100, "pids": 2}}

    reclaimed = _resource_growth(
        before, {"api": {"memory_bytes": 80, "pids": 2}}, limit_bytes=10
    )
    grown = _resource_growth(
        before, {"api": {"memory_bytes": 111, "pids": 2}}, limit_bytes=10
    )

    assert reclaimed["passed"] is True
    assert grown["passed"] is False
