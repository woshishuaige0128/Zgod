#!/usr/bin/env python
"""独立验收小论文 Fig. 10 的数据、图件、旧新差异和证据边界。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "00_源论文与复现合同" / "梁禹手稿.pdf"
DATA_DIR = ROOT / "01_论文矢量边界主数据"
FINAL_PDF = ROOT / "02_小论文Fig10最终图" / "PDF" / "fig10_stability_domain.pdf"
FINAL_PNG = ROOT / "02_小论文Fig10最终图" / "PNG" / "fig10_stability_domain.png"
OLD_DIR = ROOT / "04_现有results_v2历史候选_不得作为最终数据"
AUDIT_DIR = ROOT / "05_完整计算复现审计_未通过"
VALIDATION_DIR = ROOT / "08_总验收与论文映射"
SOURCE_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
PAGE_INDEX = 69

CURVES = (
    {
        "figure": "4-4",
        "method": "Original",
        "drawing_index": 19,
        "count": 72,
        "rightmost": 64,
        "right_tau2": (2,),
        "filename": "图4-4_Original_论文矢量边界.csv",
    },
    {
        "figure": "4-4",
        "method": "Craig-Bampton",
        "drawing_index": 92,
        "count": 69,
        "rightmost": 59,
        "right_tau2": (2, 3, 4, 5),
        "filename": "图4-4_CB_论文矢量边界.csv",
    },
    {
        "figure": "4-4",
        "method": "Guyan",
        "drawing_index": 162,
        "count": 67,
        "rightmost": 58,
        "right_tau2": (2, 3),
        "filename": "图4-4_Guyan_论文矢量边界.csv",
    },
    {
        "figure": "4-5",
        "method": "Original",
        "drawing_index": 260,
        "count": 69,
        "rightmost": 57,
        "right_tau2": (2, 3, 4),
        "filename": "图4-5_Original_论文矢量边界.csv",
    },
    {
        "figure": "4-5",
        "method": "Craig-Bampton",
        "drawing_index": 330,
        "count": 56,
        "rightmost": 51,
        "right_tau2": (2, 3),
        "filename": "图4-5_CB_论文矢量边界.csv",
    },
    {
        "figure": "4-5",
        "method": "Guyan",
        "drawing_index": 387,
        "count": 53,
        "rightmost": 48,
        "right_tau2": (2, 3),
        "filename": "图4-5_Guyan_论文矢量边界.csv",
    },
)

EXPECTED_DIFFS = {
    ("4-4", "Original"): (64, 72, 63, 1, 9),
    ("4-4", "Craig-Bampton"): (55, 69, 49, 6, 20),
    ("4-4", "Guyan"): (52, 67, 48, 4, 19),
    ("4-5", "Original"): (57, 69, 56, 1, 13),
    ("4-5", "Craig-Bampton"): (54, 56, 0, 54, 56),
    ("4-5", "Guyan"): (51, 53, 0, 51, 53),
}

AUTHOR_HASHES = {
    "huitu_2.m": "85CB7D5300F3F820AFA80926B76F0430718709BD55722F45486F2F8B9848D1BC",
    "lqr_2.mat": "9B08117CEA7A9DF95D60C4300F3BDCB515765209CD03162114F0436C5094A4C4",
    "lqr_3.mat": "69344E2E703AFE3BDFC1FA6DA133D36E450299B774C085ECE3252BCB18BDDEC1",
    "phy_MRren来源.m": "643C2922BF3EF1BCBBE923998F3BD572671C15935E95AB00B8EC49A55674539E",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def add_check(
    checks: list[dict[str, str]],
    item: str,
    passed: bool,
    actual: object,
    expected: object,
) -> None:
    checks.append(
        {
            "check_item": item,
            "status": "PASS" if passed else "FAIL",
            "actual": str(actual),
            "expected": str(expected),
        }
    )


def read_trace(path: Path) -> list[dict[str, int | float]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "point_order": int(raw["point_order"]),
                    "tau1_step": int(raw["tau1_step"]),
                    "tau2_step": int(raw["tau2_step"]),
                    "pdf_x_pt": float(raw["pdf_x_pt"]),
                    "pdf_y_pt": float(raw["pdf_y_pt"]),
                    "pdf_page_physical": int(raw["pdf_page_physical"]),
                    "pdf_drawing_index": int(raw["pdf_drawing_index"]),
                }
            )
    return rows


def extract_expected(page: fitz.Page, spec: dict[str, object]) -> list[dict[str, int | float]]:
    drawing_index = int(spec["drawing_index"])
    items = page.get_drawings()[drawing_index]["items"]
    if not items or any(item[0] != "l" for item in items):
        raise RuntimeError(f"论文绘图对象{drawing_index}不是连续折线。")
    points = [items[0][1], *[item[2] for item in items]]
    x_levels = sorted({round(point.x, 2) for point in points})
    y_levels_desc = sorted({round(point.y, 2) for point in points}, reverse=True)
    x_rank = {value: rank + 2 for rank, value in enumerate(x_levels)}
    y_rank = {value: rank + 2 for rank, value in enumerate(y_levels_desc)}
    rows = []
    for order, point in enumerate(points, start=1):
        px = round(point.x, 2)
        py = round(point.y, 2)
        rows.append(
            {
                "point_order": order,
                "tau1_step": x_rank[px],
                "tau2_step": y_rank[py],
                "pdf_x_pt": px,
                "pdf_y_pt": py,
                "pdf_page_physical": 70,
                "pdf_drawing_index": drawing_index,
            }
        )
    return rows


def right_edge(rows: list[dict[str, int | float]]) -> tuple[int, tuple[int, ...]]:
    xmax = max(int(row["tau1_step"]) for row in rows)
    ys = tuple(sorted(int(row["tau2_step"]) for row in rows if int(row["tau1_step"]) == xmax))
    return xmax, ys


def validate_old_new(
    target_rows: dict[tuple[str, str], list[dict[str, int | float]]],
    checks: list[dict[str, str]],
) -> None:
    old_files = {
        "4-4": OLD_DIR / "旧边界CSV" / "图4-4_第一类子结构划分稳定域_边界数据.csv",
        "4-5": OLD_DIR / "旧边界CSV" / "图4-5_第二类子结构划分稳定域_边界数据.csv",
    }
    name_map = {"原结构": "Original", "Craig-Bampton": "Craig-Bampton", "Guyan": "Guyan"}
    old_points: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for figure_id, path in old_files.items():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for raw in csv.DictReader(handle):
                key = (figure_id, name_map[raw["方法"]])
                old_points.setdefault(key, []).append(
                    (int(raw["原图横坐标索引"]), int(raw["原图纵坐标索引"]))
                )

    rows_out = []
    all_exact = True
    for spec in CURVES:
        key = (str(spec["figure"]), str(spec["method"]))
        current = set(old_points[key])
        target = {
            (int(row["tau1_step"]), int(row["tau2_step"]))
            for row in target_rows[key]
        }
        metrics = (
            len(old_points[key]),
            len(target_rows[key]),
            len(current & target),
            len(current - target),
            len(target - current),
        )
        exact = metrics == EXPECTED_DIFFS[key]
        all_exact = all_exact and exact
        current_x = max(x for x, _ in old_points[key])
        current_y = tuple(sorted(y for x, y in old_points[key] if x == current_x))
        target_x, target_y = right_edge(target_rows[key])
        rows_out.append(
            {
                "figure": key[0],
                "method": key[1],
                "current_point_count": metrics[0],
                "target_point_count": metrics[1],
                "common_point_count": metrics[2],
                "current_only_count": metrics[3],
                "target_missing_from_current_count": metrics[4],
                "current_right_edge_step": f"x={current_x}; y={list(current_y)}",
                "target_right_edge_step": f"x={target_x}; y={list(target_y)}",
                "current_right_tau1_ms": f"{(current_x - 1) * 1000 / 1024:.9f}",
                "target_right_tau1_ms": f"{(target_x - 1) * 1000 / 1024:.9f}",
                "status": "PASS" if exact else "FAIL",
            }
        )
    destination = OLD_DIR / "新旧数据差异说明.csv"
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_out[0]))
        writer.writeheader()
        writer.writerows(rows_out)
    add_check(
        checks,
        "当前results_v2与论文目标差异被完整锁定",
        all_exact,
        "6/6差异行匹配" if all_exact else "存在差异统计漂移",
        "6/6差异行匹配",
    )


def main() -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, str]] = []

    source_hash = sha256(SOURCE)
    add_check(checks, "源论文SHA-256", source_hash == SOURCE_SHA256, source_hash, SOURCE_SHA256)
    document = fitz.open(SOURCE)
    page = document[PAGE_INDEX]
    target_rows: dict[tuple[str, str], list[dict[str, int | float]]] = {}
    exact_count = 0
    total_points = 0
    for spec in CURVES:
        key = (str(spec["figure"]), str(spec["method"]))
        rows = read_trace(DATA_DIR / str(spec["filename"]))
        expected = extract_expected(page, spec)
        target_rows[key] = rows
        total_points += len(rows)
        exact = rows == expected
        exact_count += int(exact)
        add_check(
            checks,
            f"图{key[0]} {key[1]}与论文PDF矢量路径逐点同序",
            exact,
            f"points={len(rows)}; exact={exact}",
            f"points={spec['count']}; exact=True",
        )
        edge = right_edge(rows)
        expected_edge = (int(spec["rightmost"]), tuple(spec["right_tau2"]))
        add_check(
            checks,
            f"图{key[0]} {key[1]}最右列完整",
            edge == expected_edge,
            edge,
            expected_edge,
        )
        order_ok = [int(row["point_order"]) for row in rows] == list(range(1, len(rows) + 1))
        add_check(checks, f"图{key[0]} {key[1]} point_order连续", order_ok, order_ok, True)

    add_check(checks, "六条边界总点数", total_points == 386, total_points, 386)
    combined = DATA_DIR / "Fig10_六条论文边界_采样步与毫秒.csv"
    with combined.open("r", encoding="utf-8-sig", newline="") as handle:
        combined_rows = list(csv.DictReader(handle))
    conversion_errors = []
    for row in combined_rows:
        x_expected = (int(row["tau1_step"]) - 1) * 1000.0 / 1024.0
        y_expected = (int(row["tau2_step"]) - 1) * 1000.0 / 1024.0
        conversion_errors.extend(
            [abs(float(row["tau1_ms"]) - x_expected), abs(float(row["tau2_ms"]) - y_expected)]
        )
    max_conversion_error = max(conversion_errors)
    add_check(
        checks,
        "采样步到毫秒换算",
        len(combined_rows) == 386 and max_conversion_error < 1e-12,
        f"rows={len(combined_rows)}; max_error={max_conversion_error:.3e}",
        "rows=386; max_error<1e-12 ms",
    )

    pdf_doc = fitz.open(FINAL_PDF)
    pdf_page = pdf_doc[0]
    images = pdf_page.get_images(full=True)
    drawings = pdf_page.get_drawings()
    fonts = pdf_page.get_fonts(full=True)
    type3 = [font for font in fonts if len(font) > 2 and str(font[2]).lower() == "type3"]
    pdf_ok = pdf_doc.page_count == 1 and len(images) == 0 and len(drawings) > 0 and not type3
    add_check(
        checks,
        "最终PDF单页纯矢量且无Type3字体",
        pdf_ok,
        f"pages={pdf_doc.page_count}; images={len(images)}; drawings={len(drawings)}; type3={len(type3)}",
        "pages=1; images=0; drawings>0; type3=0",
    )
    pixmap = pdf_page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
    pixmap.save(VALIDATION_DIR / "PDF_300dpi视觉复核.png")

    with Image.open(FINAL_PNG) as image:
        dpi = image.info.get("dpi", (0.0, 0.0))
        png_ok = min(dpi) >= 599 and image.width >= 3000 and image.height >= 1300
        png_detail = f"pixels={image.width}x{image.height}; dpi={dpi}"
    add_check(checks, "最终PNG约600dpi", png_ok, png_detail, "dpi>=599; pixels>=3000x1300")

    metadata = json.loads((VALIDATION_DIR / "Fig10生成元数据.json").read_text(encoding="utf-8"))
    expected_styles = {
        "Original": {"color": "#555555", "linestyle": "--", "marker": "o", "zorder": 4},
        "Craig-Bampton": {"color": "#EE6677", "linestyle": "-", "marker": "s", "zorder": 3},
        "Guyan": {"color": "#4477AA", "linestyle": "-.", "marker": "^", "zorder": 2},
    }
    style_ok = (
        metadata.get("styles") == expected_styles
        and metadata.get("preserve_point_order") is True
        and metadata.get("drawstyle") == "default ordered polyline"
    )
    add_check(checks, "Fig10方法样式与有序路径合同", style_ok, metadata.get("styles"), expected_styles)

    for filename, expected_hash in AUTHOR_HASHES.items():
        path = ROOT / "03_原作者现存MAT与绘图候选" / filename
        actual_hash = sha256(path)
        add_check(checks, f"作者原文件哈希 {filename}", actual_hash == expected_hash, actual_hash, expected_hash)

    audit_text = (AUDIT_DIR / "图4-4图4-5最终科学裁决报告.md").read_text(encoding="utf-8")
    audit_ok = (
        "FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION" in audit_text
        and "49,848" in audit_text
        and "0/6" in audit_text
    )
    add_check(
        checks,
        "完整计算失败审计边界",
        audit_ok,
        "FAIL/49,848/0-of-6" if audit_ok else "审计字段缺失",
        "FAIL/49,848/0-of-6",
    )

    repeatability_path = VALIDATION_DIR / "重复重建哈希检查.csv"
    repeatability_rows = []
    if repeatability_path.is_file():
        with repeatability_path.open("r", encoding="utf-8-sig", newline="") as handle:
            repeatability_rows = list(csv.DictReader(handle))
    repeatability_ok = bool(repeatability_rows) and all(row["status"] == "PASS" for row in repeatability_rows)
    add_check(
        checks,
        "双轮重建字节一致",
        repeatability_ok,
        f"rows={len(repeatability_rows)}; pass={sum(row.get('status') == 'PASS' for row in repeatability_rows)}",
        "all PASS",
    )

    validate_old_new(target_rows, checks)
    passed = all(row["status"] == "PASS" for row in checks)
    with (VALIDATION_DIR / "Fig10逐项验收.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["check_item", "status", "actual", "expected"]
        )
        writer.writeheader()
        writer.writerows(checks)

    summary = {
        "overall_status": "PASS" if passed else "FAIL",
        "plot_level_reproduction": "PASS" if exact_count == 6 else "FAIL",
        "calculation_level_reproduction": "FAIL",
        "evidence_level": "PLOT_LEVEL_VECTOR_TRACE_ONLY",
        "calculation_reproduction": False,
        "source_pdf_vector_grid_path_point_match_100_percent": exact_count == 6,
        "curve_count": 6,
        "point_count": total_points,
        "check_count": len(checks),
        "pass_count": sum(row["status"] == "PASS" for row in checks),
        "fail_count": sum(row["status"] == "FAIL" for row in checks),
        "final_pdf_sha256": sha256(FINAL_PDF),
        "final_png_sha256": sha256(FINAL_PNG),
        "scientific_calculation_status": "FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION",
    }
    (VALIDATION_DIR / "Fig10验收摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest_path = VALIDATION_DIR / "文件清单与SHA256.csv"
    manifest_rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == manifest_path:
            continue
        manifest_rows.append(
            {
                "file": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
