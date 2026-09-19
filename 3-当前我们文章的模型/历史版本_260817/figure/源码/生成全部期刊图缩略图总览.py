"""生成仅供人工快速审阅的八图PNG缩略图总览，不作为论文插图。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


源码目录 = Path(__file__).resolve().parent
图片根目录 = 源码目录.parent
PNG目录 = 图片根目录 / "PNG"

图片 = [
    "fig_rths_loop",
    "fig_pole_plane",
    "fig_benchmark_geometry",
    "fig_dof_idealization",
    "fig_division",
    "fig_eq_response",
    "fig_chirp_response",
    "fig_stability_domain",
]


def 生成总览() -> Path:
    card_w, card_h = 1200, 850
    margin, label_h = 45, 55
    canvas = Image.new("RGB", (card_w * 2, card_h * 4), "white")
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    font = ImageFont.truetype(str(font_path), 28) if font_path.is_file() else ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)

    for index, stem in enumerate(图片):
        path = PNG目录 / f"{stem}.png"
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as raw:
            image = raw.convert("RGB")
        thumb = ImageOps.contain(image, (card_w - 2 * margin, card_h - label_h - 2 * margin))
        col, row = index % 2, index // 2
        x0, y0 = col * card_w, row * card_h
        x = x0 + (card_w - thumb.width) // 2
        y = y0 + label_h + (card_h - label_h - thumb.height) // 2
        canvas.paste(thumb, (x, y))
        draw.rectangle((x0 + 8, y0 + 8, x0 + card_w - 8, y0 + card_h - 8), outline="#BBBBBB", width=2)
        draw.text((x0 + margin, y0 + 16), f"{index + 1}. {stem}", fill="#222222", font=font)

    output = PNG目录 / "全部期刊图缩略图总览.png"
    canvas.save(output, format="PNG", dpi=(300, 300))
    print(output)
    return output


if __name__ == "__main__":
    生成总览()
