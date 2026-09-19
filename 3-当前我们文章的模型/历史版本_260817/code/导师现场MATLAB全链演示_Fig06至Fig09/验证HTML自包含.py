from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path


package = Path(__file__).resolve().parent
html_path = package.parent / "小论文Fig6至Fig9_MATLAB现场全计算链汇报.html"
qa_dir = package / "验证记录"
text = html_path.read_text(encoding="utf-8")

errors: list[str] = []

if not text.lstrip().lower().startswith("<!doctype html>"):
    errors.append("缺少HTML5 doctype")

images = re.findall(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', text)
if len(images) != 4:
    errors.append(f"内嵌PNG应为4张，实际为{len(images)}张")
for index, payload in enumerate(images, start=1):
    decoded = base64.b64decode(payload, validate=True)
    if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append(f"第{index}张内嵌图不是有效PNG")

forbidden_patterns = {
    "external_src": r'src\s*=\s*["\']https?://',
    "external_css": r'<link\b[^>]*href=',
    "external_css_url": r'url\(\s*["\']?https?://',
    "iframe": r'<iframe\b',
    "script_src": r'<script\b[^>]*\bsrc=',
}
for name, pattern in forbidden_patterns.items():
    if re.search(pattern, text, flags=re.IGNORECASE):
        errors.append(f"命中外部依赖：{name}")

required = [
    "RUN_FIG06_FULLCHAIN.m",
    "RUN_FIG07_FULLCHAIN.m",
    "RUN_FIG08_FULLCHAIN.m",
    "RUN_FIG09_FULLCHAIN.m",
    "40961 × 3 × 3",
    "FULL_CHAIN=PASS",
    "Fig.10 不在本报告范围",
    "Guyan 代码与小论文理论公式",
    "Fig.9 与硕士论文图3-15",
]
for marker in required:
    if marker not in text:
        errors.append(f"缺少必要内容：{marker}")

report = {
    "status": "PASS" if not errors else "FAIL",
    "html": str(html_path),
    "bytes": html_path.stat().st_size,
    "sha256": hashlib.sha256(html_path.read_bytes()).hexdigest().upper(),
    "embedded_png": len(images),
    "external_resource_count": 0 if not any("外部依赖" in error for error in errors) else None,
    "required_markers": len(required),
    "errors": errors,
}

qa_dir.mkdir(parents=True, exist_ok=True)
(qa_dir / "HTML自包含验收.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)

print(f"STATUS={report['status']}")
print(f"HTML={html_path}")
print(f"EMBEDDED_PNG={report['embedded_png']}")
print(f"EXTERNAL_RESOURCE_COUNT={report['external_resource_count']}")
print(f"SHA256={report['sha256']}")
if errors:
    for error in errors:
        print(f"ERROR={error}")
    raise SystemExit(1)
