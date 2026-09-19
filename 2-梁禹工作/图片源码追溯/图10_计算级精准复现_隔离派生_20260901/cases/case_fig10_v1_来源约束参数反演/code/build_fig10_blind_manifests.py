#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从冻结的数值物化清单生成B1/B2/B3盲算运行清单。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SCHEMA = "FIG10_BLIND_SEARCH_MANIFEST_V1"
CONTRACTS = ("B1", "B2", "B3")
METHOD_ORDER = {"Original": 0, "Craig_Bampton": 1, "Guyan": 2}
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


class ManifestError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ManifestError(message)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
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


def default_paths() -> tuple[Path, Path, Path]:
    script = Path(__file__).resolve()
    case_root = script.parents[1]
    repo_root = script.parents[5]
    materialization = (
        case_root
        / "data"
        / "numeric_bundles"
        / "gain_scale_1_source_anchor"
        / "materialization_manifest.json"
    )
    return repo_root, case_root, materialization


def normalized_gain_text(raw: Any) -> tuple[str, float]:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:
        raise ManifestError(f"gain_scale不是有效十进制数：{raw}") from exc
    require(value.is_finite(), "gain_scale必须为有限十进制数")
    require(Decimal("0") <= value <= Decimal("1"), "gain_scale必须满足0<=gain_scale<=1")
    normalized = "0" if value == 0 else format(value.normalize(), "f")
    return normalized, float(value)


def derive_gain_contract(source: dict[str, Any]) -> tuple[str, float, str]:
    parameter_contract = source.get("gain_parameter_contract")
    require(isinstance(parameter_contract, dict), "物化清单缺少gain_parameter_contract")
    raw = parameter_contract.get("gain_scale_decimal")
    require(raw is not None, "gain_parameter_contract缺少gain_scale_decimal")
    normalized, numeric = normalized_gain_text(raw)
    require(str(raw) == normalized, "gain_scale_decimal必须是规范化十进制字符串")
    evidence_level = str(parameter_contract.get("evidence_level", ""))
    require(bool(evidence_level), "gain_parameter_contract缺少evidence_level")
    return normalized, numeric, evidence_level


def gain_slug(normalized: str) -> str:
    return normalized.replace("-", "m").replace(".", "p")


def run_suffix_for_gain(normalized: str) -> str:
    status = "SOURCE_ANCHOR" if normalized == "1" else "TARGET_GUIDED_INFERRED"
    return f"GAIN_SCALE_{gain_slug(normalized).upper()}_{status}"


def evidence_level_for_gain(normalized: str) -> str:
    if normalized == "1":
        return "SOURCE_CONSTRAINED_DISCRETE_HYPOTHESIS"
    return "TARGET_GUIDED_INFERRED_GAIN_ON_SOURCE_CONSTRAINED_DISCRETE_HYPOTHESIS"


def default_output_dir(case_root: Path, materialization_path: Path) -> Path:
    numeric_root = (case_root / "data" / "numeric_bundles").resolve()
    try:
        relative_parent = materialization_path.resolve().parent.relative_to(numeric_root)
    except ValueError as exc:
        raise ManifestError(
            f"物化清单必须位于隔离案例的data/numeric_bundles下：{materialization_path}"
        ) from exc
    require(bool(relative_parent.parts), "物化清单必须位于独立的数值包子目录")
    return (case_root / "data" / "blind_manifests" / relative_parent).resolve()


def resolve_repo_path(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()


def sampling_contract() -> dict[str, Any]:
    return {
        "grid": {"l_min": 0, "l_max": 30, "j_min": 0, "j_max": 66},
        "sentinel_points": [list(point) for point in SENTINELS],
        "fixed_sparse_band_points": [
            [l_samples, j_samples]
            for j_samples in SPARSE_COLUMNS
            for l_samples in range(31)
        ],
    }


def build_all(repo_root: Path, materialization_path: Path) -> dict[str, dict[str, Any]]:
    require(materialization_path.is_file(), f"物化清单不存在：{materialization_path}")
    source = json.loads(materialization_path.read_text(encoding="utf-8"))
    require(source.get("status") == "PASS_STAGE0_NUMERIC_MATERIALIZATION", "物化清单状态不是PASS")
    gain_normalized, gain_numeric, _ = derive_gain_contract(source)
    counts = source.get("counts", {})
    new_route_count = int(counts.get("new_numeric_route_bundles", -1))
    require(0 <= new_route_count <= 18, "新数值路线数必须在0至18之间")
    require(
        int(counts.get("stage0_pass", -1)) == new_route_count,
        "Stage0通过数与新数值路线数不一致",
    )
    require(int(counts.get("stage0_fail", -1)) == 0, "Stage0存在失败路线")
    require(int(counts.get("roots_computed", -1)) == 0, "物化阶段不应已求根")
    assignments = source.get("route_assignments")
    require(isinstance(assignments, list) and len(assignments) == 18, "路线赋值必须恰好18条")

    built: dict[str, dict[str, Any]] = {}
    for contract_id in CONTRACTS:
        selected = [row for row in assignments if row.get("global_contract_id") == contract_id]
        require(len(selected) == 6, f"{contract_id}路线数不是6")
        selected.sort(key=lambda row: (int(row["division"]), METHOD_ORDER[str(row["method"])]))
        routes: list[dict[str, Any]] = []
        allowed_roots: set[str] = set()
        effective_hashes: set[str] = set()
        for row in selected:
            row_gain, _ = normalized_gain_text(row.get("gain_scale"))
            require(row_gain == gain_normalized, f"{row.get('assignment_id')}的gain_scale与物化清单不一致")
            path = resolve_repo_path(repo_root, str(row["repo_relative_path"]))
            require(path.is_file(), f"路线包不存在：{path}")
            actual_hash = sha256_file(path)
            expected_hash = str(row["artifact_sha256"]).upper()
            require(actual_hash == expected_hash, f"路线包哈希漂移：{path}")
            action = str(row["assignment_action"])
            operator_layout = (
                "BOARD20_STEP8C_LEGACY_V1"
                if action == "REUSE_BOARD20_R03_ROUTE"
                else "MINIMAL_AUGMENTED_CORE_V1"
            )
            effective_hash = str(row["effective_science_contract_sha256"]).upper()
            effective_hashes.add(effective_hash)
            allowed_roots.add(str(path.parent))
            routes.append(
                {
                    "route_id": str(row["assignment_id"]),
                    "contract_id": contract_id,
                    "contract_hash": effective_hash,
                    "division": int(row["division"]),
                    "method": str(row["method"]),
                    "dimension": int(row["dimension"]),
                    "operator_layout": operator_layout,
                    "bundle_path": str(path),
                    "bundle_sha256": actual_hash,
                    "assignment_action": action,
                    "source_route_id": str(row["source_route_id"]),
                    "route_operator_sha256": str(row["route_operator_sha256"]).upper(),
                    "stage0_status": str(row["stage0_status"]),
                }
            )
        require(len(effective_hashes) == 1, f"{contract_id}有效科学合同哈希不唯一")
        manifest = {
            "schema_version": SCHEMA,
            "run_id": f"FIG10_{contract_id}_{run_suffix_for_gain(gain_normalized)}",
            "evidence_level": evidence_level_for_gain(gain_normalized),
            "target_dependency": "FORBIDDEN_BLIND_CALCULATION_ONLY",
            "gain_scale": gain_numeric,
            "source_materialization_manifest": str(materialization_path.resolve()),
            "source_materialization_sha256": sha256_file(materialization_path),
            "allowed_bundle_roots": sorted(allowed_roots),
            "sampling": sampling_contract(),
            "routes": routes,
        }
        built[contract_id] = manifest
    return built


def expected_outputs(built: dict[str, dict[str, Any]]) -> dict[str, bytes]:
    payloads = {f"{contract_id}.json": canonical_bytes(manifest) for contract_id, manifest in built.items()}
    index = {
        "schema_version": "FIG10_BLIND_MANIFEST_INDEX_V1",
        "status": "PASS",
        "scientific_search_executed": False,
        "contract_count": len(payloads),
        "route_count": sum(len(value["routes"]) for value in built.values()),
        "sentinel_points_per_route": len(SENTINELS),
        "sparse_band_points_per_route": 31 * len(SPARSE_COLUMNS),
        "full_grid_points_per_route": 31 * 67,
        "files": [
            {"name": name, "bytes": len(payload), "sha256": sha256_bytes(payload)}
            for name, payload in sorted(payloads.items())
        ],
    }
    payloads["manifest_index.json"] = canonical_bytes(index)
    return payloads


def main() -> int:
    repo_default, case_root, materialization_default = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_default)
    parser.add_argument("--materialization-manifest", type=Path, default=materialization_default)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="隔离输出目录；省略时从物化清单相对data/numeric_bundles的目录动态派生。",
    )
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    materialization = args.materialization_manifest.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else default_output_dir(case_root, materialization)
    )
    try:
        output_dir.relative_to(case_root.resolve())
    except ValueError as exc:
        raise ManifestError("输出目录必须位于板块28隔离案例内") from exc
    built = build_all(repo_root, materialization)
    payloads = expected_outputs(built)
    if args.verify_existing:
        for name, payload in payloads.items():
            path = output_dir / name
            require(path.is_file(), f"待验证清单不存在：{path}")
            require(path.read_bytes() == payload, f"清单内容漂移：{path}")
        action = "VERIFY_EXISTING"
    else:
        for name, payload in payloads.items():
            atomic_write(output_dir / name, payload)
        action = "WRITE"
    result = {
        "status": "PASS",
        "action": action,
        "output_dir": str(output_dir),
        "contract_count": 3,
        "route_count": 18,
        "sentinel_total_points": 3 * 6 * len(SENTINELS),
        "sparse_band_total_points": 3 * 6 * 31 * len(SPARSE_COLUMNS),
        "full_grid_total_points": 3 * 6 * 31 * 67,
        "files": [
            {"name": name, "sha256": sha256_bytes(payload), "bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
