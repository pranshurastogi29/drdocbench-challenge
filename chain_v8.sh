#!/bin/bash
# waits for the full v8 dev run, scores it with the official scorer, compares to the already-scored v7 run
cd "$(dirname "$0")"
while pgrep -f "[p]redict.py --fold all" >/dev/null; do sleep 10; done
cp runs/dev_all_full_bunny_v8.jsonl runs/dev_all_v8_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_v8_final.jsonl --name FINAL_v8 --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v8.txt 2>&1
{ echo "failed windows in v8 dev run: $(grep -c FAILED runs/full_bunny_v8.log) | rows $(wc -l < runs/dev_all_v8_final.jsonl)"
  grep -h '^\[' runs/score_FINAL_v7.txt runs/score_FINAL_v8.txt | cut -c1-140
  echo; .venv/bin/python compare_runs.py FINAL_v7 FINAL_v8; } > runs/compare_v7_v8.txt 2>&1
echo done >> runs/compare_v7_v8.txt
