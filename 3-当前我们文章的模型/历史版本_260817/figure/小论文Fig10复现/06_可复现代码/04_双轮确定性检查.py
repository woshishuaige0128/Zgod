#!/usr/bin/env python
"""连续运行两次Fig10生成器并比较正式输出的SHA-256。"""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve().parent / "02_生成小论文Fig10.py"
VALIDATION_DIR = ROOT / "08_总验收与论文映射"
FILES = (
    ROOT / "01_论文矢量边界主数据" / "Fig10_六条论文边界_采样步与毫秒.csv",
    ROOT / "02_小论文Fig10最终图" / "PDF" / "fig10_stability_domain.pdf",
    ROOT / "02_小论文Fig10最终图" / "PNG" / "fig10_stability_domain.png",
    VALIDATION_DIR / "Fig10生成元数据.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def run_once(index: int) -> dict[Path, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    (VALIDATION_DIR / f"重建运行日志_第{index}轮.txt").write_text(
        result.stdout + ("\n[stderr]\n" + result.stderr if result.stderr else ""),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"第{index}轮生成失败，退出码{result.returncode}。")
    return {path: sha256(path) for path in FILES}


def main() -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    first = run_once(1)
    second = run_once(2)
    rows = []
    for path in FILES:
        same = first[path] == second[path]
        rows.append(
            {
                "file": str(path.relative_to(ROOT)),
                "round1_sha256": first[path],
                "round2_sha256": second[path],
                "status": "PASS" if same else "FAIL",
            }
        )
    destination = VALIDATION_DIR / "重复重建哈希检查.csv"
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['status']} {row['file']} {row['round2_sha256']}")
    return 0 if all(row["status"] == "PASS" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
