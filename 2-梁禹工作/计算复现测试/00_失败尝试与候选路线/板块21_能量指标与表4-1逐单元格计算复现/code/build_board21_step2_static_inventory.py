from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat, whosmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parents[1]
AUTHOR_ROOT = BOARD_ROOT / "input" / "author_energy"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step2_static_inventory"
TABLE_ROOT = OUTPUT_ROOT / "tables"
MLX_CODE_ROOT = OUTPUT_ROOT / "extracted_mlx_code"
MLX_JSON_ROOT = OUTPUT_ROOT / "extracted_mlx_records"
TEXT_CODE_ROOT = OUTPUT_ROOT / "extracted_text_code"

STEP1_FIXED_HASHES = {
    BOARD_ROOT / "outputs" / "step1_validation" / "checks.csv": "BD7B7411401C4AFECF417CEEA4F281304A47D690E9B78FB99FCBE24D518E170B",
    BOARD_ROOT
    / "outputs"
    / "step1_validation"
    / "validation_summary.json": "B75CE38E2529AB0873720922057D35DC1B6EE4346D17BC44F5CB10E134AB7C60",
    BOARD_ROOT
    / "outputs"
    / "step1_validation"
    / "relative_handle_race_test.json": "F887F904480AAD9FF2AAF7CF3EC9EA0A7D392FA64F10AB377D0884AEFEB9D354",
    BOARD_ROOT
    / "outputs"
    / "step1_artifact_manifest.csv": "0BF3542E8ACFF7446EE2B069680C6B4A84A9A113C2CE2E76E7EF6CD110F00F5E",
}

ENERGY_SCRIPTS = (
    "energy_zonghe.mlx",
    "energy_zonghe2.mlx",
    "Copy_of_energy_zonghe2.mlx",
    "Copy_2_of_energy_zonghe2.mlx",
    "energy_zonghe3.mlx",
    "Copy_of_energy_zonghe3.mlx",
    "Copy_2_of_energy_zonghe3.mlx",
)

EXPECTED_COUNTS = {".m": 5, ".mat": 2, ".mlx": 26, ".slx": 3}

# Curated static contracts below are evidence assertions, not reconstructed results.
# They bind file identities, dimensions, and coordinate order so that Step 3 can run
# every historical route in isolation without silently changing its scientific meaning.
ROUTE_STATIC_CONTRACTS: dict[str, dict[str, Any]] = {
    "energy_zonghe.mlx": {
        "producer": "PDmonicanshu.m",
        "division_identity": "旧15自由度水平主坐标参考体系；未绑定表4-1两类整体划分",
        "dimension_family": "15->3/6",
        "full_dof": 15,
        "guyan_dof": 3,
        "cb_dof": 6,
        "variable_family": "KRrt/MRrt|T/KRren/MRren|T_cb/KR_cb/MR_cb",
        "producer_order": "[1,6,11,2,3,4,5,7,8,9,10,12,13,14,15]",
        "consumer_order": "external index3,index4; same producer workspace",
        "dimension_status": "PASS",
        "coordinate_order_status": "PASS",
        "candidate_status": "STATIC_CANDIDATE_REFERENCE",
    },
    "energy_zonghe2.mlx": {
        "producer": "monicanshu_2_suoju.mlx",
        "division_identity": "第一类划分局部物理子结构",
        "dimension_family": "6->2/5",
        "full_dof": 6,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|TP/KPren/MPren|TP_cb/KP_cb/MP_cb",
        "producer_order": "[1,4,2,3,5,6]",
        "consumer_order": "[1,4,2,3,5,6]",
        "dimension_status": "PASS",
        "coordinate_order_status": "PASS",
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_of_energy_zonghe2.mlx": {
        "producer": "PDmonicanshu2.m",
        "division_identity": "第一类划分局部物理子结构",
        "dimension_family": "6->2/5",
        "full_dof": 6,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|T/KRren/MRren|T_cb/KR_cb/MR_cb",
        "producer_order": "[1,4,2,3,5,6]",
        "consumer_order": "external index1,index2; same producer workspace",
        "dimension_status": "PASS",
        "coordinate_order_status": "PASS",
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_2_of_energy_zonghe2.mlx": {
        "producer": "monicanshu_2_suoju.mlx",
        "division_identity": "第一类划分局部物理子结构",
        "dimension_family": "6->2/5",
        "full_dof": 6,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|TP/KPren/MPren|TP_cb/KP_cb/MP_cb",
        "producer_order": "[1,4,2,3,5,6]",
        "consumer_order": "[1,4,2,3,5,6]",
        "dimension_status": "PASS",
        "coordinate_order_status": "PASS",
        "candidate_status": "STATIC_CANDIDATE_FORMULA_INVALID",
    },
    "energy_zonghe3.mlx": {
        "producer": "monicanshu_3_suoju.mlx",
        "division_identity": "第二类划分局部物理子结构",
        "dimension_family": "9->2/5",
        "full_dof": 9,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|TP/KPren/MPren|TP_cb/KP_cb/MP_cb",
        "producer_order": "[1,7,2,3,4,5,6,8,9]",
        "consumer_order": "[1,7,4,2,3,5,6,8,9]",
        "dimension_status": "PASS",
        "coordinate_order_status": "FAIL",
        "candidate_status": "STATIC_CANDIDATE_COORDINATE_SEMANTICS_FAIL",
    },
    "Copy_of_energy_zonghe3.mlx": {
        "producer": "PDmonicanshu3.m",
        "division_identity": "第二类划分局部物理子结构",
        "dimension_family": "9->2/5",
        "full_dof": 9,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|T/KRren/MRren|T_cb/KR_cb/MR_cb",
        "producer_order": "[1,7,4,2,3,5,6,8,9]",
        "consumer_order": "external index1,index2; same producer workspace",
        "dimension_status": "PASS",
        "coordinate_order_status": "PASS",
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_2_of_energy_zonghe3.mlx": {
        "producer": "monicanshu_3_suoju.mlx",
        "division_identity": "第二类划分局部物理子结构",
        "dimension_family": "9->2/5",
        "full_dof": 9,
        "guyan_dof": 2,
        "cb_dof": 5,
        "variable_family": "KPrt/MPrt|TP/KPren/MPren|TP_cb/KP_cb/MP_cb",
        "producer_order": "[1,7,2,3,4,5,6,8,9]",
        "consumer_order": "[1,7,4,2,3,5,6,8,9]",
        "dimension_status": "PASS",
        "coordinate_order_status": "FAIL",
        "candidate_status": "STATIC_CANDIDATE_COORDINATE_AND_FORMULA_FAIL",
    },
}

DEPENDENCY_FILE_CONTRACTS: dict[str, tuple[str, str, str]] = {
    "PDmonicanshu.m": ("15自由度参考结构及3/6维缩聚准备", "energy_zonghe.mlx入口", "旧水平主坐标体系，不代表表4-1两类整体划分"),
    "PDmonicanshu2.m": ("第一类6自由度局部结构及2/5维缩聚准备", "Copy_of_energy_zonghe2.mlx入口", "密度系数与MLX参数族不同"),
    "PDmonicanshu3.m": ("第二类9自由度局部结构及2/5维缩聚准备", "Copy_of_energy_zonghe3.mlx入口", "密度系数与MLX参数族不同"),
    "energy.m": ("18维模态参与系数试验", "不形成式(4-43)至式(4-45)", "与15维PDmonicanshu矩阵不相容"),
    "tes.m": ("任意维全1激励参与质量试验", "不是表4-1入口", "平动与转动自由度均被激励"),
    "monicanshu_2.mlx": ("第一类18维响应参数准备", "不直接生产能量缩聚矩阵", "初始化注释维数与实际18维冲突"),
    "monicanshu_2_suoju.mlx": ("第一类局部TP-family及整体/数值侧缩聚准备", "energy_zonghe2与Copy_2_of_energy_zonghe2入口", "静态变量名、维数和坐标顺序闭合"),
    "monicanshu_3.mlx": ("第二类18维响应与稳定性参数准备", "不直接生产能量缩聚矩阵", "29项依赖中唯一包含未注释save语句的脚本"),
    "monicanshu_3_suoju.mlx": ("第二类局部TP-family及整体/数值侧缩聚准备", "energy_zonghe3与Copy_2_of_energy_zonghe3名义入口", "生产者与消费者坐标顺序不一致"),
    "simulink_str_2.mlx": ("第一类18维状态空间准备", "供lvxvjie_guyan_2.slx", "不生产表4-1能量量"),
    "simulink_str_3.mlx": ("第二类18维状态空间准备", "供lvxvjie_guyan_3.slx", "不生产表4-1能量量"),
    "untitled.mlx": ("当前第二类整体15到5/8维响应缩聚试验", "不对应energy_zonghe历史3/6维身份", "注释写前5模态而代码r=3"),
    "untitled2.mlx": ("第一类6到2/5维特征值和能量比试验", "旁支试验", "保存状态error，Guyan仅2项却索引前5项"),
    "untitled3.mlx": ("第一类6到2维加权能量差试验", "缺失入口", "K_r与M_r无生产者"),
    "untitled4.mlx": ("第二类9到2维加权能量差试验", "缺失入口", "K_r与M_r无生产者"),
    "luxvjie_cb_2.mlx": ("Craig-Bampton稳定性候选", "不生产能量入口", "与_3字节相同且遗漏整体自由度2"),
    "luxvjie_cb_3.mlx": ("Craig-Bampton稳定性候选", "不生产能量入口", "与_2字节相同，不能区分两类"),
    "luxvjie_guyan_2.mlx": ("Guyan稳定性候选", "不生产能量入口", "内部主坐标不符合当前两类任一集合"),
    "luxvjie_cb_LQR2.mlx": ("第一类Craig-Bampton LQR稳定性", "不生产能量入口", "保存状态error且索引集合重叠"),
    "luxvjie_cb_LQR3.mlx": ("第二类Craig-Bampton LQR稳定性", "不生产能量入口", "仅稳定性旁支"),
    "luxvjie_guyan_LQR2.mlx": ("第一类Guyan LQR稳定性", "不生产能量入口", "符号z先使用后声明"),
    "luxvjie_guyan_LQR3.mlx": ("第二类Guyan LQR稳定性", "不生产能量入口", "符号z先使用后声明"),
    "luxvjie_ori_LQR2.mlx": ("第一类原系统LQR稳定性", "不生产能量入口", "save语句已注释"),
    "luxvjie_ori_LQR3.mlx": ("第二类原系统LQR稳定性", "不生产能量入口", "仅稳定性旁支"),
    "EQ.mat": ("El Centro地震时程与开关/强度", "响应旁支", "不是模态能量入口"),
    "stab_3.mat": ("20乘20历史稳定性网格", "稳定性旁支", "不含质量、模态或缩聚矩阵"),
    "lvxvjie_guyan_2.slx": ("第一类18维响应模型", "响应旁支", "缺外部地震MAT且无自动准备回调"),
    "lvxvjie_guyan_3.slx": ("第二类18维响应模型", "响应旁支", "缺外部地震MAT且无自动准备回调"),
    "test.slx": ("临时响应比较模型", "响应旁支", "不生成表4-1能量量且缺外部地震MAT"),
}
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_STYLE = f"{{{WORD_NS}}}val"
IDENTIFIER_RE = re.compile(r"(?<![.'\"])[A-Za-z]\w*")
SIMPLE_ASSIGNMENT_RE = re.compile(r"(?m)^\s*([A-Za-z]\w*)\s*=(?!=)")
MULTI_ASSIGNMENT_RE = re.compile(r"(?m)^\s*\[([^\]]+)\]\s*=(?!=)")
FUNCTION_CALL_RE = re.compile(r"\b([A-Za-z]\w*)\s*\(")

MATLAB_KEYWORDS = {
    "break",
    "case",
    "catch",
    "classdef",
    "continue",
    "else",
    "elseif",
    "end",
    "for",
    "function",
    "global",
    "if",
    "otherwise",
    "parfor",
    "persistent",
    "return",
    "spmd",
    "switch",
    "try",
    "while",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.replace("\r\n", "\n").encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    write_text(path, stream.getvalue())


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def classify_file(name: str) -> str:
    if name in ENERGY_SCRIPTS:
        return "energy_summary_route"
    if name.startswith("monicanshu_") or name.startswith("untitled"):
        return "matrix_or_reduction_preparation"
    if name.startswith("luxvjie_"):
        return "modal_or_stability_candidate"
    if name.startswith("simulink_str_"):
        return "state_space_preparation"
    if name.startswith("PDmonicanshu"):
        return "physical_parameter_script"
    if name.endswith(".slx"):
        return "simulink_model"
    if name.endswith(".mat"):
        return "saved_workspace_or_result"
    return "auxiliary_script"


def strip_matlab_comment(line: str) -> str:
    in_character_vector = False
    index = 0
    while index < len(line):
        character = line[index]
        if character == "'":
            if in_character_vector:
                if index + 1 < len(line) and line[index + 1] == "'":
                    index += 2
                    continue
                in_character_vector = False
            else:
                prefix = line[:index].rstrip()
                previous = prefix[-1] if prefix else ""
                if not prefix or previous in "([{,=:+-*/\\^~;":
                    in_character_vector = True
        elif character == "%" and not in_character_vector:
            return line[:index]
        index += 1
    return line


def noncomment_code(code: str) -> str:
    retained = []
    for line in code.splitlines():
        content = strip_matlab_comment(line)
        if content.strip():
            retained.append(content)
    return "\n".join(retained)


def code_tokens(code: str) -> tuple[list[str], list[str], list[str]]:
    active = noncomment_code(code)
    assignments = set(SIMPLE_ASSIGNMENT_RE.findall(active))
    for match in MULTI_ASSIGNMENT_RE.findall(active):
        assignments.update(
            token.strip()
            for token in match.split(",")
            if re.fullmatch(r"[A-Za-z]\w*", token.strip())
        )
    calls = {
        name
        for name in FUNCTION_CALL_RE.findall(active)
        if name not in MATLAB_KEYWORDS
    }
    identifiers = {
        name
        for name in IDENTIFIER_RE.findall(active)
        if name not in MATLAB_KEYWORDS
    }
    return sorted(assignments), sorted(calls), sorted(identifiers)


def extract_output_element(element: ET.Element, index: int) -> dict[str, Any]:
    raw = ET.tostring(element, encoding="utf-8")
    output_data = element.find("./outputData")
    output_type = element.findtext("./type", default="")
    line_numbers = [
        node.text or "" for node in element.findall("./lineNumbers/element")
    ]
    fields: dict[str, str] = {}
    large_fields: dict[str, dict[str, Any]] = {}
    if output_data is not None:
        for node in output_data.iter():
            if len(node):
                continue
            key = local_name(node.tag)
            value = node.text or ""
            if key == "figureUri" or value.startswith("data:image/"):
                large_fields[key] = {
                    "length": len(value),
                    "sha256": sha256_bytes(value.encode("utf-8")),
                }
            elif key not in fields:
                fields[key] = value
    return {
        "output_index": index,
        "output_xpath": f"/embeddedOutputs/outputArray/element[{index}]",
        "output_type": output_type,
        "line_numbers": line_numbers,
        "name": fields.get("name", ""),
        "var_size": fields.get("varSize", ""),
        "rows": fields.get("rows", ""),
        "columns": fields.get("columns", ""),
        "var_type": fields.get("varType", ""),
        "value": fields.get("value", fields.get("text", "")),
        "leaf_fields": fields,
        "large_fields": large_fields,
        "element_sha256": sha256_bytes(raw),
    }


def extract_mlx(path: Path) -> dict[str, Any]:
    source_before = sha256_file(path)
    with zipfile.ZipFile(path) as archive:
        names = sorted(archive.namelist(), key=str.casefold)
        document_payload = archive.read("matlab/document.xml")
        output_payload = (
            archive.read("matlab/output.xml")
            if "matlab/output.xml" in names
            else b""
        )
    document_root = ET.fromstring(document_payload)
    namespace = {"w": WORD_NS}
    paragraphs: list[dict[str, Any]] = []
    code_cells: list[str] = []
    text_cells: list[str] = []
    for paragraph_index, paragraph in enumerate(
        document_root.findall(".//w:body/w:p", namespace), start=1
    ):
        style_node = paragraph.find("./w:pPr/w:pStyle", namespace)
        style = style_node.attrib.get(WORD_STYLE, "") if style_node is not None else ""
        text = "".join(paragraph.itertext())
        if not text.strip():
            continue
        kind = "code" if style == "code" else "text"
        if kind == "code":
            code_cells.append(text)
            cell_index = len(code_cells)
        else:
            text_cells.append(text)
            cell_index = len(text_cells)
        paragraphs.append(
            {
                "paragraph_index": paragraph_index,
                "xml_xpath": f"/w:document/w:body/w:p[{paragraph_index}]",
                "kind": kind,
                "cell_index": cell_index,
                "style": style,
                "text": text,
                "text_sha256": sha256_bytes(text.encode("utf-8")),
            }
        )

    outputs: list[dict[str, Any]] = []
    output_metadata = {
        "evaluation_state": "",
        "output_status": "",
        "error_element_count": 0,
        "error_messages": "",
    }
    if output_payload:
        output_root = ET.fromstring(output_payload)
        output_metadata = {
            "evaluation_state": output_root.findtext(
                "./metaData/evaluationState", default=""
            ),
            "output_status": output_root.findtext(
                "./metaData/outputStatus", default=""
            ),
            "error_element_count": 0,
            "error_messages": "",
        }
        for index, element in enumerate(
            output_root.findall(".//outputArray/element"), start=1
        ):
            outputs.append(extract_output_element(element, index))
        error_outputs = [
            output for output in outputs if output["output_type"].lower() == "error"
        ]
        output_metadata["error_element_count"] = len(error_outputs)
        output_metadata["error_messages"] = " | ".join(
            output["value"] for output in error_outputs
        )

    combined_code = "\n\n".join(code_cells)
    assignments, calls, identifiers = code_tokens(combined_code)
    source_after = sha256_file(path)
    if source_after != source_before:
        raise RuntimeError(f"MLX changed during extraction: {path}")
    return {
        "source_name": path.name,
        "source_sha256": source_before,
        "source_size_bytes": path.stat().st_size,
        "archive_entries": names,
        "document_xml_sha256": sha256_bytes(document_payload),
        "output_xml_sha256": sha256_bytes(output_payload) if output_payload else "",
        "output_metadata": output_metadata,
        "paragraphs": paragraphs,
        "code_cells": code_cells,
        "text_cells": text_cells,
        "outputs": outputs,
        "assignments": assignments,
        "function_calls": calls,
        "identifiers": identifiers,
    }


def extracted_code_text(record: dict[str, Any]) -> str:
    lines = [
        f"% Static extraction from {record['source_name']}",
        f"% Source SHA-256: {record['source_sha256']}",
        "% No MATLAB execution was performed.",
        "",
    ]
    for index, code in enumerate(record["code_cells"], start=1):
        lines.extend((f"%% CODE_CELL_C{index:03d}", code.rstrip(), ""))
    return "\n".join(lines).rstrip() + "\n"


def extracted_cell_locations(record: dict[str, Any]) -> dict[int, dict[str, int]]:
    locations: dict[int, dict[str, int]] = {}
    header_line = 5
    for index, code in enumerate(record["code_cells"], start=1):
        code_line_count = max(1, len(code.splitlines()))
        locations[index] = {
            "extracted_header_line": header_line,
            "extracted_code_start_line": header_line + 1,
            "extracted_code_end_line": header_line + code_line_count,
        }
        header_line += code_line_count + 2
    return locations


def output_rows_for_mlx(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for output in record["outputs"]:
        rows.append(
            {
                "source_name": record["source_name"],
                "source_sha256": record["source_sha256"],
                "output_index": output["output_index"],
                "output_xpath": output["output_xpath"],
                "output_type": output["output_type"],
                "line_numbers": "|".join(output["line_numbers"]),
                "name": output["name"],
                "var_size": output["var_size"],
                "rows": output["rows"],
                "columns": output["columns"],
                "var_type": output["var_type"],
                "value": output["value"],
                "element_sha256": output["element_sha256"],
                "large_field_summary": json.dumps(
                    output["large_fields"], ensure_ascii=False, sort_keys=True
                ),
            }
        )
    return rows


def read_text_source(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", payload, 0, 1, f"Cannot decode {path}")


def mat_scalar(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, (float, int, str, bool)):
        return value
    return str(value)


def inventory_mat(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, shape, matlab_class in whosmat(path):
        loaded = loadmat(path, variable_names=[name], squeeze_me=False, struct_as_record=False)
        value = loaded.get(name)
        dtype = str(getattr(value, "dtype", ""))
        data_sha = ""
        finite_count: int | str = ""
        minimum: Any = ""
        maximum: Any = ""
        if isinstance(value, np.ndarray) and value.dtype != object:
            contiguous = np.ascontiguousarray(value)
            data_sha = sha256_bytes(
                (str(contiguous.dtype) + "|" + repr(contiguous.shape) + "|").encode(
                    "utf-8"
                )
                + contiguous.tobytes()
            )
            if np.issubdtype(value.dtype, np.number):
                finite = np.isfinite(value)
                finite_count = int(np.count_nonzero(finite))
                if finite_count:
                    finite_values = np.real(value[finite])
                    minimum = mat_scalar(np.min(finite_values))
                    maximum = mat_scalar(np.max(finite_values))
        rows.append(
            {
                "source_name": path.name,
                "source_sha256": sha256_file(path),
                "variable_name": name,
                "shape": "x".join(str(item) for item in shape),
                "matlab_class": matlab_class,
                "numpy_dtype": dtype,
                "data_sha256": data_sha,
                "finite_count": finite_count,
                "minimum_real": minimum,
                "maximum_real": maximum,
            }
        )
    return rows


def inventory_slx(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    block_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    xml_entry_count = 0
    with zipfile.ZipFile(path) as archive:
        archive_entries = sorted(archive.namelist(), key=str.casefold)
        for entry_name in archive_entries:
            if not entry_name.lower().endswith(".xml"):
                continue
            xml_entry_count += 1
            try:
                root = ET.fromstring(archive.read(entry_name))
            except ET.ParseError:
                continue
            for block in root.iter("Block"):
                block_row = {
                    "source_name": path.name,
                    "xml_entry": entry_name,
                    "sid": block.attrib.get("SID", ""),
                    "block_type": block.attrib.get("BlockType", ""),
                    "block_name": block.attrib.get("Name", ""),
                }
                block_rows.append(block_row)
                for parameter in block.findall("./P"):
                    value = "".join(parameter.itertext())
                    parameter_rows.append(
                        {
                            **block_row,
                            "parameter_name": parameter.attrib.get("Name", ""),
                            "parameter_value": value,
                        }
                    )
    summary = {
        "source_name": path.name,
        "source_sha256": sha256_file(path),
        "source_size_bytes": path.stat().st_size,
        "archive_entry_count": len(archive_entries),
        "xml_entry_count": xml_entry_count,
        "block_count": len(block_rows),
        "parameter_count": len(parameter_rows),
        "block_type_counts": dict(
            sorted(Counter(row["block_type"] for row in block_rows).items())
        ),
    }
    return block_rows, parameter_rows, summary


def active_lines_matching(code: str, token: str) -> list[str]:
    return [
        line.strip()
        for line in noncomment_code(code).splitlines()
        if token in line
    ]


def active_assignment_lines(code: str, variable: str) -> list[str]:
    pattern = re.compile(rf"\s*{re.escape(variable)}\s*=")
    return [
        line.strip()
        for line in noncomment_code(code).splitlines()
        if pattern.match(line)
    ]


def route_record(record: dict[str, Any]) -> dict[str, Any]:
    code = "\n".join(record["code_cells"])
    active = noncomment_code(code)
    contract = ROUTE_STATIC_CONTRACTS[record["source_name"]]
    named_outputs = {
        output["name"]: output["value"]
        for output in record["outputs"]
        if output["name"]
    }
    guy_value = named_outputs.get("total_increase_guyan", "")
    cb_value = named_outputs.get("total_increase_cb", "")
    branch_active = [noncomment_code(cell) for cell in record["code_cells"][:3]]
    branch_mass_normalization = [
        bool(re.search(r"phi\(:,i\)\s*=\s*phi\(:,i\)\s*/\s*sqrt", cell))
        for cell in branch_active
    ]
    branch_energy_normalization = [
        bool(re.search(r"E\(:,i\)\s*=\s*E\(:,i\)\s*/\s*sum\(E\(:,i\)\)", cell))
        for cell in branch_active
    ]
    branch_participation_normalization = [
        bool(re.search(r"participation_ratio\s*=\s*GammaSq\s*/\s*sum\(GammaSq\)", cell))
        for cell in branch_active
    ]
    total_output_name_counts = Counter(
        output["name"]
        for output in record["outputs"]
        if output["name"] in {"total_increase_guyan", "total_increase_cb"}
    )
    row = {
        "source_name": record["source_name"],
        "source_sha256": record["source_sha256"],
        "saved_output_evidence_level": "历史保存输出",
        "saved_output_source": "embedded_historical",
        "evaluation_state": record["output_metadata"]["evaluation_state"],
        "output_status": record["output_metadata"]["output_status"],
        "code_cell_count": len(record["code_cells"]),
        "external_workspace_only": not bool(
            re.search(r"(?m)^\s*(load|save|run|sim|cd|clear)\s*(?:\(|\s|$)", active)
        ),
        "original_mass_normalization_active": branch_mass_normalization[0],
        "guyan_mass_normalization_active": branch_mass_normalization[1],
        "cb_mass_normalization_active": branch_mass_normalization[2],
        "original_energy_normalization_active": branch_energy_normalization[0],
        "guyan_energy_normalization_active": branch_energy_normalization[1],
        "cb_energy_normalization_active": branch_energy_normalization[2],
        "original_participation_normalization_active": branch_participation_normalization[0],
        "guyan_participation_normalization_active": branch_participation_normalization[1],
        "cb_participation_normalization_active": branch_participation_normalization[2],
        "mass_normalization_active": bool(
            re.search(r"phi\(:,i\)\s*=\s*phi\(:,i\)\s*/\s*sqrt", active)
        ),
        "modal_energy_normalization_active": bool(
            re.search(r"E\(:,i\)\s*=\s*E\(:,i\)\s*/\s*sum\(E\(:,i\)\)", active)
        ),
        "participation_ratio_normalized": bool(
            re.search(r"participation_ratio\s*=\s*GammaSq\s*/\s*sum\(GammaSq\)", active)
        ),
        "active_r_lines": " | ".join(active_assignment_lines(code, "r")),
        "active_order_lines": " | ".join(active_lines_matching(code, "order =")),
        "active_d_lines": " | ".join(
            line
            for line in active.splitlines()
            if re.match(r"\s*d2?\s*=", line)
        ),
        "guyan_total_formula": " | ".join(
            active_lines_matching(code, "total_increase_guyan")
        ),
        "cb_total_formula": " | ".join(
            active_lines_matching(code, "total_increase_cb")
        ),
        "cb_uses_guyan_denominator": bool(
            re.search(
                r"total_increase_cb\s*=.*?/\s*energy_sum_guyan", active
            )
        ),
        "equation_4_45_exact": False,
        "saved_guyan_output_count": total_output_name_counts["total_increase_guyan"],
        "saved_cb_output_count": total_output_name_counts["total_increase_cb"],
        "saved_total_increase_guyan": guy_value,
        "saved_total_increase_cb": cb_value,
        "saved_guyan_div100": numeric_div100(guy_value),
        "saved_cb_div100": numeric_div100(cb_value),
        "assignments": "|".join(record["assignments"]),
        "function_calls": "|".join(record["function_calls"]),
    }
    row.update(contract)
    return row


def numeric_div100(value: str) -> str:
    try:
        number = float(value.strip().split()[0])
    except (ValueError, IndexError):
        return ""
    if not math.isfinite(number):
        return ""
    return f"{number / 100:.8f}"


def paper_formula_rows() -> list[dict[str, Any]]:
    return [
        {
            "equation": "4-41",
            "pdf_page": 72,
            "printed_page": 62,
            "literal_formula": "Gamma_i=(phi_i^T M r)/(phi_i^T M phi_i)",
            "required_inputs": "phi_i|M|r",
            "hard_invariant": "denominator_nonzero",
            "open_issue": "modal normalization convention is not stated",
            "evidence_level": "论文原文公式",
        },
        {
            "equation": "4-42",
            "pdf_page": 72,
            "printed_page": 62,
            "literal_formula": "p_i=Gamma_i^2/sum_{k=1}^m Gamma_k^2",
            "required_inputs": "Gamma|m|modal_order",
            "hard_invariant": "sum_i(p_i)=1",
            "open_issue": "m and modal ordering are not stated for Table 4-1",
            "evidence_level": "论文原文公式",
        },
        {
            "equation": "4-43",
            "pdf_page": 72,
            "printed_page": 62,
            "literal_formula": "E_{j,i}=m_j phi_{j,i}^2/sum_{l=1}^n(m_l phi_{l,i}^2)",
            "required_inputs": "scalar_m_j|phi|n",
            "hard_invariant": "for each i: sum_j(E_{j,i})=1",
            "open_issue": "off-diagonal mass and translational/rotational mass convention are not stated",
            "evidence_level": "论文原文公式",
        },
        {
            "equation": "4-44",
            "pdf_page": 72,
            "printed_page": 62,
            "literal_formula": "E_j^total=sum_{i=1}^m p_i E_{j,i}",
            "required_inputs": "p_i|E_{j,i}|m",
            "hard_invariant": "sum_j(E_j^total)=1",
            "open_issue": "Craig-Bampton physical-coordinate recovery is not stated",
            "evidence_level": "论文原文公式",
        },
        {
            "equation": "4-45",
            "pdf_page": 72,
            "printed_page": 62,
            "literal_formula": "Delta E_k=sum_{k=1}^q[(E_guyan^total(k)-E^total(d_k))/E^total(d_k)]",
            "required_inputs": "D={d_1,...,d_q}|E_guyan^total|E^total",
            "hard_invariant": "all reference denominators nonzero; preserve signed sum",
            "open_issue": "left index conflicts with summed k; D mapping is underdefined; only Guyan symbol is printed",
            "evidence_level": "论文原文公式",
        },
    ]


def historical_target_rows() -> list[dict[str, Any]]:
    return [
        {
            "division": "第一类划分",
            "method": "Guyan",
            "paper_value": "0.3065",
            "unit_printed": "none",
            "evidence_level": "历史值",
        },
        {
            "division": "第一类划分",
            "method": "Craig-Bampton",
            "paper_value": "0.1879",
            "unit_printed": "none",
            "evidence_level": "历史值",
        },
        {
            "division": "第二类划分",
            "method": "Guyan",
            "paper_value": "0.3927",
            "unit_printed": "none",
            "evidence_level": "历史值",
        },
        {
            "division": "第二类划分",
            "method": "Craig-Bampton",
            "paper_value": "0.2021",
            "unit_printed": "none",
            "evidence_level": "历史值",
        },
    ]


def dependency_file_rows() -> list[dict[str, Any]]:
    return [
        {
            "source_name": source_name,
            "static_role": contract[0],
            "energy_relation": contract[1],
            "known_boundary_or_issue": contract[2],
        }
        for source_name, contract in sorted(
            DEPENDENCY_FILE_CONTRACTS.items(), key=lambda item: item[0].casefold()
        )
    ]


def dependency_edge_rows() -> list[dict[str, Any]]:
    rows = []
    for consumer in ENERGY_SCRIPTS:
        contract = ROUTE_STATIC_CONTRACTS[consumer]
        producer = contract["producer"]
        if consumer == "energy_zonghe.mlx":
            retained_mapping = "reduced[1,2,3]->global[1,6,11]"
        elif consumer.endswith("zonghe2.mlx"):
            retained_mapping = "reduced[1,2]->local[1,4]->global[1,6]"
        else:
            retained_mapping = "reduced[1,2]->local[1,7]->global[1,11]"
        rows.append(
            {
                "producer": producer,
                "consumer": consumer,
                "division_identity": contract["division_identity"],
                "dimension_family": contract["dimension_family"],
                "variable_family": contract["variable_family"],
                "producer_order": contract["producer_order"],
                "consumer_order": contract["consumer_order"],
                "dimension_status": contract["dimension_status"],
                "coordinate_order_status": contract["coordinate_order_status"],
                "parameter_family": "rho=785e3*1.9"
                if producer.startswith("PDmonicanshu")
                else "rho=785e3*1.7",
                "retained_coordinate_mapping": retained_mapping,
                "explicit_upstream_workspace_dependency": True,
                "candidate_status": contract["candidate_status"],
                "step3_execution_status": "NOT_RUN",
            }
        )
    return rows


def formula_route_rows(route_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    copy_2_names = {
        "Copy_2_of_energy_zonghe2.mlx",
        "Copy_2_of_energy_zonghe3.mlx",
    }
    repeated_mass_names = {
        "energy_zonghe2.mlx",
        "Copy_2_of_energy_zonghe2.mlx",
    }
    for route in route_rows:
        source = route["source_name"]
        influence_note = (
            "r0=MPrt*ones后代码仍计算phi^T*M*r，存在重复质量矩阵风险"
            if source in repeated_mass_names
            else "质量归一化使论文分母数值为1，但激励向量身份仍未由脚本证明"
        )
        rows.extend(
            [
                {
                    "source_name": source,
                    "equation": "4-41",
                    "implementation": "质量归一化phi后执行Gamma=phi^T*M*r",
                    "static_status": "PARTIAL",
                    "reason": influence_note,
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-42",
                    "implementation": "GammaSq=Gamma.^2; participation_ratio=GammaSq/sum(GammaSq)",
                    "static_status": "STRUCTURAL_MATCH",
                    "reason": "归一化结构与论文一致，但继承式(4-41)的激励身份风险",
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-43",
                    "implementation": "E=0.5*omega^2*m*phi^2后按列归一化"
                    if source not in copy_2_names
                    else "E=0.5*omega^2*m*phi^2；按列归一化被注释",
                    "static_status": "STRUCTURAL_MATCH"
                    if source not in copy_2_names
                    else "FORMULA_MISMATCH",
                    "reason": "按列归一化后0.5*omega^2逐列消去"
                    if source not in copy_2_names
                    else "未形成论文要求的单模态坐标能量占比",
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-44",
                    "implementation": "E_total=E*participation_ratio",
                    "static_status": "STRUCTURAL_MATCH"
                    if source not in copy_2_names
                    else "INPUT_IDENTITY_MISMATCH",
                    "reason": "矩阵乘法结构与论文一致"
                    if source not in copy_2_names
                    else "输入E未归一化，输出不再是综合能量占比",
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-45",
                    "implementation": (
                        f"G:{route['guyan_total_formula']} | CB:{route['cb_total_formula']}"
                    ),
                    "static_status": "FORMULA_MISMATCH",
                    "reason": "最终标量使用能量和的相对变化，未执行论文逐坐标相对变化之和",
                    "evidence_cell": "C004",
                },
            ]
        )
    return rows


def historical_match_rows(
    target_rows: list[dict[str, Any]], route_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for target in target_rows:
        value_key = (
            "saved_total_increase_guyan"
            if target["method"] == "Guyan"
            else "saved_total_increase_cb"
        )
        matches = []
        for route in route_rows:
            try:
                saved_percent = float(route[value_key])
            except (TypeError, ValueError):
                continue
            divided = saved_percent / 100.0
            if f"{divided:.4f}" == f"{float(target['paper_value']):.4f}":
                matches.append(
                    {
                        "source_name": route["source_name"],
                        "saved_percent": f"{saved_percent:.4f}",
                        "saved_div100": f"{divided:.6f}",
                    }
                )
        rows.append(
            {
                **target,
                "matching_rule": "saved_percent/100 rounded to 4 decimals",
                "matched_routes": "|".join(item["source_name"] for item in matches),
                "matched_saved_percent": "|".join(
                    item["saved_percent"] for item in matches
                ),
                "matched_div100": "|".join(item["saved_div100"] for item in matches),
                "match_status": "NUMERIC_MATCH_FORMULA_INVALID"
                if matches
                else "NO_SAVED_OUTPUT_MATCH",
                "formula_compliant_match": False,
            }
        )
    return rows


def static_issue_rows() -> list[dict[str, Any]]:
    issues = [
        ("S01", "CRITICAL", "all seven energy routes", "最终标量均未实现论文式(4-45)", "表4-1不存在统一公式入口"),
        ("S02", "CRITICAL", "Copy_2_of_energy_zonghe3.mlx", "唯一命中第二类两值的路线关闭式(4-43)归一化且CB错用Guyan分母", "数值命中不能作为公式复现"),
        ("S03", "CRITICAL", "Table 4-1 first division", "0.3065和0.1879在七份保存标量中均无匹配", "第一类两值仍无入口"),
        ("S04", "HIGH", "all seven energy routes", "脚本无load/run/sim/cd，依赖污染工作区", "历史调用顺序未被原工程记录"),
        ("S05", "CRITICAL", "monicanshu_3_suoju -> zonghe3 TP-family", "生产者与消费者自由度顺序不一致", "维数通过但物理坐标语义失败"),
        ("S06", "HIGH", "PDmonicanshu family versus monicanshu MLX family", "密度系数分别为785e3*1.9与785e3*1.7", "同名义划分存在不同参数族"),
        ("S07", "CRITICAL", "two whole-structure divisions", "当前15->6/9与15->5/8整体划分没有对应七份能量汇总入口", "不能把局部6/9维结果静默当成整体表值"),
        ("S08", "HIGH", "equation 4-41", "激励方向或广义荷载身份未闭合，部分路线可能重复乘质量矩阵", "参与因子含义待原样运行和独立公式审计"),
        ("S09", "HIGH", "equation 4-45", "d/d2默认坐标一一对应但没有映射断言", "坐标重排可静默改变结果"),
        ("S10", "HIGH", "untitled3.mlx|untitled4.mlx", "K_r与M_r无生产者", "历史旁支不可原样重算"),
        ("S11", "HIGH", "luxvjie_cb_2.mlx|luxvjie_cb_3.mlx", "两个文件字节相同且遗漏自由度2", "不能作为两类独立证据"),
        ("S12", "MEDIUM", "three SLX models", "引用三个冻结目录中不存在的地震MAT文件", "响应旁支不能补足能量公式入口"),
        ("S13", "MEDIUM", "Copy_2 energy routes", "注释宣称能量已归一化但执行行被注释", "注释与执行身份冲突"),
        ("S14", "MEDIUM", "saved MLX outputs", "manual/ready或error均为编辑器缓存", "不得称为本轮计算结果"),
    ]
    return [
        {
            "issue_id": issue_id,
            "scientific_severity": severity,
            "scope": scope,
            "finding": finding,
            "consequence": consequence,
            "disposition": "RETAIN_AND_TEST_IN_LATER_STEPS",
        }
        for issue_id, severity, scope, finding, consequence in issues
    ]


def verify_step1_passport() -> None:
    mismatches = []
    for path, expected in STEP1_FIXED_HASHES.items():
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append(f"{path}: expected={expected}, actual={actual}")
    if mismatches:
        raise RuntimeError("Step1 passport mismatch:\n" + "\n".join(mismatches))


def load_expected_author_hashes() -> dict[str, str]:
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = {
        row["role"].removeprefix("author_energy:"): row["frozen_sha256"].upper()
        for row in rows
        if row.get("category") == "author_energy_tree"
    }
    if len(result) != 36:
        raise RuntimeError(f"Expected 36 author-energy manifest rows, got {len(result)}")
    return result


def main() -> int:
    verify_step1_passport()
    expected_hashes = load_expected_author_hashes()
    files = sorted(AUTHOR_ROOT.iterdir(), key=lambda path: path.name.casefold())
    if any(not path.is_file() for path in files):
        raise RuntimeError("Author-energy frozen root must contain files only")
    extension_counts = Counter(path.suffix.lower() for path in files)
    if len(files) != 36 or dict(extension_counts) != EXPECTED_COUNTS:
        raise RuntimeError(
            f"Author-energy inventory drift: count={len(files)}, extensions={dict(extension_counts)}"
        )
    actual_names = {path.name for path in files}
    if actual_names != set(expected_hashes):
        raise RuntimeError(
            f"Author-energy names differ from manifest: missing={set(expected_hashes)-actual_names}, "
            f"extra={actual_names-set(expected_hashes)}"
        )
    if set(DEPENDENCY_FILE_CONTRACTS) != actual_names - set(ENERGY_SCRIPTS):
        raise RuntimeError(
            "Dependency-file contracts do not cover the exact 29 non-summary files"
        )
    if set(ROUTE_STATIC_CONTRACTS) != set(ENERGY_SCRIPTS):
        raise RuntimeError("Route contracts do not cover the exact seven energy scripts")

    all_inventory: list[dict[str, Any]] = []
    mlx_records: dict[str, dict[str, Any]] = {}
    mlx_cell_rows: list[dict[str, Any]] = []
    mlx_output_rows: list[dict[str, Any]] = []
    mlx_metadata_rows: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    mat_rows: list[dict[str, Any]] = []
    slx_block_rows: list[dict[str, Any]] = []
    slx_parameter_rows: list[dict[str, Any]] = []
    slx_summaries: list[dict[str, Any]] = []

    for path in files:
        source_hash = sha256_file(path)
        if source_hash != expected_hashes[path.name]:
            raise RuntimeError(
                f"Frozen author file hash mismatch: {path.name}: {source_hash}"
            )
        inventory = {
            "source_name": path.name,
            "extension": path.suffix.lower(),
            "source_size_bytes": path.stat().st_size,
            "source_sha256": source_hash,
            "role": classify_file(path.name),
            "extraction_status": "PASS",
            "primary_record": "",
            "item_count": 0,
        }
        if path.suffix.lower() == ".mlx":
            record = extract_mlx(path)
            mlx_records[path.name] = record
            code_path = MLX_CODE_ROOT / f"{path.stem}__extracted.m"
            json_path = MLX_JSON_ROOT / f"{path.stem}__record.json"
            write_text(code_path, extracted_code_text(record))
            write_json(json_path, record)
            locations = extracted_cell_locations(record)
            inventory["primary_record"] = json_path.relative_to(OUTPUT_ROOT).as_posix()
            inventory["item_count"] = len(record["code_cells"])
            for paragraph in record["paragraphs"]:
                location = (
                    locations[paragraph["cell_index"]]
                    if paragraph["kind"] == "code"
                    else {
                        "extracted_header_line": "",
                        "extracted_code_start_line": "",
                        "extracted_code_end_line": "",
                    }
                )
                mlx_cell_rows.append(
                    {
                        "source_name": path.name,
                        "source_sha256": source_hash,
                        **paragraph,
                        **location,
                    }
                )
            mlx_output_rows.extend(output_rows_for_mlx(record))
            mlx_metadata_rows.append(
                {
                    "source_name": path.name,
                    "source_sha256": source_hash,
                    "document_xml_sha256": record["document_xml_sha256"],
                    "output_xml_sha256": record["output_xml_sha256"],
                    "evaluation_state": record["output_metadata"]["evaluation_state"],
                    "output_status": record["output_metadata"]["output_status"],
                    "embedded_historical_output_status": record["output_metadata"]["output_status"].upper(),
                    "error_element_count": record["output_metadata"]["error_element_count"],
                    "error_messages": record["output_metadata"]["error_messages"],
                    "code_cell_count": len(record["code_cells"]),
                    "text_cell_count": len(record["text_cells"]),
                    "output_element_count": len(record["outputs"]),
                    "saved_output_evidence_level": "历史保存输出",
                    "static_extraction_status": "PASS",
                }
            )
        elif path.suffix.lower() == ".m":
            text = read_text_source(path)
            assignments, calls, identifiers = code_tokens(text)
            target = TEXT_CODE_ROOT / path.name
            write_text(target, text.rstrip() + "\n")
            text_rows.append(
                {
                    "source_name": path.name,
                    "source_sha256": source_hash,
                    "line_count": len(text.splitlines()),
                    "assignments": "|".join(assignments),
                    "function_calls": "|".join(calls),
                    "identifiers": "|".join(identifiers),
                }
            )
            inventory["primary_record"] = target.relative_to(OUTPUT_ROOT).as_posix()
            inventory["item_count"] = len(text.splitlines())
        elif path.suffix.lower() == ".mat":
            rows = inventory_mat(path)
            mat_rows.extend(rows)
            inventory["primary_record"] = "tables/mat_variables.csv"
            inventory["item_count"] = len(rows)
        elif path.suffix.lower() == ".slx":
            blocks, parameters, summary = inventory_slx(path)
            slx_block_rows.extend(blocks)
            slx_parameter_rows.extend(parameters)
            slx_summaries.append(summary)
            inventory["primary_record"] = "tables/slx_models.csv"
            inventory["item_count"] = len(blocks)
        all_inventory.append(inventory)

    route_rows = [route_record(mlx_records[name]) for name in ENERGY_SCRIPTS]
    paper_rows = paper_formula_rows()
    target_rows = historical_target_rows()
    dependency_rows = dependency_file_rows()
    edge_rows = dependency_edge_rows()
    formula_rows = formula_route_rows(route_rows)
    match_rows = historical_match_rows(target_rows, route_rows)
    issue_rows = static_issue_rows()

    if any(
        route["evaluation_state"] != "manual" or route["output_status"] != "ready"
        for route in route_rows
    ):
        raise RuntimeError("All seven energy routes must be manual/ready saved outputs")
    if len(formula_rows) != 35 or len(dependency_rows) != 29 or len(edge_rows) != 7:
        raise RuntimeError("Curated Step 2 table cardinality drift")

    write_csv(
        TABLE_ROOT / "all_author_files.csv",
        all_inventory,
        [
            "source_name",
            "extension",
            "source_size_bytes",
            "source_sha256",
            "role",
            "extraction_status",
            "primary_record",
            "item_count",
        ],
    )
    write_csv(
        TABLE_ROOT / "mlx_cells.csv",
        mlx_cell_rows,
        [
            "source_name",
            "source_sha256",
            "paragraph_index",
            "xml_xpath",
            "kind",
            "cell_index",
            "style",
            "text_sha256",
            "extracted_header_line",
            "extracted_code_start_line",
            "extracted_code_end_line",
            "text",
        ],
    )
    write_csv(
        TABLE_ROOT / "mlx_outputs.csv",
        mlx_output_rows,
        [
            "source_name",
            "source_sha256",
            "output_index",
            "output_xpath",
            "output_type",
            "line_numbers",
            "name",
            "var_size",
            "rows",
            "columns",
            "var_type",
            "value",
            "element_sha256",
            "large_field_summary",
        ],
    )
    write_csv(
        TABLE_ROOT / "mlx_metadata.csv",
        mlx_metadata_rows,
        [
            "source_name",
            "source_sha256",
            "document_xml_sha256",
            "output_xml_sha256",
            "evaluation_state",
            "output_status",
            "embedded_historical_output_status",
            "error_element_count",
            "error_messages",
            "code_cell_count",
            "text_cell_count",
            "output_element_count",
            "saved_output_evidence_level",
            "static_extraction_status",
        ],
    )
    write_csv(
        TABLE_ROOT / "text_scripts.csv",
        text_rows,
        [
            "source_name",
            "source_sha256",
            "line_count",
            "assignments",
            "function_calls",
            "identifiers",
        ],
    )
    write_csv(
        TABLE_ROOT / "mat_variables.csv",
        mat_rows,
        [
            "source_name",
            "source_sha256",
            "variable_name",
            "shape",
            "matlab_class",
            "numpy_dtype",
            "data_sha256",
            "finite_count",
            "minimum_real",
            "maximum_real",
        ],
    )
    write_csv(
        TABLE_ROOT / "slx_models.csv",
        slx_summaries,
        [
            "source_name",
            "source_sha256",
            "source_size_bytes",
            "archive_entry_count",
            "xml_entry_count",
            "block_count",
            "parameter_count",
            "block_type_counts",
        ],
    )
    write_csv(
        TABLE_ROOT / "slx_blocks.csv",
        slx_block_rows,
        ["source_name", "xml_entry", "sid", "block_type", "block_name"],
    )
    write_csv(
        TABLE_ROOT / "slx_parameters.csv",
        slx_parameter_rows,
        [
            "source_name",
            "xml_entry",
            "sid",
            "block_type",
            "block_name",
            "parameter_name",
            "parameter_value",
        ],
    )
    write_csv(
        TABLE_ROOT / "energy_routes.csv",
        route_rows,
        list(route_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "paper_formula_contract.csv",
        paper_rows,
        list(paper_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "historical_table4_1_targets.csv",
        target_rows,
        list(target_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "dependency_file_roles.csv",
        dependency_rows,
        list(dependency_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "dependency_edges.csv",
        edge_rows,
        list(edge_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "formula_route_audit.csv",
        formula_rows,
        list(formula_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "historical_target_matches.csv",
        match_rows,
        list(match_rows[0]),
    )
    write_csv(
        TABLE_ROOT / "static_issue_register.csv",
        issue_rows,
        list(issue_rows[0]),
    )

    summary = {
        "schema_version": "BOARD21_STEP2_STATIC_INVENTORY_V3",
        "status": "STATIC_INVENTORY_PASS",
        "matlab_executed": False,
        "scientific_reproduction_status": "STATIC_ONLY_NOT_COMPUTATIONALLY_REPRODUCED",
        "author_file_count": len(all_inventory),
        "extension_counts": dict(sorted(extension_counts.items())),
        "mlx_file_count": len(mlx_records),
        "mlx_manual_count": sum(
            row["evaluation_state"] == "manual" for row in mlx_metadata_rows
        ),
        "mlx_embedded_output_ready_count": sum(
            row["output_status"] == "ready" for row in mlx_metadata_rows
        ),
        "mlx_error_count": sum(
            row["output_status"] == "error" for row in mlx_metadata_rows
        ),
        "mlx_explicit_error_element_count": sum(
            int(row["error_element_count"]) for row in mlx_metadata_rows
        ),
        "mlx_code_cell_count": len(
            [row for row in mlx_cell_rows if row["kind"] == "code"]
        ),
        "mlx_text_cell_count": len(
            [row for row in mlx_cell_rows if row["kind"] == "text"]
        ),
        "mlx_output_element_count": len(mlx_output_rows),
        "energy_route_count": len(route_rows),
        "energy_route_embedded_manual_ready_output_count": sum(
            row["evaluation_state"] == "manual" and row["output_status"] == "ready"
            for row in route_rows
        ),
        "dependency_file_count": len(dependency_rows),
        "dependency_edge_count": len(edge_rows),
        "dependency_coordinate_pass_count": sum(
            row["coordinate_order_status"] == "PASS" for row in edge_rows
        ),
        "dependency_coordinate_fail_count": sum(
            row["coordinate_order_status"] == "FAIL" for row in edge_rows
        ),
        "formula_route_audit_count": len(formula_rows),
        "formula_4_45_match_count": sum(
            row["equation"] == "4-45" and row["static_status"] != "FORMULA_MISMATCH"
            for row in formula_rows
        ),
        "historical_numeric_match_count": sum(
            row["match_status"] == "NUMERIC_MATCH_FORMULA_INVALID"
            for row in match_rows
        ),
        "formula_compliant_historical_match_count": sum(
            bool(row["formula_compliant_match"]) for row in match_rows
        ),
        "static_issue_count": len(issue_rows),
        "mat_variable_count": len(mat_rows),
        "slx_model_count": len(slx_summaries),
        "slx_block_count": len(slx_block_rows),
        "slx_parameter_count": len(slx_parameter_rows),
        "paper_formula_count": len(paper_rows),
        "historical_target_count": len(target_rows),
        "step1_passport_hashes": {
            path.relative_to(BOARD_ROOT).as_posix(): expected
            for path, expected in STEP1_FIXED_HASHES.items()
        },
    }
    write_json(OUTPUT_ROOT / "inventory_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
