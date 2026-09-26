#!/bin/bash
cd "$(dirname "$0")"
R=runs/dev_all_v7_final.jsonl
for v in snap snapg snaps snapm; do
  .venv/bin/python run_md2md_eval.py runs/dev_all_v7_$v.jsonl --name SNAP_$v --restrict-to $R -q > runs/score_SNAP_$v.txt 2>&1 &
done
wait
{ grep -h '^\[' runs/score_FINAL_v7.txt runs/score_SNAP_snap.txt runs/score_SNAP_snapg.txt runs/score_SNAP_snaps.txt runs/score_SNAP_snapm.txt | cut -c1-140
  for v in snap snapg snaps snapm; do echo; echo "##### FINAL_v7 -> SNAP_$v"; .venv/bin/python compare_runs.py FINAL_v7 SNAP_$v 2>&1 | head -7; done; } > runs/compare_snap.txt 2>&1
echo done >> runs/compare_snap.txt
