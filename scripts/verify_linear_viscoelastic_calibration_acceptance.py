"""Verify linear-viscoelastic calibration journeys through the live API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cmp.tools.linear_viscoelastic_acceptance_http import LinearViscoelasticAcceptanceError
from cmp.tools.linear_viscoelastic_calibration_workflow import (
    verify,
    verify_dma_temperature_sweep,
    verify_public_shear_dma,
    verify_readback,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://api:8000/api/v1")
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("plugins/production/linear_viscoelastic_calibrator"),
    )
    parser.add_argument(
        "--public-data",
        action="store_true",
        help="run the public DaRUS shear-DMA path without IR promotion",
    )
    parser.add_argument(
        "--public-fixture",
        type=Path,
        default=Path("fixtures/public/smp-shear-dma-283.15k-v1.csv"),
    )
    parser.add_argument("--public-manifest", type=Path)
    parser.add_argument(
        "--dma-temperature-sweep",
        action="store_true",
        help="run fixed-frequency DMA through TTS, Prony calibration, and Selection",
    )
    parser.add_argument(
        "--dma-fixture",
        type=Path,
        default=Path("fixtures/synthetic/dma-temperature-sweep-linear-viscoelastic-v1.json"),
    )
    parser.add_argument("--readback-model-id")
    parser.add_argument("--readback-revision-id")
    parser.add_argument("--readback-sha256")
    args = parser.parse_args(argv)
    readback_values = (
        args.readback_model_id,
        args.readback_revision_id,
        args.readback_sha256,
    )
    if any(readback_values) and not all(readback_values):
        parser.error("all three --readback-* values are required together")
    if args.public_data and args.dma_temperature_sweep:
        parser.error("choose either --public-data or --dma-temperature-sweep")
    if (args.public_data or args.dma_temperature_sweep) and any(readback_values):
        parser.error("data workflows cannot be combined with --readback-* values")
    try:
        if all(readback_values):
            report = verify_readback(
                args.api_base_url,
                material_model_id=args.readback_model_id,
                material_model_revision_id=args.readback_revision_id,
                material_model_sha256=args.readback_sha256,
            )
        elif args.public_data:
            report = verify_public_shear_dma(
                args.api_base_url,
                args.package_root.resolve(),
                args.public_fixture.resolve(),
                args.public_manifest.resolve() if args.public_manifest is not None else None,
            )
        elif args.dma_temperature_sweep:
            report = verify_dma_temperature_sweep(
                args.api_base_url,
                args.package_root.resolve(),
                args.dma_fixture.resolve(),
            )
        else:
            report = verify(args.api_base_url, args.package_root.resolve())
    except LinearViscoelasticAcceptanceError as error:
        parser.exit(1, f"acceptance failed: {error}\n")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
