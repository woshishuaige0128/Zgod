"""由最终总索引、完整性审计和环境记录生成自包含的交付报告。"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path


工作区 = Path(__file__).resolve().parents[2]
图片根 = 工作区 / "figure"
索引路径 = 图片根 / "00_总索引与说明" / "图片总索引.csv"
审计路径 = 图片根 / "00_总索引与说明" / "图片完整性审计.json"
环境路径 = 图片根 / "00_总索引与说明" / "运行环境.txt"
输出路径 = 图片根 / "00_总索引与说明" / "验证总报告.md"


def 读取CSV(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def 链接(path_text: str, label: str) -> str:
    result: list[str] = []
    values = [x.strip() for x in path_text.split(";") if x.strip()]
    for i, text in enumerate(values, start=1):
        path = Path(text.replace("\\", "/"))
        if path.is_absolute():
            path = path.relative_to(工作区)
        absolute = (工作区 / path).resolve()
        relative = Path(os.path.relpath(absolute, start=输出路径.parent.resolve()))
        suffix = str(i) if len(values) > 1 else ""
        result.append(f"[{label}{suffix}]({relative.as_posix()})")
    return "、".join(result)


def 主函数() -> int:
    rows = 读取CSV(索引路径)
    if len(rows) != 28:
        raise ValueError(f"总索引不是28行：{len(rows)}")
    audit = json.loads(审计路径.read_text(encoding="utf-8"))
    if not audit.get("通过"):
        raise RuntimeError("完整性审计未通过，不能生成最终验证总报告")
    statuses = Counter(r["状态"].strip() for r in rows)
    chapters = Counter(r["章节"].strip() for r in rows)
    types = Counter(r["来源分类"].strip() for r in rows)

    lines = [
        "# 梁禹硕士论文28张图片源码追溯与SCI规范重绘验证总报告",
        "",
        f"- 生成时间：{dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        "- 论文：《实时混合实验系统缩聚方法研究及其稳定性分析》",
        f"- 最终结论：**通过**；28个唯一图片实例均具备原始来源、数据、中文命名代码入口、单页PDF、600 dpi PNG和逐图验证记录。",
        f"- 章节数量：{dict(chapters)}",
        f"- 完成状态：{dict(statuses)}",
        f"- 来源分类：{dict(types)}",
        "- 自动审计：28行索引、28个唯一ID、28份PDF、28份PNG，错误0。",
        "- 来源完整性：真正的论文/代码/数据/图源通过；外层可再生 `manuscript.pdf` 在任务期间被外部重编译，作为警告保留，详见 `外部辅助构建产物变更记录.md`。",
        "",
        "## 真实性边界",
        "",
        "- MATLAB/Simulink结果图使用梁禹工程中的模型、矩阵或保存的稳定域数据恢复；不使用拟合曲线或伪造数据。",
        "- 原生可编辑工程缺失的嵌入示意图，明确标为依据原稿语义建立的参数化矢量重绘代码，不冒充原作者源码。",
        "- 图4-1是鲁旭杰[48]的引用素材；本包保留引用属性，只提供语义等价的矢量重绘入口。",
        "",
        "## 原稿中已确认且未静默掩盖的问题",
        "",
        "1. 第3章图号跳过图3-3和图3-4；整理包保留这一事实。",
        "2. 五张Chirp响应图的原题注依次写成图3-11、图3-11、图3-13、图3-13、图3-13；整理唯一ID使用图3-11至图3-15，同时保留原稿图号。",
        "3. 图书馆版DOCX最后一张Chirp组合图误贴了地震响应局部窗；最终图使用真实Chirp数据，答辩PPT第20页只作视觉证据。",
        "4. 图4-5的原始MAT文件把绘图索引序列保存进扩展数组；共同物理网格之外没有满足稳定判据的点，清洗依据记录在逐图验证文件。",
        "",
        "## 统一绘图规范验收",
        "",
        "- 27张参数化重绘/曲线图使用Computer Modern 9 pt；图2-9保留原生Simulink导出的嵌入Arial/宋体作为可追溯例外，且无Type 3字体。",
        "- 坐标刻度向内、四边刻度、无图内标题、无默认网格、图例无边框。",
        "- 最终结果同时包含单页矢量PDF和600 dpi PNG；图2-8是依据论文嵌入图与真实SLX块拓扑的可追溯矢量重绘，图2-9是原生Simulink子系统的矢量导出。",
        "",
        "## 逐图证据入口",
        "",
        "|唯一ID|原稿图号|图题|恢复方式|状态|代码|数据|验证|",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            "|{uid}|{orig}|{title}|{mode}|{status}|{code}|{data}|{check}|".format(
                uid=r["唯一ID"],
                orig=r["原稿图号"],
                title=r["图题"].replace("|", "\\|"),
                mode=r["恢复方式"].replace("|", "\\|"),
                status=r["状态"],
                code=链接(r["代码入口"], "代码"),
                data=链接(r["数据文件"], "数据"),
                check=链接(r["验证记录"], "记录"),
            )
        )

    lines.extend(
        [
            "",
            "## 运行与审阅入口",
            "",
            "- 一键生成：`figure/生成全部图片.py`。",
            "- 全部图片缩略图：`figure/00_总索引与说明/全部图片缩略图总览.pdf`。",
            "- 机器审计：`figure/00_总索引与说明/图片完整性审计.md`。",
            "- 运行环境：`figure/00_总索引与说明/运行环境.txt`。",
            "",
            "## 运行环境快照",
            "",
            "```text",
            环境路径.read_text(encoding="utf-8").rstrip(),
            "```",
            "",
        ]
    )
    输出路径.write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成最终验证总报告：{输出路径}")
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())
