"""核验八组图片的数量、单页矢量性、PNG DPI、像素和SHA-256。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader


源码目录 = Path(__file__).resolve().parent
图片根目录 = 源码目录.parent
PDF目录 = 图片根目录 / "PDF"
PNG目录 = 图片根目录 / "PNG"
验证目录 = 图片根目录 / "验证记录"

预期图片 = [
    "fig_rths_loop",
    "fig_pole_plane",
    "fig_benchmark_geometry",
    "fig_dof_idealization",
    "fig_division",
    "fig_eq_response",
    "fig_chirp_response",
    "fig_stability_domain",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _统计PDF图像对象(reader: PdfReader) -> int:
    count = 0
    for page in reader.pages:
        resources_ref = page.get("/Resources")
        if resources_ref is None:
            continue
        resources = resources_ref.get_object()
        xobjects_ref = resources.get("/XObject")
        if xobjects_ref is None:
            continue
        xobjects = xobjects_ref.get_object()
        for item in xobjects.values():
            obj = item.get_object()
            if obj.get("/Subtype") == "/Image":
                count += 1
    return count


def 验证全部图片() -> Path:
    验证目录.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    errors: list[str] = []

    actual_pdf = sorted(path.stem for path in PDF目录.glob("fig_*.pdf"))
    actual_png = sorted(path.stem for path in PNG目录.glob("fig_*.png"))
    if sorted(预期图片) != actual_pdf:
        errors.append(f"PDF集合不一致：{actual_pdf}")
    if sorted(预期图片) != actual_png:
        errors.append(f"PNG集合不一致：{actual_png}")

    for stem in 预期图片:
        pdf = PDF目录 / f"{stem}.pdf"
        png = PNG目录 / f"{stem}.png"
        if not pdf.is_file() or not png.is_file():
            errors.append(f"缺少成品：{stem}")
            continue
        reader = PdfReader(str(pdf))
        pages = len(reader.pages)
        image_objects = _统计PDF图像对象(reader)
        if pages != 1:
            errors.append(f"{pdf.name} 不是单页PDF：{pages}")
        if image_objects != 0:
            errors.append(f"{pdf.name} 含 {image_objects} 个栅格图像对象")

        with Image.open(png) as image:
            width, height = image.size
            dpi = image.info.get("dpi", (0.0, 0.0))
        dpi_x = float(dpi[0]) if dpi else 0.0
        dpi_y = float(dpi[1]) if dpi else 0.0
        if min(dpi_x, dpi_y) < 590.0:
            errors.append(f"{png.name} DPI不足：{dpi}")
        if min(width, height) < 1_000:
            errors.append(f"{png.name} 短边像素不足：{width}x{height}")

        rows.append(
            {
                "图片基名": stem,
                "PDF页数": pages,
                "PDF栅格对象数": image_objects,
                "PDF字节": pdf.stat().st_size,
                "PDF_SHA256": _sha256(pdf),
                "PNG宽_px": width,
                "PNG高_px": height,
                "PNG_DPI_X": f"{dpi_x:.3f}",
                "PNG_DPI_Y": f"{dpi_y:.3f}",
                "PNG字节": png.stat().st_size,
                "PNG_SHA256": _sha256(png),
            }
        )

    csv_path = 验证目录 / "图片生成与质量清单.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["图片基名"])
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "预期图片数": len(预期图片),
        "实际PDF数": len(actual_pdf),
        "实际PNG数": len(actual_png),
        "错误数": len(errors),
        "错误": errors,
        "结论": "通过" if not errors else "失败",
    }
    json_path = 验证目录 / "图片质量检查.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError("；".join(errors))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return csv_path


if __name__ == "__main__":
    验证全部图片()
