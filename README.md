# Dr.DocBench challenge: page image -> Markdown

Local record of the pipeline behind our submissions. Task: turn each page image of the Dr.DocBench test set (509 pages)
into Markdown; the challenge scores text edit distance, table TEDS, formula CDM and reading order per page (md2md).

**Best leaderboard result so far: 78.66** (`submissions/submission_final5.zip`). See `SUBMISSIONS.md` and `MILESTONES.md`.

## What is reproducible here

| Layer | Reproducible? | How |
|---|---|---|
| Everything after the model outputs (ensemble, snapping, table add, formula candidates, packaging) | **Yes, byte-for-byte** | `python build_submission.py final5_wd --verify` rebuilds from `artifacts/candidates_*.tar.gz` and compares to the uploaded zip (verified 509/509 pages for medoid4_snap, best, final5, final5_wd) |
| Scoring on dev | Yes | `run_md2md_eval.py` runs the official md2md scorer (`SCORER_PIN.txt`); reproduced our first leaderboard result within ~1 point (text 0.2001 vs 0.2257) |
| Kaggle image package | Yes | `python kaggle/build_package.py` (manifest and every image identical to what was uploaded) |
| LLM candidate outputs (`runs/*_all_*.jsonl`) | **No** (archived, not regenerable) | free alpha model `stealth/space-bunny-alpha` via OpenRouter, sampled; the model may change. The outputs are archived in `artifacts/` |
| PaddleOCR-VL 1.6 / MinerU 2.7.6 outputs | Rerunnable on Kaggle, not byte-identical | notebooks in `kaggle/`, driven by `kaggle/run_kaggle.py`; hashes in `ARTIFACTS.md` |
| First submissions (`v3*`, `v6`, `v7*`, `medoid*`) | Recorded artifacts only | produced by earlier code states; kept as files with hashes in `SUBMISSIONS.md` |

Scripts are at their **final** version. The commit history is organised by milestone, not by each individual edit, so an
early commit is not a runnable snapshot of what the code looked like at that moment.

## Layout
- `predict.py`, `common.py`, `postprocess.py`, `prompts/v0..v9.txt`: model calls (OpenRouter), windows of 2 pages, prompts, cleanup
- `run_md2md_eval.py`, `compare_runs.py`, `evaluate.py`, `reading_order.py`: official scorer wrapper, paired comparisons, early proxy scorer
- `snap.py`, `tablefix.py`, `wrapdup.py`, `variants.py`, `fill.py`, `normalize.py`, `furniture.py`: post-processing steps (kept and rejected ones)
- `paddle_ingest.py`, `mineru_ingest.py`, `kaggle/`: PaddleOCR-VL and MinerU on Kaggle GPUs
- `build_submission.py`: deterministic submission builder; `difficulty.py`, `predict_test.py`, `error_analysis*.py`, `contrast_check.py`, `formula_check.py`: analyses
- `chain_*.sh`, `sub*.sh`, `run*.sh`: the exact background jobs that were run
- `runs/*.txt`: score and comparison reports (the bulk `.jsonl` outputs are not tracked)

## Reproduce from a clean checkout
1. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `hf download 2077AIDataFoundation/DrDocBench --repo-type dataset --local-dir data`
3. `git clone https://github.com/2077AI/DrDocBench scorer && git -C scorer checkout <commit in SCORER_PIN.txt>`
4. `mkdir -p runs && tar xzf artifacts/candidates_test.tar.gz -C runs && tar xzf artifacts/candidates_dev.tar.gz -C runs`
5. Paddle layout blocks (needed by snapping and table add): unzip the Kaggle output to `kaggle/results/paddle/out/`
   (hash in `ARTIFACTS.md`) or rerun `kaggle/paddleocr_vl.ipynb`.
6. `python build_submission.py final5_wd --verify` (test) and `python run_md2md_eval.py runs/<file>.jsonl --name X -q` (dev scoring).
Model calls need `OPENROUTER_API_KEY` in `.env` (never committed); Kaggle calls need your own `~/.kaggle/access_token`.
