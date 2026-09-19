#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤8G最终封存独立验收器。

本脚本只读取既有科学输出；唯一写入位置为规范包内
``验证记录/步骤8G最终封存验收``。科学结论固定为计算复现失败，
封存门只裁决证据是否完整、同源、可审计。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
BOARD = HERE.parent.parent
PROJECT = next(p for p in HERE.parents if (p / "figure").is_dir() and (p / "test").is_dir())
CANON = BOARD / "outputs" / "step8g_图4-4图4-5最终中文失败审计包"
MIRROR = PROJECT / "figure" / "第4章_缩聚对试验稳定性的影响" / "图4-4与图4-5_完整数值复现审计_未通过"
OUT = CANON / "验证记录" / "步骤8G最终封存验收"

EXPECTED_SOURCES = {
    PROJECT.parent / "梁禹手稿.pdf": "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1",
    PROJECT / "figure/第4章_缩聚对试验稳定性的影响/原始来源副本/第一类划分最终绘图数据_lqr_2.mat": "9B08117CEA7A9DF95D60C4300F3BDCB515765209CD03162114F0436C5094A4C4",
    PROJECT / "figure/第4章_缩聚对试验稳定性的影响/原始来源副本/第二类划分最终绘图数据_lqr_3.mat": "69344E2E703AFE3BDFC1FA6DA133D36E450299B774C085ECE3252BCB18BDDEC1",
    PROJECT / "figure/第4章_缩聚对试验稳定性的影响/原始来源副本/原始绘图脚本_huitu_2.m": "85CB7D5300F3F820AFA80926B76F0430718709BD55722F45486F2F8B9848D1BC",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


checks = []


def check(name: str, ok: bool, actual, expected, detail=""):
    checks.append({"检查项": name, "状态": "PASS" if ok else "FAIL",
                   "实际值": str(actual), "预期值": str(expected), "说明": detail})


def required_files():
    rels = [
        "README.md", "图4-4图4-5最终科学裁决报告.md", "对象状态更新.csv",
        "可复现代码/源码映射.csv",
        "计算结果/最终裁决/24候选与六条论文目标逐项裁决.csv",
        "计算结果/最终裁决/8行同候选整图级裁决.csv",
        "计算结果/最终裁决/4行同候选六曲线全局裁决.csv",
        "计算结果/最终裁决/步骤8F计算候选裁决摘要.json",
        "计算结果/全网格双求解器验证/验证摘要.json",
        "验证记录/步骤8F独立验收/步骤8F独立验收摘要.json",
        "验证记录/论文矢量目标验收/逐点验收摘要.json",
    ]
    missing = [r for r in rels if not (CANON / r).is_file()]
    check("规范包必需文件", not missing, len(rels) - len(missing), len(rels), ";".join(missing))


def source_mirrors():
    mapping = rows(CANON / "可复现代码/源码映射.csv")
    check("源码映射行数", len(mapping) == 15, len(mapping), 15)
    bad = []
    for r in mapping:
        mirror = CANON / "可复现代码" / r.get("中文文件名", "")
        authority = PROJECT / r.get("权威源码项目相对路径", "")
        if not mirror.is_file() or not authority.is_file() or sha(mirror) != sha(authority):
            bad.append(r.get("顺序", "?"))
    check("15份源码镜像与权威源码逐字节同源", not bad, 15 - len(bad), 15, "失败序号=" + ",".join(bad))


def data_counts():
    targets = list((CANON / "论文矢量目标").glob("*.csv"))
    check("论文目标CSV", len(targets) == 6, len(targets), 6)
    data = CANON / "计算结果/候选掩膜与边界"
    masks = list(data.rglob("*掩膜*.csv")) if data.exists() else []
    bounds = list(data.rglob("*边界*.csv")) if data.exists() else []
    check("候选与历史掩膜", len(masks) == 30, len(masks), 30)
    check("候选与历史边界", len(bounds) == 30, len(bounds), 30)
    for rel, n in [("24候选与六条论文目标逐项裁决.csv", 24),
                   ("8行同候选整图级裁决.csv", 8),
                   ("4行同候选六曲线全局裁决.csv", 4)]:
        got = len(rows(CANON / "计算结果/最终裁决" / rel))
        check(rel, got == n, got, n)


def scientific_summaries():
    e = json.loads((CANON / "计算结果/全网格双求解器验证/验证摘要.json").read_text(encoding="utf-8-sig"))
    vals = {x["gate"]: x for x in e.get("checks", [])}
    check("步骤8E全门通过", e.get("status") == "PASS" and not e.get("failures"), e.get("status"), "PASS")
    check("步骤8E固定键数", vals.get("49,848固定键", {}).get("value") == "49848", vals.get("49,848固定键", {}).get("value"), 49848)
    check("步骤8E总根数", str(vals.get("根数与总数", {}).get("value", "")).startswith("3356432/mismatch=0"), vals.get("根数与总数", {}).get("value"), "3356432/mismatch=0")
    f = json.loads((CANON / "计算结果/最终裁决/步骤8F计算候选裁决摘要.json").read_text(encoding="utf-8-sig"))
    check("步骤8F候选组与点数", f.get("candidate_group_count") == 24 and f.get("candidate_point_count") == 49848,
          f"{f.get('candidate_group_count')}/{f.get('candidate_point_count')}", "24/49848")
    check("步骤8F完整计算复现数为零", f.get("complete_reproduction_exact_candidate_count") == 0 and not f.get("all_six_targets_completely_reproduced"),
          f.get("complete_reproduction_exact_candidate_count"), 0)
    check("步骤8F科学裁决失败", str(f.get("overall_gate", "")).startswith("FAIL_"), f.get("overall_gate"), "FAIL_*")
    vt = json.loads((CANON / "验证记录/论文矢量目标验收/逐点验收摘要.json").read_text(encoding="utf-8-sig"))
    check("论文矢量目标仅绘图级通过", vt.get("overall_status") == "PASS" and vt.get("evidence_level") == "PLOT_LEVEL_VECTOR_TRACE_ONLY" and vt.get("calculation_reproduction") is False,
          f"{vt.get('overall_status')}/{vt.get('evidence_level')}/{vt.get('calculation_reproduction')}", "PASS/PLOT_LEVEL_VECTOR_TRACE_ONLY/false")


def figures_and_format():
    pdfs = list((CANON / "PDF结果").rglob("*.pdf"))
    pngs = list((CANON / "PNG结果").rglob("*.png"))
    check("PDF总数", len(pdfs) == 6, len(pdfs), 6)
    check("PNG总数", len(pngs) == 6, len(pngs), 6)
    check("比较图PDF/PNG", sum("计算候选" in str(p) for p in pdfs) == 4 and sum("计算候选" in str(p) for p in pngs) == 4, "PDF/PNG", "4/4")
    check("目标复刻PDF/PNG", sum("论文矢量" in str(p) for p in pdfs) == 2 and sum("论文矢量" in str(p) for p in pngs) == 2, "PDF/PNG", "2/2")
    bad_pdf = [p.name for p in pdfs if p.read_bytes()[:5] != b"%PDF-"]
    bad_png = [p.name for p in pngs if p.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"]
    check("PDF文件签名", not bad_pdf, len(pdfs) - len(bad_pdf), len(pdfs), ";".join(bad_pdf))
    check("PNG文件签名", not bad_png, len(pngs) - len(bad_png), len(pngs), ";".join(bad_png))


def labels_and_sources():
    index_rows = rows(PROJECT / "test/00_总索引与复现规则/全部对象总索引.csv")
    selected = [r for r in index_rows if r.get("对象ID") in {"F4-4", "F4-5"}]
    check("总索引F4-4/F4-5保持绘图级", len(selected) == 2 and all(r.get("当前证据等级") == "绘图级复现" for r in selected),
          ";".join(f"{r.get('对象ID')}={r.get('当前证据等级')}" for r in selected), "两行均为绘图级复现")
    success_dirs = [PROJECT / r["成功文件夹"] for r in selected if r.get("成功文件夹")]
    existing = [str(p) for p in success_dirs if p.exists()]
    check("正式成功目录不存在", not existing, len(existing), 0, ";".join(existing))
    bad_lines = []
    for p in CANON.rglob("*"):
        if p.suffix.lower() not in {".md", ".json", ".csv", ".txt"} or OUT in p.parents:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
            compact = line.replace(" ", "")
            positive = any(x in compact for x in ("计算级复现通过", "完整计算复现通过", "计算级复现成功", "完整计算复现成功"))
            negated = any(x in compact for x in ("未通过", "不通过", "失败", "不得", "不是", "不声称", "不存在", "不自动等于"))
            if positive and not negated:
                bad_lines.append(f"{p.relative_to(CANON)}:{i}")
    check("无计算级成功声明", not bad_lines, len(bad_lines), 0, ";".join(bad_lines))
    bad_sources = []
    for path, expected in EXPECTED_SOURCES.items():
        if not path.is_file() or sha(path) != expected:
            bad_sources.append(str(path))
    check("论文及三个原始来源哈希不变", not bad_sources, 4 - len(bad_sources), 4, ";".join(bad_sources))


def tree_hashes(root: Path, excluded_prefix: Path | None = None):
    ans = {}
    for p in root.rglob("*"):
        if not p.is_file() or (excluded_prefix and excluded_prefix in p.parents):
            continue
        ans[p.relative_to(root).as_posix()] = sha(p)
    return ans


def mirror_and_processes():
    if not MIRROR.is_dir():
        check("canonical与figure镜像逐文件一致", False, "镜像不存在", "逐文件相同")
    else:
        a = tree_hashes(CANON, OUT)
        b = tree_hashes(MIRROR, MIRROR / "验证记录/步骤8G最终封存验收")
        diff = sorted(set(a) ^ set(b) | {k for k in set(a) & set(b) if a[k] != b[k]})
        check("canonical与figure镜像逐文件一致", not diff, f"canonical={len(a)},mirror={len(b)},diff={len(diff)}", "diff=0", ";".join(diff[:20]))
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "Get-Process matlab,python,pythonw -ErrorAction SilentlyContinue | Select-Object Id,ProcessName | ConvertTo-Csv -NoTypeInformation"],
                        text=True, capture_output=True, encoding="utf-8", errors="replace")
    proc_rows = list(csv.DictReader(ps.stdout.splitlines())) if ps.stdout.strip() else []
    names = [f"{r.get('ProcessName')}:{r.get('Id')}" for r in proc_rows if int(r.get("Id", -1)) != os.getpid()]
    check("无MATLAB/Python/PythonW残留", not names, ",".join(names), "无")


def write_results():
    OUT.mkdir(parents=True, exist_ok=True)
    failed = [x for x in checks if x["状态"] == "FAIL"]
    summary = {
        "schema_version": "board20-step8g-final-v1",
        "package_seal_status": "PASS" if not failed else "FAIL",
        "scientific_reproduction_status": "FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION",
        "plot_level_reproduction_status": "PASS",
        "scientific_failure_is_not_packaging_failure": True,
        "check_count": len(checks), "pass_count": len(checks) - len(failed), "fail_count": len(failed),
        "canonical": str(CANON), "figure_mirror": str(MIRROR),
    }
    with (OUT / "步骤8G最终封存验收检查.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0])); w.writeheader(); w.writerows(checks)
    (OUT / "步骤8G最终封存验收摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 步骤8G最终封存验收报告", "", f"- 封存验收：**{summary['package_seal_status']}**。",
             "- 科学裁决：**FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION**。",
             "- 绘图级复现：**PASS**。", "- 科学FAIL与格式/封存PASS为两个独立结论。", "",
             f"检查共{len(checks)}项：PASS {len(checks)-len(failed)}，FAIL {len(failed)}。", "",
             "## 迭代留痕", "",
             "首次运行得到24/28 PASS：当时规范包只建立了四个数据子目录，60份CSV尚未递归复制；随后补齐24份候选掩膜、24份候选边界、6份历史掩膜和6份历史边界。另有两项验收器假阳性：否定句被误识别为计算级成功声明，且正在运行的验收器自身Python被计为残留。验收器仅修正否定语义和排除当前PID，仍检查其他MATLAB/Python/PythonW进程；科学数据、科学阈值和科学裁决均未改变。", "",
             "## 检查明细", "",
             "| 检查项 | 状态 | 实际值 | 预期值 |", "|---|---|---|---|"]
    lines += [f"| {x['检查项']} | {x['状态']} | {x['实际值'].replace('|','/')} | {x['预期值'].replace('|','/')} |" for x in checks]
    (OUT / "步骤8G最终封存验收报告.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if not failed else 1


def main():
    required_files(); source_mirrors(); data_counts(); scientific_summaries()
    figures_and_format(); labels_and_sources(); mirror_and_processes()
    return write_results()


if __name__ == "__main__":
    sys.exit(main())
