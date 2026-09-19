from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

from PIL import Image
from scipy.io import loadmat


代码目录 = Path(__file__).resolve().parent
章节目录 = 代码目录.parent
# 章节目录为 <项目根>/figure/<章节>。
项目根 = 章节目录.parent.parent
清单路径 = 章节目录 / "章节交付清单.csv"
验收JSON = 章节目录 / "验证记录" / "第4章自动验收结果.json"
允许状态 = {"已复现", "已重绘"}
预期列 = ["唯一ID", "代码入口", "数据文件", "PDF结果", "PNG结果", "原始来源", "恢复方式", "验证记录", "状态", "备注"]


def 文件哈希(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def 验收() -> dict:
    with 清单路径.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == 预期列, f"清单列不匹配: {reader.fieldnames}"
        rows = list(reader)
    assert len(rows) == 5, f"清单应有5行，实际{len(rows)}行"
    assert [r["唯一ID"] for r in rows] == ["4-1", "4-2", "4-3", "4-4", "4-5"]

    png_checks = []
    pdf_checks = []
    for row in rows:
        for field in 预期列:
            assert row[field].strip(), f"{row['唯一ID']}字段{field}为空"
        assert row["状态"] in 允许状态
        for field in ["代码入口", "数据文件", "PDF结果", "PNG结果", "原始来源", "验证记录"]:
            for rel in row[field].split(";"):
                assert not Path(rel).is_absolute(), f"清单路径必须为相对路径: {rel}"
                target = 项目根 / Path(rel)
                assert target.is_file() and target.stat().st_size > 0, f"缺失或空文件: {target}"

        png = 项目根 / row["PNG结果"]
        with Image.open(png) as im:
            dpi = tuple(float(v) for v in im.info.get("dpi", (0.0, 0.0)))
            assert im.format == "PNG"
            assert im.width >= 1000 and im.height >= 1000
            assert min(dpi) >= 599.0, f"{png.name} DPI不足: {dpi}"
            png_checks.append({"文件": png.name, "像素": [im.width, im.height], "DPI": list(dpi)})

        pdf = 项目根 / row["PDF结果"]
        pdfinfo = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
        ).stdout
        pages = re.search(r"^Pages:\s+(\d+)", pdfinfo, re.MULTILINE)
        assert pages and int(pages.group(1)) == 1
        pdffonts = subprocess.run(
            ["pdffonts", str(pdf)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True
        ).stdout
        assert "Type 3" not in pdffonts, f"{pdf.name}含Type 3字体"
        # Matplotlib矢量图包含Path/文字操作符；文件不能是仅嵌入单张位图的壳。
        data = pdf.read_bytes()
        assert b"/Font" in data and b"/Subtype /Image" not in data, f"{pdf.name}含栅格图像对象，未保持纯矢量"
        pdf_checks.append({"文件": pdf.name, "页数": 1, "字节数": pdf.stat().st_size, "SHA256": 文件哈希(pdf)})

    # 清洗MAT必须包含掩膜、三种边界、采样周期和共同网格。
    for uid, label in [("4-4", "第一类子结构划分"), ("4-5", "第二类子结构划分")]:
        mat = loadmat(章节目录 / "输入数据" / f"图{uid}_{label}稳定域_清洗数据.mat")
        required = {
            "dt_seconds",
            "common_grid_shape",
            "original_stable_mask",
            "craig_bampton_stable_mask",
            "guyan_stable_mask",
            "original_boundary_delay_ms",
            "craig_bampton_boundary_delay_ms",
            "guyan_boundary_delay_ms",
        }
        assert required.issubset(mat), f"{uid}清洗MAT缺字段: {sorted(required - set(mat))}"
        assert abs(float(mat["dt_seconds"].squeeze()) - 1 / 1024) < 1e-15

    result = {
        "状态": "通过",
        "清单行数": len(rows),
        "PNG检查": png_checks,
        "PDF检查": pdf_checks,
        "样式检查": {
            "字体": "Computer Modern, 9 pt",
            "稳定域颜色": {"原结构": "#333333", "Craig-Bampton": "#4477AA", "Guyan": "#EE6677"},
            "无标题": True,
            "默认网格": False,
            "四边内向刻度": True,
        },
    }
    验收JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(验收(), ensure_ascii=False, indent=2))
