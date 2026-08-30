"""Generate the independent Decimal oracle manifest for linear-viscoelastic calibration.

This file intentionally imports no ``cmp`` package, SciPy, NumPy, Arrow, unit converter,
or production serializer.  The oracle is a high-precision arithmetic reference for the
closed-form equations, response/objective identity, digest envelope, and deterministic SVD
rank fixtures.  It is not a quality-threshold authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 80
PI = Decimal("3.141592653589793238462643383279502884197169399375105820974944592307816406286")


def relaxation(
    g_inf: Decimal, moduli: tuple[Decimal, ...], taus: tuple[Decimal, ...], time_s: Decimal
) -> Decimal:
    return g_inf + sum(
        (modulus * (-(time_s / tau)).exp() for modulus, tau in zip(moduli, taus, strict=True)),
        Decimal(0),
    )


def dma_storage(
    g_inf: Decimal, moduli: tuple[Decimal, ...], taus: tuple[Decimal, ...], frequency_hz: Decimal
) -> Decimal:
    omega = Decimal(2) * PI * frequency_hz
    return g_inf + sum(
        (
            modulus * (omega * tau) ** 2 / (Decimal(1) + (omega * tau) ** 2)
            for modulus, tau in zip(moduli, taus, strict=True)
        ),
        Decimal(0),
    )


def dma_loss(
    moduli: tuple[Decimal, ...], taus: tuple[Decimal, ...], frequency_hz: Decimal
) -> Decimal:
    omega = Decimal(2) * PI * frequency_hz
    return sum(
        (
            modulus * omega * tau / (Decimal(1) + (omega * tau) ** 2)
            for modulus, tau in zip(moduli, taus, strict=True)
        ),
        Decimal(0),
    )


def weighted_residual(
    predicted: Decimal, observed: Decimal, wd: Decimal, wdc: Decimal, q: Decimal, scale_pa: Decimal
) -> Decimal:
    return (wd * wdc * q).sqrt() * (predicted - observed) / scale_pa


def bic(rss: Decimal, m: int, parameter_count: int) -> Decimal:
    return Decimal(m) * (rss / Decimal(m)).ln() + Decimal(parameter_count) * Decimal(m).ln()


def digest_envelope(
    header: bytes, payload: bytes, rule: str = "linear_viscoelastic_selected_arrays@1.0.0"
) -> str:
    value = (
        rule.encode("ascii")
        + b"\n"
        + len(header).to_bytes(8, "big")
        + header
        + len(payload).to_bytes(8, "big")
        + payload
    )
    return hashlib.sha256(value).hexdigest()


def oracle_cases() -> dict[str, object]:
    params = (Decimal("4"), Decimal("2"), Decimal("0.1"))
    g_inf, g1, tau1 = params
    selected_header = json.dumps(
        {
            "rule_version": "linear_viscoelastic_selected_arrays@1.0.0",
            "dtype": "ieee754-binary64",
            "byte_order": "little",
            "layout": "C",
            "shape": [2, 2],
            "channels": ["time", "modulus"],
            "source_ordinals": [1, 2],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    selected_payload = struct.pack("<4d", Decimal(1), Decimal(2), Decimal(3), Decimal(4))
    return {
        "R01_relaxation_closed_form": {
            "value": str(relaxation(g_inf, (g1,), (tau1,), Decimal("0.1")))
        },
        "R02_dma_storage_closed_form": {
            "value": str(dma_storage(g_inf, (g1,), (tau1,), Decimal("1")))
        },
        "R03_dma_loss_closed_form": {"value": str(dma_loss((g1,), (tau1,), Decimal("1")))},
        "R07_response_residual_identity": {
            "value": str(
                weighted_residual(
                    Decimal("4"),
                    Decimal("5"),
                    Decimal("1"),
                    Decimal("1"),
                    Decimal("0.25"),
                    Decimal("2"),
                )
            )
        },
        "R08_bic_rule": {"value": str(bic(Decimal("2"), 6, 3))},
        "R09_svd_rank": {
            "algorithm": "terminal_scaled_jacobian_svd",
            "threshold": "max(m,p)*float64_eps*sigma_max",
            "matrix": [[1, 0], [0, 1], [0, 0]],
            "expected_rank": 2,
            "expected_singular_values": ["1", "1"],
        },
        "R10_domain_extrapolation_rank": {"policy": "observed_only"},
        "R11_decimal_pi": {"pi": str(PI)},
        "R12_objective_weights": {"storage": "0.5", "loss": "0.5", "sum": "1"},
        "R13_exact_selected_array_digest": {
            "rule": "linear_viscoelastic_selected_arrays@1.0.0",
            "matrix": [["1", "2"], ["3", "4"]],
            "channels": ["time", "modulus"],
            "source_ordinals": [1, 2],
            "digest": digest_envelope(selected_header, selected_payload),
        },
        "R14_excluded_ordinal": {"partition": "EXCLUDED", "reason": "INSTANTANEOUS_LIMIT"},
        "R15_profile_mode": {"schema_version": "1.2.0", "deformation_mode": "shear"},
        "R16_failure_recovery": {
            "failure_code": "CALCULATION_FAILED",
            "recovery": "new immutable Plan/Run",
        },
        "R17_selection": {"selection": "engineer_only", "recommendation_is_not_selection": True},
        "R18_export_regression": {"status": "existing_exporters_only"},
        "R19_loss_factor_rejection": {"code": "INPUT_ABSOLUTE_MODULUS_CHANNEL_REQUIRED"},
        "R20_legacy_regression": {"status": "reference_prony_and_tts_unchanged"},
    }


def generate(path: Path) -> None:
    document = {
        "oracle_version": "linear-viscoelastic-oracle@1.0.0",
        "implementation": "independent_decimal_fixed_high_precision",
        "production_imports": [],
        "quality_thresholds": [],
        "units": {
            "modulus": "Pa",
            "time": "s",
            "frequency": "Hz",
            "angular_frequency": "rad/s",
        },
        "comparison_tolerances": {
            "closed_form_relative": "5e-15",
            "closed_form_absolute": "5e-15",
            "bic_absolute": "5e-14",
            "rank_singular_absolute": "5e-15",
            "plugin_residual_absolute": "5e-8",
            "plugin_objective_absolute": "5e-8",
            "plugin_bic_absolute": "5e-7",
        },
        "cases": oracle_cases(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/fixtures/linear_viscoelastic/oracle-manifest.json"),
    )
    args = parser.parse_args(argv)
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
