#!/usr/bin/env python3
"""Fetch a compact Crossref evidence record for the 50-entry source BibTeX file."""

from __future__ import annotations

import concurrent.futures
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANUSCRIPT = HERE.parent
SOURCE_BIB = MANUSCRIPT.parent / "rths_references_verified_expanded.bib"
OUTPUT_JSON = HERE / "crossref_metadata_50.json"
OUTPUT_MD = HERE / "crossref_metadata_50.md"

USER_AGENT = "RHTS-reference-audit/1.0"


def entry_blocks(text: str) -> list[tuple[str, str]]:
    starts = list(re.finditer(r"(?m)^@\w+\{([^,]+),", text))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        blocks.append((match.group(1).strip(), text[match.start() : end]))
    return blocks


def extract_source_records() -> list[dict[str, str]]:
    text = SOURCE_BIB.read_text(encoding="utf-8")
    records: list[dict[str, str]] = []
    for key, block in entry_blocks(text):
        match = re.search(r"(?im)^\s*doi\s*=\s*\{([^}]*)\}", block)
        if not match:
            raise RuntimeError(f"Missing DOI for {key}")
        records.append({"key": key, "doi": match.group(1).strip()})
    if len(records) != 50:
        raise RuntimeError(f"Expected 50 records, found {len(records)}")
    return records


def compact_message(message: dict) -> dict:
    issued = message.get("published-print") or message.get("published-online") or message.get("issued") or {}
    date_parts = issued.get("date-parts") or []
    year = date_parts[0][0] if date_parts and date_parts[0] else None
    keep = {
        "title": message.get("title", []),
        "author": message.get("author", []),
        "container-title": message.get("container-title", []),
        "year": year,
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "page": message.get("page") or message.get("article-number"),
        "publisher": message.get("publisher"),
        "type": message.get("type"),
    }
    return keep


def fetch_one(source: dict[str, str]) -> dict:
    doi = source["doi"]
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    last_error = ""
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            return {
                "key": source["key"],
                "doi": doi,
                "status": "ok",
                "crossref": compact_message(payload["message"]),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.5 * (attempt + 1))
    return {"key": source["key"], "doi": doi, "status": "error", "error": last_error}


def render_markdown(records: list[dict]) -> str:
    lines = [
        "# Crossref metadata evidence for the 50-entry RHTS bibliography",
        "",
        f"Source: `{SOURCE_BIB.as_posix()}`",
        "",
        "This is verification evidence only. DOI fields remain excluded from the clean delivery BibTeX.",
        "",
        "| Key | Status | Registered title | Registered authors | Venue | Year | Volume(issue) | Pages/article |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for record in records:
        if record["status"] != "ok":
            lines.append(f"| {record['key']} | error | {record.get('error', '')} | | | | | |")
            continue
        data = record["crossref"]
        title = " ".join(data.get("title") or []).replace("|", "\\|")
        authors = "; ".join(
            " ".join(part for part in (author.get("given"), author.get("family"), author.get("suffix")) if part)
            for author in data.get("author") or []
        ).replace("|", "\\|")
        venue = " ".join(data.get("container-title") or []).replace("|", "\\|")
        volume_issue = str(data.get("volume") or "")
        if data.get("issue"):
            volume_issue += f"({data['issue']})"
        lines.append(
            f"| {record['key']} | ok | {title} | {authors} | {venue} | {data.get('year') or ''} | "
            f"{volume_issue} | {data.get('page') or ''} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    source_records = extract_source_records()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fetched = list(pool.map(fetch_one, source_records))
    output = {
        "schema_version": 1,
        "source_bib": str(SOURCE_BIB),
        "record_count": len(fetched),
        "records": fetched,
    }
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT_MD.write_text(render_markdown(fetched), encoding="utf-8")
    ok = sum(record["status"] == "ok" for record in fetched)
    print(f"Crossref records: {ok}/{len(fetched)} ok")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"Markdown: {OUTPUT_MD}")
    if ok != len(fetched):
        for record in fetched:
            if record["status"] != "ok":
                print(f"ERROR | {record['key']} | {record.get('error', '')}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
