#!/usr/bin/env python3
"""只读解析板块20冻结的 MLX 输入，生成可审计的代码合同。

计算输入边界：本脚本只会从同级板块目录下的 ``input/`` 递归读取
``*.mlx``，不会回退到作者源目录。仅在所有冻结 MLX 均成功解析后，
才会将转存的 ``.m`` 和 CSV/JSON 合同写入 ``outputs/``。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CODE_STYLE = "code"

MATLAB_KEYWORDS = {
    "break",
    "case",
    "catch",
    "classdef",
    "continue",
    "else",
    "elseif",
    "end",
    "enumeration",
    "events",
    "for",
    "function",
    "global",
    "if",
    "methods",
    "otherwise",
    "parfor",
    "persistent",
    "properties",
    "return",
    "spmd",
    "switch",
    "try",
    "while",
}

# 仅用于静态“读变量候选”降噪；不将未知函数擅自排除。
COMMON_MATLAB_FUNCTIONS = {
    "abs",
    "c2d",
    "cell",
    "diag",
    "disp",
    "dlqr",
    "double",
    "eig",
    "eigs",
    "eye",
    "find",
    "fprintf",
    "full",
    "inv",
    "length",
    "linspace",
    "load",
    "lqr",
    "max",
    "min",
    "ones",
    "save",
    "size",
    "solve",
    "sort",
    "sparse",
    "sqrt",
    "ss",
    "sym",
    "syms",
    "tf",
    "vpa",
    "zeros",
}

IDENTIFIER_RE = re.compile(r"(?<![\w.])([A-Za-z]\w*)")
ASSIGNMENT_RE = re.compile(r"(?<![<>=~])=(?!=)")
LQR_CALL_RE = re.compile(r"(?<![A-Za-z0-9_])lqr\s*\(", re.IGNORECASE)
DLQR_CALL_RE = re.compile(r"(?<![A-Za-z0-9_])dlqr\s*\(", re.IGNORECASE)
QR_LITERAL_RE = re.compile(
    r"(?m)^\s*(?P<name>[QR])\s*=\s*(?P<value>[^;\r\n]+)"
)
FOR_RANGE_RE = re.compile(
    r"(?m)^\s*(?:par)?for\s+(?P<variable>[A-Za-z]\w*)\s*=\s*"
    r"(?P<range>[^%\r\n]+)"
)
H_INIT_RE = re.compile(
    r"\bH\s*=\s*(?:sym\s*\(\s*)?"
    r"(?P<constructor>zeros|eye)\s*\(\s*(?P<dimensions>[^)]+?)\s*\)\s*\)?",
    re.IGNORECASE,
)
H_ASSIGN_RE = re.compile(
    r"(?m)^\s*H\s*\(\s*(?P<position>[^)]+?)\s*\)\s*=\s*"
    r"(?P<value>[^;\r\n]+)"
)
SAVE_CALL_RE = re.compile(
    r"\bsave\s*\(\s*['\"](?P<target>[^'\"]+)['\"]", re.IGNORECASE
)
SAVE_COMMAND_RE = re.compile(
    r"(?m)^\s*save\s+(?!\()(?P<target>[^\s;%]+)", re.IGNORECASE
)


class ContractError(RuntimeError):
    """可预期的合同审计失败。"""


@dataclass(frozen=True)
class ParsedMlx:
    """单个冻结 MLX 的内存解析结果。"""

    source_path: Path
    frozen_relative_path: str
    output_relative_path: str
    source_sha256: str
    normalized_code: str
    normalized_code_sha256: str
    code_line_count: int
    nonblank_code_line_count: int
    read_variables_candidate: tuple[str, ...]
    write_variables_candidate: tuple[str, ...]
    external_read_variables_candidate: tuple[str, ...]
    lqr_call_count: int
    dlqr_call_count: int
    q_literals: tuple[str, ...]
    r_literals: tuple[str, ...]
    loop_ranges: tuple[dict[str, str], ...]
    h_initializations: tuple[dict[str, str], ...]
    h_nonzero_positions: tuple[dict[str, str], ...]
    save_targets: tuple[str, ...]
    embedded_output_status: tuple[str, ...]
    source_role: str


def sha256_bytes(payload: bytes) -> str:
    """返回大写 SHA-256。"""

    return hashlib.sha256(payload).hexdigest().upper()


def local_name(tag: str) -> str:
    """去掉 XML 命名空间。"""

    return tag.rsplit("}", 1)[-1]


def attribute_by_local_name(element: ET.Element, wanted: str) -> str | None:
    """按局部名读取 XML 属性。"""

    for key, value in element.attrib.items():
        if local_name(key) == wanted:
            return value
    return None


def normalize_code_units(code_units: Sequence[str]) -> str:
    """统一换行、行末空白与单元边界，用于稳定哈希。"""

    normalized_units: list[str] = []
    for raw_unit in code_units:
        text = raw_unit.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()

        compacted: list[str] = []
        previous_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and previous_blank:
                continue
            compacted.append(line)
            previous_blank = is_blank
        if compacted:
            normalized_units.append("\n".join(compacted))

    return "\n\n".join(normalized_units)


def extract_code_units(document_xml: bytes, source_label: str) -> list[str]:
    """从 ``matlab/document.xml`` 提取 WordprocessingML code 段落。"""

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise ContractError(
            f"[INVALID_DOCUMENT_XML] {source_label}: {exc}"
        ) from exc

    code_units: list[str] = []
    for paragraph in root.iter(f"{{{WORD_NS}}}p"):
        style_value: str | None = None
        for descendant in paragraph.iter():
            if local_name(descendant.tag) == "pStyle":
                style_value = attribute_by_local_name(descendant, "val")
                break
        if style_value != CODE_STYLE:
            continue

        text_fragments = [
            node.text or ""
            for node in paragraph.iter()
            if local_name(node.tag) == "t"
        ]
        unit = "".join(text_fragments)
        if unit.strip():
            code_units.append(unit)

    return code_units


def extract_output_status(output_xml: bytes | None, source_label: str) -> tuple[str, ...]:
    """读取 MLX 内嵌的 ``outputStatus``；无输出 XML 时返回空元组。"""

    if output_xml is None:
        return ()
    try:
        root = ET.fromstring(output_xml)
    except ET.ParseError as exc:
        raise ContractError(
            f"[INVALID_OUTPUT_XML] {source_label}: {exc}"
        ) from exc

    statuses: list[str] = []
    for element in root.iter():
        if local_name(element.tag) != "outputStatus":
            continue
        value = (element.text or attribute_by_local_name(element, "value") or "").strip()
        if value and value not in statuses:
            statuses.append(value)
    return tuple(statuses)


def strip_matlab_comment(line: str) -> str:
    """移除字符串外的 MATLAB ``%`` 注释。

    MATLAB 中单引号同时可作转置符。这里只用于候选变量统计，
    因此采用保守解析：成对引号视为字符串，其余内容保留。
    """

    in_single = False
    in_double = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == "'" and not in_double:
            if in_single and index + 1 < len(line) and line[index + 1] == "'":
                index += 2
                continue
            in_single = not in_single
        elif char == '"' and not in_single:
            if in_double and index + 1 < len(line) and line[index + 1] == '"':
                index += 2
                continue
            in_double = not in_double
        elif char == "%" and not in_single and not in_double:
            return line[:index]
        index += 1
    return line


def identifiers(text: str) -> set[str]:
    """提取非关键字、非常用内建函数的 MATLAB 标识符候选。"""

    without_properties = re.sub(r"\.[A-Za-z]\w*", "", text)
    result: set[str] = set()
    for match in IDENTIFIER_RE.finditer(without_properties):
        name = match.group(1)
        lowered = name.lower()
        if lowered in MATLAB_KEYWORDS or lowered in COMMON_MATLAB_FUNCTIONS:
            continue
        result.add(name)
    return result


def analyze_variable_candidates(code: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """返回读、写和外部读变量的保守静态候选。"""

    reads: set[str] = set()
    writes: set[str] = set()

    for raw_line in code.splitlines():
        line = strip_matlab_comment(raw_line).strip()
        if not line:
            continue

        syms_match = re.match(r"^syms\s+(.+)$", line, re.IGNORECASE)
        if syms_match:
            writes.update(identifiers(syms_match.group(1)))
            continue

        for_match = re.match(
            r"^(?:par)?for\s+([A-Za-z]\w*)\s*=\s*(.+)$", line, re.IGNORECASE
        )
        if for_match:
            writes.add(for_match.group(1))
            reads.update(identifiers(for_match.group(2)))
            continue

        assignment = ASSIGNMENT_RE.search(line)
        if assignment is None:
            reads.update(identifiers(line))
            continue

        lhs = line[: assignment.start()].strip()
        rhs = line[assignment.end() :]
        if lhs.startswith("["):
            writes.update(identifiers(lhs))
        else:
            target = re.match(r"^([A-Za-z]\w*)", lhs)
            if target:
                writes.add(target.group(1))
            # 索引变量仍是读依赖，但左值目标本身不重复计入。
            if target:
                lhs_without_target = lhs[target.end() :]
                reads.update(identifiers(lhs_without_target))
        reads.update(identifiers(rhs))

    external_reads = reads - writes
    return (
        tuple(sorted(reads, key=str.casefold)),
        tuple(sorted(writes, key=str.casefold)),
        tuple(sorted(external_reads, key=str.casefold)),
    )


def infer_source_role(relative_path: str) -> str:
    """仅根据冻结文件名生成可复核的源角色标签。"""

    name = Path(relative_path).stem.lower()
    if re.search(r"(?:^|_)lqr2(?:_|$)", name):
        division = "第一类子结构划分"
    elif re.search(r"(?:^|_)lqr3(?:_|$)", name):
        division = "第二类子结构划分"
    else:
        division = "划分身份未由文件名确定"

    if re.search(r"(?:^|_)cb(?:_|$)", name):
        method = "Craig-Bampton"
    elif "guyan" in name:
        method = "Guyan"
    elif re.search(r"(?:^|_)ori(?:_|$)", name) or "origin" in name:
        method = "原结构"
    else:
        method = "方法身份未由文件名确定"
    return f"{division} / {method} / 冻结MLX候选源"


def unique_dicts(items: Iterable[dict[str, str]]) -> tuple[dict[str, str], ...]:
    """按键值对去重且保留首次出现顺序。"""

    result: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for item in items:
        marker = tuple(sorted(item.items()))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return tuple(result)


def parse_mlx(source_path: Path, input_dir: Path) -> ParsedMlx:
    """解析一个且仅一个冻结 MLX。"""

    try:
        relative = source_path.resolve().relative_to(input_dir.resolve())
    except ValueError as exc:
        raise ContractError(
            f"[INPUT_BOUNDARY_VIOLATION] {source_path} is outside {input_dir}"
        ) from exc

    relative_label = relative.as_posix()
    raw = source_path.read_bytes()
    try:
        with zipfile.ZipFile(source_path, "r") as archive:
            members = set(archive.namelist())
            document_member = "matlab/document.xml"
            if document_member not in members:
                raise ContractError(
                    f"[MISSING_DOCUMENT_XML] {relative_label}: "
                    f"{document_member} is absent"
                )
            document_xml = archive.read(document_member)
            output_xml = (
                archive.read("matlab/output.xml")
                if "matlab/output.xml" in members
                else None
            )
    except zipfile.BadZipFile as exc:
        raise ContractError(f"[INVALID_MLX_ZIP] {relative_label}: {exc}") from exc

    code_units = extract_code_units(document_xml, relative_label)
    normalized_code = normalize_code_units(code_units)
    executable_code = "\n".join(
        strip_matlab_comment(line) for line in normalized_code.splitlines()
    )
    read_vars, write_vars, external_reads = analyze_variable_candidates(normalized_code)
    qr_literals: dict[str, list[str]] = {"Q": [], "R": []}
    for match in QR_LITERAL_RE.finditer(executable_code):
        value = " ".join(match.group("value").split())
        if value not in qr_literals[match.group("name")]:
            qr_literals[match.group("name")].append(value)

    loop_ranges = unique_dicts(
        {
            "variable": match.group("variable"),
            "range": match.group("range").strip().rstrip(";"),
        }
        for match in FOR_RANGE_RE.finditer(executable_code)
    )
    h_initializations = unique_dicts(
        {
            "constructor": match.group("constructor"),
            "dimensions": " ".join(match.group("dimensions").split()),
        }
        for match in H_INIT_RE.finditer(executable_code)
    )
    h_nonzero_positions = unique_dicts(
        {
            "position": " ".join(match.group("position").split()),
            "value": " ".join(match.group("value").split()),
        }
        for match in H_ASSIGN_RE.finditer(executable_code)
        if not re.fullmatch(
            r"(?:0+(?:\.0*)?|sym\s*\(\s*0\s*\))",
            match.group("value").strip(),
            re.IGNORECASE,
        )
    )

    save_targets: list[str] = []
    for regex in (SAVE_CALL_RE, SAVE_COMMAND_RE):
        for match in regex.finditer(executable_code):
            target = match.group("target").strip()
            if target and target not in save_targets:
                save_targets.append(target)

    output_relative = relative.with_suffix(".m").as_posix()
    lines = normalized_code.splitlines()
    return ParsedMlx(
        source_path=source_path,
        frozen_relative_path=relative_label,
        output_relative_path=output_relative,
        source_sha256=sha256_bytes(raw),
        normalized_code=normalized_code,
        normalized_code_sha256=sha256_bytes(normalized_code.encode("utf-8")),
        code_line_count=len(lines),
        nonblank_code_line_count=sum(bool(line.strip()) for line in lines),
        read_variables_candidate=read_vars,
        write_variables_candidate=write_vars,
        external_read_variables_candidate=external_reads,
        lqr_call_count=len(LQR_CALL_RE.findall(executable_code)),
        dlqr_call_count=len(DLQR_CALL_RE.findall(executable_code)),
        q_literals=tuple(qr_literals["Q"]),
        r_literals=tuple(qr_literals["R"]),
        loop_ranges=loop_ranges,
        h_initializations=h_initializations,
        h_nonzero_positions=h_nonzero_positions,
        save_targets=tuple(save_targets),
        embedded_output_status=extract_output_status(output_xml, relative_label),
        source_role=infer_source_role(relative_label),
    )


def record_to_json(record: ParsedMlx) -> dict[str, Any]:
    """将内部数据类型转换为 JSON 友好结构。"""

    return {
        "source_role": record.source_role,
        "frozen_relative_path": record.frozen_relative_path,
        "extracted_code_relative_path": record.output_relative_path,
        "source_sha256": record.source_sha256,
        "normalized_code_sha256": record.normalized_code_sha256,
        "code_line_count": record.code_line_count,
        "nonblank_code_line_count": record.nonblank_code_line_count,
        "read_variables_candidate": list(record.read_variables_candidate),
        "write_variables_candidate": list(record.write_variables_candidate),
        "external_read_variables_candidate": list(
            record.external_read_variables_candidate
        ),
        "has_lqr_call": record.lqr_call_count > 0,
        "has_dlqr_call": record.dlqr_call_count > 0,
        "lqr_call_count": record.lqr_call_count,
        "dlqr_call_count": record.dlqr_call_count,
        "q_literals": list(record.q_literals),
        "r_literals": list(record.r_literals),
        "loop_ranges": list(record.loop_ranges),
        "h_initializations": list(record.h_initializations),
        "h_nonzero_positions": list(record.h_nonzero_positions),
        "save_targets": list(record.save_targets),
        "embedded_output_status": list(record.embedded_output_status),
    }


def json_compact(value: Any) -> str:
    """用于 CSV 单元格的稳定紧凑 JSON。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_outputs(records: Sequence[ParsedMlx], board_root: Path) -> None:
    """在全部解析通过后一次性写出代码与合同。"""

    outputs_dir = board_root / "outputs"
    code_dir = outputs_dir / "mlx_code"
    code_dir.mkdir(parents=True, exist_ok=True)

    for record in records:
        destination = code_dir / Path(record.output_relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            record.normalized_code + ("\n" if record.normalized_code else ""),
            encoding="utf-8",
        )

    json_path = outputs_dir / "mlx_contract.json"
    csv_path = outputs_dir / "mlx_contract.csv"
    payload = {
        "schema_version": "board20-mlx-contract-v1",
        "input_boundary": "input/**/*.mlx only",
        "record_count": len(records),
        "records": [record_to_json(record) for record in records],
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fieldnames = [
        "source_role",
        "frozen_relative_path",
        "extracted_code_relative_path",
        "source_sha256",
        "normalized_code_sha256",
        "code_line_count",
        "nonblank_code_line_count",
        "read_variables_candidate",
        "write_variables_candidate",
        "external_read_variables_candidate",
        "has_lqr_call",
        "has_dlqr_call",
        "lqr_call_count",
        "dlqr_call_count",
        "q_literals",
        "r_literals",
        "loop_ranges",
        "h_initializations",
        "h_nonzero_positions",
        "save_targets",
        "embedded_output_status",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            item = record_to_json(record)
            writer.writerow(
                {
                    key: json_compact(item[key])
                    if isinstance(item[key], (list, dict))
                    else item[key]
                    for key in fieldnames
                }
            )

    print(f"MLX_CONTRACT_OK records={len(records)}")
    print(f"CSV={csv_path}")
    print(f"JSON={json_path}")
    print(f"CODE_DIR={code_dir}")


def resolve_paths(script_path: Path) -> tuple[Path, Path]:
    """从脚本位置解析板块根目录与冻结输入目录。"""

    board_root = script_path.resolve().parent.parent
    input_dir = board_root / "input"
    return board_root, input_dir


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Audit frozen Board 20 MLX files and emit code/CSV/JSON contracts."
    )
    parser.add_argument(
        "--check-input-only",
        action="store_true",
        help="validate and parse frozen MLX files without writing outputs",
    )
    args = parser.parse_args()

    board_root, input_dir = resolve_paths(Path(__file__))
    if not input_dir.is_dir():
        raise ContractError(
            f"[MISSING_INPUT] Frozen input directory does not exist: {input_dir}"
        )

    mlx_files = sorted(
        (path for path in input_dir.rglob("*.mlx") if path.is_file()),
        key=lambda path: path.relative_to(input_dir).as_posix().casefold(),
    )
    if not mlx_files:
        raise ContractError(
            f"[MISSING_FROZEN_MLX] No frozen .mlx files found under: {input_dir}"
        )

    records = [parse_mlx(path, input_dir) for path in mlx_files]
    if args.check_input_only:
        print(f"MLX_INPUT_CHECK_OK records={len(records)}")
        return 0

    write_outputs(records, board_root)
    return 0


def main() -> int:
    try:
        return run()
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"[IO_ERROR] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
