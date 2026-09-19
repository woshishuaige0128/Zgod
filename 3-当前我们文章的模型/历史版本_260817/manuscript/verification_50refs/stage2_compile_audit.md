# RHTS Stage 2 technical compilation audit

Date: 2026-09-03

## Inputs

- `main_50refs_clean.tex`: 52,644 bytes; SHA-256 `EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995`
- `reference_50refs_clean.bib`: 16,610 bytes; SHA-256 `F48DD73DF3DF7927E90D07C1B81D24A540079A081B9039D494250E6078BB77EA`

## Compilation sequence

Working directory: `D:/JZ_PhD/10_论文_Papers/Li/RHTS/260817/manuscript`

Output directory: `tmp/pdfs/stage2_compile_final`

1. `pdflatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=tmp/pdfs/stage2_compile_final main_50refs_clean.tex` — exit 0
2. `bibtex tmp/pdfs/stage2_compile_final/main_50refs_clean` — exit 0
3. The same pdfLaTeX command — exit 0
4. The same pdfLaTeX command — exit 0

## Deterministic checks

- PDF: 28 pages; 1,431,001 bytes; SHA-256 `2BF849A0A0EF06C8F54A9793A8390ECBFA5171BEE032679958D1C0E5DA0021D6`.
- AUX: 60 citation lines, 50 bibcite entries, 59 newlabel entries.
- BBL: 50 bibitems, 0 actual `\doi{...}` calls, 0 `\nolinkurl{...}` calls.
- BLG: 0 warnings, 0 errors.
- LOG: 0 LaTeX errors, 0 undefined citations, 0 undefined references, 0 rerun requests, 0 overfull boxes, 0 underfull boxes, 0 missing characters.
- TeX/Bib source scan: 0 DOI tokens, 0 `\rev`, 0 `\newcommand`, 0 `\nolinkurl`.
- Extracted PDF text: 0 `??`, 0 `[?]`, 0 DOI, 0 nolinkurl, 0 `Draft with Sections`, 0 missing-figure notice.
- Fonts: all 28 listed font records are embedded.

## Rendered-page inspection

Pages 1, 9, 25, and 28 were rendered at 130 dpi and inspected. No clipping, overlap, garbled text, missing figure, visible revision marking, or DOI was found.

The initial version used the complete title as `\shorttitle`, which wrapped over the body header and produced 27 overfull-vbox warnings. The running title alone was shortened to `Craig--Bampton Reduction for MDOF-Coupled RTHS`; the full article title and manuscript text were unchanged. Recompilation reduced the warning count to zero.

## Known source-asset boundary

The source requests the nonexistent `figure/selected_v2/fig02_rths_loop_optionC.png`. The clean derivative maps this to the existing, frozen `submit_figure/fig01_rths_loop_optionD.png`. The replacement is a readable Chinese-labelled general RTHS feedback loop, but it does not explicitly depict the independent actuator-delay channels named by the unchanged caption. This is a scientific figure/caption mismatch in the available source assets, not a compilation failure; neither the figure nor caption was rewritten.

This PDF is an intermediate technical check. The final PDF will be regenerated and inspected page by page after the bibliography metadata corrections in workflow tasks 3 and 4.
