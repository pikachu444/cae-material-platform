from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[3]
REVIEW = Path(__file__).resolve().parent
GALLERY = ROOT / "docs/00-research/ux-reference-gallery/images"
OUTPUT = ROOT / "docs/17-evidence/images/ux-layout-review"
FONT = ImageFont.load_default()
COLORS = {
    "navigation": "#7b5ca7",
    "search-control-band": "#3c78a8",
    "explorer-filter": "#23856d",
    "result-datasheet": "#cb6b26",
    "context": "#7a7730",
    "curve-tree": "#23856d",
    "settings": "#b05482",
    "graph": "#cb6b26",
    "primary-action": "#b33c3c",
}


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    left, top = xy
    box = draw.textbbox((left, top), text, font=FONT)
    draw.rectangle((box[0] - 3, box[1] - 2, box[2] + 3, box[3] + 2), fill=color)
    draw.text((left, top), text, fill="white", font=FONT)


def overlay_pixels(source: Path, regions: list[dict[str, object]], output: Path) -> None:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    for region in regions:
        role = str(region["role"])
        x = int(float(region["x"]))
        y = int(float(region["y"]))
        width = int(float(region["width"]))
        height = int(float(region["height"]))
        if width <= 0 or height <= 0:
            continue
        color = COLORS.get(role, "#555555")
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline=color, width=4)
        label(draw, (x + 6, y + 5), f"{role} {width}x{height}", color)
    image.save(output)


def overlay_normalized(source: Path, regions: list[dict[str, object]], output: Path) -> None:
    image = Image.open(source).convert("RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    for region in regions:
        role = str(region["role"])
        x, y, region_width, region_height = (float(value) for value in region["rect"])
        left = int(x * width)
        top = int(y * height)
        right = int((x + region_width) * width)
        bottom = int((y + region_height) * height)
        color = COLORS.get(role, "#555555")
        draw.rectangle((left, top, right, bottom), outline=color, width=max(3, width // 450))
        label(draw, (left + 6, top + 5), f"{role} {region_width:.0%}", color)
    image.save(output)


def tile(image: Image.Image, title: str, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, "white")
    fitted = ImageOps.contain(image.convert("RGB"), (size[0] - 16, size[1] - 38))
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, 30 + (size[1] - 38 - fitted.height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, size[0], 28), fill="#27343b")
    draw.text((9, 8), title, fill="white", font=FONT)
    return canvas


def board(items: list[tuple[str, Path]], output: Path) -> None:
    cell = (720, 450)
    canvas = Image.new("RGB", (cell[0] * 2, cell[1] * 2), "#d8dddf")
    for index, (title, path) in enumerate(items):
        panel = tile(Image.open(path), title, cell)
        canvas.paste(panel, ((index % 2) * cell[0], (index // 2) * cell[1]))
    canvas.save(output)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    annotations = json.loads((REVIEW / "region-annotations.json").read_text(encoding="utf-8"))
    measurements = json.loads((OUTPUT / "measurements.json").read_text(encoding="utf-8"))

    for filename, value in annotations["references"].items():
        overlay_normalized(GALLERY / filename, value["regions"], OUTPUT / f"reference-{Path(filename).stem}-mask.png")

    for screen in ("materials", "detail", "modeling", "export", "card"):
        measurement = next(item for item in measurements if item["screen"] == screen and item["viewport"]["width"] == 1440)
        overlay_pixels(OUTPUT / f"{screen}-1440x900.png", measurement["regions"], OUTPUT / f"{screen}-1440x900-mask.png")

    board(
        [
            ("Reference: Granta continuous browse + list", GALLERY / "granta-mi-favourites-list.png"),
            ("Rejected current: Tree is not in the default surface", OUTPUT / "rejected-materials-1440x900.jpg"),
            ("Proposed: searchable governed explorer + dominant results", OUTPUT / "materials-1440x900.jpg"),
            ("Measured proposal regions", OUTPUT / "materials-1440x900-mask.png"),
        ],
        OUTPUT / "materials-reference-comparison.png",
    )
    board(
        [
            ("Reference: Material Modeler control band + graph", GALLERY / "material-modeler-curve-fitting.png"),
            ("Rejected current: 250 + 767 + 340 three columns", OUTPUT / "rejected-modeling-1440x900.jpg"),
            ("Proposed: 184 compact tree + 1,216 graph region", OUTPUT / "modeling-1440x900.jpg"),
            ("Measured proposal regions", OUTPUT / "modeling-1440x900-mask.png"),
        ],
        OUTPUT / "modeling-reference-comparison.png",
    )
    board(
        [
            ("Reference: focused CAE model delivery", GALLERY / "material-data-center-cae-model.png"),
            ("Reference mask: sequential focused action", OUTPUT / "reference-material-data-center-cae-model-mask.png"),
            ("Proposed: native preview + one Download", OUTPUT / "card-1440x900.jpg"),
            ("Measured proposal regions", OUTPUT / "card-1440x900-mask.png"),
        ],
        OUTPUT / "card-reference-comparison.png",
    )


if __name__ == "__main__":
    main()
