#!/bin/bash
# wait for the v9 dev run, score it, then run the paired overall comparison and the formula-convention check against v7
cd "$(dirname "$0")"
while pgrep -f "[p]redict.py --fold all" >/dev/null; do sleep 15; done
cp runs/dev_all_full_bunny_v9.jsonl runs/dev_all_v9_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_v9_final.jsonl --name FINAL_v9 --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v9.txt 2>&1
{ echo "v9 dev rows: $(wc -l < runs/dev_all_v9_final.jsonl)  failed windows: $(grep -c FAILED runs/full_bunny_v9.log)"
  grep -h '^\[' runs/score_FINAL_v7.txt runs/score_FINAL_v9.txt | cut -c1-140
  echo; echo '##### paired, official components'; .venv/bin/python compare_runs.py FINAL_v7 FINAL_v9 2>&1 | head -9
  echo; echo '##### formula-convention check'; .venv/bin/python formula_check.py FINAL_v9 2>&1 | grep -v -i warning; } > runs/compare_v9.txt 2>&1
echo done >> runs/compare_v9.txt
