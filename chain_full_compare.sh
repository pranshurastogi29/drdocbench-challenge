#!/bin/bash
# waits for the full v7 dev run, scores v6 and v7 on the shared pages with the official scorer, writes runs/compare_v6_v7.txt
cd "$(dirname "$0")"
while pgrep -f "[p]redict.py --fold all" >/dev/null; do sleep 15; done
cp runs/dev_all_full_bunny_v7.jsonl runs/dev_all_v7_final.jsonl
.venv/bin/python run_md2md_eval.py runs/dev_all_full_bunny.jsonl --name FINAL_v6 --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v6.txt 2>&1 &
.venv/bin/python run_md2md_eval.py runs/dev_all_v7_final.jsonl --name FINAL_v7 --restrict-to runs/dev_all_v7_final.jsonl -q > runs/score_FINAL_v7.txt 2>&1 &
wait
{ echo "failed windows in v7 dev run: $(grep -c FAILED runs/full_bunny_v7.log)"
  grep -h '^\[' runs/score_FINAL_v6.txt runs/score_FINAL_v7.txt | cut -c1-140
  echo; .venv/bin/python compare_runs.py FINAL_v6 FINAL_v7; } > runs/compare_v6_v7.txt 2>&1
echo done >> runs/compare_v6_v7.txt
