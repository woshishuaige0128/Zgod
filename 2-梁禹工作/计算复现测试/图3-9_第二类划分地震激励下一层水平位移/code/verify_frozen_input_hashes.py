#!/usr/bin/env python3
"""独立复算板块18冻结输入的源文件、副本尺寸与SHA-256。"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


BOARD_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
DETAIL = BOARD_ROOT / "outputs" / "independent_input_hash_recheck.csv"
SUMMARY = BOARD_ROOT / "outputs" / "independent_input_hash_recheck_summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> int:
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    checks: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        source = Path(row["source_path"])
        copy = BOARD_ROOT.joinpath(*Path(row["copied_relative_path"]).parts)
        source_exists = source.is_file()
        copy_exists = copy.is_file()
        source_size = source.stat().st_size if source_exists else -1
        copy_size = copy.stat().st_size if copy_exists else -1
        source_hash = sha256(source) if source_exists else ""
        copy_hash = sha256(copy) if copy_exists else ""
        expected_source_hash = row["source_sha256_after"].upper()
        expected_copy_hash = row["copy_sha256"].upper()
        passed = all(
            [
                source_exists,
                copy_exists,
                source_size == int(row["source_size_bytes"]),
                copy_size == int(row["copy_size_bytes"]),
                source_hash == expected_source_hash,
                copy_hash == expected_copy_hash,
                source_hash == copy_hash,
            ]
        )
        checks.append(
            {
                "row": index,
                "role": row["role"],
                "source_path": str(source),
                "copy_path": str(copy),
                "source_exists": source_exists,
                "copy_exists": copy_exists,
                "expected_source_size_bytes": row["source_size_bytes"],
                "actual_source_size_bytes": source_size,
                "expected_copy_size_bytes": row["copy_size_bytes"],
                "actual_copy_size_bytes": copy_size,
                "expected_source_sha256": expected_source_hash,
                "actual_source_sha256": source_hash,
                "expected_copy_sha256": expected_copy_hash,
                "actual_copy_sha256": copy_hash,
                "source_copy_same_sha256": source_hash == copy_hash and bool(source_hash),
                "status": "PASS" if passed else "FAIL",
            }
        )

    fields = list(checks[0]) if checks else []
    with DETAIL.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(checks)

    generator_rows = [
        row for row in checks if row["role"] == "2026现存响应生成器（非作者历史原件）"
    ]
    pass_count = sum(row["status"] == "PASS" for row in checks)
    overall = len(checks) == 80 and pass_count == 80 and len(generator_rows) == 1
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest": str(MANIFEST),
        "manifest_sha256": sha256(MANIFEST),
        "row_count": len(checks),
        "pass_count": pass_count,
        "fail_count": len(checks) - pass_count,
        "generator_frozen_count": len(generator_rows),
        "generator_status": generator_rows[0]["status"] if len(generator_rows) == 1 else "FAIL",
        "overall_status": "PASS" if overall else "FAIL",
        "simulation_run": False,
        "source_assets_modified": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if overall else 2


if __name__ == "__main__":
    raise SystemExit(main())
