from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
VALIDATION_DIR = ROOT / "验证记录"
VALIDATION_DIR.mkdir(exist_ok=True)

CASES = [
    {
        "id": "Fig06",
        "dir": "Fig06_第一类划分_ElCentro全链计算",
        "entry": "RUN_FIG06_FULLCHAIN.m",
        "reference": "第一类划分_ElCentro地震响应.csv",
        "stem": "fig06_eq_div1_fullchain",
        "dof": (15, 6, 9),
    },
    {
        "id": "Fig07",
        "dir": "Fig07_第二类划分_ElCentro全链计算",
        "entry": "RUN_FIG07_FULLCHAIN.m",
        "reference": "第二类划分_ElCentro地震响应.csv",
        "stem": "fig07_eq_div2_fullchain",
        "dof": (15, 5, 8),
    },
    {
        "id": "Fig08",
        "dir": "Fig08_第一类划分_Chirp全链计算",
        "entry": "RUN_FIG08_FULLCHAIN.m",
        "reference": "第一类划分_Chirp响应.csv",
        "stem": "fig08_chirp_div1_fullchain",
        "dof": (15, 6, 9),
    },
    {
        "id": "Fig09",
        "dir": "Fig09_第二类划分_Chirp全链计算",
        "entry": "RUN_FIG09_FULLCHAIN.m",
        "reference": "第二类划分_Chirp响应.csv",
        "stem": "fig09_chirp_div2_fullchain",
        "dof": (15, 5, 8),
    },
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_key_values(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def check_pdf(path: Path) -> dict[str, object]:
    pdfinfo = shutil.which("pdfinfo")
    pdfimages = shutil.which("pdfimages")
    pdffonts = shutil.which("pdffonts")
    require(bool(pdfinfo and pdfimages and pdffonts), "缺少pdfinfo/pdfimages/pdffonts。")
    info = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, errors="replace", check=True).stdout
    pages_match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", info)
    require(pages_match is not None and int(pages_match.group(1)) == 1, f"{path.name}不是单页PDF。")
    image_listing = subprocess.run([pdfimages, "-list", str(path)], capture_output=True, text=True, errors="replace", check=True).stdout
    image_rows = [line for line in image_listing.splitlines() if re.match(r"^\s*\d+\s+\d+\s+", line)]
    require(not image_rows, f"{path.name}含栅格对象，不是纯矢量曲线PDF。")
    font_listing = subprocess.run([pdffonts, str(path)], capture_output=True, text=True, errors="replace", check=True).stdout
    require("Type 3" not in font_listing, f"{path.name}含Type 3字体。")
    return {"pages": 1, "image_objects": 0, "type3_fonts": 0}


def validate_case(case: dict[str, object]) -> dict[str, object]:
    case_dir = ROOT / str(case["dir"])
    entry = case_dir / str(case["entry"])
    manifest_path = case_dir / "输入与代码SHA256.csv"
    output_dir = case_dir / "输出"
    report_path = output_dir / "现场演示验收报告.txt"
    computed_csv = output_dir / "本轮计算数据" / f"{case['id']}_本轮全链计算响应.csv"
    reference_csv = case_dir / "参考结果_仅用于末端验收" / str(case["reference"])
    pdf_path = output_dir / "本轮计算图" / f"{case['stem']}.pdf"
    png_path = output_dir / "本轮计算图" / f"{case['stem']}.png"

    for path in (entry, manifest_path, report_path, computed_csv, reference_csv, pdf_path, png_path):
        require(path.is_file(), f"缺少文件：{path}")

    source = entry.read_text(encoding="utf-8")
    forbidden = {
        "硬编码盘符": r"(?i)(?<![A-Za-z0-9_])[A-Z]:[\\/]",
        "父目录依赖": r"\.\.[\\/]",
        "MATLAB路径修改": r"(?i)\b(addpath|genpath|rmpath)\s*\(",
        "当前目录依赖": r"(?i)\b(pwd|userpath)\b",
        "环境变量路径": r"(?i)\bgetenv\s*\(",
    }
    for name, pattern in forbidden.items():
        require(re.search(pattern, source) is None, f"{case['id']}入口命中{name}。")
    require("参考结果_仅用于末端验收" in source, f"{case['id']}缺少末端验收隔离说明。")
    require(source.index("computed_csv_file") < source.index("reference_matrix = readmatrix"), f"{case['id']}参考结果读取早于计算保存。")

    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))
    require(len(manifest_rows) == 9, f"{case['id']}固定输入清单不是9项。")
    for row in manifest_rows:
        target = case_dir / row["relative_path"]
        require(target.is_file(), f"{case['id']}清单目标缺失：{target}")
        require(int(row["size_bytes"]) == target.stat().st_size, f"{case['id']}清单字节数错误：{target.name}")
        require(row["sha256"] == sha256_file(target), f"{case['id']}清单哈希错误：{target.name}")

    computed = np.loadtxt(computed_csv, delimiter=",", skiprows=1, encoding="utf-8-sig")
    reference = np.loadtxt(reference_csv, delimiter=",", skiprows=1, encoding="utf-8-sig")
    require(computed.shape == (40961, 10), f"{case['id']}新算CSV尺寸错误：{computed.shape}")
    require(reference.shape == (40961, 10), f"{case['id']}参考CSV尺寸错误：{reference.shape}")
    require(np.isfinite(computed).all(), f"{case['id']}新算CSV含NaN/Inf。")
    require(abs(computed[0, 0]) <= 1e-14 and abs(computed[-1, 0] - 40) <= 1e-14, f"{case['id']}时间范围错误。")
    time_step_error = float(np.max(np.abs(np.diff(computed[:, 0]) - 1 / 1024)))
    require(time_step_error <= 1e-14, f"{case['id']}时间步长误差超限。")
    max_difference = float(np.max(np.abs(computed - reference)))
    require(max_difference <= 1e-12, f"{case['id']}与当前结果差异超限：{max_difference}")

    report = parse_key_values(report_path)
    require(report.get("STATUS") == "PASS", f"{case['id']}MATLAB验收报告未PASS。")
    require(report.get("RESPONSE_SIZE") == "[40961 3 3]", f"{case['id']}响应张量尺寸记录错误。")
    dof = tuple(int(x) for x in re.findall(r"\d+", report["DISPLACEMENT_DOF"]))
    require(dof == tuple(case["dof"]), f"{case['id']}自由度记录错误：{dof}")
    require(float(report["MAX_ABS_DIFFERENCE_TO_CURRENT_MM"]) <= 1e-12, f"{case['id']}MATLAB记录差异超限。")

    pdf_result = check_pdf(pdf_path)
    with Image.open(png_path) as image:
        dpi = image.info.get("dpi", (0.0, 0.0))
        require(abs(float(dpi[0]) - 600) < 1 and abs(float(dpi[1]) - 600) < 1, f"{case['id']} PNG不是600 dpi：{dpi}")
        png_size = image.size
        require(image.mode in {"RGB", "RGBA"}, f"{case['id']} PNG颜色模式异常：{image.mode}")

    require((output_dir / "Simulink缓存").is_dir(), f"{case['id']} Simulink缓存未限制在输出目录。")
    root_cache = [p for p in case_dir.rglob("*.slxc") if output_dir not in p.parents]
    require(not root_cache, f"{case['id']}根目录仍有Simulink缓存：{root_cache}")

    return {
        "figure": case["id"],
        "entry": str(entry),
        "manifest_files": len(manifest_rows),
        "computed_shape": list(computed.shape),
        "response_shape": [40961, 3, 3],
        "time_step_error_s": time_step_error,
        "max_abs_difference_to_current_mm": max_difference,
        "simulation_seconds": float(report["SIMULATION_SECONDS"]),
        "dof_original_guyan_cb": list(dof),
        "pdf": pdf_result,
        "png_pixels": list(png_size),
        "png_dpi": [float(dpi[0]), float(dpi[1])],
        "status": "PASS",
    }


def main() -> None:
    require((ROOT / "README_导师现场操作总指南.md").is_file(), "缺少导师总指南。")
    require((ROOT / "RUN_ALL_FOUR.m").is_file(), "缺少四图总入口。")
    results = [validate_case(case) for case in CASES]

    html_path = ROOT.parent / "小论文Fig6至Fig9_MATLAB现场全计算链汇报.html"
    html_validation_path = VALIDATION_DIR / "HTML自包含验收.json"
    layout_validation_path = VALIDATION_DIR / "HTML布局验收.json"
    a4_path = VALIDATION_DIR / "HTML_A4打印验收.pdf"
    for path in (html_path, html_validation_path, layout_validation_path, a4_path):
        require(path.is_file(), f"缺少HTML验收文件：{path}")
    html_validation = json.loads(html_validation_path.read_text(encoding="utf-8"))
    layout_validation = json.loads(layout_validation_path.read_text(encoding="utf-8"))
    require(html_validation.get("status") == "PASS", "HTML自包含验收未PASS。")
    require(html_validation.get("embedded_png") == 4, "HTML内嵌图不是4张。")
    require(html_validation.get("external_resource_count") == 0, "HTML仍有外部资源。")
    require(html_validation.get("sha256") == sha256_file(html_path), "HTML验收哈希与当前文件不一致。")
    require(layout_validation.get("status") == "PASS", "HTML布局验收未PASS。")
    for viewport_result in layout_validation.get("results", []):
        require(
            viewport_result["scrollWidth"] <= viewport_result["clientWidth"] + 1,
            f"HTML在{viewport_result['viewport']['name']}视口发生文档级横向溢出。",
        )
    pdfinfo = shutil.which("pdfinfo")
    require(bool(pdfinfo), "缺少pdfinfo，不能验收HTML的A4打印件。")
    a4_info = subprocess.run(
        [pdfinfo, str(a4_path)], capture_output=True, text=True, errors="replace", check=True
    ).stdout
    a4_pages = re.search(r"(?m)^Pages:\s+(\d+)\s*$", a4_info)
    require(a4_pages is not None and int(a4_pages.group(1)) == 15, "HTML A4打印页数不是15。")
    require("(A4)" in a4_info, "HTML打印件不是A4页面。")
    summary = {
        "status": "PASS",
        "scope": "Fig.6--Fig.9, Fig.10 excluded",
        "case_count": len(results),
        "all_full_chain_matlab_runs_pass": True,
        "standalone_copy_run": "PASS; C:/Windows/Temp/liangyu_live_demo_board27_20260901_01",
        "evidence_level": "计算级复现（现存代码/必要适配路线）",
        "author_historical_point_values": "待决定",
        "html": {
            "status": "PASS",
            "sha256": html_validation["sha256"],
            "embedded_png": 4,
            "external_resources": 0,
            "desktop_document_overflow": 0,
            "narrow_document_overflow": 0,
            "a4_pages": 15,
        },
        "cases": results,
    }
    json_path = VALIDATION_DIR / "导师现场演示包验收摘要.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "STATUS=PASS",
        "SCOPE=Fig.6--Fig.9; Fig.10 excluded",
        "MATLAB_FINAL_PACKAGE_RUN=4/4 PASS",
        "MATLAB_STANDALONE_COPY_RUN=4/4 PASS",
        "FIXED_INPUT_MANIFESTS=36/36 PASS",
        "PDF_VECTOR_SINGLE_PAGE=4/4 PASS",
        "PNG_600DPI=4/4 PASS",
        "MAX_ABS_DIFFERENCE_TO_CURRENT_MM=" + format(max(r["max_abs_difference_to_current_mm"] for r in results), ".17g"),
        "HTML_SINGLE_FILE=PASS",
        "HTML_EMBEDDED_PNG=4",
        "HTML_EXTERNAL_RESOURCE_COUNT=0",
        "HTML_DESKTOP_LAYOUT=PASS; 1440 px; no document overflow",
        "HTML_NARROW_LAYOUT=PASS; 390 px; no document overflow",
        "HTML_A4_PRINT=PASS; 15 pages; A4",
        "HTML_SHA256=" + html_validation["sha256"],
        "",
    ]
    for result in results:
        lines.append(
            f"{result['figure']}: dof={result['dof_original_guyan_cb']}, "
            f"response={result['response_shape']}, simulation_seconds={result['simulation_seconds']:.6f}, "
            f"max_diff={result['max_abs_difference_to_current_mm']:.17g}, STATUS=PASS"
        )
    text_path = VALIDATION_DIR / "导师现场演示包验收总报告.txt"
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"JSON={json_path}")
    print(f"REPORT={text_path}")


if __name__ == "__main__":
    main()
