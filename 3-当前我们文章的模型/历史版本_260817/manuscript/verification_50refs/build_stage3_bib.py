#!/usr/bin/env python3
"""Build the Stage 3 corrected bibliography as an isolated candidate."""

from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANUSCRIPT = HERE.parent
ROOT = MANUSCRIPT.parent
SOURCE_BIB = ROOT / "rths_references_verified_expanded.bib"
OLD_VERIFIED_BIB = ROOT / "citation_clean_20260831" / "rths_references_verified.bib"
TARGET_BIB = MANUSCRIPT / "reference_50refs_clean.bib"
CROSSREF_CACHE = HERE / "crossref_metadata_50.json"
CANDIDATE_BIB = HERE / "reference_50refs_stage3_candidate.bib"

EXPECTED_SOURCE_HASH = "3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8"
EXPECTED_OLD_HASH = "71D767B20073D1D87A151A57EF1A80BC1A45CBEC5989F75205BABF4FE1449DF9"
EXPECTED_STAGE2_HASH = "F48DD73DF3DF7927E90D07C1B81D24A540079A081B9039D494250E6078BB77EA"

AUTHOR_FIELDS = {
    "Takanashi1987": "Takanashi, Koichi and Nakashima, Masayoshi",
    "Mahin1989": "Mahin, Stephen A. and Shing, Pui-Shum B. and Thewalt, Christopher R. and Hanson, Robert D.",
    "Nakashima1992": "Nakashima, Masayoshi and Kato, Hiroto and Takaoka, Eiji",
    "NakashimaMasaoka1999": "Nakashima, Masayoshi and Masaoka, Nobuaki",
    "Horiuchi1999": "Horiuchi, Toshihiko and Inoue, M. and Konno, Takao and Namita, Y.",
    "Pan2005": "Pan, Peng and Nakashima, Masayoshi and Tomofuji, Hiroshi",
    "Shao2011": "Shao, Xiaoyun and Reinhorn, Andrei M. and Sivaselvan, Mettupalayam V.",
    "Gao2013": "Gao, Xiuyu and Castaneda, Nestor and Dyke, Shirley J.",
    "Phillips2013": "Phillips, Brian M. and Spencer, Jr., Billie F.",
    "Phillips2013Feedforward": "Phillips, Brian M. and Spencer, Jr., Billie F.",
    "Fermandois2017": "Fermandois, Gaston A. and Spencer, Jr., Billie F.",
    "Najafi2020": "Najafi, Amirali and Fermandois, Gaston A. and Spencer, Jr., Billie F.",
    "NajafiSpencer2021": "Najafi, Amirali and Spencer, Jr., Billie F.",
    "Najafi2023": "Najafi, Amirali and Fermandois, Gaston A. and Dyke, Shirley J. and Spencer, Jr., Billie F.",
    "Condori2023": "Condori Uribe, Johnny W. and Salmeron, Manuel and Patino, Edwin and Montoya, Herta and Dyke, Shirley J. and Silva, Christian E. and Maghareh, Amin and Najarian, Mehdi and Montoya, Arturo",
    "Quiroz2024": r"Quiroz, Mar{\'i}a and G{\'a}lmez, Crist{\'o}bal and Fermandois, Gast{\'o}n A.",
    "RuizSong2024": "Ruiz, Santiago and Song, Wei",
    "Xu2024": "Xu, Weijie and Meng, Xiangjin and Chen, Cheng and Guo, Tong and Peng, Changle",
    "Shangguan2024": "Shangguan, Yuekun and Wang, Zhen and Guo, Yu and Chen, Yucai and Zeng, Yunhai and Zhou, Huimeng",
    "Silva2020": "Silva, Christian E. and Gomez, Daniel and Maghareh, Amin and Dyke, Shirley J. and Spencer, Jr., Billie F.",
    "PalacioBetancur2023": "Palacio-Betancur, Alejandro and Gutierrez Soto, Mariantonieta",
    "Guyan1965": "Guyan, Robert J.",
    "Hurty1965": "Hurty, Walter C.",
    "CraigBampton1968": "Craig, Jr., Roy R. and Bampton, Mervyn C. C.",
    "MacNeal1971": "MacNeal, Richard H.",
    "Rubin1975": "Rubin, Sylvan",
    "Besselink2013": "Besselink, B. and Tabak, U. and Lutowska, A. and van de Wouw, N. and Nijmeijer, H. and Rixen, D. J. and Hochstenbach, M. E. and Schilders, W. H. A.",
    "Benner2015": "Benner, Peter and Gugercin, Serkan and Willcox, Karen",
    "Krattiger2019": "Krattiger, Dimitri and Wu, Long and Zacharczuk, Martin and Buck, Martin and Kuether, Robert J. and Allen, Matthew S. and Tiso, Paolo and Brake, Matthew R. W.",
    "Miraglia2020": r"Miraglia, Gaetano and Petrovic, Milos and Abbiati, Giuseppe and Mojsilovic, Nebojsa and Stojadinovi{\'c}, Bozidar",
    "Tsokanas2022": r"Tsokanas, Nikolaos and Simpson, Thomas and Pastorino, Roland and Chatzi, Eleni and Stojadinovi{\'c}, Bozidar",
    "Mucha2023": "Mucha, Waldemar",
    "Zhang2024": "Zhang, Jian and Ding, Hao and Wang, Jin-Ting and Altay, Okyay",
    "Darby2002": "Darby, A. P. and Williams, M. S. and Blakeborough, A.",
    "Wu2005": "Wu, Bin and Bao, H. and Ou, Jinping and Tian, S.",
    "Wallace2005": "Wallace, M. I. and Sieber, J. and Neild, S. A. and Wagg, D. J. and Krauskopf, B.",
    "MercanRicles2007": "Mercan, Oya and Ricles, James M.",
    "Mercan2008": "Mercan, Oya and Ricles, James M.",
    "ChenRicles2008": "Chen, Cheng and Ricles, James M.",
    "ChenRiclesMarullo2009": "Chen, Cheng and Ricles, James M. and Marullo, Thomas M. and Mercan, Oya",
    "ChenRicles2009Delay": "Chen, Cheng and Ricles, James M.",
    "ChenRicles2012": "Chen, Cheng and Ricles, James M.",
    "Chae2013": "Chae, Yunbyeong and Kazemibidokhti, Karim and Ricles, James M.",
    "Maghareh2014": "Maghareh, Amin and Dyke, Shirley J. and Prakash, Arun and Rhoads, Jeffrey F.",
    "Ou2015": "Ou, Ge and Ozdagli, Ali Irmak and Dyke, Shirley J. and Wu, Bin",
    "Zhu2015": "Zhu, Fei and Wang, Jin-Ting and Jin, Feng and Chi, Fu-Dong and Gui, Yao",
    "Huang2020": "Huang, Liang and Chen, Cheng and Guo, Tong and Gao, Xiaoshu",
    "HuangEffect2022": "Huang, Liang and Chen, Cheng and Chen, Menghui and Guo, Tong",
    "HuangJVC2022": "Huang, Liang and Chen, Cheng and Huang, Shenjiang and Wang, Jingfeng",
    "HuangEESD2022": "Huang, Liang and Chen, Cheng and Pu, Yifan and Wang, Jingfeng and Guo, Tong",
}

EESD_KEYS = {
    "Nakashima1992",
    "NakashimaMasaoka1999",
    "Horiuchi1999",
    "Pan2005",
    "Gao2013",
    "Miraglia2020",
    "Zhang2024",
    "Wu2005",
    "Wallace2005",
    "MercanRicles2007",
    "Mercan2008",
    "ChenRicles2008",
    "ChenRiclesMarullo2009",
    "ChenRicles2012",
    "Chae2013",
    "Ou2015",
    "Zhu2015",
    "HuangEESD2022",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def frozen_text(path: Path, expected_hash: str) -> str:
    data = path.read_bytes()
    actual = sha256(data)
    if actual != expected_hash:
        raise RuntimeError(f"Frozen input changed: {path}\n{actual} != {expected_hash}")
    return data.decode("utf-8")


def entry_spans(text: str) -> list[tuple[str, int, int]]:
    starts = list(re.finditer(r"(?m)^@\w+\{([^,]+),", text))
    spans = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        spans.append((match.group(1).strip(), match.start(), end))
    return spans


def get_field(block: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{(.*)\}},?\s*$", block)
    if not match:
        raise RuntimeError(f"Missing {name} field")
    return match.group(1)


def set_field(block: str, name: str, value: str) -> tuple[str, bool]:
    pattern = re.compile(rf"(?m)^(\s*{re.escape(name)}\s*=\s*)\{{.*\}}(,?)\s*$")
    match = pattern.search(block)
    if not match:
        raise RuntimeError(f"Missing {name} field")
    replacement = f"{match.group(1)}{{{value}}}{match.group(2)}"
    changed = match.group(0) != replacement
    return block[: match.start()] + replacement + block[match.end() :], changed


def stage2_baseline(source: str) -> str:
    body = source[source.index("@") :]
    kept = []
    for line in body.splitlines():
        if re.match(r"^\s*(doi|note)\s*=", line, re.IGNORECASE):
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip() + "\n"
    cleaned = re.sub(r",(\n\s*\})", r"\1", cleaned)
    header = (
        "% Clean 50-entry bibliography used by main_50refs_clean.tex.\n"
        "% Identifier display fields were removed from this derivative at the user's request.\n"
        "% Bibliographic name and journal metadata are verified in workflow task 3.\n\n"
    )
    return header + cleaned


def normalize_title(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\\[A-Za-z]+", "", value)
    value = value.replace("{", "").replace("}", "")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return "".join(char.lower() for char in value if char.isalnum())


def validate_crossref(source: str) -> None:
    payload = json.loads(CROSSREF_CACHE.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if payload.get("record_count") != 50 or len(records) != 50:
        raise RuntimeError("Crossref cache does not contain 50 records")
    source_blocks = {key: source[start:end] for key, start, end in entry_spans(source)}
    for record in records:
        key = record["key"]
        if record.get("status") != "ok" or key not in source_blocks:
            raise RuntimeError(f"Invalid Crossref cache record: {key}")
        block = source_blocks[key]
        if get_field(block, "doi").lower() != record["doi"].lower():
            raise RuntimeError(f"DOI mismatch for {key}")
        registered_titles = record["crossref"].get("title") or []
        if not registered_titles:
            raise RuntimeError(f"Crossref title missing for {key}")
        if normalize_title(get_field(block, "title")) != normalize_title(" ".join(registered_titles)):
            raise RuntimeError(f"Registered title mismatch for {key}")
        registered_authors = record["crossref"].get("author") or []
        if len(AUTHOR_FIELDS[key].split(" and ")) != len(registered_authors):
            raise RuntimeError(f"Registered author-count mismatch for {key}")


def build_candidate(baseline: str) -> tuple[str, dict[str, int]]:
    spans = entry_spans(baseline)
    if len(spans) != 50 or [key for key, _, _ in spans] != list(AUTHOR_FIELDS):
        raise RuntimeError("The 50-entry order no longer matches the approved author map")
    pieces = [baseline[: spans[0][1]]]
    counts = {"author": 0, "journal": 0, "title": 0, "number": 0}
    for key, start, end in spans:
        block = baseline[start:end]
        block, changed = set_field(block, "author", AUTHOR_FIELDS[key])
        counts["author"] += int(changed)
        if key in EESD_KEYS:
            block, changed = set_field(block, "journal", r"Earthquake Engineering \& Structural Dynamics")
            counts["journal"] += int(changed)
        elif key == "MacNeal1971":
            block, changed = set_field(block, "journal", r"Computers \& Structures")
            counts["journal"] += int(changed)
        if key == "Krattiger2019":
            block, changed = set_field(
                block,
                "title",
                "Interface Reduction for {Hurty/Craig--Bampton} Substructured Models: Review and Improvements",
            )
            counts["title"] += int(changed)
        if key == "Mucha2023":
            if re.search(r"(?m)^\s*number\s*=", block):
                if get_field(block, "number") != "7":
                    raise RuntimeError("Mucha2023 has an unexpected number field")
            else:
                volume = re.search(r"(?m)^(\s*volume\s*=\s*\{58\},\s*\n)", block)
                if not volume:
                    raise RuntimeError("Mucha2023 volume insertion point not found")
                block = block[: volume.end()] + "  number  = {7},\n" + block[volume.end() :]
                counts["number"] += 1
        pieces.append(block)
    candidate = "".join(pieces)
    if counts != {"author": 50, "journal": 19, "title": 1, "number": 1}:
        raise RuntimeError(f"Unexpected correction counts: {counts}")
    return candidate, counts


def main() -> None:
    source = frozen_text(SOURCE_BIB, EXPECTED_SOURCE_HASH)
    frozen_text(OLD_VERIFIED_BIB, EXPECTED_OLD_HASH)
    validate_crossref(source)
    baseline = stage2_baseline(source)
    if sha256(baseline.encode("utf-8")) != EXPECTED_STAGE2_HASH:
        raise RuntimeError("Rebuilt Stage 2 bibliography hash mismatch")
    candidate, counts = build_candidate(baseline)
    current = TARGET_BIB.read_text(encoding="utf-8")
    if current == baseline:
        target_status = "stage2-baseline"
    elif current == candidate:
        target_status = "stage3-candidate"
    else:
        raise RuntimeError("Target bibliography is neither the frozen Stage 2 baseline nor the Stage 3 candidate")
    forbidden = [r"\nolinkurl", "DOI", "doi     =", "note    ="]
    leftovers = [token for token in forbidden if token in candidate]
    if leftovers:
        raise RuntimeError(f"Forbidden identifier-display remnants: {leftovers}")
    CANDIDATE_BIB.write_text(candidate, encoding="utf-8", newline="\n")
    print(f"PASS | Crossref DOI/title/author-count records: 50")
    print(f"PASS | correction counts: {counts}")
    print(f"PASS | target status before application: {target_status}")
    print(f"WROTE | {CANDIDATE_BIB}")
    print(f"BYTES | {CANDIDATE_BIB.stat().st_size}")
    print(f"SHA256 | {sha256(CANDIDATE_BIB.read_bytes())}")


if __name__ == "__main__":
    main()
