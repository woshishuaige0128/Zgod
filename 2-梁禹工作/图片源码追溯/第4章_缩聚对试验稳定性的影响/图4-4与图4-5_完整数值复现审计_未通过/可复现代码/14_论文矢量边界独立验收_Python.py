#!/usr/bin/env python
"""独立重读论文 PDF，验收六个 CSV、两张矢量 PDF 与 600 dpi PNG。"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import fitz
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_DIR.parent
REBUILD_PATH = SCRIPT_DIR / "rebuild_thesis_vector_trace.py"


def load_rebuild_module():
    spec = importlib.util.spec_from_file_location("thesis_trace_rebuild", REBUILD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载重建脚本。")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, int | float]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "point_order": int(row["point_order"]),
                    "tau1_step": int(row["tau1_step"]),
                    "tau2_step": int(row["tau2_step"]),
                    "pdf_x_pt": float(row["pdf_x_pt"]),
                    "pdf_y_pt": float(row["pdf_y_pt"]),
                    "pdf_page_physical": int(row["pdf_page_physical"]),
                    "pdf_drawing_index": int(row["pdf_drawing_index"]),
                }
            )
    return rows


def add_check(checks: list[dict[str, str]], item: str, passed: bool, actual: str, expected: str) -> None:
    checks.append(
        {
            "check_item": item,
            "status": "PASS" if passed else "FAIL",
            "actual": actual,
            "expected": expected,
        }
    )


def validate_pdf(path: Path) -> tuple[bool, str]:
    document = fitz.open(path)
    page = document[0]
    images = page.get_images(full=True)
    drawings = page.get_drawings()
    fonts = page.get_fonts(full=True)
    type3 = [font for font in fonts if len(font) > 2 and str(font[2]).lower() == "type3"]
    passed = len(images) == 0 and len(drawings) > 0 and len(type3) == 0
    return passed, f"images={len(images)}; drawings={len(drawings)}; type3_fonts={len(type3)}"


def render_pdf(path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open(path)
    pixmap = document[0].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
    pixmap.save(destination)


def main() -> int:
    rebuild = load_rebuild_module()
    checks: list[dict[str, str]] = []
    source = rebuild.DEFAULT_SOURCE.resolve()
    source_hash = sha256(source)
    add_check(checks, "源论文SHA-256", source_hash == rebuild.SOURCE_SHA256, source_hash, rebuild.SOURCE_SHA256)

    document = fitz.open(source)
    page = document[rebuild.PAGE_INDEX]
    all_points_match = True
    for curve in rebuild.CURVES:
        # 独立重读 PDF 并重新做坐标秩映射，不复用已生成 CSV。
        expected_rows = rebuild.extract_curve(page, curve)
        actual_rows = read_csv(OUTPUT_ROOT / "data" / curve.csv_name)
        exact = actual_rows == expected_rows
        all_points_match = all_points_match and exact
        add_check(
            checks,
            f"图{curve.figure_id}_{curve.method}_PDF矢量路径逐点一致",
            exact,
            f"points={len(actual_rows)}; exact={exact}",
            f"points={curve.expected_points}; exact=True",
        )
        rightmost = max(int(row["tau1_step"]) for row in actual_rows)
        right_tau2 = tuple(
            sorted(int(row["tau2_step"]) for row in actual_rows if int(row["tau1_step"]) == rightmost)
        )
        full_right = rightmost == curve.expected_rightmost and right_tau2 == curve.expected_rightmost_tau2
        add_check(
            checks,
            f"图{curve.figure_id}_{curve.method}_最右列完整",
            full_right,
            f"tau1={rightmost}; tau2={list(right_tau2)}",
            f"tau1={curve.expected_rightmost}; tau2={list(curve.expected_rightmost_tau2)}",
        )

    figure_hashes = []
    for figure_id, plot_spec in rebuild.PLOT_SPECS.items():
        pdf_path = OUTPUT_ROOT / "figures" / plot_spec["pdf"]
        png_path = OUTPUT_ROOT / "figures" / plot_spec["png"]
        pdf_ok, pdf_detail = validate_pdf(pdf_path)
        add_check(checks, f"图{figure_id}_PDF为纯矢量且无Type3字体", pdf_ok, pdf_detail, "images=0; drawings>0; type3_fonts=0")
        with Image.open(png_path) as image:
            dpi = image.info.get("dpi", (0, 0))
            png_ok = min(dpi) >= 599 and image.width >= 3000 and image.height >= 2000
            png_detail = f"pixels={image.width}x{image.height}; dpi={dpi}"
        add_check(checks, f"图{figure_id}_PNG为600dpi", png_ok, png_detail, "dpi>=599; pixels>=3000x2000")
        render_pdf(
            pdf_path,
            OUTPUT_ROOT / "visual_qa" / f"图{figure_id}_PDF_300dpi复核.png",
        )
        figure_hashes.extend(
            [
                {"file": str(pdf_path.relative_to(OUTPUT_ROOT)), "sha256": sha256(pdf_path)},
                {"file": str(png_path.relative_to(OUTPUT_ROOT)), "sha256": sha256(png_path)},
            ]
        )

    passed = all(check["status"] == "PASS" for check in checks)
    validation_dir = OUTPUT_ROOT / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    with (validation_dir / "逐点验收检查.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check_item", "status", "actual", "expected"])
        writer.writeheader()
        writer.writerows(checks)

    summary = {
        "overall_status": "PASS" if passed else "FAIL",
        "evidence_level": "PLOT_LEVEL_VECTOR_TRACE_ONLY",
        "calculation_reproduction": False,
        "source_pdf_vector_grid_path_point_match_100_percent": all_points_match,
        "source_sha256": source_hash,
        "check_count": len(checks),
        "pass_count": sum(check["status"] == "PASS" for check in checks),
        "fail_count": sum(check["status"] == "FAIL" for check in checks),
        "figure_hashes": figure_hashes,
    }
    (validation_dir / "逐点验收摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest_rows = []
    for path in sorted(OUTPUT_ROOT.rglob("*")):
        if not path.is_file() or path.name == "文件哈希清单.csv":
            continue
        manifest_rows.append(
            {
                "file": str(path.relative_to(OUTPUT_ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    with (validation_dir / "文件哈希清单.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
