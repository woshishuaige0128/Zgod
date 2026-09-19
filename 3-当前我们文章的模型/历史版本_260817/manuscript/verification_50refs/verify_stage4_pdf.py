from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tmp" / "pdfs" / "stage4_compile"
TEX = ROOT / "main_50refs_clean.tex"
BIB = ROOT / "reference_50refs_clean.bib"
PDF = BUILD / "main_50refs_clean.pdf"
LOG = BUILD / "main_50refs_clean.log"
BLG = BUILD / "main_50refs_clean.blg"
AUX = BUILD / "main_50refs_clean.aux"
BBL = BUILD / "main_50refs_clean.bbl"
REPORT = ROOT / "verification_50refs" / "stage4_pdf_validation.txt"

EXPECTED_TEX_SHA256 = "EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995"
EXPECTED_BIB_SHA256 = "7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A"


class Validation:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures: list[str] = []

    def record(self, label: str, actual: object, expected: object | None = None) -> None:
        if expected is None:
            self.lines.append(f"INFO  {label}: {actual}")
            return
        passed = actual == expected
        self.lines.append(
            f"{'PASS' if passed else 'FAIL'}  {label}: actual={actual!r}, expected={expected!r}"
        )
        if not passed:
            self.failures.append(label)

    def require(self, label: str, condition: bool, detail: str = "") -> None:
        self.lines.append(f"{'PASS' if condition else 'FAIL'}  {label}{': ' + detail if detail else ''}")
        if not condition:
            self.failures.append(label)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_text(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.decode("utf-8", errors="replace")


def is_red(color: object) -> bool:
    if not isinstance(color, (tuple, list)) or len(color) < 3:
        return False
    try:
        r, g, b = (float(color[0]), float(color[1]), float(color[2]))
    except (TypeError, ValueError):
        return False
    return r >= 0.75 and g <= 0.35 and b <= 0.35


def main() -> int:
    validation = Validation()
    required = [TEX, BIB, PDF, LOG, BLG, AUX, BBL]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    validation.require("required non-empty files", not missing, "; ".join(missing) if missing else "7/7")
    if missing:
        REPORT.write_text("\n".join(validation.lines) + "\nSTATUS: FAIL\n", encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"))
        return 1

    tex = TEX.read_text(encoding="utf-8")
    bib = BIB.read_text(encoding="utf-8")
    log = LOG.read_text(encoding="utf-8", errors="replace")
    blg = BLG.read_text(encoding="utf-8", errors="replace")
    aux = AUX.read_text(encoding="utf-8", errors="replace")
    bbl = BBL.read_text(encoding="utf-8", errors="replace")

    validation.record("TeX SHA-256", sha256(TEX), EXPECTED_TEX_SHA256)
    validation.record("BibTeX SHA-256", sha256(BIB), EXPECTED_BIB_SHA256)
    validation.record("PDF bytes", PDF.stat().st_size)
    validation.record("PDF SHA-256", sha256(PDF))

    forbidden_source = {
        r"\\rev": r"\\rev\b",
        r"\\citedoi": r"\\citedoi\b",
        r"\\newcitedoi": r"\\newcitedoi\b",
        r"\\newcommand": r"\\newcommand\b",
        r"\\nolinkurl": r"\\nolinkurl\b",
        "literal DOI": r"(?i)\bdoi\b",
        "red text command": r"(?i)\\(?:textcolor\s*\{\s*red\s*\}|color\s*\{\s*red\s*\})",
        r"\\safeincludegraphics": r"\\safeincludegraphics\b",
    }
    for label, pattern in forbidden_source.items():
        count = len(re.findall(pattern, tex)) + len(re.findall(pattern, bib))
        validation.record(f"forbidden source token {label}", count, 0)

    structure = {
        "sections": len(re.findall(r"\\section\{", tex)),
        "subsections": len(re.findall(r"\\subsection\{", tex)),
        "equation environments": len(re.findall(r"\\begin\{equation\}", tex)),
        "subequations environments": len(re.findall(r"\\begin\{subequations\}", tex)),
        "align environments": len(re.findall(r"\\begin\{align\}", tex)),
        "table environments": len(re.findall(r"\\begin\{table\}", tex)),
        "figure environments": len(re.findall(r"\\begin\{figure\}", tex)),
        "included graphics": len(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)),
    }
    expected_structure = {
        "sections": 6,
        "subsections": 12,
        "equation environments": 22,
        "subequations environments": 2,
        "align environments": 2,
        "table environments": 5,
        "figure environments": 9,
        "included graphics": 10,
    }
    for label, expected in expected_structure.items():
        validation.record(label, structure[label], expected)

    graphics = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)
    missing_graphics = [name for name in graphics if not (ROOT / "submit_figure" / name).is_file()]
    validation.require("all included graphics exist", not missing_graphics, ", ".join(missing_graphics) or "10/10")
    absent_from_log = [name for name in graphics if name not in log]
    validation.require("all included graphics loaded by pdfLaTeX", not absent_from_log, ", ".join(absent_from_log) or "10/10")

    citation_keys: list[str] = []
    for group in re.findall(r"\\citation\{([^}]*)\}", aux):
        citation_keys.extend(key.strip() for key in group.split(",") if key.strip())
    validation.record("citation occurrences", len(citation_keys), 60)
    validation.record("unique cited keys", len(set(citation_keys)), 50)
    validation.record("bibcite records", len(re.findall(r"\\bibcite\{", aux)), 50)
    validation.record("bibitems", len(re.findall(r"\\bibitem\[", bbl)), 50)
    validation.record("newlabel records", len(re.findall(r"\\newlabel\{", aux)), 59)

    bad_log_patterns = {
        "LaTeX errors": r"(?:^|\n)! LaTeX Error|Undefined control sequence|Emergency stop|Fatal error occurred",
        "undefined citations": r"Citation [`'][^\n]* undefined|There were undefined citations",
        "undefined references": r"Reference [`'][^\n]* undefined|There were undefined references",
        "rerun requests": r"Rerun to get|Label\(s\) may have changed",
        "overfull boxes": r"Overfull \\[hv]box",
        "underfull boxes": r"Underfull \\[hv]box",
        "missing characters": r"Missing character:",
        "missing files": r"LaTeX Error: File [`'][^\n]* not found|Figure file not found",
    }
    for label, pattern in bad_log_patterns.items():
        validation.record(label, len(re.findall(pattern, log, flags=re.MULTILINE)), 0)
    validation.record("BibTeX warnings", len(re.findall(r"^Warning--", blg, flags=re.MULTILINE)), 0)
    validation.record("BibTeX errors", len(re.findall(r"^I couldn't|^I'm skipping|---line", blg, flags=re.MULTILINE)), 0)
    validation.require("BibTeX completed", "You've used 50 entries" in blg, "50 entries")

    pdfinfo = run_text(["pdfinfo", str(PDF)])
    page_match = re.search(r"^Pages:\s+(\d+)", pdfinfo, flags=re.MULTILINE)
    validation.record("PDF pages", int(page_match.group(1)) if page_match else None, 28)
    validation.require("PDF is not encrypted", bool(re.search(r"^Encrypted:\s+no", pdfinfo, flags=re.MULTILINE)))

    text = run_text(["pdftotext", "-layout", "-enc", "UTF-8", str(PDF), "-"])
    forbidden_pdf_text = {
        "double question marks": r"\?\?",
        "citation placeholders": r"\[\?\]",
        "visible DOI": r"(?i)\bdoi\b",
        "visible nolinkurl": r"(?i)nolinkurl",
        "draft subtitle": r"Draft with Sections 2 to 5",
        "missing-figure notice": r"(?i)(?:figure file|file) not found",
        "visible revision command": r"\\rev\b",
    }
    for label, pattern in forbidden_pdf_text.items():
        validation.record(label, len(re.findall(pattern, text)), 0)
    normalized_text = re.sub(r"\s+", " ", text)
    validation.require(
        "title present",
        "On Craig–Bampton Model Reduction for Multi-Degree-of-Freedom Coupled Real-Time Hybrid Simulation"
        in normalized_text,
    )
    validation.require("abstract present", bool(re.search(r"\bABSTRACT\b", text, flags=re.IGNORECASE)))
    validation.require("references present", "References" in text)

    fonts = run_text(["pdffonts", str(PDF)])
    font_rows = [line for line in fonts.splitlines()[2:] if line.strip()]
    unembedded: list[str] = []
    for row in font_rows:
        parts = row.split()
        if len(parts) >= 5 and parts[-5].lower() != "yes":
            unembedded.append(row)
    validation.record("font records", len(font_rows), 28)
    validation.require("all fonts embedded", not unembedded, " | ".join(unembedded) or "28/28")

    red_chars: list[tuple[int, str, object]] = []
    out_of_bounds = 0
    page_char_counts: list[int] = []
    dimensions: set[tuple[float, float]] = set()
    color_counts: Counter[str] = Counter()
    with pdfplumber.open(PDF) as document:
        validation.record("pdfplumber pages", len(document.pages), 28)
        for page_number, page in enumerate(document.pages, start=1):
            dimensions.add((round(float(page.width), 2), round(float(page.height), 2)))
            page_char_counts.append(len(page.chars))
            for char in page.chars:
                color = char.get("non_stroking_color")
                color_counts[repr(color)] += 1
                if is_red(color):
                    red_chars.append((page_number, char.get("text", ""), color))
                if (
                    float(char.get("x0", 0.0)) < -0.5
                    or float(char.get("x1", 0.0)) > float(page.width) + 0.5
                    or float(char.get("top", 0.0)) < -0.5
                    or float(char.get("bottom", 0.0)) > float(page.height) + 0.5
                ):
                    out_of_bounds += 1
    validation.record("uniform page dimensions", len(dimensions), 1)
    validation.record("page dimensions", sorted(dimensions))
    validation.require("all pages contain extractable text", all(count > 0 for count in page_char_counts))
    validation.record("out-of-bounds text characters", out_of_bounds, 0)
    validation.record("red PDF text characters", len(red_chars), 0)
    validation.record("PDF text colors", dict(color_counts))

    status = "PASS" if not validation.failures else "FAIL"
    validation.lines.append(f"STATUS: {status}")
    if validation.failures:
        validation.lines.append("FAILED CHECKS: " + ", ".join(validation.failures))
    REPORT.write_text("\n".join(validation.lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
