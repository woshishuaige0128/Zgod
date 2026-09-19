"""校验四章交付清单并回填28图总索引。

只有当28个唯一ID均出现一次、10个交付字段非空且状态明确时才写回总索引。
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
图片根 = 工作区 / "figure"
总索引 = 图片根 / "00_总索引与说明" / "图片总索引.csv"
允许状态 = {"已复现", "已重绘"}
必填字段 = [
    "唯一ID",
    "代码入口",
    "数据文件",
    "PDF结果",
    "PNG结果",
    "原始来源",
    "恢复方式",
    "验证记录",
    "状态",
    "备注",
]


def 读取(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def 规范相对路径(value: str, field: str, uid: str) -> str:
    texts = [x.strip().replace("\\", "/") for x in value.split(";") if x.strip()]
    if not texts:
        raise ValueError(f"图{uid}字段“{field}”为空")
    if field in {"代码入口", "PDF结果", "PNG结果", "验证记录"} and len(texts) != 1:
        raise ValueError(f"图{uid}字段“{field}”必须恰好一个文件，实际{len(texts)}个")
    result: list[str] = []
    for text in texts:
        path = Path(text)
        if path.is_absolute():
            try:
                path = path.resolve().relative_to(工作区.resolve())
            except ValueError as exc:
                raise ValueError(f"图{uid}字段“{field}”不在工作区内：{text}") from exc
        full = (工作区 / path).resolve()
        try:
            path = full.relative_to(工作区.resolve())
        except ValueError as exc:
            raise ValueError(f"图{uid}字段“{field}”通过相对路径逃逸工作区：{text}") from exc
        if not full.is_file() or full.stat().st_size == 0:
            raise FileNotFoundError(f"图{uid}字段“{field}”指向缺失/空文件：{path}")
        result.append(path.as_posix())
    return ";".join(result)


def 稳定合并备注(*values: str) -> str:
    """按中文/英文分号拆分并保持首次出现顺序，保证重复汇总幂等。"""
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in value.replace(";", "；").split("；"):
            text = part.strip()
            if text and text not in seen:
                seen.add(text)
                parts.append(text)
    return "；".join(parts)


def 主函数() -> int:
    清单文件 = sorted(图片根.glob("第*章_*/章节交付清单.csv"))
    if not 清单文件:
        raise FileNotFoundError("尚未找到任何章节交付清单.csv")

    交付行: list[dict[str, str]] = []
    for path in 清单文件:
        rows = 读取(path)
        if not rows:
            raise ValueError(f"空清单：{path.relative_to(工作区)}")
        if list(rows[0].keys()) != 必填字段:
            raise ValueError(
                f"清单列名/顺序错误：{path.relative_to(工作区)}；"
                f"应为{必填字段}，实际{list(rows[0].keys())}"
            )
        交付行.extend(rows)

    原索引 = 读取(总索引)
    索引ID = [r["唯一ID"].strip() for r in 原索引]
    交付ID = [r["唯一ID"].strip() for r in 交付行]
    重复 = sorted(uid for uid, n in Counter(交付ID).items() if n != 1)
    if 重复:
        raise ValueError(f"章节清单唯一ID重复：{重复}")
    if set(交付ID) != set(索引ID) or len(交付ID) != 28:
        缺失 = sorted(set(索引ID) - set(交付ID))
        多余 = sorted(set(交付ID) - set(索引ID))
        raise ValueError(f"章节清单覆盖不是28图：实际{len(交付ID)}，缺失{缺失}，多余{多余}")

    by_id: dict[str, dict[str, str]] = {}
    for row in 交付行:
        uid = row["唯一ID"].strip()
        for field in 必填字段:
            if not row[field].strip():
                raise ValueError(f"图{uid}字段“{field}”为空")
        if row["状态"].strip() not in 允许状态:
            raise ValueError(f"图{uid}状态不明确：{row['状态']}")
        for field in ("代码入口", "数据文件", "PDF结果", "PNG结果", "原始来源", "验证记录"):
            row[field] = 规范相对路径(row[field], field, uid)
        by_id[uid] = row

    输出列 = list(原索引[0].keys())
    if "验证记录" not in 输出列:
        输出列.insert(输出列.index("状态"), "验证记录")
    for row in 原索引:
        item = by_id[row["唯一ID"].strip()]
        row["代码入口"] = item["代码入口"]
        row["数据文件"] = item["数据文件"]
        row["PDF结果"] = item["PDF结果"]
        row["PNG结果"] = item["PNG结果"]
        row["验证记录"] = item["验证记录"]
        row["原始来源候选"] = item["原始来源"]
        row["恢复方式"] = item["恢复方式"]
        row["状态"] = item["状态"]
        原备注 = row.get("备注", "").strip()
        新备注 = item["备注"].strip()
        row["备注"] = 稳定合并备注(原备注, 新备注)

    临时 = 总索引.with_suffix(".csv.tmp")
    with 临时.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=输出列)
        writer.writeheader()
        writer.writerows(原索引)
    临时.replace(总索引)
    状态统计 = Counter(r["状态"] for r in 原索引)
    print(f"已汇总{len(清单文件)}份章节清单、28张图；状态：{dict(状态统计)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
