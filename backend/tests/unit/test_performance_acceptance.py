import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from cmp.tools.performance_acceptance import (
    DeterministicByteSource,
    FullStackClient,
    PerformanceAcceptanceError,
    build_inline_bundle_fixture,
    latency_summary,
    percentile,
    verify_report,
    write_report,
)
from cmp.tools.performance_fixture import PerformanceFixtureError, _fixture_rows, _normalized_dsn


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


def test_large_fixture_source_is_reproducible_and_chunk_bounded() -> None:
    source = DeterministicByteSource(5 * 1024 * 1024 + 17, seed=11)
    digest = source.sha256(chunk_size=512 * 1024)
    replay = DeterministicByteSource(source.size_bytes, seed=11)

    assert digest == replay.sha256(chunk_size=1024 * 1024)
    assert source.maximum_generated_chunk_bytes == 512 * 1024
    assert replay.maximum_generated_chunk_bytes == 1024 * 1024
    assert replay.maximum_generated_chunk_bytes < source.size_bytes


def test_material_scale_fixture_rows_are_typed_deterministic_revisions() -> None:
    organization_id = UUID("10000000-0000-4000-8000-000000000001")
    project_id = UUID("10000000-0000-4000-8000-000000000002")
    created_at = datetime(2026, 7, 17, tzinfo=UTC)

    identities, revisions = _fixture_rows(
        organization_id=organization_id,
        project_id=project_id,
        start=1,
        count=2,
        created_at=created_at,
    )
    replay_identities, replay_revisions = _fixture_rows(
        organization_id=organization_id,
        project_id=project_id,
        start=1,
        count=2,
        created_at=created_at,
    )

    assert identities == replay_identities
    assert revisions == replay_revisions
    assert revisions[0]["schema_version"] == "2.0.0"
    assert revisions[0]["material_class"] == "metal"
    assert len(str(revisions[0]["content_hash"])) == 64


def test_material_scale_fixture_refuses_unsafe_targets() -> None:
    with pytest.raises(PerformanceFixtureError, match="loopback"):
        _normalized_dsn(
            "postgresql://owner:secret@database.example/cmp_acceptance",
            allow_non_loopback=False,
        )
    with pytest.raises(PerformanceFixtureError, match="application database"):
        _normalized_dsn(
            "postgresql://owner:secret@127.0.0.1/postgres",
            allow_non_loopback=False,
        )


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


def test_full_stack_client_does_not_duplicate_absolute_api_base_path() -> None:
    client = FullStackClient("http://127.0.0.1:5173/api/v1")

    assert client.url_for("/materials") == "http://127.0.0.1:5173/api/v1/materials"
    assert client.url_for("/api/v1/artifacts/one/content") == (
        "http://127.0.0.1:5173/api/v1/artifacts/one/content"
    )
