"""补充冻结外层SCI稿的LaTeX文本源；基线建立在已发现外部重编译事件之后。"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
根 = 工作区.parent / "manuscript"
输出 = 工作区 / "figure" / "00_总索引与说明" / "补充LaTeX文本来源SHA256_外部重编译事件后.csv"
扩展名 = {".tex", ".bib", ".cls", ".bst"}

if 输出.exists() and "--force-rebaseline" not in sys.argv[1:]:
    raise SystemExit(
        f"拒绝覆盖外部事件后补充基线：{输出}\n"
        "如确需在全新审计事件中重建，请显式传入 --force-rebaseline 并记录原因。"
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


files = sorted(p.resolve() for p in 根.rglob("*") if p.is_file() and p.suffix.lower() in 扩展名)
if not files:
    raise FileNotFoundError(f"没有找到LaTeX文本源：{根}")
with 输出.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["绝对路径", "字节数", "SHA256", "基线说明"])
    for p in files:
        writer.writerow([str(p), p.stat().st_size, sha256(p), "外部重编译事件后于2026-08-13补充冻结"])
print(f"已补充冻结{len(files)}个LaTeX文本源：{输出}")
