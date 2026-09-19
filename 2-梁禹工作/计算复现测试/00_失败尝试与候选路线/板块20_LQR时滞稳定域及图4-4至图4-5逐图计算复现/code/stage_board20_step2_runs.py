from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
INPUT_ROOT = BOARD_ROOT / "input"
TMP_ROOT = BOARD_ROOT / "tmp" / "step2_runs"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step2_runs"
LOG_ROOT = BOARD_ROOT / "logs" / "step2_runs"
CONTRACT_CSV = BOARD_ROOT / "outputs" / "step2_run_contract.csv"
CONTRACT_JSON = BOARD_ROOT / "outputs" / "step2_run_contract.json"
STAGE_MANIFEST_CSV = BOARD_ROOT / "outputs" / "step2_stage_manifest.csv"
STAGE_SUMMARY_JSON = BOARD_ROOT / "outputs" / "step2_stage_summary.json"
INPUT_MANIFEST_CSV = INPUT_ROOT / "input_manifest.csv"

HELPER_RELATIVE = Path(
    "historical_upstream/新物理子结构方案/fcn_newmark_beta_const.m"
)

DIVISION1_UPSTREAM = [
    Path("historical_upstream/新结构稳定/New_Full.m"),
    Path("historical_upstream/新结构稳定/New_Ps2.m"),
    Path("historical_upstream/新结构稳定/New_Ns2.m"),
]
DIVISION2_UPSTREAM = [
    Path("historical_stability_route/稳定域/New_Full.m"),
    Path("historical_stability_route/稳定域/New_Ps3.m"),
    Path("historical_stability_route/稳定域/New_Ns3.m"),
]

ROUTES: list[dict[str, Any]] = [
    {
        "route_id": "main_ori_div1",
        "declared_method": "Original",
        "declared_division": "第一类子结构划分",
        "actual_code_identity": "原结构LQR2命名脚本；无LQR；零时滞单点",
        "upstream_selection_basis": "后缀2与6x6物理矩阵合同；两版New_Full数值仍不唯一",
        "upstream_identity_status": "CANDIDATE_NOT_UNIQUE_NEW_FULL",
        "dependency_closure_status": "CLOSED_WITH_AUTHOR_EXTERNAL_NEWMARK_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_ori_LQR2.mlx"
        ),
        "upstream": DIVISION1_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": False,
        "expected_scan_point_count": 1,
        "expected_stab_shape": [20, 20],
        "expected_written_regions": [[1, 1, 1, 1]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
    {
        "route_id": "main_ori_div2",
        "declared_method": "Original",
        "declared_division": "第二类子结构划分",
        "actual_code_identity": "原结构LQR3命名脚本；实际为5维Guyan式路线",
        "upstream_selection_basis": "后缀3与稳定域目录；代码也可读取Ps2前六项，非唯一",
        "upstream_identity_status": "CANDIDATE_BY_SUFFIX_AND_DIRECTORY_NOT_UNIQUE",
        "dependency_closure_status": "CLOSED_WITH_AUTHOR_EXTERNAL_NEWMARK_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_ori_LQR3.mlx"
        ),
        "upstream": DIVISION2_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": True,
        "expected_scan_point_count": 1517,
        "expected_stab_shape": [26, 67],
        "expected_written_regions": [
            [1, 21, 1, 21],
            [1, 26, 22, 41],
            [1, 26, 42, 61],
            [1, 6, 62, 67],
        ],
        "source_save_call_count": 4,
        "author_save_targets": ["stab_guyan_lqr.mat"],
    },
    {
        "route_id": "main_guyan_div1",
        "declared_method": "Guyan",
        "declared_division": "第一类子结构划分",
        "actual_code_identity": "Guyan-LQR2命名脚本；无LQR；21x21双时滞扫描",
        "upstream_selection_basis": "后缀2与新结构稳定父目录；代码不能唯一排除Ps3",
        "upstream_identity_status": "CANDIDATE_BY_SUFFIX_AND_DIRECTORY_NOT_UNIQUE",
        "dependency_closure_status": "CLOSED_WITH_AUTHOR_EXTERNAL_NEWMARK_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_guyan_LQR2.mlx"
        ),
        "upstream": DIVISION1_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": False,
        "expected_scan_point_count": 441,
        "expected_stab_shape": [21, 21],
        "expected_written_regions": [[1, 21, 1, 21]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
    {
        "route_id": "main_guyan_div2",
        "declared_method": "Guyan",
        "declared_division": "第二类子结构划分",
        "actual_code_identity": "Guyan-LQR3命名脚本；5维Guyan式路线",
        "upstream_selection_basis": "后缀3与稳定域目录；代码也可读取Ps2前六项，非唯一",
        "upstream_identity_status": "CANDIDATE_BY_SUFFIX_AND_DIRECTORY_NOT_UNIQUE",
        "dependency_closure_status": "CLOSED_WITH_AUTHOR_EXTERNAL_NEWMARK_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_guyan_LQR3.mlx"
        ),
        "upstream": DIVISION2_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": True,
        "expected_scan_point_count": 1517,
        "expected_stab_shape": [26, 67],
        "expected_written_regions": [
            [1, 21, 1, 21],
            [1, 26, 22, 41],
            [1, 26, 42, 61],
            [1, 6, 62, 67],
        ],
        "source_save_call_count": 4,
        "author_save_targets": ["stab_guyan_lqr.mat"],
    },
    {
        "route_id": "main_cb_div1",
        "declared_method": "Craig--Bampton",
        "declared_division": "第一类子结构划分",
        "actual_code_identity": "CB-LQR2命名脚本；无LQR；与CB-LQR3字节相同",
        "upstream_selection_basis": "后缀2自然上游；不注入隐藏MRren工作区",
        "upstream_identity_status": "CANDIDATE_BY_SUFFIX_AND_DIRECTORY_NOT_UNIQUE",
        "dependency_closure_status": "EXPECTED_FAIL_HIDDEN_MRREN_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_cb_LQR2.mlx"
        ),
        "upstream": DIVISION1_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": False,
        "expected_scan_point_count": 441,
        "expected_stab_shape": [21, 21],
        "expected_written_regions": [[1, 21, 1, 21]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
    {
        "route_id": "main_cb_div2",
        "declared_method": "Craig--Bampton",
        "declared_division": "第二类子结构划分",
        "actual_code_identity": "CB-LQR3命名脚本；与CB-LQR2字节相同",
        "upstream_selection_basis": "后缀3自然上游；不注入隐藏MRren工作区",
        "upstream_identity_status": "CANDIDATE_BY_SUFFIX_AND_DIRECTORY_NOT_UNIQUE",
        "dependency_closure_status": "EXPECTED_FAIL_HIDDEN_MRREN_DEPENDENCY",
        "candidate": Path(
            "historical_stability_route/稳定域/luxvjie_cb_LQR3.mlx"
        ),
        "upstream": DIVISION2_UPSTREAM,
        "dependency": HELPER_RELATIVE,
        "source_contains_dlqr": False,
        "expected_scan_point_count": 441,
        "expected_stab_shape": [21, 21],
        "expected_written_regions": [[1, 21, 1, 21]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
    {
        "route_id": "energy_guyan_div1",
        "declared_method": "Guyan（能量目录冲突Q/R）",
        "declared_division": "第一类子结构划分",
        "actual_code_identity": "能量目录Guyan-LQR2；单轴16点；上游变量合同不闭合",
        "upstream_selection_basis": "同目录PDmonicanshu2.m，不加载任何历史MAT或他路工作区",
        "upstream_identity_status": "ONLY_NATURAL_SAME_DIRECTORY_CHAIN",
        "dependency_closure_status": "NO_DIMENSIONALLY_CLOSED_CHAIN",
        "candidate": Path("alternative_lqr_route/能量指标/luxvjie_guyan_LQR2.mlx"),
        "upstream": [Path("alternative_lqr_route/能量指标/PDmonicanshu2.m")],
        "dependency": None,
        "source_contains_dlqr": True,
        "expected_scan_point_count": 16,
        "expected_stab_shape": [20, 20],
        "expected_written_regions": [[1, 16, 1, 1]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
    {
        "route_id": "energy_guyan_div2",
        "declared_method": "Guyan（能量目录冲突Q/R）",
        "declared_division": "第二类子结构划分",
        "actual_code_identity": "能量目录Guyan-LQR3；单轴16点；LQR项未进入最终G",
        "upstream_selection_basis": "同目录PDmonicanshu3.m，不加载任何历史MAT或他路工作区",
        "upstream_identity_status": "ONLY_NATURAL_SAME_DIRECTORY_CHAIN",
        "dependency_closure_status": "NO_COMPLETE_VARIABLE_CHAIN",
        "candidate": Path("alternative_lqr_route/能量指标/luxvjie_guyan_LQR3.mlx"),
        "upstream": [Path("alternative_lqr_route/能量指标/PDmonicanshu3.m")],
        "dependency": None,
        "source_contains_dlqr": True,
        "expected_scan_point_count": 16,
        "expected_stab_shape": [20, 20],
        "expected_written_regions": [[1, 1, 1, 16]],
        "source_save_call_count": 0,
        "author_save_targets": [],
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_frozen_baseline() -> dict[str, dict[str, str]]:
    if not INPUT_MANIFEST_CSV.is_file():
        raise FileNotFoundError(f"缺少步骤1冻结清单：{INPUT_MANIFEST_CSV}")
    with INPUT_MANIFEST_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    baseline: dict[str, dict[str, str]] = {}
    for row in rows:
        relative = Path(row["frozen_relative_path"]).as_posix()
        if relative in baseline:
            raise RuntimeError(f"冻结清单相对路径重复：{relative}")
        baseline[relative] = row
    return baseline


def output_paths(replicate: str) -> tuple[Path, Path, Path, Path]:
    if replicate == "rep01":
        return CONTRACT_CSV, CONTRACT_JSON, STAGE_MANIFEST_CSV, STAGE_SUMMARY_JSON
    suffix = f"_{replicate}"
    return (
        BOARD_ROOT / "outputs" / f"step2_run_contract{suffix}.csv",
        BOARD_ROOT / "outputs" / f"step2_run_contract{suffix}.json",
        BOARD_ROOT / "outputs" / f"step2_stage_manifest{suffix}.csv",
        BOARD_ROOT / "outputs" / f"step2_stage_summary{suffix}.json",
    )


def stage_file(
    *,
    route_id: str,
    replicate: str,
    kind: str,
    order: int,
    source_relative: Path,
    destination: Path,
    frozen_baseline: dict[str, dict[str, str]],
) -> dict[str, Any]:
    source = (INPUT_ROOT / source_relative).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"缺少冻结输入：{source}")
    try:
        source.relative_to(INPUT_ROOT.resolve())
    except ValueError as error:
        raise RuntimeError(f"源文件不在冻结输入内：{source}") from error
    baseline_key = source_relative.as_posix()
    if baseline_key not in frozen_baseline:
        raise RuntimeError(f"文件未登记在步骤1冻结清单：{baseline_key}")
    baseline_row = frozen_baseline[baseline_key]
    source_hash = sha256_file(source)
    baseline_hash = baseline_row["frozen_sha256"].upper()
    if source_hash != baseline_hash:
        raise RuntimeError(
            f"冻结输入已漂移：{baseline_key} "
            f"expected={baseline_hash} actual={source_hash}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(f"分发目标已存在，拒绝覆盖：{destination}")
    shutil.copy2(source, destination)
    staged_hash = sha256_file(destination)
    if source.stat().st_size != destination.stat().st_size or source_hash != staged_hash:
        raise RuntimeError(f"分发哈希不一致：{source} -> {destination}")
    return {
        "route_id": route_id,
        "execution_artifact": "ORIGINAL_MLX",
        "replicate": replicate,
        "kind": kind,
        "execution_order": order,
        "source_relative_path": source_relative.as_posix(),
        "source_absolute_path": str(source),
        "staged_absolute_path": str(destination.resolve()),
        "size_bytes": source.stat().st_size,
        "source_sha256": source_hash,
        "frozen_manifest_item_id": baseline_row["item_id"],
        "frozen_manifest_sha256": baseline_hash,
        "staged_sha256": staged_hash,
        "status": "MATCH",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将板块20原始MLX路线分发到全新、不可覆盖的重复运行目录。"
    )
    parser.add_argument(
        "--replicate",
        default="rep01",
        help="重复运行编号，格式如rep02；已有目录一律拒绝覆盖。",
    )
    parser.add_argument(
        "--route",
        action="append",
        dest="routes",
        help="只分发指定route_id；可重复给出。默认八条全部分发。",
    )
    args = parser.parse_args()
    if re.fullmatch(r"rep\d{2,}", args.replicate) is None:
        parser.error("--replicate必须符合rep02这类格式")
    known = {route["route_id"] for route in ROUTES}
    if args.routes:
        unknown = sorted(set(args.routes) - known)
        if unknown:
            parser.error(f"未知route_id: {', '.join(unknown)}")
        if len(args.routes) != len(set(args.routes)):
            parser.error("--route不得重复")
    return args


def main() -> int:
    args = parse_args()
    replicate = args.replicate
    selected_routes = [
        route for route in ROUTES
        if not args.routes or route["route_id"] in set(args.routes)
    ]
    frozen_baseline = load_frozen_baseline()
    instrumentation_paths = {
        "stager": SCRIPT,
        "matlab_runner": SCRIPT.parent / "run_one_board20_candidate.m",
        "outer_executor": SCRIPT.parent / "execute_board20_step2_route.py",
    }
    for name, path in instrumentation_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"缺少运行仪器代码 {name}：{path}")
    instrumentation = {
        name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
        for name, path in instrumentation_paths.items()
    }
    contract_csv, contract_json, stage_manifest_csv, stage_summary_json = output_paths(
        replicate
    )

    for path in (contract_csv, contract_json, stage_manifest_csv, stage_summary_json):
        if path.exists():
            raise FileExistsError(f"重复运行全局工件已存在，拒绝覆盖：{path}")

    # 先完成全局只读预检，避免中途失败后留下半分分发包。
    for route in selected_routes:
        run_relative = Path(route["route_id"]) / "original_mlx" / replicate
        for target in (
            TMP_ROOT / run_relative,
            OUTPUT_ROOT / run_relative,
            LOG_ROOT / run_relative,
        ):
            if target.exists():
                raise FileExistsError(f"路线目录已存在，拒绝复用：{target}")
        relatives = list(route["upstream"]) + [route["candidate"]]
        if route["dependency"] is not None:
            relatives.append(route["dependency"])
        for relative in relatives:
            source = INPUT_ROOT / relative
            if not source.is_file():
                raise FileNotFoundError(f"缺少冻结输入：{source}")
            key = relative.as_posix()
            if key not in frozen_baseline:
                raise RuntimeError(f"文件未登记在步骤1冻结清单：{key}")
            actual = sha256_file(source)
            expected = frozen_baseline[key]["frozen_sha256"].upper()
            if actual != expected:
                raise RuntimeError(f"冻结输入已漂移：{key}")

    for root in (TMP_ROOT, OUTPUT_ROOT, LOG_ROOT):
        root.mkdir(parents=True, exist_ok=True)

    stage_rows: list[dict[str, Any]] = []
    contract_rows: list[dict[str, Any]] = []
    config_paths: list[str] = []

    for route in selected_routes:
        route_id = route["route_id"]
        run_relative = Path(route_id) / "original_mlx" / replicate
        work_dir = TMP_ROOT / run_relative / "work"
        run_output_dir = OUTPUT_ROOT / run_relative
        run_log_dir = LOG_ROOT / run_relative
        metadata_dir = run_output_dir / "metadata"
        workspace_dir = run_output_dir / "workspace"
        scientific_dir = run_output_dir / "scientific"
        author_saved_dir = run_output_dir / "author_saved"
        dependency_dir = work_dir / "dependencies"

        for path in (
            work_dir,
            metadata_dir,
            workspace_dir,
            scientific_dir,
            author_saved_dir,
            run_log_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        staged_upstream: list[str] = []
        order = 1
        for upstream_relative in route["upstream"]:
            staged = work_dir / upstream_relative.name
            row = stage_file(
                route_id=route_id,
                replicate=replicate,
                kind="upstream",
                order=order,
                source_relative=upstream_relative,
                destination=staged,
                frozen_baseline=frozen_baseline,
            )
            stage_rows.append(row)
            staged_upstream.append(row["staged_absolute_path"])
            order += 1

        dependency_directories: list[str] = []
        dependency_relative = route["dependency"]
        if dependency_relative is not None:
            staged_dependency = dependency_dir / dependency_relative.name
            row = stage_file(
                route_id=route_id,
                replicate=replicate,
                kind="author_external_dependency",
                order=order,
                source_relative=dependency_relative,
                destination=staged_dependency,
                frozen_baseline=frozen_baseline,
            )
            stage_rows.append(row)
            dependency_directories.append(str(dependency_dir.resolve()))
            order += 1

        candidate_relative = route["candidate"]
        staged_candidate = work_dir / candidate_relative.name
        candidate_row = stage_file(
            route_id=route_id,
            replicate=replicate,
            kind="candidate_original_mlx",
            order=order,
            source_relative=candidate_relative,
            destination=staged_candidate,
            frozen_baseline=frozen_baseline,
        )
        stage_rows.append(candidate_row)

        config_path = metadata_dir / "run_config.json"
        config_hash_path = metadata_dir / "run_config.sha256"
        config = {
            "schema": "board20_original_mlx_run_config_v2",
            "created_at": datetime.now().astimezone().isoformat(),
            "route_id": route_id,
            "declared_method": route["declared_method"],
            "declared_division": route["declared_division"],
            "actual_code_identity": route["actual_code_identity"],
            "upstream_selection_basis": route["upstream_selection_basis"],
            "upstream_identity_status": route["upstream_identity_status"],
            "dependency_closure_status": route["dependency_closure_status"],
            "execution_artifact": "ORIGINAL_MLX",
            "replicate": replicate,
            "dependency_mode": (
                "AUTHOR_FROZEN_EXTERNAL_DEPENDENCY"
                if dependency_directories
                else "NO_EXTERNAL_DEPENDENCY"
            ),
            "work_dir": str(work_dir.resolve()),
            "run_output_dir": str(run_output_dir.resolve()),
            "run_log_dir": str(run_log_dir.resolve()),
            "upstream_files": staged_upstream,
            "dependency_directories": dependency_directories,
            "candidate_mlx": candidate_row["staged_absolute_path"],
            "candidate_sha256": candidate_row["source_sha256"],
            "file_contracts": [
                {
                    "kind": row["kind"],
                    "execution_order": row["execution_order"],
                    "path": row["staged_absolute_path"],
                    "expected_sha256": row["frozen_manifest_sha256"],
                    "frozen_manifest_item_id": row["frozen_manifest_item_id"],
                }
                for row in stage_rows
                if row["route_id"] == route_id and row["replicate"] == replicate
            ],
            "allowed_work_files": [
                str(Path(row["staged_absolute_path"]).resolve().relative_to(work_dir.resolve())).replace("\\", "/")
                for row in stage_rows
                if row["route_id"] == route_id and row["replicate"] == replicate
            ],
            "source_contains_dlqr": route["source_contains_dlqr"],
            "expected_scan_point_count": route["expected_scan_point_count"],
            "expected_stab_shape": route["expected_stab_shape"],
            "expected_written_regions": route["expected_written_regions"],
            "source_save_call_count": route["source_save_call_count"],
            "enable_profile": False,
            "runtime_call_evidence": "CLEAN_BASE_WORKSPACE_VARIABLE_K_lqr",
            "actual_scan_point_count_method": "NOT_MEASURED_PROFILE_DISABLED",
            "expected_stab_required_on_execution_success": True,
            "author_save_targets": route["author_save_targets"],
            "status_json": str((metadata_dir / "run_status.json").resolve()),
            "diary_file": str((run_log_dir / "matlab_diary.log").resolve()),
            "workspace_success": str(
                (workspace_dir / "workspace_complete.mat").resolve()
            ),
            "workspace_failure": str(
                (workspace_dir / "workspace_failure.mat").resolve()
            ),
            "scientific_arrays": str(
                (scientific_dir / "scientific_arrays.mat").resolve()
            ),
            "raw_stab": str((scientific_dir / "raw_stab.mat").resolve()),
            "profile_info": str((metadata_dir / "profile_info.mat").resolve()),
            "author_saved_dir": str(author_saved_dir.resolve()),
            "process_exit_json": str((metadata_dir / "process_exit.json").resolve()),
            "command_txt": str((run_log_dir / "matlab_command.txt").resolve()),
            "shell_log": str((run_log_dir / "shell_stdout_stderr.log").resolve()),
            "config_hash_file": str(config_hash_path.resolve()),
            "instrumentation": instrumentation,
        }
        write_json(config_path, config)
        config_hash = sha256_file(config_path)
        config_hash_path.write_text(config_hash + "\n", encoding="ascii")
        config_paths.append(str(config_path.resolve()))

        contract_rows.append(
            {
                "route_id": route_id,
                "declared_method": route["declared_method"],
                "declared_division": route["declared_division"],
                "actual_code_identity": route["actual_code_identity"],
                "upstream_selection_basis": route["upstream_selection_basis"],
                "upstream_identity_status": route["upstream_identity_status"],
                "dependency_closure_status": route["dependency_closure_status"],
                "execution_artifact": "ORIGINAL_MLX",
                "replicate": replicate,
                "dependency_mode": config["dependency_mode"],
                "upstream_count": len(staged_upstream),
                "candidate_filename": staged_candidate.name,
                "candidate_sha256": candidate_row["source_sha256"],
                "source_contains_dlqr": route["source_contains_dlqr"],
                "expected_scan_point_count": route["expected_scan_point_count"],
                "expected_stab_shape": "x".join(
                    str(value) for value in route["expected_stab_shape"]
                ),
                "source_save_call_count": route["source_save_call_count"],
                "config_path": str(config_path.resolve()),
                "run_config_sha256": config_hash,
                "run_config_hash_path": str(config_hash_path.resolve()),
                "matlab_runner_sha256": instrumentation["matlab_runner"]["sha256"],
                "outer_executor_sha256": instrumentation["outer_executor"]["sha256"],
                "stager_sha256": instrumentation["stager"]["sha256"],
                "initial_status": "STAGED_NOT_RUN",
            }
        )

    with contract_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(contract_rows[0].keys()))
        writer.writeheader()
        writer.writerows(contract_rows)
    write_json(
        contract_json,
        {
            "schema": "board20_step2_run_contract_v2",
            "created_at": datetime.now().astimezone().isoformat(),
            "route_count": len(contract_rows),
            "routes": contract_rows,
        },
    )

    with stage_manifest_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stage_rows[0].keys()))
        writer.writeheader()
        writer.writerows(stage_rows)
    summary = {
        "schema": "board20_step2_stage_summary_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "route_count": len(contract_rows),
        "staged_file_count": len(stage_rows),
        "match_count": sum(row["status"] == "MATCH" for row in stage_rows),
        "total_bytes": sum(int(row["size_bytes"]) for row in stage_rows),
        "unique_staged_paths": len({row["staged_absolute_path"] for row in stage_rows}),
        "config_paths": config_paths,
        "status": "PASS",
    }
    summary["replicate"] = replicate
    summary["input_manifest_path"] = str(INPUT_MANIFEST_CSV.resolve())
    summary["input_manifest_sha256"] = sha256_file(INPUT_MANIFEST_CSV)
    write_json(stage_summary_json, summary)

    print(
        "BOARD20_STEP2_STAGE_PASS "
        f"routes={summary['route_count']} "
        f"files={summary['match_count']}/{summary['staged_file_count']} "
        f"bytes={summary['total_bytes']}"
    )
    print(f"CONTRACT={contract_csv}")
    print(f"MANIFEST={stage_manifest_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
