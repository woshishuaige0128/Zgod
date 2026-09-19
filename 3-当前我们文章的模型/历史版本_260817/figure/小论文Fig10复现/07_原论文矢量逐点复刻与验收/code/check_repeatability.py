#!/usr/bin/env python
"""连续运行两次重建脚本，并比较四个最终图文件的 SHA-256。"""

from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_DIR.parent
REBUILD = SCRIPT_DIR / "rebuild_thesis_vector_trace.py"
FIGURE_DIR = OUTPUT_ROOT / "figures"
REPORT = OUTPUT_ROOT / "validation" / "重复重建哈希检查.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return digest


def run_rebuild() -> None:
    subprocess.run([sys.executable, str(REBUILD)], check=True, capture_output=True, text=True, encoding="utf-8")


def figure_hashes() -> dict[str, str]:
    return {path.name: sha256(path) for path in sorted(FIGURE_DIR.iterdir()) if path.suffix.lower() in {".pdf", ".png"}}


def main() -> int:
    run_rebuild()
    first = figure_hashes()
    run_rebuild()
    second = figure_hashes()
    rows = []
    for name in sorted(first):
        rows.append(
            {
                "file": name,
                "run_1_sha256": first[name],
                "run_2_sha256": second.get(name, "MISSING"),
                "identical": first[name] == second.get(name),
            }
        )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["file", "run_1_sha256", "run_2_sha256", "identical"],
        )
        writer.writeheader()
        writer.writerows(rows)
    passed = len(rows) == 4 and all(row["identical"] for row in rows)
    print(f"repeatability={'PASS' if passed else 'FAIL'}; files={len(rows)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
