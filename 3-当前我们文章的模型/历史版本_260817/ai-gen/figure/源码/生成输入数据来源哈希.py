"""验证新图片包的九份输入快照与既有28图证据库逐字节一致。"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path


源码目录 = Path(__file__).resolve().parent
图片根目录 = 源码目录.parent
本地数据目录 = 图片根目录 / "输入数据"
证据库根 = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\figure")

来源映射 = {
    "第1至2章示意图参数.json": 证据库根 / "第2章_系统缩聚理论和模型建立" / "输入数据" / "第1至2章示意图参数.json",
    "图3-1与图3-2_结构自由度参数.json": 证据库根 / "第3章_缩聚对试验精度的影响" / "输入数据" / "图3-1与图3-2_结构自由度参数.json",
    "第一类划分_ElCentro地震响应.csv": 证据库根 / "第3章_缩聚对试验精度的影响" / "输入数据" / "第一类划分_ElCentro地震响应.csv",
    "第二类划分_ElCentro地震响应.csv": 证据库根 / "第3章_缩聚对试验精度的影响" / "输入数据" / "第二类划分_ElCentro地震响应.csv",
    "第一类划分_Chirp响应.csv": 证据库根 / "第3章_缩聚对试验精度的影响" / "输入数据" / "第一类划分_Chirp响应.csv",
    "第二类划分_Chirp响应.csv": 证据库根 / "第3章_缩聚对试验精度的影响" / "输入数据" / "第二类划分_Chirp响应.csv",
    "图4-2_极点映射参数.json": 证据库根 / "第4章_缩聚对试验稳定性的影响" / "输入数据" / "图4-2_极点映射参数.json",
    "图4-4_第一类子结构划分稳定域_边界数据.csv": 证据库根 / "第4章_缩聚对试验稳定性的影响" / "输入数据" / "图4-4_第一类子结构划分稳定域_边界数据.csv",
    "图4-5_第二类子结构划分稳定域_边界数据.csv": 证据库根 / "第4章_缩聚对试验稳定性的影响" / "输入数据" / "图4-5_第二类子结构划分稳定域_边界数据.csv",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def 生成并验证() -> Path:
    rows = []
    errors = []
    for name, source in 来源映射.items():
        local = 本地数据目录 / name
        if not source.is_file() or not local.is_file():
            errors.append(f"缺少文件：{source} 或 {local}")
            continue
        source_hash = _sha256(source)
        local_hash = _sha256(local)
        same = source_hash == local_hash and source.stat().st_size == local.stat().st_size
        rows.append(
            {
                "本地文件": str(local.relative_to(图片根目录)),
                "权威来源": str(source),
                "字节数": local.stat().st_size,
                "本地SHA256": local_hash,
                "来源SHA256": source_hash,
                "逐字节一致": "是" if same else "否",
            }
        )
        if not same:
            errors.append(f"哈希或大小不一致：{name}")

    output = 图片根目录 / "验证记录" / "输入数据来源与哈希.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["本地文件"])
        writer.writeheader()
        writer.writerows(rows)
    if errors:
        raise RuntimeError("；".join(errors))
    print(f"九份输入快照逐字节一致：{output}")
    return output


if __name__ == "__main__":
    生成并验证()
