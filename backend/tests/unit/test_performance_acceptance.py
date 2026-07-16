import json
from pathlib import Path

import pytest
from cmp.tools.performance_acceptance import (
    FullStackClient,
    PerformanceAcceptanceError,
    build_inline_bundle_fixture,
    latency_summary,
    percentile,
    verify_report,
    write_report,
)


def test_nearest_rank_percentiles_and_summary_are_deterministic() -> None:
    samples = [10.0, 2.0, 4.0, 8.0, 6.0]

    assert percentile(samples, 50) == 6.0
    assert percentile(samples, 95) == 10.0
    assert latency_summary(samples) == {
        "max_ms": 10.0,
        "p50_ms": 6.0,
        "p95_ms": 10.0,
        "p99_ms": 10.0,
        "sample_count": 5,
        "samples_ms": samples,
    }


@pytest.mark.parametrize("samples", ([], [-1.0], [float("inf")], [float("nan")]))
def test_percentile_rejects_missing_or_invalid_samples(samples: list[float]) -> None:
    with pytest.raises(ValueError, match=r"samples|finite"):
        percentile(samples, 95)


def test_inline_bundle_fixture_uses_real_deterministic_builder() -> None:
    result = build_inline_bundle_fixture(1024 * 1024, seed=7)

    assert result["component_count"] == 1
    assert result["input_size_bytes"] == 1024 * 1024
    assert result["archive_size_bytes"] > 1024 * 1024
    assert result["rng"]["seed"] == 7


def test_performance_report_digest_and_canonical_encoding(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    document = {
        "claims": {"bounded_local_gate_passed": True},
        "passed": True,
        "schema": "cmp.performance-security-acceptance.v1",
        "source_commit": "a" * 40,
    }

    digest = write_report(output, document)

    assert len(digest) == 64
    assert verify_report(output) == document


def test_performance_report_rejects_substitution(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    write_report(output, {"passed": True})
    (output / "report.json").write_text(json.dumps({"passed": False}), encoding="utf-8")

    with pytest.raises(PerformanceAcceptanceError, match="digest"):
        verify_report(output)


@pytest.mark.parametrize(
    "url",
    (
        "file:///tmp/api",
        "http://user:password@localhost/api/v1",
        "http://localhost/api/v1?token=secret",
    ),
)
def test_full_stack_client_rejects_unsafe_base_url(url: str) -> None:
    with pytest.raises(PerformanceAcceptanceError, match="base URL"):
        FullStackClient(url)
