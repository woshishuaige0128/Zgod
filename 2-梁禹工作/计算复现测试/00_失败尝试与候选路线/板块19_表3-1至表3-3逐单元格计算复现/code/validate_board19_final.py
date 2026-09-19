from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


BOARD_NAME = "板块19_表3-1至表3-3逐单元格计算复现"
TARGET_IDS = {"T3-1", "T3-2", "T3-3"}
EXPECTED_THESIS_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
EXPECTED_MANUSCRIPT_SHA256 = "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76"


def find_board_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if candidate.name == BOARD_NAME:
            return candidate
    raise RuntimeError("无法定位板块19隔离目录。")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "pass"}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    board_root = find_board_root(Path(__file__).resolve().parent)
    project_root = board_root.parents[2]
    output_dir = board_root / "outputs"
    final_dir = output_dir / "final_validation"
    final_dir.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, expected: Any, actual: Any, evidence: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "result": "PASS" if condition else "FAIL",
                "expected": expected,
                "actual": actual,
                "evidence": evidence,
            }
        )

    # 40个目标单元格及匹配统计
    all_cells_path = output_dir / "evidence" / "table3_all_40_cells.csv"
    all_cells = read_csv(all_cells_path)
    check("cell_count", len(all_cells) == 40, 40, len(all_cells), str(all_cells_path))
    ids = [row["cell_id"] for row in all_cells]
    check("cell_id_unique", len(set(ids)) == 40, 40, len(set(ids)), str(all_cells_path))
    object_counts = Counter(row["object_id"] for row in all_cells)
    match_counts = Counter(row["object_id"] for row in all_cells if truthy(row["rounded_match"]))
    for object_id, expected_cells, expected_matches in (("T3-1", 8, 4), ("T3-2", 8, 7), ("T3-3", 24, 13)):
        check(f"{object_id}_cell_count", object_counts[object_id] == expected_cells, expected_cells, object_counts[object_id], str(all_cells_path))
        check(f"{object_id}_match_count", match_counts[object_id] == expected_matches, expected_matches, match_counts[object_id], str(all_cells_path))
    required_fields = [
        "cell_id", "object_id", "object_name", "division", "condition", "method", "route",
        "calculated_value", "paper_value", "printed_decimals", "rounded_value",
        "absolute_difference", "rounded_match", "cross_language_pass", "evidence_label",
        "formula", "source_file", "source_sha256",
    ]
    for row in all_cells:
        missing = [field for field in required_fields if row.get(field, "") == ""]
        check(f"cell_fields_{row['cell_id']}", not missing, "all required fields nonempty", ";".join(missing) or "complete", str(all_cells_path))
        check(f"cell_cross_language_{row['cell_id']}", truthy(row["cross_language_pass"]), True, row["cross_language_pass"], str(all_cells_path))

    # MATLAB/Python摘要与原脚本边界
    modal = read_json(output_dir / "modal_python" / "modal_cross_language_summary.json")
    nrmse = read_json(output_dir / "nrmse_python" / "nrmse_cross_language_summary.json")
    original = read_json(output_dir / "original_script_attempts_summary.json")
    check("modal_cross_language", modal["comparison_rows"] == modal["comparison_pass_count"] == 64 and modal["comparison_fail_count"] == 0, "64/64 PASS", f"{modal['comparison_pass_count']}/{modal['comparison_rows']} PASS", "modal_cross_language_summary.json")
    check("modal_frequency_tolerance", modal["maximum_frequency_hz_absolute_difference"] <= 5e-10, "<=5e-10 Hz", modal["maximum_frequency_hz_absolute_difference"], "modal_cross_language_summary.json")
    check("modal_mac_tolerance", modal["maximum_mac_absolute_difference"] <= 5e-10, "<=5e-10", modal["maximum_mac_absolute_difference"], "modal_cross_language_summary.json")
    check("nrmse_cross_language", nrmse["cross_language_rows"] == nrmse["cross_language_pass_count"] == 264 and nrmse["cross_language_fail_count"] == 0, "264/264 PASS", f"{nrmse['cross_language_pass_count']}/{nrmse['cross_language_rows']} PASS", "nrmse_cross_language_summary.json")
    check("nrmse_historical_rows", nrmse["historical_candidate_rows"] == 72 and nrmse["historical_chirp_rows"] == 60 and nrmse["historical_elcentro_rows"] == 12, "72=60+12", f"{nrmse['historical_candidate_rows']}={nrmse['historical_chirp_rows']}+{nrmse['historical_elcentro_rows']}", "nrmse_cross_language_summary.json")
    check("nrmse_tolerance", nrmse["maximum_nrmse_absolute_difference_percent"] <= 5e-10, "<=5e-10 percentage points", nrmse["maximum_nrmse_absolute_difference_percent"], "nrmse_cross_language_summary.json")
    check("original_scripts_expected_failures", original == {"script_count": 5, "success_count": 0, "failure_count": 5, "empty_workspace_before_each": True, "status": "EXPECTED_FAILURES_RECORDED"}, "5 empty-workspace failures recorded", original, "original_script_attempts_summary.json")

    # 唯一Excel、前后公式校验及11张最终渲染
    workbook_files = list(output_dir.glob("*.xlsx"))
    check("single_workbook", len(workbook_files) == 1, 1, len(workbook_files), str(output_dir))
    workbook_path = output_dir / "板块19_表3-1至表3-3逐单元格计算复现审计.xlsx"
    check("workbook_exists", workbook_path.is_file() and workbook_path.stat().st_size > 40000, "one readable workbook >40000 bytes", workbook_path.stat().st_size if workbook_path.exists() else 0, str(workbook_path))
    workbook_validation = read_json(output_dir / "evidence" / "workbook_validation_summary.json")
    for phase_key in ("before_export", "after_reimport"):
        phase = workbook_validation[phase_key]
        check(f"workbook_{phase_key}_status", phase["status"] == "PASS", "PASS", phase["status"], "workbook_validation_summary.json")
        check(f"workbook_{phase_key}_formula_errors", phase["formula_error_count"] == 0, 0, phase["formula_error_count"], "workbook_validation_summary.json")
        check(f"workbook_{phase_key}_cell_matches", (phase["table3_1_match_count"], phase["table3_2_match_count"], phase["table3_3_match_count"]) == (4, 7, 13), "4/7/13", f"{phase['table3_1_match_count']}/{phase['table3_2_match_count']}/{phase['table3_3_match_count']}", "workbook_validation_summary.json")
        check(f"workbook_{phase_key}_formula_python", phase["evidence_formula_python_pass_count"] == 40 and phase["evidence_cross_language_pass_count"] == 40, "40/40 and 40/40", f"{phase['evidence_formula_python_pass_count']}/40 and {phase['evidence_cross_language_pass_count']}/40", "workbook_validation_summary.json")
    final_renders = workbook_validation["final_renders"]
    check("render_count", len(final_renders) == 11, 11, len(final_renders), "workbook_validation_summary.json")
    for filename in final_renders:
        image_path = output_dir / "workbook_render" / filename
        if image_path.is_file():
            with Image.open(image_path) as image:
                dimensions = image.size
                valid = image.format == "PNG" and image.width >= 500 and image.height >= 250
        else:
            dimensions = (0, 0)
            valid = False
        check(f"render_{filename}", valid, "valid PNG >=500x250", f"{dimensions[0]}x{dimensions[1]}", str(image_path))

    # 35份冻结副本、34份未授权演进源及两份论文保护源
    manifest_path = board_root / "input" / "input_manifest.csv"
    manifest_rows = read_csv(manifest_path)
    check("input_manifest_count", len(manifest_rows) == 35, 35, len(manifest_rows), str(manifest_path))
    source_live_match_count = 0
    copy_live_match_count = 0
    for index, row in enumerate(manifest_rows, start=1):
        copy_path = board_root / "input" / row["copied_relative_path"]
        copy_hash = sha256_file(copy_path) if copy_path.is_file() else "MISSING"
        copy_ok = copy_hash == row["sha256_copy"] == row["sha256_source"]
        copy_live_match_count += int(copy_ok)
        check(f"frozen_copy_{index:02d}", copy_ok, row["sha256_copy"], copy_hash, str(copy_path))
        if row["role"] != "object_index":
            source_path = Path(row["source_path"])
            source_hash = sha256_file(source_path) if source_path.is_file() else "MISSING"
            source_ok = source_hash == row["sha256_source"]
            source_live_match_count += int(source_ok)
            check(f"live_source_{index:02d}", source_ok, row["sha256_source"], source_hash, str(source_path))
    check("frozen_copy_total", copy_live_match_count == 35, 35, copy_live_match_count, str(manifest_path))
    check("unchanged_live_source_total", source_live_match_count == 34, 34, source_live_match_count, "object_index excluded as authorized evolution")
    thesis_path = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\梁禹手稿.pdf")
    manuscript_path = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript_0824.tex")
    check("thesis_protected", sha256_file(thesis_path) == EXPECTED_THESIS_SHA256, EXPECTED_THESIS_SHA256, sha256_file(thesis_path), str(thesis_path))
    check("manuscript_protected", sha256_file(manuscript_path) == EXPECTED_MANUSCRIPT_SHA256, EXPECTED_MANUSCRIPT_SHA256, sha256_file(manuscript_path), str(manuscript_path))

    # 三个失败包及正式成功目录不存在
    index_current_path = project_root / "test" / "00_总索引与复现规则" / "全部对象总索引.csv"
    current_rows = read_csv(index_current_path)
    current_by_id = {row["对象ID"]: row for row in current_rows}
    for object_id in sorted(TARGET_IDS):
        row = current_by_id[object_id]
        success_path = project_root / row["成功文件夹"]
        failure_path = project_root / row["失败尝试目录"]
        check(f"{object_id}_success_absent", not success_path.exists(), False, success_path.exists(), str(success_path))
        check(f"{object_id}_failure_present", failure_path.is_dir(), True, failure_path.is_dir(), str(failure_path))
        summary = read_json(failure_path / "package_summary.json")
        check(f"{object_id}_package_summary", summary["status"] == "FAILURE_EVIDENCE_PACKAGED" and not summary["all_cells_closed"] and not summary["formal_success_directory_exists"], "failure package and no success", summary, str(failure_path / "package_summary.json"))
        package_manifest = read_csv(failure_path / "artifact_manifest.csv")
        check(f"{object_id}_package_manifest_nonempty", len(package_manifest) >= 6, ">=6", len(package_manifest), str(failure_path / "artifact_manifest.csv"))
        for manifest_row in package_manifest:
            artifact = failure_path / manifest_row["relative_path"]
            actual_hash = sha256_file(artifact) if artifact.is_file() else "MISSING"
            actual_size = artifact.stat().st_size if artifact.is_file() else -1
            valid = actual_hash == manifest_row["sha256"] and actual_size == int(manifest_row["size_bytes"])
            check(f"{object_id}_artifact_{manifest_row['relative_path']}", valid, f"{manifest_row['size_bytes']}|{manifest_row['sha256']}", f"{actual_size}|{actual_hash}", str(artifact))

    # 总索引只允许3个目标行演进
    frozen_index_path = board_root / "input" / "contracts" / "全部对象总索引_冻结前.csv"
    frozen_rows = read_csv(frozen_index_path)
    frozen_by_id = {row["对象ID"]: row for row in frozen_rows}
    check("index_row_count", len(current_rows) == len(frozen_rows) == 45, 45, f"current={len(current_rows)}, frozen={len(frozen_rows)}", f"{frozen_index_path} -> {index_current_path}")
    unchanged_non_targets = sum(current_by_id[object_id] == frozen_by_id[object_id] for object_id in frozen_by_id if object_id not in TARGET_IDS)
    changed_targets = sum(current_by_id[object_id] != frozen_by_id[object_id] for object_id in TARGET_IDS)
    check("index_non_targets_unchanged", unchanged_non_targets == 42, 42, unchanged_non_targets, f"{frozen_index_path} -> {index_current_path}")
    check("index_targets_changed", changed_targets == 3, 3, changed_targets, f"{frozen_index_path} -> {index_current_path}")
    for object_id in sorted(TARGET_IDS):
        row = current_by_id[object_id]
        current_evidence_ok = "部分计算级复现" in row["当前证据等级"] and "历史值" in row["当前证据等级"] and "待决定" in row["当前证据等级"]
        check(f"{object_id}_index_evidence", current_evidence_ok, "部分计算级复现；其余历史值/待决定", row["当前证据等级"], str(index_current_path))

    # 报告和文献留痕
    report_path = board_root / "report" / "板块19_表3-1至表3-3逐单元格计算复现报告.md"
    note_path = project_root / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md"
    check("report_present", report_path.is_file() and report_path.stat().st_size > 5000, "report >5000 bytes", report_path.stat().st_size if report_path.exists() else 0, str(report_path))
    note_text = note_path.read_text(encoding="utf-8") if note_path.is_file() else ""
    check("literature_note_finalized", "板块19最终逐格计算裁决" in note_text and "35/35" in note_text, "final Board19 note with 35/35", "present" if "板块19最终逐格计算裁决" in note_text else "missing", str(note_path))

    fail_count = sum(row["result"] != "PASS" for row in checks)
    summary = {
        "check_count": len(checks),
        "pass_count": len(checks) - fail_count,
        "fail_count": fail_count,
        "table3_1_matches": 4,
        "table3_1_cells": 8,
        "table3_2_matches": 7,
        "table3_2_cells": 8,
        "table3_3_matches": 13,
        "table3_3_cells": 24,
        "formal_success_directory_count": 0,
        "failure_package_count": 3,
        "workbook_sha256": sha256_file(workbook_path) if workbook_path.is_file() else "MISSING",
        "thesis_sha256": sha256_file(thesis_path),
        "manuscript_sha256": sha256_file(manuscript_path),
        "status": "PASS" if fail_count == 0 else "FAIL",
    }
    write_csv(final_dir / "board19_final_validation_checks.csv", checks)
    (final_dir / "board19_final_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if fail_count:
        failed_ids = [row["check_id"] for row in checks if row["result"] != "PASS"]
        raise SystemExit(f"最终验收失败：{failed_ids}")


if __name__ == "__main__":
    main()
