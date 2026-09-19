from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = BOARD_ROOT.parents[2]
INPUT_ROOT = BOARD_ROOT / "input"
MANIFEST_PATH = INPUT_ROOT / "input_manifest.csv"
OUTPUT_CSV = BOARD_ROOT / "outputs" / "input_freeze_validation.csv"
OUTPUT_JSON = BOARD_ROOT / "outputs" / "input_freeze_validation.json"

EXPECTED_MANIFEST_ROW_COUNT = 185
EXPECTED_BOARD15_PROTECTED_COUNT = 326

REQUIRED_MANIFEST_COLUMNS = {
    "item_id",
    "category",
    "role",
    "source_absolute_path",
    "source_relative_label",
    "frozen_relative_path",
    "source_size_bytes",
    "source_mtime_iso",
    "source_sha256",
    "frozen_size_bytes",
    "frozen_sha256",
    "live_change_policy",
    "status",
}

MAIN_LQR_MLX_NAMES = (
    "luxvjie_ori_LQR2.mlx",
    "luxvjie_ori_LQR3.mlx",
    "luxvjie_guyan_LQR2.mlx",
    "luxvjie_guyan_LQR3.mlx",
    "luxvjie_cb_LQR2.mlx",
    "luxvjie_cb_LQR3.mlx",
)

PAPER_BASELINE_HASHES = {
    "梁禹硕士论文": "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1",
    "小论文公式源": "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76",
}

UPSTREAM_PROTECTION_HASHES = {
    "board16保护基线:board16_artifact_manifest.csv": (
        "F18B2A4E18D27D21581AE05F88D380B12663E5EDE4368E03FF179D89A09C4A93"
    ),
    "板块17上游:report/board17_artifact_manifest.csv": (
        "43C29665D0E08EF4FFB8D9067B38F797797735EA382E7F5B004EA2637A787405"
    ),
    "板块17上游:report/board17_final_validation_summary.json": (
        "AE580B5A25F89F68E257DADB0F243962F634248C035864EBC8F681C083AEBF4A"
    ),
    "board18保护基线:board18_final_validation_summary.json": (
        "236D5AC6BCB9FD9EBCC60F5D6FF4FDB1C87B788E445C7CF3AB733F20BAACD934"
    ),
    "board19保护基线:board19_final_validation_summary.json": (
        "9F3F11CAD44430F94F47420F25BB1E3585AF60BF107F5E451D79677BF735F6E6"
    ),
}

EXPECTED_ABSENT_SUCCESS_DIRECTORIES = (
    PROJECT_ROOT / "test" / "图4-4_第一类子结构划分稳定域",
    PROJECT_ROOT / "test" / "图4-5_第二类子结构划分稳定域",
    PROJECT_ROOT / "test" / "结论C05_两类划分的稳定裕度下降量",
    PROJECT_ROOT / "test" / "结论C07_结论章频率区间、误差幅值与临界时滞总结",
)

BOARD15_REQUIRED_COLUMNS = {
    "类别",
    "绝对路径",
    "相对基准",
    "相对路径",
    "文件大小_字节",
    "修改时间",
    "SHA256",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_within(path: Path, parent: Path) -> bool:
    try:
        child_text = os.path.normcase(str(path.resolve()))
        parent_text = os.path.normcase(str(parent.resolve()))
        return os.path.commonpath([child_text, parent_text]) == parent_text
    except (OSError, ValueError):
        return False


def as_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalized_path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def add_check(
    checks: list[dict[str, str]],
    *,
    check_id: str,
    scope: str,
    item_id: str,
    check: str,
    expected: Any,
    actual: Any,
    passed: bool,
    detail: str = "",
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "scope": scope,
            "item_id": item_id,
            "check": check,
            "expected": str(expected),
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def load_csv(path: Path) -> tuple[list[dict[str, str]], set[str], str]:
    if not path.is_file():
        return [], set(), f"文件不存在: {path}"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = set(reader.fieldnames or [])
        return rows, columns, ""
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], set(), f"{type(exc).__name__}: {exc}"


def validate_manifest_rows(
    rows: list[dict[str, str]], checks: list[dict[str, str]]
) -> tuple[int, int]:
    item_ids = [row.get("item_id", "") for row in rows]
    item_id_counts = Counter(item_ids)
    duplicate_item_ids = sorted(
        item_id for item_id, count in item_id_counts.items() if not item_id or count != 1
    )
    add_check(
        checks,
        check_id="manifest_item_ids_unique",
        scope="manifest",
        item_id="",
        check="item_id非空且唯一",
        expected=f"{EXPECTED_MANIFEST_ROW_COUNT}个非空唯一item_id",
        actual=f"唯一数={len(set(item_ids))}; 异常={duplicate_item_ids}",
        passed=not duplicate_item_ids and len(item_ids) == len(set(item_ids)),
    )

    frozen_paths: list[str] = []
    for row in rows:
        relative = Path(row.get("frozen_relative_path", ""))
        frozen_paths.append(normalized_path_key(INPUT_ROOT / relative))
    frozen_counts = Counter(frozen_paths)
    duplicate_destinations = sorted(
        path for path, count in frozen_counts.items() if count != 1
    )
    add_check(
        checks,
        check_id="manifest_frozen_destinations_unique",
        scope="manifest",
        item_id="",
        check="冻结目的路径唯一",
        expected="每个frozen_relative_path唯一",
        actual=f"唯一数={len(set(frozen_paths))}; 重复数={len(duplicate_destinations)}",
        passed=not duplicate_destinations and len(frozen_paths) == len(set(frozen_paths)),
        detail=" | ".join(duplicate_destinations[:10]),
    )

    passed_rows = 0
    for row_number, row in enumerate(rows, start=1):
        item_id = row.get("item_id", f"ROW-{row_number:04d}")
        source_text = row.get("source_absolute_path", "")
        frozen_relative_text = row.get("frozen_relative_path", "")
        source = Path(source_text).resolve() if source_text else Path("")
        frozen_relative = Path(frozen_relative_text)
        frozen = (INPUT_ROOT / frozen_relative).resolve()

        source_exists = bool(source_text) and source.is_file()
        frozen_exists = bool(frozen_relative_text) and frozen.is_file()
        source_size = source.stat().st_size if source_exists else -1
        frozen_size = frozen.stat().st_size if frozen_exists else -1
        source_hash = sha256(source) if source_exists else ""
        frozen_hash = sha256(frozen) if frozen_exists else ""
        manifest_source_size = as_int(row.get("source_size_bytes", ""))
        manifest_frozen_size = as_int(row.get("frozen_size_bytes", ""))
        manifest_source_hash = row.get("source_sha256", "").upper()
        manifest_frozen_hash = row.get("frozen_sha256", "").upper()
        live_change_policy = row.get("live_change_policy", "")
        immutable_source = live_change_policy == "immutable"
        policy_valid = live_change_policy in {"immutable", "authorized_evolution"}

        conditions = {
            "source_exists": source_exists,
            "frozen_exists": frozen_exists,
            "source_outside_board": source_exists and not is_within(source, BOARD_ROOT),
            "frozen_relative_not_absolute": not frozen_relative.is_absolute(),
            "frozen_inside_input": frozen_exists and is_within(frozen, INPUT_ROOT),
            "frozen_inside_board": frozen_exists and is_within(frozen, BOARD_ROOT),
            "source_size_matches_manifest_or_authorized": (
                source_size == manifest_source_size or not immutable_source
            ),
            "frozen_size_matches_manifest": frozen_size == manifest_frozen_size,
            "source_frozen_size_match_or_authorized": (
                (source_size == frozen_size and source_size >= 0) or not immutable_source
            ),
            "source_hash_matches_manifest_or_authorized": (
                source_hash == manifest_source_hash or not immutable_source
            ),
            "frozen_hash_matches_manifest": frozen_hash == manifest_frozen_hash,
            "source_frozen_hash_match_or_authorized": (
                (bool(source_hash) and source_hash == frozen_hash) or not immutable_source
            ),
            "status_match": row.get("status") == "MATCH",
            "live_change_policy_valid": policy_valid,
            "role_nonempty": bool(row.get("role", "").strip()),
        }
        failed_conditions = [name for name, ok in conditions.items() if not ok]
        row_passed = not failed_conditions
        passed_rows += int(row_passed)
        add_check(
            checks,
            check_id=f"manifest_row_{row_number:04d}",
            scope="manifest_row",
            item_id=item_id,
            check="源/冻结副本存在、路径边界、大小、SHA-256与状态一致",
            expected="全14项子条件成立",
            actual=f"成立={len(conditions) - len(failed_conditions)}/{len(conditions)}",
            passed=row_passed,
            detail=(
                f"failed={','.join(failed_conditions)}; source={source}; frozen={frozen}"
                if failed_conditions
                else f"source={source}; frozen={frozen}"
            ),
        )

    return passed_rows, len(rows)


def validate_main_mlx_pairs(
    rows: list[dict[str, str]], checks: list[dict[str, str]]
) -> int:
    passed_pairs = 0
    for index, filename in enumerate(MAIN_LQR_MLX_NAMES, start=1):
        main_rows = [
            row
            for row in rows
            if row.get("category") == "historical_stability_route"
            and Path(row.get("source_absolute_path", "")).name == filename
        ]
        outer_rows = [
            row
            for row in rows
            if row.get("category") == "plotting_baseline"
            and Path(row.get("source_absolute_path", "")).name == filename
            and "原始来源副本" in row.get("frozen_relative_path", "")
        ]

        pair_passed = False
        detail_parts = [f"main_count={len(main_rows)}", f"outer_count={len(outer_rows)}"]
        actual_hashes: list[str] = []
        if len(main_rows) == 1 and len(outer_rows) == 1:
            main_row = main_rows[0]
            outer_row = outer_rows[0]
            paths = (
                Path(main_row["source_absolute_path"]),
                INPUT_ROOT / main_row["frozen_relative_path"],
                Path(outer_row["source_absolute_path"]),
                INPUT_ROOT / outer_row["frozen_relative_path"],
            )
            all_exist = all(path.is_file() for path in paths)
            actual_hashes = [sha256(path) for path in paths] if all_exist else []
            pair_passed = all_exist and len(set(actual_hashes)) == 1
            detail_parts.extend(f"path{number}={path}" for number, path in enumerate(paths, 1))
        passed_pairs += int(pair_passed)
        add_check(
            checks,
            check_id=f"main_mlx_pair_{index:02d}",
            scope="main_mlx_pair",
            item_id=filename,
            check="稳定域目录主MLX与外层绘图包副本逐对SHA-256一致",
            expected="两类来源各1行，4个实体文件SHA-256全相同",
            actual=(actual_hashes[0] if pair_passed else json.dumps(actual_hashes)),
            passed=pair_passed,
            detail="; ".join(detail_parts),
        )
    return passed_pairs


def validate_fixed_role_hashes(
    rows: list[dict[str, str]],
    expected: dict[str, str],
    checks: list[dict[str, str]],
    *,
    scope: str,
    prefix: str,
) -> int:
    passed_count = 0
    for index, (role, expected_hash) in enumerate(expected.items(), start=1):
        hits = [row for row in rows if row.get("role") == role]
        passed = False
        actual_hashes: list[str] = []
        if len(hits) == 1:
            row = hits[0]
            source = Path(row["source_absolute_path"])
            frozen = INPUT_ROOT / row["frozen_relative_path"]
            if source.is_file() and frozen.is_file():
                actual_hashes = [sha256(source), sha256(frozen)]
                passed = (
                    actual_hashes == [expected_hash, expected_hash]
                    and row.get("source_sha256", "").upper() == expected_hash
                    and row.get("frozen_sha256", "").upper() == expected_hash
                )
        passed_count += int(passed)
        add_check(
            checks,
            check_id=f"{prefix}_{index:02d}",
            scope=scope,
            item_id=(hits[0].get("item_id", "") if len(hits) == 1 else ""),
            check=f"唯一角色固定哈希: {role}",
            expected=expected_hash,
            actual=json.dumps(actual_hashes),
            passed=passed,
            detail=f"match_count={len(hits)}",
        )
    return passed_count


def validate_board15_live_protection(
    rows: list[dict[str, str]], checks: list[dict[str, str]]
) -> tuple[int, int]:
    hits = [row for row in rows if row.get("role") == "板块15源文件冻结清单"]
    list_path = Path(hits[0]["source_absolute_path"]) if len(hits) == 1 else Path("")
    protected_rows, columns, error = load_csv(list_path)
    schema_ok = BOARD15_REQUIRED_COLUMNS.issubset(columns)
    add_check(
        checks,
        check_id="board15_manifest_contract",
        scope="board15_protection",
        item_id=(hits[0].get("item_id", "") if len(hits) == 1 else ""),
        check="板块15保护清单唯一、存在、列合同和行数",
        expected=f"1个角色，{EXPECTED_BOARD15_PROTECTED_COUNT}行，必需7列",
        actual=(
            f"role_hits={len(hits)}; rows={len(protected_rows)}; "
            f"missing_columns={sorted(BOARD15_REQUIRED_COLUMNS - columns)}; error={error}"
        ),
        passed=(
            len(hits) == 1
            and not error
            and schema_ok
            and len(protected_rows) == EXPECTED_BOARD15_PROTECTED_COUNT
        ),
    )

    if not schema_ok:
        return 0, len(protected_rows)

    passed_count = 0
    for row_number, row in enumerate(protected_rows, start=1):
        source = Path(row.get("绝对路径", ""))
        exists = source.is_file()
        actual_size = source.stat().st_size if exists else -1
        actual_hash = sha256(source) if exists else ""
        expected_size = as_int(row.get("文件大小_字节", ""))
        expected_hash = row.get("SHA256", "").upper()
        passed = (
            exists
            and actual_size == expected_size
            and actual_hash == expected_hash
            and not is_within(source, BOARD_ROOT)
        )
        passed_count += int(passed)
        add_check(
            checks,
            check_id=f"board15_live_{row_number:04d}",
            scope="board15_protected_source",
            item_id=f"B15-{row_number:04d}",
            check="板块15保护源实时大小/SHA-256一致且不在板块20目录",
            expected=f"size={expected_size}; sha256={expected_hash}",
            actual=f"exists={exists}; size={actual_size}; sha256={actual_hash}",
            passed=passed,
            detail=str(source),
        )
    return passed_count, len(protected_rows)


def validate_success_directories_absent(checks: list[dict[str, str]]) -> int:
    passed_count = 0
    for index, directory in enumerate(EXPECTED_ABSENT_SUCCESS_DIRECTORIES, start=1):
        absent = not directory.exists()
        passed_count += int(absent)
        add_check(
            checks,
            check_id=f"success_directory_absent_{index:02d}",
            scope="publication_gate",
            item_id=directory.name,
            check="计算复现通过前预定成功目录不存在",
            expected="ABSENT",
            actual="ABSENT" if absent else "EXISTS",
            passed=absent,
            detail=str(directory),
        )
    return passed_count


def write_outputs(checks: list[dict[str, str]], summary: dict[str, Any]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "check_id",
                "scope",
                "item_id",
                "check",
                "expected",
                "actual",
                "status",
                "detail",
            ],
        )
        writer.writeheader()
        writer.writerows(checks)
    OUTPUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    checks: list[dict[str, str]] = []
    rows, columns, manifest_error = load_csv(MANIFEST_PATH)
    schema_ok = REQUIRED_MANIFEST_COLUMNS.issubset(columns)

    add_check(
        checks,
        check_id="manifest_exists_and_schema",
        scope="manifest",
        item_id="",
        check="input_manifest.csv存在且列合同完整",
        expected=f"必需{len(REQUIRED_MANIFEST_COLUMNS)}列",
        actual=(
            f"exists={MANIFEST_PATH.is_file()}; rows={len(rows)}; "
            f"missing={sorted(REQUIRED_MANIFEST_COLUMNS - columns)}; error={manifest_error}"
        ),
        passed=MANIFEST_PATH.is_file() and not manifest_error and schema_ok,
    )
    add_check(
        checks,
        check_id="manifest_row_count",
        scope="manifest",
        item_id="",
        check="冻结清单行数",
        expected=EXPECTED_MANIFEST_ROW_COUNT,
        actual=len(rows),
        passed=len(rows) == EXPECTED_MANIFEST_ROW_COUNT,
    )

    manifest_rows_passed = 0
    manifest_rows_checked = 0
    main_mlx_pairs_passed = 0
    paper_hashes_passed = 0
    upstream_hashes_passed = 0
    board15_passed = 0
    board15_checked = 0
    success_directories_absent = 0

    if schema_ok:
        manifest_rows_passed, manifest_rows_checked = validate_manifest_rows(rows, checks)
        main_mlx_pairs_passed = validate_main_mlx_pairs(rows, checks)
        paper_hashes_passed = validate_fixed_role_hashes(
            rows,
            PAPER_BASELINE_HASHES,
            checks,
            scope="paper_baseline",
            prefix="paper_baseline",
        )
        upstream_hashes_passed = validate_fixed_role_hashes(
            rows,
            UPSTREAM_PROTECTION_HASHES,
            checks,
            scope="upstream_protection",
            prefix="upstream_protection",
        )
        board15_passed, board15_checked = validate_board15_live_protection(rows, checks)
    else:
        add_check(
            checks,
            check_id="dependent_checks_skipped",
            scope="fatal",
            item_id="",
            check="依赖清单列合同的检查不得跳过",
            expected="列合同完整后执行",
            actual="列合同不完整，无法执行",
            passed=False,
        )

    success_directories_absent = validate_success_directories_absent(checks)

    failed_checks = [check for check in checks if check["status"] == "FAIL"]
    passed = not failed_checks
    manifest_hash = sha256(MANIFEST_PATH) if MANIFEST_PATH.is_file() else ""
    summary: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "board_root": str(BOARD_ROOT),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": manifest_hash,
        "expected_manifest_rows": EXPECTED_MANIFEST_ROW_COUNT,
        "manifest_rows": len(rows),
        "manifest_rows_passed": manifest_rows_passed,
        "manifest_rows_checked": manifest_rows_checked,
        "main_mlx_pairs_passed": main_mlx_pairs_passed,
        "main_mlx_pairs_expected": len(MAIN_LQR_MLX_NAMES),
        "paper_baseline_hashes_passed": paper_hashes_passed,
        "paper_baseline_hashes_expected": len(PAPER_BASELINE_HASHES),
        "upstream_protection_hashes_passed": upstream_hashes_passed,
        "upstream_protection_hashes_expected": len(UPSTREAM_PROTECTION_HASHES),
        "board15_live_protected_passed": board15_passed,
        "board15_live_protected_checked": board15_checked,
        "board15_live_protected_expected": EXPECTED_BOARD15_PROTECTED_COUNT,
        "success_directories_absent": success_directories_absent,
        "success_directories_expected_absent": len(EXPECTED_ABSENT_SUCCESS_DIRECTORIES),
        "total_checks": len(checks),
        "passed_checks": len(checks) - len(failed_checks),
        "failed_checks": len(failed_checks),
        "failures": [
            {
                "check_id": check["check_id"],
                "scope": check["scope"],
                "item_id": check["item_id"],
                "detail": check["detail"],
            }
            for check in failed_checks
        ],
        "output_csv": str(OUTPUT_CSV),
        "output_json": str(OUTPUT_JSON),
        "pass": passed,
    }
    write_outputs(checks, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
