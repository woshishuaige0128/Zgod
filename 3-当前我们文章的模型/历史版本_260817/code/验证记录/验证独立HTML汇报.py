from __future__ import annotations

import base64
import hashlib
import re
import shutil
import struct
import tempfile
from html.parser import HTMLParser
from pathlib import Path


REPORT_NAME = "小论文案例分析Fig6至Fig10_复现汇报.html"


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.nav_hrefs: list[str] = []
        self.images: list[dict[str, str]] = []
        self.h1_count = 0
        self.section_count = 0
        self.details_count = 0
        self.text_parts: list[str] = []
        self._nav_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "nav":
            self._nav_depth += 1
        elif tag == "a" and self._nav_depth:
            self.nav_hrefs.append(values.get("href", ""))
        elif tag == "img":
            self.images.append(values)
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "section":
            self.section_count += 1
        elif tag == "details":
            self.details_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self._nav_depth -= 1

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data)


def fail(message: str) -> None:
    raise RuntimeError(message)


def png_dimensions(raw: bytes) -> tuple[int, int]:
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        fail("内嵌图片不是有效PNG")
    return struct.unpack(">II", raw[16:24])


def validate(path: Path) -> list[str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    parser = ReportParser()
    parser.feed(text)
    visible_text = "\n".join(parser.text_parts)

    checks: list[str] = []
    if not text.lstrip().lower().startswith("<!doctype html>"):
        fail("缺少HTML5 doctype")
    if '<html lang="zh-CN">' not in text:
        fail("缺少lang=zh-CN")
    if '<meta charset="utf-8">' not in text.lower():
        fail("缺少UTF-8声明")
    if 'name="viewport"' not in text:
        fail("缺少移动端viewport")
    checks.append("HTML5、UTF-8、中文语言和移动端viewport声明完整")

    if parser.h1_count != 1:
        fail(f"H1数量应为1，实际为{parser.h1_count}")
    expected_sections = {"summary", "scope", "logic", "figures", "validation", "operate", "boundary", "action"}
    ids = set(parser.ids)
    if not expected_sections.issubset(ids):
        fail(f"缺少章节ID：{sorted(expected_sections - ids)}")
    if len(parser.ids) != len(ids):
        fail("HTML存在重复ID")
    if parser.section_count != 8:
        fail(f"section数量应为8，实际为{parser.section_count}")
    if parser.details_count < 3:
        fail(f"证据折叠区至少应为3个，实际为{parser.details_count}")
    checks.append("一份主标题、八个主体章节、证据折叠区和唯一ID完整")

    expected_hrefs = [f"#{item}" for item in ("summary", "scope", "logic", "figures", "validation", "operate", "boundary", "action")]
    if parser.nav_hrefs != expected_hrefs:
        fail(f"导航目标不符合预期：{parser.nav_hrefs}")
    if any(href[1:] not in ids for href in parser.nav_hrefs):
        fail("导航存在无目标锚点")
    checks.append("八个目录跳转均指向现有章节")

    if len(parser.images) != 5:
        fail(f"内嵌图片应为5张，实际为{len(parser.images)}")
    image_dimensions: list[str] = []
    for index, attrs in enumerate(parser.images, start=1):
        src = attrs.get("src", "")
        if not src.startswith("data:image/png;base64,"):
            fail(f"第{index}张图片不是内嵌PNG data URI")
        if not attrs.get("alt", "").strip():
            fail(f"第{index}张图片缺少替代文本")
        decoded = base64.b64decode(src.split(",", 1)[1], validate=True)
        width, height = png_dimensions(decoded)
        if int(attrs.get("width", "0")) != width or int(attrs.get("height", "0")) != height:
            fail(f"第{index}张图片声明尺寸与PNG不一致")
        image_dimensions.append(f"{width}×{height}")
    checks.append("五张结果图均完整内嵌、可解码、带替代文本且尺寸声明正确：" + "、".join(image_dimensions))

    forbidden_resource_patterns = {
        "HTTP(S)资源": r"(?:src|href)=[\"']https?://",
        "本地文件资源": r"(?:src|href)=[\"']file://",
        "外部样式表": r"<link\b(?=[^>]*\brel=[\"']?stylesheet\b)",
        "外部或内联脚本": r"<script\b",
        "CSS导入": r"@import\b",
        "CSS网络URL": r"url\(\s*[\"']?https?://",
    }
    for label, pattern in forbidden_resource_patterns.items():
        if re.search(pattern, text, flags=re.I):
            fail(f"发现{label}")
    checks.append("无网络、本地旁置文件、外部样式表、脚本或CSS导入依赖")

    required_text = [
        "Fig.1–Fig.5", "不在本次交付范围内", "MATLAB R2025b", "Windows 64位",
        "Fig.6–Fig.9", "没有重跑Simulink", "Fig.10", "计算级复现未通过",
        "RUN_THIS_FIGURE.m", "VERIFY_THIS_FIGURE.m", "10/10", "386点",
        "0.9765625 ms", "当前是否需要您操作", "SHA-256",
    ]
    missing = [item for item in required_text if item not in visible_text]
    if missing:
        fail(f"缺少关键事实：{missing}")
    forbidden_claims = ["计算级复现通过", "从模型重新算出全部结果", "从物理模型重新求解出全部结果"]
    present_forbidden = [item for item in forbidden_claims if item in visible_text]
    if present_forbidden:
        fail(f"出现越界结论：{present_forbidden}")
    placeholders = [item for item in ("TODO", "TBD", "Lorem ipsum", "待补充", "待填写", "??") if item in visible_text]
    if placeholders:
        fail(f"出现占位内容：{placeholders}")
    checks.append("范围、逐图代码、实测环境、验证结果和计算级证据边界表述完整且无占位符")

    css_requirements = ["@media (max-width:850px)", "@media print", "@page", "size:A4", "minmax(0,1fr)", "overflow-x:auto"]
    missing_css = [item for item in css_requirements if item not in text]
    if missing_css:
        fail(f"缺少响应式或打印样式：{missing_css}")
    checks.append("包含窄屏布局、局部横向滚动和A4打印样式")

    digest = hashlib.sha256(raw).hexdigest().upper()
    with tempfile.TemporaryDirectory(prefix="html_standalone_") as temp_dir:
        copied = Path(temp_dir) / "任意改名后的独立汇报.html"
        shutil.copy2(path, copied)
        copied_raw = copied.read_bytes()
        if hashlib.sha256(copied_raw).hexdigest().upper() != digest:
            fail("随机临时目录复制后文件哈希变化")
        copied_parser = ReportParser()
        copied_parser.feed(copied_raw.decode("utf-8"))
        if len(copied_parser.images) != 5:
            fail("随机临时目录中的副本未保留五张图片")
    checks.append("单个HTML复制并任意改名到随机临时目录后，完整SHA-256与五张内嵌图片保持不变")
    checks.append(f"文件大小={len(raw)}字节；SHA-256={digest}")
    return checks


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    html_path = root / REPORT_NAME
    report_path = root / "验证记录" / "HTML汇报验收报告.txt"
    checks = validate(html_path)
    lines = [
        "STATUS=PASS",
        f"HTML={html_path}",
        "STATIC_CHECKS=PASS",
        "STANDALONE_COPY_CHECK=PASS",
        "",
        "检查明细：",
        *[f"- {item}" for item in checks],
        "",
        "说明：桌面、390×844窄屏与打印媒体的浏览器视觉检查另行记录。",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("STATUS=PASS")
    print(f"HTML={html_path}")
    print(f"VALIDATION_REPORT={report_path}")
    for item in checks:
        print(f"PASS: {item}")


if __name__ == "__main__":
    main()
