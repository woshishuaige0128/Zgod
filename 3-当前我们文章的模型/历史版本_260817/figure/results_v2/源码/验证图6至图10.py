"""验证图6至图10的输入、方法样式、PDF矢量性和PNG质量。"""

from __future__ import annotations

import csv
import hashlib
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

import 科研绘图统一样式_V2 as 样式


根目录 = Path(__file__).resolve().parent.parent
输入目录 = 根目录 / "输入数据"
PDF目录 = 根目录 / "PDF"
PNG目录 = 根目录 / "PNG"
验证目录 = 根目录 / "验证记录"

输入哈希 = {
    "第一类划分_ElCentro地震响应.csv": "E7149DD6777B2127527393CE1D7B126B040576F0A535618BE33E882738ACFC40",
    "第二类划分_ElCentro地震响应.csv": "2899DFD2C03B22AAEE701C7E4B3B70E40D49668531BB6734FA6B52E8246B5E5D",
    "第一类划分_Chirp响应.csv": "2FDC6B5BF3B48118A51DD147ECE32B6711CEFDCD702D88EEC64CFC4E6A13DF49",
    "第二类划分_Chirp响应.csv": "88919C2AFA4FC431EDB08772A1DCB091B6D8DC1445253C0A4D30334223040457",
    "图4-4_第一类子结构划分稳定域_边界数据.csv": "58F45ADB3FA125A61AB636696E72AAD82FAB05EAD8556B742394069D681A372D",
    "图4-5_第二类子结构划分稳定域_边界数据.csv": "BAB62AFA096E5427AB0D8ABA49F6CCBE4556890E82178132628F4654FCE6F10E",
}

稳定域方法点数 = {
    "图4-4_第一类子结构划分稳定域_边界数据.csv": {"原结构": 64, "Craig-Bampton": 55, "Guyan": 52},
    "图4-5_第二类子结构划分稳定域_边界数据.csv": {"原结构": 57, "Craig-Bampton": 54, "Guyan": 51},
}

输出基名 = (
    "fig06_eq_div1",
    "fig07_eq_div2",
    "fig08_chirp_div1",
    "fig09_chirp_div2",
    "fig10_stability_domain",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def run_text(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout


def 验证输入() -> None:
    for name, expected_hash in 输入哈希.items():
        path = 输入目录 / name
        if not path.is_file() or sha256(path) != expected_hash:
            raise AssertionError(f"输入缺失或哈希不一致：{name}")
        if "响应" in name:
            raw = np.loadtxt(path, delimiter=",", skiprows=1, encoding="utf-8-sig")
            if raw.shape != (40_961, 10):
                raise AssertionError(f"响应尺寸错误：{name} -> {raw.shape}")
            if not np.all(np.isfinite(raw)):
                raise AssertionError(f"响应含NaN/Inf：{name}")
            if raw[0, 0] != 0.0 or raw[-1, 0] != 40.0 or not np.all(np.diff(raw[:, 0]) == 1 / 1024):
                raise AssertionError(f"响应时间轴错误：{name}")
        else:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            actual = {method: sum(row["方法"] == method for row in rows) for method in ("原结构", "Craig-Bampton", "Guyan")}
            if actual != 稳定域方法点数[name]:
                raise AssertionError(f"稳定域方法点数错误：{name} -> {actual}")


def 验证样式() -> None:
    expected = {
        "Original": ("#555555", "--"),
        "Craig-Bampton": ("#EE6677", "-"),
        "Guyan": ("#4477AA", "-."),
    }
    actual = {name: (style["color"], style["linestyle"]) for name, style in 样式.方法样式.items()}
    if actual != expected:
        raise AssertionError(f"方法样式不符合约定：{actual}")


def 验证产物() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in 输出基名:
        pdf = PDF目录 / f"{name}.pdf"
        png = PNG目录 / f"{name}.png"
        if not pdf.is_file() or not png.is_file():
            raise AssertionError(f"缺少输出：{name}")

        info = run_text("pdfinfo", str(pdf))
        page_match = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
        if page_match is None or int(page_match.group(1)) != 1:
            raise AssertionError(f"PDF不是单页：{pdf}")

        image_list = run_text("pdfimages", "-list", str(pdf))
        image_rows = re.findall(r"^\s*\d+\s+\d+\s+\w+\s+\d+\s+\d+", image_list, flags=re.MULTILINE)
        if image_rows:
            raise AssertionError(f"PDF含栅格Image对象：{pdf}")

        font_list = run_text("pdffonts", str(pdf))
        if "Type 3" in font_list:
            raise AssertionError(f"PDF含Type 3字体：{pdf}")

        with Image.open(png) as image:
            width, height = image.size
            dpi = image.info.get("dpi", (0.0, 0.0))
        if width < 3_000 or height < 1_500:
            raise AssertionError(f"PNG像素不足：{png} -> {width}×{height}")
        if min(dpi) < 590 or max(dpi) > 610:
            raise AssertionError(f"PNG DPI不在约600范围：{png} -> {dpi}")

        rows.append(
            {
                "图片基名": name,
                "PDF字节": pdf.stat().st_size,
                "PDF_SHA256": sha256(pdf),
                "PDF栅格对象数": len(image_rows),
                "PDF_Type3字体": 0,
                "PNG宽_px": width,
                "PNG高_px": height,
                "PNG_DPI_X": f"{dpi[0]:.3f}",
                "PNG_DPI_Y": f"{dpi[1]:.3f}",
                "PNG字节": png.stat().st_size,
                "PNG_SHA256": sha256(png),
            }
        )
    return rows


def 写出质量清单(rows: list[dict[str, object]]) -> Path:
    验证目录.mkdir(parents=True, exist_ok=True)
    path = 验证目录 / "图6至图10质量清单.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    验证输入()
    验证样式()
    rows = 验证产物()
    path = 写出质量清单(rows)
    print(f"输入验证通过：{len(输入哈希)}份")
    print("方法样式通过：Original深灰色虚线；Craig-Bampton红色实线；Guyan蓝色点划线")
    print(f"输出验证通过：{len(rows)}份PDF + {len(rows)}份PNG")
    print(f"质量清单：{path}")


if __name__ == "__main__":
    main()
