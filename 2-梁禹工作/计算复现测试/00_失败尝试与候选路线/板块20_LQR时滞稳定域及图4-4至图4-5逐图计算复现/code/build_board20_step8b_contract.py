# -*- coding: utf-8 -*-
"""建立图4-4/图4-5的论文—代码—矩阵合同，并执行第8B步自检。

本脚本只整理与核验来源，不计算稳定域，不读取论文曲线作为数值输入。
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
from scipy.linalg import eigh
from scipy.io import loadmat, savemat


BOARD20 = Path(__file__).resolve().parent.parent
PROJECT = BOARD20.parents[2]
BOARD17 = PROJECT / "test" / "00_失败尝试与候选路线" / "板块17_两类划分与缩聚候选路线"
OUT = BOARD20 / "outputs" / "step8b_论文代码矩阵合同"
STEP8A = BOARD20 / "outputs" / "step8a_全盘源资产检索"
CODE_ROOT = BOARD20 / "outputs" / "mlx_code" / "historical_stability_route" / "稳定域"
GLOBAL_MAT = BOARD17 / "outputs" / "global_routes_matlab.mat"
LOCAL_MAT = BOARD17 / "outputs" / "local_pd_reductions.mat"
KEY_INPUTS = STEP8A / "步骤8后续关键输入哈希清单.csv"
THESIS = PROJECT.parent / "梁禹手稿.pdf"
WORKSPACE_DIV1 = (BOARD20 / "outputs" / "step2_runs" / "main_ori_div1" /
                  "original_mlx" / "rep03" / "workspace" / "workspace_complete.mat")
WORKSPACE_DIV2 = (BOARD20 / "outputs" / "step2_runs" / "main_ori_div2" /
                  "original_mlx" / "rep03" / "workspace" / "workspace_complete.mat")
WORKSPACE_GUYAN_DIV1 = (BOARD20 / "outputs" / "step2_runs" / "main_guyan_div1" /
                        "original_mlx" / "rep03" / "workspace" / "workspace_complete.mat")
WORKSPACE_GUYAN_DIV2 = (BOARD20 / "outputs" / "step2_runs" / "main_guyan_div2" /
                        "original_mlx" / "rep03" / "workspace" / "workspace_complete.mat")
WORKSPACE_HASHES = {
    WORKSPACE_DIV1: "E0FFF9B1B0CFF5DB7013FE888D8A5957D3AC8776952EA40446109FE5A1C35923",
    WORKSPACE_DIV2: "7781807F01B9D95CA9554F3AE5449065C4DEB4C2FF8FFC62679E08BEC8757061",
    WORKSPACE_GUYAN_DIV1: "2CE61CAC0828B9D7DF1151B456A559D051CF6C48C60714756CCFABE03E392FD7",
    WORKSPACE_GUYAN_DIV2: "5B677B11EDCEC3AA7EE4955BE7B46ADB3F1BC7957BD7A7673456AE3F24476F21",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def array_sha256(a: np.ndarray) -> str:
    x = np.ascontiguousarray(np.asarray(a, dtype="<f8"))
    return hashlib.sha256(x.tobytes(order="C")).hexdigest().upper()


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_mat_deterministic(path: Path, payload: dict[str, np.ndarray]) -> None:
    """写MAT v5并固定含当前时间的说明头，保证相同数组逐字节复跑一致。"""
    savemat(path, payload, do_compression=True, oned_as="column")
    fixed = b"MATLAB 5.0 MAT-file, Board20 Step8B deterministic contract matrices"
    header = fixed.ljust(116, b" ")[:116]
    with path.open("r+b") as fh:
        fh.seek(0)
        fh.write(header)


def read_key_inputs() -> dict[str, dict[str, str]]:
    with KEY_INPUTS.open("r", encoding="utf-8-sig", newline="") as fh:
        return {row["角色"]: row for row in csv.DictReader(fh)}


def rel_asymmetry(a: np.ndarray) -> float:
    den = max(float(np.linalg.norm(a, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(a - a.T, ord="fro") / den)


def condense_single_sided(m: np.ndarray, c: np.ndarray, k: np.ndarray,
                          master: list[int], slave: list[int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ksm = k[np.ix_(slave, master)]
    kss = k[np.ix_(slave, slave)]
    relation = np.linalg.solve(kss, ksm)
    def one(a: np.ndarray) -> np.ndarray:
        return a[np.ix_(master, master)] - a[np.ix_(master, slave)] @ relation
    return one(m), one(c), one(k)


def h5_array(path: Path, name: str) -> np.ndarray:
    """读取MATLAB v7.3数组并恢复MATLAB行列方向。"""
    with h5py.File(path, "r") as fh:
        value = np.asarray(fh[name])
    return np.asarray(value.T, dtype=float)


def build_combined_reductions(full: dict[str, np.ndarray], master: list[int],
                              slave: list[int]) -> dict[str, Any]:
    """在一个来源明确的15维全模型上建立单边Guyan、标准Guyan与3模态CB。"""
    order = master + slave
    ordered = {s: full[s][np.ix_(order, order)] for s in ("M", "C", "K")}
    n_master = len(master)
    ksm = ordered["K"][n_master:, :n_master]
    kss = ordered["K"][n_master:, n_master:]
    static = -np.linalg.solve(kss, ksm)
    t = np.vstack((np.eye(n_master), static))

    historical = {}
    projected = {}
    for symbol in ("M", "C", "K"):
        a = ordered[symbol]
        historical[symbol] = a[:n_master, :n_master] + a[:n_master, n_master:] @ static
        projected[symbol] = t.T @ a @ t

    vals, phi = eigh(ordered["K"][n_master:, n_master:],
                     ordered["M"][n_master:, n_master:], check_finite=True)
    idx = np.argsort(vals.real)
    phi = np.asarray(phi[:, idx[:3]], float)
    # 固定每列最大绝对值分量为正，消除特征向量符号的不确定性。
    for col in range(phi.shape[1]):
        pivot = int(np.argmax(np.abs(phi[:, col])))
        if phi[pivot, col] < 0:
            phi[:, col] *= -1.0
    t_cb = np.block([[np.eye(n_master), np.zeros((n_master, 3))],
                     [static, phi]])
    cb = {s: t_cb.T @ ordered[s] @ t_cb for s in ("M", "C", "K")}

    r_guyan = np.zeros((15, n_master))
    r_cb = np.zeros((15, n_master + 3))
    r_guyan[order, :] = t
    r_cb[order, :] = t_cb
    return {
        "order": np.asarray(order, dtype=int), "ordered": ordered,
        "historical": historical, "projected": projected, "cb": cb,
        "R_guyan": r_guyan, "R_cb": r_cb,
        "T": t, "T_cb": t_cb, "fixed_interface_eigenvalues": vals[idx[:3]],
    }


def build_local_two_channel(full: dict[str, np.ndarray], master: list[int]) -> dict[str, Any]:
    slave = [i for i in range(full["M"].shape[0]) if i not in master]
    order = master + slave
    ordered = {s: full[s][np.ix_(order, order)] for s in ("M", "C", "K")}
    ksm = ordered["K"][len(master):, :len(master)]
    kss = ordered["K"][len(master):, len(master):]
    static = -np.linalg.solve(kss, ksm)
    t = np.vstack((np.eye(len(master)), static))
    historical = {s: ordered[s][:len(master), :len(master)] + ordered[s][:len(master), len(master):] @ static
                  for s in ("M", "C", "K")}
    projected = {s: t.T @ ordered[s] @ t for s in ("M", "C", "K")}
    return {"historical": historical, "projected": projected, "T": t,
            "order": np.asarray(order, dtype=int)}


def contract_pdf_rows() -> list[dict[str, Any]]:
    raw = [
        ("dt", 70, 60, "图4-4/图4-5后正文", "采样时间dt=1/1024 s；坐标是采样时间倍数", "1/1024 s=0.9765625 ms", "SPECIFIED", "图轴显示整数步，不得把1格精确写成1 ms"),
        ("integer_delay", 57, 47, "式(4-2)", "tau=n*Delta t，n属于正整数；延迟为z^(-n)", "整数步时滞", "SPECIFIED", "论文理论不含n=0；若源码从0开始必须列为冲突"),
        ("cr_alpha", 65, 55, "式(4-24)", "加速度项含标量alpha，但附近及全文没有数值定义", "MISSING", "NOT_CLOSED", "不可把源码矩阵al当成论文标量alpha"),
        ("source_newmark_alpha", 65, 55, "论文外部代码补全", "两套后缀上游Newmark依赖均保存alpha=0.25、delta=0.5", "alpha=0.25", "SOURCE_COMPLETION_ONLY", "可以作为有限候选输入，但不得写成论文已给数值"),
        ("delay_block", 65, 55, "式(4-25)", "时滞左乘整个C2/K2界面反馈括号", "H(z)[sC2+K2]", "SPECIFIED", "实现为局部通道H左乘"),
        ("H_definition", 66, 56, "式(4-26)后正文", "H(z)=diag(z^(-j),z^(-i))", "2×2对角时滞矩阵", "SPECIFIED", "j/i与图轴仍需源码绑定"),
        ("H_orientation", 66, 56, "式(4-27)、(4-28)", "论文只写H左乘C2/K2块，没有右乘H", "LEFT", "SPECIFIED", "右乘H的作者脚本属于冲突历史路线"),
        ("delayed_terms", 63, 54, "式(4-18)、(4-21)", "仅C2、K2受作动器动态误差影响", "C2和K2", "SPECIFIED", "M、C1、K1不得进入H"),
        ("division1_channels", 69, 59, "4.5节正文", "第一类主自由度psi1、psi6，两个受控自由度各有独立时滞", "psi1/psi6", "SPECIFIED", "两通道都进入H"),
        ("division2_channels", 69, 59, "4.5节正文", "第二类主自由度psi1、psi6、psi11；psi1/psi6有时滞，psi11无时滞", "delay(psi1,psi6); no_delay(psi11)", "SPECIFIED", "第二类不能改成延迟psi1/psi11"),
        ("lqr_equation", 68, 58, "式(4-31)", "xdot=A x+B u", "连续时间状态空间", "SYMBOLIC_ONLY", "A/B数值与输入单位未给全"),
        ("lqr_objective", 68, 58, "式(4-32)", "0到无穷的连续时间二次性能指标", "continuous infinite horizon", "SPECIFIED", "不能用离散性能指标冒充"),
        ("lqr_Q", 68, 58, "式(4-32)后正文", "Q前两项修正位移、后两项修正速度", "diag(1e6,1e6,1e4,1e4)", "SPECIFIED", "状态顺序[q1,q2,qdot1,qdot2]"),
        ("lqr_R", 68, 58, "式(4-32)后正文", "两输入权重", "diag(1e-2,1e-2)", "SPECIFIED", "两作动器"),
        ("lqr_solver", 68, 58, "式(4-33)", "连续代数Riccati方程", "CARE", "SPECIFIED", "不得用DARE/dlqr替代后仍称论文原式"),
        ("lqr_gain", 68, 58, "式(4-34)、(4-35)", "K=R^-1 B^T P；u=-Kx", "连续时间状态反馈", "SPECIFIED", "输入语义与单位仍未闭合"),
        ("lqr_partition", 68, 59, "式(4-38)至(4-40)", "K_qdot与K_q分别修正速度和位移", "s*K_qdot+K_q", "SPECIFIED", "s=(z-1)/(z*dt)"),
        ("lqr_delay_placement", 69, 59, "式(4-38)至(4-40)", "H[C2/K2]+[K_qdot/K_q]", "OUTSIDE_H", "SPECIFIED_FORMULA_TEXT_CONFLICT", "公式明确在H外；正文信号路径未解释"),
        ("division1_lqr", 70, 60, "4.4.2、4.5、图4-4", "同章明确选用LQR并随后绘制第一类稳定域", "YES", "SPECIFIED", "图4-4完整复现应包含LQR"),
        ("division2_lqr", 70, 60, "4.4.2、4.5、图4-5", "章节语义指向LQR闭环，但三主自由度如何映射到四维状态未说明", "YES_BUT_MAPPING_MISSING", "NOT_CLOSED", "不得臆造psi11状态/反馈映射"),
        ("stability_metric", 66, 56, "式(4-29)", "主导闭环极点为全部极点的最大模", "rho=max(abs(poles))", "SPECIFIED", "不是最大实部"),
        ("stability_class", 66, 56, "式(4-29)后正文", "rho<1稳定，rho=1临界，rho>1失稳", "stable iff rho<1", "SPECIFIED", "等于1不得归入稳定"),
        ("axes", 70, 60, "图4-4、图4-5", "横轴tau1、纵轴tau2，单位为采样步数", "x=tau1; y=tau2", "SPECIFIED", "j/i到横纵轴仍须源码裁决"),
        ("grid_shape", 70, 60, "图4-4、图4-5", "PDF未给循环上限、31×67尺寸或数组下标约定", "MISSING", "NOT_CLOSED", "网格范围只能来自作者MAT/源码"),
        ("root_polynomial", 66, 56, "式(4-23)等", "根分解排版使用求和符号，和特征多项式逻辑冲突", "按特征方程直接求根", "TYPOGRAPHICAL_CONFLICT", "不得照抄求和根式"),
        ("K3_label", 64, 54, "式(4-18)、(4-20)", "式(4-20)右侧K2与前式K3标号不一致", "INTERNAL_CONFLICT", "TYPOGRAPHICAL_CONFLICT", "装配须回查源码"),
    ]
    return [dict(field_id=a, pdf_page=b, printed_page=c, equation_or_figure=d,
                 evidence=e, contract_value=f, status=g, reproduction_constraint=h)
            for a, b, c, d, e, f, g, h in raw]


def author_script_rows(key: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    specs = [
        ("图4-4", 1, "Original", "第一类原结构Live Script", "luxvjie_ori_LQR2.m", "15维完整模型", "仅l=0,j=0；循环被注释", "NONE", "无", "RIGHT", "psi1/psi6", "PARTIAL_SINGLE_POINT", "没有LQR，不能生成论文31×67网格"),
        ("图4-4", 1, "Guyan", "第一类Guyan Live Script", "luxvjie_guyan_LQR2.m", "5维历史单边Guyan", "l,j=0:20，21×21", "NONE", "无", "LEFT", "缩聚坐标1/2", "RUNNABLE_HISTORY", "主集合[1,6,4,9,11]，不是板块17第一类6维集合"),
        ("图4-4", 1, "Craig-Bampton", "第一类Craig-Bampton Live Script", "luxvjie_cb_LQR2.m", "8维CB候选", "l,j=0:20，21×21", "NONE", "无", "LEFT", "缩聚坐标1/2", "BROKEN", "在CB矩阵使用前引用未定义MRren/CRren/KRren；S仍为2×5"),
        ("图4-5", 2, "Original", "第二类原结构Live Script", "luxvjie_ori_LQR3.m", "实际为5维历史单边Guyan", "四段循环，共1517点", "c2d+dlqr", "Q=diag(1e6,1,1e5,1);R=diag(1e-1,1e-2)", "LEFT_FEEDBACK_OUTSIDE", "局部两通道", "RUNNABLE_MISIDENTIFIED", "文件名Original与矩阵身份冲突"),
        ("图4-5", 2, "Guyan", "第二类Guyan Live Script", "luxvjie_guyan_LQR3.m", "5维历史单边Guyan", "四段循环，共1517点", "c2d+dlqr", "Q=diag(1e6,1,1e5,1);R=diag(1e-1,1e-2)", "LEFT_FEEDBACK_OUTSIDE", "局部两通道", "RUNNABLE_HISTORY", "9维物理源只使用前6个坐标；第三组未进入"),
        ("图4-5", 2, "Craig-Bampton", "第二类Craig-Bampton Live Script", "luxvjie_cb_LQR3.m", "与第一类CB脚本字节相同的8维候选", "l,j=0:20，21×21", "NONE", "无", "LEFT", "缩聚坐标1/2", "BROKEN_DUPLICATE", "两份CB MLX字节相同，不能证明第二类独立链"),
    ]
    rows = []
    for fig, div, method, role, name, identity, grid, controller, weights, hpos, channels, status, issue in specs:
        source = CODE_ROOT / name
        source_text = source.read_text(encoding="utf-8")
        role_item = key[role]
        mlx_hash = role_item["SHA256"]
        rows.append({
            "figure": fig, "division": div, "method_label": method, "source_m": str(source),
            "source_m_sha256": sha256_file(source), "source_mlx_sha256": mlx_hash,
            "active_matrix_identity": identity, "grid_or_loop": grid,
            "controller": controller, "weights": weights, "H_and_feedback": hpos,
            "delay_channels": channels, "execution_identity": status, "blocking_issue": issue,
            "token_checks": json.dumps({
                "has_dt": "1/1024" in source_text,
                "has_solve": "solve(det_G == 0" in source_text,
                "has_dlqr": "dlqr(" in source_text,
                "has_feedback_outside": ")+S'*DeltaG*S" in source_text,
            }, ensure_ascii=False, sort_keys=True),
        })
    return rows


def matrix_rows_and_payload() -> tuple[
        list[dict[str, Any]], dict[str, np.ndarray], dict[str, Any],
        list[dict[str, Any]], list[dict[str, Any]]]:
    board17_global = loadmat(GLOBAL_MAT, squeeze_me=True, struct_as_record=False)
    board17_local = loadmat(LOCAL_MAT, squeeze_me=True, struct_as_record=False)
    board17_full = {s: np.asarray(board17_global[{"M": "MRrt", "C": "CRrt", "K": "KRrt"}[s]], float)
                    for s in ("M", "C", "K")}

    source_workspaces = {1: WORKSPACE_DIV1, 2: WORKSPACE_DIV2}
    author_workspaces = {1: WORKSPACE_GUYAN_DIV1, 2: WORKSPACE_GUYAN_DIV2}
    source_full: dict[int, dict[str, np.ndarray]] = {}
    source_local: dict[int, dict[str, np.ndarray]] = {}
    for division, path in source_workspaces.items():
        source_full[division] = {s: h5_array(path, {"M": "MRrt", "C": "CRrt", "K": "KRrt"}[s])
                                 for s in ("M", "C", "K")}
        source_local[division] = {s: h5_array(path, {"M": "MPrt", "C": "CPrt", "K": "KPrt"}[s])
                                  for s in ("M", "C", "K")}

    division_contracts = {
        1: {"master": [0, 5, 10, 3, 8, 13], "slave": [1, 2, 4, 6, 7, 9, 11, 12, 14]},
        2: {"master": [0, 10, 3, 8, 13], "slave": [5, 1, 2, 4, 6, 7, 9, 11, 12, 14]},
    }
    built = {d: build_combined_reductions(source_full[d], **division_contracts[d]) for d in (1, 2)}

    rows: list[dict[str, Any]] = []
    payload: dict[str, np.ndarray] = {}
    comparisons: list[dict[str, Any]] = []
    embeddings: list[dict[str, Any]] = []

    def add_matrix_set(division: int, method: str, variant: str, matrices: dict[str, np.ndarray],
                       source_fields: str, selected: bool) -> None:
        n = matrices["M"].shape[0]
        method_key = method.replace("-", "_")
        for symbol in ("M", "C", "K"):
            a = np.asarray(matrices[symbol], float)
            rows.append({
                "division": division, "source_model": f"figure4-{division+3}_suffix{division+1}",
                "method": method, "variant": variant, "symbol": symbol,
                "shape": f"{a.shape[0]}x{a.shape[1]}", "finite": bool(np.isfinite(a).all()),
                "relative_asymmetry": f"{rel_asymmetry(a):.17g}",
                "array_sha256_float64_c": array_sha256(a), "source_fields": source_fields,
                "selected_for_step8c": selected,
            })
            payload[f"div{division}_{method_key}_{variant}_{symbol}"] = a
        assert n in (5, 6, 8, 9, 15)

    for division in (1, 2):
        full = source_full[division]
        route = built[division]
        workspace_name = source_workspaces[division].as_posix()
        n_master = len(division_contracts[division]["master"])
        k_ordered = route["ordered"]["K"]
        static_residual = (np.linalg.norm(k_ordered[n_master:, n_master:] @ route["T"][n_master:, :]
                                          + k_ordered[n_master:, :n_master], ord="fro") /
                           max(np.linalg.norm(k_ordered[n_master:, :n_master], ord="fro"), np.finfo(float).eps))
        payload[f"div{division}_static_constraint_relative_residual"] = np.asarray([[static_residual]])
        payload[f"div{division}_fixed_interface_frequency_hz"] = (
            np.sqrt(np.maximum(np.asarray(route["fixed_interface_eigenvalues"], float), 0.0)) / (2.0 * np.pi)
        ).reshape(-1, 1)
        add_matrix_set(division, "Original", "source_full15", full,
                       f"{workspace_name}:MRrt/CRrt/KRrt", True)
        add_matrix_set(division, "Guyan", "source_historical_single_sided", route["historical"],
                       f"{workspace_name}+division{division} master/slave:single-sided", True)
        add_matrix_set(division, "Guyan", "source_standard_congruence", route["projected"],
                       f"{workspace_name}+division{division} master/slave:T'AT", True)
        add_matrix_set(division, "Craig-Bampton", "source_sorted_three_modes", route["cb"],
                       f"{workspace_name}+division{division} master/slave:eigh sorted first3", True)

        recoveries = {"Original": np.eye(15), "Guyan": route["R_guyan"],
                      "Craig-Bampton": route["R_cb"]}
        for method, recovery in recoveries.items():
            method_key = method.replace("-", "_")
            selector = recovery[[0, 5], :]
            payload[f"div{division}_{method_key}_recovery_natural"] = recovery
            payload[f"div{division}_{method_key}_delay_selector_psi1_psi6"] = selector
            assert selector.shape[0] == 2
            if division == 1 and method != "Original":
                expected = np.zeros_like(selector)
                expected[0, 0] = 1.0
                expected[1, 1] = 1.0
                assert np.max(np.abs(selector - expected)) < 1e-11
            if division == 2 and method != "Original":
                assert np.count_nonzero(np.abs(selector[1]) > 1e-12) > 1
            embeddings.append({
                "division": division, "method": method,
                "recovery_shape": f"{recovery.shape[0]}x{recovery.shape[1]}",
                "delay_selector_shape": f"{selector.shape[0]}x{selector.shape[1]}",
                "psi1_row": json.dumps(selector[0].tolist(), ensure_ascii=False),
                "psi6_row": json.dumps(selector[1].tolist(), ensure_ascii=False),
                "psi6_is_dense": bool(np.count_nonzero(np.abs(selector[1]) > 1e-12) > 1),
                "left_delay_formula": "S' diag(z^-l,z^-j) [v(z)Cp+Kp] S",
                "right_delay_formula": "仅第一类Original历史候选保留 [v(z)C2+K2] H",
                "status": "PASS",
            })

        p = source_local[division]["M"].shape[0]
        global_local_dofs = [0, 1, 2, 5, 6, 7] if division == 1 else [0, 1, 2, 5, 6, 7, 10, 11, 12]
        e = np.eye(15)[:, global_local_dofs]
        j = np.eye(p)[[0, 3], :]
        payload[f"div{division}_local_embedding_E"] = e
        payload[f"div{division}_local_delay_selection_J_psi1_psi6"] = j
        for symbol, a in source_local[division].items():
            payload[f"div{division}_local_full_{symbol}"] = a
        local_two = build_local_two_channel(source_local[division], [0, 3])
        for variant in ("historical", "projected"):
            for symbol, a in local_two[variant].items():
                payload[f"div{division}_local_psi1_psi6_{variant}_{symbol}"] = a
        for symbol, source_name in (("M", "MPren"), ("C", "CPren"), ("K", "KPren")):
            payload[f"div{division}_author_final_local2_{symbol}"] = h5_array(author_workspaces[division], source_name)
        payload[f"div{division}_source_alpha_newmark"] = h5_array(source_workspaces[division], "alpha")
        payload[f"div{division}_source_delta_newmark"] = h5_array(source_workspaces[division], "delta")
        payload[f"div{division}_source_dt"] = h5_array(source_workspaces[division], "dt")

    # 量化板块17与两套稳定域上游模型的身份。第一类应相同；第二类后缀3必须保持为不同模型。
    for division in (1, 2):
        local_ref = board17_local["pd2" if division == 1 else "pd3"]
        for scope, source, reference, variables in (
            ("global", source_full[division], board17_full, ("M", "C", "K")),
            ("local", source_local[division],
             {s: np.asarray(getattr(local_ref, {"M": "MPrt", "C": "CPrt", "K": "KPrt"}[s]), float)
              for s in ("M", "C", "K")}, ("M", "C", "K")),
        ):
            for symbol in variables:
                a, b = source[symbol], reference[symbol]
                rel = float(np.linalg.norm(a - b, ord="fro") / max(np.linalg.norm(b, ord="fro"), np.finfo(float).eps))
                comparisons.append({
                    "division": division, "scope": scope, "symbol": symbol,
                    "source_shape": f"{a.shape[0]}x{a.shape[1]}",
                    "board17_shape": f"{b.shape[0]}x{b.shape[1]}",
                    "relative_frobenius_difference": f"{rel:.17g}",
                    "max_absolute_difference": f"{float(np.max(np.abs(a-b))):.17g}",
                    "same_numeric_model": rel <= 1e-12,
                    "adjudication": ("图4-4后缀2与板块17同一数值模型" if division == 1 else
                                     "图4-5必须使用后缀3源模型；不得复用板块17后缀2数值"),
                })

    dimensions = {
        "division1": {"Original": 15, "Guyan": 6, "Craig-Bampton": 9},
        "division2": {"Original": 15, "Guyan": 5, "Craig-Bampton": 8},
        "local_division1": {"full": 6, "two_channel": 2},
        "local_division2": {"full": 9, "two_channel": 2},
    }
    return rows, payload, dimensions, comparisons, embeddings


def conflict_rows() -> list[dict[str, str]]:
    data = [
        ("C01", "LQR求解器", "论文CARE", "作者主LQR3为c2d+dlqr", "分开计算；禁止互相改名"),
        ("C02", "LQR权重", "论文Q=[1e6,1e6,1e4,1e4],R=[1e-2,1e-2]", "作者Q=[1e6,1,1e5,1],R=[1e-1,1e-2]", "整套保留，不逐项拼接"),
        ("C03", "CR参数", "论文标量alpha缺失", "上游Newmark依赖给alpha=0.25；稳定域活动式另用矩阵al", "alpha=0.25与矩阵al分别建立来源补全路线，均不得倒写为论文已明确"),
        ("C04", "H乘法方向", "论文H左乘", "第一类Original脚本右乘H", "论文合同用左乘；右乘作为历史冲突候选"),
        ("C05", "LQR与H位置", "论文公式反馈在H外", "主LQR3反馈在H外；小论文在H内", "硕士论文复现只采用H外"),
        ("C06", "第一类LQR", "论文要求LQR闭环", "三份第一类源没有活动LQR", "作者逐文件路线无法形成图4-4完整链"),
        ("C07", "第二类Original身份", "目标应为15维完整模型", "ori_LQR3实际为5维Guyan", "不能按文件名认领Original"),
        ("C08", "第二类延迟自由度", "论文延迟psi1/psi6，psi11无时滞", "板块17第二类psi6为从坐标；小论文延迟psi1/psi11", "用恢复矩阵构造psi1/psi6选择行；不改成psi1/psi11"),
        ("C09", "Guyan公式", "通用理论为T'AT", "作者历史为单边消元", "标准与历史各成完整候选，不混用M/C/K"),
        ("C10", "CB脚本身份", "两类应为独立9维/8维链", "两份CB MLX字节相同且均含未定义MRren", "作者CB链判为缺失；板块17矩阵只可作透明重建"),
        ("C11", "网格与轴", "PDF不给31×67与j/i轴映射", "MAT为31×67；绘图x=列,y=行；计算写stab(l+1,j+1)", "计算保存原矩阵；验收同时检查原向与转置，不以命中选参数"),
        ("C12", "零时滞", "论文n属于正整数", "作者循环从0开始且MAT含首行首列", "历史网格保留0步；报告与论文理论差异"),
        ("C13", "图4-4/图4-5全模型身份", "两图对应两类划分", "后缀2与板块17相同；后缀3质量/阻尼显著不同", "图4-4绑定后缀2；图4-5绑定后缀3，并各自在自身全模型上重建缩聚"),
        ("C14", "第二类局部物理坐标", "论文延迟psi1/psi6", "pd3作者主坐标[1,7]实际为psi1/psi11", "论文路线用完整9维局部矩阵和J=[e1;e4]投影；pd3.MRren不得冒充psi1/psi6"),
    ]
    return [dict(conflict_id=a, subject=b, thesis_or_theory=c, author_or_other=d, adjudication=e,
                 status="CONFLICT_RECORDED") for a, b, c, d, e in data]


def candidate_rows() -> list[dict[str, Any]]:
    rows = [
        ("T00_论文原义", "论文原义", "论文符号矩阵", "CARE", "论文Q/R", "论文标量alpha", "H左乘；反馈H外", "psi1/psi6", False,
         "CR alpha、数值A/B及输入单位、第二类三主自由度到四维状态映射未闭合"),
        ("H00_作者六脚本逐文件", "作者历史", "按各MLX逐文件", "第一类无LQR；第二类DARE", "作者Q/R", "作者矩阵al", "按各文件", "按各文件", False,
         "第一类Original仅单点；两份CB相同且报错；第二类Original实际为Guyan，不能形成六条目标链"),
        ("R01_论文CARE_alpha025_广义力", "来源补全重建", "后缀2/3各自Original15；标准Guyan6/5；排序CB9/8", "连续CARE，B=[0;M^-1]，反馈力增益直接嵌入", "论文Q/R", "标量alpha=0.25（上游Newmark来源）", "H左乘；反馈H外", "完整局部模型投影后的psi1/psi6", True,
         "B的广义力语义与alpha数值是显式来源补全，不是论文自包含参数"),
        ("R02_论文CARE_alpha025_加速度", "来源补全重建", "后缀2/3各自Original15；标准Guyan6/5；排序CB9/8", "连续CARE，B=[0;I]，乘局部M换算为力反馈", "论文Q/R", "标量alpha=0.25（上游Newmark来源）", "H左乘；反馈H外", "完整局部模型投影后的psi1/psi6", True,
         "加速度输入语义由作者DeltaK=M*K模式补全，论文未明确"),
        ("R03_论文CARE_矩阵al_广义力", "来源补全重建", "后缀2/3各自Original15；标准Guyan6/5；排序CB9/8", "连续CARE，B=[0;M^-1]，反馈力增益直接嵌入", "论文Q/R", "每条路线按自身M/C/K重算未对角化矩阵al", "H左乘；反馈H外", "完整局部模型投影后的psi1/psi6", True,
         "控制器遵循论文，积分质量项遵循作者活动代码；禁止复用作者5×5 al"),
        ("R04_论文CARE_矩阵al_加速度", "来源补全重建", "后缀2/3各自Original15；标准Guyan6/5；排序CB9/8", "连续CARE，B=[0;I]，乘局部M换算为力反馈", "论文Q/R", "每条路线按自身M/C/K重算未对角化矩阵al", "H左乘；反馈H外", "完整局部模型投影后的psi1/psi6", True,
         "输入语义与积分矩阵均显式标注来源；禁止复用作者5×5 al"),
        ("R05_作者DARE规则外推", "来源补全重建", "后缀2/3各自Original15；历史单边Guyan6/5；排序CB9/8", "ZOH+c2d+dlqr，B=[0;M^-1]，再乘局部M", "作者Q/R", "作者最终未对角化矩阵al", "Original右乘H；Guyan/CB左乘H；反馈H外", "恢复后的psi1/psi6", True,
         "作者B=[0;M^-1]后又乘M形成Delta，输入单位重复；只作历史诊断，不作公式有效候选"),
        ("R06_作者无LQR规则外推", "来源补全重建", "后缀2/3各自Original15；历史单边Guyan6/5；排序CB9/8", "无LQR", "不适用", "作者最终未对角化矩阵al", "Original右乘H；Guyan/CB左乘H", "恢复后的psi1/psi6", True,
         "对应第一类源的无LQR结构，但与论文4.4.2的LQR要求冲突"),
    ]
    result = []
    for a, b, c, d, e, f, g, h, i, j in rows:
        if a.startswith(("R01_", "R02_", "R03_", "R04_")):
            validity = "FORMULA_COHERENT_SOURCE_COMPLETION"
        elif a.startswith(("R05_", "R06_")):
            validity = "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID"
        elif a.startswith("T00_"):
            validity = "THESIS_LITERAL_BLOCKED"
        else:
            validity = "AUTHOR_SIX_CHAIN_INCOMPLETE"
        result.append(dict(candidate_id=a, evidence_label=b, base_matrices=c, controller=d, weights=e,
                           integration_parameter=f, delay_and_feedback=g, delayed_coordinates=h,
                           executable_in_step8c=i, formula_validity=validity, limitation=j,
                           selection_rule="全部有限候选均计算；不得按论文曲线先验挑选"))
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    key = read_key_inputs()
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, actual: Any, expected: Any) -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL",
                       "actual": actual, "expected": expected})

    for role, item in key.items():
        path = Path(item["绝对路径"])
        actual = sha256_file(path) if path.exists() else "MISSING"
        check(f"HASH_{role}", path.exists() and actual == item["SHA256"], actual, item["SHA256"])
    check("THESIS_PATH", THESIS.resolve() == Path(key["硕士论文"]["绝对路径"]).resolve(), str(THESIS), key["硕士论文"]["绝对路径"])
    for path, expected_hash in WORKSPACE_HASHES.items():
        actual_hash = sha256_file(path) if path.exists() else "MISSING"
        check(f"WORKSPACE_HASH_{path.parents[3].name}", path.exists() and actual_hash == expected_hash,
              actual_hash, expected_hash)

    pdf_rows = contract_pdf_rows()
    author_rows = author_script_rows(key)
    matrix_rows, matrix_payload, dimensions, model_comparisons, delay_embeddings = matrix_rows_and_payload()
    conflicts = conflict_rows()
    candidates = candidate_rows()
    quality_rows: list[dict[str, Any]] = []
    for division in (1, 2):
        residual = float(np.ravel(matrix_payload[f"div{division}_static_constraint_relative_residual"])[0])
        for method, variant in (("Original", "source_full15"),
                                ("Guyan", "source_standard_congruence"),
                                ("Craig_Bampton", "source_sorted_three_modes")):
            m = matrix_payload[f"div{division}_{method}_{variant}_M"]
            k = matrix_payload[f"div{division}_{method}_{variant}_K"]
            recovery = matrix_payload[f"div{division}_{method}_recovery_natural"]
            min_m = float(np.min(np.linalg.eigvalsh((m + m.T) / 2.0)))
            min_k = float(np.min(np.linalg.eigvalsh((k + k.T) / 2.0)))
            quality_rows.append({
                "division": division, "method": method.replace("_", "-"),
                "matrix_order": m.shape[0], "recovery_rank": int(np.linalg.matrix_rank(recovery)),
                "min_eigenvalue_M": f"{min_m:.17g}", "min_eigenvalue_K": f"{min_k:.17g}",
                "static_constraint_relative_residual": f"{residual:.17g}",
                "status": "PASS" if min_m > 0 and min_k > 0 and np.linalg.matrix_rank(recovery) == m.shape[0]
                                      and residual <= 1e-12 else "FAIL",
            })

    check("PDF_REQUIRED_FIELDS", len(pdf_rows) >= 20, len(pdf_rows), ">=20")
    check("SIX_AUTHOR_SCRIPTS", len(author_rows) == 6, len(author_rows), 6)
    check("SIX_TARGET_DIMENSIONS",
          dimensions["division1"] == {"Original": 15, "Guyan": 6, "Craig-Bampton": 9}
          and dimensions["division2"] == {"Original": 15, "Guyan": 5, "Craig-Bampton": 8},
          dimensions, "div1=15/6/9; div2=15/5/8")
    check("DELAY_SELECTORS_PRESENT",
          sum(k.endswith("delay_selector_psi1_psi6") for k in matrix_payload) == 6,
          sum(k.endswith("delay_selector_psi1_psi6") for k in matrix_payload), 6)
    div1_diffs = [float(r["relative_frobenius_difference"]) for r in model_comparisons if r["division"] == 1]
    div2_global_m = next(float(r["relative_frobenius_difference"]) for r in model_comparisons
                         if r["division"] == 2 and r["scope"] == "global" and r["symbol"] == "M")
    check("DIV1_SOURCE_EQUALS_BOARD17", max(div1_diffs) == 0.0, max(div1_diffs), 0.0)
    check("DIV2_SOURCE_DIFFERS_BOARD17", abs(div2_global_m - 0.4736842105263158) < 1e-14,
          div2_global_m, 0.4736842105263158)
    check("SOURCE_ALPHA_025", all(abs(float(np.ravel(matrix_payload[f"div{d}_source_alpha_newmark"])[0]) - 0.25) < 1e-15 for d in (1, 2)),
          [float(np.ravel(matrix_payload[f"div{d}_source_alpha_newmark"])[0]) for d in (1, 2)], [0.25, 0.25])
    check("SIX_REBUILT_ROUTES_POSITIVE_DEFINITE_FULL_RANK",
          len(quality_rows) == 6 and all(r["status"] == "PASS" for r in quality_rows),
          [r["status"] for r in quality_rows], ["PASS"] * 6)
    check("CB_MLX_BYTE_IDENTICAL",
          key["第一类Craig-Bampton Live Script"]["SHA256"] == key["第二类Craig-Bampton Live Script"]["SHA256"],
          key["第一类Craig-Bampton Live Script"]["SHA256"], "same hash")
    check("LITERAL_CONTRACT_BLOCKED", candidates[0]["executable_in_step8c"] is False,
          candidates[0]["executable_in_step8c"], False)
    check("FINITE_SOURCE_COMPLETIONS", sum(bool(r["executable_in_step8c"]) for r in candidates) == 6,
          sum(bool(r["executable_in_step8c"]) for r in candidates), 6)
    check("FORMULA_VALID_VS_DIAGNOSTIC_SEPARATED",
          sum(r["formula_validity"] == "FORMULA_COHERENT_SOURCE_COMPLETION" for r in candidates) == 4
          and sum(r["formula_validity"] == "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID" for r in candidates) == 2,
          {"formula_coherent": sum(r["formula_validity"] == "FORMULA_COHERENT_SOURCE_COMPLETION" for r in candidates),
           "historical_diagnostic": sum(r["formula_validity"] == "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID" for r in candidates)},
          {"formula_coherent": 4, "historical_diagnostic": 2})
    candidate_blob = json.dumps(candidates, ensure_ascii=False, sort_keys=True)
    forbidden_pdf_targets = ("64/59/58", "57/51/48", "paper_boundary", "pdf_boundary")
    check("NO_PDF_NUMERIC_INPUT", not any(token in candidate_blob for token in forbidden_pdf_targets),
          "candidate definitions contain no paper boundary values or boundary fields",
          "no PDF curve coordinate used")
    check("NO_SILENT_CARE_DARE_MIX", all(not ("CARE" in r["controller"] and "dlqr" in r["controller"]) for r in candidates),
          "candidate controller definitions inspected", "CARE and dlqr kept separate")

    write_csv(OUT / "论文逐字段合同.csv", pdf_rows,
              ["field_id", "pdf_page", "printed_page", "equation_or_figure", "evidence", "contract_value", "status", "reproduction_constraint"])
    write_csv(OUT / "作者六脚本执行身份.csv", author_rows,
              ["figure", "division", "method_label", "source_m", "source_m_sha256", "source_mlx_sha256", "active_matrix_identity", "grid_or_loop", "controller", "weights", "H_and_feedback", "delay_channels", "execution_identity", "blocking_issue", "token_checks"])
    write_csv(OUT / "基础矩阵合同.csv", matrix_rows,
              ["division", "source_model", "method", "variant", "symbol", "shape", "finite", "relative_asymmetry", "array_sha256_float64_c", "source_fields", "selected_for_step8c"])
    write_csv(OUT / "两套上游模型与板块17数值身份比较.csv", model_comparisons,
              ["division", "scope", "symbol", "source_shape", "board17_shape", "relative_frobenius_difference", "max_absolute_difference", "same_numeric_model", "adjudication"])
    write_csv(OUT / "六路线延迟选择与恢复合同.csv", delay_embeddings,
              ["division", "method", "recovery_shape", "delay_selector_shape", "psi1_row", "psi6_row", "psi6_is_dense", "left_delay_formula", "right_delay_formula", "status"])
    write_csv(OUT / "六路线重建质量门禁.csv", quality_rows,
              ["division", "method", "matrix_order", "recovery_rank", "min_eigenvalue_M", "min_eigenvalue_K", "static_constraint_relative_residual", "status"])
    write_csv(OUT / "合同冲突与裁决.csv", conflicts,
              ["conflict_id", "subject", "thesis_or_theory", "author_or_other", "adjudication", "status"])
    write_csv(OUT / "有限候选整链清单.csv", candidates,
              ["candidate_id", "evidence_label", "base_matrices", "controller", "weights", "integration_parameter", "delay_and_feedback", "delayed_coordinates", "executable_in_step8c", "formula_validity", "limitation", "selection_rule"])
    write_mat_deterministic(OUT / "步骤8B_基础矩阵与选择矩阵.mat", matrix_payload)

    fail_count = sum(r["status"] == "FAIL" for r in checks)
    write_csv(OUT / "步骤8B验收检查.csv", checks, ["check_id", "status", "actual", "expected"])
    summary = {
        "schema": "board20.step8b.contract.v2",
        "gate_status": "PASS_CONTRACTS_SEPARATED" if fail_count == 0 else "FAIL",
        "check_count": len(checks), "pass_count": len(checks) - fail_count, "fail_count": fail_count,
        "thesis_literal_executable": False,
        "author_six_script_chain_complete": False,
        "source_completed_candidate_count": sum(bool(r["executable_in_step8c"]) for r in candidates),
        "formula_coherent_candidate_count": sum(r["formula_validity"] == "FORMULA_COHERENT_SOURCE_COMPLETION" for r in candidates),
        "historical_diagnostic_candidate_count": sum(r["formula_validity"] == "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID" for r in candidates),
        "dimensions": dimensions,
        "model_identity": "图4-4绑定后缀2；图4-5绑定后缀3。后缀2与板块17逐元素相同，后缀3必须在自身模型上重建第二类缩聚。",
        "scientific_conclusion": "论文原义合同和作者逐文件合同均不足以直接生成六条目标曲线；已建立4条公式自洽来源补全候选及2条历史诊断，均不使用论文曲线调参。",
        "hard_boundary": "PDF曲线只用于步骤8F逐点验收，禁止作为矩阵、控制器、alpha或候选选择输入。",
    }
    write_json(OUT / "步骤8B合同摘要.json", summary)

    readme = "# 步骤8B：论文—代码—矩阵合同\n\n"
    readme += "本目录把图4-4和图4-5的论文公式、作者六份Live Script、两套后缀源模型与板块17已核验划分分开绑定。论文曲线坐标没有进入任何计算候选。\n\n"
    readme += "## 结论\n\n"
    readme += "- 论文原义路线不能直接计算：CR标量alpha、数值A/B与输入单位、第二类三主自由度到四维LQR状态的映射没有闭合。\n"
    readme += "- 作者六脚本也不是六条完整计算链：第一类没有LQR，第一类Original只有单点，两份CB脚本字节相同且引用未定义矩阵，第二类Original实际进入5维Guyan。\n"
    readme += "- 图4-4使用后缀2源模型；它与板块17全局及局部矩阵逐元素相同。图4-5使用后缀3源模型；其质量和阻尼与板块17显著不同，已在后缀3自身矩阵上重建第二类5/8维缩聚。\n"
    readme += "- 为继续穷尽复现，固定了4条公式自洽来源补全候选和2条历史诊断；每条都一次性固定矩阵、控制器、Q/R、积分参数、H位置和两通道恢复规则，后续全部计算，不以是否命中论文曲线筛选。\n"
    readme += "- 作者DARE规则存在广义力输入后再次乘质量的单位重复，无LQR规则也不满足论文LQR合同；两者只作历史敏感性诊断，不进入论文公式有效候选判定。\n\n"
    readme += "## 验收\n\n"
    readme += f"- 自动检查：{len(checks)-fail_count}/{len(checks)} PASS，{fail_count} FAIL。\n"
    readme += "- 维数：第一类Original/Guyan/CB=15/6/9；第二类=15/5/8。\n"
    readme += "- 第二类psi6虽然是缩聚从坐标，仍通过板块17恢复矩阵形成延迟选择行，没有被替换成psi11。\n"
    readme += "- 科学状态：`PASS_CONTRACTS_SEPARATED`仅表示合同已分开、输入已冻结，不表示六条论文曲线已复现。\n"
    (OUT / "README_步骤8B合同说明.md").write_text(readme, encoding="utf-8")

    artifacts = []
    for path in sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "步骤8B工件清单.csv"):
        artifacts.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv(OUT / "步骤8B工件清单.csv", artifacts, ["filename", "bytes", "sha256"])

    if fail_count:
        raise SystemExit(f"步骤8B失败：{fail_count}项检查未通过")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
