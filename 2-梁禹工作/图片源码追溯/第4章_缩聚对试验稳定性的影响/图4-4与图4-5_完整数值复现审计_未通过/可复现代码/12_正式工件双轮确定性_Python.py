from __future__ import annotations

"""
步骤 8F 正式工件的双轮逐字节确定性检查。

检查流程：
1. 对构建器当前正式拥有的 79 个工件建立第一轮 SHA-256 快照；
2. 调用 build_board20_step8f_adjudication.py --render 完整重建一次；
3. 对同一相对路径集合重新计算 SHA-256，要求集合与内容逐字节一致。

正式 79 件的固定结构为：
- 70 个数据/裁决文件；
- 1 个绘图工件哈希清单；
- 4 个矢量 PDF；
- 4 个 600 dpi PNG。

validation、visual_qa 和 repeatability 目录不属于构建器正式工件，
始终从两轮集合中排除。
"""

import csv
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
BUILDER = SCRIPT.parent / "build_board20_step8f_adjudication.py"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step8f_计算候选与论文目标裁决"
REPEATABILITY_ROOT = OUTPUT_ROOT / "repeatability"
COMPARISON_CSV = REPEATABILITY_ROOT / "步骤8F正式工件双轮逐文件比较.csv"
SUMMARY_JSON = REPEATABILITY_ROOT / "步骤8F正式工件双轮确定性摘要.json"

EXCLUDED_TOP_LEVEL_DIRECTORIES = {"validation", "visual_qa", "repeatability"}
EXPECTED_TOTAL = 79
EXPECTED_DATA_AND_ADJUDICATION = 70
EXPECTED_PLOT_MANIFEST = 1
EXPECTED_PDF = 4
EXPECTED_PNG = 4
PLOT_MANIFEST_RELATIVE_PATH = Path("裁决证据") / "绘图工件哈希清单.csv"


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    size_bytes: int
    sha256: str
    category: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def classify(relative_path: Path) -> str:
    normalized = relative_path.as_posix()
    if normalized == PLOT_MANIFEST_RELATIVE_PATH.as_posix():
        return "plot_hash_manifest"
    if relative_path.parts and relative_path.parts[0].casefold() == "figures":
        suffix = relative_path.suffix.casefold()
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".png":
            return "png"
        return "unexpected_figure_file"
    return "data_or_adjudication"


def collect_owned_files() -> dict[str, FileRecord]:
    if not OUTPUT_ROOT.is_dir():
        raise FileNotFoundError(f"步骤8F输出根目录不存在：{OUTPUT_ROOT}")
    records: dict[str, FileRecord] = {}
    for path in sorted(OUTPUT_ROOT.rglob("*"), key=lambda value: value.as_posix().casefold()):
        if not path.is_file():
            continue
        relative = path.relative_to(OUTPUT_ROOT)
        if relative.parts and relative.parts[0].casefold() in EXCLUDED_TOP_LEVEL_DIRECTORIES:
            continue
        relative_text = relative.as_posix()
        if relative_text in records:
            raise RuntimeError(f"重复相对路径：{relative_text}")
        records[relative_text] = FileRecord(
            relative_path=relative_text,
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
            category=classify(relative),
        )
    return records


def category_counts(records: dict[str, FileRecord]) -> dict[str, int]:
    result = {
        "data_or_adjudication": 0,
        "plot_hash_manifest": 0,
        "pdf": 0,
        "png": 0,
        "unexpected_figure_file": 0,
    }
    for record in records.values():
        result[record.category] = result.get(record.category, 0) + 1
    return result


def structure_checks(records: dict[str, FileRecord]) -> dict[str, Any]:
    counts = category_counts(records)
    checks = {
        "total_file_count_exact": len(records) == EXPECTED_TOTAL,
        "data_or_adjudication_count_exact": (
            counts["data_or_adjudication"] == EXPECTED_DATA_AND_ADJUDICATION
        ),
        "plot_hash_manifest_count_exact": (
            counts["plot_hash_manifest"] == EXPECTED_PLOT_MANIFEST
        ),
        "pdf_count_exact": counts["pdf"] == EXPECTED_PDF,
        "png_count_exact": counts["png"] == EXPECTED_PNG,
        "unexpected_figure_file_count_zero": counts["unexpected_figure_file"] == 0,
    }
    return {
        "expected": {
            "total": EXPECTED_TOTAL,
            "data_or_adjudication": EXPECTED_DATA_AND_ADJUDICATION,
            "plot_hash_manifest": EXPECTED_PLOT_MANIFEST,
            "pdf": EXPECTED_PDF,
            "png": EXPECTED_PNG,
            "unexpected_figure_file": 0,
        },
        "actual": {"total": len(records), **counts},
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_builder() -> subprocess.CompletedProcess[str]:
    if not BUILDER.is_file():
        raise FileNotFoundError(f"构建器不存在：{BUILDER}")
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["SOURCE_DATE_EPOCH"] = "946684800"
    return subprocess.run(
        [sys.executable, str(BUILDER), "--render"],
        cwd=str(BOARD_ROOT),
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def compare_rounds(
    before: dict[str, FileRecord], after: dict[str, FileRecord]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    paths = sorted(set(before) | set(after), key=str.casefold)
    rows: list[dict[str, Any]] = []
    counts = {
        "identical": 0,
        "added_after": 0,
        "missing_after": 0,
        "sha256_mismatch": 0,
        "size_mismatch": 0,
        "category_mismatch": 0,
        "difference": 0,
    }
    for relative_path in paths:
        first = before.get(relative_path)
        second = after.get(relative_path)
        if first is None:
            status = "ADDED_AFTER"
            counts["added_after"] += 1
        elif second is None:
            status = "MISSING_AFTER"
            counts["missing_after"] += 1
        elif first.category != second.category:
            status = "CATEGORY_MISMATCH"
            counts["category_mismatch"] += 1
        elif first.size_bytes != second.size_bytes:
            status = "SIZE_MISMATCH"
            counts["size_mismatch"] += 1
        elif first.sha256 != second.sha256:
            status = "SHA256_MISMATCH"
            counts["sha256_mismatch"] += 1
        else:
            status = "IDENTICAL"
            counts["identical"] += 1
        if status != "IDENTICAL":
            counts["difference"] += 1
        rows.append(
            {
                "relative_path": relative_path,
                "category_before": first.category if first else "",
                "category_after": second.category if second else "",
                "size_bytes_before": first.size_bytes if first else "",
                "size_bytes_after": second.size_bytes if second else "",
                "sha256_before": first.sha256 if first else "",
                "sha256_after": second.sha256 if second else "",
                "path_present_before": first is not None,
                "path_present_after": second is not None,
                "size_exact": (
                    first is not None
                    and second is not None
                    and first.size_bytes == second.size_bytes
                ),
                "sha256_exact": (
                    first is not None
                    and second is not None
                    and first.sha256 == second.sha256
                ),
                "status": status,
            }
        )
    return rows, counts


def write_comparison(rows: list[dict[str, Any]]) -> None:
    REPEATABILITY_ROOT.mkdir(parents=True, exist_ok=True)
    fieldnames = tuple(rows[0].keys()) if rows else (
        "relative_path",
        "category_before",
        "category_after",
        "size_bytes_before",
        "size_bytes_after",
        "sha256_before",
        "sha256_after",
        "path_present_before",
        "path_present_after",
        "size_exact",
        "sha256_exact",
        "status",
    )
    with COMPARISON_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(payload: dict[str, Any]) -> None:
    REPEATABILITY_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    before = collect_owned_files()
    before_structure = structure_checks(before)

    completed = run_builder()
    after = collect_owned_files()
    after_structure = structure_checks(after)
    comparison_rows, difference_counts = compare_rounds(before, after)
    write_comparison(comparison_rows)

    path_set_exact = set(before) == set(after)
    all_sha256_exact = (
        path_set_exact
        and difference_counts["difference"] == 0
        and difference_counts["identical"] == EXPECTED_TOTAL
    )
    passed = (
        completed.returncode == 0
        and before_structure["passed"]
        and after_structure["passed"]
        and path_set_exact
        and all_sha256_exact
    )
    summary = {
        "step": "8F",
        "purpose": "FORMAL_ARTIFACT_BYTE_REPEATABILITY",
        "overall_gate": (
            "PASS_79_OF_79_BYTE_IDENTICAL"
            if passed
            else "FAIL_FORMAL_ARTIFACT_REPEATABILITY"
        ),
        "passed": passed,
        "excluded_top_level_directories": sorted(EXCLUDED_TOP_LEVEL_DIRECTORIES),
        "first_round_structure": before_structure,
        "second_round_structure": after_structure,
        "first_round_file_count": len(before),
        "second_round_file_count": len(after),
        "path_set_exact": path_set_exact,
        "sha256_identical_file_count": difference_counts["identical"],
        "difference_file_count": difference_counts["difference"],
        "difference_counts": difference_counts,
        "builder_command": [sys.executable, str(BUILDER), "--render"],
        "builder_returncode": completed.returncode,
        "builder_output": completed.stdout.strip(),
        "builder_sha256": sha256_file(BUILDER),
        "repeatability_script_sha256": sha256_file(SCRIPT),
        "comparison_csv": COMPARISON_CSV.relative_to(BOARD_ROOT).as_posix(),
        "summary_json": SUMMARY_JSON.relative_to(BOARD_ROOT).as_posix(),
    }
    write_summary(summary)
    print(
        f"{summary['overall_gate']}: first={len(before)}, second={len(after)}, "
        f"identical={difference_counts['identical']}, differences={difference_counts['difference']}"
    )
    if completed.stdout.strip():
        print(completed.stdout.strip())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
