from __future__ import annotations

"""Publish Board 18 figures only after every numeric and visual gate passes.

This script intentionally performs a complete read-only preflight before it
creates a staging directory.  A failed preflight therefore creates neither a
formal success directory nor a partial index update.
"""

import codecs
import csv
import hashlib
import io
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[4]
OUTPUTS = BOARD_ROOT / "outputs"
CODE_ROOT = BOARD_ROOT / "code"
FIGURE_CANDIDATES = OUTPUTS / "figure_candidates"
FIGURE_VALIDATION = OUTPUTS / "figure_validation"
COMPARISONS = OUTPUTS / "comparisons"
INDEX_PATH = PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv"
PROJECT_SOURCE_FREEZE = PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结清单.csv"
FROZEN_SOURCE_FREEZE = BOARD_ROOT / "input" / "plotting_baseline" / "验证记录" / "汇总" / "源文件冻结清单.csv"

INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
INPUT_RECHECK = OUTPUTS / "independent_input_hash_recheck.csv"
INPUT_RECHECK_SUMMARY = OUTPUTS / "independent_input_hash_recheck_summary.json"
BUILD_BOARD18_SUMMARY = OUTPUTS / "build_board18_summary.json"
PROTECTED_SOURCE_RECHECK = OUTPUTS / "protected_source_recheck.csv"
BOARD17_ARTIFACT_RECHECK = OUTPUTS / "board17_artifact_recheck.csv"
BOARD17_PASSPORT = BOARD_ROOT / "input" / "upstream_passports" / "board17"
BOARD17_ARTIFACT_MANIFEST = BOARD17_PASSPORT / "board17_artifact_manifest.csv"
BOARD17_VALIDATION_SUMMARY = BOARD17_PASSPORT / "board17_final_validation_summary.json"

TARGET_IDS = (
    "F3-5",
    "F3-6",
    "F3-7",
    "F3-8",
    "F3-9",
    "F3-10",
    "F3-11",
    "F3-12",
    "F3-13",
    "F3-14",
    "F3-15",
)
TARGET_SET = set(TARGET_IDS)

EVIDENCE_LABEL = "计算级复现（现存代码/必要适配路线）"
HISTORY_LABEL = "作者历史逐点值：待决定"

OBJECT_RESPONSE_SCOPE: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "F3-5": ("unit", "单位激励_原结构三层响应", ("Floor 1", "Floor 2", "Floor 3")),
    "F3-6": ("division1_elcentro", "第一类划分_ElCentro地震响应", ("Floor 1",)),
    "F3-7": ("division1_elcentro", "第一类划分_ElCentro地震响应", ("Floor 2",)),
    "F3-8": ("division1_elcentro", "第一类划分_ElCentro地震响应", ("Floor 3",)),
    "F3-9": ("division2_elcentro", "第二类划分_ElCentro地震响应", ("Floor 1",)),
    "F3-10": ("division2_elcentro", "第二类划分_ElCentro地震响应", ("Floor 3",)),
    "F3-11": ("division1_chirp", "第一类划分_Chirp响应", ("Floor 1",)),
    "F3-12": ("division1_chirp", "第一类划分_Chirp响应", ("Floor 2",)),
    "F3-13": ("division1_chirp", "第一类划分_Chirp响应", ("Floor 3",)),
    "F3-14": ("division2_chirp", "第二类划分_Chirp响应", ("Floor 1",)),
    "F3-15": ("division2_chirp", "第二类划分_Chirp响应", ("Floor 3",)),
}

COMPARISON_SUMMARY = COMPARISONS / "response_comparison_summary.json"
COMPARISON_DETAIL = COMPARISONS / "response_column_comparisons.csv"
COMPARISON_DATASET = COMPARISONS / "response_dataset_comparisons.csv"
FIGURE_DATA_CONTRACT = COMPARISONS / "figure_data_contract.csv"
INDEPENDENT_ROOT = OUTPUTS / "independent"
INDEPENDENT_SUMMARY = INDEPENDENT_ROOT / "summary.json"
INDEPENDENT_MATRIX = INDEPENDENT_ROOT / "matrix_checks.csv"
INDEPENDENT_RESPONSE = INDEPENDENT_ROOT / "response_checks.csv"
HISTORY_SUMMARY = OUTPUTS / "manual_history_audit_summary.json"
HISTORY_ADJUDICATION = OUTPUTS / "manual_history_file_adjudication.csv"
FIGURE_CONTRACT = OUTPUTS / "figure_contract.csv"
ORIGINAL_ATTEMPT_ROOT = OUTPUTS / "original_attempt"
ORIGINAL_ATTEMPT_SUMMARY = ORIGINAL_ATTEMPT_ROOT / "original_attempt_summary.json"

CANDIDATE_MANIFEST = FIGURE_CANDIDATES / "artifact_manifest.csv"
CANDIDATE_SUMMARY = FIGURE_CANDIDATES / "generation_summary.json"
VALIDATION_DETAIL = FIGURE_VALIDATION / "validation_detail.csv"
VALIDATION_SUMMARY = FIGURE_VALIDATION / "validation_summary.json"
MANUAL_VISUAL_REVIEW = FIGURE_VALIDATION / "manual_visual_review.csv"

PUBLISH_MANIFEST = OUTPUTS / "publish_board18_manifest.csv"
PUBLISH_SUMMARY = OUTPUTS / "publish_board18_summary.json"
PUBLISH_GATES = OUTPUTS / "publish_board18_gate_results.csv"
INDEX_BEFORE_COPY = OUTPUTS / "publish_index_before.csv"
INDEX_AFTER_COPY = OUTPUTS / "publish_index_after.csv"


class GateError(RuntimeError):
    """Raised when a publication precondition is not satisfied."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"缺少JSON门槛文件: {path}")
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    require(isinstance(value, dict), f"JSON顶层不是对象: {path}")
    return value


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    require(path.is_file(), f"缺少CSV门槛文件: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None, f"CSV缺少表头: {path}")
        rows = [dict(row) for row in reader]
        return list(reader.fieldnames), rows


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"1", "TRUE", "PASS", "YES"}


def as_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GateError(f"{label}不是整数: {value!r}") from exc


def project_relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def safe_relative_file(root: Path, raw: str, label: str) -> Path:
    require(bool(str(raw).strip()), f"{label}为空")
    candidate = (root / Path(str(raw))).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise GateError(f"{label}越出允许目录: {raw}") from exc
    require(candidate.is_file(), f"{label}不存在: {candidate}")
    return candidate


def add_gate(gates: list[dict[str, Any]], gate: str, actual: Any, expected: str) -> None:
    gates.append({"gate": gate, "actual": actual, "expected": expected, "status": "PASS"})


def fingerprint(
    path: Path,
    cache: dict[Path, tuple[int, str]],
    label: str,
) -> tuple[int, str]:
    """Return a live size/hash pair; cache identical paths within one preflight."""
    resolved = path.resolve()
    require(resolved.is_file(), f"{label}不存在: {resolved}")
    if resolved not in cache:
        cache[resolved] = (resolved.stat().st_size, sha256(resolved))
    return cache[resolved]


def require_live_file_matches(
    path: Path,
    expected_size: Any,
    expected_sha256: Any,
    cache: dict[Path, tuple[int, str]],
    label: str,
) -> tuple[int, str]:
    actual_size, actual_sha = fingerprint(path, cache, label)
    require(actual_size == as_int(expected_size, f"{label} expected_size"), f"{label}当前大小不符: {path}")
    require(actual_sha == str(expected_sha256).strip().upper(), f"{label}当前SHA-256不符: {path}")
    return actual_size, actual_sha


def preflight_authoritative_hashes(gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-hash all protected authorities before any publication write occurs."""
    cache: dict[Path, tuple[int, str]] = {}

    # Board18 frozen inputs: frozen manifest + independent audit + live re-hash.
    input_summary = read_json(INPUT_FREEZE_SUMMARY)
    input_recheck_summary = read_json(INPUT_RECHECK_SUMMARY)
    input_fields, input_rows = read_csv(INPUT_MANIFEST)
    recheck_fields, recheck_rows = read_csv(INPUT_RECHECK)
    required_input = {
        "role", "source_path", "copied_relative_path", "source_size_bytes",
        "copy_size_bytes", "source_sha256_after", "copy_sha256", "status",
    }
    required_recheck = {
        "source_path", "copy_path", "expected_source_size_bytes",
        "expected_copy_size_bytes", "expected_source_sha256", "expected_copy_sha256",
        "actual_source_sha256", "actual_copy_sha256", "status",
    }
    require(required_input.issubset(input_fields), f"80输入清单缺列: {sorted(required_input - set(input_fields))}")
    require(required_recheck.issubset(recheck_fields), f"80输入复核缺列: {sorted(required_recheck - set(recheck_fields))}")
    require(len(input_rows) == 80 and len(recheck_rows) == 80, "Board18冻结输入或独立复核不是80行")
    manifest_hash = sha256(INPUT_MANIFEST)
    require(as_int(input_summary.get("source_count"), "source_count") == 80, "冻结摘要source_count不是80")
    require(as_int(input_summary.get("copy_count"), "copy_count") == 80, "冻结摘要copy_count不是80")
    require(as_int(input_summary.get("match_count"), "match_count") == 80, "冻结摘要match_count不是80")
    require(is_true(input_summary.get("all_match")), "冻结摘要并非all_match")
    require(str(input_summary.get("manifest_sha256", "")).upper() == manifest_hash, "冻结摘要的输入清单SHA不符")
    require(as_int(input_recheck_summary.get("row_count"), "row_count") == 80, "输入独立复核row_count不是80")
    require(as_int(input_recheck_summary.get("pass_count"), "pass_count") == 80, "输入独立复核不是80/80 PASS")
    require(as_int(input_recheck_summary.get("fail_count"), "fail_count") == 0, "输入独立复核存在失败")
    require(str(input_recheck_summary.get("overall_status", "")).upper() == "PASS", "输入独立复核汇总未PASS")
    require(str(input_recheck_summary.get("manifest_sha256", "")).upper() == manifest_hash, "输入独立复核清单SHA不符")
    require(all(row.get("status", "").upper() == "MATCH" for row in input_rows), "80输入清单存在非MATCH行")
    require(all(row.get("status", "").upper() == "PASS" for row in recheck_rows), "80输入独立复核存在非PASS行")

    recheck_by_source = {str(Path(row["source_path"]).resolve()).lower(): row for row in recheck_rows}
    require(len(recheck_by_source) == 80, "80输入独立复核source_path不唯一")
    for row in input_rows:
        source = Path(row["source_path"]).resolve()
        copied = (BOARD_ROOT / Path(row["copied_relative_path"])).resolve()
        try:
            copied.relative_to(BOARD_ROOT.resolve())
        except ValueError as exc:
            raise GateError(f"冻结输入副本越出Board18: {copied}") from exc
        _, source_sha = require_live_file_matches(
            source, row["source_size_bytes"], row["source_sha256_after"], cache, "Board18冻结输入源",
        )
        _, copy_sha = require_live_file_matches(
            copied, row["copy_size_bytes"], row["copy_sha256"], cache, "Board18冻结输入副本",
        )
        require(source_sha == copy_sha, f"冻结输入源/副本当前SHA不同: {source}")
        audit = recheck_by_source.get(str(source).lower())
        require(audit is not None, f"80输入独立复核缺少源: {source}")
        require(Path(audit["copy_path"]).resolve() == copied, f"80输入独立复核副本路径不符: {source}")
        require(audit["expected_source_sha256"].upper() == row["source_sha256_after"].upper(), f"80输入源期望SHA交叉不符: {source}")
        require(audit["expected_copy_sha256"].upper() == row["copy_sha256"].upper(), f"80输入副本期望SHA交叉不符: {copied}")
        require(audit["actual_source_sha256"].upper() == source_sha, f"80输入旧复核源SHA与当前不符: {source}")
        require(audit["actual_copy_sha256"].upper() == copy_sha, f"80输入旧复核副本SHA与当前不符: {copied}")
    add_gate(gates, "Board18冻结输入当前哈希", "80/80 source+copy live PASS", "80/80 PASS")

    build_summary = read_json(BUILD_BOARD18_SUMMARY)
    require(str(build_summary.get("overall_status", "")).upper() == "PASS", "Board18构建摘要未PASS")
    require(as_int(build_summary.get("freeze_source_count"), "freeze_source_count") == 80, "构建摘要冻结输入数不是80")
    require(as_int(build_summary.get("freeze_match_count"), "freeze_match_count") == 80, "构建摘要冻结输入不是80/80")
    require(is_true(build_summary.get("freeze_pass")), "构建摘要freeze_pass为false")

    # The protected-source authority is itself a frozen Board18 input.
    require_live_file_matches(
        PROJECT_SOURCE_FREEZE,
        FROZEN_SOURCE_FREEZE.stat().st_size if FROZEN_SOURCE_FREEZE.is_file() else -1,
        sha256(FROZEN_SOURCE_FREEZE) if FROZEN_SOURCE_FREEZE.is_file() else "MISSING",
        cache,
        "项目326保护源清单",
    )
    freeze_fields, freeze_rows = read_csv(FROZEN_SOURCE_FREEZE)
    protected_fields, protected_rows = read_csv(PROTECTED_SOURCE_RECHECK)
    required_freeze = {"类别", "绝对路径", "文件大小_字节", "SHA256"}
    required_protected = {"absolute_path", "expected_size_bytes", "actual_size_bytes", "expected_sha256", "actual_sha256", "status"}
    require(required_freeze.issubset(freeze_fields), f"326保护源清单缺列: {sorted(required_freeze - set(freeze_fields))}")
    require(required_protected.issubset(protected_fields), f"326保护源复核缺列: {sorted(required_protected - set(protected_fields))}")
    require(len(freeze_rows) == 326 and len(protected_rows) == 326, "保护源清单或复核不是326行")
    protected_by_path = {str(Path(row["absolute_path"]).resolve()).lower(): row for row in protected_rows}
    require(len(protected_by_path) == 326, "326保护源复核路径不唯一")
    for row in freeze_rows:
        source = Path(row["绝对路径"]).resolve()
        actual_size, actual_sha = require_live_file_matches(
            source, row["文件大小_字节"], row["SHA256"], cache, "受保护源",
        )
        audit = protected_by_path.get(str(source).lower())
        require(audit is not None, f"326保护源复核缺少路径: {source}")
        require(audit["status"].upper() == "MATCH", f"326保护源复核非MATCH: {source}")
        require(as_int(audit["expected_size_bytes"], "protected expected_size") == actual_size, f"保护源期望大小交叉不符: {source}")
        require(as_int(audit["actual_size_bytes"], "protected actual_size") == actual_size, f"保护源旧复核大小与当前不符: {source}")
        require(audit["expected_sha256"].upper() == row["SHA256"].upper(), f"保护源期望SHA交叉不符: {source}")
        require(audit["actual_sha256"].upper() == actual_sha, f"保护源旧复核SHA与当前不符: {source}")
    require(as_int(build_summary.get("protected_source_count"), "protected_source_count") == 326, "构建摘要保护源数不是326")
    require(as_int(build_summary.get("protected_source_match_count"), "protected_source_match_count") == 326, "构建摘要保护源不是326/326")
    require(is_true(build_summary.get("protected_pass")), "构建摘要protected_pass为false")
    add_gate(gates, "原始受保护源当前哈希", "326/326 live MATCH", "326/326 PASS")

    # Board17 published artifacts: signed manifest + formal validation + live re-hash.
    board17_summary = read_json(BOARD17_VALIDATION_SUMMARY)
    board17_fields, board17_rows = read_csv(BOARD17_ARTIFACT_MANIFEST)
    board17_recheck_fields, board17_recheck_rows = read_csv(BOARD17_ARTIFACT_RECHECK)
    required_board17 = {"relative_path", "size_bytes", "sha256"}
    required_board17_recheck = {"relative_path", "resolved_path", "inside_project", "expected_size_bytes", "actual_size_bytes", "expected_sha256", "actual_sha256", "status"}
    require(required_board17.issubset(board17_fields), f"Board17工件清单缺列: {sorted(required_board17 - set(board17_fields))}")
    require(required_board17_recheck.issubset(board17_recheck_fields), f"Board17工件复核缺列: {sorted(required_board17_recheck - set(board17_recheck_fields))}")
    require(len(board17_rows) == 305 and len(board17_recheck_rows) == 305, "Board17工件清单或复核不是305行")
    require(is_true(board17_summary.get("pass")), "Board17正式验收未PASS")
    require(as_int(board17_summary.get("check_count"), "Board17 check_count") == 59, "Board17检查数不是59")
    require(as_int(board17_summary.get("pass_count"), "Board17 pass_count") == 59, "Board17不是59/59 PASS")
    require(as_int(board17_summary.get("failure_count"), "Board17 failure_count") == 0, "Board17存在正式验收失败")
    require(as_int(board17_summary.get("board17_artifact_manifest_count"), "board17_artifact_manifest_count") == 305, "Board17正式清单数不是305")
    board17_recheck_by_relative = {row["relative_path"]: row for row in board17_recheck_rows}
    require(len(board17_recheck_by_relative) == 305, "Board17工件复核相对路径不唯一")
    for row in board17_rows:
        source = (PROJECT_ROOT / Path(row["relative_path"])).resolve()
        try:
            source.relative_to(PROJECT_ROOT.resolve())
        except ValueError as exc:
            raise GateError(f"Board17工件路径越出项目: {source}") from exc
        actual_size, actual_sha = require_live_file_matches(
            source, row["size_bytes"], row["sha256"], cache, "Board17已发布工件",
        )
        audit = board17_recheck_by_relative.get(row["relative_path"])
        require(audit is not None, f"Board17工件复核缺少路径: {row['relative_path']}")
        require(is_true(audit["inside_project"]), f"Board17工件复核标记越界: {source}")
        require(Path(audit["resolved_path"]).resolve() == source, f"Board17工件解析路径不符: {source}")
        require(audit["status"].upper() == "MATCH", f"Board17工件复核非MATCH: {source}")
        require(as_int(audit["expected_size_bytes"], "Board17 expected_size") == actual_size, f"Board17期望大小交叉不符: {source}")
        require(as_int(audit["actual_size_bytes"], "Board17 actual_size") == actual_size, f"Board17旧复核大小与当前不符: {source}")
        require(audit["expected_sha256"].upper() == row["sha256"].upper(), f"Board17期望SHA交叉不符: {source}")
        require(audit["actual_sha256"].upper() == actual_sha, f"Board17旧复核SHA与当前不符: {source}")
    require(as_int(build_summary.get("board17_artifact_count"), "board17_artifact_count") == 305, "构建摘要Board17工件数不是305")
    require(as_int(build_summary.get("board17_artifact_match_count"), "board17_artifact_match_count") == 305, "构建摘要Board17工件不是305/305")
    require(is_true(build_summary.get("board17_pass")), "构建摘要board17_pass为false")
    add_gate(gates, "Board17已发布工件当前哈希", "305/305 live MATCH", "305/305 PASS")

    # Explicit source-paper gate, anchored in the protected frozen manifest.
    paper_rows = [row for row in freeze_rows if row["类别"] in {"小论文", "硕士论文"}]
    require(len(paper_rows) == 2, "冻结清单未恰好包含小论文与硕士论文各一条")
    require({row["类别"] for row in paper_rows} == {"小论文", "硕士论文"}, "论文冻结类别不完整")
    paper_hashes: dict[str, str] = {}
    for row in paper_rows:
        path = Path(row["绝对路径"]).resolve()
        _, current_sha = require_live_file_matches(
            path, row["文件大小_字节"], row["SHA256"], cache, f"{row['类别']}当前源",
        )
        audit = protected_by_path.get(str(path).lower())
        require(audit is not None and audit["status"].upper() == "MATCH", f"{row['类别']}未进入326保护源PASS集合")
        paper_hashes[row["类别"]] = current_sha
    require(input_summary.get("thesis_sha256", "").upper() == paper_hashes["硕士论文"], "Board18冻结摘要硕士论文SHA与总基线不一致")
    require(is_true(input_summary.get("thesis_hash_ok")), "Board18冻结摘要thesis_hash_ok为false")
    add_gate(
        gates,
        "论文源与小论文当前哈希",
        f"thesis={paper_hashes['硕士论文']}; manuscript_0824={paper_hashes['小论文']}",
        "match frozen protected baselines",
    )
    return {
        "board18_input_count": 80,
        "protected_source_count": 326,
        "board17_artifact_count": 305,
        "thesis_sha256": paper_hashes["硕士论文"],
        "manuscript_0824_sha256": paper_hashes["小论文"],
        "authority_paths": [
            project_relative(INPUT_MANIFEST),
            project_relative(INPUT_RECHECK),
            project_relative(FROZEN_SOURCE_FREEZE),
            project_relative(PROTECTED_SOURCE_RECHECK),
            project_relative(BOARD17_ARTIFACT_MANIFEST),
            project_relative(BOARD17_ARTIFACT_RECHECK),
        ],
    }


def preflight_index(gates: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]], dict[str, dict[str, str]], bytes]:
    fieldnames, rows = read_csv(INDEX_PATH)
    require("对象ID" in fieldnames, "总索引缺少对象ID列")
    require(len(rows) == 45, f"总索引应为45行，实际{len(rows)}行")
    by_id = {row["对象ID"]: row for row in rows}
    require(len(by_id) == len(rows), "总索引对象ID不唯一")
    require(TARGET_SET.issubset(by_id), f"总索引缺少目标对象: {sorted(TARGET_SET - set(by_id))}")
    require(len(rows) - len(TARGET_IDS) == 34, "目标11行之外应恰有34行")
    for object_id in TARGET_IDS:
        row = by_id[object_id]
        raw_success = row.get("成功文件夹", "")
        require(raw_success, f"{object_id}没有预定义成功文件夹")
        success = (PROJECT_ROOT / Path(raw_success)).resolve()
        try:
            success.relative_to((PROJECT_ROOT / "test").resolve())
        except ValueError as exc:
            raise GateError(f"{object_id}成功目录不在test内: {success}") from exc
        require(not success.exists(), f"拒绝覆盖已存在的成功目录: {success}")
    for path in (PUBLISH_MANIFEST, PUBLISH_SUMMARY, PUBLISH_GATES, INDEX_BEFORE_COPY, INDEX_AFTER_COPY):
        require(not path.exists(), f"拒绝覆盖已有发布记录: {path}")
    add_gate(gates, "总索引目标与非目标行数", "11 target + 34 untouched", "11 + 34")
    add_gate(gates, "成功目录发布前不存在", 11, "11/11 absent")
    return fieldnames, rows, by_id, INDEX_PATH.read_bytes()


def preflight_comparisons(gates: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]], list[str], list[dict[str, str]]]:
    summary = read_json(COMPARISON_SUMMARY)
    detail_fields, detail = read_csv(COMPARISON_DETAIL)
    dataset_fields, datasets = read_csv(COMPARISON_DATASET)
    require(as_int(summary.get("expected_detail_count"), "expected_detail_count") == 135, "比较预期数不是135")
    require(as_int(summary.get("detail_count"), "detail_count") == 135, "比较实际数不是135")
    require(as_int(summary.get("failure_count"), "failure_count") == 0, "比较存在失败")
    require(is_true(summary.get("pass")), "比较汇总未PASS")
    require(len(detail) == 135, f"比较明细应135行，实际{len(detail)}")
    require(all(row.get("status", "").strip().upper() == "PASS" for row in detail), "135条比较并非全部PASS")
    keys = [(row.get("comparison"), row.get("dataset_id"), row.get("floor"), row.get("method")) for row in detail]
    require(len(set(keys)) == 135, "135条比较键不唯一")
    add_gate(gates, "响应逐列比较", "135/135 PASS", "135/135 PASS")
    return detail_fields, detail, dataset_fields, datasets


def preflight_independent(gates: list[dict[str, Any]]) -> dict[str, Any]:
    summary = read_json(INDEPENDENT_SUMMARY)
    _, matrix = read_csv(INDEPENDENT_MATRIX)
    _, response = read_csv(INDEPENDENT_RESPONSE)
    require(str(summary.get("status", "")).upper() == "PASS", "独立重算汇总未PASS")
    require(as_int(summary.get("matrix_check_count"), "matrix_check_count") == 60, "独立矩阵检查数不是60")
    require(as_int(summary.get("matrix_pass_count"), "matrix_pass_count") == 60, "独立矩阵不是60/60 PASS")
    require(as_int(summary.get("response_check_count"), "response_check_count") == 47, "独立响应检查数不是47")
    require(as_int(summary.get("response_pass_count"), "response_pass_count") == 47, "独立响应不是47/47 PASS")
    require(len(matrix) == 60 and all(row.get("result", "").upper() == "PASS" for row in matrix), "矩阵明细不是60/60 PASS")
    require(len(response) == 47 and all(row.get("result", "").upper() == "PASS" for row in response), "响应明细不是47/47 PASS")
    require(summary.get("force_equation") == "M*qdd + C*qd + K*q = +f_projection*u(t)", "独立重算正号载荷合同不一致")
    require(float(summary.get("dt_s")) == 1.0 / 1024.0, "独立重算dt不是1/1024 s")
    require(float(summary.get("stop_time_s")) == 40.0, "独立重算终止时间不是40 s")
    add_gate(gates, "独立矩阵重建", "60/60 PASS", "60/60 PASS")
    add_gate(gates, "独立响应重算", "47/47 PASS", "47/47 PASS")
    return summary


def preflight_history(gates: list[dict[str, Any]]) -> dict[str, Any]:
    summary = read_json(HISTORY_SUMMARY)
    _, rows = read_csv(HISTORY_ADJUDICATION)
    require(str(summary.get("overall_status", "")).upper() == "PASS", "历史候选人工审计未PASS")
    require(as_int(summary.get("manual_candidate_count"), "manual_candidate_count") == 6, "历史候选数不是6")
    require(as_int(summary.get("total_excluded_file_count"), "total_excluded_file_count") == 6, "历史候选不是6/6排除")
    require(as_int(summary.get("supports_board18_timeseries_file_count"), "supports_board18_timeseries_file_count") == 0, "发现可支持板块18的作者历史时程")
    require(as_int(summary.get("inspection_failure_file_count"), "inspection_failure_file_count") == 0, "历史候选存在检查失败")
    require(is_true(summary.get("all_original_files_unchanged")), "历史候选原件哈希发生变化")
    require(len(rows) == 6, f"历史裁决应6行，实际{len(rows)}")
    for row in rows:
        require(row.get("adjudication", "").startswith("EXCLUDED_"), "历史候选存在未排除项")
        require(not is_true(row.get("supports_board18_timeseries")), "历史候选行标记为支持板块18时程")
        require(is_true(row.get("hash_unchanged")), "历史候选源文件哈希发生变化")
    add_gate(gates, "作者历史时程候选审计", "6/6 excluded; 0 usable", "6/6 excluded; no historical timeseries")
    return summary


def preflight_generation(gates: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, str]], dict[str, list[dict[str, str]]], dict[str, Any]]:
    summary = read_json(CANDIDATE_SUMMARY)
    fields, rows = read_csv(CANDIDATE_MANIFEST)
    required = {
        "figure_pair_id", "object_id", "object_name", "version", "figure_basename",
        "artifact_type", "relative_path", "sha256", "size_bytes", "expected_pdf_pages",
        "expected_png_dpi", "source_data_csv_relative_path", "metrics_csv_relative_path",
        "contract_json_relative_path",
    }
    require(required.issubset(fields), f"候选图清单缺列: {sorted(required - set(fields))}")
    require(str(summary.get("status", "")).upper() == "PASS", "候选图生成汇总未PASS")
    require(as_int(summary.get("object_count"), "object_count") == 11, "候选图对象数不是11")
    require(as_int(summary.get("figure_pair_count"), "figure_pair_count") == 12, "候选图对数不是12")
    require(as_int(summary.get("pdf_count"), "pdf_count") == 12, "候选PDF数不是12")
    require(as_int(summary.get("png_count"), "png_count") == 12, "候选PNG数不是12")
    require(str(summary.get("manifest_sha256", "")).upper() == sha256(CANDIDATE_MANIFEST), "候选图清单哈希与汇总不一致")
    require(str(summary.get("f3_15_historical_assertion", {}).get("status", "")).upper() == "PASS", "图3-15论文历史组合断言未PASS")
    contract = summary.get("output_contract", {})
    require(as_int(contract.get("pdf_pages_each"), "pdf_pages_each") == 1, "候选PDF并非每件1页")
    require(str(contract.get("pdf_kind", "")).lower() == "vector", "候选PDF未声明为矢量")
    require(as_int(contract.get("png_dpi"), "png_dpi") == 600, "候选PNG未声明600 dpi")
    require(not is_true(contract.get("formal_success_directories_created")), "绘图脚本越权创建了正式成功目录")
    require(len(rows) == 24, f"候选图清单应24行，实际{len(rows)}")

    by_object: dict[str, list[dict[str, str]]] = defaultdict(list)
    pair_types: dict[str, set[str]] = defaultdict(set)
    pair_objects: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        object_id = row.get("object_id", "")
        require(object_id in TARGET_SET, f"候选图清单含越界对象: {object_id}")
        artifact_type = row.get("artifact_type", "").strip().lower()
        require(artifact_type in {"pdf", "png"}, f"候选图类型非法: {artifact_type}")
        source = safe_relative_file(FIGURE_CANDIDATES, row.get("relative_path", ""), "候选图路径")
        require(source.suffix.lower() == f".{artifact_type}", f"候选图扩展名与类型不符: {source}")
        require(str(row.get("sha256", "")).upper() == sha256(source), f"候选图哈希不符: {source}")
        require(as_int(row.get("size_bytes"), "size_bytes") == source.stat().st_size, f"候选图大小不符: {source}")
        if artifact_type == "pdf":
            require(as_int(row.get("expected_pdf_pages"), "expected_pdf_pages") == 1, f"候选PDF页数合同不为1: {source}")
        else:
            require(as_int(row.get("expected_png_dpi"), "expected_png_dpi") == 600, f"候选PNG分辨率合同不为600: {source}")
        for column in ("source_data_csv_relative_path", "metrics_csv_relative_path", "contract_json_relative_path"):
            safe_relative_file(FIGURE_CANDIDATES, row.get(column, ""), column)
        pair = row.get("figure_pair_id", "")
        require(pair, "候选图清单figure_pair_id为空")
        pair_types[pair].add(artifact_type)
        pair_objects[pair].add(object_id)
        by_object[object_id].append(row)

    require(set(by_object) == TARGET_SET, f"候选图对象集合不完整: {sorted(set(by_object) ^ TARGET_SET)}")
    require(len(pair_types) == 12, f"候选图pair应12个，实际{len(pair_types)}")
    require(all(types == {"pdf", "png"} for types in pair_types.values()), "每个候选图pair必须恰有PDF与PNG")
    require(all(len(objects) == 1 for objects in pair_objects.values()), "候选图pair跨对象")
    pair_count_by_object = Counter(next(iter(pair_objects[pair])) for pair in pair_objects)
    for object_id in TARGET_IDS:
        expected = 2 if object_id == "F3-15" else 1
        require(pair_count_by_object[object_id] == expected, f"{object_id}候选图pair数应{expected}")
    f315_versions = {row.get("version", "") for row in by_object["F3-15"]}
    require(
        f315_versions == {"paper_historical_composite", "physically_consistent_corrected"},
        f"F3-15机器版本不完整: {sorted(f315_versions)}",
    )
    f315_basenames = {row.get("figure_basename", "") for row in by_object["F3-15"]}
    require(
        f315_basenames == {"F3-15_论文历史组合版", "F3-15_物理一致修正版"},
        f"F3-15中文文件基名不完整: {sorted(f315_basenames)}",
    )
    add_gate(gates, "候选图生成", "11 objects; 12 PDF; 12 PNG", "11 objects; 12 PDF; 12 PNG")
    return fields, rows, by_object, summary


def preflight_figure_validation(gates: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    summary = read_json(VALIDATION_SUMMARY)
    fields, detail = read_csv(VALIDATION_DETAIL)
    require(str(summary.get("status", "")).upper() == "PASS", "独立图件验证未PASS")
    require(as_int(summary.get("failure_count"), "failure_count") == 0, "独立图件验证存在失败")
    require(as_int(summary.get("check_count"), "check_count") == as_int(summary.get("pass_count"), "pass_count"), "独立图件检查并非全部PASS")
    for stem, expected in (("object_count", 11), ("figure_pair_count", 12), ("pdf_count", 12), ("png_count", 12), ("manifest_row_count", 24)):
        require(as_int(summary.get(f"{stem}_expected"), f"{stem}_expected") == expected, f"{stem}预期值错误")
        require(as_int(summary.get(f"{stem}_observed"), f"{stem}_observed") == expected, f"{stem}实际值错误")
    require(is_true(summary.get("f3_15_historical_pointwise_equal")), "F3-15历史局部窗未逐点等于F3-10地震窗")
    require(is_true(summary.get("f3_15_corrected_from_division2_chirp")), "F3-15修正版未来自第二类Chirp")
    require(summary.get("subjective_visual_review") == "NOT_PERFORMED_BY_DESIGN", "独立验证未保持人工视觉边界")
    require(str(summary.get("detail_csv_sha256", "")).upper() == sha256(VALIDATION_DETAIL), "独立图件明细哈希不符")
    add_gate(gates, "独立图件验证", "PASS; 12 vector PDF + 12 PNG@600dpi", "PASS")
    return summary, fields, detail


def preflight_manual_visual(
    gates: list[dict[str, Any]],
    candidate_rows: list[dict[str, str]],
) -> tuple[list[str], list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    fields, rows = read_csv(MANUAL_VISUAL_REVIEW)
    required = {"figure_pair_id", "object_id", "status"}
    require(required.issubset(fields), f"人工视觉验收缺列: {sorted(required - set(fields))}")
    require(len(rows) == 12, f"人工视觉验收应12行，实际{len(rows)}")
    expected_pairs = {row["figure_pair_id"]: row["object_id"] for row in candidate_rows}
    require(len(expected_pairs) == 12, "候选图pair集合不是12个")
    observed_pairs: dict[str, str] = {}
    by_object: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        pair = row.get("figure_pair_id", "")
        object_id = row.get("object_id", "")
        require(pair in expected_pairs, f"人工视觉验收含未知pair: {pair}")
        require(object_id == expected_pairs[pair], f"人工视觉验收pair与对象不匹配: {pair}")
        require(row.get("status", "").strip().upper() == "PASS", f"人工视觉验收未PASS: {pair}")
        require(pair not in observed_pairs, f"人工视觉验收pair重复: {pair}")
        observed_pairs[pair] = object_id
        by_object[object_id].append(row)
    require(set(observed_pairs) == set(expected_pairs), "人工视觉验收未覆盖全部12个图件pair")
    require(all(len(by_object[oid]) == (2 if oid == "F3-15" else 1) for oid in TARGET_IDS), "人工视觉验收对象计数错误")
    add_gate(gates, "主线程人工视觉验收", "12/12 PASS", "12/12 PASS")
    return fields, rows, by_object


def preflight_contracts_and_original_attempt(
    gates: list[dict[str, Any]],
) -> tuple[list[str], dict[str, dict[str, str]], list[str], dict[str, dict[str, str]], dict[str, Any]]:
    contract_fields, contract_rows = read_csv(FIGURE_CONTRACT)
    data_contract_fields, data_contract_rows = read_csv(FIGURE_DATA_CONTRACT)
    contract_by_id = {row.get("对象ID", ""): row for row in contract_rows}
    data_contract_by_id = {row.get("object_id", ""): row for row in data_contract_rows}
    require(set(contract_by_id) == TARGET_SET, "逐图合同未恰好覆盖F3-5至F3-15")
    require(set(data_contract_by_id) == TARGET_SET, "比较逐图合同未恰好覆盖F3-5至F3-15")
    original = read_json(ORIGINAL_ATTEMPT_SUMMARY)
    models = original.get("models", [])
    require(isinstance(models, list) and len(models) == 2, "原样SLX尝试不是两模型")
    for model in models:
        require(model.get("load_status") == "SUCCESS", "原样SLX未能加载，证据链异常")
        require(model.get("update_status") == "ERROR" and model.get("simulation_status") == "ERROR", "原样SLX尝试结果不再是预期失败")
        require(is_true(model.get("sha256_match")), "原样SLX尝试改变了模型哈希")
        require(model.get("close_status") == "SUCCESS_WITHOUT_SAVE", "原样SLX没有无保存关闭")
    add_gate(gates, "逐图合同与原样SLX失败证据", "11 contracts; 2 unchanged failed SLX", "PASS")
    return contract_fields, contract_by_id, data_contract_fields, data_contract_by_id, original


def preflight_response_files() -> dict[str, dict[str, tuple[Path, Path]]]:
    sources: dict[str, dict[str, tuple[Path, Path]]] = {}
    for object_id, (_, basename, _) in OBJECT_RESPONSE_SCOPE.items():
        route_files: dict[str, tuple[Path, Path]] = {}
        for route, root in (
            ("adapted_run1", OUTPUTS / "adapted_run1" / "输入数据"),
            ("adapted_run2", OUTPUTS / "adapted_run2" / "输入数据"),
            ("independent", INDEPENDENT_ROOT / "输入数据"),
        ):
            mat = root / f"{basename}.mat"
            csv_path = root / f"{basename}.csv"
            require(mat.is_file() and csv_path.is_file(), f"{object_id}缺少{route}响应MAT/CSV: {basename}")
            route_files[route] = (mat, csv_path)
        sources[object_id] = route_files
    return sources


def preflight_code_files() -> list[Path]:
    files = sorted(
        [path for path in CODE_ROOT.iterdir() if path.is_file() and path.suffix.lower() in {".py", ".m"}],
        key=lambda path: path.name.lower(),
    )
    names = {path.name for path in files}
    for required in (
        "run_board18_original_attempt.m",
        "run_board18_adapted.m",
        "independent_recompute_board18.py",
        "compare_board18_runs.py",
        SCRIPT_PATH.name,
    ):
        require(required in names, f"缺少发布所需代码: {required}")
    require(any("plot" in path.stem.lower() or "figure" in path.stem.lower() or "绘" in path.stem for path in files), "缺少板块18绘图脚本")
    return files


def copy_verified(source: Path, target: Path, provenance: dict[str, str], source_note: str | None = None) -> None:
    require(source.is_file(), f"复制源不存在: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    require(not target.exists(), f"包内目标冲突: {target}")
    shutil.copy2(source, target)
    require(sha256(source) == sha256(target), f"复制哈希不一致: {source} -> {target}")
    provenance[target.relative_to(target.parents[1]).as_posix()] = source_note or project_relative(source)


def write_generated_text(package: Path, relative: str, text: str, provenance: dict[str, str]) -> Path:
    target = package / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")
    provenance[target.relative_to(package).as_posix()] = f"generated by {project_relative(SCRIPT_PATH)}"
    return target


def write_generated_csv(
    package: Path,
    relative: str,
    fields: list[str],
    rows: list[dict[str, Any]],
    provenance: dict[str, str],
    source_note: str,
) -> Path:
    target = package / relative
    write_csv(target, fields, rows)
    provenance[target.relative_to(package).as_posix()] = source_note
    return target


def readme_text(index_row: dict[str, str], contract: dict[str, str], original: dict[str, Any]) -> str:
    object_id = index_row["对象ID"]
    models = original["models"]
    original_fail = "；".join(
        f"{model.get('model_label')}加载成功，但update={model.get('update_status')}、simulation={model.get('simulation_status')}"
        for model in models
    )
    special = "无额外对象专属修补。"
    if object_id in {"F3-10", "F3-15"}:
        special = (
            "第二类划分冻结SLX的Mux6缺少三层Guyan与Craig--Bampton连线；必要适配路线仅在隔离模型副本中补回，"
            "原始SLX保持哈希不变。"
        )
    if object_id == "F3-15":
        special += (
            " 图3-15同时保留两版：论文历史组合版的全时程为第二类Chirp三层响应，但两个局部窗逐点复用图3-10的"
            "El Centro地震10--11 s与21.5--22.5 s；物理一致修正版改用同一Chirp响应的13--14 s与38--38.3 s。"
        )
    return f"""# {index_row['唯一图号']} {index_row['名称']}

## 对象身份

- 对象ID：`{object_id}`
- 论文原稿图号：`{index_row['论文编号']}`；审计唯一图号：`{index_row['唯一图号']}`
- 论文PDF页：{index_row['PDF页']}；印刷页：{index_row['印刷页']}
- 划分：{contract['划分']}
- 激励：{contract['激励']}
- 楼层：{contract['楼层']}
- 全时窗：{contract['全时窗']}
- 局部窗：{contract['局部窗']}

## 证据标签与边界

- {EVIDENCE_LABEL}
- {HISTORY_LABEL}

这里的“计算级复现”只指现存代码与必要适配路线已经从冻结输入重新计算、重复运行并由独立Python RK4交叉核对；它不把2026年重算数组冒充为梁禹当年的逐点原始数组。仓库检索与6个候选MAT人工审计均未找到可支撑本组图片的作者历史40961×3×3时程。

## 数据轴、公式与求解器

- 响应张量轴固定为 `time_s × floor × method`，即 `response_mm[:, floor, method]`；楼层轴依次为 `Floor 1 / Floor 2 / Floor 3`，方法轴依次为 `Original / Guyan / Craig-Bampton (CB)`。
- Guyan严格保留作者现存代码的历史单侧实现，不用标准双侧合同投影覆盖它。
- Craig--Bampton在当前生成器中先按固定界面广义特征值升序排序，再取 `r=3`；作者Live Script仅在`eig(Kss,Mss)`后直接取前三列，未显式排序，二者身份分开记录。
- 外载合同为 `M*qdd + C*qd + K*q = +f_projection*u(t)`，符号为正；不是常见基底激励负号的自行替换。
- Simulink求解器为固定步长`ode4`，`dt=1/1024 s`，`t=0--40 s`，共40961点。

## 原样模型失败与必要适配

原样冻结模型尝试结果：{original_fail}。主要原因是保存态未自带完整工作区（包括`EQ_intensity`、`T`、`T_cb`以及`G_1/G_2/G_3`状态空间对象），因此不能把“SLX文件存在”误报为“原样可运行”。两份原始SLX均无保存关闭且前后SHA-256一致。

{special}

## 文件说明

- `figures/`：经独立文件验证与主线程12/12人工视觉验收的矢量PDF和600 dpi PNG。
- `data/`：本图候选绘图数据、三条响应来源（两次适配Simulink与一次独立RK4）及135条总比较中的本对象子集。
- `code/`：原样尝试、必要适配仿真、独立RK4、比较、绘图、验证与本发布脚本。
- `evidence/`：逐图合同、指标、数值/图件/历史候选门槛及人工视觉验收子集。
- `artifact_manifest.csv`：包内逐文件大小、SHA-256与来源。
"""


def build_updated_index_bytes(
    original_bytes: bytes,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> tuple[bytes, list[dict[str, str]]]:
    has_bom = original_bytes.startswith(codecs.BOM_UTF8)
    payload = original_bytes[len(codecs.BOM_UTF8):] if has_bom else original_bytes
    text = payload.decode("utf-8")
    physical_lines = text.splitlines(keepends=True)
    parsed = list(csv.reader(io.StringIO(text, newline="")))
    require(len(parsed) == len(physical_lines), "总索引含跨行CSV字段，拒绝无法逐行原样保护的更新")
    require(parsed and parsed[0] == fieldnames, "总索引原始表头与DictReader不一致")
    by_id = {row["对象ID"]: row for row in rows}
    updated_rows: list[dict[str, str]] = []
    new_lines = [physical_lines[0]]
    for line, values in zip(physical_lines[1:], parsed[1:]):
        require(len(values) == len(fieldnames), "总索引物理行列数异常")
        row = dict(zip(fieldnames, values))
        object_id = row["对象ID"]
        if object_id not in TARGET_SET:
            new_lines.append(line)
            updated_rows.append(row)
            continue
        row["当前证据等级"] = EVIDENCE_LABEL
        row["当前状态"] = f"{EVIDENCE_LABEL}；11对象数值、独立重算、图件与人工视觉门槛均PASS；{HISTORY_LABEL}"
        boundary = f"{HISTORY_LABEL}；成功目录不代表获得梁禹历史逐点时程"
        old_note = row.get("备注", "").strip()
        row["备注"] = old_note if boundary in old_note else f"{old_note}；{boundary}".lstrip("；")
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        buffer = io.StringIO(newline="")
        csv.writer(buffer, lineterminator=ending).writerow([row.get(name, "") for name in fieldnames])
        new_lines.append(buffer.getvalue())
        updated_rows.append(row)

    new_payload = "".join(new_lines).encode("utf-8")
    updated_bytes = (codecs.BOM_UTF8 if has_bom else b"") + new_payload
    _, reread_rows = read_csv_from_bytes(updated_bytes)
    require(len(reread_rows) == 45, "更新后总索引行数不是45")
    before_by_id = {row["对象ID"]: row for row in rows}
    after_by_id = {row["对象ID"]: row for row in reread_rows}
    for object_id in set(before_by_id) - TARGET_SET:
        require(before_by_id[object_id] == after_by_id[object_id], f"非目标索引行被改变: {object_id}")
    for object_id in TARGET_IDS:
        require(after_by_id[object_id]["成功文件夹"] == by_id[object_id]["成功文件夹"], f"{object_id}成功文件夹字段被改写")
        require(after_by_id[object_id]["当前证据等级"] == EVIDENCE_LABEL, f"{object_id}证据标签更新失败")
        require(HISTORY_LABEL in after_by_id[object_id]["当前状态"], f"{object_id}历史边界未写入")
    return updated_bytes, reread_rows


def read_csv_from_bytes(payload: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    require(reader.fieldnames is not None, "内存CSV缺少表头")
    return list(reader.fieldnames), [dict(row) for row in reader]


def create_package_manifest(package: Path, provenance: dict[str, str]) -> tuple[Path, list[dict[str, Any]]]:
    manifest = package / "artifact_manifest.csv"
    rows: list[dict[str, Any]] = []
    for path in sorted(package.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path == manifest or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(package).as_posix()
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "source": provenance.get(relative, f"generated by {project_relative(SCRIPT_PATH)}"),
            }
        )
    require(rows, f"拒绝为空包写清单: {package}")
    write_csv(manifest, ["relative_path", "size_bytes", "sha256", "source"], rows)
    return manifest, rows


def package_object(
    package: Path,
    object_id: str,
    index_row: dict[str, str],
    contract_fields: list[str],
    contract: dict[str, str],
    data_contract_fields: list[str],
    data_contract: dict[str, str],
    candidate_fields: list[str],
    candidate_rows: list[dict[str, str]],
    manual_fields: list[str],
    manual_rows: list[dict[str, str]],
    validation_fields: list[str],
    validation_rows: list[dict[str, str]],
    comparison_fields: list[str],
    comparison_rows: list[dict[str, str]],
    dataset_fields: list[str],
    dataset_rows: list[dict[str, str]],
    response_files: dict[str, tuple[Path, Path]],
    code_files: list[Path],
    original: dict[str, Any],
) -> tuple[Path, list[dict[str, Any]]]:
    provenance: dict[str, str] = {}
    write_generated_text(package, "README.md", readme_text(index_row, contract, original), provenance)

    unique_figure_sources: dict[str, Path] = {}
    for row in candidate_rows:
        source = safe_relative_file(FIGURE_CANDIDATES, row["relative_path"], "候选图路径")
        unique_figure_sources[source.name] = source
    require(len(unique_figure_sources) == (4 if object_id == "F3-15" else 2), f"{object_id}候选图文件名不唯一")
    for name, source in sorted(unique_figure_sources.items()):
        target = package / "figures" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        require(sha256(source) == sha256(target), f"图件复制哈希不一致: {source}")
        provenance[target.relative_to(package).as_posix()] = project_relative(source)

    support_columns = (
        ("source_data_csv_relative_path", "data/figure_plot_data.csv"),
        ("metrics_csv_relative_path", "evidence/metrics.csv"),
        ("contract_json_relative_path", "evidence/contract.json"),
    )
    for column, target_relative in support_columns:
        values = {row[column] for row in candidate_rows}
        require(len(values) == 1, f"{object_id}的{column}不唯一")
        source = safe_relative_file(FIGURE_CANDIDATES, next(iter(values)), column)
        target = package / target_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        require(sha256(source) == sha256(target), f"支持文件复制哈希不一致: {source}")
        provenance[target.relative_to(package).as_posix()] = project_relative(source)

    for route, (mat, csv_path) in response_files.items():
        for source in (mat, csv_path):
            target = package / "data" / route / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            require(sha256(source) == sha256(target), f"响应文件复制哈希不一致: {source}")
            provenance[target.relative_to(package).as_posix()] = project_relative(source)

    dataset_id, _, floors = OBJECT_RESPONSE_SCOPE[object_id]
    subset = [row for row in comparison_rows if row.get("dataset_id") == dataset_id and row.get("floor") in floors]
    expected_subset = 27 if object_id == "F3-5" else 9
    require(len(subset) == expected_subset, f"{object_id}比较子集应{expected_subset}行，实际{len(subset)}")
    require(all(row.get("status", "").upper() == "PASS" for row in subset), f"{object_id}比较子集含失败")
    write_generated_csv(
        package, "data/response_comparison_subset.csv", comparison_fields, subset, provenance,
        f"subset of {project_relative(COMPARISON_DETAIL)}",
    )
    dataset_subset = [row for row in dataset_rows if row.get("dataset_id") == dataset_id]
    require(len(dataset_subset) == 3, f"{object_id}数据集比较汇总应3行")
    write_generated_csv(
        package, "data/response_dataset_comparison_subset.csv", dataset_fields, dataset_subset, provenance,
        f"subset of {project_relative(COMPARISON_DATASET)}",
    )

    write_generated_csv(package, "evidence/figure_contract.csv", contract_fields, [contract], provenance, f"row {object_id} of {project_relative(FIGURE_CONTRACT)}")
    write_generated_csv(package, "evidence/figure_data_contract.csv", data_contract_fields, [data_contract], provenance, f"row {object_id} of {project_relative(FIGURE_DATA_CONTRACT)}")
    write_generated_csv(package, "evidence/candidate_manifest_subset.csv", candidate_fields, candidate_rows, provenance, f"subset of {project_relative(CANDIDATE_MANIFEST)}")
    write_generated_csv(package, "evidence/manual_visual_review_subset.csv", manual_fields, manual_rows, provenance, f"subset of {project_relative(MANUAL_VISUAL_REVIEW)}")
    object_validation = [row for row in validation_rows if row.get("object_id") == object_id]
    if not object_validation:
        object_validation = validation_rows
    write_generated_csv(package, "evidence/independent_figure_validation.csv", validation_fields, object_validation, provenance, f"object subset or complete copy of {project_relative(VALIDATION_DETAIL)}")

    common_evidence = (
        COMPARISON_SUMMARY,
        INDEPENDENT_SUMMARY,
        INDEPENDENT_MATRIX,
        INDEPENDENT_RESPONSE,
        HISTORY_SUMMARY,
        HISTORY_ADJUDICATION,
        CANDIDATE_SUMMARY,
        VALIDATION_SUMMARY,
        ORIGINAL_ATTEMPT_SUMMARY,
        ORIGINAL_ATTEMPT_ROOT / "model_attempt_summary.csv",
        ORIGINAL_ATTEMPT_ROOT / "division2_mux6_inputs.csv",
    )
    for source in common_evidence:
        require(source.is_file(), f"缺少公共证据: {source}")
        target = package / "evidence" / source.name
        if target.exists():
            target = package / "evidence" / f"{source.parent.name}_{source.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        require(sha256(source) == sha256(target), f"公共证据复制哈希不一致: {source}")
        provenance[target.relative_to(package).as_posix()] = project_relative(source)

    for source in code_files:
        target = package / "code" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        require(sha256(source) == sha256(target), f"代码复制哈希不一致: {source}")
        provenance[target.relative_to(package).as_posix()] = project_relative(source)

    _, manifest_rows = create_package_manifest(package, provenance)
    return package / "artifact_manifest.csv", manifest_rows


def main() -> int:
    gates: list[dict[str, Any]] = []

    # Phase 1: strictly read-only preflight.  No mkdir/write occurs above this line.
    index_fields, index_rows, index_by_id, original_index_bytes = preflight_index(gates)
    authority_summary = preflight_authoritative_hashes(gates)
    comparison_fields, comparison_rows, dataset_fields, dataset_rows = preflight_comparisons(gates)
    independent_summary = preflight_independent(gates)
    history_summary = preflight_history(gates)
    candidate_fields, candidate_rows, candidate_by_object, generation_summary = preflight_generation(gates)
    validation_summary, validation_fields, validation_rows = preflight_figure_validation(gates)
    manual_fields, manual_rows, manual_by_object = preflight_manual_visual(gates, candidate_rows)
    contract_fields, contract_by_id, data_contract_fields, data_contract_by_id, original = preflight_contracts_and_original_attempt(gates)
    response_files = preflight_response_files()
    code_files = preflight_code_files()
    add_gate(gates, "发布源文件完整性", "11 response scopes; code/evidence present", "PASS")
    require(all(row["status"] == "PASS" for row in gates), "存在未PASS发布门槛")

    # Phase 2: all gates passed.  Build complete packages only in an isolated staging tree.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stage_root = BOARD_ROOT / "tmp" / f"publish_board18_{stamp}_{os.getpid()}"
    require(not stage_root.exists(), f"暂存目录意外存在: {stage_root}")
    stage_packages = stage_root / "packages"
    stage_outputs = stage_root / "board_outputs"
    stage_packages.mkdir(parents=True)
    stage_outputs.mkdir(parents=True)

    updated_index_bytes, _ = build_updated_index_bytes(original_index_bytes, index_fields, index_rows)
    staged_index = stage_root / "全部对象总索引.updated.csv"
    staged_index.write_bytes(updated_index_bytes)
    (stage_outputs / INDEX_BEFORE_COPY.name).write_bytes(original_index_bytes)
    (stage_outputs / INDEX_AFTER_COPY.name).write_bytes(updated_index_bytes)

    package_records: list[dict[str, Any]] = []
    global_artifacts: list[dict[str, Any]] = []
    staged_to_target: list[tuple[Path, Path, str]] = []
    for object_id in TARGET_IDS:
        index_row = index_by_id[object_id]
        target = (PROJECT_ROOT / Path(index_row["成功文件夹"])).resolve()
        stage_package = stage_packages / object_id
        manifest, manifest_rows = package_object(
            stage_package,
            object_id,
            index_row,
            contract_fields,
            contract_by_id[object_id],
            data_contract_fields,
            data_contract_by_id[object_id],
            candidate_fields,
            candidate_by_object[object_id],
            manual_fields,
            manual_by_object[object_id],
            validation_fields,
            validation_rows,
            comparison_fields,
            comparison_rows,
            dataset_fields,
            dataset_rows,
            response_files[object_id],
            code_files,
            original,
        )
        package_records.append(
            {
                "object_id": object_id,
                "success_directory": project_relative(target),
                "package_file_count_excluding_manifest": len(manifest_rows),
                "artifact_manifest_sha256": sha256(manifest),
                "evidence_level": EVIDENCE_LABEL,
                "historical_pointwise_status": HISTORY_LABEL,
            }
        )
        for row in manifest_rows:
            global_artifacts.append(
                {
                    "object_id": object_id,
                    "success_directory": project_relative(target),
                    **row,
                }
            )
        global_artifacts.append(
            {
                "object_id": object_id,
                "success_directory": project_relative(target),
                "relative_path": "artifact_manifest.csv",
                "size_bytes": manifest.stat().st_size,
                "sha256": sha256(manifest),
                "source": f"generated by {project_relative(SCRIPT_PATH)}",
            }
        )
        staged_to_target.append((stage_package, target, object_id))

    gate_path = stage_outputs / PUBLISH_GATES.name
    write_csv(gate_path, ["gate", "actual", "expected", "status"], gates)
    manifest_path = stage_outputs / PUBLISH_MANIFEST.name
    write_csv(
        manifest_path,
        ["object_id", "success_directory", "relative_path", "size_bytes", "sha256", "source"],
        global_artifacts,
    )
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "publication_executed": True,
        "object_count": 11,
        "success_directory_count": 11,
        "package_records": package_records,
        "gate_count": len(gates),
        "gate_pass_count": len(gates),
        "comparison_pass_count": 135,
        "independent_matrix_pass_count": independent_summary["matrix_pass_count"],
        "independent_response_pass_count": independent_summary["response_pass_count"],
        "manual_history_excluded_count": history_summary["total_excluded_file_count"],
        "figure_pdf_count": generation_summary["pdf_count"],
        "figure_png_count": generation_summary["png_count"],
        "independent_figure_validation_status": validation_summary["status"],
        "manual_visual_review_pass_count": 12,
        "index_row_count": 45,
        "index_target_rows_updated": 11,
        "index_non_target_rows_unchanged": 34,
        "index_sha256_before": sha256_bytes(original_index_bytes),
        "index_sha256_after": sha256_bytes(updated_index_bytes),
        "publish_manifest_sha256": sha256(manifest_path),
        "publish_gate_results_sha256": sha256(gate_path),
        "evidence_level": EVIDENCE_LABEL,
        "historical_pointwise_status": HISTORY_LABEL,
        "authoritative_hash_gates": authority_summary,
    }
    write_json(stage_outputs / PUBLISH_SUMMARY.name, summary)

    # Commit is rollback-capable because all formal target directories were absent.
    moved_targets: list[tuple[Path, Path]] = []
    committed_output_paths: list[Path] = []
    index_committed = False
    try:
        for stage_package, target, _ in staged_to_target:
            require(not target.exists(), f"提交前成功目录已被并发创建: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(stage_package), str(target))
            moved_targets.append((target, stage_package))
        index_temp = INDEX_PATH.with_name(f".{INDEX_PATH.name}.{stamp}.tmp")
        index_temp.write_bytes(staged_index.read_bytes())
        os.replace(index_temp, INDEX_PATH)
        index_committed = True
        for staged in sorted(stage_outputs.iterdir(), key=lambda path: path.name):
            target = OUTPUTS / staged.name
            require(not target.exists(), f"提交前发布记录已被并发创建: {target}")
            shutil.move(str(staged), str(target))
            committed_output_paths.append(target)
    except Exception:
        for path in committed_output_paths:
            if path.is_file():
                path.unlink()
        if index_committed:
            rollback_temp = INDEX_PATH.with_name(f".{INDEX_PATH.name}.{stamp}.rollback.tmp")
            rollback_temp.write_bytes(original_index_bytes)
            os.replace(rollback_temp, INDEX_PATH)
        for target, stage_package in reversed(moved_targets):
            stage_package.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.move(str(target), str(stage_package))
        raise
    finally:
        if stage_root.exists():
            resolved = stage_root.resolve()
            require(resolved.parent == (BOARD_ROOT / "tmp").resolve(), f"拒绝清理越界暂存目录: {resolved}")
            shutil.rmtree(resolved)

    # Post-commit verification: 11 packages exist, index target fields changed, 34 rows unchanged.
    _, final_rows = read_csv(INDEX_PATH)
    final_by_id = {row["对象ID"]: row for row in final_rows}
    original_by_id = {row["对象ID"]: row for row in index_rows}
    require(all((PROJECT_ROOT / Path(final_by_id[oid]["成功文件夹"])).is_dir() for oid in TARGET_IDS), "提交后并非11个成功目录全部存在")
    require(all(final_by_id[oid]["当前证据等级"] == EVIDENCE_LABEL for oid in TARGET_IDS), "提交后目标证据标签不一致")
    require(all(final_by_id[oid] == original_by_id[oid] for oid in set(original_by_id) - TARGET_SET), "提交后34个非目标索引行改变")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
