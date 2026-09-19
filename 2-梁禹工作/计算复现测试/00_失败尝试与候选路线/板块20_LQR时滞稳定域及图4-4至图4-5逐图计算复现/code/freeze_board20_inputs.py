from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
TEST_ROOT = PROJECT_ROOT / "test"
RHTS_ROOT = PROJECT_ROOT.parent
INNER_ROOT = PROJECT_ROOT / "liangyustability-master"
FIGURE4_ROOT = PROJECT_ROOT / "figure" / "第4章_缩聚对试验稳定性的影响"
BOARD17_ROOT = (
    TEST_ROOT
    / "00_失败尝试与候选路线"
    / "板块17_两类划分与缩聚候选路线"
)

INPUT_ROOT = BOARD_ROOT / "input"
OUTPUT_ROOT = BOARD_ROOT / "outputs"
MANIFEST_PATH = INPUT_ROOT / "input_manifest.csv"
SUMMARY_PATH = OUTPUT_ROOT / "input_freeze_summary.json"

THESIS_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
MANUSCRIPT_SHA256 = "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def relative_label(path: Path) -> str:
    for label, root in (
        ("project", PROJECT_ROOT),
        ("rths", RHTS_ROOT),
    ):
        try:
            return f"{label}/{path.relative_to(root).as_posix()}"
        except ValueError:
            pass
    return path.as_posix()


items: list[dict[str, object]] = []
destinations: set[Path] = set()


def add_file(
    category: str,
    role: str,
    source: Path,
    frozen_relative: Path,
    *,
    live_change_policy: str = "immutable",
) -> None:
    source = source.resolve()
    destination = (INPUT_ROOT / frozen_relative).resolve()
    if destination in destinations:
        raise RuntimeError(f"冻结目标重复：{destination}")
    if is_relative_to(source, BOARD_ROOT):
        raise RuntimeError(f"源文件错误地位于板块20目录内：{source}")
    destinations.add(destination)
    items.append(
        {
            "category": category,
            "role": role,
            "source": source,
            "destination": destination,
            "frozen_relative": frozen_relative.as_posix(),
            "live_change_policy": live_change_policy,
        }
    )


def add_tree(
    category: str,
    role_prefix: str,
    source_root: Path,
    frozen_root: Path,
    *,
    suffixes: set[str] | None = None,
) -> None:
    if not source_root.is_dir():
        raise FileNotFoundError(f"缺少候选目录：{source_root}")
    for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
        if suffixes is not None and source.suffix.lower() not in suffixes:
            continue
        rel = source.relative_to(source_root)
        add_file(
            category,
            f"{role_prefix}:{rel.as_posix()}",
            source,
            frozen_root / rel,
        )


def build_source_catalogue() -> None:
    add_file(
        "theory",
        "梁禹硕士论文",
        RHTS_ROOT / "梁禹手稿.pdf",
        Path("theory/梁禹手稿.pdf"),
    )
    add_file(
        "theory",
        "小论文公式源",
        RHTS_ROOT / "260817" / "manuscript_0824.tex",
        Path("theory/manuscript_0824.tex"),
    )
    add_file(
        "theory",
        "梁禹论文精读笔记_板块20前快照",
        PROJECT_ROOT / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md",
        Path("theory/Liang2025_实时混合试验缩聚与稳定性_板块20前快照.md"),
        live_change_policy="authorized_evolution",
    )

    add_file(
        "project_contract",
        "全部对象总索引_板块20前快照",
        TEST_ROOT / "00_总索引与复现规则" / "全部对象总索引.csv",
        Path("project_contract/全部对象总索引_板块20前快照.csv"),
        live_change_policy="authorized_evolution",
    )
    add_file(
        "project_contract",
        "板块15源文件冻结清单",
        TEST_ROOT / "00_总索引与复现规则" / "源文件冻结清单.csv",
        Path("project_contract/板块15_源文件冻结清单.csv"),
    )
    add_file(
        "project_contract",
        "板块15源文件冻结复核",
        TEST_ROOT / "00_总索引与复现规则" / "源文件冻结复核.csv",
        Path("project_contract/板块15_源文件冻结复核.csv"),
    )
    add_file(
        "project_contract",
        "test说明_板块20前快照",
        TEST_ROOT / "README.md",
        Path("project_contract/test_README_板块20前快照.md"),
        live_change_policy="authorized_evolution",
    )
    acceptance_record = TEST_ROOT / "00_总索引与复现规则" / "验收记录.md"
    if acceptance_record.is_file():
        add_file(
            "project_contract",
            "总体验收记录_板块20前快照",
            acceptance_record,
            Path("project_contract/验收记录_板块20前快照.md"),
            live_change_policy="authorized_evolution",
        )

    stability_root = INNER_ROOT / "新结构稳定" / "稳定域"
    add_tree(
        "historical_stability_route",
        "稳定域目录原件",
        stability_root,
        Path("historical_stability_route/稳定域"),
    )

    new_structure_root = INNER_ROOT / "新结构稳定"
    for name in (
        "New_Full.m",
        "New_Ns2.m",
        "New_Ps2.m",
        "New_stability_luxvjie_guyan.mlx",
        "New_stability_luxvjie4.mlx",
    ):
        add_file(
            "historical_upstream",
            f"新结构稳定上游:{name}",
            new_structure_root / name,
            Path("historical_upstream/新结构稳定") / name,
        )

    plotting_root = new_structure_root / "绘图"
    for name in (
        "huitu_2.m",
        "lqr_2.mat",
        "lqr_3.mat",
        "origin_lqr_2.mat",
        "origin_lqr_3.mat",
        "guyan_lqr_2.mat",
        "guyan_lqr_3.mat",
        "CB_lqr_2.mat",
        "CB_lqr_3.mat",
        "lvxvjie_guyan_2.slx",
        "lvxvjie_guyan.slx",
        "PDmonicanshu.m",
    ):
        add_file(
            "historical_plotting",
            f"作者绘图目录:{name}",
            plotting_root / name,
            Path("historical_plotting/作者绘图目录") / name,
        )

    energy_root = INNER_ROOT / "能量指标"
    for name in (
        "luxvjie_ori_LQR2.mlx",
        "luxvjie_ori_LQR3.mlx",
        "luxvjie_guyan_LQR2.mlx",
        "luxvjie_guyan_LQR3.mlx",
        "luxvjie_cb_LQR2.mlx",
        "luxvjie_cb_LQR3.mlx",
        "PDmonicanshu2.m",
        "PDmonicanshu3.m",
        "stab_3.mat",
    ):
        add_file(
            "alternative_lqr_route",
            f"能量目录冲突候选:{name}",
            energy_root / name,
            Path("alternative_lqr_route/能量指标") / name,
        )

    for name in (
        "Wending3.mlx",
        "Wending4.mlx",
        "Wending5_29.mlx",
        "Wending6_suoju.mlx",
        "Wending7.mlx",
        "Wending8.mlx",
    ):
        source = INNER_ROOT / name
        if source.is_file():
            add_file(
                "legacy_stability_candidate",
                f"早期Wending候选:{name}",
                source,
                Path("legacy_stability_candidate/Wending") / name,
            )

    legacy_suffixes = {".m", ".mlx", ".mat", ".slx", ".docx"}
    for directory, target in (
        (INNER_ROOT / "稳定性分析", "稳定性分析"),
        (INNER_ROOT / "稳定性分析_matlab辅助代码", "稳定性分析_matlab辅助代码"),
        (INNER_ROOT / "simulink模型修改", "simulink模型修改"),
        (new_structure_root / "鲁旭杰方法复现", "鲁旭杰方法复现"),
    ):
        add_tree(
            "legacy_stability_candidate",
            f"历史稳定候选:{target}",
            directory,
            Path("legacy_stability_candidate") / target,
            suffixes=legacy_suffixes,
        )

    add_tree(
        "plotting_baseline",
        "既有第四章绘图级基线",
        FIGURE4_ROOT,
        Path("plotting_baseline/第4章_缩聚对试验稳定性的影响"),
    )

    board17_files = (
        "code/run_board17_global_routes.m",
        "code/independent_recompute_global_routes.py",
        "input/upstream_u01/reference_model_matlab.mat",
        "outputs/global_routes_matlab.mat",
        "outputs/independent_global_routes_python.mat",
        "outputs/contract_divisions.csv",
        "outputs/contract_dof_membership.csv",
        "outputs/contract_formula_crosswalk.csv",
        "outputs/global_reduced_matrix_entries.csv",
        "outputs/global_recovery_matrices.csv",
        "outputs/global_route_summary.json",
        "outputs/object_adjudication.csv",
        "report/板块17_两类自由度划分与缩聚路线复现报告.md",
        "report/板块17_最终验收记录.md",
        "report/board17_artifact_manifest.csv",
        "report/board17_final_validation_summary.json",
    )
    for rel_text in board17_files:
        rel = Path(rel_text)
        add_file(
            "upstream_board17",
            f"板块17上游:{rel.as_posix()}",
            BOARD17_ROOT / rel,
            Path("upstream_board17") / rel,
        )

    for board_name, relative_paths in {
        "board16": (
            "test/00_上游模型身份证/U01_参考结构参数与15自由度矩阵/report/板块16_最终验收记录.md",
            "test/00_上游模型身份证/U01_参考结构参数与15自由度矩阵/report/board16_artifact_manifest.csv",
        ),
        "board18": (
            "test/00_失败尝试与候选路线/板块18_图3-5至图3-15逐图计算复现/outputs/final_validation/board18_final_validation_summary.json",
            "test/00_失败尝试与候选路线/板块18_图3-5至图3-15逐图计算复现/outputs/board18_artifact_manifest.csv",
        ),
        "board19": (
            "test/00_失败尝试与候选路线/板块19_表3-1至表3-3逐单元格计算复现/outputs/final_validation/board19_final_validation_summary.json",
            "test/00_失败尝试与候选路线/板块19_表3-1至表3-3逐单元格计算复现/outputs/final_validation/board19_artifact_manifest.csv",
        ),
    }.items():
        for rel_text in relative_paths:
            source = PROJECT_ROOT / rel_text
            if source.is_file():
                add_file(
                    "upstream_protection",
                    f"{board_name}保护基线:{Path(rel_text).name}",
                    source,
                    Path("upstream_protection") / board_name / Path(rel_text).name,
                )

    # 步骤2依赖审计补充：稳定域 New_Full.m 调用该作者原函数，
    # 但函数只保存在“新物理子结构方案”，不在稳定域同目录。
    # 放在目录末尾登记，保持首次冻结184项的 item_id 不变。
    add_file(
        "historical_upstream",
        "稳定域New_Full外部依赖:fcn_newmark_beta_const.m",
        INNER_ROOT / "新物理子结构方案" / "fcn_newmark_beta_const.m",
        Path("historical_upstream/新物理子结构方案/fcn_newmark_beta_const.m"),
    )


def freeze() -> tuple[list[dict[str, object]], dict[str, object]]:
    INPUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    previous_by_frozen: dict[str, dict[str, str]] = {}
    if MANIFEST_PATH.is_file():
        with MANIFEST_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
            previous_by_frozen = {
                row["frozen_relative_path"]: row for row in csv.DictReader(stream)
            }
    build_source_catalogue()

    missing = [str(item["source"]) for item in items if not Path(item["source"]).is_file()]
    if missing:
        raise FileNotFoundError("缺少冻结源：\n" + "\n".join(missing))

    rows: list[dict[str, object]] = []
    authorized_evolution_preserved_count = 0
    for index, item in enumerate(items, start=1):
        source = Path(item["source"])
        destination = Path(item["destination"])
        source_hash = sha256_file(source)
        snapshot_source_hash = source_hash
        snapshot_source_size = source.stat().st_size
        snapshot_source_mtime = iso_mtime(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing_hash = sha256_file(destination)
            if existing_hash != source_hash:
                previous = previous_by_frozen.get(str(item["frozen_relative"]))
                authorized = item["live_change_policy"] == "authorized_evolution"
                previous_matches_frozen = (
                    previous is not None
                    and previous.get("frozen_sha256", "").upper() == existing_hash
                    and int(previous.get("frozen_size_bytes", "-1"))
                    == destination.stat().st_size
                )
                if not (authorized and previous_matches_frozen):
                    raise RuntimeError(
                        f"冻结目标已存在且与源不同，拒绝覆盖：{destination}\n"
                        f"source={source_hash}\nfrozen={existing_hash}"
                    )
                snapshot_source_hash = previous["source_sha256"].upper()
                snapshot_source_size = int(previous["source_size_bytes"])
                snapshot_source_mtime = previous["source_mtime_iso"]
                authorized_evolution_preserved_count += 1
        else:
            shutil.copy2(source, destination)
        frozen_hash = sha256_file(destination)
        frozen_size = destination.stat().st_size
        status = (
            "MATCH"
            if snapshot_source_size == frozen_size
            and snapshot_source_hash == frozen_hash
            else "MISMATCH"
        )
        rows.append(
            {
                "item_id": f"B20-{index:04d}",
                "category": item["category"],
                "role": item["role"],
                "source_absolute_path": str(source),
                "source_relative_label": relative_label(source),
                "frozen_relative_path": item["frozen_relative"],
                "source_size_bytes": snapshot_source_size,
                "source_mtime_iso": snapshot_source_mtime,
                "source_sha256": snapshot_source_hash,
                "frozen_size_bytes": frozen_size,
                "frozen_sha256": frozen_hash,
                "live_change_policy": item["live_change_policy"],
                "status": status,
            }
        )

    if any(row["status"] != "MATCH" for row in rows):
        raise RuntimeError("冻结副本存在大小或SHA-256不一致")

    thesis_row = next(row for row in rows if row["role"] == "梁禹硕士论文")
    manuscript_row = next(row for row in rows if row["role"] == "小论文公式源")
    if thesis_row["source_sha256"] != THESIS_SHA256:
        raise RuntimeError(
            f"硕士论文SHA-256漂移：{thesis_row['source_sha256']} != {THESIS_SHA256}"
        )
    if manuscript_row["source_sha256"] != MANUSCRIPT_SHA256:
        raise RuntimeError(
            "manuscript_0824.tex SHA-256漂移："
            f"{manuscript_row['source_sha256']} != {MANUSCRIPT_SHA256}"
        )

    fieldnames = list(rows[0].keys())
    with MANIFEST_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    hash_groups: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        hash_groups[str(row["source_sha256"])].append(str(row["source_relative_label"]))
    duplicate_groups = [
        {"sha256": digest, "count": len(paths), "paths": paths}
        for digest, paths in sorted(hash_groups.items())
        if len(paths) > 1
    ]
    categories = Counter(str(row["category"]) for row in rows)
    summary: dict[str, object] = {
        "schema": "board20_input_freeze_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "board_root": str(BOARD_ROOT),
        "manifest": str(MANIFEST_PATH),
        "source_count": len(rows),
        "match_count": sum(row["status"] == "MATCH" for row in rows),
        "total_bytes": sum(int(row["source_size_bytes"]) for row in rows),
        "category_counts": dict(sorted(categories.items())),
        "duplicate_sha256_group_count": len(duplicate_groups),
        "duplicate_sha256_groups": duplicate_groups,
        "authorized_evolution_preserved_count": authorized_evolution_preserved_count,
        "thesis_sha256": thesis_row["source_sha256"],
        "manuscript_sha256": manuscript_row["source_sha256"],
        "source_inside_board_count": sum(
            is_relative_to(Path(row["source_absolute_path"]), BOARD_ROOT) for row in rows
        ),
        "frozen_destination_unique_count": len(
            {str(row["frozen_relative_path"]) for row in rows}
        ),
        "status": "PASS",
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return rows, summary


def main() -> int:
    rows, summary = freeze()
    print(f"冻结完成：{len(rows)}/{len(rows)} MATCH")
    print(f"总字节数：{summary['total_bytes']}")
    print(f"重复SHA-256组：{summary['duplicate_sha256_group_count']}")
    print(f"清单：{MANIFEST_PATH}")
    print(f"摘要：{SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
