# Poster

`poster.tex` is the A0 portrait poster for the DocInsights 2026 shared task (Dr.DocBench track) in ACL typography: Times
text and math (TeX Gyre Termes), Inconsolata, the ACL link colour, natbib author-year citations and the paper's reference
list (`../acl/references.bib`) formatted with `acl_natbib.bst`.

Compile with XeLaTeX or [tectonic](https://tectonic-typesetting.github.io), with `acl_natbib.bst` from
[acl-org/acl-style-files](https://github.com/acl-org/acl-style-files) next to `poster.tex`:

    tectonic poster.tex
    # or: xelatex poster && bibtex poster && xelatex poster && xelatex poster

Logos in `logos/` are the event and organiser marks, taken from their official sites: EMNLP 2026
(2026.emnlp.org), the DocInsights 2026 workshop (docinsights-workshop.github.io) and Abaka AI, which runs the
Dr.DocBench challenge (from the workshop's sponsor list). They belong to their owners.

For another board size, change `paperwidth` / `paperheight` in the `geometry` line.
`poster.pdf` is the compiled poster; it is also at https://pranshurastogi29.github.io/drdocbench/poster.pdf.
