from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
INPUT_ROOT = BOARD_ROOT / "input"
INPUT_MANIFEST = INPUT_ROOT / "input_manifest.csv"

ROUTE_ID = "alt_guyan_div1_stable_full_ps3"
REPLICATE = "rep01"
RUN_RELATIVE = Path(ROUTE_ID) / "original_mlx" / REPLICATE

WORK_DIR = BOARD_ROOT / "tmp" / "step2_runs" / RUN_RELATIVE / "work"
RUN_OUTPUT_DIR = BOARD_ROOT / "outputs" / "step2_runs" / RUN_RELATIVE
RUN_LOG_DIR = BOARD_ROOT / "logs" / "step2_runs" / RUN_RELATIVE
METADATA_DIR = RUN_OUTPUT_DIR / "metadata"
WORKSPACE_DIR = RUN_OUTPUT_DIR / "workspace"
SCIENTIFIC_DIR = RUN_OUTPUT_DIR / "scientific"
AUTHOR_SAVED_DIR = RUN_OUTPUT_DIR / "author_saved"
DEPENDENCY_DIR = WORK_DIR / "dependencies"

ORIGINAL_STAGER = SCRIPT.parent / "stage_board20_step2_runs.py"
ORIGINAL_STAGE_VALIDATOR = SCRIPT.parent / "validate_board20_step2_stage.py"
MATLAB_RUNNER = SCRIPT.parent / "run_one_board20_candidate.m"
OUTER_EXECUTOR = SCRIPT.parent / "execute_board20_step2_route.py"

EXPECTED_PROTECTED_HASHES = {
    ORIGINAL_STAGER: "918C786BD8E1A1FBFB9A9B156B30A45A90D4207EB56F1509C2D29F3F08943FD7",
    ORIGINAL_STAGE_VALIDATOR: "7F31B862D8614536AFC4599C718F09868F925A333D0FD3C65A1C3C73AD435C22",
    MATLAB_RUNNER: "76682306E224E5C02B6EFC6C3D2FD4B69048C7CBF58A9337A7378B5A823E6D27",
    OUTER_EXECUTOR: "B5B31D2C72643CDCE24D85D4745C924BE3CFF1A47D6839EBA76FB7206420E604",
}

FILES: tuple[dict[str, Any], ...] = (
    {
        "item_id": "B20-0028",
        "kind": "upstream",
        "execution_order": 1,
        "frozen_relative_path": "historical_stability_route/稳定域/New_Full.m",
        "destination_relative_path": "New_Full.m",
    },
    {
        "item_id": "B20-0031",
        "kind": "upstream",
        "execution_order": 2,
        "frozen_relative_path": "historical_stability_route/稳定域/New_Ps3.m",
        "destination_relative_path": "New_Ps3.m",
    },
    {
        "item_id": "B20-0185",
        "kind": "author_external_dependency",
        "execution_order": 3,
        "frozen_relative_path": (
            "historical_upstream/新物理子结构方案/fcn_newmark_beta_const.m"
        ),
        "destination_relative_path": "dependencies/fcn_newmark_beta_const.m",
    },
    {
        "item_id": "B20-0018",
        "kind": "candidate_original_mlx",
        "execution_order": 4,
        "frozen_relative_path": (
            "historical_stability_route/稳定域/luxvjie_guyan_LQR2.mlx"
        ),
        "destination_relative_path": "luxvjie_guyan_LQR2.mlx",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_manifest() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_id: dict[str, dict[str, str]] = {}
    by_path: dict[str, dict[str, str]] = {}
    for row in rows:
        item_id = row["item_id"]
        frozen_path = row["frozen_relative_path"].replace("\\", "/")
        if item_id in by_id or frozen_path in by_path:
            raise RuntimeError("冻结清单中存在重复item_id或路径")
        by_id[item_id] = row
        by_path[frozen_path] = row
    return by_id, by_path


def assert_all_targets_absent() -> None:
    roots = (WORK_DIR.parent, RUN_OUTPUT_DIR, RUN_LOG_DIR)
    existing = [str(path) for path in roots if path.exists()]
    if existing:
        raise FileExistsError("替代路线rep01已存在，拒绝覆盖：\n" + "\n".join(existing))


def preflight_sources(
    by_id: dict[str, dict[str, str]], by_path: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    checked: list[dict[str, Any]] = []
    for spec in FILES:
        item_id = str(spec["item_id"])
        relative = str(spec["frozen_relative_path"])
        if item_id not in by_id:
            raise KeyError(f"冻结清单缺少item_id：{item_id}")
        if relative not in by_path:
            raise KeyError(f"冻结清单缺少路径：{relative}")
        row_by_id = by_id[item_id]
        row_by_path = by_path[relative]
        if row_by_id is not row_by_path:
            raise RuntimeError(f"item_id与冻结路径不属于同一条记录：{item_id}")
        source = INPUT_ROOT / Path(relative)
        if not source.is_file():
            raise FileNotFoundError(f"冻结文件不存在：{source}")
        expected = row_by_id["frozen_sha256"].upper()
        actual = sha256_file(source)
        if actual != expected:
            raise RuntimeError(f"冻结文件已漂移：{relative}")
        if row_by_id.get("status") != "MATCH":
            raise RuntimeError(f"冻结清单状态不是MATCH：{item_id}")
        checked.append(
            {
                **spec,
                "source": source,
                "expected_sha256": expected,
                "source_size_bytes": source.stat().st_size,
                "manifest_role": row_by_id["role"],
            }
        )
    return checked


def main() -> int:
    assert_all_targets_absent()
    by_id, by_path = load_manifest()
    checked = preflight_sources(by_id, by_path)

    for path, expected_hash in EXPECTED_PROTECTED_HASHES.items():
        if not path.is_file():
            raise FileNotFoundError(f"缺少已封印代码：{path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(f"已封印代码与替代路线预检基线不一致：{path.name}")

    instrumentation_paths = {
        "stager": ORIGINAL_STAGER,
        "matlab_runner": MATLAB_RUNNER,
        "outer_executor": OUTER_EXECUTOR,
    }
    for name, path in instrumentation_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"缺少既有执行代码{name}：{path}")
    instrumentation = {
        name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
        for name, path in instrumentation_paths.items()
    }

    for path in (
        WORK_DIR,
        METADATA_DIR,
        WORKSPACE_DIR,
        SCIENTIFIC_DIR,
        AUTHOR_SAVED_DIR,
        RUN_LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=False)

    stage_rows: list[dict[str, Any]] = []
    for item in checked:
        destination = WORK_DIR / Path(str(item["destination_relative_path"]))
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"分发目标意外存在：{destination}")
        shutil.copy2(item["source"], destination)
        staged_hash = sha256_file(destination)
        if staged_hash != item["expected_sha256"]:
            raise RuntimeError(f"复制后哈希不一致：{destination}")
        stage_rows.append(
            {
                "route_id": ROUTE_ID,
                "replicate": REPLICATE,
                "kind": item["kind"],
                "execution_order": item["execution_order"],
                "frozen_manifest_item_id": item["item_id"],
                "manifest_role": item["manifest_role"],
                "frozen_relative_path": item["frozen_relative_path"],
                "source_absolute_path": str(Path(item["source"]).resolve()),
                "staged_relative_path": item["destination_relative_path"],
                "staged_absolute_path": str(destination.resolve()),
                "expected_sha256": item["expected_sha256"],
                "actual_sha256": staged_hash,
                "hash_match": True,
                "size_bytes": destination.stat().st_size,
            }
        )

    config_path = METADATA_DIR / "run_config.json"
    config_hash_path = METADATA_DIR / "run_config.sha256"
    upstream_rows = [row for row in stage_rows if row["kind"] == "upstream"]
    candidate_row = next(
        row for row in stage_rows if row["kind"] == "candidate_original_mlx"
    )

    config = {
        "schema": "board20_original_mlx_run_config_v2",
        "created_at": datetime.now().astimezone().isoformat(),
        "route_id": ROUTE_ID,
        "declared_method": "Guyan",
        "declared_division": "第一类子结构划分（稳定域同目录Ps3替代候选）",
        "actual_code_identity": (
            "Guyan-LQR2命名脚本；无LQR；21x21双时滞扫描；"
            "New_Ps3原生物理矩阵为9x9，候选脚本仅取前6维缩聚"
        ),
        "upstream_selection_basis": (
            "运行前预先固定为稳定域同目录New_Full.m+New_Ps3.m；"
            "不根据数值结果选路或拟合"
        ),
        "upstream_identity_status": (
            "PRECOMMITTED_SAME_DIRECTORY_CANDIDATE_WITH_DIMENSION_SEMANTIC_CONFLICT"
        ),
        "dependency_closure_status": (
            "CLOSED_WITH_AUTHOR_EXTERNAL_NEWMARK_DEPENDENCY"
        ),
        "semantic_conflicts": [
            {
                "id": "PS3_9X9_TRUNCATED_TO_FIRST_6_DOF",
                "status": "DISCLOSED_NOT_RESOLVED",
                "evidence": (
                    "New_Ps3.m定义9x9 KPrt/MPrt/CPrt；"
                    "luxvjie_guyan_LQR2.mlx的物理缩聚索引仅为"
                    "index3=[1,4]与index4=[2,3,5,6]，因而忽略第7-9维"
                ),
            }
        ],
        "execution_artifact": "ORIGINAL_MLX",
        "replicate": REPLICATE,
        "dependency_mode": "AUTHOR_FROZEN_EXTERNAL_DEPENDENCY",
        "work_dir": str(WORK_DIR.resolve()),
        "run_output_dir": str(RUN_OUTPUT_DIR.resolve()),
        "run_log_dir": str(RUN_LOG_DIR.resolve()),
        "upstream_files": [row["staged_absolute_path"] for row in upstream_rows],
        "dependency_directories": [str(DEPENDENCY_DIR.resolve())],
        "candidate_mlx": candidate_row["staged_absolute_path"],
        "candidate_sha256": candidate_row["expected_sha256"],
        "file_contracts": [
            {
                "kind": row["kind"],
                "execution_order": row["execution_order"],
                "path": row["staged_absolute_path"],
                "expected_sha256": row["expected_sha256"],
                "frozen_manifest_item_id": row["frozen_manifest_item_id"],
            }
            for row in stage_rows
        ],
        "allowed_work_files": [row["staged_relative_path"] for row in stage_rows],
        "source_contains_dlqr": False,
        "expected_scan_point_count": 441,
        "expected_stab_shape": [21, 21],
        "expected_written_regions": [[1, 21, 1, 21]],
        "source_save_call_count": 0,
        "enable_profile": False,
        "runtime_call_evidence": "CLEAN_BASE_WORKSPACE_VARIABLE_K_lqr",
        "actual_scan_point_count_method": "NOT_MEASURED_PROFILE_DISABLED",
        "expected_stab_required_on_execution_success": True,
        "author_save_targets": [],
        "status_json": str((METADATA_DIR / "run_status.json").resolve()),
        "diary_file": str((RUN_LOG_DIR / "matlab_diary.log").resolve()),
        "workspace_success": str(
            (WORKSPACE_DIR / "workspace_complete.mat").resolve()
        ),
        "workspace_failure": str(
            (WORKSPACE_DIR / "workspace_failure.mat").resolve()
        ),
        "scientific_arrays": str(
            (SCIENTIFIC_DIR / "scientific_arrays.mat").resolve()
        ),
        "raw_stab": str((SCIENTIFIC_DIR / "raw_stab.mat").resolve()),
        "profile_info": str((METADATA_DIR / "profile_info.mat").resolve()),
        "author_saved_dir": str(AUTHOR_SAVED_DIR.resolve()),
        "process_exit_json": str((METADATA_DIR / "process_exit.json").resolve()),
        "command_txt": str((RUN_LOG_DIR / "matlab_command.txt").resolve()),
        "shell_log": str(
            (RUN_LOG_DIR / "shell_stdout_stderr.log").resolve()
        ),
        "config_hash_file": str(config_hash_path.resolve()),
        "instrumentation": instrumentation,
        "protected_existing_files": [
            {
                "path": str(path.resolve()),
                "sha256": expected_hash,
                "status_at_staging": "MATCH",
            }
            for path, expected_hash in EXPECTED_PROTECTED_HASHES.items()
        ],
        "staging_provenance": {
            "mode": "INDEPENDENT_ALT_ROUTE_STAGER",
            "actual_stager": {
                "path": str(SCRIPT),
                "sha256": sha256_file(SCRIPT),
            },
            "compatibility_reference_stager": instrumentation["stager"],
            "matlab_launched_by_stager": False,
        },
    }
    write_json(config_path, config)
    config_hash = sha256_file(config_path)
    config_hash_path.write_text(config_hash + "\n", encoding="ascii")

    stage_manifest = METADATA_DIR / "stage_manifest.csv"
    with stage_manifest.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(stage_rows[0].keys()))
        writer.writeheader()
        writer.writerows(stage_rows)

    print(f"ROUTE_ID={ROUTE_ID}")
    print(f"REPLICATE={REPLICATE}")
    print(f"CONFIG={config_path}")
    print(f"CONFIG_SHA256={config_hash}")
    print(f"STAGED_FILES={len(stage_rows)}")
    print("MATLAB_LAUNCHED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
