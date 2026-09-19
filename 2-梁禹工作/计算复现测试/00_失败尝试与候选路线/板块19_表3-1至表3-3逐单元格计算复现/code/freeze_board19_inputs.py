"""冻结板块19输入，建立源文件到隔离副本的逐文件SHA-256链。"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def find_project_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "WORKFLOW.md").is_file() and (parent / "test").is_dir():
            return parent
    raise RuntimeError("无法定位包含 WORKFLOW.md 与 test/ 的项目根目录。")


def main() -> None:
    script_path = Path(__file__).resolve()
    project_root = find_project_root(script_path.parent)
    board_root = script_path.parent.parent
    input_root = board_root / "input"

    board17 = project_root / "test" / "00_失败尝试与候选路线" / "板块17_两类划分与缩聚候选路线"
    board18 = project_root / "test" / "00_失败尝试与候选路线" / "板块18_图3-5至图3-15逐图计算复现"
    historical_metrics = project_root / "liangyustability-master" / "新结构稳定" / "精度指标"
    board18_data = board18 / "input" / "plotting_baseline" / "输入数据"

    items: list[tuple[str, Path, Path]] = [
        ("thesis_pdf", project_root.parent / "梁禹手稿.pdf", Path("theory/梁禹手稿.pdf")),
        ("manuscript", project_root.parent / "260817" / "manuscript_0824.tex", Path("theory/manuscript_0824.tex")),
        ("object_index", project_root / "test" / "00_总索引与复现规则" / "全部对象总索引.csv", Path("contracts/全部对象总索引_冻结前.csv")),
        ("historical_metric_script", historical_metrics / "fguyou.m", Path("historical_metrics/fguyou.m")),
        ("historical_metric_script", historical_metrics / "MAC.m", Path("historical_metrics/MAC.m")),
        ("historical_metric_script", historical_metrics / "MAC_full.m", Path("historical_metrics/MAC_full.m")),
        ("historical_metric_script", historical_metrics / "RMSE.m", Path("historical_metrics/RMSE.m")),
        ("historical_metric_script", historical_metrics / "RMSE_full.m", Path("historical_metrics/RMSE_full.m")),
        ("historical_metric_helper", project_root / "liangyustability-master" / "新结构稳定" / "绘图" / "compute_MAC.m", Path("historical_metrics/compute_MAC.m")),
        ("documented_alternative_script", project_root / "liangyustability-master" / "新结构稳定" / "鲁旭杰方法复现" / "phy.m", Path("documented_alternatives/phy.m")),
        ("documented_alternative_script", project_root / "liangyustability-master" / "能量指标" / "PDmonicanshu.m", Path("documented_alternatives/PDmonicanshu_energy.m")),
        ("documented_local_script", project_root / "liangyustability-master" / "能量指标" / "PDmonicanshu2.m", Path("documented_alternatives/PDmonicanshu2.m")),
        ("documented_local_script", project_root / "liangyustability-master" / "能量指标" / "PDmonicanshu3.m", Path("documented_alternatives/PDmonicanshu3.m")),
        ("board17_matlab_route", board17 / "code" / "run_board17_global_routes.m", Path("board17/code/run_board17_global_routes.m")),
        ("board17_python_route", board17 / "code" / "independent_recompute_global_routes.py", Path("board17/code/independent_recompute_global_routes.py")),
        ("board17_primary_mat", board17 / "outputs" / "global_routes_matlab.mat", Path("board17/outputs/global_routes_matlab.mat")),
        ("board17_modal_csv", board17 / "outputs" / "global_modal_frequencies.csv", Path("board17/outputs/global_modal_frequencies.csv")),
        ("board17_modal_csv", board17 / "outputs" / "independent_global_modal_results.csv", Path("board17/outputs/independent_global_modal_results.csv")),
        ("board17_recovery_csv", board17 / "outputs" / "global_recovery_matrices.csv", Path("board17/outputs/global_recovery_matrices.csv")),
        ("board17_matrix_csv", board17 / "outputs" / "global_reduced_matrix_entries.csv", Path("board17/outputs/global_reduced_matrix_entries.csv")),
        ("board17_contract_csv", board17 / "outputs" / "contract_divisions.csv", Path("board17/outputs/contract_divisions.csv")),
        ("board17_local_modal_csv", board17 / "outputs" / "local_pd_modal_values.csv", Path("board17/outputs/local_pd_modal_values.csv")),
        ("board17_local_primary_mat", board17 / "outputs" / "local_pd_reductions.mat", Path("board17/outputs/local_pd_reductions.mat")),
        ("board17_local_summary_csv", board17 / "outputs" / "local_pd_reduction_summary.csv", Path("board17/outputs/local_pd_reduction_summary.csv")),
        ("board18_matlab_route", board18 / "code" / "run_board18_adapted.m", Path("board18/code/run_board18_adapted.m")),
        ("board18_python_route", board18 / "code" / "independent_recompute_board18.py", Path("board18/code/independent_recompute_board18.py")),
        ("board18_generator", board18 / "input" / "current_reproduction_code" / "regenerate_chapter3_data.m", Path("board18/code/regenerate_chapter3_data.m")),
    ]

    response_names = [
        "第一类划分_ElCentro地震响应",
        "第二类划分_ElCentro地震响应",
        "第一类划分_Chirp响应",
        "第二类划分_Chirp响应",
    ]
    for name in response_names:
        for suffix in (".csv", ".mat"):
            items.append(
                (
                    "board18_response",
                    board18_data / f"{name}{suffix}",
                    Path("board18/responses") / f"{name}{suffix}",
                )
            )

    missing = [str(source) for _, source, _ in items if not source.is_file()]
    if missing:
        raise FileNotFoundError("冻结输入缺失：\n" + "\n".join(missing))

    rows: list[dict[str, str | int]] = []
    for role, source, relative_copy in items:
        destination = input_root / relative_copy
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_hash = sha256(source)
        if destination.exists():
            existing_hash = sha256(destination)
            if existing_hash != source_hash:
                raise RuntimeError(f"已有隔离副本与源哈希冲突，拒绝覆盖：{destination}")
        else:
            shutil.copy2(source, destination)
        copy_hash = sha256(destination)
        rows.append(
            {
                "role": role,
                "source_path": str(source.resolve()),
                "copied_relative_path": str(relative_copy).replace("\\", "/"),
                "size_bytes": source.stat().st_size,
                "sha256_source": source_hash,
                "sha256_copy": copy_hash,
                "status": "MATCH" if source_hash == copy_hash else "MISMATCH",
            }
        )

    manifest_path = input_root / "input_manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "board_root": str(board_root),
        "file_count": len(rows),
        "match_count": sum(row["status"] == "MATCH" for row in rows),
        "mismatch_count": sum(row["status"] != "MATCH" for row in rows),
        "manifest_sha256": sha256(manifest_path),
        "status": "PASS" if all(row["status"] == "MATCH" for row in rows) else "FAIL",
    }
    summary_path = input_root / "input_freeze_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
