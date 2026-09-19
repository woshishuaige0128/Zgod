from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pdfplumber


MANUSCRIPT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript")
ROOT = MANUSCRIPT.parent
VERIFY = MANUSCRIPT / "verification_50refs"
SOURCE_TEX = ROOT / "temp_50refs_red_revision.tex"
OUTPUT_TEX = MANUSCRIPT / "main_50refs_clean.tex"
OUTPUT_BIB = MANUSCRIPT / "reference_50refs_clean.bib"
OUTPUT_PDF = MANUSCRIPT / "main_50refs_clean.pdf"
ACCEPTED_PDF = MANUSCRIPT / "tmp" / "pdfs" / "stage4_compile" / "main_50refs_clean.pdf"
REPORT = VERIFY / "stage5_delivery_validation.txt"
MANIFEST = MANUSCRIPT / "final_delivery_manifest.md"

EXPECTED_TEX_SHA256 = "EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995"
EXPECTED_BIB_SHA256 = "7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A"
EXPECTED_PDF_SHA256 = "11E649BD0C471AFA831441AA2BB01CDF5B809383BEF4BAB31B65103A82323101"

USED_FIGURES = {
    "fig01_rths_loop_optionD.png": "92E92289886561083AB92DB3087B3777A07BE04A1C5B1F35BED5FC40BE143C56",
    "fig03_benchmark_geometry_optionC.png": "C7A158F44B8E938A683DB1D08C3B5CAA3181F52B84EE4AC2FFA1B22502D8AB48",
    "fig04b_dof_idealized_optionD.png": "CAD6994A2C9979D3F2F452097282202F401CDA87BDE22D33E2642704B56AC1FB",
    "fig05a_divisionI_concept_optionD.png": "2A6F1DB254E664D38F3C7E45309C9B01DA45CEAEDEFD26F6E8DB2D5F1F038D13",
    "fig05b_divisionII_concept_optionD.png": "54E8E86F1F0D3924F19456014BBCF6AE93FF2648981BB7AF5F4E28351E70493B",
    "fig06_eq_div1.pdf": "D330C293C415309179514169A503F2E7BEDA8329E1FCFE07F79C5286CA48FFF0",
    "fig07_eq_div2.pdf": "CA4AE65E23994059A6BB3BB2BB44E11526CAC47CC81B2A83775F79760910BC5F",
    "fig08_chirp_div1.pdf": "7FBF5443DD6E1CC541C808992DF038139828CC1B4757376CC31C6C842F8626FC",
    "fig09_chirp_div2.pdf": "3C3EEE3D8DF36501DC23A4669622EB2336C960CF57DB1816500386373145F5CF",
    "fig10_stability_domain.pdf": "EEA26CEFA38B9666AEF48C6E9355B8B23C14365F8D0DFFBD1E8E2E61646B9847",
}

SUPPORT_FILES = [
    "cas-sc.cls",
    "cas-common.sty",
    "elsarticle-num-names.bst",
    "cas-email.jpeg",
    "cas-facebook.jpeg",
    "cas-gplus.jpeg",
    "cas-linkedin.jpeg",
    "cas-twitter.jpeg",
    "cas-url.jpeg",
]


class Checks:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures: list[str] = []

    def equal(self, label: str, actual: object, expected: object) -> None:
        passed = actual == expected
        self.lines.append(
            f"{'PASS' if passed else 'FAIL'} | {label}: actual={actual!r}, expected={expected!r}"
        )
        if not passed:
            self.failures.append(label)

    def require(self, label: str, condition: bool, detail: str = "") -> None:
        self.lines.append(f"{'PASS' if condition else 'FAIL'} | {label}{': ' + detail if detail else ''}")
        if not condition:
            self.failures.append(label)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.returncode, completed.stdout.decode("utf-8", errors="replace")


def run_checked_text(command: list[str]) -> str:
    code, output = run(command, MANUSCRIPT)
    if code != 0:
        raise RuntimeError(f"Command failed ({code}): {' '.join(command)}\n{output}")
    return output


def load_stage2_helpers():
    sys.path.insert(0, str(VERIFY))
    import verify_stage2_clean as helpers  # type: ignore

    return helpers


def check_text_contract(checks: Checks) -> None:
    helpers = load_stage2_helpers()
    source = SOURCE_TEX.read_text(encoding="utf-8")
    output = OUTPUT_TEX.read_text(encoding="utf-8")

    source_abstract = helpers.extract_between(
        source, r"\begin{abstract}", r"\end{abstract}"
    )[len(r"\begin{abstract}") :]
    expected_abstract, abstract_counts = helpers.visible_derivative(source_abstract)
    output_abstract = helpers.extract_between(
        output, r"\begin{abstract}", r"\end{abstract}"
    )[len(r"\begin{abstract}") :]
    checks.require(
        "abstract equals source after removing only its rev wrapper",
        output_abstract.strip() == expected_abstract.strip(),
    )
    checks.equal("abstract wrapper removal", abstract_counts, Counter({"rev": 1}))

    source_body = helpers.extract_between(
        source, r"\section{Introduction}", r"\bibliographystyle{unsrt}"
    )
    expected_body, body_counts = helpers.visible_derivative(source_body)
    output_body = helpers.extract_between(
        output,
        r"\section{Introduction}",
        r"\bibliographystyle{elsarticle-num-names}",
    )
    checks.require(
        "six-section body equals source after authorized wrapper/citation/figure conversions",
        output_body.rstrip() == expected_body.rstrip(),
    )
    checks.equal(
        "authorized body conversion counts",
        body_counts,
        Counter(
            {
                "rev": 44,
                "newcitedoi": 35,
                "citedoi": 25,
                "safeincludegraphics": 10,
                "mapped_figures": 10,
            }
        ),
    )

    labels = helpers.command_targets(output_body, "label")
    cites = helpers.cite_keys(output_body)
    figures = re.findall(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", output_body
    )
    checks.equal("unique labels", len(set(labels)), 59)
    checks.equal("citation occurrences", len(cites), 60)
    checks.equal("unique citation keys", len(set(cites)), 50)
    checks.equal("used image order", figures, list(USED_FIGURES))
    begins, ends = helpers.environment_counts(output_body)
    checks.require("balanced environments", begins == ends)

    forbidden = [
        r"\newcommand",
        r"\rev",
        r"\citedoi",
        r"\newcitedoi",
        r"\doimark",
        r"\todo",
        r"\textcolor",
        r"\color{red}",
        r"\nolinkurl",
        r"\safeincludegraphics",
        "[DOI",
        "Figure file not found",
        "Draft with Sections 2 to 5",
    ]
    present = {token: output.count(token) for token in forbidden if token in output}
    checks.require("forbidden TeX remnants are absent", not present, repr(present) if present else "0")
    checks.equal("parent-directory references in TeX", output.count("../"), 0)
    checks.require(
        "local bibliography selected",
        r"\bibliography{reference_50refs_clean}" in output,
    )


def is_red(color: object) -> bool:
    if not isinstance(color, (tuple, list)) or len(color) < 3:
        return False
    try:
        red, green, blue = map(float, color[:3])
    except (TypeError, ValueError):
        return False
    return red >= 0.75 and green <= 0.35 and blue <= 0.35


def check_final_pdf(checks: Checks) -> dict[str, object]:
    checks.require("accepted Stage 4 PDF exists", ACCEPTED_PDF.is_file())
    checks.require("formal final PDF exists", OUTPUT_PDF.is_file())
    if not ACCEPTED_PDF.is_file() or not OUTPUT_PDF.is_file():
        return {}
    checks.equal("accepted PDF SHA-256", sha256(ACCEPTED_PDF), EXPECTED_PDF_SHA256)
    checks.equal("final PDF SHA-256", sha256(OUTPUT_PDF), EXPECTED_PDF_SHA256)
    checks.require(
        "final/accepted PDF byte equality",
        OUTPUT_PDF.read_bytes() == ACCEPTED_PDF.read_bytes(),
    )

    info = run_checked_text(["pdfinfo", str(OUTPUT_PDF)])
    page_match = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
    size_match = re.search(r"^Page size:\s+([^\r\n]+)", info, flags=re.MULTILINE)
    checks.equal("final PDF pages", int(page_match.group(1)) if page_match else None, 28)
    checks.require("final PDF is not encrypted", bool(re.search(r"^Encrypted:\s+no", info, flags=re.MULTILINE)))

    text = run_checked_text(["pdftotext", "-layout", "-enc", "UTF-8", str(OUTPUT_PDF), "-"])
    forbidden = {
        "double question marks": r"\?\?",
        "citation placeholders": r"\[\?\]",
        "visible DOI": r"(?i)\bdoi\b",
        "visible nolinkurl": r"(?i)nolinkurl",
        "draft subtitle": r"Draft with Sections 2 to 5",
        "missing-figure notice": r"(?i)(?:figure file|file) not found",
        "visible rev command": r"\\rev\b",
    }
    for label, pattern in forbidden.items():
        checks.equal(label, len(re.findall(pattern, text)), 0)

    fonts = run_checked_text(["pdffonts", str(OUTPUT_PDF)])
    rows = [line for line in fonts.splitlines()[2:] if line.strip()]
    unembedded = [row for row in rows if len(row.split()) >= 5 and row.split()[-5].lower() != "yes"]
    checks.equal("font records", len(rows), 28)
    checks.require("all fonts embedded", not unembedded, " | ".join(unembedded) or "28/28")

    red_chars = 0
    out_of_bounds = 0
    dimensions: set[tuple[float, float]] = set()
    with pdfplumber.open(OUTPUT_PDF) as document:
        checks.equal("pdfplumber pages", len(document.pages), 28)
        for page in document.pages:
            dimensions.add((round(float(page.width), 2), round(float(page.height), 2)))
            for char in page.chars:
                if is_red(char.get("non_stroking_color")):
                    red_chars += 1
                if (
                    float(char.get("x0", 0.0)) < -0.5
                    or float(char.get("x1", 0.0)) > float(page.width) + 0.5
                    or float(char.get("top", 0.0)) < -0.5
                    or float(char.get("bottom", 0.0)) > float(page.height) + 0.5
                ):
                    out_of_bounds += 1
    checks.equal("uniform final PDF dimensions", len(dimensions), 1)
    checks.equal("red PDF text characters", red_chars, 0)
    checks.equal("out-of-bounds PDF text characters", out_of_bounds, 0)
    return {
        "pages": 28,
        "page_size": size_match.group(1).strip() if size_match else "unavailable",
        "fonts": len(rows),
    }


def file_row(path: Path, display: str) -> str:
    return f"| `{display}` | {path.stat().st_size:,} | `{sha256(path)}` |"


def main() -> int:
    checks = Checks()
    required = [OUTPUT_TEX, OUTPUT_BIB, OUTPUT_PDF, ACCEPTED_PDF]
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    checks.require("primary files exist and are non-empty", not missing, "; ".join(missing) or "4/4")
    if missing:
        REPORT.write_text("\n".join(checks.lines) + "\nSTATUS: FAIL\n", encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), end="")
        return 1

    checks.equal("formal TeX SHA-256", sha256(OUTPUT_TEX), EXPECTED_TEX_SHA256)
    checks.equal("formal BibTeX SHA-256", sha256(OUTPUT_BIB), EXPECTED_BIB_SHA256)
    check_text_contract(checks)

    bib = OUTPUT_BIB.read_text(encoding="utf-8")
    checks.equal("final BibTeX DOI literals", len(re.findall(r"(?i)\bdoi\b", bib)), 0)
    checks.equal("final BibTeX nolinkurl literals", bib.count(r"\nolinkurl"), 0)
    checks.equal("final BibTeX entries", len(re.findall(r"(?m)^\s*@\w+\s*\{", bib)), 50)

    for name, expected_hash in USED_FIGURES.items():
        path = MANUSCRIPT / "submit_figure" / name
        checks.require(f"used image exists: {name}", path.is_file())
        if path.is_file():
            checks.equal(f"used image hash: {name}", sha256(path), expected_hash)
    for name in SUPPORT_FILES:
        checks.require(f"local support file exists: {name}", (MANUSCRIPT / name).is_file())

    pdf_summary = check_final_pdf(checks)

    subprocess_checks = [
        ("frozen-source validator", VERIFY / "verify_frozen_sources.py"),
        ("Stage 3 bibliography validator", VERIFY / "verify_stage3_bib.py"),
        ("Stage 4 PDF validator", VERIFY / "verify_stage4_pdf.py"),
    ]
    subprocess_outputs: list[str] = []
    for label, script in subprocess_checks:
        code, output = run([sys.executable, str(script)], MANUSCRIPT)
        checks.equal(f"{label} exit code", code, 0)
        checks.require(f"{label} PASS marker", "PASS" in output and "FAIL" not in output)
        subprocess_outputs.append(f"## {label}\n{output.strip()}")

    final_status = "PASS" if not checks.failures else "FAIL"
    checks.lines.append(f"STATUS: {final_status}")
    if checks.failures:
        checks.lines.append("FAILED CHECKS: " + ", ".join(checks.failures))
    checks.lines.extend(["", *subprocess_outputs])
    REPORT.write_text("\n".join(checks.lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(checks.lines))
    if final_status != "PASS":
        return 1

    primary = [
        (OUTPUT_TEX, "main_50refs_clean.tex"),
        (OUTPUT_BIB, "reference_50refs_clean.bib"),
        (OUTPUT_PDF, "main_50refs_clean.pdf"),
    ]
    support = [(MANUSCRIPT / name, name) for name in SUPPORT_FILES]
    figures = [(MANUSCRIPT / "submit_figure" / name, f"submit_figure/{name}") for name in USED_FIGURES]
    reports = [
        (VERIFY / "source_manifest.md", "verification_50refs/source_manifest.md"),
        (VERIFY / "stage3_metadata_audit.md", "verification_50refs/stage3_metadata_audit.md"),
        (VERIFY / "stage4_full_pdf_audit.md", "verification_50refs/stage4_full_pdf_audit.md"),
        (VERIFY / "stage5_delivery_validation.txt", "verification_50refs/stage5_delivery_validation.txt"),
    ]
    manifest_lines = [
        "# RHTS 50-reference clean manuscript final delivery manifest",
        "",
        "- Date: 2026-09-03 (Asia/Shanghai)",
        "- Status: PASS",
        "- Delivery directory: `D:/JZ_PhD/10_论文_Papers/Li/RHTS/260817/manuscript`",
        "- The three primary deliverables are independent files and do not overwrite historical `main.tex`, `reference.bib`, or `main.pdf`.",
        "",
        "## Primary deliverables",
        "",
        "| File | Bytes | SHA-256 |",
        "|---|---:|---|",
        *(file_row(path, display) for path, display in primary),
        "",
        "## Final acceptance",
        "",
        f"- PDF pages: {pdf_summary.get('pages', 'unavailable')}",
        f"- PDF page size: {pdf_summary.get('page_size', 'unavailable')}",
        f"- Embedded font records: {pdf_summary.get('fonts', 'unavailable')}",
        "- Citation occurrences / unique keys / bibliography entries: 60 / 50 / 50",
        "- Sections / subsections / equation environments / tables / figure environments / images: 6 / 12 / 22 / 5 / 9 / 10",
        "- LaTeX errors, undefined citations/references, missing images, visible DOI, red revision text, and placeholder question marks: 0",
        "- All 28 pages were rendered and inspected in Stage 4; the final PDF is byte-identical to that accepted PDF.",
        "",
        "## Local compile support",
        "",
        "| File | Bytes | SHA-256 |",
        "|---|---:|---|",
        *(file_row(path, display) for path, display in support),
        "",
        "## Images used by the final TeX",
        "",
        "| File | Bytes | SHA-256 |",
        "|---|---:|---|",
        *(file_row(path, display) for path, display in figures),
        "",
        "## Verification evidence",
        "",
        "| File | Bytes | SHA-256 |",
        "|---|---:|---|",
        *(file_row(path, display) for path, display in reports),
        "",
        "## Recompile from the delivery directory",
        "",
        "```text",
        "pdflatex -interaction=nonstopmode -halt-on-error main_50refs_clean.tex",
        "bibtex main_50refs_clean",
        "pdflatex -interaction=nonstopmode -halt-on-error main_50refs_clean.tex",
        "pdflatex -interaction=nonstopmode -halt-on-error main_50refs_clean.tex",
        "```",
        "",
        "Run BibTeX from inside the delivery directory using the job basename, rather than passing the full Chinese absolute path.",
        "",
        "## Protected-source result",
        "",
        "The frozen-source validator passed all 19 protected inputs, including the user-provided revised TeX/PDF/BibTeX, historical `main.tex`/`reference.bib`/`main.pdf`, template files, and ten used figures. The GPT-provided `apply_rths_references.py` was not executed.",
        "",
        "## Known source boundaries",
        "",
        "- Figure 1 uses the available Chinese general RHTS closed-loop asset; it does not explicitly depict every independent actuator-delay channel named in its unchanged English caption.",
        "- Several protected source images retain internal Chinese figure numbers.",
        "- Affiliations, keywords, and ORCID values were not provided and were not invented.",
        "- The sentence ending page 19 continues intact on page 21 after the full-page placement of Figures 5 and 6 on page 20; no text is missing.",
        "",
    ]
    MANIFEST.write_text("\n".join(manifest_lines), encoding="utf-8", newline="\n")
    print(f"MANIFEST: {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
