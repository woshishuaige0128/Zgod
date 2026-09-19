#!/usr/bin/env python
"""对图10最终图件、数据、证据汇总和独立HTML执行静态/数值验收。"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from PIL import Image
from pypdf import PdfReader


CASE_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROOT = CASE_ROOT.parents[1]
DEFAULT_REPORT = DELIVERY_ROOT / "图10_硕士论文与当前文章差异汇报.html"
DEFAULT_REPORT_MANIFEST = DELIVERY_ROOT / "图10_硕士论文与当前文章差异汇报_生成清单.json"
DEFAULT_FIGURE_DIR = CASE_ROOT / "figures" / "final_delivery"
DEFAULT_PLOT_MANIFEST = DEFAULT_FIGURE_DIR / "图10_论文目标_历史候选_来源约束计算对比_生成清单.json"
DEFAULT_EVIDENCE = CASE_ROOT / "evaluation" / "final_evidence_summary_complete" / "final_evidence_summary.json"
DEFAULT_MATLAB = (
    CASE_ROOT
    / "data"
    / "matlab_independent_fullgrid_validation"
    / "gain_scale_0p625"
    / "B1"
    / "matlab_validation_summary.json"
)
DEFAULT_OUTPUT = CASE_ROOT / "evaluation" / "final_delivery_validation" / "validation_summary.json"


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.h1_count = 0
        self.h2_count = 0
        self.in_h1 = False
        self.title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if data.get("id"):
            self.ids.add(str(data["id"]))
        if data.get("href"):
            self.hrefs.append(str(data["href"]))
        if data.get("src"):
            self.srcs.append(str(data["src"]))
        if tag == "h1":
            self.h1_count += 1
            self.in_h1 = True
        if tag == "h2":
            self.h2_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str) -> None:
        if self.in_h1:
            self.title_text.append(data)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def dereference(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def pdf_resource_counts(pdf_path: Path) -> dict[str, int]:
    reader = PdfReader(str(pdf_path))
    image_count = 0
    type3_count = 0
    font_count = 0
    visited_xobjects: set[tuple[int, int]] = set()

    def scan_resources(resources: Any) -> None:
        nonlocal image_count, type3_count, font_count
        resources = dereference(resources)
        if not resources:
            return
        fonts = dereference(resources.get("/Font", {}))
        for font_ref in fonts.values() if fonts else []:
            font = dereference(font_ref)
            font_count += 1
            if str(font.get("/Subtype")) == "/Type3":
                type3_count += 1
        xobjects = dereference(resources.get("/XObject", {}))
        for xobject_ref in xobjects.values() if xobjects else []:
            identifier = getattr(xobject_ref, "idnum", None), getattr(xobject_ref, "generation", None)
            if identifier != (None, None) and identifier in visited_xobjects:
                continue
            if identifier != (None, None):
                visited_xobjects.add(identifier)
            xobject = dereference(xobject_ref)
            subtype = str(xobject.get("/Subtype"))
            if subtype == "/Image":
                image_count += 1
            elif subtype == "/Form":
                scan_resources(xobject.get("/Resources"))

    for page in reader.pages:
        scan_resources(page.get("/Resources"))
    first_box = reader.pages[0].mediabox
    return {
        "page_count": len(reader.pages),
        "image_xobject_count": image_count,
        "font_resource_count": font_count,
        "type3_font_count": type3_count,
        "width_points": float(first_box.width),
        "height_points": float(first_box.height),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--report-manifest", type=Path, default=DEFAULT_REPORT_MANIFEST)
    parser.add_argument("--plot-manifest", type=Path, default=DEFAULT_PLOT_MANIFEST)
    parser.add_argument("--evidence-summary", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--matlab-summary", type=Path, default=DEFAULT_MATLAB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "report": args.report.resolve(),
        "report_manifest": args.report_manifest.resolve(),
        "plot_manifest": args.plot_manifest.resolve(),
        "evidence": args.evidence_summary.resolve(),
        "matlab": args.matlab_summary.resolve(),
    }
    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append(
            {
                "name": name,
                "status": "PASS" if condition else "FAIL",
                "actual": actual,
                "expected": expected,
            }
        )

    for name, path in paths.items():
        check(f"input_exists__{name}", path.is_file(), str(path), "existing regular file")
    if any(item["status"] == "FAIL" for item in checks):
        raise FileNotFoundError("最终验收输入不完整")

    plot = load_json(paths["plot_manifest"])
    evidence = load_json(paths["evidence"])
    matlab = load_json(paths["matlab"])
    report_manifest = load_json(paths["report_manifest"])
    pdf_path = Path(plot["outputs"]["pdf"]).resolve()
    png_path = Path(plot["outputs"]["png"]).resolve()
    csv_path = Path(plot["outputs"]["editable_csv"]).resolve()
    for name, path in (("pdf", pdf_path), ("png", png_path), ("csv", csv_path)):
        check(f"figure_output_exists__{name}", path.is_file(), str(path), "existing regular file")

    # HTML结构与离线性
    report_bytes = paths["report"].read_bytes()
    report_text = report_bytes.decode("utf-8")
    parser = ReportParser()
    parser.feed(report_text)
    parser.close()
    required_ids = {"summary", "identity", "concepts", "method", "results", "differences", "evidence", "actions"}
    check("html_doctype", report_text.lstrip().lower().startswith("<!doctype html>"), "present", "present")
    check("html_utf8_meta", '<meta charset="utf-8">' in report_text.lower(), "present", "present")
    check("html_one_h1", parser.h1_count == 1, parser.h1_count, 1)
    check("html_section_ids", required_ids <= parser.ids, sorted(parser.ids), sorted(required_ids))
    broken_anchors = sorted(href for href in parser.hrefs if href.startswith("#") and href[1:] not in parser.ids)
    check("html_internal_anchors", not broken_anchors, broken_anchors, [])
    external_refs = sorted(
        value for value in [*parser.hrefs, *parser.srcs] if re.match(r"^(?:https?:)?//", value, re.I)
    )
    check("html_external_resources", not external_refs, external_refs, [])
    data_images = [src for src in parser.srcs if src.startswith("data:image/png;base64,")]
    check("html_embedded_png_count", len(data_images) == 1, len(data_images), 1)
    decoded_image = base64.b64decode(data_images[0].split(",", 1)[1], validate=True)
    check("html_embedded_png_sha256", hashlib.sha256(decoded_image).hexdigest().upper() == sha256(png_path), hashlib.sha256(decoded_image).hexdigest().upper(), sha256(png_path))
    check("html_print_css", "@media print" in report_text and "@page" in report_text and "size:A4" in report_text.replace(" ", ""), "present", "present")
    check("html_narrow_css", "@media(max-width:600px)" in report_text.replace(" ", ""), "present", "present")
    check("html_wide_table_scroll", "overflow-x:auto" in report_text.replace(" ", ""), "present", "present")
    for phrase in (
        "绘图级复现通过、计算级精准复现未通过",
        "目标引导的校准计算复现",
        "6135/6135",
        "0/6严格命中",
        "12462",
        "8.193445921733655e-14",
        "H07",
    ):
        check(f"html_fact__{phrase}", phrase in report_text, "present" if phrase in report_text else "missing", "present")

    # 图件与可编辑数据
    check("plot_manifest_status", plot["status"] == "PASS_GENERATED_WITH_STRICT_FAILURE_DISCLOSED", plot["status"], "PASS_GENERATED_WITH_STRICT_FAILURE_DISCLOSED")
    check("active_target_pdf_identical", plot["active_and_rebuilt_pdf_byte_identical"], plot["active_article_pdf_sha256"], plot["rebuilt_target_pdf_sha256"])
    check("selected_candidate_strict_0_of_6", int(plot["strict_curve_pass_count"]) == 0, plot["strict_curve_pass_count"], 0)
    check("pdf_hash", sha256(pdf_path) == plot["outputs"]["pdf_sha256"], sha256(pdf_path), plot["outputs"]["pdf_sha256"])
    check("png_hash", sha256(png_path) == plot["outputs"]["png_sha256"], sha256(png_path), plot["outputs"]["png_sha256"])
    check("editable_csv_hash", sha256(csv_path) == plot["outputs"]["editable_csv_sha256"], sha256(csv_path), plot["outputs"]["editable_csv_sha256"])

    pdf_info = pdf_resource_counts(pdf_path)
    check("pdf_single_page", pdf_info["page_count"] == 1, pdf_info["page_count"], 1)
    check("pdf_no_raster_xobject", pdf_info["image_xobject_count"] == 0, pdf_info["image_xobject_count"], 0)
    check("pdf_no_type3_fonts", pdf_info["type3_font_count"] == 0, pdf_info["type3_font_count"], 0)
    check("pdf_reasonable_page_size", 450 <= pdf_info["width_points"] <= 560 and 380 <= pdf_info["height_points"] <= 500, [pdf_info["width_points"], pdf_info["height_points"]], "450-560 pt by 380-500 pt")

    with Image.open(png_path) as image:
        dpi = image.info.get("dpi", (0.0, 0.0))
        width, height = image.size
        check("png_dimensions", width >= 4000 and height >= 3000, [width, height], ">=4000 x >=3000")
        check("png_600_dpi", all(abs(float(value) - 600.0) <= 1.0 for value in dpi), list(dpi), "600 +/- 1 dpi")
        check("png_format", image.format == "PNG", image.format, "PNG")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        data_rows = list(csv.DictReader(stream))
    series = {(row["division"], row["method"], row["series"]) for row in data_rows}
    conversion_errors = [
        max(
            abs(float(row["tau1_ms"]) - (int(row["tau1_step"]) - 1) * 1000.0 / 1024.0),
            abs(float(row["tau2_ms"]) - (int(row["tau2_step"]) - 1) * 1000.0 / 1024.0),
        )
        for row in data_rows
    ]
    check("editable_csv_series_count", len(series) == 18, len(series), 18)
    check("editable_csv_row_count", len(data_rows) == 1001, len(data_rows), 1001)
    check("editable_csv_ms_conversion", max(conversion_errors) <= 1e-12, max(conversion_errors), "<=1e-12")

    # 统一评价证据与独立MATLAB复核
    check("evidence_status", evidence["status"] == "PASS" and evidence["completion_status"] == "COMPLETE", [evidence["status"], evidence["completion_status"]], ["PASS", "COMPLETE"])
    check("evidence_candidate_count", int(evidence["counts"]["candidate_count"]) == 35, evidence["counts"]["candidate_count"], 35)
    check("evidence_curve_row_count", int(evidence["counts"]["curve_result_row_count"]) == 210, evidence["counts"]["curve_result_row_count"], 210)
    check("evidence_calculation_strict_pass_zero", int(evidence["counts"]["strict_pass_source_constrained_calculation_curve_result_count"]) == 0, evidence["counts"]["strict_pass_source_constrained_calculation_curve_result_count"], 0)
    check("evidence_h07_present", evidence["optional_evidence"]["H07"]["status"] == "PRESENT", evidence["optional_evidence"]["H07"], "PRESENT")
    check("matlab_status", matlab["status"] == "PASS" and matlab["all_points_pass"], [matlab["status"], matlab["all_points_pass"]], ["PASS", True])
    check("matlab_point_count", int(matlab["point_count"]) == 12462, matlab["point_count"], 12462)
    check("matlab_rho_tolerance", float(matlab["maximum_rho_absolute_difference"]) <= 1e-9, matlab["maximum_rho_absolute_difference"], "<=1e-9")
    check("matlab_stable_zero_diff", int(matlab["stable_mismatch_count"]) == 0, matlab["stable_mismatch_count"], 0)
    check("matlab_target_firewall", int(matlab["target_files_read"]) == 0 and int(matlab["python_solver_invocations"]) == 0, [matlab["target_files_read"], matlab["python_solver_invocations"]], [0, 0])
    check("report_manifest_hash", report_manifest["report_sha256"] == sha256(paths["report"]), report_manifest["report_sha256"], sha256(paths["report"]))
    check("report_manifest_candidate", report_manifest["selected_candidate_id"] == plot["selected_candidate"]["candidate_id"], report_manifest["selected_candidate_id"], plot["selected_candidate"]["candidate_id"])

    failed = [item for item in checks if item["status"] == "FAIL"]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "FIG10_FINAL_DELIVERY_VALIDATION_V1",
        "status": "PASS" if not failed else "FAIL",
        "check_count": len(checks),
        "pass_count": len(checks) - len(failed),
        "fail_count": len(failed),
        "checks": checks,
        "pdf_resource_summary": pdf_info,
        "artifacts": {
            name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for name, path in {
                **paths,
                "pdf": pdf_path,
                "png": png_path,
                "editable_csv": csv_path,
            }.items()
        },
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: payload[key] for key in ("status", "check_count", "pass_count", "fail_count")}, ensure_ascii=False, indent=2))
    if failed:
        print(json.dumps(failed, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
