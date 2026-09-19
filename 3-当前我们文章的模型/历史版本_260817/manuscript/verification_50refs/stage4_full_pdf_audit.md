# Stage 4 full-PDF audit

- Date: 2026-09-03
- Status: PASS
- Scope: four-pass compilation and rendered inspection of every page of the 50-reference clean manuscript
- Formal TeX: `main_50refs_clean.tex`
- Formal BibTeX: `reference_50refs_clean.bib`
- Isolated PDF: `tmp/pdfs/stage4_compile/main_50refs_clean.pdf`

## Protected inputs

- TeX SHA-256: `EEF99EFC6DE547453715B00763A3112DD08D30A89261CE6E79F658B5DC67C995`
- BibTeX SHA-256: `7B0B812989075F310B237C9D4E1E54CBCEA2B08D44E96EB9C131CFD5B5F4649A`
- The TeX and BibTeX hashes were unchanged before and after this audit.

## Compilation

The effective pipeline completed in the required order:

1. `pdfLaTeX`: exit 0
2. `BibTeX`: exit 0
3. `pdfLaTeX`: exit 0
4. `pdfLaTeX`: exit 0

The first attempt to call BibTeX with the full Chinese absolute path was rejected after the path was mis-encoded by the Windows process. It produced no usable `.blg` or `.bbl` and did not modify any formal source. The unchanged BibTeX and style files were copied into the isolated build directory and BibTeX was rerun there with the ASCII job basename; that run exited 0. The failure and correction are retained here rather than hidden.

The final isolated PDF has 28 pages, 1,431,589 bytes, and SHA-256 `11E649BD0C471AFA831441AA2BB01CDF5B809383BEF4BAB31B65103A82323101`.

## Programmatic validation

`verify_stage4_pdf.py` and `stage4_pdf_validation.txt` record the following PASS results:

- 6 sections, 12 subsections, 22 `equation`, 2 `subequations`, 2 `align`, 5 tables, 9 figure environments, and 10 loaded image files.
- 60 citation occurrences, 50 unique citation keys, 50 `bibcite` records, 50 `bibitem` records, and 59 labels.
- Zero LaTeX errors, undefined citations, undefined references, rerun requests, overfull boxes, underfull boxes, missing characters, missing files, BibTeX warnings, or BibTeX errors.
- Zero `\\rev`, `\\citedoi`, `\\newcitedoi`, `\\newcommand`, `\\nolinkurl`, literal DOI, red-text command, or missing-figure placeholder in the formal source and extracted PDF text.
- All 28 fonts are embedded; all 28 pages contain extractable text; no extracted character lies outside a page boundary; no red PDF text character was found.
- The 544.252 by 742.677 pt page size is uniform and matches the protected historical Elsevier CAS manuscript.

## Rendered inspection of all 28 pages

All pages were rendered at 160 dpi and inspected individually.

- Pages 1--4: title, Ning Li and Yu Liang, abstract, Introduction, citations [1]--[50], running header, and footer are complete.
- Pages 5--12: all displayed equations from (2.1) through (3.8), Sections 2--4, citations, and Figure 1 are legible and remain inside the page boundaries.
- Pages 13--19: Figures 2--4, Tables 1--3, equations (4.1)--(4.5), section transitions, labels, subscripts, and table headings are complete.
- Pages 20--24: Figures 5--9, Tables 4--5, plot legends, axes, captions, Results and discussion, and the start of Conclusions are complete. Red curves and red coordinate labels occur only inside scientific figures and are not revision markup.
- Pages 25--28: Conclusions and references [1]--[50] are continuous and complete. Compound surnames, suffixes, accents, ampersands, and long wrapped entries render correctly. The final-page white space is normal.

No page contains clipping, overlap, garbled text, missing glyphs, missing images, black blocks, visible DOI text, citation placeholders, or red revision text.

## Non-blocking source and template observations

1. Figure 1 uses the only protected existing RHTS closed-loop asset. It is a Chinese general RHTS feedback-loop diagram and does not explicitly draw the independent actuator-delay channels named in the unchanged English caption. This is an image-content boundary, not a rendering failure.
2. Figures 1--4 retain Chinese figure numbers inside the protected source images while the manuscript supplies English external captions. These internal labels were not edited.
3. The title page contains an empty `ORCID(s):` field, and the supplied sources still do not contain affiliations or keywords. No metadata was invented.
4. The sentence beginning at the end of page 19 continues intact on page 21 after the full-page placement of Figures 5 and 6 on page 20. No text is missing. This is the Elsevier float placement produced by the protected source and is not an acceptance failure under the defined clipping, overlap, completeness, and cross-reference criteria.

The PDF remains an isolated Stage 4 acceptance artifact. Copying it to the formal delivery filename and recomputing the complete delivery/source manifest are reserved for Stage 5.

The 28 rendered page images and four local zoom crops remain organized under `tmp/pdfs/stage4_render`. Two cleanup commands were rejected before execution by the filesystem safety policy, so no deletion was claimed and no broader workaround was attempted. These files are disposable QA intermediates and are not part of the delivery set.
