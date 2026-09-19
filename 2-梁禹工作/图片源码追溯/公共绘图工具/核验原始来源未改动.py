"""将当前只读来源逐字节哈希与任务开始时冻结清单比较。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
清单 = 工作区 / "figure" / "00_总索引与说明" / "原始来源SHA256.csv"
报告 = 工作区 / "figure" / "00_总索引与说明" / "原始来源未改动核验.json"
补充清单 = 工作区 / "figure" / "00_总索引与说明" / "补充LaTeX文本来源SHA256_外部重编译事件后.csv"
可变辅助构建产物 = {
    (工作区.parent / "manuscript" / "manuscript.pdf").resolve(),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


with 清单.open("r", newline="", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))

错误: list[str] = []
警告: list[str] = []


def 核验行(r: dict[str, str], 允许构建产物变化: bool = False) -> None:
    p = Path(r["绝对路径"])
    if not p.is_file():
        错误.append(f"来源文件缺失：{p}")
        return
    size = p.stat().st_size
    if size != int(r["字节数"]):
        msg = f"来源文件字节数变化：{p}，冻结{r['字节数']}，当前{size}"
        (警告 if 允许构建产物变化 and p.resolve() in 可变辅助构建产物 else 错误).append(msg)
        return
    digest = sha256(p)
    if digest.lower() != r["SHA256"].lower():
        msg = f"来源文件SHA256变化：{p}；冻结{r['SHA256']}；当前{digest}"
        (警告 if 允许构建产物变化 and p.resolve() in 可变辅助构建产物 else 错误).append(msg)


for r in rows:
    核验行(r, 允许构建产物变化=True)

补充数量 = 0
if 补充清单.is_file():
    with 补充清单.open("r", newline="", encoding="utf-8-sig") as f:
        extra = list(csv.DictReader(f))
    补充数量 = len(extra)
    for r in extra:
        核验行(r)

result = {
    "通过": not 错误,
    "初始冻结文件数": len(rows),
    "外部事件后补充文本源数": 补充数量,
    "硬错误数": len(错误),
    "警告数": len(警告),
    "硬错误": 错误,
    "警告": 警告,
}
报告.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if not 错误 else 1)
