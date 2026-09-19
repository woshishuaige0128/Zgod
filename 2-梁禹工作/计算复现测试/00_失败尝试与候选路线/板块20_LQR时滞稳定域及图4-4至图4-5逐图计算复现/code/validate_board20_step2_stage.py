from __future__ import annotations

import csv
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
INPUT_ROOT = (BOARD_ROOT / "input").resolve()
TMP_ROOT = (BOARD_ROOT / "tmp" / "step2_runs").resolve()
OUTPUT_ROOT = BOARD_ROOT / "outputs"
CONTRACT_CSV = OUTPUT_ROOT / "step2_run_contract.csv"
CONTRACT_JSON = OUTPUT_ROOT / "step2_run_contract.json"
STAGE_MANIFEST_CSV = OUTPUT_ROOT / "step2_stage_manifest.csv"
STAGE_SUMMARY_JSON = OUTPUT_ROOT / "step2_stage_summary.json"
MLX_CONTRACT_JSON = OUTPUT_ROOT / "mlx_contract.json"
VALIDATION_CSV = OUTPUT_ROOT / "step2_stage_validation.csv"
VALIDATION_JSON = OUTPUT_ROOT / "step2_stage_validation.json"
INPUT_MANIFEST_CSV = INPUT_ROOT / "input_manifest.csv"

EXPECTED: dict[str, dict[str, Any]] = {
    "main_ori_div1": {"upstream": 3, "helper": 1, "points": 1, "shape": "20x20", "dlqr": False},
    "main_ori_div2": {"upstream": 3, "helper": 1, "points": 1517, "shape": "26x67", "dlqr": True},
    "main_guyan_div1": {"upstream": 3, "helper": 1, "points": 441, "shape": "21x21", "dlqr": False},
    "main_guyan_div2": {"upstream": 3, "helper": 1, "points": 1517, "shape": "26x67", "dlqr": True},
    "main_cb_div1": {"upstream": 3, "helper": 1, "points": 441, "shape": "21x21", "dlqr": False},
    "main_cb_div2": {"upstream": 3, "helper": 1, "points": 441, "shape": "21x21", "dlqr": False},
    "energy_guyan_div1": {"upstream": 1, "helper": 0, "points": 16, "shape": "20x20", "dlqr": True},
    "energy_guyan_div2": {"upstream": 1, "helper": 0, "points": 16, "shape": "20x20", "dlqr": True},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(
    checks: list[dict[str, str]],
    check: str,
    expected: Any,
    actual: Any,
    passed: bool,
    evidence: str,
) -> None:
    checks.append(
        {
            "check_id": f"S2-STAGE-{len(checks) + 1:03d}",
            "check": check,
            "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True),
            "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True),
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence,
        }
    )


def region_point_count(regions: list[list[int]]) -> int:
    points: set[tuple[int, int]] = set()
    for row_start, row_end, column_start, column_end in regions:
        points.update(
            (row, column)
            for row in range(row_start, row_end + 1)
            for column in range(column_start, column_end + 1)
        )
    return len(points)


def paths_for_replicate(replicate: str) -> tuple[Path, Path, Path, Path, Path, Path]:
    suffix = "" if replicate == "rep01" else f"_{replicate}"
    return (
        OUTPUT_ROOT / f"step2_run_contract{suffix}.csv",
        OUTPUT_ROOT / f"step2_run_contract{suffix}.json",
        OUTPUT_ROOT / f"step2_stage_manifest{suffix}.csv",
        OUTPUT_ROOT / f"step2_stage_summary{suffix}.json",
        OUTPUT_ROOT / f"step2_stage_validation{suffix}.csv",
        OUTPUT_ROOT / f"step2_stage_validation{suffix}.json",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="验收板块20指定rep的原始MLX分发包。")
    parser.add_argument("--replicate", default="rep01")
    args = parser.parse_args()
    replicate = args.replicate
    (
        contract_csv,
        contract_json,
        stage_manifest_csv,
        stage_summary_json,
        validation_csv,
        validation_json,
    ) = paths_for_replicate(replicate)
    required = [
        contract_csv,
        contract_json,
        stage_manifest_csv,
        stage_summary_json,
        MLX_CONTRACT_JSON,
        INPUT_MANIFEST_CSV,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少分发验收输入：" + "; ".join(missing))

    checks: list[dict[str, str]] = []
    contracts = read_csv(contract_csv)
    stage_rows = read_csv(stage_manifest_csv)
    summary = read_json(stage_summary_json)
    mlx_contract = read_json(MLX_CONTRACT_JSON)
    freeze_rows = read_csv(INPUT_MANIFEST_CSV)
    freeze_by_relative = {row["frozen_relative_path"]: row for row in freeze_rows}
    mlx_by_relative = {
        row["frozen_relative_path"]: row for row in mlx_contract["records"]
    }

    route_ids = [row["route_id"] for row in contracts]
    add(
        checks,
        "八条路线唯一且完整",
        sorted(EXPECTED),
        sorted(route_ids),
        len(route_ids) == 8 and len(set(route_ids)) == 8 and set(route_ids) == set(EXPECTED),
        str(contract_csv),
    )
    add(
        checks,
        "分发汇总",
        {"routes": 8, "files": 34, "matches": 34, "bytes": 149584, "status": "PASS"},
        {
            "routes": summary.get("route_count"),
            "files": summary.get("staged_file_count"),
            "matches": summary.get("match_count"),
            "bytes": summary.get("total_bytes"),
            "status": summary.get("status"),
        },
        summary.get("route_count") == 8
        and summary.get("staged_file_count") == 34
        and summary.get("match_count") == 34
        and summary.get("total_bytes") == 149584
        and summary.get("status") == "PASS",
        str(stage_summary_json),
    )

    staged_paths = [row["staged_absolute_path"] for row in stage_rows]
    row_failures: list[str] = []
    for index, row in enumerate(stage_rows, start=1):
        source = Path(row["source_absolute_path"])
        staged = Path(row["staged_absolute_path"])
        conditions = (
            source.is_file(),
            staged.is_file(),
            is_within(source, INPUT_ROOT),
            is_within(staged, TMP_ROOT),
            source.stat().st_size == int(row["size_bytes"]) if source.is_file() else False,
            staged.stat().st_size == int(row["size_bytes"]) if staged.is_file() else False,
            sha256_file(source) == row["source_sha256"] if source.is_file() else False,
            sha256_file(staged) == row["staged_sha256"] if staged.is_file() else False,
            row["source_sha256"] == row["staged_sha256"],
            row["status"] == "MATCH",
            row["replicate"] == replicate,
            row.get("frozen_manifest_sha256") == row["source_sha256"],
            row.get("frozen_manifest_item_id")
            == freeze_by_relative.get(row["source_relative_path"], {}).get("item_id"),
            row["source_sha256"]
            == freeze_by_relative.get(row["source_relative_path"], {}).get("frozen_sha256"),
        )
        if not all(conditions):
            row_failures.append(f"row={index}; route={row['route_id']}; conditions={conditions}")
    add(
        checks,
        "34份分发文件实时大小与SHA-256",
        {"passed": 34, "failed": 0, "unique": 34},
        {
            "passed": len(stage_rows) - len(row_failures),
            "failed": len(row_failures),
            "unique": len(set(staged_paths)),
        },
        len(stage_rows) == 34 and not row_failures and len(set(staged_paths)) == 34,
        " | ".join(row_failures[:5]) or str(stage_manifest_csv),
    )

    candidate_rows = [row for row in stage_rows if row["kind"] == "candidate_original_mlx"]
    candidate_failures: list[str] = []
    for row in candidate_rows:
        relative = row["source_relative_path"]
        static = mlx_by_relative.get(relative)
        if (
            static is None
            or static["source_sha256"] != row["source_sha256"]
            or Path(row["staged_absolute_path"]).suffix.lower() != ".mlx"
        ):
            candidate_failures.append(row["route_id"])
    add(
        checks,
        "八份候选为原始MLX且反查静态合同",
        {"count": 8, "failures": []},
        {"count": len(candidate_rows), "failures": candidate_failures},
        len(candidate_rows) == 8 and not candidate_failures,
        str(MLX_CONTRACT_JSON),
    )

    forbidden_failures: list[str] = []
    allowed_suffixes = {".m", ".mlx"}
    for row in stage_rows:
        staged = Path(row["staged_absolute_path"])
        if staged.suffix.lower() not in allowed_suffixes:
            forbidden_failures.append(str(staged))
        if row["kind"] == "candidate_original_mlx" and "outputs\\mlx_code" in str(staged):
            forbidden_failures.append(str(staged))
    add(
        checks,
        "工作目录不注入历史MAT或抽取M镜像",
        [],
        forbidden_failures,
        not forbidden_failures,
        str(stage_manifest_csv),
    )

    contract_by_route = {row["route_id"]: row for row in contracts}
    for route_id, expected in EXPECTED.items():
        route_rows = [row for row in stage_rows if row["route_id"] == route_id]
        upstream_count = sum(row["kind"] == "upstream" for row in route_rows)
        helper_count = sum(
            row["kind"] == "author_external_dependency" for row in route_rows
        )
        candidate_count = sum(row["kind"] == "candidate_original_mlx" for row in route_rows)
        contract = contract_by_route[route_id]
        config_path = Path(contract["config_path"])
        config = read_json(config_path) if config_path.is_file() else {}
        config_hash_path = (
            Path(config["config_hash_file"]) if config else Path("__missing__")
        )
        config_hash_match = (
            config_hash_path.is_file()
            and sha256_file(config_path)
            == config_hash_path.read_text(encoding="ascii").strip().upper()
        )
        instrumentation_matches = []
        for name in ("stager", "matlab_runner", "outer_executor"):
            item = config.get("instrumentation", {}).get(name, {})
            path = Path(item.get("path", "__missing__"))
            instrumentation_matches.append(
                path.is_file() and sha256_file(path) == item.get("sha256")
            )
        status_path = Path(config["status_json"]) if config else Path("__missing__")
        diary_path = Path(config["diary_file"]) if config else Path("__missing__")
        work_dir = Path(config["work_dir"]) if config else Path("__missing__")
        work_results = []
        if work_dir.is_dir():
            work_results = [
                path.name
                for path in work_dir.rglob("*")
                if path.is_file() and path.suffix.lower() not in allowed_suffixes
            ]
        actual = {
            "upstream": upstream_count,
            "helper": helper_count,
            "candidate": candidate_count,
            "points": int(contract["expected_scan_point_count"]),
            "shape": contract["expected_stab_shape"],
            "dlqr": contract["source_contains_dlqr"].lower() == "true",
            "config_exists": config_path.is_file(),
            "artifact": config.get("execution_artifact"),
            "profile": config.get("enable_profile"),
            "schema": config.get("schema"),
            "replicate": config.get("replicate"),
            "file_contract_count": len(config.get("file_contracts", [])),
            "allowed_work_file_count": len(config.get("allowed_work_files", [])),
            "config_hash_match": config_hash_match,
            "instrumentation_hash_matches": instrumentation_matches,
            "written_region_points": region_point_count(
                config.get("expected_written_regions", [])
            ),
            "status_absent": not status_path.exists(),
            "diary_absent": not diary_path.exists(),
            "work_results": work_results,
        }
        expected_actual = {
            "upstream": expected["upstream"],
            "helper": expected["helper"],
            "candidate": 1,
            "points": expected["points"],
            "shape": expected["shape"],
            "dlqr": expected["dlqr"],
            "config_exists": True,
            "artifact": "ORIGINAL_MLX",
            "profile": False,
            "schema": "board20_original_mlx_run_config_v2",
            "replicate": replicate,
            "file_contract_count": len(route_rows),
            "allowed_work_file_count": len(route_rows),
            "config_hash_match": True,
            "instrumentation_hash_matches": [True, True, True],
            "written_region_points": expected["points"],
            "status_absent": True,
            "diary_absent": True,
            "work_results": [],
        }
        add(
            checks,
            f"路线分发合同：{route_id}",
            expected_actual,
            actual,
            actual == expected_actual,
            str(config_path),
        )

    failures = [row for row in checks if row["status"] == "FAIL"]
    with validation_csv.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(checks[0].keys()))
        writer.writeheader()
        writer.writerows(checks)
    result = {
        "schema": "board20_step2_stage_validation_v2",
        "created_at": datetime.now().astimezone().isoformat(),
        "replicate": replicate,
        "checks": len(checks),
        "passed": len(checks) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    validation_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"BOARD20_STEP2_STAGE_VALIDATION_{result['status']} "
        f"checks={result['passed']}/{result['checks']}"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
