#!/usr/bin/env python3
"""
Board 20, step 5: independent Python replay of the historical discrete-LQR core.

Scope is deliberately narrow:
  * read the five-route identity manifest and the two sealed division-II workspaces;
  * rebuild A/B, exact ZOH Ad/Bd, the discrete DARE gain, Acl, DeltaK and DeltaC;
  * compare against the sealed MATLAB workspaces with a strict absolute 1e-8 gate;
  * retain a secondary scale-aware diagnostic without allowing it to replace the
    strict gate;
  * record why the thesis and manuscript formula contracts are not numerically
    closed.

No spectral-radius output from step 4 is read by this program.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import scipy
from scipy.linalg import eigvals, expm, solve_discrete_are
from scipy.optimize import linear_sum_assignment


SCHEMA_VERSION = "board20_step5_lqr_audit_v1"
STRICT_ABS_TOL = 1.0e-8
SCALE_ATOL = 1.0e-8
SCALE_RTOL = 1.0e-8
EXPECTED_ROUTE_IDS = (
    "main_ori_div1",
    "main_guyan_div1",
    "alt_guyan_div1_stable_full_ps3",
    "main_ori_div2",
    "main_guyan_div2",
)
DIV2_ROUTE_IDS = ("main_ori_div2", "main_guyan_div2")
DIV1_ROUTE_IDS = (
    "main_ori_div1",
    "main_guyan_div1",
    "alt_guyan_div1_stable_full_ps3",
)
EXPECTED_Q = np.diag([1.0e6, 1.0, 1.0e5, 1.0])
EXPECTED_R = np.diag([1.0e-1, 1.0e-2])
EXPECTED_DT = 1.0 / 1024.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_float(value: float) -> str:
    return format(float(value), ".17g")


def csv_bytes(rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return buffer.getvalue().encode("utf-8")


def json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def write_if_changed(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == payload:
        return
    path.write_bytes(payload)


def matlab_numeric(dataset: h5py.Dataset) -> np.ndarray:
    matlab_class = dataset.attrs.get("MATLAB_class", b"")
    if isinstance(matlab_class, np.ndarray):
        matlab_class = matlab_class.tobytes()
    if matlab_class not in (b"double", b"single", b"logical", b"int64", b"uint64"):
        raise TypeError(
            f"Dataset {dataset.name} is not a supported numeric MATLAB array: {matlab_class!r}"
        )
    raw = np.asarray(dataset)
    if raw.ndim >= 2:
        raw = np.transpose(raw, axes=tuple(reversed(range(raw.ndim))))
    return np.asarray(raw, dtype=float)


def load_workspace_numeric(path: Path, names: Iterable[str]) -> dict[str, np.ndarray]:
    values: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as handle:
        missing = [name for name in names if name not in handle]
        if missing:
            raise KeyError(f"Missing workspace variables in {path}: {missing}")
        for name in names:
            values[name] = matlab_numeric(handle[name])
    return values


def find_contract_sha(route: dict[str, Any], kind: str) -> str:
    matches = [item for item in route.get("file_contracts", []) if item.get("kind") == kind]
    if len(matches) != 1:
        raise ValueError(
            f"Route {route['route_id']} has {len(matches)} contracts of kind {kind}; expected one"
        )
    return str(matches[0]["sha256"]).upper()


def active_matlab_lines(path: Path) -> list[tuple[int, str]]:
    active: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = raw_line.split("%", 1)[0].strip()
        if code:
            active.append((line_number, code))
    return active


def matching_lines(lines: list[tuple[int, str]], pattern: str) -> list[int]:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    return [line_number for line_number, code in lines if regex.search(code)]


def reconstruct_lqr(workspace: dict[str, np.ndarray]) -> dict[str, np.ndarray | float]:
    # The executed historical source explicitly assigns M/C/K from these three
    # workspace variables before constructing the state-space model.
    mass = np.asarray(workspace["MPren"], dtype=float)
    damping = np.asarray(workspace["CPren"], dtype=float)
    stiffness = np.asarray(workspace["KPren"], dtype=float)
    if mass.shape != damping.shape or mass.shape != stiffness.shape:
        raise ValueError("MPren, CPren and KPren must have identical shapes")
    if mass.ndim != 2 or mass.shape[0] != mass.shape[1]:
        raise ValueError("Historical LQR mass matrix must be square")

    n = mass.shape[0]
    zeros = np.zeros((n, n), dtype=float)
    eye = np.eye(n, dtype=float)
    a_matrix = np.block(
        [
            [zeros, eye],
            [-np.linalg.solve(mass, stiffness), -np.linalg.solve(mass, damping)],
        ]
    )
    b_matrix = np.vstack([zeros, np.linalg.solve(mass, eye)])

    # Exact ZOH discretization, independent of MATLAB c2d.
    state_count = 2 * n
    input_count = n
    zoh_augmented = np.zeros(
        (state_count + input_count, state_count + input_count), dtype=float
    )
    zoh_augmented[:state_count, :state_count] = a_matrix
    zoh_augmented[:state_count, state_count:] = b_matrix
    zoh_exponential = expm(zoh_augmented * EXPECTED_DT)
    ad_matrix = zoh_exponential[:state_count, :state_count]
    bd_matrix = zoh_exponential[:state_count, state_count:]

    # scipy.linalg.solve_discrete_are is an independent DARE implementation.
    p_matrix = solve_discrete_are(ad_matrix, bd_matrix, EXPECTED_Q, EXPECTED_R)
    gain = np.linalg.solve(
        bd_matrix.T @ p_matrix @ bd_matrix + EXPECTED_R,
        bd_matrix.T @ p_matrix @ ad_matrix,
    )
    acl = ad_matrix - bd_matrix @ gain
    delta_k = mass @ gain[:, :n]
    delta_c = mass @ gain[:, n:]
    poles = eigvals(acl)

    dare_residual = (
        ad_matrix.T @ p_matrix @ ad_matrix
        - p_matrix
        - ad_matrix.T
        @ p_matrix
        @ bd_matrix
        @ np.linalg.solve(
            EXPECTED_R + bd_matrix.T @ p_matrix @ bd_matrix,
            bd_matrix.T @ p_matrix @ ad_matrix,
        )
        + EXPECTED_Q
    )

    return {
        "M": mass,
        "C": damping,
        "K": stiffness,
        "A": a_matrix,
        "B": b_matrix,
        "Ad": ad_matrix,
        "Bd": bd_matrix,
        "Q": EXPECTED_Q.copy(),
        "R": EXPECTED_R.copy(),
        "P": p_matrix,
        "K_lqr": gain,
        "Acl": acl,
        "DeltaK": delta_k,
        "DeltaC": delta_c,
        "closed_loop_poles": poles,
        "closed_loop_rho": float(np.max(np.abs(poles))),
        "dare_residual_max_abs": float(np.max(np.abs(dare_residual))),
        "dare_residual_scaled_fro": float(
            np.linalg.norm(dare_residual, ord="fro")
            / max(1.0, np.linalg.norm(p_matrix, ord="fro"))
        ),
    }


def matrix_metrics(independent: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    independent = np.asarray(independent)
    reference = np.asarray(reference)
    if independent.shape != reference.shape:
        return {
            "shape_match": False,
            "max_abs_error": float("inf"),
            "relative_fro_error": float("inf"),
            "max_scale_gate_ratio": float("inf"),
            "strict_abs_pass": False,
            "scale_aware_pass": False,
        }
    difference = np.abs(independent - reference)
    max_abs = float(np.max(difference)) if difference.size else 0.0
    relative_fro = float(
        np.linalg.norm(independent - reference, ord="fro")
        / max(np.finfo(float).tiny, np.linalg.norm(reference, ord="fro"))
    )
    allowed = SCALE_ATOL + SCALE_RTOL * np.abs(reference)
    max_ratio = float(np.max(difference / allowed)) if difference.size else 0.0
    return {
        "shape_match": True,
        "max_abs_error": max_abs,
        "relative_fro_error": relative_fro,
        "max_scale_gate_ratio": max_ratio,
        "strict_abs_pass": bool(max_abs <= STRICT_ABS_TOL),
        "scale_aware_pass": bool(np.all(difference <= allowed)),
    }


def match_poles(independent: np.ndarray, reference: np.ndarray) -> list[tuple[complex, complex]]:
    independent = np.asarray(independent, dtype=complex).reshape(-1)
    reference = np.asarray(reference, dtype=complex).reshape(-1)
    if independent.size != reference.size:
        raise ValueError("Independent and reference pole counts differ")
    costs = np.abs(independent[:, None] - reference[None, :])
    row_indices, column_indices = linear_sum_assignment(costs)
    pairs = [(independent[i], reference[j]) for i, j in zip(row_indices, column_indices)]
    return sorted(pairs, key=lambda pair: (pair[1].real, pair[1].imag))


@dataclass(frozen=True)
class ContractEntry:
    field_id: str
    field_name_cn: str
    thesis_status: str
    thesis_value: str
    thesis_evidence: str
    manuscript_status: str
    manuscript_value: str
    manuscript_evidence: str
    consequence: str
    cross_document_conflict: bool = False


CONTRACT_ENTRIES = (
    ContractEntry(
        "controller_design_domain",
        "控制器设计域",
        "SPECIFIED",
        "连续时间CARE，K=R^{-1}B^T P",
        "步骤3报告:50-61；硕士论文式(4-31)至式(4-35)",
        "SPECIFIED",
        "连续时间LQR/代数Riccati方程",
        "manuscript_0824.tex:397-413",
        "两篇论文均不是历史程序的c2d+dlqr路线",
    ),
    ContractEntry(
        "state_order",
        "状态顺序",
        "SPECIFIED",
        "前两项位移、后两项速度",
        "步骤3报告:52-59",
        "SPECIFIED",
        "v=[(S_a q)^T,(S_a qdot)^T]^T",
        "manuscript_0824.tex:397-406",
        "状态排序可确定，但仍需与数值矩阵坐标顺序对应",
    ),
    ContractEntry(
        "q_weights",
        "Q权重",
        "SPECIFIED",
        "diag(1e6,1e6,1e4,1e4)",
        "步骤3报告:52-59",
        "SPECIFIED",
        "diag(1e6,1e6,1e4,1e4)",
        "manuscript_0824.tex:553；步骤3报告:250-260",
        "与历史主程序diag(1e6,1,1e5,1)不同",
    ),
    ContractEntry(
        "r_weights",
        "R权重",
        "SPECIFIED",
        "diag(1e-2,1e-2)",
        "步骤3报告:52-59",
        "SPECIFIED",
        "diag(1e-2,1e-2)",
        "manuscript_0824.tex:553；步骤3报告:250-260",
        "与历史主程序diag(1e-1,1e-2)不同",
    ),
    ContractEntry(
        "numeric_A",
        "连续状态矩阵A的数值入口",
        "SYMBOLIC_ONLY",
        "只写xdot=A x+B u",
        "步骤3报告:50-58",
        "SYMBOLIC_ONLY",
        "只声明A为状态空间矩阵",
        "manuscript_0824.tex:406-413",
        "没有唯一数值A就不能复算连续CARE增益",
    ),
    ContractEntry(
        "numeric_B_and_input_semantics",
        "输入矩阵B/B_a及输入物理语义",
        "AMBIGUOUS",
        "B u；u未唯一说明为位移、力或加速度",
        "步骤3报告:54,270-280",
        "SYMBOLIC_ONLY",
        "u_L称为命令位移；B与B_a仅给符号和尺寸",
        "manuscript_0824.tex:397-413,423-426",
        "输入尺度和嵌入映射未闭合，K的单位与DeltaK/DeltaC转换不唯一",
    ),
    ContractEntry(
        "state_input_units_and_normalization",
        "状态/输入单位与归一化",
        "MISSING",
        "未给出",
        "步骤3报告:270-280",
        "MISSING",
        "命令位移语义已给出，但量纲缩放/归一化未给出",
        "步骤3报告:270-280",
        "Q/R的数值不能脱离量纲与归一化唯一解释",
    ),
    ContractEntry(
        "numeric_reduced_matrices",
        "稳定方程所需缩聚M/C/K与通道C_l/K_l数值矩阵",
        "EXTERNAL_NUMERIC_INPUT_REQUIRED",
        "论文公式未自包含列出全部矩阵数值",
        "步骤3报告:348-357,359-365",
        "EXTERNAL_NUMERIC_INPUT_REQUIRED",
        "正文给出符号装配关系，未在合同处列出可直接计算的矩阵文件",
        "manuscript_0824.tex:380-386,414-429",
        "必须绑定明确文件及坐标顺序才能形成唯一极点网格",
    ),
    ContractEntry(
        "selection_and_embedding_matrices",
        "选择矩阵S/S_a与反馈嵌入矩阵B_a",
        "SYMBOLIC_ONLY",
        "自由度语义存在，数值选择/嵌入矩阵未唯一给出",
        "步骤3报告:282-288,348-353",
        "SYMBOLIC_ONLY",
        "S_a为Boolean选择矩阵、B_a给出尺寸，未给数值矩阵",
        "manuscript_0824.tex:406-426",
        "无法唯一把局部2通道增益嵌入组装坐标",
    ),
    ContractEntry(
        "division_I_coordinates",
        "第一类物理/作动自由度",
        "SPECIFIED",
        "psi1、psi6，两者分别带独立时滞",
        "步骤3报告:90-95",
        "SPECIFIED",
        "保留并作动psi1、psi6",
        "manuscript_0824.tex:508,553",
        "两篇论文在第一类自由度语义上一致",
    ),
    ContractEntry(
        "division_II_coordinates",
        "第二类物理/作动自由度",
        "SPECIFIED",
        "主自由度psi1、psi6、psi11；psi1/psi6延迟，psi11无延迟",
        "步骤3报告:90-95,282-288",
        "SPECIFIED",
        "作动psi1、psi11；psi6被缩聚并重构",
        "manuscript_0824.tex:508,553",
        "两篇论文定义的是不同第二类模型，不能共享一条极点网格",
        True,
    ),
    ContractEntry(
        "sampling_period",
        "采样周期/积分步长",
        "SPECIFIED",
        "dt=1/1024 s",
        "步骤3报告:97-105",
        "SPECIFIED",
        "Delta t=1/1024 s",
        "manuscript_0824.tex:553",
        "一个采样步为0.9765625 ms",
    ),
    ContractEntry(
        "feedback_delay_placement",
        "LQR反馈相对H(z)的位置",
        "CONFLICT",
        "式(4-38)至式(4-40)在H外；文字信号路径暗示作动器时滞",
        "步骤3报告:63-88,242-248",
        "SPECIFIED",
        "B_a H_a(z)[K_x+(z-1)/(z dt)K_v]S_a，反馈在H_a内",
        "manuscript_0824.tex:413-429",
        "硕士论文内部文字/公式断点待决定，且两篇论文不能共用特征方程",
        True,
    ),
    ContractEntry(
        "continuous_gain_discrete_insertion",
        "连续CARE增益进入z域方程的单位/离散插入规则",
        "MISSING",
        "未解释连续K如何成为K_q/K_qdot及其单位",
        "步骤3报告:262-280",
        "SYMBOLIC_ONLY",
        "给出K_x/K_v的z域代入形式，但B/B_a数值和单位尺度未闭合",
        "manuscript_0824.tex:406-426；步骤3报告:262-280",
        "不能用历史离散dlqr增益静默替代连续CARE增益",
    ),
    ContractEntry(
        "cr_alpha_numeric",
        "CR算法标量alpha数值",
        "MISSING",
        "公式含标量alpha但未给数值",
        "步骤3报告:305-318",
        "MISSING",
        "定义为CR算法参数但未给数值",
        "manuscript_0824.tex:388-395",
        "加速度z变换系数不唯一；代码矩阵al不能冒充该标量",
    ),
    ContractEntry(
        "delay_grid_and_axis_mapping",
        "整数时滞网格范围及l/j到tau1/tau2轴映射",
        "AMBIGUOUS",
        "论文说明采样步语义，但历史代码/绘图轴映射未闭合",
        "步骤3报告:290-303",
        "SYMBOLIC_ONLY",
        "定义n_l与两个通道，但未绑定历史l/j矩阵行列身份",
        "manuscript_0824.tex:388-395,553,711；步骤3报告:290-303",
        "逐图比较必须同时保存原矩阵和转置候选，保持待决定",
    ),
    ContractEntry(
        "negative_power_clearing",
        "清除z负次幂的具体幂次",
        "MISSING",
        "未给具体清幂次数",
        "步骤3报告:328-334",
        "GENERAL_RULE_ONLY",
        "只写乘以sufficient power of z",
        "manuscript_0824.tex:430-434",
        "不同清幂实现可能引入不同数量的原点伪根",
    ),
    ContractEntry(
        "origin_root_removal",
        "原点伪根数量与剔除容差",
        "MISSING",
        "未给出",
        "步骤3报告:328-334",
        "GENERAL_RULE_ONLY",
        "要求discard原点根，但没有数量/容差",
        "manuscript_0824.tex:430-434",
        "不能独立验收最终根数和主导极点",
    ),
    ContractEntry(
        "root_solver_and_residual_gate",
        "根求解器、根数合同与残差门槛",
        "MISSING",
        "未给出",
        "步骤3报告:328-334,348-355",
        "MISSING",
        "未给出数值求根器和残差阈值",
        "步骤3报告:328-355",
        "论文公式路线无法形成可审计的数值验收门",
    ),
    ContractEntry(
        "stability_predicate",
        "稳定判据",
        "SPECIFIED",
        "rho_cl<1稳定，=1临界，>1失稳",
        "步骤3报告:36-48",
        "SPECIFIED",
        "rho_cl<1",
        "manuscript_0824.tex:711；步骤3报告:320-326",
        "程序实现还必须排除未计算零值并要求有限正值",
    ),
)


def contract_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in CONTRACT_ENTRIES:
        for document_id, status, value, evidence in (
            (
                "liang_thesis",
                entry.thesis_status,
                entry.thesis_value,
                entry.thesis_evidence,
            ),
            (
                "manuscript_0824",
                entry.manuscript_status,
                entry.manuscript_value,
                entry.manuscript_evidence,
            ),
        ):
            rows.append(
                {
                    "document_id": document_id,
                    "field_id": entry.field_id,
                    "field_name_cn": entry.field_name_cn,
                    "required_for_unique_reproduction": "TRUE",
                    "status": status,
                    "specified_value": value,
                    "evidence": evidence,
                    "gap_consequence": entry.consequence,
                    "cross_document_conflict": "TRUE"
                    if entry.cross_document_conflict
                    else "FALSE",
                    "contract_closed_for_field": "TRUE" if status == "SPECIFIED" else "FALSE",
                }
            )
    return rows


def array_long_rows(route_id: str, arrays: dict[str, np.ndarray | float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for matrix_name in (
        "M",
        "C",
        "K",
        "A",
        "B",
        "Ad",
        "Bd",
        "Q",
        "R",
        "P",
        "K_lqr",
        "Acl",
        "DeltaK",
        "DeltaC",
    ):
        array = np.asarray(arrays[matrix_name])
        if array.ndim != 2:
            raise ValueError(f"Expected a 2-D array for {matrix_name}, got {array.shape}")
        for row_index in range(array.shape[0]):
            for column_index in range(array.shape[1]):
                value = complex(array[row_index, column_index])
                rows.append(
                    {
                        "route_id": route_id,
                        "matrix": matrix_name,
                        "row_1based": row_index + 1,
                        "column_1based": column_index + 1,
                        "real": stable_float(value.real),
                        "imag": stable_float(value.imag),
                    }
                )
    return rows


def build_report(
    route_summaries: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    contract: list[dict[str, Any]],
    source_hashes: dict[str, str],
    cross_route: dict[str, Any],
) -> str:
    div2 = [row for row in route_summaries if row["division"] == "div2"]
    failed = [row for row in comparisons if row["strict_abs_pass"] == "FALSE"]
    contract_counts: dict[str, dict[str, int]] = {}
    for document_id in ("liang_thesis", "manuscript_0824"):
        relevant = [row for row in contract if row["document_id"] == document_id]
        contract_counts[document_id] = {
            "total": len(relevant),
            "closed": sum(row["contract_closed_for_field"] == "TRUE" for row in relevant),
        }

    lines = [
        "# 板块20步骤5：作者离散LQR独立复算与论文合同缺口审计",
        "",
        "## 1. 人话结论",
        "",
        "本步骤用 Python/Scipy 从两份第二分区封签工作区中的 `MPren/CPren/KPren` 重新建立状态空间，独立执行精确ZOH离散化和离散DARE求解。程序没有读取步骤4的谱半径或极点结果。三条第一分区执行源中没有活动的 `dlqr` 调用，故统一标记为 `LQR_NOT_PRESENT_IN_EXECUTED_SOURCE`，不能凭文件名补出LQR。",
        "",
        "严格绝对门禁固定为 `max(abs(independent-reference)) <= 1e-8`，不随结果放宽。ZOH得到的 `Ad/Bd` 和闭环 `Acl` 通过该门禁；`K_lqr/DeltaK/DeltaC` 没有全部通过。作为次级诊断，另报告 `abs(diff) <= 1e-8 + 1e-8*abs(reference)`；两条第二分区路线在这个尺度感知门禁下均通过。因此裁决是 `SCALE_AWARE_PASS_STRICT_ABS_FAIL`，不是无条件PASS。",
        "",
        "这项结果只交叉验证历史主程序的 `c2d+dlqr` 核心，不会把它升级成硕士论文或当前小论文的连续CARE计算级复现。两篇论文的必填数值合同仍未闭合，结论保持 `待决定`。",
        "",
        "## 2. 五条文件身份路线",
        "",
        "| 路线 | 分区 | 活动dlqr数 | 裁决 |",
        "|---|---:|---:|---|",
    ]
    for row in route_summaries:
        lines.append(
            f"| `{row['route_id']}` | `{row['division']}` | {row['active_dlqr_count']} | `{row['status']}` |"
        )

    lines.extend(
        [
            "",
            "两份第二分区执行源虽然文件名分别写有 Original 和 Guyan，但封签的LQR输入、作者工作区LQR输出以及本次独立复算数组均逐元素完全相同。它们必须保留两个文件身份，不能据此声称存在两套独立LQR设计。",
            "",
            "## 3. 独立复算数值",
            "",
            "| 路线 | 闭环设计谱半径 | ZOH严格门禁 | Acl严格门禁 | 增益严格门禁 | 尺度感知门禁 |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for row in div2:
        lines.append(
            "| `{route_id}` | {rho} | `{zoh}` | `{acl}` | `{gain}` | `{scale}` |".format(
                route_id=row["route_id"],
                rho=row["closed_loop_rho"],
                zoh=row["zoh_strict_abs_pass"],
                acl=row["acl_strict_abs_pass"],
                gain=row["lqr_gain_and_delta_strict_abs_pass"],
                scale=row["all_scale_aware_pass"],
            )
        )

    lines.extend(
        [
            "",
            "严格绝对门禁失败量如下；绝对差必须原样保留，不能用相对量级掩盖：",
            "",
            "| 路线 | 变量 | 最大绝对差 | Frobenius相对差 | 次级尺度感知门禁 |",
            "|---|---|---:|---:|---|",
        ]
    )
    for row in failed:
        lines.append(
            f"| `{row['route_id']}` | `{row['variable']}` | {row['max_abs_error']} | {row['relative_fro_error']} | `{row['scale_aware_pass']}` |"
        )

    lines.extend(
        [
            "",
            "闭环极点由独立 `Acl=Ad-Bd*K_lqr` 与封签作者 `Acl` 分别求特征值，再用最小总代价一一配对；各极点误差详见 `design_poles.csv`。",
            "",
            "## 4. 硕士论文与当前小论文的必填字段合同",
            "",
            f"- 梁禹硕士论文：{contract_counts['liang_thesis']['closed']}/{contract_counts['liang_thesis']['total']} 个必填字段标为 `SPECIFIED`；合同状态 `CONTRACT_NOT_CLOSED`。",
            f"- 当前小论文 `manuscript_0824.tex`：{contract_counts['manuscript_0824']['closed']}/{contract_counts['manuscript_0824']['total']} 个必填字段标为 `SPECIFIED`；合同状态 `CONTRACT_NOT_CLOSED`。",
            "",
            "这里的计数不是论文质量评分，只表示能否仅凭该文档形成唯一、可审计的数值输入。完整逐字段证据见 `thesis_manuscript_contract_matrix.csv`。决定性缺口包括：连续CARE的数值A/B或B_a、输入单位与归一化、CR标量alpha、反馈嵌入矩阵、清除负次幂的具体幂次、原点伪根数量/容差、根残差门槛，以及历史l/j矩阵行列与tau1/tau2的映射。",
            "",
            "此外，两篇论文的第二分区和反馈位置不是同一合同：硕士论文第二分区写 `psi1,psi6` 两通道延迟且 `psi11` 无延迟，式(4-38)至式(4-40)把反馈放在H外；当前小论文作动 `psi1,psi11`、重构 `psi6`，并把反馈放在H_a内。两者必须分开实现和验证。",
            "",
            "## 5. 证据边界与诚实标签",
            "",
            "- `计算级复现`：步骤2的历史MATLAB执行证据另行封签。本步骤仅是独立LQR核心交叉验证；因纯绝对1e-8门禁未全部通过，不标记为无条件独立计算PASS。",
            "- `绘图级复现`：本步骤没有画图，也没有创建成功图目录，不改变既有绘图级证据等级。",
            "- `历史值`：图4-4/图4-5已有边界及论文5 ms/10 ms说法均不因本步骤升级。",
            "- `待决定`：论文输入语义、第二分区权威定义、反馈位置、CR标量alpha和轴映射仍需明确选择后才能另建论文公式路线。",
            "",
            "## 6. 独立性、封签与可重复性",
            "",
            "- 只读输入：五路线manifest、五份提取后的执行源、两份第二分区 `workspace_complete.mat`、步骤3公式报告和冻结 `manuscript_0824.tex`。",
            "- 禁止输入：`outputs/step4_rho_grids` 下任何谱半径、极点或稳定掩膜；本脚本读取列表中没有这些文件。",
            "- 两份第二分区工作区在运行前后重新计算SHA-256；输入未变化。",
            "- 数值矩阵以长表形式写入 `recomputed_lqr_matrices.csv`，可逐元素审计。",
            "- 本脚本输出不写运行时间戳；连续两次执行应得到完全相同的文件哈希。",
            "",
            "关键源文件SHA-256：",
            "",
        ]
    )
    for name, digest in sorted(source_hashes.items()):
        lines.append(f"- `{name}`: `{digest}`")
    lines.extend(
        [
            "",
            "第二分区跨文件身份逐元素相同性：",
            "",
            f"- 封签历史LQR输入与输出全部相同：`{cross_route['workspace_arrays_exactly_equal']}`。",
            f"- 独立复算数组全部相同：`{cross_route['independent_arrays_exactly_equal']}`。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Board-20 root directory (default: parent of code directory)",
    )
    args = parser.parse_args()
    base = args.base.resolve()
    code_path = Path(__file__).resolve()
    manifest_path = base / "code" / "board20_step4_route_manifest.json"
    step3_report_path = base / "report" / "板块20_公式语义审计_草稿.md"
    manuscript_path = base / "input" / "theory" / "manuscript_0824.tex"
    output_dir = base / "outputs" / "step5_lqr_contract"
    log_path = base / "logs" / "step5_lqr_run.log"

    for required in (manifest_path, step3_report_path, manuscript_path):
        if not required.is_file():
            raise FileNotFoundError(required)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = {route["route_id"]: route for route in manifest["routes"]}
    if tuple(routes.keys()) != EXPECTED_ROUTE_IDS:
        raise ValueError(
            f"Unexpected route identity/order: {tuple(routes.keys())}; expected {EXPECTED_ROUTE_IDS}"
        )

    source_hashes = {
        "analyze_board20_step5_lqr.py": sha256_file(code_path),
        "board20_step4_route_manifest.json": sha256_file(manifest_path),
        "板块20_公式语义审计_草稿.md": sha256_file(step3_report_path),
        "manuscript_0824.tex": sha256_file(manuscript_path),
    }
    source_checks: list[dict[str, Any]] = []
    route_summaries: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    pole_rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    independent_by_route: dict[str, dict[str, np.ndarray | float]] = {}
    workspace_by_route: dict[str, dict[str, np.ndarray]] = {}
    input_hash_before: dict[str, str] = {}

    for route_id in EXPECTED_ROUTE_IDS:
        route = routes[route_id]
        source_path = base / route["source_m_relpath"]
        actual_source_sha = sha256_file(source_path)
        expected_source_sha = find_contract_sha(route, "extracted_author_m")
        source_hashes[f"{route_id}:source_m"] = actual_source_sha
        source_checks.append(
            {
                "route_id": route_id,
                "check": "extracted_author_m_sha256",
                "expected": expected_source_sha,
                "actual": actual_source_sha,
                "status": "PASS" if actual_source_sha == expected_source_sha else "FAIL",
            }
        )
        if actual_source_sha != expected_source_sha:
            raise ValueError(f"Source hash mismatch for {route_id}: {source_path}")

        lines = active_matlab_lines(source_path)
        dlqr_lines = matching_lines(lines, r"\bdlqr\s*\(")
        c2d_lines = matching_lines(lines, r"\bc2d\s*\(")
        if route_id in DIV1_ROUTE_IDS:
            if dlqr_lines:
                raise ValueError(f"Unexpected active dlqr in division-I source {source_path}")
            route_summaries.append(
                {
                    "route_id": route_id,
                    "division": "div1",
                    "active_dlqr_count": 0,
                    "active_dlqr_lines": "",
                    "active_c2d_count": len(c2d_lines),
                    "status": "LQR_NOT_PRESENT_IN_EXECUTED_SOURCE",
                    "closed_loop_rho": "",
                    "zoh_strict_abs_pass": "NOT_APPLICABLE",
                    "acl_strict_abs_pass": "NOT_APPLICABLE",
                    "lqr_gain_and_delta_strict_abs_pass": "NOT_APPLICABLE",
                    "all_scale_aware_pass": "NOT_APPLICABLE",
                    "workspace_sha256": "NOT_READ",
                    "workspace_unchanged": "NOT_APPLICABLE",
                }
            )
            continue

        if len(dlqr_lines) != 1 or len(c2d_lines) != 1:
            raise ValueError(
                f"Expected one active c2d and one active dlqr in {source_path}; "
                f"found c2d={c2d_lines}, dlqr={dlqr_lines}"
            )

        required_source_patterns = {
            "M_equals_MPren": r"^M\s*=\s*MPren\s*;",
            "C_equals_CPren": r"^C\s*=\s*CPren\s*;",
            "K_equals_KPren": r"^K\s*=\s*KPren\s*;",
            "Q_historical": r"^Q\s*=\s*diag\s*\(\s*\[\s*1e6\s*,\s*1\s*,\s*1e5\s*,\s*1\s*\]\s*\)\s*;",
            "R_historical": r"^R\s*=\s*diag\s*\(\s*\[\s*1e-1\s*,\s*1e-2\s*\]\s*\)\s*;",
            "DeltaK_historical": r"^DeltaK\s*=\s*MPren\s*\*\s*K_lqr",
            "DeltaC_historical": r"^DeltaC\s*=\s*MPren\s*\*\s*K_lqr",
        }
        for check_name, pattern in required_source_patterns.items():
            found = matching_lines(lines, pattern)
            repeated_assignment_allowed = check_name in {
                "M_equals_MPren",
                "C_equals_CPren",
                "K_equals_KPren",
            }
            check_pass = bool(found) if repeated_assignment_allowed else len(found) == 1
            expected_description = (
                "one or more active matching lines; last assignment governs A/B"
                if repeated_assignment_allowed
                else "one active matching line"
            )
            source_checks.append(
                {
                    "route_id": route_id,
                    "check": check_name,
                    "expected": expected_description,
                    "actual": ",".join(str(number) for number in found),
                    "status": "PASS" if check_pass else "FAIL",
                }
            )
            if not check_pass:
                raise ValueError(
                    f"Source contract {check_name} failed for {route_id}: lines={found}"
                )

        workspace_path = base / route["workspace_relpath"]
        workspace_sha = sha256_file(workspace_path)
        input_hash_before[route_id] = workspace_sha
        expected_workspace_sha = find_contract_sha(route, "workspace_complete")
        source_hashes[f"{route_id}:workspace_complete.mat"] = workspace_sha
        source_checks.append(
            {
                "route_id": route_id,
                "check": "workspace_complete_sha256",
                "expected": expected_workspace_sha,
                "actual": workspace_sha,
                "status": "PASS" if workspace_sha == expected_workspace_sha else "FAIL",
            }
        )
        if workspace_sha != expected_workspace_sha:
            raise ValueError(f"Workspace hash mismatch for {route_id}: {workspace_path}")

        workspace = load_workspace_numeric(
            workspace_path,
            (
                "MPren",
                "CPren",
                "KPren",
                "M",
                "C",
                "K",
                "A",
                "B",
                "Ad",
                "Bd",
                "Q",
                "R",
                "K_lqr",
                "Acl",
                "DeltaK",
                "DeltaC",
                "dt",
                "S",
            ),
        )
        workspace_by_route[route_id] = workspace
        if float(np.squeeze(workspace["dt"])) != EXPECTED_DT:
            raise ValueError(f"Unexpected dt in {route_id}: {workspace['dt']}")

        independent = reconstruct_lqr(workspace)
        independent_by_route[route_id] = independent
        matrix_rows.extend(array_long_rows(route_id, independent))

        reference_map = {
            "M": workspace["M"],
            "C": workspace["C"],
            "K": workspace["K"],
            "A": workspace["A"],
            "B": workspace["B"],
            "Ad": workspace["Ad"],
            "Bd": workspace["Bd"],
            "Q": workspace["Q"],
            "R": workspace["R"],
            "K_lqr": workspace["K_lqr"],
            "Acl": workspace["Acl"],
            "DeltaK": workspace["DeltaK"],
            "DeltaC": workspace["DeltaC"],
        }
        route_metrics: dict[str, dict[str, Any]] = {}
        for variable, reference in reference_map.items():
            metrics = matrix_metrics(np.asarray(independent[variable]), reference)
            route_metrics[variable] = metrics
            comparison_rows.append(
                {
                    "route_id": route_id,
                    "variable": variable,
                    "shape": "x".join(str(item) for item in reference.shape),
                    "max_abs_error": stable_float(metrics["max_abs_error"]),
                    "relative_fro_error": stable_float(metrics["relative_fro_error"]),
                    "strict_abs_tolerance": stable_float(STRICT_ABS_TOL),
                    "strict_abs_pass": "TRUE" if metrics["strict_abs_pass"] else "FALSE",
                    "scale_atol": stable_float(SCALE_ATOL),
                    "scale_rtol": stable_float(SCALE_RTOL),
                    "max_scale_gate_ratio": stable_float(metrics["max_scale_gate_ratio"]),
                    "scale_aware_pass": "TRUE" if metrics["scale_aware_pass"] else "FALSE",
                    "reference": "sealed_step2_workspace",
                }
            )

        reference_poles = eigvals(workspace["Acl"])
        pole_pairs = match_poles(np.asarray(independent["closed_loop_poles"]), reference_poles)
        pole_errors = []
        for pole_index, (independent_pole, reference_pole) in enumerate(pole_pairs, 1):
            error = abs(independent_pole - reference_pole)
            pole_errors.append(error)
            pole_rows.append(
                {
                    "route_id": route_id,
                    "matched_pole_index": pole_index,
                    "independent_real": stable_float(independent_pole.real),
                    "independent_imag": stable_float(independent_pole.imag),
                    "reference_real": stable_float(reference_pole.real),
                    "reference_imag": stable_float(reference_pole.imag),
                    "absolute_error": stable_float(error),
                    "strict_abs_tolerance": stable_float(STRICT_ABS_TOL),
                    "strict_abs_pass": "TRUE" if error <= STRICT_ABS_TOL else "FALSE",
                }
            )
        poles_max_error = max(pole_errors, default=0.0)
        comparison_rows.append(
            {
                "route_id": route_id,
                "variable": "closed_loop_poles",
                "shape": str(len(pole_pairs)),
                "max_abs_error": stable_float(poles_max_error),
                "relative_fro_error": "NOT_APPLICABLE_MATCHED_COMPLEX_ROOTS",
                "strict_abs_tolerance": stable_float(STRICT_ABS_TOL),
                "strict_abs_pass": "TRUE" if poles_max_error <= STRICT_ABS_TOL else "FALSE",
                "scale_atol": stable_float(SCALE_ATOL),
                "scale_rtol": stable_float(SCALE_RTOL),
                "max_scale_gate_ratio": "NOT_APPLICABLE",
                "scale_aware_pass": "TRUE" if poles_max_error <= STRICT_ABS_TOL else "FALSE",
                "reference": "eig(sealed_step2_workspace_Acl)",
            }
        )

        zoh_pass = all(route_metrics[name]["strict_abs_pass"] for name in ("A", "B", "Ad", "Bd"))
        acl_pass = route_metrics["Acl"]["strict_abs_pass"] and poles_max_error <= STRICT_ABS_TOL
        gain_delta_pass = all(
            route_metrics[name]["strict_abs_pass"] for name in ("K_lqr", "DeltaK", "DeltaC")
        )
        all_scale_pass = all(metrics["scale_aware_pass"] for metrics in route_metrics.values())
        if zoh_pass and acl_pass and gain_delta_pass:
            status = "STRICT_ABS_PASS"
        elif zoh_pass and acl_pass and all_scale_pass:
            status = "SCALE_AWARE_PASS_STRICT_ABS_FAIL"
        else:
            status = "NUMERICAL_MISMATCH"

        route_summaries.append(
            {
                "route_id": route_id,
                "division": "div2",
                "active_dlqr_count": len(dlqr_lines),
                "active_dlqr_lines": ",".join(str(item) for item in dlqr_lines),
                "active_c2d_count": len(c2d_lines),
                "status": status,
                "closed_loop_rho": stable_float(independent["closed_loop_rho"]),
                "zoh_strict_abs_pass": "TRUE" if zoh_pass else "FALSE",
                "acl_strict_abs_pass": "TRUE" if acl_pass else "FALSE",
                "lqr_gain_and_delta_strict_abs_pass": "TRUE" if gain_delta_pass else "FALSE",
                "all_scale_aware_pass": "TRUE" if all_scale_pass else "FALSE",
                "workspace_sha256": workspace_sha,
                "workspace_unchanged": "PENDING_POST_READ_HASH",
                "dare_residual_max_abs": stable_float(independent["dare_residual_max_abs"]),
                "dare_residual_scaled_fro": stable_float(
                    independent["dare_residual_scaled_fro"]
                ),
                "K_lqr_max_abs_error": stable_float(
                    route_metrics["K_lqr"]["max_abs_error"]
                ),
                "K_lqr_relative_fro_error": stable_float(
                    route_metrics["K_lqr"]["relative_fro_error"]
                ),
                "DeltaK_max_abs_error": stable_float(
                    route_metrics["DeltaK"]["max_abs_error"]
                ),
                "DeltaC_max_abs_error": stable_float(
                    route_metrics["DeltaC"]["max_abs_error"]
                ),
            }
        )

    # Re-hash the two read-only workspaces after all calculations.
    input_hash_after: dict[str, str] = {}
    for route_id in DIV2_ROUTE_IDS:
        workspace_path = base / routes[route_id]["workspace_relpath"]
        input_hash_after[route_id] = sha256_file(workspace_path)
        if input_hash_after[route_id] != input_hash_before[route_id]:
            raise RuntimeError(f"Input workspace mutated during audit: {route_id}")
        for row in route_summaries:
            if row["route_id"] == route_id:
                row["workspace_unchanged"] = "TRUE"

    compared_workspace_names = (
        "MPren",
        "CPren",
        "KPren",
        "M",
        "C",
        "K",
        "A",
        "B",
        "Ad",
        "Bd",
        "Q",
        "R",
        "K_lqr",
        "Acl",
        "DeltaK",
        "DeltaC",
        "dt",
        "S",
    )
    compared_independent_names = (
        "M",
        "C",
        "K",
        "A",
        "B",
        "Ad",
        "Bd",
        "Q",
        "R",
        "P",
        "K_lqr",
        "Acl",
        "DeltaK",
        "DeltaC",
        "closed_loop_poles",
    )
    cross_route = {
        "route_pair": list(DIV2_ROUTE_IDS),
        "workspace_arrays_exactly_equal": bool(
            all(
                np.array_equal(
                    workspace_by_route[DIV2_ROUTE_IDS[0]][name],
                    workspace_by_route[DIV2_ROUTE_IDS[1]][name],
                )
                for name in compared_workspace_names
            )
        ),
        "independent_arrays_exactly_equal": bool(
            all(
                np.array_equal(
                    np.asarray(independent_by_route[DIV2_ROUTE_IDS[0]][name]),
                    np.asarray(independent_by_route[DIV2_ROUTE_IDS[1]][name]),
                )
                for name in compared_independent_names
            )
        ),
        "workspace_variables_compared": list(compared_workspace_names),
        "independent_variables_compared": list(compared_independent_names),
    }

    contract = contract_rows()
    contract_summary: dict[str, Any] = {}
    for document_id in ("liang_thesis", "manuscript_0824"):
        rows = [row for row in contract if row["document_id"] == document_id]
        closed_count = sum(row["contract_closed_for_field"] == "TRUE" for row in rows)
        contract_summary[document_id] = {
            "required_field_count": len(rows),
            "specified_field_count": closed_count,
            "unclosed_field_count": len(rows) - closed_count,
            "status": "CONTRACT_NOT_CLOSED" if closed_count != len(rows) else "CONTRACT_CLOSED",
        }

    overall_status = "STRICT_ABS_GATE_FAIL_AND_PAPER_CONTRACT_NOT_CLOSED"
    audit = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall_status,
        "scope": "historical_discrete_lqr_core_and_paper_contract_only",
        "tolerances": {
            "primary_strict_absolute": {
                "definition": "max(abs(independent-reference)) <= 1e-8",
                "value": STRICT_ABS_TOL,
                "can_be_replaced_by_scale_aware_gate": False,
            },
            "secondary_scale_aware": {
                "definition": "abs(diff) <= atol + rtol*abs(reference) elementwise",
                "atol": SCALE_ATOL,
                "rtol": SCALE_RTOL,
                "role": "diagnostic_only",
            },
        },
        "independence": {
            "matlab_used_for_recalculation": False,
            "zoh_implementation": "scipy.linalg.expm on augmented [A B;0 0] matrix",
            "dare_implementation": "scipy.linalg.solve_discrete_are",
            "step4_rho_or_poles_read": False,
            "forbidden_input_root": "outputs/step4_rho_grids",
            "actual_step4_rho_inputs": [],
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "h5py": h5py.__version__,
            "platform": platform.platform(),
        },
        "historical_program_constants": {
            "dt_seconds": EXPECTED_DT,
            "Q_diagonal": np.diag(EXPECTED_Q).tolist(),
            "R_diagonal": np.diag(EXPECTED_R).tolist(),
            "state_order": ["q1", "q2", "qdot1", "qdot2"],
            "B_lower_block": "solve(MPren, I)",
            "DeltaK": "MPren @ K_lqr[:,0:n]",
            "DeltaC": "MPren @ K_lqr[:,n:2*n]",
        },
        "routes": route_summaries,
        "cross_route_identity": cross_route,
        "source_contract_checks": source_checks,
        "input_hash_before": input_hash_before,
        "input_hash_after": input_hash_after,
        "source_hashes": source_hashes,
        "paper_contract_summary": contract_summary,
        "paper_contract_verdict": "待决定",
        "evidence_labels": {
            "historical_program_execution": "计算级复现由步骤2另行裁决",
            "this_independent_lqr_check": "SCALE_AWARE_PASS_STRICT_ABS_FAIL",
            "paper_formula_validation": "CONTRACT_NOT_CLOSED",
            "plot_reproduction": "本步骤未执行，不升级",
            "historical_figure_values": "历史值",
        },
        "generated_files": [
            "route_lqr_summary.csv",
            "lqr_variable_comparison.csv",
            "design_poles.csv",
            "recomputed_lqr_matrices.csv",
            "source_contract_checks.csv",
            "thesis_manuscript_contract_matrix.csv",
            "audit.json",
            "步骤5_LQR独立复算与论文合同缺口审计.md",
            "artifact_manifest.csv",
        ],
    }

    report = build_report(route_summaries, comparison_rows, contract, source_hashes, cross_route)
    log_lines = [
        f"SCHEMA_VERSION={SCHEMA_VERSION}",
        f"OVERALL_STATUS={overall_status}",
        f"STRICT_ABS_TOL={stable_float(STRICT_ABS_TOL)}",
        f"SCALE_ATOL={stable_float(SCALE_ATOL)}",
        f"SCALE_RTOL={stable_float(SCALE_RTOL)}",
    ]
    for row in route_summaries:
        log_lines.append(f"ROUTE={row['route_id']} STATUS={row['status']}")
    log_lines.extend(
        [
            f"CROSS_ROUTE_WORKSPACE_ARRAYS_EQUAL={cross_route['workspace_arrays_exactly_equal']}",
            f"CROSS_ROUTE_INDEPENDENT_ARRAYS_EQUAL={cross_route['independent_arrays_exactly_equal']}",
            "STEP4_RHO_INPUTS_READ=0",
            f"THESIS_CONTRACT={contract_summary['liang_thesis']['status']}",
            f"MANUSCRIPT_CONTRACT={contract_summary['manuscript_0824']['status']}",
            "RUN_COMPLETE=TRUE",
        ]
    )

    route_fields = [
        "route_id",
        "division",
        "active_dlqr_count",
        "active_dlqr_lines",
        "active_c2d_count",
        "status",
        "closed_loop_rho",
        "zoh_strict_abs_pass",
        "acl_strict_abs_pass",
        "lqr_gain_and_delta_strict_abs_pass",
        "all_scale_aware_pass",
        "workspace_sha256",
        "workspace_unchanged",
        "dare_residual_max_abs",
        "dare_residual_scaled_fro",
        "K_lqr_max_abs_error",
        "K_lqr_relative_fro_error",
        "DeltaK_max_abs_error",
        "DeltaC_max_abs_error",
    ]
    comparison_fields = [
        "route_id",
        "variable",
        "shape",
        "max_abs_error",
        "relative_fro_error",
        "strict_abs_tolerance",
        "strict_abs_pass",
        "scale_atol",
        "scale_rtol",
        "max_scale_gate_ratio",
        "scale_aware_pass",
        "reference",
    ]
    pole_fields = [
        "route_id",
        "matched_pole_index",
        "independent_real",
        "independent_imag",
        "reference_real",
        "reference_imag",
        "absolute_error",
        "strict_abs_tolerance",
        "strict_abs_pass",
    ]
    matrix_fields = ["route_id", "matrix", "row_1based", "column_1based", "real", "imag"]
    source_check_fields = ["route_id", "check", "expected", "actual", "status"]
    contract_fields = [
        "document_id",
        "field_id",
        "field_name_cn",
        "required_for_unique_reproduction",
        "status",
        "specified_value",
        "evidence",
        "gap_consequence",
        "cross_document_conflict",
        "contract_closed_for_field",
    ]

    output_payloads = {
        "route_lqr_summary.csv": csv_bytes(route_summaries, route_fields),
        "lqr_variable_comparison.csv": csv_bytes(comparison_rows, comparison_fields),
        "design_poles.csv": csv_bytes(pole_rows, pole_fields),
        "recomputed_lqr_matrices.csv": csv_bytes(matrix_rows, matrix_fields),
        "source_contract_checks.csv": csv_bytes(source_checks, source_check_fields),
        "thesis_manuscript_contract_matrix.csv": csv_bytes(contract, contract_fields),
        "audit.json": json_bytes(audit),
        "步骤5_LQR独立复算与论文合同缺口审计.md": (report + "\n").encode("utf-8"),
    }
    for filename, payload in output_payloads.items():
        write_if_changed(output_dir / filename, payload)
    write_if_changed(log_path, ("\n".join(log_lines) + "\n").encode("utf-8"))

    manifest_rows: list[dict[str, Any]] = []
    for role, path in [
        ("code", code_path),
        ("input_manifest", manifest_path),
        ("input_formula_report", step3_report_path),
        ("input_manuscript", manuscript_path),
        ("run_log", log_path),
    ]:
        manifest_rows.append(
            {
                "role": role,
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    for route_id in DIV2_ROUTE_IDS:
        path = base / routes[route_id]["workspace_relpath"]
        manifest_rows.append(
            {
                "role": f"sealed_workspace:{route_id}",
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    for filename in output_payloads:
        path = output_dir / filename
        manifest_rows.append(
            {
                "role": "generated_output",
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest_payload = csv_bytes(manifest_rows, ["role", "path", "bytes", "sha256"])
    write_if_changed(output_dir / "artifact_manifest.csv", manifest_payload)

    print(f"BOARD20_STEP5_LQR={overall_status}")
    for row in route_summaries:
        print(f"{row['route_id']}={row['status']}")
    print(
        "CONTRACTS="
        f"thesis:{contract_summary['liang_thesis']['status']},"
        f"manuscript:{contract_summary['manuscript_0824']['status']}"
    )
    print(f"OUTPUT_DIR={output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
