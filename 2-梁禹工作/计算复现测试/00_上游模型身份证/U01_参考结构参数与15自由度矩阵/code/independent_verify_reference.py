# -*- coding: utf-8 -*-
"""按梁柱连接关系独立装配梁禹15自由度参考模型并复核MATLAB结果。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
from scipy.io import loadmat
from scipy.linalg import eigh


SCRIPT_PATH = Path(__file__).resolve()
BASE_DIR = SCRIPT_PATH.parents[1]
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "outputs"
PROJECT_ROOT = BASE_DIR.parents[2]
MATLAB_RESULT = OUTPUT_DIR / "reference_model_matlab.mat"

EXPECTED_FREQUENCY = np.array(
    [2.707425741915, 9.328408686763, 18.4426700565, 22.6735592218, 24.2277487321],
    dtype=float,
)
EXPECTED_RAYLEIGH = np.array([1.318462500458, 0.001322342410366], dtype=float)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def bending_matrix(ei: float, length: float) -> np.ndarray:
    """Euler-Bernoulli梁弯曲矩阵，顺序[v_i,theta_i,v_j,theta_j]。"""
    length2 = length * length
    return ei / length**3 * np.array(
        [
            [12.0, 6.0 * length, -12.0, 6.0 * length],
            [6.0 * length, 4.0 * length2, -6.0 * length, 2.0 * length2],
            [-12.0, -6.0 * length, 12.0, -6.0 * length],
            [6.0 * length, 2.0 * length2, -6.0 * length, 4.0 * length2],
        ],
        dtype=float,
    )


def assemble_reference(e_pa: float, rho_kg_m3: float) -> tuple[np.ndarray, np.ndarray]:
    """不用MATLAB 15x15拼表，按3层4柱3梁连接关系独立装配M/K。"""
    beam_length = 0.762
    column_length = 0.635
    column_inertia = 2.520 * (25.4 / 1000.0) ** 4
    beam_inertia = 0.6132 * (25.4 / 1000.0) ** 4
    column_area = 1.670 * (25.4 / 1000.0) ** 2
    beam_area = 0.947 * (25.4 / 1000.0) ** 2

    column_local = bending_matrix(e_pa * column_inertia, column_length)
    # MATLAB中竖直柱由Tc变换；global x对应local v的负方向，转角符号不变。
    column_sign = np.diag([-1.0, 1.0, -1.0, 1.0])
    column_global = column_sign.T @ column_local @ column_sign
    beam_local = bending_matrix(e_pa * beam_inertia, beam_length)
    beam_rotation = beam_local[np.ix_([1, 3], [1, 3])]

    stiffness = np.zeros((15, 15), dtype=float)

    def add_element(element: np.ndarray, dofs: list[int | None]) -> None:
        for local_i, global_i in enumerate(dofs):
            if global_i is None:
                continue
            for local_j, global_j in enumerate(dofs):
                if global_j is None:
                    continue
                stiffness[global_i, global_j] += element[local_i, local_j]

    # 每层自由度：[公共水平位移, 四个柱节点转角]。
    for story in range(3):
        for column in range(4):
            if story == 0:
                bottom_u = None
                bottom_theta = None
            else:
                bottom_u = 5 * (story - 1)
                bottom_theta = 5 * (story - 1) + 1 + column
            top_u = 5 * story
            top_theta = 5 * story + 1 + column
            add_element(column_global, [bottom_u, bottom_theta, top_u, top_theta])

    for floor in range(3):
        for bay in range(3):
            left_rotation = 5 * floor + 1 + bay
            right_rotation = 5 * floor + 2 + bay
            add_element(beam_rotation, [left_rotation, right_rotation])

    beam_mass = rho_kg_m3 * beam_area * beam_length
    column_mass = rho_kg_m3 * column_area * column_length
    translation_mass = 3.0 * beam_mass + 4.0 * column_mass
    edge_rotation_inertia = (beam_mass / 2.0) * beam_length**2 / 12.0 + column_mass * column_length**2 / 12.0
    interior_rotation_inertia = beam_mass * beam_length**2 / 12.0 + column_mass * column_length**2 / 12.0
    floor_diagonal = [
        translation_mass,
        edge_rotation_inertia,
        interior_rotation_inertia,
        interior_rotation_inertia,
        edge_rotation_inertia,
    ]
    mass = np.diag(np.array(floor_diagonal * 3, dtype=float))
    return mass, stiffness


def solve_modes(mass: np.ndarray, stiffness: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eigenvalues, modes = eigh(stiffness, mass, check_finite=True)
    if not np.all(eigenvalues > 0):
        raise AssertionError("独立装配模型存在非正广义特征值")
    frequency_hz = np.sqrt(eigenvalues) / (2.0 * np.pi)
    return frequency_hz, modes


def rayleigh_matrix(
    mass: np.ndarray, stiffness: np.ndarray, frequency_hz: np.ndarray, damping_ratio: float = 0.05
) -> tuple[np.ndarray, float, float]:
    omega = 2.0 * np.pi * frequency_hz[:2]
    system = 0.5 * np.array([[1.0 / omega[0], omega[0]], [1.0 / omega[1], omega[1]]])
    alpha, beta = np.linalg.solve(system, np.array([damping_ratio, damping_ratio]))
    return alpha * mass + beta * stiffness, float(alpha), float(beta)


def effective_mass_ratios(modes: np.ndarray, mass: np.ndarray, direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    modal_mass = np.einsum("ij,ij->j", modes, mass @ modes)
    modal_force = modes.T @ mass @ direction
    ratios = modal_force**2 / (modal_mass * float(direction.T @ mass @ direction))
    return ratios, np.cumsum(ratios)


def relative_frobenius(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.linalg.norm(actual - expected, ord="fro") / np.linalg.norm(expected, ord="fro"))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"不允许写空CSV：{path}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_energy_zonghe_history(path: Path) -> tuple[np.ndarray, int, dict[str, bool]]:
    """提取作者MLX声明为15x1的首个participation_ratio可见历史值。"""
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("matlab/document.xml")
        output_xml = archive.read("matlab/output.xml")

    document_text = "\n".join(ElementTree.fromstring(document_xml).itertext())
    code_markers = {
        "horizontal_direction_after_reorder": "r=[1,1,1,0,0,0,0,0,0,0,0,0,0,0,0]'" in document_text,
        "reorder_index3_index4": "order = [index3,index4]" in document_text,
        "reorder_stiffness": "K = KRrt(order,order)" in document_text,
        "reorder_mass": "M = MRrt(order,order)" in document_text,
        "mass_weighted_gamma": "Gamma(i) = phi(:,i)' * M * r" in document_text,
        "normalized_gamma_square": "participation_ratio = GammaSq / sum(GammaSq)" in document_text,
    }

    root = ElementTree.fromstring(output_xml)
    history: np.ndarray | None = None
    declared_rows = 0
    for output_data in root.iter("outputData"):
        name = output_data.findtext("name")
        size = output_data.findtext("varSize")
        value = output_data.findtext("value")
        if name == "participation_ratio" and size == "15×1" and value:
            parsed = np.array([float(item) for item in re.findall(r"[-+]?\d*\.\d+(?:[Ee][-+]?\d+)?", value)])
            if parsed.size:
                history = parsed
                declared_rows = 15
                break
    if history is None:
        raise ValueError("energy_zonghe.mlx未找到声明为15x1的participation_ratio历史输出")
    return history, declared_rows, code_markers


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    checks: list[dict[str, object]] = []

    matlab = loadmat(
        MATLAB_RESULT,
        squeeze_me=True,
        struct_as_record=False,
        variable_names=[
            "MRrt",
            "CRrt",
            "KRrt",
            "frequency_hz",
            "rayleigh_alpha",
            "rayleigh_beta",
        ],
    )
    matlab_mass = np.asarray(matlab["MRrt"], dtype=float)
    matlab_damping = np.asarray(matlab["CRrt"], dtype=float)
    matlab_stiffness = np.asarray(matlab["KRrt"], dtype=float)
    matlab_frequency = np.asarray(matlab["frequency_hz"], dtype=float).reshape(-1)
    matlab_alpha = float(np.asarray(matlab["rayleigh_alpha"]).reshape(()))
    matlab_beta = float(np.asarray(matlab["rayleigh_beta"]).reshape(()))

    mass, stiffness = assemble_reference(206e9, 785e3 * 1.9)
    frequency, modes = solve_modes(mass, stiffness)
    damping, alpha, beta = rayleigh_matrix(mass, stiffness, frequency)

    comparisons = {
        "M_relative_frobenius": relative_frobenius(mass, matlab_mass),
        "C_relative_frobenius": relative_frobenius(damping, matlab_damping),
        "K_relative_frobenius": relative_frobenius(stiffness, matlab_stiffness),
        "all_frequency_max_abs_hz": float(np.max(np.abs(frequency - matlab_frequency))),
        "expected_first5_max_abs_hz": float(np.max(np.abs(frequency[:5] - EXPECTED_FREQUENCY))),
        "rayleigh_alpha_relative": abs(alpha - matlab_alpha) / abs(matlab_alpha),
        "rayleigh_beta_relative": abs(beta - matlab_beta) / abs(matlab_beta),
        "expected_alpha_relative": abs(alpha - EXPECTED_RAYLEIGH[0]) / abs(EXPECTED_RAYLEIGH[0]),
        "expected_beta_relative": abs(beta - EXPECTED_RAYLEIGH[1]) / abs(EXPECTED_RAYLEIGH[1]),
    }
    thresholds = {
        "M_relative_frobenius": 1e-12,
        "C_relative_frobenius": 1e-12,
        "K_relative_frobenius": 1e-12,
        "all_frequency_max_abs_hz": 1e-10,
        "expected_first5_max_abs_hz": 1e-9,
        "rayleigh_alpha_relative": 1e-10,
        "rayleigh_beta_relative": 1e-10,
        "expected_alpha_relative": 1e-10,
        "expected_beta_relative": 1e-10,
    }
    for name, actual in comparisons.items():
        passed = actual < thresholds[name]
        checks.append({"check": name, "actual": f"{actual:.17g}", "threshold_less_than": thresholds[name], "result": "PASS" if passed else "FAIL"})
        if not passed:
            failures.append(f"{name}={actual} 不小于 {thresholds[name]}")

    for matrix_name, matrix in (("M", mass), ("C", damping), ("K", stiffness)):
        symmetry = relative_frobenius(matrix, matrix.T)
        rank = int(np.linalg.matrix_rank(matrix))
        minimum_eigenvalue = float(np.min(np.linalg.eigvalsh((matrix + matrix.T) / 2.0)))
        passed = symmetry < 1e-12 and rank == 15 and minimum_eigenvalue > 0
        checks.append(
            {
                "check": f"{matrix_name}_dimension_rank_symmetry_positive",
                "actual": f"shape={matrix.shape};rank={rank};sym={symmetry:.17g};minEig={minimum_eigenvalue:.17g}",
                "threshold_less_than": "shape15x15;rank15;sym<1e-12;minEig>0",
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            failures.append(f"{matrix_name}矩阵身份检查失败")

    direction_horizontal = np.zeros(15)
    direction_horizontal[[0, 5, 10]] = 1.0
    direction_ones = np.ones(15)
    ratio_horizontal, cumulative_horizontal = effective_mass_ratios(modes, mass, direction_horizontal)
    ratio_ones, cumulative_ones = effective_mass_ratios(modes, mass, direction_ones)

    energy_zonghe_history, history_declared_rows, energy_zonghe_markers = read_energy_zonghe_history(
        INPUT_DIR / "energy_zonghe.mlx"
    )
    history_visible_count = int(energy_zonghe_history.size)
    history_max_abs = float(np.max(np.abs(energy_zonghe_history - ratio_horizontal[:history_visible_count])))
    history_rounding_threshold = 5.1e-5
    history_first5_cumulative = float(np.sum(energy_zonghe_history[:5]))
    history_passed = (
        history_declared_rows == 15
        and history_visible_count == 10
        and history_max_abs <= history_rounding_threshold
        and abs(history_first5_cumulative - cumulative_horizontal[4]) <= 5 * history_rounding_threshold
        and all(energy_zonghe_markers.values())
    )
    checks.append(
        {
            "check": "energy_zonghe_mlx_history_and_code_markers",
            "actual": f"declared={history_declared_rows};visible={history_visible_count};max_abs={history_max_abs:.17g};first5_sum={history_first5_cumulative:.17g};markers={sum(energy_zonghe_markers.values())}/{len(energy_zonghe_markers)}",
            "threshold_less_than": f"declared15;visible10;rounded_max_abs<={history_rounding_threshold};first5_rounding_match;markers_all_true",
            "result": "PASS" if history_passed else "FAIL",
        }
    )
    if not history_passed:
        failures.append("energy_zonghe.mlx可见历史参与比或代码标记与当前计算不一致")

    history_rows: list[dict[str, object]] = []
    for index in range(history_visible_count):
        history_rows.append(
            {
                "mode": index + 1,
                "energy_zonghe_visible_historical_rounded4": f"{energy_zonghe_history[index]:.4f}",
                "independent_current_full_precision": f"{ratio_horizontal[index]:.17g}",
                "absolute_difference": f"{abs(energy_zonghe_history[index]-ratio_horizontal[index]):.17g}",
                "rounding_level_match": "PASS"
                if abs(energy_zonghe_history[index] - ratio_horizontal[index]) <= history_rounding_threshold
                else "FAIL",
            }
        )
    write_csv(OUTPUT_DIR / "energy_zonghe_visible_historical_participation.csv", history_rows)

    modal_rows: list[dict[str, object]] = []
    for index in range(15):
        modal_rows.append(
            {
                "mode": index + 1,
                "frequency_hz_python": f"{frequency[index]:.17g}",
                "frequency_hz_matlab": f"{matlab_frequency[index]:.17g}",
                "absolute_difference_hz": f"{abs(frequency[index]-matlab_frequency[index]):.17g}",
                "effective_mass_ratio_horizontal": f"{ratio_horizontal[index]:.17g}",
                "cumulative_horizontal": f"{cumulative_horizontal[index]:.17g}",
                "effective_mass_ratio_all_ones": f"{ratio_ones[index]:.17g}",
                "cumulative_all_ones": f"{cumulative_ones[index]:.17g}",
            }
        )
    write_csv(OUTPUT_DIR / "modal_results_python.csv", modal_rows)

    route_specs = [
        ("真实响应代码", 206e9, 785e3 * 1.9, "计算级复现基准"),
        ("rho=785e3分支", 206e9, 785e3, "原工程另一New_Full分支"),
        ("rho=7.85e3分支", 206e9, 7.85e3, "原工程新物理子结构方案分支"),
        ("论文表值最小替换", 200e9, 7850.0, "仅替换论文E和rho；论文缺完整质量/惯性说明"),
    ]
    route_rows: list[dict[str, object]] = []
    for route_name, route_e, route_rho, evidence in route_specs:
        route_mass, route_stiffness = assemble_reference(route_e, route_rho)
        route_frequency, _ = solve_modes(route_mass, route_stiffness)
        for index in range(5):
            route_rows.append(
                {
                    "route": route_name,
                    "route_evidence": evidence,
                    "mode": index + 1,
                    "E_pa": f"{route_e:.17g}",
                    "rho_kg_m3": f"{route_rho:.17g}",
                    "frequency_hz": f"{route_frequency[index]:.17g}",
                    "thesis_frequency_hz": [2.7, 9.1, 18.0, 22.1, 23.6][index],
                    "relative_difference_percent": f"{(route_frequency[index]/[2.7,9.1,18.0,22.1,23.6][index]-1)*100:.17g}",
                }
            )
    write_csv(OUTPUT_DIR / "parameter_route_frequencies_python.csv", route_rows)

    source_map = {
        "PDmonicanshu.m": PROJECT_ROOT / "figure" / "第3章_缩聚对试验精度的影响" / "原始来源副本" / "模型与参数原件" / "PDmonicanshu.m",
        "tes.m": PROJECT_ROOT / "liangyustability-master" / "能量指标" / "tes.m",
        "energy.m": PROJECT_ROOT / "liangyustability-master" / "能量指标" / "energy.m",
        "calc_MPF.m": PROJECT_ROOT / "liangyustability-master" / "新结构稳定" / "绘图" / "calc_MPF.m",
        "modal_analysis.m": PROJECT_ROOT / "liangyustability-master" / "新结构稳定" / "绘图" / "modal_analysis.m",
        "modal_participation_factors.m": PROJECT_ROOT / "liangyustability-master" / "新结构稳定" / "绘图" / "modal_participation_factors.m",
        "modal_energy_ratios_batch.m": PROJECT_ROOT / "liangyustability-master" / "新结构稳定" / "绘图" / "modal_energy_ratios_batch.m",
        "energy_zonghe.mlx": PROJECT_ROOT / "liangyustability-master" / "能量指标" / "energy_zonghe.mlx",
        "PDmonicanshu_energy_branch.m": PROJECT_ROOT / "liangyustability-master" / "能量指标" / "PDmonicanshu.m",
    }
    integrity_rows: list[dict[str, object]] = []
    for name, original in source_map.items():
        copied = INPUT_DIR / name
        original_hash = sha256(original)
        copied_hash = sha256(copied)
        result = "MATCH" if original_hash == copied_hash else "MISMATCH"
        integrity_rows.append(
            {
                "file": name,
                "original_path": str(original.resolve()),
                "copy_path": str(copied.resolve()),
                "original_sha256": original_hash,
                "copy_sha256": copied_hash,
                "result": result,
            }
        )
        if result != "MATCH":
            failures.append(f"输入复制件哈希不一致：{name}")
    write_csv(OUTPUT_DIR / "board16_input_integrity.csv", integrity_rows)

    tes_text = (INPUT_DIR / "tes.m").read_text(encoding="utf-8")
    energy_text = (INPUT_DIR / "energy.m").read_text(encoding="utf-8")
    calc_text = (INPUT_DIR / "calc_MPF.m").read_text(encoding="utf-8")
    modal_analysis_text = (INPUT_DIR / "modal_analysis.m").read_text(encoding="utf-8")
    response_pd_lines = (INPUT_DIR / "PDmonicanshu.m").read_text(encoding="utf-8").splitlines()
    energy_pd_text = (INPUT_DIR / "PDmonicanshu_energy_branch.m").read_text(encoding="utf-8")
    energy_pd_lines = energy_pd_text.splitlines()
    energy_pd_markers = {
        "index3_horizontal": "index3 = [1,6,11];" in energy_pd_text,
        "index4_remaining": "index4 = [2,3,4,5,7,8,9,10,12,13,14,15];" in energy_pd_text,
        "order_index3_index4": "order = [index3,index4];" in energy_pd_text,
        "horizontal_mass_force": "Mf = diag([1,1,1,0,0,0,0,0,0,0,0,0,0,0,0].*Mforce);" in energy_pd_text,
    }
    energy_pd_core_passed = response_pd_lines[:122] == energy_pd_lines[:122] and all(energy_pd_markers.values())
    checks.append(
        {
            "check": "response_and_energy_PD_core_lineage",
            "actual": f"core_1_122_equal={response_pd_lines[:122] == energy_pd_lines[:122]};markers={sum(energy_pd_markers.values())}/{len(energy_pd_markers)}",
            "threshold_less_than": "core_1_122_identical;markers_all_true",
            "result": "PASS" if energy_pd_core_passed else "FAIL",
        }
    )
    if not energy_pd_core_passed:
        failures.append("响应分支与能量分支PDmonicanshu.m核心或重排标记不一致")
    energy_active_direction_line = next(
        (
            line.split("%", 1)[0]
            for line in energy_text.splitlines()
            if re.match(r"^\s*r\s*=", line.split("%", 1)[0])
        ),
        "",
    )
    energy_direction_match = re.search(r"r\s*=\s*\[([^\]]+)\]", energy_active_direction_line)
    energy_direction_count = len(re.findall(r"[-+]?\d+(?:\.\d+)?", energy_direction_match.group(1))) if energy_direction_match else 0
    route_audit = [
        {
            "route": "energy_zonghe.mlx作者历史主路线",
            "direction_or_projection": "先按index3=[1,6,11]重排，再用15维前3项为1的方向向量",
            "formula_identity": "质量归一化后Gamma^2/sum(Gamma^2)",
            "current_result": f"前2阶累计={cumulative_horizontal[1]:.17g};前5阶累计={cumulative_horizontal[4]:.17g};MLX四位小数最大差={history_max_abs:.17g}",
            "evidence_level": "计算级复现",
            "assessment": "作者保存了代码和历史输出；是解释论文前五阶90%以上的最强现存证据",
        },
        {
            "route": "论文图2-5一致的标准有效模态质量",
            "direction_or_projection": "15维；第1/6/11项为1",
            "formula_identity": "(phi^T M r)^2/[(phi^T M phi)(r^T M r)]",
            "current_result": f"前2阶累计={cumulative_horizontal[1]:.17g};前5阶累计={cumulative_horizontal[4]:.17g}",
            "evidence_level": "计算级复现",
            "assessment": "方向与三层水平地震惯性一致",
        },
        {
            "route": "tes.m字面路线",
            "direction_or_projection": "15维全1向量" if "ones(size(M,1), 1)" in tes_text else "未识别",
            "formula_identity": "质量归一化后Gamma^2/(r^T M r)",
            "current_result": f"前2阶累计={cumulative_ones[1]:.17g};前5阶累计={cumulative_ones[4]:.17g}",
            "evidence_level": "计算级复现",
            "assessment": "公式可运行，但把转角也作为同量纲地震方向，与图2-5不一致",
        },
        {
            "route": "energy.m字面路线",
            "direction_or_projection": f"写死{energy_direction_count}维向量",
            "formula_identity": "Gamma^2/sum(Gamma^2)",
            "current_result": "15x15 M乘18维r时真实失败",
            "evidence_level": "待决定",
            "assessment": "属于18自由度能量分支，不能解释15自由度论文主张",
        },
        {
            "route": "calc_MPF.m",
            "direction_or_projection": "主自由度选择矩阵T",
            "formula_identity": "norm(T phi)^2/norm(phi)^2" if "norm(phi_i_reduced)^2 / norm(phi_i)^2" in calc_text else "未识别",
            "current_result": "不是有效模态质量",
            "evidence_level": "历史值",
            "assessment": "欧氏坐标保留比例，未用质量矩阵或地震方向",
        },
        {
            "route": "modal_analysis.m/modal_energy_ratios_batch.m",
            "direction_or_projection": "逐自由度质量加权模态能量",
            "formula_identity": "phi_j*(M phi)_j/(phi^T M phi)",
            "current_result": "脚本实际i=3" if re.search(r"^i\s*=\s*3", modal_analysis_text, re.MULTILINE) else "i未识别",
            "evidence_level": "历史值",
            "assessment": "用于自由度能量分布，不等于结构有效模态质量累计值",
        },
    ]
    write_csv(OUTPUT_DIR / "participation_route_audit.csv", route_audit)

    write_csv(OUTPUT_DIR / "independent_validation.csv", checks)
    summary = {
        "overall": "PASS" if not failures else "FAIL",
        "failures": failures,
        "comparisons": comparisons,
        "first5_frequency_hz": frequency[:5].tolist(),
        "horizontal_cumulative_first2": float(cumulative_horizontal[1]),
        "horizontal_cumulative_first5": float(cumulative_horizontal[4]),
        "all_ones_cumulative_first2": float(cumulative_ones[1]),
        "all_ones_cumulative_first5": float(cumulative_ones[4]),
        "all_modes_horizontal_sum": float(cumulative_horizontal[-1]),
        "all_modes_ones_sum": float(cumulative_ones[-1]),
        "energy_zonghe_declared_rows": history_declared_rows,
        "energy_zonghe_visible_history_count": history_visible_count,
        "energy_zonghe_visible_historical_first5": energy_zonghe_history[:5].tolist(),
        "energy_zonghe_visible_historical_first5_cumulative": history_first5_cumulative,
        "energy_zonghe_history_max_abs_vs_independent": history_max_abs,
        "energy_zonghe_code_markers": energy_zonghe_markers,
    }
    (OUTPUT_DIR / "independent_validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"独立有限元装配：{summary['overall']}")
    print("前五阶频率(Hz)：" + ", ".join(f"{value:.12f}" for value in frequency[:5]))
    print(f"水平影响向量累计有效模态质量：前2阶={cumulative_horizontal[1]:.12f}，前5阶={cumulative_horizontal[4]:.12f}")
    print(f"全1影响向量累计有效模态质量：前2阶={cumulative_ones[1]:.12f}，前5阶={cumulative_ones[4]:.12f}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
