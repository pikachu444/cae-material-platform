"""Deterministic hard-gate checks for the UXC-00D proposal captures."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/17-evidence/images/uxc-00d-responsive-design"
VIEWPORTS = ((1366, 768), (1440, 900), (1920, 1080))
SCREENS = ("materials", "modeling", "activity", "administration")
entries = json.loads((EVIDENCE / "measurements.json").read_text(encoding="utf-8"))
annotations = json.loads(
    (ROOT / "docs/00-research/ux-layout-review/region-annotations.json").read_text(encoding="utf-8")
)
for reference_name, reference in annotations["references"].items():
    local_path = ROOT / reference["local_path"]
    gallery_readme = ROOT / reference["gallery_readme"]
    source_catalog = ROOT / reference["source_catalog"]
    assert local_path.is_file(), f"{reference_name}: permanent gallery image missing"
    assert local_path.name == reference_name, f"{reference_name}: local image mapping changed"
    assert gallery_readme.is_file(), f"{reference_name}: gallery README missing"
    assert f"images/{reference_name}" in gallery_readme.read_text(encoding="utf-8"), (
        f"{reference_name}: gallery README does not link the mapped image"
    )
    assert source_catalog.is_file(), f"{reference_name}: official source catalog missing"
    source_ids = {item["id"] for item in json.loads(source_catalog.read_text(encoding="utf-8"))["sources"]}
    assert set(reference["source_ids"]) <= source_ids, f"{reference_name}: source catalog mapping missing"
index = {(e["screen"], e["viewport"]["width"], e["viewport"]["height"]): e for e in entries}
assert len(index) == 12, "all four screens need three viewport captures"
def region(entry, role): return next(item for item in entry["regions"] if item["role"] == role)
for screen in SCREENS:
    for width, height in VIEWPORTS:
        entry = index[screen, width, height]
        assert not entry["pageHorizontalOverflow"], f"{screen} {width}: horizontal overflow"
        assert entry["nestedCards"] == 0, f"{screen}: card grammar"
        assert entry["typography"]["body"] == "14px", f"{screen}: body text"
        assert float(entry["typography"]["utility"].removesuffix("px")) >= 12, f"{screen}: utility text"
        assert entry["primaryCount"] == 1, f"{screen}: one filled primary"
        assert (EVIDENCE / f"{screen}-{width}x{height}.png").is_file(), "capture missing"
materials_1366 = index["materials", 1366, 768]; materials_1440 = index["materials", 1440, 900]
assert region(materials_1366, "context")["width"] == 0, "Materials context closes at 1366"
assert region(materials_1440, "result-datasheet")["width"] > region(materials_1440, "context")["width"], "Materials results dominate context"
assert not materials_1440["normalTextHasInternalId"], "Materials normal view must hide internal IDs"
modeling = index["modeling", 1440, 900]
assert 184 <= region(modeling, "curve-tree")["width"] <= 210, "Modeling tree width"
assert 96 <= region(modeling, "settings")["height"] <= 112, "Modeling settings band"
assert modeling["graphWorkspacePercent"] >= 72, "Modeling graph must dominate workspace"
assert modeling["graphControlsVisible"], "Modeling graph controls must fit the shallow band"
activity = index["activity", 1440, 900]
assert region(activity, "result-datasheet")["width"] >= 1300, "Activity grid must dominate"
assert activity["queueRowHeight"] <= 48, "Activity queue rows must remain compact"
assert activity["selectedQueueRows"] == 1, "Activity primary action needs one selected row"
assert activity["roleView"] == "Reviewer (target)", "Activity must show the reviewed role target"
assert all(activity["reviewerActions"].values()), "Activity must expose reviewer decision actions"
assert activity["focusOutline"] == {"style": "solid", "width": "2px"}, "Interactive controls need visible focus"
admin = index["administration", 1440, 900]
assert all(region(admin, role)["width"] > 0 for role in ("explorer-filter", "result-datasheet", "context")), "Administration three-part topology"
for board in ("four-screen-comparison.png", "activity-administration-comparison.png"): assert (EVIDENCE / board).is_file(), f"missing {board}"
print("PASS: UXC-00D proposal captures and deterministic hard gates")
