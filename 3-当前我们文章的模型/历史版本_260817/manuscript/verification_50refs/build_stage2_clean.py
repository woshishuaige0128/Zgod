from __future__ import annotations

import hashlib
import re
from pathlib import Path


MANUSCRIPT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript")
ROOT = MANUSCRIPT.parent
SOURCE_TEX = ROOT / "temp_50refs_red_revision.tex"
SOURCE_BIB = ROOT / "rths_references_verified_expanded.bib"
HISTORICAL_CAS = MANUSCRIPT / "main.tex"
OUTPUT_TEX = MANUSCRIPT / "main_50refs_clean.tex"
OUTPUT_BIB = MANUSCRIPT / "reference_50refs_clean.bib"

EXPECTED_SOURCE_TEX = "89D92852F461F26CCD7EC45E22CA8D7910A2E92C8FEA34950E6FC221A6461B73"
EXPECTED_SOURCE_BIB = "3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8"
EXPECTED_HISTORICAL_CAS = "ACF20E8F6DD47CADAAB6A42A4D53CE0CA79557EEA14B97CD02E9242EBDC0DF18"

TITLE = (
    "On Craig--Bampton Model Reduction for Multi-Degree-of-Freedom Coupled "
    "Real-Time Hybrid Simulation"
)

FIGURE_MAP = {
    "figure/selected_v2/fig02_rths_loop_optionC.png": "fig01_rths_loop_optionD.png",
    "figure/selected_v2/fig03_benchmark_geometry_optionC.png": "fig03_benchmark_geometry_optionC.png",
    "figure/selected_v2/fig04b_dof_idealized_optionD.png": "fig04b_dof_idealized_optionD.png",
    "figure/selected_v2/fig05a_divisionI_concept_optionD.png": "fig05a_divisionI_concept_optionD.png",
    "figure/selected_v2/fig05b_divisionII_concept_optionD.png": "fig05b_divisionII_concept_optionD.png",
    "figure/results_v2/PDF/fig06_eq_div1.pdf": "fig06_eq_div1.pdf",
    "figure/results_v2/PDF/fig07_eq_div2.pdf": "fig07_eq_div2.pdf",
    "figure/results_v2/PDF/fig08_chirp_div1.pdf": "fig08_chirp_div1.pdf",
    "figure/results_v2/PDF/fig09_chirp_div2.pdf": "fig09_chirp_div2.pdf",
    "figure/results_v2/PDF/fig10_stability_domain.pdf": "fig10_stability_domain.pdf",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def frozen_text(path: Path, expected_hash: str) -> str:
    data = path.read_bytes()
    actual = sha256(data)
    if actual != expected_hash:
        raise RuntimeError(f"Frozen source changed: {path}\n{actual} != {expected_hash}")
    return data.decode("utf-8")


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return bool(backslashes % 2)


def read_group(text: str, opening: int) -> tuple[str, int]:
    if opening >= len(text) or text[opening] != "{":
        raise RuntimeError(f"Expected opening brace at offset {opening}")
    depth = 0
    for cursor in range(opening, len(text)):
        char = text[cursor]
        if char == "{" and not is_escaped(text, cursor):
            depth += 1
        elif char == "}" and not is_escaped(text, cursor):
            depth -= 1
            if depth == 0:
                return text[opening + 1 : cursor], cursor + 1
            if depth < 0:
                break
    raise RuntimeError(f"Unclosed group at offset {opening}")


def skip_space(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def replace_two_argument_command(text: str, command: str) -> tuple[str, int]:
    token = "\\" + command
    pieces: list[str] = []
    cursor = 0
    count = 0
    while cursor < len(text):
        start = text.find(token, cursor)
        if start < 0:
            pieces.append(text[cursor:])
            break
        after_token = start + len(token)
        if after_token < len(text) and text[after_token].isalpha():
            pieces.append(text[cursor:after_token])
            cursor = after_token
            continue
        pieces.append(text[cursor:start])
        first_opening = skip_space(text, after_token)
        first, after_first = read_group(text, first_opening)
        second_opening = skip_space(text, after_first)
        _, after_second = read_group(text, second_opening)
        pieces.append(r"\cite{" + first + "}")
        cursor = after_second
        count += 1
    return "".join(pieces), count


def unwrap_one_argument_command(text: str, command: str) -> tuple[str, int]:
    token = "\\" + command
    pieces: list[str] = []
    cursor = 0
    count = 0
    while cursor < len(text):
        start = text.find(token, cursor)
        if start < 0:
            pieces.append(text[cursor:])
            break
        after_token = start + len(token)
        if after_token < len(text) and text[after_token].isalpha():
            pieces.append(text[cursor:after_token])
            cursor = after_token
            continue
        pieces.append(text[cursor:start])
        opening = skip_space(text, after_token)
        content, after_group = read_group(text, opening)
        pieces.append(content)
        cursor = after_group
        count += 1
    return "".join(pieces), count


def clean_source_fragment(text: str) -> tuple[str, dict[str, int]]:
    text, newcitedoi = replace_two_argument_command(text, "newcitedoi")
    text, citedoi = replace_two_argument_command(text, "citedoi")
    text, rev = unwrap_one_argument_command(text, "rev")
    safeincludegraphics = text.count(r"\safeincludegraphics")
    text = text.replace(r"\safeincludegraphics", r"\includegraphics")

    mapped = 0
    for source, target in FIGURE_MAP.items():
        occurrences = text.count(source)
        text = text.replace(source, target)
        mapped += occurrences

    return text, {
        "newcitedoi": newcitedoi,
        "citedoi": citedoi,
        "rev": rev,
        "safeincludegraphics": safeincludegraphics,
        "mapped_figures": mapped,
    }


def source_abstract(source: str) -> str:
    match = re.search(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}", source, re.DOTALL
    )
    if not match:
        raise RuntimeError("Source abstract not found")
    cleaned, counts = clean_source_fragment(match.group(1))
    if counts != {
        "newcitedoi": 0,
        "citedoi": 0,
        "rev": 1,
        "safeincludegraphics": 0,
        "mapped_figures": 0,
    }:
        raise RuntimeError(f"Unexpected abstract cleanup counts: {counts}")
    return cleaned.strip()


def source_body(source: str) -> str:
    start = source.index(r"\section{Introduction}")
    end = source.index(r"\bibliographystyle{unsrt}", start)
    body, counts = clean_source_fragment(source[start:end])
    expected = {
        "newcitedoi": 35,
        "citedoi": 25,
        "rev": 44,
        "safeincludegraphics": 10,
        "mapped_figures": 10,
    }
    if counts != expected:
        raise RuntimeError(f"Unexpected body cleanup counts: {counts} != {expected}")
    return body.rstrip()


def clean_bibliography(source: str) -> tuple[str, int, int]:
    first_entry = source.index("@")
    body = source[first_entry:]
    kept: list[str] = []
    doi_removed = 0
    note_removed = 0
    for line in body.splitlines():
        if re.match(r"^\s*doi\s*=", line, re.IGNORECASE):
            doi_removed += 1
            continue
        if re.match(r"^\s*note\s*=", line, re.IGNORECASE):
            note_removed += 1
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip() + "\n"
    cleaned = re.sub(r",(\n\s*\})", r"\1", cleaned)
    header = (
        "% Clean 50-entry bibliography used by main_50refs_clean.tex.\n"
        "% Identifier display fields were removed from this derivative at the user's request.\n"
        "% Bibliographic name and journal metadata are verified in workflow task 3.\n\n"
    )
    return header + cleaned, doi_removed, note_removed


def build_tex(source: str, historical: str) -> str:
    if r"\documentclass[a4paper,fleqn,review,12pt]{cas-sc}" not in historical:
        raise RuntimeError("Historical CAS shell no longer has the expected document class")
    if historical.count(r"\author{Ning Li}") != 1:
        raise RuntimeError("Historical first author contract changed")
    if historical.count(r"\author{Yu Liang}") != 1:
        raise RuntimeError("Historical second author contract changed")
    source_title = re.search(r"\\title\{([^{}]+)\}", source)
    if not source_title or source_title.group(1) != TITLE:
        raise RuntimeError("Source title contract changed")

    abstract = source_abstract(source)
    body = source_body(source)
    return f"""\\documentclass[a4paper,fleqn,review,12pt]{{cas-sc}}

\\usepackage[numbers,sort&compress]{{natbib}}
\\usepackage{{amsmath,amssymb,bm}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}
\\usepackage{{lineno}}

\\graphicspath{{{{submit_figure/}}}}
\\hypersetup{{hidelinks}}
\\setcounter{{secnumdepth}}{{3}}
\\setlength{{\\emergencystretch}}{{2em}}
\\allowdisplaybreaks
\\AddToHook{{env/thebibliography/begin}}{{\\interlinepenalty=10000}}
\\numberwithin{{equation}}{{section}}

\\begin{{document}}
\\let\\WriteBookmarks\\relax
\\def\\floatpagepagefraction{{1}}
\\def\\textpagefraction{{.001}}

\\title[mode=title]{{{TITLE}}}

\\author{{Ning Li}}
\\author{{Yu Liang}}
% Affiliations, e-mail addresses, and the corresponding author were not supplied.

\\begin{{abstract}}
{abstract}
\\end{{abstract}}

% Keywords were not supplied.
\\shortauthors{{N. Li and Y. Liang}}
\\shorttitle{{Craig--Bampton Reduction for MDOF-Coupled RTHS}}

\\maketitle
\\linenumbers

{body}

\\bibliographystyle{{elsarticle-num-names}}
\\bibliography{{reference_50refs_clean}}

\\end{{document}}
"""


def write_deterministic(path: Path, data: str) -> None:
    encoded = data.encode("utf-8")
    if path.exists() and path.read_bytes() != encoded:
        raise RuntimeError(f"Refusing to overwrite non-matching existing derivative: {path}")
    path.write_bytes(encoded)


def main() -> None:
    source_tex = frozen_text(SOURCE_TEX, EXPECTED_SOURCE_TEX)
    source_bib = frozen_text(SOURCE_BIB, EXPECTED_SOURCE_BIB)
    historical = frozen_text(HISTORICAL_CAS, EXPECTED_HISTORICAL_CAS)

    output_tex = build_tex(source_tex, historical)
    output_bib, doi_removed, note_removed = clean_bibliography(source_bib)
    if (doi_removed, note_removed) != (50, 50):
        raise RuntimeError(
            f"Expected to remove 50 doi and 50 note fields, got {doi_removed}/{note_removed}"
        )

    forbidden_tex = [
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
    ]
    leftovers = [token for token in forbidden_tex if token in output_tex]
    if leftovers:
        raise RuntimeError(f"Forbidden TeX remnants: {leftovers}")

    write_deterministic(OUTPUT_TEX, output_tex)
    write_deterministic(OUTPUT_BIB, output_bib)

    print(f"WROTE | {OUTPUT_TEX}")
    print(f"BYTES | {OUTPUT_TEX.stat().st_size}")
    print(f"SHA256 | {sha256(OUTPUT_TEX.read_bytes())}")
    print(f"WROTE | {OUTPUT_BIB}")
    print(f"BYTES | {OUTPUT_BIB.stat().st_size}")
    print(f"SHA256 | {sha256(OUTPUT_BIB.read_bytes())}")
    print("REMOVED | rev wrappers: 45")
    print("CONVERTED | citedoi/newcitedoi: 25/35")
    print("CONVERTED | safeincludegraphics: 10")
    print("MAPPED | figure paths: 10")
    print(f"REMOVED | BibTeX doi/note fields: {doi_removed}/{note_removed}")


if __name__ == "__main__":
    main()
