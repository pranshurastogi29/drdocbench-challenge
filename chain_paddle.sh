#!/bin/bash
# score Paddle-only and the two furniture-repositioned v7 variants with the official scorer (dev), then paired-compare with v7
cd "$(dirname "$0")"
R=runs/dev_all_v7_final.jsonl
.venv/bin/python run_md2md_eval.py runs/paddle_dev.jsonl --name PADDLE --restrict-to $R -q > runs/score_PADDLE.txt 2>&1 &
.venv/bin/python run_md2md_eval.py runs/dev_all_v7_fmove.jsonl --name V7_FMOVE --restrict-to $R -q > runs/score_V7_FMOVE.txt 2>&1 &
.venv/bin/python run_md2md_eval.py runs/dev_all_v7_fadd.jsonl --name V7_FADD --restrict-to $R -q > runs/score_V7_FADD.txt 2>&1 &
wait
{ grep -h '^\[' runs/score_FINAL_v7.txt runs/score_PADDLE.txt runs/score_V7_FMOVE.txt runs/score_V7_FADD.txt | cut -c1-140
  for n in V7_FMOVE V7_FADD PADDLE; do echo; echo "##### FINAL_v7 -> $n"; .venv/bin/python compare_runs.py FINAL_v7 $n 2>&1 | head -12; done; } > runs/compare_paddle.txt 2>&1
echo done >> runs/compare_paddle.txt
