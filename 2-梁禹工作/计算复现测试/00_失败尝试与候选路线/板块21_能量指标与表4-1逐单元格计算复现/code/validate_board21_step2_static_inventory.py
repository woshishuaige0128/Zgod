from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import PyPDF2
from scipy.io import loadmat, whosmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parents[1]
PROJECT_ROOT = SCRIPT.parents[4]
AUTHOR_ROOT = BOARD_ROOT / "input" / "author_energy"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INVENTORY_ROOT = BOARD_ROOT / "outputs" / "step2_static_inventory"
TABLE_ROOT = INVENTORY_ROOT / "tables"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step2_validation"
REPORT = BOARD_ROOT / "report" / "板块21_最小步骤2_公式与历史脚本静态审计.md"
REPORT_SHA256 = "7E642186B735E73B13547D10073AEE4B66146A7157860C1157F120165406B2DF"
VALIDATION_ALLOWED_FILES = {
    "checks.csv",
    "step2_artifact_manifest.csv",
    "validation_output_manifest.csv",
    "validation_summary.json",
}
EXPECTED_CODE_REPORT_PATHS = {
    "code/build_board21_step2_static_inventory.py",
    "code/freeze_board21_inputs.py",
    "code/run_board21_step2_determinism.py",
    "code/test_board21_relative_handle_race.py",
    "code/validate_board21_step1.py",
    "code/validate_board21_step2_static_inventory.py",
    "report/板块21_最小步骤1_输入冻结验收.md",
    "report/板块21_最小步骤2_公式与历史脚本静态审计.md",
}

INPUT_MANIFEST_SHA256 = (
    "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
)
INPUT_FREEZE_SUMMARY_SHA256 = (
    "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
)
THESIS = BOARD_ROOT / "input" / "theory" / "梁禹手稿.pdf"
THESIS_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
UPSTREAM_PD = (
    BOARD_ROOT
    / "input"
    / "upstream_candidate"
    / "board17_local_pd_reductions.mat"
)
UPSTREAM_PD_SHA256 = (
    "763C0BB0158F942E392246776D0B5D3926A71AFF69DB50473EFA41DE0263A36F"
)
STEP1_FIXED_HASHES = {
    BOARD_ROOT / "outputs" / "step1_validation" / "checks.csv":
        "BD7B7411401C4AFECF417CEEA4F281304A47D690E9B78FB99FCBE24D518E170B",
    BOARD_ROOT / "outputs" / "step1_validation" / "validation_summary.json":
        "B75CE38E2529AB0873720922057D35DC1B6EE4346D17BC44F5CB10E134AB7C60",
    BOARD_ROOT / "outputs" / "step1_validation" / "relative_handle_race_test.json":
        "F887F904480AAD9FF2AAF7CF3EC9EA0A7D392FA64F10AB377D0884AEFEB9D354",
    BOARD_ROOT / "outputs" / "step1_artifact_manifest.csv":
        "0BF3542E8ACFF7446EE2B069680C6B4A84A9A113C2CE2E76E7EF6CD110F00F5E",
}

ENERGY_EXPECTED = {
    "energy_zonghe.mlx": {
        "sha256": "BCEDEF1887ABEE046A3018EB746B2088B0D63F9ACC917B9B4A78D97DEC84159D",
        "dims": ("15×1", "3×1", "6×1"),
        "saved": ("6.5613", "6.5535"),
        "producer": "PDmonicanshu.m",
        "family": "15->3/6",
        "coordinate": "PASS",
        "energy_normalized": True,
        "candidate_status": "STATIC_CANDIDATE_REFERENCE",
    },
    "energy_zonghe2.mlx": {
        "sha256": "A84F903A5163AC0792FEA6BD0222003B3D2E1ED12B4D1B2CD6EABF325CA5CAAD",
        "dims": ("6×1", "2×1", "5×1"),
        "saved": ("9.7221", "9.3097"),
        "producer": "monicanshu_2_suoju.mlx",
        "family": "6->2/5",
        "coordinate": "PASS",
        "energy_normalized": True,
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_of_energy_zonghe2.mlx": {
        "sha256": "80C4B3FE2A860552054D8FCEABA40365C5EE646BBB2EB21C9AF68E81AFE4715D",
        "dims": ("6×1", "2×1", "5×1"),
        "saved": ("9.6488", "9.3150"),
        "producer": "PDmonicanshu2.m",
        "family": "6->2/5",
        "coordinate": "PASS",
        "energy_normalized": True,
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_2_of_energy_zonghe2.mlx": {
        "sha256": "8EBC3ACBD47B1D112395D4DCD951FE018F71A857E604187B443A2BFD572ADA66",
        "dims": ("6×1", "2×1", "5×1"),
        "saved": ("-33.7706", "-41.7441"),
        "producer": "monicanshu_2_suoju.mlx",
        "family": "6->2/5",
        "coordinate": "PASS",
        "energy_normalized": False,
        "candidate_status": "STATIC_CANDIDATE_FORMULA_INVALID",
    },
    "energy_zonghe3.mlx": {
        "sha256": "1F3B84A542AF40563F05C23402C2355345100D38A94D8EF130D5545A33D36614",
        "dims": ("9×1", "2×1", "5×1"),
        "saved": ("59.8619", "16.9607"),
        "producer": "monicanshu_3_suoju.mlx",
        "family": "9->2/5",
        "coordinate": "FAIL",
        "energy_normalized": True,
        "candidate_status": "STATIC_CANDIDATE_COORDINATE_SEMANTICS_FAIL",
    },
    "Copy_of_energy_zonghe3.mlx": {
        "sha256": "C067893CE26DA706774A886523F9000A2A0779268BB12A93A21E0EF0034296AC",
        "dims": ("9×1", "2×1", "5×1"),
        "saved": ("59.8619", "15.5000"),
        "producer": "PDmonicanshu3.m",
        "family": "9->2/5",
        "coordinate": "PASS",
        "energy_normalized": True,
        "candidate_status": "STATIC_CANDIDATE",
    },
    "Copy_2_of_energy_zonghe3.mlx": {
        "sha256": "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D",
        "dims": ("9×1", "2×1", "5×1"),
        "saved": ("39.2658", "20.2060"),
        "producer": "monicanshu_3_suoju.mlx",
        "family": "9->2/5",
        "coordinate": "FAIL",
        "energy_normalized": False,
        "candidate_status": "STATIC_CANDIDATE_COORDINATE_AND_FORMULA_FAIL",
    },
}

EXPECTED_MLX_OUTPUT_COUNTS = {
    "Copy_2_of_energy_zonghe2.mlx": 22,
    "Copy_2_of_energy_zonghe3.mlx": 16,
    "Copy_of_energy_zonghe2.mlx": 15,
    "Copy_of_energy_zonghe3.mlx": 16,
    "energy_zonghe.mlx": 13,
    "energy_zonghe2.mlx": 16,
    "energy_zonghe3.mlx": 17,
    "luxvjie_cb_2.mlx": 404,
    "luxvjie_cb_3.mlx": 404,
    "luxvjie_cb_LQR2.mlx": 8,
    "luxvjie_cb_LQR3.mlx": 7,
    "luxvjie_guyan_2.mlx": 352,
    "luxvjie_guyan_LQR2.mlx": 17,
    "luxvjie_guyan_LQR3.mlx": 10,
    "luxvjie_ori_LQR2.mlx": 1,
    "luxvjie_ori_LQR3.mlx": 2,
    "monicanshu_2.mlx": 1,
    "monicanshu_2_suoju.mlx": 1,
    "monicanshu_3.mlx": 1,
    "monicanshu_3_suoju.mlx": 1,
    "simulink_str_2.mlx": 0,
    "simulink_str_3.mlx": 0,
    "untitled.mlx": 1,
    "untitled2.mlx": 4,
    "untitled3.mlx": 2,
    "untitled4.mlx": 2,
}
EXPECTED_MLX_ERROR_NAMES = {
    "luxvjie_cb_2.mlx",
    "luxvjie_cb_3.mlx",
    "luxvjie_cb_LQR2.mlx",
    "untitled2.mlx",
}

EXPECTED_TARGETS = {
    ("第一类划分", "Guyan"): ("0.3065", "NO_SAVED_OUTPUT_MATCH", ""),
    ("第一类划分", "Craig-Bampton"): ("0.1879", "NO_SAVED_OUTPUT_MATCH", ""),
    ("第二类划分", "Guyan"): (
        "0.3927",
        "NUMERIC_MATCH_FORMULA_INVALID",
        "Copy_2_of_energy_zonghe3.mlx",
    ),
    ("第二类划分", "Craig-Bampton"): (
        "0.2021",
        "NUMERIC_MATCH_FORMULA_INVALID",
        "Copy_2_of_energy_zonghe3.mlx",
    ),
}

EXPECTED_HISTORICAL_TARGET_ROWS = [
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

EXPECTED_HISTORICAL_MATCH_ROWS = [
    {
        "division": "第一类划分",
        "method": "Guyan",
        "paper_value": "0.3065",
        "unit_printed": "none",
        "evidence_level": "历史值",
        "matching_rule": "saved_percent/100 rounded to 4 decimals",
        "matched_routes": "",
        "matched_saved_percent": "",
        "matched_div100": "",
        "match_status": "NO_SAVED_OUTPUT_MATCH",
        "formula_compliant_match": "False",
    },
    {
        "division": "第一类划分",
        "method": "Craig-Bampton",
        "paper_value": "0.1879",
        "unit_printed": "none",
        "evidence_level": "历史值",
        "matching_rule": "saved_percent/100 rounded to 4 decimals",
        "matched_routes": "",
        "matched_saved_percent": "",
        "matched_div100": "",
        "match_status": "NO_SAVED_OUTPUT_MATCH",
        "formula_compliant_match": "False",
    },
    {
        "division": "第二类划分",
        "method": "Guyan",
        "paper_value": "0.3927",
        "unit_printed": "none",
        "evidence_level": "历史值",
        "matching_rule": "saved_percent/100 rounded to 4 decimals",
        "matched_routes": "Copy_2_of_energy_zonghe3.mlx",
        "matched_saved_percent": "39.2658",
        "matched_div100": "0.392658",
        "match_status": "NUMERIC_MATCH_FORMULA_INVALID",
        "formula_compliant_match": "False",
    },
    {
        "division": "第二类划分",
        "method": "Craig-Bampton",
        "paper_value": "0.2021",
        "unit_printed": "none",
        "evidence_level": "历史值",
        "matching_rule": "saved_percent/100 rounded to 4 decimals",
        "matched_routes": "Copy_2_of_energy_zonghe3.mlx",
        "matched_saved_percent": "20.2060",
        "matched_div100": "0.202060",
        "match_status": "NUMERIC_MATCH_FORMULA_INVALID",
        "formula_compliant_match": "False",
    },
]

EXPECTED_PAPER_FORMULA_ROWS = [
    {
        "equation": "4-41",
        "pdf_page": "72",
        "printed_page": "62",
        "literal_formula": "Gamma_i=(phi_i^T M r)/(phi_i^T M phi_i)",
        "required_inputs": "phi_i|M|r",
        "hard_invariant": "denominator_nonzero",
        "open_issue": "modal normalization convention is not stated",
        "evidence_level": "论文原文公式",
    },
    {
        "equation": "4-42",
        "pdf_page": "72",
        "printed_page": "62",
        "literal_formula": "p_i=Gamma_i^2/sum_{k=1}^m Gamma_k^2",
        "required_inputs": "Gamma|m|modal_order",
        "hard_invariant": "sum_i(p_i)=1",
        "open_issue": "m and modal ordering are not stated for Table 4-1",
        "evidence_level": "论文原文公式",
    },
    {
        "equation": "4-43",
        "pdf_page": "72",
        "printed_page": "62",
        "literal_formula": (
            "E_{j,i}=m_j phi_{j,i}^2/sum_{l=1}^n(m_l phi_{l,i}^2)"
        ),
        "required_inputs": "scalar_m_j|phi|n",
        "hard_invariant": "for each i: sum_j(E_{j,i})=1",
        "open_issue": (
            "off-diagonal mass and translational/rotational mass convention "
            "are not stated"
        ),
        "evidence_level": "论文原文公式",
    },
    {
        "equation": "4-44",
        "pdf_page": "72",
        "printed_page": "62",
        "literal_formula": "E_j^total=sum_{i=1}^m p_i E_{j,i}",
        "required_inputs": "p_i|E_{j,i}|m",
        "hard_invariant": "sum_j(E_j^total)=1",
        "open_issue": (
            "Craig-Bampton physical-coordinate recovery is not stated"
        ),
        "evidence_level": "论文原文公式",
    },
    {
        "equation": "4-45",
        "pdf_page": "72",
        "printed_page": "62",
        "literal_formula": (
            "Delta E_k=sum_{k=1}^q[(E_guyan^total(k)-E^total(d_k))/"
            "E^total(d_k)]"
        ),
        "required_inputs": "D={d_1,...,d_q}|E_guyan^total|E^total",
        "hard_invariant": (
            "all reference denominators nonzero; preserve signed sum"
        ),
        "open_issue": (
            "left index conflicts with summed k; D mapping is underdefined; "
            "only Guyan symbol is printed"
        ),
        "evidence_level": "论文原文公式",
    },
]

EXPECTED_REVIEWED_OUTPUT_SHA256 = {
    "inventory_summary.json": (
        "C587F4FA80E56512C7734D545A20BE483EADC5E09B5707A6D241ACBADE2A7D1C"
    ),
    "tables/all_author_files.csv": (
        "EECE0777E9DE3B583C54F7D7405DEDDCBE85D4E60B5BFED119ED90A4CAD69A74"
    ),
    "tables/dependency_edges.csv": (
        "DADE0A4F61408F784D3F3FC300D564F775CCF46D868AE13F5728933375CBE1D6"
    ),
    "tables/dependency_file_roles.csv": (
        "A215D27B3DEDB0961C4554C3EC7D55E6B207AC28F577AF87F6CC3757CC0BEDC9"
    ),
    "tables/energy_routes.csv": (
        "E8452A71CED4553372EAA437C9EF81B1C7C01D5B07C20B2E3F64ADA07B914D1C"
    ),
    "tables/formula_route_audit.csv": (
        "EF689598EF0507A118FD83D8301C192760D964F43F7939C38802861B94A15FB7"
    ),
    "tables/historical_table4_1_targets.csv": (
        "1F879E1D1011108D66CCE76B41080DA167A70A5AD6952007953C61D036A09529"
    ),
    "tables/historical_target_matches.csv": (
        "2ACD1CA4FB6910A595955874DE5571E3CF141E7C08141F1F0C5087F9904FB0C3"
    ),
    "tables/mat_variables.csv": (
        "4709BCFC875BB8189BEB05AD75B01F8812164FC65C89CD4DF2F8E8346880E800"
    ),
    "tables/mlx_cells.csv": (
        "15CFABB2EBFC88C685F7D684876427CC760598336B51A9C1DB89E6220B616191"
    ),
    "tables/mlx_metadata.csv": (
        "1FDDBA5685FACF66820E0BF4A89B8C1F4994432FD9CEF69C86F287F7F57BFA4D"
    ),
    "tables/mlx_outputs.csv": (
        "0493E8FB04354A7690CAEACD24CD170F4250F9BED24B524F0EC9101EAF6CDA52"
    ),
    "tables/paper_formula_contract.csv": (
        "ABED7F085400A4CCB802B8D8B08C1BC0C534361AD1C4BFD1DA77818BD300BA0E"
    ),
    "tables/slx_blocks.csv": (
        "F74F75E89AE247CD13DD393E2356594B1B9CEE3AC63F0E303D7B9E5E541C11D5"
    ),
    "tables/slx_models.csv": (
        "C963A785E15771E2BF3C5B6BEA1D90CBA2B6161BD641C0B1DFB377893E755BF5"
    ),
    "tables/slx_parameters.csv": (
        "AE215E1E6B6B603D41313AB3FB8D967A331B07D24B5211E4AF0585F62FD8548F"
    ),
    "tables/static_issue_register.csv": (
        "DC6E9A3845660306AA05FDF22412A2495C53BBFB533D6DE5B0B387524D7D057E"
    ),
    "tables/text_scripts.csv": (
        "EA0B781D25304223139C791F3AF3A97FA49C96E7D2F23479D6CE2D469F0EE662"
    ),
}

EXPECTED_REVIEWED_MLX_RECORD_SHA256 = {
    "Copy_2_of_energy_zonghe2__record.json": "606ECBFCB6D53467B8CAB6198BB34CFA5CDCDE5EA9472AA32158D7EAA19ED703",
    "Copy_2_of_energy_zonghe3__record.json": "010217DBEF67168C5A23EEA24B818D2291C59A0141AB305F86CB6968D957F40D",
    "Copy_of_energy_zonghe2__record.json": "E743CA86B419655EAF96C6B010F14A332B722E3D6B1305AC9AED4054F80A6809",
    "Copy_of_energy_zonghe3__record.json": "8432867247E57303C43F42504F3E65401B566113E520C1AACF491EC0242DE26D",
    "energy_zonghe__record.json": "55E895D34DB3C4102CF1B200FA90F655321DCCB5BF34FBB83764561786282514",
    "energy_zonghe2__record.json": "3AD67DDBC849E491E66A2161C8F8400BDE59DEFA9845BB2C561BC9B54118FECC",
    "energy_zonghe3__record.json": "A7452C33FDC03DFB7622BDB84DDDAD18BBF986F6F3D17F080E52CA4335A9F108",
    "luxvjie_cb_2__record.json": "01CBB997E7E2F78B9749E0B7753D370E67BD4A99BDE178EA5E3208E22D89410C",
    "luxvjie_cb_3__record.json": "D1603D0395013EB18B8C4E9892FFBFA6497A53919E05470CCB8E4B182E3CEC26",
    "luxvjie_cb_LQR2__record.json": "294309C36C288D3CEB378E7F41C94849B502CE01AB5AB7E33F57A65EAFA73145",
    "luxvjie_cb_LQR3__record.json": "722226541A0F70125325A26473EFB68DEFD70DF97053738AE45AD60CB092FB6C",
    "luxvjie_guyan_2__record.json": "E4520A0A07DF06E4ADEBDAA30554160F70F89C714070A1A85BBF7877DED64CE6",
    "luxvjie_guyan_LQR2__record.json": "FFF098AC17C76EAAA497A0CA2F672E90B090CA36BD3F4B1C641F49EDBC4410D7",
    "luxvjie_guyan_LQR3__record.json": "51E48CFAB9A77E8FC01494C88A24F855730E3393F5EB5C0087A7E9AC5047094F",
    "luxvjie_ori_LQR2__record.json": "858720E90D1B72A001B722446350463ABC061E8F7A68975C57DC383295671D7E",
    "luxvjie_ori_LQR3__record.json": "7D08CF8C651B786C8A2A461DA1D1D6ACBC1FDA5BCDEAD2B185D6ECA47A216E76",
    "monicanshu_2__record.json": "A71438A7A4A4CC4E85B39BBF26FE635794435204D91DF7A0279F0A96E8DB33E4",
    "monicanshu_2_suoju__record.json": "3285B6ECFD25A4BAA9BB03CAB297EDD1465E7B7D1D368F71CDF321DF3C381F06",
    "monicanshu_3__record.json": "7892E55DDA0049E817CE86B916415727C5BB04166DC1A5BCBFAE57371E5D9A69",
    "monicanshu_3_suoju__record.json": "331BC10FD74F1BE07B51EAE34AF87F6E3DB9702118B45F3EAC36268CD417C78E",
    "simulink_str_2__record.json": "6BF313B4B69B32037532B00B65E094372B1A0621B32E6FD4DB45E68F5E8E48C5",
    "simulink_str_3__record.json": "F308D2AF6892B83E8ABA7F57C5F6345F6CE8DAE1989C2214ABAEC91C0199F61B",
    "untitled__record.json": "CE61EBD15D5BDB5BA0D2391A9148BC77CAEC8D99E67761DA846B92E986BA6624",
    "untitled2__record.json": "C735443E0C757A3F0A4BFF8C6C6876FC66B85DD1D9736DB72736C4423CB2167A",
    "untitled3__record.json": "849E25ED2D08979F46537A2E717801AA4E87C2407EEADA0B954580A174284057",
    "untitled4__record.json": "1B6D515155A9D3EF5306C685DA00C33368C88358272D31C537616B26CADE4FED",
}

FORMAL_OBJECT_NAMES = (
    "表4-1_两类划分Guyan与Craig--Bampton能量变化率",
    "结论C06_能量变化率稳定风险阈值",
)
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_STYLE = f"{{{WORD_NS}}}val"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {
            str(key): jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted((jsonable(item) for item in value), key=str)
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def render(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(
        jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def add_check(
    checks: list[dict[str, str]],
    check_id: str,
    category: str,
    passed: bool,
    expected: Any,
    actual: Any,
    evidence: Any,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "expected": render(expected),
            "actual": render(actual),
            "evidence": render(evidence),
        }
    )


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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    atomic_write_bytes(path, stream.getvalue().encode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_bytes(path, payload.encode("utf-8"))


def write_validation_manifest_and_verify(
    ordered_targets: tuple[Path, ...], manifest_path: Path
) -> tuple[bool, dict[str, Any]]:
    rows = [
        {
            "relative_path": path.relative_to(BOARD_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in ordered_targets
    ]
    write_csv(
        manifest_path,
        rows,
        ["relative_path", "size_bytes", "sha256"],
    )
    reread_rows = read_csv(manifest_path)
    expected_relative_paths = [
        path.relative_to(BOARD_ROOT).as_posix() for path in ordered_targets
    ]
    row_paths_exact = [
        row.get("relative_path", "") for row in reread_rows
    ] == expected_relative_paths
    row_files_exact = len(reread_rows) == len(ordered_targets)
    if row_files_exact:
        for row, target, expected_relative in zip(
            reread_rows, ordered_targets, expected_relative_paths
        ):
            row_files_exact &= (
                row.get("relative_path") == expected_relative
                and target.is_file()
                and row.get("size_bytes") == str(target.stat().st_size)
                and row.get("sha256") == sha256_file(target)
            )
    final_entries = sorted(
        path.relative_to(VALIDATION_ROOT).as_posix()
        for path in VALIDATION_ROOT.rglob("*")
    )
    root_exact = (
        final_entries == sorted(VALIDATION_ALLOWED_FILES)
        and all(
            (VALIDATION_ROOT / name).is_file()
            for name in VALIDATION_ALLOWED_FILES
        )
    )
    details = {
        "root_exact": root_exact,
        "actual_entries": final_entries,
        "expected_entries": sorted(VALIDATION_ALLOWED_FILES),
        "row_paths_exact": row_paths_exact,
        "row_files_exact": bool(row_files_exact),
        "manifest_row_count": len(reread_rows),
    }
    return root_exact and row_paths_exact and bool(row_files_exact), details


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def decode_text(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Cannot decode {path}")


def remove_matlab_comments(code: str) -> str:
    retained = []
    for line in code.splitlines():
        in_string = False
        output = []
        index = 0
        while index < len(line):
            character = line[index]
            if character == "'":
                if in_string:
                    if index + 1 < len(line) and line[index + 1] == "'":
                        output.extend(("'", "'"))
                        index += 2
                        continue
                    in_string = False
                else:
                    prefix = "".join(output).rstrip()
                    previous = prefix[-1] if prefix else ""
                    if not prefix or previous in "([{,=:+-*/\\^~;":
                        in_string = True
            if character == "%" and not in_string:
                break
            output.append(character)
            index += 1
        content = "".join(output)
        if content.strip():
            retained.append(content)
    return "\n".join(retained)


def output_record(element: ET.Element, index: int) -> dict[str, Any]:
    raw = ET.tostring(element, encoding="utf-8")
    output_data = element.find("./outputData")
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
        "output_type": element.findtext("./type", default=""),
        "line_numbers": [
            node.text or "" for node in element.findall("./lineNumbers/element")
        ],
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


def inspect_mlx(path: Path) -> dict[str, Any]:
    source_payload = path.read_bytes()
    source_sha256 = sha256_bytes(source_payload)
    with zipfile.ZipFile(io.BytesIO(source_payload)) as archive:
        names = sorted(archive.namelist(), key=str.casefold)
        if names.count("matlab/document.xml") != 1:
            raise RuntimeError(f"MLX document.xml cardinality mismatch: {path}")
        if names.count("matlab/output.xml") != 1:
            raise RuntimeError(f"MLX output.xml cardinality mismatch: {path}")
        document_payload = archive.read("matlab/document.xml")
        output_payload = (
            archive.read("matlab/output.xml")
            if "matlab/output.xml" in names
            else b""
        )
    document_root = ET.fromstring(document_payload)
    namespace = {"w": WORD_NS}
    paragraphs = []
    code_cells = []
    text_cells = []
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
                "text_sha256": sha256_bytes(text.encode("utf-8")),
                "text": text,
            }
        )
    outputs = []
    evaluation_state = ""
    output_status = ""
    if output_payload:
        output_root = ET.fromstring(output_payload)
        evaluation_state = output_root.findtext(
            "./metaData/evaluationState", default=""
        )
        output_status = output_root.findtext("./metaData/outputStatus", default="")
        outputs = [
            output_record(element, index)
            for index, element in enumerate(
                output_root.findall(".//outputArray/element"), start=1
            )
        ]
    return {
        "source_name": path.name,
        "source_sha256": source_sha256,
        "source_post_parse_sha256": sha256_file(path),
        "source_size_bytes": len(source_payload),
        "archive_entries": names,
        "document_xml_sha256": sha256_bytes(document_payload),
        "output_xml_sha256": sha256_bytes(output_payload) if output_payload else "",
        "evaluation_state": evaluation_state,
        "output_status": output_status,
        "paragraphs": paragraphs,
        "code_cells": code_cells,
        "text_cells": text_cells,
        "outputs": outputs,
    }


def extracted_code(record: dict[str, Any]) -> str:
    lines = [
        f"% Static extraction from {record['source_name']}",
        f"% Source SHA-256: {record['source_sha256']}",
        "% No MATLAB execution was performed.",
        "",
    ]
    for index, code in enumerate(record["code_cells"], start=1):
        lines.extend((f"%% CODE_CELL_C{index:03d}", code.rstrip(), ""))
    return "\n".join(lines).rstrip() + "\n"


def extracted_locations(code_cells: list[str]) -> dict[int, tuple[int, int, int]]:
    result = {}
    header_line = 5
    for index, code in enumerate(code_cells, start=1):
        count = max(1, len(code.splitlines()))
        result[index] = (header_line, header_line + 1, header_line + count)
        header_line += count + 2
    return result


def inventory_mat_direct(path: Path) -> list[dict[str, str]]:
    rows = []
    for name, shape, matlab_class in whosmat(path):
        value = loadmat(
            path, variable_names=[name], squeeze_me=False, struct_as_record=False
        ).get(name)
        data_hash = ""
        finite_count: int | str = ""
        minimum: Any = ""
        maximum: Any = ""
        if isinstance(value, np.ndarray) and value.dtype != object:
            contiguous = np.ascontiguousarray(value)
            data_hash = sha256_bytes(
                (
                    str(contiguous.dtype)
                    + "|"
                    + repr(contiguous.shape)
                    + "|"
                ).encode("ascii")
                + contiguous.tobytes(order="C")
            )
            if np.issubdtype(value.dtype, np.number):
                finite = np.isfinite(value)
                finite_count = int(np.count_nonzero(finite))
                if finite_count:
                    minimum = np.min(np.real(value[finite])).item()
                    maximum = np.max(np.real(value[finite])).item()
        rows.append(
            {
                "source_name": path.name,
                "source_sha256": sha256_file(path),
                "variable_name": name,
                "shape": "x".join(str(item) for item in shape),
                "matlab_class": matlab_class,
                "numpy_dtype": str(getattr(value, "dtype", "")),
                "data_sha256": data_hash,
                "finite_count": str(finite_count),
                "minimum_real": str(minimum),
                "maximum_real": str(maximum),
            }
        )
    return rows


def inventory_slx_direct(
    path: Path,
) -> tuple[list[tuple[str, str, str, str]], list[tuple[str, ...]], dict[str, Any]]:
    blocks: list[tuple[str, str, str, str]] = []
    parameters: list[tuple[str, ...]] = []
    xml_entry_count = 0
    parse_error_count = 0
    local_name_block_count = 0
    with zipfile.ZipFile(path) as archive:
        entries = sorted(archive.namelist(), key=str.casefold)
        for entry in entries:
            if not entry.lower().endswith(".xml"):
                continue
            xml_entry_count += 1
            try:
                root = ET.fromstring(archive.read(entry))
            except ET.ParseError:
                parse_error_count += 1
                continue
            local_name_block_count += sum(
                local_name(element.tag) == "Block" for element in root.iter()
            )
            for block in root.iter("Block"):
                base = (
                    entry,
                    block.attrib.get("SID", ""),
                    block.attrib.get("BlockType", ""),
                    block.attrib.get("Name", ""),
                )
                blocks.append(base)
                for parameter in block.findall("./P"):
                    parameters.append(
                        base
                        + (
                            parameter.attrib.get("Name", ""),
                            "".join(parameter.itertext()),
                        )
                    )
    summary = {
        "source_name": path.name,
        "source_sha256": sha256_file(path),
        "source_size_bytes": path.stat().st_size,
        "archive_entry_count": len(entries),
        "xml_entry_count": xml_entry_count,
        "block_count": len(blocks),
        "parameter_count": len(parameters),
        "parse_error_count": parse_error_count,
        "local_name_block_count": local_name_block_count,
    }
    return blocks, parameters, summary


def process_snapshot() -> list[str]:
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    residual = []
    if completed.returncode != 0:
        return [f"TASKLIST_ERROR:{completed.returncode}"]
    targets = {"matlab.exe", "python.exe", "pythonw.exe", "pdftoppm.exe"}
    for row in csv.reader(io.StringIO(completed.stdout)):
        if len(row) < 2:
            continue
        name = row[0].strip().lower()
        try:
            process_id = int(row[1].strip())
        except ValueError:
            continue
        if name in targets and process_id not in {os.getpid(), os.getppid()}:
            residual.append(f"{name}:{process_id}")
    return sorted(residual)


def artifact_manifest_rows() -> list[dict[str, Any]]:
    roots = [
        BOARD_ROOT / "code",
        INVENTORY_ROOT,
        BOARD_ROOT / "report",
    ]
    files = []
    for root in roots:
        if root.exists():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.relative_to(root).parts
                and path.suffix.lower() != ".pyc"
            )
    rows = []
    for path in sorted(set(files), key=lambda item: item.as_posix().casefold()):
        rows.append(
            {
                "relative_path": path.relative_to(BOARD_ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def find_named_entries(root: Path, prefix: str) -> list[str]:
    found = []
    pending = [root]
    visited = set()
    while pending:
        directory = pending.pop()
        try:
            resolved = str(directory.resolve()).casefold()
        except OSError:
            continue
        if resolved in visited:
            continue
        visited.add(resolved)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(prefix):
                found.append(entry.path)
            try:
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    pending.append(Path(entry.path))
            except OSError:
                continue
    return sorted(found)


def main() -> int:
    checks: list[dict[str, str]] = []
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    existing_validation_entries = sorted(
        path.relative_to(VALIDATION_ROOT).as_posix()
        for path in VALIDATION_ROOT.rglob("*")
    )
    validation_preflight_ok = all(
        "/" not in relative
        and relative in VALIDATION_ALLOWED_FILES
        and (VALIDATION_ROOT / relative).is_file()
        for relative in existing_validation_entries
    )
    add_check(
        checks,
        "S2-VALIDATION-ROOT-PREFLIGHT",
        "validation_integrity",
        validation_preflight_ok,
        {
            "allowed_files": sorted(VALIDATION_ALLOWED_FILES),
            "missing_allowed_before_run": "permitted",
            "directories": "forbidden",
        },
        existing_validation_entries,
        VALIDATION_ROOT,
    )
    initial_residual = process_snapshot()

    add_check(
        checks,
        "S2-PASSPORT-MANIFEST",
        "step1_passport",
        sha256_file(INPUT_MANIFEST) == INPUT_MANIFEST_SHA256,
        INPUT_MANIFEST_SHA256,
        sha256_file(INPUT_MANIFEST),
        INPUT_MANIFEST,
    )
    for index, (path, expected) in enumerate(STEP1_FIXED_HASHES.items(), start=1):
        actual = sha256_file(path) if path.is_file() else "MISSING"
        add_check(
            checks,
            f"S2-PASSPORT-{index:02d}",
            "step1_passport",
            actual == expected,
            expected,
            actual,
            path,
        )
    freeze_summary_path = BOARD_ROOT / "input" / "input_freeze_summary.json"
    freeze_summary_hash = sha256_file(freeze_summary_path)
    add_check(
        checks,
        "S2-PASSPORT-FREEZE-SUMMARY",
        "step1_passport",
        freeze_summary_hash == INPUT_FREEZE_SUMMARY_SHA256,
        INPUT_FREEZE_SUMMARY_SHA256,
        freeze_summary_hash,
        freeze_summary_path,
    )
    freeze_summary = json.loads(freeze_summary_path.read_text(encoding="utf-8"))
    add_check(
        checks,
        "S2-PASSPORT-FREEZE-CONTENT",
        "step1_passport",
        freeze_summary.get("status") == "PASS"
        and freeze_summary.get("input_count") == 53
        and freeze_summary.get("author_energy_file_count") == 36
        and freeze_summary.get("source_frozen_match_count") == 53
        and freeze_summary.get("source_inside_board_root_count") == 0,
        "PASS|53|36|53|0",
        "|".join(
            str(freeze_summary.get(key, "MISSING"))
            for key in (
                "status",
                "input_count",
                "author_energy_file_count",
                "source_frozen_match_count",
                "source_inside_board_root_count",
            )
        ),
        freeze_summary_path,
    )

    manifest_rows = read_csv(INPUT_MANIFEST)
    expected_author = {
        row["role"].removeprefix("author_energy:"): row["frozen_sha256"].upper()
        for row in manifest_rows
        if row.get("category") == "author_energy_tree"
    }
    author_files = sorted(AUTHOR_ROOT.iterdir(), key=lambda path: path.name.casefold())
    extension_counts = Counter(path.suffix.lower() for path in author_files)
    add_check(
        checks,
        "S2-SOURCE-COUNT",
        "source_inventory",
        len(expected_author) == 36 and len(author_files) == 36,
        "36 manifest rows and 36 files",
        f"{len(expected_author)} manifest rows and {len(author_files)} files",
        AUTHOR_ROOT,
    )
    add_check(
        checks,
        "S2-SOURCE-EXTENSIONS",
        "source_inventory",
        extension_counts == Counter({".m": 5, ".mat": 2, ".mlx": 26, ".slx": 3})
        and all(path.is_file() for path in author_files),
        {".m": 5, ".mat": 2, ".mlx": 26, ".slx": 3},
        dict(sorted(extension_counts.items())),
        AUTHOR_ROOT,
    )
    add_check(
        checks,
        "S2-SOURCE-NAMES",
        "source_inventory",
        {path.name for path in author_files} == set(expected_author),
        sorted(expected_author),
        sorted(path.name for path in author_files),
        INPUT_MANIFEST,
    )
    step1_artifact_rows = read_csv(
        BOARD_ROOT / "outputs" / "step1_artifact_manifest.csv"
    )
    step1_artifact_by_path = {
        row["relative_path"]: row for row in step1_artifact_rows
    }
    passport_paths = {
        "input/input_manifest.csv": (INPUT_MANIFEST.stat().st_size, INPUT_MANIFEST_SHA256),
        "input/input_freeze_summary.json": (
            freeze_summary_path.stat().st_size,
            INPUT_FREEZE_SUMMARY_SHA256,
        ),
    }
    for name in expected_author:
        path = AUTHOR_ROOT / name
        passport_paths[f"input/author_energy/{name}"] = (
            path.stat().st_size,
            expected_author[name],
        )
    passport_ok = True
    for relative, (size, digest) in passport_paths.items():
        row = step1_artifact_by_path.get(relative, {})
        passport_ok &= row.get("size_bytes") == str(size) and row.get("sha256") == digest
    add_check(
        checks,
        "S2-PASSPORT-ARTIFACT-CROSSCHECK",
        "step1_passport",
        passport_ok and len(passport_paths) == 38,
        "38 exact manifest/freeze-summary/author-energy rows",
        f"count={len(passport_paths)}|exact={passport_ok}",
        BOARD_ROOT / "outputs" / "step1_artifact_manifest.csv",
    )
    author_manifest_rows = [
        row for row in manifest_rows if row.get("category") == "author_energy_tree"
    ]
    manifest_contract_ok = len(author_manifest_rows) == 36
    for row in author_manifest_rows:
        name = row.get("role", "").removeprefix("author_energy:")
        path = AUTHOR_ROOT / name
        manifest_contract_ok &= (
            row.get("role") == f"author_energy:{name}"
            and row.get("frozen_relative_path") == f"author_energy/{name}"
            and row.get("status") == "MATCH"
            and row.get("frozen_sha256", "").upper() == expected_author.get(name)
            and row.get("frozen_size_bytes") == str(path.stat().st_size)
        )
    add_check(
        checks,
        "S2-SOURCE-MANIFEST-CONTRACT",
        "source_inventory",
        manifest_contract_ok,
        "36 exact roles, paths, sizes, hashes, MATCH statuses",
        "exact" if manifest_contract_ok else "mismatch",
        INPUT_MANIFEST,
    )
    for index, path in enumerate(author_files, start=1):
        actual = sha256_file(path)
        expected = expected_author.get(path.name, "MISSING")
        add_check(
            checks,
            f"S2-SOURCE-HASH-{index:02d}",
            "source_hash",
            actual == expected,
            expected,
            actual,
            path,
        )

    all_author_rows = read_csv(TABLE_ROOT / "all_author_files.csv")
    author_by_name = {row["source_name"]: row for row in all_author_rows}
    add_check(
        checks,
        "S2-TABLE-AUTHOR-COVERAGE",
        "inventory_table",
        len(all_author_rows) == 36
        and len(author_by_name) == 36
        and set(author_by_name) == set(expected_author),
        "36 raw rows, 36 exact unique source names",
        f"{len(all_author_rows)} raw rows; {len(author_by_name)} unique rows",
        TABLE_ROOT / "all_author_files.csv",
    )
    for name, expected_hash in sorted(expected_author.items(), key=lambda item: item[0].casefold()):
        row = author_by_name.get(name, {})
        add_check(
            checks,
            f"S2-TABLE-AUTHOR-{name}",
            "inventory_table",
            row.get("source_sha256") == expected_hash
            and row.get("extraction_status") == "PASS",
            f"{expected_hash}|PASS",
            f"{row.get('source_sha256', 'MISSING')}|{row.get('extraction_status', 'MISSING')}",
            TABLE_ROOT / "all_author_files.csv",
        )

    mlx_paths = [path for path in author_files if path.suffix.lower() == ".mlx"]
    records = {path.name: inspect_mlx(path) for path in mlx_paths}
    add_check(
        checks,
        "S2-MLX-COUNT",
        "mlx_direct_parse",
        len(records) == 26,
        26,
        len(records),
        AUTHOR_ROOT,
    )

    cell_rows = read_csv(TABLE_ROOT / "mlx_cells.csv")
    output_rows = read_csv(TABLE_ROOT / "mlx_outputs.csv")
    metadata_rows = read_csv(TABLE_ROOT / "mlx_metadata.csv")
    metadata_by_name = {row["source_name"]: row for row in metadata_rows}
    cell_by_key = {
        (row["source_name"], int(row["paragraph_index"])): row for row in cell_rows
    }
    output_by_key = {
        (row["source_name"], int(row["output_index"])): row for row in output_rows
    }
    direct_cell_count = 0
    direct_text_count = 0
    direct_output_count = 0
    for source_index, (name, record) in enumerate(
        sorted(records.items(), key=lambda item: item[0].casefold()), start=1
    ):
        locations = extracted_locations(record["code_cells"])
        direct_cell_count += len(record["code_cells"])
        direct_text_count += len(record["text_cells"])
        direct_output_count += len(record["outputs"])
        generated_code_path = (
            INVENTORY_ROOT / "extracted_mlx_code" / f"{Path(name).stem}__extracted.m"
        )
        expected_code = extracted_code(record).encode("utf-8")
        actual_code = (
            generated_code_path.read_bytes() if generated_code_path.is_file() else b""
        )
        add_check(
            checks,
            f"S2-MLX-CODE-{source_index:02d}",
            "mlx_direct_parse",
            actual_code == expected_code,
            sha256_bytes(expected_code),
            sha256_bytes(actual_code),
            generated_code_path,
        )
        generated_record_path = (
            INVENTORY_ROOT / "extracted_mlx_records" / f"{Path(name).stem}__record.json"
        )
        stored_record = (
            json.loads(generated_record_path.read_text(encoding="utf-8"))
            if generated_record_path.is_file()
            else {}
        )
        record_core_expected = (
            record["source_sha256"],
            record["source_size_bytes"],
            record["archive_entries"],
            record["document_xml_sha256"],
            record["output_xml_sha256"],
            record["paragraphs"],
            record["code_cells"],
            record["text_cells"],
            record["outputs"],
            record["evaluation_state"],
            record["output_status"],
            len(record["outputs"]),
        )
        metadata = stored_record.get("output_metadata", {})
        record_core_actual = (
            stored_record.get("source_sha256"),
            stored_record.get("source_size_bytes"),
            stored_record.get("archive_entries"),
            stored_record.get("document_xml_sha256"),
            stored_record.get("output_xml_sha256"),
            stored_record.get("paragraphs"),
            stored_record.get("code_cells"),
            stored_record.get("text_cells"),
            stored_record.get("outputs"),
            metadata.get("evaluation_state"),
            metadata.get("output_status"),
            len(stored_record.get("outputs", [])),
        )
        expected_record_sha256 = EXPECTED_REVIEWED_MLX_RECORD_SHA256.get(
            generated_record_path.name, "MISSING"
        )
        actual_record_sha256 = (
            sha256_file(generated_record_path)
            if generated_record_path.is_file()
            else "MISSING"
        )
        add_check(
            checks,
            f"S2-MLX-JSON-{source_index:02d}",
            "mlx_direct_parse",
            record_core_actual == record_core_expected
            and actual_record_sha256 == expected_record_sha256,
            {
                "core": record_core_expected,
                "full_file_sha256": expected_record_sha256,
            },
            {
                "core": record_core_actual,
                "full_file_sha256": actual_record_sha256,
            },
            generated_record_path,
        )
        metadata_row = metadata_by_name.get(name, {})
        metadata_expected = (
            record["source_sha256"],
            record["document_xml_sha256"],
            record["output_xml_sha256"],
            record["evaluation_state"],
            record["output_status"],
            record["output_status"].upper(),
            str(
                sum(
                    output["output_type"].lower() == "error"
                    for output in record["outputs"]
                )
            ),
            " | ".join(
                output["value"]
                for output in record["outputs"]
                if output["output_type"].lower() == "error"
            ),
            str(len(record["code_cells"])),
            str(len(record["text_cells"])),
            str(len(record["outputs"])),
            "历史保存输出",
            "PASS",
        )
        metadata_actual = tuple(
            metadata_row.get(field, "MISSING")
            for field in (
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
            )
        )
        add_check(
            checks,
            f"S2-MLX-META-{source_index:02d}",
            "mlx_direct_parse",
            metadata_actual == metadata_expected,
            metadata_expected,
            metadata_actual,
            TABLE_ROOT / "mlx_metadata.csv",
        )
        paragraph_ok = True
        for paragraph in record["paragraphs"]:
            row = cell_by_key.get((name, paragraph["paragraph_index"]), {})
            expected_core = (
                paragraph["xml_xpath"],
                paragraph["kind"],
                str(paragraph["cell_index"]),
                paragraph["style"],
                paragraph["text_sha256"],
                paragraph["text"],
            )
            actual_core = tuple(
                row.get(field, "MISSING")
                for field in (
                    "xml_xpath",
                    "kind",
                    "cell_index",
                    "style",
                    "text_sha256",
                    "text",
                )
            )
            paragraph_ok &= actual_core == expected_core
            if paragraph["kind"] == "code":
                expected_location = tuple(
                    str(item) for item in locations[paragraph["cell_index"]]
                )
            else:
                expected_location = ("", "", "")
            actual_location = tuple(
                row.get(field, "MISSING")
                for field in (
                    "extracted_header_line",
                    "extracted_code_start_line",
                    "extracted_code_end_line",
                )
            )
            paragraph_ok &= actual_location == expected_location
        add_check(
            checks,
            f"S2-MLX-CELLS-{source_index:02d}",
            "mlx_direct_parse",
            paragraph_ok,
            f"{len(record['paragraphs'])} exact paragraphs",
            "exact" if paragraph_ok else "mismatch",
            TABLE_ROOT / "mlx_cells.csv",
        )
        source_outputs_ok = True
        for output in record["outputs"]:
            row = output_by_key.get((name, output["output_index"]), {})
            expected_core = (
                output["output_xpath"],
                output["output_type"],
                "|".join(output["line_numbers"]),
                output["name"],
                output["var_size"],
                output["rows"],
                output["columns"],
                output["var_type"],
                output["value"],
                output["element_sha256"],
                json.dumps(output["large_fields"], ensure_ascii=False, sort_keys=True),
            )
            actual_core = tuple(
                row.get(field, "MISSING")
                for field in (
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
                )
            )
            source_outputs_ok &= actual_core == expected_core
        add_check(
            checks,
            f"S2-MLX-OUTPUTS-{source_index:02d}",
            "mlx_direct_parse",
            source_outputs_ok,
            f"{len(record['outputs'])} exact output elements",
            "exact" if source_outputs_ok else "mismatch",
            TABLE_ROOT / "mlx_outputs.csv",
        )
        expected_output_count = EXPECTED_MLX_OUTPUT_COUNTS.get(name, -1)
        add_check(
            checks,
            f"S2-MLX-OUTPUT-COUNT-{source_index:02d}",
            "mlx_direct_parse",
            len(record["outputs"]) == expected_output_count
            and record["source_sha256"] == record["source_post_parse_sha256"],
            f"count={expected_output_count}|source unchanged",
            f"count={len(record['outputs'])}|before={record['source_sha256']}|after={record['source_post_parse_sha256']}",
            AUTHOR_ROOT / name,
        )

    add_check(
        checks,
        "S2-MLX-CARDINALITY",
        "mlx_direct_parse",
        (
            direct_cell_count,
            direct_text_count,
            direct_output_count,
            len(cell_rows),
            len(output_rows),
            len(metadata_rows),
        )
        == (83, 84, 1333, 167, 1333, 26),
        (83, 84, 1333, 167, 1333, 26),
        (
            direct_cell_count,
            direct_text_count,
            direct_output_count,
            len(cell_rows),
            len(output_rows),
            len(metadata_rows),
        ),
        TABLE_ROOT,
    )
    actual_error_names = {
        name for name, record in records.items() if record["output_status"] == "error"
    }
    actual_manual_names = {
        name for name, record in records.items() if record["evaluation_state"] == "manual"
    }
    explicit_errors = [
        (name, output)
        for name, record in records.items()
        for output in record["outputs"]
        if output["output_type"].lower() == "error"
    ]
    untitled_error_ok = (
        len(explicit_errors) == 1
        and explicit_errors[0][0] == "untitled2.mlx"
        and explicit_errors[0][1]["line_numbers"] == ["71"]
        and "索引不能超过 2" in explicit_errors[0][1]["value"]
    )
    add_check(
        checks,
        "S2-MLX-SAVED-STATUSES",
        "mlx_direct_parse",
        actual_error_names == EXPECTED_MLX_ERROR_NAMES
        and len(actual_manual_names) == 26
        and untitled_error_ok,
        {
            "manual_count": 26,
            "error_names": sorted(EXPECTED_MLX_ERROR_NAMES),
            "explicit_error": "untitled2 line71 index<=2",
        },
        {
            "manual_count": len(actual_manual_names),
            "error_names": sorted(actual_error_names),
            "explicit_error_ok": untitled_error_ok,
        },
        TABLE_ROOT / "mlx_metadata.csv",
    )

    text_rows = read_csv(TABLE_ROOT / "text_scripts.csv")
    text_by_name = {row["source_name"]: row for row in text_rows}
    text_paths = [path for path in author_files if path.suffix.lower() == ".m"]
    expected_text_names = {path.name for path in text_paths}
    text_coverage_ok = (
        len(text_rows) == 5
        and len(text_by_name) == 5
        and set(text_by_name) == expected_text_names
    )
    for index, path in enumerate(text_paths, start=1):
        source_text = decode_text(path)
        expected_payload = (source_text.rstrip() + "\n").replace("\r\n", "\n").encode("utf-8")
        target = INVENTORY_ROOT / "extracted_text_code" / path.name
        actual_payload = target.read_bytes() if target.is_file() else b""
        row = text_by_name.get(path.name, {})
        passed = (
            text_coverage_ok
            and actual_payload == expected_payload
            and row.get("source_sha256") == sha256_file(path)
            and row.get("line_count") == str(len(source_text.splitlines()))
        )
        add_check(
            checks,
            f"S2-TEXT-{index:02d}",
            "text_direct_parse",
            passed,
            f"{sha256_bytes(expected_payload)}|{len(source_text.splitlines())}",
            f"{sha256_bytes(actual_payload)}|{row.get('line_count', 'MISSING')}",
            target,
        )

    direct_mat_rows = []
    for path in author_files:
        if path.suffix.lower() == ".mat":
            direct_mat_rows.extend(inventory_mat_direct(path))
    table_mat_rows = read_csv(TABLE_ROOT / "mat_variables.csv")
    direct_mat_core = sorted(
        (
            row["source_name"],
            row["source_sha256"],
            row["variable_name"],
            row["shape"],
            row["matlab_class"],
            row["numpy_dtype"],
            row["data_sha256"],
            row["finite_count"],
            row["minimum_real"],
            row["maximum_real"],
        )
        for row in direct_mat_rows
    )
    table_mat_core = sorted(
        (
            row["source_name"],
            row["source_sha256"],
            row["variable_name"],
            row["shape"],
            row["matlab_class"],
            row["numpy_dtype"],
            row["data_sha256"],
            row["finite_count"],
            row["minimum_real"],
            row["maximum_real"],
        )
        for row in table_mat_rows
    )
    add_check(
        checks,
        "S2-MAT-DIRECT",
        "mat_direct_parse",
        direct_mat_core == table_mat_core and len(direct_mat_core) == 4,
        direct_mat_core,
        table_mat_core,
        TABLE_ROOT / "mat_variables.csv",
    )
    mat_shape_contract = {
        (row["source_name"], row["variable_name"]): (
            row["shape"],
            row["matlab_class"],
            row["numpy_dtype"],
        )
        for row in direct_mat_rows
    }
    expected_mat_shape_contract = {
        ("EQ.mat", "EQ_intensity"): ("1x1", "double", "float64"),
        ("EQ.mat", "EQ_sw"): ("1x1", "double", "uint8"),
        ("EQ.mat", "ElCentroAccel"): ("2x2060", "double", "float64"),
        ("stab_3.mat", "stab"): ("20x20", "double", "float64"),
    }
    add_check(
        checks,
        "S2-MAT-CONTRACT",
        "mat_direct_parse",
        mat_shape_contract == expected_mat_shape_contract,
        expected_mat_shape_contract,
        mat_shape_contract,
        AUTHOR_ROOT,
    )

    slx_model_rows = read_csv(TABLE_ROOT / "slx_models.csv")
    slx_block_rows = read_csv(TABLE_ROOT / "slx_blocks.csv")
    slx_parameter_rows = read_csv(TABLE_ROOT / "slx_parameters.csv")
    direct_blocks = []
    direct_parameters = []
    direct_slx_summary = {}
    for path in author_files:
        if path.suffix.lower() != ".slx":
            continue
        blocks, parameters, summary = inventory_slx_direct(path)
        direct_blocks.extend((path.name,) + row for row in blocks)
        direct_parameters.extend((path.name,) + row for row in parameters)
        direct_slx_summary[path.name] = summary
    table_blocks = [
        (
            row["source_name"],
            row["xml_entry"],
            row["sid"],
            row["block_type"],
            row["block_name"],
        )
        for row in slx_block_rows
    ]
    table_parameters = [
        (
            row["source_name"],
            row["xml_entry"],
            row["sid"],
            row["block_type"],
            row["block_name"],
            row["parameter_name"],
            row["parameter_value"],
        )
        for row in slx_parameter_rows
    ]
    add_check(
        checks,
        "S2-SLX-BLOCKS",
        "slx_direct_parse",
        Counter(direct_blocks) == Counter(table_blocks) and len(direct_blocks) == 424,
        "424 exact block tuples",
        f"{len(table_blocks)} table tuples; exact={Counter(direct_blocks) == Counter(table_blocks)}",
        TABLE_ROOT / "slx_blocks.csv",
    )
    add_check(
        checks,
        "S2-SLX-PARAMETERS",
        "slx_direct_parse",
        Counter(direct_parameters) == Counter(table_parameters)
        and len(direct_parameters) == 1884,
        "1884 exact parameter tuples",
        f"{len(table_parameters)} table tuples; exact={Counter(direct_parameters) == Counter(table_parameters)}",
        TABLE_ROOT / "slx_parameters.csv",
    )
    expected_slx_counts = {
        "lvxvjie_guyan_2.slx": (189, 840),
        "lvxvjie_guyan_3.slx": (185, 822),
        "test.slx": (50, 222),
    }
    slx_model_by_name = {row["source_name"]: row for row in slx_model_rows}
    models_ok = (
        len(slx_model_rows) == 3
        and len(slx_model_by_name) == 3
        and set(slx_model_by_name) == set(expected_slx_counts)
        and set(direct_slx_summary) == set(expected_slx_counts)
    )
    for source_name, expected_counts in expected_slx_counts.items():
        row = slx_model_by_name.get(source_name, {})
        direct = direct_slx_summary.get(source_name, {})
        models_ok &= (
            row.get("source_sha256") == direct.get("source_sha256")
            and row.get("block_count") == str(direct.get("block_count", "MISSING"))
            and row.get("parameter_count")
            == str(direct.get("parameter_count", "MISSING"))
            and (direct.get("block_count"), direct.get("parameter_count"))
            == expected_counts
            and direct.get("parse_error_count") == 0
            and direct.get("local_name_block_count") == direct.get("block_count")
        )
    add_check(
        checks,
        "S2-SLX-MODELS",
        "slx_direct_parse",
        models_ok,
        "3 exact model summaries",
        "exact" if models_ok else "mismatch",
        TABLE_ROOT / "slx_models.csv",
    )
    expected_external_mat = {
        "ElCentroAccelNoScaling.mat",
        "KobeAccelNoScaling.mat",
        "MorganAccelNoScaling.mat",
    }
    parameter_values = [row[-1] for row in direct_parameters]
    found_external_mat = {
        name
        for name in expected_external_mat
        if any(name in value for value in parameter_values)
    }
    absent_external_mat = {
        name for name in found_external_mat if not (AUTHOR_ROOT / name).exists()
    }
    add_check(
        checks,
        "S2-SLX-EXTERNAL-MAT",
        "slx_direct_parse",
        found_external_mat == expected_external_mat
        and absent_external_mat == expected_external_mat,
        sorted(expected_external_mat),
        {
            "referenced": sorted(found_external_mat),
            "absent_from_frozen_author_root": sorted(absent_external_mat),
        },
        TABLE_ROOT / "slx_parameters.csv",
    )

    route_rows = read_csv(TABLE_ROOT / "energy_routes.csv")
    route_by_name = {row["source_name"]: row for row in route_rows}
    edge_rows = read_csv(TABLE_ROOT / "dependency_edges.csv")
    edge_by_consumer = {row["consumer"]: row for row in edge_rows}
    add_check(
        checks,
        "S2-ENERGY-COVERAGE",
        "energy_route_contract",
        len(route_rows) == 7
        and len(route_by_name) == 7
        and len(edge_rows) == 7
        and len(edge_by_consumer) == 7
        and set(route_by_name) == set(ENERGY_EXPECTED)
        and set(edge_by_consumer) == set(ENERGY_EXPECTED),
        {"row_count": 7, "unique_count": 7, "names": sorted(ENERGY_EXPECTED)},
        {
            "route_row_count": len(route_rows),
            "route_unique_count": len(route_by_name),
            "edge_row_count": len(edge_rows),
            "edge_unique_count": len(edge_by_consumer),
            "names": sorted(route_by_name),
        },
        TABLE_ROOT,
    )
    for index, (name, expected) in enumerate(ENERGY_EXPECTED.items(), start=1):
        record = records[name]
        code = "\n".join(record["code_cells"])
        active = remove_matlab_comments(code)
        branch_active = [
            remove_matlab_comments(cell) for cell in record["code_cells"][:3]
        ]
        branch_mass = tuple(
            bool(re.search(r"phi\(:,i\)\s*=\s*phi\(:,i\)\s*/\s*sqrt", cell))
            for cell in branch_active
        )
        branch_participation = tuple(
            bool(
                re.search(
                    r"participation_ratio\s*=\s*GammaSq\s*/\s*sum\(GammaSq\)",
                    cell,
                )
            )
            for cell in branch_active
        )
        branch_energy = tuple(
            bool(
                re.search(
                    r"E\(:,i\)\s*=\s*E\(:,i\)\s*/\s*sum\(E\(:,i\)\)",
                    cell,
                )
            )
            for cell in branch_active
        )
        expected_energy_branches = (
            (True, True, True)
            if expected["energy_normalized"]
            else (False, False, False)
        )
        total_name_counts = Counter(
            output["name"]
            for output in record["outputs"]
            if output["name"] in {"total_increase_guyan", "total_increase_cb"}
        )
        direct_guyan_formula_lines = [
            line.strip()
            for line in active.splitlines()
            if re.match(r"\s*total_increase_guyan\s*=", line)
        ]
        direct_cb_formula_lines = [
            line.strip()
            for line in active.splitlines()
            if re.match(r"\s*total_increase_cb\s*=", line)
        ]
        named_outputs = {
            output["name"]: output["value"]
            for output in record["outputs"]
            if output["name"]
        }
        dimensions = tuple(
            output["var_size"]
            for output in record["outputs"]
            if output["name"] == "participation_ratio"
        )
        energy_normalized = all(branch_energy)
        route = route_by_name.get(name, {})
        edge = edge_by_consumer.get(name, {})
        actual_saved = (
            named_outputs.get("total_increase_guyan", "MISSING"),
            named_outputs.get("total_increase_cb", "MISSING"),
        )
        passed = (
            record["source_sha256"] == expected["sha256"]
            and record["evaluation_state"] == "manual"
            and record["output_status"] == "ready"
            and len(record["code_cells"]) == 4
            and dimensions == expected["dims"]
            and actual_saved == expected["saved"]
            and branch_mass == (True, True, True)
            and branch_participation == (True, True, True)
            and branch_energy == expected_energy_branches
            and total_name_counts["total_increase_guyan"] == 1
            and total_name_counts["total_increase_cb"] == 1
            and not re.search(
                r"(?m)^\s*(load|save|run|sim|cd|clear)\s*(?:\(|\s|$)", active
            )
            and route.get("saved_output_evidence_level") == "历史保存输出"
            and route.get("saved_output_source") == "embedded_historical"
            and route.get("evaluation_state") == "manual"
            and route.get("output_status") == "ready"
            and route.get("dimension_family") == expected["family"]
            and route.get("coordinate_order_status") == expected["coordinate"]
            and route.get("candidate_status") == expected["candidate_status"]
            and route.get("equation_4_45_exact") == "False"
            and route.get("saved_guyan_output_count") == "1"
            and route.get("saved_cb_output_count") == "1"
            and len(direct_guyan_formula_lines) == 1
            and len(direct_cb_formula_lines) == 1
            and route.get("guyan_total_formula") == direct_guyan_formula_lines[0]
            and route.get("cb_total_formula") == direct_cb_formula_lines[0]
            and tuple(
                route.get(field) == "True"
                for field in (
                    "original_mass_normalization_active",
                    "guyan_mass_normalization_active",
                    "cb_mass_normalization_active",
                )
            )
            == (True, True, True)
            and tuple(
                route.get(field) == "True"
                for field in (
                    "original_participation_normalization_active",
                    "guyan_participation_normalization_active",
                    "cb_participation_normalization_active",
                )
            )
            == (True, True, True)
            and tuple(
                route.get(field) == "True"
                for field in (
                    "original_energy_normalization_active",
                    "guyan_energy_normalization_active",
                    "cb_energy_normalization_active",
                )
            )
            == expected_energy_branches
            and edge.get("producer") == expected["producer"]
            and edge.get("dimension_family") == expected["family"]
            and edge.get("coordinate_order_status") == expected["coordinate"]
            and edge.get("candidate_status") == expected["candidate_status"]
        )
        add_check(
            checks,
            f"S2-ENERGY-{index:02d}",
            "energy_route_contract",
            passed,
            {
                "dims": expected["dims"],
                "saved": expected["saved"],
                "producer": expected["producer"],
                "coordinate": expected["coordinate"],
                "mass_branches": (True, True, True),
                "participation_branches": (True, True, True),
                "energy_branches": expected_energy_branches,
                "saved_output_count": (1, 1),
                "formula_lines": "exact direct code",
            },
            {
                "dims": dimensions,
                "saved": actual_saved,
                "producer": edge.get("producer", "MISSING"),
                "coordinate": edge.get("coordinate_order_status", "MISSING"),
                "mass_branches": branch_mass,
                "participation_branches": branch_participation,
                "energy_branches": branch_energy,
                "saved_output_count": (
                    total_name_counts["total_increase_guyan"],
                    total_name_counts["total_increase_cb"],
                ),
                "formula_lines": (
                    direct_guyan_formula_lines,
                    direct_cb_formula_lines,
                ),
            },
            AUTHOR_ROOT / name,
        )
        add_check(
            checks,
            f"S2-ENERGY-45-{index:02d}",
            "formula_contract",
            (
                "sum(increase_rate)" not in active
                and "total_increase_guyan" in active
                and "total_increase_cb" in active
                and (
                    route.get("cb_uses_guyan_denominator") == "True"
                    if name.startswith("Copy_2_")
                    else route.get("cb_uses_guyan_denominator") == "False"
                )
            ),
            "saved scalar is not equation 4-45 and mismatch is explicitly retained",
            route.get("guyan_total_formula", "MISSING")
            + "|"
            + route.get("cb_total_formula", "MISSING"),
            INVENTORY_ROOT / "extracted_mlx_code" / f"{Path(name).stem}__extracted.m",
        )

    upstream_hash = sha256_file(UPSTREAM_PD)
    upstream = loadmat(UPSTREAM_PD, squeeze_me=True, struct_as_record=False)
    upstream_actual = {}
    upstream_ok = upstream_hash == UPSTREAM_PD_SHA256
    for name, expected_contract in {
        "pd2": {
            "dims": (6, 2, 5),
            "master": [1, 4],
            "slave": [2, 3, 5, 6],
            "order": [1, 4, 2, 3, 5, 6],
        },
        "pd3": {
            "dims": (9, 2, 5),
            "master": [1, 7],
            "slave": [4, 2, 3, 5, 6, 8, 9],
            "order": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        },
    }.items():
        value = upstream.get(name)
        actual_contract = {
            "dims": (
                int(np.asarray(value.full_dof).squeeze()),
                int(np.asarray(value.guyan_dof).squeeze()),
                int(np.asarray(value.cb_dof).squeeze()),
            ),
            "master": np.asarray(value.index_master).astype(int).reshape(-1).tolist(),
            "slave": np.asarray(value.index_slave).astype(int).reshape(-1).tolist(),
            "order": np.asarray(value.idx_all).astype(int).reshape(-1).tolist(),
            "matrix_finite": int(np.asarray(value.matrix_finite).squeeze()),
            "matrix_shapes": (
                tuple(np.asarray(value.KPrt).shape),
                tuple(np.asarray(value.KRren).shape),
                tuple(np.asarray(value.KR_cb).shape),
            ),
            "all_finite": all(
                np.all(np.isfinite(np.asarray(getattr(value, field))))
                for field in (
                    "KPrt",
                    "MPrt",
                    "KRren",
                    "MRren",
                    "KR_cb",
                    "MR_cb",
                )
            ),
        }
        upstream_actual[name] = actual_contract
        expected_shapes = (
            (expected_contract["dims"][0], expected_contract["dims"][0]),
            (expected_contract["dims"][1], expected_contract["dims"][1]),
            (expected_contract["dims"][2], expected_contract["dims"][2]),
        )
        upstream_ok &= (
            actual_contract["dims"] == expected_contract["dims"]
            and actual_contract["master"] == expected_contract["master"]
            and actual_contract["slave"] == expected_contract["slave"]
            and actual_contract["order"] == expected_contract["order"]
            and actual_contract["matrix_finite"] == 1
            and actual_contract["matrix_shapes"] == expected_shapes
            and actual_contract["all_finite"]
        )
    add_check(
        checks,
        "S2-UPSTREAM-PD",
        "upstream_coordinate_contract",
        upstream_ok,
        {
            "sha256": UPSTREAM_PD_SHA256,
            "pd2": "6->2/5|[1,4,2,3,5,6]|finite",
            "pd3": "9->2/5|[1,7,4,2,3,5,6,8,9]|finite",
        },
        {"sha256": upstream_hash, "contracts": upstream_actual},
        UPSTREAM_PD,
    )

    normalized_sources = {
        name: re.sub(
            r"\s+",
            "",
            remove_matlab_comments(
                decode_text(AUTHOR_ROOT / name)
                if name.endswith(".m")
                else "\n".join(records[name]["code_cells"])
            ),
        )
        for name in (
            "PDmonicanshu.m",
            "PDmonicanshu2.m",
            "PDmonicanshu3.m",
            "monicanshu_2_suoju.mlx",
            "monicanshu_3_suoju.mlx",
            "energy_zonghe2.mlx",
            "Copy_2_of_energy_zonghe2.mlx",
            "energy_zonghe3.mlx",
            "Copy_2_of_energy_zonghe3.mlx",
            "Copy_of_energy_zonghe2.mlx",
            "Copy_of_energy_zonghe3.mlx",
        )
    }
    parameter_family_ok = all(
        bool(re.search(r"785e3\.\*1\.9|785e3\*1\.9", normalized_sources[name]))
        for name in ("PDmonicanshu.m", "PDmonicanshu2.m", "PDmonicanshu3.m")
    ) and all(
        bool(re.search(r"785e3\.\*1\.7|785e3\*1\.7", normalized_sources[name]))
        for name in ("monicanshu_2_suoju.mlx", "monicanshu_3_suoju.mlx")
    )
    order_semantics_ok = (
        "index2=[2,3,4,5,6,8,9]" in normalized_sources["monicanshu_3_suoju.mlx"]
        and "index2=[4,2,3,5,6,8,9]" in normalized_sources["energy_zonghe3.mlx"]
        and "index2=[4,2,3,5,6,8,9]"
        in normalized_sources["Copy_2_of_energy_zonghe3.mlx"]
        and "index1=" not in normalized_sources["Copy_of_energy_zonghe2.mlx"]
        and "index2=" not in normalized_sources["Copy_of_energy_zonghe2.mlx"]
        and "index1=" not in normalized_sources["Copy_of_energy_zonghe3.mlx"]
        and "index2=" not in normalized_sources["Copy_of_energy_zonghe3.mlx"]
    )
    edge_contract_ok = len(edge_rows) == 7
    for consumer, edge in edge_by_consumer.items():
        producer = edge.get("producer", "")
        expected_parameter = (
            "rho=785e3*1.9"
            if producer.startswith("PDmonicanshu")
            else "rho=785e3*1.7"
        )
        if consumer == "energy_zonghe.mlx":
            expected_mapping = "reduced[1,2,3]->global[1,6,11]"
        elif consumer.endswith("zonghe2.mlx"):
            expected_mapping = "reduced[1,2]->local[1,4]->global[1,6]"
        else:
            expected_mapping = "reduced[1,2]->local[1,7]->global[1,11]"
        edge_contract_ok &= (
            edge.get("parameter_family") == expected_parameter
            and edge.get("retained_coordinate_mapping") == expected_mapping
            and edge.get("explicit_upstream_workspace_dependency") == "True"
            and edge.get("step3_execution_status") == "NOT_RUN"
        )
    add_check(
        checks,
        "S2-DEPENDENCY-DIRECT",
        "upstream_coordinate_contract",
        parameter_family_ok and order_semantics_ok and edge_contract_ok,
        "1.9/1.7 parameter families; two TP order failures; retained-coordinate mappings",
        {
            "parameter_family_ok": parameter_family_ok,
            "order_semantics_ok": order_semantics_ok,
            "edge_contract_ok": edge_contract_ok,
        },
        TABLE_ROOT / "dependency_edges.csv",
    )

    thesis_hash = sha256_file(THESIS)
    with THESIS.open("rb") as stream:
        reader = PyPDF2.PdfReader(stream)
        thesis_page_count = len(reader.pages)
        formula_text = re.sub(r"\s+", " ", reader.pages[71].extract_text() or "")
        table_text = re.sub(r"\s+", " ", reader.pages[72].extract_text() or "")
    formula_markers_ok = all(
        marker in formula_text for marker in ("(4-41)", "(4-42)", "(4-43)", "(4-44)", "(4-45)")
    )
    table_pattern = re.compile(
        r"一类\s*Guyan\s*0\.3065\s*Craig-Bampton\s*0\.1879\s*"
        r"二类\s*Guyan\s*0\.3927\s*Craig-Bampton\s*0\.2021"
    )
    table_values_ok = bool(table_pattern.search(table_text))
    add_check(
        checks,
        "S2-THESIS-DIRECT",
        "paper_contract",
        thesis_hash == THESIS_SHA256
        and thesis_page_count == 83
        and formula_markers_ok
        and table_values_ok,
        "fixed thesis hash|83 pages|equations 4-41..4-45|four ordered Table 4-1 values",
        {
            "sha256": thesis_hash,
            "pages": thesis_page_count,
            "formula_markers_ok": formula_markers_ok,
            "table_values_ok": table_values_ok,
        },
        THESIS,
    )

    historical_target_rows = read_csv(
        TABLE_ROOT / "historical_table4_1_targets.csv"
    )
    add_check(
        checks,
        "S2-HISTORICAL-TARGET-CONTRACT",
        "historical_target_contract",
        historical_target_rows == EXPECTED_HISTORICAL_TARGET_ROWS,
        EXPECTED_HISTORICAL_TARGET_ROWS,
        historical_target_rows,
        TABLE_ROOT / "historical_table4_1_targets.csv",
    )

    derived_matches: dict[tuple[str, str], list[str]] = {}
    for division, method in EXPECTED_TARGETS:
        target = float(EXPECTED_TARGETS[(division, method)][0])
        output_name = (
            "total_increase_guyan" if method == "Guyan" else "total_increase_cb"
        )
        matches = []
        for source, record in records.items():
            if source not in ENERGY_EXPECTED:
                continue
            for output in record["outputs"]:
                if output["name"] != output_name:
                    continue
                if f"{float(output['value']) / 100.0:.4f}" == f"{target:.4f}":
                    matches.append(source)
        derived_matches[(division, method)] = matches
    derived_expected = {
        ("第一类划分", "Guyan"): [],
        ("第一类划分", "Craig-Bampton"): [],
        ("第二类划分", "Guyan"): ["Copy_2_of_energy_zonghe3.mlx"],
        ("第二类划分", "Craig-Bampton"): ["Copy_2_of_energy_zonghe3.mlx"],
    }
    matched_route = route_by_name["Copy_2_of_energy_zonghe3.mlx"]
    invalid_match_guard = (
        matched_route.get("original_energy_normalization_active") == "False"
        and matched_route.get("guyan_energy_normalization_active") == "False"
        and matched_route.get("cb_energy_normalization_active") == "False"
        and matched_route.get("cb_uses_guyan_denominator") == "True"
        and matched_route.get("equation_4_45_exact") == "False"
    )
    add_check(
        checks,
        "S2-TARGET-DIRECT-DERIVATION",
        "historical_target_match",
        derived_matches == derived_expected and invalid_match_guard,
        {"matches": derived_expected, "formula_valid": False},
        {"matches": derived_matches, "invalid_match_guard": invalid_match_guard},
        TABLE_ROOT / "historical_target_matches.csv",
    )

    formula_rows = read_csv(TABLE_ROOT / "formula_route_audit.csv")
    expected_formula_rows = []
    copy_2_names = {
        "Copy_2_of_energy_zonghe2.mlx",
        "Copy_2_of_energy_zonghe3.mlx",
    }
    repeated_mass_names = {
        "energy_zonghe2.mlx",
        "Copy_2_of_energy_zonghe2.mlx",
    }
    for source in ENERGY_EXPECTED:
        active = remove_matlab_comments("\n".join(records[source]["code_cells"]))
        direct_guyan = [
            line.strip()
            for line in active.splitlines()
            if re.match(r"\s*total_increase_guyan\s*=", line)
        ]
        direct_cb = [
            line.strip()
            for line in active.splitlines()
            if re.match(r"\s*total_increase_cb\s*=", line)
        ]
        influence_note = (
            "r0=MPrt*ones后代码仍计算phi^T*M*r，存在重复质量矩阵风险"
            if source in repeated_mass_names
            else "质量归一化使论文分母数值为1，但激励向量身份仍未由脚本证明"
        )
        formula_45_implementation = (
            f"G:{direct_guyan[0]} | CB:{direct_cb[0]}"
            if len(direct_guyan) == 1 and len(direct_cb) == 1
            else "SOURCE_FORMULA_LINE_MISSING_OR_DUPLICATED"
        )
        expected_formula_rows.extend(
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
                    "implementation": (
                        "GammaSq=Gamma.^2; "
                        "participation_ratio=GammaSq/sum(GammaSq)"
                    ),
                    "static_status": "STRUCTURAL_MATCH",
                    "reason": "归一化结构与论文一致，但继承式(4-41)的激励身份风险",
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-43",
                    "implementation": (
                        "E=0.5*omega^2*m*phi^2；按列归一化被注释"
                        if source in copy_2_names
                        else "E=0.5*omega^2*m*phi^2后按列归一化"
                    ),
                    "static_status": (
                        "FORMULA_MISMATCH"
                        if source in copy_2_names
                        else "STRUCTURAL_MATCH"
                    ),
                    "reason": (
                        "未形成论文要求的单模态坐标能量占比"
                        if source in copy_2_names
                        else "按列归一化后0.5*omega^2逐列消去"
                    ),
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-44",
                    "implementation": "E_total=E*participation_ratio",
                    "static_status": (
                        "INPUT_IDENTITY_MISMATCH"
                        if source in copy_2_names
                        else "STRUCTURAL_MATCH"
                    ),
                    "reason": (
                        "输入E未归一化，输出不再是综合能量占比"
                        if source in copy_2_names
                        else "矩阵乘法结构与论文一致"
                    ),
                    "evidence_cell": "C001|C002|C003",
                },
                {
                    "source_name": source,
                    "equation": "4-45",
                    "implementation": formula_45_implementation,
                    "static_status": "FORMULA_MISMATCH",
                    "reason": (
                        "最终标量使用能量和的相对变化，"
                        "未执行论文逐坐标相对变化之和"
                    ),
                    "evidence_cell": "C004",
                },
            ]
        )
    formula_counts = Counter(
        (row["equation"], row["static_status"]) for row in formula_rows
    )
    expected_formula_counts = Counter(
        {
            ("4-41", "PARTIAL"): 7,
            ("4-42", "STRUCTURAL_MATCH"): 7,
            ("4-43", "STRUCTURAL_MATCH"): 5,
            ("4-43", "FORMULA_MISMATCH"): 2,
            ("4-44", "STRUCTURAL_MATCH"): 5,
            ("4-44", "INPUT_IDENTITY_MISMATCH"): 2,
            ("4-45", "FORMULA_MISMATCH"): 7,
        }
    )
    add_check(
        checks,
        "S2-FORMULA-AUDIT",
        "formula_contract",
        formula_rows == expected_formula_rows
        and formula_counts == expected_formula_counts,
        expected_formula_rows,
        formula_rows,
        TABLE_ROOT / "formula_route_audit.csv",
    )

    paper_rows = read_csv(TABLE_ROOT / "paper_formula_contract.csv")
    add_check(
        checks,
        "S2-PAPER-FORMULAS",
        "paper_contract",
        paper_rows == EXPECTED_PAPER_FORMULA_ROWS,
        EXPECTED_PAPER_FORMULA_ROWS,
        paper_rows,
        TABLE_ROOT / "paper_formula_contract.csv",
    )

    match_rows = read_csv(TABLE_ROOT / "historical_target_matches.csv")
    add_check(
        checks,
        "S2-TARGET-MATCH-EXACT",
        "historical_target_match",
        match_rows == EXPECTED_HISTORICAL_MATCH_ROWS,
        EXPECTED_HISTORICAL_MATCH_ROWS,
        match_rows,
        TABLE_ROOT / "historical_target_matches.csv",
    )
    match_by_key = {(row["division"], row["method"]): row for row in match_rows}
    for index, (key, expected) in enumerate(EXPECTED_TARGETS.items(), start=1):
        row = match_by_key.get(key, {})
        actual = (
            row.get("paper_value", "MISSING"),
            row.get("match_status", "MISSING"),
            row.get("matched_routes", "MISSING"),
            row.get("formula_compliant_match", "MISSING"),
        )
        desired = (expected[0], expected[1], expected[2], "False")
        add_check(
            checks,
            f"S2-TARGET-{index:02d}",
            "historical_target_match",
            actual == desired,
            desired,
            actual,
            TABLE_ROOT / "historical_target_matches.csv",
        )

    dependency_rows = read_csv(TABLE_ROOT / "dependency_file_roles.csv")
    non_energy_names = set(expected_author) - set(ENERGY_EXPECTED)
    add_check(
        checks,
        "S2-DEPENDENCY-COVERAGE",
        "dependency_contract",
        len(dependency_rows) == 29
        and {row["source_name"] for row in dependency_rows} == non_energy_names
        and sha256_file(TABLE_ROOT / "dependency_file_roles.csv")
        == EXPECTED_REVIEWED_OUTPUT_SHA256[
            "tables/dependency_file_roles.csv"
        ],
        {
            "names": sorted(non_energy_names),
            "sha256": EXPECTED_REVIEWED_OUTPUT_SHA256[
                "tables/dependency_file_roles.csv"
            ],
        },
        {
            "names": sorted(
                row.get("source_name", "") for row in dependency_rows
            ),
            "sha256": sha256_file(TABLE_ROOT / "dependency_file_roles.csv"),
        },
        TABLE_ROOT / "dependency_file_roles.csv",
    )
    issue_rows = read_csv(TABLE_ROOT / "static_issue_register.csv")
    add_check(
        checks,
        "S2-ISSUE-REGISTER",
        "scientific_boundary",
        len(issue_rows) == 14
        and [row["issue_id"] for row in issue_rows]
        == [f"S{index:02d}" for index in range(1, 15)]
        and sha256_file(TABLE_ROOT / "static_issue_register.csv")
        == EXPECTED_REVIEWED_OUTPUT_SHA256[
            "tables/static_issue_register.csv"
        ],
        {
            "issue_ids": [f"S{index:02d}" for index in range(1, 15)],
            "sha256": EXPECTED_REVIEWED_OUTPUT_SHA256[
                "tables/static_issue_register.csv"
            ],
        },
        {
            "issue_ids": [row.get("issue_id") for row in issue_rows],
            "sha256": sha256_file(TABLE_ROOT / "static_issue_register.csv"),
        },
        TABLE_ROOT / "static_issue_register.csv",
    )

    summary_path = INVENTORY_ROOT / "inventory_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected_summary = {
        "schema_version": "BOARD21_STEP2_STATIC_INVENTORY_V3",
        "status": "STATIC_INVENTORY_PASS",
        "matlab_executed": False,
        "scientific_reproduction_status": "STATIC_ONLY_NOT_COMPUTATIONALLY_REPRODUCED",
        "author_file_count": 36,
        "mlx_file_count": 26,
        "mlx_manual_count": 26,
        "mlx_embedded_output_ready_count": 22,
        "mlx_error_count": 4,
        "mlx_explicit_error_element_count": 1,
        "mlx_code_cell_count": 83,
        "mlx_text_cell_count": 84,
        "mlx_output_element_count": 1333,
        "energy_route_count": 7,
        "energy_route_embedded_manual_ready_output_count": 7,
        "dependency_file_count": 29,
        "dependency_edge_count": 7,
        "dependency_coordinate_pass_count": 5,
        "dependency_coordinate_fail_count": 2,
        "formula_route_audit_count": 35,
        "formula_4_45_match_count": 0,
        "historical_numeric_match_count": 2,
        "formula_compliant_historical_match_count": 0,
        "static_issue_count": 14,
        "mat_variable_count": 4,
        "slx_model_count": 3,
        "slx_block_count": 424,
        "slx_parameter_count": 1884,
        "paper_formula_count": 5,
        "historical_target_count": 4,
    }
    actual_summary = {key: summary.get(key, "MISSING") for key in expected_summary}
    add_check(
        checks,
        "S2-SUMMARY",
        "inventory_summary",
        actual_summary == expected_summary,
        expected_summary,
        actual_summary,
        summary_path,
    )

    inventory_files = sorted(
        path.relative_to(INVENTORY_ROOT).as_posix()
        for path in INVENTORY_ROOT.rglob("*")
        if path.is_file()
    )
    add_check(
        checks,
        "S2-INVENTORY-FILE-COUNT",
        "artifact_closure",
        len(inventory_files) == 75,
        75,
        len(inventory_files),
        INVENTORY_ROOT,
    )
    expected_table_names = {
        "all_author_files.csv",
        "dependency_edges.csv",
        "dependency_file_roles.csv",
        "energy_routes.csv",
        "formula_route_audit.csv",
        "historical_table4_1_targets.csv",
        "historical_target_matches.csv",
        "mat_variables.csv",
        "mlx_cells.csv",
        "mlx_metadata.csv",
        "mlx_outputs.csv",
        "paper_formula_contract.csv",
        "slx_blocks.csv",
        "slx_models.csv",
        "slx_parameters.csv",
        "static_issue_register.csv",
        "text_scripts.csv",
    }
    actual_table_names = {path.name for path in TABLE_ROOT.iterdir() if path.is_file()}
    add_check(
        checks,
        "S2-INVENTORY-TABLE-NAMES",
        "artifact_closure",
        actual_table_names == expected_table_names,
        sorted(expected_table_names),
        sorted(actual_table_names),
        TABLE_ROOT,
    )
    expected_inventory_paths = {"inventory_summary.json"}
    expected_inventory_paths.update(f"tables/{name}" for name in expected_table_names)
    expected_inventory_paths.update(
        f"extracted_mlx_code/{Path(name).stem}__extracted.m" for name in records
    )
    expected_inventory_paths.update(
        f"extracted_mlx_records/{Path(name).stem}__record.json" for name in records
    )
    expected_inventory_paths.update(
        f"extracted_text_code/{path.name}" for path in text_paths
    )
    expected_reviewed_output_paths = {"inventory_summary.json"}
    expected_reviewed_output_paths.update(
        f"tables/{name}" for name in expected_table_names
    )
    actual_reviewed_output_hashes = {
        relative: (
            sha256_file(INVENTORY_ROOT / relative)
            if (INVENTORY_ROOT / relative).is_file()
            else "MISSING"
        )
        for relative in EXPECTED_REVIEWED_OUTPUT_SHA256
    }
    reviewed_output_hashes_ok = (
        set(EXPECTED_REVIEWED_OUTPUT_SHA256)
        == expected_reviewed_output_paths
        and actual_reviewed_output_hashes == EXPECTED_REVIEWED_OUTPUT_SHA256
    )
    extension_contract = Counter(Path(path).suffix.lower() for path in inventory_files)
    add_check(
        checks,
        "S2-INVENTORY-ALLOWED-PATHS",
        "artifact_closure",
        set(inventory_files) == expected_inventory_paths
        and extension_contract == Counter({".m": 31, ".json": 27, ".csv": 17})
        and reviewed_output_hashes_ok
        and not any(".tmp" in path.lower() or "copytmp" in path.lower() for path in inventory_files),
        {
            "paths": sorted(expected_inventory_paths),
            "extensions": {".m": 31, ".json": 27, ".csv": 17},
            "reviewed_output_sha256": EXPECTED_REVIEWED_OUTPUT_SHA256,
        },
        {
            "extra": sorted(set(inventory_files) - expected_inventory_paths),
            "missing": sorted(expected_inventory_paths - set(inventory_files)),
            "extensions": dict(sorted(extension_contract.items())),
            "reviewed_output_hash_mismatch": sorted(
                relative
                for relative in expected_reviewed_output_paths
                if actual_reviewed_output_hashes.get(relative) !=
                EXPECTED_REVIEWED_OUTPUT_SHA256.get(relative)
            ),
        },
        INVENTORY_ROOT,
    )
    board_tmp_files = (
        [path for path in (BOARD_ROOT / "tmp").rglob("*") if path.is_file()]
        if (BOARD_ROOT / "tmp").exists()
        else []
    )
    add_check(
        checks,
        "S2-TMP-EMPTY",
        "artifact_closure",
        not board_tmp_files,
        [],
        [str(path) for path in board_tmp_files],
        BOARD_ROOT / "tmp",
    )
    builder_path = BOARD_ROOT / "code" / "build_board21_step2_static_inventory.py"
    builder_source = builder_path.read_text(encoding="utf-8")
    builder_tree = ast.parse(builder_source)
    forbidden_calls = {
        "subprocess.run",
        "subprocess.Popen",
        "os.system",
        "os.popen",
        "matlab.engine.start_matlab",
    }
    found_forbidden_calls = sorted(
        {
            call_name(node.func)
            for node in ast.walk(builder_tree)
            if isinstance(node, ast.Call) and call_name(node.func) in forbidden_calls
        }
    )
    forbidden_imports = sorted(
        {
            alias.name
            for node in ast.walk(builder_tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
            if alias.name.startswith("matlab") or alias.name == "subprocess"
        }
    )
    add_check(
        checks,
        "S2-NO-COMPUTE-LAUNCH-CODE",
        "process_boundary",
        not found_forbidden_calls
        and not forbidden_imports
        and '"-batch"' not in builder_source
        and "'-batch'" not in builder_source,
        "no MATLAB/process launch imports, calls, or -batch argument",
        {
            "forbidden_calls": found_forbidden_calls,
            "forbidden_imports": forbidden_imports,
            "batch_literal": "-batch" in builder_source,
        },
        builder_path,
    )
    report_text = REPORT.read_text(encoding="utf-8") if REPORT.is_file() else ""
    report_required_phrases = (
        "静态抽取与依赖审计完成",
        "公式正确命中为0",
        "表4-1四格保持“历史值”",
        "两类整体计算入口尚未唯一闭合",
        "MATLAB未运行",
    )
    add_check(
        checks,
        "S2-REPORT",
        "human_readable_evidence",
        REPORT.is_file()
        and sha256_file(REPORT) == REPORT_SHA256
        and all(phrase in report_text for phrase in report_required_phrases),
        {
            "sha256": REPORT_SHA256,
            "required_phrases": report_required_phrases,
        },
        {
            "sha256": sha256_file(REPORT) if REPORT.is_file() else "MISSING",
            "present_phrases": [
                phrase for phrase in report_required_phrases if phrase in report_text
            ],
        },
        REPORT,
    )

    success_present = []
    failure_present = []
    for name in FORMAL_OBJECT_NAMES:
        success = PROJECT_ROOT / "test" / name
        failure = PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name
        if os.path.lexists(success):
            success_present.append(str(success))
        if os.path.lexists(failure):
            failure_present.append(str(failure))
    add_check(
        checks,
        "S2-FORMAL-SUCCESS-BOUNDARY",
        "publication_boundary",
        not success_present,
        [],
        success_present,
        PROJECT_ROOT / "test",
    )
    add_check(
        checks,
        "S2-PREPUBLICATION-FAILURE-BOUNDARY",
        "publication_boundary",
        not failure_present,
        [],
        failure_present,
        PROJECT_ROOT / "test" / "00_失败尝试与候选路线",
    )
    board22 = find_named_entries(PROJECT_ROOT / "test", "板块22")
    add_check(
        checks,
        "S2-BOARD22-BOUNDARY",
        "publication_boundary",
        not board22,
        [],
        board22,
        PROJECT_ROOT / "test",
    )
    final_residual = process_snapshot()
    add_check(
        checks,
        "S2-RESIDUAL-PROCESSES",
        "process_boundary",
        not initial_residual and not final_residual,
        {"initial": [], "final": []},
        {"initial": initial_residual, "final": final_residual},
        "tasklist before and after static validation",
    )

    manifest_rows_out = artifact_manifest_rows()
    manifest_path = VALIDATION_ROOT / "step2_artifact_manifest.csv"
    write_csv(
        manifest_path,
        manifest_rows_out,
        ["relative_path", "size_bytes", "sha256"],
    )
    unique_manifest_paths = {row["relative_path"] for row in manifest_rows_out}
    expected_artifact_paths = set(EXPECTED_CODE_REPORT_PATHS)
    expected_artifact_paths.update(
        f"outputs/step2_static_inventory/{relative}"
        for relative in expected_inventory_paths
    )
    add_check(
        checks,
        "S2-ARTIFACT-MANIFEST",
        "artifact_closure",
        len(manifest_rows_out) == 83
        and len(unique_manifest_paths) == 83
        and unique_manifest_paths == expected_artifact_paths
        and all(
            sha256_file(BOARD_ROOT / row["relative_path"]) == row["sha256"]
            for row in manifest_rows_out
        ),
        {"count": 83, "paths": sorted(expected_artifact_paths)},
        {
            "row_count": len(manifest_rows_out),
            "unique_count": len(unique_manifest_paths),
            "extra": sorted(unique_manifest_paths - expected_artifact_paths),
            "missing": sorted(expected_artifact_paths - unique_manifest_paths),
        },
        manifest_path,
    )

    check_ids = [row["check_id"] for row in checks] + ["S2-CHECK-ID-UNIQUE"]
    add_check(
        checks,
        "S2-CHECK-ID-UNIQUE",
        "validation_integrity",
        len(check_ids) == len(set(check_ids)),
        len(check_ids),
        len(set(check_ids)),
        VALIDATION_ROOT,
    )
    checks_path = VALIDATION_ROOT / "checks.csv"
    write_csv(
        checks_path,
        checks,
        ["check_id", "category", "status", "expected", "actual", "evidence"],
    )
    passed_count = sum(row["status"] == "PASS" for row in checks)
    failed = [row for row in checks if row["status"] != "PASS"]
    validation_summary = {
        "schema_version": "BOARD21_STEP2_INDEPENDENT_VALIDATION_V2",
        "status": "PASS" if not failed else "FAIL",
        "check_count": len(checks),
        "passed_count": passed_count,
        "failed_count": len(failed),
        "failed_check_ids": [row["check_id"] for row in failed],
        "builder_imported": False,
        "matlab_executed": False,
        "inventory_file_count": len(inventory_files),
        "artifact_manifest_file_count": len(manifest_rows_out),
        "validation_output_manifest_file_count": 3,
        "validation_root_file_count": None,
        "validation_output_manifest_verified": False,
        "validation_output_postcondition_status": "PENDING",
        "energy_route_count": len(ENERGY_EXPECTED),
        "formula_4_45_match_count": 0,
        "formula_compliant_historical_match_count": 0,
        "numeric_but_formula_invalid_match_count": 2,
        "formal_success_directory_count": len(success_present),
        "prepublication_failure_directory_count": len(failure_present),
        "board22_named_root_count": len(board22),
        "initial_residual_target_process_count": len(initial_residual),
        "final_residual_target_process_count": len(final_residual),
        "scientific_status": "STATIC_AUDIT_COMPLETE_TABLE4_1_REMAINS_HISTORICAL",
    }
    validation_summary_path = VALIDATION_ROOT / "validation_summary.json"
    write_json(validation_summary_path, validation_summary)
    validation_output_manifest_path = (
        VALIDATION_ROOT / "validation_output_manifest.csv"
    )
    validation_output_targets = (
        checks_path,
        validation_summary_path,
        manifest_path,
    )
    preliminary_postcondition_ok, preliminary_postcondition_details = (
        write_validation_manifest_and_verify(
            validation_output_targets,
            validation_output_manifest_path,
        )
    )
    if preliminary_postcondition_ok:
        validation_summary.update(
            {
                "validation_root_file_count": 4,
                "validation_output_manifest_verified": True,
                "validation_output_postcondition_status": "PASS",
            }
        )
    else:
        validation_summary.update(
            {
                "status": "FAIL",
                "validation_root_file_count": sum(
                    (VALIDATION_ROOT / relative).is_file()
                    for relative in preliminary_postcondition_details[
                        "actual_entries"
                    ]
                ),
                "validation_output_manifest_verified": False,
                "validation_output_postcondition_status": "FAIL",
                "validation_output_postcondition_details": (
                    preliminary_postcondition_details
                ),
            }
        )
    write_json(validation_summary_path, validation_summary)
    final_postcondition_ok, final_postcondition_details = (
        write_validation_manifest_and_verify(
            validation_output_targets,
            validation_output_manifest_path,
        )
    )
    if not final_postcondition_ok:
        validation_summary.update(
            {
                "status": "FAIL",
                "validation_root_file_count": sum(
                    (VALIDATION_ROOT / relative).is_file()
                    for relative in final_postcondition_details["actual_entries"]
                ),
                "validation_output_manifest_verified": False,
                "validation_output_postcondition_status": "FAIL",
                "validation_output_postcondition_details": (
                    final_postcondition_details
                ),
            }
        )
        write_json(validation_summary_path, validation_summary)
        write_validation_manifest_and_verify(
            validation_output_targets,
            validation_output_manifest_path,
        )
        print(json.dumps(validation_summary, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(validation_summary, ensure_ascii=False, sort_keys=True))
    return (
        0
        if not failed
        and validation_summary["status"] == "PASS"
        and final_postcondition_ok
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
