#!/bin/bash
cd ~/Desktop/drdocbench
R=runs/dev_all_v7_final.jsonl
.venv/bin/python run_md2md_eval.py runs/mineru_dev.jsonl --name MINERU --restrict-to $R -q > runs/score_MINERU.txt 2>&1 &
.venv/bin/python run_md2md_eval.py runs/mineru_dev_ns.jsonl --name MINERU_NS --restrict-to $R -q > runs/score_MINERU_NS.txt 2>&1 &
wait
{ grep -h '^\[' runs/score_FINAL_v7.txt runs/score_ENS_SC.txt runs/score_PADDLE.txt runs/score_MINERU.txt runs/score_MINERU_NS.txt | cut -c1-140
  for n in MINERU MINERU_NS; do echo; echo "##### FINAL_v7 -> $n"; .venv/bin/python compare_runs.py FINAL_v7 $n 2>&1 | head -7; done; } > runs/compare_mineru.txt 2>&1
echo done >> runs/compare_mineru.txt
