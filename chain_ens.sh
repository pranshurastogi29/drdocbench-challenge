#!/bin/bash
cd "$(dirname "$0")"
R=runs/dev_all_v7_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_ens.jsonl --name ENS --restrict-to $R -q > runs/score_ENS.txt 2>&1 &
.venv/bin/python run_md2md_eval.py runs/dev_all_ens_snaps.jsonl --name ENS_S --restrict-to $R -q > runs/score_ENS_S.txt 2>&1 &
wait
{ grep -h '^\[' runs/score_ENS.txt runs/score_ENS_S.txt | cut -c1-140; echo; .venv/bin/python compare_runs.py ENS ENS_S 2>&1 | head -8; echo; echo '##### also vs v7'; .venv/bin/python compare_runs.py FINAL_v7 ENS_S 2>&1 | head -7; } > runs/compare_ens.txt 2>&1
echo done >> runs/compare_ens.txt
