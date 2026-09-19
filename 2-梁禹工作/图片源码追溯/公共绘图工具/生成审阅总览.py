"""把四章最终 PNG 生成为便于 Doctor Bego 一次性审阅的缩略图总览。"""

from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


工作区 = Path(__file__).resolve().parents[2]
图片根 = 工作区 / "figure"
输出目录 = 图片根 / "00_总索引与说明"
章节目录 = [
    图片根 / "第1章_绪论" / "PNG结果",
    图片根 / "第2章_系统缩聚理论和模型建立" / "PNG结果",
    图片根 / "第3章_缩聚对试验精度的影响" / "PNG结果",
    图片根 / "第4章_缩聚对试验稳定性的影响" / "PNG结果",
]


def 自然排序键(path: Path):
    m = re.search(r"图(\d+)-(\d+)", path.stem)
    return (int(m.group(1)), int(m.group(2))) if m else (99, 99)


def 找字体(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    候选 = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    for p in 候选:
        if p.is_file():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def 主函数() -> None:
    文件 = sorted(
        [p for d in 章节目录 if d.is_dir() for p in d.glob("图*.png")],
        key=自然排序键,
    )
    if len(文件) != 28:
        raise RuntimeError(f"需要28张最终PNG，当前找到{len(文件)}张")

    # 28 张图按 7 张/页均衡排成四页，避免最后一页只有一张图。
    列数 = 2
    单元宽, 单元高 = 1300, 700
    边距, 标签高 = 40, 90
    每页行数 = 4
    每页数量 = 7
    页数 = math.ceil(len(文件) / 每页数量)
    标题字体 = 找字体(30)
    标签字体 = 找字体(24)
    页图像: list[Image.Image] = []

    for 页 in range(页数):
        当前 = 文件[页 * 每页数量 : (页 + 1) * 每页数量]
        画布 = Image.new(
            "RGB",
            (边距 * 2 + 列数 * 单元宽, 边距 * 2 + 70 + 每页行数 * 单元高),
            "white",
        )
        draw = ImageDraw.Draw(画布)
        draw.text((边距, 边距), f"梁禹硕士论文图片重绘总览  第{页+1}/{页数}页", fill="black", font=标题字体)
        for i, p in enumerate(当前):
            row, col = divmod(i, 列数)
            x0 = 边距 + col * 单元宽
            y0 = 边距 + 70 + row * 单元高
            with Image.open(p) as src:
                im = src.convert("RGB")
                im.thumbnail((单元宽 - 50, 单元高 - 标签高 - 40), Image.Resampling.LANCZOS)
                x = x0 + (单元宽 - im.width) // 2
                y = y0 + (单元高 - 标签高 - im.height) // 2
                画布.paste(im, (x, y))
            标签 = p.stem.replace("_", "  ")
            draw.text((x0 + 20, y0 + 单元高 - 标签高 + 10), 标签, fill="black", font=标签字体)
        页路径 = 输出目录 / f"全部图片缩略图总览_第{页+1}页.png"
        画布.save(页路径, dpi=(300, 300))
        页图像.append(画布)

    pdf = 输出目录 / "全部图片缩略图总览.pdf"
    页图像[0].save(pdf, save_all=True, append_images=页图像[1:], resolution=300.0)
    print(f"已生成{页数}页总览和PDF：{pdf}")


if __name__ == "__main__":
    主函数()
