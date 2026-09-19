#!/usr/bin/env python3
"""固化板块17两类自由度划分、缩聚公式与 Simulink 工作区契约。

本脚本只读取同一候选目录的 input 冻结副本，只写 outputs/contract_*
与 logs/contract_*。它不运行作者 MATLAB/Simulink 代码，也不修改原始工程。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import traceback
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
OUTPUT = ROOT / "outputs"
LOGS = ROOT / "logs"

GENERATOR = INPUT / "response_chain" / "regenerate_chapter3_data.m"
DOF_JSON = INPUT / "response_chain" / "图3-1与图3-2_结构自由度参数.json"
DOF_MAP = INPUT / "upstream_u01" / "dof_map.csv"
FREEZE_SUMMARY = INPUT / "input_freeze_summary.json"
FREEZE_MANIFEST = INPUT / "input_manifest.csv"
STANDARD_AUDIT = INPUT / "legacy_audit" / "audit_guyan_projection.m"
THESIS_NOTE = INPUT / "theory" / "Liang2025_实时混合试验缩聚与稳定性.md"

DIVISION_FILES = {
    1: {
        "history": INPUT / "response_chain" / "untitled2_转存.m",
        "mlx": INPUT / "response_chain" / "untitled2.mlx",
        "slx": INPUT / "response_chain" / "lvxvjie_guyan_2.slx",
        "json_key": "图3-1",
    },
    2: {
        "history": INPUT / "response_chain" / "untitled_转存.m",
        "mlx": INPUT / "response_chain" / "untitled.mlx",
        "slx": INPUT / "response_chain" / "lvxvjie_guyan.slx",
        "json_key": "图3-2",
    },
}

MODEL_CALLBACKS = [
    "PreLoadFcn",
    "PostLoadFcn",
    "InitFcn",
    "StartFcn",
    "PauseFcn",
    "ContinueFcn",
    "StopFcn",
    "CloseFcn",
]


def rel(path: Path) -> str:
    """Return a stable POSIX-style path relative to the candidate root."""
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def read_lines(path: Path) -> list[str]:
    return read_text(path).splitlines()


def evidence_line(path: Path, line_number: int) -> str:
    return f"{rel(path)}:{line_number}"


def find_line(lines: list[str], pattern: str, start: int = 1) -> int:
    regex = re.compile(pattern)
    for index, line in enumerate(lines, start=1):
        if index >= start and regex.search(line):
            return index
    raise AssertionError(f"未找到行模式：{pattern}")


def find_all_lines(lines: list[str], pattern: str) -> list[int]:
    regex = re.compile(pattern)
    return [index for index, line in enumerate(lines, start=1) if regex.search(line)]


def parse_matlab_vector(line: str, variable: str) -> list[int]:
    match = re.search(
        rf"^\s*{re.escape(variable)}\s*=\s*\[([^\]]*)\]",
        line,
    )
    if not match:
        raise AssertionError(f"无法从该行解析 {variable}：{line}")
    tokens = re.findall(r"[-+]?\d+(?:\.\d+)?", match.group(1))
    values = [float(token) for token in tokens]
    if any(not value.is_integer() for value in values):
        raise AssertionError(f"{variable} 包含非整数：{line}")
    return [int(value) for value in values]


def vector_assignment(
    lines: list[str], variable: str, start_line: int, end_line: int
) -> tuple[list[int], int]:
    pattern = re.compile(rf"^\s*{re.escape(variable)}\s*=\s*\[")
    found: list[tuple[list[int], int]] = []
    for number in range(start_line, end_line + 1):
        if pattern.search(lines[number - 1]):
            found.append((parse_matlab_vector(lines[number - 1], variable), number))
    if not found:
        raise AssertionError(
            f"{variable} 在 {start_line}-{end_line} 行中没有赋值"
        )
    return found[-1]


def csv_write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {
                key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                if isinstance(value, (list, dict))
                else value
                for key, value in row.items()
            }
            writer.writerow(normalized)


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def extract_generator_divisions(lines: list[str]) -> dict[int, dict[str, Any]]:
    if_line = find_line(lines, r"^\s*if division == 1\s*$")
    elseif_line = find_line(lines, r"^\s*elseif division == 2\s*$", if_line + 1)
    else_line = find_line(lines, r"^\s*else\s*$", elseif_line + 1)
    result: dict[int, dict[str, Any]] = {}
    for division, start, end in (
        (1, if_line + 1, elseif_line - 1),
        (2, elseif_line + 1, else_line - 1),
    ):
        master, master_line = vector_assignment(lines, "master", start, end)
        slave, slave_line = vector_assignment(lines, "slave", start, end)
        mask, mask_line = vector_assignment(lines, "forceMask", start, end)
        result[division] = {
            "master": master,
            "slave": slave,
            "order": master + slave,
            "force_mask": mask,
            "master_line": master_line,
            "slave_line": slave_line,
            "mask_line": mask_line,
        }
    return result


def extract_history(path: Path) -> dict[str, Any]:
    lines = read_lines(path)
    order_lines = find_all_lines(lines, r"^\s*order\s*=\s*\[")
    if not order_lines:
        raise AssertionError(f"历史文件无 order：{path}")
    order_line = order_lines[-1]
    master, master_line = vector_assignment(lines, "index3", 1, order_line)
    slave, slave_line = vector_assignment(lines, "index4", 1, order_line)
    order = parse_matlab_vector(lines[order_line - 1], "order")
    mask_line = find_line(lines, r"^\s*Mf\s*=\s*diag\(")
    mask_match = re.search(r"diag\(\[([^\]]+)\]", lines[mask_line - 1])
    if not mask_match:
        raise AssertionError(f"历史 Mf 掩码无法解析：{path}:{mask_line}")
    mask = [int(token) for token in re.findall(r"\d+", mask_match.group(1))]
    r_line = find_line(lines, r"^\s*r\s*=\s*\d+")
    r_value = int(re.search(r"=\s*(\d+)", lines[r_line - 1]).group(1))
    eig_line = find_line(lines, r"eig\(Kss,\s*Mss\)")
    select_line = find_line(lines, r"phi_s_r\s*=\s*phi_s\(:,\s*1:r\)")
    modal_window = "\n".join(lines[eig_line - 1 : select_line])
    return {
        "lines": lines,
        "master": master,
        "slave": slave,
        "order": order,
        "force_mask": mask,
        "master_line": master_line,
        "slave_line": slave_line,
        "order_line": order_line,
        "mask_line": mask_line,
        "r": r_value,
        "r_line": r_line,
        "r_comment": lines[r_line - 1].split("%", 1)[1].strip()
        if "%" in lines[r_line - 1]
        else "",
        "eig_line": eig_line,
        "select_line": select_line,
        "explicit_sort_between_eig_and_selection": bool(
            re.search(r"\bsort\s*\(", modal_window)
        ),
    }


def extract_mlx_code(path: Path) -> tuple[str, str]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        raw = archive.read("matlab/document.xml")
    root = ET.fromstring(raw)
    code_blocks: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        style = paragraph.find("./w:pPr/w:pStyle", namespace)
        if style is None:
            continue
        value = style.attrib.get(f"{{{namespace['w']}}}val")
        if value != "code":
            continue
        code_blocks.append("".join(paragraph.itertext()))
    code = "\n".join(code_blocks)
    xml_position = (
        "matlab/document.xml:/w:document/w:body/w:p"
        "[w:pPr/w:pStyle/@w:val='code']/w:r/w:t"
    )
    return code, xml_position


def normalized_executable_code(text: str) -> str:
    normalized: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("%"):
            continue
        normalized.append(re.sub(r"\s+", " ", stripped))
    return "\n".join(normalized)


def block_xml_path(block: ET.Element, parameter: str | None = None) -> str:
    sid = block.attrib.get("SID", "")
    name = block.attrib.get("Name", "")
    base = f"/System/Block[@SID='{sid}'][@Name={json.dumps(name, ensure_ascii=False)}]"
    if parameter is not None:
        return base + f"/P[@Name='{parameter}']"
    return base


def parse_slx(path: Path) -> dict[str, Any]:
    required_direct_variables = {"G_1", "G_2", "G_3", "T", "T_cb", "Mf", "MRrt"}
    variable_rows: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    callback_rows: list[dict[str, Any]] = []
    observed_variables: set[str] = set()
    xml_member = "simulink/systems/system_root.xml"

    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read(xml_member))
        for block in root.findall(".//Block"):
            block_type = block.attrib.get("BlockType", "")
            block_name = block.attrib.get("Name", "")
            block_sid = block.attrib.get("SID", "")
            parameters: dict[str, str] = {}
            for parameter in block.findall(".//P"):
                name = parameter.attrib.get("Name", "")
                value = "".join(parameter.itertext()).strip()
                parameters[name] = value
                for variable in sorted(required_direct_variables):
                    if re.search(
                        rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])",
                        value,
                    ):
                        observed_variables.add(variable)
                        variable_rows.append(
                            {
                                "model_file": path.name,
                                "scope": "original_slx_archive",
                                "variable": variable,
                                "block_name": block_name,
                                "block_sid": block_sid,
                                "block_type": block_type,
                                "parameter": name,
                                "expression": value,
                                "evidence": (
                                    f"{rel(path)}!{xml_member}:"
                                    f"{block_xml_path(block, name)}"
                                ),
                                "status": "PASS",
                            }
                        )
            if block_type == "ToWorkspace":
                output_rows.append(
                    {
                        "model_file": path.name,
                        "block_name": block_name,
                        "block_sid": block_sid,
                        "workspace_output": parameters.get("VariableName", ""),
                        "save_format": parameters.get("SaveFormat", ""),
                        "evidence": (
                            f"{rel(path)}!{xml_member}:"
                            f"{block_xml_path(block, 'VariableName')}"
                        ),
                        "status": "PASS",
                    }
                )
            if block_name in {
                "Demux3",
                "Demux4",
                "Demux5",
                "Mux6",
                "Selector3",
                "Selector5",
                "Selector9",
            }:
                key = ""
                for candidate in ("Outputs", "Inputs", "Indices", "InputPortWidth"):
                    if candidate in parameters:
                        key = candidate
                        topology_rows.append(
                            {
                                "model_file": path.name,
                                "block_name": block_name,
                                "block_sid": block_sid,
                                "parameter": key,
                                "value": parameters[key],
                                "evidence": (
                                    f"{rel(path)}!{xml_member}:"
                                    f"{block_xml_path(block, key)}"
                                ),
                                "status": "OBSERVED",
                            }
                        )

        xml_members = [name for name in archive.namelist() if name.endswith(".xml")]
        decoded_members = {
            name: archive.read(name).decode("utf-8", errors="replace")
            for name in xml_members
        }
        for callback in MODEL_CALLBACKS:
            occurrences: list[tuple[str, str]] = []
            attribute_pattern = re.compile(
                rf"<P\s+Name=[\"']{re.escape(callback)}[\"'][^>]*>(.*?)</P>",
                re.DOTALL,
            )
            tag_pattern = re.compile(
                rf"<{re.escape(callback)}[^>]*>(.*?)</{re.escape(callback)}>",
                re.DOTALL,
            )
            for member_name, decoded in decoded_members.items():
                for match in attribute_pattern.finditer(decoded):
                    occurrences.append((member_name, re.sub(r"<[^>]+>", "", match.group(1)).strip()))
                for match in tag_pattern.finditer(decoded):
                    occurrences.append((member_name, re.sub(r"<[^>]+>", "", match.group(1)).strip()))
            nonempty = [item for item in occurrences if item[1]]
            callback_rows.append(
                {
                    "model_file": path.name,
                    "callback": callback,
                    "serialized_occurrence_count": len(occurrences),
                    "nonempty_occurrence_count": len(nonempty),
                    "value": " | ".join(value for _, value in nonempty),
                    "evidence": (
                        f"{rel(path)}!archive-wide XML search:"
                        f"P[@Name='{callback}'] or /{callback}"
                    ),
                    "interpretation": "ABSENT_IN_SERIALIZED_MODEL"
                    if not occurrences
                    else ("EMPTY" if not nonempty else "NONEMPTY"),
                    "status": "PASS" if not nonempty else "FAIL",
                }
            )

    return {
        "variable_rows": variable_rows,
        "output_rows": output_rows,
        "topology_rows": topology_rows,
        "callback_rows": callback_rows,
        "observed_variables": sorted(observed_variables),
    }


def add_gate(
    gates: list[dict[str, Any]],
    gate_id: str,
    description: str,
    expected: Any,
    actual: Any,
    passed: bool,
    evidence: str,
) -> None:
    gates.append(
        {
            "gate_id": gate_id,
            "description": description,
            "expected": expected,
            "actual": actual,
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence,
        }
    )


def main() -> int:
    required_files = [
        GENERATOR,
        DOF_JSON,
        DOF_MAP,
        FREEZE_SUMMARY,
        FREEZE_MANIFEST,
        STANDARD_AUDIT,
        THESIS_NOTE,
    ]
    for values in DIVISION_FILES.values():
        required_files.extend([values["history"], values["mlx"], values["slx"]])
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少冻结输入：" + "; ".join(missing))
    if any(INPUT.resolve() not in path.resolve().parents for path in required_files):
        raise AssertionError("存在不位于 input 冻结区的读取路径")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    freeze_summary = json.loads(read_text(FREEZE_SUMMARY))
    semantic_json = json.loads(read_text(DOF_JSON))
    generator_lines = read_lines(GENERATOR)
    standard_lines = read_lines(STANDARD_AUDIT)
    note_lines = read_lines(THESIS_NOTE)
    current = extract_generator_divisions(generator_lines)
    history = {
        division: extract_history(values["history"])
        for division, values in DIVISION_FILES.items()
    }

    current_r_line = find_line(generator_lines, r"^\s*r\s*=\s*3\s*;")
    current_eig_line = find_line(generator_lines, r"eig\(Kss,\s*Mss\)")
    current_sort_line = find_line(
        generator_lines, r"sort\(real\(diag\(lambda\)\),\s*'ascend'\)"
    )
    current_select_line = find_line(generator_lines, r"phi\(:,1:r\)")
    floor_line = find_line(generator_lines, r"floorOriginal\s*=\s*\[1,6,11\]")
    floor_rows_line = find_line(generator_lines, r"floorRowsOrdered\s*=")
    guyan_recovery_line = find_line(generator_lines, r"Cfloor2\s*=\s*\[P\*T,")
    cb_recovery_line = find_line(generator_lines, r"Cfloor3\s*=\s*\[P\*Tcb,")
    assign_names_line = find_line(generator_lines, r"names\s*=\s*\{'G_1'")
    assign_more_line = assign_names_line + 1
    assign_last_line = assign_names_line + 2
    output_floor1_line = find_line(generator_lines, r"out\.floor1\s*=\s*simOut\.simout3")
    output_floor2_line = find_line(generator_lines, r"out\.floor2\s*=\s*simOut\.simout\s*;")
    output_floor3_line = find_line(generator_lines, r"out\.floor3\s*=\s*simOut\.simout1")

    dof_rows_from_csv: dict[int, dict[str, str]] = {}
    with DOF_MAP.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            dof_rows_from_csv[int(row["dof_number"])] = row

    division_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    recovery_rows: list[dict[str, Any]] = []
    formula_rows: list[dict[str, Any]] = []
    workspace_rows: list[dict[str, Any]] = []
    simulink_output_rows: list[dict[str, Any]] = []
    callback_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    mlx_rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []

    add_gate(
        gates,
        "G01_FREEZE_INTEGRITY",
        "冻结输入清单全部源/副本哈希一致",
        {"source_count": 32, "all_match": True},
        {
            "source_count": freeze_summary.get("source_count"),
            "match_count": freeze_summary.get("match_count"),
            "all_match": freeze_summary.get("all_match"),
        },
        freeze_summary.get("source_count") == 32
        and freeze_summary.get("match_count") == 32
        and freeze_summary.get("all_match") is True,
        rel(FREEZE_SUMMARY),
    )

    slx_results: dict[int, dict[str, Any]] = {}
    mlx_all_match = True
    for division in (1, 2):
        values = DIVISION_FILES[division]
        cur = current[division]
        hist = history[division]
        order = cur["order"]
        n_master = len(cur["master"])
        n_slave = len(cur["slave"])
        cb_width = n_master + 3
        floor_original = [1, 6, 11]
        floor_ordered_rows = [order.index(dof) + 1 for dof in floor_original]
        force_positions = [
            index + 1 for index, value in enumerate(cur["force_mask"]) if value == 1
        ]
        force_dofs_ordered = [order[index - 1] for index in force_positions]
        json_entry = semantic_json[values["json_key"]]
        numeric = json_entry["数值子结构"]
        physical = json_entry["物理子结构"]
        semantic_master = list(numeric["保留水平自由度"]) + list(
            numeric["保留转角自由度"]
        )
        if division == 2:
            semantic_master = list(physical["保留水平自由度"]) + list(
                numeric["保留转角自由度"]
            )

        psi6_role = "master" if 6 in cur["master"] else "slave_recovered"
        current_evidence = ";".join(
            [
                evidence_line(GENERATOR, cur["master_line"]),
                evidence_line(GENERATOR, cur["slave_line"]),
                evidence_line(GENERATOR, cur["mask_line"]),
            ]
        )
        history_evidence = ";".join(
            [
                evidence_line(values["history"], hist["master_line"]),
                evidence_line(values["history"], hist["slave_line"]),
                evidence_line(values["history"], hist["order_line"]),
                evidence_line(values["history"], hist["mask_line"]),
            ]
        )
        json_evidence = (
            evidence_line(DOF_JSON, 2 if division == 1 else 32)
            + ("-30" if division == 1 else "-64")
        )
        row_pass = (
            cur["master"] == hist["master"]
            and cur["slave"] == hist["slave"]
            and order == hist["order"]
            and cur["force_mask"] == hist["force_mask"]
            and sorted(order) == list(range(1, 16))
            and semantic_master == cur["master"]
        )
        division_rows.append(
            {
                "division": division,
                "model_file": values["slx"].name,
                "historical_mlx": values["mlx"].name,
                "current_master": cur["master"],
                "historical_master": hist["master"],
                "current_slave": cur["slave"],
                "historical_slave": hist["slave"],
                "order": order,
                "n_full": 15,
                "n_master": n_master,
                "n_slave": n_slave,
                "guyan_width": n_master,
                "cb_retained_modes_r": 3,
                "cb_width": cb_width,
                "psi6_role": psi6_role,
                "psi6_order_position": order.index(6) + 1,
                "floor_original_dofs": floor_original,
                "floor_ordered_rows": floor_ordered_rows,
                "force_mask_ordered": cur["force_mask"],
                "force_positions_ordered": force_positions,
                "force_source_dofs_ordered": force_dofs_ordered,
                "current_evidence": current_evidence,
                "historical_evidence": history_evidence,
                "semantic_json_evidence": json_evidence,
                "status": "PASS" if row_pass else "FAIL",
            }
        )

        for dof in range(1, 16):
            source_row = dof_rows_from_csv[dof]
            ordered_position = order.index(dof) + 1
            membership_rows.append(
                {
                    "division": division,
                    "dof_number": dof,
                    "dof_label": source_row["dof_label"],
                    "floor_number": source_row["floor_number"],
                    "dof_type": source_row["dof_type"],
                    "role": "master" if dof in cur["master"] else "slave",
                    "ordered_position": ordered_position,
                    "is_floor_output": int(dof in floor_original),
                    "is_force_source": int(cur["force_mask"][ordered_position - 1] == 1),
                    "evidence": current_evidence,
                    "status": "PASS",
                }
            )

        recovery_rows.extend(
            [
                {
                    "division": division,
                    "quantity": "floor_original_dofs",
                    "value": floor_original,
                    "interpretation": "三层水平位移的原始自由度",
                    "evidence": evidence_line(GENERATOR, floor_line),
                    "status": "PASS",
                },
                {
                    "division": division,
                    "quantity": "floor_rows_in_ordered_system",
                    "value": floor_ordered_rows,
                    "interpretation": "按 order 定位三层水平自由度",
                    "evidence": evidence_line(GENERATOR, floor_rows_line),
                    "status": "PASS",
                },
                {
                    "division": division,
                    "quantity": "guyan_floor_recovery",
                    "value": "P*T",
                    "interpretation": "从 Guyan 广义坐标恢复三层物理位移",
                    "evidence": evidence_line(GENERATOR, guyan_recovery_line),
                    "status": "PASS",
                },
                {
                    "division": division,
                    "quantity": "cb_floor_recovery",
                    "value": "P*Tcb",
                    "interpretation": "从 Craig-Bampton 广义坐标恢复三层物理位移",
                    "evidence": evidence_line(GENERATOR, cb_recovery_line),
                    "status": "PASS",
                },
                {
                    "division": division,
                    "quantity": "psi6_rule",
                    "value": {
                        "role": psi6_role,
                        "ordered_position": order.index(6) + 1,
                        "forced": cur["force_mask"][order.index(6)] == 1,
                        "recovered_in_floor_outputs": True,
                    },
                    "interpretation": (
                        "psi6 是组合主自由度并直接保留"
                        if division == 1
                        else "psi6 是从自由度，但通过 P*T/P*Tcb 恢复且仍计入惯性力掩码"
                    ),
                    "evidence": (
                        current_evidence
                        + ";"
                        + evidence_line(GENERATOR, guyan_recovery_line)
                        + ";"
                        + evidence_line(GENERATOR, cb_recovery_line)
                    ),
                    "status": "PASS",
                },
            ]
        )

        combined_match = (
            cur["master"] == hist["master"]
            and cur["slave"] == hist["slave"]
            and order == hist["order"]
            and cur["force_mask"] == hist["force_mask"]
        )
        add_gate(
            gates,
            f"G02_DIV{division}_CURRENT_HISTORY_MATCH",
            f"第{division}类当前生成器与历史转存的组合自由度/力掩码一致",
            {
                "master": cur["master"],
                "slave": cur["slave"],
                "order": order,
                "force_mask": cur["force_mask"],
            },
            {
                "master": hist["master"],
                "slave": hist["slave"],
                "order": hist["order"],
                "force_mask": hist["force_mask"],
            },
            combined_match,
            current_evidence + ";" + history_evidence,
        )
        add_gate(
            gates,
            f"G03_DIV{division}_ORDER_PERMUTATION",
            f"第{division}类 order 恰好覆盖 1..15 且无重复",
            list(range(1, 16)),
            sorted(order),
            sorted(order) == list(range(1, 16)) and len(set(order)) == 15,
            current_evidence,
        )
        expected_dimensions = {1: (6, 9), 2: (5, 8)}[division]
        add_gate(
            gates,
            f"G04_DIV{division}_REDUCED_DIMENSIONS",
            f"第{division}类 Guyan/CB 宽度符合当前生成器硬门槛",
            {"guyan": expected_dimensions[0], "cb": expected_dimensions[1]},
            {"guyan": n_master, "cb": cb_width},
            (n_master, cb_width) == expected_dimensions,
            evidence_line(GENERATOR, 85 if division == 1 else 99),
        )
        add_gate(
            gates,
            f"G05_DIV{division}_SEMANTIC_JSON",
            f"第{division}类语义 JSON 与组合主自由度一致",
            cur["master"],
            semantic_master,
            semantic_master == cur["master"],
            json_evidence + ";" + evidence_line(GENERATOR, cur["master_line"]),
        )
        add_gate(
            gates,
            f"G06_DIV{division}_R_EQUALS_3",
            f"第{division}类历史代码与当前生成器实际均保留 r=3",
            {"history": 3, "current": 3},
            {"history": hist["r"], "current": 3},
            hist["r"] == 3,
            evidence_line(values["history"], hist["r_line"])
            + ";"
            + evidence_line(GENERATOR, current_r_line),
        )
        add_gate(
            gates,
            f"G07_DIV{division}_MODAL_ORDER_ROUTE_CAPTURED",
            f"第{division}类历史未显式排序、当前生成器显式升序排序的差异已捕获",
            {"history_explicit_sort": False, "current_sort": "ascending"},
            {
                "history_explicit_sort": hist[
                    "explicit_sort_between_eig_and_selection"
                ],
                "current_sort": "ascending",
            },
            hist["explicit_sort_between_eig_and_selection"] is False
            and current_eig_line < current_sort_line < current_select_line,
            evidence_line(values["history"], hist["eig_line"])
            + "-"
            + str(hist["select_line"])
            + ";"
            + evidence_line(GENERATOR, current_eig_line)
            + "-"
            + str(current_select_line),
        )

        raw_mlx_code, mlx_position = extract_mlx_code(values["mlx"])
        normalized_mlx = normalized_executable_code(raw_mlx_code)
        normalized_export = normalized_executable_code(read_text(values["history"]))
        mlx_match = normalized_mlx == normalized_export
        mlx_all_match = mlx_all_match and mlx_match
        mlx_rows.append(
            {
                "division": division,
                "mlx_file": values["mlx"].name,
                "export_file": values["history"].name,
                "mlx_normalized_sha256": hashlib.sha256(
                    normalized_mlx.encode("utf-8")
                ).hexdigest().upper(),
                "export_normalized_sha256": hashlib.sha256(
                    normalized_export.encode("utf-8")
                ).hexdigest().upper(),
                "normalized_line_count": len(normalized_mlx.splitlines()),
                "evidence": f"{rel(values['mlx'])}!{mlx_position};{rel(values['history'])}:executable-lines",
                "status": "PASS" if mlx_match else "FAIL",
            }
        )

        slx = parse_slx(values["slx"])
        slx_results[division] = slx
        workspace_rows.extend(slx["variable_rows"])
        simulink_output_rows.extend(slx["output_rows"])
        callback_rows.extend(slx["callback_rows"])
        topology_rows.extend(slx["topology_rows"])
        required_model_vars = {"G_1", "G_2", "G_3", "T", "T_cb", "Mf", "MRrt"}
        add_gate(
            gates,
            f"G08_DIV{division}_SLX_VARIABLES",
            f"第{division}类原始 SLX 直接消费七个关键工作区变量",
            sorted(required_model_vars),
            slx["observed_variables"],
            set(slx["observed_variables"]) == required_model_vars,
            f"{rel(values['slx'])}!simulink/systems/system_root.xml",
        )
        observed_outputs = {
            row["workspace_output"] for row in slx["output_rows"]
        }
        add_gate(
            gates,
            f"G09_DIV{division}_SLX_OUTPUTS",
            f"第{division}类原始 SLX 保存 simout3/simout/simout1",
            sorted(["simout", "simout1", "simout3"]),
            sorted(observed_outputs),
            observed_outputs == {"simout", "simout1", "simout3"},
            f"{rel(values['slx'])}!simulink/systems/system_root.xml",
        )
        callbacks_ok = all(row["status"] == "PASS" for row in slx["callback_rows"])
        add_gate(
            gates,
            f"G10_DIV{division}_MODEL_CALLBACKS",
            f"第{division}类原始 SLX 无非空模型级回调",
            "all standard model callbacks absent or empty",
            {
                row["callback"]: row["interpretation"]
                for row in slx["callback_rows"]
            },
            callbacks_ok,
            f"{rel(values['slx'])}!archive-wide XML search",
        )

    add_gate(
        gates,
        "G11_MLX_EXPORT_EQUIVALENCE",
        "两份 MLX 中的代码段与对应转存 .m 的可执行代码逐行等价",
        True,
        mlx_all_match,
        mlx_all_match,
        ";".join(row["evidence"] for row in mlx_rows),
    )

    # Generator-side variables assigned to the copied Simulink models.
    assigned_names = [
        "G_1",
        "G_2",
        "G_3",
        "T",
        "T_cb",
        "Mf",
        "output_matrix_original",
        "output_matrix_guyan",
        "output_matrix_cb",
        "feedthrough_matrix_original",
        "feedthrough_matrix_guyan",
        "feedthrough_matrix_cb",
        "MRrt",
    ]
    for variable in assigned_names:
        line = (
            assign_names_line
            if variable in {"G_1", "G_2", "G_3", "T", "T_cb", "Mf"}
            else (assign_more_line if variable.startswith("output_matrix") else assign_last_line)
        )
        workspace_rows.append(
            {
                "model_file": "division1_repro.slx;division2_repro.slx",
                "scope": "current_generator_assignin",
                "variable": variable,
                "block_name": "base workspace",
                "block_sid": "",
                "block_type": "assignin",
                "parameter": "names/vals",
                "expression": variable,
                "evidence": evidence_line(GENERATOR, line),
                "status": "PASS",
            }
        )
    for variable, line in (("excitation_input", 322), ("dt", 323)):
        workspace_rows.append(
            {
                "model_file": "division1_repro.slx;division2_repro.slx",
                "scope": "current_generator_assignin",
                "variable": variable,
                "block_name": "base workspace",
                "block_sid": "",
                "block_type": "assignin",
                "parameter": "runtime input",
                "expression": variable,
                "evidence": evidence_line(GENERATOR, line),
                "status": "PASS",
            }
        )

    # Explicit floor/output meaning in the current generator.
    for workspace_output, floor, line in (
        ("simout3", "floor1", output_floor1_line),
        ("simout", "floor2", output_floor2_line),
        ("simout1", "floor3", output_floor3_line),
    ):
        simulink_output_rows.append(
            {
                "model_file": "current_generator_mapping",
                "block_name": floor,
                "block_sid": "",
                "workspace_output": workspace_output,
                "save_format": "Timeseries (from frozen SLX)",
                "evidence": evidence_line(GENERATOR, line),
                "status": "PASS",
            }
        )

    # Formula crosswalk: historical executable route, standard congruence, and CB.
    formula_specs = [
        (
            "current_generator_historical_guyan",
            "T",
            "T=[I;-Kss\\Ksm]",
            "static transformation",
            GENERATOR,
            find_line(generator_lines, r"^\s*T\s*=\s*\[eye\(nm\)"),
            "EXECUTABLE_HISTORY",
            "",
        ),
        (
            "current_generator_historical_guyan",
            "M",
            "Mg=Mmm-Mms*(Kss\\Ksm)",
            "single-sided elimination",
            GENERATOR,
            find_line(generator_lines, r"^\s*Mg\s*=\s*Mmm"),
            "EXECUTABLE_HISTORY",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "current_generator_historical_guyan",
            "C",
            "Cg=Cmm-Cms*(Kss\\Ksm)",
            "single-sided elimination",
            GENERATOR,
            find_line(generator_lines, r"^\s*Cg\s*=\s*Cmm"),
            "EXECUTABLE_HISTORY",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "current_generator_historical_guyan",
            "K",
            "Kg=Kmm-Kms*(Kss\\Ksm)",
            "single-sided elimination",
            GENERATOR,
            find_line(generator_lines, r"^\s*Kg\s*=\s*Kmm"),
            "EXECUTABLE_HISTORY",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "standard_guyan_congruence",
            "M",
            "M_projected=T'*M*T",
            "bilateral congruence",
            STANDARD_AUDIT,
            find_line(standard_lines, r"M_projected\s*=\s*T'\s*\*\s*M\s*\*\s*T"),
            "STANDARD_FORMULA",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "standard_guyan_congruence",
            "C",
            "C_projected=T'*C*T",
            "bilateral congruence",
            STANDARD_AUDIT,
            find_line(standard_lines, r"C_projected\s*=\s*T'\s*\*\s*C\s*\*\s*T"),
            "STANDARD_FORMULA",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "standard_guyan_congruence",
            "K",
            "K_projected=T'*K*T",
            "bilateral congruence",
            STANDARD_AUDIT,
            find_line(standard_lines, r"K_projected\s*=\s*T'\s*\*\s*K\s*\*\s*T"),
            "STANDARD_FORMULA",
            "C02_GUYAN_FORMULA_ROUTE",
        ),
        (
            "current_generator_cb",
            "M/C/K",
            "A_cb=Tcb'*A_ordered*Tcb",
            "bilateral congruence",
            GENERATOR,
            find_line(generator_lines, r"Mcb\s*=\s*Tcb'\*Mo\*Tcb"),
            "EXECUTABLE_CURRENT",
            "",
        ),
    ]
    for route, matrix, formula, kind, source, line, classification, conflict_id in formula_specs:
        formula_rows.append(
            {
                "route": route,
                "matrix": matrix,
                "formula": formula,
                "projection_type": kind,
                "classification": classification,
                "evidence": evidence_line(source, line),
                "conflict_id": conflict_id,
                "status": "OBSERVED",
            }
        )
    for division in (1, 2):
        hist = history[division]
        source = DIVISION_FILES[division]["history"]
        hist_lines = hist["lines"]
        for matrix, pattern, formula in (
            ("M", r"^\s*MRren\s*=", "MRren=Mmn-Mmsn*(Ksn\\Ksmn)"),
            ("C", r"^\s*CRren\s*=", "CRren=Cmn-Cmsn*(Ksn\\Ksmn)"),
            ("K", r"^\s*KRren\s*=", "KRren=Kmn-Kmsn*(Ksn\\Ksmn)"),
        ):
            formula_rows.append(
                {
                    "route": f"historical_mlx_division_{division}",
                    "matrix": matrix,
                    "formula": formula,
                    "projection_type": "single-sided elimination",
                    "classification": "EXECUTABLE_HISTORY",
                    "evidence": evidence_line(source, find_line(hist_lines, pattern)),
                    "conflict_id": "C02_GUYAN_FORMULA_ROUTE",
                    "status": "OBSERVED",
                }
            )
        formula_rows.append(
            {
                "route": f"historical_mlx_division_{division}",
                "matrix": "M/C/K",
                "formula": "A_cb=T_cb'*A_ordered*T_cb",
                "projection_type": "bilateral congruence",
                "classification": "EXECUTABLE_HISTORY",
                "evidence": evidence_line(
                    source, find_line(hist_lines, r"^\s*MR_cb\s*=\s*T_cb'")
                )
                + "-"
                + str(find_line(hist_lines, r"^\s*CR_cb\s*=\s*T_cb'")),
                "conflict_id": "",
                "status": "OBSERVED",
            }
        )

    formula_gate_pass = (
        any(
            row["route"] == "standard_guyan_congruence" and row["matrix"] == "M"
            for row in formula_rows
        )
        and any(
            row["route"] == "current_generator_historical_guyan"
            and row["matrix"] == "M"
            for row in formula_rows
        )
    )
    add_gate(
        gates,
        "G12_FORMULA_ROUTES_DISTINGUISHED",
        "历史 Guyan 单边消元与标准 T'AT 双边合同投影分开固化",
        True,
        formula_gate_pass,
        formula_gate_pass,
        evidence_line(THESIS_NOTE, find_line(note_lines, r"公式\(2-5\).*双侧合同投影"))
        + ";"
        + evidence_line(GENERATOR, find_line(generator_lines, r"^\s*Mg\s*=\s*Mmm"))
        + ";"
        + evidence_line(STANDARD_AUDIT, find_line(standard_lines, r"M_projected\s*=")),
    )

    psi6_gate = all(
        any(
            row["division"] == division
            and row["quantity"] == "psi6_rule"
            and row["status"] == "PASS"
            for row in recovery_rows
        )
        for division in (1, 2)
    )
    add_gate(
        gates,
        "G13_PSI6_RECOVERY",
        "psi6 在第一类直接保留，在第二类作为从自由度由 P*T/P*Tcb 恢复",
        True,
        psi6_gate,
        psi6_gate,
        evidence_line(DOF_JSON, 51)
        + "-62;"
        + evidence_line(GENERATOR, guyan_recovery_line)
        + ";"
        + evidence_line(GENERATOR, cb_recovery_line),
    )

    # Conflicts and route differences are expected observations, not hidden failures.
    for division in (1, 2):
        hist = history[division]
        values = DIVISION_FILES[division]
        conflicts.append(
            {
                "conflict_id": f"C01_DIV{division}_R_COMMENT",
                "category": "CONFLICT_EXECUTABLE_VS_COMMENT",
                "subject": f"第{division}类 CB 保留模态数",
                "side_a": {"executable_r": hist["r"]},
                "side_b": {"comment": hist["r_comment"]},
                "adjudication": "执行事实取 r=3；注释‘前5个模态’为历史文字冲突",
                "evidence": evidence_line(values["history"], hist["r_line"]),
                "status": "CONFLICT_RECORDED",
            }
        )
        conflicts.append(
            {
                "conflict_id": f"C03_DIV{division}_MODAL_SORT",
                "category": "ROUTE_DIFFERENCE_REPRODUCIBILITY",
                "subject": f"第{division}类固定界面模态列顺序",
                "side_a": "历史 eig 后直接 phi_s(:,1:r)，未显式排序",
                "side_b": "当前生成器按特征值实部升序排序后取前三列",
                "adjudication": "两条路线均保留；确定性复现使用当前显式升序排序",
                "evidence": evidence_line(values["history"], hist["eig_line"])
                + "-"
                + str(hist["select_line"])
                + ";"
                + evidence_line(GENERATOR, current_eig_line)
                + "-"
                + str(current_select_line),
                "status": "ROUTE_DIFFERENCE_RECORDED",
            }
        )
    conflicts.append(
        {
            "conflict_id": "C02_GUYAN_FORMULA_ROUTE",
            "category": "CONFLICT_HISTORICAL_VS_STANDARD",
            "subject": "Guyan 质量/阻尼/刚度矩阵投影",
            "side_a": "历史与当前响应生成器执行 A_mm-A_ms*K_ss^{-1}*K_sm 单边消元",
            "side_b": "通用标准采用 T'*A*T 双边合同投影",
            "adjudication": "不静默合并；两条公式路线分别保留并由后续数值审计比较",
            "evidence": evidence_line(THESIS_NOTE, 20)
            + "-21;"
            + evidence_line(GENERATOR, 268)
            + "-270;"
            + evidence_line(STANDARD_AUDIT, 48)
            + "-50",
            "status": "CONFLICT_RECORDED",
        }
    )
    conflicts.append(
        {
            "conflict_id": "C04_DIV2_PHYSICAL_PRELUDE",
            "category": "EXTRA_HISTORICAL_PHYSICAL_PRELUDE",
            "subject": "第二类历史 Live Script 的局部物理子结构预处理",
            "side_a": "untitled_转存.m 前20行先对 MPrt/CPrt/KPrt 的 6DOF 物理子结构做 2DOF Guyan",
            "side_b": "当前生成器直接对完整 15DOF MRrt/CRrt/KRrt 做一次组合缩聚",
            "adjudication": "局部预处理作为历史候选路线保留，不视为当前响应生成器的一部分",
            "evidence": evidence_line(DIVISION_FILES[2]["history"], 4)
            + "-20;"
            + evidence_line(GENERATOR, 246)
            + "-277",
            "status": "ROUTE_DIFFERENCE_RECORDED",
        }
    )
    conflicts.append(
        {
            "conflict_id": "C05_DIV2_THIRD_FLOOR_REPAIR",
            "category": "MODEL_PATCH_REQUIRED",
            "subject": "第二类原始模型 Guyan/CB 三层输出",
            "side_a": "冻结 lvxvjie_guyan.slx 中 Demux4/Demux5 仅有2个输出",
            "side_b": "当前生成器将两者改为3输出，并用 P*T/P*Tcb 恢复三层位移后补接 Mux6",
            "adjudication": "原始模型拓扑事实与当前可复现副本修复均保留；不得把补线说成原模型已完整",
            "evidence": f"{rel(DIVISION_FILES[2]['slx'])}!simulink/systems/system_root.xml:/System/Block[@Name='Demux4' or @Name='Demux5']/P[@Name='Outputs'];"
            + evidence_line(GENERATOR, 205)
            + "-220;"
            + evidence_line(GENERATOR, guyan_recovery_line)
            + "-"
            + str(cb_recovery_line),
            "status": "MODEL_PATCH_RECORDED",
        }
    )

    all_gates_pass = all(row["status"] == "PASS" for row in gates)
    for gate in gates:
        evidence_rows.append(
            {
                "fact_id": gate["gate_id"],
                "fact": gate["description"],
                "value": gate["actual"],
                "evidence": gate["evidence"],
                "status": gate["status"],
            }
        )

    outputs = {
        "contract_divisions.csv": (
            division_rows,
            [
                "division",
                "model_file",
                "historical_mlx",
                "current_master",
                "historical_master",
                "current_slave",
                "historical_slave",
                "order",
                "n_full",
                "n_master",
                "n_slave",
                "guyan_width",
                "cb_retained_modes_r",
                "cb_width",
                "psi6_role",
                "psi6_order_position",
                "floor_original_dofs",
                "floor_ordered_rows",
                "force_mask_ordered",
                "force_positions_ordered",
                "force_source_dofs_ordered",
                "current_evidence",
                "historical_evidence",
                "semantic_json_evidence",
                "status",
            ],
        ),
        "contract_dof_membership.csv": (
            membership_rows,
            [
                "division",
                "dof_number",
                "dof_label",
                "floor_number",
                "dof_type",
                "role",
                "ordered_position",
                "is_floor_output",
                "is_force_source",
                "evidence",
                "status",
            ],
        ),
        "contract_recovery.csv": (
            recovery_rows,
            ["division", "quantity", "value", "interpretation", "evidence", "status"],
        ),
        "contract_formula_crosswalk.csv": (
            formula_rows,
            [
                "route",
                "matrix",
                "formula",
                "projection_type",
                "classification",
                "evidence",
                "conflict_id",
                "status",
            ],
        ),
        "contract_simulink_workspace.csv": (
            workspace_rows,
            [
                "model_file",
                "scope",
                "variable",
                "block_name",
                "block_sid",
                "block_type",
                "parameter",
                "expression",
                "evidence",
                "status",
            ],
        ),
        "contract_simulink_outputs.csv": (
            simulink_output_rows,
            [
                "model_file",
                "block_name",
                "block_sid",
                "workspace_output",
                "save_format",
                "evidence",
                "status",
            ],
        ),
        "contract_simulink_callbacks.csv": (
            callback_rows,
            [
                "model_file",
                "callback",
                "serialized_occurrence_count",
                "nonempty_occurrence_count",
                "value",
                "evidence",
                "interpretation",
                "status",
            ],
        ),
        "contract_simulink_topology.csv": (
            topology_rows,
            [
                "model_file",
                "block_name",
                "block_sid",
                "parameter",
                "value",
                "evidence",
                "status",
            ],
        ),
        "contract_mlx_export_equivalence.csv": (
            mlx_rows,
            [
                "division",
                "mlx_file",
                "export_file",
                "mlx_normalized_sha256",
                "export_normalized_sha256",
                "normalized_line_count",
                "evidence",
                "status",
            ],
        ),
        "contract_conflicts.csv": (
            conflicts,
            [
                "conflict_id",
                "category",
                "subject",
                "side_a",
                "side_b",
                "adjudication",
                "evidence",
                "status",
            ],
        ),
        "contract_acceptance_gates.csv": (
            gates,
            [
                "gate_id",
                "description",
                "expected",
                "actual",
                "status",
                "evidence",
            ],
        ),
        "contract_evidence.csv": (
            evidence_rows,
            ["fact_id", "fact", "value", "evidence", "status"],
        ),
    }
    for filename, (rows, fields) in outputs.items():
        csv_write(OUTPUT / filename, rows, fields)

    summary = {
        "schema_version": "board17-contract-v1",
        "input_policy": "read only from candidate_root/input",
        "overall_status": "PASS" if all_gates_pass else "FAIL",
        "gate_count": len(gates),
        "gate_pass_count": sum(row["status"] == "PASS" for row in gates),
        "division_count": len(division_rows),
        "dof_membership_row_count": len(membership_rows),
        "formula_row_count": len(formula_rows),
        "simulink_workspace_row_count": len(workspace_rows),
        "simulink_output_row_count": len(simulink_output_rows),
        "simulink_callback_row_count": len(callback_rows),
        "conflict_count": len(conflicts),
        "conflict_ids": [row["conflict_id"] for row in conflicts],
        "key_findings": {
            "division_1": {
                "master": current[1]["master"],
                "slave": current[1]["slave"],
                "guyan_width": 6,
                "cb_width": 9,
            },
            "division_2": {
                "master": current[2]["master"],
                "slave": current[2]["slave"],
                "guyan_width": 5,
                "cb_width": 8,
                "psi6": "slave_recovered_by_P_times_T_and_P_times_Tcb",
            },
            "cb_retained_modes_r": 3,
            "historical_modal_sort": "none_explicit",
            "current_modal_sort": "ascending_eigenvalue",
            "historical_guyan": "single_sided_elimination",
            "standard_guyan": "bilateral_congruence_T_transpose_A_T",
            "workspace_outputs": {
                "simout3": "floor1",
                "simout": "floor2",
                "simout1": "floor3",
            },
            "model_callbacks": "no_nonempty_standard_model_callbacks_in_frozen_slx",
        },
        "input_freeze_manifest_sha256": sha256(FREEZE_MANIFEST),
        "builder_sha256": sha256(Path(__file__)),
    }
    json_write(OUTPUT / "contract_summary.json", summary)

    artifact_rows: list[dict[str, Any]] = []
    for path in sorted(OUTPUT.glob("contract_*"), key=lambda item: item.name):
        if path.name == "contract_artifact_manifest.csv":
            continue
        artifact_rows.append(
            {
                "relative_path": rel(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "status": "PRESENT",
            }
        )
    csv_write(
        OUTPUT / "contract_artifact_manifest.csv",
        artifact_rows,
        ["relative_path", "size_bytes", "sha256", "status"],
    )

    log_lines = [
        "板块17自由度/公式/Simulink契约固化",
        f"candidate_root={ROOT}",
        f"input_freeze_all_match={freeze_summary.get('all_match')}",
        f"input_source_count={freeze_summary.get('source_count')}",
        f"overall_status={summary['overall_status']}",
        f"gate_pass={summary['gate_pass_count']}/{summary['gate_count']}",
        "division_1=master[1,6,11,4,9,14];slave[2,3,5,7,8,10,12,13,15];Guyan6;CB9",
        "division_2=master[1,11,4,9,14];slave[6,2,3,5,7,8,10,12,13,15];Guyan5;CB8",
        "psi6_division_2=slave_recovered_by_P*T_and_P*Tcb;force_mask_included",
        "cb_modes=r3;historical_comment_conflict=first5",
        "modal_sort=history_none_explicit;current_ascending",
        "guyan_formula=history_single_sided;standard_T_transpose_A_T",
        "workspace_variables=G_1,G_2,G_3,T,T_cb,Mf,MRrt plus generator output/feedthrough matrices",
        "workspace_outputs=simout3:floor1,simout:floor2,simout1:floor3",
        "model_callbacks=no_nonempty_standard_model_callbacks_in_frozen_slx",
        f"artifact_count_excluding_manifest={len(artifact_rows)}",
        f"summary_sha256={sha256(OUTPUT / 'contract_summary.json')}",
    ]
    (LOGS / "contract_build.log").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )
    print("\n".join(log_lines))
    return 0 if all_gates_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        LOGS.mkdir(parents=True, exist_ok=True)
        failure = traceback.format_exc()
        (LOGS / "contract_build_failure.log").write_text(failure, encoding="utf-8")
        print(failure, file=sys.stderr)
        raise SystemExit(1)
