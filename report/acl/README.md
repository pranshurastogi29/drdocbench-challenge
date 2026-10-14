# Technical report (ACL format)

`paper.tex` and `references.bib` follow the ACL template. Compile with the official ACL style files:

1. Get `acl.sty` and `acl_natbib.bst` from https://github.com/acl-org/acl-style-files (or start from the ACL template on Overleaf and replace its `.tex` and `.bib`).
2. Put them next to `paper.tex`.
3. `pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper`

Packages used beyond the template: booktabs, multirow, amsmath, xcolor, tikz, pgfplots (all in TeX Live / Overleaf).
Before submitting, fill in the co-author names (TODO in the author block) and check the base-model disclosure in Section 8.
