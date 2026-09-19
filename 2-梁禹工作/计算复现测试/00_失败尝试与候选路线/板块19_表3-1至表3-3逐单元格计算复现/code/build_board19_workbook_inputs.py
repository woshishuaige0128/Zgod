from __future__ import annotations

import csv
import hashlib
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg
from scipy.io import loadmat
from scipy.io.matlab import MatReadWarning


TOL_VALUE = 1.0e-11
HISTORICAL_BOUNDS_S = np.array([0.0, 7.27, 13.73, 21.4, 32.31, 40.0])


def find_board_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if candidate.name == "板块19_表3-1至表3-3逐单元格计算复现":
            return candidate
    raise RuntimeError("无法定位板块19隔离根目录。")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空表：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fields or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "pass"}


def method_code(method: str) -> str:
    return "G" if method == "Guyan" else "CB"


def solve_modes(k_matrix: np.ndarray, m_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    eigenvalues, eigenvectors = linalg.eig(k_matrix, m_matrix)
    imaginary_ratio = np.max(
        np.abs(eigenvalues.imag) / np.maximum(np.abs(eigenvalues.real), np.finfo(float).eps)
    )
    if imaginary_ratio > 1.0e-10:
        raise ValueError(f"广义特征值虚部比例超限：{imaginary_ratio:.16g}")
    order = np.argsort(eigenvalues.real)
    eigenvalues = eigenvalues.real[order]
    eigenvectors = eigenvectors.real[:, order]
    if np.any(eigenvalues <= 0):
        raise ValueError("出现非正广义特征值。")
    eigenvectors /= np.linalg.norm(eigenvectors, axis=0, keepdims=True)
    frequencies = np.sqrt(eigenvalues) / (2.0 * np.pi)
    return eigenvectors, frequencies


def euclidean_mac(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    numerator = abs(vector_a.T @ vector_b) ** 2
    denominator = (vector_a.T @ vector_a) * (vector_b.T @ vector_b)
    return float(numerator / denominator)


def manifest_hash(manifest: dict[str, dict[str, str]], source_file: str) -> str:
    key = source_file.replace("\\", "/")
    if key.startswith("input/"):
        key = key[len("input/") :]
    if key not in manifest:
        raise KeyError(f"输入清单中缺少：{source_file}（归一化为 {key}）")
    return manifest[key]["sha256_copy"]


def main() -> None:
    board_root = find_board_root(Path(__file__).resolve().parent)
    output_root = board_root / "outputs"
    evidence_dir = output_root / "evidence"
    workbook_input_dir = output_root / "workbook_inputs"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    workbook_input_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = read_csv(board_root / "input" / "input_manifest.csv")
    manifest = {row["copied_relative_path"].replace("\\", "/"): row for row in manifest_rows}
    if len(manifest_rows) != 35 or any(row["status"] != "MATCH" for row in manifest_rows):
        raise RuntimeError("输入冻结清单必须为35/35 MATCH。")

    table31 = read_csv(output_root / "modal_python" / "table3_1_cell_adjudication.csv")
    table32 = read_csv(output_root / "modal_python" / "table3_2_cell_adjudication.csv")
    table33 = read_csv(output_root / "nrmse_python" / "table3_3_cell_adjudication.csv")
    group33 = read_csv(output_root / "nrmse_python" / "table3_3_group_adjudication.csv")
    if (len(table31), len(table32), len(table33)) != (8, 8, 24):
        raise RuntimeError(
            f"目标单元格数异常：表3-1={len(table31)}，表3-2={len(table32)}，表3-3={len(table33)}"
        )

    frequency_inputs: list[dict[str, Any]] = []
    all_cells: list[dict[str, Any]] = []
    for row in table31:
        division = int(row["division"])
        mode = int(row["mode"])
        method = row["method"]
        cell_id = f"T3-1-D{division}-{method_code(method)}-M{mode}"
        source_hash = manifest_hash(manifest, row["source_file"])
        frequency_inputs.append(
            {
                "cell_id": cell_id,
                "division": division,
                "method": method,
                "route": row["route"],
                "mode": mode,
                "full_frequency_hz": float(row["full_frequency_hz"]),
                "reduced_frequency_hz": float(row["reduced_frequency_hz"]),
                "paper_value_percent": float(row["paper_value_percent"]),
                "printed_decimals": int(row["printed_decimals"]),
                "source_file": row["source_file"],
                "source_sha256": source_hash,
            }
        )
        all_cells.append(
            {
                "cell_id": cell_id,
                "object_id": "T3-1",
                "object_name": "表3-1 两类划分前两阶固有频率相对误差",
                "division": division,
                "condition": f"第{mode}阶",
                "method": method,
                "route": row["route"],
                "calculated_value": float(row["relative_error_percent"]),
                "paper_value": float(row["paper_value_percent"]),
                "printed_decimals": int(row["printed_decimals"]),
                "rounded_value": float(row["rounded_value"]),
                "absolute_difference": float(row["absolute_difference_percent"]),
                "rounded_match": as_bool(row["rounded_match"]),
                "cross_language_pass": as_bool(row["cross_language_pass"]),
                "evidence_label": row["evidence_label"],
                "formula": row["formula"],
                "source_file": row["source_file"],
                "source_sha256": source_hash,
            }
        )

    write_csv(workbook_input_dir / "frequency_inputs.csv", frequency_inputs)

    modal_source = board_root / "input" / "board17" / "outputs" / "global_routes_matlab.mat"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MatReadWarning)
        modal_data = loadmat(modal_source, simplify_cells=True)
    phi_full, _frequency_full = solve_modes(
        np.asarray(modal_data["KRrt"], dtype=float), np.asarray(modal_data["MRrt"], dtype=float)
    )
    mac_vectors: list[dict[str, Any]] = []
    mac_cell_inputs: list[dict[str, Any]] = []
    for row in table32:
        division = int(row["division"])
        mode = int(row["mode"])
        method = row["method"]
        cell_id = f"T3-2-D{division}-{method_code(method)}-M{mode}"
        division_data = modal_data[f"division{division}"]
        master = np.asarray(division_data["master"], dtype=int).reshape(-1) - 1
        n_master = int(division_data["n_master"])
        if method == "Guyan":
            k_reduced = np.asarray(division_data["K_historical"], dtype=float)
            m_reduced = np.asarray(division_data["M_historical"], dtype=float)
        else:
            k_reduced = np.asarray(division_data["K_cb"], dtype=float)
            m_reduced = np.asarray(division_data["M_cb"], dtype=float)
        phi_reduced, _frequency_reduced = solve_modes(k_reduced, m_reduced)
        vector_full = phi_full[master, mode - 1]
        vector_reduced = phi_reduced[:n_master, mode - 1]
        value = euclidean_mac(vector_full, vector_reduced)
        expected = float(row["mac_value"])
        if abs(value - expected) > TOL_VALUE:
            raise RuntimeError(f"{cell_id} 模态向量反算MAC不一致：{value:.16g} vs {expected:.16g}")
        start_index = len(mac_vectors) + 1
        for position, (natural_dof, full_component, reduced_component) in enumerate(
            zip(master + 1, vector_full, vector_reduced, strict=True), start=1
        ):
            mac_vectors.append(
                {
                    "cell_id": cell_id,
                    "division": division,
                    "method": method,
                    "mode": mode,
                    "vector_position": position,
                    "natural_dof": int(natural_dof),
                    "full_component": float(full_component),
                    "reduced_component": float(reduced_component),
                }
            )
        end_index = len(mac_vectors)
        source_hash = manifest_hash(manifest, row["source_file"])
        mac_cell_inputs.append(
            {
                "cell_id": cell_id,
                "division": division,
                "method": method,
                "route": row["route"],
                "mode": mode,
                "coordinate_dimension": n_master,
                "vector_data_start": start_index,
                "vector_data_end": end_index,
                "paper_value": float(row["paper_value"]),
                "printed_decimals": int(row["printed_decimals"]),
                "expected_mac": expected,
                "source_file": row["source_file"],
                "source_sha256": source_hash,
            }
        )
        all_cells.append(
            {
                "cell_id": cell_id,
                "object_id": "T3-2",
                "object_name": "表3-2 两类划分前两阶模态保证准则",
                "division": division,
                "condition": f"第{mode}阶",
                "method": method,
                "route": row["route"],
                "calculated_value": expected,
                "paper_value": float(row["paper_value"]),
                "printed_decimals": int(row["printed_decimals"]),
                "rounded_value": float(row["rounded_value"]),
                "absolute_difference": float(row["absolute_difference"]),
                "rounded_match": as_bool(row["rounded_match"]),
                "cross_language_pass": as_bool(row["cross_language_pass"]),
                "evidence_label": row["evidence_label"],
                "formula": row["formula"],
                "source_file": row["source_file"],
                "source_sha256": source_hash,
            }
        )

    write_csv(workbook_input_dir / "mac_vectors.csv", mac_vectors)
    write_csv(workbook_input_dir / "mac_cell_inputs.csv", mac_cell_inputs)

    nrmse_aggregates: list[dict[str, Any]] = []
    loaded_responses: dict[str, np.ndarray] = {}
    for row in table33:
        division = int(row["division"])
        excitation = row["excitation"]
        band_id = int(row["band_id"])
        floor = int(row["reported_floor"])
        method = row["method"]
        cell_id = f"T3-3-D{division}-{excitation}-B{band_id}-{method_code(method)}"
        filename = row["source_file"]
        response_path = board_root / "input" / "board18" / "responses" / filename
        if filename not in loaded_responses:
            loaded_responses[filename] = np.loadtxt(
                response_path, delimiter=",", skiprows=1, encoding="utf-8-sig"
            )
        data = loaded_responses[filename]
        time = data[:, 0]
        responses = data[:, 1:].reshape(data.shape[0], 3, 3)
        reference = responses[:, floor - 1, 0]
        method_index = 1 if method == "Guyan" else 2
        reduced = responses[:, floor - 1, method_index]
        error = reference - reduced
        if excitation == "ElCentro":
            window_start = float(time[0])
            window_end = float(time[-1])
            mask = np.ones_like(time, dtype=bool)
            inclusion = "all_samples"
        else:
            window_start = float(HISTORICAL_BOUNDS_S[band_id - 1])
            window_end = float(HISTORICAL_BOUNDS_S[band_id])
            mask = (time >= window_start) & (time < window_end)
            inclusion = "historical_[start,end)"
        segment_error = error[mask]
        sample_count = int(segment_error.size)
        sum_squared_error = float(np.sum(segment_error**2))
        reference_min = float(np.min(reference))
        reference_max = float(np.max(reference))
        reference_range = reference_max - reference_min
        calculated = 100.0 * math.sqrt(sum_squared_error / sample_count) / reference_range
        expected = float(row["historical_value_percent"])
        if abs(calculated - expected) > TOL_VALUE:
            raise RuntimeError(f"{cell_id} 聚合量反算NRMSE不一致：{calculated:.16g} vs {expected:.16g}")
        source_hash = sha256_file(response_path)
        if source_hash != row["source_sha256"]:
            raise RuntimeError(f"{cell_id} 响应CSV哈希不一致。")
        nrmse_aggregates.append(
            {
                "cell_id": cell_id,
                "division": division,
                "excitation": excitation,
                "band_id": band_id,
                "frequency_band": row["frequency_band"],
                "method": method,
                "reported_floor": floor,
                "group_inferred_floor": row["group_inferred_floor"],
                "selection_basis": row["selection_basis"],
                "window_start_s": window_start,
                "window_end_s": window_end,
                "window_inclusion": inclusion,
                "sample_count": sample_count,
                "sum_squared_error_mm2": sum_squared_error,
                "reference_min_mm": reference_min,
                "reference_max_mm": reference_max,
                "reference_range_mm": reference_range,
                "paper_value_percent": float(row["paper_value_percent"]),
                "printed_decimals": int(row["printed_decimals"]),
                "expected_historical_value_percent": expected,
                "source_file": filename,
                "source_sha256": source_hash,
            }
        )
        all_cells.append(
            {
                "cell_id": cell_id,
                "object_id": "T3-3",
                "object_name": "表3-3 两类划分五个Chirp频段及El Centro响应NRMSE",
                "division": division,
                "condition": f"{row['frequency_band']}；报告楼层{floor}",
                "method": method,
                "route": f"historical_mean_full_range；{row['selection_basis']}",
                "calculated_value": expected,
                "paper_value": float(row["paper_value_percent"]),
                "printed_decimals": int(row["printed_decimals"]),
                "rounded_value": float(row["historical_rounded_value"]),
                "absolute_difference": float(row["historical_absolute_difference_percent"]),
                "rounded_match": as_bool(row["historical_rounded_match"]),
                "cross_language_pass": as_bool(row["cross_language_pass"]),
                "evidence_label": row["evidence_label"],
                "formula": row["formula"],
                "source_file": filename,
                "source_sha256": source_hash,
            }
        )

    write_csv(workbook_input_dir / "nrmse_aggregates.csv", nrmse_aggregates)
    write_csv(workbook_input_dir / "nrmse_group_inference.csv", group33)
    write_csv(evidence_dir / "table3_all_40_cells.csv", all_cells)

    provenance_rows: list[dict[str, Any]] = []
    for row in manifest_rows:
        copied = board_root / "input" / row["copied_relative_path"]
        live_hash = sha256_file(copied)
        provenance_rows.append(
            {
                **row,
                "live_copy_sha256": live_hash,
                "live_status": "MATCH" if live_hash == row["sha256_copy"] else "MISMATCH",
            }
        )
    if any(row["live_status"] != "MATCH" for row in provenance_rows):
        raise RuntimeError("工作簿封装前输入哈希复核失败。")
    write_csv(workbook_input_dir / "provenance.csv", provenance_rows)

    counts = {
        "table3_1_cells": len(table31),
        "table3_1_rounded_matches": sum(as_bool(row["rounded_match"]) for row in table31),
        "table3_2_cells": len(table32),
        "table3_2_rounded_matches": sum(as_bool(row["rounded_match"]) for row in table32),
        "table3_3_cells": len(table33),
        "table3_3_rounded_matches": sum(as_bool(row["historical_rounded_match"]) for row in table33),
        "all_cells": len(all_cells),
        "all_cross_language_pass": all(row["cross_language_pass"] for row in all_cells),
        "mac_vector_rows": len(mac_vectors),
        "nrmse_aggregate_rows": len(nrmse_aggregates),
        "provenance_rows": len(provenance_rows),
        "provenance_live_matches": sum(row["live_status"] == "MATCH" for row in provenance_rows),
        "status": "PASS",
    }
    if counts["all_cells"] != 40 or not counts["all_cross_language_pass"]:
        raise RuntimeError(f"40单元格统一证据检查失败：{counts}")
    workbook_payload = {
        "frequency_inputs": frequency_inputs,
        "mac_vectors": mac_vectors,
        "mac_cell_inputs": mac_cell_inputs,
        "nrmse_aggregates": nrmse_aggregates,
        "nrmse_group_inference": group33,
        "all_cells": all_cells,
        "provenance": provenance_rows,
        "summary": counts,
    }
    (workbook_input_dir / "workbook_payload.json").write_text(
        json.dumps(workbook_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (evidence_dir / "workbook_inputs_summary.json").write_text(
        json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
