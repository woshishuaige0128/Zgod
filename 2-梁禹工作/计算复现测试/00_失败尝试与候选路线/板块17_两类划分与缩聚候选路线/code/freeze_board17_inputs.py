from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master")
CANDIDATE_ROOT = (
    PROJECT_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块17_两类划分与缩聚候选路线"
)
INPUT_ROOT = CANDIDATE_ROOT / "input"
LOG_ROOT = CANDIDATE_ROOT / "logs"

U01_ROOT = PROJECT_ROOT / "test" / "00_上游模型身份证" / "U01_参考结构参数与15自由度矩阵"
CHAPTER3_ROOT = PROJECT_ROOT / "figure" / "第3章_缩聚对试验精度的影响"
AUTHOR_ROOT = PROJECT_ROOT / "liangyustability-master"
BOARD14_ROOT = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\test\2026-08-24_Guyan双侧投影结论影响核查"
)
PAPER_ROOT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817")
THESIS_PATH = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\梁禹手稿.pdf")


SOURCES: list[tuple[str, str, Path]] = [
    (
        "U01_完整模型矩阵",
        "upstream_u01/reference_model_matlab.mat",
        U01_ROOT / "data" / "reference_model_matlab.mat",
    ),
    (
        "U01_自由度映射",
        "upstream_u01/dof_map.csv",
        U01_ROOT / "data" / "dof_map.csv",
    ),
    (
        "U01_板块16验收摘要",
        "upstream_u01/board16_acceptance_summary.json",
        U01_ROOT / "report" / "board16_acceptance_summary.json",
    ),
    (
        "U01_板块16工件清单",
        "upstream_u01/board16_artifact_manifest.csv",
        U01_ROOT / "report" / "board16_artifact_manifest.csv",
    ),
    (
        "U01_板块16最终验收记录",
        "upstream_u01/板块16_最终验收记录.md",
        U01_ROOT / "report" / "板块16_最终验收记录.md",
    ),
    (
        "第三章_完整参数入口",
        "response_chain/PDmonicanshu.m",
        CHAPTER3_ROOT / "原始来源副本" / "模型与参数原件" / "PDmonicanshu.m",
    ),
    (
        "第三章_当前确定性生成器",
        "response_chain/regenerate_chapter3_data.m",
        CHAPTER3_ROOT / "可复现代码" / "regenerate_chapter3_data.m",
    ),
    (
        "第三章_第二类原LiveScript",
        "response_chain/untitled.mlx",
        CHAPTER3_ROOT / "原始来源副本" / "原始LiveScript" / "untitled.mlx",
    ),
    (
        "第三章_第一类原LiveScript",
        "response_chain/untitled2.mlx",
        CHAPTER3_ROOT / "原始来源副本" / "原始LiveScript" / "untitled2.mlx",
    ),
    (
        "第三章_第二类LiveScript转存",
        "response_chain/untitled_转存.m",
        CHAPTER3_ROOT / "原始来源副本" / "MLX转存文本" / "untitled_转存.m",
    ),
    (
        "第三章_第一类LiveScript转存",
        "response_chain/untitled2_转存.m",
        CHAPTER3_ROOT / "原始来源副本" / "MLX转存文本" / "untitled2_转存.m",
    ),
    (
        "第三章_第一类Simulink",
        "response_chain/lvxvjie_guyan_2.slx",
        CHAPTER3_ROOT / "原始来源副本" / "模型与参数原件" / "lvxvjie_guyan_2.slx",
    ),
    (
        "第三章_第二类Simulink",
        "response_chain/lvxvjie_guyan.slx",
        CHAPTER3_ROOT / "原始来源副本" / "模型与参数原件" / "lvxvjie_guyan.slx",
    ),
    (
        "第三章_自由度语义JSON",
        "response_chain/图3-1与图3-2_结构自由度参数.json",
        CHAPTER3_ROOT / "输入数据" / "图3-1与图3-2_结构自由度参数.json",
    ),
    (
        "第三章_历史映射修正报告",
        "response_chain/两类子结构映射审计与修正报告.md",
        CHAPTER3_ROOT / "验证记录" / "两类子结构映射审计与修正报告.md",
    ),
    (
        "局部物理候选_第一类",
        "local_candidates/PDmonicanshu2.m",
        AUTHOR_ROOT / "能量指标" / "PDmonicanshu2.m",
    ),
    (
        "局部物理候选_第二类",
        "local_candidates/PDmonicanshu3.m",
        AUTHOR_ROOT / "能量指标" / "PDmonicanshu3.m",
    ),
    (
        "局部物理支路_第一类",
        "local_candidates/New_Ps2.m",
        AUTHOR_ROOT / "新结构稳定" / "New_Ps2.m",
    ),
    (
        "局部数值支路_第一类",
        "local_candidates/New_Ns2.m",
        AUTHOR_ROOT / "新结构稳定" / "New_Ns2.m",
    ),
    (
        "局部物理支路_第二类",
        "local_candidates/New_Ps3.m",
        AUTHOR_ROOT / "新结构稳定" / "稳定域" / "New_Ps3.m",
    ),
    (
        "局部数值支路_第二类",
        "local_candidates/New_Ns3.m",
        AUTHOR_ROOT / "新结构稳定" / "稳定域" / "New_Ns3.m",
    ),
    (
        "板块14_第一类矩阵快照",
        "legacy_audit/division_1_guyan_matrices.mat",
        BOARD14_ROOT / "outputs" / "matrices" / "division_1_guyan_matrices.mat",
    ),
    (
        "板块14_第二类矩阵快照",
        "legacy_audit/division_2_guyan_matrices.mat",
        BOARD14_ROOT / "outputs" / "matrices" / "division_2_guyan_matrices.mat",
    ),
    (
        "板块14_Guyan矩阵审计",
        "legacy_audit/guyan_matrix_audit.csv",
        BOARD14_ROOT / "outputs" / "matrices" / "guyan_matrix_audit.csv",
    ),
    (
        "板块14_模态对照",
        "legacy_audit/guyan_modal_comparison.csv",
        BOARD14_ROOT / "outputs" / "modal" / "guyan_modal_comparison.csv",
    ),
    (
        "板块14_运行入口",
        "legacy_audit/run_guyan_impact.m",
        BOARD14_ROOT / "code" / "run_guyan_impact.m",
    ),
    (
        "早期Guyan独立审计",
        "legacy_audit/audit_guyan_projection.m",
        PROJECT_ROOT / "need-help" / "audit_guyan_projection.m",
    ),
    (
        "小论文公式源",
        "theory/manuscript_0824.tex",
        PAPER_ROOT / "manuscript_0824.tex",
    ),
    (
        "硕士论文PDF",
        "theory/梁禹手稿.pdf",
        THESIS_PATH,
    ),
    (
        "硕士论文精读笔记",
        "theory/Liang2025_实时混合试验缩聚与稳定性.md",
        PROJECT_ROOT / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md",
    ),
    (
        "45项总索引",
        "project_contract/全部对象总索引.csv",
        PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv",
    ),
    (
        "326项保护源清单",
        "project_contract/源文件冻结清单.csv",
        PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结清单.csv",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def main() -> None:
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_resolved = CANDIDATE_ROOT.resolve()

    rows: list[dict[str, object]] = []
    for role, relative_destination, source in SOURCES:
        source = source.resolve(strict=True)
        if source.is_dir():
            raise IsADirectoryError(source)
        if candidate_resolved == source or candidate_resolved in source.parents:
            raise RuntimeError(f"输入源不得位于板块17候选目录内: {source}")

        destination = (INPUT_ROOT / relative_destination).resolve()
        if INPUT_ROOT.resolve() not in destination.parents:
            raise RuntimeError(f"复制目标越界: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)

        source_hash = sha256(source)
        if destination.exists():
            destination_hash_before = sha256(destination)
            if destination_hash_before != source_hash:
                raise RuntimeError(
                    f"拒绝覆盖哈希不同的既有输入副本: {destination}\n"
                    f"source={source_hash}\nexisting={destination_hash_before}"
                )
            action = "REUSED_MATCHING_COPY"
        else:
            shutil.copy2(source, destination)
            action = "COPIED"

        destination_hash = sha256(destination)
        if destination_hash != source_hash:
            raise RuntimeError(f"复制后哈希不一致: {source} -> {destination}")

        source_stat = source.stat()
        destination_stat = destination.stat()
        rows.append(
            {
                "role": role,
                "source_path": str(source),
                "copied_relative_path": destination.relative_to(CANDIDATE_ROOT).as_posix(),
                "source_size_bytes": source_stat.st_size,
                "copy_size_bytes": destination_stat.st_size,
                "source_mtime_utc": datetime.fromtimestamp(
                    source_stat.st_mtime, tz=timezone.utc
                ).isoformat(),
                "source_sha256": source_hash,
                "copy_sha256": destination_hash,
                "status": "MATCH",
                "action": action,
            }
        )

    manifest_path = INPUT_ROOT / "input_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(CANDIDATE_ROOT),
        "source_count": len(rows),
        "match_count": sum(row["status"] == "MATCH" for row in rows),
        "all_match": all(row["status"] == "MATCH" for row in rows),
        "manifest_sha256": sha256(manifest_path),
    }
    summary_path = INPUT_ROOT / "input_freeze_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    log_path = LOG_ROOT / "freeze_board17_inputs.log"
    log_path.write_text(
        "\n".join(
            [
                f"generated_at_utc={summary['generated_at_utc']}",
                f"source_count={summary['source_count']}",
                f"match_count={summary['match_count']}",
                f"all_match={summary['all_match']}",
                f"manifest_sha256={summary['manifest_sha256']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_match"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
