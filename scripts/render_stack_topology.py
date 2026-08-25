"""Render the canonical Compose demo from the versioned stack topology."""

from __future__ import annotations

import argparse
import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

_HEADER = "# Generated from deploy/stack/topology.yaml; do not edit directly.\n"


def load_topology(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("stack topology must be a schema_version 1 mapping")
    compose = document.get("compose")
    if not isinstance(compose, dict):
        raise ValueError("stack topology must contain a compose mapping")
    services = compose.get("services")
    if not isinstance(services, dict):
        raise ValueError("stack topology compose must contain services")
    order = document.get("service_order")
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ValueError("stack topology service_order must be a string list")
    missing = [service for service in order if service not in services]
    if missing:
        raise ValueError(f"stack topology service_order references missing services: {missing}")
    return document


def render_compose(topology: Mapping[str, Any]) -> str:
    compose = copy.deepcopy(topology["compose"])
    compose.pop("status", None)
    common_environment = topology.get("application_environment")
    if not isinstance(common_environment, dict):
        raise ValueError("stack topology must contain application_environment")
    services = compose["services"]
    api_environment = services["api"]["environment"]
    if not isinstance(api_environment, dict):
        raise ValueError("stack topology Compose api environment must be a mapping")
    services["api"]["environment"] = {**common_environment, **api_environment}
    services["worker"]["environment"] = services["api"]["environment"]
    return _HEADER + yaml.safe_dump(
        compose,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, default=Path("deploy/stack/topology.yaml"))
    parser.add_argument(
        "--compose", type=Path, default=Path("deploy/compose/docker-compose.demo.yml")
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rendered = render_compose(load_topology(args.topology))
    if args.check:
        if not args.compose.is_file() or args.compose.read_text(encoding="utf-8") != rendered:
            print(
                f"stack topology drift: run {Path(__file__).as_posix()} --write",
            )
            return 1
        print("stack topology matches generated Compose")
        return 0
    args.compose.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote {args.compose}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
