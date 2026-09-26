#!/bin/bash
cd "$(dirname "$0")"
R=runs/dev_all_v7_final.jsonl
for v in TA TR; do .venv/bin/python run_md2md_eval.py runs/dev_all_ensx_$v.jsonl --name ENSX_$v --restrict-to $R -q > runs/score_ENSX_$v.txt 2>&1 & done
wait
{ grep -h '^\[' runs/score_ENS_SC.txt runs/score_ENSX_FB.txt runs/score_ENSX_TA.txt runs/score_ENSX_TR.txt | cut -c1-140
  for v in TA TR; do echo; echo "##### ENS_SC -> ENSX_$v"; .venv/bin/python compare_runs.py ENS_SC ENSX_$v 2>&1 | head -7; done; } > runs/compare_t.txt 2>&1
echo done >> runs/compare_t.txt
