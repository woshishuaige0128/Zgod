from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image
try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    from PyPDF2 import PdfReader


TEST_ROOT = Path(__file__).resolve().parents[1]
FIGURE_ROOT = TEST_ROOT / "figures"
OUTPUT_CSV = TEST_ROOT / "outputs" / "figure_validation.csv"


def count_raster_xobjects(reader: PdfReader) -> int:
    total = 0
    for page in reader.pages:
        resources = page.get("/Resources")
        if resources is not None and hasattr(resources, "get_object"):
            resources = resources.get_object()
        if not resources or "/XObject" not in resources:
            continue
        for obj in resources["/XObject"].get_object().values():
            resolved = obj.get_object()
            if resolved.get("/Subtype") == "/Image":
                total += 1
    return total


def main() -> None:
    stems = sorted(path.stem for path in FIGURE_ROOT.glob("*.pdf"))
    if len(stems) != 4:
        raise RuntimeError(f"Expected 4 PDF figures, found {len(stems)}")

    rows: list[dict[str, object]] = []
    for stem in stems:
        pdf_path = FIGURE_ROOT / f"{stem}.pdf"
        png_path = FIGURE_ROOT / f"{stem}.png"
        if not png_path.is_file():
            raise FileNotFoundError(png_path)

        reader = PdfReader(str(pdf_path))
        if len(reader.pages) != 1:
            raise RuntimeError(f"{pdf_path.name} is not a single-page PDF")
        image_objects = count_raster_xobjects(reader)
        if image_objects != 0:
            raise RuntimeError(
                f"{pdf_path.name} contains {image_objects} raster image XObjects"
            )

        with Image.open(png_path) as image:
            dpi = image.info.get("dpi", (0.0, 0.0))
            dpi_x, dpi_y = float(dpi[0]), float(dpi[1])
            if not (599.0 <= dpi_x <= 601.0 and 599.0 <= dpi_y <= 601.0):
                raise RuntimeError(
                    f"{png_path.name} DPI is ({dpi_x:.6g}, {dpi_y:.6g})"
                )
            width, height = image.size
            if width < 4000 or height < 3500:
                raise RuntimeError(
                    f"{png_path.name} dimensions are only {width}x{height}"
                )

        rows.append(
            {
                "figure": stem,
                "pdf_pages": len(reader.pages),
                "pdf_raster_xobjects": image_objects,
                "png_width_px": width,
                "png_height_px": height,
                "png_dpi_x": dpi_x,
                "png_dpi_y": dpi_y,
                "status": "PASS",
            }
        )

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"figure_validation: PASS; figures={len(rows)}")


if __name__ == "__main__":
    main()
