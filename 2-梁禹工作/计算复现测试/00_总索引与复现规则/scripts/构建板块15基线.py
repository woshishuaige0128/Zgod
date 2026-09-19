# -*- coding: utf-8 -*-
"""构建板块15的45项对象总索引与保护源冻结清单。

本脚本只读项目源文件，只在 test/00_总索引与复现规则 内写生成物，
不启动 MATLAB，也不创建任何逐图/逐表成功目录。
"""

from __future__ import annotations

import csv
import hashlib
import platform
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
RHTS_ROOT = PROJECT_ROOT.parent
TEST_ROOT = PROJECT_ROOT / "test"
OUTPUT_DIR = TEST_ROOT / "00_总索引与复现规则"
FIGURE_INDEX = PROJECT_ROOT / "figure" / "00_总索引与说明" / "图片总索引.csv"
THESIS_PDF = RHTS_ROOT / "梁禹手稿.pdf"
MANUSCRIPT = RHTS_ROOT / "260817" / "manuscript_0824.tex"
ORIGINAL_PROJECT = PROJECT_ROOT / "liangyustability-master"

OBJECT_FIELDS = [
    "对象ID",
    "对象类型",
    "论文编号",
    "唯一图号",
    "名称",
    "PDF页",
    "印刷页",
    "计算对象",
    "对比基准",
    "目标证据等级",
    "当前证据等级",
    "当前状态",
    "成功文件夹",
    "失败尝试目录",
    "备注",
]

SOURCE_FIELDS = [
    "类别",
    "绝对路径",
    "相对基准",
    "相对路径",
    "文件大小_字节",
    "修改时间",
    "SHA256",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = re.sub(r"\s+", "", value)
    return value.strip("._")


def planned_paths(prefix: str, name: str, upstream: bool = False) -> tuple[str, str]:
    folder = f"{prefix}_{safe_name(name)}"
    if upstream:
        success = Path("test") / "00_上游模型身份证" / folder
    else:
        success = Path("test") / folder
    failure = Path("test") / "00_失败尝试与候选路线" / folder
    return success.as_posix(), failure.as_posix()


def object_row(
    object_id: str,
    object_type: str,
    paper_no: str,
    unique_figure_no: str,
    name: str,
    pdf_page: str,
    print_page: str,
    calculation: str,
    baseline: str,
    target_evidence: str,
    current_evidence: str,
    state: str,
    success: str,
    failure: str,
    note: str,
) -> dict[str, str]:
    return dict(
        zip(
            OBJECT_FIELDS,
            [
                object_id,
                object_type,
                paper_no,
                unique_figure_no,
                name,
                pdf_page,
                print_page,
                calculation,
                baseline,
                target_evidence,
                current_evidence,
                state,
                success,
                failure,
                note,
            ],
            strict=True,
        )
    )


def build_objects() -> list[dict[str, str]]:
    objects: list[dict[str, str]] = []

    upstream = [
        (
            "U01",
            "参考结构参数与15自由度矩阵",
            "28-30",
            "18-20",
            "论文表2-1、图2-3至图2-5、PDmonicanshu.m及完整模型M/C/K",
            "历史值",
            "论文参数和当前代码均存在，但尚未在本目标内统一自由度顺序并独立装配",
        ),
        (
            "U02",
            "完整模型前五阶频率与质量参与系数",
            "30",
            "20",
            "论文2.7/9.1/18.0/22.1/23.6 Hz与原工程特征值结果",
            "历史值",
            "论文值与当前代码值有差异；质量参与系数生成链待追踪",
        ),
        (
            "U03",
            "第一类物理/数值子结构划分",
            "31-37",
            "21-27",
            "论文图2-6、图3-1与untitled2.mlx/Simulink自由度排列",
            "待决定",
            "需要锁定接口、主/从自由度和结果恢复顺序",
        ),
        (
            "U04",
            "第二类物理/数值子结构划分",
            "31-37",
            "21-27",
            "论文图2-7、图3-2与untitled.mlx/Simulink自由度排列",
            "待决定",
            "需要锁定接口、主/从自由度和结果恢复顺序",
        ),
        (
            "U05",
            "Guyan历史单侧实现、论文公式与标准双侧合同投影",
            "22-27,38-53",
            "12-17,28-43",
            "论文式、原工程Mmm+MmsR路线及T'(M/C/K)T独立审计",
            "计算级复现",
            "既有隔离审计已证明历史单侧与标准双侧不同；本目标仍需纳入完整线路",
        ),
        (
            "U06",
            "Craig--Bampton三固定界面模态的实际实现",
            "24-27,38-53",
            "14-17,28-43",
            "论文Craig--Bampton公式与原工程svds(Kss,Mss,3,'smallest')生成器",
            "计算级复现",
            "既有代码表明每个全局划分总共保留3个固定界面模态，需与小论文文字逐项核对",
        ),
    ]
    for object_id, name, pdf_page, print_page, baseline, evidence, state in upstream:
        success, failure = planned_paths(object_id, name, upstream=True)
        objects.append(
            object_row(
                object_id,
                "上游计算门槛",
                f"上游门槛{object_id}",
                "不适用",
                name,
                pdf_page,
                print_page,
                "是",
                baseline,
                "计算级复现",
                evidence,
                state,
                success,
                failure,
                "上游门槛通过前，下游对象不得因已有图片而自动升级为计算级成功",
            )
        )

    with FIGURE_INDEX.open("r", encoding="utf-8-sig", newline="") as stream:
        figures = list(csv.DictReader(stream))
    if len(figures) != 28:
        raise RuntimeError(f"既有图片总索引应为28行，实际为{len(figures)}行")
    ids = [row["唯一ID"] for row in figures]
    if len(ids) != len(set(ids)):
        raise RuntimeError("既有图片总索引的唯一ID存在重复")

    chapter3_calculation = {f"3-{number}" for number in range(5, 16)}
    stability_calculation = {"4-4", "4-5"}
    for row in figures:
        figure_id = row["唯一ID"]
        name = row["图题"]
        success, failure = planned_paths(f"图{figure_id}", name)
        if figure_id in chapter3_calculation:
            calculation = "是"
            target = "计算级复现"
            current = "计算级复现"
            state = "既有修复路线已真实运行；本目标尚未从上游模型身份证独立重跑并逐图晋升"
            baseline = f"论文PDF图{figure_id} + 第三章冻结MAT/CSV绘图数据 + 原工程Simulink响应"
            note = "必须同时保留历史Guyan单侧实现；不能以标准双侧结果覆盖历史线路"
        elif figure_id in stability_calculation:
            calculation = "是"
            target = "计算级复现"
            current = "绘图级复现"
            state = "历史稳定边界数据可重画，但生成最终极点网格与掩码的保存入口尚未闭合"
            baseline = f"论文PDF图{figure_id} + lqr_2.mat/lqr_3.mat及冻结稳定边界CSV"
            note = "必须恢复原始最大极点模网格，不能把0/0.999阶梯掩码冒充极点模"
        else:
            calculation = "否（非计算结果图）"
            target = "绘图级复现"
            current = "绘图级复现"
            state = "已有可追溯重绘/导出；不是本目标需要新增运行的计算结果"
            baseline = f"论文PDF图{figure_id} + 既有原始嵌入对象/截图/重绘参数"
            note = "保留在45项总索引中用于完整论文线路，但不伪装成数值算例"
        objects.append(
            object_row(
                f"F{figure_id}",
                "论文图片",
                row["原稿图号"],
                figure_id,
                name,
                row["PDF页"],
                row["印刷页"],
                calculation,
                baseline,
                target,
                current,
                state,
                success,
                failure,
                note,
            )
        )

    tables = [
        (
            "T3-1",
            "表3-1",
            "两类划分前两阶固有频率相对误差",
            "51",
            "41",
            "论文表3-1逐单元格 + 原工程与独立特征值计算",
            "论文8个百分数为历史值；第一类可追到当前生成器，第二类当前生成器不吻合",
            "第一类Guyan 0.648/5.411、CB 0.003/0.284；第二类Guyan 13.040/24.575、CB 0.007/0.834",
        ),
        (
            "T3-2",
            "表3-2",
            "两类划分前两阶MAC",
            "51",
            "41",
            "论文表3-2逐单元格 + 完整/恢复模态向量独立MAC",
            "历史脚本存在维数、顺序与恢复路线冲突，尚未计算闭合",
            "第一类Guyan 1.0000/0.9998、CB 1.0000/1.0000；第二类Guyan 0.9962/0.9255、CB 1.0000/0.9998",
        ),
        (
            "T3-3",
            "表3-3",
            "两类划分五个Chirp频段及El Centro响应NRMSE",
            "51-52",
            "41-42",
            "论文表3-3逐单元格 + 冻结三层响应CSV独立NRMSE",
            "第一类与第二类地震值可追到特定楼层；第二类Chirp整表与当前各楼层均不完全吻合",
            "表头单位为百分数；需逐单元格追踪楼层、频段端点与百分数定义",
        ),
        (
            "T4-1",
            "表4-1",
            "两类划分Guyan与Craig--Bampton能量变化率",
            "73",
            "63",
            "论文表4-1逐单元格 + 18自由度能量支路原始时程独立积分",
            "第二类数值可追到含错误归一化/分母的历史脚本；第一类历史入口缺失",
            "第一类Guyan/CB 0.3065/0.1879；第二类Guyan/CB 0.3927/0.2021",
        ),
    ]
    for object_id, paper_no, name, pdf_page, print_page, baseline, state, note in tables:
        success, failure = planned_paths(paper_no, name)
        objects.append(
            object_row(
                object_id,
                "论文结果表",
                paper_no,
                "不适用",
                name,
                pdf_page,
                print_page,
                "是",
                baseline,
                "计算级复现",
                "历史值",
                state,
                success,
                failure,
                note,
            )
        )

    claims = [
        (
            "C01",
            "完整参考模型的固有频率与模态质量参与度",
            "30",
            "20",
            "前五阶2.7/9.1/18.0/22.1/23.6 Hz；前五阶模态质量参与系数达到90%以上",
        ),
        (
            "C02",
            "第二类划分Chirp响应随频率恶化的局部定量描述",
            "49-50",
            "39-40",
            "0.1-0.5 Hz较准；13-14 s接近第一阶；30 s后Guyan恶化；约10 Hz时一二层不足一半、三层接近两倍",
        ),
        (
            "C03",
            "低频及高频条件下的相对精度结论",
            "53",
            "43",
            "低于第一阶频率两法精度超过95%；超过1.3倍第一阶后第一类Guyan回升；CB高频仍超过95%",
        ),
        (
            "C04",
            "响应失真的经验判据",
            "53",
            "43",
            "NRMSE大于7%且固有频率相对误差大于10%时，正文判断响应已经失真",
        ),
        (
            "C05",
            "两类划分的稳定裕度下降量",
            "70-71",
            "60-61",
            "第一类Guyan两个作动器稳定裕度下降接近5 ms；第二类Guyan相对表述接近10 ms",
        ),
        (
            "C06",
            "能量变化率稳定风险阈值",
            "73",
            "63",
            "能量变化率大于0.3时潜在不稳定风险显著增加、稳定域收缩明显",
        ),
        (
            "C07",
            "结论章频率区间、误差幅值与临界时滞总结",
            "75-76",
            "65-66",
            "低频0-0.7倍第一阶；共振0.7-1.3倍第一阶，Guyan峰值10%、CB小于5%；高频大于2倍第一阶，Guyan幅值变化大于50%、CB小于5%；Guyan临界时滞降低5 ms以上",
        ),
    ]
    for object_id, name, pdf_page, print_page, target_value in claims:
        success, failure = planned_paths(f"结论{object_id}", name)
        objects.append(
            object_row(
                object_id,
                "定量结论",
                f"论文定量结论{object_id}",
                "不适用",
                name,
                pdf_page,
                print_page,
                "是",
                f"论文原文目标：{target_value}；须由对应图表与原始数据重新推导",
                "计算级复现",
                "历史值",
                "论文原文已定位；尚未在本目标内从统一上游模型逐项验证",
                success,
                failure,
                "原文结论即使与复算冲突也保留为历史值，复算结果不得反向篡改原文目标",
            )
        )

    if len(objects) != 45:
        raise RuntimeError(f"对象总数应为45，实际为{len(objects)}")
    object_ids = [row["对象ID"] for row in objects]
    if len(object_ids) != len(set(object_ids)):
        raise RuntimeError("对象ID不唯一")
    for row_number, row in enumerate(objects, start=2):
        blanks = [field for field in OBJECT_FIELDS if not str(row[field]).strip()]
        if blanks:
            raise RuntimeError(f"对象索引第{row_number}行存在空字段：{blanks}")
    return objects


def recursive_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    return sorted((path for path in root.rglob("*") if path.is_file()), key=lambda p: str(p).casefold())


def build_source_manifest() -> list[dict[str, object]]:
    chapter3 = PROJECT_ROOT / "figure" / "第3章_缩聚对试验精度的影响"
    chapter4 = PROJECT_ROOT / "figure" / "第4章_缩聚对试验稳定性的影响"
    journal_inputs = RHTS_ROOT / "260817" / "figure" / "results_v2" / "输入数据"
    groups: list[tuple[str, Path, list[Path]]] = [
        ("硕士论文", RHTS_ROOT, [THESIS_PDF]),
        ("小论文", RHTS_ROOT, [MANUSCRIPT]),
        ("梁禹原工程", ORIGINAL_PROJECT, recursive_files(ORIGINAL_PROJECT)),
        ("既有28图总索引", PROJECT_ROOT, [FIGURE_INDEX]),
        ("第三章原始来源副本", PROJECT_ROOT, recursive_files(chapter3 / "原始来源副本")),
        ("第三章绘图输入", PROJECT_ROOT, recursive_files(chapter3 / "输入数据")),
        ("第三章数据重建入口", PROJECT_ROOT, [chapter3 / "可复现代码" / "regenerate_chapter3_data.m"]),
        ("第四章原始来源副本", PROJECT_ROOT, recursive_files(chapter4 / "原始来源副本")),
        ("第四章绘图输入", PROJECT_ROOT, recursive_files(chapter4 / "输入数据")),
        ("期刊图6至图10绘图输入", RHTS_ROOT, recursive_files(journal_inputs)),
    ]

    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for category, base, paths in groups:
        for path in paths:
            resolved = path.resolve(strict=True)
            key = str(resolved).casefold()
            if key in seen:
                continue
            seen.add(key)
            if not resolved.is_file():
                raise RuntimeError(f"冻结对象不是文件：{resolved}")
            stat = resolved.stat()
            rows.append(
                {
                    "类别": category,
                    "绝对路径": str(resolved),
                    "相对基准": str(base.resolve(strict=True)),
                    "相对路径": resolved.relative_to(base.resolve(strict=True)).as_posix(),
                    "文件大小_字节": stat.st_size,
                    "修改时间": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    "SHA256": sha256(resolved),
                }
            )
    rows.sort(key=lambda row: (str(row["类别"]), str(row["绝对路径"]).casefold()))
    return rows


def write_summary(source_rows: list[dict[str, object]]) -> None:
    counts = Counter(str(row["类别"]) for row in source_rows)
    bytes_by_category = Counter()
    for row in source_rows:
        bytes_by_category[str(row["类别"])] += int(row["文件大小_字节"])
    key_hashes = {str(row["绝对路径"]): str(row["SHA256"]) for row in source_rows}
    lines = [
        "# 板块15来源冻结摘要",
        "",
        f"生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "本摘要冻结论文、原工程和既有绘图基准。冻结只证明本板块开始时的文件身份，不证明其中计算正确。",
        "",
        "## 分类统计",
        "",
        "| 类别 | 文件数 | 总字节数 |",
        "|---|---:|---:|",
    ]
    for category in sorted(counts):
        lines.append(f"| {category} | {counts[category]} | {bytes_by_category[category]} |")
    lines.extend(
        [
            "",
            f"冻结文件总数：{len(source_rows)}。",
            "",
            "## 关键保护源",
            "",
            f"- 硕士论文：`{THESIS_PDF}`；SHA-256 `{key_hashes[str(THESIS_PDF.resolve())]}`。",
            f"- 小论文：`{MANUSCRIPT}`；SHA-256 `{key_hashes[str(MANUSCRIPT.resolve())]}`。",
            f"- 梁禹原工程：`{ORIGINAL_PROJECT}`；逐文件冻结，不以目录时间代替文件哈希。",
            "",
            "## 证据边界",
            "",
            "- 第三章既有响应数据可能已达到旧任务的计算级复现，但仍要在本目标中从上游模型身份证重新串联。",
            "- 第四章稳定域当前只有历史边界快照的绘图级复现，不能冒充原始极点网格计算。",
            "- 表格与论文结论中的数字在逐项算回以前保持历史值。",
            "- 本板块未运行MATLAB，也未创建任何逐图或逐表成功目录。",
        ]
    )
    (OUTPUT_DIR / "来源冻结摘要.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_environment() -> None:
    matlab = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
    lines = [
        f"生成时间={datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"项目根目录={PROJECT_ROOT}",
        f"脚本={SCRIPT_PATH}",
        f"Python可执行文件={sys.executable}",
        f"Python版本={sys.version.replace(chr(10), ' ')}",
        f"平台={platform.platform()}",
        f"PowerShell路径={shutil.which('powershell') or shutil.which('pwsh') or '未找到'}",
        f"MATLAB路径={matlab}",
        f"MATLAB文件存在={matlab.is_file()}",
        "MATLAB是否由本板块运行=否",
        "板块15操作范围=只读保护源；只写test/00_总索引与复现规则",
    ]
    (OUTPUT_DIR / "运行环境.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    objects = build_objects()
    sources = build_source_manifest()
    write_csv(OUTPUT_DIR / "全部对象总索引.csv", OBJECT_FIELDS, objects)
    write_csv(OUTPUT_DIR / "源文件冻结清单.csv", SOURCE_FIELDS, sources)
    write_summary(sources)
    write_environment()
    type_counts = Counter(row["对象类型"] for row in objects)
    print(f"对象总索引：{len(objects)}项；分类={dict(type_counts)}")
    print(f"源文件冻结：{len(sources)}个文件")
    print(f"输出目录：{OUTPUT_DIR}")
    print("MATLAB：未运行；逐图/逐表成功目录：未创建")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
