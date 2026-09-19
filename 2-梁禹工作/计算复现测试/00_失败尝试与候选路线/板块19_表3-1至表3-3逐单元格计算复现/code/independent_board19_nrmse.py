"""独立复算表3-3 NRMSE，比较MATLAB并按统一楼层逐格裁决论文值。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


TOL_NRMSE_PERCENT = 5e-10
TOL_RMSE_MM = 5e-12
TOL_RANGE_MM = 5e-12
TOL_TIME_S = 5e-12


def find_board_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if parent.name == "板块19_表3-1至表3-3逐单元格计算复现":
            return parent
    raise RuntimeError("无法定位板块19根目录。")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fieldnames or list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def rounding_match(value: float, target: float, decimals: int) -> bool:
    return abs(float(np.round(value, decimals)) - target) <= 5e-12


def main() -> None:
    board_root = find_board_root(Path(__file__).resolve().parent)
    input_dir = board_root / "input" / "board18" / "responses"
    matlab_dir = board_root / "outputs" / "nrmse_matlab"
    output_dir = board_root / "outputs" / "nrmse_python"
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = read_csv(board_root / "input" / "input_manifest.csv")
    manifest = {row["copied_relative_path"]: row for row in manifest_rows}
    datasets = [
        (1, "Chirp", "第一类划分_Chirp响应.csv"),
        (1, "ElCentro", "第一类划分_ElCentro地震响应.csv"),
        (2, "Chirp", "第二类划分_Chirp响应.csv"),
        (2, "ElCentro", "第二类划分_ElCentro地震响应.csv"),
    ]
    methods = [("Guyan", 1), ("Craig-Bampton", 2)]
    historical_bounds = np.array([0.0, 7.27, 13.73, 21.4, 32.31, 40.0])
    frequency_bounds = np.array([0.1, 1.9, 3.5, 5.4, 8.1, 10.0])
    exact_bounds = (frequency_bounds - 0.1) / (10.0 - 0.1) * 40.0
    band_labels = ["0.1-1.9 Hz", "1.9-3.5 Hz", "3.5-5.4 Hz", "5.4-8.1 Hz", "8.1-10 Hz"]

    candidates: list[dict[str, Any]] = []
    input_checks: list[dict[str, Any]] = []

    def add_candidate(
        *,
        division: int,
        excitation: str,
        floor: int,
        method: str,
        route: str,
        band_id: int,
        band_label: str,
        window_start: float,
        window_end: float,
        mask: np.ndarray,
        inclusion: str,
        use_trapezoid: bool,
        time: np.ndarray,
        error: np.ndarray,
        reference_range: float,
        filename: str,
        source_hash: str,
    ) -> None:
        if np.count_nonzero(mask) < 2:
            raise ValueError(f"{filename}/层{floor}/{method}/{route}样本不足")
        segment_error = error[mask]
        if use_trapezoid:
            rmse = math.sqrt(
                float(np.trapezoid(segment_error**2, time[mask])) / (window_end - window_start)
            )
            numerator_formula = "sqrt(trapezoid(error^2)/(window_end-window_start))"
        else:
            rmse = math.sqrt(float(np.mean(segment_error**2)))
            numerator_formula = "sqrt(mean(error^2))"
        candidates.append(
            {
                "division": division,
                "excitation": excitation,
                "floor": floor,
                "method": method,
                "route": route,
                "band_id": band_id,
                "frequency_band": band_label,
                "window_start_s": window_start,
                "window_end_s": window_end,
                "window_inclusion": inclusion,
                "sample_count": int(np.count_nonzero(mask)),
                "reference_range_mm": reference_range,
                "rmse_mm": rmse,
                "nrmse_percent": 100.0 * rmse / reference_range,
                "numerator_formula": numerator_formula,
                "normalization": "full_40s_reference_peak_to_peak",
                "source_file": filename,
                "source_sha256": source_hash,
            }
        )

    for division, excitation, filename in datasets:
        path = input_dir / filename
        manifest_key = f"board18/responses/{filename}"
        if manifest_key not in manifest:
            raise RuntimeError(f"冻结清单缺少：{manifest_key}")
        expected_hash = manifest[manifest_key]["sha256_copy"]
        live_hash = sha256(path)
        if live_hash != expected_hash or manifest[manifest_key]["status"] != "MATCH":
            raise RuntimeError(f"输入哈希未通过：{filename}")
        data = np.genfromtxt(path, delimiter=",", skip_header=1, encoding="utf-8-sig")
        if data.shape != (40961, 10) or not np.isfinite(data).all():
            raise RuntimeError(f"{filename}尺寸或有限性异常：{data.shape}")
        time = data[:, 0]
        dt = np.diff(time)
        if (
            time[0] != 0.0
            or time[-1] != 40.0
            or np.any(dt <= 0)
            or np.max(np.abs(dt - 1 / 1024)) > 5e-15
        ):
            raise RuntimeError(f"{filename}时间轴异常")
        responses = data[:, 1:].reshape(data.shape[0], 3, 3)  # time × floor × method in C order
        input_checks.append(
            {
                "division": division,
                "excitation": excitation,
                "source_file": filename,
                "row_count": data.shape[0],
                "column_count": data.shape[1],
                "time_start_s": time[0],
                "time_end_s": time[-1],
                "dt_min_s": dt.min(),
                "dt_max_s": dt.max(),
                "all_finite": bool(np.isfinite(data).all()),
                "source_sha256": live_hash,
            }
        )
        for floor in (1, 2, 3):
            reference = responses[:, floor - 1, 0]
            reference_range = float(np.max(reference) - np.min(reference))
            if reference_range <= 0:
                raise RuntimeError(f"{filename}第{floor}层参考峰峰值非正")
            for method, method_index in methods:
                reduced = responses[:, floor - 1, method_index]
                error = reference - reduced
                if excitation == "ElCentro":
                    full_mask = np.ones_like(time, dtype=bool)
                    for route, use_trapezoid in [
                        ("historical_mean_full_range", False),
                        ("paper_trapezoid_full_range", True),
                    ]:
                        add_candidate(
                            division=division,
                            excitation=excitation,
                            floor=floor,
                            method=method,
                            route=route,
                            band_id=0,
                            band_label="El Centro full",
                            window_start=0.0,
                            window_end=40.0,
                            mask=full_mask,
                            inclusion="all_samples",
                            use_trapezoid=use_trapezoid,
                            time=time,
                            error=error,
                            reference_range=reference_range,
                            filename=filename,
                            source_hash=live_hash,
                        )
                else:
                    for band_index in range(5):
                        h_start = historical_bounds[band_index]
                        h_end = historical_bounds[band_index + 1]
                        e_start = exact_bounds[band_index]
                        e_end = exact_bounds[band_index + 1]
                        route_definitions = [
                            (
                                "historical_mean_full_range",
                                h_start,
                                h_end,
                                (time >= h_start) & (time < h_end),
                                "[start,end)",
                                False,
                            ),
                            (
                                "historical_inclusive_mean_full_range",
                                h_start,
                                h_end,
                                (time >= h_start) & (time <= h_end),
                                "[start,end]",
                                False,
                            ),
                            (
                                "exact_frequency_mean_full_range",
                                e_start,
                                e_end,
                                (time >= e_start) & (time < e_end),
                                "linear_chirp_[start,end)",
                                False,
                            ),
                            (
                                "paper_trapezoid_full_range",
                                h_start,
                                h_end,
                                (time >= h_start) & (time < h_end),
                                "historical_[start,end)",
                                True,
                            ),
                        ]
                        for route, start, end, mask, inclusion, use_trapezoid in route_definitions:
                            add_candidate(
                                division=division,
                                excitation=excitation,
                                floor=floor,
                                method=method,
                                route=route,
                                band_id=band_index + 1,
                                band_label=band_labels[band_index],
                                window_start=float(start),
                                window_end=float(end),
                                mask=mask,
                                inclusion=inclusion,
                                use_trapezoid=use_trapezoid,
                                time=time,
                                error=error,
                                reference_range=reference_range,
                                filename=filename,
                                source_hash=live_hash,
                            )

    candidate_fields = [
        "division",
        "excitation",
        "floor",
        "method",
        "route",
        "band_id",
        "frequency_band",
        "window_start_s",
        "window_end_s",
        "window_inclusion",
        "sample_count",
        "reference_range_mm",
        "rmse_mm",
        "nrmse_percent",
        "numerator_formula",
        "normalization",
        "source_file",
        "source_sha256",
    ]
    input_fields = [
        "division",
        "excitation",
        "source_file",
        "row_count",
        "column_count",
        "time_start_s",
        "time_end_s",
        "dt_min_s",
        "dt_max_s",
        "all_finite",
        "source_sha256",
    ]
    if len(candidates) != 264:
        raise RuntimeError(f"候选行应为264，实际为{len(candidates)}")
    historical_rows = [row for row in candidates if row["route"] == "historical_mean_full_range"]
    if len(historical_rows) != 72:
        raise RuntimeError(f"历史口径行应为72，实际为{len(historical_rows)}")
    write_csv(output_dir / "nrmse_candidates_python.csv", candidates, candidate_fields)
    write_csv(output_dir / "nrmse_historical_floor_candidates_python.csv", historical_rows, candidate_fields)
    write_csv(output_dir / "nrmse_input_checks_python.csv", input_checks, input_fields)

    matlab_rows = read_csv(matlab_dir / "nrmse_candidates_matlab.csv")
    key_fields = ("division", "excitation", "floor", "method", "route", "band_id")
    python_by_key = {
        (
            int(row["division"]),
            row["excitation"],
            int(row["floor"]),
            row["method"],
            row["route"],
            int(row["band_id"]),
        ): row
        for row in candidates
    }
    comparisons: list[dict[str, Any]] = []
    for matlab_row in matlab_rows:
        key = (
            int(matlab_row["division"]),
            matlab_row["excitation"],
            int(matlab_row["floor"]),
            matlab_row["method"],
            matlab_row["route"],
            int(matlab_row["band_id"]),
        )
        python_row = python_by_key[key]
        differences = {
            "window_start_difference_s": abs(float(matlab_row["window_start_s"]) - python_row["window_start_s"]),
            "window_end_difference_s": abs(float(matlab_row["window_end_s"]) - python_row["window_end_s"]),
            "reference_range_difference_mm": abs(
                float(matlab_row["reference_range_mm"]) - python_row["reference_range_mm"]
            ),
            "rmse_difference_mm": abs(float(matlab_row["rmse_mm"]) - python_row["rmse_mm"]),
            "nrmse_difference_percent": abs(
                float(matlab_row["nrmse_percent"]) - python_row["nrmse_percent"]
            ),
        }
        passed = (
            int(matlab_row["sample_count"]) == python_row["sample_count"]
            and differences["window_start_difference_s"] <= TOL_TIME_S
            and differences["window_end_difference_s"] <= TOL_TIME_S
            and differences["reference_range_difference_mm"] <= TOL_RANGE_MM
            and differences["rmse_difference_mm"] <= TOL_RMSE_MM
            and differences["nrmse_difference_percent"] <= TOL_NRMSE_PERCENT
            and matlab_row["source_sha256"] == python_row["source_sha256"]
        )
        comparisons.append(
            {
                "division": key[0],
                "excitation": key[1],
                "floor": key[2],
                "method": key[3],
                "route": key[4],
                "band_id": key[5],
                "sample_count_match": int(matlab_row["sample_count"]) == python_row["sample_count"],
                **differences,
                "source_hash_match": matlab_row["source_sha256"] == python_row["source_sha256"],
                "result": "PASS" if passed else "FAIL",
            }
        )

    comparison_fields = [
        "division",
        "excitation",
        "floor",
        "method",
        "route",
        "band_id",
        "sample_count_match",
        "window_start_difference_s",
        "window_end_difference_s",
        "reference_range_difference_mm",
        "rmse_difference_mm",
        "nrmse_difference_percent",
        "source_hash_match",
        "result",
    ]
    write_csv(output_dir / "nrmse_cross_language_comparison.csv", comparisons, comparison_fields)
    comparison_by_key = {
        (
            row["division"],
            row["excitation"],
            row["floor"],
            row["method"],
            row["route"],
            row["band_id"],
        ): row
        for row in comparisons
    }

    paper_targets: dict[tuple[int, str, int, str], tuple[float, int, str]] = {}
    first_chirp = {
        1: (0.0295, 0.00005),
        2: (1.9950, 0.0079),
        3: (0.6225, 0.0026),
        4: (0.0764, 0.0028),
        5: (0.7452, 0.0505),
    }
    second_chirp = {
        1: (2.9956, 0.0037),
        2: (19.0594, 0.0560),
        3: (14.8760, 0.0296),
        4: (7.4984, 0.0139),
        5: (2.8127, 0.0070),
    }
    for division, values in ((1, first_chirp), (2, second_chirp)):
        for band_id, pair in values.items():
            paper_targets[(division, "Chirp", band_id, "Guyan")] = (pair[0], 4, band_labels[band_id - 1])
            cb_decimals = 5 if division == 1 and band_id == 1 else 4
            paper_targets[(division, "Chirp", band_id, "Craig-Bampton")] = (
                pair[1],
                cb_decimals,
                band_labels[band_id - 1],
            )
    paper_targets[(1, "ElCentro", 0, "Guyan")] = (0.7578, 4, "El Centro full")
    paper_targets[(1, "ElCentro", 0, "Craig-Bampton")] = (0.0058, 4, "El Centro full")
    paper_targets[(2, "ElCentro", 0, "Guyan")] = (10.9355, 4, "El Centro full")
    paper_targets[(2, "ElCentro", 0, "Craig-Bampton")] = (0.0272, 4, "El Centro full")

    groups: dict[tuple[int, str], list[tuple[int, str, float, int, str]]] = defaultdict(list)
    for (division, excitation, band_id, method), (target, decimals, label) in paper_targets.items():
        groups[(division, excitation)].append((band_id, method, target, decimals, label))

    group_rows: list[dict[str, Any]] = []
    inferred_floor: dict[tuple[int, str], int | None] = {}
    for group_key, target_cells in sorted(groups.items()):
        division, excitation = group_key
        floor_scores: dict[int, int] = {}
        floor_abs_sums: dict[int, float] = {}
        for floor in (1, 2, 3):
            score = 0
            difference_sum = 0.0
            for band_id, method, target, decimals, _label in target_cells:
                row = python_by_key[
                    (division, excitation, floor, method, "historical_mean_full_range", band_id)
                ]
                score += int(rounding_match(float(row["nrmse_percent"]), target, decimals))
                difference_sum += abs(float(row["nrmse_percent"]) - target)
            floor_scores[floor] = score
            floor_abs_sums[floor] = difference_sum
        best_score = max(floor_scores.values())
        best_floors = [floor for floor, score in floor_scores.items() if score == best_score]
        selected_floor = best_floors[0] if best_score > 0 and len(best_floors) == 1 else None
        inferred_floor[group_key] = selected_floor
        group_rows.append(
            {
                "division": division,
                "excitation": excitation,
                "target_cell_count": len(target_cells),
                "floor1_rounded_matches": floor_scores[1],
                "floor2_rounded_matches": floor_scores[2],
                "floor3_rounded_matches": floor_scores[3],
                "floor1_absolute_difference_sum": floor_abs_sums[1],
                "floor2_absolute_difference_sum": floor_abs_sums[2],
                "floor3_absolute_difference_sum": floor_abs_sums[3],
                "inferred_uniform_floor": "NONE" if selected_floor is None else selected_floor,
                "best_match_count": best_score,
                "all_cells_match_on_one_floor": best_score == len(target_cells),
                "inference_rule": "unique maximum rounded matches using historical route; no per-cell floor switching",
                "evidence_label": "计算级复现（当前冻结响应；楼层由整组唯一闭合推断）"
                if best_score == len(target_cells) and selected_floor is not None
                else "部分计算闭合/历史值待决定",
            }
        )

    cell_rows: list[dict[str, Any]] = []
    for target_key in sorted(paper_targets):
        division, excitation, band_id, method = target_key
        target, decimals, label = paper_targets[target_key]
        group_floor = inferred_floor[(division, excitation)]
        historical_candidates = [
            python_by_key[(division, excitation, floor, method, "historical_mean_full_range", band_id)]
            for floor in (1, 2, 3)
        ]
        historical_matches = [
            int(row["floor"])
            for row in historical_candidates
            if rounding_match(float(row["nrmse_percent"]), target, decimals)
        ]
        if group_floor is not None:
            selected = python_by_key[
                (division, excitation, group_floor, method, "historical_mean_full_range", band_id)
            ]
            selection_basis = "group_inferred_uniform_floor"
        else:
            selected = min(
                historical_candidates, key=lambda row: abs(float(row["nrmse_percent"]) - target)
            )
            selection_basis = "no_uniform_floor; nearest_historical_reported_only"
        documented_candidates = [
            row
            for row in candidates
            if row["division"] == division
            and row["excitation"] == excitation
            and row["method"] == method
            and row["band_id"] == band_id
        ]
        closest = min(documented_candidates, key=lambda row: abs(float(row["nrmse_percent"]) - target))
        documented_matches = [
            f"{row['route']}@floor{row['floor']}"
            for row in documented_candidates
            if rounding_match(float(row["nrmse_percent"]), target, decimals)
        ]
        selected_key = (
            division,
            excitation,
            int(selected["floor"]),
            method,
            "historical_mean_full_range",
            band_id,
        )
        cross_pass = comparison_by_key[selected_key]["result"] == "PASS"
        selected_match = rounding_match(float(selected["nrmse_percent"]), target, decimals)
        evidence_label = (
            "计算级复现（当前冻结响应+历史脚本口径；作者历史逐点数组待决定）"
            if selected_match and cross_pass
            else "历史值/待决定"
        )
        cell_rows.append(
            {
                "division": division,
                "excitation": excitation,
                "band_id": band_id,
                "frequency_band": label,
                "method": method,
                "paper_value_percent": target,
                "printed_decimals": decimals,
                "group_inferred_floor": "NONE" if group_floor is None else group_floor,
                "reported_floor": selected["floor"],
                "selection_basis": selection_basis,
                "historical_value_percent": selected["nrmse_percent"],
                "historical_rounded_value": float(np.round(selected["nrmse_percent"], decimals)),
                "historical_absolute_difference_percent": abs(float(selected["nrmse_percent"]) - target),
                "historical_rounded_match": selected_match,
                "historical_matching_floors": ";".join(map(str, historical_matches)) or "NONE",
                "closest_documented_route": closest["route"],
                "closest_documented_floor": closest["floor"],
                "closest_documented_value_percent": closest["nrmse_percent"],
                "closest_documented_absolute_difference_percent": abs(
                    float(closest["nrmse_percent"]) - target
                ),
                "closest_documented_rounded_match": rounding_match(
                    float(closest["nrmse_percent"]), target, decimals
                ),
                "all_documented_rounded_matches": ";".join(documented_matches) or "NONE",
                "matlab_python_absolute_difference_percent": comparison_by_key[selected_key][
                    "nrmse_difference_percent"
                ],
                "cross_language_pass": cross_pass,
                "formula": "100*sqrt(mean((x_full-x_red)^2))/(max(x_full)-min(x_full))",
                "normalization_scope": "same floor full 40s reference peak-to-peak",
                "source_file": selected["source_file"],
                "source_sha256": selected["source_sha256"],
                "evidence_label": evidence_label,
            }
        )

    group_fields = list(group_rows[0])
    cell_fields = list(cell_rows[0])
    write_csv(output_dir / "table3_3_group_adjudication.csv", group_rows, group_fields)
    write_csv(output_dir / "table3_3_cell_adjudication.csv", cell_rows, cell_fields)

    summary = {
        "input_files": len(input_checks),
        "total_candidate_rows": len(candidates),
        "historical_candidate_rows": len(historical_rows),
        "historical_chirp_rows": sum(row["excitation"] == "Chirp" for row in historical_rows),
        "historical_elcentro_rows": sum(row["excitation"] == "ElCentro" for row in historical_rows),
        "cross_language_rows": len(comparisons),
        "cross_language_pass_count": sum(row["result"] == "PASS" for row in comparisons),
        "cross_language_fail_count": sum(row["result"] != "PASS" for row in comparisons),
        "maximum_nrmse_absolute_difference_percent": max(
            row["nrmse_difference_percent"] for row in comparisons
        ),
        "maximum_rmse_absolute_difference_mm": max(row["rmse_difference_mm"] for row in comparisons),
        "table3_3_target_cells": len(cell_rows),
        "table3_3_historical_rounded_matches": sum(row["historical_rounded_match"] for row in cell_rows),
        "table3_3_any_documented_rounded_matches": sum(
            row["closest_documented_rounded_match"] for row in cell_rows
        ),
        "table3_3_all_cells_closed": all(row["historical_rounded_match"] for row in cell_rows),
        "group_inferences": {
            f"division{row['division']}_{row['excitation']}": {
                "floor": row["inferred_uniform_floor"],
                "matches": row["best_match_count"],
                "targets": row["target_cell_count"],
            }
            for row in group_rows
        },
        "status": "PASS"
        if all(row["result"] == "PASS" for row in comparisons)
        else "FAIL",
    }
    (output_dir / "nrmse_cross_language_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
