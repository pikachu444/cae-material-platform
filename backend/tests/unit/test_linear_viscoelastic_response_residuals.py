from __future__ import annotations

import io
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from cmp.modules.modeling.domain.linear_viscoelastic_response_residuals import (
    InvalidLinearViscoelasticResponseResiduals,
    LinearViscoelasticResponseChannel,
    LinearViscoelasticResponsePartition,
    linear_viscoelastic_response_residuals_from_parquet,
)


def _parquet_bytes(columns: dict[str, pa.Array]) -> bytes:
    stream = io.BytesIO()
    cast(Any, pq.write_table)(pa.table(columns), stream, compression=None)
    return stream.getvalue()


def _valid_columns() -> dict[str, pa.Array]:
    return {
        "ordinal": pa.array([0, 1], type=pa.int64()),
        "channel": pa.array(["relaxation", "relaxation"], type=pa.string()),
        "observed": pa.array([12.0, 10.0], type=pa.float64()),
        "predicted": pa.array([11.5, 10.25], type=pa.float64()),
        "residual": pa.array([-0.5, 0.25], type=pa.float64()),
        "partition": pa.array(["CALIBRATION", "HOLDOUT"], type=pa.string()),
    }


def test_response_residual_parquet_reads_exact_typed_rows() -> None:
    rows = linear_viscoelastic_response_residuals_from_parquet(
        _parquet_bytes(_valid_columns())
    )

    assert rows[0].ordinal == 0
    assert rows[0].channel is LinearViscoelasticResponseChannel.RELAXATION
    assert rows[0].partition is LinearViscoelasticResponsePartition.CALIBRATION
    assert rows[1].observed == 10.0
    assert rows[1].predicted == 10.25
    assert rows[1].residual == 0.25


@pytest.mark.parametrize("failure", ("column", "type", "null"))
def test_response_residual_parquet_rejects_non_exact_schema(failure: str) -> None:
    columns = _valid_columns()
    if failure == "column":
        columns["unexpected"] = pa.array([0, 0], type=pa.int64())
    elif failure == "type":
        columns["ordinal"] = pa.array([0, 1], type=pa.int32())
    else:
        columns["observed"] = pa.array([12.0, None], type=pa.float64())

    with pytest.raises(InvalidLinearViscoelasticResponseResiduals):
        linear_viscoelastic_response_residuals_from_parquet(_parquet_bytes(columns))


@pytest.mark.parametrize(
    ("column", "value"),
    (("channel", "unknown"), ("partition", "LATEST")),
)
def test_response_residual_parquet_rejects_unbounded_enums(
    column: str, value: str
) -> None:
    columns = _valid_columns()
    columns[column] = pa.array([value, value], type=pa.string())

    with pytest.raises(InvalidLinearViscoelasticResponseResiduals):
        linear_viscoelastic_response_residuals_from_parquet(_parquet_bytes(columns))
