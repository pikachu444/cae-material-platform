"""Deterministic minimal client generator for the T-02 health contract."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml


def _load_contract(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("OpenAPI contract must be a mapping")
    return cast(dict[str, Any], data)


def _health_path(contract: Mapping[str, Any]) -> str:
    paths = contract.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI contract has no paths mapping")
    for path, item in paths.items():
        if not isinstance(path, str) or not isinstance(item, dict):
            continue
        operation = item.get("get")
        if isinstance(operation, dict) and operation.get("operationId") == "getHealth":
            return path
    raise ValueError("OpenAPI contract has no getHealth operation")


def render_client(contract_path: Path) -> str:
    """Render the intentionally small generated client from the source contract."""

    path = _health_path(_load_contract(contract_path))
    return f'''"""Generated from contracts/http/openapi.yaml; do not edit manually."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class HealthResponse:
    status: str
    service: str
    version: str


class Client:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_health(self) -> HealthResponse:
        request = Request(self._base_url + "{path}", method="GET")
        with urlopen(request, timeout=self._timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("health response must be a JSON object")
        return HealthResponse(
            status=str(payload["status"]),
            service=str(payload["service"]),
            version=str(payload["version"]),
        )
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the baseline Python API client.")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_client(args.contract), encoding="utf-8")
    print(f"generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
