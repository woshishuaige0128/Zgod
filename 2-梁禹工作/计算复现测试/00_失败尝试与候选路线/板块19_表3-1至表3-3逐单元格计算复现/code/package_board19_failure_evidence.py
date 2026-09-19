from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


BOARD_NAME = "板块19_表3-1至表3-3逐单元格计算复现"


def find_board_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if candidate.name == BOARD_NAME:
            return candidate
    raise RuntimeError("无法定位板块19隔离目录。")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空CSV：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def copy_files(board_root: Path, package_root: Path, mappings: list[tuple[str, str]]) -> None:
    for source_relative, destination_relative in mappings:
        source = board_root / source_relative
        destination = package_root / destination_relative
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256_file(source) != sha256_file(destination):
            raise RuntimeError(f"复制哈希不一致：{source} -> {destination}")


def build_manifest(package_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file() or path.name == "artifact_manifest.csv":
            continue
        rows.append(
            {
                "relative_path": path.relative_to(package_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "role": "self_contained_readme"
                if path.name == "README.md"
                else "rerun_entry"
                if path.parent.name == "code"
                else "historical_attempt_log"
                if path.parent.name == "logs"
                else "machine_readable_evidence",
            }
        )
    write_csv(package_root / "artifact_manifest.csv", rows)
    return rows


def main() -> None:
    board_root = find_board_root(Path(__file__).resolve().parent)
    project_root = board_root.parents[2]
    failure_base = board_root.parent
    all_cells = read_csv(board_root / "outputs" / "evidence" / "table3_all_40_cells.csv")

    specifications = [
        {
            "object_id": "T3-1",
            "name": "表3-1_两类划分前两阶固有频率相对误差",
            "paper_name": "表3-1 两类划分前两阶固有频率相对误差",
            "match_count": 4,
            "total_count": 8,
            "formula": "100*abs(f_full-f_red)/f_full",
            "conclusion": (
                "第一类划分4/4单元格按论文三位小数闭合；第二类划分4/4均不闭合。"
                "当前有文档依据的完整/局部物理/能量划分候选也没有形成第二类整组闭合路线。"
            ),
            "gap": (
                "缺少能同时产生论文第二类Guyan 13.040/24.575%及Craig-Bampton "
                "0.007/0.834%的作者历史质量/刚度矩阵、参数或另一划分入口。"
            ),
            "mappings": [
                ("outputs/modal_python/table3_1_cell_adjudication.csv", "data/表3-1_逐单元格裁决_Python.csv"),
                ("outputs/modal_matlab/table3_1_cell_adjudication_matlab.csv", "data/表3-1_逐单元格裁决_MATLAB.csv"),
                ("outputs/modal_python/frequency_candidates_python.csv", "data/表3-1_全部频率候选_Python.csv"),
                ("outputs/modal_matlab/frequency_candidates_matlab.csv", "data/表3-1_全部频率候选_MATLAB.csv"),
                ("outputs/documented_alternatives/documented_frequency_alternatives.csv", "data/表3-1_有文档依据的替代路线.csv"),
                ("outputs/modal_python/modal_cross_language_comparison.csv", "data/表3-1与表3-2_模态跨语言比较.csv"),
                ("logs/original_fguyou.log", "logs/原作者_fguyou_空工作区运行.log"),
            ],
            "commands": [
                "D:/Downlad/Matlab/bin/matlab.exe -batch \"run('code/compute_board19_modal_metrics.m')\"",
                "D:/Software/python/python.exe code/independent_board19_modal_metrics.py",
                "D:/Software/python/python.exe code/audit_documented_modal_alternatives.py",
            ],
        },
        {
            "object_id": "T3-2",
            "name": "表3-2_两类划分前两阶MAC",
            "paper_name": "表3-2 两类划分前两阶模态保证准则（MAC）",
            "match_count": 7,
            "total_count": 8,
            "formula": "abs(phi_full.T@phi_red)^2/((phi_full.T@phi_full)*(phi_red.T@phi_red))",
            "conclusion": (
                "统一使用正确自然顺序的保留坐标普通欧氏MAC后，7/8单元格按论文四位小数闭合；"
                "第二类划分Craig-Bampton第2阶为0.9999997834，舍入1.0000，而论文为0.9998。"
            ),
            "gap": (
                "缺少与论文第二类Craig-Bampton频率路线一致的历史振型对象。"
                "全15维质量加权候选虽可单独命中该格，却会破坏第一类统一口径，因此禁止混用填表。"
            ),
            "mappings": [
                ("outputs/modal_python/table3_2_cell_adjudication.csv", "data/表3-2_逐单元格裁决_Python.csv"),
                ("outputs/modal_matlab/table3_2_cell_adjudication_matlab.csv", "data/表3-2_逐单元格裁决_MATLAB.csv"),
                ("outputs/modal_python/mac_candidates_python.csv", "data/表3-2_全部MAC候选_Python.csv"),
                ("outputs/modal_matlab/mac_candidates_matlab.csv", "data/表3-2_全部MAC候选_MATLAB.csv"),
                ("outputs/documented_alternatives/documented_mac_alternatives.csv", "data/表3-2_有文档依据的替代路线.csv"),
                ("outputs/modal_python/modal_cross_language_comparison.csv", "data/表3-1与表3-2_模态跨语言比较.csv"),
                ("outputs/workbook_inputs/mac_vectors.csv", "data/表3-2_工作簿模态向量输入.csv"),
                ("logs/original_MAC.log", "logs/原作者_MAC_空工作区运行.log"),
                ("logs/original_MAC_full.log", "logs/原作者_MAC_full_空工作区运行.log"),
            ],
            "commands": [
                "D:/Downlad/Matlab/bin/matlab.exe -batch \"run('code/compute_board19_modal_metrics.m')\"",
                "D:/Software/python/python.exe code/independent_board19_modal_metrics.py",
                "D:/Software/python/python.exe code/audit_documented_modal_alternatives.py",
            ],
        },
        {
            "object_id": "T3-3",
            "name": "表3-3_两类划分五个Chirp频段及ElCentro响应NRMSE",
            "paper_name": "表3-3 两类划分五个Chirp频段及El Centro响应NRMSE",
            "match_count": 13,
            "total_count": 24,
            "formula": "100*sqrt(mean((x_full-x_red)^2))/(max(x_full)-min(x_full))",
            "conclusion": (
                "历史均值/完整40 s同楼层参考峰峰值口径得到13/24单元格末位闭合："
                "第一类Chirp采用第2层为9/10，第一类El Centro第2层2/2，第二类El Centro第3层2/2；"
                "第二类Chirp任一统一楼层均为0/10。"
            ),
            "gap": (
                "缺少作者第二类Chirp历史逐点响应；第一类Chirp最高频Guyan当前为0.7450123%，"
                "论文为0.7452%，包括端点、精确频率边界及连续积分在内的有文档口径仍未命中。"
            ),
            "mappings": [
                ("outputs/nrmse_python/table3_3_cell_adjudication.csv", "data/表3-3_逐单元格裁决_Python.csv"),
                ("outputs/nrmse_python/table3_3_group_adjudication.csv", "data/表3-3_整组楼层裁决.csv"),
                ("outputs/nrmse_python/nrmse_candidates_python.csv", "data/表3-3_全部NRMSE候选_Python.csv"),
                ("outputs/nrmse_matlab/nrmse_candidates_matlab.csv", "data/表3-3_全部NRMSE候选_MATLAB.csv"),
                ("outputs/nrmse_python/nrmse_historical_floor_candidates_python.csv", "data/表3-3_历史口径逐楼层候选.csv"),
                ("outputs/nrmse_python/nrmse_cross_language_comparison.csv", "data/表3-3_NRMSE跨语言比较.csv"),
                ("outputs/nrmse_python/nrmse_input_checks_python.csv", "data/表3-3_响应输入检查.csv"),
                ("outputs/workbook_inputs/nrmse_aggregates.csv", "data/表3-3_工作簿聚合输入.csv"),
                ("logs/original_RMSE.log", "logs/原作者_RMSE_空工作区运行.log"),
                ("logs/original_RMSE_full.log", "logs/原作者_RMSE_full_空工作区运行.log"),
            ],
            "commands": [
                "D:/Downlad/Matlab/bin/matlab.exe -batch \"run('code/compute_board19_nrmse.m')\"",
                "D:/Software/python/python.exe code/independent_board19_nrmse.py",
            ],
        },
    ]

    for spec in specifications:
        success_root = project_root / "test" / spec["name"]
        if success_root.exists():
            raise RuntimeError(f"未闭合对象不应存在正式成功目录：{success_root}")
        package_root = failure_base / spec["name"]
        package_root.mkdir(parents=True, exist_ok=True)
        copy_files(board_root, package_root, spec["mappings"])

        subset = [row for row in all_cells if row["object_id"] == spec["object_id"]]
        if len(subset) != spec["total_count"]:
            raise RuntimeError(f"{spec['object_id']}统一证据子集数量异常：{len(subset)}")
        write_csv(package_root / "data" / f"{spec['object_id']}_统一证据子集.csv", subset)

        readme = f"""# {spec['paper_name']}：失败证据与候选路线

## 人话结论

本对象完成了逐单元格计算审计，但**没有达到整表计算级复现**。当前冻结路线按论文印刷小数位闭合 {spec['match_count']}/{spec['total_count']} 格，因此本目录位于 `test/00_失败尝试与候选路线/`；对应的正式成功目录刻意保持不存在。

{spec['conclusion']}

## 计算合同

- 公式：`{spec['formula']}`
- 对比方式：计算未舍入值，同时按论文该单元格印刷小数位舍入比较；禁止修改标准迁就结果。
- 双实现：当前被选单元格均由 MATLAB 与独立 Python 路线交叉核验。
- 证据等级：匹配格标为“计算级复现（限定当前冻结路线）”；未匹配格保留“历史值/待决定”。

## 尚缺的作者级证据

{spec['gap']}

## 文件导航

- `data/`：逐格裁决、全部候选、跨语言比较和工作簿中间量。
- `logs/`：原作者脚本在空工作区的真实失败现场。
- `code/复现入口.md`：从板块19中央代码重新计算的命令与边界。
- `artifact_manifest.csv`：本目录除清单自身外每个文件的字节数与SHA-256。
- 总公式工作簿：`../{BOARD_NAME}/outputs/板块19_表3-1至表3-3逐单元格计算复现审计.xlsx`（只保留一份，不在本目录重复复制）。

## 禁止误读

这里的“失败”只表示当前冻结证据不能逐格恢复论文整表，不表示公式实现失败，也不表示论文值一定错误。缺失作者历史矩阵、振型或逐点时程时，必须保持“待决定”。
"""
        (package_root / "README.md").write_text(readme, encoding="utf-8")

        command_lines = "\n".join(f"{index}. `{command}`" for index, command in enumerate(spec["commands"], 1))
        rerun = f"""# 复现入口

所有命令都应在板块19中央隔离目录执行：

`{board_root}`

{command_lines}

工作簿重新生成命令：

`C:/Users/lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe code/build_board19_workbook.mjs`

这些入口只读取 `input/` 冻结副本并写入板块19中央 `outputs/`；本失败证据目录不承担计算源身份，也不得反向覆盖冻结输入。
"""
        code_dir = package_root / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        (code_dir / "复现入口.md").write_text(rerun, encoding="utf-8")

        summary = {
            "object_id": spec["object_id"],
            "paper_name": spec["paper_name"],
            "target_cells": spec["total_count"],
            "rounded_matches": spec["match_count"],
            "all_cells_closed": False,
            "formal_success_directory_exists": False,
            "evidence_state": "部分计算级复现；其余历史值/待决定",
            "central_workbook_relative_path": f"../{BOARD_NAME}/outputs/板块19_表3-1至表3-3逐单元格计算复现审计.xlsx",
            "status": "FAILURE_EVIDENCE_PACKAGED",
        }
        (package_root / "package_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        manifest_rows = build_manifest(package_root)
        if len(manifest_rows) < 6:
            raise RuntimeError(f"{spec['object_id']}证据包文件过少：{len(manifest_rows)}")

    result = {
        "packages": [spec["name"] for spec in specifications],
        "package_count": len(specifications),
        "formal_success_directories_present": 0,
        "status": "PASS",
    }
    output = board_root / "outputs" / "evidence" / "failure_packages_summary.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
