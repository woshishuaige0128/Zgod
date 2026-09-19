"""13个中文单图入口共用的轻量调用器。"""

from __future__ import annotations

from pathlib import Path

from 生成第3章全部图片 import 刷新最终图片哈希, 绘制指定图片


def 运行单图入口(唯一ID: str) -> int:
    pdf, png = 绘制指定图片(唯一ID)
    if not pdf.is_file() or not png.is_file():
        raise RuntimeError(f"单图输出缺失：{pdf} / {png}")
    hash_manifest = 刷新最终图片哈希()
    print(f"{唯一ID} 已重绘：{pdf.name}；{png.name}")
    print(f"已同步刷新26项最终图片SHA-256：{hash_manifest}")
    return 0
