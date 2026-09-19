"""仅修改图2-9 PDF页面框，保持所有矢量内容与嵌入字体不变。"""
from __future__ import annotations

from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import RectangleObject


PDF = Path(__file__).resolve().parents[1] / "PDF结果" / "图2-9_物理子结构反力计算.pdf"
# Ghostscript bbox 对原生 Letter PDF 测得的内容框（pt），外加 2 pt 安全边距。
BBOX = (116.20, 174.13, 674.95, 433.77)


def 紧裁图2_9() -> None:
    reader = PdfReader(str(PDF))
    if len(reader.pages) != 1:
        raise RuntimeError(f"图2-9 PDF页数不是1：{len(reader.pages)}")
    page = reader.pages[0]
    rect = RectangleObject(BBOX)
    page.mediabox = rect
    page.cropbox = rect
    page.trimbox = rect
    page.bleedbox = rect
    page.artbox = rect
    temp = PDF.with_name(PDF.stem + "_紧裁临时.pdf")
    writer = PdfWriter()
    writer.add_page(page)
    with temp.open("wb") as fh:
        writer.write(fh)
    temp.replace(PDF)


if __name__ == "__main__":
    紧裁图2_9()

