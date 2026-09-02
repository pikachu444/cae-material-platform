"""Typed read contract for immutable linear-viscoelastic response evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq

LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_COLUMNS = (
    "ordinal",
    "channel",
    "observed",
    "predicted",
    "residual",
    "partition",
)
LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_MAX_ROWS = 1_000_000


class InvalidLinearViscoelasticResponseResiduals(ValueError):
    """The immutable response-residual Artifact does not satisfy its exact schema."""


class LinearViscoelasticResponseChannel(StrEnum):
    RELAXATION = "relaxation"
    DMA_STORAGE = "dma_storage"
    DMA_LOSS = "dma_loss"


class LinearViscoelasticResponsePartition(StrEnum):
    CALIBRATION = "CALIBRATION"
    HOLDOUT = "HOLDOUT"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True, slots=True)
class LinearViscoelasticResponseResidualRow:
    ordinal: int
    channel: LinearViscoelasticResponseChannel
    observed: float
    predicted: float
    residual: float
    partition: LinearViscoelasticResponsePartition


def linear_viscoelastic_response_residuals_from_parquet(
    value: bytes,
) -> tuple[LinearViscoelasticResponseResidualRow, ...]:
    """Read the exact bounded response-residual Parquet schema without recalculation."""

    try:
        table = cast(Any, pq.read_table)(pa.BufferReader(value))
    except Exception as error:
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact is not valid Parquet"
        ) from error

    if tuple(table.column_names) != LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_COLUMNS:
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact columns are not exact"
        )
    expected_types = (
        pa.int64(),
        pa.string(),
        pa.float64(),
        pa.float64(),
        pa.float64(),
        pa.string(),
    )
    if any(
        not table.schema.field(index).type.equals(expected_type)
        for index, expected_type in enumerate(expected_types)
    ):
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact column types are not exact"
        )
    if table.num_rows < 1:
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact must contain at least one row"
        )
    if table.num_rows > LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_MAX_ROWS:
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact exceeds the read projection row limit"
        )
    if any(table.column(index).null_count for index in range(table.num_columns)):
        raise InvalidLinearViscoelasticResponseResiduals(
            "response-residual Artifact cannot contain null values"
        )

    rows: list[LinearViscoelasticResponseResidualRow] = []
    for index, item in enumerate(table.to_pylist()):
        ordinal = int(item["ordinal"])
        if ordinal < 0:
            raise InvalidLinearViscoelasticResponseResiduals(
                f"response-residual row {index} has a negative ordinal"
            )
        try:
            channel = LinearViscoelasticResponseChannel(str(item["channel"]))
            partition = LinearViscoelasticResponsePartition(str(item["partition"]))
        except ValueError as error:
            raise InvalidLinearViscoelasticResponseResiduals(
                f"response-residual row {index} has an unsupported channel or partition"
            ) from error
        observed = float(item["observed"])
        predicted = float(item["predicted"])
        residual = float(item["residual"])
        if not all(math.isfinite(number) for number in (observed, predicted, residual)):
            raise InvalidLinearViscoelasticResponseResiduals(
                f"response-residual row {index} contains a non-finite value"
            )
        rows.append(
            LinearViscoelasticResponseResidualRow(
                ordinal=ordinal,
                channel=channel,
                observed=observed,
                predicted=predicted,
                residual=residual,
                partition=partition,
            )
        )
    return tuple(rows)


__all__ = (
    "LINEAR_VISCOELASTIC_RESPONSE_RESIDUAL_COLUMNS",
    "InvalidLinearViscoelasticResponseResiduals",
    "LinearViscoelasticResponseChannel",
    "LinearViscoelasticResponsePartition",
    "LinearViscoelasticResponseResidualRow",
    "linear_viscoelastic_response_residuals_from_parquet",
)
