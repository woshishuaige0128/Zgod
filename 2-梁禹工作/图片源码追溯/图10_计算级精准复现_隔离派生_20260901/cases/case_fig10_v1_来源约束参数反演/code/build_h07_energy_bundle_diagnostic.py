#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""物化H07“能量脚本整束历史来源补全诊断”，但不求根、不跑网格。

H07把作者能量目录六份稳定性脚本视为一整束历史来源：

* 精确ZOH后离散DARE；
* Qe=diag(4e8,1e4,1e2,1e1)，Re=diag(3e-3,1e-2)；
* al与DeltaK/DeltaC均按作者脚本取对角；
* 延迟动力项右乘H，反馈位于H外；
* Guyan采用步骤8B冻结的历史单侧投影。

六份能量脚本都没有形成可直接执行、同时又与步骤8B六路线同维的完整矩阵束：
第一类Guyan的index2越过其H维数，CB的KP_cb/KN_cb/CP_cb/CN_cb没有冻结数值，
Original又与步骤8B维数不同。因此，延迟块明确采用步骤8B低秩混合补全，并标记
``BOARD20_LOW_RANK_HYBRID_DIAGNOSTIC``；六条路线统一标记为
``HISTORICAL_SOURCE_COMPLETION_DIAGNOSTIC_NOT_PAPER_FORMULA_VALID``。

本脚本只读取步骤8B冻结MAT、板块20的MLX合同和六份提取源码；不导入步骤8C
生成器，不读取绘图/校准资产，不调用盲算求根器。
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
from scipy.linalg import expm, solve_discrete_are


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
DEFAULT_OUTPUT_DIR = CASE_DIR / "data" / "h07_energy_bundle_diagnostic"

BOARD20_REL = Path(
    "test/00_失败尝试与候选路线/"
    "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
)
STEP8B_REL = BOARD20_REL / "outputs/step8b_论文代码矩阵合同/步骤8B_基础矩阵与选择矩阵.mat"
MLX_CONTRACT_REL = BOARD20_REL / "outputs/mlx_contract.json"
EXTRACTED_CODE_REL = BOARD20_REL / "outputs/mlx_code/alternative_lqr_route/能量指标"
FROZEN_MLX_REL = BOARD20_REL / "input/alternative_lqr_route/能量指标"

STEP8B_SHA256 = "261852003EEA79A6C7C609C472E82B8782BB7619191C2CFA3759AC39EFCC80FF"
MLX_CONTRACT_SHA256 = "8F873AD0DEEE9F6425819DF669F5F412164DF9D4CE5C7BE3F2751FF0AAF22C88"
BLIND_CORE_SCHEMA = "FIG10_BLIND_CORE_V1"
BLIND_MANIFEST_SCHEMA = "FIG10_BLIND_SEARCH_MANIFEST_V1"
NATIVE_LAYOUT = "MINIMAL_AUGMENTED_CORE_V1"
DIAGNOSTIC_STATUS = "HISTORICAL_SOURCE_COMPLETION_DIAGNOSTIC_NOT_PAPER_FORMULA_VALID"
DELAY_HYBRID_STATUS = "BOARD20_LOW_RANK_HYBRID_DIAGNOSTIC"

Q_ENERGY = np.diag([4.0e8, 1.0e4, 1.0e2, 1.0e1])
R_ENERGY = np.diag([3.0e-3, 1.0e-2])
METHODS = ("Original", "Guyan", "Craig_Bampton")
METHOD_CODE = {"Original": 1, "Guyan": 2, "Craig_Bampton": 3}
METHOD_SCRIPT = {"Original": "ori", "Guyan": "guyan", "Craig_Bampton": "cb"}
EXPECTED_DIMS = {
    (1, "Original"): 15,
    (1, "Guyan"): 6,
    (1, "Craig_Bampton"): 9,
    (2, "Original"): 15,
    (2, "Guyan"): 5,
    (2, "Craig_Bampton"): 8,
}
SCRIPT_DIMS = {
    (1, "Original"): 18,
    (2, "Original"): 18,
    (1, "Guyan"): 6,
    (2, "Guyan"): 5,
    (1, "Craig_Bampton"): 9,
    (2, "Craig_Bampton"): 8,
}
GUYAN_MASTER_DOFS = {
    1: (0, 5, 10, 3, 8, 13),
    2: (0, 10, 3, 8, 13),
}

SOURCE_FILES = {
    "luxvjie_ori_LQR2.m": {
        "mlx": "luxvjie_ori_LQR2.mlx",
        "code_sha256": "1A4F0F8FAD5846542EF4B1961BD41FF4C5ECDBFE8BF6987564A2F975F33A9EAB",
        "mlx_sha256": "8ECA148D813F0C7652F412F5896D2DB8EF5B1279CA0DCBBF10A1FFB45FEA5509",
        "line_count": 42,
        "line_assertions": {
            3: "K2 = KRrt-KNrt_1-KPrt_1;",
            4: "C2 = CRrt-CNrt_1-CPrt_1;",
            5: "K1 = KRrt-K2;",
            6: "C1 = CRrt-C2;",
            8: "al = (4*MRrt+2*dt*CRrt+dt^2*KRrt)\\MRrt*4;",
            14: "row_map = [1 7];",
            27: "H = sym(eye(18));",
            33: "((z-1)/z/dt*C2+K2)*H+S'*DeltaG*S;",
        },
    },
    "luxvjie_ori_LQR3.m": {
        "mlx": "luxvjie_ori_LQR3.mlx",
        "code_sha256": "F1502FCBB2E8689BD2A5558852CACD067C0248F8F50F107FBB30DC2415A53D3C",
        "mlx_sha256": "149E9FDD7F98CFD0A5B581D7BD2B27521908BC89FFB2DEF1F891D4402E4B89D5",
        "line_count": 43,
        "line_assertions": {
            3: "K2 = KRrt-KNrt_1-KPrt_1;",
            4: "C2 = CRrt-CNrt_1-CPrt_1;",
            5: "K1 = KRrt-K2;",
            6: "C1 = CRrt-C2;",
            8: "al = (4*MRrt+2*dt*CRrt+dt^2*KRrt)\\MRrt*4;",
            14: "row_map = [1 13];",
            27: "H = sym(eye(18));",
            33: "((z-1)/z/dt*C2+K2)*H;",
            34: "%+S'*DeltaG*S",
        },
    },
    "luxvjie_guyan_LQR2.m": {
        "mlx": "luxvjie_guyan_LQR2.mlx",
        "code_sha256": "4B919405367AB4C3BF51921A4CDB662B54942A0E7E604A47A11F049ED4D706B3",
        "mlx_sha256": "85B71050673BCB956E397490E41A8BC6D748AF2E633F00F5D0D8968BAFB67102",
        "line_count": 82,
        "line_assertions": {
            1: "index1 = [1,2];",
            2: "index2 = [3,4,5,6,7,8];",
            3: "K2 = KRren;",
            4: "K2(index1,index1) = KRren(index1,index1)-KPren;",
            5: "K2(index2,index2) = KRren(index2,index2)-KNren;",
            6: "C2 = CRren;",
            7: "C2(index1,index1) = CRren(index1,index1)-CPren;",
            8: "C2(index2,index2) = CRren(index2,index2)-CNren;",
            9: "C1 = CRren-C2;",
            10: "K1 = KRren-K2;",
            13: "al = (4*MRren+2*dt*CRren+dt^2*KRren)\\MRren*4;",
            14: "al = diag(diag(al));",
            38: "sys_d = c2d(sys_c, dt);",
            42: "Q = diag([4e8, 1e4, 1e2, 1e1]);",
            43: "R = diag([3e-3,1e-2]);",
            44: "[K_lqr, ~, ~] = dlqr(Ad, Bd, Q, R);",
            49: "DeltaK = diag(diag(MPren*K_lqr(:, 1:n)))",
            50: "DeltaC = diag(diag(MPren*K_lqr(:, n+1:end)));",
            68: "H = sym(eye(6,6));",
            74: "((z-1)/z/dt*C2+K2)*H+S'*DeltaG*S;",
        },
    },
    "luxvjie_guyan_LQR3.m": {
        "mlx": "luxvjie_guyan_LQR3.mlx",
        "code_sha256": "F809DECE535C681D45AEFB0156FCBED3D2EAC85C64C671B9495310F2875E3ACB",
        "mlx_sha256": "3A9291D5FC4B5DD183C88874879B34623B38F3C020F0FBC66991E070936EDE05",
        "line_count": 83,
        "line_assertions": {
            1: "index1 = [1,2];",
            2: "index2 = [3,4,5];",
            3: "K2 = KRren;",
            4: "K2(index1,index1) = KRren(index1,index1)-KPren;",
            5: "K2(index2,index2) = KRren(index2,index2)-KNren;",
            6: "C2 = CRren;",
            7: "C2(index1,index1) = CRren(index1,index1)-CPren;",
            8: "C2(index2,index2) = CRren(index2,index2)-CNren;",
            9: "C1 = CRren-C2;",
            10: "K1 = KRren-K2;",
            13: "al = (4*MRren+2*dt*CRren+dt^2*KRren)\\MRren*4;",
            14: "al = diag(diag(al));",
            38: "sys_d = c2d(sys_c, dt);",
            42: "Q = diag([4e8, 1e4, 1e2, 1e1]);",
            43: "R = diag([3e-3,1e-2]);",
            44: "[K_lqr, ~, ~] = dlqr(Ad, Bd, Q, R);",
            49: "DeltaK = diag(diag(MPren*K_lqr(:, 1:n)))",
            50: "DeltaC = diag(diag(MPren*K_lqr(:, n+1:end)));",
            68: "H = sym(eye(5));",
            74: "((z-1)/z/dt*C2+K2)*H;",
            75: "%+S'*DeltaG*S",
        },
    },
    "luxvjie_cb_LQR2.m": {
        "mlx": "luxvjie_cb_LQR2.mlx",
        "code_sha256": "BD94C9048D52DFA1AEC22C2B851A56881A06CB246E0635A4ED2DEC12D5224FE4",
        "mlx_sha256": "803A5CCE13D2E15F5761D62F87B12F0B0C77376A8AD1718647D226A8DD3E20FD",
        "line_count": 54,
        "line_assertions": {
            1: "index1 = [1,2,7,8,9];",
            2: "index2 = [3,4,5,6,7,8,9];",
            3: "K2 = KR_cb;",
            4: "K2(index1,index1) = KR_cb(index1,index1)-KP_cb;",
            5: "K2(index2,index2) = KR_cb(index2,index2)-KN_cb;",
            6: "C2 = CR_cb;",
            7: "C2(index1,index1) = CR_cb(index1,index1)-CP_cb;",
            8: "C2(index2,index2) = CR_cb(index2,index2)-CN_cb;",
            9: "C1 = CR_cb-C2;",
            10: "K1 = KR_cb-K2;",
            13: "al = (4*MR_cb+2*dt*CR_cb+dt^2*KR_cb)\\MR_cb*4;",
            14: "al = diag(diag(al));",
            40: "H = sym(eye(9,9));",
            46: "((z-1)/z/dt*C2+K2)*H+S'*DeltaG*S;",
        },
    },
    "luxvjie_cb_LQR3.m": {
        "mlx": "luxvjie_cb_LQR3.mlx",
        "code_sha256": "5FE405DEA5D1A6DF1485F69447BF677FFB33545080FDC9297A876931F4329EAF",
        "mlx_sha256": "4BC123ED437DD7E632F0638A009D6BFD08649335480B9730DBAAC01691B72689",
        "line_count": 55,
        "line_assertions": {
            1: "index1 = [1,2,6,7,8];",
            2: "index2 = [3,4,5,6,7,8];",
            3: "K2 = KR_cb;",
            4: "K2(index1,index1) = KR_cb(index1,index1)-KP_cb;",
            5: "K2(index2,index2) = KR_cb(index2,index2)-KN_cb;",
            6: "C2 = CR_cb;",
            7: "C2(index1,index1) = CR_cb(index1,index1)-CP_cb;",
            8: "C2(index2,index2) = CR_cb(index2,index2)-CN_cb;",
            9: "C1 = CR_cb-C2;",
            10: "K1 = KR_cb-K2;",
            13: "al = (4*MR_cb+2*dt*CR_cb+dt^2*KR_cb)\\MR_cb*4;",
            14: "al = diag(diag(al));",
            40: "H = sym(eye(8));",
            46: "((z-1)/z/dt*C2+K2)*H;",
            47: "%+S'*DeltaG*S",
        },
    },
}

OPERATOR_FIELDS = (
    "mass_term",
    "base_zero",
    "base_minus_one",
    "delay_left",
    "delay_v_zero",
    "delay_v_minus_one",
    "register_scales",
)
TOL = 1.0e-12
DARE_TOL = 1.0e-6
SENTINELS = ((0, 0), (1, 0), (0, 1), (3, 7), (10, 20), (15, 33), (30, 66))
SPARSE_COLUMNS = (0, 1, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64, 66)


class H07Error(RuntimeError):
    pass


@dataclass(frozen=True)
class Route:
    route_id: str
    division: int
    method: str
    dimension: int
    source_script: str
    source_support_status: str
    delay_decomposition_status: str
    extrapolation_reasons: tuple[str, ...]
    payload: dict[str, np.ndarray]
    operator: dict[str, np.ndarray]
    stage0: dict[str, Any]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise H07Error(message)


def repo_root() -> Path:
    root = SCRIPT_DIR.parents[4]
    require((root / "WORKFLOW.md").is_file(), f"无法定位仓库根目录：{root}")
    return root


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def csv_bytes(rows: Iterable[Mapping[str, Any]], fields: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def deterministic_mat_bytes(payload: Mapping[str, np.ndarray]) -> bytes:
    buffer = io.BytesIO()
    savemat(buffer, dict(payload), do_compression=True, oned_as="column")
    result = bytearray(buffer.getvalue())
    header = b"MATLAB 5.0 MAT-file, Fig10 H07 energy bundle deterministic"
    result[:116] = header.ljust(116, b" ")[:116]
    return bytes(result)


def numeric(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).copy()


def scalar(value: Any) -> float:
    result = np.asarray(value, dtype=np.float64).reshape(-1)
    require(result.size == 1 and np.isfinite(result[0]), "标量字段非法")
    return float(result[0])


def mat_scalar(value: float | int | bool) -> np.ndarray:
    return np.asarray([[value]], dtype=np.float64)


def utf8_uint8(value: str) -> np.ndarray:
    return np.frombuffer(value.encode("utf-8"), dtype=np.uint8).reshape(-1, 1)


def rel(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)


def semantic_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    description = json.dumps(
        {"dtype": array.dtype.str, "shape": list(array.shape), "order": "C"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(description)
    digest.update(b"\0")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def exact_zoh(a_matrix: np.ndarray, b_matrix: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    states, inputs = b_matrix.shape
    block = np.zeros((states + inputs, states + inputs), dtype=np.float64)
    block[:states, :states] = a_matrix
    block[:states, states:] = b_matrix
    discrete = expm(block * dt)
    return discrete[:states, :states], discrete[:states, states:]


def dare_residual(
    ad: np.ndarray, bd: np.ndarray, p: np.ndarray
) -> float:
    middle = R_ENERGY + bd.T @ p @ bd
    residual = (
        ad.T @ p @ ad
        - p
        - ad.T @ p @ bd @ np.linalg.solve(middle, bd.T @ p @ ad)
        + Q_ENERGY
    )
    denominator = max(float(np.linalg.norm(Q_ENERGY)), np.finfo(float).eps)
    return float(np.linalg.norm(residual) / denominator)


def validate_source_evidence(root: Path) -> dict[str, Any]:
    step8b = root / STEP8B_REL
    mlx_contract = root / MLX_CONTRACT_REL
    require(sha256_file(step8b) == STEP8B_SHA256, "步骤8B冻结MAT哈希漂移")
    require(sha256_file(mlx_contract) == MLX_CONTRACT_SHA256, "MLX合同哈希漂移")
    contract_data = json.loads(mlx_contract.read_text(encoding="utf-8"))
    records = {
        Path(row["extracted_code_relative_path"]).name: row
        for row in contract_data["records"]
        if str(row.get("frozen_relative_path", "")).startswith("alternative_lqr_route/能量指标/")
    }
    evidence_rows = []
    for code_name, expected in SOURCE_FILES.items():
        code_path = root / EXTRACTED_CODE_REL / code_name
        mlx_path = root / FROZEN_MLX_REL / expected["mlx"]
        require(code_path.is_file() and mlx_path.is_file(), f"能量脚本证据缺失：{code_name}")
        require(sha256_file(code_path) == expected["code_sha256"], f"提取源码哈希漂移：{code_name}")
        require(sha256_file(mlx_path) == expected["mlx_sha256"], f"冻结MLX哈希漂移：{expected['mlx']}")
        lines = code_path.read_text(encoding="utf-8").splitlines()
        require(len(lines) == expected["line_count"], f"源码行数漂移：{code_name}")
        for line_number, exact in expected["line_assertions"].items():
            require(lines[line_number - 1].strip() == exact, f"源码行漂移：{code_name}:{line_number}")
        record = records.get(code_name)
        require(record is not None, f"MLX合同缺少记录：{code_name}")
        require(str(record["source_sha256"]).upper() == expected["mlx_sha256"], f"MLX合同源哈希不符：{code_name}")
        evidence_rows.append(
            {
                "code_file": code_name,
                "code_repo_relative_path": code_path.relative_to(root).as_posix(),
                "code_sha256": expected["code_sha256"],
                "mlx_file": expected["mlx"],
                "mlx_repo_relative_path": mlx_path.relative_to(root).as_posix(),
                "mlx_sha256": expected["mlx_sha256"],
                "line_count": expected["line_count"],
                "line_assertions": [
                    {"line": number, "exact_text": text}
                    for number, text in expected["line_assertions"].items()
                ],
            }
        )
    return {
        "step8b_path": step8b,
        "step8b_sha256": STEP8B_SHA256,
        "mlx_contract_sha256": MLX_CONTRACT_SHA256,
        "source_scripts": evidence_rows,
    }


def base_prefix(division: int, method: str) -> str:
    if method == "Original":
        return f"div{division}_Original_source_full15"
    if method == "Guyan":
        return f"div{division}_Guyan_source_historical_single_sided"
    return f"div{division}_Craig_Bampton_source_sorted_three_modes"


def source_support(division: int, method: str) -> tuple[str, tuple[str, ...]]:
    reasons: list[str] = [
        "step8b_low_rank_delay_completion_used_because_energy_KN_CN_blocks_are_not_frozen_for_all_six_routes"
    ]
    if method != "Guyan":
        reasons.append("controller_ZOH_DARE_Qe_Re_and_diagonal_feedback_not_defined_locally")
    if division == 2:
        reasons.append("feedback_term_commented_out_in_characteristic_matrix")
    if method == "Original":
        reasons.append("diag_al_not_present_in_original_energy_script")
        reasons.append("energy_script_dimension_18_completed_with_frozen_step8B_dimension_15")
    if division == 1 and method == "Guyan":
        reasons.append("energy_script_index2_3_to_8_exceeds_H_dimension_6")
    if method == "Craig_Bampton":
        reasons.append("energy_script_KP_cb_KN_cb_CP_cb_CN_cb_values_are_not_defined_in_frozen_source_bundle")
        reasons.append("energy_script_index1_and_index2_overlap_in_fixed_interface_coordinates")
    return DIAGNOSTIC_STATUS, tuple(reasons)


def build_route(source: Mapping[str, Any], division: int, method: str) -> Route:
    prefix = base_prefix(division, method)
    mass = numeric(source[f"{prefix}_M"])
    damping = numeric(source[f"{prefix}_C"])
    stiffness = numeric(source[f"{prefix}_K"])
    n = mass.shape[0]
    require(n == EXPECTED_DIMS[(division, method)], "步骤8B路线维数不符")
    require(mass.shape == damping.shape == stiffness.shape == (n, n), "路线M/C/K形状不符")
    recovery = numeric(source[f"div{division}_{method}_recovery_natural"])
    embedding = numeric(source[f"div{division}_local_embedding_E"])
    local_selection = numeric(source[f"div{division}_local_delay_selection_J_psi1_psi6"])
    selector_right = local_selection @ embedding.T @ recovery
    if method == "Guyan":
        test_basis = np.eye(15)[:, GUYAN_MASTER_DOFS[division]]
    else:
        test_basis = recovery.copy()
    full = {
        symbol: numeric(source[f"div{division}_Original_source_full15_{symbol}"])
        for symbol in ("M", "C", "K")
    }
    base_projection_error = max(
        rel(value, test_basis.T @ full[symbol] @ recovery)
        for symbol, value in (("M", mass), ("C", damping), ("K", stiffness))
    )
    local_full = {
        symbol: numeric(source[f"div{division}_local_full_{symbol}"])
        for symbol in ("M", "C", "K")
    }
    # 冻结能量源码没有给出六路线齐全且同维的KN/CN数值块。这里复制步骤8B的
    # 两通道低秩补全逻辑；它只决定H实际作用的两列，其余H恒为1的列并入base。
    # 这不是作者能量块的逐元素等价认领，必须随包标成DELAY_HYBRID_STATUS。
    delay_c_left = test_basis.T @ embedding @ local_full["C"] @ local_selection.T
    delay_k_left = test_basis.T @ embedding @ local_full["K"] @ local_selection.T
    delay_right = selector_right
    c2 = delay_c_left @ delay_right
    k2 = delay_k_left @ delay_right
    c1 = damping - c2
    k1 = stiffness - k2

    local_mass = numeric(source[f"div{division}_author_final_local2_M"])
    local_damping = numeric(source[f"div{division}_author_final_local2_C"])
    local_stiffness = numeric(source[f"div{division}_author_final_local2_K"])
    require(local_mass.shape == local_damping.shape == local_stiffness.shape == (2, 2), "局部控制矩阵必须为2x2")
    identity = np.eye(2)
    zero = np.zeros((2, 2))
    a_matrix = np.block(
        [[zero, identity], [-np.linalg.solve(local_mass, local_stiffness), -np.linalg.solve(local_mass, local_damping)]]
    )
    b_matrix = np.vstack((zero, np.linalg.solve(local_mass, identity)))
    dt = scalar(source[f"div{division}_source_dt"])
    require(abs(dt - 1.0 / 1024.0) <= np.finfo(float).eps, "能量脚本dt必须为1/1024")
    ad, bd = exact_zoh(a_matrix, b_matrix, dt)
    p = solve_discrete_are(ad, bd, Q_ENERGY, R_ENERGY)
    gain = np.linalg.solve(bd.T @ p @ bd + R_ENERGY, bd.T @ p @ ad)
    delta_k_raw = local_mass @ gain[:, :2]
    delta_c_raw = local_mass @ gain[:, 2:]
    delta_k = np.diag(np.diag(delta_k_raw))
    delta_c = np.diag(np.diag(delta_c_raw))
    feedback_k = selector_right.T @ delta_k @ selector_right
    feedback_c = selector_right.T @ delta_c @ selector_right
    dare_error = dare_residual(ad, bd, p)
    closed_loop_radius = float(np.max(np.abs(np.linalg.eigvals(ad - bd @ gain))))

    al_full = np.linalg.solve(4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness, 4.0 * mass)
    al_diag = np.diag(np.diag(al_full))
    diagonal_values = np.diag(al_diag)
    require(np.all(np.isfinite(diagonal_values)) and np.all(np.abs(diagonal_values) > np.finfo(float).eps), "diag(al)奇异")
    integration_mass = np.linalg.solve(al_diag.T, mass.T).T
    physical_mass_term = integration_mass / dt**2
    physical_base_zero = -2.0 * physical_mass_term + c1 / dt + k1 + feedback_c / dt + feedback_k
    physical_base_minus = physical_mass_term - c1 / dt - feedback_c / dt

    # 作者六份能量稳定脚本均采用(...C2+K2)*H。其两通道表示共享右因子，
    # 因而对完整多项式算子取转置后进入原生共享左因子布局。
    delay_left = delay_right.T
    delay_v_zero = delay_c_left.T / dt + delay_k_left.T
    delay_v_minus = -delay_c_left.T / dt
    register_scales = np.maximum.reduce(
        (
            np.linalg.norm(delay_v_zero, axis=1),
            np.linalg.norm(delay_v_minus, axis=1),
            np.full(2, np.finfo(float).eps),
        )
    )
    operator = {
        "mass_term": np.ascontiguousarray(physical_mass_term.T),
        "base_zero": np.ascontiguousarray(physical_base_zero.T),
        "base_minus_one": np.ascontiguousarray(physical_base_minus.T),
        "delay_left": np.ascontiguousarray(delay_left),
        "delay_v_zero": np.ascontiguousarray(delay_v_zero),
        "delay_v_minus_one": np.ascontiguousarray(delay_v_minus),
        "register_scales": np.ascontiguousarray(register_scales),
    }
    actual_zero = operator["base_zero"] + operator["delay_left"] @ operator["delay_v_zero"]
    actual_minus = operator["base_minus_one"] + operator["delay_left"] @ operator["delay_v_minus_one"]
    expected_zero = (-2.0 * physical_mass_term + (damping + feedback_c) / dt + stiffness + feedback_k).T
    expected_minus = (physical_mass_term - (damping + feedback_c) / dt).T
    source_status, extrapolation_reasons = source_support(division, method)
    route_id = f"H07_D{division}_{method}"
    checks = {
        "base_projection_relative_error": base_projection_error,
        "delay_C_low_rank_factorization_relative_error": rel(c2, delay_c_left @ delay_right),
        "delay_K_low_rank_factorization_relative_error": rel(k2, delay_k_left @ delay_right),
        "C_delay_closure_relative_error": rel(c1 + c2, damping),
        "K_delay_closure_relative_error": rel(k1 + k2, stiffness),
        "al_linear_solve_relative_error": rel(
            (4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness) @ al_full,
            4.0 * mass,
        ),
        "al_diagonal_offdiagonal_norm": float(np.linalg.norm(al_diag - np.diag(np.diag(al_diag)))),
        "DeltaK_diagonal_offdiagonal_norm": float(np.linalg.norm(delta_k - np.diag(np.diag(delta_k)))),
        "DeltaC_diagonal_offdiagonal_norm": float(np.linalg.norm(delta_c - np.diag(np.diag(delta_c)))),
        "dare_relative_residual": dare_error,
        "closed_loop_radius": closed_loop_radius,
        "zero_delay_operator_relative_error": rel(actual_zero, expected_zero),
        "minus_one_operator_relative_error": rel(actual_minus, expected_minus),
    }
    require(base_projection_error <= TOL, "步骤8B路线投影闭合失败")
    require(max(checks[name] for name in ("delay_C_low_rank_factorization_relative_error", "delay_K_low_rank_factorization_relative_error", "C_delay_closure_relative_error", "K_delay_closure_relative_error", "al_linear_solve_relative_error", "al_diagonal_offdiagonal_norm", "DeltaK_diagonal_offdiagonal_norm", "DeltaC_diagonal_offdiagonal_norm", "zero_delay_operator_relative_error", "minus_one_operator_relative_error")) <= TOL, "H07 Stage0代数闭合失败")
    require(dare_error <= DARE_TOL and closed_loop_radius < 1.0, "H07 DARE设计门失败")
    require(np.linalg.matrix_rank(operator["mass_term"]) == n, "H07 mass_term不满秩")
    require(np.all(register_scales > 0.0), "H07 register_scales非法")

    script_name = f"luxvjie_{METHOD_SCRIPT[method]}_LQR{division + 1}.m"
    stage0 = {
        "route_id": route_id,
        "division": division,
        "method": method,
        "dimension": n,
        "source_script": script_name,
        "source_script_dimension": SCRIPT_DIMS[(division, method)],
        "source_support_status": source_status,
        "delay_decomposition_status": DELAY_HYBRID_STATUS,
        "energy_literal_KN_CN_block_equivalence_claimed": False,
        "extrapolation_required": bool(extrapolation_reasons),
        "extrapolation_reasons": ";".join(extrapolation_reasons),
        "controller_bundle": "EXACT_ZOH_DARE_QE_RE_DIAG_DELTA",
        "integration_bundle": "ROUTE_MATRIX_AL_THEN_DIAG_AL",
        "delay_orientation": "H_RIGHT_TRANSPOSED_TO_NATIVE_SHARED_LEFT",
        "feedback_placement": "OUTSIDE_H",
        "guyan_projection": "HISTORICAL_SINGLE_SIDED" if method == "Guyan" else "NOT_APPLICABLE",
        **checks,
        "mass_term_rank": int(np.linalg.matrix_rank(operator["mass_term"])),
        "register_scales_positive": bool(np.all(register_scales > 0.0)),
        "formula_valid_code": 0,
        "paper_grid_eligible_code": 0,
        "roots_computed": 0,
        "grid_points_computed": 0,
        "stage0_pass": True,
    }
    payload: dict[str, np.ndarray] = {
        "bundle_schema_version": mat_scalar(1),
        "route_dimension": mat_scalar(n),
        "division": mat_scalar(division),
        "method_index": mat_scalar(METHOD_CODE[method]),
        "candidate_index": mat_scalar(7),
        "formula_valid_code": mat_scalar(0),
        "paper_grid_eligible_code": mat_scalar(0),
        "scientific_search_executed_code": mat_scalar(0),
        "roots_computed": mat_scalar(0),
        "grid_points_computed": mat_scalar(0),
        "operator_transpose_for_shared_left_code": mat_scalar(1),
        "dt": mat_scalar(dt),
        "Q_energy": Q_ENERGY.copy(),
        "R_energy": R_ENERGY.copy(),
        "M": mass,
        "C": damping,
        "K": stiffness,
        "R_recovery": recovery,
        "W_test_basis": test_basis,
        "S_R": selector_right,
        "M_controller_local": local_mass,
        "C_controller_local": local_damping,
        "K_controller_local": local_stiffness,
        "A_continuous": a_matrix,
        "B_continuous": b_matrix,
        "A_discrete_zoh": ad,
        "B_discrete_zoh": bd,
        "riccati_solution_P": p,
        "controller_gain": gain,
        "DeltaK_raw": delta_k_raw,
        "DeltaC_raw": delta_c_raw,
        "DeltaK_diag": delta_k,
        "DeltaC_diag": delta_c,
        "feedback_K": feedback_k,
        "feedback_C": feedback_c,
        "C1": c1,
        "K1": k1,
        "C2_completed_delayed_columns": c2,
        "K2_completed_delayed_columns": k2,
        "delay_C_left_H_right": delay_c_left,
        "delay_K_left_H_right": delay_k_left,
        "delay_right_selector": delay_right,
        "matrix_al_full": al_full,
        "matrix_al_diag": al_diag,
        "integration_mass_operator": integration_mass,
        **{name: value for name, value in operator.items() if name != "register_scales"},
        "register_scales": register_scales.reshape(-1, 1),
        "shared_left_factor_relative_error": mat_scalar(0.0),
        "stage0_dare_relative_residual": mat_scalar(dare_error),
        "stage0_zero_delay_operator_relative_error": mat_scalar(checks["zero_delay_operator_relative_error"]),
        "stage0_overall_pass_code": mat_scalar(1),
        "blind_core_schema_version_utf8": utf8_uint8(BLIND_CORE_SCHEMA),
        "operator_layout_utf8": utf8_uint8(NATIVE_LAYOUT),
        "contract_id_utf8": utf8_uint8("H07"),
        "source_script_utf8": utf8_uint8(script_name),
        "source_support_status_utf8": utf8_uint8(source_status),
        "delay_decomposition_status_utf8": utf8_uint8(DELAY_HYBRID_STATUS),
        "energy_literal_KN_CN_block_equivalence_claimed_code": mat_scalar(0),
        "extrapolation_reasons_utf8": utf8_uint8(";".join(extrapolation_reasons)),
    }
    return Route(
        route_id=route_id,
        division=division,
        method=method,
        dimension=n,
        source_script=script_name,
        source_support_status=source_status,
        delay_decomposition_status=DELAY_HYBRID_STATUS,
        extrapolation_reasons=extrapolation_reasons,
        payload=payload,
        operator=operator,
        stage0=stage0,
    )


def route_operator_sha256(route: Route) -> str:
    record = {
        "route_dimension": route.dimension,
        "dt_seconds": format(scalar(route.payload["dt"]), ".17g"),
        "operator_arrays": {
            name: {
                "shape": list(np.asarray(route.operator[name]).shape),
                "semantic_array_sha256": semantic_array_sha256(route.operator[name]),
            }
            for name in OPERATOR_FIELDS
        },
    }
    return sha256_bytes(json.dumps(record, sort_keys=True, separators=(",", ":")).encode("ascii"))


def sampling() -> dict[str, Any]:
    return {
        "grid": {"l_min": 0, "l_max": 30, "j_min": 0, "j_max": 66},
        "sentinel_points": [list(point) for point in SENTINELS],
        "fixed_sparse_band_points": [[l_value, j_value] for j_value in SPARSE_COLUMNS for l_value in range(31)],
    }


def build_artifacts(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    evidence = validate_source_evidence(root)
    source = {
        key: value
        for key, value in loadmat(evidence["step8b_path"], simplify_cells=True).items()
        if not key.startswith("__")
    }
    routes = [build_route(source, division, method) for division in (1, 2) for method in METHODS]
    require(len(routes) == 6 and all(route.stage0["stage0_pass"] for route in routes), "H07六路线Stage0未闭合")
    artifacts: dict[str, bytes] = {}
    bundle_hashes: dict[str, str] = {}
    for route in routes:
        relative = f"numeric_bundles/{route.route_id}_native.mat"
        payload = deterministic_mat_bytes(route.payload)
        artifacts[relative] = payload
        bundle_hashes[route.route_id] = sha256_bytes(payload)

    scientific_contract = {
        "contract_id": "H07",
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "controller": {
            "continuous_to_discrete": "EXACT_ZOH",
            "riccati": "DARE",
            "Qe_diagonal": [4.0e8, 1.0e4, 1.0e2, 1.0e1],
            "Re_diagonal": [3.0e-3, 1.0e-2],
            "DeltaK": "diag(diag(M_local*K_lqr_position))",
            "DeltaC": "diag(diag(M_local*K_lqr_velocity))",
        },
        "integration": "al_full=solve(4M+2dtC+dt^2K,4M); al=diag(diag(al_full)); integration=M/al",
        "delay": "energy-script H_RIGHT; step8B two-channel low-rank hybrid completion; complete polynomial operator transposed for native shared-left layout",
        "delay_decomposition_status": DELAY_HYBRID_STATUS,
        "energy_literal_KN_CN_block_equivalence_claimed": False,
        "feedback_placement": "OUTSIDE_H_COMPLETED_AS_PART_OF_THE_WHOLE_BUNDLE",
        "guyan_projection": "HISTORICAL_SINGLE_SIDED",
        "route_completion_policy": "no single-factor ablation; all seven bundle choices move together",
        "step8b_sha256": STEP8B_SHA256,
        "source_script_hashes": {
            name: {"code_sha256": row["code_sha256"], "mlx_sha256": row["mlx_sha256"]}
            for name, row in SOURCE_FILES.items()
        },
    }
    contract_hash = sha256_bytes(
        json.dumps(scientific_contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    manifest_routes = []
    for route in routes:
        operator_hash = route_operator_sha256(route)
        route.stage0["route_operator_sha256"] = operator_hash
        manifest_routes.append(
            {
                "route_id": route.route_id,
                "contract_id": "H07",
                "contract_hash": contract_hash,
                "division": route.division,
                "method": route.method,
                "dimension": route.dimension,
                "candidate_index": 7,
                "operator_layout": NATIVE_LAYOUT,
                "bundle_path": f"../numeric_bundles/{route.route_id}_native.mat",
                "bundle_sha256": bundle_hashes[route.route_id],
                "route_operator_sha256": operator_hash,
                "source_script": route.source_script,
                "source_support_status": route.source_support_status,
                "delay_decomposition_status": route.delay_decomposition_status,
                "energy_literal_KN_CN_block_equivalence_claimed": False,
                "extrapolation_required": bool(route.extrapolation_reasons),
                "extrapolation_reasons": list(route.extrapolation_reasons),
                "formula_valid_code": 0,
                "paper_grid_eligible_code": 0,
                "stage0_status": "PASS_MATERIALIZATION_ONLY_NO_ROOTS_NO_GRID",
            }
        )
    manifest = {
        "schema_version": BLIND_MANIFEST_SCHEMA,
        "blind_core_schema_version": BLIND_CORE_SCHEMA,
        "run_id": "FIG10_H07_ENERGY_BUNDLE_HISTORICAL_SOURCE_COMPLETION_DIAGNOSTIC",
        "evidence_level": DIAGNOSTIC_STATUS,
        "target_dependency": "FORBIDDEN_BLIND_CALCULATION_ONLY",
        "paper_formula_eligible": False,
        "paper_grid_eligible": False,
        "execution_policy": "DIAGNOSTIC_ONLY_REQUIRES_EXPLICIT_SEPARATE_RUN",
        "scientific_search_executed": False,
        "roots_computed": 0,
        "grid_points_computed": 0,
        "allowed_bundle_roots": ["../numeric_bundles"],
        "sampling": sampling(),
        "scientific_contract": scientific_contract,
        "routes": manifest_routes,
    }
    artifacts["manifests/H07.json"] = canonical_json_bytes(manifest)
    artifacts["source_code_evidence.json"] = canonical_json_bytes(
        {
            "schema_version": "FIG10_H07_SOURCE_CODE_EVIDENCE_V1",
            "status": "PASS",
            "step8b_sha256": evidence["step8b_sha256"],
            "mlx_contract_sha256": evidence["mlx_contract_sha256"],
            "source_scripts": evidence["source_scripts"],
        }
    )
    stage_fields = [
        "route_id", "division", "method", "dimension", "source_script",
        "source_script_dimension", "source_support_status", "extrapolation_required",
        "delay_decomposition_status", "energy_literal_KN_CN_block_equivalence_claimed",
        "extrapolation_reasons", "controller_bundle", "integration_bundle",
        "delay_orientation", "feedback_placement", "guyan_projection",
        "base_projection_relative_error", "delay_C_low_rank_factorization_relative_error",
        "delay_K_low_rank_factorization_relative_error", "C_delay_closure_relative_error",
        "K_delay_closure_relative_error", "al_linear_solve_relative_error",
        "al_diagonal_offdiagonal_norm", "DeltaK_diagonal_offdiagonal_norm",
        "DeltaC_diagonal_offdiagonal_norm", "dare_relative_residual",
        "closed_loop_radius", "zero_delay_operator_relative_error",
        "minus_one_operator_relative_error", "mass_term_rank",
        "register_scales_positive", "formula_valid_code", "paper_grid_eligible_code",
        "route_operator_sha256", "roots_computed", "grid_points_computed", "stage0_pass",
    ]
    artifacts["stage0_gate_results.csv"] = csv_bytes([route.stage0 for route in routes], stage_fields)
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
                    "finite": bool(np.all(np.isfinite(value))),
                    "semantic_array_sha256": semantic_array_sha256(value),
                }
            )
    artifacts["array_hash_inventory.csv"] = csv_bytes(
        array_rows, ["route_id", "field", "shape", "dtype", "finite", "semantic_array_sha256"]
    )
    manifest_summary = {
        "schema_version": "FIG10_H07_MATERIALIZATION_MANIFEST_V1",
        "status": "PASS_STAGE0_H07_ENERGY_BUNDLE_DIAGNOSTIC",
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "delay_decomposition_status": DELAY_HYBRID_STATUS,
        "contract_sha256": contract_hash,
        "h07_blind_manifest_sha256": sha256_bytes(artifacts["manifests/H07.json"]),
        "counts": {
            "route_count": 6,
            "direct_source_bundle_routes": sum(not route.extrapolation_reasons for route in routes),
            "source_completion_routes": sum(bool(route.extrapolation_reasons) for route in routes),
            "low_rank_hybrid_delay_routes": sum(
                route.delay_decomposition_status == DELAY_HYBRID_STATUS for route in routes
            ),
            "stage0_pass": 6,
            "stage0_fail": 0,
            "formula_valid_code_zero": 6,
            "paper_grid_eligible_code_zero": 6,
            "roots_computed": 0,
            "grid_points_computed": 0,
        },
        "blind_core_modified": False,
        "single_factor_ablation_performed": False,
        "artifacts": [
            {"relative_path": name, "sha256": sha256_bytes(payload), "bytes": len(payload)}
            for name, payload in sorted(artifacts.items())
        ],
    }
    artifacts["h07_materialization_manifest.json"] = canonical_json_bytes(manifest_summary)
    return artifacts, {"routes": routes, "manifest": manifest_summary}


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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
    require(output_dir.is_dir(), f"H07输出目录不存在：{output_dir}")
    actual = {path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file()}
    require(actual == set(artifacts), f"H07输出文件集合漂移：missing={sorted(set(artifacts)-actual)}, extra={sorted(actual-set(artifacts))}")
    for name, payload in artifacts.items():
        require((output_dir / name).read_bytes() == payload, f"H07工件字节漂移：{name}")


def write_output(output_dir: Path, artifacts: Mapping[str, bytes]) -> None:
    if output_dir.exists():
        unexpected = {path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*") if path.is_file()} - set(artifacts)
        require(not unexpected, f"H07目录存在非本生成器文件：{sorted(unexpected)}")
    for name, payload in artifacts.items():
        atomic_write(output_dir / name, payload)
    verify_output(output_dir, artifacts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = args.output_dir.resolve()
    require(output.is_relative_to(CASE_DIR.resolve()), "H07输出必须位于隔离案例内")
    first, summary = build_artifacts(root)
    second, _ = build_artifacts(root)
    require(
        {name: sha256_bytes(value) for name, value in first.items()}
        == {name: sha256_bytes(value) for name, value in second.items()},
        "H07双轮内存构建不确定",
    )
    if args.verify_existing:
        verify_output(output, first)
        action = "verified"
    else:
        write_output(output, first)
        action = "written"
    print(
        json.dumps(
            {
                "status": "PASS",
                "action": action,
                "output_dir": str(output),
                "route_count": len(summary["routes"]),
                "artifact_count": len(first),
                "direct_source_bundle_routes": summary["manifest"]["counts"]["direct_source_bundle_routes"],
                "source_completion_routes": summary["manifest"]["counts"]["source_completion_routes"],
                "deterministic_two_build_hashes": True,
                "roots_computed": 0,
                "grid_points_computed": 0,
                "diagnostic_status": DIAGNOSTIC_STATUS,
                "materialization_manifest_sha256": sha256_bytes(first["h07_materialization_manifest.json"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
