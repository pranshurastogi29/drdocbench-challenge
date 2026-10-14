# Technical report (ACL format)

`paper.pdf` is the compiled report (7 pages). To rebuild it from `paper.tex` and `references.bib`:

1. Get `acl.sty` and `acl_natbib.bst` from https://github.com/acl-org/acl-style-files and put them next to `paper.tex`
   (or start from the ACL template on Overleaf and replace its `.tex` and `.bib`).
2. Either `tectonic paper.tex` (https://tectonic-typesetting.github.io, runs BibTeX itself), or
   `pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper`.

Packages used beyond the template: booktabs, multirow, amsmath, xcolor, tikz, pgfplots.
Before submitting, check the base-model disclosure in Section 8.
