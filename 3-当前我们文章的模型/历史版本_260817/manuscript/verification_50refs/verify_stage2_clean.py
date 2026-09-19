from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path


MANUSCRIPT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript")
ROOT = MANUSCRIPT.parent
SOURCE_TEX = ROOT / "temp_50refs_red_revision.tex"
SOURCE_BIB = ROOT / "rths_references_verified_expanded.bib"
OUTPUT_TEX = MANUSCRIPT / "main_50refs_clean.tex"
OUTPUT_BIB = MANUSCRIPT / "reference_50refs_clean.bib"
REPORT = MANUSCRIPT / "verification_50refs" / "stage2_content_audit.txt"

EXPECTED_SOURCE_TEX = "89D92852F461F26CCD7EC45E22CA8D7910A2E92C8FEA34950E6FC221A6461B73"
EXPECTED_SOURCE_BIB = "3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8"

FIGURE_PATHS = [
    "fig01_rths_loop_optionD.png",
    "fig03_benchmark_geometry_optionC.png",
    "fig04b_dof_idealized_optionD.png",
    "fig05a_divisionI_concept_optionD.png",
    "fig05b_divisionII_concept_optionD.png",
    "fig06_eq_div1.pdf",
    "fig07_eq_div2.pdf",
    "fig08_chirp_div1.pdf",
    "fig09_chirp_div2.pdf",
    "fig10_stability_domain.pdf",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def escaped(text: str, index: int) -> bool:
    count = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        count += 1
        index -= 1
    return count % 2 == 1


def group_at(text: str, opening: int) -> tuple[str, int]:
    assert text[opening] == "{"
    level = 0
    cursor = opening
    while cursor < len(text):
        if text[cursor] == "{" and not escaped(text, cursor):
            level += 1
        elif text[cursor] == "}" and not escaped(text, cursor):
            level -= 1
            if level == 0:
                return text[opening + 1 : cursor], cursor + 1
        cursor += 1
    raise AssertionError(f"Unclosed brace at {opening}")


def next_nonspace(text: str, cursor: int) -> int:
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    return cursor


def visible_derivative(text: str) -> tuple[str, Counter[str]]:
    output: list[str] = []
    counts: Counter[str] = Counter()
    cursor = 0
    commands = ("newcitedoi", "citedoi", "rev")
    while cursor < len(text):
        if text[cursor] != "\\":
            output.append(text[cursor])
            cursor += 1
            continue
        matched = next(
            (
                command
                for command in commands
                if text.startswith("\\" + command, cursor)
                and (
                    cursor + len(command) + 1 == len(text)
                    or not text[cursor + len(command) + 1].isalpha()
                )
            ),
            None,
        )
        if matched is None:
            output.append(text[cursor])
            cursor += 1
            continue
        first_opening = next_nonspace(text, cursor + len(matched) + 1)
        first, after_first = group_at(text, first_opening)
        if matched == "rev":
            output.append(first)
            cursor = after_first
        else:
            second_opening = next_nonspace(text, after_first)
            _, after_second = group_at(text, second_opening)
            output.append(r"\cite{" + first + "}")
            cursor = after_second
        counts[matched] += 1
    derivative = "".join(output)
    counts["safeincludegraphics"] = derivative.count(r"\safeincludegraphics")
    derivative = derivative.replace(r"\safeincludegraphics", r"\includegraphics")
    source_paths = re.findall(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", derivative
    )
    if source_paths:
        assert len(source_paths) == len(FIGURE_PATHS)
        for source, target in zip(source_paths, FIGURE_PATHS):
            derivative = derivative.replace("{" + source + "}", "{" + target + "}", 1)
    counts["mapped_figures"] = len(source_paths)
    return derivative, counts


def extract_between(text: str, start: str, end: str) -> str:
    start_position = text.index(start)
    end_position = text.index(end, start_position)
    return text[start_position:end_position]


def cite_keys(text: str) -> list[str]:
    return [
        key.strip()
        for group in re.findall(r"\\cite\{([^{}]+)\}", text)
        for key in group.split(",")
        if key.strip()
    ]


def command_targets(text: str, command: str) -> list[str]:
    return re.findall(rf"\\{command}\{{([^}}]+)\}}", text)


def environment_counts(text: str) -> tuple[Counter[str], Counter[str]]:
    return (
        Counter(re.findall(r"\\begin\{([^}]+)\}", text)),
        Counter(re.findall(r"\\end\{([^}]+)\}", text)),
    )


def parse_bib(text: str) -> dict[str, tuple[str, dict[str, str]]]:
    entries: dict[str, tuple[str, dict[str, str]]] = {}
    header = re.compile(r"(?m)^\s*@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,")
    matches = list(header.finditer(text))
    for match in matches:
        entry_type = match.group(1).lower()
        key = match.group(2)
        if key in entries:
            raise AssertionError(f"Duplicate BibTeX key: {key}")
        opening = text.find("{", match.start())
        body, _ = group_at(text, opening)
        body = body.split(",", 1)[1]
        fields: dict[str, str] = {}
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "}":
                continue
            field_match = re.match(
                r"^([A-Za-z][A-Za-z0-9_-]*)\s*=\s*\{(.*)\},?\s*$", stripped
            )
            if not field_match:
                continue
            name = field_match.group(1).lower()
            if name in fields:
                raise AssertionError(f"Duplicate field {name} in {key}")
            fields[name] = field_match.group(2)
        entries[key] = (entry_type, fields)
    return entries


def main() -> None:
    assert sha256(SOURCE_TEX) == EXPECTED_SOURCE_TEX
    assert sha256(SOURCE_BIB) == EXPECTED_SOURCE_BIB
    assert OUTPUT_TEX.is_file() and OUTPUT_BIB.is_file()

    source = SOURCE_TEX.read_text(encoding="utf-8")
    output = OUTPUT_TEX.read_text(encoding="utf-8")
    source_bib = SOURCE_BIB.read_text(encoding="utf-8")
    output_bib = OUTPUT_BIB.read_text(encoding="utf-8")

    source_abstract = extract_between(
        source, r"\begin{abstract}", r"\end{abstract}"
    )[len(r"\begin{abstract}") :]
    expected_abstract, abstract_counts = visible_derivative(source_abstract)
    output_abstract = extract_between(
        output, r"\begin{abstract}", r"\end{abstract}"
    )[len(r"\begin{abstract}") :]
    assert output_abstract.strip() == expected_abstract.strip()
    assert abstract_counts == Counter({"rev": 1})

    source_body = extract_between(
        source, r"\section{Introduction}", r"\bibliographystyle{unsrt}"
    )
    expected_body, body_counts = visible_derivative(source_body)
    output_body = extract_between(
        output,
        r"\section{Introduction}",
        r"\bibliographystyle{elsarticle-num-names}",
    )
    assert output_body.rstrip() == expected_body.rstrip(), "Clean body differs from source contract"
    assert body_counts == Counter(
        {
            "rev": 44,
            "newcitedoi": 35,
            "citedoi": 25,
            "safeincludegraphics": 10,
            "mapped_figures": 10,
        }
    )

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
    assert not {token: output.count(token) for token in forbidden if token in output}
    assert output.count(r"\documentclass[a4paper,fleqn,review,12pt]{cas-sc}") == 1
    assert output.count(r"\bibliographystyle{elsarticle-num-names}") == 1
    assert output.count(r"\bibliography{reference_50refs_clean}") == 1

    source_labels = command_targets(source_body, "label")
    output_labels = command_targets(output_body, "label")
    assert source_labels == output_labels
    assert len(output_labels) == len(set(output_labels)) == 59
    assert command_targets(source_body, "ref") == command_targets(output_body, "ref")
    assert command_targets(source_body, "eqref") == command_targets(output_body, "eqref")
    source_begins, source_ends = environment_counts(source_body)
    output_begins, output_ends = environment_counts(output_body)
    assert source_begins == source_ends == output_begins == output_ends

    output_cites = cite_keys(output_body)
    assert len(output_cites) == 60
    assert len(set(output_cites)) == 50
    figures = re.findall(
        r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", output_body
    )
    assert figures == FIGURE_PATHS
    for figure in figures:
        assert (MANUSCRIPT / "submit_figure" / figure).is_file()

    source_entries = parse_bib(source_bib)
    output_entries = parse_bib(output_bib)
    assert list(output_entries) == list(source_entries)
    assert len(output_entries) == 50
    for key, (source_type, source_fields) in source_entries.items():
        output_type, output_fields = output_entries[key]
        assert source_type == output_type
        expected_fields = {
            name: value
            for name, value in source_fields.items()
            if name not in {"doi", "note"}
        }
        assert output_fields == expected_fields, f"Unauthorized BibTeX field change: {key}"
        assert "doi" not in output_fields and "note" not in output_fields
    assert set(output_entries) == set(output_cites)
    assert r"\nolinkurl" not in output_bib

    report = [
        "RHTS STAGE 2 CLEAN SOURCE AUDIT",
        "",
        f"Output TeX: {OUTPUT_TEX}",
        f"TeX bytes: {OUTPUT_TEX.stat().st_size}",
        f"TeX SHA-256: {sha256(OUTPUT_TEX)}",
        f"Output BibTeX: {OUTPUT_BIB}",
        f"BibTeX bytes: {OUTPUT_BIB.stat().st_size}",
        f"BibTeX SHA-256: {sha256(OUTPUT_BIB)}",
        "",
        "PASS | Abstract equals the source abstract after removal of one rev wrapper",
        "PASS | Six-section body equals the source after only authorized wrapper, citation, and figure-path conversions",
        "PASS | rev wrappers removed: 45; their contents retained",
        "PASS | citedoi/newcitedoi converted to cite: 25/35",
        "PASS | safeincludegraphics converted to includegraphics: 10",
        "PASS | figure paths mapped to ten existing self-contained files",
        f"PASS | labels preserved in order: {len(output_labels)} unique",
        f"PASS | citation commands/unique keys: {len(output_cites)}/{len(set(output_cites))}",
        "PASS | all 50 citation keys match all 50 BibTeX keys",
        "PASS | all begin/end environment sequences remain balanced and unchanged",
        "PASS | forbidden revision, DOI, placeholder, and custom-command remnants: 0",
        "PASS | BibTeX differs only by removal of doi and note fields",
        "PASS | historical main.tex/reference.bib were not targeted",
        "",
        "NOTE | Bibliographic author and journal corrections remain workflow task 3.",
    ]
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
