from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import loadmat


BOARD = Path(__file__).resolve().parents[1]
BASELINE = BOARD / "input" / "plotting_baseline" / "输入数据"
RUN1 = BOARD / "outputs" / "adapted_run1" / "输入数据"
RUN2 = BOARD / "outputs" / "adapted_run2" / "输入数据"
INDEPENDENT = BOARD / "outputs" / "independent" / "输入数据"
OUT = BOARD / "outputs" / "comparisons"

DATASETS = {
    "unit": "单位激励_原结构三层响应.mat",
    "division1_elcentro": "第一类划分_ElCentro地震响应.mat",
    "division2_elcentro": "第二类划分_ElCentro地震响应.mat",
    "division1_chirp": "第一类划分_Chirp响应.mat",
    "division2_chirp": "第二类划分_Chirp响应.mat",
}

FLOORS = ("Floor 1", "Floor 2", "Floor 3")
METHODS = ("Original", "Guyan", "Craig-Bampton")


@dataclass(frozen=True)
class PairContract:
    name: str
    left_root: Path
    right_root: Path
    time_tol_s: float
    abs_tol_mm: float
    peak_normalized_tol: float


PAIR_CONTRACTS = (
    PairContract("adapted_run1_vs_run2", RUN1, RUN2, 1e-14, 1e-12, 1e-12),
    PairContract("adapted_run1_vs_2026_plotting_baseline", RUN1, BASELINE, 1e-14, 1e-10, 1e-10),
    PairContract("independent_rk4_vs_adapted_run1", INDEPENDENT, RUN1, 1e-14, 1e-8, 1e-8),
)

FIGURES = (
    ("F3-5", "3-5", "unit", "all_original_floors", "none"),
    ("F3-6", "3-6", "division1_elcentro", "Floor 1", "10-11;21.5-22.5"),
    ("F3-7", "3-7", "division1_elcentro", "Floor 2", "10-11;21.5-22.5"),
    ("F3-8", "3-8", "division1_elcentro", "Floor 3", "10-11;21.5-22.5"),
    ("F3-9", "3-9", "division2_elcentro", "Floor 1", "10-11;21.5-22.5"),
    ("F3-10", "3-10", "division2_elcentro", "Floor 3", "10-11;21.5-22.5"),
    ("F3-11", "3-11", "division1_chirp", "Floor 1", "13-14;38-38.3"),
    ("F3-12", "3-12", "division1_chirp", "Floor 2", "13-14;38-38.3"),
    ("F3-13", "3-13", "division1_chirp", "Floor 3", "13-14;38-38.3"),
    ("F3-14", "3-14", "division2_chirp", "Floor 1", "13-14;38-38.3"),
    (
        "F3-15",
        "3-15",
        "division2_chirp",
        "Floor 3",
        "historical_local_panels=division2_elcentro/Floor 3/10-11;21.5-22.5;"
        "corrected_local_panels=division2_chirp/Floor 3/13-14;38-38.3",
    ),
)


def matlab_text_tuple(value: object) -> tuple[str, ...]:
    items: list[str] = []
    for item in np.asarray(value, dtype=object).reshape(-1):
        array = np.asarray(item)
        if array.size != 1:
            raise ValueError(f"MATLAB text cell is not scalar: shape={array.shape}")
        items.append(str(array.reshape(-1)[0]))
    return tuple(items)


def load_response(path: Path) -> tuple[np.ndarray, np.ndarray]:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw = loadmat(path, squeeze_me=False, struct_as_record=False)
    required = {"time_s", "response_mm", "method_order", "floor_order"}
    missing = sorted(required.difference(raw))
    if missing:
        raise KeyError(f"{path}: missing required variables {missing}")
    method_order = matlab_text_tuple(raw["method_order"])
    floor_order = matlab_text_tuple(raw["floor_order"])
    if method_order != METHODS:
        raise ValueError(f"{path}: method_order={method_order}, expected {METHODS}")
    if floor_order != FLOORS:
        raise ValueError(f"{path}: floor_order={floor_order}, expected {FLOORS}")
    time_s = np.asarray(raw["time_s"], dtype=float).reshape(-1)
    response = np.asarray(raw["response_mm"], dtype=float)
    if response.shape != (time_s.size, 3, 3):
        raise ValueError(f"{path}: response shape {response.shape}, expected ({time_s.size}, 3, 3)")
    if time_s.size != 40961:
        raise ValueError(f"{path}: expected 40961 samples, got {time_s.size}")
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(response)):
        raise ValueError(f"{path}: non-finite values")
    if not np.all(np.diff(time_s) > 0):
        raise ValueError(f"{path}: time is not strictly increasing")
    return time_s, response


def correlation(left: np.ndarray, right: np.ndarray) -> float:
    left_centered = left - np.mean(left)
    right_centered = right - np.mean(right)
    denom = float(np.linalg.norm(left_centered) * np.linalg.norm(right_centered))
    if denom == 0.0:
        return 1.0 if np.array_equal(left, right) else 0.0
    return float(np.dot(left_centered, right_centered) / denom)


def compare_pair(contract: PairContract) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    detail_rows: list[dict[str, object]] = []
    dataset_rows: list[dict[str, object]] = []
    for dataset_id, filename in DATASETS.items():
        left_time, left_response = load_response(contract.left_root / filename)
        right_time, right_response = load_response(contract.right_root / filename)
        time_max_abs = float(np.max(np.abs(left_time - right_time)))
        dataset_pass = time_max_abs <= contract.time_tol_s
        dataset_max_abs = 0.0
        dataset_max_peak_norm = 0.0
        for floor_index, floor_name in enumerate(FLOORS):
            for method_index, method_name in enumerate(METHODS):
                left = left_response[:, floor_index, method_index]
                right = right_response[:, floor_index, method_index]
                delta = left - right
                max_abs = float(np.max(np.abs(delta)))
                rmse = float(np.sqrt(np.mean(delta * delta)))
                right_norm = float(np.linalg.norm(right))
                relative_fro = float(np.linalg.norm(delta) / max(right_norm, np.finfo(float).tiny))
                reference_peak = float(np.max(np.abs(right)))
                peak_normalized = max_abs / max(reference_peak, np.finfo(float).tiny)
                corr = correlation(left, right)
                passed = (
                    time_max_abs <= contract.time_tol_s
                    and max_abs <= contract.abs_tol_mm
                    and peak_normalized <= contract.peak_normalized_tol
                )
                dataset_pass = dataset_pass and passed
                dataset_max_abs = max(dataset_max_abs, max_abs)
                dataset_max_peak_norm = max(dataset_max_peak_norm, peak_normalized)
                detail_rows.append(
                    {
                        "comparison": contract.name,
                        "dataset_id": dataset_id,
                        "filename": filename,
                        "floor": floor_name,
                        "method": method_name,
                        "sample_count": left_time.size,
                        "time_max_abs_s": time_max_abs,
                        "response_max_abs_mm": max_abs,
                        "response_rmse_mm": rmse,
                        "relative_fro": relative_fro,
                        "peak_normalized_max_abs": peak_normalized,
                        "correlation": corr,
                        "time_tolerance_s": contract.time_tol_s,
                        "abs_tolerance_mm": contract.abs_tol_mm,
                        "peak_normalized_tolerance": contract.peak_normalized_tol,
                        "status": "PASS" if passed else "FAIL",
                    }
                )
        dataset_rows.append(
            {
                "comparison": contract.name,
                "dataset_id": dataset_id,
                "filename": filename,
                "sample_count": left_time.size,
                "time_max_abs_s": time_max_abs,
                "max_response_abs_mm": dataset_max_abs,
                "max_peak_normalized_abs": dataset_max_peak_norm,
                "status": "PASS" if dataset_pass else "FAIL",
            }
        )
    return detail_rows, dataset_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    all_detail: list[dict[str, object]] = []
    all_dataset: list[dict[str, object]] = []
    errors: list[str] = []
    for contract in PAIR_CONTRACTS:
        try:
            detail, dataset = compare_pair(contract)
            all_detail.extend(detail)
            all_dataset.extend(dataset)
        except Exception as exc:  # preserve missing/invalid-route evidence in summary
            errors.append(f"{contract.name}: {type(exc).__name__}: {exc}")

    if all_detail:
        write_csv(OUT / "response_column_comparisons.csv", all_detail)
    if all_dataset:
        write_csv(OUT / "response_dataset_comparisons.csv", all_dataset)

    figure_rows = [
        {
            "object_id": object_id,
            "unique_figure_id": figure_id,
            "dataset_id": dataset_id,
            "floor_scope": floor_scope,
            "window_contract": window_contract,
            "author_historical_timeseries": "NOT_AVAILABLE_PENDING_DECISION",
        }
        for object_id, figure_id, dataset_id, floor_scope, window_contract in FIGURES
    ]
    write_csv(OUT / "figure_data_contract.csv", figure_rows)

    failed_rows = [row for row in all_detail if row["status"] != "PASS"]
    expected_detail_count = len(PAIR_CONTRACTS) * len(DATASETS) * len(FLOORS) * len(METHODS)
    passed = not errors and len(all_detail) == expected_detail_count and not failed_rows
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_detail_count": expected_detail_count,
        "detail_count": len(all_detail),
        "dataset_summary_count": len(all_dataset),
        "figure_contract_count": len(figure_rows),
        "failure_count": len(failed_rows),
        "errors": errors,
        "pass": passed,
    }
    (OUT / "response_comparison_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
