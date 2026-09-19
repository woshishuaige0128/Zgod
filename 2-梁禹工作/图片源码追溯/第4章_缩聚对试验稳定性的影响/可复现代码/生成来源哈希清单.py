from __future__ import annotations

import csv
import hashlib
from pathlib import Path


代码目录 = Path(__file__).resolve().parent
来源目录 = 代码目录.parent / "原始来源副本"
输出文件 = 来源目录 / "SHA256清单.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def 主程序() -> None:
    rows = []
    for path in sorted(来源目录.iterdir(), key=lambda p: p.name):
        if not path.is_file() or path == 输出文件:
            continue
        rows.append(
            {
                "文件名": path.name,
                "字节数": path.stat().st_size,
                "SHA256": sha256(path),
            }
        )
    with 输出文件.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["文件名", "字节数", "SHA256"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成: {输出文件}")


if __name__ == "__main__":
    主程序()
