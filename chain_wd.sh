#!/bin/bash
cd ~/Desktop/drdocbench
R=runs/dev_all_v7_final.jsonl
for v in wdF wdS; do .venv/bin/python run_md2md_eval.py runs/dev_all_$v.jsonl --name WD_$v --restrict-to $R -q > runs/score_WD_$v.txt 2>&1 & done
wait
{ grep -h '^\[' runs/score_FINAL5.txt runs/score_WD_wdF.txt runs/score_WD_wdS.txt | cut -c1-140
  for v in wdF wdS; do echo; echo "##### FINAL5 -> WD_$v"; .venv/bin/python compare_runs.py FINAL5 WD_$v 2>&1 | head -7; echo "-- formula check vs FINAL5:"; sed 's/FINAL_v7/FINAL5/; s/^new = .*//' formula_check.py > /dev/null; done; } > runs/compare_wd.txt 2>&1
echo done >> runs/compare_wd.txt
