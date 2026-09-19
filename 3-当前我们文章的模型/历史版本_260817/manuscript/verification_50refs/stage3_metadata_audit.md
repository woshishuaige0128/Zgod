# RHTS Stage 3 bibliography metadata audit

Date: 2026-09-03

STATUS: PASS

## Scope and protected inputs

- Target derivative: `reference_50refs_clean.bib`
- DOI evidence cache: `crossref_metadata_50.json`
- Protected expanded source SHA-256: `3E5FA6BB488237153395D6774128FE7C3A7A6D7A62D48FCD003366F6284A16A8`
- Protected prior verified library SHA-256: `71D767B20073D1D87A151A57EF1A80BC1A45CBEC5989F75205BABF4FE1449DF9`
- Corrected target SHA-256: `7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A`
- Crossref cache SHA-256: `013C3C48255FFFFAF3102F065B0EC98B1189AD93E56C43CBA3DD221CB00199AF`

The protected expanded source supplied the 50 DOI values used for verification. DOI and note fields remain absent from the target derivative and are not printed by the manuscript.

## DOI and record matching

- Crossref `/works/{doi}` returned a successful record for all 50 unique source DOI values.
- After normalization of capitalization, braces, HTML entities, accents, and dash glyphs, all 50 source titles matched their registered titles.
- All 50 author lists matched the registered author count and order. Full-name expansions for older records that expose initials only were retained from the prior verified library and checked against author identity or publisher pages.
- Year, volume, issue, and page/article identifiers matched populated Crossref fields, subject to the documented exceptions below.

## Author corrections

All 50 author fields were converted to stable BibTeX `Family, Given` form. The corrected file contains 170 authors and every author parses in either `Family, Given` or `Family, Jr., Given` form.

Confirmed factual corrections:

- `Mahin1989`: `P. Benson Shing` was corrected to `Shing, Pui-Shum B.` and `Craig R. Thewalt` to `Thewalt, Christopher R.`. The [ASCE article page](https://ascelibrary.org/doi/abs/10.1061/%28asce%290733-9445%281989%29115%3A8%282113%29) lists both full names.
- `Chae2013`: `Kasra Kazemibidokhti` was corrected to `Kazemibidokhti, Karim`; Crossref and the [Wiley article record](https://onlinelibrary.wiley.com/doi/10.1002/eqe.2294) agree on the author identity.
- `MacNeal1971`: `Robert H. MacNeal` was corrected to `MacNeal, Richard H.` using the [Elsevier article page](https://www.sciencedirect.com/science/article/pii/0045794971900319).

Suffix and compound-family-name controls:

- Seven records use `Spencer, Jr., Billie F.`: `Phillips2013`, `Phillips2013Feedforward`, `Fermandois2017`, `Najafi2020`, `NajafiSpencer2021`, `Najafi2023`, and `Silva2020`.
- `CraigBampton1968` uses `Craig, Jr., Roy R.`.
- `Condori2023` preserves `Condori Uribe, Johnny W.`; the [Frontiers article page](https://www.frontiersin.org/journals/built-environment/articles/10.3389/fbuil.2023.1270996/full) confirms the compound family name and author order.
- `PalacioBetancur2023` preserves `Palacio-Betancur` and `Gutierrez Soto`; `Besselink2013` preserves `van de Wouw`.
- `Miraglia2020` and `Tsokanas2022` use the publisher-supported `Stojadinovi{\'c}` spelling. No unsupported accents were added to other names.

## Venue, issue, and title protection corrections

- The following 18 records now use the formal journal name `Earthquake Engineering \& Structural Dynamics`: `Nakashima1992`, `NakashimaMasaoka1999`, `Horiuchi1999`, `Pan2005`, `Gao2013`, `Miraglia2020`, `Zhang2024`, `Wu2005`, `Wallace2005`, `MercanRicles2007`, `Mercan2008`, `ChenRicles2008`, `ChenRiclesMarullo2009`, `ChenRicles2012`, `Chae2013`, `Ou2015`, `Zhu2015`, and `HuangEESD2022`.
- `MacNeal1971` now uses the formal journal name `Computers \& Structures`.
- `Mucha2023` now includes `number = {7}`. The [Springer record](https://link.springer.com/article/10.1007/s11012-023-01675-0) confirms volume 58, issue 7, pages 1409--1425.
- `Krattiger2019` protects the registered proper names as `{Hurty/Craig--Bampton}`. The [Elsevier record](https://www.sciencedirect.com/science/article/pii/S088832701830284X) confirms the title wording.

No citation key, entry type, entry order, author order, substantive title wording, year, volume, or page value was changed. The only title-field edit adds braces around registered proper names.

## Registered-metadata exceptions retained deliberately

- Crossref currently exposes `eqe.4221` as the page value and omits the final volume/issue assignment for `Zhang2024`; the [Wiley version of record](https://onlinelibrary.wiley.com/doi/10.1002/eqe.4221) confirms `53(14):4334--4353`, so the final journal citation is retained.
- Seven records have an online-first year earlier than their assigned volume year: `Gao2013`, `ChenRiclesMarullo2009`, `Ou2015`, `PalacioBetancur2023`, `HuangEffect2022`, `HuangJVC2022`, and `Zhu2015`. The target uses the formal volume year.
- `Guyan1965` is a one-page item. `pages = {380}` is equivalent to Crossref's `380-380`.
- `HuangJVC2022` retains `number = {13--14}` as a valid double-issue range.

## Executed validation

- Deterministic candidate builder: 50 Crossref matches; 50 author corrections; 19 formal-journal-name corrections; one issue insertion; one proper-name protection; exit 0.
- Independent static validator: 50 target entries; 60 citation occurrences; 50 unique cited keys; 170/170 authors parsed as `Family, Given`; zero duplicate normalized titles; zero DOI literals; PASS.
- Traditional BibTeX test with `elsarticle-num-names.bst`: exit 0, 50 bibitems, zero BibTeX warnings, zero actual `\doi{...}` and `\nolinkurl{...}` calls.
- Biber 2.21 tool-mode datamodel validation: exit 0, validation complete, zero Biber log warnings or errors.
- Rendered `.bbl` spot checks confirmed correct output for both `Jr.` forms, all three compound-family-name cases, `Stojadinovi{\'c}`, formal ampersand journal names, and the protected `Hurty/Craig--Bampton` title.

The corrected bibliography metadata therefore passes the Stage 3 field, identity, parsing, and no-visible-DOI contracts.

## Manuscript integration check

The corrected target BibTeX was integrated with the unchanged `main_50refs_clean.tex` and compiled in `tmp/pdfs/stage3_compile` using pdfLaTeX, BibTeX, pdfLaTeX, and pdfLaTeX. All four commands exited 0.

- Output: 28 pages; 1,431,589 bytes; SHA-256 `F3E5EEEEA091BE3030741DD66D56374AD05B9C8AEC8F8B31BD65E4BCA9FFE637`.
- Final AUX/BBL: 60 citation lines, 50 bibcite entries, 50 bibitems, and 59 newlabel entries.
- Final LOG/BLG: zero LaTeX errors, undefined citations, undefined references, rerun requests, overfull/underfull boxes, missing characters, BibTeX warnings, or BibTeX errors.
- PDF text: zero `??`, `[?]`, DOI, nolinkurl, draft-title text, or missing-figure notice.
- Fonts: all 28 listed font records are embedded.
- Pages 25--28, containing all 50 references, were rendered at 130 dpi and inspected. No clipping, overlap, garbling, missing glyph, visible DOI, or revision marking was found.
- Text extraction confirmed seven `B. F. Spencer, Jr.` renderings, one `R. R. Craig, Jr.`, and the expected compound family names and protected titles.

This integration PDF is a technical Stage 3 check. Full 28-page visual acceptance remains workflow task 4.
