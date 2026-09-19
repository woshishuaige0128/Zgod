#!/usr/bin/env python
"""生成图10硕士论文与当前文章差异的独立单文件HTML汇报。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping


CASE_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROOT = CASE_ROOT.parents[1]
DEFAULT_EVIDENCE = CASE_ROOT / "evaluation" / "final_evidence_summary" / "final_evidence_summary.json"
DEFAULT_PLOT_MANIFEST = (
    CASE_ROOT
    / "figures"
    / "final_delivery"
    / "图10_论文目标_历史候选_来源约束计算对比_生成清单.json"
)
DEFAULT_OUTPUT = DELIVERY_ROOT / "图10_硕士论文与当前文章差异汇报.html"

CURVE_ORDER = (
    "division1_original",
    "division1_craig_bampton",
    "division1_guyan",
    "division2_original",
    "division2_craig_bampton",
    "division2_guyan",
)
CURVE_NAMES = {
    "division1_original": "第一类划分—未缩聚原模型",
    "division1_craig_bampton": "第一类划分—Craig–Bampton缩聚",
    "division1_guyan": "第一类划分—Guyan缩聚",
    "division2_original": "第二类划分—未缩聚原模型",
    "division2_craig_bampton": "第二类划分—Craig–Bampton缩聚",
    "division2_guyan": "第二类划分—Guyan缩聚",
}
SOURCE_GROUP_NAMES = {
    "historical_mask_regression": "历史 lqr_2/lqr_3 掩膜",
    "archived_r01_r04_read_only_audit": "既有 R01–R04 冻结计算候选（未重算）",
    "coarse_gain_sweep": "增益比例粗扫候选",
    "historical_diagnostic_h05_h06": "历史诊断整束 H05/H06",
    "historical_diagnostic_h07": "能量源码补全诊断整束 H07",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def yes_no(value: Any) -> str:
    return "是" if bool(value) else "否"


def pass_badge(status: Any) -> str:
    normalized = str(status).upper()
    if normalized in {"PASS", "ELIGIBLE", "PRESENT", "COMPLETE"}:
        cls, label = "good", str(status)
    elif normalized in {"PENDING", "MISSING", "UNKNOWN"} or "PENDING" in normalized:
        cls, label = "warn", str(status)
    else:
        cls, label = "bad", str(status)
    return f'<span class="badge {cls}">{esc(label)}</span>'


def short_hash(value: str, length: int = 16) -> str:
    return value[:length] + "…" if len(value) > length else value


def image_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def group_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[str(candidate["source_group"])].append(candidate)
    result = []
    for group_name, rows in groups.items():
        result.append(
            {
                "source_group": group_name,
                "display_name": SOURCE_GROUP_NAMES.get(group_name, group_name),
                "candidate_count": len(rows),
                "strict_6of6_count": sum(int(row["strict_curve_pass_count"]) == 6 for row in rows),
                "strict_0of6_count": sum(int(row["strict_curve_pass_count"]) == 0 for row in rows),
                "topology_rejected_count": sum(
                    row["ranking_eligibility_status"] == "REJECTED_TOPOLOGY" for row in rows
                ),
                "best_curve_pass_count": max(int(row["strict_curve_pass_count"]) for row in rows),
            }
        )
    return result


def get_selected_rows(
    evidence: dict[str, Any], candidate_id: str
) -> dict[str, dict[str, Any]]:
    rows = {
        row["curve_id"]: row
        for row in evidence["curve_results"]
        if row["candidate_id"] == candidate_id
        and row["source_category"] == "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE"
    }
    if set(rows) != set(CURVE_ORDER):
        raise ValueError(f"所选候选的六曲线评价不完整：{sorted(rows)}")
    return rows


def get_historical_rows(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {
        row["curve_id"]: row
        for row in evidence["curve_results"]
        if row["source_category"] == "HISTORICAL_MAT_CANDIDATE"
    }
    if set(rows) != set(CURVE_ORDER):
        raise ValueError(f"历史MAT六曲线评价不完整：{sorted(rows)}")
    return rows


def find_first(payload: Any, names: Iterable[str]) -> Any:
    wanted = {name.casefold() for name in names}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).casefold() in wanted:
                return value
        for value in payload.values():
            found = find_first(value, names)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_first(value, names)
            if found is not None:
                return found
    return None


def matlab_verification_block(path: Path | None) -> tuple[str, dict[str, Any]]:
    if path is None:
        return (
            '<div class="callout warn"><strong>MATLAB独立复核尚未接入最终汇报。</strong>'
            "这会阻止本HTML被标记为最终交付。</div>",
            {"status": "PENDING"},
        )
    resolved = path.resolve()
    payload = load_json(resolved)
    status = find_first(payload, ("status", "overall_status", "verification_status")) or "UNKNOWN"
    point_count = find_first(
        payload,
        ("point_count", "compared_point_count", "grid_point_count", "total_point_count"),
    )
    rho_diff = find_first(
        payload,
        ("max_rho_abs_diff", "maximum_rho_absolute_difference", "rho_max_abs_diff"),
    )
    stable_diff = find_first(
        payload,
        (
            "stable_difference_count",
            "stable_mask_difference_count",
            "stable_diff_count",
            "stable_mismatch_count",
        ),
    )
    residual = find_first(
        payload,
        (
            "max_residual",
            "maximum_eigen_residual",
            "maximum_residual",
            "maximum_state_eigenpair_residual",
        ),
    )
    values = {
        "status": status,
        "point_count": point_count,
        "max_rho_abs_diff": rho_diff,
        "stable_difference_count": stable_diff,
        "max_residual": residual,
        "path": str(resolved),
        "sha256": sha256(resolved),
    }
    cells = [
        ("复核状态", pass_badge(status)),
        ("比较网格点", esc(point_count if point_count is not None else "见原始JSON")),
        ("最大谱半径绝对差", esc(rho_diff if rho_diff is not None else "见原始JSON")),
        ("稳定性判定差异点", esc(stable_diff if stable_diff is not None else "见原始JSON")),
        ("最大特征残差", esc(residual if residual is not None else "见原始JSON")),
    ]
    html_block = '<div class="metric-grid">' + "".join(
        f'<div class="metric"><span>{label}</span><strong>{value}</strong></div>'
        for label, value in cells
    ) + "</div>"
    return html_block, values


def render_group_table(groups: list[dict[str, Any]]) -> str:
    rows = []
    for group in groups:
        rows.append(
            "<tr>"
            f"<td>{esc(group['display_name'])}</td>"
            f"<td>{group['candidate_count']}</td>"
            f"<td>{group['best_curve_pass_count']}/6</td>"
            f"<td>{group['strict_6of6_count']}</td>"
            f"<td>{group['topology_rejected_count']}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_curve_table(
    plot_manifest: dict[str, Any],
    history_rows: dict[str, dict[str, Any]],
    selected_rows: dict[str, dict[str, Any]],
) -> str:
    plot_curves = {row["curve_id"]: row for row in plot_manifest["curves"]}
    rows = []
    for curve_id in CURVE_ORDER:
        plot_row = plot_curves[curve_id]
        history = history_rows[curve_id]
        selected = selected_rows[curve_id]
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{esc(CURVE_NAMES[curve_id])}</th>"
            f"<td>{plot_row['target_point_count']}</td>"
            f"<td>{history['candidate_boundary_point_count']}</td>"
            f"<td>{pass_badge(history['strict_curve_status'])}</td>"
            f"<td>{selected['candidate_boundary_point_count']}</td>"
            f"<td>{pass_badge(selected['strict_curve_status'])}</td>"
            f"<td>{yes_no(selected['ordered_exact_original'])}</td>"
            f"<td>{yes_no(selected['set_exact'])}</td>"
            f"<td>{yes_no(selected['start_endpoint_exact'])}/{yes_no(selected['end_endpoint_exact'])}</td>"
            f"<td>{float(selected['symmetric_hausdorff_steps']):.3f}</td>"
            f"<td>{selected['point_levenshtein_original']}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_evidence_files(
    evidence: dict[str, Any],
    evidence_path: Path,
    plot_manifest_path: Path,
    plot_manifest: dict[str, Any],
) -> str:
    entries = []
    for item in evidence["full_tree_audit"]["evidence_files"]:
        entries.append((item["path"], item["sha256"], "全树生成链审计"))
    entries.extend(
        [
            (
                str(evidence_path),
                sha256(evidence_path),
                "统一评价端证据汇总",
            ),
            (str(plot_manifest_path), sha256(plot_manifest_path), "最终对比图生成清单"),
            (
                plot_manifest["outputs"]["editable_csv"],
                plot_manifest["outputs"]["editable_csv_sha256"],
                "三层边界逐点可编辑数据",
            ),
            (
                plot_manifest["selected_strict_summary"],
                plot_manifest["selected_strict_summary_sha256"],
                "所选候选六曲线严格评价",
            ),
        ]
    )
    return "".join(
        "<tr>"
        f"<td><code>{esc(path)}</code></td>"
        f"<td><code>{esc(short_hash(hash_value))}</code></td>"
        f"<td>{esc(role)}</td>"
        "</tr>"
        for path, hash_value, role in entries
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-summary", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--plot-manifest", type=Path, default=DEFAULT_PLOT_MANIFEST)
    parser.add_argument("--independent-matlab-json", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evidence_path = args.evidence_summary.resolve()
    plot_manifest_path = args.plot_manifest.resolve()
    output_path = args.output.resolve()
    if not evidence_path.is_file() or not plot_manifest_path.is_file():
        raise FileNotFoundError(f"缺少汇报输入：{evidence_path} 或 {plot_manifest_path}")

    evidence = load_json(evidence_path)
    plot_manifest = load_json(plot_manifest_path)
    if evidence["status"] != "PASS":
        raise RuntimeError("最终证据汇总未通过")
    if not plot_manifest["active_and_rebuilt_pdf_byte_identical"]:
        raise RuntimeError("当前文章活跃图件与论文矢量重建图件不一致")
    if plot_manifest["strict_overall_status"] != "FAIL":
        raise RuntimeError("本报告模板用于诚实汇报严格未命中，输入状态异常")

    selected = plot_manifest["selected_candidate"]
    selected_id = selected["candidate_id"]
    history_rows = get_historical_rows(evidence)
    selected_rows = get_selected_rows(evidence, selected_id)
    groups = group_candidates(evidence["candidate_summaries"])
    group_table = render_group_table(groups)
    curve_table = render_curve_table(plot_manifest, history_rows, selected_rows)
    evidence_table = render_evidence_files(
        evidence, evidence_path, plot_manifest_path, plot_manifest
    )
    matlab_block, matlab_values = matlab_verification_block(args.independent_matlab_json)

    png_path = Path(plot_manifest["outputs"]["png"]).resolve()
    if not png_path.is_file():
        raise FileNotFoundError(png_path)
    embedded_image = image_data_uri(png_path)
    current_hash = plot_manifest["active_article_pdf_sha256"]
    target_hash = plot_manifest["rebuilt_target_pdf_sha256"]
    counts = evidence["counts"]
    audit = evidence["full_tree_audit"]
    h07_status = evidence["optional_evidence"]["H07"]["status"]
    report_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>图10｜硕士论文与当前文章差异汇报</title>
  <style>
    :root {{
      --ink:#16202a; --muted:#5c6875; --paper:#f7f8fa; --card:#ffffff;
      --line:#d8dee6; --blue:#4477aa; --red:#c23b55; --green:#177a52;
      --amber:#9a6514; --soft-blue:#edf3fa; --soft-red:#fbecef; --soft-green:#eaf6f1;
      --shadow:0 12px 32px rgba(25,38,52,.08);
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:"Noto Sans SC","Microsoft YaHei",Arial,sans-serif; line-height:1.72; }}
    main {{ width:min(1160px, calc(100% - 36px)); margin:0 auto 70px; }}
    .hero {{ margin:28px auto 18px; padding:38px 42px; border-radius:22px; color:white; background:linear-gradient(135deg,#13283b 0%,#244e70 62%,#3c6d91 100%); box-shadow:var(--shadow); }}
    .eyebrow {{ margin:0 0 9px; color:#cde2f1; font-size:.82rem; letter-spacing:.12em; font-weight:700; }}
    h1 {{ margin:.08em 0 .25em; font-size:clamp(1.9rem,4.5vw,3.3rem); line-height:1.2; letter-spacing:-.03em; }}
    .hero .lead {{ max-width:900px; margin:12px 0 0; font-size:1.08rem; color:#eef6fb; }}
    .status-line {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:22px; }}
    .pill {{ padding:7px 12px; border:1px solid rgba(255,255,255,.26); border-radius:999px; background:rgba(255,255,255,.1); font-size:.86rem; }}
    nav {{ position:sticky; top:0; z-index:10; margin:0 0 18px; padding:10px 14px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.96); box-shadow:0 5px 18px rgba(25,38,52,.07); backdrop-filter:blur(8px); }}
    nav ul {{ display:flex; flex-wrap:wrap; gap:8px 18px; margin:0; padding:0; list-style:none; }}
    nav a {{ color:#284e70; text-decoration:none; font-weight:700; font-size:.88rem; }}
    section {{ margin:18px 0; padding:28px 30px; border:1px solid var(--line); border-radius:18px; background:var(--card); box-shadow:0 7px 22px rgba(25,38,52,.045); }}
    h2 {{ margin:0 0 16px; font-size:1.55rem; line-height:1.3; letter-spacing:-.015em; }}
    h3 {{ margin:26px 0 10px; font-size:1.12rem; }}
    p {{ margin:.7em 0; }}
    .summary-grid,.metric-grid,.two-col {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
    .summary-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); margin-top:18px; }}
    .summary-card,.metric {{ min-width:0; padding:17px; border:1px solid var(--line); border-radius:14px; background:#fbfcfd; }}
    .summary-card strong,.metric strong {{ display:block; margin-top:5px; font-size:1.22rem; line-height:1.28; overflow-wrap:anywhere; }}
    .summary-card span,.metric span {{ color:var(--muted); font-size:.84rem; }}
    .verdict {{ border-left:5px solid var(--blue); background:var(--soft-blue); }}
    .verdict.bad {{ border-left-color:var(--red); background:var(--soft-red); }}
    .callout {{ margin:15px 0; padding:15px 17px; border-left:5px solid var(--blue); border-radius:10px; background:var(--soft-blue); }}
    .callout.good {{ border-left-color:var(--green); background:var(--soft-green); }}
    .callout.bad {{ border-left-color:var(--red); background:var(--soft-red); }}
    .callout.warn {{ border-left-color:var(--amber); background:#fff7e7; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:.75rem; font-weight:800; white-space:nowrap; }}
    .badge.good {{ color:#0b6542; background:#dcefe8; }}
    .badge.bad {{ color:#a52540; background:#f8dfe5; }}
    .badge.warn {{ color:#7b4e08; background:#f8ebc9; }}
    .table-scroll {{ max-width:100%; overflow-x:auto; border:1px solid var(--line); border-radius:12px; }}
    table {{ width:100%; min-width:820px; border-collapse:collapse; font-size:.88rem; }}
    th,td {{ padding:10px 11px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    thead th {{ position:sticky; top:0; color:#f5f9fc; background:#274b68; white-space:nowrap; }}
    tbody tr:last-child th,tbody tr:last-child td {{ border-bottom:0; }}
    tbody tr:nth-child(even) {{ background:#fafbfd; }}
    code {{ font-family:"Cascadia Mono",Consolas,monospace; font-size:.82em; overflow-wrap:anywhere; }}
    figure {{ margin:18px 0 5px; break-inside:avoid; }}
    figure img {{ display:block; width:100%; height:auto; border:1px solid var(--line); background:white; }}
    figcaption {{ margin-top:10px; color:var(--muted); font-size:.88rem; }}
    ol.steps,ul.clean {{ padding-left:1.25rem; }}
    ol.steps li,ul.clean li {{ margin:.62em 0; }}
    .flow {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:16px 0; }}
    .flow div {{ position:relative; padding:14px 13px; border-radius:12px; border:1px solid var(--line); background:#fbfcfe; }}
    .flow b {{ display:block; margin-bottom:4px; color:#244f70; }}
    details {{ margin:12px 0; border:1px solid var(--line); border-radius:12px; background:#fcfdfe; }}
    summary {{ padding:13px 15px; cursor:pointer; font-weight:800; }}
    details > div {{ padding:0 15px 15px; }}
    .footer {{ color:var(--muted); text-align:center; font-size:.82rem; }}
    @media (max-width:850px) {{
      .summary-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .flow {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    }}
    @media (max-width:600px) {{
      main {{ width:min(100% - 20px,1160px); margin-bottom:35px; }}
      .hero {{ margin-top:10px; padding:26px 20px; border-radius:16px; }}
      nav {{ position:static; border-radius:12px; }}
      nav ul {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px 12px; }}
      section {{ padding:22px 17px; border-radius:14px; }}
      .summary-grid,.metric-grid,.two-col,.flow {{ grid-template-columns:minmax(0,1fr); }}
      h2 {{ font-size:1.35rem; }}
      .table-scroll {{ scrollbar-width:thin; }}
    }}
    @page {{ size:A4; margin:13mm; }}
    @media print {{
      :root {{ --paper:#fff; --card:#fff; --shadow:none; }}
      body {{ background:#fff; font-size:9.5pt; line-height:1.5; print-color-adjust:exact; -webkit-print-color-adjust:exact; }}
      main {{ width:100%; margin:0; }}
      .hero {{ margin:0 0 8mm; padding:9mm; border-radius:0; box-shadow:none; }}
      nav {{ display:none; }}
      section {{ margin:0 0 7mm; padding:6mm; border-radius:0; box-shadow:none; break-inside:auto; }}
      h2,h3 {{ break-after:avoid-page; }}
      .summary-card,.metric,.callout,figure,details {{ break-inside:avoid-page; }}
      .table-scroll {{ overflow:visible; border:0; }}
      table {{ min-width:0; font-size:7.2pt; }}
      th,td {{ padding:4px 5px; }}
      thead th {{ position:static; }}
      details > div {{ display:block; }}
      .footer {{ margin-top:5mm; }}
    }}
  </style>
</head>
<body>
<main>
  <header class="hero" id="top">
    <p class="eyebrow">RHTS · 稳定域证据链 · 2026-09-01</p>
    <h1>图10：硕士论文与当前文章差异汇报</h1>
    <p class="lead"><strong>结论先行：</strong>当前文章实际引用的 <code>fig10_stability_domain.pdf</code> 与按硕士论文六条矢量边界重建的PDF逐字节相同，因此两者在绘图层面没有差异；但现有资料仍无法从结构矩阵和控制参数重新计算出这六条边界。来源受约束的搜索没有一个候选通过六曲线严格门，科学状态保持“绘图级复现通过、计算级精准复现未通过”。</p>
    <div class="status-line">
      <span class="pill">文章活跃图件：逐字节一致</span>
      <span class="pill">论文目标：6条 / 386点</span>
      <span class="pill">来源约束计算：0/6严格命中</span>
      <span class="pill">需用户操作：无</span>
    </div>
  </header>

  <nav aria-label="报告目录"><ul>
    <li><a href="#summary">一页结论</a></li><li><a href="#identity">对象身份</a></li>
    <li><a href="#concepts">必要概念</a></li><li><a href="#method">方法</a></li>
    <li><a href="#results">逐项结果</a></li><li><a href="#differences">差异来源</a></li>
    <li><a href="#evidence">证据边界</a></li><li><a href="#actions">后续行动</a></li>
  </ul></nav>

  <section id="summary">
    <h2>一页结论</h2>
    <div class="two-col">
      <div class="callout good"><strong>已经闭合：</strong>硕士论文图4-4/图4-5的六条边界共386个有序点，已成为当前文章活跃图件；两份PDF的SHA-256完全相同。</div>
      <div class="callout bad"><strong>没有闭合：</strong>现有源码与矩阵不能生成与386个目标点严格一致的六条计算边界；任何“看起来接近”的候选都不能升级为计算级复现。</div>
    </div>
    <div class="summary-grid">
      <div class="summary-card"><span>全树只读审计</span><strong>{audit['scan_file_count']} / {audit['source_protection_match_count']}</strong><small>文件哈希保持一致</small></div>
      <div class="summary-card"><span>当前文章与目标PDF</span><strong>相同</strong><small>{esc(short_hash(current_hash))}</small></div>
      <div class="summary-card"><span>历史MAT严格命中</span><strong>2 / 6</strong><small>仅两条未缩聚原模型</small></div>
      <div class="summary-card"><span>所选计算候选</span><strong>{selected['strict_curve_pass_count']} / 6</strong><small>{esc(selected_id)}</small></div>
    </div>
    <p>这意味着文章现在显示的线条是正确的“论文图形资产”，但它的身份仍是<strong>绘图级矢量复刻</strong>。要把身份升级为“计算级复现”，必须从同一套结构、缩聚、LQR、时滞和边界提取合同出发，重新得到六条完全相同的有序点列；本轮没有达到该门槛。</p>
  </section>

  <section id="identity">
    <h2>对象身份：为什么“没有图形差异”仍不等于“计算已经复现”</h2>
    <div class="table-scroll"><table>
      <thead><tr><th>对象</th><th>当前身份</th><th>已验证关系</th><th>不能据此声称</th></tr></thead>
      <tbody>
        <tr><th>硕士论文图4-4、图4-5</th><td>语义与目标曲线来源</td><td>六条边界72/69/67/69/56/53点，共386点</td><td>论文PDF本身不包含完整可执行控制参数合同</td></tr>
        <tr><th>当前文章 <code>fig10_stability_domain.pdf</code></th><td>活跃排版资产</td><td>与矢量边界重建PDF逐字节一致；SHA-256均为 <code>{esc(current_hash)}</code></td><td>图件相同不证明计算生成链相同</td></tr>
        <tr><th>历史 <code>lqr_2.mat</code>/<code>lqr_3.mat</code></th><td>历史绘图掩膜</td><td>两条Original严格相同，四条缩聚曲线不同</td><td>它们不是论文最终六曲线的完整计算合同</td></tr>
        <tr><th>本轮来源约束候选</th><td>目标引导的校准计算复现</td><td>盲算与目标评价隔离；全部候选保留严格失败结果</td><td>不得称为已恢复作者原始程序或精准复现</td></tr>
      </tbody>
    </table></div>
  </section>

  <section id="concepts">
    <h2>理解结果所需的四个概念</h2>
    <div class="flow">
      <div><b>稳定掩膜</b>在31×67个双时滞网格点上逐点判断最大特征根模是否小于1；它是“整张地图”。</div>
      <div><b>边界曲线</b>从稳定掩膜外缘提取的有序格点；它是“地图边界线”，不是完整地图。</div>
      <div><b>绘图级复现</b>能够逐点画回论文中的线，但不一定知道这些点最初怎样算出来。</div>
      <div><b>计算级复现</b>从模型、控制器和时滞方程开始重算，并得到完全相同的掩膜与边界。</div>
    </div>
    <p>严格门要求每条曲线同时满足：点数相同、有序点列相同、无序点集相同、首尾端点相同、对称Hausdorff距离为0、点序编辑距离为0，以及采样步到毫秒的换算误差不超过规定容差。任一项失败，该曲线即为失败；六条必须同时通过。</p>
  </section>

  <section id="method">
    <h2>本轮怎样执行，为什么结果可信</h2>
    <ol class="steps">
      <li><strong>穷尽当前交付树。</strong>对 <code>D:\\JZ_PhD\\10_论文_Papers\\Li\\RHTS</code> 内6135个相关文件进行文件名、源码、MAT字段、MLX/SLX解包、ZIP成员和写入链审计。源文件前后哈希6135/6135一致。</li>
      <li><strong>锁定缺口。</strong>找到了部分谱半径脚本、历史掩膜和最终曲线追踪数据，但没有找到“六套模型与控制参数 → 六个掩膜 → 六条最终边界”的完整程序。</li>
      <li><strong>建立目标防火墙。</strong>盲算核心只能读取来源矩阵与合同清单，禁止读取 <code>plotted_data.mat</code>、目标CSV和目标PDF；计算结束后，评价器才读取目标并打分。</li>
      <li><strong>不重复旧算例。</strong>R01–R04直接审计冻结结果；新搜索只覆盖有源码依据的增益比例、历史DARE/无LQR诊断与能量参数补全诊断。</li>
      <li><strong>严格验收并保留拓扑门。</strong>多连通分量、全网格稳定等非判别性结果被明确拒绝；没有降低阈值，也没有用“最接近”替代“完全相同”。</li>
      <li><strong>独立求解器复核。</strong>对最终保留的非拓扑异常候选，用独立MATLAB路径逐点比较谱半径与稳定判断，结果见下方。</li>
    </ol>
    {matlab_block}
  </section>

  <section id="results">
    <h2>逐项结果</h2>
    <h3>1. 候选家族结果</h3>
    <div class="table-scroll"><table>
      <thead><tr><th>候选家族</th><th>候选数</th><th>家族最佳</th><th>六曲线全通过</th><th>拓扑拒绝</th></tr></thead>
      <tbody>{group_table}</tbody>
    </table></div>
    <div class="callout bad"><strong>统一结论：</strong>纳入最终汇总的来源约束计算曲线中，严格通过曲线数为 <strong>{counts['strict_pass_source_constrained_calculation_curve_result_count']}</strong>；没有任何一个计算候选六条全通过。H07状态为 {pass_badge(h07_status)}。</div>

    <h3>2. 六条曲线逐项严格指标</h3>
    <div class="table-scroll"><table>
      <thead><tr><th>曲线</th><th>目标点</th><th>历史点</th><th>历史状态</th><th>计算点</th><th>计算状态</th><th>有序完全相同</th><th>点集完全相同</th><th>首/尾端点相同</th><th>Hausdorff（步）</th><th>编辑距离</th></tr></thead>
      <tbody>{curve_table}</tbody>
    </table></div>

    <h3>3. 图形对比</h3>
    <figure>
      <img src="{embedded_image}" alt="硕士论文与当前文章目标、历史MAT掩膜和来源约束计算候选的六面板稳定域对比图">
      <figcaption>黑色实线为硕士论文目标与当前文章活跃图件，两者完全重合；红色虚线为历史MAT边界；蓝色点划线为评价端选出的拓扑合格、距离最小的来源约束计算候选。蓝线仍为严格0/6，图形仅用于展示差距，不是成功证书。</figcaption>
    </figure>
  </section>

  <section id="differences">
    <h2>差异究竟来自哪里</h2>
    <div class="table-scroll"><table>
      <thead><tr><th>技术环节</th><th>论文/文章需要的唯一合同</th><th>当前可用材料</th><th>对结果的影响</th><th>状态</th></tr></thead>
      <tbody>
        <tr><th>模型维数</th><td>文章叙述为两类划分下Guyan 6维、Craig–Bampton 12维</td><td>可闭合的现有包为第一类6/9维、第二类5/8维</td><td>系统矩阵阶数和模态内容直接改变特征根</td><td>{pass_badge('MISSING')}</td></tr>
        <tr><th>作动器与保留自由度</th><td>每类划分需要唯一通道映射</td><td>第二类在现有脚本中存在 ψ1/ψ6 与 ψ1/ψ11 等冲突路线</td><td>反馈注入位置不同，六条边界整体移动</td><td>{pass_badge('AMBIGUOUS')}</td></tr>
        <tr><th>LQR合同</th><td>唯一CARE/DARE、Q、R和增益</td><td>作者脚本、论文表达和能量脚本存在多套参数</td><td>闭环极点位置和时滞裕度改变</td><td>{pass_badge('AMBIGUOUS')}</td></tr>
        <tr><th>反馈相对时滞矩阵H的位置</th><td>必须唯一确定反馈在H内或H外</td><td>硕士论文/部分主程序为H外，小论文表达为H内</td><td>特征方程结构变化，不是简单缩放</td><td>{pass_badge('CONFLICT')}</td></tr>
        <tr><th>离散化与输入语义</th><td>唯一ZOH/Tustin、广义力/加速度输入合同</td><td>R01–R04已覆盖主要2×2组合；加速度路线出现全网格稳定</td><td>全稳定矩形没有边界辨识力，不能据此选轴</td><td>{pass_badge('TESTED_FAIL')}</td></tr>
        <tr><th>采样与边界提取</th><td>1/1024 s；31×67；8连通、无孔、可见开边界</td><td>评价器与MATLAB辅助程序已固定并回归</td><td>该环节已锁定，不再用改变提取规则迁就目标</td><td>{pass_badge('PASS')}</td></tr>
      </tbody>
    </table></div>
    <p>最关键的缺口不是“再调一个增益”，而是缺少与文章表述一致的两类12维Craig–Bampton装配矩阵、载荷映射和唯一控制参数合同。没有这些来源证据，继续扩大无约束参数搜索只会增加拟合自由度，不能提高历史可解释性。</p>
  </section>

  <section id="evidence">
    <h2>证据边界与可复核入口</h2>
    <div class="callout good"><strong>可以写入结论：</strong>当前文章活跃图件与硕士论文目标在绘图层面一致；历史MAT只有两条Original严格一致；来源受约束的计算搜索没有得到六曲线精准命中。</div>
    <div class="callout bad"><strong>不能写入结论：</strong>不能把当前图件称为从文章模型重新计算得到；不能把所选“最接近”候选称为作者原始合同；不能用单个端点相同替代386点的严格验收。</div>
    <div class="table-scroll"><table>
      <thead><tr><th>证据文件</th><th>SHA-256（前16位）</th><th>作用</th></tr></thead>
      <tbody>{evidence_table}</tbody>
    </table></div>
    <details><summary>哈希与标签的含义</summary><div><p>SHA-256用于证明报告引用的文件没有在汇总过程中被悄然替换。标签“目标引导的校准计算复现”说明目标只在计算完成后的评价阶段使用；它不等价于“作者历史计算合同已恢复”。</p></div></details>
  </section>

  <section id="actions">
    <h2>当前状态、风险与下一步</h2>
    <div class="two-col">
      <div class="verdict callout"><strong>本板块已经完成的目标</strong><ul class="clean"><li>全RHTS树生成链审计与源文件保护</li><li>盲算/评价防火墙与严格六曲线验收</li><li>既有R01–R04只读复核及新诊断候选搜索</li><li>可编辑对比代码、逐点CSV、矢量PDF和600 dpi PNG</li><li>本独立单文件HTML与视觉/打印验收</li></ul></div>
      <div class="verdict bad callout"><strong>仍未获得的科学对象</strong><ul class="clean"><li>作者最终六掩膜的完整生成程序</li><li>文章声称的两类12维Craig–Bampton数值装配包</li><li>唯一的Q/R/K、反馈位置和作动器映射</li><li>六条边界全部严格命中的计算合同</li></ul></div>
    </div>
    <h3>建议的下一步</h3>
    <ol class="steps">
      <li><strong>首选：</strong>查找作者当时未交付的MATLAB工作区、自动保存目录、外置硬盘或其他计算机备份。验收标准是找到能直接写出六个最终掩膜或 <code>lqr_2/lqr_3</code> 的有效程序。</li>
      <li><strong>次选：</strong>由论文作者确认两类12维Craig–Bampton矩阵、作动器通道、Q/R/K和H内外位置。确认后重新建立来源合同并盲算；六条曲线仍按零容差门验收。</li>
      <li><strong>不建议：</strong>在缺少新增来源证据时继续扩大自由参数、修改稳定阈值或更换边界提取规则。这些做法会提高拟合能力，却不能证明历史真实性。</li>
    </ol>
    <p><strong>当前无需Doctor Bego作出立即决定。</strong>本报告已经把可以使用的文章图件、不能升级的科学身份和未来真正有价值的证据需求分开。</p>
  </section>

  <section aria-label="通俗回顾">
    <h2>通俗回顾</h2>
    <p>现在的情况像是：我们有一张与毕业论文完全相同的“最终地图”，也找到了几张旧地图和一些计算路线，但丢失了画出最终地图的那套完整导航程序。我们把所有现有路线都按同一规则重新跑或复核，没有一条能把六段边界全部画对。因此，当前文章可以继续使用这张经过逐点验收的图，但必须把它称为绘图级复刻；只有找回缺失程序或补齐由作者确认的关键矩阵和控制参数后，才有资格再次挑战计算级复现。</p>
  </section>

  <p class="footer">生成时间：{esc(report_time)} ｜ 证据汇总：<code>{esc(short_hash(evidence['canonical_payload_sha256']))}</code> ｜ HTML为UTF-8独立单文件，无网络依赖。</p>
</main>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8", newline="\n")
    result = {
        "schema_version": "FIG10_FINAL_REPORT_GENERATION_V1",
        "status": "PASS",
        "report": str(output_path),
        "report_sha256": sha256(output_path),
        "report_bytes": output_path.stat().st_size,
        "embedded_png": str(png_path),
        "embedded_png_sha256": sha256(png_path),
        "selected_candidate_id": selected_id,
        "selected_candidate_strict_curve_pass_count": selected["strict_curve_pass_count"],
        "active_and_target_pdf_sha256": current_hash,
        "independent_matlab": matlab_values,
        "external_resource_count_expected": 0,
        "embedded_image_count_expected": 1,
    }
    result_path = output_path.with_name(output_path.stem + "_生成清单.json")
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result["generation_manifest"] = str(result_path)
    result["generation_manifest_sha256"] = sha256(result_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
