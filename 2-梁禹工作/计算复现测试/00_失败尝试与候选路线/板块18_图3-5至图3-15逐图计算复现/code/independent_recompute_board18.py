"""板块18第三章响应的独立Python状态空间复算器。

本脚本只从板块18 ``input/`` 冻结包读取以下五类证据：

1. ``reference_model_matlab.mat`` 中由 ``PDmonicanshu.m`` 得到的
   15自由度 ``MRrt/CRrt/KRrt``；
2. 板块17 ``global_routes_matlab.mat`` 中的矩阵、载荷投影与恢复矩阵，
   仅用于逐矩阵交叉核对；
3. ``PDmonicanshu.m`` 与 ``regenerate_chapter3_data.m`` 的冻结字节；
4. ``EQ.mat`` 中的原始El Centro时间与加速度；
5. 若冻结包提供，则读取板块17 ``contract_simulink_workspace.csv``，
   复核原SLX的三个增益表达式。

严禁事项：本脚本不搜索、不读取、也不复制任何Simulink ``simout*``、
``response_mm`` 或历史响应列来生成独立结果。所有响应都由连续状态空间
在零初值下采用经典四阶Runge--Kutta重新积分。

力符号不是按常见基底激励公式猜测。两份冻结SLX的静态合同均给出：

* Original: ``diag([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0].*MRrt)``；
* Guyan: ``T'*Mf``；
* Craig--Bampton: ``T_cb'*Mf``。

三个Gain均无前置负号，而生成器的StateSpace输入矩阵为
``B=[0; M\\I]``，故本脚本忠实实现
``M*qdd + C*qd + K*q = +f_projection*u(t)``。这只是现存代码合同，
不宣称等同于通常写成负号的物理基底激励约定。

From Workspace合同也逐阶段复现：单位阶跃 ``Interpolate=off``，按
零阶保持取RK4的起点、半步和终点值；Chirp与El Centro
``Interpolate=on``，在每个RK4半步/终点做分段线性插值，区间外保持
首末值。单位阶跃在 ``t=1 s`` 不连续点的Simulink事件命中语义仍须由
后续MATLAB交叉比较裁决，脚本不会为拟合响应而静默移位。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy import linalg
from scipy.io import loadmat, savemat


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_INPUT_ROOT = CANDIDATE_ROOT / "input"
DEFAULT_OUTPUT_ROOT = CANDIDATE_ROOT / "outputs" / "independent"

DT = 1.0 / 1024.0
STOP_TIME_S = 40.0
EXPECTED_SAMPLES = 40961
FORCE_SIGN = 1.0
MATRIX_RELATIVE_TOLERANCE = 5.0e-12
MATRIX_ABSOLUTE_TOLERANCE = 5.0e-12
TIME_TOLERANCE_S = 1.0e-14

EXPECTED_SHA256 = {
    "reference_model_matlab.mat": (
        "7F9C7C6ACEEDA106304B943F280CCFFF06CBA9137059857A4D89CB06D5B0DAB3"
    ),
    "global_routes_matlab.mat": (
        "A58A830134259585ECD091BA37B3A69640E79D3AA10B5094E106F2EC01ED56ED"
    ),
    "PDmonicanshu.m": (
        "CB25DFABD21175FE0CE5F93ABE722B365D25C0D4ADE9BEAF3B7EBD25328D1C4D"
    ),
    "regenerate_chapter3_data.m": (
        "CBD7D4BE3927DEC5C18D5C16FBE164528AE6DC022F0B81DB28BD93416F4E7CEE"
    ),
    "EQ.mat": (
        "F0292EF78E5B3FA585931F382BDFBF325FBC2E79DDA55ED4FC97568A3344F9C9"
    ),
    "contract_simulink_workspace.csv": (
        "15B934A84AD78C78704A81079B71C2F899E1932A9F2E38ACF78BC1C4DEA077B7"
    ),
}

METHOD_ORDER = ("Original", "Guyan", "Craig-Bampton")
FLOOR_ORDER = ("Floor 1", "Floor 2", "Floor 3")

DIVISIONS: dict[int, dict[str, Any]] = {
    1: {
        "master": [1, 6, 11, 4, 9, 14],
        "slave": [2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask_ordered": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "expected_guyan_dimension": 6,
        "expected_cb_dimension": 9,
    },
    2: {
        "master": [1, 11, 4, 9, 14],
        "slave": [6, 2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask_ordered": [1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "expected_guyan_dimension": 5,
        "expected_cb_dimension": 8,
    },
}

DATASETS = (
    {
        "key": "unit_step_division1",
        "basename": "单位激励_原结构三层响应",
        "division": 1,
        "signal": "unit_step",
        "excitation": "单位阶跃，t>=1 s；From Workspace Interpolate=off",
    },
    {
        "key": "division1_elcentro",
        "basename": "第一类划分_ElCentro地震响应",
        "division": 1,
        "signal": "elcentro",
        "excitation": "El Centro 1940 NS，原记录乘0.40；线性插值",
    },
    {
        "key": "division2_elcentro",
        "basename": "第二类划分_ElCentro地震响应",
        "division": 2,
        "signal": "elcentro",
        "excitation": "El Centro 1940 NS，原记录乘0.40；线性插值",
    },
    {
        "key": "division1_chirp",
        "basename": "第一类划分_Chirp响应",
        "division": 1,
        "signal": "chirp",
        "excitation": "0.1--10 Hz线性Chirp，40 s；线性插值",
    },
    {
        "key": "division2_chirp",
        "basename": "第二类划分_Chirp响应",
        "division": 2,
        "signal": "chirp",
        "excitation": "0.1--10 Hz线性Chirp，40 s；线性插值",
    },
)


@dataclass(frozen=True)
class ResolvedInput:
    role: str
    path: Path
    sha256: str
    equivalent_candidates: tuple[str, ...]


@dataclass(frozen=True)
class WorkspaceSignal:
    """MATLAB From Workspace的标量时间序列合同。"""

    time_s: np.ndarray
    values: np.ndarray
    interpolate: bool
    name: str

    def sample(self, query_time_s: np.ndarray) -> np.ndarray:
        query = np.asarray(query_time_s, dtype=float)
        if self.interpolate:
            return np.interp(
                query,
                self.time_s,
                self.values,
                left=float(self.values[0]),
                right=float(self.values[-1]),
            )
        # From Workspace关闭插值时按前一样本零阶保持；精确落在新时间戳时
        # 采用该新样本。后续与Simulink在t=1 s事件点的逐点比较仍单列裁决。
        indices = np.searchsorted(self.time_s, query, side="right") - 1
        indices = np.clip(indices, 0, self.time_s.size - 1)
        return self.values[indices]

    def rk4_stage_values(self, output_time_s: np.ndarray) -> tuple[np.ndarray, ...]:
        left = output_time_s[:-1]
        right = output_time_s[1:]
        middle = left + 0.5 * (right - left)
        return self.sample(left), self.sample(middle), self.sample(right)


@dataclass(frozen=True)
class MechanicalStateSpace:
    name: str
    mass: np.ndarray
    damping: np.ndarray
    stiffness: np.ndarray
    force_projection: np.ndarray
    floor_recovery: np.ndarray
    A: np.ndarray
    b: np.ndarray


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_error(actual: np.ndarray, reference: np.ndarray) -> float:
    actual_array = np.asarray(actual, dtype=float)
    reference_array = np.asarray(reference, dtype=float)
    difference = actual_array - reference_array
    denominator = float(np.linalg.norm(reference_array.ravel()))
    numerator = float(np.linalg.norm(difference.ravel()))
    return numerator if denominator == 0.0 else numerator / denominator


def maximum_absolute_error(actual: np.ndarray, reference: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(actual) - np.asarray(reference))))


def decode_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"无法按UTF-8或GB18030解码冻结文本：{path}")


def ensure_inside(path: Path, root: Path, label: str) -> None:
    path_resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RuntimeError(f"{label}越出允许根：{path_resolved}；允许根={root_resolved}") from exc


def resolve_input(
    input_root: Path,
    basename: str,
    explicit: str | None,
    optional: bool = False,
) -> ResolvedInput | None:
    expected = EXPECTED_SHA256[basename]
    if explicit:
        candidates = [Path(explicit).resolve()]
    else:
        candidates = sorted(path.resolve() for path in input_root.rglob(basename) if path.is_file())
    for candidate in candidates:
        ensure_inside(candidate, input_root, f"冻结输入{basename}")
    if not candidates:
        if optional:
            return None
        raise RuntimeError(f"冻结输入未就绪：在{input_root}下找不到{basename}")
    missing = [str(path) for path in candidates if not path.is_file()]
    if missing:
        raise RuntimeError(f"显式输入不存在：{missing}")
    hashes = {path: sha256(path) for path in candidates}
    unexpected = {str(path): value for path, value in hashes.items() if value != expected}
    if unexpected:
        raise RuntimeError(
            f"{basename}出现非冻结哈希，拒绝猜选：expected={expected}, actual={unexpected}"
        )
    chosen = candidates[0]
    return ResolvedInput(
        role=basename,
        path=chosen,
        sha256=expected,
        equivalent_candidates=tuple(str(path) for path in candidates),
    )


def record_check(
    rows: list[dict[str, Any]],
    scope: str,
    object_name: str,
    metric: str,
    actual: Any,
    criterion: str,
    passed: bool,
    evidence: str,
) -> None:
    rows.append(
        {
            "scope": scope,
            "object": object_name,
            "metric": metric,
            "actual": actual,
            "criterion": criterion,
            "result": "PASS" if passed else "FAIL",
            "evidence": evidence,
        }
    )


def audit_source_contract(
    pd_script: ResolvedInput,
    generator: ResolvedInput,
    workspace_contract: ResolvedInput | None,
    rows: list[dict[str, Any]],
) -> list[str]:
    uncertainties: list[str] = []
    pd_text = decode_text(pd_script.path)
    generator_text = decode_text(generator.path)
    pd_tokens = ("MRrt", "CRrt", "KRrt", "damping = 0.05")
    generator_tokens = (
        "dt = 1/1024;",
        "stopTime = 40;",
        "unitStep = double(fineTime >= 1);",
        "chirpAcceleration = sin(2*pi*0.1*fineTime",
        "eqAcceleration = EQ_intensity * ElCentroAccel(2,:)'",
        "'Interpolate', interpolateText",
        "'Solver', 'ode4', 'FixedStep', 'dt'",
        "T = [eye(nm); -Kss\\Ksm];",
        "Mg = Mmm - Mms*(Kss\\Ksm);",
        "Cg = Cmm - Cms*(Kss\\Ksm);",
        "Kg = Kmm - Kms*(Kss\\Ksm);",
        "Mf = diag(forceMask .* Mforce);",
    )
    for token in pd_tokens:
        present = token in pd_text
        record_check(
            rows,
            "source_contract",
            "PDmonicanshu.m",
            f"token:{token}",
            present,
            "present=True",
            present,
            str(pd_script.path),
        )
    for token in generator_tokens:
        present = token in generator_text
        record_check(
            rows,
            "source_contract",
            "regenerate_chapter3_data.m",
            f"token:{token}",
            present,
            "present=True",
            present,
            str(generator.path),
        )

    if workspace_contract is None:
        raise RuntimeError("冻结工作区合同不得缺失")
    with workspace_contract.path.open("r", encoding="utf-8-sig", newline="") as stream:
        contract_rows = list(csv.DictReader(stream))
    expected_gain_contracts = {
        (model, sid, expression)
        for model in ("lvxvjie_guyan_2.slx", "lvxvjie_guyan.slx")
        for sid, expression in (
            ("4384", "diag([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0].*MRrt)"),
            ("4386", "T'*Mf"),
            ("4398", "T_cb'*Mf"),
        )
    }
    actual_gain_contracts = {
        (row.get("model_file", ""), row.get("block_sid", ""), row.get("expression", ""))
        for row in contract_rows
        if row.get("parameter") == "Gain"
        and row.get("block_sid") in {"4384", "4386", "4398"}
        and row.get("status") == "PASS"
    }
    exact_positive_contract = actual_gain_contracts == expected_gain_contracts
    record_check(
        rows,
        "force_contract",
        "原SLX静态合同",
        "six_exact_positive_gain_expressions",
        sorted(actual_gain_contracts),
        "exactly six model/SID/expression tuples, all without leading minus",
        exact_positive_contract,
        str(workspace_contract.path),
    )
    uncertainties.append(
        "单位阶跃Interpolate=off在t=1 s不连续点的右端事件命中语义须与MATLAB逐点交叉核对；当前实现为精确时间戳采用新样本。"
    )
    return uncertainties


def canonical_fixed_interface_modes(
    stiffness: np.ndarray, mass: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    eigenvalues, eigenvectors = linalg.eig(stiffness, mass)
    max_imaginary = float(np.max(np.abs(eigenvalues.imag)))
    if max_imaginary > 1.0e-7:
        raise RuntimeError(f"固定界面特征值出现不可忽略虚部：{max_imaginary:.17g}")
    order = np.argsort(eigenvalues.real)
    values = eigenvalues.real[order]
    vectors = eigenvectors.real[:, order]
    if values[0] <= 0.0:
        raise RuntimeError(f"固定界面特征值非正：min={values[0]:.17g}")
    for column in range(vectors.shape[1]):
        norm = float(np.linalg.norm(vectors[:, column]))
        if norm == 0.0:
            raise RuntimeError("固定界面特征向量范数为零")
        vectors[:, column] /= norm
        pivot = int(np.argmax(np.abs(vectors[:, column])))
        if vectors[pivot, column] < 0.0:
            vectors[:, column] *= -1.0
    return values, vectors


def build_division(
    mass: np.ndarray,
    damping: np.ndarray,
    stiffness: np.ndarray,
    division: int,
) -> dict[str, Any]:
    definition = DIVISIONS[division]
    master_1 = np.asarray(definition["master"], dtype=int)
    slave_1 = np.asarray(definition["slave"], dtype=int)
    order_1 = np.concatenate([master_1, slave_1])
    if sorted(order_1.tolist()) != list(range(1, 16)) or np.unique(order_1).size != 15:
        raise RuntimeError(f"第{division}类主从自由度不是1:15无重复分割")
    order = order_1 - 1
    n_master = master_1.size
    mo = mass[np.ix_(order, order)]
    co = damping[np.ix_(order, order)]
    ko = stiffness[np.ix_(order, order)]
    m_mm = mo[:n_master, :n_master]
    m_ms = mo[:n_master, n_master:]
    c_mm = co[:n_master, :n_master]
    c_ms = co[:n_master, n_master:]
    k_mm = ko[:n_master, :n_master]
    k_ms = ko[:n_master, n_master:]
    k_sm = ko[n_master:, :n_master]
    k_ss = ko[n_master:, n_master:]
    m_ss = mo[n_master:, n_master:]

    static_relation = -linalg.solve(k_ss, k_sm, assume_a="sym")
    transform = np.vstack([np.eye(n_master), static_relation])
    historical_mass = m_mm + m_ms @ static_relation
    historical_damping = c_mm + c_ms @ static_relation
    historical_stiffness = k_mm + k_ms @ static_relation

    fixed_values, fixed_modes = canonical_fixed_interface_modes(k_ss, m_ss)
    retained = 3
    cb_transform = np.block(
        [
            [np.eye(n_master), np.zeros((n_master, retained))],
            [static_relation, fixed_modes[:, :retained]],
        ]
    )
    cb_mass = cb_transform.T @ mo @ cb_transform
    cb_damping = cb_transform.T @ co @ cb_transform
    cb_stiffness = cb_transform.T @ ko @ cb_transform

    permutation = np.eye(15)[order, :]
    natural_recovery_guyan = permutation.T @ transform
    natural_recovery_cb = permutation.T @ cb_transform
    floor_selector = np.eye(15)[np.asarray([1, 6, 11]) - 1, :]
    floor_recovery_guyan = floor_selector @ natural_recovery_guyan
    floor_recovery_cb = floor_selector @ natural_recovery_cb

    force_mask = np.asarray(definition["force_mask_ordered"], dtype=float)
    mf = force_mask * np.diag(mo)
    input_guyan = FORCE_SIGN * (transform.T @ mf)
    input_cb = FORCE_SIGN * (cb_transform.T @ mf)

    return {
        "division": division,
        "master": master_1,
        "slave": slave_1,
        "order": order_1,
        "Mo": mo,
        "Co": co,
        "Ko": ko,
        "Ksm": k_sm,
        "Kss": k_ss,
        "Mss": m_ss,
        "static_relation": static_relation,
        "T": transform,
        "M_historical": historical_mass,
        "C_historical": historical_damping,
        "K_historical": historical_stiffness,
        "fixed_interface_eigenvalues_sorted": fixed_values,
        "fixed_interface_phi_sorted": fixed_modes,
        "T_cb": cb_transform,
        "M_cb": cb_mass,
        "C_cb": cb_damping,
        "K_cb": cb_stiffness,
        "R_guyan_natural": natural_recovery_guyan,
        "R_cb_natural": natural_recovery_cb,
        "S_floor_natural": floor_selector,
        "floor_recovery_guyan": floor_recovery_guyan,
        "floor_recovery_cb": floor_recovery_cb,
        "Mf": mf,
        "input_guyan": input_guyan,
        "input_cb": input_cb,
    }


def as_float_array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=float)


def compare_matrices_to_board17(
    reference: dict[str, Any],
    board17: dict[str, Any],
    computed: dict[int, dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    for name in ("MRrt", "CRrt", "KRrt"):
        actual = as_float_array(reference[name])
        frozen = as_float_array(board17[name])
        error = relative_error(actual, frozen)
        record_check(
            rows,
            "full_model",
            name,
            "reference_vs_board17_relative_error",
            error,
            f"<={MATRIX_RELATIVE_TOLERANCE}",
            error <= MATRIX_RELATIVE_TOLERANCE,
            "reference_model_matlab.mat vs global_routes_matlab.mat",
        )

    natural_mask = np.zeros(15, dtype=float)
    natural_mask[[0, 5, 10]] = 1.0
    input_full_natural = FORCE_SIGN * natural_mask * np.diag(as_float_array(reference["MRrt"]))

    direct_fields = (
        "Mo",
        "Co",
        "Ko",
        "T",
        "M_historical",
        "C_historical",
        "K_historical",
        "Mf",
        "input_guyan",
        "floor_recovery_guyan",
    )
    for division in (1, 2):
        result = computed[division]
        frozen = board17[f"division{division}"]
        for field in direct_fields:
            actual = as_float_array(result[field]).squeeze()
            expected = as_float_array(frozen[field]).squeeze()
            error = relative_error(actual, expected)
            record_check(
                rows,
                f"division_{division}",
                field,
                "independent_vs_board17_relative_error",
                error,
                f"<={MATRIX_RELATIVE_TOLERANCE}",
                error <= MATRIX_RELATIVE_TOLERANCE,
                "独立公式重建；未调用MATLAB缩聚代码",
            )

        full_error = relative_error(
            input_full_natural,
            as_float_array(frozen["input_full_natural"]).squeeze(),
        )
        record_check(
            rows,
            f"division_{division}",
            "input_full_natural",
            "positive_projection_relative_error",
            full_error,
            f"<={MATRIX_RELATIVE_TOLERANCE}",
            full_error <= MATRIX_RELATIVE_TOLERANCE,
            "原SLX SID4384正号质量增益",
        )

        n_master = int(np.asarray(result["master"]).size)
        independent_modes = as_float_array(result["T_cb"])[n_master:, n_master:]
        frozen_tcb = as_float_array(frozen["T_cb"])
        frozen_modes = frozen_tcb[n_master:, n_master:]
        angles = linalg.subspace_angles(independent_modes, frozen_modes)
        max_angle = float(np.max(angles))
        record_check(
            rows,
            f"division_{division}",
            "T_cb_retained_mode_subspace",
            "maximum_principal_angle_rad",
            max_angle,
            "<=5e-8 rad",
            max_angle <= 5.0e-8,
            "允许固定界面模态符号/尺度/基底旋转，不改变传递函数",
        )

        basis_map, _, rank, _ = linalg.lstsq(independent_modes, frozen_modes)
        if rank != 3 or not np.all(np.isfinite(basis_map)):
            raise RuntimeError(f"第{division}类CB模态基底对齐矩阵秩不足")
        coordinate_map = linalg.block_diag(np.eye(n_master), basis_map)
        aligned = {
            "T_cb": as_float_array(result["T_cb"]) @ coordinate_map,
            "M_cb": coordinate_map.T @ as_float_array(result["M_cb"]) @ coordinate_map,
            "C_cb": coordinate_map.T @ as_float_array(result["C_cb"]) @ coordinate_map,
            "K_cb": coordinate_map.T @ as_float_array(result["K_cb"]) @ coordinate_map,
            "input_cb": coordinate_map.T @ as_float_array(result["input_cb"]),
            "floor_recovery_cb": as_float_array(result["floor_recovery_cb"]) @ coordinate_map,
        }
        for field, actual in aligned.items():
            expected = as_float_array(frozen[field]).squeeze()
            actual_squeezed = np.asarray(actual).squeeze()
            error = relative_error(actual_squeezed, expected)
            record_check(
                rows,
                f"division_{division}",
                field,
                "basis_aligned_relative_error",
                error,
                f"<={MATRIX_RELATIVE_TOLERANCE}",
                error <= MATRIX_RELATIVE_TOLERANCE,
                "独立CB基底经可逆坐标映射后与板块17比较",
            )

        eigen_error = relative_error(
            as_float_array(result["fixed_interface_eigenvalues_sorted"]),
            as_float_array(frozen["fixed_interface_eigenvalues_sorted"]),
        )
        record_check(
            rows,
            f"division_{division}",
            "fixed_interface_eigenvalues_sorted",
            "relative_error",
            eigen_error,
            f"<={MATRIX_RELATIVE_TOLERANCE}",
            eigen_error <= MATRIX_RELATIVE_TOLERANCE,
            "scipy.linalg.eig(Kss,Mss)升序",
        )

        static_residual = float(
            np.linalg.norm(result["Ksm"] + result["Kss"] @ result["static_relation"])
            / np.linalg.norm(result["Ksm"])
        )
        record_check(
            rows,
            f"division_{division}",
            "static_relation",
            "constraint_relative_residual",
            static_residual,
            f"<={MATRIX_RELATIVE_TOLERANCE}",
            static_residual <= MATRIX_RELATIVE_TOLERANCE,
            "Ksm+Kss*R=0",
        )


def build_state_space(
    name: str,
    mass: np.ndarray,
    damping: np.ndarray,
    stiffness: np.ndarray,
    force_projection: np.ndarray,
    floor_recovery: np.ndarray,
) -> MechanicalStateSpace:
    mass = as_float_array(mass)
    damping = as_float_array(damping)
    stiffness = as_float_array(stiffness)
    force_projection = as_float_array(force_projection).reshape(-1)
    floor_recovery = as_float_array(floor_recovery)
    n = mass.shape[0]
    if mass.shape != (n, n) or damping.shape != (n, n) or stiffness.shape != (n, n):
        raise RuntimeError(f"{name}的M/C/K维数不一致")
    if force_projection.shape != (n,) or floor_recovery.shape != (3, n):
        raise RuntimeError(
            f"{name}的载荷/恢复维数错误：force={force_projection.shape}, recovery={floor_recovery.shape}"
        )
    acceleration_stiffness = linalg.solve(mass, stiffness)
    acceleration_damping = linalg.solve(mass, damping)
    acceleration_input = linalg.solve(mass, force_projection)
    A = np.block(
        [
            [np.zeros((n, n)), np.eye(n)],
            [-acceleration_stiffness, -acceleration_damping],
        ]
    )
    b = np.concatenate([np.zeros(n), acceleration_input])
    return MechanicalStateSpace(
        name=name,
        mass=mass,
        damping=damping,
        stiffness=stiffness,
        force_projection=force_projection,
        floor_recovery=floor_recovery,
        A=A,
        b=b,
    )


def construct_systems(
    mass: np.ndarray,
    damping: np.ndarray,
    stiffness: np.ndarray,
    computed: dict[int, dict[str, Any]],
) -> dict[int, dict[str, MechanicalStateSpace]]:
    natural_mask = np.zeros(15, dtype=float)
    natural_mask[[0, 5, 10]] = 1.0
    input_full = FORCE_SIGN * natural_mask * np.diag(mass)
    floor_selector = np.eye(15)[[0, 5, 10], :]
    systems: dict[int, dict[str, MechanicalStateSpace]] = {}
    for division in (1, 2):
        route = computed[division]
        systems[division] = {
            "Original": build_state_space(
                f"Division {division} Original",
                mass,
                damping,
                stiffness,
                input_full,
                floor_selector,
            ),
            "Guyan": build_state_space(
                f"Division {division} historical Guyan",
                route["M_historical"],
                route["C_historical"],
                route["K_historical"],
                route["input_guyan"],
                route["floor_recovery_guyan"],
            ),
            "Craig-Bampton": build_state_space(
                f"Division {division} Craig-Bampton r=3",
                route["M_cb"],
                route["C_cb"],
                route["K_cb"],
                route["input_cb"],
                route["floor_recovery_cb"],
            ),
        }
    return systems


def integrate_rk4(
    system: MechanicalStateSpace,
    output_time_s: np.ndarray,
    signal: WorkspaceSignal,
) -> np.ndarray:
    """按Simulink ode4的经典RK4阶段公式积分LTI状态空间。"""

    u_left, u_middle, u_right = signal.rk4_stage_values(output_time_s)
    state = np.zeros(system.A.shape[0], dtype=float)
    response_mm = np.empty((output_time_s.size, 3), dtype=float)
    displacement_count = system.mass.shape[0]
    response_mm[0, :] = 1000.0 * (system.floor_recovery @ state[:displacement_count])
    A = system.A
    b = system.b
    for index in range(output_time_s.size - 1):
        h = float(output_time_s[index + 1] - output_time_s[index])
        k1 = A @ state + b * u_left[index]
        k2 = A @ (state + 0.5 * h * k1) + b * u_middle[index]
        k3 = A @ (state + 0.5 * h * k2) + b * u_middle[index]
        k4 = A @ (state + h * k3) + b * u_right[index]
        state = state + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        response_mm[index + 1, :] = 1000.0 * (
            system.floor_recovery @ state[:displacement_count]
        )
    if not np.all(np.isfinite(response_mm)):
        raise RuntimeError(f"{system.name}/{signal.name}独立RK4响应含NaN/Inf")
    return response_mm


def load_and_validate_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, ResolvedInput | None], dict[str, Any], dict[str, Any], dict[str, Any]]:
    input_root = Path(args.input_root).resolve()
    if input_root != DEFAULT_INPUT_ROOT.resolve():
        raise RuntimeError(
            f"独立复算输入根必须精确等于冻结input目录：{DEFAULT_INPUT_ROOT.resolve()}；实际={input_root}"
        )
    if not input_root.is_dir():
        raise RuntimeError(f"板块18冻结输入根不存在：{input_root}")
    resolved: dict[str, ResolvedInput | None] = {
        "reference": resolve_input(
            input_root, "reference_model_matlab.mat", args.reference_mat
        ),
        "global_routes": resolve_input(
            input_root, "global_routes_matlab.mat", args.global_routes_mat
        ),
        "pd_script": resolve_input(input_root, "PDmonicanshu.m", args.pd_script),
        "generator": resolve_input(
            input_root, "regenerate_chapter3_data.m", args.generator
        ),
        "eq": resolve_input(input_root, "EQ.mat", args.eq_mat),
        "workspace_contract": resolve_input(
            input_root,
            "contract_simulink_workspace.csv",
            args.workspace_contract,
        ),
    }
    reference_path = resolved["reference"]
    global_path = resolved["global_routes"]
    eq_path = resolved["eq"]
    assert isinstance(reference_path, ResolvedInput)
    assert isinstance(global_path, ResolvedInput)
    assert isinstance(eq_path, ResolvedInput)
    reference = loadmat(
        reference_path.path,
        variable_names=["MRrt", "CRrt", "KRrt"],
        squeeze_me=True,
        struct_as_record=False,
    )
    board17 = loadmat(
        global_path.path,
        variable_names=["MRrt", "CRrt", "KRrt", "division1", "division2"],
        simplify_cells=True,
    )
    earthquake = loadmat(
        eq_path.path,
        variable_names=["EQ_intensity", "EQ_sw", "ElCentroAccel"],
        squeeze_me=True,
        struct_as_record=False,
    )
    for name in ("MRrt", "CRrt", "KRrt"):
        if name not in reference or as_float_array(reference[name]).shape != (15, 15):
            raise RuntimeError(f"reference_model_matlab.mat缺少15x15变量{name}")
    for name in ("MRrt", "CRrt", "KRrt", "division1", "division2"):
        if name not in board17:
            raise RuntimeError(f"global_routes_matlab.mat缺少变量{name}")
    if not isinstance(board17["division1"], dict) or not isinstance(board17["division2"], dict):
        raise RuntimeError("global_routes_matlab.mat的division1/division2不是可解析结构体")
    if "ElCentroAccel" not in earthquake:
        raise RuntimeError("EQ.mat缺少ElCentroAccel")
    return resolved, reference, board17, earthquake


def build_signals(earthquake: dict[str, Any]) -> tuple[np.ndarray, dict[str, WorkspaceSignal]]:
    step_count = int(round(STOP_TIME_S / DT))
    output_time = np.arange(step_count + 1, dtype=float) * DT
    if output_time.size != EXPECTED_SAMPLES or output_time[-1] != STOP_TIME_S:
        raise RuntimeError(
            f"固定时间网格错误：shape={output_time.shape}, end={output_time[-1]:.17g}"
        )
    unit_step = (output_time >= 1.0).astype(float)
    chirp = np.sin(
        2.0 * np.pi * 0.1 * output_time
        + np.pi * (10.0 - 0.1) / STOP_TIME_S * output_time**2
    )
    eq_switch = int(np.asarray(earthquake.get("EQ_sw", -1)).squeeze())
    eq_intensity = float(np.asarray(earthquake.get("EQ_intensity", np.nan)).squeeze())
    if eq_switch != 1 or abs(eq_intensity - 0.4) > 1.0e-15:
        raise RuntimeError(f"EQ合同错误：EQ_sw={eq_switch}, EQ_intensity={eq_intensity}")
    raw = as_float_array(earthquake["ElCentroAccel"])
    if raw.ndim != 2 or raw.shape[0] != 2:
        raise RuntimeError(f"ElCentroAccel应为2xN，实际{raw.shape}")
    eq_time = raw[0, :]
    eq_value = eq_intensity * raw[1, :]
    valid = eq_time <= STOP_TIME_S
    eq_time = eq_time[valid]
    eq_value = eq_value[valid]
    if eq_time.size < 2 or not np.all(np.diff(eq_time) > 0.0):
        raise RuntimeError("El Centro时间轴不足或不严格递增")
    signals = {
        "unit_step": WorkspaceSignal(
            output_time, unit_step, False, "unit_step_zoh"
        ),
        "chirp": WorkspaceSignal(
            output_time, chirp, True, "linear_chirp_workspace_interpolation"
        ),
        "elcentro": WorkspaceSignal(
            eq_time, eq_value, True, "elcentro_workspace_interpolation"
        ),
    }
    return output_time, signals


def response_checks_for_dataset(
    dataset: dict[str, Any],
    time_s: np.ndarray,
    response_mm: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expected_shape = (EXPECTED_SAMPLES, 3, 3)
    shape_pass = response_mm.shape == expected_shape
    time_pass = (
        time_s.shape == (EXPECTED_SAMPLES,)
        and np.all(np.diff(time_s) > 0.0)
        and abs(float(time_s[0])) <= TIME_TOLERANCE_S
        and abs(float(time_s[-1]) - STOP_TIME_S) <= TIME_TOLERANCE_S
        and float(np.max(np.abs(np.diff(time_s) - DT))) <= TIME_TOLERANCE_S
    )
    for floor_index, floor in enumerate(FLOOR_ORDER):
        for method_index, method in enumerate(METHOD_ORDER):
            values = response_mm[:, floor_index, method_index]
            finite = bool(np.all(np.isfinite(values)))
            rows.append(
                {
                    "dataset": dataset["basename"],
                    "division": dataset["division"],
                    "floor": floor,
                    "method": method,
                    "samples": int(values.size),
                    "response_shape": "x".join(str(v) for v in response_mm.shape),
                    "time_start_s": float(time_s[0]),
                    "time_end_s": float(time_s[-1]),
                    "max_dt_error_s": float(np.max(np.abs(np.diff(time_s) - DT))),
                    "finite": finite,
                    "peak_abs_mm": float(np.max(np.abs(values))),
                    "rms_mm": float(np.sqrt(np.mean(values**2))),
                    "final_mm": float(values[-1]),
                    "comparison_max_abs_error_mm": "",
                    "criterion": "shape=40961x3x3; time=0:1/1024:40; finite",
                    "result": "PASS" if shape_pass and time_pass and finite else "FAIL",
                }
            )
    return rows


def atomic_savemat(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    savemat(
        str(temporary),
        payload,
        do_compression=True,
        long_field_names=True,
        appendmat=False,
    )
    os.replace(temporary, path)


def atomic_write_response_csv(path: Path, time_s: np.ndarray, response_mm: np.ndarray) -> None:
    temporary = path.with_name(path.name + ".tmp")
    header = [
        "时间_s",
        "原结构_一层_mm",
        "Guyan_一层_mm",
        "CraigBampton_一层_mm",
        "原结构_二层_mm",
        "Guyan_二层_mm",
        "CraigBampton_二层_mm",
        "原结构_三层_mm",
        "Guyan_三层_mm",
        "CraigBampton_三层_mm",
    ]
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for index, time_value in enumerate(time_s):
            row: list[float] = [float(time_value)]
            for floor_index in range(3):
                for method_index in range(3):
                    row.append(float(response_mm[index, floor_index, method_index]))
            writer.writerow([format(value, ".17g") for value in row])
    os.replace(temporary, path)


def atomic_write_table(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写空CSV：{path}")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def serialize_resolved_inputs(
    resolved: dict[str, ResolvedInput | None]
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for role, item in resolved.items():
        if item is None:
            output[role] = None
        else:
            output[role] = {
                "path": str(item.path),
                "sha256": item.sha256,
                "equivalent_candidates": list(item.equivalent_candidates),
            }
    return output


def run_full(args: argparse.Namespace) -> int:
    resolved, reference, board17, earthquake = load_and_validate_inputs(args)
    matrix_rows: list[dict[str, Any]] = []
    pd_script = resolved["pd_script"]
    generator = resolved["generator"]
    assert isinstance(pd_script, ResolvedInput)
    assert isinstance(generator, ResolvedInput)
    workspace_contract = resolved["workspace_contract"]
    assert isinstance(workspace_contract, ResolvedInput)
    uncertainties = audit_source_contract(
        pd_script, generator, workspace_contract, matrix_rows
    )

    mass = as_float_array(reference["MRrt"])
    damping = as_float_array(reference["CRrt"])
    stiffness = as_float_array(reference["KRrt"])
    computed = {
        division: build_division(mass, damping, stiffness, division)
        for division in (1, 2)
    }
    compare_matrices_to_board17(reference, board17, computed, matrix_rows)
    matrix_failures = [row for row in matrix_rows if row["result"] != "PASS"]
    if matrix_failures:
        raise RuntimeError(
            "逐矩阵门槛未通过，拒绝积分："
            + json.dumps(matrix_failures[:8], ensure_ascii=False)
        )
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "VALIDATE_ONLY_PASS",
                    "matrix_check_count": len(matrix_rows),
                    "inputs": serialize_resolved_inputs(resolved),
                    "uncertainties": uncertainties,
                    "writes_performed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    output_root = Path(args.output_root).resolve()
    if output_root != DEFAULT_OUTPUT_ROOT.resolve():
        raise RuntimeError(
            f"独立复算输出根必须精确等于{DEFAULT_OUTPUT_ROOT.resolve()}；实际={output_root}"
        )
    data_root = output_root / "输入数据"
    data_root.mkdir(parents=True, exist_ok=True)
    systems = construct_systems(mass, damping, stiffness, computed)
    output_time, signals = build_signals(earthquake)
    response_rows: list[dict[str, Any]] = []
    dataset_outputs: dict[str, dict[str, Any]] = {}

    for dataset in DATASETS:
        division = int(dataset["division"])
        signal = signals[str(dataset["signal"])]
        response = np.empty((EXPECTED_SAMPLES, 3, 3), dtype=float)
        for method_index, method in enumerate(METHOD_ORDER):
            response[:, :, method_index] = integrate_rk4(
                systems[division][method], output_time, signal
            )
        rows = response_checks_for_dataset(dataset, output_time, response)
        response_rows.extend(rows)
        if any(row["result"] != "PASS" for row in rows):
            raise RuntimeError(f"{dataset['basename']}独立响应自检失败")

        mat_path = data_root / f"{dataset['basename']}.mat"
        csv_path = data_root / f"{dataset['basename']}.csv"
        atomic_savemat(
            mat_path,
            {
                "time_s": output_time.reshape(-1, 1),
                "response_mm": response,
                "method_order": np.asarray(METHOD_ORDER, dtype=object),
                "floor_order": np.asarray(FLOOR_ORDER, dtype=object),
                "excitation": str(dataset["excitation"]),
                "division": f"Division {division}",
                "solver": "independent classical RK4 matching Simulink ode4",
                "dt": DT,
                "stopTime": STOP_TIME_S,
                "force_sign": FORCE_SIGN,
            },
        )
        atomic_write_response_csv(csv_path, output_time, response)
        dataset_outputs[str(dataset["key"])] = {
            "basename": dataset["basename"],
            "mat": str(mat_path),
            "mat_sha256": sha256(mat_path),
            "csv": str(csv_path),
            "csv_sha256": sha256(csv_path),
            "shape": list(response.shape),
        }

    # 相同激励下完整模型与划分无关；这里只比较两次独立积分的Original列，
    # 不从任一Simulink响应文件取值。
    by_key = {item["key"]: item for item in DATASETS}
    cross_pairs = (
        ("division1_elcentro", "division2_elcentro"),
        ("division1_chirp", "division2_chirp"),
    )
    for left_key, right_key in cross_pairs:
        left_path = data_root / f"{by_key[left_key]['basename']}.mat"
        right_path = data_root / f"{by_key[right_key]['basename']}.mat"
        left = loadmat(left_path, variable_names=["response_mm"])["response_mm"][:, :, 0]
        right = loadmat(right_path, variable_names=["response_mm"])["response_mm"][:, :, 0]
        error = maximum_absolute_error(left, right)
        response_rows.append(
            {
                "dataset": f"{by_key[left_key]['basename']} vs {by_key[right_key]['basename']}",
                "division": "1_vs_2",
                "floor": "ALL",
                "method": "Original",
                "samples": EXPECTED_SAMPLES * 3,
                "response_shape": "40961x3",
                "time_start_s": 0.0,
                "time_end_s": STOP_TIME_S,
                "max_dt_error_s": 0.0,
                "finite": True,
                "peak_abs_mm": float(np.max(np.abs(left))),
                "rms_mm": float(np.sqrt(np.mean(left**2))),
                "final_mm": float(left[-1, -1]),
                "comparison_max_abs_error_mm": error,
                "criterion": "Original route division-invariant max_abs<=1e-12 mm",
                "result": "PASS" if error <= 1.0e-12 else "FAIL",
            }
        )

    matrix_csv = output_root / "matrix_checks.csv"
    response_csv = output_root / "response_checks.csv"
    atomic_write_table(matrix_csv, matrix_rows)
    atomic_write_table(response_csv, response_rows)
    response_failures = [row for row in response_rows if row["result"] != "PASS"]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not response_failures else "FAIL",
        "route": "Independent Python continuous state space + fixed-step classical RK4",
        "simulink_response_columns_read": False,
        "simulink_called": False,
        "force_equation": "M*qdd + C*qd + K*q = +f_projection*u(t)",
        "force_sign": FORCE_SIGN,
        "force_sign_evidence": {
            "Original": "frozen SLX SID4384 positive diag(horizontal_mask.*MRrt)",
            "Guyan": "frozen SLX SID4386 positive T'*Mf",
            "Craig-Bampton": "frozen SLX SID4398 positive T_cb'*Mf",
            "state_input": "regenerate_chapter3_data.m second_order_ss B=[0;M\\I]",
        },
        "interpolation_contract": {
            "unit_step": "From Workspace Interpolate=off; zero-order hold; exact timestamp uses new sample",
            "chirp": "From Workspace Interpolate=on; piecewise linear values at each RK4 half/full stage",
            "elcentro": "EQ_intensity*ElCentroAccel; piecewise linear values at each RK4 half/full stage",
            "after_final_value": "hold final value",
        },
        "dt_s": DT,
        "stop_time_s": STOP_TIME_S,
        "samples": EXPECTED_SAMPLES,
        "method_order": list(METHOD_ORDER),
        "floor_order": list(FLOOR_ORDER),
        "inputs": serialize_resolved_inputs(resolved),
        "matrix_check_count": len(matrix_rows),
        "matrix_pass_count": sum(row["result"] == "PASS" for row in matrix_rows),
        "response_check_count": len(response_rows),
        "response_pass_count": sum(row["result"] == "PASS" for row in response_rows),
        "response_failures": response_failures,
        "uncertainties": uncertainties,
        "datasets": dataset_outputs,
        "check_files": {
            "matrix_checks": str(matrix_csv),
            "matrix_checks_sha256": sha256(matrix_csv),
            "response_checks": str(response_csv),
            "response_checks_sha256": sha256(response_csv),
        },
    }
    atomic_write_json(output_root / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 2


def self_test() -> int:
    time_s = np.arange(11, dtype=float) * 0.1
    constant = WorkspaceSignal(time_s, np.ones_like(time_s), True, "constant")
    unit_mass = build_state_space(
        "self_test_qdd_equals_one",
        np.asarray([[1.0]]),
        np.asarray([[0.0]]),
        np.asarray([[0.0]]),
        np.asarray([1.0]),
        np.asarray([[1.0], [1.0], [1.0]]),
    )
    response = integrate_rk4(unit_mass, time_s, constant)
    expected_final_mm = 500.0
    acceleration_error = float(np.max(np.abs(response[-1, :] - expected_final_mm)))

    sample_time = np.asarray([0.0, 1.0, 2.0])
    sample_value = np.asarray([0.0, 10.0, 20.0])
    linear = WorkspaceSignal(sample_time, sample_value, True, "linear")
    zoh = WorkspaceSignal(sample_time, sample_value, False, "zoh")
    interpolation_checks = {
        "linear_half": float(linear.sample(np.asarray([0.5]))[0]),
        "linear_hold_after": float(linear.sample(np.asarray([3.0]))[0]),
        "zoh_half": float(zoh.sample(np.asarray([0.5]))[0]),
        "zoh_exact_new_timestamp": float(zoh.sample(np.asarray([1.0]))[0]),
        "zoh_hold_after": float(zoh.sample(np.asarray([3.0]))[0]),
    }
    passed = (
        acceleration_error <= 1.0e-10
        and interpolation_checks
        == {
            "linear_half": 5.0,
            "linear_hold_after": 20.0,
            "zoh_half": 0.0,
            "zoh_exact_new_timestamp": 10.0,
            "zoh_hold_after": 20.0,
        }
    )
    result = {
        "status": "PASS" if passed else "FAIL",
        "writes_performed": False,
        "qdd_equals_one_final_error_mm": acceleration_error,
        "interpolation_checks": interpolation_checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 2


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="板块18完整/Guyan/CB独立连续状态空间RK4复算"
    )
    parser.add_argument("--self-test", action="store_true", help="不读写工程文件的小样本自测")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="只核对冻结输入、矩阵、投影与恢复，不积分、不写输出",
    )
    parser.add_argument("--input-root", default=str(DEFAULT_INPUT_ROOT))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--reference-mat")
    parser.add_argument("--global-routes-mat")
    parser.add_argument("--pd-script")
    parser.add_argument("--generator")
    parser.add_argument("--eq-mat")
    parser.add_argument("--workspace-contract")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    return run_full(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # 保留完整错误类型，供外部命令日志捕获非零退出码。
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
