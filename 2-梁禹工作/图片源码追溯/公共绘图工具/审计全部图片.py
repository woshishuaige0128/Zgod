"""对28张论文图片做交付级完整性与文件质量审计。

本脚本不判断工程结论是否正确；数值与语义证据由各图验证记录提供。
它负责证明索引覆盖、文件存在、PDF可读、PNG分辨率/DPI以及明显路径泄漏。
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from PIL import Image
from PyPDF2 import PdfReader


工作区 = Path(__file__).resolve().parents[2]
图片根 = 工作区 / "figure"
总索引 = 图片根 / "00_总索引与说明" / "图片总索引.csv"
报告JSON = 图片根 / "00_总索引与说明" / "图片完整性审计.json"
报告MD = 图片根 / "00_总索引与说明" / "图片完整性审计.md"
最终哈希清单 = 图片根 / "00_总索引与说明" / "最终图片SHA256.csv"

期望章节数量 = {"第1章": 1, "第2章": 9, "第3章": 13, "第4章": 5}
期望唯一ID = {
    "1-1",
    *(f"2-{i}" for i in range(1, 10)),
    "3-1",
    "3-2",
    *(f"3-{i}" for i in range(5, 16)),
    *(f"4-{i}" for i in range(1, 6)),
}
章节目录 = {
    "第1章": 图片根 / "第1章_绪论",
    "第2章": 图片根 / "第2章_系统缩聚理论和模型建立",
    "第3章": 图片根 / "第3章_缩聚对试验精度的影响",
    "第4章": 图片根 / "第4章_缩聚对试验稳定性的影响",
}


def 读取CSV(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def 文件SHA256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def 相对路径存在(文本: str) -> tuple[bool, list[Path]]:
    values = [x.strip() for x in 文本.split(";") if x.strip()]
    if not values:
        return False, []
    paths: list[Path] = []
    for value in values:
        p = Path(value)
        if not p.is_absolute():
            p = (工作区 / p).resolve()
        else:
            p = p.resolve()
        try:
            p.relative_to(工作区.resolve())
        except ValueError:
            return False, []
        paths.append(p)
    return all(p.exists() and p.is_file() and p.stat().st_size > 0 for p in paths), paths


def 检查索引文件字段(r: dict[str, str], 字段: str, uid: str, 错误: list[str]) -> list[Path] | None:
    ok, paths = 相对路径存在(r.get(字段, ""))
    if not ok:
        错误.append(f"图{uid}索引字段“{字段}”为空或文件缺失：{r.get(字段, '')}")
        return None
    if 字段 in {"代码入口", "PDF结果", "PNG结果", "验证记录"} and len(paths) != 1:
        错误.append(f"图{uid}索引字段“{字段}”必须恰好一个文件，实际{len(paths)}个")
        return None
    return paths


def 查找匹配文件(根: Path, 子目录: str, 唯一ID: str, 扩展名: str) -> list[Path]:
    d = 根 / 子目录
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob(f"图{唯一ID}_*{扩展名}") if p.is_file() and p.stat().st_size > 0)


def 检查PNG(path: Path) -> dict[str, object]:
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        dpi = im.info.get("dpi", (0.0, 0.0))
        dpi = tuple(float(v) for v in dpi[:2]) if isinstance(dpi, tuple) else (0.0, 0.0)
        alpha_extrema = im.getchannel("A").getextrema() if "A" in im.getbands() else None
        rgb = im.convert("RGB")
        corners = [
            rgb.getpixel((0, 0)),
            rgb.getpixel((rgb.width - 1, 0)),
            rgb.getpixel((0, rgb.height - 1)),
            rgb.getpixel((rgb.width - 1, rgb.height - 1)),
        ]
        opaque = alpha_extrema is None or alpha_extrema == (255, 255)
        white_corners = all(min(pixel) >= 245 for pixel in corners)
        return {
            "路径": str(path.relative_to(工作区)),
            "像素": [im.size[0], im.size[1]],
            "DPI": list(dpi),
            "DPI通过": min(dpi) >= 590.0,
            "有效像素通过": min(im.size) >= 1000,
            "模式": im.mode,
            "Alpha范围": list(alpha_extrema) if alpha_extrema is not None else None,
            "不透明通过": opaque,
            "四角白底通过": white_corners,
        }


def 解引用(obj):
    try:
        return obj.get_object()
    except AttributeError:
        return obj


def 统计PDF资源(resources) -> tuple[int, int, int]:
    """递归统计页面/Form XObject内的栅格图、字体和Type 3字体。"""
    图片对象: set[tuple[int, int] | int] = set()
    字体对象: set[tuple[int, int] | int] = set()
    Type3对象: set[tuple[int, int] | int] = set()
    已访问资源: set[tuple[int, int] | int] = set()

    def 对象键(obj) -> tuple[int, int] | int:
        if hasattr(obj, "idnum") and hasattr(obj, "generation"):
            return (int(obj.idnum), int(obj.generation))
        return id(obj)

    def 扫描(res) -> None:
        res_key = 对象键(res)
        if res_key in 已访问资源:
            return
        已访问资源.add(res_key)
        res = 解引用(res) or {}
        if not hasattr(res, "get"):
            return

        fonts = 解引用(res.get("/Font") or {})
        for font_ref in fonts.values() if hasattr(fonts, "values") else []:
            key = 对象键(font_ref)
            字体对象.add(key)
            font = 解引用(font_ref)
            if hasattr(font, "get") and str(font.get("/Subtype", "")) == "/Type3":
                Type3对象.add(key)

        xobjects = 解引用(res.get("/XObject") or {})
        for xref in xobjects.values() if hasattr(xobjects, "values") else []:
            key = 对象键(xref)
            obj = 解引用(xref)
            if not hasattr(obj, "get"):
                continue
            subtype = str(obj.get("/Subtype", ""))
            if subtype == "/Image":
                图片对象.add(key)
            elif subtype == "/Form" and obj.get("/Resources") is not None:
                扫描(obj.get("/Resources"))

    扫描(resources)
    return len(图片对象), len(字体对象), len(Type3对象)


def 检查PDF(path: Path) -> dict[str, object]:
    reader = PdfReader(str(path))
    page = reader.pages[0] if reader.pages else None
    图片对象数 = 0
    字体数 = 0
    Type3字体数 = 0
    if page is not None:
        resources = page.get("/Resources") or {}
        图片对象数, 字体数, Type3字体数 = 统计PDF资源(resources)
        box = page.mediabox
        页面点 = [float(box.width), float(box.height)]
    else:
        页面点 = [0.0, 0.0]
    return {
        "路径": str(path.relative_to(工作区)),
        "页数": len(reader.pages),
        "单页通过": len(reader.pages) == 1,
        "字节数": path.stat().st_size,
        "页面尺寸_pt": 页面点,
        "栅格图片对象数": 图片对象数,
        "字体资源数": 字体数,
        "Type3字体数": Type3字体数,
    }


def 主函数() -> int:
    错误: list[str] = []
    警告: list[str] = []
    明细: list[dict[str, object]] = []

    if not 总索引.is_file():
        raise FileNotFoundError(总索引)
    行 = 读取CSV(总索引)
    ids = [r["唯一ID"].strip() for r in 行]
    if len(行) != 28:
        错误.append(f"总索引应为28行，实际{len(行)}行")
    重复 = sorted(k for k, v in Counter(ids).items() if v > 1)
    if 重复:
        错误.append(f"唯一ID重复：{重复}")
    if set(ids) != 期望唯一ID:
        错误.append(
            f"唯一ID集合错误：缺失{sorted(期望唯一ID - set(ids))}，"
            f"多余{sorted(set(ids) - 期望唯一ID)}"
        )
    实际章节数量 = Counter(r["章节"].strip() for r in 行)
    if dict(实际章节数量) != 期望章节数量:
        错误.append(f"章节数量错误：{dict(实际章节数量)}")

    for r in 行:
        章节 = r["章节"].strip()
        uid = r["唯一ID"].strip()
        根 = 章节目录.get(章节)
        图明细: dict[str, object] = {"章节": 章节, "唯一ID": uid, "图题": r["图题"]}
        if 根 is None or not 根.is_dir():
            错误.append(f"图{uid}章节目录缺失")
            明细.append(图明细)
            continue

        pdfs = 查找匹配文件(根, "PDF结果", uid, ".pdf")
        pngs = 查找匹配文件(根, "PNG结果", uid, ".png")
        代码路径 = 检查索引文件字段(r, "代码入口", uid, 错误)
        数据路径 = 检查索引文件字段(r, "数据文件", uid, 错误)
        来源路径 = 检查索引文件字段(r, "原始来源候选", uid, 错误)
        PDF路径 = 检查索引文件字段(r, "PDF结果", uid, 错误)
        PNG路径 = 检查索引文件字段(r, "PNG结果", uid, 错误)
        验证路径 = 检查索引文件字段(r, "验证记录", uid, 错误)

        if r.get("状态", "").strip() not in {"已复现", "已重绘"}:
            错误.append(f"图{uid}尚未完成，索引状态为：{r.get('状态', '')}")
        if 代码路径 and 代码路径[0].suffix.lower() not in {".py", ".m"}:
            错误.append(f"图{uid}代码入口不是.py或.m：{代码路径[0].relative_to(工作区)}")
        if 代码路径 and "可复现代码" not in 代码路径[0].parts:
            错误.append(f"图{uid}代码入口不在可复现代码目录：{代码路径[0].relative_to(工作区)}")

        if len(pdfs) != 1:
            错误.append(f"图{uid} PDF应恰有1份，实际{len(pdfs)}份")
        if len(pngs) != 1:
            错误.append(f"图{uid} PNG应恰有1份，实际{len(pngs)}份")
        if PDF路径 and pdfs and PDF路径[0].resolve() != pdfs[0].resolve():
            错误.append(f"图{uid}索引PDF与章节唯一PDF不一致")
        if PNG路径 and pngs and PNG路径[0].resolve() != pngs[0].resolve():
            错误.append(f"图{uid}索引PNG与章节唯一PNG不一致")

        if pdfs:
            try:
                图明细["PDF"] = 检查PDF(pdfs[0])
                if not 图明细["PDF"]["单页通过"]:
                    错误.append(f"图{uid} PDF不是单页")
                width_pt, height_pt = 图明细["PDF"]["页面尺寸_pt"]
                if not (280.0 <= width_pt <= 560.0 and 120.0 <= height_pt <= 560.0):
                    错误.append(
                        f"图{uid} PDF页面尺寸异常或存在整页画布留白："
                        f"{width_pt/72:.3f}×{height_pt/72:.3f} in"
                    )
                if 图明细["PDF"]["栅格图片对象数"] > 0:
                    错误.append(
                        f"图{uid}应为纯矢量PDF，却含{图明细['PDF']['栅格图片对象数']}个栅格图片对象"
                    )
                if 图明细["PDF"]["Type3字体数"] > 0:
                    错误.append(f"图{uid} PDF含{图明细['PDF']['Type3字体数']}个Type 3字体")
            except Exception as exc:
                错误.append(f"图{uid} PDF不可读：{exc}")
        if pngs:
            try:
                图明细["PNG"] = 检查PNG(pngs[0])
                if not 图明细["PNG"]["DPI通过"]:
                    错误.append(f"图{uid} PNG未达到600 dpi（允许元数据舍入至590）")
                if not 图明细["PNG"]["有效像素通过"]:
                    错误.append(f"图{uid} PNG有效像素不足（短边小于1000像素）")
                if not 图明细["PNG"]["不透明通过"]:
                    错误.append(f"图{uid} PNG含透明像素，未使用不透明白底")
                if not 图明细["PNG"]["四角白底通过"]:
                    错误.append(f"图{uid} PNG四角不是白色背景")
            except Exception as exc:
                错误.append(f"图{uid} PNG不可读：{exc}")
        图明细["证据路径"] = {
            "代码": ";".join(str(p.relative_to(工作区)) for p in 代码路径) if 代码路径 else "",
            "数据": ";".join(str(p.relative_to(工作区)) for p in 数据路径) if 数据路径 else "",
            "来源": ";".join(str(p.relative_to(工作区)) for p in 来源路径) if 来源路径 else "",
            "验证": ";".join(str(p.relative_to(工作区)) for p in 验证路径) if 验证路径 else "",
        }
        明细.append(图明细)

    # 静态检查新增代码是否泄漏原作者桌面路径或明显违反出图要求。
    新代码 = [
        p
        for p in list(图片根.rglob("*.py")) + list(图片根.rglob("*.m"))
        if "原始来源副本" not in p.parts and "__pycache__" not in p.parts
    ]
    禁止模式 = {
        "原作者桌面绝对路径": re.compile(r"C:[\\/]Users[\\/]liangyu", re.I),
        "禁用jet色图": re.compile(r"(?:cmap\s*=\s*['\"]jet|colormap\s*\(\s*jet)", re.I),
        "禁用rainbow色图": re.compile(r"(?:cmap\s*=\s*['\"]rainbow|colormap\s*\(\s*rainbow)", re.I),
        "禁止开启默认网格": re.compile(r"(?:\.grid\s*\(\s*True|\bgrid\s+on\b)", re.I),
        "禁止MATLAB图内标题": re.compile(r"(?m)^\s*title\s*\(\s*[^)\s]", re.I),
        "禁止引用旧映射审计留存": re.compile(r"(?:旧映射|审计留存_旧映射数据_禁止出图)", re.I),
    }
    for p in 新代码:
        try:
            文本 = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            文本 = p.read_text(encoding="gb18030", errors="replace")
        for 名称, pat in 禁止模式.items():
            if 名称 == "禁止引用旧映射审计留存" and p.resolve() == Path(__file__).resolve():
                continue
            if pat.search(文本):
                错误.append(f"{名称}：{p.relative_to(工作区)}")

    # 章节清单和最终报告都应让使用者逐图直接进入中文命名单图源码。
    code_names: list[str] = []
    for r in 行:
        ok, paths = 相对路径存在(r.get("代码入口", ""))
        if not ok or len(paths) != 1:
            continue
        code = paths[0]
        code_names.append(str(code.resolve()))
        uid = r["唯一ID"].strip()
        if f"图{uid}_" not in code.stem:
            错误.append(f"图{uid}代码入口不是对应的中文命名单图入口：{code.relative_to(工作区)}")
    if len(set(code_names)) != 28:
        错误.append(f"28张图应有28个独立单图代码入口，实际唯一入口{len(set(code_names))}个")

    if not 最终哈希清单.is_file():
        错误.append("缺少统一最终图片SHA-256清单")
    else:
        hash_rows = 读取CSV(最终哈希清单)
        if len(hash_rows) != 56:
            错误.append(f"最终图片SHA-256清单应有56行，实际{len(hash_rows)}行")
        hash_paths = [item.get("相对工作区路径", "") for item in hash_rows]
        if len(set(hash_paths)) != len(hash_paths):
            错误.append("最终图片SHA-256清单包含重复路径")
        hash_formats = Counter(Path(path).suffix.lower() for path in hash_paths)
        if hash_formats != Counter({".pdf": 28, ".png": 28}):
            错误.append(f"最终图片SHA-256清单格式数量错误：{dict(hash_formats)}")
        indexed_outputs = {
            str((工作区 / r[field]).resolve().relative_to(工作区.resolve())).replace("\\", "/")
            for r in 行
            for field in ("PDF结果", "PNG结果")
            if r.get(field, "").strip() and ";" not in r[field]
        }
        if set(hash_paths) != indexed_outputs:
            错误.append(
                "最终图片SHA-256清单目标集与索引56个PDF/PNG不一致："
                f"缺失{sorted(indexed_outputs - set(hash_paths))[:5]}，"
                f"多余{sorted(set(hash_paths) - indexed_outputs)[:5]}"
            )
        hash_bad: list[str] = []
        for item in hash_rows:
            target = (工作区 / item.get("相对工作区路径", "")).resolve()
            try:
                target.relative_to(工作区.resolve())
            except ValueError:
                hash_bad.append(item.get("相对工作区路径", ""))
                continue
            if (
                not target.is_file()
                or target.stat().st_size != int(item.get("字节数", -1))
                or 文件SHA256(target) != item.get("SHA256", "")
            ):
                hash_bad.append(item.get("相对工作区路径", ""))
        if hash_bad:
            错误.append(f"最终图片SHA-256清单有{len(hash_bad)}项不匹配：{hash_bad[:5]}")

    结果 = {
        "通过": not 错误,
        "索引行数": len(行),
        "唯一ID数": len(set(ids)),
        "章节数量": dict(实际章节数量),
        "错误": 错误,
        "警告": 警告,
        "明细": 明细,
    }
    报告JSON.write_text(json.dumps(结果, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# 28张图片完整性审计",
        "",
        f"- 结论：{'通过' if not 错误 else '未通过'}",
        f"- 索引行数：{len(行)}",
        f"- 唯一ID数：{len(set(ids))}",
        f"- 错误数：{len(错误)}",
        f"- 警告数：{len(警告)}",
        "",
        "## 错误",
    ]
    md.extend([f"- {x}" for x in 错误] or ["- 无"])
    md.extend(["", "## 警告"])
    md.extend([f"- {x}" for x in 警告] or ["- 无"])
    报告MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: 结果[k] for k in ("通过", "索引行数", "唯一ID数", "章节数量", "错误", "警告")}, ensure_ascii=False, indent=2))
    return 0 if not 错误 else 1


if __name__ == "__main__":
    raise SystemExit(主函数())
