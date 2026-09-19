import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops


ARCHIVE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ARCHIVE_ROOT / "00_完整源PDF" / "梁禹手稿.pdf"
REFERENCE_DIR = ARCHIVE_ROOT / "02_高分辨率使用版_仅裁边"
EXPECTED_PDF_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"

# 坐标基于完整 PDF 页面在 600 dpi 下的像素坐标；顺序为 x、y、宽、高。
FIGURES = [
    ("图1", 21, (700, 3266, 3567, 1234), "图1_大论文图2-1_RTHS反馈控制闭环_PDF21页_600dpi.png"),
    ("图2", 59, (1133, 4000, 2834, 1734), "图2_大论文图4-2_极点平面_PDF59页_600dpi.png"),
    ("图3", 28, (900, 4500, 3400, 1834), "图3_大论文图2-3_参考结构尺寸_PDF28页_600dpi.png"),
    ("图4(a)", 29, (1400, 3933, 2900, 1567), "图4a_大论文图2-4_参考结构自由度_PDF29页_600dpi.png"),
    ("图4(b)", 30, (1333, 600, 2434, 1767), "图4b_大论文图2-5_简化自由度_PDF30页_600dpi.png"),
    ("图5(a)", 37, (933, 600, 3501, 1734), "图5a_大论文图3-1_第一类子结构自由度选取_PDF37页_600dpi.png"),
    ("图5(b)", 37, (1000, 2300, 3434, 1834), "图5b_大论文图3-2_第二类子结构自由度选取_PDF37页_600dpi.png"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def render_full_page(pdftoppm: str, page: int, work_dir: Path) -> Path:
    output_stem = work_dir / f"page_{page}_600dpi"
    command = [
        pdftoppm,
        "-png",
        "-r",
        "600",
        "-f",
        str(page),
        "-l",
        str(page),
        "-singlefile",
        str(SOURCE_PDF),
        str(output_stem),
    ]
    subprocess.run(command, check=True)
    output_path = output_stem.with_suffix(".png")
    if not output_path.is_file():
        raise FileNotFoundError(f"PDF 页面渲染结果不存在：{output_path}")
    return output_path


def extract(output_dir: Path, overwrite: bool, verify: bool) -> None:
    if not SOURCE_PDF.is_file():
        raise FileNotFoundError(f"完整源 PDF 不存在：{SOURCE_PDF}")
    actual_pdf_hash = sha256(SOURCE_PDF)
    if actual_pdf_hash != EXPECTED_PDF_SHA256:
        raise RuntimeError(
            "完整源 PDF 的 SHA-256 与留档基线不一致："
            f"expected={EXPECTED_PDF_SHA256}, actual={actual_pdf_hash}"
        )

    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        raise FileNotFoundError("PATH 中未找到 pdftoppm。")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [output_dir / filename for _, _, _, filename in FIGURES]
    if not overwrite and any(path.exists() for path in existing):
        raise FileExistsError("输出目录已有同名文件；改用空目录，或显式传入 --overwrite。")

    page_paths: dict[int, Path] = {}
    results = []
    with tempfile.TemporaryDirectory(prefix="liangyu_original_figures_") as temp_name:
        temp_dir = Path(temp_name)
        for page in sorted({page for _, page, _, _ in FIGURES}):
            page_paths[page] = render_full_page(pdftoppm, page, temp_dir)

        for label, page, (x, y, width, height), filename in FIGURES:
            target = output_dir / filename
            with Image.open(page_paths[page]) as rendered_page:
                crop = rendered_page.crop((x, y, x + width, y + height))
                crop.save(target, dpi=(600, 600))

            pixel_match = None
            if verify:
                reference_path = REFERENCE_DIR / filename
                if not reference_path.is_file():
                    raise FileNotFoundError(f"像素核验基准不存在：{reference_path}")
                with Image.open(reference_path) as reference_image, Image.open(target) as actual_image:
                    reference_rgb = reference_image.convert("RGB")
                    actual_rgb = actual_image.convert("RGB")
                    pixel_match = (
                        reference_rgb.size == actual_rgb.size
                        and ImageChops.difference(reference_rgb, actual_rgb).getbbox() is None
                    )
                if not pixel_match:
                    raise RuntimeError(f"{label} 的重跑结果未通过逐像素核验：{target}")

            results.append((label, page, x, y, width, height, target, pixel_match))

    print(f"源 PDF SHA-256：{actual_pdf_hash}")
    for label, page, x, y, width, height, target, pixel_match in results:
        verification = "；逐像素核验=PASS" if pixel_match else ""
        print(
            f"{label}：PDF第{page}页，crop=({x},{y},{width},{height})，"
            f"输出={target}；SHA-256={sha256(target)}{verification}"
        )
    print(f"完成：{len(results)}/{len(FIGURES)} 幅。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从梁禹手稿完整 PDF 的 600 dpi 页面渲染结果中，仅按固定像素框裁出图1—图5的7个面板。"
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="输出目录；建议使用新的空目录。")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖输出目录中的同名结果。")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="将重跑图与归档的600 dpi使用版逐像素比较；任一不一致即返回失败。",
    )
    args = parser.parse_args()
    extract(args.output_dir.resolve(), args.overwrite, args.verify)


if __name__ == "__main__":
    main()
