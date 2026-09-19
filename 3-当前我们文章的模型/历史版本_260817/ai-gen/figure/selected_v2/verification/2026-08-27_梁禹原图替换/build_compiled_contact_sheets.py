from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
JOBS = [
    (
        "manuscript_0826.tex：梁禹原图替换后20页总览",
        ROOT / "rendered_all_pages_manuscript_0826",
        ROOT / "all_pages_manuscript_0826_contact_sheet.png",
    ),
    (
        "manuscript_0826_anti_defensive.tex：梁禹原图替换后20页总览",
        ROOT / "rendered_all_pages_manuscript_0826_anti_defensive",
        ROOT / "all_pages_manuscript_0826_anti_defensive_contact_sheet.png",
    ),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def build(title: str, page_dir: Path, output: Path) -> None:
    pages = sorted(page_dir.glob("page-*.png"))
    if len(pages) != 20:
        raise RuntimeError(f"{page_dir} 应有20页，实际为{len(pages)}页。")

    columns, rows = 4, 5
    margin, gutter = 28, 18
    title_h, label_h = 72, 30
    cell_w, cell_h = 430, 640
    width = margin * 2 + columns * cell_w + (columns - 1) * gutter
    height = margin * 2 + title_h + rows * cell_h + (rows - 1) * gutter
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((width // 2, margin), title, font=font(30), fill="#202020", anchor="ma")

    for index, page in enumerate(pages):
        row, column = divmod(index, columns)
        x0 = margin + column * (cell_w + gutter)
        y0 = margin + title_h + row * (cell_h + gutter)
        draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), outline="#A0A0A0", width=2)
        draw.text((x0 + cell_w // 2, y0 + 5), f"第{index + 1}页", font=font(20), fill="#303030", anchor="ma")
        with Image.open(page) as source:
            thumbnail = ImageOps.contain(
                source.convert("RGB"),
                (cell_w - 20, cell_h - label_h - 18),
                Image.Resampling.LANCZOS,
            )
        canvas.paste(thumbnail, (x0 + (cell_w - thumbnail.width) // 2, y0 + label_h + 8))

    canvas.save(output, dpi=(150, 150), optimize=True)
    print(f"已生成：{output}；页数={len(pages)}；尺寸={canvas.width}x{canvas.height}")


def main() -> None:
    for title, page_dir, output in JOBS:
        build(title, page_dir, output)


if __name__ == "__main__":
    main()
