#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把板块20 R05/R06历史诊断包转换为图10盲算侧原生算子包。

本程序只读取板块20步骤8C的索引、摘要、自检表和R05/R06数值MAT。
它不导入求根器，不创建结果网格，也不读取任何绘图或校准目标资产。

H05/H06只是历史诊断身份：源包的 ``formula_valid_code`` 与
``paper_grid_eligible_code`` 必须同时为0，输出元数据固定标记为
``HISTORICAL_DIAGNOSTIC_NOT_PAPER_FORMULA_VALID``。这条桥不会改变
``fig10_blind_core.py`` 对旧布局包的公式有效门。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.io import loadmat, savemat


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT_DIR = CASE_DIR / "data" / "historical_diagnostic_blind_bridge"

SOURCE_BOARD_RELATIVE = Path(
    "test/00_失败尝试与候选路线/"
    "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现/"
    "outputs/step8c_六链模型生成/python"
)
SOURCE_INDEX_NAME = "六路线六候选索引.csv"
SOURCE_CHECK_NAME = "步骤8C_Python自检.csv"
SOURCE_SUMMARY_NAME = "步骤8C_Python摘要.json"
SOURCE_INDEX_SHA256 = "E78F3AAE56CCEF63B222BC5BF2CF648AC6305C78E40D86B8A48B047C5EA3ADDA"
SOURCE_CHECK_SHA256 = "230BD728F753DA97B39EE9448B2726FDCB3EB8CEA767040A16B50C02C785A591"
SOURCE_SUMMARY_SHA256 = "3D519F413CEE339DAD63142AFE208ABAC97154ECA57FFDAE5098C69FE789669E"

BRIDGE_SCHEMA = "FIG10_HISTORICAL_DIAGNOSTIC_BRIDGE_V1"
BLIND_MANIFEST_SCHEMA = "FIG10_BLIND_SEARCH_MANIFEST_V1"
BLIND_CORE_SCHEMA = "FIG10_BLIND_CORE_V1"
NATIVE_LAYOUT = "MINIMAL_AUGMENTED_CORE_V1"
DIAGNOSTIC_STATUS = "HISTORICAL_DIAGNOSTIC_NOT_PAPER_FORMULA_VALID"
SOURCE_FORMULA_STATUS = "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID"
METHOD_ORDER = {"Original": 0, "Guyan": 1, "Craig_Bampton": 2}
METHOD_CODE = {"Original": 1, "Guyan": 2, "Craig_Bampton": 3}
EXPECTED_DIMS = {
    (1, "Original"): 15,
    (1, "Guyan"): 6,
    (1, "Craig_Bampton"): 9,
    (2, "Original"): 15,
    (2, "Guyan"): 5,
    (2, "Craig_Bampton"): 8,
}
CONTRACT_MAP = {"R05": "H05", "R06": "H06"}
EXPECTED_CONTROLLER_CODE = {"R05": 2, "R06": 0}
OPERATOR_FIELDS = (
    "mass_term",
    "base_zero",
    "base_minus_one",
    "delay_left",
    "delay_v_zero",
    "delay_v_minus_one",
    "register_scales",
)
FACTOR_LIMIT = 1.0e-12
SENTINELS = (
    (0, 0),
    (1, 0),
    (0, 1),
    (3, 7),
    (10, 20),
    (15, 33),
    (30, 66),
    (1, 48),
    (1, 57),
    (1, 64),
)
SPARSE_COLUMNS = (0, 1, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64, 66)


class BridgeError(RuntimeError):
    """历史诊断桥输入或Stage0门失败。"""


@dataclass(frozen=True)
class ConvertedRoute:
    source_contract_id: str
    diagnostic_contract_id: str
    division: int
    method: str
    dimension: int
    source_route_id: str
    route_id: str
    source_relative_path: str
    source_sha256: str
    payload: dict[str, np.ndarray]
    operator: dict[str, np.ndarray]
    stage0: dict[str, Any]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BridgeError(message)


def repo_root_from_script() -> Path:
    root = SCRIPT_DIR.parents[4]
    require((root / "WORKFLOW.md").is_file(), f"无法定位仓库根目录：{root}")
    return root


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def csv_bytes(rows: Iterable[Mapping[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def semantic_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    descriptor = json.dumps(
        {"dtype": array.dtype.str, "shape": list(array.shape), "order": "C"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(descriptor)
    digest.update(b"\0")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)


def numeric(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).copy()


def scalar(value: Any, name: str) -> float:
    array = np.asarray(value, dtype=np.float64)
    require(array.size == 1, f"{name}必须是标量，实际shape={array.shape}")
    result = float(array.reshape(-1)[0])
    require(np.isfinite(result), f"{name}必须是有限数")
    return result


def scalar_int(value: Any, name: str) -> int:
    number = scalar(value, name)
    rounded = int(round(number))
    require(number == rounded, f"{name}={number}不是整数")
    return rounded


def mat_scalar(value: float | int | bool) -> np.ndarray:
    return np.asarray([[value]], dtype=np.float64)


def utf8_uint8(value: str) -> np.ndarray:
    return np.frombuffer(value.encode("utf-8"), dtype=np.uint8).reshape(-1, 1)


def deterministic_mat_bytes(payload: Mapping[str, np.ndarray]) -> bytes:
    buffer = io.BytesIO()
    savemat(buffer, dict(payload), do_compression=True, oned_as="column")
    output = bytearray(buffer.getvalue())
    header = b"MATLAB 5.0 MAT-file, Fig10 historical diagnostic bridge deterministic"
    output[:116] = header.ljust(116, b" ")[:116]
    return bytes(output)


def load_source_registry(repo_root: Path) -> tuple[Path, list[dict[str, str]], dict[str, str]]:
    source_root = (repo_root / SOURCE_BOARD_RELATIVE).resolve()
    index_path = source_root / SOURCE_INDEX_NAME
    check_path = source_root / SOURCE_CHECK_NAME
    summary_path = source_root / SOURCE_SUMMARY_NAME
    required = {
        SOURCE_INDEX_NAME: (index_path, SOURCE_INDEX_SHA256),
        SOURCE_CHECK_NAME: (check_path, SOURCE_CHECK_SHA256),
        SOURCE_SUMMARY_NAME: (summary_path, SOURCE_SUMMARY_SHA256),
    }
    evidence_hashes: dict[str, str] = {}
    for name, (path, expected) in required.items():
        require(path.is_file(), f"缺少板块20冻结证据：{path}")
        actual = sha256_file(path)
        require(actual == expected, f"板块20冻结证据哈希漂移：{name}")
        evidence_hashes[name] = actual
    with index_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    selected = [row for row in rows if row.get("candidate_id") in CONTRACT_MAP]
    require(len(selected) == 12, f"R05/R06源路线应为12条，实际{len(selected)}条")
    selected.sort(
        key=lambda row: (
            0 if row["candidate_id"] == "R05" else 1,
            int(row["division"]),
            METHOD_ORDER[row["method"]],
        )
    )
    return source_root, selected, evidence_hashes


def convert_legacy_arrays(
    data: Mapping[str, Any], dimension: int
) -> tuple[dict[str, np.ndarray], dict[str, float], bool]:
    dt = scalar(data["dt"], "dt")
    require(dt > 0.0, "dt必须大于0")
    shape = (dimension, dimension)
    integration_mass_operator = numeric(data["integration_mass_operator"])
    c1 = numeric(data["C1"])
    k1 = numeric(data["K1"])
    feedback_c = numeric(data["feedback_C"])
    feedback_k = numeric(data["feedback_K"])
    delay_c_left = numeric(data["delay_C_left_factor"])
    delay_k_left = numeric(data["delay_K_left_factor"])
    delay_c_right = numeric(data["delay_C_right_factor"])
    delay_k_right = numeric(data["delay_K_right_factor"])
    for name, value in (
        ("integration_mass_operator", integration_mass_operator),
        ("C1", c1),
        ("K1", k1),
        ("feedback_C", feedback_c),
        ("feedback_K", feedback_k),
    ):
        require(value.shape == shape, f"{name} shape={value.shape}，预期{shape}")
    require(delay_c_left.shape == (dimension, 2), "delay_C_left_factor形状错误")
    require(delay_k_left.shape == (dimension, 2), "delay_K_left_factor形状错误")
    require(delay_c_right.shape == (2, dimension), "delay_C_right_factor形状错误")
    require(delay_k_right.shape == (2, dimension), "delay_K_right_factor形状错误")
    require(
        all(
            np.all(np.isfinite(value))
            for value in (
                integration_mass_operator,
                c1,
                k1,
                feedback_c,
                feedback_k,
                delay_c_left,
                delay_k_left,
                delay_c_right,
                delay_k_right,
            )
        ),
        "旧布局字段含非有限值",
    )
    shared_left_error = relative_error(delay_c_left, delay_k_left)
    shared_right_error = relative_error(delay_c_right, delay_k_right)
    direct_shared_left = shared_left_error <= FACTOR_LIMIT
    transpose_for_shared_left = (not direct_shared_left) and shared_right_error <= FACTOR_LIMIT
    require(
        direct_shared_left or transpose_for_shared_left,
        "旧布局C/K时滞因子既不共享左因子也不共享右因子",
    )

    mass_term = integration_mass_operator / (dt * dt)
    base_zero = (
        -2.0 * mass_term
        + c1 / dt
        + k1
        + feedback_c / dt
        + feedback_k
    )
    base_minus_one = mass_term - c1 / dt - feedback_c / dt
    if direct_shared_left:
        delay_left = delay_c_left.copy()
        delay_v_zero = delay_c_right / dt + delay_k_right
        delay_v_minus_one = -delay_c_right / dt
    else:
        # 历史Original为(v L_C+L_K) H S_R。对完整多项式算子取转置后，
        # S_R'成为共享左因子；det(P(z))=det(P(z)').因此特征根不变。
        mass_term = mass_term.T.copy()
        base_zero = base_zero.T.copy()
        base_minus_one = base_minus_one.T.copy()
        delay_left = delay_c_right.T.copy()
        delay_v_zero = delay_c_left.T / dt + delay_k_left.T
        delay_v_minus_one = -delay_c_left.T / dt
    register_scales = np.maximum.reduce(
        (
            np.linalg.norm(delay_v_zero, axis=1),
            np.linalg.norm(delay_v_minus_one, axis=1),
            np.full(2, np.finfo(float).eps),
        )
    )
    operator = {
        "mass_term": np.ascontiguousarray(mass_term),
        "base_zero": np.ascontiguousarray(base_zero),
        "base_minus_one": np.ascontiguousarray(base_minus_one),
        "delay_left": np.ascontiguousarray(delay_left),
        "delay_v_zero": np.ascontiguousarray(delay_v_zero),
        "delay_v_minus_one": np.ascontiguousarray(delay_v_minus_one),
        "register_scales": np.ascontiguousarray(register_scales),
    }

    c2 = delay_c_left @ delay_c_right
    k2 = delay_k_left @ delay_k_right
    c2_source = numeric(data["C2_zero_delay"])
    k2_source = numeric(data["K2_zero_delay"])
    damping = numeric(data["C"])
    stiffness = numeric(data["K"])
    integration_rebuilt = np.linalg.solve(numeric(data["matrix_al"]).T, numeric(data["M"]).T).T
    expected_zero_physical = (
        -2.0 * mass_term
        + (c1 + c2 + feedback_c) / dt
        + k1
        + k2
        + feedback_k
    )
    expected_minus_one_physical = mass_term - (c1 + c2 + feedback_c) / dt
    if transpose_for_shared_left:
        # mass_term已在上方转置，物理闭合式需由未转置源字段独立重建后再转置。
        source_mass_term = integration_mass_operator / (dt * dt)
        expected_zero = (
            -2.0 * source_mass_term
            + (c1 + c2 + feedback_c) / dt
            + k1
            + k2
            + feedback_k
        ).T
        expected_minus_one = (
            source_mass_term - (c1 + c2 + feedback_c) / dt
        ).T
    else:
        expected_zero = expected_zero_physical
        expected_minus_one = expected_minus_one_physical
    actual_zero = base_zero + delay_left @ delay_v_zero
    actual_minus_one = base_minus_one + delay_left @ delay_v_minus_one
    checks = {
        "shared_factor_relative_error": (
            shared_right_error if transpose_for_shared_left else shared_left_error
        ),
        "source_shared_left_relative_error": shared_left_error,
        "source_shared_right_relative_error": shared_right_error,
        "delay_C_factor_relative_error": relative_error(c2, c2_source),
        "delay_K_factor_relative_error": relative_error(k2, k2_source),
        "C_physical_closure_relative_error": relative_error(c1 + c2, damping),
        "K_physical_closure_relative_error": relative_error(k1 + k2, stiffness),
        "matrix_al_identity_relative_error": relative_error(
            integration_mass_operator, integration_rebuilt
        ),
        "zero_delay_operator_relative_error": relative_error(actual_zero, expected_zero),
        "minus_one_operator_relative_error": relative_error(actual_minus_one, expected_minus_one),
        "register_scale_relative_error": relative_error(
            register_scales,
            np.maximum.reduce(
                (
                    np.linalg.norm(delay_v_zero, axis=1),
                    np.linalg.norm(delay_v_minus_one, axis=1),
                    np.full(2, np.finfo(float).eps),
                )
            ),
        ),
    }
    require(np.linalg.matrix_rank(mass_term) == dimension, "mass_term不满秩")
    require(np.all(register_scales > 0.0), "register_scales必须严格为正")
    gated_names = (
        "shared_factor_relative_error",
        "delay_C_factor_relative_error",
        "delay_K_factor_relative_error",
        "C_physical_closure_relative_error",
        "K_physical_closure_relative_error",
        "matrix_al_identity_relative_error",
        "zero_delay_operator_relative_error",
        "minus_one_operator_relative_error",
        "register_scale_relative_error",
    )
    require(
        max(checks[name] for name in gated_names) <= FACTOR_LIMIT,
        f"legacy->native Stage0闭合失败：{checks}",
    )
    return operator, checks, transpose_for_shared_left


def route_operator_sha256(dimension: int, dt: float, operator: Mapping[str, np.ndarray]) -> str:
    record = {
        "route_dimension": dimension,
        "dt_seconds": format(dt, ".17g"),
        "channel_to_delay_exponent": {"channel_1": "l", "channel_2": "j"},
        "operator_arrays": {
            field: {
                "semantic_array_sha256": semantic_array_sha256(operator[field]),
                "dtype": np.ascontiguousarray(operator[field]).dtype.str,
                "shape": list(np.ascontiguousarray(operator[field]).shape),
            }
            for field in OPERATOR_FIELDS[:-1]
        },
        "register_scales": {
            "semantic_array_sha256": semantic_array_sha256(operator["register_scales"]),
            "dtype": np.ascontiguousarray(operator["register_scales"]).dtype.str,
            "shape": list(np.ascontiguousarray(operator["register_scales"]).shape),
        },
    }
    return sha256_bytes(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def build_route(repo_root: Path, source_root: Path, row: Mapping[str, str]) -> ConvertedRoute:
    source_contract = str(row["candidate_id"])
    diagnostic_contract = CONTRACT_MAP[source_contract]
    division = int(row["division"])
    method = str(row["method"])
    dimension = int(row["dimension"])
    require(dimension == EXPECTED_DIMS[(division, method)], "源路线维数与冻结合同不符")
    require(row["formula_status"] == SOURCE_FORMULA_STATUS, "源索引公式身份不符")
    require(row["paper_grid_eligible"] == "BLOCKED_DIAGNOSTIC_ONLY", "源索引论文网格门未阻断")
    require(str(row["overall_pass"]).lower() == "true", "源步骤8C Stage0未通过")
    source_path = (source_root / row["relative_path"]).resolve()
    require(source_path.is_file(), f"源MAT不存在：{source_path}")
    source_hash = sha256_file(source_path)
    require(source_hash == str(row["mat_sha256"]).upper(), f"源MAT哈希漂移：{row['bundle_id']}")
    source_relative_path = source_path.relative_to(repo_root).as_posix()
    data = {
        key: value
        for key, value in loadmat(source_path, squeeze_me=True, struct_as_record=False).items()
        if not key.startswith("__")
    }
    require(scalar_int(data["route_dimension"], "route_dimension") == dimension, "源MAT维数不符")
    require(scalar_int(data["division"], "division") == division, "源MAT划分号不符")
    require(scalar_int(data["method_index"], "method_index") == METHOD_CODE[method], "源MAT方法号不符")
    require(scalar_int(data["candidate_index"], "candidate_index") == int(source_contract[-2:]), "源MAT候选号不符")
    formula_gate = scalar_int(data["formula_valid_code"], "formula_valid_code")
    paper_gate = scalar_int(data["paper_grid_eligible_code"], "paper_grid_eligible_code")
    require(formula_gate == 0, "源MAT formula_valid_code必须保持0")
    require(paper_gate == 0, "源MAT paper_grid_eligible_code必须保持0")
    require(scalar_int(data["feedback_placement_code"], "feedback_placement_code") == 1, "仅支持冻结的H外反馈")
    require(scalar_int(data["integration_mode_code"], "integration_mode_code") == 2, "历史诊断必须使用逐路线matrix_al")
    require(
        scalar_int(data["controller_type_code"], "controller_type_code")
        == EXPECTED_CONTROLLER_CODE[source_contract],
        "源MAT控制器类型不符",
    )
    operator, checks, transpose_for_shared_left = convert_legacy_arrays(data, dimension)
    orientation_code = scalar_int(data["delay_orientation_code"], "delay_orientation_code")
    require(
        orientation_code == (2 if method == "Original" else 1),
        "源MAT延迟方向与历史冻结规则不符",
    )
    require(
        transpose_for_shared_left == (method == "Original"),
        "共享因子桥接方向与历史冻结规则不符",
    )
    dt = scalar(data["dt"], "dt")
    route_id = f"{diagnostic_contract}_D{division}_{method}"
    operator_hash = route_operator_sha256(dimension, dt, operator)
    stage0 = {
        "route_id": route_id,
        "source_route_id": str(row["bundle_id"]),
        "source_contract_id": source_contract,
        "diagnostic_contract_id": diagnostic_contract,
        "division": division,
        "method": method,
        "dimension": dimension,
        "source_mat_sha256": source_hash,
        "source_index_sha256": SOURCE_INDEX_SHA256,
        "source_formula_valid_code": formula_gate,
        "source_paper_grid_eligible_code": paper_gate,
        "formula_gate_blocked": formula_gate == 0,
        "paper_grid_gate_blocked": paper_gate == 0,
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "source_delay_orientation_code": orientation_code,
        "operator_transpose_for_shared_left": transpose_for_shared_left,
        **checks,
        "mass_term_rank": int(np.linalg.matrix_rank(operator["mass_term"])),
        "register_scales_strictly_positive": bool(np.all(operator["register_scales"] > 0.0)),
        "route_operator_sha256": operator_hash,
        "roots_computed": 0,
        "grid_points_computed": 0,
        "stage0_pass": True,
    }
    payload: dict[str, np.ndarray] = {
        "bundle_schema_version": mat_scalar(1),
        "route_dimension": mat_scalar(dimension),
        "division": mat_scalar(division),
        "method_index": mat_scalar(METHOD_CODE[method]),
        "candidate_index": mat_scalar(int(source_contract[-2:])),
        "dt": mat_scalar(dt),
        "formula_valid_code": mat_scalar(0),
        "paper_grid_eligible_code": mat_scalar(0),
        "source_formula_valid_code": mat_scalar(formula_gate),
        "source_paper_grid_eligible_code": mat_scalar(paper_gate),
        "scientific_search_executed_code": mat_scalar(0),
        "roots_computed": mat_scalar(0),
        "grid_points_computed": mat_scalar(0),
        "shared_left_factor_relative_error": mat_scalar(
            checks["shared_factor_relative_error"]
        ),
        "operator_transpose_for_shared_left_code": mat_scalar(
            int(transpose_for_shared_left)
        ),
        "stage0_overall_pass_code": mat_scalar(1),
        "diagnostic_status_utf8": utf8_uint8(DIAGNOSTIC_STATUS),
        "blind_core_schema_version_utf8": utf8_uint8(BLIND_CORE_SCHEMA),
        "operator_layout_utf8": utf8_uint8(NATIVE_LAYOUT),
        "source_contract_id_utf8": utf8_uint8(source_contract),
        "diagnostic_contract_id_utf8": utf8_uint8(diagnostic_contract),
        "source_route_id_utf8": utf8_uint8(str(row["bundle_id"])),
        "source_repo_relative_path_utf8": utf8_uint8(source_relative_path),
        "source_mat_sha256_utf8": utf8_uint8(source_hash),
        "route_operator_sha256_utf8": utf8_uint8(operator_hash),
        **{field: value for field, value in operator.items() if field != "register_scales"},
        "register_scales": operator["register_scales"].reshape(-1, 1),
    }
    return ConvertedRoute(
        source_contract_id=source_contract,
        diagnostic_contract_id=diagnostic_contract,
        division=division,
        method=method,
        dimension=dimension,
        source_route_id=str(row["bundle_id"]),
        route_id=route_id,
        source_relative_path=source_relative_path,
        source_sha256=source_hash,
        payload=payload,
        operator=operator,
        stage0=stage0,
    )


def sampling_contract() -> dict[str, Any]:
    return {
        "grid": {"l_min": 0, "l_max": 30, "j_min": 0, "j_max": 66},
        "sentinel_points": [list(point) for point in SENTINELS],
        "fixed_sparse_band_points": [
            [l_value, j_value]
            for j_value in SPARSE_COLUMNS
            for l_value in range(31)
        ],
    }


def contract_descriptor(contract_id: str, routes: list[ConvertedRoute]) -> dict[str, Any]:
    source_contract = "R05" if contract_id == "H05" else "R06"
    return {
        "diagnostic_contract_id": contract_id,
        "source_contract_id": source_contract,
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "controller": "DARE" if source_contract == "R05" else "NONE",
        "integration": "route_matrix_al",
        "guyan_projection": "historical_single_sided",
        "delay_orientation": "H_RIGHT_FOR_ORIGINAL_H_LEFT_FOR_REDUCED",
        "feedback_placement": "OUTSIDE_H",
        "conversion": {
            "mass_term": "integration_mass_operator/dt^2",
            "base_zero": "-2*mass_term+C1/dt+K1+feedback_C/dt+feedback_K",
            "base_minus_one": "mass_term-C1/dt-feedback_C/dt",
            "delay_left": "reduced: delay_C_left_factor; Original after transpose: shared delay_C_right_factor'",
            "delay_v_zero": "reduced: C_right/dt+K_right; Original after transpose: C_left'/dt+K_left'",
            "delay_v_minus_one": "reduced: -C_right/dt; Original after transpose: -C_left'/dt",
            "register_scales": "rowwise max(norm(delay_v_zero),norm(delay_v_minus_one),eps)",
        },
        "orientation_bridge": {
            "reduced_routes": "direct shared-left representation",
            "Original_routes": "transpose complete polynomial operator because historical H_RIGHT shares the right factor; determinant and roots are invariant under transpose",
        },
        "source_routes": [
            {
                "source_route_id": route.source_route_id,
                "source_mat_sha256": route.source_sha256,
                "route_operator_sha256": route.stage0["route_operator_sha256"],
            }
            for route in routes
        ],
    }


def build_artifacts(repo_root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    source_root, rows, evidence_hashes = load_source_registry(repo_root)
    routes = [build_route(repo_root, source_root, row) for row in rows]
    require(len(routes) == 12 and all(route.stage0["stage0_pass"] for route in routes), "12条历史诊断Stage0未闭合")

    artifacts: dict[str, bytes] = {}
    bundle_hashes: dict[str, str] = {}
    for route in routes:
        relative = f"numeric_bundles/{route.diagnostic_contract_id}/{route.route_id}_native.mat"
        payload = deterministic_mat_bytes(route.payload)
        artifacts[relative] = payload
        bundle_hashes[route.route_id] = sha256_bytes(payload)

    contracts: dict[str, dict[str, Any]] = {}
    for contract_id in ("H05", "H06"):
        selected = [route for route in routes if route.diagnostic_contract_id == contract_id]
        require(len(selected) == 6, f"{contract_id}应含六条路线")
        descriptor = contract_descriptor(contract_id, selected)
        contract_hash = sha256_bytes(
            json.dumps(descriptor, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        manifest_routes = []
        for route in selected:
            bundle_rel = f"../numeric_bundles/{contract_id}/{route.route_id}_native.mat"
            manifest_routes.append(
                {
                    "route_id": route.route_id,
                    "contract_id": contract_id,
                    "contract_hash": contract_hash,
                    "division": route.division,
                    "method": route.method,
                    "dimension": route.dimension,
                    "candidate_index": int(route.source_contract_id[-2:]),
                    "operator_layout": NATIVE_LAYOUT,
                    "bundle_path": bundle_rel,
                    "bundle_sha256": bundle_hashes[route.route_id],
                    "source_route_id": route.source_route_id,
                    "source_mat_sha256": route.source_sha256,
                    "formula_valid_code": 0,
                    "paper_grid_eligible_code": 0,
                    "diagnostic_status": DIAGNOSTIC_STATUS,
                    "operator_transpose_for_shared_left": route.stage0[
                        "operator_transpose_for_shared_left"
                    ],
                    "route_operator_sha256": route.stage0["route_operator_sha256"],
                    "stage0_status": "PASS_CONVERSION_ONLY_NO_ROOTS_NO_GRID",
                }
            )
        manifest = {
            "schema_version": BLIND_MANIFEST_SCHEMA,
            "blind_core_schema_version": BLIND_CORE_SCHEMA,
            "run_id": f"FIG10_{contract_id}_HISTORICAL_DIAGNOSTIC",
            "evidence_level": DIAGNOSTIC_STATUS,
            "target_dependency": "FORBIDDEN_BLIND_CALCULATION_ONLY",
            "paper_formula_eligible": False,
            "paper_grid_eligible": False,
            "execution_policy": "DIAGNOSTIC_ONLY_REQUIRES_EXPLICIT_SEPARATE_RUN",
            "scientific_search_executed": False,
            "roots_computed": 0,
            "grid_points_computed": 0,
            "allowed_bundle_roots": ["../numeric_bundles"],
            "sampling": sampling_contract(),
            "scientific_contract": descriptor,
            "routes": manifest_routes,
        }
        manifest_path = f"manifests/{contract_id}.json"
        artifacts[manifest_path] = canonical_json_bytes(manifest)
        contracts[contract_id] = {
            "contract_sha256": contract_hash,
            "manifest_path": manifest_path,
            "manifest_sha256": sha256_bytes(artifacts[manifest_path]),
            "route_count": 6,
        }

    stage0_fields = [
        "route_id",
        "source_route_id",
        "source_contract_id",
        "diagnostic_contract_id",
        "division",
        "method",
        "dimension",
        "source_mat_sha256",
        "source_index_sha256",
        "source_formula_valid_code",
        "source_paper_grid_eligible_code",
        "formula_gate_blocked",
        "paper_grid_gate_blocked",
        "diagnostic_status",
        "source_delay_orientation_code",
        "operator_transpose_for_shared_left",
        "shared_factor_relative_error",
        "source_shared_left_relative_error",
        "source_shared_right_relative_error",
        "delay_C_factor_relative_error",
        "delay_K_factor_relative_error",
        "C_physical_closure_relative_error",
        "K_physical_closure_relative_error",
        "matrix_al_identity_relative_error",
        "zero_delay_operator_relative_error",
        "minus_one_operator_relative_error",
        "register_scale_relative_error",
        "mass_term_rank",
        "register_scales_strictly_positive",
        "route_operator_sha256",
        "roots_computed",
        "grid_points_computed",
        "stage0_pass",
    ]
    artifacts["stage0_gate_results.csv"] = csv_bytes(
        [route.stage0 for route in routes], stage0_fields
    )
    source_rows = [
        {
            "source_route_id": route.source_route_id,
            "source_contract_id": route.source_contract_id,
            "source_repo_relative_path": route.source_relative_path,
            "source_mat_sha256": route.source_sha256,
            "formula_valid_code": 0,
            "paper_grid_eligible_code": 0,
            "diagnostic_status": DIAGNOSTIC_STATUS,
        }
        for route in routes
    ]
    artifacts["source_hash_inventory.csv"] = csv_bytes(
        source_rows,
        [
            "source_route_id",
            "source_contract_id",
            "source_repo_relative_path",
            "source_mat_sha256",
            "formula_valid_code",
            "paper_grid_eligible_code",
            "diagnostic_status",
        ],
    )
    array_rows = []
    for route in routes:
        for field in OPERATOR_FIELDS:
            value = route.operator[field]
            array_rows.append(
                {
                    "route_id": route.route_id,
                    "field": field,
                    "shape": "x".join(str(number) for number in value.shape),
                    "dtype": value.dtype.str,
                    "semantic_array_sha256": semantic_array_sha256(value),
                    "finite": bool(np.all(np.isfinite(value))),
                }
            )
    artifacts["array_hash_inventory.csv"] = csv_bytes(
        array_rows,
        ["route_id", "field", "shape", "dtype", "semantic_array_sha256", "finite"],
    )
    manifest_index = {
        "schema_version": "FIG10_HISTORICAL_DIAGNOSTIC_MANIFEST_INDEX_V1",
        "status": "PASS_STAGE0_ONLY",
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "contract_count": 2,
        "route_count": 12,
        "roots_computed": 0,
        "grid_points_computed": 0,
        "contracts": contracts,
    }
    artifacts["manifests/manifest_index.json"] = canonical_json_bytes(manifest_index)

    non_manifest_artifacts = [
        {
            "relative_path": name,
            "sha256": sha256_bytes(payload),
            "bytes": len(payload),
        }
        for name, payload in sorted(artifacts.items())
    ]
    bridge_manifest = {
        "schema_version": BRIDGE_SCHEMA,
        "status": "PASS_STAGE0_HISTORICAL_DIAGNOSTIC_BRIDGE",
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "source_board_relative_path": SOURCE_BOARD_RELATIVE.as_posix(),
        "source_evidence_hashes": evidence_hashes,
        "counts": {
            "source_route_mats": 12,
            "native_route_bundles": 12,
            "diagnostic_contracts": 2,
            "routes_per_contract": 6,
            "source_formula_gate_zero": 12,
            "source_paper_grid_gate_zero": 12,
            "stage0_pass": 12,
            "stage0_fail": 0,
            "roots_computed": 0,
            "grid_points_computed": 0,
        },
        "formula_gate_policy": {
            "source_formula_valid_code_required": 0,
            "source_paper_grid_eligible_code_required": 0,
            "blind_core_modified": False,
            "legacy_source_direct_load_expected": "BLOCKED_BEFORE_OPERATOR_CONVERSION",
            "native_bridge_identity": DIAGNOSTIC_STATUS,
        },
        "contracts": contracts,
        "artifacts": non_manifest_artifacts,
    }
    artifacts["bridge_manifest.json"] = canonical_json_bytes(bridge_manifest)
    summary = {
        "routes": routes,
        "bridge_manifest": bridge_manifest,
        "artifact_count": len(artifacts),
    }
    return artifacts, summary


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def verify_output(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    require(output_dir.is_dir(), f"输出目录不存在：{output_dir}")
    expected = set(artifacts)
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    require(actual == expected, f"输出文件集合不符：missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    for relative, payload in artifacts.items():
        path = output_dir / relative
        require(path.read_bytes() == payload, f"输出字节漂移：{relative}")


def write_output(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    if output_dir.exists():
        unexpected = {
            path.relative_to(output_dir).as_posix()
            for path in output_dir.rglob("*")
            if path.is_file()
        } - set(artifacts)
        require(not unexpected, f"输出目录存在非本桥文件，拒绝覆盖：{sorted(unexpected)}")
    for relative, payload in artifacts.items():
        atomic_write(output_dir / relative, payload)
    verify_output(output_dir, artifacts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_script())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    require(output_dir == DEFAULT_OUTPUT_DIR.resolve() or output_dir.is_relative_to(CASE_DIR.resolve()), "输出必须位于隔离案例内")
    artifacts_first, summary = build_artifacts(repo_root)
    artifacts_second, _ = build_artifacts(repo_root)
    require(
        {name: sha256_bytes(payload) for name, payload in artifacts_first.items()}
        == {name: sha256_bytes(payload) for name, payload in artifacts_second.items()},
        "内存双轮构建哈希不一致",
    )
    if args.verify_existing:
        verify_output(output_dir, artifacts_first)
        action = "verified"
    else:
        write_output(output_dir, artifacts_first)
        action = "written"
    print(
        json.dumps(
            {
                "status": "PASS",
                "action": action,
                "output_dir": str(output_dir),
                "route_count": len(summary["routes"]),
                "artifact_count": len(artifacts_first),
                "deterministic_two_build_hashes": True,
                "roots_computed": 0,
                "grid_points_computed": 0,
                "diagnostic_status": DIAGNOSTIC_STATUS,
                "bridge_manifest_sha256": sha256_bytes(artifacts_first["bridge_manifest.json"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
