#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块28：生成不读取目标的Fig10离散科学合同骨架。

本文件当前只完成合同层：

* 从板块20已验证的R03科学合同派生B1、B2、B3；
* 登记R03六路线既有数值包和全网格验证证据，明确禁止重复计算；
* 计算规范化科学合同SHA-256并拒绝与R01至R04重复的新骨架；
* 不装配新数值矩阵、不求根、不扫描时滞网格、不执行参数搜索。

允许的只读输入由 ``contracts/known_board20_contracts.json`` 的冻结哈希白名单
唯一确定，全部位于板块20。脚本不接受任意科学输入路径。
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "fig10-contract-v1"
INDEX_VERSION = "fig10-contract-index-v1"

SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
CONTRACTS_DIR = CASE_DIR / "contracts"
SCHEMA_PATH = CONTRACTS_DIR / "fig10_contract_schema.json"
KNOWN_REGISTRY_PATH = CONTRACTS_DIR / "known_board20_contracts.json"
DEFAULT_OUTPUT_DIR = CASE_DIR / "data" / "contract_layer"

METHOD_ORDER = ("Original", "Guyan", "Craig_Bampton")
EXPECTED_DIMENSIONS = {
    1: {"Original": 15, "Guyan": 6, "Craig_Bampton": 9},
    2: {"Original": 15, "Guyan": 5, "Craig_Bampton": 8},
}

OUTSIDE_FEEDBACK_FORMULA = "S_L^T [v(z) DeltaC + DeltaK] S_R"
OUTSIDE_BUNDLE_RULE = (
    "not_applicable; active physical delay factors remain W_C and W_K; "
    "projected feedback is external"
)
INSIDE_FEEDBACK_FORMULA = (
    "S_L^T H(z) [v(z) (W_C + DeltaC S_R) + "
    "(W_K + DeltaK S_R)]"
)
INSIDE_BUNDLE_RULE = (
    "W_C_active = W_C + DeltaC S_R; W_K_active = W_K + DeltaK S_R; "
    "projected feedback is retained for audit; external feedback matrices are zero"
)

RECORD_KEYS = {
    "schema_version",
    "contract_id",
    "record_kind",
    "label_cn",
    "evidence_level",
    "search_action",
    "materialization_status",
    "scientific_contract",
    "contract_hash",
    "source_basis",
    "difference_from_r03",
    "route_bundle_plan",
    "reuse_evidence",
    "notes",
}


class ContractError(RuntimeError):
    """合同、来源或确定性验证失败。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def canonical_json_bytes(value: Any) -> bytes:
    """返回科学合同哈希使用的唯一UTF-8 JSON字节序列。"""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def science_contract_sha256(scientific_contract: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(scientific_contract))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON顶层必须为对象：{path}")
    return value


def find_repo_root() -> Path:
    for candidate in (SCRIPT_DIR, *SCRIPT_DIR.parents):
        if (candidate / "WORKFLOW.md").is_file() and (candidate / "test").is_dir():
            return candidate.resolve()
    raise ContractError("无法从脚本位置定位项目根目录")


def resolve_repo_relative(repo_root: Path, relative_text: str) -> Path:
    relative = Path(relative_text)
    require(not relative.is_absolute(), f"来源路径不得为绝对路径：{relative_text}")
    require(".." not in relative.parts, f"来源路径不得包含父目录跳转：{relative_text}")
    resolved = (repo_root / relative).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ContractError(f"来源路径越出项目根目录：{relative_text}") from exc
    return resolved


def set_nested(value: dict[str, Any], dotted_path: str, new_value: Any) -> None:
    parts = dotted_path.split(".")
    require(all(parts), f"无效覆盖路径：{dotted_path}")
    cursor: Any = value
    for part in parts[:-1]:
        require(isinstance(cursor, dict) and part in cursor, f"覆盖路径不存在：{dotted_path}")
        cursor = cursor[part]
    require(isinstance(cursor, dict) and parts[-1] in cursor, f"覆盖路径不存在：{dotted_path}")
    cursor[parts[-1]] = copy.deepcopy(new_value)


def verify_schema_file() -> dict[str, Any]:
    schema = load_json(SCHEMA_PATH)
    require(
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "Fig10合同模式不是JSON Schema draft 2020-12",
    )
    require(schema.get("additionalProperties") is False, "合同模式必须拒绝顶层额外字段")
    require(set(schema.get("required", [])) == RECORD_KEYS, "合同模式顶层必填字段集合不符")
    require("scientific_contract" in schema.get("$defs", {}), "合同模式缺少scientific_contract定义")
    return schema


def verify_source_fingerprints(
    registry: dict[str, Any], repo_root: Path
) -> dict[str, Path]:
    sources = registry.get("source_fingerprints")
    require(isinstance(sources, list) and sources, "已知合同登记表缺少来源指纹")
    resolved_by_id: dict[str, Path] = {}
    board20_prefix = (
        repo_root
        / "test"
        / "00_失败尝试与候选路线"
        / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
    ).resolve()

    for item in sources:
        require(isinstance(item, dict), "来源指纹条目必须为对象")
        source_id = item.get("source_id")
        relative_text = item.get("repo_relative_path")
        expected_hash = item.get("sha256")
        require(isinstance(source_id, str) and source_id, "来源指纹缺少source_id")
        require(source_id not in resolved_by_id, f"重复来源ID：{source_id}")
        require(isinstance(relative_text, str), f"来源{source_id}缺少相对路径")
        require(
            isinstance(expected_hash, str)
            and len(expected_hash) == 64
            and expected_hash == expected_hash.lower(),
            f"来源{source_id}的SHA-256格式无效",
        )
        path = resolve_repo_relative(repo_root, relative_text)
        try:
            path.relative_to(board20_prefix)
        except ValueError as exc:
            raise ContractError(f"合同生成器只允许读取板块20来源：{relative_text}") from exc
        require(path.is_file(), f"冻结来源缺失：{path}")
        actual_hash = sha256_file(path)
        require(
            actual_hash == expected_hash,
            f"冻结来源哈希不符：{source_id}; actual={actual_hash}; expected={expected_hash}",
        )
        resolved_by_id[source_id] = path
    return resolved_by_id


def validate_channel_contract(value: Any, division: int) -> None:
    require(isinstance(value, dict), f"division_{division}通道合同必须为对象")
    require(set(value) == {"coordinates", "local_selector_zero_based"}, "通道合同字段不闭合")
    coordinates = value["coordinates"]
    selector = value["local_selector_zero_based"]
    require(isinstance(coordinates, list) and len(coordinates) == 2, "通道坐标必须恰有两个")
    require(isinstance(selector, list) and len(selector) == 2, "局部选择行必须恰有两个")
    require(coordinates[0] == "psi1" and selector[0] == 0, "第一作动通道必须为psi1/局部第0行")
    if division == 1:
        require(coordinates == ["psi1", "psi6"], "第一类合同只允许psi1/psi6")
        require(selector == [0, 3], "第一类psi1/psi6局部选择应为[0,3]")
    else:
        allowed = {
            ("psi1", "psi6"): (0, 3),
            ("psi1", "psi11"): (0, 6),
        }
        require(tuple(coordinates) in allowed, "第二类只允许psi1/psi6或psi1/psi11")
        require(tuple(selector) == allowed[tuple(coordinates)], "第二类坐标与局部选择行不一致")


def validate_scientific_contract(science: dict[str, Any]) -> None:
    expected_keys = {
        "matrix_package",
        "controller",
        "integration",
        "sampling",
        "actuation_and_delay_channels",
        "controller_channels",
        "delay_and_feedback",
        "stability_classification",
    }
    require(set(science) == expected_keys, "科学合同字段集合不闭合")

    matrix = science["matrix_package"]
    require(matrix["id"] == "BOARD20_STEP8B_SUFFIX2_SUFFIX3", "未知矩阵包")
    require(
        matrix["frozen_mat_sha256"]
        == "261852003eea79a6c7c609c472e82b8782bb7619191c2cfa3759ac39efcc80ff",
        "冻结矩阵哈希不符",
    )
    require(
        matrix["division_method_dimensions"]
        == {"division_1": EXPECTED_DIMENSIONS[1], "division_2": EXPECTED_DIMENSIONS[2]},
        "板块20矩阵路线维数不符",
    )
    require(matrix["guyan_projection"] == "standard_congruence_TtAT", "当前骨架必须使用标准Guyan")
    require(matrix["craig_bampton_mode_count"] == 3, "当前矩阵包应保留三个CB模态")
    require(
        matrix["article_dimension_contract_status"]
        == "BOARD20_NUMERIC_PACKAGE_IS_NOT_ARTICLE_6_AND_12_MODEL",
        "必须保留文章6/12维矩阵尚未闭合的声明",
    )

    controller = science["controller"]
    require(controller["solver"] == "CARE", "B1/B2/B3基线控制器必须为CARE")
    require(
        controller["state_order"] == ["q1", "q2", "qdot1", "qdot2"],
        "控制状态顺序不符",
    )
    require(controller["Q_diagonal"] == [1000000, 1000000, 10000, 10000], "CARE Q不符")
    require(controller["R_diagonal"] == [0.01, 0.01], "CARE R不符")
    if controller["input_semantics"] == "generalized_force":
        require(controller["B_lower_block"] == "M_inverse", "广义力输入必须使用M_inverse")
        require(controller["force_embedding"] == "gain_direct", "广义力增益不得再次乘质量")
    elif controller["input_semantics"] == "acceleration":
        require(controller["B_lower_block"] == "identity", "加速度输入必须使用identity")
        require(
            controller["force_embedding"] == "left_multiply_local_mass",
            "加速度增益必须乘局部质量换算为力反馈",
        )
    else:
        raise ContractError("未知控制输入语义")
    require(
        controller["local_matrix_contract"]
        == "standard_static_projection_of_full_local_MCK_on_actuation_coordinates",
        "局部控制器必须与作动坐标同步重建",
    )

    integration = science["integration"]
    if integration["mode"] == "route_matrix_al":
        require(integration["alpha"] is None, "矩阵al合同不得同时激活标量alpha")
        require(integration["al_formula"] == "solve(4M+2dtC+dt^2K,4M)", "矩阵al公式不符")
        require(integration["mass_operator"] == "M/al", "矩阵al质量项不符")
    elif integration["mode"] == "scalar_alpha_0p25":
        require(integration["alpha"] == 0.25, "标量alpha必须为0.25")
        require(integration["al_formula"] is None, "标量alpha合同不得激活矩阵al")
        require(integration["mass_operator"] == "M/alpha", "标量alpha质量项不符")
    else:
        raise ContractError("未知积分合同")

    sampling = science["sampling"]
    require(sampling["dt_seconds"] == {"numerator": 1, "denominator": 1024}, "采样周期必须为1/1024 s")
    require(sampling["delay_grid_status"] == "NOT_ASSIGNED_BY_CONTRACT_LAYER", "合同层不得分配搜索网格")

    actuation = science["actuation_and_delay_channels"]
    controller_channels = science["controller_channels"]
    require(set(actuation) == {"division_1", "division_2"}, "作动通道划分字段不闭合")
    require(controller_channels == actuation, "控制器坐标必须与作动/时延坐标完全一致")
    validate_channel_contract(actuation["division_1"], 1)
    validate_channel_contract(actuation["division_2"], 2)

    delay = science["delay_and_feedback"]
    require(delay["delay_orientation"] == "H_LEFT", "当前三个骨架只允许H左乘")
    require(
        delay["channel_to_delay_exponent"] == {"channel_1": "l", "channel_2": "j"},
        "通道到时滞指数映射不符",
    )
    if delay["feedback_placement"] == "OUTSIDE_H":
        require(delay["feedback_formula"] == OUTSIDE_FEEDBACK_FORMULA, "H外反馈公式不符")
        require(delay["inside_bundle_rule"] == OUTSIDE_BUNDLE_RULE, "H外活动因子规则不符")
    elif delay["feedback_placement"] == "INSIDE_H":
        require(delay["feedback_formula"] == INSIDE_FEEDBACK_FORMULA, "H内反馈公式不符")
        require(delay["inside_bundle_rule"] == INSIDE_BUNDLE_RULE, "H内活动因子规则不符")
    else:
        raise ContractError("未知反馈位置")

    stability = science["stability_classification"]
    require(stability["quantity"] == "maximum_modulus_of_physical_roots", "稳定量定义不符")
    require(stability["stable_rule"] == "rho < 1", "稳定分类必须严格小于1")
    require(stability["critical_rule"] == "abs(rho - 1) <= 1e-9", "临界规则不符")
    require(stability["grid_assignment"] == "NOT_PART_OF_CONTRACT_LAYER", "合同层不得写入网格")


def realize_known_contracts(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base = registry.get("base_scientific_contract_r03")
    require(isinstance(base, dict), "已知合同登记表缺少R03基线")
    records = registry.get("fullgrid_known_contracts")
    require(isinstance(records, list), "已知合同登记表缺少全网格合同")
    require([item.get("contract_id") for item in records] == ["R01", "R02", "R03", "R04"], "全网格合同必须按R01至R04登记")

    realized: dict[str, dict[str, Any]] = {}
    seen_hashes: set[str] = set()
    for item in records:
        contract_id = item["contract_id"]
        science = copy.deepcopy(base)
        for override in item.get("overrides_from_r03", []):
            set_nested(science, override["path"], override["value"])
        validate_scientific_contract(science)
        actual_hash = science_contract_sha256(science)
        require(actual_hash == item.get("contract_hash"), f"{contract_id}科学合同哈希不符")
        require(actual_hash not in seen_hashes, f"R01至R04存在重复科学合同：{contract_id}")
        seen_hashes.add(actual_hash)
        realized[contract_id] = science

    diagnostics = registry.get("non_fullgrid_diagnostics")
    require(isinstance(diagnostics, list), "缺少R05/R06非全网格边界记录")
    require([item.get("contract_id") for item in diagnostics] == ["R05", "R06"], "非全网格诊断必须为R05/R06")
    for item in diagnostics:
        require(item.get("coverage_status") == "BUNDLES_BUILT_FULLGRID_POINTS_ZERO", "R05/R06不得误记为全网格")
    return realized


def make_inside_feedback(science: dict[str, Any]) -> None:
    delay = science["delay_and_feedback"]
    delay["feedback_placement"] = "INSIDE_H"
    delay["feedback_formula"] = INSIDE_FEEDBACK_FORMULA
    delay["inside_bundle_rule"] = INSIDE_BUNDLE_RULE


def make_division2_psi11(science: dict[str, Any]) -> None:
    channel = {
        "coordinates": ["psi1", "psi11"],
        "local_selector_zero_based": [0, 6],
    }
    science["actuation_and_delay_channels"]["division_2"] = copy.deepcopy(channel)
    science["controller_channels"]["division_2"] = copy.deepcopy(channel)


def route_plan(contract_id: str, science: dict[str, Any]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for division in (1, 2):
        for method in METHOD_ORDER:
            if contract_id == "B1" and division == 1:
                action = "REUSE_EXISTING_R03_ROUTE"
                reuse_from: str | None = f"D1_{method}_R03"
            elif contract_id == "B3" and division == 1:
                action = "REUSE_B2_ROUTE_AFTER_MATERIALIZATION"
                reuse_from = f"B2_D1_{method}"
            else:
                action = "MATERIALIZE_LATER"
                reuse_from = None
            plans.append(
                {
                    "bundle_plan_id": f"{contract_id}_D{division}_{method}",
                    "division": division,
                    "method": method,
                    "dimension": science["matrix_package"]["division_method_dimensions"][f"division_{division}"][method],
                    "matrix_source_contract": "BOARD20_STEP8B_SUFFIX2_SUFFIX3",
                    "materialization_status": "CONTRACT_ONLY_NOT_MATERIALIZED",
                    "operator_action": action,
                    "reuse_from": reuse_from,
                    "route_operator_sha256": None,
                }
            )
    return plans


def diff_entry(field: str, r03_value: Any, candidate_value: Any) -> dict[str, Any]:
    return {
        "field": field,
        "r03_value": copy.deepcopy(r03_value),
        "candidate_value": copy.deepcopy(candidate_value),
        "classification": "SOURCE_DISCRETE_FACTOR",
    }


def source_basis_for(contract_id: str) -> list[dict[str, str]]:
    if contract_id == "B1":
        return [
            {
                "classification": "SOURCE",
                "source_id": "board20_conflict_adjudication",
                "pointer": "C08 and C14",
                "claim": "当前文章第二类作动坐标为psi1/psi11；局部九维坐标对应选择行[0,6]。",
            },
            {
                "classification": "VERIFIED_PRIOR_COMPUTATION",
                "source_id": "board20_r03",
                "pointer": "R03 fullgrid contract",
                "claim": "R03提供CARE、论文Q/R、广义力、逐路线矩阵al、标准Guyan、H左乘和H外反馈基线。",
            },
            {
                "classification": "INFERENCE",
                "source_id": "board28_factor_isolation",
                "pointer": "B1 design decision",
                "claim": "psi11与H外反馈的组合用于隔离通道因素，并非已恢复的作者完整合同。",
            },
        ]
    if contract_id == "B2":
        return [
            {
                "classification": "SOURCE",
                "source_id": "board20_conflict_adjudication",
                "pointer": "C05",
                "claim": "当前文章将LQR反馈放在时滞矩阵H内。",
            },
            {
                "classification": "VERIFIED_PRIOR_COMPUTATION",
                "source_id": "board20_r03",
                "pointer": "R03 fullgrid contract",
                "claim": "R03提供psi1/psi6及其余不变基线。",
            },
            {
                "classification": "INFERENCE",
                "source_id": "board28_factor_isolation",
                "pointer": "B2 design decision",
                "claim": "psi1/psi6与H内反馈的组合用于隔离反馈位置，并非已恢复的作者完整合同。",
            },
        ]
    if contract_id == "B3":
        return [
            {
                "classification": "SOURCE",
                "source_id": "board20_conflict_adjudication",
                "pointer": "C05, C08 and C14",
                "claim": "当前文章同时采用第二类psi1/psi11与H内反馈。",
            },
            {
                "classification": "VERIFIED_PRIOR_COMPUTATION",
                "source_id": "board20_r03",
                "pointer": "R03 fullgrid contract",
                "claim": "CARE、论文Q/R、广义力、逐路线矩阵al和标准Guyan继承自R03。",
            },
            {
                "classification": "INFERENCE",
                "source_id": "board28_matrix_carryover",
                "pointer": "B3 design boundary",
                "claim": "文章算子搭载板块20的15/6/9与15/5/8维矩阵链；文章6/12维数值矩阵尚未闭合。",
            },
        ]
    if contract_id == "R03_REUSE":
        return [
            {
                "classification": "VERIFIED_PRIOR_COMPUTATION",
                "source_id": "board20_bundle_index",
                "pointer": "six R03 bundle rows",
                "claim": "R03六路线数值包均已生成并通过包级检查。",
            },
            {
                "classification": "VERIFIED_PRIOR_COMPUTATION",
                "source_id": "board20_fullgrid_validation",
                "pointer": "PASS validation summary",
                "claim": "R03已包含在板块20六路线31乘67跨语言全网格验证中，不得重复运行。",
            },
        ]
    raise ContractError(f"未知合同ID：{contract_id}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_r03_reuse_evidence(
    registry: dict[str, Any], repo_root: Path, sources: dict[str, Path]
) -> dict[str, Any]:
    index_path = sources["board20_bundle_index"]
    statistics_path = sources["board20_fullgrid_route_statistics"]
    validation_path = sources["board20_fullgrid_validation"]

    index_rows = [row for row in read_csv_rows(index_path) if row.get("candidate_id") == "R03"]
    stats_rows = [row for row in read_csv_rows(statistics_path) if row.get("candidate_id") == "R03"]
    require(len(index_rows) == 6, f"R03包索引应有6行，实际{len(index_rows)}行")
    require(len(stats_rows) == 6, f"R03全网格统计应有6行，实际{len(stats_rows)}行")
    stats_by_bundle = {row["bundle_id"]: row for row in stats_rows}
    require(len(stats_by_bundle) == 6, "R03全网格统计bundle_id不唯一")

    expected_pairs = [(division, method) for division in (1, 2) for method in METHOD_ORDER]
    index_by_pair = {(int(row["division"]), row["method"]): row for row in index_rows}
    require(set(index_by_pair) == set(expected_pairs), "R03六路线身份不闭合")

    bundles: list[dict[str, Any]] = []
    for division, method in expected_pairs:
        row = index_by_pair[(division, method)]
        bundle_id = row["bundle_id"]
        require(row["overall_pass"].strip().lower() == "true", f"R03包未通过：{bundle_id}")
        require(int(row["dimension"]) == EXPECTED_DIMENSIONS[division][method], f"R03维数不符：{bundle_id}")
        bundle_path = (index_path.parent / Path(row["relative_path"])).resolve()
        try:
            bundle_relative = bundle_path.relative_to(repo_root).as_posix()
        except ValueError as exc:
            raise ContractError(f"R03包越出项目根目录：{bundle_path}") from exc
        require(bundle_path.is_file(), f"R03包缺失：{bundle_path}")
        expected_bundle_hash = row["mat_sha256"].lower()
        actual_bundle_hash = sha256_file(bundle_path)
        require(actual_bundle_hash == expected_bundle_hash, f"R03包哈希不符：{bundle_id}")
        stat = stats_by_bundle[bundle_id]
        bundles.append(
            {
                "bundle_id": bundle_id,
                "division": division,
                "method": method,
                "dimension": int(row["dimension"]),
                "repo_relative_path": bundle_relative,
                "mat_sha256": actual_bundle_hash,
                "overall_pass": True,
                "stable_point_count": int(stat["stable_point_count"]),
                "critical_point_count": int(stat["critical_point_count"]),
                "rightmost_stable_j": int(stat["rightmost_stable_j"]),
                "maximum_rho_difference": float(stat["maximum_rho_difference"]),
            }
        )

    validation = load_json(validation_path)
    require(validation.get("status") == "PASS", "板块20全网格验证摘要不是PASS")
    grid = registry["grid_contract"]
    require(grid["points_per_candidate"] == 12462, "R03六路线全网格点数合同不符")
    return {
        "source_candidate_id": "R03",
        "fullgrid_status": "PASS_FULLGRID_DUAL_SOLVER_SHARED_CERTIFICATE",
        "fullgrid_point_count": 12462,
        "rerun_policy": "DO_NOT_RERUN_KNOWN_CONTRACT",
        "route_bundles": bundles,
    }


def validate_route_plan(plans: Any) -> None:
    require(isinstance(plans, list) and len(plans) == 6, "新骨架必须有六条路线计划")
    pairs = {(item["division"], item["method"]) for item in plans}
    require(pairs == {(division, method) for division in (1, 2) for method in METHOD_ORDER}, "六路线计划身份不闭合")
    for item in plans:
        division = item["division"]
        method = item["method"]
        require(item["dimension"] == EXPECTED_DIMENSIONS[division][method], "路线计划维数不符")
        require(item["route_operator_sha256"] is None, "合同层不得预填路线求解算子哈希")


def validate_record(record: dict[str, Any]) -> None:
    require(set(record) == RECORD_KEYS, f"{record.get('contract_id')}顶层字段集合不闭合")
    require(record["schema_version"] == SCHEMA_VERSION, "合同模式版本不符")
    validate_scientific_contract(record["scientific_contract"])
    require(
        record["contract_hash"] == science_contract_sha256(record["scientific_contract"]),
        f"{record['contract_id']}科学合同哈希不符",
    )
    require(isinstance(record["source_basis"], list) and record["source_basis"], "合同缺少来源/推断标记")
    for item in record["source_basis"]:
        require(item["classification"] in {"SOURCE", "VERIFIED_PRIOR_COMPUTATION", "INFERENCE"}, "来源分类无效")
    if record["record_kind"] == "NEW_SKELETON":
        require(record["search_action"] == "MATERIALIZE_LATER_NO_SEARCH", "新骨架当前不得搜索")
        require(record["materialization_status"] == "CONTRACT_ONLY_NOT_MATERIALIZED", "新骨架不得伪称已物化")
        require(record["reuse_evidence"] is None, "新骨架不得携带R03复用证据")
        validate_route_plan(record["route_bundle_plan"])
    elif record["record_kind"] == "KNOWN_REUSE":
        require(record["search_action"] == "REUSE_EXISTING_NO_RERUN", "R03必须登记为不重跑")
        require(record["materialization_status"] == "EXISTING_BOARD20_BUNDLES_REUSED", "R03复用状态不符")
        require(record["route_bundle_plan"] == [], "R03复用记录不得生成新路线计划")
        evidence = record["reuse_evidence"]
        require(isinstance(evidence, dict), "R03复用记录缺少既有证据")
        require(len(evidence["route_bundles"]) == 6, "R03复用必须闭合六个包")
        require(evidence["fullgrid_point_count"] == 12462, "R03复用全网格点数不符")
    else:
        raise ContractError("未知记录类型")


def make_new_record(
    contract_id: str,
    label_cn: str,
    evidence_level: str,
    science: dict[str, Any],
    differences: list[dict[str, Any]],
    notes: list[str],
) -> dict[str, Any]:
    record = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": contract_id,
        "record_kind": "NEW_SKELETON",
        "label_cn": label_cn,
        "evidence_level": evidence_level,
        "search_action": "MATERIALIZE_LATER_NO_SEARCH",
        "materialization_status": "CONTRACT_ONLY_NOT_MATERIALIZED",
        "scientific_contract": science,
        "contract_hash": science_contract_sha256(science),
        "source_basis": source_basis_for(contract_id),
        "difference_from_r03": differences,
        "route_bundle_plan": route_plan(contract_id, science),
        "reuse_evidence": None,
        "notes": notes,
    }
    validate_record(record)
    return record


def build_records() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Path]]:
    verify_schema_file()
    registry = load_json(KNOWN_REGISTRY_PATH)
    require(registry.get("registry_version") == "known-board20-contracts-v1", "已知合同登记表版本不符")
    repo_root = find_repo_root()
    sources = verify_source_fingerprints(registry, repo_root)
    known = realize_known_contracts(registry)
    r03 = known["R03"]

    b1_science = copy.deepcopy(r03)
    make_division2_psi11(b1_science)
    b1_differences = [
        diff_entry(
            "actuation_and_delay_channels.division_2",
            r03["actuation_and_delay_channels"]["division_2"],
            b1_science["actuation_and_delay_channels"]["division_2"],
        ),
        diff_entry(
            "controller_channels.division_2",
            r03["controller_channels"]["division_2"],
            b1_science["controller_channels"]["division_2"],
        ),
    ]
    b1 = make_new_record(
        "B1",
        "第二类psi1/psi11与H外反馈骨架",
        "SOURCE_FACTORS_COMBINED_DIAGNOSTIC",
        b1_science,
        b1_differences,
        [
            "只隔离第二类通道因素；第一类三路线的求解算子应直接复用R03。",
            "第二类控制器局部M/C/K必须以[0,6]从完整九维局部矩阵重新做标准静力投影。",
        ],
    )

    b2_science = copy.deepcopy(r03)
    make_inside_feedback(b2_science)
    b2_differences = [
        diff_entry(
            "delay_and_feedback.feedback_placement",
            r03["delay_and_feedback"]["feedback_placement"],
            b2_science["delay_and_feedback"]["feedback_placement"],
        ),
        diff_entry(
            "delay_and_feedback.feedback_formula",
            r03["delay_and_feedback"]["feedback_formula"],
            b2_science["delay_and_feedback"]["feedback_formula"],
        ),
        diff_entry(
            "delay_and_feedback.inside_bundle_rule",
            r03["delay_and_feedback"]["inside_bundle_rule"],
            b2_science["delay_and_feedback"]["inside_bundle_rule"],
        ),
    ]
    b2 = make_new_record(
        "B2",
        "psi1/psi6与H内反馈骨架",
        "SOURCE_FACTORS_COMBINED_DIAGNOSTIC",
        b2_science,
        b2_differences,
        [
            "只隔离反馈位置因素；物理时延矩阵与含反馈活动时延矩阵必须分别保存和验收。",
            "H内物化时外部反馈矩阵必须置零，但投影反馈矩阵仍需作为审计字段保留。",
        ],
    )

    b3_science = copy.deepcopy(r03)
    make_division2_psi11(b3_science)
    make_inside_feedback(b3_science)
    b3_differences = [
        diff_entry(
            "actuation_and_delay_channels.division_2",
            r03["actuation_and_delay_channels"]["division_2"],
            b3_science["actuation_and_delay_channels"]["division_2"],
        ),
        diff_entry(
            "controller_channels.division_2",
            r03["controller_channels"]["division_2"],
            b3_science["controller_channels"]["division_2"],
        ),
        diff_entry(
            "delay_and_feedback.feedback_placement",
            r03["delay_and_feedback"]["feedback_placement"],
            b3_science["delay_and_feedback"]["feedback_placement"],
        ),
        diff_entry(
            "delay_and_feedback.feedback_formula",
            r03["delay_and_feedback"]["feedback_formula"],
            b3_science["delay_and_feedback"]["feedback_formula"],
        ),
        diff_entry(
            "delay_and_feedback.inside_bundle_rule",
            r03["delay_and_feedback"]["inside_bundle_rule"],
            b3_science["delay_and_feedback"]["inside_bundle_rule"],
        ),
    ]
    b3 = make_new_record(
        "B3",
        "当前文章通道与H内反馈算子骨架搭载板块20矩阵链",
        "ARTICLE_FORMULA_ON_BOARD20_MATRIX_PACKAGE_DIAGNOSTIC",
        b3_science,
        b3_differences,
        [
            "B3最接近当前文章的通道与反馈位置，但仍不是文章6/12维数值模型。",
            "第一类三路线与B2相同，待B2物化后应按路线求解算子哈希复用。",
        ],
    )

    r03_reuse = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": "R03_REUSE",
        "record_kind": "KNOWN_REUSE",
        "label_cn": "板块20 R03既有六路线全网格复用记录",
        "evidence_level": "BOARD20_FULLGRID_VERIFIED_REUSE",
        "search_action": "REUSE_EXISTING_NO_RERUN",
        "materialization_status": "EXISTING_BOARD20_BUNDLES_REUSED",
        "scientific_contract": copy.deepcopy(r03),
        "contract_hash": science_contract_sha256(r03),
        "source_basis": source_basis_for("R03_REUSE"),
        "difference_from_r03": [
            {
                "field": "scientific_contract",
                "r03_value": "same_scientific_contract",
                "candidate_value": "same_scientific_contract",
                "classification": "NO_CHANGE_REUSE",
            }
        ],
        "route_bundle_plan": [],
        "reuse_evidence": build_r03_reuse_evidence(registry, repo_root, sources),
        "notes": [
            "本记录只复用既有六个R03数值包和既有全网格结果，不触发求根或网格计算。",
            "R03保留为已知基线，不能改名为板块28新候选。",
        ],
    }
    validate_record(r03_reuse)

    records = [b1, b2, b3, r03_reuse]
    hashes = [record["contract_hash"] for record in records]
    known_hashes = {science_contract_sha256(value) for value in known.values()}
    for record in (b1, b2, b3):
        require(
            record["contract_hash"] not in known_hashes,
            f"{record['contract_id']}与板块20 R01至R04重复，应拒绝而不是重跑",
        )
    require(len(set(hashes[:3])) == 3, "B1/B2/B3科学合同哈希必须互异")
    require(r03_reuse["contract_hash"] == science_contract_sha256(known["R03"]), "R03复用哈希必须等于已知R03")
    return records, registry, sources


def expected_output_files() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    records, registry, sources = build_records()
    files: dict[str, bytes] = {}
    index_rows: list[dict[str, Any]] = []
    for record in records:
        filename = f"{record['contract_id']}.json"
        payload = pretty_json_bytes(record)
        files[filename] = payload
        index_rows.append(
            {
                "contract_id": record["contract_id"],
                "record_kind": record["record_kind"],
                "science_contract_sha256": record["contract_hash"],
                "record_file": filename,
                "artifact_sha256": sha256_bytes(payload),
                "search_action": record["search_action"],
                "materialization_status": record["materialization_status"],
            }
        )

    index = {
        "index_version": INDEX_VERSION,
        "mode": "CONTRACT_LAYER_ONLY_NO_NUMERIC_BUNDLE_NO_GRID_NO_PARAMETER_SEARCH",
        "generator": "code/build_fig10_candidate_bundles.py",
        "schema_sha256": sha256_file(SCHEMA_PATH),
        "known_registry_sha256": sha256_file(KNOWN_REGISTRY_PATH),
        "verified_source_fingerprints": [
            {
                "source_id": item["source_id"],
                "sha256": item["sha256"],
            }
            for item in registry["source_fingerprints"]
        ],
        "record_files": index_rows,
        "counts": {
            "new_skeletons": 3,
            "known_reuse_records": 1,
            "numeric_bundles_materialized": 0,
            "grid_points_computed": 0,
            "parameter_candidates_run": 0,
        },
        "source_dependency_count": len(sources),
    }
    files["contract_index.json"] = pretty_json_bytes(index)
    return files, index_rows


def write_files_atomic(output_dir: Path, files: dict[str, bytes]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in files.items():
        require(Path(filename).name == filename, f"输出文件名无效：{filename}")
        destination = output_dir / filename
        temporary = output_dir / f".{filename}.tmp"
        temporary.write_bytes(payload)
        temporary.replace(destination)


def verify_existing_files(output_dir: Path, files: dict[str, bytes]) -> None:
    for filename, expected in files.items():
        path = output_dir / filename
        require(path.is_file(), f"合同输出缺失：{path}")
        actual = path.read_bytes()
        require(actual == expected, f"合同输出不是当前确定性期望值：{path}")


def summary_payload(files: dict[str, bytes], rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "PASS_CONTRACT_LAYER_ONLY",
        "records": list(rows),
        "files": [
            {
                "name": name,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
            }
            for name, payload in sorted(files.items())
        ],
        "numeric_bundles_materialized": 0,
        "grid_points_computed": 0,
        "parameter_candidates_run": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成Fig10 B1/B2/B3合同骨架和R03复用记录")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="合同记录输出目录；默认位于当前隔离案例data/contract_layer",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true", help="只在内存中构建和验证，不写文件")
    mode.add_argument("--verify-existing", action="store_true", help="只核对既有输出，不写文件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files, rows = expected_output_files()
    output_dir = args.output_dir.resolve()
    if args.check_only:
        action = "CHECK_ONLY"
    elif args.verify_existing:
        verify_existing_files(output_dir, files)
        action = "VERIFY_EXISTING"
    else:
        write_files_atomic(output_dir, files)
        verify_existing_files(output_dir, files)
        action = "WRITE_CONTRACT_RECORDS"
    summary = summary_payload(files, rows)
    summary["action"] = action
    summary["output_dir"] = str(output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
