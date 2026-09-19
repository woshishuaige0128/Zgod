from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import stat
import subprocess
import sys
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import h5py
import numpy as np
from scipy import linalg
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
TEST_ROOT = PROJECT_ROOT / "test"
INPUT_ROOT = BOARD_ROOT / "outputs" / "s4i"
COMPUTE_ROOT = BOARD_ROOT / "outputs" / "s4"
ORCHESTRATION_ROOT = BOARD_ROOT / "outputs" / "s4o"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "s4v"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"

INPUT_MANIFEST_SHA256 = "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
INPUT_FREEZE_SUMMARY_SHA256 = "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
ANCHORS = {
    "outputs/step2_static_inventory/inventory_summary.json": "C587F4FA80E56512C7734D545A20BE483EADC5E09B5707A6D241ACBADE2A7D1C",
    "outputs/step2_validation/checks.csv": "0207D7AAFC16BDCAC4298E387668DAABB143300F92927FDD4C6CABDBEDA13EF9",
    "outputs/step2_validation/step2_artifact_manifest.csv": "4BCD18ADB8321123ACFF53E30C0B5F02D5ED05C16181E7BAA829743831C5B9F9",
    "outputs/step2_determinism/determinism_audit.json": "9CD0C07D7956E4CC5F0ECC1956EAD54A21B9DD2AD3371F769DA6ED1D06CEED38",
    "report/板块21_最小步骤2_公式与历史脚本静态审计.md": "7E642186B735E73B13547D10073AEE4B66146A7157860C1157F120165406B2DF",
    "outputs/step3_stage/stage_summary.json": "F0F44C7C7128D2AC6DF88BFD5C0FF9367211B95DBF54EC32C145CB167986D238",
    "outputs/step3_stage/run_configs.csv": "D70D2D6F20C77BA6C709A7AED3BD2CE46B60165F8AB9516C15E2979F3AD87BFF",
    "outputs/step3_stage/staged_input_manifest.csv": "6DEA6F89A367C4684D34FECA7EC8F5D28CF606BA753830B9AEB0E403382B94EE",
    "outputs/step3_orchestration/run_all_summary.json": "03A2FA963E685259C0692733D536231C60B5FD1FFB514BDC297980377619DA44",
    "outputs/step3_validation/checks.csv": "1E0A0D715809A06B3E33BD2A73EAA8471D157B53F1277DD6D0C8F4D7DCC28236",
    "outputs/step3_validation/route_results.csv": "007CED89C2E109F0095E375808FC4547759AB0F9537ED54D955B734ADBB6DAC6",
    "outputs/step3_validation/repeat_comparison.csv": "230886D9378816E0B7BB14B7DB489A2C536F4EE82025E18EC7DA67F13188D48D",
    "outputs/step3_validation/validation_summary.json": "09CCF3FF1C1EA8E45C4B0FF30ADF1827FAB4F5AC966C3A680302E64F76EBB897",
}
EXPECTED_TOOL_NAMES = {
    "stage_board21_step4_inputs.py",
    "compute_board21_step4_formulas.py",
    "compute_board21_step4_formulas.m",
    "run_board21_step4_all.py",
    "validate_board21_step4.py",
}
FORMAL_OBJECT_NAMES = {
    "表4-1_两类划分Guyan与Craig--Bampton能量变化率",
    "结论C06_能量变化率稳定风险阈值",
}
VALUE_KEY_FIELDS = (
    "case_id", "scope", "coordinate_identity", "route_variant",
    "result_identity", "excitation_identity", "recovery_identity", "mode_count",
    "model", "quantity", "row", "column",
)
RESULT_KEY_FIELDS = (
    "case_id", "scope", "coordinate_identity", "route_variant",
    "result_identity", "excitation_identity", "recovery_identity", "mode_count",
    "comparison_model",
)


ROUTES: dict[str, dict[str, Any]] = {
    "r01": {
        "route_id": "reference15_pd19_energy",
        "full_M": "MRrt", "full_K": "KRrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer": [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15],
        "producer": [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15],
        "d": [1, 2, 3], "excitation": "BINARY_FIRST_3",
        "normalize": True, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "ORIGINAL",
    },
    "r02": {
        "route_id": "division1_pd19_copy",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer": [1, 4, 2, 3, 5, 6], "producer": [1, 4, 2, 3, 5, 6],
        "d": [1, 2], "excitation": "BINARY_FIRST_2",
        "normalize": True, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "ORIGINAL",
    },
    "r03": {
        "route_id": "division1_tp17_energy",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer": [1, 4, 2, 3, 5, 6], "producer": [1, 4, 2, 3, 5, 6],
        "d": [1, 2], "excitation": "MASS_TIMES_ONES",
        "normalize": True, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "ORIGINAL",
    },
    "r04": {
        "route_id": "division1_tp17_copy2_formula_invalid",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer": [1, 4, 2, 3, 5, 6], "producer": [1, 4, 2, 3, 5, 6],
        "d": [1, 2], "excitation": "MASS_TIMES_ONES",
        "normalize": False, "scopes": ("ALL", "ALL", "ALL"), "denominator": "GUYAN",
    },
    "r05": {
        "route_id": "division2_pd19_copy",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer": [1, 7, 4, 2, 3, 5, 6, 8, 9], "producer": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        "d": [1, 2], "excitation": "BINARY_FIRST_3",
        "normalize": True, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "ORIGINAL",
    },
    "r06": {
        "route_id": "division2_tp17_energy_coordinate_conflict",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer": [1, 7, 4, 2, 3, 5, 6, 8, 9], "producer": [1, 7, 2, 3, 4, 5, 6, 8, 9],
        "d": [1, 2], "excitation": "BINARY_FIRST_3",
        "normalize": True, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "ORIGINAL",
    },
    "r07": {
        "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer": [1, 7, 4, 2, 3, 5, 6, 8, 9], "producer": [1, 7, 2, 3, 4, 5, 6, 8, 9],
        "d": [1, 2], "excitation": "BINARY_FIRST_3",
        "normalize": False, "scopes": ("SELECTED", "ALL", "SELECTED"), "denominator": "GUYAN",
    },
}


@dataclass(frozen=True)
class Modal:
    eigenvalue: np.ndarray
    phi: np.ndarray
    gamma: np.ndarray
    participation: np.ndarray
    energy_total: np.ndarray


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def utf16_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def write_csv_new(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def read_hdf5(path: Path, names: Iterable[str]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as handle:
        for name in names:
            if name not in handle or not isinstance(handle[name], h5py.Dataset):
                raise KeyError(f"missing {name} in {path}")
            value = np.asarray(handle[name])
            if value.ndim >= 2:
                value = value.transpose(tuple(reversed(range(value.ndim))))
            value = np.asarray(value, dtype=np.float64).squeeze()
            if np.iscomplexobj(value) or not np.all(np.isfinite(value)):
                raise ValueError(f"invalid {name} in {path}")
            result[name] = value
    return result


def canonical_modes(M: np.ndarray, phi: np.ndarray) -> np.ndarray:
    result = np.asarray(phi, dtype=np.float64).copy()
    for index in range(result.shape[1]):
        modal_mass = float(result[:, index].T @ M @ result[:, index])
        if modal_mass <= 0.0:
            raise ValueError("non-positive modal mass")
        result[:, index] /= math.sqrt(modal_mass)
        pivot = int(np.argmax(np.abs(result[:, index])))
        if result[pivot, index] < 0.0:
            result[:, index] *= -1.0
    return result


def third_eigensystem(M: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    M = np.asarray(M, dtype=np.float64)
    K = np.asarray(K, dtype=np.float64)
    if M.ndim != 2 or M.shape[0] != M.shape[1] or K.shape != M.shape:
        raise ValueError("third solver matrix size mismatch")
    if np.linalg.norm(M - M.T, ord="fro") > 1e-10 * max(1.0, np.linalg.norm(M, ord="fro")):
        raise ValueError("third solver M symmetry gate failed")
    if np.linalg.norm(K - K.T, ord="fro") > 1e-10 * max(1.0, np.linalg.norm(K, ord="fro")):
        raise ValueError("third solver K symmetry gate failed")
    L = np.linalg.cholesky(M)
    left = linalg.solve_triangular(L, K, lower=True, check_finite=True)
    standard = linalg.solve_triangular(L, left.T, lower=True, check_finite=True).T
    if np.linalg.norm(standard - standard.T, ord="fro") > 1e-10 * max(1.0, np.linalg.norm(standard, ord="fro")):
        raise ValueError("Cholesky-transformed eigenproblem is not symmetric")
    eigenvalue, y = np.linalg.eigh(standard)
    order = np.argsort(eigenvalue, kind="stable")
    eigenvalue = eigenvalue[order]
    y = y[:, order]
    if np.any(eigenvalue <= 0.0):
        raise ValueError("third solver non-positive eigenvalue")
    phi = linalg.solve_triangular(L.T, y, lower=False, check_finite=True)
    phi = canonical_modes(M, phi)
    residual = np.linalg.norm(K @ phi - M @ phi @ np.diag(eigenvalue), ord="fro")
    if residual / max(1.0, np.linalg.norm(K @ phi, ord="fro")) > 1e-10:
        raise ValueError("third solver eigen residual gate failed")
    return eigenvalue, phi


def third_modal_from_basis(
    M: np.ndarray, K: np.ndarray, r: np.ndarray,
    eigenvalue: np.ndarray, phi: np.ndarray, mode_count: int,
    normalize_energy: bool = True,
) -> Modal:
    count = eigenvalue.size if mode_count == -1 else mode_count
    if count < 1 or count > eigenvalue.size:
        raise ValueError("third solver invalid mode count")
    eigenvalue = np.asarray(eigenvalue[:count], dtype=np.float64)
    phi = canonical_modes(M, phi[:, :count])
    r = np.asarray(r, dtype=np.float64).reshape(-1)
    numerator = phi.T @ M @ r
    denominator = np.einsum("ij,ij->j", phi, M @ phi)
    gamma = numerator / denominator
    gamma_sq = gamma**2
    participation = gamma_sq / np.sum(gamma_sq)
    energy_raw = 0.5 * np.diag(M)[:, None] * phi**2 * eigenvalue[None, :]
    energy_normalized = energy_raw / np.sum(energy_raw, axis=0)[None, :]
    energy = energy_normalized if normalize_energy else energy_raw
    total = energy @ participation
    if not np.all(np.isfinite(total)):
        raise ValueError("third solver non-finite energy")
    return Modal(eigenvalue, phi, gamma, participation, total)


def third_modal(
    M: np.ndarray, K: np.ndarray, r: np.ndarray,
    mode_count: int = -1, normalize_energy: bool = True,
) -> Modal:
    eigenvalue, phi = third_eigensystem(M, K)
    return third_modal_from_basis(M, K, r, eigenvalue, phi, mode_count, normalize_energy)


def author_vectors(spec: dict[str, Any], raw_M: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = raw_M.shape[0]
    if spec["excitation"] == "BINARY_FIRST_3":
        literal = np.zeros(n); literal[:3] = 1.0; direction = literal.copy()
    elif spec["excitation"] == "BINARY_FIRST_2":
        literal = np.zeros(n); literal[:2] = 1.0; direction = literal.copy()
    elif spec["excitation"] == "MASS_TIMES_ONES":
        direction = np.ones(n); literal = raw_M @ direction
    else:
        raise ValueError("unknown hard-coded excitation")
    return literal, direction


def selected_sum(values: np.ndarray, indices: list[int], scope: str) -> float:
    vector = np.asarray(values).reshape(-1)
    return float(np.sum(vector)) if scope == "ALL" else float(np.sum(vector[np.asarray(indices)-1]))


def equation445(
    original: np.ndarray, reduced: np.ndarray, d_original: list[int], d_reduced: list[int]
) -> tuple[float, str]:
    original = np.asarray(original).reshape(-1)
    reduced = np.asarray(reduced).reshape(-1)
    oi = np.asarray(d_original) - 1
    ri = np.asarray(d_reduced) - 1
    denominator = original[oi]
    if np.any(denominator == 0.0):
        return 0.0, "UNDEFINED_DENOMINATOR"
    total = float(np.sum((reduced[ri] - denominator) / denominator))
    status = "ILL_CONDITIONED" if np.any(np.abs(denominator) <= 1e-14) else "FINITE"
    return total, status


def key_of(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row[field] for field in fields)


def unique_map(rows: list[dict[str, str]], fields: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = key_of(row, fields)
        if key in result:
            raise ValueError(f"duplicate canonical key: {key}")
        result[key] = row
    return result


def tolerance(a: float, b: float, quantity: str) -> float:
    if quantity == "frequency_hz":
        return max(1e-9, 1e-10 + 1e-10 * max(abs(a), abs(b)))
    return 1e-10 + 1e-10 * max(abs(a), abs(b))


def add_check(checks: list[dict[str, Any]], check_id: str, category: str, passed: bool, detail: str) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def verify_direct_freeze() -> tuple[int, dict[str, int]]:
    if sha256_file(INPUT_MANIFEST) != INPUT_MANIFEST_SHA256:
        raise RuntimeError("Step1 input manifest hash mismatch")
    if sha256_file(INPUT_FREEZE_SUMMARY) != INPUT_FREEZE_SUMMARY_SHA256:
        raise RuntimeError("Step1 input summary hash mismatch")
    rows = read_csv(INPUT_MANIFEST)
    if len(rows) != 53:
        raise RuntimeError("Step1 direct input count mismatch")
    categories = Counter(row["category"] for row in rows)
    for row in rows:
        source = Path(row["source_absolute_path"])
        frozen = BOARD_ROOT / "input" / PurePosixPath(row["frozen_relative_path"])
        expected = row["source_sha256"]
        if (
            not source.is_file() or not frozen.is_file()
            or source.stat().st_size != int(row["source_size_bytes"])
            or frozen.stat().st_size != int(row["frozen_size_bytes"])
            or sha256_file(source) != expected or sha256_file(frozen) != expected
            or row["frozen_sha256"] != expected or row["status"] != "MATCH"
        ):
            raise RuntimeError(f"Step1 protected source mismatch: {row['item_id']}")
    return len(rows), dict(categories)


def verify_step4_stage() -> tuple[list[dict[str, str]], dict[str, str]]:
    stage = json.loads((INPUT_ROOT / "staging_summary.json").read_text(encoding="utf-8"))
    if (
        stage.get("status") != "PASS" or stage.get("step3_evidence_item_count") != 98
        or stage.get("board17_external_candidate_item_count") != 5
        or stage.get("total_manifest_item_count") != 103
        or stage.get("global_asset_directly_frozen_by_board21_step1") is not False
    ):
        raise RuntimeError("Step4 staging summary contract mismatch")
    manifest = read_csv(INPUT_ROOT / "input_manifest.csv")
    if len(manifest) != 103 or len({row["item_id"] for row in manifest}) != 103:
        raise RuntimeError("Step4 input manifest cardinality/uniqueness mismatch")
    for row in manifest:
        source = Path(row["source_absolute_path"])
        staged = INPUT_ROOT / PurePosixPath(row["staged_relative_path"])
        if (
            not source.is_file() or not staged.is_file() or is_reparse(source) or is_reparse(staged)
            or source.stat().st_size != int(row["size_bytes"])
            or staged.stat().st_size != int(row["size_bytes"])
            or sha256_file(source) != row["sha256"] or sha256_file(staged) != row["sha256"]
            or row["status"] != "MATCH"
        ):
            raise RuntimeError(f"Step4 staged input mismatch: {row['item_id']}")
    case_rows = read_csv(INPUT_ROOT / "case_index.csv")
    if len(case_rows) != 14 or len({row["case_id"] for row in case_rows}) != 14:
        raise RuntimeError("Step4 case index mismatch")
    case_dirs: dict[str, str] = {}
    for row in case_rows:
        alias = row["route_alias"]
        if alias not in ROUTES or row["route_id"] != ROUTES[alias]["route_id"]:
            raise RuntimeError(f"hard-coded route identity mismatch: {row['case_id']}")
        case = json.loads((INPUT_ROOT / row["staged_relative_dir"] / "case.json").read_text(encoding="utf-8"))
        spec = ROUTES[alias]
        expected_contract = {
            "full_M": spec["full_M"], "full_K": spec["full_K"],
            "guyan_M": spec["guyan_M"], "guyan_K": spec["guyan_K"], "guyan_T": spec["guyan_T"],
            "cb_M": spec["cb_M"], "cb_K": spec["cb_K"], "cb_T": spec["cb_T"],
        }
        if any(case.get(key) != value for key, value in expected_contract.items()):
            raise RuntimeError(f"case contract differs from validator hard-code: {row['case_id']}")
        if case.get("consumer_order") != spec["consumer"] or case.get("producer_order") != spec["producer"]:
            raise RuntimeError(f"case coordinate contract mismatch: {row['case_id']}")
        case_dirs[row["case_id"]] = row["staged_relative_dir"]
    return manifest, case_dirs


def load_local_system(case_id: str, case_dirs: dict[str, str], cache: dict[str, Any]) -> dict[str, Any]:
    if case_id in cache:
        return cache[case_id]
    alias = case_id.split("_", 1)[0]
    spec = ROUTES[alias]
    names = {
        spec["full_M"], spec["full_K"], spec["guyan_M"], spec["guyan_K"], spec["guyan_T"],
        spec["cb_M"], spec["cb_K"], spec["cb_T"],
    }
    root = INPUT_ROOT / case_dirs[case_id]
    data = read_hdf5(root / "u.mat", names)
    raw_M = np.asarray(data[spec["full_M"]], dtype=np.float64)
    raw_K = np.asarray(data[spec["full_K"]], dtype=np.float64)
    result = {"spec": spec, "data": data, "raw_M": raw_M, "raw_K": raw_K}
    cache[case_id] = result
    return result


def load_whole_system(case_id: str, cache: dict[str, Any]) -> dict[str, Any]:
    if case_id in cache:
        return cache[case_id]
    division = int(case_id[-1])
    if "whole_mat" not in cache:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cache["whole_mat"] = loadmat(
                INPUT_ROOT / "g" / "gr.mat",
                variable_names=["division1", "division2"], squeeze_me=True,
                struct_as_record=False,
            )
    D = cache["whole_mat"][f"division{division}"]
    field = lambda name: np.asarray(getattr(D, name), dtype=np.float64)
    d = [1, 2, 3] if division == 1 else [1, 2]
    result = {
        "full_M": field("Mo"), "full_K": field("Ko"),
        "T": field("T"), "Tcb": field("T_cb"),
        "Mg": field("M_historical"), "Kg": field("K_historical"),
        "Mg_standard": field("M_projected"), "Kg_standard": field("K_projected"),
        "Mcb": field("M_cb"), "Kcb": field("K_cb"),
        "literal": field("force_mask_ordered").reshape(-1),
        "direction": field("force_mask_ordered").reshape(-1),
        "d": d,
    }
    cache[case_id] = result
    return result


def system_for_result(
    row: dict[str, str], case_dirs: dict[str, str], cache: dict[str, Any]
) -> dict[str, Any]:
    case_id = row["case_id"]
    if case_id.startswith("w"):
        base = load_whole_system(case_id, cache)
        full_M, full_K = base["full_M"], base["full_K"]
        literal, direction = base["literal"], base["direction"]
        T, Tcb = base["T"], base["Tcb"]
        Mg, Kg, Mcb, Kcb = base["Mg"], base["Kg"], base["Mcb"], base["Kcb"]
        d = base["d"]
    else:
        base = load_local_system(case_id, case_dirs, cache)
        spec, data = base["spec"], base["data"]
        order_values = spec["consumer"] if row["coordinate_identity"] == "AUTHOR_CONSUMER_ORDER" else spec["producer"]
        order = np.asarray(order_values) - 1
        full_M = base["raw_M"][np.ix_(order, order)]
        full_K = base["raw_K"][np.ix_(order, order)]
        literal, direction = author_vectors(spec, full_M)
        T = np.asarray(data[spec["guyan_T"]], dtype=np.float64)
        Tcb = np.asarray(data[spec["cb_T"]], dtype=np.float64)
        Mg = np.asarray(data[spec["guyan_M"]], dtype=np.float64)
        Kg = np.asarray(data[spec["guyan_K"]], dtype=np.float64)
        Mcb = np.asarray(data[spec["cb_M"]], dtype=np.float64)
        Kcb = np.asarray(data[spec["cb_K"]], dtype=np.float64)
        d = spec["d"]
    variant = row["route_variant"]
    if variant == "GUYAN_HISTORICAL_ONESIDED":
        model, transform, reduced_M, reduced_K = "guyan", T, Mg, Kg
    elif variant == "GUYAN_STANDARD_CONGRUENT":
        model, transform = "guyan", T
        reduced_M, reduced_K = T.T @ full_M @ T, T.T @ full_K @ T
    elif variant == "CB_SAVED_CONGRUENT":
        model, transform, reduced_M, reduced_K = "cb", Tcb, Mcb, Kcb
    else:
        raise ValueError(f"unknown paper route variant: {variant}")
    return {
        "full_M": full_M, "full_K": full_K,
        "literal": literal, "direction": direction,
        "model": model, "T": transform, "Mred": reduced_M, "Kred": reduced_K, "d": d,
    }


def third_paper_result(
    row: dict[str, str], case_dirs: dict[str, str], cache: dict[str, Any]
) -> tuple[float, str]:
    S = system_for_result(row, case_dirs, cache)
    excitation = row["excitation_identity"]
    if excitation == "AUTHOR_LITERAL":
        full_r = S["literal"]
        reduced_r = S["T"].T @ S["literal"]
    elif excitation == "FORCE_CONSISTENT_INFERENCE":
        full_r = S["direction"]
        force = S["T"].T @ S["full_M"] @ S["direction"]
        reduced_r = np.linalg.solve(S["Mred"], force)
    else:
        raise ValueError(f"unknown excitation identity: {excitation}")
    mode_count = int(row["mode_count"])
    full_eigenvalue, full_phi = third_eigensystem(S["full_M"], S["full_K"])
    reduced_eigenvalue, reduced_phi = third_eigensystem(S["Mred"], S["Kred"])
    original = third_modal_from_basis(
        S["full_M"], S["full_K"], full_r, full_eigenvalue, full_phi, mode_count, True
    )
    reduced = third_modal_from_basis(
        S["Mred"], S["Kred"], reduced_r,
        reduced_eigenvalue, reduced_phi, mode_count, True,
    )
    recovery = row["recovery_identity"]
    if recovery.endswith("PHYSICAL_RECOVERY_INFERENCE"):
        physical_phi = S["T"] @ reduced.phi
        physical = third_modal_from_basis(
            S["full_M"], S["full_K"], full_r,
            reduced.eigenvalue, physical_phi, reduced.eigenvalue.size, True,
        )
        return equation445(original.energy_total, physical.energy_total, S["d"], S["d"])
    return equation445(original.energy_total, reduced.energy_total, S["d"], S["d"])


def third_historical_results(
    case_dirs: dict[str, str], cache: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for case_id in sorted(case_dirs):
        base = load_local_system(case_id, case_dirs, cache)
        spec, data = base["spec"], base["data"]
        order = np.asarray(spec["consumer"]) - 1
        full_M = base["raw_M"][np.ix_(order, order)]
        full_K = base["raw_K"][np.ix_(order, order)]
        literal, _ = author_vectors(spec, full_M)
        T = np.asarray(data[spec["guyan_T"]])
        Tcb = np.asarray(data[spec["cb_T"]])
        original = third_modal(full_M, full_K, literal, -1, spec["normalize"])
        guyan = third_modal(data[spec["guyan_M"]], data[spec["guyan_K"]], T.T @ literal, -1, spec["normalize"])
        cb = third_modal(data[spec["cb_M"]], data[spec["cb_K"]], Tcb.T @ literal, -1, spec["normalize"])
        scopes = spec["scopes"]
        sums = (
            selected_sum(original.energy_total, spec["d"], scopes[0]),
            selected_sum(guyan.energy_total, spec["d"], scopes[1]),
            selected_sum(cb.energy_total, spec["d"], scopes[2]),
        )
        denominator = sums[0] if spec["denominator"] == "ORIGINAL" else sums[1]
        totals = ((sums[1]-sums[0])/denominator*100.0, (sums[2]-sums[0])/denominator*100.0)
        output[(case_id, "guyan")] = {"total": totals[0], "modal": guyan}
        output[(case_id, "cb")] = {"total": totals[1], "modal": cb}
        output[(case_id, "orig")] = {"total": None, "modal": original}
    return output


def modal_groups(rows: list[dict[str, str]]) -> dict[tuple[str, ...], dict[tuple[int, int], float]]:
    result: dict[tuple[str, ...], dict[tuple[int, int], float]] = defaultdict(dict)
    for row in rows:
        if row["quantity"] != "phi_mass_normalized":
            continue
        key = tuple(row[field] for field in VALUE_KEY_FIELDS[:7]) + (row["model"],)
        result[key][(int(row["row"]), int(row["column"]))] = float(row["value"])
    return result


def modal_phase_factors(
    py_rows: list[dict[str, str]], matlab_rows: list[dict[str, str]]
) -> dict[tuple[tuple[str, ...], int], float]:
    py_groups = modal_groups(py_rows)
    matlab_groups = modal_groups(matlab_rows)
    if set(py_groups) != set(matlab_groups):
        raise RuntimeError("modal group key mismatch")
    factors: dict[tuple[tuple[str, ...], int], float] = {}
    for group in py_groups:
        if set(py_groups[group]) != set(matlab_groups[group]):
            raise RuntimeError(f"modal entry mismatch: {group}")
        columns = sorted({column for _, column in py_groups[group]})
        for column in columns:
            row_indices = sorted(row for row, col in py_groups[group] if col == column)
            dot = sum(
                py_groups[group][(row, column)] * matlab_groups[group][(row, column)]
                for row in row_indices
            )
            factors[(group, column)] = -1.0 if dot < 0.0 else 1.0
    return factors


def matrix_residual_contracts(cache: dict[str, Any]) -> dict[tuple[str, str, str], tuple[float, float]]:
    contracts: dict[tuple[str, str, str], tuple[float, float]] = {}
    eps = np.finfo(np.float64).eps
    for division in (1, 2):
        case_id = f"w0{division}"
        system = load_whole_system(case_id, cache)
        definitions = (
            ("guyan", "matrix_identity_M_standard_minus_TtMT", system["Mg_standard"], system["T"].T @ system["full_M"] @ system["T"]),
            ("guyan", "matrix_identity_K_standard_minus_TtKT", system["Kg_standard"], system["T"].T @ system["full_K"] @ system["T"]),
            ("cb", "matrix_identity_M_cb_minus_TtMT", system["Mcb"], system["Tcb"].T @ system["full_M"] @ system["Tcb"]),
            ("cb", "matrix_identity_K_cb_minus_TtKT", system["Kcb"], system["Tcb"].T @ system["full_K"] @ system["Tcb"]),
        )
        for model, quantity, saved, rebuilt in definitions:
            scale = max(1.0, float(np.linalg.norm(saved, ord="fro")), float(np.linalg.norm(rebuilt, ord="fro")))
            tolerance_value = 100.0 * saved.shape[0] * eps
            contracts[(case_id, model, quantity)] = (scale, tolerance_value)
    return contracts


def compare_cross_language(
    py_rows: list[dict[str, str]], matlab_rows: list[dict[str, str]],
    residual_contracts: dict[tuple[str, str, str], tuple[float, float]],
) -> tuple[list[dict[str, Any]], float, float]:
    py_map = unique_map(py_rows, VALUE_KEY_FIELDS)
    matlab_map = unique_map(matlab_rows, VALUE_KEY_FIELDS)
    if set(py_map) != set(matlab_map):
        missing_py = len(set(matlab_map) - set(py_map))
        missing_matlab = len(set(py_map) - set(matlab_map))
        raise RuntimeError(f"cross-language value key mismatch: py_missing={missing_py}, matlab_missing={missing_matlab}")
    phase_factors = modal_phase_factors(py_rows, matlab_rows)
    modal_dimensions = {
        group: max(row for row, _ in entries)
        for group, entries in modal_groups(py_rows).items()
    }
    residual_norm_sq: dict[tuple[str, ...], list[float]] = defaultdict(lambda: [0.0, 0.0])
    matrix_quantities = {key[2] for key in residual_contracts}
    for key in py_map:
        p = py_map[key]
        if p["quantity"] not in matrix_quantities:
            continue
        group = tuple(p[field] for field in VALUE_KEY_FIELDS[:-2])
        residual_norm_sq[group][0] += float(p["value"]) ** 2
        residual_norm_sq[group][1] += float(matlab_map[key]["value"]) ** 2

    rows: list[dict[str, Any]] = []
    max_abs = 0.0
    max_scaled = 0.0
    for order, key in enumerate(sorted(py_map), start=1):
        p = py_map[key]; m = matlab_map[key]
        a = float(p["value"]); b = float(m["value"])
        compared_b = b
        raw_error = abs(a-b)
        comparison_method = "DIRECT"
        alignment_sign = ""
        normalization_scale = 1.0
        quantity = p["quantity"]
        modal_group = tuple(p[field] for field in VALUE_KEY_FIELDS[:7]) + (p["model"],)
        if quantity == "phi_mass_normalized":
            factor = phase_factors[(modal_group, int(p["column"]))]
            compared_b = factor * b
            error = abs(a-compared_b)
            limit = tolerance(a, compared_b, quantity)
            comparison_method = "MODAL_COLUMN_PHASE_ALIGNED"
            alignment_sign = format(factor, ".0f")
        elif quantity in {"eq441_numerator", "eq441_gamma"}:
            factor = phase_factors[(modal_group, int(p["row"]))]
            compared_b = factor * b
            error = abs(a-compared_b)
            limit = tolerance(a, compared_b, quantity)
            comparison_method = "MODAL_PHASE_PROPAGATED"
            alignment_sign = format(factor, ".0f")
        elif quantity == "author_saved_energy_total_abs_error":
            companion_key = list(key)
            companion_key[VALUE_KEY_FIELDS.index("quantity")] = "author_saved_energy_total"
            companion = tuple(companion_key)
            normalization_scale = max(
                1.0, abs(float(py_map[companion]["value"])), abs(float(matlab_map[companion]["value"]))
            )
            error = max(abs(a), abs(b)) / normalization_scale
            limit = 64.0 * modal_dimensions[modal_group] * np.finfo(np.float64).eps
            comparison_method = "EACH_RESIDUAL_NORMALIZED_TO_SAVED_ENERGY"
        elif quantity in matrix_quantities:
            contract_key = (p["case_id"], p["model"], quantity)
            normalization_scale, limit = residual_contracts[contract_key]
            residual_group = tuple(p[field] for field in VALUE_KEY_FIELDS[:-2])
            norms = residual_norm_sq[residual_group]
            error = max(math.sqrt(norms[0]), math.sqrt(norms[1])) / normalization_scale
            comparison_method = "EACH_MATRIX_RESIDUAL_FROBENIUS_NORMALIZED"
        else:
            error = raw_error
            limit = tolerance(a, b, quantity)
        scaled = error / limit if limit > 0 else 0.0
        status_match = p["value_status"] == m["value_status"]
        flags_match = p["uncertainty_flags"] == m["uncertainty_flags"]
        passed = error <= limit and status_match and flags_match
        rows.append(
            {
                "comparison_order": order,
                "key": "|".join(key),
                "python_value": format(a, ".17g"),
                "matlab_value": format(b, ".17g"),
                "comparison_method": comparison_method,
                "alignment_sign": alignment_sign,
                "compared_matlab_value": format(compared_b, ".17g"),
                "raw_absolute_error": format(raw_error, ".17g"),
                "normalization_scale": format(normalization_scale, ".17g"),
                "absolute_error": format(error, ".17g"),
                "tolerance": format(limit, ".17g"),
                "scaled_error": format(scaled, ".17g"),
                "status_match": str(status_match).upper(),
                "flags_match": str(flags_match).upper(),
                "status": "PASS" if passed else "FAIL",
            }
        )
        max_abs = max(max_abs, error)
        max_scaled = max(max_scaled, scaled)
    return rows, max_abs, max_scaled


def compare_result_tables(
    py_rows: list[dict[str, str]], matlab_rows: list[dict[str, str]]
) -> tuple[int, float]:
    py_map = unique_map(py_rows, RESULT_KEY_FIELDS)
    matlab_map = unique_map(matlab_rows, RESULT_KEY_FIELDS)
    if set(py_map) != set(matlab_map):
        raise RuntimeError("cross-language case-result key mismatch")
    max_error = 0.0
    numeric_fields = ("eq445_sum", "historical_total_percent", "author_target_percent", "author_abs_error")
    for key in py_map:
        p, m = py_map[key], matlab_map[key]
        if p["eq445_status"] != m["eq445_status"] or p["boundary_status"] != m["boundary_status"]:
            raise RuntimeError(f"case-result status mismatch: {key}")
        for field in numeric_fields:
            if bool(p[field]) != bool(m[field]):
                raise RuntimeError(f"case-result blank/value mismatch: {key}/{field}")
            if p[field]:
                a, b = float(p[field]), float(m[field])
                error = abs(a-b)
                if error > 1e-10 + 1e-10*max(abs(a), abs(b)):
                    raise RuntimeError(f"case-result numeric mismatch: {key}/{field}: {error}")
                max_error = max(max_error, error)
    return len(py_map), max_error


def modal_mac_checks(py_rows: list[dict[str, str]], matlab_rows: list[dict[str, str]]) -> tuple[int, float]:
    pg, mg = modal_groups(py_rows), modal_groups(matlab_rows)
    if set(pg) != set(mg):
        raise RuntimeError("modal group key mismatch")
    maximum_one_minus_mac = 0.0
    count = 0
    for key in pg:
        indices = set(pg[key])
        if indices != set(mg[key]):
            raise RuntimeError(f"modal entry mismatch: {key}")
        nrow = max(index[0] for index in indices)
        ncol = max(index[1] for index in indices)
        P = np.zeros((nrow, ncol)); M = np.zeros((nrow, ncol))
        for index in indices:
            P[index[0]-1, index[1]-1] = pg[key][index]
            M[index[0]-1, index[1]-1] = mg[key][index]
        for column in range(ncol):
            numerator = abs(np.vdot(P[:, column], M[:, column]))**2
            denominator = float(np.vdot(P[:, column], P[:, column]).real * np.vdot(M[:, column], M[:, column]).real)
            mac = numerator / denominator
            maximum_one_minus_mac = max(maximum_one_minus_mac, abs(1.0-mac))
            count += 1
    return count, maximum_one_minus_mac


def target_process_count() -> int:
    board_token = str(BOARD_ROOT).replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw)\\.exe$' -and "
        "$_.CommandLine -like '*" + board_token + "*' -and "
        "$_.CommandLine -like '*compute_board21_step4_formulas*'} | "
        "Select-Object Name,ProcessId,CommandLine; $items | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("final process query failed")
    raw = completed.stdout.decode("utf-8-sig").strip()
    parsed: Any = [] if not raw else json.loads(raw)
    if isinstance(parsed, dict): parsed = [parsed]
    return sum(int(item.get("ProcessId", -1)) != os.getpid() for item in parsed)


def run_mutations(case_dirs: dict[str, str], cache: dict[str, Any]) -> list[dict[str, Any]]:
    base = load_local_system("r03_p1", case_dirs, cache)
    spec, data = base["spec"], base["data"]
    order = np.asarray(spec["consumer"])-1
    M = base["raw_M"][np.ix_(order, order)]
    K = base["raw_K"][np.ix_(order, order)]
    T = np.asarray(data[spec["guyan_T"]])
    Mg, Kg = np.asarray(data[spec["guyan_M"]]), np.asarray(data[spec["guyan_K"]])
    literal, direction = author_vectors(spec, M)
    original = third_modal(M, K, literal)
    guyan = third_modal(Mg, Kg, T.T @ literal)
    base_eq, _ = equation445(original.energy_total, guyan.energy_total, spec["d"], spec["d"])
    mutation_values: list[tuple[str, str, np.ndarray | float, np.ndarray | float]] = []
    no_mass_gamma = original.phi.T @ literal
    mutation_values.append(("M01_FORMULA_441", "formula.eq4_41.numerator", original.gamma, no_mass_gamma))
    swapped = list(reversed(spec["d"]))
    swapped_eq, _ = equation445(original.energy_total, guyan.energy_total, spec["d"], swapped)
    mutation_values.append(("M02_COORDINATE_MAP", "route.coordinate_mapping", base_eq, swapped_eq))
    orig_sum = selected_sum(original.energy_total, spec["d"], "SELECTED")
    g_sum = selected_sum(guyan.energy_total, spec["d"], "ALL")
    denominator_mutation = abs((g_sum-orig_sum)/g_sum*100 - (g_sum-orig_sum)/orig_sum*100)
    mutation_values.append(("M03_DENOMINATOR", "formula.denominator", 0.0, denominator_mutation))
    scope_mutation = abs(float(np.sum(original.energy_total))-orig_sum)
    mutation_values.append(("M04_SUM_SCOPE", "formula.sum_scope", 0.0, scope_mutation))
    guyan_raw = third_modal(Mg, Kg, T.T @ literal, -1, False)
    mutation_values.append(("M05_NORMALIZATION", "formula.energy_normalization", guyan.energy_total, guyan_raw.energy_total))
    mutation_values.append(("M06_PERCENT_SCALE", "formula.percent_scale", base_eq, base_eq*100))
    orig_m1 = third_modal(M, K, literal, 1, True)
    g_m1 = third_modal(Mg, Kg, T.T @ literal, 1, True)
    m1_eq, _ = equation445(orig_m1.energy_total, g_m1.energy_total, spec["d"], spec["d"])
    mutation_values.append(("M07_MODE_SET", "formula.mode_set", base_eq, m1_eq))
    direction_modal = third_modal(M, K, direction)
    mutation_values.append(("M08_EXCITATION_IDENTITY", "formula.excitation_identity", original.gamma, direction_modal.gamma))

    def numeric_contract_accepts(reference: np.ndarray | float, candidate: np.ndarray | float) -> bool:
        reference_array = np.asarray(reference, dtype=np.float64)
        candidate_array = np.asarray(candidate, dtype=np.float64)
        return (
            reference_array.shape == candidate_array.shape
            and np.all(np.isfinite(reference_array))
            and np.all(np.isfinite(candidate_array))
            and bool(np.allclose(reference_array, candidate_array, rtol=1e-12, atol=1e-12))
        )

    pristine_original = third_modal(M, K, literal)
    pristine_guyan = third_modal(Mg, Kg, T.T @ literal)
    pristine_eq, _ = equation445(pristine_original.energy_total, pristine_guyan.energy_total, spec["d"], spec["d"])
    pristine_recheck = (
        numeric_contract_accepts(original.energy_total, pristine_original.energy_total)
        and numeric_contract_accepts(guyan.energy_total, pristine_guyan.energy_total)
        and numeric_contract_accepts(base_eq, pristine_eq)
    )
    rows: list[dict[str, Any]] = []
    for order_number, (mutation_id, field, reference, candidate) in enumerate(mutation_values, start=1):
        delta = float(np.max(np.abs(np.asarray(candidate, dtype=np.float64)-np.asarray(reference, dtype=np.float64))))
        changed = math.isfinite(delta) and delta > 1e-12
        actual_rejection = not numeric_contract_accepts(reference, candidate)
        rows.append(
            {
                "mutation_order": order_number,
                "mutation_id": mutation_id,
                "expected_rejection_field": field,
                "numeric_delta": format(delta, ".17g"),
                "numeric_changed": str(changed).upper(),
                "contract_rejected": str(actual_rejection).upper(),
                "positive_contract_after": str(pristine_recheck).upper(),
                "status": "PASS" if changed and actual_rejection and pristine_recheck else "FAIL",
            }
        )
    return rows


def main() -> int:
    if VALIDATION_ROOT.exists():
        raise FileExistsError(f"exclusive validation output exists: {VALIDATION_ROOT}")
    VALIDATION_ROOT.mkdir(parents=True)
    checks: list[dict[str, Any]] = []
    cross_rows: list[dict[str, Any]] = []
    determinism_rows: list[dict[str, Any]] = []
    third_rows: list[dict[str, Any]] = []
    mutation_rows: list[dict[str, Any]] = []
    failure: Exception | None = None
    metrics: dict[str, Any] = {}
    try:
        direct_count, categories = verify_direct_freeze()
        add_check(checks, "S4-001", "source_protection", direct_count == 53, f"direct_count={direct_count}; categories={categories}")
        anchor_failures = []
        for relative, expected in ANCHORS.items():
            path = BOARD_ROOT / PurePosixPath(relative)
            if not path.is_file() or sha256_file(path) != expected:
                anchor_failures.append(relative)
        add_check(checks, "S4-002", "source_protection", not anchor_failures, f"anchor_failures={anchor_failures}")
        manifest, case_dirs = verify_step4_stage()
        add_check(checks, "S4-003", "staging", len(manifest) == 103, "98 Step3 evidence + 5 Board17 external candidates")

        run_summary = json.loads((ORCHESTRATION_ROOT / "run_all_summary.json").read_text(encoding="utf-8"))
        add_check(
            checks, "S4-004", "orchestration",
            run_summary.get("status") == "PASS" and run_summary.get("compute_success_count") == 4
            and run_summary.get("table4_1_adjudicated") is False,
            f"status={run_summary.get('status')}; success={run_summary.get('compute_success_count')}",
        )
        tool_rows = read_csv(ORCHESTRATION_ROOT / "tool_hashes.csv")
        tool_ok = {row["name"] for row in tool_rows} == EXPECTED_TOOL_NAMES and all(
            (SCRIPT.parent / row["name"]).is_file()
            and sha256_file(SCRIPT.parent / row["name"]) == row["sha256"]
            and row["status"] == "UNCHANGED" for row in tool_rows
        )
        add_check(checks, "S4-005", "instrument", tool_ok, f"tool_count={len(tool_rows)}")

        for implementation in ("py", "matlab"):
            for name in ("values.csv", "case_results.csv", "compute_summary.json", "output_manifest.csv"):
                a = COMPUTE_ROOT / "a" / implementation / name
                b = COMPUTE_ROOT / "b" / implementation / name
                match = a.is_file() and b.is_file() and a.stat().st_size == b.stat().st_size and sha256_file(a) == sha256_file(b)
                determinism_rows.append(
                    {
                        "implementation": implementation, "relative_path": name,
                        "a_sha256": sha256_file(a) if a.is_file() else "",
                        "b_sha256": sha256_file(b) if b.is_file() else "",
                        "byte_identical": str(match).upper(), "status": "PASS" if match else "FAIL",
                    }
                )
        add_check(checks, "S4-006", "determinism", all(row["status"] == "PASS" for row in determinism_rows), f"checks={len(determinism_rows)}")

        py_values = read_csv(COMPUTE_ROOT / "a" / "py" / "values.csv")
        matlab_values = read_csv(COMPUTE_ROOT / "a" / "matlab" / "values.csv")
        value_cardinality_ok = len(py_values) == 305382 and len(matlab_values) == 305382
        add_check(
            checks, "S4-007A", "cross_language_cardinality", value_cardinality_ok,
            f"python_values={len(py_values)}; matlab_values={len(matlab_values)}; expected_each=305382",
        )
        residual_contracts = matrix_residual_contracts({})
        cross_rows, max_cross_abs, max_cross_scaled = compare_cross_language(
            py_values, matlab_values, residual_contracts
        )
        cross_pass = all(row["status"] == "PASS" for row in cross_rows)
        add_check(checks, "S4-007", "cross_language", cross_pass, f"rows={len(cross_rows)}; max_abs={max_cross_abs:.17g}; max_scaled={max_cross_scaled:.17g}")
        py_results = read_csv(COMPUTE_ROOT / "a" / "py" / "case_results.csv")
        matlab_results = read_csv(COMPUTE_ROOT / "a" / "matlab" / "case_results.csv")
        py_scope_counts = Counter(row["scope"] for row in py_results)
        matlab_scope_counts = Counter(row["scope"] for row in matlab_results)
        result_cardinality_ok = (
            len(py_results) == 1096 and len(matlab_results) == 1096
            and py_scope_counts == {"HISTORICAL": 28, "PAPER": 1068}
            and matlab_scope_counts == {"HISTORICAL": 28, "PAPER": 1068}
        )
        add_check(
            checks, "S4-008A", "cross_language_cardinality", result_cardinality_ok,
            f"python_results={len(py_results)}; matlab_results={len(matlab_results)}; "
            f"python_scopes={dict(py_scope_counts)}; matlab_scopes={dict(matlab_scope_counts)}",
        )
        result_count, max_result_error = compare_result_tables(py_results, matlab_results)
        add_check(checks, "S4-008", "cross_language", True, f"result_count={result_count}; max_error={max_result_error:.17g}")
        mac_count, max_one_minus_mac = modal_mac_checks(py_values, matlab_values)
        add_check(checks, "S4-009", "modal_mac", max_one_minus_mac <= 1e-10, f"mode_count={mac_count}; max_1_minus_MAC={max_one_minus_mac:.17g}")

        cache: dict[str, Any] = {}
        historical = third_historical_results(case_dirs, cache)
        result_map = unique_map(py_results, RESULT_KEY_FIELDS)
        hist_checked = 0
        max_third_error = 0.0
        for row in py_results:
            if row["scope"] == "HISTORICAL":
                expected = historical[(row["case_id"], row["comparison_model"])]["total"]
                actual = float(row["historical_total_percent"])
                error = abs(expected-actual)
                max_third_error = max(max_third_error, error)
                passed = error <= 1e-10 + 1e-10*max(abs(expected), abs(actual))
                third_rows.append(
                    {
                        "third_order": len(third_rows)+1,
                        "case_id": row["case_id"], "scope": "HISTORICAL",
                        "key": "|".join(key_of(row, RESULT_KEY_FIELDS)),
                        "reported_value": format(actual, ".17g"),
                        "third_value": format(expected, ".17g"),
                        "absolute_error": format(error, ".17g"),
                        "status": "PASS" if passed else "FAIL",
                    }
                )
                hist_checked += 1
            elif row["scope"] == "PAPER":
                expected, expected_status = third_paper_result(row, case_dirs, cache)
                actual = float(row["eq445_sum"])
                error = abs(expected-actual)
                max_third_error = max(max_third_error, error)
                passed = (
                    expected_status == row["eq445_status"]
                    and error <= 1e-10 + 1e-10*max(abs(expected), abs(actual))
                )
                third_rows.append(
                    {
                        "third_order": len(third_rows)+1,
                        "case_id": row["case_id"], "scope": "PAPER",
                        "key": "|".join(key_of(row, RESULT_KEY_FIELDS)),
                        "reported_value": format(actual, ".17g"),
                        "third_value": format(expected, ".17g"),
                        "absolute_error": format(error, ".17g"),
                        "status": "PASS" if passed else "FAIL",
                    }
                )
        add_check(checks, "S4-010", "third_recompute", hist_checked == 28, f"historical_result_rows={hist_checked}")
        add_check(checks, "S4-011", "third_recompute", all(row["status"] == "PASS" for row in third_rows), f"third_rows={len(third_rows)}; max_error={max_third_error:.17g}")

        hist_value_map = unique_map(py_values, VALUE_KEY_FIELDS)
        intermediate_count = 0
        max_intermediate_error = 0.0
        for case_id in sorted(case_dirs):
            for model in ("orig", "guyan", "cb"):
                modal = historical[(case_id, model)]["modal"]
                arrays = {"eq441_gamma": modal.gamma, "eq442_participation_ratio": modal.participation, "eq444_energy_total": modal.energy_total}
                for quantity, array in arrays.items():
                    for index, expected in enumerate(np.asarray(array).reshape(-1), start=1):
                        key = (
                            case_id, "HISTORICAL", "AUTHOR_CONSUMER_ORDER", "AUTHOR_HISTORICAL_FORMULA",
                            "AUTHOR_ROUTE_REPRODUCED", "AUTHOR_LITERAL", "REDUCED_GENERALIZED", "-1",
                            model, quantity, str(index), "0",
                        )
                        actual = float(hist_value_map[key]["value"])
                        error = abs(float(expected)-actual)
                        max_intermediate_error = max(max_intermediate_error, error)
                        if error > 1e-10 + 1e-10*max(abs(float(expected)), abs(actual)):
                            raise RuntimeError(f"third historical intermediate mismatch: {key}: {error}")
                        intermediate_count += 1
        add_check(checks, "S4-012", "third_recompute", True, f"historical_intermediates={intermediate_count}; max_error={max_intermediate_error:.17g}")

        mutation_rows = run_mutations(case_dirs, cache)
        add_check(checks, "S4-013", "mutations", len(mutation_rows) == 8 and all(row["status"] == "PASS" for row in mutation_rows), f"mutations={len(mutation_rows)}")
        forbidden = [str(path) for path in TEST_ROOT.rglob("*") if path.is_dir() and path.name in FORMAL_OBJECT_NAMES]
        board22 = [str(path) for path in TEST_ROOT.rglob("*") if path.is_dir() and "板块22" in path.name]
        add_check(checks, "S4-014", "scope_boundary", not forbidden and not board22, f"formal_objects={len(forbidden)}; board22_dirs={len(board22)}")
        all_paths = [path for root in (INPUT_ROOT, COMPUTE_ROOT, ORCHESTRATION_ROOT) for path in [root, *root.rglob("*")]]
        max_path = max(utf16_units(path) for path in all_paths)
        reparses = [str(path) for path in all_paths if path.exists() and is_reparse(path)]
        add_check(checks, "S4-015", "filesystem", max_path <= 220 and not reparses, f"max_utf16_units={max_path}; reparse_count={len(reparses)}")
        process_count = target_process_count()
        add_check(checks, "S4-016", "process", process_count == 0, f"target_process_count={process_count}")
        statuses = Counter(row["boundary_status"] for row in py_results)
        boundary_ok = (
            any("INPUT_IDENTITY_UNRESOLVED" in status for status in statuses)
            and any("MODE_COUNT_UNSPECIFIED" in status for status in statuses)
            and any("D_SET_UNSPECIFIED" in status for status in statuses)
            and any("WHOLE_VS_LOCAL_MODEL_UNRESOLVED" in status for status in statuses)
            and any("CB_RECOVERY_UNSPECIFIED" in status for status in statuses)
            and any("COORDINATE_ORDER_CONFLICT" in status for status in statuses)
            and any("LOCAL_NUMERICAL_SUBSTRUCTURE_12D_PENDING" in status for status in statuses)
        )
        add_check(checks, "S4-017", "scientific_boundary", boundary_ok, f"distinct_boundary_statuses={len(statuses)}")
        metrics.update(
            {
                "cross_value_count": len(cross_rows),
                "case_result_count": result_count,
                "modal_mac_count": mac_count,
                "third_recompute_count": len(third_rows),
                "historical_intermediate_count": intermediate_count,
                "max_cross_absolute_error": max_cross_abs,
                "max_cross_scaled_error": max_cross_scaled,
                "max_case_result_error": max_result_error,
                "max_one_minus_mac": max_one_minus_mac,
                "max_third_recompute_error": max_third_error,
                "max_historical_intermediate_error": max_intermediate_error,
                "max_utf16_path_units": max_path,
                "final_target_process_count": process_count,
            }
        )
    except Exception as error:
        failure = error
        add_check(checks, "S4-FAILURE", "validator_exception", False, f"{type(error).__name__}: {error}")

    write_csv_new(VALIDATION_ROOT / "checks.csv", checks, ["check_id", "category", "status", "detail"])
    write_csv_new(
        VALIDATION_ROOT / "cross_language.csv", cross_rows,
        [
            "comparison_order", "key", "python_value", "matlab_value", "comparison_method",
            "alignment_sign", "compared_matlab_value", "raw_absolute_error", "normalization_scale",
            "absolute_error", "tolerance", "scaled_error", "status_match", "flags_match", "status",
        ],
    )
    write_csv_new(
        VALIDATION_ROOT / "determinism.csv", determinism_rows,
        ["implementation", "relative_path", "a_sha256", "b_sha256", "byte_identical", "status"],
    )
    write_csv_new(
        VALIDATION_ROOT / "third_recompute.csv", third_rows,
        ["third_order", "case_id", "scope", "key", "reported_value", "third_value", "absolute_error", "status"],
    )
    write_csv_new(
        VALIDATION_ROOT / "mutation_results.csv", mutation_rows,
        ["mutation_order", "mutation_id", "expected_rejection_field", "numeric_delta", "numeric_changed", "contract_rejected", "positive_contract_after", "status"],
    )
    pass_count = sum(row["status"] == "PASS" for row in checks)
    fail_count = sum(row["status"] == "FAIL" for row in checks)
    summary = {
        "schema_version": "BOARD21_STEP4_VALIDATION_V1",
        "status": "PASS" if failure is None and fail_count == 0 else "FAIL",
        "check_count": len(checks),
        "pass_count": pass_count,
        "failure_count": fail_count,
        "input_manifest_item_count": 103,
        "step3_case_count": 14,
        "whole_model_candidate_count": 2,
        "mutation_count": len(mutation_rows),
        "formula_4_45_evaluated_conditionally": True,
        "table4_1_adjudicated": False,
        "scientific_status": "AUTHOR_ROUTE_REPRODUCED_AND_PAPER_LITERAL_CONDITIONAL_TABLE4_1_PENDING",
        "metrics": metrics,
        "error": "" if failure is None else f"{type(failure).__name__}: {failure}",
    }
    write_json_new(VALIDATION_ROOT / "validation_summary.json", summary)
    manifest_names = ["checks.csv", "cross_language.csv", "determinism.csv", "third_recompute.csv", "mutation_results.csv", "validation_summary.json"]
    manifest_rows = []
    for order, name in enumerate(manifest_names, start=1):
        path = VALIDATION_ROOT / name
        manifest_rows.append(
            {
                "artifact_order": order, "relative_path": name,
                "size_bytes": path.stat().st_size, "sha256": sha256_file(path),
                "manifest_scope": "VALIDATION_OUTPUTS_EXCLUDING_THIS_MANIFEST",
            }
        )
    write_csv_new(
        VALIDATION_ROOT / "validation_output_manifest.csv", manifest_rows,
        ["artifact_order", "relative_path", "size_bytes", "sha256", "manifest_scope"],
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
