"""生成并立即复算全部28个PDF与28个PNG的统一SHA-256清单。"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
图片根 = 工作区 / "figure"
输出 = 图片根 / "00_总索引与说明" / "最终图片SHA256.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def 主函数() -> int:
    files = sorted(
        [
            p
            for chapter in 图片根.glob("第*章_*")
            for folder, suffix in (("PDF结果", ".pdf"), ("PNG结果", ".png"))
            for p in (chapter / folder).glob(f"图*{suffix}")
            if p.is_file()
        ],
        key=lambda p: p.as_posix(),
    )
    if len(files) != 56:
        raise RuntimeError(f"最终图片应为28 PDF + 28 PNG = 56个文件，实际{len(files)}个")
    pdf_count = sum(p.suffix.lower() == ".pdf" for p in files)
    png_count = sum(p.suffix.lower() == ".png" for p in files)
    if (pdf_count, png_count) != (28, 28):
        raise RuntimeError(f"最终格式数量错误：PDF={pdf_count}, PNG={png_count}")

    rows = [
        {
            "相对工作区路径": p.relative_to(工作区).as_posix(),
            "字节数": p.stat().st_size,
            "SHA256": sha256(p),
        }
        for p in files
    ]
    with 输出.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["相对工作区路径", "字节数", "SHA256"])
        writer.writeheader()
        writer.writerows(rows)

    # 写入后立即逐项复算，避免清单生成逻辑与实际文件漂移。
    with 输出.open("r", newline="", encoding="utf-8-sig") as handle:
        check_rows = list(csv.DictReader(handle))
    bad = []
    for row in check_rows:
        path = 工作区 / row["相对工作区路径"]
        if not path.is_file() or path.stat().st_size != int(row["字节数"]) or sha256(path) != row["SHA256"]:
            bad.append(row["相对工作区路径"])
    if bad:
        raise RuntimeError(f"最终图片哈希写入后复算失败：{bad}")
    print(f"已生成并复算56项最终图片SHA-256：{输出}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
