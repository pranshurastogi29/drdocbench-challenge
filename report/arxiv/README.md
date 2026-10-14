# arXiv submission

Upload `arxiv_submission.tar.gz` (the three files in `source/`: `paper.tex`, `paper.bbl`, `acl.sty`). arXiv compiles
LaTeX with pdfLaTeX and does not run BibTeX, so the bibliography ships as the generated `paper.bbl` (regenerate it from
`../acl/references.bib` with `acl_natbib.bst` whenever the references change, and keep its name equal to the `.tex` file's).

## Metadata for the submission form

**Title**

Consensus Selection over Prompt-Diverse VLM Transcriptions for Expert-Level Document Parsing

**Authors**

Pranshu Rastogi, Rajneesh Tiwari

**Abstract** (1348 characters; arXiv allows 1,920)

We describe a training-free system for the Dr.DocBench document-parsing challenge, which asks for Markdown transcriptions of difficult book pages and scores text, reading order, display formulas and tables. One general vision-language model transcribes every page many times under different prompts, image settings and window sizes. A page-level minimum-Bayes-risk (MBR) selector, whose utility is the challenge's own text and reading-order matching, picks one transcription per page. Deterministic rules derived from a close reading of the evaluator refine it, and a gated word-level consensus layer fixes recognition slips that independent OCR engines confirm. Because display formulas and tables are scored by best match, the submission also carries LaTeX and HTML candidate blocks. The final system scored 84.54 overall on the 509 test pages (Text_ED 0.1641, TEDS 71.86, CDM 81.84, reading order 85.65), rank 7. We document the full development path over 134 commits and more than 25 scored leaderboard submissions, ablate every component, quantify which development-set gains transferred to the hidden test set (selection changes: 68%; convention rules: none), locate the remaining error with diagnostic submissions, and report a large set of measured negative results, including five stronger commercial models that did not beat the ensemble.

**Comments**

9 pages, 2 figures, 6 tables. System description for the Dr.DocBench track of the DocInsights 2026 shared task (EMNLP 2026); rank 7 on the confirmed final leaderboard. Code: https://github.com/pranshurastogi29/drdocbench-challenge

**Primary category**: cs.CL (Computation and Language)

**Cross-list**: cs.CV (Computer Vision and Pattern Recognition)

**ACM class** (optional): I.2.7; I.7.5

**License**: CC BY 4.0 is the usual choice for ACL-style preprints (anyone may reuse with attribution); the default
arXiv licence (non-exclusive distribution) is more restrictive. Pick one before submitting; it cannot be changed later.

## Steps

1. Log in at https://arxiv.org/submit and start a new submission; accept the submission agreement.
2. Choose the licence and the primary category cs.CL (add cs.CV as a cross-list).
3. Upload `arxiv_submission.tar.gz`; arXiv unpacks it and compiles `paper.tex`.
4. Check the generated PDF preview: 9 pages, title as above, references present, no `??` marks.
5. Paste the title, authors, abstract and comments above into the metadata form.
6. Submit. New submissions are announced after the next daily cut-off (14:00 US Eastern, Monday to Friday).

cs.CL may ask a first-time submitter for an endorsement; an author who already has a cs.CL paper on arXiv is usually
endorsed automatically.

## After it is announced

Replace the venue line "Preprint 2026" on the site's publication entry with the arXiv ID, and add the arXiv link to the
README, the report page and the poster.
