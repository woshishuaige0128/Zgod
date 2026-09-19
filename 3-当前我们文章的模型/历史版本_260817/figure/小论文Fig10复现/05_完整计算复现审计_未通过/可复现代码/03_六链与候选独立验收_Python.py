#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块20最小步骤8C独立验收。

本验证器不导入任何步骤8B/8C生成器。它从磁盘重新读取冻结合同、MATLAB
v7.3六链结果和Python候选包，独立重算矩阵身份、CARE闭环、逐路线al、
零时滞Laurent同幂次闭合及历史Guyan Petrov双基关系。
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from scipy.io import loadmat


SCRIPT_DIR = Path(__file__).resolve().parent
BOARD_DIR = SCRIPT_DIR.parent
PYTHON_GENERATOR = SCRIPT_DIR / "build_board20_step8c_candidate_bundles.py"
MATLAB_GENERATOR = SCRIPT_DIR / "build_board20_step8c_routes_matlab.m"

STEP8B_DIR = BOARD_DIR / "outputs" / "step8b_论文代码矩阵合同"
CONTRACT_MAT = STEP8B_DIR / "步骤8B_基础矩阵与选择矩阵.mat"
CONTRACT_MANIFEST = STEP8B_DIR / "步骤8B工件清单.csv"
CANDIDATE_CONTRACT = STEP8B_DIR / "有限候选整链清单.csv"

MATLAB_DIR = BOARD_DIR / "outputs" / "step8c_六链模型生成" / "matlab"
MATLAB_SUMMARY = MATLAB_DIR / "步骤8C_六链模型汇总.mat"
MATLAB_PETROV_CSV = MATLAB_DIR / "Guyan历史单边Petrov门禁.csv"
PYTHON_DIR = BOARD_DIR / "outputs" / "step8c_六链模型生成" / "python"
PYTHON_INDEX = PYTHON_DIR / "六路线六候选索引.csv"
PYTHON_METADATA = PYTHON_DIR / "候选包元数据.json"
VALIDATION_DIR = BOARD_DIR / "outputs" / "step8c_六链模型生成" / "validation"

DIV1_WORKSPACE = (
    BOARD_DIR
    / "outputs"
    / "step2_runs"
    / "main_ori_div1"
    / "original_mlx"
    / "rep03"
    / "workspace"
    / "workspace_complete.mat"
)
DIV2_WORKSPACE = (
    BOARD_DIR
    / "outputs"
    / "step2_runs"
    / "main_ori_div2"
    / "original_mlx"
    / "rep03"
    / "workspace"
    / "workspace_complete.mat"
)
THESIS_PDF = BOARD_DIR.parents[3] / "梁禹手稿.pdf"

EXPECTED_HASHES = {
    CONTRACT_MAT: "261852003eea79a6c7c609c472e82b8782bb7619191c2cfa3759ac39efcc80ff",
    DIV1_WORKSPACE: "e0fff9b1b0cff5db7013fe888d8a5957d3ac8776952ea40446109fe5a1c35923",
    DIV2_WORKSPACE: "7781807f01b9d95ca9554f3ae5449065c4deb4c2ff8ffc62679e08bec8757061",
    THESIS_PDF: "dda04ce3dbff6a5dce33e6a7d07191f5a33d27f025174087ee395dfe4cf9d5d1",
}
EXPECTED_PYTHON_GENERATOR_SHA256 = "b3f09be226275994cd2a570b81a8a19e59dd0e0a7da96fac904ea9e0201f053a"
EXPECTED_CANDIDATE_NAMES = {
    "R01": "论文CARE_alpha025_广义力",
    "R02": "论文CARE_alpha025_加速度",
    "R03": "论文CARE_矩阵al_广义力",
    "R04": "论文CARE_矩阵al_加速度",
    "R05": "作者DARE规则外推_逐路线矩阵al",
    "R06": "作者无LQR规则外推_逐路线矩阵al",
}

EXPECTED_DIMS = {
    (1, "Original"): 15,
    (1, "Guyan"): 6,
    (1, "Craig_Bampton"): 9,
    (2, "Original"): 15,
    (2, "Guyan"): 5,
    (2, "Craig_Bampton"): 8,
}
METHOD_INDEX = {"Original": 1, "Guyan": 2, "Craig_Bampton": 3}
FORMULA_CANDIDATES = {"R01", "R02", "R03", "R04"}
DIAGNOSTIC_CANDIDATES = {"R05", "R06"}
GUYAN_MASTER = {1: (0, 5, 10, 3, 8, 13), 2: (0, 10, 3, 8, 13)}
CARE_Q = np.diag([1.0e6, 1.0e6, 1.0e4, 1.0e4])
CARE_R = np.diag([1.0e-2, 1.0e-2])
TOL = 1.0e-12
COMPLEX_PROBE_TOL = 1.0e-11
DELAY_PROBE_POINTS = ((0, 0), (1, 0), (0, 1), (1, 1), (3, 7), (30, 66))
COMPLEX_Z_PROBES = (
    0.99 * np.exp(1j * 0.23),
    1.01 * np.exp(-1j * 0.41),
    0.995 * np.exp(1j * 1.07),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel_error(actual: np.ndarray, expected: np.ndarray) -> float:
    actual_array = np.asarray(actual)
    expected_array = np.asarray(expected)
    denominator = max(float(np.linalg.norm(expected_array.ravel())), np.finfo(float).eps)
    return float(np.linalg.norm((actual_array - expected_array).ravel()) / denominator)


def scalar(value: Any) -> float:
    return float(np.asarray(value, dtype=np.float64).reshape(-1)[0])


def integer(value: Any) -> int:
    return int(round(scalar(value)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def snapshot_tree(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, sha256_file(path))
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def run_python_generator_twice() -> tuple[list[dict[str, Any]], str, str]:
    """以子进程运行，不导入生成器；比较两轮完整输出树。"""
    generator_hash_before = sha256_file(PYTHON_GENERATOR)
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    snapshots: list[dict[str, tuple[int, str]]] = []
    stdout_parts: list[str] = []
    for run_number in (1, 2):
        completed = subprocess.run(
            [sys.executable, str(PYTHON_GENERATOR)],
            cwd=BOARD_DIR.parents[1],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        stdout_parts.append(f"RUN{run_number}\n{completed.stdout.strip()}")
        snapshots.append(snapshot_tree(PYTHON_DIR))
    generator_hash_after = sha256_file(PYTHON_GENERATOR)

    all_paths = sorted(set(snapshots[0]) | set(snapshots[1]))
    rows: list[dict[str, Any]] = []
    for relative_path in all_paths:
        first = snapshots[0].get(relative_path)
        second = snapshots[1].get(relative_path)
        rows.append(
            {
                "relative_path": relative_path,
                "run1_bytes": "" if first is None else first[0],
                "run1_sha256": "" if first is None else first[1],
                "run2_bytes": "" if second is None else second[0],
                "run2_sha256": "" if second is None else second[1],
                "byte_identical": first is not None and first == second,
            }
        )
    return rows, generator_hash_before, generator_hash_after


def matlab_class(obj: h5py.Dataset) -> str:
    value = obj.attrs.get("MATLAB_class", b"")
    if isinstance(value, np.ndarray):
        value = value.reshape(-1)[0]
    if isinstance(value, bytes):
        return value.decode("ascii", errors="ignore")
    return str(value)


def read_h5_object(handle: h5py.File, obj: h5py.Group | h5py.Dataset) -> Any:
    """读取本任务所需的MATLAB v7.3标量、字符、cell和struct。"""
    if isinstance(obj, h5py.Group):
        return {name: read_h5_object(handle, child) for name, child in obj.items()}

    raw = np.asarray(obj)
    if matlab_class(obj) == "char":
        return "".join(chr(int(code)) for code in raw.ravel(order="F") if int(code) != 0)
    if raw.dtype.kind == "O":
        values = [read_h5_object(handle, handle[reference]) for reference in raw.ravel(order="F")]
        return values[0] if len(values) == 1 else values
    if raw.ndim >= 2:
        raw = np.transpose(raw, axes=tuple(reversed(range(raw.ndim))))
    return raw


def load_matlab_struct_array(path: Path, group_name: str) -> list[dict[str, Any]]:
    with h5py.File(path, "r") as handle:
        group = handle[group_name]
        first_field = next(iter(group.values()))
        count = int(first_field.shape[0] * first_field.shape[1])
        structures = [dict() for _ in range(count)]
        for field_name, dataset in group.items():
            references = np.asarray(dataset).ravel(order="F")
            if len(references) != count:
                raise RuntimeError(f"MATLAB结构字段长度不一致：{field_name}")
            for index, reference in enumerate(references):
                structures[index][field_name] = read_h5_object(handle, handle[reference])
        return structures


def ast_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = ast_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def audit_generator_inputs(path: Path) -> tuple[bool, dict[str, Any]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    loadmat_calls = [node for node in calls if ast_call_name(node.func).endswith("loadmat")]
    loadmat_arguments = [ast.unparse(node.args[0]) if node.args else "" for node in loadmat_calls]
    forbidden_readers = {
        "np.load",
        "numpy.load",
        "pandas.read_csv",
        "pd.read_csv",
        "pandas.read_excel",
        "pd.read_excel",
        "h5py.File",
        "Image.open",
        "fitz.open",
    }
    reader_hits = sorted(
        {ast_call_name(node.func) for node in calls if ast_call_name(node.func) in forbidden_readers}
    )
    imported_roots = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module or "")])
    }
    forbidden_imports = sorted(imported_roots & {"fitz", "pdfplumber", "pypdf", "PIL", "cv2"})
    passed = loadmat_arguments == ["INPUT_MAT"] and not reader_hits and not forbidden_imports
    return passed, {
        "loadmat_calls": loadmat_arguments,
        "forbidden_reader_hits": reader_hits,
        "forbidden_import_hits": forbidden_imports,
    }


def reset_validation_outputs() -> None:
    expected = (BOARD_DIR / "outputs" / "step8c_六链模型生成" / "validation").resolve()
    if VALIDATION_DIR.resolve() != expected:
        raise RuntimeError("validation输出路径安全检查失败")
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    known_outputs = (
        "步骤8C_Python确定性逐文件对比.csv",
        "步骤8C_逐包独立数值审计.csv",
        "步骤8C_独立验收检查.csv",
        "步骤8C_独立验收摘要.json",
        "步骤8C_独立验收报告.md",
        "步骤8C_独立验收工件清单.csv",
    )
    for filename in known_outputs:
        target = VALIDATION_DIR / filename
        if target.is_file():
            target.unlink()


def main() -> None:
    required_files = [
        PYTHON_GENERATOR,
        MATLAB_GENERATOR,
        CONTRACT_MAT,
        CONTRACT_MANIFEST,
        CANDIDATE_CONTRACT,
        MATLAB_SUMMARY,
        MATLAB_PETROV_CSV,
    ] + list(EXPECTED_HASHES)
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"缺少8C验收输入：{missing}")

    reset_validation_outputs()
    determinism_rows, generator_hash_before, generator_hash_after = run_python_generator_twice()
    deterministic = bool(determinism_rows) and all(row["byte_identical"] for row in determinism_rows)

    checks: list[dict[str, Any]] = []

    def add_check(category: str, check: str, passed: bool, actual: Any, expected: Any, note: str = "") -> None:
        checks.append(
            {
                "category": category,
                "check": check,
                "status": "PASS" if bool(passed) else "FAIL",
                "actual": actual,
                "expected": expected,
                "note": note,
            }
        )

    add_check(
        "确定性",
        "Python生成器连续两轮完整输出树逐文件字节一致",
        deterministic,
        f"{sum(row['byte_identical'] for row in determinism_rows)}/{len(determinism_rows)}",
        f"{len(determinism_rows)}/{len(determinism_rows)}",
    )
    add_check(
        "确定性",
        "两轮复跑期间Python生成器源码哈希不变",
        generator_hash_before == generator_hash_after,
        generator_hash_after,
        generator_hash_before,
    )
    add_check(
        "最终生成器身份",
        "Python生成器SHA-256严格等于终审封签值",
        generator_hash_before.lower() == EXPECTED_PYTHON_GENERATOR_SHA256,
        generator_hash_before,
        EXPECTED_PYTHON_GENERATOR_SHA256,
    )

    source_hash_rows: list[dict[str, Any]] = []
    for source_path, expected_hash in EXPECTED_HASHES.items():
        actual_hash = sha256_file(source_path)
        passed = actual_hash.lower() == expected_hash.lower()
        source_hash_rows.append(
            {
                "path": str(source_path),
                "actual_sha256": actual_hash,
                "expected_sha256": expected_hash,
                "pass": passed,
            }
        )
    add_check(
        "来源保护",
        "两套源工作区、步骤8B冻结MAT及硕士论文哈希不变",
        all(row["pass"] for row in source_hash_rows),
        f"{sum(row['pass'] for row in source_hash_rows)}/{len(source_hash_rows)}",
        f"{len(source_hash_rows)}/{len(source_hash_rows)}",
    )

    manifest_rows = read_csv(CONTRACT_MANIFEST)
    manifest_passes = []
    for row in manifest_rows:
        artifact = STEP8B_DIR / row["filename"]
        manifest_passes.append(
            artifact.is_file()
            and artifact.stat().st_size == int(row["bytes"])
            and sha256_file(artifact).lower() == row["sha256"].lower()
        )
    add_check(
        "来源保护",
        "步骤8B封签工件清单逐项哈希闭合",
        all(manifest_passes),
        f"{sum(manifest_passes)}/{len(manifest_passes)}",
        f"{len(manifest_passes)}/{len(manifest_passes)}",
    )

    input_audit_pass, input_audit = audit_generator_inputs(PYTHON_GENERATOR)
    add_check(
        "来源隔离",
        "Python生成器唯一数值读取为步骤8B冻结MAT且无PDF/图像/历史掩膜读取器",
        input_audit_pass,
        json.dumps(input_audit, ensure_ascii=False, sort_keys=True),
        "loadmat(INPUT_MAT)且无禁止读取器",
    )

    index_rows = read_csv(PYTHON_INDEX)
    metadata_payload = json.loads(PYTHON_METADATA.read_text(encoding="utf-8"))
    metadata_by_id = {row["bundle_id"]: row for row in metadata_payload["bundles"]}
    contract = {
        key: value
        for key, value in loadmat(CONTRACT_MAT, simplify_cells=True).items()
        if not key.startswith("__")
    }
    matlab_routes = load_matlab_struct_array(MATLAB_SUMMARY, "routes")
    matlab_route_map: dict[tuple[int, str], dict[str, Any]] = {}
    for route in matlab_routes:
        method = str(route["method"])
        normalized = "Craig_Bampton" if method == "Craig-Bampton" else method
        matlab_route_map[(integer(route["division"]), normalized)] = route

    expected_routes = set(EXPECTED_DIMS)
    matlab_route_identity = set(matlab_route_map)
    add_check(
        "六链身份",
        "MATLAB六条路线身份完整",
        matlab_route_identity == expected_routes,
        sorted(f"D{d}_{m}" for d, m in matlab_route_identity),
        sorted(f"D{d}_{m}" for d, m in expected_routes),
    )
    matlab_dimensions = {
        key: integer(route["dimension"]) for key, route in matlab_route_map.items()
    }
    add_check(
        "六链身份",
        "路线维数严格为15/6/9/15/5/8",
        matlab_dimensions == EXPECTED_DIMS,
        matlab_dimensions,
        EXPECTED_DIMS,
    )

    expected_formula_ids = {
        (division, method, candidate)
        for division, method in EXPECTED_DIMS
        for candidate in FORMULA_CANDIDATES
    }
    expected_diagnostic_ids = {
        (division, method, candidate)
        for division, method in EXPECTED_DIMS
        for candidate in DIAGNOSTIC_CANDIDATES
    }
    actual_formula_ids: set[tuple[int, str, str]] = set()
    actual_diagnostic_ids: set[tuple[int, str, str]] = set()
    bundle_rows: list[dict[str, Any]] = []
    loaded_bundles: dict[tuple[int, str, str], dict[str, Any]] = {}

    for index_row in index_rows:
        division = int(index_row["division"])
        method = index_row["method"]
        candidate = index_row["candidate_id"]
        bundle_id = index_row["bundle_id"]
        bundle_path = PYTHON_DIR / Path(index_row["relative_path"])
        metadata = metadata_by_id[bundle_id]
        payload = {
            key: value
            for key, value in loadmat(bundle_path, simplify_cells=True).items()
            if not key.startswith("__")
        }
        loaded_bundles[(division, method, candidate)] = payload
        mass = np.asarray(payload["M"], dtype=np.float64)
        damping = np.asarray(payload["C"], dtype=np.float64)
        stiffness = np.asarray(payload["K"], dtype=np.float64)
        dimension = EXPECTED_DIMS[(division, method)]
        dimension_pass = (
            mass.shape == (dimension, dimension)
            and damping.shape == mass.shape
            and stiffness.shape == mass.shape
            and integer(payload["route_dimension"]) == dimension
            and integer(payload["method_index"]) == METHOD_INDEX[method]
        )

        matlab_route = matlab_route_map[(division, method)]
        if method == "Guyan" and candidate in DIAGNOSTIC_CANDIDATES:
            matlab_base = matlab_route["guyan_historical"]
        else:
            matlab_base = matlab_route
        matlab_errors = {
            symbol: rel_error(payload[symbol], matlab_base[symbol]) for symbol in ("M", "C", "K")
        }
        matlab_base_error = max(matlab_errors.values())
        recovery_error = rel_error(payload["R"], matlab_route["R_natural"])
        selector_error = rel_error(payload["S"], matlab_route["S_psi1_psi6"])

        dt = scalar(payload["dt"])
        operator = 4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness
        expected_al = np.linalg.solve(operator, 4.0 * mass)
        al_matrix = np.asarray(payload["matrix_al"], dtype=np.float64)
        al_direct_error = rel_error(al_matrix, expected_al)
        mass_right_div_al = np.linalg.solve(al_matrix.T, mass.T).T
        al_identity_expected = mass + 0.5 * dt * damping + 0.25 * dt**2 * stiffness
        al_identity_error = rel_error(mass_right_div_al, al_identity_expected)
        al_shape_pass = al_matrix.shape == mass.shape
        if candidate in {"R01", "R02"}:
            integration_error = rel_error(payload["integration_mass_operator"], mass / 0.25)
            integration_code_pass = integer(payload["integration_mode_code"]) == 1
        else:
            integration_error = rel_error(payload["integration_mass_operator"], al_identity_expected)
            integration_code_pass = integer(payload["integration_mode_code"]) == 2

        c_left = np.asarray(payload["delay_C_left_factor"], dtype=np.float64)
        c_right = np.asarray(payload["delay_C_right_factor"], dtype=np.float64)
        k_left = np.asarray(payload["delay_K_left_factor"], dtype=np.float64)
        k_right = np.asarray(payload["delay_K_right_factor"], dtype=np.float64)
        c2 = np.asarray(payload["C2_zero_delay"], dtype=np.float64)
        k2 = np.asarray(payload["K2_zero_delay"], dtype=np.float64)
        c1 = np.asarray(payload["C1"], dtype=np.float64)
        k1 = np.asarray(payload["K1"], dtype=np.float64)
        feedback_c = np.asarray(payload["feedback_C"], dtype=np.float64)
        feedback_k = np.asarray(payload["feedback_K"], dtype=np.float64)

        delay_exp0 = np.zeros_like(mass)
        delay_expm1 = np.zeros_like(mass)
        for channel in range(2):
            delay_exp0 += np.outer(c_left[:, channel], c_right[channel, :] / dt)
            delay_exp0 += np.outer(k_left[:, channel], k_right[channel, :])
            delay_expm1 -= np.outer(c_left[:, channel], c_right[channel, :] / dt)
        direct_delay_exp0 = c2 / dt + k2
        direct_delay_expm1 = -c2 / dt
        delay_laurent_error = max(
            rel_error(delay_exp0, direct_delay_exp0),
            rel_error(delay_expm1, direct_delay_expm1),
        )
        aggregate_exp0 = c1 / dt + k1 + delay_exp0 + feedback_c / dt + feedback_k
        aggregate_expm1 = -c1 / dt + delay_expm1 - feedback_c / dt
        expected_exp0 = (damping + feedback_c) / dt + stiffness + feedback_k
        expected_expm1 = -(damping + feedback_c) / dt
        laurent_aggregate_error = max(
            rel_error(aggregate_exp0, expected_exp0),
            rel_error(aggregate_expm1, expected_expm1),
        )
        zero_delay_error = max(
            rel_error(c1 + c2, damping),
            rel_error(k1 + k2, stiffness),
            rel_error(c_left @ c_right, c2),
            rel_error(k_left @ k_right, k2),
        )

        # 完整离散Laurent式复数探针：直接矩阵式与逐幂次系数和相互独立重建。
        complex_probe_error = 0.0
        for delay_l, delay_j in DELAY_PROBE_POINTS:
            delays = (delay_l, delay_j)
            coefficients: dict[int, np.ndarray] = {}

            def add_coefficient(exponent: int, value: np.ndarray) -> None:
                if exponent not in coefficients:
                    coefficients[exponent] = np.zeros_like(mass, dtype=np.complex128)
                coefficients[exponent] += np.asarray(value, dtype=np.complex128)

            add_coefficient(0, mass / dt**2 + c1 / dt + k1 + feedback_c / dt + feedback_k)
            add_coefficient(-1, -2.0 * mass / dt**2 - c1 / dt - feedback_c / dt)
            add_coefficient(-2, mass / dt**2)
            for channel, delay in enumerate(delays):
                delayed_c = np.outer(c_left[:, channel], c_right[channel, :])
                delayed_k = np.outer(k_left[:, channel], k_right[channel, :])
                add_coefficient(-delay, delayed_k + delayed_c / dt)
                add_coefficient(-(delay + 1), -delayed_c / dt)

            for z_value in COMPLEX_Z_PROBES:
                v_value = (1.0 - z_value ** -1) / dt
                h_matrix = np.diag([z_value ** (-delay_l), z_value ** (-delay_j)])
                direct = (
                    v_value**2 * mass
                    + v_value * c1
                    + k1
                    + v_value * (c_left @ h_matrix @ c_right)
                    + k_left @ h_matrix @ k_right
                    + v_value * feedback_c
                    + feedback_k
                )
                from_laurent = sum(
                    coefficient * z_value**exponent
                    for exponent, coefficient in coefficients.items()
                )
                complex_probe_error = max(complex_probe_error, rel_error(from_laurent, direct))

        care_residual = 0.0
        gain_error = 0.0
        care_max_real = float("nan")
        care_contract_pass = True
        if candidate in FORMULA_CANDIDATES:
            actual_formula_ids.add((division, method, candidate))
            a_matrix = np.asarray(payload["A_continuous"], dtype=np.float64)
            b_matrix = np.asarray(payload["B_continuous"], dtype=np.float64)
            q_weight = np.asarray(payload["Q_control"], dtype=np.float64)
            r_weight = np.asarray(payload["R_control_weight"], dtype=np.float64)
            solution = np.asarray(payload["riccati_solution_P"], dtype=np.float64)
            gain = np.asarray(payload["controller_gain"], dtype=np.float64)
            expected_gain = np.linalg.solve(r_weight, b_matrix.T @ solution)
            gain_error = rel_error(gain, expected_gain)
            residual = (
                a_matrix.T @ solution
                + solution @ a_matrix
                - solution @ b_matrix @ np.linalg.solve(r_weight, b_matrix.T @ solution)
                + q_weight
            )
            care_residual = float(
                np.linalg.norm(residual, ord="fro")
                / max(float(np.linalg.norm(q_weight, ord="fro")), np.finfo(float).eps)
            )
            care_max_real = float(np.max(np.real(np.linalg.eigvals(a_matrix - b_matrix @ gain))))
            local_mass = np.asarray(payload["M_controller_local"], dtype=np.float64)
            local_standard_error = max(
                rel_error(payload[f"{symbol}_controller_local"], payload[f"{symbol}_local2_standard"])
                for symbol in ("M", "C", "K")
            )
            if candidate in {"R01", "R03"}:
                expected_lower_b = np.linalg.solve(local_mass, np.eye(2))
                delta_error = max(
                    rel_error(payload["DeltaK"], gain[:, :2]),
                    rel_error(payload["DeltaC"], gain[:, 2:]),
                )
                semantic_code = 1
            else:
                expected_lower_b = np.eye(2)
                delta_error = max(
                    rel_error(payload["DeltaK"], local_mass @ gain[:, :2]),
                    rel_error(payload["DeltaC"], local_mass @ gain[:, 2:]),
                )
                semantic_code = 2
            b_semantic_error = rel_error(b_matrix[2:, :], expected_lower_b)
            care_contract_pass = all(
                (
                    integer(payload["controller_type_code"]) == 1,
                    integer(payload["control_input_semantics_code"]) == semantic_code,
                    rel_error(q_weight, CARE_Q) <= TOL,
                    rel_error(r_weight, CARE_R) <= TOL,
                    local_standard_error <= TOL,
                    b_semantic_error <= TOL,
                    delta_error <= TOL,
                    gain_error <= TOL,
                    care_residual <= 1.0e-8,
                    care_max_real < 0.0,
                )
            )
        else:
            actual_diagnostic_ids.add((division, method, candidate))

        expected_formula_status = (
            "FORMULA_COHERENT_SOURCE_COMPLETION"
            if candidate in FORMULA_CANDIDATES
            else "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID"
        )
        formula_codes_pass = (
            integer(payload["formula_valid_code"]) == int(candidate in FORMULA_CANDIDATES)
            and integer(payload["paper_grid_eligible_code"]) == int(candidate in FORMULA_CANDIDATES)
            and metadata["paper_grid_eligibility"]
            == ("ELIGIBLE_SOURCE_COMPLETION" if candidate in FORMULA_CANDIDATES else "BLOCKED_DIAGNOSTIC_ONLY")
            and metadata["formula_status"] == expected_formula_status
            and index_row["formula_status"] == expected_formula_status
            and metadata["candidate_name"] == EXPECTED_CANDIDATE_NAMES[candidate]
            and index_row["candidate_name"] == EXPECTED_CANDIDATE_NAMES[candidate]
        )
        bundle_pass = all(
            (
                dimension_pass,
                matlab_base_error <= TOL,
                recovery_error <= TOL,
                selector_error <= TOL,
                al_shape_pass,
                al_direct_error <= TOL,
                al_identity_error <= TOL,
                integration_error <= TOL,
                integration_code_pass,
                zero_delay_error <= TOL,
                delay_laurent_error <= TOL,
                laurent_aggregate_error <= TOL,
                complex_probe_error <= COMPLEX_PROBE_TOL,
                care_contract_pass,
                formula_codes_pass,
            )
        )
        bundle_rows.append(
            {
                "bundle_id": bundle_id,
                "division": division,
                "method": method,
                "candidate_id": candidate,
                "dimension": dimension,
                "dimension_pass": dimension_pass,
                "matlab_python_base_max_relative_error": f"{matlab_base_error:.17g}",
                "recovery_relative_error": f"{recovery_error:.17g}",
                "selector_relative_error": f"{selector_error:.17g}",
                "matrix_al_direct_relative_error": f"{al_direct_error:.17g}",
                "matrix_al_identity_relative_error": f"{al_identity_error:.17g}",
                "integration_operator_relative_error": f"{integration_error:.17g}",
                "zero_delay_factor_max_relative_error": f"{zero_delay_error:.17g}",
                "delay_laurent_same_power_relative_error": f"{delay_laurent_error:.17g}",
                "full_laurent_same_power_relative_error": f"{laurent_aggregate_error:.17g}",
                "complex_laurent_probe_max_relative_error": f"{complex_probe_error:.17g}",
                "care_gain_relative_error": f"{gain_error:.17g}",
                "care_residual": f"{care_residual:.17g}",
                "care_closed_loop_max_real": "" if np.isnan(care_max_real) else f"{care_max_real:.17g}",
                "formula_or_diagnostic_code_pass": formula_codes_pass,
                "overall_pass": bundle_pass,
            }
        )

    bundle_count_pass = len(index_rows) == 36 and len(loaded_bundles) == 36
    add_check("候选身份", "六路线乘六候选共36个数值包且身份唯一", bundle_count_pass, len(loaded_bundles), 36)
    add_check(
        "候选身份",
        "R01-R04共24个论文公式候选身份齐全",
        actual_formula_ids == expected_formula_ids,
        len(actual_formula_ids),
        len(expected_formula_ids),
    )
    add_check(
        "候选身份",
        "R05/R06共12个历史诊断包全部BLOCKED且未计入论文候选",
        actual_diagnostic_ids == expected_diagnostic_ids
        and all(
            row["formula_or_diagnostic_code_pass"]
            for row in bundle_rows
            if row["candidate_id"] in DIAGNOSTIC_CANDIDATES
        ),
        len(actual_diagnostic_ids),
        len(expected_diagnostic_ids),
    )
    add_check(
        "跨语言",
        "36包基础M/C/K与MATLAB六链相应标准或历史诊断矩阵一致",
        max(float(row["matlab_python_base_max_relative_error"]) for row in bundle_rows) <= TOL,
        f"{max(float(row['matlab_python_base_max_relative_error']) for row in bundle_rows):.17g}",
        "<=1e-12",
    )
    add_check(
        "逐路线积分",
        "36包matrix_al均由各自M/C/K重算且恒等式闭合",
        max(
            max(float(row["matrix_al_direct_relative_error"]), float(row["matrix_al_identity_relative_error"]))
            for row in bundle_rows
        )
        <= TOL,
        f"{max(max(float(row['matrix_al_direct_relative_error']), float(row['matrix_al_identity_relative_error'])) for row in bundle_rows):.17g}",
        "<=1e-12",
    )
    add_check(
        "控制器",
        "24个CARE候选均满足连续ARE、增益语义和闭环左半平面",
        all(row["overall_pass"] for row in bundle_rows if row["candidate_id"] in FORMULA_CANDIDATES),
        f"max_real={max(float(row['care_closed_loop_max_real']) for row in bundle_rows if row['candidate_id'] in FORMULA_CANDIDATES):.17g}; "
        f"max_res={max(float(row['care_residual']) for row in bundle_rows if row['candidate_id'] in FORMULA_CANDIDATES):.17g}",
        "max_real<0且ARE残差<=1e-8",
    )
    add_check(
        "零时滞",
        "36包Laurent项按z^0与z^-1同幂次聚合后闭合",
        max(float(row["full_laurent_same_power_relative_error"]) for row in bundle_rows) <= TOL,
        f"{max(float(row['full_laurent_same_power_relative_error']) for row in bundle_rows):.17g}",
        "<=1e-12",
    )
    probe_configuration_pass = (
        len(DELAY_PROBE_POINTS) == 6
        and len(COMPLEX_Z_PROBES) >= 3
        and all(abs(value) > 0.0 and abs(value.imag) > 0.0 for value in COMPLEX_Z_PROBES)
        and all(0.9 <= abs(value) <= 1.1 for value in COMPLEX_Z_PROBES)
    )
    complex_probe_max = max(
        float(row["complex_laurent_probe_max_relative_error"]) for row in bundle_rows
    )
    add_check(
        "完整Laurent复数探针",
        "36包在六组l/j与三个非零近单位圆复数z处直接式和逐幂次和一致",
        probe_configuration_pass and complex_probe_max <= COMPLEX_PROBE_TOL,
        f"points={len(DELAY_PROBE_POINTS)}; z={len(COMPLEX_Z_PROBES)}; max_rel={complex_probe_max:.17g}",
        "6组时延点、至少3个非零复数z且max_rel<=1e-11",
    )

    dense_checks: list[bool] = []
    dense_notes: list[str] = []
    expected_div2_guyan_psi6 = np.array(
        [
            0.719397421364447,
            0.4550298059053014,
            -0.05486876460548015,
            0.0009471928735798241,
            0.05045152183090985,
        ]
    )
    for method in ("Guyan", "Craig_Bampton"):
        bundle = loaded_bundles[(2, method, "R01")]
        psi6 = np.asarray(bundle["S"], dtype=np.float64)[1, :]
        nonzero = int(np.count_nonzero(np.abs(psi6) > 1.0e-12))
        passed = nonzero == psi6.size
        if method == "Guyan":
            passed = passed and rel_error(psi6, expected_div2_guyan_psi6) <= TOL
        dense_checks.append(passed)
        dense_notes.append(f"{method}:{nonzero}/{psi6.size}")
    add_check(
        "图4-5坐标恢复",
        "Guyan与Craig-Bampton的psi6均为稠密恢复行而非单个缩聚坐标",
        all(dense_checks),
        "; ".join(dense_notes),
        "Guyan=5/5且CB=8/8非零",
    )

    candidate_contract_rows = read_csv(CANDIDATE_CONTRACT)
    candidate_contract_by_id = {
        row["candidate_id"].split("_", 1)[0]: row for row in candidate_contract_rows
    }
    petrov_errors: list[float] = []
    petrov_separation: list[float] = []
    div2_petrov_separation: list[float] = []
    petrov_passes: list[bool] = []
    for division in (1, 2):
        full = {
            symbol: np.asarray(contract[f"div{division}_Original_source_full15_{symbol}"], dtype=np.float64)
            for symbol in ("M", "C", "K")
        }
        for candidate in DIAGNOSTIC_CANDIDATES:
            payload = loaded_bundles[(division, "Guyan", candidate)]
            recovery = np.asarray(payload["R"], dtype=np.float64)
            test_basis = np.asarray(payload["W"], dtype=np.float64)
            embedding = np.asarray(payload["E"], dtype=np.float64)
            selection = np.asarray(payload["J"], dtype=np.float64)
            s_left = np.asarray(payload["S_L"], dtype=np.float64)
            s_right = np.asarray(payload["S_R"], dtype=np.float64)
            expected_w = np.eye(15)[:, GUYAN_MASTER[division]]
            base_error = max(
                rel_error(payload[symbol], expected_w.T @ full[symbol] @ recovery)
                for symbol in ("M", "C", "K")
            )
            sl_error = rel_error(s_left, selection @ embedding.T @ expected_w)
            sr_error = rel_error(s_right, selection @ embedding.T @ recovery)
            active_error = max(
                rel_error(payload["delay_C_left_factor"], s_right.T),
                rel_error(payload["delay_C_right_factor"], payload["W_C"]),
                rel_error(payload["delay_K_left_factor"], s_right.T),
                rel_error(payload["delay_K_right_factor"], payload["W_K"]),
                rel_error(payload["C2_zero_delay"], s_right.T @ payload["W_C"]),
                rel_error(payload["K2_zero_delay"], s_right.T @ payload["W_K"]),
                rel_error(payload["feedback_C"], s_right.T @ payload["DeltaC"] @ s_right),
                rel_error(payload["feedback_K"], s_right.T @ payload["DeltaK"] @ s_right),
            )
            petrov_audit_error = max(
                rel_error(
                    payload["petrov_audit_C_left_factor"],
                    expected_w.T @ embedding @ payload["C_local_full"] @ selection.T,
                ),
                rel_error(payload["petrov_audit_C_right_factor"], s_right),
                rel_error(
                    payload["petrov_audit_K_left_factor"],
                    expected_w.T @ embedding @ payload["K_local_full"] @ selection.T,
                ),
                rel_error(payload["petrov_audit_K_right_factor"], s_right),
                rel_error(
                    payload["C2_petrov_right_audit"],
                    payload["petrov_audit_C_left_factor"] @ s_right,
                ),
                rel_error(
                    payload["K2_petrov_right_audit"],
                    payload["petrov_audit_K_left_factor"] @ s_right,
                ),
            )
            separation = float(np.linalg.norm(s_left - s_right))
            basis_separation_pass = float(np.linalg.norm(test_basis - recovery)) > 1.0e-6
            selector_separation_pass = True
            second_channel_pass = True
            if division == 2:
                selector_separation_pass = separation > 1.0e-6
                second_channel_pass = (
                    float(np.linalg.norm(s_left[1, :])) <= 1.0e-14
                    and np.count_nonzero(np.abs(s_right[1, :]) > 1.0e-12) == s_right.shape[1]
                )
            passed = all(
                (
                    rel_error(test_basis, expected_w) <= TOL,
                    base_error <= TOL,
                    sl_error <= TOL,
                    sr_error <= TOL,
                    active_error <= TOL,
                    petrov_audit_error <= TOL,
                    basis_separation_pass,
                    selector_separation_pass,
                    second_channel_pass,
                    integer(payload["petrov_historical_guyan_code"]) == 1,
                    integer(payload["delay_orientation_code"]) == 1,
                    integer(payload["petrov_right_audit_only_code"]) == 1,
                    integer(payload["formula_valid_code"]) == 0,
                    integer(payload["paper_grid_eligible_code"]) == 0,
                )
            )
            metadata = metadata_by_id[f"D{division}_Guyan_{candidate}"]
            passed = passed and all(
                (
                    metadata["delay_orientation"] == "H_LEFT",
                    "FROZEN_STEP8B_H_LEFT" in metadata["active_formula_contract"],
                    "AUDIT_ONLY" in metadata["petrov_contract"],
                    "AUDIT_ONLY" in metadata["petrov_audit_formula"],
                )
            )
            petrov_errors.append(
                max(base_error, sl_error, sr_error, active_error, petrov_audit_error)
            )
            petrov_separation.append(separation)
            if division == 2:
                div2_petrov_separation.append(separation)
            petrov_passes.append(passed)

    r05_reason = candidate_contract_by_id["R05"]["limitation"]
    r06_reason = candidate_contract_by_id["R06"]["limitation"]
    exclusion_reason_pass = "输入单位重复" in r05_reason and "LQR要求冲突" in r06_reason
    r06_open_loop_max_real_values: list[float] = []
    for division, method in EXPECTED_DIMS:
        r05 = loaded_bundles[(division, method, "R05")]
        local_mass = np.asarray(r05["M_controller_local"], dtype=np.float64)
        gain = np.asarray(r05["controller_gain"], dtype=np.float64)
        exclusion_reason_pass = exclusion_reason_pass and all(
            (
                integer(r05["controller_type_code"]) == 2,
                integer(r05["control_input_semantics_code"]) == 1,
                rel_error(r05["B_continuous"][2:, :], np.linalg.solve(local_mass, np.eye(2))) <= TOL,
                rel_error(r05["DeltaK"], local_mass @ gain[:, :2]) <= TOL,
                rel_error(r05["DeltaC"], local_mass @ gain[:, 2:]) <= TOL,
            )
        )
        r06 = loaded_bundles[(division, method, "R06")]
        r06_open_loop_max_real = float(
            np.max(np.real(np.linalg.eigvals(np.asarray(r06["A_continuous"], dtype=np.float64))))
        )
        r06_open_loop_max_real_values.append(r06_open_loop_max_real)
        exclusion_reason_pass = exclusion_reason_pass and all(
            (
                integer(r06["controller_type_code"]) == 0,
                np.count_nonzero(r06["controller_gain"]) == 0,
                np.count_nonzero(r06["DeltaK"]) == 0,
                np.count_nonzero(r06["DeltaC"]) == 0,
            )
        )
    add_check(
        "历史诊断排除",
        "R05广义力输入后重复乘M、R06无LQR的排除原因均由数值字段闭合",
        exclusion_reason_pass,
        f"R05:{r05_reason}; R06:{r06_reason}",
        "R05输入单位重复；R06与论文LQR要求冲突",
    )
    add_check(
        "R06开环诊断",
        "六条R06无LQR路线的连续开环状态矩阵均渐近稳定",
        max(r06_open_loop_max_real_values) < 0.0,
        f"max_real={max(r06_open_loop_max_real_values):.17g}",
        "max_real<0",
    )
    add_check(
        "Petrov双基",
        "历史Guyan活动诊断为S_R左乘与S_R双侧反馈，Petrov右乘仅作AUDIT_ONLY",
        all(petrov_passes),
        f"max_error={max(petrov_errors):.17g}; 图4-5 min_norm(S_L-S_R)={min(div2_petrov_separation):.17g}",
        "活动式H_LEFT且max_error<=1e-12；Petrov右乘只审计；图4-5 S_L[2,:]=0",
    )

    matlab_petrov_passes: list[bool] = []
    for division in (1, 2):
        route = matlab_route_map[(division, "Guyan")]
        audit = route["guyan_historical_petrov_audit"]
        matlab_petrov_passes.append(
            str(audit["status"]) == "PASS"
            and not bool(integer(audit["executable_control_candidate_generated"]))
            and bool(integer(audit["primary_R01_R04_numerics_unchanged"]))
            and scalar(audit["historical_matrix_max_relative_difference"]) <= TOL
            and (division != 2 or scalar(audit["S_L_second_channel_norm"]) <= 1.0e-14)
        )
    add_check(
        "MATLAB排除证据",
        "MATLAB两类历史Guyan均保存Petrov审计且R05/R06未生成为可执行控制候选",
        all(matlab_petrov_passes),
        f"{sum(matlab_petrov_passes)}/{len(matlab_petrov_passes)}",
        "2/2",
    )

    all_bundle_pass = all(row["overall_pass"] for row in bundle_rows)
    add_check(
        "逐包总门禁",
        "36个包全部通过独立维数、跨语言、al、Laurent及身份检查",
        all_bundle_pass,
        f"{sum(row['overall_pass'] for row in bundle_rows)}/{len(bundle_rows)}",
        "36/36",
    )

    all_checks_pass = all(row["status"] == "PASS" for row in checks)
    write_csv(
        VALIDATION_DIR / "步骤8C_Python确定性逐文件对比.csv",
        determinism_rows,
        [
            "relative_path",
            "run1_bytes",
            "run1_sha256",
            "run2_bytes",
            "run2_sha256",
            "byte_identical",
        ],
    )
    write_csv(
        VALIDATION_DIR / "步骤8C_逐包独立数值审计.csv",
        bundle_rows,
        list(bundle_rows[0].keys()),
    )
    write_csv(
        VALIDATION_DIR / "步骤8C_独立验收检查.csv",
        checks,
        ["category", "check", "status", "actual", "expected", "note"],
    )

    summary = {
        "schema": "board20-step8c-independent-validation-v1",
        "status": "PASS" if all_checks_pass else "FAIL",
        "independence": "不导入任何生成器；子进程复跑后从磁盘独立重算",
        "gate_count": len(checks),
        "gate_pass_count": sum(row["status"] == "PASS" for row in checks),
        "bundle_count": len(bundle_rows),
        "formula_candidate_count": len(actual_formula_ids),
        "blocked_diagnostic_count": len(actual_diagnostic_ids),
        "deterministic_file_count": len(determinism_rows),
        "source_hashes": source_hash_rows,
        "generator_hashes": {
            "python_before": generator_hash_before,
            "python_after": generator_hash_after,
            "matlab": sha256_file(MATLAB_GENERATOR),
            "validator": sha256_file(Path(__file__)),
        },
        "maximum_errors": {
            "matlab_python_base_relative_error": max(
                float(row["matlab_python_base_max_relative_error"]) for row in bundle_rows
            ),
            "matrix_al_relative_error": max(
                max(float(row["matrix_al_direct_relative_error"]), float(row["matrix_al_identity_relative_error"]))
                for row in bundle_rows
            ),
            "zero_delay_factor_relative_error": max(
                float(row["zero_delay_factor_max_relative_error"]) for row in bundle_rows
            ),
            "laurent_same_power_relative_error": max(
                float(row["full_laurent_same_power_relative_error"]) for row in bundle_rows
            ),
            "complex_laurent_probe_relative_error": complex_probe_max,
            "CARE_residual": max(
                float(row["care_residual"])
                for row in bundle_rows
                if row["candidate_id"] in FORMULA_CANDIDATES
            ),
            "CARE_closed_loop_max_real": max(
                float(row["care_closed_loop_max_real"])
                for row in bundle_rows
                if row["candidate_id"] in FORMULA_CANDIDATES
            ),
            "R06_open_loop_max_real": max(r06_open_loop_max_real_values),
            "Petrov_relative_error": max(petrov_errors),
        },
        "input_audit": input_audit,
        "conclusion": (
            "六条源干净模型链和24个公式候选可进入步骤8D；"
            "R05/R06共12包仅保留为BLOCKED历史诊断，禁止进入论文稳定域网格。"
        ),
    }
    write_json(VALIDATION_DIR / "步骤8C_独立验收摘要.json", summary)

    report_lines = [
        "# 板块20最小步骤8C独立验收报告",
        "",
        f"验收状态：**{summary['status']}**。本验证器没有导入MATLAB或Python生成器；Python生成器以子进程连续运行两次，随后全部数值从磁盘独立重算。",
        "",
        "## 核心结果",
        "",
        f"- 六路线维数：15/6/9/15/5/8；候选包：36，其中R01-R04公式候选24，R05/R06阻断诊断12。",
        f"- Python两轮确定性：{sum(row['byte_identical'] for row in determinism_rows)}/{len(determinism_rows)}个文件字节一致。",
        f"- 当前Python生成器SHA-256：`{summary['generator_hashes']['python_after'].upper()}`。",
        f"- 当前MATLAB生成器SHA-256：`{summary['generator_hashes']['matlab'].upper()}`。",
        f"- MATLAB/Python基础矩阵最大相对误差：{summary['maximum_errors']['matlab_python_base_relative_error']:.3e}。",
        f"- 逐路线matrix_al最大误差：{summary['maximum_errors']['matrix_al_relative_error']:.3e}。",
        f"- 零时滞Laurent同幂次聚合最大相对误差：{summary['maximum_errors']['laurent_same_power_relative_error']:.3e}。",
        f"- 六组时延点、三个复数z的完整Laurent直接探针最大相对误差：{summary['maximum_errors']['complex_laurent_probe_relative_error']:.3e}。",
        f"- 24个CARE候选最差连续闭环实部：{summary['maximum_errors']['CARE_closed_loop_max_real']:.9g}；最大ARE相对残差：{summary['maximum_errors']['CARE_residual']:.3e}。",
        f"- R06六条开环路线最差连续特征值实部：{summary['maximum_errors']['R06_open_loop_max_real']:.9g}。",
        f"- 历史Guyan活动H左乘与Petrov审计关系最大相对误差：{summary['maximum_errors']['Petrov_relative_error']:.3e}。活动诊断使用S_R左乘和S_R双侧反馈；Petrov右乘仅为AUDIT_ONLY。",
        "",
        "## 身份边界",
        "",
        "R01-R04的精确身份标签为FORMULA_COHERENT_SOURCE_COMPLETION，可进入下一步试点求解。R05在B=[0;M^-1]后再次乘局部M，形成输入单位重复；R06没有LQR但开环稳定。二者均为BLOCKED_DIAGNOSTIC_ONLY，不能进入论文稳定域网格。历史Guyan活动式冻结为H左乘，Petrov右乘只保留审计证据。",
        "",
        "## 门禁明细",
        "",
    ]
    for row in checks:
        report_lines.append(f"- [{row['status']}] {row['category']}：{row['check']}（实际：{row['actual']}；要求：{row['expected']}）。")
    (VALIDATION_DIR / "步骤8C_独立验收报告.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )

    manifest_path = VALIDATION_DIR / "步骤8C_独立验收工件清单.csv"
    manifest_artifacts = [
        path
        for path in sorted(VALIDATION_DIR.iterdir(), key=lambda item: item.name)
        if path.is_file() and path != manifest_path
    ]
    validation_manifest_rows = [
        {"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in manifest_artifacts
    ]
    write_csv(manifest_path, validation_manifest_rows, ["filename", "bytes", "sha256"])

    print(f"STEP8C_INDEPENDENT_STATUS={summary['status']}")
    print(f"GATES={summary['gate_pass_count']}/{summary['gate_count']}")
    print(f"BUNDLES={sum(row['overall_pass'] for row in bundle_rows)}/{len(bundle_rows)}")
    print(f"DETERMINISTIC_FILES={sum(row['byte_identical'] for row in determinism_rows)}/{len(determinism_rows)}")
    print(f"MAX_MATLAB_PYTHON_REL={summary['maximum_errors']['matlab_python_base_relative_error']:.17g}")
    print(f"MAX_AL_REL={summary['maximum_errors']['matrix_al_relative_error']:.17g}")
    print(f"MAX_LAURENT_REL={summary['maximum_errors']['laurent_same_power_relative_error']:.17g}")
    print(f"MAX_COMPLEX_PROBE_REL={summary['maximum_errors']['complex_laurent_probe_relative_error']:.17g}")
    print(f"CARE_MAX_REAL={summary['maximum_errors']['CARE_closed_loop_max_real']:.17g}")
    print(f"R06_OPEN_LOOP_MAX_REAL={summary['maximum_errors']['R06_open_loop_max_real']:.17g}")
    print(f"PETROV_MAX_REL={summary['maximum_errors']['Petrov_relative_error']:.17g}")
    if not all_checks_pass:
        failed = [row["check"] for row in checks if row["status"] != "PASS"]
        raise RuntimeError(f"步骤8C独立验收失败：{failed}")


if __name__ == "__main__":
    main()
