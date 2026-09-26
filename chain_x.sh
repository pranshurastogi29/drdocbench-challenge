#!/bin/bash
cd "$(dirname "$0")"
R=runs/dev_all_v7_final.jsonl
for v in N1 N2 N3 FT FB; do
  .venv/bin/python run_md2md_eval.py runs/dev_all_ensx_$v.jsonl --name ENSX_$v --restrict-to $R -q > runs/score_ENSX_$v.txt 2>&1 &
done
wait
{ grep -h '^\[' runs/score_ENS_SC.txt runs/score_ENSX_N1.txt runs/score_ENSX_N2.txt runs/score_ENSX_N3.txt runs/score_ENSX_FT.txt runs/score_ENSX_FB.txt | cut -c1-140
  for v in N1 N2 N3 FT FB; do echo; echo "##### ENS_SC -> ENSX_$v"; .venv/bin/python compare_runs.py ENS_SC ENSX_$v 2>&1 | head -7; done; } > runs/compare_x.txt 2>&1
echo done >> runs/compare_x.txt
