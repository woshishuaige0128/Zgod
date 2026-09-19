#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""独立批量评价 Fig10 盲算全网格候选。

本程序处于目标评价侧，严格遵守以下边界：

1. 只读取已经完成的 ``stable_mask.csv`` 及其盲算元数据；
2. 不导入、不运行 ``fig10_blind_core.py`` 或任何参数搜索程序；
3. 为允许的合同 ID 的六条路线构造 ``FIG10_CANDIDATE_MANIFEST_V1``；
4. 通过独立子进程调用 ``strict_target_evaluator.py``。冻结目标 MAT 仅由该严格
   评价器读取，本批量桥不打开、不哈希目标 MAT；
5. 结果只能称为“目标引导的校准计算复现”，不能据此认领作者原始参数合同。

标准盲算输入根必须具有如下结构。未给 ``--contract-id`` 时仅允许
B1/B2/B3；诊断合同必须用可重复的 ``--contract-id`` 显式允许：

``routes/B1_D1_Original/full-grid/stable_mask.csv``

每个完整合同必须同时提供 D1/D2 × Original/Craig_Bampton/Guyan 六条路线。
程序也支持把现有 ``FIG10_CANDIDATE_MANIFEST_V1`` 回归目录作为输入根，用于
验证历史掩膜接口；该兼容入口不替代标准盲算输入合同。

词典序排名键由小到大依次为：失败路线数、边界点数绝对误差、集合差点数、
点级 Levenshtein 编辑距离、最大 Hausdorff 距离、Hausdorff 距离总和、
端点 L1 误差、轴截距误差、候选 ID。轴截距采用“从原点连续稳定前缀的最后一个采样点”；
同时输出轴上最远稳定点，显式暴露孔洞或离散孤点。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT = Path(__file__).resolve()
CASE_ROOT = SCRIPT.parent.parent
REPOSITORY_ROOT = SCRIPT.parents[5]
DEFAULT_STRICT_EVALUATOR = SCRIPT.parent / "strict_target_evaluator.py"
DEFAULT_MATLAB_HELPER = SCRIPT.parent / "fig10_extract_mask_boundaries.m"
DEFAULT_TARGET = (
    REPOSITORY_ROOT.parent
    / "260817"
    / "code"
    / "Fig10_双时滞稳定域"
    / "输出"
    / "plotted_data.mat"
)
DEFAULT_MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")

BATCH_SCHEMA = "FIG10_BATCH_TARGET_EVALUATOR_V1"
STRICT_MANIFEST_SCHEMA = "FIG10_CANDIDATE_MANIFEST_V1"
EXPECTED_ROWS = 31
EXPECTED_COLUMNS = 67
EXPECTED_GRID_POINTS = EXPECTED_ROWS * EXPECTED_COLUMNS
MS_PER_SAMPLE = 1000.0 / 1024.0
SHA256_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")
SAFE_COMPONENT_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
CONTRACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class CurveSpec:
    curve_id: str
    division: int
    method: str
    route_method: str
    expected_boundary_points: int


CURVE_SPECS: tuple[CurveSpec, ...] = (
    CurveSpec("division1_original", 1, "Original", "Original", 72),
    CurveSpec("division1_craig_bampton", 1, "Craig-Bampton", "Craig_Bampton", 69),
    CurveSpec("division1_guyan", 1, "Guyan", "Guyan", 67),
    CurveSpec("division2_original", 2, "Original", "Original", 69),
    CurveSpec("division2_craig_bampton", 2, "Craig-Bampton", "Craig_Bampton", 56),
    CurveSpec("division2_guyan", 2, "Guyan", "Guyan", 53),
)
CURVE_IDS = tuple(spec.curve_id for spec in CURVE_SPECS)
DEFAULT_CONTRACT_IDS = ("B1", "B2", "B3")
EXPECTED_REGRESSION_PASS_CURVES = (
    "division1_original",
    "division2_original",
)

RANKING_FIELDS = (
    "failed_route_count",
    "total_abs_boundary_point_count_error",
    "total_set_difference_count",
    "total_point_levenshtein_original",
    "maximum_symmetric_hausdorff_steps",
    "sum_symmetric_hausdorff_steps",
    "total_endpoint_l1_error_steps_original",
    "total_axis_prefix_intercept_error_samples",
    "candidate_id",
)


@dataclass
class MaskStats:
    path: Path
    sha256: str
    rows: int
    columns: int
    stable_point_count: int
    tau1_axis_origin_prefix_last_index: int
    tau2_axis_origin_prefix_last_index: int
    tau1_axis_rightmost_stable_index: int
    tau2_axis_highest_stable_index: int
    tau1_axis_hole_count_before_rightmost: int
    tau2_axis_hole_count_before_highest: int


@dataclass
class CandidateSource:
    candidate_id: str
    contract_id: str
    input_mode: str
    input_root: Path
    evidence_label: str
    masks: dict[str, Path]
    route_ids: dict[str, str]
    route_inputs: dict[str, dict[str, Any]]
    source_manifest: Path | None = None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_json(path: Path, payload: Any) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(payload, dict), f"JSON 顶层必须是对象：{path}")
    return payload


def safe_component(value: str) -> str:
    cleaned = SAFE_COMPONENT_PATTERN.sub("_", value.strip()).strip("._-")
    return cleaned[:120] or "candidate"


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root = root.resolve()
    return resolved == root or resolved.is_relative_to(root)


def contiguous_prefix_last_index(values: Sequence[int]) -> int:
    last = -1
    for index, value in enumerate(values):
        if value != 1:
            break
        last = index
    return last


def farthest_stable_index(values: Sequence[int]) -> int:
    stable = [index for index, value in enumerate(values) if value == 1]
    return max(stable) if stable else -1


def holes_before(values: Sequence[int], farthest: int) -> int:
    if farthest < 0:
        return 0
    return sum(value == 0 for value in values[: farthest + 1])


def load_mask(path: Path) -> tuple[list[list[int]], MaskStats]:
    path = path.resolve()
    require(path.is_file(), f"掩膜不存在：{path}")
    matrix: list[list[int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        for row_number, row in enumerate(reader, start=1):
            require(row, f"掩膜含空行：{path}:{row_number}")
            values: list[int] = []
            for column_number, raw in enumerate(row, start=1):
                token = raw.strip()
                require(
                    token in {"0", "1"},
                    f"掩膜必须是无表头 0/1 矩阵：{path}:{row_number}:{column_number}={raw!r}",
                )
                values.append(int(token))
            matrix.append(values)
    require(len(matrix) == EXPECTED_ROWS, f"掩膜行数必须为31：{path} -> {len(matrix)}")
    require(
        all(len(row) == EXPECTED_COLUMNS for row in matrix),
        f"掩膜每行列数必须为67：{path}",
    )
    tau1_axis = matrix[0]
    tau2_axis = [row[0] for row in matrix]
    tau1_prefix = contiguous_prefix_last_index(tau1_axis)
    tau2_prefix = contiguous_prefix_last_index(tau2_axis)
    tau1_farthest = farthest_stable_index(tau1_axis)
    tau2_farthest = farthest_stable_index(tau2_axis)
    stats = MaskStats(
        path=path,
        sha256=sha256_file(path),
        rows=len(matrix),
        columns=len(matrix[0]),
        stable_point_count=sum(sum(row) for row in matrix),
        tau1_axis_origin_prefix_last_index=tau1_prefix,
        tau2_axis_origin_prefix_last_index=tau2_prefix,
        tau1_axis_rightmost_stable_index=tau1_farthest,
        tau2_axis_highest_stable_index=tau2_farthest,
        tau1_axis_hole_count_before_rightmost=holes_before(tau1_axis, tau1_farthest),
        tau2_axis_hole_count_before_highest=holes_before(tau2_axis, tau2_farthest),
    )
    return matrix, stats


def validate_grid_axes(path: Path) -> str:
    require(path.is_file(), f"全网格缺少 grid_axes.json：{path}")
    payload = read_json(path)
    require(payload.get("row_axis") == "l_samples", f"row_axis合同错误：{path}")
    require(payload.get("column_axis") == "j_samples", f"column_axis合同错误：{path}")
    require(payload.get("l_values") == list(range(EXPECTED_ROWS)), f"l_values必须为0..30：{path}")
    require(
        payload.get("j_values") == list(range(EXPECTED_COLUMNS)),
        f"j_values必须为0..66：{path}",
    )
    require(payload.get("mask_shape") == [EXPECTED_ROWS, EXPECTED_COLUMNS], f"mask_shape错误：{path}")
    require(payload.get("stable_rule") == "rho < 1.0", f"stable_rule错误：{path}")
    return sha256_file(path)


def load_hash_manifest(path: Path) -> dict[Path, str]:
    require(path.is_file(), f"盲算根缺少 artifact_hash_manifest.csv：{path}")
    result: dict[Path, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None, f"空哈希清单：{path}")
        require({"path", "sha256"} <= set(reader.fieldnames), f"哈希清单字段不完整：{path}")
        for row in reader:
            digest = str(row["sha256"]).upper()
            require(SHA256_PATTERN.fullmatch(digest) is not None, f"非法SHA-256：{path}")
            result[Path(str(row["path"])).resolve()] = digest
    return result


def normalize_method(value: Any) -> str:
    token = re.sub(r"[^a-z]", "", str(value).casefold())
    aliases = {
        "original": "original",
        "craigbampton": "craig_bampton",
        "guyan": "guyan",
    }
    require(token in aliases, f"不支持的路线method：{value!r}")
    return aliases[token]


def require_recorded_hash(path: Path, recorded_hashes: Mapping[Path, str]) -> str:
    resolved = path.resolve()
    require(resolved.is_file(), f"路线工件不存在：{resolved}")
    require(resolved in recorded_hashes, f"盲算哈希清单未登记工件：{resolved}")
    digest = sha256_file(resolved)
    require(recorded_hashes[resolved] == digest, f"盲算哈希清单与现场工件不一致：{resolved}")
    return digest


def validate_route_result(
    route_dir: Path,
    route_entry: Mapping[str, Any],
    run_route_summary: Mapping[str, Any],
    manifest_sha256: str,
    recorded_hashes: Mapping[Path, str],
) -> dict[str, Any]:
    route_id_value = str(route_entry["route_id"])
    full_grid = route_dir / "full-grid"
    paths = {
        "checkpoint": full_grid / "checkpoint.json",
        "grid_axes": full_grid / "grid_axes.json",
        "points": full_grid / "points.csv",
        "route_summary": full_grid / "route_summary.json",
        "mask": full_grid / "stable_mask.csv",
    }
    hashes = {name: require_recorded_hash(path, recorded_hashes) for name, path in paths.items()}
    validate_grid_axes(paths["grid_axes"])
    matrix, stats = load_mask(paths["mask"])

    checkpoint = read_json(paths["checkpoint"])
    require(checkpoint.get("status") == "COMPLETE", f"检查点不是COMPLETE：{route_id_value}")
    require(checkpoint.get("mode") == "full-grid", f"检查点不是full-grid：{route_id_value}")
    require(checkpoint.get("route_id") == route_id_value, f"检查点route_id不符：{route_id_value}")
    require(checkpoint.get("contract_id") == route_entry["contract_id"], f"检查点contract_id不符：{route_id_value}")
    require(str(checkpoint.get("manifest_sha256", "")).upper() == manifest_sha256, f"检查点manifest哈希不符：{route_id_value}")
    require(str(checkpoint.get("bundle_sha256", "")).upper() == str(route_entry["bundle_sha256"]).upper(), f"检查点bundle哈希不符：{route_id_value}")
    require(int(checkpoint.get("completed_point_count", -1)) == EXPECTED_GRID_POINTS, f"检查点完成点数错误：{route_id_value}")
    require(int(checkpoint.get("total_point_count", -1)) == EXPECTED_GRID_POINTS, f"检查点总点数错误：{route_id_value}")
    require(int(checkpoint.get("next_point_index", -1)) == EXPECTED_GRID_POINTS, f"检查点下一索引错误：{route_id_value}")
    require(str(checkpoint.get("results_csv_sha256", "")).upper() == hashes["points"], f"检查点points哈希不符：{route_id_value}")

    local_summary = read_json(paths["route_summary"])
    for item, label in ((run_route_summary, "run_summary"), (local_summary, "route_summary")):
        require(item.get("status") == "PASS", f"{label}路线未通过：{route_id_value}")
        require(item.get("mode") == "full-grid", f"{label}路线不是full-grid：{route_id_value}")
        require(item.get("route_id") == route_id_value, f"{label} route_id不符：{route_id_value}")
        require(item.get("contract_id") == route_entry["contract_id"], f"{label} contract_id不符：{route_id_value}")
        require(int(item.get("point_count", -1)) == EXPECTED_GRID_POINTS, f"{label}点数错误：{route_id_value}")

    required_columns = {
        "route_id",
        "contract_id",
        "division",
        "method",
        "mode",
        "point_order",
        "l_samples",
        "j_samples",
        "rho",
        "stable",
        "overall_pass",
    }
    point_stable_count = 0
    with paths["points"].open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and required_columns <= set(reader.fieldnames), f"points.csv字段不完整：{route_id_value}")
        point_rows = list(reader)
    require(len(point_rows) == EXPECTED_GRID_POINTS, f"points.csv行数不是2077：{route_id_value}")
    expected_method = normalize_method(route_entry["method"])
    for index, row in enumerate(point_rows):
        expected_l, expected_j = divmod(index, EXPECTED_COLUMNS)
        require(int(row["point_order"]) == index + 1, f"point_order错位：{route_id_value}/{index + 1}")
        require(int(row["l_samples"]) == expected_l, f"l_samples错位：{route_id_value}/{index + 1}")
        require(int(row["j_samples"]) == expected_j, f"j_samples错位：{route_id_value}/{index + 1}")
        require(row["route_id"] == route_id_value, f"points route_id不符：{route_id_value}/{index + 1}")
        require(row["contract_id"] == str(route_entry["contract_id"]), f"points contract_id不符：{route_id_value}/{index + 1}")
        require(int(row["division"]) == int(route_entry["division"]), f"points division不符：{route_id_value}/{index + 1}")
        require(normalize_method(row["method"]) == expected_method, f"points method不符：{route_id_value}/{index + 1}")
        require(row["mode"] == "full-grid", f"points mode不符：{route_id_value}/{index + 1}")
        rho = finite_number(row["rho"], f"rho {route_id_value}/{index + 1}")
        stable = int(row["stable"])
        require(stable in (0, 1), f"points stable不是0/1：{route_id_value}/{index + 1}")
        require(stable == int(rho < 1.0), f"points stable与rho<1不符：{route_id_value}/{index + 1}")
        require(stable == matrix[expected_l][expected_j], f"points stable与mask不符：{route_id_value}/{index + 1}")
        require(int(row["overall_pass"]) == 1, f"points内部验收未通过：{route_id_value}/{index + 1}")
        point_stable_count += stable
    require(point_stable_count == stats.stable_point_count, f"points与mask稳定点数不闭合：{route_id_value}")
    require(point_stable_count == int(local_summary["stable_point_count"]), f"route_summary稳定点数不闭合：{route_id_value}")
    require(point_stable_count == int(run_route_summary["stable_point_count"]), f"run_summary稳定点数不闭合：{route_id_value}")

    fingerprint_payload = {
        "manifest_sha256": manifest_sha256,
        "route_id": route_id_value,
        "contract_id": route_entry["contract_id"],
        "division": int(route_entry["division"]),
        "method": expected_method,
        "contract_hash": str(route_entry["contract_hash"]).upper(),
        "bundle_sha256": str(route_entry["bundle_sha256"]).upper(),
        "route_operator_sha256": str(route_entry.get("route_operator_sha256", "")).upper(),
        "artifact_sha256": hashes,
    }
    return {
        "route_input_fingerprint": canonical_sha256(fingerprint_payload),
        "manifest_sha256": manifest_sha256,
        "contract_hash": str(route_entry["contract_hash"]).upper(),
        "bundle_sha256": str(route_entry["bundle_sha256"]).upper(),
        "route_operator_sha256": str(route_entry.get("route_operator_sha256", "")).upper(),
        "checkpoint_sha256": hashes["checkpoint"],
        "grid_axes_sha256": hashes["grid_axes"],
        "points_sha256": hashes["points"],
        "route_summary_sha256": hashes["route_summary"],
        "stable_mask_sha256": hashes["mask"],
        "checkpoint_path": str(paths["checkpoint"].resolve()),
        "grid_axes_path": str(paths["grid_axes"].resolve()),
        "points_path": str(paths["points"].resolve()),
        "route_summary_path": str(paths["route_summary"].resolve()),
    }


def validate_blind_root(root: Path) -> tuple[dict[str, Any], dict[Path, str]]:
    summary_path = root / "run_summary.json"
    require(summary_path.is_file(), f"标准盲算输入根缺少 run_summary.json：{root}")
    summary = read_json(summary_path)
    require(summary.get("status") == "PASS", f"盲算 run_summary 未通过：{summary_path}")
    require(summary.get("blind_calculation_only") is True, f"盲算防火墙标记缺失：{summary_path}")
    require(summary.get("mode") == "full-grid", f"输入根不是 full-grid：{summary_path}")
    route_summaries = summary.get("route_summaries")
    require(isinstance(route_summaries, list) and route_summaries, f"route_summaries为空：{summary_path}")
    by_id: dict[str, dict[str, Any]] = {}
    for item in route_summaries:
        require(isinstance(item, dict), f"route_summaries元素不是对象：{summary_path}")
        route_id = str(item.get("route_id", ""))
        require(route_id and route_id not in by_id, f"route_id为空或重复：{summary_path}")
        require(item.get("status") == "PASS", f"路线未通过：{route_id}")
        require(item.get("mode") == "full-grid", f"路线不是full-grid：{route_id}")
        require(int(item.get("point_count", -1)) == EXPECTED_GRID_POINTS, f"路线点数不是2077：{route_id}")
        by_id[route_id] = item
    require(int(summary.get("route_count", -1)) == len(by_id), f"run_summary路线数不闭合：{summary_path}")
    require(int(summary.get("point_count", -1)) == len(by_id) * EXPECTED_GRID_POINTS, f"run_summary总点数不闭合：{summary_path}")
    hashes = load_hash_manifest(root / "artifact_hash_manifest.csv")
    manifest_path = Path(str(summary.get("manifest_path", ""))).resolve()
    require(manifest_path.is_file(), f"run_summary绑定的盲算manifest不存在：{manifest_path}")
    manifest_sha256 = sha256_file(manifest_path)
    require(str(summary.get("manifest_sha256", "")).upper() == manifest_sha256, f"run_summary manifest哈希不符：{summary_path}")
    require(manifest_path in hashes and hashes[manifest_path] == manifest_sha256, f"artifact_hash_manifest未闭合盲算manifest：{manifest_path}")
    manifest = read_json(manifest_path)
    require(manifest.get("schema_version") == "FIG10_BLIND_SEARCH_MANIFEST_V1", f"盲算manifest schema错误：{manifest_path}")
    entries = manifest.get("routes")
    require(isinstance(entries, list) and entries, f"盲算manifest routes为空：{manifest_path}")
    manifest_by_route: dict[str, dict[str, Any]] = {}
    for entry in entries:
        require(isinstance(entry, dict), f"盲算manifest route不是对象：{manifest_path}")
        route_id_value = str(entry.get("route_id", ""))
        require(route_id_value and route_id_value not in manifest_by_route, f"盲算manifest route_id为空或重复：{manifest_path}")
        manifest_by_route[route_id_value] = entry
    require(set(manifest_by_route) == set(by_id), f"盲算manifest与run_summary路线集合不一致：{root}")
    return {
        "summary": summary,
        "by_route_id": by_id,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_sha256,
        "manifest_by_route_id": manifest_by_route,
    }, hashes


def route_id(contract_id: str, spec: CurveSpec) -> str:
    return f"{contract_id}_D{spec.division}_{spec.route_method}"


def resolve_contract_ids(explicit_ids: Sequence[str] | None) -> tuple[str, ...]:
    if explicit_ids is None:
        return DEFAULT_CONTRACT_IDS
    require(explicit_ids, "--contract-id显式列表不得为空")
    resolved: list[str] = []
    seen: set[str] = set()
    for raw_value in explicit_ids:
        value = str(raw_value).strip()
        require(value == raw_value, f"--contract-id不得含首尾空白：{raw_value!r}")
        require(CONTRACT_ID_PATTERN.fullmatch(value) is not None, f"--contract-id格式非法：{value!r}")
        folded = value.casefold()
        require(folded not in seen, f"--contract-id重复：{value}")
        seen.add(folded)
        resolved.append(value)
    return tuple(resolved)


def discover_standard_root(root: Path, allowed_contract_ids: Sequence[str]) -> list[CandidateSource]:
    root = root.resolve()
    allowed_contract_ids = tuple(allowed_contract_ids)
    require(allowed_contract_ids, "允许的合同ID列表为空")
    allowed_contract_set = set(allowed_contract_ids)
    allowed_label = "/".join(allowed_contract_ids)
    route_root = root / "routes"
    require(route_root.is_dir(), f"标准盲算输入根缺少 routes/：{root}")
    run_metadata, recorded_hashes = validate_blind_root(root)
    actual_dirs = {
        child.name.lower(): child
        for child in route_root.iterdir()
        if child.is_dir()
    }
    candidates: list[CandidateSource] = []
    entries_by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    for entry in run_metadata["manifest_by_route_id"].values():
        contract = str(entry.get("contract_id", ""))
        require(
            contract in allowed_contract_set,
            f"盲算manifest含未经--contract-id允许的合同：{contract}；当前允许：{allowed_label}",
        )
        division = int(entry.get("division", -1))
        require(division in (1, 2), f"盲算manifest division非法：{entry.get('route_id')}")
        key = (contract, division, normalize_method(entry.get("method")))
        require(key not in entries_by_key, f"盲算manifest含重复科学路线：{key}")
        entries_by_key[key] = entry
    method_key = {"Original": "original", "Craig-Bampton": "craig_bampton", "Guyan": "guyan"}
    for contract_id in allowed_contract_ids:
        expected_keys = [(contract_id, spec.division, method_key[spec.method]) for spec in CURVE_SPECS]
        found_count = sum(key in entries_by_key for key in expected_keys)
        if found_count == 0:
            continue
        require(
            found_count == len(expected_keys),
            f"{root}: {contract_id} 只找到 {found_count}/6 条路线，拒绝部分候选评价",
        )
        masks: dict[str, Path] = {}
        route_ids: dict[str, str] = {}
        route_inputs: dict[str, dict[str, Any]] = {}
        for spec, key in zip(CURVE_SPECS, expected_keys, strict=True):
            entry = entries_by_key[key]
            expected = str(entry["route_id"])
            require(expected.lower() in actual_dirs, f"routes目录缺少manifest路线：{expected}")
            actual_route_dir = actual_dirs[expected.lower()]
            actual_route_id = actual_route_dir.name
            require(actual_route_id in run_metadata["by_route_id"], f"run_summary未登记路线：{actual_route_id}")
            route_summary = run_metadata["by_route_id"][actual_route_id]
            require(str(route_summary.get("contract_id")) == contract_id, f"合同ID不符：{actual_route_id}")
            mask_path = (actual_route_dir / "full-grid" / "stable_mask.csv").resolve()
            require(mask_path.is_file(), f"路线缺少 stable_mask.csv：{actual_route_id}")
            route_inputs[spec.curve_id] = validate_route_result(
                actual_route_dir,
                entry,
                route_summary,
                run_metadata["manifest_sha256"],
                recorded_hashes,
            )
            masks[spec.curve_id] = mask_path
            route_ids[spec.curve_id] = actual_route_id
        candidates.append(
            CandidateSource(
                candidate_id=f"{root.name}__{contract_id}",
                contract_id=contract_id,
                input_mode="BLIND_FULL_GRID_ROOT",
                input_root=root,
                evidence_label="目标引导的校准计算复现",
                masks=masks,
                route_ids=route_ids,
                route_inputs=route_inputs,
                source_manifest=run_metadata["manifest_path"],
            )
        )
    require(candidates, f"{root}: 未发现任何完整六路线候选；当前允许合同：{allowed_label}")
    return candidates


def strict_manifest_candidates(root: Path) -> list[Path]:
    matches: list[Path] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
        if payload.get("schema_version") == STRICT_MANIFEST_SCHEMA:
            matches.append(path.resolve())
    return matches


def discover_regression_root(root: Path) -> list[CandidateSource]:
    manifests = strict_manifest_candidates(root)
    require(
        len(manifests) == 1,
        f"回归兼容输入根必须恰好含一个 {STRICT_MANIFEST_SCHEMA}：{root} -> {len(manifests)}",
    )
    manifest_path = manifests[0]
    manifest = read_json(manifest_path)
    entries = manifest.get("curves")
    require(isinstance(entries, list), f"manifest.curves不是列表：{manifest_path}")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        require(isinstance(entry, dict), f"manifest.curves元素不是对象：{manifest_path}")
        curve_id = str(entry.get("curve_id", ""))
        require(curve_id and curve_id not in by_id, f"curve_id为空或重复：{manifest_path}")
        by_id[curve_id] = entry
    require(set(by_id) == set(CURVE_IDS), f"回归manifest必须恰好绑定六曲线：{manifest_path}")
    masks: dict[str, Path] = {}
    route_ids: dict[str, str] = {}
    route_inputs: dict[str, dict[str, Any]] = {}
    for spec in CURVE_SPECS:
        entry = by_id[spec.curve_id]
        require(entry.get("input_type") == "mask_csv", f"回归入口只接受mask_csv：{spec.curve_id}")
        expected_shape = entry.get("expected_shape")
        require(expected_shape == [EXPECTED_ROWS, EXPECTED_COLUMNS], f"回归掩膜形状声明错误：{spec.curve_id}")
        require(
            entry.get("boundary_mode") == "matlab_bwboundaries_8_noholes_visible_open",
            f"回归边界模式错误：{spec.curve_id}",
        )
        masks[spec.curve_id] = resolve_from(manifest_path.parent, str(entry["path"]))
        route_ids[spec.curve_id] = f"REGRESSION_D{spec.division}_{spec.route_method}"
        route_inputs[spec.curve_id] = {
            "route_input_fingerprint": canonical_sha256(
                {
                    "source_manifest_sha256": sha256_file(manifest_path),
                    "curve_id": spec.curve_id,
                    "stable_mask_sha256": sha256_file(masks[spec.curve_id]),
                }
            ),
            "manifest_sha256": sha256_file(manifest_path),
            "contract_hash": "",
            "bundle_sha256": "",
            "route_operator_sha256": "",
            "checkpoint_sha256": "",
            "grid_axes_sha256": "",
            "points_sha256": "",
            "route_summary_sha256": "",
            "stable_mask_sha256": sha256_file(masks[spec.curve_id]),
            "checkpoint_path": "",
            "grid_axes_path": "",
            "points_path": "",
            "route_summary_path": "",
        }
    return [
        CandidateSource(
            candidate_id=str(manifest.get("candidate_id", root.name)),
            contract_id="REGRESSION",
            input_mode="STRICT_MANIFEST_REGRESSION_ROOT",
            input_root=root.resolve(),
            evidence_label=str(manifest.get("evidence_label", "回归接口测试，不是当前计算复现")),
            masks=masks,
            route_ids=route_ids,
            route_inputs=route_inputs,
            source_manifest=manifest_path,
        )
    ]


def discover_input_root(root: Path, allowed_contract_ids: Sequence[str]) -> list[CandidateSource]:
    root = root.resolve()
    require(root.is_dir(), f"输入根不存在或不是目录：{root}")
    if (root / "routes").is_dir():
        return discover_standard_root(root, allowed_contract_ids)
    return discover_regression_root(root)


def make_unique_candidate_ids(candidates: list[CandidateSource]) -> None:
    counts: dict[str, int] = {}
    for candidate in candidates:
        base = safe_component(candidate.candidate_id)
        counts[base.lower()] = counts.get(base.lower(), 0) + 1
    used: set[str] = set()
    for candidate in candidates:
        base = safe_component(candidate.candidate_id)
        if counts[base.lower()] > 1:
            path_hash = hashlib.sha256(str(candidate.input_root).encode("utf-8")).hexdigest()[:12]
            base = f"{base}__{path_hash}"
        value = base
        serial = 2
        while value.lower() in used:
            value = f"{base}__{serial}"
            serial += 1
        candidate.candidate_id = value
        used.add(value.lower())


def build_strict_manifest(candidate: CandidateSource, path: Path) -> dict[str, Any]:
    curves = []
    for spec in CURVE_SPECS:
        curves.append(
            {
                "curve_id": spec.curve_id,
                "input_type": "mask_csv",
                "path": str(candidate.masks[spec.curve_id].resolve()),
                "expected_shape": [EXPECTED_ROWS, EXPECTED_COLUMNS],
                "boundary_mode": "matlab_bwboundaries_8_noholes_visible_open",
            }
        )
    payload = {
        "schema_version": STRICT_MANIFEST_SCHEMA,
        "candidate_id": candidate.candidate_id,
        "evidence_label": candidate.evidence_label,
        "curves": curves,
    }
    write_json(path, payload)
    return payload


def run_strict_evaluator(
    strict_evaluator: Path,
    manifest_path: Path,
    target_path: Path,
    matlab_path: Path,
    output_dir: Path,
) -> tuple[dict[str, Any], int]:
    command = [
        sys.executable,
        str(strict_evaluator),
        "--manifest",
        str(manifest_path),
        "--target",
        str(target_path),
        "--output-dir",
        str(output_dir),
        "--matlab",
        str(matlab_path),
    ]
    process = subprocess.run(
        command,
        cwd=SCRIPT.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    atomic_write_text(output_dir.parent / "strict_evaluator_stdout.log", process.stdout)
    atomic_write_text(output_dir.parent / "strict_evaluator_stderr.log", process.stderr)
    write_json(
        output_dir.parent / "strict_evaluator_process.json",
        {"returncode": process.returncode, "command": command},
    )
    require(
        process.returncode in (0, 2),
        "strict_target_evaluator执行错误，详见 "
        f"{output_dir.parent / 'strict_evaluator_stderr.log'}",
    )
    summary_path = output_dir / "strict_evaluation_summary.json"
    require(summary_path.is_file(), f"严格评价器未生成摘要：{summary_path}")
    summary = read_json(summary_path)
    require(summary.get("overall_status") in {"PASS", "FAIL"}, f"严格评价摘要状态非法：{summary_path}")
    require(
        (process.returncode == 0) == (summary.get("overall_status") == "PASS"),
        f"严格评价器返回码与摘要不一致：{summary_path}",
    )
    return summary, process.returncode


def set_difference_counts(path: Path) -> dict[str, int]:
    result = {curve_id: 0 for curve_id in CURVE_IDS}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            curve_id = str(row.get("curve_id", ""))
            require(curve_id in result, f"set_differences.csv含未知curve_id：{curve_id}")
            result[curve_id] += 1
    return result


def finite_number(value: Any, label: str) -> float:
    number = float(value)
    require(math.isfinite(number), f"{label}必须为有限数")
    return number


def metric_lookup(summary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    curves = summary.get("curves")
    require(isinstance(curves, list), "严格评价摘要缺少curves")
    result: dict[str, dict[str, Any]] = {}
    for row in curves:
        require(isinstance(row, dict), "严格评价curves元素不是对象")
        curve_id = str(row.get("curve_id", ""))
        require(curve_id in CURVE_IDS and curve_id not in result, f"严格评价curve_id非法或重复：{curve_id}")
        result[curve_id] = row
    require(set(result) == set(CURVE_IDS), "严格评价摘要未恰好覆盖六曲线")
    return result


def rank_key(candidate_row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(candidate_row["failed_route_count"]),
        int(candidate_row["total_abs_boundary_point_count_error"]),
        int(candidate_row["total_set_difference_count"]),
        int(candidate_row["total_point_levenshtein_original"]),
        float(candidate_row["maximum_symmetric_hausdorff_steps"]),
        float(candidate_row["sum_symmetric_hausdorff_steps"]),
        int(candidate_row["total_endpoint_l1_error_steps_original"]),
        int(candidate_row["total_axis_prefix_intercept_error_samples"]),
        str(candidate_row["candidate_id"]).casefold(),
    )


def evaluate_candidate(
    candidate: CandidateSource,
    output_root: Path,
    strict_evaluator: Path,
    target_path: Path,
    matlab_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    # 当前项目根路径较长；物理工件目录使用稳定短哈希，避免 Windows MAX_PATH
    # 影响 MATLAB/Python 边界提取。完整 candidate_id 仍保存在清单与汇总中。
    artifact_token = canonical_sha256(
        {
            "candidate_id": candidate.candidate_id,
            "contract_id": candidate.contract_id,
            "input_root": str(candidate.input_root),
        }
    )[:10].lower()
    candidate_dir = output_root / f"c_{artifact_token}"
    candidate_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = candidate_dir / "m.json"
    build_strict_manifest(candidate, manifest_path)

    mask_stats: dict[str, MaskStats] = {}
    for spec in CURVE_SPECS:
        _, stats = load_mask(candidate.masks[spec.curve_id])
        mask_stats[spec.curve_id] = stats

    strict_output = candidate_dir / "e"
    summary, returncode = run_strict_evaluator(
        strict_evaluator,
        manifest_path,
        target_path,
        matlab_path,
        strict_output,
    )
    require(summary.get("candidate_id") == candidate.candidate_id, "严格评价candidate_id被改写")
    metrics = metric_lookup(summary)
    set_counts = set_difference_counts(strict_output / "set_differences.csv")

    curve_rows: list[dict[str, Any]] = []
    topology_violations: list[str] = []
    for spec in CURVE_SPECS:
        metric = metrics[spec.curve_id]
        stats = mask_stats[spec.curve_id]
        topology = metric.get("mask_metadata")
        require(isinstance(topology, dict), f"严格评价未返回掩膜拓扑：{spec.curve_id}")
        component_count = int(topology.get("component_count_8_connected", -1))
        hole_pixel_count = int(topology.get("hole_pixel_count", -1))
        returned_boundary_count = int(topology.get("returned_boundary_count", -1))
        topology_ok = component_count == 1 and hole_pixel_count == 0 and returned_boundary_count == 1
        if not topology_ok:
            topology_violations.append(
                f"{spec.curve_id}:components={component_count},holes={hole_pixel_count},boundaries={returned_boundary_count}"
            )
        route_input = candidate.route_inputs[spec.curve_id]
        right_prefix = stats.tau1_axis_origin_prefix_last_index
        top_prefix = stats.tau2_axis_origin_prefix_last_index
        right_any = stats.tau1_axis_rightmost_stable_index
        top_any = stats.tau2_axis_highest_stable_index
        target_right = int(metric["target_start_endpoint"][0]) - 1
        target_top = int(metric["target_end_endpoint"][1]) - 1
        curve_rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "contract_id": candidate.contract_id,
                "input_mode": candidate.input_mode,
                "curve_id": spec.curve_id,
                "route_id": candidate.route_ids[spec.curve_id],
                "division": spec.division,
                "method": spec.method,
                "strict_curve_status": metric["strict_curve_status"],
                "stable_point_count": stats.stable_point_count,
                "mask_rows": stats.rows,
                "mask_columns": stats.columns,
                "mask_sha256": stats.sha256,
                "component_count_8_connected": component_count,
                "hole_pixel_count": hole_pixel_count,
                "returned_boundary_count": returned_boundary_count,
                "topology_ranking_gate": "PASS" if topology_ok else "REJECTED",
                "route_input_fingerprint": route_input["route_input_fingerprint"],
                "blind_manifest_sha256": route_input["manifest_sha256"],
                "checkpoint_sha256": route_input["checkpoint_sha256"],
                "points_sha256": route_input["points_sha256"],
                "grid_axes_sha256": route_input["grid_axes_sha256"],
                "route_summary_sha256": route_input["route_summary_sha256"],
                "bundle_sha256": route_input["bundle_sha256"],
                "route_operator_sha256": route_input["route_operator_sha256"],
                "tau1_axis_origin_prefix_last_index": right_prefix,
                "tau1_axis_origin_prefix_intercept_ms": "" if right_prefix < 0 else right_prefix * MS_PER_SAMPLE,
                "tau2_axis_origin_prefix_last_index": top_prefix,
                "tau2_axis_origin_prefix_intercept_ms": "" if top_prefix < 0 else top_prefix * MS_PER_SAMPLE,
                "target_tau1_axis_intercept_index": target_right,
                "target_tau1_axis_intercept_ms": target_right * MS_PER_SAMPLE,
                "target_tau2_axis_intercept_index": target_top,
                "target_tau2_axis_intercept_ms": target_top * MS_PER_SAMPLE,
                "tau1_axis_prefix_intercept_error_samples": abs(right_prefix - target_right),
                "tau2_axis_prefix_intercept_error_samples": abs(top_prefix - target_top),
                "tau1_axis_rightmost_stable_index": right_any,
                "tau1_axis_rightmost_stable_ms": "" if right_any < 0 else right_any * MS_PER_SAMPLE,
                "tau2_axis_highest_stable_index": top_any,
                "tau2_axis_highest_stable_ms": "" if top_any < 0 else top_any * MS_PER_SAMPLE,
                "tau1_axis_hole_count_before_rightmost": stats.tau1_axis_hole_count_before_rightmost,
                "tau2_axis_hole_count_before_highest": stats.tau2_axis_hole_count_before_highest,
                "target_boundary_point_count": int(metric["target_point_count"]),
                "candidate_boundary_point_count": int(metric["candidate_point_count"]),
                "boundary_point_count_signed_error": int(metric["candidate_point_count"]) - int(metric["target_point_count"]),
                "boundary_point_count_abs_error": abs(int(metric["candidate_point_count"]) - int(metric["target_point_count"])),
                "set_difference_count": set_counts[spec.curve_id],
                "ordered_exact_original": bool(metric["ordered_exact_original"]),
                "set_exact": bool(metric["set_exact"]),
                "start_endpoint_exact": bool(metric["start_endpoint_exact"]),
                "end_endpoint_exact": bool(metric["end_endpoint_exact"]),
                "candidate_start_endpoint": json.dumps(metric["candidate_start_endpoint"], separators=(",", ":")),
                "candidate_end_endpoint": json.dumps(metric["candidate_end_endpoint"], separators=(",", ":")),
                "target_start_endpoint": json.dumps(metric["target_start_endpoint"], separators=(",", ":")),
                "target_end_endpoint": json.dumps(metric["target_end_endpoint"], separators=(",", ":")),
                "endpoint_l1_error_steps_original": int(metric["endpoint_l1_error_steps_original"]),
                "symmetric_hausdorff_steps": finite_number(metric["symmetric_hausdorff_steps"], "Hausdorff"),
                "symmetric_hausdorff_ms": finite_number(metric["symmetric_hausdorff_ms"], "Hausdorff ms"),
                "point_levenshtein_original": int(metric["point_levenshtein_original"]),
                "ordered_candidate_to_target_ms_max_abs_error": (
                    ""
                    if metric["ordered_candidate_to_target_ms_max_abs_error"] is None
                    else finite_number(metric["ordered_candidate_to_target_ms_max_abs_error"], "ms误差")
                ),
                "mask_path": str(stats.path),
            }
        )

    failed = sum(row["strict_curve_status"] != "PASS" for row in curve_rows)
    candidate_row: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "contract_id": candidate.contract_id,
        "input_mode": candidate.input_mode,
        "input_root": str(candidate.input_root),
        "source_manifest": "" if candidate.source_manifest is None else str(candidate.source_manifest),
        "strict_overall_status": summary["overall_status"],
        "strict_evaluator_returncode": returncode,
        "ranking_eligibility_status": "ELIGIBLE" if not topology_violations else "REJECTED_TOPOLOGY",
        "topology_violation_count": len(topology_violations),
        "topology_violations_json": json.dumps(topology_violations, ensure_ascii=False, separators=(",", ":")),
        "strict_curve_pass_count": len(curve_rows) - failed,
        "failed_route_count": failed,
        "candidate_total_boundary_point_count": sum(int(row["candidate_boundary_point_count"]) for row in curve_rows),
        "target_total_boundary_point_count": sum(int(row["target_boundary_point_count"]) for row in curve_rows),
        "total_abs_boundary_point_count_error": sum(int(row["boundary_point_count_abs_error"]) for row in curve_rows),
        "total_set_difference_count": sum(int(row["set_difference_count"]) for row in curve_rows),
        "total_point_levenshtein_original": sum(int(row["point_levenshtein_original"]) for row in curve_rows),
        "maximum_symmetric_hausdorff_steps": max(float(row["symmetric_hausdorff_steps"]) for row in curve_rows),
        "sum_symmetric_hausdorff_steps": sum(float(row["symmetric_hausdorff_steps"]) for row in curve_rows),
        "total_endpoint_l1_error_steps_original": sum(int(row["endpoint_l1_error_steps_original"]) for row in curve_rows),
        "total_axis_prefix_intercept_error_samples": sum(
            int(row["tau1_axis_prefix_intercept_error_samples"])
            + int(row["tau2_axis_prefix_intercept_error_samples"])
            for row in curve_rows
        ),
        "total_stable_point_count": sum(int(row["stable_point_count"]) for row in curve_rows),
        "strict_manifest_path": str(manifest_path),
        "strict_manifest_sha256": sha256_file(manifest_path),
        "strict_summary_path": str(strict_output / "strict_evaluation_summary.json"),
        "strict_summary_sha256": sha256_file(strict_output / "strict_evaluation_summary.json"),
    }
    for row in curve_rows:
        suffix = row["curve_id"]
        candidate_row[f"stable_points__{suffix}"] = row["stable_point_count"]
        candidate_row[f"tau1_intercept_index__{suffix}"] = row["tau1_axis_origin_prefix_last_index"]
        candidate_row[f"tau1_intercept_ms__{suffix}"] = row["tau1_axis_origin_prefix_intercept_ms"]
        candidate_row[f"tau2_intercept_index__{suffix}"] = row["tau2_axis_origin_prefix_last_index"]
        candidate_row[f"tau2_intercept_ms__{suffix}"] = row["tau2_axis_origin_prefix_intercept_ms"]

    pass_ids = tuple(row["curve_id"] for row in curve_rows if row["strict_curve_status"] == "PASS")
    regression_check = {
        "applicable": candidate.input_mode == "STRICT_MANIFEST_REGRESSION_ROOT",
        "expected_pass_curve_ids": list(EXPECTED_REGRESSION_PASS_CURVES),
        "actual_pass_curve_ids": list(pass_ids),
        "expected_failed_route_count": 4,
        "actual_failed_route_count": failed,
        "status": (
            "PASS"
            if candidate.input_mode == "STRICT_MANIFEST_REGRESSION_ROOT"
            and pass_ids == EXPECTED_REGRESSION_PASS_CURVES
            and failed == 4
            else "NOT_APPLICABLE"
            if candidate.input_mode != "STRICT_MANIFEST_REGRESSION_ROOT"
            else "FAIL"
        ),
    }
    return candidate_row, curve_rows, regression_check


CANDIDATE_BASE_FIELDS = (
    "rank",
    "candidate_id",
    "contract_id",
    "input_mode",
    "ranking_eligibility_status",
    "topology_violation_count",
    "topology_violations_json",
    "strict_overall_status",
    "strict_curve_pass_count",
    "failed_route_count",
    "candidate_total_boundary_point_count",
    "target_total_boundary_point_count",
    "total_abs_boundary_point_count_error",
    "total_set_difference_count",
    "total_point_levenshtein_original",
    "maximum_symmetric_hausdorff_steps",
    "sum_symmetric_hausdorff_steps",
    "total_endpoint_l1_error_steps_original",
    "total_axis_prefix_intercept_error_samples",
    "total_stable_point_count",
    "ranking_key_json",
)

CURVE_FIELDS = (
    "batch_sha256",
    "rank",
    "candidate_id",
    "contract_id",
    "input_mode",
    "curve_id",
    "route_id",
    "division",
    "method",
    "strict_curve_status",
    "stable_point_count",
    "mask_rows",
    "mask_columns",
    "mask_sha256",
    "component_count_8_connected",
    "hole_pixel_count",
    "returned_boundary_count",
    "topology_ranking_gate",
    "route_input_fingerprint",
    "blind_manifest_sha256",
    "checkpoint_sha256",
    "points_sha256",
    "grid_axes_sha256",
    "route_summary_sha256",
    "bundle_sha256",
    "route_operator_sha256",
    "tau1_axis_origin_prefix_last_index",
    "tau1_axis_origin_prefix_intercept_ms",
    "tau2_axis_origin_prefix_last_index",
    "tau2_axis_origin_prefix_intercept_ms",
    "target_tau1_axis_intercept_index",
    "target_tau1_axis_intercept_ms",
    "target_tau2_axis_intercept_index",
    "target_tau2_axis_intercept_ms",
    "tau1_axis_prefix_intercept_error_samples",
    "tau2_axis_prefix_intercept_error_samples",
    "tau1_axis_rightmost_stable_index",
    "tau1_axis_rightmost_stable_ms",
    "tau2_axis_highest_stable_index",
    "tau2_axis_highest_stable_ms",
    "tau1_axis_hole_count_before_rightmost",
    "tau2_axis_hole_count_before_highest",
    "target_boundary_point_count",
    "candidate_boundary_point_count",
    "boundary_point_count_signed_error",
    "boundary_point_count_abs_error",
    "set_difference_count",
    "ordered_exact_original",
    "set_exact",
    "start_endpoint_exact",
    "end_endpoint_exact",
    "candidate_start_endpoint",
    "candidate_end_endpoint",
    "target_start_endpoint",
    "target_end_endpoint",
    "endpoint_l1_error_steps_original",
    "symmetric_hausdorff_steps",
    "symmetric_hausdorff_ms",
    "point_levenshtein_original",
    "ordered_candidate_to_target_ms_max_abs_error",
    "mask_path",
)


def compact_candidate_for_hash(row: Mapping[str, Any], curve_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "rank": None if row["rank"] == "" else int(row["rank"]),
        "candidate_id": row["candidate_id"],
        "contract_id": row["contract_id"],
        "input_mode": row["input_mode"],
        "ranking_eligibility_status": row["ranking_eligibility_status"],
        "topology_violations_json": row["topology_violations_json"],
        "strict_overall_status": row["strict_overall_status"],
        "ranking_key": None if row["ranking_key_json"] == "" else json.loads(str(row["ranking_key_json"])),
        "curves": [
            {
                "curve_id": curve["curve_id"],
                "route_id": curve["route_id"],
                "strict_curve_status": curve["strict_curve_status"],
                "mask_sha256": curve["mask_sha256"],
                "route_input_fingerprint": curve["route_input_fingerprint"],
                "component_count_8_connected": int(curve["component_count_8_connected"]),
                "hole_pixel_count": int(curve["hole_pixel_count"]),
                "returned_boundary_count": int(curve["returned_boundary_count"]),
                "stable_point_count": int(curve["stable_point_count"]),
                "tau1_axis_origin_prefix_last_index": int(curve["tau1_axis_origin_prefix_last_index"]),
                "tau2_axis_origin_prefix_last_index": int(curve["tau2_axis_origin_prefix_last_index"]),
                "tau1_axis_rightmost_stable_index": int(curve["tau1_axis_rightmost_stable_index"]),
                "tau2_axis_highest_stable_index": int(curve["tau2_axis_highest_stable_index"]),
                "candidate_boundary_point_count": int(curve["candidate_boundary_point_count"]),
                "set_difference_count": int(curve["set_difference_count"]),
                "symmetric_hausdorff_steps": float(curve["symmetric_hausdorff_steps"]),
                "point_levenshtein_original": int(curve["point_levenshtein_original"]),
                "endpoint_l1_error_steps_original": int(curve["endpoint_l1_error_steps_original"]),
            }
            for curve in curve_rows
            if curve["candidate_id"] == row["candidate_id"]
        ],
    }


def evaluate_batch(args: argparse.Namespace) -> dict[str, Any]:
    strict_evaluator = args.strict_evaluator.resolve()
    matlab_helper = strict_evaluator.parent / "fig10_extract_mask_boundaries.m"
    target_path = args.target.resolve()
    matlab_path = args.matlab.resolve()
    output_root = args.output_dir.resolve()
    input_roots = [path.resolve() for path in args.input_root]
    allowed_contract_ids = resolve_contract_ids(args.contract_id)

    require(strict_evaluator.is_file(), f"严格评价器不存在：{strict_evaluator}")
    require(matlab_helper.is_file(), f"MATLAB边界提取器不存在：{matlab_helper}")
    require(target_path.is_file(), f"冻结目标MAT不存在：{target_path}")
    require(matlab_path.is_file(), f"MATLAB可执行文件不存在：{matlab_path}")
    require(len(input_roots) == len(set(input_roots)), "--input-root包含重复路径")
    require(
        all(not is_under(output_root, root) for root in input_roots),
        "评价输出目录不得位于任何盲算输入根内",
    )
    if output_root.exists():
        require(output_root.is_dir(), f"输出路径已存在且不是目录：{output_root}")
        require(not any(output_root.iterdir()), f"输出目录必须不存在或为空：{output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    candidates: list[CandidateSource] = []
    for root in input_roots:
        candidates.extend(discover_input_root(root, allowed_contract_ids))
    make_unique_candidate_ids(candidates)
    candidates.sort(key=lambda item: (str(item.input_root).casefold(), item.contract_id, item.candidate_id.casefold()))

    candidate_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    regression_checks: list[dict[str, Any]] = []
    target_hashes: set[str] = set()
    evaluator_hashes: set[str] = set()
    for candidate in candidates:
        candidate_row, candidate_curves, regression = evaluate_candidate(
            candidate,
            output_root,
            strict_evaluator,
            target_path,
            matlab_path,
        )
        strict_summary = read_json(Path(candidate_row["strict_summary_path"]))
        target_hashes.add(str(strict_summary["target"]["sha256"]).upper())
        evaluator_hashes.add(str(strict_summary["evaluator"]["sha256"]).upper())
        candidate_rows.append(candidate_row)
        curve_rows.extend(candidate_curves)
        regression_checks.append({"candidate_id": candidate.candidate_id, **regression})

    require(len(target_hashes) == 1, f"批次各候选目标哈希不一致：{sorted(target_hashes)}")
    require(len(evaluator_hashes) == 1, f"批次各候选严格评价器哈希不一致：{sorted(evaluator_hashes)}")
    require(next(iter(evaluator_hashes)) == sha256_file(strict_evaluator), "严格评价器运行哈希与现场文件不一致")

    eligible_rows = [row for row in candidate_rows if row["ranking_eligibility_status"] == "ELIGIBLE"]
    rejected_rows = [row for row in candidate_rows if row["ranking_eligibility_status"] != "ELIGIBLE"]
    eligible_rows.sort(key=rank_key)
    rejected_rows.sort(key=lambda row: str(row["candidate_id"]).casefold())
    rank_by_id: dict[str, int | str] = {}
    for rank, row in enumerate(eligible_rows, start=1):
        row["rank"] = rank
        row["ranking_key_json"] = json.dumps(list(rank_key(row)), ensure_ascii=False, separators=(",", ":"))
        rank_by_id[str(row["candidate_id"])] = rank
    for row in rejected_rows:
        row["rank"] = ""
        row["ranking_key_json"] = ""
        rank_by_id[str(row["candidate_id"])] = ""
    candidate_rows = eligible_rows + rejected_rows
    rejected_order = {str(row["candidate_id"]): index for index, row in enumerate(rejected_rows)}
    curve_rows.sort(
        key=lambda row: (
            0 if rank_by_id[str(row["candidate_id"])] != "" else 1,
            rank_by_id[str(row["candidate_id"])] if rank_by_id[str(row["candidate_id"])] != "" else rejected_order[str(row["candidate_id"])],
            CURVE_IDS.index(str(row["curve_id"])),
        )
    )
    for row in curve_rows:
        row["rank"] = rank_by_id[str(row["candidate_id"])]

    hash_payload = {
        "schema_version": BATCH_SCHEMA,
        "ranking_fields": list(RANKING_FIELDS),
        "target_sha256": next(iter(target_hashes)),
        "strict_evaluator_sha256": next(iter(evaluator_hashes)),
        "matlab_boundary_helper_sha256": sha256_file(matlab_helper),
        "candidates": [
            compact_candidate_for_hash(row, curve_rows)
            for row in candidate_rows
        ],
    }
    batch_sha256 = canonical_sha256(hash_payload)
    for row in curve_rows:
        row["batch_sha256"] = batch_sha256

    candidate_fields = (
        "batch_sha256",
        *CANDIDATE_BASE_FIELDS,
        *tuple(f"stable_points__{curve_id}" for curve_id in CURVE_IDS),
        *tuple(f"tau1_intercept_index__{curve_id}" for curve_id in CURVE_IDS),
        *tuple(f"tau1_intercept_ms__{curve_id}" for curve_id in CURVE_IDS),
        *tuple(f"tau2_intercept_index__{curve_id}" for curve_id in CURVE_IDS),
        *tuple(f"tau2_intercept_ms__{curve_id}" for curve_id in CURVE_IDS),
        "input_root",
        "source_manifest",
        "strict_manifest_path",
        "strict_manifest_sha256",
        "strict_summary_path",
        "strict_summary_sha256",
    )
    for row in candidate_rows:
        row["batch_sha256"] = batch_sha256
    write_csv(output_root / "candidate_ranking.csv", candidate_fields, candidate_rows)
    write_csv(output_root / "curve_metrics.csv", CURVE_FIELDS, curve_rows)

    input_hash_rows = []
    for row in curve_rows:
        input_hash_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "contract_id": row["contract_id"],
                "curve_id": row["curve_id"],
                "route_id": row["route_id"],
                "mask_path": row["mask_path"],
                "bytes": Path(str(row["mask_path"])).stat().st_size,
                "sha256": row["mask_sha256"],
            }
        )
    write_csv(
        output_root / "input_mask_hashes.csv",
        ("candidate_id", "contract_id", "curve_id", "route_id", "mask_path", "bytes", "sha256"),
        input_hash_rows,
    )
    route_input_fields = (
        "candidate_id",
        "contract_id",
        "curve_id",
        "route_id",
        "route_input_fingerprint",
        "blind_manifest_sha256",
        "checkpoint_sha256",
        "points_sha256",
        "mask_sha256",
        "grid_axes_sha256",
        "route_summary_sha256",
        "bundle_sha256",
        "route_operator_sha256",
    )
    write_csv(output_root / "route_input_fingerprints.csv", route_input_fields, curve_rows)

    applicable_regressions = [row for row in regression_checks if row["applicable"]]
    regression_status = (
        "NOT_APPLICABLE"
        if not applicable_regressions
        else "PASS"
        if all(row["status"] == "PASS" for row in applicable_regressions)
        else "FAIL"
    )
    summary = {
        "schema_version": BATCH_SCHEMA,
        "status": "PASS" if regression_status in {"PASS", "NOT_APPLICABLE"} else "FAIL",
        "evidence_label": "目标引导的校准计算复现",
        "claim_boundary": "排名结果不证明已恢复作者原始参数合同。",
        "independence_contract": {
            "blind_solver_imported": False,
            "blind_solver_executed": False,
            "parameter_search_executed": False,
            "target_mat_opened_by_batch_bridge": False,
            "target_mat_reader": str(strict_evaluator),
            "matlab_boundary_helper": str(matlab_helper),
        },
        "input_root_count": len(input_roots),
        "contract_allowlist": {
            "mode": "DEFAULT_B1_B2_B3" if args.contract_id is None else "EXPLICIT_CLI",
            "allowed_contract_ids": list(allowed_contract_ids),
        },
        "candidate_count": len(candidate_rows),
        "ranking_eligible_candidate_count": len(eligible_rows),
        "ranking_rejected_candidate_count": len(rejected_rows),
        "strict_pass_candidate_count": sum(row["strict_overall_status"] == "PASS" for row in candidate_rows),
        "strict_fail_candidate_count": sum(row["strict_overall_status"] == "FAIL" for row in candidate_rows),
        "target_sha256_reported_by_strict_evaluator": next(iter(target_hashes)),
        "strict_evaluator_sha256": next(iter(evaluator_hashes)),
        "matlab_boundary_helper_sha256": sha256_file(matlab_helper),
        "ranking": {
            "direction": "ASCENDING_LEXICOGRAPHIC",
            "fields": list(RANKING_FIELDS),
            "tie_breaker": "candidate_id.casefold()",
        },
        "axis_intercept_contract": {
            "primary": "origin-connected contiguous stable prefix last zero-based sample index",
            "tau1_axis": "mask row l_samples=0; scan j_samples from 0 until first unstable cell",
            "tau2_axis": "mask column j_samples=0; scan l_samples from 0 until first unstable cell",
            "conversion": "tau_ms=zero_based_sample_index*1000/1024",
            "diagnostic": "also report farthest stable index and holes before it",
        },
        "batch_sha256": batch_sha256,
        "batch_hash_contract": "SHA-256 of canonical path-independent target/evaluator/helper hashes, ranking definition, ranked candidate metrics and six mask hashes",
        "regression_interface_status": regression_status,
        "regression_checks": regression_checks,
        "candidates": candidate_rows,
        "outputs": {
            "candidate_ranking_csv": str(output_root / "candidate_ranking.csv"),
            "curve_metrics_csv": str(output_root / "curve_metrics.csv"),
            "input_mask_hashes_csv": str(output_root / "input_mask_hashes.csv"),
            "route_input_fingerprints_csv": str(output_root / "route_input_fingerprints.csv"),
        },
    }
    write_json(output_root / "batch_evaluation_summary.json", summary)

    artifact_rows = []
    artifact_manifest = output_root / "artifact_hashes.csv"
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.resolve() != artifact_manifest.resolve():
            artifact_rows.append(
                {
                    "path": path.relative_to(output_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_csv(artifact_manifest, ("path", "bytes", "sha256"), artifact_rows)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        action="append",
        required=True,
        help="盲算full-grid输出根；可重复。回归测试时也可给现有严格manifest目录。",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="必须不存在或为空的评价输出目录")
    parser.add_argument(
        "--contract-id",
        action="append",
        default=None,
        help=(
            "标准盲算根允许的合同ID；可重复且区分大小写。"
            "未给时默认B1/B2/B3；给出时用显式列表取代默认列表。"
        ),
    )
    parser.add_argument(
        "--strict-evaluator",
        type=Path,
        default=DEFAULT_STRICT_EVALUATOR,
        help="现有 strict_target_evaluator.py",
    )
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="冻结 plotted_data.mat")
    parser.add_argument("--matlab", type=Path, default=DEFAULT_MATLAB, help="MATLAB可执行文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    try:
        summary = evaluate_batch(args)
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "candidate_count": summary["candidate_count"],
                    "strict_pass_candidate_count": summary["strict_pass_candidate_count"],
                    "contract_allowlist": summary["contract_allowlist"],
                    "regression_interface_status": summary["regression_interface_status"],
                    "batch_sha256": summary["batch_sha256"],
                    "output_dir": str(output_dir),
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )
        return 0 if summary["status"] == "PASS" else 1
    except Exception as exc:
        error = {
            "schema_version": BATCH_SCHEMA,
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(output_dir / "batch_evaluation_error.json", error)
        except Exception:
            pass
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
