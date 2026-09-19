from __future__ import annotations

import hashlib
import re
from pathlib import Path


MANUSCRIPT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript")
ROOT = MANUSCRIPT.parent

EXPECTED = {
    ROOT / "temp_50refs_red_revision.tex": ("89D92852F461F26CCD7EC45E22CA8D7910A2E92C8FEA34950E6FC221A6461B73", 55645),
    ROOT / "temp_50refs_red_revision.pdf": ("4FA95231518B4837D5A10F32D78BE4EAE1D74FEDA98FEC75ACCFEDE01853E93E", 1282220),
    ROOT / "rths_references_verified_expanded.bib": ("3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8", 21551),
    MANUSCRIPT / "main.tex": ("ACF20E8F6DD47CADAAB6A42A4D53CE0CA79557EEA14B97CD02E9242EBDC0DF18", 61277),
    MANUSCRIPT / "reference.bib": ("0AD91DD3CF150DF5ABD35B330E41D0D7A02B46B37344BFFE358695580C5EB0DF", 3163),
    MANUSCRIPT / "main.pdf": ("CFCC03362FCAA27641266C4EC7894DDEEFFBB2AF0F0D4A1896E3D9389C06058A", 1487451),
    MANUSCRIPT / "cas-sc.cls": ("0BA919511E97AF9E37C3056B7674D2A7CEA225208AFC6A412EC510284BBFF777", 4410),
    MANUSCRIPT / "cas-common.sty": ("D830C770F805C1A3ABF3EB413F3B14A40B515E1E46378E33F09BCD974CEFE6C7", 76432),
    MANUSCRIPT / "elsarticle-num-names.bst": ("F7B33FBA01050D3F65F56088BB4D4551A05B8C554F4D1884DF9222A1E6DB8E6B", 28892),
    MANUSCRIPT / "submit_figure" / "fig01_rths_loop_optionD.png": ("92E92289886561083AB92DB3087B3777A07BE04A1C5B1F35BED5FC40BE143C56", 136723),
    MANUSCRIPT / "submit_figure" / "fig03_benchmark_geometry_optionC.png": ("C7A158F44B8E938A683DB1D08C3B5CAA3181F52B84EE4AC2FFA1B22502D8AB48", 123436),
    MANUSCRIPT / "submit_figure" / "fig04b_dof_idealized_optionD.png": ("CAD6994A2C9979D3F2F452097282202F401CDA87BDE22D33E2642704B56AC1FB", 124387),
    MANUSCRIPT / "submit_figure" / "fig05a_divisionI_concept_optionD.png": ("2A6F1DB254E664D38F3C7E45309C9B01DA45CEAEDEFD26F6E8DB2D5F1F038D13", 176500),
    MANUSCRIPT / "submit_figure" / "fig05b_divisionII_concept_optionD.png": ("54E8E86F1F0D3924F19456014BBCF6AE93FF2648981BB7AF5F4E28351E70493B", 191348),
    MANUSCRIPT / "submit_figure" / "fig06_eq_div1.pdf": ("D330C293C415309179514169A503F2E7BEDA8329E1FCFE07F79C5286CA48FFF0", 156950),
    MANUSCRIPT / "submit_figure" / "fig07_eq_div2.pdf": ("CA4AE65E23994059A6BB3BB2BB44E11526CAC47CC81B2A83775F79760910BC5F", 158583),
    MANUSCRIPT / "submit_figure" / "fig08_chirp_div1.pdf": ("7FBF5443DD6E1CC541C808992DF038139828CC1B4757376CC31C6C842F8626FC", 170070),
    MANUSCRIPT / "submit_figure" / "fig09_chirp_div2.pdf": ("3C3EEE3D8DF36501DC23A4669622EB2336C960CF57DB1816500386373145F5CF", 172548),
    MANUSCRIPT / "submit_figure" / "fig10_stability_domain.pdf": ("EEA26CEFA38B9666AEF48C6E9355B8B23C14365F8D0DFFBD1E8E2E61646B9847", 104941),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def citation_keys(tex: str) -> list[str]:
    keys: list[str] = []
    pattern = re.compile(
        r"\\(?:new)?citedoi\s*\{([^{}]+)\}\s*\{[^{}]*\}"
        r"|\\cite\s*\{([^{}]+)\}"
    )
    for match in pattern.finditer(tex):
        raw = match.group(1) or match.group(2)
        if raw == "#1":
            continue
        keys.extend(key.strip() for key in raw.split(",") if key.strip())
    return keys


def main() -> None:
    for path, (expected_hash, expected_size) in EXPECTED.items():
        assert path.is_file(), f"Missing frozen file: {path}"
        assert path.stat().st_size == expected_size, f"Size changed: {path}"
        assert sha256(path) == expected_hash, f"Hash changed: {path}"

    tex_path = ROOT / "temp_50refs_red_revision.tex"
    bib_path = ROOT / "rths_references_verified_expanded.bib"
    tex = tex_path.read_text(encoding="utf-8")
    bib = bib_path.read_text(encoding="utf-8")

    cited = citation_keys(tex)
    unique_cited = set(cited)
    bib_keys = re.findall(r"(?m)^\s*@\w+\s*\{\s*([^,\s]+)\s*,", bib)

    assert len(cited) == 60
    assert len(unique_cited) == 50
    assert len(bib_keys) == len(set(bib_keys)) == 50
    assert unique_cited == set(bib_keys)
    assert tex.count(r"\rev{") == 45
    assert tex.count(r"\citedoi{") == 25
    assert tex.count(r"\newcitedoi{") == 35
    assert tex.count(r"\newcommand") == 6
    assert tex.count(r"\safeincludegraphics") == 11

    source_paths = re.findall(
        r"\\safeincludegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex
    )
    assert len(source_paths) == 10
    missing = [path for path in source_paths if not (ROOT / path).is_file()]
    assert missing == ["figure/selected_v2/fig02_rths_loop_optionC.png"]

    print(f"PASS | frozen files: {len(EXPECTED)}")
    print(f"PASS | citation commands: {len(cited)}")
    print(f"PASS | unique citation keys: {len(unique_cited)}")
    print(f"PASS | BibTeX entries: {len(bib_keys)}")
    print("PASS | missing citation keys: 0")
    print("PASS | uncited BibTeX entries: 0")
    print("PASS | rev/citedoi/newcitedoi/newcommand: 45/25/35/6")
    print(f"PASS | expected missing figure path: {missing[0]}")


if __name__ == "__main__":
    main()
