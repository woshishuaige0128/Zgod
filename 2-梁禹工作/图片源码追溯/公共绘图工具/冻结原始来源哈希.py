"""计算本任务全部只读来源的 SHA-256，输出到总索引目录。"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
RHTS根 = 工作区.parent
输出 = 工作区 / "figure" / "00_总索引与说明" / "原始来源SHA256.csv"

# 该文件是“任务开始时”不可变基线，误覆盖会永久破坏来源未改动证据。
# 仅在显式传入 --force-rebaseline 时允许重新建立；此选项不属于正常复现流程。
if 输出.exists() and "--force-rebaseline" not in sys.argv[1:]:
    raise SystemExit(
        f"拒绝覆盖既有任务开始基线：{输出}\n"
        "如确需在全新任务中重新建立基线，请显式传入 --force-rebaseline 并记录原因。"
    )

来源 = [
    RHTS根 / "梁禹手稿.pdf",
    RHTS根 / "图书馆-2022205052+梁禹+实时混合实验系统缩聚方法研究及其稳定性分析+土木工程+李宁.docx",
    RHTS根 / "梁禹硕士答辩-20250528.pptx",
    RHTS根 / "liangyustability-master.zip",
    RHTS根 / "maRTHS-bmk-RoDeAC-main.zip",
]

扫描目录 = [
    工作区 / "liangyustability-master",
    RHTS根 / "manuscript",
    RHTS根 / "maRTHS-bmk-RoDeAC-main" / "maRTHS-bmk-RoDeAC-main",
]

允许扩展名 = {
    ".m",
    ".mlx",
    ".slx",
    ".mat",
    ".csv",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".docx",
    ".pptx",
    ".md",
}


def 文件哈希(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


文件集: set[Path] = {p.resolve() for p in 来源 if p.is_file()}
for 根 in 扫描目录:
    if not 根.is_dir():
        continue
    for p in 根.rglob("*"):
        if p.is_file() and p.suffix.lower() in 允许扩展名:
            文件集.add(p.resolve())

输出.parent.mkdir(parents=True, exist_ok=True)
with 输出.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["绝对路径", "字节数", "SHA256"])
    for p in sorted(文件集, key=lambda x: str(x).lower()):
        writer.writerow([str(p), p.stat().st_size, 文件哈希(p)])

print(f"已冻结 {len(文件集)} 个来源文件：{输出}")
