#!/usr/bin/env python
"""从包内梁禹硕士论文第70物理页重建六条有序矢量边界CSV。"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "00_源论文与复现合同" / "梁禹手稿.pdf"
DATA_DIR = ROOT / "01_论文矢量边界主数据"
VALIDATION_DIR = ROOT / "08_总验收与论文映射"
SOURCE_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
PAGE_INDEX = 69


@dataclass(frozen=True)
class Curve:
    figure_id: str
    method: str
    drawing_index: int
    expected_points: int
    expected_rightmost: int
    expected_rightmost_tau2: tuple[int, ...]
    filename: str


CURVES = (
    Curve("4-4", "Original", 19, 72, 64, (2,), "图4-4_Original_论文矢量边界.csv"),
    Curve("4-4", "CB", 92, 69, 59, (2, 3, 4, 5), "图4-4_CB_论文矢量边界.csv"),
    Curve("4-4", "Guyan", 162, 67, 58, (2, 3), "图4-4_Guyan_论文矢量边界.csv"),
    Curve("4-5", "Original", 260, 69, 57, (2, 3, 4), "图4-5_Original_论文矢量边界.csv"),
    Curve("4-5", "CB", 330, 56, 51, (2, 3), "图4-5_CB_论文矢量边界.csv"),
    Curve("4-5", "Guyan", 387, 53, 48, (2, 3), "图4-5_Guyan_论文矢量边界.csv"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def extract(page: fitz.Page, curve: Curve) -> list[dict[str, int | float]]:
    drawings = page.get_drawings()
    if curve.drawing_index >= len(drawings):
        raise RuntimeError(f"论文绘图对象{curve.drawing_index}不存在。")
    items = drawings[curve.drawing_index]["items"]
    if not items or any(item[0] != "l" for item in items):
        raise RuntimeError(f"论文绘图对象{curve.drawing_index}不是连续折线。")
    points = [items[0][1], *[item[2] for item in items]]
    x_levels = sorted({round(point.x, 2) for point in points})
    y_levels_desc = sorted({round(point.y, 2) for point in points}, reverse=True)
    x_rank = {value: rank + 2 for rank, value in enumerate(x_levels)}
    y_rank = {value: rank + 2 for rank, value in enumerate(y_levels_desc)}
    rows = []
    for point_order, point in enumerate(points, start=1):
        px = round(point.x, 2)
        py = round(point.y, 2)
        rows.append(
            {
                "point_order": point_order,
                "tau1_step": x_rank[px],
                "tau2_step": y_rank[py],
                "pdf_x_pt": px,
                "pdf_y_pt": py,
                "pdf_page_physical": PAGE_INDEX + 1,
                "pdf_drawing_index": curve.drawing_index,
            }
        )
    rightmost = max(int(row["tau1_step"]) for row in rows)
    right_tau2 = tuple(
        sorted(int(row["tau2_step"]) for row in rows if int(row["tau1_step"]) == rightmost)
    )
    if len(rows) != curve.expected_points:
        raise RuntimeError(f"{curve.filename}点数{len(rows)} != {curve.expected_points}")
    if rightmost != curve.expected_rightmost or right_tau2 != curve.expected_rightmost_tau2:
        raise RuntimeError(
            f"{curve.filename}最右列({rightmost},{right_tau2})与合同不一致。"
        )
    return rows


def main() -> int:
    source_hash = sha256(SOURCE)
    if source_hash != SOURCE_SHA256:
        raise RuntimeError(f"梁禹手稿.pdf哈希变化：{source_hash}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    document = fitz.open(SOURCE)
    page = document[PAGE_INDEX]
    count = 0
    for curve in CURVES:
        rows = extract(page, curve)
        count += len(rows)
        with (DATA_DIR / curve.filename).open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "status": "PASS",
        "evidence_level": "PLOT_LEVEL_VECTOR_TRACE_ONLY",
        "calculation_reproduction": False,
        "source_sha256": source_hash,
        "source_pdf_physical_page": 70,
        "curve_count": len(CURVES),
        "point_count": count,
    }
    (VALIDATION_DIR / "论文PDF矢量提取摘要.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
