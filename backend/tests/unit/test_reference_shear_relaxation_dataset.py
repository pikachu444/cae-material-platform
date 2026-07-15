import pytest
from cmp.modules.datasets.domain.reference_shear_relaxation import (
    InvalidShearRelaxationData,
    ShearRelaxationMapping,
    parse_shear_relaxation_csv,
    shear_relaxation_parquet_bytes,
    shear_relaxation_points_from_parquet,
)


def test_csv_mapping_normalizes_time_and_modulus_and_round_trips_parquet() -> None:
    parsed = parse_shear_relaxation_csv(
        b"time_ms,G_MPa\n0,1200\n100,1000\n1000,700\n10000,600\n",
        ShearRelaxationMapping("time_ms", "G_MPa", "ms", "MPa"),
    )
    assert [point.time_s for point in parsed.normalized_points] == [0.0, 0.1, 1.0, 10.0]
    assert [point.shear_modulus_pa for point in parsed.normalized_points] == [
        1.2e9,
        1.0e9,
        0.7e9,
        0.6e9,
    ]
    encoded = shear_relaxation_parquet_bytes(parsed.normalized_points)
    assert shear_relaxation_points_from_parquet(encoded) == parsed.normalized_points


def test_curve_rejects_increasing_modulus_and_non_increasing_time() -> None:
    mapping = ShearRelaxationMapping("time", "G", "s", "Pa")
    with pytest.raises(InvalidShearRelaxationData, match="non-increasing"):
        parse_shear_relaxation_csv(b"time,G\n0,10\n1,9\n2,11\n", mapping)
    with pytest.raises(InvalidShearRelaxationData, match="strictly increasing"):
        parse_shear_relaxation_csv(b"time,G\n0,10\n1,9\n1,8\n", mapping)


def test_mapping_requires_explicit_supported_units() -> None:
    with pytest.raises(InvalidShearRelaxationData, match="time unit"):
        ShearRelaxationMapping("time", "G", "day", "Pa")
    with pytest.raises(InvalidShearRelaxationData, match="modulus unit"):
        ShearRelaxationMapping("time", "G", "s", "psi")
