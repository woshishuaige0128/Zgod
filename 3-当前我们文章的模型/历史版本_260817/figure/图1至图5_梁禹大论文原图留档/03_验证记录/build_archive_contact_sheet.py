from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ARCHIVE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ARCHIVE_ROOT / "02_高分辨率使用版_仅裁边"
OUTPUT_PATH = Path(__file__).resolve().parent / "图1至图5原图总览.png"

FIGURES = [
    ("图1（大论文图2-1，PDF第21页）", "图1_大论文图2-1_RTHS反馈控制闭环_PDF21页_600dpi.png"),
    ("图2（大论文图4-2，PDF第59页）", "图2_大论文图4-2_极点平面_PDF59页_600dpi.png"),
    ("图3（大论文图2-3，PDF第28页）", "图3_大论文图2-3_参考结构尺寸_PDF28页_600dpi.png"),
    ("图4(a)（大论文图2-4，PDF第29页）", "图4a_大论文图2-4_参考结构自由度_PDF29页_600dpi.png"),
    ("图4(b)（大论文图2-5，PDF第30页）", "图4b_大论文图2-5_简化自由度_PDF30页_600dpi.png"),
    ("图5(a)（大论文图3-1，PDF第37页）", "图5a_大论文图3-1_第一类子结构自由度选取_PDF37页_600dpi.png"),
    ("图5(b)（大论文图3-2，PDF第37页）", "图5b_大论文图3-2_第二类子结构自由度选取_PDF37页_600dpi.png"),
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def main() -> None:
    missing = [name for _, name in FIGURES if not (SOURCE_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少留档图片：{missing}")

    columns = 2
    rows = 4
    margin = 42
    gutter = 30
    title_height = 90
    cell_width = 980
    cell_height = 610
    label_height = 54
    footer_height = 70
    canvas_width = margin * 2 + columns * cell_width + gutter
    canvas_height = margin * 2 + title_height + rows * cell_height + (rows - 1) * gutter + footer_height

    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = load_font(38)
    label_font = load_font(25)
    footer_font = load_font(21)
    draw.text(
        (canvas_width // 2, margin),
        "梁禹大论文图1—图5原图留档总览",
        fill="#202020",
        font=title_font,
        anchor="ma",
    )

    for index, (label, filename) in enumerate(FIGURES):
        row, column = divmod(index, columns)
        x0 = margin + column * (cell_width + gutter)
        y0 = margin + title_height + row * (cell_height + gutter)
        draw.rounded_rectangle(
            (x0, y0, x0 + cell_width, y0 + cell_height),
            radius=10,
            fill="#FFFFFF",
            outline="#B0B0B0",
            width=2,
        )
        draw.text(
            (x0 + cell_width // 2, y0 + 11),
            label,
            fill="#202020",
            font=label_font,
            anchor="ma",
        )
        with Image.open(SOURCE_DIR / filename) as source:
            source_rgb = source.convert("RGB")
            fitted = ImageOps.contain(
                source_rgb,
                (cell_width - 46, cell_height - label_height - 34),
                method=Image.Resampling.LANCZOS,
            )
        image_x = x0 + (cell_width - fitted.width) // 2
        image_y = y0 + label_height + (cell_height - label_height - fitted.height) // 2
        canvas.paste(fitted, (image_x, image_y))

    draw.text(
        (canvas_width // 2, canvas_height - margin - 8),
        "总览图仅用于快速核对；单图使用版均由完整源 PDF 在 600 dpi 下直接裁边生成，未重绘。",
        fill="#505050",
        font=footer_font,
        anchor="ms",
    )
    canvas.save(OUTPUT_PATH, dpi=(180, 180), optimize=True)
    print(f"已生成：{OUTPUT_PATH}")
    print(f"尺寸：{canvas.width} x {canvas.height} px；子图数量：{len(FIGURES)}")


if __name__ == "__main__":
    main()
