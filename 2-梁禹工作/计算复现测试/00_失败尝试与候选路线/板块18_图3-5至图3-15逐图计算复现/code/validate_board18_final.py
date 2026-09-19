from __future__ import annotations

"""Independent post-publication acceptance audit for Board 18.

The validator is deliberately read-only outside ``outputs/final_validation``.
It does not regenerate responses, figures, packages, or index rows.  Existing
authoritative manifests and summaries define the protected populations; this
script only rechecks their current files and the published packages.
"""

import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from PIL import Image, ImageChops

    PIL_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - recorded as a hard failure.
    Image = None  # type: ignore[assignment]
    ImageChops = None  # type: ignore[assignment]
    PIL_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[4]
TEST_ROOT = PROJECT_ROOT / "test"
OUTPUTS = BOARD_ROOT / "outputs"
FINAL_OUTPUT = OUTPUTS / "final_validation"
DETAIL_PATH = FINAL_OUTPUT / "board18_final_validation_detail.csv"
SUMMARY_PATH = FINAL_OUTPUT / "board18_final_validation_summary.json"

INDEX_PATH = TEST_ROOT / "00_总索引与复现规则" / "全部对象总索引.csv"
INDEX_RELATIVE = "test/00_总索引与复现规则/全部对象总索引.csv"
INDEX_BEFORE = OUTPUTS / "publish_index_before.csv"
INDEX_AFTER = OUTPUTS / "publish_index_after.csv"
FROZEN_INDEX_ROW_NUMBER = 56
FROZEN_INDEX_ROLE = "45对象总索引"
FROZEN_INDEX_COPY_RELATIVE = (
    "input/plotting_baseline/验证记录/汇总/全部对象总索引.csv"
)
PUBLISH_SUMMARY = OUTPUTS / "publish_board18_summary.json"
PUBLISH_GATES = OUTPUTS / "publish_board18_gate_results.csv"
PUBLISH_MANIFEST = OUTPUTS / "publish_board18_manifest.csv"

INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
BUILD_SUMMARY = OUTPUTS / "build_board18_summary.json"
PROTECTED_RECHECK = OUTPUTS / "protected_source_recheck.csv"
BOARD17_RECHECK = OUTPUTS / "board17_artifact_recheck.csv"
BOARD17_MANIFEST = (
    BOARD_ROOT
    / "input"
    / "upstream_passports"
    / "board17"
    / "board17_artifact_manifest.csv"
)
BOARD17_SUMMARY = (
    BOARD_ROOT
    / "input"
    / "upstream_passports"
    / "board17"
    / "board17_final_validation_summary.json"
)

COMPARISON_ROOT = OUTPUTS / "comparisons"
COMPARISON_SUMMARY = COMPARISON_ROOT / "response_comparison_summary.json"
COMPARISON_DETAIL = COMPARISON_ROOT / "response_column_comparisons.csv"
INDEPENDENT_ROOT = OUTPUTS / "independent"
INDEPENDENT_SUMMARY = INDEPENDENT_ROOT / "summary.json"
INDEPENDENT_MATRIX = INDEPENDENT_ROOT / "matrix_checks.csv"
INDEPENDENT_RESPONSE = INDEPENDENT_ROOT / "response_checks.csv"
HISTORY_SUMMARY = OUTPUTS / "manual_history_audit_summary.json"
HISTORY_ADJUDICATION = OUTPUTS / "manual_history_file_adjudication.csv"
FIGURE_CANDIDATES = OUTPUTS / "figure_candidates"
CANDIDATE_MANIFEST = FIGURE_CANDIDATES / "artifact_manifest.csv"
FIGURE_VALIDATION = OUTPUTS / "figure_validation"
FIGURE_VALIDATION_SUMMARY = FIGURE_VALIDATION / "validation_summary.json"
MANUAL_VISUAL_REVIEW = FIGURE_VALIDATION / "manual_visual_review.csv"

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
EXPECTED_SUCCESS_RELATIVE = {
    "F3-5": "test/图3-5_单位激励下的3层响应",
    "F3-6": "test/图3-6_第一类划分地震激励下一层水平位移",
    "F3-7": "test/图3-7_第一类划分地震激励下二层水平位移",
    "F3-8": "test/图3-8_第一类划分地震激励下三层水平位移",
    "F3-9": "test/图3-9_第二类划分地震激励下一层水平位移",
    "F3-10": "test/图3-10_第二类划分地震激励下三层水平位移",
    "F3-11": "test/图3-11_第一类划分Chirp信号下一层水平位移",
    "F3-12": "test/图3-12_第一类划分Chirp信号下二层水平位移",
    "F3-13": "test/图3-13_第一类划分Chirp信号下三层水平位移",
    "F3-14": "test/图3-14_第二类划分Chirp信号下一层水平位移",
    "F3-15": "test/图3-15_第二类划分Chirp信号下三层水平位移",
}

EVIDENCE_LABEL = "计算级复现（现存代码/必要适配路线）"
HISTORY_LABEL = "作者历史逐点值：待决定"
EXPECTED_INDEX_STATUS = (
    f"{EVIDENCE_LABEL}；11对象数值、独立重算、图件与人工视觉门槛均PASS；{HISTORY_LABEL}"
)
EXPECTED_TOP_LEVEL = {
    "README.md",
    "figures",
    "data",
    "code",
    "evidence",
    "artifact_manifest.csv",
}
DETAIL_COLUMNS = [
    "sequence",
    "category",
    "check",
    "object_id",
    "artifact",
    "expected",
    "actual",
    "status",
    "evidence",
    "detail",
]

DETAIL_ROWS: list[dict[str, str]] = []
STATE: dict[str, Any] = {}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def render(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def record(
    category: str,
    check: str,
    passed: bool,
    *,
    expected: Any,
    actual: Any,
    evidence: Path | str = "",
    detail: str = "",
    object_id: str = "",
    artifact: str = "",
) -> None:
    DETAIL_ROWS.append(
        {
            "sequence": str(len(DETAIL_ROWS) + 1),
            "category": category,
            "check": check,
            "object_id": object_id,
            "artifact": artifact,
            "expected": render(expected),
            "actual": render(actual),
            "status": "PASS" if passed else "FAIL",
            "evidence": str(evidence),
            "detail": detail,
        }
    )


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"1", "TRUE", "PASS", "YES"}


def as_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv_file(
    path: Path,
    category: str,
    label: str,
    required_columns: Iterable[str] = (),
) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        record(
            category,
            f"{label}存在且可读",
            False,
            expected="existing CSV",
            actual="MISSING",
            evidence=path,
        )
        return [], []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        missing = sorted(set(required_columns) - set(fields))
        record(
            category,
            f"{label}存在、可解析且列合同完整",
            not missing,
            expected={"required_columns": sorted(required_columns)},
            actual={"row_count": len(rows), "missing_columns": missing},
            evidence=path,
        )
        return fields, rows
    except Exception as exc:
        record(
            category,
            f"{label}存在且可读",
            False,
            expected="parseable UTF-8 CSV",
            actual=f"{type(exc).__name__}: {exc}",
            evidence=path,
        )
        return [], []


def read_json_file(path: Path, category: str, label: str) -> dict[str, Any]:
    if not path.is_file():
        record(
            category,
            f"{label}存在且可读",
            False,
            expected="existing JSON object",
            actual="MISSING",
            evidence=path,
        )
        return {}
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
        ok = isinstance(value, dict)
        record(
            category,
            f"{label}存在且可读",
            ok,
            expected="JSON object",
            actual=type(value).__name__,
            evidence=path,
        )
        return value if ok else {}
    except Exception as exc:
        record(
            category,
            f"{label}存在且可读",
            False,
            expected="parseable JSON object",
            actual=f"{type(exc).__name__}: {exc}",
            evidence=path,
        )
        return {}


def resolve_inside(base: Path, relative: str) -> Path:
    candidate = (base / Path(relative)).resolve()
    candidate.relative_to(base.resolve())
    return candidate


def live_file_matches(path: Path, expected_size: Any, expected_hash: Any) -> tuple[bool, dict[str, Any]]:
    if not path.is_file():
        return False, {"exists": False, "path": str(path)}
    actual_size = path.stat().st_size
    actual_hash = sha256(path)
    expected_size_int = as_int(expected_size)
    expected_hash_text = str(expected_hash).strip().upper()
    return (
        actual_size == expected_size_int and actual_hash == expected_hash_text,
        {
            "exists": True,
            "size_bytes": actual_size,
            "sha256": actual_hash,
        },
    )


def run_section(name: str, action: Callable[[], None]) -> None:
    try:
        action()
    except Exception as exc:  # Keep producing a complete failure report.
        record(
            "internal",
            f"{name}验收段完整执行",
            False,
            expected="no unhandled exception",
            actual=f"{type(exc).__name__}: {exc}",
            evidence=SCRIPT_PATH,
        )


def audit_publication_records() -> None:
    summary = read_json_file(PUBLISH_SUMMARY, "publication", "Board18发布摘要")
    gate_fields, gates = read_csv_file(
        PUBLISH_GATES,
        "publication",
        "Board18发布门槛",
        {"gate", "actual", "expected", "status"},
    )
    manifest_fields, manifest = read_csv_file(
        PUBLISH_MANIFEST,
        "publication",
        "Board18全局发布清单",
        {"object_id", "success_directory", "relative_path", "size_bytes", "sha256", "source"},
    )
    summary_ok = (
        summary.get("status") == "PASS"
        and is_true(summary.get("publication_executed"))
        and as_int(summary.get("object_count")) == 11
        and as_int(summary.get("success_directory_count")) == 11
        and as_int(summary.get("index_row_count")) == 45
        and as_int(summary.get("index_target_rows_updated")) == 11
        and as_int(summary.get("index_non_target_rows_unchanged")) == 34
        and summary.get("evidence_level") == EVIDENCE_LABEL
        and summary.get("historical_pointwise_status") == HISTORY_LABEL
    )
    record(
        "publication",
        "发布摘要声明11对象已提交且边界标签正确",
        summary_ok,
        expected={"status": "PASS", "objects": 11, "index": "11 changed + 34 unchanged"},
        actual=summary,
        evidence=PUBLISH_SUMMARY,
    )
    gates_ok = bool(gate_fields) and bool(gates) and all(
        row.get("status", "").strip().upper() == "PASS" for row in gates
    )
    record(
        "publication",
        "发布门槛全部PASS且数量与摘要一致",
        gates_ok
        and len(gates) == as_int(summary.get("gate_count"))
        and len(gates) == as_int(summary.get("gate_pass_count")),
        expected="all gate rows PASS; row count equals summary",
        actual={"rows": len(gates), "status_counts": dict(Counter(row.get("status", "") for row in gates))},
        evidence=PUBLISH_GATES,
    )
    hashes_ok = (
        PUBLISH_MANIFEST.is_file()
        and PUBLISH_GATES.is_file()
        and str(summary.get("publish_manifest_sha256", "")).upper() == sha256(PUBLISH_MANIFEST)
        and str(summary.get("publish_gate_results_sha256", "")).upper() == sha256(PUBLISH_GATES)
    )
    record(
        "publication",
        "发布摘要引用的全局清单与门槛SHA实时一致",
        hashes_ok,
        expected={
            "manifest": summary.get("publish_manifest_sha256"),
            "gates": summary.get("publish_gate_results_sha256"),
        },
        actual={
            "manifest": sha256(PUBLISH_MANIFEST) if PUBLISH_MANIFEST.is_file() else "MISSING",
            "gates": sha256(PUBLISH_GATES) if PUBLISH_GATES.is_file() else "MISSING",
        },
        evidence=PUBLISH_SUMMARY,
    )
    STATE["publish_summary"] = summary
    STATE["publish_gates"] = gates
    STATE["publish_manifest_fields"] = manifest_fields
    STATE["publish_manifest"] = manifest


def audit_index() -> None:
    required = {
        "对象ID",
        "当前证据等级",
        "当前状态",
        "成功文件夹",
        "备注",
    }
    fields, rows = read_csv_file(INDEX_PATH, "index", "当前全部对象总索引", required)
    ids = [row.get("对象ID", "") for row in rows]
    by_id = {row.get("对象ID", ""): row for row in rows}
    shape_ok = len(rows) == 45 and len(set(ids)) == 45 and TARGET_SET.issubset(by_id)
    record(
        "index",
        "总索引45行、45个唯一对象且包含本板块11对象",
        shape_ok,
        expected={"rows": 45, "unique_ids": 45, "target_ids": list(TARGET_IDS)},
        actual={"rows": len(rows), "unique_ids": len(set(ids)), "missing_targets": sorted(TARGET_SET - set(ids))},
        evidence=INDEX_PATH,
    )
    target_status_ok = shape_ok
    target_actual: dict[str, Any] = {}
    for object_id in TARGET_IDS:
        row = by_id.get(object_id, {})
        expected_path = EXPECTED_SUCCESS_RELATIVE[object_id]
        ok = (
            row.get("成功文件夹", "").replace("\\", "/") == expected_path
            and row.get("当前证据等级") == EVIDENCE_LABEL
            and row.get("当前状态") == EXPECTED_INDEX_STATUS
            and HISTORY_LABEL in row.get("备注", "")
            and "成功目录不代表获得梁禹历史逐点时程" in row.get("备注", "")
        )
        target_status_ok = target_status_ok and ok
        target_actual[object_id] = {
            "success_directory": row.get("成功文件夹"),
            "evidence": row.get("当前证据等级"),
            "status": row.get("当前状态"),
        }
    record(
        "index",
        "本板块11行成功目录、计算级标签与历史值边界精确正确",
        target_status_ok,
        expected={
            "evidence": EVIDENCE_LABEL,
            "status": EXPECTED_INDEX_STATUS,
            "success_directories": EXPECTED_SUCCESS_RELATIVE,
        },
        actual=target_actual,
        evidence=INDEX_PATH,
    )

    before_fields, before_rows = read_csv_file(INDEX_BEFORE, "index", "发布前索引副本", required)
    after_fields, after_rows = read_csv_file(INDEX_AFTER, "index", "发布后索引副本", required)
    summary = STATE.get("publish_summary", {})
    byte_chain_ok = (
        INDEX_BEFORE.is_file()
        and INDEX_AFTER.is_file()
        and INDEX_PATH.is_file()
        and sha256(INDEX_BEFORE) == str(summary.get("index_sha256_before", "")).upper()
        and sha256(INDEX_AFTER) == str(summary.get("index_sha256_after", "")).upper()
        and INDEX_AFTER.read_bytes() == INDEX_PATH.read_bytes()
    )
    record(
        "index",
        "发布前后索引SHA链闭合且当前索引等于发布后副本",
        byte_chain_ok,
        expected={
            "before_sha256": summary.get("index_sha256_before"),
            "after_sha256": summary.get("index_sha256_after"),
            "live_equals_after": True,
        },
        actual={
            "before_sha256": sha256(INDEX_BEFORE) if INDEX_BEFORE.is_file() else "MISSING",
            "after_sha256": sha256(INDEX_AFTER) if INDEX_AFTER.is_file() else "MISSING",
            "live_sha256": sha256(INDEX_PATH) if INDEX_PATH.is_file() else "MISSING",
        },
        evidence=PUBLISH_SUMMARY,
    )
    before_by_id = {row.get("对象ID", ""): row for row in before_rows}
    after_by_id = {row.get("对象ID", ""): row for row in after_rows}
    changed_ids = {
        object_id
        for object_id in set(before_by_id) | set(after_by_id)
        if before_by_id.get(object_id) != after_by_id.get(object_id)
    }
    non_target_equal = all(
        before_by_id.get(object_id) == after_by_id.get(object_id)
        for object_id in (set(before_by_id) | set(after_by_id)) - TARGET_SET
    )
    allowed_target_changes = True
    for object_id in TARGET_IDS:
        before = before_by_id.get(object_id, {})
        after = after_by_id.get(object_id, {})
        changed_columns = {
            field for field in set(before) | set(after) if before.get(field) != after.get(field)
        }
        allowed_target_changes = allowed_target_changes and changed_columns.issubset(
            {"当前证据等级", "当前状态", "备注"}
        )
    exact_changes_ok = (
        fields == before_fields == after_fields
        and len(before_rows) == len(after_rows) == 45
        and changed_ids == TARGET_SET
        and non_target_equal
        and allowed_target_changes
    )
    record(
        "index",
        "恰好只有本板块11行被更新且其34行逐字段不变",
        exact_changes_ok,
        expected={"changed_ids": list(TARGET_IDS), "non_target_unchanged": 34},
        actual={"changed_ids": sorted(changed_ids), "non_target_equal": non_target_equal},
        evidence=INDEX_BEFORE,
    )
    STATE["index_rows"] = rows
    STATE["index_by_id"] = by_id
    STATE["index_byte_chain_ok"] = byte_chain_ok
    STATE["index_authorized_field_evolution_ok"] = exact_changes_ok and target_status_ok


def audit_packages_and_manifests() -> None:
    summary = STATE.get("publish_summary", {})
    package_records_raw = summary.get("package_records", [])
    package_records = package_records_raw if isinstance(package_records_raw, list) else []
    record_by_id = {
        str(item.get("object_id", "")): item
        for item in package_records
        if isinstance(item, dict)
    }
    record(
        "packages",
        "发布摘要的11个包记录唯一完整",
        len(package_records) == 11 and set(record_by_id) == TARGET_SET,
        expected=list(TARGET_IDS),
        actual=sorted(record_by_id),
        evidence=PUBLISH_SUMMARY,
    )

    expected_global: dict[tuple[str, str, str], dict[str, str]] = {}
    pdfs: list[tuple[str, Path]] = []
    pngs: list[tuple[str, Path]] = []
    package_roots: dict[str, Path] = {}
    for object_id in TARGET_IDS:
        relative = EXPECTED_SUCCESS_RELATIVE[object_id]
        package = (PROJECT_ROOT / Path(relative)).resolve()
        package_roots[object_id] = package
        inside_test = False
        try:
            package.relative_to(TEST_ROOT.resolve())
            inside_test = True
        except ValueError:
            pass
        expected_path = PROJECT_ROOT / Path(relative)
        directory_ok = inside_test and package == expected_path.resolve() and package.is_dir()
        record(
            "packages",
            "预期中文成功目录在test内精确存在",
            directory_ok,
            expected=str(expected_path),
            actual={"resolved": str(package), "is_dir": package.is_dir(), "inside_test": inside_test},
            evidence=INDEX_PATH,
            object_id=object_id,
        )
        if not package.is_dir():
            continue
        top_level = {path.name for path in package.iterdir()}
        record(
            "packages",
            "成功目录顶层结构精确且无未申明项",
            top_level == EXPECTED_TOP_LEVEL,
            expected=sorted(EXPECTED_TOP_LEVEL),
            actual=sorted(top_level),
            evidence=package,
            object_id=object_id,
        )
        manifest_path = package / "artifact_manifest.csv"
        _, local_rows = read_csv_file(
            manifest_path,
            "package_manifest",
            f"{object_id}包内工件清单",
            {"relative_path", "size_bytes", "sha256", "source"},
        )
        local_by_rel = {row.get("relative_path", ""): row for row in local_rows}
        actual_files = {
            path.relative_to(package).as_posix()
            for path in package.rglob("*")
            if path.is_file() and path != manifest_path
        }
        manifest_paths = set(local_by_rel)
        closure_ok = (
            len(local_by_rel) == len(local_rows)
            and "" not in local_by_rel
            and actual_files == manifest_paths
        )
        record(
            "package_manifest",
            "包内实际文件集与局部SHA清单双向闭合",
            closure_ok,
            expected={"manifested_files": sorted(manifest_paths)},
            actual={
                "actual_count": len(actual_files),
                "manifest_count": len(manifest_paths),
                "missing_from_disk": sorted(manifest_paths - actual_files),
                "unmanifested": sorted(actual_files - manifest_paths),
            },
            evidence=manifest_path,
            object_id=object_id,
        )
        for relative_path, row in sorted(local_by_rel.items()):
            try:
                path = resolve_inside(package, relative_path)
                ok, actual = live_file_matches(path, row.get("size_bytes"), row.get("sha256"))
            except Exception as exc:
                path = package / relative_path
                ok = False
                actual = f"{type(exc).__name__}: {exc}"
            record(
                "package_manifest_item",
                "发布包工件大小与SHA实时匹配",
                ok,
                expected={"size_bytes": row.get("size_bytes"), "sha256": row.get("sha256")},
                actual=actual,
                evidence=manifest_path,
                object_id=object_id,
                artifact=relative_path,
            )
            expected_global[(object_id, relative, relative_path)] = dict(row)
        manifest_record = record_by_id.get(object_id, {})
        manifest_hash = sha256(manifest_path) if manifest_path.is_file() else "MISSING"
        manifest_record_ok = (
            manifest_record.get("success_directory", "").replace("\\", "/") == relative
            and as_int(manifest_record.get("package_file_count_excluding_manifest")) == len(local_rows)
            and str(manifest_record.get("artifact_manifest_sha256", "")).upper() == manifest_hash
            and manifest_record.get("evidence_level") == EVIDENCE_LABEL
            and manifest_record.get("historical_pointwise_status") == HISTORY_LABEL
        )
        record(
            "package_manifest",
            "包内清单SHA、文件数与发布摘要一致",
            manifest_record_ok,
            expected=manifest_record,
            actual={"manifest_sha256": manifest_hash, "file_count": len(local_rows)},
            evidence=PUBLISH_SUMMARY,
            object_id=object_id,
        )
        expected_global[(object_id, relative, "artifact_manifest.csv")] = {
            "relative_path": "artifact_manifest.csv",
            "size_bytes": str(manifest_path.stat().st_size) if manifest_path.is_file() else "-1",
            "sha256": manifest_hash,
            "source": "generated package manifest",
        }
        pdfs.extend((object_id, path) for path in sorted((package / "figures").glob("*.pdf")))
        pngs.extend((object_id, path) for path in sorted((package / "figures").glob("*.png")))

    global_rows = STATE.get("publish_manifest", [])
    global_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    duplicate_keys: list[tuple[str, str, str]] = []
    for row in global_rows:
        key = (
            row.get("object_id", ""),
            row.get("success_directory", "").replace("\\", "/"),
            row.get("relative_path", "").replace("\\", "/"),
        )
        if key in global_by_key:
            duplicate_keys.append(key)
        global_by_key[key] = row
    keys_ok = not duplicate_keys and set(global_by_key) == set(expected_global)
    record(
        "global_manifest",
        "全局发布清单与11个包内清单加清单本身双向闭合",
        keys_ok,
        expected={"row_count": len(expected_global), "duplicates": 0},
        actual={
            "row_count": len(global_rows),
            "unique_keys": len(global_by_key),
            "duplicates": duplicate_keys,
            "missing": sorted(set(expected_global) - set(global_by_key)),
            "extra": sorted(set(global_by_key) - set(expected_global)),
        },
        evidence=PUBLISH_MANIFEST,
    )
    for key, row in sorted(global_by_key.items()):
        object_id, success_relative, relative_path = key
        expected_row = expected_global.get(key, {})
        try:
            package = (PROJECT_ROOT / Path(success_relative)).resolve()
            path = resolve_inside(package, relative_path)
            ok, actual = live_file_matches(path, row.get("size_bytes"), row.get("sha256"))
            if expected_row:
                ok = (
                    ok
                    and as_int(row.get("size_bytes")) == as_int(expected_row.get("size_bytes"))
                    and str(row.get("sha256", "")).upper()
                    == str(expected_row.get("sha256", "")).upper()
                )
        except Exception as exc:
            path = PROJECT_ROOT / Path(success_relative) / relative_path
            ok = False
            actual = f"{type(exc).__name__}: {exc}"
        record(
            "global_manifest_item",
            "全局发布清单工件与包内清单及实时文件一致",
            ok and key in expected_global,
            expected={"size_bytes": expected_row.get("size_bytes"), "sha256": expected_row.get("sha256")},
            actual=actual,
            evidence=PUBLISH_MANIFEST,
            object_id=object_id,
            artifact=relative_path,
        )

    stems_pdf = {(object_id, path.stem) for object_id, path in pdfs}
    stems_png = {(object_id, path.stem) for object_id, path in pngs}
    per_object_pdf = Counter(object_id for object_id, _ in pdfs)
    per_object_png = Counter(object_id for object_id, _ in pngs)
    figure_count_ok = (
        len(pdfs) == len(pngs) == 12
        and stems_pdf == stems_png
        and all(per_object_pdf[oid] == (2 if oid == "F3-15" else 1) for oid in TARGET_IDS)
        and all(per_object_png[oid] == (2 if oid == "F3-15" else 1) for oid in TARGET_IDS)
    )
    record(
        "packages",
        "11个成功包共有12对PDF/PNG且F3-15恰有两版",
        figure_count_ok,
        expected={"pdf": 12, "png": 12, "F3-15_pairs": 2, "other_pairs_each": 1},
        actual={
            "pdf": len(pdfs),
            "png": len(pngs),
            "pdf_per_object": dict(per_object_pdf),
            "png_per_object": dict(per_object_png),
            "unpaired_pdf": sorted(stems_pdf - stems_png),
            "unpaired_png": sorted(stems_png - stems_pdf),
        },
        evidence=PUBLISH_MANIFEST,
    )
    STATE["package_roots"] = package_roots
    STATE["pdfs"] = pdfs
    STATE["pngs"] = pngs


def audit_freeze_and_protected_sources() -> None:
    freeze = read_json_file(INPUT_FREEZE_SUMMARY, "freeze", "冻结输入摘要")
    _, rows = read_csv_file(
        INPUT_MANIFEST,
        "freeze",
        "冻结输入权威清单",
        {
            "role",
            "source_path",
            "copied_relative_path",
            "source_size_bytes",
            "copy_size_bytes",
            "source_sha256_before",
            "source_sha256_after",
            "copy_sha256",
            "status",
        },
    )
    manifest_hash = sha256(INPUT_MANIFEST) if INPUT_MANIFEST.is_file() else "MISSING"
    summary_ok = (
        len(rows) == 80
        and as_int(freeze.get("source_count")) == 80
        and as_int(freeze.get("copy_count")) == 80
        and as_int(freeze.get("match_count")) == 80
        and is_true(freeze.get("all_match"))
        and is_true(freeze.get("thesis_hash_ok"))
        and str(freeze.get("manifest_sha256", "")).upper() == manifest_hash
        and all(row.get("status", "").upper() == "MATCH" for row in rows)
    )
    record(
        "freeze",
        "冻结输入权威摘要与清单80/80 MATCH",
        summary_ok,
        expected={"source": 80, "copy": 80, "match": 80, "all_match": True},
        actual={
            "rows": len(rows),
            "status_counts": dict(Counter(row.get("status", "") for row in rows)),
            "summary": freeze,
            "manifest_sha256": manifest_hash,
        },
        evidence=INPUT_FREEZE_SUMMARY,
    )
    frozen_index_role_rows = [
        index
        for index, row in enumerate(rows, start=1)
        if row.get("role") == FROZEN_INDEX_ROLE
    ]
    frozen_index_identity_ok = frozen_index_role_rows == [FROZEN_INDEX_ROW_NUMBER]
    record(
        "freeze",
        "冻结清单中授权演进角色唯一且恰为第56行45对象总索引",
        frozen_index_identity_ok,
        expected={"one_based_row": FROZEN_INDEX_ROW_NUMBER, "role": FROZEN_INDEX_ROLE},
        actual={"matching_rows": frozen_index_role_rows},
        evidence=INPUT_MANIFEST,
    )
    unchanged_pass_count = 0
    unchanged_fail_count = 0
    authorized_index_pass_count = 0
    authorized_index_fail_count = 0
    for index, row in enumerate(rows, start=1):
        source = Path(row.get("source_path", ""))
        is_authorized_index_row = (
            index == FROZEN_INDEX_ROW_NUMBER and row.get("role") == FROZEN_INDEX_ROLE
        )
        if is_authorized_index_row:
            try:
                copy = resolve_inside(BOARD_ROOT, row.get("copied_relative_path", ""))
                expected_copy = resolve_inside(BOARD_ROOT, FROZEN_INDEX_COPY_RELATIVE)
                source_path_ok = source.resolve() == INDEX_PATH.resolve()
                copy_path_ok = copy == expected_copy
                manifest_old_hash = str(row.get("copy_sha256", "")).upper()
                manifest_old_size = as_int(row.get("copy_size_bytes"))
                manifest_contract_ok = (
                    row.get("status", "").upper() == "MATCH"
                    and as_int(row.get("source_size_bytes")) == manifest_old_size
                    and str(row.get("source_sha256_before", "")).upper() == manifest_old_hash
                    and str(row.get("source_sha256_after", "")).upper() == manifest_old_hash
                )
                copy_manifest_ok, copy_actual = live_file_matches(
                    copy, row.get("copy_size_bytes"), row.get("copy_sha256")
                )
                before_manifest_ok, before_actual = live_file_matches(
                    INDEX_BEFORE, row.get("copy_size_bytes"), row.get("copy_sha256")
                )
                before_copy_equal = (
                    copy.is_file()
                    and INDEX_BEFORE.is_file()
                    and copy.read_bytes() == INDEX_BEFORE.read_bytes()
                )
                source_after_equal = (
                    source.is_file()
                    and INDEX_PATH.is_file()
                    and INDEX_AFTER.is_file()
                    and source.read_bytes() == INDEX_PATH.read_bytes() == INDEX_AFTER.read_bytes()
                )
                before_after_differ = (
                    INDEX_BEFORE.is_file()
                    and INDEX_AFTER.is_file()
                    and INDEX_BEFORE.read_bytes() != INDEX_AFTER.read_bytes()
                )
                prior_index_proof_ok = (
                    is_true(STATE.get("index_byte_chain_ok"))
                    and is_true(STATE.get("index_authorized_field_evolution_ok"))
                )
                ok = (
                    frozen_index_identity_ok
                    and source_path_ok
                    and copy_path_ok
                    and manifest_contract_ok
                    and copy_manifest_ok
                    and before_manifest_ok
                    and before_copy_equal
                    and source_after_equal
                    and before_after_differ
                    and prior_index_proof_ok
                )
                actual = {
                    "one_based_row": index,
                    "role": row.get("role"),
                    "source_path_exact": source_path_ok,
                    "copy_path_exact": copy_path_ok,
                    "manifest_old_contract": manifest_contract_ok,
                    "copy_live": copy_actual,
                    "publish_before": before_actual,
                    "copy_equals_publish_before_bytes": before_copy_equal,
                    "source_equals_live_and_publish_after_bytes": source_after_equal,
                    "publish_before_differs_from_after": before_after_differ,
                    "index_34_unchanged_and_11_authorized_fields_proved": prior_index_proof_ok,
                    "publish_after_sha256": sha256(INDEX_AFTER) if INDEX_AFTER.is_file() else "MISSING",
                    "live_source_sha256": sha256(source) if source.is_file() else "MISSING",
                }
            except Exception as exc:
                ok = False
                actual = f"{type(exc).__name__}: {exc}"
            if ok:
                authorized_index_pass_count += 1
            else:
                authorized_index_fail_count += 1
            record(
                "freeze_authorized_index",
                "冻结第56行总索引授权演进闭合：副本=发布前，源=当前=发布后",
                ok,
                expected={
                    "one_based_row": FROZEN_INDEX_ROW_NUMBER,
                    "role": FROZEN_INDEX_ROLE,
                    "source_path": str(INDEX_PATH),
                    "copy_relative_path": FROZEN_INDEX_COPY_RELATIVE,
                    "copy_equals_manifest_and_publish_before": True,
                    "source_equals_live_and_publish_after": True,
                    "before_after_authorization": "34 non-target unchanged; 11 target rows authorized fields only",
                },
                actual=actual,
                evidence=INPUT_MANIFEST,
                artifact=f"row {index}: {row.get('role', '')}",
            )
            continue
        try:
            copy = resolve_inside(BOARD_ROOT, row.get("copied_relative_path", ""))
            source_ok, source_actual = live_file_matches(
                source, row.get("source_size_bytes"), row.get("source_sha256_after")
            )
            copy_ok, copy_actual = live_file_matches(
                copy, row.get("copy_size_bytes"), row.get("copy_sha256")
            )
            hashes_consistent = (
                str(row.get("source_sha256_before", "")).upper()
                == str(row.get("source_sha256_after", "")).upper()
                == str(row.get("copy_sha256", "")).upper()
            )
            ok = source_ok and copy_ok and hashes_consistent and row.get("status", "").upper() == "MATCH"
            actual = {"source": source_actual, "copy": copy_actual, "hashes_consistent": hashes_consistent}
        except Exception as exc:
            ok = False
            actual = f"{type(exc).__name__}: {exc}"
        if ok:
            unchanged_pass_count += 1
        else:
            unchanged_fail_count += 1
        record(
            "freeze_item",
            "非授权演进的冻结输入源与隔离副本大小/SHA实时一致",
            ok,
            expected={
                "source_size": row.get("source_size_bytes"),
                "source_sha256": row.get("source_sha256_after"),
                "copy_size": row.get("copy_size_bytes"),
                "copy_sha256": row.get("copy_sha256"),
            },
            actual=actual,
            evidence=INPUT_MANIFEST,
            artifact=f"row {index}: {row.get('role', '')}",
        )
    freeze_accounting = {
        "unchanged_pass": unchanged_pass_count,
        "unchanged_fail": unchanged_fail_count,
        "authorized_index_pass": authorized_index_pass_count,
        "authorized_index_fail": authorized_index_fail_count,
        "accounted_total": unchanged_pass_count
        + unchanged_fail_count
        + authorized_index_pass_count
        + authorized_index_fail_count,
    }
    freeze_accounting_ok = (
        unchanged_pass_count == 79
        and unchanged_fail_count == 0
        and authorized_index_pass_count == 1
        and authorized_index_fail_count == 0
        and freeze_accounting["accounted_total"] == 80
    )
    record(
        "freeze",
        "发布后冻结输入账户闭合：79项实时不变+1项总索引授权演进=80项全覆盖",
        freeze_accounting_ok,
        expected={
            "unchanged_pass": 79,
            "unchanged_fail": 0,
            "authorized_index_pass": 1,
            "authorized_index_fail": 0,
            "accounted_total": 80,
        },
        actual=freeze_accounting,
        evidence=INPUT_MANIFEST,
    )
    STATE["freeze_accounting"] = freeze_accounting

    build = read_json_file(BUILD_SUMMARY, "protected", "Board18构建与上游保护摘要")
    _, protected = read_csv_file(
        PROTECTED_RECHECK,
        "protected",
        "326件原始受保护源权威回查表",
        {
            "row",
            "category",
            "absolute_path",
            "expected_size_bytes",
            "actual_size_bytes",
            "expected_sha256",
            "actual_sha256",
            "status",
        },
    )
    protected_summary_ok = (
        len(protected) == 326
        and as_int(build.get("protected_source_count")) == 326
        and as_int(build.get("protected_source_match_count")) == 326
        and is_true(build.get("protected_pass"))
        and all(row.get("status", "").upper() == "MATCH" for row in protected)
    )
    record(
        "protected",
        "原始受保护源权威摘要与回查表326/326 MATCH",
        protected_summary_ok,
        expected={"protected": 326, "match": 326},
        actual={
            "rows": len(protected),
            "status_counts": dict(Counter(row.get("status", "") for row in protected)),
            "summary_count": build.get("protected_source_count"),
            "summary_match": build.get("protected_source_match_count"),
        },
        evidence=BUILD_SUMMARY,
    )
    for row in protected:
        path = Path(row.get("absolute_path", ""))
        ok, actual = live_file_matches(path, row.get("expected_size_bytes"), row.get("expected_sha256"))
        ok = (
            ok
            and row.get("status", "").upper() == "MATCH"
            and as_int(row.get("actual_size_bytes")) == as_int(row.get("expected_size_bytes"))
            and str(row.get("actual_sha256", "")).upper()
            == str(row.get("expected_sha256", "")).upper()
        )
        record(
            "protected_item",
            "原始受保护源实时大小/SHA与权威回查表一致",
            ok,
            expected={"size_bytes": row.get("expected_size_bytes"), "sha256": row.get("expected_sha256")},
            actual=actual,
            evidence=PROTECTED_RECHECK,
            artifact=f"{row.get('row', '')}: {row.get('category', '')}: {path}",
        )

    thesis_freeze = [row for row in rows if row.get("role") == "硕士论文PDF"]
    thesis_protected = [
        row
        for row in protected
        if row.get("category") == "硕士论文" and Path(row.get("absolute_path", "")).name == "梁禹手稿.pdf"
    ]
    manuscript_rows = [
        row
        for row in protected
        if row.get("category") == "小论文" and Path(row.get("absolute_path", "")).name == "manuscript_0824.tex"
    ]
    thesis_ok = False
    thesis_actual: dict[str, Any] = {
        "freeze_rows": len(thesis_freeze),
        "protected_rows": len(thesis_protected),
    }
    if len(thesis_freeze) == len(thesis_protected) == 1:
        freeze_row = thesis_freeze[0]
        protected_row = thesis_protected[0]
        thesis_path = Path(freeze_row["source_path"])
        live_hash = sha256(thesis_path) if thesis_path.is_file() else "MISSING"
        hashes = {
            str(freeze.get("thesis_sha256", "")).upper(),
            str(freeze_row.get("source_sha256_after", "")).upper(),
            str(freeze_row.get("copy_sha256", "")).upper(),
            str(protected_row.get("expected_sha256", "")).upper(),
            live_hash,
        }
        thesis_ok = len(hashes) == 1 and "MISSING" not in hashes
        thesis_actual.update({"path": str(thesis_path), "hashes": sorted(hashes)})
    record(
        "paper_sources",
        "梁禹硕士论文源PDF实时SHA与冻结/受保护记录一致",
        thesis_ok,
        expected=freeze.get("thesis_sha256"),
        actual=thesis_actual,
        evidence=INPUT_MANIFEST,
        artifact="梁禹手稿.pdf",
    )
    manuscript_ok = False
    manuscript_actual: dict[str, Any] = {"protected_rows": len(manuscript_rows)}
    if len(manuscript_rows) == 1:
        row = manuscript_rows[0]
        path = Path(row["absolute_path"])
        live_hash = sha256(path) if path.is_file() else "MISSING"
        manuscript_ok = live_hash == str(row.get("expected_sha256", "")).upper()
        manuscript_actual.update({"path": str(path), "live_sha256": live_hash})
    record(
        "paper_sources",
        "manuscript_0824.tex实时SHA与受保护记录一致",
        manuscript_ok,
        expected=manuscript_rows[0].get("expected_sha256") if len(manuscript_rows) == 1 else "one authoritative row",
        actual=manuscript_actual,
        evidence=PROTECTED_RECHECK,
        artifact="manuscript_0824.tex",
    )
    STATE["build_summary"] = build


def audit_board17_integrity() -> None:
    summary = read_json_file(BOARD17_SUMMARY, "board17", "Board17最终验收摘要")
    _, manifest = read_csv_file(
        BOARD17_MANIFEST,
        "board17",
        "Board17权威工件清单",
        {"relative_path", "size_bytes", "sha256"},
    )
    _, recheck = read_csv_file(
        BOARD17_RECHECK,
        "board17",
        "Board17工件实时回查表",
        {
            "relative_path",
            "resolved_path",
            "inside_project",
            "expected_size_bytes",
            "actual_size_bytes",
            "expected_sha256",
            "actual_sha256",
            "status",
        },
    )
    build = STATE.get("build_summary", {})
    manifest_by_rel = {row.get("relative_path", ""): row for row in manifest}
    recheck_by_rel = {row.get("relative_path", ""): row for row in recheck}
    population_ok = (
        len(manifest) == len(manifest_by_rel) == 305
        and len(recheck) == len(recheck_by_rel) == 305
        and set(manifest_by_rel) == set(recheck_by_rel)
        and is_true(summary.get("pass"))
        and as_int(summary.get("failure_count")) == 0
        and as_int(summary.get("board17_artifact_manifest_count")) == 305
        and as_int(build.get("board17_artifact_count")) == 305
        and as_int(build.get("board17_artifact_match_count")) == 305
        and is_true(build.get("board17_pass"))
    )
    record(
        "board17",
        "Board17权威清单、原验收摘要与Board18发布前回查表305/305同集合",
        population_ok,
        expected={"manifest": 305, "recheck": 305, "summary_pass": True},
        actual={
            "manifest": len(manifest),
            "recheck": len(recheck),
            "summary_pass": summary.get("pass"),
            "missing": sorted(set(manifest_by_rel) - set(recheck_by_rel)),
            "extra": sorted(set(recheck_by_rel) - set(manifest_by_rel)),
        },
        evidence=BOARD17_SUMMARY,
    )
    publish_gates = STATE.get("publish_gates", [])
    board17_publish_gates = [
        row
        for row in publish_gates
        if "Board17" in row.get("gate", "") or "305/305" in row.get("actual", "")
    ]
    publisher_preflight_ok = any(
        row.get("status", "").upper() == "PASS"
        and "305" in f"{row.get('actual', '')} {row.get('expected', '')}"
        for row in board17_publish_gates
    )
    record(
        "board17",
        "Board18发布器在提交前已把Board17工件305/305作为硬门槛",
        publisher_preflight_ok,
        expected="at least one PASS publication gate explicitly covering Board17 305/305",
        actual=board17_publish_gates,
        evidence=PUBLISH_GATES,
    )
    index_manifest_row = manifest_by_rel.get(INDEX_RELATIVE)
    index_recheck_row = recheck_by_rel.get(INDEX_RELATIVE)
    authorized_index_ok = False
    authorized_index_actual: dict[str, Any] = {
        "manifest_row_present": index_manifest_row is not None,
        "recheck_row_present": index_recheck_row is not None,
    }
    if index_manifest_row is not None and index_recheck_row is not None:
        old_hash = str(index_manifest_row.get("sha256", "")).upper()
        old_size = as_int(index_manifest_row.get("size_bytes"))
        before_hash = sha256(INDEX_BEFORE) if INDEX_BEFORE.is_file() else "MISSING"
        after_hash = sha256(INDEX_AFTER) if INDEX_AFTER.is_file() else "MISSING"
        live_hash = sha256(INDEX_PATH) if INDEX_PATH.is_file() else "MISSING"
        authorized_index_ok = (
            index_recheck_row.get("status", "").upper() == "MATCH"
            and str(index_recheck_row.get("expected_sha256", "")).upper() == old_hash
            and str(index_recheck_row.get("actual_sha256", "")).upper() == old_hash
            and as_int(index_recheck_row.get("expected_size_bytes")) == old_size
            and as_int(index_recheck_row.get("actual_size_bytes")) == old_size
            and INDEX_BEFORE.is_file()
            and INDEX_BEFORE.stat().st_size == old_size
            and before_hash == old_hash
            and INDEX_AFTER.is_file()
            and INDEX_PATH.is_file()
            and INDEX_AFTER.read_bytes() == INDEX_PATH.read_bytes()
            and after_hash == live_hash
            and live_hash != old_hash
        )
        authorized_index_actual.update(
            {
                "board17_expected_sha256": old_hash,
                "publish_index_before_sha256": before_hash,
                "publish_index_after_sha256": after_hash,
                "live_index_sha256": live_hash,
                "old_size_bytes": old_size,
            }
        )
    record(
        "board17",
        "Board17清单中唯一授权演进文件为全局总索引：旧哈希对应发布前副本，新哈希对应当前/发布后副本",
        authorized_index_ok,
        expected={
            "authorized_relative_path": INDEX_RELATIVE,
            "before_equals_board17_expected": True,
            "after_equals_live": True,
            "after_differs_from_before": True,
        },
        actual=authorized_index_actual,
        evidence=INDEX_BEFORE,
        artifact=INDEX_RELATIVE,
    )
    unchanged_count = 0
    unexpected_changes: list[str] = []
    for relative, manifest_row in sorted(manifest_by_rel.items()):
        if relative == INDEX_RELATIVE:
            continue
        row = recheck_by_rel.get(relative, {})
        try:
            path = resolve_inside(PROJECT_ROOT, relative)
            ok, actual = live_file_matches(path, manifest_row.get("size_bytes"), manifest_row.get("sha256"))
            ok = (
                ok
                and is_true(row.get("inside_project"))
                and row.get("status", "").upper() == "MATCH"
                and Path(row.get("resolved_path", "")).resolve() == path
                and as_int(row.get("expected_size_bytes")) == as_int(manifest_row.get("size_bytes"))
                and str(row.get("expected_sha256", "")).upper()
                == str(manifest_row.get("sha256", "")).upper()
                and as_int(row.get("actual_size_bytes")) == as_int(manifest_row.get("size_bytes"))
                and str(row.get("actual_sha256", "")).upper()
                == str(manifest_row.get("sha256", "")).upper()
            )
        except Exception as exc:
            ok = False
            actual = f"{type(exc).__name__}: {exc}"
        if ok:
            unchanged_count += 1
        else:
            unexpected_changes.append(relative)
        record(
            "board17_item",
            "Board17既有工件实时大小/SHA未被Board18破坏",
            ok,
            expected={"size_bytes": manifest_row.get("size_bytes"), "sha256": manifest_row.get("sha256")},
            actual=actual,
            evidence=BOARD17_RECHECK,
            artifact=relative,
        )
    record(
        "board17",
        "Board17除授权更新的全局总索引外其304件工件实时不变",
        unchanged_count == 304 and not unexpected_changes,
        expected={"unchanged": 304, "unexpected_changes": []},
        actual={"unchanged": unchanged_count, "unexpected_changes": unexpected_changes},
        evidence=BOARD17_RECHECK,
    )


def audit_numeric_and_history_gates() -> None:
    comparison_summary = read_json_file(COMPARISON_SUMMARY, "numeric", "135项响应比较摘要")
    _, comparisons = read_csv_file(
        COMPARISON_DETAIL,
        "numeric",
        "135项响应比较明细",
        {
            "comparison",
            "dataset_id",
            "floor",
            "method",
            "time_max_abs_s",
            "response_max_abs_mm",
            "peak_normalized_max_abs",
            "time_tolerance_s",
            "abs_tolerance_mm",
            "peak_normalized_tolerance",
            "status",
        },
    )
    comparison_keys = [
        (row.get("comparison"), row.get("dataset_id"), row.get("floor"), row.get("method"))
        for row in comparisons
    ]
    numeric_rows_ok = True
    numeric_failures: list[dict[str, Any]] = []
    for row_index, row in enumerate(comparisons):
        values = [
            as_float(row.get("time_max_abs_s")),
            as_float(row.get("response_max_abs_mm")),
            as_float(row.get("peak_normalized_max_abs")),
            as_float(row.get("time_tolerance_s")),
            as_float(row.get("abs_tolerance_mm")),
            as_float(row.get("peak_normalized_tolerance")),
        ]
        row_ok = (
            all(math.isfinite(value) for value in values)
            and values[0] <= values[3]
            and values[1] <= values[4]
            and values[2] <= values[5]
            and row.get("status", "").upper() == "PASS"
        )
        numeric_rows_ok = numeric_rows_ok and row_ok
        if not row_ok:
            numeric_failures.append({"key": comparison_keys[row_index], "values": values})
    comparison_ok = (
        len(comparisons) == 135
        and len(set(comparison_keys)) == 135
        and numeric_rows_ok
        and as_int(comparison_summary.get("expected_detail_count")) == 135
        and as_int(comparison_summary.get("detail_count")) == 135
        and as_int(comparison_summary.get("failure_count")) == 0
        and is_true(comparison_summary.get("pass"))
    )
    record(
        "numeric",
        "两次适配运行、2026绘图基线与独立RK4的135/135逐列门槛PASS",
        comparison_ok,
        expected={"rows": 135, "unique_keys": 135, "all_within_recorded_thresholds": True},
        actual={
            "rows": len(comparisons),
            "unique_keys": len(set(comparison_keys)),
            "status_counts": dict(Counter(row.get("status", "") for row in comparisons)),
            "numeric_failures": numeric_failures[:10],
        },
        evidence=COMPARISON_DETAIL,
    )

    independent = read_json_file(INDEPENDENT_SUMMARY, "numeric", "独立Python RK4摘要")
    _, matrix = read_csv_file(
        INDEPENDENT_MATRIX,
        "numeric",
        "独立RK4矩阵检查",
        {"scope", "object", "metric", "actual", "criterion", "result", "evidence"},
    )
    _, response = read_csv_file(
        INDEPENDENT_RESPONSE,
        "numeric",
        "独立RK4响应检查",
        {"dataset", "division", "floor", "method", "criterion", "result"},
    )
    check_files = independent.get("check_files", {}) if isinstance(independent.get("check_files"), dict) else {}
    independent_ok = (
        str(independent.get("status", "")).upper() == "PASS"
        and as_int(independent.get("matrix_check_count")) == 60
        and as_int(independent.get("matrix_pass_count")) == 60
        and as_int(independent.get("response_check_count")) == 47
        and as_int(independent.get("response_pass_count")) == 47
        and len(matrix) == 60
        and all(row.get("result", "").upper() == "PASS" for row in matrix)
        and len(response) == 47
        and all(row.get("result", "").upper() == "PASS" for row in response)
        and independent.get("force_equation") == "M*qdd + C*qd + K*q = +f_projection*u(t)"
        and as_float(independent.get("dt_s")) == 1.0 / 1024.0
        and as_float(independent.get("stop_time_s")) == 40.0
        and INDEPENDENT_MATRIX.is_file()
        and str(check_files.get("matrix_checks_sha256", "")).upper() == sha256(INDEPENDENT_MATRIX)
        and INDEPENDENT_RESPONSE.is_file()
        and str(check_files.get("response_checks_sha256", "")).upper() == sha256(INDEPENDENT_RESPONSE)
    )
    record(
        "numeric",
        "独立Python RK4为60/60矩阵检查与47/47响应检查PASS",
        independent_ok,
        expected={"matrix": "60/60 PASS", "response": "47/47 PASS", "dt_s": 1.0 / 1024.0},
        actual={
            "summary": {
                "status": independent.get("status"),
                "matrix": [independent.get("matrix_pass_count"), independent.get("matrix_check_count")],
                "response": [independent.get("response_pass_count"), independent.get("response_check_count")],
                "dt_s": independent.get("dt_s"),
                "stop_time_s": independent.get("stop_time_s"),
            },
            "matrix_rows": len(matrix),
            "response_rows": len(response),
        },
        evidence=INDEPENDENT_SUMMARY,
    )

    history = read_json_file(HISTORY_SUMMARY, "history", "作者历史时程候选审计摘要")
    _, history_rows = read_csv_file(
        HISTORY_ADJUDICATION,
        "history",
        "作者历史时程候选裁决",
        {"adjudication", "supports_board18_timeseries", "hash_unchanged"},
    )
    history_ok = (
        history.get("overall_status") == "PASS"
        and as_int(history.get("manual_candidate_count")) == 6
        and as_int(history.get("total_excluded_file_count")) == 6
        and as_int(history.get("supports_board18_timeseries_file_count")) == 0
        and as_int(history.get("inspection_failure_file_count")) == 0
        and is_true(history.get("all_original_files_unchanged"))
        and len(history_rows) == 6
        and all(row.get("adjudication", "").startswith("EXCLUDED_") for row in history_rows)
        and all(not is_true(row.get("supports_board18_timeseries")) for row in history_rows)
        and all(is_true(row.get("hash_unchanged")) for row in history_rows)
    )
    record(
        "history",
        "6个人工候选全部排除且作者历史逐点数组仍为待决定",
        history_ok,
        expected={"candidates": 6, "excluded": 6, "usable_timeseries": 0},
        actual={
            "candidates": history.get("manual_candidate_count"),
            "excluded": history.get("total_excluded_file_count"),
            "usable_timeseries": history.get("supports_board18_timeseries_file_count"),
            "rows": len(history_rows),
        },
        evidence=HISTORY_SUMMARY,
    )

    figure_summary = read_json_file(FIGURE_VALIDATION_SUMMARY, "figure_gate", "独立图件验证摘要")
    figure_gate_ok = (
        figure_summary.get("status") == "PASS"
        and as_int(figure_summary.get("failure_count")) == 0
        and as_int(figure_summary.get("check_count")) == as_int(figure_summary.get("pass_count"))
        and as_int(figure_summary.get("object_count_observed")) == 11
        and as_int(figure_summary.get("figure_pair_count_observed")) == 12
        and as_int(figure_summary.get("pdf_count_observed")) == 12
        and as_int(figure_summary.get("png_count_observed")) == 12
        and is_true(figure_summary.get("f3_15_historical_pointwise_equal"))
        and is_true(figure_summary.get("f3_15_corrected_from_division2_chirp"))
    )
    record(
        "figure_gate",
        "发布前独立图件验证PASS且覆盖11对象/12图对",
        figure_gate_ok,
        expected={"status": "PASS", "objects": 11, "pairs": 12, "pdf": 12, "png": 12},
        actual=figure_summary,
        evidence=FIGURE_VALIDATION_SUMMARY,
    )


def audit_manual_visual_review() -> None:
    _, candidate_rows = read_csv_file(
        CANDIDATE_MANIFEST,
        "visual",
        "候选图工件清单",
        {"figure_pair_id", "object_id", "artifact_type"},
    )
    _, visual_rows = read_csv_file(
        MANUAL_VISUAL_REVIEW,
        "visual",
        "主线程人工视觉验收",
        {"figure_pair_id", "object_id", "status"},
    )
    expected_pairs: dict[str, str] = {}
    pair_conflict = False
    for row in candidate_rows:
        pair = row.get("figure_pair_id", "")
        object_id = row.get("object_id", "")
        if pair in expected_pairs and expected_pairs[pair] != object_id:
            pair_conflict = True
        expected_pairs[pair] = object_id
    observed_pairs: dict[str, str] = {}
    duplicates: list[str] = []
    rows_ok = True
    for row in visual_rows:
        pair = row.get("figure_pair_id", "")
        object_id = row.get("object_id", "")
        if pair in observed_pairs:
            duplicates.append(pair)
        observed_pairs[pair] = object_id
        rows_ok = rows_ok and row.get("status", "").upper() == "PASS"
        rows_ok = rows_ok and expected_pairs.get(pair) == object_id
    visual_ok = (
        not pair_conflict
        and len(expected_pairs) == 12
        and len(visual_rows) == 12
        and len(observed_pairs) == 12
        and not duplicates
        and set(observed_pairs) == set(expected_pairs)
        and rows_ok
    )
    record(
        "visual",
        "主线程人工视觉验收与候选图对12/12唯一对应且全部PASS",
        visual_ok,
        expected={"pairs": 12, "status": "PASS", "duplicates": 0},
        actual={
            "candidate_pairs": len(expected_pairs),
            "visual_rows": len(visual_rows),
            "observed_pairs": len(observed_pairs),
            "duplicates": duplicates,
            "status_counts": dict(Counter(row.get("status", "") for row in visual_rows)),
        },
        evidence=MANUAL_VISUAL_REVIEW,
    )


def audit_readmes() -> None:
    package_roots: dict[str, Path] = STATE.get("package_roots", {})
    for object_id in TARGET_IDS:
        readme = package_roots.get(object_id, PROJECT_ROOT / EXPECTED_SUCCESS_RELATIVE[object_id]) / "README.md"
        try:
            text = readme.read_text(encoding="utf-8")
            required_fragments = [
                "计算级复现",
                HISTORY_LABEL,
                "未找到",
                "作者历史",
                "不把2026年重算数组冒充为梁禹当年的逐点原始数组",
                "time_s × floor × method",
            ]
            missing = [fragment for fragment in required_fragments if fragment not in text]
            forbidden = "time_s × method × floor" in text
            ok = not missing and not forbidden
            actual: Any = {"missing_fragments": missing, "forbidden_wrong_axis_present": forbidden}
        except Exception as exc:
            ok = False
            actual = f"{type(exc).__name__}: {exc}"
        record(
            "readme",
            "README明确计算级复现、历史值待决定、未找到逐点数组与正确张量轴",
            ok,
            expected={
                "required": ["计算级复现", HISTORY_LABEL, "未找到", "time_s × floor × method"],
                "forbidden": "time_s × method × floor",
            },
            actual=actual,
            evidence=readme,
            object_id=object_id,
        )
    f315 = package_roots.get("F3-15", PROJECT_ROOT / EXPECTED_SUCCESS_RELATIVE["F3-15"])
    readme = f315 / "README.md"
    figure_names = {path.name for path in (f315 / "figures").glob("*")} if (f315 / "figures").is_dir() else set()
    expected_names = {
        "F3-15_论文历史组合版.pdf",
        "F3-15_论文历史组合版.png",
        "F3-15_物理一致修正版.pdf",
        "F3-15_物理一致修正版.png",
    }
    try:
        text = readme.read_text(encoding="utf-8")
        text_ok = all(
            fragment in text
            for fragment in (
                "论文历史组合版",
                "物理一致修正版",
                "El Centro地震10--11 s与21.5--22.5 s",
                "Chirp响应的13--14 s与38--38.3 s",
            )
        )
    except Exception:
        text_ok = False
    record(
        "readme",
        "F3-15同时保留论文历史错误组合版与物理一致修正版",
        text_ok and figure_names == expected_names,
        expected={"figure_files": sorted(expected_names), "two_versions_documented": True},
        actual={"figure_files": sorted(figure_names), "two_versions_documented": text_ok},
        evidence=readme,
        object_id="F3-15",
    )


def run_tool(executable: str, arguments: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def audit_pdf_and_png() -> None:
    tools = {name: shutil.which(name) for name in ("pdfinfo", "pdffonts", "pdfimages")}
    for name, path in tools.items():
        record(
            "dependency",
            f"{name}可执行文件可用",
            path is not None,
            expected="resolved from PATH",
            actual=path or "MISSING",
            evidence=SCRIPT_PATH,
        )
    record(
        "dependency",
        "Pillow可用于PNG独立像素验收",
        not PIL_IMPORT_ERROR,
        expected="IMPORT_OK",
        actual="IMPORT_OK" if not PIL_IMPORT_ERROR else PIL_IMPORT_ERROR,
        evidence=SCRIPT_PATH,
    )

    pdfs: list[tuple[str, Path]] = STATE.get("pdfs", [])
    for object_id, path in pdfs:
        media_width = math.nan
        media_height = math.nan
        info_actual: Any = "NOT_RUN"
        info_ok = False
        if tools["pdfinfo"]:
            try:
                code, stdout, stderr = run_tool(tools["pdfinfo"] or "", ["-box", str(path)])
                pages_match = re.search(r"^Pages:\s*(\d+)\s*$", stdout, flags=re.MULTILINE)
                size_match = re.search(
                    r"^Page size:\s*([0-9.eE+-]+)\s*x\s*([0-9.eE+-]+)\s*pts",
                    stdout,
                    flags=re.MULTILINE,
                )
                media_match = re.search(
                    r"^MediaBox:\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*$",
                    stdout,
                    flags=re.MULTILINE,
                )
                pages = int(pages_match.group(1)) if pages_match else -1
                page_width = float(size_match.group(1)) if size_match else math.nan
                page_height = float(size_match.group(2)) if size_match else math.nan
                if media_match:
                    x0, y0, x1, y1 = (float(media_match.group(i)) for i in range(1, 5))
                    media_width = x1 - x0
                    media_height = y1 - y0
                info_ok = (
                    code == 0
                    and pages == 1
                    and page_width > 0.0
                    and page_height > 0.0
                    and media_width > 0.0
                    and media_height > 0.0
                )
                info_actual = {
                    "returncode": code,
                    "pages": pages,
                    "page_size_pt": [page_width, page_height],
                    "media_size_pt": [media_width, media_height],
                    "stderr": stderr.strip(),
                }
            except Exception as exc:
                info_actual = f"{type(exc).__name__}: {exc}"
        record(
            "pdf",
            "PDF由pdfinfo确认为单页且页面框为正",
            info_ok,
            expected={"returncode": 0, "pages": 1, "positive_page_and_media_box": True},
            actual=info_actual,
            evidence=path,
            object_id=object_id,
            artifact=path.name,
        )

        font_rows: list[str] = []
        font_actual: Any = "NOT_RUN"
        font_ok = False
        if tools["pdffonts"]:
            try:
                code, stdout, stderr = run_tool(tools["pdffonts"] or "", [str(path)])
                type3 = bool(re.search(r"\bType\s*3\b", stdout, flags=re.IGNORECASE))
                font_rows = [
                    line
                    for line in stdout.splitlines()
                    if line.strip()
                    and not line.lower().lstrip().startswith("name")
                    and not set(line.strip()) <= {"-", " "}
                ]
                font_ok = code == 0 and not type3 and len(font_rows) > 0
                font_actual = {
                    "returncode": code,
                    "type3": type3,
                    "font_rows": len(font_rows),
                    "stderr": stderr.strip(),
                }
            except Exception as exc:
                font_actual = f"{type(exc).__name__}: {exc}"
        record(
            "pdf",
            "PDF由pdffonts确认无Type 3且含可缩放字体对象",
            font_ok,
            expected={"returncode": 0, "type3": False, "font_rows_min": 1},
            actual=font_actual,
            evidence=path,
            object_id=object_id,
            artifact=path.name,
        )

        image_actual: Any = "NOT_RUN"
        vector_ok = False
        if tools["pdfimages"]:
            try:
                code, stdout, stderr = run_tool(tools["pdfimages"] or "", ["-list", str(path)])
                images: list[dict[str, float | int | str]] = []
                for line in stdout.splitlines():
                    parts = line.split()
                    if len(parts) < 14 or not parts[0].isdigit() or not parts[1].isdigit():
                        continue
                    try:
                        width_px = int(parts[3])
                        height_px = int(parts[4])
                        x_ppi = float(parts[12])
                        y_ppi = float(parts[13])
                        width_fraction = (
                            (width_px / x_ppi * 72.0) / media_width
                            if x_ppi > 0.0 and media_width > 0.0
                            else math.nan
                        )
                        height_fraction = (
                            (height_px / y_ppi * 72.0) / media_height
                            if y_ppi > 0.0 and media_height > 0.0
                            else math.nan
                        )
                        images.append(
                            {
                                "type": parts[2],
                                "width_fraction": width_fraction,
                                "height_fraction": height_fraction,
                            }
                        )
                    except (ValueError, IndexError):
                        continue
                covering = [
                    item
                    for item in images
                    if math.isfinite(float(item["width_fraction"]))
                    and math.isfinite(float(item["height_fraction"]))
                    and (
                        (
                            float(item["width_fraction"]) >= 0.80
                            and float(item["height_fraction"]) >= 0.80
                        )
                        or float(item["width_fraction"]) * float(item["height_fraction"]) >= 0.70
                    )
                ]
                vector_ok = code == 0 and not covering and len(font_rows) > 0
                image_actual = {
                    "returncode": code,
                    "embedded_images": len(images),
                    "covering_images": len(covering),
                    "font_rows": len(font_rows),
                    "stderr": stderr.strip(),
                }
            except Exception as exc:
                image_actual = f"{type(exc).__name__}: {exc}"
        record(
            "pdf",
            "PDF由pdfimages与字体证据确认含矢量对象且非整页栅格化",
            vector_ok,
            expected={
                "returncode": 0,
                "covering_images": 0,
                "font_rows_min": 1,
                "covering_rule": "width>=0.80 and height>=0.80, or area>=0.70",
            },
            actual=image_actual,
            evidence=path,
            object_id=object_id,
            artifact=path.name,
        )

    pngs: list[tuple[str, Path]] = STATE.get("pngs", [])
    for object_id, path in pngs:
        ok = False
        actual: Any = "NOT_RUN"
        if Image is not None and ImageChops is not None:
            try:
                with Image.open(path) as image:
                    image.load()
                    dpi_raw = image.info.get("dpi")
                    if isinstance(dpi_raw, (tuple, list)) and len(dpi_raw) >= 2:
                        dpi_x, dpi_y = float(dpi_raw[0]), float(dpi_raw[1])
                    else:
                        dpi_x = dpi_y = math.nan
                    rgb = image.convert("RGB")
                    white = Image.new("RGB", rgb.size, (255, 255, 255))
                    content_bbox = ImageChops.difference(rgb, white).getbbox()
                    extrema = rgb.getextrema()
                    content_dynamic = any(high - low > 5 for low, high in extrema)
                    dpi_ok = (
                        math.isfinite(dpi_x)
                        and math.isfinite(dpi_y)
                        and 599.0 <= dpi_x <= 601.0
                        and 599.0 <= dpi_y <= 601.0
                    )
                    ok = (
                        image.format == "PNG"
                        and image.width > 0
                        and image.height > 0
                        and dpi_ok
                        and content_bbox is not None
                        and content_dynamic
                    )
                    actual = {
                        "format": image.format,
                        "width_px": image.width,
                        "height_px": image.height,
                        "dpi_x": dpi_x,
                        "dpi_y": dpi_y,
                        "content_bbox": content_bbox,
                        "channel_extrema": extrema,
                        "size_bytes": path.stat().st_size,
                    }
            except Exception as exc:
                actual = f"{type(exc).__name__}: {exc}"
        record(
            "png",
            "PNG为600 dpi（pHYs整数量化容差±1 dpi）且像素内容非空",
            ok,
            expected={"format": "PNG", "dpi_range": [599.0, 601.0], "nonblank": True},
            actual=actual if Image is not None else PIL_IMPORT_ERROR,
            evidence=path,
            object_id=object_id,
            artifact=path.name,
        )
    record(
        "figure_counts",
        "最终PDF和PNG验收对象各为12件",
        len(pdfs) == len(pngs) == 12,
        expected={"pdf": 12, "png": 12},
        actual={"pdf": len(pdfs), "png": len(pngs)},
        evidence=PUBLISH_MANIFEST,
    )


def audit_processes() -> None:
    tasklist = shutil.which("tasklist")
    if tasklist is None:
        record(
            "process",
            "无MATLAB/Python/PythonW残留进程",
            False,
            expected="tasklist available and zero residual target processes",
            actual="tasklist MISSING",
            evidence=SCRIPT_PATH,
        )
        return
    try:
        code, stdout, stderr = run_tool(tasklist, ["/FO", "CSV", "/NH"])
        rows = list(csv.reader(stdout.splitlines()))
        current_pid = os.getpid()
        targets = {"matlab.exe", "python.exe", "pythonw.exe"}
        residual: list[dict[str, Any]] = []
        for row in rows:
            if len(row) < 2:
                continue
            image_name = row[0].strip().casefold()
            try:
                pid = int(row[1].replace(",", ""))
            except ValueError:
                continue
            if image_name in targets and pid != current_pid:
                residual.append({"image": row[0], "pid": pid})
        ok = code == 0 and not residual
        actual: Any = {
            "returncode": code,
            "current_validator_pid_excluded": current_pid,
            "residual": residual,
            "stderr": stderr.strip(),
        }
    except Exception as exc:
        ok = False
        actual = f"{type(exc).__name__}: {exc}"
    record(
        "process",
        "无MATLAB/Python/PythonW残留进程（仅排除当前验收器自身Python PID）",
        ok,
        expected={"residual": [], "excluded_pid": os.getpid()},
        actual=actual,
        evidence=SCRIPT_PATH,
    )


def write_outputs() -> tuple[Path, Path]:
    expected_output = (OUTPUTS / "final_validation").resolve()
    resolved_output = FINAL_OUTPUT.resolve()
    if resolved_output != expected_output or resolved_output.parent != OUTPUTS.resolve():
        raise RuntimeError(f"拒绝写入越界验收目录: {resolved_output}")
    FINAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    with DETAIL_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DETAIL_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(DETAIL_ROWS)
    failures = [row for row in DETAIL_ROWS if row["status"] == "FAIL"]
    category_counts: dict[str, dict[str, int]] = {}
    for row in DETAIL_ROWS:
        counts = category_counts.setdefault(row["category"], {"PASS": 0, "FAIL": 0})
        counts[row["status"]] += 1
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "validator": str(SCRIPT_PATH),
        "status": "PASS" if not failures else "FAIL",
        "check_count": len(DETAIL_ROWS),
        "pass_count": len(DETAIL_ROWS) - len(failures),
        "failure_count": len(failures),
        "category_counts": category_counts,
        "required_counts": {
            "success_directories": 11,
            "figure_pairs": 12,
            "pdf": 12,
            "png": 12,
            "index_rows": 45,
            "index_unique_objects": 45,
            "index_target_rows_updated": 11,
            "frozen_inputs": 80,
            "frozen_inputs_unchanged_after_publication": 79,
            "frozen_index_authorized_evolution": 1,
            "protected_sources": 326,
            "board17_artifacts": 305,
            "response_comparisons": 135,
            "independent_matrix_checks": 60,
            "independent_response_checks": 47,
            "manual_visual_reviews": 12,
        },
        "freeze_accounting": STATE.get("freeze_accounting", {}),
        "detail_csv": str(DETAIL_PATH),
        "detail_csv_sha256": sha256(DETAIL_PATH),
        "failed_checks": [
            {
                "sequence": row["sequence"],
                "category": row["category"],
                "check": row["check"],
                "object_id": row["object_id"],
                "artifact": row["artifact"],
                "actual": row["actual"],
            }
            for row in failures
        ],
        "output_boundary": str(FINAL_OUTPUT),
        "mutations_outside_output_boundary": False,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return DETAIL_PATH, SUMMARY_PATH


def main() -> int:
    sections: list[tuple[str, Callable[[], None]]] = [
        ("发布记录", audit_publication_records),
        ("总索引", audit_index),
        ("成功包与SHA清单", audit_packages_and_manifests),
        ("冻结输入与受保护源", audit_freeze_and_protected_sources),
        ("Board17上游工件", audit_board17_integrity),
        ("数值、独立RK4与历史值边界", audit_numeric_and_history_gates),
        ("人工视觉验收", audit_manual_visual_review),
        ("README证据边界", audit_readmes),
        ("PDF/PNG最终图件", audit_pdf_and_png),
        ("残留进程", audit_processes),
    ]
    for name, action in sections:
        run_section(name, action)
    detail_path, summary_path = write_outputs()
    failures = sum(row["status"] == "FAIL" for row in DETAIL_ROWS)
    result = {
        "status": "PASS" if failures == 0 else "FAIL",
        "check_count": len(DETAIL_ROWS),
        "failure_count": failures,
        "detail_csv": str(detail_path),
        "summary_json": str(summary_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
