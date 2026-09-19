from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANUSCRIPT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript")
ROOT = MANUSCRIPT.parent
SOURCE_BIB = ROOT / "rths_references_verified_expanded.bib"
TARGET_BIB = MANUSCRIPT / "reference_50refs_clean.bib"
TARGET_TEX = MANUSCRIPT / "main_50refs_clean.tex"
VERIFICATION = MANUSCRIPT / "verification_50refs"
CROSSREF_CACHE = VERIFICATION / "crossref_metadata_50.json"
METADATA_AUDIT = VERIFICATION / "stage3_metadata_audit.md"
REPORT = VERIFICATION / "stage3_bib_validation.txt"

EXPECTED_SOURCE_BIB_SHA256 = (
    "3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8"
)
EXPECTED_TEX_SHA256 = (
    "EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995"
)

OFFICIAL_JOURNAL_NAMES = {
    "Earthquake Engineering and Structural Dynamics": (
        r"Earthquake Engineering \& Structural Dynamics"
    ),
    "Computers and Structures": r"Computers \& Structures",
}

EXPECTED_SPECIAL_AUTHORS = {
    "Mahin1989": (
        "Mahin, Stephen A. and Shing, Pui-Shum B. and "
        "Thewalt, Christopher R. and Hanson, Robert D."
    ),
    "Chae2013": "Chae, Yunbyeong and Kazemibidokhti, Karim and Ricles, James M.",
    "MacNeal1971": "MacNeal, Richard H.",
}

EXPECTED_SPECIAL_TITLES = {
    "Krattiger2019": (
        "Interface Reduction for {Hurty/Craig--Bampton} Substructured Models: "
        "Review and Improvements"
    ),
}

SPENCER_JR_KEYS = {
    "Phillips2013",
    "Phillips2013Feedforward",
    "Fermandois2017",
    "Najafi2020",
    "NajafiSpencer2021",
    "Najafi2023",
    "Silva2020",
}

KNOWN_WRONG_NAME_LITERALS = (
    "Stephen A. Mahin",
    "P. Benson Shing",
    "Craig R. Thewalt",
    "Kasra Kazemibidokhti",
    "Robert H. MacNeal",
    "Spencer Jr.",
    "Craig Jr.",
)

# Crossref records an online-publication year for these articles, whereas the
# journal citation correctly uses the year assigned to the volume and issue.
CROSSREF_ONLINE_YEAR_EXCEPTIONS = {
    "Gao2013",
    "ChenRiclesMarullo2009",
    "Ou2015",
    "PalacioBetancur2023",
    "HuangEffect2022",
    "HuangJVC2022",
    "Zhu2015",
}

# Crossref's current Zhang2024 record exposes the DOI suffix as ``page`` and
# omits the final volume/issue/page assignment.  Wiley's journal page supplies
# the authoritative 53(14):4334--4353 citation used in the BibTeX derivative.
CROSSREF_PAGE_EXCEPTIONS = {"Zhang2024"}


@dataclass(frozen=True)
class Entry:
    entry_type: str
    key: str
    fields: dict[str, str]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def is_escaped(text: str, position: int) -> bool:
    backslashes = 0
    cursor = position - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def scan_braced(text: str, opening: int) -> tuple[str, int]:
    if opening >= len(text) or text[opening] != "{":
        raise ValueError(f"Expected opening brace at offset {opening}")
    depth = 0
    for position in range(opening, len(text)):
        char = text[position]
        if char == "{" and not is_escaped(text, position):
            depth += 1
        elif char == "}" and not is_escaped(text, position):
            depth -= 1
            if depth == 0:
                return text[opening + 1 : position], position + 1
            if depth < 0:
                raise ValueError(f"Negative brace depth at offset {position}")
    raise ValueError(f"Unclosed brace at offset {opening}")


def parse_fields(body: str, key: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    cursor = 0
    while cursor < len(body):
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor >= len(body):
            break
        if body[cursor] == "%":
            newline = body.find("\n", cursor)
            cursor = len(body) if newline < 0 else newline + 1
            continue
        match = re.match(r"[A-Za-z][A-Za-z0-9_-]*", body[cursor:])
        if not match:
            snippet = body[cursor : cursor + 50]
            raise ValueError(f"Invalid field name in {key} near {snippet!r}")
        field = match.group(0).lower()
        cursor += len(match.group(0))
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor >= len(body) or body[cursor] != "=":
            raise ValueError(f"Missing '=' after {field} in {key}")
        cursor += 1
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor >= len(body):
            raise ValueError(f"Missing value for {field} in {key}")
        if body[cursor] == "{":
            value, cursor = scan_braced(body, cursor)
        elif body[cursor] == '"':
            start = cursor + 1
            cursor = start
            while cursor < len(body):
                if body[cursor] == '"' and not is_escaped(body, cursor):
                    break
                cursor += 1
            if cursor >= len(body):
                raise ValueError(f"Unclosed quoted value for {field} in {key}")
            value = body[start:cursor]
            cursor += 1
        else:
            start = cursor
            while cursor < len(body) and body[cursor] != ",":
                cursor += 1
            value = body[start:cursor].strip()
        if field in fields:
            raise ValueError(f"Duplicate field {field} in {key}")
        fields[field] = value.strip()
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor < len(body):
            if body[cursor] != ",":
                raise ValueError(f"Missing ',' after {field} in {key}")
            cursor += 1
    return fields


def parse_bib(text: str) -> list[Entry]:
    header = re.compile(r"(?m)^[ \t]*@([A-Za-z]+)\s*\{\s*([^,\s]+)\s*,")
    entries: list[Entry] = []
    intervals: list[tuple[int, int]] = []
    cursor = 0
    while True:
        match = header.search(text, cursor)
        if match is None:
            break
        opening = text.find("{", match.start(), match.end())
        _, end = scan_braced(text, opening)
        body = text[match.end() : end - 1]
        entries.append(
            Entry(
                entry_type=match.group(1).lower(),
                key=match.group(2),
                fields=parse_fields(body, match.group(2)),
            )
        )
        intervals.append((match.start(), end))
        cursor = end

    previous = 0
    outside_parts: list[str] = []
    for start, end in intervals:
        outside_parts.append(text[previous:start])
        previous = end
    outside_parts.append(text[previous:])
    for part in outside_parts:
        for line in part.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("%"):
                raise ValueError(f"Unexpected text outside entries: {stripped!r}")
    return entries


def split_outside_braces(value: str, separator: str) -> list[str]:
    pieces: list[str] = []
    depth = 0
    start = 0
    cursor = 0
    while cursor < len(value):
        char = value[cursor]
        if char == "{" and not is_escaped(value, cursor):
            depth += 1
        elif char == "}" and not is_escaped(value, cursor):
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced braces in {value!r}")
        if depth == 0 and value.startswith(separator, cursor):
            pieces.append(value[start:cursor].strip())
            cursor += len(separator)
            start = cursor
            continue
        cursor += 1
    if depth != 0:
        raise ValueError(f"Unbalanced braces in {value!r}")
    pieces.append(value[start:].strip())
    return pieces


def split_authors(value: str) -> list[str]:
    return split_outside_braces(value, " and ")


def parse_family_given(name: str) -> tuple[str, str, str]:
    parts = split_outside_braces(name, ",")
    if len(parts) == 2:
        family, given = parts
        suffix = ""
    elif len(parts) == 3:
        family, suffix, given = parts
    else:
        raise ValueError(
            f"author must use 'Family, Given' or 'Family, Jr., Given': {name!r}"
        )
    if not family or not given:
        raise ValueError(f"empty family/given component in {name!r}")
    if suffix and suffix != "Jr.":
        raise ValueError(f"unsupported suffix {suffix!r} in {name!r}")
    return family, given, suffix


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_doi(value: str) -> str:
    value = html.unescape(normalize_space(value)).lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(".,;")


def de_latex(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace(r"\&", " and ").replace("&", " and ")
    value = value.replace("--", "-")
    value = re.sub(
        r"\\(?:['\"`^~=.uvHck])\s*\{?([A-Za-z])\}?",
        r"\1",
        value,
    )
    value = re.sub(r"\\[A-Za-z]+\*?(?:\s*\[[^\]]*\])?", " ", value)
    value = value.replace("{", "").replace("}", "")
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_words(value: str) -> str:
    value = de_latex(value).lower()
    value = re.sub(r"[^0-9a-z]+", " ", value)
    return normalize_space(value)


def normalize_pages(value: str) -> str:
    value = de_latex(value).replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"-+", "-", value)
    return value.lower()


def pages_equivalent(left: str, right: str) -> bool:
    left_normalized = normalize_pages(left)
    right_normalized = normalize_pages(right)
    if left_normalized == right_normalized:
        return True
    left_parts = left_normalized.split("-")
    right_parts = right_normalized.split("-")
    if len(left_parts) == 1 and len(right_parts) == 2:
        return right_parts[0] == right_parts[1] == left_parts[0]
    if len(right_parts) == 1 and len(left_parts) == 2:
        return left_parts[0] == left_parts[1] == right_parts[0]
    return False


def initials(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", de_latex(value))
    return "".join(word[0].lower() for word in words if word)


def cite_keys(tex: str) -> list[str]:
    keys: list[str] = []
    pattern = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}")
    for group in pattern.findall(tex):
        keys.extend(key.strip() for key in group.split(",") if key.strip())
    return keys


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return scalar(value[0]) if value else ""
    if isinstance(value, dict):
        return ""
    return str(value).strip()


def source_expected_fields(entry: Entry) -> set[str]:
    fields = set(entry.fields) - {"doi", "note"}
    if entry.key == "Mucha2023":
        fields.add("number")
    return fields


def validate_static(
    source_bytes: bytes,
    target_bytes: bytes,
    tex_bytes: bytes,
    errors: list[str],
    details: list[str],
) -> tuple[list[Entry], list[Entry], list[str]]:
    check(
        sha256(source_bytes) == EXPECTED_SOURCE_BIB_SHA256,
        "protected expanded source Bib SHA-256 changed",
        errors,
    )
    check(
        sha256(tex_bytes) == EXPECTED_TEX_SHA256,
        "main_50refs_clean.tex changed during bibliography-only stage 3",
        errors,
    )

    source_entries = parse_bib(source_bytes.decode("utf-8"))
    target_entries = parse_bib(target_bytes.decode("utf-8"))
    source_keys = [entry.key for entry in source_entries]
    target_keys = [entry.key for entry in target_entries]
    source_map = {entry.key: entry for entry in source_entries}
    target_map = {entry.key: entry for entry in target_entries}
    source_dois = [
        normalize_doi(entry.fields.get("doi", "")) for entry in source_entries
    ]

    check(len(source_entries) == 50, f"source entry count is {len(source_entries)}, not 50", errors)
    check(len(target_entries) == 50, f"target entry count is {len(target_entries)}, not 50", errors)
    check(len(source_map) == len(source_entries), "duplicate exact key in source Bib", errors)
    check(len(target_map) == len(target_entries), "duplicate exact key in target Bib", errors)
    check(
        len({key.casefold() for key in target_keys}) == len(target_keys),
        "case-insensitive duplicate key in target Bib",
        errors,
    )
    check(target_keys == source_keys, "target key set or order differs from protected expanded Bib", errors)
    check(
        Counter(entry.entry_type for entry in target_entries) == Counter({"article": 50}),
        "target entry types are not exactly 50 articles",
        errors,
    )
    check(all(source_dois), "one or more protected source entries lacks a DOI", errors)
    check(len(set(source_dois)) == 50, "protected source DOI values are not 50 unique values", errors)

    tex = tex_bytes.decode("utf-8")
    cited = cite_keys(tex)
    cited_unique = set(cited)
    check(len(cited) == 60, f"citation occurrence count is {len(cited)}, not 60", errors)
    check(len(cited_unique) == 50, f"unique cited key count is {len(cited_unique)}, not 50", errors)
    check(
        cited_unique == set(target_keys),
        "citation-key closure failed between TeX and target Bib",
        errors,
    )

    target_text = target_bytes.decode("utf-8")
    doi_literals = re.findall(r"(?i)(?<![A-Za-z])doi(?![A-Za-z])", target_text)
    check(not doi_literals, f"target contains {len(doi_literals)} DOI literal(s)", errors)
    check(r"\nolinkurl" not in target_text, r"target contains \nolinkurl", errors)

    normalized_titles: list[str] = []
    author_count = 0
    family_given_count = 0
    for entry in target_entries:
        source = source_map.get(entry.key)
        if source is None:
            continue
        required = {"author", "title", "journal", "year", "volume", "pages"}
        check(
            required.issubset(entry.fields),
            f"{entry.key}: missing required article fields {sorted(required - set(entry.fields))}",
            errors,
        )
        check(
            set(entry.fields) == source_expected_fields(source),
            f"{entry.key}: field set differs from source-minus-identifier contract",
            errors,
        )
        check("doi" not in entry.fields, f"{entry.key}: doi field remains", errors)
        check("note" not in entry.fields, f"{entry.key}: note field remains", errors)
        check(
            re.fullmatch(r"\d{4}", entry.fields.get("year", "")) is not None,
            f"{entry.key}: invalid four-digit year",
            errors,
        )
        pages = entry.fields.get("pages", "")
        check(
            not ("-" in pages and "--" not in pages),
            f"{entry.key}: page range uses a single hyphen",
            errors,
        )
        normalized_titles.append(normalize_words(entry.fields.get("title", "")))
        check(
            normalize_words(entry.fields.get("title", ""))
            == normalize_words(source.fields.get("title", "")),
            f"{entry.key}: title content changed from protected expanded Bib",
            errors,
        )

        try:
            authors = split_authors(entry.fields.get("author", ""))
        except ValueError as exc:
            errors.append(f"{entry.key}: {exc}")
            authors = []
        source_author_count = len(split_authors(source.fields.get("author", "")))
        check(
            len(authors) == source_author_count,
            f"{entry.key}: author count {len(authors)} differs from source count {source_author_count}",
            errors,
        )
        for author in authors:
            author_count += 1
            try:
                parse_family_given(author)
                family_given_count += 1
            except ValueError as exc:
                errors.append(f"{entry.key}: {exc}")

        expected_journal = OFFICIAL_JOURNAL_NAMES.get(
            source.fields.get("journal", ""), source.fields.get("journal", "")
        )
        check(
            entry.fields.get("journal") == expected_journal,
            f"{entry.key}: journal is not the expected formal name {expected_journal!r}",
            errors,
        )
        if entry.key != "Mucha2023":
            for field in ("year", "volume", "number", "pages"):
                check(
                    entry.fields.get(field) == source.fields.get(field),
                    f"{entry.key}.{field}: value changed outside approved metadata scope",
                    errors,
                )

    duplicate_titles = sorted(
        title for title, count in Counter(normalized_titles).items() if count > 1
    )
    check(not duplicate_titles, f"duplicate normalized titles: {duplicate_titles}", errors)

    for key, expected in EXPECTED_SPECIAL_AUTHORS.items():
        actual = target_map.get(key, Entry("", key, {})).fields.get("author", "")
        check(actual == expected, f"{key}: corrected author contract does not match", errors)

    for key, expected in EXPECTED_SPECIAL_TITLES.items():
        actual = target_map.get(key, Entry("", key, {})).fields.get("title", "")
        check(actual == expected, f"{key}: protected title contract does not match", errors)

    for key in SPENCER_JR_KEYS:
        actual = target_map.get(key, Entry("", key, {})).fields.get("author", "")
        check(
            "Spencer, Jr., Billie F." in actual,
            f"{key}: Billie F. Spencer Jr. is not in BibTeX suffix form",
            errors,
        )
    craig = target_map.get("CraigBampton1968", Entry("", "", {})).fields.get(
        "author", ""
    )
    check(
        "Craig, Jr., Roy R." in craig,
        "CraigBampton1968: Roy R. Craig Jr. is not in BibTeX suffix form",
        errors,
    )
    check(
        target_text.count("Spencer, Jr., Billie F.") == 7,
        "expected exactly seven Spencer, Jr., Billie F. occurrences",
        errors,
    )
    check(
        target_text.count("Craig, Jr., Roy R.") == 1,
        "expected exactly one Craig, Jr., Roy R. occurrence",
        errors,
    )

    condori_authors = split_authors(
        target_map.get("Condori2023", Entry("", "", {})).fields.get("author", "")
    )
    condori_families: list[str] = []
    for author in condori_authors:
        try:
            condori_families.append(de_latex(parse_family_given(author)[0]).strip("{}"))
        except ValueError:
            pass
    check(
        bool(condori_families) and condori_families[0] == "Condori Uribe",
        "Condori2023: compound family name 'Condori Uribe' is not preserved",
        errors,
    )
    check(
        bool(condori_authors) and condori_authors[0] == "Condori Uribe, Johnny W.",
        "Condori2023: first author must be 'Condori Uribe, Johnny W.'",
        errors,
    )
    palacio_authors = split_authors(
        target_map.get("PalacioBetancur2023", Entry("", "", {})).fields.get(
            "author", ""
        )
    )
    palacio_families: list[str] = []
    for author in palacio_authors:
        try:
            palacio_families.append(de_latex(parse_family_given(author)[0]).strip("{}"))
        except ValueError:
            pass
    check(
        palacio_families == ["Palacio-Betancur", "Gutierrez Soto"],
        "PalacioBetancur2023: hyphenated/compound family names are not preserved",
        errors,
    )
    besselink_authors = split_authors(
        target_map.get("Besselink2013", Entry("", "", {})).fields.get("author", "")
    )
    besselink_families: list[str] = []
    for author in besselink_authors:
        try:
            besselink_families.append(de_latex(parse_family_given(author)[0]).strip("{}"))
        except ValueError:
            pass
    check(
        "van de Wouw" in besselink_families,
        "Besselink2013: compound family name 'van de Wouw' is not preserved",
        errors,
    )

    for wrong in KNOWN_WRONG_NAME_LITERALS:
        check(wrong not in target_text, f"known wrong/unstable name literal remains: {wrong}", errors)

    mucha = target_map.get("Mucha2023", Entry("", "", {})).fields
    check(mucha.get("number") == "7", "Mucha2023: expected number = {7}", errors)

    details.extend(
        [
            f"Source entries: {len(source_entries)}",
            f"Target entries: {len(target_entries)}",
            f"Citation occurrences: {len(cited)}",
            f"Unique cited keys: {len(cited_unique)}",
            f"Parsed authors in Family, Given form: {family_given_count}/{author_count}",
            f"Duplicate normalized titles: {len(duplicate_titles)}",
            f"Target DOI literals: {len(doi_literals)}",
            f"Protected source DOI values: {len(source_dois)} ({len(set(source_dois))} unique)",
        ]
    )
    return source_entries, target_entries, cited


def validate_crossref(
    source_entries: list[Entry],
    target_entries: list[Entry],
    errors: list[str],
    details: list[str],
) -> None:
    try:
        payload = json.loads(CROSSREF_CACHE.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"Crossref cache read/parse failed: {exc}")
        return

    check(isinstance(payload, dict), "Crossref cache top level is not an object", errors)
    if not isinstance(payload, dict):
        return
    check("schema_version" in payload, "Crossref cache lacks schema_version", errors)
    check(bool(payload.get("schema_version")), "Crossref cache schema_version is empty", errors)
    cache_source = scalar(payload.get("source_bib"))
    check(bool(cache_source), "Crossref cache source_bib is empty", errors)
    check(
        cache_source.replace("\\", "/").endswith(SOURCE_BIB.name),
        "Crossref cache source_bib does not identify the protected expanded Bib",
        errors,
    )
    check(payload.get("record_count") == 50, "Crossref cache record_count is not 50", errors)
    records = payload.get("records")
    check(isinstance(records, list), "Crossref cache records is not a list", errors)
    if not isinstance(records, list):
        return
    check(len(records) == 50, f"Crossref cache contains {len(records)} records, not 50", errors)

    record_keys = [record.get("key") for record in records if isinstance(record, dict)]
    check(len(record_keys) == len(records), "Crossref cache contains a non-object record", errors)
    check(len(set(record_keys)) == len(record_keys), "Crossref cache has duplicate keys", errors)
    source_map = {entry.key: entry for entry in source_entries}
    target_map = {entry.key: entry for entry in target_entries}
    check(set(record_keys) == set(source_map), "Crossref cache key set differs from source Bib", errors)

    compared_titles = 0
    compared_authors = 0
    for raw_record in records:
        if not isinstance(raw_record, dict):
            continue
        key = raw_record.get("key")
        if key not in source_map or key not in target_map:
            continue
        source = source_map[key]
        target = target_map[key]
        cache_doi = normalize_doi(scalar(raw_record.get("doi")))
        source_doi = normalize_doi(source.fields.get("doi", ""))
        check(bool(source_doi), f"{key}: protected source has no DOI", errors)
        check(cache_doi == source_doi, f"{key}: cached DOI differs from protected source DOI", errors)
        check(raw_record.get("status") == "ok", f"{key}: Crossref status is not 'ok'", errors)
        crossref = raw_record.get("crossref")
        check(isinstance(crossref, dict), f"{key}: crossref payload is not an object", errors)
        if not isinstance(crossref, dict):
            continue
        required_crossref_fields = {
            "title",
            "author",
            "container-title",
            "year",
            "volume",
            "issue",
            "page",
            "publisher",
            "type",
        }
        check(
            required_crossref_fields.issubset(crossref),
            f"{key}: Crossref payload lacks fields "
            f"{sorted(required_crossref_fields - set(crossref))}",
            errors,
        )

        cache_title = scalar(crossref.get("title"))
        if cache_title:
            compared_titles += 1
            check(
                normalize_words(cache_title) == normalize_words(target.fields.get("title", "")),
                f"{key}: target title differs from Crossref",
                errors,
            )
        cache_journal = scalar(crossref.get("container-title"))
        if cache_journal:
            check(
                normalize_words(cache_journal)
                == normalize_words(target.fields.get("journal", "")),
                f"{key}: target journal differs from Crossref",
                errors,
            )
        for target_field, cache_field in (
            ("year", "year"),
            ("volume", "volume"),
            ("number", "issue"),
        ):
            cache_value = scalar(crossref.get(cache_field))
            if cache_value and not (
                target_field == "year" and key in CROSSREF_ONLINE_YEAR_EXCEPTIONS
            ):
                target_value = target.fields.get(target_field, "")
                values_match = (
                    normalize_pages(target_value) == normalize_pages(cache_value)
                    if target_field == "number"
                    else normalize_space(target_value) == cache_value
                )
                check(
                    values_match,
                    f"{key}: target {target_field} differs from Crossref {cache_field}",
                    errors,
                )
        cache_page = scalar(crossref.get("page"))
        if cache_page and key not in CROSSREF_PAGE_EXCEPTIONS:
            check(
                pages_equivalent(target.fields.get("pages", ""), cache_page),
                f"{key}: target pages differs from Crossref page",
                errors,
            )

        cache_authors = crossref.get("author")
        if isinstance(cache_authors, list) and cache_authors:
            compared_authors += 1
            try:
                target_authors = [
                    parse_family_given(name)
                    for name in split_authors(target.fields.get("author", ""))
                ]
            except ValueError as exc:
                errors.append(f"{key}: cannot compare authors with Crossref: {exc}")
                continue
            check(
                len(target_authors) == len(cache_authors),
                f"{key}: target/Crossref author count differs",
                errors,
            )
            for index, (target_author, cache_author) in enumerate(
                zip(target_authors, cache_authors), start=1
            ):
                if not isinstance(cache_author, dict):
                    errors.append(f"{key}: Crossref author {index} is not an object")
                    continue
                target_family, target_given, target_suffix = target_author
                cache_family = scalar(cache_author.get("family"))
                cache_given = scalar(cache_author.get("given"))
                cache_suffix = scalar(cache_author.get("suffix"))
                if cache_family:
                    check(
                        normalize_words(target_family) == normalize_words(cache_family),
                        f"{key}: author {index} family differs from Crossref",
                        errors,
                    )
                if cache_given:
                    check(
                        initials(target_given) == initials(cache_given),
                        f"{key}: author {index} given-name initials differ from Crossref",
                        errors,
                    )
                if cache_suffix:
                    check(
                        normalize_words(target_suffix) == normalize_words(cache_suffix),
                        f"{key}: author {index} suffix differs from Crossref",
                        errors,
                    )

    try:
        audit = METADATA_AUDIT.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        errors.append(f"stage-3 metadata audit read failed: {exc}")
    else:
        check(TARGET_BIB.name in audit, "metadata audit does not name target Bib", errors)
        check(CROSSREF_CACHE.name in audit, "metadata audit does not name Crossref cache", errors)
        check(
            re.search(r"(?i)\bPASS\b|通过", audit) is not None,
            "metadata audit has no explicit PASS/通过 status",
            errors,
        )
        check(
            re.search(r"(?i)STATUS\s*:\s*FAIL|\bUNRESOLVED\b|未通过", audit) is None,
            "metadata audit contains FAIL/unresolved status",
            errors,
        )

    details.extend(
        [
            f"Crossref records: {len(records)}",
            f"Crossref titles compared: {compared_titles}",
            f"Crossref author lists compared: {compared_authors}",
            f"Crossref cache SHA-256: {sha256(CROSSREF_CACHE.read_bytes())}",
        ]
    )


def write_report(
    mode: str,
    target_bytes: bytes | None,
    details: list[str],
    errors: list[str],
) -> None:
    lines = [
        "RHTS STAGE 3 BIBTEX VALIDATION",
        "",
        f"Mode: {mode}",
        f"Source Bib: {SOURCE_BIB}",
        f"Target Bib: {TARGET_BIB}",
        f"Target TeX: {TARGET_TEX}",
        f"Crossref cache: {CROSSREF_CACHE}",
        f"Metadata audit: {METADATA_AUDIT}",
    ]
    if target_bytes is not None:
        lines.extend(
            [
                f"Target bytes: {len(target_bytes)}",
                f"Target SHA-256: {sha256(target_bytes)}",
            ]
        )
    lines.extend(["", *details, ""])
    if errors:
        lines.extend(["STATUS: FAIL", *[f"FAIL | {error}" for error in errors]])
    elif mode == "static-only":
        lines.extend(
            [
                "STATUS: PASS (STATIC ONLY)",
                "PASS | BibTeX structure, 50-key citation closure, fields, names, venues, and identifier removal passed",
                "SKIP | Crossref cache and metadata-audit interface intentionally skipped",
            ]
        )
    else:
        lines.extend(
            [
                "STATUS: PASS",
                "PASS | 50-key TeX/Bib closure and all static bibliography contracts passed",
                "PASS | All original DOI values map one-to-one to successful Crossref cache records",
                "PASS | Target metadata agrees with populated Crossref fields",
                "PASS | Stage-3 metadata audit interface passed",
            ]
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independently validate the 50-entry RHTS stage-3 BibTeX derivative."
    )
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="Skip Crossref-cache and metadata-audit checks while corrections are in progress.",
    )
    args = parser.parse_args()
    mode = "static-only" if args.static_only else "full"
    errors: list[str] = []
    details: list[str] = []
    target_bytes: bytes | None = None
    try:
        source_bytes = SOURCE_BIB.read_bytes()
        target_bytes = TARGET_BIB.read_bytes()
        tex_bytes = TARGET_TEX.read_bytes()
        source_entries, target_entries, _ = validate_static(
            source_bytes, target_bytes, tex_bytes, errors, details
        )
        if not args.static_only:
            validate_crossref(source_entries, target_entries, errors, details)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"validation could not complete: {type(exc).__name__}: {exc}")

    write_report(mode, target_bytes, details, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
