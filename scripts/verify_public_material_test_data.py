"""Validate manifest-declared public material test-data archives."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cmp.modules.testing.domain.public_material_test_data import (
    PublicMaterialTestDataError,
    load_public_material_test_data_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        action="append",
        type=Path,
        required=True,
        help="repeat for every public test-data manifest to validate",
    )
    args = parser.parse_args(argv)
    reports: list[dict[str, object]] = []
    try:
        for manifest in args.manifest:
            dataset = load_public_material_test_data_manifest(manifest.resolve())
            reports.append(
                {
                    "manifest": str(dataset.manifest_path),
                    "archive": str(dataset.archive_path),
                    "archive_sha256": dataset.archive_sha256,
                    "doi": dataset.source["doi"],
                    "license": dataset.source["license"],
                    "experiment_counts": dict(
                        sorted(Counter(item.kind for item in dataset.experiments).items())
                    ),
                    "eligible_frequency_group_count": len(dataset.eligible_frequency_groups),
                    "export_eligible_count": sum(
                        item.export_eligible for item in dataset.experiments
                    ),
                }
            )
    except PublicMaterialTestDataError as error:
        parser.exit(1, f"public material test-data validation failed: {error}\n")
    print(json.dumps(reports, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
