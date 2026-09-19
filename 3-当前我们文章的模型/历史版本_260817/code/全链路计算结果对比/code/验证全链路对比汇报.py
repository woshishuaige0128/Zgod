from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import shutil
import struct
import tempfile
from html.parser import HTMLParser
from pathlib import Path


SCRIPT = Path(__file__).resolve()
PACKAGE_ROOT = SCRIPT.parent.parent
DELIVERY_ROOT = PACKAGE_ROOT.parent
REPORT = DELIVERY_ROOT / "小论文Fig6至Fig10_全链路计算结果对比汇报.html"
AUDIT_ROOT = PACKAGE_ROOT / "04_数值审计"
VALIDATION_REPORT = AUDIT_ROOT / "全链路对比汇报静态验收.txt"


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.images: list[dict[str, str]] = []
        self.nav_links: list[str] = []
        self.text: list[str] = []
        self.h1_count = 0
        self._nav_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "nav":
            self._nav_depth += 1
        elif tag == "a" and self._nav_depth:
            self.nav_links.append(values.get("href", ""))
        elif tag == "img":
            self.images.append(values)
        elif tag == "h1":
            self.h1_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._nav_depth -= 1

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def png_dimensions(raw: bytes) -> tuple[int, int]:
    require(raw[:8] == b"\x89PNG\r\n\x1a\n", "内嵌对象不是有效PNG")
    return struct.unpack(">II", raw[16:24])


def validate_html() -> list[str]:
    raw = REPORT.read_bytes()
    text = raw.decode("utf-8")
    parser = Parser()
    parser.feed(text)
    visible = "\n".join(parser.text)
    checks: list[str] = []

    require(text.lstrip().lower().startswith("<!doctype html>"), "缺少HTML5 doctype")
    require('<html lang="zh-CN">' in text, "缺少中文语言声明")
    require('<meta charset="utf-8">' in text.lower(), "缺少UTF-8声明")
    require('name="viewport"' in text, "缺少viewport")
    require(parser.h1_count == 1, f"H1数量不是1：{parser.h1_count}")
    checks.append("HTML5、UTF-8、中文语言、移动端viewport和唯一H1通过")

    expected_ids = (
        "summary",
        "scope",
        "chain",
        "results",
        "fig10",
        "mapping",
        "validation",
        "boundary",
        "action",
    )
    require(set(expected_ids).issubset(set(parser.ids)), "主体章节不完整")
    require(len(parser.ids) == len(set(parser.ids)), "HTML存在重复ID")
    expected_links = [f"#{value}" for value in expected_ids]
    require(parser.nav_links == expected_links, f"导航目标不符合预期：{parser.nav_links}")
    checks.append("九个主体章节和九个导航目标完整且ID唯一")

    require(len(parser.images) == 5, f"内嵌图片不是5张：{len(parser.images)}")
    dimensions: list[str] = []
    for index, attrs in enumerate(parser.images, start=1):
        source = attrs.get("src", "")
        require(source.startswith("data:image/png;base64,"), f"第{index}张图片不是data URI")
        require(bool(attrs.get("alt", "").strip()), f"第{index}张图片缺少alt")
        decoded = base64.b64decode(source.split(",", 1)[1], validate=True)
        width, height = png_dimensions(decoded)
        require(int(attrs.get("width", "0")) == width, f"第{index}张图片宽度声明错误")
        require(int(attrs.get("height", "0")) == height, f"第{index}张图片高度声明错误")
        dimensions.append(f"{width}x{height}")
    checks.append("五张必要对比图均内嵌、可解码、有替代文本且尺寸声明一致：" + "、".join(dimensions))

    forbidden = {
        "HTTP(S)资源": r"(?:src|href)=[\"']https?://",
        "file资源": r"(?:src|href)=[\"']file://",
        "外部样式表": r"<link\b(?=[^>]*\brel=[\"']?stylesheet)",
        "脚本": r"<script\b",
        "CSS导入": r"@import\b",
        "CSS网络URL": r"url\(\s*[\"']?https?://",
    }
    for label, pattern in forbidden.items():
        require(re.search(pattern, text, flags=re.I) is None, f"发现{label}")
    checks.append("无网络、本地旁置资源、外部样式表、脚本或CSS导入依赖")

    required_text = (
        "Fig.6–Fig.9已经稳定实现计算级复现",
        "Fig.10的计算链也能稳定运行，但没有复现出论文中的六条稳定边界",
        "49,848",
        "3,356,432",
        "0 / 6",
        "run_board18_adapted.m",
        "run_board20_step8e_fullgrid_matlab('full')",
        "没有读取论文PDF、386点目标",
        "板块21",
        "当前是否需要您操作",
    )
    missing = [value for value in required_text if value not in visible]
    require(not missing, f"缺少关键事实：{missing}")
    require("R01、R02、R03、R04均为0/6" in visible, "缺少四候选0/6结论")
    require(not any(token in visible for token in ("TODO", "TBD", "Lorem ipsum", "待补充", "待填写", "??")), "出现占位符")
    checks.append("计算级结论、Fig.10失败门、运行数字、代码映射和证据边界表述完整")

    for required_css in (
        "@media (max-width:850px)",
        "@media print",
        "@page",
        "size:A4",
        "minmax(0,1fr)",
        "overflow-x:auto",
    ):
        require(required_css in text, f"缺少响应式/打印样式：{required_css}")
    checks.append("桌面、窄屏、宽表局部滚动和A4打印样式存在")

    digest = sha256_file(REPORT)
    with tempfile.TemporaryDirectory(prefix="fullchain_html_") as temporary:
        copied = Path(temporary) / "任意改名后的全链对比.html"
        shutil.copy2(REPORT, copied)
        require(sha256_file(copied) == digest, "随机目录复制后HTML哈希变化")
        copied_parser = Parser()
        copied_parser.feed(copied.read_text(encoding="utf-8"))
        require(len(copied_parser.images) == 5, "随机目录副本没有保留五张内嵌图")
    checks.append(f"随机位置离线复制后哈希与五张图片保持；HTML SHA-256={digest}")
    return checks


def validate_numeric_outputs() -> list[str]:
    checks: list[str] = []
    file_rows = read_rows(AUDIT_ROOT / "Fig06至Fig09文件级对比.csv")
    require(len(file_rows) == 4, "Fig.6--Fig.9文件级结果不是4行")
    require(all(float(row["maximum_absolute_difference"]) == 0.0 for row in file_rows), "Fig.6--Fig.9存在非零最大差")
    require(all(row["sha256_equal"].lower() == "true" for row in file_rows), "Fig.6--Fig.9存在哈希不同")
    checks.append("Fig.6--Fig.9四对40961x10文件最大差0且SHA-256逐对相同")

    column_rows = read_rows(AUDIT_ROOT / "Fig06至Fig09逐列对比.csv")
    require(len(column_rows) == 40, "Fig.6--Fig.9逐列审计不是40行")
    require(all(float(row["maximum_absolute_difference"]) == 0.0 for row in column_rows), "40列中存在非零差")
    require(all(row["exact_elementwise_equal"] == "1" for row in column_rows), "40列中存在非逐元素相等")
    checks.append("Fig.6--Fig.9四图40列全部逐元素完全相等")

    path_rows = read_rows(AUDIT_ROOT / "Fig10_24条候选逐路径精确匹配.csv")
    require(len(path_rows) == 24, "Fig.10逐路径审计不是24行")
    require(all(row["ordered_path_exact_match"] == "0" for row in path_rows), "Fig.10出现与0/6结论冲突的精确命中")
    panel_rows = read_rows(AUDIT_ROOT / "Fig10_8面板命中汇总.csv")
    require(len(panel_rows) == 8, "Fig.10面板汇总不是8行")
    require(all(row["exact_matches"] == "0" and row["status"] == "FAIL" for row in panel_rows), "Fig.10面板状态不是全部0/3 FAIL")
    checks.append("Fig.10的24条方法候选均未精确命中；8个候选面板均为0/3 FAIL")

    step_summary = json.loads(
        (
            PACKAGE_ROOT
            / "01_本轮全链新算结果"
            / "Fig10_全网格计算"
            / "MATLAB步骤8E摘要.json"
        ).read_text(encoding="utf-8")
    )
    require(int(step_summary["point_count"]) == 49848, "Fig.10点数不是49,848")
    require(int(step_summary["total_physical_root_count"]) == 3356432, "Fig.10根数不是3,356,432")
    require(bool(step_summary["all_points_pass"]), "Fig.10不是全部点PASS")
    checks.append("Fig.10全网格49,848点、3,356,432根且all_points_pass=true")
    return checks


def validate_artifacts() -> list[str]:
    checks: list[str] = []
    pdf_files = sorted((PACKAGE_ROOT / "03_对比图" / "PDF").glob("*.pdf"))
    png_files = sorted((PACKAGE_ROOT / "03_对比图" / "PNG_600dpi").glob("*.png"))
    web_files = sorted((PACKAGE_ROOT / "03_对比图" / "HTML内嵌图").glob("*.png"))
    require(len(pdf_files) == 5, f"矢量PDF不是5份：{len(pdf_files)}")
    require(len(png_files) == 5, f"600dpi PNG不是5份：{len(png_files)}")
    require(len(web_files) == 5, f"HTML内嵌图不是5份：{len(web_files)}")
    for path in png_files:
        from PIL import Image

        with Image.open(path) as image:
            dpi = image.info.get("dpi", (0.0, 0.0))
            require(abs(float(dpi[0]) - 600.0) < 1.0 and abs(float(dpi[1]) - 600.0) < 1.0, f"{path.name}不是600dpi：{dpi}")
            require(image.mode in ("RGB", "RGBA"), f"{path.name}颜色模式异常：{image.mode}")
    checks.append("五份PDF、五份600dpi PNG和五份HTML内嵌预览数量正确；PNG分辨率与颜色模式通过")
    return checks


def validate_manifest() -> list[str]:
    manifest_path = AUDIT_ROOT / "本轮交付文件清单.csv"
    rows = read_rows(manifest_path)
    expected_paths = {
        path.relative_to(PACKAGE_ROOT).as_posix(): path
        for path in PACKAGE_ROOT.rglob("*")
        # 清单本身和每次验收都会改写的实时验收记录不参与载荷哈希闭环，
        # 避免“验证器改写记录后立即使自身清单失效”的自引用问题。
        if path.is_file() and path not in {manifest_path, VALIDATION_REPORT}
    }
    row_paths = {row["relative_path"] for row in rows}
    require(len(rows) == len(row_paths), "交付清单relative_path不唯一")
    require(row_paths == set(expected_paths), "交付清单与实际文件集合不闭合")
    for row in rows:
        path = expected_paths[row["relative_path"]]
        require(int(row["size_bytes"]) == path.stat().st_size, f"清单字节数错误：{path.name}")
        require(row["sha256"] == sha256_file(path), f"清单SHA-256错误：{path.name}")
    return [f"交付清单{len(rows)}/{len(rows)}文件路径、字节数和SHA-256全部闭合"]


def main() -> None:
    checks = validate_html() + validate_numeric_outputs() + validate_artifacts() + validate_manifest()
    lines = [
        "STATUS=PASS",
        f"HTML={REPORT}",
        f"HTML_SHA256={sha256_file(REPORT)}",
        "STATIC_HTML=PASS",
        "NUMERIC_AUDIT=PASS",
        "STANDALONE_COPY=PASS",
        "FIGURE_FILES=PASS",
        "",
        "检查明细：",
        *[f"- {check}" for check in checks],
        "",
        "浏览器桌面、390px窄屏和A4打印视觉检查另行记录。",
    ]
    VALIDATION_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
