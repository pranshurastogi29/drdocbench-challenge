# Poster

`poster.tex` is the A0 portrait poster for the DocInsights 2026 shared task (Dr.DocBench track) in ACL typography: Times
text and math (TeX Gyre Termes), Inconsolata, the ACL link colour, natbib author-year citations and the paper's reference
list (`../acl/references.bib`) formatted with `acl_natbib.bst`.

Compile with XeLaTeX or [tectonic](https://tectonic-typesetting.github.io), with `acl_natbib.bst` from
[acl-org/acl-style-files](https://github.com/acl-org/acl-style-files) next to `poster.tex`:

    tectonic poster.tex
    # or: xelatex poster && bibtex poster && xelatex poster && xelatex poster

For another board size, change `paperwidth` / `paperheight` in the `geometry` line.
`poster.pdf` is the compiled poster; it is also at https://pranshurastogi29.github.io/drdocbench/poster.pdf.
