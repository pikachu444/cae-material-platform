"""Validate the measurable hard gates for the reference-layout design review."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs" / "15-demo" / "images" / "ux-layout-review"
MEASUREMENTS = EVIDENCE / "measurements.json"
VIEWPORTS = {(1366, 768), (1440, 900), (1920, 1080)}
SCREENS = {"materials", "detail", "modeling", "export", "card"}


def region(entry: dict, role: str) -> dict:
    return next(item for item in entry["regions"] if item["role"] == role)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


entries = json.loads(MEASUREMENTS.read_text(encoding="utf-8"))
index = {
    (entry["screen"], entry["viewport"]["width"], entry["viewport"]["height"]): entry
    for entry in entries
}

require(len(index) == len(SCREENS) * len(VIEWPORTS), "missing screen/viewport measurements")

for screen in SCREENS:
    for width, height in VIEWPORTS:
        entry = index[(screen, width, height)]
        require(entry["outerMarginTotal"] <= (48 if width >= 1440 else 40), f"{screen}: outer margin")
        require(entry["nestedCards"] == 0, f"{screen}: nested card detected")
        require(entry["typography"]["body"] == "14px", f"{screen}: body typography")
        for item in entry["regions"]:
            require(item["radius"] == "0px", f"{screen}: rounded workspace region")
            require(item["shadow"] == "none", f"{screen}: shadowed workspace region")
        image = EVIDENCE / f"{screen}-{width}x{height}.png"
        require(image.is_file() and image.stat().st_size > 0, f"missing capture: {image.name}")

materials_1366 = index[("materials", 1366, 768)]
materials_1440 = index[("materials", 1440, 900)]
require(region(materials_1366, "context")["width"] == 0, "1366 Materials context must close")
require(region(materials_1366, "result-datasheet")["width"] >= 1100, "1366 results too narrow")
require(220 <= region(materials_1440, "explorer-filter")["width"] <= 250, "Materials Tree width")
require(region(materials_1440, "result-datasheet")["width"] >= 850, "1440 results too narrow")
require(region(materials_1440, "context")["width"] <= 300, "Materials context too wide")
require(materials_1440["resultHorizontalOverflow"] is False, "Materials result overflow")

for width, height in VIEWPORTS:
    modeling = index[("modeling", width, height)]
    require(modeling["graphWorkspacePercent"] >= 85, f"{width} Modeling graph width share")
    require(region(modeling, "settings")["height"] <= 156, f"{width} Modeling settings too tall")
    require(modeling["graphSvg"]["width"] >= (1100 if width < 1920 else 1600), f"{width} graph SVG")
    require(all(not curve["horizontalOverflow"] for curve in modeling["curveNames"]), "curve name overflow")
    require(not any(item["role"] == "context" for item in modeling["regions"]), "persistent third column")

for board in (
    "materials-reference-comparison.png",
    "modeling-reference-comparison.png",
    "card-reference-comparison.png",
):
    require((EVIDENCE / board).is_file(), f"missing comparison board: {board}")

print("PASS: 15 responsive captures and all measurable reference-layout hard gates")
