"""第1至2章10张图的结构、格式、分辨率和静态样式验收。"""
from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader


项目根 = Path(__file__).resolve().parents[3]
规定列 = ["唯一ID", "代码入口", "数据文件", "PDF结果", "PNG结果", "原始来源",
       "恢复方式", "验证记录", "状态", "备注"]


def _读取清单(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != 规定列:
            raise AssertionError(f"清单列名不符：{path}: {reader.fieldnames}")
        return list(reader)


def _检查PDF(path: Path, uid: str) -> None:
    reader = PdfReader(str(path))
    if len(reader.pages) != 1:
        raise AssertionError(f"{uid} PDF不是单页")
    page = reader.pages[0]
    resources = page.get("/Resources")
    if resources:
        resources = resources.get_object()
        xobjects = resources.get("/XObject")
        if xobjects:
            for obj in xobjects.get_object().values():
                if obj.get_object().get("/Subtype") == "/Image":
                    raise AssertionError(f"{uid} PDF含Image XObject，不是纯矢量")
        fonts = resources.get("/Font")
        if fonts:
            for font in fonts.get_object().values():
                if font.get_object().get("/Subtype") == "/Type3":
                    raise AssertionError(f"{uid} PDF含Type3字体")
    if uid == "2-9":
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if not (558.0 <= width <= 560.0 and 259.0 <= height <= 261.0):
            raise AssertionError(f"2-9页面未按内容紧裁：{width}x{height} pt")


def 验证() -> None:
    rows = _读取清单(项目根 / "figure" / "第1章_绪论" / "章节交付清单.csv")
    rows += _读取清单(项目根 / "figure" / "第2章_系统缩聚理论和模型建立" / "章节交付清单.csv")
    if len(rows) != 10:
        raise AssertionError(f"清单不是10行：{len(rows)}")
    expected_ids = {"1-1", *[f"2-{i}" for i in range(1, 10)]}
    if {r["唯一ID"] for r in rows} != expected_ids:
        raise AssertionError("唯一ID集合不完整")
    if len({r["代码入口"] for r in rows}) != 10:
        raise AssertionError("10张图没有10个不同单图入口")

    for row in rows:
        uid = row["唯一ID"]
        if row["状态"] not in {"已复现", "已重绘"}:
            raise AssertionError(f"{uid}状态非法：{row['状态']}")
        for field in ("代码入口", "数据文件", "PDF结果", "PNG结果", "原始来源", "验证记录"):
            if not row[field].strip():
                raise AssertionError(f"{uid}字段为空：{field}")
            target = 项目根 / row[field]
            if not target.is_file() or target.stat().st_size == 0:
                raise AssertionError(f"{uid}文件缺失或为空：{field}={target}")
        _检查PDF(项目根 / row["PDF结果"], uid)
        with Image.open(项目根 / row["PNG结果"]) as im:
            dpi = im.info.get("dpi", (0, 0))
            if min(dpi) < 599:
                raise AssertionError(f"{uid} PNG低于600 dpi容差：{dpi}")

    plotting_code = (项目根 / "figure" / "第2章_系统缩聚理论和模型建立" /
                     "可复现代码" / "重绘第1至2章矢量示意图.py").read_text(encoding="utf-8-sig")
    low = re.findall(r"fontsize\s*=\s*([0-8])(?:\D|$)", plotting_code)
    if low:
        raise AssertionError(f"新建Matplotlib图仍有显式fontsize<9：{low}")

    pdffonts = Path(r"D:\Downlad\texlive\2026\bin\windows\pdffonts.exe")
    fig29 = 项目根 / next(r["PDF结果"] for r in rows if r["唯一ID"] == "2-9")
    report = subprocess.run([str(pdffonts), str(fig29)], check=True,
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    if "ArialMT" not in report or "SimSun" not in report or "Type 3" in report:
        raise AssertionError("图2-9字体嵌入/Type3检查失败")
    print("验收通过：10行清单、10个单图入口、20个结果文件、纯矢量PDF、600 dpi PNG、9 pt静态门槛。")


if __name__ == "__main__":
    验证()

