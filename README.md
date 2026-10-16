# Dr.DocBench Challenge 2026: page image -> Markdown

Team **pranshu29** (Pranshu Rastogi, Rajneesh Tiwari). [Final confirmed leaderboard](https://drdocbench-challenge.abaka-pages.com/#leaderboard) (2026-10-13): **rank 7, Overall 84.54**
(Text_ED 0.1641, Table TEDS 71.86, Formula CDM 81.84, Reading Order 85.65) on the 509 test pages.

The task: turn each page image of the Dr.DocBench test set into Markdown; the challenge scores text edit distance, table
TEDS, formula CDM and reading order per page (md2md pipeline of the official scorer).

- **Paper (DOI)**: [10.5281/zenodo.23421062](https://doi.org/10.5281/zenodo.23421062) on Zenodo (preprint, CC BY 4.0; paper and poster PDFs).
- **Technical report**: read it online at <https://pranshurastogi29.github.io/drdocbench/>
  ([paper on Zenodo](https://doi.org/10.5281/zenodo.23421062)). Sources: `report/acl/paper.tex` (ACL format; see
  `report/acl/README.md` to compile) and `report/technical_report.html`.
- **LaTeX source package**: `report/arxiv/` (self-contained source: `paper.tex`, `paper.bbl`, `acl.sty`).
- **Poster** (A0, ACL typography): <https://pranshurastogi29.github.io/drdocbench/poster.pdf>; source in `report/poster/`.
- **Development summary**: `MILESTONES.md` (kept changes, ablations, what transferred, models, scorer findings) and
  `SUBMISSIONS.md` (leaderboard submissions). The commit history follows the same path, milestone by milestone.

## The system in one paragraph
One general vision-language model transcribes every page several times (prompts v6-v11, contrast preprocessing, one- and
two-page windows). PaddleOCR-VL and the MinerU pipeline add layout blocks, tables, formulas and word evidence. Each candidate
goes through the same rules (layout snap, Paddle tables, furniture merge), a minimum-Bayes-risk selector picks one candidate
per page using the official text + reading-order matching as utility (`mbr_refs_choose.py`, stack `sel=mbr8`), then spill
drop, boundary votes, cleanup and a gated word-level consensus (`rover.py`) refine it. Formula and
table candidate blocks are appended for the best-match formula and table metrics (technical report, Section 4). The whole post-model
pipeline is `stack.py`; it rebuilds every uploaded file byte-identically from the archived model outputs.

## Public release: what is not included
The model transcriptions of the development and test pages (`artifacts/`, `submissions/`, `runs/*.jsonl`) are not in this
repository: the pages come from copyrighted books. They were removed from the whole history. The dataset itself is on
Hugging Face (below). Without the archived outputs the model calls must be rerun; the free model we used
(`stealth/space-bunny-alpha` on OpenRouter) has since been withdrawn, so results will differ.

## Layout
- `predict.py`, `common.py`, `postprocess.py`, `prompts/`: model calls (OpenRouter or Hugging Face Inference Providers), 2-page windows, prompts
- `stack.py`, `build_submission.py`: deterministic post-model pipeline and submission builder (`python stack.py --split test --steps ...`)
- `mbr*.py`, `sel_lab.py`, `rover.py`: selection and consensus
- `snap.py`, `tablefix.py`, `furnmerge.py`, `spilldrop.py`, `bvote.py`, `artclean.py`, `wrapdup*.py`, `formula_pool.py`, `table_pool.py`: rules and candidate blocks
- `md2md_eval.py`, `ablate.py`, `ablate_vs.py`, `run_md2md_eval.py`: dev scoring with the official matcher, ablations with book-clustered bootstrap
- `probe_decode.py`, `lb_decode.py`, `group_merge.py`: decoding leaderboard A/B uploads
- `text_anatomy2.py`, `ro_anatomy3.py`, `cdm_anatomy.py` and other `*_eval.py` / `*_anatomy*.py`: analyses behind the report
- `paddle_ingest.py`, `mineru_ingest.py`, `kaggle/`: PaddleOCR-VL and MinerU on Kaggle GPUs
- `runs/*.txt`, `runs/*.usage.json`: score reports and API usage (no transcriptions)

## Running it
1. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `hf download 2077AIDataFoundation/DrDocBench --repo-type dataset --local-dir data`
3. `git clone https://github.com/2077AI/DrDocBench scorer && git -C scorer checkout <commit in SCORER_PIN.txt>`
4. Transcribe: `python predict.py --split dev --prompt v7 --max-side 1600 --tag v7` (and the other prompts); PaddleOCR-VL / MinerU via `kaggle/`.
5. Build and score: `python stack.py --split dev --steps "sel=mbr8,rules,fm,sd,bv,rv=free,ac" --out runs/dev_pipeline.jsonl`,
   then `python run_md2md_eval.py runs/dev_pipeline.jsonl --name pipeline -q`; ablations with `python ablate.py --variants "name=steps;..."`.

Model calls need `OPENROUTER_API_KEY` (or `HF_TOKEN` with `--api hf`) in `.env`, which is never committed.

## Citation

```bibtex
@misc{rastogi2026consensus,
  title     = {Consensus Selection over Prompt-Diverse {VLM} Transcriptions for Expert-Level Document Parsing},
  author    = {Rastogi, Pranshu and Tiwari, Rajneesh},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.23421062},
  url       = {https://doi.org/10.5281/zenodo.23421062},
  note      = {System description, Dr.DocBench track of the DocInsights 2026 shared task (EMNLP 2026)}
}
```

## License
MIT, see `LICENSE`. The Dr.DocBench data and the official scorer are not part of this repository and keep their own licenses.
