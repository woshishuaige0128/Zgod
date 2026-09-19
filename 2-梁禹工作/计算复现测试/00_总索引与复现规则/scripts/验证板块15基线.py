# -*- coding: utf-8 -*-
"""独立验证板块15对象索引、哈希冻结和目录隔离。"""

from __future__ import annotations

import csv
import hashlib
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
TEST_ROOT = PROJECT_ROOT / "test"
OUTPUT_DIR = TEST_ROOT / "00_总索引与复现规则"
OBJECT_INDEX = OUTPUT_DIR / "全部对象总索引.csv"
SOURCE_MANIFEST = OUTPUT_DIR / "源文件冻结清单.csv"
RECHECK_CSV = OUTPUT_DIR / "源文件冻结复核.csv"
ACCEPTANCE_MD = OUTPUT_DIR / "验收记录.md"

EXPECTED_OBJECT_TYPES = {
    "上游计算门槛": 6,
    "论文图片": 28,
    "论文结果表": 4,
    "定量结论": 7,
}

EXPECTED_SOURCE_TYPES = {
    "硕士论文": 1,
    "小论文": 1,
    "梁禹原工程": 251,
    "既有28图总索引": 1,
    "第三章原始来源副本": 26,
    "第三章绘图输入": 15,
    "第三章数据重建入口": 1,
    "第四章原始来源副本": 16,
    "第四章绘图输入": 8,
    "期刊图6至图10绘图输入": 6,
}

REQUIRED_OBJECT_FIELDS = [
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

REQUIRED_SOURCE_FIELDS = [
    "类别",
    "绝对路径",
    "相对基准",
    "相对路径",
    "文件大小_字节",
    "修改时间",
    "SHA256",
]

ALLOWED_EVIDENCE = {"计算级复现", "绘图级复现", "历史值", "待决定"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(parent.resolve())]).casefold() == str(parent.resolve()).casefold()
    except ValueError:
        return False


def main() -> int:
    errors: list[str] = []
    checks: list[tuple[str, str, str]] = []

    objects = read_csv(OBJECT_INDEX)
    object_headers = set(objects[0].keys()) if objects else set()
    missing_object_headers = [field for field in REQUIRED_OBJECT_FIELDS if field not in object_headers]
    if missing_object_headers:
        errors.append(f"对象索引缺少列：{missing_object_headers}")
    blank_cells: list[str] = []
    for line_number, row in enumerate(objects, start=2):
        for field in REQUIRED_OBJECT_FIELDS:
            if field in row and not str(row[field]).strip():
                blank_cells.append(f"第{line_number}行/{field}")
    if blank_cells:
        errors.append(f"对象索引存在空必填字段：{blank_cells[:20]}")

    object_ids = [row.get("对象ID", "") for row in objects]
    object_counts = Counter(row.get("对象类型", "") for row in objects)
    checks.append(("对象总数", str(len(objects)), "PASS" if len(objects) == 45 else "FAIL"))
    checks.append(("对象ID唯一", f"{len(set(object_ids))}/{len(object_ids)}", "PASS" if len(set(object_ids)) == 45 else "FAIL"))
    checks.append(("对象类型计数", str(dict(object_counts)), "PASS" if dict(object_counts) == EXPECTED_OBJECT_TYPES else "FAIL"))
    if len(objects) != 45:
        errors.append(f"对象总数应为45，实际为{len(objects)}")
    if len(set(object_ids)) != len(object_ids):
        errors.append("对象ID存在重复")
    if dict(object_counts) != EXPECTED_OBJECT_TYPES:
        errors.append(f"对象类型计数不符：{dict(object_counts)}")

    invalid_evidence: list[str] = []
    for row in objects:
        for field in ("目标证据等级", "当前证据等级"):
            value = row.get(field, "")
            if value not in ALLOWED_EVIDENCE:
                invalid_evidence.append(f"{row.get('对象ID')}/{field}={value}")
    if invalid_evidence:
        errors.append(f"出现未定义证据标签：{invalid_evidence}")
    checks.append(("证据标签", "仅使用4种固定标签", "PASS" if not invalid_evidence else "FAIL"))

    existing_success_folders: list[str] = []
    for row in objects:
        path = PROJECT_ROOT / Path(row.get("成功文件夹", ""))
        if path.exists():
            existing_success_folders.append(str(path))
    if existing_success_folders:
        errors.append(f"板块15不应存在成功对象目录：{existing_success_folders}")
    checks.append(("成功目录空置", f"已存在{len(existing_success_folders)}个", "PASS" if not existing_success_folders else "FAIL"))

    sources = read_csv(SOURCE_MANIFEST)
    source_headers = set(sources[0].keys()) if sources else set()
    missing_source_headers = [field for field in REQUIRED_SOURCE_FIELDS if field not in source_headers]
    if missing_source_headers:
        errors.append(f"源文件清单缺少列：{missing_source_headers}")
    source_counts = Counter(row.get("类别", "") for row in sources)
    checks.append(("冻结文件总数", str(len(sources)), "PASS" if len(sources) == sum(EXPECTED_SOURCE_TYPES.values()) else "FAIL"))
    checks.append(("冻结分类计数", str(dict(source_counts)), "PASS" if dict(source_counts) == EXPECTED_SOURCE_TYPES else "FAIL"))
    if dict(source_counts) != EXPECTED_SOURCE_TYPES:
        errors.append(f"冻结分类计数不符：{dict(source_counts)}")

    recheck_rows: list[dict[str, str]] = []
    mismatches: list[str] = []
    inside_test: list[str] = []
    duplicate_paths: list[str] = []
    seen_paths: set[str] = set()
    for row in sources:
        source_path = Path(row["绝对路径"]).resolve()
        path_key = str(source_path).casefold()
        if path_key in seen_paths:
            duplicate_paths.append(str(source_path))
        seen_paths.add(path_key)
        if is_within(source_path, TEST_ROOT):
            inside_test.append(str(source_path))
        if not source_path.is_file():
            current_hash = "MISSING"
            result = "MISMATCH"
        else:
            current_hash = sha256(source_path)
            size_match = source_path.stat().st_size == int(row["文件大小_字节"])
            result = "MATCH" if current_hash == row["SHA256"].upper() and size_match else "MISMATCH"
        if result != "MATCH":
            mismatches.append(str(source_path))
        recheck_rows.append(
            {
                **row,
                "当前SHA256": current_hash,
                "复核结果": result,
            }
        )

    with RECHECK_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        fieldnames = REQUIRED_SOURCE_FIELDS + ["当前SHA256", "复核结果"]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(recheck_rows)

    if mismatches:
        errors.append(f"冻结哈希/大小不匹配：{mismatches[:20]}")
    if inside_test:
        errors.append(f"冻结保护源不应位于test内：{inside_test[:20]}")
    if duplicate_paths:
        errors.append(f"冻结清单出现重复路径：{duplicate_paths[:20]}")
    checks.append(("哈希即时复核", f"{len(sources)-len(mismatches)}/{len(sources)} MATCH", "PASS" if not mismatches else "FAIL"))
    checks.append(("保护源位于test外", f"违规{len(inside_test)}个", "PASS" if not inside_test else "FAIL"))
    checks.append(("冻结路径唯一", f"{len(seen_paths)}/{len(sources)}", "PASS" if not duplicate_paths else "FAIL"))

    overall = "PASS" if not errors else "FAIL"
    lines = [
        "# 板块15验收记录",
        "",
        f"复核时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        f"总结果：**{overall}**",
        "",
        "| 检查项 | 实际结果 | 判定 |",
        "|---|---|---|",
    ]
    for name, actual, result in checks:
        lines.append(f"| {name} | {actual.replace('|', '/')} | {result} |")
    lines.extend(
        [
            "",
            "## 行动边界",
            "",
            "- 本板块没有运行MATLAB或任何模型计算。",
            "- 本板块没有创建逐图、逐表、逐结论或上游对象的成功子目录。",
            "- `计算级复现`、`绘图级复现`、`历史值`、`待决定`四种标签保持分离。",
            "- 进程残留由验证脚本退出后的PowerShell独立检查，不在正在运行的Python进程内部伪判。",
            "",
            "## 错误",
            "",
        ]
    )
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- 无。")
    ACCEPTANCE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"对象：{len(objects)}项；唯一ID：{len(set(object_ids))}")
    print(f"冻结源：{len(sources)}个；哈希MATCH：{len(sources)-len(mismatches)}")
    print(f"成功目录已存在：{len(existing_success_folders)}个")
    print(f"板块15验收：{overall}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
