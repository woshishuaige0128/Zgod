# -*- coding: utf-8 -*-
"""板块16最终独立验收：数值、证据标签、成功/失败目录和保护源。"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()


def find_project_root(path: Path) -> Path:
    for parent in path.parents:
        if (parent / "WORKFLOW.md").is_file() and (parent / "test").is_dir():
            return parent
    raise RuntimeError("无法定位项目根目录")


PROJECT_ROOT = find_project_root(SCRIPT_PATH)
TEST_ROOT = PROJECT_ROOT / "test"
CANDIDATE = TEST_ROOT / "00_失败尝试与候选路线" / "板块16_参考模型候选路线"
REPORT_DIR = CANDIDATE / "report"
INDEX_CSV = TEST_ROOT / "00_总索引与复现规则" / "全部对象总索引.csv"
SOURCE_MANIFEST = TEST_ROOT / "00_总索引与复现规则" / "源文件冻结清单.csv"
U01 = TEST_ROOT / "00_上游模型身份证" / "U01_参考结构参数与15自由度矩阵"
U02 = TEST_ROOT / "00_上游模型身份证" / "U02_完整模型前五阶频率与质量参与系数"
F01 = TEST_ROOT / "00_失败尝试与候选路线" / "U01_参考结构参数与15自由度矩阵"
F02 = TEST_ROOT / "00_失败尝试与候选路线" / "U02_完整模型前五阶频率与质量参与系数"
FC1 = TEST_ROOT / "00_失败尝试与候选路线" / "结论C01_完整参考模型的固有频率与模态质量参与度"
C01_SUCCESS = TEST_ROOT / "结论C01_完整参考模型的固有频率与模态质量参与度"

EXPECTED_THESIS_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
EXPECTED_MANUSCRIPT_SHA256 = "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76"
THESIS_PATH = PROJECT_ROOT.parent / "梁禹手稿.pdf"
MANUSCRIPT_PATH = PROJECT_ROOT.parent / "260817" / "manuscript_0824.tex"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(parent.resolve())]).casefold() == str(parent.resolve()).casefold()
    except ValueError:
        return False


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, str]] = []
    errors: list[str] = []

    def record(name: str, passed: bool, actual: object, expected: object) -> None:
        checks.append(
            {
                "check": name,
                "actual": str(actual),
                "expected": str(expected),
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            errors.append(f"{name}: actual={actual}; expected={expected}")

    # 1. 对象索引和证据标签。
    objects = read_csv(INDEX_CSV)
    record("对象总数与ID唯一", len(objects) == 45 and len({row["对象ID"] for row in objects}) == 45, f"{len(objects)}/{len({row['对象ID'] for row in objects})}", "45/45")
    by_id = {row["对象ID"]: row for row in objects}
    allowed_evidence = {"计算级复现", "绘图级复现", "历史值", "待决定"}
    invalid_evidence = [
        f"{row['对象ID']}:{field}={row[field]}"
        for row in objects
        for field in ("目标证据等级", "当前证据等级")
        if row[field] not in allowed_evidence
    ]
    record("只使用四种固定证据标签", not invalid_evidence, invalid_evidence or "none", "none")
    record("U01索引等级", by_id.get("U01", {}).get("当前证据等级") == "计算级复现", by_id.get("U01", {}).get("当前证据等级"), "计算级复现")
    record("U02索引等级", by_id.get("U02", {}).get("当前证据等级") == "计算级复现", by_id.get("U02", {}).get("当前证据等级"), "计算级复现")
    record("U02状态保留历史/待决定边界", "历史值" in by_id.get("U02", {}).get("当前状态", "") and "待决定" in by_id.get("U02", {}).get("当前状态", ""), by_id.get("U02", {}).get("当前状态"), "同时包含历史值和待决定")
    record("C01索引保持历史值", by_id.get("C01", {}).get("当前证据等级") == "历史值", by_id.get("C01", {}).get("当前证据等级"), "历史值")

    # 2. 目录晋级边界。
    for name, path in (("U01成功目录", U01), ("U02限定成功目录", U02), ("U01失败目录", F01), ("U02失败目录", F02), ("C01失败目录", FC1)):
        record(name, path.is_dir() and (path / "README.md").is_file(), str(path), "directory with README")
    record("C01不得建立整体成功目录", not C01_SUCCESS.exists(), str(C01_SUCCESS.exists()), "False")

    # 3. 候选区最终数值。
    summary_path = CANDIDATE / "outputs" / "independent_validation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    record("候选区独立验证总结果", summary.get("overall") == "PASS" and not summary.get("failures"), summary.get("overall"), "PASS")
    validation_rows = read_csv(CANDIDATE / "outputs" / "independent_validation.csv")
    failed_validation = [row["check"] for row in validation_rows if row["result"] != "PASS"]
    record("预注册数值门槛全部通过", not failed_validation and len(validation_rows) >= 14, f"{len(validation_rows)-len(failed_validation)}/{len(validation_rows)}", "all PASS and >=14 checks")
    input_rows = read_csv(CANDIDATE / "outputs" / "board16_input_integrity.csv")
    record("板块16隔离输入哈希", len(input_rows) == 9 and all(row["result"] == "MATCH" for row in input_rows), f"{sum(row['result']=='MATCH' for row in input_rows)}/{len(input_rows)}", "9/9 MATCH")

    expected_first5 = [2.707425741915, 9.328408686763, 18.4426700565, 22.6735592218, 24.2277487321]
    current_first5 = [float(value) for value in summary["first5_frequency_hz"]]
    first5_max = max(abs(a - b) for a, b in zip(current_first5, expected_first5))
    record("现存代码前五阶频率", first5_max < 1e-9, f"max_abs={first5_max:.17g}", "<1e-9 Hz")
    record("水平方向前五阶累计", abs(float(summary["horizontal_cumulative_first5"]) - 0.980607619065411) < 1e-12, summary["horizontal_cumulative_first5"], "0.980607619065411 +/-1e-12")
    record("MLX历史输出契约", summary.get("energy_zonghe_declared_rows") == 15 and summary.get("energy_zonghe_visible_history_count") == 10 and all(summary.get("energy_zonghe_code_markers", {}).values()), f"declared={summary.get('energy_zonghe_declared_rows')};visible={summary.get('energy_zonghe_visible_history_count')};markers={sum(summary.get('energy_zonghe_code_markers', {}).values())}/6", "declared15;visible10;markers6/6")

    frequency_rows = read_csv(CANDIDATE / "outputs" / "frequency_comparison_thesis_vs_code.csv")
    frequency_differences = [float(row["relative_difference_percent"]) for row in frequency_rows]
    record("论文五频率必须明确为未精确闭合", len(frequency_rows) == 5 and max(frequency_differences) > 2.5 and all(abs(float(row["thesis_frequency_hz"]) - float(row["response_code_frequency_hz"])) > 1e-6 for row in frequency_rows), f"max_relative={max(frequency_differences):.12g}%", "five unequal values; max>2.5%")
    energy_rows = read_csv(CANDIDATE / "outputs" / "energy_route_status.csv")
    record("energy.m真实18维失败", len(energy_rows) == 1 and energy_rows[0]["energy_route_status"] == "EXPECTED_DIMENSION_FAILURE" and energy_rows[0]["energy_error_identifier"] == "MATLAB:innerdim", energy_rows[0] if energy_rows else "missing", "EXPECTED_DIMENSION_FAILURE/MATLAB:innerdim")
    participation_rows = read_csv(CANDIDATE / "outputs" / "participation_route_audit.csv")
    energy_audit = next((row for row in participation_rows if row["route"] == "energy.m字面路线"), {})
    record("energy.m审计文字是18维", energy_audit.get("direction_or_projection") == "写死18维向量", energy_audit.get("direction_or_projection"), "写死18维向量")

    # 4. 成功包的自包含验证。
    for object_name, folder in (("U01", U01), ("U02", U02)):
        object_summary = json.loads((folder / "outputs" / "independent_validation_summary.json").read_text(encoding="utf-8"))
        object_inputs = read_csv(folder / "outputs" / "board16_input_integrity.csv")
        self_log = folder / "logs" / "self_contained_python_validation.log"
        record(f"{object_name}自包含独立验证", object_summary.get("overall") == "PASS" and len(object_inputs) == 9 and all(row["result"] == "MATCH" for row in object_inputs) and self_log.is_file() and "PASS" in self_log.read_text(encoding="utf-8", errors="replace"), f"summary={object_summary.get('overall')};inputs={sum(row['result']=='MATCH' for row in object_inputs)}/{len(object_inputs)}", "PASS;9/9 MATCH;PASS log")

    u02_pdf = U02 / "outputs" / "板块16_频率与模态参与度证据图.pdf"
    u02_png = U02 / "outputs" / "板块16_频率与模态参与度证据图.png"
    visual_pdf = U02 / "visual" / u02_pdf.name
    visual_png = U02 / "visual" / u02_png.name
    plot_passed = (
        u02_pdf.is_file()
        and u02_pdf.stat().st_size > 10_000
        and u02_pdf.read_bytes()[:5] == b"%PDF-"
        and u02_png.is_file()
        and u02_png.stat().st_size > 50_000
        and visual_pdf.is_file()
        and visual_png.is_file()
        and sha256(u02_pdf) == sha256(visual_pdf)
        and sha256(u02_png) == sha256(visual_png)
    )
    record("U02矢量PDF与600dpi PNG证据图", plot_passed, f"pdf={u02_pdf.stat().st_size if u02_pdf.exists() else 0};png={u02_png.stat().st_size if u02_png.exists() else 0};copies_match={plot_passed}", "valid PDF/PNG and output=visual hash")

    # 5. 保护源哈希。
    frozen_sources = read_csv(SOURCE_MANIFEST)
    source_mismatches: list[str] = []
    source_inside_test: list[str] = []
    for row in frozen_sources:
        path = Path(row["绝对路径"])
        if is_within(path, TEST_ROOT):
            source_inside_test.append(str(path))
        if not path.is_file() or path.stat().st_size != int(row["文件大小_字节"]) or sha256(path) != row["SHA256"].upper():
            source_mismatches.append(str(path))
    record("保护源即时哈希复核", len(frozen_sources) == 326 and not source_mismatches, f"{len(frozen_sources)-len(source_mismatches)}/{len(frozen_sources)}", "326/326 MATCH")
    record("保护源位于test外", not source_inside_test, source_inside_test or "none", "none")
    record("硕士论文哈希不变", THESIS_PATH.is_file() and sha256(THESIS_PATH) == EXPECTED_THESIS_SHA256, sha256(THESIS_PATH) if THESIS_PATH.is_file() else "MISSING", EXPECTED_THESIS_SHA256)
    record("小论文母版哈希不变", MANUSCRIPT_PATH.is_file() and sha256(MANUSCRIPT_PATH) == EXPECTED_MANUSCRIPT_SHA256, sha256(MANUSCRIPT_PATH) if MANUSCRIPT_PATH.is_file() else "MISSING", EXPECTED_MANUSCRIPT_SHA256)

    # 6. 代码语法、报告和失败迭代。
    python_files = sorted((CANDIDATE / "code").glob("*.py"))
    syntax_errors: list[str] = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append(f"{path.name}:{exc}")
    record("Python代码语法", len(python_files) >= 3 and not syntax_errors, f"files={len(python_files)};errors={syntax_errors}", ">=3 files;no errors")
    report_path = REPORT_DIR / "板块16_参考结构与模态参与度复现报告.md"
    report_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    report_markers = ["计算级复现", "历史值", "待决定", "energy_zonghe.mlx", "manuscript_0824.tex", "未精确闭合"]
    record("中文证据报告完整", len(report_text) > 10_000 and all(marker in report_text for marker in report_markers), f"chars={len(report_text)};markers={sum(marker in report_text for marker in report_markers)}/{len(report_markers)}", ">10000 chars;6/6 markers")
    required_failure_logs = [
        CANDIDATE / "logs" / "run_reference_model_matlab_attempt1_mu_name_collision.log",
        CANDIDATE / "logs" / "run_reference_model_matlab_attempt2.log",
        CANDIDATE / "logs" / "independent_verify_reference_attempt2.log",
        CANDIDATE / "logs" / "independent_verify_reference_attempt6_final.log",
    ]
    record("失败迭代与最终日志保留", all(path.is_file() and path.stat().st_size > 0 for path in required_failure_logs), [path.name for path in required_failure_logs if not path.is_file() or path.stat().st_size == 0], "four nonempty logs")

    # 7. 工件SHA-256清单（排除验收器自己刚生成的可变报告）。
    manifest_excluded_names = {
        "board16_artifact_manifest.csv",
        "board16_acceptance_checks.csv",
        "board16_acceptance_summary.json",
        "板块16_最终验收记录.md",
    }
    artifact_roots = [CANDIDATE, U01, U02, F01, F02, FC1]
    artifact_files: list[Path] = []
    for root in artifact_roots:
        artifact_files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.name not in manifest_excluded_names
        )
    unique_artifacts = sorted({path.resolve() for path in artifact_files}, key=lambda item: str(item).casefold())
    manifest_rows = [
        {
            "relative_path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in unique_artifacts
    ]
    record("板块16工件清单非空", len(manifest_rows) >= 100, len(manifest_rows), ">=100 files")

    manifest_path = REPORT_DIR / "board16_artifact_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["relative_path", "size_bytes", "sha256"])
        writer.writeheader()
        writer.writerows(manifest_rows)

    overall = "PASS" if not errors else "FAIL"
    checks_path = REPORT_DIR / "board16_acceptance_checks.csv"
    with checks_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["check", "actual", "expected", "result"])
        writer.writeheader()
        writer.writerows(checks)

    summary_output = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "overall": overall,
        "passed": sum(row["result"] == "PASS" for row in checks),
        "total": len(checks),
        "errors": errors,
        "protected_sources": len(frozen_sources),
        "artifact_files": len(manifest_rows),
        "object_decisions": {
            "U01": "计算级复现（现存响应代码路线）",
            "U02": "计算级复现（已闭合代码/MLX部分）；论文频率为历史值/待决定",
            "C01": "历史值＋计算级旁证；整体不晋级",
        },
    }
    (REPORT_DIR / "board16_acceptance_summary.json").write_text(
        json.dumps(summary_output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    markdown_lines = [
        "# 板块16最终验收记录",
        "",
        f"验收时间：{summary_output['timestamp']}",
        "",
        f"总结果：**{overall}**（{summary_output['passed']}/{summary_output['total']}）",
        "",
        "| 检查项 | 实际 | 预期 | 结果 |",
        "|---|---|---|---|",
    ]
    for row in checks:
        markdown_lines.append(
            f"| {row['check']} | {row['actual'].replace('|', '/')} | {row['expected'].replace('|', '/')} | {row['result']} |"
        )
    markdown_lines.extend(
        [
            "",
            "## 对象裁决",
            "",
            "- U01：计算级复现，限现存响应代码路线。",
            "- U02：现存代码频率与作者MLX参与度为计算级复现；论文五频率仍是历史值/待决定。",
            "- C01：前五阶90%以上有计算级旁证，但综合结论整体保持历史值，不建成功目录。",
            "",
            "## 错误",
            "",
        ]
    )
    markdown_lines.extend([f"- {error}" for error in errors] if errors else ["- 无。"])
    (REPORT_DIR / "板块16_最终验收记录.md").write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    print(f"板块16最终验收：{overall}")
    print(f"检查项：{summary_output['passed']}/{summary_output['total']}")
    print(f"保护源：{len(frozen_sources)-len(source_mismatches)}/{len(frozen_sources)} MATCH")
    print(f"工件清单：{len(manifest_rows)}个文件")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
