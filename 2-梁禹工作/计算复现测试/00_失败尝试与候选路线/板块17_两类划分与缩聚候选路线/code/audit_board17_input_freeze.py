from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_ROOT = SCRIPT_PATH.parents[1]
MANIFEST_PATH = CANDIDATE_ROOT / "input" / "input_manifest.csv"
FREEZE_SUMMARY_PATH = CANDIDATE_ROOT / "input" / "input_freeze_summary.json"
OUTPUT_CSV = CANDIDATE_ROOT / "outputs" / "input_freeze_independent_audit.csv"
OUTPUT_JSON = CANDIDATE_ROOT / "outputs" / "input_freeze_independent_summary.json"
LOG_PATH = CANDIDATE_ROOT / "logs" / "input_freeze_independent_audit.log"

EXPECTED_SOURCE_COUNT = 32
EXPECTED_KEY_HASHES = {
    "reference_model_matlab.mat": (
        "U01_完整模型矩阵",
        "7F9C7C6ACEEDA106304B943F280CCFFF06CBA9137059857A4D89CB06D5B0DAB3",
    ),
    "regenerate_chapter3_data.m": (
        "第三章_当前确定性生成器",
        "CBD7D4BE3927DEC5C18D5C16FBE164528AE6DC022F0B81DB28BD93416F4E7CEE",
    ),
    "manuscript_0824.tex": (
        "小论文公式源",
        "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76",
    ),
    "梁禹手稿.pdf": (
        "硕士论文PDF",
        "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1",
    ),
}

PRELIMINARY_AUDIT_ATTEMPTS = [
    {
        "attempt": 1,
        "result": "审计器失败，不能评价冻结结果",
        "cause": "临时 PowerShell 检查器错误假定 copied_relative_path 列名为 copy_path，且错误假定论文 PDF 文件名。",
    },
    {
        "attempt": 2,
        "result": "64 次哈希重算未发现不一致，但关键角色名检查器失败，不能作为最终验收",
        "cause": "临时 PowerShell 检查器对当前响应生成器和小论文使用了不存在的角色别名。",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path), str(parent)]) == str(parent)
    except ValueError:
        return False


def main() -> int:
    for directory in (OUTPUT_CSV.parent, OUTPUT_JSON.parent, LOG_PATH.parent):
        directory.mkdir(parents=True, exist_ok=True)

    with MANIFEST_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    freeze_summary = json.loads(FREEZE_SUMMARY_PATH.read_text(encoding="utf-8"))

    required_columns = {
        "role",
        "source_path",
        "copied_relative_path",
        "source_size_bytes",
        "copy_size_bytes",
        "source_sha256",
        "copy_sha256",
        "status",
        "action",
    }
    actual_columns = set(rows[0]) if rows else set()
    schema_ok = required_columns.issubset(actual_columns)
    manifest_hash = sha256(MANIFEST_PATH)
    manifest_hash_matches_freeze_summary = (
        manifest_hash == freeze_summary.get("manifest_sha256", "")
    )

    audited_rows: list[dict[str, object]] = []
    problems: list[str] = []
    key_hits: dict[str, list[dict[str, str]]] = {
        filename: [] for filename in EXPECTED_KEY_HASHES
    }

    if not schema_ok:
        problems.append(
            "MANIFEST_SCHEMA_MISSING|" + ",".join(sorted(required_columns - actual_columns))
        )

    for index, row in enumerate(rows, start=1):
        source = Path(row["source_path"]).resolve()
        copied_relative = Path(row["copied_relative_path"])
        copy_path = (CANDIDATE_ROOT / copied_relative).resolve()
        source_exists = source.is_file()
        copy_exists = copy_path.is_file()
        source_outside_candidate = not is_within(source, CANDIDATE_ROOT)
        copy_inside_candidate = is_within(copy_path, CANDIDATE_ROOT)
        source_hash = sha256(source) if source_exists else ""
        copy_hash = sha256(copy_path) if copy_exists else ""
        source_size = source.stat().st_size if source_exists else -1
        copy_size = copy_path.stat().st_size if copy_exists else -1
        row_ok = all(
            [
                source_exists,
                copy_exists,
                source_outside_candidate,
                copy_inside_candidate,
                source_hash == row["source_sha256"],
                copy_hash == row["copy_sha256"],
                source_hash == copy_hash,
                source_size == int(row["source_size_bytes"]),
                copy_size == int(row["copy_size_bytes"]),
                source_size == copy_size,
                row["status"] == "MATCH",
                row["action"] in {"COPIED", "REUSED_IDENTICAL"},
            ]
        )
        if not row_ok:
            problems.append(f"ROW_{index}_FAILED|{source}")

        audit_row: dict[str, object] = {
            "row": index,
            "role": row["role"],
            "source_path": str(source),
            "copied_relative_path": copied_relative.as_posix(),
            "copy_path": str(copy_path),
            "source_exists": source_exists,
            "copy_exists": copy_exists,
            "source_outside_candidate": source_outside_candidate,
            "copy_inside_candidate": copy_inside_candidate,
            "source_size_bytes_rechecked": source_size,
            "copy_size_bytes_rechecked": copy_size,
            "source_sha256_rechecked": source_hash,
            "copy_sha256_rechecked": copy_hash,
            "source_copy_match": source_hash == copy_hash and source_size == copy_size,
            "manifest_fields_match": row_ok,
        }
        audited_rows.append(audit_row)

        filename = source.name
        if filename in key_hits:
            key_hits[filename].append(row)

    key_checks: list[dict[str, object]] = []
    for filename, (expected_role, expected_hash) in EXPECTED_KEY_HASHES.items():
        hits = key_hits[filename]
        unique = len(hits) == 1
        role_matches = unique and hits[0]["role"] == expected_role
        hash_matches = unique and hits[0]["source_sha256"] == expected_hash
        passed = unique and role_matches and hash_matches
        key_checks.append(
            {
                "filename": filename,
                "expected_role": expected_role,
                "match_count": len(hits),
                "role_matches": role_matches,
                "hash_matches": hash_matches,
                "expected_sha256": expected_hash,
                "pass": passed,
            }
        )
        if not passed:
            problems.append(f"KEY_FILE_CHECK_FAILED|{filename}")

    source_count_ok = len(rows) == EXPECTED_SOURCE_COUNT
    all_rows_match = len(audited_rows) == len(rows) and all(
        bool(row["manifest_fields_match"]) for row in audited_rows
    )
    key_hashes_ok = all(bool(item["pass"]) for item in key_checks)
    passed = all(
        [
            schema_ok,
            source_count_ok,
            manifest_hash_matches_freeze_summary,
            all_rows_match,
            key_hashes_ok,
            not problems,
        ]
    )

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(CANDIDATE_ROOT),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256_rechecked": manifest_hash,
        "manifest_hash_matches_freeze_summary": manifest_hash_matches_freeze_summary,
        "expected_source_count": EXPECTED_SOURCE_COUNT,
        "source_count": len(rows),
        "source_count_ok": source_count_ok,
        "rehashed_file_count": 2 * len(rows),
        "schema_ok": schema_ok,
        "all_rows_match": all_rows_match,
        "key_hashes_ok": key_hashes_ok,
        "key_checks": key_checks,
        "problem_count": len(problems),
        "problems": problems,
        "preliminary_audit_attempts": PRELIMINARY_AUDIT_ATTEMPTS,
        "pass": passed,
    }

    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audited_rows[0]))
        writer.writeheader()
        writer.writerows(audited_rows)
    OUTPUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    log_lines = [
        "板块17输入冻结独立复核",
        f"生成时间(UTC): {summary['generated_at_utc']}",
        f"冻结输入数: {len(rows)}/{EXPECTED_SOURCE_COUNT}",
        f"独立重算哈希文件数: {2 * len(rows)}",
        f"清单哈希: {manifest_hash}",
        f"逐项源/副本/尺寸/边界/状态一致: {all_rows_match}",
        f"4个关键文件固定哈希一致: {key_hashes_ok}",
        f"问题数: {len(problems)}",
        f"最终结论: {'PASS' if passed else 'FAIL'}",
        "",
        "前置检查器失败记录（不作为冻结结果失败）：",
    ]
    for item in PRELIMINARY_AUDIT_ATTEMPTS:
        log_lines.append(
            f"- 第{item['attempt']}次：{item['result']}；原因：{item['cause']}"
        )
    if problems:
        log_lines.extend(["", "实际问题：", *[f"- {item}" for item in problems]])
    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
